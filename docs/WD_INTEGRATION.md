# Future WD integration

The native agent-mediated path is now implemented and contract-tested without live
WD access. Prefer [WD_DEPLOYMENT.md](WD_DEPLOYMENT.md) and
[DEVIN_INTEGRATION.md](DEVIN_INTEGRATION.md) when WD's Devin already has Atlassian
MCP access. No duplicate server/authentication client is needed. The direct-adapter
discussion below remains a future option; the original direct API stubs remain
explicitly unimplemented. Live access is still unverified.

**Live Atlassian MCP and Devin have not been tested.** The supplied
`config/wd.example.toml` selects contracts, not working network implementations.
`AtlassianMCPRetriever.search/fetch` raise `NotImplementedError`. `DevinChecker`
returns unresolved findings and `not_evaluated`. No WD URLs, MCP tool names,
authentication mechanism or Devin API are guessed.

## Adapter implementation boundary

Discover WD-approved services and capabilities in the target environment. Implement
the existing `FCGRetriever` and `ComplianceChecker` interfaces; preserve core
workflow and typed contracts. Search returns ranked source references in provider
order. Fetch must return actual authorized content, source identity/version and
stable references. Do not manufacture scores when managed rankings expose none;
the shared `score` field now accepts null when unavailable. Integer lexical scores
remain local-only; provider-specific fractional scores can be retained in bridge metadata. Core consumers
use returned order, not hidden score thresholds.

Convert Confluence storage/ADF/HTML to a canonical document with provenance mapping
through `DocumentNormalizer`; the existing Markdown normalizer cannot assert
fidelity to unknown enterprise response formats. Retain page versions, links,
permissions, content hashes and exact source spans or equivalent mapping. Validate
search/fetch identities and source scope at the adapter boundary. Exercise schema
contract tests with approved captured examples before live integration tests.

Implement Devin submission, task/session identity, polling/cancellation, timeout,
failure/retry semantics and structured result validation only from approved API
documentation. Render the same canonical skill/prompt and reject unknown IDs or
unsupported citations. Record exact exposed model/version/settings and usage.
Shared instructions do not make different model implementations equivalent.

The experiment runner currently rejects production-source snapshot capture.
Before enterprise runs, add an approved storage/retention/access-control adapter
and explicit permission-aware capture policy. Do not bypass this guard merely to
enable a demonstration. Synthetic snapshot approval does not authorize WD content.

## WD-server deployment checklist

- [ ] Approve repository/dependency licenses, target OS/Python and isolated runtime.
- [ ] Build and verify target-specific dependency wheels and release checksums.
- [ ] Run local tests and acceptance entirely without WD services first.
- [ ] Discover approved MCP/Devin endpoints, actual contracts and permissions.
- [ ] Implement secret injection outside versioned files and least-privilege access.
- [ ] Validate scope enforcement, document versions, normalization and citations.
- [ ] Add real adapter contract/integration tests with authorized data and failures.
- [ ] Approve egress, TLS/proxy settings, credentials, timeout/retry/cancellation policy.
- [ ] Approve audit snapshot locations, encryption, retention, redaction and deletion.
- [ ] Create independent enterprise ground truth with reviewer sign-off.
- [ ] Calibrate only on development; freeze controls before isolated held-out runs.
- [ ] Measure real ranking variability, checking quality, latency and exposed costs.
- [ ] Run a small supervised pilot and obtain firmware/security/research acceptance.

Network reachability, credentials, live permissions, enterprise ranking behavior,
Devin correctness and proprietary billing remain pending verification.
