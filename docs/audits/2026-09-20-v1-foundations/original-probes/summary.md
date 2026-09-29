# Original compiler finding revalidation

Only compiler, AST, semantic and token commands ran. No Zig build or compiled program execution. All 32 compiler Python file hashes stayed unchanged across this run. Exact commands, source text, full stdout/stderr and emitted Zig are in `results.json`; copied dependency sources and `input-sha256.json` preserve the import corpus.

45 final compiler invocations returned valid JSON. No timeout fired. Every failed compile wrote no Zig output. Six direct token-column assertion groups passed.

An initial invocation attempt passed `--output` to non-compile modes, which correctly returned usage exit 2. `initial-invocation-results.json` preserves those errors. Final results rerun the modes without that unsupported flag.

| ID | Disposition | Evidence and limits |
| --- | --- | --- |
| PAR-02 | reproduced, failure containment improved | Six original long-condition/inline-struct shapes reject with exit 5; the short-condition control compiles. None hangs or emits partial Zig. The struct-literal context defect remains; silent dropping is repaired in these forms. |
| PAR-03 | original selected recovery failures no longer reproduce | All eight selected original recovery/declaration cases reject with exit 5 and no Zig artifact. Typed/untyped local promotion and silent function loss do not reproduce. Valid function-type declarations still reject, which is a separate parsing limitation; no claim of full parser support. |
| PAR-05 | verified fixed for both original JSON reproductions | Both original match-expression else probes produce valid JSON and exit 0 in compile, AST and semantic modes, six checks total. Duplicate else acceptance in p12b is unchanged and is not approved by this result. No native behavior checked. |
| TOK-03 | partially fixed; lexical contract decision remains | All eight original malformed separator cases and superscript digit reject with exit 4, not internal exit 8. Original 0x_1, Arabic decimal 1٣ and fullwidth float 1.５ still compile. Accepted spelling policy remains a decision; do not mark all TOK-03 closed. |
| TOK-04 | verified fixed for original reported column shapes | Original two fixtures plus six verbatim snippets give correct operator/newline/brace columns. Explicit assertions cover + at 3, newline at 6, braces at 1, <<= at 3, .. at 2, and leading operators at 1. Closing-brace token now has column 1; the compile fails earlier at the missing-parenthesis newline, line 5 column 12. No full source-map guarantee. |
| PIP-10 | cycle fixed; deep recursion failure reproduced | Original cyclic fixtures reject with exit 6. Original 1100-file import chain still exits 8 with RecursionError. This finding remains open for iterative loading and the depth contract. |

## Individual results

| ID | Probe/mode | Exit | Diagnostic |
| --- | --- | --- | --- |
| PAR-02 | p03_long_if_condition_ident_before_brace-compile | 5 | input.a7:13:6: Expected expression |
| PAR-02 | p03b_short_if_condition_control-compile | 0 |  |
| PAR-02 | q03_while_long_condition-compile | 5 | input.a7:9:11: Expected RIGHT_BRACE, got PLUS_ASSIGN |
| PAR-02 | p04_struct_lit_in_if_expr-compile | 5 | input.a7:10:19: Expected RIGHT_BRACE, got LEFT_BRACE |
| PAR-02 | p05_struct_lit_in_match_expr_arm-compile | 5 | input.a7:12:17: Expected 'case' or 'else' in match expression |
| PAR-02 | q04_ret_struct_single_line_if-compile | 5 | input.a7:9:22: Expected type |
| PAR-02 | q05_match_stmt_else_ret_struct-compile | 5 | input.a7:11:21: Expected 'case' or 'else' in match statement |
| PAR-03 | q01_broken_body_typed_local_leak-compile | 5 | input.a7:5:9: Expected expression |
| PAR-03 | p13_broken_body_locals_leak-compile | 5 | input.a7:5:9: Expected expression |
| PAR-03 | q10_destructuring_decl-compile | 5 | input.a7:5:6: Expected expression |
| PAR-03 | q20_new_with_args-compile | 5 | input.a7:9:17: Expected type |
| PAR-03 | p15b_struct_fn_field_single_line-compile | 5 | input.a7:3:24: Expected type |
| PAR-03 | q19_fn_alias_at_eof_no_newline-compile | 5 | input.a7:6:17: Expected type |
| PAR-03 | p18_using_import_after_decls-compile | 5 | input.a7:5:1: Expected declaration (constant, variable, or function) |
| PAR-03 | p15_fn_type_return_void_fn-compile | 5 | input.a7:8:18: Expected type |
| PAR-05 | p05b_match_expr_else_int_json-compile | 0 |  |
| PAR-05 | p05b_match_expr_else_int_json-ast | 0 |  |
| PAR-05 | p05b_match_expr_else_int_json-semantic | 0 |  |
| PAR-05 | p12b_match_expr_two_else-compile | 0 |  |
| PAR-05 | p12b_match_expr_two_else-ast | 0 |  |
| PAR-05 | p12b_match_expr_two_else-semantic | 0 |  |
| TOK-03 | tok04_0_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '1_' |
| TOK-03 | tok04_1_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '1__0' |
| TOK-03 | tok04_2_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '0x1_' |
| TOK-03 | tok04_3_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '0x__1' |
| TOK-03 | tok04_4_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '1_e5' |
| TOK-03 | tok04_5_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '1._5' |
| TOK-03 | tok04_6_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '1.5_' |
| TOK-03 | tok04_7_underscore-compile | 4 | input.a7:5:10: Invalid numeric literal '1e1_' |
| TOK-03 | tok04_8_underscore-compile | 0 |  |
| TOK-03 | tok05a_superscript-compile | 4 | input.a7:5:10: Invalid numeric literal '²' |
| TOK-03 | tok05b_arabic-compile | 0 |  |
| TOK-03 | tok05c_fullwidth_float-compile | 0 |  |
| TOK-04 | tok06_op_column-compile | 5 | input.a7:5:13: Expected expression after '+' operator |
| TOK-04 | tok06_op_column-tokens | 0 |  |
| TOK-04 | tok06b_close_brace_col-compile | 5 | input.a7:5:12: Expected RIGHT_PAREN, got TERMINATOR |
| TOK-04 | tok06b_close_brace_col-tokens | 0 |  |
| TOK-04 | direct-plus | 0 |  |
| TOK-04 | direct-braces | 0 |  |
| TOK-04 | direct-shift | 0 |  |
| TOK-04 | direct-range | 0 |  |
| TOK-04 | direct-negative_col_shift | 0 |  |
| TOK-04 | direct-negative_col_assign | 0 |  |
| PIP-10 | m10_cycle-compile | 6 | Semantic analysis failed with 1 error(s) |
| PIP-10 | chain1100-compile | 8 | maximum recursion depth exceeded |

## Reproduction commands

Each case directory contains `input.a7`; module cases include their dependencies. These commands compile only.

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p03_long_if_condition_ident_before_brace-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p03_long_if_condition_ident_before_brace-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p03b_short_if_condition_control-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p03b_short_if_condition_control-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q03_while_long_condition-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q03_while_long_condition-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p04_struct_lit_in_if_expr-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p04_struct_lit_in_if_expr-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p05_struct_lit_in_match_expr_arm-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p05_struct_lit_in_match_expr_arm-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q04_ret_struct_single_line_if-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q04_ret_struct_single_line_if-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q05_match_stmt_else_ret_struct-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q05_match_stmt_else_ret_struct-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q01_broken_body_typed_local_leak-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q01_broken_body_typed_local_leak-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p13_broken_body_locals_leak-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p13_broken_body_locals_leak-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q10_destructuring_decl-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q10_destructuring_decl-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q20_new_with_args-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q20_new_with_args-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p15b_struct_fn_field_single_line-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p15b_struct_fn_field_single_line-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q19_fn_alias_at_eof_no_newline-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/q19_fn_alias_at_eof_no_newline-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p18_using_import_after_decls-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p18_using_import_after_decls-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p15_fn_type_return_void_fn-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p15_fn_type_return_void_fn-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p05b_match_expr_else_int_json-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p05b_match_expr_else_int_json-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p05b_match_expr_else_int_json-ast/input.a7 --mode ast --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p05b_match_expr_else_int_json-semantic/input.a7 --mode semantic --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p12b_match_expr_two_else-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p12b_match_expr_two_else-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p12b_match_expr_two_else-ast/input.a7 --mode ast --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/p12b_match_expr_two_else-semantic/input.a7 --mode semantic --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_0_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_0_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_1_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_1_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_2_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_2_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_3_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_3_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_4_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_4_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_5_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_5_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_6_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_6_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_7_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_7_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_8_underscore-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok04_8_underscore-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok05a_superscript-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok05a_superscript-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok05b_arabic-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok05b_arabic-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok05c_fullwidth_float-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok05c_fullwidth_float-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok06_op_column-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok06_op_column-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok06_op_column-tokens/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok06b_close_brace_col-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok06b_close_brace_col-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/tok06b_close_brace_col-tokens/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/direct-plus/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/direct-braces/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/direct-shift/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/direct-range/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/direct-negative_col_shift/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/direct-negative_col_assign/input.a7 --mode tokens --format json
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/m10_cycle-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/m10_cycle-compile/output.zig
```

```bash
/home/cx89/Projects/pl-dev/a7-py/.venv/bin/python /home/cx89/Projects/pl-dev/a7-py/main.py /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/chain1100-compile/input.a7 --mode compile --format json --output /home/cx89/Projects/pl-dev/a7-py/tmp/v1-delivery-2026-09-20/original-probes/chain1100-compile/output.zig
```
