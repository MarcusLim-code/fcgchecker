"""External imports and monkeypatches remain compatible after the package moves."""

import importlib

import pytest


@pytest.mark.parametrize(
    "old,new",
    [
        ("fcgc.core.artifact_target", "fcgc.checking.function_scope"),
        ("fcgc.core.checking", "fcgc.checking.compliance_checker"),
        ("fcgc.core.context_packer", "fcgc.checking.context_packer"),
        ("fcgc.core.context_reducer", "fcgc.checking.context_reducer"),
        ("fcgc.core.document_normalizer", "fcgc.checking.document_normalizer"),
        ("fcgc.core.features", "fcgc.checking.feature_extractor"),
        ("fcgc.core.rule_segmentation", "fcgc.checking.rule_extractor"),
        ("fcgc.core.p2", "fcgc.checking.reduced_context"),
        ("fcgc.core.baseline", "fcgc.retrieval.baseline"),
        ("fcgc.core.query_planner", "fcgc.retrieval.query_planner"),
        ("fcgc.core.retrieval", "fcgc.retrieval.search_pipeline"),
        ("fcgc.core.p1", "fcgc.retrieval.planned_retrieval"),
        ("fcgc.core.p3", "fcgc.retrieval.adaptive_retrieval"),
        ("fcgc.adapters.retrieval.local", "fcgc.retrieval.local_retriever"),
        ("fcgc.adapters.retrieval.replay", "fcgc.retrieval.replay_retriever"),
        ("fcgc.adapters.retrieval.agent", "fcgc.retrieval.mcp_bridge"),
        ("fcgc.adapters.retrieval.atlassian", "fcgc.retrieval.atlassian"),
        ("fcgc.adapters.retrieval.benchmark", "fcgc.retrieval.benchmark"),
        ("fcgc.adapters.checker.mock", "fcgc.integrations.mock_checker"),
        ("fcgc.adapters.checker.placeholder", "fcgc.integrations.placeholder_checker"),
        ("fcgc.adapters.checker.demo", "fcgc.integrations.synthetic_checker"),
        ("fcgc.adapters.checker.local_llm", "fcgc.integrations.ollama_checker"),
        ("fcgc.adapters.checker.devin", "fcgc.integrations.devin"),
        ("fcgc.adapters.checker.devin_agent", "fcgc.integrations.devin_agent"),
    ],
)
def test_legacy_imports_are_the_same_implementation_module(old, new, monkeypatch):
    legacy = importlib.import_module(old)
    implementation = importlib.import_module(new)
    assert legacy is implementation
    # Consumers patching a legacy import must affect the executing implementation.
    monkeypatch.setattr(legacy, "_external_compatibility_probe", True, raising=False)
    assert implementation._external_compatibility_probe is True
