---
title: Compiler
nav: Compiler
group: Compiler
summary: The A7 compiler pipeline, safety checks, and Zig backend contract.
order: 4
---

# Compiler

The package lives under `a7/`. The CLI entry point is `a7.cli:main`, exposed as
`uv run a7` after `uv sync`.

## Pipeline

1. Tokenize source.
2. Parse into AST.
3. Resolve names and imports.
4. Type check.
5. Validate language invariants.
6. Plan safety obligations.
7. Preprocess AST for backend emission.
8. Emit Zig.
9. Let Zig build the native binary.

Failures in tokenization, parsing, semantic validation, code generation, and
internal errors have stable exit stages for tool usage.

## Safety stance

A7 rejects direct recursion, mutual recursion, and local function-pointer
alias-cycle recursion. Compiler internals also avoid recursive AST traversal.

The safety layer focuses on compile-time checks for:

- narrowing casts,
- division and modulo denominator checks,
- indexing and slicing bounds,
- nil reference use,
- direct use after `del`.

These checks are compiler guarantees, not an OS sandbox.

## Zig backend

The Zig backend targets Zig 0.16.0. Generated Zig should be readable, preserve
source structure where practical, and remain single-file even when A7 imports
multiple input files.

Debug and release artifact builders verify generated source and binaries.
