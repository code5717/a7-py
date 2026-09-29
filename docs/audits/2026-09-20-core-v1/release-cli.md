# Release and CLI verification

Date: 2026-09-20. This report covers focused checks in the working tree. It does
not establish that the full release gate passed or that A7 is production-ready.

## Installed artifacts

The strengthened verifier installs a wheel in a temporary virtual environment
outside the checkout. It checks that the imported `a7` package resolves inside
that environment. A two-module A7 program must compile, build with real Zig in
Debug and ReleaseFast, exit with code 0, and print exactly `wheel smoke 42\n`.
Undefined-function source must return semantic exit code 6 with a JSON diagnostic
and must not create its requested output artifact.

The opt-in `--verify-sdist` path extracts the source archive with Python's `data`
filter, builds a wheel from that temporary source tree, and repeats the same
installation and native checks. Missing Zig fails qualification.

Executed:

```bash
uv run pytest -q test/test_release_tooling.py -k wheel_install_smoke
uv run pytest -q test/test_release_tooling.py -k 'not wheel_install_smoke'
uvx --from bandit==1.9.4 bandit scripts/verify_wheel_install.py -q --skip B404,B603
```

Results: the wheel/source-archive integration passed in 23.58 seconds. The
remaining 18 release-tooling tests passed. File-scoped Bandit passed. These
results precede later central integration changes and are not a final artifact
qualification record.

## CLI behavior

Executed `uv run pytest -q test/test_cli_workflows.py test/test_cli_failures.py`.
All 26 tests collected at that point passed in 21.53 seconds. Real Zig built and
executed A7 in Debug and ReleaseFast. Tests covered paths containing spaces,
legacy JSON behavior, full-pipeline checks without file output, missing or wrong
Zig, and preservation of an existing executable when the native build fails.

Native argument forwarding, caller working directory and exit code 23 were
checked with a fake Zig executable that writes a small Python program. This is
a process-boundary test. It does not establish A7 argument-reading support.
Wrong-version and native-build-failure tests also use fake Zig executables.

Five additional source-output protection cases passed. After human diagnostics
were improved, nine affected nonnative workflow tests passed. Bandit on
`a7/cli.py` and `a7/toolchain.py` passed.

After the controller replaced duplicate dependency loading with the compiler's
`CompilationResult.input_paths`, the reviewer independently reran:

```bash
uv run --locked pytest -q test/test_cli_workflows.py -k 'cannot_replace or wrong_zig or missing_toolchain'
```

Result: 7 passed, 4 deselected in 0.84 seconds. The output-protection cases cover
the entry source, an imported source, symlink and hard-link aliases, and a
directory. Source bytes remain unchanged. This last run covers the integrated
input-path protection, not the full CLI suite.

## Release preflight defect and repair

The initial `run_release_checks.sh` called `uv run` before `uv sync --locked`.
A temporary project reproduced why that order could hide a stale lockfile.
After `uv lock`, its package version changed from 0.1.0 to 0.2.0. Results were:

```text
uv sync --locked --all-groups before preflight: exit 1
uv run python preflight: exit 0
uv.lock changed: True
uv sync --locked --all-groups after preflight: exit 0
```

The controller changed the preflight to:

```bash
uv run --locked python scripts/verify_release_version.py "$@"
```

The reviewer confirmed this command in the current script. The complete release
script was not rerun by this reviewer. A separate mismatched-tag invocation with
`--tag v9.9.9` reported that the tag disagrees with package version `v0.3.0`.

## Dependency and documentation checks

The locked Python requirements export passed pinned `pip-audit==2.10.0` with
`No known vulnerabilities found`. Bun audit passed for 103 packages using local
Bun 1.4.2. No network or provider failures occurred in those checks.

The initial full Bandit command failed on B607 in `scripts/check_no_secrets.py`
for invoking Git by a partial executable path. That result was reported to the
controller. The later file-scoped passes above do not establish the result of a
subsequent full Bandit scan.

After CLI documentation changes, `scripts/check_docs_style.py`, site lint and
site reference coverage passed. Export synchronization and complete site checks
were left to the controller. No release publication or attestation execution
was performed by this reviewer.

## Installed workflow acceptance gaps, historical finding

Closed by the installed-workflow patch and the second combined gate in
`final-release-checks.log`. The verifier now exercises every command below from
both wheel and source-distribution installations and compares version metadata.
GLM review 3 independently passed these checks and a tampered-version negative
control. The following text records the finding before its repair.

A later read-only review found that the installed-artifact verifier still calls
only legacy token mode and file-first compilation. It invokes Zig directly for
native builds. The new `check`, `build`, `run`, `doctor` and `--version` commands
are tested from the checkout, but not through the installed release artifact.
This is a coverage gap, not a reproduced installed-command failure.

Close it without adding redundant native builds:

- Retain one legacy token/code-generation check.
- Replace the two direct Zig builds with installed `a7 build` in debug mode,
  execution of its output, and installed `a7 run` in release mode. Require the
  same exact output and exit code.
- Invoke installed `check --format json` on valid and invalid source. Verify
  diagnostics, exit codes and the absence of new output artifacts.
- Invoke installed `doctor` on the qualified environment and require success.
- Compare installed `--version` and installed distribution metadata with the
  input wheel's metadata version. Apply the same checks to the source-archive
  wheel through the shared verifier.

The current verifier only requires a Zig executable to exist. Direct Zig builds
can bypass the new CLI's exact-version check. Exercising installed `build` and
`run` closes that toolchain-contract gap as well.

The tag checker compares the tag, `pyproject.toml` and changelog. It does not
compare the public `a7.__version__` constant or built distribution metadata.
Both source version declarations currently read `0.3.0`; no present mismatch
was found. A future version bump should have an explicit identity check across
those values and the installed CLI.
