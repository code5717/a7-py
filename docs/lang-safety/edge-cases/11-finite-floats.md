# Gap 11 — Finite floats (`Fin<f>` and NaN/inf discipline)

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.11](../07-language-review.md#111-floating-point--nan--inf-flow-silently).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Today `f32` and `f64` flow NaN and infinity silently through
arithmetic and propagate to integer conversions. The contract
requires either (a) `Fin<F>` refined type for code that wants
total arithmetic, or (b) explicit handling at each operation that
may produce a non-finite. Ada offers a partial analog via the
`'Valid` attribute and constrained subtypes; A7 takes a cleaner
refinement-based path.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| FF-01 | `let x: f64 = 1.0 / 0.0` | Compiles; produces `inf` | Produces `inf`; allowed but tracked |
| FF-02 | `let x: f64 = 0.0 / 0.0` | Compiles; produces `NaN` | Produces `NaN`; allowed but tracked |
| FF-03 | `let x: f64 = sqrt(-1.0)` | Compiles; produces `NaN` | Allowed but tracked |
| FF-04 | `let x: f64 = log(0.0)` | Produces `-inf` | Tracked |
| FF-05 | `let y: int = cast(int, x: f64)` where `x = NaN` | Today: UB under `-O ReleaseFast` | **Compile error** unless `x: Fin<f64>`; otherwise use `int_from(x) -> ?int` |
| FF-06 | Comparison `NaN == NaN` | Returns `false` (IEEE 754) | Allowed; documented quirk |
| FF-07 | `Fin::new(x: f64) -> ?Fin<f64>` | n/a | Constructor; returns `none` for NaN/inf |
| FF-08 | `Fin<f64> + Fin<f64>` | n/a | May produce non-finite (e.g., overflow); returns `?Fin<f64>` |
| FF-09 | `Fin<f64> * Fin<f64>` | n/a | Same |
| FF-10 | `Fin<f64> / Fin<f64>` | n/a | Returns `?Fin<f64>` (divisor zero ⇒ inf) |
| FF-11 | `sqrt(x: Fin<f64>) -> ?Fin<f64>` | n/a | None for negative `x` |
| FF-12 | `log(x: Fin<f64>) -> ?Fin<f64>` | n/a | None for `x ≤ 0` |
| FF-13 | Subnormals (very small `f64` values) | Allowed | Allowed — they're finite |
| FF-14 | `f32` vs `f64` mixing | Today: requires explicit cast | Same |
| FF-15 | Float literal `1.5` | Compiles | Refined to `Fin<f64>` (compile-time check) |
| FF-16 | NaN/inf literals: `NaN`, `inf`, `-inf` | n/a | Allowed via explicit keywords; **never** assigned to `Fin<F>` |
| FF-17 | `printf("%f", x: Fin<f64>)` | n/a | Format string accepts `Fin<F>` and prints standard form |
| FF-18 | `printf("%f", x: f64)` where `x` may be NaN | n/a | Allowed; prints `nan` literal text |
| FF-19 | `Fin<f64>` storage layout | n/a | Same as `f64` (zero-cost) |
| FF-20 | `Fin<f64>` in match guard: `match x { case Fin::new(v): ...; case null: ... }` | n/a | Standard pattern |
| FF-21 | Coerce `Fin<f64>` to `f64` | n/a | Implicit upcast |
| FF-22 | Coerce `f64` to `Fin<f64>` | n/a | Only via `Fin::new` |
| FF-23 | Float ranges `Bounded<f64, lo, hi>` (analogous to integer `Bounded`) | n/a | Optional refinement; finiteness implied if range is finite |
| FF-24 | `abs(x: f64) -> f64` always finite if `x` is finite | n/a | `abs(x: Fin<f64>) -> Fin<f64>` |
| FF-25 | `neg(x: Fin<f64>) -> Fin<f64>` | n/a | Always finite |
| FF-26 | Hex float literals `0x1.fp10` | If parser supports | Same handling as decimal |

## Interactions

- **Gap 01 cast.** Float-to-int cast (FF-05) requires `Fin<F>` input
  or returns `?T`. Cast from `Fin<F>` to base `F` is implicit upcast.
- **Gap 02 nullable pointers.** No interaction.
- **Gap 03 definite assignment.** Float locals default to whatever
  the backend produces; DA forces explicit init (same as integers).
- **Gap 04 NonZero division.** Division of `Fin<F>` by `Fin<F>` can
  still produce `inf` — divisor zero (or near-zero) yields `inf`.
  Float `NonZero<F>` is a *separate* refinement that excludes
  zero exactly; combined with `Fin<F>` gives total division.
- **Gap 05 stack budget.** No interaction.
- **Gap 06 typed arithmetic.** Float range tracking is **less
  precise** than integer ranges (intervals over reals don't compose
  cleanly under arithmetic — especially with subnormals and
  rounding). Decision: float range tracking is *optional* and
  coarse; the main discipline is finiteness.
- **Gap 07 bounded indexing.** Floats are never indices; no
  interaction.
- **Gap 08 `Option<T>` / `Result<T, E>`.** `Fin::new`,
  `int_from(f) -> ?int`, etc.
- **Gap 09 refinement-lite.** `Fin<F>` is the canonical example for
  this gap.
- **Gap 10 affine ownership.** Floats are `Copy`; no ownership issues.
- **Gap 12 FFI.** Foreign returns of `f64` cross as bare `f64`; user
  wraps in `Fin` if needed.

## Failure modes

### False positives

- Numeric code that needs intermediate NaN values (e.g., as a
  sentinel during a search) would be rejected by `Fin<F>`-typed
  intermediate. Mitigation: keep computations in bare `f64` and
  wrap in `Fin<F>` at boundaries.
- Float comparison reliance on NaN ≠ NaN (FF-06) — if the code
  *depends on* this IEEE 754 behaviour, `Fin<F>` excludes the
  case, simplifying the comparison.

### False negatives

- Subnormals (FF-13) are finite but represent precision loss.
  Some codebases want to reject them. Mitigation: a `Normal<F>`
  refinement (open question).
- Rounding error in `Fin<F>` arithmetic — the result may be
  technically finite but mathematically wrong. Refinements don't
  protect against this.

### Ergonomic costs

- Float-heavy code (DSP, graphics, ML) becomes wordy with `Fin<F>`
  wrappers. Mitigation: provide `Fin<F>`-preserving combinators
  for common operations (`fma`, `dot_product`).
- Users not doing safety-critical work probably won't bother with
  `Fin<F>`. The contract requires that bare `f64` *cannot* slip
  into a context where NaN propagation is unsafe (the cast to int
  case, FF-05) — that's the main enforcement.

### Performance costs

- `Fin<F>` is zero-cost (same storage as `F`).
- Constructor `Fin::new` does one comparison (NaN check) — fast.

## Open questions

- **Q11a.** Should bare `f64` be allowed at all, or must everything
  use `Fin<F>`? Three options:
  - Bare `f64` allowed; constructors and operations that yield
    non-finite return bare `f64`; conversion to `Fin<F>` only via
    `Fin::new`.
  - Bare `f64` allowed; operations on `Fin<F>` return `?Fin<F>`.
  - Strict: bare `f64` reserved; user must always wrap.
- **Q11b.** Should there be a `Normal<F>` refinement that excludes
  subnormals? Yes/no.
- **Q11c.** Float `NonZero<F>` (for total division) — yes/no, and
  combined with `Fin<F>` how?
- **Q11d.** Float range refinements `Bounded<f64, lo, hi>` (FF-23)
  — yes/no, and how does the type checker propagate ranges through
  float arithmetic given rounding?
- **Q11e.** Comparison operators on `Fin<F>` — total ordering
  (since NaN is excluded), so `<` is total. Implications for
  generic code using `Ord` trait (if A7 has one).
- **Q11f.** Sin/cos/tan and other transcendental functions — return
  `?Fin<f64>` or are they guaranteed total on `Fin<f64>` input?
  Sin/cos are total (output in `[-1, 1]`); tan can blow up to inf
  near π/2; log, sqrt, etc., have domain restrictions. Decision per
  function.
- **Q11g.** Float-to-int cast (FF-05) — explicit `truncating_int_from(f)
  -> ?int` or extends Gap 01's `cast` classifier?
- **Q11h.** Float literals (FF-15) — should literal `0.5` get
  refined to `Fin<f64>` automatically?

## Source citations

- Today's emission: `a7/backends/zig.py:1556-1557` — direct `/` for
  floats (not `@divTrunc`).
- Float primitives: `a7/types.py:92-94` for `f32`, `f64`.
- No `Fin<F>` type exists; greenfield.
- Ada's `'Valid` attribute documented in
  `learn.adacore.com/courses/advanced-ada/parts/data_types/types.html`
  is the closest analog — it returns false for scalar values whose
  representation is invalid (which on floats includes NaN/inf on
  most platforms).
- Limited float usage in current examples; this gap is
  forward-looking.

## Phase C decision-input summary

1. Q11a — bare `f64` policy. **Drives:** scope of refinement
   enforcement.
2. Q11c — `NonZero<F>` shape.
3. Q11d — float range refinements yes/no.
4. Q11f — transcendental functions per-function decision.
5. Q11g — float-to-int operator placement.

The rest follow.
