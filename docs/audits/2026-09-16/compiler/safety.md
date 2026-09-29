> **Source:** Claude audit subagents, full audit of the A7 safety proof pass and AST preprocessor, run against commit `701c679` with Zig 0.16.0; started by one auditor (interrupted by plan mode) and finished by a second from the first's saved state; shared instructions in `tmp/audit/compiler/PROMPT-COMMON.md`.  
> **Date:** 2026-09-16 to 2026-09-17.  
> **Status:** Evidence. Body preserved verbatim. Probes, logs and depth scripts it cites stay under `tmp/audit/compiler/safety/`, which is not tracked.

# SAF audit: safety proof pass and AST preprocessor

Scope read in full: `a7/safety.py` (737 lines), `a7/ast_preprocessor.py` (694 lines),
`a7/cast_classifier.py` (83 lines, as used by the safety pass), their wiring in
`a7/compile.py:346-404`, and `docs/SAFETY_CONTRACT.md`. Related backend lines read where
a finding depends on them: `a7/backends/zig.py:1272-1297` (`_visit_defer`), `:2378-2391`
(`_emit_statement_inline`), `:1479-1483` (float literals), `:1625-1638` (math calls).
Tree: `master` at `701c679` with uncommitted docs and tests; `a7/` unmodified.
Zig 0.16.0. Dates 2026-09-16 and 2026-09-17 (this audit was interrupted once and
resumed; IDs SAF-1 to SAF-25 were assigned before the interruption and are already
cited by `docs/plan/execution.md` and `docs/plan/fix-program/backend-fix-plan.md`, so
they are kept).

Method. Probe sources are in `tmp/audit/compiler/safety/probes/` (first line states
`compile-only` or `run-allowed`). `run.sh <names>` runs
`uv run a7 <probe> --format human --output out/<name>.zig`, then
`zig build-obj -fno-emit-bin` from `out/`, and appends `=== <name>: a7 exit N` to
`results.txt`. Batch logs: `batch1.txt`-`batch8.txt`, `reverify.txt` (second run of every
CRITICAL and HIGH probe), `runs6.txt` and `reverify_runs.txt` (`zig build-exe -ODebug`
and `-OReleaseFast` plus a run, run-allowed probes only). Per-probe compiler output is
`out/<name>.log`, Zig errors `out/<name>.zigerr`. Python-level checks: `idreuse.py`
(node id reuse), `stages.py` and `recur.py` (which stage overflows), `depth/deep_safety.py`
and `depth/helpers_direct.py` (safety pass alone on synthetic ASTs). "a7=N" is the A7
exit code, "zig=N" the `build-obj` exit code. Nothing in the repository was edited.

Known-defect sources checked: `docs/plan/README.md` "Defects reproduced in Wave 0" and
the lists above it, `docs/plan/audit/evidence/2026-09-16-ledger-part2.md`,
`docs/plan/packets/P0b-unsafe-programs.md`. Sibling reports cross-referenced:
`tmp/audit/compiler/parser.md` (PAR), `pipeline.md` (PIP), `types.md` (TYP).

## Summary

| Severity | Findings | NEW | KNOWN or partly KNOWN |
| --- | --- | --- | --- |
| CRITICAL | 12 | 11 | 1 (SAF-10 extends S13) |
| HIGH | 2 | 2 | 0 |
| MEDIUM | 15 | 12 | 3 (SAF-14 G3; SAF-28 D7; SAF-29 G3/P4) |
| LOW | 5 | 5 | 0 |
| KNOWN, re-confirmed only | listed in SAF-KNOWN | 0 | 13 |
| **Total** | **34** | **30** | **4 + 13 re-confirmed** |

Severity rule used: CRITICAL means A7 accepts the program, `zig build-obj` accepts the
emitted Zig, and the program is memory-unsafe, divides by zero, or computes a wrong
result. HIGH means the same unsafety is hidden today only by an unrelated Zig
rejection that is already scheduled to be fixed. MEDIUM covers accepted programs that
Zig rejects in ordinary code, false rejections of documented forms, internal errors,
wrong diagnostics and invariant breaks. LOW covers contrived triggers and dead code.

Severity changes from the interrupted notes: SAF-8, SAF-9 and SAF-10 were HIGH and are
now CRITICAL under the rule above (each builds and runs wrong or unsafe; SAF-9 is the
same root cause as PIP-2, which `pipeline.md` files as CRITICAL). SAF-11 was MEDIUM and
is now CRITICAL (probes p17b, p17c, p30h2 build). SAF-24 was LOW and is now HIGH:
like SAF-25, its unsafe approval is hidden only by a scheduled backend fix (B9
capture shadowing). SAF-25 is HIGH.

The CRITICAL items contradict `docs/SAFETY_CONTRACT.md:40-41`: "If a fact is
invalidated or unknown, the compiler rejects the dependent operation." (P0b cites
this sentence as lines 47-49; in the current file it is at 40-41.)

---

## CRITICAL

### SAF-1 (CRITICAL, NEW): `ref T` parameters are assumed non-nil, and no call site has to prove it

**What is wrong.** On function entry every parameter whose type node is `TYPE_POINTER`
(`ref T`) gets `non_nil=True`; callers are never asked to pass a non-nil value. Passing
`nil` or a nil `ref` local builds, and the callee writes through null.

**Evidence.** `safety.py:291-293`
`self.facts.set_symbol(param.name, self._fact_from_type_node(param.param_type))`;
`:482-483` `if node.kind == NodeKind.TYPE_POINTER: return ValueFact(non_nil=True)`;
the CALL branch `:444-447` only visits arguments. Contract: "the safety pass treats
`new` and `nil` references as maybe nil and requires proof before field access or
dereference" (`SAFETY_CONTRACT.md:77-78`).
- `p08_nil_into_ref_param` (`p: ref i32 = nil; set_one(p)`): a7=0, zig=0, emits
  `fn set_one(v: ?*i32) void { v.?.* = 1; }` and `set_one(p)` with `p = null`.
- `p08b_nil_literal_into_ref_param` (`set_one(nil)`): a7=0, zig=0.
Both re-run in `reverify.txt` with the same result. Not run (null unwrap).

**Fix direction.** Discharge a REF_NON_NIL obligation per `ref` argument at the call
site, or give parameters `maybe_nil` until the planned `ref`/optional `ref` split.
**Changes an accepted, building program:** yes; count not measured here.

### SAF-2 (CRITICAL, NEW): any field named `ptr` is treated as non-nil

**What is wrong.** A field access whose field name is `ptr` yields `non_nil=True`
regardless of type, so `o.ptr.value` through a nil `ref` field is approved. The rule is
meant for slice `.ptr`.

**Evidence.** `safety.py:434-435` `if node.field == "ptr": fact = ValueFact(non_nil=True)`.
- `p19_ptr_field_on_struct_local` (`o := Outer{ptr: nil}; o.ptr.value = 7`): a7=0, zig=0,
  emits `var o = Outer{ .ptr = null }; o.ptr.?.value = 7;` (`reverify.txt`).
- Control `p06c_field_other_name_control`: identical program with the field named
  `link` is rejected, a7=6, "reference must be proven non-nil before field access
  through it: reference may be nil [line 14: col 10]".
- `p06b` (read instead of write, `o` const) is accepted by A7 and rejected by Zig only
  because Zig evaluates the null unwrap at compile time ("unable to unwrap null").

**Fix direction.** Apply the rule only when the object's type is a slice or string.
**Changes an accepted, building program:** yes; count not measured.

### SAF-3 (CRITICAL, NEW): `match` statements neither scope nor join facts, and `fall` carries state the pass never sees

**What is wrong.** The MATCH branch visits each case in sequence on one shared fact map
with no save, restore or join. An un-braced case assignment leaks into later cases
and past the match. With braced cases each case BLOCK restores its entry facts, so a
`fall` into the next case is analyzed with the pre-match facts instead of the state at
the end of the falling case.

**Evidence.** `safety.py:372-378` (no `copy_symbols`/`restore_symbols`); BLOCK restore
at `:301-306`; there is no FALL handling anywhere in `safety.py`.
- `p01_match_case_leak_between_cases` (`x := 0`, `case 1: x = 5`,
  `case 2: io.println("{}", 10 / x)`, `k := 2`): a7=0, zig=0, emits
  `2 => { ... @divTrunc(10, x) ... }` with `x` still 0 on that path.
- `p02_match_case_leak_after` (`case 1: x = 5` then `y := 10 / x` after the match with
  `k := 2`): a7=0, zig=0.
- `p26_fall_zero_divisor` (`x := 5`, `case 1: { x = 0; fall }`,
  `case 2: { io.println("{}", 10 / x) }`, `k := 1`): a7=0, zig=0. The emitted Zig
  implements the fallthrough correctly (`__a7_match_fall_3 = true; break :__a7_match_case_0_4;`),
  so the division runs with `x == 0`.
All three re-run in `reverify.txt`. Not run.

**Fix direction.** Join the exit states of all case paths (plus the pre-state when there
is no `else`). The hull-join rule in the ledger (`2026-09-16-ledger-part2.md:315`,
"match: the join of every case path") does not say how `fall` is handled: the exit
state of case N must flow into the entry of case N+1.
**Changes an accepted, building program:** yes; count not measured.

### SAF-4 (CRITICAL, NEW): the early-return rule applies the negated guard even when the `else` branch reassigns

**What is wrong.** After `if v == 0 { ret } else { v = 0 }`, the pass adds `v != 0` to
the facts that follow the `if`, although the only path that reaches them just set `v`
to 0.

**Evidence.** `safety.py:663-668` `_learn_after_stmt` checks only that `then_stmt`
always returns, then `self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))`;
the else BLOCK's assignment was discarded by `:301-306`.
`p03_early_return_else_assign`: a7=0, zig=0, emits
`if ((v == 0)) { return 0; } else { v = 0; } return @divTrunc(10, v);`
(`reverify.txt`). INFERENCE: a hull join at the `if` that is then refined by the
early-return fact would stay unsound unless the refinement is applied only to the
fall-through path state.

**Fix direction.** Apply the negated condition to the else-path exit state, not to the
pre-`if` state. **Changes an accepted, building program:** yes; count not measured.

### SAF-5 (CRITICAL, NEW): `a / b` is marked non-zero when both operands are merely non-zero

**What is wrong.** Integer division truncates, so `1 / 2 == 0`, but the pass returns
`nonzero=True` for a quotient of two non-zero operands without intervals.

**Evidence.** `safety.py:504-506` and `:516-518`
`if node.operator == BinaryOp.DIV and left.nonzero and right.nonzero: return ValueFact(nonzero=True)`.
`p05_div_result_nonzero` (`if a != 0 { if b != 0 { c := a / b; ret 100 / c } }`,
called as `f(1, 2)`): a7=0, zig=0, emits `const c = @divTrunc(a, b); return @divTrunc(100, c);`
(`reverify.txt`). With `f(1, 2)` the second division divides by zero. Not run.

**Fix direction.** Remove the rule for integer division (keep it only for floats, if
at all). **Changes an accepted, building program:** yes; count not measured.

### SAF-6 (CRITICAL, NEW): facts about globals survive calls that assign the global

**What is wrong.** A CALL invalidates nothing, so a fact learned about a global before
a call is still used after a callee sets that global to 0.

**Evidence.** CALL branch `safety.py:444-447`; facts are reset only at function entry
(`:290`). `p07_global_changed_by_call` (`g = 5; zero_g(); y := 10 / g` where `zero_g`
does `g = 0`): a7=0, zig=0, emits `g = 5; zero_g(); const y = @divTrunc(10, g);`
(`reverify.txt`). This is the global counterpart of KNOWN S3 (ref-parameter writes),
which P0b.3 covers only for locals passed by `ref`.

**Fix direction.** Drop facts about mutable globals at every call (or at calls whose
callee may write them). **Changes an accepted, building program:** yes; count not
measured.

### SAF-7 (CRITICAL, NEW): folding frees nodes whose ids are then reused, so `type_map` gives new literals the type of an unrelated dead node

**What is wrong.** `type_map` is keyed by `id(node)`. The preprocessor replaces
folded nodes with new `ASTNode` objects after type checking; the replaced subtree is
freed, CPython reuses its address, and the new literal inherits whatever type the dead
node had. The backend then picks format specifiers and division lowering from that
wrong type.

**Evidence.** `ast_preprocessor.py:141-149` (parent slot replaced), new nodes at
`:569-575`, `:580-586`, `:643-649`, `:669-675`, `:686-692`; `compile.py:392-404` passes
the same `type_map` to the backend after `preprocessor.process(ast)`.
`idreuse.txt` (3 runs of `idreuse.py`): "old id=...352 type=f64; new literal
id=...696 value=5 type_map[id(new)]=f64", the same pattern in every run.
- `f17_id_reuse_format_char` (run-allowed; `same := 'a' == 'a'; io.println("{} {}", same, 60 + 5)`):
  a7=0, zig=0, emits `__a7_stdout_print("{} {c}\n", .{ same, 65 });`. Debug and
  ReleaseFast both print `true A` instead of `true 65` (`reverify_runs.txt`).
- `f17b_id_reuse_format_string` (`"a" == "a"`): emits `{s}` for `65`; zig=1
  "invalid format string 's' for type 'comptime_int'".
- `f06_id_reuse_type_confusion`: `a / (2 + 3)` with `a: i32` emits `(a / 5)`; zig=1
  "signed integers must use @divTrunc". Re-run in `reverify.txt`, same output.
Approval lookups are also keyed by `id(node)` (`safety.py:211, 215`). INFERENCE: no
approval is misattached today, because the only nodes created after the safety pass
are LITERAL (`ast_preprocessor.py`) and TYPE_PRIMITIVE (`:419-427`), and neither kind
is looked up in the backend plan. UNVERIFIED as a concrete program.

**Fix direction.** Key side tables by a stable node id assigned at parse time, or copy
the replaced node's `type_map` entry to the new node and keep the replaced subtree
referenced until codegen ends. **Changes an accepted, building program:** yes (f17
output changes from `true A` to `true 65`).

### SAF-8 (CRITICAL, NEW): `del` of a field or other non-identifier is never recorded, so a double free builds

**What is wrong.** `_mark_deleted` handles only identifiers. `del h.child` twice is
accepted and emits two destroy calls on the same pointer.

**Evidence.** `safety.py:724-726`
`if node.kind == NodeKind.IDENTIFIER and node.name: self.moved_symbols.add(node.name)`;
DEL branch `:387-389`. `p16_del_field_twice`: a7=0, zig=0, emits
`if (h.child) |p| allocator.destroy(p);` twice (`reverify.txt`). Not run. Different
from KNOWN P0b.6 (two names for one allocation) and S7 (loop); P0b.6 does not mention
field paths.

**Fix direction.** Track deleted access paths, or reject `del` of non-identifier
expressions until memory gates M3/M4 decide `del`. **Changes an accepted, building
program:** yes; count not measured.

### SAF-9 (CRITICAL, NEW; same root cause as PIP-2): a user function named like a typed math builtin is replaced by the Zig builtin

**What is wrong.** Any call whose bare callee name is in the stdlib builtin table gets
`stdlib_canonical`, without checking that the name resolves to the builtin rather
than a user declaration; the backend then emits `@abs(...)`.

**Evidence.** `ast_preprocessor.py:216-220`
`canonical = self.stdlib.resolve_builtin(func.name)`; `zig.py:1631-1637` emits
`@{short}({args})` for `std.math.*` canonicals. `f07_user_fn_named_builtin`
(run-allowed; `abs_f64 :: fn(x: f64) f64 { ret x + 100.0 }`,
`io.println("{}", abs_f64(-1.0))`): a7=0, zig=0, emits `.{@abs(-1.0)}`; Debug and
ReleaseFast print `1` instead of `99` (`reverify_runs.txt`). Also reported as PIP-2 in
`pipeline.md`; `execution.md:102` batch C2 lists it.

**Fix direction.** Resolve builtins only when name resolution bound the callee to the
builtin symbol. **Changes an accepted, building program:** yes (output).

### SAF-10 (CRITICAL, KNOWN S13 extension): integer `%` folding loses precision above 2^53

**What is wrong.** Folding computes integer `%` through float division, so large
operands give wrong remainders. S13 records `/`; `%` fails the same way.

**Evidence.** `ast_preprocessor.py:623-624`
`result = lval - (int(lval / rval) * rval)`. `f03_fold_int_mod_precision` (run-allowed):
`a: i64 = 18014398509481983 % 2` emits `const a: i64 = -1;`; the unfolded `@rem(n, d)`
prints `1`. Debug and ReleaseFast both print `-1 1` (`reverify_runs.txt`).
`test/test_pipeline_native.py:79` (uncommitted) targets the `/` case.

**Fix direction.** Use integer `//` and `%` with truncation adjustments; never float.
**Changes an accepted, building program:** yes (output).

### SAF-11 (CRITICAL, NEW; interacts with P3/ZIG-38 and L5): intervals are never clamped or wrapped to the operand type, and approvals trust the impossible values

**What is wrong.** `IntegerInterval.add/sub/mul` compute mathematical results with no
reference to the result type, so an `i32` or `u8` expression can carry an interval
outside its type. Casts, divisions and indexes are then approved from those values.

**Evidence.** `safety.py:115-134` (no type), `_binary_fact` `:503-520`, `_cast_fact`
returns the source interval unchanged `:552-553`, `_prove_index` trusts it `:571`.
- `p17b_mul_interval_runtime` (`a: i32 = 1; a = 65536; b := a * a; y := 10 / b`):
  a7=0, zig=0. Interval of `b` is `[4294967296, 4294967296]`, "non-zero"; the i32
  product is 0 after wrapping.
- `p17c_unclamped_interval_index` (`x: u8 = 1; x = 200; y := x + x;
  idx := cast(usize, y) - 395; arr[idx]` on a `[6]i32`): a7=0, zig=0 (`reverify.txt`).
  The pass sees `y` as `[400, 400]` and `idx` as `[5, 5]`, and approves the index. At
  run time `x + x` overflows u8 (Debug trap, ReleaseFast undefined), and if it wraps
  to 144, `144 - 395` underflows `usize` and indexes out of bounds.
- `p30h2_cast_unclamped_interval_runtime` (`x: i32 = 1; x = 2000000000; y := x + x;
  z := cast(u32, y)`): a7=0, zig=0, emits `const z = @as(u32, @intCast(y));`. The
  cast is approved as "range fits u32" for a value that is negative after wrapping.
- `p17` (constant operands) is caught only by Zig's comptime overflow check.
Today the first undefined operation in each program is the unproven overflow itself
(KNOWN: `_prove_integer_overflow` is dead, ZIG-38/P3). Under decision L5 (wrapping),
the overflow becomes defined and the approved division, cast or index is the only
unsafe operation. Not run.

**Fix direction.** Clamp every arithmetic result to the type range, or wrap it and
drop the interval when wrapping is possible; apply the same in `_unary_fact`.
**Changes an accepted, building program:** yes; count not measured.

### SAF-26 (CRITICAL, NEW): an un-braced `else` branch is analyzed without save/restore, so its assignment is kept on the path that skipped it

**What is wrong.** `then_stmt` is visited inside `copy_symbols`/`restore_symbols`;
`else_stmt` is not. A braced else is still restored by its BLOCK, but `} else x = 5`
leaves `x = 5` in the facts after the `if`, although the then path never assigned.
This is the mirror image of P0b.1: P0b.1 describes the pass as restoring what it knew
before a branch, which is not true for an un-braced else.

**Evidence.** `safety.py:335-344`:
`self.facts.restore_symbols(saved)` then `if node.else_stmt: self._visit_stmt(node.else_stmt)`.
- `p33_else_branch_leak` (`x := 0; c := true; if c { ... } else x = 5; 10 / x`):
  a7=0, zig=0, emits `if (c) { ... } else { x = 5; } ... @divTrunc(10, x)`
  (`batch5.txt`, `reverify.txt`). `c` is true, so the division is by zero. Not run.
- `p33b_else_if_unbraced_leak` (the same after an `else if`): a7=0, zig=0.
- Control `p33d_else_braced_control` (`else { x = 5 }`): a7=6 "divisor may be zero"
  (`batch7.txt`), which pins the cause to the missing restore.

**Fix direction.** Visit the else branch under the same save/restore and join both
exits (P0b.1). **Changes an accepted, building program:** yes; count not measured.

---

## HIGH

### SAF-25 (HIGH, NEW; latent CRITICAL behind KNOWN B11): a deferred assignment is applied at the `defer` site

**What is wrong.** For `defer <statement>` other than `del`, the pass visits the
statement immediately, so its effect on facts is applied before the code that runs
before the deferred statement. `x := 0; defer x = 5; y := 10 / x` is approved.

**Evidence (confirmed against the code).** `safety.py:379-384`: when
`node.statement.kind != NodeKind.DEL`, `self._visit_stmt(node.statement)` runs. For an
ASSIGNMENT this reaches `:326-327` `self.facts.set_symbol(node.target.name, rhs)`, so
`x` gets the fact of `5` at the defer site. A braced defer body goes through the BLOCK
branch, which restores (`:301-306`).
- `p18_defer_assign_fact`: a7=0 (accepted); zig=1 only because the backend emits
  `defer void;` ("value of type 'type' ignored", `out/p18_defer_assign_fact.zigerr`).
  The division `const y = @divTrunc(10, x);` with `var x: i32 = 0` is in the output.
  Re-run in `reverify.txt`, same result.
- `p18b_defer_block_assign_fact` (`defer { x = 5 }`): a7=6 "divisor may be zero".
- The same approval happens for `defer x += 5` (`p32b`, a7=0) and for a deferred
  `match` with un-braced case assignments (`p32`, a7=0, via SAF-3). Both emit
  `defer void;`.
The backend emits `defer void;` for every deferred statement that is not a block,
expression statement, call or `del`: `zig.py:1290-1293` writes `defer ` followed by
`self._emit_statement_inline(node.statement)` and `;`, and `_emit_statement_inline`
returns `"void"` for anything else (`zig.py:2391`). That is KNOWN B11. So every defer form
whose safety visit changes facts is rejected by Zig today, and fixing B11 alone turns
p18, p32 and p32b into accepted, building divisions by zero. `execution.md:109` already
orders batch C4 before the B11 fix for this reason.

**Fix direction.** Visit the deferred statement on a snapshot and discard its fact
changes (or apply them at scope exits). **Changes an accepted, building program:** no
(nothing with a deferred assignment builds today).

### SAF-24 (HIGH, NEW; latent CRITICAL behind KNOWN B9 capture shadowing): a for-in value variable keeps the outer variable's fact

**What is wrong.** FOR_IN sets a fact only for `index_var`; the value variable keeps
whatever fact an outer variable with the same name had, so a division by the loop
value is approved from the outer value.

**Evidence.** `safety.py:364-371` (only `node.index_var` is given a fact).
`p04_for_in_value_var_fact` (`v := 5; arr: [3]i32 = [0, 0, 0]; for v in arr
{ y := 10 / v }`): a7=0 (division approved); zig=1 only because the emitted capture
`for (arr) |v|` shadows `const v` ("capture 'v' shadows local constant from outer
scope"). Run twice (`results.txt`, `reverify2.txt`). The capture-shadowing
fix is scheduled in batch Z1 (`execution.md:120`), and `execution.md:109` names
SAF-24 with SAF-25 as holes that the backend fixes would expose.

**Fix direction.** Give the value variable a fresh fact (unknown, or derived from the
element type) on loop entry. **Changes an accepted, building program:** no.

---

## MEDIUM

### SAF-12 (MEDIUM, NEW): float folding emits `inf.0` and `nan.0`

Folding `1.0e308 * 10.0` produces Python `inf`; the backend appends `.0` to any float
text without `.` or `e` (`zig.py:1480-1482`), giving `const x: f64 = inf.0;`.
`ast_preprocessor.py:614-619` does not check `math.isfinite`. `f02_fold_float_inf`:
a7=0, zig=1 "expected pointer dereference ... found 'a number literal'".
`f18_fold_nan` (`1e308 * 10.0 - 1e308 * 10.0`): a7=0, emits `nan.0`, zig=1.
Fix: do not fold to non-finite values. Changes an accepted, building program: no.

### SAF-13 (MEDIUM, NEW): folding a huge shift raises an uncaught `ValueError`, exit 8

`1 << 20000` folds at `ast_preprocessor.py:633-634`; `raw_text=str(result)` at `:647`
exceeds CPython's 4300-digit int-to-str limit. Only `ZeroDivisionError` and
`OverflowError` are caught (`:637`), and `str()` is outside the `try` anyway.
`f01_fold_huge_shift`: a7=8, "Unexpected error: Exceeds the limit (4300 digits) for
integer string conversion". Fix: bound shift folding by the operand width and let the
shift obligation reject it. Changes an accepted, building program: no.

### SAF-14 (MEDIUM, KNOWN G3): folded integer results are not checked against the declared type

`x: i32 = 2147483647 + 1` folds to `2147483648` (`f04`, a7=0, zig=1 "type 'i32' cannot
represent integer value '2147483648'"). `a: i32 = 1 << 31` behaves the same (`f19`,
a7=0, zig=1); INFERENCE: the unfolded Zig `1 << 31` into an `i32` would also be
rejected, so folding is not the cause, the missing range check is. Tracked by gate G3 (`README.md:143`).
Changes an accepted, building program: no.

### SAF-15 (MEDIUM, NEW): usage analysis is keyed by name, so an unused local in a sibling scope is marked used

`_collect_used_identifiers` collects names for the whole function
(`ast_preprocessor.py:361-372`) and `_mark_usage` sets `n.is_used = n.name in used`
(`:380-382`). `f08_sibling_scope_is_used` (`{ x := 1; io.println(x) } { x := 2 }`):
a7=0, zig=1 "unused local constant" on `const x = 2;`. Fix: resolve uses to
declarations by scope. Changes an accepted, building program: no.

### SAF-17 (MEDIUM, NEW): inferred type of a mutable untyped integer is always `i32`

`_infer_from_value` returns `i32` for any integer literal (`ast_preprocessor.py:418-419`)
and ignores the type checker's type. `f10_infer_i32_for_big_literal`
(`x := 3000000000; x = 1`): a7=0, emits `var x: i32 = 3000000000;`, zig=1.
Fix: take the type from `type_map` for the VAR's value. Changes an accepted, building
program: unknown (INFERENCE: a program whose literal fits i32 but whose checker type
differs would change its emitted type).

### SAF-18 (MEDIUM, NEW): mutability analysis is keyed by name

`_collect_mutations` collects root names for the whole function (`:324-346`) and
`_mark_mutations` marks every VAR with that name (`:350-352`).
`f09_sibling_scope_is_mutable`: the unmutated `x := 5` in a sibling block becomes
`var x: i32 = 5;`, zig=1 "local variable is never mutated". Fix as SAF-15.
Changes an accepted, building program: no.

### SAF-20 (MEDIUM, NEW): nested function bodies are never analyzed by the safety pass, so codegen fails with exit 7

`_visit_stmt` has no FUNCTION branch (`safety.py:300-389`), so no obligation inside a
nested function is proven, and the backend refuses the lowering.
`p10b_nested_fn_uncalled_division`: a7=7 "Zig backend: div was not approved by safety
proof analysis", no location. Nested functions also cannot be called (`p10`: a7=6
"Undefined type (Identifier 'helper')"; PIP-30). The failure is fail-closed but at the
wrong stage and without a source location. Changes an accepted, building program: no.

### SAF-21 (MEDIUM, NEW): facts for file-scope constants are discarded at every function entry

`_visit_decl` stores facts for CONST/VAR globals (`safety.py:295-298`) but each FUNCTION
starts with `self.facts.by_symbol = {}` (`:290`). `p11_global_const_divisor`
(`N :: 4; y := 10 / N`): a7=6 "divisor may be zero", no line. Fix: seed `::` constant
facts per function; keep dropping facts for mutable globals (see SAF-6). Changes an
accepted, building program: no.

### SAF-22 (MEDIUM, NEW; the missing-line half is PAR-04): safety obligations reuse unrelated error types

Division uses `TypeErrorType.UNSAFE_CAST` (`safety.py:561`), index and slice use
`INDEX_NOT_INTEGER` (`:568`, `:577`), deref uses `CANNOT_DEREFERENCE` (`:625`). Users
see "Unsafe type cast (division/modulo divisor must be non-zero ...)" with hint "This
cast may lose information" (`p11`, `p29`, `p18b`), "Array index must be integer (index
must satisfy 0 <= index < len ...)" for a `usize` index (`p23`, `p24`), and "Cannot
dereference non-pointer type" for a `ref` (`p06c`). Division diagnostics have no line
because BINARY nodes have no span (PAR-04; generalizes KNOWN D7's "no line"). Fix:
dedicated error types per obligation. Changes an accepted, building program: no.

### SAF-23 (MEDIUM, NEW): the safety pass is recursive, contrary to CLAUDE.md and the test docstring

`_visit_stmt`, `_visit_expr`, `_always_returns` and `_int_literal` recurse
(`safety.py:304, 341, 402-407, 675, 720`). CLAUDE.md lists "internal safety proof
planning" among the passes and states the pipeline is validated at limit 100.
Synthetic ASTs driven into `SafetyProofPass.analyze` alone
(`depth/deep_safety.py` -> `depth/deep_safety.txt`):

| Shape | Limit 100: max depth that passes | Limit 1000 | Preprocessor on same AST |
| --- | --- | --- | --- |
| nested blocks | 86 | 986 | no failure up to 4096 |
| binary `+` chain | 87 | 987 | no failure up to 4096 |
| nested `if` with block | 43 (two frames per level) | 493 | no failure up to 4096 |
| unary `-` chain in a guard | 85 | 985 | no failure up to 4096 |
| `if x == 0` with nested blocks ending in `ret` | 89 | 989 | no failure up to 4096 |

`_int_literal` and `_always_returns` called directly fail at depth 100 with limit 100
(`depth/helpers_direct.txt`). End to end, the type checker overflows first on binary
chains (`stages.txt`: `f15b` 1200 terms, RecursionError in `type_checker.py
visit_binary_expr`, TYP-18), and 400 nested blocks pass safety and fail in the backend
with exit 7 (`recur.txt`). So the safety pass is not the first stage to fail today;
it will be once TYP-18 is fixed. The AST preprocessor is iterative as documented.
Fix: explicit stacks (planned for the Wave 3 engine). Changes an accepted, building
program: no.

### SAF-27 (MEDIUM, NEW): `if` expressions get no guard facts and no value fact

The IF_EXPR branch visits condition, then and else without applying the condition's
facts and returns an empty fact (`safety.py:458-461`).
- `p29_if_expr_guard` (`y := if x != 0 { 10 / x } else { 0 }`): a7=6 "divisor may be
  zero", no line. The statement form `p29b_if_stmt_guard_control` is accepted (a7=0,
  zig=0). SPEC shows the expression form at `docs/SPEC.md:530`.
- `p29c_if_expr_value_fact` (`d := if c { 5 } else { 7 }; 10 / d`): a7=6.
MATCH_EXPR (`:462-469`) has the same shape (INFERENCE, not probed). Changes an accepted,
building program: no.

### SAF-28 (MEDIUM, partly KNOWN D7): no negative float literal can be cast to an integer

`_float_to_int_is_proven` requires `node.kind == LITERAL` (`safety.py:655`). At safety
time `-1.0` is still `UNARY(NEG, 1.0)` because folding runs later, and `_unary_fact`
yields nothing for floats (`:497-501`). `_int_literal` does look through NEG (`:719-721`);
the two helpers disagree. `p30_cast_neg_zero_float` (`cast(i32, -0.0)`) and
`p30b_cast_neg_float_literal` (`cast(i32, -1.0)`): both a7=6 "float-to-int cast requires
finite integral range proof". KNOWN D7 records the same cause for a negative float
divisor. Changes an accepted, building program: no.

### SAF-29 (MEDIUM, partly KNOWN G3/P4 cast decisions): `f64` to `f32` casts need no range proof

`classify_cast` returns `EXPLICIT_NUMERIC` for float narrowing (`cast_classifier.py:71`),
and `_cast_fact` approves it (`safety.py:547-551`). SAFETY_CONTRACT's table requires
"primitive cast is classified and range-safe" (`SAFETY_CONTRACT.md:47`). `p30g_cast_f64_to_f32_overflow`
(run-allowed; `big: f64 = 1e300; cast(f32, big)`): a7=0, zig=0, Debug and ReleaseFast
print `inf` (`runs6.txt`). No trap, but the value is not range-safe. Cast policy is open
(D.024 vs D.038, gate G3, packet P4). Fix: decide in P4; then either document the
float narrowing rule or require a proof. Changes an accepted, building program: yes.

### SAF-30 (MEDIUM, NEW): type ranges and loop bounds are never seeded, so documented guarded forms are rejected

- `_default_fact_for_type` (`safety.py:473-477`) has no caller (`grep -rn _default_fact_for_type a7/`
  finds only the definition). Parameters get `ValueFact()` (`:291-293`). A guard such as
  `if x >= 0` on an `i64` parameter therefore yields `[0, None]`, and
  `PROVABLE_NARROWING` needs both bounds (`:543`, `_range_fits` `:648-652`).
  `p30i2_cast_guard_nonneg_no_upper` (`if x >= 0 { y := cast(u64, x) }`): a7=6 "cast
  target range is not proven" (`batch6.txt`).
- For-in index variables get `[0, None]` (`:368`), so indexing the iterated array
  itself is rejected: `p23b_for_in_index_same_array` (`for i, v in a { a[i] }`), a7=6
  "index bounds are not proven" (`batch8.txt`).
Fix: seed parameter and local facts from their type range; give the index of
`for i, v in a` the bound `len(a) - 1` for `a` itself. Changes an accepted, building
program: no.

### SAF-31 (MEDIUM, NEW): positional struct initializers map fields by struct name across the whole program

`_collect_struct_defs` walks the entire AST and stores `self._struct_defs[node.name]`
(`ast_preprocessor.py:175-185`); the last struct with a given name wins, whatever its
scope. `_normalize_struct_init` then names positional fields from that entry
(`:259-269`). `p31e_positional_named_struct_vs_local`: file-scope
`Pair :: struct { a: i32  b: i32 }`, `main` uses `Pair{1, 2}`, and a later function
declares a local `Pair :: struct { b: i32  a: i32 }`. a7=0 and main is emitted as
`const p = Pair{ .b = 1, .a = 2 };` for the file-scope `Pair`, so `p.a` would be 2.
zig=1 only because the emitted local `const Pair` shadows the file-scope one. Two local
structs with the same name could not be tested: positional init of a local struct
fails in the type checker (`p31`, `p31c`, `p31d`, a7=6 "Cannot access field 'a' on
undefined identifier 'p'"). Fix: resolve the struct from the init node's type in
`type_map`. Changes an accepted, building program: no today; unknown after local struct
names are escaped.

---

## LOW

### SAF-16 (LOW, NEW): a nested function's parameter use counts for the outer parameter, and the nested function is not emitted

`_collect_used_identifiers(func_node.body)` includes nested function bodies
(`ast_preprocessor.py:294-295`), so outer `a` is "used" by inner `a`. `f12`: a7=0,
zig=1 "unused function parameter" on `fn outer(a: i32)`; `inner` is absent from the
output. Nested functions cannot be called today (PIP-30), which limits impact.
Changes an accepted, building program: no.

### SAF-19 (LOW, NEW): shadow renaming ignores file-scope names

`_resolve_shadowing` seeds `all_emitted` with parameters only (`:436-442`), so a
generated `x_1` can collide with a global `x_1`. `f13`: a7=0, zig=1 "local constant
shadows declaration of 'x_1'". Changes an accepted, building program: no.

### SAF-32 (LOW, NEW; sibling of KNOWN B10 and PIP baseline row 11): `::` constants are not renamed when they shadow

`_resolve_shadowing` renames only `NodeKind.VAR` (`ast_preprocessor.py:480-484`).
`p35_const_shadow` (`x :: 1; { x :: 2 ... }`): a7=0, zig=1 "local constant 'x' shadows
local constant from outer scope". Changes an accepted, building program: no.

### SAF-33 (LOW, NEW): out-of-range float literal casts get the wrong reason

`cast(u64, 18446744073709551615.0)` is correctly rejected (the literal is 2^64 in
f64), but the message is "float-to-int cast requires finite integral range proof"
(`p30c`, a7=6), because one message covers non-finite, fractional and out-of-range
cases (`safety.py:545-546`, `:654-661`). Changes an accepted, building program: no.

### SAF-34 (LOW, NEW): dead state and structure that block the Wave 3 fact engine

- Dead: `_default_fact_for_type` (SAF-30); `case.statements` at `safety.py:375` (the
  parser sets only `statement`, `parser.py:2248-2253`); the body of
  `_prove_integer_overflow` after `return` (`:636-646`, KNOWN P3/ZIG-38) and therefore
  `ObligationKind.INTEGER_OVERFLOW`; `ObligationKind.UNION_FIELD` has no use;
  `ValueFact.initialized`, `moved` and `enum_discriminant` are never read, and
  `maybe_nil` is only copied (`:691-702`); `self.symbols` (`:229`) is never read;
  `self.obligations` and `self.results` are never read outside `safety.py`; the
  ADDRESS_OF and DEREF branches (`:438-443`) handle node kinds `parser.py` never
  creates; `_lower_field_sugar` is a no-op (`ast_preprocessor.py:187-189`).
- Structure: facts are keyed by name strings (`FactMap.by_symbol`), not symbols, so
  shadowing and cross-function state depend on restore order (KNOWN S4:
  `moved_symbols` is reset once per `analyze`, `:247`); `node_types`, `by_node` and
  `BackendPlan.approved` are keyed by `id(node)` while the preprocessor replaces nodes
  (SAF-7). The preprocessor's `ASTPreprocessor` docstring says it "does NOT modify
  semantic meaning" (`:82`), which SAF-7, SAF-9 and SAF-10 contradict.
Changes an accepted, building program: no.

---

## SAF-KNOWN: re-confirmed known items

| Known ID | Probe or code | Result |
| --- | --- | --- |
| S1 / P0b.1 (branch assignment forgotten) | `p33c_then_unbraced` (`x := 5; if c x = 0; 10 / x`); code `safety.py:338-342` | a7=0, zig=0 |
| S2 / P0b.2 (loops), `continue` path | `p28_labeled_continue_zero`; `p34_for_init_index` (`for i := cast(usize, 0); i < 10; i += 1 { arr[i] }` on `[5]i32`) | both a7=0, zig=0 |
| E8 (break state), labeled variant | `p20_while_break_restores`; `p27_labeled_break_zero` (`break outer`) | both a7=0, zig=0 |
| S3 / P0b.3 | code: CALL branch `:444-447` invalidates nothing | not re-probed |
| X1 / P0b.4 (compound assignment) | code `:326-327` stores the RHS fact for `-=`; `p32b` shows `defer x += 5` storing `5` | consistent |
| S4 | code `:247` resets `moved_symbols` only in `analyze` | not re-probed |
| S7 | `p21_moved_in_loop_use_before_del` | a7=0, zig=0 |
| P0b.8 (`defer del` then `del`) | code `:381-382` visits the deferred `del` expression without `_mark_deleted` | not re-probed |
| P5 (inactive union field) | `p22_union_inactive_field` | a7=0; zig=1 only because `payload` is comptime-known |
| P3 / ZIG-38 (`_prove_integer_overflow` dead) | code `:636` `return` | confirmed |
| B10 | `p36_match_case_var_shadow` | a7=0, zig=1 "unused local constant" on `x_1` |
| B11 | `p18`, `p32`, `p32b`, `p32c` emit `defer void;` | zig=1 |
| F2 / PAR-03 | `f11_struct_init_mixed_positional` (`P{y: 2, 1}`): `--mode ast` shows only `STRUCT P`; `main` is dropped (`out/f11_ast.txt`) | a7=0, output has no `main` |

---

## Checked and correct

- Negative integer `/` and `%` folding truncates like Zig (`f14`: `7 % -3`, `-7 / 2`,
  zig=0; matches ledger S13b NOT REPRODUCED).
- A guard `x >= 1` keeps the variable's previous upper bound, and a stale bound is not
  invented: `p24` (`i: usize = 7; if i >= 1 { arr[i] }` on `[4]i32`) and `p25`
  (`i = j` with `j = 9`) are both rejected.
- Boolean `and`/`or` fold only when both operands are literals
  (`ast_preprocessor.py:677-692`), so no side effect is dropped.
- Division and modulo by a literal zero are never folded (`:620`, `:622`), and the
  safety pass rejects them.
- `p18b`: a braced `defer { x = 5 }` does not leak facts.
- `p33d`: a braced `else { x = 5 }` does not leak facts.
- Cast rules exercised through the safety pass: `u32 -> i32` with a proven small value is
  approved and runs (`p30e`, prints `5` in Debug and ReleaseFast); the same cast with
  `4000000000` is rejected (`p30f`, "unsigned-to-signed cast requires an upper-bound
  proof"); `i32 -> i64` on a parameter is lossless without a proof and runs (`p30j`,
  prints `-3`); `cast(u64, 18446744073709551615.0)` is rejected (`p30c`).
- Float literal precision in casts is not a safety hole: a double that rounds into range
  cannot be a true value out of range at the i32/i64/u64 limits, because
  `_float_to_int_is_proven` compares the rounded double and doubles near 2^63 and 2^64
  are exact powers of two (reasoning checked against `p30c` and `p30d`). `p30d`
  (`cast(i64, 9007199254740993.0)`, `cast(u8, 255.00000000000000001)`) is approved and
  prints `9007199254740992 255` in both modes; the value loss happens when the literal
  is read as an f64, before this pass.
- Folded float text with exponents is valid Zig (`f20`: `1e+21`, `1e-08`, zig=0, prints
  `1000000000000000000000 0.00000001` in both modes).
- `BackendPlan.require` is operation-specific (`safety.py:214-218`), and the backend
  fails closed when an approval is missing (`p10b`, exit 7).
- `compile.py:346-360` runs the safety pass only when validation passed, adds its
  errors to the semantic stage, and hands `backend_plan` to codegen (`:396-400`).
- The AST preprocessor's tree walks are iterative (SAF-23 table: no failure up to depth
  4096 at limit 100).

---

## Test gaps

- **No test asserts rejection by the divisor, index, slice or deref obligations.**
  `grep -rn "may be zero\|bounds are not proven\|may be nil\|non-nil\|not proven\|Unsafe type cast\|Cannot dereference" test/*.py scripts/*.py`
  exits 1 with no lines (`testgaps/diag_grep.txt`). Only cast rejection (`test_cast_safety_matrix.py:179-218`) and
  use-after-`del` (`:264-277`) have rejection tests.
- **A test asserts the opposite of the compiler's behavior.** `run_semantic_analysis` in
  `test/test_semantic_comprehensive.py:25-49` stops after semantic validation; of the
  `test_semantic_*.py` files only `test_semantic_types.py:58-61` runs `SafetyProofPass`.
  `test_calculator` (`test_semantic_comprehensive.py:876-894`) asserts acceptance of
  `div :: fn(a: i32, b: i32) i32 { ret a / b }`; the CLI rejects that program with exit 6
  "divisor may be zero" (`testgaps/comprehensive_calc.json`).
- **No unsound counterexample is pinned.** Nothing tests match joins, `fall`, un-braced
  branches, deferred assignments, `ref` parameters receiving `nil`, `ptr` fields,
  early-return plus else, quotient facts, globals across calls, or field `del` twice
  (SAF-1 to SAF-8, SAF-11, SAF-24, SAF-25, SAF-26). Each needs a rejected program paired with an
  accepted guarded program, as `docs/plan/README.md` "Test plan" requires.
- **Preprocessor tests cannot see SAF-7, SAF-9 or SAF-31.** `test_ast_preprocessor.py:30-35`
  constructs `ASTPreprocessor()` with no `type_map` and no stdlib, so the id-keyed
  `type_map`, builtin resolution and struct lookup across scopes are never exercised.
  The committed fold tests use small integers (`:178-233`); the only exactness test,
  `test/test_pipeline_native.py:79`, is uncommitted and covers `/`, not `%` (SAF-10) or
  non-finite floats (SAF-12).
- **Usage and mutability tests use one scope.** `test_ast_preprocessor.py:417-690` never
  declares the same name in sibling scopes (SAF-15, SAF-18). `:654-670` asserts that a
  variable only assigned is "used", documenting the name-keyed walk rather than a
  requirement.
- **Recursion tests are too shallow to see SAF-23.** `test_iterative_traversal.py:678-720`
  uses depths 10-20 at limit 150; the safety pass fails at 44 nested `if`s and 87 nested
  blocks at limit 100. The module docstring says the semantic passes are iterative.
- **The cast matrix mirrors the implementation.** As `types.md` notes,
  `test_cast_safety_matrix.py:110-146` computes expected values with `classify_cast`
  itself; no test states an independent cast table, and no test covers float narrowing
  (SAF-29) or negative float literals (SAF-28).
- `test_backend_plan_is_operation_specific_for_approved_nodes` (`:233-261`) is a real
  requirement test and passes for the right reason.

---

## Not verified

- No unsafe probe was built into an executable or run (division by zero, null
  unwrap, double free, out-of-bounds); their runtime effect is INFERENCE from the
  emitted Zig and Zig's documented Debug and ReleaseFast behavior.
- How many existing programs each CRITICAL fix would change: not scanned. The ledger's
  Part C and Part E scans cover P0b.1-P0b.4 rules, not these findings.
- Approval misattachment through reused node ids (SAF-7): no concrete program found.
- MATCH_EXPR guard facts (SAF-27): not probed.
- Whether two same-named local structs would miscompile (SAF-31): blocked by the type
  checker rejecting positional init of local structs, which belongs to the TYP/PIP
  scopes.
- Behavior with file-module imports: local imports fail closed before codegen, so
  struct-name and builtin collisions across modules were not tested.
- 32-bit targets: `SIGNED_RANGES`/`UNSIGNED_RANGES` fix `isize`/`usize` at 64 bits
  (`safety.py:54, 61`); not tested.
- Performance was not measured. INFERENCE: `copy_symbols` (`safety.py:170-171`) copies
  the whole symbol dict at every BLOCK, IF, WHILE, FOR and FOR_IN entry (`:302, 338,
  348, 354, 366`), so the cost is O(scopes x live symbols) per function; the
  preprocessor walks each function body five times plus once per nested function
  (`ast_preprocessor.py:290-304`), which is linear.

claims checked: 201
