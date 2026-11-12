# Workflow diagrams

These diagrams describe the inspected **0.13.0** implementation. Python filenames
are relative to `src/fcgc/` unless another root is shown. Arrows mean actual calls,
data transfer or the labeled external host action—not a verified live service.

- **Local:** executable with synthetic fixtures and mock/bounded deterministic checking.
- **WD bridge:** implemented and contract-tested with fake host receipts; native/live access unverified.
- **Unimplemented:** explicit stubs or missing functionality, outside working paths.

Read the [beginner walkthrough](HOW_FCGC_WORKS.md) for the example, or the
[file interaction map](FILE_INTERACTION_MAP.md) for inputs, functions and failures.

## High-level architecture

```mermaid
flowchart TD
  U["Engineer: /fcg-check FILE"] --> SK[".agents/skills/fcg-check/SKILL.md"]
  SK --> WF["skills/fcg_orchestration/WORKFLOW.md"]
  WF --> A["agent/cli.py → commands.py → session.py"]
  C["Read-only C file"] --> A
  A --> R["experiments/runner.py: shared strategy executor"]
  R --> Q["feature_extractor.py + query_planner.py for P1/P2/P3"]
  R --> B["baseline.py: fixed B0 query"]
  Q --> CH{"Selected provider"}
  B --> CH
  CH --> L["Local: local_retriever.py or approved replay"]
  CH --> M["WD: mcp_bridge.py / typed session actions"]
  M -. "Host performs actual tools; live unverified" .-> W["Existing Devin Atlassian MCP → Confluence"]
  W -. "Actual source text through validated JSON receipts" .-> M
  L --> D["FetchedDocument: identity + original wording"]
  M --> D
  D --> E["document_normalizer.py + rule_extractor.py"]
  E --> P["P2/P3: context_reducer.py + context_packer.py"]
  P --> G["P3: adaptive_retrieval.py risk gate / bounded rounds"]
  G -->|"Additional query only within limits"| CH
  E --> F["compliance_checker.py: canonical task/prompt"]
  P --> F
  G --> F
  F --> CK{"Configured checker"}
  CK --> MK["Local default: mock_checker.py / not_evaluated"]
  CK --> DM["synthetic_checker.py: narrow supported grammar"]
  CK --> OL["ollama_checker.py: optional model, explicit opt-in"]
  CK --> DA["WD host judgment → devin_agent.py; live unverified"]
  MK --> O["session.py: validated results + report.md + audit"]
  DM --> O
  OL --> O
  DA --> O

  subgraph Missing["Not operational implementations"]
    ST["retrieval/atlassian.py: direct API stub"]
    DS["integrations/devin.py: direct API stub"]
    ES["Enterprise experiment/storage adapter: not implemented"]
  end
  classDef pending fill:#fff4dd,stroke:#a87300,stroke-dasharray:5 5
  class ST,DS,ES pending
```

B0/P1/R bypass reduction/gate. In P3 the reducer, assessment and packer run on each
retrieval round before the loop decides whether to continue. Arrows into canonical
task preparation represent alternative strategy outputs, not simultaneous branches.
The optional Ollama implementation exists; a real local model was not available
for this documentation verification.

## `/fcg-check` execution sequence

This diagram expands the **default local P3** command. It shows the important
calls rather than every import/validation helper. The WD interruption is expanded
in the next section.

```mermaid
sequenceDiagram
  actor E as Engineer
  participant H as Devin host / skill workflow
  participant C as agent/cli.py + commands.py
  participant S as agent/session.py
  participant R as experiments/runner.py
  participant P as retrieval/adaptive_retrieval.py
  participant L as LocalFixtureRetriever
  participant K as CanonicalChecker + configured provider

  E->>H: /fcg-check FILE [--function NAME]
  Note over H: Native Devin recognition/invocation still needs target verification
  H->>C: fcgc agent invoke --command ... --output ...
  C->>C: invoke_command → invoke → parse_command
  C->>S: start_session(source, settings, mode, strategy, limits)
  S->>S: load_firmware, optional function_location, lock and features
  S->>R: perform_run(..., checkers_enabled=False, task_transform=_focus)
  R->>P: execute_strategy → run_p3
  P->>P: extract_features → FCGQueryPlanner.plan
  loop Initial round, then only while warned and within limits
    P->>L: search(query, document_K)
    L-->>P: SearchResults in ranked order
    P->>L: fetch(new source IDs)
    L-->>P: Original FetchedDocument objects
    P->>P: extract_documents → reducer.reduce → assess_sufficiency
    P->>P: pack_checker_input; decide stop or next unique query
  end
  P-->>R: P3Run with final evidence, assessments, attempts and costs
  R->>R: prepare_task → freeze_packed_audit → render_checking_prompt
  R->>R: Final budget check, source hashes, diagnostic features and timings
  R-->>S: RunTrace with checking task; checker not invoked yet
  S->>R: execute_checkers(trace, config)
  R->>K: check(fresh FrozenCheckingTask)
  alt No rules or incomplete context
    K->>K: Return unresolved without substantive prediction
  else Complete supplied context
    K->>K: predict with canonical prompt; validate findings/citations
  end
  K-->>R: CheckingResult + CheckerExecution
  R-->>S: Checker results and checker-stage timing
  S->>S: save_session → summary + render_report
  S-->>C: Structured result with report path
  C-->>H: JSON stdout; nonzero on error
  H->>H: Read report.md and actual audit records
  H-->>E: Findings or explicit abstention, citations, warnings, report link
```

The mock never supplies a substantive decision, even with complete context. In
this walkthrough C001 remained incomplete and returned not_evaluated. `/fcg-rules`
shares retrieval/context processing but skips checking altogether.

## MCP handoff and adaptive fallback

### The host-to-Python request/receipt loop

```mermaid
flowchart TD
  A["session.py: advance"] --> P["runner.perform_run: deterministic strategy"]
  P --> B["mcp_bridge.py: AgentMCPRetriever._call"]
  B --> V{"Accepted matching receipt at this position?"}
  V -->|Yes| RR["Return typed response; no new physical host call"]
  RR --> P
  V -->|No, budgets allow| AC["Raise AgentRetrievalRequired(AgentAction)"]
  AC --> SAVE["advance catches suspension; save action.json + session.json"]
  SAVE --> HOST["Devin host reads exact pending search/fetch action"]
  HOST -. "Actual authorized tool invocation, live unverified" .-> MCP["Existing Atlassian MCP search or fetch"]
  MCP -. "Actual result or sanitized tool error" .-> JSON["Host writes AgentToolResult JSON file"]
  JSON --> SUB["fcgc agent submit --session DIR --response FILE"]
  SUB --> CHECK["session.submit_result: validate identity, query/K/scope, source and timestamp"]
  CHECK -->|Accepted| STORE["Persist CompletedCall and handoffs/NNN.json"]
  STORE --> A
  CHECK -->|Rejected| REJ["Explicit error; do not invent a replacement response"]
```

On resumption, Python restarts deterministic computation and reuses prior validated
receipts. It does not continue an in-memory stack or reissue old physical calls.
Authentication/permission errors stop the workflow. Missing tools fail before WD
execution; local fixtures are not substituted. Physical pagination/cursor handling
is not automatic. Partial responses must be marked and cannot support a false
complete-context judgment.

A later `checking_required` action uses the same file/submit transport:
`task.json` + exact `checker-prompt.json` → host judgment → `AgentJudgment` JSON →
`validate_findings()` → `DevinAgentChecker`. No Python Devin API is involved.

### What actually triggers another retrieval round

```mermaid
flowchart TD
  D["Fetched documents accumulated so far"] --> X["run_p3.process: extract_documents"]
  X --> R["RuleContextReducer.reduce"]
  R --> G["assess_sufficiency: category signals, rules, references, ambiguity, errors"]
  G --> PK["pack_checker_input: preserve required evidence"]
  PK --> OK{"Sufficient signals and pack fits?"}
  OK -->|Yes| FINAL["Finish P3 with current task; not a completeness proof"]
  OK -->|No| LIMIT{"Pack exists and round/call/source/time limits allow?"}
  LIMIT -->|No| INC["Stop with insufficient_evidence / incomplete context"]
  LIMIT -->|Yes| Q["fallback_queries: first unseen targeted or broadened query"]
  Q --> UNIQUE{"Any unused query?"}
  UNIQUE -->|No| INC
  UNIQUE -->|Yes| CALL["Search/fetch through same selected provider or host handoff"]
  CALL --> D
```

These are observable warnings, not ground-truth knowledge or hidden Atlassian
confidence. P2 never enters this loop. Packing failure can stop fallback before
another query; it is not a reason to truncate normative evidence.

## B0/P1/P2/P3 experiment workflow

```mermaid
flowchart TD
  U["/fcg-compare or fcgc experiment --config FILE"] --> LOAD["commands.compare or cli.experiment"]
  CFG["research/experiments/*.toml or constructed ExperimentConfig"] --> LOAD
  LOAD --> RUN["runner.run_experiment: load_experiment + make_lock"]
  DATA["Public manifest/catalog, source cases/corpus; no per-case labels in prediction input"] --> RUN
  RUN --> JOB["Case × strategy × repetition; fresh providers/checkers; lock recheck"]
  JOB --> EX["perform_run → execute_strategy"]
  EX --> B["B0: retrieve_b0 / fixed generic query"]
  EX --> P1["P1: retrieve_p1 / features + planner"]
  EX --> P2["P2: run_p2 / P1 + rule reduction + pack"]
  EX --> P3["P3: run_p3 / shared analysis + bounded adaptive loop"]
  B --> SH["Shared task preparation, instructions, checker validation and tracing"]
  P1 --> SH
  P2 --> SH
  P3 --> SH
  SH --> SAV["lock.json, runs/trace.json, frozen tasks/prompts, content snapshots"]
  SAV --> EV["evaluation.evaluate: validate saved controls and load selected annotations"]
  GT["Separate ground_truth split; held-out margins checked first"] --> EV
  EV --> MET["Canonical rule metrics, eligible compliance, costs and paired statistics"]
  MET --> REP["write_reports: JSON, CSV, Markdown, offline HTML"]
  SAV --> REPLAY["replay_run + OrderedReplayRetriever; no live retrieval"]
  REPLAY --> HASH["Validate reconstructed evidence before optional checker execution"]
```

The save→evaluate arrow is orchestrated by `/fcg-compare`, `validate-local` or a
separate `fcgc report`; `run_experiment()` itself only records prediction runs.
Report-only commands start at saved controls and never fill missing runs by
retrieving again. Optional R uses the same shared remainder with a larger broad
reference document budget. See [research workflow](RESEARCH_WORKFLOW.md) for precise
K units, eligibility, grouped repetitions and limitations.

## Reading and verification notes

The Python edges were checked against `commands.py`, `session.py`, `runner.py`,
`adaptive_retrieval.py`, `mcp_bridge.py`, canonical checking and reporting source.
Representative local commands, a 24-run comparison, report generation and replay
were executed; the full suite passed. Diagram branching is source-verified;
no live MCP/Devin arrows are claimed as executed. Mermaid source is provided for
offline rendering by a compatible Markdown viewer, not as a screenshot of a running
enterprise system. Detailed measured example fields are in [How FCGC works](HOW_FCGC_WORKS.md).
