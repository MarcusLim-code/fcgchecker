import pytest
from pydantic import ValidationError

from fcgc.retrieval.local_retriever import LocalLexicalRetriever
from fcgc.schemas.models import FetchedDocument, SearchResults


def test_search_is_deterministic_and_fetch_preserves_content() -> None:
    retriever = LocalLexicalRetriever()
    first = retriever.search("firmware coding guidelines C source sensor poll", 2)
    second = retriever.search("firmware coding guidelines C source sensor poll", 2)

    assert first == second
    assert isinstance(first, SearchResults)
    assert [hit.source_id for hit in first.hits][0] == "FCG-002"
    document = retriever.fetch(first.hits[0].source_id)
    assert isinstance(document, FetchedDocument)
    assert document.source_ref == first.hits[0].source_ref
    assert "bounded\ntimeout" in document.content


def test_invalid_search_and_fetch() -> None:
    retriever = LocalLexicalRetriever()
    with pytest.raises(ValueError, match="top_k"):
        retriever.search("firmware", 0)
    with pytest.raises(KeyError, match="Unknown guideline"):
        retriever.fetch("FCG-999")


def test_contract_validation() -> None:
    with pytest.raises(ValidationError):
        FetchedDocument(source_id="", title="title", source_ref="ref", content="text")
    with pytest.raises(ValidationError):
        SearchResults(query="firmware", hits=[], unexpected="field")
