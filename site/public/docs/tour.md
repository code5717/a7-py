---
title: A7 tour
nav: Tour
group: Getting started
summary: Learn declarations, arrays, control flow, references, and generics through runnable examples.
order: 2
---

# A7 tour

Start with [installation](/a7-py/docs/start.md). Each fragment below is an excerpt of a
complete source file, not a standalone program. Run the main tour from the
repository root:

```bash
uv run a7 examples/037_language_tour.a7
zig run examples/037_language_tour.zig
```

The [complete source](https://github.com/code5717/a7-py/blob/master/examples/037_language_tour.a7)
and [expected output](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/037_language_tour.out)
let you compare each lesson with the actual program.

## 1. Declare values

```a7
name: string = "A7"
version := 1
io.println("{} tour v{}", name, version)
```

`: Type =` declares a binding with an explicit type. `:=` infers its type.
`::` introduces constants and named declarations such as functions. The output
line is `A7 tour v1`. Change the string and run the file again.
See [declarations](/a7-py/docs/language/declarations.md).

## 2. Work with arrays and slices

```a7
numbers: [5]i32 = [3, 5, 8, 13, 21]
middle := numbers[1..4]
total := 0
for value in middle {
    total += value
}
io.println("slice total = {}", total)
```

`[5]i32` holds five integers. The slice selects indices 1, 2, and 3, so this
prints `slice total = 26`. The upper bound is exclusive. Slices view existing
storage. Use `usize` for index variables and lengths.
See [arrays and strings](/a7-py/docs/language/arrays-strings.md).

## 3. Pass structured values

```a7
Point :: struct {
    x: i32
    y: i32
}

area :: fn(point: Point) i32 {
    ret point.x * point.y
}
```

The tour constructs `Point{x: 6, y: 7}` and prints `area = 42`.
Named fields make the structure explicit. `ret` returns a value.
See [aggregate types](/a7-py/docs/language/aggregate-types.md) and
[functions](/a7-py/docs/language/functions.md).

## 4. Choose branches and repeat work

```a7
countdown := 3
while countdown > 0 {
    io.println("countdown {}", countdown)
    countdown -= 1
}
```

This prints countdown lines for 3, 2, and 1. The same source also matches an enum
with one case per variant. Source recursion is banned, including mutual and
local function-pointer alias cycles. Use loops or explicit worklists.
See [control flow](/a7-py/docs/language/control-flow.md).

## 5. Update through a reference

```a7
bump :: fn(value: ref i32) {
    value += 1
}
```

The tour passes an ordinary lvalue to `bump`. It splits the declaration and
assignment before that call:

```a7
counter: i32
counter = 41
bump(counter)
io.println("counter = {}", counter)
```

The output is `counter = 42`. A7 has no public address-of or dereference
operators. The full tour also allocates a struct with `new`, checks for `nil`,
and registers `defer del` cleanup. These checks do not establish complete
ownership or lifetime safety. See [memory](/a7-py/docs/language/memory.md).

## 6. Reuse a generic function

Generics have their own complete example:

```bash
uv run a7 examples/014_generics.a7
zig run examples/014_generics.zig
```

```a7
identity($T) :: fn(value: $T) $T {
    ret value
}
```

Inside `main`, `identity(7)` returns the integer and `identity("ok")` returns
the string. The compiler infers `$T` at each call. The example also instantiates
`Box(i32)`, a nested box, and `Pair(i32, string)`.

See the [source](https://github.com/code5717/a7-py/blob/master/examples/014_generics.a7),
[expected output](https://github.com/code5717/a7-py/blob/master/test/fixtures/golden_outputs/014_generics.out),
and [generic restrictions](/a7-py/docs/language/generics.md). These direct top-level
calls do not establish arbitrary call-chain or cross-module specialization.

## Next examples

Use the [example index](/a7-py/docs/examples.md) to find callbacks, iterative linked
lists and trees, sorting, text analysis, and small reporting programs. Consult
the [reference](/a7-py/docs/language.md) when you need exact restrictions.
