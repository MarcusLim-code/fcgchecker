"""Offline repository secret-pattern scan and dependency/configuration inventory.

This is a bounded pattern scan, not a vulnerability or exhaustive secret detector.
"""

import importlib.metadata
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    ".venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "runs",
    "outputs",
    "dist",
    "build",
    "wheelhouse",
}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "api_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
}


def main():
    findings, invalid, skipped = [], [], []
    scanned = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(
            part in SKIP or part.endswith(".egg-info") for part in path.relative_to(ROOT).parts
        ):
            continue
        if path.stat().st_size > 8_000_000:
            skipped.append(str(path.relative_to(ROOT)))
            continue
        try:
            content = path.read_bytes().decode("utf-8")
        except UnicodeError:
            continue
        scanned += 1
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                findings.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "kind": kind,
                        "line": content.count("\n", 0, match.start()) + 1,
                    }
                )
        if path.suffix in {".json", ".toml"}:
            try:
                json.loads(content) if path.suffix == ".json" else tomllib.loads(content)
            except ValueError:
                invalid.append(str(path.relative_to(ROOT)))
    report = {
        "scanned_text_files": scanned,
        "secret_pattern_findings": findings,
        "invalid_json_or_toml": invalid,
        "skipped_large_files": skipped,
        "python": sys.version,
        "static_type_check": "not configured in pyproject.toml",
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("fcgc", "pydantic", "typer", "tree-sitter", "tree-sitter-c")
        },
        "limitation": (
            "Pattern scan only; dependency CVE scanning requires a current advisory database."
        ),
    }
    print(json.dumps(report, indent=2))
    return int(bool(findings or invalid))


if __name__ == "__main__":
    raise SystemExit(main())
