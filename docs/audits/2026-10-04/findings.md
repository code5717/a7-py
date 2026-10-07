# Audit plan, 2026-10-04

Working draft. Updated as reviewers finish. Nothing here is approved;
rows marked DECISION need the user before any code changes.

Execution order:

1. Phase 0 (regressions, gate).
2. Phase 1b steps 1-2 only: the real-pipeline test helper and the
   `build_and_run` helper. Every later fix needs them.
3. Safety holes: P2-52..P2-58, P2-69, P2-42 with decisions D-K and D-G.
   These are accepted programs that crash or run undefined behaviour.
4. Phase 1 (split and land the working tree).
5. The rest of Phase 2, then 3, 3b, 3c, 4, 4b.
6. Phase 5, which also takes Phase 1b steps 4-5 (deleting and merging
   about 640 tests, markers).
7. Phase 6, then Phase 7.

Sections 3b, 3c and 4b sit after Phase 4 in this file because they
were added later. Appendix A lists every finding that has no row in a phase
table, so this file plus `ledger-audit.md` and `reports/` is the whole
audit. Round-1 reviewer reports were delivered in chat only; their
content is recorded here.

## Inputs

| Source | State |
| --- | --- |
| Own pass: docs, layout, counts, ledger | done |
| Diff review: frontend/checker | done |
| Diff review: backend + new tests | done |
| Full review: tooling, CLI, gates, security | done |
| Full review: types, names, constant folding | done |
| Full review: user docs + site | done |
| Full review: tokenizer/parser/modules | done |
| Full review: type checker | done |
| Full review: validator/safety/pipeline | done |
| Round 2 (8 reviewers): stdlib proposal, fuzz, diagnostics, modules, CI/release, site, remaining tests, generated Zig | done; reports in `reports/`, proposal in `stdlib-proposal.md` |
| Full review: Zig backend + stdlib | done |
| Full review: test suite | done (first run finished after a stall notice) |
| Full review: SPEC vs compiler | done |
| Full review: plan/research/ledger | done |
| Full review: examples + bench | done |
| Full gate `./run_all_tests.sh --timeout 2400` | done: 10/10 checks passed, exit 0 (pytest 2548 passed, 2 xfailed; examples 51/51; debug and release artifacts 51/51; bench 10/10; error stages 61/61; docs style; secrets; wheel build and install). `run_release_checks.sh` not run; its site coverage check is red (P0-8). |

Evidence: reviewer probe sources are copied to `probes/` beside this
file (23M, about 3,700 files: `.a7`, scripts, logs; no binaries or Zig
caches; the fuzz corpus is capped at 400 files and the 1,200-module
chain at 1,500). The originals were in the session scratchpad, which
does not persist. `probes/gate.log` is the full gate output and
`probes/known-findings.md` is the brief given to round-1 reviewers.
Appendices B to J embed `ledger-audit.md`, the seven round-2 reports
and the stdlib proposal in full, so this one file holds everything. "V" = reproduced
with a compiled probe. "R" = reading only.

## Verdict

The gate is green (10/10: 2,548 tests passed, 51/51 examples, both
artifact profiles, bench, wheel). That does not unblock the
consolidated commit. Sixteen reviews produced about 190 table rows
plus Appendix A; most rows were reproduced with a compiled probe. The
suite misses them because its helpers skip passes, use `zig ast-check`
as a build check, and rarely run a binary (Phase 1b).

State in one line each:

- Uncommitted work (2,293 lines, 20 files, 9 new test files): holds
  regressions against HEAD (P0-1..P0-4, P0-9) and features whose Zig
  does not build (P0-5, P0-6). Not ready as one commit.
- Safety proof: accepts programs that crash, and in release run
  undefined behaviour (P2-52..P2-56, P2-69). Predates the diff.
- Language core: the parser accepts junk (P2-17, P2-24), the checker
  passes many programs Zig rejects (P2-30..P2-36, P2-47), modules are
  a flat merge (L25, L27, L30 not implemented).
- Docs: SPEC presents 15 of 40 "working" blocks that fail; README and
  the site missed the feature work; STATUS has become a changelog.
- Records: most shipped changes have no ledger entry (D-E); the
  constant-folding rules are recorded two contradictory ways (D-D).
- Organization: clear rules exist (AGENTS.md, plan README) and are
  not followed: todos in nine places, research in two trees, audits in
  three, 5.7G of `tmp/`, 42M tracked.

First five actions:

1. Answer D-A, D-B, D-C (they unblock Phase 0).
2. Phase 0: fix or revert the regressions; fix the gate's argument
   parsing and timeout (P0-7, P0-10); update `features.json` (P0-8).
3. Add the real-pipeline and build-and-run test helpers.
4. Close the loop and defer proof holes (P2-52, P2-53) and decide the
   release profile (D-K).
5. Split the working tree into the Phase 1 commits.

## Phase 0: stop the bleeding (before any commit)

Goal: the working tree accepts nothing HEAD ran correctly and then
breaks, and the gate can not pass vacuously.

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| P0-1 | `ref` param as `*T` breaks `if p != nil`, fn-pointer types with `ref` params, and `nil` literal args. Regression. | `a7/backends/zig.py:663-676, 2644-2670, 2333-2337` | V |
| P0-2 | Native `switch` on `f64` scrutinee and on runtime-identifier arms fails the Zig build. Regression. | `zig.py:1608-1647` | V |
| P0-3 | Overload sets and identical duplicate fns exit 0 and emit duplicate Zig members. HEAD exits 6. Call typing depends on source order. | `a7/passes/name_resolution.py:157-175` | V |
| P0-4 | Unlabeled `break`/`continue` in a match case now exits 6. It ran correctly at HEAD. Stated reason in STATUS is false. | `a7/passes/semantic_validator.py:255-266` | V |
| P0-5 | Tagged-union match emits bad Zig: redundant `else` on qualified full coverage, `case _:` beside dot arm, capture shadowing a local, unused capture in match expr. | `zig.py:1302-1368, 1649-1684, 2448` | V |
| P0-6 | `$N` kind checks skip type annotations; backend emits `comptime N: type`. STATUS says "work". | `a7/passes/type_checker.py:841-845` | V |
| P0-7 | Gate exits 0 with `0/0 checks` on a typo'd `--only`; unknown flags ignored; non-numeric timeout disables the kill switch. | `run_all_tests.sh:24-56, 96, 164-170` | V |
| P0-9 | Working tree only: two modules exporting the same function name. `a.c()` is typed with `b.c`'s signature; a call returning `char 'A'` prints `65`. P0-3 reaching modules as a silent wrong result; HEAD exits 6. | `a7/passes/type_checker.py:1998-2005` | V |
| P0-10 | Gate default timeout is 1200 s per check; pytest took 1643 s on this host, so a default run fails with TIMEOUT. `run_release_checks.sh:10` can't forward a timeout (same as C-3). Phase 0's exit needs a gate that finishes. | `run_all_tests.sh:20`, `run_release_checks.sh:10` | V |
| P0-8 | `site` coverage check is red: `features.json` not updated for SPEC heading edits. Blocks `run_release_checks.sh`. | `site/scripts/check-coverage.py:197` | V |

Decisions needed for Phase 0:

- DECISION D-A (P0-4). Today at HEAD: `for ... { match i { case 2: {
  break } ... } }` leaves the loop and prints `0 1 done`. Working tree:
  exit 6 `break_in_match_case`. Options: (1) revert the rejection,
  keep HEAD behavior; (2) keep the rejection and record it in the
  ledger as an approved break. Recommended: (1). No evidence of a
  miscompile exists.
- DECISION D-B (P0-3). Today at HEAD: two `f :: fn` with any
  signatures exit 6 `Already defined`. Working tree: exit 0, Zig build
  fails. Options: (1) restore the exit-6 rejection until ranking and
  dispatch exist; (2) keep coexistence but reject at codegen with a
  clear exit-7 "overloads not lowered yet". Recommended: (1); roadmap
  A8 already lists general overloading as a locked cut.
- DECISION D-C (P0-1, P0-2). Fix forward or revert E3/E4. Recommended:
  fix forward for E4 (gate the switch on integer/enum/bool/char
  scrutinee and comptime-known arms; else keep the if-chain). For E3,
  revert unless nil-check, fn-pointer, and nil-literal cases all get
  runtime tests; `*T` cannot represent the `p != nil` idiom AGENTS.md
  prescribes.

Exit for Phase 0: each row has a test that runs the binary; gate green
with `--timeout 2400`; then split the commit (see Phase 1).

## Phase 1: land the working tree in reviewable commits

One consolidated commit hides the regressions. Proposed split, in order:

1. AGENTS.md style rules + `check_docs_style.py` word list (after P1-6).
2. Import/comment error-stage pins (`test_import_error_stages.py`).
3. Reversed constant match ranges (`test_match_ranges_break.py`, range half).
4. SPEC text alignment (no behavior change) + `features.json` (P0-8).
5. Generic unions + `GENERIC_PARAM_MISMATCH`.
6. Payload matching (after P0-5 and P1-1..P1-3).
7. `where` clauses.
8. `$N` value params (after P0-6) or hold back.
9. Codegen E1/E2, then E4, then E3 per D-C.
10. `io.println_ok` / `io.read_line` (after P1-4) or hold back.
11. Examples 049/050 + goldens.
12. Plan docs: ledger L56/L57, roadmap, handoff.

Fixes that ride with those commits:

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| P1-1 | Owning-payload check is `payload == "string"`; struct-with-string and `[2]string` bind. | `semantic_validator.py:1594-1596` | V |
| P1-2 | `ref` tagged union cannot be matched with dot arms. | `type_checker.py:3060-3080` | V |
| P1-3 | Missing-tag match expression reports twice; `.ok` + `Result.ok` duplicate not caught; `fall` in tag arm exits 7 not 6. | `semantic_validator.py:1647-1676`, `type_checker.py:3381` | V |
| P1-4 | `__a7_stdin_read_line` drops input on the second read. | `zig.py:278-291` | V |
| P1-5 | Wrong type-arg count swallowed; `where T: Numeric, {` accepted; `where` on enum exits 5 while STATUS says 6; value param can't be forwarded and error prints twice; `_extract_value_arg` can't fold `-1` or `2 + 2`. | `type_checker.py:4289, 910, 490`, `parser.py:677` | V |
| P1-6 | `_has_clean_match` in the style checker is dead logic. | `scripts/check_docs_style.py:63-78` | V |
| P1-7 | Plan IDs in user-facing errors and comments (M33/M49, "packet item 2e"). Ad-hoc node attrs `where_clause`, `where_valid`, `overload_nodes`. | `semantic_validator.py:1601`, `type_checker.py:2296` | R |

Test repairs that ride with them:

- Replace `zig ast-check` with `zig build-exe`/run in
  `test_codegen_emit.py:25` and `test_stdlib_result.py:114`. It passes
  on five outputs that `zig run` rejects.
- `test_match_dot_e2e.py`: 1 of 10 tests runs the binary. Run all.
- Make the two overload xfails strict, or delete them per D-B
  (`test_semantic_errors.py:113`, `test_semantic_comprehensive.py:715`);
  restore `test_semantic_analysis.py:76`.
- Add messages to bare exit-6 asserts (`test_where_clauses.py:356-394`,
  `:178`, `:329`; `test_generics_value_params.py:184`).
- Fix stale docstrings (`test_match_payload.py:18-24`,
  `test_generics_value_params.py` where-class).

## Phase 1b: make the test suite tell the truth

The suite is green (2,548 passed) on a tree with the defects above.
These rows explain why. Do them before Phase 2 so each Phase 2 fix
lands with a test that can fail.

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| T-1 | Seven semantic test files each define `run_semantic_analysis` with 3 of 4 passes (no safety pass, no codegen); `conftest.py:60` omits safety too. 22 "expect success" snippets fail in the real pipeline: 13 at semantic/parse, 9 at codegen (all in `test_semantic_generics.py`, inline `$T` and `@type_set`). | `test_semantic_*.py`, `conftest.py:60` | V |
| T-2 | 30 more tests end in `assert isinstance(result, bool)` (always true). 10 hide a wrong outcome (wrong message, ParseError instead of semantic, a test bug at `generics:218`). | list in report F2 | V |
| T-3 | `compile_a7_to_zig` ignores type-checker errors and skips the validator. Three tests pin Zig output for sources the compiler rejects (`:687, :723, :740`). | `test_codegen_zig.py:48-94` | V |
| T-4 | `expect_error` catches every `CompilerError` incl. `ParseError`; with no fragment any error passes; 12 tests match the fragment `"type"`. | `test_semantic_comprehensive.py:62` and helpers | V |
| T-5 | ~156 parser tests assert only `ast is not None` (parse returns or raises). ~25 tests pass on either outcome via `except ParseError: pass`; two tokenizer tests also accept `TypeError`. 6 `assert True` report tests; 4 no-assert tests. | parser/tokenizer test files | V |
| T-6 | `test_codegen_zig.py`: `:1175` cannot fail; `:1183` is `isinstance(zig, str)`; `:1189` never asserts on `debug`; 18 `zig ast-check` sites; dead skip branches. | `test_codegen_zig.py` | V |
| T-7 | Missing zig turns the golden gate green (`skipif` at `test_examples_e2e.py:35, :63` and 9 codegen sites). Five files call zig with no version check and no cache dir. | - | V |
| T-8 | Inflation: `test_cast_safety_matrix.py` 595 cases, ~300 equivalent; `test_stdlib_registry.py` 44 tests mirror the dict; `TestDeepNestingStress` 17; `test_stage_exit_codes.py` redundant; 102 codegen example tests duplicate the e2e run. | - | V |
| T-9 | Order dependence: `test_parser_fuzzing.py` seeds global `random` at import and reseeds mid-suite. Wall-clock assert at `test_recursion_detection_scaling.py:69`. | - | V / R |
| T-10 | No direct tests: `exact_constants` (holds P2-1), `semantic_context`, `markdown_formatter`, `scope_walk`, `stdlib/io`, `stdlib/math`. No pytest markers exist (no slow/zig split). | - | V |

Work:

1. One conftest helper that runs the real pipeline
   (`A7Compiler.compile_file_detailed`) with `expect_ok`,
   `expect_exit(code, fragment)`; delete the seven private copies.
   Expect ~22 tests to go red; each is a real finding or a wrong test.
2. One `build_and_run` helper (pinned zig 0.16.0, `tmp_path` cache)
   that fails when zig is absent. Replace every `ast-check`.
3. Stage-boundary test: any program accepted in `--mode semantic` must
   not exit 7 or fail `zig build-exe`. Seed with the 9 inline-`$T` /
   `@type_set` cases and the Phase 0 probes.
4. Delete or merge ~640 tests that verify nothing (table in report
   section 3): parser smoke 170-190, cast matrix ~300, codegen example
   duplicates 102, registry ~35, deep nesting ~15, exit codes 5.
5. Add `zig` and `slow` markers so the fast loop skips native builds.

Second test review (51 more files, 789 tests; full report
`reports/tests-remaining.md`, verdict table in its section 9: keep 22,
fix 17, merge 8, delete 4):

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| T-11 | The recursion ratchet does not ratchet. The allowlist is keyed on name tuples with no member ceiling, so a rename and a rename-plus-new-member look the same; "only shrink" lives in a comment. 19 groups, 113 functions, unchanged since 2026-09-29. It includes the path that crashes at 330 terms (`:489-498`) and 8 type-checker, 3 validator, 3 safety groups, against README:178 and AGENTS.md:40-44. | `test/test_no_recursion.py` | V |
| T-12 | The scan misses handlers registered through `dict(...)`, item assignment, a decorator registry, outside attribute binding, and operator dunders (5 of 24 probes). None of those patterns exists in `a7/` today. | `test/norec_scan.py` | V (black box) |
| T-13 | No flat-chain test exists (`test_parser_depth.py`), so nothing covers P2-29. | - | V |
| T-14 | `test_audit_safety_repairs.py`: 14 of 16 tests check exit 6 plus a message substring; only the safe control is built and run; none reproduces the original crash. | - | V |
| T-15 | Defects pinned as expected behavior and absent from STATUS: returning a slice of a local array is accepted (`test_safety_precursors.py:502`, "KNOWN"); `i < xs.len and xs[i]` rejected (`:534`, false positive); `RecursionError` on cyclic types is the expected result (`test_iterative_types.py:83`, `test_iterative_type_equality_hashing.py:183`). | - | V |
| T-16 | Stale skips: `test_safety_precursors.py:187, :254` say unbraced defer emits `defer void;`; all three programs build today, so the skipped Zig checks can return. | - | V |
| T-17 | 69 tests in `test_parser_creative_cases.py`, `test_parser_combinatorial.py`, `test_parser_unicode_and_special.py` assert only `result.kind == PROGRAM`; 51 of their 72 snippets exit 6 in the real pipeline. | - | V |
| T-18 | `test_ast_preprocessor.py`: 27 fold tests exercise the secondary folder with no type map, a path the pipeline never takes; eight test a removed no-op; `:653` asserts the opposite of its name. | - | V |
| T-19 | `test_constant_folding_exact.py:355-357` has the wrap case with only `returncode != 8` as its live assert. `test_release_tooling.py:53, :538` cannot fail. `test_resume_backend_bindings.py:54-63` cannot tell a capture from a constant compare (P2-2). `test_error_stage_matrix.py` runs its 61 cases twice; exit 7 comes only from `--backend nope`. | - | V |
| T-20 | 15 test files are named after models, sessions, audits or tickets (`glm`, `resume`, `v1`, `console_review`, `language_audit_*`, `audit_*`, `saf4`, `*_pins`); rename by topic (report section 7). The zig fixture is copy-pasted in 9 files; five files call zig with no version check or private cache. | - | V |

`test_feature_pins.py` pins no defect (13 tests: bench file list, ten
build-only bench checks, two CLI rejections). Its docstring names two
accepted defects with no test: cross-module visibility and
del-through-ref.

Extra work for this phase: put a member-count ceiling per allowlisted
group and a total (113) in `test_no_recursion.py`; add a 2,000-term
flat-chain test at recursion limit 100; move T-15 items into STATUS or
fix them.

## Phase 2: silent wrong results in existing code

These predate the diff. Each produces a wrong answer or a Zig failure
after `a7` exits 0.

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| P2-1 | Untyped integer `+ - *` wraps to i32: `30*24*60*60*1000` into `i64` prints `-1702967296`; `[65536*65536+3]u8` is 3 bytes. Not a plain bug: the wrap is recorded as intended in `docs/CHANGELOG.md:67`, ledger L52 (`decisions.md:188-191`), SPEC 2.5 (`SPEC.md:205-207`), and pinned by a native-run test (`test/test_audit_backend_repairs.py:59-61`, `2147483647 + 1`). SPEC 4.2.1 (`SPEC.md:615`) and L47 say the opposite. No record or test covers an `i64` destination or an array length. L52 has no quoted user words and no before/after examples. Needs D-D. | `a7/exact_constants.py:157-166` | V |
| P2-2 | `case LIMIT:` with `LIMIT` declared below the function becomes a capture and matches everything. | `name_resolution.py:404` | V |
| P2-3 | Unknown or unresolved generic constraint is dropped: `$T: Bogus` and `$T: Signed` accept anything; user alias can't shadow a predefined set. | `a7/types.py:1017-1051` | V |
| P2-4 | Any int is assignable to any float; Zig rejects `x: f64 = a` with `a: i64`. | `types.py:139-140` | V |
| P2-5 | Duplicate enum variants exit 0. Local may reuse a parameter name. Both fail in Zig. | `name_resolution.py:307, 178, 436` | V |
| P2-6 | Float folding. Same split as P2-1: `docs/CHANGELOG.md:67` and SPEC 2.5 (`SPEC.md:208`) record "each float operation rounds in f64, overflow folds to infinity", so `1e308 * 10.0` = inf and `0.1 + 0.2 == 0.3` = false follow the record; SPEC 4.2.1 (`:610, :620`) says reject and true. Needs D-D. Bugs under either rule: `0.0 * -1.0` folds to `0.0` (runtime gives `-0`; the subtraction sign rule is applied to MUL); `1.0 / 0.0` gives inf though both texts say a zero divisor is not folded; `BIG :: 1e308 * 10.0; b: f64 = BIG` emits `0.0` (P3-24); no exact shifts. | `exact_constants.py:171-199` | V |
| P2-7 | `cast(i64, x)` with `x: $T` exits 6; SPEC 4.3 shows it. | `a7/cast_classifier.py:55-56` | V |
| P2-8 | All modules share one namespace; clash error names no file. SPEC 10.1 says file = module. | name resolution | V |
| P2-9 | Local `struct` declaration gives a misleading error. | `name_resolution.py:421-537` | V |
| P2-10 | Default output path uses `replace(".a7", ext)` on the whole path. | `a7/compile.py:1148-1150` | V |
| P2-11 | Legacy `-o other.a7` overwrites A7 source; `a7 build` refuses it. | `compile.py:556-565` | V |
| P2-12 | Rich markup in error text crashes console output (exit 8). | `compile.py:1027`, `console_formatter.py:149, 188` | V |
| P2-13 | `print_failure` prints each non-semantic failure twice; legacy CLI writes errors to stdout, subcommands to stderr. | `a7/cli.py:59-63` | V |
| P2-14 | `check --layout --format json` drops the layout; `--version` only works alone. | `cli.py:135-141, 188` | V |
| P2-15 | Console and markdown AST views drop loop bodies, match cases, else-if; markdown symbol table passes the wrong scope name. | `console_formatter.py:790-810`, `markdown_formatter.py:224-257` | V |
| P2-16 | `bench_perf.py --gate` passes with no pin for the host. | `scripts/bench_perf.py:175-182, 263-284` | R |

Frontend rows (tokenizer, parser, module resolver):

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| P2-17 | No statement terminator is required. `x := 1 2`, `x := 123abc`, `q := p.5`, `a :: 1 b :: 2` all exit 0. `1.5.3` lexes as two numbers. | `a7/parser.py:197-203, 1005-1011`, `a7/tokens.py:555-564` | V |
| P2-18 | Nested `f([f([...])])` parses in ~3x per level: depth 11 takes 2.5s, depth 20 times out at 60s. | `parser.py:1580-1608` | V |
| P2-19 | Import path with a 300-char component exits 8 (`File name too long`). | `a7/module_resolver.py:156` | V |
| P2-20 | Struct-literal lookback (10 tokens) rejects valid code: `if a + b + c + d + e + f == g {` exits 5; one-line `if c { ret P{x: 1} }` exits 5. Multi-line forms parse. | `parser.py:168-187` | V |
| P2-21 | Accepted then rejected by Zig: `1 = 2`, `g() = 2`, `defer ret`, `f :: fn(a:, b: i32)`, char literal `'€'` into `u8`. | `parser.py:1391-1410, 2442, 779`, `tokens.py:795-808` | V |
| P2-22 | A second `else:` in a match silently replaces the first; `else:` may precede `case`. | `parser.py:1974-1977, 2418-2421` | V |
| P2-23 | `./x` resolves against the entry directory, not the importing file (ledger L-entry on modules says relative to importing file). `"dup"` vs `"dup/"` pick different files with no ambiguity error. | `module_resolver.py:146-157` | V |
| P2-24 | Separators optional in lists: `Pair(i32 i64)`, `Box(,,)`, `struct { a: i32 b: i32 }`, `enum { A B C }`, `import "v" {,,}` exit 0. Positional struct literal can't span lines. | `parser.py:945, 598, 353, 2143, 2077` | V |
| P2-25 | `f :: fn()` with the brace on the next line is rejected; with params and return type it parses. `S :: struct { cb: fn() }` fails. | `parser.py:461-472, 872-880` | V |
| P2-26 | Every char-literal failure reports "not closed". Bare `@` lexes as an intrinsic. | `tokens.py:722-875` | V |
| P2-27 | SPEC vs parser: `using import` is rejected though SPEC 2.4/10.2/13.1 say parsed; `pub import` drops `pub`; `if c ret` and `while c stmt` parse without a block; if-expression may omit `else`. | `parser.py:237-285, 1201, 1220, 1914` | V |
| P2-28 | Most nodes span only their first token (calls, index, field, assignment, unary). STATUS:200 says binary nodes have no span; they now do. | `parser.py:1632-1695` | R |

Type-checker rows (`a7/passes/type_checker.py`, line numbers in that file):

| ID | Item | Lines | Ev |
| --- | --- | --- | --- |
| P2-29 | Exit 8 on a flat expression of 330 terms (`x + x + ...`): Python recursion limit. 250 terms pass. README:178 says semantic analysis uses explicit stacks. | 1634, 1698, 1768 | V |
| P2-30 | A struct/enum/union used before its declaration resolves to UNKNOWN. `A :: struct { b: B }` before `B` exits 6; self-referential `next: ref Node` exits 6; `next: Node` passes and Zig fails. Linked-list examples work only by declaration order. | 846-859, 655-663 | V |
| P2-31 | `nil` is UNKNOWN and UNKNOWN is assignable to everything. `p = nil` on a `ref i32` exits 6 (SPEC 2.6 allows it); `x == nil` on an `i32`, `id(nil)`, `[nil, nil]`, `x := []` pass. | 1751, 1332-1339, 4139 | V |
| P2-32 | Mutability is checked only for bare identifiers. Assigning a field of a `::` constant, a field or element of a by-value parameter, `s[0]` on a string, `s.len`, or `f() = 3` passes; Zig rejects. | 1349-1357 | V |
| P2-33 | `ref` arguments use assignability: `i8` into `ref i32` and a by-value param into `ref` pass; Zig rejects. | 2108-2111 | V |
| P2-34 | Bitwise ops return the left type unchecked (`i32 & i64`). `1 << 40` emits `i32`; `i <<= 40` passes while `i << 40` is rejected. | 1861-1879, 3974-4006 | V |
| P2-35 | Unconstrained `$T` counts as numeric: `add(true, false)` passes. `==` accepts struct, array, string; Zig rejects. | 4133-4143 | V |
| P2-36 | Values and types not told apart: `s.Small` on an enum value, `P.x` on a type name, `Scale{a: 1}` on an enum, `p: Nope(i32)` on an undefined base, `d := io`, duplicate enum values. | 1755, 2656, 3753, 840-845 | V |
| P2-37 | Default width disagrees with itself and with the record: `io.println("{}", 5000000000)` prints; `y := 5000000000` exits 6 ("does not fit default i32"). `docs/CHANGELOG.md:67` says the default widens to `i64` beyond `i32`; SPEC 4.2.1 says formatting and inference use the `i32` default. Part of D-D. | 1683-1690, 1232 | V |
| P2-38 | If-expressions ignore the destination type: `y: u8 = if c { 1 } else { 2 }` exits 6. Indexing through `ref [N]T` exits 6. `c += 1` and `c < 'z'` on `char` exit 6 against the code's own comment. | 2810-2834, 2487-2495, 1375 | V |
| P2-39 | One mistake reports two or three errors: only `visit_var_decl` checks `exact_diagnosed`; every signature error prints twice; a third error reads `expected '[2][2]i32', got '[2][2]i32'`; bare `ret` prints `got 'None'`. | 1182, register vs visit | V |
| P2-40 | Checker accepts, backend exits 7: SPEC 7.1 form `identity :: fn(x: $T) $T` (only `identity($T) ::` compiles); `z: $T = 0`; undeclared `$U`. Global initialised from a later global fails the Zig build. | - | V |
| P2-41 | Backend-owned, seen by this reviewer: `P{x: 1}.x` emits Zig that does not parse; `del p` after a nil check emits a shadowing capture. | zig.py | V |

Backend rows (`a7/backends/zig.py`, line numbers in that file; all
`a7` exit 0 unless noted):

| ID | Item | Lines | Ev |
| --- | --- | --- | --- |
| P2-42 | Uninitialized struct, enum, slice, fn-pointer locals and all `new T` memory are `undefined`. `q: P; q.x = 1; println(q.y)` prints `-1431655766` in debug, `0` in release. Same root as P3-21 / D-G. | 2761-2787, 952 | V |
| P2-43 | Unary `-` never wraps: `neg(i32 min)` panics in debug, prints `-2147483648` in release. Binary `+ - *` wrap. | 2164 | V |
| P2-44 | Signed `min / -1` and `min % -1` under `if m != 0`: panic in debug, undefined behaviour in release (prints 7, 8). SPEC 2.5 (`SPEC.md:196-200`) lists `MIN / -1`, `-MIN` and runtime shift amounts as undecided under gate G3 and says folds and emission "keep the current fail-closed behavior". They are not fail-closed in release (also P2-43, P2-69). | 2144-2146 | V |
| P2-45 | stdout is flushed only when `main` returns; a panic drops everything printed before it. | 252-303 | V |
| P2-46 | `del p` hard-codes capture name `p`: `p := new Box ... del p` fails Zig (shadowing). `defer del` on a `ref` param fails (second `del` emitter lacks the branch). | 1785, 3088-3092 | V |
| P2-47 | Zig build fails on: `x <<= n` (no `@intCast`); `1 << n` and `~5` (comptime_int); `s == "hi"` and `match` on a string; locals named `u1`, `std`, `f16`, `void`; top-level `std`; enum variant or union tag named `error`/`type` in a pattern; enum value over i32; `defer if ...` (emits `defer void;`); `xs := [1, 2, 3]` with a runtime index (emitted as a tuple); inner block shadowing a parameter. | 1823, 2147-2168, 2156, 515-528, 2563, 810, 3076, 941, 672 | V |
| P2-48 | Module prefix maps every non-alphanumeric to `_`: modules `a/b` and `a_b` both emit `module_a_b__f`. | `compile.py:704-706` | V |
| P2-49 | Exit 7 after the checker accepted: `tmp: $T = a` and `Pair($B, $A){...}` in a generic body; `Wrap :: struct { inner: Box($T) }`; `crr := arr + brr`; `x := io.println("a")`. | 899, 2514, 783, 917, 2189 | V |
| P2-50 | Nested functions: the checker rejects every call to one (exit 6), and the hoisting path emits them at module level where outer names are undeclared. Dead feature. | 627-637 | V |
| P2-51 | Silent fallbacks: unknown unary op emits negation (2170), unknown assign op emits `=` (3059), unknown primitive passes through (2735), `"void"`/`"undefined"`/`"anytype"` stand in for missing nodes. | - | R |

Safety, validator, pipeline rows. None matches the admitted SAF-2,
SAF-3, SAF-6, SAF-8. All but the validator predate the uncommitted work.

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| P2-52 | Facts survive a loop that ran zero times. `while d != 0 { break }  ret 10 / d` with `d = 0` exits 0, panics in debug, dumps core in release. Same shape breaks nil (`while b != nil { break }  ret b.value` prints `0` in release), bounds (core dump in release), nonwrap (release emits plain `x + 1` on max i32: UB), and `del` (segfault). | `a7/passes/safety.py:631-663, 681` | V |
| P2-53 | A deferred statement is proven with the facts at the `defer` line. `d := 5; defer io.println("{}", 10 / d); d = n` divides by zero; `defer ... b.value; del b` segfaults; `defer del b` plus `del b` double-frees. | `safety.py:700-713` | V |
| P2-54 | Block exit restores a shadowed name but keeps length facts of the inner binding: outer `s[i]` reads out of bounds. | `safety.py:547-556, 1079-1083` | V |
| P2-55 | `function_deletes` resolves callees by bare name: a parameter named like a non-deleting function hides a deleting one; use after free (segfault at HEAD). | `safety.py:790-796, 362-394` | V |
| P2-56 | `-x` is not clamped to the type range: index approved from a false interval; release dumps core. | `safety.py:856-860` | V |
| P2-57 | Match payload captures are never bound in the fact table and inherit an outer name's fact (`10 / v` approved from global `v :: 5`). | `safety.py:683-699` | V (accept) |
| P2-58 | Recursion ban bypassed eight ways, each prints `depth 5`: alias of alias, two-level forwarding, global fn constant, struct field, returned fn, array element, if-expression, through a module. AGENTS.md says alias cycles are rejected. | `a7/passes/semantic_validator.py:933-992, 1245-1282` | V |
| P2-59 | `--mode semantic` rejects every valid program with a file import (exit 6, `Unknown stdlib call`); `--mode pipeline` accepts. | `a7/compile.py:329` | V |
| P2-60 | Module declarations merge unprefixed into the entry namespace: entry `LIMIT` and module `LIMIT` clash (root of P2-8). | `compile.py:894-927` | V |
| P2-61 | Nested function bodies get no control-flow or return checks. `defer ret` and `defer break` accepted. `while true { ... ret ... }` as last statement exits 6 "Missing return". | `semantic_validator.py:153-253, 426-440, 1447-1487` | V |
| P2-62 | `check --layout` disagrees with Zig for single-variant enums, untagged and tagged unions, and fn-pointer fields (e.g. reports size 8, Zig says 12). STATUS:17 says it matches. | `a7/layout.py:85-157` | V |
| P2-63 | Safety failures are raised as `TypeCheckError`; JSON labels them with the wrong pass. | `safety.py:310` | R |

P2-52 and P2-53 are the top items of the whole audit: programs that
pass the safety proof and then crash or run undefined behaviour in
release. Root causes are two: facts keyed by identifier text, and
loops/defers/blocks patching state by hand with no join. Fix shape:
save state before a loop and join with the body exit state; re-check
deferred statements against scope-exit state; key facts, deletes and
the recursion graph by declaration identity. L32 already accepts that
safety fixes may reject programs that compile today.

Runtime contract and generated code (full report:
`reports/generated-zig.md`; timings are indicative, the box was loaded):

| ID | Item | Ev |
| --- | --- | --- |
| P2-69 | Release is `-O ReleaseFast`, so every proof gap is undefined behaviour. A runtime shift count needs no proof though `SPEC.md:219` says overshift "must stay fail-closed": `1 << 32` panics in debug; in release it segfaults or writes newlines without end (900 MB before it was killed). `math.abs(i32 min)` does the same. Release silently wrong where debug traps: out-of-bounds after a stale guard, stale-fact division, overshift, `abs(min)`, double `del` of a field (exit 0), use after `del` through an alias (exit 0). | V |
| P2-70 | stdout is fully buffered even on a terminal: a prompt printed before 1.8 s of work appears only at exit. L48 says "C-like"; C line-buffers a tty. | V |
| P2-71 | `prog \| head -1` panics with "a7 stdout write failed", a stack trace, exit 134 and a core dump, in both profiles. | V |
| P2-72 | `main` cannot return an exit code: 0, or 134 on panic, 139 on a release segfault. | V |
| P2-73 | `io.read_line()` with no argument compiles to a no-op. A 200 MB local array is accepted and segfaults with no message in release. | V |
| P2-74 | Neither profile reports leaks or double frees. Debug uses `page_allocator`: one page per `new`, 404 MB RSS for 100k 24-byte boxes, 913 ms vs 4.3 ms on alloc churn. | V |
| P2-75 | No source mapping: emitted Zig has no comments; DWARF points at the deleted `a7-native-XXXX/program.zig`; gdb `list` fails. A7 function names survive. | V |
| P2-76 | Release hello world takes 12-20 s to build and is never cached; debug is about 0.4 s warm. Binaries are static, libc-free, unstripped (10.3 MB debug, 3.8 MB release, 0.55 MB stripped) and target the host CPU (AVX-512 present; failure on older CPUs unverified). | V |

Clean: `zig fmt` and `ast-check` pass on all 102 emitted files. Nits:
redundant parentheses and `@as(usize, 0)`, per-use `.?` on preamble
globals, a dead statement in the `fall` flag machine, `_ = dead;` with
no A7 warning.

DECISION D-K (P2-69). Release profile safety. Today
`a7 build --profile release` uses ReleaseFast: a program with an
unproven shift or a stale proof runs undefined behaviour (`1 << 32`
segfaults). Option 1: release uses ReleaseSafe (traps like debug;
measured within noise on two loop kernels, 27-28% slower on print and
alloc). L49's release nonwrap emits plain `+` only for proven cases,
which stays safe under ReleaseSafe. Option 2: keep ReleaseFast and close every proof gap first
(P2-52..P2-56, shifts, `abs`). Option 3: add a third profile; roadmap
A4 says "one `--profile` flag", which rules this out unless that row
changes. L52 already sends "the -OReleaseFast safety-backstop question"
to the Wave B comparison memo, so this decision has a recorded home.
Recommended: ReleaseSafe as the default release until the proof gaps
close; keep ReleaseFast behind an explicit flag.

Performance against the L38 1.10x-of-C target:

- Zig 0.16 does not vectorize loops in Zig source. `bench/array_walk`
  takes 258 ms against 21 ms for clang (about 12x). `zig cc` on the C
  version vectorizes; three other `-mcpu` targets did not help. A
  hand-written `@Vector(16, i32)` reduction took 258 ms down to 47 ms.
- `smp_allocator` is 2.1-2.5x `malloc` on churn.
- `sort_load` at 1.13x of C (weak: one kernel, cause not isolated).
- No cost in release from the flag machine, `.?`, bounds checks,
  generics, `defer`, or print formatting; `io.println` is 0.38x of
  `printf`.
- Six bench kernels were not compared against C. `perf` and `strace`
  are not installed.

The abort probes left about a dozen small cores in systemd-coredump.

Fuzzing rows (full report: `reports/fuzz.md`; 73,385 cases with fixed
seeds, each finding confirmed through the CLI):

| ID | Item | Where | Ev |
| --- | --- | --- | --- |
| P2-77 | `--format json` exits 1 with a traceback and empty stdout on a postfix chain of about 10,000 links: `json.dumps` hits the recursion limit, called unguarded on the success path and inside the internal-error handler. Affects `ast`, `semantic`, `pipeline`, `doc`. | `a7/compile.py:42, 623, 642` | V |
| P2-78 | Postfix chains bypass the 256 nesting cap: `p.x.x...`, `a[0][0]...`, `f()()...` exit 8 at 400 links (300 pass); mixed `a[0].q()` at 200 pairs. A valid 400-level field chain also exits 8. Same root as P2-29. | `type_checker.py:1694, 1715, 2561` | V |
| P2-79 | An exact constant over 4,300 digits exits 8: `x: i32 = 1e4300` raises `ValueError` while formatting the error message. A product of 240 twenty-digit integers reaches it too. | `type_checker.py:3956, 3960` | V |
| P2-80 | Hang on a 16-byte literal: `x := 1e999999999` times out; `1e9999999` takes 4 s. `Fraction(raw_text)` has no exponent cap (SPEC Appendix C states 4,096). | `a7/exact_constants.py:98` | V |
| P2-81 | The safety pass is quadratic: 10,000 locals take 11.7 s (`safety.py:500`); 4,000 `new`/`del` pairs take 15.9 s (`:510`); loop nesting depth (`:415, :470`). | `a7/passes/safety.py` | V |
| P2-82 | `E :: enum { A = 1e99999 }` exits 0 and emits `std.math.inf(f64)` as the tag. `K :: f() { p: struct { x: i32 } }` passes `--mode semantic` then exits 7. | - | V |

Clean: no exit 8 from the tokenizer, parser, name resolution,
validator, backend or formatters. JSON is valid on every exit 0-8 path
except P2-77. The nesting cap stops every recursive-parser dimension
(24 tested); the real limit is 85 to 256 source levels by construct.
Nothing scales worse than quadratic; outside P2-81 everything is
linear (1.8 ms per function, 0.2 ms per expression statement). The
human token table costs 140 us per token, so 1 MB inputs exceed 20 s.
Of 11,560 fuzz programs that passed semantic, 128 exited 7 and none
exited 8; all exit-7 messages are already rows here except P2-82.
Two 1-2 MB inputs killed an in-process worker with no Python
exception; cause not isolated.

Module rows (full report: `reports/modules.md`):

| ID | Item | Ev |
| --- | --- | --- |
| P0-9 | Listed in the Phase 0 table. | V |
| P2-64 | `a.fb()` is accepted when `fb` lives in module `b` or the entry; Zig fails. Same plain-name lookup. At HEAD too. | V |
| P2-65 | A module's own import aliases are dropped in the merge: a module doing `console :: import "std/io"` exits 6 unless the entry declares the same alias. (`compile.py:914`) | V |
| P2-66 | Only calls work through an alias. `alias.CONST`, a global read, a function pointer, or the alias as a value pass a7 (and `a7 check`) and fail Zig; a global write exits 6. A function used as a value is never prefixed, even in its own module. | V |
| P2-67 | One file reached as `d` and `./d` (or symlink, or `pkg` vs `pkg/mod`) from different importers emits one copy and two prefixes; Zig fails. Unicode module name emits an invalid Zig identifier. | V |
| P2-68 | Selected-import lists are never validated: `import "lib" { Nope }` exits 0. Codegen errors in a module set JSON `file` to the entry (against STATUS:13). | V |

Ledger rules L25-L31 against the code: L25 file = module not
implemented (flat scope); L26 duplicate import implemented per file;
L27 `_` private and `__` reserved not enforced (a user `__a7_stdout_print`
collides with the preamble); L28 alias clash only at top level; L29
holds; L30 relative-to-importing-file not implemented, every `..`
rejected; L31 holds. Passing: chains, diamonds (global initialized
once), cycles detected, `mod.a7` directories, a 1,200-module chain,
deterministic output.

The module system needs one design pass, not row-by-row patches:
per-module scopes with real qualification replace the flat merge
(covers P2-8, P2-23, P2-60, P2-64..P2-67, L25, L27, L30). P-MOD is
still "draft for user decision"; that packet is the gate (D-E).

DECISION D-F (P2-17, P2-24, P2-27). Requiring a terminator and commas
rejects programs that compile today. Example: `x := 1 2` compiles and
runs today; after the fix it exits 5. Recommended: reject, with a scan
of `examples/` and `test/` first to show nothing valid depends on it.

DECISION D-D (P2-1, P2-4, P2-6, P2-8). Each changes accepted programs
or printed values, so each needs a before/after packet under the
"Language change approval" rule. P2-1 is a SPEC violation with wrong
output; recommended first.

## Phase 3: docs and site catch-up

| ID | Item | Ev |
| --- | --- | --- |
| P3-1 | README + `site/public/docs/` untouched by the feature work: `where` "reserved", `union(tag)` "reserved", "untagged unions", no `println_ok`/`read_line`, examples table stops at 048. Then `bun run sync:exports`. | V |
| P3-2 | `site/public/docs/language/modules.md:16` snippet exits 6 (duplicate `std/io` import). | V |
| P3-3 | `compiler.md:177` (library without `--lib`), `status.md:53-62` (two closed gaps), `functions.md:75` (wrong stage), `stdlib.md:101` (stubs that don't exist). | V |
| P3-4 | `ERROR_CATALOG.md`: header says 87 codes, enums hold 89; missing `break_in_match_case`, `continue_in_match_case`, `unknown`; exit table omits missing-Zig (2), Zig build failure (7), output conflict (3); wrong trigger for `generic_param_mismatch`. | V |
| P3-5 | README says 43 examples (51). CLI reference omits `--lib`, `--build-profile`, `--no-nonwrap`, `check --layout`. | V |
| P3-6 | RELEASE.md and site release page list gate steps the script no longer runs; omit bench and `--verify-sdist`. | V |
| P3-7 | CHANGELOG Unreleased contradicts itself on `$N`/`where`/overloads. STATUS says 27 tests in `test_match_payload` (30) and misplaces the xfails. | V |
| P3-8 | STATUS is a changelog: 15 "fixed" bullets with test lists. Cut to surface, open gaps, priorities. CHANGELOG: drop internal items and test paths. | V |
| P3-9 | ARCHITECTURE map omits `layout.py`, `cast_classifier.py`, `generics.py`. `docs/README.md` lists ERROR_CATALOG as historical and says the site build regenerates `llms*.txt` (only `sync:exports` does). | V |
| P3-10 | `docs/design-system.md` describes a removed site. Move it, `ERROR_ANALYSIS.md`, and the PDF to `docs/archive/`. | V |
| P3-11 | `site/docs/verify-snippets.py` skips fences without `main` and is not in `bun run check`. Run all fences in the check. | V |
| P3-12 | `check_docs_style.py` covers 38 of 325 markdown files, globs two directories that don't exist, non-recursive in `docs/`. Decide scope: verbatim evidence under `docs/plan/research/` and `docs/audits/` must stay exempt. | V |

SPEC rows (`docs/SPEC.md`; 40 blocks presented as working: 25 pass and
15 fail as written, 28 and 12 with bare `print` adapted; 7 error
examples all reject correctly):

| ID | Item | SPEC line | Ev |
| --- | --- | --- | --- |
| P3-13 | Inline-`$T` generic fns (`identity :: fn(value: $T) $T`) exit 7 even uncalled. SPEC 7.1 calls this the core rule and 6.1 labels it "Current". Only `name($T) :: fn` runs. `test_where_clauses.py:96-160` uses the failing form and never reaches codegen. Same at HEAD. | 913-931, 1089-1118, 1218 | V |
| P3-14 | Stray closing fence at L1839 swallows headings 10.3, 10.4, 11, 11.1; TOC link dead; style check skips that text. | 1839 | V |
| P3-15 | Bare `print`/`printf` used 24 times in working blocks; both exit 6. | 5.1-6.3, 8.3 | V |
| P3-16 | 5.2 match block: arms yielding `i32` and `string` exit 6; `string` payload bind exits 6; "bare tag" comment with no bare tag. String match (`case "a":`) passes a7, fails Zig; L752 and L2176 imply support. | 752-795, 2176 | V |
| P3-17 | 6.1: `DivModResult{a / b, a % b}` exits 6 (divisor proof never explained); anonymous struct return with a `math` call fails Zig. 8.1 uses `fn example() {` (exit 5). | 885-906, 1264 | V |
| P3-18 | 10.x: block imports `std/io` twice (exit 6 by its own rule L1776); `using import` exits 5; selected import called "not runnable" but type use runs; `p: v.Vec3` exits 5 (unlisted gap); 10.1 "private helper" contradicts 10.4. | 1727-1791 | V |
| P3-19 | 3.3 `T.len`, `arr.len`, `T.element` fail. 7.2 shows generic enums; L1173 says out of scope. 7.3 says `@type_set` aliases are implemented; they exit 7 (STATUS:153 admits it). `Handle :: MyInt` alias unusable as a type. | 314-496, 1128-1183 | V |
| P3-20 | Rules stated, not enforced: `$T1` compiles; Appendix C limits (256 params, 33 generics, 9 dims, 1024 fields, ...) all exit 0, real cap is nesting 256; `MIN / -1` "fail-closed" exits 0; `~5 + 1` fails Zig. | 1097, App. C, 199 | V |
| P3-21 | Initialization contradiction: L313 says zero-initialized, L535 says uninitialized. `c: Counter` then `c.value += 1` prints `-1431655765`; an uninitialized slice prints a garbage `len`. No diagnostic. | 313, 535 | V |
| P3-22 | Grammar section 13 does not match the parser: productions for forms that exit 5; no productions for match, if, for, while, block, enum, `new`, `del`, `fall`, literals. | 2300-2390 | V |
| P3-23 | 12.2, 12.3, Appendix B describe a different compiler: no `AST_*` names, no `E0xxx` codes, wrong error format. Appendix E "historical" but titled "Current". Section 9 disclaimer sits under 9.1 only. 4 of 18 `file:line` citations stale. 15 lines with emojis. | 2030-2200, App. B/E | V |
| P3-24 | `BIG :: 1e308 * 10.0` then `b: f64 = BIG` emits `0.0` (compiler bug, belongs with P2-6). | 208, 610 | V |

P3-21 is a safety hole, not a doc bug: move to Phase 2 once the
intended rule is chosen (DECISION D-G: zero-initialize, or reject
read-before-write. Today `c: Counter; c.value += 1` prints garbage).

SPEC reorganization (proposal): split SPEC into what compiles today
and `docs/design/` (section 9, methods, variadics, intrinsics, planned
stdlib, Appendix B). Delete 12.2, 12.3, Appendix E. Make every `a7`
block a complete program compiled by a gate script; tag others
`a7-planned` or `a7-error` with the expected exit. Pick one generic fn
spelling. Rewrite section 13 from the parser or delete it. Cite
symbols, not `file:line`.

Examples and bench rows:

| ID | Item | Ev |
| --- | --- | --- |
| P3-25 | All of 000-049 match their goldens. 51 sources, 51 goldens, no orphans. | V |
| P3-26 | False or stale comments: `045:27-29` (`{0}` claim), `044:10-13` (guard claim), `037:6-8` (tagged unions "not implemented"), `043:1` (lists `round`, which doesn't exist), `048:1-12` (promises a queue that isn't there), `004:15,56` ("multiple return values"). | V |
| P3-27 | `025_linked_list` uses `isize` index with `-1` sentinel; AGENTS.md cites it as the model for `usize`. Names that don't match content: 008 switch, 013 pointers, 017 methods, 018 modules, 035 matrix. | V |
| P3-28 | No example covers: tagged-union payload match, generic unions, `where`, `@type_set`, `$N`, file-backed imports, `[]T` params, labeled break from a nested loop or match. Duplicates: 008 in 046, 021 in 005+007, 023 in 004, 012 in 005, 047 3-5 repeats 044. | V |
| P3-29 | Golden `043` pins a 34-digit compile-time float (`math.sqrt(2.0)`); the runtime call prints 17 digits. Goldens 019/045 show Zig spelling (`null`, `.{ .x = 0 }`). | V |

Phase 6 bench corrections (B0 promotion):

| ID | Item | Ev |
| --- | --- | --- |
| P6-1 | Handoff expected value for `mem_shared` is wrong: it says 4999999500000; program prints 49999995000000 (= sum of 0..9,999,999). Dropped digit, same at HEAD. | V |
| P6-2 | `mem_cache` (0.0007 s) and `mem_copy` (0.0024 s) are folded away in ReleaseFast and use no heap. Do not promote as written. | V |
| P6-3 | `mem_text` (0.018 s) and `mem_cyclic` (0.039 s) are too short for a 1.15x gate. Existing pins `alloc_churn` (0.0049 s) and `print_lines` have the same problem. | V / inference |
| P6-4 | Ready after a header comment: `mem_shared`, `mem_returned`, `mem_cleanup`. Six of seven staged files lack headers; `mem_cache.a7:8` has an uncommented proof workaround. `bench/README.md` names no workload. | V |

DECISION D-H (P6-2). L56 says promote all seven. Two measure nothing.
Options: promote five and rewrite two to defeat folding and use the
heap; or promote three now. Recommended: promote the three ready ones,
rewrite four with longer runs.

## Phase 4: ledger, roadmap, layout

| ID | Item | Ev |
| --- | --- | --- |
| P4-1 | Ledger has no entries for E1-E4 approvals (roadmap says approved 2026-10-03), `$N`, `where`, overload coexistence, payload match syntax, bare `case tag:` rejection, or the break rejection. Add entries or mark unapproved. | V |
| P4-2 | `decisions.md` L50-L57 scope line is malformed (joined lines). | V |
| P4-3 | Roadmap D1 says examples 049+ queued; they exist. Baseline section names HEAD `701c679`. | V |
| P4-4 | Handoff 2026-10-02 B0 steps not done: 7 `mem_*.a7` still in `tmp/b-benchspec/`, `bench_perf.py` list unchanged, STATUS says "ten-program". Handoff's "do not touch zig.py/types.py/SPEC" note is stale. Write a new handoff; don't back-edit. | V |
| P4-5 | `docs/research/language-needs/` (26 untracked files) sits outside `docs/plan/research/` and has no index entry. Move or index. | V |
| P4-6 | `tmp/` has 12 loose top-level files (rule: none). `.gitignore` misses `examples/*.md`, built binaries from README commands, `*.mutantbak`. | V |
| P4-7 | Repo tracks 42M / 1,443 files; `docs/audits` 19M incl. two identical 4.86M JSON files; ~100 audit logs under `site/docs/audits/`. | V |

Plan/research review is in. Full tables: `ledger-audit.md` beside this
file. It widens P4-1 and adds:

| ID | Item | Ev |
| --- | --- | --- |
| P4-8 | Approval gap is wider than E1-E4. No record on disk for: generic unions, `$N`, `where`, overload coexistence, dot-arm match and the bare `case tag:` rejection, `println_ok`/`read_line`, struct constraint enforcement, import-cycle diagnosis. Duplicate-import and bare-imported-call rejections cite L25/L26, but `decisions.md:255` requires P-MOD approval and P-MOD is still "draft for user decision". | V (absence) |
| P4-9 | Bare `case tag:` compiled on 2026-09-16 as a whole-union capture (`plan/README.md:238-258`), listed "needs approval" (`:410`). It now exits 6. Probes exist in `tmp/g5a-2026-10-03/`; the packet was never filed. | V |
| P4-10 | Roadmap rows cite approvals the ledger lacks: A4 "QUEUED, approved" (`PKT-num-D/G` defined nowhere), A6 "never", A8 "Locked cuts", B8 NEVER. Sources are research files, which approve nothing. A8's "GC" cut contradicts L37. | V |
| P4-11 | L47 contradicts itself (`decisions.md:148` vs `:275`). L52/L53/L55 lack quoted user words. Gate stub `:350-362` stale. | V |
| P4-12 | Todo lists exist in nine places besides the roadmap and STATUS. B0 and Wave B (L56/L57) have no roadmap row; roadmap A5 says PROPOSED while L57 says go. | V |
| P4-13 | IDs defined nowhere: G5A, G5B, G5B-2, PKT-num-D/G, Wave A, "phases 2a/2b/2c", "plan PROGRESS". Roadmap B1-B8 collide with memory B0-B3; D1-D4 and E1-E4 collide with older families. Add `docs/plan/ids.md`. | V |
| P4-14 | Stale pointers: `plan/README.md:285, 238`; STATUS:232 and `audits/README.md:4` name `execution.md` as tracker; `docs/README.md` never links the roadmap; `lang-safety/README.md:22` says L1-L22. | V |
| P4-15 | 19 cited `tmp/` paths are gone; 38 links use absolute `/home/cx89/` paths; `plan/research/README.md` misses 14 entries; `language-needs/00` omits files 22-25. | V |

DECISION D-E (P4-8..P4-10). Chat approvals can't be seen from disk.
For each row in `ledger-audit.md` "no record" table the user says one
of: approved (then it gets an L-entry with quoted words), not approved
(then the change is held or reverted), or decide later (then STATUS
marks it unapproved). Example of one row: today `case ok:` on a tagged
union exits 6; on 2026-09-16 it compiled and captured the whole union.

## Phase 3b: diagnostics

Full report: `reports/diagnostics.md` (219 probes). Of 28 common
beginner mistakes, 7 give a message a newcomer can act on, 10 partly,
11 not at all.

| ID | Item | Ev |
| --- | --- | --- |
| G-1 | Undefined names are labelled as types: a typo'd variable prints `Undefined type (Identifier 'totl')` with the hint "import the module that defines the type". | V |
| G-2 | Safety-proof errors never say what shape the compiler accepts. Divisor, index, slice errors print no hint (`safety.py:921, 928, 941` pass `diagnostic_code=None`). `if n != 0`, `if i < 5`, `if p != nil` appear in no message. `n := new Node; n.v = 3` fails with a circular hint. | V |
| G-3 | Human output never names the file; with errors in two modules only `[line N: col M]` shows. A parse error in an imported module prints no snippet. | V |
| G-4 | Parse errors have no hints and leak token kinds (`Expected RIGHT_BRACE, got EOF`). `return x`, `&&`, `||`, `++`, `let`, `fn add(...)`, `f64(a)` all get generic text. | V |
| G-5 | `a7 check` (first command in README) drops the snippet and the hint. | V |
| G-6 | JSON details carry no error code and no hint; `type` is the Python class name (`ValueError`, `CompilerError`); `message` embeds `file:line:col:`; codegen details have no span; `compiler.md` does not document the `details` fields. | V |
| G-7 | 15 headline/hint mismatches (`Struct has no such field (Stdlib module ... has no function 'printn')`, `Type mismatch (Missing struct fields: y)`, `Requires numeric type` for string `+`). Leaks: `unknown type`, `NodeKind.TYPE_ARRAY`. A 70,000-char line prints whole. | V |
| G-8 | Cascades: three errors for one mistake when `unknown type` propagates (undeclared `count = 0`, missing `io` import, type declared later). | V |
| G-9 | ERROR_CATALOG: 13 of 17 sampled rows don't match what the compiler prints. `duplicate_generic_param` program is accepted. | V |

Order: G-2 first (the proof errors are the ones users can't guess),
then G-1, G-3, G-4. Add the error code to JSON (G-6) before generating
the catalog from `a7/errors.py` (P3-4, G-9).

## Phase 3c: docs site as software

Full report: `reports/site.md`. Low priority next to the compiler rows.

| ID | Item | Ev |
| --- | --- | --- |
| W-1 | `bun run check` still exits 0 with `site.js` emptied, all custom CSS removed, and `<main>`, `lang`, and the skip link deleted. Nothing tests the page template, JS, or CSS. | V |
| W-2 | No error reference on the site: the error catalog is not linked; four error names appear nowhere. The 435 feature status records live only in `manifest.json`, not in HTML. | V |
| W-3 | `404.html`: links differ from body text by color only (2.21:1 light, 1.65:1 dark; needs 3:1), no nav, hardcoded base path. | V |
| W-4 | Search: 39% of `search.json` is feature-id text copied onto every section; substring matching gives tied id-only hits. | V |
| W-5 | Preview server serves pages without the `/a7-py` prefix and plain text on a miss, so base-path bugs and the 404 page are never exercised. | V |
| W-6 | Tailwind scans the whole `site/` tree though no page uses a utility. No-JS mobile shows the 23-link nav above content. 37 of 157 GitHub source links point at paths not on the pushed `master`. `site/docs/verify-*.py` are wired into nothing and overwrite tracked files. | V / R |

Clean: text and focus contrast pass AA in both themes, no XSS path in
search, reproducible builds, self-hosted fonts, no third-party
requests. The site never renders SPEC, so the stray fence (P3-14) does
not reach it.

## Phase 4b: CI, release, repo settings

Full report: `reports/ci-release.md`. CI last ran on `0294071`
(2026-09-20); HEAD has 8 unpushed commits plus the dirty tree, so CI
says nothing about HEAD.

| ID | Item | Ev |
| --- | --- | --- |
| C-1 | `.github/workflows/claude-code-review.yml:55` passes `direct_prompt`, which the pinned action does not define; the review prompt and its untrusted-content guard are dropped. Last 100 runs: 31 failed, 17 skipped, 0 succeeded (cause unverified). | V |
| C-2 | GitHub settings (public repo): no branch protection on master, default workflow token is `write`, secret scanning, push protection and Dependabot security updates off, unused `pypi` environment. Seven Dependabot PRs open since June/July. | V |
| C-3 | Gate default timeout is 1200 s per check; pytest took 1643 s here. `run_release_checks.sh:10` calls the gate with no timeout and can't forward one. No `timeout-minutes` in any workflow. | V / runner unverified |
| C-4 | Release path never ran: no tags, no releases. `verify_release_version.py` would accept `v0.3.0` today with 190 Unreleased changelog lines and ignores `a7/__init__.py`. `release.yml` attests artifacts from any branch via `workflow_dispatch`; RELEASE.md verification accepts them. No rollback section. | V |
| C-5 | `deploy-docs.yml:8-11` gives the build job `pages: write` and `id-token: write`; deploy does not wait for CI. | V |
| C-6 | sdist ships 87 test files without `conftest.py` or fixtures. `verify_wheel_install.py --skip-build` accepts a stale wheel. `pyproject.toml` has no license, authors, classifiers; `requires-python >=3.13` open-ended, only 3.13 tested; version in three places. | V |
| C-7 | `ci.yml:50` runs pytest with `--tb=no`; no caching. | V |
| C-8 | Agent guidance: `AGENTS.md:213` ("no recursion anywhere in `a7/`") contradicts `:33-44`; "Docs Accuracy" and "Out of Scope" live only in `CLAUDE.md`, so other agents never see them; neither file says how to get Zig, how long the gate takes, or that the gate deletes `dist/`. `.interface-design/system.md` and `test.sh` are orphaned. | V |

Clean: runtime dependency is `rich` only, lock matches, all 11 actions
SHA-pinned, no `pull_request_target`, no injection path, no secrets in
history, no CDN assets on the site.

DECISION D-I (C-2). These are GitHub settings changes outside the
repo: turn on branch protection, secret scanning and push protection,
set the default token to read. Only the user can approve them.

## Phase 5: cleanliness and structure

After behavior is stable. No behavior change per A4.

- One constant folder. Today four exist with different integer rules
  (`exact_constants`, `const_eval`, `ast_preprocessor.py:626-640`,
  `_extract_value_arg`).
- Union generics clone struct generics (four parallel dicts, ~4
  cloned methods). Merge.
- Dead code: `NameResolutionPass.modules` and the unused half of
  `ModuleTable`; unused `SemanticContext` and `SymbolTable` members;
  `a7/generics.py` (5-line re-export, one test importer);
  unreachable `LOSSLESS` branch in `cast_classifier.py:72-75`;
  unreachable unknown-tag branches in validator and checker.
- Parser: one `_expect_statement_end()`; an explicit
  `no_struct_literal` flag instead of token lookback; one
  `_parse_delimited` helper that enforces commas; bounded lookahead
  for type-vs-expression call arguments. Declaration dispatch after
  `::` is written three times. 108 `ParseError.from_token` calls, 8
  pass `source_lines`.
- Tokenizer: the 0b/0x/0o block is repeated three times; the two-char
  operator chain 18 times.
- Unraised error codes: 5 tokenizer, 9 semantic, 8 type (list in the
  frontend report). Cycles raise an untyped `SemanticError` while
  `CIRCULAR_IMPORT` sits unused. Dead: `create_error_handler`,
  `topological_sort` (SPEC 10.2.2 cites it), search-path methods,
  seven unused parser imports.
- AST: `variant_type` and `has_fallthrough` read but never set;
  `struct_type` typed node but holds `str`; `else_case` is a list in
  statements and a node in expressions.
- Formatters: shared symbol-walk helpers copied between console and
  markdown and drifted; unused imports; bare `except:`.
- Scripts: `build_examples.py` and `verify_examples_common.py`
  duplicate helpers; E2E check is a subset of the debug artifact
  build; error-stage matrix runs twice; `mutation_harness.py` is
  orphaned and `--check` can't return 0.
- CI re-lists checks instead of calling the gate; Zig version
  hard-coded in four places.
- AST walking: six separate child enumerations (two validator tables
  missing 20 and 10 node fields, `fields()`, a preprocessor table,
  `vars(node)`, `__dict__`). One shared child iterator in
  `ast_nodes.py`. "Returns on all paths" exists in three passes. The
  validator walks the program five times.
- Middle dead code: `validate_nil_usage`, `_block_exits_current_block`,
  the no-op `_visit_expression_iterative` walk, `_lower_field_sugar`,
  `backend_import_errors` (stage always ok), `compile_project`.
  `compile_file_detailed` is ~490 lines; split by stage.
- AGENTS.md recursion paragraph is too broad: safety `_visit_stmt`,
  `_visit_expr` and validator `visit_statement` are recursive and
  allowlisted.
- Type checker dead code: write-only non-negative fact machinery
  (2727-2788); `_integer_literal_value` defined twice (2790, 4015);
  never-pushed `'action'` branch (1262); 12 unused imports. State:
  four name-keyed dicts, an `id()`-keyed `node_types`, ~14 ad-hoc node
  attributes; `analyze()` resets six fields but not `exact_bindings`,
  `node_types`, or the four dicts. Duplicates: signature building
  (352-401 vs 956-1029), match pattern loop (1520-1591 vs 2836-2901).
  Errors swallowed into UNKNOWN at 836, 3754, 702, 2096.
- God-file splits (roadmap D4): parser 2,469, type_checker 4,305,
  zig 3,097. Proposed checker split, nine modules under `checker/`:
  `core`, `type_resolve` (two-phase: names, then fields; owns P2-30),
  `assignability` (one mismatch emitter; owns P2-39), `declarations`,
  `statements` (lvalue + mutability; owns P2-32), `expressions`,
  `calls`, `generics` (one struct/union path), `match` (one pattern
  loop).
- Proposed backend split, eight modules under `zig/`: `runtime`
  (preamble, io helper names), `names` (quoting incl. primitives,
  scopes), `analysis` (collectors), `types`, `decls` (one generic
  wrapper), `stmts` (one brace-wrap helper, one `del` emitter),
  `match`, `exprs`. Ratchet keys in `test_no_recursion.py` must be
  renamed one-for-one.
- Backend dead code: `_mutated_vars`/`_collect_mutations`,
  `_declared_structs`, four `base.py` members, `backend_map` (only
  tests read it; zig.py hard-codes the names), the `new [N]T` branch.
  Duplicates: two `del` emitters, call-argument loop twice, 23
  push-scope/brace sites, struct vs union generic emission, three
  loop-body copies. Fragile: paren stripping by first/last char,
  format-string rescans, `StringIO` rebuilt per `else`.

Static analysis (run 2026-10-04, read-only, after the reviews):

- The repo configures no linter and no type checker (`pyproject.toml`
  has no `tool.ruff`, `tool.pyright` or `tool.mypy`), and the gate runs
  neither.
- `uvx ruff check a7 --select F`: 66 findings (42 unused imports, 12
  f-strings without placeholders, 11 unused variables, 1 redefinition).
- `uvx pyright a7`: 563 errors. 306 are in `types.py`, 62 in
  `type_checker.py`, 34 in `zig.py`. 319 are attribute-access errors,
  the type-level view of the ad-hoc node attributes listed above; 15
  are unresolved imports (environment, not checked further).
- Proposed: add `ruff check --select F` to the gate now (55 of 66 are
  auto-fixable); add pyright per module as each god-file is split.

Spot checks by the orchestrating session (compiled and run, working
tree): P2-52 `while d != 0 { break }  ret 10 / d` exits 0 and panics
"division by zero"; P2-1 prints `-1702967296`; P2-17 `x := 1 2` exits
0 and prints `1`; P0-4 bare `break` in a match case exits 6. All four
match the reviewers' reports. The other rows rest on the reviewers'
own probes.

Not covered by this audit:

- `./run_release_checks.sh` was never run (known red at P0-8).
- Line and branch coverage were never measured; no mutation run.
- macOS, Windows, Python versions other than 3.13, older x86-64 CPUs.
- The content of `docs/lang-safety/` and `docs/audits/` (indexes and
  links only), and research content.
- The live site and whether docs deploys succeed.
- Six of ten bench kernels against C; no `perf` or `strace` on the box.
- Approvals for changes older than CHANGELOG "Unreleased".
- Fuzzing of imported files, of `build`/`check`/`run`, and of emitted
  Zig from fuzz programs.
- Each reviewer's own "not reached" list (Appendix A and `reports/`).

## Phase 6: resume the roadmap

Only after Phases 0-1.

1. B0 promotion per D-H and rows P6-1..P6-4 (three workloads ready,
   four need rewriting; fix the `mem_shared` expected value).
2. G5B-2 checker-typed `Result`.
3. Wave B prototypes (B1 arena, B2 RC, B3 memo).
4. Numerics A4.

## Phase 7: general-purpose stdlib (proposal only)

Full document: `stdlib-proposal.md` beside this file. Design only;
nothing is approved or implemented. Starts after Phases 0-2, because
it depends on fixes there.

Recommended architecture: hybrid. About 40 typed hooks stay in the
Python registry and lower to Zig (printing, OS calls, string
primitives, `List`/`Map` handles). Everything else ships as `.a7`
source files in the wheel. Evidence from the reviewer's probes:
`import "std/strings"` already resolves a file at
`<entry>/stdlib/std/strings.a7`; eight A7-source modules (241 lines)
ran natively and added about 0.15 s of front-end time; a 140-line JSON
event reader ran on one input.

| Phase | Modules | Gate |
| --- | --- | --- |
| A (no heap, 18 modules) | `io` (typed), `option`/`result`, `slices`, `strings`, `ascii`, `bytes`, `math`, `conv`, `sort`, `hash`, `random`, `time`, `os`, `fs` (caller buffers), `path`, `testing`, `json` (event reader and writer), `yaml` (event reader) | prerequisites 1-5, 7 |
| B | `text`, `list`, `map`, `set`, `data`, `ring` | memory decision (Wave B, L42) |
| C | `process`, `log`, `net` | later |

Prerequisites, mapped to rows here:

1. Checker types hook calls from a declared signature (G5B-2; today
   `match io.read_line(...)` exits 6).
2. Type names scoped per module (P2-8, P2-60; a second `Option` in any
   imported module exits 6).
3. A generic function may build and return `Option($T)` (P2-49; today
   exit 7).
4. `string` payloads bind in `match` (P1-1, M33/M49).
5. String equality, length, byte view, `char`/`u8` casts (P2-47, P2-38;
   the rest is new).
6. Memory decision for `List`/`Map` handles; `new [N]T` is rejected.
7. New: the bundled search path at `a7/compile.py:279` points at a
   repo-root `stdlib/` that does not exist and that `pyproject.toml`
   would not ship (R); move it inside the package and reserve `std/`.
8. New, not blocking: the index prover fails on a guard over a
   field-loaded index or two slices; a checked `at`/`put` accessor
   written in A7 passes today.

User decisions U1-U14 are in the proposal, each with a before/after
snippet: free functions vs method sugar; one `Result` form vs
panicking twins; compiler-provided `Option`/`Result` vs scoped types;
explicit vs auto-imported `io`; `std/` prefix only; list sharing and
copy spelling; checked accessors vs trusted stdlib mode; `strings.len(s)`
vs `s.len`; ship `os.arg_or` now; may a project file shadow `std/`;
confirm the unapproved NEVER/LATER rows; typed registry hooks vs
`extern fn`; YAML subset vs full 1.2; event readers in phase A.

Open points:

- Sections 3.21-3.23 add `std/json`, `std/yaml`, `std/data`. The user
  confirmed on 2026-10-04 that they gave the reviewer this instruction
  ("add json and yaml parsers into stdlib"). It reverses roadmap B8
  "JSON later. YAML/TOML NEVER" for JSON and YAML. It needs a ledger
  entry with those quoted words and an edit to roadmap row B8; neither
  is written yet. Subset vs full YAML 1.2 is still open (U13).
- Not verified: claims about other languages and Zig call names are
  from memory; no hook was written; no YAML reader body exists; the
  `time`, `os`, `fs`, `path`, `conv`, `utf8`, `yaml`, `data` examples
  ran only against stubs.

## Open questions for the user

Each needs a yes/no. Examples are with the decision text above.

| ID | Question | Recommended |
| --- | --- | --- |
| D-A | Bare `break`/`continue` in a match case in a loop: keep HEAD behavior (leaves the loop) or keep the new exit 6? | Revert to HEAD |
| D-B | Same-name functions: restore exit 6 `Already defined`, or keep coexistence? | Restore exit 6 |
| D-C | Codegen E3 (`ref` as `*T`) and E4 (native `switch`): fix forward or revert? | Fix E4 forward, revert E3 |
| D-D | Constant wrap to i32, float fold rounding and overflow, the default width past i32 (P2-1, P2-6, P2-37), int-to-float assignment, shared module namespace: approve each fix with a packet? Constant arithmetic: the docs contradict each other (CHANGELOG:67, L52, SPEC 2.5 say wrap to i32 and round each float op in f64; SPEC 4.2.1 and L47 say exact, no wrap, reject on overflow). Today `MONTH_MS :: 30 * 24 * 60 * 60 * 1000; ms: i64 = MONTH_MS` prints `-1702967296`. | The user picks one rule. Suggested: exact arithmetic, then fit to the destination (prints 2592000000; `x: i32 = 2147483647 + 1` becomes an error instead of `-2147483648`) |
| D-E | For each shipped change with no ledger record: approved, not approved, or decide later? | Go through the table in `ledger-audit.md` |
| D-F | Require statement terminators and list commas (rejects `x := 1 2`)? | Yes, after a scan of examples and tests |
| D-G | Uninitialized variables: zero-initialize, or reject read-before-write? | Not recommended yet; needs a packet with both options |
| D-H | B0: promote all seven benchmarks (L56) or only the ones that measure something? | Promote three, rewrite four |
| D-K | Release profile: ReleaseSafe by default, or keep ReleaseFast? | ReleaseSafe until proof gaps close; ReleaseFast behind a flag |
| D-J | Stdlib: adopt the hybrid architecture and the phase A list? JSON and YAML parsers are confirmed by the user (needs a ledger entry). Then U1-U14 in `stdlib-proposal.md`. | Hybrid; answer U1-U14 before any stdlib code |
| D-I | GitHub settings: branch protection, secret scanning, push protection, read-only default token? | Turn all on |

## Appendix A: findings without a row above

Grouped by review. "R" marks reading-only items; the rest were
reproduced by the reviewer.

### A.1 Diff review, frontend/checker

- Wrong error labels: conflicting `$T` bindings print as "Generic
  parameter count mismatch" and add a third error to a call that
  already had two; an unknown union tag prints as "Struct has no such
  field".
- `semantic_validator.py:1583-1592`: the unknown-tag branch is dead in
  the pipeline, because `compile.py:435` runs the validator only if
  the checker passed. The "has no tag" check is written three more
  times in the checker (`:3082-3095`, two branches of
  `_resolve_pattern_type` from `:3584`); two look unreachable (R).
- `_union_payload_type_name` documents a `None` path "for an untyped
  test double" (`semantic_validator.py:1537`): production code shaped
  for tests (R).
- Defensive reads on trusted nodes: `isinstance(decl, ASTNode)`,
  `getattr(decl, "is_tagged", False)` (`:1492-1495`),
  `getattr(node, "where_clause", None)`,
  `getattr(entry, "where_valid", True)`,
  `getattr(existing, "overload_nodes", None)` (R).
- `_validate_where_names` (`type_checker.py:630`) has one caller and
  repeats a branch of `_merge_where_constraints` (`:588`), which also
  carries a `report` flag and a `known_names=None` mode.
  `_parse_trailing_where_clause` is a four-line wrapper (R).
- Tagged-ness is computed two ways (checker reads
  `symbol.node.is_tagged`; validator builds a name-keyed table).
  `_value_param_types_from_params` runs twice in each function path.
  `VALUE_PARAM_KINDS` sits mid-class. `_infer_generic_types` grew three
  nested closures. `GenericValueArg` is a `Type` with
  `kind = GENERIC_PARAM` stored in `type_args` (a value posing as a
  type; cause of P0-6) and has no `name`.
- Signed kinds are in `VALUE_PARAM_KINDS`, but a negative value can
  never be passed, so the lower-bound check at `:548` is unreachable.
- Checked clean: `Result(i32, string) = Result(bool, bool){...}` is
  rejected; an imported tagged union gets dot arms and exhaustiveness;
  nested generic unions match; payload bindings are immutable and do
  not clobber outer variables; reversed ranges with negative endpoints
  are rejected.
- Not reached by that reviewer: `types.py` hash/equality changes beyond
  reading; char and const-alias forms of reversed ranges.

### A.2 Diff review, backend and new tests

- `__a7_stdin_read_line`: EOF and read error both map to `ReadFailed`;
  stdout is not flushed before the read (R). The CLI rejects
  `read_line` at exit 6, so it is reachable only through the test
  helper that ignores checker errors.
- `a7/cli.py:169`: release builds use `ReleaseFast`, where `.?` is
  unchecked; CHANGELOG:40 calls the `ref` lowering "one boundary
  check" (R).
- No defect found in paren removal (16 mixed conditions match HEAD),
  IO elision (HEAD already elided the header, so E2 pins old
  behavior), or switch lowering for u8, i64, char, bool, enum.
- `test_overload_coexist.py:166-202`: two tests assert only that
  "already defined" is absent, with no exit code; the same shape exits 7.
- `test_stdlib_result.py:438-494`: `read_line` tests snapshot five
  emitted lines, then run one read through a checker bypass;
  `test_eof_leaves_buffer_zeroed` checks the buffer, not the `err`
  result (R).
- `test_codegen_emit.py`: string snapshots split across tests that
  recompile one source (`:190-208`, `:295-305`); all E4 arms have empty
  bodies (R).
- `test_generics_value_params.py:342` duplicates
  `test_where_clauses.py:344`; no test in that file reaches Zig (R).
- Examples 049/050: both compile, run, match goldens. `049:6` `label`
  is never read and `:63` hardcodes `"stapler"`; categories and grades
  are magic `i32` values, not an enum; `count: i32` holds an entry
  count; `050` has two near-identical match functions; neither
  exercises the no-else switch, payload match, or `println_ok`.

### A.3 Tooling, CLI, gates, security

- Gate: `--timeout` or `--only` as the last argument dies with
  `$2: unbound variable`.
- `bench_perf.py`: the pin's `zig` field is written but never compared (R).
- `a7 -h` lists no subparsers (subcommands dispatch on `argv[1]`).
- Per-binary runtime timeout is 2.0 s (`build_examples.py:280`,
  `verify_examples_common.py:230`); on a loaded box a slow example
  reports as a failure (R).
- `check_no_secrets.py:28-63`: no `github_pat_`, `glpat-`, `AIza`
  patterns; `.gz` and `.lock` skipped, including one tracked
  `.tar.gz`; non-UTF-8 files skipped silently (R).
- `check_docs_style.py`: inline code spans and `~~~` fences are not
  excluded; no emoji rule; unchecked banned-word hits: `docs/plan` 55,
  `docs/audits` 24, `docs/lang-safety` 2, `site/docs` 2.
- `mutation_harness.py`: no baseline run, so an already-red suite
  reports every mutant caught; `Mutant.revert` unused (R).
- `BackendConfig` has one instance. `run_cmd`, `normalize_output`,
  `first_error_text`, `find_examples` are copied between two scripts.
- Tracked: about 30 `.log` files, 4 PNGs, a PDF,
  `.interface-design/system.md`. Ignored but present: `tmp/` 5.7G,
  `build/` 659M.
- Formatters: `console_formatter.py:14` unused `Columns` import, `:100`
  unused `type_map`, `:348` bare `except:`; `json_formatter.py:115-125`
  builds `metadata` and `source_code` that are discarded, `token_count`
  counts EOF against its comment, `:185` sets `raw_text` twice;
  `markdown_formatter.py:57` labels a character count as bytes and
  `:59-61` breaks if the source contains a code fence (R).
- Checked clean: JSON valid on all modes and error paths; exit codes
  0, 2, 3, 5, 6, 7, 8 reproduced; input/doc/output alias conflicts
  rejected; missing parents created; stdin unsupported (exit 3);
  parent, absolute and symlink-escape imports rejected; no
  `shell=True`; versions agree at 0.3.0.

### A.4 Types, names, constant folding

- `FunctionType.equals` ignores `is_variadic`, `variadic_type`,
  `generic_param_order` (`types.py:743-749`); `==` does not (Python
  only; no end-to-end repro).
- Struct `equals` is not transitive: named `A` equals an anonymous
  struct with the same fields, which equals named `B`
  (`types.py:751-758`; Python only).
- Two equality relations on every type: `.equals` by name, `==`
  structural (`types.py:164-176`). Hash and `==` are consistent.
  Whether a caller picks the wrong one is unverified.
- `1e308 * 10.0 / 10.0` prints `inf`. No bitwise or shift operators in
  the exact evaluator (`exact_constants.py:132, 220`).
- Dead in `semantic_context.py`: `ContextKind`, `add_generic_param`,
  `get_generic_param`, `instantiate_generic`,
  `get_instantiated_type`, `generic_instantiations`,
  `get_loop_depth`, `get_defer_count`, `dump`; `errors` appended and
  never read; `has_break`, `has_continue`, `defer_count`, `depth`
  written and never read; `current_function` is one slot, not a stack.
- Dead in `symbol_table.py`: `update_symbol`, `lookup_type`,
  `lookup_in_scope` (ignores `self`), `is_global_scope`,
  `get_unused_symbols`, the `reuse_existing` parameter,
  `resolve_qualified_name`, `resolve_using_import`,
  `resolve_named_import` (`:399-458`); `is_used` set and never
  reported. Return values of `add_alias` and `add_named_import` are
  ignored though SPEC 10.2 cites them as a guard.
- `cast_classifier.py:42-44` copies three tables to "keep isolation"
  from a mutation nobody performs.
- `types.py:801-810, 863-869, 931-941`: extension-method dispatch for
  subclasses that occur only in `test/test_no_recursion.py`.
- Misleading docstrings: `name_resolution.py:4` ("resolves names"; it
  registers declarations), `types.py:37` ("types are immutable"),
  `exact_constants.py:1` ("Experimental" for the path every numeric
  literal takes).
- Ad-hoc node attributes `exact_constant`, `exact_f64`,
  `exact_nonfinite`, `exact_materialized`, `exact_float_bits`,
  `exact_float_error`, `exact_failed`.
- No recursion found in the nine files. `ieee_bits` at width 64
  matched `float()` on 200,000 random rationals.

### A.5 User docs and site content

- `site/docs/verification.md:15-16, 53, 59` and
  `content-verification.md:30` state "all 43 examples", "43/43" and
  "2,651 pytest cases" as current; STATUS:210 links them as live.
- `docs/README.md` does not index `bench/README.md` or
  `site/README.md`.
- Hardcoded values: `docs/RELEASE.md:60, 126` and the site release page
  say `v0.3.0`; `docs/SECURITY.md:44` dates action pinning 2026-05-08;
  `README.md:115` calls `run_all_tests.sh` the "full release-oriented
  local gate" while RELEASE.md gives that name to
  `run_release_checks.sh`; `test.sh` is tracked and documented nowhere.
- Writing rule violations: `README.md:252` call to action; `README.md:3-9`
  generic claims; emojis in `docs/ERROR_ANALYSIS.md`; STATUS:20-22
  "proves ... 1.59x faster" from five runs on one host (a later single
  run gave about 1.24x, not evidence either way); STATUS:212
  "regressions" meaning regression tests; `SECURITY.md:30-31` lists
  `fall` placement as a security limitation.
- `docs/audits/2026-09-14/website-codex-review.md:11-24` has 16
  absolute-path links.
- Site: `package.json:18` runs `python3` directly; `build.ts:45`
  special-cases the `exit-codes` alias.
- Checked clean: every script and flag the docs name exists; the
  keyword index matches the tokenizer (48); archive name matches
  `release.yml`; no registry feature is presented as available;
  intrinsics, variadics, destructuring are marked unavailable on the
  pages read; 33 of 42 site snippets pass as written.
- Proposed document layout: STATUS keeps surface, open gaps,
  priorities only; CHANGELOG user-visible lines only; README install,
  CLI, links; site status page links STATUS; move dated verification
  files and `site/docs/audits/` to `docs/audits/<date>/`; generate the
  examples table and the error catalog from source.

### A.6 Frontend (tokenizer, parser, resolver)

- A file with CR-only line endings lexes as one line, so a leading
  `//` comment swallows the file (SPEC 2.1 documents CR as whitespace;
  low).
- `import "."` loads `<entry>/mod.a7` with exit 0.
- `module_resolver.py:85-93` and SPEC 10.2.1 say parent-relative
  segments compare equal; `_is_safe_module_path` rejects every `..`
  first (R).
- `topological_sort` emits dependents first while its docstring says
  dependencies first (`module_resolver.py:431-471`; no caller) (R).
- SPEC 13.1/13.2 list grammar the parser lacks: `"fn" generic_params`,
  `generic_params?` on `struct`, `union`, fn types; `del`, `fall` and
  local type declarations are missing from 13.4 (R). `parser.py:4`
  cites SPEC section 12 for the grammar; it is 13.
- Tokens never emitted: `SEMICOLON`, `ADDRESS_OF`, `DEREFERENCE`,
  `COMMENT`. `TRUE`, `FALSE`, `NIL` are mapped in `KEYWORDS`, then
  overridden at `tokens.py:855-860`. `tokens.py:1065, 1083-1087`
  unreachable; unused imports `re`, `string`, `Union`.
- Unraised codes. Tokenizer: `OUT_OF_MEMORY`, `END_OF_FILE`,
  `FILE_EMPTY`, `BAD_TOKEN_AT_GLOBAL`, `UNKNOWN`. Semantic:
  `DUPLICATE_PARAMETER`, `DUPLICATE_VARIANT`, `INVALID_DEFER_SCOPE`,
  `MEMORY_LEAK`, `DOUBLE_FREE`, `CIRCULAR_IMPORT`, `MODULE_NOT_FOUND`,
  `UNSUPPORTED_IMPORT`, `UNKNOWN`. Type: `REQUIRES_STRUCT_TYPE`,
  `REQUIRES_FUNCTION_TYPE`, `NIL_NOT_ALLOWED`,
  `MISSING_TYPE_OR_INITIALIZER`, `INCOMPATIBLE_TYPES`, `INVALID_CAST`,
  `UNKNOWN_TYPE`, `UNKNOWN`.
- Dead: `errors.py:865-923` `create_error_handler`; `errors.py:969-977`
  `create_span_from_tokens` (clashes with the same name in
  `ast_nodes.py:542`); `errors.py:477-484` `severity` computed over
  four identical branches and never read; resolver `is_loaded`,
  `add_search_path` (would not update `resolved_search_paths`),
  `remove_search_path`, `get_search_paths`; parser
  `_is_valid_expression_statement` (1438), `self.current_token` (68),
  `if not right` (1502), `parse_function_decl_anonymous` wrapper (584).
- `ast_nodes.py:4` docstring says "visitor pattern"; there is none.
  `"__inline__"` is a magic struct name. Ad-hoc attributes `inline_type`,
  `fatal`.
- Three parser functions over 150 lines: `parse_type` 203,
  `parse_statement` 178, `parse_for_statement` 157. The type-start
  token list is written twice (531-553, 1572-1578). `errors.py` keeps
  six parallel message and advice dicts.

### A.7 Type checker

- `visit_address_of` and `visit_deref`: no `ADDRESS_OF` or `DEREF`
  producer found in the parser (R).
- The checker rewrites node kinds in place (1663, 3665). Two error
  channels: untyped `add_error` for exact-constant diagnostics,
  `add_type_error` for the rest.
- Oversized methods: `visit_call_expr` 209 lines, `visit_field_access`
  119, `visit_binary_expr` 115, `visit_var_decl` 113,
  `_resolve_type_leaf` 116.
- Lines 1045-1048 are a no-op `pass`; 1211-1213 assign the same value
  twice. The `!= NodeKind.DEREF` test at 1352 is always true.
- Not covered by that reviewer: cross-module calls (1950-2031),
  function-pointer generics, `defer`/`del` typing, `new` of generic
  types, f32 overflow at materialization.

### A.8 Test suite (first 78 files)

- `test_semantic_analysis.py:207` never reads `validator.errors`;
  `:47, :254, :284` assert only that a symbol table exists.
- `test_codegen_zig.py:1022` asserts two method names are absent;
  `SEMANTIC_KNOWN_FAIL` (`:33`) is empty and `ZIG_AST_CHECK_PASS`
  (`:161`) is unused; `TestZigAstCheck.test_ast_check` (`:177`) ignores
  the `compile_file` result.
- `test_stage_exit_codes.py:47` compares `ExitCode.PARSE == 5`.
- `test_iterative_traversal.py:34` writes to system temp via
  `tempfile.mkstemp`, not `tmp_path`.
- `test_examples_e2e.py:43` gives 51 build-and-run examples a 180 s
  timeout.
- `test_error_stage_matrix.py:234` hardcodes a `/tmp/...` path.
  `test_rejected_examples.py:83` greps a script's source text.
  `test_parser_examples.py:27-260` parses 22 examples the e2e test
  already runs.
- `norec_scan.py` (1,700 lines) is a helper imported only by
  `test_no_recursion.py`.
- Five highest-value missing tests: (1) stage-boundary check, (2) two
  consecutive `read_line` calls run as a binary, (3) a generic
  constraint violation with the constraint attached, asserting exit 6
  and the message, (4) the golden gate failing, not skipping, when
  zig is absent or not 0.16.0, (5) unit tests for `exact_constants.py`
  and `markdown_formatter.py`.
- Line lists for the rows above. T-2 (`assert isinstance(result, bool)`):
  `test_semantic_errors.py` 128, 167, 213, 225, 237, 249, 284, 307,
  319, 335, 349; `test_semantic_generics.py` 130, 218, 278, 415, 479,
  499, 514, 533, 567; `test_semantic_functions.py` 165, 181, 255, 662;
  `test_semantic_expressions.py` 265, 407, 481;
  `test_semantic_control_flow.py` 1273, 1299;
  `test_semantic_types.py` 185. Hidden wrong outcomes: `errors:213`
  expects "pointer", gets "Cannot access field on non-struct";
  `errors:284`, `errors:319`, `control_flow:1299` get a ParseError;
  `generics:218` never attaches its constraint; `generics:499` is a
  ParseError on `Some: $T`; `generics:130, :567`, `functions:662`,
  `control_flow:1273` are rejected by the checker.
- T-1 private helpers: `test_semantic_errors.py:32`, `_generics.py:37`,
  `_functions.py:32`, `_expressions.py:30`, `_types.py:33`,
  `_control_flow.py:33`, `_comprehensive.py:25`. Codegen failures in
  `test_semantic_generics.py`: 115, 165, 189, 205, 235, 430, 452, 465,
  533. Other examples: `test_semantic_comprehensive.py:310, :882`,
  `test_semantic_generics.py:415, :278`.
- T-4: `expect_error` with no message check is used at
  `test_semantic_comprehensive.py` 339, 661, 670, 726, 734 and one more.
- T-5 `ast is not None` counts: extreme_edge_cases 54 of 62,
  type_combinations 35 of 35, stress_tests 16 of 21,
  comprehensive_problems 16 of 39, advanced_edge_cases 15 of 26,
  examples 12 of 28, fuzzing 4, error_handling_improvements 3,
  missing_constructs 1. Either-outcome tests:
  `test_parser_advanced_edge_cases.py` 132, 144, 156, 181, 322, 424,
  443; `test_parser_error_handling_improvements.py` 252, 269, 284,
  493; `test_parser_stress_tests.py` 86, 267; `test_parser_fuzzing.py`
  8 sites; `test_tokenizer.py` 703, 738, 846, 857, 1098 (703 and 846
  also accept `TypeError`). `assert True` tests:
  `test_parser_integration.py` four or five near 458, 492, 527;
  `test_parser_examples.py:318`. No-assert tests:
  `test_parser_missing_constructs.py:152, :327`,
  `test_parser_error_handling_improvements.py:291`.
- T-8 cast matrix: `:169-194` 60 cases hit one branch; `:197` 144
  int-to-int cells all use literal `1`; `:229, :235` 81 cases expect
  "numeric"; `:208, :215` 50 cases. Keep the 225-cell hand-written
  table at `:139`. Ten largest in-scope files by collected tests:
  cast_safety_matrix 595, codegen_zig 173, semantic_control_flow 90,
  ast_preprocessor 69, semantic_comprehensive 65, error_stage_matrix
  63, parser_extreme_edge_cases 62, semantic_types 57, tokenizer 54,
  iterative_traversal 44.
- Counts: 2,550 collected, 87 files, 0 duplicate test names in one
  scope, 13 names shared across semantic files, 10 across parser files.

### A.9 Examples and bench

- `bench/stride_walk.a7:6` promises a gap between two phases; the
  harness times the whole binary once. `bench/README.md` omits
  `--taskset` and the trimmed median.
- `mem_cleanup` prints `result: 9999900 100`; the handoff writes
  `9999900/100` (separator only).
- No undefined behavior in the ten existing benches; all ten output
  hashes match the pins.
- Required proof guards carry no comment: `026:48, 57, 64`, `030:62`,
  `032:11`. Unneeded workarounds: `006:58`, `031:11-15`, `034:8`.
- `036:18-31` puts labels on single-level loops, where labeled and
  unlabeled forms behave the same. `047:34` `unsafe_field_ratio` is
  the safe pattern. `028_state_machine` has no transition rules.
  `045:22-24, 59-62` comments don't match their code.
- Smaller: `029:7` `ascending` returns `left > right`; `014:9` `Box`
  omits `($T)`; `016` has no header; `018:11` labels `math.abs(-5.0)`
  as `abs(-5)`; trailing commas in 045-048 and newlines elsewhere.
- A payload-less tag (`none` with no type) is a parse error, exit 5.
- Proposed adds: a tagged-union payload example with generic
  `Result`/`Option` and `where`; a two-file import example; a
  nested-loop labeled break including from a match arm; a `[]T`
  parameter example. Proposed drops or merges: 021, 023, 012, 015;
  fold 008 into 046 and 047 sections 3-5 into 044; rename 008, 013,
  017, 035; rewrite or retitle 048.

### A.10 SPEC

- Smaller block failures: L689 `cast(T, value)` exits 6; L833
  `for char in string[2..5]` uses two keywords as names; L314
  `arr: [5]i32 = 0` exits 6 (STATUS:152 says scalar fill is rejected);
  L399 `string :: struct` pseudo-definition exits 5; L1744 `length(v)`
  undefined when the module is imported.
- `import "../utils"` exits 3 (not found), not a resolver rejection.
- Contradictions: L129 vs L136 on `where`; L1910 vs L1923 on which io
  calls lower; L782 presents capture-on-unknown-name as design while
  STATUS:203 lists it as a gap; four "See STATUS Known Gaps" pointers
  (L733, L801, L2345, L2387) point at nothing; "12.1 Token Types"
  appears twice; L1030 names no file; L1339 "implemented backends".
- Stale citations: `zig.py:2074-2083` (L218), `zig.py:2047` (L605),
  `parser.py:2030-2043` (L1870), `zig.py:152-221` (L1914).
- Section 9 uses destructuring, `@vectorize`/`@parallel`/`@prefetch`,
  named arguments, and `^` as power, unmarked. L181 and L1889 use
  variadic `..` without the parsed-only caveat. Section 1.1 lists
  "Zero-cost abstractions" and "Clean C ABI compatibility" with no
  support. Header box dated 2026-05-08.
- Appendix C: column says "Minimum Limit" for maximums; exponent cap
  4,096 not enforced (`1e5000 == 1e5000` compiles).
- Confirmed correct: keyword table (48), 12.1 token list, precedence
  table, lexical limits and escapes, `/` and `%` signs, wrapping `+`,
  widening and narrowing rules, match duplicates/overlap/ranges/`fall`,
  entry-point rules, import cycles, recursion ban, all five relative
  links.

### A.11 Backend (whole file)

- `c: char = 'é'` prints the invalid byte `0xE9`.
- `_global_names` omits the preamble names `std` and `allocator`.
- `StdlibRegistry.is_io_call` has no caller in `a7/`. The abstract
  `generate(ast)` signature in `base.py` does not match the Zig one.
- Oversized methods: `_visit_function` 139 lines, `_visit_match` 108,
  `_emit_preamble` 82, `_visit_var` 75, `_visit_for` 72, `_emit_call` 72.
- Duplicates beyond those in Phase 5: `_visit_if_stmt` vs
  `_visit_else_chain`; `println_ok` format handling vs
  `_emit_io_call`; `_emit_deref` vs `_emit_implicit_deref`; mutation
  and usage collectors repeated from `ast_preprocessor.py`.
- Observed print formats with no SPEC rule: enums as `.Red`, structs
  as `.{ .x = 3 }`, `1.0e300` as 301 digits.
- Not reached: `using`/selected imports, `for ... in` over a string or
  call result, runtime shift counts at or above operand width, reading
  the inactive member of an untagged union, `$N` emission.

### A.12 Safety, validator, pipeline

- `semantic_validator.py:579-585`: the recursion group is a dict keyed
  by name, so same-name overloads collapse to the last one (R).
- Dead: `self.allocations` (47) never read; `visit_literal_expr`,
  `visit_new_expr`, `visit_fall_stmt` do nothing; `return_type = None`
  (132) unused; `ObligationKind.UNION_FIELD` and
  `ValueFact.enum_discriminant` never set or read;
  `_resolve_stdlib_call` only counts; `_infer_types` (406) returns
  early for every typed VAR; `compile_a7_project` has no callers.
- Misleading comments: `safety.py:57-60` describes one table above
  another; `safety.py:61-66` says other deferred kinds lower to
  `defer void;` but `defer x = 2` builds and prints `2`; the
  preprocessor docstring numbers passes 1-8 while the code has
  "Pass 0" and "Pass 9"; `layout.py:85, 97` use `-> (int, int)`.
- `_visit_stmt` is about 205 lines (526-731).
- Not reached: generic-function recursion bypasses; runtime evidence
  for P2-57 (blocked by codegen).

### A.13 Round 2 (full reports in `reports/`)

- CI/release (`ci-release.md`): build backend unpinned; `build` dev
  dependency unused; RELEASE.md has no `__init__`/`uv lock` bump step
  and `git push --tags` pushes every local tag; local Bun 1.4.2 vs CI
  1.3.11; no CSP on the site. The report lists eleven cheap fixes.
- Diagnostics (`diagnostics.md`): codegen errors are one line with no
  snippet; messages omit the operator or function name; the caret
  breaks on wrapped lines; `undefined identifier 'expression'` leaks.
  Catalog: `break 'nope` is a tokenizer error; `return`/`defer` at top
  level exit 5, not 6; bare `x;` gives "Undefined type". Codes not
  triggered: `return_outside_function`, `defer_outside_function`,
  `nil_not_reference_type`, `requires_pointer_type`,
  `address_of_rvalue`, `out_of_memory`.
- Modules (`modules.md`): a local or parameter named like an import
  alias is accepted (L28 only at top level); hardlinks are not covered
  by duplicate-import detection; `"./io"` loads a local `io.a7`;
  `module_h__value` as a user name collides with a module prefix.
- Site (`site.md`): `<pre>` has `aria-label` with no role; 70 code
  blocks and 24 table wrappers are tab stops; sidebar `<h2>`s precede
  the `<h1>`; Enter during the search debounce opens the previous
  query's first result (all R); the `?from=` redirect in `site.js` has
  no producer; `robots.txt` under `/a7-py/` is ignored by crawlers.
- All round-2 reviewers have finished.

### A.14 Plan and ledger review: items not in Appendix B

- Changes that do have a record (CHANGELOG Unreleased only): reversed
  constant range, unclosed `/*`, imported-file stage attribution,
  sibling calls in modules: L24 class, self-asserted. No-`main` exit 6
  and `--lib`: L54. Buffered stdout: L48. Release nonwrap: L49. Early
  return fact repair, malformed declarations, safety-fact
  invalidation, literal contexts: L35. Wrapping `+ - *`: L5, L35. Loop
  `defer` stale proof: L32. Keyword escaping, loop captures: L34.
  Float remainder fold: L33. `check`/`build`/`run`/`doctor`: L45. i32
  fold wrap, i64 widen, f64 rounding: L52 (no quoted words), L47.
  Examples 049/050 are not a language change, but L23 holds new
  examples until CRITICAL/HIGH closure and no closure record exists.
- ID families that are defined: L1-L57 and O1-O4 (`decisions.md`,
  three formats); G1-G9 (`plan/README.md:75-348`); M1-M51
  (`plan/memory.md:562+`, a file marked historical); Tracks 0-13
  (`plan/README.md:352-371`; roadmap "7a remainder" covers items track
  7a does not list); P0-P11 (`execution.md:469-481`, files only for P0
  and P0b); P-MOD, P-SAF, P-TYP (`plan/packets/`, no ledger
  disposition for P-MOD, P-SAF, P0, P0b); LNG-nn
  (`audits/2026-09-18`); SAF-nn, ZIG-n, TOK-nn
  (`audits/2026-09-16/compiler/`, no README; `execution.md:525` notes
  conflicting SAF-11); LX-Ann (`fix-program/`); Waves 0-7, 1R, 2R
  (`execution.md`); Waves A, B, C, E (one sentence in L50; A undefined);
  D.nnn (`lang-safety/08-decisions.md`, historical).
- Roadmap internals: `:81-82` "23->22 pins, ~375 lines" and "cap
  overage accepted" are worker notes and no doc defines a cap; `:139`
  cites "plan PROGRESS", which does not exist; `:144` heading says
  "dispatch queued" while `:156` says DONE; E3 and E4 say "Needs
  before/after packet" and no packet exists.
- Current vs superseded: `delivery-roadmap.md` and `decisions.md`
  current; `memory.md` historical and `memory-brainstorm.md` closed,
  both say so; `execution.md` superseded for work order but its status
  line still reads "approved"; `plan/README.md` half-superseded and
  says so only at `:38`, with a 20-row track table and defect lists
  still in it (583 lines).
- 47 directories have no README; the ones that matter: `docs/research`,
  `docs/research/language-needs`, `docs/audits/2026-09-16`,
  `docs/audits/2026-09-20-resumed-v1`, `docs/lang-safety/edge-cases`,
  `docs/plan/research/memory`, `docs/plan/audit/evidence`.
- Largest files: `research/tooling/08-agentic-debugging.md` 2,280
  lines, `lang-safety/08-decisions.md` 2,192. In plan proper:
  `memory.md` 795, `fix-program/frontend-fix-plan.md` 665,
  `backend-fix-plan.md` 600, `README.md` 583,
  `packets/P-TYP-forward-globals.md` 559, `execution.md` 542.
- `tmp/`: 3.6G in `tmp/untyped-constants-next`, 1.1G in `tmp/audit`.
- `HANDOFF-2026-10-02.md:23-24` step 4 depends on a diff "in the B0
  promotion-pack agent output", which is not on disk.
  `tmp/b-benchspec/` and `tmp/b-benchspec-staged/` hold the same 7
  file names. `HANDOFF-2026-09-20.md` has one commit and no later
  diff (frozen, as the rule requires).
- Own first pass: the handoff file and `docs/research/` are untracked;
  `.gitignore` covers `build/`, `dist/`, `*.egg-info`, `/tmp/`; 214
  commits; last commit 2026-10-02.

## Appendix B: Ledger and plan-docs audit

Embedded copy of `ledger-audit.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Ledger and plan-docs audit, 2026-10-04

Source: read-only reviewer over `docs/plan/`, `docs/research/`,
`docs/audits/`, `docs/lang-safety/`. No compiler runs. Approvals given
in chat can't be seen from disk; "None" means no record on disk.

#### Shipped or approved claims with no ledger entry or packet

| Claim | Where claimed | Record |
| --- | --- | --- |
| Generic `union(tag)` specialization | CHANGELOG:8, STATUS:93 | None |
| Conflicting `$T` exits 6 | CHANGELOG:12 | None |
| `$N` value params | CHANGELOG:16, STATUS:99 | None; research 04:78 says gate |
| Minimal `where` | CHANGELOG:21, STATUS:106 | None; research 04:79 says gate |
| Overload sets coexist | CHANGELOG:24, STATUS:110 | None; roadmap A8 lists overloading as a cut |
| Dot-arm match; bare `case tag:` exits 6 | CHANGELOG:29, STATUS:121 | None; G5 open; `plan/README.md:238-258, 410` records the bare form compiling and "needs approval" |
| `io.println_ok` / `io.read_line` | CHANGELOG:35 | None; "G5B" packet not on disk |
| Codegen E1-E4 | CHANGELOG:39, roadmap:144 | None; roadmap says "APPROVED 2026-10-03" with no quote |
| Unlabeled break/continue in match case exits 6 | CHANGELOG:52 | None; self-classified |
| Duplicate imports exit 6 | STATUS:155 | L26 direction; P-MOD approval required by decisions:255 missing (P-MOD is "draft for user decision") |
| Bare call to imported fn exits 6 | CHANGELOG:65 | L25 direction; P-MOD approval missing |
| `y :: y + 1` reads outer binding; match-arm scopes | CHANGELOG:62 | L50 orders the wave only |
| Struct generic constraints enforced | CHANGELOG:82 | None |
| Import cycles diagnosed | CHANGELOG:153 | None; decisions:257 says cycles not decided |
| Roadmap A4 numerics "QUEUED, approved" | roadmap:89 | None; `PKT-num-D/G` defined nowhere |
| Roadmap A6 "Async syntax never", B8 NEVER items, A8 "Locked cuts" | roadmap:95-123 | None except package registry; sources are research files 16, 22, 23, 25 |

#### Ledger defects

- L47 contradicts itself: `decisions.md:148-150` ("do not request this
  approval again") vs `:275-277` ("need approval before further
  compiler changes"). No supersede note.
- L52, L53, L55 have no quoted user words; L53 and L55 name no user
  action. L33-L57 carry no Locked/Open state. L36-L46 table has no date.
- `:350-362` "Pending records: L50-L53" and the G1-G9 stub are stale.
- `:325` says audit files are untracked; 301 are tracked.
- `:287` joined lines; `:154` and `:328` formatting.
- L56 links an untracked handoff file.
- Roadmap `:9` says "user approved this roadmap on 2026-09-20" above 87
  lines added 2026-10-03/04.

#### Todo lists outside the two allowed files

HANDOFF-2026-10-02 (B0 and Wave B have no roadmap row; roadmap A5 says
arena PROPOSED while L57 says go), `plan/audit/open-items.md` (live list
in a "frozen" directory), STATUS priorities (no shared IDs with the
roadmap), `execution.md:28-232, 465-491`, HANDOFF-2026-09-20:198-225,
packets P-MOD:266 and P-TYP:463, `language-needs/00-read-over.md:36-62`,
`tmp/RESUME.md`, `tmp/packets/pending-items.md`.

#### IDs defined nowhere or colliding

- Undefined: G5A, G5B, G5B-2, PKT-num-D/G, Wave A, "phases 2a/2b/2c",
  "plan PROGRESS" (roadmap:139), "KNOWN S2".
- Collisions: roadmap B1-B8 (stdlib) vs B0-B3 (memory prototypes);
  roadmap D1-D4 vs numerics D-items; E1-E4 vs Wave E; row "A7" vs the
  language name; C1 vs memory phase C1.

#### Staleness

- `plan/README.md:285` says unclosed `/*` still exits 0; STATUS says
  fixed. `:238` says payload matching doesn't exist.
- STATUS:232 and `audits/README.md:4` name `execution.md` as the
  tracker; `execution.md` says the roadmap is.
- `docs/README.md` never links `delivery-roadmap.md`.
- `lang-safety/README.md:22` says ledger L1-L22.
- Roadmap heading `:144` "dispatch queued" vs `:156` "DONE".

#### Research and evidence

- `docs/research/language-needs/`: 0 of 26 files have the
  `> **Source:**` header; file 00 covers 01-21, not 22-25, which
  roadmap A5/A6/A7/B8 rest on. Row 14b ("no v1 overloading") is about
  operator overloading only; the roadmap widened it.
- `docs/plan/research/README.md` misses 14 entries (`untyped-*`,
  `zig-free-features.md`).
- 38 links use absolute `/home/cx89/...` paths (five files).
- 19 cited `tmp/` paths no longer exist. `tmp/` is ignored, so every
  doc citation into it is dead on a clean checkout.
- Three audit trees: `docs/audits/`, `docs/plan/audit/`,
  `site/docs/audits/`. Byte-identical evidence pairs in
  `untyped-candidate-*` and `glm-probes/`.
- Sizes: `docs/plan` 44,981 md lines (13M), `docs/audits` 18,950
  (19M), `docs/lang-safety` 18,101. 55 md files over 500 lines.
  `tmp/` 5.7G; 42 of 56 top-level dirs don't match `<topic>-YYYY-MM-DD`.

#### Proposed layout

1. `docs/plan/` keeps four live files: `decisions.md`,
   `delivery-roadmap.md` (only todo list), short `README.md`, `ids.md`.
2. One ledger row format: ID, date, state, quoted words, packet link.
3. Every packet shown to the user is a file in `plan/packets/`;
   "APPROVED" needs an L-number.
4. `plan/archive/` takes `execution.md`, `memory.md`,
   `memory-brainstorm.md`, `fix-program/`, handoffs.
5. One research root (`plan/research/`); move `language-needs/` in.
6. One audit root (`docs/audits/<date>/`); fold `plan/audit/` in.
7. Docs cite `tmp/` only for disposable scratch.
8. `docs/README.md` and STATUS link the roadmap as the tracker.

## Appendix C: CI, release, packaging, guidance (full report)

Embedded copy of `reports/ci-release.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### CI, release, packaging, supply chain, agent guidance

Audit date 2026-10-04. Read-only. No pytest, build, or install was run.
`gh` was authenticated as `code5717`; GitHub facts come from `gh api`.

Labels: VERIFIED = read in a file or returned by a command in this
session. UNVERIFIED = inference, or a cause I could not observe.

Items already in PLAN.md are not repeated (gate arg parsing, ci.yml
re-listing checks, Zig version in four places, secrets pattern gaps,
bench host pin, `.gitignore` gaps, 42 MB tracked, P3-6).

#### State of the evidence

- Last CI run: `0294071`, 2026-09-20, success, 13m35s. HEAD is `c8face6`
  with 8 unpushed commits and a dirty tree. CI says nothing about HEAD.
  VERIFIED (`git log origin/master..HEAD`, `gh run list`).
- `dist/` inspected at mtime 2026-10-04 01:56 (+0300). The running gate
  rebuilt it at 14:36 during this audit. Contents below describe the
  01:56 build.
- `a7_py.egg-info/` mtime 14:11, `build/debug` and `build/release` 14:25,
  `build/bench` 14:34. All produced by the running gate, not stale.
- Last 100 CI runs: 84 success, 13 failure, 3 cancelled. All 13
  failures fall on 2026-05-12 and 05-13 (site toolchain switch and its
  Dependabot PRs). None since.

#### Findings, ranked

##### 1. Claude review workflow passes an input the pinned action does not define. VERIFIED

`.github/workflows/claude-code-review.yml:55` passes `direct_prompt`.
The pinned SHA `d5726de` is tag `v1.0.148`. Its `action.yml` has
`prompt`, no `direct_prompt` (`grep -c direct_prompt` = 0). GitHub
warns on unknown inputs and continues. The review prompt, including the
"treat PR content as untrusted" guard at lines 56-60, is dropped.

Run history for this workflow, last 100 runs: 31 failure (2026-05-08 to
06-12), 17 skipped, 0 success. Logs return HTTP 410, so the failure
cause is UNVERIFIED. The secret `CLAUDE_CODE_OAUTH_TOKEN` dates from
2025-08-03; an expired token is one possible cause (inference).

Stale comments in both claude workflows: "`@beta` resolved on
2026-05-08" sits on a v1.0.148 SHA (`claude.yml:50`,
`claude-code-review.yml:46`); "defaults to Claude Sonnet 4"
(`claude.yml:59`); commented `model`, `allowed_tools`,
`custom_instructions`, `claude_env` inputs do not exist in v1.

##### 2. Default gate timeout is shorter than the local pytest run. VERIFIED locally, UNVERIFIED on runners

`run_all_tests.sh:20` defaults to 1200 s per check. PLAN.md records
pytest at 27m23s (1643 s) under `--timeout 2400`. A bare
`./run_all_tests.sh` on this host fails pytest with TIMEOUT.

`run_release_checks.sh:10` calls `./run_all_tests.sh` with no
arguments, and line 8 forwards `"$@"` only to
`verify_release_version.py`, whose argparse rejects `--timeout`. The
only way to raise the bound for a release check is the
`A7_CHECK_TIMEOUT` env var. `docs/RELEASE.md` does not say so.

`release.yml:60` uses the same default. `ci.yml:50` runs pytest with no
cap. The two paths diverge. CI pytest took 78 s on 09-20; test
functions grew from 1151 (`origin/master`) to 1594 (working tree), so
runner time for the current suite is unknown.

##### 3. Repository settings leave master, tags, and tokens unguarded. VERIFIED

- `branches/master/protection`: 404 "Branch not protected". Rulesets: `[]`.
  Force-push to master and tag deletion or re-pointing are possible.
  No required status check gates merge or deploy.
- `actions/permissions/workflow`: `default_workflow_permissions: write`.
  Every current workflow declares `permissions`, so the effect today is
  nil; a new workflow without the block gets a write token.
- `actions/permissions`: `allowed_actions: all`,
  `sha_pinning_required: false`. The repo pins by SHA by convention only.
- `security_and_analysis`: secret scanning, push protection, and
  Dependabot security updates all `disabled` on a public repo.
  `vulnerability-alerts` returns 404 (off).
- Environment `pypi` exists with a required reviewer. No workflow
  references it. RELEASE.md:157 says no registry publishing.

##### 4. The release publish path has never run. VERIFIED

`git tag -l` is empty. `gh release list` is empty. `release.yml` has
five runs, all `workflow_dispatch` on 2026-05-08. The
`create-github-release` job (`release.yml:130-170`) has never executed.

`docs/CHANGELOG.md:199` has `## 0.3.0`, `pyproject.toml:3` is `0.3.0`,
and lines 6-198 are `Unreleased`. `verify_release_version.py:22-26`
checks only tag == `v<pyproject version>` and that a `## <version>`
heading exists. Tagging `v0.3.0` today passes and ships 190 lines of
Unreleased work under a heading that does not describe it. The script
does not check: Unreleased empty, version greater than the last tag,
tag commit reachable from master, `a7/__init__.py:9`.

With no tag and no `GITHUB_REF`, the script prints "untagged
qualification" and exits 0 (`:20-21, :43`). That is documented, but a
local `./run_release_checks.sh` ends with "Release checks passed"
without any identity check.

##### 5. release.yml builds and attests from any ref. VERIFIED by reading

- `release.yml:7` allows `workflow_dispatch` on any branch. The
  `build-release` job holds `id-token: write` and `attestations: write`
  (`:27-28`) and runs `actions/attest` (`:109-117`) unconditionally.
  Attestations get issued for artifacts built from any branch.
- `docs/RELEASE.md:140-143` verifies with `gh attestation verify
  --repo` only. That accepts a branch-built artifact. Add
  `--source-ref refs/tags/vX` or `--signer-workflow`.
- Tag trigger `v*` (`:6`) has no check that the tag commit is on master.
- `create-github-release` checks out the tag and runs
  `scripts/verify_release_manifest.py` under `contents: write`
  (`:135-158`) with default `persist-credentials`.
- The draft release has no body, no `generate_release_notes`, and no
  changelog extract (`:162-170`). The maintainer writes notes by hand.
- Upload artifacts expire after 7 days (`:71, :128`). A draft left
  longer can not be rebuilt from the same run.
- No `timeout-minutes` on any job in any workflow (default 360).
- Artifact names match RELEASE.md and AGENTS.md:209-211.

##### 6. deploy-docs grants deploy rights to the build job and skips CI. VERIFIED

- `deploy-docs.yml:8-11` sets `pages: write` and `id-token: write` at
  workflow level. The `build` job holds them while running
  `bun install` and third-party build code. Move them to `deploy`.
- Triggers are `push` to master/main and `workflow_dispatch`. A PR can
  not trigger it. Environment `github-pages` allows only `master`.
- It does not wait for CI. A push that fails pytest still deploys.
- It runs `python3 scripts/check_docs_style.py` (`:38`) on the runner's
  system Python with no `setup-python`; ci.yml uses 3.13 through uv.
- It re-lists `bun run check` steps (`:44-70`) and omits `bun audit`
  and the secrets check. Same root as the known ci.yml item.
- `cancel-in-progress: true` (`:15`) can cancel a deploy mid-flight.

##### 7. sdist ships untracked tests that can not run; dist reflected the dirty tree. VERIFIED (01:56 build)

- sdist holds 87 `test/test_*.py`. Git tracks 78. The 9 untracked test
  files shipped.
- sdist has no `test/conftest.py`, `test/fixtures/`,
  `test/norec_scan.py`, or `examples/`. The shipped tests can not run.
  There is no `MANIFEST.in`; setuptools picks up `test/test*.py` by
  default. Either exclude tests or ship what they need.
- Wheel `a7/` equals the working tree (`diff -rq` rc 0), which has 8
  modified `a7/` files against HEAD. A local `dist/` matches no commit.
- Wheel content is correct otherwise: 33 modules including
  `a7/passes/safety.py` and `a7/layout.py`, LICENSE, entry point. No
  tests, docs, site, or tmp. `a7/` has no non-Python files, so no
  package data is needed.
- `verify_wheel_install.py --skip-build` (`:248`) accepts whatever one
  wheel sits in `dist/`. It does not compare the wheel to the source
  tree or to `git ls-files a7`. In the gate, "Package Build" runs first;
  with `--skip build` or `--only wheel` a stale wheel passes.
- `verify_sdist` (`:205-229`) builds and smokes a wheel from the sdist
  but never inspects sdist contents.

##### 8. pyproject metadata and pins. VERIFIED

- No `license`, `authors`, `classifiers`, `urls`, or `keywords`
  (`pyproject.toml:1-9`). PKG-INFO has `License-File` only, no
  `License-Expression`. LICENSE is MIT, "Copyright (c) 2026 Code5717".
- `requires-python = ">=3.13"` is open. `a7/cli.py:98` qualifies only
  3.13 on Linux x86_64; `a7 doctor` exits 2 elsewhere. CI tests only
  3.13 on `ubuntu-latest`. Host Python is 3.14.7. No matrix.
- `rich>=15.0.0` has no upper bound. Tests run on locked 15.0.0. The
  wheel smoke runs `pip install <wheel>` (`verify_wheel_install.py:94`),
  which pulls the newest rich from PyPI, unhashed.
- `[build-system] requires = ["setuptools>=84", "wheel"]` is unpinned
  and not covered by `uv.lock`. Release wheels are built with whatever
  setuptools is newest (84.0.0 in the inspected wheel). `wheel` is not
  needed by current setuptools.
- Dev dependency `build>=1.6.1` is unused; every path uses `uv build`.
- Version lives in `pyproject.toml:3`, `a7/__init__.py:9`, and
  `uv.lock:7`. RELEASE.md:120 names only pyproject. A bump without
  `uv lock` fails `--locked`; a bump without `__init__` fails the wheel
  smoke (`verify_wheel_install.py:109`). Both fail loudly, late.
- `uv.lock` matches pyproject: `rich>=15.0.0`, dev `build`, `pytest`;
  12 packages. `uv tree --locked` resolves clean.
- `main.py:1` shebang `#!/usr/bin/env uv run python` passes three words
  to `env` and fails on Linux without `-S`. The file is not executable,
  so nothing hits it today.

##### 9. ci.yml gaps not already listed. VERIFIED

- `ci.yml:50` runs pytest with `--tb=no -q`. A CI failure shows test
  names only. The gate uses `--tb=short`.
- No caching for uv, Zig, or bun. Each run downloads Zig from
  `ziglang.org` (checksum verified, `:39-40`). "Build release
  artifacts" took 10m35s of the 13m35s run.
- `uv==0.12.15` (`:35`), `pip-audit==2.10.0`, `bandit==1.9.4` are
  version pins without hashes. Host uv is 0.12.17.
- Docs job runs `uv run` without `--locked` (`:94, :97`).
- Triggers list `main` (`:6`), which does not exist.
- No `pull_request_target` anywhere. No `${{ github.event.* }}` inside
  any `run:` block. No script-injection path found.
- All 11 action references are full SHAs that resolve to release tags
  (checkout v6.0.3, setup-python v6.2.0, setup-bun v2.2.0,
  upload-artifact v7.0.1, download-artifact v8.0.1, attest v4.1.0,
  action-gh-release v3.0.0, claude-code-action v1.0.148,
  configure-pages v6.0.0, upload-pages-artifact v5.0.0, deploy-pages
  v5.0.0). Only setup-bun carries a `# vX` comment.

##### 10. claude.yml scope. VERIFIED by reading

- Author gate is present on all four events: OWNER, MEMBER,
  COLLABORATOR (`claude.yml:22-34`). Fork authors can not trigger it.
- Permissions are read-only plus `id-token: write` (`:36-41`). The
  action swaps the OIDC token for an app token, so real write scope is
  set by the GitHub App install, not this file. UNVERIFIED what the app
  can write.
- No `claude_args` tool allowlist is set.
- Zero non-skipped runs in the last 100. The workflow is untested in
  its current form.
- `claude-code-review.yml:23` restricts to same-repo PRs, so the secret
  is not exposed to forks.

##### 11. Seven Dependabot PRs open since June and July. VERIFIED

PRs 24, 27, 29, 33, 34, 35, 36: checkout 7.0.0, action-gh-release
3.0.1, setup-python 6.3.0, claude-code-action 1.0.170, attest 4.1.1,
tailwindcss 4.3.3 (two). `dependabot.yml:8` uses ecosystem `pip`; the
project locks with `uv.lock`. Whether Dependabot updates `uv.lock` here
is UNVERIFIED; no pip PR is open, and weekly pip runs succeed.

##### 12. Release doc gaps for a first-time maintainer. VERIFIED by reading docs/RELEASE.md

- No rollback section. Nothing on deleting a bad tag, deleting a draft,
  or shipping a fix release (grep for rollback, yank, revert: no hits).
- `git push origin master --tags` (`:127`) pushes every local tag.
- No step for `a7/__init__.py` or `uv lock` when bumping the version.
- No post-release step (open a new Unreleased, bump to next dev version).
- Does not say how to publish the draft, who may, or what the release
  notes should contain.
- Does not state gate duration or the `A7_CHECK_TIMEOUT` need (item 2).
- "Bun 1.3+" (`:20`) vs CI pin 1.3.11 vs host 1.4.2 vs
  `@types/bun` 1.4.2. "Python 3.13+" vs the 3.13-only qualification.
- Says a release "should contain" debug binaries "if needed" (`:10`);
  the workflow ships release binaries only.
- Manual and unverifiable: changelog move (step 1), attestation check
  before publishing the draft (`:135-144`), the publish click itself.

##### 13. Agent guidance. VERIFIED by reading

Contradictions:
- AGENTS.md:213 says "no recursion anywhere in `a7/`". AGENTS.md:33-44
  says the parser is recursive descent and an allowlist of recursive
  groups exists. README.md:178 matches the second statement.
- AGENTS.md:19 says the file holds "only behavior rules". Lines 37-45
  (2026-09-17 census, current-state paragraph), 70-72 (tmpfs incident),
  and 95-98 (site entry points, repeated from lines 5-7) are narrative.
- CLAUDE.md:5-6 says AGENTS.md is canonical and CLAUDE.md holds
  Claude-only deltas. "Docs Accuracy" (CLAUDE.md:36-49) and "Out of
  Scope" (`:51-56`) are project rules, not Claude-specific. Other
  agents never see them.
- AGENTS.md A5 (`:177-179`) bans broad allows. Local
  `.claude/settings.local.json` allows `Bash(python3 -)` and
  `Read(/tmp/opencode/**)`. The file is ignored and local; low severity.
- AGENTS.md:209-211 puts a release-archive naming rule under "A7 Source
  Rules".
- AGENTS.md:86-89 lists the gate steps without bench. Same root as P3-6.

Stale or duplicated:
- `.interface-design/system.md` is still tracked. `docs/design-system.md:3`
  says it moved on 2026-10-02. The two differ by 4 diff lines.
- `test.sh` has no reference in any doc, workflow, or script.
- AGENTS.md:62-67 says "default 1200s per check" without noting that
  pytest alone exceeds it on this host.
- CLAUDE.md mode list and exit codes match `a7/compile.py:45-70`.
  CLAUDE.md does not mention the `check`, `build`, `run`, `doctor`
  subcommands (`a7/cli.py:191`).

Missing for an agent:
- How to get Zig 0.16.0 (README.md:22 links the download page; neither
  agent file mentions it; the host uses `mise`).
- Gate wall time and the timeout to pass.
- That `run_all_tests.sh` deletes and rebuilds `dist/`
  (`run_all_tests.sh:159`), so two gates at once collide.
- No `.agents/`, `.hermes/`, `.opencode/`, `opencode.json`,
  `.cursor*`, or `.github/copilot-instructions.md` exist.

Checkable by machine but not checked:
- A1 word list is enforced. A3 "no emojis" is not (PLAN P3-23 found 15
  lines in SPEC).
- "never add loose top-level `tmp/` files" (AGENTS.md:17): 12 exist.
- Three-way version agreement (item 8).
- CHANGELOG `Unreleased` touched when `a7/` changes.

##### 14. Runtime dependencies. VERIFIED by grep

| Package | Declared | Used in | Why |
| --- | --- | --- | --- |
| rich | yes, `>=15.0.0` | `a7/errors.py:9-14`, `a7/formatters/console_formatter.py:8-15`, `a7/compile.py:20`, `a7/parser.py` | console diagnostics, tables, syntax panels |
| markdown-it-py, mdurl, pygments | transitive of rich | not imported by `a7/` | |

Every other import in `a7/` is stdlib. No undeclared import. No
declared-but-unused runtime dependency. No dev dependency in the
runtime set. Licenses: rich MIT, markdown-it-py MIT, mdurl MIT,
pygments BSD-2-Clause; all compatible with MIT (from memory, not
checked against package metadata).

rich is imported at module top in `errors.py` and `compile.py`, so
`--format json` and library use still require it.

##### 15. site/ supply chain. VERIFIED

- 3 runtime and 5 dev dependencies; 104 lock entries; 34 top-level
  directories in `node_modules`.
- Caret ranges: `@tailwindcss/cli ^4.3.0`, `tailwindcss ^4.3.0`
  (`package.json:21, 24`). The other six are exact. The lockfile pins
  all with integrity hashes; CI uses `--frozen-lockfile`.
- `@parcel/watcher` declares an install script. `package.json` has no
  `trustedDependencies`. Bun skips untrusted lifecycle scripts by
  default (inference; not run).
- No network fetch at build time in `site/scripts/*.ts`. The only
  `fetch` calls are the local preview server and a same-origin
  `search.json` load (`site/src/site.js:162`).
- Built HTML (`site/dist`, mtime 2026-10-01 18:00): no external script,
  stylesheet, or image. Fonts are self-hosted. 23 pages each carry one
  inline `<script>` and one `site.js`. No Content-Security-Policy meta.
- `check:coverage` shells to `python3` (`package.json:18`), stdlib only.

##### 16. Repo hygiene. VERIFIED

- LICENSE is MIT. No source file carries an SPDX or copyright header.
- Absent: CONTRIBUTING, CODEOWNERS, issue templates, PR template,
  CODE_OF_CONDUCT, `.editorconfig`, pre-commit config.
  `docs/SECURITY.md` exists, which GitHub recognizes.
- Default branch is `master`. Workflows also list `main`.
- 214 commits. Last 60 subjects: imperative sentence case, 0
  conventional-commit prefixes, 3 over 72 characters, 2 with a trailing
  period. Recent subjects are batch labels ("Waves C+E, LNG-16 --lib,
  parser alias restore, bench staging", "Checkpoint: Wave A ...").
  Two author names for one person (Airbus5717 47, code5717 10).
- History pack is 12.84 MiB. Largest blob 4.86 MB
  (`docs/audits/2026-09-20-v1-foundations/glm-probes/helpers-cand.json`),
  then `site/public/a7-terminal-hero.png` 1.89 MB and
  `site/docs/audits/glm-5.3-flash-events.jsonl` 1.26 MB. Twelve more
  JSON result files between 0.43 and 0.85 MB.
- Secret pattern scan over all history, added lines, lockfiles
  excluded: 0 hits for AWS key, GitHub PAT (two forms), `sk-ant-`,
  `sk-` 40+, Slack token, PEM private key, Google API key. No `.env`,
  `.pem`, `.key`, `.npmrc`, or `.pypirc` was ever tracked.

#### Cheapest high-value fixes

1. Settings only: enable secret scanning and push protection; set
   default workflow permissions to read; add a ruleset on `master` (no
   force-push, require CI) and on `v*` tags (no delete, no update).
2. `claude-code-review.yml:55`: rename `direct_prompt` to `prompt`, or
   delete the workflow. Then trigger one run and read the log.
3. `deploy-docs.yml`: move `pages: write` and `id-token: write` to the
   `deploy` job.
4. `release.yml`: gate the attest step on
   `startsWith(github.ref, 'refs/tags/v')`; add `timeout-minutes`.
5. `verify_release_version.py`: also compare `a7/__init__.py`, and
   fail a tagged run when `## Unreleased` has content.
6. `run_release_checks.sh`: pass a timeout to the gate, or document
   `A7_CHECK_TIMEOUT` in RELEASE.md and AGENTS.md with the measured time.
7. `pyproject.toml`: add `license = "MIT"`, exclude `test*` from the
   sdist (or ship conftest and fixtures), drop `build` and `wheel`.
8. `ci.yml:50`: `--tb=short`.
9. Move "Docs Accuracy" and "Out of Scope" from CLAUDE.md to AGENTS.md.
   Fix AGENTS.md:213. `git rm .interface-design/system.md test.sh`.
10. RELEASE.md: add rollback, the three version locations, and
    `--source-ref` on `gh attestation verify`.
11. Merge or close the seven Dependabot PRs.

#### Not covered

- Root cause of the 31 Claude review failures (logs expired, HTTP 410).
- Runner time for the current 1594-test suite; whether release.yml
  hits the 1200 s bound.
- Whether Dependabot's `pip` ecosystem updates `uv.lock`.
- What the Claude GitHub App install may write.
- Whether bun skips the `@parcel/watcher` install script (not run).
- Contents of the dist rebuilt at 14:36 by the running gate.
- Dependency licenses against package metadata.
- `scripts/generate_release_manifest.py`, `verify_release_manifest.py`,
  `verify_archive_contents.py`: skimmed for structure only. `verify_archive_contents.py:92-94` rejects an empty requirement set
  and `:27-56` rejects unsafe members; the other two were not traced.
- `scripts/mutation_harness.py`, `site/scripts/*.test.ts`.

## Appendix D: Diagnostics (full report)

Embedded copy of `reports/diagnostics.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Diagnostics audit, 2026-10-04

Scope: what the user reads when a program is rejected. Accept/reject
decisions are out of scope. Items already in `PLAN.md` are cited by ID only.

Evidence: 219 probe programs under the session scratchpad `diag/`
(`c/` per-code, `b/` beginner and extra, `m/` multi-file, `x/` catalog
and proof-shape probes). Each ran through `a7 --mode pipeline`,
`a7 check`, and `a7 --mode pipeline --format json` with `NO_COLOR=1
COLUMNS=100`. Raw results: `diag/out/c.json`, `diag/out/b.json`,
`diag/out/*.txt`. All output below is copied from those runs.

Limit on the method: JSON carries no error code (finding F4), so "code X
was triggered" is inferred from the headline text in `a7/errors.py`.

#### Ranked findings

Order by user impact: F2, F3, F1, F6, F5, F4, F8, F7, F9, F10, F11, F12.
The F numbers are labels, kept stable for citation.

##### F1. Human output never names the file

`--mode pipeline` and the default `compile` mode print `[line N: col M]` and a snippet.
No file name appears anywhere. With two modules the reader can not tell
which file an error is in.

Program: `m/two/main.a7` imports `helper.a7`; one mistake in each.

```
Error 1/3:
error: Undefined type (Identifier 'factor') [line 2: col 13]
   1 ┃ pub twice :: fn(x: i32) i32 {
   2 ┃     ret x * factor
...
Error 2/3:
error: Undefined type (Identifier 'oops') [line 5: col 34]
   4 ┃ main :: fn() {
   5 ┃     io.println("{}", h.twice(2), oops)
```

The snippet is from the right file in both cases. `a7 check` does name
it (`helper.a7:2:13: ...`), basename only. JSON `details[].file` holds
the full path. Fix: print `helper.a7:2:13` in the human header, relative
to the working directory, the way `check` does.

##### F2. An undefined name is reported as "Undefined type", with a hint about importing a module

Every undefined variable or function takes this path. It is the most
common beginner error.

```a7
main :: fn() {
    total := 10
    io.println("{}", totl)
}
```
```
error: Undefined type (Identifier 'totl') [line 5: col 22]
hint: Fix the spelling or import the module that defines the type
```

Same headline for a bare `x` statement, `count = 0` on an undeclared
name, `print("hi")`, `io.println` with no import, and a bare `println`.
`SemanticErrorType.UNDEFINED_IDENTIFIER` exists with the right hint
("Fix the spelling or declare the name before this line") but is used
only at `type_checker.py:1983` and `:3673`.

Suggested: `Undefined name 'totl'` with hint `Fix the spelling or
declare it first with ':='`. For a call to `print`/`println`:
`'println' is not defined; import "std/io" and call io.println`.

##### F3. Safety-proof errors do not say what proof the compiler accepts

Index, divisor and slice errors print no hint at all. The message
repeats itself and names no variable.

```a7
avg :: fn(sum: i32, n: i32) i32 {
    ret sum / n
}
```
```
error: Divisor not proven non-zero (division/modulo divisor must be non-zero: divisor may be zero)
[line 4: col 9]
```
```
error: Index not proven in bounds (index must satisfy 0 <= index < len: index bounds are not proven)
error: Slice bounds not proven (slice must satisfy 0 <= start <= end <= len: slice bounds are not proven)
error: Reference not proven non-nil (reference must be proven non-nil before field access through it: reference may be nil)
hint: Reference use requires a proven non-nil reference
```

Shapes the compiler accepted in probes (`x/`): `if n != 0 { ... sum / n }`,
`if n > 0 { ... }`, `if n == 0 { ret 0 }` before the division,
`if i < 5 { ... xs[i] }`, `if p != nil { ... p.v }`,
`if a >= 0 and a <= 127 { cast(i8, a) }`. None of these appear in any
message. Shapes rejected with the same text and no extra note:
`if s.d != 0 { 10 / s.d }` (field divisor), `a / 0` (says "may be zero"
for a literal zero), `a[5]` on `[3]i32` (says "not proven" for an index
that is known to be out of range).

The nil case hits the first thing a newcomer writes:

```a7
n := new Node
n.v = 3          // error: Reference not proven non-nil
```

Suggested wording:

- `Divisor 'n' may be zero. Guard it: 'if n != 0 { ... }' or return early with 'if n == 0 { ret ... }'.`
- `Divisor is the constant 0.`
- `Index 'i' is not proven below the length 5. Guard it: 'if i < 5 { ... }', or loop with 'while i < 5'.`
- `Index 5 is out of range for '[3]i32'.`
- `'n' may be nil. Check first: 'if n != nil { ... }'.`
- For a field divisor: add `copy the field to a local first; proofs track locals only` (the rule is stated in `examples/047_safety_obligations.a7:27-30` but in no diagnostic).

Cause of the missing hint: `a7/passes/safety.py:921, 928, 941` create
the divisor, index and slice obligations with `diagnostic_code=None`.
`_error` (`:296-312`) then builds a bare `TypeCheckError` with no
`error_type`, so the formatter has no advice to look up.

The most natural index guard fails with an unrelated message
(`x/idx_guard_len`; the accept side is P3-19):

```a7
if i < xs.len {      // error: Cannot access field on non-struct type: got '[5]i32'
```

##### F4. JSON errors carry no code, no hint, and leak Python class names

Observed envelope, identical key set at every stage:
`error = {category, message, details[], span, exception_type}`;
`details[] = {type, message, file, span?}`;
`span = {start_line, start_column, end_line, end_column, length}`.
Lines and columns are 1-based at tokenize, parse and semantic stages
(checked against source text for 150+ spans). Multiple errors arrive as
a list in `details`. `error.span` is a copy of `details[0].span`.

Defects:

| # | Defect | Evidence |
| --- | --- | --- |
| a | No machine code. `undefined_type`, `type_mismatch`, ... never appear. A tool must match English text. | every probe |
| b | `details[].type` is the Python class: `TypeCheckError`, `SemanticError`, `ParseError`, `TokenizerError`, `ImportError`, `CodegenError`, `CompilerError` (missing input file), `ValueError` (`--backend nope`). | `x/nonexistent.a7`, backend probe |
| c | Hint text is absent. `expected_type`/`got_type` exist on `TypeCheckError` and are not emitted. | `compile.py:1095-1110` |
| d | `details[].message` embeds `basename:line:col: ` in front of the text, duplicating `file` and `span`. Not present when there is no span. | every probe |
| e | `error.message` is a count at the semantic stage (`Semantic analysis failed with 1 error(s)`) and the first diagnostic at every other stage. | `c/sf_divisor` vs `c/pa_missing_brace` |
| f | Codegen errors have `span: null` and no `span` key in the detail, while the message text starts `3:19:`. `exception_type` is set only here and for internal errors; `null` elsewhere. | `c/cg_inline_generic` |
| g | EOF parse error: `length: 0`, `end_column == start_column`, line is one past the last source line. | `c/pa_missing_brace` |
| h | `site/public/docs/compiler.md` documents only "category, message, details, span, and exception type". The fields of `details[]` and `span`, the 1-based rule, and the optional `span` key are documented only in `docs/ERROR_CATALOG.md`. | `compiler.md:119` |
| i | Module-not-found is `category: "io"`, exit 3, though it is a source error at an `import` line. | `c/sem_module_not_found` |
| j | `check --format json` reports `mode: "pipeline"`. | `x/cat_del1` |
| k | Internal error (exit 8, 400-term `x + x + ...`, P2-29): `details: []`, `span: null`, `message: "maximum recursion depth exceeded"`, `exception_type: "RecursionError"`. The key set holds, but `details` is empty, so a consumer that reads only `details` sees nothing. No traceback leaks. Human: `Unexpected error: maximum recursion depth exceeded`. | `x/deep.a7` |

Suggested detail shape: `{code, stage, message, hint, file, span, expected, got}`
with `message` free of the location prefix.

##### F5. `a7 check` drops the snippet and the hint

```
Semantic analysis failed with 1 error(s)
t1.a7:5:22: Undefined type (Identifier 'y')
```

`check` is the first command in `README.md:42` and
`site/public/docs/start.md:53`. It shows less than the
legacy pipeline mode: no source line, no caret, no hint. It prints the
basename only, so two modules named `util.a7` in different directories
are indistinguishable. (Non-semantic failures print twice: P2-13.)

##### F6. Parse errors: no hints, token-kind names, and misleading text for common mistakes

`ParseError` has no code and no advice table, so no parse error ever
prints a hint.

| Program line | Output | Problem |
| --- | --- | --- |
| `fn add(a: i32, b: i32) i32 {` | `Function declarations must have names` at `fn` | It has a name. Should say: write `add :: fn(...)`. |
| `return x * 2` | `Unexpected identifier after 'return'; missing operator?` at `x` | `return` is treated as a variable. Should say: the keyword is `ret`. |
| `var x: i32 = 1` | `Unexpected identifier after 'var'; missing operator?` | Same. Should say: declare with `x: i32 = 1` or `x := 1`. |
| `} elif x < 0 {` | `Unexpected identifier after 'elif'; missing operator?` | Should say: use `else if`. |
| `if a && b {` | `Expected expression` at the second `&` | Should say: use `and`. |
| `if a \|\| b {` | `Expected expression` at the second `\|` | Should say: use `or`. |
| `i++` | `Expected expression` at the second `+` | Should say: use `i += 1`. |
| `p := &x` | `Expected expression` | Should say: there is no address-of; pass to a `ref` parameter. |
| `b := f64(a)` | `Expected expression` at `f64` | Should say: use `cast(f64, a)`. |
| `let x = 1` | `Expected expression` at `let` | Should say: use `x := 1`. |
| `else {` on its own line | `Expected expression` at `else` | Should say: put `else` on the line of the closing `}`. |
| `for (i := 0; ...) {` | `Expected identifier or '{' after 'for' keyword` at `(` | Should say: drop the parentheses. |
| `for i in 0..3 {` | `Expected LEFT_BRACE, got DOT_DOT` | Token kinds leaked. Should say: range loops are not supported; use `for i := 0; i < 3; i += 1`. |
| `struct P {` | `Expected declaration (constant, variable, or function)` | Should say: write `P :: struct {`. |
| `f :: fn() -> i32 {` | `Expected function body after function signature` at `-` | Should say: no arrow; write `fn() i32`. |
| `x := 1 @ 2` | `Expected LEFT_PAREN, got INTEGER_LITERAL` | Token kinds leaked. |
| missing `}` | `Expected RIGHT_BRACE, got EOF [line 10: col 1]` | Token kinds leaked. Points past the end of file; snippet has no caret; does not name the `{` at line 5 that was never closed. |
| `io.println('hello')` | `The char is not closed` | P2-26. A newcomer needs: strings use double quotes. |
| `a, b := 1, 2` | `Expected expression` at `,` | CLAUDE.md lists multiple-declaration syntax as parsed-only. This spelling is rejected by the parser with no pointer to a supported form. |

Suggested wording for the kind names: `Expected '}' but reached the end
of the file; the '{' on line 5 is not closed`.

A parse error inside an imported module prints no snippet at all
(`m/par`): `error: Expected expression after '*' operator [line 9: col 13]`
and nothing else. Tokenizer and semantic errors in the same module do
print the snippet.

##### F7. Codegen errors use a different, poorer format

Programs that pass all semantic passes and fail in the backend print one
line, no snippet, no hint, backend vocabulary:

```
✗ 3:19: Zig backend: generic type requires an explicit generic environment
✗ 6:5: Zig backend: array binary initializer requires a known array type
✗ 4:10: Zig backend: io.print/io.println cannot be used as expression values
```

Programs: `identity :: fn(x: $T) $T { ret x }`; `c := a + b` on two
`[2]i32`; `a := io.println("x")`. The first is the form SPEC 7.1 shows
(P3-13). Suggested for it: `Generic parameter '$T' must be declared on
the function name: 'identity($T) :: fn(x: $T) $T'`.

##### F8. Headline or hint belongs to a different mistake

The headline comes from the enum code, the real message sits in
parentheses, and the hint is for the code. 15 cases found:

| Trigger | Output | Hint printed |
| --- | --- | --- |
| `io.printn("x")` | `Struct has no such field (Stdlib module 'std/io' has no function 'printn')` | Fix the field spelling or add the field to the struct |
| `C.Blue` on an enum | `Struct has no such field (Enum 'C' has no variant 'Blue')` | same |
| `h.thrice(2)` on a module | `Type is not callable (Cannot call 'h.thrice' (not defined in the imported module))` | Only functions can be called |
| `p.show()` on a struct | `Struct ... has no field 'show'` then `Type is not callable (Cannot call 'p.show' (undefined identifier))` | Only functions can be called |
| `P{x: 1}` missing `y` | `Type mismatch (Missing struct fields: y)` | Ensure the types match or use an explicit cast |
| `new [3]i32` | `Type mismatch: expected 'scalar or struct allocation', got '[3]i32' (new [N]T heap arrays are not implemented; ...)` | Ensure the types match or use an explicit cast |
| `make()` with `$T` only in the return | `Generic parameter count mismatch: Could not infer generic parameter '$T'` | Provide the correct number of generic type arguments |
| `cast(i32, "s")` | `Unsafe type cast (cast must be classified and range-proven: only primitive numeric casts are supported)` | Narrow the source type first so the cast cannot lose data |
| `a << 40` | `Operator requires compatible types (Shift count must be non-negative and less than 32)` | Ensure operand types are compatible with the operator |
| `del p` twice | `Use after move or delete (moved/deleted values cannot be read: 'p' was moved or deleted earlier)` | Use the value before deleting it, ... |
| `io2 :: import "std/io"` (second import) | `Import name conflicts with existing definition: Duplicate import of 'std/io': importing the same file twice in one file is a compile error` | Use an alias for the import (it already has one; the fix is to delete the line) |
| `x = x + 1` on a parameter | `Cannot assign to immutable binding: 'x' is immutable` | Declare the binding with := (following it gives `x := x + 1`, which a7 accepts and Zig rejects, P2-5; the working fix is a local with a new name, or a `ref` parameter) |
| `xs[i]` with `i: i32` | `Array index must be integer: got 'i32; expected usize'` | (hint is right; headline contradicts `i32`, and the quote wraps two things) |
| `io.println("{}", [bold]x)` | `Unexpected AST node kind: Unknown expression kind: NodeKind.TYPE_ARRAY` | This is likely a compiler bug, please report it |
| `"hello " + name` | `Requires numeric type` | Use i8, i16, ... f64 |

`duplicate_parameter` is a never-raised code (PLAN); the compiler prints
`Already defined: Parameter 'a'`. `import_name_conflict` is raised, but
for the wrong half of its name: an alias clash (`io` bound twice) prints
`Already defined: Import alias 'io'`, and a second import of one path
under a new alias prints `Import name conflicts with existing definition`
with the alias hint.

Tokenizer messages that contradict the input: `0o89` and `0xZZ` print
`Octal literal must have at least one digit after '0o'` and
`Hexadecimal literal must have at least one digit after '0x'`. Digits
are present; they are the wrong digits. Suggested: `'8' is not an octal
digit`.

The right label exists and is reachable. A bare call to a function that
lives in a file-backed module (`m/bare`) prints `Undefined identifier:
'twice' is defined in the module imported as 'h'; call it through the
module alias` with the hint `Fix the spelling or declare the name before
this line`. That message is the model for F2; its hint should be dropped
there, since the message already gives the fix.

##### F9. Messages that omit the name, the operator, or the type

- `Requires numeric type`, `Requires bool type`, `Requires integer type`
  print no operator and no operand type (`-"a"`, `!a`, `a and true`, `~a`,
  `a * 2` with a string). Suggested: `Operator '+' needs numbers; left
  side is 'string'`.
- `Wrong number of arguments (Expected 2 arguments, got 1)` does not
  name the function. Suggested: `'area' takes 2 arguments (w, h); 1 given`.
- `Argument type mismatch: expected 'i32', got 'string' (Argument 2)`
  gives a position, not the parameter name, and the span is the callee
  (P2-28).
- `Missing return statement: Function 'double' does not return on all
  paths` for a body of `x * 2`. The span is the function name. A newcomer
  who forgot `ret` gets no pointer at the last expression.
- `If expression branches have different types: expected 'string', got
  'i32'`: span is `if`, not the `else` branch.
- `Already defined: Variable 'count'` does not say where the first
  definition is, or that `=` reassigns.
- `Module 'utils' not found` does not say which path was tried.
- `Exact constant does not fit default i32; use an explicit destination
  type` does not print the value.
- `Operator requires compatible types (eq between i32 and string)`:
  operator shown as `eq`.

##### F10. Leaked internals

| Text | Where |
| --- | --- |
| `expected 'unknown type', got 'i32'`; `got 'ref unknown type'`; `expected 'unknown type', got 'unknown type'` | `ty_undefined_type`, `b06a`, `b24b`, `sf_nil`, `ty_compare_mismatch` |
| `Cannot access field 'x' on undefined identifier 'expression'` | `b24b_field_before_def` (the identifier is `l.a`) |
| `Unknown expression kind: NodeKind.TYPE_ARRAY` | `x_rich_markup` |
| `Expected RIGHT_BRACE, got EOF`, `LEFT_BRACE`, `DOT_DOT`, `RIGHT_PAREN`, `LEFT_PAREN`, `INTEGER_LITERAL` | parse errors |
| `expected 'Pair(i32)', got 'Pair(A, B)'` next to `expected '$A'` | `sem_generic_mismatch` (two spellings of one parameter) |
| `Exact constant 5/2 is fractional and cannot fit i32` for the literal `2.5` | `b04_wrong_argtype` |
| `cast must be classified and range-proven` | all cast errors |
| `zig backend ABI/lowering is not implemented yet` | variadic parameter |
| `explicit generic environment` | codegen |
| `Use a current virtual stdlib import or keep file-backed modules in the same source file until backend linking is implemented` | `unsupported_import` hint in `errors.py:313` (not triggered) |
| `got 'None'` | bare `ret` in a value function. P2-39. |

##### F11. Rendering defects

1. A source line wider than the terminal wraps, and the caret line wraps
   separately. The underline lands at column 0 of the next row
   (`b/x_wide_line`, `COLUMNS=100`):
   ```
      4 ┃     io.println("{} {} ... 11, 12, 
   13, 14, 15, 16, 17, 18, 19, 20, undefined_name_here)
        ┃                                                                                              
   └─────────────────┘
   ```
2. A 70,000-character line is printed whole, with a 70,000-character
   underline (`c/tok_too_long_string`). No truncation exists.
3. No snippet for: every `Exact constant ...` error, `No entry point`,
   `Module ... not found`, parse errors in imported modules, all codegen
   errors. The first group goes through `add_error(str, span)` and loses
   `source_lines` (inference from `type_checker.py:1233`).
4. No hint for any error without an enum code: entry point, main
   signature, exact constants, module not found, import cycle, all parse
   errors, all codegen errors, divisor/index/slice proofs.
5. `Found 1 error:` / `Error 1/1:` header appears only at the semantic
   stage. Tokenizer and parse errors print without it.
6. Location format differs by command: `[line 4: col 13]` (pipeline),
   `file:4:13:` (check), `✗ 4:10:` (codegen).
7. `io format string expects 1 values, got 2`: plural.
8. An empty file reports `No entry point` (`file_empty` is a
   never-raised code, PLAN).
9. Some spans point one column past the token, which is separate from
   P2-28: `x := 1e` reports col 12 (literal is cols 10-11); `x := 'a`
   reports col 12; `if (x > 0)` with no block reports col 15, past the
   end of the line. The caret lands on empty space.

##### F12. Phrasing is not consistent

- Three shapes for detail: `Headline: detail` (semantic), `Headline:
  expected 'A', got 'B' (detail)` (type), `Headline (obligation: reason)`
  (safety).
- Capitals inside the detail vary: `Got 'i32'` vs `got 'i32'`;
  `Variable 'x'`, `Label 'nope'`, `Cycle: a -> b -> a`, `'k' is immutable`.
- `The char is not closed`, `The string is not closed`, `Comment not closed`.
- Hints that restate the message: `break`/`continue` in match (the
  advice sentence is printed twice, once in the message, once as hint),
  `fall`, `Requires bool type` / `Use a bool value (true or false)`,
  `Type is not callable` / `Only functions can be called`.
- Type errors quote types (`'i32'`); constraint errors do not
  (`requires Numeric, got string`).

#### Beginner mistakes

Score: 2 = a newcomer can fix it from the message; 1 = location is right
but the fix must be guessed; 0 = misleading or no usable direction.

| # | Mistake | First message printed | Errors | Score |
| --- | --- | --- | --- | --- |
| 1 | no `main` | `No entry point: file defines no 'main :: fn()'; add one or check as a library with --lib` | 1 | 2 |
| 2 | typo `totl` | `Undefined type (Identifier 'totl')` + hint about importing a module | 1 | 1 |
| 3 | `area(3)` for two params | `Wrong number of arguments (Expected 2 arguments, got 1)` | 1 | 2 |
| 4 | `area(3, 2.5)` | `Exact constant 5/2 is fractional and cannot fit i32`, then `Argument type mismatch: expected 'i32', got 'f64' (Argument 2)` | 2 | 1 |
| 5 | `if/else if` with no final `ret` | `Missing return statement: Function 'sign' does not return on all paths` | 1 | 2 |
| 6a | `count = 0` to declare | `Undefined type (Identifier 'count')`, `Assignment type mismatch: expected 'unknown type', got 'i32'`, `Undefined type` again | 3 | 0 |
| 6b | reassign a `::` binding | `Cannot assign to immutable binding: 'count' is immutable` + `:=` hint | 1 | 2 |
| 6c | `count := ...` twice | `Already defined: Variable 'count'` | 1 | 1 |
| 7a | body `x * 2` without `ret` | `Missing return statement: Function 'double' ...` at the function name | 1 | 1 |
| 7b | `return x * 2` | `Unexpected identifier after 'return'; missing operator?` | 1 | 0 |
| 8 | assign to parameter | `Cannot assign to immutable binding: 'x' is immutable`; hint says use `:=` | 1 | 1 |
| 9a | `print("hi")`, no import | `Undefined type (Identifier 'print')`, `Type is not callable (Cannot call undefined identifier 'print')` | 2 | 0 |
| 9b | `io.println` with no import | `Undefined type (Identifier 'io')`, `Cannot access field on non-struct type (...)`, `Type is not callable (...)` | 3 | 0 |
| 10 | `p.show()` | `Struct has no such field (Struct 'P' has no field 'show')`, `Type is not callable (...)` | 2 | 1 |
| 11 | `xs[i]`, `i: usize` param | `Index not proven in bounds (index must satisfy 0 <= index < len: index bounds are not proven)`, no hint | 1 | 0 |
| 12 | `sum / n` | `Divisor not proven non-zero (division/modulo divisor must be non-zero: divisor may be zero)`, no hint | 1 | 0 |
| 13 | recursive `fib` | `Recursion is not allowed: Cycle: fib -> fib` + loop hint | 1 | 2 |
| 14 | `n := new Node; n.v = 3` | `Reference not proven non-nil (...)` twice (field write, call argument) | 2 | 0 |
| 15 | `for (i := 0; ...) {` | `Expected identifier or '{' after 'for' keyword` at `(` | 1 | 1 |
| 16 | `a && b`, `a \|\| b` | `Expected expression` | 1 | 0 |
| 17 | `i++` | `Expected expression` | 1 | 0 |
| 18 | semicolons | accepted, exit 0 | 0 | n/a |
| 19 | missing `}` | `Expected RIGHT_BRACE, got EOF [line 10: col 1]`, no caret | 1 | 1 |
| 20 | `import "utils"` (absent) | `Module 'utils' not found [line 2: col 1]`, exit 3, no snippet, no hint | 1 | 1 |
| 21 | if-expression `"big"` / `0` | `If expression branches have different types: expected 'string', got 'i32'` | 1 | 2 |
| 22 | match without `else` | enum: `Non-exhaustive match: Enum 'Dir' missing case(s): E, W`. Match expression on int: `match expression must cover every value; add an else or wildcard branch`. Statement match on int: accepted. | 1 | 2 |
| 23 | `small: u8 = 256`, `big := 3000000000` | `Exact constant 256 is out of range for u8`; `Exact constant does not fit default i32; use an explicit destination type`; no snippet, no hint | 2 | 1 |
| 24 | struct field of a type declared later | `Type mismatch: expected 'unknown type', got 'Point' (Field 'a')` x2, `Cannot access field 'x' on undefined identifier 'expression'` | 3 | 0 |
| 25 | `"hello " + name` | `Requires numeric type` + list of integer types | 1 | 0 |

Totals over the 28 scored rows: seven at 2, ten at 1, eleven at 0.
`import "io"` (without `std/`) and a struct literal used above its
declaration compiled with exit 0, so they produced no diagnostic.

#### Cascades: one mistake, several errors

Counts are `len(error.details)`. Rows that are the P2-39 duplicate are
marked.

| Errors | Program | Mistake | What is printed |
| --- | --- | --- | --- |
| 3 | `b06a_eq_decl` | `count = 0` undeclared | undefined, `expected 'unknown type'`, undefined again at the next use |
| 3 | `b09b_io_no_import` / `b20b_import_stmt` | no `io ::` binding | undefined `io`, field access on undefined, not callable; all on one span (P2-39 family) |
| 3 | `b24b_field_before_def` | type declared below its use | two `expected 'unknown type'`, one `undefined identifier 'expression'` |
| 3 | `sem_generic_mismatch` | `Pair(i32)` for a two-parameter struct | two field mismatches against `$A`/`$B`, one variable mismatch (P1-5: wrong type-arg count swallowed) |
| 3 | `ty_use_after_del` | read after `del`, and no nil check after `new` (two mistakes) | non-nil proof at the write, use-after-delete, non-nil proof at the read. With `if p != nil` around the uses (`x/uad`) the count is 1. |
| 2 | `b09_print_no_import`, `sem_undefined_fn`, `x_bare_imported_call` | call to an undefined name | undefined + not callable, one span (P2-39 family) |
| 2 | `b10_no_method`, `b10b_str_len` | unknown member call | no such field + not callable, one span (P2-39 family) |
| 2 | `ty_undefined_type` | `a: Nope = 1` | undefined type + `expected 'unknown type', got 'i32'` |
| 2 | `ty_undefined_type_param` | `fn(a: Strng)` | same error twice (P2-39) |
| 2 | `ty_compare_mismatch` | `if a == "s"` | operator mismatch + `Condition must be bool: expected 'bool', got 'unknown type'` |
| 2 | `ty_no_such_field_lit` | `P{x: 1, zz: 2}` | missing field `y` + no field `zz` (one typo) |
| 2 | `x_generic_conflict` | `same(1, "s")` | generic conflict + argument mismatch that blames argument 1 (PLAN: wrong `$T` label) |
| 2 | `b04_wrong_argtype` | `2.5` into `i32` | exact-constant error + argument mismatch |
| 2 | `sem_unreachable` | statement after `ret` | unreachable code + `Missing return statement` for a function that returns |
| 2 | `x_del_twice_field` | write after `del`, and no nil check (two mistakes) | use-after-delete + non-nil proof |
| 2 | `b14_nil_deref` | no nil check after `new` | one per use |

Root cause in most rows: an expression that already failed yields
`unknown type`, and later checks report against it instead of staying
silent.

#### Multi-file

| Case | File named (human / check / JSON) | Snippet from the right file |
| --- | --- | --- |
| semantic error in `helper.a7` | no / basename / full path | yes |
| safety error in `helper.a7` | no / basename / full path | yes |
| tokenizer error in `helper.a7` | no / basename / full path | yes |
| parse error in `helper.a7` | no / basename / full path | no snippet printed |
| errors in both files | no / basename / full path | yes, each from its own file |
| import cycle | no / `main.a7:1:1` / full path | yes; message `Circular dependency detected: helper -> main -> helper`; no hint (untyped error, `CIRCULAR_IMPORT` advice unused) |
| missing module | no / basename / full path | no snippet |
| call to a name the module lacks | n/a | yes; headline `Type is not callable` (F8) |

JSON `input` stays the entry file; only `details[].file` shows the
module. `error.span` copies the first detail's span without its file, so
`error.span` alone can point into the wrong file.

#### ERROR_CATALOG vs compiler (17 sampled rows)

| Code | Catalog trigger → fix | What the compiler prints | Match |
| --- | --- | --- | --- |
| invalid_character | stray char "(e.g. `@`)" | `x := 1 @ 2` gives ParseError `Expected LEFT_PAREN, got INTEGER_LITERAL`, exit 5. A backtick gives `Unexpected character: '`'`. | no (example) |
| break_undefined_label | `break 'nope` | `break 'nope` gives `The char is not closed`, exit 4. Real syntax is `break nope`: `Break label is not defined: Label 'nope'`. | no (syntax) |
| continue_undefined_label | `continue 'nope` | same | no |
| return_outside_function | `return` at top level, exit 6 | `ret 1` at top level: ParseError `Expected declaration (constant, variable, or function)`, exit 5. Keyword is `ret`. | no |
| defer_outside_function | `defer` at top level, exit 6 | ParseError, exit 5, same text | no |
| missing_type_annotation | bare `x;` | `Undefined type (Identifier 'x')` | no |
| missing_type_or_initializer | bare `x;` | same; code has no raise site | no |
| nil_not_reference_type | `nil` for plain `i32` | `Nil only allowed for reference types: got 'i32' (Variable 'x')` (the type-check code fires first) | no |
| duplicate_parameter | `fn(a: i32, a: i32)` | `Already defined: Parameter 'a'` | no |
| duplicate_variant | enum variant twice | exit 0 (P2-5) | no |
| duplicate_generic_param | `$T` listed twice | `Pair($T, $T) :: struct` exits 0 | no |
| operator_type_mismatch | `1 + "s"` | `Requires numeric type` | no |
| requires_pointer_type | deref of plain value | `a.*` is a ParseError `Expected field name after '.'`; `a.val` gives `Cannot access field on non-struct type` | no |
| module_not_found | exit 3 ImportError, as noted | `Module 'utils' not found`, exit 3 | yes |
| delete_non_reference | `del 1` | `Delete requires a reference type: Got 'i32'` | yes |
| invalid_generic_syntax | `$1T` | `Invalid generic syntax: generic types must start with a letter after '$'` | yes |
| ParseError | `fn( {` → "complete the syntax at the span" | `Expected type` at 1:10; no hint printed | trigger yes, fix text is not shown to users |

Also: every "fix" column for parse, codegen, entry-point and
exact-constant rows describes advice that no output shows. The catalog
has no row for the `Exact constant ...` family or for the four safety
headlines (`Divisor not proven non-zero`, `Index not proven in bounds`,
`Slice bounds not proven`, `Reference not proven non-nil`). Header count
and missing codes: P3-4.

#### Advice strings that are generic or wrong

Generic (restate the headline, give no action):

- `Ensure the types match or use an explicit cast` (type_mismatch; shown
  for missing struct fields, `new [N]T`, match pattern types)
- `Provide the correct number of arguments`
- `Ensure argument types match parameter types`
- `Ensure operand types are compatible with the operator`
- `Ensure the type satisfies the generic constraint`
- `The assigned value must match the variable's type`
- `Return value must match the function's return type`
- `Both branches of if expression must have the same type`
- `Use a boolean expression for the condition` (does not suggest `x != 0`)
- `Use a bool value (true or false)`
- `Use an array or slice type`, `Use a struct type`, `Use a pointer (ref) type`, `Use a function or function pointer`
- `Only functions can be called`
- `Field access requires a struct type`
- `Only arrays and slices can be indexed`
- `Remove unreachable code or fix control flow`
- `Reference use requires a proven non-nil reference` (circular)
- `Remove or replace the character at the reported column`
- `Rewrite without this construct; it has no support in this release`
- `The type could not be determined`, `This type cannot be nil`,
  `These types cannot be cast to each other`

Wrong for the trigger that reaches them:

- `Fix the spelling or import the module that defines the type` for undefined variables and functions (F2).
- `Fix the field spelling or add the field to the struct` for stdlib functions and enum variants.
- `Declare the binding with :=` for a parameter.
- `Use an alias for the import or rename the conflicting definition` for a duplicate import.
- `Provide the correct number of generic type arguments` for an inference failure (`make()`). The conflicting-`$T` case is the known label defect in PLAN.
- `Narrow the source type first so the cast cannot lose data` for a string cast, and for a narrowing cast where the accepted fix is a range guard (`if a >= 0 and a <= 127`), not a narrower source type.
- `Use i8, ..., f64` for string `+`.
- `This is likely a compiler bug, please report it` for user syntax `[bold]x`.
- `Add a return statement that covers all code paths`: the keyword is `ret`.
- `Fix the module path or add the file to the search path` (`module_not_found`, not shown by the live path): no search-path option exists in the CLI help.
- `Use fall only as the final statement of a non-final match case` paired with the message `fall cannot appear in the final match case` (`c/sem_fall_middle`). The `fall` is in `case 1:`, which is followed by `else:`, and is not the last statement of its body. The reader sees a non-final arm; the message does not say that `else` does not count, or that the position in the body is also wrong.
- `Internal address-of requires variables, fields, indexes, or dereferenced references`: "Internal" (not triggered).

#### Codes not triggered

No JSON code exists, so these are headlines I never saw.

- Reached a different diagnostic first: `return_outside_function`,
  `defer_outside_function` (parser, exit 5); `nil_not_reference_type`
  (`nil_only_for_references` fires); `requires_pointer_type` (no deref
  syntax parses); `address_of_rvalue` (`bump(3)` gives argument type
  mismatch); `missing_type_annotation` form 1.
  `undefined_identifier` was triggered late through `m/bare` (see F8);
  its second raise site (match pattern identifier) was not.
- Accepted with exit 0: `duplicate_generic_param` (`Pair($T, $T)`),
  `invalid_binary_number` with `0b12` (bare `0b` does trigger it).
- Not attempted: `out_of_memory`.
- No raise site (PLAN, 22 never-raised codes): not probed.

#### Not done

- `compile`, `build`, `run`, `doc` commands and `-v` output. Zig build
  failures surfaced through `build`/`run` were not examined.
- Color output and terminal widths other than 100 columns.
- `--lib` mode diagnostics.
- Tagged-union match, `where` clause and `$N` diagnostics beyond one
  constraint probe (`requires Numeric, got string`).
- Rich-markup crash (P2-12) was not re-tested with a crashing input.
- `site/public/docs/` pages other than `compiler.md`.
- Spans were checked by slicing the source at each JSON span; I did not
  judge whether a wider span would be better (P2-28).

## Appendix E: Fuzzing (full report)

Embedded copy of `reports/fuzz.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Fuzz and stress report, 2026-10-04

Target: HEAD `c8face6` plus the uncommitted working tree. Zig was not needed
for the counts; `--mode pipeline` runs codegen.

Scratch: `/tmp/claude-1000/-home-cx89-Projects-pl-dev-a7-py/fa2805be-328b-45b2-a1df-ab981ee81691/scratchpad/fuzz/`
(called `$S` below). Nothing in the repo was edited. All reproducers are in
`$S/repro/`, `$S/tgt/`, `$S/exp/`, `$S/big/`, `$S/keep/`.

#### What ran

- `harness.py`: in-process driver around `A7Compiler.compile_file_detailed`,
  4 workers, 20 s alarm per case, traceback captured by wrapping
  `FailureInfo` and `_finish_with_failure` inside the harness process.
- 73,385 cases, fixed seeds (1, 99, 777, 4242, 4243, 20261004).
  Seeds: 51 examples + 6 `examples/rejected` + 10 `test/fixtures` files (67),
  plus 1,036 A7 snippets harvested from string constants in `test/*.py`
  (run with `--lib` so snippets without `main` reach codegen).
- Token mutations: delete, duplicate, swap, identifier to keyword, extreme
  literal, mild literal, unbalanced brackets, truncate, span delete/duplicate,
  splice, nesting wrap (3/40/300 levels), identifier swap, operator swap,
  type swap, line delete/swap.
- Byte mutations: NUL, invalid UTF-8, lone surrogate, BOM (start and middle),
  CR-only, CRLF, control bytes, odd Unicode, 200 KB line, 2 KB / 100 KB / 1 MB
  runs of one token.
- Every finding below was rerun through `.venv/bin/a7` (same entry point as
  `uv run a7`).

Outcome over all 73,385 in-process cases:

| exit | 0 | 3 | 4 | 5 | 6 | 7 | 8 | 1 (escaped) | timeout |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| count | 11,560 | 709 | 2,523 | 43,319 | 15,081 | 128 | 57 | 1 | 7 |

Crash buckets (exception type + innermost `a7/` frame):

| Bucket | Count | Finding |
| --- | --- | --- |
| `ValueError` at `type_checker.py:3960` | 25 | F3 |
| `ValueError` at `type_checker.py:3956` | 32 | F3 |
| `RecursionError` escaping `compile.py:623` via `_safe_json_dumps` | 1 | F1 |
| timeout, 1 MB inputs | 7 | linear, see scaling notes |

No exit 8 came from the tokenizer, parser, name resolution, validator,
safety pass, backend, or formatters. No invalid JSON was produced on any
exit 0-8 path. No exit 7 carried a non-`CodegenError` exception.

#### Findings

##### F1. `--format json` exits 1 with a Python traceback on a long postfix chain

Severity: high. Exit 1 is outside the contract. stdout is empty, so a JSON
consumer gets nothing.

Reproducer (`$S/repro/field_16000.a7`, generated):

```
P :: struct { x: i32 }
main :: fn() {
    p := P{x: 1}
    y := p.x.x.x.x ... (.x repeated 10,027 times or more)
}
```

```
$ .venv/bin/a7 --mode ast --format json $S/repro/field_16000.a7; echo $?
Traceback (most recent call last):
  File "a7/cli.py", line 297, in main
  File "a7/compile.py", line 608, in compile_file_detailed
  File "a7/compile.py", line 642, in _emit_success
  File "a7/compile.py", line 42, in _safe_json_dumps
RecursionError: maximum recursion depth exceeded while encoding a JSON object
1
```

Same in `--mode semantic`, `pipeline`, `doc` with `--format json`. There the
type checker raises first (F2), then the handler at `compile.py:611-623`
calls `_safe_json_dumps` inside the `except` block and that raises again.
Last passing length 9,984, first failing 10,027 (both modes). Human format
gives exit 0 (`ast`) or exit 8 (others).

Suspected: `a7/compile.py:42` (`json.dumps` of the nested AST),
`compile.py:623` and `compile.py:642` (unguarded emit). Any left-nested
shape works: `.x`, `[0]`, `()`, or the known flat binary chain.

##### F2. Postfix chains bypass the 256 nesting cap; type checker exits 8 at about 330-400 links

Severity: high. Same recursive `visit_expression` as P2-29, but a different
trigger and a different frame. P2-29 lists lines 1634, 1698, 1768. This one
cycles `type_checker.py:1694 -> 1715 -> 2561 (visit_field_access)`.
The parser builds postfix chains in a loop and never calls `_enter_nesting`.

```
P :: struct { x: i32 }
main :: fn() {
    p := P{x: 1}
    y := p.x.x.x ... (400 times)
}
```

```
$ .venv/bin/a7 --mode pipeline $S/repro/field_400.a7; echo $?
Unexpected error: maximum recursion depth exceeded
8
```

300 links: exit 6 (normal error). 400 links: exit 8. A valid program hits it
too: 400 struct types `S0..S400`, `s.c.c.c...v` exits 8; 300 exits 0
(`$S/stress/field_chain_400.a7`).

Other shapes with the same result:

| Shape | First N with exit 8 |
| --- | --- |
| `p.x.x.x...` | 400 (300 ok) |
| `a[0][0][0]...` | 400 (300 ok) |
| `f()()()...` | 400 (300 ok) |
| `a[0].q()[0].q()...` | 200 pairs (100 ok) |
| `p.next.next...` on `ref N` | 400 (300 ok) |
| `f(1) + f(1) + ...` (P2-29) | 400 (300 ok) |

`--mode tokens` and `--mode ast` (human) stay exit 0 at 16,000 links.

##### F3. Exact constant over 4,300 digits exits 8 (`ValueError` from `int` to `str`)

Severity: high. Nine bytes of source. Two crash sites, both error messages
that format a `Fraction`.

```
main :: fn() {
    x: i32 = 1e4300
}
```

```
$ .venv/bin/a7 --mode pipeline $S/exp/i32_e4300.a7; echo $?
Unexpected error: Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit
8
```

`1e4299` exits 6. `--format json` gives valid JSON with `exception_type:
ValueError`. `--mode semantic` and `--mode doc` also exit 8; `tokens` and
`ast` exit 0.

- `a7/passes/type_checker.py:3960` (`out of range`): `x: i32 = 1e4300`,
  `f(1e99999)`, `ret 1e99999`, `P{x: 1e99999}`, `x += 1e99999`,
  `while i < 1e99999`, `K :: 1e99999` then `x: i32 = K`.
- `a7/passes/type_checker.py:3956` (`is fractional`): `x: i32 = 1e-99999`,
  `[1e-99999, 2]` into `[2]i32`.
- No float literal needed. A product of 240 twenty-digit integers reaches it:
  `x: i32 = 99999999999999999999 * 99999999999999999999 * ...`
  (`$S/big/mul_300_i32.a7`). The same product as an index, an array size,
  a comparison operand, a `cast(u8, ...)` argument, or a `println` argument
  exits 8 at the same line.

The tokenizer caps a numeric token at 100 characters, so the exponent is the
short route.

##### F4. Float literal with a large exponent hangs the type checker

Severity: high. Sixteen bytes of source, unbounded CPU and memory.

```
main :: fn() {
    x := 1e999999999
}
```

```
$ timeout 20 .venv/bin/a7 --mode semantic $S/tgt/exp_huge.a7; echo $?
124
```

Stack at 5 s (`faulthandler`): `fractions.py:274 __new__` <-
`a7/exact_constants.py:98 evaluate` (`Fraction(node.raw_text)`) <-
`type_checker.py:144 _evaluate_exact` <- `type_checker.py:1677`.
`Fraction("1e999999999")` computes `10**999999999`.

| Literal | `--mode semantic` |
| --- | --- |
| `1e999999` | 0.2 s |
| `1e9999999` | 4.1 s |
| `1e99999999` | timeout 20 s |
| `1e-99999999` | timeout 20 s |

Negative exponents hang the same way. `--mode tokens` and `--mode ast`
return at once. The exponent has no cap of its own; only the 100-character
token cap applies.

##### F5. Safety pass is quadratic in locals, in `new`/`del` pairs, and in loop depth

Severity: medium. Nothing worse than quadratic was found. These are the
dimensions with exponent near 2.

| Input | N: time | Hot function (cProfile) |
| --- | --- | --- |
| N locals `vI: i32 = k` | 2500: 1.1 s, 5000: 2.3 s, 10000: 11.7 s, 20000: >20 s | `a7/passes/safety.py:500 _invalidate_length_relations` (scans all facts per declaration) |
| N `Box([I]i32)` locals | 2500: 1.4 s, 5000: 4.0 s, 10000: 12.5 s, 20000: >40 s | same |
| N `p := new i32; if p != nil { del p }` | 500: 0.8 s, 1000: 1.9 s, 2000: 4.7 s, 4000: 15.9 s, 5000: >27 s | `safety.py:510 _join_facts` |
| N nested `for` loops | 60: 0.15 s, 120: 0.5 s, 240: 2.0 s | `safety.py:415 _deferred_assigned_symbols`, `safety.py:470 _deleted_names` (re-walk the whole body per loop) |

With 10,000 `new`/`del` pairs one C-level call blocked `SIGALRM` for over
100 s.

##### F6. `E :: enum { A = 1e99999 }` exits 0 and emits `std.math.inf(f64)` as the tag

Severity: low (accepted, then Zig rejects). `$S/tgt/enum_exp.a7`.
`zig build-exe` says `float value Inf cannot be stored in integer type
'i32'`. Enum values are not range- or integer-checked.

##### F7. New exit 7 after `--mode semantic` exit 0

Severity: low.

```
K :: f() {
    p: struct { x: i32 }
}
main :: fn() {
}
```

```
$ .venv/bin/a7 --mode semantic $S/repro/const_call_block.a7; echo $?   -> 0
$ .venv/bin/a7 --mode pipeline $S/repro/const_call_block.a7; echo $?
2:8: Zig backend: unsupported expression node 'TYPE_STRUCT'            -> 7
```

`f` is undefined and the block after the call is accepted at top level.
Same with `main :: main() { point: struct { x: i32 } }` under `--lib`.

##### Same root as known items (listed for completeness, not new)

- Import path longer than `PATH_MAX` in total (`"a/a/a/...x"`, 5,000 chars,
  each component short) exits 8 with `[Errno 36]`. Same site as P2-19.
- Nesting cap counts parser entries, not source levels. `if`, `while`,
  `match`, parens, calls, casts, array literals stop at 126 levels; if-
  expressions at 84; blocks, unary operators, type prefixes at 253-255.

#### Step 3: modes and JSON

For the inputs above and for the largest input under the cap in each of 24
nesting dimensions, all of `tokens`, `ast`, `semantic`, `pipeline`, `doc`
were run in `human` and `json`.

- JSON stayed valid on every exit 0-8 path. The only invalid output is F1
  (empty stdout, exit 1).
- `--mode tokens` and `--mode ast` never exit 8.
- `--mode doc` behaves as `semantic` for F2-F4.
- Human format is slow on big inputs but linear: token table 140 us per
  token (80,000 tokens: 11.4 s; JSON: 0.3 s). AST view of 80,000 expression
  statements exceeds 20 s; JSON takes 2.5 s.
- No Rich markup crash (P2-12) appeared in 2,680 human-format pipeline
  cases.

#### Step 4: semantic accepts, codegen fails

11,560 mutated or harvested inputs reached exit 0 or 7 in pipeline mode.
128 exited 7; none exited 8 after semantic passed. Distinct messages:

| Count | Message | Status |
| --- | --- | --- |
| 102 | `generic type requires an explicit generic environment` | known P2-40 / P3-13 |
| 22 | `unsupported expression node 'TYPE_SET'` | known P3-19 |
| 1 | `io.print/io.println cannot be used as expression values` | known P2-49 |
| 1 | `array binary initializer requires a known array type` (`c := a + a`) | known P2-49 |
| 3 | `unsupported expression node 'TYPE_STRUCT'` | new, F7 |

#### Scaling table

In-process, 4 workers in parallel, so times are noisy by about 30%.
`t/e` = seconds / exit code. `cap` = exit 5 "Maximum nesting depth (256)
exceeded". `>20` = alarm.

Breadth dimensions:

| Dimension | 10 | 100 | 1000 | 5000 | 20000 | Shape |
| --- | --- | --- | --- | --- | --- | --- |
| functions | 0.01/0 | 0.12/0 | 1.5/0 | 8.9/0 | >20 | linear, 1.8 ms each |
| statements in one fn | 0.01/0 | 0.04/0 | 0.46/0 | 2.5/0 | 10.2/0 | linear |
| locals | 0.01/0 | 0.02/0 | 0.27/0 | 2.4/0 | >20 | quadratic, F5 |
| struct fields | 0.01/0 | 0.03/0 | 0.30/0 | 1.7/0 | 8.6/0 | linear |
| enum variants | 0.00/0 | 0.01/0 | 0.05/0 | 0.27/0 | 1.5/0 | linear |
| union variants | 0.01/0 | 0.01/0 | 0.12/0 | 0.50/0 | 2.0/0 | linear |
| match arms (int) | 0.01/0 | 0.10/0 | 0.93/0 | 4.7/0 | >20 | linear |
| match arms (enum) | 0.01/0 | 0.07/0 | 0.87/0 | 5.6/0 | >20 | linear |
| match ranges | 0.01/0 | 0.09/0 | 1.2/0 | 6.4/0 | >20 | linear |
| values in one `case` | 0.01/0 | 0.02/0 | 0.21/0 | 0.83/0 | 3.7/0 | linear |
| call arguments | 0.01/0 | 0.02/0 | 0.18/0 | 1.4/0 | 9.9/0 | about n^1.4 |
| array literal length | 0.00/0 | 0.01/0 | 0.08/0 | 0.39/0 | 1.9/0 | linear |
| string literal length | 0.01/0 | 0.00/0 | 0.01/0 | 0.01/0 | 0.02/0 | linear |
| string of N `\n` escapes | 0.00/0 | 0.00/0 | 0.00/0 | 0.01/0 | exit 4 "String is too long" | capped |
| format args | 0.00/0 | 0.01/0 | 0.08/0 | 0.52/0 | exit 4 | capped |
| identifier length | 0.00/0 | 0.00/0 | exit 4 "too long" | - | - | capped |
| struct declarations | 0.01/0 | 0.02/0 | 0.17/0 | 1.1/0 | 4.0/0 | linear |
| globals | 0.01/0 | 0.02/0 | 0.14/0 | 0.54/0 | 2.5/0 | linear |
| generic instances `Box([I]i32)` | 0.01/0 | 0.06/0 | 0.49/0 | 3.1/0 | >40 | quadratic, F5 |
| generic fn calls | 0.01/0 | 0.06/0 | 0.77/0 | 4.8/0 | 19.5/0 | linear |
| defers | 0.01/0 | 0.09/0 | 0.65/0 | 3.2/0 | 13.9/0 | linear |
| `new`/`del` pairs | 0.01/0 | 0.08/0 | 1.5/0 | >27 | - | quadratic, F5 |
| sequential `if` | 0.01/0 | 0.09/0 | 1.1/0 | 5.3/0 | >20 | linear |
| sequential `while` | 0.02/0 | 0.11/0 | 0.99/0 | 4.7/0 | >20 | linear |
| imported modules (flat) | 0.01/0 | 0.09/0 | 0.63/0 | 4.3/0 | >20 | linear |
| comment lines | 0.00/0 | 0.00/0 | 0.00/0 | 0.01/0 | 0.04/0 | linear |
| bare expression statements `1 1 1 ...` | - | - | 0.13/0 | 0.96/0 (4k) | 2.6/0 (16k), 13.1/0 (64k) | linear, 0.2 ms each; 1 MB of `"` or `1 ` exceeds 20 s |

Depth dimensions:

| Dimension | 10 | 100 | 200 | 250 | 300 | 400 | 1000 | 5000 | Stopped by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nested blocks | 0.01/0 | 0.02/0 | 0.05/0 | 0.07/0 | cap | cap | cap | cap | cap at 254 |
| nested `if` | 0.01/0 | 0.10/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested `while` | 0.01/0 | 0.35/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested `for` | 0.02/0 | 0.38/0 | 1.4/0 | 2.5/0 | cap | cap | cap | cap | cap at 254; quadratic below it, F5 |
| nested `match` | 0.03/0 | 0.13/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested parens | 0.01/0 | 0.00/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested calls `f(f(...))` | 0.01/0 | 0.03/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested `cast` | 0.01/0 | 0.03/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested if-expression | 0.01/0 | cap | cap | cap | cap | cap | cap | cap | cap at 85 |
| nested array literal | 0.00/0 | 0.01/0 | cap | cap | cap | cap | cap | cap | cap at 127 |
| nested struct literal | 0.00/6 | 0.01/6 | cap | cap | cap | cap | cap | cap | cap at 127 |
| unary `-` / `!` chain | 0.00/0 | 0.01/0 | 0.02/0 | 0.03/0 | cap | cap | cap | cap | cap at 254 |
| `[2][2]...i32` | 0.00/0 | 0.02/0 | 0.06/0 | 0.08/0 | cap | cap | cap | cap | cap at 254 |
| `[][]...i32` | 0.01/0 | 0.01/0 | 0.02/0 | 0.02/0 | cap | cap | cap | cap | cap at 255 |
| `ref ref ... i32` | 0.01/0 | 0.01/0 | 0.02/0 | 0.03/0 | cap | cap | cap | cap | cap at 255 |
| `fn(fn(...))` type | 0.00/0 | 0.01/0 | 0.02/0 | 0.02/0 | cap | cap | cap | cap | cap at 256 |
| `Box(Box(...))` type | 0.00/0 | 0.01/0 | 0.03/0 | 0.03/0 | cap | cap | cap | cap | cap at 255 |
| inline `struct { a: struct {...` | 0.01/0 | 0.01/0 | 0.03/0 | 0.04/0 | cap | cap | cap | cap | cap at 256 |
| `else if` chain | 0.01/0 | 0.06/0 | 0.16/0 | 0.18/0 | cap | cap | cap | cap | cap at 253 |
| field chain `a.b.c` (valid) | 0.01/0 | 0.05/0 | 0.08/0 | 0.10/0 | 0.11/0 | 0.13/**8** | 0.31/**8** | 3.4/**8** | RecursionError, F2 |
| index chain `a[0][0]` | 0.00/6 | 0.01/6 | 0.03/6 | 0.03/6 | 0.03/6 | 0.10/**8** | 0.14/**8** | 1.0/**8** | RecursionError, F2 |
| call chain `f()()()` | 0.00/6 | 0.01/6 | 0.02/6 | 0.02/6 | 0.02/6 | 0.16/**8** | 0.19/**8** | 0.64/**8** | RecursionError, F2 |
| `b and b and ...` | 0.01/0 | 0.02/0 | 0.04/0 | 0.04/0 | 0.05/0 | 0.11/**8** | 0.13/**8** | 1.2/**8** | RecursionError, known P2-29 |
| import chain m0 -> m1 -> ... | 0.01/0 | 0.08/0 | 0.17/0 | 0.17/0 | 0.19/0 | 0.28/0 | 0.85/0 | 5.1/0 | nothing; linear |
| call graph chain g0 <- g1 <- ... | 0.01/0 | 0.10/0 | 0.20/0 | 0.15/0 | 0.18/0 | 0.26/0 | 0.84/0 | 4.9/0 | nothing; linear |
| global constant chain | 0.00/0 | 0.02/0 | 0.04/0 | 0.05/0 | 0.06/0 | 0.08/0 | 0.32/0 | 1.2/0 | nothing; linear |
| nested block comments | 0.00/0 | 0.00/0 | 0.00/0 | 0.00/0 | 0.00/0 | 0.00/0 | 0.00/0 | 0.01/0 | nothing; linear |

At the largest N under the cap, every dimension exits 0 (or 6 where the
program is ill-typed) in all five modes and both formats. The cap holds for
everything the parser recurses on. It does not cover loops in the parser:
postfix chains and binary chains.

Repeated single tokens (2 KB to 1 MB of `(`, `[`, `{`, `-`, `!`, `x(`,
`cast(`, `/*`, `'`, `\`, tab, and 50 more, measured to 64,000 repeats):
all linear, all exit 4 or 5. 1 MB runs from the fuzzer that exit 5 took up
to 8.3 s. Exception: `x.` (F1, F2).

#### Not done

- No `zig build-exe` on fuzz outputs that exited 0. Only F6 was built.
- No coverage-guided fuzzing; mutations are blind. Deep backend paths were
  reached only on 11,560 of 73,385 cases.
- Multi-file fuzzing: imports were stressed for count and depth and probed
  by hand (cycles, self-import, BOM, bad UTF-8, NUL, symlink loop,
  traversal; all exit 3 or 6), but imported files were not mutated.
- The `a7 build` / `check` / `run` subcommands and `--backend`,
  `--profile`, `--no-nonwrap` flags were not fuzzed.
- Combined depth (for example 120 nested `if` plus a 200-term expression
  inside) was not measured. It should lower the P2-29 / F2 threshold.
- In-process, two 1-2 MB inputs (`x.` repeated 1,000,000 times; `"`
  repeated 1,000,000 times) killed a pool worker without a Python
  exception. Through the CLI both time out at 20 s. The cause of the worker
  death (memory limit or C stack) was not isolated.
- No hand minimization beyond what is shown; ddmin was not needed because
  each crash reduced to a one-line body.

## Appendix F: Generated Zig and runtime contract (full report)

Embedded copy of `reports/generated-zig.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Generated Zig quality and runtime contract

Audit date 2026-10-04. Zig 0.16.0, Linux x86_64 (Ryzen AI 9 HX 370, `znver5`).
Working tree as found (uncommitted changes present). Nothing in the repo was
edited. All builds went to
`/tmp/claude-1000/-home-cx89-Projects-pl-dev-a7-py/fa2805be-328b-45b2-a1df-ab981ee81691/scratchpad/zigq/`
(`$Z` below). Probe sources are in `$Z/p/`, binaries in `$Z/bin/`, C baselines
in `$Z/c/`, hand-written Zig experiments in `$Z/vx/`.

Timing numbers are CPU time (user+sys), minimum of 7 runs, on a busy box.
Treat them as indicative. `perf`, `strace`, `valgrind` and `lldb` are not
installed, so there are no instruction counts or syscall counts. Peak RSS
below 8 MB could not be measured (the fork harness floor is about 8 MB).

Rows P0-1, P0-2, P0-5 and P2-42 to P2-51 in PLAN.md are not re-reported. Where
a probe hit one of them it is named.

Commands used throughout:

```
uv run --project /home/cx89/Projects/pl-dev/a7-py a7 FILE -o $Z/x.zig --build-profile {debug,release}
uv run --project /home/cx89/Projects/pl-dev/a7-py a7 build FILE -o $Z/bin/NAME.{debug,release} --profile {debug,release}
```

---

#### Ranked findings

##### F1. Release is `-O ReleaseFast`; every proof gap is undefined behaviour, and overshift is accepted with no proof. VERIFIED

`a7/cli.py:169` passes `-O ReleaseFast`. Debug traps on Zig safety checks.
Release has no check on index, `.?`, `@intCast`, `@divTrunc`, or plain `+`.
The observed release outcomes are wrong values, SIGSEGV, and unbounded output.

New part (not in PLAN.md): a runtime shift count needs no proof at all.
SPEC.md:219-221 says overshift "must stay fail-closed until it lands". It is
not fail-closed.

A7 (`$Z/p/shift2.a7`):

```a7
shl :: fn(a: i32, n: i32) i32 { ret a << n }
main :: fn() { io.println("shl 1 32 = {}", shl(1, 32)) ... }
```

Emitted Zig, both profiles:

```zig
fn shl(a: i32, n: i32) i32 {
    return (a << @intCast(n));
}
```

- Debug: `panic: integer does not fit in destination type`, exit 134.
- Release: SIGSEGV, exit 139, no message (`shift2`). In `shift.a7` (same
  shape after three valid shifts) release printed three correct lines and then
  wrote newlines without end: 900 MB to a file in about two minutes until
  killed.
- `math.abs(i32 min)` lowers to `@as(i32, @intCast(@abs(a)))`. Debug panics.
  Release produced the same endless newline stream (`$Z/p/absmin.a7`).
  STATUS.md lists the abs case as "not a proven safe case"; the release
  outcome is not stated anywhere.

Cost of the safe mode on four kernels (indicative, same emitted Zig rebuilt
with `zig build-exe -O ReleaseSafe`):

| kernel | ReleaseFast | ReleaseSafe |
| --- | --- | --- |
| bench/array_walk | 246.6 ms | 249.0 ms |
| bench/sort_load | 231.6 ms | 231.2 ms |
| bench/alloc_churn | 3.6 ms | 4.6 ms |
| bench/print_lines | 16.0 ms | 20.3 ms |

The two loop kernels show no difference; they are already scalar (F4), so
this must be re-measured if vector lowering lands, because bounds checks can
block vectorization. print_lines is 27 percent slower and alloc_churn 28
percent slower (1 ms absolute). ReleaseSafe would also turn the L49 plain `+`
into a trap when a nonwrap proof is wrong. That changes L49's contract and
needs a decision.

Docs state of this finding: SAFETY_CONTRACT.md lists shift checks and signed
`abs` at the minimum as open work, and README.md:55 says ReleaseFast "does not
establish complete memory safety". PLAN.md A.11 lists "runtime shift counts at
or above operand width" as not reached by the backend review. What is new
here is the conflict with SPEC.md:219-221 and the observed release outcomes.

##### F2. Stdout is fully buffered on a terminal. VERIFIED

L48 says "C-like buffered". C line-buffers a tty. The generated writer uses
one 4096-byte buffer and flushes only when full, before a stderr write, and
when `main` returns.

`$Z/p/tty.a7` prints, runs a 1.8 s loop, prints again. Run on a pty:

```
t+1.83s b'prompt before work\r\nafter work 3000000000\r\n'
```

Both lines arrive together at exit. A progress line or prompt never shows
before the work it announces. Combined with P2-45 (panic drops the buffer) a
crashing program shows no output at all: every panic probe below lost its
earlier `println` lines. Not stated in SPEC.md 1950-1954 or L48.

##### F3. A closed pipe is a panic with a stack trace and a core dump. VERIFIED

`./longprint | head -1` (2M `println` lines):

```
line 0
thread 2965319 panic: a7 stdout write failed
error return context: ... (22 frames of std/Io in debug)
```

`${PIPESTATUS[0]}` is 134 in both profiles. Release prints a 4-line trace.
The shell reports "Aborted (core dumped)" and systemd-coredump stores a core.
C and most tools die silently on SIGPIPE (exit 141). Zig ignores SIGPIPE, so
EPIPE reaches `catch @panic("a7 stdout write failed")`.

Related, same binary (`order.release`):

| case | result |
| --- | --- |
| `>&-` (stdout closed) | `panic: a7 stdout flush failed`, exit 134 |
| `>/dev/full` | `panic: a7 stdout flush failed`, exit 134 |
| `2>&-` (stderr closed) | prints `out 1`, then abort, exit 134, no message, remaining stdout lost |
| `setsid ... <&-` (no tty, no stdin) | normal output, exit 0 |

SPEC.md:1952 states "helpers panic on formatting or write failure". It does
not state the pipe case or the exit code.

##### F4. Loops over arrays are not vectorized by Zig 0.16 ReleaseFast. VERIFIED

`bench/array_walk.a7` sums a `[4096]i32` 300000 times. Emitted Zig:

```zig
var i_1: usize = @as(usize, 0);
while (i_1 < 4096) : (i_1 += 1) {
    total +%= buf[i_1];
}
```

Release assembly is scalar, unrolled 32 times (`objdump -d`, `program.main`):

```
add -0x4114(%rbp,%rdx,4),%r12d
add -0x4110(%rbp,%rdx,4),%r12d
...
```

| build | CPU time |
| --- | --- |
| A7 release | 258 ms |
| C, `clang -O3 -march=native` | 21 ms |
| C, `gcc -O2 -march=native` | 35 ms |
| hand Zig, explicit `@Vector(16, i32)` + `@reduce` (`$Z/vx/w.zig`) | 47 ms |

That is about 12 times the C baseline against an L38 limit of 1.10. It is not
the A7 loop shape: `$Z/vx/v.zig` has four variants (emitted `while`, idiomatic
`for (buf) |v|`, pointer parameter, local array) and none produced a `ymm` or
`zmm` instruction in the loop. The fill loop in the same function is also
scalar. Bounds checks are absent in release, so they are not the cause.

Cause narrowed with two more builds:

| build | `ymm`/`zmm` instructions in the loop function | CPU time |
| --- | --- | --- |
| `zig cc -O3 -march=native array_walk.c` (Zig's bundled LLVM, C source) | 31 | 18.7 ms |
| `v.zig` with `-mcpu=x86_64_v3` | 0 | - |
| `v.zig` with `-mcpu=znver4` | 0 | - |
| `v.zig` with `-mcpu=x86_64_v4` | 0 | - |

The same LLVM vectorizes the C source. Zig source stays scalar on every
target tried. So the cause is in how Zig 0.16 drives LLVM for Zig code, not
the CPU target and not the A7 lowering shape. Whether that is deliberate in
Zig 0.16 was not checked against Zig sources. A different `-mcpu` does not
fix it.

##### F5. Debug allocator costs a page per `new`; no profile reports leaks or double frees. VERIFIED

Preamble: `std.heap.page_allocator` in debug, `std.heap.smp_allocator` in
release (SPEC.md:1308 states this).

| probe | debug | release | C (gcc -O2) |
| --- | --- | --- | --- |
| `manynew.a7`: 100000 live 24-byte boxes, peak RSS | 404776 KB | under 8 MB | under 8 MB |
| `bench/alloc_churn.a7`: 300000 new/del pairs | 913 ms | 4.3 ms | 1.7 ms |

- Leak at exit (`leak.a7`, `new` with no `del`): accepted by the checker,
  exit 0, no report in either profile.
- Double `del` of a field (`p16_del_field_twice.a7`): accepted, exit 0 in both
  profiles. The lowering does not clear the pointer:

  ```zig
  if (h.child) |p| allocator.destroy(p);
  if (h.child) |p| allocator.destroy(p);
  ```

- Use after `del` through an alias (`dbl.a7`: `q := a; del a; q.value`):
  debug segfaults (the page is unmapped), release prints `0`, accepts a write,
  then double-frees silently and exits 0.

`std.heap.DebugAllocator` in the debug profile would report leaks and double
frees and would not spend a page per object. UNVERIFIED: not built here.
The debug time cost (913 ms) is presumably one `mmap` and one `munmap` per
object; syscalls were not counted (no `strace`).

##### F6. No source mapping to A7; DWARF points at a deleted temp directory. VERIFIED

- Zero comments in 102 emitted files (`grep -c '^\s*//'` over 51 examples,
  both profiles). No `.a7` path or line appears anywhere in the Zig.
- `DW_AT_comp_dir` is `.../a7-native-5tcre2xm`, the `tempfile` directory that
  `cli.py` removes after the build. `DW_AT_name` is `program.zig`.
- Panic trace frames for user code have no source line; std frames do:

  ```
  thread 3012101 panic: division by zero
  /tmp/a7-native-13bwdc4_/program.zig:35:20: 0x11d82aa in __a7_user_main (program.zig)
  /tmp/a7-native-13bwdc4_/program.zig:21:19: 0x11d8097 in main (program.zig)
  .../lib/std/start.zig:737:30: 0x11d2a53 in callMain (std.zig)
      return wrapMain(root.main(.{
  ```

  Line 35 is a line of a file the user never sees and cannot open.
- gdb: `break area` fails ("Function not defined"); `break program.area`
  works. `bt` shows `program.area (point=...)`, `program.__a7_user_main ()`.
  `p point` works. `list` fails: `program.zig: No such file or directory`.
  `break 037_language_tour.a7:10` fails: "No source file named".
- A7 function, struct and local names survive unmangled (`area`, `bump`,
  `Point`). A7 `main` becomes `__a7_user_main` when the program does IO, and
  stays `main` when it does not. Print helpers appear as
  `__a7_stdout_print__anon_35698`. Shadowed locals get a numeric suffix
  (`i_1`).
- Release keeps symbols for `program.main` only; user functions are inlined.

##### F7. `main` cannot set an exit code; there is no exit API. VERIFIED

`main :: fn() i32` is rejected: "Executable entry point main must have no
parameters and no return value" (exit 6). A finished program always exits 0.
A panic exits 134 (SIGABRT). A segfault exits 134 in debug (Zig's handler
aborts) and 139 in release. `a7 run` maps a signal death to `128 + N`
(`cli.py:181`), so the same numbers come back. A program cannot report
failure to its caller except by crashing. Not stated in SPEC.md.

##### F8. Release build takes 12 to 20 s for hello world and is never reused. VERIFIED (times indicative)

Fresh `ZIG_GLOBAL_CACHE_DIR`, then two more builds with it warm:

| program | profile | cold | warm 1 | warm 2 |
| --- | --- | --- | --- | --- |
| 001_hello | debug | 2.7 s | 0.36 s | 0.49 s |
| 001_hello | release | 16.6 s | 14.0 s | 12.5 s |
| 037_language_tour | debug | 2.8 s | 0.50 s | 0.47 s |
| 037_language_tour | release | 20.8 s | 17.2 s | 16.6 s |

The Python frontend is about 0.1 s of that. After three builds the cache
`o/` directory held one entry (`libcompiler_rt.a`): the program itself is not
cached, so `a7 run --profile release` pays the full LLVM cost every time.

##### F9. `io.read_line()` with no argument compiles to a no-op. VERIFIED

```a7
main :: fn() { io.read_line()  io.println("done") }
```

emits

```zig
_ = __a7_stdin_read_line(&[_]u8{});
```

It reads nothing and discards the result. With stdin at EOF, with input, and
with stdin closed the program prints `done` and exits 0. Passing a buffer is
rejected (STATUS.md states this). So reading stdin is not reachable and the
EOF contract cannot be probed. The helper dropping input on a second read is
PLAN.md P1-4 and is not re-reported. The new part is the zero-argument call
that the checker accepts.

##### F10. Binaries are large, unstripped, and tuned to the build host. VERIFIED (portability effect UNVERIFIED)

See the table in "Binary and build facts". `cli.py` passes no `-fstrip` and no
`-mcpu`. Zig defaults to the native CPU (`znver5` here). The release hello
binary contains 3484 instructions that use `zmm` or mask registers. A binary
built here can fault on a CPU without AVX-512. Not run on another CPU.

##### F11. Stack overflow on a large local array. VERIFIED

`big: [50000000]i32` in a function (`bigstack.a7`, 200 MB frame): accepted.
Debug: "Segmentation fault at address 0x7ffc..." with a trace, exit 134.
Release: bare SIGSEGV, exit 139, no message. The `println("before")` issued
earlier is lost in both. No size limit or diagnostic at compile time. Not
stated in the docs.

##### F12. Emitted code, style level. VERIFIED

Counts are over the 51 examples, release profile.

- `zig fmt --check`: clean on all 102 files. `zig ast-check`: clean on all 102.
- `var` that should be `const`: none. Zig rejects a never-mutated `var` in
  AstGen, which `ast-check` runs, and all 102 files pass. Unused labels: none
  for the same reason.
- Preamble is per-need: programs without IO get no header, `allocator` is
  emitted in 2 files (both use `new`), `__a7_stderr_print` in 0. No unused
  preamble helper found in the 51 examples.
- Redundant parentheses on every binary expression: 20 `return (...);` and 16
  `= (...);` lines, 3 `arr[(j + 1)]`. Example: `return ((value / total) * 100.0);`.
- Redundant `@as` on a typed declaration, 6 occurrences in 5 files:
  `var i: usize = @as(usize, 0);`, and
  `var stack: [3]usize = .{ @as(usize, 0), @as(usize, 0), @as(usize, 0) };`.
- Type written twice: `const boxed: Box(i32) = Box(i32){ .value = number };`.
- `.?` unwrap on every use. 100 of the 104 occurrences are the two preamble
  globals (`__a7_io: ?std.Io`, `__a7_stdout_writer: ?std.Io.File.Writer`),
  which are set once at the top of `main` and unwrapped on every print. They
  could be non-optional `undefined` globals. The other 4 are heap refs:

  ```zig
  var heap_value = allocator.create(HeapBox) catch null;
  if (heap_value == null) { ...; return; }
  defer if (heap_value) |p| allocator.destroy(p);
  heap_value.?.value = 99;
  __a7_stdout_print("heap = {}\n", .{heap_value.?.value});
  ```

  One `orelse return` at the check would give a plain `*HeapBox`. No cost in
  ReleaseFast; a check per use in debug.
- Error handling: `catch @panic(...)` in the print helpers (2 per file), no
  `catch unreachable`, `catch null` for allocation (2 files).
- `_ = x;` appears for an unused A7 local (`const dead: i32 = (a *% 2); _ = dead;`)
  and an unused parameter becomes `_: i32`. The A7 compiler prints no warning
  for either, so the discard hides a dead value from the user. None occur in
  the 51 examples.
- C-style `for` gets an extra block scope each time (16 `while (...) : (...)`
  loops, each wrapped in `{ var i ...; while ... }`). Needed for scoping; noisy
  when nested three deep (`029_sorting`).
- The `fall` flag machine (046, one file, 22 flag uses). Five cases emit two
  booleans, ten `if`s, and a dead statement after an unconditional `break`:

  ```zig
  if (__a7_match_fall_3) __a7_match_case_3_4: {
      __a7_match_fall_3 = false;
      {
          __a7_stdout_print("B: good\n", .{});
          __a7_match_fall_3 = true;
          break :__a7_match_case_3_4;
      }
      if (!__a7_match_fall_3) __a7_match_done_2 = true;   // unreachable
  }
  ```

  LLVM removes all of it in release (see lowering section). Zig 0.16 labeled
  `switch` with `continue :sw .next` expresses `fall` directly.
- `switch` arms that only return use statement form with a block per arm
  (`1 => { return "low"; },`), 19 switches in 12 files. Readable, verbose.
- Release differs from debug only in the allocator line and `+%`/`+`. 75 `+%`,
  `-%`, `*%` remain in release across 25 files (unproven sites).

---

#### Runtime contract table

"Docs" means SAFETY_CONTRACT.md, SPEC.md, STATUS.md or README.md states the
runtime outcome. **Bold** marks release silently wrong where debug traps.

| # | Case | Debug | Release | Docs |
| --- | --- | --- | --- | --- |
| 1 | `+ - *` overflow, unproven (`ovf.a7`, operands from parameters) | wraps: `-2147483648`, `2147483647`, `0`, `u8 250+10=4` | same | Yes (wrapping, SPEC 2439) |
| 2 | `+ - *` proven nonwrap sites | `+%` | plain `+`; UB if the proof is wrong. No wrong proof found in this audit | Yes (L49) |
| 3 | Index out of bounds past a stale guard (`saf6i.a7`, global changed by a call, SAF-6 shape) | panic `index out of bounds: index 4000, len 4`, 134 | **SIGSEGV 139, no message** | Gap listed (SAF-6); outcome not stated |
| 4 | Division by zero past a stale fact (`saf6.a7`) | panic `division by zero`, 134 | **prints `10 / g = 2`, exit 0** | Gap listed; outcome not stated |
| 5 | Modulo by zero, same shape (`saf6m.a7`) | panic, 134 | **prints `10 % g = 0`, exit 0** | Gap listed; outcome not stated |
| 6 | Division by zero through `fall` (`saf3.a7`, SAF-3 shape) | panic, 134 | **prints `0`, exit 0** | Gap listed; outcome not stated |
| 7 | Signed `>>` (`shr(-8, 1)`) | `-4` (arithmetic) | `-4` | No |
| 8 | `1 << 31` on `i32`, `-1 << 1` | `-2147483648`, `-2` | same | No |
| 9 | Shift count >= width or negative (`shift2.a7`) | panic `integer does not fit in destination type`, 134 | **SIGSEGV 139, or endless newline output (`shift.a7`)** | Conflict: SAFETY_CONTRACT lists the gap, SPEC 219 says fail-closed; outcome not stated |
| 10 | Narrowing cast, unguarded (`cast(u8, i32)`) | rejected, exit 6 | rejected | Yes |
| 11 | Narrowing cast, guarded | correct | correct | Yes |
| 12 | Float to int cast, runtime value | rejected, exit 6 | rejected | Yes |
| 13 | Float division, unguarded | rejected, exit 6 | rejected | Yes |
| 14 | `MIN / -1`, unary `-MIN` | P2-43, P2-44 | P2-43, P2-44 | not re-tested |
| 15 | `math.abs(i32 min)` (`absmin.a7`) | panic `integer does not fit`, 134 | **endless newline output** | STATUS and SAFETY_CONTRACT name the gap, not the outcome |
| 16 | `usize` `0 - 1` (`idx(0)`) | `18446744073709551615` | same | Yes (wrapping) |
| 17 | Nil deref | no accepted escape found in 9 attempts (`nil*.a7`, `nilg.a7`, p06, p08); field refs are never provable. By lowering, `.?` panics | by lowering, UB | UNVERIFIED at run time |
| 18 | Double `del` of a local | rejected, exit 6 | rejected | Yes |
| 19 | Double `del` of a field (`p16`) | exit 0, no report | **exit 0, no report (double free)** | Gap listed (SAF-8); outcome not stated |
| 20 | Use after `del`, direct | rejected, exit 6 | rejected | Yes |
| 21 | Use after `del` via alias, then second `del` (`dbl.a7`) | segfault with trace, 134 | **reads `0`, writes, double-frees, exit 0** | SAFETY says alias analysis incomplete; outcome not stated |
| 22 | Leak at exit (`leak.a7`) | exit 0, no report | exit 0, no report | No |
| 23 | 200 MB local array (`bigstack.a7`) | segfault with trace, 134 | SIGSEGV 139, no message | No |
| 24 | Allocation failure (`oom.a7` under `ulimit -v 2000000`) | `new` gives nil; prints `alloc failed after 243`, exit 0 | same | Yes (SPEC 1304) |
| 25 | stdin at EOF | `io.read_line()` is a no-op, exit 0 | same | Reading not reachable (STATUS) |
| 26 | `prog \| head -1` | panic `a7 stdout write failed`, long trace, 134, core | same, short trace, 134, core | Panic stated; pipe case and code not |
| 27 | stdout closed or `/dev/full` | panic `a7 stdout flush failed`, 134 | same | Partly (SPEC 1952) |
| 28 | stderr closed | abort 134, no message | same | No |
| 29 | Exit code of `main` | always 0; `main` cannot return a value | same | No |
| 30 | Exit code of a panic | 134 | 134 (trap cases 139) | No |
| 31 | stdout/stderr order (`order.a7`) | `out 1, err 1, out 2, err 2, out 3` through a pipe and into a file with `2>&1`; not run on a tty | same | Yes (L48) |
| 32 | No terminal (`setsid`, stdin closed) | normal, exit 0 | same | No |
| 33 | Output on a tty | fully buffered until exit or 4096 bytes | same | No (L48 says "C-like") |
| 34 | Output before a panic | lost (P2-45) | lost | P2-45 |
| 35 | Inactive bare-union field read (p22) | Zig build error, exit 7 | same | STATUS says union proofs incomplete |

Release-silent rows: 3, 4, 5, 6, 9, 15, 19, 21.

Other probes that hit known rows: `del p` with a local named `p` (P2-46), a
loop variable named `i2` (P2-47, "name shadows primitive").

---

#### Binary and build facts

`zig build-exe program.zig -O {Debug|ReleaseFast} -femit-bin=...`, no other
flags (`cli.py:167-171`).

| binary | size | `strip`ped size | text | link | libc | debug info |
| --- | --- | --- | --- | --- | --- | --- |
| 001_hello debug | 10,262,605 | 2,676,384 | 2,266,465 | static | none | yes, not stripped |
| 001_hello release | 3,824,992 | 546,408 | 525,759 | static | none | yes, not stripped |
| 037_language_tour debug | 10,280,824 | 2,690,048 | 2,280,833 | static | none | yes, not stripped |
| 037_language_tour release | 3,853,640 | 552,824 | 532,170 | static | none | yes, not stripped |

- `file`: "ELF 64-bit LSB executable, x86-64, statically linked, with
  debug_info, not stripped". `ldd`: "not a dynamic executable". No dynamic
  section.
- Half a megabyte of text for hello world in release is Zig `std.Io` plus the
  panic and DWARF unwinder.
- Cache: Zig's global cache, `~/.cache/zig` (2.3 GB on this box). No
  `.zig-cache` appears in the cwd or beside the output. `a7` sets no cache
  flag. `ZIG_GLOBAL_CACHE_DIR` is honoured.
- Build times: see F8.
- Concurrent builds: UNVERIFIED by running (builds were kept sequential). By
  reading `cli.py`: each build uses a unique `tempfile.TemporaryDirectory`
  and `os.replace`, so two builds do not share paths; two builds to the same
  `-o` leave whichever finished last. The shared cache is Zig's own.
- `a7 build` creates `a7-native-XXXX/` next to the output and removes it.
  `a7 run` creates it under the system temp dir (`/tmp/a7-native-XXXX`).
  After a normal `a7 run`, `ls -d /tmp/a7-native-*` was empty and the cwd was
  empty. If `a7` is killed with SIGKILL the directory stays. UNVERIFIED.
- `a7 build` default output is `./<stem>` in the cwd, which may be the source
  directory.

---

#### Lowering efficiency

Release CPU time against C (`clang -O3 -march=native`, `gcc -O2 -march=native`).
Outputs matched in every case.

| kernel | A7 release | clang | gcc | A7 / best C |
| --- | --- | --- | --- | --- |
| bench/array_walk | 258.0 ms | 21.3 ms | 34.5 ms | 12.1 |
| bench/sort_load | 241.5 ms | 214.6 ms | 213.3 ms | 1.13 |
| bench/alloc_churn | 4.3 ms | 2.0 ms | 1.7 ms | 2.5 (tiny absolute) |
| bench/print_lines | 15.3 ms | 41.3 ms | 40.2 ms | 0.38 |
| fallk (`fall` in a 200M loop) | 86.2 ms | 165.8 ms | 206.3 ms | not comparable (C `score` was `noinline`) |

Per pattern:

- `for`/`while` over arrays: no bounds checks in release (ReleaseFast). Debug
  checks every access. Loops are not vectorized (F4).
- Struct by value: `fn ends(b: Big) i64` takes the struct as a Zig value
  parameter; `c := a` becomes `const c = a;`. `bigval.a7` (2 KB struct, 20M
  iterations) ran in 0.7 ms: LLVM removed the copies and the loop. Copy cost
  under a non-foldable workload: not measured.
- `ref` parameters: `*T`, call sites pass `&x`. No overhead.
- Slices: `numbers[1..4]`, native Zig slices.
- `io.println`: format string is `comptime`, parsed at compile time. One
  helper instantiation per distinct format (13 for the tour's 15 call sites
  in debug). One 4096-byte buffer, flushed when full and at exit. Faster than
  `printf` here (0.38). Cost is code size, not time.
- `match`: equality-only arms become a native `switch`, including ranges
  (`4...9`) and multi-value arms. Captures and `fall` use the if-chain.
- `fall` flag machine: all flags vanish in release; `score` was inlined and
  the loop ran faster than the C version. No runtime cost found. Cost is
  debug speed and readability only.
- Generics: `fn identity(comptime T: type, value: T) T` and
  `fn Box(comptime T: type) type`. Zig instantiates per type. No runtime cost.
- `defer`: native Zig `defer`. `defer del x` becomes
  `defer if (x) |p| allocator.destroy(p);`.
- `new`: one `allocator.create` per call. Release `smp_allocator` is about
  2 times glibc `malloc` on the churn kernel (4.3 ms vs 1.7 to 2.0 ms for
  300000 pairs). Debug: F5.
- Zero-init arrays: `var buf: [4096]i32 = [_]i32{0} ** 4096;` becomes one
  `memset`.

##### Three lowering changes for the L38 1.10x target

1. **Emit explicit vector code for recognized loops over fixed arrays**
   (reductions and elementwise updates), or find a build setting that makes
   Zig 0.16 vectorize. Evidence: array_walk is 12.1 times C; four hand-written
   scalar shapes all stay scalar; a hand-written `@Vector(16, i32)` reduction
   drops 258 ms to 47 ms. The backend already has `_emit_array_vector_expr`
   for whole-array operators. `zig cc` on the C source vectorizes with the
   same LLVM (18.7 ms) and three other `-mcpu` targets do not help, so a
   build flag is unlikely to be enough. This is the only measured gap of an
   order of magnitude. aos_walk, soa_walk, stride_walk and vector_ops have the same
   loop shape; not measured here.
2. **Allocation path.** Release `smp_allocator` is 2.1 to 2.5 times `malloc`
   on new/del churn. Startup is not the cause: hello world is 0.6 ms for A7
   release against 0.5 ms for C, and the churn gap is 2 ms over 300000 pairs. L38 also limits peak memory. Debug is outside L38 but
   uses 4 KB per object. Evidence: alloc_churn and manynew above. Candidates:
   a size-class or arena allocator chosen by the memory plan (L15-L21),
   `DebugAllocator` for debug. The gap is small in absolute terms; it matters
   only for allocation-heavy workloads.
3. **Give LLVM range and no-overflow facts in the hot loops that stay
   scalar.** sort_load is 1.13 times C, just over the limit. The emitted
   fill loop is
   `s[j] = (@rem(((@as(i32, @intCast(j)) * 7) +% (r *% 13)), 251) -% 125);`
   and the scan loops use `usize` counters with proven plain `+`. Evidence is
   weak: one kernel, 13 percent, on a noisy box, and the cause was not
   isolated in the assembly. Treat this as the next thing to measure, not as
   a proven lever.

Not levers (no release cost found): `.?` unwraps, bounds checks, the `fall`
flag machine, generic instantiation, `defer`, print formatting.

---

#### Not done

- No instruction counts or syscall counts (`perf`, `strace` not installed).
- Peak memory against C not measured below 8 MB; no allocation or copy counts.
- Concurrent `a7 build` runs not executed (sequential-build rule).
- Nil deref at run time: no accepted program reached one.
- `MIN / -1`, unary `-MIN`, uninitialized reads: left to P2-42 to P2-44.
- aos_walk, soa_walk, stride_walk, vector_ops, arith_loop, kv_append not
  compared against C.
- sort_load's 13 percent gap not explained from the assembly.
- Large-struct copy cost not measured (the probe was optimized away).
- `DebugAllocator` and `-fstrip` not tried. Portability of the native-CPU
  binary not tested on another machine.
- Whether Zig 0.16 disables the LLVM loop vectorizer on purpose was not
  checked against Zig sources or issues; only the output was observed.
- A fixed-path release rebuild was not timed, so it is not shown whether an
  a7-side cache keyed on the emitted Zig would be the fix for F8.
- PLAN.md grew from 443 to 1080 lines during this audit. Overlap was checked
  by grep only (P1-4, P2-52, A.11 found and referenced).
- Multi-module emission (`module_a_b__f` names) not reviewed beyond P2-48.
- Only gdb was tried; lldb is not installed.
- Abort probes left core dumps in systemd-coredump before `ulimit -c 0` was
  added to the run script (about a dozen small cores).

## Appendix G: Modules end to end (full report)

Embedded copy of `reports/modules.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Module/import audit, 2026-10-04

Scope: end-to-end probes of multi-file programs. Every cell is a real
project compiled with `uv run a7 <entry> -o out.zig` and run with
`zig run out.zig` (Zig 0.16.0). No repo file was edited. No pytest or
gate ran.

Probe root (`$S`):
`/tmp/claude-1000/-home-cx89-Projects-pl-dev-a7-py/fa2805be-328b-45b2-a1df-ab981ee81691/scratchpad/modules/`
Harness: `$S/run.sh <cell-dir> [entry.a7]`. Cell directories are named
in each finding.

Labels: WRONG = wrong result at run time. ZIG = a7 exits 0, Zig fails.
REJ = valid program rejected. ACC = invalid program accepted.
CRASH = exit 8. CONTRA = contradicts L25-L31 or SPEC.
"known" = on the do-not-re-report list; listed for the matrix only.

#### How merging works (read from code, confirmed by probes)

- `compile.py:894-926` concatenates every module's declarations in
  front of the entry's. Import declarations of non-entry modules are
  dropped (`:914`).
- Only FUNCTION declarations get `module_<path>__` (`:916-917`).
  Structs, enums, unions, constants, globals and type aliases keep
  their plain names in one shared scope.
- Only CALL nodes are rewritten (`:797-808`, `:810-824`). No other use
  of `alias.name` or of a sibling function name is rewritten.
- The type checker looks up an alias call by plain callee name in the
  global scope (`type_checker.py:1998-2005`). The alias is not used to
  pick the module.
- The merge and call rewrite run only in compile, pipeline and doc
  modes (`compile.py:328-329`).

Most findings below follow from these five facts.

#### Ranked findings

##### F1. WRONG (working tree only): qualified call binds to another module's same-named function

Attribution: this is P0-3 (overload coexistence) reaching modules. At
HEAD (exported with `git archive HEAD` into `$S/head`, run with the
repo venv) every cell in this finding exits 6 `Already defined:
Function 'c'` (the known shared namespace, P2-8). In the working tree
same-named functions from two modules coexist in the one flat scope,
the module prefix keeps the Zig members apart, and the build succeeds
with the wrong signature. P0-3 is recorded in PLAN.md as a Zig build
failure only; with modules it is a silent wrong result. This supports
D-B option (1), or needs the checker lookup below fixed first.

`a.c()` is typed with `b.c`'s signature when both modules export `c`.
Print formatting follows the wrong type.

```
// sig2/a.a7
pub c :: fn() char { ret 'A' }
pub w :: fn() i32 { ret 7 }
// sig2/b.a7
pub c :: fn() u8 { ret 66 }
pub w :: fn() i64 { ret 5000000000 }
// sig2/main.a7
io :: import "std/io"
a :: import "a"
b :: import "b"
main :: fn() {
    io.println("{} {}", a.c(), b.c())
    x := a.w()
    y := b.w()
    io.println("{} {}", x, y)
}
```

`run.sh sig2`: a7 0, zig 0, prints `65 66`. With only `a` imported
(`sig2/only_a.a7`) the same `a.c()` prints `A`.

Same root, other outcomes:

- ZIG, import order swapped (`sig2/main_rev.a7`):
  `const y: i32 = module_b__w();` then `expected type 'i32', found 'i64'`.
- REJ (`sig/main.a7`): `a.g(1)` with `a.g(x: i32)` and `b.g(s: string)`
  exits 6 `Argument type mismatch: expected 'string', got 'i32'`.
- REJ (`ov/main3.a7`): `a.g()` vs `b.g(s: string)` exits 6
  `Wrong number of arguments (Expected 1 arguments, got 0)`.
- ACC then ZIG (`sig/main_bad.a7`): `a.g("oops")` exits 0; Zig rejects.
- Order dependence (`sig/main_ret.a7` exits 6, `sig/main_ret2.a7` with
  the two imports swapped runs and prints `1 2.5`).
- REJ (`ov/main6.a7`): module `main :: fn(x: i32) i32` called as
  `mm.main(4)` exits 6 `Expected 0 arguments, got 1`; it is checked
  against the entry's `main`.

Cause: `type_checker.py:1998-2005` picks whichever same-named symbol
the global scope holds.

HEAD comparison for the other cells: `same/main.a7` (two `util.a7`
both exporting `who`, same signature) prints `1 2` in the working tree
and exits 6 `Already defined` at HEAD. `ov/main5.a7` (module `main`)
runs in the working tree and exits 6 at HEAD.

##### F2. ZIG (also at HEAD): `alias.f()` accepted when `f` lives in a different module or in the entry

```
// wm/a.a7
pub fa :: fn() i32 { ret 1 }
// wm/b.a7
pub fb :: fn() i32 { ret 2 }
// wm/main.a7
io :: import "std/io"
a :: import "a"
b :: import "b"
main :: fn() { io.println("{}", a.fb()) }
```

a7 0; Zig: `use of undeclared identifier 'module_a__fb'`.
`wm/main2.a7`: `a.local()` where `local` is an entry function, same
result (`module_a__local`). Same lookup as F1, but independent of P0-3: HEAD gives the same
result for both cells. The existing pin
`test_missing_callee_in_imported_module_is_rejected` only covers a name
defined nowhere.

##### F3. REJ: a module cannot use an import alias the entry does not also declare

Non-entry import declarations are dropped in the merge, so the module's
own aliases are undefined at name resolution. Same at HEAD.

```
// stdmod/lib.a7
console :: import "std/io"
pub hello :: fn() { console.println("hello from lib") }
// stdmod/main.a7
io :: import "std/io"
l :: import "lib"
main :: fn() {
    l.hello()
    io.println("main")
}
```

a7 exits 6: `Undefined type (Identifier 'console') [line 2: col 21]`
(3 errors). Variants:

- `stdmod2/main.a7`: lib uses `io :: import "std/io"`, entry imports no
  io at all. Exit 6 `Identifier 'io'`. A library that prints only
  works when the entry happens to declare the same alias for the same
  stdlib module.
- `stdmod2/main2.a7`: entry has `io :: import "std/math"`, lib has
  `io :: import "std/io"`. Exit 6
  `Stdlib module 'std/math' has no function 'println'`. The module's
  `io` resolves to the entry's alias.
- `chain2`: `c :: import "c"` then `ret c.K` inside `b.a7` exits 6
  `Identifier 'c'`. Same for a global (`init/main3.a7`, `q: i32 = c.base`).
  P-MOD recorded this as `iso_const`; it is still current. Calls
  through the alias (`c.cf()`) work.

Test gap: every multi-file test uses `io` in the entry only.

##### F4. ZIG: every non-call use of `alias.name` from the entry

All exit 0 in a7 and in `a7 check`; Zig fails with
`use of undeclared identifier 'm'`. `use/lib.a7` is the module.

| Use | Cell | a7 | Zig |
| --- | --- | --- | --- |
| `m.LIMIT` (constant) | `use/const_q.a7` | 0 | fails |
| `m.counter` (global read) | `use/global_read_q.a7` | 0 | fails |
| `f: fn(i32) i32 = m.dbl`, `apply(m.dbl, 5)` | `use/fnptr_q.a7` | 0 | fails |
| `x := h` (alias as a value) | `place/main6.a7` | 0 | fails |
| `h.v` (function not called) | `place/main7.a7` | 0 | fails |

Minimal:

```
// use/lib.a7 (excerpt)
pub LIMIT :: 42
// use/const_q.a7
io :: import "std/io"
m :: import "lib"
main :: fn() { io.println("{}", m.LIMIT) }
```

Related REJ: `m.counter = 5` (`use/global_write_q.a7`) exits 6
`Assignment type mismatch: expected 'unknown type', got 'i32'`.

HEAD gives the same results for `const_q` and `fnptr_q`. The working
spelling today is the unqualified leaked name (`LIMIT`, `counter`,
`Vec`); that leak is the known P2-8, not a new finding.

##### F5. ZIG: a function used as a value has no working spelling across files

- Entry, bare name (`use/fnptr_bare.a7`): `f: fn(i32) i32 = dbl` exits
  0; Zig: `undeclared identifier 'dbl'`.
- Entry, selected import (`use/sel_fnptr.a7`,
  `import "lib" { dbl }`): same.
- Inside the module itself (`in/lib_fnptr.a7`):

```
pub dbl :: fn(a: i32) i32 { ret a * 2 }
pub apply :: fn(f: fn(i32) i32, x: i32) i32 { ret f(x) }
pub useit :: fn() i32 {
    f: fn(i32) i32 = dbl
    ret f(4) + apply(dbl, 1)
}
```

  with `in/main_fnptr.a7` calling `l.useit()`: a7 0, Zig
  `undeclared identifier 'dbl'`. A file that runs as an entry stops
  building once it is imported.

Cause: sibling rewrite covers CALL nodes only (`compile.py:810-824`).
Same at HEAD.

##### F6. ZIG: one file reached under two spellings from different importers

L26 allows different files to import the same module. The merge keeps
one copy (first spelling's prefix); the other importer's calls use the
other spelling's prefix.

```
// dia2/d.a7
pub hits: i32 = 100
pub touch :: fn() i32 {
    hits += 1
    ret hits
}
// dia2/b.a7
d :: import "d"
pub fb :: fn() i32 { ret d.touch() }
// dia2/c.a7
d :: import "./d"
pub fc :: fn() i32 { ret d.touch() }
// dia2/main.a7
io :: import "std/io"
b :: import "b"
c :: import "c"
main :: fn() {
    x := b.fb()
    y := c.fc()
    io.println("{} {}", x, y)
}
```

a7 0; Zig: `undeclared identifier 'module___d__touch'`. Same with a
symlink (`dia4`, `module_dlink__touch`) and with `"pkg"` vs `"pkg/mod"`
(`pk`, `module_pkg__g`). Cause: `load_module` caches by spelling
(`module_resolver.py:181`), merge dedupes by file path
(`compile.py:909-912`).

Same at HEAD (`dia2`).

Side effect in the cycle message (`cyc3`, `c.a7` imports `"./a"`):
`Circular dependency detected: a -> b -> c -> ./a -> b`. The cycle is
found one lap late and the chain shows `a` twice under two names.

##### F7. REJ: `--mode semantic` rejects every program that calls a file module

`uv run a7 $S/chain/main.a7 --mode semantic` exits 6:
`Type is not callable (Unknown stdlib call 'b.bf')`. The same file
compiles and prints `42 3`. Bare leaked names also fail in this mode
(`use/const_bare.a7`: `Undefined type (Identifier 'LIMIT')`).
Cause: merge and call annotation are skipped outside
compile/pipeline/doc (`compile.py:328-329`). P-MOD acceptance item 7
asks for one module graph in all modes. Same at HEAD.

##### F8. CONTRA L27, L28: rules not implemented

- L27 `_name` private: not enforced. `ni/priv_fn.a7` calls `h._priv()`
  and `h._hidden()`, prints `8 9`. `ni/priv_const.a7` reads bare
  `_SECRET`, prints `5`.
- L27 `__name` reserved: not enforced at top level, local, or alias
  (`ni/dunder_top.a7`, `dunder_local.a7`, `dunder_alias.a7` all run).
  Real clashes reach Zig:
  - `ni/dunder_clash.a7`: `__a7_stdout_print :: fn() i32 { ret 1 }`
    exits 0; Zig `duplicate struct member name '__a7_stdout_print'`.
  - `ni/dunder_clash2.a7`: entry defines `module_h__value` beside
    `h :: import "h"` with `value`; a7 0; Zig
    `duplicate struct member name 'module_h__value'`. The emit prefix
    is not in the reserved `__` space.
- L28 local vs alias: accepted. `ni/local_shadow.a7` (`h := 9`) prints
  `9`. `ni/param_shadow.a7` (parameter `h`) prints `2 7`. Only
  top-level clashes exit 6 (`alias_global*.a7`, `alias_fn.a7`,
  `alias_two.a7`).

##### F9. ZIG: non-ASCII module name

`names/módulo.a7` + `q :: import "módulo"`: a7 0; Zig
`pub fn module_módulo__val()` then `expected '(', found invalid bytes`.
`str.isalnum()` keeps non-ASCII letters (`compile.py:705`).
Dash, dot, space, uppercase, leading digit, and the names `error`,
`type`, `u1`, `std`, `fn`, `match`, `i32`, `comptime`, `test`, `main`
all build and print `7`, both as file names and as aliases
(`names/k_alias.a7`, `k_alias2.a7`).

##### F10. Diagnostics from a module name no file in human output

Chain `main -> b -> c`, error on line 4 of `c.a7`
(`diag/`, entry padded so line numbers differ):

| Error in c.a7 | Exit | JSON `file` | JSON message prefix | Human output |
| --- | --- | --- | --- | --- |
| tokenize (open string) | 4 | c.a7 | `c.a7:4:6` | line/col + c.a7 source, no file name |
| parse (`fn( { }`) | 5 | c.a7 | `c.a7:4:16` | same |
| name (undefined ident) | 6 | c.a7 | `c.a7:4:27` | same |
| type (ret string as i32) | 6 | c.a7 | `c.a7:4:23` | same |
| validator (recursion) | 6 | c.a7 | `c.a7:4:5` | same |
| safety (divisor, index) | 6 | c.a7 | `c.a7:4:41` | same |
| codegen (`fall` in tag arm) | 7 | **main.a7** | `c.a7:14:13` | `✗ c.a7:14:13: ...` |
| missing import inside c | 3 | c.a7 | `c.a7:1:1` | no file name |

Stage, line and source excerpt are right in every row. Two defects:

- Human format prints `[line 4: col 27]` and the excerpt but never the
  file. With several files the reader has to recognize the excerpt.
- Codegen errors: JSON `details[0].file` is the entry path while the
  message says `c.a7`; `span` is null. `docs/STATUS.md:13` says
  "Diagnostics retain module origins", so this row is doc/code drift.

##### F11. REJ: an entry function sharing a name with a module function

```
// ov/m.a7
pub f :: fn(x: i32) i32 { ret x * 100 }
pub callf :: fn() i32 { ret f(2) }
// ov/main2.a7
io :: import "std/io"
m :: import "m"
f :: fn(x: i32) i32 { ret x + 1 }
main :: fn() { io.println("{} {} {}", f(3), m.f(3), m.callf()) }
```

Exit 6: `'f' is defined in the module imported as 'm'; write 'm.f()'`.
The entry's own `f` is unreachable. At HEAD the same project exits 6
`Already defined: Function 'f'` (verified). Both are the known shared
namespace (P2-8); the working tree changes only the message, and the
new message tells the user to call the wrong function.

##### F12. Selected imports are not a filter and are not validated (ACC)

- `use/sel_missing.a7`: `import "lib" { Nope, alsoNope }` exits 0, runs.
- `use/sel_unlisted.a7`: `import "lib" { Vec }` then uses `Color`,
  `LIMIT`, `counter`; exits 0, prints `42 10`.
- Bare `import "lib"` is the same: every non-function name is in scope
  (`use/bare_types.a7` prints `1 5 42 11`). The leak itself is the
  known P2-8; the new part is that the item list is never checked.

SPEC 10.2 calls selected imports "resolver-side metadata only"; it does
not say the item list is unchecked.

##### F13. Lower-rank notes

- `ov/main5.a7`: a module may define `main`; `mm.main()` runs it. No
  rule in SPEC 10.2.2 covers a module `main` being callable.
- L31: `import "io"` picks the stdlib over a local `io.a7`
  (`l31/main.a7`, prints `std wins`). `io :: import "./io"` does load
  the local file (`l31/main2.a7`, prints `3`). L31 says such files
  "cannot be imported"; state whether `./io` is the allowed escape.
- Unaliased or selected stdlib import gives no usable name:
  `import "std/io"` then `io.println` exits 6 (`use/std_unaliased.a7`);
  `import "std/io" { println }` then `println("x")` exits 6
  (`use/std_selected.a7`).
- Hardlink to the same file is a second module (`esc/proj/main4.a7`,
  prints `2 2`), not a duplicate import. P-MOD item 4 asks for a stated
  policy.
- `<entry>/stdlib/` is a search path: `import "foo"` finds
  `stdlib/foo.a7` when no `foo.a7` sits beside the entry; the entry
  directory wins when both exist (`esc/proj/main3.a7`). SPEC 10.2.1
  lists the order; the bundled `stdlib/` directory it names does not
  exist in the repo.
- `pkg.a7` beside `pkg/mod.a7`: `"pkg"` silently picks `pkg.a7` (`pk`
  second run, prints `2 1`). Same family as known `dup` vs `dup/`.
- `--lib` output drops `pub` on types, constants and globals
  (`use/lib_out.zig`: `const Vec = struct`, `var counter`); functions
  keep it.
- `a7 build --lib` is a usage error (exit 2); SPEC 10.2.2 says so.
- Global whose initializer reads another runtime global
  (`derived: i32 = base + K`) exits 0 and fails Zig
  (`initializer of container-level variable must be comptime-known`).
  This reproduces in a single file (`single/main.a7`), so it is not a
  module defect; it does block cross-module global initializers
  (`init/main.a7`).

#### Matrix

P = builds and prints the expected output. Other cells give the label
and finding. "known" cells are on the do-not-re-report list.

##### Import forms

| Form | Result |
| --- | --- |
| `m :: import "x"` + call | P (`use/call.a7`) |
| bare `import "x"`, call `add()` | exit 6 by design, names the alias rule |
| bare `import "x"`, types/consts/globals | P, all names leak (F12) |
| selected, types and constants | P (`use/sel_types.a7`) |
| selected, unlisted or missing items | ACC (F12) |
| selected, function call | known |
| selected, function as value | ZIG (F5) |
| `using import` | known (exit 5) |
| `pub m :: import` | P, `pub` dropped (known) |
| `console :: import "std/io"`, `mth :: import "std/math"` | P |
| `io :: import "io"`, `math :: import "math"` | P |
| `std :: import "std/io"` | P |
| `io` + `io2` for the same stdlib module | exit 6 duplicate, per L26 |
| stdlib alias inside a non-entry module | REJ (F3) |

##### Use through alias `m` (entry file)

| Use | Qualified `m.X` | Bare leaked `X` |
| --- | --- | --- |
| function call | P | exit 6 by design |
| generic function call | P (`m.identity(7)`) | exit 6 by design |
| struct type in declaration | known (exit 5) | P |
| struct value via `v := m.mk(3)` | P | - |
| struct literal | known gap (exit 5 `Expected type`) | P |
| generic struct `m.Box(i32){...}` | exit 5 `Expected type` (same gap) | P |
| enum variant `m.Color.Green`, `case m.Color.Red` | exit 5 `Expected COLON, got DOT` (same gap) | P |
| tagged union literal `m.Res{ok: 5}` | exit 5 (same gap) | P |
| tagged union from `m.mkres(5)` + `.ok(v)` match | P | P |
| constant | ZIG (F4) | P |
| global read | ZIG (F4) | P |
| global write | REJ exit 6 (F4) | P (`77 77`) |
| global through module functions | P (`12`) | - |
| type alias `h: m.Handle` | exit 5 (same gap) | P |
| function pointer | ZIG (F4) | ZIG (F5) |
| module fn calls sibling and `_helper` | P (`42`) | - |
| module fn takes own sibling as value | ZIG (F5) | - |
| module fn: match on own union/enum, generic struct param, `ref` forwarding | P (`in/main_match.a7`: `4 -3 2 8 7`) | - |

##### Topologies

| Topology | Result |
| --- | --- |
| chain A->B->C, calls | P (`42 3`) |
| chain, generic calls B->C and A->C | P (`gch`: `7 2.5 s`) |
| chain, B reads `c.K` or `c.base` | REJ (F3) |
| entry reaches C through B (`c.cf()`, `b.c.cf()`) | exit 6; no re-export, as P-MOD wants |
| diamond, same spelling, global in D | P (`101 102`); one `var hits`, initialized once |
| diamond, `d` vs `./d`, symlink, `pkg` vs `pkg/mod` | ZIG (F6) |
| `sub/../x` | exit 3 (`..` rejected; L30 partly, see rules) |
| cycle of 2 | exit 6 `a -> b -> a` |
| cycle of 3 with one `./` spelling | exit 6, chain text wrong (F6) |
| cycle through the entry | exit 6 `a -> main -> a` |
| self-import, entry and module | exit 6 `main -> main`, `m -> m` |
| `geo/mod.a7` as `"geo"`; `"geo/shapes/circle"`; `"util/num"` | P (`6 9 4`) |
| `"geo"` and `"geo/mod"` in one file | exit 6 duplicate |
| nested importer, sibling by bare name or `./` | known (entry-dir resolution), exit 3 |
| nested importer, `../geo` | exit 3 (`..` rejected) |
| entry in a subdirectory, local sibling | P |
| entry in a subdirectory, parent via `../geo` or `geo` | exit 3 |
| two `util.a7` in `a/` and `b/` (both export `who`) | P (`1 2`) in the working tree; exit 6 at HEAD |
| names `error`, `type`, `u1`, `std`, `fn`, `match`, `i32`, `comptime`, `test`, `main` | P |
| names with dash, dot, space, uppercase, leading digit | P |
| unicode name | ZIG (F9) |
| symlink file or directory leaving the entry folder | exit 3 `not found` |
| hardlink | second module (F13) |
| 1,200-module chain | P (`1199`), 1.6 s, no recursion error |

##### Name interactions

| Case | Result |
| --- | --- |
| local shadows alias | ACC, CONTRA L28 (F8) |
| parameter shadows alias | ACC, CONTRA L28 (F8) |
| alias vs global, function, second alias | exit 6 `Already defined` |
| two modules export `who` with the same signature | P (`1 2`) in the working tree; exit 6 `Already defined` at HEAD |
| two modules export a name with different signatures | WRONG / REJ / ZIG (F1) |
| `a.fb()` where `fb` is in module b | ZIG (F2) |
| struct `P` in entry and module | known (exit 6 `Already defined: Struct 'P'`) |
| function `f` in entry and module | REJ, wrong hint (F11) |
| `main` in a module | P in the working tree, callable as `mm.main()` (F13); exit 6 `Already defined` at HEAD |
| `main` with parameters in a module | REJ (F1) |
| module with top-level statements | exit 5 `Expected declaration`, in the module |
| import after use, at top level | P |
| import inside a function | exit 5 |
| `"h.a7"`, `"H"`, `""`, `"std/nothing"` | exit 3 `not found` |

##### Initialization

| Case | Result |
| --- | --- |
| module constants from deeper modules' constants | P (`init2`: `9 18 7 13 6`), folded at compile time |
| module global initialized from constants | P |
| module global initialized by a module function call (`c.mkbase()`) | P (`5`), Zig evaluates at comptime |
| module global initialized from another runtime global | ZIG, single-file defect (F13) |
| emit order | breadth-first: direct imports in source order, then their imports; identical output under `PYTHONHASHSEED` 0-3 (`dia`, `nest`) |
| run-time side effects at module load | none possible; top-level statements do not parse |

##### CLI

| Command | Result |
| --- | --- |
| `--mode tokens`, `--mode ast` | exit 0; entry file only |
| `--mode semantic` | REJ exit 6 (F7) |
| `--mode pipeline` | exit 0, modules merged |
| `--mode doc` | exit 0, writes `main.md` beside the entry |
| `a7 check` | exit 0; also exit 0 on the F4 programs |
| `a7 build` | `./main` in the working directory; runs |
| `a7 run` | prints `42 3`; exit 7 with Zig stderr on F4 programs |
| `check` on a module without `main` | exit 6 with `--lib` hint |
| `check --lib`, `--lib` compile of a module | exit 0; `zig test` on the output reports 0 tests and no error (lazy analysis, so function bodies are not checked) |
| default output path | `<entry>.zig` beside the entry (`sub/main.zig`) |
| `-o` pointing at an imported module's `.a7` | exit 3, module untouched |

#### L25-L31 status

| Rule | Status | Evidence |
| --- | --- | --- |
| L25 file = module, own namespace, `alias.name` | Not implemented. One flat scope; `alias.name` works for calls only; bare leaked names are the only working spelling for types, constants, globals. | F1, F3, F4, known P2-8 |
| L26 duplicate import is an error | Implemented per file: same path, `./` spelling, second alias, `"geo"` vs `"geo/mod"`, bare + aliased, two selected, stdlib `io` + `std/io`, and inside a dependency (`depdup`). Hardlinks not covered. Cross-file alternate spellings break the build. | `ni/dup_*.a7`, `depdup`, F6 |
| L27 `_` private | Not implemented. | F8 |
| L27 `__` reserved | Not implemented; two real clashes reach Zig. | F8 |
| L28 local vs alias | Not implemented for locals and parameters. Top-level clashes are rejected. | F8 |
| L29 all fields visible | Holds, including `_b` (`ni/fields.a7` prints `1 2`). | - |
| L30 relative to importing file, `..` inside root | Not implemented. Resolution is from the entry directory (known). Every `..` is rejected, including ones that stay inside the root. | `nest/*`, `dia3` |
| L31 bare stdlib names | Holds for `"io"`, `"math"`. `"./io"` loads a local `io.a7`. | `l31` |

#### Not covered

- ReleaseFast builds. All runs are Zig Debug via `zig run`.
- `using import` and `pub` re-export beyond confirming the known exits.
- Struct-constraint and `where` checks across files; `$N` value
  parameters across files; generic unions across files.
- `del`/`new` and `ref` ownership across module boundaries beyond one
  `ref i32` forwarding case.
- Module-level arrays, strings, and struct globals as shared state.
- Unreadable or permission-denied module files (pinned by
  `test_import_error_stages.py`).
- `--format json` shape for success results; `--doc-out` content with
  modules; `check --layout` with module structs.
- Case-insensitive file systems; Windows paths.
- Chain depth limit M-DEPTH (no limit exists; 1,200 passes).
- HEAD was compared only for the 17 cells named in F1-F7 and F11
  (from a `git archive` copy under `$S/head`; nothing was stashed or
  checked out). The rest of the matrix is working tree only.

## Appendix H: Docs site (full report)

Embedded copy of `reports/site.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Site audit: `site/` as software and reading experience

Date: 2026-10-04. Scope: build scripts, front-end code, templates, CSS, public
assets, tests, `site/docs` tooling. Markdown content accuracy is out of scope
(covered by P3-1..P3-11).

#### Method

- Read every file in `site/scripts/`, `site/src/`, `site/content/*.ts|json`
  (not all 182 KB of `features.json`), `site/public/` non-Markdown assets,
  `site/docs/*.py`, both workflows that touch `site/`.
- Copied `site/` (minus `dist/` and `docs/audits/`) to the scratch dir and
  built there with the existing `node_modules`. Bun 1.4.2 locally.
- Nothing in the repo was edited. `git status --short site` is empty.
- Prebuilt `site/dist` has mtime 2026-10-01 18:00. It is byte-identical to my
  scratch build except `assets/site.css` (finding 2). So it is current for
  HTML, search, exports.
- VERIFIED = I ran or computed it. UNVERIFIED = from reading only.

Checks that passed in the scratch copy: `lint`, `typecheck`, `test` (12 pass),
`build`, `check:exports`, `check:links` (1493 local resources, 178 search
targets). `check:coverage` exits 1 (known).

#### Findings, ranked

By reader or release impact the order is 1, 3, 4, 5, then 2. Finding 2 sits
second because it is the cheapest to fix and affects every build.

##### 1. `bun run check` passes on a site with no JavaScript, no custom CSS, no `<main>`, no `lang`, no skip link (VERIFIED)

In a second scratch copy I emptied `src/site.js`, reduced `src/tailwind.css`
to `@import "tailwindcss";`, and edited the template in `scripts/build.ts` to
drop `<main id="main">`, `lang="en"` and the skip link. Then ran
`lint && typecheck && test && build && check:exports && check:links`. Exit 0.
`links: 1470 local resources ... checked`.

Why:

- `scripts/publishing.test.ts` tests `renderMarkdown`, `readRegistry`,
  `exportsFor`, `searchEntries` only. Nothing imports or renders `page()` in
  `build.ts:31-71`. `build.ts` runs its build at import time (`:17`, `:72`),
  so it cannot be imported by a test.
- `scripts/serve.test.ts` tests the preview server, which production does not use.
- No test loads `site.js`. No test reads `site.css`.
- `check-links.ts` is the only gate on built output. It checks `href`/`src`
  targets, duplicate ids, and one `<h1>`. It does not check that `#main`
  exists for the skip link in a meaningful way (the link is just another
  anchor; when both are removed nothing fails).
- The `tsconfig.json:12` include list is `scripts/**/*.ts` and
  `content/**/*.ts`. `src/site.js` is never type-checked or linted.
- `scripts/lint.ts` is not a linter. It checks that eight Markdown files
  exist, and greps every text file for the old package manager name and for
  `TODO`/`TBD` in Markdown (`:28-38`).

Several tests are weak: `publishing.test.ts:58` (in-process repeat of
`exportsFor`, which only shows the function is pure), `:41` (`BASE` equals a
literal), `:59-66` (manifest fields compared with the registry they were
built from).

##### 2. Shipped CSS depends on unrelated files in the tree; Tailwind contributes no used utility (VERIFIED)

`src/tailwind.css:1-2` imports Tailwind with automatic source detection.
`site/.gitignore` ignores only `dist` and `node_modules`. Tailwind therefore
scans `site/docs/`, `site/content/features.json`, the Markdown corpus, and
everything else, and emits a utility for any word that looks like a class.

- Scratch build (without `docs/audits/`): 21,345 bytes. Utilities emitted:
  `.visible .absolute .fixed .relative .static .block .contents .hidden
  .inline .table .transform .resize .underline .shadow .outline .filter`.
- Scratch build of the full tree (with `docs/audits/`): 21,781 bytes and
  byte-identical to the repo's `dist/assets/site.css`. Adds `.border
  .border-collapse .flex .flex-shrink .flex-wrap .grid .invisible .isolate
  .size-1`.
- The generated HTML uses 34 distinct class values. None is a Tailwind
  utility. All are hand-written rules in `tailwind.css:56-982`.
- Tailwind's layers are 5,791 of 21,345 bytes. Only preflight has an effect.

Consequences: editing an audit log or a Markdown sentence changes the
stylesheet. A doc that mentions a word such as `hidden` or `table` adds a
global rule with that class name. Two rebuilds of the same tree are
identical (I diffed two scratch builds), so this is input sensitivity, not
run-to-run nondeterminism. No element uses the stray utilities, so rendering
is unaffected today; the cost is about 400 bytes and a fragile input set.

Fix: `@import "tailwindcss" source(none);` plus the explicit `@source`, or
drop Tailwind and keep a small reset.

##### 3. 404 page inline links are distinguishable by color only (VERIFIED by computation)

Preflight sets `a { text-decoration: inherit }`. Underlines are restored only
under `.prose a` (`tailwind.css:237`). `public/404.html` has no `.prose`
wrapper, so its two links inside a sentence have no underline (screenshot
confirms). Link against body text contrast: light 2.21:1, dark 1.65:1. WCAG
1.4.1 needs 3:1 or a non-color cue. Same pattern for "Read Markdown" in
`.article-meta` and "GitHub" in the top bar, but those are not inline in text.

Other 404 defects (`public/404.html:2`):

- No skip link, navigation, search, or theme script. A stored explicit theme
  is ignored there.
- Hardcodes `/a7-py` four times. It is a static file outside the registry.
- `<h1>` renders at normal weight and paragraphs have no margin, because
  preflight resets them and `.not-found` restores only size
  (`tailwind.css:655-662`). Screenshot confirms.
- `site.js` is not loaded, so the `?from=` redirect at `site.js:21-24` has no
  producer. I grepped `site/` and `.github/` for `from=`: no match. That
  branch is dead. The `#/slug` branch still serves old hash routes.

##### 4. Search: 39% of the index is feature-id text that makes ranking flat (VERIFIED)

`scripts/search.ts:35` attaches the page's full feature-id string to every
section of that page. `src/site.js:203-204` matches against it.

- `search.json`: 179,728 bytes, 178 entries. `features` fields: 70,550 bytes
  (39%). `language/arrays-strings` carries 106 ids (2,490 bytes) on each of
  its sections.
- Query `tensor`: 13 hits, 8 match only through feature ids. All score 2. The
  first result is the home page; the arrays page sections follow in document
  order.
- Query `error`: 15 hits, 8 feature-id-only, all score 2. Query `defer`: 17
  hits, 9 feature-id-only.
- Query `if`: 106 hits. Matching is substring (`includes`), so `if` matches
  `specific`, `verify`.
- Scoring (`site.js:207-215`) is section hit 5, title hit 3, otherwise 1. No
  term frequency, no word boundary, stable sort by index order. Body-only
  matches are unranked.
- Error names from `a7/errors.py` (`generic_param_mismatch`,
  `break_in_match_case`, `undefined_identifier`, `type_mismatch`) occur in
  no HTML page, not in `search.json`, and not in `llms-full.txt`. Search
  cannot find a diagnostic by name (see finding 9).

Fix: index feature ids once per page (H1 entry), match on word starts, weight
body hits by count.

No XSS path: results are built with `createElement`, `textContent`, and
`append` of strings (`site.js:180-190`, `:226-252`). `a.href` comes from the
same-origin JSON. No `innerHTML` anywhere in `site.js`. (Reading.)

##### 5. Without JavaScript on mobile, 23 navigation links precede the content (VERIFIED)

`build.ts:61` ships `<details class="navigation" open>`. `site.js:1-6`
closes it under 900px. With scripts disabled at 390px the screenshot shows
the full rail (about 1,250px tall) above the article. With scripts enabled
the rail starts open in the HTML and closes when the deferred script runs,
which is a layout shift on every mobile page load (UNVERIFIED, no trace
taken).

`tailwind.css:189-191` (`.navigation:not([open]) > nav { display: block }`)
does not reveal content of a closed `<details>` in current browsers
(UNVERIFIED). The desktop rail depends on the `open` attribute, not on that rule.

Fix: ship without `open`, set it in the inline head script when the viewport
is wide, or use a CSS-only layout that does not rely on `<details>` on desktop.

##### 6. Accessibility defects in the template (reading, UNVERIFIED unless noted)

- `content.ts:82`: `<pre tabindex="0" aria-label="...">` has no role.
  `aria-label` is not permitted on a generic element. The table wrapper at
  `content.ts:145` does it correctly with `role="region"`. Add
  `role="region"` to `pre` or drop the label.
- Every one of 70 code blocks and 24 table wrappers is a tab stop, whether
  or not it overflows (counts VERIFIED from built HTML). Keyboard users tab
  through each one plus its copy button.
- Heading order: four `<h2>` group headings in the sidebar
  (`build.ts:22`) come before the page `<h1>`. The dialog and outline add
  more `<h2>`s outside the article. One `<h1>` per page holds (checked by
  `check-links.ts:25`).
- No `contentinfo` landmark. The `<footer>` is inside `<article>`
  (`build.ts:67`).
- Enter during the 120 ms debounce opens the first result of the previous
  query (`site.js:296-300` vs `:324-331`).
- Each keystroke writes three messages to the live region: "Typing…",
  "Loading search index…", then the count (`site.js:193`, `:221`, `:298`).
- `theme-color` metas follow the system scheme (`build.ts:53`), not the
  explicit theme choice.
- `main` has `tabindex="-1"` and no outline override, so activating the skip
  link may draw the 3px focus ring around the whole column in some browsers.

Passes:

- Contrast, computed from the tokens in `tailwind.css:21-55` (VERIFIED):

  | Pair | Light | Dark |
  | --- | --- | --- |
  | text on bg / surface / selected | 16.10 / 14.76 / 14.20 | 15.86 / 13.89 / 12.97 |
  | muted on bg / surface / selected | 6.81 / 6.25 / 6.01 | 9.21 / 8.07 / 7.53 |
  | link on bg / surface / selected | 7.29 / 6.68 / 6.43 | 9.64 / 8.44 / 7.88 |
  | focus ring on bg / surface | 5.98 / 5.49 | 9.05 / 7.92 |
  | control border (muted) on bg | 6.81 | 9.21 |

  `--line` is 1.39 (light) and 1.82 (dark) on bg. It is used for dividers and
  code-block frames only, not for control boundaries.
- `lang="en"`, viewport meta, skip link, `:focus-visible` ring, reduced-motion
  block (`tailwind.css:974-982`), prose links underlined, tables and code
  scroll inside their own containers, `body { overflow-wrap: anywhere }`.
- No `<img>` in any page, so no alt text to check (VERIFIED by grep). Icons
  are inline SVG with `aria-hidden`.
- Dialog uses `showModal`, returns focus to the opener, and the search
  button stays hidden when `showModal` is missing.
- Index load failure (`site.js:159-179`, `:253-264`): a non-OK response or
  a malformed index shows a message and a "Retry search" button. `finally`
  clears `request`, so retry refetches. The `generation` counter drops stale
  results. The theme toggle tolerates blocked storage (`:34-37`).

##### 7. Preview server hides base-path and 404 behavior (VERIFIED)

- `serve.ts:33` strips `/a7-py` if present, and serves the same file when it
  is absent. `GET /start/` returns 200. A URL that forgets the base works in
  preview and fails on GitHub Pages. `check-links.ts:31` catches that for
  `href`/`src` attributes in HTML, not for URLs built in `site.js`.
- `GET /a7-py/nope/` returns `text/plain` "Not found". The preview never
  serves `404.html`, so that page is not exercised locally or in tests.
- `site.js:8` and `site.js:9-20` duplicate `BASE` and ten slugs from the
  registry by hand. A renamed page will not update the list. (New instances,
  separate from the known `serve.ts` and `check-coverage.py` ones.)

##### 8. Silent no-ops in the build (VERIFIED where stated)

- Legacy anchors. `content/legacy-anchors.json` lists 48 ids. 44 are current
  heading ids and are filtered out (`content.ts:193-195`). Four are live:
  `start`, `status`, `cli-modes`, `exit-codes` (VERIFIED from built HTML).
  `build.ts:43-44` hardcodes `exit-codes` to one heading. Every other alias
  lands on the `<h1>`. So `#cli-modes` goes to the top of the Compiler page,
  not to "Legacy CLI modes". If a listed heading is renamed, its old id
  silently becomes an alias to the top of the page.
- If the target id is missing, `String.replace` at `build.ts:45-48` does
  nothing and the alias vanishes. The manifest still lists it. No check
  compares manifest aliases with built ids.
- Diagrams. `content/diagrams.ts` keys on heading ids. A renamed heading
  drops the `flow`/`pipeline` styling without an error. All four apply today.
- `content.ts:176-183`: a missing `features.json` is tolerated. The build
  then ships a manifest with zero features.
- `parseFrontmatter` (`content.ts:150-163`) is a line splitter, not YAML.
  `order: abc` yields `NaN` and an undefined sort order. A missing `group`
  defaults to "Reference". A `group` not in `GROUPS` drops the page from the
  navigation and `llms.txt`; that case is caught, `bun test` fails at
  `publishing.test.ts:63` (VERIFIED with a mutated copy).
- `markdown-links.ts:43-44`: the regex `\]\(([^)]+)\)` breaks on link
  destinations containing `)` or a title. Reference-style links are not
  rewritten. The corpus has neither today (VERIFIED by grep).
- `slugify` (`content.ts:46-52`) returns `section` for a heading with no
  ASCII letters or digits, and truncates at 72 characters. Duplicate ids get
  `-1`, `-2`; inserting a heading renumbers later duplicates.

Markdown rendering itself is sound: `html: false`, code escaped through
`escapeHtml` including quotes, language class escaped, tables wrapped, nested
lists kept, `.md` links rewritten to page URLs with fragments. Relative
links resolve against the source document. Tests cover these.

##### 9. Information architecture gaps (reading of built pages)

- No error reference on the site. `docs/ERROR_CATALOG.md` is not linked from
  any page and no diagnostic name appears in any page (VERIFIED: zero
  `ERROR_CATALOG` hrefs and zero hits for four error names in `dist`). A reader with a
  diagnostic lands on `compiler/#diagnostics-and-exit-codes` and nothing
  more specific. Search for an error name finds feature ids, not prose.
- "What works today" is split. The per-feature status data (435 records:
  199 limited, 150 planned, 53 supported, 26 unavailable, 7 unverified)
  exists only in `docs/manifest.json`. No HTML page renders it. Readers get
  prose "Status and restrictions" sections per topic and the Status page.
  Agents get more than humans here.
- Status is the 20th of 23 links, under "Project". The home page does put an
  "Experimental status" section and a top-bar "Experimental" tag up front,
  so the warning is visible; the detail is far from the start path.
- Newcomer path is coherent: Overview, Get started, Tour, Examples, then
  Reference. Prev/next pager follows the same order.
- Examples page is a table of links to GitHub sources and fixtures. No
  source is shown on the site. It indexes 49 of 51 example files (VERIFIED
  count; content gap belongs to P3-1).
- Stdlib has one page with two `<h3>`s. Only `<h2>`s appear in the outline
  (`build.ts:33`), so `std/io` and `std/math` are not in "On this page".
- SPEC is not rendered. The registry reads only `public/docs`
  (`content.ts:185`). SPEC appears as eight outbound GitHub links. The stray
  fence at SPEC line 1839 (P3-14) does not reach the site or `llms-full.txt`.
- The repo README routes readers to `docs/README.md` first and lists the
  site as a bare URL (`README.md:219-228`). README "What Works" and the site
  Status page are separate texts with no shared source.
- No orphan pages: all 23 are in the navigation, sitemap, and `llms.txt`.
  No duplicate routes.

##### 10. Agent exports (VERIFIED)

- `llms.txt`: 3,898 bytes, 43 lines, 23 page links grouped as the nav, plus
  full corpus and manifest. All 23 targets exist in `dist`.
- `llms-full.txt`: 113,116 bytes, 2,252 lines, 23 `Source:` blocks,
  frontmatter stripped. Links are rewritten to root-relative
  `/a7-py/docs/*.md`. Every distinct target resolves in `dist`. Root-relative
  links have no origin, so a consumer that saved the file must know the host.
- `manifest.json`: 324,207 bytes, 73% of it feature records. Fetched whole
  by agents that only want the page list.
- 157 distinct `github.com/code5717/a7-py/(blob|tree)/master/...` links
  across `dist`. All 157 paths exist in `git ls-tree HEAD`. Local `master`
  is 8 commits ahead of `origin/master` (2026-09-20); against the local
  `origin/master` ref (not fetched, may be stale) 37 of the 157 are missing,
  for example `a7/const_eval.py`, `docs/audits/README.md`,
  `docs/plan/delivery-roadmap.md`. Those links 404 until the branch is pushed. `check:links` does not test these; nothing in
  CI does.
- Exports contain what HTML lacks: feature status records, evidence URLs,
  aliases. HTML contains what exports lack: nothing of substance.
- Feature `qualification` strings carry fixed dates ("verification passed
  ... on 2026-09-19") and cite `site/docs/*.json` evidence files as
  authority. Those files are produced by scripts no check runs (finding 12).

##### 11. SEO and hosting (reading, UNVERIFIED against the live host)

- `public/robots.txt` deploys to `/a7-py/robots.txt`. Crawlers read only
  `/robots.txt` at the origin root, which a project site cannot provide. The
  file and its `Sitemap:` line have no effect.
- Sitemap URLs are absolute and correct under the base. No `lastmod`.
- Each page has title, description, canonical, `og:title`,
  `og:description`, `og:url`, `og:type`, `twitter:card`. No `og:image` or
  `og:site_name`.
- `404.html` at the project root is what GitHub Pages serves for misses.
  Old `#/slug` URLs are redirected client-side from the home page only.
- No third-party requests. Outbound origins in HTML are links only
  (github.com, docs.astral.sh, ziglang.org, llmstxt.org) (VERIFIED by grep).

Weights (VERIFIED, scratch build): HTML 13 to 35 KB per page; CSS 21.3 KB
(5.4 KB gzip); `site.js` 10.9 KB unminified (3.5 KB gzip); `search.json`
180 KB (35.9 KB gzip), fetched on first search open; Inter 72.9 KB,
preloaded; JetBrains Mono 21.2 KB, weight 400 only. Both fonts self-hosted
with `font-display: swap`. Asset names are not fingerprinted.

##### 12. `site/docs` tooling is unwired and writes tracked files (reading)

- `docs/verify-content.py`, `docs/verify-reference-content.py`,
  `docs/verify-snippets.py` are referenced only from `site/docs/*.md`. No
  package script, workflow, or gate runs them.
- Each overwrites a tracked JSON evidence file before its assertions run
  (`verify-content.py:64`, `verify-reference-content.py:113`,
  `verify-snippets.py:17`). A failing run still rewrites the evidence.
- `verify-content.py` and `verify-reference-content.py` test hard-coded
  program strings, not text extracted from the published pages. They cannot
  detect a page that drifts from the probe.
- `verify-reference-content.py:127-128` asserts a constrained generic exits
  7. That pins a known compiler gap as expected.
- `site/docs/verification.md:68` gives the path as `docs/verify-snippets.py`
  (relative to `site/`); `content-verification.md:41` uses
  `site/docs/verify-content.py` (relative to the repo root).
- `site/docs/` is 5.9 MB, inside the tree Tailwind scans and `lint.ts`
  greps. `lint.ts:32-37` would fail the deploy if any audit log mentioned
  the old package manager.
- `site/docs/__pycache__/` and `site/scripts/__pycache__/` exist on disk. Both are git-ignored and untracked (VERIFIED), so they are clutter only.

##### 13. Toolchain and workflow notes

- CI and deploy pin Bun 1.3.11 (`ci.yml`, `deploy-docs.yml:30`).
  `package.json` pins `@types/bun` 1.4.2 and declares no `packageManager`
  or `engines`. Local Bun is 1.4.2. `bun.lock` is dated 2026-09-19.
- `deploy-docs.yml:52-54` runs `check:coverage` before the build. That check
  exits 1 on the current working tree (known item), so a deploy from this
  tree would stop there. UNVERIFIED against CI: `gh run list` timed out, and
  local `master` is 8 commits ahead of `origin/master` (2026-09-20), so the
  live site reflects at most that commit, not the local `dist`.
- `deploy-docs.yml` runs on every push to master with no path filter.
- `bun audit` runs in `ci.yml` only, not in the deploy workflow.
- README says "The Pages workflow checks generated exports before uploading
  the build" (true) and that `check` covers "renderer and publication
  tests" (true) "preview-server security tests" (true). It does not say
  that the page template, script, and stylesheet are untested.

##### 14. Dead or redundant code (VERIFIED by grep unless noted)

- `content.ts` exports used nowhere else: `slugify`, `markdownHref`,
  `SOURCE`, `parseFrontmatter`.
- `site.js:23` `?from=` branch (finding 3).
- `tailwind.css:680-682` `.flow small`, `:677-679` `.flow strong`:
  `html: false` cannot produce `<small>`; the three flow lists I read use no bold.
- `tailwind.css:189-191` (finding 5).
- `tailwind.css:856-982` is an appended override block that redefines
  `.brand`, `kbd`, `[data-search-open]`, `.tools`, `.article-meta`,
  `.search-top` already defined above. Two definitions per selector.
- `button:hover { border-color: var(--muted) }` (`:99-101`) repeats the
  resting border.
- 44 of 48 entries in `legacy-anchors.json` (finding 8).
- `mobile-outline` and `page-outline` duplicate the same links in every
  page; one is hidden by CSS.

#### Not defects

- Tap target size is not a WCAG 2.1 AA criterion. Controls are 44px high on
  mobile anyway (`tailwind.css:91`, `:701`, `:750`).
- Listeners are attached once per static page load. No leak.
- Build output is reproducible for a fixed tree. No timestamps. Page order
  is `order` then slug.

#### Prioritized fix list

1. Add a built-output test: render `page()` for one doc and assert `lang`,
   skip link target, `<main id="main">`, one `<h1>`, `site.js` and
   `site.css` references; assert `dist/assets/site.js` and `site.css` are
   non-empty and contain known selectors. Move the build body of `build.ts`
   into an exported function so tests can import it.
2. Set Tailwind `source(none)` (or remove Tailwind). Rebuild and confirm the
   utilities layer is empty.
3. Underline links outside `.prose` (404 page, article meta) or wrap the 404
   body in `.prose`. Generate `404.html` from the template so it gets the
   theme script, base path, and navigation.
4. Search: index feature ids on the H1 entry only; match on word starts;
   rank body hits. Cancel the stale-Enter case by running the search
   synchronously on Enter.
5. Ship `<details class="navigation">` closed-safe for no-JS mobile, and
   avoid the open-then-close shift.
6. Give `pre` a role or remove its `aria-label`. Make scroll regions
   focusable only when they overflow.
7. Fail the build when a legacy alias or diagram key has no target, when a
   page's `group` is not in `GROUPS`, and when `order` is not a number.
8. Make the preview require the `/a7-py` prefix and serve `404.html` with
   status 404. Inject `BASE` and the slug list into `site.js` at build time.
9. Add an error reference page (or link the catalog) and a rendered feature
   status table built from `features.json`.
10. Wire `site/docs/verify-*.py` into a gate or move them out; make them
    write evidence only after assertions pass.
11. Align Bun: pin one version in the workflows and `packageManager`.
12. Delete `public/robots.txt` or note that it is inert on a project site.

#### Not covered

- No real browser session beyond three headless Chromium screenshots (mobile
  with scripts, mobile without scripts through a sandboxed iframe, 404).
  Keyboard flows, screen-reader output, focus order, layout shift, and
  horizontal overflow at 320px were not measured.
- The live site at `code5717.github.io/a7-py` was not fetched. Deployed
  state, HTTP headers, and cache behavior are unknown.
- `content/features.json` was sampled, not read in full.
  `scripts/check-coverage.py` was run once (exit 1) and not analyzed.
- `site/docs/audits/**` and `site/docs/evidence/**` were listed, not read.
- The three `verify-*.py` scripts were not run because they write into
  `site/`.
- `bun audit` and dependency licenses were not checked.
- Print stylesheet and Windows high-contrast mode were not checked.

## Appendix I: Remaining test files (full report)

Embedded copy of `reports/tests-remaining.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Test audit, remaining files (2026-10-04)

Read-only. No pytest run except `--collect-only`. 51 files in scope, 789 tests collected, no import errors.
"Nine newest" taken as the nine untracked `test/test_*.py` files in `git status`; excluded.
`test/test_import_error_stages.py` is modified in the working tree; audited as it stands.

#### 1. Special attention: constant-fold wrap (P2-1)

No test contains `30 * 24 * 60 * 60 * 1000`, nor any untyped `+ - *` whose exact result exceeds i32 assigned to i64.
Nearest cases:

- `test/test_constant_folding_exact.py:353-368`:
  ```
  ("x: i64 = 1 << 20000", None),
  # The fold wraps to -2147483648 the way the runtime operator does, so a
  # successful compile must never name the unwrapped value.
  ("x: i32 = 2147483647 + 1", None),
  ...
  assert process.returncode != 8
  if process.returncode == 0 and forbidden is not None:
      assert re.search(forbidden, ...) is None
  ```
  `forbidden` is `None` in both rows, so the second assert is dead. The test only proves "no exit 8".
  The comment records the wrap as intended. The value -2147483648 is never asserted. Name
  `test_unrepresentable_fold_is_not_emitted` does not match: nothing about emission is checked.
- `test_constant_folding_exact.py:327,337`: `2147483647 + 0, -2147483647 - 1, 2147483647 * 1` -> `2147483647 -2147483648 2147483647`. In range; does not exercise wrap.
- `test_untyped_constants_acceptance.py:71-72` `x: u8 = 255; x += 1` -> `0` is typed runtime wrap (L5), not the fold.
- `test_untyped_constants_acceptance.py:73-75` `LEFT :: 1 << 40` into i64 -> `1099511627776`. Shift is exact; only `+ - *` wrap.

Recorded decision or bug:

- `docs/CHANGELOG.md:67-68`: "Integer constant folds wrap to `i32` when both operands fit, and widen the default to `i64` beyond it."
- `docs/plan/decisions.md:188-191` (L52): "The repairs restore pinned contracts: IEEE f64 rounding for fold operands (L16), i32 wrap for i32-fitting operands, safety precedence for zero divisors."
- `docs/plan/decisions.md:129-137` (L47) approves exact-fit constants "like Odin"; "2.5 and out-of-range values reject"; "not ... every arithmetic, rounding and materialization detail".
- `docs/SPEC.md:205-207`: "Untyped `::` constant arithmetic is a separate pipeline owned by §4.2.1: only there do `+`, `-`, `*` over two operands that both fit `i32` wrap to `i32` like the runtime operator."
- `docs/SPEC.md:615`: "Wholly untyped arithmetic uses exact values. `+`, `-` and `*` do not wrap or round."
- Code: `a7/exact_constants.py:157-166` wraps when both operands fit i32, regardless of destination type.

Conclusion (corrected after the addendum below):
- The wrap is recorded behavior: CHANGELOG:67, SPEC:205-207 (heading "2.5 Operators and Punctuation"), L52, and a native-run test (addendum).
  None of those texts mentions the destination type. "Both operands fit i32" is true for the last multiply of `30*24*60*60*1000`
  (`2592000 * 1000`), so read plainly the recorded rule covers the `i64` case and yields the -1702967296 the audit saw.
- It conflicts with SPEC:615, which sits in "4.2.1 Untyped numeric constants", the section SPEC:205 names as the owner of the rule.
  SPEC 2.5 says 4.2.1 wraps; 4.2.1 says "`+`, `-` and `*` do not wrap or round". The spec contradicts itself.
- It conflicts with L47 (decisions.md:129-137): untyped constants fit exactly and "out-of-range values reject".
- L52 (decisions.md:188-191) is the user adopting a repair wave that "restore[s] pinned contracts". It is not an approval of the wrap
  with current/proposed examples, which the language-change rule requires (inference from the text; L52 carries no examples).
- So neither "bug" nor "decision" is settled by the docs. The user has to choose between SPEC:615/L47 (exact, reject or widen) and
  SPEC:207/CHANGELOG:67 (wrap). No test covers the `i64` destination or array-length case either way.

#### 2. Special attention: test_no_recursion.py + norec_scan.py

How it works. `norec_scan.scan(root)` parses every `.py` under the package with `ast`, builds a call graph with
receiver-aware resolution (norec_scan.py:19-66 docstring), runs iterative Tarjan, reports SCCs with >1 member and
self-loops. It also reports `copy.deepcopy` callers and dataclasses with recursive generated `__eq__/__repr__/__hash__`.
`test_no_recursion.py` has 22 synthetic scanner-spec functions (28 collected; exact group/edge sets; these can fail) and 7 ratchet tests
over `a7/` (35 collected in total).

Current scan of `a7/` (run outside pytest): 19 groups, 113 member functions, 25 dataclass findings, 0 deepcopy, 39 unresolved calls.
Allowlist `KNOWN_RECURSIVE_GROUPS` (test_no_recursion.py:393-545): 19 groups, 113 members. Same counts at ed0baff (2026-09-29) and 48fdb99 (2026-10-02); no shrink in that window.
`KNOWN_RECURSIVE_DATACLASS_METHODS` (:552-578): 25 entries.

The 330-term crash path is allowlisted: `TypeCheckingPass._visit_expression_impl` (:489), `visit_binary_expr` (:494),
`visit_expression` (:498), in a 21-member group. The ratchet therefore passes on a tree where that crash exists.

Doc claims vs allowlist:
- README.md:178 and AGENTS.md:40-44: "Semantic analysis, AST preprocessing, formatter/reporting AST walks, and backend binary-expression emission use explicit stacks."
  False for semantic analysis: allowlist holds 8 type-checker groups (37 functions), 3 validator groups, 3 safety groups.
- AGENTS.md:44-45: "The pipeline is validated at Python recursion limit 100". Only for the fixtures in test_iterative_*; not for chained binary expressions in the checker.
- docs/STATUS.md:64-66 does say "Passing the gate does not qualify the full no-recursion requirement."
- docs/plan/execution.md:192 exit criterion: "the ratchet list is empty". Not met.

Ratchet bypass:
- Groups are keyed by the sorted tuple of qualified names (:587, :597). Nothing counts groups or members.
- A rename, or a new member joining a group, makes both `test_no_new_recursion_in_a7` and `test_listed_recursive_groups_still_exist` fail.
  The fix a developer applies is to edit the tuple in the same file. A rename edit and a rename-plus-new-member edit look the same to the test.
  "Never add a member" exists only in the comment (:389-392) and the assert message (:589-591).
- No stored ceiling (e.g. `assert total_members <= 113`) and no check against git history. The ratchet is a snapshot test, not a ratchet.
- A new function that calls into an existing group without being called back is not a group member and is not reported, which is correct, but depth still grows.

What the scan misses. Probes run through `norec_scan.scan` in scratch (`tests2/probe.py`), 24 patterns:
- Detected: cross-module mutual recursion (both `from .b import g` and `b.g`), subclass override called from base, fully dynamic `getattr(self, node.attr)`,
  `getattr` with prefix held in a local, `functools.partial`, `map(f, ...)`, `sorted(key=f)`, `@property`, class-attribute alias, returned closure, list of handlers, generator expression.
- Missed (0 groups, also 0 with `include_unresolved=True`):
  - handler dict built with `dict(block=block)`
  - handler registered by item assignment `H['b'] = block` (module level and `self.h['b'] = self.block`)
  - decorator registry (`@reg('b')` storing into a dict)
  - `setattr`-style binding from outside (`v.hook = v.b`)
  - operator dunders: `__add__`, `__lt__`, `__getitem__`, `__iter__`/`for x in k`, `__getattr__`
- Missed by default, found only with `include_unresolved=True`: two unrelated classes calling each other through untyped parameters
  (`A.go(other) -> other.back(self)`, `B.back(a) -> a.go(self)`).
- These match the "Limits" paragraph (norec_scan.py:67-74) except decorator registry and external attribute binding, which the docstring does not list.
- Live exposure in `a7/` today (grep): no `__add__/__lt__/__iter__/__getitem__/__getattr__` definitions, no `functools`, no callable `dict(...)`. The misses are latent.
- The 39 unresolved calls in `a7/` are not reviewed by any test; `test_unresolved_edges_do_not_change_a7_recursive_groups` (:760) only checks they add no group.
- The scan proves cycle existence, not depth. An acyclic design can still overflow; a cyclic one bounded by grammar depth is flagged the same.

Other notes:
- `test_the_scanner_itself_has_no_recursion` (:326) can fail and is meaningful.
- `sys.path.insert(0, test/)` at import (:21). Scanner lives in `test/`, 1,700 lines, with no CLI gate use found (unchecked: scripts/).
- docs reference `tmp/recursion/scan.py` in execution.md:169 as the origin; the test does not depend on it.

#### 3. Special attention: test_feature_pins.py (13 tests)

| Pin | Line | What it asserts | Defect pin? |
| --- | --- | --- | --- |
| bench corpus shape | :41 | `bench/*.a7` stems equal a hardcoded 10-name tuple | No. Mirrors a directory listing; fails on any bench add. Low value. |
| each bench builds (x10) | :72 | CLI exit 0, `zig build-exe` Debug + ReleaseFast exit 0; binary not run | No. Build-only by design ("timing-sensitive"). Output correctness of benches is unverified here. |
| f64 into f32 rejected | :99 | exit 6, one detail, message `expected 'f32', got 'f64'`, line 5 | No. |
| `pub` on local rejected | :117 | exit 5 only; no message or span | No. Weak: any parse error passes. |

No test in this file pins a defect. The docstring (:6-8) names two accepted-today defects with no test:
"Cross-module visibility and del-through-ref have no passing test: both are accepted today (spec-drift findings, not pins)."
STATUS.md check for those two: see section 6.
The file name says "pins"; 11 of 13 tests are bench build checks. Topic name: `test_bench_builds.py`; move the two CLI rejections to the type and parser files.

#### 4. Special attention: test_audit_safety_repairs.py (16 tests)

- 14 rejection tests (:36, :49, :88): real CLI subprocess, assert exit 6, category `semantic`, a message substring, and no `.zig` written.
  They do not build or run anything. They prove the compiler now rejects the fixture, not that a crash is absent.
  Fixtures live in `test/fixtures/safety_regressions/*.a7` (10 files used).
  Message check is `message in str(payload['error']['details'])`; no line number, so a rejection at the wrong statement passes.
- 2 control tests (:57, Debug and ReleaseFast): build and run a binary, assert `(0, '20\n2\n3\n4\n4\n', '')`. This is the only native run.
- No test builds an unsafe fixture with the proof bypassed to show the original crash, so the "accepted-crashing" premise is not reproduced.
- `:80` calls bare `'zig'` with no version check and no `--cache-dir`; zig's local cache lands in the pytest cwd (repo root). T-7 class.
- File name carries "audit". Topic name: `test_safety_proof_rejections.py`.

#### 5. Per-file notes

##### Batch 1 (small files)

- test_glm_for_update.py (4). For-loop update clause with a call, with continue/break. CLI subprocess + zig build + run, both profiles, exact stdout. Sound. Name carries a model name; topic: `test_for_update_clause.py`. Imports helpers from `test_zig_backend_runtime` via `sys.path.insert`.
- test_module_resolver.py (3). Virtual stdlib module load, alias, path traversal. In-process `ModuleResolver` only. `:14`, `:17`, `:33` are `is not None` but paired with value asserts. Path traversal test (:37) checks two inputs. Keep.
- test_v1_backend_regressions.py (8). Array snapshot order, control chars, defer order, unused const effects. CLI + build + run, both profiles, exact stdout. Sound. Imports `test_zig_backend_runtime` with no `sys.path` insert: collects only because pytest prepends `test/`. Name "v1" is a phase label; merge into `test_zig_backend_runtime.py`.
- test_console_review_regressions.py (3). `--mode ast` shows `@type_set`; formatter terminates on cyclic AST. One CLI subprocess, two `python -c` subprocesses with `timeout=10` (hang guard, not a perf assert). Asserts exact strings. Keep; rename `test_console_formatter_cycles.py`.
- test_resume_backend_bindings.py (16). Labels, shadowing, const bindings in nested scopes. CLI + build + run, both profiles, exact stdout. Sound, except case "unbraced-and-pattern-binding" (:54-63):
  `value :: 5; match 5 { case value: ... }` and `value :: 3; match 3 { case value: ... }` print the same output whether `case value` compares to the constant or captures. It cannot detect P2-2 (constant-as-capture). Name carries "resume" (session word); topic: `test_block_bindings_and_labels.py`.
- test_language_audit_match_coverage.py (4). Value-producing match must be exhaustive. CLI; 3 rejections check exit 6 + message + line; 1 native run, Debug only, bare `"zig"` (:56), no version, no cache dir. Keep; rename `test_match_expression_coverage.py`.
- test_language_audit_json_formatter.py (4). JSON AST carries match else shapes. CLI `--format json`. Asserts on payload values. Keep; rename `test_json_ast_match_shapes.py`.
- test_language_audit_parser_fixes.py (17). Multi-declaration rejected at parse with span, numeric separator diagnostics (8 params), ellipsis diagnostic, multiline array native run, nested recursion rejected. CLI + one build/run via `shutil.which("zig")` asserted non-None (fails, not skips), no version, no cache dir. `:104` asserts only exit 0. Keep; rename by topic or split into tokenizer/parser files.
- test_backends_registry.py (4, not on the scope list). Only zig backend registered; `a7.backends.c` and `a7.passes.generic_lowering` not importable. `:9-12` mirrors the dict. `:15`, `:20` pin the absence of deleted modules; cannot regress short of re-adding a file. Delete 2, keep `:25`.
- test_release_version.py (2, not on the scope list). `scripts/verify_release_version.py` tag vs pyproject vs changelog. In-process on a tmp project. Sound. Keep; merge into `test_release_tooling.py`.
- test_saf4_early_return.py (5, not on the scope list). Guard facts die after a mutating else branch. 3 CLI rejections (exit 6 + message, no line), 2 native runs both profiles. Sound. Name carries a ticket id; merge into the safety file.

##### Batch 2 (native-run files)

- test_zig_backend_runtime.py (14). If-expression as operand, print to files vs pipes, struct literal eval order, isize, float widths, signed `/=` `%=`, slice guard, for-in, generic struct nesting, proven narrowing cast. CLI subprocess + zig 0.16.0 version-checked fixture + private cache dirs + run in Debug and ReleaseFast, exact stdout and empty stderr. Missing zig fails. Sound. Docstring (:5-6) says "no heap, references, division, indexing"; tests at :271 and :294 use division and indexing. It is the de facto shared helper module (6 files import `build, compile_with_cli, run_piped, zig, zig_cache` from it). Move helpers to conftest.
- test_layout.py (6). Struct size/offset/touch counts for the layout view. In-process full pipeline (`A7Compiler(mode=PIPELINE).compile_file_detailed`), no zig. Expected numbers are hardcoded and said to come from Zig `@sizeOf/@offsetOf`; the test does not run zig to confirm (unverified claim in docstring :3-5). Asserts exact values. Keep. Does not exercise the CLI flag itself.
- test_multi_file_modules.py (12). Sibling calls, alias calls, transitive imports, struct generic constraints. 8 CLI + build + run both profiles with exact stdout (stderr ignored: `stdout, _ = run_piped`); 3 CLI rejections with exit 6 and message; 1 direct `ZigCodeGenerator().generate` on a synthetic AST (:274, says CLI cannot reach it). `:162` comment pins a limitation: "Module-qualified struct literals (b.Box(...)) do not parse yet". Keep.
- test_float_nonfinite_folding.py (10). Float folds follow IEEE f64 (inf, NaN). CLI + build + run both profiles; one `build-obj` only (:175); one in-process `const_eval.fold_binary` unit test (:210). Expected values hand-derived. Sound. Copies the zig fixture and four helpers verbatim from test_constant_folding_exact.py (:33-80 in both).
- test_constant_folding_exact.py (12). Folded literals keep type and exact integer value. 7 CLI + build + run both profiles; 2 in-process partial passes (tokenizer, parser, name resolution, type checker; no validator, no safety, no codegen) at :164 and :215; 2 compile-only "not exit 8" (:359, cannot detect wrong value); 2 CLI text checks (:375).
  `:164` and `:215` assert `len(checked) >= 40*7` and that every folded literal has a type entry; they depend on private attrs (`node_types`, `exact_materialized`) and mirror implementation.
  `:215` name says "replaced nodes stay alive"; body checks materialized literals have type-map entries. Name is stale (comment :216-220 admits the design changed).
- test_untyped_constants_acceptance.py (26). Exact-fit untyped constants: order independence, destinations, 11 rejections, IEEE bit patterns. CLI + build + run both profiles; rejections check exit 6, exactly one detail, span line > 0, any-of word list, no output file.
  Word lists are loose: `('range','fit')`, `('i32','default')`, `('i32','f64')` match almost any type error. `start_line > 0` is always true for a located error.
  `:157` rewrites the emitted Zig with a regex to print bit patterns; it tests a modified artifact (stated in docstring).
  Imports the `zig` fixture and helpers from test_constant_folding_exact via `sys.path.insert`.

##### Batch 3 (iterative, termination, depth)

- test_iterative_helpers.py (3). `SafetyProofPass._int_literal`, `ZigCodeGenerator._collect_mutations`, `SymbolTable.dump` work at recursion limit 100 on 2000-5000 deep input. `python -c` subprocess, private methods on hand-built ASTs. No compiler pipeline. Asserts exact values. Docstring states the limit ("do not qualify deep programs through the whole compiler"). Keep; private-method coupling.
- test_iterative_types.py (25). `str(type)` spelling table (22 params) and deep render at limit 100. In-process on `a7.types`. Exact strings. `:83` `test_named_cycle_remains_a_name_and_structural_cycle_still_fails` asserts `RecursionError` on a self-referential slice: pins a crash as expected behavior. Keep.
- test_iterative_preprocessor.py (3). Nested-function hoisting at limit 100 with 160 nested functions. In-process `ASTPreprocessor` on hand-built AST. Exact flags. 160 nested A7 functions cannot come from the parser (depth cap), so the depth case is synthetic. Keep.
- test_iterative_return_analysis.py (6). `SemanticValidationPass._returns_on_all_paths` and `_statement_exits_current_block` at limit 100, 180 deep. Private methods via `getattr`, hand-built AST, manual `node_types` injection. Exact booleans. Mirrors internals but states real flow rules. Keep.
- test_iterative_module_loading.py (5). 1100-module import chain compiles at limit 100; missing/cyclic import diagnostics; resolver cache after failure; diamond order. 3 via `python -c "... a7.cli.main()"` subprocess (real CLI path, limit set after import), 2 in-process `ModuleResolver`. Exit codes 0/3/6 plus message and path. Sound. Writes 1100 files per run (slow, unmarked).
- test_iterative_console.py (4). Console AST render baseline, type formatting, deep render at limit 100, markup escaping. In-process `ConsoleFormatter` with private methods (`_display_ast`, `_add_statements_to_tree`). Exact output. `:90` `0 < count("BLOCK") < depth` depends on Rich clipping at width 80. Keep.
- test_parse_termination.py (6). Malformed `match` body must not hang; exit 5 with line/column, JSON and human. Real CLI subprocess with `timeout=20` (hang guard). `cwd=source.parent`. Sound. Keep.
- test_parser_depth.py (11). Nesting cap: 40 blocks and 100 parens compile; 500-deep parens/blocks/unary/ref types and 300 else-if exit 5 with "nesting depth". In-process `A7Compiler().compile_file` / `compile_file_detailed`; no zig.
  Gap: no flat chain case (`1 + 1 + ... + 1`, 330 terms). The cap counts nesting, not chain length, so the type-checker crash path is not covered here or anywhere in scope.
  `compile_ok` (:20-35) uses `tempfile.mkstemp` in the system temp dir and writes a `.zig` next to it, not `tmp_path`.
  `TestLowLimitShallow` (:122) runs hello-world and 10-deep input at limit 100 inside pytest's own stack; STATUS.md:64 records that this class of test fails under `python -m pytest`. Launcher-dependent.
  `:113` `failure is not None` is followed by a message assert; fine.

##### Batch 4 (safety)

- test_safety_precursors.py (25). Safety proof pass: deferred assignments, for-in bindings, nested functions, file-scope constants, per-obligation diagnostics. Real CLI subprocess with JSON. 17 rejections via `assert_rejected_at` (exit 6, exactly one detail, message, exact line): strong. 5 accepted twins checked with `zig build-obj -fno-emit-bin` (type-check only, no run). 1 build + run both profiles (:388). 3 accept-only tests assert just exit 0 (:184, :209, :251).
  - Stale docstrings: `:187-189` and `:254-256` say an un-braced deferred assignment "still lowers to `defer void;` (B11), which Zig rejects until batch Z4". Verified today: the exact sources of :184, :209 and :251 compile (exit 0), emit `defer x = 0;`, and pass `zig build-obj -fno-emit-bin` with zig 0.16.0 in scratch. The reason for skipping the Zig check is gone.
  - Pinned defect `:502-516` `test_returned_local_slice_is_accepted_and_zig_builds`: "S5: returning a slice of a local stack array is accepted (KNOWN)". Returns a dangling slice. The test only reads `s.len`, so it never touches the dead memory. Not listed in docs/STATUS.md (grep for slice/dangling/escape: no hit).
  - Pinned precision limit `:534-559`: `if i < xs.len and xs[i] > 0 { ret xs[i] }` is rejected at both the condition (line 3) and the body (line 4). The body rejection is a false positive pinned as expected. Not in STATUS.md.
  - `:412` joins stdout and stderr before comparing.

##### Batch 5 (preprocessor)

- test_ast_preprocessor.py (69). `ASTPreprocessor` folding, mutation, usage, hoisting flags. Partial: `parse_a7` + `ASTPreprocessor()` only, with no type map and no prior type checking. No semantic passes, no codegen, no zig.
  - The real pipeline folds in the type checker first (`exact_constants`) and hands the preprocessor a type map (`a7/compile.py:508`). The 27 `TestConstantFolding` tests exercise the second folder (`const_eval.fold_binary`) in a configuration the pipeline never uses. Probe: preprocessor-only leaves `2147483647 + 1` and `30*24*60*60*1000` unfolded (BINARY), while the pipeline wraps them. Two folders, two behaviors; these tests cover the one that does not decide the output.
  - `TestFieldSugarLowering` (8 tests, :64-168) asserts that removed `.adr/.val` sugar is not lowered, by calling the private no-op `_lower_field_sugar`. Six are the same check. Class name says "Lowering"; tests assert no lowering.
  - `:653` `test_variable_used_only_as_assignment_target_still_unused` asserts `is_used is True`. Name and docstring say the opposite of the assert.
  - `:605` `test_default_is_used_true_on_ast_node` tests a dataclass default.
  - `:359` `changes >= 1`, `:768` `changes >= 1`, `:875` `changes_made < 999`: near-vacuous.
  - `TestEmptyAndMinimalInput` (7, :794-876): 6 assert parser output shape ("process without error"), not preprocessor behavior.
  - Docstring :7 lists "Legacy field sugar compatibility" as a preprocessor job; it is a no-op.
  Verdict: fix. Keep mutation/usage/hoisting (about 25 tests), move fold checks to the CLI-level folding files, delete field sugar and minimal-input classes.

##### Addendum to section 1: the test that pins the i32 fold wrap

Found outside the two files named in the brief: `test/test_audit_backend_repairs.py:49-61`, case `'wrap'`:
```
    a: u8 = 255
    b: u8 = 1
    io.println("{} {} {} {} {}", x, y, z, a + b, 2147483647 + 1)
}
''', '0 127 0 0 -2147483648\n'),
```
It runs the binary in Debug and ReleaseFast and requires the untyped constant sum `2147483647 + 1` to print `-2147483648`.
This is the wrap pinned as expected behavior, with a native run. It is what L52 calls a "pinned contract".
It conflicts with SPEC.md:615 ("Wholly untyped arithmetic uses exact values. `+`, `-` and `*` do not wrap or round.") and agrees with SPEC.md:205-207 and CHANGELOG.md:67.
It has no destination type. The `x: i64 = 30*24*60*60*1000` case (wider destination, each operand fits i32) is still untested and undecided in writing.
It has no destination type. The `i64`-destination and array-length forms have no test. See the corrected conclusion in section 1: the recorded rule is destination-blind, and it conflicts with SPEC:615 and L47.

##### Batch 6 (type boundaries, rejected examples, import stages, backend repairs)

- test_audit_type_boundaries.py (19). Type errors at struct literals, shifts, unsigned negate, out-of-range args, main signature, `--lib`, import cycle. Real CLI subprocess (no `cwd`, absolute paths). Rejections check exit 6 + lowercase fragment in whole stdout + no output; no line numbers. Fragments `'Type mismatch'` and `'mismatch'` (:21, :30, :45) match any type error.
  1 native run (:54), Debug only, `shutil.which('zig')` asserted, no version check, no cache dir.
  `:92` `test_library_without_main_remains_valid` first asserts a main-less file is rejected (exit 6) and only then that `--lib` accepts it. Name is stale after LNG-16.
  `:116` asserts exit 5 only. Rename file by topic (`test_type_boundaries.py`).
- test_rejected_examples.py (13). `examples/rejected/*.a7` each fail with the manifest exit code and message; one detail with a span; no output file. Real CLI. `load_cases()` asserts manifest == directory at import (a mismatch is a collection error, not a test failure). 6 cases, each compiled twice (two tests could be one). `:83` greps `scripts/verify_examples_common.py` for the literal `glob("*.a7")`; text-mirror test, fails on a harmless rewrite. `EXIT_SEMANTIC` (:25) unused. Keep; merge the two parametrized tests; drop :83 or replace with a behavioral check.
- test_import_error_stages.py (12, modified in working tree). Unclosed comment exit 4; duplicate import exit 6; dependency tokenize/parse/missing/unreadable/permission exit 4/5/3/3/3. Real CLI. `:85-86` accepts either of two messages. `:106` asserts exit 0 only, no build. `:89`, `:175` skip on no-symlink / root (legitimate). Docstring calls itself "Phase 1 frontend pins"; content is stage attribution. Keep.
- test_audit_backend_repairs.py (19, not on the scope list). Match without else, compound `/=` `%=`, brace escapes, `math.abs`, keyword shadow, zero strings, generic fields, for-shadow, wrap. CLI + build + run both profiles, exact stdout. Sound mechanics. Holds the wrap pin above. `:72` rejection twin checks exit 6 + message. Rename by topic; merge into `test_zig_backend_runtime.py`.

##### Batch 7 (CLI contracts)

- test_cli_failures.py (20). CLI exit codes, JSON error shape, no artifact on failure, `--verbose`, `--doc-out`, `--mode doc`. Real CLI subprocess, `cwd=PROJECT_ROOT`. No zig. Asserts exit code plus message fragment or JSON field in most tests.
  Weak spots: `:88` exit 0 + file exists only; `:392` exit code only, relative path resolved against repo root; `:378` accepts `ParseError` or `CompilerError`; `:64` fragment `type mismatch`; `:224` loops over a one-element backend list (leftover from a removed backend).
  Limitation pins (not defects): variadics rejected "not implemented yet" (:208, :238), named import items exit 6 (:261). STATUS.md lists variadics and import follow-ups as not supported.
  Keep.
- test_error_stage_matrix.py (63). Each failing stage gives its exit code in every mode and both formats. Real CLI through `scripts/error_stage_common.run_cli` (`sys.path.insert` of `scripts/`). No zig.
  `:40` re-runs the whole matrix through the script's own audit and asserts `passed == total == 61`; the 61 parametrized tests below then run the same CLI calls again. One of the two is redundant, and the count 61 is a magic number tied to the mode lists.
  Human-format branches are weak: `:72` `"line" in combined`, `:111-126` and `:183-198` assert only the exit code for human output.
  "Codegen error" (exit 7) is produced only by `--backend nope` (:206). No test in this file triggers exit 7 from real code generation.
  `:234` hardcoded `/tmp/this_file_does_not_exist_1234567890.a7`.
  `:256` monkeypatches `Parser.parse` to raise; the docstring states what that leaves unverified. Acceptable mock.
  Fix: drop `:40` or the duplicated parametrized bodies; add one real codegen failure.

##### Batch 8 (release tooling)

- test_release_tooling.py (20). Release scripts: manifest generate/verify, archive contents, secret scan, wheel install, example build script, project status. Mostly `scripts/*.py` via subprocess on tmp dirs; exit code plus message. Compiler touched only at `:30` (`uv run a7 --mode tokens`) and `:81` (build script on one example, `shutil.which("zig")`, no version check).
  - Wall-clock: 21 `timeout=` sites. `:45` gives `uv run a7` 10 s (a cold `uv` sync exceeds it), `:105` gives a zig build 30 s, `:73` gives wheel + sdist build 360 s. A timeout raises, so a slow machine fails the test.
  - `:53` `test_package_exports_compiler_api`: `A7Compiler is not None`, `callable(...)`. Verifies nothing beyond import.
  - `:418` `test_project_status_reports_example_and_golden_counts` checks only `example_count`; no golden count. Name is stale.
  - `:538-552` after asserting the prefix string, the loop matches names built from that prefix against a regex of the same literal. The loop cannot fail. Also pins `linux-x86_64`.
  - `:61` builds a wheel and sdist inside the unit suite (slow, unmarked; network need unchecked).
  - Manifest and secret-scan tests (:123-345, :437-535) are sound: tamper, traversal, symlink, flat download.
  Keep; fix the four items above; mark slow.

##### Batch 9 (files not on the scope list and not in the reviewed set)

- test_pipeline_artifacts.py (10). `--output`/`--doc-out` never overwrite an input (direct, symlink, hardlink, imported, transitive), failed compile leaves the old artifact, JSON `artifacts` is truthful. Real CLI, real files. Exact bytes and exit codes. Sound. Docstring :3 "Known failures deliberately remain visible" is stale if all pass (unchecked: not run). Keep.
- test_pipeline_diagnostics.py (7). Diagnostics carry file, line, column for token/parse/semantic errors, in entry file and imported module. Real CLI, `cwd=source.parent`. Exact line and column. `:91-92` accepts exit 5 or 6 for an imported parse error, while test_import_error_stages.py:142 and test_error_catalog_pins.py:118 require 5. Tighten to 5. Keep.
- test_parser_regressions.py (8). Intrinsic name with underscore, trailing comma in call, type alias vs function, generic decls. Parse only (`parse_a7`). Asserts node kinds and names. `@size_of` is parsed-only; test does not claim more. Class name "Recent...Guards" is stale. Merge into test_parser_basic.py.
- test_error_catalog_pins.py (9). JSON hardening for non-serializable values; token count excludes EOF; imported-file stage attribution. 3 unit tests on private functions (`_safe_json_value`, `_ast_node_shallow_dict`, `_safe_json_dumps`), 6 real CLI. `:39` `!= ""` and `:65`, `:155` truthiness asserts are near-vacuous. Docstring :4-5 "worker C attribution ... All tests pass" is session wording. Imported-file cases duplicate test_import_error_stages.py. Merge the 5 import cases there; keep the JSON tests.
- test_compound_assignment_types.py (13). Compound assignment rejects string/bool/float operand misuse with line; accepts 8 forms and checks them with `zig build-obj -fno-emit-bin` (type-check only, nothing run). Real CLI. Rejections strong (message + line + no "divisor" misattribution).
  Accept list pins `char += char`, `char |= char`, `bool ^= bool`, `bool &= bool` because "Zig builds today" (:4, :132). The oracle is the backend, not SPEC. Whether SPEC allows arithmetic on `char` or bitwise on `bool` is unchecked.
- test_cli_workflows.py (15). `check`, `build`, `run`, `doctor`, `--version`, `--lib`, paths with spaces, input protection, wrong zig version, native build failure, argument forwarding. Real CLI with `cwd=tmp_path`; real zig for 2 tests (`shutil.which`, version checked by the CLI itself); a fake `zig` script on PATH for 2 tests (named boundary, limit stated at :113). `timeout=120`. Sound. Keep.
- test_module_alias_shadowing.py (7). A local named like an import alias shadows it by scope. 6 CLI + build + run both profiles, exact stdout; `:201-205` and `:208` call private `A7Compiler._annotate_file_module_calls`. Docstring :9-11: "stopgap until the module redesign; ledger L28 will later make a local named like an alias a compile error". Pins interim behavior by decision. Keep.
- test_stdlib_call_resolution.py (18). User code named like stdlib functions runs user code; stdlib calls resolve only through an import. CLI + build + run both profiles, exact stdout and stderr. `:294` re-runs two examples against goldens (duplicates test_examples_e2e). Docstring :11-12 "no ... integer division" fine; own copy of the zig fixture. Sound. Keep; drop :294.
- test_iterative_type_equality_hashing.py (18). `a7.types` equality, `equals`, hash at depth 5000 under limit 100. In-process unit tests.
  `:109` compares a 33x33 relation matrix to `LEGACY_*_ROWS` bitstrings captured from the old implementation: a characterization snapshot, unreadable on failure.
  `:117-132` asserts `hash(x) == hash(('slice', array_hash))` etc.: mirrors the implementation's hash payloads.
  `:183-190` requires `RecursionError` from `equals`, `==`, `hash` on a self-referential slice: pins a crash. `:147` pins `UNKNOWN.is_assignable_to(I32)` true (error-recovery rule; unchecked against SPEC).
  Keep depth tests; fix or drop the snapshot and hash-payload mirrors.

##### Batch 10 (parser files)

Method: every test's asserts extracted with `ast` (`tests2/asserts.py`); the source snippet of each non-rejection test run through the in-process full pipeline (`tests2/pipe.py`, `CompileMode.PIPELINE`).

| File | Tests | Assert only `result.kind == NodeKind.PROGRAM` | Snippets that pass the full pipeline |
| --- | --- | --- | --- |
| test_parser_creative_cases.py | 32 | 30 | 5 of 31 (26 exit 6) |
| test_parser_combinatorial.py | 26 collected (24 functions) | 20 | 5 of 22 (17 exit 6) |
| test_parser_unicode_and_special.py | 19 | 19 | 11 of 19 (8 exit 6) |

- `parse_a7` either returns a PROGRAM node or raises, so `result.kind == NodeKind.PROGRAM` cannot fail once the call returns. These 69 tests are the T-5 pattern with a different spelling. They detect only "parser now raises on this text".
- 51 of 72 "valid" snippets exit 6 in the full pipeline. Causes, from CLI JSON details (files with at least one such error): undefined identifier 33, call of undefined or non-callable name 27, field access on non-struct 15, assignment type mismatch 11, non-integer index 10, no `main` 9. None is rejected only for a missing `main`. They are not valid programs, so they do not document accepted A7.
- test_parser_creative_cases.py: `:17` docstring "property-based pointer syntax" uses removed `.adr/.val` sugar; passes only because those are ordinary field names now. `:640-675` and `:677` are the two real tests (decl names; value-generic rejection). The comment at :678 records that the old version passed because recovery dropped `main`: the same risk still applies to the other 30.
- test_parser_combinatorial.py: `:600` label test asserts kinds and labels (good); `:654`, `:659` reject malformed labels (good). The rest are smoke. "Combinatorial" is a misnomer: no parametrization over combinations, each test is one long snippet.
- test_parser_unicode_and_special.py: `:234` `test_very_wide_expression` has 26 terms, not near any limit. `:355` `test_number_extremes` contains `scaled := 1_000_000 * 1_000_000` (the P2-1 wrap input) and asserts nothing about its value. No test checks that a non-ASCII string survives to output; identifiers are ASCII only.
- test_parser_basic.py (30). Literal, expression, declaration, statement AST shapes. Parse only; asserts kinds, operators, values, spans. Sound. `:350` `test_missing_semicolon_recovery` feeds valid code; no recovery happens. Keep.
- test_parser_edge_cases.py (40). Error messages, empty input, long names, nesting, type syntax. Parse only. Mostly real asserts. `:108`, `:124`, `:133` are named "recovery"/"synchronization" and feed valid code. `:256` wraps asserts in `try/except Exception: pytest.fail` (harmless, hides the traceback). Keep; rename the three.
- Verdict for the three smoke files: delete 69, or convert the 21 pipeline-clean snippets into CLI + build + run cases and drop the rest.

#### 6. Pinned bugs and pinned limitations

| # | Where | What is pinned | Defect? | In docs/STATUS.md? |
| --- | --- | --- | --- | --- |
| 1 | test_audit_backend_repairs.py:59-61 | untyped `2147483647 + 1` prints `-2147483648` | Needs a user decision: recorded (L52, CHANGELOG:67, SPEC:207) but conflicts with SPEC:615 and L47 | No (STATUS:88 covers typed runtime wrap only) |
| 2 | test_constant_folding_exact.py:355-357 | same wrap, by comment only; assert is `returncode != 8` | Same; test verifies nothing | No |
| 3 | test_safety_precursors.py:502-516 | returning a slice of a local array is accepted ("KNOWN") | Yes, dangling slice | No |
| 4 | test_safety_precursors.py:534-559 | `if i < xs.len and xs[i] > 0 { ret xs[i] }` rejected at line 3 and line 4 | Line 4 is a false positive | No |
| 5 | test_safety_precursors.py:187-189, :254-256 | docstrings say un-braced defer emits `defer void;` so no Zig check | Stale: all three programs build with zig today (verified) | n/a |
| 6 | test_iterative_types.py:83-90 | `str()` of a self-referential slice raises `RecursionError` | Crash on malformed input, pinned | No |
| 7 | test_iterative_type_equality_hashing.py:183-190 | `equals`, `==`, `hash` on a cyclic type raise `RecursionError` | Same | No |
| 8 | test_no_recursion.py:393-545 | 19 recursive groups (113 functions) allowed, incl. the type-checker expression visitor that overflows at 330 chained terms | Yes | Partly: STATUS:64-66 says the gate does not qualify the requirement; no list |
| 9 | test_multi_file_modules.py:162-163 | module-qualified struct literal `b.Box(...)` does not parse | Limitation | Yes (STATUS:82) |
| 10 | test_cli_failures.py:208-258 | variadic functions rejected "not implemented yet" | Limitation | Yes (STATUS:118) |
| 11 | test_cli_failures.py:261-281 | `import "std/io" { println }` exits 6 | Limitation | Partly (STATUS:82 names `using import`; named items unchecked) |
| 12 | test_module_alias_shadowing.py:9-11 | local may shadow an import alias until L28 | Interim by decision | No |
| 13 | test_compound_assignment_types.py:132-136 | `char += char`, `bool ^= bool` accepted because Zig builds them | Unchecked against SPEC | No |
| 14 | test_feature_pins.py:6-8 (docstring, no test) | cross-module visibility and del-through-ref "accepted today" | Yes, and untested | Visibility: STATUS:197 mentions "10.4 visibility intent" only; del-through-ref: no |
| 15 | test_resume_backend_bindings.py:54-63 | `case value:` with `value` a constant; output is the same for capture or compare | Cannot detect P2-2 | n/a |

#### 7. File names that carry a model, session, phase, or ticket label

| File | Label | Topic name |
| --- | --- | --- |
| test_glm_for_update.py | model name | test_for_update_clause.py |
| test_resume_backend_bindings.py | session word | test_block_bindings_and_labels.py |
| test_v1_backend_regressions.py | phase | merge into test_zig_backend_runtime.py |
| test_console_review_regressions.py | review session | test_console_formatter_cycles.py |
| test_language_audit_match_coverage.py | audit | test_match_expression_coverage.py |
| test_language_audit_json_formatter.py | audit | test_json_ast_match_shapes.py |
| test_language_audit_parser_fixes.py | audit | split: tokenizer separators, parser diagnostics |
| test_audit_safety_repairs.py | audit | test_safety_proof_rejections.py |
| test_audit_type_boundaries.py | audit | test_type_boundaries.py |
| test_audit_backend_repairs.py | audit | merge into test_zig_backend_runtime.py |
| test_saf4_early_return.py | ticket id | merge into safety file |
| test_feature_pins.py | "pins", "Phase 3" | test_bench_builds.py |
| test_error_catalog_pins.py | "Phase 1B", "worker C" in docstring | test_json_error_hardening.py |
| test_safety_precursors.py | batch "C4" | test_safety_proof_facts.py |
| test_import_error_stages.py | docstring "Phase 1 frontend pins" | name is fine; fix docstring |
Fixture and case ids also carry probe ids (`p18-`, `b34-`, `c35-`, `d_loop_no_fixedpoint`); harmless, but meaningless without the audit notes.

#### 8. Environment, order, and shared state

- No test in scope reads or writes under repo `tmp/`. No hardcoded `/home/...` paths. One hardcoded `/tmp/` path: test_error_stage_matrix.py:234 (a path that must not exist).
- System temp outside `tmp_path`: test_parser_depth.py:20-35 (`tempfile.mkstemp`, cleaned up).
- zig without version check or private cache: test_audit_safety_repairs.py:80 (bare `'zig'`), test_language_audit_match_coverage.py:56 (bare `"zig"`), test_language_audit_parser_fixes.py:87-90, test_audit_type_boundaries.py:75-78, test_release_tooling.py:82. These use whatever zig is on PATH and the user's global zig cache (inference: no `.zig-cache` appears in the repo root). Three of them build Debug only.
- No `skipif` on missing zig in any in-scope file: missing zig fails (good). Skips exist only at test_import_error_stages.py:91, :96, :177 (symlink, root).
- The version-checked `zig` fixture is copy-pasted in 9 files; 7 more files import it from `test_zig_backend_runtime` or `test_constant_folding_exact`. 5 of those 7 import without a `sys.path` insert and rely on pytest's default rootdir-prepend import mode (`pyproject.toml:32` sets only `testpaths`).
- Wall-clock: `timeout=` in test_release_tooling.py (21 sites, 10-360 s), test_parse_termination.py (20 s), test_console_review_regressions.py (10 s), test_cli_workflows.py (120 s). These are hang guards; the 10 s ones on `uv run` and script startup are the fragile ones. No elapsed-time asserts in scope.
- Recursion-limit tests that set `sys.setrecursionlimit(100)` in-process (test_parser_depth.py:122, test_iterative_types.py:73, test_iterative_console.py:71, test_iterative_preprocessor.py:31, test_iterative_return_analysis.py:46, test_iterative_type_equality_hashing.py:168/:257, test_module_alias_shadowing.py:226) depend on how deep pytest's own stack is. STATUS.md:64-65 records a launcher-dependent failure of this kind. The subprocess form (test_iterative_helpers.py, test_iterative_module_loading.py) does not have the problem.
- No `random`, no order dependence found. `sys.path.insert` at import in 5 files (test_no_recursion, test_layout, test_glm_for_update, test_untyped_constants_acceptance, test_error_stage_matrix) mutates global state but harmlessly.
- No pytest markers. Native-build tests in scope: roughly 150 test cases build with zig (estimate from collect counts, not measured), most twice (Debug + ReleaseFast).

#### 9. Verdict table

| File | Tests | Verdict | Reason |
| --- | --- | --- | --- |
| test_release_tooling.py | 20 | fix | 3 vacuous/stale tests, tight timeouts, wheel build unmarked |
| test_release_version.py | 2 | merge | into test_release_tooling.py |
| test_layout.py | 6 | keep | exact values; "Zig ground truth" not re-verified |
| test_multi_file_modules.py | 12 | keep | native runs; stderr ignored |
| test_module_resolver.py | 3 | keep | small, real asserts |
| test_zig_backend_runtime.py | 14 | keep | model file; move helpers to conftest; fix docstring |
| test_constant_folding_exact.py | 12 | fix | :359 verifies nothing; :164/:215 mirror internals; no wide-destination case |
| test_float_nonfinite_folding.py | 10 | keep | drop duplicated helpers |
| test_untyped_constants_acceptance.py | 26 | fix | loose word lists; add `i64 = a*b` beyond i32 and array-length cases |
| test_feature_pins.py | 13 | fix | rename; 11 are build-only; move 2 CLI tests |
| test_glm_for_update.py | 4 | merge | rename/merge into loop tests |
| test_resume_backend_bindings.py | 16 | fix | rename; pattern case cannot detect P2-2 |
| test_v1_backend_regressions.py | 8 | merge | into test_zig_backend_runtime.py |
| test_console_review_regressions.py | 3 | merge | with test_iterative_console.py |
| test_language_audit_match_coverage.py | 4 | fix | rename; pinned zig + both profiles |
| test_language_audit_json_formatter.py | 4 | keep | rename |
| test_language_audit_parser_fixes.py | 17 | fix | rename/split; pinned zig |
| test_iterative_helpers.py | 3 | keep | private-method coupling noted |
| test_iterative_types.py | 25 | keep | :83 pins RecursionError |
| test_iterative_preprocessor.py | 3 | keep | |
| test_iterative_return_analysis.py | 6 | keep | private methods |
| test_iterative_module_loading.py | 5 | keep | mark slow |
| test_iterative_console.py | 4 | keep | |
| test_iterative_type_equality_hashing.py | 18 | fix | snapshot matrix and hash-payload mirrors |
| test_parse_termination.py | 6 | keep | |
| test_parser_depth.py | 11 | fix | add flat-chain case; use tmp_path; subprocess for limit 100 |
| test_parser_creative_cases.py | 32 | delete | 30 smoke tests; keep the 2 real ones elsewhere |
| test_parser_combinatorial.py | 26 | delete | 20 smoke; move 4 label tests to test_parser_basic.py |
| test_parser_unicode_and_special.py | 19 | delete | 19 smoke; replace with a few native-run unicode string cases |
| test_parser_basic.py | 30 | keep | rename :350 |
| test_parser_edge_cases.py | 40 | keep | rename 3 "recovery" tests |
| test_parser_regressions.py | 8 | merge | into test_parser_basic.py |
| test_no_recursion.py + norec_scan.py | 35 | fix | add a member-count ceiling; docs overstate; allowlisted crash path |
| test_ast_preprocessor.py | 69 | fix | folds test the wrong folder; 8 no-op sugar tests; 1 inverted name |
| test_safety_precursors.py | 25 | fix | stale B11 docstrings; add Zig check to 3; S5 pin |
| test_saf4_early_return.py | 5 | merge | into safety file |
| test_audit_safety_repairs.py | 16 | fix | rename; assert line numbers; pinned zig |
| test_audit_type_boundaries.py | 19 | fix | rename; loose fragments; stale test name :92 |
| test_audit_backend_repairs.py | 19 | merge | into test_zig_backend_runtime.py; decide the wrap pin |
| test_cli_failures.py | 20 | keep | minor loose asserts |
| test_cli_workflows.py | 15 | keep | |
| test_rejected_examples.py | 13 | fix | merge two passes; drop text-mirror test :83 |
| test_error_stage_matrix.py | 63 | fix | matrix run twice; no real codegen failure |
| test_import_error_stages.py | 12 | keep | absorb import cases from catalog pins |
| test_error_catalog_pins.py | 9 | merge | split between import stages and JSON tests |
| test_pipeline_artifacts.py | 10 | keep | |
| test_pipeline_diagnostics.py | 7 | fix | :91 accepts two exit codes |
| test_compound_assignment_types.py | 13 | keep | check accept list against SPEC |
| test_module_alias_shadowing.py | 7 | keep | interim by L28 |
| test_stdlib_call_resolution.py | 18 | keep | drop :294 duplicate |
| test_backends_registry.py | 4 | delete 3 | mirrors a dict and pins deleted modules; keep :25 |

#### 10. Not done

- No test was executed (rule). Pass/fail status of every test is unverified; "sound" means the assertions can fail, not that they pass today.
- test_ast_preprocessor.py lines 330-986 were read as a condensed listing (test names, docstring first lines, asserts, preprocess calls), not line by line. test_parser_creative_cases.py, test_parser_combinatorial.py, test_parser_unicode_and_special.py, test_parser_basic.py and test_parser_edge_cases.py were analysed with `ast` scripts plus sampled reads, not read fully. test_stdlib_call_resolution.py and test_iterative_type_equality_hashing.py were read with blank lines and the case corpus (lines 10-108) skipped.
- norec_scan.py (1,700 lines): docstring and public API read; internals not read. Miss list comes from 24 black-box probes, not from the edge-building code.
- The 39 unresolved calls the scanner reports for `a7/` were not inspected.
- `test/fixtures/safety_regressions/*.a7` and `examples/rejected/manifest.json` contents not read.
- Whether SPEC allows `char += char` / `bool ^= bool`, and whether layout numbers match Zig, not checked.
- conftest.py reviewed only at :50-76 (already covered by T-1).
- Which of the 15 Wave E failures first pinned the wrap (L52) not traced beyond `git log -S` (the 'wrap' case entered at ed0baff, 2026-09-29). L52 has no date in decisions.md, so whether it predates that commit is unchecked.
- "Nine newest files" taken as the nine untracked test files; PLAN.md cites four of them by name (test_codegen_emit, test_stdlib_result, test_where_clauses, test_match_payload) and does not list the set.

## Appendix J: Stdlib proposal (full document)

Embedded copy of `stdlib-proposal.md` as written by its reviewer; headings demoted.
Paths such as `tmp/...` or the scratchpad in it refer to `probes/`.

### Stdlib proposal, 2026-10-04

Status: research and design only. Nothing here is approved. Every item
that changes A7 syntax or behavior needs a before/after packet and the
user's approval under AGENTS.md "Language change approval". No tracked
file was edited. No pytest or gate script was run.

Recommendation in one paragraph: build the stdlib as a hybrid. A small
set of typed hooks stays in the Python registry and lowers to Zig. All
other stdlib code ships as `.a7` files inside the wheel. The compiler
already resolves and runs A7-source `std/...` modules (probe D1 below).
Phase A lists eighteen modules that need no heap, including event
readers for JSON and YAML. Lists, maps, and
owning strings wait for the memory decision (L51, L57), because L42
makes a growable list a shared handle, which a plain A7 struct cannot
express.

Change during this session: the user wrote "add json and yaml parsers
into stdlib" on 2026-10-04. Sections 3.21-3.23 add `std/json`,
`std/yaml`, and a shared document tree. This reverses the roadmap B8
row "YAML/TOML NEVER" for YAML. Nothing was implemented in the
compiler; the request is recorded here as design, and it needs a
ledger entry and a roadmap edit that I did not make (tracked files).

Evidence labels: "V" = I ran a probe and saw the output. "R" = I read
the file. "M" = from memory, not checked this session. Probe sources
are in the session scratchpad under `scratchpad/stdlib/` (`cat/` and `cat2/` module
stubs, `ex/` the section 3 examples, `iso/` and `iso2/` isolation probes, `demo/` the runnable demo, `old/` first
rounds, `cat-results.txt`, `iso-results.txt`). The scratchpad is
session-local; the load-bearing probes are quoted in this file.

#### 0. What the probes found

All runs used `uv run a7 --mode pipeline FILE` (add `--lib` for files
without `main`) and `uv run a7 run FILE`, Zig 0.16.0.

| ID | Finding | Ev |
| --- | --- | --- |
| D1 | An A7-source stdlib module resolves and runs today. A file at `<entry dir>/stdlib/std/strings.a7` loads through `strings :: import "std/strings"`, and its functions return typed values (`usize`, `bool`). The search path is `a7/compile.py:276-280`. | V |
| D2 | A nine-import demo (eight A7-source modules, 241 lines, plus `std/io`) ran natively: `13 passed, 1 failed` with one deliberate failure. Front-end time rose from 0.15-0.24 s (hello world) to 0.31-0.38 s. | V |
| D3 | The third search path is `Path(__file__).parent.parent / "stdlib"`, which is the repo root, outside the `a7` package. No such directory exists. `pyproject.toml` ships `include = ["a7*"]` only, so a wheel would not carry it. | R |
| D4 | Functions are namespaced per module; types are not. Two modules that each define `helper :: fn` ran correctly (printed `1 2`). Two modules that each define `P :: struct` exit 6 `Already defined: Struct 'P'`. A type from an imported module is used bare (`Tally{...}`); `coll.Pair(i32, i32)` exits 5 `Expected expression`. | V |
| D5 | Generic functions work in the `name($T) :: fn(x: $T)` form with `$T` at every use. Bare `T` in a signature exits 6 `Undefined type (Type 'T')`. Explicit type arguments at a call (`push(i32, s, 5)`) exit 6. | V |
| D6 | A generic function that builds or returns a generic type fails codegen. `wrap($T) :: fn(v: $T) Box($T) { ret Box($T){value: v} }` and the `Option($T)` equivalent exit 7 `Zig backend: generic type requires an explicit generic environment`. Taking `Box($T)`, `ref Box($T)`, `Option($T)`, `[]$T`, or `fn($T) bool` as a parameter exits 0. Returning a concrete `Option(usize)` from a generic function exits 0. | V |
| D7 | Index proofs hold for one bound on one identifier. Works: `while i < xs.len { xs[i] }`, a guarded parameter index, a guarded index into a field array (`s.items[n]` with `n` a parameter). Fails with exit 6 `Index not proven in bounds`: an index loaded from a struct field (`n := s.count; if n < 8 { items[n] }`), `xs[0]` under `if 0 < xs.len`, two slices under two guards (`while i < dst.len { if i < src.len { dst[i] = src[i] } }`), `if a and b` guards. | V |
| D8 | Slice bounds with runtime values are mostly unprovable: `xs[from..xs.len]` under `if from <= xs.len`, `xs[0..0]`, and `s[0..]` exit 6. `a[n..4]` on a fixed array under `if n <= 4` runs. | V |
| D9 | Strings are thin. Works: `for ch in s`, `s[i]` with a literal-bounded counter, printing, passing, storing in structs. Fails: `s.len` (exit 6), `string` to `[]u8` or `[]char` (exit 6), `cast(u8, ch)` and `cast(char, b)` (exit 6, "only primitive numeric casts"), `c >= 'A'` (exit 6), `s == "hello"` (a7 exits 0, Zig fails: `cannot compare strings with ==`). `case '0'..'9':` on a `char` runs. | V |
| D10 | No heap buffers. `new [16]u8` exits 6 (`expected 'scalar or struct allocation'`). `Node :: struct { next: ref Node }` exits 6 (`expected 'ref unknown type'`). `new Box` with a nil check, `ret b`, and `del b` runs. | V |
| D11 | A `string` payload cannot be matched: `case .some(name):` on `Option(string)` exits 6 and names M33/M49. `Option(string)` as a return type checks. | V |
| D12 | `match io.read_line(buf[0..16])` exits 6: the checker types the call as void and demands a format string. `r := io.println_ok("x")` compiles and runs. | V |
| D13 | Wrapping `u64` math, shifts by literals, xor, and `%` under a `while y != 0` or `if bound != 0` guard run. FNV-1a over `[3]u8` printed `4452171178779021548`. Narrowing `cast(u8, d)` under `if d < 10` and float-to-int casts exit 6. | V |
| D15 | A checked accessor written in A7 passes the prover and removes most D7 failures. `at(xs, i, fallback)` and `put(xs, i, v)` each hold one guard. `bytes.copy`, `bytes.eq`, and a two-cursor `reverse` written through them ran (`4 true`, `4 -1 true`). | V |
| D16 | An import alias cannot equal a function name in the imported module. `sort :: import "std/sort"` with `sort($T) :: fn` inside exits 6 `Already defined: Import alias 'sort'`. The alias `sorting` runs. | V |
| D17 | A JSON event reader written in A7 (140 lines, no heap, no recursion) runs today. For the bytes of `{"a":[12,true]}` it printed `object_start 0..1`, `key 2..3`, `array_start 5..6`, `number 6..8`, `true 9..13`, `array_end 13..14`, `object_end 14..15`. Source: `ex/stdlib/std/json.a7`. | V |
| D14 | Function-pointer parameters run (`min_by(xs, less)` with `Less :: fn(i32, i32) bool`). Methods (`c.inc()`), `for i in 0..3`, variadic lowering, and one-line `if c { ret S{...} }` do not (exit 6, 5, 6, 5). | V |

#### 1. Scope

##### What "general purpose" should mean for A7 v1

Proposed definition: a program in the L44 class (text scanning, syntax
trees, symbol tables, multi-file tools) and an ordinary command-line
tool can be written with the stdlib alone, with no Zig written by the
user and no manual memory calls (L19, L21).

Concretely, v1 covers: console and file I/O with recoverable errors,
text and bytes, number parsing and formatting, math, growable lists,
maps, sorting and searching, arguments, environment, exit codes, time,
seeded random numbers, JSON and YAML parsing, and a test helper. Sources: L36 ("useful
libraries"), roadmap sequence step 5 ("strings, collections and
practical input/file/path operations"), roadmap milestones "Usable
core" and "Standard library and native boundary".

Constraints from the ledger that shape every API:

- L17, L19, L21: no allocator parameters and no manual free in stdlib
  signatures. This rules out the Zig convention of passing an
  allocator to each call.
- L42: `b := a` on a growable list shares one list. Copies are explicit.
- L39: prefer compile-time proof; checked execution is allowed where
  proof is unavailable. A bounds-checked `get` fits this.
- L41: native code goes through Zig. Application code does not manage
  raw native pointers.
- L31: `import "io"` and `import "math"` are stdlib spellings.
- L48: stdout is buffered; stderr flushes per call.
- L4, L5: explicit integer widths; `+ - *` wrap.
- L38: stdlib workloads count against the 1.10x C limit.

##### What stays out of v1

| Item | Source | Approval on disk |
| --- | --- | --- |
| Package registry | CLAUDE.md "Out of Scope", STATUS:225 | Yes (project rule) |
| Networking, TLS, HTTP | research 10 section 4, research 25 section 6 | None; research only |
| TOML, binary formats | roadmap B8 "NEVER", research 25 section 4 | None (`ledger-audit.md` row "Roadmap A6 ... B8 NEVER items, A8") |
| YAML anchors, aliases, tags, merge keys, multi-document streams | this proposal (3.22, decision U13) | None |
| Regex in the language; a regex library only "on a qualified use case" | roadmap B8, research 25 section 2 | None |
| Fresh crypto primitives | roadmap B8, research 25 section 3 | None |
| C++ interop | roadmap B8 | None |
| SIMD intrinsics, string interpolation, general overloading | roadmap A8 "Locked cuts" | None (PLAN.md P4-10; A8's "GC" cut contradicts L37) |
| Async syntax | roadmap A6 "never" | None (PLAN.md P4-10) |
| Calendar, time zones | research 16 section 7, research 25 section 5 | None |
| Tensors, concurrency | L36 (later tracks) | Yes |

JSON and YAML were out of v1 in the roadmap (B8: "JSON later.
YAML/TOML NEVER"). The user's 2026-10-04 message moves both in.

Seven of these rows rest on research files or this proposal only. `decisions.md:29-30`
says research recommendations are not approval. This proposal follows
them as working assumptions and lists them as decision U11.

#### 2. Survey

Every claim in this section is from memory (M). None was checked
against source this session.

| Language | How the small core is organized | What fits A7 | What does not fit |
| --- | --- | --- | --- |
| Zig std | One `std` namespace; `mem`, `fmt`, `fs`, `process`, `time`, `Random`, `ArrayList`, hash maps, `testing`. Containers take an allocator. Generic containers are functions that return types. Format strings are checked at compile time. | Compile-time format checking (A7 already checks placeholder counts). `testing` as an ordinary module. Caller-buffer APIs (`bufPrint`). | Allocator parameters (L17, L19, L21). |
| Go | Flat package list: `fmt`, `strings`, `bytes`, `strconv`, `os`, `io`, `sort`, `time`, `math`, `errors`, `path/filepath`. Slices and maps are builtins with reference identity. Errors are returned values. | The package split and names. Reference identity for growable collections matches L42. `strings` and `bytes` as mirror modules. `strconv` separate from `fmt`. | Interfaces (`io.Reader`), closures in `sort.Slice`, garbage collector. |
| Odin core | `core:fmt`, `strings`, `slice`, `os`, `time`, `math`, `mem`, `strconv`, `unicode/utf8`. Dynamic arrays and maps are language builtins. An implicit `context` carries the allocator. Free functions, no methods. | Free-function style matches A7 today (no methods). Builtin dynamic array and map: the compiler knows the type, the library holds the helpers. `strings.Builder` for growable text. | The visible `context` and explicit `delete`. |
| Rust core/std | `core` has no allocation and no OS; `alloc` adds heap types; `std` adds the OS. `Option` and `Result` are in `core` and in the prelude. | The three-layer split maps onto the phases here: phase A is the "core" layer (no heap), phase B the "alloc" layer, and OS modules sit beside both. Prelude for `Option`/`Result`. | Traits, iterators with closures, lifetimes. |
| Hare | Small modules (`fmt`, `strings`, `bytes`, `os`, `fs`, `io`, `strconv`, `sort`, `time`). Errors are tagged unions matched by the caller. Many functions write into caller buffers. | Tagged-union errors matched explicitly are what A7 has today. Caller-buffer APIs let phase A ship before a memory model. | Manual `free`. |
| C3 | `std::core`, `std::io`, `std::collections`, with generic modules and optionals for errors. | Generic container modules. | Macros, temp allocator calls visible to the user. |

Ideas that survive A7's limits (no recursion, no closures, value
semantics, no methods):

1. Free functions grouped by module, first argument is the subject
   (`strings.len(s)`). Odin and Go show this scales.
2. Errors as tagged unions matched by the caller (Hare). A7 has this.
3. Function-pointer parameters replace closures for `sort_by` (D14).
4. Caller-buffer variants (`format_i64(buf, v)`) need no allocator.
5. The compiler owns growable collection types; the library owns the
   helpers (Odin, Go). L42 forces this for A7.
6. Iterative algorithms only: insertion sort, heap sort, or iterative
   merge sort instead of recursive quicksort; explicit stacks for tree
   walks.

#### 3. Module catalog

Status words per signature:

- RUNS: real body, compiled and ran natively in the demo (D2).
- CHECKS: signature with a stub body passes `--mode pipeline --lib`.
  The body still has to be written or hooked.
- FAILS n: exits `n` today; the error follows.
- PLANNED: needs the named missing feature.

"Hook" means a typed registry entry lowered to a Zig helper (section
4). Zig helper names in the lowering lines are from memory of Zig std
and were not compiled against 0.16.0 (M).

Shared types used below. Today each file must declare them itself,
and a second declaration in any imported module exits 6 (D4):

```a7
Option :: union(tag) {
    some: $T,
    none: bool,
}
Result :: union(tag) {
    ok: $T,
    err: $E,
}
```

##### 3.1 `std/io` (hook; exists)

Purpose: console input and output.

```a7
print    :: fn(fmt: string, args: ..)                        // RUNS (registry)
println  :: fn(fmt: string, args: ..)                        // RUNS (registry)
eprintln :: fn(fmt: string, args: ..)                        // RUNS (registry)
eprint   :: fn(fmt: string, args: ..)                        // PLANNED: new registry row
println_ok :: fn(fmt: string, args: ..) Result(usize, IoErr) // statement form RUNS; match FAILS 6 (D12)
read_line  :: fn(buf: []u8) Result(usize, IoErr)             // FAILS 6 (D12); PLAN.md P1-4 second-read bug
flush      :: fn() Result(usize, IoErr)                      // PLANNED: new registry row
format_into :: fn(buf: []u8, fmt: string, args: ..) Result(usize, IoErr) // PLANNED: new registry row
```

The `args: ..` spelling parses (`--mode ast` exit 0) and exits 6 at
check: "Variadic parameters are parsed for future support". The
registry handles these calls without a declared signature, so the
lines above describe the call shape and are not A7 source.

- Errors: `IoErr :: enum { WriteFailed, FlushFailed, ReadFailed }`
  (matches `__a7_IoErr`, `a7/backends/zig.py:270`).
- Allocation: none. `read_line` fills the caller's buffer.
- Lowering: the existing `__a7_stdout_print`, `__a7_stderr_print`,
  `__a7_stdout_print_ok`, `__a7_stdin_read_line` helpers.
- Stays a hook because A7 has no variadics and the format string is
  checked at compile time.

```a7
io :: import "std/io"
main :: fn() {
    buf: [8]u8 = [0, 0, 0, 0, 0, 0, 0, 0]
    match io.read_line(buf[0..8]) {
        case .ok(n): { io.println("read {} bytes", n) }
        case .err(e): { io.eprintln("no input") }
    }
}
```

Status: parses; FAILS 6 today (D12): `expected 'string', got '[]u8'
(io format argument)` and `expected 'tagged union', got 'void'`.

`format_into` writes formatted text into a caller buffer (Zig
`std.fmt.bufPrint`, M). It sits in `std/io` because it shares the
format-string checker path; there is no separate `std/fmt` module in
this proposal. `IoErr` gains a `NoSpace` tag for it.

##### 3.2 `std/slices` (A7 source)

Purpose: checked element access and small generic slice helpers. This
module is what lets other stdlib code pass the index prover (D15).

```a7
at($T)       :: fn(xs: []$T, i: usize, fallback: $T) $T   // RUNS
put($T)      :: fn(xs: []$T, i: usize, v: $T) bool        // RUNS (through reverse)
swap($T)     :: fn(xs: []$T, i: usize, j: usize) bool     // RUNS (through reverse)
reverse($T)  :: fn(xs: []$T)                              // RUNS
contains($T) :: fn(xs: []$T, v: $T) bool                  // RUNS
count($T)    :: fn(xs: []$T, v: $T) usize                 // CHECKS (real body)
get($T)      :: fn(xs: []$T, i: usize) Option($T)         // FAILS 7 (D6)
```

- Errors: `at` returns the fallback when `i` is out of range. `put`
  and `swap` return false and change nothing. `get` is the `Option`
  form and waits for R3.
- Allocation: none. Lowering: ordinary A7. Each accessor is one
  compare; Zig can inline it (inference, not measured).

```a7
io :: import "std/io"
slices :: import "std/slices"
main :: fn() {
    xs: [4]i32 = [1, 2, 3, 4]
    slices.reverse(xs[0..4])
    io.println("{} {} {}", xs[0], slices.at(xs[0..4], 9, -1), slices.contains(xs[0..4], 3))
}
```

Status: RUNS, printed `4 -1 true`.

##### 3.3 `std/option`, `std/result` (A7 source)

Purpose: the two shared unions and small helpers.

```a7
is_some($T)   :: fn(o: Option($T)) bool                    // CHECKS in isolation (iso/g5)
unwrap_or($T) :: fn(o: Option($T), fallback: $T) $T        // CHECKS in isolation (iso2)
is_ok($T, $E) :: fn(r: Result($T, $E)) bool                // CHECKS in isolation (iso2)
ok_or($T, $E) :: fn(r: Result($T, $E), fallback: $T) $T    // CHECKS in isolation (iso2)
some($T)      :: fn(v: $T) Option($T)                      // FAILS 7 (D6)
```

The stub file `cat/option.a7` exits 7 because of `some`. Each of the
other four exits 0 in a file of its own.

- Errors: none. Allocation: none. Lowering: ordinary A7.
- There is no `unwrap` that panics in this proposal; see decision U2.

```a7
port := unwrap_or(parse_port(text), 8080)
```

##### 3.4 `std/strings` (A7 source over three hooks)

Purpose: read-only operations on `string` views.

```a7
len           :: fn(s: string) usize                // RUNS as an O(n) loop; hook makes it O(1)
eq            :: fn(a: string, b: string) bool      // CHECKS; body needs a hook (D9)
compare       :: fn(a: string, b: string) Order     // CHECKS; hook
starts_with   :: fn(s: string, prefix: string) bool // CHECKS; needs `byte_at` or a hook
ends_with     :: fn(s: string, suffix: string) bool // CHECKS
contains      :: fn(s: string, needle: string) bool // CHECKS
count_char    :: fn(s: string, needle: char) usize  // RUNS
index_of_char :: fn(s: string, needle: char) Option(usize) // see the last bullet
sub           :: fn(s: string, start: usize, end: usize) string  // CHECKS; hook (D8)
trim          :: fn(s: string) string               // CHECKS; needs `sub`
```

`Order :: enum { Less, Equal, Greater }`.

- Errors: none. `sub` clamps `start` and `end` to the length (proposed;
  decision U2 covers the alternative of returning `Option(string)`).
- Allocation: none. Every result is a view into the argument.
- Hooks needed: `len`, `eq`/`compare`, `sub`. Lowering: `s.len`,
  `std.mem.eql(u8, a, b)`, `std.mem.order`, `s[a..b]` (M).
- `index_of_char` returns `Option(usize)`. AGENTS.md "A7 Source Rules"
  reserves `isize` for signed offsets, and PLAN.md P3-27 flags the
  `-1` sentinel in `examples/025`. The demo ran an `isize`/`-1` draft
  of this function; the `Option(usize)` shape ran as `bytes.index_of`
  (3.6), not under this name.

```a7
io :: import "std/io"
strings :: import "std/strings"
main :: fn() {
    io.println("{} {}", strings.len("hello"), strings.count_char("banana", 'a'))
}
```

Status: RUNS today with the module at `<entry>/stdlib/std/strings.a7`;
printed `5 3`.

##### 3.5 `std/ascii` (A7 source)

Purpose: byte-range character classes.

```a7
is_digit    :: fn(c: char) bool   // RUNS (match on '0'..'9')
is_alpha    :: fn(c: char) bool   // CHECKS (two range arms)
is_space    :: fn(c: char) bool   // CHECKS (== chain)
is_upper    :: fn(c: char) bool   // FAILS 6 as `c >= 'A' and c <= 'Z'` (PLAN.md P2-38); write with a range arm
to_upper    :: fn(c: char) char   // CHECKS; body needs char arithmetic (P2-38) or a 26-arm match
to_lower    :: fn(c: char) char   // CHECKS; same
digit_value :: fn(c: char) i32    // RUNS as a 10-arm match; -1 when not a digit
```

- Errors: none. Allocation: none. Lowering: ordinary A7.

```a7
io :: import "std/io"
ascii :: import "std/ascii"
main :: fn() {
    digits := 0
    for ch in "a1b22" {
        if ascii.is_digit(ch) {
            digits += ascii.digit_value(ch)
        }
    }
    io.println("{}", digits)
}
```

Status: RUNS, printed `5`.

##### 3.6 `std/bytes` (A7 source; `std/mem` folded in)

Purpose: operations on `[]u8`. I propose no separate `std/mem`: SPEC
11.2's `mem_alloc`, `mem_free`, `mem_realloc` conflict with L19, and
the remaining four functions are these.

```a7
fill        :: fn(dst: []u8, value: u8)              // RUNS
index_of    :: fn(xs: []u8, value: u8) Option(usize) // RUNS
copy        :: fn(dst: []u8, src: []u8) usize        // RUNS when written through at/put (D15); direct form FAILS 6 (D7)
eq          :: fn(a: []u8, b: []u8) bool             // RUNS through at (D15); direct form FAILS 6 (D7)
compare     :: fn(a: []u8, b: []u8) Order            // PLANNED; same shape as eq
from_string :: fn(s: string) []u8                    // FAILS 6: "expected '[]u8', got 'string'"; hook
```

- Errors: none. `copy` copies `min(dst.len, src.len)` bytes and returns
  the count. `index_of` returns `.none` when absent.
- Allocation: none.
- Lowering: A7 source. `from_string` is a hook (the two types share a
  Zig representation, M). `copy` could later lower to `@memcpy` if the
  L38 measurements ask for it.

```a7
io :: import "std/io"
bytes :: import "std/bytes"
main :: fn() {
    src: [4]u8 = [1, 2, 3, 4]
    dst: [4]u8 = [0, 0, 0, 0]
    n := bytes.copy(dst[0..4], src[0..4])
    io.println("{} {}", n, bytes.eq(dst[0..4], src[0..4]))
    match bytes.index_of(dst[0..4], 3) {
        case .some(i): { io.println("found at {}", i) }
        case .none: { io.println("absent") }
    }
}
```

Status: RUNS, printed `4 true` and `found at 2`.

A caution on probe reading: `cat/bytes.a7` standalone reported only the
`from_string` type error. The direct `copy` and `eq` index errors
appeared only when the module was imported without that function. A
type error stops the pipeline before the safety pass.

##### 3.7 `std/math` (hook + A7 source)

Purpose: numeric functions and constants.

```a7
// registry today, RUNS: sqrt abs floor ceil sin cos tan log exp min max
pow   :: fn(base: f64, exp: f64) f64                       // FAILS 6 today: "no function 'pow'"; new hook
round :: fn(x: f64) f64                                    // new hook (PLAN.md P3-26: examples/043 names `round`)
PI :: 3.141592653589793                                    // CHECKS as a constant in an A7 file; `math.pi` FAILS 6
clamp($T) :: fn(x: $T, lo: $T, hi: $T) $T where T: Numeric // RUNS
gcd   :: fn(a: u64, b: u64) u64                            // RUNS
sign  :: fn(x: i64) i64                                    // CHECKS
is_nan :: fn(x: f64) bool                                  // CHECKS
```

- Errors: none in this list. Checked integer arithmetic
  (`add_checked :: fn(a: i64, b: i64) Option(i64)`) belongs to the
  numerics packet (roadmap A4), not here.
- Allocation: none.
- Lowering: hooks to `@sqrt`-style builtins and `std.math.pow` (M);
  the rest is A7.
- `std/math` is a virtual module today. Mixing registry functions and
  A7 functions under one name needs the rule in section 4.

```a7
io :: import "std/io"
math :: import "std/math"
mathx :: import "std/mathx"
main :: fn() {
    io.println("{} {} {}", math.sqrt(16.0), mathx.gcd(48, 18), mathx.clamp(15, 0, 10))
}
```

Status: RUNS, printed `4 6 10`. The probe put the A7 functions in a
module named `mathx` because `std/math` is registry-only today.

##### 3.8 `std/conv` (A7 source)

Purpose: text to number and number to text, no format string.

```a7
parse_i64  :: fn(s: string) Result(i64, ParseErr)                       // CHECKS (stub body)
parse_u64  :: fn(s: string) Result(u64, ParseErr)                       // CHECKS
parse_f64  :: fn(s: string) Result(f64, ParseErr)                       // CHECKS; hook body (std.fmt.parseFloat, M)
parse_bool :: fn(s: string) Result(bool, ParseErr)                      // CHECKS; needs strings.eq
format_i64 :: fn(buf: []u8, value: i64) Result(usize, FmtErr)           // CHECKS; body blocked by D13 narrowing cast
format_f64 :: fn(buf: []u8, value: f64, digits: u8) Result(usize, FmtErr) // CHECKS; hook body
```

`ParseErr :: enum { Empty, BadDigit, Overflow }`.

- Allocation: none; output goes to the caller's buffer.
- `parse_i64` is writable in A7 today with `for ch in s` and
  `ascii.digit_value`: `iso2/parse_run.a7` printed `ok 123` for
  `"123"` and `err` for `"1x"`. The first draft used `cast(i32, ch)`,
  which exits 6. Overflow detection needs the numerics packet or a
  compare-before-multiply guard.

```a7
io :: import "std/io"
conv :: import "std/conv"
main :: fn() {
    match conv.parse_i64("42") {
        case .ok(v): { io.println("{}", v) }
        case .err(e): { io.eprintln("not a number") }
    }
}
```

Status: compiles and runs against the stub module, which always
returns `.err` (printed `not a number`). The real loop ran as a
user-defined `parse` in `iso2/parse_run.a7`.

##### 3.9 `std/sort` (A7 source)

Purpose: sort and search slices.

```a7
sort_i32 :: fn(xs: []i32)                                         // RUNS (insertion sort, nested single guards)
sort($T) :: fn(xs: []$T) where T: Numeric                         // RUNS across modules on i32 and f64 (iso2/xmod_generic)
sort_by($T) :: fn(xs: []$T, less: fn($T, $T) bool)                // parameter shape CHECKS (iso/g7)
is_sorted($T) :: fn(xs: []$T) bool where T: Numeric               // CHECKS (stub)
index_of($T) :: fn(xs: []$T, target: $T) Option(usize)            // CHECKS (iso/g8)
binary_search($T) :: fn(xs: []$T, target: $T) Option(usize) where T: Numeric // CHECKS (stub)
// reverse lives in std/slices (3.2)
min_of($T) :: fn(xs: []$T) Option($T) where T: Numeric            // FAILS 7 (D6)
```

The stub file `cat/sort.a7` exits 7 because of `min_of` (D6). With
`min_of` removed the file exits 0 (`iso2/sort_generic.a7`). A program
that imports the generic `sort` from a bundled-style module printed
`1 5` for `[4, 2, 5, 1, 3]` and `0.5 2.5` for `[2.5, 0.5, 1.5]`.

- Errors: none. Allocation: none (in place).
- Algorithm: insertion sort below a small length, then iterative heap
  sort. No recursion, no auxiliary buffer. Stable sort (iterative
  merge) needs a scratch buffer and waits for phase B.
- The index proof costs: `sort_i32` needs three nested `if` guards per
  swap today. `slices.swap` (3.2) hides them.
- D16: with a function named `sort` inside, the alias `sort` exits 6.
  Until PLAN.md P2-8 is fixed, callers must pick another alias.

```a7
io :: import "std/io"
sorting :: import "std/sort"
main :: fn() {
    xs: [5]i32 = [4, 2, 5, 1, 3]
    sorting.sort(xs[0..5])
    match sorting.index_of(xs[0..5], 4) {
        case .some(i): { io.println("4 is at {}", i) }
        case .none: { io.println("absent") }
    }
}
```

Status: RUNS, printed `4 is at 3`. With the alias `sort` it exits 6.

##### 3.10 `std/hash` (A7 source)

Purpose: non-cryptographic hashes for maps and checksums.

```a7
fnv1a     :: fn(data: []u8) u64      // RUNS; `fnv1a("key" bytes)` = 4452171178779021548
of_string :: fn(s: string) u64       // CHECKS; body blocked: no char-to-u64 cast (D9); hook or `bytes.from_string`
of_u64    :: fn(x: u64) u64          // CHECKS (real body, multiply-xorshift mix)
combine   :: fn(a: u64, b: u64) u64  // CHECKS (real body)
fnv1a_seeded :: fn(data: []u8, seed: u64) u64 // RUNS; for per-process map seeds
```

- Errors: none. Allocation: none. Lowering: ordinary A7.
- Not for security. The doc comment must say so (roadmap B8 crypto rule).

```a7
io :: import "std/io"
hash :: import "std/hash"
main :: fn() {
    key: [3]u8 = [107, 101, 121]
    io.println("{}", hash.fnv1a(key[0..3]))
    io.println("{}", hash.fnv1a_seeded(key[0..3], 7) != hash.fnv1a(key[0..3]))
}
```

Status: RUNS, printed `4452171178779021548` and `true`.

##### 3.11 `std/random` (A7 source + one hook)

Purpose: seeded pseudo-random numbers.

```a7
Rng :: struct {
    state: u64
}
seeded   :: fn(seed: u64) Rng              // RUNS
next_u64 :: fn(r: ref Rng) u64             // RUNS (xorshift64)
below    :: fn(r: ref Rng, bound: u64) u64 // RUNS; returns 0 when bound is 0
next_f64 :: fn(r: ref Rng) f64             // CHECKS (real body)
shuffle($T) :: fn(r: ref Rng, xs: []$T)    // CHECKS as stub; body writable with slices.swap (D15), not run
from_os  :: fn() Rng                       // hook: seed from the OS
```

- Errors: none. Allocation: none; the caller holds the `Rng` value.
- Explicit state instead of a hidden global keeps runs reproducible.
  A module-level `state: u64` global also runs today (probe q15).
- `below` uses `%`, which has modulo bias. Acceptable for v1; the doc
  must say it.

```a7
io :: import "std/io"
random :: import "std/random"
main :: fn() {
    rng := random.seeded(42)
    io.println("{}", random.below(rng, 6) < 6)
}
```

Status: RUNS, printed `true`.

##### 3.12 `std/time` (hook + A7 source)

```a7
Instant :: struct {
    ns: i64
}
now_unix_ms :: fn() i64                              // hook
monotonic   :: fn() Instant                          // hook
elapsed_ms  :: fn(start: Instant, end: Instant) i64  // CHECKS (real body)
sleep_ms    :: fn(ms: u64)                           // hook
since_ms    :: fn(start: Instant) i64                // CHECKS (real body over monotonic)
now_unix_s  :: fn() i64                              // CHECKS (real body over now_unix_ms)
```

- Errors: none. A clock failure panics (decision U2).
- Allocation: none.
- Lowering: Zig 0.16 moved clocks and sleep behind `std.Io` (the
  backend already stores `init.io` in `__a7_io`, `zig.py:293-294`).
  Exact 0.16 call names are unchecked (M).
- No calendar, no time zones (section 1).

```a7
io :: import "std/io"
time :: import "std/time"
main :: fn() {
    start := time.monotonic()
    time.sleep_ms(10)
    io.println("{} ms", time.since_ms(start))
}
```

Status: compiles and runs against a stub module whose hooks return 0
(printed `0 ms`). The real hooks do not exist.

##### 3.13 `std/os` (hook)

Purpose: arguments, environment, exit.

```a7
arg_count :: fn() usize                                 // hook; CHECKS
arg_or    :: fn(index: usize, fallback: string) string  // hook; CHECKS
arg       :: fn(index: usize) Option(string)            // CHECKS; caller's match FAILS 6 (D11)
env_or    :: fn(name: string, fallback: string) string  // hook; CHECKS
env       :: fn(name: string) Option(string)            // same D11 blocker
exit      :: fn(code: u8)                               // hook; flushes stdout first (L48)
```

- Errors: absence is `Option`. Until `string` payloads bind (PLAN.md
  P1-1, M33/M49), phase A ships only the `_or` forms.
- Allocation: none visible. Argument and environment strings live for
  the whole process.
- Lowering: `std.process.Init` carries arguments and environment in
  0.16 (M; the backend's `main(init: std.process.Init)` is at
  `zig.py:293`). `exit` lowers to `std.process.exit` after
  `__a7_stdout_flush()`.
- `main :: fn()` keeps its shape (SPEC 10.2.2). Arguments come from
  the module, not from `main` parameters.

```a7
os :: import "std/os"
io :: import "std/io"
main :: fn() {
    name := os.arg_or(1, "world")
    io.println("hello {}", name)
}
```

Status: compiles and runs against a stub module (printed
`hello world`). No `std/os` hook exists.

##### 3.14 `std/fs` (hook)

Purpose: whole-file operations first, handles second.

```a7
FsErr :: enum { NotFound, Denied, TooLarge, IsDir, Io }
read_into   :: fn(path: string, buf: []u8) Result(usize, FsErr)    // CHECKS; hook
write_bytes :: fn(path: string, data: []u8) Result(usize, FsErr)   // CHECKS; hook
write_text  :: fn(path: string, text: string) Result(usize, FsErr) // CHECKS; hook
append_text :: fn(path: string, text: string) Result(usize, FsErr) // CHECKS; hook
exists      :: fn(path: string) bool                               // CHECKS; hook
remove      :: fn(path: string) Result(bool, FsErr)                // CHECKS; hook
make_dir    :: fn(path: string) Result(bool, FsErr)                // CHECKS; hook
// phase B
read_text   :: fn(path: string) Result(Text, FsErr)                // PLANNED: owning text type
open        :: fn(path: string) Result(File, FsErr)                // CHECKS as a signature
close       :: fn(f: ref File)                                     // CHECKS as a signature
```

- Errors: every OS failure maps to one `FsErr` tag. `read_into`
  returns `TooLarge` when the file exceeds the buffer, and writes
  nothing past it.
- Allocation: none in phase A. `read_text` allocates and waits for
  the memory decision.
- Lowering: `std.Io.Dir.cwd()` file calls with the stored `__a7_io`
  (M, unchecked against 0.16).
- `Result(bool, FsErr)` for `remove` is a workaround: a payload-free
  `ok` tag needs a unit type, which A7 lacks. Decision U2 covers it.
- Directory listing waits for phase B (it returns a list of names).

```a7
io :: import "std/io"
fs :: import "std/fs"
main :: fn() {
    buf: [8]u8 = [0, 0, 0, 0, 0, 0, 0, 0]
    match fs.read_into("notes.txt", buf[0..8]) {
        case .ok(n): { io.println("{} bytes", n) }
        case .err(e): { io.eprintln("cannot read notes.txt") }
    }
}
```

Status: compiles and runs against a stub module that always returns
`.err` (printed `cannot read notes.txt`). The real hook needs R1 and
R13. A real program wants a larger buffer; an uninitialized
`buf: [4096]u8` is PLAN.md P2-42 / D-G today.

##### 3.15 `std/path` (A7 source over `strings.sub`)

```a7
base      :: fn(p: string) string   // CHECKS as stub; needs strings.sub
dir       :: fn(p: string) string   // CHECKS as stub
ext       :: fn(p: string) string   // CHECKS as stub
is_abs    :: fn(p: string) bool     // CHECKS (real body)
join_into :: fn(buf: []u8, a: string, b: string) Result(usize, PathErr) // CHECKS as stub
```

- Linux `/` separator only (roadmap: Linux x86-64 is the first target).
- Allocation: none. `join` returning an owning string is phase B.

```a7
io :: import "std/io"
path :: import "std/path"
main :: fn() {
    io.println("{} {}", path.base("/tmp/a.txt"), path.is_abs("/tmp/a.txt"))
}
```

Status: compiles and runs against a stub whose `base` returns its
argument (printed `/tmp/a.txt true`). `is_abs` has its real body.

##### 3.16 `std/testing` (A7 source)

Purpose: checks for golden programs, with a count and an exit status.

```a7
Tally :: struct {
    passed: u32
    failed: u32
}
check        :: fn(t: ref Tally, cond: bool, name: string)             // RUNS
check_eq_i64 :: fn(t: ref Tally, got: i64, want: i64, name: string)    // RUNS
check_eq($T) :: fn(t: ref Tally, got: $T, want: $T, name: string)      // CHECKS
report       :: fn(t: Tally) bool                                      // RUNS
panic        :: fn(msg: string)                                        // hook: print, flush, abort
```

- Errors: none; failures are counted and printed to stderr.
- Allocation: none.
- `panic` must flush stdout first (PLAN.md P2-45 drops buffered output
  on a panic today).

```a7
io :: import "std/io"
strings :: import "std/strings"
testing :: import "std/testing"
main :: fn() {
    t := Tally{passed: 0, failed: 0}
    testing.check(t, strings.len("hello") == 5, "strings.len")
    ok := testing.report(t)
}
```

Status: RUNS, printed `1 passed, 0 failed`. `Tally` is written bare
because `testing.Tally` does not parse (D4). The D2 demo printed
`FAIL deliberate failure: got 2, want 3` and `13 passed, 1 failed`.

##### 3.17 `std/utf8`, `std/hex`, `std/base64` (A7 source)

```a7
valid         :: fn(data: []u8) bool                                // CHECKS (stub)
count_runes   :: fn(data: []u8) Result(usize, Utf8Err)              // CHECKS (stub)
decode_rune   :: fn(data: []u8, at: usize) Result(u32, Utf8Err)     // CHECKS (stub)
encode_rune   :: fn(buf: []u8, rune: u32) Result(usize, EncErr)     // CHECKS (stub)
hex_encode    :: fn(dst: []u8, src: []u8) Result(usize, EncErr)     // CHECKS (stub)
hex_decode    :: fn(dst: []u8, src: []u8) Result(usize, EncErr)     // CHECKS (stub)
base64_encode :: fn(dst: []u8, src: []u8) Result(usize, EncErr)     // CHECKS (stub)
```

- Allocation: none; caller buffers.
- Bodies read one slice and write another at different indexes. D15
  covers the indexing; the D13 narrowing-cast limit still blocks them.
  Phase B.

```a7
io :: import "std/io"
utf8 :: import "std/utf8"
main :: fn() {
    src: [2]u8 = [202, 254]
    dst: [4]u8 = [0, 0, 0, 0]
    match utf8.hex_encode(dst[0..4], src[0..2]) {
        case .ok(n): { io.println("{} hex digits", n) }
        case .err(e): { io.eprintln("buffer too small") }
    }
}
```

Status: compiles and runs against a stub that always returns `.err`
(printed `buffer too small`).
- `char` is a byte today (SPEC 2.1; PLAN.md P2-21 notes `'€'` into
  `u8`). A rune type is a language decision and is not proposed here.

##### 3.18 `std/list` (compiler type + hooks; phase B)

Purpose: growable array.

```a7
make($T)  :: fn() List($T)                               // PLANNED
push($T)  :: fn(l: List($T), value: $T)                  // PLANNED
pop($T)   :: fn(l: List($T)) Option($T)                  // PLANNED; D6 and D11 apply
get($T)   :: fn(l: List($T), index: usize) Option($T)    // PLANNED; roadmap B3
set($T)   :: fn(l: List($T), index: usize, value: $T) bool // PLANNED
len($T)   :: fn(l: List($T)) usize                       // PLANNED
items($T) :: fn(l: List($T)) []$T                        // PLANNED; view lifetime is gate M13
copy($T)  :: fn(l: List($T)) List($T)                    // PLANNED; the explicit copy L42 requires
clear($T) :: fn(l: List($T))                             // PLANNED
```

My stub (`cat/list.a7`) exits 6 on a stub artifact (a phantom field
needed to carry `$T`), so no row here is verified beyond parsing.

Why this cannot be an A7 struct today:

1. L42: `b := a` shares the list. A7 structs copy on assignment, so a
   struct `{ptr, len, cap}` would give two lengths over one buffer.
2. D10: no heap buffer of runtime size exists (`new [N]T` rejected).
3. D7: `l.items[l.len]` is not provable from a field-loaded length.
4. D6: `make` and `pop` return generic types from generic functions.

So `List(T)` is a compiler-known handle type. The parameter is `List($T)`,
not `ref List($T)`, because the value is already a shared handle.

- Errors: `get` and `pop` return `Option`. Growth failure: decision
  U6 (gate M2: `try_push` vs stop).
- Allocation: the runtime, by whichever mechanism wins Wave B. No
  allocator parameter (L17, L19).
- Lowering: a Zig generic `__a7_List(T)` holding `std.ArrayList(T)`
  behind a pointer (M).

```a7
io :: import "std/io"
list :: import "std/list"
main :: fn() {
    xs := list.make(i32)
    list.push(xs, 3)
    ys := xs
    list.push(ys, 4)
    io.println("{}", list.len(xs))
}
```

Status: parses (`--mode ast` exit 0); pipeline exits 3 `Module
'std/list' not found`. Intended output is `2`: `ys` and `xs` are one
list (L42). `list.make(i32)` passes a type as an argument, which
exits 6 for user generics today (D5).

##### 3.19 `std/map`, `std/set` (compiler type + hooks; phase B)

```a7
make($K, $V)   :: fn() Map($K, $V)                          // PLANNED
put($K, $V)    :: fn(m: Map($K, $V), key: $K, value: $V)    // PLANNED
get($K, $V)    :: fn(m: Map($K, $V), key: $K) Option($V)    // PLANNED
has($K, $V)    :: fn(m: Map($K, $V), key: $K) bool          // PLANNED
remove($K, $V) :: fn(m: Map($K, $V), key: $K) bool          // PLANNED
len($K, $V)    :: fn(m: Map($K, $V)) usize                  // PLANNED
```

- Keys in v1: integers, `bool`, `char`, enums, `string`. Struct keys
  need derived equality and hashing (research 03 section 4 step 4),
  which is a language feature and is not proposed here.
- Iteration order: insertion order (proposed), so golden outputs are
  stable. Research 03 section 5 asks for hash determinism (M40).
- `Set(K)` is `Map(K, bool)` with `add`, `has`, `remove`, `len`.
- Lowering: Zig `std.AutoArrayHashMap` / `std.StringArrayHashMap`,
  which keep insertion order (M).
- Same four blockers as `List`, plus string equality (D9).

```a7
io :: import "std/io"
map :: import "std/map"
main :: fn() {
    counts := map.make(string, i64)
    map.put(counts, "a", 1)
    match map.get(counts, "a") {
        case .some(n): { io.println("{}", n) }
        case .none: { io.println("absent") }
    }
}
```

Status: parses; pipeline exits 3 `Module 'std/map' not found`.

##### 3.20 `std/ring` (A7 source; phase A if D6 is fixed)

Purpose: fixed-capacity queue over caller storage. It gives worklists
(the no-recursion idiom) before the heap exists.

```a7
Ring :: struct {
    data: []$T
    head: usize
    count: usize
}
over($T)      :: fn(storage: []$T) Ring($T)           // FAILS 7 (D6)
push_back($T) :: fn(r: ref Ring($T), value: $T) bool  // parameter shape CHECKS; body hits D7
pop_front($T) :: fn(r: ref Ring($T)) Option($T)       // FAILS 7 (D6)
is_full($T)   :: fn(r: Ring($T)) bool                 // CHECKS (real body, iso2)
is_empty($T)  :: fn(r: Ring($T)) bool                 // PLANNED; same shape as is_full
len($T)       :: fn(r: Ring($T)) usize                // PLANNED
```

- Errors: `push_back` returns false when full. Allocation: none.
- This module is the smallest test of "containers in A7 source". It
  fails today on D6. D15 covers its indexing (not run for this module).

```a7
io :: import "std/io"
ring :: import "std/ring"
main :: fn() {
    storage: [4]usize = [0, 0, 0, 0]
    work := ring.over(storage[0..4])
    ok := ring.push_back(work, 2)
    match ring.pop_front(work) {
        case .some(node): { io.println("visit {}", node) }
        case .none: { io.println("done") }
    }
}
```

Status: parses; pipeline exits 3 `Module 'std/ring' not found`.

##### 3.21 `std/json` (A7 source; reader and writer in phase A)

Purpose: read and write JSON without a heap. The reader is a pull
parser: each `next` call returns one event that points into the input
bytes. Nesting is a counter and a bit stack inside the reader, so no
recursion is needed.

```a7
Kind :: enum { ObjectStart, ObjectEnd, ArrayStart, ArrayEnd, Key, String, Number, True, False, Null, End, Invalid }
JsonErr :: enum { Syntax, TooDeep, NoSpace, NotANumber, BadEscape, WrongKind }
Event :: struct {
    kind: Kind
    start: usize
    end: usize
}
reader        :: fn(data: []u8) Reader                                   // RUNS
next          :: fn(r: ref Reader) Event                                 // RUNS (D17)
kind_name     :: fn(k: Kind) string                                      // RUNS
skip_value    :: fn(r: ref Reader) bool                                  // CHECKS (stub)
text_is       :: fn(r: Reader, ev: Event, want: string) bool             // CHECKS (stub); body needs R7
number_f64    :: fn(r: Reader, ev: Event) Result(f64, JsonErr)           // CHECKS (stub)
number_i64    :: fn(r: Reader, ev: Event) Result(i64, JsonErr)           // CHECKS (stub)
unescape_into :: fn(r: Reader, ev: Event, buf: []u8) Result(usize, JsonErr) // CHECKS (stub); body needs R23
validate      :: fn(data: []u8) Result(usize, JsonErr)                   // CHECKS (stub)
// writer over a caller buffer
writer       :: fn(buf: []u8) Writer                                     // CHECKS (stub)
begin_object :: fn(w: ref Writer)                                        // CHECKS (stub); also end_object, begin_array, end_array
key          :: fn(w: ref Writer, name: string)                          // CHECKS (stub)
put_string   :: fn(w: ref Writer, value: string)                         // CHECKS (stub); also put_i64, put_f64, put_bool, put_null
finish       :: fn(w: Writer) Result(usize, JsonErr)                     // CHECKS (stub)
```

- Errors: a malformed input yields one `Invalid` event, then `End`.
  `validate` walks the whole input first and returns the byte offset
  of the first error. Nesting deeper than 64 gives `TooDeep`. The
  writer records the first failure and `finish` reports it, so calls
  need no per-call match.
- Allocation: none. Events hold offsets into the caller's bytes.
  A string event with escapes is copied out with `unescape_into`.
- Lowering: ordinary A7. `number_f64` uses the `conv.parse_f64` hook.
- An event is a struct, not a union with a text payload, because a
  `string` payload cannot be matched today (D11).
- The probe reader does not validate: it skips commas and colons as
  whitespace and trusts the first letter of `true`, `false`, `null`.
  The shipped reader must track "expect value / expect key / expect
  comma" per level. That is a state enum plus the bit stack; still no
  recursion.
- Input is `[]u8`. A `string` literal cannot become `[]u8` today (D9),
  so the probe spelled the document as byte values.

```a7
io :: import "std/io"
json :: import "std/json"
main :: fn() {
    // the bytes of {"a":[12,true]}
    text: [15]u8 = [123, 34, 97, 34, 58, 91, 49, 50, 44, 116, 114, 117, 101, 93, 125]
    r := json.reader(text[0..15])
    running := true
    while running {
        ev := json.next(r)
        if ev.kind == Kind.End {
            running = false
        } else {
            io.println("{} {}..{}", json.kind_name(ev.kind), ev.start, ev.end)
        }
    }
    io.println("depth seen {}", r.depth)
}
```

Status: RUNS. Output: `object_start 0..1`, `key 2..3`,
`array_start 5..6`, `number 6..8`, `true 9..13`, `array_end 13..14`,
`object_end 14..15`, `depth seen 2`. With `bytes.from_string` (R7) the
second line of `main` becomes `r := json.reader(bytes.from_string(doc))`.

##### 3.22 `std/yaml` (A7 source; reader in phase A, subset)

Purpose: read configuration-style YAML with the same event model as
`std/json`.

Proposed subset (decision U13). YAML rules here are from memory (M):

- In: block mappings and block sequences nested by space indentation;
  flow sequences `[a, b]` and flow mappings `{a: b}`; plain,
  single-quoted, and double-quoted scalars; `|` and `>` block scalars;
  `#` comments; one document with an optional leading `---`.
- Scalar typing follows the YAML 1.2 core schema: `null` and `~`;
  `true` and `false`; integers; floats; everything else is text. `no`,
  `yes`, `on`, `off` are text.
- Out, reported as `Unsupported` with a line number: anchors (`&a`),
  aliases (`*a`), tags (`!t`), merge keys (`<<`), complex keys (`?`),
  more than one document. Tabs in indentation report `TabIndent`.
- Reason for the cut: aliases let a small file expand without bound,
  the failure research 25 section 4 names. Without aliases the
  document is a tree, the same shape as JSON.

```a7
Kind :: enum { MapStart, MapEnd, SeqStart, SeqEnd, Key, Scalar, DocStart, End, Invalid }
ScalarKind :: enum { Null, Bool, Int, Float, Text }
YamlErr :: enum { Syntax, BadIndent, TabIndent, TooDeep, Unsupported, NoSpace, WrongKind }
Event :: struct {
    kind: Kind
    start: usize
    end: usize
    line: u32
}
next         :: fn(r: ref Reader) Event                                  // CHECKS (stub)
error_of     :: fn(r: Reader) YamlErr                                    // CHECKS (stub)
scalar_kind  :: fn(r: Reader, ev: Event) ScalarKind                      // CHECKS (stub)
text_is      :: fn(r: Reader, ev: Event, want: string) bool              // CHECKS (stub)
scalar_i64   :: fn(r: Reader, ev: Event) Result(i64, YamlErr)            // CHECKS (stub)
scalar_f64   :: fn(r: Reader, ev: Event) Result(f64, YamlErr)            // CHECKS (stub)
scalar_bool  :: fn(r: Reader, ev: Event) Result(bool, YamlErr)           // CHECKS (stub)
unquote_into :: fn(r: Reader, ev: Event, buf: []u8) Result(usize, YamlErr) // CHECKS (stub)
skip_value   :: fn(r: ref Reader) bool                                   // CHECKS (stub)
validate     :: fn(data: []u8) Result(usize, YamlErr)                    // CHECKS (stub)
```

- Errors: as `std/json`, plus a line number on each event. `MapEnd`
  and `SeqEnd` are produced when indentation drops.
- Allocation: none. The reader holds an indentation stack of 64 levels
  as a fixed array field. Writing to that field with a field-loaded
  depth needs a `slices.put`-style accessor (D15) or R14.
- Lowering: ordinary A7. No Zig YAML library exists in Zig std (M), so
  a hook is not an option; this module is A7 source or nothing.
- No YAML writer in v1. `std/json` output is valid YAML flow style (M).
- `Kind`, `Event`, and `Reader` collide with the `std/json` names
  while types share one namespace (D4): a program that imports both
  exits 6. Until R9, the names carry a prefix (`YamlKind`, `YamlEvent`).

```a7
io :: import "std/io"
yaml :: import "std/yaml"
main :: fn() {
    // bytes of "port: 8080\n"
    text: [11]u8 = [112, 111, 114, 116, 58, 32, 56, 48, 56, 48, 10]
    r := yaml.reader(text[0..11])
    key := yaml.next(r)
    value := yaml.next(r)
    match yaml.scalar_i64(r, value) {
        case .ok(port): { io.println("port {}", port) }
        case .err(e): { io.eprintln("port is not a number") }
    }
}
```

Status: compiles and runs against a stub module whose `next` returns
`End` and whose `scalar_i64` returns `.err` (printed
`port is not a number`). Intended output is `port 8080`. No YAML
reader body was written; the signatures pass `--mode pipeline --lib`
over stub bodies (`cat2/yaml_api.a7`, exit 0).

##### 3.23 `std/data` (document tree for JSON and YAML; phase B)

Purpose: parse a whole document into a tree and look values up by key
or index. One tree type serves both formats.

```a7
ValueKind :: enum { Null, Bool, Number, Text, List, Map }
DataErr :: enum { Syntax, TooDeep, Unsupported, WrongKind }
parse_json :: fn(text: []u8) Result(Doc, DataErr)   // CHECKS (stub)
parse_yaml :: fn(text: []u8) Result(Doc, DataErr)   // CHECKS (stub)
root    :: fn(d: Doc) Value                         // CHECKS (stub)
kind    :: fn(v: Value) ValueKind                   // CHECKS (stub)
get     :: fn(v: Value, key: string) Option(Value)  // CHECKS (stub)
at      :: fn(v: Value, index: usize) Option(Value) // CHECKS (stub)
len     :: fn(v: Value) usize                       // CHECKS (stub)
as_f64  :: fn(v: Value) Option(f64)                 // CHECKS (stub); also as_i64, as_bool
as_text :: fn(v: Value) Option(string)              // CHECKS as a signature; the caller's match FAILS 6 (D11)
text_or :: fn(v: Value, fallback: string) string    // CHECKS (stub)
to_json :: fn(d: Doc, buf: []u8) Result(usize, DataErr) // PLANNED
```

- Design: `Doc` owns a flat node table. `Value` is a small copyable
  struct `{doc, node}` holding an index, so it binds in a `match`
  today. Children link by index (first child, next sibling), the
  pattern `examples/025` and `026` use, so no self-referential `ref`
  is needed (D10). The builder runs the event reader with an explicit
  stack of open containers.
- Errors: `parse_*` returns `DataErr`. Lookups return `Option`.
- Allocation: the node table and copied text grow, so this module
  needs `List` and owning text, and waits for the memory decision.
  A phase A variant over caller storage is possible:
  `parse_json_into(text, nodes: []Node) Result(Doc, DataErr)`.
- Lowering: A7 source over `std/list`.

```a7
io :: import "std/io"
data :: import "std/data"
main :: fn() {
    src: [2]u8 = [123, 125]
    match data.parse_json(src[0..2]) {
        case .ok(doc): {
            match data.get(data.root(doc), "port") {
                case .some(v): { io.println("{}", data.text_or(v, "?")) }
                case .none: { io.println("no port") }
            }
        }
        case .err(e): { io.eprintln("bad json") }
    }
}
```

Status: compiles and runs against a stub module that always returns
`.err` (printed `bad json`; `cat2/tree_use.a7`, imported as
`./tree_api`). The nested match over `Result(Doc, DataErr)` and
`Option(Value)` type-checks today.

##### 3.24 Later modules (phase C)

| Module | Sketch | Blocker |
| --- | --- | --- |
| `std/text` | Owning, growable text: `make`, `push_str`, `push_char`, `view`, `len` (phase B) | Memory decision; research 03 section 3 `String` |
| `std/process` | `run :: fn(cmd: List(string)) Result(RunResult, ProcErr)` | `List`, owning text |
| `std/log` | Levels over `io.eprintln` | Variadics or a hook |
| `std/net` | `dial_tcp`, `listen_tcp` | Concurrency track (research 10 section 4) |

#### 4. Architecture

##### Options

(a) Registry only. Every function is a Python `StdlibFunction` plus
Zig emission in `a7/backends/zig.py`.

- Typing: each function needs checker code. Today `std.io.*` returns
  `VOID` and `std.math.*` goes through `_validate_math_call`
  (`type_checker.py:2151-2156`).
- Cost: the io family alone spans about 140 lines of emission
  (`zig.py:250-303`, `2190-2210`, `2812-2880`). One hundred functions at
  that rate grows a 3,097-line file PLAN.md Phase 5 already wants split.
- Generic containers lower straight to Zig generics, so D6 and D7 do
  not block them.
- The stdlib is invisible to A7 tooling (`--mode doc`, diagnostics).

(b) A7 source only, with thin intrinsics.

- Typing is free: D1 returned typed values with no checker change.
- Blocked today by D6, D8, D9, D10. D7 has a workaround in A7 (D15).
- Needs an `extern` or intrinsic declaration form, which is new syntax.

(c) Hybrid. Recommended.

- Layer 0, hooks: about 40 typed registry entries for what A7 cannot
  express: formatted printing, OS calls, string primitives, and the
  `List`/`Map` handle types.
- Layer 1, A7 source: everything else, in `.a7` files.
- No new syntax. The hook declaration lives in Python, not in A7.

##### How hooks get types

Extend `StdlibFunction` with a signature written in A7 type syntax:

```python
StdlibFunction(module="fs", name="read_into",
    signature="fn(path: string, buf: []u8) Result(usize, FsErr)",
    backend_map={"zig": "__a7_fs_read_into"})
```

The checker parses the signature once with the existing type parser
and uses it for every hook call. This replaces the special cases in
`_visit_stdlib_module_call` and is the general form of G5B-2
(PLAN.md Phase 6 item 2). Printing keeps its format-string path.

Each hook's Zig body lives in a `.zig` snippet file under
`a7/stdlib/rt/`. The backend copies a snippet into the single output
file only when a call uses it, as it already does for the io preamble
(`_io_streams_needed`). Output stays one Zig file (STATUS:81).

`Result` and `FsErr` in that signature must name real A7 types. They
come from a bundled A7 source file (below), which is why the type
namespace problem (D4) is a prerequisite.

##### How `std/...` imports resolve

Today (R): `ModuleResolver` checks the registry aliases first, then
searches the entry directory, `<entry>/stdlib`, and the repo-root
`stdlib` (D3).

Proposed order:

1. Registry (virtual) modules: `std/io` and hook-only modules.
2. Bundled A7 modules: `a7/stdlib/src/std/<name>.a7`.
3. User files, relative to the importing file (L30).

Three things change, and each needs approval:

- The bundled directory moves inside the package (D3 is a bug today:
  the path points outside the wheel).
- `std/` becomes reserved: a user's `std/strings.a7` or
  `stdlib/std/strings.a7` no longer shadows the shipped module. Today
  it does (D1 relied on that). Decision U10.
- A module is either virtual or A7 source. `std/math` needs both
  (hooks for `sqrt`, A7 for `clamp`). Proposed rule: an A7 std module
  may import a hook module named `std/sys/<name>` and wrap it. Zig
  inlines the wrapper (inference, not measured). The alternative is to
  let the registry supply names the A7 file does not define.

##### Generic containers under today's generics

- Slice algorithms (`sort_by($T)`, `index_of($T)`, `count($T)`): A7
  source. Parameter-position generics work (D6).
- Anything that returns `Option($T)`, `Ring($T)`, or `Box($T)` from a
  generic function: blocked by D6 until PLAN.md P2-49 is fixed.
- `List($T)` and `Map($K, $V)`: compiler-known handle types lowered to
  Zig generics, per L42. The A7-side `std/list` file holds only
  helpers that need no handle internals.
- Fixed-capacity containers with a size parameter (`Buf($T, $N)`):
  `Buf(4)` does not parse (STATUS:103). Not used in this proposal.

##### Testing

- One golden program per module under `examples/std/` (or a new
  `test/stdlib/`), each printing a `testing.report` line, each with an
  expected-output file, each built and run in debug and release. This
  follows the existing example E2E pattern (AGENTS.md "Verification
  Commands").
- One failure-path program per fallible hook: missing file, read-only
  directory, full buffer, bad digit. Research 03 section 5 and
  roadmap B6 ask for real failure recovery.
- A stage-boundary check for the bundled sources: every bundled `.a7`
  file passes `a7 check --lib`, and one program that calls every
  public function builds with `zig build-exe`. Zig analyses function
  bodies lazily, so an uncalled stdlib function is never checked by
  Zig (L32 records the same effect). PLAN.md Phase 1b item 3 proposes
  this check for user code.
- No test may mirror the registry dict (PLAN.md T-8 lists 44 such
  tests in `test_stdlib_registry.py`).

##### Wheel packaging

- Put sources at `a7/stdlib/src/std/*.a7` and snippets at
  `a7/stdlib/rt/*.zig`. Add them as setuptools package data
  (`[tool.setuptools.package-data] a7 = ["stdlib/src/std/*.a7",
  "stdlib/rt/*.zig"]`).
- Resolve them with `Path(__file__).parent / "stdlib" / "src"` from
  `a7/compile.py`.
- `scripts/verify_wheel_install.py` gains one program that imports a
  bundled A7 module, so a wheel without the files fails the gate.
- Not verified: I did not run `uv build`. The claim that the current
  wheel would miss a repo-root `stdlib/` is from reading
  `pyproject.toml:24-26`.

##### Compile-time cost

- Measured (V): hello world 0.15-0.24 s; the nine-import demo
  0.31-0.38 s. Eight A7 modules of 241 lines cost about 0.15 s of
  front-end time. Three runs each, same machine, not a benchmark.
- Only imported modules are parsed. A program that imports `std/io`
  alone pays nothing new.
- A7 checks every function of an imported module, called or not
  (L32). Cost grows with module size, so modules stay small and
  single-purpose.
- Zig builds only what is called. Zig build time was not measured.
- If front-end time becomes a problem: cache parsed std ASTs keyed by
  compiler version. Not needed at the measured numbers.

#### 5. Dependency graph

Prerequisites, each mapped to PLAN.md or marked new.

| ID | Prerequisite | PLAN.md row | Probe |
| --- | --- | --- | --- |
| R1 | Checker types hook calls from a declared signature | Phase 6 item 2 (G5B-2); roadmap A3, B2 | D12 |
| R2 | `read_line` second-read fix | P1-4 | not rerun |
| R3 | Generic function may build and return `G($T)` | P2-49 (nearest: `Pair($B, $A){...}` in a generic body) | D6 |
| R4 | Inline-`$T` form or one documented spelling | P3-13, P2-40 | D5 |
| R5 | Owning or `string` payloads bind in `match` | P1-1; roadmap A5 (M33/M49) | D11 |
| R6 | String equality | P2-47, P2-35 | D9 |
| R7 | String length, byte view, `char`/`u8` casts, `char` ordering | P2-38 for ordering; the rest is new (STATUS:152 says `string.len` is rejected on purpose) | D9 |
| R8 | Memory model decision | Phase 6 item 3 (Wave B); L51, L57; roadmap A5 | D10 |
| R9 | Type names scoped per module | P2-8 | D4 |
| R10 | Module-qualified types (`m.T`, `m.G(i32)`) | P3-18 | D4 |
| R11 | Visibility enforced (`_name` private, L27) | SPEC 10.4; P4-8 (P-MOD unapproved) | not probed |
| R12 | Slices as parameters | none needed; works | p03 |
| R13 | Hook mechanism (typed registry + Zig snippets) | new; direction in L41 | - |
| R14 | Index proof from a field-loaded value | new; nearest is STATUS priority 4 and SAF-2 | D7 |
| R15 | Index proof with two bounds on one index; literal index against a slice length. Not blocking: D15 works around it at one compare per access | new | D7, D15 |
| R16 | Runtime slice bounds (`xs[a..b]`) | new | D8 |
| R17 | Heap buffer of runtime size | new for A7 source; AGENTS.md says `new [N]T` is rejected "until the language model is defined" | D10 |
| R18 | Self-referential `ref` struct field | P2-30 | D10 |
| R19 | Defined initial values for buffers | P2-42, P3-21, D-G | not rerun |
| R20 | Stdout flushed on panic | P2-45 | not rerun |
| R21 | Bundled directory inside the package; `std/` reserved | new | D3 |
| R22 | Variadic lowering (only if `io.format_into` or `log` move to A7 source) | STATUS:118 | D14 |
| R23 | Narrowing cast under a range guard | new; nearest is numerics roadmap A4 | D13 |
| R24 | Unit payload for `Result` (`ok` with no value) | new | - |

Module to prerequisite:

| Module | Needs |
| --- | --- |
| `io` (typed) | R1, R2; R13 for `format_into` |
| `slices` | none; R3 for `get` |
| `option`, `result` | R9 or a prelude (U3); R3 for constructors |
| `strings` | R13 (three hooks), R6, R7; R16 if `sub` is A7 |
| `ascii` | none for the match-based forms; P2-38 for comparisons |
| `bytes` | none (accessors, D15); R7 for `from_string` |
| `math` | R13 for `pow`/`round`; the virtual-plus-source rule |
| `conv` | R9 (shared `Result`), R23 for `format_i64`, R13 for floats |
| `sort` | R3 for `min_of`; R9 so the alias `sort` works (D16) |
| `hash` | R7 for `of_string` |
| `random` | R13 for `from_os` |
| `time`, `os`, `fs` | R1, R13, R9; R5 for `arg`/`env`; R19 for buffers; R24 optional |
| `path` | `strings.sub` |
| `testing` | R20 for `panic`; runs today otherwise |
| `ring` | R3 |
| `list`, `map`, `set`, `text` | R8, R3, R5, R6, R10 |
| `utf8`, `hex`, `base64` | R23 |
| `json` (reader, writer) | none for `next` (D17); R7 for string input and `text_is`; R23 for `unescape_into` and number output; R9 for the shared `Result` |
| `yaml` (reader) | same as `json`; R9 or prefixed names to import beside `json` (D4) |
| `data` (tree) | `list`, `text`, R5 for `as_text`, R8 |
| `process`, `log`, `net` | `list`, `map`, `text`; R22 for `log` |

#### 6. Phased roadmap

##### Phase A: no heap

Starts after PLAN.md Phases 0-2 land and after R1, R9, R13, R21.
Eighteen modules: `io` (typed), `option`/`result` (counted as one),
`slices`, `strings`, `ascii`, `bytes`, `math`, `conv`, `sort`, `hash`,
`random`, `time`, `os`, `fs` (caller-buffer forms), `path`, `testing`,
`json` (event reader and writer), `yaml` (event reader).

What already runs with no compiler change (D2, D15, D17, section 3):
`strings.len`, `count_char`; `ascii.is_digit`, `digit_value`;
`slices.at`, `put`, `swap`, `reverse`, `contains`; `bytes.fill`,
`index_of`, `copy`, `eq`; `math.gcd`, `clamp`; `sort.sort`,
`sort_i32`, `index_of`; `hash.fnv1a`, `fnv1a_seeded`; `random.seeded`,
`next_u64`, `below`; `testing.check`, `check_eq_i64`, `report`;
`json.reader`, `next`, `kind_name`.

Exit criteria, each a program with a golden output file, run in debug
and release:

1. `wc`: reads a file named by `os.arg_or(1, "input.txt")` into a
   64 KiB buffer with `fs.read_into`, prints line, word, and byte
   counts. A missing file prints one error line and exits 1 through
   `os.exit`.
2. `sum`: reads integers from stdin with `io.read_line` and
   `conv.parse_i64`, prints the total, reports the first bad line by
   number. Covers PLAN.md P1-4.
3. `sorted`: fills 1,000 values from `random.seeded(1)`, sorts with
   `sort.sort_by`, checks `sort.is_sorted`, prints the first five.
4. `selftest`: one `testing.Tally` over every phase A function;
   prints `N passed, 0 failed`.
5. `jsonlint`: reads a file with `fs.read_into`, runs
   `json.validate`, prints `ok` or `error at byte N`, then prints one
   line per event. A second run on a file with a missing brace prints
   the error offset.
6. `config`: reads a YAML file with nested maps, a list, a quoted
   string, and a comment; prints `server.port = 8080` style lines. A
   file with an anchor prints `unsupported at line N` and exits 1.
7. A wheel installed in a clean venv builds and runs program 4.

##### Phase B: heap types

Starts after the memory mechanism is selected (L51, L57, Wave B memo)
and after R3, R5, R6, R10. Modules: `text`, `list`, `map`, `set`,
`data` (JSON and YAML tree), `fs.read_text`, directory listing, `ring`,
`utf8`/`hex`/`base64`, `slices.get`, `sort.min_of`.

Exit criteria:

1. `wordfreq`: reads a file of any size with `fs.read_text`, counts
   words in a `Map(string, i64)`, prints the ten most frequent, sorted.
2. `tokens`: a tokenizer for a small expression language that returns
   a `List(Token)`; the L44 acceptance class.
3. `shared`: `b := a` then `list.push(b, x)` and `list.len(a)` prints
   the new length; `c := list.copy(a)` stays independent (L42).
4. A loop that builds and drops 10N lists keeps peak memory flat
   (research 03 section 5), measured under the L38 rule.
5. `data` round-trip: `parse_json` on a nested document, `to_json`
   back, output equals a golden file. `parse_yaml` on the equivalent
   YAML file prints the same JSON.

##### Phase C: later

`process`, `log`, then `net` with the concurrency track.

Exit criteria:

1. `process.run` of `echo` returns exit code 0 and the output text.
2. A loopback TCP echo program (research 10 section 5).

#### 7. Decisions for the user

Each row is a proposal. None is approved.

Snippets in this section are fragments unless a status is given. I
ran three: U1 option 2 (`name.len()` exits 6), U7 option 1 (runs,
through `bytes.copy`), and U12 option 2 (`extern fn` exits 5,
`Function declarations must have names`). The `{ ... }` bodies in U3
stand for omitted code and do not parse.

##### U1. Function spelling: `strings.len(s)` or `s.len()`

Today: methods do not exist. `c.inc()` exits 6 (`Struct 'Counter' has
no field 'inc'`). `s.len` on a string exits 6.

- Option 1 (recommended): free functions in modules. No language change.
- Option 2: add method-call sugar, so `x.f(a)` means `f(x, a)`.
  A language change with its own packet.

```a7
// Option 1
n := strings.len(name)
list.push(xs, 3)
// Option 2
n := name.len()
xs.push(3)
```

##### U2. Failing operations: panic, `Result`, or both

Today: `io.println` panics on a write failure. `io.println_ok`
returns a `Result` that only a statement can discard (D12).

- Option 1 (recommended): one name per operation. An operation that
  can fail for reasons outside the program (files, input, parsing)
  returns `Result` or `Option`. Printing to the console keeps the
  panicking `println`; `println_ok` stays as the one checked form.
- Option 2: every fallible function ships twice, `read_into` and
  `must_read_into`.

```a7
// Option 1
match fs.read_into("a.txt", buf[0..4096]) {
    case .ok(n): { io.println("{}", n) }
    case .err(e): { io.eprintln("read failed") }
}
// Option 2 adds
n := fs.must_read_into("a.txt", buf[0..4096])   // panics on failure
```

Sub-questions with the same shape. A search returns `Option(usize)`
(as proposed; AGENTS.md keeps `isize` for offsets and P3-27 flags the
`-1` sentinel) or `isize` with `-1`. `fs.remove` returns
`Result(bool, FsErr)` (as proposed) or A7 gains a no-payload `ok`.

```a7
match bytes.index_of(data[0..4], 3) {       // proposed; ran, printed "found at 2"
    case .some(i): { io.println("found at {}", i) }
    case .none: { io.println("absent") }
}
i := bytes.index_of(data[0..4], 3)          // alternative: i is isize, -1 when absent
```

##### U3. Who declares `Option` and `Result`

Today: each program declares its own. A second declaration in an
imported module exits 6 `Already defined` (D4). So a stdlib that
declares `Result` breaks every program that already declares one.

- Option 1 (recommended): the compiler provides `Option` and `Result`
  to every file. A user declaration of either name becomes an error
  (roadmap B4 states this shape). Programs that declare them today
  must delete the declaration.
- Option 2: wait for per-module type scoping (PLAN.md P2-8, P3-18),
  then write `opt.Option(i32)`.

```a7
// Today: required in each program
Result :: union(tag) {
    ok: $T,
    err: $E,
}
parse :: fn(s: string) Result(i32, ParseErr) { ... }

// Option 1: the declaration above is deleted; the rest is unchanged
parse :: fn(s: string) Result(i32, ParseErr) { ... }

// Option 2
res :: import "std/result"
parse :: fn(s: string) res.Result(i32, ParseErr) { ... }
```

##### U4. Auto-import

Today: nothing is imported unless written. A program that prints
needs `io :: import "std/io"`.

- Option 1 (recommended): keep explicit imports for modules. Only the
  two type names in U3 are always present.
- Option 2: `io` is always available without an import.

```a7
// Option 1 (today)
io :: import "std/io"
main :: fn() {
    io.println("hi")
}
// Option 2
main :: fn() {
    io.println("hi")
}
```

Option 2 breaks a program with a local named `io` (L28 makes that
clash an error).

##### U5. Bare names for new modules

Today: `import "io"` and `import "math"` mean the stdlib (L31), so a
local `io.a7` cannot be imported.

- Option 1 (recommended): new modules use the `std/` prefix only.
  `import "strings"` keeps meaning a local `strings.a7`.
- Option 2: every stdlib module also gets a bare name. A user file
  named `list.a7`, `path.a7`, `time.a7`, `sort.a7`, or `testing.a7`
  becomes unimportable.

```a7
strings :: import "std/strings"   // stdlib under both options
strings :: import "strings"       // Option 1: local strings.a7. Option 2: stdlib
```

##### U6. Lists: sharing, copying, growth failure

Today: no list type exists. L42 records "Share the same list" for
`b := a`. Copy spelling and failure behavior are open in L42.

- Proposed: `list.copy(a)` is the copy spelling. `list.push` stops the
  program with a message when memory runs out; `list.try_push` returns
  `bool` for programs that must recover (gate M2).
- A function that returns a list returns the handle; the caller and
  the function share it. Nobody frees it by hand (L19).

```a7
a := list.make(i32)
list.push(a, 1)
b := a                 // same list
c := list.copy(a)      // independent
list.push(b, 2)
io.println("{} {}", list.len(a), list.len(c))   // 2 1
```

##### U7. Unproven indexes inside the stdlib

Today: an index the prover cannot bound exits 6. A loop over two
slices fails on it (D7).

- Option 1 (recommended): stdlib code goes through `slices.at` and
  `slices.put` (3.2). They are ordinary A7, they compile today, and
  they are public, so user code gets the same tool. Each access costs
  one compare in every build profile, which is the checked execution
  L39 allows.
- Option 2: bundled std files compile in a mode where unproven indexes
  become runtime-checked and stop the program. User code keeps exit 6.
  Two rule sets.
- Option 3: wait for the prover (R14, R15) and ship the affected
  functions as Zig hooks until then.

```a7
// Today: exits 6 at dst[i]
while i < dst.len {
    if i < src.len {
        dst[i] = src[i]
    }
    i += 1
}
// Option 1: compiles and runs today
while i < dst.len {
    ok := slices.put(dst, i, slices.at(src, i, 0))
    i += 1
}
```

##### U8. String length and bytes

Today: `s.len` exits 6 (STATUS:152 lists the rejection as deliberate).
A string cannot become `[]u8`. The only way to count is
`for ch in s { n += 1 }`.

- Option 1 (recommended): `strings.len(s)` and
  `bytes.from_string(s)` as hooks. No field on `string`.
- Option 2: allow `s.len` like slices (`xs.len` works today).

```a7
n := strings.len(name)   // Option 1
n := name.len            // Option 2
```

##### U9. Arguments before `string` payloads work

Today: `match os.arg(1) { case .some(name): ... }` cannot compile
(D11), whatever `os.arg` does.

- Option 1 (recommended): phase A ships `os.arg_or(1, "default")` and
  `os.env_or("HOME", "")` only. `os.arg` arrives with R5.
- Option 2: hold `std/os` until R5.

```a7
name := os.arg_or(1, "world")   // Option 1, phase A
```

##### U10. May a project replace a stdlib module?

Today: a file at `<entry>/stdlib/std/strings.a7` is found before any
bundled module (and no bundled module exists). Probe D1 used this.

- Option 1 (recommended): `std/...` always means the shipped module.
  A project file at that path is ignored with a warning, or is an
  error.
- Option 2: project files win, so a project can patch the stdlib.

```a7
strings :: import "std/strings"
// Option 1: always a7's own strings module
// Option 2: ./stdlib/std/strings.a7 if the project has one
```

##### U11. Confirm the "never" and "later" list

Today: the roadmap marks TOML "NEVER", regex "library-only", crypto
"wrapper-only", async syntax "never". The ledger holds no approval
for these (`ledger-audit.md`, last table row). JSON and YAML left this
list on 2026-10-04 (see U13).

Question: for each row of the section 1 table marked "None", say
approved, not approved, or decide later. Example of one row: under
"TOML never", a program that must read `Cargo.toml`-style files has no
stdlib module for it and no `std/toml` is ever added; it reads JSON or
YAML instead.

##### U12. How hooks are declared

Today: a hook is a Python dict entry with no types
(`a7/stdlib/io.py`). The checker hard-codes each family.

- Option 1 (recommended): typed registry entries (section 4). No A7
  syntax change. Users cannot add hooks.
- Option 2: an A7 declaration form for external functions, which also
  serves the L41 native interface later. New syntax, own packet.

```a7
// Option 2 sketch, not valid today
now_unix_ms :: extern fn() i64
```

##### U13. How much YAML

Today: no YAML module exists, and roadmap B8 says "YAML/TOML NEVER".
Your message of 2026-10-04 asks for a YAML parser.

- Option 1 (recommended): the subset in 3.22. Anchors, aliases, tags,
  merge keys, and multi-document files are rejected with a line
  number.
- Option 2: full YAML 1.2, including anchors and aliases. Aliases
  need a size limit to stop one small file from expanding without
  bound, and the document stops being a tree.

```yaml
# Option 1 and 2 both read this
server:
  port: 8080
  hosts: [a, b]
# Option 1 rejects this with "unsupported at line 2"; Option 2 reads it
base: &b {port: 8080}
dev: *b
```

Also needed from you: one line for the ledger that records JSON and
YAML as v1 stdlib modules, since the roadmap row says the opposite.

##### U14. JSON and YAML: events first, or wait for the tree

Today: neither exists. A document tree needs growable lists, which
wait for the memory decision. An event reader needs nothing (D17).

- Option 1 (recommended): phase A ships the event readers and the
  JSON writer. Phase B adds `std/data` with `parse_json`/`parse_yaml`
  and key lookup.
- Option 2: ship nothing until the tree exists. One API, later.

```a7
// Option 1, phase A: walk events (ran today)
ev := json.next(r)
if ev.kind == Kind.Key {
    io.println("key at {}..{}", ev.start, ev.end)
}
// Phase B under both options: look up by key
match data.get(data.root(doc), "port") {
    case .some(v): { io.println("{}", data.text_or(v, "?")) }
    case .none: { io.println("no port") }
}
```

#### 8. Risks and what I did not verify

Risks:

1. Phase A depends on PLAN.md Phases 0-2. Several stdlib bodies sit on
   known wrong-result bugs: uninitialized buffers (P2-42), dropped
   stdout on panic (P2-45), `1 << n` (P2-47), untyped constant wrap
   (P2-1; `hash` and `random` use large `u64` literals, which printed
   correct values in D13 with typed variables).
2. Stdlib code in A7 pays one compare per element access through
   `slices.at`/`put` (D15) until the prover handles two bounds (R15)
   and field-loaded indexes (R14). The cost against the L38 limit is
   not measured. If it fails that limit, hot loops (`copy`, `eq`,
   `sort`, the JSON and YAML readers) become Zig hooks.
3. L42 makes `List` a handle while structs stay values. Users will
   meet two assignment rules. The memory packet has to state this.
4. D4: until type names are scoped (R9), every public stdlib type name
   (`Order`, `Rng`, `Tally`, `FsErr`, `File`) is taken from every
   program that imports the module. A user struct named `File` would
   exit 6 after importing `std/fs`.
5. Zig 0.16 `std.Io` is new and differs from earlier releases. Hook
   bodies for files, clocks, arguments, and environment may need more
   Zig than the one-line lowerings named in section 3.
6. Zig analyses lazily. A bundled function nobody calls is never
   compiled by Zig, so a stdlib bug can ship unless the all-functions
   program in section 4 exists.
7. Front-end cost is linear in imported stdlib lines. Measured at
   241 lines only.
8. The roadmap's stdlib IDs B1-B8 collide with memory IDs B0-B3
   (PLAN.md P4-13). This file uses R, D, and U prefixes to avoid a
   third collision.

Not verified:

- Every statement about Zig std, Go, Odin, Rust, Hare, and C3 in
  section 2, and every Zig call name in section 3. From memory.
- No hook was written or compiled. All hook rows are designs. The
  `time`, `os`, `fs`, `path`, `conv`, and `utf8` examples ran against
  stub A7 modules with placeholder bodies; their printed output shows
  that the call and match shapes compile, not that the modules work.
- `strings.index_of_char` with the `Option(usize)` return, `shuffle`
  through `slices.swap`, and `slices.count` were not run.
- The cost of `slices.at`/`put` against direct indexing.
- The JSON reader ran on one 15-byte input. It does not validate
  (it accepts `tru!` as `true`, and commas anywhere). No YAML code ran;
  the YAML rows are signatures over stub bodies.
- YAML 1.2 rules quoted in 3.22 are from memory.
- Stub bodies prove that a signature parses and type-checks, not that
  the function can be implemented.
- Every `list`/`map` signature beyond parsing.
- Release-profile behavior beyond two programs: the D2 demo and the
  cross-module generic sort printed the same output under
  `a7 run --profile release`. All other runs used debug.
- `uv build` and wheel contents (D3 is from reading two files).
- PLAN.md rows cited as prerequisites were not re-run unless the
  table in section 5 names a probe.
- No pytest, no gate script, per the task rules.
- L42's interaction with arena-per-function lowering (roadmap A5): a
  list returned from a function must outlive that function's arena.
  Research 22 section 4 proposes a hidden caller-arena parameter; I
  did not evaluate it.

## Change log of this plan

- v21: Appendix A.8 line lists, A.14, Appendices B-J (embedded
  reports and stdlib proposal), `probes/` copied from the scratchpad.
- v20: JSON/YAML confirmed by the user; static-analysis results,
  spot checks, and the not-covered list added before Phase 6.
- v19: verdict rewritten; execution order puts safety holes right
  after Phase 0 and moves test deletion to Phase 5; P0-10 added;
  P2-6, P2-37, P2-44, D-D, D-K checked against CHANGELOG:67, L49, L52,
  SPEC 2.5.
- v18: fuzzing review added. Rows P2-77..P2-82. All reviews done.
- v17: generated-Zig review added. Rows P2-69..P2-76, decision D-K,
  performance notes against L38.
- v16: stdlib proposal added as Phase 7, decision D-J.
- v15: second test review added. Rows T-11..T-20. P2-1 and D-D
  rewritten: the i32 constant wrap is a recorded pin that contradicts
  SPEC 4.2.1 and L47, so it is a decision, not a plain bug.
- v14: every finding now has a place in this file. Added Appendix A
  (findings without a table row), the decision table, P0-9 in the
  Phase 0 table, reading-order note.
- v13: site review added. Phase 3c rows W-1..W-6.
- v12: modules review added. P0-9 (Phase 0), P2-64..P2-68, L25-L31
  status.
- v11: diagnostics review added. Phase 3b rows G-1..G-9.
- v10: CI/release review added. Phase 4b rows C-1..C-8, decision D-I.
- v9: gate finished green, 10/10.
- v8: safety/validator review added. Rows P2-52..P2-63. Round 2
  reviewers launched.
- v7: backend review added. Rows P2-42..P2-51, backend split and dead
  code in Phase 5. SPEC block counts corrected to the final report.
- v6: test-suite review added. New Phase 1b, rows T-1..T-10.
- v5: SPEC and examples/bench reviews added. Rows P3-13..P3-29,
  P6-1..P6-4, decisions D-G and D-H. Gate: pytest and E2E pass.
- v4: type-checker review added. Rows P2-29..P2-41, Phase 5 checker
  items and split.
- v3: frontend review added. Rows P2-17..P2-28, decision D-F, Phase 5
  parser/tokenizer/AST items.
- v2: plan/research review added. Phase 4 rows P4-8..P4-15, decision
  D-E, `ledger-audit.md`. Inputs table: plan/research is done.
- v1: built from six finished reviews.
