# Flow-Sensitive Narrowing — Research Notes for Cluster CD

> Research input for Phase C Cluster CD (flow analysis decisions).
> Not itself a decision document — explores the design space of
> "after this check, the value has a narrower type."

## The big idea

A variable's **type** is what's known about it statically at a
particular program point. Most languages give each binding a
single type that holds everywhere the binding is in scope.
**Flow-sensitive narrowing** says: the type can be *different*
on different sides of a branch.

Concrete example — the user's framing:

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

In words: **the type system treats `b` inside `if b != 0` as a
strictly narrower subtype of `int` — specifically, "any `int`
*except* zero."** That refined type satisfies division's
precondition.

This same mechanism handles:

- **Nullability**: inside `if x == nil`, `x` is `nil`; outside,
  `x` is the unwrapped `T`.
- **Bounds**: inside `if i < s.length`, `i` is bounded by
  `s.length`.
- **Tagged unions**: inside `case some(v):`, the binding `v`
  has the inner type, not the outer `Option<T>`.
- **Equality**: inside `if x == 5`, `x` is the literal 5.
- **Recursion-banned function calls** the user has already
  proven safe.

Narrowing is **the single mechanism that powers the entire
zero-runtime-error contract for runtime-dependent values.** Every
SPARK-tier safety obligation (division by non-zero, index in
bounds, no overflow, etc.) is discharged by reading the narrowed
type at the use site.

---

## Subtypes as the mental model

The user proposed framing this as **subtypes**. That's a clean
mental model. Inside a narrowing branch, the value's *visible
type* becomes a stricter subtype of its declared type.

Hierarchy (a slice):

```
int                              ; the wide type, anything
 ├── int with range [a, b]      ; bounded subtype
 │    ├── int with range [1, b] ; non-zero positive subtype
 │    └── int with range [a, -1] ; non-zero negative subtype
 ├── int with non-zero          ; the union of non-zero ranges
 │    └── int with range [1, b] etc.
 └── int with value c           ; a literal subtype (range [c, c])
```

The narrowing rules are subtype-relation moves. Going from
`int` (declared) to `int with non-zero` (after the check) is
**moving down the subtype lattice**.

**Why subtypes work as the mental model:**

- The narrower type satisfies *more* preconditions (e.g.,
  `int with non-zero` satisfies division's "divisor non-zero"
  precondition).
- A function expecting `int` accepts `int with non-zero` (the
  subtype substitutes for the supertype — Liskov substitution).
- A function returning `int with non-zero` can be assigned to
  `int` (widening upcast — always safe).
- Constructing the subtype from the supertype requires a proof
  (either a narrowing pattern, or `match` on a guard, or a
  fallible constructor).

These are **subtypes only in the type checker's view** — the
runtime representation is identical (`int` everywhere). The
user-facing language doesn't have a literal `int with non-zero`
type to write down. It's all in the prover.

---

## What can be narrowed

Five categories:

1. **Integer range narrowing** — by `<`, `<=`, `>`, `>=`, `==`,
   `!=` on `int`/`uint`.
2. **Float bound narrowing** — same operators on `number`.
3. **Optional narrowing** — by `== nil`, `!= nil`, or via
   `match`.
4. **Tagged union variant narrowing** — via `match` and possibly
   via discriminator checks.
5. **Reference nullability narrowing** — via `== nil` / `!=
   none` on `?ref T`.

(1) and (2) are the SPARK-tier additions; (3), (4), (5) are
standard for modern systems languages.

---

## Recognised patterns (concrete examples)

### Pattern N1: equality / inequality with a constant

```a7
divide_or_default :: fn(a: int, b: int) int {
    if b == 0 {
        ret -1                          // narrowing not useful in this branch
    }
    // here `b: int with range [_, -1] ∪ [1, _]`  — non-zero
    ret a / b                            // OK
}
```

The check `b == 0` partitions `int` into two subtypes; the **else
branch** uses the complementary one.

### Pattern N2: range comparison narrows interval

```a7
safe_lookup :: fn(s: []int, i: int) ?int {
    if i < 0 or i >= s.length {
        ret nil
    }
    // here `i: int with range [0, s.length-1]` — provably in-bounds for `s`
    ret s[cast(uint, i)]                  // needs conversion since indices are uint
}
```

### Pattern N3: smart-narrow on optional

```a7
maybe_double :: fn(x: ?int) ?int {
    if x == nil {
        ret nil
    }
    // here `x: int` — the option has been narrowed
    ret x * 2
}
```

### Pattern N4: smart-narrow on `?ref T`

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

### Pattern N5: match-arm narrowing

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

### Pattern N7: chained guards (conjunction)

```a7
pick :: fn(x: int, y: int) int {
    if x > 0 and y > 0 {
        // here `x: int with range [1, _]` and `y: int with range [1, _]`
        ret x + y                         // both proved positive
    }
    ret 0
}
```

### Pattern N8: disjunction (more subtle)

```a7
lookup :: fn(opt: ?int, fallback: int) int {
    if opt == nil or fallback == 0 {
        ret -1
    }
    // here `opt: int` (nil case excluded) AND `fallback: int with non-zero`
    ret opt + fallback                    // both narrowed in this branch
}
```

The "or" form is harder than "and" because the negation of
`A or B` is `not A and not B`, which is what holds in the else
branch. The compiler must handle the De Morgan'd form.

### Pattern N9: early return reshapes the trailing block

```a7
process :: fn(s: ?string) int {
    if s == nil {
        ret -1
    }
    // here, AND in all subsequent code in this block, `s: string` — non-null
    ret cast(int, s.length)
}
```

The narrowing **propagates beyond the immediate `if` block**
because the branch unconditionally exits. This is the most useful
form in practice; it's exactly the pattern users write at function
tops.

### Pattern N10: assignment invalidates

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

### Pattern N11: mutation through reference invalidates

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

A function taking `x` mutably can rewrite it; the narrowing is
lost across that call.

### Pattern N12: nested narrowing composes

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

Three independent narrowings hold simultaneously. The flow
analysis tracks them as conjunction.

---

## What invalidates a narrowing

Narrowing is **a property of program points**, not of bindings.
The analysis tracks it forward through the CFG; certain
operations reset it:

| Operation | Effect on narrowing of `x` |
| --- | --- |
| `x = new_value` | Resets; new narrowing inferred from `new_value` |
| `x += rhs`, `x *= rhs`, etc. | Resets (assignment with arithmetic) |
| Call `f(inout x)` | Resets — `f` may have changed `x` |
| Call `f(borrow x)` | **No reset** — `borrow` is read-only |
| Call `f(x)` for a `Copy` type | No reset — `x` was copied |
| Call `f(x)` for a non-`Copy` type | `x` is consumed; further use is an error anyway |
| Call `f(borrow other)` where `other` aliases `x` | **No reset** if A7's parameter modes (Cluster CC) forbid aliasing of `borrow` parameters — which they do |
| Mutation through `*ptr` where the pointer is derived from `x` | Resets (heap mutation invalidates) |
| Reaching the end of the narrowing block | Resets — narrowing is scoped |

The "borrow doesn't reset" rule is the key payoff of A7's
parameter modes (Cluster CC): a function that can only *read*
its argument can't invalidate the caller's narrowings. This
makes narrowing far more useful in A7 than in languages without
the discipline.

---

## The trade-off ladder — precision vs. compiler cost

There are at least four levels of precision the analysis could
operate at:

### Level 1 — Single-variable intervals (cheapest)

Each binding tracks `(lo, hi)` — an interval. Operations:

- Comparison narrows: `if x < 5` ⇒ inside, `x.hi = min(x.hi, 4)`.
- Arithmetic propagates: `let y = x + 1` ⇒ `y.lo = x.lo + 1`,
  `y.hi = x.hi + 1`.
- Loses precision on disjunctions and on multi-variable
  relations.

Covers: ~80 % of typical cases.
Cost: trivial (a pair of integers per binding).

### Level 2 — Disjunctive intervals (small cost)

Each binding tracks a *union* of intervals. Lets the analysis
express `int with non-zero` as `[INT_MIN, -1] ∪ [1, INT_MAX]`.

- Handles `!=` cleanly.
- 2× memory; comparable runtime.

Covers: ~95 % of typical cases.
Cost: small; one extra interval per binding when negation
applies.

### Level 3 — Polyhedral / linear relations (medium cost)

Tracks linear relations between variables (e.g., `a ≤ b - 1`).
Lets the analysis express "after the check `if a < b`, `a < b`
holds" — not just per-variable intervals.

Covers: ~99 % including correlated-variable patterns.
Cost: significant; classic abstract-interpretation territory.
Used in CompCert, Polyspace, PIPS. Implementation: PPL or apron
libraries.

### Level 4 — SMT solver (high cost)

Hand off verification conditions to Z3 / CVC5. Covers anything
decidable.

Covers: ~100 % of decidable cases.
Cost: SMT calls per function; build-time impact; diagnostic
challenges (when the solver says no, *why* is hard to explain).
Used in SPARK, F\*, Dafny, Liquid Haskell.

### Recommendation for A7 v1

**Level 2 (disjunctive intervals)**, plus a hardcoded set of
recognised patterns for what the analysis can't do generally
(loop induction, `for` over `0..n`, `if x == none` narrowing,
`match`-arm narrowing).

Rationale:

- Level 2 catches the "non-zero" case the user just described.
- The pattern set covers what Level 3/4 would catch in practice
  without their compile-time cost.
- Implementation cost is bounded; the analysis fits in a few
  hundred lines on top of the existing iterative-traversal
  infrastructure in `a7/passes/semantic_validator.py`.
- Level 3/4 can be retrofitted later if real programs trip on
  un-narrowable patterns.

---

## How other languages do this

| Language | Mechanism | Notes |
| --- | --- | --- |
| **Kotlin** | Smart casts on nullables and class types | `if (x is Foo) x.bar` works. No integer-range narrowing. |
| **TypeScript** | Type guards and control-flow narrowing | Extensive; the type system is intentionally narrowing-heavy. `typeof`, `in`, `instanceof`, user-defined guards. No range types. |
| **C# (NRT)** | Flow-sensitive null state | Tracks nullable annotations through control flow. Similar in scope to Kotlin's. |
| **Rust** | `match` exhaustiveness, `if let` | Narrowing through pattern matching; **no integer-range narrowing**. The borrow checker is separate. |
| **Swift** | `if let`, `guard let`, `case let` | Similar to Rust. |
| **Zig** | `if (x) \|val\|` for optionals | Same. No range tracking. |
| **SPARK** | Subtype constraints + SMT | Full range tracking via subtypes; verification conditions discharged by gnatprove. |
| **Liquid Haskell** | Refinement types + SMT | Per-binding refinement predicates; SMT-discharged. |
| **F\*** / **Dafny** | Dependent / refinement types + SMT | Same approach. |

**A7's proposal lands in a unique spot:** integer-range narrowing
*built into the language semantics* (not via SMT), plus
narrowing on optionals and sum types as in Kotlin/TS. The
specifics matter: A7 doesn't need an SMT solver because the
range patterns it accepts are syntactic — the analysis is
predictable, the diagnostics are direct.

---

## What A7 v1 should support

A concrete list. Each is a recognised pattern in the analysis.

### Required (drives the safety contract)

1. **Constant equality / inequality**: `x == c`, `x != c` where
   `c` is a compile-time constant — narrows in both branches.
2. **Constant ordering**: `x < c`, `x <= c`, `x > c`, `x >= c`
   — narrows interval in both branches.
3. **Variable ordering**: `x < y`, `x <= y` — narrows the
   correlation (Level 3 territory; v1 implementation can be
   conservative).
4. **Optional narrowing**: `x == none`, `x != none` for `x: ?T`.
5. **Tagged-union narrowing**: `match` arm bindings.
6. **For-loop induction**: `for i in lo..hi: body` — `i:
   {lo..hi-1}` in body.
7. **Range membership**: `if i in r` where `r` is a known range
   — narrows.
8. **Negation**: `if not p` narrows the else of `p`'s narrowing.
9. **Conjunction**: `if a and b` narrows both `a` and `b`'s
   conditions in the then-branch.
10. **Disjunction with De Morgan**: `if a or b` narrows
    `not a and not b` in the else-branch (the more useful side).
11. **Early-return propagation**: `if guard: return ... end`
    narrows in the rest of the block based on `not guard`.

### Nice-to-have (v2 maybe)

12. **Cross-variable correlations**: `if a == b` narrows `a` to
    the value of `b` and vice versa in the then-branch.
13. **Function purity-based narrowing**: if `pure_fn(x) > 0`
    after the check, future calls return the same result.
14. **Multi-variable polyhedral**: full Level 3 analysis.

### Out of scope for v1

15. SMT-backed verification (Level 4).
16. User-written refinement predicates.
17. Cross-procedural narrowing without `pure` annotation.

---

## The "what does the user see" view

The user **never names a narrowed subtype**. They write `int`;
the compiler reads it as `int with range ...` at each program
point. The narrowing is invisible until the user writes
something the compiler can't prove — at which point the
diagnostic shows the *current* narrowed type plus the
*required* one:

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

Diagnostics are *the* user-visible interface of the narrowing
system. They have to be excellent. Phase D §7 (Diagnostics) is
where this lives.

---

## Verification primitive: should A7 have `assert`?

A `assert` keyword would let the user state an invariant the
compiler must prove:

```a7
process :: fn(s: []int) {
    assert s.length > 0
    // from here on, `s.length: uint with range [1, _]`
    first := s[0]                 // OK; index 0 is in [0, s.length-1] = [0, _]
}
```

Two flavours:

- **Compile-time `assert`**: the compiler proves the condition.
  Compile error if it can't. **No runtime code emitted.**
- **Runtime `assert`**: a runtime check that traps on failure.
  **Forbidden by the contract.**

If A7 has `assert`, it must be the compile-time form. The user
gets a verification tool; the language gets no runtime traps.

Alternative: no `assert` keyword; the user uses early-return
guards instead. Both achieve the same end:

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

The early-return form is **more explicit about the failure case**
(it says what happens when `s.length == 0`). The `assert` form
is **more concise** but says "trust me, this can't happen" —
shifting the verification burden onto the compiler.

**Recommendation**: skip `assert` in v1. The early-return guard
form covers all cases and is more honest. Adding `assert` is a
*post-v1* convenience.

---

## Open questions for Cluster CD

When Cluster CD's decisions are drafted, the analyses below need
explicit answers:

1. **Lattice level**: confirm Level 2 (disjunctive intervals) +
   recognised patterns.
2. **Disjunction handling**: De Morgan's only, or richer?
3. **Cross-variable correlations**: any in v1?
4. **`pure` annotation**: yes/no/deferred.
5. **`assert` keyword**: yes/no/deferred.
6. **Method-call invalidation rules**: when does `f(borrow x)`
   invalidate narrowings of values reachable from `x`?
7. **Loop-carried narrowings**: when a loop iteration could
   invalidate a narrowing established in the loop header, how is
   the conflict reported?
8. **Diagnostic format**: how exactly does the compiler explain
   "narrowing required; not yet established"?
9. **Refining through arithmetic**: `let y = x + 1` propagates
   `x`'s range to `y` — yes; does `let y = x.checked_add(1)?`
   also propagate (matching the contract on overflow)?
10. **Negation as a primitive**: `if not (x == 0)` should
    narrow same as `if x != 0` — confirm.
11. **Compound guards across statements**: should
    `let cond = x != 0; if cond: ...` narrow `x` inside the
    branch? If `cond` is an immutable binding immediately after
    its definition, yes. Worth confirming.

---

## Cross-cutting impact

The narrowing system **is the single mechanism** behind almost
every Cluster decision that depends on flow:

- **D.003** (integer arithmetic specialises) — uses range
  tracking.
- **D.022** (division-by-zero compile error) — discharged by
  narrowing.
- **D.023** (out-of-bounds compile error) — discharged by
  narrowing.
- **D.014** (smart-narrow through `if x == none:`) — direct
  application.
- **D.020** (compiler-internal range analysis) — the
  infrastructure.

Cluster CD will lock in the analysis level, the exact set of
recognised patterns, and the diagnostic format. That cluster
also picks up definite-assignment (same CFG) and any open
questions from this exploration.

---

## Subtype lattice — concrete shape for v1

Given Level 2 (disjunctive intervals), the user-invisible
subtype lattice is:

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

These are **internal types** in the compiler's view. The user
never sees these spellings; they see the declared type
(`int`, `?int`, `T`) and the diagnostic when a narrowing is
insufficient.

---

## What this means for the spec (Phase D)

Phase D will document this as a single section of the language
spec: **"Narrowing semantics"**. The section will:

1. Define the subtype lattice in formal terms.
2. Enumerate the recognised patterns (the 11 in v1).
3. Specify the invalidation rules.
4. Describe what the user can rely on (the public contract).
5. Provide example diagnostics.

Implementation-wise, this is a single pass in
`a7/passes/semantic_validator.py` (or a new sibling pass)
running over the same iterative-traversal infrastructure
already used for the recursion check and exhaustive-match check.
