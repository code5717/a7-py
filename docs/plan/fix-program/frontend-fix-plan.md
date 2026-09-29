> **Source:** Claude Plan subagent, fix plan for the tokenizer, parser and pipeline audit findings (TOK, PAR, PIP), 2026-09-16.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim from the agent's final message. The approved execution plan (`docs/plan/execution.md`, Wave 1R and 2R) adopts its batches with the user's module decisions applied; where they differ, the execution plan governs.

I couldn't save a plan file because this session has no write tool, so the full plan is below. Line numbers are from commit `701c679`. `git status` shows no changes under `a7/`, so they are current. Every compatibility check is marked either "grep-verified" (I ran the grep) or "not checked".

# Fix plan for the tokenizer, parser and pipeline audits

## 0. Conventions and ownership

- **Batch IDs.** `LX` = lexer, `PR` = parser, `CLI`/`PL`/`X` = pipeline and shared work, `NR` = name resolution, `BE` = backend, `MOD` = module redesign, `ID-2.1` = the Wave 2.1 node-identity step.
- **Exactly once.** The coverage table in §7 gives each audit ID exactly one owner. Packets in §5 only reference batches. When one finding is split (part fixed without asking, part needing approval), both parts live in the same batch row.
- **Approval classes.** A–D are the classes from `docs/plan/packets/P0-plan-confirmations.md:21-26`. P0 is still "proposed" in that file. The owner's rule in your brief ("crashes, hangs, miscompiles, wrong diagnostics and code Zig already rejects are fixed without asking") is effectively the P0.1 approval; the controller should record it in `docs/plan/decisions.md`.
- **Ownership gap.** The lane table (`docs/plan/execution.md:40-50`) gives no owner to `a7/compile.py` (apart from the IR lane's one-hunk wiring), `a7/module_resolver.py` or `a7/ast_nodes.py`. I propose splitting lane F into three sub-lanes by file, so they can run in three worktrees:
  - **F1 lexer:** `a7/tokens.py`, `a7/ast_nodes.py:536-604` (literal decoding), the tokenizer tables in `a7/errors.py`.
  - **F2 parser:** `a7/parser.py`. The rest of `a7/ast_nodes.py` is untouched in Wave 1 and owned by the serial ID-2.1 step in Wave 2.
  - **F3 CLI/pipeline:** `a7/cli.py`, `a7/compile.py` (except the later IR hunk), `a7/formatters/*`, `a7/module_resolver.py` until MOD takes it over, and the formatter part of `a7/errors.py`.
  - `a7/errors.py` is a serialization point: hunks from F1 and F3 are applied one after the other.
- **Packets.** The execution plan's P1 and P2 packets are merged into one lexer packet and one parser packet, as you decided.

---

## 1. Root-cause batches

### Wave 1: critical hangs and miscompiles (applied first, whatever the usual lane order)

**PR-00: the parser loops forever on some inputs** (PAR-01, the CRITICAL hang). Lane F2. Class A.
- **Files:** `a7/parser.py`.
  - `parse_match_statement` (2235-2261).
  - The same loop shape in `parse_match_expression` (~1860-1880), struct/enum/union bodies (2035-2036, 2081-2082), `parse_array_literal` (1894-1913), `parse_struct_literal` (1942-1980), `parse_import` (395-408), `parse_block` (932-937) and the type-argument loop (877-881).
- **Approach.** A match statement raises "Expected 'case' or 'else' in match statement" at the current token, as the expression form already does (1874-1880). Every loop that runs to a closing bracket gets a no-progress guard that raises a located `ParseError` (exit 5).
- **Tests.** New CLI tests, human and JSON, with `subprocess` timeout 20 s: p01, p02 and p02b exit 5 with the offending token's line and column. One in-process test per list construct with a stray token (`S :: struct { a: i32 ) }`) must raise within the timeout. q05, a valid program, is tested in PR-02.
- **Depends on:** nothing. Runs first in F2.

**PL-01: stdlib calls recognised by name text** (PIP-2, PIP-3, and the code half of PIP-23). Lane B plus lane L. Class C.
- **Shared work.** This is the same code as execution-plan Lane B item 7 (B14, `docs/plan/execution.md:133`) and the other planner's ZIG-5 and SAF-9. Run it as one task.
- **Files:**
  - `a7/ast_preprocessor.py` `_resolve_stdlib_call` (194-220): delete the bare-builtin `elif` (216-220) and the `or obj.name` fallback (209).
  - `a7/backends/zig.py`: in `_emit_call` (1612-1650) delete `_MATH_BUILTIN_MAP` and the `func.startswith('math.')` branch; in `_scan_features` (144-149) and `_is_io_call` (2163-2167) delete the text match on `io`.
  - `a7/stdlib/__init__.py:78` `resolve_builtin` and the typed names in `a7/stdlib/math.py:34-41`: delete, or leave unused until packet item PL-A2 is decided.
- **Approach.** A call is treated as stdlib only through `stdlib_canonical`. That field is set only when `_resolve_module_import_path` (`ast_preprocessor.py:221-232`) finds a `MODULE` symbol.
  - Removing the bare-builtin path changes no correct program: the type checker already rejects an undeclared `sqrt_f64` (`probes/s07`). So that path only fires when the user declared the name, which is exactly the hijack.
  - The case where a local named `io` shadows a real `std/io` alias is not fixed here, because the lookup is not scope-aware. X-SYM finishes it.
- **Tests.** In `test/test_zig_backend_runtime.py` (Lane B's file), Debug and ReleaseFast:
  - s01 prints `10`.
  - s02b prints nothing.
  - The B14 case prints `4.5 4.5`.
  - Counterexample: `m :: import "std/math"; m.sqrt(9.0)` still lowers to `@sqrt` and prints `3`.
- **Replace:** the `resolve_builtin` tests in `test/test_stdlib_registry.py:167ff`, which only restate the registry table.
- **Depends on:** nothing.

**PL-02: interim stopgap for PIP-1 (optional).** PIP-1 itself is owned by MOD. Lane F3. Class C.
- **Files:** `a7/compile.py` `_annotate_file_module_calls` (574-595).
- **Approach.** Walk with an explicit stack of scope frames: function parameters, blocks, for iterators, match captures, and VAR/CONST declared in each frame. Annotate `X.f()` as a module call only if no enclosing frame declares `X`.
  - The failure mode is safe: if shadow detection is wrong, the emitted Zig fails to build with "undeclared identifier". It never silently computes the wrong thing.
  - MOD deletes this code; the tests stay as acceptance tests for MOD.
- **Why offered.** f03 prints `1 2` today instead of `2 2`, and MOD has no date. This is a stopgap, not module design. The controller can drop it; PIP-1 then stays open until MOD.
- **Tests.** In `test/test_pipeline_native.py`, Debug and ReleaseFast:
  - f03 with `flat.a7` prints `2 2`.
  - Control: a module call in a function whose locals have other names still calls the module.
  - Control: a local `h` in a sibling block does not disable `h.work()` elsewhere.
  - The walk passes at recursion limit 100 (`test/test_iterative_traversal.py`).

**BE-01: redirected stdout keeps only the last line** (parser addendum S1). Lane B. Class C.
- **Files:** `a7/backends/zig.py` `_emit_preamble` (166-169).
- **Approach.** Emit `std.Io.File.<stream>().writerStreaming(__a7_io.?, &__a7_stream_buf)` instead of `.writer(...)`.
  - In the Zig 0.16.0 library, `File.writer` "Defaults to positional" and `writerStreaming` is the streaming form (`lib/std/Io/File.zig:596-609`, which I read).
  - The helper builds a fresh writer on every call. A positional writer starts at offset 0, so each print overwrites the file. This mechanism is inferred from the Zig source and has not been run.
  - The fix does not depend on the P8 buffering decision.
- **Tests.** The runtime test writes two `io.println` lines and one `io.eprintln` with stdout and stderr redirected to files in `tmp_path`, not pipes. Debug and ReleaseFast files must contain every line.
- **Update:** the emitted-text asserts in `test/test_codegen_zig.py:287-291, 357-360`.

### Wave 1: lexer

**LX-01: operator and terminator columns** (TOK-04, TOK-27). Lane F1. Class A. Fixes baseline failure #5.
- **Files:** `a7/tokens.py` `_add_token` (364-376), the newline branch (297-299), `_try_operator` (826-956, with the dict rebuilt on every call at 928-952).
- **Approach.** Record `start_column` before consuming a token and make the column a required argument. Hoist the operator tables to class constants.
- **Tests.**
  - Token columns written by hand for `a + b\n`, `{\n}`, `x <<= 1`, `0..5`, `:= x`.
  - `--mode tokens --format json` on tok06b checks the column of `}`.
- **Replace:** `test_tokenizer_aggressive.py:578-592` (asserts internal fields) and `:542-555` (a "performance" test with no time bound; delete it).
- **Compatibility (grep-verified):** the column asserts in `test_tokenizer_errors.py` use invalid characters and identifiers, which this does not change; `test_parser_error_handling_improvements.py:534` asserts `> 5`, which still holds.

**LX-02: literal and name diagnostics** (TOK-03 crash forms, TOK-08 `inf`, TOK-09, TOK-15, TOK-24). Lane F1. Classes A and B.
- **Files:** `a7/tokens.py` number scanners (428-564), `_tokenize_char` (672-750), `_tokenize_builtin` (811-817), `_try_generic_type` (974-1005), the unexpected-character message (357); `a7/ast_nodes.py` `create_literal_from_token` (587, 590); the tokenizer error tables in `a7/errors.py`; `a7/compile.py:153-164` (reading the file).
- **Approach.**
  - **Underscores in numbers.** Reject, with a located `TokenizerError` (exit 4), the placements that crash today: trailing `_`, `__`, and `_` next to `.` or `e`. The lexer validates the conversion so the value never reaches `int()`/`float()` unchecked.
    - `0x_1` stays accepted.
    - Non-ASCII digits (`1٣` compiles to 13) go to the lexer packet.
  - **Char literals above 0xFF.** Reject them. Class B: Zig reports "cannot represent integer value".
  - **Float overflow.** A non-finite float literal is an error (class B: `inf.0` fails in Zig). Underflow to 0.0 is deferred to gate G1.
  - **`@` and `$` names.** Use the ASCII identifier character class and reject an empty name. Class B for labels, which Zig rejects.
    - A Unicode `$T` name stays in class B only if a probe shows no program with one builds today; otherwise it moves to packet item LX-A12.
  - **Char literal errors.** Distinct errors for a bad escape (`INVALID_ESCAPE_CHAR`), an empty char and a char with several characters, located at the opening quote and covering the literal.
  - **Unprintable characters.** Show them as `U+XXXX`.
  - **Invalid UTF-8.** Decode the bytes and give the line and column of the first bad sequence. The exit code stays 3 (io), so the current contract holds; only the span is added.
- **Tests (CLI, human and JSON, spans derived by hand):**
  - tok04_0..7 exit 4.
  - tok12 exits 4.
  - tok10a and tok10c exit 4.
  - `'\q'`, `''`, `'ab'` and `'\xZZ'` report the right message at the opening quote.
  - tok11c and tok11d exit 4.
  - tok17b shows `U+0000`.
  - tok17a has a line and column.
- **Replace:**
  - `test_tokenizer_errors.py:104-121` (locks in the TOK-15 text) and `:68-85` (computes expected line and column but never asserts them).
  - The `try/except TokenizerError:` blocks with no `else: fail` at `:156-176, 178-194, 196-214, 216-245, 273-310, 366-383, 385-411`; use `pytest.raises` instead.
  - The either-outcome tests `test_tokenizer_aggressive.py:180-196, 230-240, 351-373, 594-614, 616-633`: their split-literal cases wait for LX-P, and the rest get a definite expected result here.
- **Depends on:** LX-01 (same file).

**LX-03: Zig escaping for char and string literals** (the emitter half of TOK-07). Lane B. Class B.
- **Files:** `a7/backends/zig.py` `_emit_literal` for chars (`char_escapes` at 1491-1496) and `_quote_zig_string` (2297-2303).
- **Approach.**
  - Chars: emit `'\xHH'` for byte values 0x00-0x1F, 0x7F and 0x80-0xFF. `'é'` then emits `'\xe9'`, the same u8 value as today.
  - Strings: write U+0080-U+009F, U+2028 and U+2029 as escaped UTF-8 bytes. The bytes are the same ones emitted raw today, which Zig accepts for other code points and rejects for these.
  - The lexer-side validation is in the lexer packet.
- **Tests.** tok11a, tok11b, tok11g and tok11i build and print the byte value. tok25 builds, and its stdout bytes equal the UTF-8 of the source text, compared with `od`. tok01 still builds (its output is decided by LX-A5).

**LX-04: shared line table** (TOK-10, TOK-25). Lanes F1 then F3. Class A.
- **Files:** a helper that strips the BOM, splits on `"\n"` and strips a trailing `"\r"`, used by `Tokenizer.__init__` (`tokens.py:233-237`), `compile.py:192, 232` and `module_resolver.py:158`. In `a7/errors.py`, `_build_source_context` (524-602) pads with `rich.cells.cell_len` instead of counting characters.
- **Tests.** Human-mode CLI with a fixed console width: tok08 and tok08b show the error line's own text; tok33 highlights the right column; tok21 places the caret under the backtick.
- **Depends on:** LX-01 (F1 part); CLI-02 (F3 part, same files).

### Wave 1: parser

**PR-01: spans and parse diagnostics** (PAR-04, PAR-09, PAR-14, PAR-21, PAR-24). Lane F2. Class A.
- **Files:** `a7/parser.py`.
  - 1423: BINARY span runs from `left.span` start to `right.span` end. EXPRESSION_STMT and ASSIGNMENT spans cover the whole statement (1303-1327).
  - An `_error(msg, token)` helper passes `source_lines` at the 23 `from_token` call sites that omit it (e.g. 183-186, 211-214, 327-331, 597-601, 923, 1715).
  - Specific messages for `new T(args)` (1457-1463 is unreachable today), grouped parameters, `@label` not followed by a loop, `else` on the next line (q18) and a case body on the next line (p17).
  - 1623-1629: a type in value position raises "expected '{' to initialize inline struct".
  - 1682: the bare `except:` becomes `except ParseError`, and once `Name(types){` is seen the parser commits to a struct literal.
  - PAR-24: guard `Parser([])` (60); a proper message for `union(foo)`; `pub import` keeps its flag (stored only; its meaning belongs to MOD). Recovery keyed on message text goes away with PR-P.
- **Shared.** PAR-04 is the parser half of D7 "no line"; the other planner's divisor and binary diagnostics depend on it.
- **Tests.**
  - JSON spans: q14, q14b and q32 have non-null spans at the expression start.
  - Human output shows the source excerpt for the p03 error.
  - q22 exits 5 at the missing comma; q17 exits 5.
- **Replace:**
  - `test_parser_fuzzing.py:314` (claims every node has a span but walks only declarations and statements): use an explicit-stack walk over the 43 examples asserting every node has a span.
  - `test_parser_basic.py:350` and `test_parser_edge_cases.py:52, 108, 119, 133`, `test_parser_extreme_edge_cases.py:280`: AST-shape tests for every precedence level and for left associativity, with shapes written from SPEC 4.3.
- **Depends on:** LX-01 (expected columns).

**PR-02: struct-literal context, fn-type return, assignment targets, `defer`** (PAR-02, PAR-11, PAR-13, the `defer` half of PAR-20). Lane F2. Classes B and D, conditional on a scan.
- **Files:** `a7/parser.py`.
  - Delete the 10-token lookback in `_should_parse_struct_literal` (108-144). Replace `_suppress_struct_literals` (117, 1242-1245, 1280-1283) with an explicit "no struct literal" context: set for if/while conditions, for-iterables and match scrutinees; cleared inside `(`, `[`, call arguments, struct-literal bodies and blocks.
  - Fn-type return (806-814): parse a return type only if the next token can start a type.
  - `parse_expression_or_assignment` (1303-1327): the target must be IDENTIFIER, FIELD_ACCESS, INDEX or DEREF.
  - `defer` (2276): reject `ret`, `break`, `continue` and `fall` (q15 and q15b emit `defer void;`, which Zig rejects). Reject nested `defer` or a declaration only after a probe shows Zig rejects the emitted form.
- **Condition.** Run the P0b method: parse the 2440-program corpus with the old and new parser and diff the ASTs. If any difference falls in a program that builds today, it becomes packet item PR-A9. The only change expected is a bare struct literal in a condition longer than 10 tokens (inference; not scanned). If any non-literal assignment target builds today, it becomes PR-A10.
- **Tests.**
  - Runtime, Debug and ReleaseFast, outputs derived by hand: p03 prints `done`; q03; p04 prints `1`; p05; q04; q05.
  - p15, p15b and q19 compile and pass `zig build-obj`, with `S` and `Callback` present in the emitted Zig.
  - q16, q15 and q15b exit 5 with a location.
  - Counterexample: `if f(Pt{x: 1}) {` still parses a struct literal inside call arguments.
  - Extend `test_parser_error_handling_improvements.py:400-449` (short conditions only) with conditions longer than 10 tokens.
- **Depends on:** PR-00, PR-01.

**PR-03: declaration cap and parser warning** (PAR-17). Lane F2. P0.1 items 1 and 19 (classes A and D).
- **Files:** `a7/parser.py` 153-156 and 201-206. Remove the cap; the progress guard at 167-169 stays. Remove the stdout warning.
- **Tests.** 1100 constants plus `main` compile, the Zig passes build-obj, and JSON stdout parses.
- **Replace:** `test_parser_fuzzing.py:486-497`, which asserts the cap boundary.
- **Depends on:** Lane D adding the defect row first (`docs/plan/execution.md:117`).

**X-DEPTH: deep nesting becomes an internal error** (PAR-08, and the parser and exit-code part of PIP-14). Lane F2. Class A.
- **Files.** In `Parser.parse`, catch `RecursionError` around `parse_declaration`. After the stack unwinds, raise `ParseError("Nesting too deep")` at `self.current()`; the position survives the unwind. This relies on PR-01's `except ParseError`.
- **Rest of PIP-14.** The type-checker recursion is fixed by the other planner in Wave 2.2 (explicit stacks). Import recursion is fixed by MOD. PIP-14 closes when all three land.
- **Tests.** d01 (197 parentheses) and d03 (490 `else if` arms) exit 5 with a span. d02 and d04 still exit 0 (SPEC Appendix C minimum). After Wave 2.2, `deep_chain_3000` exits 0 and its Zig builds; that test is owned by lane S.

### Wave 1: pipeline, CLI and output

**CLI-01: output destinations and artifacts** (PIP-12, PIP-19, PIP-22, PIP-26, PIP-27). Lane F3. Class A. Fixes baseline failures #1-4.
- **Files.**
  - `a7/cli.py:54-58`: `--backend` gets `choices=list_backends()`.
  - `a7/cli.py:72-87`: `--output` equal to `--doc-out` after resolving is a usage error (exit 2).
  - `a7/compile.py:150-151`: resolve paths; refuse a destination equal to the input or to any loaded module file, checked before the writes at 434-451.
  - `a7/compile.py:436-482`: write to a temporary file in the same directory and `os.replace` it once all outputs are rendered; record which paths were written.
  - `a7/compile.py:779-782`: advertise only paths written in this run.
  - `a7/compile.py:848-850` and `:456-457`: use `Path(...).with_suffix(ext)`.
- **Tests.**
  - The 4 baseline tests.
  - `--output` pointed at an imported module file: refused, and the module bytes are unchanged.
  - Default output for `proj.a7dir/prog.a7` is `proj.a7dir/prog.zig`, and no `proj.zigdir` is created.
  - `--output X --doc-out X` exits 2.
  - `--backend nope` exits 2 in every mode.
  - A doc write into a read-only directory exits 3, and the `.zig` file is neither left on disk nor advertised.

**CLI-02: errors from imported modules** (PIP-11). Lane F3, plus a hook in lane S. Class A. Fixes baseline failures #6-8.
- **Files.**
  - `a7/module_resolver.py` `load_module` (113-196): per module, catch `CompilerError`, `OSError` and `UnicodeDecodeError`; attach the module's filename, source lines and the importer's IMPORT span. Surface the name-resolution errors that 164-166 drops.
  - `load_program_dependencies` (234-259): the "not found" error gets the import's span, and the message stops listing absolute search paths.
  - `a7/compile.py:246-250`: module tokenize and parse errors map to their own stage.
  - `_error_to_detail` (795-810): use `err.filename`.
  - `a7/errors.py` `format_error` (461-522): print `file:line:col`.
  - `_combined_program_for_file_modules` (597-627): stamp each merged declaration with its origin.
- **Shared hook with the other planner.** The type checker, validator and safety pass set `current_file` and `source_lines` from that origin when they visit a top-level declaration. Without it, baseline #8 stays red.
- **Tests.**
  - The 3 baseline tests.
  - m14 exits 4 and m15 exits 3, both with the module's file and span.
  - m32 exits 5.
  - m16's human output shows the module's own source line.
  - m29 has a span at the import and no absolute paths.
- **Depends on:** CLI-01 (same file). MOD must keep these tests passing.

**X-JSON: JSON validity and size** (PAR-05, PAR-16, PIP-16, PIP-25, TOK-26). Lane F3. Class A.
- **Files.**
  - `a7/formatters/json_formatter.py` `_ast_to_dict` (135-232): accept a node or a list for `else_case`; emit only fields that are present and not at their default; include `inline_type`.
  - `a7/compile.py` internal-error handler (491-503): if serialization fails, emit a payload without AST or tokens, never raise again.
  - `_to_json_payload` (731-793): tokens and source only in `--mode tokens`; AST only in `--mode ast` or on success.
  - `json.dumps` at 503, 508 and 715: compact separators.
  - PIP-25: `stages.<failed stage>.ok = false` for tokenize and codegen failures; `details[].message` without the `file:line:col:` prefix; one token-count rule.
  - Bump `schema_version` to `2.1`.
- **Later.** Normalizing the parser's `else_case` shape happens in ID-2.1.
- **Compatibility (not checked):** tests reading `stages.tokenize.tokens` on failure; README and site JSON examples.
- **Tests.**
  - p05b, p12b and n23 give valid JSON with exit 0 or 6 (never 1).
  - q13's JSON contains the inline struct's field names.
  - d07 `--mode ast --format json` stays under a fixed multiple of the source size; tok32's failure payload is under 2× the source.
  - All exit classes share the same top-level keys.

**X-RICH: Rich markup crashes and diagnostic stream** (TOK-06, PAR-07, PIP-13, PIP-24). Lane F3. Class A.
- **Files.**
  - `a7/formatters/console_formatter.py` 339-391, 446, 612-616, 673, 762: user text goes in `Text` objects.
  - `a7/compile.py` 521, 550-556, 723, 727: `Text` or `markup=False`.
  - `a7/compile.py:32`: success and inspection output stays on stdout; diagnostics (717-727) go to a `Console(stderr=True)`.
- **Compatibility (grep-verified):** `scripts/error_stage_common.py:86, 268` and `test/test_error_stage_matrix.py:69-240` join stdout and stderr; `test_cli_failures.py:123-146` reads only success output from stdout.
- **Tests.**
  - Modes tokens, ast, semantic, pipeline and `compile -v` on a source containing `"[/bold] and [red]x"`: exit 0, and the text appears verbatim.
  - Paths `[red]dir/x.a7` and `[/]x/p.a7` are printed verbatim with exit 0.
  - A semantic error writes to stderr and leaves stdout empty.

**NR-01: name-resolution duplicates and messages** (PIP-18 enum part, PIP-29, PIP-30, PIP-31). Lane S; the message change in `type_checker.py` is coordinated with the other planner. Classes B and A; the n09 part is packet item PL-A1.
- **Files.**
  - `a7/passes/name_resolution.py:130` (check the alias `define` result; its rejection waits for PL-A1).
  - `:287` (raise `DUPLICATE_VARIANT`).
  - `:158-173` (a local named like a generic parameter is an error).
  - `visit_statement` (401-517): a FUNCTION branch reporting "nested functions are not supported".
  - `a7/passes/type_checker.py:1189`: an "Undefined name" error instead of `UNDEFINED_TYPE`, and duplicate diagnostics removed.
- **Tests.**
  - n08 exits 6 at the second `A`.
  - n16c exits 6.
  - n06 exits 6 with the nested-function message.
  - An undefined `c` is reported once as "Undefined name 'c'".
  - n16b gives 2 errors, not 4.

### Wave 2

**ID-2.1: node identity (extends the execution plan's serial step)** (PAR-15, and the `type_args` addendum). All code lanes paused. Class A.
- **Additions to 2.1.**
  - `@dataclass(eq=False)` on `ASTNode`, with iterative `repr`, plus an `ast_equal()` helper for tests.
  - Declare every attribute that is set at runtime today (`inline_type`, `implicit_ref_args`, `implicit_deref_target`, `implicit_deref_object`, `cast_*`, `generic_mapping`, `file_module_call`, `module_emit_prefix`).
  - Match expressions get their own `else_expr` field; update `semantic_validator.py:315`, `zig.py:1081, 1180` and the JSON formatter.
  - Type `STRUCT_INIT.struct_type` as `str`.
  - Delete the dead fields `has_fallthrough`, `variant_type` and `type_args`, together with the unreachable branch `type_checker.py:501-511` (lane S) and `console_formatter.py:524` (F3, which should read `generic_params`).
- **Tests.** Two structurally identical parses compare unequal while `ast_equal` returns true. `==` and `repr` on a 3000-term chain raise no `RecursionError`. JSON content for match expressions is unchanged apart from the field name.
- **Risk.** Tests that compare ASTs with `==` break; their number was not checked.

**AST-INLINE: local inline struct** (parser addendum, q34). Lanes S then B. Class D.
- **Files.** `type_checker.py` STRUCT_INIT (~2745) resolves `node.inline_type` through `resolve_type_node`'s TYPE_STRUCT branch (490-498). `zig.py:1870-1895` emits an anonymous struct literal.
- **Unverified:** whether SPEC 6.1 shows the local form; `sincos` shows only the return-type form.
- **Tests.** q34 prints `1`; q13 still prints `1 2`.

**NR-02: scopes paired by node identity** (PIP-4, PIP-5, PIP-15, PIP-33). Lane S, shared with the other planner's TYP-01. Classes D and B.
- **Files.**
  - `name_resolution.py` `visit_statement` (401-517) records `scope_of[node_id]` for every node that opens a scope, and now also walks match-expression cases (never visited today, 496-514).
  - `type_checker.py` `_enter_matching_scope` (142-157) is replaced by a lookup on the node's ID. A missing scope is an internal error, not a new empty scope.
  - Symbols record their declaration order, and block lookups reject a use before the declaration (1179-1187, 742-744).
  - File-scope self-dependency is detected (n13).
- **Condition.** Corpus scan for type changes in programs that build today. Whether any exist was not verified by the audit.
- **Tests.**
  - n21, n02 and n23 compile and run with hand-derived output.
  - n03 and n14 exit 6 with the immutability error.
  - n01 exits 6 "used before declaration"; n13 exits 6; n12 still builds.
  - The perf_blocks timings go to a benchmark script, not a pytest assert.

**X-SYM: stdlib and module calls by resolved symbol.** Lanes S then B. Class C.
- **Scope.** No new audit IDs of mine close here. It completes PIP-3's local-shadow case and is shared with ZIG-5, SAF-9 and B14.
- **Approach.** The type checker records `resolved_symbol[node_id]` for identifiers and field-access objects. The preprocessor, the call path at `type_checker.py:1310-1325` and the backend's `_emit_call`, `_is_io_call` and `_scan_features` use only that.
- **Test.** First run a new run-allowed probe: `io :: import "std/io"`, and inside a block `io := Printer{println: say}; io.println("x")`, then `io.println("done")`. Expected output: `done` only. Current behavior is not verified.
- **Depends on:** NR-02; the module-symbol shape from MOD.

**MOD: module redesign** (PIP-1, 6, 7, 8, 9, 10, 17, 20, 32). Design pending; see §3.

**LX-P: lexer packet implementation** (TOK-01, 02, 05, 11, 12, 13, 14, 16, 17, 18, 19, 20, PIP-28). Lane F1, approved items only.

**PR-P: parser packet implementation** (PAR-03, 06, 10, 12, 18, 19, the block half of PAR-20, PAR-22). Lane F2.
- **Replace (from the parser audit's test-gap list):**
  - `test_parser_creative_cases.py:644`, which passes only because recovery drops `main`.
  - The `try/except ParseError: pass` blocks in `test_parser_advanced_edge_cases.py:122, 135, 147, 171, 298, 403, 427`.
  - The `assert True` endings in `test_parser_integration.py:366, 415, 461, 493, 527`.
  - The either-outcome tests in `test_parser_error_handling_improvements.py:238, 255, 271, 483-496`.
  - Tests that only check `PROGRAM`: all 31 in `test_parser_creative_cases.py` and all 35 in `test_parser_type_combinations.py`, among others. Rewrite them with shape assertions or delete them.
  - Tests asserting that banned syntax parses (`.adr`/`.val`, `new [N]T`, non-ASCII strings).

**NR-03: match capture rule** (PIP-21). This is the existing P5 item and belongs to the types packet. Lane S implements it after approval.

**CLEAN: dead code** (TOK-22, PAR-25, and TOK-21's unused `MAX_STRING_LENGTH`). Lanes F1 and F2, after LX-P and PR-P, because several error types that are unused today get raised by the packets. Replace the vacuous zero-`COMMENT`-token asserts in `test_tokenizer_aggressive.py:275-310, 557-576`.

**VIEWS: AST and report views** (PAR-23, PIP-34). Lane F3, low priority.
- Console and markdown trees show loop, defer and match bodies.
- `[None]i32` and dropped generic arguments are fixed.
- The markdown label bug at `markdown_formatter.py:264` is fixed.
- `format_type` uses an explicit stack.
- The `Compiled` line gets `soft_wrap`.

**DOC-LEX: SPEC lexical text** (TOK-28). Lane D, after the lexer packet decision. It also carries the doc rows from PR-P/PAR-22 and PL-A2.

### Wave 3

**SRC-MAP: source map and decoded literals** (TOK-29, TOK-23). Lanes F1 and IR.
- One source map per file (file ID, offsets, line table); tokens carry offsets, end positions and decoded values; spans can cover several lines.
- **Ordering.** After MOD (it needs file IDs) and before the IR builder in 3.1 hardens its span handling.

---

## 2. Waves, lanes and parallel worktrees

**Wave 1** (after the H0 probe runner): five worktrees in parallel. The critical patches (PR-00, PL-01, PL-02, BE-01) go to the main tree first; after that the usual F → S → B order applies.

| Worktree | Owned files | Serial order |
| --- | --- | --- |
| wt-F1 | `tokens.py`, `ast_nodes.py:536-604`, tokenizer tables in `errors.py` | LX-01 → LX-02 → LX-04 (tokenizer part) |
| wt-F2 | `parser.py` | PR-00 → PR-01 → PR-02 → X-DEPTH → PR-03 |
| wt-F3 | `compile.py`, `cli.py`, `formatters/*`, `module_resolver.py`, formatter part of `errors.py` | PL-02 → CLI-01 → CLI-02 → X-JSON → X-RICH → LX-04 (compile and resolver part) |
| wt-B | `zig.py`, `ast_preprocessor.py` (non-folding), `stdlib/*` (lane L) | PL-01 (merged with Lane B item 7) → BE-01 → LX-03, interleaved with the other planner's B items |
| wt-S | `name_resolution.py`, and `type_checker.py:1189` by agreement | NR-01, plus CLI-02's origin hook |

- **Serialization points:**
  - `errors.py` hunks from F1 and F3.
  - `compile.py`, which PL-02, CLI-01, CLI-02, X-JSON, X-RICH and LX-04 all touch.
  - `zig.py`, shared with the other planner's B batches.
- **Zig-heavy worktrees:** B, S, and the runtime tests in F3/F2. That respects the limit of 3 concurrent Zig builds.
- **Packets presented in Wave 1:** lexer, parser, pipeline/CLI.
- **Wave 1 exit:** the 8 baseline failures owned here pass (#1-4 in CLI-01, #5 in LX-01, #6-8 in CLI-02).

**Wave 2:**
1. ID-2.1, serial.
2. In parallel: wt-F1 LX-P; wt-F2 PR-P; wt-S NR-02 → X-SYM (with B) → NR-03 (after P5); wt-B AST-INLINE (after its S part); wt-F3 VIEWS.
3. MOD implementation goes after NR-02, and after X-SYM, because they share `name_resolution.py`, `type_checker.py`, `compile.py` and `zig.py`. PL-02 is removed when MOD lands.
4. CLEAN after LX-P and PR-P. DOC-LEX last, in lane D.

**Wave 3:** SRC-MAP, and the PIP-35 leftovers, removed as MOD and the IR replace that code.

---

## 3. Module redesign: what the rest of the pipeline needs, and ordering

**What the design must provide:**
1. Module identity keyed by resolved file path, including the main file (m11 double merge, m09 self-import).
2. A symbol table per module, with the import alias bound as a `MODULE` symbol in the importer's file scope that points at the module's exports. X-SYM, PIP-1 and PIP-9's type checking resolve `alias.member` through it.
3. An origin (file ID, filename, line table) on every declaration and node. CLI-02's hook and SRC-MAP depend on it, and the tests from CLI-02 must keep passing.
4. Iterative loading with the SPEC depth limit of 32 (`docs/SPEC.md:2145`) and a cycle diagnostic at the IMPORT span (PIP-10 and the import half of PIP-14). Tokenize, parse and IO errors from modules keep their stage exit codes.
5. The same module processing in every semantic mode (PIP-17), so ID-2.1's node numbering covers module nodes in `--mode semantic` too.
6. Emitted names for every declaration kind and every call site, including calls inside a module (PIP-6) and type references like `mod.Point` (`docs/plan/execution.md:190`).
7. The set of loaded module files, exposed to CLI-01's destination guard.
8. IMPORT declarations kept on each module, so the transitive closure can be merged (PIP-8).
9. Unique node IDs across modules.

**Decisions for the modules packet** (not designed here): visibility (f01, f02), cycles (m10), named and bare imports (m26, m27), local `io.a7`/`math.a7` versus virtual modules (PIP-32), `using import` (cross-reference PR-A6), `pub import` (PAR-24), duplicate aliases (cross-reference PL-A1), and whether PL-02 stays until MOD.

**Ordering:**
- After Wave 1 CLI-01 and CLI-02 (their tests become the contract).
- After ID-2.1 and NR-02 (scopes by node).
- Before X-SYM's file-module part.
- Before Wave 3's IR builder (3.1) and the multi-file app (3.8).
- PIP-35's dead `ModuleTable`, `topological_sort` and resolver helpers are deleted inside MOD.

---

## 4. Work shared with the other planner

| Shared root cause | My IDs | Their IDs | Batch and owner |
| --- | --- | --- | --- |
| Node identity | PAR-15, type_args addendum | Wave 2.1 node_id | ID-2.1, serial |
| Stdlib recognized by name text | PIP-2, PIP-3, PIP-23 | ZIG-5, SAF-9, B14 | PL-01 (Wave 1) and X-SYM (Wave 2) |
| Scope pairing by position | PIP-4, PIP-5, PIP-33, PIP-15 | TYP-01 (use before declaration) | NR-02, lane S |
| Rich markup crashes | TOK-06, PAR-07, PIP-13 | none | X-RICH, lane F3 |
| Recursion limit gives exit 8 | PAR-08, PIP-14 | type-checker stacks (Wave 2.2) | X-DEPTH plus S 2.2 plus MOD |
| JSON crash and payload size | PAR-05, PAR-16, PIP-16, TOK-26 | none | X-JSON; parser shape in ID-2.1 |
| BINARY nodes without spans | PAR-04 | D7 divisor diagnostics | PR-01 lands first |
| Error origin per declaration | PIP-11 | per-declaration `current_file` in the type checker, validator and safety pass | CLI-02 hook |
| Zig-reserved names | TOK-14 (`__a7_*` clash), TOK-16 (`type := 1`) | Lane B item 4 (B12) | Lane B item 4 |
| Unused `_x` bindings | none | Lane B item 4 | none |

---

## 5. Approval packets

Each example shows current and proposed behavior. Line numbers inside an example count from its first line.

### Lexer packet (replaces the lexical half of P1, and P2)

**LX-A1: unclosed block comment is an error** (TOK-05).
```a7
main :: fn() {}
/* note
helper :: fn() {}
```
- Current: exit 0; `helper` is silently dropped.
- Proposed: exit 4, "The comment is not closed", at 2:1.
- Also proposed: `*/` with no opening comment is an error (TOK-28; it currently lexes as `*` then `/`).
- Impact: `examples/003_comments.a7:28-30` changes (its golden output does not); tests `test_tokenizer.py:136-162` and `test_tokenizer_aggressive.py:298-303` change.

**LX-A2: a newline inside `/* */` ends the statement** (TOK-12).
```a7
a := 5
b := 3
x := a /* note
*/ -b
io.println("{}", x)
```
- Current: prints `2`.
- Proposed: prints `5`, the same as when the newline is outside the comment (tok36b).
- Impact (grep-verified): the block comments in `examples/003_comments.a7` sit on their own lines, so the extra terminator merges with the existing one.

**LX-A3: a digit or letter directly after a number is an error** (TOK-02, TOK-20).
- `x := 0b12`: current prints `1`; proposed exit 4, "invalid digit '2' in binary literal".
- `1.5.25`: current prints `1.5`; proposed exit 4.
- `y := p.5`: current emits `const y = p; _ = 0.5;`; proposed exit 4.
- `0X2A`: current exit 6, "Undefined type"; proposed exit 4, "radix prefix must be lowercase".

**LX-A4: only ASCII digits in numbers** (the packet half of TOK-03).
- `x := 1٣`: current prints `13`; proposed exit 4 at the Arabic digit.
- Sub-choice: keep `0x_1` (recommended; it builds today) or allow `_` only between digits.

**LX-A5: `\xHH` escapes and SPEC Appendix D** (TOK-01, TOK-13).
- `io.println("\xff\x80A")`: current output bytes `c3 bf c2 80 41 0a`.
  - Option (a), follow SPEC D.1 "ASCII only": exit 4.
  - Option (b): output bytes `ff 80 41 0a`.
- `"\b"`, `"\f"`, `"\v"`, `"\a"`: current exit 4. Either accept them as in Appendix D or remove them from the SPEC. SPEC 2.6 and Appendix D contradict each other.
- Impact: `test_parser_creative_cases.py:696` uses `"\xFF"`.

**LX-A6: non-ASCII in strings, chars and comments** (TOK-17, the lexer half of TOK-07; existing P2/G6).
- `io.println("café")` prints its UTF-8 bytes today; `c := 'é'` builds.
- Options: ASCII-only source (exit 4), or UTF-8 strings with ASCII-only chars.
- The emitter half (LX-03) goes ahead regardless.

**LX-A7: a string cannot contain a raw newline** (TOK-11).
```a7
io.println("line one
    still in string")
```
- Current: exit 0; prints two lines.
- Proposed: exit 4, "The string is not closed", at the opening quote, 1:12.

**LX-A8: tabs inside strings and comments** (TOK-18).
- A tab inside `"a<TAB>b"` or `// tab<TAB>here`: current exit 0.
- Options: exit 4, as SPEC 2.1 says, or change the SPEC to "outside literals and comments" (recommended, since `\t` exists).

**LX-A9: carriage returns** (TOK-19).
- A raw CR inside a string: current output `61 0a 62` (read with universal newlines).
- Options: reject a raw CR inside literals, or keep it as `0d`. CRLF files keep working either way.

**LX-A10: reserved leading underscore** (TOK-14).
- `_x := 1`: current prints `1`.
- Options: exit 4 per SPEC 2.3, or reserve only `__a7`.

**LX-A11: keyword and punctuation set** (TOK-16; existing P1).
- `x := 5 # note` compiles today (D8).
- `0...5` lexes as `0`, `..`, `.5`.
- `?` is not a token.
- `int`, `uint`, `float`, `let`, `as` and `where` are keywords the parser never accepts. `let := 1` fails with "Unexpected token '}'".
- SPEC keywords `cast`, `const`, `self`, `size_of`, `type`, `using` and `var` lex as identifiers.
- Proposed: the owner chooses the set. `type := 1` is already fixed without asking by Lane B item 4.

**LX-A12 (conditional): Unicode `$T` names** (TOK-09).
- `$Té`: present only if the LX-02 probe finds a program with one that builds.

**LX-A13: empty source file** (PIP-28).
- A 0-byte `.a7`: current exit 0 and a 0-byte `.zig`.
- Proposed: exit 4, "file is empty" (`FILE_EMPTY` exists at `errors.py:37`), or keep.

### Parser packet (replaces the parser half of P1)

**PR-A1: every parse error fails the compile** (PAR-03, F2/C5; also removes recovery keyed on message text from PAR-14 and PAR-24).
```a7
helper :: fn() {
    x :=
    limit: i32 = 42
}
main :: fn() { io.println("{}", limit) }
```
- Current: prints `42`.
- Proposed: exit 5, "Expected expression", at 2:9.
- Impact: q10 destructuring and q20 `new Pt(1)` become parse errors; `docs/SPEC.md:254, 281, 296, 383` snippets stop compiling.

**PR-A2: duplicate `else`, and `case` after `else`** (PAR-10).
```a7
match x {
    case 1: io.println("one")
    else: io.println("first else")
    else: io.println("second else")
}
```
- Current: prints `second else`.
- Proposed: exit 5, "duplicate else arm", at 4:5.
- Also decide whether `case` after `else` is allowed (p12c prints `one` today).

**PR-A3: `$T` in expression position** (PAR-12).
- With `T :: 5`, `y := $T`: current prints `5`.
- Proposed: exit 5, "`$T` is only valid in type or size positions". `[$N]$T` keeps working.

**PR-A4: separators are required** (PAR-19).
- `x := 1 y := 2` prints `1`; proposed exit 5, "expected newline or ';'".
- `p: Pair(i32 bool)`: current exit 0; proposed exit 5, "expected ','".
- `S :: struct { a: i32 b: i32 }`, `for i := 0;; i < 3; i += 1`, `N(,) :: 5`: all proposed errors.

**PR-A5: `if` and `while` bodies need a block** (the block half of PAR-20).
- `if x > 0 ret 1`: current prints `1`.
- Proposed: exit 5, "expected '{' after condition".

**PR-A6: `using import`** (PAR-18).
- `using import "std/math"` after other declarations: current exit 0, with `using` silently dropped.
- Proposed: exit 5, "`using import` is not supported". Its future meaning belongs to the modules packet.

**PR-A7: newlines inside array literals, positional struct literals and import lists** (PAR-06). This only accepts more programs, but SPEC does not document it.
```a7
arr: [3]i32 = [
    1,
    2,
    3
]
```
- Current: exit 5. The positional `Pt{\n 1,\n 2\n}` form exits 0 with no `main` emitted.
- Proposed: both compile and print `1`.

**PR-A8: `pub` on struct fields** (PAR-22; SPEC 10.4 contradicts 13.2).
- `P :: struct { pub x: i32 }`: current prints `1`.
- Options: keep it and fix SPEC 10.4, or reject it and fix 13.2.
- The other PAR-22 rows are documentation-only and go to lane D.

**PR-A9 and PR-A10 (conditional).** A bare struct literal in a condition longer than 10 tokens, and non-literal assignment targets. Present only if PR-02's corpus scan finds a program that builds today.

### Pipeline and CLI packet

**PL-A1: name clashes with import aliases** (the packet part of PIP-18).
```a7
io :: fn() {}
io :: import "std/io"
main :: fn() { io() }
```
- Current: exit 0; the import is silently ignored.
- Proposed: exit 6, "Already defined: io".
- Also reject two imports with the same alias (m23), unless a probe shows Zig already rejects every such form.

**PL-A2: bare typed math names** (PIP-23).
- `sqrt_f64(9.0)` with no user function: current exit 6, "Undefined".
- Options: implement them at the lowest lookup priority per SPEC A.3, or remove the claim at `docs/SPEC.md:1571-1572` and `site/public/docs/stdlib.md:36` (both grep-verified).
- PL-01's code fix is correct under either choice.

**PL-A3 (cross-reference).** PIP-21 capture rule: this is P5 and is presented in the types packet.

Modules-packet inputs are listed in §3.

---

## 6. Deferred or not fixed

- **TOK-21 (length caps).** No observed failure. Caps on `$` and `@` names or on strings would reject programs that build today. The unused constant is deleted in CLEAN. Revisit with G6.
- **PIP-35 (dead code and structural blockers).** Removed by MOD (the resolver's `ModuleTable`, `topological_sort`) and by the Wave 3 IR (duplicated stdlib recognition, AST mutation). Deleting `semantic_context.errors` is left to lane S. Removing any of it earlier is churn in code about to be replaced.
- **Sub-items:**
  - TOK-08 float underflow goes to G1/P4.
  - PAR-24's quadratic speculative parse is bounded by X-DEPTH; revisit only if PR-02 keeps speculation.
  - PAR-15 item 5 (moving analysis annotations into side tables) goes to Wave 3 IR.

---

## 7. Coverage table

| ID | Batch | ID | Batch | ID | Batch |
| --- | --- | --- | --- | --- | --- |
| TOK-01 | LX-P (A5) | PAR-01 | PR-00 | PIP-1 | MOD (stopgap PL-02) |
| TOK-02 | LX-P (A3) | PAR-02 | PR-02 | PIP-2 | PL-01 |
| TOK-03 | LX-02 (A4 in packet) | PAR-03 | PR-P (A1) | PIP-3 | PL-01 (finished by X-SYM) |
| TOK-04 | LX-01 | PAR-04 | PR-01 | PIP-4 | NR-02 |
| TOK-05 | LX-P (A1) | PAR-05 | X-JSON | PIP-5 | NR-02 |
| TOK-06 | X-RICH | PAR-06 | PR-P (A7) | PIP-6 | MOD |
| TOK-07 | LX-03 (A6 in packet) | PAR-07 | X-RICH | PIP-7 | MOD |
| TOK-08 | LX-02 | PAR-08 | X-DEPTH | PIP-8 | MOD |
| TOK-09 | LX-02 | PAR-09 | PR-01 | PIP-9 | MOD |
| TOK-10 | LX-04 | PAR-10 | PR-P (A2) | PIP-10 | MOD |
| TOK-11 | LX-P (A7) | PAR-11 | PR-02 | PIP-11 | CLI-02 |
| TOK-12 | LX-P (A2) | PAR-12 | PR-P (A3) | PIP-12 | CLI-01 |
| TOK-13 | LX-P (A5) | PAR-13 | PR-02 | PIP-13 | X-RICH |
| TOK-14 | LX-P (A10) | PAR-14 | PR-01 | PIP-14 | X-DEPTH |
| TOK-15 | LX-02 | PAR-15 | ID-2.1 | PIP-15 | NR-02 |
| TOK-16 | LX-P (A11) | PAR-16 | X-JSON | PIP-16 | X-JSON |
| TOK-17 | LX-P (A6) | PAR-17 | PR-03 | PIP-17 | MOD |
| TOK-18 | LX-P (A8) | PAR-18 | PR-P (A6) | PIP-18 | NR-01 (A1 in packet) |
| TOK-19 | LX-P (A9) | PAR-19 | PR-P (A4) | PIP-19 | CLI-01 |
| TOK-20 | LX-P (A3) | PAR-20 | PR-02 (A5 in packet) | PIP-20 | MOD |
| TOK-21 | Deferred | PAR-21 | PR-01 | PIP-21 | NR-03 (types packet, P5) |
| TOK-22 | CLEAN | PAR-22 | PR-P (A8) | PIP-22 | CLI-01 |
| TOK-23 | SRC-MAP | PAR-23 | VIEWS | PIP-23 | PL-01 (A2 in packet) |
| TOK-24 | LX-02 | PAR-24 | PR-01 | PIP-24 | X-RICH |
| TOK-25 | LX-04 | PAR-25 | CLEAN | PIP-25 | X-JSON |
| TOK-26 | X-JSON | Addendum: `type_args` dead branch | ID-2.1 | PIP-26 | CLI-01 |
| TOK-27 | LX-01 | Addendum: local inline struct | AST-INLINE | PIP-27 | CLI-01 |
| TOK-28 | DOC-LEX | Addendum: redirected stdout | BE-01 | PIP-28 | LX-P (A13) |
| TOK-29 | SRC-MAP | | | PIP-29 | NR-01 |
| | | | | PIP-30 | NR-01 |
| | | | | PIP-31 | NR-01 |
| | | | | PIP-32 | MOD |
| | | | | PIP-33 | NR-02 |
| | | | | PIP-34 | VIEWS |
| | | | | PIP-35 | Deferred |

Counts: TOK 29, PAR 25 plus 3 addenda, PIP 35.

---

## 8. Risks and verification

**Per batch:**
- Write the failing test first and confirm it fails on the current tree.
- The verifier derives expected output before reading the implementation report and runs one counterexample (listed in each batch).
- Only run-allowed probes are executed, through `scripts/run_probe.py` (H0). Compile-only probes are never run.
- Tests copy probe sources into `test/fixtures/regressions/<component>/`. They must not read `tmp/`, which is excluded from the repo and pytest collection per P0.6.
- New walkers (PL-02, X-JSON, LX-04, VIEWS) get a recursion-limit-100 test in `test/test_iterative_traversal.py`.

**Gate:**
- After each patch, run `./run_all_tests.sh` in the background with `timeout 2700`.
- Compare with `docs/audits/2026-09-16/baseline.md`: 11 of 12 checks pass, and the pytest failure count only goes down.
- #5 closes with LX-01, #1-4 with CLI-01, #6-8 with CLI-02. #9-12 belong to the other planner.

**Compatibility scans** (examples, goldens, tests, SPEC, site):
- Required for every batch that needs no approval. PR-02 and NR-02 also get the 2440-program corpus diff (AST, or types for NR-02).
- Any hit on a program that builds today moves that item into its area's packet.

**GLM review (ledger L12):**
- PL-01, PL-02 and X-SYM: miscompile fixes.
- CLI-01: path and destination handling.
- CLI-02: path leakage in messages.

**Risks:**
1. **LX-01 column shift.** Every parse and JSON column moves. Expected spans in tests must be rewritten by hand, not captured from a rerun.
2. **PR-02 regressions.** Replacing the heuristic could change how examples parse; mitigated by the corpus diff and the 43-example gate.
3. **CLI-02 needs lane S's origin hook.** If the hook slips, baseline #8 stays red and the Wave 1 exit is blocked. Land the hook in wt-S next to NR-01.
4. **X-JSON schema change.** Could break external consumers. Bump `schema_version`, add a CHANGELOG entry, and scan site JSON examples (not checked).
5. **X-RICH moves diagnostics to stderr.** User-visible; add a CHANGELOG entry. Harness compatibility is grep-verified only for the files named in X-RICH.
6. **BE-01 changes every emitted preamble.** Text-matching tests in `test_codegen_zig.py` need updates. Pipe output, and therefore goldens, should not change (inference).
7. **ID-2.1 `eq=False`.** Breaks tests that compare ASTs with `==`; the count was not checked.
8. **MOD replaces the internals of PL-02 and CLI-02.** Their tests are the contract MOD must keep passing.
9. **Serialization bottlenecks.** `errors.py` and `compile.py` patches collide unless applied strictly in the orders in §2.

## 9. Not verified

- BE-01's mechanism: read from the Zig 0.16.0 std source, not run.
- Whether a local `io` shadowing a real `std/io` alias miscompiles (X-SYM probe).
- Whether any program with a Unicode `$T` name builds (LX-A12).
- Whether Zig itself accepts `0x_1`.
- Whether any program that builds today is affected by PR-02 (bare struct literal in a condition over 10 tokens, non-literal assignment targets) or by NR-02 (type changes).
- Whether SPEC 6.1 documents the local inline-struct form (AST-INLINE's class D).
- Whether the `defer defer` and declaration-after-`defer` forms are rejected by Zig.
- Whether duplicate import aliases are always rejected by Zig.
- How many tests use AST `==`.
- How tests and site docs consume the JSON output.
- Test-file line ranges cited from the parser audit's delegated read that the audit itself did not spot-check.

### Critical files for implementation
- /home/cx89/Projects/pl-dev/a7-py/a7/parser.py
- /home/cx89/Projects/pl-dev/a7-py/a7/tokens.py
- /home/cx89/Projects/pl-dev/a7-py/a7/compile.py
- /home/cx89/Projects/pl-dev/a7-py/a7/module_resolver.py
- /home/cx89/Projects/pl-dev/a7-py/a7/formatters/json_formatter.py
