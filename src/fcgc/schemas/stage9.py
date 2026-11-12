"""Experiment configuration locking and trace contracts."""

from typing import Literal

from pydantic import Field

from fcgc.checking.context_reducer import ReductionConfig
from fcgc.config import Settings
from fcgc.experiments.snapshots import ToolCall
from fcgc.retrieval.adaptive_retrieval import FallbackConfig
from fcgc.schemas.checking import CheckingResult, FrozenCheckingTask
from fcgc.schemas.models import Contract, FirmwareInput, RetrievalOutput
from fcgc.schemas.rules import RuleExtraction
from fcgc.schemas.stage3 import FeatureReport, P1Run
from fcgc.schemas.stage6 import P2Run
from fcgc.schemas.stage7 import P3Run


class PipelineConfig(Contract):
    seed: int = 0
    retrieval: Settings
    checkers: list[Settings] = Field(min_length=1)
    expected_skill_version: str
    expected_prompt_version: str
    document_top_k: int = Field(default=3, ge=1)
    reference_top_k: int = Field(default=8, ge=1)
    context_token_budget: int = Field(default=12000, ge=1)
    snapshots_approved: bool = False
    reduction: ReductionConfig
    fallback: FallbackConfig


class ArtifactLock(Contract):
    config: PipelineConfig
    code_version: str
    code_hash: str
    instruction_hash: str


class ExperimentConfig(PipelineConfig):
    dataset_id: Literal["fcgc-synthetic-v2"]
    dataset_root: str
    split: Literal["development", "heldout"]
    strategies: list[Literal["b0", "p1", "p2", "p3", "r"]] = Field(min_length=1)
    case_ids: list[str] = Field(default_factory=list)
    repetitions: int = Field(default=3, ge=1)
    shuffle_order: bool = True
    output_directory: str


class ExperimentLock(Contract):
    config: ExperimentConfig
    code_version: str
    code_hash: str
    instruction_hash: str
    dataset_version: str
    annotation_version: str
    manifest_hash: str
    corpus_hash: str
    case_hashes: dict[str, str]
    controls_not_verified: list[str]


class StageError(Contract):
    stage: str
    error_type: str
    message: str


class StageLatency(Contract):
    stage: str
    duration_ms: float


class RunTrace(Contract):
    version: Literal["experiment-run-v1"] = "experiment-run-v1"
    run_id: str
    timestamp_utc: str
    lock_hash: str
    strategy: str
    repetition: int
    seed: int
    firmware: FirmwareInput
    features: FeatureReport | None = None
    feature_role: str = "runtime"
    pipeline: RetrievalOutput | P1Run | P2Run | P3Run | None = None
    segmented_documents: list[RuleExtraction] = Field(default_factory=list)
    selected_ids: list[str] = Field(default_factory=list)
    selection_policy: str = "unavailable"
    task: FrozenCheckingTask | None = None
    packed_checker_input: str | None = None
    checker_results: list[CheckingResult] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    stage_latencies: list[StageLatency] = Field(default_factory=list)
    end_to_end_ms: float = 0
    retrieval_context_tokens: int = 0
    checker_input_estimated_tokens: int = 0
    token_estimation_method: str = "regex-word-punctuation-v1"
    source_content_hashes: dict[str, str] = Field(default_factory=dict)
    snapshot_path: str | None = None
    snapshot_hash: str | None = None
    replay_of: str | None = None
    traffic_kind: str
    status: Literal["started", "finished", "failed"] = "started"
    incomplete_stages: list[str] = Field(default_factory=list)
    errors: list[StageError] = Field(default_factory=list)
