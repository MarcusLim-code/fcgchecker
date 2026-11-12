# Research guide

Research configuration lives in `research/experiments/`; experiment implementation
lives in `src/fcgc/experiments/`. Generated comparisons belong in `outputs/`, not in
source or curated data directories.

## Choose a workflow

Engineers in a supported Devin host can use:

```text
/fcg-compare --case C001 --repeat 3
/fcg-report --experiment latest
```

C001 includes its matched C002 variant. Omitting the case selects all eight
development cases. The same backend can run a configuration file:

```sh
.venv/bin/fcgc experiment --config research/experiments/stage9_development.toml
.venv/bin/fcgc report --config research/experiments/stage10_evaluation.toml
```

The report configuration above consumes the matching stage10 development output;
run `stage10_development.toml` first if using that report. To run a self-contained
acceptance experiment and generate its matching report configuration automatically:

```sh
.venv/bin/fcgc validate-local --dataset-root benchmarks/v2 --output outputs/validation/research
.venv/bin/fcgc report --config outputs/validation/research/evaluation.toml
```

Use fresh directories. Configure budgets/providers/repetitions in TOML; do not
change algorithms manually between strategies. Three repetitions are the default.
Local mode runs without WD, paid services, embeddings or a live LLM.

## Keep the definitions fixed

| Strategy | Retrieval and context behavior |
| --- | --- |
| B0 | Fixed generic query, normal search/fetch, full documents; no feature expansion, reduction or fallback |
| P1 | Deterministic feature extraction and versioned targeted query; no reduction/fallback |
| P2 | P1 retrieval plus whole-rule/section evidence reduction; no fallback |
| P3 | P2 plus observable sufficiency warnings and bounded additional retrieval |
| R | Optional broad-reference generic retrieval; larger document budget |

B0 and P1 use the same one-search, document Top-K=3 budget by default. P3 has extra
bounded calls, logged separately. Rule Recall@18 uses unique canonical rules in
source-arrival/line/ID order; document K and rule K are different. Compare fetched,
retained and checker-supplied evidence separately. The gate detects risk, not completeness.

## Dataset and labels

`benchmarks/v2/` contains the versioned manifest, canonical rule catalog and separate
`ground_truth/development/` and `ground_truth/heldout/`. Public firmware/guidelines
are packaged under `src/fcgc/fixtures/`. There are 36 rules in eight documents and
24 cases (eight development, 16 held-out). All annotations remain provisional.

Read [the annotation review guide](../benchmarks/v2/REVIEW_GUIDE.md). Independent
review must validate applicability, expected decisions, violation locations and
source evidence before accuracy claims. Keep matched variants together and record
versions/hashes. Do not edit labels to agree with a retriever/checker. Runtime
features/queries/checker tasks do not read these labels. Quality checks may inspect
both splits structurally; calibration must use development only.

The dataset and frozen `benchmarks/v2/reports/` stay in place to preserve references
and existing tests. `research/experiments/` is a navigation/working area, not a
second copy of the corpus. Related manifest/rule/source hashes remain unchanged.

## Read the outputs honestly

An experiment directory contains `lock.json`, `summary.json`, `runs/<id>/trace.json`,
frozen tasks/prompts and content-bearing `snapshots/`. Its evaluation directory
contains metrics JSON, CSVs and Markdown/offline HTML reports. These include exact
queries, sources, rule decisions, fallback, tokens and local timings.

Mock results are not_evaluated and excluded from compliance accuracy. The bounded
synthetic checker is a real demonstration, not general checking. Token counts are
local estimates unless a provider exposes counters; unavailable billing/ACU/Rovo
metrics are null. Repetitions are grouped within case, then matched variants are
clustered for inference. Eight development cases are a small sample, not 24
independent cases merely because they were repeated three times.

Use [experiments](EXPERIMENTS.md), [evaluation](evaluation.md) and [checking](checking.md)
for precise controls, frozen acceptance margins and model setup. Held-out evaluation
must follow frozen development calibration, never the reverse.

## Replay and historical evidence

```sh
.venv/bin/fcgc replay --run outputs/validation/research/experiment/runs/C001-p3-r01/trace.json --output outputs/validation/replayed
```

Exact replay requires available approved content and the recorded code/instructions.
The refactoring changes source hashes; older snapshots remain untouched but require
their original release to replay exactly. No compatibility flag bypasses this guard.
Historic `runs/`, `release/` and benchmark reports remain read-only archives. For
cross-checker work, use saved frozen tasks without rerunning retrieval.

Live enterprise comparisons require approved WD dataset/snapshot governance and
an enterprise matrix adapter, which are still pending. Do not treat local fixture
calls or fake MCP receipts as real MCP traffic or enterprise performance evidence.
