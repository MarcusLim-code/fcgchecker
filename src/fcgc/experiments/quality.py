"""Offline benchmark integrity checks; never used by retrieval or checking adapters."""

import argparse
import hashlib
import json
import re
import tomllib
from collections import Counter
from itertools import combinations
from pathlib import Path

from pydantic import ValidationError

from fcgc.experiments.benchmark import load_public_benchmark
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever
from fcgc.schemas.benchmark import (
    BenchmarkTargets,
    CaseAnnotation,
    Coverage,
    RuleJudgement,
    SourceEvidence,
    SourceSpan,
)


class DatasetValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("\n".join(issues))


def _duplicate_values(values: list[str]) -> set[str]:
    counts = Counter(values)
    return {value for value, count in counts.items() if count > 1}


def _tokens(code: str) -> list[str]:
    code = re.sub(r"/\*.*?\*/|//[^\n]*", " ", code, flags=re.DOTALL)
    return re.findall(r"[A-Za-z_]\w*|0x[0-9A-Fa-f]+|\d+|[^\s]", code)


def _shingles(code: str, width: int = 5) -> set[tuple[str, ...]]:
    tokens = _tokens(code)
    return {tuple(tokens[index : index + width]) for index in range(len(tokens) - width + 1)}


def _similarity(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _check_span(span: SourceSpan, lines: list[str], label: str, issues: list[str]) -> bool:
    if span.start_line > span.end_line or span.end_line > len(lines):
        issues.append(f"{label}: broken source span {span.start_line}-{span.end_line}")
        return False
    return True


def _check_evidence(
    evidence: SourceEvidence, lines: list[str], label: str, issues: list[str]
) -> None:
    if _check_span(evidence, lines, label, issues):
        source = "\n".join(lines[evidence.start_line - 1 : evidence.end_line])
        if evidence.quote not in source:
            issues.append(f"{label}: evidence quote does not match source")


def _check_judgement(
    judgement: RuleJudgement, lines: list[str], label: str, issues: list[str]
) -> None:
    for evidence in judgement.source_evidence:
        _check_evidence(evidence, lines, label, issues)
    for span in judgement.violation_spans:
        _check_span(span, lines, label, issues)
    if judgement.expected_status == "violation":
        if not judgement.violation_spans:
            issues.append(f"{label}: violation has no location")
        for span in judgement.violation_spans:
            if not any(
                span.start_line <= evidence.end_line and evidence.start_line <= span.end_line
                for evidence in judgement.source_evidence
            ):
                issues.append(f"{label}: violation location has no overlapping evidence")
    elif judgement.violation_spans:
        issues.append(f"{label}: non-violation has violation locations")


def validate_dataset(root: Path, config: Path | None = None) -> dict[str, object]:
    """Validate the complete dataset, including held-out labels, without tuning on them."""
    try:
        public = load_public_benchmark(root)
    except (OSError, ValidationError) as exc:
        raise DatasetValidationError([f"invalid public benchmark: {exc}"]) from exc
    manifest = public.manifest
    catalog = public.rules
    settings_path = config or root / "benchmark.toml"
    targets = BenchmarkTargets.model_validate(tomllib.loads(settings_path.read_text()))
    issues: list[str] = []

    if catalog.dataset_version != manifest.dataset_version:
        issues.append("rule catalog and manifest dataset versions differ")
    if len(catalog.rules) < targets.minimum_rules:
        issues.append(f"only {len(catalog.rules)} rules; minimum is {targets.minimum_rules}")
    for name, values in (
        ("document source ID", [doc.source_id for doc in manifest.documents]),
        ("rule ID", [rule.rule_id for rule in catalog.rules]),
        ("case ID", [case.case_id for case in manifest.cases]),
    ):
        for value in sorted(_duplicate_values(values)):
            issues.append(f"duplicate {name}: {value}")

    document_by_id = {doc.source_id: doc for doc in manifest.documents}
    category_counts = Counter(rule.category for rule in catalog.rules)
    if len(category_counts) < 6:
        issues.append("fewer than six rule categories")
    retriever = BenchmarkLexicalRetriever()
    for doc in manifest.documents:
        try:
            public._public_path(doc.path, "benchmark_guidelines", ".md")
        except ValueError as exc:
            issues.append(str(exc))
            continue
        path = root / doc.path
        if not path.is_file():
            issues.append(f"missing document: {doc.path}")
            continue
        content = path.read_text(encoding="utf-8")
        if "not official WD requirements" not in content:
            issues.append(f"synthetic disclaimer missing: {doc.source_id}")
        expected_ref = f"fcgc://synthetic-benchmark/{path.name}"
        if doc.source_ref != expected_ref:
            issues.append(f"bad document source reference: {doc.source_id}")
        try:
            fetched = retriever.fetch(doc.source_id)
            if fetched.content != content or fetched.source_ref != doc.source_ref:
                issues.append(f"retriever source mismatch: {doc.source_id}")
        except KeyError:
            issues.append(f"retriever cannot fetch document: {doc.source_id}")

    for rule in catalog.rules:
        doc = document_by_id.get(rule.source_id)
        if doc is None or doc.scope != "benchmark_firmware":
            issues.append(f"{rule.rule_id}: missing or decoy source document")
            continue
        path = root / doc.path
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if rule.line > len(lines):
            issues.append(f"{rule.rule_id}: broken source line {rule.line}")
            continue
        line = lines[rule.line - 1].strip()
        if rule.excerpt != line or f"[{rule.rule_id}]" not in line:
            issues.append(f"{rule.rule_id}: excerpt does not match source text")
        if rule.source_ref != f"{doc.source_ref}#L{rule.line}":
            issues.append(f"{rule.rule_id}: missing or incorrect source reference")

    expected_coverage = Coverage(
        rule_categories=dict(sorted(category_counts.items())),
        document_types=dict(
            sorted(Counter(doc.document_type for doc in manifest.documents).items())
        ),
        code_behaviors=dict(
            sorted(
                Counter(behavior for case in manifest.cases for behavior in case.behaviors).items()
            )
        ),
        splits=dict(sorted(Counter(case.split for case in manifest.cases).items())),
    )
    if manifest.coverage != expected_coverage:
        issues.append("manifest coverage does not match corpus and case metadata")
    if expected_coverage.splits.get("development", 0) != targets.development_cases:
        issues.append("development case count differs from configured target")
    if expected_coverage.splits.get("heldout", 0) != targets.heldout_cases:
        issues.append("held-out case count differs from configured target")
    status_hints = re.compile(r"compliant|violat|leak|overflow|unchecked|ignored|unsafe")
    for case in manifest.cases:
        public_tags = [case.group, *case.behaviors]
        if any(status_hints.search(tag.lower()) for tag in public_tags):
            issues.append(f"ground-truth hint exposed in case metadata: {case.case_id}")

    groups: dict[str, set[str]] = {}
    source_by_case: dict[str, str] = {}
    for case in manifest.cases:
        groups.setdefault(case.group, set()).add(case.split)
        try:
            public._public_path(case.path, "benchmark_cases", ".c")
        except ValueError as exc:
            issues.append(str(exc))
            continue
        path = root / case.path
        if not path.is_file():
            issues.append(f"missing case source: {case.case_id}")
            continue
        source_by_case[case.case_id] = path.read_text(encoding="utf-8")
    for group, splits in groups.items():
        if len(splits) > 1:
            issues.append(f"matched group crosses splits: {group}")

    rule_ids = {rule.rule_id for rule in catalog.rules}
    annotation_dir = root / "ground_truth"
    actual_paths = {
        path.relative_to(annotation_dir).as_posix() for path in annotation_dir.rglob("*.json")
    }
    expected_paths = {f"{case.split}/{case.case_id}.json" for case in manifest.cases}
    for relative in sorted(expected_paths - actual_paths):
        issues.append(f"missing annotation: {relative}")
    for relative in sorted(actual_paths - expected_paths):
        issues.append(f"unlisted or mis-split annotation: {relative}")
    provisional_count = 0
    for case in manifest.cases:
        relative = f"{case.split}/{case.case_id}.json"
        if relative not in actual_paths or case.case_id not in source_by_case:
            continue
        try:
            annotation = CaseAnnotation.model_validate_json(
                (annotation_dir / relative).read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            issues.append(f"invalid annotation {case.case_id}: {exc}")
            continue
        if annotation.case_id != case.case_id:
            issues.append(f"annotation case ID mismatch: {case.case_id}")
        if annotation.dataset_version != manifest.dataset_version:
            issues.append(f"annotation dataset version mismatch: {case.case_id}")
        if annotation.annotation_version != manifest.annotation_version:
            issues.append(f"annotation version mismatch: {case.case_id}")
        source = source_by_case[case.case_id]
        if annotation.code_sha256 != hashlib.sha256(source.encode("utf-8")).hexdigest():
            issues.append(f"code hash mismatch: {case.case_id}")
        if annotation.review_status == "provisional":
            provisional_count += 1
        label_ids = [item.rule_id for item in annotation.applicable_rules]
        for rule_id in sorted(_duplicate_values(label_ids)):
            issues.append(f"duplicate rule label: {case.case_id}/{rule_id}")
        for judgement in annotation.applicable_rules:
            label = f"{case.case_id}/{judgement.rule_id}"
            if judgement.rule_id not in rule_ids:
                issues.append(f"{label}: unknown rule ID")
            _check_judgement(judgement, source.splitlines(), label, issues)

    # The public runtime inputs must not carry labels or review state.
    public_paths = [root / "manifest.json", root / "rules.json"]
    public_paths += [root / doc.path for doc in manifest.documents]
    public_paths += [root / case.path for case in manifest.cases]
    forbidden = ("expected_status", "review_status", "applicable_rules", "ground_truth")
    for path in public_paths:
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        if any(marker in content for marker in forbidden):
            issues.append(f"ground-truth marker exposed in public input: {path.name}")

    for left, right in combinations(manifest.cases, 2):
        if left.split == right.split:
            continue
        if left.case_id not in source_by_case or right.case_id not in source_by_case:
            continue
        left_source = source_by_case[left.case_id]
        right_source = source_by_case[right.case_id]
        if (
            hashlib.sha256(left_source.encode()).digest()
            == hashlib.sha256(right_source.encode()).digest()
        ):
            issues.append(f"identical cases cross splits: {left.case_id}, {right.case_id}")
        elif _similarity(_shingles(left_source), _shingles(right_source)) >= (
            targets.near_duplicate_threshold
        ):
            issues.append(f"near-duplicate cases cross splits: {left.case_id}, {right.case_id}")

    if issues:
        raise DatasetValidationError(issues)
    return {
        "dataset_version": manifest.dataset_version,
        "annotation_version": manifest.annotation_version,
        "rules": len(catalog.rules),
        "documents": len(manifest.documents),
        "cases": len(manifest.cases),
        "annotations": len(actual_paths),
        "provisional_annotations": provisional_count,
        "coverage": expected_coverage.model_dump(),
        "validation": "passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate synthetic FCG benchmark")
    parser.add_argument("root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = validate_dataset(args.root, args.config)
    except DatasetValidationError as exc:
        parser.exit(1, f"Dataset validation failed:\n{exc}\n")
    payload = json.dumps(report, indent=2) + "\n"
    if args.report is not None:
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
