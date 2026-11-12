# Synthetic Decoy: Manufacturing Bootloader Notes

Dataset version 2.0.0. Illustrative research material only; not official WD requirements.
Scope: a separate manufacturing bootloader that is not part of this benchmark.
Its buffer length, resource cleanup, initialization order, and flash_write
semantics differ from the application firmware contracts. It has a special
unaligned transfer mode. Similar words here must not be treated as applicability.
