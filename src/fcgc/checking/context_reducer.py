"""Transparent deterministic P2 rule selection; absence of keywords is not a veto."""

import hashlib
import re
import tomllib
from importlib.resources import files
from pathlib import Path

from pydantic import Field

from fcgc.schemas.models import Contract, FetchedDocument, FirmwareInput
from fcgc.schemas.rules import RuleEvidence
from fcgc.schemas.stage3 import CodeFeatures
from fcgc.schemas.stage6 import EvidenceSelection, ReductionDecision


class CategoryTerms(Contract):
    feature: str = Field(min_length=1)
    terms: list[str] = Field(min_length=1)


class ReductionConfig(Contract):
    version: str = Field(min_length=1)
    token_budget: int = Field(ge=1)
    minimum_score: int = Field(ge=0)
    artifact_scope: str = Field(min_length=1)
    scope_exclusion_phrases: list[str]
    known_components: list[str]
    instructions_version: str = Field(min_length=1)
    categories: list[CategoryTerms]


def load_reduction_config(path: Path | None = None) -> ReductionConfig:
    raw = (
        path.read_bytes()
        if path is not None
        else files("fcgc").joinpath("config", "p2_reduction_v1.toml").read_bytes()
    )
    return ReductionConfig.model_validate(tomllib.loads(raw.decode("utf-8")))


def _document_scope(document: FetchedDocument | None) -> str:
    if document is None:
        return ""
    match = re.search(r"(?im)^Scope:\s*(.*?)(?:\n\s*\n|\Z)", document.content, re.S)
    return " ".join(match.group(1).lower().split()) if match else ""


def _explicit_api_names(rule: RuleEvidence) -> set[str]:
    text = rule.normative_statement
    names = set(re.findall(r"`([A-Za-z_]\w*_[A-Za-z_]\w*)`", text))
    names.update(re.findall(r"\b([A-Za-z_]\w*_[A-Za-z_]\w*)\s*\(", text))
    return names


def _mentions(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


class RuleContextReducer:
    def __init__(self, config: ReductionConfig | None = None) -> None:
        self.config = config or load_reduction_config()

    def reduce(
        self,
        firmware: FirmwareInput,
        features: CodeFeatures,
        candidates: list[RuleEvidence],
        documents: list[FetchedDocument],
    ) -> EvidenceSelection:
        if firmware.sha256 != hashlib.sha256(firmware.content.encode("utf-8")).hexdigest():
            raise ValueError("Firmware content hash disagrees with artifact")
        doc_by_id = {document.source_id: document for document in documents}
        if len(doc_by_id) != len(documents):
            raise ValueError("Duplicate fetched document source IDs")
        for rule in candidates:
            document = doc_by_id.get(rule.source_id)
            if document is None or document.source_ref != rule.source_ref:
                raise ValueError(f"Rule has no matching fetched source: {rule.evidence_id}")
            spans = [
                rule.normative_span,
                *(
                    fragment.span
                    for fragment in rule.conditions + rule.exceptions + rule.supporting_definitions
                ),
                *(reference.span for reference in rule.dependencies),
            ]
            if rule.section_span is not None:
                spans.append(rule.section_span)
            if any(document.content[span.start : span.end] != span.excerpt for span in spans):
                raise ValueError(f"Rule has broken source provenance: {rule.evidence_id}")
        feature_names = {category.name for category in features.inferred_categories}
        observed_calls = {call.effective_callee for call in features.observed.calls}
        component_hints = {hint.lower() for hint in features.component_hints}
        uncertain_analysis = features.analysis_mode != "tree_sitter_ast" or any(
            call.possible_indirect_call or call.macro_expanded for call in features.observed.calls
        )
        decisions: dict[str, ReductionDecision] = {}
        warnings: list[str] = []

        for rule in candidates:
            document = doc_by_id[rule.source_id]
            scope = _document_scope(document)
            text = " ".join(
                [
                    rule.normative_statement,
                    *rule.heading_lineage,
                    *(fragment.span.excerpt for fragment in rule.conditions),
                ]
            )
            reasons: list[str] = []
            score = 0
            api_names = _explicit_api_names(rule)
            if api_names & observed_calls:
                score += 4
                reasons.append("observed_api_match")
            category_matches = [
                category.feature
                for category in self.config.categories
                if category.feature in feature_names and _mentions(text, category.terms)
            ]
            if category_matches:
                score += 2 * len(category_matches)
                reasons.append("feature_category_match")
            if component_hints and _mentions(text, sorted(component_hints)):
                score += 2
                reasons.append("component_match")
            named_components = {
                component
                for component in self.config.known_components
                if re.search(rf"\b{re.escape(component)}\b", text, re.I)
            }
            component_unresolved = bool(named_components and not named_components & component_hints)
            if component_unresolved:
                reasons.append("component_applicability_unresolved")
            general = not api_names
            if general:
                score += 1
                reasons.append("general_rule_candidate")
            if rule.dependencies:
                reasons.append("has_cross_reference")
            uncertain = bool(
                rule.ambiguity_status == "review_required"
                or rule.conditions
                or rule.exceptions
                or rule.obligation_strength == "uncertain"
                or uncertain_analysis
                or component_unresolved
            )
            if uncertain:
                reasons.append("preserve_uncertain_applicability")
            scope_conflict = bool(
                scope
                and (
                    _mentions(scope, self.config.scope_exclusion_phrases)
                    or f"not {self.config.artifact_scope.lower()}" in scope
                )
            )
            if scope_conflict:
                action = "exclude"
                reasons.append("explicit_document_scope_conflict")
                explanation = (
                    "The source document explicitly declares a scope outside this firmware "
                    "artifact; "
                    "its wording and reference remain in the audit trail."
                )
            elif (
                api_names
                and observed_calls
                and not api_names & observed_calls
                and not uncertain
                and not re.search(
                    r"\b(?:such as|for example|e\.g\.|any API|all APIs|across APIs)\b",
                    rule.normative_statement,
                    re.I,
                )
            ):
                action = "exclude"
                reasons.append("specific_api_binding_unobserved")
                explanation = (
                    "The rule binds a different named API absent from parsed calls; no "
                    "macro or indirect-call uncertainty was observed. Category matches "
                    "remain logged but do not override the explicit API binding."
                )
            else:
                action = "include"
                if score < self.config.minimum_score:
                    reasons.append("low_score_retained_without_inapplicability_proof")
                    uncertain = True
                explanation = (
                    "Retained using observed API, category, component, or general-rule signals; "
                    "conditions and exceptions remain unresolved unless explicit evidence "
                    "settles them."
                )
            decisions[rule.evidence_id] = ReductionDecision(
                evidence_id=rule.evidence_id,
                rule_id=rule.explicit_rule_id,
                source_id=rule.source_id,
                source_ref=rule.source_ref,
                action=action,
                reason_codes=reasons,
                explanation=explanation,
                relevance_score=score,
                preserved_for_uncertainty=uncertain and action == "include",
                duplicate_of=rule.duplicate_of,
            )

        # References are requirements of interpretation, not relevance tie-breakers.
        by_rule_id: dict[str, list[RuleEvidence]] = {}
        for rule in candidates:
            if rule.explicit_rule_id:
                by_rule_id.setdefault(rule.explicit_rule_id.upper(), []).append(rule)
        unresolved: set[str] = set()
        changed = True
        while changed:
            changed = False
            for rule in candidates:
                if decisions[rule.evidence_id].action != "include":
                    continue
                for reference in rule.dependencies:
                    target = reference.target
                    related: list[RuleEvidence] = []
                    if re.fullmatch(r"SFCG-\d{3}", target, re.I):
                        related = by_rule_id.get(target.upper(), [])
                    elif target.lower().endswith(".md"):
                        related = [
                            candidate
                            for candidate in candidates
                            if candidate.source_ref.rsplit("/", 1)[-1].lower() == target.lower()
                        ]
                    elif target.lower().startswith("section"):
                        if rule.supporting_definitions:
                            continue
                        unresolved.add(f"{rule.evidence_id}:{target}")
                        continue
                    if not related:
                        unresolved.add(f"{rule.evidence_id}:{target}")
                        continue
                    for dependency in related:
                        decision = decisions[dependency.evidence_id]
                        if "explicit_document_scope_conflict" in decision.reason_codes:
                            unresolved.add(f"{rule.evidence_id}:{target}:scope_conflict")
                        elif decision.action == "exclude":
                            decisions[dependency.evidence_id] = decision.model_copy(
                                update={
                                    "action": "include",
                                    "reason_codes": [*decision.reason_codes, "required_dependency"],
                                    "explanation": (
                                        "Retained because a selected rule explicitly references it."
                                    ),
                                    "preserved_for_uncertainty": True,
                                }
                            )
                            changed = True

        by_evidence_id = {rule.evidence_id: rule for rule in candidates}
        for rule in candidates:
            if not rule.duplicate_of:
                continue
            decision = decisions[rule.evidence_id]
            original = by_evidence_id.get(rule.duplicate_of)
            if original is None or decision.action != "include":
                continue
            original_decision = decisions[original.evidence_id]
            same_scope = _document_scope(doc_by_id[rule.source_id]) == _document_scope(
                doc_by_id[original.source_id]
            )
            if same_scope and original_decision.action == "include":
                decisions[rule.evidence_id] = decision.model_copy(
                    update={
                        "action": "exclude",
                        "reason_codes": [*decision.reason_codes, "exact_duplicate_same_scope"],
                        "explanation": (
                            "Exact duplicate with the same stated scope; original source retained "
                            "and this source logged."
                        ),
                        "preserved_for_uncertainty": False,
                    }
                )
            elif not same_scope:
                decisions[rule.evidence_id] = decision.model_copy(
                    update={
                        "reason_codes": [
                            *decision.reason_codes,
                            "distinct_document_scope_retained",
                        ],
                        "preserved_for_uncertainty": True,
                    }
                )

        if not candidates:
            warnings.append("No normative rule candidates were extracted from fetched documents.")
        if unresolved:
            warnings.append(
                "Some selected rules refer to evidence absent from the fetched context."
            )
        ordered = [decisions[rule.evidence_id] for rule in candidates]
        return EvidenceSelection(
            config_version=self.config.version,
            candidate_rules=candidates,
            decisions=ordered,
            selected_ids=[
                decision.evidence_id for decision in ordered if decision.action == "include"
            ],
            excluded_ids=[
                decision.evidence_id for decision in ordered if decision.action == "exclude"
            ],
            unresolved_dependencies=sorted(unresolved),
            warnings=warnings,
        )
