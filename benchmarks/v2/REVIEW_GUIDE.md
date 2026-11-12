# Synthetic FCG benchmark review guide

**Status:** All 24 annotations are provisional. No independent firmware engineer
review has been performed. These are illustrative research rules and cases, not
official WD requirements or validated production firmware.

## What to review

The public manifest is `manifest.json`; `rules.json` maps each of the 36 synthetic
rule IDs to a document and source line. Eight corpus documents are in
`src/fcgc/fixtures/benchmark_guidelines/`, including two explicit scope decoys.
The 24 C files are in `src/fcgc/fixtures/benchmark_cases/`. One annotation JSON
per case is stored only in `benchmarks/v2/ground_truth/development/` or
`benchmarks/v2/ground_truth/heldout/`.

The development split contains C001–C008 (four matched groups). C009–C024 are
held out (eight groups). A group's variants stay in the same split. Case IDs and
public behavior tags do not encode the expected outcome.

## Independent firmware review procedure

1. Freeze the rule corpus and record its dataset version before inspecting labels.
   Read the full source document for each cited rule, including scope, shared
   definitions, later exceptions, and cross-references. Treat decoys as out of
   scope for these application-firmware cases.
2. For each case, read the C source and decide applicability **before** looking
   at its provisional JSON. Include general rules that apply without an API name.
   An empty applicable-rule list means no rule was established; it does not mean
   the code is compliant. If an API contract is unknown, record that uncertainty.
3. For every applicable rule, decide `compliant`, `violation`, or `uncertain` from
   code behavior and the stated synthetic contract. Examine all control-flow
   paths, macro expansions, indirect calls, ownership transfer, and exception
   conditions. Do not infer compliance from a retriever hit or miss.
4. Compare your decisions with the provisional annotation. Check that the code
   hash matches, every quoted evidence snippet is exact, and each violation span
   points to the line that causes the failure. Record disagreements and a reason
   before changing any label.
5. Have a second engineer review disagreements without seeing the first reviewer's
   verdict. Resolve them using the corpus text; mark unresolved cases `uncertain`.
   Only set `review_status` to `independently_reviewed` after this process and
   increment `annotation_version` for any substantive annotation change.

## Split discipline

Use only C001–C008 annotations for prompt selection, thresholds, retrieval
experiments, or error analysis during development. The public runtime loader
never reads annotations. The calibration loader exposes only development
annotations. Held-out JSON files are read by the integrity validator and should
be opened for final evaluation only after methods and thresholds are frozen.
Do not move matched variants between splits or tune on held-out outcomes.

## Validation

From the repository root:

```sh
.venv/bin/python -m fcgc.experiments.quality benchmarks/v2 \
  --report benchmarks/v2/validation_report.json
```

The validator checks schema and versions, 36 rule source references, all case
hashes, status presence, evidence and violation spans, duplicate IDs, public
input leakage markers, split groups, and cross-split five-token similarity.
The target counts and similarity threshold are configurable in `benchmark.toml`.
For smaller public experiments, `PublicBenchmark.select_cases(development=4,
heldout=8)` selects whole matched groups deterministically without opening labels.
Automated checks cannot establish semantic correctness; engineering review is
required before using these labels as final ground truth.
