# FCG Compliance Report

File: `/Users/marcuslim/Desktop/fcgchecker/src/fcgc/fixtures/benchmark_cases/C001.c`. Function: `whole artifact`.
Mode/strategy: local/p3.
Retrieval: benchmark. Workflow: complete.
Checker: not_evaluated. Evidence: incomplete_context.
Host-attested capture; Python does not independently authenticate live MCP access.
Judgments cover supplied evidence only; no corpus-wide compliance claim.

Checker: mock/mock-contract-v1.
- SFCG-001: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/api_returns.md; original lines 7-8.
  Condition: After `sensor_open` succeeds,
- SFCG-004: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/api_returns.md; original lines 13-14.
  Condition: When a callback is invoked through a function pointer and its contract
   returns status,
- SFCG-005: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/api_returns.md; original lines 15-16.
- SFCG-006: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/api_returns.md; original lines 17-18.
  Condition: only
   when the caller does not depend on the log being persisted
- SFCG-013: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/pointers.md; original lines 8-8.
  Condition: Any entry point
  Exception: It does not relax
[SFCG-013] for a separately required configuration pointer.
- SFCG-014: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/pointers.md; original lines 9-9.
  Condition: Output parameters
- SFCG-015: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/pointers.md; original lines 10-10.
  Condition: External addresses
- SFCG-016: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/pointers.md; original lines 11-11.
  Condition: Length-bearing buffers
  Exception: The zero-length exception in [SFCG-016] is intentional.
- SFCG-017: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/pointers.md; original lines 12-12.
  Condition: Indirect callbacks
- SFCG-018: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/pointers.md; original lines 13-13.
  Condition: Copy without overlap support
- SFCG-025: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/initialization.md; original lines 8-9.
  Condition: For the benchmark `State` module, the documented default threshold is 7.
  Exception: An object with static zero initialization may satisfy [SFCG-025] if zero is its
documented initial state.
- SFCG-026: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/initialization.md; original lines 10-11.
- SFCG-027: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/initialization.md; original lines 12-13.
  Condition: If initialization reports failure,
- SFCG-028: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/initialization.md; original lines 14-15.
  Condition: After a device reset,
- SFCG-029: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/initialization.md; original lines 16-17.
  Exception: This exception does not satisfy [SFCG-029] when the
documented default is nonzero.
- SFCG-030: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/initialization.md; original lines 18-19.
- ev-b49c1f98f30d95a4: unresolved/unresolved; No evidence or incomplete evidence context.
  Source: fcgc://synthetic-benchmark/decoy_bootloader.md; original lines 7-7.

Severity: unavailable without an authoritative requirement or explicit project policy.
Calls: {'search_calls': 3, 'fetch_calls': 5, 'transport_retries': 0}; estimated input tokens=6542.
Workflow ms=28.79; this includes agent/human waiting time.
Audit: `/Users/marcuslim/Desktop/fcgchecker/runs/native-final/check/session.json`.

- Warning: Sufficiency gate: ambiguous_applicability
- Warning: Review applicability: SFCG-001, SFCG-004, SFCG-006, SFCG-013, SFCG-014, SFCG-015, SFCG-016, SFCG-017, SFCG-018, SFCG-025, SFCG-026, SFCG-027, SFCG-028, SFCG-029, ev-b49c1f98f30d95a4

