import json
from pathlib import Path

import pytest

from fcgc.checking.compliance_checker import compare_checkers
from fcgc.experiments import runner
from fcgc.integrations.mock_checker import MockChecker
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.schemas.stage9 import RunTrace

ROOT = Path(__file__).resolve().parents[2]


def specification(tmp_path, strategies='["b0", "p1", "p2", "p3"]', repetitions=1):
    text = (ROOT / "research/experiments/stage9_development.toml").read_text()
    text = text.replace("../../benchmarks/v2", str(ROOT / "benchmarks/v2"))
    text = text.replace("../../outputs/experiments/stage9-development", str(tmp_path / "output"))
    text = text.replace('strategies = ["b0", "p1", "p2", "p3"]', f"strategies = {strategies}")
    text = text.replace(
        "repetitions = 3", f'case_ids = ["C001", "C002"]\nrepetitions = {repetitions}'
    )
    path = tmp_path / "experiment.toml"
    path.write_text(text)
    return path


def traces(tmp_path):
    return [
        RunTrace.model_validate_json(p.read_text())
        for p in sorted((tmp_path / "output/runs").glob("*/trace.json"))
    ]


def test_full_matrix_trace_completeness_and_no_label_access(tmp_path, monkeypatch):
    original = Path.read_text

    def guard(path, *args, **kwargs):
        if "ground_truth" in str(path):
            pytest.fail("Runtime touched annotation labels")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guard)
    result = runner.run_experiment(specification(tmp_path))
    assert result["runs"] == result["finished"] == 8
    records = traces(tmp_path)
    for trace in records:
        assert trace.pipeline is not None
        assert trace.features is not None
        assert trace.task is not None
        assert trace.snapshot_hash and trace.snapshot_path
        assert trace.tool_calls[0].operation == "search"
        assert trace.tool_calls[0].search_result.query == trace.tool_calls[0].query
        assert trace.segmented_documents and trace.selected_ids
        assert trace.source_content_hashes
        assert trace.stage_latencies and trace.end_to_end_ms > 0
        assert trace.checker_results[0].status == "not_evaluated"
        assert trace.checker_results[0].execution.skill_version == "1.1.0"
        assert trace.traffic_kind == "local_fixture"
        assert trace.task.full_document_context == (trace.strategy in {"b0", "p1"})
    assert (
        len({trace.firmware.sha256 for trace in records if trace.firmware.case_id == "C001"}) == 1
    )
    c001 = {trace.strategy: trace for trace in records if trace.firmware.case_id == "C001"}
    phrase = "These similar terms are deliberately present to challenge retrieval."
    assert phrase in c001["p1"].packed_checker_input
    assert phrase not in c001["p2"].packed_checker_input


def test_fresh_provider_and_checker_instances_and_three_repetitions(tmp_path, monkeypatch):
    providers, checkers = [], []

    def provider(settings):
        obj = BenchmarkLexicalRetriever()
        providers.append(obj)
        return obj

    class Once(MockChecker):
        def check(self, task):
            assert not hasattr(self, "used")
            self.used = True
            return super().check(task)

    def checker(settings):
        obj = Once()
        checkers.append(obj)
        return obj

    monkeypatch.setattr(runner, "make_retriever", provider)
    monkeypatch.setattr(runner, "make_checker", checker)
    config = specification(tmp_path, '["p1"]', repetitions=3)
    result = runner.run_experiment(config)
    assert result["runs"] == 6
    assert len(providers) == len(checkers) == 6
    assert len({id(obj) for obj in providers}) == 6
    # Re-entering an identical lock resumes without another provider call.
    runner.run_experiment(config)
    assert len(providers) == 6


def test_failed_run_has_snapshot_errors_and_incomplete_stages(tmp_path, monkeypatch):
    class Broken:
        def search(self, query, top_k):
            raise OSError("synthetic backend failure")

    monkeypatch.setattr(runner, "make_retriever", lambda settings: Broken())
    result = runner.run_experiment(specification(tmp_path, '["b0"]'))
    assert result["failed"] == 2
    for trace in traces(tmp_path):
        assert trace.errors and trace.incomplete_stages
        assert trace.tool_calls[0].error_type == "OSError"
        assert trace.snapshot_path
        assert trace.task is None
    assert runner.replay_run(
        tmp_path / "output/runs/C001-b0-r01/trace.json", tmp_path / "failed-replay"
    )


def test_exact_replay_never_constructs_live_provider_and_task_can_change_checker(
    tmp_path, monkeypatch
):
    runner.run_experiment(specification(tmp_path))
    run = tmp_path / "output/runs/C001-p1-r01/trace.json"
    monkeypatch.setattr(runner, "make_retriever", lambda settings: pytest.fail("Live retrieval"))
    assert runner.replay_run(run, tmp_path / "replay")
    for strategy in ("b0", "p2", "p3"):
        assert runner.replay_run(
            tmp_path / f"output/runs/C001-{strategy}-r01/trace.json",
            tmp_path / f"replay-{strategy}",
        )
    replayed = RunTrace.model_validate_json((tmp_path / "replay/trace.json").read_text())
    original = RunTrace.model_validate_json(run.read_text())
    assert replayed.task.evidence_hash() == original.task.evidence_hash()
    assert replayed.traffic_kind == "recorded_replay"
    results = compare_checkers(original.task, [MockChecker(), MockChecker()])
    assert len({r.execution.input_evidence_hash for r in results}) == 1


def test_missing_or_tampered_snapshot_cannot_reconstruct_from_hash(tmp_path):
    runner.run_experiment(specification(tmp_path, '["b0"]'))
    run = tmp_path / "output/runs/C001-b0-r01/trace.json"
    trace = RunTrace.model_validate_json(run.read_text())
    snapshot = tmp_path / "output" / trace.snapshot_path
    content = snapshot.read_text()
    snapshot.unlink()
    with pytest.raises(ValueError, match="snapshot unavailable"):
        runner.replay_run(run, tmp_path / "replay")
    raw = json.loads(content)
    raw["calls"][0]["query"] = "tampered"
    snapshot.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.replay_run(run, tmp_path / "replay")


def test_configuration_and_code_lock_reject_changes(tmp_path, monkeypatch):
    config = specification(tmp_path, '["b0"]')
    runner.run_experiment(config)
    original = config.read_text()
    config.write_text(
        original.replace("context_token_budget = 12000", "context_token_budget = 13000")
    )
    with pytest.raises(ValueError, match="lock mismatch"):
        runner.run_experiment(config)
    config.write_text(original)
    monkeypatch.setattr(runner, "code_hash", lambda: "changed")
    with pytest.raises(ValueError, match="code or canonical instructions changed"):
        runner.replay_run(tmp_path / "output/runs/C001-b0-r01/trace.json", tmp_path / "replay")


def test_split_boundary_and_snapshot_approval(tmp_path):
    config = specification(tmp_path)
    original = config.read_text()
    config.write_text(original.replace('split = "development"', 'split = "heldout"'))
    with pytest.raises(ValueError, match="crosses"):
        runner.run_experiment(config)
    config.write_text(original.replace("snapshots_approved = true", "snapshots_approved = false"))
    with pytest.raises(ValueError, match="approve"):
        runner.run_experiment(config)


def test_optional_reference_and_recorded_retrieval_variability(tmp_path, monkeypatch):
    number = 0

    class Varying(BenchmarkLexicalRetriever):
        def search(self, query, top_k):
            response = super().search(query, top_k)
            if self.reverse:
                response.hits.reverse()
            return response

    def provider(settings):
        nonlocal number
        obj = Varying()
        obj.reverse = bool(number % 2)
        number += 1
        return obj

    monkeypatch.setattr(runner, "make_retriever", provider)
    result = runner.run_experiment(specification(tmp_path, '["r"]', repetitions=3))
    assert result["runs"] == 6
    for values in result["retrieval_variability"].values():
        assert len(values) == 3
        assert len({tuple(value["ordered_sources"]) for value in values}) > 1
    assert all(len(trace.source_content_hashes) == 8 for trace in traces(tmp_path))


def test_checker_matrix_reuses_one_frozen_retrieval(tmp_path):
    config = specification(tmp_path, '["p1"]')
    config.write_text(
        config.read_text() + '\n[[checkers]]\nretriever="benchmark"\nchecker="synthetic_demo"\n'
    )
    runner.run_experiment(config)
    for trace in traces(tmp_path):
        assert sum(call.operation == "search" for call in trace.tool_calls) == 1
        assert len(trace.checker_results) == 2
        assert len({result.execution.input_evidence_hash for result in trace.checker_results}) == 1
