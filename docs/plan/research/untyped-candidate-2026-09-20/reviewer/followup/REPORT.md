# Advisory follow-up review

All four previously reported ordinary-source failures are repaired in the rerun. The previous evidence remains unchanged.

The real candidate CLI built all ten prior sources using both `--profile debug` and `--profile release`. The release CLI selects Zig `ReleaseFast` in `a7/cli.py:114`. `results.json` records the twenty exact commands, complete source text, compiler output, exit status and successful executable output.

| Case | Debug and ReleaseFast result |
| --- | --- |
| Distinct decimal comparison | Builds and prints `false` |
| Same decimal comparison control | Builds and prints `true` |
| Exact `0.1 + 0.2 == 0.3` control | Builds and prints `true` |
| Negative zero | Builds and prints `-0` |
| Positive zero control | Builds and prints `0` |
| Mixed `i8 + 200` | A7 rejects with exit 6 before Zig |
| Mixed `i8 + 2` control | Builds and prints `3` |
| Formatting integer above `i32` maximum | A7 rejects with exit 6 |
| Formatting maximum `i32` control | Builds and prints `2147483647` |
| Local shadow control | Builds and prints `2`, then `2` |

The existing static recursion scanner found no candidate-added recursive groups compared with the baseline. `recursion.json` retains the complete reported groups. The changed helpers use loops and existing nonrecursive exact evaluation. Inherited recursive groups remain outside this patch.

Remaining limits found by code inspection, not newly qualified by these native probes:

- Exact evaluation still supports unary negation and `+`, `-`, `*`. Division, remainder and shifts use the existing behavior; this is not the packet's complete operator table.
- New fitting at mixed typed operations applies to integral peers for `+`, `-`, `*`. Float overflow fitting and other mixed operators lack the same new checker path.
- Integer fitting still uses the compiler's existing 64-bit pointer-size assumptions.
- The signed-zero probes cover literal materialization. They do not independently qualify every signed-zero arithmetic combination.
- This review did not qualify the packet's full context table, resource policy, security, packaging or release readiness.

`source-hashes.json` records hashes of the three modified compiler files reviewed. No candidate or production file was edited by this reviewer.
