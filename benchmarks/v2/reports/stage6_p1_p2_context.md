# Stage 6: P1 versus P2 context output

These are **offline development-case context measurements**, not compliance
results or a retrieval-accuracy evaluation. Both paths use the same P1 query,
three-document Top-K, local corpus, search ranking, and fetched source text.
P2 then segments and selects rules; it does not search again.

```sh
.venv/bin/fcgc reduce --case C001 --strategy p2 \
  --config src/fcgc/config/benchmark.toml --top-k 3 \
  --output benchmarks/v2/reports/stage6_C001.json
.venv/bin/fcgc reduce --case C005 --strategy p2 \
  --config src/fcgc/config/benchmark.toml --top-k 3 \
  --output benchmarks/v2/reports/stage6_C005.json
```

The local `regex-word-punctuation-v1` approximation counts Unicode word runs
and individual punctuation symbols. “Retrieval context” counts raw fetched
document content only. “P1 checker input” is a comparison rendering with the
same standard instructions and firmware code plus all fetched documents.
“P2 checker input” counts the actual `rendered_input` field of the packed
request. JSON transport, model-specific tokenization, and service latency are
outside these counts.
The full audit JSON retains P1 documents and all decisions; only the packed
request's `rendered_input` is intended as future checker model input.

| Case | Context status | Raw fetched tokens | P1 full input | P2 packed input | P1 minus P2 | Candidates / selected / excluded |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| C001 | complete | 614 | 802 | 648 | +154 | 12 / 10 / 2 |
| C005 | complete | 749 | 969 | 1,075 | −106 | 18 / 16 / 2 |

For C001, P1 fetches `api_returns`, `decoy_host_tools`, and `pointers` in that
ranked order. P2 keeps the unchanged query and these same fetched documents as
its retrieval trace. Its packed input includes the firmware code, standard
instructions, source directory, and ten verbatim rule candidates with their
conditions, exceptions, definitions, and references. Two API-specific rules
(`SFCG-002` and `SFCG-003`) are excluded because they bind calls absent from
the parsed C artifact. Their exact source references and reasons remain in the
audit JSON. This is a bounded static heuristic, not proof of inapplicability.

For C005, retaining complete buffer and pointer rule context plus source and
review metadata costs 106 more estimated tokens than sending the fetched
documents. The reducer does not remove required text to force a saving.

On the C001 run, local P1 retrieval took 0.246 ms, feature extraction 6.307 ms,
query planning 0.060 ms, rule reduction 2.877 ms, and packing 0.235 ms.
These single-run wall-clock observations vary with the machine and do not
estimate remote service latency.

A 100-token C001 budget returns `budget_exceeded`, no packed checker request,
and a measured requirement of 648 tokens. The `complete` context status above
means the selected evidence fits and no referenced evidence is unresolved
*within the fetched set*. It does not establish that retrieval found every
applicable guideline, or that the firmware complies. No checker was invoked.
