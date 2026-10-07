---
title: Get started
nav: Get started
group: Getting started
summary: Install the compiler, compile your first program, and diagnose setup failures.
order: 1
---

# Get started

## Requirements

- Python 3.13 or newer.
- [uv](https://docs.astral.sh/uv/) for the Python environment.
- [Zig 0.16.0](https://ziglang.org/download/) on `PATH` to build native programs.
- Git to clone the repository.

The compiler emits Zig source. The `build` and `run` commands invoke Zig.
`check` validates the full A7 pipeline without writing files or requiring Zig.
The V1 qualification target is Linux x86_64 with Python 3.13 and Zig 0.16.0.
Bun is only needed for [website contributors](/a7-py/docs/project.md).

## Install

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
uv run a7 --version
uv run a7 doctor
```

Run the following commands from the `a7-py` repository root. `zig version`
should print `0.16.0`, the toolchain version used by this checkout's release gates.
The release workflow attaches package files to GitHub releases; it does not
publish to a package registry.

## First compile

The file `examples/001_hello.a7` contains:

```a7
io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
}
```

Check and run it:

```bash
uv run a7 check examples/001_hello.a7
uv run a7 run examples/001_hello.a7
```

Expected program output:

```text
Hello, World!
```

To keep a native executable:

```bash
uv run a7 build examples/001_hello.a7 -o hello
./hello
```

The default profile is `debug`. Use `--profile release` for Zig ReleaseSafe,
which keeps runtime checks, or `--profile fast` for Zig ReleaseFast, which
removes them. Current safety checks have alias and lifetime limits in every
profile; no profile establishes complete memory safety.

To emit Zig without building, keep the existing file-first command:

```bash
uv run a7 examples/001_hello.a7
# Writes examples/001_hello.zig
```
The repository wrapper `uv run python main.py` accepts the same arguments as
`uv run a7`.

## Language tour

Continue with the [guided tour](/a7-py/docs/tour.md). Its main source is
[037_language_tour.a7](https://github.com/code5717/a7-py/blob/master/examples/037_language_tour.a7).
Compile and run it with:

```bash
uv run a7 run examples/037_language_tour.a7
```

## Useful modes

Use `--mode semantic` to stop after semantic checks, `--mode pipeline` to
exercise code generation without writing Zig, and `--format json` for tooling.
Neither mode builds a native executable. `a7 check FILE --format json` provides
the full pipeline without file output. `a7 run FILE -- ARGS` forwards arguments
to the native process and returns its exit status. A7 `main` still has no
parameters or return value, and there is no argument-reading API. See [all CLI options](/a7-py/docs/compiler.md).

## Common setup failures

| Symptom | Check |
| --- | --- |
| `uv` not found | Install uv and reopen the terminal so `PATH` updates apply. |
| Python version cannot be resolved | Install Python 3.13 or newer through uv or your system package manager, then repeat `uv sync`. |
| `a7` not found | Run `uv sync` in the repository root and invoke `uv run a7`. |
| Input file cannot be read | Confirm the working directory and source path. Compiler exit code 3 means an I/O failure. |
| `zig` not found | Install Zig and add its executable directory to `PATH`. |
| Generated code fails with another Zig version | Check `zig version`; the supported toolchain is 0.16.0. |
| Compilation succeeds but there is no executable | The file-first command emits `.zig` source. Use `a7 build FILE` or `a7 run FILE` for native execution. |
| A7 rejects a program from the specification | Check its [feature status](/a7-py/docs/language.md) and the diagnostic stage before assuming executable support. |

## Verify locally

To compile, build, execute, and compare every checked-in example against its
expected output:

```bash
uv run python scripts/verify_examples_e2e.py
```

Contributor and release checks are on [Project](/a7-py/docs/project.md) and
[Release](/a7-py/docs/release.md). Evidence for this guide comes from
[README](https://github.com/code5717/a7-py/blob/master/README.md), the
[hello example](https://github.com/code5717/a7-py/blob/master/examples/001_hello.a7),
and its [output fixture](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/001_hello.out).
