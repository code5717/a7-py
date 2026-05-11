# Comparative: Inko, Koka, Verona (short profiles)

> Phase B artifact in the `docs/lang-safety/` research process.
> Three short profiles of additional safe languages that inform
> specific A7 design decisions but don't merit a full per-gap
> walk-through.

---

## Inko — single-ownership without lifetimes, isolated heaps

[Inko](https://inko-lang.org/) is a relatively new
(2020-onward) language built around **single ownership** for
memory safety **without** Rust's borrow checker. Inko's
discipline:

- Each thread has an **isolated heap**. Values cannot escape
  their owning thread except through explicit channels.
- Within a thread, single ownership applies: a value has one
  owner; moving transfers ownership.
- **No borrow checker**; no lifetime annotations.
- **No GC** — deterministic destruction at scope exit.

### What A7 can steal

1. **The isolated-heap model** for concurrency: each
   thread/task owns its data; cross-thread communication is via
   explicit channels carrying owned (moved) values. This is
   essentially **Erlang's actor model with affine types**.
2. **No-borrow-checker** as another data point — Hylo, Vale, and
   Inko all reach memory safety without one.
3. **Deterministic destruction without GC** — Inko's argument
   that explicit move semantics + scope exit gives you
   predictable cleanup without a runtime collector.

### What A7 should not steal

- Inko's specific syntax (it's Smalltalk-influenced).
- The exact channel implementation (a runtime concern).

### Relevance to A7

Inko is most relevant for **Phase 7 (concurrency)** of the
implementation roadmap. The isolated-heap + channel model is
the simplest concurrency design that composes cleanly with
affine ownership. When A7 adds concurrency, Inko's model is
worth re-reading.

Source: [Inko language](https://inko-lang.org/),
[Inko docs](https://docs.inko-lang.org/).

---

## Koka — effect tracking with reference counting (Perceus)

[Koka](https://koka-lang.github.io/koka/doc/index.html)
(Microsoft Research) is a **functional language with a rich
effect system** and a **reference-counted runtime** (Perceus)
that achieves near-zero-overhead deterministic memory
management.

Koka's contribution:

- **Algebraic effects** in the type system: every function
  declares what effects it can perform (`io`, `div`, `exn`,
  user-defined). The type checker propagates and enforces.
- **Perceus reference counting** — at compile time, every value
  has a use count; the compiler inserts the minimal number of
  refcount adjustments. Many adjustments are statically elided.
  No tracing GC.

### What A7 can steal

1. **Effect tracking** as a future direction — when A7 needs
   to express "this function performs IO" or "this function
   does not allocate," Koka's effect system is the design
   reference. Probably out of scope for A7 v1.
2. **Compile-time refcount adjustment elision** — Perceus's
   technique of statically determining when refcount changes
   are needed is applicable even if A7 doesn't use refcounts
   for memory management.

### What A7 should not steal

- Koka's functional-first style (A7 is procedural).
- Reference counting as the memory-management strategy (A7
  uses ownership + region scopes).

### Relevance to A7

Koka is mostly a **future reference** for if A7 ever adds
effect tracking. The Perceus technique is independently
interesting but not on A7's critical path.

Source: [Koka](https://koka-lang.github.io/),
["Perceus: Garbage Free Reference Counting with Reuse" (PLDI 2021)](https://www.microsoft.com/en-us/research/uploads/prod/2020/11/perceus-tr-v1.pdf).

---

## Verona — region-based concurrency with capabilities

[Project Verona](https://github.com/microsoft/verona)
(Microsoft Research, paused as of 2024) was a research
language exploring **region-based memory management combined
with concurrency safety**.

Verona's contribution:

- **Regions as first-class** — every object belongs to a
  region; regions can be sent between threads (transferring
  ownership of the whole region) without aliases escaping.
- **No data races** — regions are single-owner; cross-region
  references are restricted.
- **Compile-time concurrency safety** without locks or shared
  memory.

### What A7 can steal

1. **Regions as the unit of concurrent ownership** — when A7
   adds concurrency, sending a region to another thread (as a
   single transfer) is a clean primitive that composes with
   affine ownership.
2. **Verona's combination of regions and capabilities** —
   demonstrates that regions and capabilities can compose; A7's
   future design might use both.

### What A7 should not steal

- Verona's specific syntax / type-system details (it's
  research-grade; production-readiness is open).

### Relevance to A7

Verona is the **most ambitious** of the recent
safe-concurrency research projects. Even though it's paused,
the published designs are the closest match for
"affine ownership + regions + actor-like concurrency" — A7's
likely eventual concurrency story.

Source: [Project Verona](https://github.com/microsoft/verona),
[Verona project papers](https://www.microsoft.com/en-us/research/project/project-verona/).

---

## Cross-cutting observation

These three languages all reject the borrow checker as the
*central* memory-safety mechanism. Each picks a different
substitute:

- **Inko** — isolated heaps + single ownership within a heap.
- **Koka** — functional purity + refcount with compile-time
  elision.
- **Verona** — regions as first-class concurrent units.

All three confirm what Hylo and Vale also demonstrate: **the
borrow checker is one option, not the only path to compile-time
memory safety**. A7's design choice (Hylo's parameter modes +
optional Cyclone regions) is well within the established
design space.

---

## What A7 should pull from all three together

1. **Isolation as a first-class concurrency primitive** —
   Inko's per-thread isolation + Verona's per-region isolation
   suggest A7's concurrency model should center on "owned
   region, sent in bulk."
2. **Compile-time elision** for whatever runtime mechanism is
   chosen — Perceus shows the technique, Vale shows the same
   for generational checks, A7's bound-proof discipline is the
   same idea applied to indexing.
3. **The "no GC, no borrow checker" design point is real and
   reachable.** A7 isn't off in the woods.
