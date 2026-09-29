# Language-feature completeness audit — 2026-09-18

Scope: what a program can and cannot express in A7 today. Nine feature areas
(generics, multiple returns and destructuring, optionals and error handling,
pattern matching, compile-time evaluation, data modelling, strings and text,
integer and float work, program structure), each established by probes that
compile and, where the probe rules allow, build and run.

Tree audited: the main working tree as it stands on 2026-09-18, with batches C3,
PR-00, T0, V1, NOREC-0 and PL-02 applied as uncommitted changes. C1, C4 and C2
are in flight in worktrees and were not audited.

Method. Every probe lives in `tmp/audit/2026-09-18/language/`. Each was compiled
with `uv run a7 <probe>.a7 --output <probe>.zig` (exit code recorded as `a7=`)
and, when that returned 0, checked with `zig build-obj -fno-emit-bin <probe>.zig`
(recorded as `zig=`). Run-allowed probes were built with `zig build-exe -ODebug`
and run. `zig version` is 0.16.0.

**One probe was run before its header was rechecked.** `ps03_bounds_tool.a7`
takes `ref Record` and `ref Report` parameters, which the probe rules exclude
from running, and it was built and run under both `-ODebug` and
`-OReleaseFast` before that was caught. Its header, and those of
`ps02_workaround_tool.a7` and `g19_nongeneric_ref_assign.a7`, now read
`// probe: compile-only`. The observed output stands as an observation; the rule
was breached, and no further `ref` probe was run.

Two facts shape everything below.

**The compiler reports one stage at a time.** A type error stops the pipeline
before the safety pass, so a program's error list is only its first wall. The
naive 193-line tool (`ps01_naive_tool.a7`) reported 17 type errors and none of
the safety-proof rejections sitting behind them.

**Zig acceptance is tested, but over a narrow set of programs.** Tests do build
the emitted Zig: `zig build-obj -fno-emit-bin` at four sites in
`test/test_codegen_zig.py` (`zig_build_check`, `:112`), at
`test/test_compound_assignment_types.py:151` and at
`test/test_float_nonfinite_folding.py:189`; `zig build-exe` at six sites in
`test/test_codegen_zig.py` and in `test_zig_backend_runtime.py:54`,
`test_pipeline_native.py:39`, `test_module_alias_shadowing.py:85` and
`test_float_nonfinite_folding.py:69`. What none of them covers is the shape of
an ordinary program: no array of structs, no struct `==`, no string `==`, no
non-enum match, no `::` constant as an array size, no bounds guard, no `char`
operation. Ten of the 29 findings here are "A7 exits 0, Zig rejects" (LNG-03,
06, 07, 08, 09, 10, 11, 13, 18, 23); four more (LNG-01, 05, 16, 20) exit 0 and
produce an empty or wrong program.

## Summary

| Severity | NEW | KNOWN | Total |
| --- | --- | --- | --- |
| CRITICAL | 2 | 4 | 6 |
| HIGH | 4 | 6 | 10 |
| MEDIUM | 5 | 5 | 10 |
| LOW | 2 | 1 | 3 |
| **Total** | **13** | **16** | **29** |

Every NEW label was checked against `docs/audits/2026-09-16/compiler/*.md` by
grep before it was written; seven findings moved from NEW to KNOWN in that
pass (LNG-05, 06, 08, 09, 15, 21, 22).

Status by feature area:

| # | Feature | Status | The one sentence |
| --- | --- | --- | --- |
| 1 | Generics | partial | Declared generic functions and structs work end to end by handing `comptime T: type` to Zig; four of SPEC §7's own forms do not compile. |
| 2 | Multiple returns / destructuring | parsed-only is generous — not parsed, and dangerous | Every spelling fails; one spelling exits 0 and emits a file with no program. |
| 3 | Optionals and error handling | missing | A fallible function returns a struct with an `ok` flag, checked by hand; there is no other form. |
| 4 | Pattern matching | partial | Literals, ranges, enums, captures, `fall`, match-as-expression and match-on-call all work; exhaustiveness is checked for enums only, and six pattern shapes pass A7 and fail Zig. |
| 5 | Compile-time evaluation | partial | `::` constants fold and print, but a constant used as an array size makes the array unindexable. |
| 6 | Data modelling | partial | Nested structs, struct copy and struct-array fields work; a bare array of structs, a slice in a struct, struct equality and partial initialisation all fail in Zig. |
| 7 | Strings and text | broken for text work | `char` supports only `==` and `!=`; no ordering, no arithmetic, no cast to an integer. |
| 8 | Integers and floats | partial | Mixed widths, signed division and float comparison work; a division whose divisor passes through a `cast` cannot be proved non-zero by any guard, overflow and shifts are emitted raw with no proof and no diagnostic, and there is no float precision control. |
| 9 | Program structure | single-file only | 1087 lines compile in 140 ms; splitting into modules emits Zig that does not build as soon as one imported function calls another. |

---

## Findings

### LNG-01. CRITICAL. KNOWN (PAR-03 `parser.md:46`; PAR-02 heuristic `parser.md:103-106`; PRD-33 `production-readiness.md:831`). New shapes. A parse error inside a function body deletes the function, exits 0, and emits a Zig file with no program

**What is wrong.** `a7/parser.py:190-218` recovers from a `ParseError` raised
while parsing a top-level declaration whenever at least one declaration has
already parsed. `synchronize()` (`a7/parser.py:255-289`) then skips forward to
the next identifier followed by `::` or `:=`. The function that failed is
discarded, the program node is built from what survived, the parse stage reports
`"ok": true`, and the compiler exits 0.

**Evidence.** Five probes, all `a7=0`, `zig=0` (an object file needs no `main`):

| Probe | Source line that trips it | Emitted Zig, in full |
| --- | --- | --- |
| `mr01_var_pair.a7` | `x, y := 10, 20` | `var y = 10;` |
| `mr13_bad_stmt_drop.a7` | `a, b := 1, 2` | `fn helper() i32 { return 1; }` + `var b = 1;` |
| `mr14_second_fn_survives.a7` | `a, b := 1, 2` | `var b = 1;` + `fn after() i32 { return 7; }` |
| `mr15_pair_nested_block.a7` | `a, b := 1, 2` inside `if true {}` | `var b = 1;` |
| `b5.a7` | `if good { ret Res{ok: true, value: 42} }` | rejected at the *call site* with `Undefined type (Identifier 'lookup')` |

`uv run a7 tmp/audit/2026-09-18/language/mr01_var_pair.a7 --mode ast --format json`
shows the parse stage returning `"ok": true` with a two-element `declarations`
list holding the `io` import and a top-level `VAR y`. `main` is gone.

`b5.a7` is the shape an ordinary program hits without writing any planned
syntax: a one-line guard clause returning a struct literal. The struct-literal
heuristic (`a7/parser.py:140-162`) refuses `Res{` because `if` appears earlier on
the same line, the parse fails, `lookup` is deleted, and the user is shown three
errors at lines 9-11 saying the function they wrote at line 4 does not exist.
The multi-line spelling (`b4.a7`) compiles (`a7=0`, `zig=0`), so the difference
is a line break.

**Fix direction.** Make a `ParseError` inside a function body fatal, so it is
reported at its own location and never recovered from. The struct-literal
heuristic half is PAR-02's (`parser.md:136`).

**Changes accepted programs?** No for the recovery path — every affected program
is already either rejected or silently emptied. Yes, narrowly, for PAR-02's
half: see `parser.md:140`.

### LNG-02. CRITICAL. NEW. `char` supports only `==` and `!=` — no ordering, no arithmetic, no conversion to or from an integer

**What is wrong.** `a7/types.py:88-93` lists the numeric primitives; `char` is
not among them. `a7/passes/type_checker.py:3049-3056` `_types_are_comparable`
returns `self._is_numeric_compatible(left) and self._is_numeric_compatible(right)`
when `ordering=True`, so `<`, `<=`, `>`, `>=` on two `char` values are rejected.
`visit_binary_expr` (`:1221-1236`) rejects `+`/`-` on `char` through
`REQUIRES_NUMERIC_TYPE`, and the cast classifier refuses `cast(i32, c)`.

**Evidence.**

| Probe | Source | a7 exit | Message |
| --- | --- | --- | --- |
| `st16_char_lt.a7` | `c < 'b'` | 6 | `Operator requires compatible types (lt between char and char)` |
| `st20_char_typed_compare.a7` | `c: char = 'a'; d: char = 'b'; c < d` | 6 | same, `lt between char and char` |
| `st17_u8_index_compare.a7` | `b := a[0]; b >= 'a'` | 6 | `ge between char and char` |
| `st19_char_minus.a7` | `c - '0'` | 6 | `Requires numeric type` |
| `st09_char_to_digit.a7` | `cast(i32, c)` | 6 | `Unsafe type cast (cast must be classified and range-proven: only primitive numeric casts are supported)` |
| `st18_char_cast_u8.a7` | `cast(u8, c)` | 6 | same |
| `st15_char_eq_only.a7` | `c == 'a'` | 0, zig=0, runs, prints `true` | — |

**What an ordinary program cannot do.** Write `is_digit`, `is_alpha`,
`is_upper`, `to_lower`, `to_upper`, or convert `'7'` into `7`. Every text tool
starts here. The only workaround is to enumerate every character: `is_digit` as
ten `or`-ed `==` tests and `digit_value` as a ten-arm `match` on char literals,
which is what `ps02_workaround_tool.a7:20-38` had to do.

The message is also wrong on its face: it reports an incompatibility "between
char and char".

**Fix direction.** Either make `char` ordered and integrally castable (it is
`u8` in the emitted Zig — `st04_index.zig` proves `a[0]` is a `u8`), or register
the SPEC 11.2 `char_is_digit` / `char_to_upper` family that already exists on
paper (`docs/SPEC.md:1631-1638`).

**Changes accepted programs?** No. Every affected program is rejected today.
The owner still has to choose between the two directions; this is a language
decision with no gate. The nearest owner is track 8b (stdlib), and
`docs/plan/audit/language-audit-checklist.md:70` records that
`a7/stdlib/string.py` is an empty stub that is not even aliased.

### LNG-03. CRITICAL. KNOWN (PIP-6, `visibility-modules.md:550`). New scale. An imported module whose functions call each other emits Zig that does not build

**What is wrong.** Imported declarations are renamed
`module___<mod>__<name>`, but calls made *inside* the imported module to its own
functions keep the original spelling.

**Evidence.** `ps04/` is `ps03_bounds_tool.a7` split into `text.a7` (3
functions), `report.a7` (7 functions and 3 types) and `main.a7`.
`uv run a7 tmp/audit/2026-09-18/language/ps04/main.a7 --output .../ps04/main.zig`
exits 0. `zig build-obj -fno-emit-bin main.zig` reports:

```
main.zig:37:13: error: use of undeclared identifier 'is_digit'
main.zig:81:17: error: use of undeclared identifier 'set_name'
main.zig:154:17: error: use of undeclared identifier 'print_name'
```

`grep -n '^pub fn' ps04/main.zig` shows all ten functions present under their
`module___` names; only the call sites were missed.

**What an ordinary program cannot do.** Have more than one function per file in
any file it imports. That is the practical ceiling on multi-file A7 today, and
it is lower than `docs/STATUS.md:29-31` implies.

`ps04/main.a7` also calls `add_record`, `sort_by_score`, `print_report` and
`parse_int` and names the type `Report` **unqualified**, with no `using import`
and with the aliases `text` and `rep_mod` bound but unused. A7 accepts all of
it: visibility is not enforced anywhere (KNOWN PIP-7, `visibility-modules.md`
summary rows).

**Fix direction.** PIP-6's; no batch names it (`visibility-modules.md:603`).

**Changes accepted programs?** No — every such program emits Zig that does not
build.

### LNG-04. CRITICAL. NEW. A value read from a parameter, a struct field or a function call can never be used as an index, whatever guard precedes it

**What is wrong.** The bounds proof accepts an index whose interval the fact
engine already tracks — a literal, a loop induction variable, or a local
initialised from a constant. A value read from a parameter, a struct field or a
function call is unbounded, and an explicit guard does not narrow it.

**Evidence.**

| Probe | Shape | a7 exit |
| --- | --- | --- |
| `bd01`, `bd02` | local array, index is a loop counter bounded by a literal | 0 (zig=0) |
| `bd03`, `bd04` | array inside a struct, reached directly and through `ref`, literal bound | 0 (zig=0) |
| `bd05` | fixed-array parameter, loop counter, literal bound | 0 (zig=0) |
| `bd07` | `n: usize = 2` then `if n < 4 { a[n] }` | 0 (INFERENCE: on the tracked interval, not on the guard) |
| `bd13_guard_from_param.a7` | `get :: fn(a: [4]i32, idx: usize) i32 { if idx < 4 { ret a[idx] } ... }` | **6** `index bounds are not proven` |
| `bd12_guard_from_call.a7` | `idx := pick(); if idx < 4 { a[idx] }` | **6** same |
| `bd11_field_bound_if_lt.a7` | `idx: usize = s.n; if idx < 4 { s.items[idx] = v }` | **6** same |
| `bd09`, `bd10` | early-return guard `if s.n >= 4 { ret }` then `s.items[s.n]` | **6** same |
| `bd06_slice_param_index.a7` | index into a `[]i32` parameter | **6** same (KNOWN S11) |

A guard *does* refine a variable the interval engine already tracks, even after
loop widening: `ps02_workaround_tool.a7`'s `set_name` (`n: usize = 0`
incremented inside a `for ... in`, then `if n < 16 { r.name[n] = ch }`) is
accepted — `ps02`'s only two errors are in `add_record`. The line is between
tracked and untracked values, not between guarded and unguarded ones.

**What an ordinary program cannot do.** Write a bounds-checked accessor. Append
to a buffer at a stored length. Index by anything a caller supplied. The
150-line `ps02_workaround_tool.a7` fails on exactly this —
`set_name(rep.records[idx], text)` where `idx := rep.count`, guarded by
`if rep.count >= 8 { ret }` — and `ps03_bounds_tool.a7` compiles only because
every loop was rewritten to run over the array's literal capacity with an
`if i < count` filter inside, a rewrite that is slower and harder to read than
the original.

**Fix direction.** Give the fact domain a rule for `if v < C` on an untracked
`v`, and a rule that carries a `usize` parameter's guard into the branch.
`a7/safety.py:97-222`, batch SD / P7 (`execution.md:139,462`).

**Changes accepted programs?** No — it only accepts more.

### LNG-05. CRITICAL. KNOWN (`docs/lang-safety/edge-cases/03-definite-assignment.md:1-13`, which cites `07-language-review.md §1.6`; gate M34). Measured: an uninitialised struct returns garbage, an uninitialised scalar is silently zeroed

**What is wrong.** `x: i32` with no initialiser emits `const x: i32 = 0;`
(`dm08_uninit_read.zig:15`). `p: P` where `P` is a struct emits
`const p: P = undefined;` (`dm09_zero_struct.zig:19`). Neither is diagnosed.

**Evidence.** Both probes are `a7=0`, `zig=0`. Built with `zig build-exe -ODebug`
and run: `dm08_uninit_read.bin` prints `0`; `dm09_zero_struct.bin` prints
`-1431655766` (0xAAAAAAAA, Zig's debug undefined fill). The same source shape,
two different answers, no diagnostic for either.

The research note already says both halves —
"The Zig backend either emits `undefined` (undefined behavior under
`-O ReleaseFast`) or zero-initializes. Neither is correct."
(`docs/lang-safety/edge-cases/03-definite-assignment.md:11-13`) — and records
that gate M34 proposes rejecting unassigned reads. What is new here is the
measurement: the split is by type category, and the garbage value was observed.
`grep -rin 'definite\|uninit' a7/passes/ a7/safety.py` returns nothing, so no
check exists.

**What an ordinary program cannot rely on.** That a declared value has a value.
The zero for scalars is not a documented rule either — `docs/SPEC.md:407-425`
says nothing about default initialisation.

**Fix direction.** Either a definite-assignment check, or one documented rule
applied to every type.

**Changes accepted programs?** Yes if a check is added — a program that reads an
uninitialised scalar and relies on the silent zero would start being rejected.
Needs approval; no gate owns it.

### LNG-06. CRITICAL. KNOWN-family (ZIG-24 / B4, `backend.md:373-375`). New element type. A local array of structs with no initialiser emits `[_]P{0} ** N`, which Zig rejects

**Evidence.** `dm02_array_of_structs.a7`, `a7=0`, `zig=1`:

```
dm02_array_of_structs.zig:20:26: error: expected type 'dm02_array_of_structs.P', found 'comptime_int'
    var pts: [3]P = [_]P{0} ** 3;
```

`dm12_for_in_array_structs.a7` is the same shape with a `for ... in` loop over
the array. The zero-fill emitter uses the scalar zero for every element type. An
array of structs written with an explicit literal list
(`dm03_array_struct_literal_init.a7`) compiles, builds and prints `2`, so the
workaround is to write out every element — impractical above a handful, and
impossible when the count is a `::` constant (LNG-15).

ZIG-24 records the same emitter bug for `[2]string` and `[2][2]i32`
(`backend.md:374-375`); a struct element is a third shape of it.

**Fix direction.** Emit `undefined` (as the struct case already does) or a
recursive zero value.

**Changes accepted programs?** No.

### LNG-07. HIGH. KNOWN (TYP-09 / B3, evidence map row 59). Status changed: string `==` is now a Zig error, not a silent address compare

**Evidence.** `st01_compare.a7` (`a: string`, `b: string`, `a == b`): `a7=0`,
`zig=1`, `error: operator == not allowed for type '[]const u8'`.
`st02_compare_literal.a7` (`a == "abd"`): `a7=0`, `zig=1`,
`error: cannot compare strings with ==`.

The evidence map records B3 as "compares addresses". Under Zig 0.16 the emitted
code no longer builds at all, so the defect is now a failed build rather than a
wrong answer. Ordering is rejected earlier, in A7: `st21_string_order.a7` exits 6
with `lt between string and string`.

**What an ordinary program cannot do.** Compare two strings for equality or
order. No sort by name, no keyword match, no dictionary.

**Changes accepted programs?** No.

### LNG-08. HIGH. KNOWN (TYP-09, `types.md:247-254`). Confirmed. Struct equality is accepted and rejected by Zig

**Evidence.** `dm06_struct_equality.a7`, `a7=0`, `zig=1`:
`error: operator == not allowed for type 'dm06_struct_equality.P'`.
`_types_are_comparable` (`a7/passes/type_checker.py:3053-3054`) returns True for
`left.equals(right)` on any two identical types, structs, arrays and slices
included. TYP-09 records the same for `b17_struct_eq`, `b18_array_eq`,
`b20_union_eq` and `d49_array_eq_literal`, and proposes exactly the fix below.

**Fix direction.** Either restrict `==` to types Zig can compare, or emit a
field-wise comparison. A field-wise `==` is a language addition and needs the
owner.

**Changes accepted programs?** No — no such program builds today.

### LNG-09. HIGH. KNOWN-family (ZIG-26, `backend.md:379`; ZIG-33, `backend.md:410`). New shape. Any format specifier other than a bare `{}` is passed through unchecked; there is no way to print a float with chosen precision

**Evidence.** `num07_float_precision.a7` writes `io.println("{:.2}", x)`.
`a7=0`; `zig=1` with
`Writer.zig:736:18: error: unused argument in '{{:.2}}'`. The A7 side counts
holes but does not read them: `mx05_format_garbage.a7` (`"{} {} {}"` with one
argument) and `mx06_too_many_args.a7` (`"{}"` with three) are both correctly
rejected with `Wrong number of arguments (io format string expects N values,
got M)`, so the count is checked and the content is not.

**What an ordinary program cannot do.** Print a money column, a percentage, or a
fixed-width table. `num08_float_print.a7` runs and prints `3.14159` — full
precision or nothing.

ZIG-26 records the checker counting any `{...}` as a placeholder while the
emitter treats `{x}` as literal text; ZIG-33 records `{{`. `{:.2}` is a third
shape of the same unvalidated-specifier root, and the one an ordinary program
reaches for first.

**Fix direction.** Validate the specifier against what the backend's writer
accepts, and define an A7 spelling for precision and width. No gate; the
nearest is P-BK (`execution.md:189`, ZIG-33).

**Changes accepted programs?** No — the rejected forms do not build.

### LNG-10. HIGH. NEW. Exhaustiveness is checked for enums only; six other match shapes pass A7 and fail Zig

**Evidence.** The enum check works and is precise:
`pm02_enum_exhaustive_missing.a7` exits 6 with
`Non-exhaustive match: Enum 'Color' missing case(s): Blue`. Redundancy is
checked too: `pm12_dup_case.a7` (`Unreachable code: redundant match pattern '1'`)
and `pm17_overlap_range.a7` (`covered by previous range pattern '1..10'`).

Everything else is unchecked:

| Probe | Shape | a7 | zig | Zig message |
| --- | --- | --- | --- | --- |
| `pm13_int_no_else.a7` | integer match, no `else` | 0 | 1 | `else prong required when switching on type 'comptime_int'` |
| `pm20_typed_int_no_else.a7` | `x: i32`, no `else` | 0 | 1 | `switch must handle all possibilities` |
| `pm14_match_expr_no_else.a7` | match *expression*, no `else` | 0 | 1 | `else prong required` |
| `pm16_range_desc.a7` | `case 10..4` | 0 | 1 | `range start value is greater than the end value` |
| `pm19_match_float.a7` | match on `f64` | 0 | 1 | `switch on type 'comptime_float'` |
| `pm08_match_string.a7` | match on `string` | 0 | 1 | `cannot switch on strings` |

**What an ordinary program cannot do.** Dispatch on a keyword string — the one
thing a text tool wants a match for. And it learns that a non-exhaustive integer
match is a mistake only from Zig.

**Fix direction.** Require `else` (or provable coverage) for every non-enum
scrutinee; reject descending ranges and float and string scrutinees in the
semantic pass with A7 diagnostics. Batch T6.

**Changes accepted programs?** No — none of the six builds today.

### LNG-11. HIGH. NEW. A struct field holding a slice cannot be filled from an array

**Evidence.** `dm05_struct_with_slice.a7`:
`S :: struct { data: []i32, n: usize }`, `S{data: a[0..3], n: 3}`. `a7=0`,
`zig=1`:

```
dm05_struct_with_slice.zig:21:24: error: expected type '[]i32', found '*const [3]i32'
    note: cast discards const qualifier
```

The slice expression lowers to a pointer to the array rather than a slice, and
to a `const` one. Combined with LNG-04 (a slice parameter cannot be indexed,
KNOWN S11) and `mx04_return_slice.a7` (returning `s[0..2]` exits 6,
`slice bounds are not proven`), slices are declarable and effectively unusable.
`grep -lE '\[\]' examples/*.a7` returns nothing, which matches.

**Changes accepted programs?** No.

### LNG-12. HIGH. NEW. A division whose divisor passes through a `cast` cannot be proved non-zero by any guard

**Evidence.**

| Probe | Shape | a7 |
| --- | --- | --- |
| `num04_signed_div.a7` | `a / 2` with `a: i32 = -7` | 0; runs, prints `-3 -1` |
| `num05_div_by_param.a7` | `a / b`, both parameters, no guard | 6 (correct) |
| `num06_div_guarded.a7` | `if b == 0 { ret 0 }` then `a / b` | 0, zig=0 — the guard works |
| `num11_int_to_float.a7` | `cast(f64, n) / cast(f64, d)`, `d: i32 = 2` | **6** |
| `num18_guard_shapes.a7` | early return `if c == 0 { ret 0.0 }` then the cast division | **6** |
| `num19_guard_ne.a7` | `if c != 0 { ret cast(f64,t) / cast(f64,c) }` | **6** |

All three rejections read
`Unsafe type cast (division/modulo divisor must be non-zero: divisor may be zero)`.
The guard that discharges the obligation on a bare variable (`num06`) does not
survive the cast. `num15_float_div_literal.a7` (`cast(f64, n) / 2.0`) compiles
and prints `3.5`, so it is the cast on the *divisor* that loses the fact.
Division by a field (`num20`), by an array element (`num21`) and by a call
result (`num22`) are all rejected too, correctly, since none can be proved.

**What an ordinary program cannot do.** Compute an average, a rate, or a
percentage from integer counts. There is no spelling that works.

**Fix direction.** Propagate the source value's interval through a
value-preserving cast in `a7/safety.py:522-575`. Batch SD (`execution.md:139`).

**Changes accepted programs?** No — it only accepts more.

### LNG-13. HIGH. KNOWN (VIS-4, `visibility-modules.md:162`). Confirmed still live

**Evidence.** `vis/gmod.a7` declares `pub identity($T) :: fn(value: $T) $T`;
`vis/gmain.a7` calls `g.identity(7)`. `a7=0`; `zig=1`:

```
gmain.zig:19:36: error: expected 2 argument(s), found 1
    __a7_stdout_print("{any}\n", .{module___gmod__identity(7)});
gmain.zig:14:5: note: pub fn module___gmod__identity(comptime T: type, value: T) T
```

The type argument is never inferred on the alias-qualified path (PIP-9). Note
the emitted format string is `{any}`, not `{}` — the call's result type is
unknown to the backend as well.

**Fix direction.** PIP-9's; `visibility-modules.md:581` records that no batch
owns it.

**Changes accepted programs?** No.

### LNG-14. HIGH. KNOWN (D3 `LEDG2:64`; TYP-04 `types.md:146`; PRD-34 `production-readiness.md:882`). Four of SPEC §7's own generic forms do not compile

**What works.** Declared generic functions and structs compile to Zig
`comptime T: type` parameters and run correctly. All of these are `a7=0`,
`zig=0`, built and run:

| Probe | Form | Output |
| --- | --- | --- |
| `g01_declared_infer.a7` | `identity($T) :: fn(value: $T) $T`, two call sites | `7 ok` |
| `g04_generic_over_struct.a7` | generic instantiated at a user struct | `1 2` |
| `g05_generic_struct.a7` | `Box($T) :: struct`, `Box(i32){...}` | `5` |
| `g06_chain.a7` | generic calling a generic | `9` |
| `g10_two_params.a7` | `pair($A, $B)` | `1` |
| `g11_nested_generic.a7` | `Box(Box(i32))` | `5` |
| `g14_generic_struct_param.a7` | `unwrap($T) :: fn(b: Box($T)) $T` | zig=0 |
| `g18_generic_mixed_widths.a7` | one generic at `i64`, `f64`, `bool` | `7 2.5 true` |

**Where specialization stops.** It does not stop, because A7 does not
monomorphize. `g01_declared_infer.zig:14,19-20` shows
`fn identity(comptime T: type, value: T) T` with call sites `identity(i32, 7)`
and `identity([]const u8, "ok")`. The specialization is Zig's.
`g06_chain.zig:18-19` threads the type argument through a call chain as
`inner(T, v)`. Constraint checking is real and runs in A7:
`g12_typeset_reject.a7` exits 6 with
`Generic constraint violation: Generic parameter '$T' requires Numeric, got string`.

What fails, all at codegen (exit 7) except where noted:

| Probe | Form, quoted from SPEC | Result |
| --- | --- | --- |
| `g02_inline_generic.a7` | `identity :: fn(x: $T) $T` — SPEC 7.1's primary spelling, `docs/SPEC.md:885-887` | `✗ 3:19: Zig backend: generic type requires an explicit generic environment` |
| `g07_ret_generic.a7` | a generic function returning `Box($T)` | same message |
| `g17_generic_union.a7` | `Result :: union { ok: $T, err: $E }` — `docs/SPEC.md:933-937` | same message |
| `g16_generic_enum.a7`, `eh01_spec_option.a7` | `Option :: enum { Some: $T, None }` — `docs/SPEC.md:928-932` | **exit 5**, `Expected IDENTIFIER, got COLON` (KNOWN C5) |
| `g08_typeset.a7` | `Numeric :: @type_set(i32, i64, f64)` used as a constraint — `docs/SPEC.md:949-957` | `✗ 3:12: Zig backend: unsupported expression node 'TYPE_SET'` (PRD-34) |
| `g03_explicit_inst.a7` | `identity(i32)(7)` | exit 6, `Unexpected AST node kind: Unknown expression kind: NodeKind.TYPE_PRIMITIVE` |
| `g15_generic_slice_param.a7` | `first :: fn(arr: []$T) $T` — `docs/SPEC.md:901-903` | exit 6, bounds proof (LNG-04) |

A predefined set name works where a user-declared one does not:
`g09_predef_typeset.a7` (`addup($T: Numeric)` with no `Numeric` declared in the
file) is `a7=0`, `zig=0`.

**Changes accepted programs?** No.

### LNG-15. HIGH. KNOWN (SAF-21, `safety.md:423-428`). New manifestation. An array whose size comes from a `::` constant cannot be indexed at all

**Evidence.** `N :: 4; buf: [N]i32; buf[0] = 1` — `ct02_const_array_size.a7`
exits 6 with `index must satisfy 0 <= index < len: index bounds are not proven`
for the literal index `0`. The same array with a literal size
(`dm01_literal_array.a7`) is `a7=0`, `zig=0`, and prints `1`.

`ct03_const_in_type_global.a7` (`Grid :: [N][N]i32`) and
`ct05_const_expr_in_bound.a7` (`[N * 3]i32`) fail the same way.
`ct07_comptime_fn.a7` (`N :: double(4)`) also fails — a function call in a
constant initialiser is accepted by the type checker and leaves the length
unknown.

Constants themselves fold: `ct01_const_fold.a7` (`A :: 10; B :: A * 2;
C :: B + A`) runs and prints `30`; `ct04_const_string.a7` and
`ct06_local_const.a7` run.

**What an ordinary program cannot do.** Give a buffer a named capacity. Every
size and every bound has to be a repeated literal, as `ps02`→`ps03` had to do:
`MAX_RECORDS :: 8` declared, then `8` written out at four call sites.

SAF-21 names the mechanism: `_visit_decl` stores facts for globals
(`a7/safety.py:295-298`) but every FUNCTION starts with
`self.facts.by_symbol = {}` (`:290`), so a file-scope `::` constant is unknown
inside any function. SAF-21's probe is `N :: 4; y := 10 / N`; the array-length
manifestation is the one an ordinary program hits, and SAF-21's fix covers both.

**Fix direction.** SAF-21's: seed `::` constant facts per function. Batch C4
(`execution.md:119`).

**Changes accepted programs?** No.

### LNG-16. HIGH. NEW. A file with no `main` compiles with exit 0

**Evidence.** `mx07_no_main.a7` contains only an import and `helper`. `a7=0`;
the emitted `mx07_no_main.zig` is 35 bytes and is the body of `helper` alone —
no `main`, no `__a7_user_main`. This is what makes LNG-01 silent: the compiler
has no notion of an entry point to miss.

**Fix direction.** Require an entry point in `compile` mode, or say in the
diagnostics that none was emitted.

**Changes accepted programs?** Yes — a library-shaped `.a7` file compiled with
`--mode compile` would start failing. Needs approval; the decision belongs with
gate G6's `a7 build` / `a7 run` commands (`docs/plan/README.md:240-246`).

### LNG-17. MEDIUM. NEW. A `ref $T` parameter is immutable, so SPEC 7.1's `swap` is rejected while the non-generic form works

**Evidence.** `g13_generic_ref_swap.a7` is SPEC 7.1's own example
(`docs/SPEC.md:876-882`) verbatim. Exit 6:
`Cannot assign to immutable binding: 'a' is immutable [line 5: col 5]`.
`g19_nongeneric_ref_assign.a7` (`set100 :: fn(value: ref i32) { value = 100 }`)
is `a7=0`, `zig=0`, runs and prints `100`. So `ref T` is assignable and
`ref $T` is not.

**Changes accepted programs?** No.

### LNG-18. MEDIUM. KNOWN (TYP-11, `types.md:274`). A partial struct literal is accepted and Zig rejects it

**Evidence.** `dm10_partial_init.a7`: `P :: struct { x: i32, y: i32 }`,
`p := P{x: 1}`. `a7=0`, `zig=1`, `error: missing struct field: y`. There is no
zero-fill and no diagnostic.

**Fix direction.** TYP-11's: validate struct literals against the declared
field list. Completeness here is gate G5 (`types.md:274`).

**Changes accepted programs?** No.

### LNG-19. MEDIUM. NEW for arrays; KNOWN S12 for strings. `.len` works on neither an array nor a string, contradicting SPEC 3.3

**Evidence.** `docs/SPEC.md:259` states `T.len // Number of elements (compile-time
constant)` for arrays and `:276` `slice.len // Number of elements (usize)`. `bd08_len_bound.a7` (`a: [4]i32`, `a.len`) exits 6 with
`Cannot access field on non-struct type: got '[4]i32'`. `st03_len.a7`
(`a: string`, `a.len`) exits 6 with the same error naming `string`.

Consequence: a function that takes a fixed array or a string cannot ask how long
it is, which is why `examples/034_string_utils.a7:5-13` counts characters in a
loop and stops on `'\0'` — a sentinel that a Zig `[]const u8` does not carry.

**Changes accepted programs?** No.

### LNG-20. MEDIUM. NEW. Printing a `[]char` prints a list of numbers

**Evidence.** `st14_print_slice.a7` (`p := a[1..3]; io.println("{}", p)`) is
`a7=0`, `zig=0`; built and run it prints `{ 98, 99 }`. Printing the characters
one at a time (`st05_slice.a7`) prints `bc`.
`st13_slice_of_string_as_string.a7` shows why there is no third option:
`p: string = a[1..3]` exits 6 with
`Type mismatch: expected 'string', got '[]char'`.

**What an ordinary program cannot do.** Print a substring.

**Changes accepted programs?** Yes — a program that prints a `[]char` today
prints numbers and would start printing text. Needs approval.

### LNG-21. MEDIUM. KNOWN (TYP-20, `types.md:439`). New trigger. An integer literal is not accepted where `usize` is expected in an argument or a return

**Evidence.** `pick :: fn() usize { ret 9 }` exits 6 with
`Return type mismatch: expected 'usize', got 'i32'`
(`bd12_guard_from_call.a7`, first run). `get(a, 1)` where the parameter is
`usize` exits 6 with `Argument type mismatch: expected 'usize', got 'i32'
(Argument 2)` (`bd13_guard_from_param.a7`, first run). Both compile after
`cast(usize, ...)`.

`CLAUDE.md` states "non-negative integer literals are still accepted for simple
indexing", which is true of `a[0]` and false of every other `usize` position.
`ps03_bounds_tool.a7` needed `cast(usize, 0)` in four loop headers.

**Changes accepted programs?** Yes — accepting the literal accepts more. Needs
approval only if the owner wants the current strictness kept; it sits under
gate G3 (`docs/plan/README.md:143`).

### LNG-22. MEDIUM. KNOWN (PAR-04, via SAF-22 `safety.md:435-437`, which generalises KNOWN D7). New scale. Most type errors carry no line or column

**Evidence.** `ps01_naive_tool.a7` produced 17 semantic errors. Read back as
JSON, 16 of the 17 messages are of the form
`ps01_naive_tool.a7: Operator requires compatible types (ge between char and char)`
with no `line:col` prefix; exactly one carries `ps01_naive_tool.a7:59:9`. The
console renderer therefore prints them with no source excerpt. On a file of a
few hundred lines that is 16 errors the user cannot locate.

SAF-22 records the root: "Division diagnostics have no line because BINARY
nodes have no span (PAR-04; generalizes KNOWN D7's 'no line')"
(`safety.md:435-437`). The scale is what is new — 16 of 17 errors on one
ordinary file.

**Fix direction.** PAR-04's: give BINARY nodes a span.

**Changes accepted programs?** No.

### LNG-23. MEDIUM. KNOWN (B6, ZIG-3, evidence map row 65). A mutable global without a type annotation emits Zig that does not build

**Evidence.** `mx08_global_var.a7` (`counter := 0`, incremented in a function):
`a7=0`, `zig=1`,
`error: variable of type 'comptime_int' must be const or comptime`.

**Fix direction.** ZIG-3's, batch P-BK.1 (`execution.md:189`).

**Changes accepted programs?** No.

### LNG-24. MEDIUM. NEW. No string concatenation and no way to build text at run time

**Evidence.** `st06_concat.a7` (`a + b` on two strings) exits 6 with
`Requires numeric type`. There is no other spelling:
`a7/stdlib/__init__.py:11-16` registers only `io` and `math`;
`a7/stdlib/string.py` is a stub (see `docs/audits/2026-09-18/stdlib.md`). A
`[N]char` buffer can be filled and printed one character at a time
(`st07_build_buffer.a7` runs, prints `hi`), and that is the whole of text
construction.

**Fix direction.** A `string` concatenation needs an allocator and an ownership
rule, so it belongs with the owning-string work (`docs/STATUS.md:38-39`) and
track 8a/8b, not with the operator.

**Changes accepted programs?** No — `a + b` on strings is rejected today.

### LNG-25. MEDIUM. NEW. Match guards are not parsed, and the error lands two lines past the cause

**Evidence.** `pm05_guard.a7` (`case v if v > 3:`) exits 5 with
`Unexpected token 'else' after parsing complete program [line 7: col 9]`; the
guard is on line 6. SPEC does not claim guards, so their absence is a gap, not
drift; the misplaced diagnostic is the defect.

**Fix direction.** Report the parse failure at the `if` token. Adding guards
themselves is a syntax decision with no owner.

**Changes accepted programs?** No.

### LNG-26. MEDIUM. KNOWN (ZIG-38 `backend.md:83`; SAF-11 `safety.md:266`; ledger L5). Integer overflow and shifts are emitted raw, with no proof and no diagnostic

**Evidence.** `num10_overflow_emit.a7` (`add :: fn(a: i32, b: i32) i32 { ret a + b }`)
is `a7=0`, `zig=0`, and `num10_overflow_emit.zig:14` emits `return (a + b);` —
the plain operator, not `+%` and not `@addWithOverflow`. `num13_shift.a7`
emits `(n << 4)` the same way (`num13_shift.zig:15`). Under `-ODebug` a Zig
integer overflow panics; under `-OReleaseFast` it is undefined behaviour
(INFERENCE from Zig semantics, matching `backend.md:235`). A7 says nothing at
any stage: `a7/safety.py:631` `_prove_integer_overflow` is dead behind an early
`return` (evidence map row 68).

Ledger L5 locks wrapping semantics but nothing implements them, so what a
program does on overflow today is decided by the Zig build mode, not by A7.

**Fix direction.** Batch Z7 plus the P3 deferral (`execution.md:201,458`);
gate G3 (`docs/plan/README.md:143-170`).

**Changes accepted programs?** Yes — emitting a checked or wrapping operator
changes the behaviour of every program that overflows today. Needs approval,
and L5 is the ledger entry that carries it.

### LNG-27. LOW. NEW. Explicit instantiation reports an internal node kind

**Evidence.** `g03_explicit_inst.a7` (`identity(i32)(7)`) exits 6 with
`Unexpected AST node kind: Unknown expression kind: NodeKind.TYPE_PRIMITIVE`.
The form is not in SPEC, so rejection is right; the message names a compiler
internal.

**Fix direction.** Map the node kind to a user-facing message, or say that
explicit instantiation is not a form.

**Changes accepted programs?** No.

### LNG-28. LOW. NEW. A declaration named after a type keyword is misreported once recovery takes over

**Evidence.** `mx01_keyword_fn_name.a7` (`f64 :: fn(x: i32) i32`) exits 5 with
`Unexpected token 'f64' after parsing complete program [line 3: col 1]`, which
is right. In a longer file the diagnostic moves: in `sc01_500line.a7` before it was
renamed, a function called `f64` among 120 others produced
`Already defined: Variable 'y' [line 517: col 5]` — a name collision reported
inside an unrelated function 400 lines away. That LNG-01's recovery is the
mechanism is INFERENCE; I did not dump the AST for that file.

**Fix direction.** Falls out of LNG-01's fix.

**Changes accepted programs?** No.

### LNG-29. LOW. KNOWN (evidence map row 91). Every destructuring spelling other than LNG-01's fails at parse

**Evidence.** The rest of the family, for completeness:

| Probe | Source | Exit | Message |
| --- | --- | --- | --- |
| `mr02` | `a, b, c: i32 = 1, 2, 3` | 5 | `Unexpected token 'io' after parsing complete program [line 5]` |
| `mr03` | `A, B :: 1, 2` (top level) | 5 | `Expected declaration` |
| `mr04` | `fn(a, b) (i32, i32)` | 5 | `Expected function body after function signature` |
| `mr05` | `ret a, b` | 5 | `Expected expression` |
| `mr06` | `x, y = 1, 2` (assignment) | 5 | `Unexpected token 'io' after parsing complete program` |
| `mr07` | `x, y := p` (from a struct) | 6 | `Undefined type (Identifier 'p')` |
| `mr11` | `x, y := 10, 20` at top level | 5 | `Unexpected token 'x' after parsing complete program` |

The current form is a struct return, and it works: `b4`, `b6` and `mr08`'s shape
all compile. `mr10_anon_struct_ret.a7` shows SPEC 6.1's anonymous struct return
type (`fn(x: f64) struct { s: f64, c: f64 }`) is also `a7=0`, `zig=0`.

**Fix direction.** None until the syntax is decided; packet P-parsed
(`execution.md:407,469`). `docs/SPEC.md:421-423` already marks the form planned,
so the docs are not drifting here.

**Changes accepted programs?** No.

---

## Feature 3 in full: what a fallible function can return today

Probed exhaustively; the answer is one form.

| Form | Probe | Result |
| --- | --- | --- |
| Struct with an `ok` flag | `b6.a7`, `eh11_rename.a7` | **works** — `a7=0`, `zig=0`; the caller writes `if r.ok { ... } else { ... }` |
| Untagged union | `eh03`, `examples/016_unions.a7` | declarable and constructible; **there is no way to ask which field is live**. Reading the wrong field is accepted with no diagnostic |
| `union(tag)` | `eh04_tagged_union.a7` | parses and compiles (`a7=0`, `zig=0`) but the tag is inert; `docs/SPEC.md:340-350` says tag inspection "is reserved syntax and is not implemented yet" |
| `match` on a union | `eh05`, `eh06` | exit 6: `match pattern 'err' is unreachable because a previous wildcard pattern covers all values` — the first `case ok:` is read as a capture of the whole union (KNOWN B2), so the second arm is dead |
| Generic `Option` / `Result` | `eh01`, `eh02`, `eh10` | SPEC 7.2's own text: the enum form exits 5 at parse, the union form exits 7 at codegen |
| Enum with a payload | `eh01` | not parsed — `Expected IDENTIFIER, got COLON` |
| Enum with explicit values as a status code | `eh09_enum_payload.a7` | `a7=0`, `zig=0` — works, but carries no value |
| `nil` sentinel through `ref T` | `eh08_nil_return.a7` | exit 6: `Return type mismatch: expected 'ref P', got 'P'` — a local cannot be returned as a reference |

**What the compiler does with an unhandled case.** Nothing. There is no
construct that forces a caller to look at the flag, no `assert`, no `panic`
(SPEC 11.2 lists all three at `docs/SPEC.md:1616-1619` and `:1580` marks
the whole list "planned API shape, not current implementation"), and no defined
run-time stop (`docs/plan/audit/language-audit-checklist.md:82`, gate M39).
Ignoring the `ok` flag and reading the value is silently accepted.

---

## What is missing

Ordered by how often an ordinary program hits it.

| # | Item | What exists now | What it needs | Decision owner | Priority for v1 |
| --- | --- | --- | --- | --- | --- |
| 1 | Character operations | `==` and `!=` only (LNG-02) | Ordering and integer conversion for `char`, or the SPEC 11.2 `char_is_*` / `char_to_*` family | none; nearest track 8b | P0 |
| 2 | Indexing by a computed value | Literal and loop-tracked indices only (LNG-04) | A guard rule in the fact domain for parameters, fields and call results | batch SD / P7 `execution.md:139,462` | P0 |
| 3 | String equality and ordering | Emits Zig that does not build (LNG-07) | A content comparison in the backend, or `str_compare` in the registry | P0b.9 `packets/P0b-unsafe-programs.md:37` | P0 |
| 4 | Input of any kind | `print`, `println`, `eprintln` (`a7/stdlib/io.py:1-26`); no args, no stdin, no files, no env | An argument and stdin surface | packet **P9** `execution.md:464`; env has no owner (`checklist:80`) | P0 |
| 5 | Parse a number from text, format a number into text | Impossible in both directions (LNG-02, LNG-24) | `str_to_int` / `int_to_str`, or the char operations that let a user write them | track 8b, no batch | P0 |
| 6 | Multi-file programs | One function per imported file (LNG-03) | PIP-6's rename fix | none named (`visibility-modules.md:603`) | P0 |
| 7 | Named capacities | A `::` constant as an array size makes the array unindexable (LNG-15) | Constant folding before the length interval is read | batch SD | P1 |
| 8 | A fallible return | A hand-checked `ok` flag | A decision on `Option`/`Result`: library type, language type, or neither | gate **G5** `docs/plan/README.md:211`; packet P10 `execution.md:465` | P1 |
| 9 | Exhaustiveness for non-enum matches | Unchecked; six shapes fail in Zig (LNG-10) | An A7-side check, and rejection of float/string/descending-range patterns | batch T6 | P1 |
| 10 | Arrays of structs | Emits `[_]P{0} ** N` (LNG-06) | A recursive zero value or `undefined` | none named | P1 |
| 11 | Float formatting | `{:.2}` passes A7 and fails Zig (LNG-09) | A validated specifier grammar | P-BK `execution.md:189` | P1 |
| 12 | Averages and rates | A cast on the divisor loses the non-zero fact (LNG-12) | Interval propagation through value-preserving casts | batch SD | P1 |
| 13 | Definite assignment | Scalars silently zeroed, aggregates `undefined` (LNG-05) | One documented rule, or a check | gate **M34** (`edge-cases/03-definite-assignment.md:3`) | P1 |
| 13b | A defined answer for integer overflow | Raw `+` and `<<`; Debug panics, ReleaseFast is undefined (LNG-26) | Wrapping, checked or saturating lowering per ledger L5 | batch Z7 + P3 `execution.md:201,458`; gate **G3** | P1 |
| 14 | Usable slices | Not indexable, not returnable, not storable in a struct (LNG-11, S5, S11) | The bounds work of item 2 plus a slice lowering fix | track 5 `docs/plan/README.md:326-357`; P0b.5 | P1 |
| 15 | `.len` | Rejected on arrays and strings (LNG-19) | Implement the SPEC 3.3 property | none | P2 |
| 16 | Substrings as text | `a[1..3]` is `[]char` and prints as numbers (LNG-20) | A `[]char`→`string` view or a text print rule | packet P10 | P2 |
| 17 | Sorting | Hand-written sorts work (`examples/029_sorting.a7`, `ps03`) | Nothing blocking; a library sort needs item 2 and a comparator over slices | not in plan (`checklist:69`) | P2 |
| 18 | Generic composites | Inline `$T`, generic unions and generic enums fail (LNG-14) | The codegen work behind TYP-04 | batch T7; `docs/STATUS.md:35` | P2 |
| 19 | Compile-time evaluation beyond folding | `::` folds arithmetic across declarations; a call in a constant is accepted and yields nothing usable (`ct07`) | A decision on whether A7 has comptime code at all | none | P2 |
| 20 | An entry-point rule | None; a file with no `main` exits 0 (LNG-16) | A rule, tied to `a7 build` / `a7 run` | gate **G6** `docs/plan/README.md:240-246` | P2 |
| 21 | Match guards | Not parsed (LNG-25) | A syntax decision | none | P3 |
| 22 | Multiple returns and destructuring | Not parsed; one spelling deletes the program (LNG-01, LNG-29) | A syntax decision, after LNG-01's fix | P-parsed `execution.md:407,469` | P3 |

---

## Checked and correct

Each ran to a correct answer unless noted.

- **Generics in the declared-parameter form.** Eight probes, listed under
  LNG-14. Inference from arguments, two type parameters, a generic over a user
  struct, a nested instantiation, a generic calling a generic, and one generic
  used at `i64`, `f64` and `bool` all produce correct output. Constraint
  violations are rejected in A7 with a clear message (`g12`).
- **Pattern matching.** `pm01` (literal, multi-value, range and `else` in one
  match) prints `0 1 2 3`. `pm03` match-as-expression prints `20`. `pm04`
  identifier capture prints `100 6`. `pm06` `fall` prints `one` then `two`.
  `pm07` match on a call result prints `two`. `pm09` nested match prints `1,2`.
  `pm10` match on `char` prints `b`. `pm11` match on `bool` with both arms and no
  `else` compiles. `pm21` correctly rejects `fall` in the final case. Enum
  exhaustiveness (`pm02`), duplicate patterns (`pm12`) and range-covered
  patterns (`pm17`) are all rejected with precise messages.
- **Structs.** Nested structs (`dm04`, prints `5 1`), value-copy semantics
  (`dm07`, prints `1 2` — assignment copies), an array field inside a struct
  (`dm11`, prints `9`), an array of structs written with an explicit literal
  list (`dm03`, prints `2`), and struct returns (`b4`, `b6`).
- **Bounds proofs that should pass.** `bd01`–`bd05`, `bd07`: local arrays,
  struct-field arrays reached directly and through `ref`, and fixed-array
  parameters, all indexed by loop counters against literal bounds.
- **Numerics.** Explicit casts (`num02`, prints `3`). Signed division and
  remainder on a negative value (`num04`, prints `-3 -1` — truncating, matching
  Zig). Float comparison (`num09`, prints `true false`). Float printing without a
  specifier (`num08`, prints `3.14159`). Shifts and bitwise operators emit
  (`num13`). A `usize`/`i32` mix is correctly rejected at the call site
  (`num17`). **Not in this list:** mixed-width `i32 + i64` (`num16`) compiles,
  builds and prints `3`, but that acceptance is KNOWN TYP-07 (`types.md:218`) —
  implicit widening beyond SPEC A.2. Zig 0.16 happens to build it; SPEC does not
  permit it.
- **Division guards without a cast.** `num05` is correctly rejected and `num06`
  correctly accepted.
- **Format-string arity.** `mx05` and `mx06` are both rejected with the counts
  named.
- **`defer`** runs after the body (`mx02`, prints `start` then `done`).
- **`for i, value in`** yields a `usize` index (`mx03`, prints `0 7 | 1 8 | 2 9`).
- **Compile-time constant folding** across declarations (`ct01`, prints `30`),
  string constants (`ct04`), local `::` constants (`ct06`), typed immutables
  (`ct08`).
- **Unimplemented intrinsics are rejected honestly.** `ct09` (`@size_of`) exits 6
  with `Intrinsic '@size_of' is parsed for future support but is not implemented
  in the Zig backend yet`.
- **Scaling.** `sc01_500line.a7` — 1087 lines, 120 functions, a 120-call chain in
  `main` — compiles in 140 ms (437 ms wall including process start), `zig=0`.
  TYP-03's 50-second case does not reproduce; V1 holds.
- **A real program does run.** `ps03_bounds_tool.a7` (150 lines: a record struct,
  a report struct, a hand-written digit parser, a bubble sort over an array of
  structs, an enum grade, a match, and a printed table) compiles, builds under
  both `-ODebug` and `-OReleaseFast`, and prints the same correct report from
  both.

## Test gaps

- **Zig acceptance is checked at six call sites in the whole suite**
  (`test/test_codegen_zig.py:430,672,704,1120` through `zig_build_check`;
  `test/test_compound_assignment_types.py:151`;
  `test/test_float_nonfinite_folding.py:189`). Everything else stops at
  `zig ast-check`, which parses without analysing. Fourteen of the 28 findings
  here are "A7 exits 0, Zig rejects", and none falls inside that slice.
- **No test for `char` beyond tokenizing and casting.** 19 test files mention
  `char`; `grep -n "'a'.*<\|char.*>=" test/*.py` finds no ordering test and no
  `is_digit`-shaped test. The whole LNG-02 surface is untested in both
  directions.
- **No test for destructuring.** `grep -ln 'destructur\|, y :=' test/*.py`
  returns nothing, so LNG-01's worst shape has no regression test even though
  PAR-03 and PRD-33 both record it.
- **No test for exhaustiveness outside enums.** `grep -ln exhaust test/*.py`
  matches two files; neither covers an integer, float, string or bool
  scrutinee.
- **No test for an array of structs, a struct containing a slice, or struct
  equality.** `grep -n '\[3\]P\|array of struct' test/*.py` returns nothing.
- **No test for a `::` constant as an array size** (LNG-15), for a bounds guard
  (LNG-04), or for a cast on a divisor (LNG-12) — the three defects that stop an
  ordinary program soonest after the character ones.
- **No test asserts that a program has an entry point** (LNG-16).
- **No test mentions integer overflow or wrapping** (LNG-26). The checklist
  already records this (`docs/plan/audit/language-audit-checklist.md:75-76`);
  it is still true.

## Not verified

- Which call site drops the span on `REQUIRES_NUMERIC_TYPE` and
  `OPERATOR_TYPE_MISMATCH` errors (LNG-22). The two `add_type_error` calls at
  `a7/passes/type_checker.py:1231,1255` pass `node.span`; the loss is elsewhere
  and I did not trace it.
- Whether the `{any}` format string in LNG-13's output is specific to the
  alias-generic path or a general fallback for unknown types.
- Whether `ps04`'s module split hides further defects behind LNG-03. The first
  Zig error stops the build.
- Whether the examples corpus and the test suite contain other programs that
  compile to Zig that does not build. I probed only my own files; the
  examples-and-tests audit owns that question. `examples-tests.md` and
  `design-gaps.md` landed while these probes were running and were not read, so
  nothing here is cited from them or checked against them.
- `-OReleaseFast` behaviour of the uninitialised-struct read (LNG-05). I ran only
  `-ODebug` for `dm09`; running an optimised undefined read is not worth the
  risk.

---

## The smallest set of additions that would let someone write a useful 500-line program

The target: a text tool that reads arguments, parses numbers, sorts results and
prints a report. Six things, in the order the tool hits them. Everything else on
the missing list can wait.

1. **Argument access.** Today a program cannot receive a single byte of input:
   `a7/stdlib/__init__.py:11-16` registers `io` and `math` and nothing else, and
   `io` is three print functions. Packet P9 owns this. Without it the tool has to
   have its data compiled in, which is what `ps03_bounds_tool.a7` does.
2. **`char` ordering and `char`↔integer conversion** (LNG-02). Without it there
   is no `is_digit`, no `to_lower`, and no way to turn `'7'` into `7`. The
   enumerate-every-character workaround costs about 30 lines per predicate and
   does not scale past digits.
3. **String equality** (LNG-07). Without it the tool cannot match a flag, group
   by a key, or deduplicate. It compiles today and does not build.
4. **An index guard that discharges the bounds obligation** (LNG-04). Without it
   the tool cannot append at a stored length or read at a computed offset, so it
   cannot have a growable result list at all. This is the difference between
   `ps02_workaround_tool.a7` (rejected) and `ps03_bounds_tool.a7` (accepted, but
   rewritten to scan the full capacity on every operation).
5. **Named capacities** (LNG-15) and **arrays of structs** (LNG-06). Together
   these are what a record table is made of. Today `MAX :: 64` cannot size an
   indexable array and `recs: [64]Record` does not build.
6. **Number formatting with a chosen precision** (LNG-09), paired with the
   cast-through-divisor fix (LNG-12). A report of integers prints fine; a report
   with a mean or a percentage can neither be computed nor printed.

Two things are *not* on the list, and both are worth saying plainly. **Sorting is
not missing**: `examples/029_sorting.a7` and `ps03_bounds_tool.a7:75-90` both
sort by hand, and the second sorts an array of structs by a field. The
checklist's row 2 ("No sorting anywhere",
`docs/plan/audit/language-audit-checklist.md:69`) is about the stdlib, not about
what a program can do. **Generics are not blocking either**: the declared form
works end to end, and a 500-line tool does not need the four SPEC forms that
fail.

With items 1–6 the tool is writable. Without item 1 it is a demo; without items 2
and 3 it is not a text tool.

claims checked: 131
