# Error catalog

Every compiler diagnostic: code, stage, exit code, span, trigger, fix.
Counts: 22 tokenizer + 34 semantic + 31 type = 87 enum codes, plus ad-hoc
`ParseError`, `CodegenError`, `ImportError`, entry-point, and internal rows.
Exits live in `a7/compile.py` (`ExitCode`); messages and hints in `a7/errors.py`.

| Stage | Exit | Category |
| --- | --- | --- |
| tokenize | 4 | lexer failure |
| parse | 5 | syntax failure |
| semantic | 6 | name, type, safety, import, entry-point failure |
| codegen | 7 | backend failure (incl. unknown backend) |
| io | 3 | missing input, output conflict, doc-write failure |
| usage | 2 | bad CLI flags (`--output` outside compile mode) |
| internal | 8 | unexpected exception (bug) |

JSON shape key: `D1` = detail with span
(`{type, message, file, span:{start_line, start_column, end_line,
end_column, length}}`); `D0` = same without span. The envelope is
`{category, message, details:[D1|D0], span, exception_type}`.
Pin key: `matrix` = test_error_stage_matrix, `exits` = test_stage_exit_codes,
`tok` = test_tokenizer, `sem` = test_semantic_errors, `pedge` =
test_parser_error_handling_improvements, `mmod` = test_multi_file_modules,
`pins` = test_error_catalog_pins.

## Tokenizer (stage tokenize, exit 4, span yes, D1)

| Code | Trigger → fix | Pin |
| --- | --- | --- |
| out_of_memory | resource exhaustion → free memory, retry | — |
| invalid_character | stray char (e.g. `@`) → remove it | tok |
| too_long_identifier | name over 100 chars → shorten it | tok |
| too_long_number | digits over 100 → shorten it | tok |
| too_long_string | oversize literal → shorten it | tok |
| not_closed_char | `'a` → close with `'` on the same line | tok |
| not_closed_string | `"abc` → close with `"` | matrix, tok |
| end_of_file | truncated input → add the missing closing token | tok |
| file_empty | zero-byte file → add code or drop the file | tok |
| bad_token_at_global | statement outside any function → move it inside one | tok |
| tabs_unsupported | tab indent → convert tabs to spaces | tok |
| invalid_escape_char | bad `\x` → use `n t r 0 \ ' "` or `\xHH` | tok |
| not_closed_comment | unterminated `/*` → close with `*/` | tok |
| invalid_number | bad digit separators → one `_` between digits at most | tok |
| invalid_scientific_notation | `1e` → add digits after the exponent | tok |
| invalid_hex_number | bad `0x` digits → use 0-9, a-f, A-F | tok |
| invalid_binary_number | bad `0b` digits → use 0, 1 | tok |
| invalid_octal_number | bad `0o` digits → use 0-7 | tok |
| invalid_generic_syntax | `$1T` → letter after `$`, then letters/digits/`_` | tok |
| unsupported | no backend support → rewrite without the construct | — |
| unknown | should not happen → report it | — |

## Semantic (stage semantic, exit 6, span yes except noted, D1)

| Code | Trigger → fix | Pin |
| --- | --- | --- |
| undefined_identifier | `y` never declared → fix spelling, declare first | sem |
| already_defined | name declared twice → rename or drop one | sem |
| duplicate_parameter | `fn(a: i32, a: i32)` → unique names | — |
| duplicate_field | struct field twice → unique names | — |
| duplicate_variant | enum variant twice → unique names | — |
| duplicate_generic_param | `$T` listed twice → unique names | — |
| break_outside_loop | `break` in plain block → move into a loop | sem |
| break_undefined_label | `break 'nope` → label an enclosing loop | — |
| continue_outside_loop | `continue` in plain block → move into a loop | sem |
| continue_undefined_label | `continue 'nope` → label an enclosing loop | — |
| return_outside_function | `return` at top level → move into a function | sem |
| defer_outside_function | `defer` at top level → move into a function | sem |
| unreachable_code | code after `ret` → delete it | — |
| missing_return | paths without `ret` → return on every path | — |
| cannot_assign_to_immutable | `x = 1` on `::` binding → declare with `:=` | sem |
| invalid_defer_scope | misplaced `defer` → put it in its function body | — |
| memory_leak | allocated value escapes scope → free it first | — |
| double_free | `del` twice → delete once | — |
| delete_non_reference | `del 1` → delete reference values only | sem |
| nil_not_reference_type | `nil` for plain `i32` → use it for `ref` types | sem |
| missing_type_annotation | bare `x;` → add a type or initializer | — |
| non_exhaustive_match | missing case → add cases or an `else` branch | — |
| invalid_pattern | bad match pattern → use a supported pattern form | — |
| unsupported_fallthrough | misplaced `fall` → last statement of a non-final case | — |
| recursion_not_allowed | `f` calls `f` → rewrite with loops or a stack | exits |
| circular_import | `a` imports `b` imports `a` → extract a third module | pins |
| module_not_found | `import "nosuch"` → fix the path or search path (live CLI path raises ImportError, exit 3; see ad-hoc rows) | — |
| import_name_conflict | import shadows a name → alias the import | — |
| unsupported_import | exotic import form → use a virtual stdlib import | — |
| generic_param_mismatch | wrong `$T` count → match the declared count | — |
| constraint_violation | type misses the bound → use a conforming type | — |
| unsupported_feature | parsed but not runnable → rewrite without it | — |
| unexpected_node_kind | compiler bug → report it | — |
| unknown | compiler bug → report it | — |

## Type check (stage semantic, exit 6, span yes, D1)

| Code | Trigger → fix | Pin |
| --- | --- | --- |
| type_mismatch | `x: i32 = "s"` → match types or cast | matrix, sem |
| return_type_mismatch | `ret "s"` in `fn() i32` → return the declared type | sem |
| assignment_type_mismatch | wrong value type → assign the declared type | sem |
| condition_not_bool | `if 1` → use a `bool` condition | — |
| if_expr_type_mismatch | branches differ → unify both branch types | — |
| requires_numeric_type | string in arithmetic → use a numeric type | sem |
| requires_integer_type | float where int needed → use an integer type | — |
| requires_bool_type | non-bool logic operand → use `true`/`false` | — |
| requires_array_or_slice | scalar indexed or iterated → use array/slice | — |
| requires_struct_type | field access needs struct → use a struct value | sem |
| requires_pointer_type | deref of plain value → use a `ref` value | sem |
| requires_function_type | non-function in call position → use a function | — |
| not_callable | `x()` where `x` is data → call a function | sem |
| wrong_argument_count | arity differs → pass the declared count | — |
| argument_type_mismatch | arg type differs → match parameter types | sem |
| no_such_field | `p.nope` → fix spelling or add the field | sem |
| field_access_on_non_struct | `.x` on `i32` → use a struct value | sem |
| cannot_index_type | index into scalar → index arrays/slices only | sem |
| index_not_integer | `a["k"]` → index with a `usize` value | — |
| cannot_dereference | deref of non-`ref` → use a proven reference | sem |
| address_of_rvalue | address of temporary → use a variable or field | — |
| use_after_move | read after `del` → assign before re-reading | — |
| nil_not_allowed | `nil` for non-nilable → provide a value | — |
| nil_only_for_references | `nil` for plain type → use a `ref` type | — |
| missing_type_or_initializer | bare `x;` → add a type or initializer | — |
| undefined_type | `x: Nope` → fix spelling or import the type | — |
| incompatible_types | operands clash → cast one side explicitly | — |
| invalid_cast | uncastable pair → change the approach | — |
| unsafe_cast | lossy cast → narrow the source type first | — |
| operator_type_mismatch | `1 + "s"` → use compatible operand types | sem |
| unknown_type | type cannot be inferred → annotate it | — |

## Ad-hoc rows (no enum code)

| Code | Stage:exit | Span | Trigger → fix | Pin |
| --- | --- | --- | --- | --- |
| ParseError | parse:5 | yes, D1 | `fn( {` → complete the syntax at the span | matrix, pedge, pins |
| CodegenError array-binary (6 forms) | codegen:7 | yes, D1 | array op without fixed arrays → use fixed-size arrays | — |
| CodegenError type-emission (7 forms) | codegen:7 | yes except missing node/leaf, D1/D0 | unresolvable/generic-less type → give env or concrete type | — |
| CodegenError approval (cast, safety) | codegen:7 | yes, D1 | unapproved op → pass semantic/safety first | — |
| CodegenError misc (unhandled node, io-as-expr, bad operator) | codegen:7 | mostly yes, D1 | unsupported construct → rewrite without it | — |
| unknown backend | codegen:7 | no, D0 | `--backend nope` → use a supported backend | matrix |
| ImportError (missing/unreadable module) | io:3 | import decl span, D1 | bad path → fix path or search path | pins, mmod |
| circular module graph | semantic:6 | import decl span, D1 | import cycle → extract a third module | pins |
| no entry point | semantic:6 | no, D0 | file has no `main` → add one or pass `--lib` | — |
| internal exception | internal:8 | no, D0 | compiler bug → report with input | matrix |
