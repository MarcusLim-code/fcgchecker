# Stage 7: bounded evidence-sufficiency fallback

These offline development runs use observable warning signals only. No ground-truth
annotations were opened for this comparison. Recovered category signals below are
heuristic matches in selected normative wording; they do not measure recall.

```sh
.venv/bin/fcgc reduce --case C001 --strategy p3 \
  --config src/fcgc/config/benchmark.toml \
  --output benchmarks/v2/reports/stage7_C001.json
.venv/bin/fcgc reduce --case C002 --strategy p3 \
  --config src/fcgc/config/benchmark.toml \
  --output benchmarks/v2/reports/stage7_C002.json
```

| Case | Initial triggers | Searches / fetches, total | Additional calls | Additional raw context tokens | Packed input token delta | Final result |
| --- | --- | --- | --- | ---: | ---: | --- |
| C001 | Missing initialization evidence; ambiguous applicability | 3 / 5 | 2 searches, 2 fetches | 307 | +343 | insufficient_evidence |
| C002 | Missing initialization evidence; missing dependency; ambiguous applicability | 3 / 4 | 2 searches, 1 fetch | 230 | +297 | insufficient_evidence |

Both runs reached the three-round limit. The missing initialization signal was
recovered by fetching `initialization`, which supplied six new explicit rule IDs.
C001's final broadening also fetched `decoy_bootloader`; its presence did not clear
the remaining applicability uncertainty. C002's query for `resources.md` returned
only already-known sources, so it made no additional fetch and the dependency
remained unresolved. The reports retain all query texts, ranked responses, new
source/rule IDs, selection decisions, and final packed context.

C001 used 614 raw context tokens initially and 921 finally; its packed input grew
from 654 to 997 estimated tokens. C002 grew from 631 to 861 raw context tokens,
and from 664 to 961 packed tokens. The same Stage 6 word/punctuation approximation
is used throughout. These are counts of rendered input, excluding audit JSON
transport and model-specific tokenization.

On this local run, fallback and reassessment added 7.397 ms for C001 and 7.219 ms
for C002. Initial processing took 9.337 ms and 9.321 ms respectively. These are
single wall-clock observations, including local reduction/packing overhead, and
do not estimate enterprise latency. No checker was invoked. Both requests are
marked incomplete and blocked by `checker_payload()`.

Defaults count the initial pass in the limits: three rounds/searches, eight fetch
attempts, eight unique candidate sources, 3,000 packed tokens, and a five-second
soft elapsed limit. Each search returns at most three documents, reduced to the
remaining source capacity. Calls that fail count against the budget. Failed source
IDs are not retried in the same run. Duplicate references are never refetched.
Elapsed time is checked before each synchronous provider call; an in-flight call
cannot be interrupted by this local interface. Providers need their own timeouts.

The gate is deliberately conservative about conditions and exceptions. Its
`sufficient_signals` result means configured warning signals were absent, not that
every applicable rule was retrieved. Category wording can produce false matches
or miss synonyms. Unmapped feature categories remain uncovered. Scope changes and
source-identity changes are rejected; no hidden ranking confidence is used.
