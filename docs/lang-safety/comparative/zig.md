# Comparative: Zig

> Phase B artifact in the `docs/lang-safety/` research process.

Zig is **A7's backend**. Understanding Zig's safety story exactly
— where it traps, where it's UB, what `-O ReleaseFast` removes —
is mandatory for the codegen-discipline contract in
[`../05-for-a7.md` §4.8](../05-for-a7.md#48-codegen-discipline--what-the-emitted-zig-must-look-like).

Zig occupies an unusual position: it has *more* compile-time
safety than C/C++ (mandatory error handling, no implicit
conversions, `comptime`) but *less* than Rust (no borrow checker;
manual memory management). The contract says A7 must produce Zig
that is safe **without** Zig's runtime safety checks.

Primary sources:

- [Zig documentation](https://ziglang.org/documentation/master/)
- [Zig language reference](https://ziglang.org/documentation/master/#Memory)
- [Undefined Behavior in Zig](https://ziglang.org/documentation/master/#Undefined-Behavior)
- [Zig build modes](https://ziglang.org/documentation/master/#Build-Mode)

---

## Zig's optimisation modes (this is the central context)

| Mode | Runtime safety checks | Optimised |
| --- | --- | --- |
| `Debug` | All checks (overflow, OOB, null, UB) | No |
| `ReleaseSafe` | All checks | Yes |
| `ReleaseFast` | **All checks disabled** | Yes |
| `ReleaseSmall` | All checks disabled | Yes (for size) |

The runtime safety checks Zig inserts under Debug/ReleaseSafe:

- Integer overflow on `+`, `-`, `*` — panic
- Integer divide-by-zero — panic
- Slice/array OOB access — panic
- Null pointer deref (on `?*T` after `.?`) — panic
- Cast overflow (`@intCast`, `@floatToInt`) — panic
- Stack overflow — panic (architectural; OS-level)
- `unreachable` reached — panic
- `@panic` called — panic
- Shift-amount too large — panic

Under `ReleaseFast` (and `ReleaseSmall`), **all of these become
undefined behaviour.** The compiler is free to assume they don't
happen and optimise accordingly. This is exactly what A7's
contract is built to handle: A7 must prove the conditions
upstream so the emitted Zig can be `ReleaseFast` without UB.

---

## How Zig handles each gap

### Gap 01 — Cast

Zig has fine-grained cast operators:

- `@as(T, x)` — implicit conversion (compile error if not lossless)
- `@intCast(T, x)` — narrow / extend integer; runtime check
- `@floatCast(T, x)` — float conversion
- `@intFromFloat(T, x)` — float-to-int with runtime range check
- `@floatFromInt(T, x)` — int-to-float (always lossless or
  rounding)
- `@bitCast(T, x)` — same-size reinterpret (pointers excluded)
- `@ptrFromInt(T, x)` — int-to-pointer (sketchy, but explicit)
- `@intFromPtr(x)` — pointer-to-int

Each has a name; no overloaded `as`-style operator. The runtime
checks in `@intCast` etc. become UB under `ReleaseFast`.

**What A7 can steal:** **the per-operation naming**. A7's
proposed `cast` / `truncating_cast` / `bit_cast` triple is
inspired by Zig's `@as` / `@intCast` / `@bitCast`. The Zig
discipline of "each kind of conversion has its own name" is
worth importing.

**What A7 should not steal:** the runtime check fallback. A7
discharges the bound statically; the emission has no runtime
check to disable.

---

### Gap 02 — Nullable pointers

Zig distinguishes `*T` (non-null) from `?*T` (nullable):

```zig
const p: *T = ...;       // never null
const q: ?*T = null;     // may be null

const x = p.*;           // safe: p is non-null
const y = q.?.*;         // .? unwraps with runtime null check;
                          // ReleaseFast turns this into UB
```

The pattern `if (q) |val| { val.* }` is the safe unwrap.

**What A7 can steal:** **directly**. A7's `ref T` (non-null) →
Zig `*T`; `?ref T` → Zig `?*T`. The mapping is one-to-one. The
unwrap pattern is `if (q) |val|`.

**What A7 must avoid:** **emitting `.?` in generated Zig**.
Under `ReleaseFast`, `.?` on a null is UB. A7's type system
guarantees non-null at every point where the Zig emission uses
`*T`; the `.?` operator should never appear in A7-emitted code.

---

### Gap 03 — Definite assignment

Zig has limited definite-assignment checking. Reading `undefined`
is UB:

```zig
var x: i32 = undefined;  // explicit "uninit"
const y = x;              // UB in ReleaseFast; safety check in Debug
```

Zig requires you to initialise locals (with `undefined` as the
opt-in for "I'll fill this in later"). A7 must lower its DA pass
to either emit explicit initial values or `undefined` plus a
*guaranteed* write before any read.

**What A7 can steal:** the **`undefined` literal as the explicit
opt-in** for delayed initialisation. A7's DA pass ensures this
is followed by a write before any read.

---

### Gap 04 — NonZero division

Zig division: `@divTrunc(a, b)` panics on `b == 0` under Debug /
ReleaseSafe; UB under ReleaseFast.

A7's `NonZero<T>` proof discharges the obligation upstream. The
emission is bare `@divTrunc(a, d.value)` and the absence of a
zero divisor is guaranteed by A7's type system.

**What A7 can steal:** the **explicit `@divTrunc` vs `@divExact`
vs `@divFloor`** naming. Each rounding mode has its own
operator; A7 should match.

---

### Gap 05 — Stack budget

Zig has `@frameSize(func)` builtin for introspection but no
compile-time max-stack analysis. The OS sets `RLIMIT_STACK`; a
program can exhaust it.

**What A7 contributes:** the budget analysis is A7-side; Zig
doesn't help, but doesn't get in the way.

---

### Gap 06 — Typed arithmetic

Zig has wrapping (`+%`), saturating (`+|`), and overflow-detecting
(`@addWithOverflow`) operators. Bare `+` panics on overflow under
Debug/ReleaseSafe; UB under ReleaseFast.

```zig
const c1 = a +% b;                       // wrapping
const c2 = a +| b;                       // saturating
const result = @addWithOverflow(a, b);   // returns (T, u1) tuple
if (result[1] == 0) use(result[0]);
```

**What A7 can steal:** the operator vocabulary (`+%`, `+|`,
`@addWithOverflow`) **directly**. A7's `wrap_add` lowers to `+%`;
`sat_add` to `+|`; `checked_add` to `@addWithOverflow`. Same
mapping for `-`, `*`.

**What A7 must avoid:** emitting bare `+` on opaque operands.
A7's range tracker proves the operands fit; if it can't, the
user picks one of the explicit forms.

---

### Gap 07 — Bounded indexing

Zig slices have `.ptr` and `.len`. Indexing `s[i]` checks `i <
s.len` under Debug/ReleaseSafe (panic) or is UB under ReleaseFast.

The **safe-by-shape** pattern: use `s.ptr[i]` (raw pointer index;
no bounds check anywhere) after A7 has proved `i < s.len`. This
is exactly what A7's emission does (per §4.8.3 of `05-for-a7.md`).

**What A7 can steal:** **the `s.ptr[i]` emission trick**. The
absence of a runtime bounds check is the proof that A7's static
analysis was load-bearing.

---

### Gap 08 — Error unions, not Option/Result

Zig's fallibility shape is different: `!T` is an **error union**:

```zig
fn parse(s: []const u8) !i32 {
    if (s.len == 0) return error.Empty;
    // ...
}

const x = try parse("42");  // propagates error; returns from current fn on error
const y = parse("42") catch |err| return err;
```

Zig's `try` / `catch` is the propagation mechanism (analog of
Rust's `?`). Errors are *enum-like values* drawn from a global
error set.

**What A7 can steal:** the **`try`** operator (the Rust `?`
analog). A7's `?`-propagation operator could lower to Zig's
`try` directly.

**What A7 should not steal:** the **global error set** —
Zig's errors are not parametrised, leaking across modules. A7's
`Result<T, E>` is structural and per-module.

---

### Gap 09 — Refinement-lite

Zig has **`comptime`** (a Turing-complete compile-time
sublanguage) and `comptime`-typed parameters:

```zig
fn bounded(comptime lo: i32, comptime hi: i32, x: i32) i32 {
    if (x < lo or x > hi) @compileError("out of range");
    return x;
}
```

But Zig doesn't have first-class refinement types. The
`comptime` mechanism is the workhorse.

**What A7 can steal:** the **`comptime`** discipline for static
value parameters (Gap 09 Q09b). A7's `static N: usize` is the
same idea.

---

### Gap 10 — Ownership

Zig **has no ownership system**. Manual allocator pattern: every
allocation takes an `Allocator` argument; the user calls
`destroy` explicitly. Aliasing and UAF are the programmer's
problem.

**What A7 contributes:** the ownership system. Zig is the
backend; ownership lives at the A7 level only.

---

### Gap 11 — Finite floats

Zig allows NaN/inf in `f32`/`f64`; arithmetic propagates. Same as
C/Rust. `std.math.isNan` / `isInf` query.

**What A7 contributes:** `Fin<F>` is A7-level only.

---

### Gap 12 — FFI

Zig's FFI is excellent. `@cImport(...)` parses C headers and
generates declarations; `extern fn` declares foreign functions.

**What A7 can steal:** **A7's FFI inherits Zig's directly.**
A7's `extern fn libc_read(...)` lowers to Zig's `extern fn
libc_read(...)`, with A7 adding the `Result<T, E>`-return
discipline on top.

---

## Primary sources

- [Zig documentation](https://ziglang.org/documentation/master/)
- [Undefined Behavior](https://ziglang.org/documentation/master/#Undefined-Behavior)
- [Build Mode](https://ziglang.org/documentation/master/#Build-Mode)
- [Memory](https://ziglang.org/documentation/master/#Memory)
- [Pointers](https://ziglang.org/documentation/master/#Pointers)
- [Slices](https://ziglang.org/documentation/master/#Slices)
- [Errors](https://ziglang.org/documentation/master/#Errors)

---

## What A7 can steal — consolidated

1. **Per-operation cast naming** (`@as`/`@intCast`/`@bitCast` → A7's
   `cast`/`truncating_cast`/`bit_cast`).
2. **`*T` vs `?*T` lowering** for non-null vs nullable references.
3. **`+%`/`+|`/`@addWithOverflow`** as the lowering targets for
   A7's typed arithmetic.
4. **`s.ptr[i]` emission** to skip bounds checks when A7 has
   proved them statically.
5. **`undefined` literal** for explicit-uninit DA.
6. **`try` operator** for error propagation.
7. **`comptime`** for static value parameters.
8. **`@cImport` / `extern fn`** for FFI.

## What A7 must avoid in its Zig emission

1. **Bare `.?`** on `?*T` — would be UB under ReleaseFast.
2. **Bare `s[i]`** on `[]T` slices with opaque `i`.
3. **Bare `+`/`-`/`*`/`<<`** on opaque integers.
4. **Bare `@divTrunc(a, b)`** without a `NonZero<T>` proof.
5. **`@panic`** in any emission path the user didn't explicitly
   request.
6. **`unreachable`** outside lines tagged `// proof-dead`.
7. **`@intCast`** without a range proof (would be UB under
   ReleaseFast).

## The contract restated against Zig

> Every A7-emitted Zig source file compiles cleanly with
> `zig build-exe -O ReleaseFast` and runs the program to
> completion against its golden output. The absence of every
> runtime safety check that ReleaseFast removes is the
> definition of A7 having discharged each safety obligation
> statically.

This is exactly the test in `../05-for-a7.md` §4.8.13.
