# Gap 09 — Refinement-lite type kit

Status: Phase A research from before 2026-09-14. Not approved. Current decisions
are in the [v1 decision ledger](../../plan/decisions.md).

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.9](../07-language-review.md#19-refinement-types--currently-absent).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

## Summary

A7 has no refinement types. The Phase A contract asked for a small, named
refinement vocabulary that Gaps 04, 06, 07 and 11 would use as the public surface
for proved-property types.

Ada's `subtype` mechanism is the direct design reference. Ada's predefined
`Natural` (`Integer range 0 .. Integer'Last`) and `Positive`
(`Integer range 1 .. Integer'Last`) are close to the refinements proposed here.

## Audit notes (2026-09-16)

- Note (2026-09-16): the user-facing kit is superseded as a direction.
  `08-decisions.md` D.020 (line 577, recorded ACCEPTED) keeps range analysis inside
  the compiler: "no `Bounded<T, lo, hi>`, no `Index<n>`, no `NonZero<T>`".
  [`SAFETY_CONTRACT.md`](../../SAFETY_CONTRACT.md) states that facts are "internal
  compiler data, not public language types". The ledger supersedes D.020's
  `int`/`uint`/`number` wording (L4). The subcases below remain a record of the
  properties the internal fact system must track.
- Note (2026-09-16): RF-06 `Fin<$F>` is superseded by ledger L16; floats are IEEE
  and NaN and infinity are ordinary values.
- Note (2026-09-16): RF-18 says "modulo overflow". Ledger L5 makes `+ - *` wrap, so
  a range computed for `+` is only valid when the result is proved not to wrap.
- Note (2026-09-16): the Gap 10 row assumes a `Copy` / non-`Copy` split. The
  [memory plan](../../plan/memory.md) (proposed) makes copy the meaning of
  assignment; only resources are move-only.
- Note (2026-09-16): the Ada `NonZero` analog was written as "built via `range 1 ..
  Integer'Last` for unsigned positive". That describes `Positive`, not non-zero for
  signed types.

## Subcases

| # | Refinement | Purpose | Ada analog |
| --- | --- | --- | --- |
| RF-01 | `Bounded<$T, $lo, $hi>` | Generic ranged integer | `subtype S is Integer range Lo .. Hi;` |
| RF-02 | `Index<$n: usize>` | Index in `[0, $n)` | `subtype Index_Type is Integer range 0 .. N-1;` |
| RF-03 | `NonZero<$T>` | Non-zero integer, for division | No direct analog; `range 1 .. Integer'Last` covers unsigned positive |
| RF-04 | `Positive<$T>` | `> 0` | `subtype Positive is Integer range 1 .. Integer'Last;` |
| RF-05 | `Natural<$T>` | `≥ 0` | `subtype Natural is Integer range 0 .. Integer'Last;` |
| RF-06 | `Fin<$F>` | Float without NaN or infinity | Ada `'Valid` checks a similar property |
| RF-07 | `SafeDivisor<$T>` | Non-zero, and not `-1` for signed types | n/a; `NonZero` plus the signed exclusion |
| RF-08 | `Length<$n: usize>` | Slice with exactly `n` elements (matrix code) | n/a; a constraint on access types |
| RF-09 | `NonEmpty<$T>` (slices) | Slice with `length > 0` | Array types with a `Range` constraint |
| RF-10 | `Refinement::new(x) -> ?Refinement` | Fallible construction | Ada raises `Constraint_Error`; A7 returns `Option<Refined>` |
| RF-11 | `Refinement::comptime_new(x)` for literals | Compile-time check | Ada static-subtype check on literals |
| RF-12 | Implicit upcast `Refinement → BaseType` | Lossless coercion | Ada's implicit subtype-to-base conversion |
| RF-13 | Constructor checks range and type-set membership | Compositional check | Ada `Dynamic_Predicate` for non-range predicates |
| RF-14 | User-defined refinements (open) | User types that behave like refinements | Ada permits user subtypes |
| RF-15 | Composition: `Index<n>` is a `NonZero<usize>` for `n > 0` | Subtype lattice | Ada has a natural subtype lattice |
| RF-16 | In a match pattern: `case Bounded::new(x): ...` | Smart constructor | n/a |
| RF-17 | In a generic constraint: `fn f<$T: NonZero>(...)` | Type-set predicate | Ada generic formal `<>` types |
| RF-18 | Preserved through arithmetic: `Bounded<T, lo1, hi1> + Bounded<T, lo2, hi2> = Bounded<T, lo1+lo2, hi1+hi2>` (modulo overflow) | Result type computed at compile time | Ada checks at run time (`Constraint_Error`); SPARK can prove statically |
| RF-19 | Debug printing of a refinement value | Format/Display trait | Ada `'Image` |
| RF-20 | Storage: `Bounded<i32, 0, 255>` packed as `u8`? | Optional optimization | Ada `pragma Pack` and `'Size` |

Note (2026-09-16) on RF-02 and RF-15: `Index<n>` values include 0, so `Index<n>` is
not a `NonZero<usize>` for any `n`. RF-15 and Q09d state the lattice as written in
Phase A; the example is wrong as stated.

## Examples

RF-10, RF-12 and RF-16, construction and use:

```a7
// Proposed (superseded as a user surface by D.020; not implemented)
Percent :: Bounded(u8, 0, 100)

main :: fn() {
    p := Percent.new(42)          // RF-10: ?Percent
    match p {
        case some(v): {
            raw: u8 = v           // RF-12: implicit upcast
            io.println("{}%", raw)
        }
        case nil: { io.println("out of range") }
    }
}
```

RF-13 and RF-14, a user-defined refinement with a checked constructor:

```a7
// Proposed (Q09g option 2: struct plus private constructor; not implemented)
EvenU32 :: struct {
    value: u32                    // private in the proposal
}

even_new :: fn(x: u32) ?EvenU32 {
    if x % 2 == 0 {               // RF-13: the constructor must prove the predicate
        ret EvenU32{value: x}
    }
    ret nil
}
```

RF-19, printing a refinement value:

```a7
// Proposed (not implemented)
p := Percent.comptime_new(75)     // RF-11
io.println("p = {}", p)           // prints "p = 75", the base value
```

## Interactions

| Area | Interaction |
| --- | --- |
| Gap 01 cast | Casts to refinements are forbidden; only constructors create them. Casts to base types are implicit upcasts. |
| Gap 02 nullable pointers | Refinements over references (`Refined<ref T, valid_predicate>`) are possible but rare; most refinements are over primitives. |
| Gap 03 definite assignment | Refinement locals are initialized by constructors; definite assignment applies normally. |
| Gap 04 NonZero division | RF-03 is the canonical example. |
| Gap 05 stack budget | Zero-cost wrappers; frame size equals the base type size (RF-20 aside). |
| Gap 06 typed arithmetic | Core interaction. The range tracker publishes proved bounds and the refinement framework consumes them. Auto-promotion from a range-proved value to `Bounded` happens here. |
| Gap 07 bounded indexing | RF-02 `Index<n>` is the canonical consumer. |
| Gap 08 `Option<T>` / `Result<T, E>` | Constructors return `Option<Refined>` uniformly. |
| Gap 10 affine ownership | Refinements over `Copy` base types are `Copy`; over non-`Copy` types they inherit ownership. |
| Gap 11 finite floats | RF-06 `Fin<F>` is the canonical example. |
| Gap 12 FFI | Foreign returns are base types; the user constructs refinements. |
| Generics / type sets | RF-17: `NonZero`, `Positive` and the others become type-set predicates. The `@type_set(...)` vocabulary needs extension. |
| Tagged unions | A variant payload may carry a refinement; pattern binding keeps the refinement type. |
| Match | RF-16: constructing in a pattern is natural sugar. |

## Failure modes

### False positives

- A closed list may miss a real need. Mitigation: RF-14, user-defined refinements
  with the same shape (struct with a private inner field and a checked
  constructor).
- Refinement-preserving arithmetic (RF-18) needs comptime-known bounds. Imprecision
  causes more `?Refined` returns than needed.
- Generic instantiation may fail when a constraint does not hold for some target
  type. Mitigation: better diagnostics.

### False negatives

- A user-defined refinement can promise more than its constructor proves. RF-13
  requires the language to check the constructor against the predicate. If the
  constructor calls an opaque function, the prover gives up and the refinement is
  only as good as the constructor.
- `comptime_new` (RF-11) is a footgun if the compile-time check is weak.

### Ergonomic costs

- New words: `Bounded`, `Index`, `NonZero`, `Fin`, `Positive`, `Natural`,
  `SafeDivisor`. A manageable list.
- Constructor plus `match` everywhere is verbose. Mitigation: the `Option<T>`
  combinators from Gap 08 (`.map`, `.and_then`).
- Users may expect more than the lite version delivers. Documentation must state
  that the list is closed.

### Performance costs

- None. A refinement is `struct { value: T }`; constructors inline and `.value`
  extracts. RF-20 packed storage is optional.

## Open questions

- **Q09a.** Open or closed list?
  - Closed: only the built-ins RF-01 to RF-09. Simplest; least flexible.
  - Open with restrictions: users declare refinements from a fixed template
    (RF-14). More flexible; more machinery.
  - Open with full predicates, as in Liquid Haskell. Heavy; needs SMT.
- **Q09b.** `Bounded<$T, $lo, $hi>` takes `$lo` and `$hi` as `comptime $T` values.
  That needs comptime arguments in generics; `@type_set(...)` may need extension.
- **Q09c.** Refinement-preserving arithmetic (RF-18):
  - No: arithmetic always degrades to the base type.
  - Limited: addition and multiplication on `Bounded` with comptime bounds.
  - Full: any operation with comptime-computed bounds.
- **Q09d.** Subtype lattice (RF-15): is it built into the language, inferred from
  constructors, or stated by the user?
- **Q09e.** Auto-promotion from a range-proved value (for example loop variable
  `i: usize ∈ [1, n)` to `NonZero<usize>`). Which sites trigger it?
  - A call argument typed `NonZero<usize>`.
  - An explicit cast.
  - A match-arm pattern.
- **Q09f.** Refinements over composite types such as `NonEmpty<[]T>`: yes, no or
  limited scope?
- **Q09g.** Syntax for user-defined refinements (RF-14):
  - `refined NonZero<$T> over $T where x != 0 { ... }`, a first-class declaration.
  - Struct plus private constructor by convention; no new syntax.
  - A `@refined(predicate)` attribute on a struct. Note (2026-09-16): CLAUDE.md
    lists intrinsics other than `@type_set` as parsed-only or reserved.
- **Q09h.** Storage (RF-20): pack automatically into the smallest type, or require
  an annotation?

## Source citations

- No refinement infrastructure exists; greenfield.
- Generics infrastructure to extend: `a7/generics.py`, `a7/types.py:TypeSetType`.
- `@type_set(...)` vocabulary at `a7/passes/type_checker.py:1501-1535`.
  Note (2026-09-16): stale; those lines now hold format-placeholder counting and
  the start of `_check_generic_constraints`. The current `@type_set` location was
  not re-verified.
- Stdlib target: a new `a7/stdlib/refinement.py`.
- Ada: <https://learn.adacore.com/courses/intro-to-ada/chapters/strongly_typed_language.html>
  documents `Natural`, `Positive` and `subtype`.
- SPARK static predicates:
  <https://docs.adacore.com/spark2014-docs/html/lrm/declarations-and-types.html>.
  This is the model A7 should follow: predicates without runtime input.

## Phase C decision-input summary

1. Q09a — open vs closed list. Drives the whole architecture.
2. Q09b — comptime-argument shape.
3. Q09c — refinement-preserving arithmetic scope.
4. Q09e — auto-promotion sites.
5. Q09g — user-defined refinement syntax.

The rest follow from these.
