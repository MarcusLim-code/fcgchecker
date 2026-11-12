"""Content-bearing, approved, ordered retrieval snapshots separate from the corpus."""

import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Literal

from fcgc.schemas.models import Contract, FetchedDocument, SearchResults


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ToolCall(Contract):
    operation: Literal["search", "fetch"]
    query: str | None = None
    top_k: int | None = None
    source_id: str | None = None
    search_result: SearchResults | None = None
    document: FetchedDocument | None = None
    error_type: str | None = None
    error: str | None = None
    duration_ms: float
    retry_count: int = 0


class RetrievalSnapshot(Contract):
    version: Literal["ordered-retrieval-v1"] = "ordered-retrieval-v1"
    approved: bool
    provider: str
    corpus_hash: str
    calls: list[ToolCall]

    def content_hash(self):
        return digest(self.model_dump(mode="json"))


class RecordingRetriever:
    def __init__(self, provider):
        self.provider = provider
        self.calls: list[ToolCall] = []

    def _invoke(self, operation, query=None, top_k=None, source_id=None):
        started = perf_counter()
        call = ToolCall(
            operation=operation, query=query, top_k=top_k, source_id=source_id, duration_ms=0
        )
        try:
            if operation == "search":
                result = SearchResults.model_validate(self.provider.search(query, top_k))
                call.search_result = result.model_copy(deep=True)
            else:
                result = FetchedDocument.model_validate(self.provider.fetch(source_id))
                call.document = result.model_copy(deep=True)
            return result
        except Exception as exc:
            call.error_type, call.error = type(exc).__name__, str(exc)
            raise
        finally:
            call.duration_ms = (perf_counter() - started) * 1000
            self.calls.append(call)

    def search(self, query, top_k):
        return self._invoke("search", query=query, top_k=top_k)

    def fetch(self, source_id):
        return self._invoke("fetch", source_id=source_id)


class OrderedReplayRetriever:
    """Never constructs a live provider. Repeated calls preserve recorded variability."""

    def __init__(self, path: Path, expected_hash: str):
        if not path.is_file():
            raise ValueError(f"Exact replay impossible: snapshot unavailable: {path}")
        self.snapshot = RetrievalSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        if not self.snapshot.approved:
            raise ValueError("Exact replay impossible: snapshot is not approved")
        if self.snapshot.content_hash() != expected_hash:
            raise ValueError("Exact replay impossible: snapshot content hash mismatch")
        self.position = 0

    def _next(self, operation, query=None, top_k=None, source_id=None):
        if self.position >= len(self.snapshot.calls):
            raise ValueError("Exact replay impossible: snapshot call sequence exhausted")
        call = self.snapshot.calls[self.position]
        if (operation, query, top_k, source_id) != (
            call.operation,
            call.query,
            call.top_k,
            call.source_id,
        ):
            raise ValueError("Exact replay impossible: retrieval request differs from snapshot")
        self.position += 1
        if call.error_type:
            error = {
                "OSError": OSError,
                "PermissionError": PermissionError,
                "FileNotFoundError": FileNotFoundError,
                "ConnectionError": ConnectionError,
                "ValueError": ValueError,
                "KeyError": KeyError,
                "RuntimeError": RuntimeError,
                "NotImplementedError": NotImplementedError,
                "TimeoutError": TimeoutError,
            }.get(call.error_type, RuntimeError)
            raise error(call.error)
        result = call.search_result if operation == "search" else call.document
        if result is None:
            raise ValueError("Exact replay impossible: snapshot lacks response content")
        return result.model_copy(deep=True)

    def search(self, query, top_k):
        return self._next("search", query=query, top_k=top_k)

    def fetch(self, source_id):
        return self._next("fetch", source_id=source_id)
