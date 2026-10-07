# Numerics + conversions: research

Scope: MIN/-1, -MIN, oversized shifts, narrowing-cast proofs, float-to-int
runtime path, ReleaseFast backstop (L39), fold-pipeline wording (§2.5 vs §4.2.1).
No implementation. Each packet states before/after and G1/G3 impact.

## 1. Current mechanics (file:line)

- Literal fold entry: `a7/ast_preprocessor.py:542-669`. Node-local only,
  literals in, literal out. Unfolded nodes go to Zig unchanged.
- Integer fold: `a7/const_eval.py:93-154`. `/`,`%` truncate toward zero
  (`truncating_divmod`, lines 76-81). Result folds only if it fits the node
  type (`_fit_integer`, lines 66-73). Shifts fold only when
  `0 <= amount < width` (lines 148-151).
- Negation fold: `a7/const_eval.py:84-90`. `-value` then fit-check. So
  `-(-2147483648)`-style MIN negation returns None and stays unfolded.
- Exact constants: `a7/exact_constants.py:81-222`. Rational pairs plus a
  per-operation f64 shadow. Both-i32 `+,-,*` wrap (`lines 157-166`); float
  ops round per-op in f64; int `/`,`%` by zero return None so the safety
  pass reports them. `materialize` + `ieee_bits` at lines 229-321.
- Shift typing: `a7/passes/type_checker.py:1569-1587`. Literal-left shifts
  allow counts up to 64; declared-left shifts use the operand width.
  `_shift_overflows_destination` (`lines 3446-3478`) rejects a literal
  shift value that does not fit the destination; amounts >= 64 defer to
  the count check.
- Unsigned negation rejected: `type_checker.py:1610-1614`.
- Safety: divisor proof `a7/passes/safety.py:919-925` (applies to float
  division too, which contradicts L16/G1). Integer `+,-,*` never error;
  `_prove_integer_overflow` (`lines 995-1028`) only approves a non-wrapping
  release lowering when both operand intervals fit. Float-to-int proof
  (`lines 1036-1043`) accepts float literals that are finite, integral,
  and in range; everything else errors.
- Cast classes: `a7/cast_classifier.py:47-83`. Lossless ok. Signed narrowing
  and unsigned narrowing are FORBIDDEN ("requires a range proof") with no
  proof syntax. Signed-to-unsigned needs proven non-negative; unsigned to
  signed needs a wider target.
- Zig lowering: `a7/backends/zig.py:1855-1873` (`@divTrunc`, `@rem`,
  `<< @intCast`), casts `lines 2042-2052` (`@as`, `@floatCast`,
  `@intFromFloat`, `@floatFromInt`, `@intCast`), wrapping switch
  `lines 2074-2083` (Debug wraps; release drops the suffix only when the
  safety pass proved `*_nonwrap`).

## 2. Per-operation cross-language handling

Checked against toolchain docs at time of writing; re-verify pins before
locking SPEC wording.

| Op | Zig (current target) | Rust | C | Odin (verify pin) |
| --- | --- | --- | --- | --- |
| `MIN / -1` (signed) | `@divTrunc` traps (safe modes), UB in ReleaseFast | panics Debug, wraps Release | UB | traps or defined wrap per build mode; confirm |
| `MIN % -1` | `@rem` same trap/UB split | panics Debug, `0` Release | UB | confirm; likely mirrors division |
| `-MIN` | `(-x)` overflow: trap Debug, UB ReleaseFast | panics Debug, wraps Release | UB | confirm |
| Shift count >= width | safety check Debug, UB ReleaseFast | panics Debug, masks Release | UB | confirm |
| Float->int out of range / NaN | `@intFromFloat` traps safe, UB ReleaseFast | `as` saturates (no trap) | UB | confirm; usually truncates, range unchecked |
| Narrowing int cast | `@intCast` traps on out-of-range safe, UB ReleaseFast | `as` truncates silently | truncates | truncates; confirm |

A7 today inherits the Zig column exactly, including the ReleaseFast UB
column. That is the L39 question below.

## 3. Fold-pipeline contradiction (§2.5 vs §4.2.1)

- §2.5 (`docs/SPEC.md:157-167`): typed folds use runtime rules. Integer
  `+,-,*` on i32-fitting operands wrap; floats round per-op in f64.
- §4.2.1 (`docs/SPEC.md:500-557`): wholly untyped `::` arithmetic is exact.
  `+,-,*` do not wrap or round; `5/2` is 2, `5.0/2` is 2.5; comparisons
  use exact values (`0.1+0.2 == 0.3` is true).
- Conflict: one section says fold like the runtime, the other says never
  wrap or round before a destination is known. Both cannot describe the
  same node. Fix is editorial: §2.5 governs typed expressions, §4.2.1
  governs untyped `::` expressions, with the fit-then-operate rule at
  `SPEC.md:552-557` as the bridge. Packet D1 below.

## 4. Decision-ready packets

D1. Fold routing (typed vs untyped). Before: `A :: 2000000000 + 2000000000`
  folds wrapped or exact depending on which pass runs. After: untyped
  `::` stays exact until a destination fits it; typed folds match runtime.
  Compat: G3 closes the `a: u8 = 250+10` class; exact `::` programs that
  relied on wrap reject with a located message.

D2. `MIN / -1`, `MIN % -1`, `-MIN`. Before: emits `@divTrunc(x,-1)`,
  `@rem(x,-1)`, `(-x)`; traps Debug, UB ReleaseFast
  (`docs/plan/README.md:189`). After (recommended): reject unless proven
  safe; provide checked/wrapping spelling later. Compat: G3; rare code
  that never executed these values keeps compiling, executing cases fail
  closed at compile time.

D3. Oversized shifts. Before: `value << @intCast(count)` with runtime
  count unchecked (`zig.py:1866-1873`). After: require count proof
  `0 <= count < width`, keep literal-destination check. Compat: G3;
  dynamic shifts need a guard; literal shifts unchanged.

D4. Narrowing-cast proof syntax. Before: `cast(u8, n)` rejected with no
  way to prove it (`cast_classifier.py:78-81`). After: add one proof form
  (range guard or checked-cast spelling), keep default reject. Compat:
  G3; no existing program changes meaning; new syntax unlocks ports.

D5. Runtime float-to-int path. Before: literal-only proof
  (`safety.py:1036-1043`) plus raw `@intFromFloat` (trap/UB split).
  Choice: (a) reject without proof (status quo, L39-migration needed for
  any runtime check), (b) saturate like Rust `as`, (c) trap in all
  profiles. Recommended: (a) now, decide (b)/(c) with G1 float guards.
  Compat: G1; (b) changes values silently, (c) adds release traps.

D6. ReleaseFast backstop under L39. Before: proven-`nonwrap` nodes drop
  wrapping; everything else keeps it, but `@divTrunc`/`@rem`/`@intCast`/
  `@intFromFloat`/shifts stay UB in ReleaseFast when reached.
  L39 (`docs/plan/decisions.md:118`) allows checked execution and requires
  checks to remain in release, but the fail-closed contract needs a
  migration packet first. After: either keep fail-closed (no new UB in
  release; add checks) or approve defined-wrap/saturate semantics per op.
  Compat: G3 + Wave B memo input; affects performance work (L38) and
  release parity claims.

## 5. G1/G3 impact

- G1 (floats): D5 + float divisor proof (`safety.py:919-925`, L16). Float
  `x/0` currently errors; IEEE wants inf/NaN. Changing it alters guard
  rules and docs.
- G3 (integers/casts): D1-D4, D6. All keep fail-closed until their packet
  lands; each needs before/after examples and release-profile proof runs.
