# Compile-Time Knowledge — The Principle Behind A7's Safety

> Research notes formalising the principle the user stated:
> "the cast is allowed because the compiler knows the number."
>
> This document explains why A7's entire safety contract reduces
> to a single idea: **the compiler permits an operation precisely
> when it has accumulated enough static knowledge about the
> operand values to discharge the operation's preconditions.**
> Companion to `narrowing.md` and `conversions.md`.

## The principle in one sentence

> **`cast(T, x)` (and `a / b`, `s[i]`, etc.) is permitted at a
> particular program point if and only if the compiler's
> accumulated static knowledge about the operand values is
> sufficient to discharge the operation's preconditions at that
> point. The cast is allowed precisely because the compiler
> knows the value.**

The corollary, equally important:

> **If the compiler does not have the required knowledge, the
> program does not compile.** No runtime check is inserted; no
> `?T` is silently returned; no panic path is generated. The
> user fixes the code at compile time by adding a guard, a
> match, or a narrower declared type.

## Why this matters

This principle is the unifying thread behind every decision in
Clusters CA, CB, and the upcoming CD. Once you internalise it,
every other safety rule in A7 follows mechanically:

- **`if x >= 0` makes `cast(uint, x)` compile**: because the
  guard adds the knowledge `x >= 0` to the compiler's view of
  `x`, satisfying `cast(uint, ...)`'s precondition.
- **`if i < s.length` makes `s[i]` compile**: same mechanism;
  the guard adds the bounds knowledge.
- **`if b != 0` makes `a / b` compile**: the guard adds the
  non-zero knowledge.
- **`if x == nil` followed by `ret` makes `x` usable as a
  non-null value below**: the early-return invalidates the
  nil case; what remains is the non-null knowledge.
- **`match` on a tagged union narrows the binding per arm**:
  the match arm adds the variant knowledge.

The user writes plain control flow — `if`, `match`, early
returns. The compiler turns each control-flow statement into a
piece of knowledge added (or removed) from the surrounding
context. When that knowledge is enough to discharge a
precondition, the operation compiles. When it isn't, the
operation doesn't compile.

This is **not** a metaphor for what the compiler does — it is a
faithful description.

## The mental model: type as accumulated knowledge

A *type* in A7's view is **the compiler's accumulated knowledge
about a value at a program point**. A declared type like `int`
is the initial knowledge: "this value is a mathematical integer
of unknown range." A narrowed type like `int with range [0,
s.length-1]` is the knowledge after a guard.

Knowledge flows through the program:

| Construct | Knowledge effect |
| --- | --- |
| Declaration with literal: `x: int = 5` | `x: int with value 5` |
| Reading an opaque function parameter: `f :: fn(x: int)` | `x: int` (no further knowledge) |
| `if x < 5 { ... }` (inside) | `x: int with range [_, 4]` |
| `if x < 5 { ... }` (else / after) | `x: int with range [5, _]` |
| `if y != 0 { ... }` (inside) | `y: int with non-zero` |
| `for i := 0; i < n; i += 1 { ... }` (body) | `i: uint with range [0, n-1]` |
| `match opt { case some(v): { ... } }` (arm) | `v: T` (unwrapped from `?T`) |
| `x = new_value` | `x`'s knowledge reset to whatever `new_value` provides |
| `f(inout x)` | `x`'s knowledge reset — `f` may have changed it |
| `f(borrow x)` | **no reset** — `borrow` is read-only |

Every operation in A7 is annotated with the knowledge it
**requires** (its precondition). At each call site, the
compiler compares required knowledge to available knowledge. If
available ⊇ required, the operation compiles; otherwise it
doesn't.

## Three knowledge tiers for any operation

For any A7 operation, the call-site knowledge falls into one of
three tiers:

### Tier 1 — Sufficient knowledge: bare emission

The compiler has accumulated enough static knowledge to
discharge the precondition. The operation compiles. The emitted
Zig has **no runtime check**.

```a7
x: int = 42                              // x: int with value 42
y: uint = cast(uint, x)                  // precondition x >= 0 trivially holds;
                                          // emits @intCast(u64, 42) — no check
```

### Tier 2 — Insufficient but recoverable: compile error with fix-it

The compiler doesn't have enough knowledge, **but** there's a
guard the user can add that would discharge the precondition.
The compiler emits a compile error with a fix-it suggestion.

```a7
process :: fn(x: int) uint {
    ret cast(uint, x)                    // compile error
}
```

```
error: cast(uint, int) requires `x >= 0`
  --> example.a7:2:17
   |
 2 |     ret cast(uint, x)
   |                    ^ `x` may be negative here
   |
help: add a guard so the prover can discharge the precondition:
   |
 1 | process :: fn(x: int) uint {
 2 |     if x < 0 { ret 0 }
 3 |     ret cast(uint, x)
 4 | }
```

The fix-it tells the user exactly what knowledge the compiler
needs. The user adds the guard; on the next compile, the
knowledge is present; the cast compiles.

### Tier 3 — Insufficient and irrecoverable: hard compile error

Some preconditions can never be discharged because the source
type contains no information that could satisfy them. These are
hard errors with no fix-it pattern — the user must change the
algorithm.

```a7
p: ref T = cast(ref T, 0xDEADBEEFu)      // hard compile error
                                          // no guard can make an integer
                                          // into a valid pointer
```

```
error: cast(ref T, uint) is forbidden
  --> example.a7:1:16
   |
 1 |     p: ref T = cast(ref T, 0xDEADBEEFu)
   |                ^^^^^^^^^^^^^^^^^^^^^^^^
   |
note: there is no guard that can transform an integer into a
      valid reference; this is the audit-flagged unsafe cast
      (`07-language-review.md` §1.2). To obtain a `ref T`, allocate
      one with `new T` or pass it as a parameter.
```

## Worked examples — the knowledge for each cast

For every conversion `cast(T, x)`, the table lists what the
compiler needs to know about `x` to permit the cast, and what
fix-it suggests when the knowledge is missing.

| Cast | Required knowledge | Fix-it when missing |
| --- | --- | --- |
| `cast(int, x: int)` | none — identity | n/a |
| `cast(int, x: uint)` | none — lossless | n/a |
| `cast(int, n: number)` | none — defaults to trunc | n/a |
| `cast(uint, x: int)` | `x >= 0` | `if x < 0: ... end` or `if x >= 0: cast(uint, x) ... end` |
| `cast(uint, n: number)` | `n >= 0` (and trunc-mode) | `if n < 0: ... end` |
| `cast(number, x: int)` | none — embedding | n/a |
| `cast(number, x: uint)` | none — embedding | n/a |
| `cast(string, x)` | none — format always succeeds | n/a |
| `cast(int, s: string)` | none — but result is `?int` (data-dependent) | match on result |
| `cast(uint, s: string)` | none — result is `?uint` | match |
| `cast([N]T, s: []T)` | `s.length == N` | `if s.length == N: ... end` |
| `cast(EnumT, i: int)` | `i` is a valid discriminant of `EnumT` | `match i { case <valid_discs>: ... case _: ... end }` |
| `cast(i32, x: int)` | `x in [INT32_MIN, INT32_MAX]` | range guard |
| `cast(int, x: i32)` | none — widening | n/a |
| `cast(ref T, x: uint)` | **irrecoverable** | rewrite — use `new` or pass as parameter |
| `cast(uint, p: ref T)` | **irrecoverable** | use `e.discriminant()` analog or rewrite |
| `cast(EnumA, x: EnumB)` | **irrecoverable** | go through discriminants explicitly |

The first column is the **precondition**; the second is the
**knowledge needed** to satisfy it; the third is the
**guard pattern** that would provide that knowledge.

## Knowledge from data-dependent sources

Some values arrive in the program from sources the compiler
fundamentally cannot see into:

- Strings read from stdin or files.
- Bytes from a network socket.
- Return values from FFI.
- The result of an allocation (success or OOM).

For these, the compiler has **no static knowledge** of the value.
It cannot prove `x >= 0` or `i < s.length` or "this discriminant
is valid." So the operation's return type carries the failure
possibility explicitly:

```a7
raw: ?string = read_line()               // ?string — could be nil (EOF, error)
match raw {
    case nil: { ret 0 }
    case some(s): {
        // here `s: string`, but its content is still opaque
        n: ?int = cast(int, s)            // ?int — parse may fail
        match n {
            case nil: { ret 0 }
            case some(v): { ret v }
        }
    }
}
```

These are the **data-dependent** operations from D.025. They are
the only operations that return `?T` or `Result<T, E>` in A7
because they're the only operations where the compiler
genuinely cannot acquire the knowledge at compile time.

## Theoretical foundations

This principle isn't novel — A7 is applying ideas with deep
roots:

### Abstract interpretation (Patrick Cousot, 1977 onwards)

Cousot's framework of **abstract interpretation** says: every
static analysis is an abstraction of a program's concrete
runtime behaviour. The abstract values are "what the analyser
knows" about the concrete values. A type system is a particular
abstract interpretation where the abstract values are types.
([Wikipedia: Abstract interpretation](https://en.wikipedia.org/wiki/Abstract_interpretation);
[Cousot, *Types as Abstract Interpretations*](https://www.irif.fr/~mellies/mpri/mpri-ens/articles/cousot-types-as-abstract-interpretations.pdf))

A7's narrowing system is a specific abstract interpretation:
the abstract domain is "disjunctive intervals over integers,
plus optional-narrowing flags, plus tagged-union variant tags."
The "knowledge" the compiler accumulates is the abstract value
at each program point.

### Epistemic type theory (modal logic, S4)

In modal logic, the operator `□A` means "it is known that A."
Several authors have explored type systems with modal
type-formers: `□T` is "a value of type T whose value is known
at compile time." Calls a function `□(a → b) → (□a → □b)` —
if you know the function and know the argument, you know the
result. ([Sigfpe on S4 and partial evaluation](http://blog.sigfpe.com/2006/04/s4-and-partial-evaluation.html))

A7's compile-time knowledge framing is a practical (non-formal)
adoption of this view: each operation's precondition is a modal
formula the compiler must prove at compile time. The fix-its
are the user's way of providing the missing modal evidence.

### Refinement types (Liquid Haskell, F\*, ATS)

[Refinement types](https://en.wikipedia.org/wiki/Refinement_type)
attach predicates to types: `{x: int | x > 0}` is "the integers
greater than zero." Liquid Haskell uses these with an SMT
solver to discharge predicates automatically.

A7 takes a **lite** version of this:

- The predicates are restricted to **disjunctive intervals**
  (Level 2 of `narrowing.md`'s ladder), plus optional-narrowing
  and variant-tag predicates.
- The discharge is by **pattern recognition**, not SMT.
- The predicates are **invisible to the user** — they exist only
  inside the type checker.

The user never writes `{x: int | x > 0}`; they write plain
`int`. The compiler infers the predicate from the control flow.

### Flow-sensitive typing (Crystal, TypeScript)

[Crystal](https://crystal-lang.org/) and TypeScript pioneered
**flow-sensitive typing** in mainstream languages: a variable's
type changes through the program based on the control flow
preceding it. TypeScript's
[narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
docs describe the same mechanism A7 uses for nullability and
tagged-union narrowing.

A7 extends flow-sensitive typing to **integer ranges** as well,
which neither Crystal nor TypeScript does. This is the SPARK
tier in the comparison.

## What the compiler can and cannot know

It's worth being explicit about the limits.

### Can know (sufficient knowledge inside one function):

- Range of a value derived from literals and other range-proved
  values: `y := x + 1` for `x: int with range [0, n)` gives
  `y: int with range [1, n+1)`.
- Range of a value after a comparison guard: `if x < 5:` narrows.
- Value of a binding after `match arm`: the bound variable's
  type per arm.
- Non-nullness of a binding after `if x == nil { ret }`.
- Discharge of `s.length == N` after `if s.length == N:`.
- Variant tag after `match` on a tagged union.

### Cannot know (in v1):

- Range of a value passed as a function argument unless the
  callee's signature declares it. A7 v1 does not have
  function-level preconditions; the receiving function sees the
  parameter as its declared type only.
- Range of a value returned from a function unless the
  signature declares a refinement. A7 v1 has no refinement
  return types in user-facing signatures (the refinement system
  is compiler-internal per CA D.020).
- Range across pointer dereferences (if the pointer's target
  was mutated by another path the compiler can't see).
- Cross-variable correlations beyond simple narrowing
  (`if x < y` narrows `x`'s upper-bound and `y`'s lower-bound
  individually but doesn't track "x < y" as a relation).
- Arbitrary SMT-decidable predicates.

The cannot-know cases are precisely the ones that produce Tier 2
errors. The user works around them by adding local guards.

## Implementation in the A7 compiler

The principle is enforced by **one analysis pass** in the
semantic validator:

1. **Walk the CFG** in forward order, maintaining per-binding
   knowledge.
2. **At each operation site**, look up the operation's
   precondition table entry (e.g., `cast(uint, int)` requires
   "source >= 0").
3. **Compare** the binding's accumulated knowledge to the
   required precondition.
4. **Three outcomes**:
   - Sufficient → mark the site as "discharged"; emit bare op.
   - Insufficient-recoverable → emit a compile error with the
     fix-it pattern from the precondition table.
   - Insufficient-irrecoverable → emit a hard error.

The pass is a few hundred lines on top of the existing
iterative-traversal infrastructure in
`a7/passes/semantic_validator.py`. The precondition tables live
in `a7/passes/preconditions.py` (new file).

## Diagnostics — the user-visible interface

Because every compile error from this system is a "you don't
have the knowledge for this operation" error, the diagnostics
should follow a uniform template:

```
error: <operation> requires <precondition>
  --> <file>:<line>:<col>
   |
N  | <source line>
   |       <highlight under offending operand>
   |
note: at this point, <operand>'s type is <accumulated knowledge>
note: the precondition requires <missing knowledge>
help: add a guard that supplies the missing knowledge:
   |
M  | if <guard>: ... end
N  | <source line>
```

The fix-it patterns are derived mechanically from the
precondition tables; the user sees consistent messages across
all operations.

## Worked examples — the principle in practice

### Example 1: trivial — knowledge from literals

```a7
q: uint = cast(uint, 42)                 // precondition x >= 0; 42 trivially >= 0
```

Knowledge available: `42: int with value 42` ⇒ trivially `>= 0`.
Operation compiles. Bare emission.

### Example 2: knowledge from a guard

```a7
f :: fn(x: int) uint {
    if x < 0 { ret 0 }
    ret cast(uint, x)                    // precondition `x >= 0` discharged by guard
}
```

Inside the second `ret`, `x: int with range [0, +∞)`. The
guard's effect: invalidating the `x < 0` case via early return
leaves only the `x >= 0` case for the trailing code. Operation
compiles. Bare emission.

### Example 3: knowledge from a loop bound

```a7
sum :: fn(s: []int) int {
    total: int = 0
    for i := 0; i < s.length; i += 1 {
        total = total + s[i]              // precondition i < s.length;
                                          // loop induction proves it
    }
    ret total
}
```

Inside the loop body, `i: uint with range [0, s.length - 1]`,
which is exactly `i < s.length`. Bare emission for `s[i]`.

### Example 4: knowledge insufficient — recoverable

```a7
divide :: fn(a: int, b: int) int {
    ret a / b                             // compile error
}
```

Knowledge: `b: int` (full range). Precondition: `b != 0`.
Sufficient? No. Fix-it: `if b == 0 { ret 0 }` (or similar).

### Example 5: knowledge insufficient — irrecoverable

```a7
load :: fn(addr: uint) int {
    p: ref int = cast(ref int, addr)     // hard error
    ret p.val
}
```

No knowledge about `addr` could make it a valid `ref int` —
references can only be obtained from allocation, never from
integer reinterpretation. Hard compile error.

### Example 6: knowledge from a match arm

```a7
print_value :: fn(opt: ?int) {
    match opt {
        case some(v): {
            // here v: int — the some-arm provides the unwrap knowledge
            io.println("{}", v)
        }
        case nil: {
            io.println("nothing")
        }
    }
}
```

Inside the `case some(v):` arm, `v: int` (the inner type of
`?int`). No `?` propagation needed; the match arm adds the
knowledge directly.

### Example 7: cross-variable correlation — current v1 limitation

```a7
f :: fn(x: int, y: int) int {
    if x < y {
        // here `x` has upper bound from `y`, but A7 v1 doesn't
        // track the correlation "x < y" as a relation.
        // The narrowing knowledge: x < y, but `y`'s value is unknown.
        // So `x`'s upper bound is "less than y" — not a concrete number.
        // If we now try to use `x` as an index for a slice of size y,
        // A7 v1 will not discharge the bound.
        s: []int = ...
        if y <= s.length {
            // here we know y <= s.length, AND x < y, AND x < s.length
            // but A7's v1 tracker won't derive "x < s.length" from these.
            ret s[cast(uint, x)]          // v1: compile error
        }
    }
    ret 0
}
```

This is a Tier 2 case where A7 v1 conservatively gives up. The
workaround: introduce a local intermediate variable that
captures the relation explicitly.

```a7
        n: uint = cast(uint, y)           // OK once y >= 0 is proved
        if x_uint < n and n <= s.length {
            ret s[x_uint]                  // works
        }
```

Future versions (Level 3 polyhedral analysis from
`narrowing.md`) would handle the original form directly.

## Comparison: how other languages express this

| Language | "Knowledge" mechanism | What user writes |
| --- | --- | --- |
| **Python** | None at compile time; everything is runtime checked | `int(x)` raises on failure |
| **JS / TS** | TypeScript narrowing for nullables and unions | `if (x !== null) { /* x is non-null */ }` |
| **C** | None; cast is reinterpretation | `(uint32_t)x` — UB on overflow |
| **Rust** | Compile-time type checking but not flow-sensitive on integer ranges | `as u32` — truncates silently |
| **Swift** | Optional narrowing; runtime trap on overflow | `Int(exactly:)` returns `Int?` |
| **Zig** | `comptime` known values; `@intCast` traps on overflow | `@as(u32, x)` — compile error if loss |
| **Crystal** | First-class union types + flow-sensitive | `case x; when Int32; ... end` narrows |
| **Ada / SPARK** | Subtype constraints; SPARK proves at compile time | `Positive_T (X)` runtime-or-compile-time-checked |
| **Liquid Haskell** | Refinement types with SMT solver | `{x: Int \| x > 0}` discharged by Z3 |
| **A7 (proposed)** | Compile-time knowledge via narrowing + pattern recognition | `cast(uint, x)` only compiles when `x >= 0` is known |

A7 sits in a unique combination: as strict as SPARK on the
operations it covers, as simple as Python/JS on the
user-facing syntax, with the cost of the analysis paid by the
compiler (not by an SMT solver and not by the user).

## Limits and future extensions

What this principle does **not** give A7:

- It does not prove **functional correctness**. The compiler
  proves preconditions (no division by zero, no OOB, etc.), not
  that the function returns the right answer.
- It does not propagate **across function boundaries** in v1.
  A function's parameter loses any caller-side narrowing
  information at the function entry.
- It does not handle **all valid programs**. Some programs that
  are obviously safe to a human (and to an SMT solver) will
  fail to compile because the pattern recogniser missed them.
  Workaround: refactor to a recognised pattern.
- It does not eliminate the need for **runtime error handling**
  for data-dependent operations (parsing, I/O, allocation).
  Those still return `?T` / `Result<T, E>`.

Future extensions (v2+):

- Function preconditions / postconditions (Ada aspect-style)
  to propagate narrowing across calls.
- Level 3 polyhedral analysis for cross-variable correlations.
- Optional SMT integration for cases the pattern recogniser
  can't handle.
- User-written predicates (`refined int as Positive where x >
  0`) — a controlled refinement-type addition.

None of these are needed for v1.

## Cross-references

- [`narrowing.md`](./narrowing.md) — the mechanism that
  accumulates knowledge.
- [`conversions.md`](./conversions.md) — the cast catalog.
- [`08-decisions.md`](./08-decisions.md) — the Cluster CA / CB
  decisions that depend on this principle.
- [`05-for-a7.md`](./05-for-a7.md) §7 — the contract paragraph.
- [`comparative/ada.md`](./comparative/ada.md) — SPARK's
  predicate-based version of the same idea.

## Summary

> A7's safety contract is "the compiler emits Zig that runs
> correctly under `-O ReleaseFast`." The mechanism is "the
> compiler proves the preconditions of every emitted operation
> at compile time." The user's interface is "the compiler tells
> you what it doesn't know and how to fix it." The compiler's
> job is to **accumulate knowledge** through the program's
> control flow and discharge each operation's precondition
> against the available knowledge. When the knowledge is
> sufficient, the operation compiles to bare native code. When
> it isn't, the user adds a guard.
>
> **The cast is allowed because the compiler knows the value.**

This sentence — the user's framing — is the entire safety
contract in nine words.
