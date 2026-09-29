# Compile-Time Knowledge — The Principle Behind A7's Safety

Status: research note, written before 2026-05-11 (Codex cited it in its first
review), with audit notes added 2026-09-16. The principle still describes how
the safety pass works. The numeric types, `cast` spelling and parameter modes in
its examples are superseded or open. Current user decisions are in the
[v1 decision ledger](../plan/decisions.md).

This note formalizes a principle the user stated: "the cast is allowed because
the compiler knows the number." It argues that A7's safety contract reduces to
one idea: **the compiler permits an operation exactly when its static knowledge
about the operands discharges the operation's preconditions.** Companion to
[`narrowing.md`](./narrowing.md) and [`conversions.md`](./conversions.md).

## Notes (2026-09-16)

Read the examples with these changes in mind:

| Topic in this note | Decision (and current compiler state where it differs) | Source |
| --- | --- | --- |
| `int`, `uint`, `number` | Removed. Integers have explicit widths (`i8`–`i64`, `u8`–`u64`, `isize`, `usize`); floats are `f32`/`f64`. Read `int` as a signed width such as `i64`, `uint` as `u64` or `usize`, `number` as `f64` | Ledger L3, L4 |
| Integer `+ - *` | Decided to wrap, so they carry no overflow precondition. Not yet lowered: `u8` `x += 1` still emits plain Zig `+=`. Division, remainder, `MIN / -1`, shifts, narrowing casts and size arithmetic still need rules | L5; plan track 3; gate G3 |
| Floats | Decided: IEEE 754 with NaN and infinity as ordinary values; the finite-only idea is withdrawn. The current compiler still rejects `0.0 / 0.0` | L16; gate G1 |
| `cast(T, x)` spelling | Open (D.024 vs D.038) | Gate G3 |
| `f(inout x)`, `f(borrow x)` | No parameter-mode syntax is approved; `ref` stays the working form | L6; [memory plan](../plan/memory.md) |
| `?T`, `case some(v)`, `s.length` | Proposed syntax. Current slices spell length `.len` (`a7/passes/type_checker.py:1796`) | — |
| Implementation | See the note under "Implementation in the A7 compiler" | `a7/safety.py` |

Every A7 block below is labeled. "Proposed" blocks use syntax or types that
current A7 does not have and show design intent only.

## The principle in one sentence

> **`cast(T, x)` (and `a / b`, `s[i]`, etc.) is permitted at a
> particular program point if and only if the compiler's
> accumulated static knowledge about the operand values is
> sufficient to discharge the operation's preconditions at that
> point. The cast is allowed precisely because the compiler
> knows the value.**

The corollary:

> **If the compiler does not have the required knowledge, the
> program does not compile.** No runtime check is inserted; no
> `?T` is silently returned; no panic path is generated. The
> user fixes the code at compile time by adding a guard, a
> match, or a narrower declared type.

## Why this matters

This principle links the decisions in Clusters CA and CB and the planned
Cluster CD. Each safety rule follows from it:

- **`if x >= 0` makes `cast(uint, x)` compile.** The guard adds `x >= 0`, which
  is the cast's precondition.
- **`if i < s.length` makes `s[i]` compile.** The guard adds the bound.
- **`if b != 0` makes `a / b` compile.** The guard adds non-zero.
- **`if x == nil` followed by `ret` makes `x` non-null below.** The early return
  removes the nil case.
- **`match` on a tagged union narrows the binding in each arm.** The arm adds
  the variant.

The user writes ordinary control flow: `if`, `match`, early returns. The
compiler turns each statement into knowledge added to or removed from the
context. When the knowledge covers a precondition, the operation compiles;
otherwise it does not. This is a literal description of the analysis, not a
metaphor.

The early-return case, in current syntax:

```a7
// Current A7 syntax; not compiled for this note.
Node :: struct {
    value: i32
}

read_value :: fn(n: ref Node) i32 {
    if n == nil { ret 0 }
    ret n.value          // n is known non-nil after the early return
}
```

Read from source, not run: the current safety pass learns "non-nil" from an
always-returning `if n == nil` (`a7/safety.py:663-668`, `698-702`), and field
access through a `ref` requires that fact (`a7/safety.py:425-433`).

## The mental model: type as accumulated knowledge

In this view a *type* is **the compiler's knowledge about a value at a program
point**. A declared type such as `int` is the starting knowledge: "an integer of
unknown range." A narrowed type such as `int with range [0, s.length-1]` is the
knowledge after a guard.

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

> Note (2026-09-16): the `inout` and `borrow` rows describe proposed modes that
> were not accepted (L6). Current A7 passes mutable arguments as `ref`
> parameters.

Each operation has a precondition: the knowledge it **requires**. At each use,
the compiler compares required knowledge with available knowledge. If available
covers required, the operation compiles; otherwise it does not.

## Three knowledge tiers for any operation

At any use site, the available knowledge falls into one of three tiers.

### Tier 1 — Sufficient knowledge: bare emission

The compiler can discharge the precondition. The operation compiles, and the
emitted Zig has **no runtime check**.

```a7
// Proposed (uses `int`/`uint`).
x: int = 42                              // x: int with value 42
y: uint = cast(uint, x)                  // precondition x >= 0 trivially holds;
                                          // emits @intCast(u64, 42) — no check
```

The two-argument `@intCast(u64, 42)` is pre-0.11 Zig syntax. Zig 0.16 writes
`@as(u64, @intCast(x))` or relies on the result type.

### Tier 2 — Insufficient but recoverable: compile error with fix-it

The compiler lacks the knowledge, but a guard the user could add would supply
it. The compiler reports an error with a fix-it.

```a7
// Proposed (uses `int`/`uint`).
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

The fix-it names the missing knowledge. Once the user adds the guard, the next
compile has the knowledge and the cast compiles.

### Tier 3 — Insufficient and irrecoverable: hard compile error

Some preconditions can never be discharged, because the source type holds no
information that could satisfy them. These are hard errors with no fix-it; the
user must change the algorithm.

```a7
// Proposed (uses a `u` literal suffix and `ref` casts).
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

> Note (2026-09-16), read from source: `a7/cast_classifier.py:40-41` forbids
> every cast whose source or target is a reference or function type. The
> diagnostic format above is proposed; current safety errors report the required
> proof and a reason (`a7/safety.py:254-264`). The advice "allocate with
> `new T`" predates the memory direction (L15, L17–L22), which moves toward no
> explicit allocation.

## Worked examples — the knowledge for each cast

For each `cast(T, x)`: what the compiler must know about `x`, and the fix-it
when it does not.

> Note (2026-09-16): the `int`/`uint`/`number` rows are superseded by L3 and L4.
> Under explicit widths the same pattern applies: widening is free, while
> signed-to-unsigned and narrowing need a range proof (`a7/cast_classifier.py`).

| Cast | Required knowledge | Fix-it when missing |
| --- | --- | --- |
| `cast(int, x: int)` | none — identity | n/a |
| `cast(int, x: uint)` | none — lossless | n/a |
| `cast(int, n: number)` | none — defaults to trunc | n/a |
| `cast(uint, x: int)` | `x >= 0` | `if x < 0 { ... }` or `if x >= 0 { cast(uint, x) ... }` |
| `cast(uint, n: number)` | `n >= 0` (and trunc mode) | `if n < 0 { ... }` |
| `cast(number, x: int)` | none — embedding | n/a |
| `cast(number, x: uint)` | none — embedding | n/a |
| `cast(string, x)` | none — format always succeeds | n/a |
| `cast(int, s: string)` | none — but result is `?int` (data-dependent) | match on result |
| `cast(uint, s: string)` | none — result is `?uint` | match |
| `cast([N]T, s: []T)` | `s.length == N` | `if s.length == N { ... }` |
| `cast(EnumT, i: int)` | `i` is a valid discriminant of `EnumT` | `match i { case <valid_discs>: { ... } else: { ... } }` |
| `cast(i32, x: int)` | `x in [INT32_MIN, INT32_MAX]` | range guard |
| `cast(int, x: i32)` | none — widening | n/a |
| `cast(ref T, x: uint)` | **irrecoverable** | rewrite — use `new` or pass as parameter |
| `cast(uint, p: ref T)` | **irrecoverable** | use `e.discriminant()` analog or rewrite |
| `cast(EnumA, x: EnumB)` | **irrecoverable** | go through discriminants explicitly |

Column 1 is the operation, column 2 the **knowledge needed** (its precondition),
and column 3 the **guard pattern** that supplies it.

> Note (2026-09-16): `cast(int, n: number)` "defaults to trunc" and
> `cast(string, x)` / `cast(int, s: string)` are not current behavior: the
> classifier accepts only primitive numeric casts, and float-to-integer casts
> are proved only for finite, integral, in-range literals
> (`a7/safety.py:654-661`). Float-to-integer failure is an open item under G1.

## Knowledge from data-dependent sources

Some values come from sources the compiler cannot see into:

- Strings read from stdin or files.
- Bytes from a network socket.
- Return values from FFI.
- The result of an allocation (success or OOM).

The compiler has **no static knowledge** of these values. It cannot prove
`x >= 0`, `i < s.length`, or "this discriminant is valid." So the operation's
return type carries the failure explicitly:

```a7
// Proposed (uses `?T`, `case some(v)` and string-to-int `cast`).
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

These are the **data-dependent** operations from D.025. They are the only A7
operations that return `?T` or `Result<T, E>`, because only for them can the
compiler not acquire the knowledge at compile time.

> Note (2026-09-16): D.025 must be restated for explicit widths (ledger
> "Superseded material"). `Option`, `Result` and recoverable I/O are open under
> gate G5, which also notes that the current I/O helpers panic on external
> failures.

## Theoretical foundations

A7 applies established ideas.

### Abstract interpretation (Patrick Cousot, 1977 onwards)

Cousot's **abstract interpretation** treats every static analysis as an
abstraction of the program's concrete runtime behaviour. The abstract values are
what the analyser knows about the concrete values. A type system is an abstract
interpretation whose abstract values are types.
([Wikipedia: Abstract interpretation](https://en.wikipedia.org/wiki/Abstract_interpretation);
[Cousot, *Types as Abstract Interpretations*](https://www.irif.fr/~mellies/mpri/mpri-ens/articles/cousot-types-as-abstract-interpretations.pdf))

A7's narrowing is one such interpretation. Its abstract domain is disjunctive
integer intervals, plus optional-narrowing flags, plus tagged-union variant
tags. The compiler's "knowledge" is the abstract value at each program point.

### Epistemic type theory (modal logic, S4)

In modal logic, `□A` means "it is known that A." Several authors have explored
type systems with modal type formers, where `□T` is "a value of type T known at
compile time." Function application becomes `□(a → b) → (□a → □b)`: if you know
the function and the argument, you know the result.
([Sigfpe on S4 and partial evaluation](http://blog.sigfpe.com/2006/04/s4-and-partial-evaluation.html))

A7 adopts this view informally. Each precondition is a modal formula the
compiler must prove at compile time, and a fix-it is the user supplying the
missing evidence.

### Refinement types (Liquid Haskell, F\*, ATS)

[Refinement types](https://en.wikipedia.org/wiki/Refinement_type) attach
predicates to types: `{x: int | x > 0}` is the integers greater than zero.
Liquid Haskell discharges such predicates with an SMT solver.

A7 takes a **lite** version:

- Predicates are limited to **disjunctive intervals** (Level 2 of
  `narrowing.md`'s ladder), plus optional-narrowing and variant-tag predicates.
- Discharge is by **pattern recognition**, not SMT.
- Predicates are **invisible to the user**; they exist only inside the compiler.

The user never writes `{x: int | x > 0}`; they write `int`, and the compiler
infers the predicate from control flow.

### Flow-sensitive typing (Crystal, TypeScript)

[Crystal](https://crystal-lang.org/) and TypeScript brought **flow-sensitive
typing** to mainstream languages: a variable's type changes with the control
flow before it. TypeScript's
[narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html) docs
describe the mechanism A7 uses for nullability and tagged unions.

A7 also applies flow-sensitive typing to **integer ranges**, which neither
Crystal nor TypeScript does. This is the SPARK tier in the comparison.

## What the compiler can and cannot know

### Can know (sufficient knowledge inside one function):

- The range of a value derived from literals and other range-proved values:
  `y := x + 1` for `x: int with range [0, n)` gives `y: int with range [1, n+1)`.
- The range of a value after a comparison guard: `if x < 5 { ... }` narrows.
- The type of a binding in a `match` arm.
- Non-nullness after `if x == nil { ret }`.
- `s.length == N` after `if s.length == N { ... }`.
- The variant tag after `match` on a tagged union.

### Cannot know (in v1):

- The range of a function argument, unless the callee's signature declares it.
  A7 v1 has no function preconditions; the callee sees only the declared type.
- The range of a function's return value, unless the signature declares a
  refinement. A7 v1 has no user-facing refinement return types (the refinement
  system is compiler-internal per CA D.020).
- Ranges across pointer dereferences, if another path the compiler cannot see
  mutated the target.
- Cross-variable relations beyond simple narrowing. `if x < y` narrows `x`'s
  upper bound and `y`'s lower bound separately, but does not keep "x < y" as a
  relation.
- Arbitrary SMT-decidable predicates.

These limits produce the Tier 2 errors. The user works around them with local
guards.

> Note (2026-09-16), read from source, not run: the current safety pass knows
> less than the "can know" list:
>
> - Guards are recognized only when an identifier is compared with an integer
>   literal, zero or `nil` (`a7/safety.py:678-703`). `if i < s.len` against a
>   non-literal adds no fact.
> - Parameters start with no interval (`a7/safety.py:291-293`, `479-484`). So
>   after `if x < 0 { ret 0 }` the fact is `[0, unbounded)`, and a
>   signed-to-unsigned cast still fails the range check
>   (`a7/safety.py:543`, `648-652`).
> - C-style `for` loops add no induction facts (`a7/safety.py:353-363`).
>   Indexed `for-in` gives the index `[0, unbounded)` (`a7/safety.py:368`).
> - Float division uses the integer non-zero divisor proof. Plan gate G1
>   records that `0.0 / 0.0` is rejected, which conflicts with L16.

## Implementation in the A7 compiler

The plan was **one analysis pass** in the semantic validator:

1. **Walk the CFG** forward, keeping per-binding knowledge.
2. **At each operation**, look up its precondition in a table (for example,
   `cast(uint, int)` requires "source >= 0").
3. **Compare** the binding's knowledge with the precondition.
4. **Three outcomes:**
   - Sufficient → mark the site "discharged"; emit the bare operation.
   - Insufficient but recoverable → compile error with the table's fix-it.
   - Insufficient and irrecoverable → hard error.

The estimate was a few hundred lines on top of the iterative-traversal code in
`a7/passes/semantic_validator.py`, with precondition tables in a new
`a7/passes/preconditions.py`.

> Note (2026-09-16), checked against the source at 701c679: the analysis exists
> as `SafetyProofPass` in `a7/safety.py`, not in `semantic_validator.py`. It
> runs after semantic validation (`a7/compile.py:347`) and records approvals in
> a `BackendPlan` that codegen checks before lowering (for example
> `a7/backends/zig.py:1672`). `a7/passes/preconditions.py` does not exist. Cast
> rules live in `a7/cast_classifier.py`; other preconditions are methods of the
> pass. It saves and restores facts per block instead of walking a CFG. It
> reports proof failures but does not produce fix-its or separate Tier 2 from
> Tier 3. Codex called the "few hundred lines, one pass" estimate not credible
> ([codex-review.md](./codex-review.md)). STATUS priority 4 is to split the pass
> into CFG, fact, obligation, proof-discharge and backend-plan stages.

## Diagnostics — the user-visible interface

Every error from this system means "you don't have the knowledge for this
operation," so diagnostics should share one template:

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
M  | if <guard> { ... }
N  | <source line>
```

Fix-its come mechanically from the precondition tables, so messages stay
consistent across operations.

## Worked examples — the principle in practice

### Example 1: trivial — knowledge from literals

```a7
// Proposed (uses `uint`).
q: uint = cast(uint, 42)                 // precondition x >= 0; 42 trivially >= 0
```

Knowledge: `42: int with value 42`, so `>= 0` holds. The operation compiles to a
bare emission.

### Example 2: knowledge from a guard

```a7
// Proposed (uses `int`/`uint`).
f :: fn(x: int) uint {
    if x < 0 { ret 0 }
    ret cast(uint, x)                    // precondition `x >= 0` discharged by guard
}
```

At the second `ret`, `x: int with range [0, +∞)`. The early return removes the
`x < 0` case, leaving only `x >= 0`. The operation compiles to a bare emission.

### Example 3: knowledge from a loop bound

```a7
// Proposed (uses `int` and `s.length`).
sum :: fn(s: []int) int {
    total: int = 0
    for i := 0; i < s.length; i += 1 {
        total = total + s[i]              // precondition i < s.length;
                                          // loop induction proves it
    }
    ret total
}
```

In the loop body, `i: uint with range [0, s.length - 1]`, which is exactly
`i < s.length`. `s[i]` is a bare emission.

### Example 4: knowledge insufficient — recoverable

```a7
// Proposed (uses `int`).
divide :: fn(a: int, b: int) int {
    ret a / b                             // compile error
}
```

Knowledge: `b: int` (full range). Precondition: `b != 0`. Not sufficient.
Fix-it: `if b == 0 { ret 0 }` or similar.

The fixed form, in current syntax:

```a7
// Current A7 syntax; not compiled for this note.
divide :: fn(a: i64, b: i64) i64 {
    if b == 0 { ret 0 }
    ret a / b                             // b is known non-zero here
}
```

Read from source, not run: the early return adds a non-zero fact for `b`
(`a7/safety.py:695-697`), which the divisor proof accepts
(`a7/safety.py:559-565`).

### Example 5: knowledge insufficient — irrecoverable

```a7
// Proposed (uses `ref` casts and `uint`).
load :: fn(addr: uint) int {
    p: ref int = cast(ref int, addr)     // hard error
    ret 0
}
```

No knowledge about `addr` can make it a valid `ref int`. References come only
from allocation, never from reinterpreting an integer. Hard compile error.

(Edited 2026-09-16: the original second line was `ret p.val`. Public A7 has no
`.val`, and the type checker rejects it (`a7/passes/type_checker.py:1784-1791`),
so it was replaced with `ret 0`. The example's point is the forbidden cast.)

### Example 6: knowledge from a match arm

```a7
// Proposed (uses `?int` and `case some(v)`).
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

In the `case some(v):` arm, `v: int`, the inner type of `?int`. No `?`
propagation is needed; the arm supplies the knowledge.

### Example 7: cross-variable correlation — current v1 limitation

```a7
// Proposed (uses `int`, `uint` and `s.length`; `...` is a placeholder).
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

A7 v1 gives up here (Tier 2). The workaround: introduce local variables that
state the relation directly.

```a7
// Proposed (fragment inside the `if x < y` block above).
        x_uint: uint = cast(uint, x)      // OK once x >= 0 is proved
        n: uint = cast(uint, y)           // OK once y >= 0 is proved
        if x_uint < n and n <= s.length {
            ret s[x_uint]                  // works
        }
```

(Edited 2026-09-16: added the `x_uint` declaration, which the original fragment
used without declaring.)

Level 3 polyhedral analysis (`narrowing.md`) would handle the original form.

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

The aim: as strict as SPARK on the operations it covers, as simple as Python/JS
in syntax, with the analysis cost paid by the compiler rather than an SMT solver
or the user.

## Limits and future extensions

What this principle does **not** give A7:

- **Functional correctness.** The compiler proves preconditions (no division by
  zero, no out-of-bounds), not that the function returns the right answer.
- **Propagation across function boundaries** in v1. A parameter loses the
  caller's narrowing at function entry.
- **Acceptance of all valid programs.** Some programs that are safe to a human
  (or an SMT solver) fail because the pattern recognizer misses them.
  Workaround: refactor to a recognized pattern.
- **Freedom from runtime error handling** for data-dependent operations
  (parsing, I/O, allocation). Those still return `?T` / `Result<T, E>`.

> Note (2026-09-16): allocation failure is handled differently in the proposed
> [memory plan](../plan/memory.md), where ordinary source never allocates
> explicitly; not approved.

Future extensions (v2+):

- Function preconditions and postconditions (Ada aspect style) to carry
  narrowing across calls.
- Level 3 polyhedral analysis for cross-variable relations.
- Optional SMT integration for cases the pattern recognizer cannot handle.
- User-written predicates (`refined int as Positive where x > 0`), a controlled
  refinement-type addition.

None of these are needed for v1.

## Cross-references

- [`narrowing.md`](./narrowing.md) — the mechanism that accumulates knowledge.
- [`conversions.md`](./conversions.md) — the cast catalog.
- [`08-decisions.md`](./08-decisions.md) — the Cluster CA / CB decisions that
  depend on this principle.
- [`05-for-a7.md`](./05-for-a7.md) §7 — the contract paragraph.
- [`comparative/ada.md`](./comparative/ada.md) — SPARK's predicate-based version
  of the same idea.
- [`../SAFETY_CONTRACT.md`](../SAFETY_CONTRACT.md) — what the compiler enforces
  today.
- [`../plan/decisions.md`](../plan/decisions.md) — current user decisions.

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

This sentence, the user's framing, states the whole safety contract in ten
words. (Corrected 2026-09-16: the original said "nine words".)
