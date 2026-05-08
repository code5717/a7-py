# Features

## Language

- Static typing with inference in supported contexts.
- Functions, structs, enums, untagged union field literals/access, aliases, modules, and generics.
- Simple top-level generic function calls lower in both Zig and C backends.
- `if`, `while`, `for`, `for-in`, `match`, labeled loops, `break`, and `continue`.
- Arrays, slices, string slices, pointers, references, and manual `new` / `del`.
- `defer` and unreachable-statement diagnostics.
- Direct and mutual source-recursion diagnostics.

## Compiler

- Tokenizer, parser, semantic validation, AST preprocessing, and backend codegen.
- Zig backend and C11 backend.
- Stable CLI modes and exit codes.
- Human and JSON output formats.
- Markdown pipeline report generation.

## Verification

- Pytest coverage for tokenizer, parser, semantic, codegen, CLI, and release tooling.
- Zig and C example end-to-end verification against golden output.
- Selected backend parity checks that compile, build, run, and compare Zig/C outputs.
- Debug and release artifact builds for examples.
- Release checksum manifest generation and verification.

## Current Limits

The status page is canonical for remaining gaps. Key limits include complete memory/lifetime guarantees, full generic specialization beyond simple top-level functions, tagged union workflows, and arbitrary symbolic inequality reasoning.
