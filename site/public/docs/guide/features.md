# Features

## Language

- Static typing with inference in supported contexts.
- Functions, structs, enums, untagged union field literals/access, aliases, virtual stdlib modules, and generics.
- Simple top-level generic function calls and used generic struct instances lower in the Zig backend.
- `if`, `while`, `for`, `for-in`, `match`, labeled loops, `break`, and `continue`.
- Arrays, same-shape numeric fixed-array `+`, slices, string slices, pointers, references, and manual `new` / `del`.
- `defer` and unreachable-statement diagnostics.
- Direct, mutual, local alias, and callback-trampoline source-recursion diagnostics.

## Compiler

- Tokenizer, parser, semantic validation, AST preprocessing, and backend codegen.
- Zig backend.
- Stable CLI modes and exit codes.
- Human and JSON output formats.
- Markdown pipeline report generation.

## Verification

- Pytest coverage for tokenizer, parser, semantic, codegen, CLI, and release tooling.
- Zig example end-to-end verification against golden output.
- Selected Zig end-to-end checks that compile, build, run, and compare golden outputs.
- Debug and release artifact builds for examples.
- Release checksum manifest generation and verification.

## Current Limits

The status page is canonical for remaining gaps. Key limits include complete memory/lifetime guarantees, backend lowering/linking for file-backed local modules, selected/using import lowering, broader generic propagation beyond current function and struct instance coverage, parsed-only variadic declarations, reserved-but-unimplemented intrinsics beyond `@type_set(...)`, tagged union workflows, and arbitrary symbolic inequality reasoning.
