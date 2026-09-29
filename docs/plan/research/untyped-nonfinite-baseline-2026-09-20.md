# Nonfinite numeric baseline

Existing typed arithmetic and math calls can produce infinity and NaN without
an overflowing literal. These routes provide a concrete way to retain L16's
IEEE values while considering stricter fitting of untyped finite constants.
This is baseline research, not approval or implementation of new rules.

## Observed results

The current A7 CLI compiled fourteen small programs. Every accepted program was
built and run with Zig 0.16.0 in Debug and ReleaseFast. The profiles agreed.
[The JSON evidence](untyped-nonfinite-baseline-2026-09-20.json) preserves sources,
commands, full outputs, emitted Zig, compiler version and selected source hashes.

| Source case | Observed result in both profiles |
| --- | --- |
| `x: f64 = 1e400` | Builds and prints `inf` |
| `x: f64 = -1e400` | Builds and prints `-inf` |
| `x := 1.0 / 0.0` | A7 rejects with exit 6; no native build |
| `x := 0.0 / 0.0` | A7 rejects with exit 6; no native build |
| The two divisions with an explicit `f64` result annotation | A7 rejects with exit 6; no native build |
| The two divisions using separately declared `f64` operands | A7 rejects with exit 6; no native build |
| Separate `f64` values `1e308` and `10.0`, multiplied | Builds and prints `inf` |
| Subtract that typed multiplication result from itself | Builds; `x == x` is false and `x != x` is true |
| `x := math.exp(1000.0)` | Builds and prints `inf` |
| `x := math.sqrt(-1.0)` | Builds; `x == x` is false and `x != x` is true |
| Global `INF :: math.exp(1000.0)` | Builds and prints `inf` |
| Global `NAN :: math.sqrt(-1.0)` | Builds; `NAN == NAN` is false and `NAN != NAN` is true |

NaN is checked through comparisons rather than its printed spelling. These are
observations from the current implementation. In particular, the zero-division
rejections must not be described as current support for all IEEE operations.

## Existing typed routes

This tested program produces infinity through an ordinary typed math call:

```a7
io :: import "std/io"
math :: import "std/math"
main :: fn() {
    x := math.exp(1000.0)
    io.println("{}", x)
}
```

Replacing the assignment with `x := math.sqrt(-1.0)` and printing `x == x` and
`x != x` produces `false true`. The registered math functions in
`a7/stdlib/math.py` include `exp`, `log` and `sqrt`. That registry has no explicit
`inf` or `nan` constructor. No constructor is proposed or added by this report.

The global binding routes were also tested:

```a7
io :: import "std/io"
math :: import "std/math"
INF :: math.exp(1000.0)
main :: fn() { io.println("{}", INF) }
```

A separate program with `NAN :: math.sqrt(-1.0)` prints `false true` for
`NAN == NAN` and `NAN != NAN`. These are existing `::` binding routes, not merely
runtime local-variable workarounds. The evidence contains both complete programs.

The proposed untyped-constant design can preserve these existing function-call
routes and concrete-width arithmetic. This is an inference from the observed
programs and the proposal's typed-value boundary, not evidence that the proposal
has been implemented. Keeping these routes does not itself settle how explicitly
typed constant casts, constant arithmetic or zero division should work.

## Limits

Only the listed local and global programs and profiles were checked. No other
target, hardware backend or optimized float mode was tested.
No compiler source changed. The full release gate was not run for this research.
The JSON records exact diagnostics for rejected cases; native execution applies
only to programs that passed A7 compilation and Zig compilation.
