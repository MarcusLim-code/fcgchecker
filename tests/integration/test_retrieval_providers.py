import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from fcgc.checking.feature_extractor import extract_features
from fcgc.cli import app
from fcgc.retrieval.baseline import load_firmware, retrieve_b0
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.retrieval.planned_retrieval import retrieve_p1
from fcgc.retrieval.query_planner import FCGQueryPlanner
from fcgc.retrieval.replay_retriever import ReplayRetriever, capture_replay
from fcgc.schemas.models import SearchHit, SearchResults, SearchScope

PROJECT = Path(__file__).resolve().parents[2]
FIRMWARE = PROJECT / "src/fcgc/fixtures/benchmark_cases/C002.c"
REPLAY = PROJECT / "src/fcgc/fixtures/replay/benchmark_c002_v2.json"


def test_local_ranking_scope_and_empty_results() -> None:
    all_docs = BenchmarkLexicalRetriever()
    first = all_docs.search("synthetic firmware guidelines", 8)
    assert first == all_docs.search("synthetic firmware guidelines", 8)
    assert len(first.hits) == 8
    assert first.hits == sorted(first.hits, key=lambda hit: (-hit.score, hit.source_id))
    assert all_docs.search("zzzznonexistenttoken", 3).hits == []

    scope = SearchScope(allowed_scopes=["benchmark_firmware"])
    scoped = BenchmarkLexicalRetriever(scope=scope)
    hits = scoped.search("synthetic firmware guidelines", 8)
    assert len(hits.hits) == 6
    assert hits.scope == scope
    assert all(not hit.source_id.startswith("decoy") for hit in hits.hits)
    with pytest.raises(PermissionError, match="outside search scope"):
        scoped.fetch("decoy_host_tools")
    with pytest.raises(ValueError, match="unknown"):
        BenchmarkLexicalRetriever(scope=SearchScope(allowed_source_ids=["missing"]))

    manifest = json.loads((PROJECT / "benchmarks/v2/manifest.json").read_text())
    metadata = json.loads((PROJECT / "src/fcgc/config/benchmark_scopes_v1.json").read_text())
    assert metadata["corpus_version"] == manifest["dataset_version"]
    assert metadata["scope_by_source"] == {
        document["source_id"]: document["scope"] for document in manifest["documents"]
    }


def test_replay_matches_local_b0_and_p1_with_exact_searches() -> None:
    firmware = load_firmware(FIRMWARE, "C002")
    local = BenchmarkLexicalRetriever()
    replay = ReplayRetriever(REPLAY)
    for execute in (retrieve_b0, retrieve_p1):
        local_run = execute(firmware, local, top_k=3)
        replay_run = execute(firmware, replay, top_k=3)
        local_output = local_run.retrieval if hasattr(local_run, "retrieval") else local_run
        replay_output = replay_run.retrieval if hasattr(replay_run, "retrieval") else replay_run
        assert replay_output.search_results == local_output.search_results
        assert replay_output.documents == local_output.documents
        assert [event.operation for event in replay_output.trace.events] == [
            "search",
            "fetch",
            "fetch",
            "fetch",
        ]
    with pytest.raises(KeyError, match="No exact replay"):
        replay.search("another query", 3)
    with pytest.raises(KeyError, match="No exact replay"):
        replay.search("firmware coding guidelines C source", 2)
    with pytest.raises(KeyError, match="not returned"):
        replay.fetch("not-recorded")


def test_replay_rejects_duplicate_hits_and_missing_sources(tmp_path: Path) -> None:
    payload = json.loads(REPLAY.read_text(encoding="utf-8"))
    hit = payload["searches"][0]["results"]["hits"][0]
    payload["searches"][0]["results"]["hits"][-1] = hit
    broken = tmp_path / "duplicate.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError, match="duplicate source IDs"):
        ReplayRetriever(broken)

    payload["searches"][0]["results"]["hits"][-1] = {**hit, "source_id": "absent"}
    broken.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError, match="missing source"):
        ReplayRetriever(broken)


def test_pipeline_validates_provider_duplicates_and_fetch_errors() -> None:
    firmware = load_firmware(FIRMWARE, "C002")
    local = BenchmarkLexicalRetriever()
    hit = local.search("firmware", 1).hits[0]

    class DuplicateProvider:
        def search(self, query: str, top_k: int) -> SearchResults:
            return SearchResults(query=query, hits=[hit, hit])

        def fetch(self, source_id: str):
            return local.fetch(source_id)

    with pytest.raises(ValueError, match="duplicate source IDs"):
        retrieve_b0(firmware, DuplicateProvider(), top_k=3)

    class MissingProvider:
        def search(self, query: str, top_k: int) -> SearchResults:
            return SearchResults(
                query=query,
                hits=[SearchHit(source_id="absent", title="absent", source_ref="absent", score=1)],
            )

        def fetch(self, source_id: str):
            raise KeyError(source_id)

    with pytest.raises(KeyError, match="absent"):
        retrieve_p1(firmware, MissingProvider(), top_k=3)

    class EmptyProvider:
        def search(self, query: str, top_k: int) -> SearchResults:
            return SearchResults(query=query, hits=[])

        def fetch(self, source_id: str):
            raise AssertionError("Empty search must not fetch")

    empty = retrieve_b0(firmware, EmptyProvider(), top_k=3)
    assert empty.documents == []
    assert [event.operation for event in empty.trace.events] == ["search"]


def test_planner_v2_uses_runtime_names_and_general_concepts() -> None:
    features = extract_features(load_firmware(FIRMWARE, "C002"))
    plan = FCGQueryPlanner().plan(features, document_top_k=3)
    assert plan.mapping_version == "feature-concepts-v2"
    assert plan.template_version == "p1-template-v2"
    assert "sensor_open" in plan.api_names
    assert "sensor" in plan.component_hints
    assert "sensor_open" in plan.query
    assert "general firmware coding requirements" in plan.query
    assert "SFCG-" not in plan.query
    without_categories = features.model_copy(update={"inferred_categories": []})
    generic_plan = FCGQueryPlanner().plan(without_categories, document_top_k=3)
    assert [concept.feature_category for concept in generic_plan.concepts] == ["general_firmware"]


def test_cli_b0_p1_replay_and_full_log(tmp_path: Path) -> None:
    runner = CliRunner()
    benchmark_config = PROJECT / "src/fcgc/config/benchmark.toml"
    replay_config = PROJECT / "src/fcgc/config/replay.toml"
    log = tmp_path / "runs.jsonl"
    for strategy in ("b0", "p1"):
        local = runner.invoke(
            app,
            [
                "retrieve",
                "--case",
                "C002",
                "--strategy",
                strategy,
                "--config",
                str(benchmark_config),
                "--top-k",
                "3",
            ],
        )
        replay = runner.invoke(
            app,
            [
                "retrieve",
                "--case",
                "C002",
                "--strategy",
                strategy,
                "--config",
                str(replay_config),
                "--top-k",
                "3",
                "--log",
                str(log),
            ],
        )
        assert local.exit_code == replay.exit_code == 0, replay.output
        local_data = json.loads(local.stdout)
        replay_data = json.loads(replay.stdout)
        if strategy == "p1":
            assert local_data["plan"] == replay_data["plan"]
            local_data, replay_data = local_data["retrieval"], replay_data["retrieval"]
        assert local_data["search_results"] == replay_data["search_results"]
        assert local_data["documents"] == replay_data["documents"]
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert entries[0]["query_template_version"] == "b0-generic-v1"
    assert entries[1]["query_template_version"] == "p1-template-v2"
    assert entries[1]["ranked_results"]
    assert entries[1]["fetched_documents"][0]["content"]


def test_capture_replay_of_empty_search(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    fixture = capture_replay(
        path,
        BenchmarkLexicalRetriever(),
        [("zzzznonexistenttoken", 3)],
        corpus_version="2.0.0",
    )
    assert fixture.searches[0].results.hits == []
    assert ReplayRetriever(path).search("zzzznonexistenttoken", 3).hits == []


def test_cli_scope_is_shared_by_b0_and_p1() -> None:
    config = PROJECT / "src/fcgc/config/benchmark_scoped.toml"
    for strategy in ("b0", "p1"):
        result = CliRunner().invoke(
            app,
            [
                "retrieve",
                "--case",
                "C002",
                "--strategy",
                strategy,
                "--config",
                str(config),
                "--top-k",
                "3",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        retrieval = data["retrieval"] if strategy == "p1" else data
        assert retrieval["search_results"]["scope"] == {
            "allowed_scopes": ["benchmark_firmware"],
            "allowed_source_ids": [],
        }
        assert all(
            not hit["source_id"].startswith("decoy") for hit in retrieval["search_results"]["hits"]
        )
