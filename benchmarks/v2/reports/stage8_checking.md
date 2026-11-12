# Stage 8 offline checking demonstration

The synthetic rule SFCG-981 requires a null check before the first output-pointer
write. Both cases use the same source-backed rule. No annotation file is used to
produce a prediction.

| Input | Synthetic checker status / finding | Mock status / finding |
| --- | --- | --- |
| `pointer_bad.c` | evaluated / violating, line 3 (`    *out = 7;`) | not_evaluated / unresolved |
| `pointer_good.c` | evaluated / compliant for the supported pointer-guard subset | not_evaluated / unresolved |

The bad-task input hash is
`5cdf739e760f82c8399af9240ff08efdaa8e11fe5cd275a4a36b8e73d39378fe`;
the good-task hash is
`3fc112542a1b77a7caec174ef17a47ec129eb1e731d34a29af7792fbf6b0886b`.
Within each comparison both adapters record the same task and prompt hashes.
The exact task JSON and result JSON files are alongside this report as
`stage8_pointer_bad_task.json`, `stage8_pointer_good_task.json`,
`stage8_pointer_bad_results.json`, and `stage8_pointer_good_results.json`.

The canonical skill version is 1.0.0 and prompt version FCGC-PROMPT-V1. Offline
token counts are null. Execution durations in the result files are local single-run
measurements. These are actual deterministic demo results, not LLM results or
general FCG compliance claims. The Ollama template returned `unavailable` because
networking was disabled. No installed Ollama executable was found; a service probe
was sandbox-denied and no model inference was claimed.

See [checker operation](../../../docs/checking.md) for exact commands, frozen
P2/P3 task support, optional Ollama activation, cross-model comparison, schema
validation, and limitations. Devin remains an explicitly unimplemented adapter.

Validation: 81 pytest tests passed; Ruff passed; the skill creator validator
reported “Skill is valid!” A 0.8.0 wheel was built and installed in a temporary
environment. Its packaged canonical skill loaded at version 1.0.0 and the installed
synthetic checker reproduced the unguarded-write violation. Wheel assets matched
the canonical skill/prompt bytes, and no ground-truth files were packaged.
