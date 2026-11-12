# Push checkpoint checks, 2026-11-12

The existing compiler, tests, examples, research and site changes were checked
before committing for the requested push. The staged source tree before adding
this record and the status link was
`4c418b3ad32a43c1fd99c591beb92d09455461c3`.
This checkpoint does not qualify a release or full V1.

## Results

The machine exposes 24 logical CPUs. Checks used CPU affinity `0-7` or smaller
subsets and four pytest workers. The active Zig binary reports `0.17.0`;
the repository requires `0.16.0`.

| Command | Observed result |
| --- | --- |
| `git diff --cached --check` | Passed |
| `taskset -c 0-7 env A7_PYTEST_WORKERS=4 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 ./run_release_checks.sh` | Incomplete. Pytest reported 11 failed, 4,665 passed, one expected failure and 487 errors. Example E2E failed with Zig 0.17.0 errors. The controller stopped this run during debug artifact verification after confirming the incompatible toolchain. |
| `taskset -c 0-1 env PYTHONPATH=. uv run pytest test/test_zig_backend_runtime.py::test_prints_to_regular_files_keep_every_line -q --tb=short` | Setup failed because Zig reports 0.17.0 instead of required 0.16.0. |
| `taskset -c 0-3 env PYTHONPATH=. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run pytest -n 4 -m 'not zig' -q --tb=short` | 4,657 passed, five failed. All five failures are `test_build_cannot_replace_inputs_or_directories` cases. Each reports `Zig 0.16.0 required; found 0.17.0` and exit 2 instead of expected exit 3. |
| `taskset -c 4-7 env A7_PYTEST_WORKERS=4 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 ./run_all_tests.sh --only 'Docs Style' --only 'Secrets' --only 'Package Build' --only 'Error Stage'` | Four checks passed, seven skipped. Error-stage matrix: 61/61. Docs style and secrets passed. Wheel and source archive built. Native installation verification was skipped. |
| In `site/`: `taskset -c 0-3 bash -c 'bun install --frozen-lockfile && bun run check && bun audit --audit-level=moderate'` | Install and site checks passed, including current exports and 1,506 local resources plus 183 search targets. Dependency audit failed with one high-severity advisory for markdown-it 15.0.2. |

The dependency audit identifies
[GHSA-gfr2-rv44-r23c](https://github.com/advisories/GHSA-gfr2-rv44-r23c),
a quadratic-time rendering issue in markdown-it versions `>=15.0.0 <15.0.3`.
No dependency or compiler behavior was changed during this push task.

## Limits

Native tests, example E2E, artifact builds, benchmarks and native package
installation remain unverified with Zig 0.16.0 in this task. The release wrapper
did not reach its Python dependency audit or static security check.
The wrapper retained only the final pytest failure summary and recent output;
the focused and non-native reruns retain their
complete diagnostics under local `tmp/push-2026-11-12/`.

The unreferenced generated PDF
`output/pdf/deep-learning-for-compiler-ir-2026-10-04.pdf` remains outside the
commit. Existing candidate failures and pending language decisions remain open.
