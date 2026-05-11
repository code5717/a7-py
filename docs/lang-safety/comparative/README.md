# `comparative/` — Per-language deep dives

Phase B artifacts in the `docs/lang-safety/` research process.
Each file walks how a reference language handles each of the 12
gaps from `../07-language-review.md`, and tells you what A7
should and should not take.

| File | Language | Why study it |
| --- | --- | --- |
| [`ada.md`](./ada.md) | Ada / SPARK (12-gap walk-through) | Industrial reference for static safety; the SPARK ownership model is Rust-inspired in production |
| [`ada-deep-dive.md`](./ada-deep-dive.md) | Ada — the whole language | Distinct types, packages, generics, tasking, aspect specifications — inspirations beyond the 12 gaps |
| [`rust.md`](./rust.md) | Rust | Upper bound of expressiveness; the bar every "simpler" approach is measured against |
| [`hylo.md`](./hylo.md) | Hylo (formerly Val) | The cleanest reference for *compile-time memory safety without lifetime annotations* — A7's target model |
| [`zig.md`](./zig.md) | Zig | A7's backend; understand exactly what `-O ReleaseFast` removes so codegen discipline holds |
| [`cyclone.md`](./cyclone.md) | Cyclone | First serious safe-C dialect; region inference with 8% migration cost from legacy C |
| [`pony.md`](./pony.md) | Pony | Six reference capabilities for race-free concurrency; future A7 concurrency model |
| [`austral.md`](./austral.md) | Austral | Pure linear types; 600-line borrow checker proves implementation tractable |
| [`swift.md`](./swift.md) | Swift | Largest production deployment of `borrowing`/`consuming`/`inout` |
| [`mojo.md`](./mojo.md) | Mojo | Current incumbent doing essentially what A7 plans; validates the target is reachable |
| [`vale.md`](./vale.md) | Vale | Generational references as a runtime-tinged fallback; useful taxonomy of approaches |
| [`inko-koka-verona.md`](./inko-koka-verona.md) | Inko, Koka, Verona (short profiles) | Three additional safe languages: isolated heaps, effect tracking, region-based concurrency |

## How to use this directory

For each design decision in Phase C (`../08-decisions.md`):

1. Open the relevant Phase A edge-case file (e.g.
   `../edge-cases/01-cast.md`) to see what A7 must decide.
2. Check **3–5 of these comparative files** to see what each
   reference language did and why.
3. Apply the "A7 can steal / cannot steal" guidance from each.
4. Write the decision in `08-decisions.md` with citations.

## Cross-cutting insights from the whole set

Reading all the comparative files together, several
**consistent design patterns** emerge:

### A. Non-null references by default

Ada (`not null`), Rust (`&T`), Hylo, Swift, Mojo, Inko, Vale —
**every modern safe language treats non-null as the default** and
nullability as an opt-in via `Option<T>` or `?T`. The default
in legacy C/Cyclone-permissive code (nullable by default) is
considered a design mistake.

⇒ **A7's `ref T` / `?ref T` split is uncontroversial.**

### B. Parameter modes over lifetimes

Hylo, Swift (5.9+), Mojo all use **parameter-mode-only
references** (no storable references, no lifetimes). Only Rust
and SPARK (cautiously) ship full lifetime annotations.

⇒ **A7's plan to skip lifetimes and use parameter modes only is
   well-supported by the literature.**

### C. Tagged unions for fallibility, not exceptions

Ada/SPARK explicitly forbids exceptions; Rust, Swift, Hylo,
Pony, Vale use sum types / `Option` / `Result`. Only Java/C#-
lineage languages use exceptions as the primary error
mechanism.

⇒ **A7's `Option<T>` / `Result<T, E>` choice (no exceptions) is
   the modern consensus.**

### D. Ranged subtypes for arithmetic safety

Ada's predefined `Natural`, `Positive`, and user-defined ranges
are the canonical reference. SPARK proves them at compile time.
A7's `Bounded<T, lo, hi>` / `Index<n>` / `NonZero<T>` are direct
ports.

⇒ **A7's refinement-lite plan is solidly grounded in 40-year-old
   Ada practice.**

### E. Compile-time discipline beats runtime checks

Every language that promises memory safety **at compile time**
(Rust, Hylo, Austral, A7) accepts a more restrictive language
in exchange for stronger guarantees. Languages that promise
**runtime safety** (Zig's `ReleaseSafe`, Swift's exclusivity
fallback, Vale's generation check) reach a different design
point.

⇒ **A7's compile-time-only contract is the strict end of the
   spectrum.** The trade is real but the precedent is solid.

### F. Borrow checkers are not strictly required

Rust pioneered the full borrow checker; Hylo, Vale, Inko,
Mojo demonstrate that *similar* safety is achievable without
one. The cost: less expressive language (no storable
references); the benefit: vastly simpler implementation,
no lifetime annotations.

⇒ **A7's choice to not build a borrow checker is supported by
   half a dozen production languages.**

### G. FFI is the single allowed safety boundary

Every safe language has an FFI escape: Rust's `unsafe`, Swift's
`@_cdecl`, Ada's `pragma Import`, Hylo's `unsafe`, Pony's
`@ffi_call`, SPARK's contract-summarised imports. The discipline
is uniform: **the foreign side is trusted**; the language can't
police it.

⇒ **A7's `extern fn ... -> Result<T, E>` discipline matches the
   industry consensus.**

## What the comparative work tells us about A7

After reading all 11 reference languages:

1. A7's design is **squarely in the middle of the design space**
   — not at the bleeding edge, not at the conservative end.
2. The features A7 plans to ship (parameter modes, `Option`/
   `Result`, ranged refinements, `del` consumption, no
   exceptions, no `unsafe`) **each individually has 2–4
   production languages backing the choice**.
3. The most novel A7 contribution is **the combination**: every
   single feature exists in some language, but no existing
   language combines exactly this set with A7's
   "zero runtime errors" guarantee. The closest is SPARK; A7 is
   "SPARK Lite" in spirit.
4. The Ada deep-dive (`ada-deep-dive.md`) surfaced five
   non-safety inspirations for A7 (distinct types, `static N`
   generics, `private` sections, hierarchical modules, aspect
   specifications). None are safety-critical but each would
   improve A7.
