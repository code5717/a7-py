# Numeric candidate follow-up

The isolated candidate satisfies the tested overflow, direct rounding, and exact division/remainder requirements. The final matrix has 92 passing expectations and two preserved inherited-behavior probes. Three additional maximum-finite controls pass. Accepted cases have matching Zig 0.16.0 Debug and ReleaseFast output. This is advisory prototype evidence, not production language approval or release qualification.

Implementation edits are confined to `candidate/`. New evidence is confined to this directory. Production source, the original baseline, `candidate-evidence/`, and the controller's `review-candidate/` snapshots were not edited.

## Numeric results

| Case | Final result |
| --- | --- |
| Finite `1e100` fitted to f32 | A7 exit 6, `Finite exact constant overflows f32`, no Zig artifact |
| Finite `1e400` fitted to f64 | A7 exit 6, `Finite exact constant overflows f64`, no Zig artifact |
| f32 midpoint `1.000000059604644775390625` | 1.0 |
| Same midpoint followed by enough zeros and a final 1, within the token limit | Upper neighbor of 1.0 |
| Value immediately below that midpoint | 1.0 |
| Short witness `1.0000000596046448` fitted to f32 | Upper neighbor of 1.0 |
| Odd-lower-significand tie and carry at 2.0 | Even neighbor |
| f64 midpoint and a value just above it | 1.0 and its upper neighbor |
| Half the minimum f32 subnormal | Positive or negative zero, following input sign |
| Minimum subnormal and subnormal-to-normal boundary | Expected nonzero/even neighbor |
| f32/f64 maximum-finite controls | Finite values accepted, overflow boundary rejected |
| `(9007199254740993.0 / 1.0) == 9007199254740992.0` | false |
| `5 / 2` assigned to f64 | 2 |
| `5.0 / 2` assigned to f64 | 2.5 |
| `5.0 / 2` assigned to i32 | A7 rejects fractional 5/2 |
| `(1.0 / 3.0) * 3.0 == 1.0` | true before materialization |
| Negative integer/floating remainder | Truncation toward zero, dividend's sign |
| `-0.0 / 2.0`, `0.0 / -2.0`, `-4.0 % 2.0` | -0, -0, -0 |
| Global `INF :: math.exp(1000.0)` | inf |
| Global `NAN :: math.sqrt(-1.0)` | Self equality false, self inequality true |
| Local typed math calls and typed f64 multiplication overflow | Existing inf/NaN behavior retained |

[Final CLI/native matrix](final-results.json) contains the complete A7 sources, exact commands, diagnostics, emitted Zig, exit codes, and native outputs. Its 94 cases include 60 accepted programs, 32 rejected programs, and two inherited-behavior probes. [Additional maximum-finite controls](supplemental-results.json) add two accepted programs and one rejection. Overflow errors point to the operand, such as line 2, column 25 in the controller's f64 case. Exact zero division and remainder reject at A7 stage with a source location.

Every final matrix source was recompiled against the final candidate. For unchanged emitted Zig, the runner retained the recorded successful build command/output and reran the native executable. The JSON identifies this reuse and links its prior build evidence. New or changed Zig was built in both profiles. No native outcome is inferred solely from an A7 compile.

## Implementation

`a7/exact_constants.py` now evaluates unary negation and exact rational addition, subtraction, multiplication, division, and remainder using explicit worklists. Integer-category division truncates toward zero. A floating operand keeps the rational quotient, including nonterminating decimal results such as 1/3. Remainder subtracts the truncated quotient times the divisor. Zero divisors produce A7 diagnostics. These supported exact operations do not fall through to host-float arithmetic.

Float materialization computes the binary exponent and target significand with integer arithmetic. It uses the remainder and significand parity to choose the nearest value, ties to even. The result is a 32-bit or 64-bit encoding. Python float storage is reconstructed from those already selected bits; it does not choose the rounding result.

The Zig backend emits `@as(f32, @bitCast(@as(u32, bits)))` or the f64/u64 form. The target representation is bounded by the target integer width. Zig does not round the original decimal through `comptime_float` on these paths. Exact binding caches retain their rational values so fitting one use to f32 does not specialize later f64 or integer uses.

The checker applies fitting to concrete destinations and mixed typed-float peers. It checks remaining default-f64 overflow after contextual fitting. This preserves typed identifiers and ordinary math-call results as typed values. Explicit casts retain the packet's category-default-then-cast behavior; they are not redefined as implicit direct fitting.

## Regression evidence and compatibility

[Selected existing tests](selected-tests.json) report 52 passed and one failed. The remaining failure is `test_listed_recursive_groups_still_exist`, which lists two semantic-validator recursion groups no longer present. [Fresh baseline reproduction](baseline-selected-failure.json) has the same failure. [The recursion comparison](recursion.json) finds no added recursive groups. Existing compiler recursion remains.

The first selected run exposed two additional failures, preserved in [the original selected result](selected-before-default-context-fix.json). Both older tests formatted exact integer quotients larger than i32 without a numeric destination. The first candidate had left those divisions to Zig, bypassing its own formatting default rule. Exact division now consistently applies the packet's i32 default and rejects these sources.

The isolated copies of those two tests now assign the same quotients/remainders to explicit wide intermediates before formatting. Their expected native numbers and typed runtime comparisons are unchanged. Two added rejection controls verify the bare large quotients fail at A7 stage. This is an explicit compatibility expectation update under the candidate's existing default rule, not an inherited baseline failure or a claim that division is unsupported. The source diff includes all test edits.

[Independent review](reviewer/REPORT.md) found and helped correct missing mixed-f32 fitting. Its initial failed native probes remain in `reviewer/mixed-results.json`; corrected probes are in `reviewer/mixed-final-results.json`. The independent rational-neighbor oracle passed 2,120 checks per width plus six overflow and two above-maximum-finite controls per width. [The final oracle result](reviewer/rounding-final-results.json) records the frozen helper's hash. Expected neighbors are derived by decoding IEEE encodings, not by copying the rounding algorithm.

`exploratory-results.json` preserves an initial subnormal probe rejected for exceeding the tokenizer's existing 100-digit limit. The final probe expresses the same minimum subnormal as an exact quotient within that limit. This was a probe-authoring correction, not a resource-policy experiment.

## Frozen sources and limits

[Source manifest](source-manifest.json) records every copied file's SHA256, the corresponding original-baseline hash, and the frozen copy's hash. [Frozen sources](final-sources.tar.gz) contain the complete copied candidate apart from Python/pytest caches. [Source diff](source.diff) compares it with the original sibling baseline. Four files differ: the exact-constant helper, type checker, Zig backend, and the two adjusted regression tests in `test/test_constant_folding_exact.py`.

The final source-tree SHA256 is `caaeeb0030e973b08dfb3454790d5aec985599f5a80039983047f08de71e9c15`. The manifest specifies the exact sorted-path hash calculation. The baseline diff SHA256 is `9e74611349748b65ab9d78b710bd56ebf0b3893608c5ff844ef9ea6f4a3342c1`.

This remains a bounded numeric slice. Exact bitwise operations and shifts are not implemented in this helper; they retain legacy paths. No general exactness claim applies to unsupported operations, calls, explicit casts, generic inference, patterns, or index/aggregate contexts. Declaration/type infrastructure remains the first candidate's partial model. In particular, untyped declaration initializers still receive provisional default-f64 materialization, so arbitrary-magnitude binding/cancellation behavior is not qualified by this matrix. The inherited local-forward-reference and global-side-effect-initializer probes still reach Zig failures.

No resource caps were implemented. No exhaustion tests, security qualification, full corpus comparison, package gate, or release gate ran. The sibling resource-policy review remains separate. Native evidence covers the current host and Zig 0.16.0 only.

Reproduce the numeric matrix with `finalize.py`, extra boundary controls with `supplemental.py`, selected regressions with `run_selected.py`, baseline failure with `baseline_failure.py`, recursion comparison with `scan.py`, and the independent oracle with `reviewer/check_rounding_final.py`. `snapshot.py` copies the final sources and regenerates the baseline diff and manifest. These scripts write only this follow-up evidence directory, except that selected pytest checks run the isolated candidate.

Archive note: the copied report changes only the frozen-source link to the
preserved archive. Commands and scripts retain their original temporary paths.
