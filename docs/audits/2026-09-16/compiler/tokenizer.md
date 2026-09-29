> **Source:** Claude audit subagent, full audit of the A7 compiler component `tokenizer`, run against commit `701c679` with Zig 0.16.0; shared instructions in `tmp/audit/compiler/PROMPT-COMMON.md`.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim. Probes and logs it cites stay under `tmp/audit/compiler/tokenizer/`, which is not tracked.

# Tokenizer audit (component prefix TOK)

Auditor scope: `a7/tokens.py` (1018 lines, read in full); `a7/errors.py` (963 lines, read in full; lexical parts are
`TokenizerErrorType`, the message and advice tables, `SourceSpan`, `ErrorFormatter`, `CompilerError`,
`TokenizerError`); `a7/cli.py` (read in full); the `--mode tokens` path in `a7/compile.py:112-216, 486-557, 669-810`;
`a7/formatters/console_formatter.py:1-35, 339-391`, `json_formatter.py:1-68`, `markdown_formatter.py:60-75`; tests
`test/test_tokenizer.py`, `test/test_tokenizer_aggressive.py`, `test/test_tokenizer_errors.py` (read in full). To trace
literal values downstream I also read `a7/ast_nodes.py:536-604` and `a7/backends/zig.py:1470-1503, 2282-2311`.

Revision: working tree at `701c679`; `a7/tokens.py`, `a7/errors.py`, `a7/cli.py`, `a7/compile.py`, `a7/ast_nodes.py`
and `a7/backends/zig.py` are unmodified relative to that commit (git status snapshot). Toolchain: Zig 0.16.0, uv 0.12.6.

Working files, all under `tmp/audit/compiler/tokenizer/`:

- `probe_direct.py` / `probe_direct.out`: direct `Tokenizer(...)` calls on about 100 inputs.
- `make_probes.py`: generates the `.a7` probes in `probes/` (non-ASCII and control bytes are built with `chr()`).
- `run_probes.py` / `run_probes*.out`: for each probe, `uv run a7 <probe> --format json --output probes/out/<name>.zig`,
  then the human run, then `zig build-obj -fno-emit-bin` from `probes/out/` if the compile exited 0.
- `run_exec.out`, `run_probes4.out`, `run_probes5.out`: `zig build-exe -ODebug` and `-OReleaseFast` for the
  `run-allowed` probes, plus `od` dumps of stdout.
- `human_dump.out`, `zig_dump.out`, `tokens_mode.out`, `markup_modes.out`, `perf.out`, `big_json.out`,
  `spec_escapes.out`, `pytest_tokenizer.out`, `pytest_diag.out`.

Known-defect sources used for classification: `docs/plan/README.md` (sections "Documentation defects for track 0" and
"Defects reproduced in Wave 0") and `docs/plan/audit/evidence/2026-09-16-ledger-part1.md`, `-part2.md`. Some NEW findings
were reported earlier in `docs/audits/2026-09-14/pipeline-glm-review.md` (H-4, H-10, M-3, M-8). That report is not in the
known set, so these are marked NEW and cite it.

## Summary

| Severity | NEW | KNOWN | Total |
|----------|-----|-------|-------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 4 | 1 | 5 |
| MEDIUM | 10 | 0 | 10 |
| LOW | 12 | 2 | 14 |
| Total | 26 | 3 | 29 |

| ID | Sev | Status | One line |
|----|-----|--------|----------|
| TOK-01 | HIGH | NEW | `"\x80"`..`"\xff"` string escapes are emitted as 2-byte UTF-8 (miscompile, run-confirmed) |
| TOK-02 | HIGH | NEW | Malformed numeric literals split into two tokens and compile with a different value (`0b12` prints 1) |
| TOK-03 | HIGH | NEW | Underscore and non-ASCII digit forms pass the lexer, then crash `int()`/`float()` (exit 8) or silently compile |
| TOK-04 | HIGH | NEW (symptom recorded as B16 item 5) | Operator, `;` and newline token columns are too small by the token length; column 0 reaches JSON |
| TOK-05 | HIGH | KNOWN (F1) | Unclosed `/*` swallows the rest of the file with exit 0 |
| TOK-06 | MEDIUM | NEW | Rich markup in a string literal crashes `--mode tokens/ast/semantic/pipeline` and `compile -v` (exit 8) |
| TOK-07 | MEDIUM | NEW (extends F6b/F6c) | Control bytes and non-ASCII code points in char/string literals reach Zig unvalidated; Zig rejects |
| TOK-08 | MEDIUM | NEW | `1e999` becomes Python `inf` and is emitted as `inf.0`; Zig rejects |
| TOK-09 | MEDIUM | NEW | `@label` and `$T` accept Unicode letters; a Unicode label emits a non-ASCII Zig identifier; `@` alone lexes |
| TOK-10 | MEDIUM | NEW | Line-separator characters in comments/strings desync `source_lines`; diagnostics show the wrong source line |
| TOK-11 | MEDIUM | NEW | A missing closing quote runs across lines; the error names a later line, or the program compiles |
| TOK-12 | MEDIUM | NEW | A newline inside `/* */` is not a terminator; `x := a /*\n*/ -b` computes `a - b` (run-confirmed) |
| TOK-13 | MEDIUM | NEW | SPEC escapes `\b \f \v \a` rejected; SPEC's ASCII-only `\xHH` accepts 0x80-0xFF |
| TOK-14 | MEDIUM | NEW | Leading-underscore names are not reserved; `__a7_stdout_print` user function makes Zig reject |
| TOK-15 | MEDIUM | NEW | Every char-literal error says "The char is not closed" (bad escape, empty, multi-char) |
| TOK-16 | LOW | KNOWN (D5, D8, D9, B12) | Keyword and punctuation set differs from SPEC; extra details below |
| TOK-17 | LOW | KNOWN (F6b, F6c) | Non-ASCII accepted in strings, chars and comments against SPEC 2.1 / Appendix D |
| TOK-18 | LOW | NEW | Tabs inside strings, chars and comments are accepted against SPEC 2.1 |
| TOK-19 | LOW | NEW | File read uses universal newlines: raw CR or CRLF inside a string becomes LF; CR alone terminates statements |
| TOK-20 | LOW | NEW | Uppercase radix prefixes (`0X2A`) split into `0` and an identifier; misleading "Undefined type" error |
| TOK-21 | LOW | NEW | `MAX_STRING_LENGTH` unused and disagrees with SPEC Appendix C; `$`/`@` names have no length cap |
| TOK-22 | LOW | NEW | Dead code: unused imports, 6 never-produced and 6 never-consumed token types, 8 never-raised error types, unreachable branches |
| TOK-23 | LOW | NEW | Spans of multi-line tokens are computed as single-line (`end_column` past end of line) |
| TOK-24 | LOW | NEW | Diagnostics echo raw NUL/control bytes; invalid UTF-8 reports a byte offset, not line/column, as an IO error |
| TOK-25 | LOW | NEW | Caret misalignment for wide characters and for a BOM on line 1 in later-stage diagnostics |
| TOK-26 | LOW | NEW | `--format json` on any failure serializes all tokens, source and AST (458 KB source gives a 64 MB payload) |
| TOK-27 | LOW | NEW | Lexer throughput about 1.9 MB/s; `_try_operator` rebuilds a 23-entry dict per call |
| TOK-28 | LOW | NEW | SPEC lexical text drift: B.2 error format, 2.3 EBNF forbids leading `_`, advice text for generics |
| TOK-29 | LOW | NEW | Structure: tokens carry raw text only, no offsets; literal decoding lives in `ast_nodes.py`; three `splitlines()` copies |

---

## HIGH

### TOK-01 HIGH NEW: string hex escapes `\x80`..`\xff` are emitted as two UTF-8 bytes

What is wrong: the tokenizer accepts any two hex digits after `\x`. `_unescape_literal_content` turns `\xff` into the code
point U+00FF, and `_quote_zig_string` writes that code point raw into the UTF-8 Zig file. The one byte 0xFF becomes the
two bytes C3 BF, and `\x80` becomes C2 80. The program builds and prints different bytes from the ones the source asks for.

Evidence:

- `a7/tokens.py:630-648` accepts `\x` plus two hex digits with no range check.
- `a7/ast_nodes.py:562-563`: `out.append(chr(int(content[i + 2 : i + 4], 16)))`.
- `a7/backends/zig.py:2297-2303`: only `code < 0x20 or code == 0x7F` becomes `\xHH`, otherwise `out.append(ch)`.
- Probe `probes/tok01_hex_escape_high.a7` (run-allowed): `io.println("\xff\x80A")`.
  - Compile: `uv run a7 probes/tok01_hex_escape_high.a7 --format json --output probes/out/tok01_hex_escape_high.zig`,
    exit 0. `zig build-obj -fno-emit-bin`, exit 0.
  - Emitted line (od): `__a7_stdout_print(" 303 277 302 200 A \ n "`.
  - Run, Debug and ReleaseFast, exit 0. stdout bytes `c3 bf c2 80 41 0a`. The expected bytes are `ff 80 41 0a`
    (`run_exec.out:2-13`).
- Probe `probes/tok31_hex_escape_print.a7`: `io.println("\xff")` prints `c3 bf 0a` in both modes.
- SPEC `docs/SPEC.md:2170`: "`\xHH` | 0-127 | Hex escape (2 digits, ASCII only)". The tokenizer should have rejected these
  escapes (see TOK-13).
- `test/test_parser_creative_cases.py:696` uses `s5 := "\x00\xFF\x7F"` in a parse-only test.

Fix direction: decide the meaning of `\x80`-`\xff` (gate G6). Either reject them in the tokenizer, as the SPEC says, or carry
bytes rather than code points and emit `\xHH` for every non-ASCII byte in `_quote_zig_string`. Changes accepted programs:
yes. Rejection removes programs that compile today, and byte emission changes their output. Needs owner approval.

### TOK-02 HIGH NEW: malformed numeric literals split silently and compile with a different value

What is wrong: every number scanner stops at the first character that is not a digit and does not check what follows. Then
`0b12` lexes as `0b1` and `2`, `0o78` as `0o7` and `8`, `1.5.25` as `1.5` and `.25`, and `p.5` as `p` and `.5`. Statement
terminators are optional in the parser, so the second token becomes a separate expression statement and the program builds.

Evidence:

- `a7/tokens.py:428` (binary loop):
  `while self.current_char() and (self.current_char() in "01" or self.current_char() == "_"):`, followed at `:455` by
  `self._add_token(TokenType.INTEGER_LITERAL, number_text, start_column)` with no check of the next character. The same
  shape appears at `:464` (hex), `:500` (octal) and `:532-541` (decimal and fraction, where
  `:536` `if self.current_char() == "." and self.peek_char() != ".":` starts a new fraction scan that the next `.` ends).
- `probe_direct.out:85-96`: `0b12` gives `INTEGER_LITERAL '0b1'` then `INTEGER_LITERAL '2'`; `0x1G` gives `0x1` then
  `IDENTIFIER 'G'`; `0o78` gives `0o7` then `8`.
- `probes/tok28_bin_split_run.a7` (run-allowed): `x := 0b12`, then print x. Exit 0; emits `const x = 1;`. Prints `1` in
  Debug and ReleaseFast (`run_exec.out:61-73`).
- `probes/tok30_octal_split_run.a7`: `x := 0o78` prints `7`. `probes/tok29_float_split_run.a7`: `x := 1.5.25` prints
  `1.5`.
- `probes/tok15a_bin_split.a7`: emits `const x = 1; _ = x; _ = 2;` (`zig_dump.out:72-77`).
- `probes/tok23_dot_digit.a7`: `y := p.5` emits `const y = p; _ = 0.5;`, exit 0, `zig build-obj` exit 0.
- Previously reported as a confusing parse error in `docs/audits/2026-09-14/pipeline-glm-review.md` M-8. Today it compiles.

Fix direction: after any numeric literal, reject an immediately following identifier character, digit outside the radix, or
`.` followed by a digit, with an "invalid digit in literal" diagnostic. The parser's optional-terminator rule (prior M-7)
is a separate issue. Changes accepted programs: yes (these programs stop compiling). A7 source with these typos is
unlikely to be intended, but this still needs approval under the language-change rule.

### TOK-03 HIGH NEW: literal forms accepted by the lexer crash the literal decoder or pass as non-ASCII digits

What is wrong: the lexer consumes `_` anywhere after the first digit and uses Unicode `str.isdigit()`. Python's
`int()`/`float()` reject `1_`, `1__0`, `0x1_`, `0x__1`, `1_e5`, `1._5`, `1.5_`, `1e1_` and `²`. The `ValueError` escapes
as an internal error, exit 8, with no span. Non-ASCII decimal digits that `int()`/`float()` accept (`1٣`, `1.５`)
compile silently as ASCII values, while non-ASCII letters in identifiers are rejected.

Evidence:

- `a7/tokens.py:307` `if self.current_char() and self.current_char().isdigit():`, and likewise `:312, 532, 540, 553,
  564`, use `isdigit()` with no `isascii()` guard. Compare identifiers at `:328-329`, which check `isascii()`.
- `a7/tokens.py:532` `while self.current_char() and (self.current_char().isdigit() or self.current_char() == "_"):`, and
  likewise `:428, 464, 500, 540, 564`, accept `_` in any position.
- `a7/ast_nodes.py:587` `value = int(value_str)` and `:590` `float(token.value)` decode with no error handling.
- `run_probes.out:9-24`: probes `tok04_0` .. `tok04_7` all exit 8. JSON gives `category internal`,
  `exc=ValueError` and `span=None`, for example `"invalid literal for int() with base 10: '1_'"`. Human output:
  `Unexpected error: invalid literal for int() with base 10: '1_'`.
- `tok04_8_underscore` (`0x_1`) exits 0, because Python accepts one `_` after the prefix. The accepted set therefore depends
  on Python's grammar.
- `tok05a_superscript` (`x := ²`) exits 8, `ValueError`. `tok05b_arabic` (`x := 1٣`) exits 0 and emits
  `const x = 13;`. `tok05c_fullwidth_float` (`1.５`) exits 0 and emits `const x = 1.5;` (`zig_dump.out:17-50`).
- SPEC `docs/SPEC.md:145` says only "Underscores can be used as separators for readability", with no placement rule.
  `docs/SPEC.md:83` defines `digit = "0"..."9" ; ASCII digits only` for identifiers.
- The superscript case was previously reported in `docs/audits/2026-09-14/pipeline-glm-review.md` H-10.

Fix direction: define underscore placement in the SPEC (for example, only between two digits). Enforce it in the lexer and
guard digit tests with `isascii()`. Produce a `TokenizerError` with a span and exit 4. Do the numeric conversion in the
lexer, or catch `ValueError` in `create_literal_from_token` and raise a located error. Changes accepted programs: yes for
`1٣`, `1.５` and possibly `0x_1` (these stop compiling). No for the crashing forms.

### TOK-04 HIGH NEW (symptom recorded as B16 item 5 and at ledger-part1.md:145, undiagnosed there): operator and terminator columns are wrong

What is wrong: `_add_token` computes `column = self.column - len(value)`, which assumes the token text has already been
consumed. `_try_operator` and the newline branch call it before `advance()`. Every 1-character operator or punctuation token
(`( ) { } [ ] , . ; + - ...`) and every newline TERMINATOR is too small by 1. Every 2-character operator (`:: := == .. +=`)
is too small by 2, and `<<=`/`>>=` by 3. A 1-character token in column 1 gets column 0. A 2- or 3-character operator near
the start of a line gets a negative column: `<<= x` gives -2 and `:= x` gives -1 (`neg_col.out`). These columns reach
parse diagnostics and JSON spans.

Evidence:

- `a7/tokens.py:364-376` (`column = self.column - len(value)`), `:297-299` (newline: `_add_token` then `advance`),
  `:826-829`, `:842-844`, and every branch through `:955-956` (`_add_token` then `advance`).
- `probe_direct.out:1-35`:
  - `a + b\n` gives `PLUS C2` (actual 3) and `TERMINATOR C5` (actual 6).
  - `{\n}` gives `LEFT_BRACE C0` and `RIGHT_BRACE C0`.
  - `x <<= 1` gives `LEFT_SHIFT_ASSIGN C0` (actual 3).
  - `0..5` gives `DOT_DOT C0` (actual 2).
- `tokens_mode.out`: `uv run a7 probes/tok06b_close_brace_col.a7 --mode tokens --format json`, exit 0. It lists
  `DECLARE_VAR ':=' line 5 column 5` (actual 7), `LEFT_PAREN column 9` (actual 10), `RIGHT_BRACE line 6 column 0`.
- `run_probes.out:38`: `tok06b_close_brace_col` compile JSON, exit 5.
  `"tok06b_close_brace_col.a7:6:0: Unexpected token '}' after parsing complete program"`, span `start_column 0`.
- `pytest_diag.out`: `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[parse]` fails
  with `assert 9 == 10`. It is recorded as B16 item 5 in `docs/plan/audit/evidence/2026-09-16-ledger-part1.md:529-531`.
  The "col 0" diagnostics at `ledger-part1.md:145` have the same cause.
- Previously reported with the same root cause in `docs/audits/2026-09-14/pipeline-glm-review.md` H-4.

Fix direction: record `start_column`, and `start_line` for multi-line safety, before consuming, and pass it to
`_add_token` in `_try_operator` and the newline branch, as the number paths already do. Changes accepted programs: no. Only
diagnostic and `--mode tokens` columns change.

### TOK-05 HIGH KNOWN (F1; README "Compiler defects for track 1"): unclosed block comment is accepted

What is wrong: an unterminated `/*` consumes to EOF with no diagnostic, so any declarations after it disappear with exit 0.
Also, `TokenizerErrorType.NOT_CLOSED_COMMENT` and its message and advice exist (`a7/errors.py:42, 175, 191`) but are never
raised, and `/* a /* b */` (the inner comment closed, the outer not) is swallowed the same way.

Evidence:

- `a7/tokens.py:387-406` (the comment at `:388-390` calls EOF "an accepted comment terminator").
- `probe_direct.out:215-216`: `'/* a /* b */ x'` gives only `EOF`.
- `probes/tok19b_unclosed_nested.a7`: `foo :: fn() {}` after `/* outer /* inner */` is dropped; exit 0,
  `zig build-obj` exit 0.
- The tests `test/test_tokenizer.py:136-162` and `test/test_tokenizer_aggressive.py:298-303` enshrine the behavior (ledger
  part 2, C5).

Fix direction: as in packet P1. Raise `NOT_CLOSED_COMMENT` at the opening `/*`. Changes accepted programs: yes (known,
`examples/003_comments.a7`).

---

## MEDIUM

### TOK-06 MEDIUM NEW: Rich markup in token values crashes every inspection mode

What is wrong: `_display_tokens` passes `repr(token.value)` as a plain `str` cell to a Rich `Table`, which parses console
markup. A string literal containing `[/]` raises `MarkupError`, and the program exits 8. This happens in `--mode tokens`,
`ast`, `semantic`, `pipeline` and `compile -v`. In the `-v` case the `.zig` file has already been written. A literal like
`"[bold red]x"` is shown as `'"x"'`, so the token table misreports the value. Paths with markup are also rendered with the
markup stripped (`probes/[red]dir[/]/x.a7` is shown as `probes/dir/x.a7`).

Evidence:

- `a7/formatters/console_formatter.py:380-386` (`repr(token.value)` passed to `add_row`) and `:342, :362` (a `str` title
  passed to `Panel`). `a7/compile.py:550-553` prints a `Compiled {input_path}` f-string through the markup parser.
- `tokens_mode.out`: `uv run a7 probes/tok18a_markup_string.a7 --mode tokens` (source `io.println("[/]")`) prints
  `Unexpected error: closing tag '[/]' at position 2 has nothing to close`, exit 8.
- `markup_modes.out`: modes `ast`, `semantic` and `pipeline` all exit 8 the same way. `compile -v` exits 8 and
  `probes/out/tok18a_v.zig` exists (569 bytes). The markdown report (`--doc-out`) is correct: `'"[/]"'`.
- `tok18b_markup_style` in `--mode tokens` shows `STRING_LITERAL '"x"' 13`, although the value is `"[bold red]x"`.

Fix direction: wrap cell values in `rich.text.Text(...)`, or call `rich.markup.escape`, for token values, titles and paths.
Changes accepted programs: no.

### TOK-07 MEDIUM NEW (extends KNOWN F6b/F6c): control bytes and non-ASCII code points in literals reach Zig unvalidated

What is wrong: the tokenizer accepts any single code point, including raw control bytes, between `'…'`, and any `\xHH` in a
char literal. The char emitter escapes only 6 characters and writes everything else raw. Zig rejects the result:
`'\x01'`, `'\x7f'`, a raw 0x01 byte, `'\x85'`, `'€'` and `'😀'` all compile with exit 0 but fail `zig build-obj`. Strings
containing U+0085 or U+2028 are also emitted raw and Zig rejects them. Known F6c covers only `'é'`, which Zig accepts.

Evidence:

- `a7/tokens.py:737-750` (single character: any code point), `:705-723` (`\x` with no range check).
- `a7/backends/zig.py:1491-1496`: `char_escapes` covers only `\n \t \r \\ ' \0`.
- `run_probes.out:64-89`:
  - `tok11a_char_ctrl` (`'\x01'`): Zig `character literal contains invalid byte: '\x01'`.
  - `tok11b_char_del` (`'\x7f'`): `invalid byte: '\x7f'`.
  - `tok11g_char_raw_ctrl` (raw 0x01): same as `tok11a`.
  - `tok11i_char_hex_80` (`'\x85'`): `character literal contains invalid byte`.
  - `tok11c_char_euro`: `type 'u8' cannot represent integer value '8364'`.
  - `tok11d_char_emoji`: `cannot represent integer value '128512'`.

  Each A7 compile exits 0, and each `zig build-obj` exits 1.
- `run_probes.out:174-176`: `tok25_c1_in_string` (U+0085 and U+2028 in a string) compiles with exit 0. Zig reports
  `string literal contains invalid byte`, exit 1.
- `tok11e_char_raw_newline` (a raw newline between quotes) compiles to `'\n'`, Zig exit 0. It is accepted although no SPEC
  text allows it.

Fix direction: validate char literals in the tokenizer (one ASCII byte or a valid escape with value 0-127, as SPEC Appendix
D says), and make both emitters hex-escape every byte outside printable ASCII. Changes accepted programs: yes, for the
ASCII rule (G6). The emitter half alone would change no program that Zig builds today.

### TOK-08 MEDIUM NEW: float literal overflow becomes `inf.0`

What is wrong: `float("1e999")` is `inf`. `_emit_literal` appends `.0` because the text has no `.` or `e`, so Zig
receives `inf.0` and rejects it. The lexer and type checker accept the literal. `1e-999` silently becomes `0.0`.

Evidence:

- `a7/ast_nodes.py:590`, `a7/backends/zig.py:1479-1483`.
- `run_probes.out:90-92`: `tok12_float_inf` (`x: f64 = 1e999`) compiles with exit 0. Zig reports
  `expected pointer dereference, optional unwrap, or field access, found 'a number literal'` for `const x: f64 = inf.0;`,
  exit 1. `tok12f_float_inf_untyped` behaves the same way.
- `tok12b_float_underflow` emits `const x: f64 = 0.0;`.

Fix direction: reject non-finite float literals, and possibly literals that underflow to zero, with a located diagnostic.
This fits the G1 float gate. Changes accepted programs: no for `inf` (Zig rejects today). Yes if underflow is also rejected.

### TOK-09 MEDIUM NEW: `@name` and `$T` scanners accept Unicode letters and empty names

What is wrong: `_tokenize_builtin` and `_try_generic_type` use unguarded `isalnum()`/`isalpha()`, unlike identifiers.
`@café` is a valid BUILTIN_ID. As a loop label it is emitted as the Zig label `a7_loop_café`, which Zig rejects. `$Té`
becomes a GENERIC_TYPE. `@` alone and `@1` are BUILTIN_ID tokens with no error from the lexer.

Evidence:

- `a7/tokens.py:811-813` `while self.current_char() and (self.current_char().isalnum() or self.current_char() == "_"):`
  (no `isascii()`, and zero iterations still yield a token at `:817`). `:974`
  `if not (self.current_char() and self.current_char().isalpha()):`, and `:1003-1005` (`isalnum()`).
- `a7/backends/zig.py:2310` `safe = label.replace("$", "_").replace(".", "_").replace("-", "_")` passes other characters
  through.
- `probe_direct.out:128-146`: `$Té` gives `GENERIC_TYPE '$Té'`; `$é` gives `GENERIC_TYPE '$é'`; `@ for` gives
  `BUILTIN_ID '@'`; `@1` gives `BUILTIN_ID '@1'`; `@café` gives `BUILTIN_ID '@café'`.
- `run_probes.out:55-57`: `tok10a_unicode_label` compiles with exit 0 and emits `a7_loop_café: while ...`. Zig reports
  `expected ';' after statement`, exit 1.
- SPEC `docs/SPEC.md:2046`: `loop_label = "@" identifier`. The identifier rules at `:88-90` require ASCII.

Fix direction: apply the identifier character class (ASCII letter or `_` first, then ASCII alphanumerics or `_`) after `@`
and `$`, and reject an empty name in the lexer. Changes accepted programs: no for labels (Zig rejects them). Unknown for
Unicode generic names, because generic codegen failed first in `tok10b_unicode_generic`, exit 7.

### TOK-10 MEDIUM NEW: line-separator characters inside comments or strings make diagnostics show the wrong line

What is wrong: the tokenizer counts only `\n`. `source_lines` comes from `str.splitlines()`, which also splits on `\x0b`,
`\x0c`, `\x1c`-`\x1e`, U+0085, U+2028 and U+2029. These characters are legal inside comments and strings. After one of
them, every later diagnostic has the right line number and column but renders the wrong source text and places the caret
under an unrelated line.

Evidence:

- `a7/tokens.py:237` (`self.source_lines = source_code.splitlines()`), `:264-266` (only `"\n"` increments the line).
  `a7/compile.py:192, 232` build the same `splitlines()` list for later stages.
- `probe_direct.out:298`: `Tokenizer("\n//a b\nx\n").source_lines` is `['', '//a', 'b', 'x']`, while the token `x` is
  on line 3.
- `human_dump.out:24-35`: `probes/tok08_u2028_context.a7` (U+2028 in the line-2 comment, backtick on line 7) prints
  `error: Unexpected character: '`' [line 7: col 10]`. The context shows row `7 ┃     x := 1` with the caret, and the
  backtick line shown as row 8.
- `human_dump.out:37-48`: `tok08b_formfeed_string_context` (form feed inside a string) has the same one-line shift.

Fix direction: split lines on `\n` only (`source.split("\n")`, stripping a trailing `\r`), computed once and shared by all
stages. Changes accepted programs: no.

### TOK-11 MEDIUM NEW: a missing closing quote is reported on a later line, or the program compiles

What is wrong: `_tokenize_string` lets strings contain raw newlines. A missing `"` therefore pairs with the next quote in
the file. The error lands on whichever later quote ends up unpaired, or, if the quotes pair up evenly, the program compiles
with code inside a string. The SPEC gives only single-line examples (`docs/SPEC.md:168`, `"Hello, World!" // single line
string`) and does not define multi-line strings.

Evidence:

- `a7/tokens.py:590` `while self.current_char() and self.current_char() != '"':` (no newline check; `:594`
  `self.advance()` consumes `\n`), then `:596-606` report `start_line, start_column` of whichever quote is still open at
  EOF.
- `probe_direct.out:183`: `'a := "oops\nb := "fine"\n'` gives `NOT_CLOSED_STRING span=(2,11)`. The missing quote is on
  line 1, column 6.
- `human_dump.out:92-102`: `tok07_unterminated_newline` reports `[line 6: col 21]` with the underline under `")` on the
  `io.println("fine")` line. The quote is missing on line 5.
- `run_probes.out:45-47`: `tok07b_unterminated_compiles` compiles with exit 0. It emits
  `__a7_stdout_print("line one\n    still in string\n", .{});`, and Zig exits 0.

Fix direction: decide in the SPEC whether raw newlines are allowed in string literals. If not, stop at `\n` and report the
opening quote. Changes accepted programs: yes, if multi-line strings become illegal.

### TOK-12 MEDIUM NEW: a newline inside a block comment is not a statement terminator

What is wrong: `_try_comment` discards the whole `/* ... */`, including any `\n`, so no TERMINATOR is emitted. The SPEC
says "Newlines (U+000A) serve as statement terminators" (`docs/SPEC.md:65`). Moving a line break into a comment changes how
the code parses and what it computes.

Evidence:

- `a7/tokens.py:404-406` `else: self.advance()` inside the depth loop, then `return True`. No TERMINATOR is added for the
  newlines consumed. Compare `//` comments at `:382-384`, which stop before `\n` ("Leave newline for main tokenizer to
  handle as TERMINATOR").
- `probes/tok36_comment_newline.a7` (run-allowed): `x := a /* note\n    */ -b` with `a := 5`, `b := 3`. It emits
  `const x = (a - b);` and prints `2` in Debug and ReleaseFast.
- `probes/tok36b_plain_newline.a7`: `x := a\n    -b` emits `const x = a; _ = (-b);` and prints `5`
  (`run_probes5.out`).

Fix direction: emit one TERMINATOR when a block comment spans one or more newlines, as Go does. Changes accepted programs:
yes (the parse of such programs changes). Needs approval.

### TOK-13 MEDIUM NEW: escape sequences do not match SPEC Appendix D

What is wrong:

- SPEC D.1 lists `\b`, `\f`, `\v` and `\a`, but the tokenizer rejects all four in strings and chars.
- SPEC D.1 and 2.6 say `\xHH` is "0-127", "ASCII only", but 0x80-0xFF is accepted (see TOK-01).
- `\r`, `\0` and `\"` in chars are accepted but not listed in 2.6, only in Appendix D.

Evidence:

- `a7/tokens.py:650` and `:724` accept `"ntr\\'\"0"`.
- `docs/SPEC.md:2159-2171`.
- `spec_escapes.out`: `"\b"` gives `1:2: Invalid string escape sequence`; `'\b'` gives `1:3: The char is not closed`; the
  same holds for `f`, `v` and `a`.
- `probe_direct.out:191-193`: `'\xff'` gives `CHAR_LITERAL`. `tok11f_char_hex_ff` compiles to `'ÿ'`, and Zig exits 0.

Fix direction: align the SPEC and the lexer (owner decision). Changes accepted programs: yes if `\x80+` is rejected; no if
only the four missing escapes are added.

### TOK-14 MEDIUM NEW: names reserved by SPEC 2.3 are accepted and can clash with emitted runtime names

What is wrong: SPEC 2.3 says "Leading underscores are reserved for compiler-generated names" (`docs/SPEC.md:91`). Neither
the lexer nor any later pass enforces it. A user function named `__a7_stdout_print` compiles, and Zig rejects the
duplicate. `_x` compiles.

Evidence:

- `a7/tokens.py:327-333`.
- `run_probes.out:118-123`: `tok14a_leading_underscore` compiles with exit 0.
- `run_probes3.out`: `tok34_reserved_clash_io` compiles with exit 0; Zig reports `duplicate struct member name
  '__a7_stdout_print'`, exit 1.
- `tok14b_reserved_clash` (a user `__a7_user_main` with no io) builds only because the prelude is omitted.

Fix direction: reject identifiers starting with `_` (or at least `__a7`) in the lexer or name resolution, or document the
exact reserved prefix. Changes accepted programs: yes for plain `_x` (needs approval). No for `__a7_*` names that Zig
already rejects.

### TOK-15 MEDIUM NEW: char-literal diagnostics all say "The char is not closed"

What is wrong: every char-literal failure raises `NOT_CLOSED_CHAR`. This includes an invalid escape (`'\q'`, `'\b'`), a
bad hex escape (`'\xZZ'`), an empty literal (`''`) and several characters (`'ab'`). The column is the offending character,
not the opening quote, and the hint is "Close the char with a quote". Strings report `INVALID_ESCAPE_CHAR` for the same
mistakes. The SPEC B.2 message list has only "The char is not closed".

Evidence:

- `a7/tokens.py:672-680, 716-723, 729-736, 743-750`.
- `probe_direct.out:189-195`: `'\q'` gives `NOT_CLOSED_CHAR` at `(1,3)`; `'\xZZ'` at `(1,4)`; `'ab'` at `(1,3)`; `''`
  at `(1,2)`.
- `run_probes.out:85-86`: `tok11h_char_bad_escape` gives `5:17: The char is not closed`, exit 4.
- `test/test_tokenizer_errors.py:104-121` asserts this text for `''` and `'ab'`.

Fix direction: use `INVALID_ESCAPE_CHAR`, plus new "empty char literal" and "char literal has more than one character"
messages, located at the opening quote with a length covering the literal. Changes accepted programs: no.

---

## LOW

### TOK-16 LOW KNOWN (D5, D8, D9; B12 for emission): keyword and punctuation set drift, with new details

The known part: `int`, `uint` and `float` are keyword tokens the parser rejects (D5). `#` is a line comment (D8). `?` is not
a token, and `...` lexes as `..` then `.` (D9). SPEC keywords `cast`, `const`, `self`, `size_of`, `type`, `using` and `var`
lex as identifiers (as stated in the audit brief). Additional detail observed:

- `...` followed by a digit lexes as `..` then a float: `0...5` gives `INTEGER 0`, `DOT_DOT`, `FLOAT_LITERAL '.5'`
  (`probe_direct.out:27-31`).
- `let`, `as` and `where` are keyword tokens that the parser never consumes. A grep for `TokenType.LET`, `.AS` and `.WHERE`
  outside `tokens.py` returns 0 hits. `let := 1` fails at the wrong place: `tok13d_let_ident` reports
  `6:0: Unexpected token '}' after parsing complete program`, exit 5 (combined with TOK-04's column 0).
- `type := 1` compiles with exit 0 and emits `const type = 1;`. Zig reports `name shadows primitive 'type'`
  (`run_probes.out:110-112`), the same class as B12. `cast := 1` and `using`/`self`/`size_of` locals compile, and Zig builds
  them (`tok13a`, `tok13c`).
- SPEC's token table (`docs/SPEC.md:1763-1774`) lists `TOKEN_DOT_DOT_DOT`, `TOKEN_DOLLAR`, `TOKEN_QUESTION`,
  `TOKEN_NEWLINE`, `TOKEN_COMMENT` and `TOKEN_ERROR`. None exists in that form.

Fix direction: packet P1. Changes accepted programs: yes (known).

### TOK-17 LOW KNOWN (F6b, F6c; gate G6): non-ASCII accepted outside identifiers

Strings (`tok03_nonascii_string`: `"café € 😀"` is emitted raw, prints UTF-8 bytes, runs), chars (`'é'`, `'ÿ'`) and
comments accept non-ASCII, against `docs/SPEC.md:60` ("must be ASCII encoded") and Appendix D. The test
`test/test_tokenizer_aggressive.py:557-576` treats non-ASCII comments as intended. TOK-07 and TOK-01 are the cases where
this goes wrong in Zig or at run time. Changes accepted programs: yes (known).

### TOK-18 LOW NEW: tab characters are accepted inside literals and comments

SPEC `docs/SPEC.md:64`: "Tab characters (U+0009) are **not supported** and will cause a compilation error." Only
`skip_whitespace` checks for tabs (`a7/tokens.py:272-286`), so a tab inside `// ...`, `/* ... */`, `"..."` or `'...'` is
accepted. `probe_direct.out:173-182, 199-201`. `tok09_tab_in_string_comment` compiles with exit 0 and emits
`"a\tb\n"`; Zig exits 0. Fix: either reword the SPEC ("outside literals and comments") or reject tabs everywhere. Changes
accepted programs: yes if tabs are rejected everywhere.

### TOK-19 LOW NEW: the source is read with universal newlines

`a7/compile.py:154` opens the file with `open(input_path, "r", encoding="utf-8")`, which has no `newline=""`. Python turns
CRLF and lone CR into LF before the tokenizer runs. As a result:

- A raw CR inside a string literal becomes LF. `tok16d_lone_cr_in_string` emits `"a\nb\n"` (`zig_dump.out:139-154`).
- Classic-Mac CR-only files get statement terminators (`tok16e_lone_cr_lines` reports line 5, correct), although SPEC
  `:63-65` says CR is plain whitespace and only LF terminates.
- The `Tokenizer` API behaves differently from the CLI. Direct `Tokenizer("a\rb")` gives no TERMINATOR
  (`probe_direct.out:232-235`), and the comment at `a7/tokens.py:231-232` describes the CR behavior as legacy.

CRLF columns are correct through the CLI (`tok16b_crlf` reports `5:12`, the same as the LF version). Changes accepted
programs: yes (string bytes) if fixed.

### TOK-20 LOW NEW: uppercase radix prefixes split silently

`0X2A`, `0B1` and `0O7` lex as `INTEGER 0` followed by an identifier (`probe_direct.out:77-84`). `tok15b_upper_hex` fails
with exit 6, `Undefined type (Identifier 'X2A') [line 5: col 11]`, not with a lexical "uppercase prefix" error. The SPEC names only lowercase prefixes (`:146`). Fix: fold into the TOK-02 boundary check. Changes accepted
programs: no.

### TOK-21 LOW NEW: length limits are inconsistent

- `MAX_STRING_LENGTH = 2**15 - 1` (`a7/tokens.py:16`) is never referenced. `tok27_long_string` (40,000 characters)
  compiles, and Zig exits 0.
- SPEC Appendix C (`docs/SPEC.md:2135`) gives 65,535 bytes as the minimum string limit, which conflicts with the constant.
- `TOO_LONG_STRING` is never raised.
- `$…` and `@…` names have no length cap. A 500-character name is accepted (`probe_direct.out:147-152`), while identifiers
  are capped at 100 (`:153-156`).

Previously noted in `docs/audits/2026-09-14/pipeline-glm-review.md` M-3 and in `security-glm-review.md` SEC-10. Changes
accepted programs: yes if new caps are added.

### TOK-22 LOW NEW: dead code and stale text

- `a7/tokens.py:7-9`: `Union`, `re` and `string` are imported and unused.
- Token types never produced: `TRUE`, `FALSE` and `NIL` (the entries at `:209, :217, :193` are overridden at `:797-802`),
  `COMMENT`, `ADDRESS_OF` and `DEREFERENCE` (`:145-148`). Token types produced but never consumed by the parser: `LET`,
  `INT`, `UINT`, `FLOAT`, `AS` and `WHERE` (0 grep hits outside `tokens.py`).
- `TokenizerErrorType` members never raised: `OUT_OF_MEMORY`, `TOO_LONG_STRING`, `END_OF_FILE`, `FILE_EMPTY`,
  `BAD_TOKEN_AT_GLOBAL`, `NOT_CLOSED_COMMENT`, `UNSUPPORTED` and `UNKNOWN` (`a7/errors.py:29-49`).
- `create_error_handler().tokenizer_error` (`a7/errors.py:862-868`) is unused.
- `a7/tokens.py:996` (`return True` after both branches raise) and `:1014-1018` (the fallback) are unreachable.
- In `:433, :470, :505`, `self.position == digit_start` is subsumed by the `replace(...) == ""` test.
- The `INVALID_GENERIC_SYNTAX` advice "letters and underscores only" (`a7/errors.py:207`) contradicts the lexer, which
  accepts digits (`$T1`).
- The comment "Logical operators (handled as keywords)" above `LOGICAL_NOT` (`a7/tokens.py:121`) is stale.

Changes accepted programs: no.

### TOK-23 LOW NEW: spans of multi-line tokens are wrong

- `TokenizerError.from_type_and_location` and `CompilerError.from_token` always set `end_line = line` and
  `end_column = column + length` (`a7/errors.py:674-680, 743-749`).
- For an unterminated string spanning lines, the error length counts newlines: `tok07` gives span
  `start (6,21) end (6,26)` on a 22-character line.
- A multi-line STRING_LITERAL token's span also ends on its first line.
- `SourceSpan.__post_init__` sets `length = 1` for multi-line spans (`:449-452`), but nothing constructs one here.

Changes accepted programs: no.

### TOK-24 LOW NEW: raw control bytes in diagnostics; invalid UTF-8 has no location

- `Unexpected character: '{self.current_char()}'` (`a7/tokens.py:357`) prints NUL, form feed and similar characters raw.
  `human_dump.out:104-110`: `tok17b_nul` renders `'^@'`, and the JSON escapes it as ` `.
- A non-UTF-8 file fails in `open(...).read()` and is reported as IO, exit 3, with
  `'utf-8' codec can't decode byte 0xff in position 47` (a character offset, no line or column, `span=None`;
  `run_probes.out:143-144`).
- A BOM in the middle of a file is rendered as an invisible `'﻿'` (`probe_direct.out:241`).

Fix direction: print `repr()`/`U+XXXX` for non-printable characters. Decode as bytes and report the line and column of
the first invalid sequence as a tokenize error, exit 4. Changes accepted programs: no.

### TOK-25 LOW NEW: caret alignment uses code points, not display cells

- `_build_source_context` pads with `start_column - 1` spaces (`a7/errors.py:602`). With CJK text before the error
  (`tok21_wide_chars_caret`, `"中文"`) the caret lands 2 cells left of the backtick.
- The tokenizer strips a leading BOM, but `compile.py:192, 232` build `source_lines` from the unstripped text. For a
  semantic error on line 1 (`tok33_bom_semantic_line1`), the rendered line includes U+FEFF, so the highlight is shifted by
  one character.

Changes accepted programs: no.

### TOK-26 LOW NEW: JSON failure payloads always include every token, the source and the AST

`_to_json_payload` includes `formatted["tokens"]` and `source_code` for every mode and result (`a7/compile.py:731-754`,
`json_formatter.py:39-66`). `big_json.out`: a 457,844-byte source with one undefined name exits 6 and prints a 64,467,028-byte
JSON document (120,015 tokens), about 140 times the source size. The token array and its count also disagree:
`stages.tokenize.token_count` excludes EOF (`compile.py:174`), but the array includes it (`json_formatter.py:40`).
`tokens_mode.out` lists 21 entries against `token_count` 20. Changes accepted programs: no.

### TOK-27 LOW NEW: throughput

`perf.out`:

- 80,000 generated lines (3.35 MB, 640k tokens) tokenize in 1.77 s, and runtime scales linearly from 10k lines.
- 2,000,000 `;` take 3.96 s against 0.71 s for 2,000,000 newlines, because `_try_operator` rebuilds a 23-entry dict on every
  call (`a7/tokens.py:928-952`) after a 17-way `elif` chain.
- Block-comment nesting depth is a counter: depth 1,000,000 takes 0.72 s, with no recursion.

No quadratic behavior was found. Changes accepted programs: no.

### TOK-28 LOW NEW: SPEC lexical text drift

- SPEC B.2 (`docs/SPEC.md:2113-2119`) documents `error: <message>, line: <line>, col: <column>` and `help:`. The actual
  output is `error: <message> [line N: col M]` and `hint:` (`a7/errors.py:474-486, 516`). The docstring of
  `test/test_tokenizer_errors.py:143` repeats the SPEC form while asserting another.
- SPEC 2.3's EBNF (`:81-82`) makes `letter` ASCII letters only, so `_x` is not an identifier, while the prose (`:88, :91`)
  allows a leading underscore.
- SPEC 2.2 does not say whether an unterminated `/*` or `*/` without an opener is an error. The lexer turns `*/` into
  `MULTIPLY DIVIDE` (`probe_direct.out:217-221`).

Changes accepted programs: no (documentation).

### TOK-29 LOW NEW: structure limits the planned typed IR and analysis layers

- `Token` holds `type`, raw `value`, `line`, `column` and `length` (`a7/tokens.py:159-171`). It has no byte or character
  offset, no end line or column, and no decoded value.
- Numeric and escape decoding happens later in `ast_nodes.create_literal_from_token` (`a7/ast_nodes.py:536-598`), so the
  lexer cannot reject values it cannot represent (TOK-01, TOK-03, TOK-08).
- `source_lines` is computed separately in `Tokenizer.__init__`, `compile.py:192` and `compile.py:232`, with `splitlines()`
  semantics that disagree with the lexer's line counting (TOK-10, TOK-25).
- The lexer aborts on the first error with no recovery or error token.

INFERENCE: a Wave 3 IR that needs stable source mapping for diagnostics and imported modules would benefit from one shared
source map (file id, offsets, line table) and literal values decoded once in the lexer. Changes accepted programs: no.

---

## Checked and correct

1. Standard string escapes decode and emit correctly end to end. `tok02_escape_heavy` (`\" \\ \t \0 \x41 \x01 \x7f \r`)
   emits `"q\" b\\ t\t z\x00 hA c\x01 d\x7f r\rend\n"` and prints bytes
   `71 22 20 62 5c 20 74 09 20 7a 00 20 68 41 20 63 01 20 64 7f 20 72 0d 65 6e 64 0a` in Debug and ReleaseFast
   (`run_exec.out:14-31`).
2. Char `'\0'` emits `'\x00'` and prints a NUL byte (`tok24_char_zero`, both modes). Char `'\xff'` emits `'ÿ'`, and Zig
   accepts it as `u8` 255 (build-obj only).
3. A NUL byte inside a string literal is emitted as `\x00` and builds (`tok17c_nul_in_string`).
4. Nested block comments are counted correctly (`/* a /* b */ c */ x` gives `x`). The implementation is an iterative
   counter and stays linear at depth 1,000,000. Comment markers inside strings are not comments
   (`"// not /* comment" x`), and `//` inside a block comment does not hide `*/`.
5. Line and column tracking after multi-line strings and block comments is correct (`"a\nbc" d` gives `d` at L2 C5), for
   identifier, literal and keyword tokens.
6. The tokenizer contains no recursion. The iterative-traversal invariant is not at risk in `tokens.py`.
7. Tabs outside literals are rejected with the correct column and `TABS_UNSUPPORTED` (the tests in
   `test_tokenizer_errors.py:325-345` agree).
8. Identifier length: 100 accepted, 101 rejected (`TOO_LONG_IDENTIFIER`, span length 101). Numeric literal length: 101
   rejected (`TOO_LONG_NUMBER`).
9. Non-ASCII identifiers are rejected at the right column (`café` gives `Unexpected character: 'é'` at `(1,4)`).
10. `0..5`, `1.0..2.0` and `a..b` lex as ranges. `5.`, `.5` and `1.e5` lex as floats. `1e`, `1e+` and `1e-` are
    rejected. `0b`, `0x` and `0o` without digits are rejected.
11. Valid literal forms emit and run correctly: `1e-5` gives `1e-05`, `1e16` gives `1e+16`, a 18-digit float gives
    `1.2345678901234568e+17`, `5.` gives `5.0`, `.5` gives `0.5`, `1_000.25`, `0x_FF` gives 255, `0b1010_1010` gives 170,
    and `0o7_7` gives 63. Debug and ReleaseFast both print `0.00001 10000000000000000 123456789012345680 5 0.5 1000.25
    255 170 63` (`run_probes4.out`).
12. `x: u64 = 18446744073709551616` is rejected, exit 6. The message is misleading; see "Not verified".
13. A leading UTF-8 BOM is stripped, and tokenizer columns on line 1 are correct (`tok16c` gives `1:6`).
14. CRLF files through the CLI give the same line and column as LF files (`tok16b_crlf` gives `5:12`).
15. A non-UTF-8 file fails cleanly with exit 3 in both human and JSON formats. The JSON is valid and has no traceback.
16. The tokenize-stage JSON error has `category tokenize`, exit 4, 1-based `start_column`, and exclusive
    `end_column = start + length`, consistent with other stages.
17. TERMINATOR deduplication merges `;`, newlines and comment-only lines as documented (`a;\n;b` gives one TERMINATOR).
18. `--mode tokens` does not parse (`compile.py:189`). With `--format json` it prints valid JSON with all tokens.
19. The `--doc-out` markdown token table escapes `|` and shows `[/]` correctly.
20. All 56 tests in the three tokenizer test files pass (`pytest_tokenizer.out`).

## Test gaps

Behaviors with no test:

- Token columns of operators, punctuation and TERMINATOR (TOK-04). The only column tests use identifiers and invalid
  characters.
- Underscore placement in numbers, non-ASCII digits and literal-to-value conversion errors (TOK-03).
- Literal boundary errors (`0b12`, `1.5.25`, `0X2A`) (TOK-02, TOK-20).
- `\xHH` above 0x7F in strings and chars, and the bytes that reach Zig (TOK-01, TOK-13).
- Char literals with control or non-BMP code points (TOK-07). Float overflow to `inf` (TOK-08).
- Unicode or empty `@` and `$` names (TOK-09). Loop labels have no lexer-level test.
- Line separators and form feeds inside comments or strings versus rendered context (TOK-10).
- A missing closing quote across lines, and multi-line string acceptance (TOK-11).
- A block comment containing a newline between two statements (TOK-12).
- CRLF, lone CR and BOM through the CLI, including columns and string contents (TOK-19, TOK-25).
- Tabs inside strings and comments (TOK-18).
- `--mode tokens` through the CLI in human format with bracketed strings (TOK-06). No test runs `--mode tokens` on a
  string containing `[`.
- The JSON token array schema (`type`, `value`, `line`, `column`, `length`) for `--mode tokens`.

Existing tests that assert nothing meaningful or enshrine defects:

- `test_tokenizer_aggressive.py:275-310` (`test_comment_edge_cases`) and `:557-576`
  (`test_unicode_and_special_characters`) assert that there are zero `TokenType.COMMENT` tokens, a type that is never
  produced (TOK-22). The assertions are vacuous. `:298-303` also enshrines the unclosed-comment defect (KNOWN F1).
- `test_tokenizer_aggressive.py:180-196` (`test_numeric_literals_malformed` edge cases), `:230-240`,
  `:351-373` (`test_builtin_function_edge_cases` invalid cases), `:594-614` (`test_malformed_input_recovery`) and
  `:616-633` (`test_edge_case_operator_sequences`) accept either success or `TokenizerError`, or even `TypeError`, and
  check only that EOF exists. `0b123` and `0xGHI` (TOK-02) pass through them.
- `test_tokenizer_errors.py:68-85` and `:104-121` define `expected_line` and `expected_col` but never assert them. The
  unterminated-string test would pass with the wrong-line location from TOK-11.
- `test_tokenizer_errors.py:156-176, 178-194, 196-214, 216-245, 273-310, 366-383, 385-411` use `try: tokenize() except
  TokenizerError:` with no `else: fail`. If the error stopped being raised, each test would pass without running a single
  assertion.
- `test_tokenizer_errors.py:104-121` asserts "The char is not closed" for `''` and `'ab'`, which enshrines TOK-15.
- `test_tokenizer.py:136-162` (`test_003_comments`) enshrines the unclosed comment (KNOWN F1).
- `test_tokenizer_aggressive.py:542-555` (`test_performance_large_input`) asserts only that there are more than 5000
  tokens, with no time bound, so it is not a performance test.
- `test_tokenizer_aggressive.py:578-592` asserts internal fields (`position`, `line`, `column`) instead of observable
  token output. This mirrors the implementation.

## Not verified

- Parse-error human output in `tok06_op_column` and `tok16a_bom_parse_error` shows only the message line with no source
  context, while tokenizer and semantic errors show context. I did not trace why; it belongs to the parser and compile
  scope.
- `x := 999999999999999999999999999999` (untyped) compiles with exit 0, emits `const x = 9999...;`, and Zig builds it
  (`tok12d`). `x: u64 = 18446744073709551616` is rejected as "expected 'u64', got 'i32'", which misdescribes a 65-bit
  literal. The literal typing rules belong to the type checker (gate G3). I did not confirm what A7 intends.
- `main2 := := 1` after `main` (`tok06c`) and a stray `*/` after the last declaration (`tok19a`) both compile with exit 0.
  This is attributed to KNOWN F2 (parse errors after the first declaration are dropped) and was not re-traced here.
- The Windows console and legacy terminal rendering of `┃`, `▲` and wide characters were not tested.
- Generic names with Unicode letters (`$Té`) could not be followed to Zig, because generic codegen fails first
  (`tok10b`, exit 7, `generic type requires an explicit generic environment`, span `None`).
- Whether Zig 0.16.0 accepts every code point that `_quote_zig_string` writes raw was checked only for U+00E9, U+00FF,
  U+0080, U+20AC, U+1F600 (accepted in strings), and U+0085 and U+2028 (rejected).

claims checked: 77
