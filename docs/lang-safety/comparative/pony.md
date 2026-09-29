# Comparative: Pony

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Pony is the clearest example of compile-time concurrency safety through
reference capabilities. It is an actor-model language, in the style of Erlang.
Six reference capabilities statically prevent data races and memory-safety
violations across actors, without locks, lifetimes or a stop-the-world GC pause.

Pony was the Phase B reference for A7's eventual concurrency story (Gap 10 and a
later roadmap phase). It shows that a small, principled type-system extension
can make concurrency race-free by construction.

> Note (2026-09-16): L1 puts concurrency in v1. The memory plan proposes
> structured tasks where values move in (gate M10) and read-only sharing with
> child tasks (M36), not actors. See [memory.md](../../plan/memory.md) section 5.

## The six reference capabilities

Every Pony reference carries one capability:

| Cap | Read | Write | Shareable in same actor | Sendable to another actor |
| --- | --- | --- | --- | --- |
| `iso` (isolated) | yes | yes | no | yes |
| `trn` (transition) | yes | yes | yes (read-only aliases) | no |
| `ref` (reference) | yes | yes | yes | no |
| `val` (value) | yes | no | yes | yes |
| `box` (box) | yes | no | yes (read-only) | no |
| `tag` (tag) | no | no | yes | yes |

Meaning of each:

- `iso`: single owner, mutable, transferable across actors. No other reference
  exists.
- `val`: immutable and freely shareable, because immutable data cannot race.
- `ref`: mutable, but only within one actor.
- `box`: a read-only view of something that may be `ref` or `val`; the holder
  does not know which.
- `tag`: an opaque identity; cannot read or write.
- `trn`: writable with no other writers, while read-only aliases exist; can be
  frozen to `val`.

The compiler enforces:

- No two `iso` references to the same object.
- `consume x` transfers an `iso`.
- A `ref` cannot be sent to another actor, because it would race with the
  sending actor's writes.
- A `val` can be shared freely.
- Messages between actors carry only `iso`, `val` or `tag`.

As a result, no two threads can hold writable references to the same data at
the same time. The check is at compile time and has no runtime cost.

## Per-gap findings

| Gap | Pony |
| --- | --- |
| 03 Definite assignment | Enforced by the type checker. |
| 04 `NonZero` division | Division by zero returns zero (defined behavior). No `NonZero` refinement. |
| 05 Stack budget | Not addressed. Recursion is allowed. |
| 06 Typed arithmetic | Explicit numeric types. Overflow is defined and wraps. |
| 09 Refinement-lite | Primitive subtypes, but no refinement system in the A7 sense. |
| 11 Finite floats | Standard IEEE 754 only. |
| 12 FFI | Small FFI surface through `@ffi_call`. |

> Note (2026-09-16): A7 now matches Pony on Gap 06 and Gap 11: ordinary
> `+ - *` wrap (L5) and floats follow IEEE 754 (L16).

### Gap 01 — Cast

Pony has explicit type conversions. The special form for changing a reference's
capability is the `recover` block:

```pony
let x: String iso = recover iso String end  // construct an iso String
let y: String val = consume x               // freeze: iso → val
```

Inside `recover`, the compiler checks that the new capability is justified by
what the block can reach.

If A7 adopts reference capabilities, it can adopt the `recover` block: a
scoped, compiler-checked capability change.

### Gap 02 — Nullable pointers

Pony has no implicit nullable references. `None` is a separate type used in
unions. A reference to an object is always valid; "maybe an object" is written
`(SomeType | None)`.

This idiom is the same as A7's `?T` sugar for `Option<T>`.

### Gap 07 — Bounded indexing

Indexing is written `array(i)?`. The `?` marks a partial call that may fail, and
the caller must handle or propagate the failure.

A7 can compare this with Rust's propagating `?`; the two forms are similar.

> Uncertain: the original text said indexing "returns `T?` (a union of `T` and
> None)". Pony's `Array.apply` is a partial function that raises an error rather
> than returning `None`. Verify before relying on either description.

### Gap 08 — Option/Result

Pony uses union types such as `(T | None)` and `(T | Error)` instead of
dedicated `Option` and `Result` types.

A7 gains little here. Dedicated `Option<T>` and `Result<T, E>` types are clearer
to newcomers than bare unions.

### Gap 10 — Affine ownership: `iso`

Pony's `iso` is affine (Pony calls it "linear"). An `iso` reference must be
consumed before the value is used elsewhere:

```pony
let x: String iso = recover iso String("hello") end
let y = consume x          // ownership of the iso transferred
// use of x here is a compile error
```

`consume x` is the explicit move operator. This is stricter than A7's
Hylo-inspired Phase B plan, where moves are implicit at assignment and call
sites.

A7 can adopt the principle that consumption is explicit. The `consume` keyword
makes moves visible to the reader.

> Note (2026-09-16): The memory plan makes ownership internal. Assignment copies
> (contract item 4), there is no move keyword in ordinary source, and only
> resources and values sent into tasks are move-only (gates M7, M10). See
> [memory.md](../../plan/memory.md).

## Race-free concurrency

The six-capability lattice statically prevents all data races. With the actor
model, where each actor has its own mailbox and messages carry only `iso`, `val`
or `tag`, Pony gives concurrency without:

- mutexes, condition variables or atomics in user code;
- a global interpreter lock or other global lock;
- lifetime annotations.

The cost is the lattice itself. Six capabilities are a lot to learn, and the
learning curve is reported to take weeks.

Pony still has a garbage collector, run per actor; the claim is only that there
is no global stop-the-world pause.

## What A7 should adopt

1. Reference capabilities for concurrency safety. The six-capability lattice is
   the design reference; A7 may simplify it to four or five.
2. `recover` blocks for capability changes.
3. The `consume` keyword for explicit moves.
4. The actor model with immutable-or-isolated messages as the concurrency
   primitive.

Phase B proposed a default subset of `iso`, `val`, `ref` and `tag`, dropping
`trn` and `box` as advanced features.

> Note (2026-09-16): Items 1, 3 and 4 are superseded. The memory plan proposes
> structured tasks, values moved into tasks and read-only sharing of values the
> parent does not change (M10, M36), with no capability or move vocabulary in
> source. L15 rules out a garbage collector, so Pony's per-actor GC is not an
> option.

## What to avoid

1. Six capabilities: too many to teach. Pick a subset, for example `iso`, `val`,
   `ref` and `tag`.
2. Pony's actor scheduler and runtime. These are implementation, not language
   design.
3. Unions instead of `Option` and `Result`. A7 has dedicated types.

## Lessons for A7

Pony shows that race-free concurrency can come from a type-system extension with
a few new keywords. It does not need mutex libraries, a borrow checker with
`Send` and `Sync` traits, or a GC for sharing. The pure type-system approach
scales.

In Phase B, Pony was the model for A7 concurrency. The open questions were how
many capabilities to have and what to call them.

## Sources

- [Pony website](https://www.ponylang.io/)
- [Pony tutorial](https://tutorial.ponylang.io/)
- [Reference Capabilities](https://tutorial.ponylang.io/reference-capabilities/reference-capabilities.html)
- [Reference Capability Guarantees](https://tutorial.ponylang.io/reference-capabilities/guarantees.html)
- [Recovering Capabilities](https://tutorial.ponylang.io/reference-capabilities/recovering-capabilities.html)
- [Capability Subtyping](https://tutorial.ponylang.org/capabilities/capability-subtyping.html)
