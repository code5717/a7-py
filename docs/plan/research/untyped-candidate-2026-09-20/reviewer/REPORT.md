# Advisory candidate review

Reviewed the isolated candidate's exact evaluator, global resolution, initializer fitting and Zig literal emission. No production files changed. The following findings describe the reviewed version, before any later fixes.

## Native findings

| Case | Observed Debug build and execution | Implication |
| --- | --- | --- |
| Distinct exact decimals compared | `9007199254740993.0 == 9007199254740992.0` prints `true` | Unsupported comparisons still compile and lose precision through existing host-float folding. Do not claim exact comparison support. |
| Signed zero | Explicit `f64 = -0.0` prints `0`, same as positive-zero control | Fraction-based materialization loses the source zero sign. This also changes ordinary literals. |
| Formatting default range | `BIG :: 2147483648` formats successfully as `2147483648`; maximum-i32 control also succeeds | Variadic formatting does not enforce the proposed category default's range. |
| Mixed typed operation | `x: i8 = 1; y := x + 200` reaches Zig and fails with exit 7; `x + 2` prints `3` | A7 still applies widening instead of diagnosing failed fitting to the typed operand. This is a backend rejection, not successful A7 validation. |
| Local scope control | Outer `X :: 2.0`, inner use before `X :: 3.0`, then outer use prints `2` and `2` | This ordinary shadowing control retained expected visibility. |

Sources, exact command arguments, stdout, stderr and exit codes are in `results.json` and `comparison-results.json`. Native probes used the real candidate CLI with Debug. This review did not run ReleaseFast; the controlling experiment owns both-profile qualification.

## Structural findings

The global resolver changes checking order but leaves declaration order intact. Exact binding cache keys use declaration identity. The evaluator does not execute function calls. These are appropriate boundaries for the slice.

`scan.py` ran the existing static recursion scanner over both sibling trees. `recursion.json` records all reported groups. The candidate added no reported recursive groups. This does not mean the inherited compiler has no recursion.

The comparison, mixed-operation, signed-zero and formatting gaps need explicit limitations or rejection guards if left outside the experimental slice. They must not be hidden by the successful integer-destination examples. No exhaustion tests, security qualification, release gate or external model CLI was used.
