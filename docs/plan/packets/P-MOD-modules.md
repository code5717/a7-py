# P-MOD: file modules and compatibility

L69 approved implementation of L25-L31 on 2026-10-04, including separate
file scopes. The measurements and examples below remain the dated
2026-09-20 proposal evidence. They do not describe every current compiler path.
Importer-relative resolution and canonical loader identity now have focused
checks; complete semantic module isolation remains unfinished.

The additional proposals to remove directory fallback, reject alias-free
imports, impose an import-depth limit, or change initialization order remain
unapproved. Keep current behavior for those choices until their compatibility
impact receives a disposition. The [ledger](../decisions.md) and
[roadmap](../delivery-roadmap.md) separate approval from implementation evidence.

The original source fixtures, commands and results remain in the
[module probe evidence](../../audits/2026-09-20-v1-foundations/module-packet-probes/results.json).

## Approved direction and unresolved details

The [ledger](../decisions.md), L25-L31, establishes these rules:

- A file is a module. Access another file's names through its import alias.
- Importing the same file twice in one file is an error, including alternate
  spellings or aliases. Different files can import the same module.
- Top-level `_name` is private; other top-level names are public. `__name` is
  reserved for the compiler.
- A local cannot reuse an import alias. Struct fields remain visible across files.
- Resolve imports relative to the importing file. `..` cannot escape the main
  file's folder.
- Bare stdlib names such as `"io"` and `"math"` remain reserved for the stdlib.

The [MOD design](../execution.md#module-design-mod) additionally proposes uniform
module scopes, qualified types, iterative loading, cycle rejection and one Zig
struct per module. This packet separates those proposals from current behavior.

Here, a *bare import statement* means `import "helper"` without an alias. It is
not the approved stdlib shorthand `io :: import "io"`.

## Behavior measured on 2026-09-20

Eleven small fixtures contain only integer constants, integer-returning functions
and printing. All native builds ran serially with Zig Debug. Seven fixtures built
and ran. Two reached Zig and failed; two failed before Zig. Compiler Python file
hashes remained unchanged. No ReleaseFast or corpus-wide compatibility scan ran.

| Fixture | A7 exit | Zig exit | Native stdout | Proposed effect |
| --- | --- | --- | --- | --- |
| `public_qualified` | 0 | 0 | `7` | Preserve qualified public calls. |
| `private_qualified` | 0 | 0 | `7` | Reject cross-file `_value` access, even if marked `pub`. |
| `unqualified_leak` | 0 | 0 | `7` | Reject leaked `VALUE`; require `h.VALUE`. |
| `reserved_name` | 0 | 0 | `9` | Reject the user binding `__user_value`, if reservation covers locals. |
| `alias_local` | 0 | 0 | `9` | Reject local `h` that reuses import alias `h`. |
| `directory_fallback` | 0 | 0 | `7` | Reject implicit `pkg/mod.a7` fallback under the recommendation below. |
| `bare_import` | 0 | 0 | `1` | Reject alias-free import statements under the recommendation below. |
| `named_import` | 0 | 1 | Not run | Replace generated-Zig failure with a deliberate unsupported-form diagnostic. |
| `using_import` | 5 | Not run | Not run | Keep unsupported; provide a direct diagnostic and alias rewrite. |
| `sibling_call` | 0 | 1 | Not run | Make a module's call to its own helper work. |
| `duplicate_aliases` | 6 | Not run | Not run | Keep rejection; identify duplicate canonical module instead of leaked-name collisions. |

Six additional compiler-only probes from the independent review were rerun by
the controller. No native builds ran for these failing inputs. Their
[results](../../audits/2026-09-20-v1-foundations/module-packet-probes/controller-verification.json)
and [complete sources and outputs](../../audits/2026-09-20-v1-foundations/module-packet-probes/reviewer-source-results.tar.gz)
record the following gaps.

| Fixture | A7 exit | Current diagnostic |
| --- | --- | --- |
| `depth2`, `depth5` | 6 | A non-entry module's qualified call reports an undefined import alias. |
| `iso_const` | 6 | A non-entry module's qualified constant access reports undefined `b`. |
| `iso_type` | 6 | An imported file's qualified field type produces `Expected IDENTIFIER, got DOT`. |
| `pip18` | 6 | A global binding reused as an import alias fails later field/type checks, without a direct alias-clash diagnostic. |
| `mth12` | 5 | A module-qualified struct literal produces `Expected type`. |

These failures establish the tested cases, not a claim that every import chain
of length two or greater fails. Loading an unused dependency and using a name
through that dependency are separate requirements.

These are measured compatibility witnesses, not counts of all affected programs.
The original import-cycle probe now exits 6, while the original 1,100-module chain
still exits 8 with `RecursionError`. Separate evidence is in
[the original-probe results](../../audits/2026-09-20-v1-foundations/original-probes/results.json).

## Concrete examples

Each example lists complete file contents. Current measurements refer to the
named fixture above. Proposed sources are complete acceptance fixtures for the
future implementation; they are not claimed to execute correctly today.

### Public access and the `pub` transition

Current `public_qualified`, prints `7`:

```a7
// helper.a7
pub value :: fn() i32 { ret 7 }
```

```a7
// main.a7
io :: import "std/io"
h :: import "helper"
main :: fn() { io.println("{}", h.value()) }
```

Proposed canonical `helper.a7`, with the same `main.a7` and output:

```a7
value :: fn() i32 { ret 7 }
```

Recommendation: retain `pub` as a redundant accepted marker for V1. It never
changes underscore visibility. `pub _value` stays private. Do not warn on stderr
by default or schedule removal without a separate compatibility decision.

Alternative: reject every `pub` immediately. That forces needless changes to
working public declarations. Retaining `pub` as an access-control override is
rejected because it contradicts L27.

### Private access and leaked globals

Current `private_qualified`, prints `7`:

```a7
// helper.a7
pub _value :: fn() i32 { ret 7 }
```

```a7
// main.a7
io :: import "std/io"
h :: import "helper"
main :: fn() { io.println("{}", h._value()) }
```

Proposed: reject `h._value()` at that access with a private-declaration diagnostic.
If cross-file access is intended, rename `_value` to `value` in both files. If it
is internal, expose a public wrapper in `helper.a7` that calls `_value` there.
The wrapper behavior also requires the sibling-call repair below.

Current `unqualified_leak` uses these files and prints `7`:

```a7
// helper.a7
VALUE :: 7
```

```a7
// main.a7
io :: import "std/io"
h :: import "helper"
main :: fn() { io.println("{}", VALUE) }
```

Proposed: reject the unqualified `VALUE`; replacing it with `h.VALUE` prints `7`.
No compatibility alias should keep imported declarations in the caller's scope.

### Alias and reserved-name conflicts

Current `alias_local` prints `9`:

```a7
// helper.a7
pub value :: fn() i32 { ret 7 }
```

```a7
// main.a7
io :: import "std/io"
h :: import "helper"
main :: fn() { h := 9; io.println("{}", h) }
```

Proposed: reject the local declaration of `h`, with both declaration locations.
Rename the local to `count`; then the output remains `9`.

Current `reserved_name` prints `9`:

```a7
io :: import "std/io"
main :: fn() {
    __user_value := 9
    io.println("{}", __user_value)
}
```

Proposed: rename the binding to `user_value`, preserving output. Recommendation:
reject `__` names at every user declaration site, including locals, parameters,
fields and import aliases. The ledger clearly reserves the prefix but the full
site coverage and rejection of existing working programs need this disposition.
Do not silently mangle user `__` names into allowed names.

### Module-internal calls and qualified types

Current `sibling_call` exits 0 in A7 but Zig reports an undeclared helper:

```a7
// helper.a7
helper :: fn() i32 { ret 7 }
pub value :: fn() i32 { ret helper() }
```

```a7
// main.a7
io :: import "std/io"
h :: import "helper"
main :: fn() { io.println("{}", h.value()) }
```

Proposed: the same files build and print `7`; `helper()` resolves inside its own
file. No flattened-prefix workaround belongs in A7 source.

Proposed complete qualified-type fixture:

```a7
// geometry.a7
Point :: struct { x: i32 }
```

```a7
// main.a7
io :: import "std/io"
g :: import "geometry"
main :: fn() {
    p: g.Point = g.Point{x: 7}
    io.println("{}", p.x)
}
```

Expected output is `7`. This proposed fixture has not been compile-qualified.
Struct/enum/union identity includes its declaring module, so another file's
`Point` is a different type even with identical fields. Imported fields remain
visible under L29. Qualified generic types need separate instantiation evidence.

### Import forms and directory lookup

Current `directory_fallback` prints `7` with `pkg/mod.a7` containing the same
`pub value` function as above and this main file:

```a7
io :: import "std/io"
h :: import "pkg"
main :: fn() { io.println("{}", h.value()) }
```

Recommendation: remove implicit directory fallback. Rewrite the import as
`h :: import "pkg/mod"`, retaining an ordinary file module. This explicit-path
rewrite is proposed and has not been run in this packet. Keeping fallback is a
possible compatibility alternative, but makes `"pkg"` ambiguous when both
`pkg.a7` and `pkg/mod.a7` exist. If retained, precedence must be specified.

Current `bare_import` prints `1`:

```a7
// helper.a7
pub value :: fn() i32 { ret 7 }
```

```a7
// main.a7
io :: import "std/io"
import "helper"
main :: fn() { io.println("1") }
```

Recommendation: accept only aliased file imports. Rewrite the middle line as
`h :: import "helper"`; the program must still print `1`. Reject named imports
such as `import "helper" { value }` and `using import "helper"` with a direct
unsupported-form diagnostic. Their rewrite is an alias plus qualified uses.
Keeping named imports as copied local bindings would undermine the approved
always-qualified access rule.

## Remaining decisions requested

| Item | Recommendation | Compatibility impact and alternative |
| --- | --- | --- |
| M-PUB | Accept existing `pub` as redundant throughout V1; underscore wins. | Working public files remain accepted. Alternative is immediate removal. |
| M-RESERVED | Reject user `__` declarations at all binding/declaration sites. | The measured local example stops compiling. Alternative is a narrower top-level-only reservation, with additional collision handling. |
| M-FORMS | Reject bare, named and `using` file imports; require aliases. | The measured bare-import program stops compiling. Named/using examples measured here already fail before native execution. |
| M-DIRECTORY | Remove `x/mod.a7` fallback; permit explicit `x/mod` file paths. | The measured fallback program needs its path changed. Alternative retains fallback with an explicit precedence rule. |
| M-DEPTH | Maximum longest import chain is 32 edges; the entry file has depth 0. Check with an iterative graph algorithm and report the offending chain. | The tested two- and five-edge chains already fail qualified use in non-entry modules. A 32-edge cap could additionally reject currently accepted graphs; no complete scan identifies those graphs yet. Alternative is no semantic depth limit with separate finite resource budgets. |
| M-BOUNDARY | Approve measured compatibility breaks from L25-L31: private cross-file access, leaked unqualified names and local alias shadowing. | Measured working programs need the explicit rewrites above. Approved direction is preserved; this records its concrete breaking effects. |

Cycle rejection is already current behavior for the tested cycle. Preserve it,
with a complete chain and relevant import spans. Imports are not re-exported;
`a.b.value` must not expose `b` merely because `a` imports it. This rule is in the
proposed MOD design and needs coverage in compatibility review.

Proposed internal layout is one Zig struct per module, including the entry file,
with a root `main` trampoline and deterministic discovery order. Generated names
are not proposed as a public ABI. Keeping single-file programs flat would create
two lowering paths. Layout is an implementation choice, but the compatibility
scan must identify tooling that relies on current emitted names. This packet
does not settle a native ABI or module initialization order; observable
initializer ordering needs concrete examples before any affected change.

## Acceptance and compatibility evidence still required

1. Execute every proposed positive fixture through installed tooling in Debug
   and ReleaseFast. Compare stdout, stderr and exit codes with the stated result.
   Each negative fixture must fail before Zig output with both use and declaration
   locations where relevant.
2. Scan existing working examples/tests and recorded user programs before changing
   semantics. Report programs changed by private names, `pub`, `__`, import forms,
   local and global alias clashes, realpath duplicates, directory lookup and depth. These eleven
   probes are not that scan. Do not treat programs that only pass A7 as working
   unless their Zig build and defined native behavior also pass.
3. Verify separate files can use the same private helper/type names without leaks
   or collisions. Check cross-module calls for arity, argument/result types and
   generic specialization. Reject interchange of same-spelled distinct types.
4. Verify duplicate canonical imports through `./`, `..` and symlinks, plus a
   diamond whose different importing files share one dependency. State hardlink
   identity policy before claiming every same-file spelling is covered.
5. Verify relative imports from nested importers, permitted `..`, and rejection
   of paths or symlinks that escape the root folder. Preserve bare stdlib names
   and `std/` names. Do not introduce a local-file override for `io` or `math`.
6. Test direct and indirect cycles, chain depth 31/32/33, diamonds with different
   path lengths, and a deep acyclic input at Python recursion limit 100. No
   `RecursionError`, repeated module compilation or recursion scanner exception.
7. Check semantic, compile, pipeline and doc modes use the same module graph and
   origin information. Retain source/output alias protections for every loaded
   file and truthful artifact reporting after failure.
8. Compare deterministic emitted Zig under different hash seeds and checkout
   paths. Check entry-file `main`, non-entry `main`, qualified generics and module
   helper calls against native outputs. Do not expose internal generated names
   as stable public contracts.

Approval should record the selected M-* dispositions in the ledger. Any declined
item pauses its dependent change. The packet does not approve memory, numeric,
concurrency or native-ABI semantics.
