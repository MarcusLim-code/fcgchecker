# Enterprise file scope

This guide answers which FCGC files are unnecessary after integration with the WD enterprise environment. **Not needed in the daily runtime** does not mean safe to delete from the source repository or research archive. Final deployment scope depends on WD approvals for permissions, audit storage, and operations. Live Atlassian MCP and Devin integration have not yet been verified.

## Choose the delivery format first

| Delivery format | File scope |
| --- | --- |
| Source workspace for Devin | Keep `.agents/skills/`, `skills/`, `src/`, the selected `config/` profile, and required dependencies. The current [deployment procedure](WD_DEPLOYMENT.md) also calls for preserving the benchmark layout during initial transfer so offline tests and synthetic acceptance can run. Create a smaller daily workspace only after that validation and an approved packaging review. |
| Built Python wheel | Install the complete, verified wheel. It includes some synthetic fixtures and compatibility modules. A file that is unused during daily checks must not be removed manually from the wheel. A smaller wheel requires a separate reproducible build and acceptance run. Native Devin skills must still be placed where the host can discover them. |
| Research workspace | Retain the versioned benchmark, independent ground truth, experiment configurations, and auditable outputs, under separate access controls. |

## Usually unnecessary in a daily checking workspace

| Path | Purpose | Recommendation |
| --- | --- | --- |
| `examples/` | Introductory firmware and synthetic guideline examples | Omit from daily deployment; keep in the repository. |
| `tests/` | Unit, integration, end-to-end tests, and metric fixtures | Run in CI or predeployment validation; omit from the long-lived checking workspace. |
| `benchmarks/v2/` | Synthetic benchmark, rule catalog, independent annotations, and historical reports | Daily WD checking does not need it. In particular, `ground_truth/` must not be available as an input to the prediction workflow. Authorize research use separately. |
| `research/experiments/` | B0/P1/P2/P3 experiment and calibration definitions | Unnecessary for daily single-file checks; retain for controlled research. |
| `release/` and historical `runs/` | Existing release evidence, snapshots, and results | Manage as archives under retention policy, not application code. Exact replay of a historical run may still require its snapshot and original code version. |
| `outputs/` | Newly generated checks, logs, and reports | Do not distribute with the software. Configure an approved enterprise output location, access controls, and retention period. |
| `build/`, `dist/`, `*.egg-info/`, `__pycache__/` | Build and cache products | Not required in a source runtime workspace. Deploy a verified wheel instead. |
| `scripts/` and most `docs/` | Build helpers and documentation | Not required for execution alone. Keep the installation, integration, and operating guides available to the deployment team. |

## Keep or provide for the selected workflow

- `src/fcgc/checking/`, `retrieval/`, `schemas/`, `core/`, and `agent/` provide checking, retrieval, contracts, and host handoff. Parts of `src/fcgc/experiments/` may be used by CLI, acceptance, or reporting paths. Do not remove package directories without dependency analysis and a fresh test run.
- `src/fcgc/config/` contains versioned concept mappings, query templates, and budget policies. Root `config/wd_agent.toml` is the existing host-handoff example. `config/wd.example.toml` describes an unimplemented direct API contract; it is not an active WD credential profile.
- `.agents/skills/`, `skills/fcg_checking/`, and `skills/fcg_orchestration/` provide native `/fcg-*` commands, canonical checking instructions, and the agent workflow. Confirm discovery and placement in the actual Devin host.
- `src/fcgc/integrations/` contains checker interfaces and providers. `mock_checker.py` returns `not_evaluated`; it cannot establish real compliance.
- `src/fcgc/retrieval/mcp_bridge.py` and related host-session code support handoff through an existing MCP connection. Discover and verify actual tools, permissions, and response formats in WD.

The local and replay retrievers, synthetic checker, packaged `fixtures/`, and legacy import shims may not run during daily enterprise checks. They still support offline tests, regression checks, replay, or existing imports. **Keep the present distribution intact.** If a smaller distribution is needed, review imports and package data, build a new version, then rerun tests, offline acceptance, and WD contract checks.

## Data and research boundaries

Synthetic guidelines are not official WD requirements. Enterprise checks must use only approved real guideline sources and retain original text, source ID, version, permission scope, and citations. Enterprise annotations require independent review. Calibrate on the development set only, then freeze settings before evaluating a held-out set. Do not copy real firmware, guidelines, credentials, or check outputs into public synthetic benchmarks or local examples.

## Before reducing the deployment footprint

1. Decide whether the deliverable is a source workspace, complete wheel, or separate research workspace.
2. On the target WD platform, complete offline installation, tests, and synthetic acceptance before verifying native skill discovery, authorized search/fetch, and checking results.
3. Determine actual call paths and file dependencies. Build a new distribution for any reduced footprint; do not hand-edit the verified wheel.
4. Isolate benchmark ground truth from prediction runs. Approve storage, access, and retention for logs, snapshots, and outputs.
5. Preserve the original distribution, version, checksums, and replay snapshots for audit and rollback.

Related guides: [directory guide](DIRECTORY_GUIDE.md), [WD deployment](WD_DEPLOYMENT.md), and [security](SECURITY.md).
