# A7 repair and delivery plan (from the 2026-10-04 audit)

## Context

The audit in `tmp/audit-2026-10-04/PLAN.md` (16 reviews, about 190
rows, Appendices A-J, probes in `tmp/audit-2026-10-04/probes/`) found
that the gate is green (10/10, 2,548 tests) while the tree holds
regressions against HEAD, programs that pass the safety proof and then
crash or run undefined behaviour in release, a parser and checker that
accept programs Zig rejects, docs that trail the compiler, and a ledger
that lacks records for most shipped changes. The 2,293 uncommitted
lines cannot land as one commit.

This plan executes all of PLAN.md. Row IDs (P0-1, P2-52, T-1, ...)
refer to that file; it stays the detailed reference and is not
restated here. Outcome: a tree where every accepted program builds and
behaves the same in debug and release, a test suite that fails on the
defects it claims to cover and runs in minutes, docs that match the
compiler, and a recorded decision for every behavior change.

## Decisions

Given by the user on 2026-10-04:

| ID | Decision |
| --- | --- |
| Scope | Everything in PLAN.md |
| D-A | Bare `break`/`continue` in a match case: revert to HEAD (leaves the loop) |
| D-B | Same-name functions: restore exit 6 `Already defined` |
| D-C | Native `switch` kept only for integer/enum/bool/char scrutinee with constant arms; `ref` params revert to `?*T` |
| D-D | Constant arithmetic is exact, then fits the destination; overflow is exit 6 |
| D-F | Parser requires statement terminators and list commas |
| D-G | Declarations without an initializer and `new T` are zero-initialized |
| D-K | "allow user to build fast, with different defaults": `--profile release` becomes ReleaseSafe; a third value `--profile fast` gives ReleaseFast (keeps roadmap A4's "one `--profile` flag") |
| JSON/YAML | Both go into the stdlib proposal (reverses roadmap B8) |

Delegated ("stop asking and decide"), chosen here:

| ID | Choice |
| --- | --- |
| D-E | Features in the working tree that survive Phase 0 (generic unions, `where`, dot-arm match, `$N` after its fix, E1/E2/E4 codegen, `println_ok`/`read_line`) are recorded as approved under this delegation. Bare `case tag:` stays rejected (exit 6). Committed items with no record (struct constraints, import-cycle diagnosis, duplicate-import and bare-imported-call rejection) are recorded as accepted |
| D-H | Promote `mem_shared`, `mem_returned`, `mem_cleanup`; rewrite the other four before promotion |
| D-I | GitHub settings: listed as a user action (outside the repo); the plan prepares the checklist, does not change settings |
| D-J | Stdlib: hybrid architecture; U1-U14 take the proposal's recommended option each; phase A only after its prerequisites |
| Module design | Implement L25-L31 as written in the ledger (per-module scopes) |

Every row above gets an entry in `docs/plan/decisions.md` with the
user's quoted words or "delegated 2026-10-04: 'stop asking and
decide'", before the code change it covers.

## Working rules

- Follow `AGENTS.md`: no new recursion in `a7/`, house writing style,
  post-change checklist, no registry work.
- Each fix lands with a test that builds and runs the binary where the
  defect is a runtime or Zig-build defect.
- Use the probe files in `tmp/audit-2026-10-04/probes/` as test seeds.
- Parallel work goes to subagents with disjoint file sets, one worker
  per file group: `a7/parser.py`+`a7/tokens.py`; `a7/passes/safety.py`;
  `a7/passes/type_checker.py`+`a7/types.py`+`a7/exact_constants.py`;
  `a7/backends/zig.py`; `a7/compile.py`+`a7/module_resolver.py`+
  `a7/passes/name_resolution.py`; `test/`; `docs/`+`site/`; `scripts/`+
  gate+CI. The parent runs the full gate between waves.
- Commit only when the user asks. Wave 3 prepares the commit split;
  later waves stage one logical change per commit.

## Wave 0: records and safety net (no behavior change)

1. Write ledger entries L58+ for every decision above; fix L47's
   self-contradiction note, the L50-L57 scope line, the stale gate
   stub (P4-2, P4-11).
2. Gate script (`run_all_tests.sh`, `run_release_checks.sh`): proper
   argument loop with a `*)` error arm, fail on zero checks run,
   reject non-numeric timeouts, forward `--timeout`, raise the default
   to cover the suite (P0-7, P0-10, C-3).
3. `site/content/features.json` updated for the SPEC heading edits
   (P0-8).

## Wave 1: test infrastructure and test performance

Do this before compiler fixes so each fix can be proven.

1. `test/conftest.py`: one real-pipeline helper built on
   `A7Compiler.compile_file_detailed` (`a7/compile.py`) with
   `expect_ok(source)` and `expect_exit(source, code, fragment)`; one
   `build_and_run(source, profile)` helper that asserts zig 0.16.0
   (reuse `zig_binary`, `zig_version`, the session `zig` fixture) and
   fails, not skips, when zig is absent (T-1, T-3, T-4, T-7).
2. Replace the seven private `run_semantic_analysis` copies and
   `compile_a7_to_zig` in `test_codegen_zig.py` with those helpers.
   Tests that go red are triaged into: real compiler row in PLAN.md,
   or wrong test (fix or delete).
3. Replace every `zig ast-check` used as a build check with
   `build_and_run` (new test files, `test_codegen_zig.py`).
4. Stage-boundary test: programs accepted in `--mode semantic` must not
   exit 7 or fail `zig build-exe`; seeded from the probes.
5. Recursion ratchet: per-group member ceiling and a total (113) in
   `test/test_no_recursion.py` (T-11); a 2,000-term flat-chain test
   (T-13, expected red until Wave 4).
6. Test performance. Measured with `--durations=80` on 2026-10-04:
   25m20s serial on a 24-core box, about 20 GB of temp. The 80 slowest
   tests take 1,133 s of 1,520 s (75%); the other 2,470 take 6 minutes.
   All 80 are native builds at 12-22 s each, in
   `test_untyped_constants_acceptance.py` (185 s),
   `test_zig_backend_runtime.py` (169 s),
   `test_float_nonfinite_folding.py` (118 s), `test_feature_pins.py`
   (94 s), `test_module_alias_shadowing.py` (92 s),
   `test_constant_folding_exact.py` (89 s) and eight more files. By
   contrast `test_examples_e2e.py` builds and runs all 51 examples in
   20 s with one shared cache. So the cost is cold Zig caches and
   ReleaseFast builds per test, not the compiler.
   - One session-scoped shared Zig global cache for all native tests
     (the `zig_cache` fixture in `conftest.py`); remove per-test
     `tmp_path / "global-cache"` in `test_constant_folding_exact.py`,
     `test_module_alias_shadowing.py`, `test_feature_pins.py` and the
     nine copy-pasted zig fixtures (T-20). Expected to remove most of
     the 1,133 s on its own.
   - Batch native cases: where one file compiles many small programs
     (`test_untyped_constants_acceptance.py`,
     `test_float_nonfinite_folding.py`), build them in one
     session-scoped step per profile and assert per case on the
     captured outputs. Run the release profile only for cases whose
     behavior can differ by profile.
   - Add `pytest-xdist` to the dev group; run `-n auto` in the gate
     with the shared cache; make `test_parser_fuzzing.py` seed a local
     `random.Random` (T-9) so order no longer matters.
   - Markers `zig` and `slow` registered in `pyproject.toml`; fast loop
     is `pytest -m "not zig"`.
   - Remove duplicate native work: the 102 codegen example tests and
     `TestZigAstCheck` duplicate `test_examples_e2e.py`; the gate's
     "Examples E2E" step is a subset of the debug artifact build; the
     error-stage matrix runs in pytest and again as a gate step. Keep
     one of each.
   - Use the per-test timings from the durations run
     (`--durations=80`) to pick any remaining outliers; record before
     and after wall time in the commit message.
   - Target: full pytest under 6 minutes, fast loop under 60 seconds,
     temp use under 3 GB.
7. Add `ruff check --select F` to the gate and clear its 66 findings.

Deleting or merging the roughly 640 tests that verify nothing (T-2,
T-5, T-8, T-17, T-18) and renaming the 15 session-named test files
(T-20) happens in Wave 7, after behavior is stable.

## Wave 2: regressions in the uncommitted work (Phase 0)

| Row | Change | Files |
| --- | --- | --- |
| P0-4 | Remove the break/continue-in-match rejection and its two error codes; fix the false statement in STATUS | `a7/passes/semantic_validator.py`, `a7/errors.py` |
| P0-3, P0-9 | Restore `ALREADY_DEFINED` for same-name functions; remove `overload_nodes`; delete `test_overload_coexist.py`, remove the two xfails, restore `test_semantic_analysis.py:76` | `a7/passes/name_resolution.py`, `a7/passes/type_checker.py` |
| P0-1 | `ref` params back to `?*T` in declarations, call sites and fn-pointer types; remove the boundary check path; unify the two `del` emitters and stop hard-coding the capture name `p` (P2-46) | `a7/backends/zig.py` |
| P0-2 | `_match_is_plain_equality` returns true only for integer/enum/bool/char scrutinee types and comptime-known arms | `a7/backends/zig.py` |
| P0-5 | Tag-mode match: no redundant `else` on full coverage, `else` for `case _:`, unique capture names declared before use, discard unused captures in match expressions, quote variant names (P2-47) | `a7/backends/zig.py` |
| P0-6 | Run `_check_value_arg` on type annotations; emit `comptime N: <type>`; replace `_extract_value_arg` with the exact evaluator | `a7/passes/type_checker.py`, `a7/backends/zig.py` |
| P1-1..P1-5, P1-7 | Payload ownership by type (not string compare), `ref` union match, duplicate reports, `read_line` reader kept across calls, arity error, `where` comma, plan IDs out of messages | checker, validator, parser, backend |

Each row gets `build_and_run` tests in debug and release. Exit: gate
green with the new helpers.

## Wave 3: split and stage the working tree

Order from PLAN.md Phase 1 (12 commits: style rules, import pins,
reversed ranges, SPEC alignment, generic unions, payload match,
`where`, `$N`, codegen E1/E2/E4, io Result calls, examples 049/050,
plan docs). Prepare each as a staged set with its tests and its
CHANGELOG/STATUS lines; present to the user for the commit command.

## Wave 4: soundness

Safety pass (`a7/passes/safety.py`), in this order:

1. Loops: snapshot the fact state before the loop and join it with the
   body-exit state (covers `while`, C-style `for`, for-in, and
   `moved_symbols`) (P2-52).
2. Defers: prove deferred statements against the scope-exit state;
   reject `defer del x` followed by `del x` (P2-53).
3. Facts, `function_deletes` and the recursion call graph keyed by
   declaration identity, not name; bind match captures; drop inner
   facts on block exit (P2-54, P2-55, P2-57).
4. Clamp unary minus; require proofs for shift counts, `min / -1`,
   `-min`, `abs(min)` or emit checked forms (P2-56, P2-43, P2-44,
   P2-69; closes gate G3's open edge list).
5. Recursion ban: build the call graph over function values (aliases,
   fields, array elements, returns, globals, if-expressions, modules)
   in `a7/passes/semantic_validator.py` (P2-58).

Runtime contract:

6. Zero-initialize: `_default_value` returns zero values for struct,
   enum, slice, fn-pointer, and `new T` zeroes memory (D-G; P2-42,
   P3-21) in `a7/backends/zig.py`.
7. Profiles (D-K): `--profile release` maps to ReleaseSafe,
   `--profile fast` to ReleaseFast in `a7/cli.py`, `a7/compile.py`,
   `scripts/build_examples.py`, bench harness stays on fast.
8. stdout: line-buffer on a tty, flush before panic and before stdin
   reads, exit quietly on a closed pipe (P2-45, P2-70, P2-71).

## Wave 5: language core correctness

Parser and tokenizer (`a7/parser.py`, `a7/tokens.py`):
- `_expect_statement_end()` after every statement and declaration;
  `_parse_delimited()` enforcing separators; explicit
  `no_struct_literal` flag replacing the 10-token lookback; bounded
  lookahead for call arguments; assignment targets must be lvalues;
  reject duplicate `else`, `defer ret/break`, typeless params; number
  lexing; char literal range and distinct errors; route `using import`;
  spans covering whole nodes (P2-17..P2-28, D-F). A scan of
  `examples/` and `test/` for dependence on the loose forms runs first.

Type checker and types (`a7/passes/type_checker.py`, `a7/types.py`):
- Two-phase type registration (names, then fields) (P2-30).
- A real `nil` type; UNKNOWN no longer assignable (P2-31).
- Lvalue and mutability check for every assignment target and `ref`
  argument (P2-32, P2-33).
- Operand checks for bitwise, shift, `==`; unconstrained `$T` is not
  numeric; value vs type distinction; if-expression destination
  typing; `ref [N]T` indexing; int-to-float only where lossless
  (P2-4, P2-34..P2-38).
- Unknown constraint names are errors; user aliases shadow predefined
  sets (P2-3). Duplicate enum variants, parameter shadowing, captures
  resolved after all globals register (P2-2, P2-5).
- One diagnostic per mistake (P2-39).
- Iterative expression traversal for binary and postfix chains
  (P2-29, P2-78), shrinking the recursion allowlist.

Constants (D-D), `a7/exact_constants.py` as the only folder:
- Remove the i32 wrap and the f64 comparison shadow; fix the MUL zero
  sign; reject zero divisors and overflow to infinity; exact shifts;
  cap exponents and digit counts (P2-1, P2-6, P2-37, P2-79, P2-80,
  P3-24). Delete `const_eval` folding, the preprocessor fold, and
  `_extract_value_arg`. Update the pinned test
  `test/test_audit_backend_repairs.py:59-61`, SPEC 2.5, CHANGELOG.

Backend (`a7/backends/zig.py`):
- Generic environment for inline-`$T` functions and generic bodies
  (P2-40, P2-49, P3-13); string `==` and string match; typed array
  literals; `@intCast`/`@as` for shifts and literals; Zig keyword and
  primitive quoting everywhere; enum tag type sized to values; remove
  the dead nested-function hoisting; replace silent fallbacks with
  internal errors (P2-47, P2-50, P2-51).

Modules (L25-L31), `a7/compile.py`, `a7/module_resolver.py`,
`a7/passes/name_resolution.py`:
- Per-module scopes replace the flat merge; qualified access for
  functions, constants, globals, types and function values; paths
  relative to the importing file with `..` allowed inside the root;
  `_` private and `__` reserved enforced; canonical module identity;
  collision-free prefixes; selected-import validation; `--mode
  semantic` runs the merge (P2-8, P2-23, P2-48, P2-59, P2-60,
  P2-64..P2-68).

CLI and tooling:
- Output path from `Path.with_suffix`; refuse `.a7` destinations in the
  legacy path; escape Rich markup; one error stream; `--layout` JSON;
  layout sizes for unions, single-variant enums, fn pointers; AST
  renderers share one child iterator; JSON serialization without
  recursion; safety pass complexity (P2-10..P2-15, P2-62, P2-77,
  P2-81).

Diagnostics (G-1..G-9): correct label for undefined names; proof
errors state the accepted guard shape; file names in human output;
parse-error hints; `check` prints snippet and hint; error code and
hint in JSON; catalog generated from `a7/errors.py`.

## Wave 6: docs, site, records

- SPEC: split into implemented language and `docs/design/` (section 9,
  methods, variadics, intrinsics, Appendix B); delete 12.2, 12.3,
  Appendix E; tag fences `a7`, `a7-error`, `a7-planned`; add
  `scripts/check_spec_blocks.py` to the gate; rewrite section 13 from
  the parser; fix the stray fence at L1839 (P3-13..P3-24).
- README, STATUS (surface, gaps, priorities only), CHANGELOG
  (user-visible lines only), ERROR_CATALOG (generated), ARCHITECTURE,
  RELEASE, `docs/README.md`; archive `design-system.md`,
  `ERROR_ANALYSIS.md`, the PDF (P3-1..P3-12).
- Site pages and `bun run sync:exports`; snippet verifier over all
  fences in `bun run check`; a built-output test; 404 page; search
  index; error reference page (W-1..W-6).
- Examples: fix false comments, rename mismatched files, add examples
  for payload match, `where`, imports, labeled break, slices; merge
  duplicates (P3-25..P3-29).
- Plan docs: `docs/plan/ids.md`; one todo list; move
  `docs/research/language-needs/` under `docs/plan/research/` and index
  it; archive superseded plan files; new handoff; remove dead `tmp/`
  citations and absolute links (P4-1..P4-15).
- AGENTS.md/CLAUDE.md: fix the recursion contradiction, move "Docs
  Accuracy" and "Out of Scope" into AGENTS.md, add Zig setup and gate
  timing (C-8).

## Wave 7: CI, release, cleanup, structure

- CI: call the gate script; `timeout-minutes`; fix `direct_prompt`;
  narrow workflow permissions; attest only on tag refs; extend
  `verify_release_version.py`; `pyproject.toml` metadata; sdist
  contents (C-1, C-3..C-7). GitHub settings checklist for the user
  (C-2, D-I).
- Tests: delete or merge the roughly 640 tests that verify nothing;
  rename the 15 session-named files; pinned defects into STATUS or
  fixed (T-2, T-5, T-8, T-14..T-20).
- Dead code and duplicates listed in PLAN.md Phase 5 and Appendix A.
- File splits with no behavior change: `checker/` (9 modules), `zig/`
  (8 modules), parser helpers; ratchet keys renamed one-for-one; add
  pyright per split module.
- Repo hygiene: `.gitignore` gaps, duplicate evidence files, loose
  `tmp/` files (P4-6, P4-7).

## Wave 8: roadmap and stdlib

- B0: promote three benchmarks, rewrite four, fix the handoff value,
  re-pin on an idle box (P6-1..P6-4).
- G5B-2: checker types stdlib hooks from declared signatures.
- Wave B memory prototypes (L57), numerics A4.
- Stdlib phase A per `stdlib-proposal.md` (hybrid: registry hooks plus
  `.a7` sources inside the package, `std/` reserved): `io`, `option`,
  `result`, `slices`, `strings`, `ascii`, `bytes`, `math`, `conv`,
  `sort`, `hash`, `random`, `time`, `os`, `fs`, `path`, `testing`,
  `json`, `yaml`. Phase B (`list`, `map`, `set`, `text`, `data`,
  `ring`) after the memory decision.

## Verification

Per wave:

- `PYTHONPATH=. uv run pytest -n auto` and the fast loop
  `pytest -m "not zig"`.
- `./run_all_tests.sh` (all ten checks) after each wave;
  `./run_release_checks.sh` after Waves 0, 6, 7.
- Probe replay: a script runs every reproducer under
  `tmp/audit-2026-10-04/probes/` named in a closed row, in debug and
  in release, and checks the expected exit code or output. A row is
  closed only when its probe passes and a test in `test/` covers it.
- Debug/release parity: every `build_and_run` test runs both profiles
  and compares output.
- `uv run python scripts/verify_examples_e2e.py` after any change to
  `examples/`, codegen, or runtime.
- `(cd site && bun run check)` after docs or site edits.
- Wave 1 exit: record pytest wall time before (27m23s) and after.
- Final: PLAN.md rows each marked done, deferred with a ledger entry,
  or still open in STATUS.
