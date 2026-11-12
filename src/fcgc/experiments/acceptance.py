"""Repeatable local release acceptance; predictions finish before annotation evaluation."""

import json
from importlib.resources import files
from pathlib import Path

from fcgc.checking.compliance_checker import freeze_documents, instruction_assets
from fcgc.core.files import read_source
from fcgc.experiments.evaluation import EvaluationConfig, evaluate, write_reports
from fcgc.experiments.quality import validate_dataset
from fcgc.experiments.runner import replay_run, run_experiment, write_json
from fcgc.integrations.synthetic_checker import SyntheticDemoChecker
from fcgc.retrieval.baseline import load_firmware
from fcgc.schemas.models import FetchedDocument


def validate_local_release(dataset_root: Path, output: Path, repetitions: int = 3):
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    dataset_root, output = dataset_root.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Acceptance output must be a fresh directory")
    if output.is_relative_to(dataset_root):
        raise ValueError("Acceptance output must be outside the benchmark dataset")
    _, template, skill = instruction_assets()
    output.mkdir(parents=True, exist_ok=True)
    specification = output / "experiment.toml"
    specification.write_text(
        "\n".join(
            [
                'dataset_id = "fcgc-synthetic-v2"',
                f"dataset_root = {json.dumps(str(dataset_root))}",
                'split = "development"',
                'strategies = ["b0", "p1", "p2", "p3", "r"]',
                f"repetitions = {repetitions}",
                "seed = 2026",
                "shuffle_order = true",
                'output_directory = "experiment"',
                f"expected_skill_version = {json.dumps(skill)}",
                f"expected_prompt_version = {json.dumps(template.splitlines()[0])}",
                "document_top_k = 3",
                "reference_top_k = 8",
                "context_token_budget = 12000",
                "snapshots_approved = true",
                "",
                "[retrieval]",
                'retriever = "benchmark"',
                'checker = "mock"',
                "",
                "[[checkers]]",
                'retriever = "benchmark"',
                'checker = "mock"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    # Runtime runner has no label access. The evaluator below is the separate label boundary.
    matrix = run_experiment(specification)
    run_files = sorted((output / "experiment/runs").glob("*-p3-r01/trace.json"))
    replay_ok = bool(run_files) and replay_run(run_files[0], output / "replay")
    fixture_root = Path(str(files("fcgc").joinpath("fixtures/checking")))
    document = FetchedDocument(
        source_id="pointer",
        title="Synthetic pointer demonstration",
        source_ref="fcgc://demo/pointer.md",
        content=read_source(fixture_root / "pointer.md"),
    )
    demonstrations = {}
    for variant in ("good", "bad"):
        task = freeze_documents(
            load_firmware(fixture_root / f"pointer_{variant}.c", f"pointer-{variant}"), [document]
        )
        result = SyntheticDemoChecker().check(task)
        write_json(output / "deterministic" / f"{variant}-task.json", task)
        write_json(output / "deterministic" / f"{variant}-result.json", result)
        demonstrations[variant] = {
            "status": result.status,
            "decisions": [finding.decision for finding in result.findings],
        }
    quality = validate_dataset(dataset_root)
    write_json(output / "dataset-quality.json", quality)
    evaluation = EvaluationConfig(
        experiment_directories=[str(output / "experiment")],
        dataset_root=str(dataset_root),
        output_directory=str(output / "evaluation"),
        rule_k=18,
    )
    (output / "evaluation.toml").write_text(
        'experiment_directories = ["experiment"]\n'
        f"dataset_root = {json.dumps(str(dataset_root))}\n"
        'output_directory = "evaluation"\nrule_k = 18\n',
        encoding="utf-8",
    )
    metrics = evaluate(evaluation)
    write_reports(metrics, Path(evaluation.output_directory))
    accepted = (
        matrix["failed"] == 0
        and replay_ok
        and demonstrations["good"] == {"status": "evaluated", "decisions": ["compliant"]}
        and demonstrations["bad"] == {"status": "evaluated", "decisions": ["violating"]}
    )
    summary = {
        "accepted": accepted,
        "scope": "synthetic offline development acceptance",
        "runs": matrix["runs"],
        "finished": matrix["finished"],
        "failed": matrix["failed"],
        "incomplete_context_runs": matrix["incomplete"],
        "exact_evidence_replay": replay_ok,
        "benchmark_checker": "mock: not_evaluated; no compliance-accuracy claim",
        "deterministic_demonstration": demonstrations,
        "enterprise_verified": False,
        "ground_truth": "provisional; post-hoc only; no held-out calibration",
        "resource_metrics": "local token estimates and measured local wall-clock timings",
        "evaluation_observations": len(metrics["rows"]),
        "checker_status_counts": metrics["status_counts"],
        "output": str(output),
    }
    write_json(output / "acceptance.json", summary)
    return summary
