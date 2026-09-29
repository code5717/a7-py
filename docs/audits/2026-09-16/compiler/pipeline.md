> **Source:** Claude audit subagent, full audit of the A7 compiler component `pipeline`, run against commit `701c679` with Zig 0.16.0; shared instructions in `tmp/audit/compiler/PROMPT-COMMON.md`.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim. Probes and logs it cites stay under `tmp/audit/compiler/pipeline/`, which is not tracked.

# Compiler audit: pipeline, modules, name resolution, CLI, formatters (PIP)

Auditor scope: `a7/compile.py`, `a7/module_resolver.py`, `a7/passes/name_resolution.py`,
`a7/symbol_table.py`, `a7/semantic_context.py`, `a7/cli.py`, `a7/formatters/*`,
`a7/stdlib/*`, `a7/errors.py` (non-lexical), `main.py`, and the related tests. Every
file in scope was read in full. Commit under test: working tree on `master` at
`701c679` plus the uncommitted files listed in git status. Zig 0.16.0.

Probes: `tmp/audit/compiler/pipeline/probes/` (first line `// probe: compile-only` or
`// probe: run-allowed`). Driver: `tmp/audit/compiler/pipeline/run.sh <probe>` runs
`uv run a7 <probe> --format json --output out/<probe>.json.zig`, the same in human
format to `out/<probe>.zig`, then `zig build-obj -fno-emit-bin` on the human output.
Per-probe records: `out/<probe>.summary` (exit codes, JSON error details, human
stdout/stderr, build-obj result). CLI probes and logs: `cli/log.txt`,
`cli/schema.txt`. Only run-allowed probes were built with `zig build-exe` (Debug and
ReleaseFast) and run: `f03`, `f08`, `s01`, `s02b` (logs `runs.txt`, `runs2.txt`).

## Summary

| Severity | Total | NEW | KNOWN |
| --- | --- | --- | --- |
| CRITICAL | 3 | 3 | 0 |
| HIGH | 9 | 7 | 2 |
| MEDIUM | 11 | 9 | 2 |
| LOW | 12 | 12 | 0 |
| Total | 35 | 31 | 4 |

The three CRITICAL findings are silent miscompiles confirmed on real binaries. All
three come from name-based recognition that ignores lexical scope.

| ID | Sev | Status | One line |
| --- | --- | --- | --- |
| PIP-1 | CRITICAL | NEW | A local that shadows a file-module alias has its method call rewritten to the module function |
| PIP-2 | CRITICAL | NEW | A user function named `sqrt_f64` (or any of the other 21 registered typed math names) is replaced by a Zig builtin |
| PIP-3 | CRITICAL | NEW (B14 family) | A struct value named `io` has its `println` field call rewritten to stdout printing |
| PIP-4 | HIGH | NEW | `else if` desynchronizes name-resolution and type-checker scopes: valid programs rejected, invalid accepted |
| PIP-5 | HIGH | NEW | Match expressions steal later match-statement scopes, same mechanism |
| PIP-6 | HIGH | NEW | A function in an imported module that calls a sibling function emits Zig that does not build |
| PIP-7 | HIGH | NEW | Module merge is a flat concatenation: no visibility, names leak, valid programs rejected |
| PIP-8 | HIGH | NEW | Transitive imports are loaded but never merged; aliases inside modules never resolve |
| PIP-9 | HIGH | NEW | Calls through a file-module alias skip all type checking |
| PIP-10 | HIGH | NEW | Import cycle detection is dead code; import depth is unbounded and recursive |
| PIP-11 | HIGH | KNOWN B16 #6-#8 | Imported-module errors: internal exit 8, no span, wrong file and wrong source excerpt |
| PIP-12 | HIGH | KNOWN B16 #1-#4 | Output and doc destinations overwrite sources and stale files are advertised; imported modules also destroyable |
| PIP-13 | MEDIUM | NEW | Rich markup in a string literal or path crashes human output with exit 8 |
| PIP-14 | MEDIUM | NEW | Recursion over imports (and in the type checker) turns deep inputs into internal errors |
| PIP-15 | MEDIUM | NEW (T2a root cause) | Use of a block local before its declaration is accepted |
| PIP-16 | MEDIUM | KNOWN F5 | JSON crash on any match expression with `else`, also on the failure path; handler not exception-safe |
| PIP-17 | MEDIUM | NEW | `--mode semantic` rejects local-module calls that `--mode compile` accepts |
| PIP-18 | MEDIUM | NEW | Duplicate import aliases, alias/function clashes and duplicate enum variants are silently accepted |
| PIP-19 | MEDIUM | NEW | Default output path replaces every `.a7` substring in the path and creates a new directory |
| PIP-20 | MEDIUM | NEW | Named (`import "m" { f }`) and bare (`import "m"`) file imports exit 0 and emit broken Zig |
| PIP-21 | MEDIUM | KNOWN audit A-32 | Match capture named like any visible symbol (including globals and functions) compares instead of capturing |
| PIP-22 | MEDIUM | NEW | `--output` equal to `--doc-out`: doc silently replaces the Zig file, both advertised |
| PIP-23 | MEDIUM | NEW | SPEC 11.2 bare typed math builtins do not exist for users; they only hijack (see PIP-2) |
| PIP-24 | LOW | NEW | Human diagnostics go to stdout; stderr is empty on failure |
| PIP-25 | LOW | NEW | JSON schema inconsistencies across stages |
| PIP-26 | LOW | NEW | `--backend` is not validated as a usage error |
| PIP-27 | LOW | NEW | Doc write failure leaves a fresh output file advertised under status error; writes are not atomic |
| PIP-28 | LOW | NEW (F1 sibling) | An empty `.a7` file compiles to a 0-byte `.zig` with exit 0 |
| PIP-29 | LOW | NEW | Undefined identifiers are reported as "Undefined type" by the type checker; name resolution resolves no uses; duplicate diagnostics |
| PIP-30 | LOW | NEW | Nested function declarations are never registered |
| PIP-31 | LOW | NEW | A local named like a generic parameter is accepted; Zig rejects |
| PIP-32 | LOW | NEW | Local files named `io.a7`/`math.a7` cannot be imported; misleading diagnostic |
| PIP-33 | LOW | NEW | Scope matching in the type checker is superlinear |
| PIP-34 | LOW | NEW | Formatter defects (markdown symbol labels, lossy trees, wrapped paths) |
| PIP-35 | LOW | NEW | Dead code, duplicated logic and structural blockers for typed IR |

## Root causes of the 12 known failing tests

Reproduced: `tmp/audit/compiler/pipeline/pytest_pipeline.log`, `12 failed, 4 passed`.
Components other than PIP are named; their auditors own the fix.

| # | Test | Root cause in code | Component |
| --- | --- | --- | --- |
| 1 | `test_cli_rejects_input_destination_without_changing_source[--output]` | `compile.py:151` accepts any `output_path`; `compile.py:441-442` `open(result.output_path, "w")` never compares it with `input_path` (or with loaded module files, see PIP-12) | PIP |
| 2 | `...[--doc-out]` | `cli.py:85` passes `--doc-out` through; `compile.py:471` `open(doc_output, "w")` with no comparison | PIP |
| 3 | `test_failed_compile_does_not_advertise_stale_output` | `compile.py:151` sets `result.output_path` before any stage runs; `compile.py:779` `if result.output_path and Path(result.output_path).exists()` advertises whatever is already on disk | PIP |
| 4 | `test_output_write_failure_does_not_advertise_directory_as_artifact` | Same line 779: `Path(dir).exists()` is true for a directory; the `IsADirectoryError` from line 441 is reported as IO but the artifact check does not know the write failed | PIP |
| 5 | `test_cli_source_diagnostic_points_to_offending_token[parse]` | Parser reports `self.current()` correctly (`parser.py:1714-1716`); the tokenizer gives `)` column 9 instead of 10 and `:=` column 5 (same as `x`) and `::` column 4 on `main :: fn()` (`cli/tok_cols.txt`) | TOK |
| 6 | `test_missing_import_diagnostic_locates_import_declaration` | `module_resolver.py:140-142` raises `SemanticError(f"Module ... not found ...")` with no span; `:257-259` re-wraps it again with no span; the IMPORT node and its span are available in `process_imports` (`:215-218`) but not threaded | PIP |
| 7 | `test_imported_parse_error_is_a_source_failure_with_module_location` | `compile.py:246-250` catches only `SemanticError`; `ParseError` from `module_resolver.py:160` (also `TokenizerError` from `:157` and `UnicodeDecodeError` from `:149`) reaches `except Exception` at `compile.py:491` and becomes `ExitCode.INTERNAL` | PIP |
| 8 | `test_imported_semantic_error_preserves_origin_file` | `compile.py:256` merges module declarations into the main AST; `compile.py:270-271` and `:315-316` analyze it with `str(input_path)` and main's `source_lines`; `_error_to_detail` (`compile.py:795-799`) hard-codes `"file": file_path` = input path and ignores `err.filename` | PIP |
| 9 | `test_valid_a7_bindings_build_with_zig[zig-keyword-local]` | `zig.py:1512-1515` escapes a fixed reserved set only in `_emit_identifier`; `_visit_var_decl` writes `emit_name` raw (`zig.py:679-684`), giving `const error = 1;` | BACKEND |
| 10 | `...[unused-loop-capture]` | `_visit_for_in` (`zig.py:920-940`) emits `for (a) \|x\|` with no `_ = x;` discard; only var declarations get discards (`zig.py:693-697`) | BACKEND |
| 11 | `...[shadowed-loop-capture]` | `_resolve_shadowing` renames only `NodeKind.VAR` (`ast_preprocessor.py:480-484`); for-in iterators are never declared or renamed, and `zig.py:924` emits `node.iterator` raw | PREPROCESSOR/BACKEND |
| 12 | `test_large_integer_folding_preserves_exact_quotient_and_remainder` | `ast_preprocessor.py:621` `int(lval / rval)` and `:624` use float true division, so `9007199254740993 / 1` folds to `9007199254740992` and `% 1` to `1` | PREPROCESSOR |

## Findings

### PIP-1. CRITICAL. NEW. A local that shadows a file-module alias is miscompiled

What is wrong: `_annotate_file_module_calls` runs on the raw AST before name resolution
and marks every `X.f(...)` call whose object text equals an import alias. A local
variable with the same name as the alias therefore has its field call replaced by the
module function.

Evidence:
- `compile.py:586-592`:
  `if obj and obj.kind == NodeKind.IDENTIFIER and obj.name in aliases: value.file_module_call = (...)`.
  Called at `compile.py:254-255` with no scope information.
- `zig.py:1625-1629` then emits `f"{prefix}{field}({args})"` before any other check, and
  `type_checker.py:1318-1321` skips checking such calls.
- Probe `probes/f03_alias_shadow_local_run.a7` (run-allowed; helper `probes/flat.a7`):
  `h :: import "flat"`; in `main`, `h := Ops{work: two}`, `g := h.work`,
  `io.println("{} {}", h.work(), g())`.
  A7 exit 0 (JSON and human). Emitted (`out/f03_alias_shadow_local_run.zig:41-43`):
  `const h = Ops{ .work = two }; const g = h.work; __a7_stdout_print("{} {}\n", .{ module_flat__work(), g() });`.
  `zig build-exe` Debug and ReleaseFast both exit 0; both runs print **`1 2`**. Correct
  output is `2 2`.
- Without `g`, Zig rejects the unused `h` (`probes/m22b_alias_shadow_local.a7`), which
  hides the miscompile only by accident.

Fix direction: annotate module calls after name resolution by looking up the object name
in the scope of the call and requiring a `SymbolKind.MODULE` symbol. Would the fix change
a program A7 accepts and Zig builds today: yes (f03 changes output from `1 2` to `2 2`).

### PIP-2. CRITICAL. NEW. User functions named like typed math builtins are replaced

What is wrong: The stdlib registry registers `<name>_f32` and `<name>_f64` for 11 math
functions (22 names). The preprocessor tags any call whose callee identifier has one of
these names, without checking whether the name is a user declaration, and the backend
emits the Zig builtin.

Evidence:
- `stdlib/math.py:34-41` registers `sqrt_f32`, `sqrt_f64`, ..., `max_f64`.
- `ast_preprocessor.py:216-220`: `elif func.kind == NodeKind.IDENTIFIER and func.name: canonical = self.stdlib.resolve_builtin(func.name); if canonical: node.stdlib_canonical = canonical`.
- `zig.py:1631-1637` emits `@{short}(args)` for any `std.math.*` canonical; `zig.py:1612-1617, 1642-1643` also map the text `sqrt_f32` etc. independently.
- Probe `probes/s01_user_sqrt_f64.a7` (run-allowed): `sqrt_f64 :: fn(x: f64) f64 { ret x + 1.0 }` and `io.println("{}", sqrt_f64(9.0))`.
  A7 exit 0. Emitted `fn sqrt_f64(x: f64) f64 {...}` and `__a7_stdout_print("{}\n", .{@sqrt(9.0)});` (`out/s01_user_sqrt_f64.zig:14,19`). Debug and ReleaseFast both build and print **`3`**; correct is `10`.
- SPEC A.3 (`docs/SPEC.md:2077-2081`) puts "Built-in names" last, after current and file scope, so a file-scope function must win.

Fix direction: resolve bare builtins only when no user symbol of that name is visible, or
remove the bare-builtin path (see PIP-23; removal changes documented surface and needs
approval). Changes an accepted, Zig-built program: yes (s01 output changes).

### PIP-3. CRITICAL. NEW (same family as KNOWN B14). A struct value named `io` is miscompiled

What is wrong: A call `io.println(...)` is treated as the stdlib print whenever the
object is spelled `io`, even when `io` is a local struct value with a function-pointer
field and no `std/io` import exists.

Evidence:
- `ast_preprocessor.py:209`: `module_name = self._resolve_module_import_path(obj.name) or obj.name` falls back to the raw identifier text when the name is not a module.
- `zig.py:2163-2167` and `zig.py:144-149` also match `getattr(obj, 'name', '') == 'io'` textually.
- Probe `probes/s02b_struct_named_io_run.a7` (run-allowed): `say :: fn(s: string) {}`, `Printer :: struct { println: fn(string) }`, `io := Printer{println: say}`, `g := io.println`, `g("quiet")`, `io.println("hijacked")`.
  A7 exit 0; emitted `__a7_stdout_print("hijacked\n", .{});` (`out/s02b_struct_named_io_run.zig:24`). Debug and ReleaseFast build and print **`hijacked`**; correct output is empty.
- B14 in the Wave 0 ledger covers only the `math.` text prefix (`zig.py:1645`). The `io`
  path and the preprocessor fallback at `:209` are separate triggers.

Fix direction: recognize stdlib calls only through a `MODULE` symbol whose import path is
virtual; delete the textual `io`/`math.` checks. Changes an accepted, Zig-built program: yes.

### PIP-4. HIGH. NEW. `else if` desynchronizes scopes between name resolution and type checking

What is wrong: Name resolution wraps a non-block `else` branch (an `else if`) in its own
`if_else` scope, so the inner `if`'s block scopes become children of `if_else`. The type
checker visits the same `else` branch without entering `if_else`, so its positional
`_enter_matching_scope("block")` takes the next unused `block` child of the enclosing
scope, which belongs to a later sibling block. Symbols then resolve to the wrong
declarations.

Evidence:
- `name_resolution.py:430-436`: non-BLOCK `else_stmt` pushes `enter_scope("if_else")`.
- `type_checker.py:901-902`: `if node.else_stmt: self.visit_statement(node.else_stmt)` (no scope).
- `type_checker.py:142-157`: `matches = [child for child in parent.children if child.name == name]`, position counter keyed by `(id(parent), name)`, fallback creates a new empty scope.
- `type_checker.py:654-656`: const declarations only look up and never define, so in a fallback scope the constant is missing.
- Probe `probes/n21_elseif_then_if_const.a7` (valid program): `if k == 0 {...} else if k == 1 {...}` followed by `if k > 0 { c :: 3; io.println("{}", c) }`. Exit 6/6: `12:26: Undefined type (Identifier 'c')`. False rejection of a common shape.
- Probe `probes/n02_elseif_false_reject.a7`: `y := 1; y = 5` inside the `else if` block and `y :: 2` in a later block. Exit 6: `9:9 Cannot assign to immutable binding: 'y' is immutable` and `14:26 Undefined type (Identifier 'y')`. Both false.
- Probe `probes/n03_elseif_wrong_accept.a7`: `y :: 1; y = 5` inside the `else if` block and `y := 2` in a later block. Exit 0/0; `build-obj`: `20:9: error: cannot assign to constant`. Control `probes/n03c_elseif_control.a7` (plain `else`) correctly exits 6.
- `probes/n14_while_nonblock_elseif_match.a7`: `z :: 10; z = 11` in the third arm: reported as `Undefined type (Identifier 'z')` instead of the immutability error.
- `examples/006_if.a7` and `examples/031_number_guessing.a7` use `else if` and compile, so the trigger needs a later sibling block with declarations (INFERENCE).

Fix direction: key scopes by AST node identity (store the scope on the node in name
resolution, or build scopes once and reuse them), not by name and position. Changes an
accepted, Zig-built program: unknown. The confirmed wrong acceptances are rejected by Zig;
whether a mis-typed symbol ever reaches a built binary was not shown (UNVERIFIED).

### PIP-5. HIGH. NEW. Match expressions consume match-statement scopes

What is wrong: Name resolution creates `match_case` scopes only for match statements. The
type checker enters `match_case` for match expressions too, so an expression takes the
scope that belongs to a later statement's case, and that statement falls back to an empty
scope.

Evidence:
- `name_resolution.py:496-514` handles only `NodeKind.MATCH` statements; expressions are never visited.
- `type_checker.py:2025-2032`: `self._enter_matching_scope("match_case")` for every expression case.
- Probe `probes/n23_matchexpr_steals_stmt_scope.a7` (valid): `r := match k { case 1: 10 else: 20 }` then `match k { case 1: { c :: 7; io.println("{} {}", c, r) } else: {} }`. Human exit 6: `Undefined type (Identifier 'c') [line 12: col 33]`. JSON mode crashes (PIP-16).
- Probe `probes/n10_match_expr_then_stmt.a7` (captures, no constants) compiles and builds, so the trigger is a constant declaration in the stolen case (INFERENCE from the const-lookup rule above).

Fix direction: same as PIP-4. Changes an accepted, Zig-built program: unknown.

### PIP-6. HIGH. NEW. Intra-module calls in imported files emit undefined names

What is wrong: The merge sets `module_emit_prefix` on each imported function declaration,
but calls inside the module body keep their bare names. Any imported module where one
function calls another produces Zig that fails to build.

Evidence:
- `compile.py:616-617`: `if decl.kind == NodeKind.FUNCTION: decl.module_emit_prefix = prefix` (declarations only).
- `zig.py:401-402` emits `f"{emit_prefix}{name}"` for the declaration; call sites go through `_emit_identifier` unchanged.
- Probe `probes/m02_internal_call.a7` with `probes/modhelper.a7` (`pub outer :: fn() i32 { ret inner() }`): A7 exit 0; `build-obj`: `m02_internal_call.zig:23:12: error: use of undeclared identifier 'inner'` at `return inner();`.
- Every probe that imports `modhelper.a7` shows this error, whether or not `outer` is called (`out/m01_*.summary` through `out/m33_*.summary`).
- SPEC 10.3 (`docs/SPEC.md:1515-1517`): "Local file imports ... simple alias-qualified function calls lower into the same generated Zig output file." Existing tests (`test_cli_failures.py:150-178`, `test_pipeline_artifacts.py:64-82`) use single-function modules only.

Fix direction: rename call sites inside module bodies (after resolution) or lower each
module to a Zig namespace struct. Changes an accepted, Zig-built program: no.

### PIP-7. HIGH. NEW. Module merge by concatenation: no visibility, leaked names, false rejections

What is wrong: All non-import declarations of each directly imported file are prepended
to the importer's declaration list and analyzed in one global scope. Only functions get a
prefix. Consequences, each confirmed:

1. Non-`pub` declarations are callable through the alias. SPEC 10.4 (`docs/SPEC.md:1531-1532`): "`pub` items are exported from the file/module" and "Non-`pub` items are file-private". Probe `probes/f01_private_access.a7` calls `h.hidden()` on a non-pub function: exit 0, `build-obj` 0.
2. Imported structs and constants are visible unqualified. `probes/f02_unqualified_leak.a7`: `p := Point{x: LIMIT}` with only `h :: import "flat"`: exit 0, `build-obj` 0 (struct and const are emitted unprefixed, `out/m08_type_position.zig:17-26`).
3. Valid programs are rejected when the importer reuses a module's name, including private helper names. `probes/m07_fn_dup.a7` (main defines `work`, module defines `pub work`): exit 6 `Already defined: Function 'work'`. `probes/m06_struct_dup.a7` (struct `Point` in both): exit 6. `probes/m21_module_main.a7` (module defines `main`): exit 6 `Already defined: Function 'main'`.
4. Two modules cannot share a function name. `probes/m12_prefix_collision.a7` (`a_b.a7` and `a/b.a7` both define `f`): exit 6 `Already defined: Function 'f'`. The distinct prefix collision `a_b` versus `a/b` -> `module_a_b__` (`compile.py:570-572`) is therefore never reached (INFERENCE; not independently observed).
5. The same file under two spellings is merged twice. `probes/m11_dot_slash_dup.a7` (`import "./modhelper"` and `import "modhelper"`): exit 6 with 7 `Already defined` errors; `seen_paths` (`compile.py:605-611`) is keyed by the import string, not the resolved file.
6. A file importing itself (`probes/m09_self_import.a7`): exit 6 `Already defined: Function 'main'` pointing at main, with no import diagnostic.

Evidence: `compile.py:597-627` (merge), `compile.py:612-618`.

Fix direction: give each module its own symbol table and namespace; resolve `alias.name`
against exported symbols only; key modules by resolved file path. Changes an accepted,
Zig-built program: yes (f01 and f02 build today and would be rejected; needs owner
approval, gate G6 names visibility enforcement).

### PIP-8. HIGH. NEW. Transitive imports are never merged

What is wrong: `load_module` loads dependencies recursively, but
`load_program_dependencies` returns only the importer's direct imports, the merge drops
IMPORT declarations from modules, and alias annotation runs only on the main file. A
module that uses its own import cannot work.

Evidence:
- `module_resolver.py:249-254` appends only `self.load_module(module_path)` results for the main file's imports.
- `compile.py:614-615` skips `NodeKind.IMPORT` inside modules; `compile.py:254-255` annotates only the main AST.
- Probe `probes/m13_nested_alias.a7` (`nest1.a7` does `n2 :: import "nest2"` and `ret n2.g()`): exit 6, three errors `Undefined type (Identifier 'n2')` reported in `m13_nested_alias.a7` at 4:9, which is the module's line, not main's.

Fix direction: merge the full loaded closure in dependency order with per-module alias
tables. Changes an accepted, Zig-built program: no.

### PIP-9. HIGH. NEW. Calls through a file-module alias are not type checked

What is wrong: When a call carries `file_module_call`, the type checker visits the
arguments and returns `UNKNOWN`. Member existence, arity, argument types and return type
are never checked; module values in other positions also type as `UNKNOWN`.

Evidence:
- `type_checker.py:1317-1321`: `if getattr(node, "file_module_call", None): for arg in ...: self.visit_expression(arg); return UNKNOWN`.
- `type_checker.py:1742-1755`: field access on a MODULE returns `UNKNOWN` and only virtual modules are checked.
- All exit 0 in A7 and fail `build-obj`:
  - `probes/m04_missing_member.a7` `h.nope()`: `use of undeclared identifier 'module_modhelper__nope'`.
  - `probes/m05_arg_mismatch.a7` `h.takes("str", 2)`: `expected 1 argument(s), found 2`.
  - `probes/f05_arg_type_mismatch.a7` `h.takes("str")`: `expected type 'i32', found '*const [3:0]u8'`.
  - `probes/m19_module_return_type.a7` `s: string = h.work()`: `expected type '[]const u8', found 'i32'`.
  - `probes/f06_module_value_use.a7` `x := h` and `h.LIMIT`: `use of undeclared identifier 'h'`.

Fix direction: resolve the alias to the module's exported symbol and check the call like
any other. Changes an accepted, Zig-built program: no.

### PIP-10. HIGH. NEW. Cycle detection is dead code; import depth unbounded and recursive

What is wrong: A module is inserted into `loaded_modules` before its dependencies are
loaded, and the cache check precedes the `loading_stack` check, so a cycle returns the
half-loaded module instead of raising. Loading recurses once per import level with no
limit.

Evidence:
- `module_resolver.py:124-125` (cache hit returns), `:131-135` (cycle check, unreachable for a revisited module), `:187` (cache insert), `:190-191` (recursive `self.load_module(dep_path)`).
- Probe `probes/m10_cycle.a7` (`cyc_a` imports `cyc_b`, `cyc_b` imports `cyc_a`): exit 0/0, `build-obj` 0; `cyc_b` is never emitted (PIP-8).
- `topological_sort` (`module_resolver.py:310-350`) would detect cycles but is never called.
- Chain of 1100 modules (`chain/`): exit 8 `maximum recursion depth exceeded`, `exception_type: RecursionError` (`chain/res.txt`); a direct call shows 984 nested `load_module` frames (`confirm.txt`).
- SPEC Appendix C (`docs/SPEC.md:2145`): "Import depth | 32". Not enforced anywhere.

Fix direction: iterative worklist with explicit visiting/visited states and a depth limit;
report cycles with the import span. Changes an accepted, Zig-built program: yes (m10
builds today; G6 lists module cycles as an approval gate).

### PIP-11. HIGH. KNOWN (B16 #6, #7, #8), with wider triggers

What is wrong: Errors that originate in imported files are misclassified or mislocated.

Evidence (beyond the three failing tests, whose root causes are in the table above):
- Imported tokenize error, `probes/m14_imported_tokenize_error.a7`: exit 8, `category: internal`, `exception_type: TokenizerError`, human stderr `Unexpected error: badtok.a7:3:10: Unexpected character`.
- Imported file with invalid UTF-8, `probes/m15_imported_bad_utf8.a7`: exit 8, `'utf-8' codec can't decode byte 0xff`. The main file gets exit 3 for the same condition (`compile.py:156`).
- Imported file with a dropped parse error, `probes/m32_module_parse_drop.a7`: exit 8.
- Imported semantic error, `probes/m16_semantic_mode_module_error.a7`: JSON `file` is the main file; human output prints main's line 3 (`s :: import "semhelper"`) under the module's `Return type mismatch` message, a wrong source excerpt. `ErrorFormatter.format_error` (`errors.py:461-522`) never prints a filename.
- Missing import (`probes/m29_missing_import.a7`): no span, and the message leaks every search path including a nonexistent `/home/cx89/Projects/pl-dev/a7-py/stdlib`.
- Load-time name-resolution errors in modules are discarded (`module_resolver.py:164-166` ignores `name_pass.errors`); they are found again only because the merged AST is re-analyzed.

Fix direction: catch `CompilerError` and `OSError`/`UnicodeDecodeError` per module and
return located diagnostics; carry `filename` and `source_lines` per declaration; use
`err.filename` in `_error_to_detail`. Changes an accepted, Zig-built program: no.

### PIP-12. HIGH. KNOWN (B16 #1-#4), with wider triggers

What is wrong: Destination paths are not checked against inputs, and artifacts are
reported by existence rather than by what this run wrote.

Evidence beyond the four failing tests:
- `--output` pointing at an imported module (`cli/log.txt`, section o07): `uv run a7 cli/mods/usesmod.a7 --output cli/mods/helpermod.a7` exit 0, `Compiled ... -> .../helpermod.a7`; the module source became `pub fn module_helpermod__work() i32 {`. The failing test checks only the main input.
- `compile.py:441` and `:471` truncate with `open(..., "w")` before writing; a failed write leaves a truncated artifact (INFERENCE from code; not provoked).

Fix direction: compare resolved destination paths with the input and every loaded module
file; track paths actually written in this run. Changes an accepted, Zig-built program: no.

### PIP-13. MEDIUM. NEW. Rich markup in user data crashes human output

What is wrong: User-controlled text (string literal token values, AST labels, file paths)
is interpolated into Rich markup strings. A closing tag such as `[/bold]` or `[/]` raises
`MarkupError`, which becomes exit 8. Opening tags are silently swallowed, so paths are
shown incorrectly.

Evidence:
- `console_formatter.py:380-386` puts `repr(token.value)` into `Table.add_row`; `:446`, `:673`, `:762` interpolate names; `compile.py:550-553` and `:556` interpolate `result.input_path` and `result.doc_path`; `compile.py:727` interpolates error messages that can contain paths.
- `cli/markup.a7` containing `io.println("[/bold] and [red]x")`: `--mode tokens`, `--mode ast`, `--mode semantic`, `--mode pipeline` and `-v` compile all exit 8 with `Unexpected error: closing tag '[/bold]' at position 2 doesn't match any open tag` (`cli/log.txt` o11).
- Path `cli/[/]x/p.a7`, default compile mode: exit 8 `closing tag '[/]' at position 56 has nothing to close`, after the `.zig` was written. Path `cli/[red]dir/p.a7`: exit 0 but printed as `cli/dir/p.a7` (o12).

Fix direction: pass `markup=False` or `rich.markup.escape()` for all user data; use `Text`
objects. Changes an accepted, Zig-built program: no.

### PIP-14. MEDIUM. NEW. Recursion over imports and expressions turns deep input into internal errors

What is wrong: Module loading recurses per import level (PIP-10). The type checker
recurses on binary expressions, although CLAUDE.md states semantic passes use explicit
stacks. Both surface as `internal` with no location. Parser recursion is allowed by
CLAUDE.md and is noted only for the exit mapping.

Evidence:
- `probes/deep_chain_3000.a7` (`x := 1 + 1 + ... ` with 3000 terms): exit 8 both formats, `maximum recursion depth exceeded`. Stage-by-stage run (`where.txt`): tokenize, parse and name resolution pass; `RecursionError` in `type_checker.py` `_visit_expression_impl -> visit_binary_expr -> visit_expression`.
- `probes/deep_parens_3000.a7`: exit 8, recursion in `parser.py` `parse_primary_expression`.
- `type_checker.py:774-775`: `visit_statement` also calls itself for each statement of a block.
- Chain of imports: PIP-10.

Fix direction: explicit stacks in module loading and the type checker (type checker owner);
map `RecursionError` to a located "nesting limit" source diagnostic. Changes an accepted,
Zig-built program: no.

### PIP-15. MEDIUM. NEW (shares the root cause of KNOWN T2a `z := z`). Use before declaration accepted

What is wrong: Name resolution predeclares every local in a block before the type checker
runs, and type-checker lookups are not position-aware, so a use earlier in the block
resolves to a later declaration.

Evidence:
- `name_resolution.py:421-422` defines locals while walking; `type_checker.py:1179-1187` looks up with no ordering; `type_checker.py:742-744` updates the predeclared symbol.
- Probe `probes/n01_use_before_decl.a7`: `x := y + 1` then `y := 2`. Exit 0/0; `build-obj`: `n01_use_before_decl.zig:15:16: error: use of undeclared identifier 'y'`.
- Probe `probes/n12_global_forward_ref.a7` (`A :: B + 1; B :: 2` at file scope) builds and is correct; file-scope forward references are fine in Zig.
- Probe `probes/n13_global_self_ref.a7` (`C :: C + 1` at file scope): exit 0; Zig `value of declaration ... depends on itself`. File-scope variant of T2a.

Fix direction: record declaration order and reject uses before the declaring statement in
block scopes; detect self-dependent globals. Changes an accepted, Zig-built program: no.

### PIP-16. MEDIUM. KNOWN F5. JSON crash is not limited to struct-yielding matches, and the handler is unsafe

What is wrong: `json_formatter._ast_to_dict` iterates `else_case` as a list, but a match
expression stores it as an `ASTNode`. The crash also happens on the semantic failure path,
and the internal-error handler re-serializes the same AST, so the second exception escapes
with exit 1 and a traceback.

Evidence:
- `json_formatter.py:149-165` lists `else_case` as a list field; `:211-222` does `for child in field_value`.
- `compile.py:714-715` (`_finish_with_failure` JSON branch) raises; `compile.py:491-503` catches and calls `self._to_json_payload(result)` again, which raises again and escapes `compile_file_detailed`.
- Probe `probes/n23_matchexpr_steals_stmt_scope.a7` (a match expression with `else:` and an int result, semantic failure): JSON exit 1, empty stdout, traceback ending `json_formatter.py", line 215 ... TypeError: 'ASTNode' object is not iterable` (`out/n23_*.json.stderr`).

Fix direction: handle single-node `else_case`; make the internal handler emit a payload
without AST data. Changes an accepted, Zig-built program: no.

### PIP-17. MEDIUM. NEW. Semantic mode and compile mode disagree on local imports

What is wrong: Module merge and alias annotation run only in codegen modes. In
`--mode semantic` a call `h.work()` on a local module goes through the stdlib path and is
rejected.

Evidence:
- `compile.py:252-261`: `if not import_errors and self.mode in codegen_modes:`.
- `type_checker.py:1318-1322`: without `file_module_call` the call goes to `_visit_stdlib_module_call`, which reports `Unknown stdlib call`.
- Probe `probes/f04_semantic_mode_call.a7`: compile mode exit 0 and `build-obj` 0; `--mode semantic --format json` exit 6 `Type is not callable (Unknown stdlib call 'flat.work')` (`out/f04_sem.json:503`).
- `test_cli_failures.py:181-205` uses a main without any module call, so it does not see this.

Fix direction: run module merge in every semantic mode. Changes an accepted, Zig-built
program: no.

### PIP-18. MEDIUM. NEW. Duplicate declarations silently accepted in name resolution

What is wrong: `define()` failures are ignored for import aliases and enum variants.

Evidence:
- `name_resolution.py:130`: `self.symbols.define(module_symbol)` result ignored. `name_resolution.py:287`: `self.symbols.define(variant_symbol)` ignored. `SemanticErrorType.DUPLICATE_VARIANT` (`errors.py:60`) is never raised.
- `probes/m23_duplicate_alias.a7` (`h :: import "modhelper"` and `h :: import "std/math"`): exit 0 (build fails only because of PIP-6).
- `probes/n09_fn_then_alias.a7` (`io :: fn() {}` then `io :: import "std/io"`): exit 0 and `build-obj` 0; the parse output has both declarations (`confirm.txt`), and the import is silently ignored.
- `probes/n08_dup_enum_variant.a7` (`E :: enum { A A }`): exit 0; Zig `duplicate enum member name 'A'`.

Fix direction: report `ALREADY_DEFINED`/`DUPLICATE_VARIANT` on every failed define.
Changes an accepted, Zig-built program: yes (n09 builds today).

### PIP-19. MEDIUM. NEW. Default output path rewrites directory names

What is wrong: The default output path uses `str.replace(".a7", ext)`, which replaces
every occurrence, including in directory names, and the writer then creates the new
directory.

Evidence:
- `compile.py:848-850`: `return input_path.replace(".a7", extension)`; `compile.py:438-440` `os.makedirs(out_dir, exist_ok=True)`. `compile.py:457` does the same for `--doc-out auto` through the API (the CLI resolves `auto` with `with_suffix` at `cli.py:85`, so that branch is unreachable from the CLI).
- `cli/proj.a7dir/prog.a7` compiled without `--output`: exit 0, `Compiled .../proj.a7dir/prog.a7 -> .../proj.zigdir/prog.zig`; `find` shows the new `proj.zigdir/` (`cli/log.txt` o04).

Fix direction: `Path(input_path).with_suffix(ext)`. Changes an accepted, Zig-built program: no.

### PIP-20. MEDIUM. NEW. Named and bare file imports exit 0 with broken Zig

What is wrong: SPEC calls selected imports "Resolver-only ... not backend-runnable yet",
but the compiler neither rejects them nor lowers them. The module is merged, the name
resolves unqualified, and the call is emitted without the prefix.

Evidence:
- SPEC `docs/SPEC.md:1492-1493`: "Resolver-only selected import metadata; not backend-runnable yet".
- `probes/m26_named_import.a7` (`import "modhelper" { work }`, `work()`): exit 0; Zig `use of undeclared identifier 'work'`.
- `probes/m27_bare_import.a7` (`import "modhelper"`, `work()`): same.
- `SemanticErrorType.UNSUPPORTED_IMPORT` and its advice (`errors.py:90, 302`) exist and are never used; "Backend Import Support" (`compile.py:251, 286-293`) always reports 0 errors.

Fix direction: reject non-alias file imports with `UNSUPPORTED_IMPORT` until implemented.
Changes an accepted, Zig-built program: yes for bare imports used only for leaked types or
constants (the f02 pattern), otherwise no.

### PIP-21. MEDIUM. KNOWN (audit A-32, packet P5). Capture names are decided by any visible symbol

What is wrong: A match identifier pattern is a capture only if no symbol of that name is
visible anywhere, including globals and functions, so adding an unrelated global changes
the meaning of an existing arm.

Evidence:
- `name_resolution.py:384-385`: `if self.symbols.lookup(name) is not None: continue`.
- `probes/n04_capture_outer_global.a7` (global `value :: 7`, `case value:` on `x := 3`): exit 0, `build-obj` 0; the arm compares with 7 instead of capturing.
- `probes/n05_capture_named_function.a7` (`case helper:` where `helper` is a function): exit 6 `Type mismatch: expected 'i32', got 'fn() i32' (Match pattern type mismatch)`.

Fix direction: owner decision in packet P5. Changes an accepted, Zig-built program: yes.

### PIP-22. MEDIUM. NEW. `--output` equal to `--doc-out`

What is wrong: The markdown report overwrites the generated Zig and both are advertised.

Evidence: `cli/same.a7 --format json --output cli/same_out.txt --doc-out cli/same_out.txt`:
exit 0, `status ok`, `artifacts {'output_path': '.../same_out.txt', 'doc_path': '.../same_out.txt'}`;
the file starts `# Compilation Report` (`cli/log.txt` o06). `cli.py:75-87` has no check.

Fix direction: reject equal destinations as a usage error. Changes an accepted, Zig-built program: no.

### PIP-23. MEDIUM. NEW. SPEC 11.2 bare typed math builtins are not available to users

What is wrong: SPEC says typed spellings map through the registry, but the type checker
rejects them as undefined. Their only observable effect is the hijack in PIP-2.

Evidence:
- SPEC `docs/SPEC.md:1571-1572`: "Some typed math builtin spellings such as `sqrt_f32` and `sqrt_f64` also map through the stdlib registry."
- `probes/s07_builtin_sqrt_f64_undeclared.a7`: exit 6 `Undefined type (Identifier 'sqrt_f64')` and `Cannot call undefined identifier 'sqrt_f64'`. `probes/s03_min_f32_arity.a7`: same for `min_f32`.

Fix direction: remove the SPEC claim and the bare-builtin registry path, or implement them
with lowest priority per A.3 (owner decision). Changes an accepted, Zig-built program:
removal alone, no; together with PIP-2, yes.

### PIP-24. LOW. NEW. Human diagnostics are written to stdout

Evidence: `compile.py:32` `console = Console()` (stdout); `compile.py:717-727` prints all
failures there, while `compile.py:493` prints internal errors to stderr. `cli/semerr.a7`:
exit 6, stdout 758 bytes, stderr 0 bytes (`cli/log.txt` o16). Fix: `Console(stderr=True)`
for diagnostics. Changes an accepted, Zig-built program: no.

### PIP-25. LOW. NEW. JSON schema inconsistencies

Evidence (`cli/schema.txt`):
- Tokenize failure: `stages` is `[]`; parse and semantic failures include a stage with `ok: false`; codegen failure has no `codegen` stage (`compile.py:172-184`, `:407-417`).
- `details[].message` repeats `file:line:col:` because it is `str(err)` (`compile.py:798`, `errors.py:638-656`), while `span` carries the same data.
- Internal failures have `details: []` and `span: null` (`compile.py:494-498`).
- In codegen modes `stages.parse.ast` is the merged and preprocessed tree, because `result.ast` is reassigned at `compile.py:261` and `:395` and serialized at `:756-760`.
- `stages.tokenize.token_count` excludes EOF (`compile.py:174`) while `metadata.token_count` includes it (`json_formatter.py:58`); the latter is dropped from the payload.
Changes an accepted, Zig-built program: no.

### PIP-26. LOW. NEW. `--backend` is not validated

Evidence: `cli.py:54-58` accepts any string. `--mode semantic --backend nope --format json`
returns `status ok`, `backend nope`. Compile mode reports it as codegen exit 7 after the full
semantic run (`cli/log.txt` o14); `compile.py:852-857` silently picks `.out` for the default
output path. Fix: `choices=list_backends()` (usage exit 2). Changes an accepted, Zig-built program: no.

### PIP-27. LOW. NEW. Doc failure after a successful write; non-atomic writes

Evidence: `cli/same.a7 --output cli/o10.zig --doc-out cli/ro/sub/x.md` (read-only parent):
exit 3, `status error`, `category io`, but `artifacts {'output_path': '.../o10.zig'}` and the
22-byte file remains (`cli/log.txt` o10). `compile.py:441-442`, `:471-472` write in place.
Fix: write to a temporary file and rename after all outputs succeed. Changes an accepted, Zig-built program: no.

### PIP-28. LOW. NEW (sibling of KNOWN F1). Empty source compiles

Evidence: `cli/empty.a7` (0 bytes): exit 0, `status ok`, 0-byte `cli/empty.zig`
(`cli/log.txt` o18). `TokenizerErrorType.FILE_EMPTY` (`errors.py:37`) is never raised.
Changes an accepted, Zig-built program: no for executables (INFERENCE: the Wave 0 ledger F1
reports that a 0-byte Zig file passes `ast-check` and `build-obj`; with no `main` it cannot
link as an executable; `build-exe` was not run here).

### PIP-29. LOW. NEW. Name-resolution diagnostics are produced by the wrong pass and duplicated

Evidence: the "Name Resolution" pass (`name_resolution.py`) only registers declarations and
never resolves uses. Undefined names are reported by type checking as
`TypeErrorType.UNDEFINED_TYPE` with context `Identifier 'x'` (`type_checker.py:1189`), shown
as "Undefined type (Identifier 'c')" (n21, n06, s07). `probes/n16b_generic_param_leak.a7`
(`g :: fn(y: T) T` without generics) reports 4 errors for 2 occurrences (each twice).
Changes an accepted, Zig-built program: no.

### PIP-30. LOW. NEW. Nested function declarations are not registered

Evidence: `name_resolution.py:401-517` has no `NodeKind.FUNCTION` branch. Probe
`probes/n06_nested_fn.a7`: exit 6 `Undefined type (Identifier 'inner')`, while the
preprocessor has hoisting for nested functions (`ast_preprocessor.py:520-...`) and
`zig.py:397-399` skips hoisted names. SPEC does not define nested functions (grep found no
mention). Either reject with a clear diagnostic or register them. Changes an accepted,
Zig-built program: no.

### PIP-31. LOW. NEW. Local named like a generic parameter

Evidence: `probes/n16c_generic_param_vs_local.a7` (`identity($T) :: fn(value: $T) $T { T := 3 ... }`):
exit 0; Zig `local constant 'T' shadows function parameter`. Name resolution puts generic
params in the function scope and the local in the body block scope (`name_resolution.py:158-173`).
Changes an accepted, Zig-built program: no.

### PIP-32. LOW. NEW. Local `io.a7`/`math.a7` are unimportable

Evidence: `module_resolver.py:127-128` checks virtual modules first, and `stdlib/__init__.py:11-16`
maps bare `io` and `math`. `probes/m17_local_io_file.a7` with `probes/io.a7`: exit 6
`Struct has no such field (Stdlib module 'io' has no function 'hello')`. Fix: a diagnostic
that names the shadowing. Changes an accepted, Zig-built program: no.

### PIP-33. LOW. NEW. Superlinear scope matching

Evidence: `type_checker.py:147` rebuilds `matches` by scanning all children on every call.
One function with N sibling blocks (`probes/perf_blocks_N.a7`), type checking only:
1000 blocks 0.018 s, 2000 0.044 s, 4000 0.165 s (`perf2.txt`). Measured superlinear;
quadratic is INFERENCE from the code.

### PIP-34. LOW. NEW. Formatter defects

- `markdown_formatter.py:264` passes the root `scope_name` instead of `cur_name`, so struct fields are never labeled "unresolved field".
- `markdown_formatter.py:193-237` and `console_formatter.py:805-825` show only declarations, parameters, bodies, statements, fields and variants: expressions, loop bodies (`body` of while/for) and match arms are missing; console puts `else` statements before `then` statements under one node.
- `markdown_formatter.py:55` labels `len(source_code)` (characters) as bytes; source containing a fence breaks the report.
- `console_formatter.py:487-556` `format_type` recurses into generic and function type arguments (INFERENCE: deep nesting can reach the recursion limit; not probed).
- Rich soft-wraps the success line, splitting paths across lines in captured output (every human `Compiled ... ->` line in `out/*.summary`).

### PIP-35. LOW. NEW. Dead code, duplicated logic, structural blockers

Dead or unreachable:
- `backend_import_errors` is always empty (`compile.py:251`); "Backend Import Support" is a constant pass.
- `ModuleResolver.topological_sort`, `add_search_path`, `remove_search_path`; `ModuleTable.resolve_using_import`, `resolve_named_import`; the resolver's and the name-resolution pass's `ModuleTable`s are both filled and never consulted by later stages (`module_resolver.py:199-232`, `name_resolution.py:122,133,137`).
- `SymbolTable.enter_scope(reuse_existing=True)`, `get_unused_symbols`, `lookup_in_scope`.
- `register_mem_module` and `register_string_module` are never called, so the "stub" modules do not exist (`stdlib/mem.py`, `stdlib/string.py`).
- `StdlibRegistry.get_backend_mapping` is used only by tests; the Zig backend hard-codes the mappings (`zig.py:1612-1650, 2155-2168`), so `backend_map` is decorative.
- `errors.create_error_handler`; `errors.ImportError` (shadows the builtin name); error types `CIRCULAR_IMPORT`, `MODULE_NOT_FOUND`, `IMPORT_NAME_CONFLICT`, `UNSUPPORTED_IMPORT`, `DUPLICATE_VARIANT`, `DUPLICATE_PARAMETER` are never raised.
- `SemanticContext.errors` receives strings from `validate_break`/`validate_continue`/`validate_return` (`semantic_context.py:302-377`) that are never read; `semantic_validator.py:1209-1212` calls them as queries, appending on every call.
- `SemanticContext.current_function` is a single slot, not a stack (`semantic_context.py:91-106`).
- Search path `Path(__file__).parent.parent / "stdlib"` (`compile.py:242`) does not exist in the repository; in a wheel it becomes `site-packages/stdlib`.
- `compile_project`/`compile_a7_project` are not reachable from the CLI and compile each file separately.

Duplicated: the variadic check in `_backend_unsupported_feature_errors` (`compile.py:629-667`)
and in `type_checker.py:576-588`; stdlib recognition in three uncoordinated places
(`ast_preprocessor.py:195-220`, `type_checker.py:1414-1435`, `zig.py:139-149, 1631-1650, 2155-2168`).

Blockers for the Wave 3 typed IR (`docs/plan/execution.md`): modules have no identity
(textual prefix, flat global scope, no per-file origin); scopes are matched by name and
position between two passes (PIP-4, PIP-5); symbol lookups are not declaration-order aware
(PIP-15); passes mutate the AST in place (`file_module_call`, `module_emit_prefix`,
`is_capture_pattern`, `stdlib_canonical`) so no stage output is stable.

## Checked and correct

- Stage gating: tokens mode stops after tokenize; ast mode after parse; semantic mode runs no codegen; semantic sub-passes run only if earlier ones had no errors (`compile.py:313-359`); codegen is skipped on semantic failure and no `.zig` is written (`probes/n02`, `test_error_stage_matrix.py`).
- Exit codes: IO 3 for a missing file, a non-`.a7` suffix and a directory input (`cli/schema.txt`, `cli/log.txt` o18); tokenize 4; parse 5; semantic 6; codegen 7; internal 8.
- The top-level JSON keys are identical for all exit classes checked (`cli/schema.txt`), and stdout is valid JSON for them (excluding F4/F5 triggers).
- `--output` with a non-compile mode and `--doc-out` with tokens/ast/semantic are usage errors (exit 2, stderr) (`cli.py:72-80`, `test_cli_failures.py:381-389`).
- Doc mode writes `<file>.md` and reports it (`cli/log.txt` o17); `--doc-out auto` works.
- Path traversal (`../pipeline`) and absolute paths (`/etc/passwd`) are rejected (`probes/m30_traversal.a7`, `probes/m31_absolute.a7`, exit 6); null bytes and backslashes are rejected in `_is_safe_module_path` (`module_resolver.py:64-74`, code reading).
- Symlinks that leave the search paths are rejected, both a file link (`symroot/inner/link.a7 -> ../../outside/secret.a7`) and a directory link (`symroot/linkdir -> ../outside`): exit 6 (`sym.txt`), because `module_resolver.py:76-78, 108` checks the resolved path. The message says "not found" rather than naming the reason.
- Virtual `std/io` and `std/math` imports with arbitrary aliases; unknown stdlib member is exit 6 (`test_cli_failures.py:284-304`); wrong `math.sqrt` arity is exit 6 (`probes/s04_math_alias_unknown.a7`).
- Undeclared `io` (no import, or a bare `import "std/io"`) is rejected (`probes/s05`, `probes/s06`).
- Recursion ban: function-pointer alias cycle rejected (`probes/n17_fnptr_alias_cycle.a7`); a cycle inside an imported module is rejected (`probes/n18_recursion_via_module.a7`, but the location points into main.a7, PIP-11).
- Capture bindings are immutable (`probes/n15_capture_mut.a7`, exit 6).
- Block-scoped type aliases do not leak (`probes/n19_type_alias_scope.a7`); duplicate parameters rejected (`probes/n20_duplicate_param.a7`); duplicate struct fields rejected (code reading, `name_resolution.py:251-252`).
- Generic parameters do not leak into later functions (`probes/n16b_generic_param_leak.a7`).
- Break and continue outside loops are rejected (`probes/c01_break_outside_loop.a7`).
- File-scope forward references between constants work (`probes/n12_global_forward_ref.a7`).
- Formatters' AST and scope walks use explicit stacks (`json_formatter.py:205-232`, `markdown_formatter.py:199-237`, `console_formatter.py:230-252`), except `format_type` (PIP-34).
- `_annotate_file_module_calls` and `_backend_unsupported_feature_errors` are iterative with a `seen` set.

## Test gaps

- No test for any imported module with more than one function, an intra-module call, a transitive import, a cycle, a self-import, duplicate imports of one file, name clashes between importer and module, or `pub` enforcement (PIP-6 to PIP-10).
- No test that a local variable shadowing an import alias, or a value named `io`/`math`, keeps its own call (PIP-1, PIP-3; B14 has none either).
- No test that a user function named like a registry builtin keeps its body (PIP-2).
- No test combining `else if` or match expressions with later blocks that declare constants (PIP-4, PIP-5).
- No test for use before declaration in a block (PIP-15), duplicate aliases or enum variants (PIP-18).
- No test for `--mode semantic` on a program that calls a local module (PIP-17); `test_cli_failures.py:181-205` asserts only that a pass named "Backend Import Support" exists, a pass that can never fail (coverage illusion).
- No test for default output path derivation, equal `--output`/`--doc-out`, output onto an imported module, markup in source or paths, `--backend` validation, stdout/stderr split of human errors, or empty source.
- No test that JSON output stays valid for match expressions with `else` on success and failure paths.
- `test_stdlib_registry.py` mostly restates the registry tables (for example `TestStdlibDataclasses` checks dataclass field storage, and `TestCustomModuleRegistration` tests registration paths the compiler never uses); none of it checks that registry names cannot capture user symbols.
- `test_error_stage_matrix.py:52` asserts a magic total of 61 checks.
- `test_module_resolver.py` has no test of `load_module` beyond virtual modules.

## Not verified

- Whether PIP-4/PIP-5 scope desync can give a wrong type that reaches a Zig-built binary.
- `using import` (not a parser form per SPEC 10.2) and `compile_project`.
- Partial-write behavior on a real write failure (PIP-12, PIP-27 inference).
- `format_type` recursion depth (PIP-34).
- Semantic mode on a module that itself has type errors (module declarations are not merged in that mode, so INFERENCE: its errors go unreported).
- Side observation for the tokenizer auditor: `f32` cannot be used as a function name (`chain/` first run: `c32.a7:3:5: Unexpected token 'f32'`); it is a type keyword, which may be intended.

claims checked: 120
