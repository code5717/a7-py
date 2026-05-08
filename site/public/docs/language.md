# Language and Library

## Overview

A7 is a statically typed systems language with type inference, manual memory operations, modules, generics, and Zig/C backends.

The interactive Language page is the Zig-style one-page reference: use browser
find on the page for syntax, types, control flow, memory, modules, stdlib, and
current implementation notes.

For a compact learn-by-reading path, open
[`examples/037_language_tour.a7`](https://github.com/code5717/a7-py/blob/master/examples/037_language_tour.a7).
It is a single commented program verified through both native backends.

## Recursion Rule

Source recursion is banned. Direct and mutual recursion are rejected during semantic validation. Repeated work should be expressed with loops, explicit stacks, queues, or index-based worklists.

The compiler implementation also keeps AST traversals iterative and is validated with Python recursion limit 100.

## Integer Type Guidance

- Use `usize` for sizes, lengths, capacities, allocation byte counts, and array/slice/string indices.
- Use `isize` for signed pointer-sized offsets or differences between positions.
- Use fixed-width integers such as `i32`, `i64`, `u32`, or `u64` when the data itself has a fixed width or range.
- Small arithmetic examples can use `i32`; indexes and counters should usually use `usize`.

## Match Fallthrough

`fall` continues from one match case body into the next case body. It is
supported in both Zig and C backends only when it is the final direct statement
of a non-final match case. `fall` is rejected outside match cases, inside
`else`, inside nested control flow, or in the final case.

## Unions

Untagged union literals use `Type{field: value}` with exactly one named field.
The field must exist on the union and the value must match the field type.
Field access resolves declared union fields in both Zig and C backends.

Tagged/discriminated union tag workflows are not implemented yet.

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
