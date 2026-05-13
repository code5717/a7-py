# Safety

A7's safety model is a single compile-time pass that proves or rejects
risky operations *before* the backend emits Zig. There is no runtime
checking system outside of what the proof pass requests explicitly.

## Goals

1. **No undefined behaviour in emitted Zig** as a result of A7-source
   issues we could have caught.
2. **No silent narrowing** in numeric casts.
3. **No use-after-`del`** at the AST level.
4. **No recursion** in A7 source — at all.

## Banned at compile time

These are compile-time errors. The compiler does not try to be clever.

### Source recursion

```a7
fn f() -> i32 { return f() }   // ERROR: direct recursion
```

```a7
fn a() -> i32 { return b() }
fn b() -> i32 { return a() }   // ERROR: mutual recursion
```

```a7
fn f() -> i32 { return 0 }
var p: fn() -> i32 = f
fn main() -> i32 { return p() }
// ERROR if any path reaches p back to f
```

The semantic validator computes the call/alias graph with a worklist and
rejects any cycle.

### Heap fixed arrays

```a7
var buf: ref [4]i32 = new [4]i32     // ERROR: new [N]T rejected
```

The language model for heap-allocated fixed arrays hasn't been defined.
Use a stack array (`buf: [4]i32`) or a slice over heap memory.

### Reference operators in source

A7 does not expose `&`, `*`, `.adr`, or `.val` to the source. These would
be ambiguous with the compiler-managed address-of/dereference for `ref`
parameters. The compiler refuses to parse them in user source.

## Proven at compile time

The safety planner (`a7/safety.py`) generates obligations for these
operations and discharges them where possible:

### Casts

```a7
n: i32 = 1000
b: u8  = cast(u8, n)   // safety obligation: range fits
```

The planner checks the source's known value range against the target
type. If proven safe statically, the cast emits without a check. If
not, the planner requests the backend to insert a runtime check.

### Division / modulo

```a7
q := a / b
```

Denominator must be provably non-zero. If `b` is a constant, the planner
checks at compile time; if a variable, the backend inserts a runtime
non-zero check.

### Indexing / slicing

```a7
x := arr[i]
s := arr[lo..hi]
```

The planner requires `i < len(arr)` and `lo <= hi <= len(arr)`. Constant
indices over fixed arrays are proven statically. Dynamic indices fall
back to runtime bounds checks unless the planner can prove safety from
prior `if` guards.

### Reference dereferences

```a7
fn use(ref p: T) {
    if p == nil { return }
    use_value(p)    // proven non-nil here
}
```

The planner tracks nil-narrowing across control flow. Any read of `p`
that isn't proven non-nil is rejected.

### Direct use after `del`

```a7
del p
use(p)           // ERROR: use after del
```

The planner inserts a "dead" obligation on `p` after `del` and refuses
any further read.

## Failure mode

If the planner cannot discharge an obligation:

1. Try to insert a runtime check via the backend plan.
2. If the operation has no supported runtime check, reject the program
   with a structured `SemanticError` (exit code **6**).

The planner is intentionally conservative. A diagnostic always names the
operation, the source span, and the obligation that failed.

## What's not yet covered

Tracked in [Status](/a7-py/compiler/status) — these proofs are incomplete:

- Fixed-width integer overflow on `+ - *`.
- Shift amount obligations.
- Union discriminant access.
- Full `ref` / `del` alias behaviour.
- Ownership and lifetime guarantees.

Programs that exercise these areas may compile to Zig output that the
Zig compiler then catches. The goal is to push every catch to the A7
side over time.

## Trust boundary

This is the most important safety statement:

> **A7 is not a sandbox.** The compiler emits Zig that the host Zig
> toolchain builds and runs. Compiled A7 programs can do anything the
> host environment permits. Only compile and execute A7 source you
> trust.

This is true today and will remain true. The safety pass protects
correctness of emitted Zig; it does not isolate the host.
