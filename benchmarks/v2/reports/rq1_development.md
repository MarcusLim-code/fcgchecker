# RQ1 development-set comparison: B0 versus P1

Dataset 2.0.0; annotations 1.0.0-provisional.
Only the eight development annotations were read. Labels remain provisional.

## Ranking and budget

One lexical search and up to three document fetches per case for each strategy; same corpus, source scope, score, tie-break, document K, and rule K.
A fetched document contributes its canonical rule IDs ordered by source line. Precision and recall use the first 18 distinct rule IDs after document ranking; decoys contribute no IDs. Precision divides by the number of returned rule IDs (up to K). Recall divides by applicable rule IDs. The unit is a rule, not a document. Case outcome compares recall first and precision when recall ties.

Actual matched budget: **True**.

## Aggregate

| Strategy | Relevant / applicable | Relevant / retrieved | Micro recall | Micro precision | Searches | Fetches | Extraction ms | Planning ms | Retrieval ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 8/22 | 8/96 | 0.364 | 0.083 | 8 | 24 | 0.000 | 0.000 | 1.390 |
| P1 | 20/22 | 20/132 | 0.909 | 0.152 | 8 | 24 | 6.860 | 0.112 | 1.364 |

## Per-case comparison

| Case | Applicable | B0 documents | P1 documents | B0 recall / precision | P1 recall / precision | Outcome | Search Δ | Fetch Δ |
| --- | ---: | --- | --- | --- | --- | --- | ---: | ---: |
| C001 | 3 | pointers, api_returns, decoy_host_tools | pointers, resources, api_returns | 0.333 / 0.083 | 0.333 / 0.056 | regression | 0 | 0 |
| C002 | 2 | pointers, api_returns, decoy_host_tools | api_returns, error_flow, resources | 0.500 / 0.083 | 1.000 / 0.111 | improvement | 0 | 0 |
| C003 | 2 | pointers, api_returns, decoy_host_tools | pointers, api_returns, decoy_host_tools | 1.000 / 0.167 | 1.000 / 0.167 | tie | 0 | 0 |
| C004 | 2 | pointers, api_returns, decoy_host_tools | pointers, api_returns, decoy_host_tools | 1.000 / 0.167 | 1.000 / 0.167 | tie | 0 | 0 |
| C005 | 3 | pointers, api_returns, decoy_host_tools | pointers, buffers, api_returns | 0.333 / 0.083 | 1.000 / 0.167 | improvement | 0 | 0 |
| C006 | 3 | pointers, api_returns, decoy_host_tools | pointers, buffers, api_returns | 0.333 / 0.083 | 1.000 / 0.167 | improvement | 0 | 0 |
| C007 | 4 | pointers, api_returns, decoy_host_tools | resources, api_returns, error_flow | 0.000 / 0.000 | 1.000 / 0.222 | improvement | 0 | 0 |
| C008 | 3 | pointers, api_returns, decoy_host_tools | resources, api_returns, error_flow | 0.000 / 0.000 | 1.000 / 0.167 | improvement | 0 | 0 |

## Queries and rule evidence

### C001

Applicable: SFCG-001, SFCG-007, SFCG-011.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines resource lock handle cleanup release pointer null output validation dereference general firmware coding requirements`
P1 concepts: resource acquisition and cleanup, pointer contract validation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: SFCG-001; missed: SFCG-007, SFCG-011; irrelevant: 11.
P1 relevant: SFCG-001; missed: SFCG-007, SFCG-011; irrelevant: 17.

### C002

Applicable: SFCG-001, SFCG-011.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines API return result status failure resource lock handle cleanup release general firmware coding requirements`
P1 concepts: possible unchecked API result, resource acquisition and cleanup, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: SFCG-001; missed: SFCG-011; irrelevant: 11.
P1 relevant: SFCG-001, SFCG-011; missed: none; irrelevant: 16.

### C003

Applicable: SFCG-013, SFCG-014.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines pointer null output validation dereference general firmware coding requirements`
P1 concepts: pointer contract validation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: SFCG-013, SFCG-014; missed: none; irrelevant: 10.
P1 relevant: SFCG-013, SFCG-014; missed: none; irrelevant: 10.

### C004

Applicable: SFCG-013, SFCG-014.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines pointer null output validation dereference general firmware coding requirements`
P1 concepts: pointer contract validation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: SFCG-013, SFCG-014; missed: none; irrelevant: 10.
P1 relevant: SFCG-013, SFCG-014; missed: none; irrelevant: 10.

### C005

Applicable: SFCG-013, SFCG-019, SFCG-024.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines buffer capacity array count boundary pointer null output validation dereference general firmware coding requirements`
P1 concepts: buffer boundary safety, pointer contract validation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: SFCG-013; missed: SFCG-019, SFCG-024; irrelevant: 11.
P1 relevant: SFCG-013, SFCG-019, SFCG-024; missed: none; irrelevant: 15.

### C006

Applicable: SFCG-013, SFCG-019, SFCG-024.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines buffer capacity array count boundary pointer null output validation dereference general firmware coding requirements`
P1 concepts: buffer boundary safety, pointer contract validation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: SFCG-013; missed: SFCG-019, SFCG-024; irrelevant: 11.
P1 relevant: SFCG-013, SFCG-019, SFCG-024; missed: none; irrelevant: 15.

### C007

Applicable: SFCG-008, SFCG-031, SFCG-032, SFCG-007.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines resource lock handle cleanup release error flow propagation timeout retry general firmware coding requirements`
P1 concepts: resource acquisition and cleanup, error handling and propagation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: none; missed: SFCG-008, SFCG-031, SFCG-032, SFCG-007; irrelevant: 12.
P1 relevant: SFCG-031, SFCG-032, SFCG-007, SFCG-008; missed: none; irrelevant: 14.

### C008

Applicable: SFCG-008, SFCG-031, SFCG-032.
B0 query: `firmware coding guidelines C source`
P1 query: `synthetic C firmware coding guidelines resource lock handle cleanup release error flow propagation timeout retry general firmware coding requirements`
P1 concepts: resource acquisition and cleanup, error handling and propagation, general firmware rules (feature-concepts-v1, p1-template-v1).
B0 relevant: none; missed: SFCG-008, SFCG-031, SFCG-032; irrelevant: 12.
P1 relevant: SFCG-031, SFCG-032, SFCG-008; missed: none; irrelevant: 15.

## Limits

These are provisional synthetic annotations and one deterministic local run. Timings include local Python overhead; mapping files were loaded once before the timed per-case runs. They are not a service-latency estimate. P1 uses heuristics over syntax; neither path performs compliance checking. No Atlassian ranking scores or held-out labels were used.
