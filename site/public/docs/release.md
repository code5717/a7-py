# Release

## Full Local Gate

Run before tagging:

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

Clean `dist/` before `uv build` so local package output contains only the
current version. GitHub release jobs run in a clean runner, but local release
prep should not rely on stale artifacts being absent.
The Python audit tools are pinned so release gates do not fetch arbitrary latest
tool versions at runtime. The wheel install verifier installs the built wheel in
a clean virtual environment and checks the installed `a7` command through both
Zig code generation.

Generate checksums before uploading local artifacts:

```bash
uv run python scripts/generate_release_manifest.py dist --output dist/SHA256SUMS
uv run python scripts/verify_release_manifest.py dist/SHA256SUMS
uv run python scripts/verify_archive_contents.py dist/a7-docs-site.tar.gz --require dist/llms.txt --require dist/llms-full.txt
```

The tag workflow also verifies that `SHA256SUMS` contains the expected package,
docs, and native artifact archives before upload. It also checks required
archive members, then re-checks the hashes and sizes on disk. Tag runs also
generate GitHub artifact attestations for the package, docs, native examples,
and checksum manifest.

Before publishing a draft release, verify the downloaded release assets:

```bash
uv run python scripts/verify_release_manifest.py SHA256SUMS
gh attestation verify a7_py-*.tar.gz --repo code5717/a7-py
gh attestation verify a7_py-*.whl --repo code5717/a7-py
gh attestation verify a7-docs-site.tar.gz --repo code5717/a7-py
gh attestation verify a7-example-artifacts-linux-x86_64-zig0.15.2-release.tar.gz --repo code5717/a7-py
```

## Debug and Release Artifacts

```bash
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

Artifacts are written under:

```text
build/<profile>/zig/src/*.zig
build/<profile>/zig/bin/*
```

## Release Status

Tag-triggered draft GitHub releases are configured. The current workflow builds
Python package distributions, docs archives, native example artifacts, and
checksums, then attaches them to the draft GitHub release. It does not publish
to a package registry.
