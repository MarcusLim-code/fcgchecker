# FCGC research evaluation

Split: development. Labels: `{'data': 'synthetic', 'retrieval': ['benchmark'], 'checking': ['mock'], 'retrieval_kind': ['local_fixture'], 'checker_kind': ['mock'], 'resources': 'local token estimates and measured wall time; provider tokens only when exposed; no billing measurements', 'ground_truth': ['provisional']}`.
Quality flags: {'incomplete_observations': 30, 'unsupported_rule_observations': 21, 'ambiguous_rule_instances': 54, 'unresolved_finding_instances': 1440, 'compliance_eligible_observations': 0}.

Rule K is a unique canonical-rule prefix after source-arrival rank, source line, then ID. Document K is the experiment search budget; it is not rule K.
Precision divides by actual unique returned rule IDs up to K; no-applicable-rule recall and zero-denominator precision are undefined.
Checker-received means the adapter got the frozen task; model-supplied coverage is separately recorded and is empty for mocks.

| Configuration | Cases | Fetched recall@K | Fetched precision@K | Retained recall@K | Checker-received recall@K | Violation F1 | Input tokens mean | Calls search/fetch mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 155530ba / b0 / checker 0 | 8 | 0.438 | 0.083 | 0.438 | 0.438 | unavailable | 5717.875 | 1.000/3.000 |
| 155530ba / p1 / checker 0 | 8 | 0.917 | 0.163 | 0.917 | 0.917 | unavailable | 6644.625 | 1.000/3.000 |
| 155530ba / p2 / checker 0 | 8 | 0.917 | 0.163 | 0.917 | 0.917 | unavailable | 5534.625 | 1.000/3.000 |
| 155530ba / p3 / checker 0 | 8 | 0.917 | 0.139 | 0.917 | 0.917 | unavailable | 7513.000 | 3.000/5.375 |

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
| b0_vs_p1 | end_to_end_ms | 8/4 | 1.121 | [0.4126389976590872, 1.828690757974982] | 0.375 |
| b0_vs_p1 | search_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| b0_vs_p1 | fetch_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | fetched_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | fetched_precision | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | retained_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | checker_received_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | violation_f1 | 0/0 | unavailable | None | unavailable |
| p1_vs_p2 | checker_input_tokens | 8/4 | -1110.000 | [-1308.0, -818.5] | 0.375 |
| p1_vs_p2 | end_to_end_ms | 8/4 | 1.551 | [0.8896923682186748, 2.0241615420673047] | 0.375 |
| p1_vs_p2 | search_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p1_vs_p2 | fetch_calls | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | fetched_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | fetched_precision | 8/4 | -0.024 | [-0.048611111111111105, 0.0] | 1.000 |
| p2_vs_p3 | retained_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | checker_received_recall | 8/4 | 0.000 | [0.0, 0.0] | 1.000 |
| p2_vs_p3 | violation_f1 | 0/0 | unavailable | None | unavailable |
| p2_vs_p3 | checker_input_tokens | 8/4 | 1978.375 | [1888.625, 2035.0] | 0.375 |
| p2_vs_p3 | end_to_end_ms | 8/4 | 10.891 | [10.167835125078756, 11.76905717390279] | 0.375 |
| p2_vs_p3 | search_calls | 8/4 | 2.000 | [2.0, 2.0] | 0.375 |
| p2_vs_p3 | fetch_calls | 8/4 | 2.375 | [1.625, 3.0] | 0.375 |

## Per-case missed evidence and regressions

- C001-b0-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-p1-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-p2-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C001-p3-r01, checker 0: missed ['SFCG-007', 'SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-b0-r01, checker 0: missed ['SFCG-011']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C002-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-b0-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C003-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-b0-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C004-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-b0-r01, checker 0: missed ['SFCG-019', 'SFCG-024']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C005-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-b0-r01, checker 0: missed ['SFCG-019', 'SFCG-024']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C006-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-b0-r01, checker 0: missed ['SFCG-007', 'SFCG-008', 'SFCG-031', 'SFCG-032']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C007-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-b0-r01, checker 0: missed ['SFCG-008', 'SFCG-031', 'SFCG-032']; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-p1-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-p2-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.
- C008-p3-r01, checker 0: missed []; lost during reduction []; model FN None; model FP None; status not_evaluated.

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

Missing run files: 0. Checker statuses: {'not_evaluated': 96}.
- C001-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C001-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C001-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p1-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p1-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p1-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p2-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p2-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p2-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C002-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C003-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C003-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C003-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C004-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C004-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C004-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C005-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C005-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C005-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C006-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C006-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C006-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C007-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C007-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C007-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].
- C008-p3-r01: run=finished; incomplete=['evidence_context']; errors=[].
- C008-p3-r02: run=finished; incomplete=['evidence_context']; errors=[].
- C008-p3-r03: run=finished; incomplete=['evidence_context']; errors=[].

## Per-case regressions

- b0_vs_p1 / checker_input_tokens: {'C005': 2199, 'C006': 2199, 'C007': 1546, 'C008': 1546}
- b0_vs_p1 / end_to_end_ms: {'C001': 1.3082359607021017, 'C004': 0.3263750889648991, 'C005': 2.2058609562615548, 'C006': 1.7541247264792519, 'C003': 0.2052360214293003, 'C007': 1.2056659907102585, 'C008': 2.149111358448863}
- p1_vs_p2 / end_to_end_ms: {'C001': 0.1610826390484963, 'C004': 1.4196112751960754, 'C005': 1.852958385522168, 'C006': 2.4871806769321356, 'C002': 1.1538052931427947, 'C003': 1.7532638739794502, 'C007': 2.197042029971877, 'C008': 1.380986301228404}
- p2_vs_p3 / fetched_precision: {'C001': -0.027777777777777776, 'C004': -0.05555555555555555, 'C002': -0.05555555555555555, 'C003': -0.05555555555555555}
- p2_vs_p3 / checker_input_tokens: {'C001': 1984, 'C004': 1988, 'C005': 2035, 'C006': 2035, 'C002': 1727, 'C003': 1988, 'C007': 2035, 'C008': 2035}
- p2_vs_p3 / end_to_end_ms: {'C001': 9.57429176196456, 'C004': 14.808819085980456, 'C005': 10.728931054472922, 'C006': 10.99800031321744, 'C002': 10.297624782348672, 'C003': 9.501583486174544, 'C007': 10.542902629822493, 'C008': 10.678347044934828}
- p2_vs_p3 / search_calls: {'C001': 2, 'C004': 2, 'C005': 2, 'C006': 2, 'C002': 2, 'C003': 2, 'C007': 2, 'C008': 2}
- p2_vs_p3 / fetch_calls: {'C001': 2, 'C004': 2, 'C005': 3, 'C006': 3, 'C002': 1, 'C003': 2, 'C007': 3, 'C008': 3}
