# Comparative: Rust

> Phase B artifact in the `docs/lang-safety/` research process.
> Companion to the Phase A edge-case files in `../edge-cases/`.

Rust is the **upper bound of expressiveness for compile-time
memory safety**. Its borrow checker proves spatial safety, temporal
safety, and concurrency safety in a single discipline. Every
"simpler" approach (Hylo, Vale, Cyclone, A7) is measured against
how much of Rust's expressiveness it loses for how much language
simplicity it gains.

This file walks each of the 12 gaps from
[`../07-language-review.md`](../07-language-review.md), recording
how current Rust handles each, what works, and what A7 should
specifically take or not take.

Primary sources:

- [The Rust Reference](https://doc.rust-lang.org/reference/)
- [The Rustonomicon](https://doc.rust-lang.org/nomicon/)
- [Rust RFC 2094 — Non-Lexical Lifetimes](https://rust-lang.github.io/rfcs/2094-nll.html)
- [Polonius (next-gen borrow checker)](https://rust-lang.github.io/polonius/)
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/)
- [Rustc Dev Guide](https://rustc-dev-guide.rust-lang.org/)

---

## How Rust handles each gap

### Gap 01 — Cast

Rust splits casts across several mechanisms:

- **`as`** — primitive conversion, including widening, narrowing
  (with possible truncation), int↔float, ptr↔int, and unsafe
  reinterpretation:
  ```rust
  let x: i64 = y as i64;
  let p: usize = ptr as usize;       // pointer to int — allowed
  let q: *mut T = addr as *mut T;    // int to pointer — allowed (raw pointer!)
  ```
- **`TryFrom` / `From` traits** — explicit fallible / infallible
  conversions:
  ```rust
  let x: u8 = u8::try_from(y_i32)?;   // fails if out of range
  let x: i64 = i64::from(y_i32);       // infallible widening
  ```
- **`mem::transmute`** — same-size reinterpret; `unsafe`.

Pointer↔int is allowed in safe Rust through `as` for **raw**
pointers (`*const T`, `*mut T`); but *dereferencing* a raw pointer
is `unsafe`. References (`&T`, `&mut T`) cannot be cast from
integers.

**What A7 can steal:** the **`TryFrom` shape** for fallible
conversions. A7's `truncating_cast<T>(x) -> ?T` is essentially
`TryFrom::try_from`. The discipline of "infallible via trait,
fallible via different trait" is clean.

**What A7 should not steal:** Rust's permissive `as` operator.
`as` permits silent truncation (e.g., `300_u32 as u8 = 44`) and
ptr↔int conversions in safe code. A7 forbids both.

---

### Gap 02 — Nullable pointers

Rust **has no null pointer in safe code.** The combination:

- `&T` and `&mut T` are *always non-null* references.
- `Option<&T>` and `Option<&mut T>` represent "maybe a reference."
  Niche-optimised to a single null word.
- Raw pointers `*const T` and `*mut T` are the C-compatible
  nullable form; using them requires `unsafe`.

```rust
fn first(xs: &[i32]) -> Option<&i32> {
    xs.first()  // returns Option<&i32>
}
```

The Rust compiler tracks nullability *at the type level*; there
is no runtime null check on a `&T` deref because it cannot be
null.

**What A7 can steal:** the **niche optimisation** — `Option<&T>`
in Rust occupies one word (zero is the niche representing
`None`). A7's `?ref T` should lower to Zig's `?*T`, which already
does this.

**What A7 should not steal:** the trait-based `Option<T>` is
heavyweight. A7's `?T` sugar (Gap 02 Q02a) gives the same surface
with less type-system machinery.

---

### Gap 03 — Definite assignment

Rust enforces "no read before initialisation" via a flow analysis:

```rust
let x: i32;
if cond {
    x = 1;
}
println!("{}", x);  // error[E0381]: `x` is possibly uninitialised
```

The check is integrated with the borrow checker; the same CFG
analyses move analysis, borrow analysis, and initialisation.

**What A7 can steal:** the **integration with move analysis**.
Both are "is this binding readable here?" questions; sharing
infrastructure is the right architecture.

**What A7 should not steal:** Rust's specific error codes/messages
(stylistic, not technical).

---

### Gap 04 — `NonZero` division

Rust has `core::num::NonZeroI32`, `NonZeroU64`, etc., as wrapper
types:

```rust
let d: NonZeroI32 = NonZeroI32::new(5).unwrap();
let q = a / d.get();  // safe by construction
```

But Rust's `/` operator does **not require `NonZero`** — `a /
b` for `i32` `a, b` compiles and panics at runtime if `b == 0`.
The `NonZeroI32` wrapper is a *library convention*, not a
language rule.

A common pattern: store `NonZero` in struct fields where the
type system can record "this is never zero" (e.g., for hash
table capacities).

**What A7 can steal:** the **per-width-NonZero family** (or, A7's
single generic `NonZero<T>`). Rust shows that the wrapper works.

**What A7 should not steal:** Rust's *optional* discipline. A7
requires `NonZero<T>` divisor at the operator level.

---

### Gap 05 — Stack budget

Rust has **no stack-budget analysis** in the compiler. Stack
overflow is a runtime crash. Tools like
[`cargo-call-stack`](https://github.com/japaric/cargo-call-stack)
do post-hoc analysis on the compiled binary; the language and
compiler do not prevent overflow.

Rust's `#![recursion_limit = N]` is a *macro-expansion* limit,
not a stack-budget limit.

**What A7 can steal:** nothing here. A7's "ban recursion +
compute max stack" model is *better than Rust's* on this axis,
thanks to the recursion ban.

**What A7 should not steal:** the laissez-faire "stack
overflow is a runtime crash" approach.

---

### Gap 06 — Typed arithmetic with range tracking

Rust **does not have ranged integer subtypes**. Integer
overflow is:

- **Panic in debug** builds (`-O 0`).
- **Wrap in release** builds (`-O 3`).

Methods like `i32::checked_add`, `i32::wrapping_add`,
`i32::saturating_add`, `i32::overflowing_add` provide explicit
control:

```rust
let c = a.checked_add(b)?;       // returns Option
let c = a.wrapping_add(b);        // always wraps
let c = a.saturating_add(b);      // saturates at MIN/MAX
let (c, overflow) = a.overflowing_add(b);
```

A program that wants total arithmetic uses `checked_*` everywhere
and threads `Option<T>` through. Verbose but correct.

**What A7 can steal:** the **method vocabulary**
(`checked_add`/`wrapping_add`/`saturating_add`) is excellent.
Same names; same return types.

**What A7 should not steal:** the **default behaviour**. Rust
defaults to "wrap in release" — A7's contract requires either a
range proof or an explicit method.

---

### Gap 07 — Bounded indexing

Rust slice indexing `s[i]` **panics on OOB** at runtime. There
are alternatives:

- `s.get(i) -> Option<&T>` — explicit fallible access.
- `s[i..j]` — slicing; also panics on OOB.
- Iterator methods (`s.iter()`, `s.windows(n)`) — always safe.

The borrow checker doesn't statically check bounds; runtime
panic is the discipline.

**What A7 can steal:** the **`s.get(i) -> Option<&T>`** shape
is exactly A7's `try_get(i) -> ?T`. Same idiom.

**What A7 should not steal:** the default-panic-on-OOB. A7
requires either a static proof or `try_get`.

---

### Gap 08 — `Option<T>` / `Result<T, E>`

Rust's `Option<T>` and `Result<T, E>` are the **canonical
reference** for these types. Features worth noting:

- **`?` operator** for short-circuit error propagation:
  ```rust
  let v = expr?;  // returns err(e) on the spot if expr is Err(e)
  ```
- **Combinators**: `map`, `and_then`, `or_else`, `unwrap_or`,
  `unwrap_or_else`, `unwrap_or_default`.
- **`?` works in any function returning `Result<_, E>` where the
  inner error type converts (`From`)** to this function's error
  type.
- **`if let`**:
  ```rust
  if let Some(v) = expr {
      use(v);
  }
  ```
- **Pattern-matching in function args**:
  ```rust
  fn f(Point { x, y }: Point) -> i32 { x + y }
  ```

**What A7 can steal:** the **`?` operator**, the combinator
vocabulary, and `if let` are all worth importing. They're not
specific to Rust's borrow checker; they work in any sum-type
language.

**What A7 should not steal:** Rust's `unwrap()` and `expect()`
methods are runtime-panicky. A7 forbids them (per Gap 08 OR-11,
OR-12).

---

### Gap 09 — Refinement-lite

Rust **has no refinement types** in the language. The `NonZero`
family is the closest. Crates like
[`refinement`](https://crates.io/crates/refinement) provide
opt-in user-space wrappers but they're not standard.

Active research:
- [Flux](https://github.com/flux-rs/flux) — refinement types as
  a Rust extension.
- [Prusti](https://www.pm.inf.ethz.ch/research/prusti.html) —
  pre/post conditions checked via Viper.
- [Creusot](https://github.com/creusot-rs/creusot) — Why3-based
  verification.

All three are *external tools*; none is in the language itself.

**What A7 can steal:** the **insight that refinements need
language support to be ergonomic**. Library-only wrappers (like
`NonZeroI32`) hit ergonomic walls. A7's refinement-lite is
language-supported from the start.

**What A7 should not steal:** the heavyweight verifier
approach. A7 sticks to pattern-recognition + closed-set
refinements.

---

### Gap 10 — Affine ownership

Rust is the **canonical reference**. Features:

- **Affine types by default**: a non-`Copy` value is moved by
  assignment / function call / pattern-bind; subsequent use is
  a compile error.
- **`Copy` trait** opts out: types implementing `Copy` are
  copied instead of moved.
- **Borrowing**: `&T` (shared) and `&mut T` (exclusive). At any
  given lifetime point, either many `&T`s or one `&mut T`.
- **Lifetimes**: borrow durations carry `'a` annotations;
  mostly inferred by NLL / Polonius, but required at function
  signatures with multiple references.
- **`Drop` trait**: a destructor runs at scope exit.

```rust
fn process(s: String) {        // s is moved in
    let t = s;                   // s is moved into t; can't use s after
    use_string(&t);              // borrow t for the call
    // t dropped here
}
```

**What A7 can steal:** the **affine-by-default** discipline; the
distinction between `Copy` and non-`Copy` types; the move-on-
assignment rule. The fundamental insight: ownership is a
property of *bindings*, not of *types* alone.

**What A7 should not steal:** the **lifetime annotations** and
the borrow checker. As argued in `06-compile-time-safety.md`
§8, Hylo demonstrates these are not necessary if references
are not storable values. A7 follows Hylo's path.

**What A7 should still take inspiration from:**

- The `Send`/`Sync` traits — when concurrency is added, these
  encode "what can move between threads" and "what can be shared
  between threads." Worth studying.
- The `Drop` trait — A7's `del` operator is explicit; auto-drop
  via `Drop` is opt-in convenience. Decision: probably keep
  explicit `del` for now.

---

### Gap 11 — Finite floats

Rust **does not have a `Fin<f64>` analog.** `f64` includes NaN
and inf as valid values; arithmetic propagates per IEEE 754.

The `f64::is_nan`, `f64::is_infinite`, `f64::is_finite` methods
let users query. The conversion `f as i32` (via `as`) on a NaN
yields 0 (defined in safe Rust since 1.45); on an out-of-range
finite value, it saturates. This is the *defined* behaviour —
no panic, but also no signal.

**What A7 can steal:** the **defined-behaviour** approach to
float→int conversion (saturate; convert NaN to 0) is *one*
defensible model. A7's approach is stricter: return `?int` and
force the user to handle it.

**What A7 should not steal:** the silent propagation of NaN/inf.
A7 requires `Fin<f64>` for code that wants total arithmetic.

---

### Gap 12 — FFI

Rust has rich FFI via `extern`:

```rust
extern "C" {
    fn malloc(size: usize) -> *mut c_void;
}

unsafe {
    let p = malloc(64);
}
```

Calling foreign functions requires `unsafe`. The `cbindgen` /
`bindgen` tools generate `extern` declarations from C headers.

**What A7 can steal:** the **`extern "C"`** annotation form
and the auto-generated-bindings tooling pattern.

**What A7 should not steal:** the **`unsafe` keyword** — A7 has
no equivalent and the FFI boundary alone is the documented
escape. Foreign returns must be `Result<T, E>`-typed.

---

## Primary sources

Already linked inline. Quick index:

- [The Rust Reference](https://doc.rust-lang.org/reference/)
- [The Rustonomicon](https://doc.rust-lang.org/nomicon/)
- [Rust RFC 2094 — NLL](https://rust-lang.github.io/rfcs/2094-nll.html)
- [Polonius](https://rust-lang.github.io/polonius/)
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/)
- [Rustc Dev Guide](https://rustc-dev-guide.rust-lang.org/)
- [Flux (refinement types for Rust)](https://github.com/flux-rs/flux)
- [Prusti](https://www.pm.inf.ethz.ch/research/prusti.html)
- [Creusot](https://github.com/creusot-rs/creusot)

---

## What A7 can steal — consolidated

1. **`TryFrom` / `From` trait shapes** for casts (Gap 01).
2. **Niche-optimised `Option<&T>`** lowering (Gap 02).
3. **CFG-integrated definite-assignment + move analysis** (Gap 03, 10).
4. **`NonZero*` wrapper family pattern** (Gap 04).
5. **`checked_/wrapping_/saturating_/overflowing_` method vocabulary** (Gap 06).
6. **`s.get(i) -> Option<&T>` shape** (Gap 07).
7. **`?` propagation operator** (Gap 08).
8. **`if let` syntax** (Gap 08).
9. **Combinator methods on `Option` / `Result`** (Gap 08).
10. **Affine-by-default + `Copy` opt-out** (Gap 10).
11. **`Send` / `Sync` for concurrency** (future).
12. **`extern "C"` declaration form** (Gap 12).

## What A7 should not take from Rust

1. **`unsafe` block** — A7 has no escape hatch.
2. **`as` for ptr↔int and lossy conversions** — A7 forbids.
3. **Lifetime annotations (`'a`)** — A7 uses Hylo-style parameter
   modes instead.
4. **Trait system in full** — A7 may have a lightweight version
   later; the full Rust trait system (coherence, blanket impls,
   specialisation) is much more language design.
5. **`unwrap()` / `expect()`** — runtime panic, forbidden.
6. **Default-wrap-in-release arithmetic** — A7 requires explicit
   discipline.
7. **Default-panic-on-OOB indexing** — A7 requires proof or
   `try_get`.
8. **Crate-level macros** — out of scope.

## Where Rust is the strict upper bound

Rust's borrow checker accepts strictly more programs than
Hylo/A7's parameter-mode discipline:

- Storing `&mut T` in a struct field.
- Returning `&T` from a function.
- Iterator adapters that yield references.
- `Rc<T>` / `Arc<T>` shared ownership (not really
  borrow-checker-related, but enabled by it).

A7 will reject some Rust programs as un-portable. The expected
size of this set, based on Hylo's experience, is small for
typical application code. Heavy uses of iterators with
borrowed-state may need rewrites.
