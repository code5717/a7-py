# A7 execution plan

Status: approved by the user on 2026-09-16 as the plan of work, and updated 2026-09-17 with the correctness repair (Wave 1R and 2R) and the no-recursion rule. It is not approval of any language change; every change to A7 syntax or behavior still needs its own packet in [packets](packets/). This file mirrors the controlling session's plan. Current dispositions and delivery order are reconciled in [the V1 delivery roadmap](delivery-roadmap.md) and the 2026-09-20 update at the end of this file.

## Context

The user asked for one plan that: audits before changing anything; fixes every known defect; proposes language changes for approval; adds analysis and optimization layers before the Zig backend and improves generated code; adds more examples and full example software; and uses subagents plus GLM-5.3 second opinions to work faster and better. Scope confirmed with the user: full detail through release; fixed-data example apps first, interactive versions after an I/O approval; parallel agents in git worktrees **without commits**.

What exploration found (five agent reports, all read-only; shell was unavailable to them, so every claim below is from file reads and is re-verified in Wave 0):
- **No IR, no CFG.** Passes share the AST plus side tables keyed by `id(node)` (`a7/compile.py:167-404`). Constant folding replaces nodes after `type_map` and `BackendPlan` exist, so those tables go stale (`a7/ast_preprocessor.py:543-694`).
- **Unsound safety proofs.** `a7/safety.py` keys facts by name, restores a snapshot at every block exit, visits loops once and never resets facts at calls. `x := 5; { x = 0 }; 10 / x` is approved (`safety.py:170-174, 302-371, 562-563`). The type checker repeats the pattern (`passes/type_checker.py:772-778`).
- **Iteration rule broken.** `safety.py` (`_visit_stmt`, e.g. `:303-304`) and type-checker statement visits (`:775`) recurse, contrary to `CLAUDE.md:42-49`. Backend statement recursion is explicitly permitted by `CLAUDE.md:44-45`. Tests pass only because inputs are shallow.
- **Backend defects** (`a7/backends/zig.py`, 2395 lines): shadowing miscompile (declaration `x_1`, uses `x`), `arr = [arr[1], arr[0]]` prints `2 2`, `defer x = 1` emits `defer void;`, `del` capture `|p|` clashes with a user `p`, Zig keywords escaped only at uses, callee chosen by text prefix, silent `void` return for unresolved generics, quadratic else-gluing, per-print writer rebuilt and flushed, `_ = x;` discards.
- **Defect inventory:** ~35 compiler defects, ~15 documentation defects, 17 memory-plan breaking rows, gates G1–G9 and M1–M51 undecided, and two dependency cycles in `docs/plan/README.md:328-350` / `docs/plan/memory.md:660-670`.
- **Examples:** 43 single-file, fixed-data, print-only programs (`examples/000–042`), goldens in `test/fixtures/golden_outputs/`. No input, files or args exist. `test/test_parser_examples.py` ends in `assert True` (a coverage-illusion test). Local imports already merge into one Zig file (`compile.py:237-261, 597-627`), contrary to `CLAUDE.md:36-37`, but structs are not name-prefixed across files.
- **Hazards for parallel work:** `tmp/` is neither git-ignored nor skipped by `scripts/check_no_secrets.py:14-24, 80-85`. Worktrees start from commit `701c679`, which lacks all uncommitted work (`docs/plan/`, `test/test_pipeline_*.py`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `docs/SPEC.md`, `site/`). `a7/` itself has no uncommitted changes.

## Update 2026-09-16: full compiler audit and "fix it all"

The user asked for a full audit of every compiler component in subagents, then a plan to fix everything it found. Six audits reported about 150 findings (tokenizer 29, parser 25, pipeline 35, types 31, backend and safety partial). The user decided:

- **Correctness first.** No new feature work (examples beyond fixes, typed IR, docs rewrites) until every CRITICAL and HIGH audit finding is fixed or is in an approval packet in front of the user.
- **Approvals batched per area.** Crashes, hangs, miscompiles, wrong diagnostics and code Zig already rejects are fixed without asking. Every fix that changes a program that compiles and works today goes into one packet per area (lexer, parser, modules, types, safety, backend) with before/after examples.
- **Modules redesigned,** informed by Odin (and Zig, Go) research, not patched. Decided so far: **one file is one module** (its top-level names live in its own namespace, reached as `g.name` after `g :: import "geometry"`); **importing the same file twice in one file is a compile error**, whether by the same path, a different spelling of the path, or a second alias (different files may each import it; it is compiled once). **Visibility: a top-level name starting with `_` is private to its file; every other top-level name is public; names starting with `__` are reserved for the compiler** (chosen by the user from four options with examples, 2026-09-16; record as a ledger entry with the approved example when plan mode ends). The modules packet still shows the follow-ons: what happens to SPEC's `pub` keyword and existing `pub` markers (accepted as a no-op for a transition, or removed), the rejection of user names starting with `__`, and the compatibility impact on programs that call `_`-prefixed names across files today.

The fix program is Wave 1R and Wave 2R below. They replace the older Wave 1 lanes F, S and B and Wave 2.1 and 2.2. Lanes H (except H0), R, E and D, the typed IR (Wave 3) and new examples wait until Wave 2R exits.

## Wave 1R and 2R: correctness repair ("fix it all")

### Inputs

| Source | Findings | Where |
| --- | --- | --- |
| Tokenizer audit | TOK-01..29 | `tmp/audit/compiler/tokenizer.md` |
| Parser audit | PAR-01..25 plus 3 addenda | `tmp/audit/compiler/parser.md` |
| Pipeline audit | PIP-1..35 | `tmp/audit/compiler/pipeline.md` |
| Type system audit | TYP-01..32 | `tmp/audit/compiler/types.md` |
| Backend audit (partial, plan mode interrupted the write) | ZIG-1..40 (IDs 10-40 assigned from probe names by the planner) | `~/.claude/plans/iterative-bouncing-tarjan-agent-a67104b9ceb4555a9.md`, `tmp/audit/compiler/backend/` |
| Safety and preprocessor audit (partial) | SAF-1..25 (SAF-25 found by the planner from probe p18) | `~/.claude/plans/iterative-bouncing-tarjan-agent-afe708ad6db2e63b3.md`, `tmp/audit/compiler/safety/` |
| Two fix-plan designs | Batches below, with coverage tables mapping every ID exactly once | Agent reports in this session; saved to `docs/plan/fix-program/` in step 0R.2 |
| Module research (Odin, Zig, Go, primary sources) | Module design below | Saved to `docs/plan/research/modules-odin-zig-go.md` in step 0R.2 |

Round-2 packet reviews (Claude 4 HIGH, GLM 1 HIGH) also apply to P0 and P0b: `tmp/reports/packet-review2-claude.md`, `tmp/glm/review2-P0.md`, `tmp/glm/review2-P0b.md`.

### User decisions to record in `docs/plan/decisions.md` (step 0R.3)

Taken 2026-09-16 and 2026-09-17 through questions with examples:

1. Correctness first: new examples, the typed IR and docs rewrites wait until every CRITICAL and HIGH finding is fixed or is in a packet in front of the user.
2. Approvals batched per area. Crashes, hangs, miscompiles, wrong diagnostics and code Zig already rejects are fixed without asking (this is the P0.1 rule). Anything that changes a program that compiles and works today goes into one packet per area.
3. Modules: one file is one module; names from it are always written `alias.name`.
4. Importing the same file twice in one file (same path, another spelling, or a second alias) is a compile error. Different files may each import it; it is compiled once.
5. Visibility: a top-level name starting with `_` is private to its file; every other top-level name is public; names starting with `__` are reserved for the compiler. (The module research recommended enforcing `pub`; the user chose the underscore rule.)
6. A local with the same name as an import alias is a compile error.
7. All struct fields are visible to importers (SPEC 10.4's "fields are file-private" is replaced).
8. Import paths resolve from the importing file; `..` is allowed while the result stays inside the main file's folder.
9. Bare stdlib names stay: `import "io"` and `import "math"` mean the stdlib. Consequence: local `io.a7` and `math.a7` stay unimportable, so PIP-32 is closed as "not fixed by decision".

Each entry records the example the user saw. Items 3 to 9 still go through packet P-MOD for the compatibility impact before implementation.

### Module design (MOD)

From the research, adjusted to the decisions above:

- **Loading, iterative, no recursion:** a worklist keyed by real path; tokenize, parse and read errors become located diagnostics for that module (closes PIP-11's module part with CLI-02); imports resolve relative to the importing file, or to virtual `std/` or bare stdlib names; Kahn topological sort; leftover nodes form a cycle, reported with the full import chain and spans (PIP-10); depth limit 32 = longest import chain.
- **Scopes:** each module gets its own file scope; an import alias is a `MODULE` symbol in the importer's file scope; `alias.name` looks up the target module's top-level scope and applies the underscore rule; imports are never re-exported (PIP-7); alias clashes with locals and duplicate imports are errors (decisions 4, 6).
- **Types:** struct, enum and union identity is `(module_id, name)`, so two `Point`s differ; `parse_type` accepts `alias.Type` and `alias.Box(i32)` (today `mod.Type` in a type position drops `main` silently).
- **All modes:** semantic, pipeline, compile and doc modes run the same loading (PIP-17); calls through an alias are type-checked like any call (PIP-9).
- **Lowering to one Zig file:** each module becomes a struct `__a7_m{id}_{stem}` (id 0 = main file, then breadth-first discovery order); every top-level declaration keeps its A7 name inside its module struct, so calls between a module's own functions need no renaming (PIP-6, ZIG-27); `alias.name` lowers to `__a7_mN_stem.name` in value, type and generic positions; the root holds only `__a7_std`, `__a7_io`, print helpers and a `main` trampoline; a `main` in a non-main module is an ordinary function. The shape passed `zig ast-check` 0.16.0 in the research; `zig build-obj` on it is the first MOD test.
- **Rejected forms:** `using import`, named `import "m" { a }` and bare `import "m"` give `UNSUPPORTED_IMPORT` (PIP-20); `x/mod.a7` directory fallback is removed (packet item); user names starting with `__` are rejected.
- **Closes:** PIP-1, 6, 7, 8, 9, 10, 17, 20; ZIG-27; the file-module half of PIP-3.
- **Needs from other batches:** CLI-02's origin fields and tests (contract MOD keeps passing), ID-2.1 node identity (unique ids across modules), NR-02 scopes by node id, CLI-01's set of loaded files for the output guard.

### Step 0R: close the audit and prepare packets (runs alongside Wave 1R-a and 1R-b)

1. **Finish the two interrupted audits.** Resume the backend and safety auditors to run their remaining probes (backend operator matrices `p170`, `p171` with guards; safety `fall`, labeled loops, if-expression guards, cast edges, deep AST) and write `tmp/audit/compiler/backend.md` and `safety.md`. The backend auditor discloses that probes `p013`, `p052`, `p091` were run before being re-marked compile-only.
2. **Make the evidence durable.** Copy the six audit reports verbatim with source headers into `docs/audits/2026-09-16/compiler/`, add them to `tmp/evidence-manifest.txt`, write the summary `docs/audits/2026-09-16/compiler-audit.md` (counts, CRITICAL and HIGH list, batch mapping), save both fix-plan designs to `docs/plan/fix-program/` and the module research to `docs/plan/research/modules-odin-zig-go.md`, and extend the Wave 0 defect list in `docs/plan/README.md`.
3. **Record the decisions** above in `docs/plan/decisions.md`.
4. **Write the packets** (list below), compile-check every A7 example in them (`tmp/packets/check` script: A7 exit code and `zig build-obj -fno-emit-bin` exit code must match each comment), run the compatibility scan for every item with the Part E harness (`tmp/repro2/scan/analyze_e.py` pattern), then review rounds: one fresh Claude reviewer plus one GLM run per packet on `zai-coding-plan` (`tmp/glm/run_glm.sh`), at most 3 rounds, until a round finds nothing HIGH. Present all packets together.
5. **H0 probe runner** (`scripts/run_probe.py` plus its refusal test), needed by every fix batch's probes.

### Lanes for the repair

| Lane | Files | Worktree |
| --- | --- | --- |
| F1 lexer | `a7/tokens.py`, literal decoding in `a7/ast_nodes.py:536-604`, tokenizer tables in `a7/errors.py` | wt-F1 |
| F2 parser | `a7/parser.py` | wt-F2 |
| F3 CLI and pipeline | `a7/cli.py`, `a7/compile.py`, `a7/formatters/*`, `a7/module_resolver.py` (until MOD), formatter part of `a7/errors.py` | wt-F3 |
| S1 safety and folding | `a7/safety.py`, folding functions of `a7/ast_preprocessor.py`, new `a7/const_eval.py` | wt-S1 |
| S2 typing and names | `a7/passes/type_checker.py`, `a7/types.py`, `a7/generics.py`, `a7/passes/name_resolution.py` | wt-S2 |
| S3 validator | `a7/passes/semantic_validator.py` | wt-S3 |
| B backend | `a7/backends/*`, non-folding functions of `a7/ast_preprocessor.py`, `a7/stdlib/*` | wt-B |

Serialization points: `a7/errors.py` (F1 then F3), `a7/compile.py` (all F3 batches in order), `a7/backends/zig.py` (all B batches in order), and the approval call sites in `zig.py`, which S1 owns. At most 3 worktrees build Zig at once.

### Wave 1R-a: CRITICAL hangs and miscompiles (no approval; applied first)

| Batch | Closes | Change | Lane | Class |
| --- | --- | --- | --- | --- |
| PR-00 | PAR-01 | `parse_match_statement` raises "Expected 'case' or 'else'"; a no-progress guard in every bracket-terminated loop of the parser raises a located parse error | F2 | A |
| C1 | ZIG-1 = SAF-7, SAF-10, SAF-12, SAF-13, SAF-14, folded half of ZIG-11; baseline test #12 | Folding copies the replaced node's type entry to the new node and keeps replaced subtrees alive until codegen, so ids are never reused; new `a7/const_eval.py` folds integers exactly (truncating `/` and `%`), only when the result fits the node's type, shifts only below the width, floats only when finite | S1 | C, B, A |
| C2 (= PL-01) | PIP-2, PIP-3, PIP-23 code, ZIG-5, SAF-9, B14, `_MATH_BUILTIN_MAP` part of ZIG-36 | Name resolution annotates a callee or field-access root with its module only when scoped lookup finds a `MODULE` symbol; `_resolve_stdlib_call` drops the raw-name fallback and the bare-builtin branch; `zig.py` `_scan_features`, `_is_io_call`, `_emit_call` read only `stdlib_canonical` | S2 then B | C |
| C3 | ZIG-2, ZIG-39 (= parser addendum redirected stdout), ZIG-6 | If-expressions emitted parenthesized; print helper uses `writerStreaming` instead of the positional `writer`; named struct-literal fields reordered to declaration order (SPEC A.1 item 4) | B | C |
| PL-02 | PIP-1 (stopgap until MOD) | `_annotate_file_module_calls` walks scope frames on an explicit stack and skips aliases shadowed by a local; wrong detection fails as a Zig build error, never a wrong result | F3 | C |
| C4 | SAF-20..25 | Deferred statements visited on a snapshot (p18 `defer x = 5` no longer approves `10 / x`); for-in iterator facts; nested functions checked; `::` constant facts seeded; correct diagnostic categories and operand-span fallback | S1 | A, B, D |
| T0 | TYP-05 | Compound-assignment operand checks read `node.operator` | S2 | B |
| V1 | TYP-03 | Iterative Tarjan SCC replaces the exponential recursion search | S3 | A |

Progress (main tree, uncommitted; gate logs under `tmp/baseline/`). Each batch
below was gated when it was applied: 11/12 checks, with the same known failing
pytest tests as `docs/audits/2026-09-16/baseline.md` and none new.

**The baseline has since changed.** A separate session audited and repaired this
tree on 2026-09-19 ([docs/audits/2026-09-19](../audits/2026-09-19/README.md)),
closing the artifact, diagnostic and native-binding failures; its gate passed all
nine checks with 2,629 tests and no failures. Comparisons against "12 known
failures", or against the 11 that remained after C1, are stale from that point
on. Re-establish the baseline from a fresh gate run before judging a new batch.

| Batch | State | Evidence |
| --- | --- | --- |
| C3 | Applied 2026-09-17 | Verifier PASS; gate 2522 passed |
| PR-00 | Applied 2026-09-17 | Verifier PASS; gate 2528 passed |
| T0, V1 | Applied 2026-09-17 | T0 PASS. V1's first version dropped recursion diagnostics main emits; refixed to reproduce them exactly, re-verifier PASS (1,200 CLI programs and 562,144 call graphs identical to main; 24-layer program 0.11 s against 67 s). Gate 2549 passed |
| NOREC-0 | Applied 2026-09-18 | Verifier PASS: every recursive group in `a7/` is listed (399 call edges read, plus a trace of the whole pytest run). Scanner blind spots (dispatch tables, lambdas, `singledispatch`) and two false positives go to NOREC-0b before any conversion. Gate 2568 passed |
| PL-02 | Applied 2026-09-18 | Verifier PASS: 45 probes over every binding form, no missed local; differential over 862 programs changed only f03, m22b and a known `id()`-reuse probe. Gate 2575 passed |
| C1 | Applied 2026-09-18 | First verification FAIL (the finite-only float rule changed a program that built); refixed to fold floats in f64 including inf and NaN and emit `std.math.inf(f64)`/`std.math.nan(f64)`. Re-verifier PASS: 52-probe float sweep matches IEEE f64, 1,524 integer boundary comparisons with 0 mismatches against 60 wrong on HEAD. Gate 11/12 and **one baseline failure fixed**: `test_large_integer_folding_preserves_exact_quotient_and_remainder` now passes, so the known-failure list drops from 12 to 11; 2601 passed |
| C4 | Fix applied in the worktree, re-verification running | Verifier FAIL on one case: a `defer` that assigns inside a loop is invisible to the next iteration, so `while ... { defer x = 0; y := 10 / x }` went from exit 6 to accepted and divides by zero on iteration 2; it builds once Z4 fixes `defer void;`. Fix: havoc the facts for identifiers a deferred statement assigns. Everything else confirmed |
| C2 | Applied 2026-09-18 | Verifier PASS: every reproducer flipped, no stdlib spelling stopped working, 963-file differential with identical exit codes and exactly 8 intended Zig differences. Gate 11/12, same 12 failures, 2582 passed (the gate's bare `pytest` step also collected a concurrent auditor's copied test tree; the scoped rerun over `test/` is the clean result) |
| C4 | Applied 2026-09-19 | Waived under ledger L32, then narrowed to identifier targets at the owner's request: a deferred write through a base (`defer b.value = 0`) no longer discards the base's own facts, which is sound because every fact is keyed by identifier name in `FactMap.by_symbol`. Differential over 2,030 programs: 0 changed. Gate **9/9, exit 0**, 2,651 tests |

C4 lands before Z1 and Z4: fixing `defer void;` (B11) and capture shadowing (B9) first would turn a Zig rejection into a division by zero that builds (SAF-24, SAF-25).

### Wave 1R-b: remaining no-approval fixes (serialized per file)

| Lane | Batches in order |
| --- | --- |
| F1 | **LX-01** columns (TOK-04, TOK-27; baseline #5) → **LX-02** literal and name diagnostics: crash forms of TOK-03, TOK-08, TOK-09, TOK-15, TOK-24 → **LX-04** shared line table (TOK-10, TOK-25) |
| F2 | **PR-01** spans and parse diagnostics (PAR-04, 09, 14, 21, 24) → **PR-02** explicit no-struct-literal context, fn-type return stop set, assignment-target restriction, `defer` restrictions (PAR-02, 11, 13, defer half of 20; corpus AST diff first, any change to a building program moves into P-PAR) → **X-DEPTH** recursion limit becomes a located parse error (PAR-08, parser part of PIP-14) → **PR-03** declaration cap and stdout warning (PAR-17) |
| F3 | **CLI-01** outputs and artifacts (PIP-12, 19, 22, 26, 27; baseline #1-4) → **CLI-02** module errors with origins (PIP-11; baseline #6-8; needs the S2 origin hook) → **X-JSON** valid and bounded JSON (PAR-05, 16, PIP-16, 25, TOK-26; `schema_version` 2.1) → **X-RICH** markup-safe output and diagnostics on stderr (TOK-06, PAR-07, PIP-13, PIP-24) |
| S2 | **T1** `NilType` (TYP-10 accepted cases) → **T2** globals typed first, unknown type becomes an error (TYP-01 B and C cases incl. v17, TYP-12, TYP-16, ZIG-31, TYP-22 duplicates; scan first) → **T3** operator and literal typing rows Zig rejects (TYP-06, TYP-07 partial, TYP-09, 19, 20, ZIG-21, SAF-13, SAF-14; replaces the cast matrix's self-computed expectations) → **T4** aggregates and arrays (TYP-11, 17, 08; SAF-31 positional struct field names taken from the last struct of that name) → **T5** lvalue roots and implicit `ref` (TYP-14, 15, B7, B8) → **T6** match typing (TYP-13, ZIG-12, TYP-30 part) → **T8** diagnostics and scope-matching dict (TYP-21, 22, 29) → **TYP-26** delete dead generic engine → **NR-01** name-resolution duplicates (PIP-18 enum part, 29, 30, 31) → origin hook for CLI-02 |
| S3 | **V2** false rejections (TYP-24) → **V3** defer, labels, `main` signature (TYP-23, ZIG-15) |
| B | **Z1** names: escaping at declarations, reserved and preamble collisions, capture names, labels (B9, B10, B12, B15, ZIG-17, 18, 19, 23, 25, SAF-19; baseline #9-11) → **Z2** usage and mutation keyed by declaration (ZIG-13, 14, SAF-15..18) → **Z3** literal emission (ZIG-10, 11, 20, 21, ZIG-41 if- and match-expressions whose arms are all integer literals with a runtime condition, which Zig rejects; TOK-07 emitter half) → **Z4** statement lowering (ZIG-9, B11, B13, ZIG-16, 22, `<<=` half of ZIG-7) → **Z5** codegen-stage false rejections (ZIG-30) → **Z6** `zig fmt` clean output (ZIG-35) → **Z7** dead code and fail-closed defaults (ZIG-36, 38) → **Z8** backend test helper runs the real pipeline (ZIG-37) |

### Wave 1R-c: fixes after packet approval

| Lane | Batches |
| --- | --- |
| S1 (P0b revision 3 approved) | **SD** fact sources (SAF-1 nil `ref` argument checked at call sites, SAF-2, SAF-5, SAF-11; SAF-28 negative float literal casts and SAF-30 parameter type ranges seeded, both class D) → **SA** join engine on an explicit stack, ported from `tmp/repro2/scan/analyze_e.py:109-422` with three corrections: delete `_learn_after_stmt` (SAF-4), `fall` passes state into the next case, file-scope `VAR`s handled in SB (P0b.1, P0b.4, SAF-3, 4, 23, 25, SAF-26 un-braced `else` restores no facts, SAF-27 if-expression guard facts) → **SB** call invalidation (P0b.3, SAF-6) → **SC** loop fixpoint with widening (P0b.2 option c, S2, E8) → **SE** `del` tracking by access path (P0b.5-8, SAF-8, S7) |
| F1 | **LX-P** approved P-LEX items |
| F2 | **PR-P** approved P-PAR items, replacing the parser's coverage-illusion tests |
| S2, S3 | approved P-TYP items |
| B | approved P-BK items |

### Wave 2R: structural repairs (still correctness-first)

1. **ID-2.1** node identity, serial with all lanes paused: `node_id` numbered before name resolution in every mode; `@dataclass(eq=False)` with iterative `repr` and an `ast_equal()` test helper; every runtime-set attribute declared; match expressions get `else_expr`; dead fields and the `type_args` branch removed (PAR-15, addendum). C1's retention list is replaced by ids.
2. **NR-02** scopes paired by node id; use-before-declaration in blocks; file-scope self-dependency (PIP-4, 5, 15, 33) — S2.
3. **X-SYM** every stdlib and module call resolved by symbol, completing C2 — S2 then B.
4. **MOD** module redesign (above) — F3, S2, B, after packet P-MOD.
5. **R** recursion limits: type checker and validator on explicit stacks (TYP-18); backend "nesting too deep" diagnostic until the IR emitter (ZIG-32); rest of PIP-14.
6. **T7** generics checked per instantiation (TYP-04 no-approval parts, TYP-25, ZIG-29, TYP-28) — S2.
7. **AST-INLINE** local inline struct literal (parser addendum q34); **TYP-27** dead fact state; **CLEAN** dead lexer and parser code (TOK-22, PAR-25, unused `MAX_STRING_LENGTH`); **VIEWS** AST views (PAR-23, PIP-34); **DOC-LEX** SPEC lexical text (TOK-28).

Wave 3 adds **SRC-MAP** (TOK-23, TOK-29) with the IR builder.

### No recursion anywhere in the compiler (user instruction, 2026-09-17)

The user asked that no recursion be used in the code. This removes the two exceptions `CLAUDE.md` allowed (recursive-descent parser, backend statement emission). A static call-graph scan (`tmp/recursion/scan.py`) found 31 recursive groups in `a7/` on 2026-09-17, some of them false positives from approximate call resolution (for example `SymbolTable.lookup` delegating to `Scope.lookup`, and `__init__` through `super()`).

- **NOREC-0, enforcement (first, lane H):** `test/test_no_recursion.py` builds the call graph of every function in `a7/` with Python's `ast` module (explicit stack, receiver-aware resolution so delegation to another class is not a cycle), finds strongly connected components and self-loops, and also flags `copy.deepcopy` and dataclasses with recursive `__eq__`/`__repr__` over AST nodes. It starts as a ratchet: the test holds the list of today's verified recursive groups and fails on any group not in the list, and on any listed group that no longer exists (so the list shrinks with each conversion). Every false positive is fixed in the scanner, not allowlisted. A second test runs the full pipeline on generated deep inputs (nesting depth well past the default limit: 5000 nested parentheses, blocks, else-if arms, binary chains, nested calls, nested generics) at the default recursion limit and at limit 100.
- **Conversions, each after the correctness batches that edit the same file:**

| Component | Recursive groups | Batch | Lane and order |
| --- | --- | --- | --- |
| `a7/types.py` | structural `equals`, `__str__` and `__hash__` over composite types | NOREC-TY: pairwise equality worklist and iterative rendering/hashing | S2, with T2 |
| `a7/symbol_table.py`, `a7/formatters/console_formatter.py`, `a7/generics.py` (`copy.deepcopy`) | `dump` converted 2026-09-20; `format_statement_label`, the rest of `format_type` and deepcopy remain | NOREC-SMALL (generics removed by TYP-26) | F3 after X-RICH; S2 |
| `a7/module_resolver.py` | `load_module` | MOD's iterative worklist | Wave 2R |
| `a7/ast_preprocessor.py` | `_annotate_function` and `_hoist_nested_functions` | NOREC-PRE | B, with Z2 |
| `a7/safety.py` | `_visit_stmt`, `_visit_expr`, `_always_returns`; `_int_literal` converted 2026-09-20 | SA explicit-stack port | S1, Wave 1R-c |
| `a7/passes/semantic_validator.py` | `visit_statement`/`visit_defer_stmt`, exits-block pair, `_returns_on_all_paths`, call scheduling | R | S3, Wave 2R |
| `a7/passes/type_checker.py` | statement visitor (6), expression visitor (21), type resolution (3), range patterns (2), four self-loops | R | S2, Wave 2R after T-batches |
| `a7/backends/zig.py` | statement visitor, expression emitter, `_emit_semantic_type`; mutation-base helper converted 2026-09-20 | NOREC-BE: explicit task stack for statements (open, close, text tasks) and bottom-up rendering for expressions, keeping output byte-identical; the Wave 3 IR emitter reuses it | B, Wave 2R after Z-batches |
| `a7/parser.py` | statement parser (8), expression parser (20) | NOREC-PAR: statements parsed with an explicit frame stack; expressions with operator-precedence parsing on explicit operand and operator stacks (shunting-yard with prefix, postfix, call, index, field, cast, if-, match- and struct-literal forms as stack frames); AST output must be identical on the whole 2440-program corpus (`ast_equal` diff) | F2, Wave 2R after PR-P |

The compiler dataclasses also require a NOREC-DATA batch for generated equality
and representation methods. The baseline scanner records 44 such methods.
Disabling a generated method requires checking its callers and preserving the
required comparison or diagnostic behavior; it is not an automatic fix.

- **Docs:** `CLAUDE.md` and `AGENTS.md` state the rule without exceptions and name `test/test_no_recursion.py` as its enforcement (done 2026-09-17 on the user's instruction).
- **Exit:** the ratchet list is empty; the deep-input test passes at recursion limit 100. This is part of the correctness-first exit.

### Approval packets (one per area, presented together in step 0R.4)

| Packet | Items |
| --- | --- |
| P0 revision 3 | L20 reading; L17 vs L19; track split and the P9 exception; gate changes; `tmp/` ignore; `CLAUDE.md`/`AGENTS.md` corrections (all recursion sites and the formatter). P0.1's rule is now decision 2; its list is replaced by the Wave 1R-a and 1R-b tables. Apply the round-2 review findings |
| P-SAF = P0b revision 3 | P0b.1-9 with round-2 corrections (counts stated per combination; per-item decision lines; SAFETY_CONTRACT line 40-41; P0b.9 forms; 026 edit shown), plus P0b.10 nil `ref` argument (SAF-1), .11 field named `ptr` (SAF-2), .12 match facts (SAF-3), .13 else-branch fact (SAF-4), .14 `a / b` non-zero (SAF-5), .15 globals across calls (SAF-6), .16 double `del h.child` (SAF-8), .17 out-of-range intervals (SAF-11) |
| P-LEX | Unclosed `/*` (TOK-05); newline inside `/* */` ends a statement (TOK-12); digit or letter after a number (TOK-02, TOK-20); ASCII digits only (TOK-03); `\xHH` above 0x7F and SPEC escapes (TOK-01, TOK-13, ZIG-4); non-ASCII text (TOK-17, TOK-07, P2/G6); raw newline in a string (TOK-11); tabs (TOK-18); raw CR (TOK-19); keyword and punctuation set (TOK-16); Unicode `$T` if one builds (TOK-09); empty file (PIP-28). TOK-14 moves to P-MOD, since decision 5 gives `_` a meaning |
| P-PAR | Every parse error fails (PAR-03, F2/C5); duplicate `else` (PAR-10); `$T` in expressions (PAR-12); separators required (PAR-19); `if`/`while` bodies need a block (PAR-20); `using import` (PAR-18, aligned with MOD); newlines inside array and positional struct literals (PAR-06); `pub` on fields (PAR-22, aligned with decision 7); PR-02 scan hits if any |
| P-MOD | Decisions 3-9 with compatibility impact; cycles forbidden with the chain reported; fate of `pub` and existing `pub` markers; `__` names rejected (TOK-14); `x/mod.a7` fallback removed; named and bare imports rejected; depth limit = longest chain; generated Zig layout (module structs) and whether single-file programs also get a module struct; PL-A1 declaration vs alias clash |
| P-TYP | Use before declaration with a type change (TYP-01 v19); recursion through function values gets call-graph edges (TYP-02); conflicting `$T` inference (TYP-04 g05); `r = nil` rebinding (TYP-10 p02); bare typed math names (PIP-23 PL-A2) |
| P-BK | Untyped locals get their A7 type instead of Zig comptime values (ZIG-3); `{{` in format strings (ZIG-33) |
| Rows added to existing packets | P4: `f64` to `f32` cast needs no proof and gives `inf` (SAF-29); mixed-width operands and implicit widening that build (TYP-06, TYP-07), runtime shift count obligation (ZIG-7, TYP-06 c14). P5: inactive union field reads (ZIG-8), capture rule (PIP-21, TYP-30 d23), `pts: [3]Pt` |

### Deferred or not fixed

| Finding | Disposition |
| --- | --- |
| PIP-32 | Not fixed, by decision 9 |
| TOK-21 length caps | Deferred to G6; unused constant deleted in CLEAN |
| PIP-35, ZIG-36 remainder | Removed by MOD and the Wave 3 IR |
| ZIG-40, nested-function part of SAF-16 | Packet with module and scoping decisions; C4 already turns their failure into exit 6 |
| ZIG-34 print formats | P10 (strings and printing) |
| ZIG-38 overflow approvals, dead `_prove_integer_overflow` | P3 |
| ZIG-24 | P5 |
| TYP-07 32-bit `isize` | G9 |
| TYP-31 | No action (observations) |
| TYP-32 | Already scheduled items |
| Proof precision: field-path guards, per-path use-after-`del`, slice and string parameter indexing, for-in index upper bound | Wave 4 track 5 on the IR |

### Verification

- **Per batch:** failing test first, confirmed failing on the current tree; the verifier writes expected A7 exit, Zig build result and Debug/ReleaseFast output before reading the implementation; one counterexample; audit probes copied into `test/fixtures/regressions/<component>/` (tests never read `tmp/`); new walkers get a recursion-limit-100 test.
- **Soundness groups (C4, SD-SE):** every rejected program has an accepted guarded twin that builds in Debug and ReleaseFast; the Part E scan re-run on the final code must match the counts stated in P0b.
- **Gate after every patch:** `./run_all_tests.sh` in the background under `timeout 2700`, compared with `docs/audits/2026-09-16/baseline.md`. The 12 failing tests close as follows: #1-4 CLI-01, #5 LX-01, #6-8 CLI-02 with the S2 hook, #9-11 Z1, #12 C1. Wave 1R-b exits only with all 12 passing.
- **Compatibility scans:** every no-approval batch runs the 2440-program harness; a hit on a program that builds today moves the item into its area's packet.
- **Coverage-illusion tests replaced** as part of their batches: the 31 `assert isinstance(result, bool)` semantic tests, the cast matrix computing expectations with `classify_cast`, parser `PROGRAM`-only tests and `assert True` endings, tokenizer tests without `else: fail`.
- **GLM security reviews (L12) on `zai-coding-plan`:** C1, C2, PL-02, CLI-01, CLI-02, T5, and SD-SE as one group.
- **Exit of correctness-first:** Wave 1R-a, 1R-b, 1R-c and Wave 2R items ID-2.1, NR-02, X-SYM, MOD and T7 landed; every remaining CRITICAL or HIGH finding is in a packet the user has seen; an independent auditor re-runs all six audits' CRITICAL and HIGH probes and confirms each is fixed or deferred with a reason. Then lanes H, R, E, D and Wave 3 resume.

## Ground rules (apply to every step)

1. **Approval rule.** No change to A7 syntax or observable behavior without a packet showing current behavior, proposed behavior, A7 examples and compatibility impact, and explicit user approval. Dispositions go in `docs/plan/decisions.md`. Research and reviewer recommendations are not approval.
2. **Triage test** (confirmed in packet P0; tightened after audit B-1). A fix needs no approval only if **every program that A7 accepts and Zig builds today keeps the same accept/reject result and the same output**. Allowed without approval: A7 crashes and internal errors; diagnostic text, location and exit-code corrections; A7-accepted programs that Zig rejects becoming A7 rejections, or being lowered correctly where SPEC defines the operation unambiguously; a rejected program becoming accepted **only** when a docs defect row names it as wrongly rejected and SPEC is unambiguous; and a miscompile corrected, where the emitted Zig does something other than the source operation and SPEC states the intended behavior unambiguously (output becomes correct, accept/reject unchanged; e.g. `arr = [arr[1], arr[0]]` printing `2 2`). Everything else needs a packet, including rejecting undefined behavior that builds today, any new defined semantics, and anything where SPEC contradicts itself. Every no-approval fix still runs a compatibility scan; if any example, test, golden or doc snippet changes, it escalates.
3. **Test-quality rule** (`CLAUDE.md` Test quality). Prefer real CLI plus real Zig, Debug and ReleaseFast, with expected output derived independently before running.
4. **Never run memory-unsafe probes.** Probe files carry `// probe: compile-only` or `// probe: run-allowed`; the run helper refuses compile-only files, and one test proves the refusal.
5. **No commits, no pushes.** Changes move between worktrees and the main tree as patches (see Orchestration).
6. **Writing style** (`CLAUDE.md` Writing style) for every report, packet and doc.
7. **Research lands in docs** (ledger L14): conclusions go to `docs/plan/` or `docs/audits/<date>/`; raw agent and GLM output stays in `tmp/`.

## Orchestration

### Roles
- **Controller (this session):** writes task cards, creates and syncs worktrees, applies patches, runs the full gate, decides, talks to the user. Never accepts a self-report as evidence; confirms at least two verifier claims with its own tool output.
- **Explore agents:** read-only search.
- **Implementer (general-purpose agent):** one task, one worktree, owned files only.
- **Verifier (fresh general-purpose agent, never the implementer or its fork):** works in the implementer's worktree and records its path; derives expected results before reading the implementer report, re-runs every command, tries one counterexample (unsafe variant still rejected; perturbed input changes output).
- **Auditor:** independent doc or plan audit against sources; each round is a new agent that has not seen earlier fixes.
- **GLM-5.3:** second opinion, one separate CLI process per use case.
- **Workflow scripts** (user opted in by asking for agent orchestration): used for fan-out stages such as the capability probe, reproduction ledger and audit rounds; stay under 15 agents per workflow.

### Lanes (file ownership; one owner per lane at a time)
| Lane | Owns | Where |
| --- | --- | --- |
| F frontend | `a7/tokens.py`, `a7/parser.py`, `a7/cli.py`, `a7/formatters/`, `a7/errors.py` | worktree |
| B backend | `a7/backends/*`, `a7/ast_preprocessor.py` (non-folding functions) | worktree |
| S safety/typing | `a7/safety.py`, `a7/passes/*`, folding functions in `a7/ast_preprocessor.py` | worktree |
| IR | new `a7/ir/*`, new `test/test_ir_*.py`; one-hunk wiring in `a7/compile.py` | worktree |
| H harness | `scripts/*`, `run_all_tests.sh`, `.gitignore`, `pyproject.toml` pytest settings, `test/test_parser_examples.py`, `test/test_examples_e2e.py`, `test/test_error_stage_matrix.py`, harness tests | worktree |
| L stdlib | `a7/stdlib/*`, stdlib tests | worktree |
| E examples | `examples/**`, `test/fixtures/golden_outputs/*` (pre-assigned numbers) | worktree, up to 2 |
| D docs | `README.md`, `docs/**`, `site/public/**`, `CLAUDE.md`/`AGENTS.md` (only with user instruction) | **main tree only**, last in each wave |
| R research | `tmp/`, then `docs/plan/research/`, `docs/audits/` | main tree |

Lanes B and S both touch `zig.py` approval sites; S owns `_require_backend_approval` call sites, B owns lowering. Their patches apply serially.

### Worktree flow without commits
A script `tmp/orchestration/wt.sh` implements these steps so they run identically every time.
1. `git worktree add --detach ../a7-wt/<id> HEAD` (outside the repo, so the secrets scan and pytest never see it). Append `tmp/` to the worktree's `info/exclude`.
2. **Sync in:** `git -C <main> diff HEAD --binary > tmp/sync/<id>.patch` and apply it in the worktree; copy every file from `git -C <main> ls-files --others --exclude-standard` (with no commits, every new file stays untracked, so a fixed list goes stale); then `git -C <wt> add -A` so the synced state becomes the index baseline. Staging is not a commit.
3. `uv sync` inside the worktree (`.venv` is per checkout).
4. Implementer edits the working tree only, never runs `git add`, `commit`, `restore`, `stash` or `checkout`, and never creates binary files.
5. **Export:** controller checks `git -C <wt> diff --cached --quiet` (no staged changes), then `git -C <wt> add -N -- <owned paths> && git -C <wt> diff --binary -- <owned paths> > tmp/patches/<id>.patch`.
6. Controller reads the patch and checks it touches only owned paths, runs `git apply --check`, applies it to the main tree, runs the gate in the background. If `--check` fails: re-sync the worktree and ask the implementer to rebase its change. If the gate fails: revert in LIFO order with `git apply -R --check` then `git apply -R`, and return the log to the lane.
7. After any patch lands, re-sync every open worktree whose owned files intersect the patch, and re-run probe rows and examples affected by S, B or F patches.
8. Remove the worktree with `git worktree remove --force` once its patch is applied or abandoned.

### Limits and failure handling
- At most **3 GLM processes** at once, started ~10 s apart; at most **6 agents** machine-wide, of which at most **3** run Zig builds; exactly **one** `./run_all_tests.sh` machine-wide, wrapped in `timeout 2700`, always in the background. A missing `Summary:` line counts as FAIL.
- Every shell command redirects to `tmp/<id>/<step>.out` plus a `.rc` file, read back with Read. A missing file counts as NOT RUN, never as a pass.
- GLM: `TMPDIR=./tmp timeout 2400 opencode run --dir <tree> --agent plan -m zai-coding-plan/glm-5.3 "<prompt>" > tmp/glm/<use>.md 2>&1`. **Provider: always `zai-coding-plan`** (user, 2026-09-16); `zai-coding-plan/glm-5.3-flash` is allowed. Do not use `opencode-go`. **Exit code 0 does not mean success:** a run counts only if the output contains `claims checked:` and no `Rate limit` or `usage limit` error. opencode does not exit on a provider limit; it idles until `timeout`, so `tmp/glm/run_glm.sh` retries a run up to 3 times with growing backoff when the output has a limit error or no `claims checked:` line. The rate limit is shared across the account, including the user's other sessions, so GLM runs go one at a time while throttling shows in `~/.local/share/opencode/log/`. On "database is locked", retry 3 times with 30/60/120 s backoff. On timeout keep partial output, split the prompt, rerun.
- GLM read-only is prompt-enforced only, so the controller records `git status --porcelain` and `git diff --stat` before and after each run and rejects the run if the tree changed.
- Crashed agents are resumed from the task card, reports and `git -C <wt> diff`, not from the dead agent's summary.
- `tmp/orchestration/ledger.md` records task, lane, worktree, patch, verifier result, GLM result, gate result. Promoted to `docs/audits/<date>/` at each wave end.

### When GLM is used
Worth it: plan and inventory audits; soundness changes in safety or the IR fact engine; security-relevant fixes (ledger L12); each approval packet before it reaches the user; implementer/verifier disagreements; option research for gates (options only). Not worth it: example authoring, golden diffs, harness plumbing, mechanical edits.

### Prompt templates (stored in `tmp/templates/`, summarized)
- **Implementer:** task id, worktree, owned and forbidden files, goal, acceptance commands with expected results; CLAUDE.md rules; redirect every command to files; write `tmp/reports/<id>-impl.md` mapping each claim to command, raw output and file:line; mark NOT RUN; never run git add, commit, restore, stash or checkout; no binary files.
- **Verifier:** "You did not write this change." Derive expected results first; re-run every command; mark each claim CONFIRMED / REFUTED / UNCHECKED with evidence; one counterexample; no fixes; `tmp/reports/<id>-verify.md`.
- **GLM second opinion:** "Deep research and audit, read-only. Do not trust any summary, including this prompt. Open the file for every claim and quote the line with file:line; write NOT FOUND if absent. Mark INFERENCE and UNVERIFIED. Look for unsound proofs, accepted-but-unsafe and rejected-but-safe programs, Debug/ReleaseFast divergence, overflow, docs implying parsed-only features work, stale counts, contradictions between README/SPEC/STATUS/site. Double-check each finding a second time against the file before reporting. Output numbered findings with severity, evidence and a suggested counter-test, ending with `claims checked: N`. Do not edit files or run memory-unsafe programs."
- **Example author:** pre-assigned number; only capabilities marked PASS in the probe report at the current compiler patch; workarounds for listed bugs; write expected output into `tmp/<id>/expected.out` before the first A7 run, by hand or from an independent Python model written first; build Debug and ReleaseFast; golden only if all three match; a mismatch is reported as a possible compiler bug with a minimal reproducer, never "fixed" by changing the example.

### Audit rounds for docs, plans and packets
Independent rounds, each checking every changed sentence against its source. Stop after a round with zero defects, or after 3 rounds with the remainder listed for the user. Re-audit each round's fixes.

---

## Wave 0: Audit before change (no code changes)

**0.1 Audit this plan.** Three GLM processes in parallel, one per area: (a) compiler architecture and IR design, (b) defect triage and approval flow, (c) examples, harness and orchestration. One Claude auditor checks every file:line claim in this plan. Findings are merged; material changes go back to the user before 0.2.

**0.2 Workspace safety.** Done: `tmp/` is in `.git/info/exclude`. Propose `.gitignore`, `check_no_secrets.py` skip and pytest ignore entries for `tmp/` in packet P0 (the secrets check scans `tmp/`; baseline proved it).

**0.3 Baseline.** Record `git rev-parse HEAD`, `git status --porcelain`, `zig version`, and a full `./run_all_tests.sh` log with wall time. Name the currently failing tests (the plan cites 12 failing pipeline tests, `docs/plan/README.md:331`). Write `docs/audits/<date>/baseline.md`.

**0.4 Reproduction ledger.** A workflow fans out reproduction of every inventory item (compile-only unless benign) against HEAD; three GLM re-audits run alongside, split frontend / backend+typing / safety+memory (the last is the L12 security review). Output `docs/plan/audit/<date>-inventory-repro.md`: id, source, command, exit code, diagnostic, emitted Zig, Zig result, status (current / not reproduced / different). Also reproduce the unverified items: shadowing miscompile, keyword escaping, `defer x = 1`, recursion at limit 100 on deep statements, whether `int`/`uint` resolve as types, what `last: Pt` lowers to, float `%` folding on negatives, `SPEC.md:698-716` generic examples.

**0.4b Full compiler audit (user request, 2026-09-16).** Six independent Claude agents, one per component, read every file in scope and report findings marked NEW or KNOWN with compile-only reproducers, severity, and whether a fix would change programs that build today: tokenizer; parser and AST; pipeline, modules, name resolution, CLI, formatters and stdlib; type checker, types, generics and semantic validator; Zig backend; safety pass and AST preprocessor. Shared instructions: `tmp/audit/compiler/PROMPT-COMMON.md`. Reports: `tmp/audit/compiler/<component>.md`, merged into `docs/audits/2026-09-16/compiler-audit.md` and the Wave 0 defect list. GLM security second opinions (L12) on the backend and safety findings follow on `zai-coding-plan`. New defects feed the P0.1 list or packets before Wave 1 starts.

**0.5 Compatibility scan and triage.** For each proposed new rejection or behavior change, search `examples/`, tests, goldens, SPEC, README and `site/public/`. Final triage into (a) fix now, (b) packet, (c) language decision. GLM reviews the triage.

**0.6 Plan-document fixes** (not language changes). **Done 2026-09-16** in `docs/plan/README.md` (work tracks table and the note after it; the track 1 defect list split into no-approval and approval groups; the `é` diagnostic row corrected), `docs/plan/memory.md` (phase C1 dependencies; a note after the phases table) and `docs/plan/research/memory/review/README.md` (M-10 resolved). Line numbers below are from before the edit. Break the two cycles, whose edges are `docs/plan/memory.md:664, 669` against `docs/plan/README.md:338-341` (the note at `docs/plan/README.md:348-350` and `docs/plan/memory.md:25` describe them):
- Track 3 → **3a** wrapping (L5), **3b** other numerics (G1, G3).
- Track 6 → **6a** phases B, C1, C1′, D, E, C2; **6b** phase F qualification plus phase G. Tracks 9 and 10 depend on 6a; 11 on 6a and 10; 6b on 9, 10, 11.
- Track 7 → **7a** optionals and tagged-union matching; **7b** Result and error propagation.
- Track 8 → **8a** core collections (`List`, `Map`, `Table`, `Id`, owning `string`), C1 depends on 8a; **8b** rest of stdlib (files, paths, time, random, process, recoverable I/O) depends on 6a and 7b. Minimal buffer-based I/O (packet P9) is proposed as an exception that may land before 8b; the user confirms it in P0.4.
- Fix `docs/plan/README.md:372-376`: `case ok` moves to P5, the `é` string to P2. Fix `docs/plan/README.md:251`: the `é` identifier diagnostic already reads `'é'` (Wave 0 citation audit). Track 6 stops mentioning deletion. GLM reviewed the split: it removes both cycles and creates none (audit B-11).

**0.7 Packets P0 and P0b to the user.**
- **P0, plan confirmations** (not language changes): the tightened triage test; the L20 reading (`docs/plan/decisions.md:74-75`); Kimi's L17 vs L19 question; the cycle split; harness gate changes (parallel `--jobs`; optional removal of the e2e Debug build, which duplicates the artifact gate that already builds Debug and ReleaseFast against the same golden and runs `zig fmt --check`); `tmp/` ignore entries; corrections to `CLAUDE.md`/`AGENTS.md` on the iteration rule (true only for `safety.py` and the type checker) and on local imports (`CLAUDE.md:36-37` is stale).
- **P0b, fail-closed rejections of unsafe programs that build today** (language behavior change, so a packet): each with current A7, proposed diagnostic and compatibility scan. (1) Facts from assignments in nested blocks survive block exit, so `x := 5; { x = 0 }; 10 / x` is rejected. (2) Facts of variables assigned in a loop body are dropped at loop entry. (3) Facts of by-ref argument roots are dropped after a call. (4) Returning a slice of a local stack array. (5) Double `del` through an alias or in a loop. (6) `del` through a `ref` parameter. (7) String `==` between local variables holding literals, which builds today and compares addresses (ledger B3). (8) `defer del p` followed by `del p`, which the safety pass does not track (`safety.py:379-389`) and which frees twice. For (3), because a `ref` parameter can be stored in a field or global and a later call can mutate the local through it (audit A-26), the conservative rule drops facts after every call for every local that has ever been passed by reference anywhere in the function. The IR fact engine later replaces (1)-(3) with a full dataflow analysis under P7.

**Exit:** baseline recorded; ledger complete; triage and cycle split reviewed by GLM; P0 and P0b answered.

## Wave 1: Fixes without approval, harness, probe, small examples

> Superseded in part (2026-09-17): lanes F, S and B are replaced by Wave 1R above; packets P1, P2 and P0b are replaced by P-LEX, P-PAR and P-SAF. Lane H (except H0), lane R, lane E and lane D run only after the correctness-first exit.

Runs as five parallel lanes, patches applied serially F → S → B → H → E → D.

**Lane F (frontend and CLI).** Parser warnings go to stderr, not stdout (`parser.py:201-206`; today they break `--format json`, ledger F4); `--format json` on a match yielding a struct exits 8 instead of crashing with a `TypeError` in `json_formatter.py:215` (ledger F5); remove the 1000-declaration cap (`parser.py:153`; today valid programs over 1000 declarations exit 5, ledger F3), after Lane D adds the defect row the triage test requires. Parse errors always failing and file-scope statements being rejected change programs that build today (the parser drops errors after the first declaration except in three cases, `parser.py:171-199`), so they wait for packet P1. Track 1 items (`docs/plan/README.md:331`), which are 8 of the 12 failing baseline tests: reject an `--output` or `--doc-out` path equal to the input (2 tests); never report a stale or failed artifact (2 tests); correct parse diagnostic location (1 test); missing-import location and imported parse and semantic error origins (3 tests). Each with a CLI-level failing test first (human and JSON, line and column). Parse-error strictness changes accepted programs only when a declaration is silently dropped; those are A7-accepted programs whose source Zig never sees, so run the compatibility scan and escalate if any example changes.

**Lane S (safety and typing).**
- No approval needed: `moved_symbols` reset per function (removes false use-after-`del` errors across functions; Lane D first adds the defect row); for-loop update runs approval and implicit-deref logic (`zig.py:2366-2376`, shared with B). Investigate `UnknownType.is_assignable_to` returning true for every target (`a7/types.py:520-522`): record where an unknown type reaches an assignment or argument check and whether any accepted program depends on it; fix as a no-approval item only if no building program changes.
- Exact integer folding: `/` and `%` in Python ints truncating toward zero, fold only when the result fits the node's type (`ast_preprocessor.py:590-649`); folded nodes copy their type entry. Fixes failing baseline test `test_large_integer_folding_preserves_exact_quotient_and_remainder`. Tests extend `test/test_pipeline_native.py:59-97` at i8/u8/i64/u64 boundaries.
- Reject where Zig already rejects the output (no approval): `[n]u8` with unbound `n`; `z := z` without an outer `z` (lower correctly if an outer one exists); string `==` on parameters or other values Zig rejects (folded literal comparisons keep working, `test/test_ast_preprocessor.py:384-385`; local variables holding literals build today and compare pointers, ledger B3, so that case goes to P0b); untyped mutable globals; writes to by-value array parameters. Writes into a `[]T` slice already build and run; the defect is a slice write whose backing array the backend emits as `const` because mutation analysis misses slice writes (`docs/plan/research/memory/edge-case-audit.md:118`), and it is fixed by lowering the backing array as mutable, not by rejecting. Writes to `for` bindings are already rejected by A7 (`name_resolution.py:466-491`, `type_checker.py:851-859`), so no work. Accept `ret 0` from `u32`/`usize` (named defect, SPEC A.2 unambiguous).
- **After P0b approval:** block facts survive exit; loop-body assignments drop facts at loop entry; by-ref argument roots drop facts after calls; reject returned slices of local arrays, double `del` through alias or in a loop, `del` through a `ref` parameter.
- Each new rejection paired with a guarded program that must still compile. GLM security review per group (fact changes, `del` holes, folding and approval identity, returned local slice).

**Lane B (backend, current AST emitter).** New `test/test_zig_backend_runtime.py` (compile, build Debug and ReleaseFast, run, compare to hand-written output):
1. Shadowing: per-scope source→emitted name map covering VAR, CONST, params, for-in and match captures; uses annotated (`ast_preprocessor.py:433-518`, `zig.py:645-646, 1505-1516`).
2. Element order: temp when an array literal reads the assignment target's root (`zig.py:1308-1325, 1897-1901`); `arr = [arr[1], arr[0]]` prints `2 1`. Struct initializers are emitted as typed literals (`zig.py:1870-1895`), which Zig does not give a result location, so `p = Pt{x: p.y, y: p.x}` probably swaps correctly already; probe it first and drop that half if so.
3. `del` and match captures use generated unique names (`zig.py:1221, 1306, 1856, 2390`).
4. One `_zig_ident()` for all declarations and uses; rename collisions with preamble names (`std`, `allocator`, `__a7_*`). Today `test := 3` emits `const test = 3;` but uses emit `@"test"` (citation audit). Fixes failing baseline tests `zig-keyword-local`, `unused-loop-capture`, `shadowed-loop-capture`.
5. `defer x = 1` emits a deferred block (`zig.py:2378-2391`).
6. Signed `/=` and `%=` lower to `@divTrunc`/`@rem` (`zig.py:2356`).
7. Callee from `stdlib_canonical` only (`zig.py:1631-1645`). Miscompile today: a function-pointer field call on a local struct named `math` becomes `@sqrt` and prints `3 4.5` instead of `4.5 4.5` (ledger B14); fixed without approval under the miscompile clause.
8. Defensive: unresolved generic return type raises `CodegenError` instead of emitting `void` (`zig.py:484-486`); the citation audit could not reach this path from the CLI.
9. Quadratic else-gluing replaced by a last-write flag or chunk list (`zig.py:768-814`).

**Lane H (harness), first task H0 before Lane R starts:** `scripts/run_probe.py` compiles a probe and builds and runs it only if its first line is `// probe: run-allowed`; a test proves it refuses `// probe: compile-only` files.

H1 shared `find_examples()` in `scripts/verify_examples_common.py` returning `(name, path)` pairs, used by `build_examples.py`, `project_status.py` and `test/test_examples_e2e.py:18-19` (`example_count()`), discovering `examples/*.a7` (name = stem) and `examples/apps/*/main.a7` (name = `app_<dir>`); the name, not the file stem, is threaded through `ExampleResult`, `BuildResult`, fixture lookup and build paths (`verify_examples_common.py:93-97, 148`, `build_examples.py:173-174, 207`). H2 `--example NAME`. H3 `--update-golden` requires `--example`. H4 `--jobs N` thread pool. H5 ignore `examples/**/*.zig` and `tmp/` in `.gitignore`, `check_no_secrets.py` skip list and pytest collection (after P0). H6 replace `test/test_parser_examples.py:257-318` with a parametrized parse test over every discovered file. H7 two fake apps with `main.a7` get distinct names and helpers are not built as programs. H8 elapsed run time recorded per example, with `--max-runtime-ms` enforced for apps. H9 `test/test_error_stage_matrix.py:52` count derived, not hardcoded. Measure gate time before and after.

**Lane R (capability probe, parallel with F/S/B, after H0).** Each row records the compiler patch id it ran against, and rows touched by later S, B or F patches are re-run. Probes P1–P22 as specified by the examples design: arrays of structs, slice parameters, struct returns, `ret 0`, byte scanning, enum fields, named capacities, push/pop proof idioms, literals and widths, math determinism, stderr ordering, `fall`, two-file imports with shared and duplicate struct names, `using`, `@type_set`, 2-D arrays, open slices, variable divisors, struct copy-out, printing formats, Debug loop timing, function value in struct field. Output `docs/plan/research/examples-capability-probe-<date>.md` with a bug-dependency matrix (bug, reproducer, workaround, examples blocked).

**Lane E (small examples, after probe).** `043_integer_widths`, `044_number_literals`, `045_numeric_casts`, `046_math_functions`, `047_match_fall`, `048_stderr_output`, `049_open_slices`, `050_slice_params`, `051_struct_arrays`, `052_struct_return`, `053_enum_fields`, `054_generic_constraints`, `055_callback_field` (header notes gate G4), `056_fixed_stack_queue`, `057_byte_scanning`, `058_matrix_2d`; fix `025_linked_list.a7` to `usize` with a `NONE` constant and unchanged golden. Each waits on its probe row; skipped rows are listed, not faked.

**Lane D (docs, main tree, last).** Describe current behavior: `SPEC.md:192` (`ref fn() = nil`), `:2021` (remove `.val`), `:1155-1158` broadcast example, `:410-411` vs `:447-448` (probe first), `:698-716` generic examples (probe first), `:788, 817, 822` (`io.println`, `math.sqrt`), `:96-105, 129` actual keyword set and untokenized `?`/`...` marked, `:72-75` current comment behavior "under review in P1", `:40, 2086` "current; planned direction L15-L19"; `docs/plan/README.md:251` (the `é` identifier diagnostic is already correct); `STATUS.md:20-21, 41-44` superseded; `README.md:195` count replaced with a pointer to `scripts/project_status.py`; CHANGELOG entries for user-visible fixes; mirror in `site/public/docs/` and rebuild `llms*.txt` (`cd site && bun run build`).

**Packets drafted this wave** (each GLM-reviewed, then presented): **P1** parser and lexical strictness (unclosed `/*` with `examples/003_comments.a7:28-30` and its test, `#` comments, keyword list incl. `int`/`uint`/`float`/`let`/`not`, `?` and `...`); **P2** source text (ASCII vs UTF-8 for identifiers, strings, chars); **P3** L5 wrapping details (`x: u8 = 255; x += 1` gives 0 in every profile, compound assignment, wrapping lowering, retire `SAFETY_CONTRACT.md:54` and delete the unreachable body of `_prove_integer_overflow` after its early return, `safety.py:636-646`; folding matches runtime); **P5** interim composite rules (`case ok` rejected until G5; untagged-union inactive reads; `pts: [3]Pt` without initializer, which lowers to Zig-rejected `[_]Pt{0} ** 3` while `SPEC.md:201-204` promises zero-initialization: reject with a SPEC amendment, or implement zero-init for any element type; a match case whose name exists in an outer scope becomes an equality test instead of a capture, `name_resolution.py:384-385`, `zig.py:1963-1969`: keep, reject, or require explicit syntax).

**Exit:** all (a) items fixed with tests; gate green against baseline; probe report and small examples landed; P1, P2, P3, P5 presented.

## Wave 2: Approved changes, identity, iteration, full example apps

> Superseded in part (2026-09-17): 2.1 node identity and the type-checker explicit stack in 2.2 moved into Wave 2R above. 2.3 example apps wait for the correctness-first exit.

**2.1 Node identity (serial, all code lanes paused).** `node_id` field on `ASTNode` with `compare=False` (`a7/ast_nodes.py:157-259`), numbered once with a duplicate check, before name resolution in **every** compile mode: the module merge at `compile.py:256-261` runs only in codegen modes (`compile.py:252-253`), so numbering placed there would leave `--mode semantic` unnumbered. Nodes created later by constant folding (`ast_preprocessor.py:141-149, 643-649`) inherit the replaced node's `node_id` and type entry. Re-key `node_types`, `Obligation`, `BackendPlan` (`safety.py:188-222`), `FactMap.by_node` and every `id(...)` lookup in `zig.py`. Invariant test in both `--mode semantic` and compile mode: every expression in the final AST has a type entry and every approval key names a live node, including a program with a folded `2 + 3`. JSON and markdown AST output are unaffected because both formatters serialize allowlisted fields (`formatters/json_formatter.py:94-167`, `markdown_formatter.py:206-234`); a test confirms it.

**2.2 Parallel after 2.1.**
- Lane S: type checker becomes a real explicit stack (`type_checker.py:756-944`, expression visit ~1194), following `name_resolution.py:401-419`. `_nonnegative_vars` and its snapshot and learning logic (`type_checker.py:772-778, 1889-1945`) have no reader (`_expression_is_known_nonnegative` has no callers), so they are deleted rather than converted, after a grep confirms no consumer. Audit `semantic_validator.py` recursive paths (`1224-1225, 1272, 1282, 379`) and convert. Deep-statement tests at recursion limit 100 (depth ≥ 60 with assignments, if/else, while/break, match/fall, defer, nested calls).
- Lane F: implement approved P1 and P2 items.
- Lane B: implement approved P3 (track 3a wrapping lowering and folding); remaining backend items.
- Lane S: implement approved P5 interim rules.
- Present **P4** (G3 rows `docs/plan/README.md:147-156`, M41 checked size arithmetic, L16 float division proof, f32 constant folding, cast D.024 vs D.038, L3/L4 removals) after P3 is decided.

**2.3 Full example apps, fixed data (lane E, up to 2 authors).** Single-file, 300–450 lines, under 200 ms Debug, self-check line (`checks: N/N ok`), identical output in Debug and ReleaseFast, only probe-PASS capabilities:
- `059_expr_evaluator`: tokenizer, shunting-yard, RPN evaluator with explicit stacks; error cases (unbalanced parens, division by zero, underflow). May be blocked on divisor proofs through calls (probe P8, P0b).
- `060_bytecode_vm`: stack VM with jumps, step limit, status results (waits on a proof idiom for data-dependent jump targets or on track 5).
- `061_bank_ledger`: accounts, scripted transactions, integer cents, basis-point interest, reconciliation.
- `062_text_adventure`: rooms, exits, inventory as `[4]bool`, scripted command array; commands dispatch on enums or character scans, never string `==`.
- `063_scheduler_sim`: FCFS, SJF and round-robin with a ring buffer and fixed-point averages.
- Optional `064_int_matrix_kernel`: Bareiss determinant, Park–Miller generator within `i64`.

**Exit:** node identity landed; no recursion in type checker or validator statement paths; approved P1/P2/P3/P5 implemented with docs updated per the post-change checklist; apps 059–063 landed or listed with their blocking defect.

## Wave 3: Typed IR, analysis layer, IR emitter, optimizations

Design (from the IR design report): **structured typed IR plus a derived CFG, no SSA.** Zig has structured control flow, so emission stays direct; dataflow over per-declaration facts is enough at this size.

**3.1 IR model and builder (lane IR).** `a7/ir/ids.py` (`DeclId`, `nid`, `check_id`), `a7/ir/nodes.py` (`@dataclass(eq=False, slots=True)`: `Function`, `Local`, `Let`, `Assign`, `Eval`, `If`, `Loop`, `Match`, `Break`, `Continue`, `Fall`, `Return`, `Defer`, `Del`; places `LocalPlace`, `GlobalPlace`, `FieldPlace`, `IndexPlace`, `DerefPlace`; expressions `Const`, `Load`, `Binary`, `Unary`, `Call` with `FuncRef`/`StdlibRef`/`Indirect`, `Cast`, `AggregateInit`, `New`, `IfExpr`, `MatchExpr`), `a7/ir/build.py` (explicit stack; consumes every type-checker annotation; fails on unknown undeclared node attributes). Tests: builder covers every example; renaming a variable yields the same IR apart from names.

**3.2 Analysis layer.** `a7/ir/cfg.py` (edges normal/true/false/break/continue/fall/return; defers linked onto scope exits; short-circuit split), `dom.py` (Cooper–Harvey–Kennedy, explicit-stack DFS), `dataflow.py` (worklist in reverse postorder, join/leq/widen, widening after 3 header visits, deterministic), `definite_assign.py` (report-only until gate M34), `liveness.py` (replaces name-based `is_used`/`is_mutable` in `ast_preprocessor.py:324-384` and `zig.py:214-273`), `facts.py` (re-hosts `IntegerInterval`, `ValueFact`, `Obligation`, `ProofResult`, `BackendPlan`; join = interval hull, nonzero/non-nil AND, moved OR; strong update for locals; condition refinement incl. negation and `i < xs.len`). **Escape-aware invalidation** (audit A-26): A7 has no address-of operator, but implicit reference arguments (`type_checker.py:1392-1395`, emitted as `&arg` at `zig.py:1661-1664`) take a local's address, and a `ref T` parameter can be stored into a `ref T` field or global (`ReferenceType` uses exact-match assignability, `types.py:43-46, 215-225`). So a call invalidates facts of its by-reference argument roots **and of every local whose reference may have escaped** (passed by reference to any function that can store it; conservatively, any local ever passed by reference), plus facts about derived places (`p.x` after a call taking `p`). `known_length` gets an explicit join and widening rule. Tests use independent oracles: path enumeration on acyclic graphs, the dominator definition on random small graphs. CFG tests cover defer bodies on break, continue, return and fall exits with exit-time facts; labeled breaks out of nested loops (`parser.py:953-997`); match-capture scopes; and the counter idiom `i := 0; while i < xs.len { xs[i]; i += 1 }` staying provable after widening. The soundness suite includes the ref-escape case: store `r` into a `ref` field, clear it through another call, then `10 / x` must reject.

**3.3 Shadow mode and soundness suite (gate M29).** IR fact engine runs beside `SafetyProofPass`; a report lists every "old approves, new rejects" and "old rejects, new approves" case over examples and tests. `test/soundness/*.a7` pairs: each unsafe program rejected, each guarded twin accepted. GLM security review of the engine.

**3.4 Packet P7 (fact-engine switch).** Newly rejected programs (block, loop, call, ref-parameter cases) and newly accepted ones (guarded index `if i < xs.len`), with current vs proposed and the shadow report as compatibility impact. On approval: `BackendPlan` comes from the IR engine, `SafetyProofPass` and the type checker's `_nonnegative_vars` are retired, `docs/SAFETY_CONTRACT.md` and `docs/STATUS.md` updated.

**3.5 IR emitter (strangler).** `a7/backends/zig_ir.py` behind a private switch, emitting per function when `supports(fn)`, falling back to `zig.py` otherwise. Both emitters share, not duplicate: the naming helper; the whole-file feature scan and preamble (`zig.py:127-180`); the `main` to `__a7_user_main` rename (`zig.py:401-402`); nested-function hoisting (`zig.py:412-422`); the unique-name counter (`zig.py:1977-1979`); and the whole-file output normalization (`zig.py:88-101`). `supports(fn)` excludes generics, `main`, and io-call-as-expression cases (`zig.py:2214-2219`) until the IR emitter handles them. A deliberately wrong `supports()` on one example must make the differential harness fail, proving it covers mixed files. `test/test_ir_backend_differential.py` compiles every example and runtime test both ways, builds Debug and ReleaseFast, compares stdout, stderr, exit code and `zig fmt --check`. Emitter uses an explicit task stack; expressions render bottom-up. When all match: IR emitter becomes default; delete `zig.py` statement visitor and preprocessor passes 3–8, and delete `safety.py` only if packet P7 was approved. That deletion restores the iteration rule for the backend.

**3.6 Optimization layer (one per change, each through the differential harness).** Exact typed folding moved onto the IR (wrapping folds per approved P3); unreachable-code removal; unused locals and discards via liveness (drop only pure initializers, never a `new`, since allocation counts are observable under gate M14); compiler-temp elimination for match scrutinees; `fall` lowered to labeled `switch` with `continue :label value` (in Zig since 0.14.0) where each target has a representative value of the operand type, keeping the state machine for range and multi-value cases; parenthesization from Zig's operator precedence table, not A7's (`ast_nodes.py:609-641`); `.?.*` narrowing after proof (last). Float folding: keep f64, write a test exposing f32 behavior, decision under G1. No general copy propagation (LLVM does it).

**3.7 Packet P8 (print buffering).** One buffered writer per stream, flushed at exit, before panic and before each `eprintln`; shows ordering and crash-loss impact. Implement on approval; replace text-matching tests (`test/test_codegen_zig.py:287-291, 357-360`) with behavior tests.

**3.8 Parallel in this wave.** P4 implementation (track 3b) on the IR once approved; generic specialization and call-chain propagation completed as bug fixes (`docs/STATUS.md:24, 35`), before the multi-file app; multi-file app `examples/apps/calc_vm/{main.a7, lexer.a7, compiler.a7, vm.a7}` after H1 and probe P13 (types in `main.a7` or unique names); fix cross-file struct and enum name prefixing (only functions get `module_emit_prefix`, `compile.py:613-618`) and type references such as `mod.Point` in annotations, which nothing resolves (`_annotate_file_module_calls` at `compile.py:586-592` handles calls only), as bugs. Draft and present **P9 minimal I/O** (stdin line read into a caller buffer returning a count, command-line args, whole-file read into a buffer; failure as a status value until 7b) and **P10 G5** (payload matching, `?T`, Option/Result, error propagation, string equality).

**Exit:** IR emitter is default; `safety.py` removed after P7 approval; differential harness green; optimizations landed with evidence; deep-nesting full-pipeline test passes at recursion limit 100.

## Wave 4: Proofs, errors, I/O, interactive apps, memory groundwork

- **Track 5 proof repair (lane S on the IR):** guarded indexing, second write through scalar `ref`, precise use-after-`del` per path, block-form `defer { ...; del b }`, indexing `ref [N]T` and slice/string parameters. Each with rejected/accepted pairs.
- **7a** (if P10 approved): `?T` tokenized and typed, tagged-union payload matching, exhaustiveness, `case ok` real semantics. **7b:** Result type and propagation. Docs checklist per change.
- **Minimal I/O** (if P9 approved): lane L adds `std/io` read functions and `std/process` args in `a7/stdlib/`. Lane H changes the run invocation in `verify_examples_common.py:124-131` and `build_examples.py:125-132` to pass a stdin file handle and argv per example from `test/fixtures/stdin/<name>.in` and `test/fixtures/args/<name>.args`, and defines timeout behavior for prompt loops. Security review by GLM (input handling, buffer bounds).
- **Interactive apps:** `065_expr_repl`, `066_vm_runner` (program from file), `067_ledger_cli` (transactions from stdin, dispatch on enums or character scans), `068_adventure_interactive`; same self-check discipline with fixed stdin fixtures.
- **P11 L19 metric (gate M48)** before any memory gate; **P-M50 monomorphization strategy** (required by memory layers 3–8); **P-M25 native declaration surface** (`docs/plan/memory.md:623, 662` require it open in Phase A).
- **Memory phase A:** hand-trace the 31-program falsifying corpus (`docs/plan/memory.md:681-713`) and both training steps (`docs/plan/memory.md:662`); fix M14 margins before baselines, then record baselines; settle the §9 open items (`docs/plan/memory.md:737-746`): compile-time cost budgets, Zig version dependence, deep equality and hashing of owning values, a growable text type, allocator thread safety, task and channel bounds.
- **P-parsed-only:** variadics, intrinsics other than `@type_set`, destructuring, multiple return values (`docs/STATUS.md:36-37`): implement or remove, each with examples.

**Exit:** track 5 done; 7a/7b and I/O landed if approved; interactive apps landed; L19 metric and M50 decided; phase A corpus and margins recorded.

## Wave 5: Memory core (track 6a) and collections (8a)

Presented in batches, each GLM-reviewed and audited (memory gates M1–M51, disagreements G4+M6, M2, M11, M33 shown with both positions):
- **P12 model:** M1, M3, M4, M5, M8 memory report, M9 vocabulary, M13, M30, M31, M32, M33, M34, M38 block and branch extents, M39 index and key validity, M40 determinism, M42 id width, M45 arena membership, M49 storage-owning unions, M51, with the `docs/plan/memory.md:346-364` rows. Disposition lines for Kimi M-8 ("bindings copy, places change in place" as its own gate) and M-6 (M32 and tokenizer views) from `docs/plan/research/memory/review/README.md:198`.
- **P13 failure:** M2, M14, M16 (M16 last).
- **P14 function values:** G4 with M6.
- **P15 reuse and planning:** static in-place reuse per `docs/plan/research/memory/reuse-languages.md` (FP² `fbip`-style definition check; call-site uniqueness choice: uniqueness typing with duplicated functions, or compiler-inserted copies, or rejection; no general lambdas implication for M6); M44 planner bounds; M47 stale bytes in reused storage.
- **P16 resources:** M7 move-only resources with implicit release and fallible close (needed before 8b files).

Implementation after approvals, in phase order on the IR:
- **Phase B:** storage identities, effect summaries over the acyclic call graph, iterative release generation.
- **Phase C1 additive:** `List`, `Map`, `Table(T)`, `Id(T)` with generations, owning `string`, optionals (8a, 7a).
- **Phase C1′ interim lowering** of existing `new`/`ref`, running during C1 as `docs/plan/memory.md:665` specifies.
- **Phase D placement:** extent inference (call, iteration, task, step, session, process), arenas and pools, block and branch extents (M38), release at removal.
- **Phase E reuse and planning:** copy removal, in-place update under proven uniqueness, buffer planning; allocation counts and peak memory within M14 margins.
- **Phase C2 subtractive:** remove `new`, `del`, `nil`, stored/returned `ref` per approved rows; migrate every affected example (`011_memory`, `013_pointers`, `017_methods`, `019_literals`, `038`, `040–042` and any others found) with before/after goldens.
- Corpus programs for B, C1, D run as tests; 17 rejection classes each have a rejected/accepted pair.

**Exit:** approved memory model implemented through C2; corpus B/C1/D programs pass; examples migrated; `--memory-report` exists if M8 approved.

## Wave 6: Concurrency, native boundary, CPU AI, stdlib, integration

- **Track 9 concurrency** (after G7 packet with M10, M26–M28, M36, M37): structured tasks, cancel-then-join, channels with explicit close, read-only sharing with children, globals immutable after start; corpus 10, 23, 29 with ThreadSanitizer builds.
- **Track 10 native boundary** (M25 decided in Wave 4; after M12 and M43 packets): `extern` declarations and descriptors carrying layout, ownership and teardown, generated glue with size/alignment/offset assertions (pattern from the Roc report), pinned libraries; corpus 12.
- **Track 11 CPU AI** (after P17 G1 remainder, G8, M11, M17–M24 packets), in the sequence from `docs/plan/README.md:400-413`: tensor semantics; reference kernels incl. `f16`/`bf16`; eager reverse tape; BLAS/oneDNN bridge; mixed precision; training state and checkpoints (M24, M46); classifier then decoder transformer; packaged inference. Corpus 8, 9, 16–22, 30, 31.
- **Track 8b stdlib:** files, paths, time, random, process, recoverable I/O on 7b.
- **Track 6b:** phase F qualification (corpus F set, GLM memory-safety review) and phase G layout (structure-of-arrays where legal) plus memory report.
- **G6 remainder packet:** modules (selected imports, `using import`, visibility, cycles) and CLI (`check`, `build`, `run`, `test`, `fmt`, `doctor`, `--version`).
- **Full software examples:** L10 acceptance programs (small classifier; decoder transformer with checkpoint recovery), a concurrent worker pool app, a native-kernel app.

**Exit:** tracks 9, 10, 11, 8b, 6b complete with corpus evidence; L10 acceptance programs pass.

## Wave 7: Release

- **G9 packet:** release profile and platforms.
- **M16:** safety contract rewrite presented last, after §6 and the rejection list are final.
- **Track 13:** CHANGELOG, README, SPEC, STATUS, `site/public/docs/`, rebuilt `llms*.txt`; release archives named `a7-example-artifacts-<os>-<arch>-zig0.16.0-<profile>.tar.gz`; `uv build` and clean-venv wheel install; full gate green.
- Final GLM security review (L12) and three independent doc audit rounds.

## Decision calendar

| Packet | Content | Presented | Blocks |
| --- | --- | --- | --- |
| P0 | Triage test, L20 reading, L17 vs L19, cycle split, harness gate changes, `tmp/` ignore, CLAUDE.md/AGENTS.md corrections | W0 | Wave 1 |
| P0b | Fail-closed rejections of unsafe programs that build today (block, loop and call facts; returned local slice; double `del`; `del` through `ref`) | W0 | Those Lane S items |
| P1 | Parser and lexical strictness | W1 | F lane W2 |
| P2 | Source text (G6 text) | W1 | F lane W2 |
| P3 | L5 wrapping details | W1 | Track 3a, P4 |
| P5 | Interim composite rules | W1 | S lane W2 |
| P6 | Escalations from compatibility scans | as needed | the escalated fix |
| P4 | G3 numerics, M41, L16 float division, f32 folding, cast, L3/L4 | W2 | Track 3b |
| P7 | Fact-engine switch | W3 | Removing `safety.py` |
| P8 | Print buffering | W3 | Backend buffering |
| P9 | Minimal I/O | W3 | Interactive apps |
| P10 | G5 errors and matching | W3 | 7a, 7b, C1 |
| P11 | L19 metric (M48) | W4 | All memory packets |
| P-M50 | Monomorphization | W4 | Memory layers 3–8 |
| P-M25 | Native declaration surface | W4 | Phase A exit, M12, phase F, AI workloads |
| P-parsed | Variadics, intrinsics, destructuring, multiple returns | W4 | Docs accuracy |
| P12–P16 | Memory model, failure, function values, reuse and planning, resources | W5 | Track 6a, 8b |
| G7, M12/M43, G8, P17 G1 remainder | Concurrency, native, AI | W6 | Tracks 9, 10, 11 |
| G6 rest | Modules and CLI | W6 | Tooling |
| M15 | Syntax simplification after the memory model | W6 | Deferred past release unless the user decides otherwise |
| G9, M16 | Release, safety contract | W7 | Release |

If a packet is declined, the dependent steps are replaced by a documented alternative in the next wave's task cards; nothing proceeds on an assumed approval.

## Verification

- **Per task:** implementer acceptance commands; independent verifier report with a counterexample; GLM second opinion where listed; controller confirms at least two claims itself.
- **Per patch applied to the main tree:** `./run_all_tests.sh` in the background, compared to the Wave 0 baseline; revert on regression.
- **Compiler correctness:** `test/test_zig_backend_runtime.py` (Debug and ReleaseFast, hand-derived output); `test/test_ir_backend_differential.py` (old vs IR emitter, every example); folded-vs-runtime tests at type boundaries; `test/soundness/` rejected/accepted pairs; IR analysis oracles; deep-nesting tests at recursion limit 100.
- **Examples:** golden identical in Debug and ReleaseFast; `zig fmt --check` clean; under 200 ms Debug (apps) and 2 s timeout; self-check lines; expected output written before the first run; perturbed-input check by the verifier.
- **Safety of process:** compile-only probe refusal test; no memory-unsafe program executed; GLM L12 reviews for every security-relevant group.
- **Docs:** `scripts/check_docs_style.py`, `scripts/check_no_secrets.py`, link and anchor sweep (`tmp/sweep.py` pattern using `github-slugger` rules), evidence hash manifest `tmp/evidence-manifest.txt`, audit rounds until zero defects or 3 rounds.
- **Baseline:** `docs/audits/2026-09-16/baseline.md` records 11 of 12 checks passing and the 12 failing pytest tests; each is owned by a Wave 1 lane and must pass by the Wave 1 exit.
- **End of each wave:** ledger promoted to `docs/audits/<date>/`, wave exit criteria checked by an independent auditor, status reported to the user.

## Critical files

- Compiler: `a7/compile.py`, `a7/tokens.py`, `a7/parser.py`, `a7/ast_nodes.py`, `a7/passes/type_checker.py`, `a7/passes/semantic_validator.py`, `a7/safety.py`, `a7/ast_preprocessor.py`, `a7/backends/zig.py`, new `a7/ir/*`, new `a7/backends/zig_ir.py`, `a7/stdlib/*`
- Reusable patterns: explicit stack with actions `a7/passes/name_resolution.py:401-419`; post-order rewrite `a7/ast_preprocessor.py:114-169`; bottom-up rendering `a7/backends/zig.py:1524-1543`; fact domain `a7/safety.py:97-222`; frozen types `a7/types.py:30-545`; Debug/ReleaseFast agreement test `test/test_pipeline_native.py:59-97`
- Harness: `scripts/verify_examples_common.py`, `scripts/build_examples.py`, `scripts/project_status.py`, `scripts/verify_error_stages.py`, `scripts/check_no_secrets.py`, `run_all_tests.sh`, `test/test_parser_examples.py`, `test/test_error_stage_matrix.py`
- Plan and docs: `docs/plan/README.md`, `docs/plan/decisions.md`, `docs/plan/memory.md`, `docs/SPEC.md`, `docs/STATUS.md`, `docs/SAFETY_CONTRACT.md`, `docs/CHANGELOG.md`, `README.md`, `site/public/docs/`


## Current reconciliation, 2026-09-20

The [delivery roadmap](delivery-roadmap.md) preserves the full V1 boundary and
controls current work order. Earlier counts and progress entries above remain
historical evidence. The repaired working tree, not HEAD alone, is the baseline.
The [fresh baseline gate](../audits/2026-09-20-v1-foundations/baseline-gate.log)
passed 9/9 checks with 2,087 tests and 43 examples. Its source manifest includes
tracked changes and untracked files.

The [critical/high inventory](../audits/2026-09-20-v1-foundations/critical-high-inventory.md)
accounts for 49 IDs from the six original compiler reports. Fifteen have explicit
historical batch-closure mappings, two have explicit trigger-level closure, and
32 need revalidation, fuller evidence or decisions. This is not a count of all
later findings. The inventory preserves the conflicting uses of SAF-11.
Passing the aggregate gate does not close an original finding by itself.

NOREC-0b now models the requested dictionary dispatch and lambda calls, retains
untyped delegation as unresolved evidence, checks generated dataclass methods in
the scanner self-scan, and compares normal and conservative compiler scans.
Three helper conversions replace recursion in safety integer-literal extraction,
backend mutation-base extraction and symbol-table dumping. The scanner's known
recursive groups shrink from 31 to 28. Deep helper tests use recursion limit 100;
they do not qualify deep programs through the entire pipeline. Scanner dynamic
Python limitations remain documented in `test/norec_scan.py`.

See the [batch evidence](../audits/2026-09-20-v1-foundations/README.md) for final
verification and independent review. No language contract changed in this batch.
The memory contract, P-MOD compatibility packet and other grouped packets remain
unapproved. Typed IR remains behind L23's correctness-first exit. Memory research
continues through [reconciled workloads and measurement proposals](research/memory/delivery-reconciliation.md),
without adopting the proposed ordinary/advanced distinction.
