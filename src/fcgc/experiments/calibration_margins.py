"""Development-only sensitivity grids and pre-heldout acceptance-margin freezing."""

import argparse
import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field, model_validator

from fcgc.experiments.snapshots import digest
from fcgc.schemas.models import Contract


class AcceptanceMargin(Contract):
    comparison: str
    metric: str
    lower: float | None = None
    upper: float | None = None

    @model_validator(mode="after")
    def bounds(self):
        if self.lower is None and self.upper is None:
            raise ValueError("A calibrated margin needs at least one bound")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("Margin bounds are reversed")
        return self


class MarginConfig(Contract):
    rule_k: int = Field(ge=1)
    rationale: str = Field(min_length=1)
    margins: list[AcceptanceMargin] = Field(min_length=1)


def freeze_margins(report_path, margins_path, output):
    from fcgc.experiments.evaluation import METRICS, PAIRS

    report = json.loads(report_path.read_text())
    if report["split"] != "development":
        raise ValueError("Acceptance margins can only be calibrated on development data")
    config = MarginConfig.model_validate(tomllib.loads(margins_path.read_text()))
    if config.rule_k != report["configuration"]["rule_k"]:
        raise ValueError("Margin rule K differs from development evaluation")
    for margin in config.margins:
        if margin.metric not in METRICS or margin.comparison not in {
            f"{a}_vs_{b}" for a, b, _ in PAIRS
        }:
            raise ValueError("Unknown margin metric or paired contrast")
    artifact = {
        "version": "frozen-margins-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_development_report_hash": digest(report),
        "control_signatures": report["control_signatures"],
        "configuration": config.model_dump(mode="json"),
        "note": "User-configured development margins; never fitted from heldout labels.",
    }
    artifact["content_hash"] = digest(artifact)
    if output.exists():
        raise ValueError("Frozen margin artifacts cannot be overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n")
    return artifact


def validate_frozen_margins(config, locks, report=None):
    from fcgc.experiments.evaluation import control_signature

    if not config.frozen_margins:
        raise ValueError(
            "Heldout evaluation requires acceptance margins frozen before heldout execution"
        )
    artifact = json.loads(Path(config.frozen_margins).read_text())
    expected = artifact.pop("content_hash")
    if digest(artifact) != expected or artifact["version"] != "frozen-margins-v1":
        raise ValueError("Frozen margin artifact hash/version mismatch")
    margins = MarginConfig.model_validate(artifact["configuration"])
    if margins.rule_k != config.rule_k:
        raise ValueError("Heldout rule K differs from frozen calibration")
    frozen_time = datetime.fromisoformat(artifact["created_at_utc"])
    if frozen_time.tzinfo is None:
        raise ValueError("Margin timestamp needs an explicit timezone")
    for lock in locks:
        if control_signature(lock) not in artifact["control_signatures"]:
            raise ValueError("Heldout controls differ from development calibration")
    for directory in config.experiment_directories:
        for path in (Path(directory) / "runs").glob("*/trace.json"):
            started = datetime.fromisoformat(json.loads(path.read_text())["timestamp_utc"])
            if started <= frozen_time:
                raise ValueError("Margins must be frozen before heldout experiment execution")
    if report is None:
        return []
    results = []
    for comparison in report["paired_comparisons"]:
        for margin in margins.margins:
            if (comparison["comparison"], comparison["metric"]) != (
                margin.comparison,
                margin.metric,
            ):
                continue
            ci = comparison["ci95_mean_delta"]
            status = "not_assessed"
            if ci is not None:
                lower, upper = margin.lower, margin.upper
                if (lower is None or ci[0] >= lower) and (upper is None or ci[1] <= upper):
                    status = "within_frozen_margin"
                elif (lower is not None and ci[1] < lower) or (upper is not None and ci[0] > upper):
                    status = "outside_frozen_margin"
                else:
                    status = "inconclusive"
            results.append(
                {
                    "panel": comparison["panel"],
                    "checker_index": comparison["checker_index"],
                    **margin.model_dump(),
                    "ci95": ci,
                    "status": status,
                    "artifact_hash": expected,
                }
            )
    return results


def write_toml(data):
    """Serialize the validated experiment's scalar/table/array-of-table subset."""
    lines = []

    def scalar(value):
        return json.dumps(value)

    def table(values, path=(), header=None):
        if header:
            lines.append(header)
        for key, value in values.items():
            if (
                value is None
                or isinstance(value, dict)
                or (isinstance(value, list) and value and isinstance(value[0], dict))
            ):
                continue
            lines.append(f"{key} = {scalar(value)}")
        for key, value in values.items():
            name = ".".join((*path, key))
            if isinstance(value, dict):
                lines.append("")
                table(value, (*path, key), f"[{name}]")
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                for item in value:
                    lines.append("")
                    table(item, (*path, key), f"[[{name}]]")

    table(data)
    return "\n".join(lines) + "\n"


def sensitivity_grid(base, output, top_ks, thresholds):
    from fcgc.experiments.runner import load_experiment

    config = load_experiment(base)
    if config.split != "development":
        raise ValueError("Sensitivity analysis is restricted to development data")
    output.mkdir(parents=True, exist_ok=True)
    paths, directories = [], []
    for k in top_ks:
        for threshold in thresholds:
            if k < 1 or not 0 <= threshold <= 1:
                raise ValueError("Invalid Top-K or duplicate-threshold sensitivity value")
            name = f"k{k}-duplicate{threshold:g}"
            values = config.model_dump(mode="json")
            values["document_top_k"] = k
            values["output_directory"] = str((output / "runs" / name).resolve())
            values["fallback"]["top_k"] = k
            values["fallback"]["max_fetch_calls"] = max(k, values["fallback"]["max_fetch_calls"])
            values["fallback"]["max_candidate_sources"] = max(
                k, values["fallback"]["max_candidate_sources"]
            )
            values["fallback"]["max_duplicate_fraction"] = threshold
            path = output / f"{name}.toml"
            if path.exists():
                raise ValueError("Sensitivity config already exists; use a fresh directory")
            path.write_text(write_toml(values))
            paths.append(str(path))
            directories.append(values["output_directory"])
    evaluation = {
        "experiment_directories": directories,
        "dataset_root": config.dataset_root,
        "output_directory": str((output / "evaluation").resolve()),
        "rule_k": 18,
    }
    (output / "evaluation.toml").write_text(write_toml(evaluation))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--development-report", type=Path, required=True)
    freeze.add_argument("--margins", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    grid = sub.add_parser("sensitivity")
    grid.add_argument("--base", type=Path, required=True)
    grid.add_argument("--output", type=Path, required=True)
    grid.add_argument("--top-k", type=int, nargs="+", default=[1, 3])
    grid.add_argument("--duplicate-threshold", type=float, nargs="+", default=[0.25, 0.5])
    args = parser.parse_args()
    try:
        result = (
            freeze_margins(args.development_report, args.margins, args.output)
            if args.command == "freeze"
            else sensitivity_grid(args.base, args.output, args.top_k, args.duplicate_threshold)
        )
        print(json.dumps(result))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
