import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from fcgc.checking.context_packer import estimate_tokens, pack_checker_input
from fcgc.checking.context_reducer import RuleContextReducer
from fcgc.checking.feature_extractor import extract_features
from fcgc.checking.reduced_context import run_p2
from fcgc.checking.rule_extractor import extract_documents
from fcgc.cli import app
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.schemas.models import FetchedDocument, FirmwareInput, SearchHit, SearchResults
from fcgc.schemas.stage6 import EvidenceSelection, PackedEvidence


def _firmware(
    code: str = "int flash_write(void); int app(void) { return flash_write(); }\n",
) -> FirmwareInput:
    return FirmwareInput(
        case_id="stage6",
        source_name="stage6.c",
        content=code,
        sha256=hashlib.sha256(code.encode()).hexdigest(),
    )


def _document(source_id: str, body: str) -> FetchedDocument:
    return FetchedDocument(
        source_id=source_id,
        title=source_id,
        source_ref=f"fcgc://stage6/{source_id}.md",
        content=body,
        document_version="synthetic-v1",
    )


def _selection(firmware: FirmwareInput, documents: list[FetchedDocument]):
    candidates = [rule for result in extract_documents(documents) for rule in result.rules]
    return RuleContextReducer().reduce(firmware, extract_features(firmware), candidates, documents)


class StaticRetriever:
    def __init__(self, documents: list[FetchedDocument]) -> None:
        self.documents = documents
        self.search_calls = 0
        self.fetch_calls = 0

    def search(self, query: str, top_k: int) -> SearchResults:
        self.search_calls += 1
        return SearchResults(
            query=query,
            hits=[
                SearchHit(
                    source_id=document.source_id,
                    title=document.title,
                    source_ref=document.source_ref,
                    score=1,
                )
                for document in self.documents[:top_k]
            ],
        )

    def fetch(self, source_id: str) -> FetchedDocument:
        self.fetch_calls += 1
        return next(document for document in self.documents if document.source_id == source_id)


def test_low_overlap_general_rule_and_exception_are_retained_verbatim() -> None:
    firmware = _firmware()
    document = _document(
        "contextual",
        "# Synthetic FCG\n\n## Transaction handling\n\n"
        "When a persistent transaction completes, the following applies.\n\n"
        "The outcome must be propagated to the caller before another transaction.\n\n"
        "Exception: During forced shutdown, propagation may be deferred until reboot.\n",
    )
    selection = _selection(firmware, [document])
    assert len(selection.candidate_rules) == 1
    decision = selection.decisions[0]
    assert decision.action == "include"
    assert decision.preserved_for_uncertainty
    assert "general_rule_candidate" in decision.reason_codes
    request, required = pack_checker_input(
        firmware, selection, budget_tokens=2000, instructions_version="test-v1"
    )
    assert request is not None
    rule = request.evidence[0].rule
    assert rule.ambiguity_status == "review_required"
    assert rule.normative_statement in request.rendered_input
    assert rule.conditions[0].span.excerpt in request.rendered_input
    assert rule.exceptions[0].span.excerpt in request.rendered_input
    assert request.estimated_tokens == required == estimate_tokens(request.rendered_input)
    assert request.evidence[0].retained_spans
    broken = request.evidence[0].model_dump(mode="json")
    broken["retained_spans"] = [rule.normative_span.model_dump(mode="json")]
    with pytest.raises(ValidationError, match="omits a required"):
        PackedEvidence.model_validate(broken)

    broken_selection = selection.model_dump(mode="json")
    broken_selection["decisions"] = []
    with pytest.raises(ValidationError, match="exactly one reduction decision"):
        EvidenceSelection.model_validate(broken_selection)


def test_quantitative_limit_and_inline_exception_survive_packing() -> None:
    firmware = _firmware()
    document = _document(
        "limit",
        "# Synthetic FCG\n\nWhen transmitting a frame, the following applies.\n\n"
        "The payload must not exceed 16 bytes unless recovery mode is active.\n",
    )
    selection = _selection(firmware, [document])
    request, _ = pack_checker_input(
        firmware, selection, budget_tokens=2000, instructions_version="test-v1"
    )
    assert request is not None
    rule = request.evidence[0].rule
    assert "16 bytes" in rule.normative_statement
    assert "When transmitting a frame" in rule.conditions[0].span.excerpt
    assert "unless recovery mode is active" in rule.exceptions[0].span.excerpt
    assert rule.normative_statement in request.rendered_input
    assert rule.exceptions[0].span.excerpt in request.rendered_input


def test_dependency_closure_restores_low_rank_specific_rule() -> None:
    firmware = _firmware()
    document = _document(
        "dependencies",
        "# Synthetic FCG\n\n"
        "1. [SFCG-901] The result must be handled according to [SFCG-902].\n"
        "2. [SFCG-902] The `unrelated_call` result must be checked.\n",
    )
    selection = _selection(firmware, [document])
    by_id = {decision.rule_id: decision for decision in selection.decisions}
    assert by_id["SFCG-901"].action == "include"
    assert by_id["SFCG-902"].action == "include"
    assert "required_dependency" in by_id["SFCG-902"].reason_codes
    assert selection.unresolved_dependencies == []
    request, _ = pack_checker_input(
        firmware, selection, budget_tokens=2000, instructions_version="test-v1"
    )
    assert request is not None
    assert {item.rule.explicit_rule_id for item in request.evidence} == {"SFCG-901", "SFCG-902"}


def test_duplicate_sources_preserved_and_distinct_scope_not_merged() -> None:
    text = "# Synthetic FCG\n\n## Shared\n\nScope: C firmware.\n\nThe result must be checked.\n"
    documents = [
        _document("first", text),
        _document("second", text),
        _document("other_scope", text.replace("Scope: C firmware.", "Scope: recovery firmware.")),
    ]
    selection = _selection(_firmware(), documents)
    decisions = {decision.source_id: decision for decision in selection.decisions}
    assert decisions["first"].action == "include"
    assert decisions["second"].action == "exclude"
    assert "exact_duplicate_same_scope" in decisions["second"].reason_codes
    assert decisions["other_scope"].action == "include"
    assert "distinct_document_scope_retained" in decisions["other_scope"].reason_codes
    request, _ = pack_checker_input(
        _firmware(), selection, budget_tokens=2000, instructions_version="test-v1"
    )
    assert request is not None
    first = next(item for item in request.evidence if item.rule.source_id == "first")
    assert documents[1].source_ref in first.duplicate_source_refs


def test_explicit_scope_conflict_excludes_without_keyword_veto() -> None:
    firmware = _firmware()
    document = _document(
        "host",
        "# Synthetic FCG\n\nScope: host-side C++ calibration tools, not firmware.\n\n"
        "The flash_write result must be checked.\n",
    )
    selection = _selection(firmware, [document])
    assert selection.decisions[0].action == "exclude"
    assert "explicit_document_scope_conflict" in selection.decisions[0].reason_codes
    assert selection.decisions[0].source_ref == document.source_ref


def test_large_explanation_saves_tokens_and_budget_failure_never_truncates() -> None:
    background = "\n\n".join(
        f"Background section {index}: This describes historical logging architecture and "
        "build-time organization without adding a firmware obligation."
        for index in range(80)
    )
    document = _document(
        "long_guideline",
        "# Synthetic FCG\n\n" + background + "\n\n"
        "## Required behavior\n\nThe return status must be checked before reuse.\n",
    )
    firmware = _firmware()
    provider = StaticRetriever([document])
    run = run_p2(firmware, provider, top_k=1, token_budget=2000)
    assert provider.search_calls == provider.fetch_calls == 1
    assert run.status == "complete"
    assert run.metrics.retrieval_context_tokens > run.metrics.p2_checker_input_tokens
    assert run.metrics.token_savings is not None and run.metrics.token_savings > 0
    assert run.metrics.candidate_rule_count == 1
    assert run.checker_request is not None
    assert "return status must be checked" in run.checker_request.rendered_input
    assert run.checker_request.checker_payload() == run.checker_request.rendered_input
    assert "Background section 79" not in run.checker_request.rendered_input

    tiny = run_p2(firmware, StaticRetriever([document]), top_k=1, token_budget=25)
    assert tiny.status == "budget_exceeded"
    assert tiny.checker_request is None
    assert tiny.metrics.budget_failure
    assert tiny.metrics.required_p2_input_tokens > tiny.metrics.context_budget_tokens
    assert tiny.metrics.p2_checker_input_tokens is None


def test_missing_dependency_marks_context_incomplete() -> None:
    document = _document(
        "missing_ref",
        "# Synthetic FCG\n\nThe result must be checked as required by [SFCG-999].\n",
    )
    run = run_p2(_firmware(), StaticRetriever([document]), top_k=1, token_budget=2000)
    assert run.status == "incomplete_context"
    assert run.selection.unresolved_dependencies
    assert run.checker_request is not None
    assert any("Missing referenced evidence" in warning for warning in run.checker_request.warnings)
    with pytest.raises(ValueError, match="not ready"):
        run.checker_request.checker_payload()


def test_unsegmented_normative_source_is_packed_as_unresolved_section() -> None:
    document = _document(
        "ambiguous",
        "# Synthetic FCG\n\n[SFCG-950] Handle things somehow.\n",
    )
    run = run_p2(_firmware(), StaticRetriever([document]), top_k=1, token_budget=2000)
    assert run.status == "incomplete_context"
    assert run.selection.candidate_rules == []
    assert run.unresolved_sections
    assert run.checker_request is not None
    assert "[SFCG-950] Handle things somehow." in run.checker_request.rendered_input


def test_p2_reuses_p1_query_and_cli_exposes_audit(tmp_path: Path) -> None:
    document = _document("simple", "# Synthetic FCG\n\nThe return status must be checked.\n")
    firmware = _firmware()
    standalone = retrieve_p1(firmware, StaticRetriever([document]), top_k=1)
    run = run_p2(firmware, StaticRetriever([document]), top_k=1, token_budget=2000)
    assert run.p1.plan == standalone.plan
    assert run.p1.retrieval.request == standalone.retrieval.request
    assert run.p1.retrieval.search_results == standalone.retrieval.search_results
    assert run.p1.retrieval.documents == standalone.retrieval.documents

    output = tmp_path / "audit.json"
    project = Path(__file__).resolve().parents[2]
    result = CliRunner().invoke(
        app,
        [
            "reduce",
            "--case",
            "C002",
            "--strategy",
            "p2",
            "--config",
            str(project / "src/fcgc/config/benchmark.toml"),
            "--top-k",
            "3",
            "--token-budget",
            "4000",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["p1"]["retrieval"]["request"]["strategy"] == "p1"
    assert payload["status"] in {"complete", "incomplete_context"}
    assert len(payload["selection"]["decisions"]) == payload["metrics"]["candidate_rule_count"]
    assert payload["metrics"]["retrieval_context_tokens"] > 0
    assert payload["metrics"]["p2_checker_input_tokens"] is not None
