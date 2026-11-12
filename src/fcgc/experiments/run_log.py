"""Append a compact, reproducible summary of one retrieval run."""

import json
from pathlib import Path

from fcgc.schemas.models import RetrievalOutput
from fcgc.schemas.stage3 import QueryPlan


def append_run_log(path: Path, output: RetrievalOutput, plan: QueryPlan | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "case_id": output.request.firmware.case_id,
        "firmware_sha256": output.request.firmware.sha256,
        "strategy": output.request.strategy,
        "query": output.request.query,
        "document_top_k": output.request.top_k,
        "search_scope": (
            output.search_results.scope.model_dump(mode="json")
            if output.search_results.scope is not None
            else None
        ),
        "source_ids": [hit.source_id for hit in output.search_results.hits],
        "ranked_results": [hit.model_dump(mode="json") for hit in output.search_results.hits],
        "fetched_documents": [document.model_dump(mode="json") for document in output.documents],
        "mapping_version": plan.mapping_version if plan else None,
        "query_template_version": output.request.query_template_version,
        "events": [event.model_dump(mode="json") for event in output.trace.events],
        "total_duration_ms": output.trace.total_duration_ms,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
