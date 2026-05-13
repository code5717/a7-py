---
title: Standard Library
nav: Stdlib
group: Reference
summary: The small virtual stdlib surface currently exposed by A7.
order: 3
---

# Standard Library

A7 standard modules are virtual imports resolved by the compiler. No stdlib
source file is loaded from disk at compile time.

## `std/io`

Basic output helpers.

```a7
import std/io

fn main() -> void {
    io.println("hello")
}
```

## `std/math`

Numeric helpers for current examples. Keep behavior deterministic and easy to
lower to Zig.

## `std/mem`

Memory helpers that match the current ownership model. This is not a sandbox
boundary.

## `std/string`

String helpers for examples that need simple scanning or comparison.

## `std/debug`

Debugging aids for compiler examples and generated output inspection.

## `std/random`

Pseudo-random helpers are planned as deterministic, seed-driven APIs. The first
usable shape should be small:

```a7
import std/random

fn main() -> void {
    var rng = random.seed(12345)
    var n = random.next_u32(ref rng)
}
```

The stdlib should prefer predictable APIs over broad coverage. Add one module
only when examples and compiler lowering both make the behavior clear.

## Planned

- `Option<T>` and `Result<T, E>`.
- Small collections such as `Vec`.
- More string and numeric helpers.
- A deterministic random module.

File IO, network IO, and concurrency are out of scope for the current stdlib.
