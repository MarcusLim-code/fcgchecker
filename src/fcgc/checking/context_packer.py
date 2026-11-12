"""Lossless source-backed evidence packing with explicit approximate token accounting."""

import re

from fcgc.schemas.models import FetchedDocument, FirmwareInput
from fcgc.schemas.rules import RuleEvidence, SourceSpan
from fcgc.schemas.stage6 import (
    CodeLocation,
    EvidenceSelection,
    PackedCheckerRequest,
    PackedEvidence,
    UnresolvedSection,
)

TOKENIZER_VERSION = "regex-word-punctuation-v1"
INSTRUCTIONS = (
    "Evaluate only against the source-backed guideline evidence below. "
    "Treat conditions, exceptions, definitions, scope, and quantitative limits as part "
    "of each rule. Do not infer compliance from an absent rule or missing evidence. "
    "Return not_evaluated when evidence is incomplete or applicability is unresolved. "
    "Cite source IDs and exact source wording for any future finding."
)


def estimate_tokens(text: str) -> int:
    """Deterministic word/punctuation count, not a model or service tokenizer."""
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def _source_label(rule: RuleEvidence) -> str:
    label = rule.explicit_rule_id or rule.evidence_id
    heading = " > ".join(rule.heading_lineage)
    version = f" v={rule.document_version}" if rule.document_version else ""
    review = " review" if rule.ambiguity_status == "review_required" else ""
    return (
        f"[{label} @ {rule.source_id}:L{rule.normative_span.start_line}"
        f"{version}{review}; {heading}]"
    )


def _required_spans(rule: RuleEvidence) -> list[tuple[str, SourceSpan]]:
    parts: list[tuple[str, SourceSpan]] = [("Rule", rule.normative_span)]
    parts.extend(("Condition", item.span) for item in rule.conditions)
    parts.extend(("Exception", item.span) for item in rule.exceptions)
    parts.extend(("Definition", item.span) for item in rule.supporting_definitions)
    parts.extend((f"Reference {item.target}", item.span) for item in rule.dependencies)
    if rule.ambiguity_status == "review_required" and rule.section_span is not None:
        parts.insert(0, ("Review section", rule.section_span))
    retained: list[tuple[str, SourceSpan]] = []
    for label, span in parts:
        if not any(
            existing.start <= span.start and existing.end >= span.end for _, existing in retained
        ):
            retained.append((label, span))
    return retained


def _pack_rule(rule: RuleEvidence, duplicate_refs: list[str]) -> PackedEvidence:
    parts = _required_spans(rule)
    lines = [_source_label(rule)]
    for label, span in parts:
        lines.append(f"[{label}] {span.excerpt}")
    if duplicate_refs:
        lines.append("[Exact duplicate sources] " + ", ".join(sorted(set(duplicate_refs))))
    return PackedEvidence(
        rule=rule,
        retained_spans=[span for _, span in parts],
        duplicate_source_refs=sorted(set(duplicate_refs)),
        rendered_text="\n".join(lines),
    )


def render_full_document_input(firmware: FirmwareInput, documents: list[FetchedDocument]) -> str:
    """P1 comparison baseline: same instruction and code, all fetched document text."""
    line_count = firmware.content.count("\n") + (not firmware.content.endswith("\n"))
    parts = [
        INSTRUCTIONS,
        f"[Firmware {firmware.source_name}; sha256={firmware.sha256}; "
        f"lines={line_count}]\n{firmware.content}",
    ]
    parts.extend(
        f"[Document {document.source_id}; {document.source_ref}]\n{document.content}"
        for document in documents
    )
    return "\n\n".join(parts)


def pack_checker_input(
    firmware: FirmwareInput,
    selection: EvidenceSelection,
    *,
    budget_tokens: int,
    instructions_version: str,
    warnings: list[str] | None = None,
    unresolved_sections: list[UnresolvedSection] | None = None,
) -> tuple[PackedCheckerRequest | None, int]:
    """Return no checker request if complete required evidence exceeds the budget."""
    if budget_tokens < 1:
        raise ValueError("Context budget must be positive")
    selected = {rule.evidence_id: rule for rule in selection.candidate_rules}
    duplicate_refs: dict[str, list[str]] = {}
    for decision in selection.decisions:
        if "exact_duplicate_same_scope" in decision.reason_codes and decision.duplicate_of:
            duplicate_refs.setdefault(decision.duplicate_of, []).append(decision.source_ref)
    evidence = [
        _pack_rule(selected[evidence_id], duplicate_refs.get(evidence_id, []))
        for evidence_id in selection.selected_ids
    ]
    all_warnings = list(selection.warnings)
    unresolved_sections = unresolved_sections or []
    all_warnings.extend(warnings or [])
    all_warnings.extend(
        f"Missing referenced evidence: {target}" for target in selection.unresolved_dependencies
    )
    uncertain_ids = [
        decision.rule_id or decision.evidence_id
        for decision in selection.decisions
        if decision.action == "include" and decision.preserved_for_uncertainty
    ]
    if uncertain_ids:
        all_warnings.append("Review applicability: " + ", ".join(uncertain_ids))
    if not evidence:
        all_warnings.append("No source-backed rule evidence was selected.")
    location = CodeLocation(
        source_name=firmware.source_name,
        sha256=firmware.sha256,
        line_count=firmware.content.count("\n") + (not firmware.content.endswith("\n")),
    )
    parts = [
        INSTRUCTIONS,
        (
            f"[Firmware {location.source_name}; sha256={location.sha256}; "
            f"lines={location.line_count}]\n{firmware.content}"
        ),
        "[Sources]\n"
        + "\n".join(
            f"{source_id}: {source_ref}"
            for source_id, source_ref in sorted(
                {item.rule.source_id: item.rule.source_ref for item in evidence}.items()
            )
        ),
        *[item.rendered_text for item in evidence],
        *[
            f"[Unresolved section; source_id={section.source_id}; source_ref={section.source_ref}; "
            f"lines={section.span.start_line}-{section.span.end_line}]\n{section.span.excerpt}"
            for section in unresolved_sections
        ],
    ]
    if all_warnings:
        parts.append("[Warnings]\n" + "\n".join(all_warnings))
    rendered = "\n\n".join(parts)
    required_tokens = estimate_tokens(rendered)
    if required_tokens > budget_tokens:
        return None, required_tokens
    status = (
        "incomplete_context"
        if selection.unresolved_dependencies or unresolved_sections or not evidence
        else "complete"
    )
    request = PackedCheckerRequest(
        firmware=firmware,
        location=location,
        evidence=evidence,
        unresolved_sections=unresolved_sections,
        instructions_version=instructions_version,
        instructions=INSTRUCTIONS,
        warnings=all_warnings,
        status=status,
        rendered_input=rendered,
        tokenizer_version=TOKENIZER_VERSION,
        estimated_tokens=required_tokens,
    )
    return request, required_tokens
