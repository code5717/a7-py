# Comparative: Hylo (formerly Val)

Status: Phase B research from before 2026-09-14. Where it conflicts with the
ledger in [`../../plan/decisions.md`](../../plan/decisions.md) or the
[memory plan](../../plan/memory.md), those documents win.

## Summary

Hylo was the closest reference for A7's design goal: compile-time memory safety
comparable to Rust's borrow checker, with no lifetime annotations. It gets there
through mutable value semantics. References exist only as parameter-passing
modes, never as storable values. The Hylo team describes the design as memory
safety without lifetime parameters.

The earlier conclusion was that Hylo is the most important study: if its model
works, A7 does not need to invent one.

Note (2026-09-16): the memory plan keeps Hylo's value semantics, non-storable
references and exclusivity checks, but does not adopt Hylo's parameter-mode
keywords. No mode syntax is approved (L6). See the gap 10 note.

## Per-gap findings

### Gap 01: Cast

Hylo uses explicit conversion methods, like Swift's `init(exactly:)`
initialisers; fallible conversions return `Optional`. There is no `as`-style
operator. Bit casts need `unsafe`. Hylo has a small `unsafe` surface for foreign
code and similar uses; A7 takes a stricter line with no `unsafe` at all.

- Adopt: conversion through constructors. Each fallible conversion is a named
  initialiser on the target type that returns `Optional`.

Note (2026-09-16): A7's conversion vocabulary is open under plan gate G3.

### Gap 02: Nullable pointers

Hylo uses `Optional<T>` with no special nullable-pointer shape. References are
not storable values, only parameter modes, so the nullable-reference question
mostly does not arise.

- Adopt: the point that non-storable references remove most nullable-pointer
  problems. A7's `?ref T` exists only because A7 stores references in struct
  fields and locals; Hylo does not.

Note (2026-09-16): the memory plan follows Hylo here. It removes stored and
returned `ref` values and `nil` (gates M4, M6), so `?ref T` goes away and
absence uses optionals over values.

### Gap 03: Definite assignment

Hylo requires initialisation before use through flow analysis that shares
machinery with move and exclusivity checks. One control-flow pass tracks both
"is this binding initialised?" and "has it been consumed?".

- Adopt: integration with move analysis, as for Rust.

### Gap 04: NonZero division

Hylo follows Swift. The standard library can provide `NonZero`-style wrappers,
but `/` does not require them. Division by zero is a precondition violation: a
runtime trap in Swift, while Hylo's semantics are still changing.

- Adopt: nothing that Ada and Rust have not already shown. A7 is stricter and
  requires `NonZero<T>`.

Note (2026-09-16): integer division rules are open under gate G3.

### Gap 05: Stack budget

Hylo has no stack-budget analysis. Like Rust, it allows recursion and accepts
the risk of runtime overflow.

### Gap 06: Typed arithmetic

Hylo follows Swift. `&+`, `&-` and `&*` wrap; the default operators panic on
overflow in debug builds and wrap in release. The vocabulary matches Rust's.

- Adopt: the operator vocabulary. `&+` is Swift's spelling; A7 might prefer
  Zig's `+%`.

Note (2026-09-16): superseded by L5. Ordinary `+`, `-`, `*` wrap in A7, so no
separate wrapping operator is needed.

### Gap 07: Bounded indexing

Hylo collections offer `at(index)`, which has an in-range precondition and traps
otherwise, and safer accessors that return `Optional`.

- Adopt: nothing beyond Rust; A7's `try_get` is the same idea.

### Gap 08: Option and Result

Hylo has standard sum types. Its syntax suits value semantics, and `match` is
exhaustive.

### Gap 09: Refinement-lite

Hylo has no built-in refinement types. The project focuses on value semantics
and leaves refinements to libraries.

### Gap 10: Affine ownership

This is the feature that made Hylo the model for A7.

Hylo has four parameter-passing modes:

| Mode | Semantics | Lifecycle |
| --- | --- | --- |
| `let` | Immutable borrow for the duration of the call | Caller still owns at return |
| `inout` | Exclusive mutable borrow | Caller still owns at return |
| `sink` | Consume (ownership transfer) | Caller loses ownership |
| `set` | Output: uninitialised in, initialised out | Caller gains ownership |

References exist only at function boundaries. A reference cannot be stored in a
variable or field. That removes the lifetime question: every reference lives for
the duration of one call.

```hylo
fun swap(_ x: inout T, _ y: inout T) {
    let tmp = x       // borrow
    x = y
    y = tmp
}

swap(&a, &a)  // compile error: exclusivity violation — two inouts to the same value
```

The compiler checks exclusivity at the call site, within one function. No
borrow checker is needed.

Methods follow the same model; each method declares its receiver's mode:

```hylo
extension Array {
    fun count() -> Int { ... }                  // let-receiver by default
    inout fun append(_ x: sink Element) { ... } // inout-receiver
    sink fun take_first() -> Element { ... }    // sink-receiver, consumes self
}
```

- Adopt: the whole model. That means the four modes, the rule that references
  cannot be stored, and the call-site exclusivity check. A7's gap 10 plan
  mirrored it.
- Avoid: copying Hylo's keyword spellings if A7 prefers others, for example
  `borrow` for `let` or `consume` for `sink`. The semantics matter, not the
  names.

Note (2026-09-16): partly superseded. Two parts survive in the memory plan:

- `ref` values cannot be stored or returned (contract item 8.3, gate M4).
- Aliased changes are rejected at compile time (contract item 8.1).

The mode keywords do not survive. The proposed keywords and inferred modes
(D.040, D.041, D.049) were not accepted, and L6 approves no mode syntax. The
current `ref` parameter remains the working form. Ownership transfer (`sink`) is
internal: assignment copies and the compiler removes unobservable copies
(contract item 4). Resources are move-only (gate M7).

Uncertain: in the `swap` example above, `tmp` is a `let` borrow of `x`, and `x`
is then assigned while that borrow is live. By the exclusivity rule this file
describes, that would be rejected; Hylo code would need a copy of `x`. The
signature also omits a generic parameter for `T`. The example is kept as
recorded.

The same exclusivity rule in A7 terms:

```a7
// Proposed rejection; compiles today (memory plan section 3)
both :: fn(a: ref i32, b: ref i32) {
    a += 1
    b += 1
}

main :: fn() {
    x: i32 = 0
    y: i32 = 0
    both(x, y)      // accepted: distinct places
    both(x, x)      // rejected: two changes to the same place at once
}
```

### Gap 11: Finite floats

Hylo has a standard `Float` type with no `Fin<F>`, as in Swift.

Note (2026-09-16): A7 now takes the same IEEE 754 model (L16); `Fin<F>` is
withdrawn.

### Gap 12: FFI

Hylo interoperates with C through opaque types and a small `unsafe` surface.

## What A7 should adopt

1. The four parameter-passing modes (`let`, `inout`, `sink`, `set`), the core of
   A7's gap 10 plan.
2. The rule that references cannot be stored. They exist only at function
   boundaries, never in struct fields or locals.
3. Call-site exclusivity checking instead of borrow checking.
4. Conversion through fallible constructors (gap 01).
5. Receiver modes: a method declares its receiver's mode like any other
   parameter.

Note (2026-09-16): items 2 and 3 are in the memory plan. Items 1 and 5 are not
approved (L6). Item 4 is open under gate G3.

## What to avoid

1. Hylo's small `unsafe` escape. A7 has none.
2. Swift's `&+` wrapping operator. A7 might prefer Zig's `+%`; under L5 plain
   `+` wraps.
3. Hylo's lack of refinement types. A7 has refinement-lite.
4. Hylo's lack of stack-budget analysis.

## The case for Hylo's model

If A7 adopts a Hylo-style discipline:

- Use after free and aliasing are prevented at compile time.
- No lifetime annotations appear in the syntax.
- Every check is local to a function or call site; there is no lifetime
  inference across functions.
- Diagnostics are clear, for example: "you passed `x` and `x` to the same call;
  one must be different."

The cost is that references cannot be stored. Idioms that need stored
references, such as callbacks, observers and linked structures, must be
rewritten with indices or owning containers. The Hylo team's published
experience suggests this is tractable, and A7's smaller code base makes it
easier.

[`../06-compile-time-safety.md`](../06-compile-time-safety.md) already makes
this recommendation; Hylo shows it has been done in practice.

Note (2026-09-16): the memory plan is the current form of this argument. Its
replacements for stored references are `usize` positions in lists and
generation-checked `Id(T)` values in `Table(T)` (gates M1, M5). Capture-free
function values stay; capturing ones may not escape (gate M6).

## Sources

- [Hylo home](https://hylo-lang.org/)
- [Hylo introduction](https://hylo-lang.org/introduction/)
- [Hylo language specification](https://hylo-lang.org/docs/reference/specification/)
- [Implementation Strategies for Mutable Value Semantics (Racordon et al., JOT 2022)](https://www.jot.fm/issues/issue_2022_02/article2.pdf)
- [Memory Safety without Lifetime Parameters (safe-cpp draft)](https://safecpp.org/draft-lifetimes.html)
- [Borrow Checking Hylo (Dimi Racordon, SPLASH 2023)](https://2023.splashcon.org/details?action-call-with-get-request-type=1&aeaf6a94a42c4ad59b2aa49bf08e9956action_174265066106514c553537a12bb6aa18971ade0b614=1&context=splash-2023&decoTitle=Borrow-checking-Hylo&track=iwaco-2023-papers&urlKey=5)
