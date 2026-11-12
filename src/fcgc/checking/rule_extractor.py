"""Conservative rule candidate extraction with verbatim source provenance."""

import hashlib
import re

from fcgc.checking.document_normalizer import (
    DocumentNormalizer,
    MarkdownDocumentNormalizer,
    source_span,
    trimmed_span,
)
from fcgc.schemas.models import FetchedDocument
from fcgc.schemas.rules import (
    ContextFragment,
    NormalizedBlock,
    NormalizedDocument,
    ReferenceEvidence,
    RuleEvidence,
    RuleExtraction,
    SourceSpan,
)

EXTRACTOR_VERSION = "rule-segmenter-v1"
RULE_ID = re.compile(r"\bSFCG-\d{3}\b", re.IGNORECASE)
REFERENCE = re.compile(r"\bSFCG-\d{3}\b|\bSection\s+\d+(?:\.\d+)*\b|\b[\w-]+\.md\b", re.I)
MODAL = re.compile(
    r"\b(?:must|shall|should|required|prohibited|may only|must not|shall not)\b", re.I
)
CONDITIONAL_PERMISSION = re.compile(r"\bmay\b[^.?!]{0,120}\bonly\s+when\b", re.I)
PROHIBITION = re.compile(r"\bdo not\b", re.I)
IMPERATIVE = re.compile(
    r"^(?:Before\b[^,]{1,150},\s*)?(?:check|validate|reject|reserve|compute|require|"
    r"ensure|propagate|release|initialize|avoid|do not|never|preserve|perform|report|"
    r"retry|inspect|clear|zero|prevent|restore|apply|program|close|free|disable)\b",
    re.I,
)
ACTION = re.compile(
    r"\b(?:check|validate|reject|reserve|compute|require|ensure|propagate|release|"
    r"initialize|avoid|preserve|perform|report|retry|inspect|clear|zero|prevent|"
    r"restore|apply|program|close|free|disable)\b",
    re.I,
)
CONDITION_START = re.compile(r"^(?:if|when|for|before|after|during|on|in|where)\b", re.I)
EXCEPTION_START = re.compile(r"^(?:except\b|exception\s*:|however\b,?|unless\b)", re.I)
EXCEPTION_WORDING = re.compile(
    r"\b(?:does not apply|may be omitted|is exempt|exception does not|unless|except when)\b",
    re.I,
)
DEFINITION = re.compile(
    r"^(?:Definition\s*:\s*)?(?:In this section\s+)?"
    r"(?:(?:an|the|a)\b\s+)?([A-Za-z][A-Za-z0-9 _-]{1,50}?)\s+"
    r"(?:means|is defined as|refers to|is the)\b",
    re.I,
)
INLINE_CONDITION = re.compile(
    r"^(?:If|When|For|Before|After|During|On|In|Where)\b[^,.;]{1,180},",
    re.I,
)
LATER_CONDITION = re.compile(r"\bonly\s+when\b[^.?!]*", re.I)
INLINE_EXCEPTION = re.compile(r"\b(?:unless|except(?:\s+when|\s+for)?)\b[^.?!]*", re.I)
VAGUE = re.compile(r"\b(?:appropriately|as needed|where practical|when possible)\b", re.I)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])|;\s+(?=[A-Z])")
LIST_PREFIX = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
RULE_PREFIX = re.compile(r"^\s*\[?(SFCG-\d{3})\]?\s*[:.-]?\s*", re.I)
QUOTED_TEXT = re.compile(r'"[^"\n]*"|`[^`\n]*`')


def _operative_text(text: str) -> str:
    """Quoted example wording is not itself an operative modal verb."""
    return QUOTED_TEXT.sub(" ", text)


def _units(span: SourceSpan, content: str, *, split_semicolon: bool) -> list[SourceSpan]:
    text = span.excerpt
    matches = [
        match
        for match in SENTENCE_BOUNDARY.finditer(text)
        if split_semicolon or not match.group().startswith(";")
    ]
    boundaries = [0] + [match.end() for match in matches]
    ends = [match.start() for match in matches] + [len(text)]
    return [
        trimmed_span(content, span.start + start, span.start + end)
        for start, end in zip(boundaries, ends, strict=True)
        if text[start:end].strip()
    ]


def _statement_span(span: SourceSpan, content: str, kind: str) -> SourceSpan:
    text = span.excerpt
    shift = 0
    if kind == "list_item":
        marker = LIST_PREFIX.match(text)
        if marker:
            shift = marker.end()
            text = text[shift:]
    rule_marker = RULE_PREFIX.match(text)
    if rule_marker:
        shift += rule_marker.end()
    return trimmed_span(content, span.start + shift, span.end)


def _classify(span: SourceSpan, block: NormalizedBlock, explicit_marker: bool = False) -> str:
    text = span.excerpt.strip()
    operative = _operative_text(text)
    lower_headings = " ".join(block.heading_lineage).lower()
    if block.kind == "code" or "example" in lower_headings:
        return "example"
    if re.match(r"^(?:example\s*:|for example\b|e\.g\.)", text, re.I):
        return "example"
    if re.match(r"^(?:note\s*:|rationale\s*:|background\s*:)", text, re.I):
        return "informative"
    if re.match(r"^(?:See|Consult|Refer to)\b", text, re.I):
        return "informative"
    if DEFINITION.match(text) or re.match(r"^definition\s*:", text, re.I):
        return "definition"
    if re.search(r"\bmeans\b", operative, re.I) and not MODAL.search(operative):
        return "definition"
    if re.match(r'^"[^"]+"\s+includes\b', text, re.I):
        return "definition"
    if re.match(r"^(?:Exception\s*:|Except\b|However\b)", text, re.I):
        return "exception"
    if (
        not explicit_marker
        and RULE_ID.search(text)
        and re.search(r"\b(?:may satisfy|does not relax|exception)\b", text, re.I)
    ):
        return "exception"
    if (EXCEPTION_START.match(text) and not MODAL.search(operative)) or (
        EXCEPTION_WORDING.search(text) and not MODAL.search(operative)
    ):
        return "exception"
    if re.match(r"^The preceding requirement applies only when\b", text, re.I):
        return "condition"
    if (
        MODAL.search(operative)
        or PROHIBITION.match(operative)
        or (explicit_marker and PROHIBITION.search(operative))
        or (block.kind in {"list_item", "table_row"} and IMPERATIVE.match(operative))
        or (
            explicit_marker
            and (
                ACTION.search(operative)
                or CONDITIONAL_PERMISSION.search(operative)
                or re.search(r"\bonly after\b", operative, re.I)
            )
        )
    ):
        return "normative"
    if CONDITION_START.match(text):
        return "condition"
    if RULE_ID.search(text) or explicit_marker:
        return "ambiguous"
    return "informative"


def _reference_evidence(
    content: str, span: SourceSpan, own_id: str | None
) -> list[ReferenceEvidence]:
    references = []
    for match in REFERENCE.finditer(span.excerpt):
        if own_id is not None and match.group().upper() == own_id.upper():
            continue
        references.append(
            ReferenceEvidence(
                target=match.group(),
                span=source_span(content, span.start + match.start(), span.start + match.end()),
            )
        )
    return references


def _same_section(a: list[str], b: list[str]) -> bool:
    return a == b


def _evidence_id(document: FetchedDocument, span: SourceSpan) -> str:
    key = f"{document.source_id}|{document.source_ref}|{span.start}|{span.end}"
    return "ev-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _normative_strength(text: str, explicit_id: str | None) -> str:
    text = _operative_text(text)
    if CONDITIONAL_PERMISSION.search(text):
        return "conditional_permission"
    if re.search(r"\b(?:must not|shall not|prohibited|never|do not|reject|avoid)\b", text, re.I):
        return "prohibition"
    if re.search(r"\b(?:should|recommended)\b", text, re.I):
        return "recommendation"
    if MODAL.search(text) or IMPERATIVE.match(text) or (explicit_id and ACTION.search(text)):
        return "mandatory"
    return "uncertain"


def _inline_context(
    content: str, span: SourceSpan, pattern: re.Pattern[str], kind: str
) -> list[ContextFragment]:
    return [
        ContextFragment(
            kind=kind,
            span=source_span(content, span.start + match.start(), span.start + match.end()),
        )
        for match in pattern.finditer(span.excerpt)
    ]


def _all_references(
    content: str, statement: SourceSpan, contexts: list[ContextFragment], own_id: str | None
) -> list[ReferenceEvidence]:
    references = _reference_evidence(content, statement, own_id)
    for context in contexts:
        references.extend(_reference_evidence(content, context.span, own_id))
    seen: set[tuple[int, int]] = set()
    unique = []
    for reference in references:
        key = (reference.span.start, reference.span.end)
        if key not in seen:
            seen.add(key)
            unique.append(reference)
    return unique


def _unique_fragments(fragments: list[ContextFragment]) -> list[ContextFragment]:
    seen: set[tuple[str, int, int]] = set()
    result = []
    for fragment in fragments:
        key = (fragment.kind, fragment.span.start, fragment.span.end)
        if key not in seen:
            seen.add(key)
            result.append(fragment)
    return result


def _collect_definitions(normalized: NormalizedDocument) -> dict[str, list[ContextFragment]]:
    """Find definitions before segmentation so later definitions remain linkable."""
    content = normalized.document.content
    terms: dict[str, list[ContextFragment]] = {}
    for block in normalized.blocks:
        if block.kind == "table_row":
            continue
        for raw_span in _units(block.span, content, split_semicolon=False):
            span = _statement_span(raw_span, content, block.kind)
            if _classify(span, block) != "definition":
                continue
            match = DEFINITION.match(span.excerpt)
            if match:
                term = match.group(1).lower().strip()
                terms.setdefault(term, []).append(ContextFragment(kind="definition", span=span))
    return terms


def _mark_review(
    rule: RuleEvidence, note: str, content: str, block: NormalizedBlock
) -> RuleEvidence:
    section_start = min(
        rule.section_span.start if rule.section_span else rule.normative_span.start,
        block.span.start,
    )
    section_end = max(
        rule.section_span.end if rule.section_span else rule.normative_span.end, block.span.end
    )
    return rule.model_copy(
        update={
            "ambiguity_status": "review_required",
            "ambiguity_notes": [*rule.ambiguity_notes, note],
            "section_span": source_span(content, section_start, section_end),
        }
    )


def _deduplicate(rules: list[RuleEvidence]) -> list[RuleEvidence]:
    seen: dict[tuple[object, ...], str] = {}
    output = []
    for rule in rules:
        key = (
            " ".join(rule.normative_statement.lower().split()),
            tuple(rule.heading_lineage),
            tuple(" ".join(fragment.span.excerpt.lower().split()) for fragment in rule.conditions),
            tuple(" ".join(fragment.span.excerpt.lower().split()) for fragment in rule.exceptions),
            tuple(
                " ".join(fragment.span.excerpt.lower().split())
                for fragment in rule.supporting_definitions
            ),
            tuple((reference.target, reference.span.excerpt) for reference in rule.dependencies),
            rule.explicit_rule_id,
            rule.obligation_strength,
            rule.ambiguity_status,
            tuple(rule.ambiguity_notes),
            rule.section_span.excerpt if rule.section_span else None,
        )
        duplicate = seen.get(key)
        if duplicate is not None:
            rule = rule.model_copy(update={"duplicate_of": duplicate})
        else:
            seen[key] = rule.evidence_id
        output.append(rule)
    return output


def extract_rule_evidence(
    document: FetchedDocument,
    normalizer: DocumentNormalizer | None = None,
) -> RuleExtraction:
    """Extract candidates conservatively; review flags retain uncertain larger spans."""
    normalized = (normalizer or MarkdownDocumentNormalizer()).normalize(document)
    if normalized.document != document:
        raise ValueError("Normalizer changed the fetched document identity or wording")
    content = document.content
    rules: list[RuleEvidence] = []
    other: list[ContextFragment] = []
    review: list[ContextFragment] = []
    definitions = _collect_definitions(normalized)
    pending_conditions: list[ContextFragment] = []
    last_group: list[int] = []
    section_rules: list[int] = []
    current_heading: list[str] | None = None

    for block in normalized.blocks:
        if current_heading is not None and not _same_section(
            current_heading, block.heading_lineage
        ):
            if pending_conditions:
                review.extend(
                    ContextFragment(kind="ambiguous", span=fragment.span)
                    for fragment in pending_conditions
                )
            pending_conditions = []
            last_group = []
            section_rules = []
        current_heading = block.heading_lineage
        group: list[int] = []
        if block.kind == "table_row":
            requirement_cells = [
                cell
                for cell in block.cells
                if cell.column.lower() in {"requirement", "rule text", "guideline"}
            ]
            spans = [cell.span for cell in requirement_cells] or [block.span]
            rule_cell = next((cell for cell in block.cells if cell.column.lower() == "rule"), None)
            explicit_table_id = (
                RULE_ID.search(rule_cell.span.excerpt).group().upper()
                if rule_cell and RULE_ID.search(rule_cell.span.excerpt)
                else None
            )
            table_conditions = [
                ContextFragment(kind="condition", span=cell.span)
                for cell in block.cells
                if cell.column.lower() in {"scope", "condition", "applies when"}
            ]
            table_exceptions = [
                ContextFragment(kind="exception", span=cell.span)
                for cell in block.cells
                if cell.column.lower() in {"exception", "except"}
            ]
        else:
            spans = _units(block.span, content, split_semicolon=block.kind == "paragraph")
            explicit_table_id = None
            table_conditions = []
            table_exceptions = []

        for raw_span in spans:
            span = _statement_span(raw_span, content, block.kind)
            embedded = RULE_ID.search(raw_span.excerpt)
            leading_text = (
                LIST_PREFIX.sub("", raw_span.excerpt, count=1)
                if block.kind == "list_item"
                else raw_span.excerpt
            )
            leading_marker = bool(RULE_PREFIX.match(leading_text))
            marker_start = embedded.start() if embedded else 0
            marker_end = embedded.end() if embedded else 0
            if embedded and marker_start > 0 and raw_span.excerpt[marker_start - 1] == "[":
                marker_start -= 1
            if (
                embedded
                and marker_end < len(raw_span.excerpt)
                and raw_span.excerpt[marker_end] == "]"
            ):
                marker_end += 1
            prefix = raw_span.excerpt[:marker_start] if embedded else ""
            embedded_intro = bool(
                embedded
                and not leading_marker
                and (
                    (CONDITION_START.match(prefix.strip()) and prefix.rstrip().endswith(","))
                    or (
                        prefix.rstrip().endswith(":")
                        and re.search(r"\b(?:rule|constraint|guideline)\b", prefix, re.I)
                    )
                )
            )
            embedded_context: list[ContextFragment] = []
            if embedded_intro and block.kind != "table_row":
                if prefix.strip():
                    prefix_span = trimmed_span(
                        content, raw_span.start, raw_span.start + marker_start
                    )
                    prefix_kind = (
                        "condition" if CONDITION_START.match(prefix.strip()) else "informative"
                    )
                    fragment = ContextFragment(kind=prefix_kind, span=prefix_span)
                    other.append(fragment)
                    if prefix_kind == "condition":
                        embedded_context.append(fragment)
                span = trimmed_span(content, raw_span.start + marker_end, raw_span.end)
            explicit_marker = leading_marker or embedded_intro
            kind = _classify(span, block, explicit_marker)
            if kind != "normative":
                fragment_kind = kind if kind != "ambiguous" else "ambiguous"
                fragment = ContextFragment(kind=fragment_kind, span=span)
                other.append(fragment)
                if kind == "definition":
                    pass  # Definitions were indexed in a source-preserving prepass.
                elif kind == "condition":
                    cited_ids = {match.group().upper() for match in RULE_ID.finditer(span.excerpt)}
                    cited_targets = [
                        index
                        for index in section_rules
                        if rules[index].explicit_rule_id in cited_ids
                    ]
                    if cited_targets:
                        for rule_index in cited_targets:
                            rule = rules[rule_index]
                            rules[rule_index] = rule.model_copy(
                                update={
                                    "conditions": [*rule.conditions, fragment],
                                    "dependencies": _all_references(
                                        content,
                                        rule.normative_span,
                                        [
                                            *rule.conditions,
                                            fragment,
                                            *rule.exceptions,
                                            *rule.supporting_definitions,
                                        ],
                                        rule.explicit_rule_id,
                                    ),
                                }
                            )
                    elif last_group and re.match(r"^The preceding requirement", span.excerpt, re.I):
                        for rule_index in last_group:
                            rule = rules[rule_index]
                            rules[rule_index] = _mark_review(
                                rule.model_copy(
                                    update={"conditions": [*rule.conditions, fragment]}
                                ),
                                "Later condition attached by proximity; confirm its scope.",
                                content,
                                block,
                            )
                    else:
                        pending_conditions.append(fragment)
                elif kind == "exception":
                    cited_ids = {match.group().upper() for match in RULE_ID.finditer(span.excerpt)}
                    cited_targets = [
                        index
                        for index in section_rules
                        if rules[index].explicit_rule_id in cited_ids
                    ]
                    targets = cited_targets or group or last_group
                    if targets:
                        for rule_index in targets:
                            rule = rules[rule_index]
                            amended = rule.model_copy(
                                update={
                                    "exceptions": [*rule.exceptions, fragment],
                                    "dependencies": _all_references(
                                        content,
                                        rule.normative_span,
                                        [
                                            *rule.conditions,
                                            *rule.exceptions,
                                            fragment,
                                            *rule.supporting_definitions,
                                        ],
                                        rule.explicit_rule_id,
                                    ),
                                }
                            )
                            if len(targets) > 1 or (not group and not cited_targets):
                                amended = _mark_review(
                                    amended,
                                    "Later exception attached by proximity; confirm its scope.",
                                    content,
                                    block,
                                )
                            rules[rule_index] = amended
                    else:
                        review.append(ContextFragment(kind="ambiguous", span=block.span))
                elif kind == "ambiguous":
                    review.append(ContextFragment(kind="ambiguous", span=block.span))
                continue

            own_match = RULE_ID.search(raw_span.excerpt) if explicit_marker else None
            own_id = explicit_table_id or (own_match.group().upper() if own_match else None)
            conditions = [*pending_conditions, *table_conditions, *embedded_context]
            conditions.extend(_inline_context(content, span, INLINE_CONDITION, "condition"))
            conditions.extend(_inline_context(content, span, LATER_CONDITION, "condition"))
            exceptions = [*table_exceptions]
            exceptions.extend(_inline_context(content, span, INLINE_EXCEPTION, "exception"))
            linked_definitions = [
                fragment
                for term, fragments in definitions.items()
                if re.search(rf"\b{re.escape(term)}\b", span.excerpt, re.I)
                for fragment in fragments
            ]
            notes = []
            if block.kind == "paragraph" and group and not conditions:
                preceding_conditions = rules[group[-1]].conditions
                if preceding_conditions:
                    conditions = _unique_fragments([*preceding_conditions])
                    notes.append(
                        "A preceding sentence may scope this requirement; full paragraph retained."
                    )
            if any(
                len(fragments) > 1 and re.search(rf"\b{re.escape(term)}\b", span.excerpt, re.I)
                for term, fragments in definitions.items()
            ):
                notes.append("Several definitions match this term; confirm the intended scope.")
            if VAGUE.search(span.excerpt):
                notes.append("Vague qualifier needs a firmware engineer's interpretation.")
            if block.kind == "blockquote":
                notes.append("Quoted text may not be an operative guideline.")
            if block.kind == "table_row" and not requirement_cells:
                notes.append("Table has no recognized requirement column; full row retained.")
            strength = _normative_strength(span.excerpt, own_id)
            if strength == "uncertain":
                notes.append("Normative force could not be classified reliably.")
            evidence = RuleEvidence(
                evidence_id=_evidence_id(document, span),
                source_id=document.source_id,
                source_ref=document.source_ref,
                document_version=document.document_version,
                explicit_rule_id=own_id,
                heading_lineage=block.heading_lineage,
                normative_statement=span.excerpt,
                normative_span=span,
                conditions=conditions,
                exceptions=exceptions,
                supporting_definitions=linked_definitions,
                dependencies=_all_references(
                    content,
                    span,
                    [*conditions, *exceptions, *linked_definitions],
                    own_id,
                ),
                obligation_strength=strength,
                extraction_method=f"{normalized.normalizer_version}:{block.kind}:sentence",
                ambiguity_status="review_required" if notes else "clear",
                ambiguity_notes=notes,
                section_span=block.span if notes else None,
            )
            if group and re.match(r"^(?:This|It|Such|That)\b", span.excerpt):
                previous_index = group[-1]
                previous = rules[previous_index]
                combined = source_span(content, previous.normative_span.start, span.end)
                rules[previous_index] = previous.model_copy(
                    update={
                        "evidence_id": _evidence_id(document, combined),
                        "normative_statement": combined.excerpt,
                        "normative_span": combined,
                        "conditions": _unique_fragments(
                            [*previous.conditions, *evidence.conditions]
                        ),
                        "exceptions": _unique_fragments([*previous.exceptions, *exceptions]),
                        "supporting_definitions": _unique_fragments(
                            [*previous.supporting_definitions, *linked_definitions]
                        ),
                        "dependencies": _all_references(
                            content,
                            combined,
                            [
                                *previous.conditions,
                                *evidence.conditions,
                                *previous.exceptions,
                                *exceptions,
                                *previous.supporting_definitions,
                                *linked_definitions,
                            ],
                            previous.explicit_rule_id,
                        ),
                        "ambiguity_status": (
                            "review_required"
                            if previous.ambiguity_notes or evidence.ambiguity_notes
                            else "clear"
                        ),
                        "ambiguity_notes": [*previous.ambiguity_notes, *evidence.ambiguity_notes],
                        "section_span": (
                            block.span
                            if previous.ambiguity_notes or evidence.ambiguity_notes
                            else previous.section_span
                        ),
                    }
                )
            else:
                group.append(len(rules))
                section_rules.append(len(rules))
                rules.append(evidence)
        if group:
            last_group = group
            pending_conditions = []
        # Keep the previous group through explanatory prose. A later exception
        # is retained and explicitly marked review-required when attached.

    if pending_conditions:
        review.extend(
            ContextFragment(kind="ambiguous", span=fragment.span) for fragment in pending_conditions
        )
    return RuleExtraction(
        normalized=normalized,
        extractor_version=EXTRACTOR_VERSION,
        rules=_deduplicate(rules),
        other_fragments=other,
        review_sections=review,
    )


def extract_documents(
    documents: list[FetchedDocument],
    normalizer: DocumentNormalizer | None = None,
) -> list[RuleExtraction]:
    """Flag exact duplicate candidates across documents without collapsing evidence."""
    results = [extract_rule_evidence(document, normalizer) for document in documents]
    all_rules = _deduplicate([rule for result in results for rule in result.rules])
    offset = 0
    output = []
    for result in results:
        count = len(result.rules)
        output.append(result.model_copy(update={"rules": all_rules[offset : offset + count]}))
        offset += count
    return output
