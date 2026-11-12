"""Command-line entry point for offline B0 and P1 retrieval."""

import hashlib
import json
from importlib.metadata import version as distribution_version
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer

from fcgc import __version__
from fcgc.agent.cli import app as agent_app
from fcgc.checking.compliance_checker import (
    compare_checkers,
    freeze_documents,
    freeze_packed_audit,
    instruction_assets,
)
from fcgc.checking.context_reducer import RuleContextReducer, load_reduction_config
from fcgc.checking.feature_extractor import extract_features
from fcgc.checking.reduced_context import run_p2
from fcgc.checking.rule_extractor import extract_rule_evidence
from fcgc.config import Settings, load_settings, make_checker, make_retriever
from fcgc.core.files import protect_inputs, read_source
from fcgc.experiments.run_log import append_run_log
from fcgc.experiments.runner import code_hash, perform_run, write_json
from fcgc.experiments.snapshots import RecordingRetriever
from fcgc.retrieval.adaptive_retrieval import load_fallback_config, run_p3
from fcgc.retrieval.baseline import load_firmware, retrieve_b0
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.schemas.checking import FrozenCheckingTask
from fcgc.schemas.models import FetchedDocument, RetrievalOutput
from fcgc.schemas.stage3 import P1Run
from fcgc.schemas.stage9 import ArtifactLock, PipelineConfig

app = typer.Typer(help="Firmware Coding Guidelines Checker (offline research prototype).")
app.add_typer(agent_app, name="agent")


def _settings(path: Path | None) -> Settings:
    try:
        return load_settings(path)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--config") from exc


def _firmware_path(case: str, source: Path | None) -> Path:
    if source is not None:
        return source
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    if not case or any(character not in allowed for character in case):
        raise typer.BadParameter("Case ID must use letters, digits, _ or -")
    resource = files("fcgc").joinpath("fixtures", "cases", f"{case}.c")
    if resource.is_file():
        return Path(str(resource))
    benchmark = files("fcgc").joinpath("fixtures", "benchmark_cases", f"{case}.c")
    if benchmark.is_file():
        return Path(str(benchmark))
    raise typer.BadParameter(f"Unknown bundled case: {case}")


def _run(
    case: str,
    source: Path | None,
    config: Path | None,
    log: Path | None,
    strategy: str,
    top_k: int | None,
) -> RetrievalOutput | P1Run:
    settings = _settings(config)
    if top_k is not None and top_k < 1:
        raise typer.BadParameter("top_k must be at least 1", param_hint="--top-k")
    document_top_k = top_k if top_k is not None else settings.top_k
    try:
        artifact_path = _firmware_path(case, source)
        protect_inputs(log, [artifact_path, config])
        firmware = load_firmware(artifact_path, case)
        if strategy == "b0":
            output: RetrievalOutput | P1Run = retrieve_b0(
                firmware, make_retriever(settings), document_top_k
            )
            retrieval = output
        else:
            output = retrieve_p1(firmware, make_retriever(settings), document_top_k)
            retrieval = output.retrieval
        if log is not None:
            append_run_log(log, retrieval, output.plan if isinstance(output, P1Run) else None)
        return output
    except (OSError, ValueError, KeyError, RuntimeError, NotImplementedError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def doctor(
    config: Annotated[
        Path | None, typer.Option(help="Settings TOML path.", envvar="FCGC_CONFIG")
    ] = None,
) -> None:
    """Show local readiness and configured provider capabilities."""
    settings = _settings(config)
    bundled_cases = ["sensor_poll", "register_access"]
    if settings.retriever in {"benchmark", "replay"}:
        directory = files("fcgc").joinpath("fixtures", "benchmark_cases")
        bundled_cases = sorted(item.name.removesuffix(".c") for item in directory.iterdir())
    replay_ready = settings.retriever != "replay" or (
        settings.replay_path is not None and settings.replay_path.is_file()
    )
    report = {
        "version": __version__,
        "retriever": settings.retriever,
        "retriever_implemented": settings.retriever in {"local", "benchmark", "replay"},
        "checker": settings.checker,
        "checker_implemented": settings.checker
        in {"placeholder", "mock", "synthetic_demo", "ollama"},
        "compliance_evaluation_available": settings.checker == "synthetic_demo",
        "checker_scope": (
            "single-pointer-store synthetic subset"
            if settings.checker == "synthetic_demo"
            else "optional Ollama; availability unverified"
            if settings.checker == "ollama"
            else "not_evaluated"
        ),
        "bundled_cases": bundled_cases,
        "offline_ready": settings.retriever in {"local", "benchmark", "replay"}
        and replay_ready
        and settings.checker in {"placeholder", "mock", "synthetic_demo"},
    }
    try:
        _, template, skill = instruction_assets()
        report["skill_version"] = skill
        report["prompt_version"] = template.splitlines()[0]
        if report["retriever_implemented"]:
            provider = make_retriever(settings)
            probe = provider.search("firmware coding guidelines C source", settings.top_k)
            report["local_search_validated"] = len(probe.hits)
            for hit in probe.hits:
                provider.fetch(hit.source_id)
        if settings.checker != "ollama":
            make_checker(settings)
    except (OSError, ValueError, KeyError, NotImplementedError) as exc:
        report["offline_ready"] = False
        report["diagnostic_error"] = str(exc)
    typer.echo(json.dumps(report, indent=2))
    if not report["offline_ready"]:
        raise typer.Exit(code=1)


@app.command()
def retrieve(
    case: Annotated[str, typer.Option(help="Bundled case ID, or label for --source.")],
    strategy: Annotated[str, typer.Option(help="Retrieval strategy.")] = "b0",
    source: Annotated[Path | None, typer.Option(help="Path to a C firmware file.")] = None,
    config: Annotated[
        Path | None, typer.Option(help="Settings TOML path.", envvar="FCGC_CONFIG")
    ] = None,
    log: Annotated[Path | None, typer.Option(help="Append JSONL run summary.")] = None,
    top_k: Annotated[int | None, typer.Option(help="Maximum fetched documents.")] = None,
    output: Annotated[Path | None, typer.Option(help="Full typed retrieval output JSON.")] = None,
) -> None:
    """Retrieve guideline evidence for a C firmware file."""
    if strategy not in {"b0", "p1"}:
        raise typer.BadParameter("Strategy must be b0 or p1", param_hint="--strategy")
    try:
        protect_inputs(output, [_firmware_path(case, source), config, log])
        result = _run(case, source, config, log, strategy, top_k)
        if output:
            write_json(output, result)
        typer.echo(result.model_dump_json(indent=2))
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def reduce(
    case: Annotated[str, typer.Option(help="Bundled case ID, or label for --source.")],
    strategy: Annotated[str, typer.Option(help="Context strategy.")] = "p2",
    source: Annotated[Path | None, typer.Option(help="Path to a C firmware file.")] = None,
    config: Annotated[
        Path | None, typer.Option(help="Retrieval settings TOML path.", envvar="FCGC_CONFIG")
    ] = None,
    reduction_config: Annotated[
        Path | None, typer.Option(help="P2 reduction settings TOML path.")
    ] = None,
    fallback_config: Annotated[
        Path | None, typer.Option(help="P3 gate and fallback settings TOML path.")
    ] = None,
    top_k: Annotated[int | None, typer.Option(help="Maximum fetched documents.")] = None,
    token_budget: Annotated[int | None, typer.Option(help="Maximum packed input tokens.")] = None,
    output: Annotated[Path | None, typer.Option(help="Write full audit JSON to this path.")] = None,
) -> None:
    """Run P1 retrieval and P2 source-preserving context reduction offline."""
    if strategy not in {"p2", "p3"}:
        raise typer.BadParameter("Context strategy must be p2 or p3", param_hint="--strategy")
    settings = _settings(config)
    try:
        artifact_path = _firmware_path(case, source)
        protect_inputs(output, [artifact_path, config, reduction_config, fallback_config])
        firmware = load_firmware(artifact_path, case)
        reducer = RuleContextReducer(load_reduction_config(reduction_config))
        if strategy == "p3":
            adaptive = load_fallback_config(fallback_config)
            overrides = {}
            if top_k is not None:
                overrides["top_k"] = top_k
            if token_budget is not None:
                overrides["context_token_budget"] = token_budget
            adaptive = type(adaptive).model_validate({**adaptive.model_dump(), **overrides})
            result = run_p3(firmware, make_retriever(settings), config=adaptive, reducer=reducer)
        else:
            result = run_p2(
                firmware,
                make_retriever(settings),
                top_k=top_k if top_k is not None else settings.top_k,
                reducer=reducer,
                token_budget=token_budget,
            )
        payload = result.model_dump_json(indent=2)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        typer.echo(payload)
    except (OSError, KeyError, PermissionError, ValueError, NotImplementedError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def extract_rules(
    source_id: Annotated[
        str | None, typer.Option(help="Provider source ID, or ID for --document.")
    ] = None,
    document: Annotated[
        Path | None, typer.Option(help="Local Markdown guideline document.")
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Settings TOML path.", envvar="FCGC_CONFIG")
    ] = None,
    document_version: Annotated[
        str | None, typer.Option(help="Optional version of a local document.")
    ] = None,
    output: Annotated[Path | None, typer.Option(help="Traceable rule evidence JSON.")] = None,
) -> None:
    """Normalize and segment a fetched or local synthetic guideline document."""
    if document is None and source_id is None:
        raise typer.BadParameter("Provide --source-id or --document")
    try:
        protect_inputs(output, [document, config])
        if document is not None:
            content = read_source(document)
            fetched = FetchedDocument(
                source_id=source_id or document.stem,
                title=content.splitlines()[0].removeprefix("# "),
                source_ref=document.resolve().as_uri(),
                content=content,
                document_version=document_version,
            )
        else:
            fetched = make_retriever(_settings(config)).fetch(source_id)
        extraction = extract_rule_evidence(fetched)
        if output:
            write_json(output, extraction)
        typer.echo(extraction.model_dump_json(indent=2))
    except (OSError, KeyError, PermissionError, ValueError, NotImplementedError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def freeze_task(
    output: Annotated[Path, typer.Option(help="Frozen checking-task JSON path.")],
    source: Annotated[Path | None, typer.Option(help="C artifact.")] = None,
    guideline: Annotated[
        list[Path] | None, typer.Option(help="Local guideline, repeatable.")
    ] = None,
    packed_audit: Annotated[Path | None, typer.Option(help="P2/P3 audit JSON.")] = None,
    case: Annotated[str, typer.Option()] = "local-check",
) -> None:
    """Freeze code and source-backed evidence independently from checker selection."""
    try:
        protect_inputs(output, [source, packed_audit, *(guideline or [])])
        if packed_audit:
            if source or guideline:
                raise ValueError("Use either --packed-audit or --source with --guideline")
            task = freeze_packed_audit(packed_audit.read_text(encoding="utf-8"))
        else:
            if source is None or not guideline:
                raise ValueError("Supply --source and at least one --guideline")
            documents = [
                FetchedDocument(
                    source_id=path.stem,
                    title=path.stem,
                    source_ref=path.resolve().as_uri(),
                    content=read_source(path),
                )
                for path in guideline
            ]
            task = freeze_documents(load_firmware(source, case), documents)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(task.model_dump_json(indent=2) + "\n", encoding="utf-8")
        typer.echo(json.dumps({"task": str(output), "input_evidence_hash": task.evidence_hash()}))
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def check_task(
    task: Annotated[Path, typer.Option(help="Frozen checking-task JSON.")],
    checker_config: Annotated[
        list[Path], typer.Option(help="Checker settings, repeat for comparison.")
    ],
    output: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Run the same frozen task through one or more explicitly configured checkers."""
    try:
        protect_inputs(output, [task, *checker_config])
        frozen = FrozenCheckingTask.model_validate_json(task.read_text(encoding="utf-8"))
        checkers = [make_checker(_settings(path)) for path in checker_config]
        results = compare_checkers(frozen, checkers)
        payload = json.dumps([result.model_dump(mode="json") for result in results], indent=2)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload + "\n", encoding="utf-8")
        typer.echo(payload)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def check(
    case: Annotated[str, typer.Option(help="Bundled case ID, or label for --source.")],
    strategy: Annotated[str, typer.Option(help="Retrieval strategy.")] = "b0",
    source: Annotated[Path | None, typer.Option(help="Path to a C firmware file.")] = None,
    config: Annotated[
        Path | None, typer.Option(help="Settings TOML path.", envvar="FCGC_CONFIG")
    ] = None,
    log: Annotated[Path | None, typer.Option(help="Append JSONL run summary.")] = None,
    top_k: Annotated[int | None, typer.Option(help="Maximum fetched documents.")] = None,
    token_budget: Annotated[int, typer.Option(min=1)] = 12000,
    output: Annotated[Path | None, typer.Option(help="Complete structured pipeline trace.")] = None,
) -> None:
    """Execute the shared B0/P1/P2/P3 pipeline and selected checker for a C file."""
    if strategy not in {"b0", "p1", "p2", "p3", "r"}:
        raise typer.BadParameter("Strategy must be b0, p1, p2, p3 or r")
    try:
        settings = _settings(config)
        artifact_path = _firmware_path(case, source)
        protect_inputs(output, [artifact_path, config, log])
        protect_inputs(log, [artifact_path, config])
        firmware = load_firmware(artifact_path, case)
        skill, template, skill_version = instruction_assets()
        pipeline_config = PipelineConfig(
            retrieval=settings,
            checkers=[settings],
            expected_skill_version=skill_version,
            expected_prompt_version=template.splitlines()[0],
            document_top_k=top_k if top_k is not None else settings.top_k,
            context_token_budget=token_budget,
            reduction=load_reduction_config(),
            fallback=load_fallback_config(),
        )
        lock = ArtifactLock(
            config=pipeline_config,
            code_version=__version__,
            code_hash=code_hash(),
            instruction_hash=hashlib.sha256((skill + template).encode()).hexdigest(),
        )
        trace = perform_run(
            lock,
            firmware,
            strategy,
            1,
            f"{case}-{strategy}",
            RecordingRetriever(make_retriever(settings)),
        )
        if strategy in {"b0", "p1"} and trace.checker_results:
            retrieval = trace.pipeline if strategy == "b0" else trace.pipeline.retrieval
            trace.checker_results[0].retrieval = retrieval
        if output:
            write_json(output, trace)
        if log:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as stream:
                stream.write(trace.model_dump_json() + "\n")
        if trace.status == "failed" or not trace.checker_results:
            typer.echo(trace.model_dump_json(indent=2))
            raise typer.Exit(code=1)
        typer.echo(trace.checker_results[0].model_dump_json(indent=2))
    except (OSError, ValueError, KeyError, RuntimeError, NotImplementedError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def features(
    source: Annotated[Path, typer.Option(help="C firmware file.")],
    case: Annotated[str, typer.Option()] = "local-artifact",
    output: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Extract observed firmware features and bounded semantic inferences."""
    try:
        protect_inputs(output, [source])
        report = extract_features(load_firmware(source, case))
        if output:
            write_json(output, report)
        typer.echo(report.model_dump_json(indent=2))
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def info() -> None:
    """Display installed package, provider and canonical instruction versions."""
    _, template, skill_version = instruction_assets()
    typer.echo(
        json.dumps(
            {
                "fcgc": __version__,
                "skill": skill_version,
                "prompt": template.splitlines()[0],
                "dependencies": {
                    name: distribution_version(name)
                    for name in ("pydantic", "typer", "tree-sitter", "tree-sitter-c")
                },
                "retrieval": {
                    "local": "legacy smoke fixtures",
                    "benchmark": "synthetic lexical",
                    "replay": "recorded fixtures",
                    "atlassian_mcp": "unimplemented",
                    "agent_mcp": "agent-mediated JSON handoff; no direct Python MCP access",
                },
                "checkers": {
                    "placeholder": "not_evaluated",
                    "mock": "not_evaluated",
                    "synthetic_demo": "bounded single-pointer-store grammar",
                    "ollama": "optional; explicit network opt-in; unverified availability",
                    "devin": "contract only; not_evaluated",
                    "devin_agent": "agent judgment ingestion; live unverified",
                },
            },
            indent=2,
        )
    )


@app.command()
def experiment(config: Annotated[Path, typer.Option(help="Experiment TOML.")]) -> None:
    """Run a locked dataset/configuration matrix; labels are not runtime inputs."""
    from fcgc.experiments.runner import run_experiment

    try:
        summary = run_experiment(config)
        typer.echo(json.dumps(summary, indent=2))
        if summary["failed"]:
            raise typer.Exit(code=1)
    except (OSError, ValueError, KeyError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def replay(
    run: Annotated[Path, typer.Option(help="Saved experiment runs/<id>/trace.json.")],
    output: Annotated[Path, typer.Option(help="Fresh replay directory.")],
) -> None:
    """Replay approved content snapshots without live retrieval."""
    from fcgc.experiments.runner import replay_run

    try:
        consistent = replay_run(run, output)
        trace = json.loads((output / "trace.json").read_text(encoding="utf-8"))
        typer.echo(
            json.dumps(
                {
                    "exact_evidence_replay": consistent,
                    "output": str(output),
                    "run_status": trace["status"],
                    "errors": trace["errors"],
                    "checker_statuses": [result["status"] for result in trace["checker_results"]],
                }
            )
        )
        if not consistent or trace["status"] == "failed":
            raise typer.Exit(code=1)
    except (OSError, ValueError, KeyError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def report(config: Annotated[Path, typer.Option(help="Post-hoc evaluation TOML.")]) -> None:
    """Generate JSON, CSV, Markdown and offline HTML from saved traces."""
    from fcgc.experiments.evaluation import evaluate, load_evaluation, write_reports

    try:
        settings = load_evaluation(config)
        for name in (
            "metrics.json",
            "summary.csv",
            "runs.csv",
            "paired.csv",
            "report.md",
            "report.html",
        ):
            protect_inputs(Path(settings.output_directory) / name, [config])
        result = evaluate(settings)
        write_reports(result, Path(settings.output_directory))
        typer.echo(
            json.dumps(
                {
                    "observations": len(result["rows"]),
                    "output": settings.output_directory,
                    "labels": result["labels"],
                }
            )
        )
    except (OSError, ValueError, KeyError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def validate_local(
    dataset_root: Annotated[Path, typer.Option(help="Source checkout benchmarks/v2.")],
    output: Annotated[Path, typer.Option(help="Fresh acceptance directory.")],
    repetitions: Annotated[int, typer.Option(min=1)] = 3,
) -> None:
    """Run development B0/P1/P2/P3/R, replay, bounded real checking and evaluation."""
    from fcgc.experiments.acceptance import validate_local_release

    try:
        result = validate_local_release(dataset_root, output, repetitions)
        typer.echo(json.dumps(result, indent=2))
        if not result["accepted"]:
            raise typer.Exit(code=1)
    except (OSError, ValueError, KeyError) as exc:
        raise typer.BadParameter(str(exc)) from exc


if __name__ == "__main__":
    app()
