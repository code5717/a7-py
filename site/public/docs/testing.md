# Testing

A7's tests live in `test/` at the repository root. The suite is the
contract between the compiler and the language; the docs are downstream
of it.

## Running the suite

```bash
PYTHONPATH=. uv run pytest                          # everything
PYTHONPATH=. uv run pytest test/test_tokenizer.py   # one file
PYTHONPATH=. uv run pytest -k "generic" -v          # filtered
PYTHONPATH=. uv run pytest --tb=no -q               # quick pass/fail tally
```

Coverage spans:

- Tokenizer round-trips.
- Parser AST shapes (snapshot-style).
- Semantic passes (name resolution, type checking, validation).
- Safety proof planning obligations.
- Codegen Zig output (snapshot-style).
- Stdlib registry mappings.
- Iterative-traversal invariant.

## End-to-end verification

The single source of truth for "does it actually compile and run":

```bash
uv run python scripts/verify_examples_e2e.py
```

For each program in `examples/`, this:

1. Compiles to Zig with `uv run a7`.
2. Builds the Zig with `zig build-exe`.
3. Runs the resulting binary.
4. Diffs stdout against `test/fixtures/golden_outputs/<name>.out`.

Any drift fails the script.

## Golden outputs

Snapshots of expected stdout live in `test/fixtures/golden_outputs/`.
Update them when example behaviour changes:

```bash
uv run a7 examples/041_route_simulation.a7
zig build-exe -O ReleaseFast examples/041_route_simulation.zig
./041_route_simulation > test/fixtures/golden_outputs/041_route_simulation.out
```

Commit the updated `.out` along with the source change.

## Error-stage matrix

To verify the compiler still rejects malformed programs at every stage:

```bash
uv run python scripts/verify_error_stages.py --mode-set all --format both
```

This walks the negative-test corpus and checks that each program fails
at the expected stage and with the expected exit code.

## Debug + release artifact builds

```bash
uv run python scripts/build_examples.py --profile debug   --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

Each builds the full example suite under the given profile and emits
artifacts under `build/<profile>/zig/`. CI runs both.

## The full local gate

```bash
./run_all_tests.sh
```

This is the source of truth for "everything that must pass before
releasing." It runs:

- pytest (the unit + integration suite)
- parser / semantic / codegen tests
- Zig example E2E
- debug + release artifact verification
- error-stage matrix
- docs style check
- secrets check
- package build (`uv build`)
- clean-venv wheel install smoke test

Run it before reporting a non-trivial task as done.

## Iterative-traversal guard

`test/test_iterative_traversal.py` exercises the supported pipeline at
Python recursion limit 100. Any new compiler-internal code that
reintroduces recursion will fail this test. The parser is exempt (it
is recursive descent and depth-bounded by source nesting).

## Adding a test

For a new feature:

1. Add or update an example program in `examples/`.
2. Capture the golden output to `test/fixtures/golden_outputs/`.
3. Add a unit test in the relevant `test/test_<area>.py` file.
4. Run `./run_all_tests.sh`.

For a bug fix:

1. Add a regression case that fails on the unfixed compiler.
2. Apply the fix.
3. Verify the case passes; run the rest of the gate.

## Wheel install smoke test

```bash
uv build
uv run python scripts/verify_wheel_install.py --skip-build
```

This installs the freshly built wheel into a clean virtualenv and
imports the public surface. CI runs the same check on every release tag.
