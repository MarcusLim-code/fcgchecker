"""Exact offline replay of recorded synthetic search/fetch responses."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from fcgc.core.interfaces import FCGRetriever
from fcgc.schemas.models import Contract, FetchedDocument, SearchResults, SearchScope


class ReplaySearch(Contract):
    query: str = Field(min_length=1)
    top_k: int = Field(ge=1)
    results: SearchResults


class ReplayFixture(Contract):
    version: Literal["replay-v1"]
    corpus_version: str = Field(min_length=1)
    scope: SearchScope | None = None
    documents: list[FetchedDocument]
    searches: list[ReplaySearch]

    @model_validator(mode="after")
    def validate_references(self) -> "ReplayFixture":
        documents = {document.source_id: document for document in self.documents}
        if len(documents) != len(self.documents):
            raise ValueError("Replay fixture has duplicate document source IDs")
        keys: set[tuple[str, int]] = set()
        for record in self.searches:
            key = (record.query, record.top_k)
            if key in keys:
                raise ValueError("Replay fixture has duplicate search requests")
            keys.add(key)
            if record.results.query != record.query or record.results.scope != self.scope:
                raise ValueError("Replay search query or scope differs from its request")
            if len(record.results.hits) > record.top_k:
                raise ValueError("Replay search exceeds document Top-K")
            seen: set[str] = set()
            for hit in record.results.hits:
                if hit.source_id in seen:
                    raise ValueError("Replay search contains duplicate source IDs")
                seen.add(hit.source_id)
                document = documents.get(hit.source_id)
                if document is None:
                    raise ValueError(f"Replay search references missing source: {hit.source_id}")
                if document.source_ref != hit.source_ref or document.title != hit.title:
                    raise ValueError(f"Replay search/fetch metadata mismatch: {hit.source_id}")
        return self


class ReplayRetriever:
    """Serve only exact recorded queries and their fetched source documents."""

    def __init__(self, path: Path, *, scope: SearchScope | None = None) -> None:
        fixture = ReplayFixture.model_validate_json(path.read_text(encoding="utf-8"))
        if scope != fixture.scope:
            raise ValueError("Requested search scope differs from replay fixture scope")
        self.fixture = fixture
        self._documents = {document.source_id: document for document in fixture.documents}
        self._searches = {
            (record.query, record.top_k): record.results for record in fixture.searches
        }
        self._fetchable: set[str] = {
            hit.source_id for record in fixture.searches for hit in record.results.hits
        }

    def search(self, query: str, top_k: int) -> SearchResults:
        if not query.strip() or top_k < 1:
            raise ValueError("Replay search requires a nonempty query and positive top_k")
        try:
            return self._searches[(query, top_k)].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError("No exact replay for query and document Top-K") from exc

    def fetch(self, source_id: str) -> FetchedDocument:
        if source_id not in self._fetchable:
            raise KeyError(f"Source ID was not returned by a replay search: {source_id}")
        return self._documents[source_id].model_copy(deep=True)


def capture_replay(
    path: Path,
    retriever: FCGRetriever,
    queries: list[tuple[str, int]],
    *,
    corpus_version: str,
    scope: SearchScope | None = None,
) -> ReplayFixture:
    """Capture public search/fetch evidence; never reads benchmark annotations."""
    records = []
    documents: dict[str, FetchedDocument] = {}
    for query, top_k in queries:
        results = SearchResults.model_validate(retriever.search(query, top_k))
        records.append(ReplaySearch(query=query, top_k=top_k, results=results))
        for hit in results.hits:
            documents[hit.source_id] = FetchedDocument.model_validate(
                retriever.fetch(hit.source_id)
            )
    fixture = ReplayFixture(
        version="replay-v1",
        corpus_version=corpus_version,
        scope=scope,
        documents=list(documents.values()),
        searches=records,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return fixture
