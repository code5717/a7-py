# Stdlib, builtins and intrinsics audit — 2026-09-18

Component prefix `STD`. Audited tree: `/home/cx89/Projects/pl-dev/a7-py` at
`master` plus the uncommitted batches C3, PR-00, T0, V1, NOREC-0 and PL-02. Batch
C2 (worktree `/home/cx89/Projects/pl-dev/a7-wt/r1a-c2`) is **not** in this tree;
where it already fixes something, this report says so and cites
`tmp/reports/r1a-c2-impl.md` instead of re-finding it.

Environment: `zig 0.16.0` (`tmp/audit/2026-09-18/stdlib/env.txt`). 73 probes under
`tmp/audit/2026-09-18/stdlib/p/`, outputs under `.../out/`, driver `.../run.sh`
(`uv run a7 <p>.a7 --output <out>.zig`, then `zig build-obj -fno-emit-bin` in the
output directory; run-allowed probes additionally `zig build-exe -ODebug`).

The callable stdlib is 14 functions: `io.print`, `io.println`, `io.eprintln`, and
eleven `math.*` names that each lower to a Zig `@` builtin. Everything else in
SPEC 11.2 — strings, ASCII, memory, assertions, allocation — is prose. Of the 14
gaps in the "What is missing" table, five (number parsing, number formatting,
ASCII classification, sorting, assertions) have **no** owning gate, track or
packet in `docs/plan/README.md` or `docs/plan/execution.md`.

Most defects in the stdlib call path were already found by the 2026-09-16 compiler
audits. This audit adds eight that were not, and sharpens TYP-19 with a probe
showing a program that A7 accepts *and* Zig builds.

## Summary

| Severity | NEW | KNOWN | Total |
|---|---|---|---|
| CRITICAL | 0 | 2 | 2 |
| HIGH | 0 | 2 | 2 |
| MEDIUM | 4 | 3 | 7 |
| LOW | 4 | 3 | 7 |
| **Total** | **8** | **10** | **18** |

Both CRITICAL findings are closed in C2's worktree but live in the tree audited
here.

## 1. The exact current surface

Built from `a7/stdlib/__init__.py:11-16` (`STDLIB_MODULE_ALIASES`),
`a7/stdlib/io.py:10-24`, `a7/stdlib/math.py:11-41`, the type checker's
`_visit_stdlib_module_call` (`a7/passes/type_checker.py:1436-1454`), and the Zig
backend (`a7/backends/zig.py:2176-2218` for io, `:1634-1640` for math). Every row
was confirmed by probe.

### Import paths that resolve

| Spelling | Result | Probe |
|---|---|---|
| `io :: import "std/io"` | ok | `s01_surface_io.a7`, a7=0, zig=0 |
| `io :: import "io"` | ok | `s04_bare_io.a7`, a7=0, zig=0 |
| `math :: import "std/math"` / `"math"` | ok | `s02_surface_math.a7`, `s04`, a7=0, zig=0 |
| any alias, e.g. `console :: import "std/io"` | ok | `s03_alias_io.a7`, a7=0, zig=0 |
| `import "std/mem"` / `"std/string"` | exit 6, "Module … not found in search paths" | `s09_std_mem.a7`, `s10_std_string.a7` |
| `using import "std/io"` | exit 5, "Expected declaration" | `s06_using_import.a7` |
| `import "std/math" { sqrt }` | parses; `sqrt` undefined, exit 6 | `s07_named_import.a7` |
| no import, bare `io.println(...)` | exit 6, "Undefined type (Identifier 'io')" | `s11_noimport_io.a7` |
| no import, bare `math.sqrt(...)` | exit 6 | `s12_noimport_math.a7` |

`io`/`std/io` and `math`/`std/math` are *public import paths*, not member
spellings: the alias you bind is the only way to call. There is no bare
`println`: `println("x")` is exit 6, "Undefined type (Identifier 'println')"
(`s05_bare_println.a7`).

### Functions and their Zig lowering

| A7 call | Zig emitted | Probe |
|---|---|---|
| `io.print(fmt, …)` | `__a7_stdout_print(fmt, .{…})` | `s01`, `out/s01_surface_io.zig:21-22` |
| `io.println(fmt, …)` | same helper, `\n` appended to the literal | `out/s01_surface_io.zig:23-24` |
| `io.eprintln(fmt, …)` | `__a7_stderr_print(fmt + "\n", .{…})` | `out/s01_surface_io.zig:25` |
| `math.sqrt(x)` | `@sqrt(x)` | `out/s02_surface_math.zig:15` |
| `math.abs` / `floor` / `ceil` | `@abs` / `@floor` / `@ceil` | same line |
| `math.sin` / `cos` / `tan` | `@sin` / `@cos` / `@tan` | `out/s02_surface_math.zig:16` |
| `math.log` / `exp` | `@log` / `@exp` | `:17` |
| `math.min(a,b)` / `max(a,b)` | `@min` / `@max` | `:18` |

3 io + 11 math = 14 callables, and that is the whole surface. The print helper is
generated per stream in `_emit_preamble` (`a7/backends/zig.py:162-175`): a
1024-byte stack buffer, `std.Io.File.<stream>().writerStreaming(...)`, `print`
then `flush`, `@panic` on either failure.

### The typed math spellings (`sqrt_f32`, `sqrt_f64`, …)

`a7/stdlib/math.py:33-41` registers 22 bare names (11 functions × `_f32`/`_f64`)
through `registry.register_builtin`. **No user can call them.** `sqrt_f64(9.0)`
with no declaration is exit 6, "Undefined type (Identifier 'sqrt_f64')"
(`s08_typed_builtin.a7`) — the type checker never consults the builtin table. The
only effect of the table is the hijack in STD-1. KNOWN as PIP-23
(`docs/audits/2026-09-16/compiler/pipeline.md:455-464`); C2 deletes the table
(`tmp/reports/r1a-c2-impl.md` §1).

### `@`-forms the tokenizer and parser recognize

`a7/tokens.py:806-817` (`_tokenize_builtin`) turns `@` plus any run of
`[A-Za-z0-9_]` — including none, and including digits only — into a `BUILTIN_ID`.
The parser consumes `BUILTIN_ID` in four places: `parse_type_set` (`:683`), a type
position (`:768`), a loop-label prefix before `for`/`while` (`:992`), and
`parse_builtin_intrinsic` from a primary expression (`:1684`, `:1787`).

| Form | Status | Probe / evidence |
|---|---|---|
| `@type_set(T, …)` as an inline generic constraint | **implemented and enforced** | `i_typeset_ok2.a7` a7=0 zig=0; `i_typeset_bad2.a7` exit 6 "Generic constraint violation" |
| `Ints :: @type_set(i32, i64)` (named alias, SPEC:951-955) | type-checks, **codegen rejects**: exit 7 "unsupported expression node 'TYPE_SET'" | `i_typeset_alias_only.a7` — STD-10 |
| `@type_set(...)` in value position | exit 7, same message | `i_typeset_expr.a7` |
| `@size_of`, `@align_of`, `@type_id`, `@type_name` | parsed-only, exit 6 "Intrinsic '…' is parsed for future support but is not implemented in the Zig backend yet" | `i_size_of.a7`, `i_align_of.a7`, `i_type_id.a7`, `i_type_name.a7` |
| `@unreachable`, `@likely`, `@unlikely` | parsed-only, same message | `i_unreachable.a7`, `i_likely.a7`, `i_unlikely.a7` |
| `@anything_at_all(...)` | **same "parsed for future support" message** | `i_garbage.a7` — STD-9 |
| `@1(2)` | same message for `@1` | `i_at_digit.a7` — STD-9 |
| `@()` | same message for `@` | `i_at_bare.a7` — STD-9; lexing part KNOWN TOK-09 |
| `@foo` without `(` | exit 5, "Expected LEFT_PAREN" | `i_at_noparen.a7` |
| `@label for …` / `break label` | implemented | `i_label.a7`, a7=0 zig=0 |

CLAUDE.md's Docs Accuracy rule ("intrinsics other than `@type_set` are
parsed-only") is **verified correct** for inline `@type_set` constraints, with one
caveat: the SPEC 7.3 named-alias form of `@type_set` is *not* usable end to end
(STD-10).

## 2. SPEC 11.2, function by function

SPEC 11.2 (`docs/SPEC.md:1578-1580`) does label the block "planned API shape, not
current implementation", so the SPEC itself is honest. Status of each listed name:

| SPEC 11.2 name | Registered? | Reachable from A7? | Verdict |
|---|---|---|---|
| `abs_i32`, `abs_i64`, `min_i32/i64`, `max_i32/i64` | no | no | documentation only |
| `abs_f32/f64`, `min_f32/f64`, `max_f32/f64` | yes (`math.py:33-41`) | no (`s08`) | registry-only, unreachable |
| `sqrt_f32/f64` | yes | no (`s08`) | registry-only, unreachable |
| `pow_f32/f64` | no | no — `math.pow` is exit 6 (`m08_unknown_fn.a7`) | documentation only |
| `sin_f64`, `cos_f64`, `tan_f64` | yes (`_f32`/`_f64` loop) | no | registry-only, unreachable |
| `print :: fn(s: string)` | — | `io.print(fmt, …)` exists but takes a **format literal**, not a value | different shape; bare `print` absent |
| `print_i32`, `print_f64`, `printf` | no | no | documentation only |
| `eprint` | no | no | documentation only (only `eprintln` exists, and only as `io.eprintln`) |
| `eprintln :: fn(s: string)` | as `io.eprintln(fmt, …)` | module-qualified only | different shape |
| `assert`, `assert_msg`, `panic` | no | no | documentation only |
| `str_len`, `str_copy`, `str_compare`, `str_find`, `str_contains`, `str_starts_with`, `str_ends_with` | no | no | documentation only |
| `char_is_alpha/digit/upper/lower`, `char_to_upper/lower` | no | no | documentation only |
| `mem_copy`, `mem_move`, `mem_set`, `mem_zero`, `mem_compare`, `mem_alloc`, `mem_free`, `mem_realloc` | no | no | documentation only |

`io.println` is not in SPEC 11.2's list at all, yet it is the most used call in
the repository.

Other docs checked for claims that imply more than exists:

- `README.md:167` "Standard Library: Registry with io and math modules,
  backend-specific mappings" — the backend never reads those mappings (STD-17).
- `docs/STATUS.md:38-39` "`Option`, `Result`, collections, and fuller
  string/memory helpers are planned stdlib work" — accurate.
- `site/public/docs/stdlib.md:36-37` and `site/public/llms-full.txt:281-282`
  "Typed variants such as `sqrt_f32` and `sqrt_f64` are also available as bare
  builtins" — **false** (STD-12).
- `site/public/docs/stdlib.md:11-12`, `:50-62` correctly say `mem`/`string` are
  not registered and `Option`/`Result` are unavailable.
- `docs/SPEC.md:1566-1576` correctly describes the current io/math surface, the
  per-call flush and the stream separation — all three verified (§6).
- `site/public/llms.txt:12-13` points at the stdlib page; no extra claims.

## 3. Findings

### STD-1 (CRITICAL, KNOWN = PIP-2 = SAF-9): a user function named like a typed math builtin is replaced by the Zig builtin

`ast_preprocessor.py:215-219` tags any bare call whose name is in the registry's
builtin table, and `zig.py:1634-1640` emits the Zig builtin. Probe
`p/sh04_user_sqrt_f64.a7` (`sqrt_f64 :: fn(x: f64) f64 { ret x + 1.0 }`, then
`io.println("{}", sqrt_f64(9.0))`): a7=0, zig=0, and
`out/sh04_user_sqrt_f64.zig:19` is `__a7_stdout_print("{}\n", .{@sqrt(9.0)});` —
the user's body is emitted at `:14-16` and never called. Run-time evidence is C2's
before-log, which records the same probe failing as `assert ('3\n','') ==
('10\n','')` (`tmp/reports/r1a-c2-impl.md`, "PIP-2 = SAF-9"); it was not re-run
here. KNOWN: `docs/audits/2026-09-16/compiler/pipeline.md:122-138`,
`safety.md:227-242`. **Closed in C2**; still present in the tree audited here.
**Changes an accepted, building program:** yes.

### STD-2 (CRITICAL, KNOWN = PIP-3 = ZIG-5): a struct value named `io` is printed to stdout

`zig.py:2168-2173` and `:137-149` match the identifier text `io` independently of
any import. Probe `p/sh03b.a7` (`Printer :: struct { println: fn(string) }`,
`io := Printer{println: say}`, `io.println("hijacked")`) with no import at all:
a7=0; emitted `out/sh03b.zig:21-22` is
`const io = Printer{ .println = say }; __a7_stdout_print("hijacked\n", .{});` —
the field call is gone. Zig then fails with `unused local constant` (exit 1); C2's
before-log records the running variant of the same probe as
`assert ('hijacked\n','') == ('','')` (`tmp/reports/r1a-c2-impl.md`, "PIP-3 =
ZIG-5"), so a program that also uses the struct elsewhere builds and prints the
wrong thing. KNOWN: `pipeline.md:140-156`. **Closed in C2**. **Changes an
accepted, building program:** yes.

### STD-3 (HIGH, KNOWN = TYP-19, with a new counterexample): `math.abs` on a signed integer is typed signed in A7 and unsigned in Zig

`_validate_math_call` returns the first argument's type for `abs`
(`a7/passes/type_checker.py:1489-1532`). Zig's `@abs` on a signed integer returns
the **unsigned** type of the same width. KNOWN as TYP-19
(`docs/audits/2026-09-16/compiler/types.md:429-435`).

Reconfirmed: `p/m01b_abs_int_rt.a7` (`x := neg(3)` keeps the value out of
comptime, `y := math.abs(x)`, `w: i32 = y`) is a7 exit 0, then

```
$ zig build-obj -fno-emit-bin m01b_abs_int_rt.zig      # exit 1
m01b_abs_int_rt.zig:21:20: error: expected type 'i32', found 'u32'
    const w: i32 = y;
```

**New here:** TYP-19 concludes "Changes accepted programs Zig builds: no". That is
wrong. `p/m17_abs_uses_result.a7` (`y := math.abs(x); z := y - 10`) is a7=0 **and
zig=0**, emitting `const y = @abs(x); const z = (y - 10);` — unsigned subtraction
where A7's type rules say `3 - 10 = -7`. So a fix does change a program that A7
accepts and Zig builds today, and needs the owner's approval. UNVERIFIED at run
time: the probe rules forbid running a program with possible integer overflow, so
the Debug panic / ReleaseFast wrap was not executed; the Zig typing of `@abs` and
the emitted expression are the evidence.

The all-literal case hides the defect: `x: i32 = -3` is comptime-known, so
`p/m01_abs_int.a7` builds (a7=0, zig=0) because a comptime `u32` 3 coerces to
`i32`. Fix direction: emit `@as(i32, @intCast(@abs(x)))` for signed-integer `abs`,
or restrict `math.abs` to floats as `sqrt`/`floor`/`ceil` already are.
**Changes an accepted, building program:** yes.

### STD-4 (HIGH, KNOWN = X-SYM / PIP-4, survives C2): a local `io` declared inside an `else if` still hijacks

Not re-probed here. C2's own report records it as not fixed:
`tmp/reports/r1a-c2-impl.md`, "Not fixed, and still X-SYM/PIP-4: when `else if`
desynchronizes scopes, a local `io` declared inside the `else if` block still
hijacks (`tmp/r1a-c2/scratch/elseif2.a7` emits `__a7_stdout_print("hidden\n")`
both before and after — identical bytes)." Present in this tree too, which does
not even have C2's scoped resolution. **Changes an accepted, building program:**
yes.

### STD-5 (MEDIUM, KNOWN = ZIG-26): a non-empty `{…}` group is a placeholder to the checker and literal text to the backend

`_count_format_placeholders` (`type_checker.py:1534-1552`) counts any `{` that has
a later `}` as one placeholder and demands a matching argument.
`_convert_format_string` (`zig.py:2257-2287`) recognizes only the exact pair `{}`
and escapes every other brace to `{{`/`}}`. KNOWN as ZIG-26
(`docs/audits/2026-09-16/compiler/backend.md:77`, `:379-382`).

Reconfirmed: `p/m14_io_named_placeholder.a7` (`io.println("{x}", 1)`) is a7 exit 0,
emits `__a7_stdout_print("{{x}}\n", .{1});` (`out/m14_io_named_placeholder.zig:15`),
then

```
$ zig build-obj -fno-emit-bin m14_io_named_placeholder.zig   # exit 1
.../std/Io/Writer.zig:736:18: error: unused argument in '{{x}}\n'
```

Fix direction: make the checker's counter recognize exactly what the backend
lowers (bare `{}` only), or implement named/spec placeholders. Related open ledger
work: `docs/plan/fix-program/backend-fix-plan.md:550` maps ZIG-26 to TYP-26 /
task T8, and `:471` records the open question of whether `{{` is an escape or a
literal (SPEC has no rule). **Changes an accepted, building program:** no — every
such program is rejected by Zig today.

### STD-6 (MEDIUM, KNOWN root cause = ZIG-26, NEW observable): a literal `{` … `}` in text is falsely rejected

ZIG-26 records the Zig-rejects direction. The checker-side symptom is a **false
rejection of a valid program**, which the earlier audits did not probe. Probe
`p/f04_escape_braces.a7`:

```a7
io.println("literal { and } braces")
```

a7 exit 6: `Wrong number of arguments (io format string expects 1 values, got 0)`.
The backend would have lowered it correctly: the neighbouring forms
`p/f07_brace_open_only.a7` ("open brace { only", no closing brace) and
`p/f06_double_brace.a7` are a7=0, zig=0, and running them prints
`open brace { only` and `literal {{ and }} braces`. So a lone brace is fine, a
*pair* of braces anywhere in the string is a compile error, and `{{` prints as two
braces (the last of these is KNOWN ZIG-33, `backend.md:410-415`). No document
states any of this. **Changes an accepted, building program:** no — the program is
rejected today.

### STD-7 (MEDIUM, KNOWN = TYP-19): `math.min`/`max` with an integer variable and a float literal is accepted and Zig rejects it

TYP-19 (`types.md:429-435`) records that `_validate_math_call` "returns whichever
side is assignable (`:1497-1501`), which allows int/float mixes" and cites
`c43_minmax_mixed`. Reconfirmed with a runtime-valued variant:
`p/m03b_min_mixed_rt.a7` (`a := idi(1)`, `math.min(a, 2.5)`) is a7 exit 0, emits
`@min(a, 2.5)`, then

```
$ zig build-obj -fno-emit-bin m03b_min_mixed_rt.zig     # exit 1
m03b_min_mixed_rt.zig:20:38: error: unable to resolve comptime value
note: value casted to 'comptime_float' must be comptime-known
```

The all-literal version hides it (`p/m03_min_mixed.a7` is a7=0, zig=0). Different
float widths *are* caught, but by the generic argument checker, not the math path:
`p/m06b_min_f32_f64_rt.a7` is exit 6 "expected 'f32', got 'f64'". **Changes an
accepted, building program:** no.

### STD-8 (MEDIUM, NEW): a stdlib function used as a value emits an undeclared identifier

`visit_field_access` returns `UNKNOWN` for any module field
(`type_checker.py:1759-1777`) without requiring the field to be *called*, and the
backend has no lowering for a bare module field. Probe `p/m16_math_field_value.a7`
(`f := math.sqrt`): a7 exit 0, emits `const f = math.sqrt;`, then

```
$ zig build-obj -fno-emit-bin m16_math_field_value.zig   # exit 1
m16_math_field_value.zig:3:15: error: use of undeclared identifier 'math'
```

Fix direction: reject a stdlib module member in a non-call position with a
semantic error. **Changes an accepted, building program:** no.

### STD-9 (MEDIUM, NEW; lexing part KNOWN = TOK-09): every `@name` gets the same "parsed for future support" diagnostic, including names that do not exist

`visit_call_expr` (`type_checker.py:1300-1325`) tests only
`callee.name.startswith("@")` and reports
`Intrinsic '<name>' is parsed for future support but is not implemented in the Zig
backend yet`. There is no list of recognized intrinsic names anywhere in the
compiler — `_tokenize_builtin` (`tokens.py:806-817`) accepts any `[A-Za-z0-9_]*`
after `@`, including the empty string and pure digits.

Probes: `p/i_garbage.a7` (`@not_a_real_intrinsic(1)`), `p/i_at_digit.a7` (`@1(2)`)
and `p/i_at_bare.a7` (`@()`) all exit 6 with that message, promising future support
for `@not_a_real_intrinsic`, `@1` and `@`. A misspelled `@size_off` is
indistinguishable from a real reserved name. That `@` alone lexes is KNOWN
(TOK-09, `docs/audits/2026-09-16/compiler/tokenizer.md:53, 282`: "`@label` and `$T`
accept Unicode letters; … `@` alone lexes"); the diagnostic behaviour is new.

Fix direction: keep a recognized-intrinsic set (the seven in SPEC 11.1 plus
`@type_set`); anything else gets "unknown intrinsic". **Changes an accepted,
building program:** no.

### STD-10 (MEDIUM, NEW): a named `@type_set` alias is a codegen error

SPEC 7.3 (`docs/SPEC.md:947-962`) shows `Numeric :: @type_set(i8, …)` and says
type-set syntax "is implemented for predefined sets, local `@type_set(...)`
aliases, and inline constraints". The alias *declaration* reaches the backend.
Probe `p/i_typeset_alias_only.a7` — a file whose only unusual content is
`Ints :: @type_set(i32, i64)` and an `io.println("hi")`:

```
$ uv run a7 p/i_typeset_alias_only.a7 --output out/…zig    # exit 7
✗ 4:9: Zig backend: unsupported expression node 'TYPE_SET'
```

The alias works as a *constraint* (`p/i_typeset_alias.a7` reaches exit 6 with a
correct "Generic constraint violation"), so the semantic side is implemented; the
earlier types audit's "alias type sets are enforced at call sites"
(`docs/audits/2026-09-16/compiler/types.md:605-606`) is about that path, not this
one. Fix direction: drop `@type_set` alias declarations during preprocessing (they
are compile-time only), or emit nothing for a `TYPE_SET` declaration.
**Changes an accepted, building program:** no.

### STD-11 (MEDIUM, NEW): `io.println` may only take a string *literal*, and no document says so

`_validate_io_call` (`type_checker.py:1459-1486`) rejects a non-literal first
argument. Probe `p/m12_io_nonliteral.a7` (`s := "hi"; io.println(s)`): exit 6,
`Unsupported feature: io format strings must be string literals`. Printing a string
*variable* still works through a placeholder (`io.println("{}", s)`,
`p/f03_print_kinds.a7`, a7=0 zig=0, prints `hi a true 1.5 7`), but nothing in
`docs/SPEC.md:1566-1576`, `site/public/docs/stdlib.md`, `README.md:164-167` or
`site/public/llms-full.txt:265-291` mentions the restriction. This is a
documentation gap, not a code defect — the restriction is forced by Zig's
`comptime fmt` parameter. **Changes an accepted, building program:** no.

### STD-12 (LOW, KNOWN = PIP-23, new doc locations): two site documents claim typed math builtins are callable

PIP-23 (`pipeline.md:455-464`) cited only `docs/SPEC.md:1571-1572`. Two more places
make the stronger claim:

- `site/public/docs/stdlib.md:36-37`: "Typed variants such as `sqrt_f32` and
  `sqrt_f64` are also available as bare builtins."
- `site/public/llms-full.txt:281-282`: identical sentence.

Probe `p/s08_typed_builtin.a7` refutes it: exit 6, "Undefined type (Identifier
'sqrt_f64')". C2 deletes the registry table but explicitly leaves PIP-23 and the
SPEC text open (`tmp/reports/r1a-c2-impl.md`: "PIP-23 … is untouched and still
open"); neither site file is in C2's owned list. **Changes an accepted, building
program:** no.

### STD-13 (LOW, NEW): `std/mem` and `std/string` fail as "module not found", leaking a path that does not exist

`STDLIB_MODULE_ALIASES` (`a7/stdlib/__init__.py:11-16`) has only io and math, so
`import "std/mem"` falls through to the file resolver. Probe `p/s09_std_mem.a7`:

```
exit 6: Error loading module 'std/mem' … : Module 'std/mem' not found in search
paths: ['tmp/audit/2026-09-18/stdlib/p', 'tmp/audit/2026-09-18/stdlib/p/stdlib',
'/home/cx89/Projects/pl-dev/a7-py/stdlib']
```

`/home/cx89/Projects/pl-dev/a7-py/stdlib` does not exist (KNOWN,
`pipeline.md:565`; `compile.py:241-242`). SPEC 10.3 (`docs/SPEC.md:1518-1523`)
lists `std/string`, `std/mem`, `std/collections` as planned, so the right
diagnostic is "planned, not implemented", not a filesystem miss. Adjacent to
PIP-32 (`pipeline.md:532-537`), which is the mirror case. **Changes an accepted,
building program:** no.

### STD-14 (LOW, NEW): an io call in a value position is diagnosed by the backend at exit 7

`_visit_stdlib_module_call` returns `VOID` for io calls and nothing in the semantic
passes rejects using that value; the backend raises instead (`zig.py:2220-2225`).
Probes `p/m11_io_as_value.a7` (`x := io.println("a")`) and `p/m18_io_const_init.a7`
(`X :: io.println("a")` at top level) are both

```
exit 7: ✗ Zig backend: io.print/io.println cannot be used as expression values
```

A user error reported as a codegen failure gives the wrong exit code (7 = codegen)
and no source frame beyond `line:col`. A math call in a constant initializer is
fine: `p/m09_const_init.a7` (`X :: math.sqrt(4.0)`) is a7=0, zig=0 and emits
`const X = @sqrt(4.0);`. **Changes an accepted, building program:** no.

### STD-15 (LOW, NEW): `site/public/docs/stdlib.md` writes `Option<T>` / `Result<T, E>` in a syntax A7 does not have

`site/public/docs/stdlib.md:59` and `site/public/llms-full.txt:304`:
"`Option<T>` and `Result<T, E>`". A7's generic syntax is `$T` with parenthesized
instantiation (`docs/SPEC.md:907-938`, e.g. `Box(Box(i32))`); `<>` is not generic
syntax anywhere in the language. **Changes an accepted, building program:** no.

### STD-16 (LOW, KNOWN, `pipeline.md:560`): `mem` and `string` "stub modules" are never registered

`a7/stdlib/__init__.py:45-50` (`_register_defaults`) calls only
`register_io_module` and `register_math_module`. `register_mem_module`
(`a7/stdlib/mem.py:6-9`) and `register_string_module` (`a7/stdlib/string.py:6-9`)
have no caller anywhere: `grep -rn "register_mem_module\|register_string_module"
a7/` returns only the definitions. Each file is 9 lines and registers a module
with zero functions, so calling them would still give nothing usable.

### STD-17 (LOW, KNOWN, `pipeline.md:561`): `backend_map`, `get_backend_mapping` and `is_io_call` are dead in the compiler

`grep -rn "is_io_call\|get_backend_mapping" a7/` matches only the definitions in
`a7/stdlib/__init__.py:85-101` and the backend's own unrelated `_is_io_call`
method (`zig.py:2161`). The Zig strings are hard-coded at `zig.py:1634-1640` and
`:2209-2218`. `README.md:167` advertises "backend-specific mappings" as a feature;
they are an unread table asserted only by tests (§7).

### STD-18 (LOW, NEW): the audit checklist miscounts the math module

`docs/plan/audit/language-audit-checklist.md:65` says "`a7/stdlib/math.py` 10
functions". `a7/stdlib/math.py:11-23` lists 11 (`sqrt, abs, floor, ceil, sin, cos,
tan, log, exp, min, max`), confirmed by `p/s02_surface_math.a7` calling all eleven.

## 4. `Option` and `Result`

**What exists.** Nothing named `Option` or `Result` is provided by the compiler.
Both are ordinary user identifiers:

- `Option :: struct { has: bool, value: i32 }` compiles and builds
  (`p/o03_option_name_free.a7`, a7=0 zig=0).
- `Result :: union(tag) { ok: i32, err: i32 }` compiles to a Zig `union(enum)`
  (`p/o04_result_tagged.a7`, a7=0 zig=0, `out/o04_result_tagged.zig:14-17`).

**What SPEC 7.2 shows and what happens.**

- `Option :: enum { Some: $T, None, }` (`docs/SPEC.md:928-932`) — exit 5,
  "Expected IDENTIFIER, got COLON [line 3: col 8]" (`p/o01_option_enum.a7`).
  KNOWN: `docs/audits/2026-09-16/compiler/parser.md:485` ("Exit 5 (`q28`). KNOWN
  via ledger C5").
- `Result :: union { ok: $T, err: $E, }` (`docs/SPEC.md:934-938`) — parses and
  type-checks, then **exit 7**: `✗ 3:9: Zig backend: generic type requires an
  explicit generic environment` (`p/o02_result_union.a7`). That message is KNOWN
  ZIG-29 (`backend.md:399-405`). SPEC's two generic composite examples therefore
  fail at two different stages; neither is usable.

**What STATUS promises.** `docs/STATUS.md:38-39`: "`Option`, `Result`,
collections, and fuller string/memory helpers are planned stdlib work."
`site/public/docs/stdlib.md:59` lists `Option<T>` and `Result<T, E>` under
"planned but not available" (in non-A7 syntax, STD-15).

**What gate G5 must decide.** `docs/plan/README.md:213-218`: G5 is "Errors,
matching and composite values — decide tagged-union syntax, payload matching,
`Option` and `Result` spelling, error propagation, struct initialization
completeness and nominal identity. The current I/O helpers panic on external
failures; decide their recoverable replacement." G5 also records the blocking
observation (`:220-239`): a `match` on a tagged union binds the whole union to the
case name and never tests the tag. Concretely, before any `Option`/`Result` can be
built, G5 must settle:

1. whether generic payloads in `enum`/`union` are a supported form at all — the
   SPEC 7.2 examples are the only spec text and neither works;
2. the spelling — library types, or `?T` sugar (packet P10,
   `docs/plan/execution.md:397`, proposes "payload matching, `?T`, Option/Result,
   error propagation, string equality");
3. payload matching semantics, since without tag testing neither type is
   inspectable;
4. the recoverable replacement for the `@panic` in the io helpers
   (`a7/backends/zig.py:173-174`), which is the first real user of `Result`.

Tracks 7a (optionals and matching) and 7b (results and errors) both list G5 as
their dependency (`docs/plan/README.md:341-342`).

## 5. What is missing

| Item | What exists now | What it needs | Decision owner (gate/packet/none) | v1 priority |
|---|---|---|---|---|
| Number parsing from text | nothing — no `parse`, `atoi` or equivalent anywhere in `a7/stdlib/` | a text→number API and a failure representation | **none**; blocked behind G5 (failure shape) and track 8a (owning `string`) | high |
| Number formatting into a string | only `io.println` to a stream (`zig.py:2209-2218`); no value→string | a formatting API writing into a caller buffer or an owning string | **none** (track 8b lists "text", but no packet exists) | high |
| String handling beyond literals | `string` type and literals only; `a7/stdlib/string.py` registers zero functions and is never called (STD-16); SPEC 11.2's seven `str_*` are prose | owning `string` with length, compare, find, slice, concat | track **8a** (`docs/plan/README.md:343`), depends on G5 and memory plan gates M1/M5/M13/M33/M42/M49 | high |
| ASCII / char classification | `char` type; SPEC 11.2's six `char_*` are prose | six pure functions; needs no memory model | **none** | medium |
| Collections (`List`, `Map`, …) | nothing; SPEC 10.3 lists `std/collections` as planned (`docs/SPEC.md:1523`) | `List`, `Map`, `Table`, `Id`, deep equality, hashing | track **8a** | high |
| Hashing | nothing | a hash interface, tied to `Map`/`Table` | track **8a** ("deep equality and hashing") | medium |
| Sorting | nothing; A7 source recursion is banned (CLAUDE.md "A7 Source Rules"), so a sort must be iterative | comparator convention plus an iterative sort over a slice | **none** | medium |
| Time | nothing | a clock source, a duration type, a syscall boundary | track **8b** (`docs/plan/README.md:344`) — depends on 6a and 7b | low |
| Random | nothing; `site/public/docs/status.md:27` names "deterministic random helpers" as a priority and `site/public/docs/stdlib.md:57` lists `std/random` as planned | seeded generator; no OS entropy needed for v1 | track **8b**; the site text promises it earlier than the track allows — a drift to resolve | medium |
| Files and paths | nothing; `site/public/docs/stdlib.md:62` says file IO is "out of scope for the current stdlib" | open/read/write/close, a path type, a failure representation | track **8b**, with packet **P9** (`docs/plan/execution.md:397, 466`) as the proposed early exception: "stdin line read into a caller buffer returning a count, command-line args, whole-file read into a buffer; failure as a status value until 7b". P9 needs the owner's approval in P0.4 (`docs/plan/README.md:360`) | high |
| Process / args / env | nothing; a compiled program's `main` takes `std.process.Init` but nothing is exposed to A7 (`zig.py:177-180`) | argv access; env is a later concern | packet **P9** (argv only); env has **none** | high |
| Allocators | `new`/`del` lower to a hard-coded `std.heap.page_allocator` (`zig.py:159`); SPEC 11.2's `mem_alloc`/`mem_free`/`mem_realloc` are prose; `a7/stdlib/mem.py` registers nothing (STD-16) | an allocator concept, or a decision that allocation stays implicit | memory plan track **6a** (`docs/plan/README.md:339`) | high |
| Assertions and test helpers | nothing; SPEC 11.2's `assert`, `assert_msg`, `panic` are prose. There is no way to abort from A7 except an out-of-range operation | `assert`/`panic` are three lines of lowering to Zig's `@panic`, which the io helper already uses | **none** | high |
| Recoverable I/O | `@panic("a7 stdout write failed")` on any write or flush failure (`zig.py:173-174`) | a failure value instead of a panic | gate **G5** names this explicitly (`docs/plan/README.md:216-217`); track **7b** implements it | high |

Two things stand out. **Assertions and ASCII classification have no owner at all**
and need no design work — they are the only rows that could be built today against
existing machinery. And the site status page promises deterministic random helpers
(`site/public/docs/status.md:27`) while the plan puts random behind track 8b, which
depends on 6a and 7b; those two documents should be reconciled.

## 6. Checked and correct

Each item was probed; a7 and `zig build-obj` exit codes are given, and run-allowed
probes were built with `zig build-exe -ODebug` and executed.

- **Stream separation and per-call flush.** `p/s01_surface_io.a7`, built and run:
  `./s01dbg > s01_stdout.txt 2> s01_stderr.txt` gives `ab\nx=1\n` in stdout and
  `e=2\n` in stderr. SPEC 11.2's claim (`docs/SPEC.md:1573-1576`) holds.
- **The pending-items (b) stdout-overwrite defect is FIXED in this tree.**
  `tmp/packets/pending-items.md:7` records "stdout redirected to a regular file is
  overwritten at offset 0 on each `io.println`". Batch C3 changed the helper from
  `.writer(...)` to `.writerStreaming(...)` (`a7/backends/zig.py:166-172`, an
  uncommitted change — `git log -S writerStreaming -- a7/backends/zig.py` lists
  only the two older commits `f793ff4` and `91447f2`;
  `tmp/reports/r1a-c3-impl.md:45-49` and `r1a-c3-verify.md:34` document the
  reason). Probe: four separate print calls redirected into a regular file produce
  all four lines in order (`out/s01_stdout.txt`), not just the last.
  **Refuted for the current tree**; reopen only if C3 is reverted.
- **Mixed-stream ordering.** `p/io_interleave.a7`, run-allowed, both streams into
  one file: `out1 err1 out2 err2` in source order. SPEC says order is not
  guaranteed; because each call flushes, it is preserved here.
- **Large output.** `p/io_bigbuf.a7` prints a 3000-byte literal through the
  1024-byte helper buffer: a7=0, zig=0, run exit 0, `out/iobig_out.txt` is 3005
  bytes ending `…XXX\nend\n`. The buffer does not truncate.
- **Math arity.** `math.sqrt(1.0, 2.0)` is exit 6, "math.sqrt expects 1 arguments,
  got 2" (`p/m07_arity.a7`); `min`/`max` require exactly 2
  (`type_checker.py:1491-1497`).
- **Math on the wrong scalar type.** `math.sqrt(a: i32)` is exit 6, "expected 'f32
  or f64', got 'i32'" (`p/m04_sqrt_int.a7`); `math.sqrt("hi")` is exit 6,
  "Requires numeric type: got 'string'" (`p/m19_math_abs_string.a7`).
  `math.sqrt` on both `f32` and `f64` in one program builds
  (`p/m05_sqrt_f32.a7`, a7=0 zig=0) — `@sqrt` is width-generic.
- **Unknown stdlib member.** `math.pow(2.0, 3.0)` is exit 6 with two errors,
  "Stdlib module 'std/math' has no function 'pow'" and "Unknown stdlib call
  'std/math.pow'" (`p/m08_unknown_fn.a7`).
- **io argument count against the format string.** `io.println("{} {}", 1)` is
  exit 6, "io format string expects 2 values, got 1"
  (`p/m13_io_placeholder_count.a7`).
- **io format argument type.** `io.println(42)` is exit 6, "expected 'string', got
  'i32' (io format argument)" (`p/m20_io_wrong_fmt_type.a7`).
- **Zero-argument io.** `io.println()` emits `__a7_stdout_print("\n", .{})` and
  `io.print()` emits `("", .{})` (`p/m15_io_no_args.a7`, a7=0 zig=0).
- **Per-argument format specs.** `_format_spec_for_arg` (`zig.py:2227-2255`) picks
  `{s}` for string, `{c}` for char, `{}` for scalars and `{any}` otherwise.
  `p/f03_print_kinds.a7` emits `"{s} {c} {} {} {}\n"` and prints
  `hi a true 1.5 7`. Struct, array and enum values fall to `{any}` and build
  (`p/f01_print_struct.a7`, `p/f02_print_array.a7`, `p/f05_print_enum.a7`, all
  a7=0 zig=0).
- **A math call as a bare statement.** `math.sqrt(4.0)` alone emits
  `_ = @sqrt(4.0);` (`p/m10_stmt_value.a7`, a7=0 zig=0) — Zig's ignored-value rule
  is satisfied.
- **`@type_set` enforcement.** `addv($T: @type_set(i32, i64)) :: fn(a: $T, b: $T) $T`
  accepts `i32` arguments (`p/i_typeset_ok2.a7`, a7=0 zig=0) and rejects `f64` with
  "Generic constraint violation" (`p/i_typeset_bad2.a7`, exit 6), including
  through a named alias (`p/i_typeset_alias.a7`, exit 6).
- **Loop labels.** `@outer for … { break outer }` compiles and builds
  (`p/i_label.a7`).
- **Arbitrary import aliases for virtual modules.** `console :: import "std/io"`
  with `m :: import "std/math"` compiles and builds (`p/s03_alias_io.a7`), as SPEC
  10.3 promises (`docs/SPEC.md:1509-1512`).

## 7. Test gaps

`test/test_stdlib_registry.py` (423 lines, 55 tests; 62 with
`test/test_module_alias_shadowing.py`, all passing — `out/pytest1.log`, exit 0) is
**confirmed** to be what `pipeline.md:608` says it is:

- `TestResolveBuiltin` (`:166-232`, 9 tests) exercises `resolve_builtin`, which
  only `ast_preprocessor.py:217` calls, and only to produce the STD-1 hijack. The
  tests assert the hijack table is intact. C2 deletes both
  (`tmp/reports/r1a-c2-impl.md` §1).
- `TestGetBackendMapping` (`:235-307`, 9 tests) asserts a table no compiler code
  reads (STD-17). `test_io_println_zig` asserts `"__a7_stdout_print"` — a string
  the backend independently hard-codes at `zig.py:2218`; the two could diverge and
  every test would still pass.
- `TestIsIoCall` (`:310-346`, 7 tests) tests `StdlibRegistry.is_io_call`, which has
  no caller in `a7/`.
- `TestCustomModuleRegistration` (`:349-389`, 3 tests) registers a module named
  `custom` that no import path can reach (`STDLIB_MODULE_ALIASES` is a fixed dict).
- `TestStdlibDataclasses` (`:392-423`, 4 tests) asserts that a dataclass stores the
  values passed to its constructor.
- `TestStdlibRegistryInitialization` (`:12-61`, 7 tests) and `TestResolveCall`
  (`:64-163`, 16 tests) restate the registry tables, e.g. `test_math_sqrt` asserts
  `resolve_call("math","sqrt") == "std.math.sqrt"`.

By the CLAUDE.md Test quality rule, 32 of the 55 exercise registry API with no
caller in `a7/` (9 + 9 + 7 + 3 + 4 above) and the remaining 23 assert that the
registry tables contain what the tables literally contain. None of the 55 would
fail if the io/math surface stopped working end to end.

Stdlib behaviours with real coverage: stream separation
(`test/test_codegen_zig.py:320-331`,
`test_io_println_writes_stdout_and_eprintln_writes_stderr`); the emitted helper
text, including `writerStreaming` (`test/test_codegen_zig.py:289, 357, 358, 966,
998`); and module-alias shadowing (`test/test_module_alias_shadowing.py`, 7 tests,
all passing).

Stdlib behaviours with **no** test:

1. `math.abs` on a signed integer (STD-3) — no test compiles `math.abs` of an
   `i32` and builds the result.
2. Format-string placeholder counting versus backend lowering (STD-5, STD-6) — no
   test covers `{x}`, a literal brace pair, or `{{`.
3. `math.min`/`max` with mixed integer and float arguments (STD-7).
4. A stdlib member used as a value (STD-8).
5. A user function named like a registry builtin keeping its body (STD-1) —
   already noted at `pipeline.md:602`; C2 adds the tests in its worktree.
6. Any `@`-intrinsic diagnostic: no test asserts what `@size_of` or an unknown
   `@name` reports (STD-9).
7. A named `@type_set` alias reaching codegen (STD-10).
8. `import "std/mem"` / `"std/string"` diagnostics (STD-13).
9. An io call in a value or constant-initializer position (STD-14).
10. Behaviour of the print helper against a **regular file**: the five
    `writerStreaming` asserts above check the emitted *text*, so they would still
    pass if the runtime behaviour regressed. No test redirects a compiled
    example's stdout into a file and reads back every line — the property the C3
    fix exists to guarantee.
11. Output longer than the helper's 1024-byte buffer.
12. `io.println()` and `io.print()` with zero arguments.
13. `math` on `f32` versus `f64` in the same program.

## 8. Not verified

- The run-time consequence of STD-3's silently-building shape
  (`p/m17_abs_uses_result.a7`): the probe rules forbid running a program with
  possible integer overflow, so the Debug panic / ReleaseFast wrap was not
  executed. The Zig typing of `@abs` and the emitted
  `const y = @abs(x); const z = (y - 10);` are the evidence.
- STD-1 and STD-2's run-time output (`3` instead of `10`; `hijacked` instead of
  nothing) is taken from C2's before-logs quoted in `tmp/reports/r1a-c2-impl.md`,
  not re-run here. The emitted Zig was re-derived in this tree.
- STD-4 (`else if` scope desync) is taken from `tmp/reports/r1a-c2-impl.md` and was
  not re-probed in this tree.
- A parser inconsistency noticed while building the shadowing probes, out of scope
  here and not chased: `p/sh03_struct_named_io.a7`, with
  `Printer :: struct { println: fn(string) }` on one line, is exit 5 "Expected type
  [line 2: col 40]", while the same declaration split across lines (`p/sh03b.a7`)
  parses, and the identical one-line form inside `p/sh01_shadow_local_io.a7` also
  parses. `p/sh02_param_named_io.a7` separately reports a declared `Printer` as
  "Undefined type" at a parameter position.
- Whether `math.log` is base-e at every float width: `@log` is natural log in Zig,
  but only `math.log(1.0)` — 0 in every base — was run (`p/s02_surface_math.a7`).
- `--mode doc`, `--mode semantic` and `--format json` output for stdlib calls;
  `pipeline.md:379-385` already records a stdlib-path defect in `--mode semantic`.
- Behaviour on a non-Linux host or with a Zig version other than 0.16.0.
- KNOWN sweep performed before labelling: `docs/plan/audit/language-audit-checklist.md`,
  `language-evidence-map.md`, `language-interactions.md`, `docs/plan/decisions.md`,
  `docs/plan/fix-program/*.md` and all six `docs/audits/2026-09-16/compiler/*.md`,
  case-insensitively for `abs`, `format`, `brace`, `placeholder`, `type_set`,
  `intrinsic`, `builtin`, `stdlib`, `io.` and `math.` (`out/knownsweep.txt`). The
  sweep moved five findings from NEW to KNOWN (STD-3, 5, 6, 7 and the lexing half
  of STD-9) and produced no hit for STD-8, 10, 11, 13, 14, 15 or 18.

claims checked: 121 (73 probe files, each with its a7 exit code and, where it
compiled, its `zig build-obj` exit code; plus 48 distinct file:line citations into
`a7/`, `docs/`, `test/`, `site/` and `tmp/reports/`)
