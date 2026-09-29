# Comparative: Inko, Koka, Verona (short profiles)

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Three short profiles of safe languages that inform specific A7 decisions but do
not need a full per-gap study.

| Language | Memory model | Main idea for A7 |
| --- | --- | --- |
| Inko | Single ownership, isolated heaps, no GC | Isolated heaps and channels for concurrency |
| Koka | Reference counting with compile-time insertion (Perceus) | Effect tracking; compile-time elision of runtime work |
| Verona | Regions as the unit of ownership | Sending whole regions between threads |

> Note (2026-09-16): L1 puts concurrency in v1, so the "later concurrency phase"
> framing below is superseded. The memory plan proposes structured tasks: scope
> exit cancels and joins children, values move into tasks, and children may read
> parent values the parent does not change (gates M10, M36). See
> [memory.md](../../plan/memory.md).

## Inko: single ownership without lifetimes, isolated heaps

[Inko](https://inko-lang.org/) is a newer language (2020 onward) built on single
ownership for memory safety, without Rust's borrow checker:

- Each thread has an isolated heap. Values leave their thread only through
  explicit channels.
- Within a thread, single ownership applies: a value has one owner, and a move
  transfers ownership.
- No borrow checker and no lifetime annotations.
- No GC: destruction is deterministic at scope exit.

### What A7 should adopt

1. The isolated-heap model for concurrency. Each thread or task owns its data,
   and threads communicate through channels that carry moved values. This is
   Erlang's actor model with affine types.
2. Another data point that memory safety does not need a borrow checker. Hylo,
   Vale and Inko all reach it without one.
3. Deterministic destruction without GC. Inko shows that explicit moves plus
   scope exit give predictable cleanup without a runtime collector.

> Note (2026-09-16): Item 1 is close to the memory plan's tasks, where values
> move in (M10), and channel close is explicit (M27). Moves are not written in
> A7 source; the compiler handles them internally.

### What to avoid

- Inko's Smalltalk-influenced syntax.
- The exact channel implementation, which is a runtime concern.

### Relevance to A7

Phase B placed Inko in the later concurrency phase of the roadmap. Its
isolated-heap and channel model is the simplest concurrency design that composes
cleanly with affine ownership.

Sources: [Inko language](https://inko-lang.org/),
[Inko docs](https://docs.inko-lang.org/).

## Koka: effect tracking with reference counting (Perceus)

[Koka](https://koka-lang.github.io/koka/doc/index.html) (Microsoft Research) is
a functional language with a rich effect system and a reference-counted runtime,
Perceus, that gives deterministic memory management with little overhead.

- Algebraic effects in the type system: each function declares the effects it
  may perform (`io`, `div`, `exn` or user-defined), and the type checker
  propagates and enforces them.
- Perceus reference counting: the compiler tracks uses at compile time and
  inserts the minimum number of reference-count updates. Many updates are
  removed statically. There is no tracing GC.

### What A7 should adopt

1. Effect tracking, as a future direction for expressing "this function performs
   IO" or "this function does not allocate". Koka's effect system is the design
   reference; probably out of scope for A7 v1.
2. Compile-time removal of runtime bookkeeping. Perceus decides statically when
   count updates are needed; the technique applies even without reference
   counting.

> Note (2026-09-16): Perceus places count updates and reuse statically, but
> whether a cell is unique is still a runtime test. See the
> [storage reuse study](../../plan/research/memory/reuse-languages.md).

### What to avoid

- Koka's functional-first style; A7 is procedural.
- Reference counting as the memory strategy. Phase B chose ownership plus region
  scopes.

> Note (2026-09-16): The memory plan still rejects reference counting (contract
> item 1, L15). Ownership is now internal, and the compiler groups allocations
> into inferred extents, arenas and pools instead of user-written region scopes
> (L17, memory plan section 4).

### Relevance to A7

Koka is mainly a future reference if A7 adds effect tracking. Perceus is
interesting on its own but is not on A7's critical path.

> Note (2026-09-16): Perceus-style reuse is now part of the memory direction
> (synthesis item 6), so Perceus and the later FP² paper are on the critical path.
> See the [storage reuse study](../../plan/research/memory/reuse-languages.md).

Sources: [Koka](https://koka-lang.github.io/),
["Perceus: Garbage Free Reference Counting with Reuse" (PLDI 2021)](https://www.microsoft.com/en-us/research/uploads/prod/2020/11/perceus-tr-v1.pdf).

## Verona: region-based concurrency with capabilities

[Project Verona](https://github.com/microsoft/verona) (Microsoft Research,
paused as of 2024) was a research language that combined region-based memory
management with concurrency safety.

- Regions are first-class. Every object belongs to a region, and a region can be
  sent to another thread, transferring ownership of the whole region, without
  aliases escaping.
- No data races: regions have a single owner, and references across regions are
  restricted.
- Concurrency safety at compile time, without locks or shared memory.

### What A7 should adopt

1. Regions as the unit of concurrent ownership. Sending a whole region to
   another thread as one transfer is a clean primitive that composes with affine
   ownership.
2. The combination of regions and capabilities. Verona shows they compose, and
   a future A7 design might use both.

> Note (2026-09-16): A7 source will not name regions (memory plan contract item
> 9). Extents per task are inferred (section 4), so a whole-region transfer
> would be a compiler decision rather than user syntax.

### What to avoid

- Verona's specific syntax and type-system details. It is research-grade, and
  production readiness is open.

### Relevance to A7

Verona is the most ambitious recent safe-concurrency research project. Although
paused, its published designs are the closest match for "affine ownership plus
regions plus actor-like concurrency", which Phase B saw as A7's likely
concurrency story.

Sources: [Project Verona](https://github.com/microsoft/verona),
[Verona project papers](https://www.microsoft.com/en-us/research/project/project-verona/).

## Cross-cutting observation

All three languages reject the borrow checker as the central memory-safety
mechanism, and each picks a different substitute:

- Inko: isolated heaps, with single ownership inside each heap.
- Koka: functional purity plus reference counting with compile-time elision.
- Verona: regions as first-class concurrent units.

Together with Hylo and Vale, they show that the borrow checker is one path to
compile-time memory safety, not the only one. The Phase B choice (Hylo's
parameter modes plus optional Cyclone regions) sat well within this design
space.

> Note (2026-09-16): The current direction is still in this space, without
> parameter modes or regions in source: internal ownership, inferred extents and
> generation-tagged ids (L6, O2, memory plan).

## What A7 should take from all three

1. Isolation as a first-class concurrency primitive. Inko's per-thread isolation
   and Verona's per-region isolation suggest a model centered on an owned
   region sent in bulk.
2. Compile-time elision for whatever runtime mechanism is chosen. Perceus shows
   the technique for reference counts, Vale shows it for generation checks, and
   A7's bound proofs apply the same idea to indexing.
3. The design point of no GC and no borrow checker is real and reachable.
