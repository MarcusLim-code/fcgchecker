# Start here

**FCGC finds coding guidelines relevant to C firmware and prepares source-backed checks.**
Firmware engineers use it to inspect rules and findings. Developers maintain the
analysis and integrations. Researchers compare retrieval strategies and costs.
The included firmware, guidelines and benchmark are synthetic, not WD requirements.

## Try it

In a supported Devin session with this project installed:

```text
/fcg-doctor
/fcg-rules examples/firmware/sensor_start.c
/fcg-check examples/firmware/sensor_start.c
/fcg-compare --case C001 --repeat 3
/fcg-report --experiment latest
```

All five command backends are implemented and tested offline. Native Devin command
recognition and live WD access need verification in the target environment. Local
checking defaults to a mock and returns **not_evaluated**, never a guessed verdict.
The agent runs the backend for you; engineers do not need Python module names.

For a local terminal setup, follow [Local setup](docs/LOCAL_SETUP.md). Then try:

```sh
.venv/bin/fcgc agent invoke --command '/fcg-check examples/firmware/sensor_start.c' --output outputs/checks/first-check
```

Use a fresh output directory. Open the resulting `report.md`; inspect uncertainty
and source citations alongside any findings. Optional real checking is described
in [the user guide](docs/USER_GUIDE.md).

## Find your way

| I want to… | Go to… |
| --- | --- |
| Understand the project and install it | [README](README.md) |
| Check firmware or inspect its rules | `/fcg-check` or `/fcg-rules`; [user guide](docs/USER_GUIDE.md) |
| Change firmware analysis, rule extraction or context | `src/fcgc/checking/` |
| Change queries, retrieval providers or fallback | `src/fcgc/retrieval/` |
| Add a checker provider | `src/fcgc/integrations/` |
| Change Devin command behavior | `.agents/skills/` and `src/fcgc/agent/` |
| Read the shared checking instructions | `skills/fcg_checking/SKILL.md` |
| Configure local or WD operation | `config/` |
| Run or modify research experiments | `research/experiments/`; `src/fcgc/experiments/` |
| Find the frozen benchmark and annotation review guide | `benchmarks/v2/` |
| Read generated reports | `outputs/`; older archives remain under `runs/` |
| Decide where a new feature belongs | [Directory guide](docs/DIRECTORY_GUIDE.md) |

## Edit with care

Edit the named source packages, config templates and guides. Do not edit generated
`outputs/`, `build/`, `dist/`, environment files or archived results to change the
application. Do not put credentials into example configs. Ground-truth labels
require independent review and versioned changes; never feed them into retrieval
or checker predictions. Packaged `src/fcgc/fixtures/` and internal config defaults
are maintained assets, not scratch space. `core/` and `adapters/` mostly preserve
old imports: change the implementation named in each forwarding file instead.

For WD, read [WD integration](docs/WD_INTEGRATION.md) before choosing `--mode wd`.
It uses the existing host's authorized MCP tools; local fixtures never replace
missing WD access. No live WD integration is claimed by local tests.
