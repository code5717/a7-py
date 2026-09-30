---
title: A7 documentation
nav: Overview
group: Getting started
summary: An experimental systems language that compiles to Zig and native programs.
order: 0
---

# A7 documentation

A7 is an experimental, statically typed systems language. Its Python compiler
checks `.a7` source and emits a single Zig file. Zig 0.16.0 builds the native
program. Start below, then read the tour or the language reference.

## Start in two minutes

From a [configured checkout](/a7-py/docs/start.md), check and run the hello
example:

```bash
uv run a7 check examples/001_hello.a7
uv run a7 run examples/001_hello.a7
```

Expected program output:

```text
Hello, World!
```

`check` validates without writing files. `run` builds a temporary executable.
To keep one, use `uv run a7 build examples/001_hello.a7 -o hello`. The
file-first command `uv run a7 examples/001_hello.a7` emits Zig source only.

## A first program

```a7
io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
}
```

Keep editing this shape: import capabilities, declare a `main` with no
parameters, and print. When setup fails, match the symptom in
[Get started](/a7-py/docs/start.md#common-setup-failures) before retrying.

## Pipeline

1. A7 source enters the Python compiler.
2. The compiler checks syntax, types, language rules, and safety obligations.
3. The compiler writes Zig source.
4. The separate Zig toolchain builds a native binary.
5. Your operating system runs that binary.

The boundary is the generated `.zig` file. See the expanded
[compiler pipeline](/a7-py/docs/compiler.md#pipeline).

## Read order

- **Get started** — install, compile, and fix setup failures: [Get started](/a7-py/docs/start.md).
- **Tour** — learn by changing small runnable excerpts: [Tour](/a7-py/docs/tour.md).
- **Examples** — find callbacks, lists, trees, and reports: [Examples](/a7-py/docs/examples.md).
- **Language reference** — look up syntax and restrictions: [Language reference](/a7-py/docs/language.md).
- **Standard library** — print output or call math functions: [Standard library](/a7-py/docs/stdlib.md).
- **Compiler** — automate compilation and read exit codes: [Compiler](/a7-py/docs/compiler.md).
- **Status** — check what remains incomplete before choosing A7: [Status](/a7-py/docs/status.md).
- **Agent usage** — retrieve Markdown and metadata: [Agent usage](/a7-py/docs/agent-usage.md).

## Experimental status

A7 is pre-1.0. A passing example does not establish support for every program
with similar syntax. Source recursion is rejected. Generic specialization,
module typing, integer overflow rules, reference aliasing, and lifetime checks
have limitations. Tensors, automatic memory management, and concurrency are
planned work. Read [status](/a7-py/docs/status.md) before choosing A7 for a project.

> A7 is not a sandbox. Compiled programs run with your account's permissions.
> Only compile and execute source you trust.

## Repository docs

[README](https://github.com/code5717/a7-py/blob/master/README.md) and
[release instructions](https://github.com/code5717/a7-py/blob/master/docs/RELEASE.md)
are the user-facing source authorities. The
[specification](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md)
describes language semantics, while
[current status](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
records implementation gaps. Reference topics qualify specification claims
against implementation evidence. Research proposals do not establish support.

## Public contract

Existing page routes and `/a7-py/docs/*.md` entry points remain available.
Every topic has a Markdown twin, including nested language topics. Start agent
retrieval at [llms.txt](/a7-py/llms.txt). Use the
[manifest](/a7-py/docs/manifest.json) for page and feature metadata, or the
[full corpus](/a7-py/llms-full.txt) when you need every page.
