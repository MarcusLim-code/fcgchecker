"""Typed feature, planning, and RQ1 evaluation records."""

from typing import Literal

from pydantic import Field

from fcgc.schemas.models import Contract, RetrievalOutput


class CallObservation(Contract):
    callee: str
    effective_callee: str
    enclosing_function: str | None
    line: int = Field(ge=1)
    assigned_to: str | None = None
    checked_lines: list[int] = Field(default_factory=list)
    returned_directly: bool = False
    returned_later_lines: list[int] = Field(default_factory=list)
    macro_expanded: bool = False
    possible_indirect_call: bool = False


class SyntaxObservation(Contract):
    kind: str
    expression: str
    line: int = Field(ge=1)


class ObservedFeatures(Contract):
    function_definitions: list[str]
    calls: list[CallObservation]
    pointer_buffer_operations: list[SyntaxObservation]
    control_flow: list[SyntaxObservation]
    identifiers: list[str]


class SemanticCategory(Contract):
    name: str
    basis: list[str]
    confidence: Literal["heuristic"] = "heuristic"


class FeatureReport(Contract):
    extractor_version: str
    analysis_mode: Literal["tree_sitter_ast", "lexical_fallback"]
    parser_has_error: bool
    observed: ObservedFeatures
    inferred_categories: list[SemanticCategory]
    component_hints: list[str]
    unknowns: list[str]


CodeFeatures = FeatureReport


class PlannedConcept(Contract):
    feature_category: str
    guideline_concept: str
    query_terms: str
    basis: list[str]


class QueryPlan(Contract):
    mapping_version: str
    template_version: str
    query: str = Field(min_length=1)
    concepts: list[PlannedConcept]
    api_names: list[str] = Field(default_factory=list)
    component_hints: list[str] = Field(default_factory=list)
    max_queries: int = Field(ge=1)
    document_top_k: int = Field(ge=1)


class P1Run(Contract):
    features: FeatureReport
    plan: QueryPlan
    feature_extraction_ms: float = Field(ge=0)
    query_planning_ms: float = Field(ge=0)
    retrieval: RetrievalOutput


class RuleMetrics(Contract):
    document_top_k: int = Field(ge=1)
    rule_k: int = Field(ge=1)
    applicable_rule_ids: list[str]
    ranked_rule_ids_at_k: list[str]
    relevant_rule_ids: list[str]
    irrelevant_rule_ids: list[str]
    missed_rule_ids: list[str]
    applicable_rule_count: int = Field(ge=0)
    retrieved_rule_count: int = Field(ge=0)
    relevant_rule_count: int = Field(ge=0)
    irrelevant_rule_count: int = Field(ge=0)
    precision_at_k: float | None
    recall_at_k: float | None
    search_operations: int = Field(ge=0)
    fetch_operations: int = Field(ge=0)
    feature_extraction_ms: float = Field(ge=0)
    query_planning_ms: float = Field(ge=0)
    retrieval_ms: float = Field(ge=0)


class StrategyEvaluation(Contract):
    strategy: Literal["b0", "p1"]
    query: str
    fetched_source_ids: list[str]
    metrics: RuleMetrics
    mapping_version: str | None = None
    template_version: str | None = None
    concepts: list[PlannedConcept] = Field(default_factory=list)
    analysis_mode: str | None = None
    unknowns: list[str] = Field(default_factory=list)


class CaseComparison(Contract):
    case_id: str
    b0: StrategyEvaluation
    p1: StrategyEvaluation
    recall_delta: float | None
    precision_delta: float | None
    search_operation_delta: int
    fetch_operation_delta: int
    outcome: Literal["improvement", "regression", "tie", "undefined"]


class AggregateMetrics(Contract):
    true_positive_rules: int
    retrieved_rules: int
    applicable_rules: int
    micro_precision_at_k: float | None
    micro_recall_at_k: float | None
    search_operations: int
    fetch_operations: int
    feature_extraction_ms: float
    query_planning_ms: float
    retrieval_ms: float


class RQ1Report(Contract):
    report_version: str
    dataset_version: str
    annotation_version: str
    split: Literal["development"]
    document_top_k: int
    rule_k: int
    max_searches_per_case: int
    max_fetches_per_case: int
    budget_description: str
    matched_budget: bool
    b0_aggregate: AggregateMetrics
    p1_aggregate: AggregateMetrics
    improvements: list[str]
    regressions: list[str]
    ties: list[str]
    cases: list[CaseComparison]
