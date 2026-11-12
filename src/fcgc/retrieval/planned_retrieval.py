"""P1 feature-aware retrieval with explicit extraction and planning costs."""

from time import perf_counter

from fcgc.checking.feature_extractor import extract_features
from fcgc.core.interfaces import FCGRetriever
from fcgc.retrieval.query_planner import FCGQueryPlanner
from fcgc.retrieval.search_pipeline import execute_retrieval
from fcgc.schemas.models import (
    FirmwareInput,
    RetrievalRequest,
)
from fcgc.schemas.stage3 import P1Run


def retrieve_p1(
    firmware: FirmwareInput,
    retriever: FCGRetriever,
    top_k: int = 3,
    planner: FCGQueryPlanner | None = None,
) -> P1Run:
    extraction_start = perf_counter()
    features = extract_features(firmware)
    extraction_ms = (perf_counter() - extraction_start) * 1000
    planner = planner or FCGQueryPlanner()
    planning_start = perf_counter()
    plan = planner.plan(features, document_top_k=top_k)
    planning_ms = (perf_counter() - planning_start) * 1000

    request = RetrievalRequest(
        firmware=firmware,
        strategy="p1",
        query=plan.query,
        query_template_version=plan.template_version,
        top_k=top_k,
    )
    retrieval = execute_retrieval(request, retriever)
    return P1Run(
        features=features,
        plan=plan,
        feature_extraction_ms=extraction_ms,
        query_planning_ms=planning_ms,
        retrieval=retrieval,
    )
