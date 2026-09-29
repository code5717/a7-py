# `comparative/`: per-language studies

Status: Phase B research from before 2026-09-14. Where it conflicts with the
ledger in [`../../plan/decisions.md`](../../plan/decisions.md) or the
[memory plan](../../plan/memory.md), those documents win.

## Summary

Each file studies how one reference language handles the 12 safety gaps from
[`../07-language-review.md`](../07-language-review.md). Each ends with what A7
should adopt and what it should avoid. `ada-deep-dive.md` is the exception. It
covers Ada by feature area rather than by gap.

The studies use research notation such as `Option<T>`, `Bounded<T, lo, hi>` and
`NonZero<T>`. Current A7 spells generic instances with parentheses, for example
`Table(T)`. None of these names is approved syntax.

Note (2026-09-16): several recommendations repeated across these files are
superseded:

| Earlier recommendation | Current state |
| --- | --- |
| Finite floats through `Fin<F>` (gap 11) | Withdrawn. Floats follow IEEE 754 as in Zig and C (L16, plan gate G1) |
| Range proofs for `+`, `-`, `*` (gap 06) | Ordinary `+`, `-`, `*` wrap (L5). Proofs remain for division, casts, shifts and sizes (gate G3) |
| `cast` / `truncating_cast` / `bit_cast` (gap 01) | Open under gate G3, including the D.024/D.038 contradiction |
| Parameter-mode keywords (`inout`, `borrow`, `sink`) and inferred modes (gap 10) | Not accepted. Argument bindings are immutable (L6); no mode syntax is approved |
| Explicit `del` and user-visible affine moves (gap 10) | Memory is automatic and invisible (L15, L17–L22). The memory plan removes `del` from ordinary code (gate M3) and makes ownership internal |
| Stored `ref T` and `?ref T` | `ref` becomes parameter-only (gate M4). Absence uses optionals over values |
| No runtime checks of any kind | The memory plan lists residual runtime checks with defined outcomes (section 6, gate M16). The design rule that emitted code must not rely on a Zig safety check that ReleaseFast removes is intent, not current behavior: integer overflow relies on one today (gate G3) |
| No arbitrary-precision `int`, `uint` or `number` | These types are removed; integers have explicit widths (L3, L4) |

## Index

| File | Language | Why study it |
| --- | --- | --- |
| [`ada.md`](./ada.md) | Ada and SPARK, 12-gap walk | Industrial reference for static safety. SPARK has a Rust-inspired ownership model in production |
| [`ada-deep-dive.md`](./ada-deep-dive.md) | Ada, whole language | Distinct types, packages, generics, tasking and aspect specifications, beyond the 12 gaps |
| [`rust.md`](./rust.md) | Rust | Upper bound of compile-time safety expressiveness; the bar simpler designs are measured against |
| [`hylo.md`](./hylo.md) | Hylo (formerly Val) | Compile-time memory safety without lifetime annotations, through mutable value semantics |
| [`zig.md`](./zig.md) | Zig | A7's backend. Shows what `-O ReleaseFast` removes, so emitted code stays sound |
| [`cyclone.md`](./cyclone.md) | Cyclone | First serious safe-C dialect; region inference with about 8% migration cost from legacy C |
| [`pony.md`](./pony.md) | Pony | Six reference capabilities for race-free concurrency |
| [`austral.md`](./austral.md) | Austral | Pure linear types; a 600-line borrow checker shows the implementation is tractable |
| [`swift.md`](./swift.md) | Swift | Largest production use of `borrowing`, `consuming` and `inout` |
| [`mojo.md`](./mojo.md) | Mojo | A current language with goals close to A7's earlier plan |
| [`vale.md`](./vale.md) | Vale | Generational references as a runtime-checked fallback; a useful taxonomy of approaches |
| [`inko-koka-verona.md`](./inko-koka-verona.md) | Inko, Koka, Verona | Short profiles: isolated heaps, effect tracking, region-based concurrency |

The set covers 13 languages in 12 files.

### Missing studies

There is no study of Odin or Jai. The ledger names both: L5 takes Odin-style
wrapping arithmetic, and L15 cites Jai, Odin and Zig for predictable, fast
generated code (not for their manual memory model; see L21). A study of each
would fill that gap.

## How to use this directory

For each design decision in Phase C
([`../08-decisions.md`](../08-decisions.md)):

1. Read the Phase A edge-case file, for example
   [`../edge-cases/01-cast.md`](../edge-cases/01-cast.md), to see what A7 must
   decide.
2. Read three to five of these studies to see what each language did and why.
3. Apply their adopt and avoid lists.
4. Record the decision in `08-decisions.md` with citations.

Note (2026-09-16): new decisions go to
[`../../plan/decisions.md`](../../plan/decisions.md) under the approval rule.
Research recommendations are not approval.

## Cross-cutting patterns

### A. Non-null references by default

Rust (`&T`), Hylo, Swift, Mojo, Inko and Vale treat non-null as the default and
make nullability opt-in through `Option<T>` or `?T`. Ada is the exception among
the studied languages: its access types are nullable by default, and `not null`
is opt-in. Nullable-by-default references, as in C and permissive Cyclone code,
are widely considered a design mistake.

Conclusion at the time: A7's `ref T` / `?ref T` split is uncontroversial.

Note (2026-09-16): the memory plan removes stored `ref` values and `nil`
(gates M4, M6). Absence is expressed with optionals over values, so the
non-null default holds without a `?ref T` form.

### B. Parameter modes instead of lifetimes

Hylo, Swift (5.9 and later) and Mojo use parameter-mode references only: no
storable references and no lifetimes. Only Rust, and SPARK with caution, ship
full lifetime or ownership annotations.

Conclusion at the time: A7 should skip lifetimes and use parameter modes.

Note (2026-09-16): A7 still has no lifetimes, and `ref` parameters cannot be
stored or returned (memory plan contract 8.3). No parameter-mode syntax is
approved (L6), and the proposed mode keywords D.040, D.041 and D.049 were not
accepted.

### C. Tagged unions for failure, not exceptions

SPARK forbids exceptions. Rust, Swift, Hylo, Pony and Vale use sum types such as
`Option` and `Result`. Only languages in the Java and C# line use exceptions as
the main error mechanism.

Conclusion: A7's choice of `Option` and `Result` with no exceptions matches the
modern consensus. Error shapes remain under plan gate G5.

### D. Ranged subtypes for arithmetic safety

Ada's `Natural`, `Positive` and user-defined ranges are the reference. SPARK
proves them at compile time. A7's proposed `Bounded<T, lo, hi>`, `Index<n>` and
`NonZero<T>` are direct ports.

Conclusion at the time: A7's refinement-lite plan rests on long Ada practice.

Note (2026-09-16): wrapping `+`, `-`, `*` (L5) removes overflow as a use for
ranges. Ranges may still serve division, narrowing casts, shifts and indexing
under gate G3. The ledger does not decide whether the refinement types ship.

### E. Compile-time discipline versus runtime checks

Languages that promise memory safety at compile time (Rust, Hylo, Austral)
accept a more restrictive language for stronger guarantees. Languages that
promise runtime safety (Zig `ReleaseSafe`, Swift's exclusivity fallback, Vale's
generation checks) sit at a different design point.

Conclusion at the time: A7's compile-time-only contract is the strict end of the
spectrum, with solid precedent.

Note (2026-09-16): the memory plan keeps compile-time ownership but lists a
small set of residual runtime work with defined outcomes, such as `Id(T)` lookup
returning an optional and allocation failure handling (memory plan section 6,
gates M2 and M16).

### F. A borrow checker is not required

Rust built the full borrow checker. Hylo, Vale, Inko and Mojo reach similar
safety without one. The cost is a less expressive language, with no storable
references. The benefit is a much simpler implementation with no lifetime
annotations.

Conclusion: A7 does not need a user-facing borrow checker. The memory plan keeps
this: ownership, escape analysis and exclusivity checks are internal compiler
layers, and users never write borrows or lifetimes.

### G. Foreign code is the one trusted boundary

Every safe language has a foreign-function escape: Rust `unsafe`, Swift
`@_cdecl`, Ada `pragma Import`, Hylo `unsafe`, Pony `@ffi_call`, and SPARK
imports summarised by contracts. The rule is the same everywhere: the language
trusts the foreign side and cannot police it.

Conclusion at the time: A7's `extern fn ... -> Result<T, E>` rule matches the
industry consensus.

Note (2026-09-16): the memory plan adds native binding descriptors that declare
borrowing, retention and returned storage (gate M12).

## What the set says about A7

Findings recorded after reading all 13 languages:

1. A7's design sits in the middle of the design space, neither at the leading
   edge nor at the conservative end.
2. Each planned feature had two to four production languages behind it:
   parameter modes, `Option` and `Result`, ranged refinements, `del`
   consumption, no exceptions and no `unsafe`.
3. The combination was the novel part. No existing language combined this set
   with a "zero runtime errors" guarantee. SPARK was closest, so A7 was
   described as "SPARK Lite" in spirit.
4. The Ada deep dive found five further ideas that are not safety features:
   distinct types, `static N` generic parameters, `private` sections,
   hierarchical modules and aspect specifications.

Note (2026-09-16): item 2 is partly superseded. Parameter modes and `del` are no
longer the plan (L6; memory plan gate M3). The memory plan adds a combination no
studied language offers: invisible compile-time memory management with value
semantics, inferred extents and `Table(T)`/`Id(T)`, measured against C-like
performance (L15, L17–L22).
