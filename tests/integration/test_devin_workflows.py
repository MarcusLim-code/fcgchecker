"""Host orchestration and MCP handoff contracts; all enterprise receipts here are simulated."""

import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fcgc.agent.commands import invoke, parse_command
from fcgc.agent.session import load_session, read_json, start_session, submit_result
from fcgc.agent.skills import NAMES, inspect_skills
from fcgc.checking.compliance_checker import render_checking_prompt
from fcgc.cli import app
from fcgc.config import Settings
from fcgc.integrations.synthetic_checker import SyntheticDemoChecker
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.schemas.agent import AgentJudgment, HostContext
from fcgc.schemas.checking import ModelFindings
from fcgc.schemas.models import FetchedDocument, SearchHit, SearchResults

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "src/fcgc/fixtures/checking"
SOURCE = ROOT / "src/fcgc/fixtures/benchmark_cases/C001.c"


def host(tmp_path, **changes):
    values = dict(
        runtime="devin_cloud",
        environment_id="synthetic-test-environment",
        provider_id="fixture-bridge",
        permission_scope="synthetic-fixture-only",
        approved_workspace=str(ROOT),
        search_tool="fixture_search",
        fetch_tool="fixture_fetch",
        search_schema_sha256="1" * 64,
        fetch_schema_sha256="2" * 64,
        origin="synthetic_contract_test",
        connection_status="connected_but_unverified",
    )
    values.update(changes)
    return HostContext.model_validate(values)


def start_wd(tmp_path, *, source=SOURCE, strategy="p3", checker="mock", **kwargs):
    # Both fixture source and private output must live within this synthetic host's workspace.
    source_copy = tmp_path / source.name
    source_copy.write_bytes(source.read_bytes())
    return start_session(
        source_copy,
        tmp_path / "session",
        mode="wd",
        strategy=strategy,
        settings=Settings(retriever="agent_mcp", checker=checker),
        host=host(tmp_path, approved_workspace=tmp_path),
        allow_synthetic_handoff=True,
        **kwargs,
    )


def response_for(directory, provider=None, *, error=None, complete=True):
    session = load_session(directory)
    action = session.pending
    payload = dict(
        session_id=session.session_id,
        action_id=action.action_id,
        context_hash=session.host_hash,
        provider_id=session.host.provider_id,
        tool_name=action.tool_name,
        tool_call_id="synthetic-" + action.action_id,
        retrieved_at=datetime.now(UTC).isoformat(),
        duration_ms=4,
        complete=complete,
    )
    if error:
        payload["error"] = {"code": error, "message": "Synthetic transport failure"}
    elif action.operation == "search":
        payload["search"] = (
            (provider or BenchmarkLexicalRetriever())
            .search(action.query.text, action.query.document_top_k)
            .model_dump(mode="json")
        )
    else:
        payload["document"] = (
            (provider or BenchmarkLexicalRetriever())
            .fetch(action.source.source_id)
            .model_dump(mode="json")
        )
    return payload


def submit_payload(directory, payload):
    path = directory.parent / "reply.json"
    path.write_text(json.dumps(payload))
    return submit_result(directory, path)


def drive(directory, provider=None):
    for _ in range(30):
        session = load_session(directory)
        if session.status != "retrieval_required":
            return session
        submit_payload(directory, response_for(directory, provider))
    pytest.fail("Unbounded handoff loop")


def test_skills_have_valid_unique_verified_frontmatter():
    skills = inspect_skills(ROOT / ".agents/skills")
    assert {skill["name"] for skill in skills} == set(NAMES)
    for item in skills:
        metadata = item["metadata"]
        assert set(metadata) == {"name", "description", "argument-hint", "triggers"}
        assert "user" in metadata["triggers"]
    assert not (ROOT / ".devin/skills").exists()


@pytest.mark.parametrize("strategy", ["b0", "p1", "p2", "p3"])
def test_local_slash_check_offline_shared_core_and_read_only(tmp_path, monkeypatch, strategy):
    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **k: pytest.fail("Network in local mode")
    )
    before = SOURCE.read_bytes()
    result = invoke(f'/fcg-check "{SOURCE}" --strategy {strategy}', tmp_path / "local")
    session = load_session(tmp_path / "local")
    assert result["status"] == "complete" and result["checker_status"] == "not_evaluated"
    assert session.trace.pipeline and session.trace.features and session.trace.task
    assert session.trace.checker_results[0].execution.skill_version == "1.1.0"
    assert SOURCE.read_bytes() == before
    assert (tmp_path / "local/retrieval-snapshot.json").is_file()
    if strategy != "p3":
        assert result["counts"]["search_calls"] == 1


def test_rules_never_invoke_checker_and_show_reduction(tmp_path, monkeypatch):
    from fcgc.agent import session as sessions

    monkeypatch.setattr(
        sessions, "execute_checkers", lambda *a: pytest.fail("Inspection invoked checker")
    )
    result = invoke(f"/fcg-rules {SOURCE}", tmp_path / "rules")
    saved = load_session(tmp_path / "rules")
    assert result["status"] == "complete" and not saved.trace.checker_results
    report = (tmp_path / "rules/report.md").read_text()
    assert "Selection:" in report and "retained=" in report
    assert "source_ref" in (tmp_path / "rules/trace.json").read_text()


@pytest.mark.parametrize(
    "command",
    [
        "/fcg-check missing.c",
        "/fcg-rules missing.c",
        f"/fcg-check {SOURCE} --function missing_function",
        f"/fcg-check {SOURCE} --top-k 0",
        f"/fcg-check {SOURCE} --function invalid-name",
        f"/fcg-check {SOURCE} --mode wd",
        "/fcg-report --experiment unknown",
        "/fcg-compare --dataset unknown",
        "/fcg-compare --case C024",
        "/fcg-compare --mode wd",
        "/unknown",
        f"/fcg-check {SOURCE} --unused",
    ],
)
def test_invalid_arguments_and_unavailable_wd_fail_explicitly(tmp_path, command):
    with pytest.raises((OSError, ValueError)):
        invoke(command, tmp_path / "out")


def test_function_focus_and_missing_function_keep_original_lines(tmp_path):
    source = tmp_path / "target.c"
    source.write_text("int first(void) { return 0; }\n\nint second(void) { return 1; }\n")
    result = invoke(f"/fcg-check {source} --function second --strategy p1", tmp_path / "run")
    session = load_session(tmp_path / "run")
    assert result["function"] == {"name": "second", "start_line": 3, "end_line": 3}
    assert session.trace.task.target_function == "second"
    assert session.trace.task.firmware.content == source.read_text()
    assert "target_function" in render_checking_prompt(session.trace.task)


def test_all_wd_handoffs_reuse_local_core_without_live_provider(tmp_path, monkeypatch):
    from fcgc.agent import session as sessions

    monkeypatch.setattr(
        sessions, "make_retriever", lambda *a: pytest.fail("Direct MCP/local substitution")
    )
    result = start_wd(tmp_path)
    assert (
        result["status"] == "retrieval_required"
        and result["action"]["query"]["template_version"] == "p1-template-v2"
    )
    directory = tmp_path / "session"
    session = drive(directory)
    assert session.status == "complete" and session.trace.pipeline
    assert session.trace.pipeline.status == "insufficient_evidence"
    assert session.trace.traffic_kind == "synthetic_contract_test"
    assert len([c for c in session.calls if c.action.operation == "search"]) == 3
    assert len([c for c in session.calls if c.action.operation == "fetch"]) <= 8
    assert len({c.action.query.text for c in session.calls if c.action.query}) == 3
    assert all(c.result.retrieved_at.tzinfo is not None for c in session.calls)
    assert session.trace.checker_results[0].status == "not_evaluated"


def test_legacy_replay_provider_still_available_through_slash_command(tmp_path):
    config = ROOT / "src/fcgc/config/replay.toml"
    source = ROOT / "src/fcgc/fixtures/benchmark_cases/C002.c"
    result = invoke(f"/fcg-check {source} --strategy p1 --config {config}", tmp_path / "replay")
    assert result["retrieval_provider"] == "replay" and result["checker_status"] == "not_evaluated"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_ref",
        "wrong_query",
        "wrong_id",
        "wrong_host",
        "duplicate",
        "wrong_tool",
        "wrong_provider",
        "oversized_k",
        "scope",
    ],
)
def test_bad_search_handoffs_rejected_without_consuming_action(tmp_path, mutation):
    start_wd(tmp_path)
    directory = tmp_path / "session"
    payload = response_for(directory)
    if mutation == "missing_ref":
        del payload["search"]["hits"][0]["source_ref"]
    elif mutation == "wrong_query":
        payload["search"]["query"] = "other query"
    elif mutation == "wrong_id":
        payload["action_id"] = "other request"
    elif mutation == "wrong_host":
        payload["context_hash"] = "other cloud session"
    elif mutation == "duplicate":
        payload["search"]["hits"][1] = payload["search"]["hits"][0]
    elif mutation == "wrong_tool":
        payload["tool_name"] = "other tool"
    elif mutation == "wrong_provider":
        payload["provider_id"] = "other provider"
    elif mutation == "oversized_k":
        payload["search"]["hits"] *= 2
    else:
        payload["search"]["scope"] = {"allowed_source_ids": ["other"], "allowed_scopes": []}
    with pytest.raises(ValueError):
        submit_payload(directory, payload)
    assert load_session(directory).pending.action_id.endswith("-001")
    assert not load_session(directory).calls


def test_bad_fetch_and_partial_response_cannot_claim_evaluated(tmp_path):
    start_wd(tmp_path, strategy="p1")
    directory = tmp_path / "session"
    submit_payload(directory, response_for(directory, complete=False))
    payload = response_for(directory)
    payload["document"]["source_ref"] = "https://other.invalid"
    with pytest.raises(ValueError, match="identity"):
        submit_payload(directory, payload)
    session = drive(directory)
    assert session.trace.task.context_status == "incomplete_context"
    assert session.trace.checker_results[0].status == "not_evaluated"


@pytest.mark.parametrize("code", ["authentication", "permission"])
def test_authentication_and_permission_do_not_retry_or_substitute(tmp_path, code):
    start_wd(tmp_path)
    directory = tmp_path / "session"
    result = submit_payload(directory, response_for(directory, error=code))
    assert result["status"] == "error" and result["checker_status"] == "not_evaluated"
    assert result["counts"]["search_calls"] == 1 and result["counts"]["transport_retries"] == 0


def test_timeout_fallback_and_empty_results_stop_within_budgets(tmp_path):
    start_wd(tmp_path)
    directory = tmp_path / "session"
    first = submit_payload(directory, response_for(directory, error="timeout"))
    assert first["status"] == "retrieval_required"
    assert first["action"]["query"]["search_number"] == 2

    class Empty:
        def search(self, query, top_k):
            return SearchResults(query=query, hits=[])

    session = drive(directory, Empty())
    assert session.status == "error" and session.trace.pipeline.status == "insufficient_evidence"
    assert len(session.calls) <= 3


def test_deadline_changed_code_and_receipt_tampering_are_explicit(tmp_path):
    start_wd(tmp_path)
    directory = tmp_path / "session"
    reply = response_for(directory)
    path = directory / "session.json"
    raw = read_json(path)
    raw["deadline"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(raw))
    result = submit_payload(directory, reply)
    assert result["status"] == "error" and "wall-time" in result["warnings"][0]
    # Receipt and checkpoint must agree even without independent live authentication.
    receipt = directory / "handoffs/001.json"
    content = read_json(receipt)
    content["tool_call_id"] = "tampered"
    receipt.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="receipt"):
        load_session(directory)


def test_cross_environment_scope_and_synthetic_opt_in(tmp_path):
    copied = tmp_path / "code.c"
    copied.write_bytes(SOURCE.read_bytes())
    with pytest.raises(ValueError, match="test opt-in"):
        start_session(
            copied, tmp_path / "out", mode="wd", host=host(tmp_path, approved_workspace=tmp_path)
        )
    with pytest.raises(ValueError, match="approved"):
        start_session(
            SOURCE,
            tmp_path / "out",
            mode="wd",
            host=host(tmp_path, approved_workspace=tmp_path),
            allow_synthetic_handoff=True,
        )
    with pytest.raises(ValueError, match="substitution"):
        start_session(
            copied,
            tmp_path / "out",
            mode="wd",
            host=host(tmp_path),
            settings=Settings(retriever="benchmark", checker="mock"),
            allow_synthetic_handoff=True,
        )


class PointerProvider:
    document = FetchedDocument(
        source_id="pointer",
        title="Synthetic pointer",
        source_ref="fcgc://demo/pointer.md",
        content=(FIXTURE / "pointer.md").read_text(),
    )

    def search(self, query, top_k):
        return SearchResults(
            query=query,
            hits=[
                SearchHit(
                    source_id="pointer",
                    title=self.document.title,
                    source_ref=self.document.source_ref,
                )
            ],
        )

    def fetch(self, source_id):
        return self.document


def test_agent_checker_uses_exact_canonical_task_and_validates_citations(tmp_path):
    start_wd(tmp_path, source=FIXTURE / "pointer_bad.c", strategy="p1", checker="devin")
    directory = tmp_path / "session"
    session = drive(directory, PointerProvider())
    assert session.status == "checking_required"
    task = session.trace.task
    supported = SyntheticDemoChecker().check(task)
    assert supported.status == "evaluated"
    action = session.pending
    judgment = AgentJudgment(
        session_id=session.session_id,
        action_id=action.action_id,
        context_hash=session.host_hash,
        evidence_hash=task.evidence_hash(),
        prompt_hash=action.prompt_hash,
        model_identifier=None,
        findings=ModelFindings(findings=supported.findings),
    )
    corrupt = judgment.model_dump(mode="json")
    corrupt["findings"]["findings"][0]["citations"][0]["quote"] = "invented"
    with pytest.raises(ValueError, match="source excerpt"):
        submit_payload(directory, corrupt)
    result = submit_payload(directory, judgment.model_dump(mode="json"))
    completed = load_session(directory)
    assert (
        result["checker_status"] == "evaluated"
        and result["live_access_verified_by_python"] is False
    )
    checked = completed.trace.checker_results[0]
    assert (
        checked.execution.provider == "simulated_devin_agent"
        and checked.execution.model == "unreported"
    )
    assert checked.execution.input_tokens is None and checked.execution.output_tokens is None
    assert checked.execution.skill_version == "1.1.0"
    assert (
        checked.execution.prompt_hash
        == hashlib.sha256(render_checking_prompt(task).encode()).hexdigest()
    )
    assert "violating" in (directory / "report.md").read_text()


def test_compare_and_report_share_runner_no_label_leak_and_no_reretrieval(tmp_path, monkeypatch):
    from fcgc.experiments import runner

    config = ROOT / "src/fcgc/config/benchmark.toml"
    result = invoke(
        f"/fcg-compare --case C001 --repeat 1 "
        f"--dataset-root {ROOT / 'benchmarks/v2'} --config {config}",
        tmp_path / "matrix",
    )
    assert result["experiment"]["runs"] == 8 and result["experiment"]["failed"] == 0
    records = [read_json(p) for p in (tmp_path / "matrix/experiment/runs").glob("*/trace.json")]
    assert {r["strategy"] for r in records} == {"b0", "p1", "p2", "p3"}
    assert {r["firmware"]["case_id"] for r in records} == {"C001", "C002"}
    assert all(r["checker_results"][0]["status"] == "not_evaluated" for r in records)
    assert len({r["checker_results"][0]["execution"]["instruction_hash"] for r in records}) == 1
    monkeypatch.setattr(runner, "make_retriever", lambda *a: pytest.fail("Report reran retrieval"))
    reported = invoke(
        f"/fcg-report --experiment latest --runs-root {tmp_path}", tmp_path / "report"
    )
    assert reported["retrieval_rerun"] is False
    assert set(reported["reports"]) == {
        "report.md",
        "metrics.json",
        "summary.csv",
        "runs.csv",
        "paired.csv",
        "report.html",
    }


def test_doctor_status_and_cli_simulation_not_native_registration(tmp_path, monkeypatch):
    from fcgc.agent import doctor

    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    result = invoke(f"/fcg-doctor --dataset-root {ROOT / 'benchmarks/v2'}", tmp_path / "doctor")
    assert result["devin_runtime"]["status"] == "unavailable"
    assert (
        result["skills"]["status"] == "ready"
        and result["skills"]["native_registration"] == "unverified"
    )
    assert result["atlassian_mcp"]["status"] == "not_configured"
    command = f"/fcg-check {SOURCE} --strategy p1"
    invoked = CliRunner().invoke(
        app, ["agent", "invoke", "--command", command, "--output", str(tmp_path / "cli")]
    )
    assert invoked.exit_code == 0, invoked.output
    assert json.loads(invoked.stdout)["checker_status"] == "not_evaluated"
    assert parse_command('/fcg-check "file with spaces.c"')[1].source == Path("file with spaces.c")


def test_malformed_oversized_handoff_and_symlink_outputs_fail_safely(tmp_path):
    start_wd(tmp_path)
    directory = tmp_path / "session"
    path = tmp_path / "response.json"
    path.write_text("[")
    with pytest.raises(ValueError):
        submit_result(directory, path)
    path.write_text(" " * 2_000_001)
    with pytest.raises(ValueError, match="byte limit"):
        submit_result(directory, path)
    original = (directory / "report.md").read_bytes()
    (directory / "report.md").unlink()
    (directory / "report.md").symlink_to(directory.parent / SOURCE.name)
    before = (directory.parent / SOURCE.name).read_bytes()
    with pytest.raises(ValueError, match="symlink"):
        submit_payload(directory, response_for(directory))
    assert (directory.parent / SOURCE.name).read_bytes() == before and original


def test_duplicate_json_and_secret_headers_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"session_id":"a","session_id":"b"}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        read_json(path)
    start_wd(tmp_path)
    directory = tmp_path / "session"
    reply = response_for(directory, error="authentication")
    reply["error"]["message"] = "Authorization: Bearer test-secret"
    with pytest.raises(ValueError) as rejected:
        submit_payload(directory, reply)
    assert "test-secret" not in str(rejected.value)


def test_requested_checker_unavailable_is_failed_in_trace(tmp_path):
    source = tmp_path / "pointer.c"
    source.write_bytes((FIXTURE / "pointer_bad.c").read_bytes())
    settings = Settings(retriever="agent_mcp", checker="ollama", model="unavailable:tag")
    start_session(
        source,
        tmp_path / "session",
        mode="wd",
        strategy="p1",
        settings=settings,
        host=host(tmp_path, approved_workspace=tmp_path),
        allow_synthetic_handoff=True,
    )
    session = drive(tmp_path / "session", PointerProvider())
    assert session.status == "error" and session.trace.status == "failed"
    assert session.trace.checker_results[0].status == "unavailable"
    assert session.trace.errors


def test_focus_rejects_violations_outside_selected_function(tmp_path):
    from fcgc.checking.compliance_checker import freeze_documents
    from fcgc.retrieval.baseline import load_firmware
    from fcgc.schemas.checking import validate_findings

    original = freeze_documents(
        load_firmware(FIXTURE / "pointer_bad.c", "pointer"), [PointerProvider.document]
    )
    finding = SyntheticDemoChecker().check(original).findings
    focused = original.model_copy(
        update={"target_function": "scope", "target_start_line": 4, "target_end_line": 4}
    )
    with pytest.raises(ValueError, match="outside the requested function"):
        validate_findings(focused, ModelFindings(findings=finding))


def test_no_provider_scores_or_usage_are_fabricated(tmp_path):
    start_wd(tmp_path, strategy="p1")
    directory = tmp_path / "session"
    session = drive(directory, PointerProvider())
    assert session.trace.pipeline.retrieval.search_results.hits[0].score is None
    result = read_json(directory / "result.json")
    assert result["billed_tokens"] is None and result["rovo_credits"] is None
    assert result["severity"] is None and result["rules_evaluated"] == 0


def test_explicit_experiment_config_does_not_silently_ignore_case_options(tmp_path):
    config = ROOT / "research/experiments/stage9_development.toml"
    with pytest.raises(ValueError, match="not both"):
        invoke(f"/fcg-compare --experiment-config {config} --case C024", tmp_path / "mixed")
