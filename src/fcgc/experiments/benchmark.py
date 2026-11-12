"""Public benchmark loader. This module never opens ground-truth files."""

import json
from pathlib import Path

from fcgc.core.files import read_source
from fcgc.schemas.benchmark import BenchmarkManifest, CaseRecord, RuleCatalog


class PublicBenchmark:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest = BenchmarkManifest.model_validate_json(
            (root / "manifest.json").read_text(encoding="utf-8")
        )
        self.rules = RuleCatalog.model_validate_json(
            (root / "rules.json").read_text(encoding="utf-8")
        )

    def _public_path(self, relative: str, directory: str, suffix: str) -> Path:
        project_root = self.root.resolve().parents[1]
        allowed = project_root / "src" / "fcgc" / "fixtures" / directory
        resolved = (self.root / relative).resolve()
        if not resolved.is_relative_to(allowed) or resolved.suffix != suffix:
            raise ValueError(f"Benchmark path escapes public {directory}: {relative}")
        return resolved

    def case_source(self, case_id: str) -> str:
        case = next((item for item in self.manifest.cases if item.case_id == case_id), None)
        if case is None:
            raise KeyError(f"Unknown benchmark case: {case_id}")
        return read_source(self._public_path(case.path, "benchmark_cases", ".c"))

    def document_source(self, source_id: str) -> str:
        document = next(
            (item for item in self.manifest.documents if item.source_id == source_id), None
        )
        if document is None:
            raise KeyError(f"Unknown benchmark document: {source_id}")
        return read_source(self._public_path(document.path, "benchmark_guidelines", ".md"))

    def public_summary(self) -> str:
        return json.dumps(
            {
                "dataset_version": self.manifest.dataset_version,
                "case_count": len(self.manifest.cases),
                "rule_count": len(self.rules.rules),
                "coverage": self.manifest.coverage.model_dump(),
            },
            sort_keys=True,
        )

    def select_cases(self, development: int, heldout: int) -> list[CaseRecord]:
        """Select public cases deterministically while keeping related variants together."""
        selected: list[CaseRecord] = []
        for split, requested in (("development", development), ("heldout", heldout)):
            if requested < 0:
                raise ValueError("Requested case counts must be nonnegative")
            groups: dict[str, list[CaseRecord]] = {}
            for case in self.manifest.cases:
                if case.split == split:
                    groups.setdefault(case.group, []).append(case)
            chosen: list[CaseRecord] = []
            for variants in groups.values():
                if len(chosen) + len(variants) <= requested:
                    chosen.extend(variants)
                if len(chosen) == requested:
                    break
            if len(chosen) != requested:
                raise ValueError(
                    f"Cannot select {requested} {split} cases without splitting groups"
                )
            selected.extend(chosen)
        return selected


def load_public_benchmark(root: Path) -> PublicBenchmark:
    return PublicBenchmark(root)
