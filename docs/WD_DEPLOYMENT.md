# Deploying with WD's existing Devin/Atlassian connection

For the distinction between the full research repository and a later streamlined
runtime workspace, see [enterprise file scope](ENTERPRISE_FILE_SCOPE.md).

The preferred path uses the authorized active WD Devin agent as the MCP client.
Do **not** install a second MCP server, create duplicate OAuth credentials or assume
that the local Python process shares a Cloud connection. Existing permissions and
the host's actual tool schemas remain authoritative.

1. Transfer the repository/source archive and approved target-specific dependency
   wheelhouse into WD's approved workspace. Preserve `.agents/skills`, `skills/`,
   `src/` and benchmark layout. Install with the existing offline setup instructions.
   Do not transfer production guidelines out to a local development machine.
2. Run the local suite and synthetic acceptance first. These require no enterprise
   credentials and do not establish enterprise effectiveness. The current pinned
   development environment was validated on CPython 3.13/macOS arm64; validate WD's
   target OS/Python and dependency licenses separately.
3. In the installed Devin environment, inspect `devin skills paths` and
   `devin skills list --trigger user` where that CLI is available. Check all five
   project skills; inspect `devin skills show fcg-check`. For a Cloud/Desktop surface,
   verify its own repository-skill discovery and invocation UI. Do not copy a second
   competing skill tree just to hide a discovery problem.
4. Start `/fcg-doctor` in **that same active WD session**. The agent should inspect
   already-exposed Atlassian/Confluence tools and documented input schemas, not guess
   names or dump credentials. Discovery/configuration alone remains
   connected_but_unverified. Verify a small authorized read-only search and fetch
   there before marking access live-tested in a deployment record.
5. Approve an audit directory, retention/access policy and exact source scope. The
   skill supplies a nonsecret HostContext and uses `config/wd_agent.toml` or the
   equivalent WD default. There are no WD URLs or authentication secrets in that
   file. The older `config/wd.example.toml` is the unimplemented direct API contract, not
   the recommended native handoff profile.
6. Run `/fcg-rules <approved-file.c> --mode wd` first. Inspect original requirements,
   paragraph context, conditions, exceptions, dependencies, versions and source
   provenance. Only tool-provided Markdown/plain text is supported without another
   approved converter. Do not silently paraphrase Confluence storage/ADF/HTML.
7. Run `/fcg-check <approved-file.c> --mode wd`. The active agent follows typed pending
   actions and the canonical checking prompt, then submits structured findings for
   validation. Report unresolved/incomplete contexts explicitly. Never assign
   unsupported WD severity. Keep model/settings and exposed accounting distinct
   from estimates; do not claim equivalent model behavior from a shared skill.
8. Pilot with reviewed examples and failure cases: missing access, empty/partial
   searches, changed pages, unsupported content, missing dependencies, timeouts,
   duplicate-only fallback and context budgets. Review saved receipts, query versions,
   source references, checker hashes, warnings and resource limits.

## Current status and deployment gates

**Implemented and locally tested:** all five backend workflows, project skill
frontmatter/files, fixture/replay operation, existing B0/P1/P2/P3 experiments and
reports, typed search/fetch/checker handoff, source-backed processing, bounded P3
continuation and error/security controls.

**Implemented but not live-verified:** native skill discovery/invocation in Devin,
agent-mediated production MCP ingestion and active-Devin checking. Python cannot
independently authenticate host receipts; record successful actual host call IDs
and approval evidence when available.

**Blocked by enterprise access here:** WD tool visibility, authenticated search/fetch,
actual Confluence format fidelity, live model behavior, permission enforcement and
real platform accounting. No authorized live call occurred in the local session.

**Not implemented:** direct Devin API transport, arbitrary ADF/HTML/storage conversion,
production snapshot governance/storage, live enterprise experiment matrices and
enterprise ground-truth dataset adaptation. `/fcg-compare --mode wd` fails closed
until those experiment/governance inputs exist; it never reports synthetic recall
as enterprise recall. Individual bounded WD checks are available through the bridge.

Before research deployment, obtain independent applicability/violation annotation
review, separate development/held-out sets, calibrate on development only and freeze
controls/margins before held-out evaluation. Approve egress/model choices, credentials
outside source control, encrypted/access-controlled audit storage and deletion.
The more detailed [WD integration checklist](WD_INTEGRATION.md) remains applicable;
its direct-adapter discussion is an optional future path, not a requirement to
duplicate the existing MCP connection.
