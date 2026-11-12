"""Post-hoc research evaluation, independent from runtime predictions and retrieval."""

import argparse
import csv
import hashlib
import html
import json
import math
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from fcgc.experiments.benchmark import load_public_benchmark
from fcgc.experiments.metrics import (
    compliance_metrics,
    ratio,
    retrieval_metrics,
    set_stability,
    unique,
)
from fcgc.experiments.snapshots import digest
from fcgc.experiments.statistics import describe, holm, paired_statistics
from fcgc.schemas.benchmark import CaseAnnotation
from fcgc.schemas.checking import ModelFindings, validate_findings
from fcgc.schemas.models import Contract
from fcgc.schemas.stage9 import ExperimentLock, RunTrace

FEATURE_CATEGORIES = {
    "api_return_handling": "api_return_value",
    "possibly_unchecked_result": "api_return_value",
    "storage_write": "api_return_value",
    "error_handling": "error_handling",
    "pointer_validation": "pointer_validation",
    "buffer_boundary": "buffer_safety",
    "dma_transfer": "buffer_safety",
    "resource_lifetime": "resource_lifetime",
    "initialization": "initialization",
    "interrupt_state": "initialization",
}
PAIRS = [
    ("b0", "p1", "RQ1_query_planning"),
    ("p1", "p2", "RQ2_context_reduction"),
    ("p2", "p3", "RQ3_fallback"),
]
UNEVALUATED_PROVIDERS = {"mock", "placeholder", "devin", "simulated_devin_agent"}
METRICS = [
    "fetched_recall",
    "fetched_precision",
    "retained_recall",
    "checker_received_recall",
    "violation_f1",
    "checker_input_tokens",
    "end_to_end_ms",
    "search_calls",
    "fetch_calls",
]


class EvaluationConfig(Contract):
    experiment_directories: list[str] = Field(min_length=1)
    dataset_root: str
    output_directory: str
    rule_k: int = Field(default=18, ge=1)
    seed: int = 2026
    bootstrap_samples: int = Field(default=2000, ge=100)
    allow_provisional_compliance: bool = False
    frozen_margins: str | None = None
    feature_category_mapping: dict[str, str] = Field(
        default_factory=lambda: FEATURE_CATEGORIES.copy()
    )


def load_evaluation(path):
    text = path.read_text()
    config = EvaluationConfig.model_validate(
        json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    )
    for field in ("dataset_root", "output_directory", "frozen_margins"):
        if getattr(config, field):
            setattr(config, field, str((path.parent / getattr(config, field)).resolve()))
    config.experiment_directories = [
        str((path.parent / p).resolve()) for p in config.experiment_directories
    ]
    return config


def verify_fixture(path):
    fixture = json.loads(path.read_text())
    retrieval = fixture["retrieval"]
    retrieved = retrieval_metrics(
        retrieval["ranked_ids"], retrieval["applicable_ids"], retrieval["k"]
    )
    compliance = fixture["compliance"]
    checked = compliance_metrics(compliance["expected"], compliance["predictions"])
    for measured, expected in (
        (retrieved, retrieval["expected"]),
        (checked, compliance["expected_metrics"]),
    ):
        for key, value in expected.items():
            if not math.isclose(measured[key], value, rel_tol=1e-12):
                raise ValueError(f"Known fixture metric mismatch: {key}")
    return {
        "verified": True,
        "label": fixture["note"],
        "retrieval": retrieved,
        "compliance": checked,
    }


def control_signature(lock):
    settings = lock.config.model_dump(
        mode="json",
        exclude={
            "dataset_root",
            "output_directory",
            "case_ids",
            "split",
            "strategies",
        },
    )
    return digest(
        {
            "settings": settings,
            "code_hash": lock.code_hash,
            "corpus_hash": lock.corpus_hash,
            "instructions": lock.instruction_hash,
            "dataset_version": lock.dataset_version,
            "annotation_version": lock.annotation_version,
        }
    )


def canonical_catalog(public):
    catalog = {rule.rule_id: rule for rule in public.rules.rules}
    if len(catalog) != len(public.rules.rules):
        raise ValueError("Duplicate canonical catalog rule IDs")
    return catalog


def evidence_ids(rules, catalog):
    known, unsupported = [], []
    for rule in rules:
        record = catalog.get(rule.explicit_rule_id)
        if record and (record.source_id, record.source_ref.split("#")[0]) == (
            rule.source_id,
            rule.source_ref,
        ):
            known.append(rule.explicit_rule_id)
        else:
            unsupported.append(rule.evidence_id)
    return known, unsupported


def ordered_rule_sets(trace, catalog):
    sources = unique(call.document.source_id for call in trace.tool_calls if call.document)
    fetched = [
        rule.rule_id
        for source in sources
        for rule in sorted(catalog.values(), key=lambda r: (r.line, r.rule_id))
        if rule.source_id == source
    ]
    candidate, unsupported = evidence_ids(
        [rule for extraction in trace.segmented_documents for rule in extraction.rules], catalog
    )
    # All stages retain the same source-rank / source-line canonical ordering.
    if trace.pipeline is not None and trace.strategy in {"p2", "p3"}:
        selection = trace.pipeline.selection
        retained, unknown = evidence_ids(
            [r for r in selection.candidate_rules if r.evidence_id in selection.selected_ids],
            catalog,
        )
        unsupported.extend(unknown)
    else:
        retained = candidate
    prepared, unknown = evidence_ids(trace.task.rules, catalog) if trace.task else ([], [])
    unsupported.extend(unknown)
    return (
        sources,
        {
            "fetched": fetched,
            "candidate": [key for key in fetched if key in set(candidate)],
            "retained": [key for key in fetched if key in set(retained)],
            "prepared": [key for key in fetched if key in set(prepared)],
        },
        unique(unsupported),
    )


def category_coverage(ids, applicable, catalog):
    expected = {catalog[key].category for key in applicable}
    found = {catalog[key].category for key in ids}
    return {
        "covered": sorted(expected & found),
        "missing": sorted(expected - found),
        "coverage": ratio(len(expected & found), len(expected)),
    }


def efficiency(trace, result):
    if trace.strategy == "p2" and trace.pipeline is not None:
        p1 = trace.pipeline.p1
        feature_ms = p1.feature_extraction_ms
        planning_ms = p1.query_planning_ms
        reduction_ms = trace.pipeline.metrics.reduction_ms
        packing_ms = trace.pipeline.metrics.packing_ms
    elif trace.strategy == "p1" and trace.pipeline is not None:
        feature_ms = trace.pipeline.feature_extraction_ms
        planning_ms = trace.pipeline.query_planning_ms
        reduction_ms = packing_ms = None
    else:
        feature_ms = planning_ms = reduction_ms = packing_ms = None
    execution = result.execution if result else None
    provider_input = execution.input_tokens if execution else None
    output = execution.output_tokens if execution else None
    reported_total = (
        provider_input + output if provider_input is not None and output is not None else None
    )
    pipeline = trace.pipeline
    adaptive = pipeline.metrics if trace.strategy == "p3" and pipeline is not None else None
    return {
        "retrieved_context_estimated_tokens": trace.retrieval_context_tokens if pipeline else None,
        "final_checker_input_estimated_tokens": trace.checker_input_estimated_tokens
        if trace.task
        else None,
        "provider_input_tokens": provider_input,
        "provider_output_tokens": output,
        "provider_reported_total_tokens": reported_total,
        "estimated_total_tokens": None,  # Output cannot be invented from the input estimate.
        "billed_tokens": None,
        "acu": None,
        "rovo_credits": None,
        "search_calls": sum(call.operation == "search" for call in trace.tool_calls),
        "fetch_calls": sum(call.operation == "fetch" for call in trace.tool_calls),
        "feature_extraction_ms": feature_ms,
        "diagnostic_feature_extraction_ms": next(
            (
                stage.duration_ms
                for stage in trace.stage_latencies
                if stage.stage == "diagnostic_features"
            ),
            None,
        ),
        "query_planning_ms": planning_ms,
        "retrieval_ms": sum(call.duration_ms for call in trace.tool_calls),
        "reduction_ms": reduction_ms,
        "packing_ms": packing_ms,
        "checker_ms": execution.duration_ms if execution else None,
        "end_to_end_ms": trace.end_to_end_ms if trace.status != "started" else None,
        "fallback_search_calls": adaptive.additional_search_calls if adaptive else 0,
        "fallback_fetch_calls": adaptive.additional_fetch_calls if adaptive else 0,
        "fallback_overhead_ms": adaptive.additional_duration_ms if adaptive else None,
        "fallback_added_context_tokens": adaptive.additional_retrieval_tokens if adaptive else None,
        "measurement_method": trace.token_estimation_method,
    }


def evaluate_observation(trace, annotation, catalog, result, checker_index, config, panel):
    sources, stages, unsupported = ordered_rule_sets(trace, catalog)
    applicable = [rule.rule_id for rule in annotation.applicable_rules]
    reviewed = annotation.review_status == "independently_reviewed"
    checker_status = str(result.status) if result else "missing_result"
    provider = result.execution.provider if result else "unavailable"
    eligible = bool(
        result
        and checker_status == "evaluated"
        and provider not in UNEVALUATED_PROVIDERS
        and trace.traffic_kind != "synthetic_contract_test"
        and (reviewed or config.allow_provisional_compliance)
    )
    validation_error = None
    if result and trace.task:
        try:
            validate_findings(trace.task, ModelFindings(findings=result.findings))
        except ValueError as exc:
            eligible = False
            validation_error = str(exc)
    task_rules = {rule.evidence_id: rule for rule in trace.task.rules} if trace.task else {}
    predictions = []
    for finding in result.findings if result else []:
        rule = task_rules.get(finding.evidence_id)
        if rule and rule.explicit_rule_id in stages["prepared"]:
            predictions.append(
                {
                    "rule_id": rule.explicit_rule_id,
                    "decision": finding.decision,
                    "locations": [loc.model_dump() for loc in finding.locations],
                }
            )
    stages["checker_received"] = stages["prepared"] if result else []
    if not result or not trace.task:
        model_supplied = None
    elif (
        trace.task.context_status != "complete"
        or provider in UNEVALUATED_PROVIDERS
        or trace.traffic_kind == "synthetic_contract_test"
    ):
        model_supplied = []
    elif checker_status == "evaluated" or result.execution.input_tokens is not None:
        model_supplied = stages["prepared"]
    else:
        model_supplied = None
    retrieval = {
        stage: retrieval_metrics(ids, applicable, config.rule_k) for stage, ids in stages.items()
    }
    for stage, values in retrieval.items():
        values["available"] = (
            trace.pipeline is not None if stage != "checker_received" else result is not None
        )
        if not values["available"]:
            for key in ("precision_at_k", "recall_at_k", "f2_at_k", "all_evidence_coverage"):
                values[key] = None
    retrieval["model_supplied"] = (
        retrieval_metrics(model_supplied, applicable, config.rule_k)
        if model_supplied is not None
        else None
    )
    compliance = compliance_metrics(
        [rule.model_dump(mode="json") for rule in annotation.applicable_rules],
        predictions,
        eligible=eligible,
    )
    resources = efficiency(trace, result)
    resources["estimated_input_tokens_per_correct_detection"] = (
        ratio(resources["final_checker_input_estimated_tokens"], compliance["tp"])
        if resources["final_checker_input_estimated_tokens"] is not None
        else None
    )
    resources["reported_tokens_per_correct_detection"] = (
        ratio(resources["provider_reported_total_tokens"], compliance["tp"])
        if resources["provider_reported_total_tokens"] is not None
        else None
    )
    found_categories = {catalog[key].category for key in stages["retained"]}
    features = (
        [category.name for category in trace.features.inferred_categories] if trace.features else []
    )
    mapped = {
        feature: config.feature_category_mapping[feature]
        for feature in features
        if feature in config.feature_category_mapping
    }
    return {
        "panel": panel,
        "run_id": trace.run_id,
        "strategy": trace.strategy,
        "case_id": annotation.case_id,
        "repetition": trace.repetition,
        "checker_index": checker_index,
        "checker_provider": provider,
        "checker_model": result.execution.model if result else None,
        "checker_status": checker_status,
        "run_status": trace.status,
        "incomplete_stages": trace.incomplete_stages,
        "ground_truth_review": annotation.review_status,
        "compliance_eligible": eligible,
        "compliance_exclusion": (
            None
            if eligible
            else validation_error
            or (
                "mock_or_unexecuted_checker"
                if checker_status != "evaluated"
                or provider in UNEVALUATED_PROVIDERS
                or trace.traffic_kind == "synthetic_contract_test"
                else "provisional_ground_truth"
            )
        ),
        "unsupported_evidence_ids": unsupported,
        "ordered_sources": sources,
        "ordered_rule_ids": stages,
        "retrieval": retrieval,
        "compliance": compliance,
        "efficiency": resources,
        "categories": {
            stage: category_coverage(ids, applicable, catalog) for stage, ids in stages.items()
        },
        "feature_category_coverage": ratio(
            sum(category in found_categories for category in mapped.values()), len(mapped)
        ),
        "unmapped_features": sorted(set(features) - set(mapped)),
        "lost_in_segmentation": (
            sorted(
                set(retrieval["fetched"]["all_applicable_present"])
                - set(retrieval["candidate"]["all_applicable_present"])
            )
            if trace.pipeline
            else None
        ),
        "lost_in_reduction": (
            sorted(
                set(retrieval["candidate"]["all_applicable_present"])
                - set(retrieval["retained"]["all_applicable_present"])
            )
            if trace.pipeline
            else None
        ),
        "lost_before_checker": (
            sorted(
                set(retrieval["retained"]["all_applicable_present"])
                - set(retrieval["checker_received"]["all_applicable_present"])
            )
            if result
            else None
        ),
        "ambiguous_evidence_count": sum(
            rule.ambiguity_status == "review_required" for rule in task_rules.values()
        ),
        "errors": [error.model_dump() for error in trace.errors],
    }


def row_metrics(row):
    return {
        "fetched_recall": row["retrieval"]["fetched"]["recall_at_k"],
        "fetched_precision": row["retrieval"]["fetched"]["precision_at_k"],
        "retained_recall": row["retrieval"]["retained"]["recall_at_k"],
        "checker_received_recall": row["retrieval"]["checker_received"]["recall_at_k"],
        "violation_f1": row["compliance"]["f1"],
        "violation_precision": row["compliance"]["precision"],
        "violation_recall": row["compliance"]["recall"],
        "violation_tp": row["compliance"]["tp"],
        "violation_fp": row["compliance"]["fp"],
        "violation_fn": row["compliance"]["fn"],
        "rule_attribution_accuracy": row["compliance"]["rule_attribution_accuracy"],
        "retrieved_context_tokens": row["efficiency"]["retrieved_context_estimated_tokens"],
        "output_tokens": row["efficiency"]["provider_output_tokens"],
        "provider_total_tokens": row["efficiency"]["provider_reported_total_tokens"],
        "tokens_per_correct_detection": row["efficiency"][
            "estimated_input_tokens_per_correct_detection"
        ],
        "checker_input_tokens": row["efficiency"]["final_checker_input_estimated_tokens"],
        "end_to_end_ms": row["efficiency"]["end_to_end_ms"],
        "search_calls": row["efficiency"]["search_calls"],
        "fetch_calls": row["efficiency"]["fetch_calls"],
    }


def aggregate(rows, groups, config):
    by_case = {}
    for row in rows:
        key = (row["panel"], row["strategy"], row["checker_index"], row["case_id"])
        by_case.setdefault(key, []).append(row)
    cases = []
    for (panel, strategy, checker, case), observations in by_case.items():
        values = [row_metrics(row) for row in observations]
        metrics = {
            metric: describe([value[metric] for value in values])["mean"] for metric in values[0]
        }
        cases.append(
            {
                "panel": panel,
                "strategy": strategy,
                "checker_index": checker,
                "case_id": case,
                "group": groups[case],
                "repetitions_observed": len(observations),
                "metrics": metrics,
                "source_set_stability": set_stability(
                    [
                        row["ordered_sources"]
                        for row in observations
                        if row["retrieval"]["fetched"]["available"]
                    ]
                ),
                "rule_set_stability": set_stability(
                    [
                        row["ordered_rule_ids"]["checker_received"]
                        for row in observations
                        if row["retrieval"]["checker_received"]["available"]
                    ]
                ),
                "distinct_source_orders": len(
                    {tuple(row["ordered_sources"]) for row in observations}
                ),
            }
        )
    summaries = []
    panels = sorted({row["panel"] for row in rows})
    for panel in panels:
        for checker in sorted({row["checker_index"] for row in rows if row["panel"] == panel}):
            for strategy in sorted({row["strategy"] for row in rows if row["panel"] == panel}):
                selected = [
                    case
                    for case in cases
                    if (case["panel"], case["strategy"], case["checker_index"])
                    == (panel, strategy, checker)
                ]
                summaries.append(
                    {
                        "panel": panel,
                        "strategy": strategy,
                        "checker_index": checker,
                        "case_count": len(selected),
                        "source_set_stability": describe(
                            [case["source_set_stability"] for case in selected]
                        ),
                        "rule_set_stability": describe(
                            [case["rule_set_stability"] for case in selected]
                        ),
                        "metrics": {
                            metric: describe([case["metrics"][metric] for case in selected])
                            for metric in row_metrics(rows[0])
                        },
                    }
                )
    paired = []
    for panel in panels:
        for checker in sorted({row["checker_index"] for row in rows if row["panel"] == panel}):
            for before, after, question in PAIRS:
                a = {
                    case["case_id"]: case
                    for case in cases
                    if (case["panel"], case["strategy"], case["checker_index"])
                    == (panel, before, checker)
                }
                b = {
                    case["case_id"]: case
                    for case in cases
                    if (case["panel"], case["strategy"], case["checker_index"])
                    == (panel, after, checker)
                }
                for metric in METRICS:
                    differences = {
                        case: b[case]["metrics"][metric] - a[case]["metrics"][metric]
                        for case in a.keys() & b.keys()
                        if a[case]["metrics"][metric] is not None
                        and b[case]["metrics"][metric] is not None
                    }
                    paired.append(
                        {
                            "panel": panel,
                            "checker_index": checker,
                            "comparison": f"{before}_vs_{after}",
                            "question": question,
                            "metric": metric,
                            "missing_or_unpaired_cases": sorted(
                                (a.keys() | b.keys()) - differences.keys()
                            ),
                            **paired_statistics(
                                differences, groups, config.bootstrap_samples, config.seed
                            ),
                        }
                    )
    for panel in panels:
        for checker in {row["checker_index"] for row in rows if row["panel"] == panel}:
            for metric in METRICS:
                selected = [
                    p
                    for p in paired
                    if (p["panel"], p["checker_index"], p["metric"]) == (panel, checker, metric)
                ]
                adjusted = holm({p["comparison"]: p["sign_flip_p"] for p in selected})
                for p in selected:
                    p["holm_sign_flip_p"] = adjusted.get(p["comparison"])
    baseline = {
        (case["panel"], case["checker_index"], case["case_id"]): case["metrics"][
            "checker_input_tokens"
        ]
        for case in cases
        if case["strategy"] == "p1"
    }
    for row in rows:
        value = baseline.get((row["panel"], row["checker_index"], row["case_id"]))
        tokens = row["efficiency"]["final_checker_input_estimated_tokens"]
        row["efficiency"]["token_reduction_percent_vs_p1"] = (
            100 * (value - tokens) / value if value and tokens is not None else None
        )
    for summary in summaries:
        selected = [
            case
            for case in cases
            if (case["panel"], case["strategy"], case["checker_index"])
            == (summary["panel"], summary["strategy"], summary["checker_index"])
        ]
        eligible = [case for case in selected if case["metrics"]["violation_tp"] is not None]
        tp = sum(case["metrics"]["violation_tp"] for case in eligible) if eligible else None
        fp = sum(case["metrics"]["violation_fp"] for case in eligible) if eligible else None
        fn = sum(case["metrics"]["violation_fn"] for case in eligible) if eligible else None
        summary["compliance_expected_count_micro"] = {
            "eligible_cases": len(eligible),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": ratio(tp, tp + fp) if eligible else None,
            "recall": ratio(tp, tp + fn) if eligible else None,
            "f1": ratio(2 * tp, 2 * tp + fp + fn) if eligible else None,
            "unit": "sum of within-case mean counts across eligible repetitions",
        }
    return cases, summaries, paired


def evaluate(config: EvaluationConfig):
    public = load_public_benchmark(Path(config.dataset_root))
    catalog = canonical_catalog(public)
    groups = {case.case_id: case.group for case in public.manifest.cases}
    manifest_cases = {case.case_id: case for case in public.manifest.cases}
    rows, missing_runs, locks, annotations, seen = [], [], [], {}, set()
    preflight = [
        ExperimentLock.model_validate_json((Path(directory) / "lock.json").read_text())
        for directory in config.experiment_directories
    ]
    observed_splits = {lock.config.split for lock in preflight}
    if len(observed_splits) != 1:
        raise ValueError("Development and heldout results must be evaluated separately")
    for directory, lock in zip(config.experiment_directories, preflight, strict=True):
        root = Path(directory)
        locks.append(lock)
        if lock.config.retrieval.retriever == "benchmark" and lock.corpus_hash != digest(
            {
                doc.source_id: public.document_source(doc.source_id)
                for doc in public.manifest.documents
            }
        ):
            raise ValueError("Evaluation corpus differs from locked retrieval corpus")
        if (lock.dataset_version, lock.annotation_version) != (
            public.manifest.dataset_version,
            public.manifest.annotation_version,
        ):
            raise ValueError("Evaluation dataset/annotation version differs from experiment")
        if lock.config.split == "heldout":
            from fcgc.experiments.calibration_margins import validate_frozen_margins

            validate_frozen_margins(config, [lock])
        for case_id, code_hash in lock.case_hashes.items():
            if manifest_cases[case_id].split != lock.config.split:
                raise ValueError("Locked case crosses dataset split")
            path = (
                Path(config.dataset_root) / "ground_truth" / lock.config.split / f"{case_id}.json"
            )
            annotation = CaseAnnotation.model_validate_json(path.read_text())
            ids = [rule.rule_id for rule in annotation.applicable_rules]
            if len(ids) != len(set(ids)) or not set(ids) <= set(catalog):
                raise ValueError("Invalid or duplicate ground-truth rule IDs")
            if (
                annotation.case_id != case_id
                or annotation.code_sha256 != code_hash
                or annotation.dataset_version != lock.dataset_version
                or annotation.annotation_version != lock.annotation_version
            ):
                raise ValueError("Annotation identity/hash/version mismatch")
            annotations[case_id] = annotation
        panel = control_signature(lock)
        for case_id in lock.case_hashes:
            for strategy in lock.config.strategies:
                for repetition in range(1, lock.config.repetitions + 1):
                    run_id = f"{case_id}-{strategy}-r{repetition:02}"
                    path = root / "runs" / run_id / "trace.json"
                    if not path.is_file():
                        missing_runs.append(str(path))
                        continue
                    trace = RunTrace.model_validate_json(path.read_text())
                    fetched_documents = [
                        call.document for call in trace.tool_calls if call.document
                    ]
                    if (
                        trace.source_content_hashes
                        and (trace.status == "finished" or fetched_documents)
                        and trace.source_content_hashes
                        != {
                            doc.source_id: hashlib.sha256(doc.content.encode()).hexdigest()
                            for doc in fetched_documents
                        }
                    ):
                        raise ValueError("Trace source content hash mismatch")
                    if lock.config.retrieval.retriever == "benchmark":
                        sources = {doc.source_id: doc for doc in public.manifest.documents}
                        for document in fetched_documents:
                            if (
                                document.source_id not in sources
                                or document.content != public.document_source(document.source_id)
                                or document.source_ref != sources[document.source_id].source_ref
                            ):
                                raise ValueError("Fetched evidence differs from benchmark source")
                    if (
                        trace.lock_hash != digest(lock.model_dump(mode="json"))
                        or trace.firmware.sha256 != lock.case_hashes[case_id]
                        or trace.run_id != run_id
                        or trace.strategy != strategy
                        or trace.repetition != repetition
                    ):
                        raise ValueError("Trace identity differs from locked experiment")
                    if (
                        hashlib.sha256(trace.firmware.content.encode()).hexdigest()
                        != trace.firmware.sha256
                    ):
                        raise ValueError("Trace firmware content hash mismatch")
                    lines = trace.firmware.content.splitlines()
                    for judgment in annotations[case_id].applicable_rules:
                        for span in [*judgment.violation_spans, *judgment.source_evidence]:
                            if not 1 <= span.start_line <= span.end_line <= len(lines):
                                raise ValueError("Broken ground-truth code span")
                            if hasattr(span, "quote") and span.quote not in "\n".join(
                                lines[span.start_line - 1 : span.end_line]
                            ):
                                raise ValueError("Ground-truth quote differs from firmware")
                    for index in range(len(lock.config.checkers)):
                        identity = (panel, strategy, case_id, repetition, index)
                        if identity in seen:
                            raise ValueError(
                                "Duplicate experimental observation; repetitions "
                                "cannot be duplicated across directories"
                            )
                        seen.add(identity)
                        result = (
                            trace.checker_results[index]
                            if index < len(trace.checker_results)
                            else None
                        )
                        if (
                            result
                            and trace.task
                            and result.execution.input_evidence_hash != trace.task.evidence_hash()
                        ):
                            raise ValueError(
                                "Checker result evidence hash differs from supplied task"
                            )
                        if result:
                            validate_checker_controls(result, lock, trace, index)
                        rows.append(
                            evaluate_observation(
                                trace, annotations[case_id], catalog, result, index, config, panel
                            )
                        )
    if not rows:
        raise ValueError("No saved observations available")
    cases, summaries, paired = aggregate(rows, groups, config)
    split = next(iter(observed_splits))
    report = {
        "version": "research-evaluation-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "configuration": config.model_dump(mode="json"),
        "split": split,
        "labels": {
            "data": "synthetic",
            "retrieval": sorted({lock.config.retrieval.retriever for lock in locks}),
            "checking": sorted({row["checker_provider"] for row in rows}),
            "retrieval_kind": sorted(
                {
                    "local_fixture"
                    if lock.config.retrieval.retriever in {"local", "benchmark"}
                    else "recorded_replay"
                    if lock.config.retrieval.retriever == "replay"
                    else "live_MCP_unverified"
                    for lock in locks
                }
            ),
            "checker_kind": sorted(
                {
                    {
                        "mock": "mock",
                        "synthetic_demo": "deterministic",
                        "ollama": "local_LLM",
                        "devin": "Devin_unimplemented",
                    }.get(row["checker_provider"], "unavailable")
                    for row in rows
                }
            ),
            "resources": (
                "local token estimates and measured wall time; provider tokens on"
                "ly when exposed; no billing measurements"
            ),
            "ground_truth": sorted(
                {annotation.review_status for annotation in annotations.values()}
            ),
        },
        "experiment_lock_hashes": [digest(lock.model_dump(mode="json")) for lock in locks],
        "canonical_catalog_hash": digest(public.rules.model_dump(mode="json")),
        "control_signatures": sorted({control_signature(lock) for lock in locks}),
        "experimental_controls": [
            {
                "panel": control_signature(lock),
                "code_version": lock.code_version,
                "code_hash": lock.code_hash,
                "dataset_version": lock.dataset_version,
                "annotation_version": lock.annotation_version,
                "document_top_k": lock.config.document_top_k,
                "reference_top_k": lock.config.reference_top_k,
                "context_token_budget": lock.config.context_token_budget,
                "fallback": lock.config.fallback.model_dump(mode="json"),
                "retrieval": lock.config.retrieval.model_dump(mode="json"),
                "checkers": [checker.model_dump(mode="json") for checker in lock.config.checkers],
                "skill_version": lock.config.expected_skill_version,
                "prompt_version": lock.config.expected_prompt_version,
            }
            for lock in locks
        ],
        "annotation_hash": digest(
            {key: annotation.model_dump(mode="json") for key, annotation in annotations.items()}
        ),
        "rows": rows,
        "case_aggregates": cases,
        "configuration_summaries": summaries,
        "paired_comparisons": paired,
        "missing_runs": missing_runs,
        "quality_flags": {
            "incomplete_observations": sum(bool(row["incomplete_stages"]) for row in rows),
            "unsupported_rule_observations": sum(
                bool(row["unsupported_evidence_ids"]) for row in rows
            ),
            "ambiguous_rule_instances": sum(row["ambiguous_evidence_count"] for row in rows),
            "unresolved_finding_instances": sum(
                len(row["compliance"]["unresolved_rule_ids"]) for row in rows
            ),
            "compliance_eligible_observations": sum(row["compliance_eligible"] for row in rows),
        },
        "status_counts": {
            status: sum(row["checker_status"] == status for row in rows)
            for status in sorted({row["checker_status"] for row in rows})
        },
        "limitations": [
            "Synthetic local data cannot establish enterprise retrieval or model performance.",
            (
                "Provisional annotations are not independent ground truth; compli"
                "ance accuracy is disabled unless explicitly exploratory."
            ),
            (
                "Mock/unexecuted checkers have null compliance metrics, never per"
                "fect accuracy or zero model false negatives."
            ),
            (
                "Repetitions are averaged within case; inferential tests resample"
                " matched variant groups, not individual repeated runs."
            ),
            (
                "Small group counts produce coarse p-values and unstable confiden"
                "ce intervals; tests are exploratory."
            ),
            (
                "Sign-flip tests assume symmetric independent group differences; "
                "sign tests also reported. Holm adjustment is within metric/panel"
                " only."
            ),
            (
                "Feature/category mappings and source-line ranking are explicit a"
                "pproximations, not enterprise ranking scores."
            ),
            "Unknown source rule IDs cannot be scored canonically; they remain separately listed.",
            (
                "Provider token counters are not measured bills. Output tokens, t"
                "otal tokens, ACU and Rovo credits remain null when unavailable."
            ),
            (
                "Archived P3 traces do not isolate feature/reduction timings; the"
                "se remain null instead of inferred zero."
            ),
            (
                "Legacy traces do not always establish model submission for unres"
                "olved/error results; model-supplied coverage can be unknown."
            ),
            (
                "Failed/missing runs are reported separately; paired metrics use "
                "available case pairs and disclose exclusions."
            ),
            (
                "End-to-end latency includes the entire configured checker matrix"
                "; checker_ms is specific to one checker."
            ),
        ],
    }
    for comparison in paired:
        cost = comparison["metric"] in {
            "checker_input_tokens",
            "end_to_end_ms",
            "search_calls",
            "fetch_calls",
        }
        comparison["regression_cases"] = {
            case: delta
            for case, delta in comparison["case_deltas"].items()
            if (delta > 0 if cost else delta < 0)
        }
    if split == "heldout":
        from fcgc.experiments.calibration_margins import validate_frozen_margins

        report["margin_assessments"] = validate_frozen_margins(config, locks, report)
    else:
        report["margin_assessments"] = []
    return report


def validate_checker_controls(result, lock, trace, index):
    """Reject saved results that contradict the model/instruction controls they claim."""
    settings = lock.config.checkers[index]
    expected = {
        "placeholder": ("mock", "mock-contract-v1"),
        "mock": ("mock", "mock-contract-v1"),
        "synthetic_demo": ("synthetic_demo", "single-pointer-store-v1"),
        "ollama": ("ollama", settings.model),
        "devin": ("devin", "unimplemented"),
    }[settings.checker]
    execution = result.execution
    if (
        execution.provider,
        execution.model,
    ) != expected or execution.settings != settings.generation:
        raise ValueError("Checker provider/model/settings differ from the locked experiment")
    if (
        execution.skill_version != lock.config.expected_skill_version
        or execution.prompt_template_version != lock.config.expected_prompt_version
        or execution.instruction_hash != lock.instruction_hash
    ):
        raise ValueError("Checker instructions differ from the locked experiment")
    if (
        trace.packed_checker_input is not None
        and execution.prompt_hash != hashlib.sha256(trace.packed_checker_input.encode()).hexdigest()
    ):
        raise ValueError("Checker prompt hash differs from the saved input")


def write_reports(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    summary_rows = []
    for entry in report["configuration_summaries"]:
        summary_rows.append(
            {
                "panel": entry["panel"],
                "strategy": entry["strategy"],
                "checker_index": entry["checker_index"],
                "cases": entry["case_count"],
                "source_jaccard_mean": entry["source_set_stability"]["mean"],
                "rule_jaccard_mean": entry["rule_set_stability"]["mean"],
                **{
                    metric + "_" + stat: value
                    for metric, stats in entry["metrics"].items()
                    for stat, value in stats.items()
                },
            }
        )
    run_rows = []
    for row in report["rows"]:
        run_rows.append(
            {
                "run_id": row["run_id"],
                "strategy": row["strategy"],
                "panel": row["panel"],
                "case_id": row["case_id"],
                "checker": row["checker_index"],
                "checker_status": row["checker_status"],
                "review": row["ground_truth_review"],
                **row_metrics(row),
                "missed_rules": json.dumps(
                    row["retrieval"]["checker_received"]["all_applicable_missing"]
                ),
                "false_negative_ids": json.dumps(row["compliance"]["false_negative_ids"]),
                "lost_reduction": json.dumps(row["lost_in_reduction"]),
                "eligible": row["compliance_eligible"],
            }
        )
    for name, rows in (("summary.csv", summary_rows), ("runs.csv", run_rows)):
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    paired_rows = [
        {
            "panel": row["panel"],
            "comparison": row["comparison"],
            "metric": row["metric"],
            "cases": row["case_count"],
            "clusters": row["independent_cluster_count"],
            "mean_delta": row["delta_summary"]["mean"],
            "ci95": json.dumps(row["ci95_mean_delta"]),
            "paired_dz": row["paired_dz"],
            "sign_test_p": row["sign_test_p"],
            "sign_flip_p": row["sign_flip_p"],
            "holm_p": row["holm_sign_flip_p"],
        }
        for row in report["paired_comparisons"]
    ]
    with (output / "paired.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(paired_rows[0])
            if paired_rows
            else [
                "panel",
                "comparison",
                "metric",
                "cases",
                "clusters",
                "mean_delta",
                "ci95",
                "paired_dz",
                "sign_test_p",
                "sign_flip_p",
                "holm_p",
            ],
        )
        writer.writeheader()
        writer.writerows(paired_rows)

    def fmt(value):
        return "unavailable" if value is None else f"{value:.3f}"

    lines = [
        "# FCGC research evaluation",
        "",
        f"Split: {report['split']}. Labels: `{report['labels']}`.",
        f"Quality flags: {report['quality_flags']}.",
        "",
        (
            "Rule K is a unique canonical-rule prefix after source-arrival rank, "
            "source line, then ID. Document K is the experiment search budget; it"
            " is not rule K."
        ),
        (
            "Precision divides by actual unique returned rule IDs up to K; no-app"
            "licable-rule recall and zero-denominator precision are undefined."
        ),
        (
            "Checker-received means the adapter got the frozen task; model-suppli"
            "ed coverage is separately recorded and is empty for mocks."
        ),
        "",
        (
            "| Configuration | Cases | Fetched recall@K | Fetched precision@K | "
            "Retained recall@K | Checker-received recall@K | Violation F1 | "
            "Input tokens mean | Calls search/fetch mean |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report["configuration_summaries"]:
        metrics = row["metrics"]
        lines.append(
            f"| {row['panel'][:8]} / {row['strategy']} / checker {row['checker_index']} "
            f"| {row['case_count']} | "
            + " | ".join(
                fmt(metrics[key]["mean"])
                for key in (
                    "fetched_recall",
                    "fetched_precision",
                    "retained_recall",
                    "checker_received_recall",
                    "violation_f1",
                    "checker_input_tokens",
                )
            )
            + f" | {fmt(metrics['search_calls']['mean'])}/{fmt(metrics['fetch_calls']['mean'])} |"
        )
    lines += [
        "",
        "## Paired comparisons",
        "",
        (
            "Deltas are later minus earlier. Repetitions are averaged within firm"
            "ware case; inference uses matched-variant group means. Negative toke"
            "n/latency deltas favor efficiency. No accuracy claim is made for moc"
            "ks or provisional labels."
        ),
        "",
        (
            "| Contrast | Metric | Cases / groups | Mean delta | 95% group bootst"
            "rap CI | Holm sign-flip p |"
        ),
        "| --- | --- | --- | ---: | --- | ---: |",
    ]
    for row in report["paired_comparisons"]:
        lines.append(
            f"| {row['comparison']} | {row['metric']} | {row['case_count']}/"
            f"{row['independent_cluster_count']} | {fmt(row['delta_summary']['mean'])} "
            f"| {row['ci95_mean_delta']} | {fmt(row['holm_sign_flip_p'])} |"
        )
    lines += ["", "## Per-case missed evidence and regressions", ""]
    for row in report["rows"]:
        if row["repetition"] == 1:
            lines.append(
                f"- {row['run_id']}, checker {row['checker_index']}: missed "
                f"{row['retrieval']['checker_received']['all_applicable_missing']}; "
                f"lost during reduction {row['lost_in_reduction']}; "
                f"model FN {row['compliance']['false_negative_ids']}; "
                f"model FP {row['compliance']['false_positive_ids']}; "
                f"status {row['checker_status']}."
            )
    lines += ["", "## Limitations", "", *["- " + value for value in report["limitations"]]]
    lines += [
        "",
        "## Missing and incomplete observations",
        "",
        f"Missing run files: {len(report['missing_runs'])}. "
        f"Checker statuses: {report['status_counts']}.",
    ]
    for row in report["rows"]:
        if row["run_status"] != "finished" or row["incomplete_stages"] or row["errors"]:
            lines.append(
                f"- {row['run_id']}: run={row['run_status']}; "
                f"incomplete={row['incomplete_stages']}; errors={row['errors']}."
            )
    lines += ["", "## Per-case regressions", ""]
    for comparison in report["paired_comparisons"]:
        if comparison["regression_cases"]:
            lines.append(
                f"- {comparison['comparison']} / {comparison['metric']}: "
                f"{comparison['regression_cases']}"
            )
    if report["margin_assessments"]:
        lines += [
            "",
            "## Frozen acceptance-margin results",
            "",
            json.dumps(report["margin_assessments"], indent=2),
        ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
    # Entirely offline, escaped, self-contained HTML; no external script or resource.
    header = (
        "<tr>" + "".join(f"<th>{html.escape(str(key))}</th>" for key in summary_rows[0]) + "</tr>"
    )
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row.values()) + "</tr>"
        for row in summary_rows
    )
    page = (
        "<!doctype html><meta charset='utf-8'><title>FCGC evaluation</title>"
        "<style>body{font:15px system-ui;margin:2rem}table{border-collapse:co"
        "llapse;font-size:12px}td,th{padding:.4rem;border:1px solid #ccc}pre{"
        "white-space:pre-wrap}section{overflow:auto}</style>"
        "<h1>FCGC offline research evaluation</h1><p>" + html.escape(str(report["labels"])) + "</p>"
        "<section><table>"
        + header
        + body
        + "</table></section><details open><summary>Full report</summary><pre>"
        + html.escape("\n".join(lines))
        + "</pre></details>"
    )
    (output / "report.html").write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", type=Path)
    group.add_argument("--verify-fixture", type=Path)
    args = parser.parse_args()
    try:
        if args.verify_fixture:
            print(json.dumps(verify_fixture(args.verify_fixture)))
            return
        config = load_evaluation(args.config)
        report = evaluate(config)
        write_reports(report, Path(config.output_directory))
        print(
            json.dumps(
                {
                    "observations": len(report["rows"]),
                    "case_configuration_aggregates": len(report["case_aggregates"]),
                    "firmware_cases": len({row["case_id"] for row in report["rows"]}),
                    "output": config.output_directory,
                    "labels": report["labels"],
                }
            )
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
