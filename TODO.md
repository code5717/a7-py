# TODO

Current backlog for the A7 compiler, organized by priority tier.
Check test status with `PYTHONPATH=. uv run pytest --tb=no -q`. 38/38 examples pass e2e.

---

## Tier 1: Compiler Correctness (fix what's broken)

These are bugs and schema mismatches in already-implemented features.

### Release / Workflow Hardening

- [x] Add Dependabot coverage for GitHub Actions, Python, and docs npm dependencies.
  Files: `.github/dependabot.yml`
  Notes: weekly update checks now cover workflow actions, root Python dependencies, and `site/` npm dependencies.

- [x] Pin non-`actions/*` workflow actions to immutable commits.
  Files: `.github/workflows/release.yml`, `.github/workflows/claude.yml`, `.github/workflows/claude-code-review.yml`
  Notes: `softprops/action-gh-release` and `anthropics/claude-code-action` are pinned to commit SHAs.

- [x] Pin first-party GitHub Actions to immutable commits.
  Files: `.github/workflows/*.yml`
  Notes: `actions/checkout`, `setup-python`, `setup-node`,
  `upload-artifact`, `download-artifact`, `attest`, Pages setup/upload/deploy
  actions are pinned to commit SHAs resolved from their current major tags on
  2026-05-08.

- [x] Harden automated Claude PR review against prompt injection from PR content.
  Files: `.github/workflows/claude-code-review.yml`
  Notes: the direct prompt now treats PR titles, bodies, comments, and diffs as untrusted content to review.

- [x] Add Python source static security scanning to CI/release.
  Files: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
  Notes: `uvx --from bandit==1.9.4 bandit -r a7 scripts main.py -q --skip B404,B603` now runs
  alongside dependency audits; controlled subprocess use is still manually
  reviewed because verifier/build scripts intentionally execute generated
  artifacts.

- [x] Pin CI/release Python audit tool versions.
  Files: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `RELEASE.md`, `SECURITY.md`
  Notes: `pip-audit` and `bandit` are invoked through exact `uvx --from package==version` specs.

- [x] Add concurrency to Claude automation workflows.
  Files: `.github/workflows/claude.yml`, `.github/workflows/claude-code-review.yml`
  Notes: newer Claude issue/PR runs cancel stale in-progress runs for the same
  target instead of racing duplicate automation.

- [x] Harden committed-secret filename detection and deduplicate noisy matches.
  Files: `scripts/check_no_secrets.py`, `test/test_release_tooling.py`
  Notes: `.env`/private-key-style filenames are flagged even when unreadable,
  and specific API-key matches suppress duplicate generic assignment findings
  on the same line.

- [x] Harden release manifest verification against unsafe paths.
  Files: `scripts/verify_release_manifest.py`, `test/test_release_tooling.py`
  Notes: downloaded manifest verification rejects parent-directory traversal and unsafe absolute paths while preserving flat asset downloads.

- [x] Contain file-backed module imports to configured search paths.
  Files: `a7/module_resolver.py`, `test/test_module_resolver.py`
  Notes: absolute and parent-directory traversal module paths now fail closed.

- [x] Expand installed-wheel smoke coverage.
  Files: `scripts/verify_wheel_install.py`
  Notes: clean-wheel verification now checks both installed Zig and C code generation.

- [x] Fix the `defer` AST schema mismatch in semantic analysis.
  Files: `a7/passes/type_checker.py`, `a7/passes/semantic_validator.py`
  Notes: fixed; deferred `statement` payloads are now traversed by type checking and semantic validation, with regression coverage.

- [x] Fix the `return` AST schema mismatch in semantic validation.
  Files: `a7/passes/semantic_validator.py`
  Notes: fixed; semantic validation now traverses `value`, with a schema regression test.

- [x] Fail closed for unsupported `fall` placements.
  Files: `a7/passes/semantic_validator.py`, `a7/backends/zig.py`, `a7/backends/c.py`
  Notes: valid `fall` lowering is implemented for non-final match cases; invalid
  placements still produce semantic errors and direct backend use outside a
  fall-capable match case raises `CodegenError`.

- [x] Replace Zig backend `@compileError("unsupported: ...")` fallbacks with compiler-side codegen errors.
  Files: `a7/backends/zig.py`
  Notes: unsupported expression nodes now raise `CodegenError` during A7 compilation.

- [x] Stop C slice/iteration lowering from re-evaluating side-effectful expressions.
  Files: `a7/backends/c.py`
  Notes: `for-in` and indexed `for-in` now cache array/slice iterable expressions in a generated local before loop length and element access.

- [x] Reject non-iterables in `for-in` and indexed `for-in` during type checking.
  Files: `a7/passes/type_checker.py`
  Notes: fixed; array, slice, and string remain accepted iterables, while scalar iterables now produce a type diagnostic.

---

## Tier 2: Complete the Core Language

Features that are spec'd and partially implemented, or missing from one backend.

### Type System / Semantics

- [x] Add source-language support for `slice.ptr` / `slice.len`.
  Files: `a7/passes/type_checker.py`, `a7/backends/c.py`, `a7/backends/zig.py`
  Notes: slice field access now type-checks `ptr` as `ptr T` and `len` as `usize`; C lowers `ptr` to the slice data field and `len` to the slice length field, while Zig uses native slice fields.

- [x] Implement string slicing (`string[2..5]`).
  Files: `a7/passes/type_checker.py`, `a7/backends/c.py`, `a7/backends/zig.py`
  Notes: string slicing now type-checks as `[]char`; Zig lowers to native byte slicing and C lowers to the existing slice struct representation, using `strlen` for open-ended slices.

- [x] Implement generic constraint resolution beyond placeholder level.
  Files: `a7/generics.py`
  Notes: predefined constraints, local `@type_set(...)` aliases, and inline `@type_set(...)` constraints now resolve; generic function declarations remain callable from the outer scope and inferred call arguments are checked against declared constraints.

- [x] Add exact match pattern redundancy diagnostics.
  Notes: duplicate bool, enum, and scalar literal patterns now emit unreachable-code diagnostics in match statements and expressions; wildcard-first and fully covered bool/enum cases also make later cases/else branches unreachable.

- [x] Add literal range match overlap diagnostics.
  Notes: overlapping numeric/char literal ranges, literals covered by previous ranges, and ranges containing previous literals now emit diagnostics.

- [x] Add constant/computed-constant range match overlap diagnostics.
  Notes: literal, constant identifier, and simple constant-expression numeric/char endpoints now participate in range overlap and covered-literal diagnostics.

- [ ] Add non-constant symbolic interval match overlap diagnostics.
  Notes: range overlap checks do not reason about runtime symbolic intervals.

- [ ] Define and implement true variable-binding match patterns.
  Files: `a7/passes/type_checker.py`, `a7/backends/zig.py`, `a7/backends/c.py`
  Notes: plain identifier patterns currently refer to existing symbols; binding/capture semantics are not implemented.

### C Backend Parity

- [x] C backend: side-effect-free `match` expressions.
  Files: `a7/backends/c.py`
  Notes: literal, enum, range, and wildcard patterns now lower to chained conditional expressions when the scrutinee is side-effect-free.

- [x] C backend: side-effectful `match` expression scrutinees in variable initializers.
  Files: `a7/backends/c.py`
  Notes: variable initializers now cache the scrutinee in a generated local before assigning the lowered conditional result.

- [x] C backend: side-effectful `match` expression scrutinees in non-declaration expression contexts.
  Files: `a7/backends/c.py`
  Notes: return values, assignments, variable initializer subexpressions, function arguments, and I/O arguments now lower through generated result temps and branch chains.

- [x] C backend: range patterns in match statements.
  Files: `a7/backends/c.py`
  Notes: match statements with range patterns now lower to portable `if` chains with a cached scrutinee.

- [x] C backend: existing-identifier match patterns.
  Files: `a7/backends/c.py`
  Notes: existing identifiers in match patterns now lower as comparisons in C match statements and expressions.

- [x] C backend: raw function-typed parameter and variable declarations.
  Files: `a7/backends/c.py`
  Notes: raw `fn(...)` parameter and variable declarations now emit C function-pointer declarators.

- [x] Function-type aliases in semantic analysis and C lowering.
  Files: `a7/passes/type_checker.py`, `a7/backends/c.py`
  Notes: aliases such as `BinaryOp :: fn(i32, i32) i32` now resolve to `FunctionType` in semantic analysis and lower as C typedefs.

### Module System / Stdlib

- [x] Implement or de-scope `string` and `mem` stdlib modules.
  Files: `a7/stdlib/string.py`, `a7/stdlib/mem.py`, `a7/stdlib/__init__.py`
  Notes: de-scoped from current release docs. SPEC now marks `std/string`, `std/mem`, and `std/collections` as planned, while current virtual stdlib support is limited to `io` and `math`.

- [x] Stop treating import/module loading as best-effort.
  Files: `a7/compile.py`, `a7/module_resolver.py`
  Notes: fixed for local file-based imports; missing or broken dependencies now fail as semantic errors while virtual stdlib imports remain supported.

- [x] Unify built-in stdlib imports with file-based module resolution.
  Files: `a7/module_resolver.py`, `a7/passes/name_resolution.py`, `a7/stdlib/__init__.py`
  Notes: `std/io`, `io`, `std/math`, and `math` are virtual built-ins registered through `ModuleResolver`/`ModuleTable`; backend lowering now uses the import path rather than requiring aliases named `io` or `math`.

- [x] Reconcile examples and docs with the actual stdlib surface.
  Files: `README.md`, `examples/030_calculator.a7`, `examples/001_hello.md`
  Notes: runnable examples now use the current module-qualified stdlib surface;
  regenerated reports render virtual modules as `module` and doc-mode output as
  in-memory rather than `unknown type` / `None`.

### Unimplemented Spec Features

- [ ] Variadic functions (spec §6.5).
  Notes: spec'd but not parsed or implemented.

- [ ] Multiple return values / destructuring (`a, b, c := 1, 2, 3`).
  Notes: spec'd in §4.1, not parsed.

- [ ] Complete generic specialization (spec §7.4).
  Notes: simple top-level generic function calls now lower in the C backend; generic structs and deeper call-chain propagation still need full runtime coverage.

### Type Checking Improvements

- [ ] Infer concrete types through control flow (if/match narrowing).
  Notes: `x: i32 | nil` should narrow to `i32` inside `if x != nil { ... }`.

- [ ] Propagate generic type parameters through call chains.
  Notes: `Vec(i32).push(x)` should infer `x: i32` without annotation.

- [ ] Complete C backend generic lowering.
  Files: `a7/passes/generic_lowering.py`, `a7/backends/c.py`, `a7/generics.py`, `examples/014_generics.a7`
  Notes: simple top-level generic functions are monomorphized before C codegen; remaining work includes generic structs, nested/composite specializations, and propagation through call chains.

- [x] Complete untagged runtime union construction and field access.
  Files: `a7/passes/type_checker.py`, `a7/backends/zig.py`, `a7/backends/c.py`, `examples/016_unions.a7`
  Notes: `Type{field: value}` literals now require exactly one named field and field access resolves declared union fields in both backends.

- [ ] Design and implement tagged union tag workflows.
  Files: `a7/parser.py`, `a7/passes/type_checker.py`, `a7/backends/zig.py`, `a7/backends/c.py`, `docs/SPEC.md`
  Notes: `union(tag)` is reserved in the specification, but tag inspection and discriminated-state-safe workflows are not implemented yet.

- [x] Validate return-type consistency across all branches.
  Notes: type checking visits returns inside blocks, if/else branches, and match branches; explicit regression coverage locks this down.

- [x] Flag dead code after unconditional return/break/continue.
  Notes: semantic validation now rejects block-local statements after `ret`, valid `break`/`continue`, `fall`, and fully-terminating `if`/`match` statements.

- [x] Reject direct, mutual, and local function-pointer alias recursion during semantic validation.
  Notes: A7 source must use loops, explicit stacks, or index-based worklists for repeated work; local aliases like `again := current_fn` are treated conservatively.

- [x] Require `usize` for index and slice-bound variables.
  Files: `a7/passes/type_checker.py`, examples using indexed array loops
  Notes: non-negative integer literals remain accepted for simple indexing; signed variables and negative literals are rejected.

- [x] Fail closed for heap fixed arrays until the representation is designed.
  Files: `a7/passes/type_checker.py`, `docs/SPEC.md`
  Notes: `new [N]T` is rejected instead of lowering inconsistently across Zig and C.

- [x] Tighten comparison and integer-assignment type safety.
  Files: `a7/types.py`, `a7/passes/type_checker.py`
  Notes: invalid ordering comparisons are rejected and signed variables no longer implicitly assign to unsigned integer types.

- [x] Check exhaustiveness of match statements.
  Notes: bool and enum match statements/expressions now require exhaustive coverage unless an else or wildcard branch is present. Exact duplicate patterns and unreachable branches after wildcard or full bool/enum coverage are diagnosed separately.

- [x] Validate assignment compatibility beyond top-level type equality.
  Notes: array literal assignment now validates every element against the
  declared array type, including nested array literals, and reports explicit
  size mismatches.

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
  Notes: added cases for deferred statement checking, return-payload traversal,
  non-iterable `for-in`, slice fields, string slicing, and invalid `fall`
  placement.

- [x] Add parser coverage for labeled `continue`, nested labeled loops, and malformed labels.
  Files: `test/test_parser_combinatorial.py`, `test/test_parser_integration.py`
  Notes: parser combinatorial tests now assert `@label` loop prefixes, labeled `continue`, nested `for`/`while` labels, labeled `for-in` forms, and malformed or old `label:` labels.

- [x] Add Zig regression coverage for labeled `for-in` and indexed `for-in`.
  Files: `test/test_codegen_zig.py`
  Notes: added a compile/run regression for labeled `for-in`, labeled `continue`, and labeled indexed `for-in`; indexed loop variables use `usize`, matching array/slice lengths and Zig's native indexed loop value.

- [x] Add example-level verification for labeled loops, sub-slicing, and match-case `defer` scope.
  Files: `examples/`, `test/fixtures/golden_outputs/`
  Notes: `036_control_flow_edges.a7` now verifies labeled break/continue, array sub-slicing, and match-case defer scope through Zig and C golden-output checks.

- [x] Add report-contract tests for verification scripts (not just exit status).
  Files: `test/test_examples_e2e.py`, `test/test_examples_e2e_c.py`
  Notes: Zig and C example verifier tests now request JSON reports and assert totals plus per-example compile/syntax/build/run/output flags.

- [x] Deduplicate Zig/C example verification scripts.
  Files: `scripts/verify_examples_common.py`, `scripts/verify_examples_e2e.py`, `scripts/verify_examples_e2e_c.py`
  Notes: shared compile/build/run/output-report logic now lives in `verify_examples_common.py`; the Zig and C entrypoints remain as compatible thin backend configurations.

- [x] Deduplicate error-stage audit logic between script and pytest matrix.
  Files: `scripts/error_stage_common.py`, `scripts/verify_error_stages.py`, `test/test_error_stage_matrix.py`
  Notes: shared mode sets, source fixtures, CLI runner, JSON helpers, and 61-check audit construction now live in `error_stage_common.py`; pytest keeps additional payload-specific assertions on top.

- [x] Run docs/style verification from `run_all_tests.sh`, not only in CI.
  Files: `run_all_tests.sh`, `scripts/check_docs_style.py`
  Notes: the docs style checker now includes `RELEASE.md`.

- [x] Add release/debug artifact verification script.
  Files: `scripts/build_examples.py`, `test/test_release_tooling.py`, `RELEASE.md`
  Notes: builds debug/release artifacts for Zig and C, executes binaries, and checks golden output.

- [x] Add CI coverage for release-oriented gates.
  Files: `.github/workflows/ci.yml`, `.github/workflows/deploy-docs.yml`, `site/package-lock.json`
  Notes: CI now installs Zig, runs pytest, dependency audits, error-stage checks, both backend E2E verifiers, selected backend parity checks, debug/release artifact builds, package build, docs style, docs lint, and docs build. Pages deploy now uses `npm ci`.

- [x] Add dependency-audit checks for release readiness.
  Files: `.github/workflows/ci.yml`, `RELEASE.md`, `SECURITY.md`
  Notes: Python dependencies use `uvx --from pip-audit==2.10.0 pip-audit --strict`; docs runtime dependencies use `npm audit --omit=dev --audit-level=moderate`.

- [x] Add secret scanning to CI.
  Files: `.github/workflows/`
  Notes: `scripts/check_no_secrets.py` provides a lightweight committed-secret
  pattern and sensitive-filename scan in local and CI gates.

- [x] Add tag-based release artifact automation.
  Files: `.github/workflows/`
  Notes: `release.yml` creates a draft GitHub release for `v*` tags with Python package artifacts, docs site archive, and release example artifacts. Manual dispatch validates the release gate and artifact build without creating a release. Release permissions are split so only the tag-only draft release job gets `contents: write`.

- [x] Smoke-test the built wheel as the shipped artifact.
  Files: `scripts/verify_wheel_install.py`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `pyproject.toml`
  Notes: the Python package now installs as top-level package `a7`, and CI/release install the built wheel into a clean virtual environment before upload.

- [ ] Decide whether to add package-registry publishing.
  Files: `.github/workflows/`
  Notes: the current release workflow builds Python distributions and attaches them to draft GitHub releases, but does not publish to a package registry.

- [x] Design and implement `fall` lowering.
  Files: `a7/passes/semantic_validator.py`, `a7/backends/zig.py`, `a7/backends/c.py`, `docs/SPEC.md`
  Notes: `fall` now lowers in both native backends when used as the final direct
  statement of a non-final match case; invalid placements remain semantic
  errors.

---

## Parser / Tokenizer Debt

- [x] Implement tokenizer validation for invalid escape sequences.
  Files: `a7/tokens.py`, `a7/ast_nodes.py`, `a7/backends/zig.py`
  Notes: string literals now reject unknown escapes and malformed `\xHH` escapes during tokenization, decode valid escapes into AST literal values, and re-emit escaped backend string literals.

- [x] Clean up stale "not yet implemented" comments in parser tests.
  Files: `test/test_parser_missing_constructs.py`, `test/test_parser_advanced_edge_cases.py`, `test/test_parser_stress_tests.py`
  Notes: parser regression tests now describe current behavior instead of carrying stale skip comments for implemented constructs.

- [x] Lock down ambiguous parser behavior documented in problem tests.
  Files: `test/test_parser_comprehensive_problems.py`
  Notes: `new i32(42)` now fails in the parser instead of being accepted as a
  call on a `new` expression; `new(i32)` remains valid allocation syntax.

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
