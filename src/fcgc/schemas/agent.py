"""Versioned, bounded host-to-Python handoff. No MCP SDK or credentials are used."""

from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, StrictInt, model_validator

from fcgc.core.transport_safety import credential_transport_text, credential_uri
from fcgc.schemas.checking import GenerationSettings, ModelFindings
from fcgc.schemas.models import Contract, FetchedDocument, SearchHit, SearchResults
from fcgc.schemas.stage3 import FeatureReport
from fcgc.schemas.stage9 import ArtifactLock, RunTrace

SHORT = 512


class HostContext(Contract):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    version: Literal["fcgc-host-v1"] = "fcgc-host-v1"
    runtime: Literal["devin_cli", "devin_cloud", "devin_desktop", "other"]
    runtime_version: str | None = Field(default=None, max_length=SHORT)
    environment_id: str = Field(min_length=1, max_length=SHORT)
    provider_id: str = Field(min_length=1, max_length=SHORT)
    permission_scope: str = Field(min_length=1, max_length=SHORT)
    approved_workspace: Path
    search_tool: str = Field(min_length=1, max_length=SHORT)
    fetch_tool: str = Field(min_length=1, max_length=SHORT)
    search_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fetch_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    origin: Literal["host_observed", "synthetic_contract_test"] = "host_observed"
    # Configuration/discovery is not proof of authenticated access.
    connection_status: Literal["connected_but_unverified", "unavailable", "not_configured"]


class RetrievalQuery(Contract):
    query_id: str
    text: str = Field(min_length=1, max_length=16000)
    document_top_k: int = Field(ge=1, le=100)
    template_version: str
    search_number: int = Field(ge=1)


class AgentAction(Contract):
    action_id: str
    session_id: str
    context_hash: str
    operation: Literal["search", "fetch", "check"]
    tool_name: str | None = None
    query: RetrievalQuery | None = None
    source: SearchHit | None = None
    evidence_hash: str | None = None
    prompt_hash: str | None = None


class ToolError(Contract):
    model_config = ConfigDict(hide_input_in_errors=True)
    code: Literal["authentication", "permission", "timeout", "unavailable", "invalid_response"]
    # No raw headers, transport dumps or credentials in error messages.
    message: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def no_transport_credentials(self):
        if credential_transport_text(self.message):
            raise ValueError("Tool errors must omit credentials and transport headers")
        return self


class ResultMetadata(Contract):
    source_id: str = Field(min_length=1, max_length=SHORT)
    content_type: str | None = Field(default=None, max_length=SHORT)
    space_id: str | None = Field(default=None, max_length=SHORT)
    version: str | None = Field(default=None, max_length=SHORT)
    provider_score: float | None = Field(default=None, allow_inf_nan=False)
    score_description: str | None = Field(default=None, max_length=SHORT)


class AgentToolResult(Contract):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    version: Literal["fcgc-tool-result-v1"] = "fcgc-tool-result-v1"
    session_id: str
    action_id: str
    context_hash: str
    provider_id: str = Field(min_length=1, max_length=SHORT)
    tool_name: str = Field(min_length=1, max_length=SHORT)
    tool_call_id: str | None = Field(default=None, min_length=1, max_length=SHORT)
    retrieved_at: datetime
    duration_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    complete: bool = True
    search: SearchResults | None = None
    document: FetchedDocument | None = None
    error: ToolError | None = None
    metadata: list[ResultMetadata] = Field(default_factory=list, max_length=100)
    content_format: Literal["markdown", "plain_text"] = "markdown"
    upstream_response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def payload_and_time(self):
        if sum(x is not None for x in (self.search, self.document, self.error)) != 1:
            raise ValueError("Provide exactly one search response, fetched document or tool error")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at needs a timezone")
        if self.document and len(self.document.content.encode()) > 1_000_000:
            raise ValueError("Handoff document exceeds 1 MB")
        if self.search and len(self.search.hits) > 100:
            raise ValueError("Handoff has too many references")
        return self


class AgentJudgment(Contract):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    version: Literal["fcgc-judgment-v1"] = "fcgc-judgment-v1"
    session_id: str
    action_id: str
    context_hash: str
    evidence_hash: str
    prompt_hash: str
    model_identifier: str | None = Field(default=None, max_length=SHORT)
    model_details: str | None = Field(default=None, max_length=2000)
    reported_settings: GenerationSettings | None = None
    input_tokens: StrictInt | None = Field(default=None, ge=0)
    output_tokens: StrictInt | None = Field(default=None, ge=0)
    findings: ModelFindings


class CompletedCall(Contract):
    action: AgentAction
    result: AgentToolResult


class FunctionTarget(Contract):
    name: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class AgentSession(Contract):
    version: Literal["fcgc-agent-session-v1"] = "fcgc-agent-session-v1"
    session_id: str
    source_path: Path
    source_hash: str
    features: FeatureReport | None = None
    feature_role: Literal["diagnostic_only", "runtime_equivalent"] = "runtime_equivalent"
    mode: Literal["local", "wd"]
    intent: Literal["check", "rules"]
    strategy: Literal["b0", "p1", "p2", "p3"]
    started_at: datetime
    deadline: datetime
    lock: ArtifactLock
    host: HostContext | None = None
    host_hash: str
    orchestration_version: Literal["fcg-native-v1"] = "fcg-native-v1"
    orchestration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target: FunctionTarget | None = None
    features_scope: Literal["whole_file_conservative"] = "whole_file_conservative"
    max_search_calls: int = Field(ge=1)
    max_fetch_calls: int = Field(ge=1)
    max_candidate_sources: int = Field(ge=1)
    calls: list[CompletedCall] = Field(default_factory=list)
    pending: AgentAction | None = None
    trace: RunTrace | None = None
    status: Literal["retrieval_required", "checking_required", "complete", "error"]
    warnings: list[str] = Field(default_factory=list)
    workflow_ms: float = 0
    backend_processing_ms: float = 0
    judgment: AgentJudgment | None = None


def validate_source_uri(source_ref: str) -> None:
    try:
        parsed = urlsplit(source_ref)
    except ValueError as exc:
        raise ValueError("Invalid WD source URI") from exc
    if parsed.scheme != "https" or not parsed.hostname or credential_uri(source_ref):
        raise ValueError("WD source references must be HTTPS URIs without credentials")
