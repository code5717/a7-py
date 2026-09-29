# Audit: modules, visibility and type aliases

Date: 2026-09-18. Scope: `a7/module_resolver.py`, the module merge in
`a7/compile.py`, `pub` in `a7/parser.py` and `a7/passes/name_resolution.py`,
type aliases across `a7/passes/name_resolution.py`, `a7/passes/type_checker.py`
and `a7/types.py`; SPEC 10.1-10.4, SPEC 3.4, SPEC A.3.

Tree audited: the main tree as of 2026-09-18 with batches C3, PR-00, T0, V1,
NOREC-0 and PL-02 applied as uncommitted changes. C1, C4 and C2 in
`/home/cx89/Projects/pl-dev/a7-wt/` were not read.

Probes: `tmp/audit/2026-09-18/visibility/p/*.a7`, outputs under
`tmp/audit/2026-09-18/visibility/out/` (`<name>.summary` holds both exit codes,
`<name>.a7out` the A7 diagnostic, `<name>.zigout` the Zig build log). Driver:
`tmp/audit/2026-09-18/visibility/run.sh`. Compile command for every probe:
`uv run a7 <file>.a7 --output out/<file>.zig`, then
`zig build-obj -fno-emit-bin out/<file>.zig` (`zig version` = 0.16.0). Every probe is
`// probe: compile-only`; nothing was executed.

`pub` does nothing. A module is a textual include, not a namespace: names leak
in **both** directions, not only from the imported file into the importer.
A type alias whose right-hand side names any user type or any other alias is
not parsed as a type alias at all — it becomes a constant, which is the root
cause of MTH-6 and makes SPEC 3.4's own aliasing of declared types unusable.
Import-cycle detection is unreachable code.

## Summary

| Severity | NEW | KNOWN (new manifestation or new detail) | Total |
| --- | --- | --- | --- |
| HIGH | 4 | 1 | 5 |
| MEDIUM | 4 | 4 | 8 |
| LOW | 4 | 0 | 4 |
| **Total** | **12** | **5** | **17** |

A finding is KNOWN when an existing ID or failing baseline test already records
the same defect; its header names that ID and what is new about this probe.
Twenty further re-confirmations of earlier findings are not filed again; they are
listed in "Known findings re-confirmed" with the probe that shows each.

**Seven of the 17 would change a program A7 accepts and Zig builds today**, so
their fixes need owner approval: VIS-2 (reverse name leak), VIS-4 in part
(unqualified generic *types* across files build today), VIS-6 and VIS-7 (`pub` as
a no-op, `pub` on struct fields), VIS-8 in part (`m06_two_alias.a7` builds and
L26 makes it an error), VIS-14 (`pub` on an import), VIS-16 (circular
declarations build as long as nothing uses them), and VIS-15 if the parser rather
than the SPEC line changes. The other ten already fail or produce Zig that
fails.

## Findings

### VIS-1 (HIGH, NEW; the cause of KNOWN MTH-6): `Name :: OtherType` is parsed as a constant, not a type alias

A type alias is recognised only when its right-hand side *starts with a token
that cannot begin an expression*. `_is_type_start` (`a7/parser.py:1515-1523`)
lists the primitive keywords, `ref` and `$T`; `parse_const_or_function_decl`
(`a7/parser.py:488-497`) adds `[` and, earlier, `fn`. Anything else — including
every identifier — falls through to `value = self.parse_expression()` at
`a7/parser.py:500` and becomes a `CONST` declaration.

So `Ctr :: Counter` is a constant whose value is the identifier `Counter`. In
the type checker, `_resolve_type_leaf` (`a7/passes/type_checker.py:433-452`)
looks the name up, finds `SymbolKind.CONSTANT`, which is not in the accepted set
at `:440-446`, and reports `UNDEFINED_TYPE`.

| Probe | Alias form | a7 | zig | First error |
| --- | --- | --- | --- | --- |
| `t02_struct.a7` | `Ctr :: Counter` (struct) | 6 | — | `Undefined type (Type 'Ctr')` |
| `t03_enum.a7` | `C :: Color` (enum) | 6 | — | `Undefined type (Type 'C')` |
| `t04_union.a7` | `W :: V` (union) | 6 | — | `Undefined type (Type 'W')` |
| `t09_alias_of_alias.a7` | `A :: u32` then `B :: A` | 6 | — | `Undefined type (Type 'B')` |
| `t10_alias_generic_inst.a7` | `IntBox :: Box(i32)` | 6 | — | `Type is not callable: got 'Box(T)'` |

Controls that prove the branch, not the feature, is at fault: `t01_prim.a7`
(`Handle :: u64`) a7=0 zig=0; `t05_slice.a7` (`Bytes :: []u8`) 0/0;
`t06_array.a7` (`Vector :: [3]f32`) 0/0; `t07_array2d.a7` (`Matrix :: [4][4]f32`)
0/0; `t08_fnptr.a7` (`Op :: fn(i32, i32) i32`) 0/0. Every one of these begins
with a keyword or `[`.

The same alias is accepted as a struct-literal head. `t14_alias_literal_head.a7`
(`Ctr :: Counter` then `c := Ctr{value: 1}`) is a7=0 zig=0, because the constant
lowers to `const Ctr = Counter;` and Zig treats that as a type alias
(`out/t14_alias_literal_head.zig`). One declaration is therefore usable as a
type in one position and not in another.

`docs/SPEC.md:369-378` shows aliases without restricting the right-hand side,
and `README.md:153` lists type aliases under "What Works". KNOWN MTH-6
(`docs/audits/2026-09-18/methods.md:226`) observed the symptom for
`Ctr :: Counter`; this is its cause, and it covers enums, unions, alias chains
and generic instantiations too.

Fix direction: in `parse_const_or_function_decl`, treat `Name :: Identifier`
followed by a terminator as a `TYPE_ALIAS` when the identifier is not a call or
a larger expression, or resolve a `CONST` whose value is a bare identifier
naming a type as a type in `_resolve_type_leaf`. **Changes an accepted,
Zig-built program:** no for t02/t03/t04/t09/t10 (all rejected today); t14 must
keep building, so the fix has to leave the literal-head path working.

### VIS-2 (HIGH, NEW; PIP-7's mechanism, the opposite direction): names leak from the importing file into the imported module

PIP-7 records that an importer sees a module's private names. The reverse also
holds: a module body can call a function that exists only in the file that
imports it, with no import of its own.

`p/leaner.a7`:

```a7
pub uses_main_fn :: fn() i32 { ret helper_in_main() }
```

`p/v10_reverse_leak.a7` imports it and declares `helper_in_main` itself. a7=0,
zig=0 (`out/v10_reverse_leak.summary`), and the emitted Zig resolves the call:

```zig
pub fn module_leaner__uses_main_fn() i32 {
    return helper_in_main();
}
fn helper_in_main() i32 { return 11; }
```

`a7/compile.py:730-759` concatenates every module declaration ahead of the
importer's and hands the single list to one `NameResolutionPass`
(`a7/compile.py:268-270`), so there is no direction to visibility at all.
SPEC 10.1 (`docs/SPEC.md:1450-1453`) says "Every A7 source file is a module";
a module that compiles only because of a name in another file is not one.

Fix direction: covered by MOD's per-module scopes (`docs/plan/execution.md:66`).
**Changes an accepted, Zig-built program:** yes. Needs owner approval; gate G6
and packet P-MOD own it.

### VIS-3 (HIGH, NEW): import-cycle detection and the topological sort are unreachable

`ModuleResolver.load_module` returns a cached module at
`a7/module_resolver.py:124-125` *before* the `loading_stack` check at
`:131-135`, and registers the module in `self.loaded_modules` at `:187` *before*
it recurses into its dependencies at `:190-191`. Any cycle therefore hits the
cache and returns; the `SemanticError("Circular dependency detected: …")` at
`:133-135` can never fire.

`topological_sort` (`:310-350`), which raises the second cycle error at
`:346-348`, is called from nowhere:

```
$ grep -rn "topological_sort\|loading_stack\|Circular dependency" a7/ test/ | grep -v module_resolver.py
(no output)
```

Probe `m04_cycle.a7` (`cyA` imports `cyB`, `cyB` imports `cyA`, main imports
`cyA`): a7=6, but the diagnostic is
`Undefined type (Identifier 'z') [line 3: col 27]` — the unrelated
transitive-import failure (KNOWN PIP-8), not a cycle report. There is no
diagnostic anywhere that names the cycle.

`docs/plan/execution.md:65` specifies the replacement: "Kahn topological sort;
leftover nodes form a cycle, reported with the full import chain and spans
(PIP-10)".

Fix direction: check the loading stack before the cache, or register the module
only after its dependencies load. **Changes an accepted, Zig-built program:** no
(cyclic programs fail today, with the wrong message).

### VIS-4 (HIGH, NEW): a generic function called through a module alias loses its type argument

This is the "Generics × modules" pair that
`docs/plan/audit/language-audit-checklist.md:101` flags as having no audit and
no test.

`p/genmod.a7` declares `pub identity($T) :: fn(x: $T) $T`. `g01_generic_fn_qualified.a7`
calls `g.identity(5)`: a7=0, zig=1.

```
out/g01_generic_fn_qualified.zig:12:15: error: expected 2 argument(s), found 1
    const x = module_genmod__identity(5);
out/g01_generic_fn_qualified.zig:7:5: note: function declared here
pub fn module_genmod__identity(comptime T: type, x: T) T {
```

The call carries `file_module_call`, so the type checker returns `UNKNOWN`
without inferring or recording a type argument
(`a7/passes/type_checker.py:1317-1321`, KNOWN PIP-9), and the backend emits the
argument list as written. The unqualified spelling infers the type argument
correctly — `g02_generic_fn_unqualified.a7` emits `identity(i32, 5)` — but then
omits the module prefix the declaration carries (KNOWN PIP-6), so it fails as
`use of undeclared identifier 'identity'`. Neither spelling works.

A generic *type* from another module does work unqualified: `g03` and `g05`
(`Box(i32){value: 1}`, `b: Box(i32) = …`) are a7=0 zig=0, because only
`NodeKind.FUNCTION` declarations receive `module_emit_prefix`
(`a7/compile.py:748-750`) and a generic struct lowers to `fn Box(comptime T: type) type`
with its A7 name intact.

Fix direction: MOD lowers `alias.name` in value, type and generic positions
(`docs/plan/execution.md:69`); until then the `file_module_call` path must run
the same specialization the unqualified path runs. **Changes an accepted,
Zig-built program:** no for g01/g02; **yes** for g03/g05, which build today and
would become module-qualified.

### VIS-5 (HIGH, KNOWN MTH-12, two new shapes): a module-qualified name in type or generic position silently deletes the enclosing declaration

MTH-12 (`docs/audits/2026-09-18/methods.md:335`) found `sh.Counter{value: 1}`
deleting `main`. Two further shapes do the same, and both end at a Zig build
that succeeds.

- `t27_alias_qualified.a7` — `main :: fn() { x: h.Hnd = 1 }`: a7=0, zig=0, and
  `out/t27_alias_qualified.zig` is five lines with no `main`:

  ```zig
  const Hnd = u64;
  pub fn module_aliasmod__mk() Hnd { return @as(u64, 1); }
  ```

- `g04_generic_type_qualified.a7` — `b := g.Box(i32){value: 1}`: a7=0, zig=0,
  and `out/g04_generic_type_qualified.zig` contains only `Box` and `identity`,
  no `main`.

The control `t26_alias_cross_module.a7` (same program, unqualified `x: Hnd = 1`)
is a7=0 zig=0 **with** `main` emitted, so the qualifier alone is what drops the
declaration. `zig build-obj` exits 0 because an object file needs no `main`, so
nothing in the pipeline notices that the program is empty.

`docs/plan/execution.md:67` already records the type-position case ("today
`mod.Type` in a type position drops `main` silently") and assigns it to MOD's
`parse_type`; no audit finding carried it and the generic-instantiation shape
is not recorded anywhere.

Fix direction: `parse_type` accepts `alias.Type` and `alias.Box(i32)` (MOD); and
compile mode should fail when the program has no `main`. **Changes an accepted,
Zig-built program:** no — these produce no program today.

### VIS-6 (MEDIUM, NEW): `pub` is a no-op on every declaration except a function

`is_public` is consumed for behaviour in exactly one place in the whole
compiler (the second grep hit only serializes it into `--format json` AST
output):

```
$ grep -rn "is_public" a7/ | grep -v parser.py | grep -v ast_nodes.py
a7/formatters/json_formatter.py:96:            "is_public",
a7/backends/zig.py:431:        prefix = "pub " if ((is_main and not self._io_streams_needed) or getattr(node, 'is_public', False)) else ""
```

`zig.py:431` is inside function emission. Probe `v01_private_call.a7` imports
`p/helper.a7`, whose every declaration is `pub`; the emitted Zig
(`out/v01_private_call.zig`) is:

```zig
const LIMIT = 10;           // from `pub LIMIT :: 10`   — annotations mine
const Point = struct { … }; // from `pub Point :: struct`
const Handle = u64;         // from `pub Handle :: u64`
pub fn module_helper__work() i32 { … }
fn module_helper__hidden() i32 { … }
var G = 3;                  // from `pub G := 3`
```

`v09_pub_enum_union.a7` adds `pub E :: enum`, `pub U :: union`, `pub AL :: u32`:
all three emit without `pub` (a7=0, zig=0). And because everything lands in one
Zig file compiled as one object, even the function's `pub` changes nothing
observable.

SPEC 10.4 (`docs/SPEC.md:1528-1535`) states the opposite: "`pub` items are
exported from the file/module", "Non-`pub` items are file-private". Probes
`v05_private_struct.a7` (`Secret{v: 1}` from a non-`pub` struct in `p/priv.a7`)
and `v06_private_const_unqual.a7` (`SECRET`) are both a7=0 zig=0 — KNOWN PIP-7,
re-confirmed here.

Fix direction: MOD replaces `pub` with the `_` rule (ledger L27); packet P-MOD
must decide the fate of existing `pub` markers
(`docs/plan/execution.md:24,189`). **Changes an accepted, Zig-built program:**
yes — enforcing any visibility rejects v01, v05 and v06, which build today.
Needs owner approval; P-MOD owns it.

### VIS-7 (MEDIUM, NEW): the parser accepts `pub` on struct fields

SPEC 10.4 (`docs/SPEC.md:1534`): "**Struct fields are always file-private**
(cannot be marked `pub`)". `a7/parser.py:2059-2072` reads an optional `pub`
before each field and stores it on the `FIELD` node.

`v02_pub_field.a7` (`P :: struct { pub x: i32  y: i32 }`): a7=0, zig=0, and the
emitted struct is identical to one without the marker
(`out/v02_pub_field.zig`). The keyword is accepted and then discarded.

Ledger L29 (`docs/plan/decisions.md:64`) settles the semantics — "All struct
fields are visible to importers" — which contradicts SPEC 10.4's "always
file-private" as well. Both the parser's acceptance and the SPEC line need to
move to L29.

Fix direction: reject `pub` on a field with a located diagnostic, or drop the
SPEC sentence in favour of L29 and keep `pub` rejected as meaningless.
**Changes an accepted, Zig-built program:** yes (v02 builds today). Needs owner
approval; P-MOD.

### VIS-8 (MEDIUM, KNOWN PIP-7.5, new spelling class): a symlink to an already-imported module merges it twice

`seen_paths` in the merge is keyed by the import *string*
(`a7/compile.py:740-744`), not the resolved file, so any second spelling of the
same file merges its declarations again.

`p/link.a7` is a symlink to `p/helper.a7`. `m12_symlink.a7` imports both `link`
and `helper`: a7=6 with six `Already defined` errors
(`Constant 'LIMIT'`, `Struct 'Point'`, …). `m11_dotslash.a7` (`"./helper"` and
`"helper"`) gives the identical six (KNOWN PIP-7.5); the symlink is a spelling
that no string normalization can catch, since only `Path.resolve()` sees it.
`m06_two_alias.a7`, which imports `"helper"` twice under two aliases, is a7=0
zig=0 because the strings match.

Ledger L26 (`docs/plan/decisions.md:61`) makes a duplicate import an error "by
the same path, another spelling of it, or a second alias", so m06 should be
rejected too, and m11/m12 should say "duplicate import", not six name clashes.

Fix direction: key `seen_paths` and `loaded_modules` by `Path.resolve()`.
**Changes an accepted, Zig-built program:** yes for m06, which builds today and
L26 makes an error; no for m11/m12.

### VIS-9 (MEDIUM, NEW): case-only path differences behave differently per filesystem

`m09_case.a7` imports `"helper"` and `"Helper"`. On this case-sensitive
filesystem: a7=6,
`Module 'Helper' not found in search paths: ['.', 'stdlib', '/home/cx89/Projects/pl-dev/a7-py/stdlib']`.

On a case-insensitive filesystem (macOS default) both resolve to the same file.
`resolve_module_path` returns `str(candidate.resolve())`
(`a7/module_resolver.py:109`), which preserves the spelling the caller used, and
`_module_emit_prefix` (`a7/compile.py:570-572`) is case-preserving, so the two
would merge twice with prefixes `module_helper__` and `module_Helper__` — the
VIS-8 failure, reached only on some hosts. The same program would compile on
Linux and fail on macOS, or vice versa. **UNVERIFIED on macOS**: no
case-insensitive filesystem was available in this session; the mechanism is read
from the code.

Fix direction: normalize by `os.path.realpath` and reject a case-mismatching
spelling explicitly. **Changes an accepted, Zig-built program:** unknown
(host-dependent).

### VIS-10 (MEDIUM, KNOWN baseline failing tests #6 and #8, new detail: the caret is drawn on the wrong file's text): merged-module diagnostics render the imported file's span against the importer's source

Every declaration from an imported file is analysed with
`filename=str(input_path)` — the importer's path
(`a7/compile.py:268-271`) — while the span on the node still holds the imported
file's line and column. The formatter then draws the caret on the importer's
source lines.

`m01_chain.a7` (three-file chain), `--format json`
(`out/m01.json`):

```json
{"type": "TypeCheckError",
 "message": "m01_chain.a7:3:27: Undefined type (Identifier 'c')",
 "file": "m01_chain.a7",
 "span": {"start_line": 3, "start_column": 27, …}}
```

`c` exists only in `p/chainB.a7`, at its line 3 column 27. `m01_chain.a7:3:27`
is the closing `)` of `x := b.bee()` — a real token, wrongly blamed.

`d01_imported_semantic.a7` is worse: the span from `p/badsem.a7:2:25` is drawn
on the importer's line 2, which is only 20 characters long, so the underline runs
past the end of the line:

```
   2 ┃ b :: import "badsem"
     ┃                         └─────────────┘
```

The origin half is KNOWN: `test_pipeline_diagnostics.py::test_imported_semantic_error_preserves_origin_file`
is one of the 12 failing baseline tests (`docs/audits/2026-09-16/baseline.md:50`),
owned by CLI-02 (`docs/plan/execution.md:214,322`). The caret drawn on unrelated
source, and the underline past the end of a line, are not recorded anywhere.

Also KNOWN and failing:
`test_missing_import_diagnostic_locates_import_declaration`
(`baseline.md:48`) — `m14_missing.a7` confirms it: the message
`Error loading module 'nosuchmodule' imported by 'm14_missing.a7': …` carries no
line or column at all.

Fix direction: CLI-02's origin fields; a diagnostic must carry the file its span
belongs to. **Changes an accepted, Zig-built program:** no.

### VIS-11 (MEDIUM, KNOWN baseline failing test #7, new detail: the exit code is 8, not 5): a parse error in an imported file exits 8 (INTERNAL)

`d02_imported_parse.a7` imports `p/badparse.a7`, whose body is `ret ((( }`:

```
$ uv run a7 d02_imported_parse.a7 --output out/d02_imported_parse.zig; echo $?
Unexpected error: badparse.a7:2:28: Expected expression
8
```

Exit 8 is reserved for compiler faults; a syntax error in user source is exit 5.
`ModuleResolver.load_module` calls `Parser.parse()` at
`a7/module_resolver.py:160` inside `load_program_dependencies`, whose caller
catches only `SemanticError` (`a7/compile.py:247-250`), so the `ParseError`
escapes to the outer handler that tags INTERNAL.

The message does carry the right file and position, unlike VIS-10. KNOWN as
failing baseline test
`test_pipeline_diagnostics.py::test_imported_parse_error_is_a_source_failure_with_module_location`
(`docs/audits/2026-09-16/baseline.md:49`), owned by CLI-02.

Fix direction: catch `CompilerError` around module loading and route it through
`_finish_with_failure` with `ExitCode.PARSE`. **Changes an accepted, Zig-built
program:** no.

### VIS-12 (MEDIUM, NEW): rejected import paths are reported as "not found", not as rejected paths

`_is_safe_module_path` (`a7/module_resolver.py:64-74`) rejects null bytes,
backslashes, absolute paths and any `..` segment by returning `False` from
`resolve_module_path` (`:94-95`), which is indistinguishable from a missing
file.

| Probe | Import | a7 | Message |
| --- | --- | --- | --- |
| `m07_parent.a7` | `"../helper"` | 6 | `Module '../helper' not found in search paths: [...]` |
| `m08_abs.a7` | `"/etc/passwd"` | 6 | `Module '/etc/passwd' not found in search paths: [...]` |

SPEC 10.2 (`docs/SPEC.md:1495-1496`) says parent traversal is "rejected by the
resolver", which is true, but the user is told the file does not exist. Ledger
L30 (`docs/plan/decisions.md:65`) will *allow* `..` while the result stays inside
the root, so this message becomes wrong in a second way.

The search-path list in the message also exposes an absolute host path
(`/home/cx89/Projects/pl-dev/a7-py/stdlib`) in every missing-import diagnostic.

Fix direction: separate "path not permitted" from "module not found", each with
the import declaration's span. **Changes an accepted, Zig-built program:** no.

### VIS-13 (MEDIUM, KNOWN TYP-17, new detail: the internal `None` is printed): a Python `None` reaches a user diagnostic for an alias with a computed array size

`t20_alias_array_size_const.a7`:

```a7
N :: 4
Buf :: [N]i32
main :: fn() { b: Buf = [1, 2, 3, 4] }
```

a7=6, twice:

```
error: Type mismatch: expected '[None]i32', got '[4]i32' (Variable 'b' array …)
```

`extract_int_value` reads integer literals only, so a named size becomes `None`
(`a7/passes/type_checker.py:397`), and `ArrayType` formats it verbatim. The
false rejection is KNOWN TYP-17 (`docs/audits/2026-09-16/compiler/types.md:383`,
probe `d43_array_size_const_ident`); TYP-17 does not record that the internal
`None` is printed to the user. SPEC 3.4 (`docs/SPEC.md:374-376`) shows
`Vector :: [3]f32` only, so the literal case that works is the only documented
one.

Fix direction: TYP-17's — fold constant sizes, reject unresolved ones with a
message that names the expression. **Changes an accepted, Zig-built program:**
no.

### VIS-14 (LOW, NEW): `pub` is accepted on an import declaration

`a7/parser.py:472-481` sets `is_public=is_public` on the `IMPORT` node.
`v07_pub_import.a7` (`pub h :: import "priv"`) is a7=0 zig=0. SPEC 10.4's list of
what `pub` applies to (`docs/SPEC.md:1528-1532`) does not include imports, and
MOD states "imports are never re-exported" (`docs/plan/execution.md:66`), so the
marker is both unspecified and contrary to the decided design.

Fix direction: reject it, or keep it as an explicit re-export once MOD lands.
**Changes an accepted, Zig-built program:** yes (v07 builds). Needs approval;
P-MOD.

### VIS-15 (LOW, NEW): SPEC 10.4 omits type aliases from what `pub` applies to

`docs/SPEC.md:1528-1532` lists global functions, global variables and constants,
and "Type declarations (struct, enum, union)". A type alias is none of those,
yet `pub Handle :: u64` parses and emits (`v01_private_call.a7`, via
`p/helper.a7`). Either the list or the parser is wrong.

**Changes an accepted, Zig-built program:** no if the SPEC line is corrected;
yes if the parser starts rejecting it.

### VIS-16 (LOW, NEW): circular type aliases are detected only in the wrapper form

`register_type_alias` guards against cycles with `_resolving_type_aliases`
(`a7/passes/type_checker.py:198-213`). It fires for wrapper forms:
`t32_circ_array_alias.a7` (`A :: [3]B`, `B :: [3]A`) is a7=6,
`Circular type alias dependency involving 'A'`.

It cannot fire for identifier forms, because VIS-1 makes those constants:

- `t28_alias_self.a7` (`A :: A`): a7=0, zig=0, emitting `const A = A;`
- `t18_alias_circular.a7` (`A :: B`, `B :: A`): a7=0, zig=0, emitting
  `const A = B; const B = A;`

`zig build-obj` accepts both only because nothing references them; the moment
one is used, A7 rejects it first for the wrong reason —
`t23_circ_used.a7` (`x: A = 1`) is a7=6 with `Undefined type (Type 'A')`, the
VIS-1 message, not a cycle report.

Fix direction: falls out of VIS-1. **Changes an accepted, Zig-built program:**
yes — t18 and t28 build today (as dead declarations) and would be rejected.

### VIS-17 (LOW, NEW): `test_codegen_zig.py::test_type_alias` tests no type alias

```python
    def test_type_alias(self):
        # Type aliases are emitted when using struct/enum patterns
        source = '''
Point :: struct {
    x: i32
    y: i32
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const Point = struct' in zig
```

(`test/test_codegen_zig.py:722-731`.) The source contains a struct declaration,
not a type alias; the assertion duplicates struct codegen coverage under an
alias name. Against the Test quality rule in `CLAUDE.md`, it is a coverage
illusion: no alias form is exercised by any codegen test.

**Changes an accepted, Zig-built program:** no.

## Which module probes silently produce wrong code

Task item 2 asked which cases produce wrong code rather than a diagnostic. Three
groups, by what stops them.

| Group | Probes | What happens |
| --- | --- | --- |
| **Nothing stops it** (a7=0, zig=0, program is wrong) | `t27_alias_qualified.a7`, `g04_generic_type_qualified.a7` | the enclosing declaration is deleted; the emitted Zig has no `main` and `build-obj` still exits 0 (VIS-5) |
| | `v01_private_call.a7`, `v05_private_struct.a7`, `v06_private_const_unqual.a7`, `v10_reverse_leak.a7` | SPEC 10.4 visibility violated in both directions, silently (VIS-2, VIS-6) |
| | `m24_fn_then_alias.a7` | the import is discarded with no diagnostic (KNOWN PIP-18) |
| | `t18_alias_circular.a7`, `t28_alias_self.a7` | circular declarations emit as `const A = B; const B = A;` and build only because nothing uses them (VIS-16) |
| | `v02_pub_field.a7`, `v07_pub_import.a7` | `pub` accepted where SPEC 10.4 forbids it, then discarded (VIS-7, VIS-14) |
| **Only Zig stops it** (a7=0, zig=1) | `m13_bare_import.a7`, `m22_selected.a7` (PIP-20); `m16_same_alias_twice.a7` (PIP-18); `m20_private_internal.a7`, `g02_generic_fn_unqualified.a7` (PIP-6); `g01_generic_fn_qualified.a7` (VIS-4) | the A7 pipeline reports nothing; the failure is a Zig identifier or arity error naming generated names the user never wrote |
| **A7 stops it** (a7≠0) | every other probe in this report | correctly rejected, though VIS-3, VIS-10, VIS-11, VIS-12 and VIS-13 show the message is often the wrong one |

The middle group is the dangerous one for `--mode semantic` and `--mode pipeline`
users, who never run Zig: those modes exit 0 on all six.

## Known findings re-confirmed on this tree

Each was re-probed; none is filed again.

| Known ID | Claim | Probe on this tree |
| --- | --- | --- |
| PIP-7.1 | non-`pub` names callable through the alias | `v01_private_call.a7` a7=0 zig=0, calls `h.hidden()` |
| PIP-7.2 | imported structs and constants visible unqualified | `v05_private_struct.a7`, `v06_private_const_unqual.a7` both 0/0 |
| PIP-7.3 | importer reusing a module's name is rejected | `m21_global_before_import.a7` a7=6 `Already defined: Function 'work'`; `m18_module_has_main.a7` a7=6 `Function 'main'` |
| PIP-7.3 (new shape) | two modules' **private** helpers collide | `m23_two_private_same.a7` a7=6 `Already defined: Function 'priv'` |
| PIP-7.4 | two modules cannot share a function name | `m19_prefix_collide.a7` (`a_b.a7` and `sub/b.a7`, both `pub f`) a7=6 |
| PIP-7.5 | same file under two spellings merges twice | `m11_dotslash.a7` a7=6, six errors |
| PIP-7.6 | self-import | `m05_self.a7` a7=6 `Already defined: Function 'main'`, no import diagnostic |
| PIP-6 | module-internal calls lose the prefix | `m20_private_internal.a7` a7=0, zig=1 `use of undeclared identifier 'inner'` |
| PIP-6 (new shape) | an importer's **unqualified** call to an imported generic | `g02_generic_fn_unqualified.a7` a7=0, zig=1 `use of undeclared identifier 'identity'` |
| PIP-8 | transitive imports never merged | chain `m01_chain.a7` a7=6; diamond `m02_diamond.a7` a7=6; a module importing `std/io` `m15_transitive_std.a7` a7=6 |
| PIP-8 (new shape) | diamond where the root also imports D directly | `m03_diamond_direct.a7` a7=6 `Type is not callable (Unknown stdlib call 'dD.dee')` — the two middle modules' own `d.dee()` calls are never annotated |
| PIP-9 | alias-qualified calls are not type checked | `g01_generic_fn_qualified.a7` (see VIS-4) |
| PIP-17 | `--mode semantic` skips the merge | `uv run a7 v01_private_call.a7 --mode semantic` exit 6, `Unknown stdlib call 'helper.hidden'` (compile mode exits 0) |
| PIP-18 | duplicate alias accepted | `m16_same_alias_twice.a7` (`h` twice) a7=0, zig=1 `use of undeclared identifier 'module_priv__work'` — the last import wins the alias map |
| PIP-18 | function then alias of the same name accepted | `m24_fn_then_alias.a7` a7=0 zig=0, the import silently ignored |
| PIP-20 | named and bare file imports emit broken Zig | `m13_bare_import.a7` a7=0 zig=1; `m22_selected.a7` (`import "helper" { work }`) a7=0 zig=1 |
| MTH-6 | struct alias unresolvable | root cause found: VIS-1 |
| MTH-12 | qualified struct literal deletes `main` | two further shapes: VIS-5 |
| STD-7 | named `@type_set` alias is a codegen error | `t30_alias_typeset.a7`, `t33_typeset_ok.a7` (SPEC 7.3 constraint syntax) and `t34_typeset_cross.a7` all a7=7, `Zig backend: unsupported expression node 'TYPE_SET'` |
| TYP-17 | non-literal array sizes become `None` | `t20_alias_array_size_const.a7`; the printed `None` is VIS-13 |

## What the module redesign (MOD) already answers

Read from `docs/plan/execution.md:61-72` and ledger L25-L31
(`docs/plan/decisions.md:60-66`).

| Finding | Answered by MOD? | Where |
| --- | --- | --- |
| VIS-2 reverse name leak | yes | per-module scopes, `execution.md:66` |
| VIS-3 dead cycle detection | yes | Kahn sort, cycle reported with the chain, `execution.md:65` |
| VIS-5 `alias.Type` / `alias.Box(i32)` drops the declaration | yes | `parse_type` accepts both, `execution.md:67` |
| VIS-6 `pub` a no-op | partly | L27 replaces `pub` with `_`; the *fate of existing `pub` markers* is an open P-MOD question, `execution.md:24,189` |
| VIS-7 `pub` on struct fields | partly | L29 makes all fields visible; nothing says whether the marker is rejected |
| VIS-8 symlink double-merge | yes | worklist "keyed by real path", `execution.md:65`; L26 makes any second spelling an error |
| VIS-9 case-only paths | no | "keyed by real path" does not settle case folding on a case-insensitive host |
| VIS-10 diagnostic origin | yes | CLI-02 origin fields, which MOD keeps passing, `execution.md:72,214` |
| VIS-11 imported parse error exits 8 | yes | "tokenize, parse and read errors become located diagnostics for that module", `execution.md:65` |
| VIS-12 rejected paths reported as missing | partly | L30 allows `..` inside the root; the message wording is unassigned |
| VIS-4 generic call through an alias | partly | `alias.name` lowers "in value, type and generic positions" (`execution.md:69`); the missing comptime **type argument** is a type-checker gap (PIP-9), not a lowering one, and no batch names it |
| VIS-1 `Name :: OtherType` parsed as a constant | **no** | MOD says nothing about type aliases |
| VIS-13 `[None]i32` | **no** | TYP-17's fix batch, not MOD |
| VIS-16 circular aliases | **no** | follows VIS-1 |
| VIS-17 test quality | **no** | no batch |
| VIS-14 `pub` on an import | partly | "imports are never re-exported" (`execution.md:66`) decides the semantics, not the diagnostic |
| VIS-15 SPEC 10.4 omits aliases | **no** | a docs fix, no batch |

MOD also closes PIP-1, 6, 7, 8, 9, 10, 17, 20 and ZIG-27
(`docs/plan/execution.md:71`), which covers every KNOWN row above except MTH-6,
MTH-12's non-module half, STD-7 and TYP-17.

## What is missing

| Item | What exists now | What it needs | Decision owner | Priority for v1 |
| --- | --- | --- | --- | --- |
| Any visibility at all | `pub` parsed, read once for a Zig `pub fn` prefix (`zig.py:431`) | Per-module symbol tables; `alias.name` resolved against exported names only | P-MOD (L27 decides the rule; the fate of `pub` is open) | Must |
| Module namespaces | Flat concatenation, functions prefixed, types and constants not (`compile.py:730-759`) | Module structs `__a7_mN_stem` per `execution.md:69` | P-MOD | Must |
| Transitive imports | Direct imports only (PIP-8) | Worklist over the whole graph, keyed by real path | P-MOD | Must |
| Cycle diagnostics | Unreachable code (VIS-3) | Stack check before the cache, or Kahn sort; report the chain | P-MOD | Must |
| Type alias of a declared type | Parsed as a constant (VIS-1) | Parser or resolver change; SPEC 3.4 needs examples beyond primitives and arrays | none — no batch owns type aliases | Must |
| `alias.Type` in type position | Silently drops the declaration (VIS-5) | `parse_type` accepting a qualified head | P-MOD | Must |
| Generics reached through an alias | Type argument never inferred (VIS-4) | Specialization on the `file_module_call` path | none named; PIP-9 has no batch of its own | Should |
| Named type sets | Exit 7 at codegen (STD-7) | Backend handling, or a rule that a named set is a compile-time-only declaration | STD-7's batch | Should |
| Import diagnostics with origins | Importer's filename, imported file's span (VIS-10, VIS-11) | CLI-02's origin fields | CLI-02 | Must (4 failing baseline tests) |
| Duplicate-import rule | Two aliases of one path accepted (m06), two spellings rejected with six name clashes | L26 as a single located diagnostic | P-MOD | Should |
| Case-insensitive hosts | Untested, host-dependent (VIS-9) | Real-path normalization plus an explicit spelling check | none | Could |
| `pub` on struct fields | Accepted and discarded (VIS-7) | Reject, and reconcile SPEC 10.4 with L29 | P-MOD | Should |

## Checked and correct

- Path traversal and absolute paths are refused: `m07_parent.a7`,
  `m08_abs.a7` both a7=6 (the message is VIS-12, the refusal is right).
  `test_module_resolver.py:37-45` asserts the same through the API.
- Importing one file twice under two aliases with the same path string merges it
  once: `m06_two_alias.a7` a7=0 zig=0. (L26 will make this an error.)
- An alias that shadows a stdlib module name resolves to the local file:
  `m17_alias_is_stdname.a7` (`math :: import "helper"`) a7=0 zig=0, emitting
  `module_helper__work()`.
- `pub` is a parse error on locals, parameters and nested functions, as SPEC
  10.4 requires: `v03_pub_local.a7` a7=5 `Expected expression`;
  `v04_pub_param.a7` a7=5 `Expected type`; `v08_pub_nested.a7` a7=5. (The
  messages do not mention `pub`.)
- Alias of a primitive, a slice, a 1-D array, a 2-D array and a function type
  all work end to end: `t01`, `t05`, `t06`, `t07`, `t08`, each a7=0 zig=0.
- An alias is accepted as a parameter type (`t24_alias_param.a7`), a field type
  (`t12_alias_field.a7`), a cast target (`t13_alias_cast.a7`), a struct-literal
  head (`t14`), and declared inside a block (`t15_alias_in_block.a7`, emitting a
  Zig local `const Handle = u64;`) — all a7=0 zig=0.
- An alias is usable as a **return type** once the returned value has the
  alias's type: `t22_alias_ret_cast.a7` (`mk :: fn() Handle { ret cast(u64, 7) }`)
  a7=0 zig=0. The bare-literal form `t11_alias_return.a7`
  (`mk :: fn() Handle { ret 7 }`) is a7=6, `Return type mismatch: expected 'u64',
  got 'i32'` — but so is the control without any alias,
  `t21_ctl_u64_ret.a7` (`mk :: fn() u64 { ret 7 }`), with the identical message.
  The defect is integer-literal coercion in `ret`, not the alias; it is adjacent
  to KNOWN TYP-06 (`docs/audits/2026-09-16/compiler/types.md:208-210`, the
  `c47_literal_left_u8_right` asymmetry) and contradicts SPEC A.2
  (`docs/SPEC.md:2072`, "Integer literals to any integer type if in range"). Out
  of this audit's scope; filed as no finding here.
- `ref` is accepted as an alias right-hand side: `t25_alias_ref.a7`
  (`RI :: ref i32`) is a7=6 with `Return type mismatch: expected 'i32', got
  'ref i32'` — the alias resolved correctly and the rejection is about the
  missing auto-dereference in `ret r`, not the alias.
- Two aliases of the same primitive are interchangeable:
  `t17_alias_equality.a7` (`A :: u32`, `B :: u32`, `f(x: A)` called with a `B`)
  a7=0 zig=0. Aliases are structural, not nominal; nothing in SPEC says
  otherwise.
- Redeclaring a type name as an alias is rejected: `t16_alias_shadow_type.a7`
  a7=6 `Already defined: Type alias 'S'`.
- A primitive keyword cannot be aliased over: `t19_alias_prim_shadow.a7`
  (`u32 :: u64`) a7=5.
- A generic **type** declared in one file and used unqualified in another builds
  and is correct: `g03_generic_type_unqualified.a7` and `g05_generic_annot.a7`,
  both a7=0 zig=0.
- `test/test_module_alias_shadowing.py` is a real test: it builds and runs both
  Debug and ReleaseFast binaries and asserts which function's value the program
  prints (PL-02 / PIP-1). Its docstring states what it will need when L28 lands.

## Test gaps

- **No test compiles a multi-file program end to end through the merge.**
  `test_module_resolver.py` never calls `load_module` on a file module; its two
  stdlib tests assert observable facts (`file_path == "<stdlib:std/io>"`, a
  resolved qualified symbol) but only about virtual modules, and the third
  asserts path traversal returns `None` — observable and meaningful. Nothing
  covers the merge, prefixes, cycles, duplicates or transitive imports. KNOWN:
  `docs/audits/2026-09-16/compiler/pipeline.md:610`.
- **No test asserts anything about `pub`.** `grep -rn "pub " test/*.py` finds it
  as A7 fixture text in `test_cli_failures.py:155,186`,
  `test_pipeline_diagnostics.py:84,104`, `test_pipeline_artifacts.py:69` and
  `test_module_alias_shadowing.py:30`, where the marker is incidental to what
  each test asserts, and otherwise only as Zig assertions about `pub fn main`
  (`test_codegen_zig.py:288,513,969`). Nothing checks what `pub` means in A7.
  No example uses `pub` at all
  (`docs/plan/audit/language-audit-checklist.md:58`).
- **No test declares a type alias of a declared type** (VIS-1). The nearest,
  `test_semantic_functions.py:636 test_constants_are_not_usable_as_type_aliases`,
  asserts that `Size :: 1` is not a type — correct in itself, but it locks in
  the same parse path that swallows `Ctr :: Counter`, and no test separates the
  two.
- `test_codegen_zig.py:722 test_type_alias` tests a struct (VIS-17).
- **No test for an alias of an enum, a union, a generic instantiation, or another
  alias**; no test for an alias in a cast target or a struct-literal head.
  `grep -rn "TYPE_ALIAS\|type_alias" test/` returns nine hits, all parser or
  function-type-alias cases plus one `test_no_recursion.py` allowlist entry.
- **No test for generics across modules** (VIS-4), the pair
  `docs/plan/audit/language-audit-checklist.md:101` flags.
- **No test for an import cycle, a self-import, a symlinked module, a
  case-differing path, or a diamond.**
- Four failing baseline tests already cover the diagnostic-origin half
  (`docs/audits/2026-09-16/baseline.md:47-50`); none covers the caret drawn on
  the wrong file's text (VIS-10).

## Not verified

- VIS-9 on a case-insensitive filesystem. No macOS or case-insensitive mount was
  available; the double-merge there is read from
  `module_resolver.py:98-111` and `compile.py:570-572`, not observed. **INFERENCE.**
- Whether a symlink whose target lies outside the search root is caught by
  `_is_within_search_path` (`module_resolver.py:76-78`, which calls `.resolve()`
  and should catch it) — not probed.
- No probe was executed. Every `zig` result is `build-obj -fno-emit-bin`; runtime
  behaviour of the accepted programs (v01, v05, v06, v10, m17, g03, g05, t14,
  t17) is **UNVERIFIED** beyond compiling.
- Whether the C1, C4 or C2 worktrees under `/home/cx89/Projects/pl-dev/a7-wt/`
  change any result. Not read.
- `a7/passes/name_resolution.py` computes a symbol table for each imported module
  at `module_resolver.py:162-166` and never reads `name_pass.errors`; I did not
  find a program where that discarded list would have contained an error the
  merged pass does not re-find, so I file no finding for it.
- `--mode doc` and `--mode ast` against multi-file programs were not exercised
  beyond the single `g04` AST dump, which returned no declarations list in the
  JSON schema and so did not confirm the drop independently of the emitted Zig.

claims checked: 104

(38 distinct file:line citations read in this session, 74 probe runs recorded as
A7/Zig exit-code pairs in `tmp/audit/2026-09-18/visibility/out/*.summary` over 97
probe files in `tmp/audit/2026-09-18/visibility/p/`, and 4 grep results quoted
with their outcome.)
