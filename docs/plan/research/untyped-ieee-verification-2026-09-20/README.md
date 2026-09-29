# Frozen candidate IEEE verification

The second frozen candidate passed all 19 fixed IEEE boundary rows. The 17
accepted sources each produced the expected stored bits in Debug and ReleaseFast.
The two overflow sources failed at the A7 fitting stage with exit 6, a located
diagnostic and no emitted Zig file. Compiler source hashes were unchanged.

This qualifies these bounded materialization cases only. It does not qualify
full P-TYP behavior or the production release. Production compiler files were
not changed or tested by this run.

## Evidence

- [Fixed mathematical requirements](../untyped-ieee-acceptance-2026-09-20.md).
- [Fixed expectation matrix](planned-matrix.json).
- [Observer script](verify.py).
- [Full successful report](report.json), including exact sources, commands,
  diagnostics, original Zig, instrumented Zig and all 34 native executions.
- [Compiler source hashes](source-hashes.json), recorded before and after.
- [Invalid initial attempt](attempt-0-invalid-venv.json), preserved separately.

The compiler tree was
`tmp/untyped-constants-next/review-candidate-2`. The toolchain was Zig 0.16.0.
The script used three concurrent workers. Each worker built its case in Debug
and ReleaseFast sequentially. Fixed expected bits came from the mathematical
requirements; they were not computed from candidate code or host float parsing.

## Observation boundary

Each accepted A7 program declared one concrete `f32` or `f64` value and printed
it through `io.println`. The observer changed exactly one generated print
argument from `observed_value` to
`@as(u32, @bitCast(observed_value))` or its `u64` equivalent. It preserved the
declaration, expression, destination type and remaining generated program.
The script required exactly one match and saved both versions of the Zig source.

The output therefore exposes the target value's IEEE bits, including signed zero
and adjacent values whose short decimal formatting might match. Ordinary A7
float formatting was not tested. This observer is a test-only Zig adaptation,
not a new public A7 operation. No native binary or build cache is stored here.

## Initial infrastructure failure

The first script version resolved the virtual-environment Python symlink to its
base interpreter. Every program failed during compiler import because that
interpreter lacked `rich`. Those failures were not candidate numeric failures.

The observer was corrected to preserve the supplied virtual-environment
entrypoint. The successful run used a new output directory and the same fixed
expectations. The invalid attempt remains recorded for traceability. No candidate
source or expected result changed to obtain the passing run.

## Scope limits

These cases check direct numeric declarations, midpoint rounding, underflow,
subnormals, finite maxima, overflow rejection and negative zero. They do not
establish correctness for every arithmetic expression, aggregate, generic,
function call, dependency graph, target or floating-point mode. The full release
gate was not run. The experiment does not authorize production language changes.
