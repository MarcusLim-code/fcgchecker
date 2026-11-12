"""Frozen checker tasks and validated per-rule findings."""

import hashlib
import json
from typing import Literal

from pydantic import Field, StrictInt, model_validator

from fcgc.schemas.models import CheckerResult, Contract, FetchedDocument, FirmwareInput
from fcgc.schemas.rules import RuleEvidence, _check_span


class FrozenCheckingTask(Contract):
    version: Literal["checking-task-v1"] = "checking-task-v1"
    firmware: FirmwareInput
    documents: list[FetchedDocument]
    rules: list[RuleEvidence]
    context_status: Literal["complete", "incomplete_context"]
    warnings: list[str] = Field(default_factory=list)
    full_document_context: bool = False
    # Retain the full artifact; optional focus does not imply isolated program analysis.
    target_function: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z_0-9]*$")
    target_start_line: int | None = Field(default=None, ge=1)
    target_end_line: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_sources(self) -> "FrozenCheckingTask":
        target = (self.target_function, self.target_start_line, self.target_end_line)
        if any(value is not None for value in target) and not all(
            value is not None for value in target
        ):
            raise ValueError("Function focus requires name and both original line coordinates")
        if self.target_function and not (
            self.target_start_line
            <= self.target_end_line
            <= len(self.firmware.content.splitlines())
        ):
            raise ValueError("Function focus is outside the original artifact")
        if hashlib.sha256(self.firmware.content.encode()).hexdigest() != self.firmware.sha256:
            raise ValueError("Firmware hash mismatch")
        documents = {d.source_id: d for d in self.documents}
        if len(documents) != len(self.documents):
            raise ValueError("Duplicate source IDs")
        if len({r.evidence_id for r in self.rules}) != len(self.rules):
            raise ValueError("Duplicate evidence IDs")
        for rule in self.rules:
            document = documents.get(rule.source_id)
            if document is None or (rule.source_ref, rule.document_version) != (
                document.source_ref,
                document.document_version,
            ):
                raise ValueError("Evidence source identity mismatch")
            for span in rule_spans(rule):
                _check_span(document.content, span)
        if self.context_status == "complete":
            ids = {rule.explicit_rule_id for rule in self.rules}
            for rule in self.rules:
                for reference in rule.dependencies:
                    target = reference.target
                    if (
                        (target.startswith("SFCG-") and target not in ids)
                        or (
                            target.endswith(".md")
                            and not any(
                                doc.source_ref.endswith("/" + target) for doc in self.documents
                            )
                        )
                        or (
                            target.lower().startswith("section") and not rule.supporting_definitions
                        )
                    ):
                        raise ValueError("Complete task has an unresolved dependency")
        return self

    def canonical_json(self) -> str:
        data = self.model_dump(mode="json")
        if not self.full_document_context:
            data.pop("full_document_context")
        if self.target_function is None:
            for key in ("target_function", "target_start_line", "target_end_line"):
                data.pop(key)
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def model_input_json(self) -> str:
        """The host retains full source documents; models receive selected evidence only."""
        data = self.model_dump(mode="json")
        if self.target_function is None:
            for key in ("target_function", "target_start_line", "target_end_line"):
                data.pop(key)
        if not self.full_document_context:
            data.pop("full_document_context")
            data["documents"] = [
                document.model_dump(mode="json", exclude={"content"}) for document in self.documents
            ]
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def evidence_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def rule_spans(rule):
    spans = [
        rule.normative_span,
        *(f.span for f in rule.conditions + rule.exceptions + rule.supporting_definitions),
        *(r.span for r in rule.dependencies),
    ]
    if rule.section_span:
        spans.append(rule.section_span)
    return spans


class ViolationLocation(Contract):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    excerpt: str = Field(min_length=1)


class SupportingCitation(Contract):
    source_id: str
    source_ref: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class RuleFinding(Contract):
    evidence_id: str
    applicability: Literal["applies", "not_applicable", "unresolved"]
    decision: Literal["compliant", "violating", "not_applicable", "unresolved"]
    locations: list[ViolationLocation] = Field(default_factory=list)
    citations: list[SupportingCitation] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    uncertainty: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self) -> "RuleFinding":
        if self.decision in {"compliant", "violating"} and self.applicability != "applies":
            raise ValueError("Judgment requires established applicability")
        if self.decision == "not_applicable" and self.applicability != "not_applicable":
            raise ValueError("Not-applicable decision requires matching applicability")
        if self.decision == "unresolved" and not self.uncertainty:
            raise ValueError("Unresolved finding requires uncertainty")
        if self.decision != "unresolved" and not self.citations:
            raise ValueError("Supported judgments require source citations")
        if self.decision == "violating" and not self.locations and not self.uncertainty:
            raise ValueError("Violation needs location or a localization uncertainty")
        return self


class ModelFindings(Contract):
    findings: list[RuleFinding]


class ProviderJudgment(Contract):
    """Validate adapter findings and consumed execution counters before accepting either."""

    prediction: ModelFindings
    details: str | None = None
    input_tokens: StrictInt | None = Field(default=None, ge=0)
    output_tokens: StrictInt | None = Field(default=None, ge=0)


class GenerationSettings(Contract):
    temperature: float = Field(default=0, ge=0, le=2)
    seed: int = 0
    max_output_tokens: int = Field(default=2048, ge=1)
    top_p: float = Field(default=1, gt=0, le=1)


class CheckerExecution(Contract):
    output_schema_version: Literal["model-findings-v1"] = "model-findings-v1"
    provider: str
    model: str
    model_details: str | None = None
    settings: GenerationSettings
    skill_version: str
    prompt_template_version: str
    instruction_hash: str
    input_evidence_hash: str
    prompt_hash: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_ms: float = Field(ge=0)
    error: str | None = None


class CheckingResult(CheckerResult):
    findings: list[RuleFinding]
    execution: CheckerExecution


def validate_findings(task: FrozenCheckingTask, response: ModelFindings) -> ModelFindings:
    rules = {r.evidence_id: r for r in task.rules}
    ids = [f.evidence_id for f in response.findings]
    if set(ids) != set(rules) or len(ids) != len(set(ids)):
        raise ValueError("Findings must cover each supplied evidence ID exactly once")
    lines = task.firmware.content.splitlines()
    for finding in response.findings:
        rule = rules[finding.evidence_id]
        if rule.ambiguity_status == "review_required" and finding.decision != "unresolved":
            raise ValueError("Unreviewed source ambiguity permits unresolved findings only")
        if task.context_status != "complete" and finding.decision != "unresolved":
            raise ValueError("Incomplete evidence permits unresolved findings only")
        normative_cited = False
        for citation in finding.citations:
            if (citation.source_id, citation.source_ref) != (rule.source_id, rule.source_ref):
                raise ValueError("Unsupported source citation")
            if not any(
                s.start <= citation.start < citation.end <= s.end
                and s.excerpt[citation.start - s.start : citation.end - s.start] == citation.quote
                for s in rule_spans(rule)
            ):
                raise ValueError("Fabricated or unsupported source excerpt")
            if (
                rule.normative_span.start
                <= citation.start
                < citation.end
                <= rule.normative_span.end
            ):
                normative_cited = True
        if finding.decision != "unresolved" and not normative_cited:
            raise ValueError("Judgment must cite the normative statement")
        for location in finding.locations:
            if not 1 <= location.start_line <= location.end_line <= len(lines):
                raise ValueError("Invalid code location")
            if "\n".join(lines[location.start_line - 1 : location.end_line]) != location.excerpt:
                raise ValueError("Fabricated code excerpt")
            if task.target_function and not (
                task.target_start_line
                <= location.start_line
                <= location.end_line
                <= task.target_end_line
            ):
                raise ValueError("Finding location is outside the requested function focus")
    return response
