# Synthetic FCG: Initialization and State

Dataset version 2.0.0. Illustrative research rules only; not official WD requirements.
These statements apply to stateful firmware modules even when their APIs have
unfamiliar names or are hidden behind macros.
For the benchmark `State` module, the documented default threshold is 7.

1. [SFCG-025] Initialize the state object before reading fields that depend on
   initialization.
2. [SFCG-026] Zero or explicitly set fields shared with an interrupt handler before
   enabling its interrupt source.
3. [SFCG-027] If initialization reports failure, prevent later use of the incomplete
   object in the same control flow.
4. [SFCG-028] After a device reset, restore required configuration before normal
   operations resume.
5. [SFCG-029] Apply a documented default configuration when the caller supplies no
   override.
6. [SFCG-030] Program configuration fields before enabling the device; later changes
   require a disable-and-reconfigure sequence.

An object with static zero initialization may satisfy [SFCG-025] if zero is its
documented initial state. This exception does not satisfy [SFCG-029] when the
documented default is nonzero.
