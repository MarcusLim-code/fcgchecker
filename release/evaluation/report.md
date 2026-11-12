# FCGC research evaluation

Split: development. Labels: `{'data': 'synthetic', 'retrieval': ['benchmark'], 'checking': ['mock'], 'retrieval_kind': ['local_fixture'], 'checker_kind': ['mock'], 'resources': 'local token estimates and measured wall time; provider tokens only when exposed; no billing measurements', 'ground_truth': ['provisional']}`.
Quality flags: {'incomplete_observations': 54, 'unsupported_rule_observations': 45, 'ambiguous_rule_instances': 126, 'unresolved_finding_instances': 2304, 'compliance_eligible_observations': 0}.

Rule K is a unique canonical-rule prefix after source-arrival rank, source line, then ID. Document K is the experiment search budget; it is not rule K.
Precision divides by actual unique returned rule IDs up to K; no-applicable-rule recall and zero-denominator precision are undefined.
Checker-received means the adapter got the frozen task; model-supplied coverage is separately recorded and is empty for mocks.

| Configuration | Cases | Fetched recall@K | Fetched precision@K | Retained recall@K | Checker-received recall@K | Violation F1 | Input tokens mean | Calls search/fetch mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 9a40154d / b0 / checker 0 | 8 | 0.438 | 0.083 | 0.438 | 0.438 | unavailable | 5717.875 | 1.000/3.000 |
| 9a40154d / p1 / checker 0 | 8 | 0.917 | 0.163 | 0.917 | 0.917 | unavailable | 6644.625 | 1.000/3.000 |
| 9a40154d / p2 / checker 0 | 8 | 0.917 | 0.163 | 0.917 | 0.917 | unavailable | 5534.625 | 1.000/3.000 |
| 9a40154d / p3 / checker 0 | 8 | 0.917 | 0.139 | 0.917 | 0.917 | unavailable | 7513.000 | 3.000/5.375 |
| 9a40154d / r / checker 0 | 8 | 0.438 | 0.056 | 0.438 | 0.438 | unavailable | 14136.875 | 1.000/8.000 |

## Paired comparisons

Deltas are later minus earlier. Repetitions are averaged within firmware case; inference uses matched-variant group means. Negative token/latency deltas favor efficiency. No accuracy claim is made for mocks or provisional labels.

| Contrast | Metric | Cases / groups | Mean delta | 95% group bootstrap CI | Holm sign-flip p |
| --- | --- | --- | ---: | --- | ---: |
| b0_vs_p1 | fetched_recall | 8/4 | 0.479 | [0.125, 0.8333333333333334] | 0.750 |
| b0_vs_p1 | fetched_precision | 8/4 | 0.080 | [0.020833333333333332, 0.15624999999999997] | 0.750 |
| b0_vs_p1 | retained_recall | 8/4 | 0.479 | [0.125, 0.8333333333333334] | 0.750 |
| b0_vs_p1 | checker_received_recall | 8/4 | 0.479 | [0.125, 0.8333333333333334] | 0.750 |
| b0_vs_p1 | violation_f1 | 0/0 | unavailable | None | unavailable |
| b0_vs_p1 | checker_input_tokens | 8/4 | 926.750 | [-28.5, 1872.5] | 0.500 |
| b0_vs_p1 | end_to_end_ms | 8/4 | 0.814 | [-0.0776129309087994, 1.550816115923226] | 0.375 |
| b0_vs_p1 | search_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| b0_vs_p1 | fetch_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | fetched_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | fetched_precision | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | retained_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | checker_received_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | violation_f1 | 0/0 | unavailable | None | unavailable |
| p1_vs_p2 | checker_input_tokens | 8/4 | -1110.000 | [-1308.0, -818.5] | 0.375 |
| p1_vs_p2 | end_to_end_ms | 8/4 | 1.839 | [1.3438297416238734, 2.241968429492166] | 0.375 |
| p1_vs_p2 | search_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | fetch_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | fetched_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | fetched_precision | 8/4 | -0.024 | [-0.048611111111111105, 0.0] | 1.000 |
| p2_vs_p3 | retained_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | checker_received_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | violation_f1 | 0/0 | unavailable | None | unavailable |
| p2_vs_p3 | checker_input_tokens | 8/4 | 1978.375 | [1888.625, 2035.0] | 0.375 |
| p2_vs_p3 | end_to_end_ms | 8/4 | 10.377 | [9.369078286302585, 11.121062561869621] | 0.375 |
| p2_vs_p3 | search_calls | 8/4 | 2.000 | [2.0, 2.0] | 0.375 |
| p2_vs_p3 | fetch_calls | 8/4 | 2.375 | [1.625, 3.0] | 0.375 |

## Per-case missed evidence and regressions

- C001-b0-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-p1-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-p2-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-p3-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-b0-r01, checker 0: missed ['SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-b0-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-b0-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-b0-r01, checker 0: missed ['SFCG-019', 'SFCG-024']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-b0-r01, checker 0: missed ['SFCG-019', 'SFCG-024']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-b0-r01, checker 0: missed ['SFCG-007', 'SFCG-008', 'SFCG-031', 'SFCG-032']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-b0-r01, checker 0: missed ['SFCG-008', 'SFCG-031', 'SFCG-032']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-r-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.

## Limitations

- Synthetic local data cannot establish enterprise retrieval or model performance.
- Provisional annotations are not independent ground truth; compliance accuracy is disabled unless explicitly exploratory.
- Mock/unexecuted checkers have null compliance metrics, never perfect accuracy or zero model false negatives.
- Repetitions are averaged within case; inferential tests resample matched variant groups, not individual repeated runs.
- Small group counts produce coarse p-values and unstable confidence intervals; tests are exploratory.
- Sign-flip tests assume symmetric independent group differences; sign tests also reported. Holm adjustment is within metric/panel only.
- Feature/category mappings and source-line ranking are explicit approximations, not enterprise ranking scores.
- Unknown source rule IDs cannot be scored canonically; they remain separately listed.
- Provider token counters are not measured bills. Output tokens, total tokens, ACU and Rovo credits remain null when unavailable.
- Archived P3 traces do not isolate feature/reduction timings; these remain null instead of inferred zero.
- Legacy traces do not always establish model submission for unresolved/error results; model-supplied coverage can be unknown.
- Failed/missing runs are reported separately; paired metrics use available case pairs and disclose exclusions.
- End-to-end latency includes the entire configured checker matrix; checker_ms is specific to one checker.

## Missing and incomplete observations

Missing run files: 0. Checker statuses: {'not_evaluated': 120}.
- C001-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C001-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C001-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C001-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C001-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C001-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C002-p1-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p1-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p1-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p2-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p2-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p2-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C002-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C002-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C002-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C003-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C003-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C003-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C003-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C003-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C003-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C004-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C004-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C004-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C004-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C004-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C004-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C005-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C005-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C005-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C005-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C005-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C005-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C006-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C006-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C006-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C006-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C006-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C006-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C007-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C007-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C007-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C007-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C007-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C007-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C008-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C008-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C008-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C008-r-r01: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C008-r-r02: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].
- C008-r-r03: run=finished; incomplete=['checker_context_budget', 'evidence_context']; errors=[].

## Per-case regressions

- b0_vs_p1 / checker_input_tokens: {'C007': 1546, 'C006': 2199, 'C005': 2199, 'C008': 1546}
- b0_vs_p1 / end_to_end_ms: {'C007': 1.5475419349968433, 'C001': 0.5909717486550399, 'C006': 1.5577080193907022, 'C004': 0.3171944214651985, 'C005': 1.3673613624026384, 'C003': 0.4581940205146866, 'C008': 1.7306531469027204}
- p1_vs_p2 / end_to_end_ms: {'C007': 2.5232356662551556, 'C001': 0.9351389016956091, 'C006': 2.1593609514335803, 'C004': 1.667208193490902, 'C002': 1.568458043038845, 'C005': 2.2094997111707926, 'C003': 1.5726389052967225, 'C008': 2.0757773891091347}
- p2_vs_p3 / fetched_precision: {'C001': -0.027777777777777776, 'C004': -0.05555555555555555, 'C002': -0.05555555555555555, 'C003': -0.05555555555555555}
- p2_vs_p3 / checker_input_tokens: {'C007': 2035, 'C001': 1984, 'C006': 2035, 'C004': 1988, 'C002': 1727, 'C005': 2035, 'C003': 1988, 'C008': 2035}
- p2_vs_p3 / end_to_end_ms: {'C007': 10.89554171388348, 'C001': 10.800041956827046, 'C006': 10.915041978781423, 'C004': 8.674958643193047, 'C002': 10.113374950985115, 'C005': 11.187875022490818, 'C003': 8.941611119856438, 'C008': 11.485791532322764}
- p2_vs_p3 / search_calls: {'C007': 2, 'C001': 2, 'C006': 2, 'C004': 2, 'C002': 2, 'C005': 2, 'C003': 2, 'C008': 2}
- p2_vs_p3 / fetch_calls: {'C007': 3, 'C001': 2, 'C006': 3, 'C004': 2, 'C002': 1, 'C005': 3, 'C003': 2, 'C008': 3}
