# Contributing

## Workflow

1. Read `AGENTS.md` for repo workflow and source rules.
2. Make the smallest change that addresses the issue.
3. Keep examples, docs, and tests aligned.
4. Run focused checks first, then the full gate for non-trivial changes.

## Checks

```bash
PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
uv run python scripts/check_docs_style.py
./run_all_tests.sh
```

## Docs Sync

When behavior changes, review:

- `CHANGELOG.md`
- `README.md`
- `docs/SPEC.md`
- `MISSING_FEATURES.md`
- `TODO.md`
- `site/public/llms.txt`
- `site/public/llms-full.txt`
- `site/public/docs/`

## A7 Source Rule

Do not add recursive A7 source. Port recursive algorithms to loops, explicit stacks, queues, or index-based worklists.
