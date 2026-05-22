---
title: Standard Library
nav: Stdlib
group: Reference
summary: Virtual stdlib modules registered in the compiler today.
order: 3
---

# Standard Library

A7 standard modules are virtual imports resolved by the compiler. No stdlib
source file is loaded from disk at compile time.

## Implemented modules

Only these modules are registered in the compiler today:

### `std/io`

Import path: `"std/io"`. Bindings: `print`, `println`, `eprintln`.

```a7
io :: import "std/io"

main :: fn() {
    io.println("hello")
    io.eprintln("stderr: {}", 42)
}
```

### `std/math`

Import path: `"std/math"`. Functions: `sqrt`, `abs`, `floor`, `ceil`, `sin`,
`cos`, `tan`, `log`, `exp`, `min`, `max`.

Typed variants such as `sqrt_f32` and `sqrt_f64` are also available as bare
builtins.

```a7
io :: import "std/io"
math :: import "std/math"

main :: fn() {
    x := math.sqrt(2.0)
    io.println("sqrt(2) = {}", x)
}
```

## Not registered yet

The repository contains stub modules for `mem` and `string`, but they are not
registered in the compiler. Do not use them in examples until they appear in
[Status](/a7-py/status/) as implemented.

These are planned but not available:

- `std/random` — deterministic, seed-driven APIs
- `std/debug` — debugging aids
- `Option<T>` and `Result<T, E>`
- Small collections such as `Vec`

File IO, network IO, and concurrency are out of scope for the current stdlib.
