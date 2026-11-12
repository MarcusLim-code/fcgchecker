# Security and governance

Native skills add no auto-approved tools or permission overrides. The agent bridge
validates bounded JSON, query/source/scope identity, host/session hashes, receipts
and canonical findings. WD source and output stay inside the host-attested approved
workspace; explicit WD mode rejects fixture substitution and remote checker export.
Firmware remains read-only. Tool errors omit credentials; audit files use restrictive
modes and atomic writes. Host attestations are not signatures or independent proof
of authentication. See [DEVIN_INTEGRATION.md](DEVIN_INTEGRATION.md) for trust boundaries.

Local fixtures, mock checking and the bounded deterministic checker make no network
requests. C firmware is parsed as text and is never compiled or executed. No shell
commands are generated from firmware, queries or model output. No credentials are
needed for local operation. `.env` and private environment files are ignored;
`.env.example` contains only an optional nonsecret config path. Files ending in
`.private.toml`, `.private.json`, `.local.toml` and `.local.json` are ignored and
excluded from source/wheel packaging. Build from a fresh source extraction using
`scripts/build_release.py`; inspect artifacts before transfer. Arbitrarily named
secret files are not automatically identified.

Transport diagnostics and source URLs reject recognized credential assignments,
URL user information, and sensitive query/fragment keys in several naming styles.
Validation errors omit rejected input values. These are bounded pattern checks,
not a general redaction system; host tools must sanitize errors and never include
credentials. Authoritative guideline text is never silently rewritten by them.

Local source input is bounded to 8 MB, decoded strictly as UTF-8, rejects empty/NUL
content and preserves newlines for provenance. Output options reject input aliases.
Benchmark fixture paths are constrained to their public fixture directories.
Scope filters apply to local search and fetch. Provider contracts reject unexpected
fields and revalidate model instances. Citation validation rejects invented source
or code excerpts. These controls do not establish program correctness.

The optional Ollama adapter requires explicit network opt-in, including loopback.
Remote origins and advertised remote-backed models require a second opt-in.
Credentials in endpoint URLs, path/query/fragment URLs, redirects and environment
HTTP proxies are rejected/disabled. Requests have timeouts and an 8 MB response cap.
Consumed provider metadata and token counters are validated. A failed or rejected
generation yields unavailable/error with unresolved findings. Untrusted guideline
content must be treated as evidence, never as instructions overriding the canonical
skill; prompt/schema/citation checks mitigate but cannot prove resistance to model
prompt injection. Only use approved local models with sensitive code.

Audit records and snapshots contain complete firmware, source documents, prompts
and findings. They are intentionally content-bearing for reproducibility, with no
automatic redaction/encryption or access-control service. Restrict file permissions,
storage, retention and sharing. Do not put credentials or production material in
fixtures. The experiment runner permits approved synthetic snapshots only; future
production capture needs explicit governance implementation.

Replay validates approved snapshot hashes, ordered calls, code/instruction locks
and reconstructed task before invoking a configured checker. It never calls a live
retriever. It may invoke the originally configured network checker after validation;
use offline configs or `check-task` to choose a different checker. Hashes detect
accidental drift/tampering but are not signatures or a trusted approval authority.

`scripts/release_checks.py` scans repository text for selected credential/private-key
patterns and validates JSON/TOML syntax. It excludes generated outputs/environments
and is not exhaustive secret detection. Use a current advisory scanner and approved
dependency/license review before deployment. Version pins/checksums support
reproducible transfers; they do not establish package trust. See the release report
for actual scan results and checks that were unavailable.

Ground-truth files are kept outside runtime inputs and guarded by tests. Held-out
annotations may be structurally validated but are not calibration inputs. Current
labels are provisional; independent review and controlled enterprise evaluation are
still required. This checkout has no configured Git history or signed release
provenance; code/config fingerprints and artifact checksums provide local audit
identity only.
