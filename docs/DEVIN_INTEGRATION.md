# Devin-native integration and MCP bridge

## Verified conventions and actual local availability

Official [Devin CLI skills](https://docs.devin.ai/cli/extensibility/skills/overview)
document `.agents/skills/<name>/SKILL.md`, slash invocation and project discovery.
The [frontmatter reference](https://docs.devin.ai/cli/extensibility/skills/creating-skills)
documents `name`, `description`, `argument-hint` and `triggers`. These five skills
use only those fields, with user/model triggers and no permission grants. Their
JSON-quoted values/lists are valid YAML. There is no duplicate `.devin/skills` tree.
The [CLI reference](https://docs.devin.ai/cli/reference/commands) documents
`devin skills paths`, `devin skills list --trigger user`, and `devin skills show NAME`.

This enhancement was built in **Codex Desktop**, not an active Devin session.
No `devin` executable or Atlassian/Confluence tool was exposed to the active agent.
Thus native registration, an actual slash invocation and authenticated live WD calls
are unverified. WD's reported Cloud connection does not prove access from another
CLI/Desktop installation. No Devin installation, OAuth login or server configuration
was attempted. Other host surfaces must verify their own discovery/invocation
conventions; CLI documentation is not a claim that every Cloud UI shares them.

## Layering

```mermaid
sequenceDiagram
    participant U as Engineer
    participant D as Devin skill / existing MCP access
    participant B as FCGC agent bridge
    participant C as Existing core strategies
    U->>D: /fcg-check file.c --mode wd
    D->>B: invoke + observed HostContext
    B->>C: existing feature / query / strategy executor
    C-->>B: search/fetch boundary
    B-->>D: typed AgentAction
    D->>D: invoke actual authorized MCP tool
    D->>B: AgentToolResult JSON
    B->>C: validated response; segment/reduce/assess
    Note over B,C: Repeat bounded actions for P3 only
    B-->>D: frozen canonical checker task/prompt
    D->>B: AgentJudgment with hashes and cited findings
    B->>B: existing schema/citation validation
    B-->>D: structured result, report, trace
    D-->>U: source-backed findings and limitations
```

No MCP SDK/server or direct Devin API was added. `AgentMCPRetriever` implements the
existing search/fetch boundary using captured host receipts. When a response is
missing, it yields `AgentRetrievalRequired`, a control-flow suspension outside
ordinary provider error handlers. Resumption re-executes the **same existing** core
strategy over receipts until the next boundary; there is no second planner, reducer
or fallback algorithm. B0/P1/P2/P3 definitions and local experiment semantics remain.

This deterministic resumption incurs extra CPU work. Core trace durations describe
the final receipt-replay pass, not managed MCP latency. Sessions separately record
cumulative backend processing, overall wall time (including agent/human waits),
host-reported tool durations when available and call counts. Unknown billing,
model/output token counts and proprietary credits remain null. Fixture tests are
labeled `synthetic_contract_test`; they are never actual MCP traffic.

## Handoff protocol v1

Run `fcgc agent schemas` for generated, canonical Pydantic schemas. Inputs reject
extra fields, duplicate JSON keys, malformed payloads and oversized content. Files
use the simplest supported integration: bounded UTF-8 JSON on the approved host
filesystem. No socket, external upload or independently authenticated client is
needed. The Python core never discovers/invokes a tool behind the agent's back.

`HostContext` records runtime/version when exposed, a nonsecret host-session
identity, existing provider, scope label, approved workspace, **actual discovered**
search/fetch tool names and their input-schema hashes. No tool names are assumed.
No credentials/headers/cookies are accepted as schema fields. Host configuration
stays connected_but_unverified; Python cannot authenticate an external receipt.

`AgentAction` contains session/action/context identifiers, operation and either a
`RetrievalQuery` (exact text, document K, template version, search number) or an
actual ranked source reference. A checker action contains frozen evidence/prompt
hashes. Scope/permissions stay locked in `session.json`; the host must apply the
configured source filter using actual supported tool inputs. Empty filter objects
are not proof of enterprise permission breadth.

`AgentToolResult` includes actual tool/provider identity, available call ID,
timezone-aware retrieval time, optional duration, completeness, metadata and exactly
one `SearchResults`, `FetchedDocument` or sanitized typed error. Search hit list
position is rank. Unavailable managed scores are null; optional fractional scores
can be retained as metadata and are never inferred confidence values.

Fetched content must be actual tool-provided Markdown/plain text, preserved exactly
with source URI/ID/title and available version. The normalizer/segmenter retains
original character spans. Arbitrary Confluence storage/ADF/HTML conversion is not
implemented. If no approved converter can preserve provenance, report unsupported
content rather than rewriting it. An optional upstream-response hash identifies a
known captured response; a hash alone does not reconstruct or authenticate content.

The host executes each pending action, writes its faithful result, and calls:

```sh
fcgc agent submit --session <audit-directory> --response <actual-tool-result.json>
```

The backend validates query, rank cardinality/duplicates, scope, source identity,
timestamp, environment/context hash, provider/tool match and candidate budgets.
Fetches must match their selected search reference. Host-observed WD references
must be HTTPS without embedded credentials. Synthetic handoff tests require an
explicit test opt-in and cannot masquerade as live verification. WD source and
audit paths must remain inside the host-attested approved workspace.

P3 can issue additional targeted queries through this same loop; P2 cannot. Global
deadline and search/fetch/candidate limits bound external actions. Default transport
retries are zero. Authentication/permission failures stop instead of creating new
authentication or substituting rules. Timeout/unavailable results are recorded and
may trigger the existing P3 fallback, with the physical actions still bounded.

## Checker handoff

The existing Devin API contract stays unimplemented. `DevinAgentChecker` instead
accepts a judgment from the active authorized agent. It is an input-validation
adapter, not an API transport or independent proof that a model actually ran.
The host reads `checker-prompt.json` and `task.json`, using the exact shared
canonical interpretation skill/prompt. A function focus adds original target
coordinates and a scope warning to the task; the full code remains available.

Submit `AgentJudgment` with matching session/action/context, evidence and prompt
hashes; optional actually exposed model/settings/tokens; and `ModelFindings`.
The existing canonical checker validates all rule IDs, applicability/status
consistency, normative citations, conditions/ambiguity, code excerpts and target
locations. Incomplete evidence blocks substantive agent checking. A mock never
turns into a compliant prediction. Configured generation settings are **requested**
settings; actual host-reported settings remain separately optional in execution
details. Shared instructions do not guarantee equivalent reasoning or model state.

An inline agent may retain prior conversation state; Python cannot guarantee a fresh
Devin checker session or erase previously viewed labels. Use clean host/model contexts
for future research runs and record unavailable isolation controls. The existing
local experiment runner still creates fresh adapter/task instances. Inline WD
checks are not an implemented enterprise accuracy-comparison workflow.

## Integrity and confidentiality boundaries

Sessions lock code/config, canonical instructions, orchestration skill hash, original
code hash, target, host and limits. Resume rejects code/instruction/receipt drift.
Audit files use restrictive modes and atomic writes; output symlinks are rejected.
Agent inputs are limited to 2 MB JSON, 1 MB per source document/artifact, bounded
references and a maximum one-hour workflow. Existing core CLI limits remain unchanged.

These are local consistency controls, not signatures, a secure enclave or proof of
WD authentication. The host and filesystem are trusted. Captures include firmware,
guideline text, prompts and receipts; WD must approve storage/retention/access and
ensure all files stay on approved infrastructure. Do not upload them to this local
development environment. Remote checker export requires a future approved adapter.
