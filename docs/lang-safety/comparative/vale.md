# Comparative: Vale

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Vale gets memory safety from generational references. Instead of a borrow
checker, it catches use after free with a small generation check. Ownership
tracking removes most checks at compile time; a few remain as cold-path runtime
checks.

In Phase B, Vale was the compromise design. If A7's full compile-time
discipline proved too strict in practice, generational references were the most
credible fallback that keeps most compile-time guarantees.

Vale's author, Verdagon, also wrote the memory-safety "grimoire", the best
practitioner's survey of the field.

> Note (2026-09-16): The memory plan adopts the generational idea in a narrower
> form. Records in a collection that supports removal are named by
> generation-tagged ids (`Id(T)` in a `Table(T)`), and lookup returns an optional,
> so a stale id never reads another record and never panics (gates M1 and M5).
> This is not Vale's whole model: ordinary values have no per-reference check.
> See [memory.md](../../plan/memory.md) sections 2 and 6.

## How generational references work

Each heap object has a small header with a generation, an integer that
increments on each free. Each reference stores the generation it saw when it was
created.

Before a dereference:

- If the compiler can prove the reference is still live, through ownership
  tracking, regions or "linear style", it emits a plain load with no runtime
  check.
- Otherwise it emits a runtime check: load the object's current generation and
  compare it to the reference's stored generation. A match dereferences; a
  mismatch panics.

Vale reports that the runtime check survives for a small fraction of accesses,
and plans region borrowing to reduce it further.

```vale
// Conceptual; not Vale's actual syntax
let p: &Buf = new Buf{...};
free(p);     // object's generation incremented
*p           // runtime: check remembered_gen == current_gen ⇒ panic
```

Reported cost: more than 2x faster than reference counting, and on track to
match Rust where checks are proven away.

## Per-gap findings

| Gap | Vale |
| --- | --- |
| 01 Cast | Standard explicit conversions. |
| 02 Nullable pointers | References are non-null by default; `Optional[T]` for nullable. |
| 03 Definite assignment | Enforced statically. |
| 04 `NonZero` division | No refinement types. Division by zero is a runtime trap. |
| 05 Stack budget | Not addressed. |
| 06 Typed arithmetic | Standard explicit overflow operators. |
| 07 Bounded indexing | Claimed to be covered by the generation check, because an out-of-bounds location has no valid generation. |
| 08 Option/Result | Standard sum types. |
| 09 Refinement-lite | Not present. |
| 11 Finite floats | Standard IEEE 754. |
| 12 FFI | Standard FFI. Vale's "Fearless FFI" proposal adds supply-chain protections, which do not bear on A7's gaps. |

> Uncertain (Gap 07): a generation check validates an object reference, not an
> index into an array, so this claim is doubtful. Verify it against Vale's
> documentation before relying on it.

### Gap 10 — Generational references for use after free

Compile-time savings come from ownership tracking that proves a reference
cannot have been freed since it was taken. When the proof succeeds, the common
case, no check is emitted. When it fails, on the cold path, the generation check
is the safety net.

Vale also has region borrow checking. Within a scoped region it proves that no
object is freed, which removes all generation checks in that region.

## What A7 should adopt

1. The frame from Vale's grimoire: one document covering 14 approaches, useful
   for future design discussions.
2. Removing checks through ownership tracking. The same idea drives A7's emission
   of `s.ptr[i]` when bounds are proved.
3. Region borrow checking, to combine Cyclone-style regions with finer ownership
   tracking.
4. A runtime fallback check, but only for cases static analysis cannot prove,
   and only if A7's contract turns out to reject real programs. Generational
   references are the most credible compromise for that case.

A proposed A7 form of the generational idea, from the memory plan (syntax not
approved; the lookup method name is illustrative):

```a7
// Proposed syntax
Node :: struct {
    value: i32
    parent: ?Id(Node)
}

main :: fn() {
    nodes := Table(Node){}
    root := nodes.insert(Node{value: 1, parent: none})
    child := nodes.insert(Node{value: 2, parent: root})
    nodes.remove(child)
    found := nodes.get(child)   // none: the generation no longer matches
}
```

> Note (2026-09-16): Items 2 and 3 predate the memory plan. Slice `.ptr` is
> planned for removal from the public surface, and extents are inferred rather
> than written as regions (memory plan section 3, gate M11). Item 4 is now partly
> adopted through M5, with an optional result instead of a panic.

## What to avoid

1. The runtime generational check on every unproven dereference. It can panic,
   which conflicted with A7's zero-runtime-error contract.
2. Vale's specific syntax; A7 has its own.

> Note (2026-09-16): The memory plan still avoids per-dereference checks on
> ordinary values. Its residual runtime work is a closed list with defined
> outcomes, and id lookup is one entry (section 6, gate M16).

## Vale's grimoire

[`verdagon.dev/grimoire/grimoire`](https://verdagon.dev/grimoire/grimoire)
describes fourteen memory-safety approaches:

1. Tracing GC
2. Reference counting
3. Borrow checking (Rust)
4. Generational references (Vale)
5. Linear types (Austral)
6. Capabilities (Pony)
7. Region-based memory management (Cyclone)
8. Higher RAII (Vale's variant)
9. Bidirectional references
10. Hybrid generational memory (Vale's planned addition)
11. Pure functional, immutable-only
12. Hardware tagging (MTE, CHERI)
13. Software capabilities (Fil-C InvisiCaps)
14. Profile-guided and runtime-monitoring approaches

For A7, the grimoire is the best single-page comparison of the design space. The
Phase B choice (lightweight borrow checking, lightweight linear types through
affine ownership, and region scopes) was informed by this taxonomy.

> Note (2026-09-16): The memory plan combines items 7 and 4 in a new way:
> compiler-inferred extents, arenas and pools, plus generation-tagged ids, with no tracing
> GC or reference counting (L15, L17).

## Vale as a fallback design

If A7's compile-time-only contract proved infeasible for real programs (the bet
was that it would not, but the data was not in), generational references would
be the least bad runtime fallback:

- The per-dereference cost is one load and one comparison.
- The check sits at the dereference site and is easy to understand.
- The compile-time path removes most checks.
- No lifetime annotations are needed.

If A7 ever allows some runtime safety checks, this is the model. In Phase B, the
working assumption was that the contract holds, and Vale was not a target of
research phases A–E.

> Note (2026-09-16): "Phases A–E" here are the lang-safety research phases, not
> the memory plan's phases A–G.

## Sources

- [Vale home](https://vale.dev/)
- [Vale's memory safety strategy: generational references](https://verdagon.dev/blog/generational-references)
- [Borrow checking, RC, GC, and the Eleven Other Memory Safety Approaches](https://verdagon.dev/grimoire/grimoire)
- [Making C++ Memory-Safe Without Borrow Checking, Reference Counting, or Tracing GC](https://verdagon.dev/blog/vale-memory-safe-cpp)
- [Most Memory Safe Native Programming Language](https://vale.dev/memory-safe)
- [Fearless FFI](https://verdagon.dev/blog/fearless-ffi)
