"""Five slash-command entry points over existing FCGC services, never shell evaluation."""

import argparse
import shlex
from pathlib import Path

from fcgc.agent.doctor import native_doctor
from fcgc.agent.session import private_write, start_session
from fcgc.checking.compliance_checker import instruction_assets
from fcgc.checking.context_reducer import load_reduction_config
from fcgc.config import load_settings
from fcgc.experiments.benchmark import load_public_benchmark
from fcgc.experiments.evaluation import evaluate, load_evaluation, write_reports
from fcgc.experiments.runner import load_experiment, run_experiment
from fcgc.retrieval.adaptive_retrieval import load_fallback_config
from fcgc.schemas.stage9 import ExperimentConfig


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def parse_command(command: str):
    parts = shlex.split(command)
    if not parts:
        raise ValueError("A slash command is required")
    name = parts[0].removeprefix("/")
    if name not in {"fcg-check", "fcg-rules", "fcg-compare", "fcg-report", "fcg-doctor"}:
        raise ValueError("Unknown FCG slash command")
    parser = Arguments(prog="/" + name, add_help=False)
    if name in {"fcg-check", "fcg-rules"}:
        parser.add_argument("source", type=Path)
        parser.add_argument("--function")
        parser.add_argument("--strategy", choices=["b0", "p1", "p2", "p3"], default="p3")
        parser.add_argument("--top-k", type=int)
        parser.add_argument("--token-budget", type=int, default=12000)
        parser.add_argument("--deadline", type=float, default=600)
    if name in {"fcg-check", "fcg-rules", "fcg-compare", "fcg-doctor"}:
        parser.add_argument("--mode", choices=["local", "wd"], default="local")
    if name in {"fcg-check", "fcg-rules", "fcg-compare"}:
        parser.add_argument("--config", type=Path)
    if name in {"fcg-compare", "fcg-doctor"}:
        parser.add_argument("--dataset-root", type=Path, default=Path("benchmarks/v2"))
    if name == "fcg-compare":
        parser.add_argument("--dataset", default="fcgc-synthetic-v2")
        parser.add_argument("--case")
        parser.add_argument("--repeat", type=int, default=3)
        parser.add_argument("--experiment-config", type=Path)
    if name == "fcg-report":
        parser.add_argument("--experiment", default="latest")
        parser.add_argument("--runs-root", type=Path, default=Path("outputs"))
    return name, parser.parse_args(parts[1:])


def invoke(command: str, output: Path, *, host=None, allow_synthetic_handoff=False):
    name, args = parse_command(command)
    if name in {"fcg-check", "fcg-rules"}:
        settings = load_settings(args.config) if args.config else None
        return start_session(
            args.source,
            output,
            mode=args.mode,
            strategy=args.strategy,
            intent="rules" if name == "fcg-rules" else "check",
            settings=settings,
            function=args.function,
            host=host,
            allow_synthetic_handoff=allow_synthetic_handoff,
            top_k=args.top_k,
            token_budget=args.token_budget,
            elapsed_seconds=args.deadline,
        )
    if output.exists():
        raise ValueError("Agent command output must be a fresh directory")
    if name == "fcg-doctor":
        result = native_doctor(args.dataset_root, host)
        result["requested_mode"] = args.mode
        result["status"] = (
            "complete"
            if result["workflows"]["local"]
            and result["dataset"]["status"] == "ready"
            and result["skills"]["status"] == "ready"
            and (args.mode == "local" or result["workflows"]["wd_bridge"])
            else "error"
        )
        private_write(output / "doctor.json", result)
        return result
    if name == "fcg-compare":
        if args.mode != "local" or host:
            raise ValueError(
                "Live enterprise comparison is not implemented: approved enterprise dataset/"
                "snapshot storage is required. No synthetic substitution."
            )
        return compare(args, output)
    return report_saved(args, output)


def compare(args, output):
    if args.experiment_config:
        if args.case or args.config or args.repeat != 3 or args.dataset != "fcgc-synthetic-v2":
            raise ValueError(
                "Use the experiment configuration or individual comparison options, not both"
            )
        config = load_experiment(args.experiment_config)
        if set(config.strategies) != {"b0", "p1", "p2", "p3"}:
            raise ValueError("FCG comparison requires the unchanged B0/P1/P2/P3 matrix")
        if config.split != "development":
            raise ValueError(
                "Engineer-facing comparison is development-only; "
                "use frozen held-out experiment controls explicitly"
            )
        config = config.model_copy(
            update={"output_directory": str((output / "experiment").resolve())}
        )
    else:
        if args.dataset not in {"fcgc-synthetic-v2", "synthetic_v2"} or args.repeat < 1:
            raise ValueError("Use dataset fcgc-synthetic-v2 and a positive repetition count")
        public = load_public_benchmark(args.dataset_root)
        selected = []
        if args.case:
            case = next(
                (
                    c
                    for c in public.manifest.cases
                    if c.case_id == args.case and c.split == "development"
                ),
                None,
            )
            if case is None:
                raise ValueError(
                    "Case must be an existing development case; held-out calibration is forbidden"
                )
            selected = [
                c.case_id
                for c in public.manifest.cases
                if c.group == case.group and c.split == "development"
            ]
        from fcgc.config import Settings

        settings = (
            load_settings(args.config)
            if args.config
            else Settings(retriever="benchmark", checker="mock")
        )
        _, template, skill = instruction_assets()
        config = ExperimentConfig(
            dataset_id="fcgc-synthetic-v2",
            dataset_root=str(args.dataset_root.resolve()),
            split="development",
            strategies=["b0", "p1", "p2", "p3"],
            case_ids=selected,
            repetitions=args.repeat,
            output_directory=str((output / "experiment").resolve()),
            retrieval=settings,
            checkers=[settings],
            expected_skill_version=skill,
            expected_prompt_version=template.splitlines()[0],
            document_top_k=settings.top_k,
            snapshots_approved=True,
            reduction=load_reduction_config(),
            fallback=load_fallback_config(),
        )
    config_path = output / "experiment.json"
    private_write(config_path, config)
    summary = run_experiment(config_path)
    evaluation = {
        "experiment_directories": [str((output / "experiment").resolve())],
        "dataset_root": config.dataset_root,
        "output_directory": str((output / "evaluation").resolve()),
        "rule_k": 18,
        "allow_provisional_compliance": False,
    }
    evaluation_path = output / "evaluation.json"
    private_write(evaluation_path, evaluation)
    metrics = evaluate(load_evaluation(evaluation_path))
    write_reports(metrics, Path(evaluation["output_directory"]))
    result = {
        "status": "error" if summary["failed"] else "complete",
        "experiment": summary,
        "evaluation_config": str(evaluation_path),
        "labels": metrics["labels"],
        "report": str(Path(evaluation["output_directory"]) / "report.md"),
        "case_selection": "matched variants stay together; development only",
    }
    private_write(output / "result.json", result)
    return result


def report_saved(args, output):
    if args.experiment == "latest":
        candidates = list(args.runs_root.rglob("evaluation.json")) + list(
            args.runs_root.rglob("evaluation.toml")
        )
        if not candidates and args.runs_root == Path("outputs"):
            # Existing experiments keep their locked paths; search the legacy archive only
            # when the new output tree has no saved evaluation configuration.
            candidates = list(Path("runs").rglob("evaluation.json")) + list(
                Path("runs").rglob("evaluation.toml")
            )
        if not candidates:
            raise ValueError(
                "No saved experiment evaluation configuration found under the requested runs root"
            )
        path = max(candidates, key=lambda p: (p.stat().st_mtime, str(p)))
    else:
        path = Path(args.experiment)
        if path.is_dir():
            path = next(
                (
                    path / name
                    for name in ["evaluation.json", "evaluation.toml"]
                    if (path / name).is_file()
                ),
                None,
            )
        if path is None:
            raise ValueError("Saved experiment needs an evaluation JSON/TOML configuration")
    config = load_evaluation(path)
    config.output_directory = str(output.resolve())
    metrics = evaluate(config)
    write_reports(metrics, output)
    result = {
        "status": "complete",
        "retrieval_rerun": False,
        "labels": metrics["labels"],
        "reports": {
            name: str(output / name)
            for name in [
                "report.md",
                "metrics.json",
                "summary.csv",
                "runs.csv",
                "paired.csv",
                "report.html",
            ]
        },
    }
    private_write(output / "result.json", result)
    return result
