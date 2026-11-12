"""Configuration loading and provider selection."""

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fcgc.core.interfaces import ComplianceChecker, FCGRetriever
from fcgc.integrations.devin import DevinChecker
from fcgc.integrations.mock_checker import MockChecker
from fcgc.integrations.ollama_checker import LocalLLMChecker
from fcgc.integrations.placeholder_checker import PlaceholderChecker
from fcgc.integrations.synthetic_checker import SyntheticDemoChecker
from fcgc.retrieval.atlassian import AtlassianMCPRetriever
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.retrieval.local_retriever import LocalLexicalRetriever
from fcgc.retrieval.replay_retriever import ReplayRetriever
from fcgc.schemas.checking import GenerationSettings
from fcgc.schemas.models import SearchScope


class Settings(BaseModel):
    model_config = ConfigDict(
        extra="forbid", revalidate_instances="always", hide_input_in_errors=True
    )

    retriever: Literal["local", "benchmark", "replay", "atlassian_mcp", "agent_mcp"]
    checker: Literal["placeholder", "mock", "synthetic_demo", "ollama", "devin"]
    model: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    allow_network: bool = False
    allow_remote: bool = False
    checker_timeout: float = Field(default=30, gt=0)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    top_k: int = Field(default=3, ge=1)
    scope: SearchScope | None = None
    replay_path: Path | None = None

    @model_validator(mode="after")
    def validate_checker_origin(self) -> "Settings":
        if self.checker == "ollama":
            # Validate before settings can be persisted to a lock; construction makes no calls.
            LocalLLMChecker(
                self.model,
                endpoint=self.ollama_url,
                allow_network=self.allow_network,
                allow_remote=self.allow_remote,
                timeout=self.checker_timeout,
                settings=self.generation,
            )
        return self


def load_settings(path: Path | None = None) -> Settings:
    if path is None:
        raw = files("fcgc").joinpath("config", "local.toml").read_bytes()
    else:
        raw = path.read_bytes()
    settings = Settings.model_validate(tomllib.loads(raw.decode("utf-8")))
    if settings.replay_path is not None and not settings.replay_path.is_absolute():
        base = path.parent if path is not None else Path(str(files("fcgc").joinpath("config")))
        settings.replay_path = (base / settings.replay_path).resolve()
    return settings


def make_retriever(settings: Settings) -> FCGRetriever:
    if settings.retriever == "agent_mcp":
        raise ValueError(
            "agent_mcp requires an FCGC agent handoff session, not direct Python MCP access"
        )
    if settings.retriever == "local":
        return LocalLexicalRetriever(scope=settings.scope)
    if settings.retriever == "benchmark":
        return BenchmarkLexicalRetriever(scope=settings.scope)
    if settings.retriever == "replay":
        if settings.replay_path is None:
            raise ValueError("Replay provider requires replay_path")
        return ReplayRetriever(settings.replay_path, scope=settings.scope)
    return AtlassianMCPRetriever()


def make_checker(settings: Settings) -> ComplianceChecker:
    if settings.checker == "placeholder":
        return PlaceholderChecker(settings.generation)
    if settings.checker == "mock":
        return MockChecker(settings.generation)
    if settings.checker == "synthetic_demo":
        return SyntheticDemoChecker(settings.generation)
    if settings.checker == "ollama":
        return LocalLLMChecker(
            settings.model,
            endpoint=settings.ollama_url,
            allow_network=settings.allow_network,
            allow_remote=settings.allow_remote,
            timeout=settings.checker_timeout,
            settings=settings.generation,
        )
    return DevinChecker(settings.generation)
