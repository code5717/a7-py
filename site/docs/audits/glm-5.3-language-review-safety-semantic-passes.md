<task id="ses_f44deb3e7ffe0tdaORNtzcPbOj" state="completed">
<task_result>
# A7 Semantic Enforcement Review — GLM-5.3, 2026-09-19 (read-only)

**Bottom line:** every prior finding I was asked to verify is still present in code, the L32 defer-havoc fix exists and is tested, and I found four new accepted-unsafe holes (two in defer/del interaction, one in the recursion ban, one alias false-positive) plus several over-rejection and bookkeeping defects.

## 1. Prior findings — verified status

| # | Finding | Status | Evidence |
|---|---------|--------|----------|
| P1 | `UNION_FIELD` zero producers | **Still present** | Only the enum member at `a7/safety.py:221`; no constructor anywhere in `a7/` (grep) |
| P2 | `_prove_integer_overflow` dead body | **Still present** | Unconditional `return` at `a7/safety.py:801`; dead body 802-811; call site 575-576 |
| P3 | SAF-1: `REF_NON_NIL` defeated at call sites | **Still present** | `ref T` parses to `TYPE_POINTER` (`a7/parser.py:772-780`), so `_fact_from_type_node` marks ref params `non_nil=True` inside the callee (`a7/safety.py:647-648`) while the CALL case (`a7/safety.py:609-612`) creates no obligation for ref arguments. Snippet: `fn g(b: ref Box) { b.value = 1 }` + `b := maybe_nil(); g(b)` — accepted, nil deref at runtime. Fix owned by P0b.10 (`docs/plan/fix-program/backend-fix-plan.md:292`), not landed |
| P4 | S2: loop visited once, no fixed point | **Still present** | `a7/safety.py:475-493` (while/for: one body visit, then `restore_symbols`). Concrete: `i := 0; while i < 3 { i += 1 }; a[i]` — after-loop fact restored to exact(0), `a[i]` proven, runtime i=3 → OOB |
| P5 | S3/MTH-2: call invalidates no facts | **Still present** | `a7/safety.py:609-612`; `x := 4; if x != 0 { zero_it(x); 100 / x }` still proves the divisor |
| P6 | MTH-16: struct fields never facts | **Still present** | `_facts_from_condition` only reads a plain identifier left side (`a7/safety.py:846-849`); `if b.value != 0 { 100 / b.value }` over-rejected |
| P7 | L32: defer-in-loop stale proof fix | **Fix present and tested** | Havoc drop at `a7/safety.py:526-536` via `_deferred_assigned_symbols` (375-426), kinds gate at 75-80; tests `test/test_safety_precursors.py:84-190` cover plain/compound/match/loop forms |
| P8 | SAF-2: any `.ptr` assumed non-nil | Still present | `a7/safety.py:599-600` — unconditional `non_nil=True` for a field named `ptr` |
| P9 | SAF-5: `a / b` nonzero rule | Still present | `a7/safety.py:670-671` and 682-683. New concrete repro (works because params get no interval, SAF-30, `a7/safety.py:644-649`): `fn f(x: i32, y: i32) { if x != 0 { if y != 0 { z := x / y; w := 100 / z } } }` with x=1, y=2 → z=0 → accepted division by zero |
| P10 | SAF-26: un-braced else facts | Still present | `a7/safety.py:473-474` visits `else_stmt` with no snapshot; `x := 0; if c { } else x = 5; 100 / x` — fact exact(5) persists, runtime DBD when c |
| P11 | Missing join at if/match/block merges | Still present (SA packet not landed) | Block exit restores entry facts (`a7/safety.py:431-436`), if restores pre-if facts (465-474), match cases visited sequentially with no isolation (508-514). `x := 4; if c { x = 0 }; 100 / x` accepted → runtime DBD when c |
| P12 | Recursion: direct/mutual/trampoline | Implemented, verified | Top-level graph + Tarjan SCC + cycle path at `a7/passes/semantic_validator.py:501-637`; higher-order/trampoline edges at 829-876; alias map at 1163-1200 |
| P13 | Unreachable reporting | Implemented for ret/break/continue/fall/if-both-branches/match-all-cases | `semantic_validator.py:1258-1337`. Gap: `while true { … }` is never a terminator (1292-1337 returns False for loops) — code after it is unreachable but unreported; also `_returns_on_all_paths` (1345-1396) ignores loops → conservative |
| P14 | LNG-10 exhaustiveness bool/enum only | Still open at both layers | `semantic_validator.py:1398-1432` and `a7/passes/type_checker.py:2707-2737`, `_match_full_coverage_reason` 2456-2471 — no diagnostics for int/range/string/char scrutinees without catch-all |
| P15 | PIP-4/PIP-5 scope desync; io/math hijack residual | Still present, mechanism confirmed | Type checker pairs scopes positionally (`type_checker.py:142-157`) but `visit_if_stmt` (911-924) never enters the `if_then`/`if_else` scopes that `name_resolution.py:428-444` creates for un-braced branches; and match *expressions* consume `match_case` pairing slots (`type_checker.py:2049`) that name resolution never created (it only walks statements, `name_resolution.py:496-514`). Matches the documented residual (`docs/plan/audit/open-items.md:215`), owned by NR-02 |
| P16 | L26 duplicate import | Partially enforced, not here | `name_resolution.py:122,130,137` ignore the `add_alias`/`define`/`add_named_import` failure returns; no `DUPLICATE_IMPORT` error type exists (`a7/errors.py:87-90` only has CIRCULAR/NAME_CONFLICT/UNSUPPORTED). Same-path-two-aliases accepted per `docs/audits/2026-09-18/visibility-modules.md:606` |
| P17 | Output/write protections | Present | `a7/compile.py:395-401` plus conflict check incl. `samefile`/resolution at `compile.py:528-540` |

## 2. New confirmed defects

**N1 — CRITICAL — braced defer discards the move marker; use-after-del accepted.**
`a7/safety.py:456-458` — the deferred-statement visit (523-525) restores `facts` but not `moved_symbols`, and the ASSIGNMENT case executes `moved_symbols.discard(target)`.
```a7
fn main() {
    b := new Box
    if b == nil { ret }
    b.value = 1
    del b
    defer { b = new Box }   // block form → BLOCK ∈ DEFER_HAVOC_EXCLUDED_KINDS
    b.value = 2             // executes BEFORE the defer; b is freed
}
```
Expected: use-after-del error. Actual: accepted (`b` no longer in `moved_symbols`; non-nil fact restored). Note the asymmetry: the *un-braced* `defer b = new Box` is havoc-dropped (ASSIGNMENT ∉ excluded kinds) and correctly over-rejects — only the braced form is unsound.

**N2 — HIGH — un-braced `defer del b` in a loop; use-after-del on later iterations accepted.**
`a7/safety.py:517-518` — a deferred `del` only visits the expression (no `_mark_deleted`, no havoc; `DEL` is in `DEFER_HAVOC_EXCLUDED_KINDS`, 75-80).
```a7
fn main() {
    b := new Box
    if b == nil { ret }
    while cond {
        defer del b
        b.value += 1        // iteration 2 derefs freed memory
    }
}
```
Expected: rejected (or havoc-dropped). Actual: accepted; the deferred `del` runs at each iteration's block exit. Mirror over-rejection: the *braced* `defer { del b }` does mark moved (539-541 via the BLOCK visit) and never restores the set, so safe uses *before* the defer are then wrongly rejected.

**N3 — HIGH (caveated) — nested functions are entirely outside the recursion ban.**
`_validate_no_recursion` builds its graph from `program.declarations` only (`semantic_validator.py:501-507`); `_collect_expression_calls` skips FUNCTION subtrees (822-823) and the statement scheduler treats nested functions as shadow-only (702-707). `RECURSION_NOT_ALLOWED` is produced nowhere else (grep over `a7/`). `fn main() { fn inner() { inner() } inner() }` passes A7 validation; the preprocessor hoists nested functions (runs after the validator, `a7/compile.py:341→413`) and Zig compiles recursion → runtime stack overflow. Caveat: whether nested functions are a supported feature is undecided (`docs/plan/fix-program/backend-fix-plan.md:517`), so this is a confirmed enforcement gap with a design question attached.

**N4 — MEDIUM — alias collection ignores parameter shadowing → false recursion error.**
`_collect_function_aliases` (`semantic_validator.py:1163-1200`) records `h := g` whenever `g` names a *top-level* function, without checking whether `g` is shadowed by a parameter/local in scope; `_direct_callee_name` (895-910) resolves aliases *before* the shadowed set.
```a7
fn g(cb: fn(i32)) { cb(1) }        // top-level g calls its param
fn other(n: i32) { }
fn caller(g: fn(i32)) {            // param 'g' shadows top-level g
    h := g                          // binds the PARAM, but aliases[h] = top-level g
    h(5)
}
fn main() { g(other) }              // real edges: g→param, main→g
```
Edges g→caller (real) + caller→g (false alias edge) → SCC → false `recursion_not_allowed`. The docstring (1166-1169) claims conservatism for *ambiguous* aliases; a shadowed binding is not ambiguous, it is mis-analyzed. Same flow-insensitivity also misedges `h := g; h := cb; h()`.

**N5 — LOW — defer havoc fires outside loops.** `a7/safety.py:526-536` drops facts at every defer site; the comment says "inside a loop". `defer x -= 5; y := 10 / x` at function top (defer runs at scope exit, after `y`) is safe but rejected.

**N6 — LOW (over-rejection) — early-exit learning recognizes only a bare trailing `ret`.** `_learn_after_stmt`/`_always_returns` (`a7/safety.py:828-841`) ignore `break`/`continue` and if/else-both-return tails: `while c { if b == nil { continue } b.value = 1 }` is rejected despite being safe.

**N7 — MEDIUM — defer scope bookkeeping is dead and wrong.** `semantic_validator.py:159-162` reads `symbols.get_scope_depth()` while the symbol table sits at global depth (name resolution and type checking have exited their scopes), so every defer registers at depth 0 and the first block exit pops all of them (`semantic_context.py:259-271`). Nothing consumes the defer stack (grep: no `get_defers_at_depth` callers), so defer scoping is unenforced — only `DEFER_OUTSIDE_FUNCTION` is checked.

**N8 — LOW — unreachable/return analysis asymmetries.** `_statement_exits_current_block` treats a match-else as exiting if *any* statement exits (1332-1333) while `_returns_on_all_paths` requires the *last* one (1384-1388); `validate_break` inside it (1300-1304) also appends to the dead string error list (`semantic_context.py:279-321`), a second, unused error channel.

**N9 — LOW — mutation analysis misses slice-assignment targets.** `_get_root_identifier` (`a7/ast_preprocessor.py:315-329`) handles INDEX/FIELD_ACCESS/DEREF but not SLICE, while `a7/safety.py:84-93` documents `s[0:1] = …` as a valid assignment-target form. If the parser accepts slice targets, `s` is not marked mutable → Zig const-assignment build failure. I did not confirm parser acceptance (see §4).

**N10 — LOW — duplicate-import detection unenforced at the name-resolution layer** (see P16): `name_resolution.py:130` also drops the `symbols.define` failure for a repeated alias import, so the second identical `io :: import` produces no diagnostic there.

Not defects: the backend's own `_declare_var_in_scope`/`_rename_map` (`a7/backends/zig.py:302-336`) compensates for preprocessor Pass 7 not declaring for-in iterators/match captures (`ast_preprocessor.py:500-513`) — duplication, not a hole. `const_eval.py` is sound and Zig-consistent: truncating `/`/`%` (77-82), f64-only floats with inf/NaN folding rationale (docstring 15-19), signed zero preserved through `str(-0.0)`, overflow/shift-width gating (67-74, 149-152).

## 3. Design questions
- Should the braced/un-braced defer forms differ in both fact havoc *and* move tracking (N1/N2 show each form failing in the opposite direction)? Unifying them under one semantic would fix both.
- Is nested-function recursion in scope for the ban (N3), pending the nested-function feature decision?
- Is alias-based edge creation intended to override provable shadowing (N4), or should the shadowed set be consulted before recording an alias?

## 4. What I read and could not verify
Read in full: the six target files; plus `a7/const_eval.py`, `a7/passes/type_checker.py` (scope pairing, if/match/for visitors, field access, exhaustiveness, `_nonnegative_vars`), `a7/parser.py:760-800`, `a7/backends/zig.py` (scope/rename machinery, for-in emitters), `a7/compile.py` excerpts, `examples/011_memory.a7`, `test/test_safety_precursors.py` excerpts, and the plan/audit docs cited above.
Not verified: any runtime or build behavior (read-only mandate — all "accepted/runtime crashes" claims are static inference from the proof logic); parser acceptance of slice-assignment targets (N9); exhaustive absence of other `RECURSION_NOT_ALLOWED` producers beyond grep and the two statement walkers; the greedy `_find_recursion_path` (593-636) has no counterexample but I offer no completeness proof; SAF-11 (interval clamping) was confirmed only structurally — no clamping code exists — I did not construct a wrong-proof repro for it.
</task_result>
</task>