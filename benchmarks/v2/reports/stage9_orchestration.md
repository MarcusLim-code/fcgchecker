# Stage 9 offline experiment results

Executed `experiments/stage9_development.toml`: eight development cases × four
strategies × three repetitions = **96 runs**. All 96 executions finished, none
failed; 30 retained incomplete evidence contexts. All 96 checker results were mock
`not_evaluated`. No labels, real-model inference, enterprise calls, or MCP traffic
were used by this experiment.

| Strategy | Runs | Incomplete | Searches | Fetches | Total canonical checker-input estimated tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0 | 24 | 0 | 24 | 72 | 137,229 |
| P1 | 24 | 3 | 24 | 72 | 159,471 |
| P2 | 24 | 3 | 24 | 72 | 132,831 |
| P3 | 24 | 24 | 72 | 129 | 180,312 |

The local word/punctuation approximation counts the actual canonical prompt,
including skill/schema overhead, separately from Stage 6's rendering estimates.
All 32 case/strategy groups recorded one source order across three repetitions.
Every repetition remains in the summary. These totals do not establish accuracy,
compliance, or enterprise latency improvements.

Artifacts are in `runs/stage9-development/`: lock, summary, 96 ordered content
snapshots, traces, frozen tasks and checker inputs. The lock hash is
`55b476a02503eb1d2c55fb272dbe305b496c3f5916176b03308c6669237696c9`.

Replayed `C001-p3-r01` to `runs/stage9-replay-C001-p3/` with exact evidence replay
**true**. Source/task hashes and ordered call responses matched. Timing and model
predictions are not claimed equivalent. The snapshot hash is
`70d93e8bd714e869ee84e662aa4fbb1ef21bbf98d5b343f6e10ce94749aec501`.

Validation: 90 tests passed; Ruff and skill validation passed. Tests cover run
isolation, all four strategy replays, failed runs, missing/tampered snapshots,
configuration/code locking, split separation, checker matrices, optional R,
three-repetition execution, trace completeness, and retrieval variability.
See [experiment operation](../../../docs/experiments.md) for commands and limits.
