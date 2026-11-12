"""Bounded UTF-8 input without newline conversion; offsets refer to this exact text."""

from pathlib import Path

MAX_SOURCE_BYTES = 8_000_000


def read_source(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError(f"Source exceeds {MAX_SOURCE_BYTES} byte local limit: {path}")
    text = raw.decode("utf-8")
    if not text.strip():
        raise ValueError(f"Source is empty: {path}")
    if "\x00" in text:
        raise ValueError(f"Source contains a NUL byte: {path}")
    return text


def protect_inputs(output: Path | None, inputs: list[Path | None]) -> None:
    """Reject aliases (including symlinks/hard links) before writing an output."""
    if output is None:
        return
    for source in inputs:
        if source is not None and (
            output.resolve() == source.resolve()
            or (output.exists() and source.exists() and output.samefile(source))
        ):
            raise ValueError(f"Output would overwrite an input: {source}")
