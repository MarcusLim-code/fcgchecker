# Synthetic FCG: Error Flow

Dataset version 2.0.0. Illustrative research rules only; not official WD requirements.
Applies across the benchmark's fallible APIs, including indirect and macro-wrapped calls.

- [SFCG-007] Preserve a specific nonzero error code when returning to the immediate
  caller; replacing it with a generic success value loses the failure.
- [SFCG-008] On an error path reached after resource acquisition, perform required
  cleanup before returning; the resource-specific rules in `resources.md` still apply.
- [SFCG-009] Report elapsed-deadline timeout separately from a hardware-fault result.
- [SFCG-010] Retry only an operation documented as transient and stop at the stated
  retry bound; permanent failures must not be retried as if transient.
- [SFCG-011] Inspect a fallible operation's status before starting an operation that
  assumes the first one succeeded.
- [SFCG-012] Clear a retained error state before starting a logically new transaction,
  so a previous failure is not reported as the current result.

For [SFCG-010], `BUSY` is the only transient status in this synthetic interface;
`IO_ERROR` and `BAD_ARGUMENT` are permanent. This definition is shared with
`api_returns.md` and is not inferred from API spelling.
