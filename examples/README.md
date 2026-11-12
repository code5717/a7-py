# Examples

Each `*.a7` file here is a complete program with an expected stdout fixture
under `test/fixtures/golden_outputs/`.

`014_generics.a7` demonstrates `where T: Integer` with signed and unsigned
arguments, alongside generic functions and nested generic structs.
`016_unions.a7` shows tagged-union payload bindings. `018_modules.a7` imports
the helper `modules/geometry.a7` and uses its public record and function.
Helpers under `modules/` are imported by examples; they are not standalone
programs. `036_control_flow_edges.a7` shows labeled `break` and `continue`.

Browse the full table at `site/public/docs/examples.md`. Files that must fail
live in `examples/rejected/` with expected diagnostics in
`examples/rejected/manifest.json`:

```bash
uv run python scripts/verify_examples_e2e.py
uv run pytest test/test_rejected_examples.py
```
