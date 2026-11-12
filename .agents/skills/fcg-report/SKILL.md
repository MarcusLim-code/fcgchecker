---
name: "fcg-report"
description: "Generate retrieval, checking and efficiency reports from saved FCGC experiment traces without rerunning retrieval."
argument-hint: "[--experiment latest|DIRECTORY|EVALUATION_CONFIG] [--runs-root PATH]"
triggers: ["user", "model"]
---

# fcg-report

Summarize saved experiments without rerunning retrieval or checking.

## Usage

`/fcg-report --experiment latest`

No argument is required. Optional: `--experiment DIRECTORY|CONFIG|latest` and
`--runs-root PATH`. Default latest searches `outputs/`, with a legacy `runs/`
archive fallback when no current evaluation config exists. To select an archive
explicitly: `/fcg-report --experiment runs/predeploy-audit-20261112/acceptance-final`.

Output: Markdown/HTML reports plus JSON and CSV metrics in a fresh
`outputs/reports/` directory. Common errors: no saved evaluation configuration,
missing/corrupt traces and mismatched data/control hashes. Do not rerun an
experiment to fill missing records. Unavailable compliance/resource metrics stay
unavailable; mock results are not validated accuracy.

## Execute the request

Execute `fcgc agent invoke --command '<the /fcg-report invocation>'
--output <fresh-report-directory>`. Read `docs/EXPERIMENTS.md` and
`docs/evaluation.md` when interpreting metrics.

Use saved records only: the backend resolves a saved evaluation JSON/TOML config,
validates versions/hashes and invokes the existing evaluator/report writer. latest
searches the selected output root (with the documented legacy fallback). Do not invoke MCP, retrieval, checking or
an experiment to fill missing records. If no saved config/traces exist or versions
fail validation, report the precise limitation. Do not fabricate values.

Present the returned data-source/checker/resource labels, retrieval quality,
compliance eligibility, incomplete observations and efficiency separately. Link
all generated Markdown, JSON, CSV and HTML artifacts. Mocks and provisional labels
must not be described as validated AI accuracy. Report per-case regressions and
small-sample limitations where relevant. Checking interpretations remain defined
by `skills/fcg_checking/SKILL.md`, not a new rubric in this skill. Keep source and
saved experiment inputs read-only; write only the new report directory.
