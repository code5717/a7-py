---
title: Examples
nav: Examples
group: Getting started
summary: Browse every checked-in A7 example with source, commands, output fixtures, and related reference topics.
order: 3
---

# Examples

Every row links a complete checked-in A7 source and its expected stdout fixture.
Run commands from the repository root after [installation](/a7-py/docs/start.md).
The fixture is expected output, not a claim that a new checkout has passed.
The verifier compiles A7, checks generated Zig, builds and runs it, then compares
stdout to that fixture.

## Run an example

```bash
uv run a7 examples/001_hello.a7
zig run examples/001_hello.zig
```

Substitute any source stem below. The table also gives its exact command pair.
An empty fixture means the program has no expected stdout. Compiler diagnostics
are separate from the program output. Topic labels link to the language reference.

## Example index

| Source | Topic | Commands | Expected output |
| --- | --- | --- | --- |
| [000_empty.a7](https://github.com/code5717/a7-py/blob/master/examples/000_empty.a7) | [syntax](/a7-py/docs/language/syntax.md) | `uv run a7 examples/000_empty.a7` then `zig run examples/000_empty.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/000_empty.out) |
| [001_hello.a7](https://github.com/code5717/a7-py/blob/master/examples/001_hello.a7) | [syntax](/a7-py/docs/language/syntax.md) | `uv run a7 examples/001_hello.a7` then `zig run examples/001_hello.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/001_hello.out) |
| [002_var.a7](https://github.com/code5717/a7-py/blob/master/examples/002_var.a7) | [declarations](/a7-py/docs/language/declarations.md) | `uv run a7 examples/002_var.a7` then `zig run examples/002_var.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/002_var.out) |
| [003_comments.a7](https://github.com/code5717/a7-py/blob/master/examples/003_comments.a7) | [syntax](/a7-py/docs/language/syntax.md) | `uv run a7 examples/003_comments.a7` then `zig run examples/003_comments.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/003_comments.out) |
| [004_func.a7](https://github.com/code5717/a7-py/blob/master/examples/004_func.a7) | [functions](/a7-py/docs/language/functions.md) | `uv run a7 examples/004_func.a7` then `zig run examples/004_func.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/004_func.out) |
| [005_for_loop.a7](https://github.com/code5717/a7-py/blob/master/examples/005_for_loop.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/005_for_loop.a7` then `zig run examples/005_for_loop.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/005_for_loop.out) |
| [006_if.a7](https://github.com/code5717/a7-py/blob/master/examples/006_if.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/006_if.a7` then `zig run examples/006_if.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/006_if.out) |
| [007_while.a7](https://github.com/code5717/a7-py/blob/master/examples/007_while.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/007_while.a7` then `zig run examples/007_while.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/007_while.out) |
| [008_switch.a7](https://github.com/code5717/a7-py/blob/master/examples/008_switch.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/008_switch.a7` then `zig run examples/008_switch.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/008_switch.out) |
| [009_struct.a7](https://github.com/code5717/a7-py/blob/master/examples/009_struct.a7) | [aggregate types](/a7-py/docs/language/aggregate-types.md) | `uv run a7 examples/009_struct.a7` then `zig run examples/009_struct.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/009_struct.out) |
| [010_enum.a7](https://github.com/code5717/a7-py/blob/master/examples/010_enum.a7) | [aggregate types](/a7-py/docs/language/aggregate-types.md) | `uv run a7 examples/010_enum.a7` then `zig run examples/010_enum.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/010_enum.out) |
| [011_memory.a7](https://github.com/code5717/a7-py/blob/master/examples/011_memory.a7) | [memory](/a7-py/docs/language/memory.md) | `uv run a7 examples/011_memory.a7` then `zig run examples/011_memory.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/011_memory.out) |
| [012_arrays.a7](https://github.com/code5717/a7-py/blob/master/examples/012_arrays.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/012_arrays.a7` then `zig run examples/012_arrays.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/012_arrays.out) |
| [013_pointers.a7](https://github.com/code5717/a7-py/blob/master/examples/013_pointers.a7) | [memory](/a7-py/docs/language/memory.md) | `uv run a7 examples/013_pointers.a7` then `zig run examples/013_pointers.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/013_pointers.out) |
| [014_generics.a7](https://github.com/code5717/a7-py/blob/master/examples/014_generics.a7) | [generics](/a7-py/docs/language/generics.md) | `uv run a7 examples/014_generics.a7` then `zig run examples/014_generics.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/014_generics.out) |
| [015_types.a7](https://github.com/code5717/a7-py/blob/master/examples/015_types.a7) | [types](/a7-py/docs/language/types.md) | `uv run a7 examples/015_types.a7` then `zig run examples/015_types.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/015_types.out) |
| [016_unions.a7](https://github.com/code5717/a7-py/blob/master/examples/016_unions.a7) | [aggregate types](/a7-py/docs/language/aggregate-types.md) | `uv run a7 examples/016_unions.a7` then `zig run examples/016_unions.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/016_unions.out) |
| [017_methods.a7](https://github.com/code5717/a7-py/blob/master/examples/017_methods.a7) | [functions](/a7-py/docs/language/functions.md) | `uv run a7 examples/017_methods.a7` then `zig run examples/017_methods.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/017_methods.out) |
| [018_modules.a7](https://github.com/code5717/a7-py/blob/master/examples/018_modules.a7) | [modules](/a7-py/docs/language/modules.md) | `uv run a7 examples/018_modules.a7` then `zig run examples/018_modules.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/018_modules.out) |
| [019_literals.a7](https://github.com/code5717/a7-py/blob/master/examples/019_literals.a7) | [syntax](/a7-py/docs/language/syntax.md) | `uv run a7 examples/019_literals.a7` then `zig run examples/019_literals.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/019_literals.out) |
| [020_operators.a7](https://github.com/code5717/a7-py/blob/master/examples/020_operators.a7) | [operators](/a7-py/docs/language/operators.md) | `uv run a7 examples/020_operators.a7` then `zig run examples/020_operators.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/020_operators.out) |
| [021_control_flow.a7](https://github.com/code5717/a7-py/blob/master/examples/021_control_flow.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/021_control_flow.a7` then `zig run examples/021_control_flow.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/021_control_flow.out) |
| [022_function_pointers.a7](https://github.com/code5717/a7-py/blob/master/examples/022_function_pointers.a7) | [functions](/a7-py/docs/language/functions.md) | `uv run a7 examples/022_function_pointers.a7` then `zig run examples/022_function_pointers.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/022_function_pointers.out) |
| [023_inline_structs.a7](https://github.com/code5717/a7-py/blob/master/examples/023_inline_structs.a7) | [aggregate types](/a7-py/docs/language/aggregate-types.md) | `uv run a7 examples/023_inline_structs.a7` then `zig run examples/023_inline_structs.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/023_inline_structs.out) |
| [024_defer.a7](https://github.com/code5717/a7-py/blob/master/examples/024_defer.a7) | [memory](/a7-py/docs/language/memory.md) | `uv run a7 examples/024_defer.a7` then `zig run examples/024_defer.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/024_defer.out) |
| [025_linked_list.a7](https://github.com/code5717/a7-py/blob/master/examples/025_linked_list.a7) | [memory](/a7-py/docs/language/memory.md) | `uv run a7 examples/025_linked_list.a7` then `zig run examples/025_linked_list.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/025_linked_list.out) |
| [026_binary_tree.a7](https://github.com/code5717/a7-py/blob/master/examples/026_binary_tree.a7) | [memory](/a7-py/docs/language/memory.md) | `uv run a7 examples/026_binary_tree.a7` then `zig run examples/026_binary_tree.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/026_binary_tree.out) |
| [027_callbacks.a7](https://github.com/code5717/a7-py/blob/master/examples/027_callbacks.a7) | [functions](/a7-py/docs/language/functions.md) | `uv run a7 examples/027_callbacks.a7` then `zig run examples/027_callbacks.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/027_callbacks.out) |
| [028_state_machine.a7](https://github.com/code5717/a7-py/blob/master/examples/028_state_machine.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/028_state_machine.a7` then `zig run examples/028_state_machine.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/028_state_machine.out) |
| [029_sorting.a7](https://github.com/code5717/a7-py/blob/master/examples/029_sorting.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/029_sorting.a7` then `zig run examples/029_sorting.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/029_sorting.out) |
| [030_calculator.a7](https://github.com/code5717/a7-py/blob/master/examples/030_calculator.a7) | [operators](/a7-py/docs/language/operators.md) | `uv run a7 examples/030_calculator.a7` then `zig run examples/030_calculator.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/030_calculator.out) |
| [031_number_guessing.a7](https://github.com/code5717/a7-py/blob/master/examples/031_number_guessing.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/031_number_guessing.a7` then `zig run examples/031_number_guessing.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/031_number_guessing.out) |
| [032_prime_numbers.a7](https://github.com/code5717/a7-py/blob/master/examples/032_prime_numbers.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/032_prime_numbers.a7` then `zig run examples/032_prime_numbers.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/032_prime_numbers.out) |
| [033_fibonacci.a7](https://github.com/code5717/a7-py/blob/master/examples/033_fibonacci.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/033_fibonacci.a7` then `zig run examples/033_fibonacci.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/033_fibonacci.out) |
| [034_string_utils.a7](https://github.com/code5717/a7-py/blob/master/examples/034_string_utils.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/034_string_utils.a7` then `zig run examples/034_string_utils.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/034_string_utils.out) |
| [035_matrix.a7](https://github.com/code5717/a7-py/blob/master/examples/035_matrix.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/035_matrix.a7` then `zig run examples/035_matrix.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/035_matrix.out) |
| [036_control_flow_edges.a7](https://github.com/code5717/a7-py/blob/master/examples/036_control_flow_edges.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/036_control_flow_edges.a7` then `zig run examples/036_control_flow_edges.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/036_control_flow_edges.out) |
| [037_language_tour.a7](https://github.com/code5717/a7-py/blob/master/examples/037_language_tour.a7) | [declarations](/a7-py/docs/language/declarations.md) | `uv run a7 examples/037_language_tour.a7` then `zig run examples/037_language_tour.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/037_language_tour.out) |
| [038_inventory_report.a7](https://github.com/code5717/a7-py/blob/master/examples/038_inventory_report.a7) | [aggregate types](/a7-py/docs/language/aggregate-types.md) | `uv run a7 examples/038_inventory_report.a7` then `zig run examples/038_inventory_report.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/038_inventory_report.out) |
| [039_text_analyzer.a7](https://github.com/code5717/a7-py/blob/master/examples/039_text_analyzer.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/039_text_analyzer.a7` then `zig run examples/039_text_analyzer.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/039_text_analyzer.out) |
| [040_task_board.a7](https://github.com/code5717/a7-py/blob/master/examples/040_task_board.a7) | [aggregate types](/a7-py/docs/language/aggregate-types.md) | `uv run a7 examples/040_task_board.a7` then `zig run examples/040_task_board.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/040_task_board.out) |
| [041_route_simulation.a7](https://github.com/code5717/a7-py/blob/master/examples/041_route_simulation.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/041_route_simulation.a7` then `zig run examples/041_route_simulation.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/041_route_simulation.out) |
| [042_gradebook.a7](https://github.com/code5717/a7-py/blob/master/examples/042_gradebook.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/042_gradebook.a7` then `zig run examples/042_gradebook.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/042_gradebook.out) |
| [043_math_library.a7](https://github.com/code5717/a7-py/blob/master/examples/043_math_library.a7) | [stdlib](/a7-py/docs/language/stdlib.md) | `uv run a7 examples/043_math_library.a7` then `zig run examples/043_math_library.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/043_math_library.out) |
| [044_indexing_rules.a7](https://github.com/code5717/a7-py/blob/master/examples/044_indexing_rules.a7) | [arrays strings](/a7-py/docs/language/arrays-strings.md) | `uv run a7 examples/044_indexing_rules.a7` then `zig run examples/044_indexing_rules.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/044_indexing_rules.out) |
| [045_formatting.a7](https://github.com/code5717/a7-py/blob/master/examples/045_formatting.a7) | [stdlib](/a7-py/docs/language/stdlib.md) | `uv run a7 examples/045_formatting.a7` then `zig run examples/045_formatting.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/045_formatting.out) |
| [046_match_full.a7](https://github.com/code5717/a7-py/blob/master/examples/046_match_full.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/046_match_full.a7` then `zig run examples/046_match_full.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/046_match_full.out) |
| [047_safety_obligations.a7](https://github.com/code5717/a7-py/blob/master/examples/047_safety_obligations.a7) | [safety](/a7-py/docs/language/safety.md) | `uv run a7 examples/047_safety_obligations.a7` then `zig run examples/047_safety_obligations.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/047_safety_obligations.out) |
| [048_worklist_traversal.a7](https://github.com/code5717/a7-py/blob/master/examples/048_worklist_traversal.a7) | [control flow](/a7-py/docs/language/control-flow.md) | `uv run a7 examples/048_worklist_traversal.a7` then `zig run examples/048_worklist_traversal.zig` | [fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/048_worklist_traversal.out) |

## Programs that are rejected on purpose

Everything above has to compile, build, run and match its fixture. The other
side of the contract lives in `examples/rejected/`, where each file is paired
with the diagnostic it must produce in `examples/rejected/manifest.json`, and
`test/test_rejected_examples.py` runs them. They cover source recursion
(self and mutual), a divisor a `ref` parameter can change, `new [N]T`, an
`i32` subscript, and a call to a stdlib function that does not exist.

```bash
uv run pytest test/test_rejected_examples.py
```

## Choose a learning path

Use `001_hello` for setup, `037_language_tour` for a guided overview, and
`014_generics` for direct generic calls and generic structs. The linked list and
binary tree examples use iterative algorithms because source recursion is banned.
The later inventory, text analyzer, task board, route simulation, and gradebook
examples combine several language facilities into small programs.

## Verify the suite

```bash
uv run python scripts/verify_examples_e2e.py
```

For machine-readable evidence:

```bash
uv run python scripts/verify_examples_e2e.py --json-report /tmp/a7-examples.json
```

Read `ok`, `passed`, `total`, and each result rather than treating the existence
of a report as success. The debug and release builders perform further native
checks listed on [Release](/a7-py/docs/release.md). Current counts come from
`uv run python scripts/project_status.py`; do not infer them from an old report.
