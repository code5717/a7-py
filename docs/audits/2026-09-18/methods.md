# Methods and receiver functions — audit, 2026-09-18

A7 has no methods. It has free functions whose first parameter happens to be a
`ref` struct, and `docs/SPEC.md:806` calls that section "Methods". Neither of the section's two
examples compiles: both call an undefined `sqrt` (`m01`, a7=6), and after that is
fixed the second still divides by an unguarded call result (`m40`, a7=6,
"divisor may be zero"). A guarded rewrite does compile and build
(`m47`, a7=0, zig=0), so the section is fixable in the docs. The one call form
the SPEC promises as sugar, `v.length()`, does not parse into anything callable
(`m05`, a7=6). No packet, gate or ledger entry owns dot-call syntax, so
track 8a's collection examples (`docs/plan/memory.md:182-186`) cannot be
written in A7 as drafted.

Audited tree: the main working tree as it stands on 2026-09-18, with batches
C3, PR-00, T0, V1, NOREC-0 and PL-02 applied as uncommitted changes. C1, C4 and
C2 are in flight in worktrees under `/home/cx89/Projects/pl-dev/a7-wt/` and were
not audited. Toolchain: `zig 0.16.0`
(`tmp/audit/2026-09-18/methods/zig-version.txt`).

Probes live in `/home/cx89/Projects/pl-dev/a7-py/tmp/audit/2026-09-18/methods/`.
Every probe was run with
`uv run a7 <file>.a7 --output <file>.zig` then
`zig build-obj -fno-emit-bin <file>.zig` from the probe directory
(`tmp/audit/2026-09-18/methods/run.sh`); each probe's `.result` file holds the
two exit codes. Only `m03` was built and run, in Debug and ReleaseFast: it is
the only receiver probe that uses no `ref`, per the probing rules. Every other
receiver form needs `ref`, so runtime behavior for them is compile-only and is
listed under "Not verified".

## Summary

| Severity | NEW | KNOWN | Total |
| --- | --- | --- | --- |
| CRITICAL | 0 | 2 | 2 |
| HIGH | 3 | 1 | 4 |
| MEDIUM | 3 | 5 | 8 |
| LOW | 1 | 1 | 2 |
| **Total** | **7** | **9** | **16** |

## What works today

Proved by probe, a7 exit 0 and `zig build-obj` exit 0, with the emitted Zig read:

| Form | Probe | Emitted Zig |
| --- | --- | --- |
| `f(v)` with `v: ref S`, read-only | `m02` | `fn sum(self: ?*Vec2) i32 { return (self.?.x + self.?.y); }`, `sum(&v)` |
| by-value receiver, read-only | `m03` | run: `sum=7`, Debug and ReleaseFast both exit 0 |
| `f(v)` with `v: ref S`, writes a field | `m43`, `examples/017_methods.a7` | `counter.?.value += 1` |
| assignment to the whole receiver | `m15` | `c.?.* = Counter{ .value = 0 };` |
| nested field write through a receiver | `m17` | `o.?.inner.value += 1;` |
| SPEC 6.5's `normalize`, with `math.sqrt` and a `len != 0.0` guard | `m47` | `self.?.x /= len;` inside `if ((len != 0.0))` |
| a struct field as the receiver | `m07` | `increment(&o.inner);` |
| a receiver function named like a field | `m25` | `fn len(v: ?*Vec2) i32 { return v.?.len; }` |
| a receiver function named like a stdlib call | `m37` | `fn println(c: ?*Counter) i32`, not rewritten |
| a receiver function named `sqrt` | `m28` | `sqrt(&v)`, not rewritten to `@sqrt` (the rewrite is keyed on `stdlib_canonical` starting `std.math.`, `a7/backends/zig.py:1634-1640`, and on the literal prefix `math.`, `:1648-1653`) |
| two receiver functions of the same name | `m27` | rejected, a7=6, "Already defined: Function 'get'" — no overloading, as SPEC implies |
| `ret self` (returning a `ref`) | `m31` | a7=0, zig=0 |

`examples/017_methods.a7`, `038_inventory_report.a7`, `040_task_board.a7`,
`041_route_simulation.a7` and `042_gradebook.a7` all give a7=0 and zig=0 in this
tree (logs in `tmp/audit/2026-09-18/methods/ex_*.zigout`).

## Findings

### MTH-1 (CRITICAL, KNOWN SAF-1): `nil` passed as a receiver compiles and unwraps null at run time

`nil` is accepted for any `ref` parameter, the callee assumes the receiver is
non-nil, and the emitted Zig unwraps it unconditionally.

Evidence. `a7/passes/type_checker.py:1406-1412` errors on a `nil` argument only
when the parameter is *not* a `ReferenceType`; `a7/safety.py:291-293` seeds every
parameter from `_fact_from_type_node`, and `:482-483` returns
`ValueFact(non_nil=True)` for a `TYPE_POINTER` node, which is what `ref T` parses
to (`a7/parser.py:775-781`). `_prove_ref_non_nil_for_node` then proves the
obligation from that seeded fact (`a7/safety.py:626-627`).

- `m04_nil_recv.a7` (`increment(nil)` where `increment :: fn(c: ref Counter)`):
  a7=0, zig=0. Emitted: `fn increment(c: ?*Counter) void { c.?.value += 1; }`
  and `increment(null);`.
- `m24_ref_nil_after_check.a7` (`peek(nil)` through a second function): a7=0,
  zig=0, emits `return peek(null);` into `return c.?.value;`.

Not run: a null unwrap. In Debug Zig panics; in ReleaseFast the unwrap is
unchecked. This contradicts `README.md:157-158` ("ref struct fields are accessed
directly after nil-proofing") and `docs/SPEC.md:399-401` ("then proves the
operation safe before Zig codegen").

Fix direction: discharge a `REF_NON_NIL` obligation per `ref` argument at the
call site, as SAF-1 already proposes. **Changes an accepted, building program:**
yes — `m04` and `m24` would start failing.

### MTH-2 (CRITICAL, KNOWN S3; the global twin is SAF-6): a fact about a local survives a call that zeroes it through an implicit `ref`

The safety pass's CALL branch invalidates nothing, so a guard proved before a
receiver call is still believed after it. A7 accepts a program that divides by
zero and Zig builds it.

Evidence. `a7/safety.py:444-447` — the CALL branch only visits the callee and
arguments. Facts are reset only at function entry (`:290`).
`docs/audits/2026-09-16/compiler/safety.md:588` records S3 as "not re-probed";
this is the probe.

- `m29_fact_not_invalidated.a7`: `x := 4; if x != 0 { zero_it(x); io.println("{}", 100 / x) }`
  with `zero_it :: fn(v: ref i32) { v = 0 }`. a7=0, zig=0. Emitted:

  ```zig
  if ((x != 0)) {
      zero_it(&x);
      __a7_stdout_print("{}\n", .{@divTrunc(100, x)});
  }
  ```

Not run: division by zero. The receiver shape reaches this through the implicit
`ref` argument, so every mutating receiver function is a fact-invalidation hole.
`m30_fact_index_not_invalidated.a7` (the indexing twin) is rejected for an
unrelated reason: the index fact was never proven in the first place (a7=6).

Fix direction: drop facts for every symbol passed as an implicit or explicit
`ref` argument at each call, and for mutable globals. **Changes an accepted,
building program:** yes.

### MTH-3 (HIGH, KNOWN PIP-9, new manifestation): a receiver function called through an import alias loses its implicit `ref`

PIP-9 records that a `file_module_call` skips member existence, arity, argument
types and return type (`docs/audits/2026-09-16/compiler/pipeline.md:249-265`).
Its five probes are all value arguments. The receiver case loses two more things:
the implicit `&` and the caller's mutability.

Evidence. `a7/passes/type_checker.py:1340-1343` (PIP-9 cited `:1317-1321` in the
2026-09-16 tree; the code moved, the branch is the same): when `file_module_call`
is set, the checker visits the arguments and returns `UNKNOWN` — it never reaches
the argument-type loop at `:1399-1427` where `implicit_ref_args` is computed.

- `m39_import_recv_local_struct.a7` (`sh :: import "imp/shape"`, then
  `v := Counter{value: 1}; sh.increment(v)`): a7=0, zig=1. Emitted:

  ```zig
  const v = Counter{ .value = 1 };
  _ = module_imp_shape__increment(v);
  ```

  Zig: `expected type '?*Counter', found 'Counter'`
  (`m39_import_recv_local_struct.zigout`). The argument is passed by value, and
  `v` is `const` because the mutation analysis at
  `a7/ast_preprocessor.py:352-358` keys off `implicit_ref_args`, which is empty.
- Control `m38_import_plain.a7` (a non-receiver function through the same alias
  machinery): a7=0, zig=0 — the alias path itself works.
- The `_ =` on a `void` callee is cosmetic, not a defect:
  `m48_import_void_call.a7` emits `_ = module_imp_void__noop(1);` and gives
  a7=0, zig=0.

Fix direction: covered by PIP-9's fix (resolve the alias to the module's exported
symbol and check the call like any other), which must also run the
implicit-`ref` marking. **Changes an accepted, building program:** no — `m39`
does not build today.

### MTH-4 (HIGH, NEW): both of SPEC 6.5's examples are rejected by the compiler

`docs/SPEC.md:806-831` is the SPEC's only "Methods" section and carries no
implementation-status note, unlike 6.6 (`:835-838`). Neither of its two functions
compiles.

- `m01_spec65_verbatim.a7` — SPEC 6.5 exactly as written: a7=6, four errors, all
  "Undefined type (Identifier 'sqrt')" / "Cannot call undefined identifier
  'sqrt'". The section shows no `math ::` import and `sqrt` is not a global.
- `m40_spec65_fixed.a7` — the same code with `math.sqrt` substituted: a7=6, two
  errors, "division/modulo divisor must be non-zero: divisor may be zero" at
  `self.x /= len` and `self.y /= len`. `len` is bound to a call result; the CALL
  branch of the safety pass sets no fact (`a7/safety.py:444-447`), so
  `_prove_nonzero_divisor` (`:559-565`) reads `ValueFact()` and fails. The
  comment at `docs/SPEC.md:823` ("OK: modifying through checked reference field
  access") is wrong about which check fires — the field write is fine; the
  divisor is not.
- `m47_spec65_guarded.a7` — the same function with `if len != 0.0 { ... }`
  around the two divisions: **a7=0, zig=0**. `_facts_from_condition` learns
  `nonzero` from an identifier compared against a float zero
  (`a7/safety.py:695-697`, `_zero_literal` accepts `0.0` at `:710-711`).

So SPEC 6.5 is fixable with a guard and an import, and needs no compiler change.
The defect is that the SPEC ships two non-compiling programs as the definition of
a feature, which the docs-accuracy rule in `CLAUDE.md` treats as a drift bug.

Fix direction: replace the 6.5 listing with `m47`'s text, or delete the section.
**Changes an accepted, building program:** no (documentation only).

### MTH-5 (HIGH, NEW): the SPEC contradicts itself three ways about what a method is

Three statements in one document cannot all be true.

1. `docs/SPEC.md:473-474`: "Method-call sugar such as `vec.length()` is planned
   syntax, not current semantic support. Use explicit functions such as
   `length(vec)`."
2. `docs/SPEC.md:806` names a section "6.5 Methods" and `:809` says "Methods are
   functions with receiver" — presented without any implementation-status note,
   unlike 6.6 Variadic Functions which carries one at `:835-839`.
3. `docs/SPEC.md:815`: "// Method declaration - receiver is immutable parameter",
   immediately followed at `:820` by "// Method that modifies the receiver".

Evidence for what the compiler does:
- `m05_dot_call.a7` (`v.sum()`): a7=6, two errors —
  "Struct has no such field (Struct 'Vec2' has no field 'sum')" and
  "Type is not callable (Cannot call 'v.sum' (undefined identifier))". The
  field-access path (`a7/passes/type_checker.py:1827-1833`) has no fallback that
  looks for a function whose first parameter matches, and the call path
  (`:1332-1344`) only recognises a FIELD_ACCESS callee when the object is a
  `MODULE` symbol.
- A `ref` receiver is mutable in practice (`m15`, `m17`, `examples/017_methods.a7`),
  so `:815` is wrong. SPEC 6.3's own text agrees that `ref` parameters modify
  caller storage (`docs/SPEC.md:772-775`), which is the opposite of `:815`.
- `docs/SPEC.md:988` ("deeper propagation through method-style call chains
  remain implementation work") describes a construct the language does not have.

Separately, `README.md`, `site/public/docs/*.md`, `site/public/llms.txt`,
`site/public/llms-full.txt` and `docs/STATUS.md` contain no occurrence of
"method" or "receiver"
(`grep -rn -i "method\|receiver" README.md site/public/docs/ site/public/llms.txt site/public/llms-full.txt docs/STATUS.md`
returned nothing, exit 1). A SPEC section named "Methods" has no user-facing
counterpart and no status row, so a reader of the site cannot learn that the
section describes a shape rather than a feature.

Fix direction: either delete 6.5 and fold the receiver idiom into 6.3, or mark
it parsed-only in the style of 6.6 and fix `:815`; either way the docs-accuracy
rule in `CLAUDE.md` requires the site and `llms*.txt` to say the same thing.
**Changes an accepted, building program:** no (documentation only).

### MTH-6 (HIGH, NEW): a receiver declared on a type alias of a struct does not resolve

`Ctr :: Counter` produces an unresolvable type, so a receiver function written
against the alias fails with five cascading errors.

Evidence.
- `m11_alias_recv.a7` (`Ctr :: Counter`, `increment :: fn(c: ref Ctr)`): a7=6.
  Errors: "Undefined type (Type 'Ctr')" (twice), "Cannot access field on
  non-struct type: got 'ref unknown type'", "Assignment type mismatch: expected
  'unknown type', got 'i32'", "Argument type mismatch: expected 'ref unknown
  type', got 'Counter'".
- `m14_alias_byvalue.a7` — the same alias used by value, no receiver: a7=6,
  "Undefined type (Type 'Ctr')". So the defect is the alias, not the receiver.
- Control `m20_alias_prim.a7` (`Handle :: u64`, the exact form at
  `docs/SPEC.md:372-373`): a7=0, zig=0.

`docs/SPEC.md:369-378` lists type aliases without restricting them to
primitives and arrays, and `README.md:153` lists "type aliases" under "What
Works". Type aliases are marked *incidental* coverage in
`docs/plan/audit/language-audit-checklist.md:33`, so this is the first probe of
the struct case.

Fix direction: resolve an alias whose right-hand side names a user type, in
name resolution. **Changes an accepted, building program:** no.

### MTH-7 (MEDIUM, NEW): a generic receiver `ref $T` cannot read a field

Evidence. `m12_generic_recv.a7` (`peek($T) :: fn(b: ref $T) i32 { ret b.value }`):
a7=6, one error, "Cannot access field on non-struct type: got 'ref $T'".
`a7/passes/type_checker.py:1784-1804` handles a `ReferenceType` whose referent is
a `StructType`, `GenericInstanceType` or `UnionType`; a `GenericParamType`
referent falls through to the `FIELD_ACCESS_ON_NON_STRUCT` error at `:1858-1859`.
The pass checks generic bodies before monomorphization and has no deferred
field-resolution path.

This is the "Methods x generics" pair that
`docs/plan/audit/language-audit-checklist.md:99` flags as having no audit and no
test. There is no test: `grep -rn "ref \$T" test/` returns nothing.

Fix direction: defer field resolution on a `GenericParamType` referent to
specialization, or require a type-set constraint that names struct types.
**Changes an accepted, building program:** no.

### MTH-8 (MEDIUM, KNOWN TYP-14): the implicit `ref` for a receiver ignores exact type identity

`a7/passes/type_checker.py:1414-1417` marks an argument `implicit_ref_args` when
`arg_type.is_assignable_to(param_type.referent_type)` and the node is an
identifier, field, index or deref. Assignability is not identity, so a widened
integer is accepted and `&x` is emitted against the wrong pointer type.

- `m19_widen_recv.a7` (`s: i32` into `incr :: fn(x: ref i64)`): a7=0, zig=1,
  `expected type '?*i64', found '*i32'` … "pointer type child 'i32' cannot cast
  into pointer type child 'i64'".

Zig's type check is the only thing stopping an 8-byte write into 4-byte storage.
Two forms that *are* correctly rejected, checked as controls:
`m41_struct_struct_ref.a7` (two structurally identical structs `A` and `B`):
a7=6, "expected 'ref B', got 'A'"; `m42_array_slice_ref.a7` (`[3]i32` into
`ref []i32`): a7=6, "expected 'ref []i32', got '[3]i32'". So TYP-14's hole does
not widen to structs or to array-to-slice.

Fix direction: require exact referent-type identity. **Changes an accepted,
building program:** no.

### MTH-9 (MEDIUM, KNOWN TYP-14, probes f14/f15): a `::` constant or a by-value parameter is accepted as a mutable receiver

The same code path ignores mutability and the rvalue-ness of the root.

- `m06_const_recv.a7` (`C :: Counter{value: 1}`, `increment(C)`): a7=0, zig=1,
  `expected type '?*T', found '*const T'` … "cast discards const qualifier".
- `m32_byvalue_param_forward.a7` (`outer :: fn(c: Counter) { bump(c) }` where
  `bump` takes `ref Counter`): a7=0, zig=1, same message. This is the shape a
  "method calling another method" would take.

Correctly rejected controls: `m09_literal_recv.a7` (`increment(Counter{value: 1})`)
and `m10_temp_recv.a7` (`increment(mk())`) both give a7=6, "Argument type
mismatch: expected 'ref Counter', got 'Counter'" — a STRUCT_INIT and a CALL are
not in `_is_lvalue_expression` (`a7/passes/type_checker.py:1890-1896`).

Fix direction: require a mutable root as well as identity. **Changes an
accepted, building program:** no.

### MTH-10 (MEDIUM, KNOWN TYP-15): a by-value receiver's field can be written

`a7/passes/type_checker.py:851-859` checks `is_mutable` only when the assignment
target is a bare `IDENTIFIER`, so SPEC 6.3's parameter immutability is not
enforced for field writes.

- `m16_byvalue_mutate.a7` (`bump :: fn(c: Counter) { c.value = 5 }`): a7=0,
  zig=1, "cannot assign to constant".
- Control `m33_byvalue_param_assign.a7` (`c = Counter{value: 9}`, an identifier
  target): a7=6, "Cannot assign to immutable binding" — correctly rejected. The
  two forms disagree.

Fix direction: walk to the root symbol of a field or index target before the
mutability check. **Changes an accepted, building program:** no.

### MTH-11 (MEDIUM, KNOWN B11 / SAF-25): `defer` of a receiver field write emits `defer void;`

- `m18_defer_recv_write.a7` (`defer c.value = 0`): a7=0, zig=1, "value of type
  'type' ignored". Emitted body: `fn bump(c: ?*Counter) void { defer void; c.?.value += 1; }`.

The deferred statement is silently discarded by the backend, which is the only
reason SAF-25's fact bug is not observable
(`docs/audits/2026-09-16/compiler/safety.md:311-340`).

Fix direction: covered by the scheduled B11 backend fix. **Changes an accepted,
building program:** no.

### MTH-12 (MEDIUM, KNOWN PAR-02 + PAR-03/F2, new manifestation): a qualified struct literal through an import alias silently deletes the enclosing function

`sh.Counter{value: 1}` is not recognised as a struct literal — the heuristic in
`_should_parse_struct_literal` (`a7/parser.py:126-161` in this tree;
`lookback_distance = min(10, self.position)` at `:143`, the control-keyword test
at `:157`, the default `return True` at `:160-161`) handles a bare identifier or
`Name(...)`, not a field chain
(`docs/audits/2026-09-16/compiler/parser.md:121`). Top-level recovery then drops
the whole declaration (PAR-03/F2) with no diagnostic.

- `m34_import_recv.a7`: a7=0, zig=0, and the emitted `.zig` is seven lines with
  no `pub fn main` and no `__a7_user_main` at all:

  ```zig
  const Counter = struct { value: i32, };
  fn module_imp_shape__increment(c: ?*Counter) void { c.?.value += 1; }
  ```

  `uv run a7 m34_import_recv.a7 --mode ast --format json` (exit 0) shows
  `"ok": true` with exactly two declarations, both `IMPORT`
  (`tmp/audit/2026-09-18/methods/m34_ast.json`). `zig build-obj` exits 0 because
  an object file needs no `main`, so nothing in the pipeline notices.

This is the receiver-through-an-import case from the audit scope: the program
looks like it compiled and produced nothing.

Fix direction: covered by PAR-02 and PAR-03; separately, the compile mode should
fail when the program has no `main`. **Changes an accepted, building program:**
no — `m34` produces no program today.

### MTH-13 (MEDIUM, NEW; the second probe is KNOWN ZIG-24/B4): an array element cannot be a receiver

Both ways of getting an array of structs fail in the backend.

- NEW: `m13_index_recv2.a7` (`arr := [Counter{value: 1}, Counter{value: 2}]`,
  then `increment(arr[0])`): a7=0, zig=1, "runtime value contains reference to
  comptime var" … "'runtime_value.?' points to comptime field". The array literal
  is emitted as a comptime aggregate, so `&arr[0]` is not a runtime pointer.
  `grep -n -i "comptime var\|comptime field\|reference to comptime" docs/audits/2026-09-16/compiler/*.md`
  finds nothing.
- KNOWN ZIG-24 (KNOWN-family B4,
  `docs/audits/2026-09-16/compiler/backend.md:373-375`):
  `m08_index_recv.a7` (`arr: [2]Counter` declared then assigned): a7=0, zig=1 at
  the declaration — `var arr: [2]Counter = [_]Counter{0} ** 2;`, "expected type
  'Counter', found 'comptime_int'". ZIG-24's probes are `[2]string` and
  `[2][2]i32`; `[2]Counter` is the same defect on a struct element.

Fix direction: emit an array literal into storage with a runtime type when its
address is taken; ZIG-24 covers the default initializer. **Changes an accepted,
building program:** no.

### MTH-16 (MEDIUM, NEW): no struct field is ever a safety fact, so arithmetic on a receiver field is always rejected

Evidence. `a7/safety.py:678-683` — `_facts_from_condition` returns `{}` unless
the left side of the condition is a bare `IDENTIFIER`, so `if c.d != 0` teaches
the pass nothing. The FIELD_ACCESS branch (`:425-437`) records a fact only for
the field names `ptr` and `len`. Every other field read carries the empty
`ValueFact()`.

- `m45_field_fact_false_reject.a7` — `c := Cfg{d: 4}; 100 / c.d`, no receiver
  involved: a7=6, "division/modulo divisor must be non-zero: divisor may be
  zero". A divisor whose value is a literal four lines above is rejected.
- `m46_recv_len_fact.a7` — the same division inside a receiver function
  (`div :: fn(c: ref Cfg) i32 { ret 100 / c.d }`): a7=6, same message.
- `m21_recv_div_zero.a7` — `if c.d != 0 { zero_it(c); 100 / c.d }`: a7=6. The
  guard is rejected, so MTH-2's fact-survival hole is not reachable through a
  field; it is reachable through a scalar (`m29`).

The rejection is conservative, not unsound, but it means no receiver function can
divide by one of its own fields, and no guard can make it legal.

Fix direction: key facts by root symbol plus field path, and invalidate any path
whose prefix is written or passed by `ref`. **Changes an accepted, building
program:** no — these are false rejections.

### MTH-14 (LOW, KNOWN ZIG-25 / B10 / B15; safety-side cause SAF-19): a local that shadows a receiver function's name produces invalid Zig

- `m36_local_shadow_fn.a7` (`peek :: fn(c: ref Counter) i32`, then `peek := 5`
  inside `main`): a7=0, zig=1, "local constant shadows declaration of 'peek'".
  ZIG-25's probe `p156` is the same shape with a non-receiver function
  (`docs/audits/2026-09-16/compiler/backend.md:376-378`); the cause is that
  shadow renaming ignores file-scope names
  (`docs/audits/2026-09-16/compiler/safety.md:541`).

**Changes an accepted, building program:** no.

### MTH-15 (LOW, NEW): a read-only receiver forces the caller's variable into `var`

`a7/ast_preprocessor.py:352-358` and `a7/backends/zig.py:246-252` add every
implicit-`ref` argument's root to the mutation set, whether or not the callee
writes through it. `m02_ref_read.a7` emits `var v = Vec2{ .x = 3, .y = 4 };` for
a receiver that only reads. Zig accepts it (`&v` counts as a use), so this is a
lost `const`, not a defect that shows. It becomes visible the moment callee
effect summaries exist (Wave 5 phase B, `docs/plan/execution.md:434`).

**Changes an accepted, building program:** no.

## What is missing

| Item | What exists now | What it needs | Decision owner | Priority for v1 |
| --- | --- | --- | --- | --- |
| Dot-call syntax `v.length()` | Nothing. `m05` a7=6; `docs/SPEC.md:473-474` calls it planned; field access has no function fallback (`type_checker.py:1827-1833`) | A packet with before/after examples under the language-change rule in `CLAUDE.md`; then a resolution rule (first parameter match? declared receiver?), an ambiguity rule against fields of function type, and a name-resolution order | **None exists.** `grep -rn -i "method\|\.append(\|dot\|postfix\|sugar\|UFCS" docs/plan/decisions.md docs/plan/execution.md docs/plan/README.md` returns only `execution.md:428` (C2 migrating `017_methods`) and `execution.md:176` (parser postfix forms). `docs/plan/audit/language-audit-checklist.md:67` already says "Needs a packet before track 8a (collections)" | **Blocking for track 8a.** See below |
| Facts for receiver fields | No field is ever a fact except `ptr` and `len` (`safety.py:425-437`, `:678-683`) | Path-keyed facts with prefix invalidation | Wave 4 track 5 proof repair (`docs/plan/execution.md:404`) names "second write through scalar `ref`" but not field paths | High — MTH-16: no receiver can divide by one of its own fields, guarded or not |
| Call-site nil proof for `ref` | None (MTH-1) | SAF-1's fix, or the `ref`/optional-`ref` split | Phase C2 removes `nil` and stored/returned `ref` (`docs/plan/execution.md:428`) | Critical |
| Fact invalidation at calls | None (MTH-2) | Effect summaries over the acyclic call graph | Wave 5 phase B (`docs/plan/execution.md:432`) | Critical |
| Generic receivers | Rejected (MTH-7) | Deferred field resolution or a struct-shaped constraint | P-M50 monomorphization strategy (`docs/plan/execution.md:405`) | Medium |
| Struct type aliases | Unresolvable (MTH-6) | Alias resolution for user-defined types | None | Medium |
| Receivers across file imports | Broken (MTH-3, MTH-12) | Argument checking on the `file_module_call` path | G6 remainder packet, modules (`docs/plan/execution.md:440`) | High |
| User-facing documentation of the receiver idiom | None outside `docs/SPEC.md:806-831` | A "What Works" line and a site entry, or removal of SPEC 6.5 | None | Medium |

**Can track 8a proceed without dot-call syntax?** Not as its examples are
written. `docs/plan/memory.md:182-186` is labelled "Proposed syntax" and uses
`a.append(1)` and `b.append(2)`; `a7` rejects that form today (`m05`, a7=6,
"Struct 'Vec2' has no field 'sum'"). Either the memory-plan examples are
rewritten to `append(a, 1)` — which is what SPEC 6.5 and `examples/017_methods.a7`
actually do — or a packet is opened for dot-call syntax before Wave 5 phase C1
delivers `List`, `Map` and `Table(T)` (`docs/plan/execution.md:431`). No such
packet exists. Rewriting the examples is the smaller change and needs no
language approval; adding the syntax needs one under the approval rule in
`CLAUDE.md`.

## Checked and correct

- No overloading. `m27_overload.a7` (two `get` functions on `A` and `B`): a7=6,
  "Already defined: Function 'get'". `m26_collide_type.a7` (a function named
  after a struct): a7=6, "Already defined: Function 'Vec2'". SPEC does not
  promise overloading, and the compiler agrees.
- A receiver function may share a name with a struct field (`m25`, a7=0, zig=0)
  and with a stdlib function reached only through an alias (`m37`, a7=0, zig=0).
- A user function named `sqrt` is *not* rewritten to `@sqrt` (`m28`, emitted
  `sqrt(&v)`); the rewrite requires `stdlib_canonical` to start `std.math.`
  (`a7/backends/zig.py:1634-1640`) or the emitted callee to start `math.`
  (`:1648-1653`). SAF-9's "user function named like a typed math builtin"
  concerns `_MATH_BUILTIN_MAP` keys `sqrt_f32`/`sqrt_f64` etc.
  (`a7/backends/zig.py:1615-1620`), which a receiver function's name would have
  to match exactly.
- Storing a receiver into a file-scope `ref` is rejected: `m35_escape_global.a7`,
  a7=6, "reference must be proven non-nil" — the global's own fact is
  `maybe_nil`, so the later read fails. The store itself is not diagnosed.
- SPEC 3.5's two examples (`docs/SPEC.md:380-396`) both compile and build:
  `m43_spec35.a7`, a7=0, zig=0.
- `a7/passes/name_resolution.py` contains no `ref`-specific handling
  (`grep -rn "ref\|TYPE_POINTER" a7/passes/name_resolution.py` returns nothing),
  and `a7/passes/semantic_validator.py` touches references only for `del`, `nil`
  and deref (`:386-393`, `:451`, `:485`, `:1465-1476`). Neither pass knows what a
  receiver is; the whole feature lives in the type checker's argument loop.

## Test gaps

- No test compiles, builds or runs a receiver function. `grep -rn "ref Counter\|ref Vec2\|ref Point\|ref Inner" test/`
  returns two hits, both parser-only:
  - `test/test_parser_integration.py:388` puts `"fn(self: ref Vec2) {}"` in a
    dictionary of keyword snippets inside a test that prints a "KEYWORD SUPPORT
    ANALYSIS" table; it exercises the tokenizer and parser only.
  - `test/test_parser_missing_constructs.py:228-239`
    (`test_ref_field_access_is_plain_field_access`) asserts that `p.value` parses
    to a `FIELD_ACCESS` whose object is an `IDENTIFIER`. That is a restatement of
    the parser's own structure — it would pass whatever the semantics are.
- No test asserts that `v.length()` is rejected, so the SPEC 4.3 promise has no
  guard against it silently starting to parse as something else.
- No test covers mutation through a receiver, a nil receiver, a receiver that is
  a struct field or array element, a generic receiver, or a receiver reached
  through an import. Each of MTH-1, MTH-3, MTH-6, MTH-7, MTH-9, MTH-13 would have
  been caught by one.
- `examples/017_methods.a7` is the only example named for the feature, and it
  exercises one form: a `ref` struct parameter whose field is incremented. It
  does not read a field, does not return a value, and does not use the SPEC 6.5
  shape (`length(v)` returning `f32`).

## Not verified

- Run-time behavior of every `ref` receiver form. The probing rules forbid
  building and running a probe that uses `ref`, so `m02`, `m04`, `m07`, `m15`,
  `m17`, `m24`, `m29`, `m43`, `m47` and the five examples were checked only to
  `zig build-obj`. MTH-1's null unwrap and MTH-2's division by zero are read off
  the emitted Zig, not observed.
- Debug vs ReleaseFast divergence for MTH-1 and MTH-2. Zig's Debug builds panic
  on a null unwrap and on division by zero; ReleaseFast does not check either.
  This is Zig behavior I did not run here — UNVERIFIED for these programs.
- The release gate. I did not run `./run_all_tests.sh`,
  `scripts/verify_examples_e2e.py` or `scripts/build_examples.py`; the five
  receiver examples were compiled and `zig build-obj`-checked individually
  instead, so their run-time output is UNVERIFIED in this session.
- Whether the C1, C4 or C2 worktrees change any of the above. Not read.
- `m42_array_slice_ref.a7` also produced "Cannot assign to immutable binding:
  's' is immutable" for `s = s` where `s: ref []i32`, while `m15` accepts
  `c = Counter{...}` for `c: ref Counter`. I did not isolate the cause and file
  no finding for it.

claims checked: 107

(55 distinct file:line citations read in this session, 46 probe exit-code
results taken from the `.result` files under
`tmp/audit/2026-09-18/methods/`, and 6 grep results quoted with their outcome.)
