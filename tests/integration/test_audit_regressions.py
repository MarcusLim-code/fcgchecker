"""Regressions from the transfer audit. All credentials below are synthetic markers."""

import hashlib
from pathlib import Path

import pytest

from fcgc.checking.context_packer import pack_checker_input
from fcgc.checking.context_reducer import RuleContextReducer
from fcgc.checking.feature_extractor import extract_features
from fcgc.checking.rule_extractor import extract_documents, extract_rule_evidence
from fcgc.schemas.agent import AgentToolResult, ToolError, validate_source_uri
from fcgc.schemas.checking import FrozenCheckingTask
from fcgc.schemas.models import FetchedDocument, FirmwareInput


@pytest.mark.parametrize(
    "message",
    [
        "Fetch failed at https://audit-user:audit-marker@example.invalid/page",
        "Fetch failed at https://example.invalid/page?api_key=audit-marker",
        "Fetch failed at https://example.invalid/page?clientSecret=audit-marker",
        "Fetch failed at https://example.invalid/page#access_token=audit-marker",
        "API-Key: audit-marker",
        "client_secret=audit-marker",
        'upstream returned {"password": "audit-marker"}',
    ],
)
def test_transport_error_rejects_credential_values_without_echoing_them(message):
    with pytest.raises(ValueError) as rejected:
        ToolError(code="unavailable", message=message)
    assert "audit-marker" not in str(rejected.value)


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.invalid/page?apiKey=audit-marker",
        "https://example.invalid/page?CLIENT_SECRET=audit-marker",
        "https://example.invalid/page?refresh-token=audit-marker",
        "https://example.invalid/page?X-Amz-Signature=audit-marker",
        "https://example.invalid/page#access_token=audit-marker",
        "https://audit-user:audit-marker@example.invalid/page",
    ],
)
def test_source_uri_rejects_auth_material_without_echoing_values(uri):
    with pytest.raises(ValueError) as rejected:
        validate_source_uri(uri)
    assert "audit-marker" not in str(rejected.value)


def test_safe_transport_diagnostics_and_page_scope_are_not_credentials():
    assert ToolError(code="timeout", message="Upstream request timed out").code == "timeout"
    validate_source_uri("https://example.invalid/pages/42?spaceKey=FW#conditions")


def firmware():
    text = "int service(void) { return 0; }\n"
    return FirmwareInput(
        case_id="audit",
        source_name="audit.c",
        content=text,
        sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


@pytest.mark.parametrize("name", ["", " ", "not-a-function"])
def test_empty_or_invalid_function_focus_cannot_bypass_scope_validation(name):
    with pytest.raises(ValueError):
        FrozenCheckingTask(
            firmware=firmware(),
            documents=[],
            rules=[],
            context_status="complete",
            target_function=name,
            target_start_line=99,
            target_end_line=100,
        )


def test_untargeted_task_keeps_canonical_payload_without_optional_scope_fields():
    task = FrozenCheckingTask(
        firmware=firmware(), documents=[], rules=[], context_status="complete"
    )
    assert "target_function" not in task.canonical_json()
    assert "target_start_line" not in task.model_input_json()


def test_idless_prose_qualifiers_survive_low_overlap_reduction_and_packing():
    content = (
        "# Synthetic asynchronous operation rule\n\n"
        "When a transfer is pending, the caller must retain its buffer until completion. "
        "The caller must preserve its identifier.\n\n"
        "Exception: A confirmed cancellation may release the buffer early.\n"
    )
    document = FetchedDocument(
        source_id="audit-prose",
        title="Synthetic prose",
        source_ref="fcgc://audit/prose",
        document_version="audit-v1",
        content=content,
    )
    extracted = extract_rule_evidence(document)
    assert len(extracted.rules) >= 2
    assert any(rule.conditions for rule in extracted.rules)
    assert any(rule.exceptions for rule in extracted.rules)
    assert all(
        rule.explicit_rule_id is None and rule.evidence_id.startswith("ev-")
        for rule in extracted.rules
    )
    code = firmware()
    selection = RuleContextReducer().reduce(
        code, extract_features(code), extracted.rules, [document]
    )
    request, _ = pack_checker_input(
        code, selection, budget_tokens=12000, instructions_version="audit"
    )
    assert request is not None and request.evidence
    for evidence in request.evidence:
        rule = evidence.rule
        assert rule.document_version == "audit-v1"
        assert (
            document.content[rule.normative_span.start : rule.normative_span.end]
            == rule.normative_statement
        )
        for required in [rule.normative_span, *(f.span for f in rule.conditions + rule.exceptions)]:
            assert any(
                span.start <= required.start < required.end <= span.end
                for span in evidence.retained_spans
            )
            assert required.excerpt in evidence.rendered_text


def test_bridge_schema_rejects_raw_credential_fields_without_printing_the_value():
    with pytest.raises(ValueError) as rejected:
        AgentToolResult.model_validate({"Authorization": "Bearer audit-marker"})
    assert "audit-marker" not in str(rejected.value)


def test_placeholder_preserves_requested_generation_metadata():
    from fcgc.config import Settings, make_checker
    from fcgc.schemas.checking import GenerationSettings

    settings = Settings(
        retriever="benchmark",
        checker="placeholder",
        generation=GenerationSettings(temperature=0.5, seed=91),
    )
    task = FrozenCheckingTask(
        firmware=firmware(), documents=[], rules=[], context_status="complete"
    )
    result = make_checker(settings).check(task)
    assert result.status == "not_evaluated"
    assert result.execution.settings == settings.generation
    assert result.execution.output_schema_version == "model-findings-v1"


@pytest.fixture(scope="module")
def controlled_records(tmp_path_factory):
    from fcgc.experiments.runner import run_experiment
    from fcgc.schemas.stage9 import ExperimentLock, RunTrace

    root = Path(__file__).resolve().parents[2]
    directory = tmp_path_factory.mktemp("audit-controls")
    text = (root / "research/experiments/stage9_development.toml").read_text()
    text = text.replace("../../benchmarks/v2", str(root / "benchmarks/v2"))
    text = text.replace("../../outputs/experiments/stage9-development", str(directory / "runs"))
    text = text.replace('strategies = ["b0", "p1", "p2", "p3"]', 'strategies = ["b0"]')
    text = text.replace("repetitions = 3", 'repetitions = 1\ncase_ids = ["C001", "C002"]')
    config = directory / "experiment.toml"
    config.write_text(text)
    assert run_experiment(config)["failed"] == 0
    trace = RunTrace.model_validate_json(
        (directory / "runs/runs/C001-b0-r01/trace.json").read_text()
    )
    lock = ExperimentLock.model_validate_json((directory / "runs/lock.json").read_text())
    return root, trace, lock


@pytest.mark.parametrize("field", ["provider", "model", "settings", "skill_version", "prompt_hash"])
def test_evaluation_rejects_checker_controls_that_disagree_with_lock(controlled_records, field):
    from fcgc.experiments.evaluation import validate_checker_controls
    from fcgc.schemas.checking import GenerationSettings

    _, trace, lock = controlled_records
    result = trace.checker_results[0].model_copy(deep=True)
    validate_checker_controls(result, lock, trace, 0)
    bad = (
        GenerationSettings(temperature=0.75)
        if field == "settings"
        else "unrelated-provider-or-version"
    )
    setattr(result.execution, field, bad)
    with pytest.raises(ValueError):
        validate_checker_controls(result, lock, trace, 0)


@pytest.mark.parametrize(
    "provider,traffic",
    [("simulated_devin_agent", "local_fixture"), ("ollama", "synthetic_contract_test")],
)
def test_simulated_results_never_gain_compliance_accuracy(controlled_records, provider, traffic):
    from fcgc.experiments.benchmark import load_public_benchmark
    from fcgc.experiments.evaluation import (
        EvaluationConfig,
        canonical_catalog,
        evaluate_observation,
    )
    from fcgc.schemas.benchmark import CaseAnnotation

    root, original, _ = controlled_records
    trace = original.model_copy(deep=True)
    trace.traffic_kind = traffic
    result = trace.checker_results[0]
    # Deliberately inconsistent test-double status must not turn into real-model metrics.
    result.status = "evaluated"
    result.execution.provider = provider
    public = load_public_benchmark(root / "benchmarks/v2")
    annotation = CaseAnnotation.model_validate_json(
        (root / "benchmarks/v2/ground_truth/development/C001.json").read_text()
    )
    config = EvaluationConfig(
        experiment_directories=["unused"],
        dataset_root=str(root / "benchmarks/v2"),
        output_directory="unused",
        allow_provisional_compliance=True,
    )
    row = evaluate_observation(
        trace, annotation, canonical_catalog(public), result, 0, config, "test"
    )
    assert row["compliance_eligible"] is False
    assert row["compliance"]["tp"] is row["compliance"]["fn"] is row["compliance"]["f1"] is None
    assert row["retrieval"]["model_supplied"]["returned_at_k"] == 0


def test_different_definitions_cannot_be_dropped_as_duplicate_requirements():
    documents = [
        FetchedDocument(
            source_id=f"definition-{limit}",
            title="Synthetic shared scope",
            source_ref=f"fcgc://audit/definition-{limit}",
            content=(
                "# Synthetic shared scope\n\n"
                f"Definition: A small frame means at most {limit} bytes.\n\n"
                "A transfer must use a small frame.\n"
            ),
        )
        for limit in (16, 32)
    ]
    rules = [rule for result in extract_documents(documents) for rule in result.rules]
    assert len(rules) == 2
    assert all(rule.supporting_definitions for rule in rules)
    assert all(rule.duplicate_of is None for rule in rules)
    code = firmware()
    selection = RuleContextReducer().reduce(code, extract_features(code), rules, documents)
    assert len(selection.selected_ids) == 2
    request, _ = pack_checker_input(
        code, selection, budget_tokens=12000, instructions_version="audit"
    )
    assert request is not None
    assert "at most 16 bytes" in request.rendered_input
    assert "at most 32 bytes" in request.rendered_input


def test_distinct_canonical_rule_ids_are_not_dropped_as_duplicates():
    document = FetchedDocument(
        source_id="distinct-ids",
        title="Synthetic independent rules",
        source_ref="fcgc://audit/ids",
        content="# Synthetic independent rules\n\n"
        "1. [SFCG-991] The result must be checked.\n"
        "2. [SFCG-992] The result must be checked.\n",
    )
    rules = extract_rule_evidence(document).rules
    assert len(rules) == 2
    assert all(rule.duplicate_of is None for rule in rules)


@pytest.mark.parametrize("unsafe", ["parent_path", "symlink"])
def test_release_source_extraction_rejects_escape_and_link_members(tmp_path, unsafe):
    import io
    import runpy
    import tarfile

    extract = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/build_release.py"))[
        "extract_source"
    ]
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("../escape" if unsafe == "parent_path" else "project/link")
        if unsafe == "symlink":
            member.type = tarfile.SYMTYPE
            member.linkname = "../../escape"
            bundle.addfile(member)
        else:
            member.size = 3
            bundle.addfile(member, io.BytesIO(b"bad"))
    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(ValueError, match="unsafe paths"):
        extract(archive, destination)
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("later_exception", [False, True])
def test_independently_packed_followup_rule_keeps_preceding_conditional_scope(later_exception):
    content = (
        "# Synthetic conditional paragraph\n\n"
        "When a transfer is pending, the caller must retain its buffer. "
        "The caller must preserve its identifier.\n"
    )
    if later_exception:
        content += "\nException: A confirmed cancellation may release the buffer early.\n"
    document = FetchedDocument(
        source_id="conditional-followup",
        title="Synthetic conditional paragraph",
        source_ref="fcgc://audit/conditional",
        content=content,
    )
    rules = extract_rule_evidence(document).rules
    assert len(rules) == 2
    followup = rules[1]
    assert followup.normative_statement == "The caller must preserve its identifier."
    assert any("When a transfer is pending" in c.span.excerpt for c in followup.conditions)
    assert followup.ambiguity_status == "review_required"
    assert followup.section_span is not None
    assert "When a transfer is pending" in followup.section_span.excerpt
    code = firmware()
    selection = RuleContextReducer().reduce(code, extract_features(code), [followup], [document])
    request, _ = pack_checker_input(
        code, selection, budget_tokens=12000, instructions_version="audit"
    )
    assert request is not None and len(request.evidence) == 1
    assert "When a transfer is pending" in request.evidence[0].rendered_text
    if later_exception:
        assert "confirmed cancellation" in request.evidence[0].rendered_text
