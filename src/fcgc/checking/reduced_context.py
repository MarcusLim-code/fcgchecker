"""P2 = unchanged P1 retrieval followed by source-preserving rule reduction."""

from time import perf_counter

from fcgc.checking.context_packer import (
    TOKENIZER_VERSION,
    estimate_tokens,
    pack_checker_input,
    render_full_document_input,
)
from fcgc.checking.context_reducer import RuleContextReducer
from fcgc.checking.rule_extractor import extract_documents
from fcgc.core.interfaces import FCGRetriever
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.schemas.models import FirmwareInput
from fcgc.schemas.stage6 import ContextMetrics, P2Run, UnresolvedSection


def run_p2(
    firmware: FirmwareInput,
    retriever: FCGRetriever,
    *,
    top_k: int = 3,
    reducer: RuleContextReducer | None = None,
    token_budget: int | None = None,
) -> P2Run:
    """Use the P1 search/fetch output exactly once; no adaptive retrieval or checker call."""
    p1 = retrieve_p1(firmware, retriever, top_k=top_k)
    reducer = reducer or RuleContextReducer()
    budget = token_budget if token_budget is not None else reducer.config.token_budget
    if budget < 1:
        raise ValueError("P2 token budget must be positive")

    reduction_start = perf_counter()
    extractions = extract_documents(p1.retrieval.documents)
    candidates = [rule for extraction in extractions for rule in extraction.rules]
    selection = reducer.reduce(firmware, p1.features, candidates, p1.retrieval.documents)
    unresolved_sections = [
        UnresolvedSection(
            source_id=extraction.normalized.document.source_id,
            source_ref=extraction.normalized.document.source_ref,
            span=fragment.span,
            reason="Segmentation could not establish an independent normative rule.",
        )
        for extraction in extractions
        for fragment in extraction.review_sections
    ]
    reduction_ms = (perf_counter() - reduction_start) * 1000

    packing_start = perf_counter()
    request, required_tokens = pack_checker_input(
        firmware,
        selection,
        budget_tokens=budget,
        instructions_version=reducer.config.instructions_version,
        unresolved_sections=unresolved_sections,
    )
    packing_ms = (perf_counter() - packing_start) * 1000
    p1_tokens = estimate_tokens(render_full_document_input(firmware, p1.retrieval.documents))
    p2_tokens = request.estimated_tokens if request is not None else None
    savings = p1_tokens - p2_tokens if p2_tokens is not None else None
    metrics = ContextMetrics(
        tokenizer_version=TOKENIZER_VERSION,
        retrieval_context_tokens=sum(
            estimate_tokens(document.content) for document in p1.retrieval.documents
        ),
        p1_full_document_input_tokens=p1_tokens,
        p2_checker_input_tokens=p2_tokens,
        required_p2_input_tokens=required_tokens,
        token_savings=savings,
        token_savings_percent=(
            100 * savings / p1_tokens if savings is not None and p1_tokens else None
        ),
        candidate_rule_count=len(selection.candidate_rules),
        selected_rule_count=len(selection.selected_ids),
        excluded_rule_count=len(selection.excluded_ids),
        uncertainty_preserved_count=sum(
            decision.preserved_for_uncertainty for decision in selection.decisions
        ),
        context_budget_tokens=budget,
        budget_failure=request is None,
        reduction_ms=reduction_ms,
        packing_ms=packing_ms,
    )
    return P2Run(
        p1=p1,
        selection=selection,
        unresolved_sections=unresolved_sections,
        checker_request=request,
        status="budget_exceeded" if request is None else request.status,
        metrics=metrics,
    )
