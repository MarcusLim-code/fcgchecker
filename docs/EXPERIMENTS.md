# Experiments and replay

## Native skill orchestration

`/fcg-compare --case C001 --repeat 3` invokes the same locked runner/evaluator through
`fcgc agent invoke`. It keeps matched variants together and selects development
cases only. `/fcg-report --experiment latest` reads saved experiment/evaluation
records and never reruns retrieval. Generated configuration may be validated JSON;
existing TOML paths and semantics remain supported. Explicit experiment configs
must retain B0/P1/P2/P3 and the existing provider/budget controls. Canonical checking
skill 1.1.0 and prompt FCGC-PROMPT-V1 remain shared; optional function focus is task
data, not a different compliance rubric. Untargeted canonical task hashes retain
backward compatibility with historical snapshots.

Native `/fcg-check` and `/fcg-rules` reuse the same strategy executor and preserve
source-backed evidence. WD agent handoffs record the actual query/reference order,
provider/tool/scope identity, versions, receipts and canonical checking hashes.
Pending physical operations are bounded; P2 never falls back. An unavailable
managed score is null, never a fabricated confidence. Agent workflow wall time,
backend replay processing, optional exposed tool durations, estimated tokens and
provider token counters are distinct. Receipt replay adds CPU overhead; a final
core-pass duration is not a measurement of live managed retrieval latency.

Fixture handoff tests are labeled synthetic_contract_test, not live MCP. Python
cannot independently authenticate agent-attested receipts. Current live enterprise
matrices are **not implemented** because the existing production capture guard,
enterprise dataset binding and approved storage policy must be resolved first.
`/fcg-compare --mode wd` fails without substituting fixtures or made-up metrics.
No labels influence runtime planning/checking; source-backed evidence and independent
post-hoc labels stay separate. See [native integration](DEVIN_INTEGRATION.md).

The final CLI wraps the same tested runner and evaluator:

```sh
.venv/bin/fcgc validate-local --dataset-root benchmarks/v2 --output outputs/release-local
.venv/bin/fcgc experiment --config research/experiments/release_development.toml
.venv/bin/fcgc report --config outputs/release-local/evaluation.toml
.venv/bin/fcgc replay --run outputs/release-local/experiment/runs/C001-p3-r01/trace.json --output outputs/release-replay
```

`validate-local` generates experiment/evaluation TOMLs and uses all eight development
cases with three repetitions by default. Its five configurations include optional
R. Results are labeled synthetic/local-fixture/mock with estimated tokens. The
separate deterministic pointer demonstration does not make the benchmark mock a
real checker. Every annotation remains provisional. Held-out labels are never used
for tuning; whole-dataset quality validation is structural only.

An acceptance directory contains `experiment.toml`, `evaluation.toml`,
`acceptance.json`, `dataset-quality.json`, `deterministic/`, `replay/`,
`experiment/` (lock, summary, snapshots and per-run traces/tasks/prompts), and
`evaluation/` (metrics JSON, three CSV tables, Markdown and offline HTML).

Replay validates exact evidence and the canonical prompt before invoking any
checker. A mismatch is recorded without checker execution. Replay may rerun the
original checker only after validation; its predictions and timing are not claimed
identical. Provider/corpus content mismatches are rejected during locking/evaluation.

See [evaluation definitions and statistical assumptions](evaluation.md) for rule K,
compliance eligibility, paired inference and freezing held-out acceptance margins.
The stage-oriented module commands below remain supported for compatibility.


```sh
.venv/bin/python -m fcgc.experiments.runner run \
  --config research/experiments/stage9_development.toml
```

The checked-in matrix selects eight development cases, four strategies, three
repetitions, the Stage 2 fixture corpus, and fresh mock checkers. Config paths are
relative to the TOML. `[retrieval]` chooses one provider/scope for all strategies.
Repeat `[[checkers]]` tables to evaluate the same frozen evidence through several
models without repeating retrieval. Their compatibility `retriever` setting does
not override `[retrieval]`. Budget grids use separate configs/output directories.
Add `"r"` to strategies for optional broad-reference search; R uses a larger
document Top-K with the same provider/scope and is not ground truth.

B0/P1/R retain full fetched documents and all segmented finding targets. P2/P3
retain selected rule excerpts and required context. Skill 1.1.0 explicitly supports
both modes; the prompt template remains FCGC-PROMPT-V1. Historical Stage 8 reports
retain their recorded 1.0.0 version. B0 feature observations in experiment traces
are diagnostic only, extracted after retrieval, and cannot influence its query.

`document_top_k` counts documents. B0/P1/P2 use one search and at most K fetches.
P3 shares the initial K, with explicitly larger locked fallback budgets. R uses
`reference_top_k`. Final canonical checker prompts also obey `context_token_budget`:
oversized input stays auditable, is marked incomplete, and is not sent to a real
checker. Stage 6 context-rendering estimates and actual canonical-prompt estimates
are logged separately. Generation seeds are checker settings; the experiment seed
controls reproducible run-order shuffling.

## Lock and isolation

Before provider calls, `lock.json` freezes normalized settings, code version and
source/config fingerprint, skill/prompt hashes and versions, dataset/annotation
versions, public manifest/corpus hashes, and firmware hashes. Drift is checked
before each run. Changed settings, code, source or provider require a new output
directory. Identical completed runs resume without calls. Interrupted started
runs and final failed runs are never silently overwritten or retried. Writes use
atomic replacement.

Select exactly one split. Explicit case IDs must stay within it and keep matched
variant groups together. For heldout execution, copy the config to a different
output directory and preserve the optimization settings frozen on development.
The runner never opens annotation labels or tunes thresholds. It records annotation
version only; independent evaluation must bind its own label contents to predictions.

Fresh retriever/checker instances and validated task copies prevent in-process
history leakage. External weight changes behind tags, caching, and remote session
identity cannot be guaranteed. Exposed model metadata and uncontrolled conditions
are recorded. Network providers still require Stage 8 opt-in. Production-source
snapshot capture is rejected pending an approval/storage adapter.

## Files and trace contents

```text
runs/stage9-development/
  lock.json
  summary.json
  snapshots/C001-b0-r01.json
  ...
  runs/C001-b0-r01/
    trace.json
    task.json
    checker_prompt.txt
  ...
```

Each trace includes run ID/UTC timestamp and lock reference; code artifact/hash;
feature observations and role; typed strategy output; segmented documents and
selected IDs; source content hashes, versions and references; frozen task and
canonical input; checker settings/results via the lock and execution records;
stage/end-to-end timings; token estimates/method; ordered tool calls; errors,
zero automatic retries, and incomplete stages. P2/P3 outputs include reduction
decisions; P3 includes sufficiency and fallback decisions. Baselines explicitly
record `all_candidates_no_reduction`.

Tool records retain query/K, returned ranking, fetched content, failures and timing.
Snapshots retain approved **content**, not only hashes, separately from the corpus.
The example config explicitly approves synthetic fixture snapshots. Production
knowledge sources are not modified. The summary preserves every repetition and
reports distinct source orders/task hashes rather than concealing variability.
`finished` means execution finished, not that evidence or compliance was complete.
Fixture/replay/mock calls are labeled and never counted as MCP traffic.

Pipeline wall time is distinct from diagnostic instrumentation. End-to-end time
includes diagnostic features but excludes final disk persistence. Nested pipeline
outputs retain feature/planning/reduction/packing/fallback timing. Individual
checker results retain provider timing and token counters when available.

## Replay

```sh
.venv/bin/python -m fcgc.experiments.runner replay \
  --run outputs/stage9-development/runs/C001-p3-r01/trace.json \
  --output outputs/stage9-replay-example
```

Use a fresh replay output directory. Replay constructs no live retriever. It
verifies code/instruction locks, approval, snapshot hashes, ordered requests and
response content. Repeated queries replay their original per-call variability.
Saved firmware/documents avoid reading the original dataset or corpus. Missing
snapshots explicitly report exact replay impossible; a hash cannot reconstruct
content. Tampering and changed instructions/code are rejected. P3's soft elapsed
limits may diverge on another machine; divergence is reported.

`comparison.json` checks evidence/task hashes and the consumed call sequence.
It does not equate wall-clock timing or checker predictions. Retrieval replay
re-executes the originally configured checker, including explicit model-network
settings. For checker-only replay, choose configs without any retrieval:

```sh
.venv/bin/fcgc check-task \
  --task outputs/stage9-development/runs/C001-p2-r01/task.json \
  --checker-config src/fcgc/config/checker_mock.toml \
  --checker-config src/fcgc/config/checker_demo.toml \
  --output /tmp/fcgc-checker-comparison.json
```

Supported failed-call exception classes can be replayed. Tracebacks and malformed
raw provider payloads are not reconstructed; unsupported error reconstruction
produces a mismatch. No accuracy or enterprise-performance claim follows from
successful orchestration.
