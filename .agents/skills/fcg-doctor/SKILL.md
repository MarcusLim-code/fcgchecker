---
name: "fcg-doctor"
description: "Check FCGC package, dataset, native skill files, local providers and host-reported Devin/MCP readiness without changing authentication or source files."
argument-hint: "[--dataset-root PATH] [--mode local|wd]"
triggers: ["user", "model"]
---

# fcg-doctor

Explain what is ready locally and what the active host can actually expose.

## Usage

`/fcg-doctor`

No argument is required. Optional: `--dataset-root PATH` (default benchmarks/v2)
and `--mode local|wd` (default local). Installed-wheel users can provide the
benchmark root from the extracted source archive. Do not request credentials.

Output: structured version/provider/dataset/skill diagnostics in a fresh
`outputs/checks/` directory and a concise readiness explanation. Common issues:
missing benchmark files, uninstalled dependencies, unavailable Devin executable
or tools, and unverified host access. Native skill files alone do not establish
native discovery or authenticated MCP access. No compliance check is run.

## Execute the request

Execute `fcgc agent invoke --command '<the /fcg-doctor invocation>'
--output <fresh-diagnostic-directory>`. If actual authorized Atlassian tools are
visible in this host, read `skills/fcg_orchestration/WORKFLOW.md` and supply only
nonsecret observed HostContext fields with --host. Otherwise omit --host and state
that this session cannot see those tools. Never invent tool names or access.

The backend validates installed versions, local search/fetch, structural dataset
quality and the five skill frontmatters. It probes Devin skill discovery only if
an executable exists. Do not install/login to Devin, run independent OAuth, create
MCP servers or dump configuration/headers/tokens as a diagnostic shortcut.

Present ready, not_configured, connected_but_unverified, unavailable and error
statuses distinctly. Skill files on disk are not proof of native registration;
configured/visible tools are not proof of authenticated access. Identify the
runtime/surface where actually known, permission limitations and executable
workflows. No real slash-command or live WD test may be claimed from fixture tests.
No compliance checking is performed. Record diagnostics under the selected audit
path and keep firmware and enterprise knowledge sources read-only.
