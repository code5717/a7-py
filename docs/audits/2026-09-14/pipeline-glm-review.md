# A7 Compiler Pipeline Review — Z.AI GLM-5.3 (external reviewer)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

- **Date**: 2026-09-14
- **Reviewer**: Z.AI GLM-5.3, compiler-pipeline reviewer (advisory; invited by the controlling Codex session)
- **Revision audited**: `701c679` ("Bump anthropics/claude-code-action …") plus uncommitted working-tree changes limited to documentation (`README.md`, `docs/SPEC.md`, `docs/lang-safety/README.md`, `site/public/docs/index.md`, `site/public/llms-full.txt`, new `docs/README.md`, new `docs/audits/`). No compiler-source diff is present; all findings are against committed compiler code.
- **Working-tree note**: during this audit the controlling session added three untracked test files (`test/test_pipeline_artifacts.py`, `test/test_pipeline_diagnostics.py`, `test/test_pipeline_native.py`) and modified `AGENTS.md`. The new tests encode intended behavior that the implementation does not yet satisfy; they are the failing "regression" tests cited in RB-4 and were verified to fail from the CLI independently of the test harness.
- **Scope**: tokenization, parsing, semantic passes (name resolution, type checking, semantic validation, safety proof), preprocessing, generic specialization, module resolution, Zig generation, pipeline orchestration, diagnostics (human + JSON), error-stage classification, and the test suite that guards them. Memory-runtime behavior is owned by other reviewers; I ran **compile-only** checks and did not execute any compiled payload.
- **Method**: full source read of `a7/` (18,606 lines) and `test/` spot reads; behavior verified by running the installed CLI (`.venv/bin/python -m a7.cli`) on minimal trusted fixtures in a temp directory; emitted Zig validated with the provided Zig 0.16.0 (`/tmp/a7-audit-20260914/zig/zig build-obj -fno-emit-bin`, compile-only). Minimal reproductions are checked in under `docs/audits/2026-09-14/repros/glm-pipe-*.a7`.

## Environment / unavailable capabilities (recorded per instructions)

- Full release gate (`run_all_tests.sh`) intentionally not run (audit-only mandate); the coordinator owns it.
- `zig` is **not** on `PATH` in this shell. With `/tmp/a7-audit-20260914/zig` prepended, the full pytest suite runs; `test_release_tooling.py` still fails because `uv` resolves through a mise shim with no version set (`mise ERROR No version is set for shim: uv`) — an environment limitation, not a compiler defect.
- No web tools or nested model CLIs were used. No authentication failures occurred (no authenticated services were needed).

## Executive summary

The pipeline architecture is sound and unusually disciplined for a young compiler: distinct exit codes per stage, a structured error taxonomy, an obligation/approval contract between the safety pass and the backend (`BackendPlan.require`), and genuine subprocess-level stage-matrix tests. Core guarantees I could verify as **working** include: recursion rejection (direct, mutual, and shadowing-aware, with no false positive on a local that shadows a function name), use-after-`del`, cast classification with range proofs, match redundancy/exhaustiveness diagnostics, `new`/nil-guard discipline, and tokenizer-stage rejection of tabs, unterminated strings/chars, and bad literals.

However, the checkout is **not release-ready**:

1. The parser **hangs forever** on `match x { foo }` (statement context) — trivially reachable DoS.
2. `--output`/`--doc-out` pointing at the input file **silently overwrites the .a7 source** (data loss).
3. The recursion-cycle search is **exponential** (~4× per added function; 26 functions ≈ 17 s, 34 ≈ hours).
4. The full pytest suite currently reports **15 failures**, at least 13 of which are compiler- or pipeline-real (not environment).
5. The "safety proof" discharges loop-body index obligations with **first-iteration facts only**, so a `[1]i32` accessed at `arr[i]` for `i < 3` passes the proof and builds under `-O ReleaseFast` with no bounds check — the static-guarantee claim is currently unsound for loop-varying indices.
6. A family of false positives makes ordinary numeric code unrepresentable (`f :: fn() u8 { ret 0 }`, `f(5)` into a `u8` parameter, `x: u8 = 100 + 100`), while a complementary family of false negatives (undefined struct names, unknown/missing struct fields, mixed-width arithmetic, `1e999`) passes a7 and only fails later as invalid Zig.

Severity legend: **[RB]** release-blocking, **[H]** high, **[M]** medium, **[L]** low. Classification: *defect* (confirmed misbehavior), *design gap* (documented/roadmapped absence), *hypothesis* (unverified suspicion — none of the headline findings are hypotheses).

---

## 1. Release-blocking defects

### RB-1 Parser infinite loop on unexpected token in `match` statement body
- **Where**: `a7/parser.py:2235-2261` (`parse_match_statement`). The `while not RIGHT_BRACE and not at_end()` loop only advances on `case`/`else`; any other token neither matches a branch nor advances → live-lock. The expression-context sibling `parse_match_expression` correctly raises (`a7/parser.py:1874-1880`).
- **Evidence**: `docs/audits/2026-09-14/repros/glm-pipe-match-statement-garbage.a7` — `--mode ast` never returns (killed by `timeout`, exit 124). Control: the same token inside a `match` *expression* yields a clean parse error.
- **Fix shape**: mirror the expression parser's `else: raise ParseError("Expected 'case' or 'else' in match statement", …)`.

### RB-2 `--output` / `--doc-out` equal to the source path destroys the input file
- **Where**: `a7/compile.py:434-451` (compile-mode write) and `a7/compile.py:453-482` (doc write) write to `result.output_path`/`doc_path` with no equality check against `input_path`.
- **Evidence**: `a7 prog.a7 --mode compile -o prog.a7` exits 0 and leaves `pub fn main() void {}` where the A7 source was (reproduced directly). `--doc-out` writes markdown over the source the same way. Failing regression tests: `test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--output/--doc-out]`.
- **Fix shape**: reject `Path(output).resolve() == Path(input).resolve()` with `ExitCode.USAGE` before any write (also covers suffix collisions like `--doc-out` on `x.md` when input is `x.md`).

### RB-3 Exponential recursion-cycle search
- **Where**: `a7/passes/semantic_validator.py:534-544` (`_find_recursion_path`) is a DFS over *simple paths* with no memoized "cannot reach start" set; `_validate_no_recursion` calls it for every function (`:520-532`).
- **Evidence**: generated files where `g_i` calls `g_0..g_{i-1}` (acyclic): n=18→0.15 s, n=20→0.32 s, n=22→1.06 s, n=24→3.94 s, n=26→17.0 s (~4× per +2 functions). A 60-function file is intractable. Regular call graphs are fine; the pathological shape is a plain fan-in chain any generated code can produce.
- **Fix shape**: one SCC pass (Tarjan/Kosaraju, iterative) over the call graph; report one error per cyclic SCC.

### RB-4 Currently failing regression tests (suite is red)
Full run with provided Zig on `PATH`: **15 failed, 2512 passed, 46 skipped** (`python -m pytest test/ -q`). Breakdown:

| Test | Verdict | Root cause (this report) |
|---|---|---|
| `test_pipeline_native.py::test_large_integer_folding_preserves_exact_quotient_and_remainder` | compiler-real | M-1 float-division folding precision |
| `test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels` | compiler-real | H-2 recursive-descent parser |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[zig-keyword-local]` | compiler-real | M-6 decl-site keyword escaping |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[unused-loop-capture]` | compiler-real | M-7 unused for-in captures |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[shadowed-loop-capture]` | compiler-real | M-7 shadowed for-in captures |
| `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[parse]` | compiler-real | H-4 operator column off-by-one (expects col 10, gets 9) |
| `test_pipeline_diagnostics.py::test_missing_import_diagnostic_locates_import_declaration` | compiler-real | M-2 spanless module-not-found error |
| `test_pipeline_diagnostics.py::test_imported_parse_error_is_a_source_failure_with_module_location` | compiler-real | H-8 imported-file spans |
| `test_pipeline_diagnostics.py::test_imported_semantic_error_preserves_origin_file` | compiler-real | H-8 imported-file spans |
| `test_pipeline_artifacts.py::test_cli_rejects_input_destination…[--output]` | pipeline-real | RB-2 |
| `test_pipeline_artifacts.py::test_cli_rejects_input_destination…[--doc-out]` | pipeline-real | RB-2 |
| `test_pipeline_artifacts.py::test_failed_compile_does_not_advertise_stale_output` | pipeline-real | artifact advertising after failed/overwritten compile (same family) |
| `test_pipeline_artifacts.py::test_output_write_failure_does_not_advertise_directory_as_artifact` | pipeline-real | artifact check `Path.exists()` on directories |
| `test_release_tooling.py::test_installed_cli_entrypoint_works`, `…wheel_install_smoke…` | environment | mise `uv` shim unset — not a compiler defect |

These are written to encode the *intended* behavior (the tests are not wrong); the implementation regressed or never satisfied them.

### RB-5 a7-accepted programs emit invalid Zig (deferred diagnostics / silent misbehavior)
All of the following exit 0 from a7 and fail `zig build-obj` (each verified with the provided Zig):

| Input pattern | a7 result | Zig failure | Source |
|---|---|---|---|
| `ret a + b` with `a: u8, b: u32` | ok, result typed `u8` | `expected type 'u8', found 'u32'` | `type_checker.py:1214-1227` (result = left operand; comment claims "wider of the two") |
| `p := Point{…}` with `Point` undefined | ok | `use of undeclared identifier 'Point'` | `type_checker.py:2721-2737` returns UNKNOWN silently |
| `P{x:1, z:9}` (unknown field), `P{x:1}` (missing field) | ok | `no field named 'z'` / missing field | `type_checker.py:2758-2786` checks only fields it finds by name; no exhaustiveness/unknown-field diagnostic |
| `P{1,2,3}` (extra positional) | ok | `does not support array initialization syntax` | normalization bails at >field count (`ast_preprocessor.py:262-268`) |
| `x := 1e999` | ok | `var x = inf.0;` → syntax error | `backends/zig.py:1479-1483` (`str(float('inf'))` + `.0` suffix) |
| `local := 1` named `error` | ok | `const error = 1;` → keyword | decl-site escaping missing (`zig.py:644-653`; escaping exists only for references, `zig.py:1505-1516`) — failing test `zig-keyword-local` |
| `x := 1 … for x in arr` | ok | `capture 'x' shadows local constant` | iterator names never renamed (`zig.py:920-964`; preprocessor pass 7 renames VARs only) — failing test `shadowed-loop-capture` |
| `for x in arr {}` with unused `x` | ok | `unused capture` | no `_`/discard for unused captures — failing test `unused-loop-capture` |
| `x := 2147483648` used as i32 | ok | `type 'i32' cannot represent integer value` | default literal typing has no range check (`type_checker.py:1163-1166` gives every integer literal `i32`) |

The struct-literal family is the most damaging: it converts what should be first-class semantic diagnostics into backend/Zig errors with A7-foreign wording. Repro: `docs/audits/2026-09-14/repros/glm-pipe-struct-init-gaps.a7`, `glm-pipe-mixed-width-arith.a7`.

---

## 2. High-severity defects

### H-1 Safety proof is unsound for loop-carried facts (index obligations)
- **Where**: `a7/safety.py:353-363` — FOR visits `init, condition, body, update` and restores facts at the end; `:311-327` — an assignment (including `i += 1`) **overwrites** the symbol fact with the RHS fact (`1` → exact(1)) after the body was already checked; WHILE/FOR conditions never refine bounds (`_facts_from_condition` only produces `>=` lower bounds, `:678-703`).
- **Consequence**: `arr[i]` inside `for i := cast(usize,0); i < 3; i += 1` is "proven" with the fact `i == 0` from the init statement. Repro `glm-pipe-loop-index-unsound.a7`: a7 exits 0; emitted Zig builds with `-O ReleaseFast`; `arr` is `[1]i32`, indices 0..2, no inserted bounds check → OOB read is UB at runtime (not executed, per audit rules). This contradicts the language's "no flag, no runtime check, no trap" posture (`docs/lang-safety/README.md:125`) for exactly the loop-index pattern the examples rely on (`examples/042_gradebook.a7:27-31`).
- **Fix shape**: check loop bodies under a widened/join fact (⊥ if the modified set is not expressible), i.e. obligations inside a loop must be proven for the *join* of pre- and post-update facts, or loop-carried indices must be rejected unless the object length dominates the loop bound.

### H-2 Deep nesting crashes with `RecursionError` (exit 8) despite the "iterative" claim
- **Where**: the parser is genuinely recursive (`parse_expression → parse_unary → parse_postfix → parse_primary → paren → parse_expression`; `parse_statement → parse_if → parse_statement`). AGENTS.md's "compiler internals already use iterative AST traversals" is true for *passes*, not the parser.
- **Evidence**: 5000 nested parens → `internal / RecursionError` (exit 8, no span); 2000 nested `if true {` → same. `test_iterative_traversal.py::TestLowRecursionLimit::test_nested_expressions_10_levels` fails at `sys.setrecursionlimit(100)` with only 10 levels (~10 Python frames per A7 level).
- **Fix shape**: either bound expression nesting at tokenize/parse entry with a clean diagnostic, or add a depth counter in the recursive descent raising `ParseError("expression too deeply nested")`.

### H-3 >1000 declarations per file: hard cap + stdout warning corrupts `--format json`
- **Where**: `a7/parser.py:153` (`max_iterations = 1000`), `:201-206` (`print("Warning: Parser stopped …")` to stdout).
- **Evidence**: a generated 1200-function file exits 5 with `Unexpected token … after parsing complete program`, and the warning line precedes the JSON object on stdout, so `json.loads(stdout)` fails for any tooling consuming `--format json` (`manydecls` probe: stdout begins `Warning: Parser stopped after 1000 iterations in manydecls.a7`).
- **Fix shape**: raise the cap or make it a real `ParseError`; warnings belong on stderr (and should be structured in JSON mode).

### H-4 Operator and terminator token columns are off by one
- **Where**: `a7/tokens.py:364-376` — `_add_token` computes `column = self.column - len(value)`, which assumes it is called *after* the token text was consumed (true for identifiers/numbers). `_try_operator` (`:825-955`) and the newline handler (`:297-299`) call it *before* `advance()`.
- **Evidence**: `Tokenizer('a + b\n')` → `PLUS col 2` (actual 3), `TERMINATOR col 5` (actual 6). Downstream: every parse-error span anchored to an operator points one column left; failing test `test_cli_source_diagnostic_points_to_offending_token[parse]` (expects 10, gets 9). Identifiers/literals/keywords are correct, which is why most golden spans pass.
- **Fix shape**: pass `start_column` explicitly in `_try_operator`/newline paths (as the number paths already do).

### H-5 `while true { ret … }` falsely rejected as MISSING_RETURN
- **Where**: `a7/passes/semantic_validator.py:1253-1304` — `_returns_on_all_paths` has no case for diverging loops; `type_checker.py:617-621` explicitly documents infinite loops as *not* an error, so the two passes disagree.
- **Evidence**: `glm-pipe-while-true-ret.a7` (also `for { ret 1 }`) → `Missing return statement: Function 'spin' does not return on all paths` (exit 6). Zig itself accepts `while (true) { return 1; }` as noreturn.
- **Fix shape**: treat `while <true-literal>` / condition-less `for` whose body returns-on-all-paths as returning.

### H-6 Literal-fit rules not applied to returns and call arguments (false positives)
- **Where**: initializers/assignments use `_is_initializer_assignable_to` with `_integer_literal_fits_type` (`type_checker.py:2866-2940`); returns use bare `is_assignable_to` via `context.validate_return` (`type_checker.py:1073-1103`, `semantic_context.py:344-377`); call arguments likewise (`type_checker.py:1396-1403`).
- **Evidence** (`glm-pipe-literal-fit-gaps.a7`): `f :: fn() u8 { ret 0 }` → *Return type mismatch: expected 'u8', got 'i32'*; `takes(5)` with `x: u8` → *Argument type mismatch*; `takes(0)` with `x: u32` → same. Every small literal into a narrower parameter is rejected.
- **Fix shape**: route return/argument checks through the same literal-aware helper.

### H-7 Constant expressions are not range-analyzed before typing (false positive)
- **Where**: constant folding runs *after* semantic analysis (`ast_preprocessor.py:543-694`, invoked at `compile.py:389-394`), so `100 + 100` is typed `i32` at check time.
- **Evidence**: `z: u8 = 100 + 100` → `Type mismatch: expected 'u8', got 'i32'` although the value fits. (Contrast `z: u8 = 200`, accepted.)
- **Fix shape**: evaluate literal-only expressions during `_is_initializer_assignable_to` (the evaluator already exists in the preprocessor and in `type_checker._range_const_expr_value` for match patterns).
- Note (2026-09-16): whether constant expressions are typed (wrap) or exact (fit-checked) is still open under gate G3 in the [v1 plan](../../plan/README.md).

### H-8 Imported-file diagnostics carry wrong file attribution and rendered context
- **Where**: `compile.py:246-267` merges module declarations into the main AST, then all passes run with the *main* file's `source_lines` and filename; spans embedded in imported nodes point into the imported file.
- **Evidence** (compile mode, `mods/badmod.a7` with `ret undefined_var` at its 2:9): error reported as `moderr.a7:2:9: Undefined type (Identifier 'undefined_var')` — line 2 of the *main* file is `main :: fn() {`. Human rendering underlines a bogus region of the main file (caret under `x := bad.h`). Failing tests: `test_imported_parse_error_is_a_source_failure_with_module_location`, `test_imported_semantic_error_preserves_origin_file`.
- **Related mode inconsistency**: `--mode semantic` does not run the merge (`compile.py:252-261` gates it on codegen modes), so a file-module qualified call that compiles fine in `--mode compile` (`m.double(21)` → `module_mods_goodmod__double`) is rejected in `--mode semantic` as `Unknown stdlib call '…helper'`. Modes disagree about program validity.
- **Fix shape**: carry per-node file context (or run passes per-module with their own source lines), and make the semantic stage perform the same module combining as codegen modes.

### H-9 Circular-import detection is dead code
- **Where**: `a7/module_resolver.py:124-197` — `loaded_modules[module_path]` is populated (line 187) *before* dependencies are recursively loaded (line 190), so the `loading_stack` cycle check (line 131) can never fire through the cache-first early return (line 124).
- **Evidence**: `mods/ca.a7` ↔ `mods/cb.a7` mutual import, plus a self-import — all compile successfully (exit 0). The class docstring (`:32-35`) claims circular-dependency detection; `CIRCULAR_IMPORT` is a defined error type that this path can no longer produce. Harmless today because module flattening makes the emitted Zig acyclic, but the contract is unenforced.
- **Fix shape**: check `loading_stack` before the cache return, or detect cycles in `load_program_dependencies` via DFS-finish ordering.

### H-10 Non-ASCII digits: crash or silent acceptance
- **Where**: `a7/tokens.py:307,312,532,540,564` use Python's Unicode-aware `str.isdigit()`; `a7/ast_nodes.py:587` then calls `int(value)`.
- **Evidence**: `x := ²` → tokenizer emits `INTEGER_LITERAL('²')`, `int('²')` raises `ValueError` → exit 8 (`internal`, no span, empty details). `x := ٣` (Arabic-Indic three) tokenizes *and* `int()`s cleanly → compiles to `var x = 3;` (silently accepted, inconsistent with identifiers which are ASCII-only). Repro: `glm-pipe-unicode-digit.a7`.
- **Fix shape**: gate number scanning on `ch.isascii() and ch.isdigit()`; report non-ASCII digits as `INVALID_CHARACTER`.

---

## 3. Medium-severity defects and quality issues

- **M-1 Constant-folding precision bug (failing regression test)** — `ast_preprocessor.py:621,624`: integer division/mod folding computes `int(lval / rval)` through binary float, losing precision ≥ 2^53. `test_large_integer_folding_preserves_exact_quotient_and_remainder` fails with `9007199254740992 1` instead of `9007199254740993 0`. Use `lval // rval` (sign-corrected) for ints.
- **M-2 Module-not-found error has no location** — `module_resolver.py:138-142` constructs the `SemanticError` without span; JSON `span: null`; failing test `test_missing_import_diagnostic_locates_import_declaration`. Attach the IMPORT declaration span (available at the call site).
- **M-3 `MAX_STRING_LENGTH` unenforced** — declared `tokens.py:16`, never referenced; a 40,000-char string compiles. Either enforce or delete (and drop `TOO_LONG_STRING` from the taxonomy or keep it tested).
- **M-4 Diagnostic-code reuse blurs categories** — safety obligations reuse `UNSAFE_CAST` for division/mod (`safety.py:561`) and `INDEX_NOT_INTEGER` for bounds failures (`:568,574`), producing e.g. `Unsafe type cast (division/modulo divisor must be non-zero: divisor may be zero)`. JSON consumers keying on `error_type` will misclassify. Add `DIVISOR_NONZERO`/`INDEX_OUT_OF_BOUNDS` types.
- **M-5 Struct-literal statement-context heuristic is fragile** — `parser.py:108-144` scans back ≤10 tokens for assignment vs control keywords. An `if` condition ≥10 tokens ending in an identifier before `{` misparses the identifier as a struct literal (`longcond` probe: 9 `and`-joined identifiers → `Expected RIGHT_BRACE, got ASSIGN`). The explicit suppression flag exists only for C-style-for update clauses (`parser.py:1242-1245`). Fix: set `_suppress_struct_literals` while parsing if/while/match conditions.
- **M-6 Newline between `fn()` and `{` misparses a function as a type alias** — `parser.py:484-526`: `_is_fn_type_alias` treats a TERMINATOR after `)` as "no body". `f :: fn()\n{ ret 1 }` → `Unexpected token '{' after parsing complete program`. Style-sensitive false rejection.
- **M-7 Statement terminators are optional everywhere** — `x := 5 y := 6` on one line compiles (two statements). Parsing treats terminators as pure separators (`parse_block` loop). Spec ambiguity at minimum; recommend requiring a terminator between same-line statements (cheap lookahead check after an expression statement).
- **M-8 Radix-literal boundaries split silently** — `0b12` lexes `0b1` then `2`; error only surfaces as a confusing later parse error (`Unexpected token '2' after parsing complete program`). Same for `0x1G`. Recommend requiring a delimiter/non-identifier next char after radix digits.
- **M-9 Dead or vestigial code** — `compile.py:251` `backend_import_errors` is always empty (a "Backend Import Support" pass that can never fail); `generics.py:224` `instantiate_struct` reads `field.type` but `StructField` defines `field_type` (AttributeError if ever called — currently dead); `errors.py:844` shadows builtin `ImportError`; `type_checker._expression_is_known_nonnegative` (`:1938`) and the whole `_nonnegative_vars` fact machinery is never read; `backends/base.py:44-47` `generic_visit` uses nonexistent `node.children`; `backends/base.py:9` imports `ASTNode` from `parser` via import side effect.
- **M-10 Uninitialized locals are silently zero-initialized** — `zig.py:685-689` emits `_default_value` (0). SPEC documents the zero-init (`docs/SPEC.md:202`) so this is a *design gap*, but there is no warning for read-before-assign and no definite-assignment analysis anywhere; the safety pass tracks `initialized` on `ValueFact` (`safety.py:144`) but never consults it.
- **M-11 Nested local functions are unusable** — `name_resolution.py`'s iterative `visit_statement` (comment at `:516`) has no FUNCTION case, so `inner :: fn() … ret inner()` reports `Undefined type (Identifier 'inner')`. Meanwhile the validator (`semantic_validator.py:610-615`), preprocessor (`_hoist_nested_functions`), and backend (`_collect_nested_functions`) all contain nested-function machinery — the layers disagree; only the name-resolution pass blocks the feature.

## 4. Design gaps (documented, verified as intended)

- Integer-overflow obligations are explicitly disabled — `safety.py:631-636` returns before the proof; roadmap confirms (`docs/SPEC.md:1079` area). `x: u8 := 250 + 10` passes a7; Zig panics in Debug / UB in ReleaseFast at runtime.
  Note (2026-09-16): for integer `+`, `-`, `*` the direction is superseded by ledger L5 (defined wrapping); other operations remain open under gate G3.
- Proof-carrying discipline for division/indexing/deref/casts (guards required, e.g. `if b == 0 { ret … }` before `a / b`, `if p == nil { ret }` after `new`) is the language design, exercised by `examples/004_func.a7`, `examples/011_memory.a7`. The *enforcement* is real (verified: unguarded `a / b` and unproven `arr[i]` are semantic errors). The unsoundness is only in loop contexts (H-1).
- `new [N]T` rejection (`type_checker.py:3005-3017`) matches AGENTS.md, although the Zig backend retains an `allocator.alloc` lowering for it (`zig.py:1909-1912`) — unreachable via the pipeline today.
- `isize` ranking between i32 and i64 in assignability (`types.py:120-126`) makes `i32 → isize` legal but `u64 → isize` illegal — deliberate width model; examples comply.

## 5. Verified-correct behaviors (positive coverage)

- **Error-stage classification**: exit codes 4/5/6/7/8 observed for tokenize/parse/semantic/codegen/internal respectively; JSON `schema_version 2.0` with `error.category`, per-stage `ok` flags, spans, and no `output_path` artifact on failure (matches `test_error_stage_matrix.py`, which drives the real CLI as a subprocess across 6 modes × 2 formats — no mocks anywhere in the suite).
- **Recursion rejection**: direct (`f → f`), mutual (`a → b → a`), shadowing-aware (`helper := 5` does not create a false edge), and label/alias machinery in the validator is careful (function-pointer aliases tracked conservatively).
- **Match diagnostics**: duplicate patterns, range overlap, wildcard-covered else, bool/enum exhaustiveness — all produce precise spans and messages.
- **Cast pipeline**: `cast(u8, x)` requires non-negative proof; guarded version passes; `@intCast/@floatCast/@intFromFloat` selection in the backend is consistent with the classifier decision; backend *re-verifies* approval (`_require_backend_approval`) so the pass/backend contract is enforced in both directions.
- **Use-after-delete** caught with a good message; `del` on non-reference rejected.
- **Tokenizer basics**: tabs rejected with advice; unterminated string/char reported at the opening quote with correct length; binary/octal/hex digit validation; scientific notation requires digits; BOM stripped; `/* */` nesting counted; unterminated block comment accepted-by-design (documented).
- **Formatter contract**: `{}` placeholder counting flags arity mismatches at semantic stage; brace escaping in `_convert_format_string` prevents format-string injection through user text; io calls in expression position are rejected at codegen with a span.
- **Parser recovery**: mid-file garbage produces a single accurate error (re-raise policy for first-declaration and incomplete-expression cases works as designed).

## 6. Test-suite audit (suppression / bypass)

- **No mocks** in `test/` (grep-verified); "no mocked stages" is even asserted in `test_pipeline_native.py:1`. Known-fail lists are empty (`SEMANTIC_KNOWN_FAIL = set()`, `ZIG_AST_CHECK_KNOWN_FAIL = set()` at `test_codegen_zig.py:33,167`), so no failures are being skipped away.
- Two `except ParseError: pass` blocks exist in `test_parser_error_handling_improvements.py:268,284` — they accept *any* parse error for `break`/`continue`-outside-loop sources; weak assertions but not suppression (semantic stage owns those diagnostics and tests them elsewhere).
- Semantic unit tests instantiate passes directly with hand-built symbol tables — legitimate unit scope, but it bypasses `compile.py`'s pass *ordering*; order-dependent behaviors (scope-matching via `_enter_matching_scope`, module combining, preprocessor-before-codegen) are only covered by the e2e/pipeline tests. That is where the current regressions live, which is the right place.
- The 15 red tests (RB-4) encode intended behavior; the failures are implementation-side, and **all are reproducible from the CLI** (no test-only artifacts).
- Environment-dependent tests: anything Zig-gated uses `has_zig()` on `PATH` (fine), but `test_release_tooling.py` shells out to `uv` through mise and fails in shim-less environments (recorded above); one Zig-using test (`test_slice_ptr_and_len_fields…`) lacks a `skipif(not ZIG_AVAILABLE)` guard and fails outright when Zig is absent.

## 7. Per-stage coverage matrix

Legend: **OK** verified good; **Partial** partially covered or defect found; **None** not covered by tests.

| Area | Tokenizer | Parser | NameRes | TypeCheck | Validator | Safety | Preproc | Codegen | Pipeline/Diag |
|---|---|---|---|---|---|---|---|---|---|
| Malformed input & EOF | OK | Partial: hang (RB-1), RecursionError (H-2), cap (H-3) | n/a | n/a | n/a | n/a | n/a | n/a | OK: stage matrix |
| Spans/columns | Partial: off-by-one ops (H-4) | Partial: inherits H-4 | OK | OK | OK | OK | OK | OK | Partial: imported files (H-8), spanless import err (M-2) |
| Precedence | n/a | OK: table matches SPEC order | n/a | n/a | n/a | n/a | n/a | Partial: mixed-width result (RB-5) | Partial |
| Scope resolution/shadowing | n/a | OK | OK | OK | OK | n/a | Partial: iterator renames (RB-5) | Partial: capture shadow/unused (RB-5) | Partial |
| Definite assignment | n/a | n/a | None: none exists | None | None | Partial: field exists, unused | n/a | Partial: zero-init masks (M-10) | None |
| Numeric semantics | Partial: unicode digits (H-10), limits (M-3) | OK | n/a | Partial: literal-fit gaps (H-6/7), overflow deferred | n/a | Partial: loop unsoundness (H-1), overflow disabled | Partial: folding precision (M-1) | Partial: inf literal (RB-5) | Partial |
| Recursion rejection | n/a | n/a | n/a | n/a | Partial: correct but exponential (RB-3) | n/a | n/a | n/a | OK |
| Generic specialization | n/a | OK | OK | OK: constraints/inference | n/a | n/a | OK | OK: comptime emission | OK: via examples |
| Mutation/usage analysis | n/a | n/a | n/a | n/a | n/a | n/a | OK | OK: var/const + discards | OK |
| Constant folding | n/a | n/a | n/a | Partial: pre-fold typing (H-7) | n/a | n/a | Partial: M-1 | OK | Partial |
| Error-stage/JSON | OK | OK | Partial | Partial: code reuse (M-4) | Partial | Partial | n/a | OK: codegen err w/ span | Partial: stdout pollution (H-3) |

## 8. Reviewed-file inventory

Fully read (line counts): `a7/compile.py` (892), `a7/tokens.py` (1018), `a7/errors.py` (963), `a7/parser.py` (2300), `a7/ast_nodes.py` (641), `a7/passes/name_resolution.py` (521), `a7/passes/type_checker.py` (3082), `a7/passes/semantic_validator.py` (1389), `a7/safety.py` (737), `a7/semantic_context.py` (411), `a7/types.py` (608), `a7/cast_classifier.py` (83), `a7/generics.py` (416), `a7/module_resolver.py` (369), `a7/symbol_table.py` (465), `a7/ast_preprocessor.py` (694), `a7/backends/zig.py` (2395), `a7/backends/base.py` (75), `a7/backends/__init__.py` (30), `a7/cli.py` (101), `a7/formatters/json_formatter.py` (234), `a7/stdlib/{__init__,io,math}.py` (172 total). Spot-read: `a7/formatters/console_formatter.py` (span rendering paths), `a7/stdlib/{mem,string}.py` (unregistered — noted dead), tests per §6, `scripts/error_stage_common.py`, selected `examples/`. Not reviewed: `site/`, `docs/RELEASE.md` process, wheel packaging beyond the two env-blocked tests, memory-runtime behavior (other reviewers).

**Coverage statement**: this is a full-source read plus targeted behavioral verification of every finding cited above; it is not exhaustive formal verification. Untested-runtime items are explicitly flagged (H-1 ReleaseFast UB is compile-verified only; nothing was executed).

## 9. Recommended completion roadmap (advisory)

1. **Stop-ship fixes (small, isolated)**: RB-1 match-statement else-raise; RB-2 output-path equality guard; H-3 warning→stderr + cap→error; M-1 `//`-based folding; M-6 keyword-escape at declaration sites; for-in capture `_`/rename handling (three failing native tests); H-5 while-true returns.
2. **Diagnostic-fidelity batch**: H-4 token columns (one-line fix per call site, wide span fallout — re-golden tests); M-2/M-4 import spans + dedicated error codes; H-8 per-node file attribution for imported modules + unify semantic/codegen module combining.
3. **Type-checker consistency**: H-6/H-7 literal-fit for returns/arguments + fold-before-check for literal-only expressions; RB-5 struct-literal validation (unknown/missing/positional fields, undefined struct names) and mixed-width arithmetic result typing (widen-or-require-cast).
4. **Safety-proof soundness (H-1)**: join/widen facts at loop headers or reject unproven loop indices; then re-enable the overflow obligation (`safety.py:636`) behind the same machinery. This is the item that protects the language's core claim.
   Note (2026-09-16): the overflow part is superseded for integer `+`, `-`, `*` by ledger L5 (defined wrapping); division, shifts and casts remain open under gate G3 in the [v1 plan](../../plan/README.md). The H-1 loop-fact repair is not superseded.
5. **Robustness**: RB-3 SCC-based cycle detection; H-2 nesting depth limit with clean diagnostic; H-10 ASCII digit gating; M-3 limit enforcement or removal; H-9 real circular-import detection.
6. **Hygiene**: delete or rewire M-9 dead code; decide nested-function fate (M-11) — either register them in name resolution end-to-end or reject at parse with a clear message; M-5 condition-context struct-literal suppression; M-7 terminator strictness decision (SPEC update either way).

— End of report. Advisory only; no source files were modified beyond the `glm-pipe-*` fixtures under `docs/audits/2026-09-14/repros/` and this report itself.
