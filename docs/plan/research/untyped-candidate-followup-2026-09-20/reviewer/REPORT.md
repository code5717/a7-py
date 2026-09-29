# Independent numeric review

The direct rational rounding helper passed an independent adjacent-value oracle for f32 and f64. Each width has 2,120 checks covering exact endpoints, midpoints, and nearby rational values on both sides. Both signs are tested. Named boundaries cover signed zero, minimum subnormals, the subnormal-to-normal transition, exponent carry, and maximum finite values. Six overflow checks and two values above maximum finite that still round to maximum finite also pass per width.

The oracle decodes selected IEEE integer encodings into rational values, then derives expectations from neighboring encodings and parity. It does not copy the candidate's exponent calculation or quantization algorithm. `rounding-results.json` records the reviewed helper hash. This is bounded correctness evidence, not a resource or security test.

Source review found a missing concrete-f32 fitting route for mixed arithmetic. The first copied CLI probes passed A7 but failed both Zig profiles for short-above-midpoint addition and f32 overflow addition. `mixed-results.json` preserves those failures. After the coordinator's fitting repair, `mixed-final-results.json` records these outcomes:

| Case | A7 | Debug and ReleaseFast |
| --- | --- | --- |
| Typed f32 zero plus 1.0000000596046448, compare with 1.0 | Accept | false |
| Typed f32 zero plus 1e40 | Reject, exit 6 | Not built |
| Typed f32 1.0 compared with exact midpoint 1.000000059604644775390625 | Accept | true |

The helper uses integer quotient/remainder to implement rounding to nearest with ties to even. The backend emits the target width's integer bit pattern through Zig bitCast. Thus the checked materialization path does not ask Zig to parse an arbitrary decimal through comptime_float. Exact DIV preserves rational results when either operand has floating category. Integer-category DIV truncates toward zero; MOD subtracts the truncated quotient times the divisor. Both operations remain inside the explicit evaluation stack.

The reviewer advised retaining new failures from older tests that format an out-of-i32 quotient without an explicit destination. Under the candidate's existing default-i32 rule, exact folding makes that implicit destination reject. Native arithmetic controls should use explicit i64/u64 destinations and leave original rejection evidence visible. This is a compatibility change exposed by exact folding, not an inherited failure and not unsupported division.

No generic, pattern, index, resource-policy, or security qualification was performed. Native observations cover only the recorded local Zig 0.16.0 Debug and ReleaseFast runs. The coordinator owns the broader matrix and final source snapshot.
