# Language and Library

## Overview

A7 is a statically typed systems language with type inference, manual memory operations, modules, generics, and Zig/C backends.

## Recursion Rule

Source recursion is banned. Direct and mutual recursion are rejected during semantic validation. Repeated work should be expressed with loops, explicit stacks, queues, or index-based worklists.

The compiler implementation also keeps AST traversals iterative and is validated with Python recursion limit 100.

## Integer Type Guidance

- Use `usize` for sizes, lengths, capacities, allocation byte counts, and array/slice/string indices.
- Use `isize` for signed pointer-sized offsets or differences between positions.
- Use fixed-width integers such as `i32`, `i64`, `u32`, or `u64` when the data itself has a fixed width or range.
- Small arithmetic examples can use `i32`; indexes and counters should usually use `usize`.

## Standard Library

Current virtual stdlib support is intentionally small:

- `std/io`: `io.println`, `io.print`, `io.eprintln`
- `std/math`: `sqrt`, `abs`, `floor`, `ceil`, `sin`, `cos`, `tan`, `log`, `exp`, `min`, `max` with `f32` and `f64` typed variants

These modules are virtual built-ins registered through the module resolver, so
local aliases such as `console :: import "std/io"` and
`mathlib :: import "std/math"` lower the same way as `io` and `math`.

Source stubs such as `mem` and `string` exist in the repository but are not registered public stdlib modules yet.

## Specification

The full language specification lives in [`docs/SPEC.md`](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md).
