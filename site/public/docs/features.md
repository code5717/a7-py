# Features

This page draws the line between **supported** features (compile + run
end-to-end) and **reserved** ones (syntax may parse, but the backend
rejects or doesn't emit). Treat anything not listed as unsupported.

## Supported (compile + run today)

### Types

- Primitive integers: `i8 i16 i32 i64 u8 u16 u32 u64 usize isize`.
- Floats: `f32 f64`.
- `bool`, `char`, `string`.
- Fixed-size stack arrays `[N]T`.
- Slices `[]T` (`ptr + len` pair).
- References `ref T`.
- Function types (raw and aliased).
- Structs with literal `{ field: ... }` construction.
- Enums (integer-tagged).
- Untagged unions with field-literal construction and access.
- Type aliases.

### Declarations

- `const`, `var`, `:=` inference.
- `fn` with `pub` visibility.
- `struct`, `enum`, `union`.
- Local nested function declarations.
- Type aliases.

### Control flow

- `if` / `else if` / `else`.
- `while` loops with `break` / `continue`.
- `for i in range`, `for x in iterable`.
- Labeled loops.
- `match` with exhaustiveness for `bool` and `enum`.
- `defer` (last-declared-first-run at scope exit).

### Functions

- Direct, mutual, alias-mediated, and callback-trampoline recursion are
  **rejected** at compile time. Use loops or explicit stacks.

### Expressions

- All operators with proper precedence.
- Fixed-array `+` for same-shape numeric arrays.
- `cast(T, v)` for explicit conversion.
- `if`-as-expression.
- Struct and array literals.
- Untagged union field literal/access.

### Memory

- `ref` parameters take ordinary lvalue arguments (no `&`, no `*`).
- `ref` struct fields after nil check.
- `new T` for scalar/struct allocation.
- `del p` with `defer` cleanup.

### Imports

- Virtual `std/io`, `std/math`, `std/mem`, `std/string`, `std/debug`,
  `std/random`.
- Simple file-backed alias imports lower into a single combined Zig
  output file.

### Generics

- Type parameters `$T`.
- Type-set constraints via `@type_set`.
- Generic structs, generic struct literals.
- Simple top-level generic function calls (monomorphization per call site).

### Code generation

- A7 → Zig source via the Zig backend.
- Build via host Zig 0.16 toolchain.

### Standard library

- `std/io`, `std/math`, `std/mem`, `std/string`, `std/debug`, `std/random`.

### Diagnostics

- Rich structured error messages with source context.
- JSON output for every mode via `--format json`.

## Reserved (parsed or planned, not end-to-end)

These forms may parse, but the backend doesn't emit them or the semantic
pass rejects them. Don't ship examples or docs that rely on them as if
they worked.

- **Multiple-declaration / destructuring binds** (e.g. `a, b := pair()`)
  — parsed only.
- **Variadic parameters** at runtime — parsed only.
- **Intrinsics other than `@type_set`** — placeholder.
- **Heap fixed arrays** (`new [N]T`) — rejected at compile time.
- **Tagged union tag workflows** — reserved.
- **Multiple return values** — reserved (workaround: return a struct).
- **Cross-module generic specialization** — incomplete.
- **`Option<T>` / `Result<T, E>`** — planned stdlib.
- **Collections (Vec, HashMap)** — planned stdlib.
- **Address-of (`&`) / dereference (`*`)** — not part of the public
  language. The compiler manages address-of and dereference for `ref`
  parameters automatically. Don't introduce these in source or docs.

## Out of scope

These are explicitly **not** features of A7 or this repository:

- Package registry / `a7 install`.
- Runtime polymorphism, vtables, GC.
- A sandbox for untrusted source.
- GPU / tensor primitives (deferred track).
- Concurrency runtime (deferred track).

See [Status](/a7-py/compiler/status) for the canonical roadmap and the
order in which reserved items become supported.
