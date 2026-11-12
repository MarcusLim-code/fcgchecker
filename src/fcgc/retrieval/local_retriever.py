"""Deterministic test retrieval backend over bundled synthetic guidelines.

This lexical score is not an emulation of Atlassian managed semantic retrieval.
"""

import json
import re
from importlib.resources import files
from pathlib import Path

from fcgc.core.files import read_source
from fcgc.schemas.models import FetchedDocument, SearchHit, SearchResults, SearchScope


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


class LocalFixtureRetriever:
    def __init__(
        self,
        corpus: Path | None = None,
        source_namespace: str = "synthetic-benchmark",
        *,
        scope_by_source: dict[str, str] | None = None,
        scope: SearchScope | None = None,
    ) -> None:
        if corpus is None:
            corpus = Path(str(files("fcgc").joinpath("fixtures", "benchmark_guidelines")))
            if scope_by_source is None:
                metadata = json.loads(
                    files("fcgc").joinpath("config", "benchmark_scopes_v1.json").read_text()
                )
                if metadata["corpus_version"] != "2.0.0":
                    raise ValueError("Unexpected synthetic benchmark corpus version")
                scope_by_source = metadata["scope_by_source"]
        self._documents: dict[str, FetchedDocument] = {}
        self.scope = scope.model_copy(deep=True) if scope is not None else None
        for resource in sorted(corpus.iterdir(), key=lambda item: item.name):
            if resource.name.endswith(".md"):
                source_id = resource.name.removesuffix(".md")
                content = read_source(resource)
                self._documents[source_id] = FetchedDocument(
                    source_id=source_id,
                    title=content.splitlines()[0].removeprefix("# "),
                    source_ref=f"fcgc://{source_namespace}/{resource.name}",
                    content=content,
                )
        self._scope_by_source = (
            dict(scope_by_source)
            if scope_by_source is not None
            else {source_id: "local_smoke" for source_id in self._documents}
        )
        if set(self._scope_by_source) != set(self._documents):
            raise ValueError("Scope metadata must cover exactly the local corpus source IDs")
        if scope is not None:
            unknown_ids = set(scope.allowed_source_ids) - set(self._documents)
            unknown_scopes = set(scope.allowed_scopes) - set(self._scope_by_source.values())
            if unknown_ids or unknown_scopes:
                raise ValueError("Search scope contains unknown source IDs or scopes")

    def _visible(self, source_id: str) -> bool:
        if self.scope is None:
            return True
        if self.scope.allowed_scopes and (
            self._scope_by_source[source_id] not in self.scope.allowed_scopes
        ):
            return False
        return not self.scope.allowed_source_ids or source_id in self.scope.allowed_source_ids

    def search(self, query: str, top_k: int) -> SearchResults:
        if not query.strip():
            raise ValueError("Query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        terms = _tokens(query)
        ranked = []
        for document in self._documents.values():
            if not self._visible(document.source_id):
                continue
            score = len(terms & _tokens(document.title + " " + document.content))
            if score:
                ranked.append(
                    SearchHit(
                        source_id=document.source_id,
                        title=document.title,
                        source_ref=document.source_ref,
                        score=score,
                    )
                )
        ranked.sort(key=lambda hit: (-hit.score, hit.source_id))
        return SearchResults(query=query, hits=ranked[:top_k], scope=self.scope)

    def fetch(self, source_id: str) -> FetchedDocument:
        if source_id in self._documents and not self._visible(source_id):
            raise PermissionError(f"Guideline source ID is outside search scope: {source_id}")
        try:
            return self._documents[source_id].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError(f"Unknown guideline source ID: {source_id}") from exc


class LocalLexicalRetriever(LocalFixtureRetriever):
    """Legacy Stage 1 smoke corpus; new local research runs use LocalFixtureRetriever."""

    def __init__(self, scope: SearchScope | None = None) -> None:
        corpus = Path(str(files("fcgc").joinpath("fixtures", "guidelines")))
        super().__init__(corpus, source_namespace="synthetic-guidelines", scope=scope)
