# FCGC 0.11.0 release readiness report

Scope: local synthetic research prototype. Validation environment: CPython 3.13.3,
macOS 15.3.2 arm64. **Local acceptance passed; WD deployment remains pending.**
The benchmark labels are provisional and all benchmark checkers were mocks.
Live Atlassian MCP, Devin and local-LLM inference were not tested.

## 1. Product overview

FCGC executes firmware-aware retrieval and evidence preparation for coding-guideline
checking. It separates observed code features, inferred search concepts, authoritative
source excerpts, applicability judgments and research labels. It provides a fully
offline vertical slice with reproducible fixtures, interchangeable provider contracts,
structured traces, replay and post-hoc analysis. Synthetic rules are not official WD
requirements. This is a research prototype, not a general firmware verification tool.

## 2. Implemented features and audit fixes

Implemented B0 generic retrieval, P1 deterministic query planning, P2 source-preserving
reduction, P3 bounded sufficiency/fallback and optional broad reference R; C AST
observations with bounded fallback; contextual narrative/list/table segmentation;
canonical checking skill/prompt; validated findings/citations; isolated locked
experiments, content snapshots, replay, metrics, paired statistics and offline reports.

The final audit reviewed source modules, contracts, configs, fixtures, tests and
documentation. It found and fixed these concrete integration defects:

- Mutated typed provider models could bypass field checks. Contracts now revalidate
  instances, including nested fields; firmware hashes are checked against content.
- Local fetch returned mutable internal documents and accepted mutable caller scope.
  Responses and configured scopes now use independent snapshots.
- Universal-newline reads changed source bytes/hashes. C and local guideline input
  now preserve exact UTF-8 text, with empty/NUL/oversize input rejected cleanly.
- Ollama scalar/list/malformed envelopes and invalid token counters could escape as
  crashes. Consumed metadata, messages and counters are typed and host-validated;
  invalid/unavailable responses return unresolved error/unavailable results.
- Replay invoked the checker before confirming exact reconstruction. Evidence,
  ordered calls and the canonical prompt are now checked first; divergence never
  invokes a checker. Supported permission/file/connection errors can be replayed.
- Benchmark content could differ from the dataset being evaluated. Lock creation
  and evaluation now reject mismatched provider/corpus/source hashes and content.
- CLI lacked feature, experiment, replay, reporting and version entry points and
  integrated only B0/P1 checking. All configurations now use the shared run executor
  and frozen-task path; legacy retrieval commands remain available.
- Input/output aliases could overwrite source files. CLI output paths now reject
  aliases, including symlinks/hard links. Invalid provider origins are rejected
  before configuration locks are written; validation errors hide input values.
- Incomplete/failed observations and empty comparison exports need explicit handling.
  Partial failure traces remain reportable, empty paired CSV exports are valid, and
  CLI run/replay failures return nonzero with structured errors.
- Seeded paired bootstrap/sign-flip inputs now use stable case/group ordering,
  fixing order-dependent statistical results. Fifteen pre-existing formatting failures were resolved. Added regression coverage
  for contracts, source safety, malformed responses, timeouts, replay order, config
  precedence, provenance, all CLI strategies and one-command acceptance.

Legacy retriever/checker names and stage-specific module commands remain for
compatibility; intentional aliases were not replaced with another architecture.
Enterprise stubs remain explicit, with no invented APIs or successful outputs.

## 3. Project structure

```text
src/fcgc/{schemas,core,adapters/retrieval,adapters/checker,experiments,config,fixtures}
benchmarks/v2/{manifest.json,rules.json,ground_truth,REVIEW_GUIDE.md}
skills/fcg_checking/{SKILL.md,prompt.txt}
experiments/                  configuration matrices / evaluation examples
examples/{local.toml,wd.toml}
tests/                       129 passing unit/integration/contract/end-to-end tests
scripts/release_checks.py    offline pattern scan and configuration inventory
release/validation/          saved check outputs, scans, acceptance and CLI receipts
release/evaluation/          JSON / CSV / Markdown / offline HTML release results
docs/                       architecture, operation, integration, security, limitations
dist/                       wheel, source archive and checksums (generated)
wheelhouse/                 23 pinned dependency wheels and checksums (generated)
runs/release-local/          full 120-run audit store, snapshots, tasks and prompts
runs/release-wheel/          independent installed-wheel acceptance store
```

The provider diagram is in [ARCHITECTURE.md](ARCHITECTURE.md).

## 4. Installation and packaging

Executed an editable install and built `fcgc-0.11.0-py3-none-any.whl` and
`fcgc-0.11.0.tar.gz` using installed, pinned build tools without build isolation.
Installed the wheel in `/private/tmp/fcgc-release-verified` using only local wheels and
`--no-index`; diagnostics and the complete 120-run acceptance workflow passed there.
The source archive includes benchmark annotations, tests, fixtures, skills and docs.
Its extracted source was also installed offline and passed all 129 tests independently.
The wheel includes runtime fixtures/configs and canonical shared-data instructions.
Full experiments need the source benchmark layout via explicit `--dataset-root`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m build --no-isolation
```

Offline install commands and transfer checksums are documented in
[LOCAL_SETUP.md](LOCAL_SETUP.md). Version pins are validated on this Python/platform;
WD Linux or other targets require compatible wheels and their own acceptance run.
No WD service is needed for installing or building. No container target was validated.

## 5. Exact working CLI examples

The following commands were executed successfully from the repository root;
[CLI receipts](../release/validation/cli-commands.json) record exit codes and outputs.
Use fresh output directories for acceptance, new experiment locks and replay.

```sh
.venv/bin/fcgc doctor --config examples/local.toml
.venv/bin/fcgc info
.venv/bin/fcgc features --source src/fcgc/fixtures/cases/sensor_poll.c --output runs/features.json
.venv/bin/fcgc extract-rules --document src/fcgc/fixtures/benchmark_guidelines/buffers.md --output runs/rules.json
.venv/bin/fcgc check --case C001 --source src/fcgc/fixtures/benchmark_cases/C001.c --strategy p3 --config examples/local.toml --output runs/C001-p3.json
.venv/bin/fcgc validate-local --dataset-root benchmarks/v2 --output runs/release-local
.venv/bin/fcgc experiment --config experiments/release_development.toml
.venv/bin/fcgc report --config runs/release-local/evaluation.toml
.venv/bin/fcgc replay --run runs/release-local/experiment/runs/C001-p3-r01/trace.json --output runs/release-replay
.venv/bin/fcgc freeze-task --source src/fcgc/fixtures/checking/pointer_bad.c --guideline src/fcgc/fixtures/checking/pointer.md --case pointer-bad --output runs/pointer-task.json
.venv/bin/fcgc check-task --task runs/pointer-task.json --checker-config src/fcgc/config/checker_demo.toml --checker-config src/fcgc/config/checker_mock.toml --output runs/pointer-results.json
```

`check` also accepts B0/P1/P2/R. `--source` selects a C file and `--case` supplies its
identity; `--output` records the full pipeline trace. `--config` selects providers;
optional `FCGC_CONFIG` is overridden by the explicit option. No `.env` auto-loading.

## 6. Test results and commands executed

Final checks are saved in [checks.json](../release/validation/checks.json).

| Check | Actual result |
| --- | --- |
| `.venv/bin/pytest -q` | 129 passed in 4.62s |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check src tests scripts` | 81 files already formatted |
| `.venv/bin/python -m compileall -q src tests scripts` | Exit 0 |
| `.venv/bin/python -m pip check` | No broken requirements |
| `.venv/bin/python scripts/release_checks.py` | No secret-pattern or JSON/TOML syntax findings |
| Import/config validation | 51 modules imported; 8 provider configs and default planner/reducer/fallback configs loaded |
| Known metrics fixture | Retrieval P/R/F2 0.5; violation TP 1, FP 2, FN 1, F1 0.4; attribution 0.5 |
| Dataset validation | 36 rules, 8 documents, 24 cases/annotations; all 24 provisional; passed |
| Editable acceptance | 120 finished, 0 failed; 54 incomplete-context runs; replay exact |
| Installed-wheel acceptance | Same counts, independently run without live retrieval/services |
| Extracted source archive | Offline install succeeded; 129 tests passed independently |
| CLI smoke commands | 10 commands exited 0, including experiment, report and replay |
| Static type checker | Not configured; not run; compile/runtime checks are distinct |

The pytest suite includes unit, integration, end-to-end and adapter contracts in
one run. It covers empty results, duplicate/missing sources, malformed predictions,
unknown citations, ambiguity/exceptions, no evidence, unavailable models, transport
timeouts, bounded fallback, failed/incomplete runs, configuration locks, split
isolation, annotation leakage guards and exact/missing/tampered/divergent replay.

The vulnerability scanner was installed separately in a temporary environment.
`pip-audit 2.10.1 --no-deps --disable-pip -r requirements-runtime.lock --format json`
found no known vulnerabilities in 14 runtime packages; the same command against
`requirements.lock` found none in 23 runtime/development/build packages. This used
public advisories with explicit network authorization and sent package names/versions
only. Saved [runtime](../release/validation/runtime-advisories.json) and
[full](../release/validation/development-advisories.json) reports are not a guarantee
against undisclosed vulnerabilities. No WD network access was attempted.

## 7. Synthetic end-to-end demonstration

One command executed firmware → AST/features → versioned queries → local search/fetch
→ exact-source segmentation → reduction → P3 sufficiency/fallback → context packing
→ checker → structured results/traces/snapshots → independent post-hoc evaluation:

```sh
.venv/bin/fcgc validate-local --dataset-root benchmarks/v2 --output runs/release-local
```

Observed summary (abridged):

```json
{
  "accepted": true,
  "runs": 120,
  "finished": 120,
  "failed": 0,
  "incomplete_context_runs": 54,
  "exact_evidence_replay": true,
  "checker_status_counts": {"not_evaluated": 120},
  "enterprise_verified": false
}
```

The genuine deterministic path separately judged `pointer_good.c` compliant and
`pointer_bad.c` violating for the exact supported SFCG-981 requirement. The latter
cites `fcgc://demo/pointer.md`, source offsets 119–193 and code line 3 (`*out = 7;`).
These were actual source-behavior decisions, not case-ID/label lookups. The checker
abstains on unsupported grammar, additional conditions/exceptions and ambiguity.

The full audit store contains `experiment.toml`, `evaluation.toml`, `acceptance.json`,
`dataset-quality.json`, `deterministic/`, `replay/`, `experiment/lock.json`, ordered
snapshots, per-run traces/tasks/prompts and `evaluation/` reports. Available snapshots
support exact evidence replay; hashes alone are never treated as content.

## 8. B0/P1/P2/P3/R results and interpretation

Actual saved-trace evaluation: 8 development cases, 4 matched groups, 3 repetitions,
same synthetic corpus/provider/scope and mock checker. Document K=3 for B0/P1/P2 and
P3's first pass, R document K=8. Rule K=18 unique canonical IDs, ordered by fetched
source arrival then catalog line and ID. Precision uses actual returned unique
rules up to K. Means average repetitions within case first.

| Strategy | Fetched recall@18 | Precision@18 | Full fetched coverage | Prepared input tokens | Search/fetch calls | Local end-to-end ms |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| B0 | 0.4375 | 0.0833 | 0.4375 | 5717.875 | 1 / 3 | 8.129 |
| P1 | 0.9167 | 0.1632 | 0.9167 | 6644.625 | 1 / 3 | 8.943 |
| P2 | 0.9167 | 0.1632 | 0.9167 | 5534.625 | 1 / 3 | 10.782 |
| P3 | 0.9167 | 0.1389 | 0.9167 | 7513.000 | 3 / 5.375 | 21.159 |
| R | 0.4375 | 0.0556 | 1.0000 | 14136.875 | 1 / 8 | 19.000 |

Tokens are local regex word/punctuation estimates of **prepared prompts**, including
code, instructions, schema and metadata. Oversized/incomplete prompts are kept for
audit and are not evidence of real-model submission. Latencies are measured local
wall time including a mock, not AI/enterprise latency or billing. Timing runs
overlapped other local validation jobs and are not isolated performance measurements. Billed tokens,
model output tokens, ACU and Rovo credits are unavailable, not zero.

- RQ1: P1 mean fetched recall rose by 0.4792 versus B0 on this provisional local
  development set. The four-group bootstrap interval for the paired delta was
  [0.1250, 0.8333]. P1 also increased prompt size in C005–C008; no universal efficiency
  claim follows from improved retrieval here.
- RQ2: P2 reduced mean prepared input by 1110 estimated tokens (16.705% using the
  ratio of configuration means) versus P1. No annotated applicable rule was lost
  during segmentation, reduction or preparation in these traces. Local processing
  latency increased. Mock results cannot prove preserved checking effectiveness.
- RQ3: P3 added two searches and 2.375 fetches on average versus P2, increased mean
  prepared input by 1978.375 tokens and produced no recall improvement. Precision
  regressed in C001–C004. Every P3 run remained `insufficient_evidence`; this is a
  useful negative result for the conservative gate, not a successful recovery claim.
- R fetched every source and attained full untruncated applicable-rule coverage,
  but source order places relevant rules beyond K=18 for some cases. Its low
  Recall@18 is compatible with full fetched coverage. All 24 R prompts exceeded
  the final 12000-token budget and were blocked for substantive checking.

Of 120 runs, incomplete-context counts were B0=0, P1=3, P2=3, P3=24, R=24. No execution
failures were hidden. All benchmark compliance precision/recall/F1 remain null.
Pairwise source/rule stability and per-case regressions are retained in reports.
Only four independent matched groups support inference; intervals/tests are coarse,
exploratory and do not justify enterprise claims. Held-out cases were not calibrated
or evaluated for performance. Dataset quality checked their annotation structure only.

See [release report](../release/evaluation/report.md),
[offline HTML](../release/evaluation/report.html),
[metrics JSON](../release/evaluation/metrics.json),
[summary CSV](../release/evaluation/summary.csv) and [paired CSV](../release/evaluation/paired.csv).

## 9. Supported checker providers

| Provider | Status and supported scope |
| --- | --- |
| Placeholder / mock | Offline contract path; always unresolved / not_evaluated |
| Synthetic deterministic | Real checking of exact SFCG-981 single-pointer-store grammar only |
| Ollama | Implemented opt-in transport/schema adapter; simulated transport tests passed; no executable found and no actual model inference run |
| Devin | Future contract only; not_evaluated, no API assumed |

Skill 1.1.0 and prompt FCGC-PROMPT-V1 are shared across canonical adapters and packaged
with the wheel. Model/settings/version metadata and hashes remain separately logged.
Identical tasks/instructions do not imply equivalent models. Follow
[checking setup](checking.md) to enable a provisioned local Ollama model explicitly.

## 10. MCP/Devin integration readiness

Core interfaces, source/evidence/checking contracts, factories, normalization boundary,
canonical instructions and local contract tests are ready for adapter implementation.
Live tool discovery, authentication, permissions, Confluence normalization and Devin
submission/polling/results are unimplemented and unverified. Managed scores may be
unavailable; extend/version that contract rather than inventing ranking values.
Production snapshots are intentionally blocked pending an approved storage adapter.

## 11. Security and governance status

No secret-pattern findings or malformed JSON/TOML files were found by the saved
bounded repository scan. That is a pattern scan, not exhaustive secret detection.
No runtime firmware execution, default network requirement or paid API is present.
Optional checker networking has explicit opt-in, bounded responses/timeouts and no
redirect/proxy forwarding. Input aliases, provider schemas, citations, provenance,
snapshot integrity and configuration drift are tested. No enterprise credentials
or content were used. Public package advisory queries were separate release checks.

Audit files contain full code/guidelines/prompts and need restricted storage,
retention and sharing. Encryption, user authentication, production approval storage,
secret management and license/governance approval are WD deployment prerequisites.
This checkout has no Git repository/commit identity; code/config hashes identify
the local release. Hashes are not signatures. See [SECURITY.md](SECURITY.md).

## 12. Known limitations and unfinished items

Completed: executable offline pipeline, validated contracts, synthetic benchmark,
mock and bounded genuine checking, all strategy experiments, replay/evaluation,
packaging and local validation/docs.

Pending enterprise verification: real MCP/Devin adapters, approved credentials and
permissions, Confluence provenance fidelity, true-model accuracy, real cost/latency,
production snapshot governance and independent reviewed enterprise labels.

Optional enhancements: static type checking, a multi-Python/platform CI matrix,
verified Linux container, signed release provenance, richer C/program analysis,
more robust enterprise normalization, cancellable transports and broader genuine
checking. These are not disguised as completed Stage 1–10 functionality.

The existing deterministic heuristics and soft synchronous P3 deadline have known
bounds. All current labels are provisional. No local LLM was installed or inferred.
Full details are in [LIMITATIONS.md](LIMITATIONS.md).

## 13. WD-server deployment checklist

- [ ] Approve target runtime, dependency/repository licenses and target wheelhouse.
- [ ] Verify package/checksums and rerun local tests/acceptance on the WD server.
- [ ] Discover approved MCP/Devin contracts; implement adapters without guessed APIs.
- [ ] Configure least-privilege credentials and approved egress/TLS/proxy policy.
- [ ] Validate scope, page versions, source normalization and exact provenance.
- [ ] Test live success, errors, timeouts, retries/cancellation and session isolation.
- [ ] Approve encrypted/access-controlled snapshot storage, retention and deletion.
- [ ] Independently review applicability/violation labels; preserve split isolation.
- [ ] Calibrate on development only, freeze controls/margins, then run held-out tests.
- [ ] Measure actual provider quality, variability, token/cost metrics and latency.
- [ ] Complete security/firmware/research review and a supervised enterprise pilot.

## 14. Final acceptance status

**PASS for the fully working local synthetic research prototype.** The final test
suite passed, all five configurations executed, the installed wheel passed complete
offline acceptance, available snapshots replayed, real bounded checking was
demonstrated, and saved traces generated complete evaluation reports. Incomplete
context and mock abstention remain explicit; no enterprise/model accuracy is claimed.

**PENDING for live WD deployment and validated enterprise effectiveness.** The
integration, governance and independent-review checklist above must be completed.
