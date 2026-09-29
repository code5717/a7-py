> **Source:** Claude Explore subagent, research on Odin, Zig, Go and Jai module systems from primary sources, with a recommendation for A7, 2026-09-16.  
> **Date:** 2026-09-16.  
> **Status:** Evidence. Body preserved verbatim. The user decided differently on two points: visibility uses a leading underscore for private names instead of `pub` (the research recommended `pub`), and importing the same file twice in one file is an error (the research proposed allowing two aliases). Bare stdlib names stay (the research proposed removing them). See `docs/plan/decisions.md`.

# Module design for A7: what Odin, Zig and Go do, and a recommendation

## Short answer
Don't copy Odin's directory packages. Keep A7's one-file-is-one-module model and its `alias :: import "path"` syntax. Then fix the rules around it, borrowing mostly from Zig and Go:

- **Names:** always written as `alias.name`, and the alias is a normal name in file scope.
- **Visibility:** `pub` is enforced, as the SPEC already says.
- **Cycles:** not allowed.
- **Same file imported twice:** recognised by its real path.
- **Paths:** resolved relative to the importing file.
- **Stdlib:** `std/` is reserved for it.
- **Unsupported import forms:** rejected.

**Output:** still one Zig file, but each module becomes its own Zig struct, and the root holds only runtime helpers and a `main` that calls the main module's `main`. This is how Zig treats files, done inside one file, so calls between a module's own functions need no renaming. `mod.Type` and `mod.Box(i32)` then work with no special cases.

---

## 1. Primary sources

### Odin
Sources: overview https://odin-lang.org/docs/overview/ and the compiler source at commit `d6887133` (2026-09-16).
- **A package is a directory:** "A package is a directory of Odin code files, all of which have the same package declaration at the top… Each .odin file *must* have the same package name. A directory cannot contain more than 1 package."
- **Imports and collections:** "The `core:` prefix is used to state where the import is meant to look; this is called a library collection. If no prefix is present, the import will look relative to the current file."
  - The default import name "will be determined by the last element in the import path". An alias is written `import foo "core:fmt"`.
  - Built-in collections are `base`, `core` and `vendor` (`src/main.cpp:3878-3880`).
  - User collections come from `-collection:<name>=<filepath>`, used as `import "shared:foo"` (`src/main.cpp:2861-2866`).
- **Visibility:** "All declarations in a package are public by default."
  - `@(private)` is the same as `@(private="package")`.
  - `@(private="file")` limits a name to one file.
  - "`#+private` before the package declaration will automatically add `@(private)` to everything in that file… `#+private file` will be equivalent to… `@(private="file")`."
- **`using import` is removed.** `src/parser.cpp:5819`: `"'using import' is not allowed, please use the import name explicitly"`.
- **Cycles are forbidden.** `src/checker.cpp:6244`: `"Cyclic importation of '%.*s'"`, followed by the chain as `"'%s' refers to"` lines. `import` is also only allowed at file scope (`parser.cpp`: "Cannot use 'import' within a procedure").
- **Symbol names** get a package-name prefix plus a separator (`src/name_canonicalization.cpp:574-624`). Private-to-file names also get the file name.
- I found no primary source for how Odin splits compilation across packages, so I make no claim about it.

### Zig 0.16.0
Source: https://ziglang.org/documentation/0.16.0/
- **`@import`:** "If target refers to a Zig source file, then @import returns that file's corresponding struct type, essentially as if the builtin call was replaced by `struct { FILE_CONTENTS }`." The path is "relative… from the file containing the @import call".
- **Files are structs:** "Every Zig source file is implicitly a struct declaration."
- **Cycles:** "dependency loops between modules are allowed". Analysis is lazy (File and Declaration Discovery): "If a reference to a named declaration… is analyzed, the declaration being referenced is analyzed. Declarations are order-independent… or even in another file entirely."
- **`pub`:** "makes the declaration available to reference from a different file than the one it is declared in." This is per file. The `@hasDecl` example says a private decl is visible "because this test is in the same file scope". So once A7 emits one Zig file, Zig cannot enforce A7's `pub`; A7 has to.
- **No hiding of names:** "Identifiers are never allowed to 'hide' other identifiers by using the same name."
- **`usingnamespace` removed** (0.15.1 notes, https://ziglang.org/download/0.15.1/release-notes.html): "By eliminating this feature, all identifiers can be trivially traced back to where they are imported".

### Go
Sources: https://go.dev/ref/spec and https://go.dev/doc/go1.4#internalpackages
- **Packages:** a package is "constructed from one or more source files"; "An implementation may require that all source files for a package inhabit the same directory."
- **Exports:** a name is exported if "the first character… is a Unicode uppercase letter… and the identifier is declared in the package block".
- **Cycles and unused imports:** "It is illegal for a package to import itself, directly or indirectly, or to directly import a package without referring to any of its exported identifiers."
- **Dot import:** `import . "p"` puts the exported names directly into the file (Go's version of `using import`).
- **Internal packages:** "a package .../a/b/c/internal/d/e/f can be imported only by code in the directory tree rooted at .../a/b/c." This is a rule of the `go` tool, not of the language.

### Jai (unverified)
Jai has no public official docs. Community sources only: https://jai.community/t/import-and-load/181 and https://github.com/Ivo-Balbaert/The_Way_to_Jai.
- `#import` loads a module from the modules directory. A module is one file or a folder with `module.jai`.
- `#load` pastes a file in, and it shares the importer's global scope.
- `#scope_file` and `#scope_export` control visibility.

---

## 2. New facts from the repo that affect the design
1. **`mod.Type` in a type position isn't parsed, and the error is swallowed.** `parse_type` (`a7/parser.py:869-895`) only accepts a bare IDENTIFIER. In probe `tmp/audit/compiler/pipeline/probes/m08_type_position.a7` (`p: h.Point = h.Point{x: 1}`), the JSON AST has `FUNCTION work, inner, outer, takes, STRUCT Point, CONST LIMIT, ENUM Color, IMPORT, IMPORT`, with no `main`. Compilation still exited 0. Adding qualified types is therefore new ground and breaks no program that compiles today.
2. **Nesting only the imported modules as structs fails in Zig.** I checked with `zig ast-check` 0.16.0 on stdin (no files written):
   - Root `const work = 1;` plus `M = struct { pub const work = 2; fn inner() i32 { return work; } }` gives `error: ambiguous reference`.
   - Root `const count = 1;` plus a local `const count` inside a function in `M` gives `error: local constant shadows declaration of 'count'`.
   - So the main file must be wrapped as well. The full sketch in section 4 passes `ast-check`. I did not run Zig's semantic analysis (`build-obj`), because it writes cache files; that part is unverified.
3. **Backend names at the root are not reserved.** The backend emits `const std = @import("std");` and `const allocator = …` (`a7/backends/zig.py:157-159`). The tokenizer allows identifiers that start with `_` (`a7/tokens.py:329-330`), although SPEC 2.3's grammar line says an identifier must start with a letter.
4. **The SPEC contradicts itself on struct fields.** SPEC 10.4 says "Struct fields are always file-private (cannot be marked `pub`)", but the grammar says `field = "pub"? identifier ":" type`. If fields are private to their file, an imported `h.Point` can't be built or read. The owner needs to decide this.
5. **Unused and duplicate machinery.** `ModuleResolver.topological_sort` (`a7/module_resolver.py:310-350`) and `UNSUPPORTED_IMPORT` (`a7/errors.py:90`) exist and are never used. Nothing in `examples/`, `test/` or `docs/` imports bare `"io"` or `"math"`.

---

## 3. Recommendations
Each item gives current vs proposed behavior and says whether a program that compiles and builds today would change.

**R1. Unit of modularity: one file (keep SPEC 10.1).** Drop the `x/mod.a7` directory fallback (`module_resolver.py:104`). Today, if both `x.a7` and `x/mod.a7` exist, the first one silently wins.
- Why not directories: the output is one program, and Python-style users expect a file to be a module. Odin needs a third visibility level (`@(private="file")`) only because its packages span several files. With file modules, A7 has exactly two levels: `pub` and private to the file.
- Changes compiling programs? Only for anyone using `x/mod.a7` (none in the repo). Needs approval.

**R2. Paths resolve relative to the importing file, as in Odin and Zig.**
```a7
// main.a7
geo :: import "shapes/geo"
// shapes/geo.a7
vec :: import "vec"   // today: looks next to main.a7 and is never merged (PIP-8)
                      // proposed: shapes/vec.a7
```
- Keep the project root as the main file's directory. Optionally allow `..` as long as the result stays under that root (`_is_within_search_path` already exists). Allowing `..` relaxes SPEC 10.2 and needs approval.
- Remove the `stdlib/` search paths that don't exist (`compile.py:241-242`).
- Changes compiling programs? No. Transitive imports never compiled.

**R3. A module is identified by its real path.** Key `loaded_modules` and the merge by `Path.resolve()`, not by the import string (today: `module_resolver.py:124,187`, `compile.py:609`).
```a7
a :: import "./modhelper"
b :: import "modhelper"
// today: exit 6, seven "Already defined" errors
// proposed: one module with two aliases (Go also allows this)
```
- A file that imports itself is reported as a cycle (R6).
- Changes compiling programs? No (rejected today, accepted after).

**R4. Names from a module are always written `alias.name`. The alias is a file-scope `MODULE` symbol found by normal scope lookup, and imports are never re-exported.**
```a7
h :: import "flat"
main :: fn() {
    p := Point{x: LIMIT}   // today: accepted (leak, PIP-7.2); proposed: error "Point is not defined; did you mean h.Point?"
    q: h.Point = h.Point{x: h.LIMIT}   // today: main silently dropped; proposed: works
    h := Ops{work: two}    // proposed: error "local 'h' hides import alias 'h' (flat.a7)"
}
```
- **Shadowing an alias:** I recommend an error, following Zig's rule that a name always means one thing. The softer option is to let the local win by scope; either fixes PIP-1.
- **Stdlib calls:** recognise `io.println` as stdlib only when `io` resolves to a MODULE symbol whose path is a virtual `std/` module. Delete the checks that match the text `io` or `math.`.
- Changes compiling programs? Yes: f02 is rejected, and f03 is either rejected or prints `2 2` instead of `1 2`. Needs approval.

**R5. Visibility: enforce `pub` as SPEC 10.4 says; don't switch to Odin's public-by-default.**
```a7
// flat.a7
hidden :: fn() i32 { ret 2 }
// main.a7
h.hidden()   // today: exit 0 and Zig builds (f01); proposed: "'hidden' is private to flat.a7; add pub"
```
- Why: the SPEC and the existing test (`pub double`) already use `pub`. The API is visible at the declaration, and the error message tells the user exactly what to do.
- Fields: I recommend that fields of a `pub` type are accessible, as in Zig and Odin, and that the SPEC 10.4 sentence about private fields is removed (owner decision, see section 2 item 4).
- Changes compiling programs? Yes (f01). Needs approval; gate G6.

**R6. Import cycles are errors, reported with the whole chain (Odin, Go).**
```a7
// cyc_a.a7:  b :: import "cyc_b"
// cyc_b.a7:  a :: import "cyc_a"
// today: exit 0, cyc_b never emitted
// proposed: "import cycle: main.a7 -> cyc_a.a7:1 -> cyc_b.a7:1 -> cyc_a.a7"
```
- Why forbid when the struct lowering could handle cycles, as Zig does: it fits A7's ban on recursion and gives a fixed order for checking and emitting. It could be relaxed later without backend changes.
- Import depth 32 (SPEC appendix C) should mean the longest import chain from the main file, computed after sorting so it doesn't depend on discovery order.
- Changes compiling programs? Yes (m10). Needs approval.

**R7. Stdlib: `std/` is a reserved prefix, and the bare `io` and `math` names are removed** from `STDLIB_MODULE_ALIASES` (`a7/stdlib/__init__.py:11-16`).
```a7
io :: import "io"       // today: the stdlib module; a local io.a7 can't be imported (PIP-32)
                        // proposed: the local io.a7
io :: import "std/io"   // unchanged
```
- A local `std/` directory can never be imported, and the error message should say that.
- Changes compiling programs? Only programs that write bare `import "io"` (none in the repo corpus, but SPEC 10.3 documents it). Needs approval.

**R8. No `using import`. Named `{…}` imports and bare `import "m"` are errors for now.**
```a7
import "modhelper" { work }   // today: exit 0 with broken Zig (PIP-20)
                              // proposed: UNSUPPORTED_IMPORT "write w :: import \"modhelper\" and call w.work()"
```
- Drop `using import` from the SPEC. Odin forbids it (`parser.cpp:5819`) and Zig removed `usingnamespace` for traceability. Go still has `.` imports.
- The parser currently sets `is_using` (`parser.py:375-379`), so it must also be rejected during semantic checks.
- Optional later change: default the alias to the last path segment, as Odin does. That is new syntax and needs approval (L22).
- Changes compiling programs? Only bare imports used just for leaked types or constants. Needs approval.

**R9. One path for all modes.** Load and bind modules in `semantic`, `pipeline`, `compile` and `doc` modes alike (today only codegen modes do it, `compile.py:252-253`). Calls through an alias are then type-checked like any other call (PIP-9).
- Changes compiling programs? No.

**R10. Reserve the `__a7_` prefix.** Reject user identifiers that start with `__a7`. Rename the root `std` and `allocator` to `__a7_std` and `__a7_allocator`.
- Changes compiling programs? Only programs that use `__a7…` names. Needs approval (likely none exist).

---

## 4. Lowering to one Zig file
Each module becomes a struct: `__a7_m{id}_{stem}`.
- `id` is 0 for the main file, then counts up in discovery order (breadth-first over imports in source order), so names are stable between runs.
- `stem` is the file stem with characters outside `[A-Za-z0-9_]` turned into `_`. The number makes names unique. Today's scheme is not: `a_b` and `a/b` both become `module_a_b__`.

All top-level declarations of every kind (functions, structs, enums, unions, constants, globals) keep their A7 names inside their module's struct.

```zig
const __a7_std = @import("std");
var __a7_io: ?__a7_std.Io = null;
fn __a7_stdout_print(comptime f: []const u8, a: anytype) void { ... }

const __a7_m0_main = struct {
    pub const Point = struct { x: i32 };          // main's own Point
    pub fn work() i32 { return 2; }
    pub fn main() void {
        const b: __a7_m1_util.Box(i32) = .{ .value = __a7_m1_util.outer() };
        const p: __a7_m1_util.Point = .{ .x = __a7_m1_util.LIMIT };
        const q: Point = .{ .x = work() };        // own names stay unqualified
        __a7_stdout_print("{} {} {}\n", .{ b.value, p.x, q.x });
    }
};
const __a7_m1_util = struct {
    pub const Point = struct { x: i32 };          // no clash with main's Point
    pub const LIMIT = 5;
    pub fn Box(comptime T: type) type { return struct { value: T }; }
    fn inner() i32 { return 1; }
    pub fn outer() i32 { const work: i32 = inner(); return work; }  // PIP-6 fixed, no renaming
};
pub fn main(init: __a7_std.process.Init) void { __a7_io = init.io; __a7_m0_main.main(); }
```
This passed `zig ast-check` 0.16.0. Zig's semantic analysis and a build were not run.

How references lower:
- **A module's own names:** a bare identifier bound to its own top-level declaration is emitted bare. Zig finds it in the enclosing struct.
- **`alias.name`:** in a value, type or generic position (`h.work()`, `h.Point`, `h.Box(i32)`, `h.identity(7)`), it becomes `__a7_m{target}_{stem}.name`, with the existing generic lowering applied to the member. The name resolver writes `(module_id, decl_name)` onto the node, so the backend never guesses from text.
- **Types the user didn't spell out:** if the backend has to write a type from `type_map` (for example `p := h.make()`), it always writes the owner-qualified name `__a7_mN_stem.Point`. That is valid anywhere, because root names are visible inside every struct. In the type checker, a struct, enum or union is identified by `(module_id, name)`, so two `Point`s are different types.
- **Main:** the main module's `main` is called from a root trampoline (a generalised version of today's `__a7_user_main`). A `main` in any other module is an ordinary function, which fixes m21.
- **`pub`:** A7 `pub` is copied into the Zig for readability only. Zig does not enforce it inside one file, so A7 does (R5).
- **Lazy analysis:** Zig skips unreferenced declarations. Unused module code costs nothing, but backend bugs in unused code won't show up in Zig. Backend tests should reference every declaration.
- **Single-file programs:** if the owner wants their generated Zig to stay byte-identical, emit the main module at the root when there are no file imports. Program behavior is the same either way.

**Loading and resolution, without recursion:**
1. **Discover.** A worklist of `(path, importer_id, span)`, keyed by real path. Parse each file once. Tokenizer, parse and decode errors become located diagnostics for that module (this also covers PIP-11). Resolve each import relative to the importer, or as a virtual `std/…` module. Record edges with their spans.
2. **Order.** Run the existing Kahn sort. Any modules left over are in a cycle. Find one with an iterative DFS (explicit stack, white/grey/black marks) and report the chain with spans. Compute the longest chain and check it against the depth limit of 32.
3. **Declare.** Give each module its own file scope with its top-level declarations. Duplicates are checked within that module only. Bind each alias as a MODULE symbol; an alias that clashes with a declaration is ALREADY_DEFINED (covers PIP-18 n09).
4. **Check.** First record signatures for all modules, then check all bodies. Look up `X.name` by scope. If X is a MODULE, look in the target module's top-level scope and apply the `pub` check. Then type-check it as a normal call or type.
5. **Emit** the structs in sorted order.

---

## 5. Audit findings fixed
| Finding | Fixed by |
|---|---|
| PIP-1 local named like an alias miscompiled | R4: the alias is a scoped MODULE symbol; the call is annotated after resolution |
| PIP-6 calls between a module's own functions don't build | Section 4: module struct, own names stay bare |
| PIP-7.1 private functions callable | R5 enforced in the frontend |
| PIP-7.2 structs and constants leak unqualified | R4 plus separate file scopes |
| PIP-7.3 and 7.4 name clashes, `main` in a module | Section 4: separate scopes and structs |
| PIP-7.5 same file merged twice | R3 real-path identity |
| PIP-7.6 self-import | R6 cycle error |
| PIP-8 modules imported by modules never merged | R2 paths plus step 1 discovers everything |
| PIP-9 alias calls not type-checked | Steps 3 and 4, R9 |
| PIP-10 cycles missed, recursive loading, no depth limit | Steps 1 and 2, R6 |
| PIP-17 semantic mode vs compile mode disagree | R9 |
| PIP-20 named and bare imports give broken Zig | R8 |
| PIP-32 local `io.a7` or `math.a7` can't be imported | R7 |

It also fixes the dropped-`main` problem from section 2 item 1 (qualified types in `parse_type`), removes the text matching behind PIP-3, and reduces the `a_b` vs `a/b` name collision in PIP-7.4 to nothing.

## 6. Programs that compile today and would change (need approval)
- **f01:** calling a private function is rejected.
- **f02:** unqualified use of an imported `Point` or `LIMIT` is rejected.
- **f03:** a local that shadows an alias is rejected, or prints `2 2` instead of `1 2`.
- **m10:** the import cycle is rejected.
- **Bare or named imports** used only for leaked types or constants are rejected.
- **Bare `import "io"` or `import "math"`** now means a local file.
- **`x/mod.a7` directory modules** are dropped.
- **User names starting with `__a7`** are rejected.
- **Generated Zig text** changes for every program if the main file is always wrapped; program behavior does not.

## 7. Where this is better than Odin for A7
- **Two visibility levels, not three.** File modules need no `package` line and no `@(private="file")`.
- **Explicit `pub` instead of public-by-default.** What a module exposes is visible where it's declared, and "add pub" is a one-line fix. This suits "super simple" users better than finding out later that a helper became API.
- **No collections or `-collection` flags.** There is no registry, so one reserved `std/` prefix and a project root of the main file's directory cover everything.
- **The alias is always written out.** Odin's default name comes from a convention it calls "not enforced by the compiler", so a reader can't always tell which package a name refers to.
- **Qualified names cost little in the backend.** Turning each module into a Zig struct makes `mod.name` in value, type and generic positions all lower the same way, and no identifiers are renamed. Flat renaming would have to rewrite every reference.
- **Where Odin is better:** splitting one large library across several files. A7 can add that later (for example a directory with a module file that re-exports) without changing anything above.

## 8. Decisions for the owner
1. Enforce `pub`, or make everything public by default?
2. Should a local that reuses an import alias be an error, or should the local win?
3. Forbid import cycles?
4. Allow `..` inside the project root?
5. Should the depth limit of 32 mean the longest import chain?
6. Are fields of a `pub` type visible to importers (resolves the SPEC 10.4 contradiction)?
7. Remove the bare `io` and `math` import names?
8. Drop `x/mod.a7`?
9. Always wrap the main file, or only when there are file imports?
