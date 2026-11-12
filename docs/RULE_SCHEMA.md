# Rule evidence and checking contracts

`schemas/rules.py` is the canonical `RuleEvidence` contract. Source wording and
interpretation are separate fields. Explicit IDs are optional; generated evidence
IDs identify source-backed candidates without inventing official rule identifiers.

| Fields | Meaning |
| --- | --- |
| evidence_id / explicit_rule_id | Local candidate identity / optional source-declared ID |
| source_id / source_ref / document_version | Original document identity, reference and available version |
| heading_lineage | Original section context |
| normative_statement / normative_span | Exact authoritative statement and provenance |
| conditions / exceptions | Source-backed applicability and exception fragments |
| supporting_definitions / dependencies | Definitions and cross-references required for interpretation |
| section_span | Larger source context retained when needed |
| extraction_method / ambiguity_status / ambiguity_notes | Method and required human review |
| duplicate_of | Duplicate candidate reference; distinct scopes remain separate |

Spans use half-open Python Unicode character offsets `[start, end)` into the exact
decoded UTF-8 document, plus one-based inclusive line numbers and a verbatim excerpt.
They are not byte offsets. Source bytes are read without newline normalization.
`RuleExtraction` validates excerpts and line coordinates against the original
document. `FrozenCheckingTask` rechecks every rule/context span and source identity.

The normalizer supports Markdown sections, lists, paragraphs, fenced examples and
normalized tables. The segmenter classifies explanations, examples, conditions,
exceptions, definitions/dependencies and ambiguous material separately. Normative
keywords are evidence, not a guarantee that a statement is an independent rule.
Uncertain attachments retain larger sections and `review_required` instead of
silently making a conditional obligation unconditional. Source IDs, excerpt hashes
and references remain auditable across segmentation, selection and packing.

`EvidenceSelection` accounts for every candidate with include/exclude decisions,
reasons and uncertainty. `PackedCheckerRequest` preserves complete authoritative
clauses and their context; budgets never truncate rules. The later
`FrozenCheckingTask` contains the firmware hash, source documents, selected rules,
context status and warnings. Full-document mode is explicit for B0/P1/R. Reduced
mode supplies selected evidence to the checker while the host keeps originals.

`ModelFindings` requires exactly one `RuleFinding` per supplied evidence ID.
Applicability is `applies`, `not_applicable` or `unresolved`; decision is
`compliant`, `violating`, `not_applicable` or `unresolved`. A supported judgment
needs matching applicability and a valid source citation. Violations need exact
code locations or a stated localization uncertainty. Unknown IDs, fabricated
excerpts, mismatched sources, invalid locations and unsupported judgments on
unreviewed evidence are rejected. Validation establishes contract/citation integrity;
it does not prove semantic correctness.

Canonical instructions are skill 1.1.0 and prompt FCGC-PROMPT-V1. Execution metadata
records provider/model/settings, available model details, instruction/prompt/task
hashes, validated token counters and duration. Whole-artifact compliance is never
inferred from a retrieved subset or absence of findings.
