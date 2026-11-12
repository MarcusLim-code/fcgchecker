import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from fcgc.checking.document_normalizer import MarkdownDocumentNormalizer
from fcgc.checking.rule_extractor import extract_documents, extract_rule_evidence
from fcgc.cli import app
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.schemas.models import FetchedDocument
from fcgc.schemas.rules import RuleExtraction

PROJECT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT / "src/fcgc/fixtures/segmentation"


def _document(name: str) -> FetchedDocument:
    path = FIXTURES / name
    return FetchedDocument(
        source_id=path.stem,
        title=path.stem,
        source_ref=f"fcgc://synthetic-stage5/{name}",
        content=path.read_text(encoding="utf-8"),
        document_version="1.0-synthetic",
    )


def test_normalization_retains_headings_tables_and_exact_offsets() -> None:
    document = _document("contextual_rules.md")
    normalized = MarkdownDocumentNormalizer().normalize(document)
    assert normalized.normalizer_version == "markdown-normalizer-v1"
    assert {block.kind for block in normalized.blocks} >= {"paragraph", "table_row"}
    row = next(block for block in normalized.blocks if block.kind == "table_row")
    assert row.heading_lineage == ["Synthetic FCG: Context", "Table cases"]
    assert [cell.column for cell in row.cells] == ["Rule", "Requirement", "Condition", "Exception"]
    for block in normalized.blocks:
        assert document.content[block.span.start : block.span.end] == block.span.excerpt
        for cell in block.cells:
            assert document.content[cell.span.start : cell.span.end] == cell.span.excerpt


def test_contextual_paragraph_rules_keep_conditions_exceptions_and_definitions() -> None:
    document = _document("contextual_rules.md")
    result = extract_rule_evidence(document)
    assert len(result.rules) == 6
    assert result.normalized.document == document
    storage = [rule for rule in result.rules if rule.heading_lineage[-1] == "Storage path"]
    assert len(storage) == 3  # Independent obligations in one paragraph.
    assert storage[0].explicit_rule_id == "SFCG-901"
    assert all(
        "When a write targets persistent storage" in fragment.span.excerpt
        for rule in storage
        for fragment in rule.conditions[:1]
    )
    assert all(
        "During forced shutdown" in fragment.span.excerpt
        for rule in storage
        for fragment in rule.exceptions
    )
    assert all(rule.ambiguity_status == "review_required" for rule in storage)
    assert any(
        "active handle means" in fragment.span.excerpt.lower()
        for fragment in storage[2].supporting_definitions
    )
    assert [reference.target for reference in storage[2].dependencies] == ["Section 2"]
    assert storage[2].document_version == "1.0-synthetic"
    assert storage[2].section_span is not None
    assert "Exception:" in storage[2].section_span.excerpt

    buffer_rule = next(rule for rule in result.rules if rule.heading_lineage[-1] == "Buffer path")
    assert "This check shall include" in buffer_rule.normative_statement
    assert "For caller-owned buffers" in buffer_rule.conditions[0].span.excerpt
    table_rule = next(rule for rule in result.rules if rule.explicit_rule_id == "SFCG-902")
    assert table_rule.normative_statement == "Validate the destination before copying."
    assert table_rule.conditions[0].span.excerpt == "Caller-owned output"
    assert table_rule.exceptions[0].span.excerpt.startswith("Except for")

    assert any(fragment.kind == "example" for fragment in result.other_fragments)
    assert any(
        fragment.kind == "informative" and 'word "must"' in fragment.span.excerpt
        for fragment in result.other_fragments
    )
    vague = next(rule for rule in result.rules if "appropriately" in rule.normative_statement)
    assert vague.obligation_strength == "recommendation"
    assert vague.ambiguity_status == "review_required"
    assert all(rule.normative_statement == rule.normative_span.excerpt for rule in result.rules)
    assert RuleExtraction.model_validate_json(result.model_dump_json()) == result


def test_obvious_duplicate_keeps_sources_and_distinct_scope() -> None:
    first, second = extract_documents(
        [_document("duplicate_scope_a.md"), _document("duplicate_scope_b.md")]
    )
    assert len(first.rules) == 1
    assert len(second.rules) == 2
    assert second.rules[0].duplicate_of == first.rules[0].evidence_id
    assert second.rules[0].source_ref != first.rules[0].source_ref
    assert second.rules[1].duplicate_of is None
    assert second.rules[1].heading_lineage[-1] == "Recovery scope"


def test_different_exception_is_not_deduplicated_and_quoted_modal_is_informative() -> None:
    base = "# Synthetic FCG\n\n## Shared\n\nThe result must be checked.\n"
    with_exception = base + "\nException: During recovery, checking may be omitted.\n"
    documents = [
        FetchedDocument(source_id="plain", title="plain", source_ref="local://plain", content=base),
        FetchedDocument(
            source_id="qualified",
            title="qualified",
            source_ref="local://qualified",
            content=with_exception,
        ),
    ]
    plain, qualified = extract_documents(documents)
    assert plain.rules[0].duplicate_of is None
    assert qualified.rules[0].duplicate_of is None
    assert qualified.rules[0].exceptions[0].span.excerpt.startswith("Exception:")

    quote = FetchedDocument(
        source_id="quote",
        title="quote",
        source_ref="local://quote",
        content='# Synthetic FCG\n\nThe phrase "must reset now" appears in an example caption.\n',
    )
    result = extract_rule_evidence(quote)
    assert result.rules == []
    assert any(fragment.kind == "informative" for fragment in result.other_fragments)


def test_incomplete_statement_preserves_section_for_review() -> None:
    document = FetchedDocument(
        source_id="uncertain",
        title="Synthetic uncertain",
        source_ref="fcgc://synthetic-stage5/uncertain",
        content="# Synthetic uncertain\n\n## Review\n\n[SFCG-950] Handle things somehow.\n",
    )
    result = extract_rule_evidence(document)
    assert result.rules == []
    assert result.review_sections
    assert "[SFCG-950]" in result.review_sections[0].span.excerpt


def test_later_definition_remains_linked_to_earlier_requirement() -> None:
    document = FetchedDocument(
        source_id="late-definition",
        title="Synthetic late definition",
        source_ref="fcgc://synthetic-stage5/late-definition",
        content=(
            "# Synthetic FCG\n\n## Use\n\nThe active handle must be checked.\n\n"
            "## Definitions\n\nAn active handle means a token returned by open.\n"
        ),
    )
    rule = extract_rule_evidence(document).rules[0]
    assert rule.supporting_definitions[0].span.excerpt.startswith("An active handle means")


def test_schema_rejects_broken_provenance() -> None:
    result = extract_rule_evidence(_document("contextual_rules.md"))
    payload = result.model_dump(mode="json")
    payload["rules"][0]["normative_span"]["excerpt"] = "invented wording"
    payload["rules"][0]["normative_statement"] = "invented wording"
    with pytest.raises(ValidationError, match="does not match original document"):
        RuleExtraction.model_validate(payload)


def test_stage2_corpus_and_cli_extract_offline() -> None:
    retriever = BenchmarkLexicalRetriever()
    explicit_ids = []
    for hit in retriever.search("synthetic", 20).hits:
        document = retriever.fetch(hit.source_id)
        result = extract_rule_evidence(document)
        assert result.normalized.document.content == document.content
        for rule in result.rules:
            if rule.explicit_rule_id:
                explicit_ids.append(rule.explicit_rule_id)
            assert document.content[rule.normative_span.start : rule.normative_span.end] == (
                rule.normative_statement
            )
    assert sorted(explicit_ids) == [f"SFCG-{number:03}" for number in range(1, 37)]

    result = CliRunner().invoke(
        app,
        [
            "extract-rules",
            "--source-id",
            "buffers",
            "--config",
            str(PROJECT / "src/fcgc/config/benchmark.toml"),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["normalized"]["document"]["source_id"] == "buffers"
    assert any(rule["explicit_rule_id"] == "SFCG-019" for rule in payload["rules"])

    local = CliRunner().invoke(
        app,
        [
            "extract-rules",
            "--document",
            str(FIXTURES / "contextual_rules.md"),
            "--document-version",
            "1.0-synthetic",
        ],
    )
    assert local.exit_code == 0, local.output
    assert len(json.loads(local.stdout)["rules"]) == 6
