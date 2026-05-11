# Comparative: Vale

> Phase B artifact in the `docs/lang-safety/` research process.

Vale's claim is **memory safety via generational references** —
a *runtime-tinged* compile-time-mostly approach that catches UAF
through a tiny generation check rather than a borrow checker.
Most checks elide at compile time via ownership tracking; a few
survive as cold-path runtime checks.

For A7's purpose, Vale represents the **compromise design**: if
A7's full compile-time discipline turns out to be too strict in
practice, generational references are the most credible fallback
that retains *most* of the compile-time guarantees.

Vale also stands out for **Vale's "grimoire" of memory-safety
approaches** by Verdagon (the project author), which is itself
the best practitioner's survey of the field.

Primary sources:

- [Vale home](https://vale.dev/)
- [Vale's memory safety strategy: generational references](https://verdagon.dev/blog/generational-references)
- [Borrow checking, RC, GC, and the Eleven Other Memory Safety Approaches](https://verdagon.dev/grimoire/grimoire)
- [Making C++ Memory-Safe Without Borrow Checking, Reference Counting, or Tracing GC](https://verdagon.dev/blog/vale-memory-safe-cpp)
- [Most Memory Safe Native Programming Language](https://vale.dev/memory-safe)

---

## How generational references work

Every heap object has a small header containing a
**generation** — an integer that increments on each free.

Every reference to the object includes a copy of the
generation it observed at the time the reference was taken.

Before dereferencing:

- If the compiler can prove the reference is still live (via
  ownership tracking, regions, or "linear style"), it emits a
  bare load. **No runtime check.**
- Otherwise, the compiler emits a runtime check: load the
  object's current generation; compare to the reference's
  remembered generation. Match ⇒ dereference; mismatch ⇒
  panic.

In practice (Vale's reports): the runtime check survives for a
small fraction of accesses, with planned region-borrow features
to reduce it further.

```vale
// Conceptual; not Vale's actual syntax
let p: &Buf = new Buf{...};
free(p);     // object's generation incremented
*p           // runtime: check remembered_gen == current_gen ⇒ panic
```

The runtime cost reported: *over 2× faster than reference
counting; on track to match Rust for the proved-elided cases*.

---

## How Vale handles each gap

### Gap 01 — Cast

Standard explicit conversions.

### Gap 02 — Nullable pointers

References are non-null by default; `Optional[T]` for nullable.

### Gap 03 — Definite assignment

Enforced statically.

### Gap 04 — NonZero division

No refinement types; division by zero is a runtime trap.

### Gap 05 — Stack budget

Not addressed.

### Gap 06 — Typed arithmetic

Standard explicit overflow operators.

### Gap 07 — Bounded indexing

Generational reference covers this *too*: an out-of-bounds
access fails the generation check (since OOB doesn't have a
valid generation for that location).

### Gap 08 — Option/Result

Standard sum types.

### Gap 09 — Refinement-lite

Not present.

### Gap 10 — Generational references for UAF — **the headline**

The compile-time savings come from Vale's **ownership tracking**
that proves "this reference can't have been freed since we took
it." When that proof succeeds (the common case), no runtime
check is emitted. When the proof fails (cold path), the
generation check is the safety net.

Vale also has **region borrow checking** — a region-scoped
discipline that proves swaths of code free-free, eliding all
generation checks within the region.

**What A7 can steal:**

1. **The principle of "fallback runtime check"** — for cases
   the static analysis genuinely can't prove. *A7's contract
   forbids this*, but if A7's contract turns out to over-reject
   real programs, generational references are the most credible
   compromise.
2. **Region borrow checking** as a way to elide checks within a
   scoped region — overlaps with Cyclone's regions.

**What A7 should not steal under the current contract:**

1. **The runtime check itself.** A7's contract is no runtime
   errors. Generational references add a per-deref check that
   *can* panic. This is exactly what A7's design avoids.

### Gap 11 — Finite floats

Standard IEEE 754.

### Gap 12 — FFI

Standard FFI; Vale's "Fearless FFI" proposal extends with
supply-chain protections (not relevant to A7's gaps).

---

## Vale's grimoire — the practitioner's survey

[`verdagon.dev/grimoire/grimoire`](https://verdagon.dev/grimoire/grimoire)
documents **fourteen distinct memory-safety approaches**:

1. Tracing GC
2. Reference counting
3. Borrow checking (Rust)
4. Generational references (Vale)
5. Linear types (Austral)
6. Capabilities (Pony)
7. Region-based memory management (Cyclone)
8. Higher-RAII (Vale's variant)
9. Bidirectional references
10. Hybrid generational memory (Vale's planned addition)
11. Pure functional / immutable-only
12. Hardware tagging (MTE, CHERI)
13. Software capabilities (Fil-C InvisiCaps)
14. Profile-guided / runtime-monitoring approaches

For A7, the grimoire is the best **single-page comparison** of
the design space. A7's choice (borrow checking lite + linear
types lite via affine ownership + region scopes) is informed by
this taxonomy.

---

## Primary sources

- [Vale home](https://vale.dev/)
- [Generational references blog](https://verdagon.dev/blog/generational-references)
- [Memory safety grimoire](https://verdagon.dev/grimoire/grimoire)
- [Vale C++ post](https://verdagon.dev/blog/vale-memory-safe-cpp)
- [Vale on memory safety](https://vale.dev/memory-safe)
- [Fearless FFI](https://verdagon.dev/blog/fearless-ffi)

---

## What A7 can steal — consolidated

1. **The conceptual frame from Vale's grimoire** — a single
   document covering 14 approaches that A7 can lean on for
   future design conversations.
2. **The principle of "elide checks via ownership tracking"** —
   the same insight that drives A7's `s.ptr[i]` emission when
   bounds are proved.
3. **Region borrow checking** as a way to combine
   Cyclone-style regions with finer-grained ownership tracking.

## What A7 should not steal

1. **The runtime generational check** — incompatible with
   A7's zero-runtime-error contract.
2. **Vale's specific syntax** (A7 has its own).

## Vale as a fallback design

If A7's strict compile-time-only contract turns out to be
infeasible for real programs (the bet is it won't, but the
data isn't in), generational references are the **least bad
runtime fallback**:

- Per-deref cost is one load + comparison.
- The check is at the dereference site, easy to understand.
- The compile-time path elides most checks.
- The discipline doesn't require lifetime annotations.

If A7 ever weakens its contract to allow some runtime safety
checks, this is the model. But the working assumption is that
the contract holds; Vale is not a Phase A–E target.
