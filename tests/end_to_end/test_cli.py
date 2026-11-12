import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from fcgc.cli import app

runner = CliRunner()


def test_doctor_and_retrieve_and_check(tmp_path: Path) -> None:
    doctor = runner.invoke(app, ["doctor"])
    assert doctor.exit_code == 0, doctor.output
    assert json.loads(doctor.stdout)["offline_ready"] is True

    log_path = tmp_path / "runs.jsonl"
    retrieve = runner.invoke(
        app, ["retrieve", "--case", "register_access", "--strategy", "b0", "--log", str(log_path)]
    )
    assert retrieve.exit_code == 0, retrieve.output
    evidence = json.loads(retrieve.stdout)
    assert evidence["search_results"]["hits"][0]["source_id"] == "FCG-001"
    assert len(evidence["documents"]) == 3
    assert json.loads(log_path.read_text(encoding="utf-8"))["source_ids"][0] == "FCG-001"

    check = runner.invoke(app, ["check", "--case", "sensor_poll", "--strategy", "b0"])
    assert check.exit_code == 0, check.output
    checked = json.loads(check.stdout)
    assert checked["status"] == "not_evaluated"
    source = Path(__file__).resolve().parents[2] / "src/fcgc/fixtures/cases/sensor_poll.c"
    source_text = source.read_text(encoding="utf-8")
    firmware = checked["retrieval"]["request"]["firmware"]
    assert len(source_text.splitlines()) > 200
    assert "sensor_controller_irq" in source_text
    assert "sensor_controller_poll" in source_text
    assert firmware["content"] == source_text
    assert firmware["sha256"] == hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def test_custom_source_and_enterprise_boundary(tmp_path: Path) -> None:
    source = tmp_path / "custom.c"
    source.write_text("int custom(void) { return 1; }\n", encoding="utf-8")
    result = runner.invoke(app, ["retrieve", "--case", "custom", "--source", str(source)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["request"]["firmware"]["source_name"] == "custom.c"

    enterprise = Path(__file__).resolve().parents[2] / "src/fcgc/config/enterprise.toml"
    blocked = runner.invoke(app, ["retrieve", "--case", "sensor_poll", "--config", str(enterprise)])
    assert blocked.exit_code == 1
    assert "not implemented" in blocked.output
