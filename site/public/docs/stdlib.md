---
title: Standard library
nav: Standard library
group: Reference
summary: Every registered std/io and std/math call, its arguments, and current restrictions.
order: 30
---

# Standard library

A7 resolves standard modules through a compiler registry. It does not load A7
stdlib source files from disk. `std/io` and `std/math` are the only registered
modules. Their short aliases `io` and `math` are also recognized; use the
`std/` spelling in new examples.

## Implemented modules

### std/io

```a7
io :: import "std/io"

main :: fn() {
    io.print("Hello, ")
    io.println("{}!", "A7")
    io.eprintln("diagnostic {}", 42)
}
```

The first two calls write `Hello, A7!` and a newline to stdout. The third writes
`diagnostic 42` and a newline to stderr.

These are call signatures, not user-definable variadic A7 declarations:

| Call | Result | Behavior | Status |
| --- | --- | --- | --- |
| `io.print()` | `void` | Write an empty string to stdout | supported |
| `io.print(format: string, values...)` | `void` | Write formatted text to stdout without adding a newline | limited |
| `io.println()` | `void` | Write a newline to stdout | supported |
| `io.println(format: string, values...)` | `void` | Write formatted text and a newline to stdout | limited |
| `io.eprintln()` | `void` | Write a newline to stderr | supported |
| `io.eprintln(format: string, values...)` | `void` | Write formatted text and a newline to stderr | limited |

The format must be a string literal. Each `{}` consumes one value. The number
of placeholders must equal the number of trailing arguments. `{{` prints `{`
and `}}` prints `}` without consuming an argument. Other brace text, such as
`{ }`, prints literally. The backend chooses Zig placeholders from argument types.
These functions return no value and must be used as statements. This special
stdlib formatting support does not make user-defined variadic functions available.
General formatting of arbitrary aggregate types is unverified; prefer scalar
numbers, strings, booleans, and characters as in the checked examples.

### std/math

```a7
io :: import "std/io"
math :: import "std/math"

main :: fn() {
    value: f64 = 9.0
    io.println("sqrt = {}", math.sqrt(value))
}
```

The following notation uses `F` for `f32` or `f64`, and `N` for a compatible
numeric type. These are descriptions of the checked call rules, not exported
A7 type aliases. Transcendental functions require floating-point arguments.

| Call | Semantic result type | Operation | Status |
| --- | --- | --- | --- |
| `math.sqrt(x: F)` | `F` | Square root | supported for checked floating inputs |
| `math.abs(x: N)` | `N` | Absolute value | limited for signed integers |
| `math.floor(x: F)` | `F` | Round down to an integral floating value | supported |
| `math.ceil(x: F)` | `F` | Round up to an integral floating value | supported |
| `math.sin(x: F)` | `F` | Sine of an angle in radians | supported |
| `math.cos(x: F)` | `F` | Cosine of an angle in radians | supported |
| `math.tan(x: F)` | `F` | Tangent of an angle in radians | supported |
| `math.log(x: F)` | `F` | Natural logarithm | supported for checked positive inputs |
| `math.exp(x: F)` | `F` | Exponential with base e | supported |
| `math.min(a: N, b: N)` | Compatible numeric type | Smaller argument | limited to compatible numeric arguments |
| `math.max(a: N, b: N)` | Compatible numeric type | Larger argument | limited to compatible numeric arguments |

Every unary call requires exactly one argument; `min` and `max` require two.
For `min` and `max`, one argument type must be assignable to the other. Prefer
matching explicit types. Math calls lower to Zig builtins. Signed `abs` results
are converted back to the input type, so `abs` can return `i32` from an `i32`
function. The minimum signed value has no positive value in the same type;
that input remains an unsafe edge case. Domain errors, non-finite values, and
integer edge values are not a general checked guarantee of these docs.

Standard-library operations must be called directly. Assigning `math.sqrt`
or another registered operation to a function variable is rejected.

Typed names such as `sqrt_f32` and `sqrt_f64` are unavailable. They appear in
specification planning material but are not registered calls.

## Not registered yet

| API | Status | Qualification |
| --- | --- | --- |
| `std/mem`, `std/string` | unavailable | Repository stub files are not registered. |
| `std/random`, `std/debug` | planned | No current registry entry. |
| `Option`, `Result`, growable collections | planned | Not current stdlib types. |
| File and network I/O | unavailable | No current stdlib API. |
| Concurrency primitives | planned | Require language and compiler prerequisites. |

See [status](/a7-py/docs/status.md) and [builtins](/a7-py/docs/language/builtins.md).
Evidence: [registry](https://github.com/code5717/a7-py/blob/master/a7/stdlib/__init__.py),
[io entries](https://github.com/code5717/a7-py/blob/master/a7/stdlib/io.py),
[math entries](https://github.com/code5717/a7-py/blob/master/a7/stdlib/math.py),
[call validation](https://github.com/code5717/a7-py/blob/master/a7/passes/type_checker.py),
and [Zig lowering](https://github.com/code5717/a7-py/blob/master/a7/backends/zig.py).
