---
title: Release
nav: Release
group: Project
summary: Repository-root release commands, native artifacts, dependency audits, and docs gates.
order: 42
---

# Release

The [repository release checklist](https://github.com/code5717/a7-py/blob/master/docs/RELEASE.md)
is authoritative. Run these commands from the `a7-py` repository root. Site
commands use a subshell so subsequent commands remain in that root.

## Local gates

```bash
./run_release_checks.sh
# Optional before creating a tag:
./run_release_checks.sh --tag v0.3.0
```

This is the release workflow's command. It rejects tag/package/changelog
mismatches before building. It runs the compiler gate, installed wheel and
source-distribution native checks, docs checks, locked dependency audits and
Bandit. It creates no tag or publication.

The compiler gate includes tokenizer, parser, semantic and codegen tests;
example compile/build/run/output checks; debug and release artifacts; CLI
error-stage checks; docs style; secrets; packaging and isolated installation.
Installed programs must build and run under Zig Debug and ReleaseFast. The source
distribution must build its wheel outside the checkout and pass the same checks.

Python auditing uses exported locked project requirements. A passing site build
or dependency audit alone does not qualify the language or release.

## Debug and release artifacts

```bash
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

The builders execute binaries and compare their output against
`test/fixtures/golden_outputs/*.out`.

| Profile | Generated source | Native binaries |
| --- | --- | --- |
| Debug | `build/debug/zig/src/` | `build/debug/zig/bin/` |
| Release | `build/release/zig/src/` | `build/release/zig/bin/` |

## Docs gate

After intentional Markdown edits, explicitly synchronize tracked exports:

```bash
(cd site && bun run sync:exports)
```

Verify the resulting source and exports:

```bash
python3 scripts/check_docs_style.py
(cd site && bun install --frozen-lockfile && bun run check)
```

`bun run check:exports` detects stale exports. Ordinary `bun run build` does not
rewrite them. `bun run check` includes lint, type checks, source-derived
coverage checks, tests, build, export synchronization checks, and generated link
checks. The docs workflow builds `site/dist` for
GitHub Pages under `/a7-py/`.

## Required archive files

The docs archive must retain the existing public interfaces:

- `dist/llms.txt` and `dist/llms-full.txt`.
- `dist/docs/index.md` and every existing Markdown page.
- `dist/docs/agent-usage.md`, `dist/docs/release.md`, and `dist/docs/status.md`.
- Nested Markdown topics and `dist/docs/manifest.json`.

The manifest, search index, sitemap, HTML routes, and Markdown pages must agree
before release. Fetch live Markdown without JavaScript after deployment.

## Native artifacts

Archive filenames carry the platform and toolchain, for example
`a7-example-artifacts-linux-x86_64-zig0.16.0-release.tar.gz`.
The release workflow derives the expected example count through
`scripts/project_status.py` and verifies archive membership.

Create and verify a local checksum manifest after assembling artifacts:

```bash
uv run python scripts/generate_release_manifest.py dist --output dist/SHA256SUMS
uv run python scripts/verify_release_manifest.py dist/SHA256SUMS
uv run python scripts/verify_archive_contents.py dist/a7-docs-site.tar.gz --require dist/llms.txt --require dist/llms-full.txt
```

## Publishing requirements

Move release notes from `Unreleased` into the intended version, confirm the
package version, and pass the full release gate before tagging. A `v*` tag
triggers the release workflow, which creates a draft GitHub release. Before
publishing that draft, verify downloaded checksums and GitHub artifact
attestations as described in the repository checklist. The workflow does not
publish packages to a registry.

Building this website locally does not deploy it or publish a compiler release.
See [Project](/a7-py/docs/project.md) for contributor workflow and source authority.
