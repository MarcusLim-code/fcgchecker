"""Validate the deliberately small YAML subset used by Devin orchestration skills."""

import hashlib
import json
import re
import sysconfig
from pathlib import Path

from pydantic import Field

from fcgc.schemas.models import Contract

NAMES = ("fcg-check", "fcg-compare", "fcg-report", "fcg-rules", "fcg-doctor")


class SkillMetadata(Contract):
    name: str = Field(pattern=r"^fcg-(check|compare|report|rules|doctor)$")
    description: str = Field(min_length=1)
    argument_hint: str = Field(alias="argument-hint", min_length=1)
    triggers: list[str]


def skill_directory():
    root = Path(__file__).resolve().parents[3] / ".agents/skills"
    return root if root.is_dir() else Path(sysconfig.get_path("data")) / "share/fcgc/agent-skills"


def inspect_skills(directory: Path | None = None):
    directory = directory or skill_directory()
    records, seen = [], set()
    for name in NAMES:
        path = directory / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise ValueError(f"Skill lacks YAML frontmatter: {name}")
        front, body = text[4:].split("\n---\n", 1)
        values = {}
        for line in front.splitlines():
            key, value = line.split(":", 1)
            if not re.fullmatch(r"[a-z-]+", key) or key in values:
                raise ValueError("Invalid/duplicate skill frontmatter field")
            # JSON strings/lists are valid YAML; no executable YAML tags or extra dependency.
            values[key] = json.loads(value)
        metadata = SkillMetadata.model_validate(values)
        if metadata.name != name or name in seen or set(metadata.triggers) != {"user", "model"}:
            raise ValueError("Skill name/discovery triggers disagree with the project convention")
        if not body.strip():
            raise ValueError("Skill workflow is empty")
        seen.add(name)
        records.append(
            {"name": name, "path": str(path), "metadata": metadata.model_dump(by_alias=True)}
        )
    return records


def orchestration_hash():
    directory = skill_directory()
    workflow = Path(__file__).resolve().parents[3] / "skills/fcg_orchestration/WORKFLOW.md"
    if not workflow.is_file():
        workflow = Path(sysconfig.get_path("data")) / "share/fcgc/orchestration/WORKFLOW.md"
    texts = [str(directory.joinpath(name, "SKILL.md").read_text()) for name in NAMES]
    return hashlib.sha256("\n".join([*texts, workflow.read_text()]).encode()).hexdigest()
