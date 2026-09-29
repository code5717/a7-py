<task id="ses_f44deb411ffegwhmBrGyG20r5r" state="completed">
<task_result>
# A7 Frontend Review — tokens.py, parser.py, errors.py (read-only)

Identity: GLM-5.3 / Z.AI Coding Plan, 2026-09-19. All findings are static (no compiler runs, per mandate). "KNOWN" = already tracked in `docs/plan/audit/open-items.md` or `docs/plan/execution.md`.

## Confirmed code-level defects

### CRITICAL

**C1. Error recovery silently drops declarations and promotes locals to globals (KNOWN: PRD-33 family).**
`a7/parser.py:189-221` (`parse()` recovery), `a7/parser.py:257-290` (`synchronize()`), `a7/parser.py:317-322` (top-level `name := value` accepted).
Any non-fatal `ParseError` after ≥1 parsed declaration is swallowed unless the message matches two narrow patterns (exactly-one-decl + "Expected declaration", or "Expected expression after" — note `parser.py:211` tests for `"Expected expression after"`, but `parse_primary_expression` at `parser.py:1749` raises `"Expected expression"`, which does **not** match). `synchronize()` restarts at the next `IDENTIFIER :=`, so body statements are re-parsed as top-level declarations.
Snippet:
```a7
helper :: fn() { ret 1 }
main :: fn() {
    x, y := 10, 20
}
```
Expected: `ParseError` at `,`. Actual (traced): declarations become `[helper, y := 10 (top-level)]`; `main` vanishes; compile succeeds — exactly PRD-33's emitted `var y = 10;`. Also the asymmetry at `parser.py:203-208`: the same trailing garbage hard-errors with 1 declaration, silently recovers with ≥2. `parser.py:289-290` (jump to EOF after 100 skipped tokens) silently accepts whatever was parsed before.

### HIGH

**H1. `for x in a..b` range iterables cannot parse (partially KNOWN: audit-3 p02/p06 "range loop failed to parse").**
`parser.py:1403-1422` — the binary-operator match set excludes `DOT_DOT`; the for-in iterable is parsed with `parse_expression()` (`parser.py:1217, 1232`), which stops before `..`.
```a7
main :: fn() {
    for i in 0..10 { ret 0 }
}
```
Expected: range iteration (15+ docs under `docs/lang-safety/` use `for i in 0..n` as canonical A7, e.g. `docs/lang-safety/07-language-review.md:255`). Actual: `ParseError: Expected LEFT_BRACE, got DOT_DOT` — and via C1, in any file with a preceding declaration the whole function silently disappears. No `.a7` example uses the form (grep confirmed), but the docs/implementations disagree.

**H2. String literal length limit unenforced; constant contradicts SPEC (KNOWN in part: TOK-21).**
`a7/tokens.py:16` — `MAX_STRING_LENGTH = 2**15 - 1` (32767) vs SPEC Appendix C `docs/SPEC.md:2142` "65,535 bytes". `_tokenize_string` (`a7/tokens.py:583-612`) never checks any length; `TOO_LONG_STRING` (`a7/errors.py:33`) is raised nowhere (grep confirmed). `x := "<70000 chars>"` is accepted silently.

### MEDIUM

**M1. Underscore misplacement in numeric literals becomes an "internal error".**
Tokenizer consumes `_` anywhere in numbers (`a7/tokens.py:532, 540, 564` and the base-prefix loops), but `create_literal_from_token` (`a7/ast_nodes.py:577-590`) calls bare `int()`/`float()`, which reject trailing/doubled underscores.
```a7
x := 1_
```
`int("1_")` raises `ValueError` → caught only by the pipeline catch-all `a7/compile.py:514-527` → category `internal`, exit INTERNAL, no line/column. Same for `0x1__0`, `1e5_`, `1_.5`. Expected: a tokenizer diagnostic.

**M2. Escapes `\b \f \v \a` rejected though SPEC documents them.**
SPEC D.1 `docs/SPEC.md:2167-2170`; accepted set is only `n t r \ ' " 0` + `\x` in `a7/tokens.py:650` (strings) and `a7/tokens.py:724` (chars); `a7/ast_nodes.py:536-570` (`_unescape_literal_content`) likewise. `x := "\a"` → "Invalid string escape sequence". Also `\xHH` accepts values >0x7F (`\xFF` passes `a7/tokens.py:635`) against SPEC's "ASCII only".

**M3. `fn` type with omitted return type fails before `}`/`{`/EOF.**
`parser.py:839-845` — return-type stop set is `{TERMINATOR, ASSIGN, RIGHT_PAREN, RIGHT_BRACKET, COMMA}`; missing `RIGHT_BRACE`, `LEFT_BRACE`, `EOF`, `COLON`.
```a7
S :: struct { cb: fn() }
```
→ `ParseError: Expected type` at `}` (SPEC 13.2 `docs/SPEC.md:1978` makes the return type optional). `examples/027_callbacks.a7:5` (`Handler :: fn()`) survives only because a newline TERMINATOR follows; `Handler :: fn()` as the last line without a trailing newline, or with the body brace on the next line (`main :: fn() i32\n{`, misdetected as a type alias by `parser.py:524-535` then dropped via C1), fails.

**M4. Multi-line array literals and positional struct literals rejected (inconsistent with calls/named literals).**
`parse_array_literal` `parser.py:1938-1942` and the positional branch of `parse_struct_literal` `parser.py:2006-2017` do not `skip_terminators()` after commas; `parse_call_expression` does (`parser.py:1561`) and the named struct branch does (`parser.py:1981`).
```a7
main :: fn() {
    nums := [1,
             2,
             3]
}
```
→ `ParseError: Expected expression` at the newline token. Expected: parses, matching multi-line call style. `P{1,\n2}` fails the same way.

**M5. Struct-literal heuristic misfires when a condition exceeds 10 tokens.**
`_should_parse_struct_literal` `parser.py:126-162`: lookback capped at `min(10, position)` (`parser.py:143`), blocking only on `IF/WHILE/FOR/MATCH/ELSE` (`parser.py:158`).
```a7
main :: fn() {
    if a and b and c and d and e and f and g and h {
        ret 1
    }
}
```
The `{` after `h` is 15 tokens from `if`, outside the window → defaults to True → `h { ... }` parsed as a struct literal → `ParseError` on the block contents. Valid program rejected.

**M6. 1000-iteration cap: arbitrary rejection + stdout pollution (KNOWN: PAR-17 / PRD-12).**
`parser.py:171-174` (cap), `parser.py:223-228` (warning via `print()` to **stdout**, corrupting `--format json` on a successful 1000-declaration compile), `parser.py:231-236` (leftover tokens → misleading "after parsing complete program"). Because `synchronize()` restarts at every `IDENTIFIER :=`, one error in a large function shreds the body into >1000 top-level iterations — `docs/plan/audit/open-items.md:127(c)` records a 1196-line `main` rejected this way.

**M7. Keyword set drift, reserved-but-unusable words (KNOWN in part: packet P1, `docs/plan/execution.md:360`).**
Impl reserves `int`, `uint`, `float` (`a7/tokens.py:194, 200, 222` + `:222` area) but `parse_type`'s primitive table `parser.py:934-950` omits them and `_is_type_start` `parser.py:1510-1518` excludes them → `x: int = 5` fails "Expected type"; they cannot be identifiers either. `let`, `as`, `where` (`a7/tokens.py:180, 206, 225`) are reserved and used by no grammar rule. Conversely SPEC 2.4 (`docs/SPEC.md:96-105`) lists `cast const self size_of type var using` — none are keywords (`cast` is an identifier, `size_of` is `@size_of`), and omits `not int uint float let`.

**M8. Assignment is not an expression, contradicting SPEC.**
SPEC 12.4 item 14 (`docs/SPEC.md:1934`) and grammar 13.3 (`docs/SPEC.md:1999-2003`, right-associative `assignment_expr`). Implementation handles assignment only at statement level (`parser.py:1336-1386`); `a = b = c`, `f(x = 1)`, `while (l = read()) != nil` all fail with "Expected expression"/"Expected )". Design decision needed: implement or amend SPEC.

**M9. `...` silently lexes as `..` + leading-dot float (KNOWN: `docs/plan/README.md:485`).**
`a7/tokens.py:921-925` emits `DOT_DOT`; back in `tokenize()` the leading-dot branch `a7/tokens.py:311-314` fires. `a[2...10]` → `a[2 .. 0.10]` — a wrong-but-accepting lex (SPEC 2.5 `docs/SPEC.md:129` lists `...`). `?` is an invalid character though SPEC 12.1/2.5 advertise it.

### LOW

**L1. Unterminated `/*` silently consumes the file (KNOWN: G6, `docs/plan/README.md:259,376`).** `a7/tokens.py:387-406` (comment says EOF is an accepted terminator); `NOT_CLOSED_COMMENT` (`a7/errors.py:42`) never raised. Declarations after the unclosed comment vanish without diagnostic.

**L2. Non-ASCII digits/letters accepted where SPEC says ASCII-only.** Number scan uses `isdigit()` without `isascii()` (`a7/tokens.py:307, 532`); `@builtin` and `$generic` use `isalnum()/isalpha()` un-checked (`a7/tokens.py:811-814, 1003-1007`). `x := ٣` lexes (and `int('٣')` even converts); `²` passes `isdigit` then crashes like M1.

**L3. `#` line comments supported but undocumented.** `a7/tokens.py:408-413`; SPEC 2.2 (`docs/SPEC.md:67-76`) documents only `//` and `/* */` (KNOWN, packet P1).

**L4. Char-literal diagnostics use the wrong error type.** Bad `\x` hex digit and invalid escapes in chars raise `NOT_CLOSED_CHAR` instead of `INVALID_ESCAPE_CHAR` (`a7/tokens.py:716-723, 727-736`) — message "The char is not closed" for `'\q'`.

**L5. Raw newline accepted inside a char literal.** `a7/tokens.py:737-750` consumes any single char including `\n`; `'<newline>'` is accepted.

**L6. Multi-line string spans are wrong.** Token stores only start line/column (`a7/tokens.py:611`); `create_span_from_token` (`a7/ast_nodes.py:515-523`) assumes single-line — error underlines/JSON spans are nonsense for strings containing raw newlines.

**L7. Generic-decl fallback parses an expression, not a type.** `parser.py:382-392` vs the type-aware branch at `parser.py:489-497`: `Arr($T) :: []$T` / `M($T) :: [3][3]$T` fail or misparse, while non-generic `M :: [3]i32` works.

**L8. Match-expression arms cannot be braced.** `parser.py:1895` parses `case p: expr` via `parse_expression`, so `case 1: { 2 }` fails; match statements allow braced bodies (`parser.py:2294`).

**L9. Bare `except:` in generic-struct-literal backtracking.** `parser.py:1717` swallows every exception, not just `ParseError`.

**L10. SPEC examples using reserved words as identifiers cannot compile.** `docs/SPEC.md:622` `for char in string[2..5]`: `char` fails the IDENTIFIER check at `parser.py:1195`; `string` is the STRING keyword, rejected by `parse_primary_expression`. Also SPEC 13.3 `docs/SPEC.md:2026` documents `.val` postfix, which the parser rejects (`parser.py:1636-1638`) and AGENTS.md bans — SPEC contradicts both.

**L11. Dead diagnostic plumbing.** `TOO_LONG_STRING`, `NOT_CLOSED_COMMENT`, `FILE_EMPTY`, `END_OF_FILE` defined/mapped in `a7/errors.py:33-49,167-200` but never produced (grep confirmed). `a7/errors.py:847` `class ImportError(CompilerError)` shadows the builtin.

**L12. Newlines are optional separators, contra SPEC.** SPEC 2.1 `docs/SPEC.md:65` "Newlines serve as statement terminators"; `parse_block` (`parser.py:968-974`) only skips terminators, never requires them: `x := 1 y := 2` and `ret 1 ret 2` parse as separate statements. Ironically newlines *are* load-bearing in the fragile heuristics of M3/M5.

## Verified-correct (spot checks)

- Precedence: `a7/ast_nodes.py:609-641` matches SPEC 12.4/4.3 exactly (mul 12 > add 11 > shift 10 > rel 9 > eq 8 > & 7 > ^ 6 > | 5 > and 4 > or 3); left-associativity via `precedence + 1` (`parser.py:1447`).
- Dangling-else binds to nearest `if` (standard); labeled loops `@name for/while` (`parser.py:987-1002`); multi-patterns `case 1, 2, 3:` and range patterns incl. negative endpoints (`parser.py:2192-2211`, expression fallback handles `-1..5`); slice forms `a[..3]`, `a[2..]`, `a[1..5]` (`parser.py:1579-1615`; `a[..]` is an undocumented extra); tab rejection (`a7/tokens.py:274-286`); identifier length 100 (`a7/tokens.py:783-791`) and numeric length 100 (`445, 482, 517, 570`) enforced; BOM strip; column arithmetic for single-line tokens correct.

## What I read / could not verify

Read in full: `a7/tokens.py`, `a7/parser.py`, `a7/errors.py`. Partially: `a7/ast_nodes.py:440-641`, `a7/compile.py:470-534`. Docs: SPEC.md §2, §4.3, §5.1-5.4, §12, §13, Appendices B-E; grep hits in `docs/plan/audit/open-items.md`, `docs/plan/execution.md`, `docs/plan/README.md`, `docs/audits/2026-09-18/*`; `examples/027_callbacks.a7`.

Not verified: any runtime behavior (read-only mandate — all "actual" outcomes are static traces); downstream semantic/typechecker acceptance of specific node shapes; `a7/cli.py` output paths beyond the `compile.py:514` catch-all; `a7/ast_nodes.py:1-439`; test suite expectations (e.g. `test/test_parser_fuzzing.py:486-497` reportedly asserts the 1000 cap); Rich rendering fidelity.
</task_result>
</task>