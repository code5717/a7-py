# Gap 11 — Finite floats (`Fin<f>` and NaN/inf discipline)

Status: Phase A research from before 2026-09-14. The finite-only default is
superseded by ledger L16; current decisions are in the
[v1 decision ledger](../../plan/decisions.md).

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.11](../07-language-review.md#111-floating-point--nan--inf-flow-silently).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

## Summary

In Phase A, `f32` and `f64` carried NaN and infinity silently through arithmetic
and into integer conversions. The Phase A contract required one of:

- (a) a `Fin<F>` refined type for code that wants total arithmetic; or
- (b) explicit handling at each operation that may produce a non-finite value.

Ada offers a partial analog through the `'Valid` attribute and constrained
subtypes. This enumeration took a refinement-based path.

## Audit notes (2026-09-16)

- Note (2026-09-16): superseded by ledger L16. Floats follow Zig and C: IEEE 754
  values, so NaN and infinity are ordinary values. Arithmetic is strict by default,
  and result-changing optimizations need explicit opt-in. Sub-decisions remain in
  gate G1. Open decision O1 (IEEE or finite-only) is resolved by L16.
- Note (2026-09-16): `Fin<F>` is no longer the default or a required wrapper.
  Whether an optional library refinement survives is not decided. FF-15 (literals
  refined to `Fin`), Q11a option 3 (strict) and Q11h assume the superseded default.
- Note (2026-09-16): FF-05 uses `int`, removed by ledger L4. The conversion
  operator is open under gate G3; `08-decisions.md` D.024 and D.038 contradict each
  other on `cast(T, x)`.
- Note (2026-09-16): the FF-05 "Today" entry is stale. Source reading (not run):
  the safety pass rejects a float-to-integer cast unless it proves a finite
  integral range, with the message "float-to-int cast requires finite integral
  range proof" (`a7/safety.py:545-546`).
- Note (2026-09-16): FF-01 and FF-02 are stale in the same way. Source reading (not
  run): the safety pass collects a non-zero-divisor obligation for every `/` and
  `%` without checking operand type (`a7/safety.py:408-409`, `559-565`). A float
  division by an unproved divisor is therefore rejected. This was observed on
  2026-09-15: `zero: f64 = 0.0` then `ratio := zero / zero` fails with exit 6,
  "division/modulo divisor must be non-zero" (v1 plan, gate G1). Under L16,
  whether float division should carry that obligation is a G1 question.
- Note (2026-09-16): planning research
  (`docs/plan/research/memory/notes-f-plan-memory-research.md`) records that NaN
  comparisons are false under IEEE, so float guards cannot become range facts.

## Subcases

| # | Pattern | Today (Phase A) | Decision target (Phase A) |
| --- | --- | --- | --- |
| FF-01 | `let x: f64 = 1.0 / 0.0` | Compiles; `inf` | `inf`; allowed but tracked |
| FF-02 | `let x: f64 = 0.0 / 0.0` | Compiles; `NaN` | `NaN`; allowed but tracked |
| FF-03 | `let x: f64 = sqrt(-1.0)` | Compiles; `NaN` | Allowed but tracked |
| FF-04 | `let x: f64 = log(0.0)` | `-inf` | Tracked |
| FF-05 | `let y: int = cast(int, x: f64)`, `x = NaN` | UB under `-O ReleaseFast` | Compile error unless `x: Fin<f64>`; otherwise `int_from(x) -> ?int` |
| FF-06 | `NaN == NaN` | `false` (IEEE 754) | Allowed; documented quirk |
| FF-07 | `Fin::new(x: f64) -> ?Fin<f64>` | n/a | Constructor; `none` for NaN or infinity |
| FF-08 | `Fin<f64> + Fin<f64>` | n/a | May overflow to non-finite; returns `?Fin<f64>` |
| FF-09 | `Fin<f64> * Fin<f64>` | n/a | Same as FF-08 |
| FF-10 | `Fin<f64> / Fin<f64>` | n/a | Returns `?Fin<f64>`; zero divisor gives infinity |
| FF-11 | `sqrt(x: Fin<f64>) -> ?Fin<f64>` | n/a | `none` for negative `x` |
| FF-12 | `log(x: Fin<f64>) -> ?Fin<f64>` | n/a | `none` for `x ≤ 0` |
| FF-13 | Subnormals (very small `f64` values) | Allowed | Allowed; they are finite |
| FF-14 | Mixing `f32` and `f64` | Needs explicit cast | Same |
| FF-15 | Literal `1.5` | Compiles | Refined to `Fin<f64>` at compile time |
| FF-16 | Literals `NaN`, `inf`, `-inf` | n/a | Allowed as explicit keywords; never assignable to `Fin<F>` |
| FF-17 | `printf("%f", x: Fin<f64>)` | n/a | Accepts `Fin<F>`; prints the standard form |
| FF-18 | `printf("%f", x: f64)`, `x` may be NaN | n/a | Allowed; prints `nan` |
| FF-19 | `Fin<f64>` storage layout | n/a | Same as `f64` (zero-cost) |
| FF-20 | `match x { case Fin::new(v): ...; case null: ... }` | n/a | Standard pattern |
| FF-21 | `Fin<f64>` to `f64` | n/a | Implicit upcast |
| FF-22 | `f64` to `Fin<f64>` | n/a | Only through `Fin::new` |
| FF-23 | Float ranges `Bounded<f64, lo, hi>` | n/a | Optional refinement; finite if the range is finite |
| FF-24 | `abs(x: f64) -> f64` is finite when `x` is finite | n/a | `abs(x: Fin<f64>) -> Fin<f64>` |
| FF-25 | `neg(x: Fin<f64>) -> Fin<f64>` | n/a | Always finite |
| FF-26 | Hex float literals `0x1.fp10` | If the parser supports them | Same handling as decimal |

## Examples

FF-01, FF-02 and FF-06 under ledger L16 (IEEE values):

```a7
// Proposed (L16 semantics; not re-run against the current compiler)
main :: fn() {
    zero: f64 = 0.0
    pos_inf: f64 = 1.0 / zero     // inf (see audit note on the divisor obligation)
    not_a_number: f64 = zero / zero
    io.println("{}", not_a_number == not_a_number)   // false
}
```

FF-13, FF-14 and FF-19, subnormals, mixing widths and layout:

```a7
// Current A7 syntax (behavior not re-run)
half: f32 = 0.5
wide: f64 = cast(f64, half)       // FF-14: explicit widening
```

```a7
// Proposed (exponent literal support not verified; Fin<F> superseded as the default by L16)
tiny: f64 = 4.9e-324              // FF-13: smallest subnormal, still finite

Sample :: struct {
    gain: Fin(f64)                // FF-19: same size and alignment as f64
}
```

FF-05, a float-to-integer conversion that handles NaN:

```a7
// Proposed (conversion operator open under gate G3; not implemented)
to_count :: fn(x: f64) ?u32 {
    ret u32_from(x)               // nil for NaN, infinity or out of range
}
```

## Interactions

| Gap | Interaction |
| --- | --- |
| 01 cast | Float-to-int cast (FF-05) needs `Fin<F>` input or returns `?T`. `Fin<F>` to `F` is an implicit upcast. |
| 02 nullable pointers | No interaction. |
| 03 definite assignment | Float locals start with whatever the backend produces; DA forces explicit initialization, as for integers. |
| 04 NonZero division | `Fin<F> / Fin<F>` can still give infinity when the divisor is zero or near zero. A float `NonZero<F>` excluding exactly zero, combined with `Fin<F>`, gives total division. |
| 05 stack budget | No interaction. |
| 06 typed arithmetic | Float range tracking is less precise than integer ranges; real intervals compose poorly under rounding and subnormals. Decision: float range tracking is optional and coarse; the main discipline is finiteness. |
| 07 bounded indexing | Floats are never indices. |
| 08 `Option<T>` / `Result<T, E>` | `Fin::new`, `int_from(f) -> ?int` and similar. |
| 09 refinement-lite | `Fin<F>` is the canonical refinement example. |
| 10 affine ownership | Floats are `Copy`. |
| 12 FFI | Foreign `f64` returns cross as bare `f64`; the user wraps in `Fin` if needed. |

## Failure modes

### False positives

- Numeric code that uses NaN as an intermediate sentinel (for example during a
  search) is rejected if the intermediate is `Fin<F>`. Mitigation: compute in bare
  `f64` and wrap at boundaries.
- Code that depends on NaN ≠ NaN (FF-06). `Fin<F>` excludes NaN, which simplifies
  such comparisons.

### False negatives

- Subnormals (FF-13) are finite but lose precision. Some codebases reject them.
  Mitigation: a `Normal<F>` refinement (Q11b).
- Rounding error: a finite `Fin<F>` result can still be mathematically wrong.
  Refinements do not protect against this.

### Ergonomic costs

- Float-heavy code (DSP, graphics, ML) becomes wordy with `Fin<F>`. Mitigation:
  `Fin<F>`-preserving combinators for common operations (`fma`, `dot_product`).
- Users outside safety-critical work will rarely use `Fin<F>`. The main
  enforcement is that bare `f64` cannot reach a context where NaN is unsafe, such
  as a cast to an integer (FF-05).

### Performance costs

- `Fin<F>` is zero-cost: same storage as `F`.
- `Fin::new` does one comparison (NaN check).

## Open questions

- **Q11a.** Is bare `f64` allowed, or must everything use `Fin<F>`?
  - Bare `f64` allowed; operations that may yield non-finite return bare `f64`;
    `Fin<F>` only through `Fin::new`.
  - Bare `f64` allowed; operations on `Fin<F>` return `?Fin<F>`.
  - Strict: bare `f64` reserved; the user must always wrap.
  Note (2026-09-16): answered by L16. Bare IEEE `f32` and `f64` are the default.
- **Q11b.** Should a `Normal<F>` refinement exclude subnormals?
- **Q11c.** A float `NonZero<F>` for total division: yes or no, and how does it
  combine with `Fin<F>`?
- **Q11d.** Float range refinements `Bounded<f64, lo, hi>` (FF-23): yes or no, and
  how does the type checker propagate ranges through rounding?
- **Q11e.** Comparisons on `Fin<F>` are a total order because NaN is excluded.
  What does that mean for generic code using an `Ord` trait, if A7 has one?
- **Q11f.** Transcendental functions: return `?Fin<f64>`, or total on `Fin<f64>`
  input? `sin` and `cos` are total (output in `[-1, 1]`). `tan` overflows near π/2.
  `log` and `sqrt` have domain limits. Decide per function.
- **Q11g.** Float-to-int (FF-05): an explicit `truncating_int_from(f) -> ?int`, or
  an extension of the Gap 01 `cast` classifier?
- **Q11h.** Should the literal `0.5` (FF-15) become `Fin<f64>` automatically?

## Source citations

- Phase A emission: `a7/backends/zig.py:1556-1557`, direct `/` for floats rather
  than `@divTrunc`. Note (2026-09-16): stale; those lines now hold array vector
  lowering. The current float division site was not re-verified.
- Float primitives: `a7/types.py:92-94` (`f32`, `f64` in `is_numeric`).
- No `Fin<F>` type exists; greenfield.
- Ada's `'Valid` attribute
  (`learn.adacore.com/courses/advanced-ada/parts/data_types/types.html`) is the
  closest analog. It returns false for scalars with an invalid representation,
  which for floats includes NaN and infinity on most platforms.
- Current examples use few floats; this gap is forward-looking.

## Phase C decision-input summary

1. Q11a — bare `f64` policy. Drives the scope of refinement enforcement.
   (Answered by L16.)
2. Q11c — `NonZero<F>` shape.
3. Q11d — float range refinements yes or no.
4. Q11f — per-function decision for transcendental functions.
5. Q11g — placement of the float-to-int operator.

The rest follow from these.
