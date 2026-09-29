# Flow-Sensitive Narrowing — Research Notes for Cluster CD

> **Status:** research. Phase C input for Cluster CD (flow analysis), written
> before 2026-09-14 and cleaned up on 2026-09-16. Not a decision document.
> The authoritative record is the ledger in
> [`../plan/decisions.md`](../plan/decisions.md).
> Companion to [`conversions.md`](./conversions.md) and
> [`parameter-modes.md`](./parameter-modes.md).

> **Note (2026-09-16): the idea stands, but the examples and several premises
> are stale.**
>
> - The examples use `int`, `uint` and `number`. Ledger L3 removes `number`;
>   L4 keeps only explicit widths (`i8`–`i64`, `u8`–`u64`, `isize`, `usize`).
>   Restate under gate G3.
> - The file lists "no overflow" as an obligation that narrowing discharges and
>   cites D.003. L5 makes `+`, `-` and `*` wrap, so they need no overflow proof.
>   Division, casts, shifts and sizes still need proofs.
> - Float narrowing assumes finite `number` values. L16 adopts IEEE 754 floats,
>   so NaN breaks negation and De Morgan reasoning on float comparisons (see
>   [Floats under IEEE 754](#floats-under-ieee-754)).
> - `?T`, `Option`, `some` and `none` are not current features;
>   [`../STATUS.md`](../STATUS.md) lists `Option` and `Result` as planned. Current
>   A7 uses `ref T` with `nil`.
> - The invalidation rules use `inout` and `borrow` parameter modes and `Copy`
>   types. L6 approves immutable arguments as a principle but no mode syntax.
>   Proposed D.040, D.041 and D.049 were not accepted.
> - The table also mentions mutation through `*ptr`. Public A7 syntax has no
>   dereference operator.

## The idea

A variable's type is what the compiler knows about it at a program point. Most
languages give a binding one type everywhere in its scope. Flow-sensitive
narrowing lets the type differ on each side of a branch.

The user's framing, as a proposed example:

Proposed:

```a7
f :: fn(b: int) int {
    a: int = 10

    // here `b: int` — could be anything (incl. zero)
    q := a / b                          // compile error: b may be zero

    if b != 0 {
        // here `b: int with non-zero range` — a narrower subtype
        q2 := a / b                     // OK; divisor proved non-zero
    }

    // here `b: int` again — narrowing didn't escape the branch
}
```

Inside `if b != 0`, the type checker treats `b` as a narrower subtype of `int`:
any `int` except zero. That subtype meets division's precondition.

Current A7 has the same behavior for this case, with explicit widths:

Current A7:

```a7
f :: fn(a: i32, b: i32) i32 {
    if b != 0 {
        ret a / b               // accepted: condition proves b != 0
    }
    ret 0
}
```

This follows from `_facts_from_condition` and `_prove_nonzero_divisor` in
`a7/safety.py`. Writing `ret a / b` without the guard is rejected with
"divisor may be zero".

The same mechanism covers:

- **Nullability:** after `if x == nil` exits, `x` is non-nil.
- **Bounds:** inside `if i < s.length`, `i` is bounded by `s.length`.
- **Tagged unions:** inside `case some(v):`, `v` has the inner type rather than
  `Option<T>`.
- **Equality:** inside `if x == 5`, `x` is the value 5.
- **Recursion-free calls** that the user has already proved safe.

The original notes call narrowing the single mechanism behind the
zero-runtime-error contract for runtime-dependent values. Each SPARK-tier
obligation, such as a non-zero divisor or an in-bounds index, is discharged by
reading the narrowed type at the use site.

---

## What the compiler does today

Verified on 2026-09-16 by reading `a7/safety.py` and
`test/test_cast_safety_matrix.py`. The compiler was not run for this cleanup.

The safety pass lives in `a7/safety.py`, not `a7/passes/semantic_validator.py`
as the original notes planned. It tracks one fact per variable: an integer
interval, a non-zero flag, a nil state and a known length. Facts are scoped to
a block and restored when the block ends.

| Mechanism | Current behavior |
| --- | --- |
| Starting facts | a local gets the fact of its initializer; a function parameter starts with no range |
| Recognized conditions | only `name OP literal`, one comparison |
| `x >= c`, `x > c` | lower bound inside the then-branch |
| `x < c`, `x <= c` | lower bound after an `if` whose then-branch ends in `ret` |
| `x != 0` / `x == 0` | non-zero inside the then-branch / after an early return |
| `x != nil` / `x == nil` | non-nil inside the then-branch / after an early return |
| Upper bounds from conditions | none |
| `and`, `or`, `not` | no facts |
| Comparison with another variable (`i < n`) | no facts |
| `else` branch | no facts from the condition |
| `while cond` | the condition's facts hold in the body |
| C-style `for` | no induction facts |
| `for i, v in arr` | `i >= 0` only |
| `match` arms | no facts |
| Assignment `x = e` | replaces `x`'s fact with the fact for `e` |
| Index proof | needs a statically known length and an index interval within it |
| Float-to-integer cast | proved only for a finite, integral float literal in range |
| Fixed-width `+ - *` overflow | obligation defined but not checked (`_prove_integer_overflow` returns early) |

Status of the patterns below:

| Pattern | Current A7 |
| --- | --- |
| N1 constant equality | partial: `== 0` / `!= 0` only |
| N2 range comparison | partial: lower bounds from literals; no `or`, no runtime length |
| N3 optional | no: `?T` does not exist |
| N4 nullable reference | yes, for `ref T` with `nil` |
| N5 match arm | no |
| N6 loop induction | no |
| N7 conjunction | no |
| N8 disjunction | no |
| N9 early return | yes, when the then-block ends in `ret` |
| N10 assignment invalidates | yes |
| N11 mutation through a reference | not modeled; not verified |
| N12 nested narrowing | facts on different variables coexist, but the example needs N2, N3 and N5 |

---

## Subtypes as the mental model

The user proposed treating narrowed types as subtypes. Inside a narrowing
branch, the value's visible type is a stricter subtype of its declared type.

A slice of the hierarchy:

```
int                              ; the wide type, anything
 ├── int with range [a, b]      ; bounded subtype
 │    ├── int with range [1, b] ; non-zero positive subtype
 │    └── int with range [a, -1] ; non-zero negative subtype
 ├── int with non-zero          ; the union of non-zero ranges
 │    └── int with range [1, b] etc.
 └── int with value c           ; a literal subtype (range [c, c])
```

Narrowing moves down this lattice. After the check, `int` becomes
`int with non-zero`.

Why the model works:

- A narrower type meets more preconditions. `int with non-zero` meets
  division's non-zero divisor requirement.
- A function expecting `int` accepts `int with non-zero`. The subtype
  substitutes for the supertype (Liskov substitution).
- A result of type `int with non-zero` can be assigned to `int`. Widening is
  always safe.
- Getting the subtype from the supertype needs a proof: a narrowing pattern, a
  `match` on a guard, or a fallible constructor.

These subtypes exist only inside the type checker. The runtime representation
is the same `int`. Users cannot write `int with non-zero`; it lives in the
prover.

### Lattice shape for v1

With Level 2 precision (disjunctive intervals, see
[Precision and cost](#precision-and-cost)), the internal lattice is:

```
$T                                       ; the declared type
 │
 ├── $T with range [lo, hi]              ; single interval narrowing
 │
 ├── $T with non-zero                     ; specifically [-INF, -1] ∪ [1, +INF]
 │
 ├── $T with value c                      ; a single-value subtype (literal)
 │
 └── $T with disjunctive range            ; union of intervals
```

For optionals:

```
?T
 ├── ?T = none                            ; explicitly the none case
 └── ?T narrowed to T                     ; the some case, payload type
```

For tagged unions:

```
T = A | B | C
 ├── T narrowed to A
 ├── T narrowed to B
 └── T narrowed to C
```

These spellings are internal. Users see the declared type (`int`, `?int`, `T`)
and a diagnostic when narrowing is insufficient.

---

## What can be narrowed

| # | Category | Narrowed by |
| --- | --- | --- |
| 1 | Integer range | `<`, `<=`, `>`, `>=`, `==`, `!=` on `int`/`uint` |
| 2 | Float bounds | the same operators on `number` |
| 3 | Optionals | `== nil`, `!= nil`, or `match` |
| 4 | Tagged union variants | `match`, possibly discriminator checks |
| 5 | Reference nullability | `== nil` / `!= nil` on `?ref T` |

Categories 1 and 2 are the SPARK-tier additions. Categories 3–5 are standard in
modern systems languages.

The original list wrote `== nil` / `!= none` for category 5; the mixed spelling
is corrected to `nil` here. Category 2 needs NaN handling under L16.

---

## Recognized patterns

The examples below keep the original `int`/`uint`/`?T` types. They are
proposals unless labeled "Current A7".

### Pattern N1: equality or inequality with a constant

Proposed:

```a7
divide_or_default :: fn(a: int, b: int) int {
    if b == 0 {
        ret -1                          // narrowing not useful in this branch
    }
    // here `b: int with range [_, -1] ∪ [1, _]`  — non-zero
    ret a / b                            // OK
}
```

The check `b == 0` splits `int` into two subtypes. The code after the early
return uses the complement.

Current A7:

```a7
divide_or_default :: fn(a: i32, b: i32) i32 {
    if b == 0 {
        ret -1
    }
    ret a / b                   // accepted: early return proves b != 0
}
```

### Pattern N2: range comparison narrows an interval

Proposed:

```a7
safe_lookup :: fn(s: []int, i: int) ?int {
    if i < 0 or i >= s.length {
        ret nil
    }
    // here `i: int with range [0, s.length-1]` — provably in-bounds for `s`
    ret s[cast(uint, i)]                  // needs conversion since indices are uint
}
```

Under the `usize` index rule, this is a conversion to `usize`.

### Pattern N3: optional

Proposed:

```a7
maybe_double :: fn(x: ?int) ?int {
    if x == nil {
        ret nil
    }
    // here `x: int` — the option has been narrowed
    ret x * 2
}
```

### Pattern N4: nullable reference

Proposed:

```a7
print_name :: fn(user: ?ref User) {
    if user == nil {
        io.println("(no user)")
        ret
    }
    // here `user: ref User` — non-null
    io.println(user.name)
}
```

Current A7 has no `?ref T`. A `ref T` may be `nil`, and field access needs a
non-nil proof. The test suite checks this form with a local `new` value.

Current A7:

```a7
Box :: struct {
    value: i32
}

read_value :: fn(box: ref Box) i32 {
    if box == nil {
        ret 0
    }
    ret box.value               // accepted; the guard supplies a non-nil fact
}
```

Whether a `ref T` parameter needs this guard, or starts non-nil, was not
verified; the tested form uses a local `box := new Box`.

### Pattern N5: match arm

Proposed:

```a7
match result {
    case ok(v): {
        // here `v` has the inner ok-type
        process(v)
    }
    case err(e): {
        // here `e` has the inner err-type
        log(e)
    }
}
```

### Pattern N6: for-loop induction

Proposed:

```a7
sum :: fn(s: []int) int {
    total: int = 0
    for i := 0; i < s.length; i += 1 {
        // here `i: uint with range [0, s.length-1]`
        total = total + s[i]              // OK; i provably in bounds
    }
    ret total
}
```

The original comment gives `i` type `uint`, although `i := 0` does not say so.
Under the `usize` rule the loop variable would be `usize`.

### Pattern N7: conjunction

Proposed:

```a7
pick :: fn(x: int, y: int) int {
    if x > 0 and y > 0 {
        // here `x: int with range [1, _]` and `y: int with range [1, _]`
        ret x + y                         // both proved positive
    }
    ret 0
}
```

### Pattern N8: disjunction

Proposed:

```a7
lookup :: fn(opt: ?int, fallback: int) int {
    if opt == nil or fallback == 0 {
        ret -1
    }
    // here `opt: int` (nil case excluded) AND `fallback: int with non-zero`
    ret opt + fallback                    // both narrowed in this branch
}
```

`or` is harder than `and`. After the early return, `not (A or B)` holds, which
is `not A and not B`. The compiler must apply De Morgan's law.

### Pattern N9: early return narrows the rest of the block

Proposed:

```a7
process :: fn(s: ?string) int {
    if s == nil {
        ret -1
    }
    // here, AND in all subsequent code in this block, `s: string` — non-null
    ret cast(int, s.length)
}
```

The branch always exits, so the narrowing holds after the `if` block. This is
the most useful form in practice; users write it at the top of functions.

Current A7 supports this form. See the Current A7 examples for N1 and N4, and
the cast example in
[`conversions.md`](./conversions.md#what-the-compiler-does-today).

### Pattern N10: assignment invalidates

Proposed:

```a7
maybe_reset :: fn(b: ?int, force: bool) int {
    if b == nil {
        ret -1
    }
    // `b: int` here
    if force {
        b = nil                            // reassignment widens `b` back to `?int`
    }
    // here `b: ?int` again — narrowing invalidated by the reassignment
    ret b.unwrap_or(-1)                    // have to handle option again
}
```

This example assigns to a parameter. Under L6, argument bindings are
immutable, so a restatement would use a local variable.

Current A7 (per `a7/safety.py`: assignment replaces the variable's fact):

```a7
f :: fn(a: i32, b: i32, c: i32) i32 {
    d := b
    if d == 0 {
        ret 0
    }
    d = c                       // d's non-zero fact is replaced by c's (unknown)
    ret a / d                   // rejected: divisor may be zero
}
```

### Pattern N11: mutation through a reference invalidates

Proposed:

```a7
process :: fn(x: inout ?int) {
    if x == nil {
        ret
    }
    // here `x: int`
    helper(inout x)                        // helper may set x to nil
    // here `x: ?int` again — must re-narrow if needed
}
```

A function that can mutate `x` can rewrite it, so the narrowing is lost across
the call. `inout` is not approved syntax (L6). The current mutable-parameter
form is `ref T`; whether the safety pass resets facts across such a call was
not verified.

### Pattern N12: nested narrowings compose

Proposed:

```a7
divide_lookup :: fn(s: []?int, i: int, b: int) ?int {
    if i < 0 or i >= s.length {
        ret nil
    }
    if b == 0 {
        ret nil
    }
    // here `i: uint with range [0, s.length-1]` AND `b: int with non-zero`
    v := s[cast(uint, i)]                  // OK; i in-bounds
    match v {
        case nil: { ret nil }
        case some(n): {
            // here `n: int`
            ret some(n / b)                // OK; b non-zero
        }
    }
}
```

Three independent narrowings hold at once. The analysis tracks them as a
conjunction.

---

## What invalidates a narrowing

Narrowing belongs to program points, not bindings. The analysis carries it
forward through the control-flow graph. Some operations reset it.

| Operation | Effect on the narrowing of `x` |
| --- | --- |
| `x = new_value` | Resets; a new narrowing is inferred from `new_value` |
| `x += rhs`, `x *= rhs`, etc. | Resets (assignment with arithmetic) |
| Call `f(inout x)` | Resets; `f` may have changed `x` |
| Call `f(borrow x)` | No reset; `borrow` is read-only |
| Call `f(x)` for a `Copy` type | No reset; `x` was copied |
| Call `f(x)` for a non-`Copy` type | `x` is consumed; later use is already an error |
| Call `f(borrow other)` where `other` aliases `x` | No reset, if A7's parameter modes (Cluster CC) forbid aliasing of `borrow` parameters, which they do |
| Mutation through `*ptr` where the pointer is derived from `x` | Resets (heap mutation invalidates) |
| End of the narrowing block | Resets; narrowing is scoped |

The key payoff of parameter modes (Cluster CC) is that `borrow` does not
reset. A function that can only read its argument cannot invalidate the
caller's narrowings. That makes narrowing more useful in A7 than in languages
without such modes.

> **Note (2026-09-16):** the `inout`, `borrow` and `Copy` rows depend on
> proposed parameter modes (D.040, D.041, D.049) that were not accepted; see
> L6 and gate G2. The `*ptr` row uses dereference syntax that public A7 does not
> have. The rows remain as the aliasing requirements any accepted design must
> meet. Under L15–L22, memory is automatic and invisible, which may change how
> aliasing is expressed.

---

## Precision and cost

The analysis could run at one of four precision levels.

The coverage percentages below are the original authors' estimates. No
measurement backs them.

| Level | Tracks | Estimated coverage | Cost | Used in |
| --- | --- | --- | --- | --- |
| 1. Single intervals | `(lo, hi)` per binding | ~80% | trivial | — |
| 2. Disjunctive intervals | union of intervals per binding | ~95% | small | — |
| 3. Polyhedral / linear relations | linear relations between variables | ~99% | significant | CompCert, Polyspace, PIPS |
| 4. SMT solver | verification conditions sent to Z3 / CVC5 | ~100% of decidable cases | high | SPARK, F\*, Dafny, Liquid Haskell |

### Level 1: single-variable intervals

Each binding tracks an interval `(lo, hi)`.

- A comparison narrows: inside `if x < 5`, `x.hi = min(x.hi, 4)`.
- Arithmetic propagates: for `let y = x + 1`, `y.lo = x.lo + 1` and
  `y.hi = x.hi + 1`.
- Precision is lost on disjunctions and multi-variable relations.

Cost: a pair of integers per binding.

> **Note (2026-09-16):** under L5, `+` wraps, so `y.hi = x.hi + 1` holds only
> when the analysis also proves the sum does not wrap.

### Level 2: disjunctive intervals

Each binding tracks a union of intervals, so `int with non-zero` is
`[INT_MIN, -1] ∪ [1, INT_MAX]`.

- Handles `!=` cleanly.
- About twice the memory, similar run time.

Cost: small; one extra interval per binding when negation applies.

### Level 3: polyhedral or linear relations

Tracks linear relations between variables, such as `a ≤ b - 1`. After
`if a < b`, the analysis knows `a < b` itself, not just per-variable intervals.

Covers correlated-variable patterns. This is classic abstract interpretation.
Implementations use the PPL or APRON libraries.

### Level 4: SMT solver

Verification conditions go to Z3 or CVC5, which handle anything decidable.

Costs: solver calls per function, longer builds, and hard diagnostics. When the
solver says no, explaining why is difficult.

### Recommendation for v1

Level 2 (disjunctive intervals), plus fixed recognized patterns for cases the
general analysis misses: loop induction, `for` over `0..n`, `if x == none`, and
`match` arms.

Rationale:

- Level 2 catches the non-zero case from the user's example.
- The patterns cover what Levels 3 and 4 would catch in practice, without their
  compile-time cost.
- The implementation cost is bounded. The notes estimated a few hundred lines on
  the existing iterative-traversal infrastructure in
  `a7/passes/semantic_validator.py`. The current proof work lives in
  `a7/safety.py`.
- Levels 3 and 4 can be added later if real programs hit patterns that cannot be
  narrowed.

Today's `a7/safety.py` sits below Level 1: it tracks intervals but learns only
lower bounds from conditions (see
[What the compiler does today](#what-the-compiler-does-today)).

---

## How other languages do this

| Language | Mechanism | Notes |
| --- | --- | --- |
| **Kotlin** | Smart casts on nullable and class types | `if (x is Foo) x.bar` works. No integer-range narrowing. |
| **TypeScript** | Type guards and control-flow narrowing | Extensive: `typeof`, `in`, `instanceof`, user-defined guards. No range types. |
| **C# (NRT)** | Flow-sensitive null state | Tracks nullable annotations through control flow. Similar in scope to Kotlin. |
| **Rust** | `match` exhaustiveness, `if let` | Narrowing through pattern matching. No integer-range narrowing. The borrow checker is separate. |
| **Swift** | `if let`, `guard let`, `case let` | Similar to Rust. |
| **Zig** | `if (x) \|val\|` for optionals | Same. No range tracking. |
| **SPARK** | Subtype constraints plus SMT | Full range tracking through subtypes; gnatprove discharges verification conditions. |
| **Liquid Haskell** | Refinement types plus SMT | Per-binding refinement predicates, discharged by SMT. |
| **F\*** / **Dafny** | Dependent or refinement types plus SMT | Same approach. |

A7's proposal combines two things: integer-range narrowing built into the
language semantics without SMT, and narrowing on optionals and sum types as in
Kotlin and TypeScript. The accepted range patterns are syntactic, so A7 needs no
SMT solver. The analysis is predictable and the diagnostics are direct.

> **Audit note (2026-09-16, from language knowledge; not re-verified):** the
> original text called this combination unique. Wuffs is a close precedent: it
> proves bounds and arithmetic safety at compile time from refined integer
> types and explicit facts, without an SMT solver. Optimizing compilers also run
> value-range propagation to remove checks, but as an optimization, not as a
> language guarantee.

---

## What v1 should support

Each item is a recognized pattern in the analysis.

### Required (drives the safety contract)

1. **Constant equality and inequality:** `x == c`, `x != c` with a
   compile-time constant `c` narrow both branches.
2. **Constant ordering:** `x < c`, `x <= c`, `x > c`, `x >= c` narrow the
   interval in both branches.
3. **Variable ordering:** `x < y`, `x <= y` narrow the correlation. This is
   Level 3 territory; v1 may be conservative.
4. **Optionals:** `x == none`, `x != none` for `x: ?T`.
5. **Tagged unions:** `match` arm bindings.
6. **For-loop induction:** in `for i in lo..hi`, `i` is in `lo..hi-1` in the
   body.
7. **Range membership:** `if i in r`, where `r` is a known range, narrows.
8. **Negation:** `if not p` narrows with the else-side of `p`.
9. **Conjunction:** `if a and b` applies both conditions in the then-branch.
10. **Disjunction with De Morgan:** `if a or b` applies `not a and not b` in the
    else-branch, the more useful side.
11. **Early-return propagation:** after `if guard { ret ... }`, the rest of the
    block is narrowed by `not guard`.

The original list used `none` for items 4 and `if guard: return ... end` for
item 11. Current A7 uses `nil`, `ret` and braces. The `for i in lo..hi` range
syntax in item 6 is not a current A7 form.

Proposed (items 3, 6 and 7; the `in` forms are not current syntax):

```a7
total :: fn(s: []i32, n: usize) i32 {
    sum: i32 = 0
    for i in 0..s.len {         // item 6: i in [0, s.len - 1] in the body
        sum += s[i]
    }
    if n in 0..s.len {          // item 7: n in [0, s.len - 1]
        sum += s[n]
    }
    j: usize = 0
    if j < s.len {              // item 3: relation j < s.len, not a constant bound
        sum += s[j]
    }
    ret sum
}
```

Proposed (item 8, negation):

```a7
clamp_index :: fn(i: usize, n: usize) usize {
    if not (i < n) {
        ret 0                   // narrowing of `not (i < n)` in this branch: i >= n
    }
    ret i                       // after the early return: i < n
}
```

### Floats under IEEE 754

> **Note (2026-09-16):** under L16, NaN compares false with everything. For a
> float `f`, `not (f < 0)` does not imply `f >= 0`. Items 2, 8 and 10 are sound
> for integers but not for floats unless the lattice has a separate NaN element
> and the guards rule NaN out. The same flaw affects `float_to_index` in
> [`conversions.md`](./conversions.md). Float sub-decisions are in gate G1.

Proposed (sound float guard):

```a7
to_ratio :: fn(f: f64) f64 {
    if f.is_nan() or f < 0.0 {
        ret 0.0
    }
    // here f is not NaN and f >= 0.0
    ret f
}
```

The `is_nan()` method name is illustrative.

### Nice to have (maybe v2)

12. **Cross-variable correlation:** `if a == b` narrows `a` to `b`'s value and
    back, in the then-branch.
13. **Purity-based narrowing:** after checking `pure_fn(x) > 0`, later calls
    return the same result.
14. **Multi-variable polyhedra:** full Level 3 analysis.

### Out of scope for v1

15. SMT-backed verification (Level 4).
16. User-written refinement predicates.
17. Cross-procedural narrowing without a `pure` annotation.

---

## What the user sees

The user never names a narrowed subtype. They write `int`, and the compiler
reads it as `int with range ...` at each program point. Narrowing stays hidden
until the compiler cannot prove something. The diagnostic then shows the
current narrowed type and the required one.

```
error: division requires non-zero divisor
  --> example.a7:7:14
   |
 7 |     ret a / b
   |             ^ `b` may be zero here
   |
note: `b`'s type at this point is `int` (full range)
note: to discharge the obligation, add a guard:
   |
 6 |     if b == 0 {
 7 |         ret -1
 8 |     }
 9 |     ret a / b
   |
```

Diagnostics are the user interface of narrowing, so they must be excellent.
Phase D §7 (Diagnostics) owns this.

This is a mockup. The current compiler's message is shorter ("divisor may be
zero").

---

## Should A7 have `assert`?

An `assert` keyword would state an invariant that the compiler must prove.

Proposed:

```a7
process :: fn(s: []int) {
    assert s.length > 0
    // from here on, `s.length: uint with range [1, _]`
    first := s[0]                 // OK; index 0 is in [0, s.length-1] = [0, _]
}
```

Two forms:

| Form | Behavior | Status in these notes |
| --- | --- | --- |
| Compile-time `assert` | compiler proves the condition; compile error if it cannot; no runtime code | allowed |
| Runtime `assert` | runtime check that traps on failure | forbidden by the contract |

If A7 has `assert`, it must be the compile-time form. Users get a verification
tool and the language gains no runtime traps.

The alternative is no `assert`; users write early-return guards. Both reach the
same result.

Proposed:

```a7
// with assert
assert s.length > 0
first := s[0]

// without assert
if s.length == 0 {
    ret
}
first := s[0]
```

The early-return form states what happens when `s.length == 0`. The `assert`
form is shorter but says "this cannot happen" and shifts the burden to the
compiler.

Recommendation: no `assert` in v1. Early-return guards cover every case and are
more honest. `assert` can come later as a convenience.

---

## Open questions for Cluster CD

1. **Lattice level:** confirm Level 2 (disjunctive intervals) plus recognized
   patterns.
2. **Disjunctions:** De Morgan only, or richer handling?
3. **Cross-variable correlations:** any in v1?
4. **`pure` annotation:** yes, no or deferred?
5. **`assert` keyword:** yes, no or deferred?
6. **Call invalidation:** when does `f(borrow x)` invalidate narrowings of values
   reachable from `x`?
7. **Loop-carried narrowings:** if an iteration could invalidate a narrowing from
   the loop header, how is the conflict reported?
8. **Diagnostic format:** how does the compiler explain "narrowing required, not
   yet established"?
9. **Arithmetic refinement:** `let y = x + 1` propagates `x`'s range to `y`. Does
   `let y = x.checked_add(1)?` also propagate, matching the overflow contract?
10. **Negation:** confirm that `if not (x == 0)` narrows like `if x != 0`.
11. **Guards across statements:** should `let cond = x != 0; if cond: ...`
    narrow `x` in the branch? Yes if `cond` is immutable and used right after
    its definition. Needs confirmation.

> **Note (2026-09-16):** question 6 assumes `borrow` (not accepted). Question 9
> assumed non-overflowing `+`; under L5 `x + 1` wraps, so range propagation
> needs a no-wrap proof. A new question follows from L16: how do float
> narrowings represent NaN?

---

## Links to other decisions

The notes describe narrowing as the one mechanism behind most flow-dependent
decisions:

| Decision | Topic | How narrowing applies |
| --- | --- | --- |
| D.003 | Integer arithmetic specializes | uses range tracking |
| D.022 | Division by zero is a compile error | discharged by narrowing |
| D.023 | Out-of-bounds index is a compile error | discharged by narrowing |
| D.014 | Smart narrowing through `if x == none` | direct application |
| D.020 | Compiler-internal range analysis | the infrastructure |

> **Note (2026-09-16):** D.003 is superseded by L4/L5. D.020 and D.022 are
> written for `int`/`number` and must be restated for explicit widths (L4,
> gate G3).

Cluster CD was to fix the analysis level, the recognized patterns and the
diagnostic format. It also takes definite assignment, which uses the same
control-flow graph, and any open questions from this file.

---

## Plan for the spec (Phase D)

Phase D was to document narrowing as one spec section, "Narrowing semantics",
covering:

1. the subtype lattice in formal terms;
2. the recognized patterns (the 11 required in v1);
3. the invalidation rules;
4. the public contract users can rely on;
5. example diagnostics.

The implementation was planned as one pass in
`a7/passes/semantic_validator.py` or a new sibling pass, reusing the
iterative-traversal infrastructure of the recursion and exhaustive-match
checks. Today the proof facts live in `a7/safety.py`.
