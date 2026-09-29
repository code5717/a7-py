> **Source:** Claude audit subagent, full audit of the A7 compiler component `parser`, run against commit `701c679` with Zig 0.16.0; shared instructions in `tmp/audit/compiler/PROMPT-COMMON.md`.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim. Probes and logs it cites stay under `tmp/audit/compiler/parser/`, which is not tracked.

# Audit: parser and AST (component prefix PAR)

Auditor scope: `a7/parser.py` (2300 lines), `a7/ast_nodes.py` (641), the `--mode ast` path (`a7/cli.py`, `a7/compile.py:186-215, 506-556, 731-793`), `a7/formatters/{json,console,markdown}_formatter.py`, and the 16 `test/test_parser*.py` files. All files were read in full. No repository file was edited.

Method and artifacts (all under `tmp/audit/compiler/parser/`):

- `run_probe.sh <probe>` runs `MISE_UV_VERSION=0.12.6 uv run a7 probes/<probe>.a7 --format json --output out/<probe>.json.zig`, then the same in human format. If human mode exits 0, it runs `zig build-obj -fno-emit-bin`. For `run-allowed` probes it then runs `zig build-exe -O Debug|ReleaseFast` and executes the binary with output piped through `cat` (see side observation S1).
- Results are in `out/<probe>.summary` and the matching `.stdout`, `.stderr`, `.exit`, `.zig` and `.buildobj` files. `batch1_summaries.txt` and `batch2_summaries.txt` collect them.
- `run_modes.sh` runs `--mode ast` and `--mode compile` in human and JSON formats (`out/modes/`, collected in `deep_cli.txt`).
- In-process scripts, all run with the default recursion limit of 1000:
  - `depth.py` measures nesting depth limits (`depth.log`).
  - `inproc.py` and `inproc2.py` check spans, precedence shapes, ASTNode equality and miscellaneous behavior (`inproc.log`, `inproc2.log`).
  - `attrs_dynamic.py` records undeclared ASTNode attributes and field references (`attrs.log`).
  - `recover_trace.py` logs every ParseError that the top-level loop swallows (`recover_trace.log`).
- Test-quality review: a forked reader went through all 16 parser test files. I spot-checked its claims at `test_parser_fuzzing.py:486-497`, `test_parser_creative_cases.py` (31 of 31 tests check only `PROGRAM`), `test_parser_advanced_edge_cases.py:130-145`, `test_parser_integration.py:366, 415, 461, 493, 527` and `test_parser_error_handling_improvements.py:483-496`.

Known-defect references use the IDs from `docs/plan/README.md` ("Defects reproduced in Wave 0" and the lists above it) and `docs/plan/audit/evidence/2026-09-16-ledger-part{1,2}.md`.

## Summary

| Severity | Total | NEW | KNOWN |
| --- | --- | --- | --- |
| CRITICAL | 1 | 1 | 0 |
| HIGH | 4 | 2 | 2 (F2/C5, F5) |
| MEDIUM | 12 | 11 | 1 (F3/F4) |
| LOW | 8 | 8 | 0 |
| **Total** | **25** | **22** | **3** |

Several NEW findings are new root causes behind KNOWN symptoms:

- PAR-02 and PAR-13 are new triggers for F2's silent declaration drop.
- PAR-04 is the parser-side cause of D7's "diagnostic has no line", and it is more general than D7.
- PAR-05 shows that F5 is not specific to structs.

| ID | Sev | Status | Title |
| --- | --- | --- | --- |
| PAR-01 | CRITICAL | NEW | `match` statement loops forever on any token other than `case`, `else` or `}` |
| PAR-02 | HIGH | NEW | The struct-literal lookback heuristic hangs, rejects or silently drops valid code |
| PAR-03 | HIGH | KNOWN F2/C5 (new manifestations) | Top-level recovery drops declarations and turns a broken body's locals into globals |
| PAR-04 | HIGH | NEW (root cause of D7 "no line") | BINARY nodes have no span, so binary type errors and every divisor diagnostic lack a location |
| PAR-05 | HIGH | KNOWN F5 (broader) | JSON output crashes on any match expression with an `else` arm |
| PAR-06 | MEDIUM | NEW | Multi-line array literals and positional struct literals are rejected or dropped |
| PAR-07 | MEDIUM | NEW | A string literal containing Rich markup crashes `--mode ast`, `--mode tokens` and `-v` (exit 8) |
| PAR-08 | MEDIUM | NEW | Recursion depth limits give exit 8 "internal" errors with no location |
| PAR-09 | MEDIUM | NEW | A bare `except:` swallows struct-literal parse errors and reparses the input as a call plus a block |
| PAR-10 | MEDIUM | NEW | Duplicate `else` arms in `match` are silently discarded |
| PAR-11 | MEDIUM | NEW | Assignment targets are not restricted: `1 = 2` compiles with exit 0 and Zig rejects it |
| PAR-12 | MEDIUM | NEW | `$T` in expression position becomes the plain identifier `T` |
| PAR-13 | MEDIUM | NEW | A function type's return-type stop set lacks `{`, `}` and EOF, so valid declarations are dropped or rejected |
| PAR-14 | MEDIUM | NEW (partly KNOWN, Lane F cross-cutting) | Parse diagnostics: no source excerpt at 23 of 28 sites, and misleading messages |
| PAR-15 | MEDIUM | NEW | ASTNode design: inconsistent shapes, undeclared attributes, dead fields, recursive `__eq__` and `__repr__` |
| PAR-16 | MEDIUM | NEW | JSON AST output is quadratic in nesting (256 MB for a 15 KB source) and loses inline struct types |
| PAR-17 | MEDIUM | KNOWN F3/F4 | 1000-iteration cap; warning printed to stdout |
| PAR-18 | LOW | NEW | `using import` cannot parse; the code path is dead, and `using` is silently stripped after one or more declarations |
| PAR-19 | LOW | NEW | Missing separators are accepted: type arguments, fields, variants, statements, `;;` |
| PAR-20 | LOW | NEW | `if`/`while` bodies without a block are accepted; `defer` accepts `ret`, `break` and nested `defer` |
| PAR-21 | LOW | NEW | A type in value position (`x := struct {...}`) yields a "compiler bug" diagnostic |
| PAR-22 | LOW | NEW (one item KNOWN C5) | SPEC grammar and examples diverge from the parser |
| PAR-23 | LOW | NEW | Console and markdown AST views omit loop, defer and match bodies, and print `[None]i32` |
| PAR-24 | LOW | NEW | Minor robustness issues: recovery keyed on message text including the filename, `Parser([])`, `pub import`, `union()` |
| PAR-25 | LOW | NEW | Dead code and unused state in the parser |

---

## CRITICAL

### PAR-01 (CRITICAL, NEW): `match` statement parsing never terminates on an unexpected token

**What is wrong.** Inside `match ... { }`, `parse_match_statement` handles only `case` and `else`. For any other token it calls `skip_terminators()`, which does nothing, and loops forever. The compiler hangs in every mode that parses (`ast`, `semantic`, `pipeline`, `compile`, `doc`). The 1000-iteration cap (parser.py:153) does not help because the loop runs inside one `parse_declaration` call. The expression form raises instead (parser.py:1874-1880), so the two are inconsistent.

**Evidence.** `a7/parser.py:2235-2261`:

```python
while not self.match(TokenType.RIGHT_BRACE) and not self.at_end():
    if self.match(TokenType.CASE):
        ...
    elif self.match(TokenType.ELSE):
        ...
    self.skip_terminators()
```

The hang is triggered by realistic typos, and by a valid program through PAR-02:

- `probes/p01_match_stmt_unknown_token.a7` (`match x { foo }`): the json, human and `--mode ast` runs are all killed by `timeout` (exit 124 after 60 s, 60 s and 15 s). `--mode tokens` exits 0 (`out/p01_tokens.stdout`).
- `probes/p02_match_stmt_two_stmts_one_line.a7` (`case 1: io.println("a") io.println("b")`): exit 124 in json and human modes, and in `--mode ast --format json` after 20 s.
- `probes/p02b_match_stmt_default_typo.a7` (`default: io.println("b")`): exit 124.
- `probes/q05_match_stmt_else_ret_struct.a7`, a **valid** program: `else: ret Pt{x: 2}` in a match statement. PAR-02 makes `Pt` an identifier, and the loop then spins on `{`. Exit 124 in both formats. An in-process trace over this file also hung and had to be killed.

**Fix direction.** Raise "Expected 'case' or 'else' in match statement" at the current token, as the expression form does. Add a progress guard: if the position did not advance in an iteration, raise.

**Changes accepted programs?** No. These inputs never finish compiling today.

---

## HIGH

### PAR-02 (HIGH, NEW): struct-literal detection depends on the distance to the nearest keyword within 10 tokens

**What is wrong.** Whether `Name{` starts a struct literal is decided by looking back at most 10 tokens on the same line for `if`, `while`, `for`, `match` or `else` (return False) or for `:=`/`=` (return True). If none is found, the answer is True. Two failure modes follow.

1. **False positive.** In a control-flow condition longer than 10 tokens that ends in a bare identifier, the body `{ ... }` is parsed as a struct literal of that identifier. The for-update is the only place that sets `_suppress_struct_literals` (parser.py:1242-1245, 1280-1283), even though the heuristic's docstring (line 116) says conditions are covered.
2. **False negative.** A genuine struct literal is refused when one of those keywords sits within 10 tokens before it on the same line: a single-line if-expression, `else:` arms, or `if c { ret Pt{...} }`.

The same program is accepted or rejected depending on token counts. The result is then a misleading parse error, a silent declaration drop with exit 0 (through PAR-03/F2), a false semantic error, or a hang (through PAR-01).

**Evidence.** `a7/parser.py:125-144`:

```python
lookback_distance = min(10, self.position)
...
if prev_token.type in (TokenType.IF, TokenType.WHILE, TokenType.FOR, TokenType.MATCH, TokenType.ELSE):
    return False
# Default to allowing struct literals
return True
```

It is used at parser.py:1677 and 1692. It applies only to a bare identifier or `Name(...)`, not to field chains, so `probes/q02_field_chain_condition_two_decls.a7` (`if cfg.items.count > cfg.items.limit {`) compiles and runs correctly.

| Probe | Shape | Result |
| --- | --- | --- |
| `p03_long_if_condition_ident_before_brace` (run-allowed) | `if a + b + c + d + e + a > limit {` | Exit 5 in both formats: `Unexpected token 'io' after parsing complete program [line 14: col 5]`. The swallowed real error is `Expected expression @ 13:5` (`recover_trace.log`). Control `p03b` (`if a > limit {`) exits 0 and prints `done` in Debug and ReleaseFast. |
| `q03_while_long_condition` | `while i + step + ... < limit {` | Exit 5: `Unexpected token '}' ... [line 10: col 4]`. Swallowed: `Expected RIGHT_BRACE, got PLUS_ASSIGN @ 9:9`. |
| `p04_struct_lit_in_if_expr` | `p := if c { Pt{x: 1} } else { Pt{x: 2} }` | **Exit 0 in both formats.** Emitted Zig is 36 bytes containing only `const Pt = struct {...}`, with no `main`. `build-obj` exits 0; `build-exe` fails with "root source file struct ... has no member named 'main'". Swallowed: `Expected RIGHT_BRACE, got LEFT_BRACE @ 10:18`. |
| `p05_struct_lit_in_match_expr_arm` | `else: Pt{x: 20}` in a match expression | Exit 0, 36-byte Zig with no `main`. Swallowed: `Expected 'case' or 'else' in match expression @ 12:16`. |
| `q04_ret_struct_single_line_if` | `if c { ret Pt{x: 1} }` | Exit 6 with a false semantic error, `Undefined type (Identifier 'make')` at 14:22, because `make` was dropped. Swallowed: `Expected type @ 9:22`. |
| `q05_match_stmt_else_ret_struct` | `else: ret Pt{x: 2}` | Hang, exit 124 (PAR-01). |

Multi-line forms work because a TERMINATOR stops the lookback, which is why the behavior looks intermittent to users.

**Fix direction.**

- Replace the heuristic with explicit parser context: set a "no struct literal" flag while parsing any control-flow condition, `for ... in` iterable or `match` scrutinee, and clear it inside `(...)`, `[...]` and call arguments.
- Never consult a token-distance window.
- Fix PAR-01 so a misparse can never hang.

**Changes accepted programs?** Yes, narrowly. A struct literal written without parentheses inside a condition of more than 10 tokens, such as `if a + ... == Pt{x: 1} {`, parses today and would need parentheses. Programs affected by the false negatives (p04, p05) currently produce artifacts with the function missing, and would gain it. I found no correct, building program whose meaning changes (INFERENCE).

### PAR-03 (HIGH, KNOWN F2 and C5): recovery after the first declaration drops code and fabricates file-scope declarations

**What is wrong.** This is the known F2 path: `parse()` swallows every ParseError when at least one declaration exists, unless the message contains "Expected declaration" with exactly one declaration, or contains "Expected expression after". `synchronize()` then resumes after the next TERMINATOR, which usually lies *inside* the broken function body. The remaining body lines are parsed as top-level declarations. That goes beyond "dropping a declaration": it invents globals that other functions then resolve against. Additional manifestations confirmed here (not in the ledger):

- `probes/q01_broken_body_typed_local_leak.a7` (run-allowed): `helper` has `x :=` and `limit: i32 = 42`; `main` prints `limit`. **The invalid program compiles with exit 0, Zig builds, and both Debug and ReleaseFast print `42`.** The emitted Zig has a global `var limit: i32 = 42;`. The untyped `p13` variant exits 0 and Zig rejects `var limit = 42` (B6).
- `probes/q10_destructuring_decl.a7`: `a, b := 1, 2` inside `main`. Exit 0; the entire Zig output is `var b = 1;` (12 bytes). `main` is gone, and `b := 1` became a global when `synchronize` stopped at `b :=` (parser.py:258-261). CLAUDE.md lists destructuring as "parsed-only/reserved", but it is not parsed at all.
- `probes/q20_new_with_args.a7`: `p := new Pt(1)`. Exit 0, 36-byte Zig with no `main`. The dedicated message at parser.py:1457-1463 is never reached because `parse_type` consumes `Pt(` as generic arguments and fails with "Expected type".
- `probes/p15b_struct_fn_field_single_line.a7` (`S :: struct { cb: fn() }`) and `probes/q19_fn_alias_at_eof_no_newline.a7` (`Callback :: fn()` at EOF): valid declarations silently dropped, exit 0 (see PAR-13).
- `probes/p18_using_import_after_decls.a7`: the error on `using` is swallowed and `synchronize` stops at `import`, so the result is a plain `IMPORT std/math` with the `using` modifier silently gone. Exit 0.
- False follow-on errors at the wrong stage: `p15_fn_type_return_void_fn` and `q04` exit 6 with "Undefined type (Identifier 'get'/'make')" for what is a parse error.
- With exactly one prior declaration, a real error inside `main` is swallowed and then re-reported as `Unexpected token '<next line>' after parsing complete program`, pointing at a valid line: `p03`, `p06`, `p17`, `q11`, `q18`, `q28`, `q29`. This is the ledger's "Lane F cross-cutting" item.

**Evidence.** `a7/parser.py:171-199` (Case 1 at 181-186, Case 2 at 189-191, recovery at 194) and `synchronize` at 235-268. `recover_trace.log` lists every swallowed error for each probe.

**Fix direction.** Per plan track 1 and packet P1: any ParseError fails the compilation. If recovery is kept for reporting multiple errors, it must collect errors and still exit 5, and it must resynchronize at the end of the enclosing top-level declaration (brace depth zero), not at the next newline.

**Changes accepted programs?** Yes: the SPEC fragments and tests listed under ledger C5, plus q01, q10, q20, p15b, q19 and p18 above. This needs the owner's approval (packet P1).

### PAR-04 (HIGH, NEW; the parser-side root cause of D7's "no line"): BINARY nodes are created without a span

**What is wrong.** `create_binary_expr` is called without a span, so every BINARY node has `span=None`. An EXPRESSION_STMT whose expression is binary also has no span, and a positional FIELD_INIT copies `field_value.span`, which is None for a binary value. Any later diagnostic attached to a binary node has no file position. The problem is more general than D7's "negative float literal divisor": it affects **every** division/modulo divisor obligation and every binary operand type error.

**Evidence.**

- `a7/parser.py:1423`: `left = create_binary_expr(left, binary_op, right)`.
- `a7/ast_nodes.py:288-292`: `create_binary_expr(..., span: SourceSpan = None)`.
- `inproc.log` §1, over `examples/037_language_tour.a7` plus a construct sampler: `BINARY: none=12 total=12`, `EXPRESSION_STMT: none=1 total=17`. Every other node kind had a span.
- `probes/q14_binary_type_error_span.a7` (`y := x + "a"`): exit 6, human output `error: Requires numeric type` with no line, column or excerpt. JSON `details[0].span` is `null`.
- `probes/q14b_binary_stmt_span.a7` (`x + true` as a statement): the same.
- `probes/q32_divisor_span.a7` (`ret a / b` with parameter `b`): exit 6, `Unsafe type cast (division/modulo divisor must be non-zero: divisor may be zero)`, JSON span `null`, no location in human output.

Related span choices that later diagnostics inherit:

- CALL span = callee span (1538).
- INDEX, SLICE and FIELD_ACCESS span = object span (1561, 1581, 1587, 1600).
- ASSIGNMENT span = target span (1326).
- IF_STMT, IF_EXPR, FUNCTION and others span only their first token.

The token columns of operators and punctuation are off by one or more (`token_columns.log`: `:=` at column 1, `..` at column 0, `}` at column 4 when it is really at 5). This is a tokenizer issue, known as B16 #5. Every span that starts at such a token inherits it.

**Fix direction.** Give BINARY nodes a span from `left.span` start to `right.span` end, or at least the operator token. Make EXPRESSION_STMT and ASSIGNMENT spans cover the whole statement.

**Changes accepted programs?** No (diagnostics only).

### PAR-05 (HIGH, KNOWN F5, broader than recorded): the JSON formatter crashes on any match expression with `else`

**What is wrong.** `parse_match_expression` stores `else_case` as a single node, while `parse_match_statement` stores a one-element list. The field is declared `Optional[List[ASTNode]]`. `JSONFormatter._ast_to_dict` treats `else_case` as a list and iterates it, raising `TypeError: 'ASTNode' object is not iterable`. The outer handler (compile.py:491-503) calls `_to_json_payload` again, so the exception escapes as a traceback with **exit 1**, which is not a documented exit code, and stdout is empty. This is not specific to a match yielding a struct: an `i32` match expression crashes too.

**Evidence.**

- `a7/parser.py:1872` sets `else_case = self.parse_expression()`, versus 2259 `else_case = [self.parse_statement()]`.
- `a7/ast_nodes.py:233` declares `else_case: Optional[List["ASTNode"]]`.
- `a7/formatters/json_formatter.py:164, 211-215` iterates it.
- `inproc.log` §4: `MATCH_EXPR.else_case type: ASTNode`, `MATCH.else_case type: list`.
- `probes/p05b_match_expr_else_int_json.a7` (`v := match k { case 1: 10 else: 20 }`): JSON exit 1, stderr ends `json_formatter.py", line 215 ... TypeError: 'ASTNode' object is not iterable`. Human exit 0, and the binaries print `10`.
- `probes/p12b_match_expr_two_else.a7`: the same, JSON exit 1.
- Downstream passes already paper over the inconsistency (`semantic_validator.py:315` `_as_statement_list(node.else_case)`, `zig.py:1081, 1180` `_else_case_statements`).

**Fix direction.** Give MATCH_EXPR its own field for the else expression, or always store a list, and make the formatter tolerate both. Test that `--format json` output is valid JSON for every node kind.

**Changes accepted programs?** No.

---

## MEDIUM

### PAR-06 (MEDIUM, NEW): newlines are not skipped inside array literals, positional struct literals and named-import lists

**What is wrong.** Call arguments (1522-1534) and named struct literals (1942-1946) skip TERMINATORs, but `parse_array_literal` (1894-1913), the positional branch of `parse_struct_literal` (1969-1980) and `parse_import`'s `{...}` list (395-408) do not. A multi-line array literal or positional struct literal is therefore a parse error. After one or more prior declarations it silently removes the enclosing function (PAR-03).

**Evidence.**

- `probes/p06_multiline_array_literal.a7`: exit 5, `Unexpected token '1' after parsing complete program [line 6: col 9]`. Swallowed: `Expected expression @ 5:19`.
- `probes/p07_positional_struct_multiline.a7`: **exit 0**, 48-byte Zig with no `main`. The control `p07b_named_struct_multiline_control` exits 0 and prints `1`.
- `inproc.log` §4 "named import no commas multi-line": `Expected RIGHT_BRACE, got TERMINATOR`.

**Fix direction.** Skip terminators after `[`, after every `,`, and before `]`/`}` in these constructs.

**Changes accepted programs?** No (it only accepts more; p07-like programs gain their `main`).

### PAR-07 (MEDIUM, NEW): Rich markup in a string literal crashes human `--mode ast`, `--mode tokens` and `-v`

**What is wrong.** The console formatter interpolates token values and literal values into Rich markup strings without escaping. A valid string literal such as `"[/dim]"` raises `MarkupError`, reported as `Unexpected error: closing tag '[/dim]' ...` with exit 8. With `-v`, the compile writes the `.zig` file and then exits 8.

**Evidence.**

- `a7/formatters/console_formatter.py:380-386`: `repr(token.value)` goes into `Table.add_row`.
- `:612-616`: `lit_val = f" [dim]{val_str}[/dim]"`.
- `probes/q12_rich_markup_in_string.a7`: `--mode ast` exit 8 and `--mode tokens` exit 8, stderr `Unexpected error: closing tag '[/dim]' at position 2 doesn't match any open tag`.
- In-process `ConsoleFormatter._display_ast` alone raises `MarkupError` (`out/q12_inproc.txt`).
- `probes/q33_markup_string_verbose.a7` with `-v`: exit 8 after writing `out/q33.zig` (594 bytes).

**Fix direction.** Use `rich.markup.escape` or `Text` objects for all user-derived text (token values, literal values, names).

**Changes accepted programs?** No.

### PAR-08 (MEDIUM, NEW): recursion-depth failures become exit 8 "internal" errors with no location

**What is wrong.** The parser is recursive descent, which CLAUDE.md allows. The failure mode, however, is an uncaught `RecursionError` reported as `Unexpected error: maximum recursion depth exceeded`: category `internal`, exit 8, no span. It is not a parse diagnostic. Measured first failing depths, in-process with the default limit of 1000 (`depth.log`):

| Shape | First failure |
| --- | --- |
| Nested parentheses | 197 |
| Nested calls `f(f(...))` | 164 |
| Nested array literals | 164 |
| Nested struct literals | 164 |
| Nested index `a[a[...]]` | 197 |
| Nested blocks | 492 |
| `else if` statement chain | 490 arms |
| `else if` expression chain | 977 |
| Nested `match` statements | 491 |
| `defer defer ...` | 491 |
| `while true while true ...` | 491 |
| Unary `- - -` | 983 |
| `ref ref ...` / `[][]...` / `Box(Box(...))` / `fn(fn(...))` types | about 988 |

Same-precedence and mixed binary chains are iterative and parsed fine up to 65536 terms. SPEC Appendix C's minimum of 127 nested blocks is met: `d05_blocks_127` and `d06_blocks_300` compile with exit 0.

**Evidence (CLI).** In `deep_cli.txt`:

- `d01_parens_197`: exit 8 in `ast` and `compile`, human and JSON. The JSON is valid, with `category internal` and `exception_type RecursionError`.
- `d03_else_if_490`: the same.
- `d02_parens_150` and `d04_else_if_300`: exit 0.

The bare `except:` at parser.py:1682 (PAR-09) also catches `RecursionError` during a speculative parse and backtracks, so the depth at which a failure surfaces is harder to predict.

**Fix direction.** Either catch `RecursionError` around `Parser.parse` and raise a ParseError ("nesting too deep") at the current token, or make expression and statement parsing iterative for the unbounded shapes (parentheses, `else if`, blocks). Document the limits.

**Changes accepted programs?** No.

### PAR-09 (MEDIUM, NEW): a bare `except:` hides struct-literal parse errors

**What is wrong.** When `Name(` might start a generic struct literal, the parser tries type arguments and a struct literal inside `try: ... except:`. Any exception, including a real syntax error inside the literal, `RecursionError` or `KeyboardInterrupt`, is swallowed. The parser backtracks and reparses the input as a call followed by a separate block statement. The user then gets an unrelated semantic error.

**Evidence.**

- `a7/parser.py:1665-1687` (`except:` at 1682).
- `probes/q22_bare_except_struct_fallback.a7`: `x := Wrap(i32){ foo() bar }` (missing comma). Exit 6: `Type is not callable: got 'Wrap(T)' [line 13: col 10]`. No parse error is reported.

**Fix direction.** Catch only `ParseError`. Once the tokens `Name(types){` have been recognized, commit to the struct literal and let its errors propagate.

**Changes accepted programs?** No (INFERENCE: a successful struct-literal parse is unaffected; only error reporting changes).

### PAR-10 (MEDIUM, NEW): duplicate `else` arms are silently discarded, and `case` after `else` is accepted

**What is wrong.** Each `else:` overwrites `else_case` (parser.py:2256-2259, and 1869-1872 for expressions), so earlier else bodies disappear without a diagnostic. Cases after `else` are accepted.

**Evidence.**

- `probes/p12_match_two_else_branches.a7` (run-allowed): exit 0, Debug and ReleaseFast print `second else`; the first else body is gone.
- `probes/p12b_match_expr_two_else.a7`: human exit 0, prints `3`.
- `probes/p12c_match_case_after_else.a7`: exit 0, prints `one`.

**Fix direction.** Raise a ParseError on a second `else`, and on `case` after `else` if the SPEC requires `else` to be last. The SPEC does not state this; decide it.

**Changes accepted programs?** Yes (p12 and p12b compile and run today). Needs approval.

### PAR-11 (MEDIUM, NEW): any expression is accepted as an assignment target

**What is wrong.** `parse_expression_or_assignment` accepts any expression before `=` or a compound operator, and no later pass rejects non-lvalues. The Zig backend emits `1 = 2;`.

**Evidence.**

- `a7/parser.py:1303-1327`.
- `probes/q16_assign_to_literal.a7`: exit 0, emitted `pub fn main() void { 1 = 2; }`. `build-obj` exits 1: `invalid left-hand side to assignment`.

**Fix direction.** Restrict targets to IDENTIFIER, FIELD_ACCESS and INDEX (plus the internal DEREF) in the parser or the semantic validator.

**Changes accepted programs?** No for literals (Zig rejects them already). Unknown for other non-lvalue shapes such as call results.

### PAR-12 (MEDIUM, NEW): `$T` in expression position becomes the plain identifier `T`

**What is wrong.** A GENERIC_TYPE token in expression position becomes `IDENTIFIER T`, with the `$` stripped, so it resolves to any ordinary symbol named `T`.

**Evidence.**

- `a7/parser.py:1632-1635`.
- `probes/p09_generic_type_in_expression.a7` (`T :: 5`, `y := $T`): exit 0, and Debug and ReleaseFast print `5`.
- `inproc.log` §4: `value node: IDENTIFIER T`.

**Fix direction.** Keep a distinct node kind or flag for generic references, and reject `$T` outside type or size positions.

**Changes accepted programs?** Yes (p09 compiles and runs today).

### PAR-13 (MEDIUM, NEW): a function type's optional return type is detected by an incomplete stop set

**What is wrong.** After `fn(...)` in a type, the parser tries to parse a return type unless the next token is TERMINATOR, `=`, `)`, `]` or `,`. The set lacks `{`, `}` and EOF. So:

- `get :: fn() fn() {` (a function returning a void function type) fails.
- `S :: struct { cb: fn() }` on one line fails.
- `Callback :: fn()` as the last line without a trailing newline fails.

After one or more prior declarations each is silently dropped (PAR-03). SPEC 6.4 shows `fn` types as ordinary types.

**Evidence.**

- `a7/parser.py:806-814`.
- `probes/p15_fn_type_return_void_fn.a7`: exit 6 with the false "Undefined type (Identifier 'get')". Swallowed: `Expected type @ 8:17`.
- `probes/p15b_struct_fn_field_single_line.a7`: **exit 0**, `S` absent from the AST (`out/p15b.ast.json`: `[IMPORT, FUNCTION main]`).
- `probes/q19_fn_alias_at_eof_no_newline.a7`: exit 0, `Callback` absent.

**Fix direction.** Parse a return type only if the next token can start a type (use `_is_type_start` plus IDENTIFIER, `[`, `fn`, `struct`).

**Changes accepted programs?** No (it only accepts more; output of p15b and q19 gains the declaration).

### PAR-14 (MEDIUM, NEW, partly KNOWN as "Lane F cross-cutting"): parse diagnostics lack source context and are often misleading

**What is wrong.**

1. 23 of the 28 explicit `ParseError.from_token` calls omit `source_lines`, so human output has no source excerpt. `consume()` does pass them. Examples: 183-186, 211-214, 327-331, 597-601, 923, 1715. Compare `p03` (bare `error: ... [line 14: col 5]`) with `inproc.log` §6, where the label-colon error has `source_lines=yes`.
2. Misleading messages at the wrong position:
   - "after parsing complete program" (KNOWN).
   - `new Pt(1)` gives "Expected type" instead of the dedicated message at 1457-1463 (`inproc.log` §6).
   - `main :: fn( {` gives "Expected type" (§6).
   - `fn(a, b: i32)` gives "Expected RIGHT_PAREN, got COLON" (§4).
   - An `@label` not before a loop gives "Expected LEFT_PAREN, got LEFT_BRACE" (`inproc2.log`).
   - `else` on the next line after `}` (`q18`) and a case body on the next line after `case 1:` (`p17`) both give "Unexpected token 'io' after parsing complete program".
3. Recovery decisions depend on substring matches against `str(e)` (181, 189), which includes the filename (PAR-24).

**Fix direction.** Pass `self.source_lines` everywhere, ideally via a `self._error(msg, token)` helper. Add specific messages for `else` on a new line, a case body on a new line, grouped parameters, and `new T(args)`. Base recovery on error codes, not message text.

**Changes accepted programs?** No.

### PAR-15 (MEDIUM, NEW): ASTNode design blocks a typed IR (Wave 3)

**What is wrong.**

1. **Recursive equality, repr and copy.** `@dataclass` generates a field-by-field `__eq__` over the whole subtree and sets `__hash__ = None`.
   - Two separately parsed but structurally identical trees compare `==` True, and so do two distinct `IDENTIFIER x` nodes, so `node in list` is structural (`inproc.log` §3).
   - On a 3000-term chain, `==`, `repr()` and `copy.deepcopy` all raise RecursionError (§3).
   - Every pass therefore keys node identity by `id()` (for example compile.py:578, 645).
2. **Undeclared attributes set at runtime** (`attrs.log`, instrumented `ASTNode.__setattr__` while compiling all 43 examples):
   - `inline_type` (parser.py:1996)
   - `implicit_ref_args` (type_checker.py:1405)
   - `implicit_deref_target` (type_checker.py:840)
   - `implicit_deref_object` (type_checker.py:1772, 1779)
   - `cast_source_type` and `cast_target_type` (type_checker.py:1884-1885, safety.py:549-550)
   - `cast_decision` (safety.py:548)
   - `generic_mapping` (type_checker.py:1359)
   - Also, by static grep: `file_module_call` (compile.py:589) and `module_emit_prefix` (compile.py:617). `is_capture_pattern` is declared but set via `setattr` (name_resolution.py:386).
3. **Fields never set, never read, or both:**
   - `has_fallthrough` and `variant_type`: never set, only listed in the JSON formatter and preprocessor.
   - `type_args`: never set. The console formatter reads it for TYPE_GENERIC (console_formatter.py:524), but the parser puts instantiation arguments in `generic_params` on TYPE_IDENTIFIER (parser.py:884-889).
   - `inline_type`: set, never read (grep shows only parser.py:1996).
   - `is_public`: read only to emit Zig `pub` (zig.py:428); there is no visibility enforcement.
4. **Type lies and inconsistent shapes:**
   - `else_case` is a node or a list (PAR-05).
   - `STRUCT_INIT.struct_type` is declared `Optional[ASTNode]` but is a `str` (`inproc.log` §4).
   - Negative literal patterns are raw UNARY expression nodes rather than PATTERN_LITERAL (`case -1` gives `['UNARY']`; `case -5..-2` gives PATTERN_RANGE of `(UNARY, UNARY)`). They happen to compile correctly (`p16`, `p16b` print `neg` and `minus one`).
   - CASE_BRANCH carries `statement` or `expression` depending on context.
   - `$` is stripped from generic names.
   - Generic parameters are sometimes `[]` and sometimes None.
   - `create_var_decl` and `create_const_decl` accept `explicit_type`, but the parser assigns it after construction (316, 1076).

**Fix direction.** Use `@dataclass(eq=False)` (identity equality and hashing) with an explicit structural compare helper. Split the AST into per-kind node classes, or at least declare every attribute. Move analysis annotations (types, implicit refs, casts) out of the syntax tree into side tables keyed by node ID. That is the planned typed IR.

**Changes accepted programs?** No (internal).

### PAR-16 (MEDIUM, NEW): JSON AST output is quadratic in nesting depth and incomplete

**What is wrong.**

1. `json.dumps(..., indent=2)` (compile.py:508, 715) indents each nesting level, and every BINARY adds several levels. A 3000-term `1 + 1 + ...` expression (a 15 KB source) produces **256,119,217 bytes** of JSON in `--mode ast --format json` (`deep_cli.txt`, `d07_binary_chain_3000`). A 300-arm `else if` chain produces 13 MB.
2. The formatter's field allowlist omits `inline_type`, so `struct { a: i32, b: i32 }{...}` appears as `STRUCT_INIT struct_type "__inline__"` with no fields or types (`probes/q13_inline_struct_init.a7` JSON). It also omits every undeclared annotation from PAR-15.
3. Every node repeats default booleans (`is_public`, `is_using`, `is_tagged`, `is_variadic`, `has_fallthrough`), because `False is not None` (json_formatter.py:114-117).

**Fix direction.** Emit compact JSON (no indent) or cap the indent. Derive the field list from the node definition. Omit default values.

**Changes accepted programs?** No.

### PAR-17 (MEDIUM, KNOWN F3/F4): 1000-iteration cap; warning on stdout

Re-confirmed in-process (`inproc2.log`): 1100 constants plus `main` raises `Unexpected token 'C999' after parsing complete program @ (1001, 1)`, and stdout receives `Warning: Parser stopped after 1000 iterations in s.a7`.

Code: `a7/parser.py:153-156, 201-206`. The cap counts recovery iterations too, so a file with swallowed errors reaches it sooner (INFERENCE from 156-199).

`test/test_parser_fuzzing.py:486-497` asserts exactly 1000 declarations, which is the cap boundary. That test passes `code` as `filename`, so the warning echoes the entire source.

**Fix direction.** Remove the cap and rely on the progress guard at 167-169. Send warnings to stderr or the result object.

**Changes accepted programs?** No (it accepts more).

---

## LOW

### PAR-18 (LOW, NEW): `using import` cannot parse

`parse_import` handles an IDENTIFIER `using` (378-381), but `parse_declaration` dispatches to it only on an IMPORT token (288-289), so that branch is unreachable. `is_using` consumers (`name_resolution.py:131`, `module_resolver.py:224`) are dead.

- As the first declaration: `Expected declaration ... @ (1, 1)` (`inproc.log` §4).
- After one or more declarations: `using` is silently stripped and a plain import results (`p18`, PAR-03).

SPEC 13.1 lists `"using" "import" string_lit`; SPEC 10.2 says it is planned. Decide: either delete the dead path and reject `using` with a clear message, or implement it.

**Changes accepted programs?** Yes if rejected (p18 compiles today).

### PAR-19 (LOW, NEW): separators are optional where the SPEC implies they are required

- **Type arguments without commas.** `p: Pair(i32 bool)` compiles with exit 0 (`p14`); the loop at 877-881 has no `else: break`.
- **Struct fields, union fields and enum variants without commas on one line.** `S :: struct { a: i32 b: i32 }` and `E :: enum { A B C }` parse (`inproc.log` §4; 2035-2036, 2081-2082).
- **Statements and declarations without a terminator.**
  - `x := 1 y := 2` and `io.println(..) io.println(..)` compile and print `1`, `2` (`p08`).
  - `A :: 1 B :: 2` at file scope compiles (`p08b`).
  - `io.println("{}", x) x` exits 0 and Zig rejects "pointless discard" (`q31`).
  - SPEC 2.1 says newlines are statement terminators; `parse_block` (932-937) never requires one.
- **Degenerate lists.**
  - `for i := 0;; i < 3; i += 1` compiles and prints `0 1 2` (`q21`), because the tokenizer merges `;;`.
  - `N(,) :: 5` parses.
  - `import "std/io" { ,, println }` parses.

**Changes accepted programs?** Yes (p08, p08b, p14 and q21 compile today). Needs approval.

### PAR-20 (LOW, NEW): statement bodies and `defer` are too permissive

- **Bodies without a block.** `if` and `while` take `parse_statement()` (1122, 1127, 1141), so `if x > 0 ret 1` (`p10`, prints `1`) and `while i < 3 i += 1` (`p10b`, prints `3`) compile. `for` requires a block (1156, 1185), and SPEC examples always use blocks.
- **`defer` with control flow.** `defer` takes any statement (2276): `defer ret 1` (`q15`) and `defer break` (`q15b`) compile with exit 0 and emit `defer void;`, which Zig rejects. This is the same lowering symptom as KNOWN B11. The parser-side fix is to reject control flow and declarations after `defer`.

**Changes accepted programs?** Yes for `if`/`while` without a block (they compile and run today). No for `defer ret` and `defer break` (Zig rejects them).

### PAR-21 (LOW, NEW): a type in value position yields a "compiler bug" diagnostic

`parse_primary_expression` returns a TYPE_STRUCT node as an expression (1623-1629). `x := struct { a: i32 }` exits 6 with `Unexpected AST node kind: Unknown expression kind: NodeKind.TYPE_STRUCT ... hint: This is likely a compiler bug, please report it` (`q17`). It should be a parse error: "expected `{` to initialize inline struct".

**Changes accepted programs?** No.

### PAR-22 (LOW, NEW; one item KNOWN C5): SPEC grammar and examples versus the parser

Each item was verified in-process (`inproc2.log`, `inproc.log`) or by a probe.

| SPEC | Statement | Parser |
| --- | --- | --- |
| 13.2 `type = ... union_type` | inline `union(tag) {...}` is a type | Not parsed: `u: union(tag) { a: i32 }` gives "Expected type". `parse_type` has no UNION branch. |
| 13.2 `union_type = "union" generic_params? "(" "tag" ")" "{"` | `(tag)` required | Optional; `union()` is accepted as untagged (`inproc.log` §4). |
| 13.1 `function_decl ... "fn" generic_params "("`; 13.2 `"fn" generic_params? "("`; 13.2 `"struct" generic_params?` | generic parameters after `fn` or `struct` | Not parsed ("Expected LEFT_PAREN, got GENERIC_TYPE"). The parser supports `Name($T) :: fn` instead (SPEC 7.3 and 7.4 forms work: `q27` prints `3`). |
| 13.3 `assignment_expr` and 12.4 "14. Assignment" | assignment is an expression | Statement-only; `a = b = 3` gives "Expected expression". |
| 13.3 `"if" expr block "else" block_or_if` | `else` required, block body | Body is exactly one expression; `else` is optional in the parser, and semantic analysis then reports "If expression branches have different types ... 'void'" (`p11`). |
| 13.3 postfix `"." "val"` | listed | Parsed as field `val` (KNOWN doc defect, SPEC.md:2021). |
| 13.4 statements | no `del`, `fall` or local `::` | The parser accepts all three (grammar incomplete). |
| 2.4 keywords | `cast`, `const`, `self`, `size_of`, `type`, `using`, `var` are keywords; `not` is absent | The tokenizer treats them as identifiers (`cast := 1` parses); `not` is a keyword and a unary NOT (`tokens.py:178-227`). `as` and `where` are tokens that the parser never consumes (`q29`: exit 5 `Unexpected token '}' ... col 0`). `int`, `uint` and `float` are KNOWN D5. |
| 5.3 `for char in string[2..5]` | example | `char` is a type keyword: "Expected identifier or '{' after 'for' keyword". |
| 8.1 `fn example() {` | example | "Function declarations must have names". |
| 6.6 `printf :: fn(format: string, args: ..)` | declaration without body | "Expected function body after function signature". |
| 7.2 `Option :: enum { Some: $T, None, }` | generic enum payload | Exit 5 (`q28`). KNOWN via ledger C5 (the SPEC.md:911 fragment). |
| 10.4 "Struct fields are always file-private (cannot be marked `pub`)" versus 13.2 `field = "pub"? identifier ":" type` | SPEC contradicts itself | The parser follows 13.2: `pub x: i32` compiles and runs (`p19`). |
| 12.3 AST node structure | `location` with `offset`, `children` | Does not describe `ASTNode` (`ast_nodes.py:157-259`). |

**Changes accepted programs?** Depends on the resolution: no for documentation fixes, yes for rejecting `pub` fields or `not`.

### PAR-23 (LOW, NEW): console and markdown AST views are incomplete or wrong

- `_add_statements_to_tree` (console_formatter.py:805-825) descends only into `statements` and if `then_stmt`/`else_stmt` blocks. Loop bodies, defer bodies, match cases and else arms are hidden. `q26` `--mode ast` shows `DEFER → BLOCK (1 stmts)` and `MATCH identifier x (2 cases)` with no children (`out/q26_ast_human.stdout`).
- The markdown AST tree (markdown_formatter.py:222-234) shows no expressions or match cases: `FUNCTION 'main' / BLOCK / VAR 'x' / DEFER / MATCH` (`out/q26_doc.md:137-145`).
- `format_type` prints `[None]i32` for a non-literal size (498-503) and drops generic instantiation arguments (`Box(i32)` becomes `Box`; 520-521 versus 522-528) (`inproc2.log`).
- IMPORT declarations display without their alias (`IMPORT (line 2)`).

**Changes accepted programs?** No.

### PAR-24 (LOW, NEW): miscellaneous robustness

- **Recovery keyed on message text including the filename.** The same source with filename `Expected expression after.a7` is rejected with `Expected type`, while `plain.a7` parses (with the declaration dropped) (`inproc.log` §5; parser.py:178-191).
- **Empty token list.** `Parser([])` raises `IndexError` (parser.py:60, 67-68). The CLI always has EOF, so this is API-only. `self.current_token` is set once and never updated.
- **`pub import` loses its flag.** `pub import "std/io"` drops `is_public` (`inproc.log` §4); `parse_import` never receives it (288-289).
- **Any `union(...)` argument.** `union(foo)` gives "Expected RIGHT_PAREN, got IDENTIFIER", which is a poor message for a misspelled `tag`.
- **Quadratic nested calls.** The speculative type parse at 1658-1687 re-scans nested call arguments: 2.9, 13.1, 23.9 and 41.9 ms at depths 40, 80, 120 and 160. This is quadratic but bounded by PAR-08. Wide calls and statement counts are linear (`inproc.log` §7).

**Changes accepted programs?** No, except `union()`.

### PAR-25 (LOW, NEW): dead code and unused state in the parser

- `parse_block`'s `try/except ParseError as e: raise e` (933-941).
- `_is_valid_expression_statement` (1355-1358) is never called.
- `if not right:` (1417-1421) can never be true.
- `if assign_op:` (1323) is always true.
- The `and not self.match(TERMINATOR, RIGHT_BRACE)` clauses at 983 and 993 are redundant.
- `generic_params` is always `[]` from `parse_mixed_parameters` (682) and `parse_struct_decl_with_name` (2006).
- Unused locals: `start_token` (279, 2151, 2172), `struct_token` (2003), `enum_token` (2055), `union_token` (2100), `else_token` (1870, 2257).
- Unused imports: `Union` (8), `create_span_between_tokens` (44); `ParseError` and `SourceSpan` are imported twice (10, 44).
- `parse_function_decl_anonymous` exists only to raise.
- `_suppress_struct_literals` is created with `setattr`-style assignment and read with `getattr` defaults (117, 1242).
- The docstring (line 4) says the parser "implements the A7 grammar as specified in docs/SPEC.md section 12"; the grammar is section 13, and see PAR-22.

**Changes accepted programs?** No.

---

## Side observations outside this component (not counted)

- **S1 (backend runtime, UNVERIFIED root cause):** when a compiled program's stdout is redirected to a regular file, each `io.println` overwrites the file from offset 0. `p08` Debug binary: `| cat` gives `1\n2\n`; `> file` gives `2\n` (`out/p08_pipe.txt`, `out/p08_file.txt`). INFERENCE: `std.Io.File.stdout().writer(...)` is a positional writer created fresh on every call (`__a7_stdout_print` in the emitted preamble). This silently corrupts redirected program output.
- **S2:** `d07_binary_chain_3000` parses and prints in `--mode ast` (exit 0), but `--mode compile` exits 8 with RecursionError in a later stage. The pass was not identified.
- **S3 (tokenizer):** operator and punctuation token columns are wrong (`token_columns.log`); see PAR-04 and KNOWN B16 #5.

## Checked and correct

- **Binary precedence** matches SPEC 4.3 exactly (`ast_nodes.py:609-641`), and every level is left-associative (`precedence + 1` at parser.py:1414). Shapes in `inproc.log` §2:
  - `a | b ^ c & d << 1 + 2 * 3` gives `(a | (b ^ (c & (d << (1 + (2*3))))))`.
  - `a or b and c` gives `a or (b and c)`.
  - `a & b == c` gives `a & (b == c)`.
  - `a - b - c` and `a / b * c % d` group left.
  - `a < b < c` gives `(a<b)<c`.
- **Unary binds tighter than binary**, and postfix binds tighter than unary: `-a * b` gives `(-a)*b`, `!a == b` gives `(!a)==b`, `-f(x)[0]` gives `-(f(x)[0])`.
- **The Zig backend preserves grouping.** Run-allowed `q23` prints `7 -4 -30 22` in Debug and ReleaseFast, which matches the independently computed values under C precedence.
- **Parsed-only syntax is rejected before codegen with clear located diagnostics (exit 6):**
  - Variadic parameters (`q06`: "Variadic parameters are parsed for future support ...", 4:11).
  - `@size_of(i32)` (`q07`), `@unreachable()` (`q08`) and an unknown `@no_such_builtin(1)` (`q09`). The message for an unknown builtin still says "parsed for future support", which is slightly misleading.
  - Destructuring and multi-declaration are **not** parsed; see PAR-03 (`q10` exit 0) and `q11` (exit 5).
- **Labeled loops.** `@outer for` with `break outer` and `continue outer` compiles and runs correctly (`q25` prints `2`). The old `label:` spelling is rejected with a specific message (`inproc.log` §6).
- **Control flow and literals that work:**
  - `fall` in a block case body, `defer { ... }` block form, and case lists (`q26` prints `one two deferred`).
  - Range and negative patterns (`p16` prints `neg`; `p16b` prints `minus one`).
- **Generics and types:**
  - `min($T: @type_set(i32, i64)) :: fn(...)` compiles and runs (`q27` prints `3`).
  - `Pair(i32, string){...}` and `nested: Box(Box(i32))` parse (`inproc2.log`).
  - Inline struct type as a return type with inline struct initialization (SPEC 6.1 `sincos` shape) compiles and runs (`q13` prints `1 2`).
- **Heuristic controls and statement forms:**
  - Field chains in long conditions do not trigger PAR-02 (`q02` prints `done`).
  - Named multi-line struct literals work (`p07b`).
  - `while ... and not f()` parses.
  - Typed declarations with and without initializer parse at file and block scope.
- **Parser scaling.** 65,536-term binary chains parse in-process. 8000 statements take 128 ms; 8000 call arguments take 477 ms, which is linear.
- **Nesting limits met.** 127 and 300 nested blocks, 150 nested parentheses, and 100- and 300-arm `else if` chains compile with exit 0 in human and JSON modes (`deep_cli.txt`), meeting SPEC Appendix C.
- **Deep JSON conversion.** `JSONFormatter._ast_to_dict` is iterative and handled a 3000-deep chain. Deep failures in JSON mode still produce valid JSON with `category internal` (`d01`, `d03`).
- **Recursion error reporting.** RecursionError from the parser is caught by compile.py:491 and reported as exit 8 without a traceback in human and JSON modes (`d01`, `d03`); see PAR-08 for why that is still wrong.
- **Other spans.** Every node kind except BINARY, and EXPRESSION_STMT wrapping a binary, has a span (`inproc.log` §1).

## Test gaps

These are from a full read of the 16 `test/test_parser*.py` files. I spot-checked the counts and items marked (spot-checked).

**Coverage-illusion tests** (assert only `kind == PROGRAM`, `is not None` or `assert True`; swallow `ParseError`; or accept either outcome):

| File | Illusion tests |
| --- | --- |
| `test_parser_creative_cases.py` | 31 of 31 (spot-checked) |
| `test_parser_type_combinations.py` | 35 of 35 |
| `test_parser_extreme_edge_cases.py` | about 55 of 64 |
| `test_parser_advanced_edge_cases.py` | about 23 of 26; `try/except ParseError: pass` at 122, 135 (spot-checked: the multi-line array literal test passes whether or not parsing fails), 147, 171, 298, 403, 427 |
| `test_parser_combinatorial.py` | 20 of 24 |
| `test_parser_unicode_and_special.py` | 19 of 19 |
| `test_parser_comprehensive_problems.py` | about 17 |
| `test_parser_stress_tests.py` | about 17 |
| `test_parser_examples.py` | 14; `assert True` at 318 (spot-checked) |
| `test_parser_integration.py` | `assert True` at 366, 415, 461, 493, 527 (spot-checked) |
| `test_parser_error_handling_improvements.py` | either-outcome tests at 238, 255, 271, 483-496 (483 spot-checked) |
| `test_parser_fuzzing.py` | crash-only tests, mostly unseeded (219, 241, 260, 290, 314, 415); line 354 reseeds the global RNG |

Several tests call `Parser(tokens, code)`, which passes the source as `filename`.

**Tests that lock in current or buggy behavior:**

- `test_parser_fuzzing.py:486-497` asserts exactly 1000 declarations, the PAR-17 cap boundary (spot-checked).
- `test_parser_examples.py:54` passes on `examples/003_comments.a7` with its unclosed comment (KNOWN F1/C5).
- `test_parser_creative_cases.py:644` passes only because recovery drops `main` (KNOWN C5).
- Many tests assert that banned syntax parses, checking only PROGRAM or not-None:
  - `.adr` and `.val`: `test_parser_combinatorial.py:199, 887`; `test_parser_creative_cases.py:16, 228, 951`.
  - `new [N]T`: `test_parser_advanced_edge_cases.py:308`, `test_parser_creative_cases.py:918`.
  - Non-ASCII strings: `test_parser_unicode_and_special.py:16-61`.

**Behaviors with no test:**

- **Error handling and recovery:**
  - Match statement with a non-`case` token (PAR-01).
  - Two statements on one line in a case body.
  - Struct literals after conditions of more than 10 tokens, or inside single-line if-expression and match arms (PAR-02). `test_parser_error_handling_improvements.py:400-449` uses only short conditions.
  - Any error after the second declaration asserting failure (F2): every "recovery" test places its error in the first declaration.
- **Syntax forms:**
  - Multi-line array and positional struct literals (PAR-06).
  - Duplicate `else` (PAR-10).
  - `$T` in expressions (PAR-12).
  - `fn()` types followed by `{` or `}` (PAR-13).
  - `using import` (PAR-18).
  - Missing commas and terminators (PAR-19).
  - `if` without a block (PAR-20).
  - `pub` fields.
  - Negative patterns.
  - A case body on the next line.
- **Depth:** depth limits and clean failure versus RecursionError (PAR-08). Existing depth tests stop at 40 to 100 levels.
- **AST content:**
  - Spans: no test asserts the line or column of any AST node kind; only ParseError spans are checked (`test_pipeline_diagnostics.py:39`, KNOWN failing B16 #5).
  - AST shape for any precedence level other than `+`/`*`: none, and none for unary versus binary or left associativity.
- **Output modes:**
  - `--format json` validity for match expressions, inline struct types or deep trees (PAR-05, PAR-16).
  - Console `--mode ast` content, Rich-markup escaping (PAR-07), and the markdown AST section (PAR-23).

**Tests whose names claim more than they assert:**

- `test_parser_basic.py:350` "missing_semicolon_recovery": the input has no error.
- `test_parser_edge_cases.py:108, 119, 133`: "recovery" tests on valid code.
- `test_parser_edge_cases.py:52`: claims a full precedence shape but checks only the top operator.
- `test_parser_extreme_edge_cases.py:280`: "(1 < 2) < 3" with no shape check.
- `test_parser_fuzzing.py:314`: "all nodes should have spans" but walks only declarations, bodies and statements, so it misses the BINARY span gap.

## Not verified

- Whether any semantic pass relies on structural `==` or `in` over ASTNodes. A grep for `in <node list>` and `.remove(`/`.index(` found no direct use; INFERENCE only.
- The exact later pass that raises RecursionError for the 3000-term chain in compile mode (S2).
- The root cause of S1 (overwritten redirected stdout); only the symptom was observed.
- The Zig build of `q13`, `q25`, `q26`, `q27` and `q23` was run; the Zig build of dropped-`main` artifacts was run only for p04 and p05 (`build-exe` fails). p07's missing `main` was confirmed from the emitted Zig, without a separate `build-exe` log.
- The `test_parser*.py` findings beyond the spot-checked lines come from a delegated full read and were not each re-verified line by line.
- Import and module interactions of parse recovery (a ParseError inside an imported file) belong to the module resolver; see KNOWN B16 #7.

claims checked: 205
