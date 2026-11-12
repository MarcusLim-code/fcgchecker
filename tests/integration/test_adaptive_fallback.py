import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fcgc.checking.reduced_context import run_p2
from fcgc.cli import app
from fcgc.retrieval.adaptive_retrieval import load_fallback_config, run_p3
from fcgc.schemas.models import FetchedDocument, FirmwareInput, SearchHit, SearchResults


def firmware(storage=False):
    call = "flash_write" if storage else "do_work"
    code = f"int {call}(void); int app(void) {{ return {call}(); }}\n"
    return FirmwareInput(
        case_id="gate",
        source_name="gate.c",
        content=code,
        sha256=hashlib.sha256(code.encode()).hexdigest(),
    )


def document(name, text):
    return FetchedDocument(
        source_id=name,
        title=name,
        source_ref=f"fcgc://gate/{name}.md",
        content="# Synthetic FCG\n\n" + text,
    )


class Provider:
    def __init__(self, batches, fail=()):
        self.batches = batches
        self.documents = {d.source_id: d for batch in batches for d in batch}
        self.fail = fail
        self.searches = []
        self.fetches = []

    def search(self, query, top_k):
        batch = self.batches[min(len(self.searches), len(self.batches) - 1)]
        self.searches.append(query)
        return SearchResults(
            query=query,
            hits=[
                SearchHit(source_id=d.source_id, title=d.title, source_ref=d.source_ref, score=0)
                for d in batch[:top_k]
            ],
        )

    def fetch(self, source_id):
        self.fetches.append(source_id)
        if source_id in self.fail:
            raise OSError("synthetic unavailable source")
        return self.documents[source_id]


def config(**changes):
    return load_fallback_config().model_copy(update={"top_k": 1, **changes})


def test_complete_initial_does_not_fallback_or_use_scores():
    provider = Provider([[document("good", "The return status must be checked.")]])
    run = run_p3(firmware(), provider, config=config())
    assert run.status == "sufficient_signals"
    assert len(provider.searches) == 1
    assert run.metrics.additional_fetch_calls == 0
    assert run.initial_assessment.general_category_coverage["api_return_handling"]
    assert run.checker_request.strategy == "p3"


def test_missing_operation_category_recovers_observable_signal():
    initial = document("status", "The return status must be checked.")
    extra = document("storage", "Storage write results must be checked.")
    provider = Provider([[initial], [extra]])
    run = run_p3(firmware(storage=True), provider, config=config())
    assert "storage_write" in run.initial_assessment.missing_expected_categories
    assert run.status == "sufficient_signals"
    assert run.metrics.recovered_categories == ["storage_write"]
    assert run.metrics.additional_search_calls == run.metrics.additional_fetch_calls == 1
    assert run.attempts[1].new_rule_ids
    assert len(set(provider.searches)) == len(provider.searches)


def test_empty_first_pass_broadens_and_fetches_new_source():
    provider = Provider([[], [document("found", "The return status must be checked.")]])
    run = run_p3(firmware(), provider, config=config())
    assert run.initial_assessment.empty_or_weak_results
    assert run.final_assessment.normative_rule_count == 1
    assert run.status == "sufficient_signals"
    assert run.metrics.additional_retrieval_tokens > 0


def test_duplicate_only_fallback_stops_without_refetch():
    provider = Provider([[document("same", "The return status must be checked.")]])
    run = run_p3(firmware(storage=True), provider, config=config())
    assert run.status == "insufficient_evidence"
    assert len(provider.searches) == 3
    assert provider.fetches == ["same"]
    assert all(not attempt.new_rule_ids for attempt in run.attempts[1:])


def test_missing_dependency_is_fetched_and_resolved():
    first = document("first", "[SFCG-901] The status must follow [SFCG-902].")
    second = document("second", "[SFCG-902] The status must also follow [SFCG-901].")
    run = run_p3(firmware(), Provider([[first], [second]]), config=config())
    assert run.initial_assessment.unresolved_dependencies
    assert not run.final_assessment.unresolved_dependencies
    assert run.metrics.resolved_dependencies
    assert run.status == "sufficient_signals"


@pytest.mark.parametrize(
    "limit, expected",
    [
        ({"max_rounds": 1}, "retrieval_round_limit"),
        ({"max_search_calls": 1}, "search_call_budget"),
        ({"max_fetch_calls": 1}, "fetch_call_budget"),
        ({"max_candidate_sources": 1}, "candidate_source_limit"),
        ({"context_token_budget": 10}, "context_token_budget"),
    ],
)
def test_resource_limits(limit, expected):
    provider = Provider([[document("partial", "The return status must be checked.")]])
    run = run_p3(firmware(storage=True), provider, config=config(**limit))
    assert run.status == "insufficient_evidence"
    assert run.stop_reason == expected
    assert len(provider.searches) == 1


def test_fetch_failure_is_logged_and_gate_does_not_claim_recovery():
    provider = Provider([[document("broken", "The status must be checked.")]], fail={"broken"})
    run = run_p3(firmware(), provider, config=config())
    assert run.status == "insufficient_evidence"
    assert run.attempts[0].errors
    assert "retrieval_errors" in run.final_assessment.reasons
    assert provider.fetches == ["broken"]


def test_excessive_duplicate_candidates_are_an_observable_trigger():
    text = "The return status must be checked."
    provider = Provider([[document("copy1", text), document("copy2", text)]])
    run = run_p3(firmware(), provider, config=config(top_k=2, max_duplicate_fraction=0.2))
    assert run.initial_assessment.excessive_duplication
    assert run.initial_assessment.duplicate_fraction == 0.5
    assert run.status == "insufficient_evidence"


def test_search_failure_is_counted_and_logged():
    class BrokenSearch(Provider):
        def search(self, query, top_k):
            self.searches.append(query)
            raise OSError("synthetic search failure")

    provider = BrokenSearch([[]])
    run = run_p3(firmware(), provider, config=config())
    assert run.status == "insufficient_evidence"
    assert run.metrics.search_calls == 3
    assert all(attempt.errors for attempt in run.attempts)
    assert not provider.fetches


def test_persistent_uncertainty_retained_and_checker_blocked():
    rule = document(
        "conditional",
        "When operating, the following applies.\n\nThe return status must be checked.",
    )
    run = run_p3(firmware(), Provider([[rule]]), config=config())
    assert run.initial_assessment.ambiguous_applicability
    assert run.status == "insufficient_evidence"
    assert run.checker_request.status == "incomplete_context"
    with pytest.raises(ValueError, match="not ready"):
        run.checker_request.checker_payload()


def test_soft_time_limit_stops_followup_calls(monkeypatch):
    import fcgc.retrieval.adaptive_retrieval as module

    ticks = iter(range(1000))
    monkeypatch.setattr(module, "perf_counter", lambda: float(next(ticks)))
    provider = Provider([[document("slow", "The status must be checked.")]])
    run = run_p3(firmware(), provider, config=config(max_elapsed_seconds=0.1))
    assert run.status == "insufficient_evidence"
    assert len(provider.searches) <= 1
    assert not provider.fetches
    assert run.stop_reason == "elapsed_time_limit"


def test_p2_never_uses_fallback_and_cli_writes_audit(tmp_path):
    provider = Provider([[]])
    run_p2(firmware(), provider, top_k=1)
    assert len(provider.searches) == 1
    output = tmp_path / "p3.json"
    root = Path(__file__).resolve().parents[2]
    result = CliRunner().invoke(
        app,
        [
            "reduce",
            "--case",
            "C001",
            "--strategy",
            "p3",
            "--config",
            str(root / "src/fcgc/config/benchmark.toml"),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(output.read_text())
    assert data["strategy"] == "p3"
    assert data["metrics"]["search_calls"] <= 3
    assert data["metrics"]["fetch_calls"] <= 8
