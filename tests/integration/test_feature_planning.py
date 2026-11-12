import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fcgc.checking.feature_extractor import extract_features
from fcgc.cli import app
from fcgc.experiments.rq1 import evaluate_development
from fcgc.retrieval.baseline import load_firmware
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.retrieval.query_planner import FCGQueryPlanner

PROJECT = Path(__file__).resolve().parents[2]
CASES = PROJECT / "src/fcgc/fixtures/benchmark_cases"
DATASET = PROJECT / "benchmarks/v2"


def _features(case_id: str):
    return extract_features(load_firmware(CASES / f"{case_id}.c", case_id))


def test_ast_observes_assignment_checks_and_ignored_call() -> None:
    checked = _features("C001")
    ignored = _features("C002")
    assert checked.analysis_mode == "tree_sitter_ast"
    open_call = next(call for call in checked.observed.calls if call.callee == "sensor_open")
    assert open_call.assigned_to == "rc"
    assert open_call.checked_lines == [7]
    assert open_call.returned_later_lines == [7]
    ignored_open = next(call for call in ignored.observed.calls if call.callee == "sensor_open")
    assert ignored_open.assigned_to is None
    assert not ignored_open.checked_lines
    assert "possibly_unchecked_result" in {
        category.name for category in ignored.inferred_categories
    }


def test_macro_and_indirect_calls_remain_explicitly_uncertain() -> None:
    macro = _features("C017")
    call = next(call for call in macro.observed.calls if call.callee == "STORE")
    assert call.effective_callee == "flash_write"
    assert call.macro_expanded
    assert call.assigned_to == "written"
    assert call.checked_lines
    assert "storage" in macro.component_hints
    assert any("Macro targets" in unknown for unknown in macro.unknowns)

    indirect = _features("C019")
    assert any(call.possible_indirect_call for call in indirect.observed.calls)
    assert any("Indirect call targets" in unknown for unknown in indirect.unknowns)


def test_buffer_resource_and_error_features_are_separate_from_observations() -> None:
    buffer_case = _features("C005")
    assert any(
        operation.kind == "subscript"
        for operation in buffer_case.observed.pointer_buffer_operations
    )
    assert {"buffer_boundary", "pointer_validation"}.issubset(
        {category.name for category in buffer_case.inferred_categories}
    )
    resource_case = _features("C007")
    assert any(call.callee == "lock_bus" for call in resource_case.observed.calls)
    assert any(operation.kind == "return" for operation in resource_case.observed.control_flow)
    assert {"resource_lifetime", "error_handling"}.issubset(
        {category.name for category in resource_case.inferred_categories}
    )


def test_malformed_c_uses_bounded_fallback(tmp_path: Path) -> None:
    path = tmp_path / "broken.c"
    path.write_text("int main( { flash_write(data);\n", encoding="utf-8")
    report = extract_features(load_firmware(path, "broken"))
    assert report.analysis_mode == "lexical_fallback"
    assert report.parser_has_error
    assert report.observed.pointer_buffer_operations == []
    assert report.observed.control_flow == []
    assert any("fallback" in unknown.lower() for unknown in report.unknowns)


def test_query_plan_is_versioned_and_excludes_ground_truth_ids(tmp_path: Path) -> None:
    features = _features("C002")
    planner = FCGQueryPlanner(
        mapping_path=PROJECT / "src/fcgc/config/feature_concepts_v1.json",
        template_path=PROJECT / "src/fcgc/config/p1_templates_v1.toml",
    )
    plan = planner.plan(features, document_top_k=3)
    assert plan.mapping_version == "feature-concepts-v1"
    assert plan.template_version == "p1-template-v1"
    assert plan.max_queries == 1
    assert plan.document_top_k == 3
    assert "API return result" in plan.query
    assert "SFCG-" not in plan.query
    assert all(concept.basis for concept in plan.concepts)

    bad = tmp_path / "bad_mapping.json"
    payload = json.loads((PROJECT / "src/fcgc/config/feature_concepts_v1.json").read_text())
    payload["mappings"][0]["query_terms"] = "SFCG-002"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="must not reference benchmark rule IDs"):
        FCGQueryPlanner(mapping_path=bad)


def test_p1_and_cli_keep_search_fetch_trace_and_checker_placeholder() -> None:
    firmware = load_firmware(CASES / "C005.c", "C005")
    run = retrieve_p1(firmware, BenchmarkLexicalRetriever(), top_k=3)
    assert run.retrieval.request.strategy == "p1"
    assert run.retrieval.request.query == run.plan.query
    assert len(run.retrieval.documents) == 3
    assert [event.operation for event in run.retrieval.trace.events] == [
        "search",
        "fetch",
        "fetch",
        "fetch",
    ]

    result = CliRunner().invoke(
        app,
        [
            "check",
            "--case",
            "C005",
            "--strategy",
            "p1",
            "--config",
            str(PROJECT / "src/fcgc/config/benchmark.toml"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "not_evaluated"


def test_development_evaluation_uses_rule_ids_and_never_reads_heldout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read_text = Path.read_text

    def protected_read_text(path: Path, *args, **kwargs):
        if "ground_truth/heldout" in str(path):
            raise AssertionError("Held-out annotation was read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", protected_read_text)
    report = evaluate_development(DATASET)
    assert len(report.cases) == 8
    assert report.matched_budget
    assert report.b0_aggregate.search_operations == report.p1_aggregate.search_operations == 8
    assert report.b0_aggregate.fetch_operations == report.p1_aggregate.fetch_operations == 24
    assert report.p1_aggregate.micro_recall_at_k > report.b0_aggregate.micro_recall_at_k
    assert report.improvements
    assert report.regressions
    first = report.cases[0]
    assert first.b0.metrics.document_top_k == first.p1.metrics.document_top_k == 3
    assert first.b0.metrics.rule_k == first.p1.metrics.rule_k == 18
    assert first.b0.metrics.retrieved_rule_count > len(first.b0.fetched_source_ids)
