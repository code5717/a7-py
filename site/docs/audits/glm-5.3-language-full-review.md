All verification complete. Here is the final audit.

---

# Independent Full A7 Language Review — GLM-5.3, Z.AI Coding Plan, 2026-09-19

**Scope:** language design, implementation, compiler correctness, safety enforcement, evidence quality — full repo, not limited to the website task.
**Checkout reviewed:** `701c67936c70ad2b0608326e23e56cc5d38c9fdb` (master) with **134 dirty paths** (compiler, docs, workflows, site). Repository state verified byte-identical before and after review (`REPO-STATE-UNCHANGED`). All repro artifacts in `/tmp/a7-glm53-language-audit/` (`cases/`, `out/`, `repo-state-snapshot.txt`, `all-a7-runs.txt`).

**Method:** read all core docs and plan/audit ledgers; delegated five read-only static sub-reviews (lexer/parser, type system, semantic/safety passes, backend/CLI/modules, test architecture) carrying this reviewer identity and a recursion guard; personally executed 48 focused A7 cases and 28 Zig 0.16.0 builds/runs. Findings below state their verification method: **executed** (I ran it), **static** (sub-review code reading, line refs spot-checked by me where cited), or **refuted**.

---

## 1. Verdict and prioritized confirmed blockers

**Verdict:** A7 is a functioning front end with a real pipeline and an unusually honest internal issue ledger, but it is not yet a safe or coherent language implementation. The safety contract's central promise — "fail closed: if a risky operation has no proof, semantic analysis rejects the program" (`docs/SAFETY_CONTRACT.md:3-6`) — is **falsified by six executed counterexamples** where A7 exits 0 and the binary traps at run time. A second, larger class is **acceptance without compilation**: at least 14 executed programs pass A7 (exit 0) and fail the Zig build or produce native types that contradict the checker's recorded types. The 9/9 gate with 2,651 tests is real (log inspected) but, per the repo's own mutation evidence and my structural confirmation, roughly half the suite cannot fail, so gate counts do not support safety claims. Documentation quality is bifurcated: STATUS/SAFETY_CONTRACT/decisions.md are candid; **SPEC.md materially misstates the implemented language** (swap/methods examples that cannot compile, unimplemented conversion rules presented as current, keyword drift, assignment-expression grammar that does not exist).

**Confirmed blockers, prioritized:**

| # | Blocker | Class | Evidence |
|---|---------|-------|----------|
| BL-1 | Safety facts restored without joins after `if`/loops/calls/defer → accepted division-by-zero, OOB, use-after-free; SEGFAULT/panic at run time | Soundness | Executed (5 binaries) |
| BL-2 | Parser error recovery silently deletes declarations; `main` vanishes, exit 0 | Correctness | Executed (`b_multi_decl`) |
| BL-3 | Locked decision L5 (integer wrap) not implemented: `x: u8 = 255; x += 1` panics "integer overflow" in Debug, UB in ReleaseFast | Design-vs-impl | Executed (`l5_wrap_test`) |
| BL-4 | ~14-shape "A7 accepts, Zig rejects" class incl. signed `/=`, `-u`, partial struct literals, keyword-named fns, `main` returning i32, `[2]string` defaults, escaped braces | Correctness | Executed (each named below) |
| BL-5 | Mixed-width arithmetic records the **left** operand's type while emitted Zig uses peer resolution → checker facts diverge from native values | Soundness | Executed (`c_mixed_width`: A7 says `i8`, native value 300) |
| BL-6 | No `main` existence/signature validation: files without `main` exit 0; `main :: fn() i32` emits code Zig rejects | Correctness | Executed |

---

## 2. Findings

Severity: C=critical, H=high, M=medium, L=low. "Stages": A7 compile exit vs Zig build vs native run.

### 2.1 Safety-enforcement holes (BL-1 group) — the contract is not met

**F1 [H, executed, known-family S2]** Loop bodies visited once; facts restored to pre-loop state after the loop.
- Refs: `a7/safety.py:477-486` (WHILE: one body visit, `restore_symbols(saved)`); FOR at `:487-497` (verified by my read of 455-545).
- Repro (`cases/d_loop_no_fixedpoint.a7`): `i: usize = 0; while i < 4 { i += 1 }; x := arr[i]` with `arr: [4]i32`.
- Stages: A7 exit 0 → Zig Debug build OK → **run: `panic: index out of bounds: index 4, len 4`** (exit 134).
- Test gap: no test indexes with a post-loop counter. Remedy: havoc-join all mutable facts at loop exit (or fixed-point widen); owned by the known S2 packet — still open.

**F2 [H, executed, known MTH-2/S3]** Calls invalidate no facts; `ref` writes through calls are invisible.
- Refs: `a7/safety.py:609-612` (CALL creates no obligations/fact invalidation; static).
- Repro (`d_call_invalidates.a7`): `x := 4; if x != 0 { zero_it(x); y := 100 / x }` where `zero_it :: fn(v: ref i32) { v = 0 }`.
- Stages: A7 exit 0 → build OK → **run: `panic: division by zero`**. Control `d_guard_div_ok` (no call) prints `25` — the guard machinery itself works.
- Remedy: havoc facts for any symbol passed as `ref` (and any unknown side effect) across calls.

**F3 [H, executed, known SAF-11 family]** No join at `if`/`match` merges; then-branch facts restored, else/then divergence ignored; un-braced else mutates persist.
- Refs: `a7/safety.py:464-474` (IF: restore pre-if facts after then; else visited with no snapshot); MATCH cases visited sequentially with no isolation (`:508-514`, static).
- Repro (`d_join_gap.a7`): `x := 4; … if t == 1 { x = 0 }; y := 100 / x` with runtime-true `t`.
- Stages: A7 exit 0 → build OK → **run: `panic: division by zero`**.
- Remedy: intersect facts over branches (and with the exit state of early exits); this is the known SA packet, still open.

**F4 [H, executed, NEW]** Braced `defer { b = new Box }` restores `facts` but not `moved_symbols` → use-after-`del` accepted.
- Refs: `a7/safety.py:523-541` — the DEFER branch snapshots/restores `self.facts` only; the ASSIGNMENT handler (`:455-458`) executes `moved_symbols.discard(target)`. Un-braced `defer b = new Box` is havoc-dropped (ASSIGNMENT not in `DEFER_HAVOC_EXCLUDED_KINDS`), so the two spellings fail in opposite directions.
- Repro (`d_del_braced_defer.a7`): `b := new Box; … del b; defer { b = new Box }; b.value = 2`.
- Stages: A7 exit 0 → build OK → **run: SEGFAULT** (use-after-free).
- Test gap: `test/test_safety_precursors.py:84-190` covers the L32 loop-defer fix but not moved-symbol restoration in braced defers.
- Remedy: snapshot/restore `moved_symbols` with the fact snapshot, and unify braced/un-braced defer havoc semantics. New finding, extends the documented P-SAF defer family (`docs/plan/audit/open-items.md:62-64`).

**F5 [H, executed, NEW]** Un-braced `defer del b` marks nothing; in a loop, later iterations use freed memory.
- Refs: `a7/safety.py:517-518` — deferred DEL only visits the expression (no `_mark_deleted`, no havoc; DEL is havoc-excluded).
- Repro (`d_loop_defer_del.a7`): `while n < 3 { defer del b; b.value += 1; n += 1 }`.
- Stages: A7 exit 0 → build OK → **run: SEGFAULT**. Mirror over-rejection: braced `defer { del b }` marks moved and never restores → safe programs wrongly rejected (static).
- Remedy: treat deferred `del` as havoc on the deleted binding after the defer site when inside a loop (symmetric with F4's rule).

**F6 [H, executed, known SAF-1]** No nil-proof obligation for `ref` arguments at call sites.
- Refs: `a7/safety.py:609-612` (call site creates no `REF_NON_NIL` obligation; params assumed non-nil inside callee at `:647-648`, static).
- Repro (`d_ref_nil_call.a7`): `b: ref Box = nil; g(b)` where `g :: fn(b2: ref Box) { b2.value = 1 }`.
- Stages: A7 exit 0 → build OK → run: Debug `panic: attempt to use null value` (Zig `.?` unwrap backstop); **ReleaseFast: UB, no backstop** (builds use `-OReleaseFast`, `scripts/build_examples.py:22-25`).
- Remedy: obligations for `ref` args at call sites (known, fix owned by P0b.10, not landed).

**F7 [M, static-confirmed + spot-checked, known]** Structural gaps in the obligation model: `_prove_integer_overflow` begins with an unconditional `return` (`a7/safety.py:795-801`, dead body `:802-811` — I verified the source); `UNION_FIELD` has zero producers; `.ptr` fields assumed non-nil (`:599-600`); struct fields never facts (MTH-16). Combined with F13 below, arithmetic results are entirely unbounded.

### 2.2 Parser correctness

**F8 [C, executed, known PRD-33 — still live]** Error recovery silently deletes declarations and promotes locals to top level.
- Refs: `a7/parser.py:189-221` (recovery conditions; verified by my read), `synchronize()` `:257-290`; the "Case 2" filter tests `"Expected expression after"` (`:210`) while `parse_primary_expression` raises `"Expected expression"` (`parser.py:1749`, static) — the intended hard-error path never matches.
- Repro (`b_multi_decl.a7`): `main :: fn() { x, y := 10, 20 }`.
- Stages: **A7 exit 0; emitted Zig file content is exactly `var y = 10;`** — no `main`, `x` gone. Same class (`e_qualified_type`): `h: sh.Handle` in a one-declaration file hard-errors exit 5 with "Unexpected token '}' after parsing complete program" (misleading); with ≥2 declarations the enclosing declaration is silently dropped (static trace; the ≥2-decl asymmetry is at `parser.py:203-208`).
- Remedy (no approval needed — crashes/miscompiles class per L24): make ParseError fatal once any function body is open; fix the message match; report recovery drops.

**F9 [M, executed]** `for i in 0..10` is a parse error ("Expected LEFT_BRACE, got DOT_DOT", exit 5) although 15+ docs under `docs/lang-safety/` use the form as canonical A7 (`cases/b_range_for.a7`). Range iteration is either a feature gap or a docs bug — currently neither is stated.

**F10 [M, executed]** `1_` → **exit 8 (internal)**, "Unexpected error: invalid literal for int(): '1_'", no line/col (`cases/b_underscore_num.a7`; tokenizer accepts `_` anywhere in numbers, `a7/tokens.py:532-570` static; `int()` crash in `a7/ast_nodes.py:577-590`). Exit 8 is asserted nowhere in the suite (test-architecture sub-review).

**F11 [M, executed]** Multi-line array literals rejected ("Expected expression", exit 5, `b_multiline_array.a7`) while multi-line calls and named struct literals are accepted — inconsistent placement rules (`parser.py:1938-1942` vs `:1561`, static).

**F12 [L, executed]** `a[1...3]` lexes as `1 .. 0.3` → confusing "Array index must be integer: got 'f64'" (exit 6) instead of a `...` diagnostic (`b_ellipsis_slice.a7`; `a7/tokens.py:921-925` static). SPEC 2.5 lists `...` and `?` as operators; `?` is an invalid character.

**F13-family [L, static]** Also confirmed by static review, selected: string length limit 32,767 constant vs SPEC's 65,535, unenforced (`a7/tokens.py:16`, SPEC Appendix C); `\b \f \v \a` escapes documented but rejected; `\xFF` accepted against "ASCII only"; unterminated `/*` silently consumes the file; `#` comments supported but undocumented; multi-line string token spans wrong; `fn`-type with omitted return fails before `}`/`{`/EOF; parser iteration cap prints a warning **to stdout**, corrupting `--format json` on successful compiles.

### 2.3 Type system

**F14 [H, executed, NEW]** Mixed-width integer arithmetic: result recorded as the **left operand's type**; emitted Zig has no annotation and uses peer resolution.
- Refs: `a7/passes/type_checker.py:1244-1249` ("Result type is the wider of the two" comment; code returns `left_type` — verified by my read of 1185-1250); backend emits `(a + b)` unannotated (`a7/backends/zig.py:1678-1679`, static).
- Repro (`c_mixed_width.a7`): `a: i8 = 100; b: i64 = 200; c := a + b; io.println("{}", c)`.
- Stages: A7 exit 0 → build OK → **prints 300 while the checker's recorded type for `c` is i8**. Every downstream A7 fact (cast range proofs, bounds intervals) is computed against a type the native code does not have. Mixed-sign comparisons (`u > i`) are also accepted (`c_mixed_sign_cmp` built OK here because operands were comptime-known; runtime variants fail Zig peer resolution — partially verified).
- Remedy: require one side assignable to the other (or emit explicit widening) — this changes accepted programs, so it goes to an approval packet (see §5).

**F15 [H, executed]** Compound signed `/=` and float `%=` pass A7 and fail Zig.
- Repro (`c_compound_div_signed.a7`): `x: i32 = 7; x /= y` → A7 exit 0, Zig: "signed integers must use @divTrunc…" (binary `/` is correctly lowered to `@divTrunc`; compound forms map to bare `/=`/`%=`, `zig.py:2409-2422` static). Same executed family: `-u` on unsigned (`c_neg_unsigned`: Zig "negation of type 'u8'"), `x << -1` (`c_shift_neg`: Zig rejects comptime; runtime amounts would be checked `@intCast` panics), partial struct literals (`c_partial_struct`: "missing struct field: count"; no missing-field check at `a7/passes/type_checker.py:2780-2809`, static).
- Remedy: mirror the binary-form lowerings in compound form; add missing-field and unsigned-negation checks. Preserves intended semantics; the acceptance is plainly accidental.

**F16 [H, executed, NEW]** Literals are typed `i32` globally (`type_checker.py:1187-1188`, verified) and the SPEC A.2 conversion "integer literals to any integer type if in range" applies **only** to initializers.
- Executed: `f(200)` into `fn f(x: u8)` → exit 6 ARGUMENT_TYPE_MISMATCH (`c_call_arg_u8`); `fn g() u8 { ret 200 }` → exit 6 (`c_return_u8`); slice-call variant `get(arr[0..4], 2)` → exit 6 (`g_slice_len_guard`); if-expression `if c { 1 } else { x }` with `x: i64` → exit 6 while match-expressions widen (`c_ifexpr_mixed`; `type_checker.py:2006-2014` static). Also static-confirmed: implicit int→float conversions allowed (a fourth, undocumented implicit conversion; `a7/types.py:137-138`).
- Effect: unsigned-parameter/return APIs are unusable with literals — the language's own `usize`-indexing guidance cannot be followed ergonomically.
- Remedy: apply the initializer literal-range rule uniformly (args, returns, if-expr branches). Mostly restores documented semantics (SPEC A.2); compatibility scan still required.

**F17 [H, executed]** SPEC A.2 "Array to slice (safe widening)" is implemented **nowhere** (`c_arr_to_slice.a7`: `sum(arr)` with `arr: [3]i32`, `sum :: fn(s: []i32)` → exit 6). Zig itself coerces this. Either implement or delete the promise.

**F18 [M, executed, known SAF-21/LNG-15]** `N :: 3; arr: [N]i32; arr[0]` → exit 6; const array sizes produce `ArrayType(size=None)` and unindexable arrays (`g_const_arr_size.a7`; `type_checker.py:380-384, 397-415` static).

**F19 [M, executed, known LNG-04]** Guarded indices from parameters/fields/calls never prove bounds: `fn get(a: [4]i32, i: usize) { if i < 4 { ret a[i] } }` → exit 6 (`g_guard_index.a7`). Guards only learn lower bounds, never upper bounds (`safety.py:843-868` static). No bounds-checked accessor can be written — this blocks the language's core safe-indexing story.

**F20 [M, executed, known LNG-12]** Guard facts dropped across casts: `if c != 0 { z := 100 / cast(i32, c) }` with parameter `c` → exit 6 "Divisor not proven non-zero" while the uncast form passes (`g_cast_divisor3.a7` vs `d_guard_div_ok.a7`). Note: my const-`c` variant was accepted (branch folded), so the repro needs a runtime/param value.

**F21 [M, executed]** char is unusable beyond equality: `flag < other` on `char` → exit 6 (`g_char_order.a7`); no ordering, arithmetic, or char↔int cast (known LNG-02).

**F22 [M, executed, NEW]** SPEC's canonical generic `swap` is unimplementable: `a = b` on `ref` params → "Cannot assign to immutable binding" (`g_ref_swap.a7`, exit 6); reading a ref param as a value yields `ref i32` mismatches (`g_ref_return.a7`: `ret v` → "Return type mismatch: expected 'i32', got 'ref i32'"). SPEC 6.1/7.1 present `swap` as the flagship example. Document the limit or define ref read/write semantics.

**F23 [M, static]** Generic struct fields that wrap `$T` fail codegen — **sub-review NEW, then executed by me**: `Box($T) :: struct { items: []$T }` → **A7 exit 7** (`e_generic_struct_field.a7`; `_emit_type_node_generic` handles only bare `TYPE_GENERIC`, `zig.py:590-597`, static). Only `value: $T` works. Generic receiver `ref $T` field reads also fail (MTH-7, static-confirmed).

**F24 [L]** `math.abs` on signed ints: checker returns the signed arg type; backend emits unannotated `@abs` → native unsigned. Executed: `z := math.abs(x) - 10` with `x: i32 = 5` → A7 exit 0, **Zig build fails** "overflow of integer type 'u32' with value '-5'" (`a_abs_sub.a7`); plain `y := math.abs(x)` builds and silently types `y` as `u32` natively while A7 records `i32` (`a_math_abs_signed.a7`, emitted `const y = @abs(x);` at out/a_math_abs_signed.zig:16). Known website finding — **still present**.

### 2.4 Backend / CLI / modules

**F25 [M, executed]** Zig-keyword escaping applied at reference sites but not declaration sites (static, `zig.py:318-332` vs `:445/:548/:608…`): function named `test` → A7 exit 0, Zig "expected '(', found 'test'" (`e_keyword_fn.a7`). Extends the L34 fix's coverage.

**F26 [M, executed]** `main` handling: no `main` → exit 0, emits `const x = 42;` (`b_no_main.a7`) (known LNG-16); `main :: fn() i32` → A7 exit 0, Zig "value of type 'i32' ignored" (`e_main_sig.a7`) — NEW sibling.

**F27 [M, executed]** `f := math.sqrt` as a value → A7 exit 0, Zig "use of undeclared identifier 'math'" (`e_math_fn_value.a7`, known). `[2]string` default init → A7 exit 0, Zig "expected type '[]const u8', found 'comptime_int'" (`e_string_array_default.a7`, NEW executed confirmation of static finding).

**F28 [M, executed]** Match statements without `else` on non-enum scrutinees pass A7 and fail Zig switch exhaustiveness (`g_match_no_else.a7`: "switch must handle all possibilities") — known LNG-10, confirmed at the boundary.

**F29 [M, executed, NEW]** Parameter shadowing a top-level function: `caller :: fn(g: fn(i32)) { h := g; h(5) }` → A7 exit 0 (note: **no false recursion error** — the feared N4 false-positive did not materialize on this tree), but Zig fails "function parameter shadows declaration of 'g'" (`f_false_recursion.a7`). The L34 shadowing fix did not cover params-vs-functions.

**F30 [M, executed, known]** Escaped IO braces, both directions, checker and emitter disagree: `io.println("{{}}")` → A7 exit 0, Zig "too few arguments" (`a_braces_escape.a7` — confirmed still present); `io.println("{ }")` → falsely rejected exit 6 (`a_braces_space.a7`). Nuance vs the static claim: `io.println("{{}}", x)` is now rejected at A7 (exit 6) — the arg-consuming form does not pass.

**F31 [M]** Modules (executed + static): import cycle `a.a7 ↔ b.a7` → exit 6 with "Unknown stdlib call './b.fa'" / "Undefined type (Identifier 'b')" — no cycle diagnostic; cycle detection is dead code (cache return precedes the guard, `a7/module_resolver.py:124-135, 188-191`, static; known VIS-3). Module-qualified struct literal `sh.Counter{value: 1}` → exit 6 with "Undefined type (Identifier 'c')" — **not** the silent main-drop recorded as MTH-12; on this tree it fails closed with a bad message (my shape; the original MTH-12 shape may differ). Generic module calls, intra-module sibling calls, and transitive imports remain broken per static review (VIS-4, PIP-6) — not re-executed by me.

**F32 [L]** Type-set aliases: top-level named `Ints :: @type_set(i32, i64)` → exit 7 at codegen (`a_typeset_alias.a7`) — known website finding, **still present**; parser routes it to CONST with a TYPE_SET value that no backend consumes (static: `parser.py:489`, `zig.py:1519-1520`).

**F33 [L]** Evaluation order (SPEC A.1 left-to-right) is not enforced by temporaries; emitted Zig delegates to Zig's unspecified order (static, `zig.py:1715-1733`). Design decision needed.

**F34 [L, executed]** Scalar-filled fixed arrays (`arr: [3]i32 = 0`) rejected exit 6 (`a_arr_scalar_fill.a7`) and `s.len` on strings rejected exit 6 (`a_string_len.a7`) — known website findings, **both still present**, both contradict SPEC 2.6/3.3 (`slice.len` documented as a property).

### 2.5 Locked-decision conformance

**F35 [H, executed]** **L5 (integer wrap) is not implemented.** `x: u8 = 255; x += 1` → A7 exit 0, Debug run: `panic: integer overflow` (`l5_wrap_test.a7`); ReleaseFast: UB. Decisions.md L5 scope explicitly requires `x == 0` after the increment. Either implement (emit wrapping ops `%+`-style / `@addWith`) or gate arithmetic under the v1 plan's G3 before any arithmetic claim. No user-facing doc currently states that overflow traps.
**L33 (float remainder) is implemented correctly**: `-1.5 -1.5` at both fold and runtime (`l3_float_rem.a7`) — confirmed fixed.
**L32 (defer-in-loop havoc)**: fix present (`safety.py:526-536`) and the documented rejection works, but F4/F5 show the moved-symbol half is missing.

### 2.6 Recursion ban

Direct recursion correctly rejected (exit 6, `f_direct_recursion.a7`); ban covers mutual/alias/trampoline per static review of `semantic_validator.py:501-637, 829-876`. Nested functions are rejected wholesale at name resolution ("Undefined type (Identifier 'inner')", `f_nested_recursion.a7`, `e_nested_fn_in_if.a7`, `e_nested_fn_dup.a7` — all exit 6), which moots the static sub-review's nested-function recursion-ban and duplicate-hoist concerns **as reachable code paths** (the hoisting machinery at `ast_preprocessor.py:529-544` remains dead-ish and divergent — cleanup candidate). Compiler-internal no-recursion: `test/test_no_recursion.py` holds a shrinking allowlist (per AGENTS.md); parser and parts of the backend are still recursive — consistent with what README states.

### 2.7 Refuted / corrected expectations (process value)

- Sub-review predicted false recursion errors from param-shadowed aliases (N4): **did not reproduce**; instead a new Zig-stage shadowing failure (F29).
- Sub-review predicted nested functions bypass the recursion ban (N3): **unreachable** — nested `fn` declarations fail name resolution entirely.
- `io.println("{{}}", x)` silently consuming args: **refuted** — now rejected at A7 (exit 6).
- MTH-12 module-qualified struct literal silently deleting `main`: **changed behavior** on this tree — fails closed with confusing diagnostics (F31).
- `b_long_if` (10-token struct-literal heuristic window): my 9-condition `if` compiled correctly — the specific M5 misfire did not reproduce as constructed.

### 2.8 Documentation accuracy (language-level)

- **SPEC.md misstates the language**: §6.1/7.1 `swap` cannot compile (F22); §6.5 Methods examples fail (repo's own MTH-4/5 note); A.2 conversions unimplemented (F16/F17); §12.4/13.3 assignment-as-expression and `.val` postfix do not exist; §2.4 keyword list drifts from the tokenizer (`cast/const/self/var/using/type/size_of` are not keywords; `not/let/int/uint/float` are reserved but unusable); §9 (tensors) is presented in A7 fencing though nothing compiles (repo already plans to relabel); Appendix C limits unenforced (string 65,535 vs 32,767; import depth 32 fails at 2 per prior audit).
- **README "What Works" overclaims**: "Expressions: All operators with proper precedence" — false for `/=` signed, `-u`, `<< -1`, mixed-width semantics (F14/F15); "Fixed-array `+`" is 1-D-only with a self-contradictory diagnostic (`type_checker.py:1223-1233`, verified: "add between [2][2]f64 and [2][2]f64").
- **STATUS.md/SAFETY_CONTRACT.md are candid** about known gaps (the five website findings, incomplete arithmetic/union/ownership proofs) but the safety contract's fail-closed claim needs a qualifier until BL-1 lands: today the contract holds only for straight-line, call-free, defer-free code with literal-derived facts.

---

## 3. Topic/subsystem inventory and disposition

| Topic | Disposition | Read / Executed |
|---|---|---|
| Docs: README, SPEC (full), STATUS, SAFETY_CONTRACT, RELEASE, CHANGELOG, plan/decisions, plan/audit/open-items | Read in full; cross-checked vs behavior | Read |
| Lexer/tokens (a7/tokens.py) | Reviewed (static) | Read (sub-review); spot-checks by me |
| Parser (a7/parser.py) | Reviewed (static) + 12 executed cases | Both |
| AST/literals (a7/ast_nodes.py) | Partial (static) | Read (partial) |
| Name resolution, symbol table, semantic context | Reviewed (static) | Read |
| Type checker, types, generics, cast classifier, const_eval | Reviewed (static) + 12 executed cases | Both |
| Semantic validator (incl. recursion ban) | Reviewed (static) + 4 executed cases | Both |
| Safety pass | Reviewed (static) + 8 executed cases incl. 6 crashing binaries | Both |
| AST preprocessor | Reviewed (static) | Read |
| Zig backend | Reviewed (static) + 28 builds/runs | Both |
| Module resolver | Reviewed (static) + cycle/multi-file executed | Both |
| CLI/compile/errors (exit codes, formats, output protection) | Reviewed (static); exit codes exercised across 2-8 | Both |
| Stdlib (io/math/mem/string registries) | Reviewed (static) + io/math exercised | Both |
| Examples (43) + golden outputs | Listed; 037/035/013/017/018 read; goldens architecture reviewed | Read |
| Test architecture (53 files, scripts, gate) | Reviewed (static); gate log inspected | Read |
| Release-gate.log (site/docs/audits/ui-components-evidence/) | Inspected: genuine 9/9 run, 2,651 pytest, 43/43×3, 61/61; file untracked, mtime 2026-09-19 22:12 +0300 — local-run evidence, not CI | Read |
| Formatters, site UI, docs site content | Out of scope (sibling Flash audit); not reviewed | — |
| `a7/stdlib/mem.py`, `string.py` content | Skimmed (registry only) | Read (partial) |
| Full 2,651-test suite contents | Not individually reviewed; structural sample only | — |

---

## 4. Commands, checks, limits, repository state

**Executed** (all outputs in `/tmp/a7-glm53-language-audit/out/`, `all-a7-runs.txt` has the full matrix): 50 A7 compiles via `uv run python main.py <case> -o /tmp/...` (Zig 0.16.0, Python 3.14.7/uv 0.12.15); 28 `zig build-exe` (Debug) + runs under `timeout 5`. Six binaries trapped: 3 Zig safety panics (div-zero ×2, OOB ×1), 2 segfaults (use-after-free), 1 null-unwrap panic. Controls (`z_smoke`, `d_guard_div_ok`, `b_fn_type_no_ret`, `g_cast_divisor2`, `l3_float_rem`) behaved correctly. One full-suite pytest run was deliberately **not** repeated (controller's gate is fresh and was independently inspected instead).

**Known vs new:** verified-still-present known items: escaped braces (both directions), math.abs signed, scalar array fill, `string.len`, type-set alias exit 7, PRD-33, LNG-02/04/10/12/15/16, SAF-1, S2, S3, MTH-2/7/16, TYP-19, VIS-1/3, PIP-6-family, io-hijack residuals (not re-executed), float-remainder fix (working), L34 loop-capture fix (working), output-overwrite protections (present, static). **New findings:** F4, F5 (defer/del moved-symbol holes — executed crashes), F14 (left-type divergence — executed), F23 (generic wrapped-field exit 7 — executed), F26 `main :: fn() i32` (executed), F27 `[2]string` default (executed), F29 param-shadows-fn Zig failure (executed), F16's arg/return literal-rule scope (executed), F9 range-for docs mismatch (executed), plus static-only new items: declaration-site keyword quoting, `FunctionType` equals/hash break, dead monomorphizer, mixed-sign comparison acceptance, exit-8/stderr test gaps, match-capture rename bypass.

**Limits:** static sub-review claims carry line refs I spot-checked only where cited as verified; Zig-side semantics checked against the local 0.16.0 toolchain behavior, not external references, except where the repo's own executed audits (L33/L34 corrections) corroborate. No mutation testing re-run (read-only mandate); test-quality percentages are structural estimates from the sub-review, consistent with the repo's own recorded mutation results. Web search was not needed and not used. No credentials encountered.

**Process evidence:** the first run of this review was aborted when OpenCode auto-rejected `mkdir -p /tmp/a7-glm53-language-audit` as external-directory access; the controlling session resumed with `--auto`, after which all temporary work succeeded. No other tool limits hit.

**Repository state:** unchanged (same HEAD, same 134 dirty paths before and after; `REPO-STATE-UNCHANGED` diff verified). Nothing committed, pushed, or deployed; no model/agent CLI launched; all artifacts under `/tmp/a7-glm53-language-audit`.

---

## 5. Remediation roadmap

**Track A — implementation fixes preserving intended semantics (no language approval needed; L24's crash/miscompile/Zig-rejected classes):**
1. **Parser recovery** (F8): make in-body ParseErrors fatal; fix the `"Expected expression after"` message mismatch; assert no silent declaration drops. Add the missing exit-8 and dropped-declaration tests.
2. **Safety joins and invalidation** (F1-F6): fact intersection at if/match/block merges; loop fixed point or exit-havoc; call-site `ref` obligations; snapshot `moved_symbols` with facts in defers; unify braced/un-braced defer havoc. This closes BL-1 and makes the safety contract's fail-closed claim true for the operations it claims to enforce.
3. **Zig-rejected acceptance sweep** (F15, F25-F30): compound `/=`/`%=` lowerings; declaration-site keyword quoting; `main` existence/signature validation; missing-struct-field check; `[N]string` defaults; `math.sqrt` value rejection; escaped-brace checker/emitter unification (pick one model in code, both sides).
4. **Diagnostics**: `1_` and friends as tokenizer errors (kill exit-8 leaks); cycle-specific import diagnostic; `...` and qualified-type messages.
5. **Doc-only, no approval**: fix SPEC §6.1/7.1 swap, §6.5 methods, A.2 conversions, §12.4/13.3 grammar, keyword list, README "all operators" claim; state the overflow-trap reality next to L5 until Track B decides.

**Track B — behavior/semantic changes requiring user approval packets (per the approval rule in AGENTS.md / decisions.md L24):**
1. Mixed-width/mixed-sign arithmetic rule (F14): propose "both sides must have the same type; no implicit peer resolution" with `cast` for widening, showing `a: i8 + b: i64` before (accepted, mis-typed) / after (rejected with hint). Compatibility: newly rejects programs that build today (which currently diverge silently).
2. L5 implementation (F35): choose emit-wrapping (`+%` etc.) vs keep-trapping-and-document; before/after `x: u8 = 255; x += 1` → `0` vs panic. Locked decision says wrap; implementing it changes native results for programs that avoid overflow in practice (blast radius expected ~0, but scan required).
3. Literal typing (F16/F17): extend in-range literal rule to args/returns/if-exprs; decide array→slice widening (SPEC promises it) or withdraw the promise.
4. Defer semantics (F4/F5 remediation half): decide when a deferred `del`/assignment takes effect (the repo's own open P-SAF question) — the enforcement fix in Track A must implement whatever is decided here.
5. Evaluation-order temporaries (F33), char operations (F21), `ref` read/write surface (F22), scalar array fill and `string.len` (F34): each needs a small before/after packet; several already have decisions pending in gates.

**Track C — evidence repair (the repo's own mutation lane, seconded):** replace the self-comparing cast matrix (~47% of the suite) with hand-authored expectations; pin the full precedence table and associativity; add stderr-separated and exit-8 error-stage cases; rejected-on-purpose examples; stderr goldens; runtime tests for element-wise `+`; the ten missing tests listed by the test-architecture sub-review are the right backlog.

No numeric score assigned; gate counts do not establish production safety, and six executed counterexamples currently disprove the safety contract's fail-closed claim.
