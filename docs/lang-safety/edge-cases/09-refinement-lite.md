# Gap 09 — Refinement-lite type kit

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.9](../07-language-review.md#19-refinement-types--currently-absent).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

A7 has no refinement types today. The contract requires a small,
*named* refinement vocabulary that Gaps 04, 06, 07, 11 use as the
public-facing surface for proved-property types. **Ada's `subtype`
mechanism is the direct design reference**: Ada's predefined
`Natural` (`Integer range 0 .. Integer'Last`) and `Positive`
(`Integer range 1 .. Integer'Last`) are essentially the refinements
this gap introduces, plus a few more.

## Subcases

| # | Refinement | Purpose | Ada analog |
| --- | --- | --- | --- |
| RF-01 | `Bounded<$T, $lo, $hi>` | Generic ranged integer | `subtype S is Integer range Lo .. Hi;` |
| RF-02 | `Index<$n: usize>` | Slice/array index in `[0, $n)` | `subtype Index_Type is Integer range 0 .. N-1;` |
| RF-03 | `NonZero<$T>` | Non-zero integer (for division) | No direct analog; built via `range 1 .. Integer'Last` for unsigned positive |
| RF-04 | `Positive<$T>` | `> 0` | `subtype Positive is Integer range 1 .. Integer'Last;` |
| RF-05 | `Natural<$T>` | `≥ 0` | `subtype Natural is Integer range 0 .. Integer'Last;` |
| RF-06 | `Fin<$F>` | Float without NaN/inf | Ada `'Valid` attribute checks similar property |
| RF-07 | `SafeDivisor<$T>` | Non-zero, plus `-1` excluded for signed | n/a; combine `NonZero` + signed exclusion |
| RF-08 | `Length<$n: usize>` | "Slice has exactly `n` elements" (for matrix code) | n/a directly; constraint on access types |
| RF-09 | `NonEmpty<$T>` (for slices) | Slice with `length > 0` | `array` types with `Range` constraint |
| RF-10 | Constructor `Refinement::new(x) -> ?Refinement` | Fallible construction | Ada raises `Constraint_Error`; A7 returns `Option<Refined>` |
| RF-11 | Constructor `Refinement::comptime_new(x)` for literal arguments | Compile-time check | Ada static-subtype check on literals |
| RF-12 | Implicit upcast `Refinement → BaseType` | Lossless coercion | Ada's implicit subtype-to-base conversion |
| RF-13 | Constructor must check both range *and* type-set membership | Compositional check | Ada's `Dynamic_Predicate` for non-range predicates |
| RF-14 | User-defined refinements (open) | Anyone declaring a refinement-like type | Ada permits user subtypes |
| RF-15 | Refinement composition: `Index<n>` is a `NonZero<usize>` for `n > 0` | Subtype lattice | Ada has subtype lattice naturally |
| RF-16 | Refinement in match pattern: `case Bounded::new(x): ...` | Smart constructor | n/a in Ada |
| RF-17 | Refinement in generic constraint: `fn f<$T: NonZero>(...)` | Type-set predicate | Ada generic formal `<>` types |
| RF-18 | Refinement preservation through arithmetic — `Bounded<T, lo1, hi1> + Bounded<T, lo2, hi2> = Bounded<T, lo1+lo2, hi1+hi2>` (modulo overflow) | Compile-time-computed result type | Ada's `Constraint_Error` at runtime; SPARK can prove statically |
| RF-19 | Debug printing of a refinement value | Format/Display trait | Ada's `'Image` attribute |
| RF-20 | Storage layout: `Bounded<i32, 0, 255>` packed as `u8`? | Optional optimisation | Ada's `pragma Pack` and `'Size` |

## Interactions

- **Gap 01 cast.** Casts to refinements are forbidden (only constructors).
  Casts from refinements to base types are implicit upcasts.
- **Gap 02 nullable pointers.** Refinements over reference types are
  possible (`Refined<ref T, valid_predicate>`) but rare; mostly the
  refinements operate on primitives.
- **Gap 03 definite assignment.** Refinement locals are initialised
  via constructor; DA applies normally.
- **Gap 04 NonZero division.** RF-03 is the canonical example.
- **Gap 05 stack budget.** Refinements are zero-cost wrappers; frame
  size = underlying type size (RF-20 optional optimisation aside).
- **Gap 06 typed arithmetic.** **Core interaction.** Range tracker
  publishes proved bounds; the refinement framework consumes them.
  Auto-promotion from a range-proved value to a `Bounded` happens
  here.
- **Gap 07 bounded indexing.** RF-02 `Index<n>` is the canonical
  consumer.
- **Gap 08 `Option<T>` / `Result<T, E>`.** Constructors return
  `Option<Refined>` uniformly.
- **Gap 10 affine ownership.** Refinements over `Copy` base types are
  themselves `Copy`. Refinements over non-`Copy` types inherit
  ownership semantics.
- **Gap 11 finite floats.** RF-06 `Fin<F>` is the canonical example.
- **Gap 12 FFI.** Foreign returns are base types; user constructs
  refinements explicitly.
- **Generics / type sets.** RF-17 — `NonZero`, `Positive`, etc.
  become type-set predicates. The existing `@type_set(...)`
  vocabulary needs extension.
- **Tagged unions.** A variant payload may carry a refinement;
  pattern-binding preserves the refinement type.
- **Match.** RF-16 — pattern construction via the constructor is a
  natural sugar.

## Failure modes

### False positives

- Closed-list refinements may not cover a real user need. Mitigation:
  RF-14 — allow user-defined refinements with the same shape
  (struct with private inner field + checked constructor).
- Refinement-preserving arithmetic (RF-18) requires comptime-known
  bounds. Imprecision causes more `?Refined` returns than needed.
- Generic instantiation may fail when a constraint isn't satisfied
  for some target type. Mitigation: better diagnostics.

### False negatives

- A user-defined refinement could promise more than its constructor
  proves (RF-13 — the language must check the constructor against the
  predicate). If the constructor uses an opaque function, the
  prover gives up and the refinement is only as good as the
  constructor's discipline.
- "Unsafe construction" patterns (RF-11 — `comptime_new`) are a
  footgun if the compile-time check is weak.

### Ergonomic costs

- New vocabulary words (`Bounded`, `Index`, `NonZero`, `Fin`,
  `Positive`, `Natural`, `SafeDivisor`) — a manageable list.
- Constructor + `match` everywhere is verbose. Mitigation: same
  combinators as `Option<T>` (Gap 08) — `.map`, `.and_then`.
- The promise of refinements is high — users may expect more than
  the lite version delivers. Documentation must spell out the
  closed-list nature.

### Performance costs

- None. Refinements are `struct { value: T }`; constructor calls
  inline; `.value` extracts. RF-20 (packed storage) is an
  optional optimisation.

## Open questions

- **Q09a.** Open list or closed list of refinements? Three options:
  - Closed (built-in): only the seven listed (RF-01 through RF-09).
    Simplest; least flexible.
  - Open with restrictions: users can declare refinements following
    a fixed template (RF-14). More flexible; requires more language
    machinery.
  - Open with full predicates: à la Liquid Haskell. Heavy; requires
    SMT.
- **Q09b.** `Bounded<$T, $lo, $hi>` parameterisation — `$lo` and
  `$hi` as `comptime $T` values. Requires comptime-arg support in
  generics. Today A7's `@type_set(...)` mechanism may need extension.
- **Q09c.** Refinement-preserving arithmetic (RF-18) — yes/no/scope:
  - No: arithmetic always degrades to base type.
  - Limited: addition / multiplication on `Bounded` with comptime
    bounds.
  - Full: arbitrary operations with comptime-computed bounds.
- **Q09d.** Subtype lattice (RF-15) — `Index<n>` is-a `NonZero<usize>`
  for `n > 0`. Is the lattice declared by the language (built-in
  knowledge), inferred from constructors, or stated by the user?
- **Q09e.** Auto-promotion from a range-proved value (e.g., a
  loop-induction `i: usize ∈ [1, n)` to `NonZero<usize>`). Triggered
  by which sites:
  - Function-call argument typed as `NonZero<usize>`.
  - Cast (explicit).
  - Match-arm pattern.
- **Q09f.** Refinements over composite types — `NonEmpty<[]T>`
  (a slice with `length > 0`). Yes/no/scope.
- **Q09g.** User-defined refinements (RF-14) — what's the syntactic
  shape? Three options:
  - `refined NonZero<$T> over $T where x != 0 { ... }` — first-class
    declaration syntax.
  - Struct + private constructor convention; no special syntax.
  - `@refined(predicate)` attribute on a struct.
- **Q09h.** Storage optimisation (RF-20) — auto-pack to underlying
  smallest type, or require explicit annotation?

## Source citations

- No refinement infrastructure exists today; this is greenfield.
- Generics infrastructure to extend: `a7/generics.py`,
  `a7/types.py:TypeSetType`.
- `@type_set(...)` vocabulary at `a7/passes/type_checker.py:1501-1535`.
- Stdlib target: new `a7/stdlib/refinement.py`.
- Ada inspiration: <https://learn.adacore.com/courses/intro-to-ada/chapters/strongly_typed_language.html>
  documents `Natural`, `Positive`, and the `subtype` mechanism.
- SPARK static-predicate restrictions:
  <https://docs.adacore.com/spark2014-docs/html/lrm/declarations-and-types.html>
  — the model A7 should follow (predicates without runtime input).

## Phase C decision-input summary

1. Q09a — open vs closed list. **Drives:** the entire architecture.
2. Q09b — comptime-arg shape.
3. Q09c — refinement-preserving arithmetic scope.
4. Q09e — auto-promotion sites.
5. Q09g — user-defined refinement syntax.

The rest follow.
