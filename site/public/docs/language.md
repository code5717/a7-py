# Language Reference

The implemented A7 language surface. Anything you can see in `examples/`
compiles end-to-end. Anything described here works in the current Zig
backend unless explicitly marked otherwise.

The authoritative grammar lives in `docs/SPEC.md` in the repo. This page
focuses on what compiles **today**.

## Lexical

A7 source is ASCII. The standard extension is `.a7`. Tabs are rejected by
the tokenizer; use spaces. Newlines terminate statements.

```a7
// single line comment
/* nested /* block */ comment */
```

Identifiers are `[A-Za-z_][A-Za-z0-9_]*`, max 100 characters. Leading
underscore is reserved for compiler-generated names.

## Primitive types

| Type | Notes |
|---|---|
| `bool` | `true` / `false` |
| `i8 i16 i32 i64` | Signed integers |
| `u8 u16 u32 u64` | Unsigned integers |
| `usize` | Pointer-sized unsigned. Default for sizes, lengths, indices. |
| `isize` | Pointer-sized signed. Use only for signed offsets between positions. |
| `f32 f64` | Floats |
| `char` | ASCII char literal type |
| `string` | UTF-8 string (immutable view) |

Integer-type guidance — use `usize` for any size/length/index. Reserve
`isize` for signed pointer-sized math (offsets, differences). For other
sizes, pick a fixed-width type.

## Declarations

```a7
// constant
const PI: f64 = 3.14159

// variable (mutable)
var counter: i32 = 0

// inferred type
total := 0
name := "A7"
```

`const` is compile-time fixed. `var` is mutable. `:=` infers the type from
the RHS.

## Functions

```a7
fn add(a: i32, b: i32) -> i32 {
    return a + b
}

pub fn main() -> i32 {
    return add(2, 3)
}
```

- Visibility: `pub` for module-public.
- Return type after `->`.
- **No recursion.** Direct, mutual, and function-pointer-alias-cycle
  recursion is rejected at compile time.

## Control flow

```a7
if cond { ... } else if other { ... } else { ... }

while cond { ... }

for i: usize in 0..n { ... }

match value {
    0      => { /* zero */ }
    1, 2   => { /* small */ }
    case x => { /* default */ }
}
```

`match` supports integers, booleans, and enums with exhaustiveness checking
on bool and enum.

`defer` runs at scope exit (last-declared-first-run). `break`, `continue`,
and labels work as expected on loops.

## Structs

```a7
struct Point {
    x: i32
    y: i32
}

fn shift(p: Point, dx: i32, dy: i32) -> Point {
    return Point{ x: p.x + dx, y: p.y + dy }
}
```

Struct literals use `{ field: value, ... }`. Field access is `.`.
Methods are functions in the same module that take a struct as their
first parameter.

## Enums and unions

```a7
enum Color { Red, Green, Blue }

union Value {
    i: i32
    f: f32
}
```

Enums are integer-tagged. Untagged unions allow field-literal construction
and field access; tagged unions are reserved.

## Arrays and slices

```a7
buf: [4]i32 = [1, 2, 3, 4]   // stack-allocated fixed array
sum: i32 = 0
i: usize = 0
while i < 4 {
    sum = sum + buf[i]
    i = i + 1
}

// slice view: (ptr, len)
view: []i32 = buf[..]
```

**`new [N]T` is currently rejected** — the heap fixed-array model is
not defined yet. Use stack arrays or slices.

## References

A7 references model "pass an lvalue". The compiler does the address-of and
dereference automatically.

```a7
fn bump(ref n: i32) {
    n = n + 1
}

var x: i32 = 5
bump(x)        // x is now 6 — no & or * needed
```

`nil` can only be assigned to reference/pointer types. Nil-check before
field access.

## Memory

```a7
fn make_pair() -> ref Pair {
    p: ref Pair = new Pair
    defer del p
    p.first  = 1
    p.second = 2
    return p
}
```

`new T` and `new [N]T`:
- `new T` on a scalar/struct allocates one. **Implemented.**
- `new [N]T` on a fixed array allocates `N`. **Currently rejected.**

`del p` frees. Use with `defer` for scope-end cleanup.

## Generics

```a7
fn max($T)(a: $T, b: $T) -> $T {
    if a > b { return a }
    return b
}

x: i32 = max(3, 7)
y: f64 = max(1.5, 2.5)
```

Type parameters use `$T`. Generic structs follow the same syntax.
Specialization is per call site (monomorphization). Cross-module generic
flow is incomplete — see [Status](/a7-py/compiler/status).

## Modules

```a7
import std/io
import std/math as m

pub fn main() -> i32 {
    io.println("hello")
    return 0
}
```

`std/*` modules are virtual — the compiler resolves them directly without
file lookup. File-backed imports for local modules are supported; they
lower into a single combined Zig output file.

## Casts and conversions

```a7
n: i32 = 100
big: i64 = cast(i64, n)
```

`cast()` is the only conversion — there are no implicit numeric promotions.
The safety pass approves or rejects casts before backend emission.

## What's reserved but not yet working

These syntactic forms parse but are not end-to-end:

- Multiple-return-value functions and destructuring binds.
- Variadic parameter runtime lowering.
- Intrinsics other than `@type_set`.
- Tagged union tag workflows.

See [Features](/a7-py/ref/features) for the line between supported and
reserved.

## Address-of / dereference operators

There are **no** public `.adr`, `.val`, `&`, or `*` operators in A7. The
compiler manages address-of and dereference automatically for `ref`
parameters and field access. Don't introduce these forms in examples,
tests, or docs.
