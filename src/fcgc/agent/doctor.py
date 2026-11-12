"""Readiness facts only: discovery/configuration never implies authenticated access."""

import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

from fcgc import __version__
from fcgc.agent.skills import inspect_skills
from fcgc.checking.compliance_checker import instruction_assets
from fcgc.experiments.quality import validate_dataset
from fcgc.retrieval.local_retriever import LocalFixtureRetriever


def native_doctor(dataset_root: Path, host=None):
    facts = {}
    try:
        provider = LocalFixtureRetriever()
        results = provider.search("firmware coding guidelines C source", 3)
        for hit in results.hits:
            provider.fetch(hit.source_id)
        facts["local_retrieval"] = {"status": "ready", "search_fetch_sources": len(results.hits)}
    except (OSError, ValueError) as exc:
        facts["local_retrieval"] = {"status": "error", "reason": type(exc).__name__}
    try:
        quality = validate_dataset(dataset_root)
        facts["dataset"] = {
            "status": "ready",
            "details": quality,
            "validation_scope": "structural only; no held-out calibration",
        }
    except (OSError, ValueError) as exc:
        facts["dataset"] = {"status": "error", "reason": str(exc)}
    try:
        facts["skills"] = {
            "status": "ready",
            "files": inspect_skills(),
            "native_registration": "unverified",
        }
    except (OSError, ValueError) as exc:
        facts["skills"] = {"status": "error", "reason": str(exc)}
    executable = shutil.which("devin")
    facts["devin_runtime"] = {
        "status": "unavailable" if not executable else "connected_but_unverified",
        "executable": executable,
        "surface": "no active host detected by Python",
    }
    if executable:
        # No login, server configuration, tool invocation or broad permissions are requested.
        try:
            probe = subprocess.run(
                [executable, "skills", "list", "--trigger", "user"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            facts["devin_runtime"]["skill_discovery_exit"] = probe.returncode
            facts["devin_runtime"]["expected_names_seen"] = [
                skill["name"]
                for skill in facts.get("skills", {}).get("files", [])
                if skill["name"] in probe.stdout
            ]
            # Do not save arbitrary CLI output or MCP config containing credentials.
        except (OSError, subprocess.TimeoutExpired):
            facts["devin_runtime"]["status"] = "error"
    facts["atlassian_mcp"] = {
        "status": host.connection_status if host else "not_configured",
        "active_host_tools_visible": host is not None,
        "python_direct_access": False,
        "authenticated_live_access_verified": False,
        "environment": host.runtime if host else None,
        "provenance": "host-reported discovery" if host else "not exposed to this Python process",
    }
    _, template, skill = instruction_assets()
    facts["versions"] = {
        "fcgc": __version__,
        "skill": skill,
        "prompt": template.splitlines()[0],
        "bridge": "fcgc-host-v1",
        "schemas": "Pydantic v2; existing contracts + agent v1",
        "pydantic": version("pydantic"),
    }
    facts["checkers"] = {
        "mock": {"status": "ready", "result": "not_evaluated"},
        "synthetic_demo": {"status": "ready", "scope": "one exact single-pointer-store grammar"},
        "ollama": {"status": "not_configured", "availability_probe_performed": False},
        "devin_agent": {"status": "connected_but_unverified" if host else "unavailable"},
        "devin_api": {"status": "not_configured", "implemented": False},
    }
    facts["workflows"] = {
        "local": facts["local_retrieval"]["status"] == "ready",
        "wd_bridge": host is not None and host.connection_status == "connected_but_unverified",
        "live_verified": False,
    }
    return facts
