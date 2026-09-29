# Gap 06 — Typed arithmetic with range tracking

Status: Phase A research from before 2026-09-14, partly superseded. Ledger [L5](../../plan/decisions.md) makes `+ - *` wrap; negation, shifts, division, casts and sizes stay open under gate [G3](../../plan/README.md#g3-numeric-rules-beyond-wrapping).

Audit finding: [`../07-language-review.md` §1.4](../07-language-review.md#14-integer-arithmetic--bare-----emit-zig-).
Phase C decisions were to land in [`../08-decisions.md`](../08-decisions.md).

## Summary

In Phase A, `+`, `-`, `*` and `<<` lowered to Zig's plain operators, which
trap on overflow in safe builds and are undefined behavior under
`-O ReleaseFast`. The contract required either a proof of no overflow at
each operator, or an explicit overflow operator (`+%`, `+|`,
`checked_add`).

The work was in designing a range tracker that discharges the proof for
common patterns, and in choosing the user-facing vocabulary.

## Current behavior and ledger (2026-09-16)

Note (2026-09-16): ledger L5 changes the premise. Evidence is a source
read on 2026-09-16 plus the dated observations in the
[v1 plan](../../plan/README.md); no program was compiled in this session.

**What L5 decides.** Integer `+`, `-` and `*`, and their compound
assignments, wrap as in Odin. After `x: u8 = 255` and `x += 1`, `x` is 0.
The ledger lists `docs/SAFETY_CONTRACT.md:54` (range proofs for `+ - *`)
as superseded.

Superseded by L5:

- the overflow proof for `+ - *` (TA-03, TA-05, the overflow part of
  TA-06, and TA-21 for these operators);
- `checked_*`, `wrap_*` and `sat_*` as required forms (TA-14 to TA-16),
  since wrapping is now the meaning of the plain operator;
- result-width promotion (TA-23, Q06b);
- the proof policy in Q06e (for `+ - *`) and in Q06h.

Still open under G3: negation (TA-07), shift range (TA-08), `abs` (TA-09),
mixed signs and widths (TA-10, TA-11, TA-26), signed `MIN / -1` and
`MIN % -1` (TA-17), typed or exact constant evaluation (TA-01), narrowing
casts and allocation-size arithmetic.

**What the compiler does.**

- `_prove_integer_overflow` returns before its body
  (`a7/safety.py:631-636`). The obligation kind exists; the check is off.
- The backend emits the plain Zig operator (`a7/backends/zig.py:1595`).
  The G3 table (observed 2026-09-15) shows `x: u8 = 255; x += 1` compiling
  to `x += 1`, which traps in Debug and is undefined in ReleaseFast. L5
  requires 0; v1 plan track 3 lowers to Zig wrapping operators later.
- Shifts emit `<< @intCast(k)` with no range proof (`zig.py:1586-1593`).
  G3 observed `value << count` with `count: usize = 8` on a `u8`.
- An internal range tracker exists. `IntegerInterval` supports add, sub
  and mul (`safety.py:97-134`). Conditions narrow only an identifier
  compared with an integer literal (`safety.py:678-703`). A `for ... in`
  index gets `[0, ∞)` (`safety.py:364-368`). A C-style `for` loop gets no
  induction facts (`safety.py:353-363`). The facts serve casts, division,
  indexing and slicing.
- `docs/SAFETY_CONTRACT.md` ("Internal Facts") keeps facts internal, not
  public types. A public `Bounded<T, lo, hi>` would change that contract.
- `int` in this file predates L4 (explicit widths only).

## Subcases

| # | Pattern | Phase A: today | Phase A: target |
| --- | --- | --- | --- |
| TA-01 | Literal `1 + 2` | Compiles | Constant-folded; safe |
| TA-02 | Loop induction `for i in 0..n: i + 1` | Compiles | Range `[1, n]`; `i + 1 ≤ n` proves no overflow if `n < usize::MAX` |
| TA-03 | `i + 1` with `i: usize` and no range | Compiles, may wrap | Compile error: pick `checked_add` or similar |
| TA-04 | `a - b` where ranges prove `a ≥ b` | Compiles | Allowed |
| TA-05 | `a - b` with opaque `u32` operands | Compiles, may underflow | Compile error |
| TA-06 | `a * b` with `a: u8`, `b: u8` | Compiles in `u8`; can overflow | Promote to `u16`, or compile error |
| TA-07 | `-(x: i32)` (unary negation) | Compiles; `INT_MIN` is UB | Compile error unless the range excludes `INT_MIN` |
| TA-08 | `x << k` where `k > bitwidth(T)` | Trap or UB | Compile error unless the range proves `k < bitwidth` |
| TA-09 | `x.abs()` | Not in stdlib? | Returns `?T` (handles `INT_MIN`) or the unsigned type |
| TA-10 | `usize + isize` | Maybe allowed | Compile error: explicit conversion required |
| TA-11 | `u32 + u64` | Requires an explicit cast | Explicit cast required (consistent) |
| TA-12 | `x + 0` | Compiles | Range preserved |
| TA-13 | `x + (-1)` for signed `x` | Compiles | Same as `x - 1`; range adjusted |
| TA-14 | `checked_add(a, b)` | n/a | Returns `?T` |
| TA-15 | `wrap_add(a, b)` | n/a | Returns `T`, wraps |
| TA-16 | `sat_add(a, b)` | n/a | Returns `T`, saturates |
| TA-17 | `a % b` with `b: NonZero<T>` | Compiles | Result range `[0, b)` unsigned, `(-b, b)` signed |
| TA-18 | Bit-and `a & mask` | Compiles | Always safe; range becomes `[0, mask]` |
| TA-19 | Bit-or `a \| mask` | Compiles | Range approximated as `[max(a_lo, mask_lo), max(a_hi, mask_hi)]` |
| TA-20 | Bit-xor `a ^ b` | Compiles | Range becomes conservative |
| TA-21 | Compound assignment `x += y` | Same rules as `x = x + y` | Same |
| TA-22 | Range refinement after a comparison: `if x < 100 { ... x + 1 ... }` | Compiles | Inside the `if`, `x` is in `[_, 100)`, so `x + 1 ≤ 100` |
| TA-23 | Wider result: should `u8 + u8` give `u16`? | `u8 + u8 = u8`, may overflow | Open question |
| TA-24 | Generic numeric `fn f<$T: Numeric>(a: $T, b: $T) -> $T` | Compiles | Ranges re-checked per concrete type |
| TA-25 | Constants in generic position | n/a | Known at instantiation; the range is trivially provable |
| TA-26 | `a < b` across signedness | Maybe allowed | Compile error: explicit conversion |

Notes (2026-09-16):

- TA-11: `a7/types.py:124-126` lets `u32` assign to `u64` without a cast.
  How a mixed-width binary expression is typed was not checked.
- TA-19: `max(a_hi, mask_hi)` is not a sound upper bound for `|`
  (`1 | 2 = 3`). For non-negative operands, a sound bound is the next
  power of two above the larger maximum, minus one.
- TA-22: the current pass narrows `x > k` and `x >= k` inside the branch,
  and `x < k` and `x <= k` only after an `if` that always returns
  (`safety.py:663-668`, `689-694`). It learns no upper bound.
- TA-01: G3 observed that `a: u8 = 250 + 10` is rejected with "expected
  'u8', got 'i32'".

### Examples

Current A7 blocks use today's syntax. Results cited from G3 were observed
on 2026-09-15. Every block below was compiled on 2026-09-16, and any
rejection is recorded in its comment.

```a7
// Current A7. TA-01, TA-12, TA-13.
main :: fn() {
    three := 1 + 2               // TA-01
    x: i32 = 7
    same := x + 0                // TA-12
    down := x + -1               // TA-13
}
```

```a7
// Current A7. TA-02, TA-04, TA-22.
// Rejected (exit 6), but not for an arithmetic reason: `ret 0` in `gap`
// gives "Return type mismatch: expected 'u32', got 'i32'". With
// `ret cast(u32, 0)` the block compiles and TA-04 behaves as described.
next_index :: fn(n: usize) usize {
    last: usize = 0
    for i := cast(usize, 0); i < n; i += 1 {
        last = i + 1             // TA-02
    }
    ret last
}

gap :: fn(a: u32, b: u32) u32 {
    if a < b {
        ret 0
    }
    ret a - b                    // TA-04: a >= b here, but the current pass
                                 // compares only with literals, so it cannot see it
}

bump :: fn(x: u32) u32 {
    if x < 100 {
        ret x + 1                // TA-22
    }
    ret x
}
```

```a7
// Current A7 syntax; L5 meaning. TA-03, TA-05, TA-06, TA-21, TA-23.
wrap_demo :: fn(i: usize, a: u32, b: u32, p: u8, q: u8) {
    n := i + 1                   // TA-03: wraps under L5
    d := a - b                   // TA-05: wraps under L5
    m := p * q                   // TA-06, TA-23: stays u8, wraps
    x: u8 = 255
    x += 1                       // TA-21: L5 requires 0; today emits Zig x += 1 (G3)
}
```

```a7
// Current A7. TA-07, TA-08: open under G3.
edge :: fn(x: i32, k: u32) i32 {
    n := -x                      // TA-07: no i32 result for -2147483648
    s := x << k                  // TA-08: k >= 32
    ret n + s
}
```

```a7
// Current A7. TA-10, TA-11, TA-26: mixed signs and widths.
mixed :: fn(a: usize, b: isize, c: u32, d: u64, e: i32, f: u32) {
    s := a + b                   // TA-10
    w := c + d                   // TA-11
    lt := e < f                  // TA-26
}
```

```a7
// Current A7. TA-17 to TA-20.
// Rejected (exit 6), but not for an arithmetic reason: `ret 0` in `bits`
// gives "Return type mismatch: expected 'u32', got 'i32'". With
// `ret cast(u32, 0)` the block compiles.
bits :: fn(a: u32, b: u32) u32 {
    if b == 0 {
        ret 0
    }
    r := a % b                   // TA-17: result in [0, b)
    lo := a & 255                // TA-18: [0, 255]
    hi := a | 16                 // TA-19
    x := a ^ b                   // TA-20
    ret r + lo + hi + x
}
```

```a7
// Current A7 syntax. TA-24, TA-25.
LIMIT :: 10

add_twice($T) :: fn(a: $T, b: $T) $T {
    ret a + b + b                // TA-24: re-checked per instantiation
}

main :: fn() {
    total := add_twice(LIMIT, 1) // TA-25
}
```

```a7
// Proposed (Phase A). None of these functions exist. TA-09, TA-14 to TA-16.
size := x.abs()                  // TA-09: ?T or unsigned
c := checked_add(a, b)           // TA-14: ?T
w := wrap_add(a, b)              // TA-15: under L5, the same as a + b
s := sat_add(a, b)               // TA-16
```

## Interactions

- **Gap 01, cast.** `cast` is the only widening, narrowing or sign-change
  operator. The range tracker carries ranges through casts where defined.
- **Gap 02, nullable pointers.** No interaction.
- **Gap 03, definite assignment.** DA runs first; the range tracker works
  only on assigned values.
- **Gap 04, NonZero division.** `NonZero<T>` is the range `[1, T::MAX]`.
  The tracker should promote range-proven values into `NonZero<T>` where
  needed (Q04c).
- **Gap 05, stack budget.** No interaction.
- **Gap 07, bounded indexing.** Same range tracker; `s[i]` is safe when
  the range of `i` fits `[0, s.length)`.
- **Gap 08, `Option<T>` and `Result<T, E>`.** `checked_add` returns
  `Option<T>`.
- **Gap 09, refinement-lite.** `Bounded<T, lo, hi>` is the refinement the
  tracker projects into. Promoting a range-proven value into a `Bounded`
  is the refinement framework's job.
- **Gap 10, affine ownership.** No interaction; arithmetic is on `Copy`
  types.
- **Gap 11, finite floats.** Float arithmetic has different range
  semantics; this gap is integer-only. Note (2026-09-16): Gap 11 is
  superseded by L16.
- **Gap 12, FFI.** FFI values are typed at the base level; the user
  promotes them if needed.
- **Match.** Range narrowing through match arms:
  `match v { case 0..10: ...; case 10..: ... }` should narrow the binding
  in each arm.
- **Comparisons.** `if a < b` narrows both `a` and `b` in each branch.

## Failure modes

### False positives

- Common idioms the tracker cannot see. A function takes `i: usize`, and
  the caller knows it is small, but `i + 1` inside the function is
  rejected because the range is unconstrained. Mitigation: `Bounded<T, lo,
  hi>` parameter types or `checked_add`. Note (2026-09-16): under L5 this
  `+` wraps and is not rejected.
- Imprecise bit-or and bit-xor bounds (TA-19, TA-20) may force needless
  `checked_*` calls.
- Loops with non-trivial induction (`while i < n: i = next(i)`) where the
  range cannot be tracked. Mitigation: rewrite as `for` loops where
  possible.

### False negatives

- Aliasing through references. If `a` and `b` are both `inout` for the
  same `i32`, changes interleave. The exclusivity property from Gap 10
  prevents this statically. Note (2026-09-16): `inout` is not accepted
  (ledger L6 scope limit); the memory plan proposes rejecting aliased
  `ref` arguments such as `both(x, x)`.
- Overflow in an intermediate of `(a + b) * c`. Checking operator by
  operator catches each step; the language must check the intermediate.

### Ergonomic costs

- Heavy for arithmetic-dense code (signal processing, cryptography).
  Mitigation: `wrap_*` operators with clean syntax (`+%` style) for code
  where wrapping is intended. Note (2026-09-16): L5 makes wrapping the
  default.
- New users writing `a + b` and hitting "overflow not proved" will be
  frustrated. The diagnostic must teach: "use `a.checked_add(b)` or
  `a.wrap_add(b)`; if you can prove the range, this becomes valid". Note
  (2026-09-16): for `+ - *`, superseded by L5.

### Performance costs

- Compile time: the analysis is linear.
- Run time: proven operations emit a bare `+` (zero cost); `checked_*`
  emits `@addWithOverflow` (a single instruction on modern CPUs); `wrap_*`
  and `sat_*` are zero-cost on x86_64.

## Open questions

- **Q06a.** How precise is the range lattice?
  - Intervals `[lo, hi]`. Simplest; loses correlations.
  - Polyhedra (linear relations between variables). Tracks `a + b ≤ c`;
    more precise, harder to build.
  - An SMT solver (Z3 or CVC5). Most precise; complex.
  - Note (2026-09-16): the current internal tracker uses intervals.
- **Q06b.** Width promotion (TA-23): should `u8 + u8` give `u16`?
  - Yes (Ada/SPARK style): the result widens. Even `i32 + i32` would then
    need `i64`.
  - No: the result keeps the operand type; overflow is detected at the
    operator.
  - Per operator: `+` keeps width; `mul_widening` widens.
  - Note (2026-09-16): superseded by L5 — the result keeps the type and
    wraps.
- **Q06c.** Mixed sign and mixed width (TA-10, TA-11, TA-26):
  - Strict: always require an explicit cast.
  - Lenient: allow when both sides have compatible proven ranges.
  - Note (2026-09-16): open under G3 ("same-type operands or defined
    widening").
- **Q06d.** Should imported or external code get a "no overflow"
  annotation (`@nooverflow`)? Probably not; that is the type system's job.
- **Q06e.** Compound assignment: the same rule (`+=` needs a proof), or a
  plain expansion of `x += y` to `x = x + y`? Note (2026-09-16): L5 covers
  compound `+=`, `-=` and `*=`; they wrap.
- **Q06f.** Unary negation (TA-07): treat `-x` as `0 - x` under the same
  rule, or as a separate `negate` returning `?T`? Note (2026-09-16): open
  under G3.
- **Q06g.** `abs` (TA-09): return `T` (what about `INT_MIN.abs()`?), `?T`,
  or the unsigned type (`u32` for `i32`)? Open under G3.
- **Q06h.** Unsigned subtraction underflow (TA-05): always forbidden
  without a range proof, or a `wrap_sub`/`checked_sub` family like add?
  Note (2026-09-16): superseded by L5 — `-` wraps.
- **Q06i.** Bit-operation ranges (TA-18 to TA-20): conservative intervals
  or precise bit-mask analysis?

## Source citations

Line numbers describe the Phase A tree; 2026-09-16 locations follow.

- Emission of `+`, `-`, `*`: `a7/backends/zig.py:1566`. Now the generic
  branch at `zig.py:1595`.
- Emission of shifts: `a7/backends/zig.py:1561-1564`, with `@intCast` on
  the shift amount. Now `zig.py:1586-1593`.
- Type checking: `a7/passes/type_checker.py`, in `visit_binary`, with no
  range tracking. Range facts now live in `a7/safety.py`.
- Assignability: `a7/types.py:108-140` (`is_assignable_to`) encodes the
  signed and unsigned widening rules, an input for the tracker. Unchanged.
- To audit: 4 bitwise and shift examples, plus arithmetic across the
  example suite.

## Phase C decision inputs

1. Q06a, lattice precision. Drives the whole analysis design.
2. Q06b, width promotion. Superseded by L5.
3. Q06c, mixed sign and width policy.
4. Q06e, compound assignment. Settled for `+ - *` by L5.
5. Q06f, unary negation.
6. Q06h, unsigned subtraction. Superseded by L5.

The other questions follow.
