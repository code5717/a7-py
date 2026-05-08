# Changelog

All notable changes to the A7 compiler will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Semantic recursion validation now catches higher-order callback trampolines,
  including direct, mutual, and callback-parameter-alias cycles.
- Zig and C backend binary-expression emission now uses explicit postorder
  stacks, avoiding Python recursion failures on deeply nested binary ASTs.
- Normal example verifier runs now fail closed when a golden output fixture is
  missing; only explicit `--update-golden` runs write fixture files.
- Documentation now scopes the low-recursion implementation claim to the
  compiler stages that are actually stack-based today and tracks fully
  iterative backend emission as follow-up work.
- JSON AST serialization now uses an explicit traversal stack so machine-readable
  AST output follows the same low-recursion implementation contract as the rest
  of the compiler pipeline.
- Examples now align more tightly with their catalog descriptions: callbacks
  use function-pointer dispatch, sorting uses a comparator callback, and the
  comments example emits visible golden output.
- File-backed local imports now fail closed before backend codegen, and docs
  now distinguish resolver validation from unsupported multi-file linking.
- JSON diagnostics now serialize selected import item lists without tracebacking,
  and language docs now mark selected/using imports and method-call sugar as
  non-runnable current syntax where appropriate.
- Variadic parameters now fail closed before backend codegen instead of
  emitting invalid target-language function signatures.
- Calculator example output now rounds display-only approximation values so
  the golden output stays readable across Zig and C backends.
- Tightened runnable examples so conditionals, callbacks, and state-machine
  demos exercise their documented branches in both native backends.
- `examples/014_generics.a7` now runs real generic functions and generic struct
  instances in both backends; backend parity coverage now also includes type-set
  generic constraints, explicit enum discriminants, stdlib math mappings, and
  edge operator assignments/comparisons.
- README, SPEC, site, and public Markdown docs now distinguish current features
  from parsed-only or reserved syntax such as variadics, non-`@type_set`
  intrinsics, and multiple declaration/destructuring syntax.
- Generic struct literals now retain concrete instance types during semantic
  analysis, Zig emits generic struct instances with explicit type arguments,
  and the C backend monomorphizes used generic struct instances before codegen.
- Formatter symbol collection now surfaces traversal failures instead of
  silently swallowing broad exceptions, reducing hidden documentation/reporting
  failures found during static security review.
- Manual release workflow dispatch now validates gates and artifacts without
  creating a GitHub release; draft release creation remains limited to `v*`
  tags.
- Release workflow permissions are split so the gate/artifact build job runs
  with read-only repository contents access; only the tag-only draft release job
  receives `contents: write`.
- Removed package-registry publishing from the release workflow; tag releases
  now build package artifacts and attach them to draft GitHub releases only.
- CI and release workflows now use concurrency groups; release tags re-verify
  downloaded checksums before draft release creation, and local package output
  is cleaned before workflow package builds.
- Claude-triggered workflows now restrict secret-backed runs to repository
  owners, members, or collaborators; automated Claude PR review skips fork PRs.
- Dependabot now covers GitHub Actions, Python, and docs npm dependencies;
  non-`actions/*` workflow actions are pinned to immutable commits, and the
  automated Claude review prompt now treats PR text/diffs as untrusted review
  input rather than instructions.
- First-party `actions/*` workflow actions are pinned to immutable commit SHAs
  resolved from their current major tags.
- Release-readiness and security docs now cite the latest CI, Deploy Docs, and
  manual release workflow evidence after workflow action pinning and Bandit
  scanning were added.
- CI/release Python audit tools are pinned to exact `uvx --from package==version`
  invocations so release gates do not fetch arbitrary latest tool releases.
- Claude-triggered workflows now use per-issue/PR concurrency groups so newer
  prompts cancel stale in-progress automation runs.
- The committed-secret guard now flags sensitive `.env`/key filenames even when
  file contents are binary or unreadable, and deduplicates specific API-key
  findings against generic assignment matches.
- `fall` now lowers in both Zig and C backends for its documented narrow form:
  the final direct statement of a non-final match case. Invalid placements are
  semantic errors.
- Match range diagnostics now catch conservative runtime-symbolic interval
  overlaps when two inclusive ranges share an endpoint symbol, such as
  `low..high` followed by `high..top`.
- Match identifier capture patterns now bind the scrutinee in branch-local
  scope when no existing symbol with that name is visible. Existing identifier
  patterns still compare against the existing symbol.
- Release-manifest verification rejects parent-directory traversal and unsafe
  absolute paths, while preserving the documented flat downloaded-assets flow.
- File-backed module imports are now contained to configured search paths and
  reject absolute or parent-directory traversal module paths.
- Example artifact compilation now has a timeout, and installed-wheel smoke
  verification checks both Zig and C code generation.
- Tag release runs now generate GitHub artifact attestations for the checksum
  manifest, Python package files, docs archive, and native example artifact
  archive before uploading release artifacts.
- Release manifest verification now supports the flat layout created by
  downloading release assets into one directory beside `SHA256SUMS`, matching
  the documented pre-publish verification flow.
- The Python distribution now installs a project-specific `a7` package instead
  of a generic top-level `src` package, and CI/release jobs smoke-test the built
  wheel in a clean virtual environment before upload.
- Native example release archives are explicitly named for their current
  `linux-x86_64` / Zig 0.15.2 artifact contract.
- Semantic validation now rejects direct, mutual, local function-pointer alias,
  and higher-order callback trampoline recursion; source programs should use
  loops, explicit stacks, or index-based worklists instead.
- Index and slice-bound variables now require `usize`; non-negative integer
  literals remain valid for simple indexing, while signed index variables and
  negative literals are rejected.
- `new [N]T` heap fixed arrays now fail closed until the language and both
  backends define one representation; use stack arrays or slices for now.
- Type checking now rejects invalid ordering comparisons on non-ordered types
  and blocks implicit signed-to-unsigned integer assignment except for fitting
  integer literals.
- Expanded incomplete runnable examples for function pointers, inline struct
  returns, linked-list traversal, iterative binary-tree traversal, and string
  utilities; tightened example catalog copy where language support is still
  status-only.
- Added a selected Zig/C backend parity verifier that compiles, builds, runs,
  and compares non-example smoke programs across both native backends.
- Expanded the parity verifier to cover match statements, match expressions,
  slice fields, indexed slice iteration, and string slice iteration.
- Added curl.md-friendly public Markdown docs and an `llms.txt` entry point
  for agent and terminal documentation workflows.
- Added `COMPLETION_AUDIT.md` to map the release-readiness objective to
  concrete verification evidence, residual risks, and incomplete requirements.
- Documented clean local package builds by removing `dist/` before `uv build`
  so stale versioned artifacts do not contaminate manual release prep.
- Added release artifact checksum manifest generation and wired `SHA256SUMS`
  into tag-created draft GitHub releases.
- Release checksum generation now fails closed if expected package, docs, or
  native artifact archive paths are absent from `SHA256SUMS`.
- Added release manifest verification so CI and maintainers can re-check
  recorded artifact hashes and sizes before upload.
- Expanded curl.md-friendly docs with a full-context aggregate, route aliases,
  first-class page metadata, and visible Markdown links from the docs app.
- Added release archive content verification so docs/native artifact tarballs
  must contain required curl.md entry points and example outputs before upload.
- Reworked the public docs map around curl.md-friendly Introduction, Guide,
  Plugins, LLM Resources, and Contributing groups, including static Markdown
  pages for API/SDK, agent plugins, skills, deploy, and kitchen-sink coverage.
- C backend codegen now monomorphizes simple top-level generic function calls
  before emission, so concrete calls such as `identity(7)` lower to specialized
  C functions instead of failing on unresolved `$T` type parameters.
- Built-in stdlib imports now register virtual module symbols through the
  module resolver and resolve backend lowering from the imported module path,
  so aliases such as `console :: import "std/io"` and
  `mathlib :: import "std/math"` work consistently and unknown stdlib
  functions fail during semantic analysis.
- The docs app now has a first-class `/docs` curl.md directory and canonical
  Markdown paths for `/docs/install.md` and `/docs/guide/*`, while keeping the
  previous flat public docs files available as compatibility aliases.
- Untagged union literals now require exactly one named field, union field
  access type-checks declared fields, and `examples/016_unions.a7` now runs
  through both Zig and C example verifiers.
- Markdown compilation reports now render virtual stdlib modules as `module`
  instead of `unknown type`, use an explicit in-memory output label in doc mode,
  and the examples catalog now describes the current union example accurately.
- Array literal assignment checks now validate every element against the
  declared array type, including nested arrays, and report explicit size
  mismatches instead of relying on top-level array type equality.
- C backend fixed nested fixed-array declarations such as `[2][2]i64`, and
  backend parity now covers contextual array literal assignment.
- C backend for-in lowering now handles nested fixed-array iteration with
  pointer-to-array cache declarations, and backend parity now covers defer
  unwind order, untagged unions, generic function specialization, enum match
  expressions, heap struct allocation, and 2D/3D nested fixed arrays.
- C backend return lowering now evaluates return values before running deferred
  cleanup, preventing deferred `del` from freeing data before the returned value
  is captured.
- C backend regression tests and backend parity builds now treat incompatible
  pointer-type warnings as errors.
- Removed a duplicated block from `docs/SPEC.md`, fixed section numbering, and
  refreshed the specification snapshot date.
- Parser now rejects initializer-like calls after `new` expressions, so
  `new i32(42)` fails as syntax instead of parsing as a nonsensical call.
- The docs app now exposes copyable curl.md fetch commands, includes A7
  reference pages in the `/docs` directory, advertises `llms.txt` and
  `llms-full.txt` as alternate resources, and tightens docs and examples card
  layout to prevent long file names or labels from colliding.
- Rebalanced the public docs site back toward A7 language content: the primary
  navigation now highlights Start, Language, Examples, Compiler, and Status;
  the homepage no longer frames curl.md/agent docs as the product; and the
  language reference now shows current `@label` loop syntax.
- Added `examples/037_language_tour.a7`, a commented compact one-file language
  tour, and updated docs/site example counts to 38 verified programs.
- Zig and C example verification now share one verifier implementation while
  keeping the existing `verify_examples_e2e.py` and
  `verify_examples_e2e_c.py` command entry points and JSON report contracts.
- Error-stage auditing now shares its mode matrix, generated source fixtures,
  CLI runner, JSON helpers, and 61-check audit construction between the
  standalone verifier and pytest matrix.

## [0.3.0] - 2026-05-07

### Added
- **Release and debug build readiness**
  - Added an installed `a7` CLI entrypoint via `pyproject.toml`.
  - Added `scripts/build_examples.py` to build debug/release native artifacts for Zig and C example outputs and verify each binary against golden fixtures.
  - Added `RELEASE.md` with local release gates, artifact layout, tagging steps, and security caveats.
  - Added `SECURITY.md` and `RELEASE_READINESS_REVIEW.md` to document trust boundaries, residual release risks, and verification evidence.
  - Added release-tooling pytest coverage for the installed CLI and debug build script.
  - Added a GitHub Actions CI workflow for Python, backend, package, docs, dependency audit, and artifact checks.
  - Added `scripts/check_no_secrets.py` and wired it into the local gate and CI as a committed-secret guard.
  - Added a tag-triggered draft GitHub release workflow for Python package artifacts, docs site archive, and release example artifacts.
  - Added tag-triggered draft GitHub releases with Python package artifacts,
    docs archives, and native example artifacts.

- **Compiler handling and test coverage expansion**
  - Added semantic regression coverage for deferred statement payloads, return payload traversal, and non-iterable `for-in` diagnostics.
  - Expanded AST preprocessor tests for constant folding of numeric comparisons, literal equality, and integer bitwise operators.
  - Expanded `scripts/verify_error_stages.py` and `test/test_error_stage_matrix.py` so deferred semantic errors are checked across all semantic-capable modes and human/JSON output.

- **Labeled Loops** (both backends)
  - `@outer while`, `@outer for`, `@outer for-in` with `break outer` / `continue outer`.
  - The old `outer: for` spelling is rejected so `name:` remains reserved for typed bindings, fields, and case-like syntax.
  - Zig backend emits native labeled loops; C backend lowers to goto-based control flow.

- **Slice Expressions in C Backend**
  - `arr[1..4]` on arrays and slices now emits compound-literal slice structs.
  - Indexing and `for-in` iteration over slice values supported.
  - `string[start..end]` and `string[start..]` now type-check as `[]char` and run on both Zig and C backends.
  - C backend `for-in` iteration now supports direct `string` values instead of only array and slice values.

- **C Backend Match Expressions**
  - Side-effect-free `match` expressions now lower to C conditional expressions for literal, enum, range, and wildcard patterns.
  - Match statements with literal range patterns now lower to portable C `if` chains with a cached scrutinee.
  - Existing-identifier match patterns now lower to C comparisons in both match statements and match expressions.
  - Variable initializers using side-effectful `match` scrutinees now cache the scrutinee in a generated local before evaluating patterns.
  - Side-effectful `match` scrutinees in return values, assignments, variable initializer subexpressions, function arguments, and I/O arguments now lower through generated result temps and branch chains.

- **C Backend Function Pointers**
  - Raw `fn(...)` parameter and variable declarations now emit C function-pointer declarators.
  - Function-type aliases such as `BinaryOp :: fn(i32, i32) i32` now resolve in semantic analysis and lower to C typedefs.

- **Type Checker: Slice and Index Validation**
  - `visit_slice_expr`: validates source is array/slice/string, checks start/end are integral, returns `SliceType`.
  - `visit_index_expr`: now rejects non-integer index expressions.

- **Unreachable code validation**
  - Semantic validation now rejects block-local statements after `ret`, valid `break`/`continue`, `fall`, and fully-terminating `if`/`match` statements.
  - Added control-flow regression coverage for reachable and unreachable branch combinations.

- **Match Diagnostics**
  - Duplicate bool, enum, and scalar literal patterns now emit unreachable-code diagnostics in match statements and expressions.
  - Wildcard-first and fully covered bool/enum match cases now make later case patterns and else branches unreachable.
  - Literal numeric/char range overlaps, literals covered by previous ranges, and ranges containing previous literals now emit diagnostics.
  - Compile-time constant numeric/char range endpoints now participate in range-overlap and covered-literal diagnostics.

- **Generic Constraints**
  - Generic function declarations such as `process($T: IntOnly) :: fn(value: $T) $T` are now registered in the outer scope and callable by name.
  - Declared generic constraints now resolve predefined sets, local `@type_set(...)` aliases, and inline `@type_set(...)` constraints.
  - Inferred generic call arguments now emit constraint-violation diagnostics when they do not satisfy the declared type set.

### Changed
- **Integer guidance and examples**
  - Updated the Fibonacci/frontpage example to use `usize` for count/index values and `u64` for the computed sequence value.
  - Documented integer type selection: `usize` for memory sizes and indices, `isize` only for signed pointer-adjacent offsets, and fixed-width integers for explicit data-width semantics.

- **Release documentation and verification gates**
  - Updated README, SPEC, site testing/status/CLI docs, and site README to describe the installed CLI, package build, C verifier, and debug/release artifact workflow.
  - Expanded `run_all_tests.sh` to include C backend tests, C example verification, debug/release artifact verification, error-stage verification, docs style checks, and full pytest.
  - Extended docs style checking to include `RELEASE.md`.
  - Made the docs deploy workflow use the committed `site/package-lock.json` with `npm ci`.
  - Switched the docs syntax highlighter from the Oniguruma WASM engine to Shiki's JavaScript regex engine, removing the docs build chunk-size warning.
  - Upgraded first-party GitHub workflow actions to Node 24-compatible majors and opted workflows into Node 24 JavaScript action execution.
  - Upgraded GitHub Pages, artifact, and release workflow actions to Node 24-compatible majors.
  - Replaced the third-party Zig setup action with a checksum-verified Zig 0.15.2 install step in CI and release workflows.
  - Corrected release/security checklist shell snippets and the README documentation-site URL.
  - Updated the release-readiness review with hosted CI/Pages evidence, a repeatable latest-run check, and the remaining upstream Pages action warning.
  - Release docs now describe draft GitHub release artifacts without package-registry publishing.
  - Corrected memory-safety documentation so the spec no longer claims unimplemented lifetime, double-free, use-after-free, or bounds-check guarantees.
  - Marked the tensor/AI/GPU section as planned design work instead of current language support.
  - De-scoped `std/string`, `std/mem`, and `std/collections` from current stdlib documentation; only virtual `io` and `math` modules are documented as implemented.
  - Updated generic constraint spec notes to describe the implemented `$T: Constraint` syntax instead of stale planned-only wording.

- **Import handling**
  - Local file-based imports now load dependencies during semantic analysis and fail closed on missing or broken modules.
  - Built-in stdlib imports such as `std/io` and `std/math` remain virtual so existing examples do not require on-disk stdlib `.a7` files.

- **Zig backend diagnostics**
  - Unsupported expression nodes now raise compiler-side `CodegenError` instead of emitting Zig `@compileError` fallback expressions.

- **Fallthrough handling**
  - `fall` initially failed closed with a semantic diagnostic, and both backends raised codegen errors if a `FALL` node reached them.
  - Later release-readiness work added the documented narrow lowering path for final direct `fall` statements in non-final match cases.

- **C backend iteration**
  - `for-in` and indexed `for-in` now cache array/slice iterable expressions before loop lowering so side-effectful iterables are evaluated once.

- **Tokenizer diagnostics**
  - String literals now reject unknown escape sequences and malformed `\xHH` escapes during tokenization.
  - Valid string escapes are decoded in AST literals and re-escaped for backend output, so runtime output matches source escape semantics.

- **Semantic coverage accounting**
  - Added explicit regression tests for return type mismatches inside if branches, match branches, and nested blocks.
  - Updated the tracked backlog to reflect existing bool/enum match exhaustiveness diagnostics.
  - Indexed `for-in` loop variables now type-check as `usize`, matching slice lengths, array indices, and backend-native indexed iteration.
  - Added parser coverage for labeled `continue`, nested labeled loops, labeled `for-in` forms, and malformed non-loop labels.
  - Example E2E tests now assert verifier JSON report contracts instead of only checking process exit status.
  - Added `036_control_flow_edges.a7` to verify labeled loops, array sub-slicing, and match-case `defer` scope through golden-output E2E checks.
  - Cleaned stale parser-test comments that still described implemented constructs as missing or unsupported.

- **Documentation state**
  - Marked the old error-analysis report as historical and corrected the archive index so it no longer points at removed generated artifacts.

- **Slice fields**
  - Added source-language support for `slice.ptr` and `slice.len` in type checking and both backends.
  - Added `isize` and `usize` to primitive type resolution so slice lengths can use the documented `usize` type.

- **Semantic and preprocessing correctness**
  - `defer` now traverses its parsed `statement` payload in both type checking and semantic validation.
  - `ret` semantic validation now traverses the parser's `value` payload.
  - `for-in` and indexed `for-in` now reject non-array, non-slice, non-string iterables during type checking.
  - Semantic diagnostics now include concrete messages/advice for deferred delete/reference failures and related scope/immutability cases.
  - Constant folding now covers comparisons and integer bitwise operators in addition to arithmetic and boolean logic.

- **Documentation Site Redesign**
  - Reworked the React/Vite docs frontend under `site/` into a cleaner editorial layout with a warm monochrome token system, flatter panels, and a top-led navigation shell.
  - Rebuilt the home page around an image-led docs landing composition with a framed code hero, quick-start strip, feature bento, pipeline overview, and structured footer.
  - Normalized shared docs primitives (`PageHeader`, `SectionPanel`, `MetricTile`, code/table/callout styling) so content pages inherit the same minimalist visual system.
  - Added light, dark, and system theme support with a header theme toggle and detection for extension-driven dark mode so site styling does not stack awkwardly with tools like Dark Reader.
  - Revised the dark theme into a quieter terminal-brutalist direction, replaced remote placeholder imagery with a local generated hero asset, made the header search control functional, reduced marketing copy, and removed fake testimonial content.
  - Tightened example-card wrapping, search dialog semantics, shared scroll locking, and responsive home-section padding so compact layouts do not collide with panel borders.
  - Added a documentation 404 route and social preview metadata for a cleaner fallback and share surface.

- **Semantic Coverage Expansion**
  - Unskipped 9 previously skipped semantic tests across `test/test_semantic_generics.py` and `test/test_semantic_control_flow.py`.
  - Converted deferred coverage into active failing tests to track implementation work directly in CI.

- **Error Stage Verifier**
  - Added `scripts/verify_error_stages.py` to audit tokenizer/parse/semantic/codegen/I-O/usage errors across all CLI modes and both human/JSON formats.
  - Added `test/test_error_stage_matrix.py` (53 checks) for stage-by-stage error contract coverage.

- **Examples End-to-End Verifier**
  - Added `scripts/verify_examples_e2e.py` to enforce compile → `zig ast-check` → `zig build-exe` → runtime output verification.
  - Added golden fixtures for all examples in `test/fixtures/golden_outputs/*.out`.
  - Added `test/test_examples_e2e.py` pytest gate for output-level regression checks.

- **CLI V2: MODE + FORMAT CONTRACT**
  - Added `--mode {compile,tokens,ast,semantic,pipeline,doc}`.
  - Added `--format {human,json}` with schema versioned JSON output (`schema_version: "2.0"`).
  - Added stable exit codes by failure class:
    - `2` usage, `3` I/O, `4` tokenize, `5` parse, `6` semantic, `7` codegen, `8` internal.
  - Added `--doc-out PATH` for markdown reports (pass `auto` for `<file>.md`), including compile+doc in one run.

- **STANDARD LIBRARY REGISTRY** (`a7/stdlib/`)
  - `StdlibRegistry` with `resolve_call()`, `resolve_builtin()`, `get_backend_mapping()`
  - Module definitions: `io` (println, print, eprintln), `math` (sqrt, abs, floor, ceil, sin, cos, etc.)
  - Backend-specific mappings (e.g., `sqrt` → `@sqrt` for Zig)
  - Typed builtin variants: `sqrt_f32`, `abs_f64`, etc.

- **AST NODE ANNOTATIONS** (`a7/ast_nodes.py`)
  - `is_mutable`, `is_used`, `emit_name`, `resolved_type`, `hoisted`, `stdlib_canonical`
  - Populated by preprocessor, read by backends

### Changed
- **Language Documentation Completion (Site)**
  - Expanded `site/src/pages/Language.tsx` into a full reference covering lexical rules, literals, declarations, expressions, control flow, functions, memory, generics, modules, intrinsics, operators, and grammar quick-reference.
  - Added explicit implementation-state callouts linking language docs to current semantic gaps tracked in `MISSING_FEATURES.md` / site status.

- **Current Test Baseline**
  - Check with `PYTHONPATH=. uv run pytest --tb=no -q`.
  - Known gaps are documented in `MISSING_FEATURES.md` and mirrored in docs/site status pages.

- **Error Reporting Contract Tightening**
  - Removed duplicate human-side codegen failure printing in `a7/compile.py`.
  - JSON payload now reports `artifacts.output_path` / `artifacts.doc_path` only when files actually exist.

- **Examples Stabilized for E2E Verification**
  - Updated `examples/*.a7` so all 36 compile, build, run, and produce deterministic output for golden checks.
  - Updated status docs to reflect `36/36` end-to-end verified examples.

- **Zig Backend Runtime Output and Arithmetic**
  - `io.println`/`io.print` placeholder conversion is now type-aware (`string` → `{s}`, `char` → `{c}`).
  - Division codegen now emits `/` for floating-point operands and keeps `@divTrunc` for integer division.
  - Mutation analysis no longer marks dereference targets as pointer-binding mutations.

- **ENHANCED AST PREPROCESSOR** (`a7/ast_preprocessor.py`)
  - Now accepts `symbol_table`, `type_map`, and `StdlibRegistry` from pipeline
  - 9 sub-passes: stdlib resolution, struct init normalization, mutation analysis, usage analysis, type inference, shadowing resolution, nested function hoisting, constant folding
  - Preprocessor traversals are iterative (no recursion)

- **REDUCED AST WALK RECURSION** across core compiler stages
  - Converted major AST walkers to iterative (explicit stack) implementations
  - Files: `ast_preprocessor.py`, `backends/zig.py`, `passes/semantic_validator.py`, `passes/name_resolution.py`, `passes/type_checker.py`, `generics.py`, `formatters/console_formatter.py`, `formatters/markdown_formatter.py`
  - Representative compilation paths work with Python recursion limit of 100

- **ZIG BACKEND** now reads preprocessor annotations (`emit_name`, `hoisted`, `is_used`, `resolved_type`)

- **ZIG CODE GENERATION BACKEND** (`a7/backends/zig.py`, ~1200 LOC)
  - Complete A7 → Zig translation for all AST node types
  - Type mapping: A7 primitives → Zig types, `string` → `[]const u8`, `ref T` → `?*T`
  - Statement mapping: `ret` → `return`, `match` → `switch`, C-style `for` → Zig `while` with continue expression
  - Expression mapping: arithmetic, comparisons, `a / b` → `@divTrunc(a, b)`, shift ops with `@intCast`
  - Memory management: `new T` → `allocator.create(T)`, `del p` → `allocator.destroy(p)`
  - I/O special-casing: `io.println(...)` → `std.debug.print(... ++ "\n", .{...})`
  - Smart preamble: only emits `std` import / allocator when needed
  - All 36 example programs compile successfully to Zig

- **AST PREPROCESSING** (`a7/ast_preprocessor.py`)
  - Runs between semantic analysis and code generation
  - Lowers `.adr`/`.val` sugar to ADDRESS_OF/DEREF nodes
  - Constant folding for literal arithmetic, boolean logic, unary negation

- **MARKDOWN DOCUMENTATION OUTPUT** (`--doc-out` / doc-mode)
  - `a7/formatters/markdown_formatter.py` generates full compilation reports
  - Documents all stages: source code, token table, AST structure, semantic results, generated Zig, summary
  - Usage: `uv run python main.py examples/001_hello.a7 --mode compile --doc-out auto`

- **FULL PIPELINE CONSOLE OUTPUT** (Rich formatting for all stages)
  - `display_full_pipeline()` in console_formatter.py shows all 4 stages with Rich tables and panels
  - Symbol table display, semantic pass results, Zig syntax-highlighted output

- **CODEGEN INTEGRATION TESTS** (`test/test_codegen_zig.py`)
  - Level 1: All 36 examples compile A7 → Zig without errors
  - Level 2: Generated Zig passes `zig ast-check` for simple programs
  - Level 3: Specific code pattern assertions
  - Level 4: Zig build checks for simple programs

### Changed
- Semantic analysis errors are now non-fatal (displayed as warnings, codegen proceeds)
- Module imports registered as `SymbolKind.MODULE` symbols for proper field access resolution

### Fixed
- Switch/match prong trailing commas (Zig requires `,` after `=> { ... }`)
- Character literal escaping (newline, tab, etc. now properly escaped)
- Correct AST attribute names throughout codegen: `operator` not `op`, `literal_value` not `value`, `parameter_types` not `param_types`

---

- 🔥 **COMPREHENSIVE ERROR SYSTEM: Professional Multi-Error Reporting**
  - **53 Structured Error Types**: SemanticErrorType (25) + TypeErrorType (28)
  - **Multiple Error Collection**: Shows ALL errors in one compilation run (not just first!)
  - **Helpful Error Messages**: Each error type has descriptive message + fix advice
  - **Specialized Error Classes**: SemanticError, TypeCheckError with rich context
  - **Batch Error Display**: "Found 28 errors:" with full source context for each
  - **Progressive Reporting**: Each semantic pass reports all its errors
  - Example: Fixed "Return type mismatch" shows: expected 'i32', got 'None'

- 🏷️ **NAMING REFACTORING: Lex → Tokenizer**
  - `LexError` → `TokenizerError` (more accurate terminology)
  - `LexErrorType` → `TokenizerErrorType`
  - `get_lexer_error_*` → `get_tokenizer_error_*`
  - Consistent naming throughout codebase

- ♻️ **MAJOR REFACTORING: Modular Output Formatters**
  - Extracted ~600 lines of formatting code from `compile.py` into dedicated modules
  - **`a7/formatters/json_formatter.py`**: JSON output formatting (195 lines)
  - **`a7/formatters/console_formatter.py`**: Rich console display formatting (536 lines)
  - **Result**: `compile.py` reduced from 964 lines to 310 lines (67% reduction!)
  - Clean separation of concerns: compilation logic vs. output formatting
  - Easier to maintain, test, and extend formatting independently
  - Same beautiful output, cleaner codebase

- 🚀 **SEMANTIC ANALYSIS INTEGRATED INTO COMPILATION PIPELINE!**
  - Semantic analysis now runs automatically during compilation (except analysis-only modes like `--mode ast` and `--mode tokens`)
  - Three-pass semantic analysis: Name Resolution → Type Checking → Semantic Validation
  - Error detection and reporting for type errors, undefined identifiers, control flow violations
  - Verbose mode shows progress: "✓ Name resolution complete", "✓ Type checking complete", etc.
  - Semantic errors displayed with rich formatting and source context

- 🎯 **SEMANTIC ANALYSIS INFRASTRUCTURE - Phase 2 Foundation Implemented!**
  - **Type System** (`a7/types.py`): Comprehensive type representation for A7
    - All type kinds: Primitives, Arrays, Slices, Pointers, References, Functions, Structs, Enums, Unions
    - Generic types: GenericParamType, GenericInstanceType, TypeSet
    - Type compatibility and equality checking
    - Predefined type sets: Numeric, Integer, SignedInt, UnsignedInt, Float
    - Immutable frozen dataclasses for type safety
  - **Symbol Tables** (`a7/symbol_table.py`): Hierarchical scope management
    - Scope nesting with enter/exit operations
    - Symbol registration and lookup
    - Module table for import tracking
    - Support for aliased imports, using imports, and named imports
  - **Semantic Context** (`a7/semantic_context.py`): Analysis state tracking
    - Function context (current function, return type, generic parameters)
    - Loop context (depth, labels, break/continue tracking)
    - Defer context (deferred expressions and scoping)
    - Control flow validation helpers
  - **Name Resolution Pass** (`a7/passes/name_resolution.py`): First analysis pass
    - Builds symbol tables for all scopes
    - Registers all declarations (functions, structs, enums, unions, variables)
    - Detects name collisions and shadowing
    - Handles function parameters, struct fields, enum variants
  - **Type Checking Pass** (`a7/passes/type_checker.py`): Second analysis pass
    - Type inference for `:=` declarations
    - Expression type checking (binary ops, unary ops, calls, field access)
    - Function signature validation
    - Assignment compatibility checking
    - Struct/enum/union type registration
  - **Semantic Validation Pass** (`a7/passes/semantic_validator.py`): Third analysis pass
    - Control flow validation (break/continue in loops)
    - Return statement validation
    - Defer scoping checks
    - Memory management validation (new/del)
  - **Generic System** (`a7/generics.py`): Generic type handling
    - Generic constraints and type sets
    - Type unification for inference
    - Monomorphization infrastructure (placeholder)
  - **Module Resolver** (`a7/module_resolver.py`): Import system
    - Module path resolution
    - Circular dependency detection
    - Import statement processing
    - Module caching and loading
  - **Test Suite** (`test/test_semantic_analysis.py`): Comprehensive tests
    - Name resolution tests
    - Type checking tests
    - Semantic validation tests
    - Integration tests for complete programs
- 🎉 **PARSER 100% COMPLETE - All remaining language features implemented!**
  - **Variadic Functions**: Full support for variadic parameters with `..type` or `..` syntax
    - Example: `sum :: fn(values: ..i32) i32`
    - Example: `printf :: fn(format: string, args: ..)`
    - AST tracks `is_variadic` flag on parameters
  - **Type Sets**: Complete `@type_set()` parsing for generic constraints
    - Example: `Numeric :: @type_set(i8, i16, i32, i64, f32, f64)`
    - TYPE_SET AST node with list of type members
    - Used in generic constraints and type alias declarations
  - **Generic Constraints**: Full constraint syntax for generic parameters
    - Predefined type sets: `fn($T: Numeric, x: T) T`
    - Inline type sets: `fn($T: @type_set(i32, i64), x: T) T`
    - AST stores constraint on GENERIC_PARAM nodes
  - **Labeled Loops**: Implemented for all loop forms (while, for, for-in, indexed for-in)
    - Syntax: `@outer for i := 0; i < 10; i += 1 { break outer }`
    - Zig backend emits native labeled loops (`label: while ...`, `break :label`)
    - C backend lowers to goto-based control flow with unique labels
  - **Builtin Intrinsics**: All `@function` intrinsics now parse correctly
    - Type-taking intrinsics: `@size_of(T)`, `@align_of(T)`, `@type_id(T)`, `@type_name(T)`
    - Expression-taking intrinsics: `@unreachable()`, `@panic(msg)`
    - Parsed as CALL nodes with builtin identifier
    - Correctly distinguishes type vs expression arguments
  - **Using Imports**: `using import "module"` syntax fully supported
    - AST tracks `is_using` flag on IMPORT nodes
    - Example: `using import "vector"`
  - **Named Item Imports**: `import "path" { Name1, Name2 }` syntax fully supported
    - AST tracks `imported_items` list on IMPORT nodes
    - Example: `import "vector" { Vec3, dot, cross }`
  - **Generic Struct Literal Instantiation**: Type parameters on struct literals
    - Example: `p := Pair(i32, string){42, "answer"}`
    - Parses type arguments and attaches to STRUCT_INIT node
    - Combines generic instantiation with struct initialization

### Changed
- **Clarified generics constraint syntax with inline @type_set() support**:
  - Generic type parameters use declaration-vs-usage pattern:
    - `$T` declares a compile-time type parameter
    - `T` (without `$`) references a declared type parameter
  - Constraints can be specified inline in two ways:
    - Predefined type set: `fn($T: Numeric, x: T) T {}`
    - Inline type set: `fn($T: @type_set(i32, i64), x: T) T {}`
  - Updated SPEC.md with comprehensive examples of both constraint forms
  - Benefits: Flexible constraint specification, supports both predefined and ad-hoc type sets

### Fixed
- **Fixed logical operators in all example files**:
  - Replaced C-style `&&` with A7 keyword `and` throughout all examples
  - Replaced C-style `||` with A7 keyword `or` throughout all examples
  - Fixed 6 example files that incorrectly used `&&`/`||` operators
  - All 36 examples now generate valid AST (was 34/36, now 36/36)
  - Simplified complex boolean expressions to work around parser limitations with `(a or b) and !c` patterns
- **Corrected nil usage in specification and examples**:
  - Updated `docs/SPEC.md` to clarify that `nil` is only valid for reference types (`ref T`)
  - Arrays, structs, primitives, and other value types cannot be assigned `nil`
  - Fixed all 36 example files to use proper array initialization:
    - Replaced invalid `arr: [5]i32 = nil` with `arr: [5]i32` (zero-initialized)
    - Added clear comments explaining zero-initialization behavior
  - Arrays now properly initialized with: no initializer (zero-init), single value, or array literal
- **Fixed spec violations with struct initialization** (7 examples, 9 instances):
  - `examples/004_func.a7`: Fixed `divide()` function returning `cast(struct, nil)` → proper struct literal
  - `examples/023_inline_structs.a7`: Fixed `get_point()` and `sincos()` functions returning `cast(struct, nil)` → proper inline struct initialization
  - `examples/027_callbacks.a7`: Fixed `EventDispatcher` initialization with array field set to `nil` → named field init (auto-zero)
  - `examples/031_number_guessing.a7`: Fixed 3 difficulty config functions returning `cast(struct, nil)` → proper struct literals
  - `examples/033_fibonacci.a7`: Fixed `FibMemo` initialization with array field set to `nil` → named field init (auto-zero)
  - `examples/034_string_utils.a7`: Fixed `count_vowels()` returning `cast(struct, nil)` → proper struct literal
  - All examples now use proper struct initialization with explicit field values or rely on zero-initialization

### Changed
- **Modernized all example code to use compound assignment operators**:
  - Updated all for loops and assignments to use `+=`, `-=`, `*=`, `/=` instead of verbose forms
  - Changed `i = i + 1` → `i += 1` throughout 36 example files
  - Changed struct field updates like `obj.val.field = obj.val.field + 1` → `obj.val.field += 1`
  - Improved code readability and demonstrated idiomatic A7 style
- Updated visibility rules documentation to clarify `public` modifier restrictions
- Updated `test_parser_examples.py` to handle files with import statements

### Added
- **70 new creative and systematic parser tests** (+54 passing, +16 documenting advanced features):
  - `test_parser_creative_cases.py` (35 tests) - Unusual syntax patterns and real-world coding patterns
    - Creative combinations: chained pointers, match expressions in various contexts, complex inline structs
    - Real-world patterns: state machines, callback registries, memory pools, iterators, builder pattern
    - Edge cases: complex casts, nested struct literals, unusual member access chains
  - `test_parser_unicode_and_special.py` (18 tests) - Unicode, special characters, boundary values
    - Unicode strings: emojis, multilingual text (Chinese, Japanese, Korean, Arabic, Russian, Hebrew)
    - Comment edge cases: nested block comments, comments with code-like content
    - Long constructs: long identifiers, long strings, many function parameters, wide expressions
    - Ambiguous syntax: generic vs comparison operators, struct literal vs block disambiguation
  - `test_parser_combinatorial.py` (17 tests) - Systematic feature combinations
    - Type combinations: all primitive types in arrays/pointers/functions, nested type patterns
    - Operator combinations: all binary/unary/assignment operators, precedence scenarios
    - Declaration variants: variables, functions, structs, enums in all valid forms
    - Control flow variants: if/else chains, loop patterns, match statement forms
    - Expression combinations: call expressions, member access, literals, memory operations
  - Test coverage expanded with creative, combinatorial, and unicode/special-character tests
- **Comprehensive Gap Analysis**:
  - Created `SPEC_EXAMPLES_GAP_ANALYSIS.md` documenting discrepancies between spec and examples
  - Identified outdated "Known Limitations" claims (range patterns, multiple case values, fallthrough all work)
  - Found labeled break/continue documented but not actually implemented
  - Cataloged undocumented features (compound assignments, match expressions, qualified enum access)
  - Full comparison of all 36 examples against specification
- **New Examples** (14 new programs added, total now 36):
  - Feature demonstrations:
    - `022_function_pointers.a7` - Higher-order functions and callbacks
    - `023_inline_structs.a7` - Anonymous struct types showcase
    - `024_defer.a7` - Resource management with defer
    - `025_linked_list.a7` - Generic linked list implementation
    - `026_binary_tree.a7` - Binary search tree with traversal
    - `027_callbacks.a7` - Event handling and dispatcher pattern
    - `028_state_machine.a7` - State machines with function pointers
    - `029_sorting.a7` - Sorting algorithms with custom comparators
  - Practical applications:
    - `030_calculator.a7` - Math operations including sqrt, power
    - `031_number_guessing.a7` - Interactive game with RNG
    - `032_prime_numbers.a7` - Sieve of Eratosthenes, factorization
    - `033_fibonacci.a7` - Multiple implementations with memoization
    - `034_string_utils.a7` - Text processing utilities
    - `035_matrix.a7` - Matrix operations and linear algebra
- Improved existing examples with better comments and demonstrations
- Inline/anonymous struct type parsing (`struct { id: i32, data: string }`)
- Function type parsing (`fn(i32) i32`, function pointers, higher-order functions)
- 48 comprehensive test cases for type combinations and edge cases
- New test file `test_parser_type_combinations.py` with 35 tests
- 13 edge case tests for inline struct types in `test_parser_extreme_edge_cases.py`
- Support for inline structs in function parameters and return types
- Support for nested inline struct types
- Support for inline structs with function pointer fields
- Support for arrays and slices of inline structs
- Documentation of language influences (JAI, Odin) in README

### Changed
- README.md simplified and made more natural to read
- Example count increased from 22 to 36 programs (+64% increase)
- Enhanced existing examples (001-012) with comprehensive teaching comments
- Example code: ~1,800 → ~3,500 lines (+94% increase)
- Parser completeness increased from 65% to 72%
- Test count expanded across parser, codegen, and semantic suites
- Type system completeness increased from 67% to 89%
- Updated TokenType.STRUCT to be recognized in function return type parsing
- Improved documentation in README.md, TODOLIST.md, CLAUDE.md, and MISSING_FEATURES.md
- Created examples/README.md - catalog of all example programs
- Created EXAMPLES_SUMMARY.md - comprehensive example documentation

### Fixed
- Function type parsing now works in all contexts (params, returns, struct fields)
- Inline struct types now supported in function return types
- Trailing commas now handled correctly in inline struct field lists

## [0.2.0] - 2025-11-03

### Added
- Function type parsing implementation
- Generic type instantiation in type expressions
- Uninitialized variable declarations
- Comprehensive edge case testing infrastructure

### Changed
- Parser completeness increased from 60% to 65%
- Struct literal heuristic improved for better disambiguation
- Test suite expanded with extreme edge case tests

### Fixed
- Generic type parameters in parentheses (e.g., `List($T)`)
- Struct literal vs block statement disambiguation
- Return statement without value for void functions

## [0.1.0] - 2025-11-02

### Added
- Complete tokenizer with all A7 token types
- Recursive descent parser with AST generation
- Support for all major language constructs
- 22 example A7 programs
- Comprehensive test suite (352 tests)
- Rich error messages with source context
- Property-based pointer syntax (`.adr`, `.val`)
- Control flow (if/else, while, for, match)
- Struct, enum, and union declarations
- Function declarations with generics
- Import statements
- Cast expressions

### Documentation
- Complete language specification (docs/SPEC.md)
- Development guide (CLAUDE.md)
- TODOLIST.md with tactical and strategic roadmaps
- MISSING_FEATURES.md with comprehensive feature gap analysis

[Unreleased]: https://github.com/code5717/a7-py/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/code5717/a7-py/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/code5717/a7-py/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/code5717/a7-py/releases/tag/v0.1.0
