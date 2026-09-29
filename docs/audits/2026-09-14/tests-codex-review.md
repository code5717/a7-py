# Production pipeline test review

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

Reviewer: Codex test-quality and v1 qualification worker. Advisory. The coordinating session owns implementation decisions and release acceptance.

Summary: 15 test cases added across three new files. Four pass and eleven expose current defects. No failure uses a skip or xfail marker. The 89 relevant existing CLI and preprocessing tests also pass. These results do not establish v1 readiness.

## Scope and method

Read `AGENTS.md`, including Test quality, `README.md`, relevant `docs/SPEC.md` and `docs/RELEASE.md` sections, both requested audit reports, compiler orchestration, artifact serialization, and existing CLI, stage-matrix, codegen, and preprocessing tests. A built-in sub-agent independently investigated CLI diagnostics and added `test/test_pipeline_diagnostics.py`. The controlling reviewer inspected that file and reran its tests with the affected suite.

Only three new files under `test/` and this report belong to this worker. Existing concurrent documentation changes were left alone. No compiler, configuration, release script, or site edits were made. No external model CLI, commit, deployment, or full gate was run.

All tests use real files and the production compiler or subprocess CLI. There are no mocks. Fixtures use pytest's unique temporary directories. Zig local and global caches stay inside each fixture directory. The native binding cases build only. The only executed A7 fixture performs deterministic integer division and remainder with literal divisor 5, in Debug and ReleaseFast. No crashing or memory-corruption binary was executed.

## Independent reproduction

- Ran `docs/audits/2026-09-14/repros/language_contract.py` using `.venv/bin/python`. Both direct source overwrite claims reproduce with exit 0. Malformed input exits 5 but advertises the unchanged old Zig output. Cyclic imports exit 0 while the same resolver rejects the graph during topological sorting.
- Recreated C5 and C6 through `A7Compiler.compile_file_detailed` and Zig 0.16.0. A local named `error` produces invalid Zig. An unused loop capture and a capture shadowing an outer local also produce rejected Zig. Typed `[3]i32` arrays replace inferred literals in the loop probes, isolating the capture failures from the separate tuple-lowering issue.
- Independently checked C8 using `compile_a7_to_zig` from `test/test_codegen_zig.py`. For `main :: fn() { x: i32 = "hello" }`, that helper returns Zig while the real compiler rejects the source with semantic exit 6. Helper-based results therefore cannot qualify the production pipeline. Existing helper tests remain unchanged because wholesale migration requires reviewing each test's intended layer.
- Diagnostic probes locate literal offending characters independently from compiler output. An unexpected `)` at column 10 reports column 9. A missing import has no span. A malformed imported module becomes INTERNAL exit 8. A semantic error originating in `helper.a7` identifies `main.a7` instead.
- A real output-write failure, using an existing directory as the requested Zig destination, exits IO but advertises that directory as an output artifact. Its sentinel file remains intact.

Memory-safety findings C1 through C4 were not retested here because dedicated reviewers own that work. C7's expression-depth limit was not qualified. This report does not claim independent reproduction of every finding in the source audits.

## Added test matrix

Paths below are relative to `test/`. Expected results describe requirements, not snapshots of current generated text.

| File and test | Requirement and independent expected result | Current observed result | Remaining boundary |
| --- | --- | --- | --- |
| `test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--output]` | LC-01. Reject output targeting input, preserve exact source bytes, report failure and no produced artifacts. | RED. Source replaced with Zig, exit 0. | Direct same path only. Does not cover symlinks, hardlinks, or imported sources as destinations. |
| `test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--doc-out]` | LC-01. Reject report targeting input before any artifact write and preserve source bytes. | RED. Source replaced with Markdown, exit 0. | Does not choose an exact failure exit code. Alias and cross-artifact collisions remain open. |
| `test_pipeline_artifacts.py::test_failed_compile_does_not_advertise_stale_output` | LC-02. Parse rejection preserves an earlier artifact but excludes it from this invocation's artifact list. | RED. Exit 5 and old bytes preserved, but JSON advertises the stale file. | One pre-codegen failure. Does not qualify every earlier stage or interrupted writes. |
| `test_pipeline_artifacts.py::test_output_write_failure_does_not_advertise_directory_as_artifact` | Artifact provenance. A directory that caused IO failure is not a successfully emitted Zig artifact. Existing contents survive. | RED. IO failure preserves sentinel but reports directory as output. | Real filesystem boundary, no permission simulation. Disk-full and partial-write behavior unverified. |
| `test_pipeline_artifacts.py::test_success_reports_real_output_and_preserves_all_inputs` | Successful CLI compilation with an imported module reports nonempty emitted files and leaves main and module bytes unchanged. | GREEN. Output and report exist at reported paths, both inputs unchanged. | Does not qualify generated module behavior, report content, or native execution. |
| `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[token]` | Tokenizer rejection identifies backtick at main line 3, column 10, emits no Zig, and preserves input. | GREEN. TOKENIZE exit and exact position. | ASCII, spaces, single invalid token. |
| `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[parse]` | Parser rejection identifies unexpected `)` at main line 3, column 10 and emits no Zig. | RED. Correct category, but column 9. | Does not require exact prose or end-span policy. |
| `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[semantic]` | Undefined function identifies `unknown` at main line 3, column 5 and prevents codegen. | GREEN. SEMANTIC exit and exact position. | One name-resolution failure, not every semantic pass. |
| `test_pipeline_diagnostics.py::test_missing_import_diagnostic_locates_import_declaration` | Missing module identifies the editable import declaration on main line 2. | RED. Semantic rejection has no span. | Accepts any column inside the declaration, avoiding a guessed token-selection policy. |
| `test_pipeline_diagnostics.py::test_imported_parse_error_is_a_source_failure_with_module_location` | Malformed source inside helper is a source error that identifies helper line 3. | RED. INTERNAL exit 8, ParseError, empty details. | Accepts PARSE or SEMANTIC wrapper category. Nested module failures unverified. |
| `test_pipeline_diagnostics.py::test_imported_semantic_error_preserves_origin_file` | Undefined identifier in helper reports helper line 3, column 5. | RED. Reports main file instead. | Single imported module. No source-map qualification across transitive imports. |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[zig-keyword-local]` | SPEC identifier rules and C5. Valid A7 local `error` must lower to buildable Zig. | RED. A7 succeeds, Zig rejects `const error`. | One local keyword binding, not the full keyword set or every binding context. Compile only. |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[unused-loop-capture]` | Advertised for-loop support and C6. Unused capture over a typed array must compile. | RED. A7 succeeds, Zig reports unused capture. | Ordinary capture only, not indexed or nested loops. Compile only. |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[shadowed-loop-capture]` | README shadowing resolution and C6. A loop-local name may coexist with the outer binding after lowering. | RED. A7 succeeds, Zig reports shadowing of outer constant. | Typed array, one scope boundary. Does not prove post-fix runtime name resolution. |
| `test_pipeline_native.py::test_folded_and_runtime_integer_arithmetic_agree_across_profiles` | Existing truncating-division contract, preprocessing tests, and release profiles. `-17 / 5` is `-3`; its remainder is `-2`. Literal-folded and parameter-based expressions must print those answers in both profiles. | GREEN. Both binaries print exactly two lines of `-3 -2`, exit 0, empty stderr. | One safe signed arithmetic fixture. Does not prove overflow handling or all optimizer transformations. |

## Commands and observed results

Run from the repository root:

```sh
.venv/bin/python -m pytest -q test/test_pipeline_artifacts.py test/test_pipeline_diagnostics.py test/test_cli_failures.py test/test_ast_preprocessor.py
```

Observed: 8 failed, 92 passed in 2.89 seconds. Three passing cases are new, and 89 are existing tests. All eight failures belong to the added tests and match the matrix.

```sh
A7_TEST_ZIG=/tmp/a7-audit-20260914/zig/zig .venv/bin/python -m pytest -q test/test_pipeline_native.py
```

Observed: 3 failed, 1 passed in 24.54 seconds. All three failures are real Zig build diagnostics. The arithmetic test builds and executes both profiles before passing.

The native tests require Zig 0.16.0 through `A7_TEST_ZIG` or PATH. An absent tool or wrong version fails explicitly instead of silently skipping qualification. Python and the supplied Zig binary worked. No provider, authentication, or capability failure occurred during this review. An exploratory arithmetic fixture using `b += 0` met the already reported compound-assignment proof defect. It was discarded in favor of a literal nonzero divisor so the optimization test does not depend on that unrelated defect.

## Gaps and decisions left with the coordinator

The existing stage matrix already repeats modes and formats extensively. Adding another cross-product would contribute less than the imported-file positions and stale-output checks above. Existing preprocessing tests establish local transformations, while the new arithmetic case checks their observable result after the full pipeline and two native profiles.

Do not turn LC-03 into an unconditional cycle-rejection test yet. The CLI/resolver inconsistency reproduces, but public module-cycle policy remains unsettled. Choose cycle support or rejection, document it, then assert that policy through the CLI with canonical file identities.

Source collision correction still needs symlink and hardlink identity cases, loaded-module input protection, and output/report destination collisions. Partial success when report writing fails after Zig output also needs an explicit artifact policy. These are proposed follow-ups, not qualified behavior.

The binding tests intentionally isolate three defects rather than claiming exhaustive keyword coverage. Follow-up native checks should cover parameters, fields, function names, indexed captures, nested scopes, and consistent renamed uses. Expression complexity limits, module initialization, and wider numeric semantics need agreed contracts before boundary tests can assert exact policy.

Note (2026-09-16): numeric semantics are now partly decided by ledger L3, L4 and L5 (explicit widths; integer `+`, `-`, `*` wrap). The remaining numeric rules are open under gate G3 in the [v1 plan](../../plan/README.md). Module-cycle policy is open under gate G6.

Passing these fixtures after implementation changes will close only their stated requirements. They do not establish memory safety, security enforcement, recovery, package installation, platform coverage, or production acceptance. The coordinator's separate full release gate and remaining reviews retain those responsibilities.
