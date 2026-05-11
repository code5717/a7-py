# Gap 01 — Cast (`cast(T, x)`)

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.2](../07-language-review.md#12-cast--unrestricted-and-admits-intptr).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md) (Phase C).

The cast operator is the **most urgent** safety gap. The current
implementation type-checks the target type and operand but performs
**no validity check** — `cast(ref T, some_usize)` compiles and emits a
reinterpret. The job of this file is to enumerate every concrete cast
the language admits today, decide which class it falls into, and log
the open questions about which classes A7 will continue to permit.

## Subcases

A flat catalog. Each row is a real cast someone might write; the
decision column is the Phase C target.

| # | Cast | Today | Class |
| --- | --- | --- | --- |
| C-01 | `cast(i64, x: i32)` — widening signed→signed | Compiles, emits `@as(i64, x)` | **Lossless** |
| C-02 | `cast(u64, x: u32)` — widening unsigned→unsigned | Compiles, emits `@as(u64, x)` | **Lossless** |
| C-03 | `cast(i32, x: i64)` — narrowing signed→signed | Compiles, emits `@as(i32, x)`; truncates silently | **Truncating** (must return `?T`) |
| C-04 | `cast(u32, x: u64)` — narrowing unsigned→unsigned | Compiles, emits `@as(u32, x)`; truncates silently | **Truncating** |
| C-05 | `cast(i64, x: u64)` — same-width sign change | Compiles; reinterpret | **Sign-change** (must return `?T` or be `bit_cast`) |
| C-06 | `cast(u64, x: i64)` — same-width sign change | Compiles; reinterpret | **Sign-change** |
| C-07 | `cast(i32, x: u32)` — same-width sign change | Compiles | **Sign-change** |
| C-08 | `cast(usize, x: isize)` — pointer-sized cross | Compiles | **Sign-change** |
| C-09 | `cast(f64, x: i32)` — int→float | Compiles, emits `@as(f64, @floatFromInt(x))` (TBD) | **Lossless** for small ints; **truncating** for `i64→f64` over 2^53 |
| C-10 | `cast(i32, x: f64)` — float→int | Compiles; semantics depend on Zig | **Truncating + fallible** (NaN/inf → `none`; out-of-range → `none`); must return `?T` |
| C-11 | `cast(u32, x: f32)` — same | Same hazards | **Truncating + fallible** |
| C-12 | `cast(u8, x: i32)` — narrowing + range | Compiles | **Truncating** |
| C-13 | `cast(ref T, x: usize)` — **integer to pointer** | **Compiles** — the critical hole | **Forbidden** |
| C-14 | `cast(usize, x: ref T)` — pointer to integer | **Compiles** | **Forbidden** (no escape to opaque int) |
| C-15 | `cast(ref U, x: ref T)` — pointer-type punning | Compiles; arbitrary reinterpret | **Forbidden** for unrelated types; allowed for `ref T → ref void` (if void-pointers exist) |
| C-16 | `cast(ref T, x: ref T)` — identity | Compiles, no-op | **Lossless** |
| C-17 | `cast(?ref T, x: ref T)` — non-null to nullable | Should be implicit, not require `cast` | **Implicit upcast** |
| C-18 | `cast(ref T, x: ?ref T)` — nullable to non-null | Today: just emits `@as(?*T, x)`, no unwrap | **Forbidden** — only `match` may narrow |
| C-19 | `cast(u32, x: f32)` with `bit_cast` intent | Today: no separate operator | **Bit-cast** (new operator) |
| C-20 | `cast(fn(...) T, x: usize)` — int to function pointer | **Compiles** | **Forbidden** |
| C-21 | `cast(fn(B) C, x: fn(A) B)` — function-pointer cross-typing | Compiles; ABI mismatch UB | **Forbidden** |
| C-22 | `cast(EnumA, x: EnumB)` — enum cross-cast | Behaviour today unclear; likely permitted | **Forbidden** |
| C-23 | `cast(u32, x: EnumT)` — enum to underlying integer | Permitted today | **Lossless** (if discriminant fits) |
| C-24 | `cast(EnumT, x: u32)` — integer to enum (no validation) | Permitted today; can produce invalid enum | **Truncating + fallible** (must `match` against valid range) |
| C-25 | `cast([]T, x: [N]T)` — array to slice | Permitted today; implicit in most places | **Lossless** (already implicit in many cases) |
| C-26 | `cast([N]T, x: []T)` — slice to fixed array | Today: silent truncation/expansion | **Truncating + fallible** — requires `s.length == N` proof |
| C-27 | `cast([]u8, x: T)` — value to byte-slice ("punning") | Permitted today via address-of? | **Forbidden** at the value level; permitted only via explicit `&x as []u8` if at all |
| C-28 | `cast($U, x: $T)` — generic-parameter cast where the constraints disagree | Today: unclear | **Forbidden** |
| C-29 | `cast(ref T, x: opaque)` at FFI boundary | No FFI today | **FFI-only**, restricted form |
| C-30 | `cast(T, T(...))` — calling a type as a constructor | Not a cast at all; constructor syntax | n/a |

## Interactions

How this gap touches the other 11 and existing A7 features.

- **Gap 02 nullable pointers.** C-17 and C-18 above. The nullable
  split changes how cast classes treat reference types. Decision:
  `cast` cannot move between non-null and nullable; only structural
  operations (`match`, `is null`) do.
- **Gap 03 definite assignment.** Cast doesn't read or write storage,
  so interaction is indirect — but `bit_cast`'s output type is
  considered written after the cast.
- **Gap 04 NonZero division.** A literal `0` should never auto-promote
  to `NonZero<T>` through a cast. Cast classification must reject
  laundering a runtime zero into a `NonZero`.
- **Gap 05 stack budget.** No direct interaction (cast doesn't allocate).
- **Gap 06 typed arithmetic.** Cast propagates ranges. `cast(u8, x: u32)`
  with proved `x < 256` keeps the range; otherwise the cast is
  forbidden (`truncating_cast` returns `?T`). The range lattice must
  understand cast as a transfer function.
- **Gap 07 bounded indexing.** `cast(usize, x: i32)` is the common path
  to index; needs the sign-change discipline. If `x: i32` has range
  `[0, n)`, cast yields `usize` with range `[0, n)` — proved-safe.
- **Gap 08 `Option<T>` / `Result<T, E>`.** `truncating_cast` and
  `bit_cast(EnumT, u32)` return `Option<T>`; cast classification
  drives where these surface.
- **Gap 09 refinement-lite.** A `Bounded<T, lo, hi>` value cast to a
  wider `Bounded<U, lo, hi>` is lossless; narrowing requires a
  fresh range proof.
- **Gap 10 affine ownership.** `cast(ref T, x: ref T)` doesn't move;
  identity cast is a no-op. `cast` on a non-Copy type doesn't
  consume — it's structurally an alias.
- **Gap 11 finite floats.** `cast(f64, x: f64)` is a no-op; `cast(Fin<f64>, x: f64)`
  requires the constructor (already on `Fin`, not on `cast`). `cast(int, x: Fin<f64>)`
  is a *lossless float→int* path under the Fin restriction.
- **Gap 12 FFI.** Casts to opaque foreign types are the one site
  where the rules relax; the surface area is the `extern` boundary
  only.
- **Generics / type sets.** Casts in generic code must work against
  each instantiation's type set. Either generic casts are
  monomorphised and re-checked per instantiation (current A7
  approach), or the cast is restricted to operations allowed by the
  type-set constraint.
- **Tagged unions.** `cast(EnumT, x: u32)` (C-24) — the integer must
  match a known discriminant. Today's behaviour permits invalid
  enums; the discipline rules require a `match` and an `Option`
  return.
- **Match.** Cast in a match arm pattern (`case cast(T, x): ...`)
  shouldn't exist; matching already binds typed.
- **Slices/arrays.** C-25, C-26, C-27 above.

## Failure modes

### False positives (programs we now reject that shouldn't be)

- C-09 `i32 → f64` widening — should always succeed, but if we
  conservatively require an explicit `bit_cast` or `lossless_cast`,
  users will hate writing the boilerplate.
- C-17 implicit non-null → nullable. Forcing a `cast` here is gratuitous;
  the upcast should be implicit.
- C-25 array → slice. Already implicit in most contexts; should stay
  implicit.
- Generic code that worked with the permissive `cast` may stop
  compiling. Mitigation: monomorphisation-time error with a clear
  per-instantiation message.

### False negatives (programs we still admit that we shouldn't)

- Composition of permitted casts. `cast(u32, cast(f32, x: ref T))`
  — three casts each individually maybe-permitted but the chain is
  pointer→float→int→back-to-pointer. Cast classification must be
  closed under composition: if any intermediate step is forbidden,
  the chain is forbidden.
- Generic indirection. `cast($T, x: $U)` inside a generic might be
  permitted by one instantiation and forbidden by another. The
  type-checker must re-validate per instantiation.
- Calls that move through opaque interfaces (`extern fn`,
  trait/method dispatch) and re-emerge as a different pointer type.

### Ergonomic costs

- Adding three operator names (`cast`, `truncating_cast`, `bit_cast`)
  is a vocabulary cost.
- Most casts in the existing 38 examples are lossless widenings or
  array→slice; the migration cost should be small for typical code.
- Where users *do* need a narrowing cast, the new form returns
  `Option<T>` which requires a `match`. This is annoying for cases
  where the narrowing is statically safe (cast of literal `42` to
  `u8`).

### Performance costs

- None. All casts are zero-cost at runtime; the discipline is
  compile-time only.
- The exception is `truncating_cast` when the prover *can't*
  discharge the range — the runtime check survives. The prover
  should handle constant operands trivially.

## Open questions

Each becomes a decision in Phase C.

- **Q01a.** Should `cast` (the keyword) be reserved for **only**
  lossless widening, or should it accept implicit-upcast cases (array
  → slice, non-null → nullable) too? Two options:
  - Strict: `cast(T, x)` only for numeric widening; everything else
    has its own operator or is implicit.
  - Lenient: `cast(T, x)` covers all "always safe" conversions
    including upcasts; only fallible/dangerous casts use other
    operators.
- **Q01b.** What is the exact list of fallible-cast destinations?
  Candidate: `truncating_cast<T>(x) -> ?T` returns `none` when the
  value doesn't fit. Or should it return a `Result<T, CastError>`
  with a structured error?
- **Q01c.** Is `bit_cast` allowed at all? It's needed for some
  numeric work (e.g., extracting float bits as int for hashing),
  but it's a footgun. Two options:
  - Yes, restricted to same-size non-pointer types.
  - No; provide explicit `f32_bits(x: f32) -> u32` style stdlib
    helpers for the cases we need.
- **Q01d.** How does `cast` interact with enum tagging? Should
  `cast(EnumT, x: i32)` ever compile, or always require
  `EnumT::from_discriminant(i32) -> ?EnumT`?
- **Q01e.** Do we need a cast that goes between two reference types
  in the same nominal subtype lattice (when subtyping lands)? Or do
  we use a different operator (`upcast` / `as`)?
- **Q01f.** Migration: do we provide a one-off `legacy_cast` for
  internal stdlib code that must do pointer punning during the
  refactor? Or break atomically with a single PR?
- **Q01g.** Diagnostics: when a forbidden cast is attempted, the
  error message must propose the right replacement. Build a fix-it
  table mapping (source, target) → suggested operator.
- **Q01h.** Does `cast` work in a constant-evaluation context (when
  comptime-eval is implemented)? Same rules, or more permissive?

## Source citations

From the audit:

- Cast type-check: `a7/passes/type_checker.py:1800-1805` — "Cast
  expressions type-check the target type and operand, but no safety
  validation on whether the cast is valid/safe."
- Backend emission: `a7/backends/zig.py:1690-1695` — emits
  `@as(TargetType, value)`.
- Declared-but-unused errors:
  - `a7/errors.py:148` — `INVALID_CAST`
  - `a7/errors.py:149` — `UNSAFE_CAST`
- Type assignability rules (for use by the cast classifier):
  `a7/types.py:108-140` — `is_assignable_to`.
- Example impact: `examples/015_types.a7`, `examples/020_operators.a7`,
  `examples/037_language_tour.a7` are the candidates to audit first
  (each uses `cast(...)`).
- Spec section: `docs/SPEC.md` has the existing cast definition that
  needs replacement.

## Phase C decision-input summary

The Phase C document will need to answer **at least**:

1. The full cast classification table (Q01a, Q01b, Q01c, Q01d).
2. The fallible-cast return type (`?T` vs `Result<T, E>`) — Q01b.
3. Whether `bit_cast` exists — Q01c.
4. Migration policy — Q01f.
5. Diagnostics table — Q01g.
6. Comptime semantics — Q01h.

All other items in the subcase table are determined by the answers
above plus the classification rule.
