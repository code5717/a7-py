# Comparative: Zig

Status: Phase B research from before 2026-09-14. Where it conflicts with the
ledger in [`../../plan/decisions.md`](../../plan/decisions.md) or the
[memory plan](../../plan/memory.md), those documents win.

## Summary

Zig is A7's backend; A7 targets Zig 0.16.0. The codegen contract in
[`../05-for-a7.md` section 4.8](../05-for-a7.md#48-codegen-discipline--what-the-emitted-zig-must-look-like)
depends on knowing exactly where Zig traps, where it has undefined behaviour and
what `-O ReleaseFast` removes.

Zig has more compile-time safety than C and C++: mandatory error handling, no
implicit lossy conversions, and `comptime`. It has less than Rust: no borrow
checker and manual memory management. The contract says A7 must emit Zig that is
safe without Zig's runtime safety checks.

Note (2026-09-16): Zig is the backend, not the user model (L21, L22). A7 users
should not carry Zig's manual memory load; the memory plan lowers automatic
memory management to stack slots, arenas and pools in Zig.

## Build modes

| Mode | Runtime safety checks | Optimised |
| --- | --- | --- |
| `Debug` | All checks (overflow, OOB, null, UB) | No |
| `ReleaseSafe` | All checks | Yes |
| `ReleaseFast` | All checks disabled | Yes |
| `ReleaseSmall` | All checks disabled | Yes, for size |

Checks Zig inserts under `Debug` and `ReleaseSafe`:

- integer overflow on `+`, `-`, `*`: panic
- integer division by zero: panic
- slice or array access out of bounds: panic
- null unwrap of `?*T` with `.?`: panic
- cast overflow (`@intCast`, `@intFromFloat`): panic
- stack overflow: panic (architectural; depends on the OS)
- reaching `unreachable`: panic
- calling `@panic`: panic
- shift amount too large: panic

Under `ReleaseFast` and `ReleaseSmall`, each of these becomes undefined
behaviour. The optimiser assumes they never happen. A7's contract exists for this
case: A7 proves the conditions first, so the emitted Zig can build with
`ReleaseFast` without undefined behaviour.

## Per-gap findings

### Gap 01: Cast

Zig names each conversion:

- `@as(T, x)`: implicit conversion; compile error unless lossless.
- `@intCast(x)`: narrow or extend an integer; runtime check.
- `@floatCast(x)`: float conversion.
- `@intFromFloat(x)`: float to integer with a runtime range check.
- `@floatFromInt(x)`: integer to float; exact or rounded.
- `@bitCast(x)`: same-size reinterpretation; pointers excluded.
- `@ptrFromInt(x)`: integer to pointer; explicit and risky.
- `@intFromPtr(x)`: pointer to integer.

Except for `@as`, these take the target type from the result location, for
example `const y: u8 = @intCast(x);`. There is no overloaded `as` operator. The
runtime checks in `@intCast` and similar builtins become undefined behaviour
under `ReleaseFast`.

- Adopt: one name per kind of conversion. A7's proposed `cast` /
  `truncating_cast` / `bit_cast` follows Zig's `@as` / `@intCast` / `@bitCast`.
- Avoid: the runtime check fallback. A7 discharges bounds statically, so the
  emitted code has no runtime check to disable.

Note (2026-09-16): the earlier text listed the pre-0.11 two-argument forms
(`@intCast(T, x)`) and the old name `@floatToInt`. The forms above are the
current single-argument builtins, matching the `@intCast(count)` output recorded
in plan gate G3. A7's cast vocabulary is open under G3.

### Gap 02: Nullable pointers

Zig separates `*T` (non-null) from `?*T` (nullable):

```zig
const p: *T = ...;       // never null
const q: ?*T = null;     // may be null

const x = p.*;           // safe: p is non-null
const y = q.?.*;         // .? unwraps with runtime null check;
                          // ReleaseFast turns this into UB
```

`if (q) |val| { val.* }` is the safe unwrap.

- Adopt: the mapping directly. A7 `ref T` lowers to Zig `*T`, and `?ref T`
  lowers to `?*T`. The unwrap pattern is `if (q) |val|`.
- Avoid: emitting `.?`. On a null value under `ReleaseFast` it is undefined
  behaviour. A7's types guarantee non-null wherever the emission uses `*T`, so
  `.?` should never appear in emitted code.

Note (2026-09-16): the memory plan removes stored `ref` and `nil` (gates M4, M6).
Optionals wrap values; the rule against emitting `.?` still holds for any
optional.

### Gap 03: Definite assignment

Zig's definite-assignment checking is limited. Reading `undefined` is undefined
behaviour:

```zig
var x: i32 = undefined;  // explicit "uninit"
const y = x;              // UB in ReleaseFast; safety check in Debug
```

Zig requires every local to be initialised, with `undefined` as the explicit
"filled in later" value. A7's definite-assignment pass must emit either a real
initial value or `undefined` followed by a guaranteed write before any read.

- Adopt: `undefined` as the explicit marker for delayed initialisation. A7's
  pass ensures a write precedes every read.

### Gap 04: NonZero division

`@divTrunc(a, b)` panics on `b == 0` under `Debug` and `ReleaseSafe`, and is
undefined behaviour under `ReleaseFast`.

A7's `NonZero<T>` proof discharges the obligation first. The emission is a bare
`@divTrunc(a, d.value)`, and A7's types guarantee the divisor is not zero.

- Adopt: separate names for each rounding mode: `@divTrunc`, `@divExact` and
  `@divFloor`. A7 should match.

Note (2026-09-16): integer division rules, including signed `MIN / -1`, are
open under gate G3. Float division follows IEEE 754 (L16).

### Gap 05: Stack budget

Zig has no compile-time maximum-stack analysis. The earlier study named a
`@frameSize(func)` builtin for introspection. The OS sets `RLIMIT_STACK`, and a
program can exhaust it.

A7 does the budget analysis itself. Zig neither helps nor gets in the way.

Uncertain: `@frameSize` belonged to Zig's async feature and may not exist in
Zig 0.16.0.

### Gap 06: Typed arithmetic

Zig has wrapping (`+%`), saturating (`+|`) and overflow-reporting
(`@addWithOverflow`) operations. Bare `+` panics on overflow under `Debug` and
`ReleaseSafe`, and is undefined behaviour under `ReleaseFast`.

```zig
const c1 = a +% b;                       // wrapping
const c2 = a +| b;                       // saturating
const result = @addWithOverflow(a, b);   // returns (T, u1) tuple
if (result[1] == 0) use(result[0]);
```

- Adopt: the vocabulary as lowering targets. A7's `wrap_add` lowers to `+%`,
  `sat_add` to `+|` and `checked_add` to `@addWithOverflow`. The same holds for
  `-` and `*`.
- Avoid: emitting bare `+` on operands not proven to fit. A7's range tracker
  proves they fit; otherwise the user picks an explicit form.

Note (2026-09-16): L5 changes the reason. Ordinary A7 `+`, `-`, `*` wrap, so they
lower to `+%`, `-%`, `*%` (plan track 3). Bare Zig `+` must still never be
emitted, because it traps in `Debug` and is undefined in `ReleaseFast`. Plan gate
G3 records that `x += 1` on `x: u8 = 255` currently emits bare `x += 1`.

```a7
// Proposed lowering under L5; current output differs (plan gate G3)
x: u8 = 255
x += 1          // Zig: x +%= 1; x is 0 in every build mode
```

### Gap 07: Bounded indexing

Zig slices have `.ptr` and `.len`. `s[i]` checks `i < s.len` under `Debug` and
`ReleaseSafe` and panics, or is undefined behaviour under `ReleaseFast`.

The safe-by-construction pattern emits `s.ptr[i]`, a raw pointer index with no
bounds check in any mode, after A7 has proved `i < s.len`. A7's emission does
this (section 4.8.3 of `05-for-a7.md`).

- Adopt: the `s.ptr[i]` emission. The missing runtime check shows that A7's
  static analysis carries the guarantee.

Note (2026-09-16): the memory plan removes `.ptr` from the public A7 surface
(section 3). This is an emission detail and is unaffected.

### Gap 08: Error unions, not Option and Result

Zig's failure shape is the error union `!T`:

```zig
fn parse(s: []const u8) !i32 {
    if (s.len == 0) return error.Empty;
    // ...
}

const x = try parse("42");  // propagates error; returns from current fn on error
const y = parse("42") catch |err| return err;
```

`try` and `catch` propagate errors, like Rust's `?`. Errors are enum-like values
from a global error set.

- Adopt: `try`. A7's `?` propagation operator could lower to it directly.
- Avoid: the global error set. Zig's errors are not parameterised and leak
  across modules. A7's `Result<T, E>` is structural and per module.

### Gap 09: Refinement-lite

Zig has `comptime`, a Turing-complete compile-time sublanguage, and
`comptime` parameters:

```zig
fn bounded(comptime lo: i32, comptime hi: i32, x: i32) i32 {
    if (x < lo or x > hi) @compileError("out of range");
    return x;
}
```

Zig has no first-class refinement types; `comptime` does that work.

- Adopt: `comptime` for static value parameters (gap 09, question Q09b). A7's
  `static N: usize` is the same idea.

### Gap 10: Ownership

Zig has no ownership system. Every allocation takes an `Allocator` argument, and
the user calls `destroy` or `free`. Aliasing and use after free are the
programmer's problem.

A7 supplies ownership. Zig is the backend; ownership exists only at the A7
level.

Note (2026-09-16): under the memory plan the user never names an allocator or
frees storage. The compiler infers extents and lowers them to stack locals,
`ArenaAllocator`-style extents and pool slabs behind a lowering layer, so Zig
API changes stay local (section 4). Plan gate G2 records that current A7 can
emit two `allocator.destroy` calls for one allocation.

### Gap 11: Finite floats

Zig allows NaN and infinity in `f32` and `f64`, and arithmetic propagates them,
as in C and Rust. `std.math.isNan` and `std.math.isInf` query values.

A7 was to provide `Fin<F>` at its own level only.

Note (2026-09-16): superseded by L16. A7 floats follow Zig and C; `Fin<F>` is
withdrawn. Remaining float details, such as contraction and an opt-in fast mode,
are open under plan gate G1.

### Gap 12: FFI

`@cImport(...)` parses C headers and produces declarations, and `extern fn`
declares foreign functions.

- Adopt: A7's foreign interface inherits Zig's. A7's `extern fn libc_read(...)`
  lowers to Zig's `extern fn libc_read(...)`, and A7 adds the `Result<T, E>`
  return rule.

Note (2026-09-16): the memory plan adds native descriptors for borrowing,
retention and returned storage (gate M12).

## What A7 should adopt

1. Per-operation cast names as lowering targets (`@as`, `@intCast`, `@bitCast`
   for A7's `cast`, `truncating_cast`, `bit_cast`; open under G3).
2. `*T` and `?*T` lowering for non-null and nullable references.
3. `+%`, `+|` and `@addWithOverflow` as lowering targets for A7 arithmetic
   (`+%` for ordinary operators under L5).
4. `s.ptr[i]` emission to skip bounds checks A7 has already proved.
5. `undefined` for explicit delayed initialisation.
6. `try` for error propagation.
7. `comptime` for static value parameters.
8. `@cImport` and `extern fn` for foreign code.

## What to avoid in emitted Zig

1. Bare `.?` on optionals: undefined behaviour under `ReleaseFast`.
2. Bare `s[i]` on slices when `i` is not proven in range.
3. Bare `+`, `-`, `*` or `<<` on integers not proven to fit.
4. Bare `@divTrunc(a, b)` without a `NonZero<T>` proof.
5. `@panic` on any path the user did not request.
6. `unreachable` outside lines tagged `// proof-dead`.
7. `@intCast` without a range proof: undefined behaviour under `ReleaseFast`.

Note (2026-09-16): under L5, item 3 is satisfied for `+`, `-`, `*` by emitting
`+%`, `-%`, `*%`; `<<` still needs a shift-count rule (G3). The memory plan
emits its residual runtime checks as explicit A7 code with defined outcomes,
never as Zig safety checks (section 4, "Checks are A7 code").

## The contract against Zig

> Every A7-emitted Zig source file compiles cleanly with
> `zig build-exe -O ReleaseFast` and runs the program to
> completion against its golden output. The absence of every
> runtime safety check that ReleaseFast removes is the
> definition of A7 having discharged each safety obligation
> statically.

This is the test in `../05-for-a7.md` section 4.8.13.

Note (2026-09-16): the memory plan amends the contract to allow listed residual
checks with defined outcomes and a program stop on non-recoverable out-of-memory
(gate M16, proposed). Memory claims need both native `Debug` and `ReleaseFast`
runs (memory plan section 8).

## Sources

- [Zig documentation](https://ziglang.org/documentation/master/)
- [Memory](https://ziglang.org/documentation/master/#Memory)
- [Undefined Behavior](https://ziglang.org/documentation/master/#Undefined-Behavior)
- [Build Mode](https://ziglang.org/documentation/master/#Build-Mode)
- [Pointers](https://ziglang.org/documentation/master/#Pointers)
- [Slices](https://ziglang.org/documentation/master/#Slices)
- [Errors](https://ziglang.org/documentation/master/#Errors)
