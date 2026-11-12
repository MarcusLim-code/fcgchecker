"""B0 generic query and retrieval execution."""

import hashlib
from pathlib import Path

from fcgc.core.files import read_source
from fcgc.core.interfaces import FCGRetriever
from fcgc.retrieval.search_pipeline import execute_retrieval
from fcgc.schemas.models import (
    FirmwareInput,
    RetrievalOutput,
    RetrievalRequest,
)


def load_firmware(path: Path, case_id: str) -> FirmwareInput:
    if path.suffix.lower() != ".c":
        raise ValueError("Firmware input must be a .c file")
    content = read_source(path)
    return FirmwareInput(
        case_id=case_id,
        source_name=path.name,
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def generic_query(firmware: FirmwareInput) -> str:
    # B0 only identifies the input as C; it does not inspect features or the file name.
    if Path(firmware.source_name).suffix.lower() != ".c":
        raise ValueError("B0 requires C firmware input")
    return "firmware coding guidelines C source"


def retrieve_b0(
    firmware: FirmwareInput, retriever: FCGRetriever, top_k: int = 3
) -> RetrievalOutput:
    request = RetrievalRequest(
        firmware=firmware,
        strategy="b0",
        query=generic_query(firmware),
        query_template_version="b0-generic-v1",
        top_k=top_k,
    )
    return execute_retrieval(request, retriever)
