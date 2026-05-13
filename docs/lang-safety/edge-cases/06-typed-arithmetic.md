# Gap 06 — Typed arithmetic with range tracking

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.4](../07-language-review.md#14-integer-arithmetic--bare----emit-zig-).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Today `+`, `-`, `*`, `<<` lower to Zig's plain operators. Under
`-O ReleaseFast` these wrap silently — UB. The contract requires
either a proof of non-overflow at the operator or an explicit
overflow-discipline operator (`+%`, `+|`, `checked_add`). The work is
in designing the range-tracker that discharges the proof obligation
for common patterns, and in the user-surface vocabulary.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| TA-01 | Literal `1 + 2` | Compiles | Constant-folded; safe |
| TA-02 | Loop induction `for i in 0..n: i + 1` | Compiles | Range `[1, n]`; `i + 1 ≤ n` proves no overflow if `n < usize::MAX` |
| TA-03 | `i + 1` where `i: usize` with no range info | Compiles, may wrap | **Compile error** — pick `checked_add` etc. |
| TA-04 | `a - b` where ranges prove `a ≥ b` | Compiles | Allowed |
| TA-05 | `a - b` where `a` and `b` are opaque `u32` | Compiles, may underflow | **Compile error** |
| TA-06 | `a * b` where `a: u8` and `b: u8` (proved-safe?) | Compiles in `u8`; can overflow | Either auto-promote to `u16` or **compile error** |
| TA-07 | `-(x: i32)` (unary negation) | Compiles; `INT_MIN` UB | **Compile error** unless range excludes `INT_MIN` |
| TA-08 | `x << k` where `k > bitwidth(T)` | Trap or UB | **Compile error** unless range proves `k < bitwidth` |
| TA-09 | `x.abs()` | n/a / not in stdlib? | Returns `?T` (handles `INT_MIN`) or returns `u32` |
| TA-10 | `usize + isize` mixed | Today: maybe allowed | **Compile error** — explicit conversion required |
| TA-11 | `u32 + u64` mixed width | Today: requires explicit cast | Explicit cast required (consistent) |
| TA-12 | `x + 0` | Compiles | Range preserved |
| TA-13 | `x + (-1)` for signed | Compiles | Effectively `x - 1`; range adjusted |
| TA-14 | `checked_add(a, b)` | n/a | Returns `?T` |
| TA-15 | `wrap_add(a, b)` | n/a | Returns `T`, wraps |
| TA-16 | `sat_add(a, b)` | n/a | Returns `T`, saturates |
| TA-17 | Modulo `a % b` where `b: NonZero<T>` | Compiles | Result range `[0, b)` for unsigned; `(-b, b)` for signed |
| TA-18 | Bit-and `a & mask` | Compiles | Always safe; range becomes `[0, mask]` |
| TA-19 | Bit-or `a | mask` | Compiles | Range becomes `[max(a_lo, mask_lo), max(a_hi, mask_hi)]` approximation |
| TA-20 | Bit-xor `a ^ b` | Compiles | Range becomes conservative |
| TA-21 | Compound assignment `x += y` | Same rules as `x = x + y` | Same |
| TA-22 | Range refinement after comparison: `if x < 100 { ... x + 1 ... }` | Compiles | Inside the `if`, `x: [_, 100)` — `x + 1 ≤ 100` |
| TA-23 | Wider-result auto: should `u8 + u8` produce `u16`? | Today: `u8 + u8 = u8` with possible overflow | **Open question** |
| TA-24 | Generic numeric `fn f<$T: Numeric>(a: $T, b: $T) -> $T` | Compiles | Generic instantiation re-checks ranges per concrete type |
| TA-25 | Constants in generic position | n/a | Constants known at instantiation; range trivially provable |
| TA-26 | Comparison `a < b` between different signed-ness | Today: maybe allowed | **Compile error** — explicit conversion |

## Interactions

- **Gap 01 cast.** `cast` is the only widening/narrowing/sign-change
  operator; range tracker propagates ranges through casts where
  defined.
- **Gap 02 nullable pointers.** No interaction.
- **Gap 03 definite assignment.** DA runs first; range tracker
  operates only on assigned values.
- **Gap 04 NonZero division.** `NonZero<T>` is a range `[1, T::MAX]`
  refinement. Range tracker should auto-promote range-proved values
  into `NonZero<T>` when needed (Q04c).
- **Gap 05 stack budget.** No interaction.
- **Gap 07 bounded indexing.** Same range-tracker; `s[i]` is safe
  iff `i`'s range fits `[0, s.length)`.
- **Gap 08 `Option<T>` / `Result<T, E>`.** `checked_add` returns
  `Option<T>`.
- **Gap 09 refinement-lite.** `Bounded<T, lo, hi>` is the refinement
  vocabulary item that the range tracker projects into. Auto-
  promotion from a range-proved value into a `Bounded` is the
  refinement framework's job.
- **Gap 10 affine ownership.** No interaction (arithmetic is on
  `Copy` types).
- **Gap 11 finite floats.** Float arithmetic uses different range
  semantics; this gap is integer-only.
- **Gap 12 FFI.** FFI returns are typed at the base level; user
  promotes if needed.
- **Match.** Range narrowing through `match arm`: `match v { case
  0..10: ...; case 10..: ... }` should narrow the binding in each
  arm.
- **Comparisons.** `if a < b` narrows both `a` and `b` along the
  branches.

## Failure modes

### False positives

- Common idioms that the range tracker can't see. Example: a
  function that takes `i: usize` and the caller knows it's small —
  the function-internal `i + 1` is rejected because the range is
  unconstrained.
  - Mitigation: `Bounded<T, lo, hi>` parameter types or `checked_add`.
- Imprecision in bit-or / bit-xor (TA-19, TA-20). Conservative bounds
  may force unnecessary `checked_*` use.
- Loops with non-trivial induction (`while i < n: i = next(i)`)
  where range can't be tracked.
  - Mitigation: rewrite as `for` loops where possible.

### False negatives

- Aliasing through references. If `a` and `b` are both `inout` of
  the same `i32`, modifications interleave. The exclusivity
  property from Gap 10 prevents this case statically.
- Overflow in a *intermediate* of `(a + b) * c` — operator-by-
  operator analysis catches each step; the language must check the
  intermediate.

### Ergonomic costs

- Heavy in arithmetic-dense code (digital signal processing,
  cryptography). Mitigation: provide `wrap_*` operators as a clean
  syntax (`+%`-style) for the common case where wrapping is the
  intended behaviour.
- New users writing `a + b` and hitting "overflow not proved" will
  be frustrated. Diagnostic must teach: "use `a.checked_add(b)` or
  `a.wrap_add(b)`; if you can prove the range, this becomes valid".

### Performance costs

- None at compile time (analysis is linear).
- Runtime: proved-safe operations emit bare `+` (zero-cost);
  `checked_*` emits `@addWithOverflow` (single instruction on
  modern CPUs); `wrap_*` and `sat_*` are zero-cost on x86_64.

## Open questions

- **Q06a.** Range-lattice precision. Three levels:
  - Interval `[lo, hi]`. Simplest. Loses correlation info.
  - Polyhedral (multiple variables, linear relations). Tracks
    `a + b ≤ c` correlations. More precise; harder to implement.
  - Use an SMT solver. Maximum precision; complex; pulls in Z3 or
    CVC5.
- **Q06b.** Width promotion (TA-23). Should `u8 + u8 = u16`? Three
  options:
  - Yes (Ada/SPARK style): result type widens to accommodate. Loses
    overflow even for `i32 + i32` (would need `i64`).
  - No: result type matches operand type; overflow detection at
    operator.
  - Per-operator: `+` keeps width, `mul_widening` widens.
- **Q06c.** Mixed sign / mixed width (TA-10, TA-11, TA-26). Two
  options:
  - Strict: always require explicit cast.
  - Lenient: allow when both sides have proved-compatible ranges.
- **Q06d.** Should there be a "no-overflow guarantee" annotation
  available on imported / external code (`@nooverflow`)? Probably
  no — it's the type system's job.
- **Q06e.** Compound assignments: same discipline (`+=` requires
  proof) or "the type of `x += y` is just `x = x + y`" syntactic
  expansion?
- **Q06f.** Unary negation (TA-07). Treat `-x` as `0 - x` (same
  discipline) or as a separate `negate` returning `?T`?
- **Q06g.** Abs (TA-09). Returns `T` (for `INT_MIN.abs()`?) or `?T`
  or `u32` (the unsigned absolute value)?
- **Q06h.** Subtraction underflow on unsigned (TA-05). Always
  forbidden without range proof, or provide an `wrap_sub` /
  `checked_sub` family analogous to add?
- **Q06i.** Bit ops range propagation (TA-18 – TA-20). Conservative
  intervals or precise bit-mask analysis?

## Source citations

- Today's emission: `a7/backends/zig.py:1566` for `+`, `-`, `*`.
- Today's emission: `a7/backends/zig.py:1561-1564` for shifts (with
  `@intCast` on the shift amount).
- Type-checking: `a7/passes/type_checker.py` (in `visit_binary`; no
  range tracking).
- Type assignability: `a7/types.py:108-140` (`is_assignable_to`)
  encodes signed/unsigned widening rules — relevant input for
  the range tracker.
- 4 bitwise / shift examples plus arithmetic across the current example suite
  to audit.

## Phase C decision-input summary

1. Q06a — range-lattice precision. **Drives:** the entire
   analysis architecture.
2. Q06b — width-promotion rule.
3. Q06c — mixed-sign / mixed-width policy.
4. Q06e — compound-assignment treatment.
5. Q06f — unary negation.
6. Q06h — unsigned subtraction.

The rest follow.
