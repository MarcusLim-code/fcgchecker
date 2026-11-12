"""Calibration access is intentionally limited to the development split."""

from pathlib import Path

from fcgc.experiments.benchmark import load_public_benchmark
from fcgc.schemas.benchmark import CaseAnnotation


def load_development_annotations(root: Path) -> list[CaseAnnotation]:
    public = load_public_benchmark(root)
    return [
        CaseAnnotation.model_validate_json(
            (root / "ground_truth" / "development" / f"{case.case_id}.json").read_text(
                encoding="utf-8"
            )
        )
        for case in public.manifest.cases
        if case.split == "development"
    ]
