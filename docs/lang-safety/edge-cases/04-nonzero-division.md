# Gap 04 — `NonZero<T>` for division

Status: Phase A research from before 2026-09-14, not a decision. Decisions are in the [ledger](../../plan/decisions.md); division, remainder, `MIN / -1` and shifts stay open under gate [G3](../../plan/README.md#g3-numeric-rules-beyond-wrapping), and float division under [G1](../../plan/README.md#g1-floating-point-details).

Audit finding: [`../07-language-review.md` §1.5](../07-language-review.md#15-integer-division--emits-divtrunca-b-with-no-nonzero-proof).
Phase C decisions were to land in [`../08-decisions.md`](../08-decisions.md).

## Summary

In Phase A, `/` and `%` emitted `@divTrunc(a, b)` and `@rem(a, b)` with no
proof that the divisor is non-zero. The contract required a divisor of
type `NonZero<T>`. The work is in choosing the refinement vocabulary and
the constructor and operator details.

## Current behavior (2026-09-16)

Note (2026-09-16): the compiler now rejects an unproven divisor without a
public `NonZero` type. Evidence is a source read on 2026-09-16, plus the
dated observations in the [v1 plan](../../plan/README.md); no program was
compiled in this session.

- `a7/safety.py:559-565` (`_prove_nonzero_divisor`) checks `/` and `%`
  (`safety.py:408-409`) and `/=` and `%=` (`safety.py:329-330`). An
  unproven divisor fails with "divisor may be zero".
- A divisor is proven by a non-zero integer literal, by `if b != 0 { ... }`
  inside the branch, or by `if b == 0 { ret ... }` after it
  (`safety.py:663-668`, `695-697`).
- So NZ-02, NZ-03 and NZ-05 are rejected today, and NZ-04 works through an
  `if` guard instead of a type.
- `-1` is a non-zero literal, so `x / -1` is approved. The plan's G3 table
  (observed 2026-09-15) shows `x: i8 = -128; q := x / -1` compiling to
  `@divTrunc(x, -1)`, which overflows. NZ-06 is open under G3.
- Shifts have no obligation and emit `<< @intCast(k)`
  (`a7/backends/zig.py:1586-1593`). NZ-16 is open under G3.
- Float division uses the same check. G1 (observed 2026-09-15) shows
  `zero / zero` on `f64` rejected with exit 6. Under L16, NaN and infinity
  are ordinary values, so G1 decides whether the float divisor proof goes.
- `docs/SAFETY_CONTRACT.md` ("Internal Facts") says facts are internal
  compiler data, not public language types. A public `NonZero<T>` would
  change that contract and needs approval.
- `int` in this file predates L4 (explicit widths only).

## Subcases

| # | Pattern | Phase A: today | Phase A: target |
| --- | --- | --- | --- |
| NZ-01 | `a / 5` (literal divisor) | Compiles, divides | The literal becomes `NonZero<T>` at compile time |
| NZ-02 | `a / 0` (literal zero) | Compiles, traps at run time | Compile error: no `NonZero` from 0 |
| NZ-03 | `a / b` with an opaque `int` `b` | Compiles | Compile error: construct `NonZero` first |
| NZ-04 | `a / d` after matching `NonZero::new(b)`: `match NonZero::new(b) { case some(d): a / d; case null: ... }` | n/a | Works |
| NZ-05 | `a % 0` (literal) | Compiles, traps | Compile error |
| NZ-06 | Signed `i32::MIN / -1` | Zig traps | Compile error: `-1` is not in `SafeDivisor<i32>` |
| NZ-07 | Unsigned `u32::MAX / x` | Safe for any non-zero `x` | Works with `NonZero<u32>` |
| NZ-08 | `NonZero<i32>::new(b)` returns `?NonZero<i32>` | n/a | Standard fallible constructor |
| NZ-09 | `NonZero<i32>::new_unchecked(b)` for cases the prover misses | n/a | Open question: does it exist? |
| NZ-10 | `NonZero<i32> + NonZero<i32>` | n/a | Result is `i32`; the user re-checks if needed |
| NZ-11 | `NonZero<i32> * NonZero<i32>` | n/a | Result is non-zero, so `NonZero<i32>`; signed overflow is possible |
| NZ-12 | `NonZero<i32>` to `i32` | n/a | Implicit, lossless upcast |
| NZ-13 | `i32` to `NonZero<i32>` | n/a | Only through `NonZero::new() -> ?NonZero` |
| NZ-14 | `NonZero<i32> + 0` | n/a | Result is `i32` (the proof is lost); the user re-promotes if needed |
| NZ-15 | Shift by zero (`x << 0`) | Correct | Allowed; no zero hazard |
| NZ-16 | Shift too far (`x << 32` on a `u32`) | UB in C; Zig traps in safe modes | Bound the shift amount by range (Gap 06) |
| NZ-17 | Float division by zero, `1.0 / 0.0` on `f64` | Produces inf | Allowed; the result is non-finite and Gap 11 catches it downstream |
| NZ-18 | `NonZero<usize>` for sizes and lengths | Useful for "non-empty slice" | Optional refinement, not required |
| NZ-19 | Negation `-(NonZero<i32>)` | n/a | `NonZero<i32>` unless the value is `INT_MIN`; that case overflows, so `?NonZero<i32>` |
| NZ-20 | `NonZero` as a generic constraint: `fn f<$T: NonZero>(...)` | n/a | Type-set vocabulary extension (Gap 09) |

Note (2026-09-16): NZ-11 — under L5, `*` wraps, so the product of two
non-zero values can be zero (`u8`: `16 * 16` wraps to `0`). The "result is
non-zero" claim does not hold for wrapping multiplication. NZ-17 — Gap 11
(finite floats) is superseded by L16, so no downstream finite check exists.
NZ-19 — negation of the minimum value is open under G3.

### Examples

Current A7 blocks use today's syntax. Results cited from the safety pass
come from a source read; results cited from G1 and G3 were observed on
2026-09-15. Every block below was compiled on 2026-09-16, and any rejection
is recorded in its comment.

```a7
// Current A7. NZ-01, NZ-02, NZ-05.
main :: fn() {
    a: i32 = 10
    q := a / 5                   // NZ-01: literal divisor is proven
    bad := a / 0                 // NZ-02: rejected, divisor may be zero
    rest := a % 0                // NZ-05: rejected
}
```

```a7
// Current A7. NZ-03, NZ-04: an unguarded and a guarded divisor.
raw_div :: fn(a: i32, b: i32) i32 {
    ret a / b                    // NZ-03: rejected, divisor may be zero
}

safe_div :: fn(a: i32, b: i32) i32 {
    if b == 0 {
        ret 0
    }
    ret a / b                    // NZ-04: proven by the early return
}
```

```a7
// Current A7. NZ-06 (G3 table, observed 2026-09-15: compiles, overflows).
main :: fn() {
    x: i8 = -128
    q := x / -1
}
```

```a7
// Current A7. NZ-07, NZ-18.
// Rejected (exit 6), but not for a divisor reason: `ret 0` in a function
// returning u32 or usize gives "Return type mismatch: expected 'u32', got
// 'i32'". Writing `ret cast(u32, 0)` and `ret cast(usize, 0)` makes the
// block compile, and both divisions are then proven by the early return.
top :: fn(x: u32) u32 {
    biggest: u32 = 4294967295
    if x == 0 {
        ret 0
    }
    ret biggest / x              // NZ-07
}

average :: fn(total: usize, count: usize) usize {
    if count == 0 {
        ret 0
    }
    ret total / count            // NZ-18
}
```

```a7
// Current A7. NZ-15, NZ-16: no shift-range proof today.
shift :: fn(x: u32, k: u32) u32 {
    same := x << 0               // NZ-15
    ret x << k                   // NZ-16: k >= 32 is not rejected
}
```

```a7
// Current A7. NZ-17 (G1, observed 2026-09-15: rejected with exit 6).
main :: fn() {
    zero: f64 = 0.0
    ratio := zero / zero
}
```

```a7
// Proposed (Phase A spelling). None of these names exist.
// NZ-08 to NZ-14, NZ-19, NZ-20.
d := NonZero<i32>::new(b)            // NZ-08: ?NonZero<i32>
u := NonZero<i32>::new_unchecked(b)  // NZ-09: open
sum := d1 + d2                       // NZ-10: i32
product := d1 * d2                   // NZ-11: NonZero<i32>
plain: i32 = d1                      // NZ-12: implicit upcast
back := NonZero<i32>::new(plain)     // NZ-13: only way in
lost := d1 + 0                       // NZ-14: i32, proof lost
neg := -d1                           // NZ-19: ?NonZero<i32>
f :: fn<$T: NonZero>(x: $T) $T { ... } // NZ-20
```

## Interactions

- **Gap 01, cast.** `cast(NonZero<i32>, x: i32)` is forbidden; only
  `NonZero::new(x: i32) -> ?NonZero<i32>` builds the type. The other
  direction, `cast(i32, x: NonZero<i32>)`, is lossless.
- **Gap 02, nullable pointers.** No direct interaction.
- **Gap 03, definite assignment.** A `NonZero<T>` local must be initialized
  by a constructor at declaration; DA applies normally.
- **Gap 05, stack budget.** No interaction.
- **Gap 06, typed arithmetic.** Range tracking gives `NonZero` for free in
  many cases. For example, `i: usize` in `for i in 1..n` has range
  `[1, n)`, which implies non-zero. The type checker should promote it.
  Note (2026-09-16): the internal interval facts in `a7/safety.py` already
  serve this role for the divisor check.
- **Gap 07, bounded indexing.** Indexing is not division, but it reuses the
  same range tracker.
- **Gap 08, `Option<T>` and `Result<T, E>`.** `NonZero::new` returns
  `Option<NonZero<T>>`. This sets how fallibility looks for the refinement
  family. Spelling is open under G5.
- **Gap 09, refinement-lite.** `NonZero<T>` is one of the closed
  refinement types, and its existence drives the refinement framework.
- **Gap 10, affine ownership.** `NonZero<T>` is `Copy` (a cheap value
  type); no ownership concerns.
- **Gap 11, finite floats.** Float division by zero does not trap; it
  produces inf or NaN. Gap 11 handles non-finite propagation separately.
  Note (2026-09-16): superseded by L16.
- **Gap 12, FFI.** FFI values cross as base types (`i32` and so on); user
  code promotes them with an explicit `NonZero::new`.
- **Generics and type sets.** NZ-20. The type-set vocabulary needs a
  `NonZero` predicate or marker constraint.
- **Tagged unions.** A variant carrying `NonZero<T>` is a variant with a
  refined payload; nothing special.
- **Match.** `match NonZero::new(x) { case some(d): ...; case null: ... }`
  is the canonical pattern.

## Failure modes

### False positives

- A loop where the prover cannot see that the divisor is non-zero, such as
  `for d in source { let q = n / d }`. Mitigation: call `NonZero::new` per
  iteration and match the `?NonZero` in the body.

```a7
// Current A7. The current equivalent: guard inside the loop.
spread :: fn(n: i32, source: []i32) {
    for d in source {
        if d != 0 {
            q := n / d
        }
    }
}
```

- Code that uses `0` as a sentinel, where division by zero is the failure
  path. Today that fails silently; the language turns each case into an
  explicit match.

### False negatives

- Unsafe FFI code that returns a `NonZero` without checking. The FFI
  boundary documentation must spell this out.
- `new_unchecked` (NZ-09), if it exists, is a footgun.

### Ergonomic costs

- Every division by a dynamic divisor grows a `match` block. Mitigation: a
  short propagation syntax (a `Result`-propagation operator?) from Gap 08.
- Generic numeric code (matrix arithmetic and similar) must thread
  `NonZero` through. A real cost.

### Performance costs

- None. At the Zig level `NonZero<T>` is a zero-cost `struct { value: T }`
  wrapper, and match-and-extract optimizes away.

## Open questions

- **Q04a.** Is there a `new_unchecked` constructor (NZ-09)?
  - No. Users must `match` every fallible construction.
  - Yes, with a `comptime` argument that carries the proof obligation (for
    example, `NonZero::comptime_new(42)` fails at compile time if 42 were
    zero).
  - Yes, with a debug-only assert. Rejected: it is a run-time trap.
- **Q04b.** Which `NonZero` arithmetic is defined?
  - `NonZero + NonZero`: only `*` keeps non-zero; `+`, `-` and `/` do not
    in general. Phase A decision: only `*` returns `NonZero`. Note
    (2026-09-16): wrapping `*` under L5 breaks this (see NZ-11).
  - Mixed `NonZero<T> + T`: result is `T`.
  - Comparison `NonZero<T> == T`: implicit upcast, then compare.
- **Q04c.** Are range-proven values promoted automatically? In
  `for i in 1..n: a / i`, does `i: usize` (range `[1, n)`) become
  `NonZero<usize>` without an explicit `NonZero::new`?
  - Yes: more ergonomic; the range tracker must publish into refinement
    promotions.
  - No: always write `NonZero::new(i)?`.
  - Note (2026-09-16): the current internal-fact design already works this
    way, with no public type.
- **Q04d.** One generic `NonZero<T>` for all integer widths, or per-width
  types (`NonZeroI32`, `NonZeroU64`)? A single generic is cleaner;
  per-width matches Rust's `core::num::NonZeroI32` family. Phase A
  preferred the single generic.
- **Q04e.** What about `SafeDivisor<T>`, which also excludes `-1` for
  signed types to avoid `INT_MIN / -1`?
  - Yes, a separate type. Cleanest.
  - Fold the extra exclusion into `NonZero<T>` for signed types.
  - Document `INT_MIN / -1` as known UB and panic.
  - Note (2026-09-16): open under G3 ("signed `MIN / -1` and `MIN % -1`").
- **Q04f.** Is `% 0` handled like `/ 0`? Yes. Note (2026-09-16): the
  current check already treats them the same.
- **Q04g.** Shift amounts: `x << k` needs `k` in `[0, bitwidth(T))`. Is
  that a `Bounded<usize, 0, bitwidth-1>`, or an ad-hoc rule? Note
  (2026-09-16): open under G3 ("shift-count range").

## Source citations

- Phase A emission: `a7/backends/zig.py:1550-1558`, `@divTrunc(a, b)` and
  `@rem(a, b)`. Now `zig.py:1575-1585`.
- Example: `build/debug/zig/src/020_operators.zig:16-17` shows
  `@divTrunc(a, b)` and `@rem(a, b)`. Not rechecked.
- Division examples to audit: Phase A counted 9, naming `004_func.a7`,
  `005_for_loop.a7`, `007_while.a7`, `020_operators.a7`,
  `021_control_flow.a7`, `030_calculator.a7`, `032_prime_numbers.a7` and
  2 others. Not recounted on 2026-09-16; there are now 43 examples.
- No `NonZero` type exists; this part is greenfield. Still true. The
  divisor proof lives in `a7/safety.py:559-565`.

## Phase C decision inputs

1. Q04a, `new_unchecked` policy. Drives safety against ergonomics.
2. Q04b, the `NonZero` arithmetic surface.
3. Q04c, automatic promotion of range-proven values.
4. Q04d, generic or per-width naming.
5. Q04e, how to exclude signed `-1`.
6. Q04g, shift rules.

The other questions follow.
