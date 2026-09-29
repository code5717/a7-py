> **Source:** Claude research subagent, Wave 0 reproduction ledger part 2 (safety, memory and docs claims) and compatibility scan (parts C, D and E), run against commit `701c679` with Zig 0.16.0.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim. Probe files, scan scripts and hit lists it cites stay under `tmp/repro2/`, which is not tracked. Only three probes marked run-allowed were built and run.

# Wave 0 reproduction ledger, part 2 of 2, plus compatibility scan

Date: 2026-09-16. Tree: `master` at `701c679` with uncommitted docs and test changes. `a7/` has no uncommitted changes. Zig 0.16.0.
Nothing was fixed. Every file this work created is under `tmp/repro2/`, and this report is the only other output.

## How to re-run

- Probe sources come from `tmp/repro2/gen_probes.py`, which writes them to `tmp/repro2/probes/*.a7`. Every probe starts with `// probe: compile-only` or `// probe: run-allowed`.
- The runner is `tmp/repro2/run_probes.py [names]`. For each probe it does the following:
  1. Compile: `MISE_UV_VERSION=0.12.6 uv run a7 tmp/repro2/probes/<id>.a7 --format json --output tmp/repro2/out/<id>.zig`.
  2. If A7 exits 0: `zig ast-check tmp/repro2/out/<id>.zig`, then `zig build-obj -fno-emit-bin <id>.zig` run inside `tmp/repro2/out`.
  3. Only for `run-allowed` probes whose build-obj passes: `zig build-exe -ODebug|-OReleaseFast <id>.zig -femit-bin=<id>_<opt>`, then run the binary.
- Each probe's record is in `tmp/repro2/out/<id>.rec.md`: command, exit code, diagnostics, user part of the emitted Zig, and Zig results. Aggregates are in `tmp/repro2/results_all.md`, `results_partC_triggers.md` and `results_C4b3.md`.
- Only 3 probes were built and run: `S13_int_folding`, `D7a_float_mod_folded` and `D7c_float_mod_runtime`, each in Debug and ReleaseFast. `D7b` is marked run-allowed but A7 rejected it with exit 6, so it was never built. None of the three uses `new`, `del`, `ref`, returned slices, overflow, a possibly-zero divisor, `MIN / -1` or wide shifts.
- Prior probes from `tmp/reports/w0-audit-work/` were re-run as equivalent new probes, and the results match the prior logs wherever those logs show a result: `p_block` is S1, `p_call` is S3, `p_while` is S2b, `p_fmod` is D7a, `p_intdiv` is S13 (different operands), `p_ret0` is C6a, and `p_moved` is S4a (`new Pt` instead of `new i32`).

**Which Zig check to trust (control X0):**
- The control is a non-foldable string `==` (`probes/X0_control_string_eq.a7`). A7 exits 0 and emits `return (a == b);`.
  - `zig ast-check` exits 0, so it does not catch the error.
  - A wrapper file with `comptime { _ = @import("X.zig").main; }` also passes, because the wrapper does not force analysis of function bodies.
  - `zig build-obj -fno-emit-bin` on the emitted file directly exits 1 with `operator == not allowed for type '[]const u8'`.
- Only the direct build-obj result counts. Rows that exit 6 have "Zig: n/a" because A7 writes no output.
- Zig analyzes lazily: an unreferenced declaration can pass build-obj even when its body is invalid (see C4b4).

Status meanings: CURRENT means the reported behavior reproduces as described. NOT REPRODUCED means the reported behavior does not occur. DIFFERENT means the behavior reproduces in a different form than reported.

---

## Part A: safety and memory (all compile-only unless marked)

| id | source | probe | A7 exit / key diagnostic | relevant emitted Zig | Zig build-obj | status |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | plan.md:9; safety.py:301-306 | `S1_block_fact` | 0 | `var x: i32 = 5; { x = 0; } const y = @divTrunc(10, x);` | 0 | CURRENT |
| S2 | plan.md:106 (2); safety.py:345-352 | `S2_while_fact` (divide, then `x = 0` in body); `S2b_while_assign_then_divide_after` (the `p_while` shape re-run) | 0 and 0 | S2: `while ((i < 3)) { const y = @divTrunc(10, x); ... x = 0; ...}`. S2b: `while (...) { x = 0; ... } const y = @divTrunc(10, x);` | 0 and 0 | CURRENT (both shapes) |
| S3 | plan.md:106 (3); safety.py:444-447 | `S3_ref_call_fact` | 0 | `fn zero(v: ?*i32) void { v.?.* = 0; } ... zero(&x); const y = @divTrunc(10, x);` | 0 | CURRENT |
| S4 | edge-case-audit.md:103-106; safety.py:236, 247, 290 (`moved_symbols` is not reset per function) | `S4a_del_other_fn`, plus `S4b_del_then_branch_read_else` and `S4c_del_block_then_shadow` | S4a: 6, `18:22 Use after move or delete ... 'p' was moved or deleted earlier` (read of an unrelated `p: i32` in `second`). S4b: 6 at 18:26 and 19:13 (else-branch read and del). S4c: 6 at 14:10 (`q := p + 1` on the new `p := 5`). | n/a | n/a | CURRENT (false errors) |
| S5 | edge-case-audit.md:81-84 (q13) | `S5_return_local_slice` (main uses `s.len`) | 0 | `fn get() []i32 { var buf: [4]i32 = .{ 1, 2, 3, 4 }; buf[0] = 5; return buf[0..2]; }` | 0 | CURRENT |
| S6 | docs/plan/README.md:130-141 | `S6_alias_double_del` (names `p`, `q`); `S6b_alias_double_del_renamed` (`a`, `b`) | 0 and 0 | `if (a) \|p\| allocator.destroy(p); if (b) \|p\| allocator.destroy(p);` | S6: 1, `capture 'p' shadows local constant` (the Lane B del-capture clash, a separate defect). S6b: 0, two destroys on one allocation. | CURRENT |
| S7 | edge-case-audit.md:92 (p06) | `S7_double_del_while`; `S7b_double_del_while_renamed` | 0 and 0 | `while ((i < 2)) { if (a) \|p\| allocator.destroy(p); i += 1; }` | S7: 1 (same capture clash). S7b: 0. | CURRENT |
| S8 | edge-case-audit.md:89-91 (p13) | `S8_del_through_ref_param`; `S8b_del_through_ref_param_renamed` | 0 and 0 | `fn drop_it(bx: ?*Box) void { if (bx) \|p\| allocator.destroy(p); } ... var b = Box{ .value = 0 }; drop_it(&b); b.value = 1;` | S8: 1 (capture `p` shadows parameter `p`). S8b: 0; destroys a stack address and writes after. | CURRENT |
| S9 | edge-case-audit.md:100-102 (CF-25) | `S9_second_ref_write` | 6, `6:5 Cannot dereference non-pointer type (reference must be proven non-nil before assignment through it: reference may be nil)` on `dst = 1` | n/a | n/a | CURRENT (safety.py:326-327 overwrites the parameter fact with the right-hand-side fact) |
| S10 | edge-case-audit.md:107-109 | `S10_block_defer_del` | 6, `17:5` and `18:22 Use after move or delete ... 'b'` on the uses after `defer { io.println(..); del b }` | n/a | n/a | CURRENT |
| S11a | edge-case-audit.md:110-112 (CF-26) | `S11a_index_ref_array_param` | 6, `5:9 Cannot index this type: got 'ref [4]i32'` | n/a | n/a | CURRENT |
| S11b | same (CF-10) | `S11b_index_slice_param` (`xs[0]`), `S11c_slice_slice_param` (`xs[0..2]`), `S11d_index_string_param` (`text[0]`, returns `char`), `S11e_slice_string_param` (`text[0..2]`), `S11f_guarded_slice_slice_param`, `S11g_guarded_index_string_param` | All exit 6, but none is a type error. S11b and S11d: `index must satisfy 0 <= index < len: index bounds are not proven`. S11c, S11e and S11f (guarded by `n <= xs.len`): `slice bounds are not proven`. S11g: `5:12 Cannot access field on non-struct type: got 'string'`, so `.len` is not available on a string parameter. | n/a | n/a | DIFFERENT: indexing and slicing slice and string parameters type-check, but the bounds proof always rejects them. No guard form exists for string parameters. |
| S12 | edge-case-audit.md (guarded index) | `S12a_guarded_index_slice_param` (`if i < xs.len { ret xs[i] }`, `i: usize` parameter); `S12c_guarded_index_local_slice` (local `xs := arr[0..4]`, `i: usize = 2`, guarded); `S12b_guarded_index_local_array` | S12a: 6, `6:13 index bounds are not proven`. S12c: 0, but the guard plays no part: `i` is the constant 2 and `xs` has known length 4 (safety.py:422, 597-600), and `i < xs.len` produces no fact (safety.py:688-694 handles only `>=`, `>`, `!= 0` and `nil`). S12b: 6, `7:12 Cannot access field on non-struct type: got '[4]i32'` (`.len` on a fixed array). | S12c: `if ((i < xs.len)) { ... xs[i] }` | S12c: 0 | CURRENT (a `< len` guard never proves an index) |
| S13a | plan.md:118; ast_preprocessor.py:590-649 | `S13_int_folding` (**run-allowed**) | 0 | `const a: i64 = 9007199254740992;` (folded from `9007199254740993 / 1`) and `const g: i64 = @divTrunc(big, one);` | 0. Debug and ReleaseFast both print `9007199254740992 -3 -2` / `9007199254740993 -3 -2` | CURRENT (the fold loses precision; runtime is exact) |
| S13b | same | same | 0 | `const b: i32 = -3; const c: i32 = -2;` against `@divTrunc(n, d)` and `@rem(n, d)` | Runtime prints `-3 -2` | NOT REPRODUCED (negative `/` and `%` folding matches runtime truncation) |

Side findings from Part A that are not in the inventory:
- **S12d**, `S12d_literal_arg_to_usize_param`: `twice(2)` against `i: usize` exits 6 with `9:22 Argument type mismatch: expected 'usize', got 'i32' (Argument 1)`. This is the argument-position twin of C6, and the C6 proposal as worded does not cover it.
- The del-capture name clash (`|p|`) makes Zig reject S6, S7 and S8 whenever the user variable is named `p`.
- **X1 (optional, outside the requested items; not in the inventory)**, `X1_compound_assign_fact`: `x := 5; x -= 5; y := 10 / x` exits 0 and emits `var x: i32 = 5; x -= 5; const y = @divTrunc(10, x);`. build-obj exits 0; not run. safety.py:311-328 sets the target's fact to the right-hand-side fact (`5`, non-zero) for compound assignments too, so it accepts a certain division by zero. This belongs with the P0b fact group.

## Part B: docs claims

| id | source | probe | A7 exit / key diagnostic | relevant emitted Zig | Zig build-obj | status |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | SPEC.md:192 | `D1a_ref_fn_void_nil` (`fn_ptr: ref fn() void = nil`); `D1b_ref_fn_nil` (`ref fn() = nil`) | D1a: 6, `5:22 Undefined type (Type 'void')`. D1b: 0. | D1b: `const fn_ptr: ?**const fn () void = null;` (a pointer to a function pointer) | D1b: 0 | CURRENT (the SPEC form is rejected, the undocumented form is accepted and lowers to a double pointer) |
| D2 | SPEC.md:410-411 vs 447-448 | `D2_typed_decl_reassign` (`x: i32 = 42; x = 1` in main); `D2b_typed_global_reassign` (file-scope `MAX_SIZE: i32 = 1000`, then `MAX_SIZE = 1`) | 0 and 0 | `var x: i32 = 42; x = 1;` and `var MAX_SIZE: i32 = 1000; ... MAX_SIZE = 1;` | 0 and 0 | CURRENT. Typed declarations are mutable, which matches :448 and contradicts :410-411 and :447. |
| D3 | SPEC.md:698-716 | `D3a_spec_generics_verbatim` (all three); `D3b` swap only; `D3c` add only; `D3d` convert only | D3a: 6 (`6:13 Undefined type (Identifier 'a')`, `Undefined type (Type 'Numeric')` twice). D3b: 6 (`Undefined type (Identifier 'a')` at `temp := a`). D3c: 5, `5:5 Unexpected token 'ret' after parsing complete program`. D3d: 5, `5:1 Unexpected token 'where' after parsing complete program`. | n/a | n/a | CURRENT (no verbatim example compiles) |
| D4 | SPEC.md:788 and 817-822 | `D4a_spec_printf` (SPEC increment and main, verbatim); `D4b_spec_bare_sqrt` (Vec2 methods, verbatim, inside main) | D4a: 6, `11:5 Undefined type (Identifier 'printf')` and `Cannot call undefined identifier 'printf'`. D4b: 6, the same for `sqrt` at 9:9 and 14:12. | n/a | n/a | CURRENT |
| D5 | plan.md:93, 144 (P1) | `D5a_int_type`, `D5b_uint_type`, `D5c_float_type` | All exit 5: `6:5 Unexpected token 'io' after parsing complete program`. The error points at line 6 while the failure is on line 5. `--mode tokens` shows `int` lexed as keyword token `INT` (tokens.py:55, 200). `uint` and `float` are keywords too (tokens.py:78, 223 and 49, 194). None of the three is in the SPEC.md:96-105 keyword list. | n/a | n/a | CURRENT (reserved keywords that do not resolve as types, with a misleading location) |
| D6 | plan.md:93; edge-case-audit.md:93-94 (EC1-C08) | `D6a_struct_no_init`; `D6b_struct_no_init_zero_iter_loop` | 0 and 0 | `var last: Pt = undefined;` in both. D6b: `for (empty) \|p\| { last = p; } __a7_stdout_print("{}\n", .{last.x});` | 0 and 0 (not run: it reads undefined memory) | CURRENT |
| D7 | plan.md:93 | `D7a_float_mod_folded` (**run-allowed**): `-7.5 % 2.0`. `D7c_float_mod_runtime` (**run-allowed**): `x % y` under `if y != 0.0`. `D7b_float_mod_folded_neg_divisor`: `7.5 % -2.0`, `-7.5 % -2.0`. `D7d_float_mod_runtime_unguarded`. | D7a: 0. D7c: 0. D7b: 6, twice `Unsafe type cast (division/modulo divisor must be non-zero: divisor may be zero)` with `span: None` (no line). D7d: 0 (an unguarded float variable divisor initialized from `2.0` is accepted). | D7a: `const fa: f64 = 0.5;`. D7c and D7d: `const ra: f64 = @rem(x, y);` | D7a runs `0.5` in Debug and ReleaseFast. D7c runs `-1.5` in both. | CURRENT: the fold uses Python floor-mod (`0.5`) while runtime `@rem` gives `-1.5`. New: a negative float literal divisor is "may be zero" (safety.py:497-501 keeps no nonzero fact through unary minus on floats), and that diagnostic has no span. |
| D8 | plan.md:144 (P1); SPEC.md:68-76 | `D8_hash_comment` | 0; `--mode tokens` drops the `# hash comment` line | `fn __a7_user_main() void { __a7_stdout_print("ok\n", .{}); }` | 0 | CURRENT (`#` is a line comment, tokens.py:408-412, not in SPEC 2.2) |
| D9 | SPEC.md:129 (`...` listed); plan.md:142 | `D9a_question_token` (`p: ?i32 = nil`); `D9b_ellipsis_token` (`xs: ...i32`); `D9c_tokens_only`; `D9d_ellipsis_tokens_only` | D9a and D9c: 4, `Unexpected character: '?'`. D9b: 5, `5:5 Unexpected token 'ret' after parsing complete program`. D9d: 5. `--mode tokens` lexes `...` as `DOT_DOT` then `DOT`. | n/a | n/a | CURRENT (`?` is not a token, and `...` is not one token) |

Cross-cutting finding (a Lane F item): `Unexpected token '<tok>' after parsing complete program` appears in D3c, D3d, D5 and D9b, and it points at the wrong token. Using D5 as the example:
1. The real error on line 5 (`x: int = 1`) does not contain "Expected declaration", so `synchronize()` swallows it (parser.py:194).
2. The next line (`io.println(..)`) then raises "Expected declaration".
3. Exactly one declaration (the import) had parsed, so Case 1 (parser.py:180-186) fires and points at `io`.

This is the same path as C5b. With two or more earlier declarations, a program like this would compile with the broken declaration silently dropped.

## Counts

- **Part A, counted against the task's 13 ids:**
  - **CURRENT 11:** S1-S10 and S12. S12c compiles only because its index is a constant.
  - **Split, 2:**
    - S11 is CURRENT for `ref [N]T` and DIFFERENT for slice and string parameters, which type-check but always fail the bounds proof.
    - S13 is CURRENT for the precision loss in `9007199254740993 / 1` and NOT REPRODUCED for negative `/` and `%` folding.
  - At row level (15 rows): CURRENT 13, DIFFERENT 1, NOT REPRODUCED 1.
- **Part B, 9 ids: CURRENT 9.** D7 has two new sub-findings: a negative float literal divisor is rejected as "may be zero", and that diagnostic has no span.

---

## Part C: compatibility scan

### Method

1. **Test corpus.** `tmp/repro2/scan/capture_plugin.py` ran as a pytest plugin (`PYTHONPATH=.:tmp/repro2/scan uv run pytest -p capture_plugin`).
   - It recorded every source that reached `Tokenizer.__init__`, keyed by test node id, and every `.a7` file handed to a subprocess.
   - It blocked all subprocesses, so no Zig build or binary ran. The one exception is `zig version`, which it faked so Zig-gated tests reach their compile step.
   - Result: 2617 rows, 2105 unique sources (`corpus.jsonl`).
   - Blocked calls are listed in `blocked_subprocess.jsonl`. `test_release_tooling::test_installed_cli_entrypoint_works` only tokenizes `001_hello`; it shows up as a user of other examples because of the sibling glob, and it is excluded below.
2. **Other inputs.** `tmp/repro2/scan/analyze.py` also reads `examples/*.a7` and every fenced `a7` block in `docs/SPEC.md` (62) and `site/public/docs/*.md` (6). That makes 2216 records (`hits.jsonl`, `hits_readable.txt`).
   - `README.md` has 14 code fences and none is A7 (`grep -n '^```' README.md`): 12 are `bash` or `text`, and the untagged one at README.md:129-131 is the pipeline diagram. README contains no A7 program to scan.
   - Backend-gated sources: `A7Compiler` skips type checking and safety when `_backend_unsupported_feature_errors` fires (compile.py:263). Some tests call the passes directly and would reach safety on such sources (variadic, `@size_of`). All 711 test sources that exit 6 were re-run with that gate replaced by `[]` (`scan/gap6b.txt`). None reached a C1-C4 hit except one parse-only test that is already rejected (`test_parser_integration.py:383`, `x := cast(i32, 3.14)`).
3. **C1 detector.** A `StrictSafety` subclass of `SafetyProofPass` implements P0b rules (1)-(3):
   - Block facts survive block exit. If, match and else branches are joined.
   - Names assigned in a loop body or update, including by-ref call roots, are dropped at loop entry.
   - By-ref argument roots are dropped after a call.
   It runs on the same typed AST as the real pass. A hit is an obligation that the real pass proves and the strict pass does not.
4. **C2-C4 detectors.** AST detectors over the typed AST.
5. **C5 detectors.** A counter on `Parser.synchronize` flags a successful parse that needed recovery. Re-tokenizing with a trailing sentinel declaration flags an unclosed comment at EOF, because the sentinel gets swallowed.
6. **C6 detector.** Matches the `Return type mismatch: expected 'u..', got 'i32'` diagnostic.
7. **Positive controls** (`scan/controls.out`), all detected:
   - S1, S2, S2b and S3 give C1 hits.
   - S5 gives C2a, S6b and S7b give C2b, S8b gives C2c.
   - X0 gives C3; C3a (folded `"a" == "a"`) is correctly not flagged.
   - C4a, C4b, C4c, C4e and C4f probes are flagged.
   - C5a, C5b and C5c are flagged, and C6a is flagged.
8. **C1 rule attribution** (`scan/c1_toggles.out`): every example hit comes from rule (2). Rules (1) and (3) produce zero hits outside the probes.
9. **Greps** for doc fragments that do not compile: `scan/greps1.txt` through `greps6.txt`.

### C1: block, loop and call fact changes (P0b 1-3)

5 programs are affected, all examples, all through rule (2):

| file:line | expression | why it changes |
| --- | --- | --- |
| examples/029_sorting.a7:20, 21, 22, 23 | `arr[j]`, `arr[j + 1]` | `j` has a fact only from `j := cast(usize, 0)`, and `j += 1` is ignored today. `j < limit` gives no upper bound. |
| examples/030_calculator.a7:62 | `x / guess` | `guess` is non-zero only from `guess := x / 2.0`. It is reassigned at :72. |
| examples/032_prime_numbers.a7:11 | `n % d` | `d := 2` in the for-init, `d += 1` in the update |
| examples/041_route_simulation.a7:36, 38 | `dx[i]`, `dy[i]` | `i := cast(usize, 0)` with `i += 1`. `i < 6` is not turned into a fact today (safety.py:688-694 handles only `>=` and `>`), and the `for` branch at :353-363 never reads condition facts. |
| examples/042_gradebook.a7:27, 29, 31 | `student.scores[i]` | same as 041 |

- **Tests that would change:**
  - `test/test_codegen_zig.py:143` `test_example_compiles` and `:176` `test_ast_check`, parametrized over the 5 examples.
  - `test/test_examples_e2e.py:36`, which runs all examples.
  - The artifact gate `scripts/build_examples.py` (debug and release).
  - Goldens `test/fixtures/golden_outputs/{029_sorting,030_calculator,032_prime_numbers,041_route_simulation,042_gradebook}.out` become unreachable; their content does not change.
- **Docs:** 0 hits. `site/public/docs/language.md:45` `sum_to` compiles and has no division or index.
- **Note:** 041 and 042 would not change if rule (2) came with upper-bound facts from literal `i < N` conditions, including in C-style `for` (`i < 6` and `i < 3` against arrays of exactly that size). 029 would still change: proving `j + 1 < 5` needs `limit` in `[0, 4]`, derived from `limit := cast(usize, 4) - i`, which takes interval propagation rather than a literal condition. 030 and 032 would still change as well.

### C2: returned local slices, double `del`, `del` through a `ref` parameter

**0 affected programs.**
- C2a (returned slice of a local array): 0 in examples, tests and docs.
- C2b (double `del` through an alias or in a loop): 0.
  - The detector flagged `test/test_cast_safety_matrix.py:280` (`test_assignment_after_del_reinitializes_binding`), which does `del box`, `box = new Box`, `del box`. That is not an alias or loop double delete, and the test asserts success. It must stay accepted and is the natural guard test for the new rule.
- C2c (`del` through a `ref` parameter): 0.
- Doc and example `del` sites each delete once and are unaffected: SPEC.md:1018, 1031, 1051; examples/011_memory.a7:17; examples/037_language_tour.a7:123.

### C3: rejecting non-foldable string `==`

**0 affected programs** in examples and tests. No compiled source has a non-literal string `==` or `!=`; control X0 confirms the detector works.
- Must keep working: `test/test_ast_preprocessor.py:385` (`"a" == "a"` folds). Probe C3a confirms it folds to `const same = true;`.
- Doc content only: `docs/SPEC.md:537` `if name == "admin" or permissions.admin {`. It sits in the fragment starting at SPEC.md:515, which already fails to parse as a file (exit 5), so no exit code changes. The snippet would show a construct that C3 rejects.

### C4: slice writes, untyped mutable globals, by-value array parameter writes, `for` bindings, unbound `[n]u8`, `z := z`

- **C4a** (write through a slice): 0.
- **C4c** (write to a by-value array parameter): 0.
- **C4d** (write to a `for` binding): 0. **No-op:** A7 already rejects it (`C4d_write_for_binding`, exit 6, `Cannot assign to immutable binding: 'v' is immutable`).
- **C4e** (unbound `[n]u8`): 0 compiled.
  - Doc-only: SPEC.md:1097-1098 `[N]usize` and 1102-1105 `[N]$T` etc. are in the SPEC.md:1094 design-target block, which already fails to parse (exit 5).
- **C4f** (`z := z`): 0.
- **C4b** (untyped mutable global): the answer depends on how the rule is scoped.
  - What Zig rejects today:
    - A **referenced** `var g = <int, char or float literal>` fails build-obj (probes C4b, C4b2, and C4b3 for char and float).
    - bool, string, array-literal and struct globals build even when referenced (C4b3).
    - An **unreferenced** `var x = 42;` builds (`C4b4_global_int_unused`, build-obj 0), because Zig analyzes lazily.
  - **Reading 1: reject only referenced numeric, char or float literal globals.** This matches Lane S's "reject where Zig already rejects". **0 affected programs.** Neither test below references its global.
  - **Reading 2: reject every untyped mutable global.** This rejects programs that A7 accepts and Zig builds today, so it fails the triage test (plan.md:19) and needs a packet. **2 test programs change:**
    - `test/test_codegen_zig.py:482`: `x := 42` alone, asserts `'var x = 42' in zig`.
    - `test/test_codegen_zig.py:1021`: `nl := '\n'` alone.
  - SPEC fragments that compile as-is (exit 0) and declare a numeric global: SPEC.md:306 `x := 42`, 384 `x := 42`, 415 `count := 0`. None is referenced at file scope, so they change only under Reading 2.
  - Non-numeric fragments that change only under Reading 2: SPEC.md:285 `part := name[1..4]`, 337 `value := Number{i: 42}`, 420 `name := "John"`, 918 `p := Pair(i32, string){...}`.
  - Parse-only tests that never run semantics do not change: test_parser_basic.py:38; test_parser_edge_cases.py:92-96; test_parser_advanced_edge_cases.py:63, 367; test_parser_integration.py:381, 383, 420, 471; the random programs in test_parser_fuzzing.py.

### C5: parse errors always fail and file-scope statements are rejected

Silent drops confirmed by probes:
- `C5a_file_scope_statement`: `io.println(..)` at file scope after `main` compiles with exit 0.
- `C5b_parse_error_after_decl`: `broken :: fn( {` after `main` compiles with exit 0, and the declaration disappears.
- `C5c_unclosed_block_comment`: exit 0.

Every file-scope statement goes through `synchronize()` (parser.py:171-199). No top-level non-declaration node survives parsing.

**Affected programs: 4 sources, plus the example-driven tests, plus 4 doc fragments.**

| file:line | what relies on the silent behavior | would change |
| --- | --- | --- |
| examples/003_comments.a7:28-29 | `/* Note: ...` never closed; the tokenizer accepts EOF (tokens.py:395-406) | yes. Also affects `test/test_parser_examples.py:54` (`test_003_comments`), `test/test_codegen_zig.py:143` and `:176` [003_comments], `test/test_examples_e2e.py:36`, golden `003_comments.out`, and the artifact gate. `test_parser_examples.py:260` and `test_parser_integration.py:282` end in `assert True`, so they do not change. |
| test/test_tokenizer.py:146-148 (`test_003_comments`, :136) | unclosed comment at EOF; asserts the token list | yes |
| test/test_tokenizer_aggressive.py:299 (`test_comment_edge_cases`, :275) | `source4 = "/* unterminated comment"`; asserts tokenize succeeds | yes |
| test/test_parser_creative_cases.py:644 (`test_generic_struct_with_complex_fields`) | 2 swallowed errors (`23:41 Expected type`, `25:8 Expected declaration`). The parsed program is `[STRUCT Handler, STRUCT Buffer, STRUCT Nested, VAR n]`: `main` is dropped, and its inner `n := Nested(string){}` becomes a top-level VAR. The test asserts only `kind == PROGRAM`. | yes |
| test/test_parser_fuzzing.py:219, 290, 314, 352 | random programs, several parsed only after recovery. All four tests catch `ParseError`. Only :352 is seeded (42); the rest vary per run. | no (test outcome unchanged) |
| docs/SPEC.md fragments at 254, 281, 296, 383 | compile to exit 0 only because a parse error is dropped | yes (exit 0 becomes 5) |
| docs/SPEC.md fragments at 190, 435, 669, 809, 841, 911, 1008, 1191, 1209, 1227, 1246, 1290, 1386 | drop a parse error but already fail with exit 6 or 7 | the stage changes (to exit 5); they stay rejected |

Related, for Lane F's removal of the 1000-iteration cap (parser.py:153): two test sources hit the cap and print `Warning: Parser stopped after 1000 iterations`.
- `test/test_parser_error_handling_improvements.py:483` (`"x := 1\n" * 2000`) accepts either success or `ParseError`.
- `test/test_parser_fuzzing.py:486` (1000 `var_i :: i`) asserts exactly 1000 declarations.

Neither outcome depends on the cap, but the warning goes to stdout.

### C6: accepting `ret 0` from `u32` and `usize`

**0 affected programs.**
- Today's behavior was re-probed: `C6a_ret0_u32` and `C6b_ret0_usize` both exit 6 with `Return type mismatch: expected 'u32'|'usize', got 'i32'`.
- No compiled source in tests, examples or docs produces that diagnostic.
- The 5 return-type-mismatch tests (test_semantic_functions.py:242, test_semantic_errors.py:180, test_semantic_control_flow.py:1108, 1120, 1131) all use `ret "hello"` or `ret "bad"` from `i32`. None depends on unsigned `ret 0` being rejected.
- Unsigned-returning code that could be simplified but does not change: examples/034_string_utils.a7:5 and examples/039_text_analyzer.a7:9, 19 (`count: usize = 0 ... ret count`); site/public/docs/language.md:45 (`total: usize = 0 ... ret total`).
- Not covered by C6: S12d (literal argument to a `usize` parameter).

### Part C summary

| change | affected programs | locations |
| --- | --- | --- |
| C1 | 5 | examples/029_sorting.a7:20-23; 030_calculator.a7:62; 032_prime_numbers.a7:11; 041_route_simulation.a7:36,38; 042_gradebook.a7:27,29,31 (plus test_codegen_zig.py:143/:176, test_examples_e2e.py:36, 5 goldens) |
| C2 | 0 | (guard to keep: test_cast_safety_matrix.py:280) |
| C3 | 0 | (keep: test_ast_preprocessor.py:385; doc content: SPEC.md:537) |
| C4 | 0 if C4b covers only referenced numeric, char or float literal globals. 2 tests + 7 SPEC fragments if C4b covers every untyped global, which then needs a packet. | Reading 2: test_codegen_zig.py:482, :1021; SPEC.md:285, 306, 337, 384, 415, 420, 918. C4a, C4c, C4e, C4f: 0. C4d is already rejected (no-op). |
| C5 | 4 sources + 4 SPEC fragments | examples/003_comments.a7:28-29 (and test_parser_examples.py:54, test_codegen_zig.py:143/:176, test_examples_e2e.py:36, golden 003); test_tokenizer.py:146; test_tokenizer_aggressive.py:299; test_parser_creative_cases.py:644; SPEC.md:254, 281, 296, 383 |
| C6 | 0 | none |

## Files

- Probes and runner: `tmp/repro2/gen_probes.py`, `tmp/repro2/run_probes.py`, `tmp/repro2/probes/`, `tmp/repro2/out/`
- Results: `tmp/repro2/results_all.md`, `results_partC_triggers.md`, `results_C4b3.md`, `tokens_mode.out`, `c5_human.out`
- Scan: `tmp/repro2/scan/capture_plugin.py`, `analyze.py`, `corpus.jsonl`, `hits.jsonl`, `hits_readable.txt`, `controls.out`, `c1_toggles.out`, `greps1-6.txt`

---

## Part D: follow-up scan (R3e, R7)

### Method

- The script is `tmp/repro2/scan/analyze_d.py`. It uses the same inputs as Part C: 2105 unique captured test sources, `examples/*.a7`, and the fenced `a7` blocks in SPEC and site docs, for 2216 records in total.
- Each source is compiled with `A7Compiler(mode="pipeline")`. The safety pass is replaced by a wrapper that first runs 7 strict variants on the same typed AST, then runs the real pass.
- A hit is an obligation the real pass proves and the variant does not.
- The variants:
  - `B`: rule (1) only (block facts survive exit, if and match branches joined). Same code as Part C with the loop and call rules off.
  - `R3e`, `R3e+B`
  - `R7drop`, `R7drop+B`
  - `R7int`, `R7int+B`
- **R3e as implemented:**
  - The pass keeps a per-function set of escaped locals: the root identifier of every argument at an index in the call node's `implicit_ref_args` (type_checker.py:1378-1405).
  - After every `CALL`, including stdlib calls such as `io.println`, the fact of every escaped local is reset to an empty `ValueFact()`, which clears interval, nonzero and non-nil.
  - With `B`, escaped names count as changed in any block that contains a call, so the reset survives block exit.
  - Arguments that already have a reference type are not counted as escapes, because they pass a pointer value and the callee cannot rebind the caller's local.
  - Derived places need nothing: the engine keeps facts only per symbol name (`FactMap.by_symbol`) and per expression node, with no field or element place facts.
- **R7 as implemented:** for `+= -= *= /= %= &= |= ^= <<= >>=` on an identifier target, the target's fact after the statement is:
  - `drop`: empty.
  - `interval`: `old.add/sub/mul(rhs)` for `+=`, `-=` and `*=` when both intervals exist, with nonzero recomputed; otherwise empty. `/=`, `%=` and the bitwise operators always drop.
  - The divisor obligation of `/=` and `%=` is unchanged.
- **Gated sources:** the 732 records that exit 6 today were re-run with the backend-feature gate replaced by `[]`. 0 hits in every variant (`scan/analyze_d_gateoff_summary.txt`).

### Detector confirmation (compile-only probes, `scan/d_controls.out`; A7 exits 0 and build-obj exits 0 for all six today, per `results_partD_probes.md`)

| probe | today | B | R3e | R3e+B | R7drop | R7drop+B | R7int | R7int+B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DR7a_sub_to_zero` (`x := 5; x -= 5; y := 10 / x`) | approved | - | - | - | hit L7 | hit L7 | hit L7 | hit L7 |
| `DR7b_add_control` (`x := 5; x += 1; y := 10 / x`) | approved | - | - | - | hit L7 | hit L7 | **stays approved** | **stays approved** |
| `DR3a_current_call` (`zero(x); 10 / x`) | approved | - | hit L11 | hit L11 | - | - | - | - |
| `DR3b_escape_earlier` (`bump(x); x = 5; io.println(..); 10 / x`) | approved | - | hit L13 | hit L13 | - | - | - | - |
| `DR3c_no_escape_control` (`x := 5; io.println(..); 10 / x`) | approved | - | - | - | - | - | - | - |
| `DR3d_escape_in_block` (`{ bump(x) }; 10 / x`) | approved | - | - (the block restores the fact) | hit L13 | - | - | - | - |
| `S1_block_fact` | approved | hit L9 | - | hit L9 | - | hit L9 | - | hit L9 |

### Results

Full corpus summary is in `scan/analyze_d_summary.txt` and the hits in `scan/hits_d_readable.txt`. The one affected file shows up twice, once as an example and once as a test-corpus source, so each count below is distinct programs.

| variant | affected programs | hits |
| --- | --- | --- |
| B (reference) | 0 | none |
| R3e | 0 | none |
| R3e+B | 0 | none |
| R7drop | 1 | examples/026_binary_tree.a7:49 `stack[top]`, :56 `stack[top] = right_index`, :62 `stack[top] = left_index` |
| R7drop+B | 1 | examples/026_binary_tree.a7:49, :56, :62 (same) |
| R7int | 0 | none |
| R7int+B | 1 | examples/026_binary_tree.a7:62 `stack[top] = left_index` |

**Why 026 changes.** The loop is `top: usize = 1; while top > 0 { top -= 1; index := stack[top]; ... if right_index != empty { stack[top] = right_index; top += 1 } ... if left_index != empty { stack[top] = left_index; top += 1 } }`.
- Today: `top -= 1` sets `top`'s fact to the right-hand-side fact, exactly 1. All three indexes are "proven" with `top = 1` while the real value is 0. The result is in bounds by accident.
- R7drop: `top` is unknown after `top -= 1`, so :49, :56 and :62 fail.
- R7int: `[1,1] - [1,1] = [0,0]`, so all three are proven. The `top += 1` inside the first `if` is discarded at block exit (today's rule).
- R7int+B: after the first `if`, the then branch has `top = [1,1]` and the else branch `[0,0]`. The join drops the fact, so :62 fails.
- All of these views assume a single iteration. Under Part C rule (2), `top` is assigned in the loop body, so its fact would be dropped at loop entry anyway. 026 did not appear in Part C only because rule (2) keeps today's compound-assignment behavior, which sets the fact to the right-hand side.

**Tests and goldens that would change (R7drop, R7drop+B, R7int+B):**
- `test/test_codegen_zig.py:143` `test_example_compiles[026_binary_tree]` and `:176` `test_ast_check[026_binary_tree]`.
- `test/test_examples_e2e.py:36`.
- The artifact gate `scripts/build_examples.py`, Debug and release.
- Golden `test/fixtures/golden_outputs/026_binary_tree.out` becomes unreachable; its content does not change.
- `test_release_tooling.py::test_installed_cli_entrypoint_works` appears as a corpus user only through the sibling glob. It tokenizes `001_hello` and does not change.

**R3e: 0 affected.** Examples that pass locals by implicit reference (for example `013_pointers.a7` `increment(x)` and `041_route_simulation.a7` `move_by(position, ...)`) never use those locals afterwards in a division, index, slice, cast or non-nil obligation that depends on a fact.

---

## Part E: hull-join rule (1), combinations, and wider docs coverage

### Method

- The script is `tmp/repro2/scan/analyze_e.py`. It uses the same pipeline and diff as Parts C and D: a hit is an obligation the real pass proves and the variant does not.
- One wrapper runs the Part D variants, the Part E variants, and the Part C wrapper (strict rules 1-3, the real pass, and the C2-C6 detectors) on each program.
- Modes:
  - `corpus`: the 2216 Part C records.
  - `corpus-gateoff`: the 732 records that exit 6 today, re-run with the backend feature gate replaced by `[]`.
  - `docs`: new documentation blocks.
- All runs had 0 variant exceptions. Summaries are in `scan/hits_e_summary.txt`, `hits_e_gateoff_summary.txt` and `hits_e_docs_summary.txt`; readable hits in `scan/hits_e_readable.txt`.
- The Part C and D counts reproduced in this run match Parts C and D.

**Hull-join rule (1), class `JoinSafety`:**
- **Plain block exit:** every name that existed before the block takes its post-block fact. Names declared directly in the block get their pre-block fact back, since those declarations shadow the outer name.
- **if/else:** the join of the then-path state (starting from the pre-state plus today's positive condition facts) and the else-path state (the pre-state, or the else branch). A branch that ends in `ret`, `break` or `continue` is left out of the fall-through join. Today's `_learn_after_stmt` refinement still runs afterwards.
- **match:** the join of every case path. When there is no `else`, the pre-state is added as one more path.
- **Join:**
  - Interval: hull of the incoming intervals. A bound is unbounded if it is unbounded on any path, and the interval is none if any path has none.
  - `nonzero`, `non_nil`, `initialized`: true only if true on every path, where nonzero also counts an interval that excludes 0.
  - `maybe_nil`, `moved`: true if true on any path.
  - `known_length`, `enum_discriminant`: kept only if equal on all paths.
- A name assigned on only some paths joins its pre-branch fact with the assigned fact, because the untouched path carries the pre-state.

**R7 interval and R3e** are the Part D definitions.

**Loop rules:**
- **today** (E1-E3): the current pass. It visits the body once with today's condition facts, then restores the pre-loop facts.
- **drop** (E4): Part C rule (2) on top of the join. Names assigned in the body or update, by-reference call roots, and (with R3e) escaped names are dropped at loop entry and after the loop.
- **fixpoint** (E5):
  - Header state starts as the entry state (after the `for` init).
  - Each iteration visits the condition and applies loop-condition facts, then the body, then the `for` update. The back-edge state is the join of the fall-through body state and every `continue` state, with the update applied to that join.
  - New header = join(header, back edge). From the 3rd header visit on, any bound that grew is widened to unbounded. `nonzero` and `non_nil` are joined booleans.
  - Iteration runs until the header stops changing, capped at 40 visits, after which every fact is dropped. Obligations, errors and `moved_symbols` from iterations are discarded; one recording pass then runs from the fixed header.
  - Loop exit state = join(header, every `break` state), restricted to names that existed before the loop.
  - Loop-condition facts are today's facts plus bounds from the condition's right-hand side interval: `<` gives upper `hi - 1`, `<=` gives `hi`, `>` gives `lo + 1`, `>=` gives `lo`, each intersected with the current interval. That covers `i < N`, `i < limit` when `limit` has an interval, and `i < xs.len` with a known length. Both sides of an `and` are used.
  - Types do not bound the widening; an unsigned variable can widen its lower bound to unbounded.

### Detector confirmation (compile-only probes)

A7 exits 0 and build-obj exits 0 for all nine new probes (`results_partE_probes.md`); the hit lines per variant are in `scan/e_controls.out`.

| probe | shape | E1 | E2 | E3 | E4 | E5 |
| --- | --- | --- | --- | --- | --- | --- |
| `E1_block_zero` | `x := 5; { x = 0 }; 10 / x` | hit L9 | hit | hit | hit | hit |
| `E2_if_top_stays` | `stack: [3]i32; top: usize = 1; if c { top -= 1 }; stack[top]` | **approved** | **approved** | **approved** | **approved** | **approved** |
| `E3_if_assign_zero` | `x := 5; if c { x = 0 }; 10 / x` | hit L10 | hit | hit | hit | hit |
| `E4_if_both_nonzero` | `if c { x = 2 } else { x = 3 }; 10 / x` | approved | approved | approved | approved | approved |
| `DR7a_sub_to_zero` | `x := 5; x -= 5; 10 / x` | approved | hit L7 | hit | hit | hit |
| `DR7b_add_control` | `x := 5; x += 1; 10 / x` | approved | approved | approved | approved | approved |
| `DR3b_escape_earlier` | `bump(x); x = 5; io.println(..); 10 / x` | approved | approved | hit L13 | hit | hit |
| `DR3c_no_escape_control` | no escape | approved | approved | approved | approved | approved |
| `E5_loop_bounded` | `for i := cast(usize, 0); i < 5; i += 1 { arr[i] }`, `[5]i32` | approved | approved | approved | hit L7 | **approved** |
| `E6_loop_overrun` | `i: usize = 0; while i < 10 { arr[i]; i += 1 }`, `[5]i32` | approved (unsound; approved today too) | approved | approved | hit L8 | **hit L8** |
| `E7_continue_zero` | `while i < 3 { 10 / x; if c { x = 0; i += 1; continue }; i += 1 }` | approved | approved | approved | hit L9 | **hit L9** (the continue state reaches the header) |
| `E8_break_zero` | `while i < 3 { if c { x = 0; break }; i += 1 }; 10 / x` | approved | approved | approved | hit L15 | **hit L15** (the break state reaches the exit) |
| `E9_limit_nested` | 029 shape: `limit: usize = cast(usize, 4) - i; for j ...; j < limit; ... arr[j], arr[j + 1]` | approved | approved | approved | hit L9 x2 | **approved** |

In E2, `top` after the `if` is `[1,1]` under E1, because today `top -= 1` sets the fact to the right-hand side. Under E2-E5 it is `[0,1]`, the hull of `[0,0]` and `[1,1]`. Both stay in bounds.

### Results on the Part C corpus (examples, tests, SPEC and site docs blocks)

The 732 gated records show 0 E hits. Each example also appears once as a test-corpus source; counts below are distinct programs.

| variant | affected programs | hits |
| --- | --- | --- |
| E1 hull-join (1) | **0** | none |
| E2 E1 + R7 interval | **0** | none |
| E3 E2 + R3e | **0** | none |
| E4 E3 + loop rule (2) | **6** | examples/026_binary_tree.a7:49, 56, 62; 029_sorting.a7:20 (x2), 21, 22 (x2), 23; 030_calculator.a7:62; 032_prime_numbers.a7:11; 041_route_simulation.a7:36 (x2), 38 (x2); 042_gradebook.a7:27, 29, 31 |
| E5 E3 + fixpoint/widening loop rule | **2** | examples/026_binary_tree.a7:49, 56, 62; examples/030_calculator.a7:62 |

Why each hit changes:
- **026 (E4):** `top` is assigned in the body, so it is dropped at loop entry. `top > 0` gives `[1, unbounded]`, and R7 turns `top -= 1` into `[0, unbounded]`, so `stack[top]` fails at 49, 56 and 62. Part C's rule (2) missed this because, without R7, `top -= 1` set the fact to exactly 1.
- **026 (E5):** with the right-hand side exactly 1, `top -= 1` and `top += 1` grow the header interval from `[1,1]` to `[0,2]` and then `[0,3]`. After 3 header visits the upper bound widens to unbounded. `stack[top]` against `[3]usize` fails at 49, 56 and 62. The bound actually depends on the tree shape (at most 2 pushes per pop, 3 nodes), which interval analysis cannot see.
- **029, 032, 041, 042 (E4 only):** the same sites and reasons as Part C C1. Under E5 they are approved:
  - 029: `i` is in `[0,4]` from `i < 5`, so `limit = 4 - i` is in `[0,4]`, `j < limit` gives `j <= 3`, and `j + 1 <= 4`.
  - 032: `d` is `[2, unbounded]`, which is non-zero.
  - 041 and 042: `i < 6` and `i < 3`.
- **030 (E4 and E5):** `guess` is non-zero on entry (`x / 2.0`, with `x != 0` from the early return), but the back edge assigns `guess = next_guess`, where `next_guess := (guess + x / guess) / 2.0` carries no non-zero fact because an addition drops it. The join clears `nonzero`, so `x / guess` fails. The rule is right: floating-point division by a value that could underflow to 0 is unproven.

**Tests and goldens that would change:**
- **E4:** `test/test_codegen_zig.py:143` `test_example_compiles` and `:176` `test_ast_check` for `026_binary_tree`, `029_sorting`, `030_calculator`, `032_prime_numbers`, `041_route_simulation` and `042_gradebook`; `test/test_examples_e2e.py:36`; the artifact gate; and those 6 goldens in `test/fixtures/golden_outputs/` (content unchanged, no longer reached).
- **E5:** the same tests for `026_binary_tree` and `030_calculator`, plus goldens `026_binary_tree.out` and `030_calculator.out`.
- **E1-E3:** none.

### Wider docs coverage: `site/public/llms-full.txt` and `docs/lang-safety/**/*.md`

- 224 blocks: 6 `a7` blocks from `llms-full.txt`, 216 `a7` blocks from 40 `lang-safety` files, and 2 untagged blocks that contain `::` or `:=`.
- Today's exits:
  - `llms-full.txt`: 5 exit 0, 1 exit 5.
  - `lang-safety` `a7` blocks: 49 exit 0, 36 exit 4, 78 exit 5, 53 exit 6.
  - The 2 untagged blocks exit 4; they are not A7.
- Every rule from Parts C, D and E was run on them (`scan/hits_e_docs.jsonl`, `hits_e_docs_summary.txt`).
- "Parses" below means the block tokenizes and parses as a whole file without silently dropped declarations. Line numbers are file lines.

| rule | extra doc hits | file:line, parses today?, effect |
| --- | --- | --- |
| C1 (Part C rules 1-3) | 1 | docs/lang-safety/edge-cases/03-definite-assignment.md:206 `filled[i] = 7` (block at :193, "Current A7", parses, exit 0). Loop rule (2): `i` is assigned in the `for` update. Becomes exit 6. |
| C2, C3 | 0 | none |
| C4 | 2 | C4f: 03-definite-assignment.md:233 `z := z` (block at :211, "Current A7" DA-20, parses, exit 0), becomes rejected. C4e: 05-stack-budget.md:111 `dynamic: [n]u8` with `n` a parameter (block at :98, parses, exit 0; the block's own comment says Zig would fail), becomes rejected. |
| C4b (untyped globals) | 0 | none |
| C5 | 6 | Two blocks parse only by dropping declarations and would go from exit 0 to 5: 08-decisions.md:1746 `fill(buf)` at file scope (block at :1744, D.042 illustration, not a full program); 03-definite-assignment.md:238 (block at :237, "Proposed", file-scope `add := fn() {...}` and `match`). Four blocks already exit 6 and would change stage to exit 5: 08-decisions.md:318, :1191, :1638; conversions.md:166. |
| C6 | 4 blocks (5 sites) | All exit 6 today with `Return type mismatch` as the only reported error; later passes have not run, so acceptance after C6 is not certain. 04-nonzero-division.md:122, :129 (block at :113; its comment says "Rejected (exit 6) ... ret 0"); 06-typed-arithmetic.md:139 (block at :124, same kind of comment); 06-typed-arithmetic.md:189 (block at :182, same); narrowing.md:692 (block at :689, "Proposed", uses `not (i < n)`). The first three blocks' comments would become stale. |
| R3e, R3e+B | 0 | none |
| R7drop, R7drop+B, R7int, R7int+B | 0 | none |
| E1, E2, E3 | 0 | none |
| E4 | 1 | 03-definite-assignment.md:206 `filled[i] = 7` (same site as C1) |
| E5 | 0 | none (`i < 8` against `[8]u8` is proven) |

- `site/public/llms-full.txt` has 0 hits under every rule.
