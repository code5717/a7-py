# Examples

The repository contains 38 runnable example programs in `examples/`.

Start with `examples/037_language_tour.a7` when you want a compact
learn-by-reading path: one commented file that walks through declarations,
arrays, slices, structs, enums, untagged unions, references, heap values,
function pointers, loops, and the no-recursion rule.

## Verify Examples

```bash
uv run python scripts/verify_examples_e2e.py
```

Both verifiers compile, build, run, and compare output against `test/fixtures/golden_outputs/*.out`.

## Browse

Use the interactive examples page in the docs app:

- [Examples](/a7-py/#/examples)

Use the source repository for raw files:

- [examples/](https://github.com/code5717/a7-py/tree/master/examples)
