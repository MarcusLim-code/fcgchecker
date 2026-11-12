"""Release boundaries: contracts, source safety, unavailable providers and full CLI."""

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fcgc.checking.compliance_checker import freeze_documents
from fcgc.cli import app
from fcgc.core.files import read_source
from fcgc.experiments import runner
from fcgc.experiments.evaluation import EvaluationConfig, evaluate, write_reports
from fcgc.integrations.ollama_checker import LocalLLMChecker, NoRedirect
from fcgc.integrations.synthetic_checker import SyntheticDemoChecker
from fcgc.retrieval.baseline import load_firmware, retrieve_b0
from fcgc.retrieval.local_retriever import LocalFixtureRetriever
from fcgc.schemas.models import FetchedDocument, SearchScope

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "src/fcgc/fixtures/checking"
cli = CliRunner()


def frozen_task():
    return freeze_documents(
        load_firmware(FIXTURES / "pointer_bad.c", "demo"),
        [
            FetchedDocument(
                source_id="pointer",
                title="pointer",
                source_ref="fcgc://demo/pointer.md",
                content=read_source(FIXTURES / "pointer.md"),
            )
        ],
    )


def experiment_config(tmp_path, strategies='["b0", "p1"]'):
    original = (ROOT / "research/experiments/stage9_development.toml").read_text()
    original = original.replace("../../benchmarks/v2", str(ROOT / "benchmarks/v2"))
    original = original.replace(
        "../../outputs/experiments/stage9-development", str(tmp_path / "experiment")
    )
    original = original.replace('["b0", "p1", "p2", "p3"]', strategies)
    original = original.replace("repetitions = 3", 'repetitions = 1\ncase_ids = ["C001", "C002"]')
    config = tmp_path / "experiment.toml"
    config.write_text(original)
    return config


@pytest.mark.parametrize("kind", ["search", "fetch"])
def test_mutated_typed_provider_responses_are_revalidated(kind):
    class Invalid(LocalFixtureRetriever):
        def search(self, query, top_k):
            response = super().search(query, top_k)
            if kind == "search":
                response.hits[0].score = -1
            return response

        def fetch(self, source_id):
            return super().fetch(source_id).model_copy(update={"content": ""})

    with pytest.raises(ValueError):
        retrieve_b0(load_firmware(FIXTURES / "pointer_bad.c", "demo"), Invalid())


def test_local_documents_and_scope_do_not_leak_mutable_state():
    scope = SearchScope(allowed_source_ids=["pointers"])
    provider = LocalFixtureRetriever(scope=scope)
    scope.allowed_source_ids.clear()
    document = provider.fetch("pointers")
    document.content = "mutated by caller"
    assert provider.fetch("pointers").content != document.content
    result = provider.search("must", 8)
    result.scope.allowed_source_ids.clear()
    assert provider.scope.allowed_source_ids == ["pointers"]
    with pytest.raises(PermissionError):
        provider.fetch("resources")


def test_utf8_source_preserves_crlf_and_hash(tmp_path):
    source = tmp_path / "source.c"
    raw = b"int x(void) {\r\n    return 0;\r\n}\r\n"
    source.write_bytes(raw)
    firmware = load_firmware(source, "crlf")
    assert firmware.content.encode() == raw
    assert firmware.sha256 == hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="hash mismatch"):
        type(firmware).model_validate(firmware.model_copy(update={"sha256": "0" * 64}))


@pytest.mark.parametrize("content", [b"", b" \n", b"int a;\x00", b"\xff"])
def test_invalid_local_sources_fail_cleanly(tmp_path, content):
    source = tmp_path / "source.c"
    source.write_bytes(content)
    result = cli.invoke(app, ["features", "--source", str(source)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_source_limit_and_empty_guideline(tmp_path, monkeypatch):
    from fcgc.core import files

    monkeypatch.setattr(files, "MAX_SOURCE_BYTES", 5)
    source = tmp_path / "source.c"
    source.write_text("int x;")
    with pytest.raises(ValueError, match="byte local limit"):
        load_firmware(source, "large")
    document = tmp_path / "empty.md"
    document.write_text("")
    result = cli.invoke(app, ["extract-rules", "--document", str(document)])
    assert result.exit_code == 1 and "empty" in result.output
    with pytest.raises(ValueError, match="empty"):
        LocalFixtureRetriever(tmp_path)


@pytest.mark.parametrize("command", ["features", "check", "freeze-task", "retrieve"])
def test_cli_rejects_output_aliasing_input(tmp_path, command):
    source = tmp_path / "source.c"
    source.write_text("int x(void) { return 0; }\n")
    alias = tmp_path / "alias.c"
    alias.symlink_to(source)
    args = [command, "--source", str(source)]
    if command != "features":
        args += ["--case", "alias"]
    if command == "freeze-task":
        args += ["--guideline", str(FIXTURES / "pointer.md")]
    args += ["--log" if command == "retrieve" else "--output", str(alias)]
    before = source.read_bytes()
    result = cli.invoke(app, args)
    assert result.exit_code != 0 and "overwrite an input" in result.output
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "response",
    [
        [],
        None,
        7,
        {"done": True, "message": []},
        {"done": True, "message": {"content": "{}"}, "eval_count": -1},
        {"done": True, "message": {"content": "{}"}, "prompt_eval_count": True},
    ],
)
def test_unvalidated_ollama_transport_is_rejected(monkeypatch, response):
    checker = LocalLLMChecker("fixture:exact", allow_network=True)
    monkeypatch.setattr(
        checker, "post", lambda path, payload: {} if path == "/api/show" else response
    )
    result = checker.check(frozen_task())
    assert result.status == "error" and result.execution.error
    assert all(finding.decision == "unresolved" for finding in result.findings)


def test_malformed_ollama_metadata_and_timeout(monkeypatch):
    from fcgc.integrations import ollama_checker as local_llm

    checker = LocalLLMChecker("fixture:exact", allow_network=True, timeout=0.01)
    with monkeypatch.context() as context:
        context.setattr(checker, "post", lambda *args: [])
        assert checker.check(frozen_task()).status == "error"

    class TimedOut:
        def open(self, request, timeout):
            assert timeout == 0.01
            raise TimeoutError("synthetic transport timeout")

    monkeypatch.setattr(local_llm, "build_opener", lambda *args: TimedOut())
    result = checker.check(frozen_task())
    assert result.status == "unavailable" and "timeout" in result.execution.error
    with pytest.raises(ValueError, match="redirects"):
        NoRedirect().redirect_request(None, None, None, None, None, None)


def test_canonical_checker_rejects_invalid_adapter_metadata(monkeypatch):
    from fcgc.checking.compliance_checker import CanonicalChecker
    from fcgc.schemas.checking import ModelFindings

    frozen = frozen_task()
    prediction = ModelFindings(findings=SyntheticDemoChecker().check(frozen).findings)
    checker = CanonicalChecker()
    monkeypatch.setattr(checker, "predict", lambda *args: (prediction, None, -1, 3))
    result = checker.check(frozen)
    assert result.status == "error" and result.execution.input_tokens is None
    assert result.findings[0].decision == "unresolved"


def test_replay_checks_evidence_before_invoking_checker(tmp_path, monkeypatch):
    runner.run_experiment(experiment_config(tmp_path))
    path = tmp_path / "experiment/runs/C001-p1-r01/trace.json"
    raw = json.loads(path.read_text())
    raw["packed_checker_input"] += "altered task"
    path.write_text(json.dumps(raw))
    monkeypatch.setattr(
        runner, "make_checker", lambda *args: pytest.fail("Checker called before validation")
    )
    assert not runner.replay_run(path, tmp_path / "replay")
    trace = json.loads((tmp_path / "replay/trace.json").read_text())
    assert trace["status"] == "failed" and not trace["checker_results"]


def test_single_configuration_report_and_corrupt_source_detection(tmp_path):
    runner.run_experiment(experiment_config(tmp_path, '["b0"]'))
    config = EvaluationConfig(
        experiment_directories=[str(tmp_path / "experiment")],
        dataset_root=str(ROOT / "benchmarks/v2"),
        output_directory=str(tmp_path / "reports"),
    )
    report = evaluate(config)
    assert all(row["case_count"] == 0 for row in report["paired_comparisons"])
    # The renderer must also support report consumers omitting unavailable contrasts.
    report["paired_comparisons"] = []
    write_reports(report, Path(config.output_directory))
    assert (tmp_path / "reports/paired.csv").read_text().startswith("panel,comparison")
    path = tmp_path / "experiment/runs/C001-b0-r01/trace.json"
    raw = json.loads(path.read_text())
    raw["tool_calls"][1]["document"]["content"] += "tampered"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="source content hash mismatch"):
        evaluate(config)


def test_all_check_strategies_use_shared_trace_and_network_is_off(tmp_path, monkeypatch):
    from fcgc.integrations import ollama_checker as local_llm

    monkeypatch.setattr(local_llm, "build_opener", lambda *args: pytest.fail("Unexpected network"))
    for strategy in ("b0", "p1", "p2", "p3", "r"):
        output = tmp_path / f"{strategy}.json"
        result = cli.invoke(
            app,
            [
                "check",
                "--case",
                "C001",
                "--strategy",
                strategy,
                "--config",
                str(ROOT / "src/fcgc/config/benchmark.toml"),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["status"] == "not_evaluated"
        trace = json.loads(output.read_text())
        assert trace["pipeline"] and trace["task"] and trace["tool_calls"]
        assert trace["features"] and trace["packed_checker_input"]
    assert json.loads(cli.invoke(app, ["info"]).stdout)["skill"] == "1.1.0"


def test_one_command_acceptance_and_reports(tmp_path):
    result = cli.invoke(
        app,
        [
            "validate-local",
            "--dataset-root",
            str(ROOT / "benchmarks/v2"),
            "--output",
            str(tmp_path / "release"),
            "--repetitions",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["accepted"] and summary["runs"] == 40
    assert not summary["enterprise_verified"]
    assert summary["deterministic_demonstration"]["bad"]["decisions"] == ["violating"]
    for name in (
        "metrics.json",
        "summary.csv",
        "runs.csv",
        "paired.csv",
        "report.md",
        "report.html",
    ):
        assert (tmp_path / "release/evaluation" / name).is_file()
    assert SyntheticDemoChecker().check(frozen_task()).status == "evaluated"


def test_config_env_precedence_and_enterprise_contracts(monkeypatch):
    from fcgc.integrations.devin import DevinChecker
    from fcgc.retrieval.atlassian import AtlassianMCPRetriever

    monkeypatch.setenv("FCGC_CONFIG", str(ROOT / "config/local.toml"))
    assert json.loads(cli.invoke(app, ["doctor"]).stdout)["retriever"] == "benchmark"
    explicit = cli.invoke(app, ["doctor", "--config", str(ROOT / "src/fcgc/config/local.toml")])
    assert json.loads(explicit.stdout)["retriever"] == "local"
    contract = AtlassianMCPRetriever()
    with pytest.raises(NotImplementedError, match="enterprise access"):
        contract.search("guidelines", 3)
    with pytest.raises(NotImplementedError, match="enterprise access"):
        contract.fetch("unknown")
    assert DevinChecker().check(frozen_task()).status == "not_evaluated"
    blocked = cli.invoke(app, ["doctor", "--config", str(ROOT / "config/wd.example.toml")])
    assert blocked.exit_code == 1 and not json.loads(blocked.stdout)["offline_ready"]


def test_credential_bearing_provider_settings_rejected_before_logging():
    from fcgc.config import Settings

    with pytest.raises(ValueError, match="without credentials") as rejected:
        Settings(
            retriever="benchmark",
            checker="ollama",
            model="test:tag",
            ollama_url="https://user:secret@example.invalid",
            allow_remote=True,
        )
    assert "user:secret" not in str(rejected.value)


def test_crlf_guideline_spans_remain_exact():
    from fcgc.checking.rule_extractor import extract_rule_evidence

    content = (
        "# Synthetic\r\n\r\nWhen active, callers must release the handle.\r\n\r\n"
        "Exception: Recovery may omit release.\r\n"
    )
    document = FetchedDocument(
        source_id="crlf", title="crlf", source_ref="fcgc://crlf", content=content
    )
    extraction = extract_rule_evidence(document)
    assert extraction.rules and extraction.rules[0].conditions and extraction.rules[0].exceptions
    for rule in extraction.rules:
        for span in [rule.normative_span, rule.section_span]:
            assert span.excerpt == content[span.start : span.end]


def test_paired_bootstrap_is_independent_of_input_dictionary_order():
    from fcgc.experiments.statistics import paired_statistics

    values = {"C003": 2.0, "C001": -0.5, "C004": 3.0, "C002": 1.0}
    groups = {"C001": "a", "C002": "a", "C003": "b", "C004": "c"}
    first = paired_statistics(values, groups, samples=1000, seed=51)
    second = paired_statistics(dict(reversed(list(values.items()))), groups, samples=1000, seed=51)
    assert first == second
