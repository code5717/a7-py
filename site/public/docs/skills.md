# Skills

Use this page as agent-skill guidance for A7 work.

## Core Skill Rules

- Read `AGENTS.md` before changing the repo.
- Use `llms.txt` for routing and `llms-full.txt` for one-file context.
- Never generate recursive A7 source.
- Use loops, explicit stacks, queues, and index-based worklists.
- Treat tests as evidence, not as a substitute for source review.

## Change Checklist

Update these files when behavior, commands, or public docs change:

- `docs/CHANGELOG.md`
- `README.md`
- `docs/SPEC.md`
- `docs/STATUS.md`
- `site/public/llms.txt`
- `site/public/llms-full.txt`
- `site/public/docs/`

## Verification

```bash
uv run python scripts/check_docs_style.py
PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
```
