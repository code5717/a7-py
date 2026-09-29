# Comparative: Mojo

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Mojo is the most recent attempt to ship Rust-class ownership in a
Python-flavored systems language. Chris Lattner's Modular team started it in
2023. Mojo combines:

- Python-compatible syntax;
- an MLIR-based backend (MLIR is part of the LLVM project);
- ownership and borrow checking, derived from Rust and influenced by Swift;
- value semantics with `inout` and `borrowed` parameters, similar to Hylo and
  Swift.

Mojo is in active development and many features are in flux. Its ownership
design was stable enough to study at the time of writing.

## Argument conventions

| Convention | Semantics |
| --- | --- |
| `borrowed` (default for non-`inout` parameters) | Immutable borrow |
| `inout` | Exclusive mutable borrow |
| `owned` | Consume; take ownership |

Two defaults stand out:

- Parameters are `borrowed` unless marked otherwise. This is closer to a shared
  reference than to Rust's move-by-default.
- Callers write no sigils. The call is `f(x)` whatever the parameter mode, not
  `f(&x)`.

```mojo
fn process(borrowed x: Buffer):
    # x is read-only
    pass

fn modify(inout x: Buffer):
    x.data[0] = 1

fn consume_it(owned x: Buffer):
    # x is owned by this function; caller loses access
    pass
```

## Exclusivity

Mojo enforces argument exclusivity for mutable references. A function that
receives a value as `inout` cannot receive any other reference, borrowed or
`inout`, to the same value. As in Swift, this is checked statically where
possible; a runtime fallback is rare.

## Per-gap findings

| Gap | Mojo |
| --- | --- |
| 01 Cast | Python-like patterns with stronger typing; explicit conversions such as `Int(x)` and `Float64(x)`. |
| 02 Nullable pointers | `Optional[T]`; references are non-null by default in the safe subset. |
| 03 Definite assignment | Enforced. |
| 04 `NonZero` division | No `NonZero` family in the standard library yet. Division by zero is a runtime trap. |
| 05 Stack budget | Not addressed. |
| 06 Typed arithmetic | Overflow allowed in release; no first-class range tracking. |
| 07 Bounded indexing | Standard runtime check; out of bounds raises. |
| 08 Option/Result | `Optional[T]`; the `Result` equivalent is in flux. |
| 09 Refinement-lite | Not present. |
| 11 Finite floats | Standard IEEE 754; no `Fin<F>` analog. |
| 12 FFI | C interop through MLIR's C dialect; details in flux. |

> Note (2026-09-16): A7 floats now follow IEEE 754 as in Zig and C (L16), so
> A7 matches Mojo on Gap 11.

### Gap 10 — Affine ownership

The three conventions plus argument exclusivity are the core of Mojo's safety
story. The model is Swift's, with two differences:

1. No caller-side sigils: `f(x)` regardless of whether the parameter is
   `borrowed`, `inout` or `owned`. The syntax is cleaner and less Rust-like.
   (Swift requires `&x` for `inout` arguments.)
2. `inout` exclusivity is enforced statically more aggressively than in Swift.

Mojo's lifetime system (written `Lifetime[bool]` / `Lifetime[mutable]` in the
original notes) gives reference parameters without named lifetime parameters in
signatures. The parameter is the lifetime, and it is inferred, similar to Hylo.

Mojo's pragmatic mix of Rust-class safety with simpler syntax is evidence that
A7's target is reachable.

## What A7 should adopt

1. No caller-side sigils, whatever the parameter mode. This is a real ergonomic
   improvement over Rust's `&x`, `&mut x` and `x` at call sites.
2. `owned` as the consume keyword. It reads as plain English, better than
   `consume` or `sink`.
3. Mojo's existence as evidence that borrow-checker-class safety can ship
   without alienating mainstream programmers.

Item 1 is already current A7 behavior for `ref` parameters: the caller passes an
ordinary lvalue.

```a7
// Current A7
Counter :: struct {
    value: i32
}

increment :: fn(counter: ref Counter) {
    counter.value += 1
}

main :: fn() {
    c := Counter{value: 0}
    increment(c)   // no sigil at the call site
}
```

> Note (2026-09-16): Item 2 is superseded. L6 approves no parameter-mode syntax,
> and the memory plan makes ownership internal, so A7 source has no consume
> keyword. See [decisions.md](../../plan/decisions.md) and
> [memory.md](../../plan/memory.md).

## What to avoid

1. Python-compatible syntax; A7 has its own.
2. The MLIR backend; A7 emits Zig.
3. Mojo's full runtime and metaprogramming surface.
4. Parameters borrowed by default, which is debatable. Phase B suggested A7 might
   prefer by-value parameters, with an implicit borrow for non-`Copy` types.

> Note (2026-09-16): L6 makes argument bindings immutable. The memory plan
> treats values as copies semantically and lets the compiler remove unobservable
> copies (contract item 4).

## Lessons for A7

In Phase B, Mojo was doing what A7 planned, at a much larger scale and with far
more compiler engineering. The shipped features were the ones A7 planned to
ship:

- three parameter modes (`borrowed`, `inout`, `owned`);
- static argument exclusivity;
- lifetime inference at function signatures, with no named lifetimes.

A7 differed in two ways. It emits Zig rather than targeting LLVM or MLIR, and it
committed to zero runtime errors rather than safe-by-default with traps. The
type-system mechanism was the same.

If A7's design drifted from these basics, Mojo was the counterargument: this is
what mainstream adoption of compile-time ownership looks like, so match it
rather than invent something new.

> Note (2026-09-16): Two parts are superseded. The memory plan hides ownership
> and has no parameter modes in source (O2, L6). The "zero runtime errors"
> contract is being amended to allow a closed list of residual checks with
> defined outcomes, such as id lookup returning an optional and a program stop on
> non-recoverable out-of-memory (memory plan section 6, gates M2 and M16).
> Static argument exclusivity remains.

## Sources

- [Mojo Manual: Ownership](https://docs.modular.com/mojo/manual/values/ownership/)
- [Mojo Manual: Lifetimes](https://docs.modular.com/mojo/manual/values/lifetimes/)
- [Mojo programming language (Wikipedia)](https://en.wikipedia.org/wiki/Mojo_(programming_language))
- [Modular blog](https://www.modular.com/blog)
