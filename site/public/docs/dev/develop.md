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
```

Run the full local gate for release-impacting changes:

```bash
./run_all_tests.sh
```

## Development Rules

- Prefer explicit stacks for new AST-wide analysis or reporting walks. Backend
  binary-expression emission is stack-based, but statement and non-binary
  expression emission still have recursive paths; keep low-recursion tests
  passing and track full conversion in `TODO.md`.
- No recursive A7 source examples.
- Keep docs and examples aligned.
- Document remaining gaps instead of hiding them.
