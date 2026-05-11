# Comparative: Pony

> Phase B artifact in the `docs/lang-safety/` research process.

Pony is the **purest example of compile-time concurrency safety
via reference capabilities**. It is an **actor-model** language
(à la Erlang) with **six reference capabilities** that statically
prevent data races and memory safety violations across actors —
without locks, without a GC pause, without lifetimes.

Pony is the **primary reference for A7's eventual concurrency
story** (Gap 10 / future Phase 7 of the implementation roadmap).
It demonstrates that a small, principled type-system extension
can deliver race-free concurrency by construction.

Primary sources:

- [Pony tutorial](https://tutorial.ponylang.io/)
- [Reference Capabilities](https://tutorial.ponylang.io/reference-capabilities/reference-capabilities.html)
- [Reference Capability Guarantees](https://tutorial.ponylang.io/reference-capabilities/guarantees.html)
- [Recovering Capabilities](https://tutorial.ponylang.io/reference-capabilities/recovering-capabilities.html)
- [Capability Subtyping](https://tutorial.ponylang.org/capabilities/capability-subtyping.html)

---

## The six reference capabilities

Every reference in Pony is tagged with one of:

| Cap | Read | Write | Sharable in same actor | Sendable to other actor |
| --- | --- | --- | --- | --- |
| `iso` (Isolated) | ✅ | ✅ | ❌ | ✅ |
| `trn` (Transition) | ✅ | ✅ | ✅ (read-only aliases) | ❌ |
| `ref` (Reference) | ✅ | ✅ | ✅ | ❌ |
| `val` (Value) | ✅ | ❌ | ✅ | ✅ |
| `box` (Box) | ✅ | ❌ | ✅ (read-only) | ❌ |
| `tag` (Tag) | ❌ | ❌ | ✅ | ✅ |

The lattice forces these invariants:

- **`iso`** — single owner, mutable, transferrable across actors.
  No other reference exists.
- **`val`** — immutable, freely shareable (because immutable data
  can't race).
- **`ref`** — mutable, but only within one actor.
- **`box`** — could be `ref` or `val` viewed read-only; the
  caller doesn't know which.
- **`tag`** — opaque identifier only; cannot read or write.
- **`trn`** — transitional: writeable, no other writers, but other
  read-only aliases exist; can be "frozen" to `val`.

The compiler enforces:

- No two `iso` references to the same object.
- An `iso` can be *consumed* (`consume x`) to transfer ownership.
- A `ref` cannot be sent to another actor (would race with the
  origin actor's mutations).
- A `val` can be shared freely (immutable).
- An actor sees a snapshot: cross-actor messages carry `iso`,
  `val`, or `tag` only.

The result: **no two threads can simultaneously hold writable
references to the same data**. Compile-time, no runtime cost.

---

## How Pony handles each gap

### Gap 01 — Cast

Pony has explicit type conversions; capability casts (`recover`
block) are the special form for changing a reference's
capability:

```pony
let x: String iso = recover iso String end  // construct an iso String
let y: String val = consume x               // freeze: iso → val
```

`recover` is a structured block where the compiler verifies the
new capability is justified by what's accessible inside the
block.

**What A7 can steal:** the **`recover` block pattern** when (if)
A7 adopts reference capabilities. A scoped, compiler-checked
capability shift.

---

### Gap 02 — Nullable pointers

Pony has `None` (the absence of a value) as a separate type in a
union; no implicit nullable references. References to objects
are always valid; "maybe an object" is `(SomeType | None)`.

**What A7 can steal:** the union-with-None idiom is the same as
`?T` sugar for `Option<T>`.

---

### Gap 03 — Definite assignment

Pony enforces it via the type checker.

---

### Gap 04 — `NonZero` division

Pony's division by zero returns zero (a defined-behaviour
choice). No `NonZero` refinement.

---

### Gap 05 — Stack budget

Not addressed; Pony allows recursion.

---

### Gap 06 — Typed arithmetic

Pony has explicit numeric types; overflow is defined behaviour
(wraps).

---

### Gap 07 — Bounded indexing

Pony's `Array[T]` indexing returns `T?` (a union of `T` and
None) when bounds are unverified; explicit `array(i)?` syntax
with `?` propagation.

**What A7 can steal:** the **propagating `?`** is similar to
Rust's. Pony's specific form is `?` after an expression to
indicate "may fail, return None to caller".

---

### Gap 08 — Option/Result

Pony uses union types `(T | None)` and `(T | Error)`. No
dedicated `Option`/`Result` — the language relies on its rich
union types.

**What A7 can steal:** **probably nothing** — A7's `Option<T>`
and `Result<T, E>` are clearer for new readers than Pony's bare
unions.

---

### Gap 09 — Refinement-lite

Pony has primitive subtypes but no refinement system in the A7
sense.

---

### Gap 10 — Affine ownership — **iso, the linear capability**

Pony's `iso` is **affine** (Pony's word: "linear"): an iso
reference must be consumed before re-use:

```pony
let x: String iso = recover iso String("hello") end
let y = consume x          // ownership of the iso transferred
// use of x here is a compile error
```

`consume x` is the explicit move operator. Pony's discipline is
*stricter than A7's Hylo-inspired plan*: every iso reference
must be explicitly consumed; A7 has a more conventional
"affine by default" approach where moves are implicit at
assignment / call sites.

**What A7 can steal:** the **principle that consumption is
explicit** is a reasonable choice. The `consume` keyword makes
move semantics visible to the reader.

---

### Gap 11 — Finite floats

Not addressed beyond standard IEEE 754.

---

### Gap 12 — FFI

Pony has a small FFI surface via `@ffi_call`.

---

## The headline contribution: race-free concurrency

Pony's six-capability lattice **statically prevents all data
races**. Combined with the actor model (every actor has its own
mailbox; messages cross actors only as `iso`, `val`, or `tag`),
the language gives you concurrency without:

- Mutexes, condition variables, atomics in user code.
- A GIL or other global lock.
- Lifetime annotations.

The cognitive cost is **the six-capability lattice**. Six is a
lot. Pony's tutorials report a learning curve of weeks.

---

## Primary sources

- [Pony tutorial](https://tutorial.ponylang.io/)
- [Reference Capabilities](https://tutorial.ponylang.io/reference-capabilities/reference-capabilities.html)
- [Reference Capability Guarantees](https://tutorial.ponylang.io/reference-capabilities/guarantees.html)
- [Pony website](https://www.ponylang.io/)

---

## What A7 can steal — consolidated

1. **Reference capabilities for concurrency safety** — when A7
   adds concurrency, the six-cap lattice is the design
   reference. A7 may simplify to four or five caps.
2. **`recover` blocks** for capability shifts.
3. **`consume` keyword** for explicit moves.
4. **Actor model + immutable-or-isolated messaging** as the
   concurrency primitive.

## What A7 should not steal

1. **Six capabilities** — that's a lot to teach. A7 could pick a
   subset (e.g., `iso`, `val`, `ref`, `tag`) and ship four.
2. **Pony's specific actor scheduler / runtime** — that's
   implementation, not language design.
3. **Unions instead of `Option`/`Result`** — A7's design has
   dedicated types.

## Key insight for A7

Pony shows that **race-free concurrency** is achievable through
**a type-system extension that takes a few new keywords**. Not
through library APIs (mutex etc.), not through a borrow checker
with `Send`/`Sync` traits, not through a GC. The pure
type-system approach scales.

When A7 adds concurrency (deferred per the roadmap), Pony is
the model. The decision will be: how many capabilities, and
what are they called. The default proposal: `iso`, `val`,
`ref`, `tag` (drop `trn` and `box` as advanced features).
