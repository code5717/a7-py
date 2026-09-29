# Gap 01 — Cast (`cast(T, x)`)

Status: Phase A research from before 2026-09-14, not a decision. Decisions are in the [ledger](../../plan/decisions.md); cast rules stay open under gate [G3](../../plan/README.md#g3-numeric-rules-beyond-wrapping).

Audit finding: [`../07-language-review.md` §1.2](../07-language-review.md#12-cast--unrestricted-and-admits-intptr).
Phase C decisions were to land in [`../08-decisions.md`](../08-decisions.md).

## Summary

Phase A rated cast the most urgent safety gap. The type checker checked
the target type and the operand, but it did not check whether the cast
was valid. `cast(ref T, some_usize)` compiled and emitted a reinterpret.

This file lists every concrete cast the language admitted, assigns each
one a target class and records the open questions about which classes A7
should keep.

## Current behavior (2026-09-16)

Note (2026-09-16): the Phase A "Today" claims no longer describe the
compiler. Evidence is a source read on 2026-09-16; no program was
compiled in this session.

- `a7/cast_classifier.py` sorts each cast into `LOSSLESS`,
  `EXPLICIT_NUMERIC`, `PROVABLE_NARROWING` or `FORBIDDEN`.
- Casts that involve a reference or function type are forbidden. So is
  every cast whose source or target is not a primitive numeric type:
  enums, arrays, slices, structs and generic parameters.
- `a7/safety.py:522-554` records a `cast` obligation for every cast.
  Integer narrowing and sign changes pass only when the source value's
  known interval fits the target type. Float-to-integer passes only for
  a finite, integral float literal that fits (`a7/safety.py:654-661`).
- `a7/backends/zig.py:1751-1775` (`_emit_cast`) refuses a cast without
  backend approval. It emits `@as`, `@floatCast`, `@intFromFloat`,
  `@floatFromInt` or `@intCast`.
- The ledger marks the old decisions D.024 (keep `cast`) and D.038
  (remove `cast`) as contradictory; neither holds, and G3 decides.
- The [memory plan](../../plan/memory.md) proposes removing
  `cast(ref T, value)` from the public surface.

## Subcases

Each row is a cast someone might write. "Phase A: today" and "Phase A:
target" are the original enumeration. "Now" is the 2026-09-16 source
read.

| # | Cast | Phase A: today | Phase A: target class | Now (2026-09-16) |
| --- | --- | --- | --- | --- |
| C-01 | `cast(i64, x: i32)`, signed widening | Compiles, emits `@as(i64, x)` | Lossless | Lossless, `@as` |
| C-02 | `cast(u64, x: u32)`, unsigned widening | Compiles, emits `@as(u64, x)` | Lossless | Lossless, `@as` |
| C-03 | `cast(i32, x: i64)`, signed narrowing | Compiles, emits `@as(i32, x)`; truncates silently | Truncating (must return `?T`) | Rejected unless the interval of `x` fits `i32` |
| C-04 | `cast(u32, x: u64)`, unsigned narrowing | Compiles, emits `@as(u32, x)`; truncates silently | Truncating | Rejected unless the interval fits |
| C-05 | `cast(i64, x: u64)`, same-width sign change | Compiles; reinterpret | Sign-change (must return `?T` or be `bit_cast`) | Rejected unless the interval fits |
| C-06 | `cast(u64, x: i64)`, same-width sign change | Compiles; reinterpret | Sign-change | Rejected unless `x` is proven non-negative and in range |
| C-07 | `cast(i32, x: u32)`, same-width sign change | Compiles | Sign-change | Rejected unless the interval fits |
| C-08 | `cast(usize, x: isize)`, pointer-sized sign change | Compiles | Sign-change | Rejected unless proven non-negative and in range |
| C-09 | `cast(f64, x: i32)`, int to float | Compiles, emits `@as(f64, @floatFromInt(x))` (TBD) | Lossless for small ints; truncating for `i64 → f64` above 2^53 | `EXPLICIT_NUMERIC`, emits `@floatFromInt`. Precision loss above 2^53 is not checked |
| C-10 | `cast(i32, x: f64)`, float to int | Compiles; semantics depend on Zig | Truncating and fallible (NaN, inf, out of range give `none`); must return `?T` | Rejected unless `x` is a finite integral float literal that fits. Failure semantics open under G1 |
| C-11 | `cast(u32, x: f32)` | Same hazards as C-10 | Truncating and fallible | Same as C-10 |
| C-12 | `cast(u8, x: i32)`, narrowing plus range | Compiles | Truncating | Rejected unless the interval fits `u8` |
| C-13 | `cast(ref T, x: usize)`, integer to pointer | Compiles: the critical hole | Forbidden | Forbidden |
| C-14 | `cast(usize, x: ref T)`, pointer to integer | Compiles | Forbidden (no escape to an opaque int) | Forbidden |
| C-15 | `cast(ref U, x: ref T)`, pointer punning | Compiles; arbitrary reinterpret | Forbidden for unrelated types; allowed for `ref T → ref void` if void pointers exist | Forbidden, with no `void` exception |
| C-16 | `cast(ref T, x: ref T)`, identity | Compiles, no-op | Lossless | Forbidden: the reference check runs before the identity check |
| C-17 | `cast(?ref T, x: ref T)`, non-null to nullable | Should be implicit, not need `cast` | Implicit upcast | `?ref T` does not exist; reference casts are forbidden |
| C-18 | `cast(ref T, x: ?ref T)`, nullable to non-null | Emits `@as(?*T, x)`, no unwrap | Forbidden; only `match` may narrow | Forbidden. Nil state is an internal fact (Gap 02) |
| C-19 | `cast(u32, x: f32)` meant as a bit cast | No separate operator | Bit-cast (new operator) | No bit-cast operator; the cast follows C-11 |
| C-20 | `cast(fn(...) T, x: usize)`, int to function pointer | Compiles | Forbidden | Forbidden |
| C-21 | `cast(fn(B) C, x: fn(A) B)`, function-pointer cross-typing | Compiles; ABI mismatch is UB | Forbidden | Forbidden |
| C-22 | `cast(EnumA, x: EnumB)`, enum cross-cast | Unclear; likely permitted | Forbidden | Forbidden (not primitive) |
| C-23 | `cast(u32, x: EnumT)`, enum to integer | Permitted | Lossless if the discriminant fits | Forbidden (not primitive) |
| C-24 | `cast(EnumT, x: u32)`, integer to enum | Permitted; can produce an invalid enum | Truncating and fallible (must `match` against the valid range) | Forbidden (not primitive) |
| C-25 | `cast([]T, x: [N]T)`, array to slice | Permitted; implicit in most places | Lossless (already implicit in many cases) | Forbidden as a cast. Implicit coercion not rechecked |
| C-26 | `cast([N]T, x: []T)`, slice to fixed array | Silent truncation or expansion | Truncating and fallible; needs a `s.length == N` proof | Forbidden |
| C-27 | `cast([]u8, x: T)`, value to byte slice | Permitted via address-of? | Forbidden at the value level; at most an explicit address-of form | Forbidden. Public address-of syntax does not exist |
| C-28 | `cast($U, x: $T)` with disagreeing constraints | Unclear | Forbidden | Generic parameter types are not primitive, so forbidden. Behavior after specialization not checked |
| C-29 | `cast(ref T, x: opaque)` at an FFI boundary | No FFI | FFI-only, restricted form | No FFI (v1 plan track 10) |
| C-30 | `T(...)`, a type called as a constructor | Constructor syntax, not a cast | n/a | n/a |

### Examples

Current A7 blocks use today's syntax. The class comments come from
`a7/cast_classifier.py` and `a7/safety.py`. Compiled 2026-09-16: every block
below parses, but only the widening block (C-01, C-02, C-09) and the struct
construction block (C-30) are accepted. The rest are rejected at the safety
stage with exit 6; each block records the message it produced. The rejections
match the class table above rather than contradicting it.

```a7
// Current A7. C-01, C-02, C-09: widening and int-to-float.
widen :: fn(small: i32, count: u32) {
    wide := cast(i64, small)     // C-01: lossless
    big := cast(u64, count)      // C-02: lossless
    ratio := cast(f64, small)    // C-09: explicit numeric
}
```

```a7
// Current A7. C-03, C-04, C-12: narrowing. Parameters carry no interval.
// Rejected (exit 6): "narrowing signed cast requires a range proof",
// "narrowing unsigned cast requires a range proof" and
// "signed-to-unsigned cast requires a non-negative proof".
narrow :: fn(total: i64, size: u64, code: i32) {
    a := cast(i32, total)        // C-03
    b := cast(u32, size)         // C-04
    c := cast(u8, code)          // C-12
}
```

```a7
// Current A7. C-05 to C-08: sign changes.
// Rejected (exit 6): "unsigned-to-signed cast requires an upper-bound proof"
// and "signed-to-unsigned cast requires a non-negative proof".
flip :: fn(u: u64, s: i64, w: u32, offset: isize) {
    a := cast(i64, u)            // C-05
    b := cast(u64, s)            // C-06
    c := cast(i32, w)            // C-07
    d := cast(usize, offset)     // C-08
}
```

```a7
// Current A7. C-10, C-11, C-19: float to integer.
// Rejected (exit 6): "float-to-int cast requires finite integral range proof".
truncate :: fn(x: f64, y: f32) {
    a := cast(i32, x)            // C-10
    b := cast(u32, y)            // C-11; C-19 when bit reinterpretation is meant
}
```

```a7
// Current A7. C-13 to C-16, C-20, C-21: reference and function casts.
// Rejected (exit 6), every line: "casts involving references or functions
// are forbidden". This is the gap that 07-language-review.md section 1.2
// reported as open; it is closed at HEAD.
Node :: struct {
    value: i32
}
Other :: struct {
    value: i64
}
BinaryOp :: fn(i32, i32) i32
UnaryOp :: fn(i32) i32

forge :: fn(n: usize, p: ref Node, op: BinaryOp) {
    a := cast(ref Node, n)       // C-13
    b := cast(usize, p)          // C-14
    c := cast(ref Other, p)      // C-15
    d := cast(ref Node, p)       // C-16
    e := cast(BinaryOp, n)       // C-20
    f := cast(UnaryOp, op)       // C-21
}
```

```a7
// Proposed (Phase A). `?ref T` does not exist in current A7.
widen_ref :: fn(p: ref Node) {
    q: ?ref Node = p             // C-17: implicit upcast, no cast
    r := cast(ref Node, q)       // C-18: forbidden; use match
}
```

```a7
// Current A7. C-22 to C-24: enum casts.
// Rejected (exit 6), every line: "only primitive numeric casts are supported".
Color :: enum {
    Red
    Green
}
Shade :: enum {
    Light
    Dark
}

convert :: fn(c: Color, n: u32) {
    a := cast(Shade, c)          // C-22
    b := cast(u32, c)            // C-23
    d := cast(Color, n)          // C-24
}
```

```a7
// Current A7. C-25 to C-27: arrays, slices and bytes.
// Rejected (exit 6), every line: "only primitive numeric casts are supported".
reshape :: fn(s: []i32) {
    arr: [4]i32 = [1, 2, 3, 4]
    view := cast([]i32, arr)     // C-25
    fixed := cast([4]i32, s)     // C-26
    bytes := cast([]u8, arr)     // C-27
}
```

```a7
// Current A7. C-28: cast to a generic parameter.
// Rejected (exit 6): "only primitive numeric casts are supported".
convert_to($T, $U) :: fn(value: $T, hint: $U) $U {
    ret cast($U, value)
}
```

```a7
// Proposed. A7 has no `extern` or FFI today. C-29.
handle := foreign_open()
file := cast(ref File, handle)
```

```a7
// Current A7. C-30: struct construction, not a cast.
Point :: struct {
    x: i32
    y: i32
}
main :: fn() {
    p := Point{x: 1, y: 2}
}
```

## Interactions

How this gap touches the other 11 gaps and existing A7 features.

- **Gap 02, nullable pointers.** C-17 and C-18. The nullable split changes
  how cast classes treat reference types. Phase A decision: `cast` cannot
  move between non-null and nullable; only structural operations
  (`match`, `is null`) can. Note (2026-09-16): the memory plan replaces
  `nil` references with optionals, so this split is not the proposed
  direction.
- **Gap 03, definite assignment.** Cast does not read or write storage, so
  the interaction is indirect. The output of a `bit_cast` counts as
  written after the cast.
- **Gap 04, NonZero division.** A literal `0` must never become a
  `NonZero<T>` through a cast. Cast classification must reject laundering
  a run-time zero into a `NonZero`.
- **Gap 05, stack budget.** No direct interaction; cast does not allocate.
- **Gap 06, typed arithmetic.** Cast propagates ranges. `cast(u8, x: u32)`
  with a proven `x < 256` keeps the range; otherwise the cast is forbidden
  and `truncating_cast` returns `?T`. The range lattice must treat cast as
  a transfer function. Note (2026-09-16): `a7/safety.py:552-553` already
  carries the interval through a cast that fits.
- **Gap 07, bounded indexing.** `cast(usize, x: i32)` is the common path to
  an index and needs the sign-change rule. If `x: i32` has range `[0, n)`,
  the cast yields a `usize` with range `[0, n)`, which proves the index
  safe.
- **Gap 08, `Option<T>` and `Result<T, E>`.** `truncating_cast` and
  `bit_cast(EnumT, u32)` return `Option<T>`. Cast classification decides
  where these appear. Spelling is open under G5.
- **Gap 09, refinement-lite.** Casting a `Bounded<T, lo, hi>` to a wider
  `Bounded<U, lo, hi>` is lossless; narrowing needs a fresh range proof.
- **Gap 10, affine ownership.** `cast(ref T, x: ref T)` does not move; the
  identity cast is a no-op. `cast` on a non-Copy type does not consume; it
  is an alias. Note (2026-09-16): the memory plan makes ownership internal
  (ledger O2).
- **Gap 11, finite floats.** `cast(f64, x: f64)` is a no-op.
  `cast(Fin<f64>, x: f64)` needs the `Fin` constructor, not `cast`.
  Phase A called `cast(int, x: Fin<f64>)` a lossless float-to-int path.
  Note (2026-09-16): `Fin` is superseded by L16 (IEEE floats) and `int` by
  L4. Finiteness alone does not make float-to-int lossless: the fraction
  and the range still matter.
- **Gap 12, FFI.** Casts to opaque foreign types are the one place where
  the rules relax, and only at the `extern` boundary.
- **Generics and type sets.** Casts in generic code must hold for each
  instantiation's type set. Either casts are re-checked per instantiation
  (the current A7 approach for generics), or a cast is limited to what the
  type-set constraint allows.
- **Tagged unions.** C-24: the integer must match a known discriminant.
  Phase A permitted invalid enums; the target rules need a `match` and an
  `Option` result.
- **Match.** A cast inside a match pattern (`case cast(T, x): ...`) should
  not exist; matching already binds typed values.
- **Slices and arrays.** C-25, C-26 and C-27.

## Failure modes

### False positives (rejected programs that should compile)

- C-09, `i32 → f64` widening, should always succeed. Requiring an explicit
  `bit_cast` or `lossless_cast` adds boilerplate users will dislike.
- C-17, non-null to nullable, should be implicit. Forcing a `cast` adds
  nothing.
- C-25, array to slice, is already implicit in most contexts and should
  stay implicit.
- Generic code that relied on the permissive `cast` may stop compiling.
  Mitigation: a per-instantiation error with a clear message.

### False negatives (accepted programs that should be rejected)

- Composed casts. In `cast(u32, cast(f32, x: ref T))` each step may look
  allowed, but the chain is pointer to float to int and back. The
  classification must be closed under composition: if any step is
  forbidden, the chain is forbidden. Note (2026-09-16): the classifier
  rejects the inner reference cast, so this chain fails at its first step.
- Generic indirection. `cast($T, x: $U)` may be allowed for one
  instantiation and forbidden for another. The type checker must
  re-validate each instantiation.
- Values that pass through opaque interfaces (`extern fn`, trait or method
  dispatch) and come back as a different pointer type.

### Ergonomic costs

- Three operator names (`cast`, `truncating_cast`, `bit_cast`) add
  vocabulary.
- Phase A counted 38 examples, and most casts in them were lossless
  widenings or array-to-slice conversions, so migration should be small.
  Note (2026-09-16): there are now 43 examples (000–042), and five use
  `cast(`: 026, 029, 033, 041 and 042.
- A needed narrowing cast returns `Option<T>` and requires a `match`. This
  is annoying when the narrowing is statically safe, such as casting the
  literal `42` to `u8`.

```a7
// Proposed (Phase A). `truncating_cast` does not exist.
match truncating_cast(u8, code) {
    case some(byte): {
        io.println("{}", byte)
    }
    case none: {
        io.println("out of range")
    }
}
```

### Performance costs

- None: casts cost nothing at run time, and the rules are compile-time
  only.
- The exception is `truncating_cast` when the prover cannot discharge the
  range; then the run-time check stays. The prover should handle constant
  operands trivially.

## Open questions

Each question was to become a Phase C decision. G3 now owns them.

- **Q01a.** Is `cast` reserved for lossless widening only, or does it also
  cover implicit upcasts (array to slice, non-null to nullable)?
  - Strict: `cast(T, x)` only for numeric widening; everything else has
    its own operator or is implicit.
  - Lenient: `cast(T, x)` covers every always-safe conversion, including
    upcasts; only fallible or dangerous casts use other operators.
  - Note (2026-09-16): the current classifier is neither. It also admits
    proven narrowing and int-to-float under `cast`.
- **Q01b.** What are the fallible cast forms? Candidate:
  `truncating_cast<T>(x) -> ?T`, which returns `none` when the value does
  not fit. Or a `Result<T, CastError>` with a structured error?
- **Q01c.** Is `bit_cast` allowed? Some numeric work needs it, such as
  reading float bits as an integer for hashing, but it is a footgun.
  - Yes, limited to same-size non-pointer types.
  - No; provide stdlib helpers such as `f32_bits(x: f32) -> u32`.
- **Q01d.** How does `cast` interact with enum tags? Should
  `cast(EnumT, x: i32)` ever compile, or should it always need
  `EnumT::from_discriminant(i32) -> ?EnumT`?
- **Q01e.** Is a cast needed between two reference types in one nominal
  subtype lattice, once subtyping exists? Or does that use a separate
  operator (`upcast` or `as`)?
- **Q01f.** Migration: provide a one-off `legacy_cast` for internal stdlib
  code that must pun pointers during the refactor, or break atomically in
  one PR?
- **Q01g.** Diagnostics: a forbidden cast must propose the right
  replacement. Build a fix-it table mapping (source, target) to the
  suggested operator.
- **Q01h.** Does `cast` work in constant evaluation, once it exists? Same
  rules, or more permissive?

```a7
// Proposed (Phase A). Neither `bit_cast` nor `f32_bits` exists. Q01c.
bits := bit_cast(u32, x)
same := f32_bits(x)
```

## Source citations

From the Phase A audit. Line numbers describe the tree at that time;
2026-09-16 locations follow each item.

- Cast type check: `a7/passes/type_checker.py:1800-1805`, "Cast
  expressions type-check the target type and operand, but no safety
  validation on whether the cast is valid/safe." Now `visit_cast` at
  `type_checker.py:1876`, which records types only; validation moved to
  `a7/safety.py:522-554` and `a7/cast_classifier.py`.
- Backend emission: `a7/backends/zig.py:1690-1695`, emits
  `@as(TargetType, value)`. Now `zig.py:1751-1775`.
- Error codes Phase A called declared but unused: `a7/errors.py:148`
  `INVALID_CAST` and `a7/errors.py:149` `UNSAFE_CAST`. Now
  `errors.py:149-150`; `safety.py:540` raises `UNSAFE_CAST`.
- Assignability rules for the classifier: `a7/types.py:108-140`,
  `is_assignable_to`. Still at those lines.
- Examples to audit: Phase A named `examples/015_types.a7` and
  `examples/020_operators.a7`. Note (2026-09-16): neither contains
  `cast(`; see the example count above.
- Spec: `docs/SPEC.md` holds the cast definition to replace.

## Phase C decision inputs

Phase C must answer at least:

1. The full cast classification table (Q01a, Q01b, Q01c, Q01d).
2. The fallible cast result type, `?T` or `Result<T, E>` (Q01b).
3. Whether `bit_cast` exists (Q01c).
4. Migration policy (Q01f).
5. The diagnostics table (Q01g).
6. Constant-evaluation semantics (Q01h).

The rest of the subcase table follows from these answers and the
classification rule.
