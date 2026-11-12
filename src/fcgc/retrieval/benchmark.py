"""Backward-compatible Stage 2 benchmark retriever name."""

from fcgc.retrieval.local_retriever import LocalFixtureRetriever
from fcgc.schemas.models import SearchScope


class BenchmarkLexicalRetriever(LocalFixtureRetriever):
    def __init__(self, scope: SearchScope | None = None) -> None:
        super().__init__(scope=scope)
