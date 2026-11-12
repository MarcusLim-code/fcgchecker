# FCGC native commands

Five project-level skills live in `.agents/skills/<command>/SKILL.md`. They execute
FCGC backend services using the host's execution tools; they do not merely print
suggested commands. They grant no extra tool permissions. The shared orchestration
workflow is `skills/fcg_orchestration/WORKFLOW.md`; canonical compliance interpretation
remains `skills/fcg_checking/SKILL.md` version 1.1.0 with prompt FCGC-PROMPT-V1.

## Engineer-facing usage

```text
/fcg-check src/flash_manager.c
/fcg-check src/flash_manager.c --function write_flash --mode wd
/fcg-check src/flash_manager.c --mode local --strategy p2 --config config/local.toml
/fcg-rules src/flash_manager.c --mode wd
/fcg-compare --case C001 --repeat 3
/fcg-compare --dataset fcgc-synthetic-v2 --repeat 3
/fcg-report --experiment latest
/fcg-doctor
```

The `flash_manager.c` paths illustrate files in the engineer's repository. Bundled
executable examples include `src/fcgc/fixtures/benchmark_cases/C001.c` and
`src/fcgc/fixtures/cases/sensor_poll.c`. Unknown files/functions fail explicitly.

| Command | Inputs and behavior | Saved outputs / failure behavior |
| --- | --- | --- |
| `/fcg-check` | C path; optional `--function`, `--mode`, `--strategy`, `--config`, `--top-k`, `--token-budget`, `--deadline` | Structured findings and Markdown report with locations/citations/uncertainty; missing evidence never becomes compliant |
| `/fcg-rules` | Same retrieval options | Requirements, conditions, exceptions, definitions, dependencies, ambiguity and include/exclude decisions; no checker invocation |
| `/fcg-compare` | `--case`, `--dataset`, `--dataset-root`, `--repeat`, `--config` or `--experiment-config` | Existing locked B0/P1/P2/P3 runner + evaluator, JSON/CSV/Markdown/HTML; matched cases kept together, development only |
| `/fcg-report` | `--experiment latest\|DIRECTORY\|EVALUATION_CONFIG`, optional `--runs-root` | Existing evaluator over saved records only; no retrieval/checking rerun; missing records/version mismatches are explicit |
| `/fcg-doctor` | Optional `--dataset-root`, `--mode` | Package/schema/instruction versions, dataset structural validity, providers, skill files and host-reported MCP/runtime readiness |

The actual dataset ID is `fcgc-synthetic-v2` (alias `synthetic_v2`). The proposed
`synthetic_v1` is not an installed benchmark and is rejected. Selecting C001 also
selects its matched C002 variant. Unknown/held-out case selections cannot silently
become development calibration. Three repetitions are the comparison default.

## Safe default profile

Mode defaults to **local**, strategy to **P3**, fixture corpus to the 36-rule Stage 2
benchmark, and checker to **mock/not_evaluated**. Context budget is 12000 estimated
tokens. P3 uses the existing 3-round / 3-search / 8-fetch / 8-candidate limits; P2
never falls back. The outer agent deadline defaults to 600 seconds (maximum 3600).
Local core P3 retains its existing 5-second soft deadline. WD core/outer deadlines
use the explicit agent deadline to accommodate real tool handoffs. All choices
are frozen in the session lock, not tuned against labels.

`--function NAME` resolves one definition with tree-sitter and retains the original
full artifact and line numbers. The checker receives explicit function focus and
out-of-focus locations are rejected. Features are conservatively extracted over
the whole file; this can retrieve extra categories and is not isolated function or
interprocedural analysis. Parse errors, ambiguous/missing definitions or invalid
identifiers fail rather than inventing a function span.

In WD mode the skill discovers **this host's** already-authorized MCP tools, passes
nonsecret host facts and handles typed actions. No synthetic fallback is allowed.
No direct Python access to a Cloud/Desktop/CLI MCP session is assumed. The default
WD checker is the active agent via validated judgment handoff; separate configured
checkers use the existing abstraction. Remote Ollama export is rejected in this
WD workflow pending an approved export adapter; loopback remains explicit opt-in.

## Execution states and reports

`retrieval_required` means invoke the pending tool action; `checking_required` means
follow the canonical frozen checking prompt; `complete` means the workflow finished;
`error` means a failed/blocked stage. Checker status remains independent:
`not_evaluated`, `evaluated`, `unavailable`, `error`. Evidence can remain
`incomplete_context` in an otherwise completed workflow. No status establishes
corpus-wide compliance. Severity is null unless supported by authoritative policy.

Every check/rules session saves a private `session.json`, `lock.json`, `result.json`
and `report.md`; pending sessions additionally save `action.json`. Final processing
saves the existing `trace.json`, `task.json` and exact `checker-prompt.json`.
Tool receipts are under `handoffs/`; local retrieval also has a content-bearing
`retrieval-snapshot.json`. Retained/excluded rule decisions and sufficiency/fallback
details remain in the existing typed pipeline trace.

The host presents the report and links, not an invented summary verdict. It includes
file/function, strategy/providers, evaluated rules, violations, original code lines,
normative citations, applicability context, unresolved checks, warnings and resources.
No LLM result exists when the mock or a blocked checker was used.

## Internal automation interface

This is the executable backend for skill hosts, test harnesses and CI. Engineers
normally enter slash commands in a supported Devin session.

```sh
.venv/bin/fcgc agent invoke --command '/fcg-check src/fcgc/fixtures/benchmark_cases/C001.c --mode local' --output outputs/checks/check-example
.venv/bin/fcgc agent invoke --command '/fcg-rules src/fcgc/fixtures/benchmark_cases/C001.c' --output outputs/checks/rules-example
.venv/bin/fcgc agent invoke --command '/fcg-compare --case C001 --repeat 1' --output outputs/checks/compare-example
.venv/bin/fcgc agent invoke --command '/fcg-report --experiment outputs/checks/compare-example' --output outputs/checks/report-example
.venv/bin/fcgc agent invoke --command '/fcg-doctor' --output outputs/checks/doctor-example
.venv/bin/fcgc agent schemas
.venv/bin/fcgc agent status --session outputs/checks/check-example
```

Use fresh output directories. Source/host/config paths are resolved in the current
working directory; experiment config paths keep their existing relative-to-config
semantics. Commands are parsed as arguments, never evaluated as shell code.
The CLI saves errors and exits nonzero on error states. Readiness diagnostics
distinguish ready, not_configured, connected_but_unverified, unavailable and error.

Live `/fcg-compare --mode wd` is **not implemented**: the existing runner protects
production captures and needs an approved enterprise dataset/snapshot-governance
adapter. It fails closed before any call; it never substitutes synthetic scores.
Individual WD checks and evidence inspection use the implemented bounded handoff.

Native slash registration and real MCP invocation cannot be verified without an
active supported Devin environment. File/frontmatter/backend tests are separate
from those live acceptance steps; see [Devin integration](DEVIN_INTEGRATION.md).
