# Synthetic FCG: Context

Illustrative research guidance only; this is not an official WD requirement.

## Section 2: Definitions

An active handle means a resource token acquired by a successful open call.

## Storage path

When a write targets persistent storage, the following rules apply.

[SFCG-901] The return status must be checked before reuse. The failure must be
propagated to the caller. The active handle must be validated as defined in
Section 2 before writing.

Exception: During forced shutdown, status propagation may be omitted after an
error is recorded.

Note: The word "must" in this explanatory note is not another obligation.
For example, a comment saying "must retry" is not a firmware requirement.

## Buffer path

For caller-owned buffers, the following rule applies.

The buffer length must be checked before copying. This check shall include the
terminator.

## Table cases

| Rule | Requirement | Condition | Exception |
| --- | --- | --- | --- |
| [SFCG-902] | Validate the destination before copying. | Caller-owned output | Except for a documented zero-length probe |

## Uncertain wording

The status should be handled appropriately where practical.
