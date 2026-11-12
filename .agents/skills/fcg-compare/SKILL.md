---
name: "fcg-compare"
description: "Run the existing controlled B0/P1/P2/P3 development experiment and post-hoc evaluation using one selected fixture/replay backend and checker configuration."
argument-hint: "[--case CASE] [--dataset fcgc-synthetic-v2] [--repeat N] [--config PATH] [--experiment-config PATH]"
triggers: ["user", "model"]
---

# fcg-compare

Compare generic and firmware-aware retrieval on the same development cases.

## Usage

`/fcg-compare --case C001 --repeat 3`

No argument is required. Optional: `--case ID`, `--repeat N`, `--dataset ID`,
`--dataset-root PATH`, `--config PATH`, or `--experiment-config PATH`.
Defaults: all eight development cases of fcgc-synthetic-v2, three repetitions,
the same fixture retriever and mock checker across B0/P1/P2/P3. C001 also selects
its matched C002 variant. A complete experiment config belongs under
`research/experiments/`; do not mix it with per-case/provider overrides.

Output: a locked experiment and JSON/CSV/Markdown/HTML evaluation under a fresh
`outputs/experiments/` directory. Common errors: unknown/held-out case, invalid or
mixed configuration, stale output directory and unavailable snapshots. WD mode
comparison is not implemented; report that limitation without synthetic substitution.

## Execute the request

Execute /fcg-compare through `fcgc agent invoke --command '<the slash invocation>'
--output <fresh-comparison-directory>`. Read `docs/EXPERIMENTS.md` and
`skills/fcg_orchestration/WORKFLOW.md` for profile and safety details.

The backend uses the existing locked experiment runner and evaluator. B0 remains
generic; P1 adds planning; P2 adds reduction; P3 adds bounded fallback. Hold the
case, corpus/scope, retriever, checker, canonical interpretation/prompt and versions
constant. All checkers reuse `skills/fcg_checking/SKILL.md`. Keep matched variants
together. Use development data only for calibration and never open labels to
influence runtime queries or predictions. A requested case may bring its paired
variant; disclose that selection. Configured repetition defaults to three.

Inspect the returned summary, evaluation labels and generated Markdown/JSON/CSV/HTML.
Report retrieval, actual eligible compliance metrics and efficiency separately.
Mocks remain not_evaluated; provisional labels cannot establish independent accuracy.
Missing metrics stay unavailable. Do not manually alter code/config between ablations.

Live WD matrix execution is not implemented pending an approved enterprise dataset
and snapshot-governance adapter. If requested, report this explicitly; never run a
synthetic comparison in its place or create a second MCP connection. Individual WD
checks use the implemented bounded handoff, but are not an independent accuracy study.
Source files are read-only; all run outputs stay under the approved audit directory.
