> **Source:** Claude Plan subagent, fix plan for the type system, safety pass, preprocessor and Zig backend audit findings (TYP, SAF, ZIG), 2026-09-16.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim from the agent's final message. ZIG-10 to ZIG-40 and SAF-25 were assigned by this planner. The approved execution plan (`docs/plan/execution.md`) governs where they differ.

I could not write the plan file: this session has no Write or Edit tool, and plan mode forbids writing through the shell. The full plan follows here.

# Fix plan for the types, safety and backend audit findings

## 1. Summary

- **What to do first, without asking:** three silent-wrong-output bugs and the no-approval precursors they depend on.
  - **Batch C1:** a folded constant picks up a dead node's type (ZIG-1, SAF-7). The fix goes in the folding functions of `a7/ast_preprocessor.py`; it does not wait for Wave 2.1.
  - **Batch C2:** calls whose root is any identifier named `io` or `math`, or a user function named `abs_f64`, get replaced by stdlib code. The fix makes one scope-aware annotation the only source of truth.
  - **Batch C3:** if-expressions lose their parentheses, struct fields evaluate in written order, and each print overwrites the start of a redirected file.
- **Safety soundness fixes go into `a7/safety.py` now (Waves 1b and 1c), not in Wave 3.** Only proof precision (track 5) waits for the IR fact engine. Section 2 gives the reasons.
- **Three approval packets, one per area.**
  - Safety: P0b revision 3, which is P0b plus an addendum.
  - Types: P-TYP, a new packet.
  - Backend: P-BK, a new packet.
  - Findings that belong to a gate that already has a packet go into that packet (G3 rows to P4, union reads to P5, source text to P2), so each finding appears in exactly one packet.
- **Lane S splits into three sub-lanes with separate files, so they can run in parallel worktrees.** This is a plan change for the controller, not a language change. S1 owns `safety.py`, the folding functions and a new `a7/const_eval.py`. S2 owns `type_checker.py`, `types.py`, `generics.py` and `name_resolution.py`. S3 owns `semantic_validator.py`. B keeps `zig.py` and the non-folding preprocessor functions.
- **One sequencing hazard the audits did not name.** Two unsafe programs are hidden today only because Zig rejects the emitted code:
  - Safety probe `p18` (`x := 0; defer x = 5; y := 10 / x`) is accepted today because `safety.py:379-384` applies the deferred assignment at the defer site. Zig rejects the output only because of B11 (`defer void;`, `tmp/audit/compiler/safety/out/p18_defer_assign_fact.zigerr`). I call this SAF-25; it is new from the probe results and was not written up by the auditor.
  - SAF-24 is hidden the same way by the capture-shadowing bug.
  - Batch C4 must therefore be applied before Lane B's B10 and B11 fixes (P0.1 items 5 and 6). Otherwise those fixes turn a Zig rejection into a division by zero that builds.

## 2. Which safety fixes land in `safety.py` now, and which wait

**Decision:** land every fix that removes an unsound fact or adds conservative invalidation, plus the loop fixpoint, in the current pass. Leave fixes that only prove more programs safe (precision) for the IR engine.

| Land now in `safety.py` | Waits for the IR fact engine (Wave 3 or track 5) |
| --- | --- |
| SAF-1 check at the call site that a `ref` argument is not nil; SAF-2 remove the rule that any field named `ptr` is non-nil; SAF-5 remove the rule that `a / b` is non-zero; SAF-11 clamp intervals to the type | Facts on field paths (`if o.ptr != nil { o.ptr.value }`) |
| P0b.1 hull join at block and branch exits; SAF-3 match join including `fall`; SAF-4 | Precise alias reasoning for `ref` parameters beyond "any local ever passed by `ref`" |
| P0b.4 compound-assignment intervals; P0b.3 escape invalidation; SAF-6 globals dropped at calls | Use-after-`del` tracked per path (`b := a; del a; b.x`), memory gates M3 and M4 |
| P0b.2 option (c): loop fixpoint with widening; E8 `break` joins | Indexing slice and string parameters (S11), `.?.*` narrowing, for-in index upper bound (`p23`) |
| SAF-8 and P0b.5-8 `del` holes; SAF-20, 21, 22, 24, 25; SAF-23 via an explicit stack | Overflow obligations (P3 and L5), shift obligations (P4), union active-field tracking (P5) |

Reasons:
1. **The code already exists as a measured prototype.**
   - `tmp/repro2/scan/analyze_e.py:109-422` (`JoinSafety`) implements the hull join for blocks, `if` and `match`, compound intervals (R7), escape invalidation (R3E) and a widened loop fixpoint.
   - It ran over 2440 programs: 0 affected for join, compound and escape; 2 examples for the fixpoint (`docs/plan/audit/2026-09-16-inventory-repro.md:72-81`).
   - Porting it is bounded work. Each fact-source fix (SAF-1, 2, 5, 6, 11) is under about 30 lines.
2. **Waiting ships real holes for two waves.** The IR engine is Wave 3 behind packet P7. Until then, null writes (SAF-1, SAF-2), division by zero (SAF-3 to SAF-6, S1 to S3) and out-of-bounds indexing in loops (S2) keep building. Lane E writes apps 059-063 against this pass in Wave 2, and P0b already found 5 examples approved for the wrong reason.
3. **The rules and tests carry over.** The `test/soundness/*.a7` pairs written now are the acceptance suite that Wave 3.3 needs. The join, widen and escape rules become the specification for `a7/ir/facts.py`. Wave 3.3 shadow mode compares the old and new engines. With a sound old pass, differences in that report are precision, not soundness.
4. **Precision work would duplicate Wave 3.** Field-path facts, per-path `del` state and aliasing need places and a CFG, which the IR provides (execution.md 3.2).

**Three defects in the prototype must not be ported:**
- **SAF-4 is not fixed by the join.**
  - `analyze_e.py:241` still calls `_learn_after_stmt`, and `safety.py:663-668` then overwrites the joined `v` with `nonzero=True` while its interval stays `[0,0]`.
  - Fix: delete `_learn_after_stmt`. Apply `_facts_from_condition(positive=False)` when entering the else branch. Refine at the fall-through point only when `then` always exits (abrupt) and there is no else.
- **The match join (`analyze_e.py:264-283`) starts every case from the state before the match and ignores `fall`.** A case that ends in `fall` must pass its end state into the next case's entry. Otherwise `case 1: x = 0; fall` followed by `case 2: 10 / x` is approved.
- **SAF-6 is not covered by R3E, which handles locals.**
  - Rule: every call that is not a resolved stdlib call (C2 annotation) drops the facts of every file-scope `VAR`.
  - File-scope `::` constants keep their facts in a per-program table seeded into each function, which also closes SAF-21.

The port rewrites `_visit_stmt` and `_visit_expr` anyway, so it uses explicit stacks. Statements use frames with actions, following `name_resolution.py:401-419`; expressions use a post-order stack. That closes SAF-23 without a separate conversion.

## 3. Shared root causes (coordinate by these names)

| Name | Findings | Owner here | Other planner |
| --- | --- | --- | --- |
| Node identity | ZIG-1, SAF-7 | C1 now; Wave 2.1 re-keys | none |
| Stdlib recognized by name text | ZIG-5, SAF-9, B14 | C2 | PIP-2 (= SAF-9) and PIP-3 (= ZIG-5): same fix, counted once in C2. PIP-1 (local shadowing a file-module alias) should read the same annotation |
| Unknown type assignable to everything | TYP-01, TYP-10, TYP-12, TYP-16 | T1, T2 | PIP-15 (use before declaration) uses the same "declared-before" lookup |
| BINARY nodes without spans | TYP-21, SAF-22 | T8, C4 fall back to operand spans | PAR-04 fixes the parser |
| Recursion-limit failures | TYP-18, SAF-23, ZIG-32 | batch R, SA | PAR-08, PIP-14 |
| Name-keyed preprocessor analyses | ZIG-13, ZIG-14, SAF-15 to 19 | Z1, Z2 | Wave 3 liveness replaces them |

## 4. Batches

Backend findings without auditor IDs get IDs assigned here from their probe names, because the backend report was never written:
- ZIG-10 p009, ZIG-11 p011, ZIG-12 p015-p018, ZIG-13 p029, ZIG-14 p030, ZIG-15 p032.
- ZIG-16 p033, ZIG-17 p035, ZIG-18 p036, ZIG-19 p037, ZIG-20 p041, ZIG-21 p045 and p046.
- ZIG-22 p047b, ZIG-23 p086, ZIG-24 p122, ZIG-25 p155 and p156, ZIG-26 p161b, ZIG-27 m1.
- ZIG-28: the known items the backend audit reproduced.
- ZIG-29 p038, p039 and p093; ZIG-30 p099; ZIG-31 p064; ZIG-32 nestblock_400.
- ZIG-33 p161, ZIG-34 p013 and p149, ZIG-35 zig fmt, ZIG-36 dead code, ZIG-37 test gaps.
- ZIG-38: other unapproved operations; ZIG-39: the print writer; ZIG-40: nested functions.

The audit summary counts "about 25 MEDIUM, about 10 LOW"; that total is unverified against this list. Probes are under `tmp/audit/compiler/{types,backend,safety}/probes/`.

Triage classes are P0.1's A to D:
- **A:** no program changes.
- **B:** A7 accepts, Zig rejects.
- **C:** miscompile.
- **D:** wrongly rejected.

"RT test" means compile with the real CLI, then build Debug and ReleaseFast and run, comparing against output written by hand before the first run. Runtime tests go in the planned `test/test_zig_backend_runtime.py`; paired rejected and accepted programs go in `test/soundness/`.

### Wave 1a: CRITICAL miscompiles and precursors (no approval)

**C1. Folded nodes keep identity; folding is exact** (S1)
- **Closes:**
  - ZIG-1 and SAF-7, including the f06, f17b and p082 variants.
  - SAF-10 (S13, P0.1 item 14).
  - SAF-12 and ZIG-11 (the folded part).
  - SAF-13 and SAF-14.
- **Files:**
  - `a7/ast_preprocessor.py`: `_transform_tree` (129-149), `_fold_unary` (551-588), `_fold_binary` (590-694).
  - New `a7/const_eval.py`.
- **Implementation note, 2026-09-19:** The approach below records the original
  plan. Current preprocessing retains replaced nodes in a dictionary attached
  to the root. C1's execution record supersedes finite-only float folding;
  current folding preserves IEEE nonfinite results. Float remainder mismatch D7
  remains open.
- **Approach:**
  1. When a fold returns a new node, copy `type_map[id(old)]` to `type_map[id(new)]`, and keep the replaced node alive in a list attached to the program root (`folded_originals`).
     - Popping only the old key is not enough. The freed `left` and `right` literal children also have `type_map` entries, and their ids get reused by later folds.
     - Keeping the replaced subtree alive prevents any id reuse until codegen ends. Tables keyed by id in `FactMap` and `BackendPlan` then stay correct.
  2. `const_eval` folds integers with Python ints, truncating `/` and `%` toward zero. It folds only when the result fits the node's type from `type_map`, shifts only when `0 <= amount < width`, and floats only when the result is finite. Otherwise the node is left unfolded.
     - Leaving `1e308 * 10.0` unfolded gives IEEE inf in Zig, which matches L16.
     - `2147483647 + 1` in a typed `i32` declaration and `1 << 20000` become type errors in T3 (exit 6 with a line), not internal errors.
  3. f32 folding stays under G1 and P4.
- **Class:** C (ZIG-1, SAF-10), B (SAF-12, SAF-14), A (SAF-13).
- **Tests:**
  - RT on the exact `p081e` program: expect `total=65`, and f17 expecting `true 65`.
  - RT on the p080 shape: 200 folds interleaved with char, string and bool locals, every number printed in decimal.
  - Python invariant: every folded replacement has the replaced node's type.
  - The failing baseline test `test_large_integer_folding_preserves_exact_quotient_and_remainder` passes.
  - Boundary folds at i8, u8, i64 and u64 agree with run time (extend `test/test_pipeline_native.py:59-97`).
  - CLI: `1 << 20000` gives exit 6 with a line; `x: i32 = 2147483647 + 1` gives exit 6.
- **Dependencies:** none. Wave 2.1 later replaces the retention list with `node_id`.
- **Unverified:** that no node created after safety needs an approval, so `BackendPlan` keys cannot be forged (audit inference). The 2.1 invariant test settles it.

**C2. Stdlib calls recognized by resolved symbol only** (S2 annotation, then B consumers)
- **Closes:** ZIG-5, SAF-9, B14 (P0.1 item 13), and the `_MATH_BUILTIN_MAP` part of ZIG-36.
- **Files:**
  - `a7/passes/name_resolution.py`: annotate an IDENTIFIER that is a call's callee or field-access root with `resolved_module_path` only when the scoped lookup finds a MODULE symbol.
  - `a7/ast_preprocessor.py` `_resolve_stdlib_call`: drop the `or obj.name` fallback at 209 and delete the bare-builtin branch at 215-220. Probe p071 shows `sqrt_f64` never resolves anyway.
  - `a7/backends/zig.py`: `_scan_features` 144-149, `_is_io_call` 2154-2167 and `_emit_call` 1618-1645 read only `stdlib_canonical`. Delete `_MATH_BUILTIN_MAP` and the `startswith('math.')` text path.
- **Class:** C.
- **Tests:**
  - RT p077b: expect `show called with direct` then `show called with through g`.
  - RT f07: user `abs_f64(-1.0)` prints `99`.
  - RT B14: a local struct `math` prints `4.5 4.5`.
  - Controls: `io.println`, `math.sqrt` and an aliased `console :: import "std/io"` still work.

**C3. Backend expression and output miscompiles** (B; ZIG-6 lives in a non-folding preprocessor function)
- **Closes:** ZIG-2, ZIG-39, ZIG-6.
- **Approach:**
  - `_emit_if_expr` (`zig.py:1797-1802`) returns `(if (c) a else b)`.
  - The preamble at `zig.py:162` uses `writerStreaming`. `File.writer` defaults to positional mode, so each call writes from offset 0 (`lib/std/Io/File.zig:600`, `File/Writer.zig:13`); `writerStreaming` is at `File.zig:607`. Flushing on every call stays as it is; buffering remains P8.
  - `_normalize_struct_init` (238-269) sorts named field initializers into declaration order when every name is a known field with no duplicates. SPEC A.1 "Evaluation Order" item 4 is `docs/SPEC.md:2066`.
- **Class:** C. If the controller reads A.1 item 4 as storage order rather than evaluation order, ZIG-6 moves to P-BK.
- **Tests:**
  - RT p001b expects `11 12\n3 6\n`; also p109b and p109e.
  - Writer: run a three-`println` program with stdout redirected to a regular file and expect all three lines; repeat with a pipe.
  - RT p003 expects `eval 1\neval 2\na 1 2\neval 3\neval 4\nb 3 4\n`.

**C4. Safety precursors** (S1, `safety.py`)
- **Closes:** SAF-25, SAF-24, SAF-20, SAF-21, SAF-22.
- **Approach:**
  - DEFER (379-386): visit the deferred statement on a snapshot and restore it afterwards. Record names assigned in deferred code and drop their facts at the enclosing block's exit.
  - FOR_IN (364-371): the iterator gets the element type's default fact.
  - Nested FUNCTION statements are visited with a fresh fact state.
  - `_visit_program` first builds a table of `::` constant facts that every function starts from.
  - Obligations get correct error categories (561, 568, 577, 625). The span falls back from `node.span` to the right operand, then to the statement.
- **Class:** B (SAF-24, SAF-25), A (SAF-20, SAF-22), D (SAF-21; Lane D adds the defect row).
- **Tests:**
  - Soundness pair: p18 rejected, with a twin that assigns before dividing accepted.
  - For-in iterator pair, built after Z1.
  - `N :: 4; 10 / N` prints `2` (RT).
  - `a / b` in a nested function gives exit 6 with a line, not exit 7.
  - JSON diagnostic carries a category and line.
- **Dependency:** apply before the Z1 and Z4 patches.

**T0. Compound-assignment checks** (S2): TYP-05. Read `node.operator` at `type_checker.py:862`, and also check the right operand. Class B. Tests: b34, c35 and c36 give exit 6 with "requires numeric" or "requires integer"; c37 gets a numeric message instead of the divisor message.

**V1. Recursion search in linear time** (S3): TYP-03. Replace `_find_recursion_path` (`semantic_validator.py:534-544`) with an iterative Tarjan SCC, one diagnostic per SCC or self-loop, keeping the "Cycle: f -> g -> f" text. Class A. Tests: generated `layers_24` (200 lines) finishes in under 10 s with exit 0; existing recursion rejection messages unchanged.

### Wave 1b: no-approval batches, serialized per file

**S2, `type_checker.py`, in order:**

**T1. `NilType`**
- **Closes:** TYP-10 accepted cases (b28, u04, u09, u13, u15) and the TYP-22 nil wording in u10 and u12.
- **Approach:** `visit_literal` (1175) returns `NilType`, which is assignable only to `ReferenceType`. The `p02` rebinding question goes to P-TYP.4.
- **Class:** B.
- **Tests:** each probe gives exit 6 with a message naming `nil`. Controls: `r: ref i32 = nil`, `if r != nil`, and examples 013, 019 and 025 unchanged.

**T2. Globals typed first; unknown type as an error sink**
- **Closes:**
  - TYP-01: v01, v02, v10, v14, v15, p08 and s01-s03 are class B; v17 is class C; v19 goes to P-TYP.1.
  - TYP-16 (D), TYP-12 (B), ZIG-31 (A), TYP-22 duplicates (u08, f22).
- **Approach:**
  1. Register nominal type names before filling fields (`register_type_decl`, 174-176). Field access looks up the current definition by name, so `ref Node` works.
  2. Type file-scope `CONST` and `VAR` in dependency order before any function body. A cycle is an error.
  3. A local is visible only after its declaration statement; lookup continues outward.
  4. `UnknownType.is_assignable_to` (`types.py:520-522`) returns False, and `_is_numeric_compatible` and `_types_are_comparable` (3021-3033) reject unknown types. Cascades are suppressed through a set of nodes that already have errors.
  5. `[]` needs a type from context or an error.
- **Class:** B or C, except v19.
- **Compatibility scan:** run the Part E corpus harness pattern (`tmp/repro2/scan/`) with the change. Any newly rejected program that builds today escalates into P-TYP.1.
- **Tests:**
  - RT v17 prints `hello`.
  - Rejected probes give exit 6 with a line.
  - v04, v05, v06, v08, v09 and v11 are accepted.
  - RT: a stack-node linked list walked through `ref Node` fields prints a hand-computed sum (no `new` or `del`, so run-allowed).
  - a29, a30, p12, a28, u01, a33, u07 and p064 give exit 6.

**T3. Operator and literal typing, only the rows Zig already rejects**
- **Closes:**
  - TYP-06 rows: c07, c09, c10, c13, c24, c11, c48; c47 is class D.
  - TYP-07 rows: b01-b03, c40, b04, a02, c43. The interim rule allows implicit int to float only where Zig accepts it at run time; P4 decides the full rule.
  - TYP-09, TYP-19, TYP-20 (a15, a16 and a18 class B; p05 class D).
  - ZIG-21 typing (`-x` on u32 rejected), SAF-14 diagnostic, SAF-13 literal shift width.
- **Class:** B or D.
- **Tests:**
  - Each probe gives exit 6 with its message.
  - RT controls a03-a08, c38, c41, c42, c45 and c46 print `5 5 5 5 1.5 1.5`, `4`, `300`, `3`, `-4`, `2` as today.
  - This batch also owns the cast-matrix replacement (section 7).

**T4. Aggregate literals and array types**
- **Closes:**
  - TYP-11: d01-d06, a31 and a32 are class B; h01 is class D.
  - TYP-17: e01, e02 and d42 are class B; d43 and d44 are class D.
  - TYP-08: array to slice, class D, allowed for call arguments and same-scope locals. SPEC A.4 limits lifetime; returned slices stay under P0b.5.
- **B follow-up:** emit `arr[0..]` at the coercion.
- **Tests:** probes give exit 6; RT a10 prints the first element; RT d43 prints the array.

**T5. Lvalue roots**
- **Closes:** TYP-14 (f13-f17, B) and TYP-15 (p03 and p04 B; f07, f08 and f12 are known B7 and B8, P0.1 item 11).
- **Approach:** walk the lvalue to its root. Implicit `ref` (1392-1395) requires an identical referent type and a mutable, non-rvalue root.
- **Tests:** probes give exit 6; RT `bump` in `037` unchanged.

**T6. Match typing**
- **Closes:**
  - TYP-13: d13, d19, d20, d21, d16, d17, d18, d10, p09 and p17 are class B; e03 is class D.
  - ZIG-12.
  - The TYP-30 `p01` part: a pattern name is looked up only among names declared before the match.
- **Approach:** range endpoints use `const_eval` from C1 in place of the Python `//` at 2317-2322.
- **Tests:** probes give exit 6; RT e03 prints the matched branch.

**T8. Diagnostics and scope matching**
- **Closes:** TYP-21 (operand-span fallback, `got_type`), the remaining TYP-22 items (f04, d25, e16, e17), and TYP-29 (per-parent dict of child scopes, replacing the rebuilt list at 147).
- **Class:** A.
- **Tests:** JSON diagnostics for b40, b38 and a22 have line and column; message texts asserted; 8000 sibling blocks type-check in under 0.3 s (loose bound).

**TYP-26. Dead generic code (S2):** delete `GenericMonomorphizer` and the unused helpers in `generics.py` (`generics.py:224-225` are broken). Class A. Do it before Wave 3 so the IR work cannot build on them.

**S3, `semantic_validator.py`:**
- **V2. False rejections.** TYP-24: d14 and d15 (a capture counts as a wildcard at 1342-1346), f05 `while true { ret 1 }`, f24 match with `fall`, and r15 alias scope. Class D. Each is an RT test with its expected output.
- **V3. Defer, labels and `main`.** TYP-23: f26, f27 and f35. ZIG-15: p032, `main` returning `i32` or taking parameters, rejected with a message. Class B. Tests: exit 6.

**B, `zig.py`, serialized after C3:**

**Z1. Names**
- **Closes:**
  - B10, B12 and B9 (P0.1 items 5, 7, 8), B15 p062.
  - ZIG-17, ZIG-18 (`@"name"` at declarations and uses, including fields and `.@"x" =` in struct literals), ZIG-19 (rename user names that collide with `std`, `allocator` or `__a7_*`), ZIG-23 (emit a label only when it is targeted), ZIG-25, SAF-19 (seed `all_emitted` with global names).
- **Existing Lane B items:** 1, 3 and 4.
- **Dependency:** after C4.
- **Tests:** the 3 failing baseline native tests pass; RT per probe.

**Z2. Usage and mutation keyed by declaration**
- **Closes:** ZIG-13 (= SAF-18), ZIG-14, SAF-15, SAF-16 (the parameter part), SAF-17.
- **Approach:**
  - A scope-aware walk, reusing `_resolve_shadowing`'s scope stack, maps each use to its declaring node and sets `is_used` and `is_mutable` on that node.
  - `zig.py:409` and `:652` read the node flags instead of `_mutated_vars`.
  - `_visit_const` (628-637) emits a discard for an unused local constant.
  - `_infer_from_value` takes the type from `type_map`.
- **Class:** B.
- **Tests:** RT p029, p030, f08, f09, f10 and f12; example goldens unchanged.

**Z3. Literal emission**
- **Closes:** ZIG-10 (escape every byte below 0x20, and 0x7f, in char literals at 1491-1496), ZIG-11 literal `1e999` (emit `std.math.inf(f64)`, L16), ZIG-20 (enum tag type wide enough for its values), ZIG-21 lowering (`~@as(i32, 5)`).
- **Class:** B.
- **Tests:** RT per probe.

**Z4. Statement lowering**
- **Closes:**
  - ZIG-9: C-style `for` updates go through the assignment helper, with approval and implicit dereference. The approval call is an S-owned hunk (execution.md:53).
  - B11 (P0.1 item 6, including p084) and B13 (P0.1 item 9).
  - ZIG-16 (`defer _ = f();`), ZIG-22 (float `x %= y` lowers to `x = @rem(x, y)`, matching the binary `%` at 1583), and the `<<=` missing-cast half of ZIG-7.
- **Dependency:** after C4.
- **Tests:** RT p034 variant, p084, p033 and p047b; `<<=` with a literal amount.

**Z5, Z6, Z7:**
- **Z5, codegen-stage rejections:** ZIG-30, where `d := a + b` on arrays uses the `ArrayType` from `type_map` at 663. Class A; RT prints the sums.
- **Z6, zig fmt:** ZIG-35. `_visit_block` writes indentation, and the `fall` and capture-match output is fixed. Class A. `zig fmt --check` runs on every runtime-test output.
- **Z7, dead code and fail-closed defaults:** ZIG-36 (`base.py` `write` and `generic_visit`, `_declare_var_in_scope`, `_emit_binary`, and the `void` generic return at 484-486 becoming a `CodegenError`, Lane B item 8). ZIG-38: the `"undefined"` fallbacks at 1801, 1818, 1825 and 1863 become `CodegenError`. Class A.

**Z8. Backend test helper:** ZIG-37. `compile_a7_to_zig` in `test/test_codegen_zig.py` runs `SemanticValidationPass` and `SafetyProofPass` in `compile.py` order, and pattern tests use `zig build-obj -fno-emit-bin` instead of substring checks. Test-only.

### Wave 1c: safety soundness (S1, after P0b revision 3 is approved)

Order: SD, SA, SB, SC, SE. SD goes first because it closes the null writes.

**SD. Fact sources**
- **Closes:** SAF-1, SAF-2, SAF-5, SAF-11.
- **Approach:**
  - SAF-1: new obligation `REF_ARG_NON_NIL`. At each CALL, for a `ReferenceType` parameter not listed in `implicit_ref_args`, the argument's fact must be non-nil. A `nil` literal is rejected. The callee keeps assuming its parameters are non-nil, which is now sound because every call site is checked, including calls through function values (from the function value's type).
  - SAF-2: delete `safety.py:434-435`.
  - SAF-5: delete 505-506 and 517-518.
  - SAF-11: an interval that falls outside the result type's range is dropped.
- **Tests:** soundness pairs.
  - p08 and p08b rejected; `x: i32 = 0; set_one(x)` accepted and RT.
  - p19 rejected; the twin `p := o.ptr; if p != nil { p.value = 7 }` accepted (unverified until run).
  - p05 rejected; `if c != 0 { 100 / c }` accepted.
  - p17b rejected; the small-value twin accepted.

**SA. Join engine on an explicit stack**
- **Closes:** P0b.1 (S1), P0b.4 (R7), SAF-3, SAF-4, SAF-23, and the block-exit follow-through of SAF-25.
- **Approach:** port `analyze_e.py:137-323` with the three corrections from section 2; `abrupt()` becomes iterative.
- **Tests:**
  - P0b.1, P0b.4, p01, p02, p03 and the `fall` case rejected; guarded twins accepted.
  - Deep statements at recursion limit 100: depth 60 or more with assignments, if/else, while/break, match/fall and defer.

**SB. Call invalidation**
- **Closes:** P0b.3 (S3), SAF-6.
- **Approach:** at every call, drop facts of locals ever passed by `ref` in the function, and of file-scope `VAR`s. Calls resolved as stdlib calls through the C2 annotation are exempt.
- **Tests:** P0b.3 and p07 rejected; twins with `if g != 0` after the call accepted; the ref-escape case from execution.md 3.2.

**SC. Loop fixpoint (P0b.2 option c)**
- **Closes:** S2 and E8 (p20).
- **Approach:** port `analyze_e.py:197-231, 369-422`: widening after 3 header visits, bounds from `i < N` and `i < xs.len`, `break` states joined into the loop exit, `continue` states into the header.
- **Tests:**
  - The `while i < 10` overrun on a 5-element array, a zero divisor reaching the header through `continue`, and p20 all rejected.
  - `for i := cast(usize, 0); i < 5; i += 1 { arr[i] }` and `029_sorting`'s nested loop accepted.
  - The two example edits (026, 030) shown to the user first, per P0b.

**SE. `del` tracking**
- **Closes:** P0b.5 to P0b.8, SAF-8, and S7 (p21).
- **Approach:** moved state is keyed by access-path text (`h.child`). Assigning to the path or a prefix clears it. Joins OR the moved flags, including across loop iterations.
- **Tests:** pairs from P0b.5-8 and p16; `test/test_cast_safety_matrix.py:280` (delete, reassign, delete) stays accepted.

### Wave 2, after node identity (2.1)

- **R. Recursion limits**
  - **Closes:** TYP-18 (type checker and validator explicit stacks, execution 2.2) and ZIG-32. Backend statement recursion is allowed by `CLAUDE.md`; the RecursionError becomes a "nesting too deep" `CodegenError` with a span (class A) until the IR emitter replaces the visitor.
  - **Tests:** `test/test_iterative_traversal.py` at depth 60 or more at limit 100 for the type checker, validator and safety; at default limit, a 400-term `+` chain and a 1000-term `and` chain succeed; a 400-constant chain used as a match range endpoint succeeds; 400 nested blocks give a documented exit code and message.
- **T7. Generics, no-approval parts**
  - **Closes:**
    - TYP-04: g03, g04, g06, g10 and u05 are class B; g02, e30, e12, e14, e21, e24 and e28 are class D, since SPEC 7.1 and the D3 docs defect row cover them; the e11 message is class A.
    - TYP-25: e19 and g08 are class B; e20 and p06 are class D.
    - ZIG-29 (D) and TYP-28 (A).
  - **Approach:** check each instantiation's body with the mapping applied, in a separate type table keyed by `node_id`. The body's generic types are not overwritten, because the backend emits a comptime `T`. Collect every binding and report conflicts, which feeds P-TYP.3.
  - **Tests:** g02 and e30 RT with hand-derived output; g03 and g04 give exit 6 naming the call site.
- **Dead state.** TYP-27: `_nonnegative_vars` is already scheduled for deletion in 2.2; also remove the `pass` check at 617-621, `classify_cast` imported but unused, the validator no-ops and `validate_nil_usage`. Class A.
- **Approved packets implemented.** P-TYP items in S2 and S3, P-BK items in B, P4 rows after P3, P5 additions.

## 5. Waves and lanes

| Wave | S1 (safety, folding) | S2 (type checker, types, name resolution) | S3 (validator) | B (backend) |
| --- | --- | --- | --- | --- |
| 1a | C1, then C4 | T0, then C2 annotation | V1 | C3, then C2 consumers after the S2 hunk lands |
| 1b | idle, or measure packet scans | T1, T2, T3, T4, T5, T6, T8, TYP-26 | V2, V3 | Z1 (after C4), Z2, Z3, Z4 (after C4), Z5, Z6, Z7, Z8, then the T4 slice follow-up |
| 1c | SD, SA, SB, SC, SE (after P0b rev 3) | cast-matrix and illusion-test replacements | none | none |
| 2 | Wave 2.1 node identity, serial with every lane paused; then R (safety part is done by SA) | R, T7, P-TYP implementation | R, P-TYP.2 | P-BK implementation, Z-follow-ups for P4 and P5 |
| 3 | IR engine takes `test/soundness/` as its acceptance suite; P7 shadow diff | none | none | IR emitter |

- **Patch order within a wave:** C4 before Z1 and Z4, as noted above. Otherwise execution.md's F, S, B, H, E, D order.
- **Concurrency:** at most 3 Zig builders (S1, S2 and B verifiers alternate), 6 agents machine-wide.
- **GLM security reviews:**
  - C1 (approval identity).
  - C2.
  - SD, SA, SB, SC and SE as one soundness group.
  - T5 (implicit `ref`).

## 6. Approval packets

Each item lists the program today, the proposal, and the compatibility scan to run: the Part E harness in `tmp/repro2/scan/` extended with the rule over 2440 programs. **Programs affected is unmeasured for every new item.**

### Safety: P0b revision 3 (P0b.1-9 unchanged, plus this addendum; recommend P0b.2 option (c))

```a7
// P0b.10 (SAF-1). Current: accepted; emits v.?.* = 1 on null (Debug panic, ReleaseFast UB).
set_one :: fn(v: ref i32) { v = 1 }
main :: fn() { set_one(nil) }
// Proposed: rejected, "argument for ref parameter 'v' may be nil". set_one(x) with x: i32 stays accepted.
```
```a7
// P0b.11 (SAF-2). Current: accepted because the field is named ptr; with field name link it is rejected (p06c).
Inner :: struct { value: i32 }
Outer :: struct { ptr: ref Inner }
main :: fn() { o := Outer{ptr: nil}; o.ptr.value = 7 }
// Proposed: rejected like any other field name.
```
```a7
// P0b.12 (SAF-3, extends P0b.1). Current: accepted; x = 5 in case 1 is believed in case 2 and after the match.
main :: fn() {
    x := 0
    k := 2
    match k {
        case 1: x = 5
        else: io.println("other")
    }
    y := 10 / x
}
// Proposed: rejected; each case starts from the state before the match, fall passes its state on, cases are joined afterwards.
```
```a7
// P0b.13 (SAF-4). Current: accepted; after the if, v is believed non-zero although the else branch set it to 0.
f :: fn(x: i32) i32 {
    v := x
    if v == 0 { ret 0 } else { v = 0 }
    ret 10 / v
}
// Proposed: rejected.
```
```a7
// P0b.14 (SAF-5). Current: accepted; a / b is believed non-zero, but 1 / 2 is 0.
f :: fn(a: i32, b: i32) i32 {
    if a != 0 { if b != 0 { c := a / b; ret 100 / c } }
    ret 0
}
// Proposed: rejected; the guarded twin `if c != 0 { ret 100 / c }` is accepted.
```
```a7
// P0b.15 (SAF-6). Current: accepted; zero_g() sets g to 0.
g: i32 = 5
zero_g :: fn() { g = 0 }
main :: fn() { g = 5; zero_g(); y := 10 / g }
// Proposed: rejected; any call to a non-stdlib function drops facts about file-scope variables.
```
```a7
// P0b.16 (SAF-8, extends P0b.6). Current: accepted; emits two destroys.
Box :: struct { v: i32 }
Holder :: struct { child: ref Box }
main :: fn() { h := Holder{child: new Box}; del h.child; del h.child }
// Proposed: rejected.
```
```a7
// P0b.17 (SAF-11). Current: accepted; 65536 * 65536 overflows i32 (Debug panic, ReleaseFast UB) but is "proven" non-zero.
main :: fn() { a: i32 = 1; a = 65536; b := a * a; y := 10 / b }
// Proposed: rejected; a range outside the type is dropped.
```

### Types: P-TYP (new)

```a7
// P-TYP.1 (TYP-01). Current: accepted, builds, prints 2. Declared before use, it is rejected (a44).
show :: fn() { n: i32 = RATE; io.println("{}", n) }
RATE :: 2.0
main :: fn() { show() }
// Proposed: rejected like the declared-first form. (v17, the string-printing variant, is fixed without approval: it prints "hello".)
```
```a7
// P-TYP.2 (TYP-02). Current: accepted and builds; recursion through an alias chain.
f :: fn(n: i32) i32 { if n <= 0 { ret 0 }; a := f; b := a; ret b(n - 1) }
// Proposed: rejected. Any call through a function value gets call-graph edges to every top-level
// function with a compatible signature whose value is taken (G4 option b mechanics). Also covers
// r02, r03, r06, r12, r13, m02, r05, r10. G4 itself stays open for P14. 022 and 037 must stay accepted (scan).
```
```a7
// P-TYP.3 (TYP-04 g05). Current: accepted; $T silently becomes f64 and prints 3.5.
add($T) :: fn(a: $T, b: $T) $T { ret a + b }
main :: fn() { x: i32 = 1; y: f64 = 2.5; io.println("{}", add(x, y)) }
// Proposed: rejected, "$T inferred as i32 from argument 1 and f64 from argument 2".
```
```a7
// P-TYP.4 (TYP-10 p02). Current: rejected, "expected 'i32', got 'unknown type'".
main :: fn() { r: ref i32 = nil; r = nil }
// Options: (a) keep rejected with a clear message; (b) accept as rebinding to nil. Recommendation: (a) until memory gates M3 and M4.
```

### Backend: P-BK (new)

```a7
// P-BK.1 (ZIG-3). Current: untyped immutable locals are emitted as Zig comptime values.
// Prints "0.30000000000000000000000000000000004 0.30000000000000004".
a := 0.1
b := 0.2
typed_a: f64 = 0.1
typed_b: f64 = 0.2
io.println("{} {}", a + b, typed_a + typed_b)
// Proposed: emit the A7 type (const a: f64). Prints "0.30000000000000004 0.30000000000000004".
// Integer half: x := 2147483647; y := x + 1 prints 2148483648 today; with i32 typing it
// becomes a Zig error, so it is decided after P3 (wrap to -2147483648 under L5).
```
SPEC does not state the default types of untyped literals (`docs/SPEC.md:136-160, 418-420`), so this cannot be class C. Goldens with float `:=` locals (`030_calculator.a7:95-96`, `019_literals.a7:9`) must be re-run first. Any golden change goes into this item (unverified; `030` passes values through function parameters).

```a7
// P-BK.2 (ZIG-33). Current: prints "a {{b}} 5", while the type checker counts {{ as an escape (type_checker.py:1516-1520).
io.println("a {{b}} {}", 5)
// Options: (a) {{ is an escape and prints "a {b} 5"; (b) literal braces, with the checker fixed. SPEC has no rule. Recommendation: (a).
```

### Rows added to existing packets

- **P4 (G3):**
  - TYP-06 mixed operands that build (c41: `c: u32 = a + b`, `a: u8`, prints 300; proposed: same-type operands or an approved widening).
  - TYP-07 implicit integer widening and int to float that build (a03-a08).
  - ZIG-7 plus TYP-06 c14 runtime shift count: `x << n` with runtime `n` builds, panics in Debug and is UB in ReleaseFast; proposed: a shift-count obligation.
- **P5:** ZIG-8 inactive union field reads through a parameter (p056b untagged, p057b tagged: build, Debug panic, ReleaseFast UB; proposed: rejected until G5). TYP-30 `d23` joins the A-32 row.
- **P2 (tokenizer planner):** ZIG-4. `"\xff\x80A"` iterates 5 bytes today. SPEC D.1 (`:2170`) and B.1 (`:2110`) say `\xHH` is ASCII only, so the proposal is a tokenizer rejection; the backend emits bytes only if P2 accepts them.

## 7. Replacing coverage-illusion tests

- **The 31 tests ending in `assert isinstance(result, bool)`** (listed in `tmp/audit/compiler/types/illusion.txt`):
  - Each is replaced by an assertion of the specific result that SPEC implies.
  - Every "valid" program also gets `zig build-obj -fno-emit-bin`.
  - Where SPEC and the current result disagree, the case goes to triage, not into the assertion.
  - Owners:
    - `test_semantic_generics.py` (9): T7.
    - `test_semantic_errors.py` (13): T8.
    - `test_semantic_functions.py:179, 195, 269, 679`: T2 and V2.
    - `test_semantic_expressions.py:275, 416, 497`: T3.
    - `test_semantic_types.py:196`: T4.
    - `test_semantic_control_flow.py:1282, 1306`: V2. `:1269-1282`, `defer del` on an `i32`, expects an exact rejection.
- **Cast matrix (T3).**
  - `test_cast_safety_matrix.py:110-115`: `expected` comes from a literal 15×15 table in the test file, written from the rules prose (the Phase 1 hybrid boundary in `cast_classifier.py` and G3). Cells that SPEC does not settle, the D.024 against D.038 contradiction, are marked and listed. `expected_without_proof` (80-83) reads that table.
  - Delete `:131-138` (determinism) and `:141-146` (`allowed` equals its own definition).
  - Add RT boundary casts: u32 to i64 of 4294967295, i8 to i16 of -128, f32 to f64 of 1.5, i32 to u8 of 200 under a guard.
- **Other tests.**
  - `test_semantic_analysis.py:207-226, 254-282, 284-308` (T8) assert specific symbols and errors.
  - `test_function_returning_function` (T2) asserts the exact nested-function rejection.
  - `test_iterative_traversal.py` depths move to batch R.
  - The backend helper and substring tests go to Z8.
  - `test/test_parser_examples.py` `assert True` belongs to the other planner and Lane H.

## 8. Deferrals

| Finding | Deferred to | Reason |
| --- | --- | --- |
| ZIG-27 (m1 private module call not prefixed) | Module redesign (PIP-6) | The module system is being redesigned separately |
| ZIG-40, SAF-16 inner-function part (nested functions uncallable, p083, p10) | Packet with the module and scoping redesign | Whether nested functions are a feature is undecided; C4 already makes their failures exit 6 instead of 7 |
| ZIG-34 (slices print as bytes, enums as `.Green`, `1e300` as 301 digits) | P10 (G5 strings and printing) | Changes output of programs that build; SPEC has no print-format rule |
| ZIG-38 overflow approvals, SAF KNOWN P3 (`_prove_integer_overflow` unreachable) | P3 (L5) | Wrapping semantics are decided there |
| ZIG-24 (uninitialized `[2]string`) | P5 (the existing `pts: [3]Pt` row, B4 family) | Already a packet item |
| TYP-07 32-bit `isize` assumption | G9 platforms | Inference only; no 32-bit target today |
| TYP-31 | No action | Parser F2 family (other planner); `math.max(u8, i32)` works |
| TYP-32 | Existing items: B2 to P5 and G5; B3 to P0.1 item 11 and P0b.9; S12 to P0.1 item 16; S11 to track 5; B7 and B8 to T5; MS-7 to P-TYP.2; G3 to P4 | Already scheduled |
| Track 5 precision: field-path guards, per-path use-after-`del`, slice/string parameter indexing, `p23` index bounds | Wave 4 on the IR | Needs places and a CFG (section 2) |

## 9. Coverage table

| ID | Batch | ID | Batch | ID | Batch |
| --- | --- | --- | --- | --- | --- |
| TYP-01 | T2 + P-TYP.1 | ZIG-1 | C1 | SAF-1 | SD, P0b.10 |
| TYP-02 | P-TYP.2 | ZIG-2 | C3 | SAF-2 | SD, P0b.11 |
| TYP-03 | V1 | ZIG-3 | P-BK.1 | SAF-3 | SA, P0b.12 |
| TYP-04 | T7 + P-TYP.3 | ZIG-4 | P2 | SAF-4 | SA, P0b.13 |
| TYP-05 | T0 | ZIG-5 | C2 | SAF-5 | SD, P0b.14 |
| TYP-06 | T3 + P4 | ZIG-6 | C3 | SAF-6 | SB, P0b.15 |
| TYP-07 | T3 + P4 (32-bit part deferred) | ZIG-7 | Z4 (`<<=`) + P4 | SAF-7 | C1 |
| TYP-08 | T4 | ZIG-8 | P5 | SAF-8 | SE, P0b.16 |
| TYP-09 | T3 | ZIG-9 | Z4 | SAF-9 | C2 |
| TYP-10 | T1 + P-TYP.4 | ZIG-10 | Z3 | SAF-10 | C1 |
| TYP-11 | T4 | ZIG-11 | C1 + Z3 | SAF-11 | SD, P0b.17 |
| TYP-12 | T2 | ZIG-12 | T6 | SAF-12 | C1 |
| TYP-13 | T6 | ZIG-13 | Z2 | SAF-13 | C1 + T3 |
| TYP-14 | T5 | ZIG-14 | Z2 | SAF-14 | C1 + T3 |
| TYP-15 | T5 | ZIG-15 | V3 | SAF-15 | Z2 |
| TYP-16 | T2 | ZIG-16 | Z4 | SAF-16 | Z2 + deferral |
| TYP-17 | T4 | ZIG-17 | Z1 | SAF-17 | Z2 |
| TYP-18 | R | ZIG-18 | Z1 | SAF-18 | Z2 |
| TYP-19 | T3 | ZIG-19 | Z1 | SAF-19 | Z1 |
| TYP-20 | T3 | ZIG-20 | Z3 | SAF-20 | C4 |
| TYP-21 | T8 | ZIG-21 | T3 + Z3 | SAF-21 | C4 |
| TYP-22 | T1, T2, T8 | ZIG-22 | Z4 | SAF-22 | C4 |
| TYP-23 | V3 | ZIG-23 | Z1 | SAF-23 | SA |
| TYP-24 | V2 | ZIG-24 | Deferral (P5) | SAF-24 | C4 |
| TYP-25 | T7 | ZIG-25 | Z1 | SAF-25 (new, p18) | C4 |
| TYP-26 | S2 cleanup | ZIG-26 | T8 (count placeholders the way the emitter does) | KNOWN S1, S2, S3, R7 | SA, SC, SB, SA |
| TYP-27 | Wave 2 dead state | ZIG-27 | Deferral (modules) | KNOWN S7 (p21), E8 (p20) | SE, SC |
| TYP-28 | T7 | ZIG-28 (B11, B9, B15, B6, B10) | Z4, Z1, Z1, P0.1 item 11 (S2), Z1 | KNOWN P5 (p22) | P5 |
| TYP-29 | T8 | ZIG-29 | T7 | KNOWN P3 | Deferral (P3) |
| TYP-30 | T6 + P5 | ZIG-30 | Z5 | PIP-2, PIP-3 | C2 (shared) |
| TYP-31 | Deferral (no action) | ZIG-31 | T2 | | |
| TYP-32 | Deferral (existing items) | ZIG-32 | R | | |
| | | ZIG-33 | P-BK.2 | | |
| | | ZIG-34 | Deferral (P10) | | |
| | | ZIG-35 | Z6 | | |
| | | ZIG-36 | C2 + Z7 | | |
| | | ZIG-37 | Z8 | | |
| | | ZIG-38 | Z7 + deferral (P3) | | |
| | | ZIG-39 | C3 | | |
| | | ZIG-40 | Deferral (nested functions) | | |

## 10. Verification

- **Per batch:**
  1. Before implementing, the verifier writes expected results for each probe the batch cites: A7 exit code, `zig build-obj` exit code, and for run-allowed probes the Debug and ReleaseFast output.
  2. Re-run `tmp/audit/compiler/{types,backend}/run.py` and `tmp/audit/compiler/safety/run.sh` in the worktree and diff against those expectations.
  3. Try one counterexample: the unsafe variant stays rejected, or a changed input changes the output.
  4. Never run compile-only probes.
- **Against the baseline** (`docs/audits/2026-09-16/baseline.md`):
  - Parser 503, semantic 351, backend 332, examples 43/43, Debug 43/43, Release 43/43 and the error-stage matrix 61/61 must not drop.
  - Full pytest failures must fall from 12. C1 closes `test_large_integer_folding_preserves_exact_quotient_and_remainder`; Z1 closes the three `test_valid_a7_bindings_build_with_zig` cases. The remaining 8 belong to Lane F (other planner).
  - Any example golden, test or doc snippet that changes under a no-approval batch escalates under P0.1's rule.
  - The error-stage matrix count must be derived (H9) before T and V batches change exit codes.
- **Soundness groups (SD to SE, C4):** each rejected program has an accepted guarded twin that builds Debug and ReleaseFast; the GLM security review runs before the patch is applied; the Part E scan is re-run on the final code, and its counts must match the numbers stated in the packet.

## 11. Unverified

- The backend MEDIUM and LOW counts, and whether ZIG-10 to ZIG-40 match the auditor's intended split; the report was never written.
- ZIG-3's effect on goldens.
- The P-TYP.2 scan result for examples 022 and 037.
- The SD twin `p := o.ptr; if p != nil { p.value = 7 }` being accepted.
- The C1 inference that no node created after the safety pass needs an approval.
- SAF-25 comes from `tmp/audit/compiler/safety/results.txt` (p18 exit 0) and its `.zigerr` (masked by B11), not from the auditor's findings list.
- `writerStreaming` fixing redirected output is read from `lib/std/Io/File.zig:600-607` and `File/Writer.zig:13`, not run.

### Critical Files for Implementation
- /home/cx89/Projects/pl-dev/a7-py/a7/safety.py
- /home/cx89/Projects/pl-dev/a7-py/a7/ast_preprocessor.py
- /home/cx89/Projects/pl-dev/a7-py/a7/passes/type_checker.py
- /home/cx89/Projects/pl-dev/a7-py/a7/backends/zig.py
- /home/cx89/Projects/pl-dev/a7-py/tmp/repro2/scan/analyze_e.py (the prototype to port, with the three corrections)
