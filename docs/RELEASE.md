# A7 Release Checklist

This file is the release/debug build source of truth for `a7-py`.

## Release Artifacts

A release should contain:

- the Python package built from `pyproject.toml`
- generated debug binaries for the example suite, if needed for diagnostics
- generated release binaries for the example suite, if needed for smoke testing
- the documentation site build under `site/dist`
- the changelog entry for the release version

## Local Prerequisites

- Python 3.13+
- `uv`
- Zig 0.16.0 on `PATH`
- Node.js 22+ for the docs site

## Debug Builds

Debug builds keep compiler/runtime diagnostics friendly:

```bash
uv run python scripts/build_examples.py --profile debug --backend zig --clean
```

Output layout:

```text
build/debug/zig/src/*.zig
build/debug/zig/bin/*
```

## Release Builds

Release builds use optimized target compiler flags and still run every binary
against the golden output fixtures:

```bash
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

Output layout:

```text
build/release/zig/src/*.zig
build/release/zig/bin/*
```

## Full Release Gate

Run this before tagging:

```bash
./run_all_tests.sh
(cd site && npm ci && npm run build)
rm -rf dist
uv build
uv run python scripts/verify_wheel_install.py --skip-build
uvx --from pip-audit==2.10.0 pip-audit --strict
uvx --from bandit==1.9.4 bandit -r a7 scripts main.py -q --skip B404,B603
(cd site && npm audit --omit=dev --audit-level=moderate)
```

`run_all_tests.sh` includes:

- parser and tokenizer tests
- semantic tests
- Zig backend tests
- Zig example compile/build/run/output verification
- debug artifact build verification for Zig
- release artifact build verification for Zig
- CLI error-stage matrix verification
- docs style checks
- committed secrets check
- package build
- clean-venv wheel install smoke test
- full pytest suite

The Python and docs dependency audits are separate release-gate commands above.
The Python audit tools are pinned so release gates do not fetch arbitrary latest
tool versions at runtime. The wheel install verifier installs the built wheel in
a clean virtual environment and exercises the installed `a7` entrypoint through
Zig code generation before release.

To create a local checksum manifest for package files, docs archives, or native
artifact archives, run:

```bash
uv run python scripts/generate_release_manifest.py dist --output dist/SHA256SUMS
uv run python scripts/verify_release_manifest.py dist/SHA256SUMS
uv run python scripts/verify_archive_contents.py dist/a7-docs-site.tar.gz --require dist/llms.txt --require dist/llms-full.txt
```

The tag release workflow generates `dist/SHA256SUMS` after all release archives
are built, verifies that the manifest contains the package, docs, and native
artifact archives, verifies required archive members, derives the current
example count from `scripts/project_status.py`, asserts the native example
archive contains that many generated Zig sources and binaries, re-checks the
hashes and sizes on disk, generates GitHub artifact attestations for each
release artifact, then attaches the artifacts to the draft GitHub release.

## Tagging

1. Update `docs/CHANGELOG.md` by moving relevant `Unreleased` notes under a version.
2. Confirm `pyproject.toml` has the intended version.
3. Run the full release gate.
4. Commit the release prep.
5. Tag and push:

```bash
git tag -a v0.3.0 -m "A7 v0.3.0"
git push origin master --tags
```

Pushing a `v*` tag runs `.github/workflows/release.yml`. The workflow reruns
the release gate, builds the Python package, builds the docs site, builds
release example artifacts, and creates a draft GitHub release with those files
attached.

Before publishing the draft, download each attached file and verify both the
checksum manifest and GitHub artifact attestation:

```bash
uv run python scripts/verify_release_manifest.py SHA256SUMS
gh attestation verify a7_py-*.tar.gz --repo code5717/a7-py
gh attestation verify a7_py-*.whl --repo code5717/a7-py
gh attestation verify a7-docs-site.tar.gz --repo code5717/a7-py
gh attestation verify a7-example-artifacts-linux-x86_64-zig0.16.0-release.tar.gz --repo code5717/a7-py
```

When building locally, remove `dist/` before `uv build`. The release workflow
runs on a clean GitHub runner, but local `dist/` can otherwise retain older
versioned wheels or source distributions that should not be uploaded.

Manual `workflow_dispatch` runs validate the release gate and artifact build
steps without creating a GitHub release.

The workflow keeps release permissions split: the gate/artifact build job uses
read-only repository contents access, and only the tag-only draft release job
uses `contents: write`.

The current workflow does not publish to a package registry. If registry
publishing is added later, wire it as a separate reviewed change rather than as
an implicit side effect of the draft GitHub release job.

## Known Release Caveats

The compiler is not a security sandbox. A7 programs compiled to native binaries
can do whatever the generated Zig program and host runtime allow. Only compile
and execute source you trust.

Current language gaps remain tracked in `docs/STATUS.md`.
