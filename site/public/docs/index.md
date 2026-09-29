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
program. A7 has explicit-width numbers, type inference, structs, arrays, slices,
references, and a limited generic implementation.

## A first program

```a7
io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
}
```

From a [configured checkout](/a7-py/docs/start.md), compile the existing example:

```bash
uv run a7 examples/001_hello.a7
```

Then build and run the generated Zig:

```bash
zig run examples/001_hello.zig
```

The program writes `Hello, World!` followed by a newline. The compiler command
emits source; it does not execute the A7 program.

## Pipeline

1. A7 source enters the Python compiler.
2. The compiler checks syntax, types, language rules, and safety obligations.
3. The compiler writes Zig source.
4. The separate Zig toolchain builds a native binary.
5. Your operating system runs that binary.

The boundary is the generated `.zig` file. See the expanded
[compiler pipeline](/a7-py/docs/compiler.md#pipeline).

## Read order

| Goal | Read |
| --- | --- |
| Install and run a program | [Get started](/a7-py/docs/start.md) |
| Learn by changing small examples | [Tour](/a7-py/docs/tour.md) |
| Find a runnable program | [Examples](/a7-py/docs/examples.md) |
| Look up syntax and restrictions | [Language reference](/a7-py/docs/language.md) |
| Print output or call math functions | [Standard library](/a7-py/docs/stdlib.md) |
| Automate compilation | [Compiler](/a7-py/docs/compiler.md) |
| Check what remains incomplete | [Status](/a7-py/docs/status.md) |
| Retrieve Markdown and metadata | [Agent usage](/a7-py/docs/agent-usage.md) |

## Experimental status

A7 is pre-1.0. A passing example does not establish support for every program
with similar syntax. Source recursion is rejected. Generic specialization,
module typing, integer overflow rules, reference aliasing, and lifetime checks
have limitations. Tensors, automatic memory management, and concurrency are
planned work. Read [status](/a7-py/docs/status.md) before choosing A7 for a project.

A7 is not a sandbox. Compiled programs run with your account's permissions.
Only compile and execute source you trust.

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
