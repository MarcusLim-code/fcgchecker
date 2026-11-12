# Human-first restructuring change map

Release **0.13.0**, validated locally on macOS arm64 / Python 3.13. The application
has been reorganized directly; this is not a proposed layout. The source still
uses the same algorithms, providers, schemas and canonical checking instructions.

## Before restructuring: current-state assessment

The initial tree mixed user provider profiles under `examples/`, research configs
under a root `experiments/`, runtime algorithms under a broad `core/`, providers
under nested `adapters/`, and stage-numbered tests with little task context.
README emphasized implementation and release history before helping a newcomer.
Generated `runs/`, `release/`, build/cache directories and frozen benchmark reports
were easy to mistake for editable project inputs. Several guides repeated the
same overview without a clear first-reading order.

The greatest usability gains were naming the three implementation areas, grouping
editable configuration and research definitions, giving tests behavior-based names,
and separating a beginner tour from technical/reference guides. There was no reason
to relocate canonical schemas, break packaged resource lookups, duplicate benchmark
data, change native skill discovery paths or rewrite working algorithms.

The checkout has no Git metadata: `git status --short` exited 128. No uncommitted
change list could be established. Before edits, a hash inventory and local state
were recorded under `outputs/restructuring-validation/before-files.json` and
`initial-state.json`. The baseline suite passed **208 tests**. No configured CI
workflows or static type checker were found. Unrelated source/data and historical
results were preserved; no destructive cache/result cleanup was performed.

## Final navigation structure

```text
README.md, START_HERE.md       Project overview and first steps
config/                       Local/WD editable provider profiles
examples/
  firmware/sensor_start.c      Small synthetic onboarding example
  guidelines/transfer.md       Contextual rule extraction example
src/fcgc/
  checking/                   Features, rule context and checking workflow
  retrieval/                  Queries, providers, B0/P1 and adaptive P3
  integrations/               Checker implementations
  agent/                      Five-command backend and typed host sessions
  experiments/                Runs, replay, metrics and statistics
  schemas/                    Stable validated contracts
  config/, fixtures/          Installed defaults and synthetic resources
  core/, adapters/            Shared utilities and legacy import forwarding
research/experiments/          Research TOML configurations
benchmarks/v2/                Versioned dataset and separate ground truth
.agents/skills/               Five supported command definitions
skills/                      Canonical checking and shared orchestration
tests/                       Unit, integration and complete workflow verification
  unit/                      Focused provider/import compatibility tests
  integration/               Named component and research contracts
  end_to_end/                CLI/release workflow and safety acceptance
  fixtures/                  Known-value evaluation fixture
docs/                        User/developer/research/navigation guides
outputs/                     Generated checks, reports, experiments and packages
```

Existing `runs/`, `release/`, `benchmarks/v2/reports/`, `build/`, `dist/`, caches and
`wheelhouse/` retain their locations. The first three are historical/reference
archives; the rest are generated/environment support. The directory guide makes
their edit policy explicit. Keeping important archives in place avoids rewriting
absolute paths, approved snapshots or historical fingerprints. New output goes to
ignored `outputs/`; no empty directories were created to mimic a target tree.

## Old location → New location

### Implementation moves

Each old Python module remains a small compatibility import pointing at the same
new module object. There is one algorithm implementation, not duplicate copies.
New application imports use the canonical destination.

| Old module | Canonical implementation |
| --- | --- |
| `fcgc.core.artifact_target` | `fcgc.checking.function_scope` |
| `fcgc.core.checking` | `fcgc.checking.compliance_checker` |
| `fcgc.core.context_packer` | `fcgc.checking.context_packer` |
| `fcgc.core.context_reducer` | `fcgc.checking.context_reducer` |
| `fcgc.core.document_normalizer` | `fcgc.checking.document_normalizer` |
| `fcgc.core.features` | `fcgc.checking.feature_extractor` |
| `fcgc.core.rule_segmentation` | `fcgc.checking.rule_extractor` |
| `fcgc.core.p2` | `fcgc.checking.reduced_context` |
| `fcgc.core.baseline` | `fcgc.retrieval.baseline` |
| `fcgc.core.query_planner` | `fcgc.retrieval.query_planner` |
| `fcgc.core.retrieval` | `fcgc.retrieval.search_pipeline` |
| `fcgc.core.p1` | `fcgc.retrieval.planned_retrieval` |
| `fcgc.core.p3` | `fcgc.retrieval.adaptive_retrieval` |
| `fcgc.adapters.retrieval.local` | `fcgc.retrieval.local_retriever` |
| `fcgc.adapters.retrieval.replay` | `fcgc.retrieval.replay_retriever` |
| `fcgc.adapters.retrieval.agent` | `fcgc.retrieval.mcp_bridge` |
| `fcgc.adapters.retrieval.atlassian` | `fcgc.retrieval.atlassian` |
| `fcgc.adapters.retrieval.benchmark` | `fcgc.retrieval.benchmark` |
| `fcgc.adapters.checker.mock` | `fcgc.integrations.mock_checker` |
| `fcgc.adapters.checker.placeholder` | `fcgc.integrations.placeholder_checker` |
| `fcgc.adapters.checker.demo` | `fcgc.integrations.synthetic_checker` |
| `fcgc.adapters.checker.local_llm` | `fcgc.integrations.ollama_checker` |
| `fcgc.adapters.checker.devin` | `fcgc.integrations.devin` |
| `fcgc.adapters.checker.devin_agent` | `fcgc.integrations.devin_agent` |

### Configuration and test moves

| Old file | New file |
| --- | --- |
| `examples/local.toml` | `config/local.toml` |
| `examples/wd.toml` | `config/wd.example.toml` |
| `examples/wd_agent.toml` | `config/wd_agent.toml` |
| `experiments/release_development.toml` | `research/experiments/release_development.toml` |
| `experiments/stage10_evaluation.toml` | `research/experiments/stage10_evaluation.toml` |
| `experiments/stage10_margins.toml` | `research/experiments/stage10_margins.toml` |
| `experiments/stage9_development.toml` | `research/experiments/stage9_development.toml` |
| `experiments/stage10_development.toml` | `research/experiments/stage10_development.toml` |
| `tests/test_baseline.py` | `tests/integration/test_baseline_pipeline.py` |
| `tests/test_local_retriever.py` | `tests/unit/test_local_retriever.py` |
| `tests/test_benchmark.py` | `tests/integration/test_benchmark.py` |
| `tests/test_stage3.py` | `tests/integration/test_feature_planning.py` |
| `tests/test_stage4.py` | `tests/integration/test_retrieval_providers.py` |
| `tests/test_stage5.py` | `tests/integration/test_rule_extraction.py` |
| `tests/test_stage6.py` | `tests/integration/test_context_reduction.py` |
| `tests/test_stage7.py` | `tests/integration/test_adaptive_fallback.py` |
| `tests/test_stage8.py` | `tests/integration/test_checker_contracts.py` |
| `tests/test_stage9.py` | `tests/integration/test_experiments.py` |
| `tests/test_stage10.py` | `tests/integration/test_evaluation.py` |
| `tests/test_agent.py` | `tests/integration/test_devin_workflows.py` |
| `tests/test_predeployment.py` | `tests/integration/test_audit_regressions.py` |
| `tests/test_release.py` | `tests/end_to_end/test_release_acceptance.py` |
| `tests/test_cli.py` | `tests/end_to_end/test_cli.py` |

## Why these changes help

- `checking/` answers “how is code/evidence interpreted?” without browsing provider code.
- `retrieval/` places the planner, lexical/replay/MCP providers and bounded fallback together.
- `integrations/` makes checker choices explicit: mock, synthetic demo, Ollama and Devin contracts.
- Root `config/` contains environment profiles; package `config/` stays internal for portable defaults.
- `research/experiments/` separates editable comparison definitions from experiment implementation and output.
- Test groups and descriptive names replace stage knowledge as the navigation mechanism.
- START_HERE and README lead with use; directory/developer/research guides answer different questions.
- Skills now explain arguments, defaults, examples, outputs and common errors while retaining existing routing.
- `outputs/` is the new working result area; generated audit/build data is excluded from packages and lint scans.

## Imports and configuration updates

The CLI, agent backend, experiment modules, provider factories, schema configuration
imports and tests now reference `fcgc.checking`, `fcgc.retrieval` and
`fcgc.integrations`. Public function/class names and `FCGRetriever` /
`ComplianceChecker` signatures are unchanged. Old module aliases preserve external
imports and patch behavior; 24 new regression cases verify module identity through
both paths. No wildcard-export copies or second implementation were introduced.

`fcgc.config` remains the loader/factory API. Profile consumers should update:

- `examples/local.toml` → `config/local.toml`.
- `examples/wd_agent.toml` → `config/wd_agent.toml`.
- `examples/wd.toml` → `config/wd.example.toml` (direct API contract, not operational).
- `experiments/*.toml` → `research/experiments/*.toml`.

Experiment dataset paths changed from `../benchmarks/v2` to `../../benchmarks/v2`
and generated output paths now resolve into `outputs/experiments/`. This changes
file locations, not the dataset, splits, provider settings, budgets or strategy
definitions. Configuration paths still resolve relative to their TOML. `.env.example`
now points at `config/local.toml`; it remains optional and is not auto-loaded.
Tests use the extra directory level when resolving the project root.

`MANIFEST.in` now includes START_HERE, new example files, root profiles and research
configs, and prunes `outputs/`. Python package discovery includes the new modules.
Ruff explicitly excludes generated/archived trees so it behaves correctly even
without Git metadata. Application source and all test groups remain checked.
The five protected `.agents/skills/*/SKILL.md` usage edits were applied after staging
and validating their contents; names/frontmatter, triggers and permission behavior
were preserved. The canonical checking skill/prompt were not changed.

## What stayed unchanged

- B0 fixed generic query; P1 planning; P2 reduction without fallback; P3 bounded fallback; optional R.
- Query templates/mappings, source scope, ranking behavior and Top-K definitions.
- Canonical contract identifiers, source/rule IDs, exact normative text and qualifiers.
- Reduction, dependency closure, uncertainty and budget-exceeded behavior.
- Same shared checking skill 1.1.0 / prompt FCGC-PROMPT-V1 across checker implementations.
- Mock not_evaluated behavior and the narrow genuine deterministic demonstration.
- Host-mediated existing MCP strategy; no independent MCP server/authentication added.
- Dataset versions, manifest, rule catalog, all labels, firmware/guideline bytes and split membership.
- Held-out isolation, evaluation-only label access, locked experiments, paired statistics and snapshots.

The protected-file inventory verifies **156 byte-identical files** across benchmark,
packaged fixtures, canonical checking instructions and reference release artifacts.
A full comparison against the prior 0.12.1 acceptance traces verifies **120/120 runs**
with identical features, queries/ranked responses, selected evidence, source hashes,
frozen checking tasks and packed input. Only release/lock hashes, paths and timings
were excluded. Evidence: `outputs/restructuring-validation/preservation-check.json`.

## Compatibility and replay

Old Python import paths continue working. Old top-level configuration/test paths
have moved; update scripts, editor launch files and explicit config arguments using
the table above. Test discovery remains rooted at `tests/`; no tests were deleted or
weakened. The named test groups now also support focused invocations.

`/fcg-report --experiment latest` searches `outputs/` first and falls back to legacy
`runs/` when no current evaluation config exists. `--runs-root runs` or an explicit
old evaluation path still selects archived records. Saved reports never rerun
retrieval/checking. Existing outputs are not rewritten to fit the new layout.

Refactoring necessarily changes code fingerprints. New 0.13.0 snapshots replay
exactly under this release. A 0.12.1 snapshot is correctly rejected by 0.13.0's
code/instruction guard (CLI exit 2); there is no unsafe bypass. The retained **0.12.1
release replayed that same old snapshot successfully**, with exact_evidence_replay=true.
Keep the original source/wheel and approved content store with historical results;
the 0.12.1 archive remains under the prior audit's `runs/…/artifacts-final/`. Transfer
it separately if historical replay is required: generated runs are not silently
bundled into the new source package. Frozen checking tasks retain their contracts
for checker-only reuse.

## Migration verification

Executed successfully from the source checkout:

```sh
.venv/bin/python -m pip install --no-index --no-deps --no-build-isolation -e .
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m compileall -q src tests scripts
.venv/bin/python -m pip check
.venv/bin/python scripts/release_checks.py
.venv/bin/fcgc agent invoke --command '/fcg-doctor' --output outputs/checks/restructure-doctor
.venv/bin/fcgc features --source examples/firmware/sensor_start.c --output outputs/checks/sensor-features.json
.venv/bin/fcgc extract-rules --document examples/guidelines/transfer.md --output outputs/checks/transfer-rules.json
.venv/bin/fcgc agent invoke --command '/fcg-check examples/firmware/sensor_start.c --function start_sensor --config config/local.toml' --output outputs/checks/sensor-start
.venv/bin/fcgc agent invoke --command '/fcg-rules examples/firmware/sensor_start.c --config config/local.toml' --output outputs/checks/sensor-rules
.venv/bin/fcgc agent invoke --command '/fcg-compare --case C001 --repeat 3 --config config/local.toml' --output outputs/experiments/command-review
.venv/bin/fcgc agent invoke --command '/fcg-report --experiment outputs/experiments/command-review' --output outputs/reports/command-review
.venv/bin/fcgc agent invoke --command '/fcg-report --experiment latest' --output outputs/reports/latest-review
.venv/bin/fcgc validate-local --dataset-root benchmarks/v2 --output outputs/validation/restructured-local
.venv/bin/python scripts/build_release.py --output outputs/packages/restructure-0.13.0
```

Use fresh output directories when repeating. Exact command arrays, exits and logs
are in `outputs/restructuring-validation/command-receipts.json`,
`quality-command-receipts.json`, `report-replay-compatibility.json` and the adjacent
stdout/stderr files. Final outcomes:

| Verification | Actual outcome |
| --- | --- |
| Complete repository suite | **232 passed**, no failures/skips (208 existing + 24 import compatibility cases) |
| Ruff lint / format | Pass; **123 files already formatted** |
| Imports / compile / dependencies | **89 modules import**; compileall pass; no broken requirements |
| Python 3.11 syntax | **108 files** parse with the 3.11 grammar; 3.11 runtime not available here |
| Five native-command backends | All execute locally; metadata validated for five skills |
| Small command comparison | **24/24 runs finished**, zero failed; matched C001/C002 × four strategies × three repeats |
| Full acceptance | **120/120 finished**, zero failed, **54 explicitly incomplete**; exact new evidence replay true |
| Checking truthfulness | All benchmark mock results not_evaluated; supported pointer good/bad genuinely evaluated by deterministic checker |
| Before/after research preservation | **120 matched traces, zero semantic differences**; 156 protected files unchanged |
| Historical replay | Old snapshot rejected by new code guard; exact replay succeeds under retained 0.12.1 |
| Fresh installation | Offline wheel install outside checkout; **232 passed in 6.93 s** from extracted source, plus diagnostics and full 120-run acceptance |
| Packaging | Source/wheel build; five native skills included, no generated outputs/private configs; final archive includes current guides |
| Secret/config scan | No selected secret-pattern findings or malformed JSON/TOML; pattern scan is not exhaustive |
| Documentation links | Local links validated in maintained guides; historical reports retain historical examples |

The isolated environment installed pinned dependencies using `--no-index --find-links`
and imported the installed wheel rather than the editable checkout. Source-only
resources/configs/tests were exercised from the extracted archive. No new dependency
was introduced. The generic Codex skill-creator validator could not run because
its optional PyYAML dependency is absent; no dependency was installed just for it.
The existing target-specific FCGC metadata validator and contract tests passed for
all five Devin skill files. This is not native Devin discovery or a live WD call.

## WD transfer readiness impact and remaining limits

The transfer status remains **ready with conditions** for authorized integration
testing. The new source archive includes the canonical skill locations and all
editable profiles/research resources. The installed wheel retains resource and
skill fallback paths; local mode still requires no WD systems or paid APIs.

Actual native Devin registration, active MCP tool discovery/authentication,
Confluence format/provenance/pagination and genuine Devin output require WD
verification. Production evidence storage/governance and enterprise experiment
matrices remain pending. No WD endpoint, tool name or model result was invented.
Linux/Windows and actual Python 3.11 runtime were not tested. No static type checker,
current CVE database, signed artifact authority or verified container was added.
Dataset labels remain provisional. Existing conservative context warnings and
fallback costs remain; the refactoring makes no new accuracy/performance claim.

Safe later cleanup candidates: review whether duplicate stage9/stage10 development
TOMLs can be consolidated after consumer review; archive old readiness explanations
under a dedicated historical-doc path only with link migration; retire old import
forwarders only through a versioned API deprecation; remove build/cache directories
only when the owner no longer needs their artifacts. None was deleted speculatively.

## How to Navigate FCGC in 60 Seconds

Read START_HERE. Use `/fcg-check <file.c>` or `/fcg-rules <file.c>` in supported Devin.
Change code/evidence interpretation in `src/fcgc/checking/`, search/planning in
`src/fcgc/retrieval/`, and checker providers in `src/fcgc/integrations/`. Research
implementation is in `src/fcgc/experiments/`, editable runs in `research/experiments/`,
and the frozen dataset in `benchmarks/v2/`. Choose WD profiles under root `config/`;
read the integration guide before live access. Find new reports under `outputs/`.
