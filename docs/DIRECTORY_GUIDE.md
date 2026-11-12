# Directory guide

Start with [START_HERE](../START_HERE.md). This guide is for choosing a file to
read or change; it is not a second architecture specification.

## Application source

All Python application code lives under `src/fcgc/`. The installed entry point is
`fcgc`, implemented by `cli.py`. Engineers normally use the five Devin skills;
`agent/commands.py` routes them into the same implementation.

| Directory | What and why | Who edits it, and when | Dependencies |
| --- | --- | --- | --- |
| `checking/` | Firmware observations, rule extraction and source-preserving checking context | Maintainers adding C observations, segmentation, reduction or checking behavior | Schemas, shared file utilities and retrieval outputs; never labels |
| `retrieval/` | Query planning, retrieval providers and bounded strategies | Maintainers changing how evidence is searched, fetched or broadened | Schemas, internal versioned mappings; checker results do not guide retrieval |
| `integrations/` | Mock, bounded synthetic, optional Ollama and future/agent Devin checker implementations | Provider authors adding or adapting a checker | Canonical checking workflow and supplied evidence, not ground truth |
| `agent/` | Native-command argument parsing, host handoff, session validation and reports | Integration maintainers changing command orchestration or host envelopes | Existing retrieval/checking/experiment core; shared skill workflow |
| `experiments/` | Controlled runner, snapshots, metrics, statistics and post-hoc reporting | Researchers or maintainers extending evaluation | Runtime contracts plus evaluation-only benchmark/annotation access |
| `schemas/` | Pydantic contracts and stable canonical identifiers | Contract owners when data boundaries change | Some configuration types; changes need contract/replay review |
| `config/` | Shipped defaults, retrieval concepts/templates and reduction/gate policy | Maintainers deliberately versioning runtime behavior | Used by installed packages; distinct from root environment profiles |
| `fixtures/` | Installed synthetic firmware, guidelines, replay and checking fixtures | Dataset/test maintainers through reviewed fixture changes | Benchmark source spans/hashes and packaged offline providers |
| `core/` | Shared input safety/interfaces plus forwarding imports for moved modules | Shared-contract maintainers; otherwise follow the named implementation | Compatibility paths are not a second implementation |
| `adapters/` | Forwarding imports for older checker/retrieval provider paths | Compatibility maintainers only | Points into `retrieval/` and `integrations/` |

Useful files:

| Task | Implementation |
| --- | --- |
| Extract observed C syntax and inferred categories | `checking/feature_extractor.py` |
| Resolve a requested function without changing source coordinates | `checking/function_scope.py` |
| Normalize Markdown and segment contextual requirements | `checking/document_normalizer.py`, `checking/rule_extractor.py` |
| Select evidence and retain mandatory context | `checking/context_reducer.py`, `checking/context_packer.py` |
| Freeze a task, render instructions and validate findings | `checking/compliance_checker.py` |
| Generate feature-aware queries | `retrieval/query_planner.py` |
| Rank synthetic documents or replay search/fetch | `retrieval/local_retriever.py`, `retrieval/replay_retriever.py` |
| Service host-mediated MCP requests | `retrieval/mcp_bridge.py`, `agent/session.py` |
| Follow B0/P1/P2/P3 | `retrieval/baseline.py`, `retrieval/planned_retrieval.py`, `checking/reduced_context.py`, `retrieval/adaptive_retrieval.py` |
| Add a metric or report field | `experiments/metrics.py`, `evaluation.py` and `statistics.py` |

## Project resources

| Path | Purpose and edit policy | Depends on |
| --- | --- | --- |
| `.agents/skills/` | Five human-facing command definitions. Skill maintainers edit usage/routing without changing permission policy | Actual Devin discovery conventions, `agent/` and shared orchestration |
| `skills/fcg_checking/` | Authoritative versioned checking skill and provider-independent prompt. Change deliberately, not for one model | Frozen task/result contracts and citation validation |
| `skills/fcg_orchestration/` | Shared agent workflow, separate from normative interpretation | Host discovery and typed session actions |
| Root `config/` | Editable local and WD templates. Users choose a profile here; no secrets in committed examples | Existing `fcgc.config` loader and provider factories |
| `examples/` | Small introductory C/Markdown files. Add synthetic examples for onboarding | No labels; packaged benchmark fixtures remain authoritative research inputs |
| `research/experiments/` | Editable experiment/evaluation/margin definitions. Researchers configure runs here | `benchmarks/v2/`, common providers and output paths relative to each TOML |
| `benchmarks/v2/` | Versioned public manifest, rule catalog, isolated ground truth and review guide. Dataset owners change through versioned review | Packaged source corpus/firmware and exact spans/hashes |
| `tests/unit/` | Focused provider/import checks | Small test inputs, no enterprise access |
| `tests/integration/` | Component boundaries, benchmark, checker/MCP contracts, experiments and evaluator | Synthetic fixtures; test files are named for behavior rather than stages |
| `tests/end_to_end/` | CLI and full release workflow acceptance, including safety regressions | The installed application and public synthetic resources |
| `tests/fixtures/` | Hand-verified arithmetic predictions for metrics | Separate from runtime predictions and benchmark labels |
| `docs/` | Focused maintained guides; historical readiness reports are labeled in the index | Actual implementation and recorded verification |
| `scripts/` | Offline build and repository checks | Pinned build/development tools; no application algorithms |

The benchmark stays at `benchmarks/v2/` because its manifest, ground truth and
recorded experiments use fixed relative paths. `research/` supplies the working
experiment entry point without duplicating or casually renaming the dataset.
Schema filenames `stage3.py`, `stage6.py`, `stage7.py`, `stage9.py` remain stable
historical contracts: features/plans, reduction, sufficiency, experiment traces.

## Generated files and archives

New output is directed to ignored `outputs/`: `checks/` for evidence/findings,
`experiments/` for locked comparisons, `reports/` for saved-trace reports,
`packages/` for builds, and `restructuring-validation/` for this migration's receipts.
Subdirectories are created when used, not as empty scaffolding. A comparison
keeps its experiment and evaluation together so the saved relative paths work.

Existing `runs/`, `release/` and `benchmarks/v2/reports/` remain frozen reference
archives. Some are consumed by compatibility tests; do not edit them to improve a
score. Existing absolute audit paths are historical evidence, not live defaults.
`build/`, `dist/`, `.venv/`, caches and `wheelhouse/` are tool/environment products.
Do not edit them. The clean build helper does not trust stale `build/lib` contents.

## Where should a new feature go?

- New firmware observation → `checking/feature_extractor.py`; separate observed facts from inference.
- New guideline structure → normalizer/rule extractor, plus qualifier/provenance tests.
- New query concept → versioned mappings in package `config/`; planning behavior in `retrieval/`.
- New retrieval provider → `retrieval/`, satisfying `FCGRetriever` and source/scope contracts.
- New checker provider → `integrations/`, reusing canonical instructions/validation.
- New research metric/report → `experiments/`; no evaluation labels in runtime code.
- New Devin command → supported `.agents/skills/` definition plus `agent/` routing.
- New example → `examples/`; new benchmark case → versioned dataset review, not an unreviewed example copy.
- New test → the smallest suitable test group; keep associated fixture data under `tests/fixtures/`.
- New experiment definition → `research/experiments/`; generated results → `outputs/`.

See [Developer guide](DEVELOPER_GUIDE.md) for compatibility rules and
[Research guide](RESEARCH_GUIDE.md) before editing datasets or calibration.
