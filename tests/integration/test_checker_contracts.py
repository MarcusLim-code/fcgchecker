import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fcgc.checking.compliance_checker import (
    CheckerUnavailable,
    compare_checkers,
    freeze_documents,
    freeze_packed_audit,
    render_checking_prompt,
)
from fcgc.cli import app
from fcgc.integrations.devin import DevinChecker
from fcgc.integrations.mock_checker import MockChecker
from fcgc.integrations.ollama_checker import LocalLLMChecker
from fcgc.integrations.synthetic_checker import SyntheticDemoChecker
from fcgc.retrieval.baseline import load_firmware
from fcgc.schemas.checking import ModelFindings, validate_findings
from fcgc.schemas.models import FetchedDocument

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "src/fcgc/fixtures/checking"


def task(good=False, suffix=""):
    path = FIXTURES / "pointer.md"
    document = FetchedDocument(
        source_id="pointer",
        title="pointer",
        source_ref="fcgc://demo/pointer.md",
        content=path.read_text() + suffix,
    )
    return freeze_documents(
        load_firmware(FIXTURES / ("pointer_good.c" if good else "pointer_bad.c"), "demo"),
        [document],
    )


@pytest.mark.parametrize("good, decision", [(True, "compliant"), (False, "violating")])
def test_demo_supported_source_backed_judgments(good, decision):
    frozen = task(good)
    result = SyntheticDemoChecker().check(frozen)
    assert result.status == "evaluated"
    assert result.findings[0].decision == decision
    validate_findings(frozen, ModelFindings(findings=result.findings))
    if not good:
        assert result.findings[0].locations[0].start_line == 3
    assert result.execution.skill_version == "1.1.0"
    assert result.execution.input_evidence_hash == frozen.evidence_hash()


def test_mock_is_deterministic_and_never_reads_ground_truth(monkeypatch):
    frozen = task()
    read = Path.read_text

    def protected(path, *args, **kwargs):
        if "ground_truth" in str(path):
            raise AssertionError("Checker read labels")
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", protected)
    first, second = MockChecker().check(frozen), MockChecker().check(frozen)
    assert first.status == second.status == "not_evaluated"
    assert first.findings == second.findings
    assert all(f.decision == "unresolved" for f in first.findings)
    assert first.execution.prompt_hash == second.execution.prompt_hash


@pytest.mark.parametrize("mutation", ["unknown_id", "quote", "source", "offset", "code"])
def test_reject_fabricated_findings(mutation):
    frozen = task()
    finding = SyntheticDemoChecker().check(frozen).findings[0].model_dump(mode="json")
    if mutation == "unknown_id":
        finding["evidence_id"] = "invented"
    elif mutation == "code":
        finding["locations"][0]["excerpt"] = "invented code"
    elif mutation == "quote":
        finding["citations"][0]["quote"] = "invented source"
    elif mutation == "source":
        finding["citations"][0]["source_ref"] = "unknown://source"
    else:
        finding["citations"][0]["start"] += 1
    with pytest.raises(ValueError):
        validate_findings(frozen, ModelFindings.model_validate({"findings": [finding]}))


def test_exception_and_unsupported_c_abstain():
    qualified = task(suffix="\nException: During recovery, the null guard may be omitted.\n")
    result = SyntheticDemoChecker().check(qualified)
    assert result.findings[0].decision == "unresolved"
    assert qualified.rules[0].exceptions
    original = task()
    # Extra behavior is outside the recognized single-function grammar.
    code = original.firmware.content + "int other(void) { return 1; }\n"
    import hashlib

    modified = original.model_copy(
        update={
            "firmware": original.firmware.model_copy(
                update={"content": code, "sha256": hashlib.sha256(code.encode()).hexdigest()}
            )
        }
    )
    assert SyntheticDemoChecker().check(modified).findings[0].decision == "unresolved"
    positive = ModelFindings(findings=SyntheticDemoChecker().check(original).findings)
    ambiguous = original.model_copy(
        update={
            "rules": [
                original.rules[0].model_copy(
                    update={
                        "ambiguity_status": "review_required",
                        "ambiguity_notes": ["Unreviewed scope"],
                    }
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="Unreviewed source ambiguity"):
        validate_findings(ambiguous, positive)


def test_no_evidence_and_incomplete_context_never_invoke_model(monkeypatch):
    checker = LocalLLMChecker("test:exact", allow_network=True)
    monkeypatch.setattr(checker, "post", lambda *args: pytest.fail("Unexpected network call"))
    empty = task().model_copy(update={"rules": [], "documents": []})
    assert checker.check(empty).status == "not_evaluated"
    incomplete = task().model_copy(update={"context_status": "incomplete_context"})
    assert checker.check(incomplete).findings[0].decision == "unresolved"


def test_network_opt_in_and_model_unavailability(monkeypatch):
    checker = LocalLLMChecker("test:exact")
    monkeypatch.setattr(checker, "post", lambda *args: pytest.fail("Network disabled"))
    assert checker.check(task()).status == "unavailable"
    enabled = LocalLLMChecker("test:exact", allow_network=True)

    def unavailable(*args):
        raise CheckerUnavailable("test connection refused")

    monkeypatch.setattr(enabled, "post", unavailable)
    assert enabled.check(task()).status == "unavailable"
    with pytest.raises(ValueError, match="allow_remote"):
        LocalLLMChecker("test:exact", endpoint="https://external.invalid")
    cloud = LocalLLMChecker("test:cloud", allow_network=True)
    calls = []

    def remote_metadata(path, payload):
        calls.append(path)
        return {"remote_host": "https://example.invalid"}

    monkeypatch.setattr(cloud, "post", remote_metadata)
    assert cloud.check(task()).status == "unavailable"
    assert calls == ["/api/show"]


@pytest.mark.parametrize("content", ["not JSON", '{"findings": []}', '{"findings": [{"bad": 1}]}'])
def test_malformed_model_response_rejected(monkeypatch, content):
    checker = LocalLLMChecker("test:exact", allow_network=True)

    def post(path, payload):
        return (
            {}
            if path == "/api/show"
            else {"done": True, "message": {"content": content}, "model": "test:exact"}
        )

    monkeypatch.setattr(checker, "post", post)
    result = checker.check(task())
    assert result.status == "error"
    assert result.findings[0].decision == "unresolved"


def test_same_frozen_task_model_settings_and_tokens_recorded(monkeypatch):
    frozen = task()
    content = ModelFindings(
        findings=SyntheticDemoChecker().check(frozen).findings
    ).model_dump_json()
    checkers = [
        LocalLLMChecker(model, allow_network=True) for model in ("model-a:tag", "model-b:tag")
    ]
    for checker in checkers:

        def post(path, payload):
            if path == "/api/show":
                return {"details": {"quantization_level": "test"}}
            assert payload["format"]["type"] == "object"
            assert payload["options"]["temperature"] == 0
            return {
                "done": True,
                "model": payload["model"],
                "message": {"content": content},
                "prompt_eval_count": 123,
                "eval_count": 45,
            }

        monkeypatch.setattr(checker, "post", post)
    results = compare_checkers(frozen, checkers)
    assert all(result.status == "evaluated" for result in results)
    assert {result.execution.model for result in results} == {"model-a:tag", "model-b:tag"}
    assert len({result.execution.input_evidence_hash for result in results}) == 1
    assert len({result.execution.prompt_hash for result in results}) == 1
    assert all(result.execution.input_tokens == 123 for result in results)
    assert "FCGC-PROMPT-V1" in render_checking_prompt(frozen)
    assert DevinChecker().check(frozen).status == "not_evaluated"


def test_cli_freeze_and_compare_offline(tmp_path):
    frozen = tmp_path / "task.json"
    output = tmp_path / "results.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "freeze-task",
            "--source",
            str(FIXTURES / "pointer_bad.c"),
            "--guideline",
            str(FIXTURES / "pointer.md"),
            "--output",
            str(frozen),
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "check-task",
            "--task",
            str(frozen),
            "--checker-config",
            str(ROOT / "src/fcgc/config/checker_demo.toml"),
            "--checker-config",
            str(ROOT / "src/fcgc/config/checker_mock.toml"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    results = json.loads(output.read_text())
    assert results[0]["findings"][0]["decision"] == "violating"
    assert results[1]["status"] == "not_evaluated"


def test_packed_tasks_preserve_selected_rules_without_restoring_full_context():
    frozen = freeze_packed_audit((ROOT / "benchmarks/v2/reports/stage6_C001.json").read_text())
    prompt = render_checking_prompt(frozen)
    assert "These similar terms are deliberately present to challenge retrieval." not in prompt
    assert len(frozen.rules) == 10
    assert all(rule.normative_statement in prompt.replace("\\n", "\n") for rule in frozen.rules)
    incomplete = freeze_packed_audit((ROOT / "benchmarks/v2/reports/stage7_C001.json").read_text())
    assert incomplete.context_status == "incomplete_context"
    assert MockChecker().check(incomplete).status == "not_evaluated"
