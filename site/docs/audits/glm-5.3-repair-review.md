All verification complete. Final report follows.

---

# Focused Repair Review — GLM-5.3, Z.AI Coding Plan, 2026-09-19 (second run)

**Tree reviewed:** `701c679` + 149 dirty paths (was 134 pre-repair). **The tree changed during this review**: `d_loop_defer_del` rejected with "Reference not proven non-nil" at 22:0x and with "Use after move or delete" on re-run; `a7/` shows 1,427 insertions across 13 files. All conclusions below are from a **full corpus re-run against the final tree** (`/tmp/a7-glm53-repair-review/out/final-a7-rerun.txt`, 69 A7 compiles + 24 Zig 0.16.0 builds/runs). The controller's reconciliation of my prior overclaims (hash-based state check, test-percentage strength, nested-recursion scope, ReleaseFast inference, NEW labels) is accepted; nothing in it changes a reproduced trigger.

## 1. Verdict

The repairs are real, targeted, and verified end-to-end at CLI and native level in both profiles where tested. All six accepted-crashing programs from my audit now reject exit 6 with correct, operation-specific diagnostics; the parser fail-closes instead of silently deleting `main`; L5 wrapping is implemented and native-correct (`255 + 1 → 0`, `-128 - 1 → 127`, literal `2147483647 + 1 → -2147483648`); the A7-accepts/Zig-rejects family I reproduced is closed except one case (match exhaustiveness, below). The new `test_audit_*.py` files are genuine observable regressions, and the cast matrix now checks an independent hand-authored policy. One release-relevant hole remains in the repaired trigger families' periphery, plus the declared retained limits. This pass does not make the safety analysis globally sound — joins/havoc are now enforced on the paths tested, not proven complete.

## 2. Repair verification (all evidence from this run)

| Finding | Result | Evidence (case → stages) |
|---|---|---|
| Loop havoc (S2) | **Fixed** | `d_loop_no_fixedpoint` → exit 6 "Index not proven in bounds"; native OOB panic gone |
| Call invalidation (S3/MTH-2) | **Fixed** | `d_call_invalidates` → exit 6 "Divisor not proven non-zero"; control `d_guard_div_ok` still prints `25 done` |
| Join gap (SAF-11) | **Fixed** | `d_join_gap` → exit 6 "Divisor not proven non-zero"; block/`if true`/defer variants also pinned in `test_audit_safety_repairs.py:43-52` |
| Defer moved-state (braced) | **Fixed** | `d_del_braced_defer` → exit 6 "Use after move or delete … 'b'" (was: SEGFAULT) |
| Defer `del` in loop | **Fixed** | `d_loop_defer_del` → exit 6 "Use after move or delete … 'b'" on final tree (message refined mid-review; earlier same run showed non-nil rejection — both safe directions) |
| Ref-arg nil obligation (SAF-1) | **Fixed** | `d_ref_nil_call` → exit 6 "Reference **argument** must be proven non-nil" (was: null-unwrap panic) |
| Parser recovery (PRD-33) | **Fixed** | `b_multi_decl` (`x, y := 10, 20`) → exit 5 "Expected expression [4:6]"; emitted-Zig deletion gone. `b_recovery_drop` → exit 5 with located message |
| Malformed numbers | **Fixed** | `1_` → exit 4 "Invalid numeric literal '1_' [2:10]" (was exit 8 internal) |
| `...` diagnostic | **Fixed** | exit 4 "The '...' operator is unsupported; use '..'" (was f64-index confusion) |
| Unused nested recursion | **Fixed** | `n_unused_nested_rec` → exit 6 "Recursion is not allowed: Cycle: inner -> inner" (controller's reconciliation case, now enforced) |
| Wrapping +,-,* (L5) | **Fixed, native** | `l5_wrap_test` prints `0`; `test_audit_backend_repairs.py:37-49` pins `0 127 0 0 -2147483648` in Debug **and** ReleaseFast; emitted `x +%= 1` |
| Signed compound `/=` `%=` | **Fixed, native** | `c_compound_div_signed` prints `3`; test pins `-3 -1.5 4` both profiles |
| Identifier quoting | **Fixed, native** | fn named `test` builds and prints "in test"; param-shadowing `caller(test: fn(i32))` also builds (F29 closed) |
| Escaped braces | **Fixed, native** | `{{}}` → prints `{}`; `"{ }"` accepted → prints `{ }`; nested `{{{{{}}}}} {left}` pinned in tests; arg-count form still correctly rejected |
| String arrays | **Fixed, native** | `a: [2]string` builds; prints `[][]` in test |
| Generic wrapped fields | **Fixed** | `Box($T) :: struct { items: []$T }` exit 0, builds; test also pins `[2]$T` fields |
| Contextual literals | **Fixed, native** | `f(200)`→`u8` param, `ret 200`, if-expr `1`/`i64` unify; native run pins `301 200 255 1` |
| Wider-type arithmetic | **Fixed** | `c := a + b` (i8+i64) now emits `const c: i64 = (a +% b)`; explicit `c: i8 = a + b` rejected "expected 'i8', got 'i64'"; mixed-sign runtime comparison builds |
| Invalid unary/shift | **Fixed** | `-u` → "Cannot negate unsigned"; `<< -1` and `>> 8` (over-width) → "Shift count must be non-negative and …" |
| Struct literal checks | **Fixed** | missing fields ("Missing struct fields: count"), unknown field, duplicate field all rejected |
| `math.abs` signed | **Fixed beyond stated limit** | emitted `@as(i32, @intCast(@abs(x)))`; `math.abs(x) - 10` builds and prints `-5` (retained: `abs(MIN)` intCast) |
| Root `main` signature | **Fixed** | `main :: fn() i32` and `main :: fn(x: i32)` → exit 6 "entry point main must have no parameters and no return value"; no-`main` library compiles pinned as intended (`test_audit_type_boundaries.py:89-91`) |
| Import cycle | **Fixed** | `a.a7 ↔ b.a7` → exit 6 "Circular dependency detected: ./a -> ./b -> ./a" |
| JSON match-else serialization | **Verified working** | compile/ast/semantic modes with match+else all exit 0 with valid JSON (`n_json_match.*`) |
| Const/int array bound alias | **Landed and verified** | `N :: 3; arr: [N]i32; arr[0]` exit 0, builds; chained `Alias :: N` + `buffer[2]` pinned natively at `test_audit_type_boundaries.py:51-79` (this is the fix that landed mid-review; my first-run `g_const_arr_size` result predates part of it and was re-confirmed after) |
| Guarded param indexing (LNG-04) | **Fixed, native** | `if i < 4 { ret a[i] }` with `i: usize` param → exit 0, prints `3` |
| Cast-divisor guard (LNG-12) | **Fixed** | `if c != 0 { 100 / cast(i32, c) }` with param `c` → exit 0 (nonzero fact survives cast) |
| Multi-line array literals | **Fixed** | `b_multiline_array` exit 0 (bonus repair, was F11) |
| `math.sqrt` as value | **Fixed** | exit 6 "Standard-library operations must be called directly" (was: Zig undeclared-identifier) |

Examples: the three guard insertions (026 `top` bounds, 030 `guess == 0.0`, 032 `d <= 0` plus `d <= n` bound) are source-only hardening; goldens untouched by the diff. I did not rerun the 43-example e2e (controller's 43/43 native evidence accepted; gate rerun is the controller's job).

## 3. Test-quality assessment

- `test_audit_safety_repairs.py` (79 lines): 9 parametrized rejections asserting exit 6 + semantic category + message fragment + **no output file written**; 3 stale-divisor scope-exit variants including the `if true` constant-fold trap; 1 dual-profile positive pinning exact stdout and **empty stderr**. Observable, hand-derived, no mocks. Genuine.
- `test_audit_backend_repairs.py` (57): 7 programs × Debug/ReleaseFast with hand-derived outputs covering every backend repair including literal-overflow wrap. Genuine.
- `test_audit_type_boundaries.py` (99): rejection fragments, out-of-range literals for args **and** returns, main-signature, library-mode pin, cycle diagnostic, and one native dual-agreement run pinning `301 200 255 1` / `{ } {}`. Genuine.
- `test_cast_safety_matrix.py`: `NO_PROOF_POLICY` is now a hand-authored 15×15 table with an explicit instruction not to derive expectations from the classifier (`test/test_cast_safety_matrix.py:73-76`); 595 tests pass in 0.26s. This removes the specific self-comparison tautology I flagged. Executed: 43 + 595 passed.

Regression check for over-rejection: the safe controls (`d_guard_div_ok` `25 done`, `g_guard_index` → `3`, `g_cast_divisor2/3`, `z_smoke`, float remainder `-1.5 -1.5`) all still compile and run correctly — the repairs did not break the proven-safe paths I tested.

## 4. Remaining blockers / unrepaired (in or adjacent to repaired families)

1. **[M] Non-enum match without `else` still passes A7 and fails Zig** — `g_match_no_else` (`match x: i32 { case 1: … }`, no else): A7 exit 0 → Zig "switch must handle all possibilities". Not in the repaired list nor the declared retained limits. This is the last A7-accepts/Zig-rejects case in my corpus. Remedy: extend exhaustiveness checking (or mandatory `else` on non-enum scrutinees) — likely needs an approval packet if it rejects building programs.
2. **[M] Slice-length guards are not learned** — `fn get(s: []i32, i: usize) { if i < s.len { ret s[i] } }` still rejects "Index not proven in bounds" (`g_slice_len_guard`). Fixed-array literal bounds work; runtime slice length does not. This is the known broader family (MTH-16: fields/lengths are not facts), correctly not claimed repaired — flagging so it isn't mistaken for closure of the bounds story.
3. **[L] Range `for i in 0..10` remains a parse error** (exit 5) while `docs/lang-safety/` uses the form as canonical A7 — pre-existing docs/impl mismatch (F9), untouched.
4. **[L] Module-qualified struct literals/types** (`sh.Counter{…}`, `h: sh.Handle`) now fail closed at parse with located errors ("Expected type" / "Expected expression") instead of misleading ones — improved, but real multi-file surface remains future work (modules in retained limits).
5. Retained-limit spot-checks all behave as declared: `string.len` and scalar array fill rejected (exit 6), array→slice coercion rejected, ref swap/return rejected, char ordering rejected, named type-set alias exit 7, no-`main` library compiles.

## 5. Compatibility questions requiring user decisions (no action taken)

- Match-exhaustiveness fix (blocker 1) rejects programs that currently pass A7 — approval packet with before/after needed per the L24 rule.
- Mixed-sign comparison acceptance policy (`u32 > i32` now builds; peer semantics delegated to Zig) — fine empirically, but undocumented; decide whether to specify it.
- The 032 example's `d * d <= n` → `d <= n` change is semantically output-equivalent here but is a complexity change in a shipped example; harmless, noted for completeness.

## 6. Process, limits, state

Tools: normal bash + file tools only; no model/agent CLI; no built-in delegation needed this run (focused scope). Web not used. Full gate deliberately not run; focused pytest of the three new audit files (43 passed, 88.9s) and the cast matrix (595 passed) plus 69 A7 compiles and 24 native builds were executed. **Repository state:** read-only throughout; HEAD unchanged; dirty paths 149 at start and end (content evolved mid-review as acknowledged above — the `d_loop_defer_del` message refinement and array-bound-alias fix both landed during this review; all results cited are from the post-landing rerun). All artifacts under `/tmp/a7-glm53-repair-review/`. No commits, publication, or external messages. I do not claim global soundness of the safety pass, the type system, or the suite beyond the executed evidence above.
