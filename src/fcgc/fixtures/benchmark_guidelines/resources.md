# Synthetic FCG: Resource Lifetime

Dataset version 2.0.0. Illustrative research rules only; not official WD requirements.
"Acquire" includes locks, handles, and allocated storage. See [SFCG-008] in
`error_flow.md` for error-return sequencing.

- [SFCG-031] Release a successfully acquired lock on every exit path.
- [SFCG-032] Close an opened device handle if a later operation fails before
  ownership is transferred.
- [SFCG-033] Free successfully allocated storage when its owner finishes with it.
- [SFCG-034] Ownership transferred to a documented receiver ends the sender's
  cleanup duty only after that receiver reports successful acceptance.
- [SFCG-035] Disable a device interrupt before tearing down state used by its handler.
- [SFCG-036] Release two or more acquired resources in reverse acquisition order
  when either release depends on the other's state.

The transfer exception in [SFCG-034] must not be assumed from a function name;
the local call contract must state acceptance explicitly.
