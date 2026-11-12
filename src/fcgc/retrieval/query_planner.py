"""Versioned feature-to-guideline-concept mapping with no rule-ID lookup."""

import json
import re
import tomllib
from importlib.resources import files
from pathlib import Path

from pydantic import Field

from fcgc.schemas.models import Contract
from fcgc.schemas.stage3 import CodeFeatures, PlannedConcept, QueryPlan, SemanticCategory


class ConceptMapping(Contract):
    feature_category: str = Field(min_length=1)
    guideline_concept: str = Field(min_length=1)
    query_terms: str = Field(min_length=1)
    priority: int


class MappingFile(Contract):
    version: str = Field(min_length=1)
    mappings: list[ConceptMapping] = Field(min_length=1)


class TemplateFile(Contract):
    version: str = Field(min_length=1)
    base_query: str = Field(min_length=1)
    query_template: str = Field(min_length=1)
    max_specific_concepts: int = Field(ge=1)
    max_queries: int = Field(ge=1)
    max_api_names: int = Field(default=0, ge=0)
    max_component_hints: int = Field(default=0, ge=0)


class FCGQueryPlanner:
    def __init__(self, mapping_path: Path | None = None, template_path: Path | None = None) -> None:
        if mapping_path is None:
            mapping_raw = files("fcgc").joinpath("config", "feature_concepts_v2.json").read_text()
        else:
            mapping_raw = mapping_path.read_text(encoding="utf-8")
        if template_path is None:
            template_raw = files("fcgc").joinpath("config", "p1_templates_v2.toml").read_text()
        else:
            template_raw = template_path.read_text(encoding="utf-8")
        self.mapping = MappingFile.model_validate(json.loads(mapping_raw))
        self.template = TemplateFile.model_validate(tomllib.loads(template_raw))
        if self.template.max_queries != 1:
            raise ValueError("Stage 3 P1 supports exactly one query per case")
        if (
            "{base}" not in self.template.query_template
            or "{concepts}" not in self.template.query_template
        ):
            raise ValueError("P1 query template must include {base} and {concepts}")
        placeholders = set(re.findall(r"\{([^{}]+)\}", self.template.query_template))
        if not placeholders <= {"base", "concepts", "api_names", "components"}:
            raise ValueError("P1 query template contains an unsupported placeholder")
        if re.search(r"\bSFCG-\d{3}\b", mapping_raw + template_raw, flags=re.IGNORECASE):
            raise ValueError("Query planning configuration must not reference benchmark rule IDs")
        if not any(
            mapping.feature_category == "general_firmware" for mapping in self.mapping.mappings
        ):
            raise ValueError("P1 mapping requires a general_firmware concept")

    def plan(self, features: CodeFeatures, document_top_k: int) -> QueryPlan:
        available = {category.name: category for category in features.inferred_categories}
        matches = [
            mapping
            for mapping in self.mapping.mappings
            if mapping.feature_category in available
            and mapping.feature_category != "general_firmware"
        ]
        matches.sort(key=lambda mapping: (-mapping.priority, mapping.feature_category))
        selected = matches[: self.template.max_specific_concepts]
        general = next(
            (
                mapping
                for mapping in self.mapping.mappings
                if mapping.feature_category == "general_firmware"
            ),
            None,
        )
        if general is not None:
            available.setdefault(
                "general_firmware",
                SemanticCategory(name="general_firmware", basis=["C firmware artifact"]),
            )
            selected.append(general)
        concepts = [
            PlannedConcept(
                feature_category=mapping.feature_category,
                guideline_concept=mapping.guideline_concept,
                query_terms=mapping.query_terms,
                basis=available[mapping.feature_category].basis,
            )
            for mapping in selected
        ]
        internal = set(features.observed.function_definitions)
        api_names = sorted(
            {
                call.effective_callee
                for call in features.observed.calls
                if call.effective_callee not in internal
                and re.fullmatch(r"[A-Za-z_]\w*", call.effective_callee)
            }
        )[: self.template.max_api_names]
        components = sorted(set(features.component_hints))[: self.template.max_component_hints]
        query = self.template.query_template.format(
            base=self.template.base_query,
            concepts=" ".join(concept.query_terms for concept in concepts),
            api_names=" ".join(api_names),
            components=" ".join(components),
        ).strip()
        query = " ".join(query.split())
        if re.search(r"\bSFCG-\d{3}\b", query, flags=re.IGNORECASE):
            raise ValueError("Planned query contains a benchmark rule ID")
        return QueryPlan(
            mapping_version=self.mapping.version,
            template_version=self.template.version,
            query=query,
            concepts=concepts,
            api_names=api_names,
            component_hints=components,
            max_queries=self.template.max_queries,
            document_top_k=document_top_k,
        )
