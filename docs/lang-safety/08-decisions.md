# A7 Zero-Runtime-Error Decisions Document

> Phase C artifact in the `docs/lang-safety/` research process. Each decision
> answers an open question from `edge-cases/*.md` and cites the relevant
> Phase B comparative file. Decisions were added cluster by cluster, in
> sequential review, before 2026-09-14.

## Current status

The [v1 decision ledger](../plan/decisions.md) (2026-09-14 onward) supersedes
parts of this register. This file stays as a historical record. Where the two
disagree, the ledger wins. Old line numbers cited by other documents refer to
commit `701c679`.

| Group | Decisions | Ledger entries |
| --- | --- | --- |
| Superseded | D.001 (`int`, `uint`, `number`; "No NaN, no inf") | L3, L4, L16 |
| Superseded | D.002 (bit-width types FFI-only) | L4 |
| Superseded | D.003 (bignum promotion, no overflow) | L4, L5 |
| Superseded | D.004 (`uint - uint` widens to `int`) | L4 |
| Restate for explicit widths | D.005, D.022, D.025, D.026, D.027, D.029, D.033, D.034, D.035, D.036, D.037, D.039 | L4; gate G3 |
| Restate with `usize` and explicit widths | D.007, D.010, D.020 | L4 |
| Contradictory; neither stands | D.024 (keep `cast`) and D.038 (remove `cast`) | Gate G3 |
| Proposed, not accepted | D.040, D.041, D.049 (and D.041b, which refines D.041) | L6 scope limit; memory plan |
| Unaffected by the ledger | D.006, D.008, D.009, D.011–D.019, D.021, D.023, D.028, D.030–D.032, D.042–D.048, D.050–D.053 | none |

Audit notes. These are a reading of the ledger, not ledger entries:

- Floats follow IEEE 754 (L16). NaN and infinity are ordinary values. Any text
  here that says otherwise is superseded.
- L5 makes integer `+`, `-` and `*` wrap. Division, remainder, shifts,
  narrowing casts and size arithmetic remain open under gate G3.
- D.042–D.048 and D.052 use the `borrow` / `inout` / `consume` modes from the
  unaccepted D.041. The ledger (O2) replaces the mode question with the
  [memory plan](../plan/memory.md), which makes ownership internal.
- D.023, D.030–D.032 and D.047 name `int`, `uint` or `number` in their text.
  Read those names as explicit-width types.
- D.034 relies on D.002's FFI-only rule, which L4 removes.
- The cluster CA summary says `nil` is removed. That contradicts the revised
  D.013, which keeps `nil`. See the note in that summary.

## How to read this file

| Status | Meaning |
| --- | --- |
| **PROPOSED** | Drafted; awaiting user approval. |
| **ACCEPTED** | User approved; locked in for Phase D (the spec). |
| **AMENDED** | User requested changes; the revision is recorded here. |

A heading tag such as `[REVISED — ACCEPTED]` means the decision was revised
and then given the second status.

Decisions are numbered `D.NNN` in source order, regardless of cluster.
Cross-references use the same numbers.

Each entry uses the same fields, where present: **Question** (the source),
**Decision**, examples, **Rationale** and **Implications**. Examples marked
"Proposed" were added during the 2026-09-16 cleanup to make a decision
concrete. They show the decision's intended syntax, not current compiler
behavior, and they use explicit-width types.

## Design directives running through every decision

These came out of iterative refinement during the Phase C conversation.

1. **Zero runtime errors.** The compiler emits Zig that is memory-safe under
   `-O ReleaseFast`, with every Zig safety check disabled. The emitted code has
   no `@panic`, `@trap` or unreachable-at-runtime.
2. **Python/JS-feel ergonomics.** The language reads like TypeScript or Swift,
   not Rust. The method-call surface is familiar; type annotations are short.
3. **Best performance.** Native code through the Zig backend. The compiler
   specialises arbitrary-precision numerics to machine-word operations
   whenever it can prove the value fits.
   (Superseded (2026-09-16): L4 removes arbitrary-precision integers; see
   [the ledger](../plan/decisions.md).)
4. **Keep the language simple.** Few keywords, few operators. When in doubt,
   put complexity in the type checker, not in user-facing syntax.
5. **Honour the existing A7 spec.** A7 already has `ref T`, `nil`,
   `match`/`case`, slices, generics, `new`/`del`, banned recursion and no
   `unsafe`. The contract adds little on top; existing keywords stay.

## Cluster index

| Cluster | Topic | Status |
| --- | --- | --- |
| CA | Type-system foundations + numeric vocabulary | **ACCEPTED** |
| CB | Cast and conversions | **ACCEPTED** |
| CC | Ownership and parameter modes | **PROPOSED** (this round) |
| CD | Flow analysis | pending |
| CE | Numerics specifics (NonZero, stack budget) | pending |
| CF | Modules and metaprogramming (Ada inspirations) | pending |
| CG | FFI boundary and concurrency model | pending |

---

# Cluster CA — Type-system foundations + numeric vocabulary

This cluster sets the type-shape primitives:

- the three primary numeric types (`int`, `uint`, `number`);
- `bool` and `string`;
- nullability (`?T` as sugar for `Option<T>`);
- fallibility (`Option` / `Result` with `?` propagation);
- the compiler-internal range tracking that powers the contract.

Sources: `edge-cases/02-nullable-pointers.md`,
`edge-cases/06-typed-arithmetic.md`, `edge-cases/08-option-result.md`,
`edge-cases/09-refinement-lite.md`, and user direction during the
conversation.

---

## Numeric types

### D.001 — Three primary numeric types: `int`, `uint`, `number`     [ACCEPTED]

Superseded (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L3/L4/L16.

**Decision.** The user-facing language has exactly three primary numeric
types:

- **`int`**: mathematical integer; the range is whatever memory allows.
  Default literal type for `42`, `-1`, `0`.
- **`uint`**: non-negative integer with the same arbitrary precision. Default
  for slice lengths, sizes and indices. Literal suffix `u`, or set by context
  (for example, `s.length` is `uint`).
- **`number`**: real number with infinite precision. Default literal type for
  `3.14`, `1.0`. No NaN, no inf: those are not values of `number`.

Bit-width types (`i8`, `i16`, …, `u64`, `f32`, `f64`) stay in the language but
are FFI-only. Using them outside FFI code produces a compiler warning (D.002).

**Rationale.** Three types cover the typical program: integer math, size and
index math, and floating-point math. The bit-width set (`i8` through `u64`,
`f32`, `f64`) is a C-ABI concern, not a user concern. Python has
arbitrary-precision `int` and `float`. JavaScript has `number` (IEEE 754
double) plus `BigInt`. Mojo has explicit widths. A7 takes the Python/JS
direction for ergonomics and borrows bignum promotion from LuaJIT and V8.

**Implications.**
- The stdlib prelude provides `int`, `uint` and `number` as built-in types.
- Most user code never names a bit-width type.
- Numeric literals get inferred types: `42` is `int`, `3.14` is `number`, and
  `s.length` (a stdlib method) returns `uint`.
- The compiler runs range analysis to specialise to native operations (D.020).

---

### D.002 — Bit-width types are FFI-only; warning elsewhere         [ACCEPTED]

Superseded (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4.

**Decision.** `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, `u64`, `f32` and
`f64` are valid A7 types, with these rules:

- They are allowed without warning inside `extern` declarations and their
  immediate caller shims.
- Anywhere else they produce a warning: "use `int`/`uint`/`number` unless
  interfacing with foreign code".
- An attribute can silence the warning for one declaration. Cluster CF decides
  the attribute syntax.

**Rationale.** The C ABI needs exact widths, so FFI needs these types.
Elsewhere they cause bugs: silent overflow, sign-change surprises, and
narrow-then-widen confusion. The warning steers users to the safe defaults
without removing the types.

**Implications.**
- A lint pass finds non-FFI bit-width usage.
- Stdlib internals may use bit-width types where layout matters (byte buffers,
  hash digests). The silencing attribute exempts them.

---

### D.003 — Arithmetic on `int` / `uint` / `number` never overflows; compiler specialises    [ACCEPTED]

Superseded (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4/L5.

**Decision.** Bare `+`, `-` and `*` on `int`, `uint` and `number` are always
defined at the language level. The compiler tracks each value's provable range
and emits:

- native machine-word operations when the range fits a machine integer or
  float;
- transparent bignum promotion (one branch in the emitted Zig) when the prover
  cannot rule out overflow.

The user never writes `checked_add`, `wrapping_add` or `saturating_add` for
these types.

**Rationale.** This follows the Python, Ruby, Lisp and Haskell tradition of
arbitrary precision by default. With the LuaJIT/V8/SBCL technique of tagged
integers plus range-driven specialisation, the typical case costs no more than
fixed-width arithmetic. The data, not the user, triggers the slow path.

**Implications.**
- Removes the user-facing typed-arithmetic and range-tracking surface, which
  was cluster CA's largest design source before this refinement. The range
  tracker still exists internally for bounds checking and specialisation.
- Hot inner loops with bounded counters compile to native-integer speed.
- Code with large numbers pays the bignum cost transparently, like GMP / MPFR
  in C.
- For interactive programs that read numbers from input, the compiler
  conservatively allocates bignum storage on the first arithmetic operation.
  Later operations on the same value specialise to the range it has acquired.

---

### D.004 — `uint - uint` returns `int` unless `a >= b` is proved   [ACCEPTED]

Superseded (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4.

**Decision.** Subtracting two `uint` values has type `int`, because the result
can be negative. When range analysis proves `a >= b`, the result is `uint`.

**Rationale.** This matches mathematics. The alternative, `uint - uint = ?uint`
(possibly `none`), forces error handling for a case that is usually provable.
Widening to `int` is cleanest, and loses no data because `int` is arbitrary
precision.

**Implications.**
- `x: uint = b - a` is a compile error unless the compiler proves `b >= a`.
  The user adds the check or assigns to `int`.
- `len.checked_sub(off)?` (returning `?uint`) is the fallback when the user
  wants `uint` and will handle failure.

---

### D.005 — Cross-numeric-type comparisons require explicit conversion   [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Decision.** Comparing values of different numeric types (`int == number`,
`uint < int`, and so on) is a compile error. The user converts explicitly:

```a7
i: int = 5
n: number = 5.0
if cast(number, i) == n { ... }            // OK
if i == n { ... }                          // compile error
```

**Rationale.** Hidden precision loss causes bugs. `int → number` loses
precision for large integers. `number → int` must round, and the user should
choose how (`.to_int_floor()`, `.to_int_round()`, `.to_int_trunc()`). Explicit
beats implicit.

**Implications.**
- Each type has conversion methods. Cluster CB designs the full menu.
- Comparisons within one type (`int == int`, `number < number`) are direct.

---

## bool and string

### D.006 — `bool` is a distinct type with no truthy/falsy conversions   [ACCEPTED]

**Decision.** A7 has `bool` with values `true` and `false`. There are no
implicit conversions to or from `bool`:

- `if x:` requires `x: bool`.
- `if x != nil:` works, because `x != nil` returns `bool`.
- `if x:` where `x: int` is a compile error.

Proposed example:

```a7
flags: i32 = 3
if flags != 0 { ... }           // OK: the comparison is bool
if flags { ... }                // compile error: i32 is not bool
```

**Rationale.** Truthy/falsy rules in Python and JS cause classic bugs:
`if list:` is false for an empty list, `if 0:` is false, and `if "false":` is
true. C's "non-zero is true" has the same problem. An explicit predicate keeps
intent visible.

**Implications.**
- The backend lowers `bool` to Zig's `bool`.
- Common idioms are explicit: `if list.length > 0:`, `if x != none:`,
  `if !s.is_empty():`. (Audit note: D.013 keeps `nil` and has no `none`; read
  `x != none` as `x != nil`.)

---

### D.007 — `string` is UTF-8 text; `.length` is byte count          [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate with `usize` and explicit widths.

**Decision.** A7's `string` is a UTF-8-encoded byte sequence:

- `s.length` returns `uint`, the number of bytes.
- `s.codepoints()` returns an iterator (or slice) of codepoints.
- `s[i]` returns the byte at offset `i` (`uint`).
- `s[a..b]` requires indices on codepoint boundaries. It is a compile error if
  an index is proven not on a boundary. No runtime check is emitted, because
  the contract forbids it.

**Rationale.** Zig and Rust both store bytes and make codepoint operations
explicit. Python's codepoint-indexed model is convenient but costly: indexing
is O(n) in general and O(1) only through internal representation trade-offs.
A7 picks performance plus explicit codepoint operations.

**Implications.**
- The stdlib `string` has `.length`, `.codepoints()`, `.starts_with()`,
  `.split()`, `.parse_int()` and more.
- `string + string` allocates. It is spelled either as a `+` overload or a
  `.concat()` method; stdlib design decides.
- Slicing without an alignment proof uses `s.try_slice(a, b) -> ?string`.

---

### D.008 — `f"..."` string interpolation                            [ACCEPTED]

**Decision.** A7 supports Python-style f-string interpolation:

```a7
name: string = "world"
msg: string = f"hello {name}, you have {count} items"
```

The compiler parses `f"..."` into literal segments and expressions. When every
interpolated value's `to_string` form is known at compile time, it lowers to a
series of `.concat()` calls. Otherwise it lowers to a runtime concat helper.

**Rationale.** Without f-strings, string building is verbose
(`s.concat(name).concat(", you have ").concat(...)`). F-strings add no keyword,
only an `f` prefix on the literal.

**Implications.**
- Parser change: recognise the `f"..."` prefix.
- Each interpolated expression needs a `.to_string()` method. The stdlib
  provides one for every built-in type.
- The backend emits Zig's `std.fmt.allocPrint` or equivalent.

---

## Compound types

### D.009 — Array literal `[1, 2, 3]` syntax                          [ACCEPTED]

**Decision.** A7 supports an array literal syntax:

```a7
arr: [3]int = [1, 2, 3]
slice: []int = [1, 2, 3]          // implicit array-to-slice
```

The element type is inferred from the contents; the size is the element
count.

**Rationale.** Matches Python, JS, Swift and Rust.

**Implications.**
- Parser change to handle `[...]` literals.
- If the inferred element type does not satisfy the target type, the compiler
  reports an error with a hint.
- Existing A7 syntax `[3]int{1, 2, 3}` (if present) may stay as an alternative
  or be removed; Cluster CF can decide.

---

## Nullability

### D.010 — `?T` is sugar for `Option<T>`                              [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate with `usize` and explicit widths.

**Decision.** The parser desugars `?T` to `Option<T>`. The language has one
sum-type mechanism; `?T` is only a shorter spelling.

**Rationale.** One mechanism is simpler than two. Rust niche-optimises
`Option<&T>` to one word (see [`comparative/rust.md`](./comparative/rust.md)),
which shows the sugar costs nothing at runtime. The Zig backend emits `?*T` for
the niche case (see [`comparative/zig.md`](./comparative/zig.md)).

**Implications.**
- `?int` ≡ `Option<int>`; `?ref Buf` ≡ `Option<ref Buf>`.
- Pattern matching uses `case some(v)` / `case none`. (Audit note: the revised
  D.013 spells the absent arm `case nil`.)
- The backend lowers `?ref T` to Zig's `?*T`, and `?int` and `?number` to
  tagged unions.

---

### D.011 — Implicit upcast `T → ?T` at assignment / call sites     [ACCEPTED]

**Decision.** Assigning a `T` to a `?T` location, or passing a `T` to a `?T`
parameter, wraps implicitly:

```a7
process :: fn(x: ?int) int { ... }
process(5)                              // implicit: 5 wraps to some(5)
y: ?int = 42                            // implicit wrap
```

The explicit `some(5)` constructor stays valid, and is required where the
expression's type is ambiguous.

**Rationale.** Removes ceremony at upcast sites. Matches Swift's `T? = T` and
Rust's `Option<T>::from(T)`, but only at assignment targets and call
arguments, not in arbitrary expressions, to avoid surprises.

**Implications.**
- Type-checker rule: every `?T` position accepts a `T` silently.
- The backend emits the matching `some(...)` constructor in Zig.
- The reverse, `?T → T`, is not implicit. It needs `match` or `?`
  propagation.

---

### D.012 — Generic `$T` over reference types defaults to non-null   [ACCEPTED]

**Decision.** When a generic parameter `$T` is instantiated with a reference
type, the non-null variant is the default. A generic that needs nullability
writes `?$T` explicitly.

**Rationale.** Non-null by default, as everywhere else in the contract. If the
instantiation really is nullable, the user passes `?ref Buf` instead of
`ref Buf`, and the parameter becomes `?$T` automatically.

**Implications.**
- Generic code can dereference a `$T` parameter without a null check.

---

### D.013 — `nil` is kept as the no-value literal   [REVISED — ACCEPTED]

**Revised decision.** `nil` remains the no-value literal. The user directed
that existing A7 syntax be honoured, so the earlier proposal to replace `nil`
with `none` is reverted.

`nil` has type `?Never` and unifies with any `?T`. It is the canonical
spelling of the absent value:

- Pattern matching uses `case nil: { ... }` for the absent case and
  `case some(v): { ... }` for the present case.
- Assignment uses `p: ?int = nil`.
- `p == nil` is allowed for `?T`. Comparing a non-null `ref T` with `nil` is a
  compile error.

Current A7 (from the `nil` literal rules in `docs/SPEC.md`): `nil` is accepted only for reference
types today.

```a7
ptr: ref i32 = nil
if ptr == nil { }
x: i32 = nil           // ERROR: primitives cannot be nil
```

**Rationale.** The existing spec uses `nil` (see `examples/011_memory.a7` and
`examples/013_pointers.a7`). Keeping it avoids a migration and follows the Go /
Swift / Lua "nil keyword" style, not the Rust / Python style. The user
explicitly directed that existing syntax stay.

**Implications.**
- The `nil` keyword stays in the parser.
- `case nil: { ... }` is the standard absent arm in pattern matching.
- No `none` identifier in v1.
- Backend lowering matches current A7 behaviour.

Audit note (2026-09-16): D.006, D.010, D.014, D.016, D.017 and the cluster CA
summary still use `none` or `case none`. Under this revision, read those as
`nil` / `case nil`. The CA summary's "`nil` removed" lines predate this
revision.

---

### D.014 — Reading from `?T` requires `match` or `?` propagation; smart-narrow through guards    [ACCEPTED]

**Decision.** A `?T` value cannot be used as a `T` directly. There are three
ways to extract it:

1. **`match`**: pattern match on `some(v)` and `none`.
2. **`?` propagation** (D.017): `v := expr?` returns the enclosing function's
   failure case if `expr` is `nil`.
3. **Smart-narrow** (Kotlin-style): `if x == nil { ret ... }` narrows `x` from
   `?T` to `T` for the rest of the enclosing block. The early-return shape
   `if x != nil { ... } else { ret ... }` narrows the same way.

There is no `if let` construct (Rust-style) and no `?.` chaining operator.

Proposed example:

```a7
show :: fn(p: ?ref Buf) {
    if p == nil { ret }
    use(p)                          // p is narrowed to ref Buf here
}
```

**Rationale.** `match` always works. Smart-narrow covers the common guard at
the top of a function. `?` covers passing errors upward. Three mechanisms is
the minimum; `if let` or `?.` would add parallel ways to say the same thing.

**Implications.**
- The type checker tracks narrowed bindings through the CFG (cluster CD flow
  analysis).
- Smart-narrow is purely static. The emitted Zig has the same shape as the
  `match` form.

---

### D.015 — `[N]ref T` arrays require explicit initialisation        [ACCEPTED]

**Decision.** Declaring `arr: [N]ref T` without an initialiser is a compile
error. The user must either:

1. provide an array literal: `arr: [3]ref Buf = [p1, p2, p3]`; or
2. use `[N]?ref T` and assign each slot later.

**Rationale.** This is the simplest rule that keeps the non-null invariant: a
non-null array cannot have uninitialised slots.

**Implications.**
- Examples that declare fixed-size non-null reference arrays without an
  initialiser (rare) must move to one of the two forms.

---

## Fallibility

### D.016 — `Option<T>` and `Result<T, E>` are stdlib generic sum types    [ACCEPTED]

**Decision.** The stdlib has two generic sum types, both exported from the
prelude:

- `Option<T>`, with variants `some(T)` and `none`.
- `Result<T, E>`, with variants `ok(T)` and `err(E)`.

The error type `E` is structural: any type can be `E`. There is no required
`Error` trait.

Proposed example:

```a7
ParseError :: enum { Empty, BadDigit }

parse_port :: fn(s: string) Result<u16, ParseError> {
    if s.length == 0 { ret err(ParseError.Empty) }
    ...
}
```

**Rationale.** These are the standard sum-type shapes in Rust, Swift and Hylo.
A structural `E` is simpler than Rust's `From` machinery and is enough for v1.
If a trait system lands later, an `Error` trait can be added without breaking
existing `Result` code.

**Implications.**
- New stdlib modules: `a7/stdlib/option.py`, `a7/stdlib/result.py`.
- The compiler checks `match` exhaustiveness over `Option` and `Result` with
  the existing infrastructure.

---

### D.017 — `?` postfix propagation operator                          [ACCEPTED]

**Decision.** A7 has a postfix `?` operator. `expr?` desugars to:

- for `expr: Option<T>`:
  `match expr { case some(v): { v } case nil: { ret nil } }`;
- for `expr: Result<T, E>`:
  `match expr { case ok(v): { v } case err(e): { ret err(e) } }`.

`?` is allowed only when the enclosing function's return type has the same
shape: `Option<U>` for `Option<T>?`, and `Result<U, E>` with the same `E` for
`Result<T, E>?`. There is no `From`-based error conversion.

**Rationale.** This is the ergonomic standard in Rust, Swift and Zig. Without
it, threading `Result<T, E>` through call chains is impractical. Requiring the
exact error type keeps the rule simple (D.016 has no `From` trait).

**Implications.**
- Parser change: postfix `?` operator.
- The type checker enforces the exact error-type match.
- The backend desugars to the equivalent `match`.

---

### D.018 — No `unwrap()` / `expect()` methods                        [ACCEPTED]

**Decision.** The stdlib does not provide `.unwrap()` or `.expect("msg")` on
`Option` or `Result`. Both would be runtime traps, which the contract forbids.

Proposed example:

```a7
v: ?i32 = lookup(key)
a := v.unwrap()                 // compile error: no unwrap; use match, ?, or .unwrap_or
b := v.unwrap_or(0)             // OK: total
```

**Rationale.** The contract is zero runtime errors, and `unwrap` is a runtime
trap. Not shipping it is the consistent choice. The user matches explicitly or
calls the total `.unwrap_or(default)`.

**Implications.**
- A common Rust idiom is unavailable. The diagnostic for `.unwrap()` on
  `Option` / `Result` suggests `match`, `.unwrap_or(...)` or `?`.

---

### D.019 — Minimal combinator surface in v1: `.map`, `.unwrap_or`    [ACCEPTED]

**Decision.** In v1 the stdlib provides two combinators on each of `Option<T>`
and `Result<T, E>`:

- `Option<T>::map(self, f: fn(T) -> U) -> Option<U>`
- `Option<T>::unwrap_or(self, default: T) -> T`
- `Result<T, E>::map(self, f: fn(T) -> U) -> Result<U, E>`
- `Result<T, E>::unwrap_or(self, default: T) -> T`

Other combinators (`and_then`, `or_else`, `map_err`, `filter`, `is_some`,
`is_ok`, …) are not in v1. They are easy to add when a concrete need appears.

**Rationale.** Keep the v1 stdlib small. These two cover the most common
cases; users `match` otherwise.

**Implications.**
- Four methods in total across `Option` / `Result`. This is the documented v1
  ceiling.
- When a user reaches for `.and_then` or similar, the diagnostic suggests
  `match` or notes "planned for future".

---

## Compiler-internal (no user-facing surface)

### D.020 — Range analysis is a compiler pass, not a user-facing type system   [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate with `usize` and explicit widths.

**Decision.** The compiler tracks each `int` / `uint` / `number` value's
provable range internally, for two purposes:

1. specialising to native machine operations when the range fits a machine
   word (D.003);
2. discharging the safety obligations of D.022 (non-zero divisor) and D.023
   (index in bounds).

Users do not see refinement types: no `Bounded<T, lo, hi>`, no `Index<n>`, no
`NonZero<T>`. The range information lives in the type checker as flow
analysis.

(Audit note: the original text cited D.023 and D.024 for these obligations.
The divisor and bounds decisions are D.022 and D.023.)

**Rationale.** User-visible refinement types would add a keyword (`static`),
constructor methods and pattern-binding rules for information the compiler can
keep invisibly. Users write plain `int`; the compiler proves or disproves the
obligations.

**Implications.**
- The planned "refinement-lite type kit" leaves the user surface.
- Compiler complexity rises (the range tracker becomes load-bearing);
  user-facing complexity falls.

---

### D.021 — Compiler-inferred `Copy` marker                            [ACCEPTED]

**Decision.** A7 has a built-in, compiler-level `Copy` marker. It separates
types that can be freely duplicated (numeric types, `bool`, enum tags without
payload) from types with ownership semantics (heap allocations, types with
`del`, references). `Copy` is not a user-facing trait; there is no
`impl Copy for ...` syntax. The compiler infers it from structure. D.047 gives
the proposed inference rules.

**Rationale.** Cluster CC's affine-ownership model needs to know which types
move and which copy. Inferring from structure is simpler than user
annotations.

**Implications.**
- Each type carries a compiler-tracked `Copy` flag.
- Generic constraints can require `Copy` through the existing type-set
  vocabulary.

---

## Safety obligations preserved by Cluster CA

### D.022 — Division by zero is a compile error                        [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Decision.** Bare `a / b` and `a % b` compile only when the compiler proves
`b != 0`. Otherwise the user:

1. **adds a guard**: `if b == 0: ... else: ... a / b ... end` (smart-narrow
   extends to "`b` is non-zero in this branch"); or
2. **uses the method form**: `a.checked_div(b)?`, returning `?int` (or
   `?uint`, and so on).

When the compiler rejects `/` or `%` with an opaque divisor, the diagnostic
includes the fix-it.

Proposed example (brace syntax, explicit widths):

```a7
average :: fn(total: i64, count: i64) i64 {
    if count == 0 { ret 0 }
    ret total / count               // count is proved non-zero
}
```

**Rationale.** The contract forbids runtime traps. Where range analysis cannot
discharge the obligation, A7 applies SPARK-tier discipline (see
[`comparative/ada.md`](./comparative/ada.md)).

**Implications.**
- The stdlib provides `.checked_div(b)` and `.checked_mod(b)` on numeric
  types, returning the matching `?T`.
- Existing examples and tests that divide by an opaque divisor get a one-time
  rewrite to the guard or the method.

---

### D.023 — Slice/array out-of-bounds is a compile error               [ACCEPTED]

**Decision.** Bare `s[i]` compiles only when the compiler proves
`i < s.length`. Otherwise the user:

1. **uses a recognised loop pattern** (`for i in 0..s.length: s[i]`), where
   the compiler proves the bound;
2. **adds an explicit guard**: `if i < s.length: ... s[i] ... else: ... end`;
   or
3. **uses the method form**: `s.get(i)?`, returning `?T`.

The diagnostic includes the fix-it.

Proposed example (brace syntax, `usize` index):

```a7
at_or_zero :: fn(s: []i32, i: usize) i32 {
    if i < s.length { ret s[i] }    // i is proved in bounds
    ret 0
}
```

**Rationale.** Same as D.022. The proof patterns mirror the `'Range` attribute
and `Index<n>` discipline in
[`comparative/ada-deep-dive.md`](./comparative/ada-deep-dive.md) §7, expressed
as flow analysis instead of user-visible types.

**Implications.**
- The stdlib provides `.get(i)` on every indexable type.
- The range tracker (D.020) sees through the recognised patterns and through
  smart-narrow guards.

---

## Cluster CA — summary

**Decisions: 23** (D.001 through D.023).

Coverage:
- **Numeric vocabulary**: D.001–D.005 (5)
- **bool and string**: D.006–D.008 (3)
- **Compound types and literals**: D.009 (1)
- **Nullability**: D.010–D.015 (6)
- **Fallibility**: D.016–D.019 (4)
- **Compiler-internal**: D.020–D.021 (2)
- **Safety obligations**: D.022–D.023 (2)

### What the user sees vs. what the compiler does

> Audit note (2026-09-16): this summary predates two changes. First, the
> revised D.013 keeps `nil` and has no `none`, so the "`none` replaces `nil`"
> and "`nil` removed" lines below are out of date. Second, the numeric lines
> (`int` / `uint` / `number`, bignum promotion) are superseded by L3, L4 and L5
> in [the ledger](../plan/decisions.md).

User-facing additions, compared with current A7:

- Three primary numeric types `int` / `uint` / `number`; existing bit-width
  types become FFI-only with warnings.
- `?T` type prefix sugar (one new operator character).
- `?` postfix propagation (same character, different position).
- `Option<T>` and `Result<T, E>` stdlib generics.
- `none` stdlib identifier (replaces `nil` keyword).
- `f"..."` string interpolation (one new literal prefix).
- `[1, 2, 3]` array literal syntax.

Removed from earlier proposals:
- `nil` keyword (D.013).
- `Bounded`, `Index`, `NonZero`, `Fin` and other refinement types (D.020).
- `static` keyword (not needed without refinement types).
- `newtype` keyword (Ada distinct types; deferred indefinitely).
- `?.`, `?[]`, `??` chaining operators.
- `if let` construct.
- `Default` / `From` traits.
- `unwrap()` / `expect()` methods.
- General trait system.

Compiler-internal complexity, increased to compensate:
- Range tracker on `int` / `uint` / `number` for specialisation and
  safety-obligation discharge.
- Smart-narrow analysis through `if x == none:`, `if i < s.length:`, and
  similar guards.
- Bignum-promotion code emission. It is transparent to the user and appears in
  the emitted Zig as one branch per arithmetic operation when the compiler
  cannot prove the range.

---

## Cluster CA status: **ACCEPTED**

All 23 decisions approved. Source of truth for Phase D (the spec), except
where [the ledger](../plan/decisions.md) supersedes them (see
[Current status](#current-status)).

---

# Cluster CB — Cast and conversions

This cluster decides the shape of every conversion in A7: numeric
(`int ↔ uint ↔ number`), string (parse, format), boolean, reference (already
covered by CA), array/slice, enum discriminant, and FFI bit-width.

Sources: `edge-cases/01-cast.md`, [`conversions.md`](./conversions.md) (the
deep-research input for this cluster), and the files in `comparative/`.

Direction from `conversions.md`:

- **Method-style** is the conversion shape; no new operator keyword.
- **Fallible conversions return `?T`**, consistent with CA.
- **No `cast(T, x)` operator**; this closes the hole the audit flagged.
- **No `bit_cast` operator**; stdlib helpers cover the few cases.
- **Narrowing removes runtime checks**. This is the central performance
  point: conversion checks compile away when the prover discharges them.

Audit note (2026-09-16): this direction conflicts with D.024 and D.025, which
keep `cast(T, x)` and return direct types for statically resolvable
conversions. D.038 then removes `cast`. Gate G3 in
[the ledger](../plan/decisions.md) settles `cast`.

---

### D.024 — `cast(T, x)` is the universal conversion operator       [ACCEPTED]

Contradiction (2026-09-16): D.024 and D.038 disagree. The ledger accepts neither; see [docs/plan/decisions.md](../plan/decisions.md), gate G3.

**Question.** `01-cast.md` Q01a: the shape of the cast surface.

**Decision.** Every A7 conversion uses the `cast(T, x)` operator, which is
existing A7 syntax. The operator is restricted to safe conversions (D.025):

- it returns `T` directly when the precondition is statically discharged;
- it returns `?T` when failure depends on runtime data;
- it is a compile error when the precondition is statically resolvable but
  not discharged;
- it is a hard compile error for forbidden casts (int ↔ pointer).

```a7
x: int = 5
y: uint = cast(uint, x)          // compile error: x may be negative
z: number = cast(number, x)      // infallible (lossless)
s: string = cast(string, x)      // infallible (format)
n: ?int = cast(int, "42")        // ?int — parsing is data-dependent
```

There is no `as T` operator and no `int(x)` constructor form. The one shape is
`cast(T, x)`.

`n.floor()`, `n.ceil()`, `n.round()` and `n.trunc()` on `number` still exist.
They are operations on `number` that return a rounded `number`, not
conversions. The user combines them: `cast(int, n.floor())`.

**Rationale.** The user directed that the existing `cast()` syntax stay. The
fix for the audit's most urgent finding (`07-language-review.md` §1.2) is to
restrict `cast()` to safe conversions, not to remove it.

**Implications.**
- `cast(T, x)` stays in the parser.
- The cast classifier (D.037) decides for each `(source, target)` pair whether
  the cast is allowed, fallible (returns `?T`) or forbidden.
- The `INVALID_CAST` and `UNSAFE_CAST` error types go from declared-but-unused
  to emitted.

---

### D.025 — Statically-resolvable failures compile-error; only data-dependent failures return `?T`   [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** `01-cast.md` Q01b, revised after user direction.

**Decision.** Operations fall into two categories:

| Category | Examples | Return type | Failure handling |
| --- | --- | --- | --- |
| **Statically resolvable** | `a / b`, `s[i]`, `x.to_uint()`, `n.to_int_floor()`, `[N]T::from(s)`, `EnumT::from_discriminant(i)` | the direct type (`int`, `uint`, `[N]T`, `EnumT`, etc.) | Compile error if the prover can't discharge the obligation; user adds a guard |
| **Data-dependent** | `s.parse_int()`, `new T{...}`, `read_line()`, `extern fn` returns | `?T` or `Result<T, E>` | User matches, propagates with `?`, or uses `.unwrap_or(default)` |

The principle: an operation returns `?T` only when the prover cannot discharge
the failure statically. Conversions between known types, where the prover
knows the source range, return the direct type. If the user has not
established the precondition, the call is a compile error.

```a7
divide :: fn(a: int, b: int) int {
    if b == 0 { ret 0 }
    ret a / b                           // bare; b proved non-zero
}

to_uint_or_zero :: fn(x: int) uint {
    if x < 0 { ret 0 }
    ret cast(uint, x)                   // returns uint directly; x proved >= 0
}

read_age :: fn() int {
    s: ?string = read_line()            // ?string — I/O is data-dependent
    if s == nil { ret 0 }
    ret cast(int, s).unwrap_or(0)       // ?int — parsing is data-dependent
}
```

**Rationale.** An earlier draft made every conversion return `?T`, which forces
Rust-style `?` everywhere. The revision says: if the compiler can know whether
the operation succeeds (through narrowing), return the direct type and make the
user establish the precondition. The user writes plain code and the compiler
enforces it. This meets the Python/Go/JS ergonomic target and keeps the
zero-runtime-error contract.

**Implications.**
- Most conversions return their direct type, not `?T`.
- `?T` remains for parsing, allocation, I/O, FFI returns, and the few truly
  data-dependent conversions (for example `to_int_exact()`: whether a
  `number` is an integer depends on its runtime value).
- Compile errors carry fix-its naming the right guard pattern (D.037).
- The narrowing system (`narrowing.md`) is no longer an optional
  optimisation. It is mandatory for statically resolvable operations: without
  it the program does not compile (D.039).

---

### D.026 — The numeric conversion method catalog                  [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** Implicit in the user-facing numeric surface.

**Decision.** The full conversion menu between the three primary numeric
types. Every method returns the direct type, never `?T`. When the prover
cannot discharge the precondition, the call is a compile error.

| Source | Target | Method | Returns | Precondition (must be discharged or compile error) |
| --- | --- | --- | --- | --- |
| `int` | `uint` | `.to_uint()` | `uint` | `x >= 0` |
| `int` | `number` | `.to_number()` | `number` | none (always succeeds) |
| `uint` | `int` | `.to_int()` | `int` | none |
| `uint` | `number` | `.to_number()` | `number` | none |
| `number` | `int` | (4 methods — see D.027) | `int` | varies |
| `number` | `uint` | (4 methods — see D.027) | `uint` | `n >= 0` (where applicable) |

Identity conversions (`int → int` and so on) are not methods. They are no-ops;
the type system accepts the value directly.

**Rationale.** Per D.025, statically resolvable failures return the direct type
and fail compilation when the precondition is not discharged. The user writes
plain code; the compiler enforces the guard.

**Implications.**
- The stdlib defines six methods on each numeric type.
- No `?T` returns on conversions, so no Rust-style `?` boilerplate.
- Compile errors carry fix-its (D.037).
- Narrowing (D.039) makes the methods usable: the prover discharges the
  preconditions for typical code patterns.

(Audit note: D.024 says conversions are spelled `cast(T, x)` with no
constructor form, while this table uses `.to_T()` methods. Gate G3 covers
both.)

---

### D.027 — `number → int` / `uint` rounding methods               [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** Implicit from CA D.001 plus rounding-policy design.

**Decision.** `number` has four methods for each integer target:

| Method | Semantics |
| --- | --- |
| `.to_int_trunc() -> int` | Round toward zero |
| `.to_int_floor() -> int` | Round toward `-∞` |
| `.to_int_round() -> int` | Round half to even (banker's) |
| `.to_int_exact() -> ?int` | None unless `n` is mathematically an integer (data-dependent) |

The `to_uint_*` variants have the same shape plus one precondition, `n >= 0`,
which the compiler enforces:

| Method | Return | Compile-time precondition |
| --- | --- | --- |
| `.to_uint_trunc()` | `uint` | `n >= 0` (data-dependent → compile error if not proved) |
| `.to_uint_floor()` | `uint` | `n >= 0` |
| `.to_uint_round()` | `uint` | `n >= 0` |
| `.to_uint_exact()` | `?uint` | none (returns none if not exact OR negative) |

Per D.025, the `_trunc`, `_floor` and `_round` variants return the direct type
and fail compilation if the prover cannot discharge `n >= 0`. The `_exact`
variants return `?T` because integrality depends on runtime data.

**Rationale.** Named rounding modes document themselves. Python's `int(x)`
truncates by default, which is convenient but hides the mode; A7 makes the
user pick. Four modes cover every practical need. `?T` is reserved for the
truly data-dependent case (`_exact`).

**Implications.**
- Eight methods on `number`: four `to_int_*` and four `to_uint_*`.
- Six of the eight return `int` / `uint` directly; the two `_exact` variants
  return `?int` / `?uint`.
- Calling `n.to_uint_floor()` on an opaque `n` is a compile error. The
  diagnostic suggests `if n >= 0: ... else: ... end`, or
  `n.to_uint_exact()` to handle both failure modes at once.

---

### D.028 — String formatting via `.to_string()` and `.format(spec)`   [ACCEPTED]

**Question.** Implicit: needed for `f"..."` interpolation and general
formatting.

**Decision.** Every built-in type provides `.to_string()`. For formatted
output, `.format(spec)` takes a stdlib format-spec string. The format-spec
syntax is a stdlib detail (TBD; Python-style `:0.4f` is the working
assumption).

Proposed example:

```a7
count: i32 = 7
ratio: f64 = 0.125
a: string = count.to_string()          // "7"
b: string = ratio.format("0.4f")       // spec syntax still TBD
```

**Rationale.** A two-method surface. The default format covers about 90 % of
cases and is what `f"..."` uses (CA D.008); `.format` covers the rest.

**Implications.**
- The stdlib has `.to_string()` on each built-in type.
- The format-spec language is designed during stdlib work, not in this
  decision.

---

### D.029 — String parsing methods                                  [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** Implicit from CA D.007 (`string` has `.parse_int()`).

**Decision.** `string` provides:

- `s.parse_int() -> ?int`: decimal; none for any invalid input.
- `s.parse_uint() -> ?uint`: decimal; fails for invalid or negative input.
- `s.parse_number() -> ?number`: decimal point and scientific notation.
- `s.parse_bool() -> ?bool`: exactly `"true"` or `"false"`, case-sensitive.

For other radixes: `s.parse_int_radix(r: uint) -> ?int`, where `r ∈ [2, 36]`.

**Rationale.** Five methods cover the typical surface. Richer parsing is user
code.

**Implications.**
- Five stdlib methods.
- Whitespace handling is not built in; the user calls `.trim()` first. This
  avoids hidden behaviour.

---

### D.030 — `bool ↔ numeric` conversions are forbidden              [ACCEPTED]

**Question.** Implicit from CA D.006 (no truthy/falsy).

**Decision.** `bool` has no `.to_int()`, and `int` / `uint` / `number` have no
`.to_bool()`. To get a number from a `bool`, the user writes
`if b: 1 else: 0 end`.

Proposed example (brace syntax, explicit widths):

```a7
done: bool = true
n := done.to_int()                      // compile error: bool has no numeric conversion
m: i32 = if done { 1 } else { 0 }       // OK
```

**Rationale.** Mixing numbers and booleans causes bugs. The explicit `if`
expression costs one extra character.

**Implications.**
- The stdlib does not define these methods.
- The diagnostic for `b.to_int()` suggests the explicit form.

---

### D.031 — Array → slice implicit; slice → array compile-error if length not proved   [ACCEPTED]

**Question.** `01-cast.md` C-25, C-26.

**Decision.** `[N]T → []T` is an implicit upcast; no method call is needed.
`[]T → [N]T` is statically resolvable (D.025): `[N]T::from(s)` returns `[N]T`
directly when the compiler proves `s.length == N`, and is a compile error
otherwise.

```a7
arr: [3]int = [1, 2, 3]
s: []int = arr                          // implicit array-to-slice

s2: []int = read_slice()                // opaque length
a2: [3]int = cast([3]int, s2)           // compile error: s2.length not proved == 3

if s2.length == 3 {
    a2: [3]int = cast([3]int, s2)       // OK; narrowed
}
```

v1 has no `try_from` returning `?[N]T`. Converting a runtime-length slice to a
fixed-size array is uncommon, so forcing the guard is acceptable. A fallible
variant can be added later if practice shows the need.

**Rationale.** D.025: no `?T` for statically resolvable failures. The failure
mode here is "length does not match", which is exactly the kind of obligation
the prover should discharge.

**Implications.**
- The type checker accepts `[N]T` where `[]T` is expected and emits the
  slicing automatically.
- `[N]T::from(s)` is prove-or-compile-error, not fallible.
- Narrowing through `if s.length == N:` discharges the obligation inside the
  branch.

---

### D.032 — Enum discriminant conversion                             [ACCEPTED]

**Question.** `01-cast.md` Q01d (C-22, C-23, C-24).

**Decision.** Every enum exposes two methods:

- `e.discriminant() -> int`: always succeeds; returns the discriminant
  (sequential from 0 by default, or as declared).
- `EnumT::from_discriminant(i: int) -> EnumT`: returns the variant directly.
  It is a compile error unless `i` is range-proved to be a valid
  discriminant.

For data-dependent discriminants (parsed input, FFI), the user adds an
explicit `match` or guard:

```a7
raw: int = parse_disc()?                   // opaque after parse
v: Color = cast(Color, raw)                // compile error: raw not proved valid

// with guard:
match raw {
    case 0..=2: { v: Color = cast(Color, raw) }   // OK; range-proved
    else: { ret nil }
}
```

Casts between enums (`EnumA → EnumB`) are forbidden; the user goes through the
discriminant.

**Rationale.** D.025. An invalid discriminant is statically resolvable when the
source is range-proved, and the prover discharges those cases. For data from
parsing, the user writes a `match` on the integer, and narrowing discharges the
call in each arm.

**Implications.**
- Every enum type gets these two methods automatically.
- The user wraps `from_discriminant` in a guard for parsed data.
- The diagnostic for an unguarded call suggests the `match` pattern.

---

### D.033 — FFI bit-width conversions inside extern shims          [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** `01-cast.md` C-29.

**Decision.** Inside an `extern fn` caller shim (the function that wraps the
foreign call), bit-width types (`i32`, `u64`, …) are first-class with no
warning, per CA D.002's exemption. Conversions follow D.025: direct return
type, compile error when unproved.

```a7
c_get_count :: extern fn() i32          // foreign signature

read_count :: fn() int {
    raw: i32 = c_get_count()             // raw is i32, opaque range
    if raw < 0 {
        ret 0
    }
    ret cast(int, raw)                   // returns int directly;
                                          // raw proved >= 0; precondition
                                          // for cast(int, i32) is trivially met
}
```

The reverse direction, `int → i32`, requires the prover to show the value
fits:

```a7
write_count :: fn(n: int) {
    if n > 2147483647 {
        ret                              // or handle overflow
    }
    raw: i32 = cast(i32, n)              // OK; n proved in i32 range
    c_set_count(raw)
}
```

**Rationale.** Same shape as primary-type conversions (D.026). Narrowing
discharges typical FFI conversions where the user has guarded; opaque
conversions get compile errors with fix-its.

**Implications.**
- Bit-width types are valid `cast()` sources and targets in FFI shims:
  `cast(int, raw_i32)`, `cast(i32, n: int)` and so on.
- The reverse direction (`int → i32`, …) requires a range proof; otherwise it
  is a compile error.
- FFI return values from `extern fn` are declared `?T` or `Result<T, E>`,
  depending on what the foreign function promises. That failure mode is
  data-dependent.

---

### D.034 — No `bit_cast` operator; stdlib helpers cover the cases   [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** `01-cast.md` Q01c.

**Decision.** A7 has no `bit_cast` keyword or operator. For the small, closed
set of bit-pattern reinterpretations, the stdlib provides named helpers:

| Method | Use case |
| --- | --- |
| `f32.bits() -> u32` | Float-to-int bit extraction (hashing) |
| `f64.bits() -> u64` | Same for 64-bit |
| `u32.as_f32() -> f32` | Construct float from bits |
| `u64.as_f64() -> f64` | Same |

All four use bit-width source or target types, so they are available only
inside FFI shims or with the warning-silencing attribute.

**Rationale.** Audit Q01c's first option (yes, restricted) would let users
reinterpret any same-size non-pointer value. That is rarely used and invites
bugs. Four named helpers cover the real cases without ambiguity.

**Implications.**
- No `bit_cast` keyword in the parser.
- Four stdlib methods, scoped to FFI and bit manipulation.

---

### D.035 — Compile-time literal conversion has no runtime cost     [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** `01-cast.md` Q01h.

**Decision.** Numeric literals carry comptime-known values. Converting a
literal to any compatible numeric target happens at compile time, with the
range check at compile time and no runtime code. Arithmetic among literals
works the same way.

```a7
x: int = 42                // literal, comptime int
y: uint = 42               // literal fits uint; compile-time conversion
z: number = 42             // lossless embedding
n: uint = 10 * 5           // comptime 50; fits uint
bad: uint = -5             // compile error: -5 doesn't fit uint
```

**Rationale.** Matches Zig's `comptime_int` semantics. Users can write plain
integer literals everywhere.

**Implications.**
- The existing constant-folding pass recognises literal conversions and emits
  the target-type value directly.
- The user never writes `.to_T()` for a literal.

---

### D.036 — Generic-context conversion: per-instantiation            [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** `01-cast.md` Q01g + C-28.

**Decision.** `cast()` calls inside generic code are checked per
instantiation. If a generic function calls `cast(int, x)` with `x: $T`, every
concrete `$T` must support the conversion, or `$T` must satisfy a type-set
constraint that promises it.

```a7
double_then_int :: fn($T: @type_set([CastableToInt]), x: $T) int {
    ret cast(int, x) * 2
}
```

Without the type-set constraint, the call is a compile error at the
declaration site: no instantiation can prove the conversion is supported
generically.

**Rationale.** Fits the existing generics infrastructure. `@type_set(...)`
constraints already serve this purpose; the conversions become more predicates
in that vocabulary.

**Implications.**
- Stdlib type sets such as `CastableToInt`, `CastableToUint` and
  `CastableToString` cover common conversions.
- Per-instantiation checking needs no new infrastructure; the existing pass
  covers it.

---

### D.037 — Forbidden-conversion diagnostics with fix-it suggestions   [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** `01-cast.md` Q01g.

**Decision.** When a user attempts a forbidden conversion, the diagnostic
must:

1. name the source and target types;
2. suggest the right method-call alternative;
3. where it applies, suggest a guard that would discharge the obligation.

Example:

```
error: int → uint conversion requires `x >= 0`
  --> example.a7:7:23
   |
 7 |     let u: uint = x.to_uint()
   |                        ^ `x` may be negative here; range is `int` (full range)
   |
help: add a guard so the prover can discharge the precondition:
   |
 6 |     if x < 0: return end
 7 |     let u: uint = x.to_uint()
   |
help: alternatively, use a checked form:
   |
 7 |     if x >= 0: let u: uint = x.to_uint() end
```

v1 suggests no `?T` form, because D.025 says `to_uint()` returns `uint`
directly. The diagnostic points to the guard pattern, and narrowing then
discharges the call.

The existing `INVALID_CAST` and `UNSAFE_CAST` error types (declared but unused
at `a7/errors.py:148-149` when this was written) become emitted.

**Rationale.** The diagnostic is the user-visible face of the safety contract.
Good suggestions teach the discipline.

**Implications.**
- An error-emission table maps (source type, target type) pairs to fix-it
  strings.
- A one-time investment that pays off across the example suite and user code.

---

### D.038 — The `cast(T, x)` operator is removed                     [ACCEPTED]

Contradiction (2026-09-16): D.024 and D.038 disagree. The ledger accepts neither; see [docs/plan/decisions.md](../plan/decisions.md), gate G3.

**Question.** `01-cast.md` Q01f.

**Decision.** The existing `cast(T, x)` syntax is removed from the language.
No grace period and no deprecation flag: a clean break. Existing uses get a
compile error with a fix-it that suggests the matching `.to_T()` method.

**Rationale.** The audit (`07-language-review.md` §1.2) found this the most
urgent safety hole: `cast(ref T, integer)` compiles today. Removing it closes
the hole in one step. The migration is small (a handful of uses in the example
suite, per the audit).

**Implications.**
- The parser drops `cast` as a keyword/operator.
- Existing examples using `cast(T, x)` get a one-time rewrite to the matching
  method call.
- `docs/SPEC.md` drops the cast section.

---

### D.039 — Narrowing is the only mechanism that makes statically-resolvable operations callable   [ACCEPTED]

Restate (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L4; restate for explicit widths under gate G3.

**Question.** Implicit from D.025 and the narrowing system in
`narrowing.md`.

**Decision.** For every operation whose failure is statically resolvable
(D.025) — division `a / b`, indexing `s[i]`, conversions such as
`x.to_uint()`, `n.to_int_floor()`, `[N]T::from(s)`,
`EnumT::from_discriminant(i)` — narrowing analysis is mandatory:

- If the prover discharges the precondition at the call site, the compiler
  emits a bare operation with no runtime check.
- If the prover cannot, the call does not compile. The error includes a fix-it
  suggesting the right guard.

Narrowing does not "optimise away runtime checks". It is the only way these
operations reach code generation at all. Without narrowing, the program does
not compile.

```a7
process :: fn(s: []int, i: int) int {
    if i < 0 or i >= s.length {
        ret -1
    }
    // i is range-proved [0, s.length-1]
    idx := cast(uint, i)              // returns uint directly;
                                       // prover discharged `i >= 0`;
                                       // bare emission `@intCast(usize, i)`.
    ret s[idx]                         // bare emission; bounds discharged.
}
```

Without the guard:

```a7
process_bad :: fn(s: []int, i: int) int {
    idx := cast(uint, i)              // compile error: `i` may be negative
                                       // help: guard with `if i < 0 { ret ... }`
    ret s[idx]                         // (this line never compiles)
}
```

The user never chooses between "fast" and "safe" emission. They write the
obvious code, and the compiler either accepts it (prover discharged) or
rejects it (with a fix-it). The Zig output has no `@panic`, no `unreachable`
and no implicit safety check.

**Rationale.** This is the load-bearing principle of the zero-runtime-error
contract. Statically resolvable operations share one mechanism: the type
checker enforces the precondition and the emitter assumes it. There are no two
codegen paths per method, no `?T` boilerplate and no runtime traps.

**Implications.**
- D.025–D.027 and D.031–D.033 all delegate precondition discharge to
  narrowing.
- The narrowing system (details locked in by cluster CD) is a required v1
  feature, not an optimisation to ship later.
- The no-trap codegen test (`05-for-a7.md` §4.8.13) is the operational check:
  any code path that compiles must emit safe Zig under `-O ReleaseFast`.
- Each conversion, division or index method has one codegen path (bare
  operation). The fallible shape exists only for data-dependent operations
  (parsing, I/O, allocation, FFI returns), which always emit the `if` form.

(Audit note: the first example compares `i: int` with `s.length: uint`, which
D.005 forbids without a conversion.)

---

## Cluster CB — summary

**Decisions: 16** (D.024 through D.039).

Coverage:
- **Conversion shape**: D.024–D.025 (2)
- **Numeric method catalog**: D.026–D.027 (2)
- **String I/O**: D.028–D.029 (2)
- **Bool isolation**: D.030 (1)
- **Compound conversions**: D.031–D.032 (2)
- **FFI conversions**: D.033 (1)
- **No `bit_cast`**: D.034 (1)
- **Compile-time + generics**: D.035–D.036 (2)
- **Diagnostics + migration**: D.037–D.038 (2)
- **Narrowing-mandatory**: D.039 (1)

### Conversions cheat-sheet — what the user writes

| Operation | Returns | Precondition (compile error if not proved) | Failure category |
| --- | --- | --- | --- |
| `x: int → x.to_uint()` | `uint` | `x >= 0` | Statically resolvable |
| `x: int → x.to_number()` | `number` | none | always succeeds |
| `x: uint → x.to_int()` | `int` | none | always succeeds |
| `x: uint → x.to_number()` | `number` | none | always succeeds |
| `n: number → n.to_int_trunc()` | `int` | none | always succeeds |
| `n: number → n.to_int_floor()` | `int` | none | always succeeds |
| `n: number → n.to_int_round()` | `int` | none | always succeeds |
| `n: number → n.to_int_exact()` | `?int` | none | data-dependent (is `n` integral?) |
| `n: number → n.to_uint_trunc()` | `uint` | `n >= 0` | Statically resolvable |
| `n: number → n.to_uint_floor()` | `uint` | `n >= 0` | Statically resolvable |
| `n: number → n.to_uint_round()` | `uint` | `n >= 0` | Statically resolvable |
| `n: number → n.to_uint_exact()` | `?uint` | none | data-dependent |
| `x: any → x.to_string()` | `string` | none | always succeeds |
| `s: string → s.parse_int()` | `?int` | n/a | data-dependent (parse arbitrary input) |
| `s: string → s.parse_uint()` | `?uint` | n/a | data-dependent |
| `s: string → s.parse_number()` | `?number` | n/a | data-dependent |
| `s: string → s.parse_bool()` | `?bool` | n/a | data-dependent |
| `[N]T arr → []T` | implicit upcast | none | always succeeds |
| `[]T s → [N]T::from(s)` | `[N]T` | `s.length == N` | Statically resolvable |
| `e: EnumT → e.discriminant()` | `int` | none | always succeeds |
| `i: int → EnumT::from_discriminant(i)` | `EnumT` | `i` is a valid discriminant | Statically resolvable |
| FFI bit-width conversions | direct (e.g. `i32`) | range fits target | Statically resolvable |
| `new T{...}` (allocation) | `?ref T` | n/a | data-dependent (OOM possible) |
| FFI return values | declared `?T` or `Result<T, E>` | n/a | data-dependent |

The `?T` surface is small: only data-dependent operations return option-shaped
results. Statically resolvable operations return direct types and fail to
compile when preconditions are not discharged.

### What the user sees (compared to A7 today)

Additions:
- Conversion methods on numeric, string, bool and FFI types.
- `[N]T::from(s)` for slice-to-array.
- `.discriminant()` and `EnumT::from_discriminant(i)`.
- `f32.bits()` and related bit-manipulation helpers (FFI scope).

Removals:
- The `cast(T, x)` operator, closing the audit's most urgent finding.
  (Audit note: this follows D.038 and contradicts D.024; gate G3 decides.)

Compiler-internal complexity (no user-visible change):
- Mandatory narrowing-driven check discharge (D.039).
- Forbidden-conversion diagnostic table (D.037).

---

## Cluster CB status: **ACCEPTED**

The cluster index marks all 16 decisions accepted. D.024 and D.038 still need
the explicit Q2 resolution tracked in `HANDOFF.md`: keep the hybrid `cast()`
boundary, or remove `cast()` entirely. Until that is settled, the accepted
cluster contains a known internal contradiction. As of 2026-09-16, gate G3 in
[the ledger](../plan/decisions.md) owns this question.

---

# Cluster CC — Ownership and parameter modes

This cluster defines parameter-passing modes, the move analysis behind
ownership safety, and the channel and task primitives that combine with
ownership for concurrency.

Sources: `edge-cases/10-affine-ownership.md`,
[`parameter-modes.md`](./parameter-modes.md) (deep-research input for this
cluster), `comparative/hylo.md`, `comparative/swift.md`,
`comparative/inko-koka-verona.md`.

Direction from `parameter-modes.md`:

- **Function parameters are immutable by default** (Odin / Zig style).
- **Three parameter modes** exist (`borrow`, `inout`, `consume`) but are
  inferred from the function body. The user writes plain `fn(args)`
  declarations and the compiler decides each mode. The keywords stay available
  for explicit contracts at API boundaries.
- **No caller-side sigils** (Mojo style). The function signature and IDE
  tooling tell the reader what each argument does.
- **References exist only as parameter modes**, never as storable values. No
  lifetime annotations.
- **Move analysis** at compile time: each binding is live, partially moved or
  consumed. Reusing a consumed binding is a compile error.
- **Concurrency**: channels plus isolated owned data. No shared mutable state
  across tasks. Channel send moves the value.

Audit note (2026-09-16): the revised D.041 requires explicit modes on public
functions, which narrows the "inferred" bullet above. The ledger did not accept
D.040, D.041 or D.049. L6 approves immutable arguments as a principle only,
and the [memory plan](../plan/memory.md) makes ownership internal.

---

### D.040 — Function parameters are immutable by default               [PROPOSED]

Not accepted (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L6 scope limit and the memory plan.

**Question.** Implicit from user direction ("function params are immutable
like Zig and Odin").

**Decision.** Every function parameter is immutable in the function body
unless declared `inout` or `consume`. The default mode is read-only
(equivalent to the explicit `borrow` keyword). Assigning to the parameter
binding is a compile error.

```a7
process :: fn(x: int, s: []u8) {
    x = 10                          // compile error: x is immutable
    s[0] = 0                        // compile error: s is borrow
}
```

To mutate caller data, the function declares the parameter `inout`:

```a7
fill :: fn(b: inout []u8) {
    for i := 0; i < b.length; i += 1 { b[i] = 0 }   // OK
}
```

To mutate a local copy, the user copies explicitly:

```a7
shift :: fn(x: int) int {
    local := x                       // copy
    local += 5                       // mutate local
    ret local
}
```

**Rationale.** Matches Odin, where all procedure parameters are immutable.
Removes a common bug: mutating a parameter and expecting the caller to see
it. The signature must state its intent.

**Implications.**
- Parser change: the mode keyword determines parameter mutability.
- The type checker rejects parameter reassignment unless the mode is `inout`
  or `consume`.
- Codegen lowers parameters to `const` Zig locals by default.

---

### D.041 — Parameter modes are explicit at public boundaries and inferred privately  [REVISED — PROPOSED]

Not accepted (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L6 scope limit and the memory plan.

**Question.** `10-affine-ownership.md` Q10a, Q10b. Revised after user
direction ("the user shouldn't need to write all these stuff; the compiler
should be doing the checking").

**Decision.** A7 has three parameter modes: `borrow`, `inout` and `consume`.
Public (API-boundary) functions must state modes in their signatures. Private
functions may omit them; the compiler infers each omitted mode from the body.

```a7
// Private function: no mode keyword required
print :: fn(s: []u8) {
    io.println("{}", s)              // only reads s
}
// Compiler infers: print :: fn(s: borrow []u8)

fill :: fn(b: []u8) {
    for i := 0; i < b.length; i += 1 {
        b[i] = 0                      // writes b
    }
}
// Compiler infers: fill :: fn(b: inout []u8)

release :: fn(p: ref Buf) {
    use(p)
    del p                             // consumes p
}
// Compiler infers: release :: fn(p: consume ref Buf)

// Public function: mode is part of the API contract
pub fill_public :: fn(b: inout []u8) {
    for i := 0; i < b.length; i += 1 {
        b[i] = 0
    }
}
```

Inference walks the body and takes the maximum on the lattice
`borrow` < `inout` < `consume`:

- any `del` or consume-position use → `consume`;
- otherwise, any write or inout-position use → `inout`;
- otherwise (reads only) → `borrow`.

The keywords are required for:
- **public functions**, where the signature is the durable API contract;
- **cross-module signatures**, where the body may be unavailable;
- **public generic functions**, where each instantiation may impose different
  demands and the mode must be named.

Private functions may still state modes when the author wants a local
contract. The compiler checks that the body matches the declared mode. If the
declared and inferred modes differ, the compiler reports it as a warning or an
error (D.041b).

**Rationale.** The user wants the language as easy as Python, Go or JS. For
private functions, explicit modes are ceremony the compiler can supply. For
public functions, body-inferred modes break separate compilation and make API
contracts unstable. The split keeps local code light and module interfaces
readable and stable.

**Implications.**
- The parser accepts parameters with or without mode keywords, but rejects
  omitted modes on public functions and public generic functions.
- A new pass, or an extension of the move-analysis pass (D.043), infers each
  parameter's mode from the body.
- Tooling (`a7 --show-types`) shows inferred modes so users can check them.
- Module interfaces (binary or AST form) record explicit public modes and
  inferred private modes.
- Callers always see the declared or inferred mode for exclusivity checks
  (D.044).

---

### D.041b — Inferred mode vs declared mode discrepancies         [PROPOSED]

Depends on D.041, which the ledger did not accept (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L6 scope limit.

**Decision.** When a parameter mode is written explicitly and the inferred
mode differs:

| Declared | Inferred | Outcome |
| --- | --- | --- |
| `borrow` | `borrow` | OK |
| `borrow` | `inout` | **Compile error**: body writes to a borrow parameter |
| `borrow` | `consume` | **Compile error**: body consumes a borrow parameter |
| `inout` | `borrow` | **Warning**: declared `inout` but body only reads — consider removing |
| `inout` | `inout` | OK |
| `inout` | `consume` | **Compile error**: body consumes an inout parameter |
| `consume` | `borrow` | **Warning**: declared `consume` but body only reads — consider removing |
| `consume` | `inout` | **Warning**: declared `consume` but body only mutates — consider `inout` |
| `consume` | `consume` | OK |

**Rationale.** The declared mode is the API contract; the inferred mode is what
the body does. Mismatches fall into two groups:
- The body does more than declared (for example, it writes a `borrow`): error,
  because the contract is violated.
- The body does less than declared (for example, `consume` declared but only
  borrowed): warning, because the API is stricter than needed but not unsafe.

**Implications.**
- The inference pass labels each parameter; the type-check pass compares the
  label with any declaration.
- Diagnostics suggest correcting the declaration.

---

### D.042 — No caller-side sigils for `inout`                            [PROPOSED]

**Question.** `10-affine-ownership.md` Q10b (caller-side syntax).

**Decision.** Calls need no sigil. `fill(buf)` looks the same whether `fill`'s
parameter is `borrow`, `inout` or `consume`. The resolved function signature
decides how each argument is treated: declared for public functions, inferred
for private ones.

```a7
buf: [4]u8 = [0, 0, 0, 0]
fill(buf)                            // implicit inout-pass; reads as plain call
```

**Rationale.** Matches Mojo and Hylo: less ceremony at call sites. Users learn
a function's behaviour from its resolved signature, not from per-call marks.
Swift requires `&buf` for `inout`; A7 follows Mojo instead.

**Implications.**
- Parser: no `&` or other sigil is required.
- Public signatures must make each argument's mode easy to see at a glance.
- Tooling and diagnostics must show inferred private signatures.

---

### D.043 — Move analysis: live / partially-moved / consumed             [PROPOSED]

**Question.** `10-affine-ownership.md` Q10c, Q10g.

**Decision.** At every program point, each binding `x` is in one of three
states:

- **Live**: initialised and not consumed; every operation is allowed.
- **Partially moved**: some fields have been consumed. Reading the remaining
  fields is allowed; operations on the whole of `x` are compile errors.
- **Consumed**: `x` has been moved out; any use is a compile error.

The transition table is in
[`parameter-modes.md`](./parameter-modes.md#move-analysis-lattice). Key
transitions:

- `f(consume x)`, or `f(x)` for a non-`Copy` `T` ⇒ `x` becomes consumed.
- `f(inout x)` or `f(borrow x)` ⇒ `x` stays live.
- `del x` ⇒ `x` becomes consumed.
- `y := x.field` for a non-`Copy` field ⇒ `x.field` is partially moved.
- Reassignment `x = new_value` ⇒ `x` is live again (the old value is consumed
  implicitly).

Proposed example:

```a7
b: ref Buf = make_buf()
take(b)                              // b is consumed (ref Buf is not Copy)
take(b)                              // compile error: use of consumed value
b = make_buf()                       // b is live again
take(b)                              // OK
```

**Rationale.** Three states cover the cases without per-field tracking for
`Copy` types, which copy freely. Matches Rust's affine model without
lifetimes, and Hylo's `let` / `sink` / `inout` semantics.

**Implications.**
- A new pass in `a7/passes/` (or an extension of the semantic validator)
  tracks each binding's state through the CFG.
- Use-after-free, double free and use of a moved value are rejected at compile
  time.
- Existing examples with manual `del` must keep working after the pass lands.

---

### D.044 — Call-site exclusivity for `inout` / `borrow`                 [PROPOSED]

**Question.** `10-affine-ownership.md` Q10f.

**Decision.** Within a single call, these are compile errors:

1. two `inout` arguments naming the same value;
2. one `inout` and one `borrow` argument naming the same value;
3. two `inout` arguments naming overlapping field paths
   (`f(inout x.a, inout x)`, where the second covers the first).

Two `borrow` arguments naming the same value are allowed; read-only sharing is
safe.

```a7
swap(x, y)                           // OK if x and y are distinct
swap(x, x)                           // compile error: aliasing
swap(arr[0], arr[1])                 // OK; distinct indices
swap(arr[i], arr[j])                 // compile error unless i != j proved
```

For opaque array or slice indices, the narrowing prover uses the same
machinery as bounds checking. If `i != j` is provable, the call compiles.

**Rationale.** Exclusivity prevents aliasing bugs within a function. Matches
Hylo's call-site rule. The narrowing prover (cluster CD) handles dynamic
indices uniformly.

**Implications.**
- A new check at every call site.
- It uses the narrowing prover (CD) for index-distinctness proofs.

---

### D.045 — `del p` consumes `p`; double-free is compile-time            [PROPOSED]

**Question.** `10-affine-ownership.md` AO-06, AO-08.

**Decision.** `del p` frees a heap allocation. It consumes the binding `p`, so
any later use of `p` is a compile error. A second `del` is therefore a
compile-time "use of consumed value" error.

```a7
p: ref Buf = new Buf{...}
del p
del p                                // compile error: use of consumed value
```

**Rationale.** `del` takes part in the same move analysis as everything else.
This closes double free statically and matches Rust's `drop` semantics.

**Implications.**
- Existing examples with manual `del` work unchanged.
- Codegen for `del p` still calls the allocator's destroy function.

---

### D.046 — Auto-drop at scope exit                                      [PROPOSED]

**Question.** `10-affine-ownership.md` Q10e.

**Decision.** When a non-`Copy` binding leaves scope without being consumed,
the compiler emits `del` at the scope exit.

```a7
process :: fn() {
    p: ref Buf = new Buf{...}
    use(p)
    // implicit `del p` at the closing brace
}
```

The user can still write `del p` to control timing.

`defer del p` (an existing A7 idiom) stays valid. If both an explicit
`defer del` and the implicit drop would apply, the explicit form wins and the
compiler does not free twice.

**Rationale.** Users do not write `del` for every local heap allocation.
Matches Rust's `Drop` and Hylo's scope-exit semantics. The contract holds (no
leaks), and the auto-emit is purely a compile-time codegen feature.

**Implications.**
- A new codegen pass emits `del` at scope exits for live non-`Copy` bindings.
- Auto-drop runs in reverse declaration order (last declared, first dropped),
  as in Rust.

---

### D.047 — `Copy` is compiler-inferred from structure                    [PROPOSED]

**Question.** Implicit from CA D.021 (the `Copy` marker exists).

**Decision.** A type is `Copy` if and only if all its component types are
`Copy`:

- All primitives (`int`, `uint`, `number`, `bool`) are `Copy`.
- `string` is not `Copy`: it owns a heap allocation (A7 strings are UTF-8 byte
  buffers).
- `[N]T` is `Copy` iff `T` is `Copy`.
- `[]T` (slice) is not `Copy`: it borrows backing storage, and copying it would
  create aliasing.
- `ref T` is not `Copy`: reference types track ownership.
- Tagged unions are `Copy` iff every variant payload is `Copy`.
- Structs are `Copy` iff every field is `Copy`.
- Enums without payload are always `Copy`.

Users do not write `Copy` annotations. The compiler infers the property and
reports it in diagnostics when relevant.

Proposed example:

```a7
Point :: struct {
    x: i32
    y: i32
}                                    // Copy: every field is Copy

Holder :: struct {
    data: ref Buf
}                                    // not Copy: ref field
```

**Rationale.** Structural inference, as in Hylo and Mojo, avoids trait
machinery that A7 does not have. The inferred property is stable in practice:
adding a non-`Copy` field to a `Copy` struct silently changes the inference,
but the compiler catches affected uses downstream.

**Implications.**
- The type checker keeps a `Copy` flag per type.
- Generic constraints can name `Copy` through the existing `@type_set`
  vocabulary: `@type_set([Copy])`.

---

### D.048 — Partial moves out of struct fields are allowed                [PROPOSED]

**Question.** `10-affine-ownership.md` AO-25 — AO-28, Q10i.

**Decision.** Moving a value out of a struct field is allowed; the parent
struct becomes partially moved. Accessing the other fields is still allowed.
Using the whole struct (passing it, returning it, and so on) is a compile
error until the moved field is replaced.

```a7
pair := (first: new Buf{...}, second: 42)
extracted := pair.first              // pair is now partially-moved on .first
print(pair.second)                   // OK; .second still live
take(pair)                           // compile error: pair partially moved
pair.first = new Buf{...}            // restores live state
take(pair)                           // OK now
```

**Rationale.** Matches Rust's partial moves; useful for builder patterns and
taking a struct apart field by field. Reassignment restores the state
symmetrically.

**Implications.**
- Move analysis tracks per-field state for non-`Copy` struct fields.
- Diagnostic format: "pair partially moved on field .first; the move happened
  at line N".

---

### D.049 — No storable references; references are parameter-mode only   [PROPOSED]

Not accepted (2026-09-16): see [docs/plan/decisions.md](../plan/decisions.md), L6 scope limit and the memory plan.

**Question.** `10-affine-ownership.md` Q10a.

**Decision.** References exist only as parameter modes. A struct field cannot
have type `borrow T`, `inout T` or `consume T`, and a local variable cannot
hold a borrow. The only reference-like storage is `ref T`, an owning pointer to
a heap allocation.

```a7
Wrapper :: struct {
    r: borrow int                    // compile error: borrow not storable
}

x: int = 5
b: borrow int = x                    // compile error: borrow not a value type
```

**Rationale.** Removes lifetime annotations entirely. Matches the Hylo and Mojo
rule that references appear only at parameters. Storable references would
force the language to encode lifetimes; that is deferred indefinitely.

**Implications.**
- Idioms that store references (callbacks, observers, linked structures) use
  heap-allocated `ref T` instead.
- Linked data structures use indices into an owning container instead of
  self-referential references.

---

## Concurrency

### D.050 — Concurrency model: channels + isolated owned data            [PROPOSED]

**Question.** Earlier user confirmation: channels plus isolated heaps; no
reference capabilities.

**Decision.** Tasks act like actors and communicate through channels:

- Each task has its own stack and, conceptually, its own private heap region.
- Tasks communicate only through channels.
- Values cross channels by move (ownership transfer). No mutable state is
  shared across tasks.
- For `Copy` types, sending looks the same as copying. For non-`Copy` types,
  the sender loses ownership and the receiver gains it.

```a7
ch: Channel<int> = Channel.new<int>(capacity: 16)

go fn() {
    for i := 0; i < 100; i += 1 {
        ch.send(i)
    }
    ch.close()
}()

for value in ch {
    print(value)
}
```

**Rationale.** Combines naturally with affine ownership and needs no new
type-system features (no reference capabilities like Pony's six). Familiar to
Go, Erlang and Inko users, and enough for typical concurrent workloads.

**Implications.**
- Stdlib `Channel<T>` with `.new(capacity)`, `.send(v)`, `.recv() -> ?T`,
  `.close()` and `for v in ch` iteration.
- Runtime support for task scheduling, delegated to Zig's async or a custom
  scheduler (an implementation decision).
- No mutex or lock primitives in v1; without shared mutable state they are not
  needed.

---

### D.051 — Task spawn syntax: `go` keyword                              [PROPOSED]

**Question.** `parameter-modes.md` Q11.

**Decision.** Task spawning follows Go:

```a7
go work(args)                         // spawn task running `work(args)`
go fn() {                             // inline anonymous task
    ...
}()
```

**Rationale.** Short, familiar and readable. Matches Go's goroutines, and the
keyword does not conflict with existing A7 keywords.

**Implications.**
- The tokenizer adds the `go` keyword.
- Codegen lowers `go` to a runtime task-spawn function.

---

### D.052 — Cross-task data crosses by move only; no borrow              [PROPOSED]

**Question.** Implicit from D.050.

**Decision.** Channels accept values only with `consume` semantics. A `borrow`
or `inout` parameter cannot cross a channel or task boundary. References to
data owned by another task are forbidden.

```a7
ch.send(consume p)                   // OK; p is moved into the channel
ch.send(p)                           // same; default mode for non-Copy is consume on cross-task
ch.send(borrow p)                    // compile error: borrow doesn't cross tasks
```

**Rationale.** With no storable references and no shared mutable state, the
only safe channel transfer is a move. This closes data races at the type
level.

**Implications.**
- The type checker rejects `borrow` / `inout` in channel-send positions.
- Channel `recv()` returns owned values.

---

### D.053 — Stack budget applies per task                                 [PROPOSED]

**Question.** `parameter-modes.md` Q12.

**Decision.** The compile-time stack-budget analysis (planned for CE D.062)
applies per task. Each spawned task gets a statically computed stack size, and
the runtime allocates exactly that much stack at spawn.

```a7
work :: fn(items: []int) {
    // budget analyzed at compile time; runtime allocates this much
    ...
}

go work(my_items)
```

**Rationale.** A7 bans recursion, so every task has a bounded stack. The
per-task computation reuses the main task's infrastructure. It removes the
usual "how much stack does this goroutine need?" question; the compiler
answers it.

**Implications.**
- Spawn code reads the callee's computed budget and passes it to the runtime
  stack allocator.
- A task that calls functions exceeding its budget fails to compile, so the
  problem is caught early.

(Audit note: D.062 does not exist yet; cluster CE is pending.)

---

## Cluster CC — summary

**Decisions: 14** (D.040 through D.053; D.041b is a sub-entry of D.041).

Coverage:
- **Default parameter immutability**: D.040 (1)
- **Parameter modes**: D.041–D.042 (2)
- **Move analysis**: D.043–D.048 (6)
- **No storable refs**: D.049 (1)
- **Concurrency**: D.050–D.053 (4)

### What the user sees

User-facing additions:

- Parameter mode keywords `borrow`, `inout` and `consume`.
- `go fn(args) { ... }` task spawn.
- `Channel<T>` stdlib type.
- Move by default for non-`Copy` types in function calls and channel sends.

User-facing rules (compile time):

- Parameters are immutable by default; mutation requires `inout`.
- Calling `f(x)` for a non-`Copy` `T` consumes `x`.
- Reusing a consumed binding is a compile error.
- `del p` consumes `p`; a second `del` is a compile error.
- Bindings not consumed are freed automatically at scope exit.
- Two `inout` arguments to one call must name distinct values.
- References cannot be stored in struct fields or local variables.
- Values cross tasks only by move.

### What the compiler does

- Tracks each binding's state (live / partial / consumed) through the CFG.
- Checks exclusivity at every function call.
- Computes a stack budget per task.
- Emits `del` at scope exits.

---

## Cluster CC status: **PROPOSED**

Review options:

1. **Approve as a whole**: mark all 14 as ACCEPTED and move on to cluster CD
   (flow analysis details).
2. **Amend specific D.NN**: name the decisions to change and how.
3. **Block on something**: point to the decision for more research or
   follow-up questions.

As of 2026-09-16, [the ledger](../plan/decisions.md) records D.040, D.041 and
D.049 as not accepted. The rest of the cluster has no recorded disposition.

---

# Clusters CD through CG — pending

These clusters follow cluster CC's approval. Simplified topics:

- **CD — Flow analysis** (informed by `narrowing.md`): lattice level,
  recognised pattern catalog, invalidation rules, diagnostic format.
- **CE — Numerics specifics** (mostly absorbed into CA): divisor non-zero
  method names and stack-budget policy remain.
- **CF — Modules and metaprogramming** (Ada inspirations): `private` sections,
  hierarchical modules, aspect specifications, profiles, and possibly the
  syntax of the bit-width-warning silencing attribute.
- **CG — FFI boundary and concurrency model commitment**: channels and
  isolated heaps, per the earlier user choice.
