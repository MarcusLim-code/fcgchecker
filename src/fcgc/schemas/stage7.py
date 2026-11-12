"""Observable sufficiency signals and bounded P3 retrieval audit contracts."""

from typing import Literal

from pydantic import model_validator

from fcgc.schemas.models import Contract, FetchedDocument, SearchResults
from fcgc.schemas.stage3 import FeatureReport, QueryPlan
from fcgc.schemas.stage6 import EvidenceSelection, PackedCheckerRequest


class SufficiencyAssessment(Contract):
    status: Literal["sufficient_signals", "insufficient_evidence"]
    operation_category_coverage: dict[str, list[str]]
    general_category_coverage: dict[str, list[str]]
    normative_rule_count: int
    unresolved_dependencies: list[str]
    ambiguous_applicability: list[str]
    empty_or_weak_results: bool
    duplicate_fraction: float
    excessive_duplication: bool
    missing_expected_categories: list[str]
    reasons: list[str]

    @model_validator(mode="after")
    def reasons_match_status(self) -> "SufficiencyAssessment":
        if (self.status == "insufficient_evidence") != bool(self.reasons):
            raise ValueError("Sufficiency status must agree with observable warning reasons")
        return self


class RetrievalAttempt(Contract):
    round_number: int
    query: str
    template_version: str
    trigger_reasons: list[str]
    results: SearchResults | None
    fetched_source_ids: list[str]
    new_rule_ids: list[str]
    errors: list[str]
    search_calls: int
    fetch_calls: int
    duration_ms: float


class P3Metrics(Contract):
    search_calls: int
    fetch_calls: int
    additional_search_calls: int
    additional_fetch_calls: int
    candidate_sources: int
    initial_retrieval_tokens: int
    final_retrieval_tokens: int
    additional_retrieval_tokens: int
    initial_required_input_tokens: int
    final_required_input_tokens: int
    checker_input_token_delta: int
    initial_duration_ms: float
    additional_duration_ms: float
    total_duration_ms: float
    recovered_categories: list[str]
    resolved_dependencies: list[str]
    warning_signals_recovered: bool


class P3Run(Contract):
    strategy: Literal["p3"] = "p3"
    config_version: str
    features: FeatureReport
    initial_plan: QueryPlan
    initial_assessment: SufficiencyAssessment
    final_assessment: SufficiencyAssessment
    attempts: list[RetrievalAttempt]
    documents: list[FetchedDocument]
    selection: EvidenceSelection
    checker_request: PackedCheckerRequest | None
    status: Literal["sufficient_signals", "insufficient_evidence"]
    stop_reason: str
    metrics: P3Metrics

    @model_validator(mode="after")
    def audit_matches_status(self) -> "P3Run":
        if self.metrics.search_calls != sum(a.search_calls for a in self.attempts):
            raise ValueError("Search accounting differs from attempt log")
        if self.metrics.fetch_calls != sum(a.fetch_calls for a in self.attempts):
            raise ValueError("Fetch accounting differs from attempt log")
        if self.status != self.final_assessment.status:
            raise ValueError("Run status differs from final sufficiency assessment")
        if self.status == "insufficient_evidence" and self.checker_request is not None:
            if self.checker_request.status != "incomplete_context":
                raise ValueError("Insufficient evidence must block checker payload access")
        return self
