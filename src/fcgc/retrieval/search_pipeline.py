"""Shared provider-independent search/fetch execution and response validation."""

from time import perf_counter

from fcgc.core.interfaces import FCGRetriever
from fcgc.schemas.models import (
    ExecutionTrace,
    FetchedDocument,
    RetrievalOutput,
    RetrievalRequest,
    SearchResults,
    TraceEvent,
)


def execute_retrieval(request: RetrievalRequest, retriever: FCGRetriever) -> RetrievalOutput:
    start = perf_counter()
    search_start = perf_counter()
    results = SearchResults.model_validate(retriever.search(request.query, request.top_k))
    if results.query != request.query:
        raise ValueError("Search response query disagrees with request")
    if len(results.hits) > request.top_k:
        raise ValueError("Search response exceeds document Top-K")
    source_ids = [hit.source_id for hit in results.hits]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Search response contains duplicate source IDs")
    events = [
        TraceEvent(
            operation="search",
            duration_ms=(perf_counter() - search_start) * 1000,
            query=request.query,
        )
    ]
    documents = []
    for hit in results.hits:
        fetch_start = perf_counter()
        document = FetchedDocument.model_validate(retriever.fetch(hit.source_id))
        if (
            document.source_id != hit.source_id
            or document.source_ref != hit.source_ref
            or document.title != hit.title
        ):
            raise ValueError(f"Fetched document disagrees with search hit: {hit.source_id}")
        documents.append(document)
        events.append(
            TraceEvent(
                operation="fetch",
                duration_ms=(perf_counter() - fetch_start) * 1000,
                source_id=hit.source_id,
            )
        )
    return RetrievalOutput(
        request=request,
        search_results=results,
        documents=documents,
        trace=ExecutionTrace(events=events, total_duration_ms=(perf_counter() - start) * 1000),
    )
