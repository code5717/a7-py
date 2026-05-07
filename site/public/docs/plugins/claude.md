# Claude Code

Use this workflow when Claude Code works in the A7 repo.

## Read First

- `AGENTS.md`
- `CLAUDE.md`
- `/a7-py/llms.txt`
- `/a7-py/docs/index.md`

## Commands

```bash
uv sync
uv run a7 examples/001_hello.a7
uv run python scripts/check_docs_style.py
PYTHONPATH=. uv run pytest --tb=no -q
```

## Repo Rules

- Keep `AGENTS.md`, `CLAUDE.md`, and `AGENT.md` aligned when agent guidance changes.
- Update public markdown docs when navigation or command surfaces change.
- Do not add recursive language examples.
