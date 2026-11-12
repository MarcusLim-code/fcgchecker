"""Resolve an optional function using the same C parser as feature extraction."""

import re

from fcgc.checking.feature_extractor import _function_name, _walk
from fcgc.schemas.models import FirmwareInput


def function_location(firmware: FirmwareInput, name: str) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
        raise ValueError("Function name must be a C identifier")
    import tree_sitter_c
    from tree_sitter import Language, Parser

    source = firmware.content.encode()
    root = Parser(Language(tree_sitter_c.language())).parse(source).root_node
    if root.has_error:
        raise ValueError("Cannot reliably resolve a function in code with C parse errors")
    matches = [
        node
        for node in _walk(root)
        if node.type == "function_definition" and _function_name(source, node) == name
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one definition of function {name}; found {len(matches)}")
    return matches[0].start_point[0] + 1, matches[0].end_point[0] + 1
