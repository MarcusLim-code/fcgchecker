"""Bounded C syntax-tree observations and explicitly heuristic interpretations."""

import re
from typing import Any

from fcgc.schemas.models import FirmwareInput
from fcgc.schemas.stage3 import (
    CallObservation,
    FeatureReport,
    ObservedFeatures,
    SemanticCategory,
    SyntaxObservation,
)

EXTRACTOR_VERSION = "tree-sitter-c-v1"
_IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*\b")
_CALL_FALLBACK = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_CONTROL_WORDS = {"if", "for", "while", "switch", "sizeof", "return"}
_COMPONENT_WORDS = {
    "sensor": ("sensor", "adc"),
    "storage": ("flash", "storage", "persist"),
    "dma": ("dma",),
    "interrupt": ("irq", "interrupt"),
    "bus": ("bus",),
    "register": ("register", "mmio"),
}


def _node_text(source: bytes, node: Any) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(root: Any) -> list[Any]:
    nodes = []
    pending = [root]
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(reversed(node.named_children))
    return nodes


def _function_name(source: bytes, function_node: Any) -> str | None:
    declarator = function_node.child_by_field_name("declarator")
    if declarator is None:
        return None
    matches = _CALL_FALLBACK.findall(_node_text(source, declarator))
    return matches[-1] if matches else None


def _enclosing_function(source: bytes, node: Any) -> str | None:
    parent = node.parent
    while parent is not None:
        if parent.type == "function_definition":
            return _function_name(source, parent)
        parent = parent.parent
    return None


def _assignment_target(source: bytes, node: Any) -> tuple[str | None, bool]:
    parent = node.parent
    direct_return = False
    while parent is not None and parent.type != "function_definition":
        if parent.type == "return_statement":
            direct_return = True
        if parent.type in {"init_declarator", "assignment_expression"}:
            field = "declarator" if parent.type == "init_declarator" else "left"
            target = parent.child_by_field_name(field)
            if target is not None and target.type == "identifier":
                return _node_text(source, target), direct_return
            return None, direct_return
        parent = parent.parent
    return None, direct_return


def _macro_targets(code: str) -> dict[str, str]:
    return dict(
        re.findall(
            r"(?m)^\s*#\s*define\s+([A-Za-z_]\w*)\s*\([^\n)]*\)\s*([A-Za-z_]\w*)\s*\(",
            code,
        )
    )


def _categorize(observed: ObservedFeatures) -> tuple[list[SemanticCategory], list[str]]:
    categories: dict[str, set[str]] = {}

    def add(name: str, basis: str) -> None:
        categories.setdefault(name, set()).add(basis)

    identifiers = observed.identifiers
    for call in observed.calls:
        name = call.effective_callee.lower()
        basis = f"call:{call.callee}@{call.line}"
        add("api_return_handling", basis)
        if re.search(r"write|store|persist|commit", name):
            add("storage_write", basis)
        if re.search(r"lock|unlock|open|close|alloc|free|acquire|release", name):
            add("resource_lifetime", basis)
        if re.search(r"init|configure|start|enable|reset", name):
            add("initialization", basis)
        if "dma" in name:
            add("dma_transfer", basis)
        if "irq" in name or "interrupt" in name:
            add("interrupt_state", basis)
        if call.possible_indirect_call:
            add("indirect_call", basis)
        if call.macro_expanded:
            add("macro_wrapped_call", basis)
        fallible_hint = re.search(r"open|write|read|submit|transact|perform|init|callback", name)
        if (
            fallible_hint
            and not call.checked_lines
            and not call.returned_directly
            and not call.returned_later_lines
        ):
            add("possibly_unchecked_result", basis)
    for operation in observed.pointer_buffer_operations:
        basis = f"syntax:{operation.kind}@{operation.line}"
        add("pointer_validation", basis)
        if operation.kind == "subscript":
            add("buffer_boundary", basis)
    for operation in observed.control_flow:
        if operation.kind == "condition" and re.search(
            r"\b(rc|status|error|result|written)\b|<\s*0|!=\s*0", operation.expression
        ):
            add("error_handling", f"condition@{operation.line}")
    if any("capacity" in identifier or "length" in identifier for identifier in identifiers):
        add("buffer_boundary", "identifier:capacity_or_length")
    if any(
        "irq" in identifier.lower() or "interrupt" in identifier.lower()
        for identifier in identifiers
    ):
        add("interrupt_state", "identifier:interrupt")
    add("general_firmware", "C source artifact")
    inferred = [
        SemanticCategory(name=name, basis=sorted(basis))
        for name, basis in sorted(categories.items())
    ]
    components = [
        label
        for label, words in _COMPONENT_WORDS.items()
        if any(any(word in identifier.lower() for word in words) for identifier in identifiers)
    ]
    return inferred, sorted(components)


def _fallback(firmware: FirmwareInput, reason: str) -> FeatureReport:
    # No assignment, check, pointer, or data-flow claims are made on this path.
    code = re.sub(
        r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"])*\"",
        lambda match: re.sub(r"[^\n]", " ", match.group()),
        firmware.content,
        flags=re.DOTALL,
    )
    calls = []
    for match in _CALL_FALLBACK.finditer(code):
        if match.group(1) not in _CONTROL_WORDS:
            calls.append(
                CallObservation(
                    callee=match.group(1),
                    effective_callee=match.group(1),
                    enclosing_function=None,
                    line=code.count("\n", 0, match.start()) + 1,
                )
            )
    observed = ObservedFeatures(
        function_definitions=[],
        calls=calls,
        pointer_buffer_operations=[],
        control_flow=[],
        identifiers=sorted(set(_IDENTIFIER.findall(code))),
    )
    inferred, components = _categorize(observed)
    return FeatureReport(
        extractor_version=EXTRACTOR_VERSION,
        analysis_mode="lexical_fallback",
        parser_has_error=True,
        observed=observed,
        inferred_categories=inferred,
        component_hints=components,
        unknowns=[
            reason,
            "Fallback calls may include declarations; no return-use analysis is available.",
        ],
    )


def extract_features(firmware: FirmwareInput) -> FeatureReport:
    """Observe syntax; semantic categories are name-based hypotheses, not findings."""
    try:
        import tree_sitter_c
        from tree_sitter import Language, Parser

        parser = Parser(Language(tree_sitter_c.language()))
        source = firmware.content.encode("utf-8")
        root = parser.parse(source).root_node
    except (ImportError, RuntimeError, TypeError) as exc:
        return _fallback(firmware, f"C parser unavailable: {type(exc).__name__}")
    if root.has_error:
        return _fallback(
            firmware, "C syntax tree has parse errors; using bounded lexical fallback."
        )

    nodes = _walk(root)
    macros = _macro_targets(firmware.content)
    pointer_typedefs = set(
        re.findall(r"typedef\s+[^;]*?\(\s*\*\s*([A-Za-z_]\w*)\s*\)\s*\(", firmware.content)
    )
    pointer_parameters = set()
    for node in nodes:
        if node.type == "parameter_declaration":
            text = _node_text(source, node)
            for alias in pointer_typedefs:
                match = re.search(rf"\b{re.escape(alias)}\s+([A-Za-z_]\w*)\b", text)
                if match:
                    pointer_parameters.add(match.group(1))

    conditions = []
    returns = []
    functions = []
    pointer_ops = []
    control_flow = []
    for node in nodes:
        line = node.start_point.row + 1
        if node.type == "function_definition":
            name = _function_name(source, node)
            if name:
                functions.append(name)
        if node.type in {"if_statement", "while_statement", "for_statement", "switch_statement"}:
            condition = node.child_by_field_name("condition")
            if condition is not None:
                expression = _node_text(source, condition)
                conditions.append((expression, line, _enclosing_function(source, node), condition))
                control_flow.append(
                    SyntaxObservation(kind="condition", expression=expression, line=line)
                )
        elif node.type == "return_statement":
            returns.append(
                (_node_text(source, node), line, _enclosing_function(source, node), node.start_byte)
            )
            control_flow.append(
                SyntaxObservation(kind="return", expression=_node_text(source, node), line=line)
            )
        if node.type in {"pointer_expression", "subscript_expression", "field_expression"}:
            expression = _node_text(source, node)
            kind = {
                "pointer_expression": "pointer_expression",
                "subscript_expression": "subscript",
                "field_expression": "field_access",
            }[node.type]
            pointer_ops.append(SyntaxObservation(kind=kind, expression=expression, line=line))

    calls = []
    for node in nodes:
        if node.type != "call_expression":
            continue
        function_node = node.child_by_field_name("function")
        if function_node is None:
            continue
        callee = _node_text(source, function_node)
        effective = macros.get(callee, callee)
        enclosing = _enclosing_function(source, node)
        assigned_to, returned_directly = _assignment_target(source, node)
        check_lines = [
            line
            for expression, line, condition_function, condition_node in conditions
            if condition_function == enclosing
            and (
                (
                    assigned_to is not None
                    and condition_node.start_byte >= node.end_byte
                    and re.search(rf"\b{re.escape(assigned_to)}\b", expression)
                )
                or (condition_node.start_byte <= node.start_byte < condition_node.end_byte)
            )
        ]
        later_return_lines = [
            line
            for expression, line, return_function, return_start in returns
            if assigned_to is not None
            and return_function == enclosing
            and return_start >= node.end_byte
            and re.search(rf"\b{re.escape(assigned_to)}\b", expression)
        ]
        calls.append(
            CallObservation(
                callee=callee,
                effective_callee=effective,
                enclosing_function=enclosing,
                line=node.start_point.row + 1,
                assigned_to=assigned_to,
                checked_lines=sorted(set(check_lines)),
                returned_directly=returned_directly,
                returned_later_lines=sorted(set(later_return_lines)),
                macro_expanded=callee in macros,
                possible_indirect_call=(
                    function_node.type != "identifier" or callee in pointer_parameters
                ),
            )
        )
    observed = ObservedFeatures(
        function_definitions=sorted(set(functions)),
        calls=calls,
        pointer_buffer_operations=pointer_ops,
        control_flow=control_flow,
        identifiers=sorted(
            {_node_text(source, node) for node in nodes if node.type == "identifier"}
        ),
    )
    inferred, components = _categorize(observed)
    unknowns = [
        "No interprocedural analysis, alias analysis, or proof of data-flow correctness.",
        "A later conditional reference is observable, not proof it checks the same value.",
    ]
    if macros:
        unknowns.append(
            "Macro targets use simple textual definitions; conditional expansion is unresolved."
        )
    if any(call.possible_indirect_call for call in calls):
        unknowns.append("Indirect call targets and their return contracts are not resolved.")
    return FeatureReport(
        extractor_version=EXTRACTOR_VERSION,
        analysis_mode="tree_sitter_ast",
        parser_has_error=False,
        observed=observed,
        inferred_categories=inferred,
        component_hints=components,
        unknowns=unknowns,
    )
