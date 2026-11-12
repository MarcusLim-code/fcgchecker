"""Canonical, source-preserving contracts for normalized FCG rule evidence."""

from typing import Literal

from pydantic import Field, model_validator

from fcgc.schemas.models import Contract, FetchedDocument


class SourceSpan(Contract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_bounds(self) -> "SourceSpan":
        if self.end <= self.start:
            raise ValueError("Source span end must exceed start")
        return self


class TableCell(Contract):
    column: str
    span: SourceSpan


class NormalizedBlock(Contract):
    kind: Literal["paragraph", "list_item", "table_row", "code", "blockquote"]
    span: SourceSpan
    heading_lineage: list[str]
    cells: list[TableCell] = Field(default_factory=list)


class NormalizedDocument(Contract):
    document: FetchedDocument
    normalizer_version: str = Field(min_length=1)
    blocks: list[NormalizedBlock]

    @model_validator(mode="after")
    def spans_match_source(self) -> "NormalizedDocument":
        source = self.document.content
        for block in self.blocks:
            _check_span(source, block.span)
            for cell in block.cells:
                _check_span(source, cell.span)
                if not (block.span.start <= cell.span.start < cell.span.end <= block.span.end):
                    raise ValueError("Table cell lies outside row span")
        return self


FragmentKind = Literal[
    "informative", "example", "condition", "exception", "definition", "dependency", "ambiguous"
]


class ContextFragment(Contract):
    kind: FragmentKind
    span: SourceSpan


class ReferenceEvidence(Contract):
    target: str = Field(min_length=1)
    span: SourceSpan


class RuleEvidence(Contract):
    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    document_version: str | None = None
    explicit_rule_id: str | None = None
    heading_lineage: list[str]
    normative_statement: str = Field(min_length=1)
    normative_span: SourceSpan
    conditions: list[ContextFragment] = Field(default_factory=list)
    exceptions: list[ContextFragment] = Field(default_factory=list)
    supporting_definitions: list[ContextFragment] = Field(default_factory=list)
    dependencies: list[ReferenceEvidence] = Field(default_factory=list)
    obligation_strength: Literal[
        "mandatory", "recommendation", "prohibition", "conditional_permission", "uncertain"
    ]
    extraction_method: str = Field(min_length=1)
    ambiguity_status: Literal["clear", "review_required"]
    ambiguity_notes: list[str] = Field(default_factory=list)
    section_span: SourceSpan | None = None
    duplicate_of: str | None = None

    @model_validator(mode="after")
    def statement_is_verbatim(self) -> "RuleEvidence":
        if self.normative_statement != self.normative_span.excerpt:
            raise ValueError("Normative statement must equal its verbatim source excerpt")
        if self.ambiguity_status == "review_required" and not self.ambiguity_notes:
            raise ValueError("Review-required evidence needs an ambiguity note")
        return self


class RuleExtraction(Contract):
    normalized: NormalizedDocument
    extractor_version: str = Field(min_length=1)
    rules: list[RuleEvidence]
    other_fragments: list[ContextFragment]
    review_sections: list[ContextFragment]

    @model_validator(mode="after")
    def all_evidence_traces_to_source(self) -> "RuleExtraction":
        source = self.normalized.document.content
        document = self.normalized.document
        ids = {rule.evidence_id for rule in self.rules}
        if len(ids) != len(self.rules):
            raise ValueError("Duplicate evidence IDs")
        for rule in self.rules:
            if rule.source_id != document.source_id or rule.source_ref != document.source_ref:
                raise ValueError("Rule identity differs from fetched document")
            if rule.document_version != document.document_version:
                raise ValueError("Rule version differs from fetched document")
            _check_span(source, rule.normative_span)
            if rule.section_span is not None:
                _check_span(source, rule.section_span)
            for fragment in rule.conditions + rule.exceptions + rule.supporting_definitions:
                _check_span(source, fragment.span)
            for reference in rule.dependencies:
                _check_span(source, reference.span)
        for fragment in self.other_fragments + self.review_sections:
            _check_span(source, fragment.span)
        return self


def _check_span(source: str, span: SourceSpan) -> None:
    if span.end > len(source) or source[span.start : span.end] != span.excerpt:
        raise ValueError("Evidence span does not match original document text")
    if span.start_line != source.count("\n", 0, span.start) + 1:
        raise ValueError("Evidence start line does not match original document text")
    if span.end_line != source.count("\n", 0, span.end - 1) + 1:
        raise ValueError("Evidence end line does not match original document text")
