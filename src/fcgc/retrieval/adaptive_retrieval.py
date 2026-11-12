"""Observable risk gate and bounded fallback; no ranking-confidence assumptions."""

import tomllib
from importlib.resources import files
from pathlib import Path
from time import perf_counter

from pydantic import Field

from fcgc.checking.context_packer import estimate_tokens, pack_checker_input
from fcgc.checking.context_reducer import RuleContextReducer
from fcgc.checking.feature_extractor import extract_features
from fcgc.checking.rule_extractor import extract_documents
from fcgc.core.interfaces import FCGRetriever
from fcgc.retrieval.query_planner import FCGQueryPlanner
from fcgc.schemas.models import Contract, FetchedDocument, FirmwareInput, SearchResults
from fcgc.schemas.stage3 import CodeFeatures
from fcgc.schemas.stage6 import EvidenceSelection, UnresolvedSection
from fcgc.schemas.stage7 import P3Metrics, P3Run, RetrievalAttempt, SufficiencyAssessment


class FallbackConfig(Contract):
    version: str
    template_version: str
    max_rounds: int = Field(ge=1)
    max_search_calls: int = Field(ge=1)
    max_fetch_calls: int = Field(ge=1)
    max_candidate_sources: int = Field(ge=1)
    context_token_budget: int = Field(ge=1)
    max_elapsed_seconds: float = Field(gt=0)
    top_k: int = Field(ge=1)
    max_duplicate_fraction: float = Field(ge=0, le=1)
    general_categories: list[str]
    trigger_on_ambiguity: bool
    targeted_template: str
    broadened_template: str


def load_fallback_config(path: Path | None = None) -> FallbackConfig:
    raw = (
        path.read_bytes()
        if path
        else files("fcgc").joinpath("config", "p3_fallback_v1.toml").read_bytes()
    )
    return FallbackConfig.model_validate(tomllib.loads(raw.decode("utf-8")))


def assess_sufficiency(
    features: CodeFeatures,
    selection: EvidenceSelection,
    reducer: RuleContextReducer,
    config: FallbackConfig,
    *,
    unresolved_sections: int = 0,
    errors: list[str] | None = None,
) -> SufficiencyAssessment:
    """Lexical category evidence indicates risk only, never retrieval completeness."""
    selected = [r for r in selection.candidate_rules if r.evidence_id in selection.selected_ids]
    mappings = {category.feature: category.terms for category in reducer.config.categories}
    expected = {category.name for category in features.inferred_categories} - {"general_firmware"}
    general = set(config.general_categories)

    def coverage(categories: set[str]) -> dict[str, list[str]]:
        return {
            category: [
                rule.evidence_id
                for rule in selected
                if any(
                    term.lower() in rule.normative_statement.lower()
                    for term in mappings.get(category, [])
                )
            ]
            for category in sorted(categories)
        }

    operations = coverage(expected)
    generals = coverage(general)
    missing = sorted({key for key, ids in {**operations, **generals}.items() if not ids})
    ambiguous = [
        r.evidence_id
        for r in selected
        if r.ambiguity_status == "review_required" or r.conditions or r.exceptions
    ]
    duplicate_fraction = (
        sum(rule.duplicate_of is not None for rule in selection.candidate_rules)
        / len(selection.candidate_rules)
        if selection.candidate_rules
        else 0.0
    )
    excessive = duplicate_fraction > config.max_duplicate_fraction
    reasons = []
    if missing:
        reasons.append("missing_expected_categories")
    if not selected:
        reasons.append("empty_or_weak_normative_evidence")
    if selection.unresolved_dependencies:
        reasons.append("unresolved_dependencies")
    if config.trigger_on_ambiguity and ambiguous:
        reasons.append("ambiguous_applicability")
    if unresolved_sections:
        reasons.append("unsegmented_source_sections")
    if excessive:
        reasons.append("excessive_duplication")
    if errors:
        reasons.append("retrieval_errors")
    return SufficiencyAssessment(
        status="insufficient_evidence" if reasons else "sufficient_signals",
        operation_category_coverage=operations,
        general_category_coverage=generals,
        normative_rule_count=len(selected),
        unresolved_dependencies=selection.unresolved_dependencies,
        ambiguous_applicability=ambiguous,
        empty_or_weak_results=not selected,
        duplicate_fraction=duplicate_fraction,
        excessive_duplication=excessive,
        missing_expected_categories=missing,
        reasons=reasons,
    )


def fallback_queries(assessment, features, reducer, config) -> list[str]:
    mappings = {category.feature: category.terms for category in reducer.config.categories}
    concepts = [
        " ".join(mappings.get(category, [category.replace("_", " ")]))
        for category in assessment.missing_expected_categories
    ]
    concepts.extend(target.split(":", 1)[-1] for target in assessment.unresolved_dependencies)
    if not concepts:
        concepts = ["applicability conditions exceptions shared definitions"]
    return [
        " ".join(
            template.format(
                concepts=concept,
                components=" ".join(features.component_hints),
            ).split()
        )
        for template in (config.targeted_template, config.broadened_template)
        for concept in concepts
    ]


def run_p3(
    firmware: FirmwareInput,
    retriever: FCGRetriever,
    *,
    config: FallbackConfig | None = None,
    reducer: RuleContextReducer | None = None,
) -> P3Run:
    config = config or load_fallback_config()
    reducer = reducer or RuleContextReducer()
    started = perf_counter()
    features = extract_features(firmware)
    plan = FCGQueryPlanner().plan(features, config.top_k)
    documents: dict[str, FetchedDocument] = {}
    candidates: set[str] = set()
    fetched_attempts: set[str] = set()
    queries: set[str] = set()
    attempts: list[RetrievalAttempt] = []
    errors: list[str] = []
    search_calls = fetch_calls = 0
    scope = None
    scope_seen = False
    known_refs: dict[str, str] = {}

    def elapsed() -> float:
        return perf_counter() - started

    def process():
        extractions = extract_documents(list(documents.values()))
        selection = reducer.reduce(
            firmware,
            features,
            [r for ex in extractions for r in ex.rules],
            list(documents.values()),
        )
        sections = [
            UnresolvedSection(
                source_id=ex.normalized.document.source_id,
                source_ref=ex.normalized.document.source_ref,
                span=fragment.span,
                reason="Unresolved segmentation",
            )
            for ex in extractions
            for fragment in ex.review_sections
        ]
        assessment = assess_sufficiency(
            features,
            selection,
            reducer,
            config,
            unresolved_sections=len(sections),
            errors=errors,
        )
        request, needed = pack_checker_input(
            firmware,
            selection,
            budget_tokens=config.context_token_budget,
            instructions_version=reducer.config.instructions_version,
            unresolved_sections=sections,
            warnings=(
                ["Sufficiency gate: " + ", ".join(assessment.reasons)] if assessment.reasons else []
            ),
        )
        if request:
            request = request.model_copy(
                update={
                    "strategy": "p3",
                    "status": "incomplete_context" if assessment.reasons else request.status,
                }
            )
        else:
            assessment = assessment.model_copy(
                update={
                    "status": "insufficient_evidence",
                    "reasons": [*assessment.reasons, "context_token_budget"],
                }
            )
        return selection, assessment, request, needed

    def retrieve(query: str, number: int, triggers: list[str], old_rules: set[str]):
        nonlocal search_calls, fetch_calls, scope, scope_seen
        before = perf_counter()
        local_errors = []
        fetched = []
        results = None
        queries.add(" ".join(query.casefold().split()))
        local_searches = 0
        local_fetches = 0
        try:
            if elapsed() >= config.max_elapsed_seconds:
                raise TimeoutError("Elapsed-time limit before search")
            search_calls += 1
            local_searches = 1
            k = min(config.top_k, config.max_candidate_sources - len(candidates))
            results = SearchResults.model_validate(retriever.search(query, k))
            if results.query != query or len(results.hits) > k:
                raise ValueError("Search response query or Top-K mismatch")
            if scope_seen and results.scope != scope:
                raise ValueError("Search scope changed during fallback")
            scope, scope_seen = results.scope, True
            for hit in results.hits:
                if hit.source_id in known_refs and known_refs[hit.source_id] != hit.source_ref:
                    raise ValueError("Source identity changed during fallback")
            candidates.update(hit.source_id for hit in results.hits)
            # Provider ranking is preserved; duplicate references are fetched once.
            for hit in results.hits:
                if hit.source_id in known_refs and known_refs[hit.source_id] != hit.source_ref:
                    raise ValueError("Source identity changed during fallback")
                known_refs[hit.source_id] = hit.source_ref
                if hit.source_id in fetched_attempts:
                    continue
                if fetch_calls >= config.max_fetch_calls or elapsed() >= config.max_elapsed_seconds:
                    break
                fetched_attempts.add(hit.source_id)
                fetch_calls += 1
                local_fetches += 1
                try:
                    document = FetchedDocument.model_validate(retriever.fetch(hit.source_id))
                    if (document.source_id, document.source_ref, document.title) != (
                        hit.source_id,
                        hit.source_ref,
                        hit.title,
                    ):
                        raise ValueError("Fetch response differs from ranked reference")
                    documents[document.source_id] = document
                    fetched.append(document.source_id)
                except (OSError, LookupError, ValueError, RuntimeError, NotImplementedError) as exc:
                    local_errors.append(f"fetch:{hit.source_id}:{type(exc).__name__}:{exc}")
        except (OSError, LookupError, ValueError, RuntimeError, NotImplementedError) as exc:
            local_errors.append(f"search:{type(exc).__name__}:{exc}")
        errors.extend(local_errors)
        selection, assessment, request, needed = process()
        attempts.append(
            RetrievalAttempt(
                round_number=number,
                query=query,
                template_version=plan.template_version if number == 1 else config.template_version,
                trigger_reasons=triggers,
                results=results,
                fetched_source_ids=fetched,
                new_rule_ids=[
                    r.explicit_rule_id or r.evidence_id
                    for r in selection.candidate_rules
                    if r.evidence_id not in old_rules
                ],
                errors=local_errors,
                search_calls=local_searches,
                fetch_calls=local_fetches,
                duration_ms=(perf_counter() - before) * 1000,
            )
        )
        return selection, assessment, request, needed

    selection, assessment, request, needed = retrieve(plan.query, 1, [], set())
    initial = assessment.model_copy(deep=True)
    initial_tokens = sum(estimate_tokens(d.content) for d in documents.values())
    initial_needed = needed
    initial_ms = elapsed() * 1000
    initial_fetches = fetch_calls
    stop = (
        "initial_evidence_sufficient"
        if assessment.status == "sufficient_signals"
        else "retrieval_round_limit"
    )
    for number in range(2, config.max_rounds + 1):
        if assessment.status == "sufficient_signals":
            stop = "sufficiency_signals_recovered" if number > 2 else stop
            break
        if request is None:
            stop = "context_token_budget"
            break
        if elapsed() >= config.max_elapsed_seconds:
            stop = "elapsed_time_limit"
            break
        if search_calls >= config.max_search_calls:
            stop = "search_call_budget"
            break
        if fetch_calls >= config.max_fetch_calls:
            stop = "fetch_call_budget"
            break
        if len(candidates) >= config.max_candidate_sources:
            stop = "candidate_source_limit"
            break
        query = next(
            (
                q
                for q in fallback_queries(assessment, features, reducer, config)
                if " ".join(q.casefold().split()) not in queries
            ),
            None,
        )
        if query is None:
            stop = "no_unique_fallback_query"
            break
        old_rules = {r.evidence_id for r in selection.candidate_rules}
        selection, assessment, request, needed = retrieve(
            query, number, assessment.reasons, old_rules
        )
        stop = "retrieval_round_limit"
    if assessment.status == "sufficient_signals" and request is not None:
        stop = (
            "initial_evidence_sufficient" if len(attempts) == 1 else "sufficiency_signals_recovered"
        )
    elif request is None:
        stop = "context_token_budget"
    final_tokens = sum(estimate_tokens(d.content) for d in documents.values())
    total_ms = elapsed() * 1000
    recovered = sorted(
        set(initial.missing_expected_categories) - set(assessment.missing_expected_categories)
    )
    resolved = sorted(
        set(initial.unresolved_dependencies) - set(assessment.unresolved_dependencies)
    )
    return P3Run(
        config_version=config.version,
        features=features,
        initial_plan=plan,
        initial_assessment=initial,
        final_assessment=assessment,
        attempts=attempts,
        documents=list(documents.values()),
        selection=selection,
        checker_request=request,
        status=(
            "sufficient_signals"
            if assessment.status == "sufficient_signals" and request
            else "insufficient_evidence"
        ),
        stop_reason=stop,
        metrics=P3Metrics(
            search_calls=search_calls,
            fetch_calls=fetch_calls,
            additional_search_calls=search_calls - attempts[0].search_calls,
            additional_fetch_calls=fetch_calls - initial_fetches,
            candidate_sources=len(candidates),
            initial_retrieval_tokens=initial_tokens,
            final_retrieval_tokens=final_tokens,
            additional_retrieval_tokens=final_tokens - initial_tokens,
            initial_required_input_tokens=initial_needed,
            final_required_input_tokens=needed,
            checker_input_token_delta=needed - initial_needed,
            initial_duration_ms=initial_ms,
            additional_duration_ms=total_ms - initial_ms,
            total_duration_ms=total_ms,
            recovered_categories=recovered,
            resolved_dependencies=resolved,
            warning_signals_recovered=bool(recovered or resolved),
        ),
    )
