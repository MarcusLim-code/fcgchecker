# Stage 10 recorded evaluation

Fresh saved experiment: `runs/stage10-development/`, 96 completed executions,
8 cases × B0/P1/P2/P3 × 3 repetitions. Evaluation artifacts are in
`runs/stage10-evaluation/`. Data is **synthetic**, retrieval is **local fixture**,
checking is **mock**, tokens are **local estimates**, latency is **measured locally**,
and annotations are **provisional**. No heldout labels were read for this demonstration.

The primary values below are means of case means at **rule K=18**. Each document
search used K=3; P3 additionally used bounded fallback. Means do not treat the three
repetitions as independent cases.

| Strategy | Fetched Recall@18 | Fetched Precision@18 | Retained Recall@18 | Mean prepared checker-input tokens | Mean searches / fetches |
| --- | ---: | ---: | ---: | ---: | --- |
| B0 | 0.4375 | 0.0833 | 0.4375 | 5,717.875 | 1 / 3 |
| P1 | 0.9167 | 0.1632 | 0.9167 | 6,644.625 | 1 / 3 |
| P2 | 0.9167 | 0.1632 | 0.9167 | 5,534.625 | 1 / 3 |
| P3 | 0.9167 | 0.1389 | 0.9167 | 7,513.000 | 3 / 5.375 |

No annotated applicable rule was lost during reduction on these observations.
Source/rule set Jaccard stability was 1.0 across repeated runs of this deterministic
backend. All 96 mock checker results are `not_evaluated`; compliance TP/FP/FN,
precision/recall/F1 and tokens-per-correct-detection remain **unavailable**.
Thirty observations retain incomplete evidence contexts. Unsupported ID-less
evidence and ambiguity are separately flagged, not assigned invented IDs.

Paired inference uses eight case averages and four matched-variant groups:

- B0→P1 mean fetched recall delta: +0.4792; group-bootstrap 95% CI
  [0.1250, 0.8333]; exact sign-flip p=0.25, Holm-adjusted p=0.75.
- P1→P2 mean prepared-input delta: −1,110 estimated tokens; CI
  [−1,308.0, −818.5]. Retained-recall delta was 0 on these provisional labels.
- P2→P3 mean prepared-input delta: +1,978.375 estimated tokens; CI
  [1,900.375, 2,035.0]. Applicable-rule Recall@18 did not increase.

These are small, exploratory synthetic measurements. They do not establish
independent compliance effectiveness, enterprise performance or statistically
reliable population effects. Latency values and per-case regressions are in the
generated JSON/CSV/Markdown/HTML report, with source measurement labels.

The known prediction arithmetic fixture was also executed and saved as
`stage10_known_metrics.json`: retrieval precision/recall/F2=0.5, and violation
TP=1, FP=2, FN=1, precision=1/3, recall=1/2, F1=0.4, attribution accuracy=1/2.
This checks the metric implementations, not a real checker or independent review.

Validation: 100 pytest tests and Ruff passed. Tests cover zero denominators,
missing output/resources, duplicate IDs/observations, incomplete/failed runs,
repetition clustering, hand-verified metrics, report generation, frozen-margin
integrity/timing, pre-label heldout gating, and development-only sensitivity grids.
An illustrative margin artifact was frozen and a four-config sensitivity grid
was generated; that grid was not executed or presented as measured sensitivity.
See [evaluation operation](../../../docs/evaluation.md) for exact commands and
interpretation of all three research questions.
