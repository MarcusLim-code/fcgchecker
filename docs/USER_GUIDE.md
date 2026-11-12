# User guide

Start in a supported Devin session with the project installed:

```text
/fcg-doctor
/fcg-rules examples/firmware/sensor_start.c
/fcg-check examples/firmware/sensor_start.c --function start_sensor
/fcg-compare --case C001 --repeat 3
/fcg-report --experiment latest
```

The agent runs the shared backend and presents the report. Check/rules default to
local synthetic retrieval and P3; checking defaults to mock/not_evaluated. Choose
`--mode wd --config config/wd_agent.toml` only inside an authorized host with
approved access. Native target-host discovery and live WD operation remain
unverified. See [full command options](SLASH_COMMANDS.md) and [START_HERE](../START_HERE.md).

## Terminal tools for maintainers

The equivalent internal CLI remains available for local use, tests and automation.
Run from the repository root after installing. Paths below ship with this release.
`--help` lists each command's options.

```sh
.venv/bin/fcgc doctor --config config/local.toml
.venv/bin/fcgc info
.venv/bin/fcgc features --source src/fcgc/fixtures/cases/sensor_poll.c --case sensor --output outputs/sensor-features.json
.venv/bin/fcgc extract-rules --document src/fcgc/fixtures/benchmark_guidelines/buffers.md --source-id buffers --document-version 2.0.0 --output outputs/buffer-rules.json
.venv/bin/fcgc retrieve --case C001 --strategy b0 --config config/local.toml --top-k 3 --output outputs/b0.json
.venv/bin/fcgc retrieve --case C001 --strategy p1 --config config/local.toml --top-k 3 --output outputs/p1.json
.venv/bin/fcgc reduce --case C001 --strategy p2 --config config/local.toml --output outputs/p2.json
.venv/bin/fcgc reduce --case C001 --strategy p3 --config config/local.toml --output outputs/p3.json
.venv/bin/fcgc check --case C001 --source src/fcgc/fixtures/benchmark_cases/C001.c --strategy p3 --config config/local.toml --output outputs/check-C001.json
```

`doctor` validates local provider construction, the generic search/fetch path and
instruction availability. It returns nonzero when offline readiness is false;
it does not probe enterprise services or promise that Ollama is running. `info`
lists provider capabilities and exact installed library/instruction versions.

Feature extraction records AST observations separately from inferred categories
and unknowns. Rule extraction retains verbatim source spans; review flags are
important evidence, not parsing success claims. Retrieval preserves result order.
`check --output` writes the complete structured strategy trace and checker task;
stdout contains the checker result. `check --log` appends complete traces as JSONL.
`retrieve --log` retains its compact retrieval-summary JSONL format with documents
and query/version information. Neither log format contains ground-truth labels.

Local inputs must be nonempty UTF-8 C/Markdown text, at most 8 MB each. Newline
bytes are preserved. NUL bytes and invalid UTF-8 are rejected. Output options reject
input aliases, including symlinks/hard links. Write output to a dedicated directory.
Existing explicit output files may be replaced; locked experiment/replay stores
have stricter freshness and configuration checks.

## A genuine supported offline judgment

The benchmark mock cannot evaluate compliance. The deterministic demo really
inspects the supported single-pointer-store source shape:

```sh
.venv/bin/fcgc freeze-task --source src/fcgc/fixtures/checking/pointer_bad.c --guideline src/fcgc/fixtures/checking/pointer.md --case pointer-bad --output outputs/pointer-task.json
.venv/bin/fcgc check-task --task outputs/pointer-task.json --checker-config src/fcgc/config/checker_demo.toml --checker-config src/fcgc/config/checker_mock.toml --output outputs/pointer-results.json
```

The demo returns `evaluated`, rule SFCG-981 violating at line 3 with a source
citation; the mock returns `not_evaluated`. Using `pointer_good.c` produces a
supported compliant decision. Unsupported syntax, additional behavior, conditions,
exceptions or ambiguity produce unresolved, never a guessed compliant result.
This demonstration is not a general firmware analyzer or a benchmark accuracy result.

For checker-only comparisons, repeat `--checker-config` on the same frozen task.
This never reruns retrieval. Optional Ollama setup is in [checking.md](checking.md).

## Complete acceptance and reports

```sh
.venv/bin/fcgc validate-local --dataset-root benchmarks/v2 --output outputs/release-local
.venv/bin/fcgc report --config outputs/release-local/evaluation.toml
.venv/bin/fcgc replay --run outputs/release-local/experiment/runs/C001-p3-r01/trace.json --output outputs/release-replay
```

The first command uses development predictions and later reads annotations for
evaluation. Dataset quality checks inspect both splits structurally and do not
calibrate from held-out labels. P3 may finish with `insufficient_evidence`; its
context remains incomplete and checking abstains. `finished` in a trace denotes
execution completion, not complete evidence or an artifact-wide compliant verdict.
Provider failures exit nonzero and preserve errors in structured traces when a
run has begun. Exact replay needs content snapshots and matching code/instructions.
