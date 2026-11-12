"""Source-preserving Markdown normalization boundary for future provider adapters."""

import re
from typing import Protocol

from fcgc.schemas.models import FetchedDocument
from fcgc.schemas.rules import NormalizedBlock, NormalizedDocument, SourceSpan, TableCell

HEADING = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
TABLE_SEPARATOR = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


class DocumentNormalizer(Protocol):
    def normalize(self, document: FetchedDocument) -> NormalizedDocument: ...


def source_span(content: str, start: int, end: int) -> SourceSpan:
    """Create a character-offset span while retaining its exact source wording."""
    if not 0 <= start < end <= len(content):
        raise ValueError("Invalid source span bounds")
    return SourceSpan(
        start=start,
        end=end,
        start_line=content.count("\n", 0, start) + 1,
        end_line=content.count("\n", 0, end - 1) + 1,
        excerpt=content[start:end],
    )


def trimmed_span(content: str, start: int, end: int) -> SourceSpan:
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return source_span(content, start, end)


def _table_cells(content: str, start: int, line: str, headings: list[str]) -> list[TableCell]:
    bounds = [index for index, char in enumerate(line) if char == "|"]
    if not bounds:
        return []
    left = 0 if bounds[0] != 0 else bounds[0] + 1
    right = len(line) if bounds[-1] != len(line) - 1 else bounds[-1]
    slices = []
    cursor = left
    for boundary in bounds:
        if boundary <= cursor or boundary > right:
            continue
        slices.append((cursor, boundary))
        cursor = boundary + 1
    if cursor < right:
        slices.append((cursor, right))
    cells = []
    for index, (a, b) in enumerate(slices):
        if content[start + a : start + b].strip():
            cells.append(
                TableCell(
                    column=headings[index] if index < len(headings) else f"column_{index + 1}",
                    span=trimmed_span(content, start + a, start + b),
                )
            )
    return cells


class MarkdownDocumentNormalizer:
    version = "markdown-normalizer-v1"

    def normalize(self, document: FetchedDocument) -> NormalizedDocument:
        content = document.content
        lines = content.splitlines(keepends=True)
        offsets = []
        cursor = 0
        for line in lines:
            offsets.append(cursor)
            cursor += len(line)
        blocks: list[NormalizedBlock] = []
        headings: list[tuple[int, str]] = []

        def lineage() -> list[str]:
            return [title for _, title in headings]

        def line_end(index: int) -> int:
            return offsets[index] + len(lines[index].rstrip("\r\n"))

        def add(kind: str, first: int, last: int, cells: list[TableCell] | None = None) -> None:
            blocks.append(
                NormalizedBlock(
                    kind=kind,
                    span=trimmed_span(content, offsets[first], line_end(last)),
                    heading_lineage=lineage(),
                    cells=cells or [],
                )
            )

        index = 0
        while index < len(lines):
            line = lines[index].rstrip("\r\n")
            if not line.strip():
                index += 1
                continue
            heading = HEADING.match(line)
            if heading:
                depth = len(heading.group(1))
                headings = [(level, title) for level, title in headings if level < depth]
                headings.append((depth, heading.group(2).strip()))
                index += 1
                continue
            if line.lstrip().startswith("```"):
                first = index
                index += 1
                while index < len(lines) and not lines[index].lstrip().startswith("```"):
                    index += 1
                if index < len(lines):
                    index += 1
                add("code", first, index - 1)
                continue
            if line.lstrip().startswith("|"):
                first = index
                while index < len(lines) and lines[index].lstrip().startswith("|"):
                    index += 1
                header_line = lines[first].rstrip("\r\n")
                header_cells = _table_cells(content, offsets[first], header_line, [])
                header_names = [cell.span.excerpt for cell in header_cells]
                data_start = (
                    first + 2
                    if first + 1 < index and TABLE_SEPARATOR.match(lines[first + 1].rstrip("\r\n"))
                    else first
                )
                for row in range(data_start, index):
                    row_text = lines[row].rstrip("\r\n")
                    if TABLE_SEPARATOR.match(row_text):
                        continue
                    cells = _table_cells(content, offsets[row], row_text, header_names)
                    add("table_row", row, row, cells)
                continue
            if LIST_ITEM.match(line):
                first = index
                index += 1
                while index < len(lines):
                    following = lines[index].rstrip("\r\n")
                    if not following.strip() or not following[:1].isspace():
                        break
                    if HEADING.match(following) or LIST_ITEM.match(following):
                        break
                    index += 1
                add("list_item", first, index - 1)
                continue
            if line.lstrip().startswith(">"):
                first = index
                index += 1
                while index < len(lines) and lines[index].lstrip().startswith(">"):
                    index += 1
                add("blockquote", first, index - 1)
                continue
            first = index
            index += 1
            while index < len(lines):
                following = lines[index].rstrip("\r\n")
                if (
                    not following.strip()
                    or HEADING.match(following)
                    or LIST_ITEM.match(following)
                    or following.lstrip().startswith(("|", ">", "```"))
                ):
                    break
                index += 1
            add("paragraph", first, index - 1)
        return NormalizedDocument(document=document, normalizer_version=self.version, blocks=blocks)
