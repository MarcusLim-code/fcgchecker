# FCGC 0.12.0 — Devin-native enhancement completion report

## Status

**Implemented and locally tested:** five command backends and project skills,
fixture/replay operation, typed agent-mediated search/fetch/checker handoff,
source-preserving core processing, function focus, controlled local comparisons,
saved-record reporting, readiness diagnostics, bounded continuation and error checks.

**Implemented but not live-verified:** Devin native skill registration/invocation,
production Atlassian tool ingestion and active-Devin judgment submission. File
validation and a CLI orchestration harness do not prove a real slash invocation.

**Blocked by enterprise access in this environment:** real WD tool discovery,
authorized MCP calls, actual Confluence representation fidelity, live model behavior,
permission enforcement and exact platform usage. Active host: Codex Desktop; no
`devin` executable or Atlassian/Confluence tools were exposed. No live call occurred.

**Not implemented:** direct Devin API transport, arbitrary Confluence ADF/HTML/storage
conversion, approved production snapshot storage/governance, enterprise dataset
adaptation and live WD experiment matrices. `/fcg-compare --mode wd` fails closed;
it never substitutes a synthetic study. Individual WD workflows have the implemented
handoff path but still require live acceptance in an authorized environment.

## Changes and architecture

The repository was upgraded in place. Existing feature extraction, query planning,
normalization/segmentation, reduction, sufficiency/fallback, packing, checking,
experiments, evaluation and replay remain the shared implementations. No server,
authentication client, vector database, commercial model call or new dependency
was added. The legacy CLI remains available for CI and deterministic experiments.

The new application layer calls the existing `perform_run` strategy executor with
optional task transformation and deferred checker execution. `AgentMCPRetriever`
consumes typed host receipts or suspends with a pending action. The existing engine
then resumes over those receipts; no second query planner/reducer/fallback is used.
`DevinAgentChecker` validates an active agent's canonical judgment without pretending
to call a direct Devin API. The original direct API stubs remain unimplemented.

Essential shared-contract extensions are an optional search score (unknown managed
scores stay null), optional frozen-task function coordinates, an optional executor
task transform and JSON config support alongside unchanged TOML semantics. Original
untargeted canonical task/prompt hashes are preserved. Strict older consumers must
upgrade for new optional scope fields; no live enterprise schema compatibility is
claimed. Function features remain conservative over the whole file; original source
and line locations are retained, and out-of-focus violation locations are rejected.

## New and modified files

New files:

```text
.agents/skills/fcg-check/SKILL.md
.agents/skills/fcg-compare/SKILL.md
.agents/skills/fcg-report/SKILL.md
.agents/skills/fcg-rules/SKILL.md
.agents/skills/fcg-doctor/SKILL.md
skills/fcg_orchestration/WORKFLOW.md
src/fcgc/agent/__init__.py
src/fcgc/agent/cli.py
src/fcgc/agent/commands.py
src/fcgc/agent/doctor.py
src/fcgc/agent/session.py
src/fcgc/agent/skills.py
src/fcgc/schemas/agent.py
src/fcgc/adapters/retrieval/agent.py
src/fcgc/adapters/checker/devin_agent.py
src/fcgc/core/artifact_target.py
tests/test_agent.py
examples/wd_agent.toml
docs/SLASH_COMMANDS.md
docs/DEVIN_INTEGRATION.md
docs/WD_DEPLOYMENT.md
docs/DEVIN_ENHANCEMENT_REPORT.md
```

Modified files:

```text
src/fcgc/__init__.py
src/fcgc/cli.py
src/fcgc/config/__init__.py
src/fcgc/schemas/models.py
src/fcgc/schemas/checking.py
src/fcgc/experiments/runner.py
src/fcgc/experiments/evaluation.py
pyproject.toml
MANIFEST.in
README.md
docs/EXPERIMENTS.md
docs/LOCAL_SETUP.md
docs/WD_INTEGRATION.md
docs/SECURITY.md
docs/LIMITATIONS.md
```

The canonical `skills/fcg_checking/SKILL.md` and `prompt.txt` were reused without
changing their 1.1.0 / FCGC-PROMPT-V1 interpretation. Generated validation evidence
is under `runs/native-final/`; installable artifacts are under `dist/`. The wheel
includes fallback shared-data skill/workflow assets; the source archive includes
the project `.agents/skills` tree. Installing a wheel alone does not register those
files in an arbitrary Devin project; transfer the source/project skills as documented.

## Skill discovery and engineer usage

```text
.agents/skills/
  fcg-check/SKILL.md
  fcg-compare/SKILL.md
  fcg-report/SKILL.md
  fcg-rules/SKILL.md
  fcg-doctor/SKILL.md
```

All five frontmatters were checked by the backend validator and independently parsed
as YAML. Names are unique and directory names match. Fields are the documented
`name`, `description`, `argument-hint`, `triggers`; user/model invocation stays
enabled. No allowed-tools, broad write, arbitrary shell or MCP permission grants
are preapproved. No duplicate `.devin/skills` definitions were created.

The convention is based on official [Devin CLI skills documentation](https://docs.devin.ai/cli/extensibility/skills/overview)
and [frontmatter reference](https://docs.devin.ai/cli/extensibility/skills/creating-skills).
The installed native runtime could not be tested because none was available here.
Use the documented `devin skills paths`, `devin skills list --trigger user` and
`devin skills show fcg-check` in the actual target CLI. Other host surfaces must
verify their own registration/invocation UI; Cloud connection sharing is not assumed.

```text
/fcg-check src/flash_manager.c --mode wd
/fcg-check src/flash_manager.c --function write_flash --mode local
/fcg-rules src/flash_manager.c --mode wd
/fcg-compare --case C001 --repeat 3
/fcg-report --experiment latest
/fcg-doctor
```

Those example firmware paths refer to the engineer's repository. Exact backend
commands executed locally, with all five exit codes zero:

```sh
.venv/bin/fcgc agent invoke --command '/fcg-check src/fcgc/fixtures/benchmark_cases/C001.c --mode local' --output runs/native-final/check
.venv/bin/fcgc agent invoke --command '/fcg-rules src/fcgc/fixtures/benchmark_cases/C001.c' --output runs/native-final/rules
.venv/bin/fcgc agent invoke --command '/fcg-compare --dataset fcgc-synthetic-v2 --repeat 3' --output runs/native-final/compare
.venv/bin/fcgc agent invoke --command '/fcg-report --experiment runs/native-final/compare' --output runs/native-final/report
.venv/bin/fcgc agent invoke --command '/fcg-doctor' --output runs/native-final/doctor
```

Use fresh output directories for another run. See [SLASH_COMMANDS.md](SLASH_COMMANDS.md)
for all arguments, defaults, statuses and failure behavior. The normal local default
is P3 plus mock/not_evaluated, not an AI-compliance model. WD mode requires actual
host discovery and never silently uses local rules.

## MCP-to-Python handoff

1. The core generates a versioned `RetrievalQuery` and a pending `AgentAction`.
2. Devin discovers its actual authorized search/fetch tools and schemas and supplies
   only nonsecret `HostContext` facts. No Python access to that connection is assumed.
3. Devin invokes the pending real tool, maps its actual response in returned order
   into canonical source models, and submits bounded `AgentToolResult` JSON.
4. Python validates IDs, query, Top-K, scope, source identity, timestamps, environment,
   receipts and limits, then reuses existing segmentation/reduction/sufficiency.
5. P3 returns another action only when the unchanged core requests fallback. P2 does
   not. Permission/authentication failures stop; transport retries default to zero.
6. For agent checking, the exact frozen task and canonical prompt are presented to
   Devin. `AgentJudgment` must match their hashes and schema. Existing validation
   rejects fabricated citations, missing/unknown rule IDs and wrong code locations.
7. Structured results, readable reports, source context and audit metrics are saved
   inside the approved workspace. Incomplete evidence never becomes compliant.

No raw credentials, guessed tool names or unnecessary Confluence content are part
of the protocol. Only actual tool-provided Markdown/plain text is currently accepted
as normalized source. Host receipts are attestations, not signatures or independent
proof of live access. Synthetic test receipts require explicit opt-in and remain
labeled `synthetic_contract_test`. See [DEVIN_INTEGRATION.md](DEVIN_INTEGRATION.md).

## Tests and actual demonstrations

Final full suite: **174 passed in 6.77s** (129 prior tests retained, 45 new tests).
The test run includes unit, integration, CLI, provider contracts and end-to-end cases.
Saved outputs: `runs/native-final/validation.json` and command receipts alongside it.

| Command/check | Actual result |
| --- | --- |
| `.venv/bin/pytest -q` | 174 passed |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check src tests scripts` | 92 files already formatted |
| `.venv/bin/python -m compileall -q src tests scripts` | Exit 0 |
| `.venv/bin/python -m pip check` | No broken requirements |
| `.venv/bin/python scripts/release_checks.py` | No selected secret-pattern / JSON/TOML syntax findings |
| Independent YAML parse | All five skill frontmatters valid |
| Five command backends | All exited 0; saved check/rules/compare/report/doctor outputs |
| Existing retrieval replay | Exact evidence replay true; checker not_evaluated |
| Offline package build/install | Wheel and source archive built; isolated wheel commands passed using local pinned dependencies |

New tests cover registration/frontmatter and argument handling; offline shared-core
execution and replay; missing files/functions and invalid K; function line fidelity;
inspection without checking; synthetic search/fetch/checker handoff; empty results;
wrong/missing refs, identities, tools, providers and scope; timezone-aware receipts; malformed,
duplicate-key and oversized JSON; credential-bearing errors; permission/auth stops;
timeout-driven bounded fallback; incomplete context; receipt integrity and locked read-only inputs;
cross-workspace/context rejection; unsupported citations; unavailable local model;
no fabricated scores/usage/severity; report generation without retrieval; shared
instruction hashes and controlled development comparison. Existing label-isolation
and held-out tests continue to pass.

A separate synthetic contract driver passed one search, one fetch and a canonical
judgment through the WD-mode handoff with explicit test opt-in. It detected the
supported pointer violation using the genuine deterministic demonstration checker
to supply a simulated agent judgment. The result is labeled simulated_devin_agent /
synthetic_contract_test, with `live_access_verified_by_python=false`. It is **not**
an actual Devin reasoning result, live MCP call or enterprise accuracy measurement.

Native slash invocation itself could not run. Static type checks are not configured.
The unchanged dependencies were installed from the existing target-specific wheelhouse;
no new dependency/advisory freshness or cross-platform validation claim is made.

## Research compatibility results

The native comparison used the existing runner/evaluator on 8 development cases,
3 repetitions and B0/P1/P2/P3: **96 finished, 0 failed, 30 incomplete-context runs**.
All 96 checker results were mock/not_evaluated. Canonical instructions remained
identical, source/rule citations were preserved and no held-out labels were used for
calibration. Reports were generated from saved traces without rerunning retrieval.

| Strategy | Mean fetched Recall@18 | Mean prepared input-token estimate | Mean search / fetch calls |
| --- | ---: | ---: | --- |
| B0 | 0.4375 | 5717.875 | 1 / 3 |
| P1 | 0.9167 | 6644.625 | 1 / 3 |
| P2 | 0.9167 | 5534.625 | 1 / 3 |
| P3 | 0.9167 | 7513.000 | 3 / 5.375 |

These reproduce the prior local strategy behavior, not a new claim about WD ranking.
The canonical rule is the evaluation unit; document K=3 differs from rule K=18.
P3 incurred extra cost without recall gain and retained insufficient-evidence
warnings. Provisional labels, four matched groups and an unexecuted mock prevent
validated downstream accuracy claims. Provider tokens/billing/credits stay unavailable;
token numbers are named local estimates. Native bridge wall time, cumulative backend
re-execution and optional host durations are separate and not interchangeable with
managed MCP latency. Local timing runs may overlap other validation jobs.

Saved comparison reports:

- `runs/native-final/compare/evaluation/report.md` and `report.html`
- `metrics.json`, `summary.csv`, `runs.csv`, `paired.csv`
- `runs/native-final/report/` — reports regenerated from those saved records
- `runs/native-final/replay/` — exact saved P3 evidence replay
- `runs/native-final/bridge-contract/` — explicitly simulated handoff demonstration

## Remaining WD verification tasks

- Verify project discovery and one real slash invocation in the actual WD runtime.
- Confirm actual authorized Atlassian tool names/schemas and source permissions in
  that same host; do not create another server or independently reauthenticate.
- Perform an approved live search/fetch and review real source identity/version,
  normalized content fidelity, paragraph context and cross-references.
- Approve artifact storage/access/retention and model choices; keep proprietary
  evidence inside approved infrastructure. Implement any required conversion or
  export adapter before using unsupported formats/providers.
- Validate an actual Devin judgment against the canonical task and exposed metadata;
  exercise access failures, partial results, timeouts, budgets and uncertainty.
- Add independently reviewed enterprise labels/datasets and an approved production
  experiment storage adapter before attempting WD accuracy comparisons. Calibrate
  on development only, then freeze controls before held-out evaluation.

The local enhancement is complete and executable within its stated scope.
**Full live WD operation remains unverified; the unimplemented production adapters
listed above remain explicit.** The earlier 0.11.0 release report is historical;
this report describes the native 0.12.0 enhancement.
