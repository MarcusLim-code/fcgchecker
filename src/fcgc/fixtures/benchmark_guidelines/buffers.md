# Synthetic FCG: Buffer Boundaries

Dataset version 2.0.0. Illustrative research rules only; not official WD requirements.

In this section a capacity is the number of writable elements, not the last valid
index. [SFCG-019] A loop writing an array must keep each index strictly below
capacity. [SFCG-020] When reserving a header and payload, check for arithmetic
overflow before adding their lengths and compare the total with capacity.

For text output, [SFCG-021] reserve room for a terminating zero byte before
writing it, including the empty-text path. A ring queue follows a different rule:
[SFCG-022] compute the next head and reject insertion when it would equal the tail.

The DMA contract adds two constraints. [SFCG-023] Before scheduling DMA, require
four-byte alignment of both address and byte count. [SFCG-024] A byte count returned
by an external read must be capped at destination capacity before copying.

The empty-text exception does not permit writing a terminator into a zero-capacity
buffer. Consult `pointers.md` for null pointers with zero length.
