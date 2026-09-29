# Exact-fit untyped constants candidate

The isolated candidate passes 47 of 47 stated source expectations. The matrix contains 29 valid cases, 18 rejection cases, and 2 inherited-behavior probes. Valid cases require matching output in Zig 0.16.0 Debug and ReleaseFast. This is a partial P-TYP vertical slice, not production implementation approval.

## Evidence

- [Final source, commands, stdout, stderr, exit codes, emitted Zig, and native runs](final-results.json). Every case runs through the real copied A7 CLI. Compiler failures require no new Zig artifact.
- [Source diff against the sibling baseline](source.diff) and [source hashes](source-manifest.json). Only candidate `a7/exact_constants.py`, `a7/passes/type_checker.py`, and `a7/backends/zig.py` differ. No production source, production tests, packet, or decisions were edited.
- [Selected existing tests](selected-tests.json): 50 passed, one failed. [The same failure on baseline](baseline-selected-failure.json) names two stale semantic-validator entries in the recursion allowlist. No test or allowlist was edited.
- [Independent follow-up review](reviewer/followup/REPORT.md) and [recursion comparison](reviewer/followup/recursion.json). All 20 paired profile probes met expectations. The scanner found no added recursive groups. Existing compiler recursion remains.
- [Exploratory run](exploratory-results.json) retains earlier malformed function probes and the mistaken expectation about local forward visibility. Those are probe-authoring errors, not accepted implementation results. The final matrix corrects the syntax and labels the local-forward case as an inherited-behavior probe.

## Measured compatibility

| Source case | Baseline | Candidate |
| --- | --- | --- |
| `forward_whole` | `2` | `2` |
| `forward_fraction` | A7 emits; Zig rejects | A7 rejects |
| `forward_range` | A7 emits; Zig rejects | A7 rejects |
| `forward_range_control` | `255` | `255` |
| `forward_exact_large` | `9007199254740992` | `9007199254740993` |
| `forward_string` | `{ 104, 101, 108, 108, 111 }` | `hello` |
| `backward_whole` | A7 rejects | `2` |
| `backward_fraction` | A7 rejects | A7 rejects |
| `backward_exact_large` | A7 rejects | `9007199254740993` |
| `backward_string` | `hello` | `hello` |
| `alias_chain` | `9007199254740992` | `9007199254740993` |
| `multi_use` | `200 200` | `200 200` |
| `multi_use_bad` | A7 emits; Zig rejects | A7 rejects |
| `local_exact` | A7 rejects | `9007199254740993` |
| `exact_arithmetic` | A7 emits; Zig rejects | `9007199254740994 256 3` |
| `typed_runtime_reject` | Builds; no output | A7 rejects |
| `typed_call_reject` | Builds; no output | A7 rejects |
| `mixed_range_reject` | A7 emits; Zig rejects | A7 rejects |
| `typed_wrapping` | `0` | `0` |
| `local_forward_probe` | A7 emits; Zig rejects | A7 emits; Zig rejects |
| `local_runtime_order` | `1 / 2 / 1 2 2` | `1 / 2 / 1 2 2` |
| `global_runtime_order_probe` | A7 emits; Zig rejects | A7 emits; Zig rejects |
| `typed_float_arithmetic` | `false` | `false` |
| `exact_comparison` | `true false` | `false true` |

## Mechanism and preserved behavior

The evaluator reads decimal token spelling into exact rational values and uses explicit stacks for expression evaluation. Global bindings resolve through worklists. The cache uses declaration identity and retains numeric category. Each destination gets its own literal, so one use does not specialize the declaration for later uses.

The slice implements unary negation, exact addition, subtraction, multiplication, and wholly untyped numeric comparisons. Integer destinations reject fractional or out-of-range values. Mixed typed integer addition, subtraction, and multiplication fit the constant before the existing typed operation. Inferred mutable integer variables and numeric formatting reject values outside default i32.

Global types resolve before function bodies. The compiler does not reorder the declaration list or evaluate user functions in Python. Forward and backward string formatting both print hello. The local runtime-order control verifies initializer calls run once, in source order. The global side-effect initializer probe records the inherited native limitation separately; this prototype does not add a global runtime initialization facility.

Typed mutable values and ordinary function results remain typed. The matrix pairs rejected f64-to-integer uses with accepted f64 controls. Typed integer wrapping remains observable separately from untyped range rejection. Existing exact integer quotient/remainder, float remainder, compound assignment, and recursion scanner checks were selected because they touch the changed boundaries.

## Limits

- This is not the complete operator or context table. Exact division, remainder, bitwise operations, shifts, generic inference, match fitting, and all aggregate/index contexts are not qualified. Unsupported exact operations fall back to existing paths; the candidate does not provide a general unsupported-operation diagnostic.
- Float overflow fitting, direct f32 rounding, underflow, and all signed-zero arithmetic combinations remain unqualified. Decimal token spelling drives exact integer fitting, but the parser and downstream legacy paths still construct host floats.
- Pointer-sized fitting uses the existing 64-bit assumption. Native evidence covers the current host only.
- Global cycle errors are located but do not yet show a full dependency chain. Fractional/range diagnostics lack the complete declaration context required by the packet. Diagnostic rendering and exact arithmetic have no reviewed resource policy.
- [Observable local forward-reference probe](local-visibility.json): both compilers emit Zig, then both native profiles reject the unresolved local reference. This slice does not repair that inherited diagnostic gap or add forward-local visibility.
- No exhaustion tests, security qualification, full corpus comparison, package gate, or release gate ran. The selected-test failure remains visible. This evidence does not establish release readiness.

## Reproduction

`run_cases.py` records a fresh bounded matrix. `finalize_results.py` adds boundary cases and records the final matrix. It recompiles every source against the final compiler. For unchanged emitted Zig, it retains the exact earlier build command/output and reruns the executable; records explicitly identify that reuse. Changed or new Zig is built in both profiles. `run_selected.py` records selected existing tests, and `snapshot.py` regenerates the source diff and hashes.

All sources, scripts, native artifacts, and evidence are under this evidence directory. Candidate implementation edits are confined to the sibling `candidate/` tree. Baseline source files were not edited.
