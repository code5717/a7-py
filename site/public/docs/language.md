---
title: Language
nav: Language
group: Reference
summary: The implemented A7 language surface and the rules examples must follow today.
order: 2
---

# Language

The full design is in `docs/SPEC.md`. This page is the short operational
reference for what current examples and docs should use.

## Program shape

A7 uses explicit functions, typed values, loops, structs, enums, arrays,
slices, references, generics, and imports. The compiler lowers accepted source
to Zig 0.16.

```a7
import std/io

fn main() -> void {
    io.println("Hello, A7")
}
```

## Hard rules

- A7 source recursion is rejected. Use loops, index worklists, or explicit
  stacks.
- Use `usize` for sizes, lengths, capacities, and indexes.
- Reserve `isize` for signed pointer-sized offsets and position differences.
- `new [N]T` is rejected. Use stack arrays or slices.
- Public reference syntax does not expose address-of or dereference operators.
- Pass lvalues directly to `ref` parameters.

## Control flow

Use `if`, `while`, `for`, `break`, `continue`, and `match`. Recursive examples
must be rewritten iteratively.

```a7
fn sum_to(n: usize) -> usize {
    var total: usize = 0
    var i: usize = 0
    while i <= n {
        total = total + i
        i = i + 1
    }
    return total
}
```

## Types

Implemented and documented examples may use:

- Integers and floats.
- `bool`, `char`, strings.
- Fixed arrays and slices.
- Structs, enums, and untagged unions.
- References with nil checks.
- Simple generic functions and structs.

Reserved or incomplete areas belong in `docs/STATUS.md`, not in examples that
pretend they are complete.

## Imports

Local source imports can support multi-file A7 programs. Standard library
imports use virtual module names such as `std/io` and `std/random`.

The generated Zig can always be emitted as a single file.
