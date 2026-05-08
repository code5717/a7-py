# Codex

Use this workflow when Codex works in the A7 repo.

## Read First

```text
AGENTS.md
https://code5717.github.io/a7-py/llms.txt
https://code5717.github.io/a7-py/docs/index.md
```

## Preferred Checks

```bash
uv sync
uv run a7 examples/001_hello.a7
uv run python scripts/verify_examples_e2e.py
uv run python scripts/check_docs_style.py
```

Use `./run_all_tests.sh` for release-gate changes.

## Editing Rules

- Use `apply_patch` for manual edits.
- Keep site, README, SPEC, TODO, MISSING_FEATURES, and changelog in sync when behavior changes.
- Do not claim release readiness beyond the evidence in `COMPLETION_AUDIT.md`.
