---
name: "fcg-check"
description: "Run source-backed FCG checking for a C firmware file or named function using the configured local or agent-mediated WD workflow."
argument-hint: "<file.c> [--function NAME] [--mode local|wd] [--strategy b0|p1|p2|p3] [--config PATH]"
triggers: ["user", "model"]
---

# fcg-check

Check a C file, or focus on one named function, using source-backed guidelines.

## Usage

`/fcg-check examples/firmware/sensor_start.c --function start_sensor`

Required: a C file path. Optional: `--function NAME`, `--mode local|wd`,
`--strategy b0|p1|p2|p3`, `--config PATH`, `--top-k N`, `--token-budget N`,
`--deadline SECONDS`. Defaults: local mode, P3, synthetic retrieval, abstaining
mock, 12000 estimated context tokens and a 600-second workflow deadline.
For WD: `/fcg-check path/to/firmware.c --mode wd --config config/wd_agent.toml`.

Output: a saved Markdown report and structured findings, source citations,
uncertainty and resource counts under a fresh `outputs/checks/` session.
Local default results are **not_evaluated**, not successful compliance judgments.
Common errors: missing/non-C file, missing or ambiguous function, unavailable host
tools, rejected citations or insufficient/budget-exceeded context. Explain the
actual failure or uncertainty; do not infer compliance from missing evidence.

## Execute the request

Execute the user's /fcg-check request, not a suggested command list.

Read `skills/fcg_orchestration/WORKFLOW.md` from the repository root and execute its
check workflow. Reuse the canonical `skills/fcg_checking/SKILL.md`; all substantive
interpretation comes from that specification and the injected backend prompt.

Validate the file/function through the backend. Default mode is local, default
strategy P3 and default checker an abstaining mock. Explicit WD mode must use
actual existing tools in this active host, with the typed action/result loop.
Never silently substitute synthetic sources in WD mode. A missing file/function,
unavailable tool, permission failure or exhausted budget must remain explicit.

Use `fcgc agent invoke --command '<the slash invocation>' --output <fresh-audit>`;
for WD discovery add `--host <observed-host.json>`. Execute requested search/fetch
operations and submit actual results using `fcgc agent submit`. When a checking
action is pending, evaluate the frozen task using the exact canonical prompt and
submit the structured judgment. For configured separate checkers, let the backend
invoke them. Source firmware is read-only and no Confluence writes are required.

Read the saved report and present findings, original locations, normative citations,
conditions/exceptions, unresolved checks, sufficiency warnings, resource methods
and audit links. Do not fabricate severity or claim artifact-wide compliance.
