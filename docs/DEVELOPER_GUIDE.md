# Developer guide

Read [START_HERE](../START_HERE.md), then use the [directory map](DIRECTORY_GUIDE.md)
to find the implementation. Do not start by tracing every legacy import.

## Local development loop

Install with [Local setup](LOCAL_SETUP.md). Run from the source root:

```sh
.venv/bin/pytest -q
.venv/bin/pytest -q tests/unit
.venv/bin/pytest -q tests/integration
.venv/bin/pytest -q tests/end_to_end
.venv/bin/ruff check .
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

Ruff explicitly excludes generated output/archive/build trees, including in a
source checkout without Git metadata. Application code and tests remain checked.

There is no configured static type checker or CI workflow in this checkout. Python
3.11+ syntax is supported; the local runtime/wheelhouse was tested on macOS arm64 /
Python 3.13. Validate other platform wheels on their target, not by assumption.

## Follow one check

1. `.agents/skills/fcg-check/SKILL.md` tells the host how to accept the request.
2. `agent/commands.py` parses arguments; `agent/session.py` locks input/provider choices.
3. The shared executor in `experiments/runner.py` selects the unchanged strategy.
4. `retrieval/` supplies source documents; `checking/` extracts and packs evidence.
5. `checking/compliance_checker.py` freezes and validates the canonical task/result.
6. A checker in `integrations/` receives that task; the session saves a readable report.

`cli.py` exposes the same workflows for automation. Do not implement a second
query planner, rule interpreter or experiment runner inside a skill.

## Imports and compatibility

Use `fcgc.checking`, `fcgc.retrieval`, `fcgc.integrations` in new code. For example:

```python
from fcgc.checking.feature_extractor import extract_features
from fcgc.retrieval.query_planner import FCGQueryPlanner
from fcgc.integrations.mock_checker import MockChecker
```

Old `fcgc.core.*` and `fcgc.adapters.*` paths for moved modules remain thin module
aliases. They point to the same module object, so old imports and monkeypatches
still affect the real implementation. They contain no copied algorithms. Keep
shared file/safety utilities and protocols under `core/` until a functional reason
justifies moving them. Canonical Pydantic class names, schema identifiers, rule IDs
and public function names did not change. See the complete [change map](RESTRUCTURING_CHANGELOG.md).

Changing file layout changes the source fingerprint. Never bypass replay's hash
checks to make an old trace look compatible. Keep snapshots plus their original
release archive for exact historical replay. New runs/replays use the new release.
Saved frozen checker tasks can still be validated and checked through `check-task`.

## Configuration without code edits

- Root `config/local.toml`: default onboarding profile, offline benchmark + mock.
- Root `config/wd_agent.toml`: host-mediated existing MCP/Devin workflow.
- Root `config/wd.example.toml`: explicit unimplemented direct API contract.
- `src/fcgc/config/`: installed internal defaults, versioned mappings and templates.
- `research/experiments/`: common provider/budget/repetition controls for comparisons.

Provider profiles are loaded by `fcgc.config`; explicit CLI `--config` takes
precedence over optional `FCGC_CONFIG`. `.env` is not automatically loaded.
Experiment/evaluation relative paths are relative to the TOML file. Standalone
source/output paths are relative to the caller's working directory. Keep secrets
outside example profiles, using approved host configuration; private/local config
suffixes are ignored and excluded from clean packages.

## Adding capabilities safely

A retriever implements typed `search(query, top_k)` and `fetch(source_id)`. Preserve
returned order, source identity, versions and verbatim content. Test empty results,
scope, duplicate/invalid responses and failures. Local ranking is not managed
Atlassian ranking. A checker reuses the canonical skill/prompt and citation validator;
unsupported/uncertain cases abstain. The mock must stay not_evaluated.

Rule extraction/reduction changes need tests for conditions, exceptions, dependencies,
quantitative limits and source spans. Retain larger uncertain sections rather than
inventing unconditional rules. No checker result may influence retrieval. Runtime
components must never load ground-truth labels; evaluation is a separate step.

## Builds and maintained resources

```sh
.venv/bin/python scripts/build_release.py --output outputs/packages/development-build
.venv/bin/python scripts/release_checks.py
```

Use a fresh output directory. The helper builds a wheel from an extracted source
archive and excludes private configs and generated `outputs/`. Update `MANIFEST.in`
when adding maintained top-level resources. Package runtime fixtures/defaults via
`pyproject.toml`; native skills and canonical instructions also have installed
fallback locations. Test from an installed wheel outside the checkout.

Do not remove historic reports, fixtures or compatibility imports as a cosmetic
cleanup. Establish consumers first. Current cleanup candidates are documented in
the change map; the [security guide](SECURITY.md) defines data-handling limitations.
