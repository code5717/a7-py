# A7 correctness holes: language needs (01)

Scope: seven reported holes. Three look already fixed (pins exist);
four are open. Evidence is file:line against current `a7/`.

## 1. Imported-file error-stage misattribution — FIXED, keep pin

Current: dependency failures keep their own stage. `compile.py:305-319`
maps `TokenizerError` to exit 4, `ParseError` to 5, `A7ImportError` to 3;
`module_resolver.py:204-220,247-248` re-raises tokenize/parse errors
unchanged with the dependency-file span, and only other failures gain the
importing declaration's span. Pin: `test/test_import_error_stages.py:1-40`.
Repro: entry `import "bad"` where `bad.a7` has a parse error gives exit 5
pointing at `bad.a7`, not exit 6 at the entry file.
Correct: unchanged. Cross-language: N/A (toolchain contract, like
`rustc` reporting the failing crate file, not the `use` site).
Fix sketch: none. Owner: `a7/compile.py` + `a7/module_resolver.py`.
Test pin: existing file covers tokenize/parse/missing stages; add an
unreadable-file (permission) case if missing. Gate: pure bug fix, no gate.

## 2. Duplicate-import acceptance — FIXED, keep pin

Current: same file imported twice in one file is a compile error.
`module_resolver.py:85-130` canonicalizes (`_canonical_import_key`:
resolved path for files, registry name for virtual stdlib) and
`_raise_on_duplicate_imports` raises `IMPORT_NAME_CONFLICT`; enforced for
entry (`:342-345`) and each dependency (`:193-196`). Different files
importing the same module stays legal. Pin: same test file.
Correct: unchanged; `helper` vs `./helper` vs symlink must compare equal
(they do, via resolved path). Cross-language: Rust/Go reject or dedupe
redundant imports at resolve time; none silently link twice.
Fix sketch: none. Owner: `a7/module_resolver.py`. Test pin: existing;
add alias-spelling variant (`helper` + `./helper`) if not covered.
Gate: pure bug fix, no gate.

## 3. Unclosed-comment acceptance — FIXED, keep pin

Current: unterminated `/*` is a tokenizer error (exit 4).
`tokens.py:397-425` tracks nesting depth and raises `NOT_CLOSED_COMMENT`
at the comment start when `depth > 0`. Pin: same test file.
Correct: unchanged. Cross-language: Zig/Rust/C all reject unterminated
block comments at lex time; nested-block rules vary but unclosed is
always an error.
Fix sketch: none. Owner: `a7/tokens.py`. Test pin: existing; keep one
nested-comment-unclosed case. Gate: pure bug fix, no gate.

## 4. Reversed range (`case 10..1`) silent never-match — OPEN

Current: silently normalized. `type_checker.py:2673-2674` folds with
`low = min(...); high = max(...)`, so `case 10..1` becomes `1..10` at
check time while Zig lowers the written order; prior audit measured
`a7=0, zig=1` on `d16_match_range_reversed`
(`docs/audits/2026-09-16/compiler/types.md:319-320`). No start>end check
in `_validate_match_pattern` (`type_checker.py:3034-3049`). Same file
`:2317-2322` folds `//`/`%` with Python semantics while runtime truncates
(missed/false duplicates, `d17/d18/e03`).
Correct: reject reversed constant ranges at compile time (error, exit 6);
dynamic (non-constant) bounds keep runtime "empty range matches nothing"
semantics and document it. Cross-language: Zig `10..1` is a compile
error; Rust `10..1` compiles but iterates empty (documented); C has no
native range; Odin `10..<1` is empty by construction.
Fix sketch: in `_validate_match_pattern`/`_match_pattern_range`, when both
endpoints are constant and `start > end`, emit type error; change the
redundancy checker to use the truncating folder, not Python `//`.
Owner: `a7/passes/type_checker.py`. Test pin: `case 10..1` exits 6;
`case 1..10` still compiles; runtime probe that a dynamic empty range
matches nothing. Gate: pure bug fix, no gate (diagnostic, not semantics).

## 5. `break` in match-case switch-lowering hazard — OPEN

Current: `break` inside a `match` case arm that sits inside a loop passes
validation (`semantic_context.py:302-321` only asks `in_loop()`, and
`match` pushes no loop frame) and the backend emits a bare `break;`
(`backends/zig.py:1466-1474`). After lowering (`_visit_match`,
`:1154-1166`, plain path emits Zig `switch`), that `break` exits the
`switch`, not the loop. Labeled `break :label` is safe; unlabeled is not.
Repro: `while` containing `match` with `break` in a case arm compiles but
loops instead of exiting.
Correct: unlabeled `break` directly inside a match-case body must break
the enclosing loop (language rule) or be rejected. Simplest correct rule:
reject unlabeled `break`/`continue` directly in a match-case body unless
it targets a loop via label; suggest the label in the diagnostic.
Cross-language: C/Zig `break` inside `switch` exits the switch (same
trap); Rust has no fallthrough switch and `break` in `match` inside a
labeled loop needs the label; Go forces explicit labeled break for the
same reason.
Fix sketch: track match-case depth in `SemanticContext` (push on
`CASE_BRANCH`, pop after) and reject unlabeled break/continue at depth
> 0 in `semantic_validator.py:240-248`; alternative lowering (if-chain
when an arm contains break) is larger and keeps a footgun. Owner:
`a7/semantic_context.py` + `a7/passes/semantic_validator.py`.
Test pin: unlabeled break in match-in-loop exits 6; labeled break
compiles and Zig output contains `break :<loop>`; match outside loop
unchanged. Gate: pure bug fix (control-flow meaning), no gate; note the
chosen rule in SPEC.

## 6. Signed division / negation / shift overflow semantics — OPEN

Current: lowering assumes two's-complement wrap-or-trap without a stated
rule. `backends/zig.py:1855-1873` emits `@divTrunc`/`@rem` for int div/mod,
`(-x)` for negation, raw `<<`/`>>` for shifts; `_use_wrapping` (`:2074-2084`)
only varies `+`/`-`/`*` suffixes by profile. Consequences: `MIN / -1`,
`MIN % -1`, and `-MIN` trap under Zig safety (exit at runtime, profile
dependent); overshift (`1 << 64`) and negative shifts are unchecked at
compile time; `safety.py:919-925` proves only nonzero divisor, and
`_prove_integer_overflow` (`:995`) does not cover div/neg/shift.
Correct: pick one rule and enforce it everywhere (const-eval, safety
proof, backend): (a) trap on `MIN/-1`, `-MIN`, div/mod-by-zero,
overshift (Zig/Rust-debug-like), or (b) defined wrapping (C-unsigned-like).
Recommendation: (a) trap, matching Zig backend and current `@divTrunc`.
Cross-language: Zig traps on div-by-zero, `MIN/-1`, `-MIN`, shl overflow
(safety on); Rust panics on all of these in debug (overflow checks) and
`<<`/`>>` panic on overshift; C leaves all of them undefined behavior;
Odin panics on div-by-zero, overflow behavior is type/mode dependent.
Fix sketch: safety pass gains `MIN/-1` and overshift obligations;
const-eval folds with truncating (not Python `//`) semantics and rejects
constant `MIN/-1`; backend keeps `@divTrunc`/`@rem` and emits checked
shift or a static overshift error for constant shifts. Owner:
`a7/passes/safety.py` + `a7/const_eval.py` + `a7/backends/zig.py`.
Test pin: constant `MIN/-1`, `-MIN`, `x % 0`, `1 << 64` cases each pin
exit 6 (const) or a safety error (dynamic); debug and release agree.
Gate: needs G3 (integer arithmetic semantics; `decisions.md:360` shows G3
partially open on wrapping/release arithmetic). Do not ship the fix
without the G3 decision between trap and wrap.

## 7. MIN/-1 family (const-fold divergence) — OPEN, fold into 6

Current: same root cause as 6, visible at compile time. The match-range
folder uses Python `//`/`%` (`type_checker.py:2317-2322` per audit) while
both const folding elsewhere and Zig runtime truncate toward zero, so
`A :: -7 / 2` with `case -3` / `case A..A` mis-detects duplicates
(`d17/d18`, audit `:321-326`). Any user-level `MIN / -1` constant has the
same shape: Python says it folds, Zig says it traps.
Correct: one truncating folder used by all passes; constant `MIN/-1` is a
compile error, never a folded value. Cross-language: Rust rejects
`const MIN / -1` at compile time; Zig rejects comptime div overflow; C
constant UB is still UB.
Fix sketch: route `_range_const_expr_value` through the preprocessor's
truncating folder (audit `:332-334` already recommends this); add
`MIN/-1` and `-MIN` guards there. Owner: `a7/passes/type_checker.py` +
`a7/ast_preprocessor.py` (shared folder). Test pin: `A :: -7 / 2` folds
to `-3` (not `-4`); `B :: MIN / -1` exits 6; duplicate-range detection
agrees with Zig on `d17/d18/e03`. Gate: same G3 decision as 6; the
constant-fold half is a pure bug fix once G3 picks trap.
