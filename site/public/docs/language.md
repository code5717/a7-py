---
title: Language
nav: Language
group: Reference
summary: Syntax and rules for the A7 language surface that examples use today.
order: 2
---

# Language

This page is the short operational reference. Full semantics are in
`docs/SPEC.md`. Verified examples live under `examples/`, especially
`037_language_tour.a7`.

## Program shape

Top-level bindings and functions use `::`. Functions use `fn`, explicit
`ret`, and typed parameters.

```a7
io :: import "std/io"

greet :: fn(name: string) {
    io.println("Hello, {}!", name)
}

main :: fn() {
    greet("A7")
}
```

## Declarations

- Top-level constants and functions: `name :: value`
- Mutable locals with inference: `count := 0`
- Explicit type: `count: i32 = 0`

## Control flow

Use `if`, `while`, `for`, `break`, `continue`, and `match`. A7 source
recursion is rejected at compile time. Rewrite recursive algorithms with loops,
index worklists, or explicit stacks.

```a7
sum_to :: fn(n: usize) usize {
    total: usize = 0
    i: usize = 0
    while i <= n {
        total = total + i
        i = i + 1
    }
    ret total
}
```

Indexed iteration:

```a7
for index, value in items {
    // index is usize
}
```

## Types

Examples and docs may use:

- Integers and floats
- `bool`, `char`, strings
- Fixed arrays and slices
- Structs, enums, and untagged unions
- References with nil checks
- Simple generic functions and structs

Reserved or incomplete areas belong in [Status](/a7-py/status/), not in
examples that pretend they are complete.

## Imports

Standard library imports use virtual module paths:

```a7
io :: import "std/io"
math :: import "std/math"
```

Local file imports are being extended for multi-file programs. Generated Zig
remains single-file output.

## Hard rules

- A7 source recursion is rejected. Use loops, index worklists, or explicit
  stacks.
- Use `usize` for sizes, lengths, capacities, and indexes.
- Reserve `isize` for signed pointer-sized offsets and position differences.
- `new [N]T` is rejected. Use stack arrays or slices.
- Public reference syntax does not expose address-of or dereference operators.
  Pass lvalues directly to `ref` parameters.
