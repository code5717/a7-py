# Standard Library

A7's standard library is small by design. Each module is a single virtual
import resolved by the compiler — no source file is loaded from disk.
Backends map standard-library calls to their native equivalents (Zig
stdlib for the Zig backend).

## `std/io` — input and output

```a7
import std/io

pub fn main() -> i32 {
    io.println("hello")
    io.print("count: "); io.println_i32(42)
    return 0
}
```

| Function | Signature | Notes |
|---|---|---|
| `io.print(s: string)` | print to stdout, no newline | UTF-8 |
| `io.println(s: string)` | print + newline | |
| `io.println_i32(n: i32)` | print integer + newline | |
| `io.println_u64(n: u64)` | print integer + newline | |
| `io.println_f64(n: f64)` | print float + newline | |
| `io.eprint(s: string)` | print to stderr | |

The Zig backend preserves stdout/stderr semantics on the pinned Zig 0.16
toolchain.

## `std/math` — numeric helpers

```a7
import std/math as m

x: f64 = m.sqrt(2.0)
y: i32 = m.abs(-5)
z: f64 = m.pow(2.0, 10.0)
```

| Function | Signature | Notes |
|---|---|---|
| `math.abs(n)` | `abs($T) -> $T` for signed ints / floats | |
| `math.min(a, b)`, `math.max(a, b)` | binary min/max | |
| `math.sqrt(x: f64)` | square root | |
| `math.pow(x: f64, y: f64)` | power | |
| `math.floor(x)`, `math.ceil(x)`, `math.round(x)` | floats | |

## `std/mem` — memory helpers

```a7
import std/mem
```

| Function | Signature | Notes |
|---|---|---|
| `mem.zero(buf: []u8)` | zero a slice | |
| `mem.copy(dst: []u8, src: []u8) -> usize` | copy bytes, return count | |
| `mem.equals(a: []u8, b: []u8) -> bool` | byte-equality | |

## `std/string` — string operations

```a7
import std/string as s

n: usize = s.length("hello")
ok: bool = s.starts_with("hello world", "hello")
```

| Function | Signature | Notes |
|---|---|---|
| `string.length(s: string) -> usize` | UTF-8 byte length | |
| `string.starts_with(s, prefix) -> bool` | prefix check | |
| `string.ends_with(s, suffix) -> bool` | suffix check | |
| `string.contains(s, needle) -> bool` | substring check | |
| `string.equals(a, b) -> bool` | exact equality | |

## `std/debug` — debugging aids

```a7
import std/debug as dbg

pub fn main() -> i32 {
    dbg.assert(2 + 2 == 4)
    dbg.trace("entering main")
    return 0
}
```

| Function | Signature | Notes |
|---|---|---|
| `debug.assert(cond: bool)` | aborts on false in debug builds | release no-op |
| `debug.trace(s: string)` | print to stderr with `[trace]` prefix | |

## `std/random` — pseudo-random numbers

```a7
import std/random as r

r.seed(42)
n: i32 = r.range_i32(0, 100)    // [0, 100)
f: f64 = r.range_f64(0.0, 1.0)  // [0.0, 1.0)
```

| Function | Signature | Notes |
|---|---|---|
| `random.seed(s: u64)` | seed the PRNG | |
| `random.range_i32(lo, hi) -> i32` | half-open `[lo, hi)` | |
| `random.range_f64(lo, hi) -> f64` | half-open `[lo, hi)` | |
| `random.next_u64() -> u64` | raw 64-bit output | |

## Registry

The stdlib registry lives at `a7/stdlib/__init__.py`. Each backend can
register its own mapping for stdlib calls. To add a module:

1. Create `a7/stdlib/<name>.py` with the symbol table and Zig mappings.
2. Register it in `a7/stdlib/__init__.py`.
3. Add a test in `test/test_stdlib_registry.py`.
4. Document it in this page and update [Status](/a7-py/compiler/status).

## What's not yet here

- `Option<T>`, `Result<T, E>` — planned but not implemented.
- Collections (`Vec`, `HashMap`) — planned.
- File / network IO — out of current scope.
- Concurrency primitives — deferred.

See [Status](/a7-py/compiler/status) for the canonical roadmap.
