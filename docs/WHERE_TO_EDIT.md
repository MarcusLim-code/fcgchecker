# I want to change something. Which file should I open?

Start with the file that owns the behavior, then follow its input/output in the
[file interaction map](FILE_INTERACTION_MAP.md). This document gives navigation
and suggestions only. **No application code was changed for this walkthrough.**
For general directory ownership use the existing [directory guide](DIRECTORY_GUIDE.md);
for setup use the [developer guide](DEVELOPER_GUIDE.md).

All source paths below are repository-relative. Test commands use the installed
local environment, for example `.venv/bin/pytest -q tests/integration/test_feature_planning.py`.
Run the complete suite before accepting a change across boundaries.

| I want to… | Main file / entry point | Also inspect | Relevant verification |
| --- | --- | --- | --- |
| Change how firmware features are detected | `src/fcgc/checking/feature_extractor.py::extract_features()` | `src/fcgc/schemas/stage3.py`; `src/fcgc/checking/function_scope.py` reuses parser helpers | `tests/integration/test_feature_planning.py`, `test_devin_workflows.py` |
| Change FCG query generation | `src/fcgc/retrieval/query_planner.py::FCGQueryPlanner.plan()` | Package `src/fcgc/config/feature_concepts_v2.json`, `p1_templates_v2.toml`; constructor options versus native wiring | `test_feature_planning.py`, `test_retrieval_providers.py`; rerun development B0/P1 comparison |
| Change how Confluence paragraphs are interpreted | `src/fcgc/checking/rule_extractor.py::extract_rule_evidence()` | `src/fcgc/checking/document_normalizer.py`, `src/fcgc/schemas/rules.py`; actual host format mapping in `src/fcgc/agent/session.py` | `test_rule_extraction.py`, `test_audit_regressions.py`, `test_context_reduction.py`; provenance/exception tests and new development experiment |
| Support another document representation | `src/fcgc/checking/document_normalizer.py::DocumentNormalizer` | `src/fcgc/schemas/agent.py::AgentToolResult`, shared orchestration workflow; HTML/ADF conversion currently absent | `test_rule_extraction.py`, `test_devin_workflows.py`; verify exact source spans on representative authorized content |
| Change which evidence is retained | `src/fcgc/checking/context_reducer.py::RuleContextReducer.reduce()` | Package `src/fcgc/config/p2_reduction_v1.toml`; packer required spans and references | `test_context_reduction.py`, `test_audit_regressions.py`; development P1/P2 recall-loss and token analysis |
| Change fallback behavior | `src/fcgc/retrieval/adaptive_retrieval.py::assess_sufficiency()`, `fallback_queries()`, `run_p3()` | Package `src/fcgc/config/p3_fallback_v1.toml`; `runner.execute_strategy()` budget overrides; agent physical-call limits | `test_adaptive_fallback.py`, `test_devin_workflows.py`; bounded-call/error tests and P2/P3 development comparison |
| Change checking instructions | `skills/fcg_checking/SKILL.md`, `skills/fcg_checking/prompt.txt` | `src/fcgc/checking/compliance_checker.py::instruction_assets()`, `render_checking_prompt()` | `test_checker_contracts.py`, `tests/end_to_end/test_release_acceptance.py`; version/hash and cross-checker validation |
| Add/change a checker provider | `src/fcgc/integrations/` using `CanonicalChecker` | `src/fcgc/config/__init__.py::Settings`, `make_checker()`; evaluator provider eligibility/control checks | `test_checker_contracts.py`, `test_audit_regressions.py`, release acceptance; same frozen task and honest provider/model metadata |
| Add a Devin slash command | `.agents/skills/COMMAND/SKILL.md`; `src/fcgc/agent/commands.py::parse_command()` / `invoke()` | `src/fcgc/agent/skills.py` supported names; `src/fcgc/agent/cli.py`; `skills/fcg_orchestration/WORKFLOW.md`; packaging data-files | `test_devin_workflows.py`; actual native recognition requires the target host |
| Change checker output format | `src/fcgc/schemas/checking.py::RuleFinding`, `ModelFindings`, `CheckingResult`, `validate_findings()` | Prompt schema injection, `src/fcgc/schemas/agent.py::AgentJudgment`, adapters, `session.render_report()`, evaluator | Checker/Devin/evaluation/audit tests; migrate versioned contracts and inspect replay implications |
| Add a research metric | `src/fcgc/experiments/metrics.py`; aggregation in `evaluation.py` | `statistics.py`, `write_reports()` and `tests/fixtures/evaluation_known.json` | `test_evaluation.py`; manually verified values, missing/zero/duplicate cases and grouped repetition tests |
| Add an experiment | `research/experiments/` | `src/fcgc/schemas/stage9.py::ExperimentConfig`, `runner.load_experiment()` / `make_lock()`; matching evaluation config | `test_experiments.py`, `test_evaluation.py`; fresh development output, locked common controls |
| Add a synthetic FCG test case | `src/fcgc/fixtures/benchmark_cases/`; `benchmarks/v2/manifest.json` | Separate annotation and code hash, matched group/split, version; guidelines/catalog if rules change; dataset review guide | `test_benchmark.py`, `quality.validate_dataset()` and relevant component tests; independent provisional-label review |
| Change WD integration settings | Root `config/wd_agent.toml`; command `--mode wd` | Host-observed `HostContext` JSON; `src/fcgc/agent/session.py::start_session()`; actual tool schema/permissions | `test_devin_workflows.py`; authorized native discovery, source provenance and small live check still required |
| Investigate a failed check | Saved `result.json`, `report.md`, `session.json`; `src/fcgc/agent/session.py::advance()` / `submit_result()` | Pending action and receipt, task/trace when available, CLI stderr, status distinctions | Reproduce with a fresh synthetic case; relevant error/timeout/contract tests |
| Investigate a failed batch/report/replay | Experiment `summary.json`, run `trace.json`, lock and snapshot; `src/fcgc/experiments/runner.py` | `evaluation.py`, `snapshots.py`; code/instruction/source hashes and missing stages | `test_experiments.py`, `test_evaluation.py`; retain original content/version rather than bypassing guards |

The test filenames without a directory prefix above are under `tests/integration/`.
These are actual files; no `models/CodeArtifact.py` or `EvidenceBundle` class exists.
Use `FirmwareInput`, `EvidenceSelection`/`PackedCheckerRequest` and
`FrozenCheckingTask` in their actual schema modules.

## Which changes require another experiment?

Changes to extraction, mappings/templates, ranking/scope, segmentation, reduction,
sufficiency thresholds, budgets, prompt/skill text, model/settings or data versions
can affect retrieval or checking outcomes. Test their contracts, then run controlled
**development** comparisons with fresh locks and declared costs. Freeze calibrated
margins before held-out evaluation. Do not change labels to match new predictions.

A report-layout-only change still needs saved-trace/report validation, especially
for unavailable metrics and eligibility. An import/layout change needs public-import,
installed-package, resource lookup and replay checks. Exact replay guards recorded
code and instructions; keep the old release rather than rewriting its hashes.
The present task made none of these application changes.

## Diagnose in the order the system ran

1. **Did Python start?** Check host command recognition and CLI stderr. Missing files,
   bad arguments or unavailable host facts may fail before any output directory exists.
2. **Is a host action pending?** `retrieval_required` and `checking_required` are
   instructions to the agent, not failure or compliance judgments. Match action/session hashes.
3. **Did retrieval fail?** Inspect accepted handoffs or `trace.tool_calls`, source IDs,
   query/scope, errors and partial markers. Never invent missing source data.
4. **Is context incomplete?** Check `pipeline.selection`, missing dependencies,
   sufficiency reasons, `stop_reason`, pack budget and final prompt budget.
5. **Did the checker execute?** Distinguish not_evaluated, unavailable, error and
   evaluated. Read uncertainty/citations; zero violations with no evaluated rules is not compliance.
6. **Did reporting fail?** Check dataset/annotation/control hashes, split, missing
   run files and frozen held-out margins. Saved reports do not automatically rerun work.

Do not edit `outputs/`, `runs/`, historical `release/`, cached build files or ground
truth to make an outcome look successful. Logs contain source code/document text;
WD storage and sharing require approved boundaries.

## Confusing areas and improvement suggestions

Ranked by likely impact on a new reader. These are analysis findings, **not changes
implemented in this documentation task**.

| Impact | Finding and evidence | Status / practical suggestion |
| --- | --- | --- |
| High | Three apparent entry points: Markdown skill, `fcgc.cli:app`, then agent CLI; no native listener exists in Python | Confirmed. Read the command/host distinction first; verify native recognition in WD, not from file presence |
| High | Native defaults are benchmark/mock/P3; plain core CLI defaults load package `config/local.toml` with older local/placeholder settings. `FCGC_CONFIG` is only read by specific Typer options, not native argument parsing | Confirmed. Use explicit native `--config`; distinguish the profiles in onboarding and any future unified-default proposal |
| High | `make_checker(devin)` returns an unimplemented stub, but native WD uses `checking_required` and `DevinAgentChecker` after host submission | Confirmed. Follow the session branch; a factory filename alone is not evidence of live inference |
| High | Host continuation restarts deterministic `perform_run()` and consumes receipts rather than continuing a suspended Python stack | Confirmed. Read `AgentMCPRetriever._call()` alongside `advance()`; separate receipt reuse from experiment replay when investigating timings |
| High | `PackedCheckerRequest` and the actual canonical `FrozenCheckingTask`/prompt are different representations. Bare pack budgets differ from runner overrides, and final serialization adds overhead | Confirmed. Inspect effective `execute_strategy()` arguments and final prompt count, not only nested TOML defaults or intermediate tokens |
| High | A `clear` rule with conditions/exceptions still contributes to `ambiguous_applicability` in the sufficiency gate | Confirmed. Treat this as conservative warning terminology. A future distinction between “has qualifiers” and “scope unresolved” needs review and development calibration, not an untested threshold change |
| High | WD mode uses the same default planner whose base query contains “synthetic”; custom planner paths exist at the library level but are not native profile fields | Confirmed local-oriented default; impact on real WD retrieval is unverified. Validate actual enterprise vocabulary and version/wire an approved template before claiming production retrieval behavior |
| Medium | Session startup, strategy execution and runner finalization can recompute features. Strategies/task preparation also repeat segmentation for different records | Confirmed source duplication of work, not duplicate algorithm definitions. Consider reuse only after measuring, while preserving diagnostic roles, hashes and receipt determinism |
| Medium | Single-file checks rely on `src/fcgc/experiments/runner.py` for the shared executor; `src/fcgc/schemas/stage9.py` imports concrete reduction/fallback configuration classes; function scope imports private extractor helpers | Confirmed coupling. Read the shared functions rather than assuming experiments run for every check. Any later separation must preserve contracts/import/replay compatibility |
| Medium | B0/P1 use `search_pipeline` validation; P3 has its own retrieval/validation loop; native WD submission adds another validation boundary | Confirmed parallel boundaries. Future contract tests should keep policies aligned; do not remove host validation or the adaptive loop merely to reduce files |
| Medium | `research/experiments/stage9_development.toml` and `stage10_development.toml` differ only in output directory | Confirmed. Annotate intended use or consolidate only after checking scripts/consumers; do not infer two different algorithm versions from filenames |
| Medium | Stage-numbered schemas, older RQ1 helper, legacy CheckerRequest, three corpus/provider names and compatibility wrappers require historical knowledge | Confirmed naming/compatibility burden. Use the concrete schema table and canonical packages. Legacy imports are tested; removal needs versioned deprecation, not cosmetic deletion |
| Medium | Successful local Markdown heuristics do not establish arbitrary Confluence conversion, enterprise rule-ID recognition or automatic pagination | Confirmed support boundaries; actual WD formats unknown. Verify real permitted pages and tool schema before choosing what converter/ID adapter is needed |
| Low | `src/fcgc/cli.py` module docstring still describes B0/P1 only although the app now exposes more workflows; old audit reports use old paths | Confirmed documentation drift. Use actual command registration/current guides; historical measured reports should retain their release identity |
| Investigation | Apparently unused legacy helpers/config V1 files and direct-provider stubs may look removable | No consumer/deployment deprecation audit was performed. `rq1.py` is still a callable utility, V1 assets may support comparisons, and direct stubs explicitly describe missing contracts. Do not label them dead or delete them without evidence |

The provider abstraction, canonical instruction layer, separate annotations and
replay hash checks deliberately support portability/research integrity. Removing
those layers would trade short-term reading simplicity for inconsistent providers,
label leakage or unverifiable comparisons. This guide recommends understanding
those boundaries, not flattening them.

## Suggested first code-reading path

Read `src/fcgc/agent/commands.py::invoke()` → `src/fcgc/agent/session.py::start_session()/advance()` →
`src/fcgc/experiments/runner.py::execute_strategy()/perform_run()` → the selected retrieval
strategy → `src/fcgc/checking/rule_extractor.py` → `context_reducer.py` →
`src/fcgc/checking/compliance_checker.py` → `src/fcgc/agent/session.py::render_report()`.
Only then read concrete schemas, host receipt validation and evaluation details
for the question you are investigating. The [diagrams](WORKFLOW_DIAGRAMS.md) keep
this path visible without requiring every helper to be memorized.

## Migration follow-up tasks

For the migration follow-up linked from the beginner walkthrough:

1. Update external scripts to the current configuration and test file locations; keep historic snapshots
   with their matching original release. No code-hash bypass is appropriate.
2. On WD, validate the target installation and actual native discovery of all five skills.
3. Discover the existing authorized MCP tools and approved scope; verify one permitted
   document's exact text, format, ID and available version before relying on extraction.
4. Review `/fcg-rules` output, then a genuine `/fcg-check` judgment and its citations.
   Approve storage, retention and model destinations first; no synthetic substitution.
5. Complete independent annotation review and approved enterprise dataset/snapshot/matrix
   support before enterprise comparisons. Live access, conversion/pagination and real-model
   behavior remain unverified or unimplemented as described above.

Use the existing [WD deployment checklist](WD_DEPLOYMENT.md) and
[WD integration contract](WD_INTEGRATION.md) for the detailed environment steps.
These are follow-up tasks, not actions performed during this documentation request.
