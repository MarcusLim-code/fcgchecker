---
name: "fcg-rules"
description: "Inspect source-backed FCG evidence, contextual exceptions, dependencies and reduction decisions for C firmware without declaring compliance."
argument-hint: "<file.c> [--function NAME] [--mode local|wd] [--strategy b0|p1|p2|p3] [--config PATH]"
triggers: ["user", "model"]
---

# fcg-rules

Inspect relevant source-backed rules without running compliance checking.

## Usage

`/fcg-rules examples/firmware/sensor_start.c`

Required: a C file path. Optional: `--function NAME`, `--mode local|wd`,
`--strategy b0|p1|p2|p3`, `--config PATH`, `--top-k N`, `--token-budget N`,
`--deadline SECONDS`. Defaults: local synthetic evidence, P3, 12000 estimated
context tokens and a 600-second workflow deadline.
For WD: `/fcg-rules path/to/firmware.c --mode wd --config config/wd_agent.toml`.

Output: `report.md` and a structured evidence trace under `outputs/checks/`, with
verbatim rules, sources, qualifications and reduction decisions. No verdict is
produced. Common issues: missing file/function, inaccessible sources, unsupported
content, empty results and ambiguity. Preserve warnings rather than inventing rules.

## Execute the request

Execute /fcg-rules with the evidence-inspection workflow in
`skills/fcg_orchestration/WORKFLOW.md`. It shares retrieval and rule interpretation
with /fcg-check, including `skills/fcg_checking/SKILL.md`, but never invokes a checker.

Invoke `fcgc agent invoke --command '<the slash invocation>' --output <fresh-audit>`.
For WD mode discover actual authorized tools and pass the observed host file; follow
the typed search/fetch handoff loop until the backend finishes or reports a limit.
No fixture substitution is permitted for WD mode. Missing files/functions,
unsupported content, access errors and incomplete evidence are explicit failures
or warnings, never evidence of compliance.

Read report.md and trace.json. Present original requirements and section context,
source IDs/versions/URIs, conditions, exceptions, definitions, dependencies and
ambiguity. Explain retained/excluded evidence from the reducer's recorded decisions.
Link the complete audit. Keep firmware and the knowledge source read-only. Do not
assign compliance decisions or unsupported severity in an inspection workflow.
