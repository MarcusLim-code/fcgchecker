# Synthetic transfer guidance

Illustrative example only; not official WD requirements.

When an asynchronous transfer is pending, its caller must retain the submitted
buffer until completion. The caller must preserve its transaction identifier.

Exception: A confirmed cancellation may release the buffer early.

Note: Completion notification explains when the operation ends; this note is not
another requirement. Review the scope of the later exception before checking.
