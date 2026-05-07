# Contributing

Use this page to set up local A7 development.

## Setup

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
```

For site work:

```bash
cd site
npm ci
npm run build
```

## Local Checks

```bash
uv run python scripts/check_docs_style.py
PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
uv run python scripts/verify_examples_e2e_c.py
```

Run the full local gate for release-impacting changes:

```bash
./run_all_tests.sh
```

## Development Rules

- No recursive AST traversals.
- No recursive A7 source examples.
- Keep docs and examples aligned.
- Document remaining gaps instead of hiding them.
