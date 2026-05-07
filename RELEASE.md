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
- `zig` on `PATH`
- Node.js 22+ for the docs site

## Debug Builds

Debug builds keep compiler/runtime diagnostics friendly:

```bash
uv run python scripts/build_examples.py --profile debug --backend both --clean
```

Output layout:

```text
build/debug/zig/src/*.zig
build/debug/zig/bin/*
build/debug/c/src/*.c
build/debug/c/bin/*
```

## Release Builds

Release builds use optimized target compiler flags and still run every binary
against the golden output fixtures:

```bash
uv run python scripts/build_examples.py --profile release --backend both --clean
```

Output layout:

```text
build/release/zig/src/*.zig
build/release/zig/bin/*
build/release/c/src/*.c
build/release/c/bin/*
```

## Full Release Gate

Run this before tagging:

```bash
./run_all_tests.sh
cd site && npm run build
cd ..
uv build
```

`run_all_tests.sh` includes:

- parser and tokenizer tests
- semantic tests
- Zig and C backend tests
- Zig example compile/build/run/output verification
- C example compile/build/run/output verification
- debug artifact build verification for Zig and C
- release artifact build verification for Zig and C
- CLI error-stage matrix verification
- docs style checks
- full pytest suite

## Tagging

1. Update `CHANGELOG.md` by moving relevant `Unreleased` notes under a version.
2. Confirm `pyproject.toml` has the intended version.
3. Run the full release gate.
4. Commit the release prep.
5. Tag:

```bash
git tag -a v0.1.0 -m "A7 v0.1.0"
git push origin master --tags
```

## Known Release Caveats

The compiler is not a security sandbox. A7 programs compiled to native binaries
can do whatever the generated Zig/C program and host runtime allow. Only compile
and execute source you trust.

Current language gaps remain tracked in `MISSING_FEATURES.md` and `TODO.md`.
