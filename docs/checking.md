# Stage 8 checker operation

`ComplianceChecker.check` accepts either the legacy retrieval `CheckerRequest`
or a `FrozenCheckingTask`. The latter freezes code, source documents, selected
`RuleEvidence`, context status, and warnings. The host validates exact source
spans and keeps original documents for auditing. Models receive the code, document
identities, and selected rule/context excerpts; full fetched documents are not
reintroduced into a reduced model input.

All new checker adapters render the same canonical
[`SKILL.md`](../skills/fcg_checking/SKILL.md), version 1.1.0, and
[`prompt.txt`](../skills/fcg_checking/prompt.txt), version FCGC-PROMPT-V1.
The skill and prompt are packaged as shared data in the wheel. The provider
envelope and generation settings are configured separately.

## Offline demonstration

```sh
.venv/bin/fcgc freeze-task \
  --source src/fcgc/fixtures/checking/pointer_bad.c \
  --guideline src/fcgc/fixtures/checking/pointer.md \
  --case pointer_bad --output /tmp/fcgc-pointer-task.json
.venv/bin/fcgc check-task --task /tmp/fcgc-pointer-task.json \
  --checker-config src/fcgc/config/checker_demo.toml \
  --checker-config src/fcgc/config/checker_mock.toml \
  --output /tmp/fcgc-pointer-results.json
```

The demonstration checker supports only SFCG-981 with the exact supplied
normative text and a fully recognized single-function C shape: an `int` function
with one `int *` parameter, an optional early `if (pointer == NULL) return -1;`,
one literal integer write through that pointer, and `return 0;`. Extra functions,
statements, comments, aliases, different guards, conditions, exceptions, ambiguous
evidence, and referenced dependencies are outside its supported subset and yield
unresolved. It inspects source behavior; it never maps case IDs to labels.

`MockChecker` returns unresolved findings and `not_evaluated`. It exercises the
pipeline, hashing, skill rendering, and contracts without generating predictions.
`DevinChecker` uses the same contract and instructions but returns `not_evaluated`
until a real adapter is implemented. No WD API or tool names are assumed.
The default legacy placeholder still returns `not_evaluated`.

To freeze selected P2/P3 evidence instead of local guideline files:

```sh
.venv/bin/fcgc freeze-task \
  --packed-audit benchmarks/v2/reports/stage6_C001.json \
  --output /tmp/fcgc-selected-task.json
```

Budget-exceeded audits cannot become checking tasks. Incomplete audits stay
incomplete; providers are not invoked and their per-rule decisions stay unresolved.

## Optional Ollama provider

No Ollama executable was found during this implementation. A loopback availability
probe was denied by the execution sandbox, so a running service could not be
verified. No local-model inference was performed. Adapter tests simulate transport
responses and are contract tests, not model-performance measurements.

1. Install Ollama using its official installation instructions, or use an existing
   installation. Start it with `ollama serve` if needed.
2. Run `ollama list` and choose an exact locally installed model identifier. Model
   provisioning is separate: if needed, explicitly run `ollama pull <model:tag>`
   with network access before offline use. FCGC never installs or pulls a model.
   Choose a local model, not a cloud-backed model.
3. Copy `src/fcgc/config/checker_ollama.toml` to a local config file. Set `model`
   to that exact identifier and `allow_network = true`. Keep `allow_remote = false`
   and the endpoint on loopback. Even loopback HTTP requires explicit opt-in.
4. Execute the frozen task:

```sh
.venv/bin/fcgc check-task --task /tmp/fcgc-pointer-task.json \
  --checker-config /tmp/fcgc-ollama-a.toml --output /tmp/fcgc-ollama-a-results.json
```

The adapter uses Ollama's documented `/api/chat` endpoint with `stream=false`,
a JSON output schema, and configured temperature, seed, top_p, and output limit.
It records model details exposed by `/api/show`, the response model name, and
`prompt_eval_count`/`eval_count` when available. See the official
[chat API](https://docs.ollama.com/api/chat) and
[model API](https://github.com/ollama/ollama/blob/main/docs/api.md#show-model-information)
documentation. Requests have a timeout
and response-byte limit; redirects and environment HTTP proxies are disabled.
Non-loopback origins require both `allow_network=true` and `allow_remote=true`.
Models advertised as remote-backed also require `allow_remote=true`; failed
model-metadata requests abort before generation.
The checked-in template disables networking and returns `unavailable`.

For cross-model runs, configure another file with a different model/settings and
repeat `--checker-config` on the same `check-task` invocation. Each checker receives
freshly validated copies of exactly the same frozen task. Task hash, rendered
prompt hash, instruction hash, provider/model, settings, skill/prompt versions,
available token counts, model details, and wall-clock time are recorded per run.
Shared instructions do not imply equivalent model behavior or reproducibility
across runtimes, weight revisions, quantization, or ignored generation settings.

## Validation and interpretation

Models emit only `ModelFindings`. The host assigns execution status and metadata.
Exactly one finding is required for every supplied evidence ID. Duplicate, missing,
or unknown IDs, malformed JSON, unsupported source IDs/refs, non-verbatim quotes,
invalid source offsets, contradictory decisions, and fabricated code locations are
rejected. Rejected responses produce `error` with unresolved findings; unavailable
providers produce `unavailable` with unresolved findings. No positive judgment is
recovered from invalid output.
Evidence still marked `review_required` permits unresolved findings only until
its source interpretation has been reviewed.

`evaluated` means supported per-rule judgments were produced; it is not an
artifact-wide compliant result. Missing applicable guidelines may remain absent.
Source validation proves citation integrity, not the correctness of applicability
or program reasoning. General model judgments still need independent evaluation
and firmware review. Offline mock/demo token counts are null rather than invented;
model counts are recorded only when the provider supplies them. Stage 6 token
estimates do not describe this new skill/schema prompt automatically.
