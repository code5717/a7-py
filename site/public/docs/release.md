---
title: Release
nav: Release
group: Project
summary: Release gates, docs deployment, and artifact checks.
order: 6
---

# Release

The canonical release checklist is `docs/RELEASE.md`. This page is the public
summary.

## Local gates

```bash
uv run python scripts/verify_examples_e2e.py
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
cd site && bun install && bun run build
./run_all_tests.sh
```

`run_all_tests.sh` is the single local release gate. It covers pytest, example
E2E, debug and release artifacts, error-stage matrix, docs style, secrets check,
package build, and wheel install smoke test.

## Docs gate

The docs workflow runs:

```bash
python3 scripts/check_docs_style.py
cd site
bun install --frozen-lockfile
bun run lint
bun run build
```

The build writes `site/dist`, then GitHub Pages publishes that directory.

## Required archive files

The release workflow verifies that the docs archive contains:

- `dist/llms.txt`
- `dist/llms-full.txt`
- `dist/docs/index.md`
- `dist/docs/agent-usage.md`
- `dist/docs/release.md`
- `dist/docs/status.md`

Keep these paths stable unless the release workflow changes in the same commit.

## Native artifacts

Release archives include Zig source and binaries for the example suite. Archive
names include the target toolchain: `zig0.16.0`.

For contributing and doc maintenance rules, see [Project](/a7-py/project/).
