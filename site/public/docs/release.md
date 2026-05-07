# Release

## Full Local Gate

Run before tagging:

```bash
./run_all_tests.sh
(cd site && npm run build)
rm -rf dist
uv build
uvx pip-audit --strict
(cd site && npm audit --omit=dev --audit-level=moderate)
```

Clean `dist/` before `uv build` so local package output contains only the
current version. GitHub release jobs run in a clean runner, but local release
prep should not rely on stale artifacts being absent.

## Debug and Release Artifacts

```bash
uv run python scripts/build_examples.py --profile debug --backend both --clean
uv run python scripts/build_examples.py --profile release --backend both --clean
```

Artifacts are written under:

```text
build/<profile>/zig/src/*.zig
build/<profile>/zig/bin/*
build/<profile>/c/src/*.c
build/<profile>/c/bin/*
```

## Publishing Status

Tag-triggered draft GitHub releases are configured. PyPI publishing is wired through Trusted Publishing/OIDC, but the public `a7-py` PyPI project must still be created or configured to trust repository `code5717/a7-py`, workflow `release.yml`, and environment `pypi`.
