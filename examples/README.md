# Examples

Each `*.a7` file here is a complete program with an expected stdout fixture
under `test/fixtures/golden_outputs/`.

Browse the full table at `site/public/docs/examples.md`. Files that must fail
live in `examples/rejected/` with expected diagnostics in
`examples/rejected/manifest.json`:

```bash
uv run python scripts/verify_examples_e2e.py
uv run pytest test/test_rejected_examples.py
```
