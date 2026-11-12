# Stage 10 research evaluation

Evaluation is a post-hoc operation. Retrieval, planning, reduction, fallback and
checker code do not import the label loader. Labels are opened only after saved
traces exist. The evaluator verifies dataset/annotation versions, firmware hashes,
annotation spans/quotes, canonical IDs, and experiment lock identities. Duplicate
catalog/annotation IDs and duplicate experimental observations are rejected.

## Commands and outputs

```sh
# Fresh runtime-version lock; archived Stage 9 results remain available separately.
.venv/bin/python -m fcgc.experiments.runner run \
  --config research/experiments/stage10_development.toml
.venv/bin/python -m fcgc.experiments.evaluation \
  --config research/experiments/stage10_evaluation.toml

# Check the explicit arithmetic fixture against its hand-calculated expected values.
.venv/bin/python -m fcgc.experiments.evaluation \
  --verify-fixture tests/fixtures/evaluation_known.json
```

The generated `runs/stage10-evaluation/` contains:

```text
metrics.json   # every observation, case aggregate, paired contrast and limitation
runs.csv       # per-observation metrics and missed-rule/FN lists
summary.csv    # configuration means, medians, SD, IQR, ranges, stability
paired.csv     # paired deltas, intervals, effect sizes and tests
report.md
report.html    # self-contained offline report; no CDN, server or scripts required
```

`experiment_directories` can list multiple locked experiments. Different Top-K,
gate settings, code/corpus/instruction hashes or provider settings form different
control panels. They are never silently pooled. A panel can contain several
checker configurations; their metrics remain separate. Evaluation can read archived
traces without executing their original code. Exact retrieval replay still requires
the archived code/instruction fingerprint, as documented in [experiments](EXPERIMENTS.md).

## Retrieval definitions

Document Top-K is the search budget in each locked experiment. **Rule K** in the
evaluation is a separate unique-canonical-rule cutoff. Fetched rules are ordered
by source fetch-arrival rank, then catalog source line and canonical ID. Retained
and checker stages filter that ranking and take their own first K unique IDs.
Repeated references do not consume extra rule positions.

Precision@K divides applicable returned IDs by actual unique returned IDs up to K;
recall divides by applicable IDs. Empty-return precision is undefined (`null`),
not automatically zero. No-applicable-rule recall is undefined. F2 uses the count
formula `5 TP / (5 TP + 4 FN + FP)` with undefined zero denominators.

Each observation reports these distinct evidence stages:

- `fetched`: all catalog rules present in fetched documents, before segmentation.
- `candidate`: canonical rules recognized by segmentation.
- `retained`: rules preserved after reduction (all candidates for B0/P1/R).
- `prepared`: rules in the frozen checking task.
- `checker_received`: rules delivered to the checker adapter.
- `model_supplied`: rules known to have reached a genuine checker implementation;
  empty for mocks or blocked context, unknown when legacy metadata cannot establish
  submission. A prepared prompt is not proof of model execution.

Every stage includes metrics at K and untruncated applicable-present/missing sets.
Lost rules are separately listed at segmentation, reduction, and checker delivery.
Canonical source identity must match the catalog; ID-less or unsupported evidence
remains auditable but unscored, rather than receiving invented canonical IDs.
Category coverage uses the applicable categories in the annotations. Feature
coverage uses an explicit configurable feature-to-catalog-category mapping and
lists unmapped features; it is an approximation, not an applicability oracle.

Repetition-level source/rule stability is pairwise set Jaccard, with exact source
order counts also recorded. One observation has no stability estimate. Two valid
empty sets have Jaccard 1; failed/unavailable stages are excluded from stability.

## Compliance definitions and independence

Actual performance claims require independently reviewed ground truth. Current
Stage 2 annotations are provisional. By default, compliance accuracy is disabled
for those labels; explicit `allow_provisional_compliance=true` permits exploratory
counts only. Mock/unexecuted/unavailable/rejected results are never accurate
compliance models: TP/FP/FN, precision, recall and F1 remain null. Potential
undetected annotated violations are listed separately as coverage gaps.

For eligible evaluated results, a canonical violation finding matching an annotated
violation is TP. A predicted violation on a reviewed compliant/nonapplicable rule
is FP, assuming the applicability annotation is exhaustive. An expected violation
without a matching predicted violation is strict end-to-end FN. The latter is
split into abstained/missing evidence and explicitly wrong judgments. Uncertain
ground-truth rules are excluded from binary scoring and reported separately.
Duplicate identical findings collapse by canonical ID; contradictory duplicates
become unresolved rather than multiplying detections.

Precision is `TP/(TP+FP)`, recall `TP/(TP+FN)`, and F1
`2TP/(2TP+FP+FN)`. Zero denominators are null. A genuine evaluated run missing all
known violations has recall/F1 zero; an unexecuted mock does not.

Rule-attribution accuracy is a separate localization measure: among predicted
violation IDs whose code location overlaps any annotated violation site, count
those citing the correct canonical rule and overlapping that rule's site. Unlocated
predictions do not invent attribution support. Canonical detection counts remain
available independently of localization. Source and code citations are revalidated
against the frozen task before scoring; unsupported responses are unscored.

The known arithmetic fixture enumerates retrieval `[A,A,B,C]` with truth `[A,D]`
at K=2: one relevant unique result, precision=recall=F2=0.5. Its violation fixture
has TP=1, FP=2, FN=1, precision=1/3, recall=1/2, F1=0.4, and attribution=1/2.
Those values were checked by direct enumeration. This validates arithmetic; it is
not independent firmware review or a fabricated model-performance result.

## Resources and statistics

Retrieved context counts raw fetched source text. Final checker-input counts the
saved canonical prompt including code, skill/schema and evidence metadata. Stage 6
rendering estimates are separate. Local estimates use the named word/punctuation
method; provider input/output counters, when exposed, remain distinct. Provider
counts are not measured bills. Unknown output/total/billed tokens, ACU and Rovo
credits stay null. Input-estimate tokens per TP and provider-total tokens per TP
are separate and undefined when no correct detection exists.

Token reduction is reported against the same case/configuration's mean P1 input
tokens. Search/fetch attempts and fallback overhead come from tool and P3 traces.
Measured feature, retrieval, reduction, packing, checker and end-to-end timings are
kept separate where available. Archived P3 traces cannot isolate some stages;
those fields remain null. B0 diagnostic feature extraction is labeled separately.
End-to-end time includes the whole configured checker matrix, not just one model.

Repetitions are first averaged within each firmware case. Descriptive means,
medians, sample SD, IQR and ranges then use case means. Inferential paired deltas
are B-A for B0→P1, P1→P2 and P2→P3. Related matched variants are further clustered
using the dataset's `group`; bootstrap intervals and paired tests use those group
means. Three repetitions of eight cases do not become 24 independent samples.

The report provides seeded group bootstrap 95% intervals, paired standardized
mean-difference `dz` (null for zero dispersion), exact sign tests, and exact sign-flip
tests up to 16 groups (seeded Monte Carlo beyond that). Sign-flip tests require
independent symmetric group differences. Holm adjustment covers the three contrasts
within a metric/panel/model family. Only four independent groups exist in the current
development set: intervals and p-values are exploratory, coarse and low-powered.
Failed/missing observations are disclosed; missing values are not imputed as zero.

## Development sensitivity and frozen heldout margins

Generate a development-only grid of document K and the duplicate-fraction
sufficiency threshold:

```sh
.venv/bin/python -m fcgc.experiments.calibration_margins sensitivity \
  --base research/experiments/stage10_development.toml \
  --output outputs/stage10-sensitivity-grid \
  --top-k 1 3 --duplicate-threshold 0.25 0.5
```

This writes four experiment TOMLs and an evaluation TOML; generation alone does
not produce sensitivity results. Execute each generated experiment config, then
evaluate `runs/stage10-sensitivity-grid/evaluation.toml`. Panels remain separate.
The generator rejects heldout base configs. Other gate settings can likewise be
changed in separate development configs and evaluated as separate locked panels.

After justified development calibration, freeze acceptance bounds:

```sh
.venv/bin/python -m fcgc.experiments.calibration_margins freeze \
  --development-report runs/stage10-evaluation/metrics.json \
  --margins research/experiments/stage10_margins.toml \
  --output outputs/stage10-calibration/frozen_margins.json
```

The checked-in bounds are explicitly illustrative, not validated research criteria.
Replace them with justified values and rationale. Freezing stores a development
report hash, controls, rule K, bounds and UTC timestamp and refuses to overwrite.
Keep the source development report with the artifact.

Only then execute heldout runs with the same frozen controls, separate split and
output directory. Put the artifact path in the heldout evaluation config's
`frozen_margins` field. Before opening heldout labels, the evaluator verifies its
hash, control signatures, rule K, and that freezing preceded every heldout run.
Changing code, budgets, thresholds, providers or prompts invalidates calibration.
Confidence intervals entirely inside/outside bounds yield within/outside-margin;
overlap is inconclusive and missing metrics are not assessed. The evaluator never
tunes a threshold or prompt using heldout labels.

## Reading the three research questions

- **RQ1:** compare B0/P1 fetched Recall/Precision@K and cost. These evaluate query
  planning, not downstream checker correctness. Inspect missed rules and categories.
- **RQ2:** compare P1/P2 retained and checker-received coverage as well as prompt
  tokens, latency and genuine-model violation metrics. Preserved retrieval coverage
  alone cannot establish preserved compliance-checking effectiveness.
- **RQ3:** compare P2/P3 canonical applicable-rule gains against extra calls, context
  and latency. A recovered sufficiency warning is not a ground-truth recall gain.

Every report identifies synthetic/enterprise provenance, fixture/replay/live-MCP
retrieval identity, checker kind, ground-truth review status and resource measurement
methods. The current framework supports the synthetic dataset; its local results
cannot support claims about enterprise ranking, billing or Devin performance.
