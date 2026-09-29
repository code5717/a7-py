# Examples corpus and test suite audit — 2026-09-18

Component prefix `EXT`. Audited tree: `/home/cx89/Projects/pl-dev/a7-py` at
`master` (`701c679`) plus the uncommitted batches C3, PR-00, T0, V1, NOREC-0 and
PL-02. Batches C1, C4 and C2 are in worktrees under
`/home/cx89/Projects/pl-dev/a7-wt/` and are **not** in this tree.

Environment: `zig 0.16.0`, `pytest 9.1.1`, `uv 0.12.6`, `pytest-randomly` not
installed. Probes, mutation plugins and captured runs under
`tmp/audit/2026-09-18/examples-tests/`.

**The test suite does not test the compiler.** Two single-line mutations, each
changing a core compiler decision to a constant, leave almost the whole suite
green:

| Mutation | Suite result | Tests that detected it |
| --- | --- | --- |
| `classify_cast` returns `LOSSLESS` for every pair | 79 failed, 2508 passed | **60** of 2587 |
| `get_binary_precedence` returns `1` for every operator (so `1 + 2 * 3` parses as `(1+2)*3`) | 23 failed, 2571 passed | **4** of 2594 |

Four tests in the entire suite notice that every binary operator has the same
precedence, and none of them is in the 509 parser and tokenizer tests written to
test the parser.

1240 of the 2587 collected tests (48%) live in `test/test_cast_safety_matrix.py`,
and 1180 of those 1240 still pass when the function they exist to test is
replaced by a constant. Counting by the Test quality rule in `CLAUDE.md`, at
least **1223 of 2587 tests (47%) assert nothing that could fail if the behavior
under test were wrong.**

The examples corpus is 43 single-file, fixed-data, print-only programs. All 43
are in the E2E set, all 43 have a golden that is checked in both Debug and
ReleaseFast, and no golden is stale. Its problems are coverage, not correctness:
no example is rejected on purpose, none reads input, opens a file, takes an
argument or spans two files, one teaches a tokenizer defect as a language
feature, and three are shaped around a compiler defect that no longer exists.

## Summary

| Severity | NEW | KNOWN | Total |
| --- | --- | --- | --- |
| CRITICAL | 2 | 0 | 2 |
| HIGH | 7 | 1 | 8 |
| MEDIUM | 16 | 2 | 18 |
| LOW | 8 | 0 | 8 |
| **Total** | **33** | **3** | **36** |

Nothing in this report changes compiler behavior. Of the 36 findings, 31 are
pure test- or harness-side and need no approval; 5 touch an example file
(EXT-06, EXT-12, EXT-13, EXT-14, EXT-31) and escalate under the
compatibility-scan rule at `docs/plan/execution.md:223`.

---

# Part 1 — The examples corpus

## 1.1 What each example contains

All 43 `examples/*.a7` are discovered by one glob
(`scripts/verify_examples_common.py:179-180`), so **every** example is in the
E2E set and **every** example's stdout is diffed against
`test/fixtures/golden_outputs/<stem>.out`. There is no second tier and no
example that is compiled but not run.

| # | Language features used | Golden | Relies on a defect |
| --- | --- | --- | --- |
| 000_empty | `fn` only | 0 bytes | — (prints nothing; see EXT-30) |
| 001_hello | import, `io.println`, string | 1 line | — |
| 002_var | `:=`, `::` const, explicit types, `bool`/`f64`/`string`, `+=`, uninitialized default | 6 | — |
| 003_comments | `//`, nested `/* */`, **unclosed `/*` at EOF** | 2 | **yes, F1** (EXT-06) |
| 004_func | params, return, void fn, inline-struct return, C-for, early `ret` | 6 | — |
| 005_for_loop | C-for, `[5]i32`, index assign, `for v in`, `for i, v in`, nested, `break`, `continue` | 40 | — |
| 006_if | `if`/`else if`/`else`, if-expression, `and`/`or`/`!`, nesting | 8 | — |
| 007_while | `while`, `while true`, `break`, `continue`, `*=`, `-=`, `<<`-free bitwise none | 36 | — |
| 008_switch | `match` on int, `case`, `else` | 2 | — |
| 009_struct | struct decl, nested struct, struct literal, field read | 4 | — |
| 010_enum | `enum`, `Color.Green`, exhaustive `match` | 2 | — |
| 011_memory | `new`, `del`, `defer`, `nil` compare, early `ret` | 3 | — (but see EXT-20) |
| 012_arrays | `[5]i32` with initializer, `for i, v in`, `+=` | 7 | — |
| 013_pointers | `ref i32` parameter, `p += 1` through ref | 3 | **stale workaround** (EXT-12) |
| 014_generics | `$T` fn, `$T` struct field, `Pair($A,$B) :: struct`, `Box(i32)`, nested instantiation | 6 | — |
| 015_types | `i32`,`f64`,`bool`,`char`,`string` annotations | 6 | — |
| 016_unions | `union`, construction by one field, field read | 3 | — |
| 017_methods | struct + `ref Counter` parameter, field mutation | 2 | **stale workaround** (EXT-12) |
| 018_modules | two imports, `math.sqrt`, `math.abs` | 3 | — |
| 019_literals | int/float/char/string/bool literals, `ref i32 = nil` | 7 | — (golden locks Zig's `null`, EXT-11) |
| 020_operators | `+ - * / %`, `> ==`, `& | ^ << >>` | 13 | — |
| 021_control_flow | C-for + `continue`, `while` | 5 | — |
| 022_function_pointers | named fn types, anonymous fn type annotation, higher-order calls | 4 | — |
| 023_inline_structs | inline struct return type and literal | 2 | — |
| 024_defer | two `defer`s, LIFO order visible in output | 5 | — |
| 025_linked_list | struct, `match` as expression, **`isize` sentinel** | 5 | **rule violation** (EXT-13) |
| 026_binary_tree | struct, `usize`, `cast(usize,0)`, array of `usize`, explicit stack, `match` expression | 5 | **loop rule** (EXT-14) |
| 027_callbacks | `Handler :: fn()`, fn values as arguments | 7 | — |
| 028_state_machine | enum, two exhaustive `match` statements, enum return | 8 | — |
| 029_sorting | array, named fn type, `cast(usize,…)`, nested loops, index swap | 6 | **loop rule** (EXT-14) |
| 030_calculator | `f64` arithmetic, `math.floor`, if-expression, C-for, guards | 29 | **loop rule** (EXT-14) |
| 031_number_guessing | array, `for i, v in`, `break`, `else if` | 7 | — |
| 032_prime_numbers | C-for with `d*d <= n`, `while`, `%` | 10 | **loop rule** (EXT-14) |
| 033_fibonacci | `usize`, `u64`, `cast(u64, n)`, `while` | 11 | — |
| 034_string_utils | `for ch in string`, `string[0..5]` slice, `char` compare, `io.print` | 6 | — (dead `'\0'` branch, EXT-31) |
| 035_matrix | `[4]f64`, **element-wise `c = a + b`**, printing an array | 2 | — (golden locks Zig array format, EXT-11) |
| 036_control_flow_edges | array slice `[1..4]`, `@label for`, `break label`, `continue label`, `defer` inside `match` case | 6 | — |
| 037_language_tour | the above, plus `new`/`del`/`nil`, `ref`, named fn type, `usize` index accumulation | 14 | **stale workaround** (EXT-12) |
| 038_inventory_report | structs, `ref` struct parameter, guarded integer arithmetic | 7 | — |
| 039_text_analyzer | `char` predicates, two string slices, `for ch in`, `usize` counters | 7 | — |
| 040_task_board | structs, `ref` mutation, `match` with `case 2, 3:` multi-pattern, `ret` inside case | 7 | — |
| 041_route_simulation | struct, `ref` mutation, arrays, `cast(usize,0)` loop index | 9 | **loop rule** (EXT-14) |
| 042_gradebook | array field in struct, `ref` struct, `match` with `case 90..100:` range | 5 | **loop rule** (EXT-14) |

## 1.2 Coverage: SPEC features with no example

Confirmed from the sources, extending the recorded list at
`docs/plan/audit/language-audit-checklist.md:58-59`:

| Feature | SPEC | Examples using it |
| --- | --- | --- |
| Slice **type** `[]T` | `docs/SPEC.md:270-276` | **0** (`grep -n '\[\]' examples/*.a7` → no hits) |
| `.len` (and `.ptr`, `.element`) | `docs/SPEC.md:258-259, 274-275` | **0** |
| `pub` | `docs/SPEC.md` visibility | **0** |
| `@type_set` or any intrinsic | `docs/SPEC.md:944, 964` | **0** (`grep -n '@[a-z_]*'` finds only the two `@label`s in 036) |
| `fall` | SPEC match section | **0** — `037_language_tour.a7:6` *mentions* it in a comment only |
| Variadic parameters | parsed-only per `CLAUDE.md` | 0 |
| Multiple-declaration / destructuring | parsed-only per `CLAUDE.md` | 0 |
| Local (file-backed) imports | `a7/module_resolver.py` | **0** — all 42 imports are `std/io` (42) or `std/math` (2) |
| `std/mem`, `std/string` | `CLAUDE.md:44-45` | **0**, and unreachable (EXT-05) |
| `i8`, `i16`, `i64`, `u8`, `u16`, `u32`, `f32` | SPEC 3 | **0** — the corpus uses only `i32`, `u64`, `usize`, `isize`, `f64`, `bool`, `char`, `string` |
| Generics beyond one file | SPEC 7 | 1 (`014`) |
| Tagged unions / payload match | SPEC, gate G5 | 0 |
| `using` | SPEC | 0 |
| Integer overflow / wrapping (ledger L5) | — | 0 |

`$T` appears only in `examples/014_generics.a7` — confirmed. Slice *expressions*
(`text[0..5]`, `numbers[1..4]`) **do** appear, in 034, 036, 037 and 039; only the
slice *type annotation* `[]T` is absent. `.len` cannot appear: it is rejected by
the compiler today (KNOWN S12, `docs/plan/audit/2026-09-16-inventory-repro.md:48`).

`035_matrix.a7:12` uses element-wise array `+`, which **is** specified
(`docs/SPEC.md:262-266`) — it is the only example exercising it, and no test
covers it.

## 1.3 Correctness of the corpus

Confirmed, with probes. Nothing else in the corpus falls into these classes: a
sweep for the banned reference operators found no `.adr`, `.val`, prefix `&` or
prefix `*` used as a reference operation in any example (the `.val` hits are all
a struct field literally named `value`), and no example uses `new [N]T`.

## 1.4 The goldens

**Checked in both profiles, not byte-for-byte.** `verify_examples_e2e.py` builds
with `zig build-exe` and no `-O` flag (Debug default) and diffs the golden;
`build_examples.py` runs the same diff at `-ODebug` and `-OReleaseFast`
(`scripts/build_examples.py:20-27, 205-213`). Both profiles are compared against
the *same* golden file, so cross-profile output equality is enforced. But the
comparison normalizes first (`verify_examples_common.py:67-74`,
`build_examples.py:78-83`): CRLF → LF, **every line right-stripped**, one
trailing blank line dropped. Trailing whitespace an example emits is invisible.

**stderr is folded into stdout** (`verify_examples_common.py:129`,
`build_examples.py:131` both use `stderr=subprocess.STDOUT`), so a program that
writes to the wrong stream still matches its golden. No example writes to stderr
today, so nothing is currently masked — but `048_stderr_output` is scheduled
(`docs/plan/execution.md:348`) and will be unverifiable as written.

**Exit codes are checked** (non-zero fails, `verify_examples_common.py:136-143`).

**No golden is stale.** I regenerated all 43 into a scratch directory and
diffed: identical.

```
uv run python scripts/verify_examples_e2e.py --update-golden \
  --fixtures-dir tmp/audit/2026-09-18/examples-tests/regen      # exit 0, 43/43
diff -rq test/fixtures/golden_outputs tmp/audit/2026-09-18/examples-tests/regen  # exit 0
```

**The harness has no way to create a golden except from compiler output.** The
only writer is `--update-golden` (`verify_examples_common.py:151-155`), which
writes whatever the binary printed, for **every** example at once. Whether any of
the 43 was originally hand-derived and then confirmed is UNVERIFIED; INFERENCE
from `--update-golden` being the only path. The plan's
rule that expected output be written by hand first
(`docs/plan/execution.md:282`) postdates the existing corpus and is not enforced
by the harness; `--example`-scoping of `--update-golden` is scheduled as H3
(`execution.md:344`). See EXT-18.

**One golden is trivially satisfiable**: `000_empty.out` is 0 bytes. See EXT-30.
No other golden is empty; the smallest real one is `001_hello.out` at 1 line.

## 1.5 What the corpus should contain and does not

Scheduled in `docs/plan/execution.md`, so not counted as findings:

| Scheduled | Where |
| --- | --- |
| 16 small examples `043_integer_widths` … `058_matrix_2d`, plus fixing `025` to `usize` | `execution.md:348` (lane E, after the capability probe at `:346`) |
| Full 300–450 line fixed-data apps with a `checks: N/N ok` self-check line | `execution.md:369` (Wave 2.3) |
| A multi-file app `examples/apps/calc_vm/{main,lexer,compiler,vm}.a7` | `execution.md:398` |
| stdin and command-line arguments, with `test/fixtures/stdin/` and `test/fixtures/args/` | `execution.md:405`, gated on packet P9 |
| Unsafe/guarded program pairs under `test/soundness/*.a7` | `execution.md:387` (Wave 3.3) |
| Per-example harness support: `--example`, `--jobs`, runtime budget, discovery of `examples/apps/*/main.a7` | `execution.md:344` (H1–H9) |
| `examples/003_comments.a7:28-30` and its test, inside the lexical-strictness packet | `execution.md:352` (P1) |

**Not scheduled anywhere** — see the "What is missing" table: a rejected-on-purpose
example, file I/O, an example that exercises `std/mem` or `std/string`, an
example whose golden includes stderr on a separate stream, and an example
covering the integer widths other than `i32`/`u64`/`usize` that lane E's
`043_integer_widths` will only partly reach.

---

# Part 2 — The test suite

## 2.1 Classification, per file

2587 tests collected at the start of this audit
(`PYTHONPATH=. uv run pytest test/ --collect-only -q`). The "would still pass"
column counts tests whose only assertions are `assert True`, `assert x is not
None` on a value that cannot be `None`, `assert isinstance(...)` on a value that
is always that type, an assertion inside a `try` whose `except` swallows the
interesting case, or an expected value recomputed with the function under test.

| File | What it verifies | Tests | Would still pass if wrong |
| --- | --- | --- | --- |
| test_cast_safety_matrix.py | Cast classification and the semantic cast boundary — with `classify_cast` as its own oracle | 1240 | **819** structural / **1180** measured |
| test_codegen_zig.py | All 43 examples compile and `zig ast-check`; ~55 substring assertions on emitted Zig; 6 build-and-run cases | 144 | 45 |
| test_semantic_control_flow.py | Match exhaustiveness, reachability, capture patterns, return paths, each pinned to a message fragment | 90 | 2 |
| test_ast_preprocessor.py | Constant folding, mutation/usage flags, hoisting | 69 | 18 |
| test_semantic_comprehensive.py | 65 programs accepted or rejected; nothing about inferred types | 65 | 0 strict, ~45 weak |
| test_parser_extreme_edge_cases.py | That deep-nesting / inline-struct / fn-type source parses without raising | 62 | 55 |
| test_error_stage_matrix.py | Exit code + category + stage flags for every stage × mode × format | 62 | 0 |
| test_semantic_types.py | Type-system rules; two tests inspect real `node_types`; the only semantic file that runs `SafetyProofPass` | 57 | 1 |
| test_stdlib_registry.py | The registry object's own methods, mostly ones the compiler never calls | 55 | 23 |
| test_iterative_traversal.py | Programs compile at a reduced Python recursion limit | 44 | 0 strict (weak another way, EXT-27) |
| test_parser_edge_cases.py | Mostly real AST/error assertions; a few root-kind-only and fake-recovery tests | 40 | 11 |
| test_parser_comprehensive_problems.py | Real match/enum/pattern node shapes, plus 17 smoke tests | 39 | 17 |
| test_semantic_expressions.py | Operator typing, stdlib call checks, array shape rules | 37 | 3 |
| test_semantic_functions.py | Signatures, return types, the recursion ban (11 strong cases) | 35 | 4 |
| test_parser_type_combinations.py | That 35 complex type spellings parse | 35 | **35** |
| test_parser_missing_constructs.py | Node kinds and fields for struct/enum/union/match/defer/for/generics | 33 | 3 |
| test_semantic_generics.py | Generic inference and constraints — the aspirational half unasserted | 32 | 9 |
| test_parser_creative_cases.py | That 31 "real-world pattern" blobs parse | 31 | **31** |
| test_parser_error_handling_improvements.py | That malformed constructs raise `ParseError` (message mostly unchecked) | 29 | 10 |
| test_parser_examples.py | That `examples/*.a7` parse | 28 | 14 |
| test_parser_basic.py | Exact AST shape for literals, declarations, expressions, types, imports | 27 | 1 |
| test_parser_advanced_edge_cases.py | That array/pointer/generic text tokenizes and parses | 26 | 23 |
| test_parser_combinatorial.py | That large blobs covering every type/operator/declaration form parse | 26 | 20 |
| test_tokenizer_aggressive.py | Exact token types, values and positions | 25 | 2 |
| test_tokenizer_errors.py | Tokenizer error messages, spans, Rich display layout | 23 | 7 (vacuous if no error raised) |
| test_semantic_errors.py | Error detection — 12 of 22 assert nothing about it | 22 | 12 |
| test_parser_stress_tests.py | That large/deep inputs parse; 5 real error assertions | 21 | 16 |
| test_cli_failures.py | Real CLI process: exit codes, categories, message text, absence of output files | 20 | 0 |
| test_parser_unicode_and_special.py | That 19 Unicode/comment/boundary blobs parse | 19 | **19** |
| test_no_recursion.py | The `norec_scan` scanner's spec plus a ratchet over `a7/` | 19 | 0 |
| test_release_tooling.py | Manifest checksums, tamper/unsafe-path rejection, archive contents, secret scan | 14 | 2 |
| test_semantic_analysis.py | That the three passes run on 13 tiny programs | 13 | 4 |
| test_parser_fuzzing.py | That random and mutated input raises nothing *unexpected* | 13 | 12 |
| test_compound_assignment_types.py | Compound-assign operand types through `main.py` against real Zig builds | 13 | 0 |
| test_parser_integration.py | 5 real integration checks + 5 report generators ending in `assert True` | 10 | 5 |
| test_tokenizer.py | Exact expected token-type sequence for 8 programs | 8 | 0 |
| test_recursion_detection_scaling.py | Cycle diagnostics text, line, column, order, and search cost, through the real CLI | 8 | 0 |
| test_parser_regressions.py | Node kinds for intrinsics, trailing commas, type aliases, generic decls | 8 | 0 |
| test_zig_backend_runtime.py | CLI compile → build Debug **and** ReleaseFast → run → exact stdout/stderr | 7 | 0 |
| test_module_alias_shadowing.py | A local named like an import alias wins, proved by running binaries | 7 | 0 |
| test_pipeline_diagnostics.py | Diagnostics carry the right file, line and column, including across imports | 6 | 0 |
| test_parse_termination.py | Malformed `match` exits 5 at an exact line:col, no `.zig` written | 6 | 0 |
| test_pipeline_artifacts.py | Failed compiles never advertise or clobber artifacts; inputs byte-preserved | 5 | 0 |
| test_pipeline_native.py | Real Zig builds of tricky bindings; 2 tests run binaries and check integer div/rem | 5 | 0 |
| test_backends_registry.py | Only `zig` is registered; removed C backend unimportable | 4 | 0 |
| test_module_resolver.py | Virtual `std/*` registration, alias resolution, path-traversal rejection | 3 | 0 |
| test_examples_e2e.py | Delegates to the E2E script over all 43 examples | 2 | 0 |
| **Total** | | **2587** | **1223** (47%) |

Seventeen files carry a zero in the last column: `test_error_stage_matrix.py`,
`test_iterative_traversal.py` (0 strict), `test_cli_failures.py`,
`test_no_recursion.py`, `test_compound_assignment_types.py`,
`test_tokenizer.py`, `test_recursion_detection_scaling.py`,
`test_parser_regressions.py`, `test_zig_backend_runtime.py`,
`test_module_alias_shadowing.py`, `test_pipeline_diagnostics.py`,
`test_parse_termination.py`, `test_pipeline_artifacts.py`,
`test_pipeline_native.py`, `test_backends_registry.py`,
`test_module_resolver.py`, `test_examples_e2e.py`. Most are recent and most
follow the same pattern: run the real CLI or the real toolchain, assert an exact
exit code, an exact message and an exact line and column. They are the model the
rest of the suite should be rewritten against.

## 2.2 The 12 known failing tests

All 12 reproduce on this tree
(`tmp/audit/2026-09-18/examples-tests/pipeline12.txt`, exit 1, `12 failed, 4
passed`). **In all 12 the test is right and the compiler is wrong. None fails
because the test itself is wrong.**

| Test | Observed failure | Verdict |
| --- | --- | --- |
| `test_pipeline_artifacts.py:28` `[--output]` | `--output` **destroyed the A7 input** | test right |
| `test_pipeline_artifacts.py:28` `[--doc-out]` | `--doc-out` destroyed the A7 input | test right |
| `test_pipeline_artifacts.py:39` | A parse failure still reports `output_path` | test right |
| `test_pipeline_artifacts.py:51` | A write failure reports the directory as an artifact | test right |
| `test_pipeline_diagnostics.py:43` `[parse]` | `assert 9 == 10` — the diagnostic points at the space before `)`, not at `)` | test right; col 10 is the offending token, and the `token` and `semantic` params of the same test pass |
| `test_pipeline_diagnostics.py:61` | `Missing import has no source location` | test right |
| `test_pipeline_diagnostics.py:80` | `assert 8 in {PARSE, SEMANTIC}` — **a parse error inside an imported module exits 8 (internal)** | test right, and the most serious of the 12 |
| `test_pipeline_diagnostics.py:100` | Imported semantic error blames `main.a7`, not `helper.a7` | test right |
| `test_pipeline_native.py:54` `[zig-keyword-local]` | Emitted Zig rejected | test right |
| `test_pipeline_native.py:54` `[unused-loop-capture]` | Emitted Zig rejected | test right |
| `test_pipeline_native.py:54` `[shadowed-loop-capture]` | `capture 'x' shadows local constant from outer scope` | test right |
| `test_pipeline_native.py:79` | Debug prints `9007199254740992 1`, the runtime path prints `9007199254740993 0` | test right; folding through binary64 |

## 2.3 The true baseline is 19, not 12

Full run on this tree: `19 failed, 2568 passed in 247.31s`
(`tmp/audit/2026-09-18/examples-tests/baseline_full.txt`). The seven extra
failures are all in `test_tokenizer_errors.py` and are caused by `FORCE_COLOR=3`
in the environment. See EXT-17.

---

# Findings

## EXT-01. CRITICAL. NEW. 48% of the suite tests a function against itself

`test/test_cast_safety_matrix.py` holds 1240 of 2587 tests. Four of its
parametrized families derive the expected value from the function under test, or
restate a one-line property:

- `test_classifier_all_primitive_pairs_without_nonnegative_proof` (225 tests,
  `:108-115`) asserts `classify_cast(a,b).kind is expected`, where `expected` is
  `expected_without_proof(a,b)` — which is literally `return classify_cast(a, b,
  source_nonnegative=False).kind` (`:78-81`).
- `test_classifier_forbidden_pairs_are_not_allowed` (225, `:141-146`) asserts
  `decision.allowed is (decision.kind is not CastClass.FORBIDDEN)`. That is the
  definition of `allowed` (`a7/cast_classifier.py:25-27`).
- `test_classifier_reasons_are_stable_and_nonempty` (225, `:131-138`) asserts
  only determinism and a non-empty string.
- `test_semantic_numeric_cast_matrix_without_guard` (144, `:177-185`) decides
  whether to expect an error by calling `expected_without_proof`, i.e. the same
  oracle, on the same input.

That is 819 tests. Both `a7/passes/type_checker.py:12` and `a7/safety.py:17`
import `classify_cast` at module load, so a single patch mutates the classifier
*and* the pipeline in lockstep and the mirror holds.

**Evidence.** Plugin `tmp/audit/2026-09-18/examples-tests/mutant.py` replaces
`classify_cast` with `lambda …: CastDecision(CastClass.LOSSLESS, "mutated")`:

```
PYTHONPATH=.:tmp/audit/2026-09-18/examples-tests \
  uv run pytest test/test_cast_safety_matrix.py -p mutant --tb=no -q
# exit 1 — 60 failed, 1180 passed in 0.64s
```

The 60 that fail are the reference- and function-type rejection families
(`:149-174`). Every numeric pair — the entire point of the file — passes while
the compiler claims a `f64 → u8` cast is lossless. Suite-wide the same mutation
gives `79 failed, 2508 passed`
(`tmp/audit/2026-09-18/examples-tests/mutant_full.txt`); subtracting the 19
already-failing tests, exactly **60 of 2587 tests** detect it.

**Fix direction.** Replace the four families with a hand-written table of the
expected `CastClass` for each of the 225 pairs — written from `docs/SPEC.md` and
the cast-boundary decision, not from the code — plus, for the semantic half, a
hand-written accept/reject list. A table of 225 literals is not count inflation:
it is the specification. Delete `expected_without_proof` entirely.

**Changes accepted programs?** No.

## EXT-02. CRITICAL. NEW. Operator precedence is untested

Flattening every binary operator to the same precedence changes how every mixed
expression parses, and no parser test notices.

**Evidence.** Plugin `tmp/audit/2026-09-18/examples-tests/mutant_prec.py` sets
`a7.parser.get_binary_precedence = lambda op: 1`. The mutation is real:

```
PYTHONPATH=.:tmp/audit/… uv run python -c "…parse_a7('x :: 1 + 2 * 3')…"
# mutated:   root op: BinaryOp.MUL  | left: BINARY(ADD) | right: LITERAL
# unmutated: root op: BinaryOp.ADD  | left: LITERAL     | right: BINARY(MUL)
```

Running the eight largest parser files under it:

```
uv run pytest test/test_parser_type_combinations.py test/test_parser_creative_cases.py \
  test/test_parser_unicode_and_special.py test/test_parser_extreme_edge_cases.py \
  test/test_parser_combinatorial.py test/test_parser_edge_cases.py \
  test/test_parser_stress_tests.py test/test_parser_advanced_edge_cases.py -p mutant_prec
# 260 passed in 0.17s
```

Zero of 260. Suite-wide the mutation gives `23 failed, 2571 passed in 384.85s`
(`tmp/audit/2026-09-18/examples-tests/mutant_prec_full.txt`); against the 19
already-failing tests, exactly **4 of 2594 tests** detect it —
`test_parser_basic.py` (1), `test_codegen_zig.py` (2),
`test_iterative_traversal.py` (1). None of the other 508 parser and tokenizer
tests notices.

This is despite eight tests whose names and docstrings promise
precedence coverage and which assert nothing about the tree:
`test_parser_edge_cases.py:52`, `test_parser_combinatorial.py:145` (18
operators), `:236` (13 cases), `test_parser_creative_cases.py:116`,
`test_parser_extreme_edge_cases.py:237` (5 cases) and `:280` (whose comment says
"Should parse as `(1 < 2) < 3`" and never checks),
`test_parser_comprehensive_problems.py:608`, `test_parser_stress_tests.py:288`
(17 operator lines).

**Fix direction.** One parametrized test asserting the full operator tree for a
fixed list of mixed expressions — root operator, then each side's kind and
operator. `test_parser_basic.py` already uses that pattern.

**Changes accepted programs?** No.

## EXT-03. HIGH. NEW. 281 of 509 parser and tokenizer tests assert only "did not raise"

`parse_a7` (`a7/parser.py:2354-2360`) either raises or returns a node, and
`Parser.parse` (`:164`) always returns a `PROGRAM` node. So `assert ast is not
None` and `assert result.kind == NodeKind.PROGRAM` are exactly equivalent to "no
exception" and say nothing about the tree.

Three whole files are nothing but that form, confirmed by counting every
assertion in each:

| File | `def test_` | Distinct assertion forms |
| --- | --- | --- |
| `test_parser_type_combinations.py` | 35 | `assert ast is not None` × 35 |
| `test_parser_creative_cases.py` | 31 | `assert result.kind == NodeKind.PROGRAM` × 31 |
| `test_parser_unicode_and_special.py` | 19 | `assert result.kind == NodeKind.PROGRAM` × 19 |

`test_parser_extreme_edge_cases.py` adds 55 of 62 in the same shape; its
inline-struct block (`:582-775`, 13 tests) and function-type block (`:781-922`,
9 tests) are near-identical cases differing only in field or parameter count, and
they duplicate `test_parser_type_combinations.py` almost one for one — roughly
50 tests for one grammar rule, none asserting node shape.

The worst by promise-versus-assertion:
`test_parser_type_combinations.py:379` `test_function_maze` (nested function-type
associativity, asserts `ast is not None`); `:417` `test_mixed_collection_types`
(`[5][]ref [10]ref struct{…}` — the ARRAY/SLICE/POINTER order is the only thing
that can silently invert, unchecked); `:560`
`test_function_type_no_return_type` (should assert `return_type is None`, the one
bit it is named after); `test_parser_unicode_and_special.py:16`
`test_emoji_in_strings` (would pass if the tokenizer dropped every non-ASCII byte
— should assert `literal_value` round-trips).

**Fix direction.** Each of these tests already has the parsed node in hand.
Assert the node kind chain and the field it is named after. Where two files test
the same rule, keep one.

**Changes accepted programs?** No.

## EXT-04. HIGH. NEW. 31 semantic tests assert `isinstance(result, bool)`; three hide a rejection and one hides a broken test

The 31 sites: `test_semantic_errors.py:111, 138, 178, 218, 230, 242, 255, 287,
312, 324, 342, 356`; `test_semantic_generics.py:145, 233, 293, 428, 493, 512,
527, 550, 583`; `test_semantic_functions.py:179, 195, 269, 679`;
`test_semantic_expressions.py:275, 416, 497`;
`test_semantic_control_flow.py:1282, 1306`; `test_semantic_types.py:196`.

`expect_success` / `expect_error` return `True` or `False`
(`test_semantic_errors.py:60-77` and five verbatim copies), so `assert
isinstance(result, bool)` is `assert True`. Four of the 31 are hiding something,
confirmed by running each source through its own file's
`run_semantic_analysis` (`tmp/audit/2026-09-18/examples-tests/verify4.py`):

```
generics:constraint_violation : ACCEPTED
control_flow:simple_defer     : REJECTED SemanticError : <test>:4:11: Delete requires a reference type: Got 'i32'
functions:returning_function  : REJECTED TypeCheckError : <test>:4:9: Undefined type (Identifier 'add')
errors:return_outside_function: REJECTED ParseError : 3:1: Unexpected token 'ret' after parsing complete program
```

- `test_semantic_generics.py:218-233` `test_constraint_violation`. Its own
  comment says "This should error - f64 not in IntOnly type set". The compiler
  **accepts** it — and the compiler is right: the source declares
  `process :: fn(value: $T) $T` with no constraint on `$T`, so `IntOnly` is never
  applied to anything. The test source is broken, not the compiler. The
  `isinstance` assertion is what lets a test that cannot express its own subject
  sit in the suite looking like coverage of constraint checking.
- `test_semantic_functions.py:662-679` `test_function_returning_function`. The
  feature is broken (`Undefined type (Identifier 'add')`) and the test passes
  under a comment reading "This might not be fully supported yet".
- `test_semantic_control_flow.py:1272-1282` `test_simple_defer`. The program is
  rejected; the test passes.
- `test_semantic_errors.py:279-287` `test_return_outside_function`. The program
  never reaches semantic analysis — it is a `ParseError`. Because `ParseError`
  subclasses `CompilerError` (`a7/errors.py:754, 622`) and `parse_program` runs
  *inside* `run_semantic_analysis`, every one of these helpers counts a parse
  failure as "semantic analysis rejected it". `test_semantic_generics.py:512`
  (`generic enum`, `Some: $T` does not parse) has the same problem.

**Fix direction.** Each should assert the exact outcome with the exact message
and span: `test_semantic_generics.py:218-233` should first constrain the
parameter the way `docs/SPEC.md:964` writes it
(`process($T: IntOnly) :: fn(value: $T) $T`) and only then assert rejection
naming `f64` and `IntOnly`. Whether constraint checking works at all on a
correctly constrained program is UNVERIFIED — no test in the suite exercises
one. `test_semantic_functions.py:662-679` should
assert rejection with `Undefined type (Identifier 'add')` at line 5.
`test_semantic_control_flow.py:1272-1282` should assert rejection with `Delete
requires a reference type` at line 4. `test_semantic_errors.py:279-287` should
assert `ExitCode.PARSE` and the span at line 3. Separately, the six
`run_semantic_analysis` copies should not treat a `ParseError` as a semantic
rejection.

**Changes accepted programs?** No.

## EXT-05. HIGH. NEW. `std/mem` and `std/string` are unreachable, and nothing tests or exemplifies them

`CLAUDE.md:44-45` describes "`a7/stdlib/` (registry of `std/io`, `std/math`,
`std/mem`, `std/string`)". `a7/stdlib/mem.py` and `a7/stdlib/string.py` exist and
call `register_module`, but `_register_defaults` (`a7/stdlib/__init__.py:44-50`)
registers only io and math. Both imports are rejected:

```
uv run a7 tmp/audit/2026-09-18/examples-tests/probes/p_stdmem.a7 --output …   # exit 6
uv run a7 tmp/audit/2026-09-18/examples-tests/probes/p_stdstring.a7 --output … # exit 6
```

`test_stdlib_registry.py:53` `test_only_two_default_modules` locks the current
state in as correct, so the test suite actively certifies the drift.

**Fix direction.** Either register the two modules and add examples and tests, or
strike them from `CLAUDE.md`/`AGENTS.md` and delete the dead files. This overlaps
the `stdlib.md` audit of the same date; the finding here is that the test suite
asserts the smaller set is right.

**Changes accepted programs?** No (registering them accepts more).

## EXT-06. HIGH. KNOWN (F1, `docs/plan/audit/2026-09-16-inventory-repro.md:75`). An example teaches a tokenizer defect as a language feature

`examples/003_comments.a7:28-29`:

```
/* Note: Multi-line comments do not need closing delimiter
 * if they extend to EOF (end of file)
```

The file ends there. The comment is unclosed, and the example's own body text
states the defect as a rule of the language. `docs/SPEC.md:67-75` says nothing of
the kind. Probes (`tmp/audit/2026-09-18/examples-tests/probes/`):

| Probe | Result |
| --- | --- |
| `p_003_unclosed.a7` (the example as-is) | exit 0 |
| `p_003_closed.a7` (same, with ` */` appended) | exit 0 |
| `p_unclosed_min.a7` (3 lines, trailing `/* dangling`) | exit 0 |

So the example does not *need* the defect to compile — it needs it only because
its final comment is unclosed, and it advertises that as intended behavior.
`test_parser_examples.py:54` passes on this file (KNOWN, `parser.md:593`).

**Fix direction.** Packet P1 already covers the lexer rule
(`docs/plan/execution.md:352` names this file and line range). Independently of
P1, lines 28-29 should be rewritten: they are documentation of a defect in a file
users read to learn the comment syntax.

**Changes accepted programs?** **Yes** — closing the comment is safe, but P1's
rule change turns a compiling program into a rejected one. Escalates under
`execution.md:223`.

## EXT-07. HIGH. NEW. No test outside the cast matrix asserts the safety pass rejects an unsafe program

`SafetyProofPass` appears in four test files
(`test_cast_safety_matrix.py`, `test_codegen_zig.py`, `test_semantic_types.py`,
`test_no_recursion.py`). In `test_codegen_zig.py:68-72` and
`test_semantic_types.py:58-61` it is run and its first error re-raised, so those
tests assert safety *accepts*. Five of the six semantic files' copies of
`run_semantic_analysis` stop after `SemanticValidationPass` and never construct
`SafetyProofPass` at all — a test in those files that "expects an error" from the
safety pass would silently record acceptance.

The only rejection tests are in `test_cast_safety_matrix.py`, and EXT-01 shows
that file's numeric rejections are mirrored. The nearest independent negative
test, `test_codegen_zig.py:910-922`, bypasses safety entirely and asserts the
*backend* raises.

Given that the safety pass is what stands between A7 and out-of-bounds indexing,
division by zero, use-after-`del` and unproven casts, this is the single largest
untested surface in the compiler.

**Fix direction.** `docs/plan/execution.md:387` schedules `test/soundness/*.a7`
pairs (each unsafe program rejected, each guarded twin accepted) at Wave 3.3,
behind the IR. That is too late for the current safety pass. A file of paired
A7 sources run through the real CLI, asserting `ExitCode.SEMANTIC` and the exact
message and span for the unsafe twin and exit 0 for the guarded twin, is
independent of the IR work.

**Changes accepted programs?** No.

## EXT-08. HIGH. NEW. 23 of 55 `test_stdlib_registry.py` tests exercise entry points with no callers

Grep of `a7/` excluding `a7/stdlib/` finds **zero** callers of
`StdlibRegistry.get_backend_mapping` and of the registry's `is_io_call`:

```
grep -rn "get_backend_mapping\|\.is_io_call" a7/ | grep -v '^a7/stdlib/__init__.py'   # no output
```

The backend derives `@sqrt` and friends itself (`a7/backends/zig.py:1615-1620,
1634-1640`) and defines its own private `_is_io_call` (`:2161`, used at `:1284,
1408, 1625, 2387`). The `backend_map` values in `a7/stdlib/io.py:13, 18, 23` are
dead data. The tests:

- `TestGetBackendMapping`, 9 tests (`:238-307`) — dead entry point.
- `TestIsIoCall`, 7 tests (`:313-346`) — dead entry point.
- `TestCustomModuleRegistration`, 3 tests (`:352, 366, 379`) — no compiler path
  registers a custom module.
- `TestStdlibDataclasses`, 4 tests (`:395, 407, 412, 418`) — set a dataclass
  field, read it back.

Live paths (`resolve_call`, `resolve_builtin`, `public_module_paths`) are covered
by `TestResolveCall` (16), `TestResolveBuiltin` (9) and
`TestStdlibRegistryInitialization` (7), and those are the classes most inflated
by one-name-per-test duplication: `test_all_math_builtins_f32` (`:193`) subsumes
`:169` and `:181`; `test_all_math_builtins_f64` (`:205`) subsumes `:175` and
`:187`; `test_all_math_zig_mappings` (`:268`) subsumes `:256` and `:262`;
`:140` and `:152` are the same case.

**Fix direction.** Delete the dead-path classes or make the backend use the
registry (which is the real fix, and is the `stdlib.md` audit's territory).
Collapse the duplicated single-name tests into the loops that already exist
beside them.

**Changes accepted programs?** No.

## EXT-09. HIGH. NEW. pytest has no `testpaths`; a bare `pytest` collects from `tmp/`, and this broke the gate during this audit

Confirmed: there is no `[tool.pytest.ini_options]` in `pyproject.toml`, no
`pytest.ini`, `tox.ini`, `setup.cfg` or `conftest.py` anywhere. Probe — a file
written into the audit scratch directory:

```
cat > tmp/audit/2026-09-18/examples-tests/test_collection_probe.py   # trivial test
uv run pytest --collect-only -q | grep test_collection_probe
# tmp/audit/2026-09-18/examples-tests/test_collection_probe.py::test_probe_collected_from_tmp
```

(The probe file was removed immediately after.)

**This is an observed failure, not a hypothetical one.** During this audit I
extracted `HEAD` into `tmp/audit/2026-09-18/examples-tests/head-tree/` with `git
archive` to date a defect (EXT-12). That copy carried `head-tree/test/*.py`, and
a concurrent full gate run on the main tree collected them and failed with
collection errors. The copy has been moved outside the repository to
`/home/cx89/.claude/jobs/4e152702/tmp/examples-tests-head-tree/`. A scratch
directory the project's own rules point agents at is inside the collection root;
any agent that extracts, vendors or checks out anything containing `test_*.py`
breaks the gate for everyone else. The fix is queued in
`tmp/packets/pending-items.md`.

`run_all_tests.sh:89` runs
`uv run pytest --tb=no -q` with no path, so any agent scratch file named
`test_*.py` under `tmp/`, and any worktree checked out inside the repository,
enters the release gate. The same missing exclusion is why
`check_no_secrets.py` flagged `tmp/toolchain/zig-0.16.0/lib/std/crypto/scrypt.zig`
in the Wave 0 baseline (`docs/audits/2026-09-16/baseline.md`). `.gitignore` has
no `tmp/` entry either.

Scheduled as H5 (`docs/plan/execution.md:344`), after packet P0.

**Fix direction.** `testpaths = ["test"]` plus `norecursedirs`, and `tmp/` in
`.gitignore` and the secret-scan skip list. `run_all_tests.sh:89` should name
`test/` explicitly regardless.

**Changes accepted programs?** No.

## EXT-10. HIGH. NEW. The gate's per-file steps skip 16 test files, including every safety, pipeline and cast file

`run_all_tests.sh:49-62` runs three selected-file steps covering
`test_parser*`, `test_tokenizer*`, `test_semantic*`, `test_ast_preprocessor.py`,
`test_cli_failures.py`, `test_iterative_traversal.py`,
`test_stdlib_registry.py`, `test_codegen_zig.py`. Sixteen files are reached only
by the final "TOTAL (All Pytest Tests)" step at `:89`:

```
test_backends_registry.py          test_pipeline_artifacts.py
test_cast_safety_matrix.py         test_pipeline_diagnostics.py
test_compound_assignment_types.py  test_pipeline_native.py
test_error_stage_matrix.py         test_recursion_detection_scaling.py
test_examples_e2e.py               test_release_tooling.py
test_module_alias_shadowing.py     test_stdlib_call_resolution.py
test_module_resolver.py            test_zig_backend_runtime.py
test_no_recursion.py               test_parse_termination.py
```

Note `test_parse_termination.py` does not match the glob `test_parser*.py`.

That final step is the one that is red (12 known failures), so the gate reports
"11 of 12 checks passed" while the only step that covers the safety matrix, the
native runtime tests, the CLI artifact contract and the diagnostics contract is
failing. A reader of the per-step output sees eleven greens.

**Fix direction.** Delete the three selected-file steps. One `uv run pytest test/`
covers all of them and is faster than running the same files twice.

**Changes accepted programs?** No.

## EXT-11. MEDIUM. NEW. The goldens are the only definition of A7's output formatting

`docs/SPEC.md` has no formatting section: it documents `io.println` as
`println :: fn(s: string)` (`:1614`) and its examples use a `printf` that does
not exist (`:612, 676, 788`). Every `{}` substitution is therefore Zig's
`std.fmt` default, frozen into goldens no document backs:

| Golden | Line | What it locks in |
| --- | --- | --- |
| `019_literals.out` | `nil = null` | A7's `nil` prints as Zig's `null` |
| `035_matrix.out` | `c = { 6, 8, 10, 12 }` | Zig's array format, braces and all |
| `030_calculator.out` | `a = 10, b = 3` | `f64` 10.0 prints without a decimal point |
| `030_calculator.out` | `sqrt(2) = 1.414` | rounding done in A7, but the float format is Zig's |

A backend change to Zig's formatter, or a Zig version bump, breaks all 43
goldens with no document to say which side is right.

**Fix direction.** A SPEC section defining `{}` for each type, then the goldens
follow from it. Lane D (`execution.md:350`) already owns SPEC corrections;
formatting is not on its list.

**Changes accepted programs?** No (documenting current behavior).

## EXT-12. MEDIUM. NEW. Three examples are shaped around a defect that does not exist

`examples/037_language_tour.a7:110-114`:

```
    // Split declaration and assignment here so the generated native local is
    // mutable before it is passed by reference.
    counter: i32
    counter = 41
    bump(counter)
```

`examples/013_pointers.a7:12-13` and `examples/017_methods.a7:16-17` use the same
split. Probes show the workaround is unnecessary, both on this tree and at
`HEAD` (`701c679`, extracted with `git archive` into
`tmp/audit/2026-09-18/examples-tests/head-tree/`):

| Probe | This tree | HEAD |
| --- | --- | --- |
| `x := 10; increment(x)` (`p_ref_inferred.a7`) | a7 exit 0, `zig build-obj` exit 0 | a7 exit 0, `zig build-obj` exit 0 |
| `c := Counter{value: 0}; increment(c)` (`p_ref_struct.a7`) | exit 0 / exit 0 | exit 0 / exit 0 |

Emitted Zig in both cases: `var x: i32 = 10; increment(&x);` and
`var c = Counter{ .value = 0 }; increment(&c);`. The local is already `var`.

This matters more than its severity suggests: `037_language_tour.a7` is the file
the docs point at as the canonical tour of the language, and it states a false
rule about how `ref` arguments must be prepared.

**Fix direction.** Use `counter := 41` / `x := 10` / drop `c.value = 0` and
delete the three comments. Regenerate the three goldens (they will not change —
the output is identical).

**Changes accepted programs?** **Yes** — it edits three example files, so it runs
the compatibility scan under `execution.md:223`. The goldens are unchanged, which
is the scan's own criterion for not escalating further.

## EXT-13. MEDIUM. KNOWN. `025_linked_list.a7` uses `isize` sentinels against the `usize` rule

`examples/025_linked_list.a7:7` (`next: isize`), `:15` (`next: -1`) and `:17`
(`current: isize = 0`). `CLAUDE.md` A7 Source Rules: "Use `usize` for sizes,
lengths, capacities, and array/slice/string indices… Reserve `isize` for signed
pointer-sized offsets and position differences only". `next` and `current` are
node indices. Confirmed; it is the only example using `isize`.

Already scheduled: "fix `025_linked_list.a7` to `usize` with a `NONE` constant and
unchanged golden" (`docs/plan/execution.md:348`).

**Changes accepted programs?** **Yes** (edits an example). The scheduled fix
requires the golden to be unchanged, which keeps it inside the scan's tolerance.

## EXT-14. MEDIUM. KNOWN. Six examples are approved for the wrong reason

`docs/plan/audit/2026-09-16-inventory-repro.md:81` records that under the loop
rule as it would be implemented, `examples/026, 029, 030, 032, 041, 042` change
status: they are correct programs that today pass the safety pass because facts
survive loop entry when they should not. `:75` records the narrower five-example
version of the same row, and `:78` records `026_binary_tree.a7:49, 56, 62` under
the compound-assignment rule.

Confirmed against the sources: every one of the six carries a loop-carried index
or accumulator used in an indexed access or a division —
`029_sorting.a7:17-24` (`arr[j]`, `arr[j+1]`, bound `4 - i`),
`026_binary_tree.a7:47-64` (`stack[top]` with `top` mutated in both directions),
`041_route_simulation.a7:35-38` (`dx[i]`, `dy[i]`),
`042_gradebook.a7:26-32` (`student.scores[i]`),
`030_calculator.a7:61-73` and `032_prime_numbers.a7:10-13` (loop-carried
accumulators feeding guarded arithmetic).

`packet P0b` owns the choice (`inventory-repro.md:82-83`).

**Changes accepted programs?** **Yes**, by construction — that is what the
compatibility scan measured.

## EXT-15. MEDIUM. NEW. No example is rejected on purpose, and none exercises an error path

All 43 examples compile, build and exit 0. `examples/` contains no
counterexample directory and the E2E harness has no concept of an expected
failure: `verify_example` treats a non-zero compiler exit as `compile failed` and
a non-zero binary exit as `binary exited non-zero`
(`verify_examples_common.py:100-101, 136-143`).

Negative behavior is covered elsewhere — `scripts/error_stage_common.py:195-279`
(exit 3, 4, 5, 6, 7 across six modes and two formats, 61 cases) and
`test_cli_failures.py` — but never from a file a user can read. A reader who
wants to know what a rejected A7 program looks like, or what the diagnostic says,
has no example to open.

Nothing in `docs/plan/execution.md` schedules one: lanes E and 2.3 list only
programs that run.

**Fix direction.** An `examples/errors/` tier with each file carrying its
expected exit code and diagnostic fragment in a header comment, verified by the
same harness. This is also the natural home for EXT-07's soundness pairs.

**Changes accepted programs?** No.

## EXT-16. MEDIUM. NEW. Six tests end in `assert True`

`test_parser_examples.py:318` (in `test_example_success_rate`, `:260-318`, which
prints a pass/fail table for every example and then passes unconditionally), and
`test_parser_integration.py:366, 415, 461, 493, 527` — five report generators
that build an expectation dict, print a percentage, and discard it. That is 5 of
that file's 10 tests.

`test_parser_integration.py:282` and `test_parser_examples.py:260` iterate the
same example list and both end in `assert True`.

H6 (`docs/plan/execution.md:344`) schedules replacing
`test_parser_examples.py:257-318` with a parametrized parse test over every
discovered file. `test_parser_integration.py` is not mentioned.

**Fix direction.** Parametrize per example/keyword/construct and fail on the
first that does not parse; mark the not-yet-supported ones `xfail` with a
tracking reference, so the day one starts working the suite says so.

**Changes accepted programs?** No.

## EXT-17. MEDIUM. NEW. Seven tests fail whenever the terminal forces color

`test_tokenizer_errors.py:156, 178, 196, 216, 273, 366, 385` assert plain
substrings such as `"1 ┃ §"` and `"error: Unexpected character: '§' [line 1: col
15]"` against Rich console output. With `FORCE_COLOR=3` in the environment they
fail; with `NO_COLOR=1` the file is green:

```
uv run pytest test/test_tokenizer_errors.py -q            # 7 failed, 16 passed
NO_COLOR=1 … uv run pytest test/test_tokenizer_errors.py  # 23 passed
```

This is why the full run on this tree is `19 failed, 2568 passed` rather than the
12 in `docs/audits/2026-09-16/baseline.md`. Separately, all seven place every
assertion inside `except TokenizerError:` with no `else` and no `pytest.fail`, so
if the tokenizer stopped rejecting `§` entirely they would all pass silently.

**Fix direction.** Strip ANSI before asserting, as `test_parse_termination.py:29,
137` already does, and restructure to `with pytest.raises(TokenizerError) as
exc_info:` with the assertions outside the block — the pattern the other 16 tests
in the same file use correctly.

**Changes accepted programs?** No.

## EXT-18. MEDIUM. NEW. One command regenerates all 43 goldens from compiler output

`--update-golden` (`verify_examples_common.py:151-155`) writes whatever each
binary printed into the fixture and marks the example as passing, for every
example at once. There is no confirmation, no diff, and no per-example scope. A
miscompile that changes one line of output becomes the new expected output the
moment anyone runs it to "fix the goldens".

The plan's own rule (`execution.md:282`) says an example author must write
expected output by hand *before* the first A7 run and only then create the
golden; the harness does not enforce it. H3 (`execution.md:344`) schedules
`--update-golden` requiring `--example`, which narrows the blast radius but does
not add a diff.

**Fix direction.** Require `--example`, print the diff and require confirmation,
and refuse when more than one example would change.

**Changes accepted programs?** No.

## EXT-19. MEDIUM. NEW. Eight tests mirror an identity function

`a7/ast_preprocessor.py:187-189`:

```python
def _lower_field_sugar(self, node: ASTNode) -> ASTNode:
    """Compatibility no-op: .adr/.val are no longer pointer syntax."""
    return node
```

`test_ast_preprocessor.py` `TestFieldSugarLowering` spends 8 tests
(`:67, 79, 91, 111, 125, 136, 146, 156`) asserting `result is node` and
`changes_made == 0`. They cannot fail for any reason connected to `.adr`/`.val`
behavior.

Also in this file: `:355` and `:759` assert `changes >= 1`, satisfied by any
other pass bumping the counter; `:867` asserts `pp.changes_made < 999` where
`== 0` is meant; `:605` asserts a dataclass field default rather than
preprocessor behavior; `TestEmptyAndMinimalInput` (6 tests, `:797-855`) asserts
only parser node kinds and would pass with every preprocessor pass replaced by
`pass`.

**Fix direction.** Delete the eight and replace them with one end-to-end test
that `.adr`/`.val` reach codegen as ordinary field access. Change `>= 1` to the
exact delta for a source with exactly one foldable expression.

**Changes accepted programs?** No.

## EXT-20. MEDIUM. NEW. The only `new`/`del` examples cannot observe deallocation

`examples/011_memory.a7` and `examples/037_language_tour.a7` are the only
programs using `new` and `del`. Their goldens are:

```
=== Memory ===          |   … heap = 99
heap value = 42         |   done
memory example complete |
```

Neither line depends on whether `del` ran, ran twice, or never ran. The E2E
harness checks exit code and stdout only — no allocator accounting, no
`-fsanitize`, no leak check. A backend change that dropped every `del`, or
emitted a double free that happened not to trap, would pass 43 of 43.

**Fix direction.** Build at least these two under a Zig configuration that traps
double free and reports leaks (Debug with a checked allocator), or add a
`checks: N/N ok` self-check line of the kind Wave 2.3 already specifies
(`execution.md:369`) that prints the allocation count.

**Changes accepted programs?** No.

## EXT-21. MEDIUM. NEW. Parser tests pass the whole source text as the filename

`Parser.__init__(self, tokens, filename=None, source_lines=None)`
(`a7/parser.py:50-55`). Tests call `Parser(tokens, code)`, binding the entire
program text to `filename`: every test in
`test_parser_extreme_edge_cases.py` and `test_parser_type_combinations.py`, plus
`test_parser_fuzzing.py:229, 252, 278, 324, 363, 369, 432, 460, 482, 495, 507,
530, 543`.

It is harmless only because none of those tests asserts on error output — and it
compounds KNOWN PAR-17, whose stdout warning echoes `filename` verbatim
(`docs/audits/2026-09-16/compiler/parser.md:412-420`), so
`test_parser_fuzzing.py:486-497` prints its entire 1000-declaration source into
the pytest capture buffer.

**Fix direction.** `Parser(tokens, "<test>", code.splitlines())`, or a shared
`parse_a7` helper.

**Changes accepted programs?** No.

## EXT-22. MEDIUM. NEW. Exit code 8 is asserted nowhere, and the compiler demonstrably produces it

Exit codes asserted somewhere in the suite: 0, 2 (`test_error_stage_matrix.py:252`,
`test_cli_failures.py:388`), 3, 4, 5, 6, 7 (`scripts/error_stage_common.py:261`,
`test_error_stage_matrix.py:213`). `ExitCode.INTERNAL` (8) appears in no test and
no script.

It is not hypothetical: `test_pipeline_diagnostics.py:80` fails today with
`assert 8 in {ExitCode.PARSE, ExitCode.SEMANTIC}` — a parse error inside an
imported module crashes the compiler into an internal error. Nothing in the gate
would notice a second, third or tenth path producing 8, because nothing asserts
that 8 never occurs for a source-level failure.

**Fix direction.** One assertion in the error-stage matrix that no scenario
returns 8, and a positive test that a deliberately triggered internal fault
returns 8 with a JSON payload rather than a traceback.

**Changes accepted programs?** No.

## EXT-23. MEDIUM. NEW. Test sources violate the project's own A7 source rules

`CLAUDE.md` A7 Source Rules ban recursive A7 functions, `.adr`/`.val` reference
syntax and `new [N]T`. All three are in the test corpus:

| Rule | Sites |
| --- | --- |
| Recursion | `test_parser_advanced_edge_cases.py:255` (`factorial` calling itself) |
| `.adr` / `.val` | 48 in `test_parser_creative_cases.py`, 16 in `test_parser_combinatorial.py`, 11 in `test_parser_extreme_edge_cases.py`, 10 in `test_parser_advanced_edge_cases.py`, 4 in `test_ast_preprocessor.py` |
| `new [N]T` / `new([N]T)` | `test_parser_advanced_edge_cases.py:308`, `test_parser_combinatorial.py:859`, `test_parser_creative_cases.py:918, 989`, `test_semantic_types.py:450` |

The `.adr`/`.val` cases are defensible where the point is that the sugar is *not*
special (`test_semantic_expressions.py:407-416`), but 89 uses across five files
is a corpus of banned syntax that any future strictness change must be scanned
against. Note the compatibility scan at `execution.md:223` searches
`examples/`, tests, goldens, SPEC, README and `site/public/` — so these 89 sites
will show up as blockers.

**Fix direction.** Restrict `.adr`/`.val` to the handful of tests that assert
they are ordinary field access; rewrite the rest. Replace the recursive
`factorial` with a loop or with a test that asserts it is *rejected*.

**Changes accepted programs?** No.

## EXT-24. MEDIUM. NEW. Redundant layers inflate the count without adding coverage

Three layers test the same 43 examples, each strictly weaker than the next:
`test_codegen_zig.py:141-152` (compiles, asserts `len(content) > 0`) ⊂
`test_codegen_zig.py:174-190` (compiles + `zig ast-check`) ⊂
`test_examples_e2e.py:36-60` (compiles + ast-check + build + run + golden diff).
The outer layer subsumes both inner ones: 86 redundant tests.

`test_error_stage_matrix.py:40-52` re-runs the identical 61 CLI invocations
through `scripts/error_stage_common.py` with strictly weaker checks (no
`start_line`, no per-stage flags), doubling the file's runtime for nothing.

Five `test_cli_failures.py` tests duplicate `test_error_stage_matrix.py` on
byte-identical fixture text: `:32-46` ↔ `:86-107`, `:359-378` ↔ `:86-107`,
`:49-65` ↔ `:131-153`, `:381-389` ↔ `:248-253`, `:392-396` ↔ `:230-245`.

The semantic files are largely restatements of each other:
`test_semantic_analysis.py` duplicates `test_semantic_comprehensive.py` and
`test_semantic_control_flow.py` throughout and asserts less;
`test_semantic_expressions.py:333-344` is byte-equivalent to
`test_semantic_types.py:492-503` and `test_semantic_comprehensive.py:354-365`;
`test_semantic_types.py:469-480` and `:482-490` are the same test twice.

`test_iterative_traversal.py` has five subsumed pairs (`:435-443`, `:445-453`,
`:455-463`, `:465-473`, `:475-483`) plus `:678-686` duplicating `:245-248` at a
*higher* recursion limit — about 7 of its 44 tests.

**Fix direction.** Delete the subsumed layer, not the subsuming one.

**Changes accepted programs?** No.

## EXT-25. MEDIUM. NEW. Fuzzing is unreproducible and seeds the global RNG

`test_parser_fuzzing.py:354` constructs `RandomCodeGenerator(seed=42)`, whose
`__init__` calls `random.seed(42)` on the **global** `random` module (`:20-22`).
Every test that runs after it in the same process draws from a seeded stream. The
other fuzzing tests (`:219, 241, 260, 290, 314, 415, 442`) are unseeded, so a
parser bug can pass 99 runs and fail the 100th with an input nobody can recover.

Six of them place every assertion inside a `try` whose `except (TokenizerError,
ParseError): pass` swallows the interesting case: if the parser rejected *every*
generated program, all six pass having executed no assertion.
`:314` `test_parser_ast_invariants` walks only `declarations`/`body`/`statements`,
so expressions are never span-checked, and a swallowed `ParseError` skips it.
`:415` and `:442` contain no assertion at all beyond `pytest.fail` on a
non-`ParseError` exception.

**Fix direction.** A `random.Random(seed)` instance, never the module; the seed
printed on failure; a floor on the accepted fraction so a parser that rejects
everything fails.

**Changes accepted programs?** No.

## EXT-26. MEDIUM. NEW. The gate builds all 43 examples four times and writes into the repository

`run_all_tests.sh` compiles, builds and runs all 43 examples in
`verify_examples_e2e.py` (`:65`), again at `-ODebug` (`:68`), again at
`-OReleaseFast` (`:71`), and a fourth time inside `test_examples_e2e.py` during
the final pytest step (`:89`), which shells out to the same E2E script with a
180 s timeout. Measured full-suite pytest time is 247 s, of which the E2E
delegation is the dominant single test.

`build_examples.py` defaults its output to `ROOT / "build" / profile`
(`:282`) — inside the repository. It is `.gitignore`d, but it is a write into the
working tree during the gate, and `--clean` removes it again on the next run.

**Fix direction.** Drop `test_examples_e2e.py`'s full-corpus delegation (the
shell gate already runs it) or drop the shell step; `--jobs N` is scheduled as H4
(`execution.md:344`). Default `--out-dir` outside the tree.

**Changes accepted programs?** No.

## EXT-27. MEDIUM. NEW. `test_iterative_traversal.py`'s stated rationale is false, and most of its cases carry no stack pressure

`CLAUDE.md` says "The pipeline is validated at Python recursion limit 100 (see
`test/test_iterative_traversal.py`)". That is true for `TestLowRecursionLimit`
(`:219-419`), which sets the limit in `setup_method` and runs the full pipeline
through `A7Compiler().compile_file`. Three caveats:

1. Most cases have large headroom. Peak Python stack depth measured per compile:
   hello world 27, 50 statements 26, a 10-function call chain 26, 10 nested
   blocks 46, 10 nested ifs 66, 10 nested expressions 70. Under pytest (which
   enters a test body around depth 25) the deepest case leaves 5 frames of
   margin; the first three would pass at a limit of 55 and detect nothing.
2. The depth exercised is the parser's, not the passes'. The file's docstrings
   (`:5-7`, `:657-660`) claim "the semantic analysis passes and AST preprocessor
   are fully iterative"; `test_no_recursion.py:392-603` lists 36 recursive
   `type_checker` members, 7 in `semantic_validator`, 4 in `safety` and 2 in
   `ast_preprocessor`. Two test files in the same directory contradict each
   other.
3. `TestDeepNestingStress` (`:426-603`, 18 tests) runs at the default limit of
   1000 — a capacity smoke test. `TestLowLimitDeepNesting` (`:654-721`) uses 150,
   not 100, so `:678-686` is strictly weaker than `:245-248`.

Not covered at limit 100 anywhere: the console formatter (`format_type`,
`format_statement_label`, both allowlisted as recursive), `SymbolTable.dump`
(allowlisted), `--mode semantic`, `--mode doc`, and file-backed local imports
through `ModuleResolver.load_module` (allowlisted; only the virtual `std/io`
import is exercised).

**Fix direction.** Correct the docstrings. Add cases at limit 100 for the three
uncovered recursive entry points and for `--mode semantic`/`--mode doc`.

**Changes accepted programs?** No.

## EXT-28. MEDIUM. NEW. The no-recursion ratchet has three holes it does not state

`test_no_recursion.py` is well built: `:42-333` is a specification of the scanner
(8 kinds of recursion that must be reported, 5 patterns that must not), including
a test that scans the scanner itself (`:326-333`). The ratchet
`KNOWN_RECURSIVE_GROUPS` (`:392-603`) holds 31 groups / 148 functions — 43 in
`a7.backends.zig`, 36 in `a7.passes.type_checker`, 28 in `a7.parser`, 24 in
`a7.types`, 7 in `semantic_validator`, 4 in `safety`, 2 each in
`console_formatter` and `ast_preprocessor`, 1 each in `symbol_table` and
`module_resolver` — plus 1 deepcopy caller and 44 recursive dataclass methods.
All 19 tests pass on this tree.

Groups are compared as exact sorted-name tuples, so a new function joining a
listed group, or any brand-new group, fails the ratchet. Three things do not:

1. A new call edge *among existing members* of a listed group — making
   `Parser.parse_type` call `Parser.parse_expression` adds recursion paths and
   leaves the 21-name tuple unchanged.
2. Everything in the scanner's own stated limits (`test/norec_scan.py:57-64`):
   calls from class bodies and module level, operators other than `==`/`!=`,
   iteration protocols, descriptors other than `@property`, `exec`/`eval`, and
   dispatch through dictionaries of non-constant names on objects other than
   `self`.
3. Unresolved receivers. When a receiver's class cannot be inferred and the
   candidate methods live outside the caller's class family, the call is
   recorded but not linked — `:272-278` asserts exactly this
   (`result.edges.get("pkg.checker:Proxy.find") == set()`). Nothing asserts that
   `result.unresolved` over `a7/` is empty or bounded, so that channel is
   unratcheted.

**Fix direction.** Assert the edge count within each listed group, not only the
membership tuple, and add a bound on `result.unresolved` over `a7/`.

**Changes accepted programs?** No.

## EXT-29. LOW. NEW. A release-tooling test passes silently when zig is absent

`test_release_tooling.py:78-80`:

```python
if shutil.which("zig") is None:
    return
```

No assertion, no `pytest.skip`. On a machine without zig the test reports green
having verified nothing. Every other zig-dependent test in the suite either
skips explicitly (`test_codegen_zig.py`, `test_examples_e2e.py`) or fails loudly
(`test_pipeline_native.py:18-23`, `test_zig_backend_runtime.py:25-30`,
`test_module_alias_shadowing.py:50-55`, which all assert the zig binary exists
and is exactly 0.16.0).

Also in this file: `:52-57` `test_package_exports_compiler_api` asserts only
`is not None` and `callable()`; it should call `compile_a7_file` on a fixture.

**Fix direction.** `pytest.skip("zig not installed")`.

**Changes accepted programs?** No.

## EXT-30. LOW. NEW. `000_empty.a7`'s golden is an empty file

`examples/000_empty.a7` is `main :: fn() {}`; `000_empty.out` is 0 bytes. The
E2E check still proves the program compiles, passes `zig ast-check`, links, runs
and exits 0 in both profiles, and catches any *extra* output. But the golden
itself carries no information, and `normalize_output` maps both "" and "\n" to ""
(`verify_examples_common.py:67-74`), so the file cannot distinguish a program
that prints nothing from one that prints only a newline.

**Fix direction.** Keep the example (it is a real minimal case) and state in a
header comment that the empty golden is intentional, so the next reader does not
treat it as a missing fixture. Related: KNOWN PIP-28 (`pipeline.md:499`) — a
genuinely empty `.a7` file compiles to a 0-byte `.zig` with exit 0.

**Changes accepted programs?** No.

## EXT-31. LOW. NEW. `034_string_utils.a7` contains a dead branch

`examples/034_string_utils.a7:7-12`:

```
    for ch in text {
        if ch == '\0' {
            ret count
        }
        count += 1
    }
```

`for ch in text` iterates the string's actual bytes; a Zig string slice contains
no terminating NUL, so `ch == '\0'` never fires. The golden (`len = 9` for
`"Hello, A7"`) is correct, produced by the `ret count` at `:13`. The example
teaches a C idiom that does not apply to A7's string model, in the file a reader
opens to learn string handling.

**Fix direction.** Delete the branch, or replace the function body with a
`.len`-based one once `.len` works (KNOWN S12).

**Changes accepted programs?** **Yes** (edits an example). The golden is
unchanged.

## EXT-32. LOW. NEW. `test_semantic_comprehensive.py` promises inference and asserts acceptance

Roughly 45 of its 65 tests have docstrings claiming to test type *inference* or
type *checking* while asserting only that the program is accepted.
`:74-85` `test_integer_literals` ("Test integer literal type inference") would
pass if `0xFF` inferred as `string`. Same shape at `:87-95`, `:97-105`,
`:107-114`, `:116-123`, `:778-785`, `:787-795`, `:797-808`. `:853-874`
`test_linked_list_operations` compiles 15 lines and asserts one boolean.

Its `run_analysis_expect_error` (`:62-68`) takes no message fragment at all, so
`:331-339`, `:653-660`, `:662-669`, `:714-720`, `:722-728`, `:730-738` accept any
`CompilerError` including a `ParseError`.

These are not counted in the 1223 because they *would* fail if acceptance
flipped — they are weak, not vacuous.

**Fix direction.** Assert `checker.node_types` for the named variables. The
machinery exists and is used correctly in `test_semantic_types.py:321-391`.

**Changes accepted programs?** No.

## EXT-33. LOW. NEW. An unfalsifiable assertion in the char-escape test

`test_codegen_zig.py:1020` `test_char_escape_newline`. The sole assertion is
`assert '\n' not in line.split("'")[1] if line.count("'") >= 2 else True` — a
ternary that is `True` on the else branch, and on the other branch `'\n'` cannot
occur inside a `splitlines()` fragment. It can never fail.

**Fix direction.** Assert `const nl = '\\n';` appears verbatim in the emitted
Zig.

**Changes accepted programs?** No.

## EXT-34. LOW. NEW. `test_empty_program` asserts only a Python type

`test_codegen_zig.py:1028`: `assert isinstance(zig, str)`. The generator's return
annotation is `str`, so the assertion cannot fail.

**Fix direction.** Assert the exact emitted output for a comment-only file — in
particular that it contains no `pub fn main`.

**Changes accepted programs?** No.

## EXT-35. LOW. NEW. `test_example_compiles` accepts any non-empty output

`test_codegen_zig.py:143`, 43 parametrized cases: asserts `result` truthy,
`output.exists()` and `len(content) > 0`. A backend that emitted `// x` for every
example would pass all 43. The next layer up, `TestZigAstCheck::test_ast_check`
(`:176`), already compiles the same 43 files *and* runs `zig ast-check`, so this
layer adds nothing (see EXT-24).

**Fix direction.** Delete it; `:176` subsumes it.

**Changes accepted programs?** No.

## EXT-36. LOW. NEW. `test_semantic_analysis.py` asserts nothing about semantic analysis

`:207-226` `test_break_in_loop_valid` has **no assertion at all**, under a comment
reading "# Should not raise" — but `SemanticValidationPass.analyze` collects into
`.errors` and never raises (`a7/passes/semantic_validator.py:52`, docstring
"Collects ALL errors instead of stopping"). Its neighbours `:47-63`, `:254-282`
and `:284-308` assert only `x is not None`; `:44-45` and `:95-96` assert
`symbols.lookup("main").name == "main"`, which a name-keyed lookup cannot
violate; `:80-96` is named `test_struct_field_registration` and never looks at a
field.

**Fix direction.** `assert validator.errors == []` after each accepted program,
and for `:254-282` assert `checker.node_types` gives `result` the type `i32`. The
file is otherwise a weaker restatement of `test_semantic_comprehensive.py` and
`test_semantic_control_flow.py` and could be deleted (EXT-24).

**Changes accepted programs?** No.

---

# What is missing

| Item | What exists now | What it needs | Decision owner | Priority for v1 |
| --- | --- | --- | --- | --- |
| A trustworthy cast-safety suite | 1240 mirrored tests | A hand-written 225-pair expectation table derived from SPEC | none — pure test work | **1** |
| Safety-pass rejection tests | Only the mirrored matrix | Paired unsafe/guarded A7 sources through the real CLI, exact exit code, message and span | `execution.md:387` schedules it at Wave 3.3, behind the IR — too late | **1** |
| Precedence and AST-shape assertions | 281 "did not raise" tests | One parametrized tree-shape test per grammar rule | none — pure test work | **1** |
| `testpaths` and `tmp/` exclusion | Nothing | `[tool.pytest.ini_options] testpaths = ["test"]`; `tmp/` in `.gitignore` and the secret-scan skip list | H5, `execution.md:344` | **1** |
| An example that is rejected on purpose | Nothing in `examples/` | An `examples/errors/` tier with expected exit code and diagnostic per file, run by the same harness | **none** | 2 |
| Examples for `[]T`, `.len`, `pub`, `@type_set`, `fall` | Zero each | Blocked on the compiler (`.len` KNOWN S12) or on a language decision (`pub` under the visibility redesign, `execution.md:24`) | G-level for `pub`; lane E `047_match_fall`, `054_generic_constraints` for the rest | 2 |
| Examples for `std/mem`, `std/string` | Both modules unregistered and unreachable | Register them, then examples; or delete them and correct `CLAUDE.md:44-45` | none — overlaps `stdlib.md` | 2 |
| A multi-file example | Zero; all 42 imports are `std/*` | `examples/apps/calc_vm/` plus harness discovery of `examples/apps/*/main.a7` | H1 + `execution.md:398` | 2 |
| Input, file and argument examples | Zero; the harness passes no stdin and no argv | `test/fixtures/stdin/`, `test/fixtures/args/`, timeout semantics | packet **P9**, `execution.md:405`; **file I/O has no owner at all** | 2 |
| A SPEC section defining `{}` output formatting | Nothing; 43 goldens encode Zig's `std.fmt` defaults | SPEC text, then the goldens follow from it | **none** (lane D's list at `execution.md:350` omits it) | 2 |
| Allocation accounting for `new`/`del` examples | Exit code and stdout only | A checked allocator in the Debug build, or a `checks: N/N ok` self-check line | `execution.md:369` defines the self-check line but only for Wave 2.3 apps | 3 |
| Exit-code-8 coverage | Asserted nowhere; produced today | An assertion that no source-level failure returns 8, plus a positive internal-fault test | none | 3 |
| stderr as a separate golden stream | Merged into stdout by both harnesses | A second fixture per example, or a `--split-streams` mode | none; `048_stderr_output` at `execution.md:348` will need it | 3 |
| A golden-update workflow with a diff | `--update-golden` rewrites all 43 silently | `--example` scoping, a printed diff, confirmation | H3, `execution.md:344` | 3 |

# Checked and correct

- **All 43 examples are in the E2E set and all 43 goldens are checked**, in
  Debug (`verify_examples_e2e.py`, `build_examples.py --profile debug`) and in
  ReleaseFast (`--profile release`), against the same golden — so cross-profile
  output equality is enforced. `uv run python scripts/verify_examples_e2e.py`
  exits 0, `Examples verified: 43/43`.
- **No golden is stale.** Regenerating all 43 into a scratch directory produces a
  byte-identical tree (`diff -rq`, exit 0).
- **The examples comply with the reference-syntax rule.** No `.adr`, `.val`,
  prefix `&` or prefix `*` used as a reference operation anywhere in
  `examples/*.a7`; no `new [N]T`; no recursive A7 function.
- **No test writes into the repository working tree.** Every test-authored source
  and output goes to `tmp_path` or the system temp directory. The only writes are
  indirect and gitignored: `build/<profile>` from `build_examples.py:282`, and
  `a7_py.egg-info/` from the `uv build` that `test_release_tooling.py:60-76`
  invokes.
- **CLI exit codes 0, 2, 3, 4, 5, 6 and 7 are asserted at the real process
  boundary**, in `test_cli_failures.py` (20 of 20 tests),
  `test_error_stage_matrix.py` (61 scenarios × mode × format) and
  `scripts/error_stage_common.py:195-279`.
- **Negative diagnostics are checked for line *and* column.**
  `test_pipeline_diagnostics.py:43-58` (line 3, columns 10/10/5 for
  tokenize/parse/semantic), `:100-113` (line 3, column 5 inside an imported
  module), `:61-77` (line 2, column bounded deliberately), plus
  `test_parse_termination.py:123-124, 140` and
  `test_compound_assignment_types.py:114-122` and
  `test_recursion_detection_scaling.py:117-166`.
- **Compiled programs are run and their stdout checked in 15 tests outside the
  E2E script**: `test_zig_backend_runtime.py` (7, both profiles, exact stdout
  *and* stderr, one redirecting to real files to catch a writer restarting at
  offset 0), `test_module_alias_shadowing.py` (5, both profiles),
  `test_codegen_zig.py` (6, `:213, 320, 363, 434, 793, 973`),
  `test_pipeline_native.py` (2, both profiles).
- **Seventeen test files contain no coverage-illusion tests at all** — listed in
  §2.1. `test_recursion_detection_scaling.py:169-240` is the best example in the
  repository of a correct oracle: it reimplements the *replaced* exponential
  algorithm as an independent reference rather than mirroring the code under
  test.
- **No evidence of order dependence.** `pytest-randomly` is not installed, so the
  order could not be randomized; but the 12 pipeline failures are identical when
  those three files are run alone (`12 failed, 4 passed`) and inside the full run,
  and the 7 tokenizer failures are explained entirely by `FORCE_COLOR`.
- **Runtime is not a problem.** Full suite 247 s, dominated by
  `test_examples_e2e.py`'s 43-example delegation and the zig-building tests; the
  509 parser and tokenizer tests run in 1.4 s.

# Test gaps

Behaviors with no test at all, ordered by risk:

1. **The safety pass rejecting an unsafe program** — out-of-bounds indexing,
   division by zero, use-after-`del`, an unproven narrowing cast. The only
   rejection tests are the mirrored ones in `test_cast_safety_matrix.py`
   (EXT-01, EXT-07).
2. **Operator precedence and associativity** (EXT-02) — zero tests detect a total
   flattening.
3. **Type-expression nesting order** — `[5]ref [10]i32` versus `ref [5][10]i32`,
   `[5][]ref [10]ref struct{…}`: 35 tests parse these spellings and none asserts
   the order (EXT-03).
4. **Integer overflow and wrapping** (ledger L5) — no test mentions it
   (`docs/plan/audit/language-audit-checklist.md:56`); confirmed, and no example
   either.
5. **Element-wise array arithmetic** (`docs/SPEC.md:262-266`) — exercised only by
   `examples/035_matrix.a7`; no test.
6. **`new`/`del` allocation accounting** — no leak, double-free or
   missing-free detection anywhere (EXT-20).
7. **Exit code 8** — never asserted, demonstrably reachable (EXT-22).
8. **Inferred types for literals and expressions** — asserted only in
   `test_semantic_types.py:321-391`; ~45 tests claim it and assert acceptance
   (EXT-32).
9. **Generic constraints (`@type_set`)** — no test constrains a generic
   parameter and then calls it with a violating type. The one test named for it
   never applies the constraint, so whether checking works is unknown (EXT-04).
10. **Generic enums and unions** — `Some: $T` does not parse; the test calls the
    resulting `ParseError` a semantic rejection (EXT-04).
11. **File-backed local imports at recursion limit 100** —
    `ModuleResolver.load_module` is allowlisted as recursive and only the virtual
    `std/io` path is exercised (EXT-27).
12. **Console formatter and `SymbolTable.dump` at limit 100** — both allowlisted
    as recursive, neither covered (EXT-27).
13. **`--mode semantic` and `--mode doc` under stack pressure** (EXT-27).
14. **Trailing whitespace and stderr routing in example output** — normalized
    away and merged, respectively (§1.4).
15. **Cross-file struct and enum name prefixing** — `execution.md:398` records
    that only functions get `module_emit_prefix`; no test, and no example uses a
    local import.
16. **Interactions with no test**, from
    `docs/plan/audit/language-audit-checklist.md:101-106`: generics through a
    module alias; `defer` × loops × `break`; casts × constant folding; methods ×
    generics; imports × visibility. Confirmed still uncovered.

# Not verified

- **Whether the 7 `test_tokenizer_errors.py` failures also occur in CI.** I
  showed they are caused by `FORCE_COLOR=3` in this shell and vanish under
  `NO_COLOR=1`. CI's environment was not inspected. UNVERIFIED.
- **Whether `uv build` writes `a7_py.egg-info/` during
  `test_release_tooling.py:60-76`.** The directory exists in the tree and
  `pyproject.toml:16` uses `setuptools.build_meta`, so it is the expected
  behavior, but I did not run `uv build` to confirm. INFERENCE.
- **`--lf` order sensitivity.** I ran the suite with `-p no:cacheprovider`, which
  disables the last-failed cache, so `--lf` was not exercised. `pytest-randomly`
  is not installed, so randomized ordering was not exercised either. Both are
  SKIPPED, not passed.
- **Whether the ref-splitting workaround in `013`/`017`/`037` was ever
  necessary.** It does not reproduce on this tree or at `HEAD` (`701c679`). It
  may have been needed at an older commit; I did not bisect. UNVERIFIED. The
  `HEAD` extraction used for this probe now lives outside the repository at
  `/home/cx89/.claude/jobs/4e152702/tmp/examples-tests-head-tree/` (see EXT-09).
- **The per-file "would still pass" counts for the 20 parser/tokenizer files and
  the 14 backend/CLI files** were produced by delegated readers. I re-derived and
  confirmed the totals for `test_parser_type_combinations.py` (35/35),
  `test_parser_creative_cases.py` (31/31),
  `test_parser_unicode_and_special.py` (19/19),
  `test_cast_safety_matrix.py` (measured by mutation), the 31
  `isinstance(result, bool)` sites, the four semantic tests hiding defects, the
  dead `stdlib` entry points, `_lower_field_sugar`, and the six `assert True`
  sites, by reading the code directly. The remaining per-file numbers are
  reported as given. INFERENCE.
- **The suite grew during this audit.** `test/test_stdlib_call_resolution.py`
  appeared at 22:10 on 2026-09-18 (another agent's work), taking the collected
  count from 2587 to 2594. Every count in this report is against the 2587
  snapshot taken at the start.

claims checked: 124
