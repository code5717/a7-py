# TODO

Current backlog for the A7 compiler, organized by priority tier.
Check test status with `PYTHONPATH=. uv run pytest --tb=no -q`. 36/36 examples pass e2e.

---

## Tier 1: Compiler Correctness (fix what's broken)

These are bugs and schema mismatches in already-implemented features.

- [x] Fix the `defer` AST schema mismatch in semantic analysis.
  Files: `src/passes/type_checker.py`, `src/passes/semantic_validator.py`
  Notes: fixed; deferred `statement` payloads are now traversed by type checking and semantic validation, with regression coverage.

- [x] Fix the `return` AST schema mismatch in semantic validation.
  Files: `src/passes/semantic_validator.py`
  Notes: fixed; semantic validation now traverses `value`, with a schema regression test.

- [x] Fail closed for `fall` until fallthrough lowering is designed.
  Files: `src/passes/semantic_validator.py`, `src/backends/zig.py`, `src/backends/c.py`
  Notes: `NodeKind.FALL` now produces a semantic error and both backends raise `CodegenError` if it reaches codegen. Full fallthrough lowering remains a future language-design item.

- [x] Replace Zig backend `@compileError("unsupported: ...")` fallbacks with compiler-side codegen errors.
  Files: `src/backends/zig.py`
  Notes: unsupported expression nodes now raise `CodegenError` during A7 compilation.

- [x] Stop C slice/iteration lowering from re-evaluating side-effectful expressions.
  Files: `src/backends/c.py`
  Notes: `for-in` and indexed `for-in` now cache array/slice iterable expressions in a generated local before loop length and element access.

- [x] Reject non-iterables in `for-in` and indexed `for-in` during type checking.
  Files: `src/passes/type_checker.py`
  Notes: fixed; array, slice, and string remain accepted iterables, while scalar iterables now produce a type diagnostic.

---

## Tier 2: Complete the Core Language

Features that are spec'd and partially implemented, or missing from one backend.

### Type System / Semantics

- [x] Add source-language support for `slice.ptr` / `slice.len`.
  Files: `src/passes/type_checker.py`, `src/backends/c.py`, `src/backends/zig.py`
  Notes: slice field access now type-checks `ptr` as `ptr T` and `len` as `usize`; C lowers `ptr` to the slice data field and `len` to the slice length field, while Zig uses native slice fields.

- [ ] Implement string slicing (`string[2..5]`).
  Files: `src/passes/type_checker.py`, `src/backends/c.py`, `src/backends/zig.py`
  Notes: array/slice sub-slicing works, string slicing does not.

- [ ] Implement generic constraint resolution beyond placeholder level.
  Files: `src/generics.py`
  Notes: `resolve_generic_constraint` is still a stub.

- [ ] Add match pattern overlap/redundancy diagnostics.
  Notes: no unreachable-branch detection for wildcard-first or fully-covered patterns.

### C Backend Parity

- [ ] C backend: `match` expressions.
  Files: `src/backends/c.py`
  Notes: `NodeKind.MATCH_EXPR` raises `CodegenError`; Zig backend handles it.

- [ ] C backend: range patterns and identifier-capture patterns.
  Files: `src/backends/c.py`
  Notes: front end parses and validates these, C lowering rejects them.

- [ ] C backend: function-typed declarations.
  Files: `src/backends/c.py`
  Notes: function pointer type emission is blocked.

### Module System / Stdlib

- [ ] Implement or de-scope `string` and `mem` stdlib modules.
  Files: `src/stdlib/string.py`, `src/stdlib/mem.py`, `src/stdlib/__init__.py`
  Notes: registry only wires `io` and `math`; `string` and `mem` are documented but stubbed.

- [x] Stop treating import/module loading as best-effort.
  Files: `src/compile.py`, `src/module_resolver.py`
  Notes: fixed for local file-based imports; missing or broken dependencies now fail as semantic errors while virtual stdlib imports remain supported.

- [ ] Unify built-in stdlib imports with file-based module resolution.
  Files: `src/module_resolver.py`, `src/passes/name_resolution.py`, `src/stdlib/__init__.py`
  Notes: decide whether `std/io` and `std/math` are virtual built-ins, on-disk modules, or both.

- [ ] Reconcile examples and docs with the actual stdlib surface.
  Files: `README.md`, `examples/030_calculator.a7`, `examples/001_hello.md`
  Notes: some examples use bare builtins, docs describe module-qualified usage.

### Unimplemented Spec Features

- [ ] Variadic functions (spec §6.5).
  Notes: spec'd but not parsed or implemented.

- [ ] Multiple return values / destructuring (`a, b, c := 1, 2, 3`).
  Notes: spec'd in §4.1, not parsed.

- [ ] Generic specialization (spec §7.4).
  Notes: spec'd but not implemented.

### Type Checking Improvements

- [ ] Infer concrete types through control flow (if/match narrowing).
  Notes: `x: i32 | nil` should narrow to `i32` inside `if x != nil { ... }`.

- [ ] Propagate generic type parameters through call chains.
  Notes: `Vec(i32).push(x)` should infer `x: i32` without annotation.

- [x] Validate return-type consistency across all branches.
  Notes: type checking visits returns inside blocks, if/else branches, and match branches; explicit regression coverage locks this down.

- [ ] Flag dead code after unconditional return/break/continue.
  Notes: reachability analysis is not implemented.

- [x] Check exhaustiveness of match statements.
  Notes: bool and enum match statements/expressions now require exhaustive coverage unless an else or wildcard branch is present. Pattern overlap/redundancy diagnostics remain separate work.

- [ ] Validate assignment compatibility beyond top-level type equality.
  Notes: nested struct/array type mismatches (e.g. `[4]i32` vs `[4]f32`) are not caught.

### Optimization Passes (high-leverage, low-complexity)

- [x] Constant folding: evaluate compile-time-known arithmetic, comparisons, and boolean logic.
  Notes: arithmetic, boolean logic, literal comparisons, and integer bitwise folds are covered. More advanced propagation remains separate work.

- [ ] Dead code elimination: drop unreachable statements after return/break/continue and unused local variables.
  Notes: reachability + `is_used` annotations already exist; just need a pass that prunes the AST.

- [ ] Constant propagation: substitute known-constant variables at use sites.
  Notes: `x := 5; y := x + 1` → `y := 6` (feeds into constant folding).

- [ ] Strength reduction: replace expensive ops with cheaper equivalents.
  Notes: `x * 2` → `x << 1`, `x / 4` → `x >> 2`, `x % 2` → `x & 1`. Only for integer types.

- [ ] Simple inlining: inline small leaf functions (single-expression body, no side effects).
  Notes: avoids call overhead for trivial helpers; keep a size threshold to avoid bloat.

- [ ] Loop-invariant code motion: hoist expressions that don't change across iterations.
  Notes: `for i := 0; i < len(arr); i += 1 { f(len(arr)) }` — hoist `len(arr)`.

---

## Tier 3: Big Bets (spec'd, not started)

These are entire subsystems. Each needs a design decision before implementation begins.

- [ ] **Array programming / tensors** (spec §9).
  Notes: tensors, broadcasting, vectorized ops, reshaping, reductions, linalg — ~300 lines of spec, nothing implemented. Requires either a runtime library, FFI to BLAS/LAPACK, or descoping from the spec.

- [ ] **AI-specific operations** (spec §9.6).
  Notes: conv2d, pooling, activations, batch norm, autograd. Essentially "build a DL framework in A7." Depends on tensor foundation.

- [ ] **GPU/accelerator support** (spec §9.9).
  Notes: `tensor_to_gpu`, device management. Requires a device runtime.

- [ ] **Memory/lifetime model** (spec §8.4).
  Notes: beyond basic `new`/`del` shape checks. Ownership, borrowing, lifetime analysis. Language-design research problem.

- [ ] **Performance annotations** (`@vectorize`, `@parallel`, `@prefetch`).
  Notes: requires SIMD/threading runtime support in both backends.

---

## Testing / Verification Gaps

- [x] Update `run_all_tests.sh` to include C backend tests, C example verifier, and error-stage matrix.
  Files: `run_all_tests.sh`, `test/test_codegen_c.py`, `test/test_examples_e2e_c.py`, `test/test_error_stage_matrix.py`
  Notes: also includes debug/release artifact verification and docs style checks.

- [x] Add semantic regression tests for front-end schema gaps.
  Files: `test/test_semantic_control_flow.py`, `test/test_semantic_comprehensive.py`
  Notes: added cases for deferred statement checking, return-payload traversal, and non-iterable `for-in`. Remaining feature gaps such as slice fields, string slicing, and `fall` still need implementation-specific coverage.

- [x] Add parser coverage for labeled `continue`, nested labeled loops, and malformed labels.
  Files: `test/test_parser_combinatorial.py`, `test/test_parser_integration.py`
  Notes: parser combinatorial tests now assert labeled `continue`, nested `for`/`while` labels, labeled `for-in` forms, and malformed non-loop labels.

- [x] Add Zig regression coverage for labeled `for-in` and indexed `for-in`.
  Files: `test/test_codegen_zig.py`
  Notes: added a compile/run regression for labeled `for-in`, labeled `continue`, and labeled indexed `for-in`; indexed loop variables use `usize`, matching array/slice lengths and Zig's native indexed loop value.

- [ ] Add example-level verification for labeled loops, sub-slicing, and match-case `defer` scope.
  Files: `examples/`, `test/fixtures/golden_outputs/`

- [x] Add report-contract tests for verification scripts (not just exit status).
  Files: `test/test_examples_e2e.py`, `test/test_examples_e2e_c.py`
  Notes: Zig and C example verifier tests now request JSON reports and assert totals plus per-example compile/syntax/build/run/output flags.

- [ ] Deduplicate Zig/C example verification scripts.
  Files: `scripts/verify_examples_e2e.py`, `scripts/verify_examples_e2e_c.py`

- [ ] Deduplicate error-stage audit logic between script and pytest matrix.
  Files: `scripts/verify_error_stages.py`, `test/test_error_stage_matrix.py`
  Notes: still duplicated, but both surfaces now include deferred semantic error coverage.

- [x] Run docs/style verification from `run_all_tests.sh`, not only in CI.
  Files: `run_all_tests.sh`, `scripts/check_docs_style.py`
  Notes: the docs style checker now includes `RELEASE.md`.

- [x] Add release/debug artifact verification script.
  Files: `scripts/build_examples.py`, `test/test_release_tooling.py`, `RELEASE.md`
  Notes: builds debug/release artifacts for Zig and C, executes binaries, and checks golden output.

- [x] Add CI coverage for release-oriented gates.
  Files: `.github/workflows/ci.yml`, `.github/workflows/deploy-docs.yml`, `site/package-lock.json`
  Notes: CI now installs Zig, runs pytest, dependency audits, error-stage checks, both backend E2E verifiers, debug/release artifact builds, package build, docs style, docs lint, and docs build. Pages deploy now uses `npm ci`.

- [x] Add dependency-audit checks for release readiness.
  Files: `.github/workflows/ci.yml`, `RELEASE.md`, `SECURITY.md`
  Notes: Python dependencies use `uvx pip-audit --strict`; docs runtime dependencies use `npm audit --omit=dev --audit-level=moderate`.

- [x] Add secret scanning to CI.
  Files: `.github/workflows/`
  Notes: `scripts/check_no_secrets.py` provides a lightweight committed-secret pattern scan in local and CI gates.

- [x] Add tag-based release artifact automation.
  Files: `.github/workflows/`
  Notes: `release.yml` creates a draft GitHub release for `v*` tags with Python package artifacts, docs site archive, and release example artifacts. It does not publish to PyPI.

- [ ] Add PyPI or package-registry publishing.
  Files: `.github/workflows/`
  Notes: GitHub release artifacts are automated; package registry target still needs a decision.

- [ ] Design and implement `fall` lowering.
  Files: `src/passes/semantic_validator.py`, `src/backends/zig.py`, `src/backends/c.py`, `docs/SPEC.md`
  Notes: current behavior is fail-closed; supporting fallthrough needs explicit semantics and backend lowering, especially for Zig.

---

## Parser / Tokenizer Debt

- [x] Implement tokenizer validation for invalid escape sequences.
  Files: `src/tokens.py`, `src/ast_nodes.py`, `src/backends/zig.py`
  Notes: string literals now reject unknown escapes and malformed `\xHH` escapes during tokenization, decode valid escapes into AST literal values, and re-emit escaped backend string literals.

- [ ] Clean up stale "not yet implemented" comments in parser tests.
  Files: `test/test_parser_missing_constructs.py`, `test/test_parser_advanced_edge_cases.py`, `test/test_parser_stress_tests.py`

- [ ] Lock down ambiguous parser behavior documented in problem tests.
  Files: `test/test_parser_comprehensive_problems.py`
  Notes: comments like "should either fail in parser or be handled specially" need decisions.

---

## Docs / Project State

- [x] Remove hard-coded status snapshots and brittle completeness numbers.
  Files: `README.md`, `MISSING_FEATURES.md`, `docs/SPEC.md`, `CHANGELOG.md`
  Notes: README and SPEC now point to live verification commands instead of stale pass counts.

- [x] Align status docs with actual remaining feature gaps.
  Files: `README.md`, `MISSING_FEATURES.md`, `docs/SPEC.md`, `plan.md`
  Notes: README, SPEC, site status/testing pages, and release docs now describe current backend/build gates and open caveats.

- [x] Fix broken documentation links and mark historical docs as archived.
  Files: `README.md`, `docs/SPEC.md`, `docs/archive/README.md`, `docs/ERROR_ANALYSIS.md`
  Notes: `docs/ERROR_ANALYSIS.md` is now labeled as historical, README describes it as non-current, and the archive index no longer points to removed generated artifacts.
