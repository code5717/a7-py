# Examples

The repository ships 46 example programs in `examples/` covering every
implemented language feature. Each one is verified end-to-end by
`scripts/verify_examples_e2e.py`: compile → Zig → native binary → run →
diff against `test/fixtures/golden_outputs/*.out`.

## How to run them

```bash
# Compile one example to Zig
uv run a7 examples/001_hello.a7

# Build and run all examples (debug + release)
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean

# E2E verification (compile + build + run + diff)
uv run python scripts/verify_examples_e2e.py
```

## Catalog

Examples are ordered roughly from simplest to most involved. Source under
`examples/` in the repository.

### Foundations

- `000_empty.a7` — a no-op program. Smoke test for the parser.
- `001_hello.a7` — print "Hello, World" via `std/io`.
- `002_var.a7` — variables, type inference, integer literals.
- `003_comments.a7` — single-line and nested block comments.
- `004_func.a7` — function declaration, parameters, return types.
- `019_literals.a7` — integer, float, string, char literal forms.

### Control flow

- `005_for_loop.a7` — index-based `for` loop.
- `006_if.a7` — `if` / `else if` / `else`.
- `007_while.a7` — `while` loops with `break` and `continue`.
- `008_switch.a7` — `match` statement over an integer.
- `036_control_flow_edges.a7` — labeled loops, fallthrough, defer.

### Data

- `009_struct.a7` — struct declaration, literal, field access.
- `010_enum.a7` — enum declarations and pattern matching.
- `012_arrays.a7` — fixed-size arrays, indexing, length.
- `015_types.a7` — primitive types and casts.
- `016_unions.a7` — untagged unions with field literal access.
- `017_methods.a7` — method syntax on structs.

### Memory

- `011_memory.a7` — `new` / `del` with `defer`.
- `013_pointers.a7` — references, nil checks, parameter passing.

### Generics & modules

- `014_generics.a7` — generic functions and structs.
- `018_modules.a7` — file-backed imports (single-file emission).

### Algorithms (iterative)

- `020_collatz.a7` — Collatz sequence with a loop.
- `021_sorting.a7` — bubble sort using indexes.
- `025_linked_list.a7` — singly-linked list traversal with a `cur` pointer
  loop instead of recursion.
- `026_binary_tree.a7` — binary tree pre-order walk via an explicit stack.
- `029_sorting.a7` — sort with comparator pattern.
- `032_prime_numbers.a7` — sieve / trial division.
- `033_fibonacci.a7` — iterative fibonacci (no recursion).

### Application-shaped

- `027_callbacks.a7` — callback-shaped code (without recursion cycles).
- `028_state_machine.a7` — explicit state machine.
- `030_calculator.a7` — expression evaluator.
- `031_number_guessing.a7` — interactive loop pattern.
- `034_string_utils.a7` — string operations via `std/string`.
- `035_matrix.a7` — 2D arithmetic over a flat buffer.
- `037_language_tour.a7` — single-file commented tour of the implemented
  language surface. Read this first if you want one file that shows what
  works today.

### Showcase

- `038_inventory_report.a7`, `039_text_analyzer.a7`, `040_task_board.a7`,
  `041_route_simulation.a7`, `042_gradebook.a7` — multi-feature programs
  that combine modules, generics, structs, and stdlib usage.

## Golden outputs

Every example has a corresponding `test/fixtures/golden_outputs/<name>.out`
file. The E2E script runs the compiled binary and diffs stdout against this
file; any drift fails CI. Add or update golden outputs when you change
example behaviour.

## Adding an example

1. Write `examples/0XX_name.a7` (use the next free number).
2. Run it locally: `uv run a7 examples/0XX_name.a7 && zig build-exe -O ReleaseFast examples/0XX_name.zig && ./0XX_name`.
3. Capture stdout to `test/fixtures/golden_outputs/0XX_name.out`.
4. `uv run python scripts/verify_examples_e2e.py` must pass.
5. Update [Status](/a7-py/compiler/status) if the example exercises a
   feature that wasn't previously covered.
