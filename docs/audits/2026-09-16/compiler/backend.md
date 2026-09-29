> **Source:** Claude audit subagents, full audit of the A7 Zig backend, run against commit `701c679` with Zig 0.16.0; started by one auditor (interrupted by plan mode) and finished by a second from the first's saved state; shared instructions in `tmp/audit/compiler/PROMPT-COMMON.md`.  
> **Date:** 2026-09-16 to 2026-09-17.  
> **Status:** Evidence. Body preserved verbatim. Probes and logs it cites stay under `tmp/audit/compiler/backend/`, which is not tracked. The report discloses three probes that were run before being re-marked compile-only.

# Zig backend audit

Scope: `a7/backends/zig.py` (2395 lines), `a7/backends/base.py` (75), `a7/backends/__init__.py` (30).
Revision: commit `701c679`; `git status --short a7/` is empty, so the backend sources match that commit (`backend/gitstat.log`).
Toolchain: Zig 0.16.0 (`backend/z39.log`).

This report finishes an audit that was interrupted before it wrote anything. The first auditor's saved state is in
`~/.claude/plans/iterative-bouncing-tarjan-agent-a67104b9ceb4555a9.md`. Its probes, records and logs are in
`tmp/audit/compiler/backend/` (`probes/`, `out/<probe>.rec`, `run1.log`..`run6.log`). This session re-ran the
operator matrices, re-ran every CRITICAL and HIGH probe (`run7.log`, `run8.log`, `run9.log`), re-read the cited
code, and added probes `p009e`, `p109f`, `m4` and the guarded matrices `p170b` and `p171b`.

All paths below are relative to `tmp/audit/compiler/backend/` unless they start with `a7/`, `docs/`, `test/` or
`scripts/`.

Disclosure: the first auditor built and ran `p013_format_specs`, `p052_slices` and `p091_implicit_ref_args` as
run-allowed. It then re-marked them compile-only because they use `ref` or stored slices. Their run output
(`run*.log`) is not used as evidence anywhere in this report.

Finding IDs ZIG-10 to ZIG-40 were assigned from probe names by a planner who did not see the probes
(`docs/plan/fix-program/backend-fix-plan.md:73-79`). They are kept. Where a probe shows something different, the
finding says "mapping corrected". ZIG-41 is new in this report and is not in the planner's coverage table.

Severity criterion:
- CRITICAL: A7 accepts the program, Zig builds it, and ordinary code silently computes or prints a wrong result.
- HIGH: the same kind of silent wrong result under narrower conditions; an operation that can hit undefined behavior
  in ReleaseFast with no safety approval; or silent corruption of program output.
- MEDIUM: A7 accepts and Zig rejects, so the failure is visible; a wrong rejection at the codegen stage; a gap in
  defense in depth.
- LOW: output formatting, dead code, errors reported at the wrong stage, `zig fmt`, test structure.

KNOWN means the defect is listed in `docs/plan/README.md` "Defects reproduced in Wave 0" or in
`docs/plan/audit/evidence/*.md`. KNOWN-family means the same known defect shows up at a new site.

## Summary

| Severity | Total | NEW | KNOWN or KNOWN-family |
|---|---|---|---|
| CRITICAL | 2 | 2 | 0 |
| HIGH | 7 | 7 | 0 |
| MEDIUM | 26 | 20 | 6 (ZIG-18, 22, 24, 25, 28, 38) |
| LOW | 6 | 6 | 0 |
| Total | 41 | 35 | 6 |

| ID | Sev | Status | One line |
|---|---|---|---|
| ZIG-1 | CRITICAL | NEW (= SAF-7) | A folded literal takes the type of a dead node through `id()` reuse; `total={}` prints `A` |
| ZIG-2 | CRITICAL | NEW | An if-expression is emitted without parentheses, so `(if c {a} else {b}) + 10` binds wrongly |
| ZIG-3 | HIGH | NEW | Untyped immutable locals become Zig comptime values: f128 float math and no i32 overflow |
| ZIG-4 | HIGH | NEW | `\x80`-`\xff` string escapes are emitted as 2-byte UTF-8 characters |
| ZIG-5 | HIGH | NEW (B14 sibling) | Any identifier named `io` with a `println` field is lowered to stdout printing |
| ZIG-6 | HIGH | NEW | Struct literal fields are evaluated in written order, not declaration order (SPEC A.1) |
| ZIG-7 | HIGH | NEW | Shifts by a runtime amount emit `@intCast` with no safety obligation |
| ZIG-8 | HIGH | NEW | Union field reads have no obligation; an inactive-field read builds |
| ZIG-39 | HIGH | NEW (parser.md S1) | With stdout redirected to a file, each print overwrites offset 0; only the last line survives |
| ZIG-9 | MEDIUM | NEW | C-style `for` update skips approval and implicit dereference |
| ZIG-10 | MEDIUM | NEW | Control bytes in char literals are emitted raw; Zig rejects them |
| ZIG-11 | MEDIUM | NEW | Infinite float literal or fold is emitted as `inf.0` |
| ZIG-12 | MEDIUM | NEW | Match on int without `else`, on string, or on float is accepted; Zig rejects all three |
| ZIG-13 | MEDIUM | NEW (= SAF-18) | Name-keyed mutation analysis emits `var` for a sibling-block local that is never mutated |
| ZIG-14 | MEDIUM | NEW | An unused local `K :: 5` gets no discard |
| ZIG-15 | MEDIUM | NEW | `main` returning `i32` or taking parameters is accepted |
| ZIG-16 | MEDIUM | NEW | `defer f()` with non-void `f` is emitted without a discard |
| ZIG-17 | MEDIUM | NEW | Locals named like Zig primitives (`u3`, `i7`, `f80`) |
| ZIG-18 | MEDIUM | KNOWN-family B12 | Zig keywords as field, function, parameter, type or variant names |
| ZIG-19 | MEDIUM | NEW | User names collide with generated names (`__a7_stdout_print`, `__a7_user_main`, `std`, `__a7_match_N`) |
| ZIG-20 | MEDIUM | NEW | Enum explicit values that do not fit `enum(i32)` |
| ZIG-21 | MEDIUM | NEW | `~5` on a literal and `-x` on `u32` are accepted |
| ZIG-22 | MEDIUM | KNOWN-family B13 | Float `%=` is emitted as `%=` |
| ZIG-23 | MEDIUM | NEW | An unused loop label is emitted |
| ZIG-24 | MEDIUM | KNOWN-family B4 | An uninitialized `[2]string` or `[2][2]i32` defaults to `0` |
| ZIG-25 | MEDIUM | KNOWN-family B10/B15 | A capture or local with the same name as a global declaration |
| ZIG-26 | MEDIUM | NEW | The checker counts `{x}` as a placeholder; the backend emits it as literal text |
| ZIG-27 | MEDIUM | NEW | Inside a file module, calls to the module's own functions are not prefixed (mapping extended) |
| ZIG-28 | MEDIUM | KNOWN | Reproduced B11, B9, B15, B6 (with C4b3), B10 |
| ZIG-29 | MEDIUM | NEW | Generic functions without a header and generic `ref` fields are rejected at codegen |
| ZIG-30 | MEDIUM | NEW | `d := a + b` on arrays is rejected at codegen |
| ZIG-33 | MEDIUM | NEW | `"{{b}}"` prints `{{b}}`; the checker treats `{{` as an escape |
| ZIG-38 | MEDIUM | partly KNOWN (S6, S7, S8; overflow under decision L5) | Other operations with no backend approval: `del`, overflow, `undefined` fallbacks |
| ZIG-40 | MEDIUM | NEW | Nested functions: uncallable (exit 6), or unapproved body (exit 7) |
| ZIG-41 | MEDIUM | NEW (outside plan table) | If or match expressions with literal arms and a runtime condition: Zig rejects |
| ZIG-31 | LOW | NEW | Using an io call as a value is rejected at codegen (exit 7), not in semantics |
| ZIG-32 | LOW | NEW | 400 nested blocks: backend RecursionError, reported as exit 7 |
| ZIG-34 | LOW | NEW | Print formats: enums print as `.Green`, structs as `.{ .x = 1 }`, `1e300` as 301 digits, slices as `{any}` |
| ZIG-35 | LOW | NEW | `zig fmt --check` fails on standalone blocks, `fall` and capture-match output |
| ZIG-36 | LOW | NEW | Dead code and unreachable fallbacks |
| ZIG-37 | LOW | NEW | Backend test helper and test assertions (details under Test gaps) |

## CRITICAL

### ZIG-1: a folded constant inherits a dead node's type (CRITICAL, NEW; the fix plan equates it with SAF-7)

What is wrong: the backend looks up semantic types by `id(node)`. The AST preprocessor replaces folded expressions
with new LITERAL nodes after type checking. CPython reuses the ids of freed nodes, so a new literal can pick up the
type-map entry of an unrelated dead node. That entry decides the print format, float or int division, and other
lowering choices.

Evidence:
- `a7/backends/zig.py:60` `self._type_map = type_map or {}`. There are id-keyed lookups at 1366, 1388, 1418, 1551,
  1577-1578, 1655, 1683, 1708, 1732, 1739, 1746 and 2223. For example, 2223:
  `ty = self._type_map.get(id(arg)) if arg else None`, and 2228-2229 `if name == "char": return "c"`.
- The new nodes come from `a7/ast_preprocessor.py:570, 581, 644, 670, 687` (`kind=NodeKind.LITERAL` in `_fold_unary`
  and `_fold_binary`).
- `probes/p081e_idreuse_natural.a7`: `same := 'x' == 'y'; io.println("same={}", same); io.println("total={}", 60 + 5)`.
  Re-run in this session (`run8.log`): a7 exit 0, build-obj 0. The emitted line is
  `__a7_stdout_print("total={c}\n", .{65});` (`out/p081e_idreuse_natural.rec`). Debug and ReleaseFast both print
  `same=false` / `total=A`.
- `p081f_idreuse_natural2`: prints `B true A`; `64 + 1` should print `65` (`run8.log`).
- `p082_fold_idreuse_string` (compile-only): `{s}` is chosen for a folded integer. Zig rejects it:
  `invalid format string 's' for type 'comptime_int'` (`out/p082_fold_idreuse_string.rec`).
- `idreuse.py` monkeypatches `ASTPreprocessor.process` and lists new nodes whose id is a type-map key. It finds 1 in
  p081e (`('LITERAL', INTEGER, 65, 'char')`, `p081e_idreuse_natural.idr.log`) and 899 in `p080_fold_many`
  (`idreuse1.log`).
- INFERENCE: the safety `BackendPlan` is also id-keyed (`a7/safety.py:214-216`,
  `self.approved.get((id(node), operation))`). Folding only creates literals, and the backend does not ask for
  approval on literals, so no forged approval was found. This was not proven impossible.

Fix direction: copy the replaced node's type entry to the folded node and keep replaced nodes alive until codegen
(fix plan C1). Later, key the type map by stable node identity (Wave 3 IR).
Changes programs that A7 accepts and Zig builds: yes (their output changes from wrong to right).

### ZIG-2: if-expression emitted without parentheses (CRITICAL, NEW)

What is wrong: `_emit_if_expr` returns `if (c) a else b` with no enclosing parentheses. When that string becomes the
left operand of a binary operator or a field access, Zig parses the operator as part of the `else` branch.

Evidence:
- `a7/backends/zig.py:1802` `return f"if ({cond}) {then_val} else {else_val}"`. Binary emission wraps only the whole
  expression: 1595 `return f"({left} {zig_op} {right})"`.
- `probes/p001b_if_expr_in_binary_runtime.a7`: `ret (if c { a } else { b }) + 10` emits
  `return (if (c) a else b + 10);` (`out/p001b...rec` line 15). Re-run in this session: Debug and ReleaseFast print
  `1 12` / `1 6`. The correct output is `11 12` / `3 6`.
- `p109b_if_expr_bool_eq_runtime`: `(if c {a} else {b}) == false` emits `(if (c) a else b == false)`. It prints
  `true false true false`; the correct output is `false true true false`. Only the two calls with `c` true are
  wrong: Zig parses `if (c) a else (b == false)`, so they return the raw `a`.
- `p109e_if_expr_field_runtime_value`: `(if c { p } else { q }).x` emits `const v = if (c) p else q.x;` and prints
  `.{ .x = 1, .y = 2 }`. Mapping note: this miscompile needs ZIG-3 as well. `c := true` becomes the comptime
  `const c = true`, so Zig never type-checks the dead `q.x` branch. With a runtime condition
  (`p109f_if_expr_field_param_cond`, new, compile-only), Zig rejects the same shape:
  `expected type 'i32', found '...Pt'` at `return if (c) p else q.x;` (build-obj exit 1).
- `p001d_if_expr_compare` (`== 2` on an i32 if-expression) is rejected by Zig: `expected type 'bool', found 'i32'`.
- Correct positions (first auditor's runs, `run*.log`): right operand and call argument (`p109c`, `1102 1104`), and
  unary operand (`p109d`, `-4 -6`).

Fix direction: emit `(if (c) a else b)`. Match expressions are already primary expressions in Zig.
Changes programs that A7 accepts and Zig builds: yes.

## HIGH

### ZIG-3: untyped immutable locals emitted as Zig comptime values (HIGH, NEW)

What is wrong: the type checker gives untyped literals `i32` or `f64`. The backend emits `const x = <literal>;` with
no type, so Zig treats `x` as `comptime_int` or `comptime_float`. Arithmetic on such locals then runs at compile time
with arbitrary precision instead of the A7 type.

Evidence:
- `a7/passes/type_checker.py:1165-1168`: `INTEGER: return I32  # Default integer type`,
  `FLOAT: return F64  # Default float type`.
- `a7/backends/zig.py:683-684`: when there is no `explicit_type` and no `resolved_type`,
  `self.output.write(f"{keyword} {emit_name} = {val};\n")`.
- `probes/p140_comptime_float_semantics.a7`, re-run in this session, Debug and ReleaseFast:
  - `a := 0.1; b := 0.2; a + b` prints `0.30000000000000000000000000000000004`, while typed `f64` prints
    `0.30000000000000004`.
  - `x / y` with `1.0` and `3.0` prints `0.3333333333333333333333333333333333`.
  - `math.sqrt(t)` prints `1.414213562373095048801688724209698`. These are f128 digit counts, not f64.
- `p140b_comptime_int_overflow` (compile-only): `x := 2147483647; y := x + 1` emits
  `const x = 2147483647; const y = (x + 1);`, and build-obj exits 0. As A7 `i32` this addition overflows. Zig
  computes `2147483648` at compile time and never checks it. The binary was not run.
- The same cause produces Zig rejections: ZIG-12 (`switch on type 'comptime_int'`), ZIG-41 and ZIG-2's p109e.

Fix direction: emit the checker's type on every untyped local (`const a: f64 = 0.1;`). Fix plan P-BK.1.
Changes programs that A7 accepts and Zig builds: yes (printed floats change; some programs that build today would
overflow or be rejected).

### ZIG-4: `\x80`-`\xff` string escapes emitted as UTF-8 (HIGH, NEW)

What is wrong: the tokenizer accepts `\xff` in a string, and the backend writes the resulting Python character as a
literal non-ASCII character. That character is 2 bytes in the Zig source, so the A7 string gets longer and its bytes
change.

Evidence:
- `a7/backends/zig.py:2296-2303`: only `code < 0x20 or code == 0x7F` is hex-escaped; anything else goes through
  `out.append(ch)`.
- SPEC: `docs/SPEC.md:163` `'\x41'    // Hex escape (A) - ASCII only`, and `docs/SPEC.md:2170`
  `| \xHH | 0-127 | Hex escape (2 digits, ASCII only) |`. The tokenizer accepts values above 127
  (`p009d` a7 exit 0).
- `probes/p009e_high_hex_literal_iter.a7` (new in this session, no stored slice):
  `for ch in "\xff\x80A" { if ch == 'A' { n += 100 } n += 1 }` emits `for ("ÿ<U+0080>A") |ch|` (U+0080 is invisible in the record and is shown here as `<U+0080>`; it is emitted as the UTF-8 bytes C2 80) and prints `105` in
  Debug and ReleaseFast. The 3-byte string would print `103`. `p009d` (the same loop over a local) also prints `105`.

Fix direction: reject `\xHH > 0x7F` in the tokenizer as SPEC says (execution P-LEX, TOK-01). If it stays accepted,
emit `\xHH` bytes instead.
Changes programs that A7 accepts and Zig builds: yes.

### ZIG-5: identifiers named `io` hijacked as stdlib io (HIGH, NEW, sibling of KNOWN B14)

What is wrong: `_is_io_call` and `_scan_features` fall back to the raw identifier text `io`. A user struct value named
`io` with a function field `println` is therefore lowered to the generated stdout print, and the user's function is
never called.

Evidence:
- `a7/backends/zig.py:2162-2167`: `if obj and obj.kind == NodeKind.IDENTIFIER and getattr(obj, 'name', '') == 'io':`
  then `return field in ('println', 'print', 'eprintln')`. The same pattern is at 144-149.
- `probes/p077b_io_named_struct_hijack.a7`: std io is imported as `console`, `io := Printer{println: show}`, then
  `io.println("direct")` is called. The emitted line is `__a7_stdout_print("direct\n", .{});`. Re-run in this session:
  it prints `direct` / `show called with through g`. The correct first line is `show called with direct`.

Fix direction: use only the `stdlib_canonical` annotation from name resolution (fix plan C2, shared with PIP-3,
SAF-9, B14).
Changes programs that A7 accepts and Zig builds: yes.

### ZIG-6: struct literal fields evaluated in written order (HIGH, NEW)

What is wrong: named field initializers are emitted in source order, and Zig evaluates them in that order. SPEC
requires declaration order.

Evidence:
- SPEC `docs/SPEC.md:2061-2066`, "A.1 Evaluation Order ... 4. Field initialization: declaration order".
- `a7/backends/zig.py:1885-1890` loops over `field_inits` in list order: `parts.append(f".{fi.name} = {val}")`.
- `probes/p003_struct_init_eval_order.a7`: `Pt{y: tag(2), x: tag(1)}` emits `Pt{ .y = tag(2), .x = tag(1) }`.
  Re-run in this session: it prints `eval 2` then `eval 1`.

Fix direction: evaluate the fields into temporaries in declaration order, or reorder field inits in the preprocessor.
The fix plan (C3) says the class changes if the owner reads A.1 item 4 as storage order.
Changes programs that A7 accepts and Zig builds: yes (side-effect order).

### ZIG-7: shifts by a runtime amount have no safety obligation (HIGH, NEW)

What is wrong: `<<` and `>>` with a non-literal right operand are emitted as `x << @intCast(n)`. No proof checks that
`n` is non-negative and below the bit width. `ObligationKind` in `a7/safety.py:177-185` has no shift kind. A runtime
amount of 8 or more on `u8` panics in Debug and is undefined behavior in ReleaseFast (INFERENCE from Zig semantics;
not run, because the rule forbids it). Compound `<<=` does not even emit the cast.

Evidence:
- `a7/backends/zig.py:1586-1593`: `return f"({left} << @intCast({right}))"`. There is no
  `_require_backend_approval`, which is used for div and mod at 1567-1568.
- `probes/p007e_shift_runtime.a7` (compile-only): `sh :: fn(x: u8, n: i32) u8 { ret x << n }` called with
  `k: i32 = 9`. It emits `return (x << @intCast(n));`, and a7 and build-obj both exit 0 (`run8.log`).
- Where the hole is: `p007c` and `p007d` exit 6 only because a literal `1` is passed to a `u8` parameter ("Argument
  type mismatch", the KNOWN C6 note), not because of a shift check. `p007` and `p007b` are rejected by Zig only
  because the amount is comptime-known (`type 'u3' cannot represent integer value '9'`).
- `p047e_shift_assign_runtime_param`: `x <<= n` with `n: u32` emits `x <<= n;`. Zig rejects it:
  `expected type 'u5', found 'u32'`.

Fix direction: a shift-amount obligation (execution packet P4, TYP-06 c14), plus a `@intCast` for `<<=` (Z4).
Changes programs that A7 accepts and Zig builds: yes (runtime-amount shifts that build today would need a proof).

### ZIG-8: union field reads have no safety obligation (HIGH, NEW)

What is wrong: reading an untagged or tagged union field is emitted as a plain `v.f` with no approval. Reading the
inactive field through a parameter builds. INFERENCE from Zig semantics: this panics in Debug for tagged unions and
safety-checked untagged unions, and is undefined behavior in ReleaseFast. The probes are compile-only, so this was
not observed at run time.

Evidence:
- `a7/backends/zig.py:1713-1721` `_emit_field_access` asks for approval only when `implicit_deref_object` is set.
- `a7/safety.py:184` defines `UNION_FIELD = auto()`. `grep -rn UNION_FIELD a7/` finds only that definition
  (`unionfield.log`).
- `probes/p056b_union_wrong_field_runtime.a7`: `read_f :: fn(v: Num) f32 { ret v.f }` with `Num{i: 1}` emits
  `return v.f;` and build-obj exits 0.
- `p057b_tagged_union_wrong_field_runtime`: `union(tag)` emits `union(enum)` and `return r.err;`, and build-obj
  exits 0.
- For comparison, the local-variable forms `p056` and `p057` are caught by Zig at comptime:
  `access of union field 'f' while field 'i' is active`.

Fix direction: reject union field reads until G5 decides tagged matching (execution P5).
Changes programs that A7 accepts and Zig builds: yes.

### ZIG-39: redirected stdout keeps only the last print (HIGH, NEW; symptom first seen in `tmp/audit/compiler/parser.md:526` S1, planned in `docs/plan/execution.md:103` C3)

What is wrong: every `io.println` creates a new `std.Io.File.stdout().writer(...)`. In Zig 0.16 that writer is
positional and starts at offset 0. On a regular file, each call therefore writes over the start of the file. Pipes
are unseekable, so the writer falls back to streaming and the bug does not show there. This session confirmed the
root cause, which parser.md left UNVERIFIED.

Evidence:
- `a7/backends/zig.py:164-171` emits
  `var __a7_writer = std.Io.File.{stream}().writer(__a7_io.?, &__a7_stream_buf);` inside the print helper, once per
  call.
- Zig std: `lib/std/Io/File.zig:600-601` `pub fn writer(...) Writer { return .init(file, io, buffer); }`, and
  `:607` has `writerStreaming`. `lib/std/Io/File/Writer.zig:36-42` sets `init` to `.mode = .positional`.
  `:98-121` `drainPositional` calls `fileWritePositional(..., w.pos)`, and on `error.Unseekable` switches to
  streaming (`z39_std.log`, `z39_std2.log`).
- `p170b_int_operator_matrix_guarded` Debug binary, this session (`p170b.diff.log`, `z39.log`):
  - `| cat`: 929 bytes, identical to `p170_expected.txt`.
  - `> file`: 60 bytes, only `usize false false true true false true 18446744073709551595`.
  - `1<>` onto an existing 1200-byte file: the file stays 1200 bytes; its first 60 bytes are the last line and the rest
    is the old content.
  - `>>` append: all 30 lines follow `first` (31 lines). INFERENCE: this works because Linux `pwrite` ignores the
    offset under `O_APPEND`.
- INFERENCE, not probed: `__a7_stderr_print` has the same shape (line 168 with `stream == "stderr"`), so `2> file`
  behaves the same way.

Fix direction: use `writerStreaming`, or one writer shared for the whole process (fix plan C3).
Changes programs that A7 accepts and Zig builds: yes (redirected output changes from corrupted to complete).

## MEDIUM

Unless a finding says otherwise, each MEDIUM item below is A7 accepting a program (exit 0) that Zig rejects at
`build-obj`. The failure is visible, and fixing it does not change any program that builds today (compat: no). The
error quotes come from `out/<probe>.rec`, collected in `medium_errs.log`. The first auditor ran these probes; this
session re-read their records and sources (`medium_src.log`) but did not re-run them.

- **ZIG-9 (NEW): C-style `for` update skips approval and implicit dereference.**
  - Code: `a7/backends/zig.py:2366-2373` `_emit_statement_as_expr` emits `f"{target} {zig_op} {value}"`. It never
    calls `_require_backend_approval`, which the statement path calls at 1316 and 1322-1323, and it ignores
    `implicit_deref_target`.
  - Probe: `p034_for_update_ref_param` (`for i := 0; i < 3; p += 1` with `p: ref i32`). Zig error:
    `expected type '?*i32', found 'comptime_int'`.
  - INFERENCE: `/=` in the update is still checked by safety (`a7/safety.py:353-363` according to the saved state;
    not re-read in this session), so this is a gap in defense in depth only.
  - Fix: route updates through the assignment helper (Z4).
- **ZIG-10 (NEW): char literals with control bytes.**
  - Code: `a7/backends/zig.py:1491-1496` escapes only `\n \t \r \\ ' \0`.
  - Probe: `p009_char_escapes_print` (`'\x01'`, `'\x7f'`, `'\x08'`). Zig error:
    `character literal contains invalid byte: '\x01'`.
  - Mapping corrected: `p009_char_escapes` itself exits 6, because `cast(i32, char)` is rejected as an
    unclassified cast. The finding rests on `p009_char_escapes_print`.
- **ZIG-11 (NEW): `inf.0`.**
  - Code: `a7/backends/zig.py:1480-1483` appends `.0` to `str(val)`, so `inf` becomes `inf.0`.
  - Probe: `p011_float_inf_fold` (`1e308 * 10.0`, `1e999`). Zig error: `expected pointer dereference, optional
    unwrap, or field access, found 'a number literal'`.
- **ZIG-12 (NEW): unsupported match scrutinees accepted.**
  - Probes: `p015` and `p016` (int match without `else`): `else prong required when switching on type
    'comptime_int'`. `p017` (string): `cannot switch on strings`. `p018` (float): `switch on type
    'comptime_float'`.
  - INFERENCE: with typed scrutinees, Zig still needs `else` for a non-exhaustive integer switch and still cannot
    switch on floats. This was not probed with typed locals.
- **ZIG-13 (NEW, = SAF-18): name-keyed mutation analysis.**
  - Code: `a7/backends/zig.py:409` `self._mutated_vars = self._collect_mutations(node.body)` and 652
    `is_mutated = name in self._mutated_vars`.
  - Probe: `p029_sibling_block_mutation` (`{x := 1 ...} {x := 2; x = 3}`). Zig error: `local variable is never
    mutated` (the first `x`).
- **ZIG-14 (NEW): unused local constant.**
  - Code: `a7/backends/zig.py:628-637` `_visit_const` emits no discard. `_visit_var` has one at 694-697.
  - Probe: `p030_local_const_unused`. Zig error: `unused local constant`.
- **ZIG-15 (NEW): `main` signature.**
  - Probes: `p032` (`main` returns `i32` and uses io): `value of type 'i32' ignored`. `p032b`: `expected return type
    of main to be 'void', '!void', 'noreturn', 'u8', or '!u8'`. `p032c` (parameters): `type 'i32' does not support
    struct initialization syntax`.
- **ZIG-16 (NEW): `defer f()` with a non-void `f`.**
  - Code: `a7/backends/zig.py:1290-1293` writes `defer ` plus the inline statement.
  - Probe: `p033_defer_nonvoid_call`. Zig error: `value of type 'i32' ignored`.
- **ZIG-17 (NEW): primitive-name shadowing.**
  - Probe: `p035_zig_primitive_local_names` (`u3 := 1`, and so on). Zig error: `name shadows primitive 'u3'`.
- **ZIG-18 (KNOWN-family B12): Zig keywords at new sites.**
  - Code: `a7/backends/zig.py:1512-1515` escapes 9 names, and only at identifier uses.
  - Probes: `p036` (fields `error`, `test`): `expected '.', found ':'`. `p036b` (function or parameter names):
    `expected '(', found 'try'`. `p036c` (type or variant names): `expected 'an identifier', found ','`.
- **ZIG-19 (NEW): collisions with generated names.**
  - `p037` (user fn `__a7_stdout_print`): `duplicate struct member name '__a7_stdout_print'`.
  - `p037b`: `duplicate ... '__a7_user_main'`.
  - `p037c` (global `std`): `duplicate ... 'std'`.
  - `p037f`: `local constant '__a7_match_2' shadows local constant from outer scope`.
- **ZIG-20 (NEW): enum tag type fixed at i32.**
  - Code: `a7/backends/zig.py:590` `const {name} = enum(i32) {{`.
  - Probe: `p041_enum_explicit_values` (`A = 3000000000`). Zig error: `type 'i32' cannot represent integer value
    '3000000000'`.
- **ZIG-21 (NEW): `~` on a literal and `-` on unsigned.**
  - `p045_bitnot_literal` (`x: i32 = ~5`): `bitwise not operation on type 'comptime_int'`.
  - `p046_neg_unsigned` (`-x`, `x: u32`): `negation of type 'u32'`.
- **ZIG-22 (KNOWN-family B13): float `%=`.**
  - Code: `a7/backends/zig.py:2357` maps `MOD_ASSIGN` to `"%="`, while binary `%` uses `@rem` at 1585.
  - Probe: `p047b_float_compound`. Zig error: `remainder division with 'f64' and 'f64': signed integers and floats
    must use @rem or @mod`.
- **ZIG-23 (NEW): unused loop label.**
  - Probes: `p086_while_labeled_nested` and `p086b_unused_label` (`@loop for ...` never targeted). Zig error:
    `unused while loop label`.
- **ZIG-24 (KNOWN-family B4, ledger part 1 line 76): default of uninitialized arrays.**
  - `p122_uninit_string_array` (`names: [2]string`): `expected type '[]const u8', found 'comptime_int'`.
  - `p122b` (`[2][2]i32`): `expected type '[2]i32', found 'comptime_int'`.
- **ZIG-25 (KNOWN-family B10 and B15; B15 covers local captures, here the shadowed name is a global).**
  - `p155` (`item :: 5` and `for item in arr`): `capture shadows declaration of 'item'`.
  - `p156` (`helper := 3` with `fn helper`): `local constant shadows declaration of 'helper'`.
- **ZIG-26 (NEW): the checker and the emitter count placeholders differently.**
  - `a7/passes/type_checker.py:1517-1523` counts any `{...}` as a placeholder. `a7/backends/zig.py:2263` converts
    only `{}`, and 2271-2275 escapes the rest.
  - Probe: `p161b_format_named_placeholder` (`io.println("v={x}", 5)`). Zig error: `unused argument in 'v={{x}}`.
- **ZIG-27 (NEW; mapping extended): intra-module calls not prefixed.**
  - `a7/compile.py:612-617` sets `module_emit_prefix` on every FUNCTION declaration of a file module.
    `a7/backends/zig.py:395, 402` uses it for the declared name, but call sites inside the module keep the bare name.
  - `m1_module_private_call`: `pub make` calls private `inner` and emits `return inner(v);`. Zig error: `use of
    undeclared identifier 'inner'`.
  - New `m4_module_public_call` (this session, `run9.log`): `pub twice` calls `pub base` and emits
    `return (base(v) * 2);` with the same error. The defect is not limited to private functions: any module function
    that calls another function of its own module fails to build.
  - Kept at MEDIUM because it fails visibly. Note that `CLAUDE.md` says file-backed local imports "currently fail
    closed before codegen", yet m1 and m4 reach codegen with a7 exit 0. That contradiction is pipeline scope (PIP-6).
- **ZIG-28 (KNOWN): reproduced known defects.**
  - B11 variant: `p084` (`defer x += 1`) gives `local variable is never mutated`.
  - B9: `p072`, `capture 'p' shadows local variable from outer scope`.
  - B15: `p062`, `unused capture`.
  - B6 and C4b3: `p068` (float global), `variable of type 'comptime_float' must be const or comptime`.
  - B10: `p131`, `unused local constant`.
- **ZIG-29 (NEW): generic forms rejected at codegen (exit 7 after semantic success).**
  - Code: `a7/backends/zig.py:2008-2009` raises "generic type requires an explicit generic environment".
  - Probes: `p039` (`second :: fn(a: $T, b: $T) $T`, 4:17), `p038` (a `ref Node($T)` field, 6:20), `p093`
    (a `Pair($B,$A)` return, 9:14).
  - The `@TypeOf(param)` and `void` fallback at `a7/backends/zig.py:459-486` is unreachable for these, because the
    parameter types raise first (`p039b` is rejected at stage 6). See ZIG-36.
  - Compat: no; it accepts more programs.
- **ZIG-30 (NEW): array addition into an untyped local.**
  - Code: `a7/backends/zig.py:660-663` raises "array binary initializer requires a known array type" when there is
    no `explicit_type` and no `resolved_type`.
  - Probe: `p099_array_vector_add` (`d := a + b`), exit 7, message at 9:5. Compat: no.
- **ZIG-33 (NEW): `{{` in format strings.**
  - Code: `a7/backends/zig.py:2271-2272` escapes each `{` to `{{`, so `{{` becomes `{{{{` and prints `{{`. The
    checker treats `{{` as an escape (`type_checker.py:1518-1520`).
  - Probe: `p161_format_double_brace` (`"a {{b}} {}"`) prints `a {{b}} 5` in Debug and ReleaseFast (first auditor's
    run). SPEC gives no brace-escape rule (INFERENCE from `docs/SPEC.md` grep).
  - Compat: yes (output changes). Fix plan P-BK.2.
- **ZIG-38 (partly KNOWN): other operations with no backend approval.**
  - `del` lowers to `allocator.destroy` with no approval at `a7/backends/zig.py:1306` and 2390. The unsafe cases are
    KNOWN as S6, S7 and S8.
  - `+`, `-`, `*`, unary `-`, and vector add emit plain Zig operators with no overflow approval (1595). This is
    not a Wave 0 defect; it is covered by decision L5 and track 3a.
  - When an if-expression has no `else`, a match case has no expression, or a match has no `else`, the backend emits
    `undefined` (1801, 1818, 1825, 1863). UNVERIFIED whether the checker lets any of these through.
  - Compat: yes for `del` and overflow (programs that build today would need proofs); unknown for the `undefined`
    fallbacks.
- **ZIG-40 (NEW): nested functions.**
  - `p083_nested_fn_simple`: calling a nested `inner` fails at exit 6, with "Undefined type (Identifier 'inner')"
    and "Cannot call undefined identifier 'inner'" at 8:9. The backend has hoisting code
    (`a7/backends/zig.py:412-415`) that no accepted program reaches.
  - `p083b_nested_fn_uncalled_div`: an uncalled nested function containing `a / 2` fails at exit 7 with "Zig backend:
    div was not approved by safety proof analysis". Safety does not visit nested bodies, and the backend fails
    closed.
  - `p008`, `p026`, `p027`, `p028` all exit 6.
  - Compat: no.
- **ZIG-41 (NEW, not in the planner's table): if and match expressions whose arms are all untyped integer literals.**
  - With a runtime condition, Zig rejects them: `value with comptime-only type 'comptime_int' depends on runtime
    control flow`.
  - Probes: `p002_match_expr_in_binary` (`(match k { case 1: 10 else: 20 }) + 1`, `zig:15:13`) and
    `p001_if_expr_in_binary` (`v := (if c { 1 } else { 2 }) * 3`, `zig:19:16`).
  - Same cause as ZIG-3: literal types are not emitted. Searching `docs/plan` and `tmp/audit/compiler/*.md` for
    "depends on runtime control flow" finds nothing (`p002known.log`). Compat: no.

## LOW

- **ZIG-31 (NEW): io call used as a value is caught at the wrong stage.** `p064_io_as_value` (`x := io.println("hi")`)
  fails at exit 7: `5:10: Zig backend: io.print/io.println cannot be used as expression values`
  (`a7/backends/zig.py:2214-2219`). It should be a type error at exit 6. Compat: no.
- **ZIG-32 (NEW): deep block nesting.** `perf.py`, `perf.log`: `nestblock_400` exits 7 with `maximum recursion depth
  exceeded` (codegen_s 0.003), while `nestblock_200` passes. `CLAUDE.md` allows backend statement recursion, but the
  error has no span or explanation. Nested if at 400, else-if at 500, binary at 500 and unary at 200 fail earlier with
  exit 8 in the parser (outside this scope). Compat: no.
- **ZIG-34 (NEW): print formats.**
  - `_format_spec_for_arg` (`a7/backends/zig.py:2221-2249`) returns `any` for anything that is not string, char,
    number or bool.
  - Evidence that is not affected by the disclosure: the emitted Zig of `p013_format_specs` (compile only) has
    `"{any}|{any}|{any}\n", .{ col, p, arr }` and `"{s}|{any}|{any}\n", .{ n, part, r }`.
  - Runs: `p041b` prints enums as `.A .B .C .D`, `p109e` prints a struct as `.{ .x = 1, .y = 2 }`, and `p149` prints
    `1e300` as a 301-digit integer.
  - A string slice printing as bytes (`{ 101, 108 }`) comes only from p013's disqualified run. It is UNVERIFIED by an
    allowed run; INFERENCE from Zig's `{any}` on `[]const u8`.
  - Compat: yes. Deferred to P10.
- **ZIG-35 (NEW): `zig fmt --check`.** `fmtstats.log`: of 51 probes that built, 4 fail `zig fmt --check`
  (`p004_fall_loop_break_continue`, `p021_match_side_effect_scrutinee`, `p024_labeled_loop_in_match`,
  `p037d_match_temp_collision`). The records also show fmt failures on standalone blocks (`p029` fmt=1,
  `p153_zig_fmt_nested_block`). Compat: no.
- **ZIG-36 (NEW): dead code.**
  - `a7/backends/base.py:44-47` `generic_visit` and `:49-59` `write` have no callers
    (`grep -rn "self\.write(\|generic_visit" a7/` finds only the definitions, `dead.log`). `write` also calls
    `self.output.getvalue()` on every call, which is O(n) per write.
  - `a7/backends/zig.py:1612-1643` `_MATH_BUILTIN_MAP`: `p071_bare_builtins` exits 6, so the bare builtins never reach
    it (first auditor).
  - The `void` generic-return fallback at 484-486 (see ZIG-29).
  - `_declare_var_in_scope` (296, called at 646 only when `emit_name` is unset).
  - `_emit_binary` (1518).
  - Nested-function hoisting (412-415, see ZIG-40).
  - The saved state calls `_declare_var_in_scope` and `_emit_binary` partly dead. This session did not re-trace their
    reachability (see Not verified).
  - Compat: no.
- **ZIG-37 (NEW): tests.** See Test gaps. The main item is `test/test_codegen_zig.py:48-72` `compile_a7_to_zig`,
  which runs name resolution, type checking and safety, but not `SemanticValidationPass`, and does not check
  type-checker errors. Compat: no (test-only).

## Operator matrices (this session)

The first auditor's `p170` and `p171` exit 6 because every `a / b` and `a % b` had an unproven divisor. The guarded
copies `probes/p170b_int_operator_matrix_guarded.a7` and `probes/p171b_float_operator_matrix_guarded.a7` were
generated by `gen_matrix_guard.log`'s script. They wrap each `/`/`%` print in `if b != 0 { ... }` and are otherwise
identical.

Run-allowed check: the operands are fixed at `a=-20` or `20`, `b=6`, `s=1`, so there is no overflow at any width
(the largest product is `-120` in `i8`), no division by zero, shifts only by 1 and 2, and no `new`, `del`, `ref`,
slices or indexing.

- Both a7 exit 0, JSON and human output are identical, build-obj 0, `zig fmt` 0 (`run7.log`).
- p170b Debug and ReleaseFast stdout match `p170_expected.txt` exactly: `diff` exit 0 for both profiles
  (`p170b.diff.log`).
- The expected file's provenance was not recorded, so this session recomputed all 30 lines in Python, using
  truncating division, remainder with the dividend's sign, and `~a` wrapped to width. Result:
  `recomputed == p170_expected.txt: True` (`gaps4.log`).
- The lowering verified by these runs: `@divTrunc` and `@rem` for all 10 integer types, `& | ^`, literal `<< 2`,
  `>> 1`, runtime `<< @intCast(s)` and `>> @intCast(s)`, six comparisons, and `~`
  (`out/p170b_int_operator_matrix_guarded.pre.zig`).
- p171b Debug and ReleaseFast print `f32 9.5 5.5 15 3.75 1.5 | f32 false false true true false true -7.5 |
  f64 -5.5 -9.5 -15 -3.75 -1.5 | f64 true true false false false true 7.5`. These match IEEE `+ - * /`, `@rem`
  (`-7.5 % 2.0 = -1.5`, which agrees with the runtime result in KNOWN D7), the comparisons and negation.

## Blockers for the typed IR (Wave 3)

- Node identity: `type_map` in the backend and `BackendPlan` in safety are keyed by `id(node)`, with no stable node
  identity. This is the cause of ZIG-1.
- Declaration identity: `_mutated_vars` and `_used_identifiers` are keyed by name, with no declaration identity. This
  causes ZIG-13, ZIG-14 and ZIG-25.
- Expression structure: emission concatenates strings, with no expression tree, and precedence is handled by hand at
  each site. This causes ZIG-2 and ZIG-41.

## Checked and correct

Re-run or re-read in this session:
- The integer operator matrix for 10 types and the float matrix for f32 and f64, described above.
- If-expression as a right operand and call argument (`p109c`, `1102 1104`), and as a unary operand (`p109d`,
  `-4 -6`). First auditor's runs; this session re-read the logs.
- Determinism: JSON and human output write identical Zig for all 21 probes re-run in this session (`det: true` in
  `run7.log`, `run8.log`, `run9.log`, `gaps4.log`). The first auditor reports 46 of 46 identical across `PYTHONHASHSEED` values
  (`det.log`). `p002`, `p002b` and `p096` exit 1 in JSON mode, which is KNOWN F5 (`json_formatter.py:215`,
  formatter scope).
- The approval inventory in `zig.py` agrees with the code: assignment deref (1316), `/=` and `%=` (1322-1323), binary
  div and mod (1567-1568), deref (1730), implicit field deref (1716) and cast (1753). Index (1672) and slice (1690) are
  from the saved state and were not re-read.
- `base.py` and `__init__.py` were read in full. `get_backend` raises `ValueError` for an unknown name and returns
  a new generator for `zig`.

First auditor's runs (Debug and ReleaseFast, `run1.log`..`run6.log`), not re-run in this session:
- `fall` with `continue` and `break` (`p004`, 111).
- Defer ordering (`p005`, `p128`, `p157`).
- Ranges and multi-value cases (`p019`).
- The scrutinee is evaluated once in all three match lowerings (`p021`).
- Labeled `continue` and `break` inside a `fall` match (`p024`, 55).
- C-style `for` `continue` runs the update (`p025`).
- `fall` into a capture (`p106`) and nested `fall` matches (`p141`).
- `else if` (`p087`) and short-circuit evaluation (`p088`).
- Integer widths (`p089`), compound unsigned and signed non-division assignment (`p047`), and runtime shift and
  bit-not (`p049`, `p045b`).
- Nested arrays (`p053`); positional, nested and inline structs (`p054`); `p158`; `p160`.
- Function pointers (`p092`) and generic instantiation (`p126`, `p039c`).
- Globals (`p094`, `p095`, `p132`), match expressions (`p096`, `p097`) and aliases (`p098`).
- String escapes below 0x80 (`p115`), integer extremes (`p151`), `for` over a literal (`p063`), casts (`p044c`) and
  literals (`p010`, `p012`).
- Performance, codegen time only (`perf.log`): `seqif` 1000, 2000 and 4000 take 0.12, 0.24 and 0.49 s; `seq`
  2000, 4000 and 8000 take 0.055, 0.114 and 0.233 s; `fns` 200, 400 and 800 take 0.03, 0.07 and 0.09 s. All are
  close to linear.

## Test gaps

- `test/test_codegen_zig.py:48-72`: `compile_a7_to_zig` runs `NameResolutionPass`, `TypeCheckingPass` and
  `SafetyProofPass`, but not `SemanticValidationPass`, and it never checks `type_checker.errors`. Tests built on it
  can pass on programs the real pipeline rejects (ZIG-37).
- `test/test_codegen_zig.py:289` and `:357-358` assert the text
  `std.Io.File.stdout().writer(__a7_io.?, &__a7_stream_buf)`, which is the positional writer behind ZIG-39. These
  tests lock the defect in.
- `scripts/build_examples.py:125-130` runs example binaries with `stdout=subprocess.PIPE`, and the pipeline tests use
  `capture_output=True` (`test_codegen_zig.py:350`). Pipes are unseekable, so no gate can observe ZIG-39
  (INFERENCE).
- No test covers: an if-expression as a binary left operand or field base (ZIG-2); folded literals near other typed
  nodes (ZIG-1); float math on untyped locals (ZIG-3); `\x80`-`\xff` escapes (ZIG-4); a local named `io` (ZIG-5);
  struct-literal evaluation order (ZIG-6); runtime shift amounts and `<<=` (ZIG-7); union field reads (ZIG-8); C-style
  `for` update on a `ref` (ZIG-9); calls between a module's own functions (ZIG-27); Zig keywords as fields, types or
  parameters (ZIG-18); `{{` and `{x}` in format strings (ZIG-26, ZIG-33). This was found by searching `test/` for the
  constructs (`z37.log`) and was not exhaustive.
- According to the saved state, most pattern tests check substrings or run `zig ast-check` only. `ast-check` misses
  semantic-analysis errors such as those in ZIG-10 to ZIG-26. This session did not re-count them.

## Not verified

- Run output of `p013`, `p052` and `p091` (disclosed above). Every claim that could rest on them uses compile output
  or other runs instead.
- Debug panic and ReleaseFast undefined behavior for ZIG-7 and ZIG-8. The probes are compile-only by rule, so this is
  inferred from Zig semantics.
- ZIG-39 on stderr (`2> file`), and the reason `>>` works (O_APPEND).
- Whether the ZIG-38 `undefined` fallbacks can be reached from any program A7 accepts.
- Whether the id-keyed safety `BackendPlan` can be fooled into a wrong approval through id reuse (ZIG-1). None was
  found.
- ZIG-12 with typed scrutinees.
- MEDIUM and LOW probes were not re-run in this session. Their exit codes and Zig errors were re-read from
  `out/*.rec`.
- Reachability of `_declare_var_in_scope` and `_emit_binary` (ZIG-36). Index and slice approval lines 1672 and 1690.
  `a7/safety.py:353-363` for ZIG-9.
- A full line-by-line read of `zig.py` in this session. This session read the cited regions: 140-200, 290-310,
  395-415, 455-490, 580-600, 628-720, 1284-1330, 1355-1425, 1475-1515, 1555-1600, 1700-1760, 1790-1900, 2000-2012,
  2155-2310 and 2355-2395. The rest relies on the first auditor's read.

Count basis: 41 findings, each re-checked in this session against code and a probe record or run, plus 7
checked-correct items verified in this session (integer matrix, float matrix, independent recomputation of the
expected file, determinism of the re-runs, approval inventory, `base.py` and `__init__.py`, `p109c`/`p109d` logs).
Items attributed to the first auditor are not counted.

claims checked: 48
