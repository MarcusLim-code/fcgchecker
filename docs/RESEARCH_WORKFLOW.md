# The implemented research workflow

A research run repeats the same firmware tasks under controlled strategy choices,
then evaluates saved predictions against separate annotations. It is not a second
checking system. For onboarding and experiment commands, use the existing
[research guide](RESEARCH_GUIDE.md); this document traces the actual implementation.

## 1. How a comparison starts

In a supported host, `/fcg-compare` uses its skill and shared workflow, then
`src/fcgc/agent/commands.py::compare()`. The backend either constructs an
`ExperimentConfig` or loads the supplied experiment configuration. It requires the
B0/P1/P2/P3 matrix and development split. A requested case includes all its matched
variants: selecting C001 also selects C002.

The internal CLI alternative is `src/fcgc/cli.py::experiment()`, which calls
`src/fcgc/experiments/runner.py::run_experiment()`. That entry accepts the configured
strategy list, including optional broad reference R, and the configured split.
Native `/fcg-compare --mode wd` explicitly fails: enterprise dataset/snapshot
storage and matrix execution are not implemented. It does not replace WD data
with synthetic data.

Working definitions live in `research/experiments/`. For example:

```sh
.venv/bin/fcgc experiment --config research/experiments/stage9_development.toml
```

That existing file selects eight development cases, four strategies, three
repetitions, fixture retrieval, mock checking, document K=3, final context cap=12000
and approved synthetic snapshots. Its output is relative to the TOML file, under
`outputs/experiments/stage9-development`. Use a fresh output or an identical locked
configuration; do not manually edit code between ablations.

## 2. Load public inputs, then lock the comparison

`runner.load_experiment()` reads TOML/JSON, supplies reduction/fallback defaults,
validates configuration and resolves relative paths. `make_lock()` uses
`src/fcgc/experiments/benchmark.py::load_public_benchmark()` to load `benchmarks/v2/manifest.json`
and `rules.json`. The public loader checks paths stay under the packaged
benchmark firmware/guideline directories.

There are 24 synthetic cases (eight development, 16 held-out), 36 cataloged rules
and eight documents. Manifest metadata selects split/groups and source paths;
per-case applicability/violation annotations live separately under
`benchmarks/v2/ground_truth/`. Public metadata/catalog loading does not pass expected
labels or rule IDs into planner/checker inputs. Predictions use firmware and
retrieved source evidence. Annotations remain **provisional** pending independent
review; see [the dataset review guide](../benchmarks/v2/REVIEW_GUIDE.md).

`make_lock()` records code/version, configuration, instruction hash, manifest,
corpus and case hashes plus dataset/annotation versions. It rejects unknown cases,
split crossing, broken matched groups, wrong skill/prompt versions and unapproved
snapshot capture. Current batch capture only accepts local/benchmark/replay
retrievers, not production sources. A recorded annotation *version* is not reading
its expected labels during prediction.

## 3. Run each strategy through the same executor

`run_experiment()` forms case × strategy × repetition jobs, optionally shuffles
with a seeded random generator, and checks the lock again before each job. It
constructs fresh providers lazily and fresh checkers for each run. Passing a
provider object into the algorithm rather than opening a service inside it is
**dependency injection**; it lets the same logic use fixtures or replay.

All jobs call `runner.perform_run()`. Its branch point is `execute_strategy()`:

| Configuration | Query planning | Context reduction | Fallback | Actual execution path after `execute_strategy()` |
| --- | --- | --- | --- | --- |
| B0 | Fixed generic query | No | No | `src/fcgc/retrieval/baseline.py::retrieve_b0()` → `search_pipeline.execute_retrieval()` → full-document canonical task |
| P1 | Firmware-aware | No | No | `src/fcgc/retrieval/planned_retrieval.py::retrieve_p1()` → `extract_features()` → `FCGQueryPlanner.plan()` → shared search pipeline → full-document task |
| P2 | Firmware-aware | Yes | No | `src/fcgc/checking/reduced_context.py::run_p2()` → unchanged P1 retrieval → extraction → reduction → packing → reduced canonical task |
| P3 | Firmware-aware | Yes | Yes | `src/fcgc/retrieval/adaptive_retrieval.py::run_p3()` directly invokes shared extractor/planner and its bounded retrieve/process loop → reduced canonical task |
| R, optional | Fixed broad-reference query | No | No | `execute_retrieval()` with `broad-reference-v1` and reference document K → full-document task |

P3 does **not** literally call `run_p2()` or `retrieve_p1()`. The research definition
“P2 plus fallback” describes its shared behavior; the implementation has its own
loop. P2 does not call the sufficiency gate or fallback.

B0's exact query is `firmware coding guidelines C source`. Its request carries the
artifact but does not inspect calls/filename to expand the query. B0/R diagnostic
features are still recorded; native sessions can extract them at startup and the
runner does so in its finalization. They do not influence baseline retrieval.

The common remainder is `pipeline_documents()` → trace segmentation →
`prepare_task()` → `render_checking_prompt()` → budget validation →
`execute_checkers()` → saved results. B0/P1/R tasks include full fetched document
bodies; P2/P3 tasks deliver selected rule context while retaining full originals
for audit. Checker selection and canonical instructions do not feed back into retrieval.

## 4. What is held constant, and what differs

| Control | Actual enforcement / limit |
| --- | --- |
| Firmware | Same content/hash across strategies; locked case identities |
| Corpus/source scope | Same selected backend/settings/scope and locked content; benchmark provider corpus checked against manifest sources |
| Ranking | Same lexical code/provider; source order retained. No hidden managed scores are assumed |
| Checker/model | Same configured checker matrix and generation requests; fresh instances and validated copies of each task |
| Instructions | Shared skill 1.1.0 and prompt FCGC-PROMPT-V1, with hashes/expected versions |
| Ground truth | Separate post-hoc annotations; evaluator records annotation hashes/version |
| Initial retrieval budget | B0/P1/P2: one search, document Top-K=3 by default |
| P3 budget difference | Up to three searches/rounds total, eight fetches and eight candidate sources; extra calls/tokens/time recorded |
| Context budget | Pipeline config governs P2/P3 pack size and final canonical prompt cap |
| Repetition/order | Configured count and seed; repetition is not a new independent firmware case |
| Permissions/provider identity | Local scope is checked; actual enterprise access/identity cannot be established by this synthetic runner |

A subtle override matters: package reducer/gate TOMLs contain standalone defaults
(2200/3000 estimated context tokens), but `execute_strategy()` supplies the common
`PipelineConfig.context_token_budget`, normally 12000, to both P2/P3. A serialized
nested fallback default is therefore not necessarily the effective budget. Native
WD mode also changes the core elapsed allowance to the outer session deadline;
local core fallback retains its five-second soft limit.

Controls reduce confounding; they do not prove that two models behave equivalently,
freeze remote weights, eliminate external provider state or make P3 matched-cost.
Soft time limits can change round sequences on slower hosts. These constraints
belong in results rather than being hidden.

## 5. Save enough content to explain and replay a run

The runner writes `started` before work, then finished/failed traces and content
snapshots. Existing finished records with matching lock are reused; stale started
or mismatched records are rejected rather than silently resumed as new data.

```text
experiment/
  lock.json
  summary.json
  runs/C001-p3-r01/
    trace.json
    task.json
    checker_prompt.txt
  snapshots/C001-p3-r01.json
```

`trace.json` is `RunTrace`: code artifact, diagnostic features, typed strategy
output, segmented/selected evidence, exact packed prompt, checker results, ordered
tool calls, source hashes, stage latencies, errors and incomplete-stage markers.
P2/P3 outputs retain selection reasons; P3 retains initial/final assessments,
query/trigger per round and additional resource measurements.

`src/fcgc/experiments/snapshots.py::RecordingRetriever` stores actual search/fetch responses,
including full document content, duration and errors. A hash alone cannot reconstruct
a document. The snapshot store is separate from the corpus. Ordinary batch files
are local research artifacts, not a production access-control or retention service.

An agent check uses `session.json`, `checker-prompt.json` and local
`retrieval-snapshot.json` instead. The CLI `replay` command expects the **batch**
`runs/<id>/trace.json` + experiment lock/snapshot layout; an agent trace alone is
not automatically interchangeable with it.

## 6. Evaluate saved observations, after prediction

`commands.compare()` calls `evaluation.evaluate()` only after `run_experiment()`
returns. `/fcg-report` calls the same evaluator on existing saved records, without
new retrieval/checking. Direct `fcgc experiment` saves traces; it does not itself
call the evaluator. `fcgc report --config EVALUATION_CONFIG` is the explicit next
step, or use `/fcg-compare`/`validate-local` to orchestrate both.

The evaluator validates dataset/split, corpus/source content, trace lock/identity,
checker provider/model/settings/instructions and task hashes. Held-out evaluation
requires frozen development margins before opening held-out labels. It then loads
only the selected split's annotations, compares canonical IDs and writes reports.
Structural dataset quality checks may inspect both splits; that is not permission
to tune on held-out outcomes.

### Retrieval: rules, not page counts

`ordered_rule_sets()` begins with first successful fetch order. Within each source
it orders canonical catalog rules by source line then ID. All stages use that same
ordering, with their own membership filters. It reports:

1. **Fetched:** applicable catalog rules present anywhere in fetched documents.
2. **Candidate:** those actually represented by segmented canonical evidence.
3. **Retained:** those kept after reduction, or all candidates for B0/P1/R.
4. **Prepared:** those in the frozen task.
5. **Checker received:** those delivered to an adapter, distinct from actual prediction.
6. **Model supplied:** separately available/empty/unknown depending on execution evidence.

Rule K=18 by the standard evaluation config means a prefix of **unique canonical
rule IDs**, not 18 documents or a new semantic rule score. Precision divides
relevant IDs by actual returned unique IDs up to K; recall divides by applicable
IDs. `all_evidence_coverage` additionally reports all fetched/retained IDs beyond K.
ID-less/generated evidence remains auditable but cannot be scored as an invented
canonical rule. Category coverage and repeated source/rule Jaccard stability are
separate measures.

### Compliance: eligibility before arithmetic

`evaluate_observation()` and `metrics.compliance_metrics()` calculate rule-level
violation TP/FP/FN, precision/recall/F1, false-negative categories and attribution.
Unexecuted mocks/stubs and simulated traffic are excluded. Provisional labels do
not allow accuracy scoring by default. Ambiguous labels, unresolved decisions,
missing predictions and conflicting duplicates are explicitly separated.

Rule-attribution accuracy is narrower than general precision: its denominator is
predicted violations whose locations overlap *any* true violation site; the numerator
also requires the correct rule and its own true location. Zero denominators are
null, not a perfect score. The manually constructed arithmetic fixture yields
TP=1, FP=2, FN=1, precision=1/3, recall=0.5, F1=0.4 and attribution=0.5. This verifies
formulas, not independent firmware-checking accuracy.

### Efficiency: specify what was counted

Retrieved-context tokens count fetched document bodies. Intermediate packed-input
and final canonical checker-input tokens measure different representations.
`regex-word-punctuation-v1` is a deterministic local approximation, not a model's
billing tokenizer. Provider input/output counters are optional and not automatically
billed measurements. Missing totals, tokens per correct detection, ACU or Rovo
credits remain unavailable where required inputs are absent.

Search/fetch counts, fallback overhead and measured Python wall-clock latencies
are recorded. Some stage timings combine feature/planning/reduction work; P1/P2
have additional nested timings, while P3 does not expose every stage separately.
WD receipt replay is Python processing time, not hidden network time; host durations
and overall host/human wall time are separate. `end_to_end_ms` covers the configured
checker matrix; individual checker timing is also recorded.

## 7. Aggregate paired observations and report regressions

`evaluation.aggregate()` first averages repetitions within firmware case, then
`statistics.paired_statistics()` clusters matched variants for inference. It
compares B0→P1, P1→P2 and P2→P3, reporting descriptive statistics, paired effects,
seeded group bootstrap intervals, sign/sign-flip tests and adjusted p-values when
sample size/assumptions permit. Sign-flip inference assumes symmetry. It does not
pretend that repeated runs of one case are independent new cases.

`write_reports()` creates:

```text
metrics.json   summary.csv   runs.csv   paired.csv   report.md   report.html
```

Reports distinguish synthetic/live provenance, fixture/replay provider, checker
kind, estimated/measured resources, misses, lost evidence, incomplete and failed
observations. Failed/missing runs are not silently converted into good accuracy.
Small samples and provisional annotations limit interpretation.

## 8. Replay without live retrieval

`runner.replay_run()` validates the experiment lock, current code/instruction hashes,
approved content snapshot and safe snapshot path. `OrderedReplayRetriever` supplies
responses in recorded order only when operation/query/K/source match. The shared
executor rebuilds the task with checkers disabled, verifies source hashes, task hash,
packed input and calls, and **only then** executes configured checkers.

Therefore exact evidence replay does not promise identical checker predictions or
timing. If the original checker is network-enabled, replay may call that checker
after validating retrieval; it never calls a live retriever. Missing content,
changed code/instructions or diverged calls produce an explicit error, not a live
substitute. Old release snapshots require their matching original release. Use
saved frozen tasks with `check-task` for checker-only comparisons without retrieval.

## Executed example and remaining weaknesses

For this documentation task we executed `/fcg-compare --case C001 --repeat 3` through
the backend using temporary output. It selected C001/C002, ran **24/24 jobs**, with
zero failed and **12 explicitly incomplete**. All 24 mock results were
`not_evaluated`; no eligible compliance accuracy was claimed. Saved-report generation
returned `retrieval_rerun=false`. The saved P3 batch trace replayed with
`exact_evidence_replay=true`.

The single C001 walkthrough recovered an initialization-category signal through
fallback, but stayed insufficient. Independent labels, not that recovered signal,
are needed to establish a recall gain. Synthetic lexical ranking, provisional
labels, very few independent groups, lack of real-model outcomes and unverified
live transport constrain research conclusions. Native WD experiment matrices,
production snapshot governance and genuine enterprise metrics remain unimplemented
or awaiting authorized verification. See [confusing areas](WHERE_TO_EDIT.md#confusing-areas-and-improvement-suggestions)
for confirmed implementation indirection and possible future improvements.
