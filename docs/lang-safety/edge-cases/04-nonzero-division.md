# Gap 04 — `NonZero<T>` for division

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.5](../07-language-review.md#15-integer-division--emits-divtrunca-b-with-no-nonzero-proof).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Today `/` and `%` emit `@divTrunc(a, b)` and `@rem(a, b)` with no
divisor-zero proof. The contract requires the divisor to be of type
`NonZero<T>`. The work is in picking the refinement vocabulary and
deciding constructor / operator details.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| NZ-01 | `a / 5` (literal divisor) | Compiles, divides | Literal auto-promoted to `NonZero<T>` at compile time |
| NZ-02 | `a / 0` (literal zero) | Compiles, traps at runtime | **Compile error** (cannot construct `NonZero` from 0) |
| NZ-03 | `a / b` where `b` is an opaque `int` | Compiles | **Compile error**: must construct `NonZero` first |
| NZ-04 | `a / b` where `b` was matched non-zero: `match NonZero::new(b) { case some(d): a / d; case null: ... }` | n/a | Works |
| NZ-05 | `a % 0` (literal) | Compiles, traps | **Compile error** |
| NZ-06 | Signed `i32::MIN / -1` | Today: Zig traps | **Compile error**: `-1` not in `SafeDivisor<i32>` |
| NZ-07 | Unsigned `u32::MAX / x` | Safe for any non-zero `x` | Works with `NonZero<u32>` |
| NZ-08 | `NonZero<i32>::new(b)` returns `?NonZero<i32>` | n/a | Standard fallible constructor |
| NZ-09 | `NonZero<i32>::new_unchecked(b)` for cases the prover misses | n/a | **Open question**: does this exist? |
| NZ-10 | `NonZero<i32>` arithmetic: `NonZero<i32> + NonZero<i32>` | n/a | Result is `i32` (not `NonZero`); user must re-check if needed |
| NZ-11 | `NonZero<i32>` arithmetic: `NonZero<i32> * NonZero<i32>` | n/a | Result is **also non-zero** ⇒ `NonZero<i32>` (mul of non-zero is non-zero); but signed overflow possible |
| NZ-12 | Conversion `NonZero<i32> → i32` | n/a | Implicit upcast (lossless) |
| NZ-13 | Conversion `i32 → NonZero<i32>` | n/a | Only via `NonZero::new() -> ?NonZero` |
| NZ-14 | `NonZero<i32> + 0` | n/a | Result is `i32` (the proof is lost); user repromotes if needed |
| NZ-15 | Shift by zero (`x << 0`) | Behaves correctly | Allowed (no zero hazard) |
| NZ-16 | Shift by too much (`x << 32` on a `u32`) | UB in C; Zig traps in safe | Range-bound the shift amount (Gap 06 interaction) |
| NZ-17 | Float division by zero `(f64) 1.0 / 0.0` | Produces inf | Allowed, but result is non-finite; Gap 11 catches downstream |
| NZ-18 | `NonZero<usize>` for sizes/lengths | Useful for "non-empty slice" | Optional refinement; not required |
| NZ-19 | Negation `-(NonZero<i32>)` | n/a | Result is `NonZero<i32>` if not `INT_MIN`; otherwise overflow ⇒ `?NonZero<i32>` |
| NZ-20 | `NonZero` in a generic constraint: `fn f<$T: NonZero>(...)` | n/a | Type-set vocabulary extension (Gap 09) |

## Interactions

- **Gap 01 cast.** `cast(NonZero<i32>, x: i32)` is **forbidden**; only
  `NonZero::new(x: i32) -> ?NonZero<i32>` constructs the type. Cast
  may go the other way (`cast(i32, x: NonZero<i32>)` is lossless).
- **Gap 02 nullable pointers.** No direct interaction.
- **Gap 03 definite assignment.** A `NonZero<T>` local must be
  initialised at declaration via a constructor; DA applies normally.
- **Gap 05 stack budget.** No interaction.
- **Gap 06 typed arithmetic.** Range tracking gives free `NonZero`
  for many cases — e.g., `i: usize` inside a `for i in 1..n` loop has
  range `[1, n)` which implies non-zero. The type checker should
  auto-promote in that case.
- **Gap 07 bounded indexing.** Indexing is not division, but the
  same range-tracker is reused.
- **Gap 08 `Option<T>` / `Result<T, E>`.** `NonZero::new` returns
  `Option<NonZero<T>>`. Drives the surface of fallibility for the
  refinement family.
- **Gap 09 refinement-lite.** `NonZero<T>` is one of the closed
  refinement types. Its existence drives the refinement framework.
- **Gap 10 affine ownership.** `NonZero<T>` is `Copy` (cheap value
  type); no ownership concerns.
- **Gap 11 finite floats.** Float division doesn't trap on zero
  (produces inf/NaN); Gap 11 handles the non-finite-propagation
  issue separately.
- **Gap 12 FFI.** FFI return values cross as base types
  (`i32`, etc.); refinement promotion happens via explicit
  `NonZero::new` in user code.
- **Generics / type sets.** NZ-20. The type-set vocabulary needs a
  `NonZero` predicate or marker constraint.
- **Tagged unions.** A union variant carrying `NonZero<T>` is just a
  variant with a refined payload type; nothing special.
- **Match.** `match NonZero::new(x) { case some(d): ...; case null:
  ... }` is the canonical pattern.

## Failure modes

### False positives

- A loop where the prover can't see the divisor is non-zero. E.g.,
  `for d in source { let q = n / d }`. Mitigation: explicit
  `NonZero::new` per iteration, returning `?NonZero` matched in the
  body.
- Code that legitimately uses `0` as a sentinel and would divide-by-
  zero as the failure path. Today this is silent failure; the
  language refactors them all into explicit matches.

### False negatives

- Construction in unsafe FFI code that returns a `NonZero` without
  validation. The FFI boundary documentation must spell this out.
- Constructor `new_unchecked` (NZ-09) — if it exists, it's a footgun.

### Ergonomic costs

- Every dynamic-divisor division grows a `match` block. Mitigation:
  short-circuit syntax (`Result`-propagation operator?) inherited
  from Gap 08.
- Generic numeric code (matrix arithmetic, etc.) must thread
  `NonZero` through. Real cost.

### Performance costs

- None. `NonZero<T>` is a `struct { value: T }` zero-cost wrapper at
  Zig level; `match`-and-extract optimises away.

## Open questions

- **Q04a.** Is there a `new_unchecked` constructor (NZ-09)? Three
  options:
  - No. Users must `match` every fallible construction.
  - Yes, but with a `comptime` argument that's the proof obligation
    (e.g., `NonZero::comptime_new(42)` errors at comptime if 42 is
    zero).
  - Yes, with a debug-only assert (rejected — runtime trap).
- **Q04b.** `NonZero` arithmetic surface. Which of these are
  defined?
  - `NonZero + NonZero` — only `*` preserves non-zero; `+`, `-`, `/`
    do not in general. Decision: only `*` returns `NonZero`.
  - Mixed: `NonZero<T> + T` — result is `T`.
  - Comparisons: `NonZero<T> == T` — implicit upcast, then compare.
- **Q04c.** Auto-promotion of range-proved values. If `for i in
  1..n: a / i`, does the type checker auto-promote `i: usize`
  (range `[1, n)`) to `NonZero<usize>` without an explicit
  `NonZero::new`?
  - Yes: more ergonomic; requires range tracker to publish into
    refinement promotions.
  - No: explicit `NonZero::new(i)?` always.
- **Q04d.** Single `NonZero<T>` for all integer widths, or per-width
  types (`NonZeroI32`, `NonZeroU64`)? Single generic is cleaner;
  per-width matches Rust's `core::num::NonZeroI32` family. Single
  generic preferred.
- **Q04e.** What about `SafeDivisor<T>` (for signed types excluding
  `-1` to avoid `INT_MIN / -1`)? Three options:
  - Yes, separate type. Cleanest.
  - Fold into `NonZero<T>` with extra exclusion for signed types.
  - Document `INT_MIN / -1` as a known UB and panic.
- **Q04f.** Modulo `% 0` policy: same as `/ 0`? Trivially yes.
- **Q04g.** Shift amount discipline. `x << k` requires `k` in range
  `[0, bitwidth(T))`. Is that a `Bounded<usize, 0, bitwidth-1>`, or
  ad-hoc?

## Source citations

- Today's emission: `a7/backends/zig.py:1550-1558` — `@divTrunc(a, b)`,
  `@rem(a, b)`.
- Example: `build/debug/zig/src/020_operators.zig:16-17` shows
  `@divTrunc(a, b)` and `@rem(a, b)`.
- 9 division-using examples to audit: `004_func.a7`, `005_for_loop.a7`,
  `007_while.a7`, `020_operators.a7`, `021_control_flow.a7`,
  `030_calculator.a7`, `032_prime_numbers.a7`, plus 2 others.
- No `NonZero` type exists today; this is greenfield.

## Phase C decision-input summary

1. Q04a — `new_unchecked` discipline. **Drives:** safety vs ergonomics.
2. Q04b — `NonZero` arithmetic surface.
3. Q04c — auto-promotion of range-proved values.
4. Q04d — generic vs per-width naming.
5. Q04e — signed-`-1` exclusion strategy.
6. Q04g — shift discipline.

The rest follow.
