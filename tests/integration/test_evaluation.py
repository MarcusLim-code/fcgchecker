import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from fcgc.experiments.calibration_margins import (
    freeze_margins,
    sensitivity_grid,
    validate_frozen_margins,
)
from fcgc.experiments.evaluation import (
    EvaluationConfig,
    canonical_catalog,
    efficiency,
    evaluate,
    verify_fixture,
    write_reports,
)
from fcgc.experiments.metrics import compliance_metrics, retrieval_metrics, set_stability
from fcgc.experiments.runner import load_experiment, run_experiment
from fcgc.experiments.statistics import paired_statistics
from fcgc.schemas.stage9 import ExperimentLock

ROOT = Path(__file__).resolve().parents[2]


def known():
    return json.loads((ROOT / "tests/fixtures/evaluation_known.json").read_text())


def test_manually_verified_retrieval_and_violation_values():
    fixture = known()
    retrieval = fixture["retrieval"]
    measured = retrieval_metrics(
        retrieval["ranked_ids"], retrieval["applicable_ids"], retrieval["k"]
    )
    for key, expected in retrieval["expected"].items():
        assert measured[key] == pytest.approx(expected)
    compliance = fixture["compliance"]
    measured = compliance_metrics(compliance["expected"], compliance["predictions"])
    for key, expected in compliance["expected_metrics"].items():
        assert measured[key] == pytest.approx(expected)
    assert measured["false_negative_ids"] == ["D"]
    assert measured["fn_wrong_judgment"] == ["D"]
    assert verify_fixture(ROOT / "tests/fixtures/evaluation_known.json")["verified"]


def test_provider_token_totals_and_missing_output_are_not_zero():
    trace = SimpleNamespace(
        strategy="b0",
        pipeline=None,
        tool_calls=[],
        task=None,
        end_to_end_ms=10,
        status="failed",
        token_estimation_method="test",
        stage_latencies=[],
    )
    result = SimpleNamespace(
        execution=SimpleNamespace(input_tokens=10, output_tokens=5, duration_ms=1)
    )
    measured = efficiency(trace, result)
    assert measured["provider_reported_total_tokens"] == 15
    assert measured["billed_tokens"] is measured["acu"] is measured["rovo_credits"] is None
    result.execution.output_tokens = None
    assert efficiency(trace, result)["provider_reported_total_tokens"] is None


def test_zero_denominators_duplicates_and_unexecuted_models():
    zero = retrieval_metrics([], [], 5)
    assert zero["precision_at_k"] is zero["recall_at_k"] is zero["f2_at_k"] is None
    assert retrieval_metrics([], ["A"], 5)["f2_at_k"] == 0
    assert compliance_metrics([], [])["f1"] is None
    truth = known()["compliance"]["expected"]
    empty = compliance_metrics(truth, [])
    assert empty["fn"] == 2 and empty["recall"] == empty["f1"] == 0
    mock = compliance_metrics(truth, [], eligible=False)
    assert mock["tp"] is mock["fn"] is mock["recall"] is None
    assert mock["potential_undetected_violation_ids"] == ["A", "D"]
    with pytest.raises(ValueError, match="Duplicate"):
        retrieval_metrics(["A"], ["A", "A"], 1)
    with pytest.raises(ValueError, match="Duplicate"):
        compliance_metrics([truth[0], truth[0]], [])
    with pytest.raises(ValueError, match="Duplicate canonical"):
        canonical_catalog(
            SimpleNamespace(
                rules=SimpleNamespace(
                    rules=[SimpleNamespace(rule_id="A"), SimpleNamespace(rule_id="A")]
                )
            )
        )
    conflicting = compliance_metrics(
        truth,
        [{"rule_id": "A", "decision": "violating"}, {"rule_id": "A", "decision": "compliant"}],
    )
    assert conflicting["conflicting_duplicate_ids"] == ["A"]
    assert conflicting["fn_abstained_or_missing"] == ["A", "D"]


def test_statistics_cluster_variants_and_do_not_count_repetitions():
    result = paired_statistics(
        {"A": 1.0, "B": 3.0, "C": 2.0, "D": 4.0},
        {"A": "pair1", "B": "pair1", "C": "pair2", "D": "pair2"},
        samples=100,
        seed=1,
    )
    assert result["case_count"] == 4
    assert result["independent_cluster_count"] == 2
    assert result["delta_summary"]["mean"] == 2.5
    assert result["sign_flip_p"] == 0.5
    assert result["sign_test_p"] == 0.5
    assert result["ci95_mean_delta"][0] <= 2.5 <= result["ci95_mean_delta"][1]
    assert paired_statistics({"A": 0}, {"A": "one"})["ci95_mean_delta"] is None
    assert set_stability([["A"], ["A", "B"]]) == 0.5
    assert set_stability([[]]) is None


@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    root = tmp_path_factory.mktemp("evaluation")
    source = (ROOT / "research/experiments/stage9_development.toml").read_text()
    source = source.replace("../../benchmarks/v2", str(ROOT / "benchmarks/v2"))
    source = source.replace("../../outputs/experiments/stage9-development", str(root / "runs"))
    source = source.replace(
        "repetitions = 3", 'case_ids=["C001","C002","C003","C004"]\nrepetitions=3'
    )
    path = root / "experiment.toml"
    path.write_text(source)
    assert run_experiment(path)["runs"] == 48
    return root


def eval_config(experiment):
    return EvaluationConfig(
        experiment_directories=[str(experiment / "runs")],
        dataset_root=str(ROOT / "benchmarks/v2"),
        output_directory=str(experiment / "evaluation"),
        bootstrap_samples=100,
    )


def test_saved_trace_evaluation_and_reports_are_separate_from_runtime(experiment, monkeypatch):
    def no_provider(*args, **kwargs):
        pytest.fail("Evaluator invoked a runtime provider")

    monkeypatch.setattr("fcgc.experiments.runner.make_retriever", no_provider)
    monkeypatch.setattr("fcgc.experiments.runner.make_checker", no_provider)
    config = eval_config(experiment)
    report = evaluate(config)
    assert len(report["rows"]) == 48
    assert len(report["case_aggregates"]) == 16
    assert all(case["repetitions_observed"] == 3 for case in report["case_aggregates"])
    assert all(row["compliance"]["fn"] is None for row in report["rows"])
    assert all(row["efficiency"]["rovo_credits"] is None for row in report["rows"])
    paired = next(
        row
        for row in report["paired_comparisons"]
        if row["comparison"] == "b0_vs_p1" and row["metric"] == "fetched_recall"
    )
    assert paired["case_count"] == 4 and paired["independent_cluster_count"] == 2
    assert all(row["retrieval"]["model_supplied"]["returned_at_k"] == 0 for row in report["rows"])
    output = Path(config.output_directory)
    write_reports(report, output)
    assert {
        "metrics.json",
        "runs.csv",
        "summary.csv",
        "paired.csv",
        "report.md",
        "report.html",
    } <= {p.name for p in output.iterdir()}
    assert "provisional" in (output / "report.md").read_text()
    assert "<script" not in (output / "report.html").read_text()


def test_duplicate_observations_are_rejected(experiment):
    config = eval_config(experiment)
    config.experiment_directories *= 2
    with pytest.raises(ValueError, match="Duplicate experimental observation"):
        evaluate(config)


def test_missing_and_failed_runs_do_not_become_perfect_or_zero_accuracy(experiment, tmp_path):
    shutil.copytree(experiment / "runs", tmp_path / "runs")
    missing = tmp_path / "runs/runs/C001-b0-r01/trace.json"
    missing.unlink()
    failed = tmp_path / "runs/runs/C002-p1-r01/trace.json"
    payload = json.loads(failed.read_text())
    payload.update(
        status="failed",
        pipeline=None,
        task=None,
        checker_results=[],
        segmented_documents=[],
        selected_ids=[],
        tool_calls=[],
        incomplete_stages=["retrieval"],
    )
    failed.write_text(json.dumps(payload))
    config = eval_config(tmp_path)
    report = evaluate(config)
    assert len(report["missing_runs"]) == 1
    failed_row = next(row for row in report["rows"] if row["run_id"] == "C002-p1-r01")
    assert failed_row["retrieval"]["candidate"]["recall_at_k"] is None
    assert failed_row["compliance"]["f1"] is None
    assert failed_row["checker_status"] == "missing_result"


def test_frozen_margins_and_preheldout_timing(experiment, tmp_path):
    config = eval_config(experiment)
    report = evaluate(config)
    report_path = tmp_path / "development.json"
    report_path.write_text(json.dumps(report))
    artifact = tmp_path / "frozen.json"
    frozen = freeze_margins(
        report_path, ROOT / "research/experiments/stage10_margins.toml", artifact
    )
    lock = ExperimentLock.model_validate_json((experiment / "runs/lock.json").read_text())
    config.frozen_margins = str(artifact)
    with pytest.raises(ValueError, match="before heldout experiment"):
        validate_frozen_margins(config, [lock])
    future = tmp_path / "future/runs/example"
    future.mkdir(parents=True)
    stamp = datetime.fromisoformat(frozen["created_at_utc"]) + timedelta(hours=1)
    (future / "trace.json").write_text(json.dumps({"timestamp_utc": stamp.isoformat()}))
    config.experiment_directories = [str(tmp_path / "future")]
    assert validate_frozen_margins(config, [lock], report)
    changed = lock.model_copy(deep=True)
    changed.config.document_top_k += 1
    with pytest.raises(ValueError, match="controls differ"):
        validate_frozen_margins(config, [changed])
    raw = json.loads(artifact.read_text())
    raw["created_at_utc"] = datetime.now(UTC).isoformat()
    artifact.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="hash/version"):
        validate_frozen_margins(config, [lock])


def test_heldout_gate_runs_before_opening_labels(experiment, tmp_path, monkeypatch):
    shutil.copytree(experiment / "runs", tmp_path / "runs")
    path = tmp_path / "runs/lock.json"
    raw = json.loads(path.read_text())
    raw["config"]["split"] = "heldout"
    path.write_text(json.dumps(raw))
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        if "ground_truth" in str(path):
            pytest.fail("Opened labels before verifying frozen heldout margins")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    with pytest.raises(ValueError, match="requires acceptance margins"):
        evaluate(eval_config(tmp_path))


def test_sensitivity_configs_are_development_only_and_loadable(tmp_path):
    files = sensitivity_grid(
        ROOT / "research/experiments/stage9_development.toml",
        tmp_path / "grid",
        [1, 3],
        [0.25, 0.5],
    )
    assert len(files) == 4
    configs = [load_experiment(Path(path)) for path in files]
    assert {config.document_top_k for config in configs} == {1, 3}
    assert {config.fallback.max_duplicate_fraction for config in configs} == {0.25, 0.5}
    base = (
        (ROOT / "research/experiments/stage9_development.toml")
        .read_text()
        .replace('split = "development"', 'split = "heldout"')
    )
    path = tmp_path / "heldout.toml"
    path.write_text(base)
    with pytest.raises(ValueError, match="restricted to development"):
        sensitivity_grid(path, tmp_path / "bad", [1], [0.5])
