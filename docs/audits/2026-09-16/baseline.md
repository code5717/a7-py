# Baseline before the fix program

Status: Wave 0 record, 2026-09-16. Taken before any code change in the execution
plan. Later waves compare their gate results against this file.

## Environment

| Item | Value |
| --- | --- |
| Commit | `701c67936c70ad2b0608326e23e56cc5d38c9fdb` |
| Working tree | Uncommitted documentation changes only; `a7/` unchanged from the commit |
| Zig | 0.16.0 (pinned build from `.github/workflows/ci.yml`, SHA-256 checked) |
| uv | 0.12.6 |
| Full gate wall time | 542 s |

## `./run_all_tests.sh`

Result: 10 of 12 checks passed. One failure was caused by the audit setup, so the
true baseline is 11 of 12.

| Check | Result |
| --- | --- |
| Parser and tokenizer tests | Pass, 503 tests |
| Semantic analysis tests | Pass, 351 tests |
| Compiler, CLI and backend tests | Pass, 332 tests |
| Examples end to end | Pass, 43 of 43 |
| Debug artifact builds | Pass, 43 of 43 |
| Release artifact builds | Pass, 43 of 43 |
| Error-stage matrix | Pass, 61 of 61 |
| Docs style | Pass |
| Secrets check | Failed on `tmp/toolchain/zig-0.16.0/lib/std/crypto/scrypt.zig:679`, a Zig toolchain the audit had placed under `tmp/`. After removing it the check passes. The check scans `tmp/`, which is not skipped; see packet P0 |
| Package build | Pass |
| Wheel install smoke test | Pass |
| Full pytest | Failed: 12 failed, 2515 passed |

## The 12 failing tests

These are the pipeline tests cited in `docs/plan/README.md:331`. All were failing
before this program started.

| Test | Area |
| --- | --- |
| `test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--output]` | Output path collides with input |
| `test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--doc-out]` | Doc output path collides with input |
| `test_pipeline_artifacts.py::test_failed_compile_does_not_advertise_stale_output` | Stale artifact reported |
| `test_pipeline_artifacts.py::test_output_write_failure_does_not_advertise_directory_as_artifact` | Write failure reported as artifact |
| `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[parse]` | Parse diagnostic location |
| `test_pipeline_diagnostics.py::test_missing_import_diagnostic_locates_import_declaration` | Missing import location |
| `test_pipeline_diagnostics.py::test_imported_parse_error_is_a_source_failure_with_module_location` | Imported parse error origin |
| `test_pipeline_diagnostics.py::test_imported_semantic_error_preserves_origin_file` | Imported semantic error origin |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[zig-keyword-local]` | Zig keyword as a local name |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[unused-loop-capture]` | Unused loop capture |
| `test_pipeline_native.py::test_valid_a7_bindings_build_with_zig[shadowed-loop-capture]` | Shadowed loop capture |
| `test_pipeline_native.py::test_large_integer_folding_preserves_exact_quotient_and_remainder` | Integer folding through float |

The steps in `run_all_tests.sh` that run only selected test files pass; the
failures appear only in the final full pytest step, which is the only step that
collects the `test_pipeline_*` files.
