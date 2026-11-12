# A7 compiler

A7 is a statically typed language with type inference, generics and C-style
syntax. Its Python compiler emits Zig; Zig builds the native executable.
The compiler is under development. Read [Status](docs/STATUS.md) for known gaps.

## Quick start

Install Python 3.13 or newer, [uv](https://docs.astral.sh/uv/), and
[Zig 0.16.0](https://ziglang.org/download/). Native qualification currently targets
Linux x86_64 with Python 3.13. Zig must be on `PATH` for `build` and `run`.

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
uv run a7 doctor
uv run a7 run examples/001_hello.a7
```

[The hello example](examples/001_hello.a7) contains:

```a7
io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
}
```

Its program output is:

```text
Hello, World!
```

## Check, build and run

Run these commands from the checkout after `uv sync`:

```bash
uv run a7 check examples/001_hello.a7
uv run a7 check examples/001_hello.a7 --format json
uv run a7 check examples/001_hello.a7 --timings
uv run a7 build examples/001_hello.a7 --profile release --output hello
./hello
uv run a7 run examples/001_hello.a7 --profile release
uv run a7 doctor --format json
uv run a7 --version
```

`check` runs through code generation without writing files or invoking Zig.
An entry file needs `main :: fn()`; use `check --lib` for a library without an
entry point. Imported modules do not need `main`. `--timings` prints per-stage
wall times; `build`/`run --timings` also report the Zig hop.

`build` defaults to `./<source-stem>`. Prefer long flags such as `--output` in
scripts; `-o` remains accepted. `run` builds a temporary executable and runs it
in the current directory. Arguments after `a7 run FILE --` go to the native
process. This forwarding does not provide an A7 argument-reading API; `main`
has no parameters or return value.

`doctor` reports package, Python, platform and Zig versions. It exits 2 for a
missing or wrong Zig version, or an environment outside the qualification target.
`doctor --format json` also lists capabilities for agents: supported commands,
modes, backends, profiles, exit codes and flags. Capabilities remain present
when Zig is missing.

To emit Zig source or inspect the compiler stages:

```bash
uv run a7 examples/001_hello.a7
uv run a7 --mode tokens examples/006_if.a7
uv run a7 --mode ast --format json examples/004_func.a7
uv run a7 --mode semantic examples/009_struct.a7
uv run a7 --mode pipeline --format json --timings examples/014_generics.a7
uv run a7 --help
```

The first command writes `examples/001_hello.zig`. `--mode pipeline` writes no
files. `uv run python main.py` is a compatibility entry point for the same CLI.
Output destinations cannot overwrite input modules, including filesystem aliases.
JSON artifact lists describe files written by that invocation. Compiler
`--format json` uses schema `3.0` with `stages`, `exit_code` and `diagnostics`
(spans live on each diagnostic). Failures keep stage-specific exit codes and
still emit JSON.

## Build profiles

Use `--profile` with `build` or `run`, and `--build-profile` when emitting Zig.

| Profile | Zig mode | Runtime checks |
| --- | --- | --- |
| `debug`, default | Debug | Enabled |
| `release` | ReleaseSafe | Enabled |
| `fast` | ReleaseFast | Zig safety checks disabled |

`fast` can expose undefined behavior if compiler proofs miss an unsafe operation.
No profile establishes complete memory safety. `--no-nonwrap` disables the
optimization that uses plain integer operators for proven-range results.

## Current language and limits

Exact numeric evaluation checks arithmetic growth before allocation and limits
work, retained exact values and exact binding-chain depth. Resource failures are
located semantic errors (exit 6). Repeated failures of the same resource category
within one initializer report its first failure location. Conservative bounds can reject an operation
whose final result would fit. See [SPEC Appendix C](docs/SPEC.md#appendix-c-implementation-limits)
for accounting rules and [Status](docs/STATUS.md) for remaining qualification.

Else-if arms preserve lexical shadowing: a local in one arm does not change
a parent binding or a declaration in another arm. Operating-system errors during
module path lookup, including overlong paths, report the importing location at exit 3.

The compiler supports explicit-width numeric types, arrays, slices, structs,
enums, unions, type aliases, functions, loops, `match` and `defer`. Integer
literal/range overlap checks preserve the typed integer value, including values
beyond 2^53. Generic numeric patterns fit each concrete subject type before
overlap checking. Generics include `$T` type parameters, `$N` value parameters and constraints. Generic
local initializers and bound callback arguments are checked against concrete
instantiations, including fixed-array element types such as `[2]$T`. Concrete
wrappers preserve fitting and overflow checks; unsupported generic callable
origins remain limited. A constrained generic argument satisfies a destination
constraint when its admitted set is nonempty and every member belongs to the
destination set. Struct and union type annotations enforce these constraints
as well as construction. String comparison uses byte contents. Read the
[language tour](examples/037_language_tour.a7) and [specification](docs/SPEC.md)
together with [Status](docs/STATUS.md).

Inferred slice bindings retain their slice type when initialized from an array
view. A mutable binding can later select a view of a different length; its
initializer runs once. Slice lifetime enforcement remains incomplete.

Local bindings cannot reuse an import alias from their own file. This includes
function parameters, loop bindings and match captures. Each file has its own
namespace. Imported declarations use `alias.name`; top-level `_name` is private,
and struct fields remain visible. Qualified types and struct literals retain
their defining file's identity. Import aliases remain local to the file that
declares them. See [qualification](docs/audits/2026-10-07/qualification.md) and
[Status](docs/STATUS.md) for the source-specific verification boundary.

Represented readonly calls reject known nil field reads with semantic exit 6.
Previously accepted guarded calls and literal-selected non-reading controls
remain accepted. Existing call checks still apply. General callee, container
and lifetime proofs remain incomplete; see the
[safety contract](docs/SAFETY_CONTRACT.md).

The compiler also checks the original executable entry declaration against
its complete readonly summary. It rejects a represented nil read reached through
a known local selector. `--lib` has no implicit executable root. General
caller-local Boolean and effect proofs remain incomplete.

Use `usize` for sizes, lengths and indices. Use `isize` for signed pointer-sized
offsets and position differences. A7 source recursion is rejected; use loops or
explicit stacks. Current traversal candidates use worklists for parsing, type
checking, safety traversal, Zig emission and AST comparison and display. The
recursive-group and generated-method exception lists are empty. The frozen
integration passed 3,602 tests with one expected failure. Its secrets check
needed Git metadata restored; that check and all remaining release checks then
passed on unchanged sources.
See [architecture](docs/ARCHITECTURE.md) for the checked source versions and
qualification limits.

Array literals selected by `if` or `match` use the declared element type.
Concrete generic calls check each literal element for size and range.

Reference-to-fixed-array indexing supports primitive element reads and simple
or compound writes when bounds and non-nil requirements are proven. Guarded nil
calls and borrowed-array calls remain valid. Unresolved nil-call conditions,
effectful indices, selected reference-array fields, mutable or captured callable
origins, ref slicing and general reference-element ownership remain incomplete.

A resolved function with one Boolean-literal return can supply an indexed guard
fact through direct or forwarded calls and stable unwritten, uncaptured local
aliases. The checker preserves call and argument evaluation; indexed uses retain
optional-reference unwraps. Conditional, effectful and deferred helpers remain
unknown.

Local Boolean guards, early returns and value copies can prove indexed calls
safe for every input. Bare, negated and Boolean-literal comparison guards are
supported. Captured or reference-exposed cells, fields and globals are excluded.
An unguarded symbolic nil wrapper remains unresolved even with a false caller.

Numeric writes through references apply the scalar destination's exact-fit
rules. A guarded `ref usize` accepts `n = 3`; overflow and incompatible typed
values remain semantic errors. Ordinary scalar reads through references remain
unsupported.

Heap values currently require `del` or `defer del`. Pass lvalues directly to
`ref` parameters and access reference fields after nil checks. There are no
public address-of or dereference operators. Heap fixed arrays, `new [N]T`, are
rejected. Direct reference aliases share deletion state, and guarded reference
fields are checked. Literal-index reads of tracked fixed arrays retain reference
allocation identity on represented straight-line and conditional paths.
Deleting that allocation invalidates saved aliases and later reads of the
tracked slot. Fresh slot replacements and
independent array copies preserve valid uses. Broader array, slice and joined
reference lifetime checks remain incomplete. Known direct global
reference stores now propagate allocation identity through calls, so deleting a
stored allocation invalidates its caller aliases. Simple direct calls with literal
boolean selectors preserve the selected reference or nil return. Broader return,
global nil-state and parameter proofs remain incomplete. Automatic memory
management is not implemented.

Eligible loop-counter proofs survive represented readonly calls, returned
reference forwarding and writes to distinct owned storage. Known writes through
reference parameters still invalidate affected facts. Unknown calls and escaped
storage remain conservative; these checks do not establish general lifetime
safety.

Inferred concrete function bindings support reassignment and matching
reference parameters. Saved function values keep their previous target. Generic
function aliases remain compile-time aliases; closure support is unchanged.

The current stdlib provides `io` and `math`. Reserved `std/` imports resolve to
registered hooks or bundled implementation sources. This loader support adds no
public stdlib modules. Package-owned `Option(T)` and
`Result(T, E)` are available in every file. Remove old declarations of those
names or rename custom types. `io.read_line` takes a mutable byte slice, and
both it and `io.println_ok` return `Result(usize, io.IoErr)`. Import `io` explicitly
in each file that uses its operations or error type. The compiler
rejects value uses of registered `print`, `println` and `eprintln` at semantic
exit 6, including inferred bindings and array elements. Statement effects stay
valid, and `println_ok` remains value-bearing. Nine native controls passed across
debug, release and fast. The combined gate passed on frozen source `e0c6235a`.
The [verification record](docs/audits/2026-10-07/stdio-integration-verification.json)
records the complete source hash. Ordinary user void bindings are unchanged.

File imports share one emitted Zig file after per-file semantic checking. Selected
imports (`import "m" { A, B }`) bind public names from file modules and virtual
stdlib modules. `using import` rejects at semantic exit 6 with alias-form
guidance. Forwarding another file's import alias is rejected under
L76. Unsupported multi-dot type annotations and struct literals still fail
parsing. Some accepted forms
still fail later in compilation. The [gap list](docs/STATUS.md) records those
cases and the remaining generic and numeric limits.

V1 publication requires automatic memory, useful libraries and tools,
concurrency, CPU AI, actual GPU execution and self-hosting parity under
[decision L73](docs/plan/decisions.md#full-v1-completion-boundary-2026-10-07).
These are unfinished requirements. The [delivery roadmap](docs/plan/delivery-roadmap.md)
separates approved work, unresolved designs and required evidence.
GPU execution is deferred under L75. The
[Zig GPU research](docs/research/2026-10-07-zig-gpu-support.md) records support
and compile-only evidence; it does not qualify device execution.

The compiler is not a sandbox. Compile and execute only source you trust.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 2 | Usage or toolchain error |
| 3 | I/O error |
| 4 | Tokenization error |
| 5 | Parse error |
| 6 | Semantic error |
| 7 | Code generation or native build error |
| 8 | Internal error |

`run` returns the native process's exit status, which can overlap these codes.

## Development and documentation

```bash
uv run python scripts/project_status.py
PYTHONPATH=. uv run pytest test/test_tokenizer.py
./run_release_checks.sh
```

`project_status.py` reports source-derived counts; it does not run tests.
The [release guide](docs/RELEASE.md) covers full checks, worker limits, native
artifacts, package builds and release preparation. The [site guide](site/README.md)
covers documentation development and generated exports.

- [Documentation index](docs/README.md), [architecture](docs/ARCHITECTURE.md)
  and [changelog](docs/CHANGELOG.md).
- [Safety contract](docs/SAFETY_CONTRACT.md) and [security policy](docs/SECURITY.md).
- [Published documentation](https://code5717.github.io/a7-py/).
- [Agent index](https://code5717.github.io/a7-py/llms.txt),
  [Markdown docs](https://code5717.github.io/a7-py/docs/index.md),
  [manifest](https://code5717.github.io/a7-py/docs/manifest.json) and
  [full agent context](https://code5717.github.io/a7-py/llms-full.txt).
