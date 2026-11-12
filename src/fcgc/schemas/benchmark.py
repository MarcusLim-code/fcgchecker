"""Versioned public benchmark and private annotation contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BenchmarkTargets(StrictModel):
    minimum_rules: int = Field(ge=1)
    development_cases: int = Field(ge=1)
    heldout_cases: int = Field(ge=1)
    near_duplicate_threshold: float = Field(gt=0, le=1)


class DocumentRecord(StrictModel):
    source_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    scope: Literal["benchmark_firmware", "decoy"]


class CaseRecord(StrictModel):
    case_id: str = Field(pattern=r"^C\d{3}$")
    path: str = Field(min_length=1)
    split: Literal["development", "heldout"]
    group: str = Field(min_length=1)
    behaviors: list[str] = Field(min_length=1)


class Coverage(StrictModel):
    rule_categories: dict[str, int]
    document_types: dict[str, int]
    code_behaviors: dict[str, int]
    splits: dict[str, int]


class BenchmarkManifest(StrictModel):
    dataset_version: str = Field(min_length=1)
    annotation_version: str = Field(min_length=1)
    targets: BenchmarkTargets
    documents: list[DocumentRecord]
    cases: list[CaseRecord]
    coverage: Coverage


class RuleRecord(StrictModel):
    rule_id: str = Field(pattern=r"^SFCG-\d{3}$")
    category: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    line: int = Field(ge=1)
    excerpt: str = Field(min_length=1)


class RuleCatalog(StrictModel):
    dataset_version: str = Field(min_length=1)
    rules: list[RuleRecord]


class SourceSpan(StrictModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class SourceEvidence(SourceSpan):
    quote: str = Field(min_length=1)


class RuleJudgement(StrictModel):
    rule_id: str = Field(pattern=r"^SFCG-\d{3}$")
    expected_status: Literal["compliant", "violation", "uncertain"]
    violation_spans: list[SourceSpan]
    source_evidence: list[SourceEvidence] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class CaseAnnotation(StrictModel):
    dataset_version: str = Field(min_length=1)
    annotation_version: str = Field(min_length=1)
    case_id: str = Field(pattern=r"^C\d{3}$")
    code_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    applicable_rules: list[RuleJudgement]
    case_rationale: str = Field(min_length=1)
    review_status: Literal["provisional", "independently_reviewed"]
