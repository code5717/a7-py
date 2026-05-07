# Testing

Canonical page: [Compiler and Tests](/a7-py/docs/compiler.md).

```bash
PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
uv run python scripts/verify_examples_e2e_c.py
uv run python scripts/verify_backend_parity.py
uv run python scripts/verify_error_stages.py
./run_all_tests.sh
```

Use this alias when an agent guesses `/docs/testing.md`. The full compiler and verification notes live in `compiler.md`.
