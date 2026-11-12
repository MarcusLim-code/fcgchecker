# File interaction map

Read [How FCGC works](HOW_FCGC_WORKS.md) first. This reference names the actual
0.13.0 files, calls and data boundaries. Paths are relative to the repository root.
A **schema** is an agreed set of fields and validation rules. An **adapter** is a
provider implementation behind that shared contract. **Serialization** means
turning those records into JSON for storage or transport.

## Actual directory tree: workflow-relevant files

This is a selected tree of existing files, not every cache or generated run.

```text
pyproject.toml                          fcgc = fcgc.cli:app
config/{local,wd_agent,wd.example}.toml  User provider profiles
.agents/skills/
  fcg-check/SKILL.md
  fcg-rules/SKILL.md
  fcg-compare/SKILL.md
  fcg-report/SKILL.md
  fcg-doctor/SKILL.md
skills/
  fcg_orchestration/WORKFLOW.md          Host execution instructions
  fcg_checking/{SKILL.md,prompt.txt}     Canonical interpretation/prompt
src/fcgc/
  cli.py
  agent/{cli,commands,session,skills,doctor}.py
  checking/
    feature_extractor.py, function_scope.py
    document_normalizer.py, rule_extractor.py
    context_reducer.py, context_packer.py, reduced_context.py
    compliance_checker.py
  retrieval/
    baseline.py, planned_retrieval.py, adaptive_retrieval.py
    query_planner.py, search_pipeline.py
    local_retriever.py, benchmark.py, replay_retriever.py
    mcp_bridge.py, atlassian.py
  integrations/
    mock_checker.py, placeholder_checker.py, synthetic_checker.py
    ollama_checker.py, devin.py, devin_agent.py
  schemas/{models,rules,checking,agent,benchmark,stage3,stage6,stage7,stage9}.py
  experiments/
    runner.py, snapshots.py, benchmark.py, acceptance.py
    evaluation.py, metrics.py, statistics.py
    calibration.py, calibration_margins.py
    quality.py, rq1.py, run_log.py
  config/                              Installed policy defaults/mappings
  fixtures/                            Installed synthetic resources
  core/{files,interfaces,transport_safety}.py
  core/, adapters/                     Also contain old-import forwarding files
research/experiments/                   Editable experiment/evaluation TOMLs
benchmarks/v2/                         Manifest, catalog, isolated labels, references
examples/{firmware,guidelines}/         Introductory source files
tests/{unit,integration,end_to_end,fixtures}/
outputs/                               New generated runs/reports/packages
runs/, release/                        Existing historical artifacts
scripts/{build_release,release_checks}.py
```

`src/fcgc/experiments/calibration.py` restricts calibration label access to development;
`calibration_margins.py` freezes and checks acceptance margins. Stage-numbered
schema filenames are historical names, not additional processing steps.
`core/` and `adapters/` forwarding files redirect old imports to the canonical
modules above; do not read them as duplicate algorithms. For ownership and all
other project resources, use the existing [directory guide](DIRECTORY_GUIDE.md).

## The real call sequence

The main P3 route is:

```text
Host reads fcg-check/SKILL.md → shared WORKFLOW.md
→ fcgc console entry → src/fcgc/agent/cli.py::invoke_command
→ src/fcgc/agent/commands.py::invoke → parse_command
→ src/fcgc/agent/session.py::start_session → advance
→ src/fcgc/experiments/runner.py::perform_run → execute_strategy
→ src/fcgc/retrieval/adaptive_retrieval.py::run_p3
   → extract_features → FCGQueryPlanner.plan
   → search/fetch → extract_documents → reducer.reduce
   → assess_sufficiency → pack_checker_input
   → bounded repeated search/process, if triggered
→ runner.prepare_task → freeze_packed_audit → render_checking_prompt
→ session checks provider: execute_checkers OR checking_required handoff
→ validated CheckingResult
→ save_session → summary + render_report → report.md
```

The WD tool branch interrupts this sequence at each missing receipt; it does not
run a second retrieval algorithm. The details below follow execution order, with
stages 8–11 repeated inside P3's loop.

### 1. Receive the engineer's request

**Purpose:** Tell the host what the command means and how to execute it.

**File involved:** `.agents/skills/fcg-check/SKILL.md`; `skills/fcg_orchestration/WORKFLOW.md`.

**Main function/class:** None; these are host-readable instructions.

**Called by:** A Devin host that recognizes the project skill. Native discovery is unverified here.

**Input:** `/fcg-check FILE [--function NAME] [--mode …]` and the host's actual tools.

**Processing:** The skill selects the shared workflow, read-only source handling and canonical checking policy.

**Output:** A host-executed `fcgc agent invoke --command … --output …` request; WD also supplies observed host facts.

**Next step:** The installed console entry in `pyproject.toml`, then `src/fcgc/cli.py`.

**Failure behavior:** If the host cannot discover/invoke skills, no Python workflow automatically starts. The files alone do not prove registration.

**Why this matters:** Engineers use conversational commands while one backend owns the algorithms.

### 2. Route and parse the command

**Purpose:** Convert the command into ordinary, validated arguments.

**File involved:** `src/fcgc/agent/cli.py`; `src/fcgc/agent/commands.py`.

**Main function/class:** `invoke_command()`, `invoke()`, `parse_command()`.

**Called by:** The Typer app registered with `app.add_typer(agent_app, name="agent")` in `src/fcgc/cli.py`.

**Input:** Slash-command text, a fresh output path, optional host JSON and explicit test-only simulation flag.

**Processing:** Read/validate `HostContext` when supplied; split arguments using shlex/argparse, not shell evaluation; optionally load provider settings.

**Output:** A `start_session()` call with source, mode, strategy, function, provider settings, Top-K and budgets.

**Next step:** `src/fcgc/agent/session.py`.

**Failure behavior:** Bad paths/options/config/host fields become a printed `Error: …` and CLI exit 1. Pre-session failures need not create an audit directory.

**Why this matters:** User arguments remain data, and defaults are explicit: local/P3/benchmark/mock.

### 3. Open source, select scope and lock the session

**Purpose:** Establish which exact artifact and configuration this check is about.

**File involved:** `src/fcgc/agent/session.py`, `src/fcgc/retrieval/baseline.py`, `src/fcgc/core/files.py`, `src/fcgc/checking/function_scope.py`, under `src/fcgc/`.

**Main function/class:** `start_session()`, `load_firmware()`, `read_source()`, `function_location()`.

**Called by:** `commands.invoke()`.

**Input:** A C file path, optional function name, provider/settings and mode.

**Processing:** Read exact UTF-8 bytes without newline conversion; hash them; validate size/content and requested function. WD requires `agent_mcp`, an identified host and source/output inside its approved workspace. Build `PipelineConfig`, `ArtifactLock` and `AgentSession`. Capture a diagnostic feature report and instruction/code/orchestration hashes.

**Output:** A session with original firmware identity, target coordinates, deadlines and physical-call limits; private `lock.json`.

**Next step:** `advance(session, output)`.

**Failure behavior:** Missing/non-C/empty/NUL/oversized input, invalid focus, unavailable host or incompatible provider choices fail explicitly. No local fixture substitution for WD.

**Why this matters:** Findings and later receipts cannot silently refer to a changed file/configuration.

The core reader allows 8,000,000 bytes; the agent entry adds a stricter 1,000,000-byte
artifact limit. Function focus retains the full source and whole-file features.

### 4. Start the shared strategy executor

**Purpose:** Reuse the same implementation for a single check and research runs.

**File involved:** `src/fcgc/agent/session.py`; `src/fcgc/experiments/runner.py`.

**Main function/class:** `advance()`, `perform_run()`, `execute_strategy()`.

**Called by:** `start_session()` or a validated handoff continuation.

**Input:** Locked configuration, firmware, strategy and a `RecordingRetriever` around the selected provider.

**Processing:** Check deadline/access failures; run the strategy with `checkers_enabled=False`. Apply function focus through `task_transform` before hashing/rendering the final task. `perform_run()` collects pipeline, task, source hashes, events and stage timings.

**Output:** A `RunTrace`, or a control-flow suspension for a pending host action.

**Next step:** P3 goes to `run_p3()`; P1/P2/B0 branches are described in [research workflow](RESEARCH_WORKFLOW.md).

**Failure behavior:** Ordinary exceptions are recorded as failed stages. `AgentRetrievalRequired` deliberately derives from `BaseException`, bypassing ordinary provider-error handlers so a normal host request is not labeled a failed run.

**Why this matters:** A native check does not maintain a second set of optimization algorithms.

Exact handoff from `advance()`:

```python
trace = perform_run(
    session.lock,
    firmware,
    session.strategy,
    1,
    session.session_id,
    recorder,
    checkers_enabled=False,
    task_transform=lambda task: _focus(session, task),
)
```

### 5. Observe firmware behavior

**Purpose:** Find search clues without claiming complete program analysis.

**File involved:** `src/fcgc/checking/feature_extractor.py`.

**Main function/class:** `extract_features()`.

**Called by:** `retrieve_p1()` for P1/P2; `run_p3()` for P3; session/runner also capture diagnostic features.

**Input:** `FirmwareInput` containing exact C text.

**Processing:** Build a tree-sitter C syntax tree; inspect calls, assignments, later conditions/returns, pointer/buffer expressions and simple macros. Infer operation categories and components from those observations/names.

**Output:** `FeatureReport`, also named `CodeFeatures`, with observed facts separated from heuristic categories and important unknowns.

**Next step:** `FCGQueryPlanner.plan()`.

**Failure behavior:** Parser unavailability or parse errors trigger bounded lexical fallback with warnings. Function-focus resolution is stricter and can reject an unreliable function tree.

**Why this matters:** An observation such as “status variable appears in a later condition” is useful for search, but is not a proved safety property.

### 6. Plan the initial search

**Purpose:** Translate observed/inferred behavior into guideline concepts.

**File involved:** `src/fcgc/retrieval/query_planner.py`; package `src/fcgc/config/feature_concepts_v2.json` and `src/fcgc/config/p1_templates_v2.toml`.

**Main function/class:** `FCGQueryPlanner.__init__()`, `plan()`.

**Called by:** `retrieve_p1()` or `run_p3()`.

**Input:** Feature report and document Top-K.

**Processing:** Match categories, sort mapping priority, keep at most two specific concepts, append a required general concept, then add up to three API names and two component hints. Validate template fields and reject benchmark rule IDs in configuration/query text.

**Output:** `QueryPlan`: one query, concept/basis records, mapping/template versions and budget.

**Next step:** The configured retriever's `search()`.

**Failure behavior:** Unsupported templates/query counts, malformed mappings or injected SFCG IDs fail. There is no model-assisted planner in the current path.

**Why this matters:** The query is traceable and uses runtime inputs, not expected-rule labels.

Custom mapping/template paths are constructor options; they are not fields accepted
by the root provider `Settings` model or options exposed by the native commands.
WD uses these same packaged defaults unless code/profile wiring is deliberately
extended; the default base query still contains “synthetic.”

### 7. Search, then fetch actual documents

**Purpose:** Separate discovering references from obtaining authoritative wording.

**File involved:** `src/fcgc/retrieval/local_retriever.py`, `search_pipeline.py`, `mcp_bridge.py`; `src/fcgc/experiments/snapshots.py`.

**Main function/class:** `LocalFixtureRetriever.search()/fetch()`, `execute_retrieval()`, `AgentMCPRetriever`, `RecordingRetriever`.

**Called by:** P1/B0 use `execute_retrieval()`; P3's inner `retrieve()` calls the same provider contract directly.

**Input:** Query and document Top-K; then each selected source ID.

**Processing:** Local ranking counts distinct lowercase token overlap and breaks ties by source ID. Scope filters apply to local search and fetch. B0/P1 validate query/Top-K/duplicate hits and fetch identity. P3 separately validates results/scope/references and avoids repeated fetches. The recorder stores actual responses and call durations/errors.

**Output:** Ordered `SearchResults` and original `FetchedDocument` objects.

**Next step:** Document normalization and rule extraction.

**Failure behavior:** Invalid fields/identity or fetch failures are explicit. P3 records supported retrieval failures, reassesses and may broaden within limits. WD submission adds strict receipt validation, including duplicate-result rejection.

**Why this matters:** A ranked page reference is not yet a rule or its full source context.

`benchmark.py::BenchmarkLexicalRetriever` is a compatibility-named subclass of
`LocalFixtureRetriever`. `LocalLexicalRetriever` instead selects the older
three-document smoke corpus. Neither emulates Atlassian semantic ranking.

### 8. Normalize and extract rules

**Purpose:** Make document structure usable while preserving the original text.

**File involved:** `src/fcgc/checking/document_normalizer.py`, `rule_extractor.py`; `src/fcgc/schemas/rules.py`.

**Main function/class:** `MarkdownDocumentNormalizer.normalize()`, `extract_documents()`, `extract_rule_evidence()`.

**Called by:** P2/P3 processing; also `runner.perform_run()` and `freeze_documents()` for trace/task preparation.

**Input:** Actual fetched documents, with source identity and available version.

**Processing:** Identify headings, list items, table cells and prose blocks. Classify operative guidance, notes/examples, definitions, conditions, exceptions and ambiguity. Index definitions, retain recognized references, combine dependent follow-up sentences, attach contextual qualifiers conservatively and flag larger uncertain spans. Detect obvious duplicates without collapsing source records.

**Output:** `RuleExtraction` with normalized blocks, `RuleEvidence`, other fragments and unresolved review sections.

**Next step:** Reducer, or full-document task preparation for B0/P1/R.

**Failure behavior:** Changed original wording/identity or broken spans fail validation. Unreliably segmented content remains a review section rather than a fabricated clean rule.

**Why this matters:** Conditions and later exceptions can change the meaning of an otherwise simple-looking sentence.

Explicit ID recognition currently targets `SFCG-NNN`. Generated `ev-…` IDs hash
source identity/reference and offsets; they are not official IDs. Arbitrary
Confluence HTML/ADF conversion is not implemented. Markdown table support is
bounded; unfamiliar requirement columns retain the row and flag review.

### 9. Select evidence conservatively

**Purpose:** Remove justified distractions while keeping interpretation context.

**File involved:** `src/fcgc/checking/context_reducer.py`.

**Main function/class:** `RuleContextReducer.reduce()`.

**Called by:** `run_p2()` or P3's `process()` closure.

**Input:** Firmware, feature report, candidate rules and original documents.

**Processing:** Validate source spans; score API/category/component/general-rule signals; recognize explicit scope conflicts and clear different-API bindings. Low overlap alone retains a rule with uncertainty. Restore required dependencies where available; mark unresolved references; exclude exact duplicate candidates only with matching stated scope and interpretation context.

**Output:** `EvidenceSelection` containing every candidate, one decision per candidate, selected/excluded IDs, reasons and unresolved dependencies.

**Next step:** P3 assessment then packing; P2 packs directly without a gate.

**Failure behavior:** Missing/mismatched sources or broken provenance fail. Unknown applicability stays included/unresolved rather than silently excluded.

**Why this matters:** Reduction is an auditable selection decision, not permission to rewrite normative wording.

### 10. Assess risk and decide whether to retrieve again

**Purpose:** Detect observable evidence gaps and bound the response to them.

**File involved:** `src/fcgc/retrieval/adaptive_retrieval.py`.

**Main function/class:** `run_p3()`, `assess_sufficiency()`, `fallback_queries()`.

**Called by:** `runner.execute_strategy("p3", …)` only.

**Input:** Features, current selection, category mappings, unresolved sections, errors and fallback policy.

**Processing:** Look for category signals, selected normative evidence, unresolved dependencies, conditional/review ambiguity, excessive duplicates and retrieval errors. Pack current evidence. If warnings remain and packing/budgets allow, choose a previously unused targeted/broadened query, fetch new sources and repeat stages 8–11.

**Output:** Initial/final `SufficiencyAssessment`, round records, final selection/context and `P3Metrics`.

**Next step:** Another search/fetch, or final task preparation.

**Failure behavior:** Stop at sufficient signals, no unique query, elapsed/call/source/round limit or context-budget failure. Remaining warnings produce `insufficient_evidence`, never a completeness guarantee.

**Why this matters:** The gate can notice risk without hidden provider confidence scores or ground-truth knowledge.

Default limits are three total rounds/searches, eight fetches/candidate sources and
five seconds of local core processing. WD replaces the core elapsed limit with the
explicit session deadline allowance and also has an overall wall-clock deadline.
In-flight host calls are not forcibly cancelled. Conditional evidence can trigger
ambiguity even if segmentation labels its source wording `clear`.

### 11. Pack, freeze and render checking input

**Purpose:** Supply complete source-backed obligations under an explicit budget.

**File involved:** `src/fcgc/checking/context_packer.py`, `compliance_checker.py`; `src/fcgc/experiments/runner.py`.

**Main function/class:** `pack_checker_input()`, `prepare_task()`, `freeze_packed_audit()`, `render_checking_prompt()`.

**Called by:** P2/P3 processing, then `perform_run()` after strategy completion.

**Input:** Selected rules, required spans, unresolved sections, original firmware/documents and token budget.

**Processing:** Keep normative text, conditions, exceptions, definitions, referenced text and larger review context. Count the rendered evidence. Convert to the canonical task and inject shared skill + output schema into `skills/fcg_checking/prompt.txt`. Count the final prompt too.

**Output:** Intermediate `PackedCheckerRequest` or no request if oversized; final `FrozenCheckingTask` and prompt string.

**Next step:** Session provider selection and checker execution/handoff.

**Failure behavior:** No silent truncation. Missing/oversized evidence becomes an incomplete task; substantive checking is blocked. Final prompt size is separately enforced after skill/schema serialization overhead.

**Why this matters:** A shorter context is useful only if qualifiers survive and the delivered task is accurately recorded.

“Frozen” means serialized/revalidated/hash-identified input; these Pydantic objects
are not configured as Python `frozen=True`. Adapters receive fresh validated copies.
For P2/P3 the model-facing document list excludes raw bodies; selected `RuleEvidence`
contains the wording/context. Full originals remain in the host task/audit.

### 12. Execute or receive checker judgments

**Purpose:** Establish applicability and compliance only when supported by evidence.

**File involved:** `src/fcgc/checking/compliance_checker.py`, `src/fcgc/schemas/checking.py`, `integrations/`; `src/fcgc/agent/session.py` for host judgments.

**Main function/class:** `execute_checkers()`, `CanonicalChecker.check()`, provider `predict()`, `validate_findings()`, `DevinAgentChecker`.

**Called by:** Local session `advance()`, batch `perform_run()`, or `submit_result()` after `checking_required`.

**Input:** Fresh validated frozen task and the same canonical instructions.

**Processing:** Block substantive prediction on empty/incomplete context. Otherwise ask the configured provider. Validate one finding per supplied evidence ID, applicability/decision consistency, normative citations and exact code locations. Record provider/model/settings, versions, hashes, time and exposed token counts.

**Output:** `CheckingResult`: status, reason, per-rule findings and `CheckerExecution`.

**Next step:** `save_session()`/report, or batch trace persistence.

**Failure behavior:** Unsupported behavior abstains; unavailable model returns unavailable; malformed/unsupported responses return error. Unreviewed source ambiguity permits unresolved findings only. No rule outside the bundle can be invented.

**Why this matters:** Applicable does not mean violating; no retrieved rule does not mean compliant.

| Provider | What actually produces judgments |
| --- | --- |
| `MockChecker` / legacy placeholder | No compliance judgments; unresolved/not_evaluated |
| `SyntheticDemoChecker` | Regex-bounded single-pointer-store grammar and exact SFCG-981 statement |
| `LocalLLMChecker` | Optional configured Ollama model; explicit network opt-in, availability not verified here |
| Direct `DevinChecker` | Unimplemented contract; unresolved/not_evaluated |
| Native WD `DevinAgentChecker` | Validates the actual host's `AgentJudgment`; does not call a Devin API |

WD `advance()` bypasses the direct Devin factory stub: it requests a host judgment
only for a complete task, then `submit_result()` constructs `DevinAgentChecker`.
If context is incomplete it produces abstaining mock results instead. Simulated
host judgments are labeled `simulated_devin_agent`, not real-model evidence.

### 13. Save records and present the report

**Purpose:** Give the engineer understandable findings and an audit trail.

**File involved:** `src/fcgc/agent/session.py`.

**Main function/class:** `save_session()`, `summary()`, `render_report()`, `private_write()`.

**Called by:** `advance()` and `submit_result()` on pending/completed/error states.

**Input:** Session, trace, task and validated checker results.

**Processing:** Write private JSON atomically; calculate summary counts; render report lines from actual findings/source context. No model generates this Markdown verdict.

**Output:** `session.json`, `lock.json`, `result.json`, `report.md`; conditional task/trace/prompt/action/receipt/snapshot files below.

**Next step:** The host reads and presents the report; post-hoc evaluation is a separate workflow.

**Failure behavior:** Fresh output and input/hash checks prevent accidental reuse. Filesystem failures may surface as CLI errors; failures before a session starts have stderr rather than a complete trace.

**Why this matters:** Workflow completion and compliance success remain separate, inspectable statuses.

## Devin → MCP → Python, exactly

The bridge stores **JSON files** and uses CLI arguments/stdout. It does not open a
Python MCP connection or borrow a Devin login. Relevant files:

| Boundary | Producer → consumer | Actual mechanism / validation |
| --- | --- | --- |
| Host capabilities | Active host → `src/fcgc/agent/cli.py` | `--host FILE`; `read_json()` → `HostContext`; no invented names/schemas |
| Next operation | `mcp_bridge.py` → `session.advance()` → host | `AgentAction`; `action.json` + returned result with status `retrieval_required` |
| Actual search/fetch | Host → existing authorized MCP tools | Tool invocation outside Python; tool names come from observed host context |
| Search receipt | Host → `src/fcgc/agent/cli.py::submit()` → `submit_result()` | `--response FILE`; `AgentToolResult` with `SearchResults`; query, K, duplicate IDs, scope, host/provider/action identity checked |
| Fetch receipt | Host → same submission path | Exact `FetchedDocument`; selected ID/ref/title, nonempty content, size, URI policy and timestamps checked |
| Continuation | `submit_result()` → `advance()` | Persist `CompletedCall`, reconstruct `AgentMCPRetriever`; consume validated receipts from index zero, suspend only at the next missing operation |
| Final judgment | Host → `submit_result()` | `AgentJudgment`; evidence/prompt/session hashes and `validate_findings()` before acceptance |

A compact real source excerpt from `mcp_bridge.py` shows the suspension boundary:

```python
if operation == "fetch" and action.source is None:
    raise ValueError("Fetch was not authorized by a captured search reference")
raise AgentRetrievalRequired(action)
```

`AgentRetrievalRequired` is normal control flow. `advance()` catches it and saves
an action instead of waiting inside a long-running Python server. Every resume
repeats deterministic Python computation but does not repeat physical tool calls
whose receipts were already accepted. Fake-transport tests verify this mechanism;
no actual MCP/Devin invocation was available during this documentation task.

Pagination is not automatic: the host must faithfully supply a bounded action's
result or mark it partial. It must not conceal extra physical calls. Partial
receipts make final context incomplete; their flag alone is not a cursor fallback
algorithm. Markdown/plain text is accepted; HTML/ADF needs an approved future
conversion boundary. Host attestations are not independent proof of authentication.

## Data contracts: actual names and consumers

There is no `CodeArtifact` or `EvidenceBundle` class. Their roles are represented
by the concrete models below. `CheckerRequest` is the older retrieval wrapper;
the main standardized checking path uses `FrozenCheckingTask`.

| Actual model and schema file | Contains / created by | Consumed by / why shared |
| --- | --- | --- |
| `FirmwareInput`, `src/fcgc/schemas/models.py` | Filename, case ID, content, SHA; loader or experiment runner | Extractor, retriever request and checker; same exact source identity |
| `FeatureReport` / alias `CodeFeatures`, `src/fcgc/schemas/stage3.py` | Observations, inferred categories, unknowns; extractor | Planner/reducer/gate and trace; distinguish facts from hypotheses |
| `QueryPlan`, `src/fcgc/schemas/stage3.py` | Query, concepts/bases, versions, K; planner | P1/P3 and logs; audit why a query exists |
| `RetrievalRequest`, `src/fcgc/schemas/models.py` | Firmware, b0/p1 query/version/K; baseline or P1 | Shared search pipeline; P2/P3 have separate run wrappers |
| `RetrievalQuery`, `src/fcgc/schemas/agent.py` | Handoff query ID/text/K/template/search number; agent provider | Host action; exact transport request |
| `SearchHit`, `SearchResults`, `src/fcgc/schemas/models.py` | Ranked identities and optional integer scores/scope; retriever | Fetch selection and validation; order is ranking |
| `FetchedDocument`, `src/fcgc/schemas/models.py` | Source ID/title/ref/text/optional version; provider/host | Normalizer, packer, checker and audit; original wording |
| `NormalizedDocument`, `src/fcgc/schemas/rules.py` | Original document + structure/offset blocks; normalizer | Segmenter; structure without replacing source |
| `RuleEvidence`, `src/fcgc/schemas/rules.py` | Verbatim normative span, headings, qualifiers, definitions, references, ambiguity; segmenter | Reducer/gate/checker; source-backed interpretation unit |
| `EvidenceSelection`, `src/fcgc/schemas/stage6.py` | All candidates, inclusion/exclusion reasons and dependencies; reducer | Packer, gate, audits; no invisible dropped rule |
| `PackedCheckerRequest`, `src/fcgc/schemas/stage6.py` | Source-backed packed rules, code location, rendered input, warnings/token estimate; packer | Canonical task conversion; explicit complete/incomplete/budget behavior |
| `SufficiencyAssessment`, `src/fcgc/schemas/stage7.py` | Category signals, dependencies, duplication, ambiguity and reasons; gate | Bounded fallback and report; risk rather than oracle |
| `FrozenCheckingTask`, `src/fcgc/schemas/checking.py` | Original code/documents, selected rules, focus, warnings/status; task preparation | Every checker and prompt renderer; reproducible input/hash |
| `RuleFinding`, `ModelFindings`, `src/fcgc/schemas/checking.py` | Applicability, decision, locations, citations, uncertainty; provider | Host validator; reject unsupported identities/citations |
| `CheckingResult`, `CheckerExecution`, `src/fcgc/schemas/checking.py` | Extends `CheckerResult` with findings/provider/model/settings/versions/hashes/tokens/time | Session and evaluator; outcome separate from execution metadata |
| `HostContext`, `AgentAction`, `AgentToolResult`, `AgentJudgment`, `src/fcgc/schemas/agent.py` | Capabilities, pending work, actual receipts and findings | Agent session; correlate each bounded host interaction |
| `RunTrace`, `src/fcgc/schemas/stage9.py` | Artifact, pipeline, features, selected rules, task, calls, errors, timings, status | Saved experiments/session and evaluator/replay; reconstruct what happened |

Base contracts forbid unknown fields and revalidate model instances. Source and
citation validators also compare actual text slices. `SearchHit.score` can be
null; fractional managed-provider metadata belongs in `ResultMetadata`, not a
fabricated integer/confidence. A status field does not certify all program paths.

## Configuration: what is actually selected

| Choice | Where it is set | Important scope/default |
| --- | --- | --- |
| Local vs WD | Native `--mode local|wd`, parsed in `src/fcgc/agent/commands.py` | A command flag, not a `Settings` TOML key; defaults local |
| Retriever/checker/model | Root `config/*.toml` → `config.load_settings()` / factories | Native defaults benchmark/mock, or agent_mcp/devin in WD when no profile supplied |
| Plain core CLI defaults | `src/fcgc/config/local.toml` | Legacy `local` smoke corpus + placeholder; differs from native default |
| Query concepts/template | Package `feature_concepts_v2.json`, `p1_templates_v2.toml` | Library constructor accepts custom paths; native workflow constructs defaults |
| Reduction policy | Package `p2_reduction_v1.toml` | `load_reduction_config()`; bare `run_p2()` default evidence budget 2200 |
| Fallback policy | Package `p3_fallback_v1.toml` | `load_fallback_config()`; bare `run_p3()` default context budget 3000, local soft 5 s |
| Native context budget | `--token-budget`, default 12000 | `PipelineConfig.context_token_budget`; `execute_strategy()` passes/overrides both P2/P3 pack budgets to this value; final canonical prompt also checked |
| Native deadline | `--deadline`, default 600 s, maximum 3600 | Overall host/human wall time; WD also uses it as the core elapsed allowance |
| Experiments | `research/experiments/*.toml` → `load_experiment()` | Dataset/split, strategies, common providers, budgets, repetitions and seed |
| Optional CLI environment | Typer options declaring `envvar="FCGC_CONFIG"` in `src/fcgc/cli.py` | Not automatically read by `load_settings()` or native `parse_command()`; use native `--config` explicitly |

Root profiles do not contain credentials. `config/wd.example.toml` selects the
unimplemented direct contract; `config/wd_agent.toml` selects the host bridge.
Provider profile paths resolve from the working directory; replay paths inside
profiles and experiment/evaluation paths resolve relative to their config file.
`.env` is not automatically loaded. Unsupported extra TOML keys are rejected.
Budget/Top-K/repetition changes are reasonable on development data but change the
experimental configuration; mappings/prompts/thresholds require versions and
revalidation, never tuning against held-out labels.

## Saved files and measurements

| File | Writer and meaning |
| --- | --- |
| `lock.json` | `start_session()` or batch runner; code/config/instruction identity |
| `session.json` | `save_session()`; continuation state, features, deadline, accepted host receipts |
| `action.json` | `save_session()` only while pending; removed when no action remains |
| `handoffs/001.json`, … | `submit_result()`; accepted tool-result receipts |
| `trace.json` | Final core `RunTrace` when available; not guaranteed on pre-session or early suspended/denied paths |
| `task.json`, `checker-prompt.json` | Agent task and exact prompt wrapper when prepared |
| `result.json`, `report.md` | Agent summary and human-readable report, including incomplete/pending states |
| `retrieval-snapshot.json` | Local agent recording of source-bearing responses; not the same layout as batch replay storage |
| Batch `runs/<id>/checker_prompt.txt`, `snapshots/<id>.json` | `run_experiment()`; exact prompts and approved ordered content snapshots |
| Evaluation JSON/CSV/Markdown/HTML | `evaluation.write_reports()`; post-hoc metrics, not runtime predictions |

`estimate_tokens()` counts words/punctuation with `regex-word-punctuation-v1`.
Trace retrieved-context tokens count source bodies; final input tokens count the
canonical prompt. P2/P3 additionally record intermediate pack measurements.
Provider output/input tokens are optional; billed tokens, ACU and Rovo credits are
not inferred zeros. `RecordingRetriever` times actual Python provider calls.
WD core traces measure the final receipt-consumption pass; cumulative backend
processing, supplied host-tool durations and session wall time are separate.
Wall time includes host/human waiting, and counters supplied by a host are not
independently authenticated bills. Some coarse trace stages combine work rather
than isolate every feature/reduction operation; see [research limits](RESEARCH_WORKFLOW.md).

## Failure propagation

| Failure | Actual propagation |
| --- | --- |
| Missing file/bad args before session | CLI error/exit 1; no promise of trace/report |
| Ordinary provider/processing failure inside `perform_run()` | `StageError`, failed trace and incomplete stage markers; P3 may first record/reassess supported retrieval errors |
| Missing host receipt | Normal `AgentRetrievalRequired` suspension → pending action/result, not a failed provider result |
| Invalid receipt/citation | Submission rejected before acceptance; pending identity cannot be silently changed |
| Authentication/permission receipt | Session stops on next advance; no independent login/retry/fixture substitution |
| Partial/error receipt | If a final task exists, mark incomplete; substantive judgments blocked |
| Missing dependency/unsegmented section | Keep warning/context and mark unresolved/incomplete as appropriate |
| Evidence/prompt too large | Explicit budget failure/incomplete task; no normative truncation |
| Checker unavailable/rejected | Unavailable/error with unresolved findings and recorded metadata/error |
| Evidence remains uncertain after fallback | P3 insufficient; workflow may still complete with not_evaluated |
| Changed firmware/code/skills/lock/receipts during continuation | `load_session()` rejects drift; start a fresh session |
| Missing or incompatible replay content | Explicit exact-replay-impossible error; no live retrieval substitute |

Ordinary core errors, CLI preflight errors and host suspensions use different
channels. See [where to investigate](WHERE_TO_EDIT.md) rather than assuming every
non-success has the same file set or return status.

## Documentation verification record

Verified on **2026-11-13, Asia/Kuala_Lumpur**, against release 0.13.0. The task
created only the five requested walkthrough documents; it did not refactor, rename,
move, delete or edit application/configuration/skill/test/dataset files.

| Check | Observed result |
| --- | --- |
| Before/after content hashes | All **325 pre-existing inventoried project files unchanged** |
| Source entries and contracts | **88 named source symbols** checked against Python syntax trees |
| Important direct calls | **17 caller/callee relationships** checked against actual call nodes; remaining branch/host relationships inspected in source |
| Concrete source/test/config paths | **61 checked**, all exist; explicitly illustrative/new-command paths distinguished |
| Local document links | **36 checked**, including heading targets; no broken links |
| Diagrams | Six Mermaid blocks across main walkthrough and diagram reference; source branches and Markdown fences checked |
| Representative local check | C001/boot_sensor/P3: three searches, five fetches, 17 selected rules; incomplete_context / not_evaluated |
| Paragraph extraction | Two contextual candidates; conditions/exceptions preserved and review required |
| Comparison | C001/C002 × B0/P1/P2/P3 × three repeats = 24 finished, zero failed, 12 explicitly incomplete |
| Saved reports | Generated without rerunning retrieval; `retrieval_rerun=false` |
| Batch evidence replay | `exact_evidence_replay=true`; original checker mock remained not_evaluated |
| Bounded genuine checking | Pointer demonstration violating at original line 3 with exact source citation; same task mock not_evaluated |
| Automated tests | `.venv/bin/python -m pytest -q -p no:cacheprovider`: **232 passed in 5.99 s** |
| Secret-pattern inspection | No selected credential-pattern findings in the five new documents; all code/guideline examples synthetic |
| Live enterprise verification | Not performed: no exposed Atlassian/Devin tools or available Devin/Ollama executable in this session |

The verification ran with temporary output storage and disabled pytest cache and
bytecode writing for the test subprocess. Source hashes were checked afterwards.
No repository installation/build or configuration change was needed. Current
static type checking was not part of this documentation-only task. Mermaid was
not visually rendered because no renderer was installed; reference/branch review
is not a claim of screenshot or live-system verification.

To repeat the main practical checks from the project root, choose a fresh temporary
output root (the observed execution used a temporary directory as well):

```sh
FCGC_WALKTHROUGH_OUTPUT="$(mktemp -d)"
.venv/bin/fcgc agent invoke --command '/fcg-check src/fcgc/fixtures/benchmark_cases/C001.c --function boot_sensor --mode local' --output "$FCGC_WALKTHROUGH_OUTPUT/check"
.venv/bin/fcgc agent invoke --command '/fcg-compare --case C001 --repeat 3' --output "$FCGC_WALKTHROUGH_OUTPUT/comparison"
.venv/bin/fcgc report --config "$FCGC_WALKTHROUGH_OUTPUT/comparison/evaluation.json"
.venv/bin/fcgc replay --run "$FCGC_WALKTHROUGH_OUTPUT/comparison/experiment/runs/C001-p3-r01/trace.json" --output "$FCGC_WALKTHROUGH_OUTPUT/replay"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

The check, feature extraction, paragraph extraction, diagnostics, comparison,
report-only command, replay, task freezing and deterministic/mock checking were all
executed successfully while preparing the explanations. Formula/error/transport
contracts were also exercised by the suite. Real model inference, authenticated WD
access, native command recognition and enterprise error scenarios remain live
verification tasks, not outcomes inferred from those tests.
