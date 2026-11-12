"""Development-only, matched-budget B0 versus P1 rule retrieval evaluation."""

import argparse
import tomllib
from importlib.resources import files
from pathlib import Path

from pydantic import Field

from fcgc.experiments.benchmark import PublicBenchmark, load_public_benchmark
from fcgc.experiments.calibration import load_development_annotations
from fcgc.retrieval.baseline import load_firmware, retrieve_b0
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.retrieval.query_planner import FCGQueryPlanner
from fcgc.schemas.benchmark import CaseAnnotation, RuleCatalog
from fcgc.schemas.models import Contract, RetrievalOutput
from fcgc.schemas.stage3 import (
    AggregateMetrics,
    CaseComparison,
    P1Run,
    RQ1Report,
    RuleMetrics,
    StrategyEvaluation,
)


class EvaluationConfig(Contract):
    report_version: str = Field(min_length=1)
    document_top_k: int = Field(ge=1)
    rule_k: int = Field(ge=1)
    max_searches_per_case: int = Field(ge=1)
    max_fetches_per_case: int = Field(ge=1)


def ranked_rule_ids(output: RetrievalOutput, catalog: RuleCatalog) -> list[str]:
    """Rank canonical IDs by fetched-document order, then source line, then ID."""
    by_source: dict[str, list[tuple[int, str]]] = {}
    for rule in catalog.rules:
        by_source.setdefault(rule.source_id, []).append((rule.line, rule.rule_id))
    for rules in by_source.values():
        rules.sort()
    ranked = []
    seen = set()
    for document in output.documents:
        for _, rule_id in by_source.get(document.source_id, []):
            if rule_id not in seen:
                ranked.append(rule_id)
                seen.add(rule_id)
    return ranked


def _metrics(
    output: RetrievalOutput,
    applicable: list[str],
    catalog: RuleCatalog,
    rule_k: int,
    feature_extraction_ms: float = 0.0,
    query_planning_ms: float = 0.0,
) -> RuleMetrics:
    ranked = ranked_rule_ids(output, catalog)[:rule_k]
    applicable_set = set(applicable)
    relevant = [rule_id for rule_id in ranked if rule_id in applicable_set]
    irrelevant = [rule_id for rule_id in ranked if rule_id not in applicable_set]
    missed = [rule_id for rule_id in applicable if rule_id not in relevant]
    search_count = sum(event.operation == "search" for event in output.trace.events)
    fetch_count = sum(event.operation == "fetch" for event in output.trace.events)
    return RuleMetrics(
        document_top_k=output.request.top_k,
        rule_k=rule_k,
        applicable_rule_ids=applicable,
        ranked_rule_ids_at_k=ranked,
        relevant_rule_ids=relevant,
        irrelevant_rule_ids=irrelevant,
        missed_rule_ids=missed,
        applicable_rule_count=len(applicable),
        retrieved_rule_count=len(ranked),
        relevant_rule_count=len(relevant),
        irrelevant_rule_count=len(irrelevant),
        precision_at_k=len(relevant) / len(ranked) if ranked else None,
        recall_at_k=len(relevant) / len(applicable) if applicable else None,
        search_operations=search_count,
        fetch_operations=fetch_count,
        feature_extraction_ms=feature_extraction_ms,
        query_planning_ms=query_planning_ms,
        retrieval_ms=output.trace.total_duration_ms,
    )


def _evaluation(
    output: RetrievalOutput,
    applicable: list[str],
    catalog: RuleCatalog,
    rule_k: int,
    p1: P1Run | None = None,
) -> StrategyEvaluation:
    metrics = _metrics(
        output,
        applicable,
        catalog,
        rule_k,
        feature_extraction_ms=p1.feature_extraction_ms if p1 else 0,
        query_planning_ms=p1.query_planning_ms if p1 else 0,
    )
    return StrategyEvaluation(
        strategy="p1" if p1 else "b0",
        query=output.request.query,
        fetched_source_ids=[document.source_id for document in output.documents],
        metrics=metrics,
        mapping_version=p1.plan.mapping_version if p1 else None,
        template_version=p1.plan.template_version if p1 else None,
        concepts=p1.plan.concepts if p1 else [],
        analysis_mode=p1.features.analysis_mode if p1 else None,
        unknowns=p1.features.unknowns if p1 else [],
    )


def _aggregate(evaluations: list[StrategyEvaluation]) -> AggregateMetrics:
    metrics = [evaluation.metrics for evaluation in evaluations]
    true_positive = sum(metric.relevant_rule_count for metric in metrics)
    retrieved = sum(metric.retrieved_rule_count for metric in metrics)
    applicable = sum(metric.applicable_rule_count for metric in metrics)
    return AggregateMetrics(
        true_positive_rules=true_positive,
        retrieved_rules=retrieved,
        applicable_rules=applicable,
        micro_precision_at_k=true_positive / retrieved if retrieved else None,
        micro_recall_at_k=true_positive / applicable if applicable else None,
        search_operations=sum(metric.search_operations for metric in metrics),
        fetch_operations=sum(metric.fetch_operations for metric in metrics),
        feature_extraction_ms=sum(metric.feature_extraction_ms for metric in metrics),
        query_planning_ms=sum(metric.query_planning_ms for metric in metrics),
        retrieval_ms=sum(metric.retrieval_ms for metric in metrics),
    )


def _outcome(b0: RuleMetrics, p1: RuleMetrics) -> tuple[str, float | None, float | None]:
    recall_delta = (
        p1.recall_at_k - b0.recall_at_k
        if p1.recall_at_k is not None and b0.recall_at_k is not None
        else None
    )
    precision_delta = (
        p1.precision_at_k - b0.precision_at_k
        if p1.precision_at_k is not None and b0.precision_at_k is not None
        else None
    )
    if recall_delta is None:
        return "undefined", recall_delta, precision_delta
    if recall_delta > 0 or (
        recall_delta == 0 and precision_delta is not None and precision_delta > 0
    ):
        return "improvement", recall_delta, precision_delta
    if recall_delta < 0 or (
        recall_delta == 0 and precision_delta is not None and precision_delta < 0
    ):
        return "regression", recall_delta, precision_delta
    return "tie", recall_delta, precision_delta


def evaluate_development(root: Path, config_path: Path | None = None) -> RQ1Report:
    config = EvaluationConfig.model_validate(
        tomllib.loads((config_path or root / "rq1_development.toml").read_text(encoding="utf-8"))
    )
    if config.max_searches_per_case != 1 or config.max_fetches_per_case != config.document_top_k:
        raise ValueError("Stage 3 matched budget requires one search and fetch budget equal to K")
    public: PublicBenchmark = load_public_benchmark(root)
    retriever = BenchmarkLexicalRetriever()
    # Preserve the Stage 3 development comparison as a versioned historical run.
    config_dir = Path(str(files("fcgc").joinpath("config")))
    planner = FCGQueryPlanner(
        mapping_path=config_dir / "feature_concepts_v1.json",
        template_path=config_dir / "p1_templates_v1.toml",
    )
    public_source_ids = {document.source_id for document in public.manifest.documents}

    # Run both strategies using only public code, corpus, and query configuration.
    runs: dict[str, tuple[RetrievalOutput, P1Run, str]] = {}
    for case in public.manifest.cases:
        if case.split != "development":
            continue
        path = public._public_path(case.path, "benchmark_cases", ".c")
        firmware = load_firmware(path, case.case_id)
        b0 = retrieve_b0(firmware, retriever, top_k=config.document_top_k)
        p1 = retrieve_p1(firmware, retriever, top_k=config.document_top_k, planner=planner)
        for output in (b0, p1.retrieval):
            if any(document.source_id not in public_source_ids for document in output.documents):
                raise ValueError("Retrieval escaped the public benchmark corpus")
        runs[case.case_id] = (b0, p1, firmware.sha256)

    # Development annotations are opened only after all queries and retrievals are fixed.
    annotations: dict[str, CaseAnnotation] = {
        annotation.case_id: annotation for annotation in load_development_annotations(root)
    }
    comparisons = []
    for case in public.manifest.cases:
        if case.split != "development":
            continue
        b0_output, p1_run, code_hash = runs[case.case_id]
        annotation = annotations[case.case_id]
        if annotation.code_sha256 != code_hash:
            raise ValueError(f"Development annotation hash mismatch: {case.case_id}")
        if annotation.dataset_version != public.manifest.dataset_version:
            raise ValueError(f"Development annotation version mismatch: {case.case_id}")
        applicable = [judgement.rule_id for judgement in annotation.applicable_rules]
        b0_eval = _evaluation(b0_output, applicable, public.rules, config.rule_k)
        p1_eval = _evaluation(p1_run.retrieval, applicable, public.rules, config.rule_k, p1_run)
        outcome, recall_delta, precision_delta = _outcome(b0_eval.metrics, p1_eval.metrics)
        comparisons.append(
            CaseComparison(
                case_id=case.case_id,
                b0=b0_eval,
                p1=p1_eval,
                recall_delta=recall_delta,
                precision_delta=precision_delta,
                search_operation_delta=(
                    p1_eval.metrics.search_operations - b0_eval.metrics.search_operations
                ),
                fetch_operation_delta=(
                    p1_eval.metrics.fetch_operations - b0_eval.metrics.fetch_operations
                ),
                outcome=outcome,
            )
        )

    matched = all(
        comparison.b0.metrics.search_operations == config.max_searches_per_case
        and comparison.p1.metrics.search_operations == config.max_searches_per_case
        and comparison.b0.metrics.fetch_operations == config.max_fetches_per_case
        and comparison.p1.metrics.fetch_operations == config.max_fetches_per_case
        for comparison in comparisons
    )
    return RQ1Report(
        report_version=config.report_version,
        dataset_version=public.manifest.dataset_version,
        annotation_version=public.manifest.annotation_version,
        split="development",
        document_top_k=config.document_top_k,
        rule_k=config.rule_k,
        max_searches_per_case=config.max_searches_per_case,
        max_fetches_per_case=config.max_fetches_per_case,
        budget_description=(
            "One lexical search and up to three document fetches per case for each strategy; "
            "same corpus, source scope, score, tie-break, document K, and rule K."
        ),
        matched_budget=matched,
        b0_aggregate=_aggregate([comparison.b0 for comparison in comparisons]),
        p1_aggregate=_aggregate([comparison.p1 for comparison in comparisons]),
        improvements=[item.case_id for item in comparisons if item.outcome == "improvement"],
        regressions=[item.case_id for item in comparisons if item.outcome == "regression"],
        ties=[item.case_id for item in comparisons if item.outcome == "tie"],
        cases=comparisons,
    )


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def render_markdown(report: RQ1Report) -> str:
    rows = [
        "# RQ1 development-set comparison: B0 versus P1",
        "",
        f"Dataset {report.dataset_version}; annotations {report.annotation_version}.",
        "Only the eight development annotations were read. Labels remain provisional.",
        "",
        "## Ranking and budget",
        "",
        report.budget_description,
        f"A fetched document contributes its canonical rule IDs ordered by source line. "
        f"Precision and recall use the first {report.rule_k} distinct rule IDs after "
        "document ranking; decoys contribute no IDs. Precision divides by the number "
        "of returned rule IDs (up to K). Recall divides by applicable rule IDs. "
        "The unit is a rule, not a document. Case outcome compares recall first "
        "and precision when recall ties.",
        "",
        f"Actual matched budget: **{report.matched_budget}**.",
        "",
        "## Aggregate",
        "",
        "| Strategy | Relevant / applicable | Relevant / retrieved | Micro recall | "
        "Micro precision | Searches | Fetches | Extraction ms | Planning ms | Retrieval ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metric in (("B0", report.b0_aggregate), ("P1", report.p1_aggregate)):
        rows.append(
            f"| {name} | {metric.true_positive_rules}/{metric.applicable_rules} "
            f"| {metric.true_positive_rules}/{metric.retrieved_rules} "
            f"| {_number(metric.micro_recall_at_k)} | {_number(metric.micro_precision_at_k)} "
            f"| {metric.search_operations} | {metric.fetch_operations} "
            f"| {metric.feature_extraction_ms:.3f} | {metric.query_planning_ms:.3f} "
            f"| {metric.retrieval_ms:.3f} |"
        )
    rows += [
        "",
        "## Per-case comparison",
        "",
        "| Case | Applicable | B0 documents | P1 documents | B0 recall / precision | "
        "P1 recall / precision | Outcome | Search Δ | Fetch Δ |",
        "| --- | ---: | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for case in report.cases:
        b0 = case.b0.metrics
        p1 = case.p1.metrics
        rows.append(
            f"| {case.case_id} | {b0.applicable_rule_count} "
            f"| {', '.join(case.b0.fetched_source_ids)} "
            f"| {', '.join(case.p1.fetched_source_ids)} "
            f"| {_number(b0.recall_at_k)} / {_number(b0.precision_at_k)} "
            f"| {_number(p1.recall_at_k)} / {_number(p1.precision_at_k)} "
            f"| {case.outcome} | {case.search_operation_delta} | {case.fetch_operation_delta} |"
        )
    rows += ["", "## Queries and rule evidence", ""]
    for case in report.cases:
        rows += [
            f"### {case.case_id}",
            "",
            f"Applicable: {', '.join(case.b0.metrics.applicable_rule_ids)}.",
            f"B0 query: `{case.b0.query}`",
            f"P1 query: `{case.p1.query}`",
            f"P1 concepts: {', '.join(concept.guideline_concept for concept in case.p1.concepts)} "
            f"({case.p1.mapping_version}, {case.p1.template_version}).",
            f"B0 relevant: {', '.join(case.b0.metrics.relevant_rule_ids) or 'none'}; "
            f"missed: {', '.join(case.b0.metrics.missed_rule_ids) or 'none'}; "
            f"irrelevant: {case.b0.metrics.irrelevant_rule_count}.",
            f"P1 relevant: {', '.join(case.p1.metrics.relevant_rule_ids) or 'none'}; "
            f"missed: {', '.join(case.p1.metrics.missed_rule_ids) or 'none'}; "
            f"irrelevant: {case.p1.metrics.irrelevant_rule_count}.",
            "",
        ]
    rows += [
        "## Limits",
        "",
        "These are provisional synthetic annotations and one deterministic local run. "
        "Timings include local Python overhead; mapping files were loaded once before "
        "the timed per-case runs. They are not a service-latency estimate. "
        "P1 uses heuristics over syntax; neither path performs compliance checking. "
        "No Atlassian ranking scores or held-out labels were used.",
        "",
    ]
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RQ1 development-only comparison")
    parser.add_argument("root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = evaluate_development(args.root, args.config)
    json_text = report.model_dump_json(indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json_text, encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json_text)


if __name__ == "__main__":
    main()
