# Release

How an A7 release ships. Tags drive builds; builds drive artifacts;
artifacts attach to GitHub releases. There is no package-registry
publishing.

## Cadence

A7 is pre-1.0. Releases are tagged when:

- A meaningful slice of the [Active priorities](/a7-py/compiler/status)
  closes.
- A breaking change in source syntax lands.
- The Zig toolchain is bumped.

There is no fixed schedule.

## Local pre-release gate

Run the full local gate before tagging:

```bash
./run_all_tests.sh
```

This must pass on a clean checkout with the pinned Zig version. If it
doesn't, the release isn't ready.

## Building artifacts

```bash
rm -rf dist
uv build
```

`uv build` produces an sdist + wheel under `dist/`. Cleaning first
prevents stale older artifacts from being mixed with the current build.

## Verifying artifacts

```bash
# Checksum manifest
uv run python scripts/generate_release_manifest.py dist --output dist/SHA256SUMS
uv run python scripts/verify_release_manifest.py dist/SHA256SUMS

# Archive contents (must include llms.txt + llms-full.txt for the docs tarball)
uv run python scripts/verify_archive_contents.py \
    dist/a7-docs-site.tar.gz \
    --require dist/llms.txt \
    --require dist/llms-full.txt

# Clean-venv wheel install smoke test
uv build
uv run python scripts/verify_wheel_install.py --skip-build
```

## Example artifact builds

Native binaries for the example suite are produced under both profiles:

```bash
uv run python scripts/build_examples.py --profile debug   --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

Release archives are platform/toolchain-tagged:

```text
a7-example-artifacts-linux-x86_64-zig0.16.0-<profile>.tar.gz
```

Keep any docs or scripts that reference these filenames in sync.

## Tagging and GitHub releases

```bash
git tag v0.16.x
git push origin v0.16.x
```

The release workflow on GitHub:

1. Builds the Python distributions and example artifacts.
2. Attaches them to a **draft** GitHub release.
3. Generates and attaches `dist/SHA256SUMS`.

A maintainer reviews the draft and publishes it manually. There is no
automated registry publish.

## Docs site deploy

The site under `site/` deploys to GitHub Pages at
<https://code5717.github.io/a7-py/>. The Vite build produces a static
`dist/` that includes:

- The React SPA bundle.
- `docs-data/<slug>.json` per page.
- `llms.txt` and `llms-full.txt` regenerated from the markdown corpus.
- `sitemap.xml` regenerated from the manifest.

See [Deploy](/a7-py/project/deploy) for the deploy workflow.

## Post-release checklist

When a release ships, update:

1. `docs/CHANGELOG.md` — release-facing entry.
2. `README.md` — usage, feature lists, examples (if behaviour changed).
3. `docs/SPEC.md` — language semantics or syntax (if changed).
4. `docs/STATUS.md` — close or open gaps.
5. `site/public/docs/*.md` — public docs that mirror the above.
6. `site/public/llms.txt`, `site/public/llms-full.txt` — auto-regenerated
   by the docs build; commit the updated files.

Drift between these is a bug. CI's docs-style check helps catch it.

## Out of scope

- No `a7 install`, no package registry, no lockfiles. Vendor-and-commit
  or use git submodules for downstream A7 code.
- No staged-channel (`beta`, `stable`) release model yet.
- No homebrew formula, no apt repo, no scoop bucket. Pip-installable from
  the GitHub release artifacts only.
