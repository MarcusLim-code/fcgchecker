# Known limitations and unfinished work

## Verified local scope

The executable path uses synthetic fixtures, lexical retrieval, source-backed
segmentation, deterministic planning/reduction/fallback, canonical checking and
post-hoc evaluation. Unit/contract/end-to-end tests validate behavior and failures.
The local retriever is a reproducible test backend, not Atlassian semantic retrieval.
Synthetic results cannot establish WD retrieval accuracy, enterprise latency,
Devin performance or proprietary cost savings.

## Analysis and evidence

Tree-sitter provides syntax observations with bounded lexical fallback. Categories,
return-check associations and component hints are heuristics. There is no complete
preprocessing, alias analysis, interprocedural data flow, path feasibility or proof
of firmware behavior. Macro/indirect-call ambiguity is explicit. Markdown
segmentation is conservative and cannot infer every narrative dependency or distant
exception. Complex tables and enterprise document formats need adapter-specific
normalization and human review. ID-less evidence is auditable but is not scored as
an invented canonical benchmark rule.

Reduction preserves uncertain/contextual evidence and may exceed a budget. The
sufficiency gate is risk detection, not completeness certification. Conditions and
exceptions often remain unresolved and can trigger extra retrieval with no recall
gain. P3 time limits are soft checks between synchronous calls; they cannot cancel
an in-flight provider. Local source limits do not bound AST complexity or total
trace size. Run untrusted artifacts under an OS/resource-isolated environment.

## Checkers and experimental inference

Mocks and placeholders do not evaluate compliance. The deterministic checker only
supports one exact synthetic pointer rule and a narrow C grammar; it abstains
elsewhere. Ollama transport is implemented and tested with simulated responses,
but real local-model inference is not verified in this environment. Direct Devin/MCP APIs remain contracts. An agent-mediated native handoff is now
implemented and contract-tested, but no native registration or live WD call was verified. Citation validation cannot prove semantic model judgments.

All 24 annotations remain provisional. Development has only 8 cases in 4 matched
groups, limiting statistical power and representativeness. Repetitions are not
independent cases. Current benchmark runs use a mock, so downstream accuracy and
effectiveness preservation are unavailable. R is a broad lexical reference with
a larger budget, not an exhaustive oracle. No held-out calibration or enterprise
performance claim is justified. Exact replay requires snapshots and compatible
code/instructions; model outputs/timings may differ. Archived traces can still be
evaluated without replay, but source/corpus drift is rejected.

Token counts are a named local word/punctuation approximation, not model-specific
tokenization or billing. Provider counters are recorded only when exposed. Output
tokens, ACU, Rovo credits and billed cost are unavailable rather than zero. Some P3
stage times cannot be isolated from the current nested trace; those stay null.

## Deployment and optional enhancements

The tested pinned wheelhouse targets CPython 3.13/macOS arm64. Python 3.11+ is the
declared runtime contract, but a multi-platform/version CI matrix, static type
checker, signed supply-chain provenance, production audit storage, Linux container,
authentication, telemetry export and automatic retry/cancellation are optional
future work. No static type checker is currently configured. The wheel bundles
runtime fixtures; full benchmark experiments additionally need the source archive
with its benchmark/fixture layout. No production service is required for local
builds. WD prerequisites are listed in [WD integration](WD_INTEGRATION.md).
