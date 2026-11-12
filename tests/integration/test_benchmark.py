import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fcgc.cli import app
from fcgc.experiments.benchmark import load_public_benchmark
from fcgc.experiments.calibration import load_development_annotations
from fcgc.experiments.quality import DatasetValidationError, validate_dataset
from fcgc.retrieval.benchmark import BenchmarkLexicalRetriever

PROJECT = Path(__file__).resolve().parents[2]
DATASET = PROJECT / "benchmarks/v2"


@pytest.fixture
def dataset_copy(tmp_path: Path) -> Path:
    root = tmp_path / "benchmarks/v2"
    shutil.copytree(DATASET, root)
    fixture_root = tmp_path / "src/fcgc/fixtures"
    shutil.copytree(PROJECT / "src/fcgc/fixtures/benchmark_cases", fixture_root / "benchmark_cases")
    shutil.copytree(
        PROJECT / "src/fcgc/fixtures/benchmark_guidelines", fixture_root / "benchmark_guidelines"
    )
    return root


def _rewrite(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_full_benchmark_and_public_loader() -> None:
    report = validate_dataset(DATASET)
    assert (report["rules"], report["documents"], report["cases"]) == (36, 8, 24)
    assert report["provisional_annotations"] == 24

    public = load_public_benchmark(DATASET)
    assert len(public.manifest.cases) == 24
    selected = public.select_cases(development=4, heldout=8)
    assert len(selected) == 12
    assert len({case.group for case in selected}) == 6
    with pytest.raises(ValueError, match="without splitting groups"):
        public.select_cases(development=3, heldout=8)
    assert "expected_status" not in public.public_summary()
    assert "ground_truth" not in vars(public)
    assert "apply_transform" in public.case_source("C023")
    assert "[SFCG-019]" in public.document_source("buffers")
    annotations = load_development_annotations(DATASET)
    assert len(annotations) == 8
    development_ids = {
        case.case_id for case in public.manifest.cases if case.split == "development"
    }
    assert all(annotation.case_id in development_ids for annotation in annotations)

    retriever = BenchmarkLexicalRetriever()
    assert retriever.fetch("buffers").content == public.document_source("buffers")
    assert len(retriever.search("synthetic", 20).hits) == 8


def test_benchmark_cli_retrieval_keeps_labels_private() -> None:
    result = CliRunner().invoke(
        app,
        [
            "retrieve",
            "--case",
            "C001",
            "--strategy",
            "b0",
            "--config",
            str(PROJECT / "src/fcgc/config/benchmark.toml"),
        ],
    )
    assert result.exit_code == 0, result.output
    output = json.loads(result.stdout)
    assert output["request"]["firmware"]["case_id"] == "C001"
    assert output["documents"]
    assert all(
        doc["source_ref"].startswith("fcgc://synthetic-benchmark/") for doc in output["documents"]
    )
    assert "expected_status" not in result.stdout
    assert "ground_truth" not in result.stdout


def test_missing_status_is_rejected(dataset_copy: Path) -> None:
    path = dataset_copy / "ground_truth/development/C001.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["applicable_rules"][0]["expected_status"]
    _rewrite(path, data)
    with pytest.raises(DatasetValidationError, match="invalid annotation C001"):
        validate_dataset(dataset_copy)


def test_duplicate_rule_and_missing_source_reference_are_rejected(dataset_copy: Path) -> None:
    path = dataset_copy / "rules.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    duplicate = dict(data["rules"][0])
    duplicate["source_ref"] = "fcgc://wrong/reference"
    data["rules"].append(duplicate)
    _rewrite(path, data)
    with pytest.raises(DatasetValidationError) as captured:
        validate_dataset(dataset_copy)
    assert "duplicate rule ID: SFCG-001" in str(captured.value)
    assert "missing or incorrect source reference" in str(captured.value)


def test_broken_violation_span_is_rejected(dataset_copy: Path) -> None:
    path = dataset_copy / "ground_truth/development/C002.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["applicable_rules"][0]["violation_spans"][0]["end_line"] = 999
    _rewrite(path, data)
    with pytest.raises(DatasetValidationError, match="broken source span"):
        validate_dataset(dataset_copy)


def test_cross_split_similarity_is_rejected(dataset_copy: Path) -> None:
    source = (dataset_copy / "../../src/fcgc/fixtures/benchmark_cases/C001.c").read_text()
    target = dataset_copy / "../../src/fcgc/fixtures/benchmark_cases/C009.c"
    target.write_text(source.replace("boot_sensor", "boot_sensor_variant"), encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="near-duplicate cases cross splits"):
        validate_dataset(dataset_copy)


def test_public_input_label_exposure_is_rejected(dataset_copy: Path) -> None:
    path = dataset_copy / "../../src/fcgc/fixtures/benchmark_cases/C023.c"
    path.write_text(path.read_text() + "/* expected_status: compliant */\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError, match="ground-truth marker exposed"):
        validate_dataset(dataset_copy)


def test_public_case_path_cannot_point_to_annotations(dataset_copy: Path) -> None:
    path = dataset_copy / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cases"][0]["path"] = "ground_truth/development/C001.json"
    _rewrite(path, data)
    public = load_public_benchmark(dataset_copy)
    with pytest.raises(ValueError, match="escapes public benchmark_cases"):
        public.case_source("C001")
    with pytest.raises(DatasetValidationError, match="escapes public benchmark_cases"):
        validate_dataset(dataset_copy)
