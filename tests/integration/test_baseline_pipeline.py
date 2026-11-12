from pathlib import Path

import pytest
from pydantic import ValidationError

from fcgc.integrations.placeholder_checker import PlaceholderChecker
from fcgc.retrieval.baseline import generic_query, load_firmware, retrieve_b0
from fcgc.retrieval.local_retriever import LocalLexicalRetriever
from fcgc.schemas.models import CheckerRequest, CheckerStatus


def test_b0_uses_generic_query_and_records_evidence(tmp_path: Path) -> None:
    firmware_path = tmp_path / "sensor_poll.c"
    firmware_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    firmware = load_firmware(firmware_path, "example")
    output = retrieve_b0(firmware, LocalLexicalRetriever(), top_k=2)

    assert generic_query(firmware) == "firmware coding guidelines C source"
    assert output.request.firmware.content == firmware_path.read_text(encoding="utf-8")
    assert output.request.strategy == "b0"
    assert len(output.documents) == 2
    assert output.documents[0].source_id == "FCG-001"
    assert [event.operation for event in output.trace.events] == ["search", "fetch", "fetch"]
    assert output.trace.events[0].query == output.request.query
    assert output.trace.events[1].source_id == output.documents[0].source_id
    assert output.trace.total_duration_ms >= 0

    result = PlaceholderChecker().check(CheckerRequest(firmware=firmware, retrieval=output))
    assert result.status == CheckerStatus.NOT_EVALUATED
    assert result.retrieval == output


def test_requires_c_file(tmp_path: Path) -> None:
    source = tmp_path / "input.txt"
    source.write_text("int x;", encoding="utf-8")
    with pytest.raises(ValueError, match=".c file"):
        load_firmware(source, "input")


def test_pipeline_rejects_malformed_provider_response(tmp_path: Path) -> None:
    source = tmp_path / "firmware.c"
    source.write_text("int x;\n", encoding="utf-8")

    class InvalidRetriever:
        def search(self, query: str, top_k: int) -> dict[str, object]:
            return {"query": query, "hits": [{"source_id": "FCG-001"}]}

        def fetch(self, source_id: str) -> None:
            raise AssertionError("Malformed search response should fail before fetch")

    with pytest.raises(ValidationError):
        retrieve_b0(load_firmware(source, "firmware"), InvalidRetriever())
