> **Source:** Claude research subagent, Wave 0 reproduction ledger part 1 (frontend, CLI, typing, backend and failing baseline tests), run against commit `701c679` with Zig 0.16.0.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim. Probe files and logs it cites stay under `tmp/repro1/`, which is not tracked. Only probes marked run-allowed were built and run.

# Wave 0 step 0.4: reproduction ledger, part 1 of 2

Tree: `master` at `701c67936c70ad2b0608326e23e56cc5d38c9fdb`. `git status --porcelain a7/` is
empty, so the compiler has no uncommitted changes. Run on 2026-09-16. Zig 0.16.0
(`zig version`). No file outside `tmp/repro1/` was edited, and nothing was fixed.

## Method

Every probe is in `tmp/repro1/probes/<id>.a7`. `gen_probes.py` and `gen_probes2.py`
generated them, including the `b14_mymath.a7` helper module (from `gen_probes.py`).
`b14d` and `f1b` were written directly. Each probe starts with `// probe: compile-only` or `// probe: run-allowed`.
The driver is `tmp/repro1/run.sh`, and `summarize.py` condenses its output. The raw logs
are `run.log`, `run2.log`, `run3.log` and `run4.log`. The condensed logs are
`summary.log` (every probe), `summary2.log`, `summary3.log` and `summary4.log`.
`zig_dump.txt` holds the emitted Zig with line numbers.

The driver runs these commands for each `<id>`, all from `/home/cx89/Projects/pl-dev/a7-py`:

```
MISE_UV_VERSION=0.12.6 uv run a7 tmp/repro1/probes/<id>.a7 --format json --output tmp/repro1/out/<id>.json.zig
MISE_UV_VERSION=0.12.6 uv run a7 tmp/repro1/probes/<id>.a7 --output tmp/repro1/out/<id>.zig
# only when human exit is 0:
zig ast-check tmp/repro1/out/<id>.zig
zig build-obj -fno-emit-bin --cache-dir tmp/repro1/zig-cache --global-cache-dir tmp/repro1/zig-global tmp/repro1/out/<id>.zig
# only when line 1 is exactly "// probe: run-allowed" AND build-obj exited 0:
zig build-exe -O Debug|ReleaseFast <same cache flags> tmp/repro1/out/<id>.zig -femit-bin=tmp/repro1/bin/<id>.<profile>
timeout 10 tmp/repro1/bin/<id>.<profile>
```

Each run saves stdout, stderr and the exit code to separate files in `tmp/repro1/out/`
(`<id>.json.stdout`, `.json.stderr`, `.json.exit`, `.human.*`, `.astcheck`,
`.buildobj`, `.run.<profile>.stdout`). A JSON-mode run counts as valid only when
`python3 -m json.tool` accepts its whole stdout.

Calibration: `ast-check` runs AstGen only. `tmp/repro1/calib/bad.zig` uses
`var counter = 0;` from `main`. `zig ast-check` exits 0 on it, and
`zig build-obj -fno-emit-bin` exits 1 with "variable of type 'comptime_int' must be
const or comptime" (`calib/calib.log`). So `build-obj -fno-emit-bin` does analyze
`main`, and it is the check that counts for Sema errors.

Only these probes were built as executables and run: `b1`, `b13f` (unsigned control)
and `b14d`. Every other run-allowed probe (`b10`, `b10b`, `b13a`, `b13c`, `b13d`,
`b13e`, `b14a`) failed `build-obj`, so the driver skipped the run. `b13b` failed to
parse in A7.

Pytest for B15 and B16:
`PYTHONPATH=. MISE_UV_VERSION=0.12.6 uv run pytest <files> -q --tb=short -rf -p no:cacheprovider`
Logs: `b15_pytest_native.log` and `b16_pytest_artifacts_diagnostics.log`.

## Summary table

"A7 exit" gives the JSON-mode exit, then the human-mode exit. "Zig" is the result on the
human-mode output.

| Id | Source | Main probe(s) | A7 exit (json/human) | Zig result | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | `docs/plan/README.md:254-264, 371-372`; `a7/tokens.py:387-406` | `f1b_unclosed_comment_readme_form`, `f1_unclosed_comment` | 0/0 | Empty 0-byte `.zig`; ast-check 0, build-obj 0 | CURRENT |
| F2 | `docs/plan/README.md:373-374`; plan Lane F (`parser.py:171-199, 266-268`) | `f2b`, `f2c`, `f2d`, `f2e` (controls `f2a`, `f2f`) | 0/0 (f2a, f2f: 5/5) | f2d: "use of undeclared identifier '__a7_user_main'"; f2b/c/e build-obj 0 | CURRENT |
| F3 | plan Lane F (`parser.py:153`) | `f3a_1100_consts`, `f3b_1100_fns` | 5/5 | not reached | CURRENT |
| F4 | plan Lane F (`parser.py:201-206`) | `f3a_1100_consts`, `f3b_1100_fns` (JSON mode) | 5 | not reached; JSON stdout does not parse | CURRENT |
| F5 | `edge-case-audit.md:133-134`; audit-1 F12 | `f5_match_yields_struct` | 1/0 | human output: ast-check 0, build-obj 0 | CURRENT |
| F6a | `docs/plan/README.md:251` | `f6a_utf8_identifier` | 4/4 | not reached | NOT REPRODUCED |
| F6b | `docs/plan/README.md:252, 388` | `f6b_utf8_string` | 0/0 | build-obj 0 | CURRENT |
| F6c | `edge-case-audit.md:129-130` | `f6c_utf8_char` | 0/0 | build-obj 0 | CURRENT |
| T1 | `docs/plan/README.md:375-376`; plan Lane S | `t1c_unbound_array_len_decl_only` (also `t1`, `t1b`) | 0/0 (t1, t1b: 6/6) | "use of undeclared identifier 'n'" | CURRENT |
| T2a | `docs/plan/README.md:379`; plan Lane S | `t2a_self_init_no_outer` | 0/0 | "use of undeclared identifier 'z'" | CURRENT |
| T2b | plan Lane S ("lower correctly if an outer one exists") | `t2b_self_init_outer_local`, `t2c_self_init_outer_global` | 0/0 | t2b: "unused local constant" `z_1`; t2c: "local constant shadows declaration of 'z'" | CURRENT |
| T3 | `docs/plan/README.md:377-378`; plan Lane S | `t3a_ret0_u32`, `t3b_ret0_usize` (control `t3c`) | 6/6 (t3c: 0/0) | t3c build-obj 0 | CURRENT |
| B1 | plan Lane B item 2 | `b1_array_swap_literal` (run-allowed) | 0/0 | builds; prints `2 2` in Debug and ReleaseFast | CURRENT |
| B2 | `docs/plan/README.md:223-239, 386-387` | `b2b_case_ok_no_else`, `b2c_case_ok_on_err_value` (also `b2`) | 0/0 (b2: 6/6) | build-obj 0; `const ok = __a7_match_1;` | CURRENT |
| B3 | `edge-case-audit.md:116-118`; plan Lane S | `b3b_string_eq_params` (also `b3a`, control `b3c`) | 0/0 | b3b: "operator == not allowed for type '[]const u8'"; b3a and b3c build-obj 0 | CURRENT (b3a variant DIFFERENT) |
| B4 | `edge-case-audit.md:116-118` | `b4_struct_array_no_init` | 0/0 | "expected type '...Pt', found 'comptime_int'" | CURRENT |
| B5 | `edge-case-audit.md:117-118` | `b5_slice_write` | 0/0 | "cannot assign to constant" | CURRENT |
| B6 | `edge-case-audit.md:119-120` | `b6_mutable_global` | 0/0 | "variable of type 'comptime_int' must be const or comptime" | CURRENT |
| B7 | `edge-case-audit.md:121` | `b7_byvalue_array_param_write` | 0/0 | "cannot assign to constant" | CURRENT |
| B8 | `edge-case-audit.md:121-122` | `b8a_for_binding_field_write` (also `b8b`) | 0/0 (b8b: 6/6) | "cannot assign to constant" | CURRENT |
| B9 | `edge-case-audit.md:123-125` | `b9_del_named_p` | 0/0 | "capture 'p' shadows local variable from outer scope" | CURRENT |
| B10 | plan Lane B item 1 | `b10_shadow_inner_block` (run-allowed), `b10b` | 0/0 | "unused local constant" `x_1`; no binary; nothing prints | CURRENT |
| B11 | plan Lane B item 5 | `b11_defer_assign` | 0/0 | "value of type 'type' ignored" at `defer void;` | CURRENT |
| B12 | plan Lane B item 4 | `b12_ident_{test,var,const,std,type,allocator}`, `b12g` | 0/0 (all) | 5 of 6 rejected; `allocator` builds unless the preamble allocator is emitted (`b12g` rejected) | CURRENT (plain `allocator` variant DIFFERENT) |
| B13 | plan Lane B item 6 | `b13a`, `b13c`, `b13d`, `b13e` (run-allowed; control `b13f`) | 0/0 (b13b: 5/5) | "signed integers must use @divTrunc..." and "...must use @rem or @mod"; no run possible | CURRENT |
| B14 | plan Lane B item 7 | `b14d_struct_value_named_math_used` (run-allowed), `b14a`, `b14b`, `b14c` | 0/0 | b14d builds and prints `3 4.5` (expected `4.5 4.5`); b14a: "unused local constant" `math` | CURRENT |
| B15 | plan Lane B item 4; `test/test_pipeline_native.py:80-87` | pytest | pytest exit 1 | 3 named tests fail as described below; 4th failure noted | CURRENT |
| B16 | plan Lane F Track 1 items | pytest | pytest exit 1 | 8 failed, 3 passed | CURRENT |

Counts per ledger row (28 rows): CURRENT 27, NOT REPRODUCED 1 (F6a), DIFFERENT 0.
Counted by the 25 task items instead: 24 CURRENT, and F6 is mixed (F6a NOT REPRODUCED,
F6b and F6c CURRENT). Two sub-variants behave differently from the recorded claim: B3
with local string literals, and B12 with a plain `allocator`. They are explained below
and do not change their row's status.

## Per-item detail

### F1. Unclosed `/*` exits 0

- Source: `docs/plan/README.md:254-264` (G6 example) and `:371-372`. Code:
  `a7/tokens.py:387-406`. The `/*` branch loops `while self.current_char() and depth > 0`
  and returns at EOF without an error. The comment at `:388-390` says EOF is an
  accepted terminator.
- Probes:
  - `tmp/repro1/probes/f1b_unclosed_comment_readme_form.a7` (compile-only): the
    README form, `/* unclosed` followed by `main :: fn() {}`.
  - `tmp/repro1/probes/f1_unclosed_comment.a7` (compile-only): `io :: import "std/io"`,
    then `/* unclosed`, then `main` with a println.
- Result:
  - f1b: JSON exit 0, human exit 0. The JSON parse AST has `declarations: []`. Human
    stdout: `Compiled ... f1b_unclosed_comment_readme_form.zig (0 bytes, 1 ms)`.
  - f1: exit 0/0. The declarations are `[IMPORT]` only, so `main` is gone. The Zig
    file is 0 bytes.
- Zig: on the 0-byte file, `ast-check` exits 0 and `build-obj -fno-emit-bin` exits 0.
  No diagnostic appears at any stage.
- Status: **CURRENT**.

### F2. File-scope statements and later parse errors are silently dropped

- Source: `docs/plan/README.md:373-374`. Plan Lane F cites `parser.py:171-199` and
  `:266-268`. The current `a7/parser.py:171-199` shows the three exceptions (zero
  declarations; exactly one declaration with "Expected declaration"; "Expected
  expression after"). `synchronize()` is at `:235-268`, and it jumps to EOF at `:268`.
  The plan's citations match the current tree.
- Probes (all compile-only):
  - `f2b_filescope_stmt_after_main`: import, `main`, then `io.println("stmt")`. Exit
    0/0. JSON declarations are `[IMPORT, FUNCTION main]`. The emitted
    `__a7_user_main` holds only `__a7_stdout_print("main\n", .{});`, and the
    statement is gone. `ast-check` 0, `build-obj` 0.
  - `f2c_bad_struct_after_main`: `main`, then `Pt :: struct { x i32 }`. Exit 0/0.
    Declarations are `[IMPORT, FUNCTION main]`, so the struct is dropped with no
    diagnostic. `build-obj` 0.
  - `f2d_filescope_stmt_two_decls_no_main`: import, `helper`, then
    `io.println("stmt")`, with no `main`. Exit 0/0. This matches the README claim
    "emit no `main`": the emitted `pub fn main` calls `__a7_user_main();` (line 11),
    but no such function is emitted. `ast-check` exits 1 with
    `f2d...zig:11:5: error: use of undeclared identifier '__a7_user_main'`.
  - `f2e_filescope_stmt_before_main`: import, `helper`, `io.println("stmt")`, then
    `main`. Exit 0/0. Declarations are `[IMPORT, helper, main]`. The statement is
    dropped, and `build-obj` exits 0.
  - Control `f2a_filescope_stmt_only` (import plus the statement only): exit 5/5,
    `Unexpected token 'io' after parsing complete program [line 4: col 1]`. This is
    the one-declaration exception.
  - Control `f2f_bad_struct_before_main` (bad struct first, then `main`): exit 5/5,
    `Unexpected token '}' after parsing complete program [line 6: col 0]`. It fails,
    but the diagnostic points at the closing brace, column 0, not at `x i32`.
- Status: **CURRENT**. Whether a parse error is dropped depends on how many
  declarations come before it.

### F3. More than 1000 top-level declarations

- Source: plan Lane F, `parser.py:153`. The current `a7/parser.py:153` has
  `max_iterations = 1000`, and the loop condition at `:156` caps iterations, not
  declarations.
- Probes (compile-only):
  - `f3a_1100_consts.a7`: import, `C0 :: 0` to `C1099 :: 1099`, and `main`.
  - `f3b_1100_fns.a7`: import, 1100 functions `fN :: fn() i32 { ret N }`, and `main`.
- Result:
  - f3a: exit 5/5. Human stdout is two lines:
    `Warning: Parser stopped after 1000 iterations in tmp/repro1/probes/f3a_1100_consts.a7`
    then `error: Unexpected token 'C999' after parsing complete program [line 1003: col 1]`.
  - f3b: exit 5/5. Same warning, then
    `error: Unexpected token 'f993' after parsing complete program [line 2983: col 1]`.
- Zig: not reached.
- Status: **CURRENT**. A valid program is rejected. The output is not a silent
  truncation. It is a parse error that points at a valid declaration.

### F4. Parser warning on stdout breaks `--format json`

- Source: plan Lane F, `parser.py:201-206`. The current `a7/parser.py:201-206` has
  `print(f"Warning: Parser stopped after ...")` (text at `:205`) with no `file=`.
- Probe: `f3a_1100_consts.a7` and `f3b_1100_fns.a7` in JSON mode (compile-only).
- Result: JSON exit 5. Stdout starts
  `Warning: Parser stopped after 1000 iterations in tmp/repro1/probes/f3a_1100_consts.a7\n{\n  "schema_version": "2.0", ...`.
  `json.loads` fails with "Expecting value: line 1 column 1 (char 0)", and `.json.stderr`
  is empty. f3b behaves the same.
- Status: **CURRENT**.

### F5. `--format json` on a match yielding a struct exits 1

- Source: `docs/plan/research/memory/edge-case-audit.md:133-134`, and audit-1 F12
  (`audit-1-values-moves-extents.md:341`).
- Probe: `f5_match_yields_struct.a7` (compile-only). `Pt :: struct { x: i32 }`; `k := 1`;
  `p := Pt{x: 5}`; `q := Pt{x: 6}`; `r := match k { case 1: p else: q }`; print `r.x`.
- Result:
  - JSON mode: **exit 1**, with empty stdout. Stderr has a traceback ending
    `a7/formatters/json_formatter.py", line 215, in _ast_to_dict / for child in field_value: / TypeError: 'ASTNode' object is not iterable`.
    It was raised first at `compile.py:488` (`_emit_success`), and raised again while
    handling that exception at `compile.py:503` from `cli.py:96`.
  - Human mode: exit 0. The Zig is `const r = switch (k) { 1 => p, else => q, };`
    (lines 22-25).
- Zig on the human output: `ast-check` 0, `build-obj` 0.
- Status: **CURRENT**. The exit is 1, not the documented internal exit 8.

### F6a. `café := 1` diagnostic text

- Source: `docs/plan/README.md:251` claims "Unexpected character: 'Ã'".
- Probe: `f6a_utf8_identifier.a7` (compile-only).
- Result: exit 4/4. Human output:
  `error: Unexpected character: 'é' [line 5: col 8]`, with the caret under `é` and
  `hint: Remove this character`. JSON message:
  `f6a_utf8_identifier.a7:5:8: Unexpected character: 'é'` (valid JSON).
- Status: **NOT REPRODUCED**. The diagnostic shows `é`, not `Ã`. The rejection itself
  (exit 4) still happens. This agrees with the citation audit's R1 finding.
  `docs/plan/README.md:251` is stale.

### F6b. `s := "café"` compiles

- Source: `docs/plan/README.md:252, 388`.
- Probe: `f6b_utf8_string.a7` (compile-only).
- Result: exit 0/0. Emitted `const s = "café";` (line 15), and `od -c` shows bytes
  `303 251`. Printed with `{s}`.
- Zig: `ast-check` 0, `build-obj` 0.
- Status: **CURRENT**. It compiles against the ASCII source rule.

### F6c. `c: char = 'é'`

- Source: `edge-case-audit.md:129-130` (audit 2 CF-15).
- Probe: `f6c_utf8_char.a7` (compile-only).
- Result: exit 0/0. Emitted `const c: u8 = 'é';` (line 15) and
  `__a7_stdout_print("{c}\n", .{c});`.
- Zig: `ast-check` 0, `build-obj` 0. Zig accepts the literal as a `u8`. INFERENCE: its
  value is 233; the program was not run.
- Status: **CURRENT**.

### T1. `[n]u8` with unbound `n`

- Source: `docs/plan/README.md:375-376`, plan Lane S.
- Probes (compile-only):
  - `t1c_unbound_array_len_decl_only.a7`: `buf: [n]u8` only. Exit 0/0. Emitted
    `const buf: [n]u8 = [_]u8{0} ** n;`. `ast-check` exits 1:
    `t1c...zig:3:17: error: use of undeclared identifier 'n'`.
  - `t1_unbound_array_len.a7` (adds `buf.len`): exit 6/6,
    `Cannot access field on non-struct type: got '[None]u8'`. That rejection is for
    an unrelated reason, and it shows the unbound length inside the type text as `None`.
  - `t1b_unbound_array_len_index.a7` (adds `buf[0] = 1`): exit 6/6, two errors
    `Array index must be integer (index must satisfy 0 <= index < len: index bounds are not proven)`.
    This is also unrelated to the unbound `n`.
- Status: **CURRENT**. `n` itself is never diagnosed. A7 accepts the declaration-only
  form, and Zig rejects it.

### T2a. `z := z` with no outer `z`

- Source: `docs/plan/README.md:379`.
- Probe: `t2a_self_init_no_outer.a7` (compile-only).
- Result: exit 0/0. Emitted `const z = z;` (line 15).
- Zig: `ast-check` exits 1: `t2a...zig:15:15: error: use of undeclared identifier 'z'`.
- Status: **CURRENT**.

### T2b. `z := z` with an outer `z`

- Source: plan Lane S: "`z := z` without an outer `z` (lower correctly if an outer one
  exists)".
- Probes (compile-only):
  - `t2b_self_init_outer_local.a7`: `z := 1`, then `{ z := z; print z }`. Exit 0/0.
    Emitted `const z = 1;`, then `const z_1 = z;` (line 17) and
    `__a7_stdout_print("{any}\n", .{z});` (line 18). The initializer reads the outer
    `z`, which is correct. The use inside the block is not renamed (same defect as
    B10). `ast-check` exits 1: `t2b...zig:17:15: error: unused local constant`.
  - `t2c_self_init_outer_global.a7`: `z :: 5` at file scope, and `z := z` in `main`.
    Exit 0/0. Emitted `const z = 5;` at file scope, and `const z = z;` in the function
    (line 17). `ast-check` exits 1:
    `t2c...zig:17:11: error: local constant shadows declaration of 'z'`.
- Status: **CURRENT**. Neither outer-`z` form produces Zig that builds.

### T3. `ret 0` from `u32` and `usize`

- Source: `docs/plan/README.md:377-378`, plan Lane S (SPEC A.2).
- Probes (compile-only):
  - `t3a_ret0_u32.a7`: exit 6/6,
    `error: Return type mismatch: expected 'u32', got 'i32' [line 5: col 5]`.
  - `t3b_ret0_usize.a7`: exit 6/6,
    `error: Return type mismatch: expected 'usize', got 'i32' [line 5: col 5]`.
  - Control `t3c_u32_controls.a7`: `ret cast(u32, 0)` and `x: u32 = 0`. Exit 0/0.
    Emitted `return @as(u32, 0);` and `const x: u32 = 0;`. `build-obj` exits 0.
- Status: **CURRENT**.

### B1. `arr = [arr[1], arr[0]]`

- Source: plan Lane B item 2 ("prints `2 1`").
- Probe: `b1_array_swap_literal.a7` (**run-allowed**). It uses no `new`, `del`, `ref`,
  slices, overflow or shifts.
- Result: exit 0/0. Emitted `var arr: [2]i32 = .{ 1, 2 };` and
  `arr = .{ arr[1], arr[0] };` (line 16).
- Zig: `ast-check` 0 and `build-obj` 0. `build-exe -O Debug` and `-O ReleaseFast` both
  exit 0. Both runs exit 0 with **stdout `2 2`** and empty stderr.
- Status: **CURRENT**. The expected correct output is `2 1`.

### B2. `case ok` on a tagged union

- Source: `docs/plan/README.md:223-239` (G5) and `:386-387`.
- Probes (compile-only):
  - `b2b_case_ok_no_else.a7`: the README program verbatim. Exit 0/0. Emitted
    `const __a7_match_1 = r;`, then `{ const ok = __a7_match_1; _ = ok; }`
    (lines 10-14), with no tag test. `build-obj` 0.
  - `b2c_case_ok_on_err_value.a7`: `r := Result{err: "bad"}`, where the `case ok`
    branch prints "ok branch taken". Exit 0/0. Emitted
    `const r = Result{ .err = "bad" };` (line 20), then an unconditional block
    `const ok = __a7_match_1; _ = ok; __a7_stdout_print("ok branch taken\n", .{});`
    (lines 24-26). `build-obj` 0. INFERENCE from the emitted Zig: the branch runs for
    an `err` value. Not run, because the probe stores a string.
  - `b2_case_ok_tagged_union.a7` (adds an `else` branch): exit 6/6,
    `Unreachable code: match else branch is unreachable because a previous wildcard pattern covers all values [line 15: col 14]`.
    The A7 semantic pass itself treats `case ok` as a binding wildcard.
- Status: **CURRENT**.

### B3. String `==`: non-foldable against literal

- Source: `edge-case-audit.md:116-118` (CF-09), plan Lane S.
- Probes (compile-only):
  - `b3b_string_eq_params.a7`: `same :: fn(a: string, b: string) bool { ret a == b }`.
    Exit 0/0. Emitted `return (a == b);` with `a: []const u8` (line 15). `build-obj`
    exits 1:
    `b3b...zig:15:15: error: operator == not allowed for type '[]const u8'`.
  - `b3a_string_eq_locals.a7`: `a := "x"; b := "y"; if a == b`. Exit 0/0. Emitted
    `const a = "x"; const b = "y"; if ((a == b))` (lines 15-17). `ast-check` 0 and
    **`build-obj` 0**. This sub-variant is **DIFFERENT**: Zig does not reject it,
    because untyped `const` string literals are `*const [1:0]u8` pointers and `==`
    between them compiles. INFERENCE: the program compares pointers, not contents.
    Not run, because the probe stores string slices.
  - Control `b3c_string_eq_literals.a7`: `if "a" == "a"`. Exit 0/0. Folded to
    `if (true)` (line 15). `build-obj` 0. It works as expected.
- Status: **CURRENT** for the non-foldable string case (parameters). The local-literal
  variant builds as a pointer comparison instead of being rejected by Zig.

### B4. `pts: [3]Pt` without an initializer

- Source: `edge-case-audit.md:116-118` (CF-32).
- Probe: `b4_struct_array_no_init.a7` (compile-only).
- Result: exit 0/0. Emitted `const pts: [3]Pt = [_]Pt{0} ** 3;` (line 19).
- Zig: `ast-check` 0. `build-obj` exits 1:
  `b4...zig:19:30: error: expected type 'b4_struct_array_no_init.Pt', found 'comptime_int'`.
- Status: **CURRENT**.

### B5. Write through a slice, `s[0] = 1`

- Source: `edge-case-audit.md:117-118` (CF-12).
- Probe: `b5_slice_write.a7` (compile-only). `arr: [3]i32 = [1, 2, 3]; s := arr[0..2]; s[0] = 1`.
- Result: exit 0/0. Emitted `const arr: [3]i32 = .{ 1, 2, 3 };` (line 15),
  `var s = arr[0..2];` and `s[0] = 1;`.
- Zig: `ast-check` 0. `build-obj` exits 1:
  `b5...zig:17:6: error: cannot assign to constant`.
- Status: **CURRENT**.

### B6. Mutable global `counter := 0`

- Source: `edge-case-audit.md:119-120` (audit 5 p17).
- Probe: `b6_mutable_global.a7` (compile-only).
- Result: exit 0/0. Emitted `var counter = 0;` (line 14) and `counter += 1;`.
- Zig: `ast-check` 0. `build-obj` exits 1:
  `b6...zig:14:15: error: variable of type 'comptime_int' must be const or comptime`.
- Status: **CURRENT**.

### B7. Write to a by-value array parameter

- Source: `edge-case-audit.md:121` (audit 5 p4b).
- Probe: `b7_byvalue_array_param_write.a7` (compile-only).
- Result: exit 0/0. Emitted `fn set(a: [3]i32) void { a[0] = 7; ... }` (lines 14-15).
- Zig: `ast-check` 0. `build-obj` exits 1:
  `b7...zig:15:6: error: cannot assign to constant`.
- Status: **CURRENT**.

### B8. Write to a `for` binding

- Source: `edge-case-audit.md:121-122` (audit 1 p20).
- Probes (compile-only):
  - `b8a_for_binding_field_write.a7`: `for v in pts { v.x = 9 }`. Exit 0/0. Emitted
    `const pts: [2]Pt = ...;` and `for (pts) |v| { v.x = 9; }` (lines 19-21).
    `build-obj` exits 1: `b8a...zig:21:10: error: cannot assign to constant`.
  - `b8b_for_binding_scalar_write.a7`: `for v in arr { v = 9 }`. Exit 6/6,
    `Cannot assign to immutable binding: 'v' is immutable [line 7: col 9]`. A7
    rejects the scalar form correctly. Only field writes get through.
- Status: **CURRENT** (field-write form).

### B9. `del` of a variable named `p`

- Source: `edge-case-audit.md:123-125` (audit 5 p7, p12).
- Probe: `b9_del_named_p.a7` (compile-only; uses `new` and `del`).
- Result: exit 0/0. Emitted `var p = allocator.create(Pt) catch null;` (line 20) and
  `if (p) |p| allocator.destroy(p);` (line 26).
- Zig: `ast-check` exits 1:
  `b9...zig:26:13: error: capture 'p' shadows local variable from outer scope`. The
  wording differs slightly from the recorded "local constant", because this `p` is a
  `var`.
- Status: **CURRENT**.

### B10. Shadowing in an inner block

- Source: plan Lane B item 1 (sites `ast_preprocessor.py:433-518`,
  `zig.py:645-646, 1505-1516`).
- Probes:
  - `b10_shadow_inner_block.a7` (**run-allowed**): `x := 1; { x := 2; print x }; print x`.
    Exit 0/0. Emitted `const x = 1;`, then `{ const x_1 = 2; __a7_stdout_print("{}\n", .{x}); }`
    (lines 17-18), then `__a7_stdout_print("{}\n", .{x});`.
  - `b10b_shadow_inner_mutated.a7` (**run-allowed**): adds `x += 5` inside the block.
    Exit 0/0. Emitted `var x: i32 = 1;`, `var x_1: i32 = 2;` and `x += 5;` (lines
    15-18). The write goes to the outer `x`.
- Zig:
  - b10: `ast-check` exits 1, `b10...zig:17:15: error: unused local constant` (`x_1`).
  - b10b: `ast-check` exits 1, `b10b...zig:17:13: error: unused local variable` (`x_1`).
  - Neither built, so nothing was run and **nothing prints**.
- Status: **CURRENT**. The inner declaration is renamed, but its uses are not. INFERENCE:
  any use of the inner name resolves to the outer binding, so Zig's unused-local check
  always rejects the output. That hides the wrong-value miscompile (`1 1` instead of
  `2 1`) rather than letting it run.

### B11. `defer x = 1`

- Source: plan Lane B item 5 (`zig.py:2378-2391`).
- Probe: `b11_defer_assign.a7` (compile-only).
- Result: exit 0/0. Emitted `var x: i32 = 0;` and `defer void;` (lines 15-16).
- Zig:
  - `ast-check` exits 1: `b11...zig:15:9: error: local variable is never mutated`.
  - `build-obj` exits 1 with that error plus
    `b11...zig:16:11: error: value of type 'type' ignored` at `defer void;`.
- Status: **CURRENT**.

### B12. Zig keywords and preamble names as A7 identifiers

- Source: plan Lane B item 4.
- Probes (compile-only): `b12_ident_<name>.a7`, each with `<name> := 3` and a print of
  it. All exit 0/0 in A7.

| Name | Emitted decl / use | Zig result |
| --- | --- | --- |
| `test` | `const test = 3;` / `.{@"test"}` | ast-check 1: `15:11: error: expected 'an identifier', found 'test'` |
| `var` | `const var = 3;` / `.{var}` | ast-check 1: `expected 'an identifier', found 'var'` |
| `const` | `const const = 3;` / `.{const}` | ast-check 1: `expected 'an identifier', found 'const'` |
| `std` | `const std = 3;` / `.{std}` | ast-check 1: `local constant shadows declaration of 'std'` |
| `type` | `const type = 3;` / `.{@"type"}` | ast-check 1: `name shadows primitive 'type'` |
| `allocator` | `const allocator = 3;` / `.{allocator}` | ast-check 0, build-obj 0 (DIFFERENT, see below) |
| `allocator` + `new`/`del` (`b12g`) | `const allocator = 3;`, then `allocator.create(Pt)`, `if (q) \|p\| allocator.destroy(p);` | ast-check 1: `20:11: error: local constant shadows declaration of 'allocator'` |

- The plain `allocator` probe builds, because the preamble line
  `const allocator = std.heap.page_allocator;` is emitted only when the program uses
  `new` or `del` (compare `b9`/`b12g` line 2 with `b12_ident_allocator`). With
  `new`/`del` in the same function (`b12g`), the collision reproduces. INFERENCE:
  without Zig's shadowing error, `allocator.create` would resolve to the user's
  integer. `b12g` also shows that `del q` lowers with the fixed capture `|p|`.
- Status: **CURRENT**. The plain `allocator` variant is DIFFERENT (harmless when no
  preamble allocator is emitted).

### B13. Signed `/=` and `%=`

- Source: plan Lane B item 6 (`zig.py:2356`).
- Probes (all **run-allowed**, with literal non-zero divisors and no overflow):
  - `b13a_signed_divmod_assign_stmt.a7`: `x: i32 = -7; x /= 2; y: i32 = -7; y %= 2`.
    Exit 0/0. Emitted `x /= 2;` and `y %= 2;` (lines 16, 18). `build-obj` exits 1:
    `b13a...zig:16:7: error: division with 'i32' and 'i32': signed integers must use @divTrunc, @divFloor, or @divExact`.
    Zig stopped at the first error in the function, so `%=` got its own probe.
  - `b13d_signed_mod_assign_stmt.a7`: `y %= 2` only. Emitted `y %= 2;`. `build-obj`
    exits 1:
    `16:5: error: remainder division with 'i32' and 'i32': signed integers and floats must use @rem or @mod`.
  - `b13c_signed_divmod_assign_for_update_untyped.a7`: `for i := -100; i < 0; i /= 2`
    and `for j := -7; j <= -5; j %= 4`. Exit 0/0. Emitted
    `while ((i < 0)) : (i /= 2)` and `while ((j <= -5)) : (j %= 4)`, with `var i: i32`.
    `build-obj` exits 1: `17:30: error: division with 'i32' and 'i32': signed integers must use @divTrunc...`.
  - `b13e_signed_mod_assign_for_update.a7`: the `%=` loop only. `build-obj` exits 1:
    `17:30: error: remainder division with 'i32' and 'i32': signed integers and floats must use @rem or @mod`.
  - `b13b_signed_divmod_assign_for_update.a7` (typed init `for i: i32 = -100; ...`):
    exit 5/5, `Unexpected token 'i' after parsing complete program [line 5: col 24]`.
    Side observation: the typed C-style `for` init does not parse, and the error is
    misleading (it reports the top-level parser message for a statement inside `main`).
  - Control `b13f_unsigned_divmod_assign_control.a7` (`u32`): builds. Debug and
    ReleaseFast both print `3 1` with exit 0.
- No signed program could run, because Zig rejects all four at Sema.
- Status: **CURRENT**.

### B14. `math.` callee chosen by text prefix

- Source: plan Lane B item 7 (`zig.py:1631-1645`). In the current tree,
  `a7/backends/zig.py:1625` checks `file_module_call` first, and `:1645` is
  `elif func.startswith('math.'):`.
- Probes:
  - `b14d_struct_value_named_math_used.a7` (**run-allowed**; stored function pointer,
    no slices): `Ops :: struct { sqrt: fn(f64) f64 }`; `math := Ops{sqrt: halve}`;
    `g := math.sqrt`; `io.println("{} {}", math.sqrt(9.0), g(9.0))`. Exit 0/0. Emitted
    `const g = math.sqrt;` and `__a7_stdout_print("{} {}\n", .{ @sqrt(9.0), g(9.0) });`
    (lines 24-25). `build-obj` 0. Debug and ReleaseFast both exit 0 with
    **stdout `3 4.5`**, where `4.5 4.5` is correct. This is a silent wrong result.
  - `b14a_struct_value_named_math.a7` (run-allowed): the same without `g`. Emitted
    `const math = Ops{ .sqrt = halve };` and `.{@sqrt(9.0)}` (lines 23-24). `ast-check`
    exits 1: `23:11: error: unused local constant`. Not run.
  - `b14b_local_module_alias_math.a7` (compile-only): `math :: import "b14_mymath"`.
    Emitted `module_b14_mymath__sqrt(9.0)`. `build-obj` 0. Not affected, because the
    `file_module_call` path runs before the prefix check.
  - `b14c_std_io_alias_math.a7` (compile-only): `math :: import "std/io"` with
    `math.println("hi")`. Emitted `__a7_stdout_print("hi\n", .{})`. `build-obj` 0. Not
    affected, because `println` is not in the builtin short list.
- Status: **CURRENT**. A local struct value named `math` has its call hijacked. A
  module alias named `math` is not affected.

### B15. Three failing baseline tests in `test/test_pipeline_native.py`

- Command: `PYTHONPATH=. MISE_UV_VERSION=0.12.6 uv run pytest test/test_pipeline_native.py -q --tb=short -rf -p no:cacheprovider`
- Result: `4 failed, 1 passed in 38.79s`, exit 1 (`b15_pytest_native.log`). In each of
  the three named tests, A7 compiles, and `zig build-exe -O Debug` (`build()`,
  `test_pipeline_native.py:45`) fails:
  - `test_valid_a7_bindings_build_with_zig[zig-keyword-local]` (body
    `error := 1; io.println("{}", error)`): `main.zig:15:11: error: expected 'an identifier', found 'error'` at `const error = 1;`.
    The keyword is not escaped at the declaration, like B12.
  - `[unused-loop-capture]` (body `a: [3]i32; for x in a {}`):
    `main.zig:4:14: error: unused capture` at `for (a) |x| {`. The emitted file is only
    86 bytes. INFERENCE: no preamble is emitted and no `_ = x;` discard is added.
  - `[shadowed-loop-capture]` (body `x := 9; a: [3]i32; for x in a {...}; io.println x`):
    `main.zig:17:14: error: capture 'x' shadows local constant from outer scope` at
    `for (a) |x| {`, pointing back to `const x = 9;` at `15:11`.
- A fourth failure is not assigned to B15:
  `test_large_integer_folding_preserves_exact_quotient_and_remainder`. For Debug and
  ReleaseFast, observed stdout was `9007199254740992 1\n9007199254740993 0\n` and
  expected was `9007199254740993 0\n9007199254740993 0\n`. The folded line is wrong,
  and the runtime line is right. This is the 12th baseline failure (plan Lane S).
- Status: **CURRENT**.

### B16. Eight failing tests in `test_pipeline_artifacts.py` and `test_pipeline_diagnostics.py`

- Command: `PYTHONPATH=. MISE_UV_VERSION=0.12.6 uv run pytest test/test_pipeline_artifacts.py test/test_pipeline_diagnostics.py -q --tb=short -rf -p no:cacheprovider`
- Result: `8 failed, 3 passed in 1.05s`, exit 1 (`b16_pytest_artifacts_diagnostics.log`).
  All of these tests use pytest `tmp_path`, so no repository file was touched.
  1. `test_pipeline_artifacts.py::test_cli_rejects_input_destination_without_changing_source[--output]`
     (`:33`): `AssertionError: --output destroyed the A7 input`. The source became
     `b'pub fn main() void {}\n'`, but should still be `b'// Preserve... :: fn() {}\n'`.
  2. `...[--doc-out]` (`:33`): `AssertionError: --doc-out destroyed the A7 input`. The
     source became `b"# Compilati... 22 bytes |\n"`.
  3. `test_failed_compile_does_not_advertise_stale_output` (`:48`):
     `assert 'output_path' not in {'output_path': '.../main.zig'}`.
  4. `test_output_write_failure_does_not_advertise_directory_as_artifact` (`:61`):
     `assert 'output_path' not in {'output_path': '.../destination.zig'}`.
  5. `test_pipeline_diagnostics.py::test_cli_source_diagnostic_points_to_offending_token[parse]`
     (`:58`): `assert 9 == 10`. The span `start_column` is 9, and the test expects 10.
  6. `test_missing_import_diagnostic_locates_import_declaration` (`:75`):
     `AssertionError: Missing import has no source location / assert None is not None`.
     The detail is `{'file': '.../main.a7', 'message': "Error loading module 'mi...", 'type': 'SemanticError'}`,
     with no `span`.
  7. `test_imported_parse_error_is_a_source_failure_with_module_location` (`:90`):
     `assert 8 in {<ExitCode.PARSE: 5>, <ExitCode.SEMANTIC: 6>}`. The CLI exited 8
     (internal), with JSON `"exception_type": "ParseError"`, `"span": null`, and
     message "...Expected expression".
  8. `test_imported_semantic_error_preserves_origin_file` (`:110`):
     `assert '/tmp/pytest-...or_p0/main.a7' == '/tmp/pytest-..._p0/helper.a7'`. The
     diagnostic names `main.a7`, not the module `helper.a7`.
- Status: **CURRENT**. All 8 fail.

## Side observations (not assigned items)

- `for i: i32 = -100; ...` (typed C-style `for` init) does not parse. The error is
  `Unexpected token 'i' after parsing complete program [line 5: col 24]` (`b13b`).
- The `t1` and `t1b` diagnostics for an unbound array length are misleading
  (`'[None]u8'`, "Array index must be integer").
- `f2f`: a malformed struct field before `main` is reported at the struct's closing
  `}`, column 0, not at the field.
- `unused-loop-capture` shows that an unused `for` capture gets no discard, like B10's
  unused renamed locals.
