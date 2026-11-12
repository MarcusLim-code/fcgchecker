# Synthetic FCG: Pointer Contracts

Dataset version 2.0.0. Illustrative research rules only; not official WD requirements.
The following table applies to C firmware entry points receiving caller-owned memory.

| Rule | Requirement | Scope |
| --- | --- | --- |
| [SFCG-013] | Validate a required caller pointer before its first dereference. | Any entry point |
| [SFCG-014] | Reject a null output pointer before writing through it. | Output parameters |
| [SFCG-015] | Validate an externally supplied peripheral address against the allowed mapped range before MMIO access. | External addresses |
| [SFCG-016] | A null buffer is permitted when its length is zero; for a positive length the buffer must be non-null. | Length-bearing buffers |
| [SFCG-017] | Validate callback context before dereferencing it inside the callback. | Indirect callbacks |
| [SFCG-018] | Reject overlapping source and destination ranges when the operation contract forbids aliasing. | Copy without overlap support |

The zero-length exception in [SFCG-016] is intentional. It does not relax
[SFCG-013] for a separately required configuration pointer.
