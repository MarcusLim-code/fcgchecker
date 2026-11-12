# Stage 5: contextual rule segmentation demonstration

Source: [`contextual_rules.md`](../../../src/fcgc/fixtures/segmentation/contextual_rules.md),
synthetic version `1.0-synthetic`. This is illustrative research text, not an official
WD requirement. Run with:

```sh
.venv/bin/fcgc extract-rules \
  --document src/fcgc/fixtures/segmentation/contextual_rules.md \
  --document-version 1.0-synthetic
```

## Before: source wording

> When a write targets persistent storage, the following rules apply.
>
> [SFCG-901] The return status must be checked before reuse. The failure must be
> propagated to the caller. The active handle must be validated as defined in
> Section 2 before writing.
>
> Exception: During forced shutdown, status propagation may be omitted after an
> error is recorded.

## After: extracted evidence

| Evidence | Exact normative statement | Shared condition | Later exception | Review |
| --- | --- | --- | --- | --- |
| `SFCG-901`, line 13 | `The return status must be checked before reuse.` | The preceding storage-write condition | Preserved verbatim | Required |
| No explicit ID, line 13 | `The failure must be\npropagated to the caller.` | The same condition | Preserved verbatim | Required |
| No explicit ID, line 14 | `The active handle must be validated as defined in\nSection 2 before writing.` | The same condition | Preserved verbatim | Required |

In the table, `\n` displays an original source line break; the JSON evidence
contains the actual line break and exact character offsets.

The third item also carries the verbatim definition of **active handle** and a
`Section 2` reference. Each item records its document identity, version, heading
lineage, source character offsets and line numbers, extraction method, and exact
source excerpts. The later exception is attached to the three nearby obligations
with `review_required`: its precise scope needs a firmware engineer's review.
The engine does not discard the exception or silently pick one target.

The same fixture demonstrates a two-sentence buffer rule, a Markdown table row
with scope and exception cells, an informative note containing the word “must,”
an example, and vague wording flagged for review. The full JSON result contains
six rule candidates and seven classified non-rule fragments.

## Limits

Sentence boundaries, imperative wording, and later-context attachment are
heuristics. Exact spans and review flags make uncertain cases inspectable; they do
not establish the engineering meaning of a guideline. Complex Confluence
formatting, nested tables, rich macros, and implicit cross-document definitions
need an adapter and human review. No enterprise content or compliance checker is
used here.
