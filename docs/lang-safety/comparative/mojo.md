# Comparative: Mojo

> Phase B artifact in the `docs/lang-safety/` research process.

Mojo is the **most recent attempt to ship Rust-class ownership in
a Python-flavored systems language**. Started in 2023 by
Chris Lattner's Modular team, Mojo combines:

- **Python-compatible syntax** (familiar surface).
- **MLIR-based backend** (the same compiler infrastructure as
  modern LLVM/Swift).
- **Ownership and borrow checking** (Rust-derived, Swift-influenced).
- **Value semantics with `inout` and `borrowed` parameters**
  (similar to Hylo/Swift).

Mojo is **active development** — features are still in flux —
but the **ownership design decisions are stable enough to study**.

Primary sources:

- [Mojo Manual — Ownership](https://docs.modular.com/mojo/manual/values/ownership/)
- [Mojo Manual — Lifetimes](https://docs.modular.com/mojo/manual/values/lifetimes/)
- [Mojo programming language (Wikipedia)](https://en.wikipedia.org/wiki/Mojo_(programming_language))
- [Modular blog](https://www.modular.com/blog)

---

## Argument conventions

Mojo's parameter modes:

| Convention | Semantics |
| --- | --- |
| `borrowed` (default for non-`inout` params) | Immutable borrow |
| `inout` | Exclusive mutable borrow |
| `owned` | Consume / take ownership |

The defaults are interesting:

- **Non-`inout` parameters are `borrowed` by default** for
  function arguments — closer to "shared reference" than to
  Rust's "moved value" default.
- **Mojo does *not* require sigils on the caller side**
  (`f(&x)` style). The caller writes `f(x)` regardless of
  parameter mode.

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

---

## Exclusivity

Mojo enforces argument exclusivity for mutable references: a
function receiving `inout` cannot receive any other reference
(borrowed or inout) to the same value.

Like Swift, this is checked statically where possible. Runtime
fallback is rare.

---

## How Mojo handles each gap

### Gap 01 — Cast

Mojo's casts follow Python-like patterns but with stronger
typing. Explicit conversion methods like `Int(x)`, `Float64(x)`.

### Gap 02 — Nullable pointers

Mojo has `Optional[T]` and references that are non-null by default
(within the safe subset).

### Gap 03 — Definite assignment

Enforced.

### Gap 04 — NonZero division

No NonZero family in stdlib (yet); division by zero is a
runtime trap.

### Gap 05 — Stack budget

Not addressed.

### Gap 06 — Typed arithmetic

Mojo allows overflow in release; no first-class range tracking.

### Gap 07 — Bounded indexing

Standard runtime check; OOB raises.

### Gap 08 — Option/Result

Mojo has `Optional[T]`; the `Result`-equivalent shape is in flux.

### Gap 09 — Refinement-lite

Not present.

### Gap 10 — Affine ownership — **the active feature**

Mojo's three parameter conventions plus argument-exclusivity are
the core of its safety story. **The model is essentially
Swift's**, with two differences:

1. **No sigils on the caller side** — `f(x)` regardless of
   `borrowed`/`inout`/`owned` of `f`'s parameter. Cleaner
   syntax, less Rust-like.
2. **`inout` exclusivity is statically enforced** more
   aggressively than Swift.

The `Lifetime[bool]` / `Lifetime[mutable]` system in modern Mojo
provides reference parameters that don't require named lifetime
parameters at function signatures — the lifetime is the
parameter, inferred. This is similar to Hylo's approach.

**What A7 can steal:**

1. **No sigils on caller side** — `f(x)` regardless of `f`'s
   parameter mode. This is a real ergonomic improvement over
   Rust's `&x` / `&mut x` / `x` distinction at the call site.
2. **`owned` as the keyword for consume** — clear English.
3. **Mojo's pragmatic mix of Rust-class safety with simpler
   syntax** — validation that A7's target is reachable.

**What A7 should not steal:**

1. **Python-derived syntax conventions** (the rest of Mojo's
   surface).
2. **Default-borrowed parameters** — debatable; A7 may prefer
   default-by-value (with implicit borrow for non-`Copy` types).

### Gap 11 — Finite floats

Standard IEEE 754; no `Fin<F>` analog.

### Gap 12 — FFI

Mojo has C interop via MLIR's C dialect; specifics still in flux.

---

## Primary sources

- [Mojo Manual — Ownership](https://docs.modular.com/mojo/manual/values/ownership/)
- [Mojo Manual — Lifetimes](https://docs.modular.com/mojo/manual/values/lifetimes/)
- [Modular blog](https://www.modular.com/blog)

---

## What A7 can steal — consolidated

1. **No sigils on caller side** for parameter modes — purely
   ergonomic improvement.
2. **`owned` as the consume keyword** — matches English better
   than `consume` or `sink`.
3. **Mojo's pragmatic existence** as evidence that
   borrow-checker-class safety is *productizable* without
   alienating mainstream programmers.

## What A7 should not steal

1. Python-compatible syntax (A7 has its own).
2. MLIR backend (A7 uses Zig).
3. The full Mojo runtime / metaprogramming surface.

## The lesson for A7

Mojo is **doing exactly what A7 plans to do**, at a much larger
scale and with much more compiler engineering. The features
Mojo has shipped are the features A7 should plan to ship:

- Three parameter modes (`borrowed` / `inout` / `owned`).
- Static argument exclusivity.
- Lifetime inference at function signatures (no named
  lifetimes).

A7 differs in two ways: (1) A7 emits Zig, not LLVM/MLIR
directly; (2) A7 commits to *zero runtime errors* rather than
"safe by default, trap if violated." But the type-system
mechanism is the same.

If A7's design ever drifts away from these basics, Mojo's
existence is the counterargument: "this is what mainstream
adoption of compile-time ownership looks like; we should match
it, not invent a new wheel."
