# GLM release artifact reuse review

Model: `zai-coding-plan/glm-5.3` through OpenCode. Read-only static review.

Controller disposition: no blocker in the reviewed workflow. The reviewer's
opening statement about every artifact is too broad. Reuse applies to the Python
distributions and release example binaries. Docs archives and checksums are
created later. GitHub execution and attestation were not tested locally.

## Reviewer output

## Verdict: no blockers

The reuse is sound. Every artifact uploaded/attested is bit-identical to what the gate built and verified, and a gate failure prevents all downstream steps.

### Package distributions (`dist/`)

- Gate step "Package Build" (`run_all_tests.sh:71`) runs `rm -rf dist && uv build`, so `dist/` holds a fresh sdist+wheel.
- "Wheel Install Smoke Test" (`verify_wheel_install.py --skip-build`) is read-only toward `dist/`: it installs the wheel into a `tempfile.TemporaryDirectory` venv (`scripts/verify_wheel_install.py:66-77`) and never writes or deletes dist files.
- Post-gate steps before upload (`uv export` → `$RUNNER_TEMP`, pip-audit, bandit, bun audit) write outside `dist/` or are read-only.
- Later steps add only new names (`a7-docs-site.tar.gz`, `a7-example-artifacts-*.tar.gz`, `SHA256SUMS`); none collide with the `a7_py-*` globs used for upload and manifest.

### Example binaries (`build/release`)

- `build_examples.py` defaults to `build/<profile>` and `--clean` removes only that directory (`scripts/build_examples.py:282,294-295`); layout is `release/zig/src/*.zig` + `release/zig/bin/*`, matching the tar and `verify_archive_contents.py` requirements.
- The same step also runtime-verifies each binary against golden fixtures and exits 1 on any failure (`build_example`/`verify_runtime`, lines 119-161, 205-213, 326) — so the archived binaries were executed by the gate, not merely compiled. The workflow comment is accurate.
- No step after the release build writes to `build/`: `verify_error_stages.py` uses tempdirs and only writes an optional report (not passed in the gate invocation); docs-style/secrets checks are read-only; package build/smoke touch only `dist/` and temp. Post-gate, `build/` is only read by tar.

### Docs (`bun run check`)

- `check` = `lint && test && build` (`site/package.json:10`), so `site/dist` is still produced; build.ts rm-rf's DIST first and `copyPublic` copies `public/docs/*.md` and llms files into it (all six files the archive verifier requires exist in `site/public/`). A lint/test failure stops the step before build and fails the job.
- Side note: `build.ts:755-756` rewrites `site/public/llms.txt`/`llms-full.txt` — a working-tree mutation, but pre-existing `bun run build` behavior, outside `dist/`/`build/`.

### Failure handling

- `run_all_tests.sh` uses `set -u` without `-e`, but `run_check` tallies failures and the script exits 1 if any check failed (lines 40, 80-82); GitHub fail-fast then blocks upload, archive, attest, and release.
- Both uploads set `if-no-files-found: error`; the manifest `--require` list covers all five artifacts; `create-github-release` re-verifies SHA256SUMS after downloading, and `verify_release_manifest.py:73` resolves repo-relative manifest paths against the flat download dir via basename fallback, failing closed on missing/mismatched files. Release creation is tag-gated.

Provenance is marginally stronger than before: previously the gate-verified wheel was discarded (`rm -rf dist`) and a second, unverified-at-runtime rebuild was uploaded... actually the removed post-gate steps did re-run the wheel smoke, so assurance was equivalent — but the attested digests now match the gate-built files exactly instead of a rebuild.

### Limits

- Static review only; I did not run the gate or publish (per instructions).
- The same diff also consolidates the gate's pytest suites into one full `uv run pytest` run (superset of the old split lists plus the removed duplicate TOTAL run — no coverage loss) and switches pip-audit to an `uv export` requirements file (writes only to `$RUNNER_TEMP`); neither affects reuse.
- The `ls dist/a7_py-*.tar.gz` glob in the checksums step assumes exactly one sdist/wheel; multi-word expansion would fail the `--require` check. Pre-existing pattern, unchanged, and the gate's `rm -rf dist` keeps it single.
- Reuse assumes nothing outside the reviewed scripts writes to `dist/` or `build/` between gate and archive; I verified this for every step in the current workflow ordering only.
