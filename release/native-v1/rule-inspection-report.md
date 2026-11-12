# FCG Rule Evidence Inspection

File: `/Users/marcuslim/Desktop/fcgchecker/src/fcgc/fixtures/benchmark_cases/C001.c`. Function: `whole artifact`.
Mode/strategy: local/p3.
Retrieval: benchmark. Workflow: complete.
Checker: not_evaluated. Evidence: incomplete_context.
Host-attested capture; Python does not independently authenticate live MCP access.
Judgments cover supplied evidence only; no corpus-wide compliance claim.

- SFCG-001: After `sensor_open` succeeds, the returned handle may be used; a failed
   open must be handled before any handle access.
  fcgc://synthetic-benchmark/api_returns.md; clear; retained=True.
  Selection: ['observed_api_match', 'feature_category_match', 'component_match', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: After `sensor_open` succeeds,
- SFCG-002: Firmware must inspect the result of `flash_write`, including a short
   write, before treating the bytes as stored.
  fcgc://synthetic-benchmark/api_returns.md; clear; retained=False.
  Selection: ['feature_category_match', 'specific_api_binding_unobserved']; The rule binds a different named API absent from parsed calls; no macro or indirect-call uncertainty was observed. Category matches remain logged but do not override the explicit API binding.
- SFCG-003: A negative result from `adc_read` is an error and must not be cast into
   a sample value.
  fcgc://synthetic-benchmark/api_returns.md; clear; retained=False.
  Selection: ['feature_category_match', 'specific_api_binding_unobserved']; The rule binds a different named API absent from parsed calls; no macro or indirect-call uncertainty was observed. Category matches remain logged but do not override the explicit API binding.
- SFCG-004: When a callback is invoked through a function pointer and its contract
   returns status, the caller must inspect that status before continuing.
  fcgc://synthetic-benchmark/api_returns.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: When a callback is invoked through a function pointer and its contract
   returns status,
- SFCG-005: A call declared infallible in the local interface has no status to test;
   do not invent a failure path solely for that call.
  fcgc://synthetic-benchmark/api_returns.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
- SFCG-006: Failure of a best-effort diagnostic log operation may be ignored only
   when the caller does not depend on the log being persisted.
  fcgc://synthetic-benchmark/api_returns.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: only
   when the caller does not depend on the log being persisted
- SFCG-013: Validate a required caller pointer before its first dereference.
  fcgc://synthetic-benchmark/pointers.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: Any entry point
  exception: It does not relax
[SFCG-013] for a separately required configuration pointer.
- SFCG-014: Reject a null output pointer before writing through it.
  fcgc://synthetic-benchmark/pointers.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: Output parameters
- SFCG-015: Validate an externally supplied peripheral address against the allowed mapped range before MMIO access.
  fcgc://synthetic-benchmark/pointers.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: External addresses
- SFCG-016: A null buffer is permitted when its length is zero; for a positive length the buffer must be non-null.
  fcgc://synthetic-benchmark/pointers.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: Length-bearing buffers
  exception: The zero-length exception in [SFCG-016] is intentional.
- SFCG-017: Validate callback context before dereferencing it inside the callback.
  fcgc://synthetic-benchmark/pointers.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: Indirect callbacks
- SFCG-018: Reject overlapping source and destination ranges when the operation contract forbids aliasing.
  fcgc://synthetic-benchmark/pointers.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: Copy without overlap support
- SFCG-025: Initialize the state object before reading fields that depend on
   initialization.
  fcgc://synthetic-benchmark/initialization.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: For the benchmark `State` module, the documented default threshold is 7.
  exception: An object with static zero initialization may satisfy [SFCG-025] if zero is its
documented initial state.
- SFCG-026: Zero or explicitly set fields shared with an interrupt handler before
   enabling its interrupt source.
  fcgc://synthetic-benchmark/initialization.md; clear; retained=True.
  Selection: ['feature_category_match', 'component_applicability_unresolved', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
- SFCG-027: If initialization reports failure, prevent later use of the incomplete
   object in the same control flow.
  fcgc://synthetic-benchmark/initialization.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: If initialization reports failure,
- SFCG-028: After a device reset, restore required configuration before normal
   operations resume.
  fcgc://synthetic-benchmark/initialization.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  condition: After a device reset,
- SFCG-029: Apply a documented default configuration when the caller supplies no
   override.
  fcgc://synthetic-benchmark/initialization.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate', 'preserve_uncertain_applicability']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
  exception: This exception does not satisfy [SFCG-029] when the
documented default is nonzero.
- SFCG-030: Program configuration fields before enabling the device; later changes
   require a disable-and-reconfigure sequence.
  fcgc://synthetic-benchmark/initialization.md; clear; retained=True.
  Selection: ['feature_category_match', 'general_rule_candidate']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.
- ev-b49c1f98f30d95a4: Similar words here must not be treated as applicability.
  fcgc://synthetic-benchmark/decoy_bootloader.md; clear; retained=True.
  Selection: ['component_applicability_unresolved', 'general_rule_candidate', 'preserve_uncertain_applicability', 'low_score_retained_without_inapplicability_proof']; Retained using observed API, category, component, or general-rule signals; conditions and exceptions remain unresolved unless explicit evidence settles them.

Severity: unavailable without an authoritative requirement or explicit project policy.
Calls: {'search_calls': 3, 'fetch_calls': 5, 'transport_retries': 0}; estimated input tokens=6542.
Workflow ms=25.54; this includes agent/human waiting time.
Audit: `/Users/marcuslim/Desktop/fcgchecker/runs/native-final/rules/session.json`.

- Warning: Sufficiency gate: ambiguous_applicability
- Warning: Review applicability: SFCG-001, SFCG-004, SFCG-006, SFCG-013, SFCG-014, SFCG-015, SFCG-016, SFCG-017, SFCG-018, SFCG-025, SFCG-026, SFCG-027, SFCG-028, SFCG-029, ev-b49c1f98f30d95a4

