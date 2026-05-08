# Standard Library

Canonical page: [Language and Library](/a7-py/docs/language.md).

Current virtual stdlib support:

- `std/io`: `io.println`, `io.print`, `io.eprintln`
- `std/math`: `sqrt`, `abs`, `floor`, `ceil`, `sin`, `cos`, `tan`, `log`, `exp`, `min`, `max` with `f32` and `f64` typed variants

These modules are virtual built-ins registered through the module resolver, so
local aliases such as `console :: import "std/io"` and
`mathlib :: import "std/math"` lower the same way as `io` and `math`.

`std/string`, `std/mem`, and collections are planned or stubbed but are not current public stdlib modules.
