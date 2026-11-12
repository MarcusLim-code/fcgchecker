"""Stable provider interfaces."""

from typing import Protocol

from fcgc.schemas.checking import FrozenCheckingTask
from fcgc.schemas.models import (
    CheckerRequest,
    CheckerResult,
    FetchedDocument,
    SearchResults,
)


class FCGRetriever(Protocol):
    def search(self, query: str, top_k: int) -> SearchResults: ...

    def fetch(self, source_id: str) -> FetchedDocument: ...


class ComplianceChecker(Protocol):
    def check(self, request: CheckerRequest | FrozenCheckingTask) -> CheckerResult: ...
