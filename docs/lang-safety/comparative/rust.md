# Comparative: Rust

Status: Phase B research from before 2026-09-14. Where it conflicts with the
ledger in [`../../plan/decisions.md`](../../plan/decisions.md) or the
[memory plan](../../plan/memory.md), those documents win.

Companion to the Phase A edge-case files in [`../edge-cases/`](../edge-cases/).

## Summary

Rust is the upper bound of expressiveness for compile-time memory safety. Its
borrow checker proves spatial, temporal and concurrency safety in one
discipline. Simpler approaches (Hylo, Vale, Cyclone, A7) are measured by how much
of Rust's expressiveness they give up for how much simplicity they gain.

This file walks the 12 gaps from
[`../07-language-review.md`](../07-language-review.md).

## Per-gap findings

### Gap 01: Cast

Rust spreads conversion across several mechanisms.

`as` handles primitive conversion: widening, narrowing with possible truncation,
integer to float, pointer to integer, and integer to raw pointer:

```rust
let x: i64 = y as i64;
let p: usize = ptr as usize;       // pointer to int — allowed
let q: *mut T = addr as *mut T;    // int to pointer — allowed (raw pointer!)
```

The `TryFrom` and `From` traits give explicit fallible and infallible
conversions:

```rust
let x: u8 = u8::try_from(y_i32)?;   // fails if out of range
let x: i64 = i64::from(y_i32);       // infallible widening
```

`mem::transmute` reinterprets same-size values and is `unsafe`.

Safe Rust allows pointer-to-integer casts through `as` for raw pointers
(`*const T`, `*mut T`), but dereferencing a raw pointer is `unsafe`. References
(`&T`, `&mut T`) cannot be cast from integers.

- Adopt: the `TryFrom` shape for fallible conversion. A7's
  `truncating_cast<T>(x) -> ?T` is `TryFrom::try_from`. One trait for infallible
  conversion and another for fallible conversion is a clean split.
- Avoid: the permissive `as` operator. It truncates silently
  (`300_u32 as u8` is `44`) and allows pointer-integer casts in safe code. A7
  forbids both.

Note (2026-09-16): the cast vocabulary is open under plan gate G3.

### Gap 02: Nullable pointers

Safe Rust has no null pointer:

- `&T` and `&mut T` are always non-null.
- `Option<&T>` and `Option<&mut T>` mean "maybe a reference". The niche
  optimisation stores them in one word, with zero meaning `None`.
- Raw pointers `*const T` and `*mut T` are the C-compatible nullable form;
  dereferencing them needs `unsafe`.

```rust
fn first(xs: &[i32]) -> Option<&i32> {
    xs.first()  // returns Option<&i32>
}
```

Nullability lives in the type, so dereferencing `&T` needs no runtime null
check.

- Adopt: the niche optimisation. A7's `?ref T` should lower to Zig's `?*T`,
  which already has it.
- Avoid: `Option<T>` as a full library enum with a large method surface. A7's
  `?T` sugar (gap 02, question Q02a) gives the same surface with less
  type-system machinery.

Note (2026-09-16): the memory plan removes stored references and `nil`
(gates M4, M6). Optionals wrap values, not references, so `?ref T` is no longer
planned. The niche lowering still applies to optionals the compiler places
behind a pointer.

### Gap 03: Definite assignment

Rust rejects reads before initialisation through flow analysis:

```rust
let x: i32;
if cond {
    x = 1;
}
println!("{}", x);  // error[E0381]: `x` is possibly uninitialised
```

The check shares a control-flow graph with move analysis and borrow analysis.

- Adopt: integration with move analysis. Both ask whether a binding is readable
  at a point, so they should share infrastructure.
- Avoid: nothing technical. Rust's error codes and messages are a style choice.

### Gap 04: NonZero division

Rust has wrapper types such as `core::num::NonZeroI32` and `NonZeroU64`:

```rust
let d: NonZeroI32 = NonZeroI32::new(5).unwrap();
let q = a / d.get();  // safe by construction
```

The `/` operator does not require `NonZero`. For `i32` values `a` and `b`,
`a / b` compiles and panics at run time when `b == 0`. `NonZeroI32` is a library
convention, not a language rule.

A common use stores `NonZero` in struct fields where the type records "never
zero", for example hash table capacities.

- Adopt: a `NonZero` family, or A7's single generic `NonZero<T>`. Rust shows the
  wrapper works.
- Avoid: making it optional. A7 requires a `NonZero<T>` divisor at the operator.

Note (2026-09-16): integer division rules are open under gate G3. L16 implies
float division needs no divisor proof; removing that proof is still to decide
under gate G1.

### Gap 05: Stack budget

Rust has no stack-budget analysis. Stack overflow is a runtime crash. Tools such
as [`cargo-call-stack`](https://github.com/japaric/cargo-call-stack) analyse the
compiled binary afterwards; the language does not prevent overflow.
`#![recursion_limit = N]` limits macro expansion, not stack use.

- Adopt: nothing. A7's recursion ban plus a computed maximum stack is stronger
  than Rust on this axis.
- Avoid: treating stack overflow as an acceptable runtime crash.

### Gap 06: Typed arithmetic with range tracking

Rust has no ranged integer subtypes. Integer overflow panics in the default debug
profile and wraps in the default release profile. (The behaviour follows the
`overflow-checks` setting, which is on in debug builds and off in release
builds.)

Methods give explicit control:

```rust
let c = a.checked_add(b)?;       // returns Option
let c = a.wrapping_add(b);        // always wraps
let c = a.saturating_add(b);      // saturates at MIN/MAX
let (c, overflow) = a.overflowing_add(b);
```

A program that wants total arithmetic uses `checked_*` everywhere and threads
`Option<T>` through. It is verbose but correct.

- Adopt: the method vocabulary `checked_add`, `wrapping_add` and
  `saturating_add`, with the same names and return types.
- Avoid: Rust's default of wrapping in release. A7's contract requires a range
  proof or an explicit method.

Note (2026-09-16): superseded by L5. Ordinary `+`, `-`, `*` wrap in every build
mode, as in Odin. A7 now matches Rust's release behaviour without Rust's debug
panic. `checked_*` and `saturating_*` remain possible library additions.
Division, shifts and casts still need rules under gate G3.

### Gap 07: Bounded indexing

Rust slice indexing `s[i]` panics when out of bounds. Alternatives:

- `s.get(i) -> Option<&T>`: explicit fallible access.
- `s[i..j]`: slicing, which also panics when out of bounds.
- Iterator methods (`s.iter()`, `s.windows(n)`): always in bounds.

The borrow checker does not check bounds; a runtime panic is the discipline.

- Adopt: `s.get(i) -> Option<&T>`, which is A7's `try_get(i) -> ?T`.
- Avoid: panicking on out-of-bounds by default. A7 requires a static proof or
  `try_get`.

```a7
// Proposed syntax; not supported
score_at :: fn(scores: []i32, i: usize) i32 {
    if value := scores.try_get(i) {   // ?i32
        ret value
    }
    ret 0
}
```

### Gap 08: Option and Result

Rust's `Option<T>` and `Result<T, E>` are the reference designs:

- The `?` operator propagates errors early:
  ```rust
  let v = expr?;  // returns err(e) on the spot if expr is Err(e)
  ```
- Combinators: `map`, `and_then`, `or_else`, `unwrap_or`, `unwrap_or_else`,
  `unwrap_or_default`.
- `?` works in any function returning `Result<_, E>` when the inner error type
  converts to `E` through `From`.
- `if let`:
  ```rust
  if let Some(v) = expr {
      use(v);
  }
  ```
- Patterns in function arguments:
  ```rust
  fn f(Point { x, y }: Point) -> i32 { x + y }
  ```

- Adopt: the `?` operator, the combinators and `if let`. None depends on the
  borrow checker; they work in any language with sum types.
- Avoid: `unwrap()` and `expect()`, which panic at run time. A7 forbids them
  (gap 08, rules OR-11 and OR-12).

Note (2026-09-16): error and match shapes are open under plan gate G5.

### Gap 09: Refinement-lite

Rust has no refinement types. The `NonZero` family is the closest. Crates such
as [`refinement`](https://crates.io/crates/refinement) offer opt-in wrappers,
but none is standard.

Research tools, all external to the language:

- [Flux](https://github.com/flux-rs/flux): refinement types as a Rust extension.
- [Prusti](https://www.pm.inf.ethz.ch/research/prusti.html): preconditions and
  postconditions checked through Viper.
- [Creusot](https://github.com/creusot-rs/creusot): verification through Why3.

- Adopt: the lesson that refinements need language support to be ergonomic.
  Library-only wrappers such as `NonZeroI32` hit ergonomic limits. A7 supports
  refinement-lite in the language from the start.
- Avoid: heavyweight verifiers. A7 uses pattern recognition and a closed set of
  refinements.

### Gap 10: Affine ownership

Rust is the reference design:

- Types are affine by default. A non-`Copy` value moves on assignment, function
  call or pattern binding; later use is a compile error.
- The `Copy` trait opts out: `Copy` types are copied instead of moved.
- Borrowing uses `&T` (shared) and `&mut T` (exclusive). At any point there are
  either many `&T` or one `&mut T`.
- Lifetimes carry `'a` annotations. NLL and Polonius infer most of them, but
  signatures with several references need them.
- The `Drop` trait runs a destructor at scope exit.

```rust
fn process(s: String) {        // s is moved in
    let t = s;                   // s is moved into t; can't use s after
    use_string(&t);              // borrow t for the call
    // t dropped here
}
```

- Adopt: affine by default, the split between `Copy` and non-`Copy` types, and
  move on assignment. Ownership is a property of bindings, not of types alone.
- Avoid: lifetime annotations and the borrow checker. As argued in
  [`../06-compile-time-safety.md`](../06-compile-time-safety.md) section 8, Hylo
  shows they are unnecessary when references are not storable. A7 follows Hylo.

Still worth studying:

- `Send` and `Sync`. When concurrency arrives, they encode what can move between
  threads and what can be shared between them.
- `Drop`. A7's `del` is explicit, and automatic drop is a convenience. The
  decision was to keep explicit `del` for now.

Note (2026-09-16): the `Drop` decision is reversed. The memory plan removes
`del` from ordinary code (gate M3). The compiler releases storage at static
points on control-flow edges, much like Rust's scope-exit drop but without a
user-written trait or drop flags (contract item 3). Assignment copies rather than
moves; the compiler removes a copy only when it is unobservable (contract
item 4). Resources are the move-only exception (gate M7). The lifetime-free
direction stands: `ref` cannot be stored or returned (contract item 8.3), but no
parameter-mode syntax is approved (L6).

### Gap 11: Finite floats

Rust has no `Fin<f64>`. `f64` includes NaN and infinity, and arithmetic follows
IEEE 754. `f64::is_nan`, `f64::is_infinite` and `f64::is_finite` query values.

Since Rust 1.45, `f as i32` on NaN gives 0, and an out-of-range finite value
saturates. This is defined behaviour: no panic and no signal.

- Adopt: defined float-to-integer conversion (saturate, NaN to 0) is one
  defensible model. A7's earlier approach is stricter: return `?int` and make
  the user handle it.
- Avoid: silent NaN and infinity propagation. A7 requires `Fin<f64>` for total
  arithmetic.

Note (2026-09-16): superseded by L16. A7 floats follow IEEE 754 as in Zig and C,
matching Rust's value model; `Fin<F>` is withdrawn. `int` no longer exists (L4).
Float-to-integer conversion failure is open under gate G1.

### Gap 12: FFI

Rust declares foreign functions with `extern`:

```rust
extern "C" {
    fn malloc(size: usize) -> *mut c_void;
}

unsafe {
    let p = malloc(64);
}
```

Calling a foreign function needs `unsafe`. `bindgen` generates `extern`
declarations from C headers, and `cbindgen` generates C headers from Rust.

- Adopt: the `extern "C"` annotation form and generated bindings.
- Avoid: the `unsafe` keyword. A7 has no equivalent; the foreign boundary is the
  one documented escape, and foreign returns must be `Result<T, E>`.

## What A7 should adopt

1. `TryFrom` and `From` shapes for conversion (gap 01; open under G3).
2. Niche-optimised optional lowering (gap 02).
3. Definite assignment and move analysis on one control-flow graph (gaps 03, 10).
4. The `NonZero` wrapper pattern (gap 04).
5. `checked_`, `wrapping_`, `saturating_` and `overflowing_` method names
   (gap 06; ordinary operators now wrap under L5).
6. `s.get(i) -> Option<&T>` as `try_get` (gap 07).
7. The `?` propagation operator (gap 08).
8. `if let` syntax (gap 08).
9. Combinator methods on `Option` and `Result` (gap 08).
10. Affine by default with a `Copy` opt-out (gap 10; now internal, see the gap 10
    note).
11. `Send` and `Sync` for concurrency (future).
12. The `extern "C"` declaration form (gap 12).

## What to avoid

1. `unsafe` blocks. A7 has no escape hatch.
2. `as` for pointer-integer and lossy conversions.
3. Lifetime annotations (`'a`). A7 was to use Hylo-style parameter modes instead.
4. The full trait system. A7 may add a lighter version later; coherence, blanket
   impls and specialisation are a large design space.
5. `unwrap()` and `expect()`, which panic at run time.
6. Wrapping arithmetic only in release builds.
7. Panicking on out-of-bounds indexing by default. A7 requires a proof or
   `try_get`.
8. Crate-level macros. Out of scope.

Note (2026-09-16): on item 3, parameter-mode syntax is not approved (L6); the
memory plan keeps lifetimes out by forbidding stored and returned `ref`. On
item 6, A7 now wraps `+`, `-`, `*` in every build (L5); the objection was to
build-dependent behaviour, which A7 avoids.

## Where Rust accepts more programs

Rust's borrow checker accepts more programs than a Hylo-style discipline without
storable references:

- Storing `&mut T` in a struct field.
- Returning `&T` from a function.
- Iterator adapters that yield references.
- `Rc<T>` and `Arc<T>` shared ownership. This is not strictly a borrow-checker
  feature, but the borrow checker enables it.

A7 will reject some Rust programs as unportable. Based on Hylo's experience, the
set is small for typical application code. Iterators over borrowed state may
need rewrites.

Note (2026-09-16): the memory plan's replacement for stored references and
`Rc`/`Arc` sharing is `usize` positions in lists and generation-checked `Id(T)`
values in `Table(T)` (gates M1, M5).

## Sources

- [The Rust Reference](https://doc.rust-lang.org/reference/)
- [The Rustonomicon](https://doc.rust-lang.org/nomicon/)
- [Rust RFC 2094: Non-Lexical Lifetimes](https://rust-lang.github.io/rfcs/2094-nll.html)
- [Polonius (next-generation borrow checker)](https://rust-lang.github.io/polonius/)
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/)
- [Rustc Dev Guide](https://rustc-dev-guide.rust-lang.org/)
- [cargo-call-stack](https://github.com/japaric/cargo-call-stack)
- [refinement crate](https://crates.io/crates/refinement)
- [Flux (refinement types for Rust)](https://github.com/flux-rs/flux)
- [Prusti](https://www.pm.inf.ethz.ch/research/prusti.html)
- [Creusot](https://github.com/creusot-rs/creusot)
