# Synthetic FCG: API Results and Calls

Dataset version 2.0.0. Illustrative research rules only; these are not official WD requirements.
Scope: C firmware in the synthetic benchmark. "Status" means the integer outcome returned
by a fallible operation; zero means success unless a local API declaration says otherwise.

1. [SFCG-001] After `sensor_open` succeeds, the returned handle may be used; a failed
   open must be handled before any handle access.
2. [SFCG-002] Firmware must inspect the result of `flash_write`, including a short
   write, before treating the bytes as stored.
3. [SFCG-003] A negative result from `adc_read` is an error and must not be cast into
   a sample value.
4. [SFCG-004] When a callback is invoked through a function pointer and its contract
   returns status, the caller must inspect that status before continuing.
5. [SFCG-005] A call declared infallible in the local interface has no status to test;
   do not invent a failure path solely for that call.
6. [SFCG-006] Failure of a best-effort diagnostic log operation may be ignored only
   when the caller does not depend on the log being persisted.

The exceptions in items 5 and 6 do not exempt `sensor_open`, `flash_write`, or
`adc_read` from their stated result-handling obligations. See `error_flow.md` for
propagation after a failed call.
