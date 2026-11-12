"""Provider-independent requests, responses, and trace records."""

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    # Provider boundaries must also reject invalid fields on mutated model instances.
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")


class FirmwareInput(Contract):
    case_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    content: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_matches(self) -> "FirmwareInput":
        if hashlib.sha256(self.content.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("Firmware hash mismatch")
        return self


class RetrievalRequest(Contract):
    firmware: FirmwareInput
    strategy: str = Field(pattern=r"^(b0|p1)$")
    query: str = Field(min_length=1)
    query_template_version: str = Field(min_length=1)
    top_k: int = Field(ge=1)


class SearchHit(Contract):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    # Local lexical scores are integers. Managed rankings may expose no score.
    score: int | None = Field(default=None, ge=0)


class SearchScope(Contract):
    """Provider-side visibility filter; empty lists mean no restriction."""

    allowed_scopes: list[str] = Field(default_factory=list)
    allowed_source_ids: list[str] = Field(default_factory=list)


class SearchResults(Contract):
    query: str = Field(min_length=1)
    hits: list[SearchHit]
    scope: SearchScope | None = None


class FetchedDocument(Contract):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    content: str = Field(min_length=1)
    document_version: str | None = None


class TraceEvent(Contract):
    operation: str = Field(min_length=1)
    duration_ms: float = Field(ge=0)
    query: str | None = None
    source_id: str | None = None


class ExecutionTrace(Contract):
    events: list[TraceEvent]
    total_duration_ms: float = Field(ge=0)


class RetrievalOutput(Contract):
    request: RetrievalRequest
    search_results: SearchResults
    documents: list[FetchedDocument]
    trace: ExecutionTrace


class CheckerStatus(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    EVALUATED = "evaluated"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class CheckerRequest(Contract):
    firmware: FirmwareInput
    retrieval: RetrievalOutput


class CheckerResult(Contract):
    status: CheckerStatus
    reason: str = Field(min_length=1)
    retrieval: RetrievalOutput | None = None
