# A7 compiler

A7 is a statically typed language with type inference, generics and C-style
syntax. Its Python compiler emits Zig; Zig builds the native executable.
The compiler is under development. Read [Status](docs/STATUS.md) for known gaps.

## Quick start

Install Python 3.13 or newer, [uv](https://docs.astral.sh/uv/), and
[Zig 0.17.1](https://ziglang.org/download/). Native qualification currently targets
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
as well as construction. String comparison uses byte contents. User variadic
parameters, multi-declaration / destructuring, and multi-return spellings are
cut: they fail at semantic exit 6 or parse exit 5. Pass a slice or return a
named struct instead. Intrinsics other than `@type_set` stay reserved. Read the
[language tour](examples/037_language_tour.a7) and
[specification](docs/SPEC.md) together with [Status](docs/STATUS.md).

