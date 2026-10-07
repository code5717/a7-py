# A7 release checklist

This file is the release/debug build source of truth for `a7-py`.

Final V1 publication as `1.0.0` waits for every track in the
[delivery roadmap](plan/delivery-roadmap.md): core language, automatic memory,
libraries and tools, concurrency, CPU AI, actual GPU execution and self-hosting
parity. L73 sets this boundary. Passing the commands below alone does not qualify
those tracks. Publication is authorized once all required tracks and release
gates pass. The current package remains a development
release; no new release verification is claimed by this document.

## Release artifacts

A release should contain:

- the Python package built from `pyproject.toml`
- generated debug binaries for the example suite, if needed for diagnostics
- generated release binaries for the example suite, if needed for smoke testing
- the documentation site build under `site/dist`
- the changelog entry for the release version

## Local prerequisites

- Python 3.13+
- `uv`
- Zig 0.16.0 on `PATH`
- Bun 1.3+ for the docs site

## Shared-machine limits

`A7_PYTEST_WORKERS` accepts integers from 1 through 8 and defaults to 8.
The compiler gate rejects other values before running checks. Keep at least
eight logical CPUs free for other sessions. A worker count does not limit Zig
or child-process CPU use; restrict the complete gate's CPU affinity as well.

On a Linux machine with 24 logical CPUs numbered 0 through 23, this example
limits the gate and its children to CPUs 0 through 15:

```bash
A7_PYTEST_WORKERS=8 taskset -c 0-15 ./run_release_checks.sh
```

Inspect the local CPU layout before adapting that example. Do not use `-n auto`.
Use an isolated source snapshot for qualification and record its hashes. The
[qualification record](audits/2026-10-07/qualification.md) distinguishes saved
baseline results from later source. Historical checks are not a fresh run of
the current checkout.

## Debug builds

Debug builds keep compiler/runtime diagnostics friendly:

```bash
uv run python scripts/build_examples.py --profile debug --backend zig --clean
```

Output layout:

```text
build/debug/zig/src/*.zig
build/debug/zig/bin/*
```

## Release builds

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

## Fast builds

The gate also builds and runs every example with Zig's `ReleaseFast` mode:

```bash
uv run python scripts/build_examples.py --profile fast --backend zig --clean
```

These artifacts go under `build/fast/`. The `release` profile uses
`ReleaseSafe`; both optimized profiles must match the golden output fixtures.

## Full release gate

Run the same command used by release CI:

```bash
./run_release_checks.sh
# Before a tag is created, also verify its intended identity:
./run_release_checks.sh --tag v0.3.0
```

The command checks tag/package/changelog agreement before building. An untagged
run verifies the current package without claiming a tagged release. It runs the
compiler gate, installed wheel and source-distribution native checks, docs checks,
locked Python and Bun dependency audits, and Bandit. Any failed step fails the
command. It does not publish or create a tag.

Python dependency auditing exports the locked project requirements, including
development dependencies, before passing them to pinned `pip-audit`. Auditing the
tool's isolated environment alone does not qualify the project dependencies.

After intentional website content edits, run `(cd site && bun run sync:exports)`
and review the generated diff before running the site check. Ordinary builds do
not rewrite tracked exports. The site check detects stale exports and validates
reference coverage, types, publication tests, and generated links.

`run_all_tests.sh` includes:

- parser and tokenizer tests
- semantic tests
- Zig backend tests
- Zig example compile/build/run/output verification
- debug artifact build verification for Zig
- release artifact build verification for Zig
- fast artifact build verification for Zig
- CLI error-stage matrix verification
- docs style checks
- committed secrets check
- package build
- clean-venv wheel install smoke test
- full pytest suite

The complete release command includes Python and docs dependency audits.
The Python audit tools are pinned so release gates do not fetch arbitrary latest
tool versions at runtime. The install verifier installs the built wheel and a wheel rebuilt from the source
distribution in
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

## Known release caveats

The compiler is not a security sandbox. A7 programs compiled to native binaries
can do whatever the generated Zig program and host runtime allow. Only compile
and execute source you trust.

Current language gaps remain tracked in `docs/STATUS.md`.
