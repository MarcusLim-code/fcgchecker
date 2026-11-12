"""Typed P2 reduction decisions, packed checker input, and resource accounting."""

from typing import Literal

from pydantic import Field, model_validator

from fcgc.schemas.models import Contract, FirmwareInput
from fcgc.schemas.rules import RuleEvidence, SourceSpan
from fcgc.schemas.stage3 import P1Run

DecisionAction = Literal["include", "exclude"]
ContextStatus = Literal["complete", "incomplete_context", "budget_exceeded"]


class ReductionDecision(Contract):
    evidence_id: str
    rule_id: str | None
    source_id: str
    source_ref: str
    action: DecisionAction
    reason_codes: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    relevance_score: int = Field(ge=0)
    preserved_for_uncertainty: bool = False
    duplicate_of: str | None = None


class EvidenceSelection(Contract):
    config_version: str
    candidate_rules: list[RuleEvidence]
    decisions: list[ReductionDecision]
    selected_ids: list[str]
    excluded_ids: list[str]
    unresolved_dependencies: list[str]
    warnings: list[str]

    @model_validator(mode="after")
    def every_candidate_has_one_decision(self) -> "EvidenceSelection":
        candidates = [rule.evidence_id for rule in self.candidate_rules]
        decided = [decision.evidence_id for decision in self.decisions]
        if len(candidates) != len(set(candidates)) or set(candidates) != set(decided):
            raise ValueError("Each unique candidate needs exactly one reduction decision")
        if len(decided) != len(set(decided)):
            raise ValueError("Reduction decisions contain duplicate evidence IDs")
        included = {
            decision.evidence_id for decision in self.decisions if decision.action == "include"
        }
        excluded = {
            decision.evidence_id for decision in self.decisions if decision.action == "exclude"
        }
        if set(self.selected_ids) != included or set(self.excluded_ids) != excluded:
            raise ValueError("Selected and excluded IDs disagree with decisions")
        if included & excluded:
            raise ValueError("Evidence cannot be both selected and excluded")
        return self


class CodeLocation(Contract):
    source_name: str
    sha256: str
    line_count: int = Field(ge=1)


class UnresolvedSection(Contract):
    source_id: str
    source_ref: str
    span: SourceSpan
    reason: str


class PackedEvidence(Contract):
    rule: RuleEvidence
    retained_spans: list[SourceSpan] = Field(min_length=1)
    duplicate_source_refs: list[str] = Field(default_factory=list)
    rendered_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def no_required_span_is_lost(self) -> "PackedEvidence":
        required = [
            self.rule.normative_span,
            *(fragment.span for fragment in self.rule.conditions),
            *(fragment.span for fragment in self.rule.exceptions),
            *(fragment.span for fragment in self.rule.supporting_definitions),
            *(reference.span for reference in self.rule.dependencies),
        ]
        if self.rule.ambiguity_status == "review_required" and self.rule.section_span is not None:
            required.append(self.rule.section_span)
        for span in required:
            if not any(
                retained.start <= span.start and retained.end >= span.end
                for retained in self.retained_spans
            ):
                raise ValueError("Packed evidence omits a required normative or context span")
            if span.excerpt not in self.rendered_text and not any(
                retained.start <= span.start
                and retained.end >= span.end
                and retained.excerpt in self.rendered_text
                for retained in self.retained_spans
            ):
                raise ValueError("Packed evidence text omits a required source excerpt")
        return self


class PackedCheckerRequest(Contract):
    """Auditable request; only rendered_input is the future model-bound payload."""

    strategy: Literal["p2", "p3"] = "p2"
    firmware: FirmwareInput
    location: CodeLocation
    evidence: list[PackedEvidence]
    unresolved_sections: list[UnresolvedSection]
    instructions_version: str
    instructions: str
    warnings: list[str]
    status: Literal["complete", "incomplete_context"]
    rendered_input: str
    tokenizer_version: str
    estimated_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def input_contains_code_and_evidence(self) -> "PackedCheckerRequest":
        if self.firmware.content not in self.rendered_input:
            raise ValueError("Packed checker input omits firmware source")
        if self.instructions not in self.rendered_input:
            raise ValueError("Packed checker input omits checker instructions")
        for item in self.evidence:
            if item.rendered_text not in self.rendered_input:
                raise ValueError("Packed checker input omits selected evidence")
        for section in self.unresolved_sections:
            if section.span.excerpt not in self.rendered_input:
                raise ValueError("Packed checker input omits an unresolved source section")
        return self

    def checker_payload(self) -> str:
        """Gate future checker calls on complete context; do not serialize the audit model."""
        if self.status != "complete":
            raise ValueError("Incomplete evidence context is not ready for compliance checking")
        return self.rendered_input


class ContextMetrics(Contract):
    tokenizer_version: str
    retrieval_context_tokens: int = Field(ge=0)
    p1_full_document_input_tokens: int = Field(ge=0)
    p2_checker_input_tokens: int | None = Field(default=None, ge=0)
    required_p2_input_tokens: int = Field(ge=0)
    token_savings: int | None = None
    token_savings_percent: float | None = None
    candidate_rule_count: int = Field(ge=0)
    selected_rule_count: int = Field(ge=0)
    excluded_rule_count: int = Field(ge=0)
    uncertainty_preserved_count: int = Field(ge=0)
    context_budget_tokens: int = Field(ge=1)
    budget_failure: bool
    reduction_ms: float = Field(ge=0)
    packing_ms: float = Field(ge=0)


class P2Run(Contract):
    p1: P1Run
    selection: EvidenceSelection
    unresolved_sections: list[UnresolvedSection]
    checker_request: PackedCheckerRequest | None
    status: ContextStatus
    metrics: ContextMetrics

    @model_validator(mode="after")
    def status_matches_request(self) -> "P2Run":
        if self.status == "budget_exceeded" and self.checker_request is not None:
            raise ValueError("Budget-exceeded runs must not supply a checker request")
        if self.status != "budget_exceeded" and self.checker_request is None:
            raise ValueError("Non-budget failures need an auditable checker request")
        return self
