"""Locked experiments, content-bearing retrieval replay, and frozen checker tasks."""

import argparse
import hashlib
import json
import random
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import fcgc
from fcgc.checking.compliance_checker import (
    freeze_documents,
    freeze_packed_audit,
    instruction_assets,
    render_checking_prompt,
)
from fcgc.checking.context_packer import estimate_tokens
from fcgc.checking.context_reducer import RuleContextReducer, load_reduction_config
from fcgc.checking.feature_extractor import extract_features
from fcgc.checking.reduced_context import run_p2
from fcgc.checking.rule_extractor import extract_documents
from fcgc.config import make_checker, make_retriever
from fcgc.core.files import read_source
from fcgc.experiments.benchmark import load_public_benchmark
from fcgc.experiments.snapshots import (
    OrderedReplayRetriever,
    RecordingRetriever,
    RetrievalSnapshot,
    digest,
)
from fcgc.retrieval.adaptive_retrieval import load_fallback_config, run_p3
from fcgc.retrieval.baseline import retrieve_b0
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.retrieval.search_pipeline import execute_retrieval
from fcgc.schemas.checking import FrozenCheckingTask
from fcgc.schemas.models import FirmwareInput, RetrievalRequest
from fcgc.schemas.stage9 import ExperimentConfig, ExperimentLock, RunTrace, StageError, StageLatency


def code_hash():
    root = Path(fcgc.__file__).parent
    return digest(
        {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and path.suffix in {".py", ".toml", ".json"}
            and "fixtures" not in path.parts
        }
    )


def write_json(path, model):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_experiment(path: Path):
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    raw.setdefault("reduction", load_reduction_config().model_dump())
    raw.setdefault("fallback", load_fallback_config().model_dump())
    config = ExperimentConfig.model_validate(raw)
    config.dataset_root = str((path.parent / config.dataset_root).resolve())
    config.output_directory = str((path.parent / config.output_directory).resolve())
    if config.retrieval.replay_path and not config.retrieval.replay_path.is_absolute():
        config.retrieval.replay_path = (path.parent / config.retrieval.replay_path).resolve()
    if len(set(config.strategies)) != len(config.strategies):
        raise ValueError("Duplicate strategies in experiment matrix")
    if (
        config.fallback.max_search_calls < 1
        or config.fallback.max_fetch_calls < config.document_top_k
    ):
        raise ValueError("P3 total fetch budget must accommodate initial document Top-K")
    return config


def make_lock(config):
    public = load_public_benchmark(Path(config.dataset_root))
    cases = [case for case in public.manifest.cases if case.split == config.split]
    if config.case_ids:
        chosen = set(config.case_ids)
        if not chosen <= {case.case_id for case in cases}:
            raise ValueError(
                "Case selection crosses the configured split or contains unknown cases"
            )
        groups = {case.group for case in cases if case.case_id in chosen}
        if any(case.case_id not in chosen and case.group in groups for case in cases):
            raise ValueError("Related matched variants must be selected together")
        cases = [case for case in cases if case.case_id in chosen]
    if not cases:
        raise ValueError("Experiment selected no cases")
    skill, prompt, version = instruction_assets()
    if (
        version != config.expected_skill_version
        or prompt.splitlines()[0] != config.expected_prompt_version
    ):
        raise ValueError("Configured skill/prompt version does not match installed instructions")
    if not config.snapshots_approved:
        raise ValueError("Explicitly approve synthetic retrieval snapshots in experiment config")
    if config.retrieval.retriever not in {"local", "benchmark", "replay"}:
        raise ValueError("Production-source capture requires a future approval/storage adapter")
    corpus = {
        doc.source_id: public.document_source(doc.source_id) for doc in public.manifest.documents
    }
    if config.retrieval.retriever == "benchmark":
        installed_corpus = {
            path.stem: read_source(path)
            for path in (Path(fcgc.__file__).parent / "fixtures/benchmark_guidelines").glob("*.md")
        }
        if installed_corpus != corpus:
            raise ValueError("Benchmark manifest corpus differs from the retrieval provider corpus")
    if config.retrieval.retriever == "local":
        corpus = {
            path.name: path.read_text()
            for path in (Path(fcgc.__file__).parent / "fixtures/guidelines").glob("*.md")
        }
    if config.retrieval.retriever == "replay":
        if config.retrieval.replay_path is None:
            raise ValueError("Replay provider requires its snapshot")
        corpus = {"provider_snapshot": config.retrieval.replay_path.read_text()}
    lock = ExperimentLock(
        config=config,
        code_version=fcgc.__version__,
        code_hash=code_hash(),
        instruction_hash=hashlib.sha256((skill + prompt).encode()).hexdigest(),
        dataset_version=public.manifest.dataset_version,
        annotation_version=public.manifest.annotation_version,
        manifest_hash=digest(public.manifest.model_dump(mode="json")),
        corpus_hash=digest(corpus),
        case_hashes={
            case.case_id: hashlib.sha256(public.case_source(case.case_id).encode()).hexdigest()
            for case in cases
        },
        controls_not_verified=[
            "Ground-truth labels are never loaded; only annotation version is recorded.",
            "Remote model weights and session isolation are not guaranteed by shared prompts.",
            "P3 has explicitly larger retrieval-call budgets; R has a larger document budget.",
            "Local fixture/replay calls are not MCP traffic; model calls are reported separately.",
            "P3 soft elapsed limits may change call sequences on a slower machine.",
        ],
    )
    return lock, public, cases


def execute_strategy(strategy, firmware, retriever, config):
    if strategy == "b0":
        return retrieve_b0(firmware, retriever, config.document_top_k)
    if strategy == "p1":
        return retrieve_p1(firmware, retriever, config.document_top_k)
    reducer = RuleContextReducer(config.reduction.model_copy(deep=True))
    if strategy == "p2":
        return run_p2(
            firmware,
            retriever,
            top_k=config.document_top_k,
            reducer=reducer,
            token_budget=config.context_token_budget,
        )
    if strategy == "p3":
        adaptive = config.fallback.model_copy(
            update={
                "top_k": config.document_top_k,
                "context_token_budget": config.context_token_budget,
            }
        )
        return run_p3(firmware, retriever, config=adaptive, reducer=reducer)
    return execute_retrieval(
        RetrievalRequest(
            firmware=firmware,
            strategy="b0",
            query="synthetic firmware coding guidelines",
            query_template_version="broad-reference-v1",
            top_k=config.reference_top_k,
        ),
        retriever,
    )


def pipeline_documents(strategy, pipeline):
    if strategy == "p3":
        return pipeline.documents
    if strategy == "p2":
        return pipeline.p1.retrieval.documents
    if strategy == "p1":
        return pipeline.retrieval.documents
    return pipeline.documents


def prepare_task(strategy, pipeline, firmware, documents):
    if strategy in {"b0", "p1", "r"}:
        return freeze_documents(firmware, documents).model_copy(
            update={"full_document_context": True}
        )
    if pipeline.checker_request is not None:
        return freeze_packed_audit(pipeline.model_dump_json())
    return FrozenCheckingTask(
        firmware=firmware,
        documents=documents,
        rules=[
            r
            for r in pipeline.selection.candidate_rules
            if r.evidence_id in pipeline.selection.selected_ids
        ],
        context_status="incomplete_context",
        warnings=["Context budget exceeded; no checker execution."],
    )


def execute_checkers(trace, config):
    """Only called after runtime evidence (or exact replay) has been validated."""
    if trace.task is None:
        return
    for index, settings in enumerate(config.checkers):
        t = perf_counter()
        result = make_checker(settings.model_copy(deep=True)).check(
            FrozenCheckingTask.model_validate_json(trace.task.model_dump_json())
        )
        trace.checker_results.append(result)
        trace.stage_latencies.append(
            StageLatency(stage=f"checker_{index}", duration_ms=(perf_counter() - t) * 1000)
        )
        if result.status in {"error", "unavailable"}:
            trace.errors.append(
                StageError(
                    stage="checker",
                    error_type=str(result.status),
                    message=result.execution.error or result.reason,
                )
            )
            trace.incomplete_stages.append(f"checker_{index}")


def perform_run(
    lock,
    firmware,
    strategy,
    repetition,
    run_id,
    retriever,
    replay_of=None,
    *,
    checkers_enabled=True,
    task_transform=None,
):
    started = perf_counter()
    config = lock.config
    trace = RunTrace(
        run_id=run_id,
        timestamp_utc=datetime.now(UTC).isoformat(),
        lock_hash=digest(lock.model_dump(mode="json")),
        strategy=strategy,
        repetition=repetition,
        seed=config.seed,
        firmware=firmware,
        traffic_kind="recorded_replay" if replay_of else "local_fixture",
        replay_of=replay_of,
    )
    stage = "retrieval_and_processing"
    try:
        t = perf_counter()
        pipeline = execute_strategy(strategy, firmware, retriever, config)
        trace.pipeline = pipeline
        trace.stage_latencies.append(
            StageLatency(stage=stage, duration_ms=(perf_counter() - t) * 1000)
        )
        documents = pipeline_documents(strategy, pipeline)
        stage = "segmentation_and_freezing"
        t = perf_counter()
        trace.segmented_documents = extract_documents(documents)
        trace.task = prepare_task(strategy, pipeline, firmware, documents)
        if task_transform is not None:
            trace.task = FrozenCheckingTask.model_validate(task_transform(trace.task))
        trace.selected_ids = [r.evidence_id for r in trace.task.rules]
        trace.selection_policy = (
            "all_candidates_no_reduction" if strategy in {"b0", "p1", "r"} else "p2_reducer"
        )
        trace.packed_checker_input = render_checking_prompt(trace.task)
        trace.checker_input_estimated_tokens = estimate_tokens(trace.packed_checker_input)
        if trace.checker_input_estimated_tokens > config.context_token_budget:
            trace.task = trace.task.model_copy(
                update={
                    "context_status": "incomplete_context",
                    "warnings": [
                        *trace.task.warnings,
                        "Final canonical checker prompt exceeds context budget.",
                    ],
                }
            )
            trace.packed_checker_input = render_checking_prompt(trace.task)
            trace.checker_input_estimated_tokens = estimate_tokens(trace.packed_checker_input)
            trace.incomplete_stages.append("checker_context_budget")
        if trace.task.context_status != "complete":
            trace.incomplete_stages.append("evidence_context")
        trace.retrieval_context_tokens = sum(estimate_tokens(d.content) for d in documents)
        trace.source_content_hashes = {
            d.source_id: hashlib.sha256(d.content.encode()).hexdigest() for d in documents
        }
        trace.stage_latencies.append(
            StageLatency(stage=stage, duration_ms=(perf_counter() - t) * 1000)
        )
        stage = "checker"
        if checkers_enabled:
            execute_checkers(trace, config)
        trace.status = "failed" if trace.errors else "finished"
    except Exception as exc:
        trace.status = "failed"
        trace.errors.append(
            StageError(stage=stage, error_type=type(exc).__name__, message=str(exc))
        )
        trace.incomplete_stages.extend([stage, "remaining_stages"])
    finally:
        trace.tool_calls = retriever.calls
        for call in trace.tool_calls:
            if call.error_type:
                trace.errors.append(
                    StageError(
                        stage="retrieval_call", error_type=call.error_type, message=call.error or ""
                    )
                )
        if trace.errors:
            trace.status = "failed"
        trace.end_to_end_ms = (perf_counter() - started) * 1000
        # Diagnostic B0 features are extracted after retrieval, never used for its query.
        try:
            t = perf_counter()
            trace.features = extract_features(firmware)
            trace.feature_role = (
                "diagnostic_only" if strategy in {"b0", "r"} else "runtime_equivalent"
            )
            trace.stage_latencies.append(
                StageLatency(stage="diagnostic_features", duration_ms=(perf_counter() - t) * 1000)
            )
        except Exception as exc:
            trace.errors.append(
                StageError(
                    stage="diagnostic_features", error_type=type(exc).__name__, message=str(exc)
                )
            )
            trace.status = "failed"
        trace.end_to_end_ms = (perf_counter() - started) * 1000
    return trace


def run_experiment(config_path: Path):
    config = load_experiment(config_path)
    lock, public, cases = make_lock(config)
    output = Path(config.output_directory)
    lock_path = output / "lock.json"
    if lock_path.exists():
        if json.loads(lock_path.read_text()) != lock.model_dump(mode="json"):
            raise ValueError("Configuration lock mismatch; use a new output directory")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("Output directory is nonempty without a configuration lock")
        write_json(lock_path, lock)
    jobs = [
        (case, strategy, repetition)
        for case in cases
        for strategy in config.strategies
        for repetition in range(1, config.repetitions + 1)
    ]
    if config.shuffle_order:
        random.Random(config.seed).shuffle(jobs)
    traces = []
    for case, strategy, repetition in jobs:
        # Reject source/config drift during a long experiment before any next provider call.
        current, _, _ = make_lock(config)
        if current != lock:
            raise ValueError("Configuration/code/dataset changed during the locked experiment")
        run_id = f"{case.case_id}-{strategy}-r{repetition:02}"
        path = output / "runs" / run_id / "trace.json"
        if path.exists():
            trace = RunTrace.model_validate_json(path.read_text())
            if trace.lock_hash != digest(lock.model_dump(mode="json")) or trace.status == "started":
                raise ValueError(
                    "Incomplete or mismatched existing run; use a new output directory"
                )
            traces.append(trace)
            continue
        source = public.case_source(case.case_id)
        firmware = FirmwareInput(
            case_id=case.case_id,
            source_name=f"{case.case_id}.c",
            content=source,
            sha256=hashlib.sha256(source.encode()).hexdigest(),
        )
        if firmware.sha256 != lock.case_hashes[case.case_id]:
            raise ValueError("Firmware changed after configuration locking")
        write_json(
            path,
            RunTrace(
                run_id=run_id,
                timestamp_utc=datetime.now(UTC).isoformat(),
                lock_hash=digest(lock.model_dump(mode="json")),
                strategy=strategy,
                repetition=repetition,
                seed=config.seed,
                firmware=firmware,
                traffic_kind="local_fixture",
            ),
        )

        class FreshProvider:
            instance = None

            def provider(self):
                if self.instance is None:
                    self.instance = make_retriever(config.retrieval.model_copy(deep=True))
                return self.instance

            def search(self, query, top_k):
                return self.provider().search(query, top_k)

            def fetch(self, source_id):
                return self.provider().fetch(source_id)

        recorder = RecordingRetriever(FreshProvider())
        trace = perform_run(lock, firmware, strategy, repetition, run_id, recorder)
        snapshot = RetrievalSnapshot(
            approved=config.snapshots_approved,
            provider=config.retrieval.retriever,
            corpus_hash=lock.corpus_hash,
            calls=recorder.calls,
        )
        snapshot_path = Path("snapshots") / f"{run_id}.json"
        write_json(output / snapshot_path, snapshot)
        trace.snapshot_path, trace.snapshot_hash = str(snapshot_path), snapshot.content_hash()
        write_json(path, trace)
        if trace.task:
            write_json(path.parent / "task.json", trace.task)
            (path.parent / "checker_prompt.txt").write_text(
                trace.packed_checker_input, encoding="utf-8"
            )
        traces.append(trace)
    variability = {}
    for trace in traces:
        key = f"{trace.firmware.case_id}:{trace.strategy}"
        variability.setdefault(key, []).append(
            {
                "run_id": trace.run_id,
                "ordered_sources": list(trace.source_content_hashes),
                "source_hashes": trace.source_content_hashes,
                "task_hash": trace.task.evidence_hash() if trace.task else None,
            }
        )
    summary = {
        "lock_hash": digest(lock.model_dump(mode="json")),
        "runs": len(traces),
        "finished": sum(t.status == "finished" for t in traces),
        "failed": sum(t.status == "failed" for t in traces),
        "incomplete": sum(bool(t.incomplete_stages) for t in traces),
        "run_order": [t.run_id for t in traces],
        "retrieval_variability": variability,
        "variability_counts": {
            key: {
                "distinct_source_orders": len({tuple(v["ordered_sources"]) for v in values}),
                "distinct_task_hashes": len({v["task_hash"] for v in values}),
            }
            for key, values in variability.items()
        },
    }
    write_json(output / "summary.json", summary)
    return summary


def replay_run(run_path: Path, output: Path):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Replay output must be a fresh directory")
    original = RunTrace.model_validate_json(run_path.read_text())
    root = run_path.parent.parent.parent
    lock = ExperimentLock.model_validate_json((root / "lock.json").read_text())
    if original.lock_hash != digest(lock.model_dump(mode="json")):
        raise ValueError("Exact replay impossible: experiment lock hash mismatch")
    skill, template, _ = instruction_assets()
    if (
        code_hash() != lock.code_hash
        or hashlib.sha256((skill + template).encode()).hexdigest() != lock.instruction_hash
    ):
        raise ValueError("Exact replay impossible: code or canonical instructions changed")
    if not original.snapshot_path or not original.snapshot_hash:
        raise ValueError("Exact replay impossible: content snapshot was not recorded")
    path = (root / original.snapshot_path).resolve()
    if not path.is_relative_to((root / "snapshots").resolve()):
        raise ValueError("Snapshot path escapes the isolated replay store")
    provider = OrderedReplayRetriever(path, original.snapshot_hash)
    recorder = RecordingRetriever(provider)
    replay = perform_run(
        lock,
        original.firmware,
        original.strategy,
        original.repetition,
        original.run_id + "-replay",
        recorder,
        replay_of=original.run_id,
        checkers_enabled=False,
    )
    consistent = (
        provider.position == len(provider.snapshot.calls)
        and replay.source_content_hashes == original.source_content_hashes
        and (replay.task.evidence_hash() if replay.task else None)
        == (original.task.evidence_hash() if original.task else None)
        and replay.packed_checker_input == original.packed_checker_input
        and [
            call.model_dump(mode="json", exclude={"duration_ms", "error"})
            for call in replay.tool_calls
        ]
        == [
            call.model_dump(mode="json", exclude={"duration_ms", "error"})
            for call in original.tool_calls
        ]
    )
    replay.snapshot_path, replay.snapshot_hash = str(path), original.snapshot_hash
    if consistent:
        started = perf_counter()
        try:
            execute_checkers(replay, lock.config)
        except Exception as exc:
            replay.errors.append(
                StageError(stage="checker", error_type=type(exc).__name__, message=str(exc))
            )
            replay.incomplete_stages.append("checker")
        replay.end_to_end_ms += (perf_counter() - started) * 1000
        if replay.errors:
            replay.status = "failed"
    if not consistent:
        replay.status = "failed"
        replay.errors.append(
            StageError(
                stage="replay",
                error_type="ReplayMismatch",
                message="Exact evidence replay impossible; trace diverged",
            )
        )
    write_json(output / "trace.json", replay)
    write_json(
        output / "comparison.json",
        {
            "exact_evidence_replay": consistent,
            "snapshot": str(path),
            "snapshot_hash": original.snapshot_hash,
            "checker_results_may_differ": True,
            "timing_reproduced": False,
        },
    )
    return consistent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", type=Path, required=True)
    replay = sub.add_parser("replay")
    replay.add_argument("--run", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (
            run_experiment(args.config)
            if args.command == "run"
            else replay_run(args.run, args.output)
        )
        if isinstance(result, dict):
            result = {
                key: result[key]
                for key in ("lock_hash", "runs", "finished", "failed", "incomplete")
            }
        print(json.dumps(result))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
