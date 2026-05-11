# A7 Zero-Runtime-Error Decisions Document

> Phase C artifact in the `docs/lang-safety/` research process.
> Each decision answers an open question from `edge-cases/*.md`
> with a rationale citing the relevant Phase B comparative file.
> Decisions accumulate **cluster by cluster** under sequential
> review.

## How to read this file

| Status | Meaning |
| --- | --- |
| **PROPOSED** | I drafted this; awaiting user approval. |
| **ACCEPTED** | User has approved; locked in for Phase D (the spec). |
| **AMENDED**  | User requested changes; the revision is recorded here. |

Decisions are numbered `D.NN` in source order, regardless of
cluster. Cross-references use the same numbers.

## Design directives running through every decision

These came out of the iterative refinement in this conversation:

1. **Zero runtime errors.** The compiler emits Zig that is
   memory-safe under `-O ReleaseFast` (every Zig safety check
   disabled). No `@panic`, `@trap`, or unreachable-at-runtime in
   the emitted code.
2. **Python/JS-feel ergonomics.** The user-facing language reads
   like TypeScript or Swift, not Rust. Method-call surface is
   familiar; type annotations are short.
3. **Best performance.** Native-code performance via the Zig
   backend; the compiler specialises arbitrary-precision numerics
   to machine-word operations whenever it can prove the value
   fits.
4. **Keep the language simple.** Few keywords, few operators.
   When in doubt, push complexity *under the hood* into the type
   checker rather than into user-facing syntax.
5. **Honour the existing A7 spec.** A7 already has `ref T`,
   `nil`, `match`/`case`, slices, generics, `new`/`del`, banned
   recursion, no `unsafe`. The contract additions are minimal
   on top of this; existing keywords stay.

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

This cluster establishes the type-shape primitives: the three
primary numeric types (`int`, `uint`, `number`), the `bool` and
`string` types, the nullability story (`?T` sugar for
`Option<T>`), the fallibility story (`Option`/`Result` + `?`
propagation), and the compiler-internal range-tracking that powers
the contract.

Sources: `edge-cases/02-nullable-pointers.md`,
`edge-cases/06-typed-arithmetic.md`,
`edge-cases/08-option-result.md`,
`edge-cases/09-refinement-lite.md`, plus user direction during
this conversation.

---

## Numeric types

### D.001 — Three primary numeric types: `int`, `uint`, `number`     [ACCEPTED]

**Decision.** The user-facing language has exactly three primary
numeric types:

- **`int`** — mathematical integer; range is whatever memory
  allows. Default literal type for `42`, `-1`, `0`.
- **`uint`** — non-negative integer; same arbitrary precision.
  Default for slice lengths, sizes, indices. Literal suffix `u`
  or context-driven (e.g., `s.length` is `uint`).
- **`number`** — real number with infinite precision. Default
  literal type for `3.14`, `1.0`. No NaN, no inf — those are not
  values of `number`.

Bit-width types (`i8`, `i16`, …, `u64`, `f32`, `f64`) remain in the
language but are **FFI-only**; using them in non-FFI code produces
a compiler warning (D.002).

**Rationale.** Three types covers the typical-program surface
(integer math, size/index math, floating-point math). The bit-width
zoo (`i8` through `u64`, `f32`, `f64`) is a C-ABI concern, not a
user concern. Python ([primary source for "ergonomic numerics"]) has
arbitrary-precision `int` and `float`; JavaScript has `number`
(double-precision IEEE 754 with `BigInt` for large integers); Mojo
has explicit widths. A7 takes the Python/JS direction for
ergonomics, with the bignum-promotion technique borrowed from
LuaJIT and V8.

**Implications.**
- Stdlib provides `int`, `uint`, `number` as built-in types in the
  prelude.
- Most user code never names a bit-width type.
- Numeric literals get inferred types; `42` is `int` by default,
  `3.14` is `number`, `s.length` (a stdlib method) returns `uint`.
- The compiler does range analysis to specialise to native ops
  (D.021).

---

### D.002 — Bit-width types are FFI-only; warning elsewhere         [ACCEPTED]

**Decision.** Bit-width types `i8`, `i16`, `i32`, `i64`, `u8`,
`u16`, `u32`, `u64`, `f32`, `f64` are valid types in A7 but:

- Are **allowed without warning** inside `extern` declarations
  and their immediate caller shims.
- Produce a **compiler warning** ("use `int`/`uint`/`number` unless
  interfacing with foreign code") when used anywhere else.
- The warning can be silenced for a specific declaration via an
  attribute (the exact syntax is a Cluster CF decision).

**Rationale.** Bit-width types are necessary at the FFI boundary
(C ABI requires exact widths). They are footguns elsewhere —
overflow without notice, sign-change surprises, narrow-then-widen
confusion. The warning steers users back to the safe defaults
without making bit-width types unavailable.

**Implications.**
- Lint pass identifies non-FFI bit-width usage.
- Stdlib internals may use bit-width types where layout matters
  (e.g., byte buffers, hash digests); these are exempt via the
  silencing attribute.

---

### D.003 — Arithmetic on `int` / `uint` / `number` never overflows; compiler specialises    [ACCEPTED]

**Decision.** Bare arithmetic (`+`, `-`, `*`) on `int`, `uint`,
`number` is **always defined** at the language level. The compiler
tracks each value's provable range and emits:

- **Native machine-word ops** when the range fits a machine
  integer/float.
- **Transparent bignum-promotion** (one branch in the emitted Zig)
  when the prover cannot rule out overflow.

The user never writes `checked_add`, `wrapping_add`, or
`saturating_add` for `int`/`uint`/`number`. They simply work.

**Rationale.** The Python/Ruby/Lisp/Haskell tradition: arbitrary
precision by default. Combined with the LuaJIT/V8/SBCL technique
of tagged integers + range-driven specialisation, the typical case
pays no runtime cost beyond what fixed-width arithmetic would have
cost. The slow path (genuine large numbers) is opt-in by the
data, not the user.

**Implications.**
- Removes the entire "typed-arithmetic / range-tracking" user
  surface that was Cluster CA's largest design source before this
  refinement. The range tracker still exists internally (it
  powers bounds checking and specialisation), but it is not
  user-visible.
- Hot inner loops with bounded counters compile to native-integer
  speed.
- Code working with large numbers pays the bignum cost
  transparently, equivalent to GMP / MPFR in C.
- For interactive programs reading numbers from input, the
  compiler conservatively allocates bignum storage on first
  arithmetic op; subsequent ops on the same value specialise per
  the range it has acquired.

---

### D.004 — `uint - uint` returns `int` unless `a >= b` is proved   [ACCEPTED]

**Decision.** Subtracting two `uint` values has type `int` by
default, since the result can be negative. When the compiler
proves `a >= b` (via range analysis), the result is `uint`.

**Rationale.** Mathematical semantics. The alternative ("`uint -
uint = ?uint`, may be `none`") is forces user error handling for
a case that is usually statically provable. Widening to `int` is
cleanest. No data is lost because `int` is arbitrary precision.

**Implications.**
- `x: uint = b - a` is a compile error if the compiler can't
  prove `b >= a`; the user either adds the check or assigns to
  `int`.
- `len.checked_sub(off)? ` (returning `?uint`) is the fallback
  method when the user explicitly wants `uint` and is willing to
  handle the failure.

---

### D.005 — Cross-numeric-type comparisons require explicit conversion   [ACCEPTED]

**Decision.** Comparing values of different numeric types
(`int == number`, `uint < int`, etc.) is a compile error. The user
converts explicitly:

```a7
i: int = 5
n: number = 5.0
if cast(number, i) == n { ... }            // OK
if i == n { ... }                          // compile error
```

**Rationale.** Hidden precision loss is a frequent source of
bugs. `int → number` is lossy for large integers; `number → int`
needs to round, which the user should choose
(`.to_int_floor()`, `.to_int_round()`, `.to_int_trunc()`). Explicit
beats implicit.

**Implications.**
- Conversion methods on each type. Cluster CB designs the
  conversion menu in full.
- Comparisons within one type (`int == int`, `number < number`)
  are direct.

---

## bool and string

### D.006 — `bool` is a distinct type with no truthy/falsy conversions   [ACCEPTED]

**Decision.** A7 has `bool` with values `true` and `false`. There
are **no implicit conversions** to/from `bool`:

- `if x:` requires `x: bool`.
- `if x != nil:` works (`x != nil` returns `bool`).
- `if x:` where `x: int` is a compile error.

**Rationale.** Python and JS have truthy/falsy rules that produce
classic bugs (`if list:` is false for empty list; `if 0:` is
false; `if "false":` is true). C's "anything-non-zero is true" is
its own footgun. Forcing an explicit predicate keeps user
intentions visible.

**Implications.**
- Backend lowers `bool` to Zig's `bool`; trivial.
- A common idiom is `if list.length > 0:`, `if x != none:`,
  `if !s.is_empty():` — explicit, not implicit.

---

### D.007 — `string` is UTF-8 text; `.length` is byte count          [ACCEPTED]

**Decision.** A7's `string` is a UTF-8-encoded byte sequence.
Behaviour:

- `s.length` returns `uint` = number of bytes.
- `s.codepoints()` returns an iterator (or slice) of codepoints
  for codepoint-level traversal.
- Indexing `s[i]` returns the byte at offset `i` (`uint`).
- Slicing `s[a..b]` requires byte-aligned indices (compile error
  if proven not on a codepoint boundary; runtime check is **not**
  emitted — the contract forbids it).

**Rationale.** Zig and Rust both go this way: bytes are the
storage unit, codepoint operations are explicit. Python's string
model (codepoint-indexed) is convenient but expensive (O(n) for
indexing, O(1) only because of internal representation
trade-offs). A7 picks performance + explicit codepoint operations.

**Implications.**
- Stdlib `string` has methods: `.length`, `.codepoints()`,
  `.starts_with()`, `.split()`, `.parse_int()`, etc.
- `string + string` concatenation requires allocation; explicit
  via `+` operator overload or `.concat()` method (TBD in stdlib
  design).
- String slicing without alignment proof requires
  `s.try_slice(a, b) -> ?string`.

---

### D.008 — `f"..."` string interpolation                            [ACCEPTED]

**Decision.** A7 supports Python-style f-string interpolation:

```a7
name: string = "world"
msg: string = f"hello {name}, you have {count} items"
```

The compiler parses `f"..."` as a sequence of literal segments and
expressions; lowers to a series of `.concat()` calls at compile
time when all interpolated values' `to_string` representations
are known, otherwise to a runtime concat helper.

**Rationale.** Without f-strings, A7 string handling is verbose
(`s.concat(name).concat(", you have ").concat(...)` style).
Ergonomic essential, no new keyword, single character (`f` prefix
on the literal).

**Implications.**
- Parser change: recognise `f"..."` prefix.
- Each interpolated expression must have a `.to_string()` method
  (provided by stdlib for all built-in types).
- Backend emits Zig's `std.fmt.allocPrint` or equivalent.

---

## Compound types

### D.009 — Array literal `[1, 2, 3]` syntax                          [ACCEPTED]

**Decision.** A7 supports an array literal syntax:

```a7
arr: [3]int = [1, 2, 3]
slice: []int = [1, 2, 3]          // implicit array-to-slice
```

The element type is inferred from contents; the size is the
literal count.

**Rationale.** Matches Python/JS/Swift/Rust syntax. Reads as
expected.

**Implications.**
- Parser change to handle `[...]` literals.
- If the inferred element type doesn't satisfy the target type's
  bound, compile error with a hint.
- Existing A7 syntax `[3]int{1, 2, 3}` (if present) may stay as
  an alternative or be removed; Cluster CF can decide.

---

## Nullability

### D.010 — `?T` is sugar for `Option<T>`                              [ACCEPTED]

**Decision.** The user-facing type `?T` is desugared by the
parser to `Option<T>`. There is one sum-type mechanism in the
language; the sugar is purely a shortened spelling.

**Rationale.** Single mechanism is simpler than two parallel ones.
The Rust experience (`Option<&T>` niche-optimised to one word —
see [`comparative/rust.md`](./comparative/rust.md)) shows the
sugar pays no runtime cost. The Zig backend emits `?*T` for the
niche case automatically (see
[`comparative/zig.md`](./comparative/zig.md)).

**Implications.**
- `?int` ≡ `Option<int>`; `?ref Buf` ≡ `Option<ref Buf>`.
- Pattern matching uses `case some(v)` / `case none`.
- Backend lowers `?ref T` to Zig's `?*T`; `?int` to a tagged
  union; `?number` to a tagged union; etc.

---

### D.011 — Implicit upcast `T → ?T` at assignment / call sites     [ACCEPTED]

**Decision.** Assigning a `T` value to a `?T` location or passing
a `T` to a `?T` parameter is implicit:

```a7
process :: fn(x: ?int) int { ... }
process(5)                              // implicit: 5 wraps to some(5)
y: ?int = 42                            // implicit wrap
```

The explicit `some(5)` constructor remains valid (and required
inside type-ambiguous expression contexts).

**Rationale.** Removes ceremony at upcast sites. Matches Swift's
`T? = T` and Rust's `Option<T>::from(T)` ergonomics, with stricter
discipline (only at assignment-target sites, not arbitrary
expressions, to avoid surprises).

**Implications.**
- Type-checker rule: every `?T` position accepts a `T` silently.
- Backend emits the appropriate `some(...)` constructor in Zig.
- Reverse direction (`?T → T`) is **not** implicit; requires
  `match` or `?` propagation.

---

### D.012 — Generic `$T` over reference types defaults to non-null   [ACCEPTED]

**Decision.** When a generic parameter `$T` is instantiated with a
reference type, the **non-null variant** is the default. To use
nullability inside a generic, the user writes `?$T` explicitly.

**Rationale.** Consistency with the rest of the contract:
non-null by default. If the instantiation is genuinely nullable,
the user passes `?ref Buf` rather than `ref Buf`; the parameter
becomes `?$T` automatically.

**Implications.**
- Generic function code can dereference a `$T` parameter without a
  null check.

---

### D.013 — `nil` is kept as the no-value literal   [REVISED — ACCEPTED]

**Revised decision.** `nil` **remains** the no-value literal —
the existing A7 keyword stays. Per the user's directive that
A7's existing syntax be honoured, the earlier proposal to
remove `nil` in favour of `none` is reverted.

`nil` has type `?Never` and unifies with any `?T`. It is the
canonical spelling of "the absent value." Pattern matching uses
`case nil: { ... }` for the absent case and `case some(v): { ... }`
for the present case. Assignment uses `p: ?int = nil`. Comparison
`p == nil` is allowed for `?T`; comparison against a non-null
`ref T` is a compile error.

**Rationale.** A7's existing spec uses `nil` (visible in
`examples/011_memory.a7`, `examples/013_pointers.a7`). Keeping
the keyword avoids a migration burden and matches the Go / Swift
/ Lua style ("nil as keyword") rather than the Rust / Python
style. The user has explicitly directed that existing A7 syntax
be preserved.

**Implications.**
- Existing `nil` keyword stays in the parser.
- `case nil: { ... }` is the standard "absent" arm in pattern matching.
- No `none` identifier in v1.
- Backend lowering matches current A7 behaviour.

---

### D.014 — Reading from `?T` requires `match` or `?` propagation; smart-narrow through guards    [ACCEPTED]

**Decision.** A `?T` value cannot be used as a `T` directly.
Three ways to extract it:

1. **`match`**: explicit pattern match on `some(v)` and `none`.
2. **`?` propagation** (D.017): `v := expr?` returns the
   enclosing function's failure case if `expr` is `nil`.
3. **Smart-narrow** (Kotlin-style): `if x == nil { ret ... }`
   narrows `x` from `?T` to `T` in subsequent code in the
   enclosing block. Same for early-return shape
   `if x != nil { ... } else { ret ... }`.

There is **no `if let`** construct (Rust-style) and **no `?.`
chaining operator**.

**Rationale.** `match` is the always-available form; smart-narrow
covers the common "guard at top of function" pattern; `?` covers
the "thread errors upward" pattern. Three mechanisms is the
minimum; adding `if let` or `?.` introduces parallel ways to
express the same thing.

**Implications.**
- Type checker tracks narrowed bindings through CFG (Cluster CD
  flow analysis).
- Backend: smart-narrow is purely a static property; the emitted
  Zig has the same shape as a `match` form.

---

### D.015 — `[N]ref T` arrays require explicit initialisation        [ACCEPTED]

**Decision.** Declaring `arr: [N]ref T` without an initialiser is a
compile error. The user must:

1. Provide an array literal: `arr: [3]ref Buf = [p1, p2, p3]`.
2. Or use `[N]?ref T` and assign per-slot later.

**Rationale.** The simplest rule that preserves the non-null
invariant: a non-null array cannot have un-initialised slots.

**Implications.**
- Examples that declare fixed-size non-null reference arrays
  without initialisation (rare) must migrate to one of the two
  forms.

---

## Fallibility

### D.016 — `Option<T>` and `Result<T, E>` are stdlib generic sum types    [ACCEPTED]

**Decision.** Two generic stdlib types:

- `Option<T>` with variants `some(T)` and `none`.
- `Result<T, E>` with variants `ok(T)` and `err(E)`.

Both are exported from the prelude. The error type `E` in
`Result` is **structural** — any type may serve as `E`; there is
no required `Error` trait.

**Rationale.** Standard sum-type shapes; matches Rust, Swift,
Hylo. Structural `E` (no trait requirement) is simpler than
Rust's `From` machinery and is sufficient for v1; if a trait
system lands later, an `Error` trait can be added without
breaking existing `Result` usage.

**Implications.**
- New stdlib modules: `a7/stdlib/option.py`, `a7/stdlib/result.py`.
- The compiler checks exhaustiveness on `match` over `Option` /
  `Result` (existing match-exhaustive infrastructure).

---

### D.017 — `?` postfix propagation operator                          [ACCEPTED]

**Decision.** A7 has a postfix `?` operator. `expr?` desugars to:

- For `expr: Option<T>`: `match expr { case some(v): { v } case
  nil: { ret nil } }`.
- For `expr: Result<T, E>`: `match expr { case ok(v): { v } case
  err(e): { ret err(e) } }`.

The operator is **only allowed** when the enclosing function's
return type matches the propagated variant exactly (same `Option<U>`
shape for `Option<T>?`; same `Result<U, E>` shape with the same
error type `E` for `Result<T, E>?`). There is **no `From`-based
error conversion**.

**Rationale.** The Rust/Swift/Zig ergonomic standard. Without it,
threading `Result<T, E>` values through call chains is impractical.
Strict exact-error-match keeps the rule simple (D.016 already
declared no `From` trait).

**Implications.**
- Parser change: postfix `?` operator.
- Type checker enforces the exact-error-match.
- Backend desugars to the equivalent `match`.

---

### D.018 — No `unwrap()` / `expect()` methods                        [ACCEPTED]

**Decision.** A7's stdlib does **not** provide `.unwrap()` or
`.expect("msg")` methods on `Option` or `Result`. Both would be
runtime traps, which the contract forbids.

**Rationale.** The contract is "zero runtime errors." `unwrap` is
a runtime trap. Refusing to ship the method is the consistent
choice; the user matches explicitly or uses `.unwrap_or(default)`
(total).

**Implications.**
- A common idiom from Rust is unavailable. Diagnostic for
  `.unwrap()` on `Option`/`Result` should suggest `match`,
  `.unwrap_or(...)`, or `?` propagation.

---

### D.019 — Minimal combinator surface in v1: `.map`, `.unwrap_or`    [ACCEPTED]

**Decision.** The stdlib provides **two** combinator methods on
each of `Option<T>` and `Result<T, E>` in v1:

- `Option<T>::map(self, f: fn(T) -> U) -> Option<U>`
- `Option<T>::unwrap_or(self, default: T) -> T`
- `Result<T, E>::map(self, f: fn(T) -> U) -> Result<U, E>`
- `Result<T, E>::unwrap_or(self, default: T) -> T`

Additional combinators (`and_then`, `or_else`, `map_err`,
`filter`, `is_some`, `is_ok`, etc.) are **not** in v1; they are
trivial additions later when concrete need emerges.

**Rationale.** Keep the v1 stdlib surface minimal. The two
provided cover the most common cases; users `match` explicitly
otherwise.

**Implications.**
- Stdlib has 4 methods total across `Option`/`Result`. Documented
  ceiling for v1.
- Diagnostic hint when a user reaches for `.and_then` etc. should
  suggest `match` or note "planned for future."

---

## Compiler-internal (no user-facing surface)

### D.020 — Range analysis is a compiler pass, not a user-facing type system   [ACCEPTED]

**Decision.** The compiler tracks each `int` / `uint` / `number`
value's provable range internally for two purposes:

1. **Specialisation** to native machine ops when range fits a
   machine word (D.003).
2. **Discharging the safety obligations** of D.023 (divisor
   non-zero) and D.024 (index in-bounds).

The user **does not see** refinement types in the language —
no `Bounded<T, lo, hi>`, no `Index<n>`, no `NonZero<T>`. The
range information lives inside the type checker as flow analysis.

**Rationale.** Refinement types as a user-visible feature add a
keyword (`static`), constructor methods, and pattern-binding
ergonomics for what is fundamentally information the compiler can
maintain invisibly. Users write plain `int`; the compiler proves
or disproves the obligations.

**Implications.**
- Whole "refinement-lite type kit" planned earlier is removed
  from the user surface.
- Compiler complexity increases (range tracker becomes
  load-bearing); user-facing complexity decreases.

---

### D.021 — Compiler-inferred `Copy` marker                            [ACCEPTED]

**Decision.** A7 has a built-in compiler-level `Copy` marker that
distinguishes types that may be freely duplicated (numeric types,
bool, enum tags with no payload) from those that have ownership
semantics (heap allocations, types with `del`, references).
`Copy` is **not** a user-facing trait — there is no `impl Copy
for ...` syntax. The compiler infers from structure.

**Rationale.** Cluster CC's affine-ownership story needs to know
which types move and which copy. Inferring from structure is
simpler than user annotations.

**Implications.**
- Each type carries a compiler-tracked `Copy` flag.
- Generic constraints can require `Copy` via the existing
  type-set vocabulary.

---

## Safety obligations preserved by Cluster CA

### D.022 — Division by zero is a compile error                        [ACCEPTED]

**Decision.** Bare `a / b` and `a % b` compile only when the
compiler proves `b != 0`. Otherwise the user:

1. **Adds a guard**: `if b == 0: ... else: ... a / b ... end`
   (the smart-narrow extends to "`b` is non-zero in this branch").
2. **Uses the method form**: `a.checked_div(b)?` returning `?int`
   (or `?uint`, etc.).

The compiler emits the diagnostic with the fix-it suggestion when
rejecting an opaque-divisor `/` or `%`.

**Rationale.** The contract forbids runtime traps. SPARK-tier
discipline (see [`comparative/ada.md`](./comparative/ada.md)) for
the cases where range analysis cannot discharge the obligation.

**Implications.**
- Stdlib provides `.checked_div(b)` and `.checked_mod(b)` on
  numeric types returning the appropriate `?T`.
- Existing A7 examples and tests with bare division by an opaque
  divisor get a one-time rewrite to use either the guard or
  the method.

---

### D.023 — Slice/array out-of-bounds is a compile error               [ACCEPTED]

**Decision.** Bare `s[i]` compiles only when the compiler proves
`i < s.length`. Otherwise the user:

1. **Uses a recognised loop pattern** (`for i in 0..s.length:
   s[i]`) — the compiler proves the bound.
2. **Adds an explicit guard**: `if i < s.length: ... s[i] ...
   else: ... end`.
3. **Uses the method form**: `s.get(i)?` returning `?T`.

The compiler emits a diagnostic with the fix-it suggestion.

**Rationale.** Same as D.022. The proof patterns mirror
[`comparative/ada-deep-dive.md`](./comparative/ada-deep-dive.md)
§7's `'Range` attribute and `Index<n>` discipline, but expressed
as flow analysis rather than user-visible types.

**Implications.**
- Stdlib provides `.get(i)` on every indexable type.
- Range tracker (D.020) sees through the recognised patterns and
  through smart-narrow guards.

---

## Cluster CA — summary

**Decisions: 23.** (D.001 through D.023.)

Coverage:
- **Numeric vocabulary**: D.001 — D.005 (5)
- **bool and string**: D.006 — D.008 (3)
- **Compound types and literals**: D.009 (1)
- **Nullability**: D.010 — D.015 (6)
- **Fallibility**: D.016 — D.019 (4)
- **Compiler-internal**: D.020 — D.021 (2)
- **Safety obligations**: D.022 — D.023 (2)

### What the user sees vs. what the compiler does

User-facing additions (compared to current A7):

- Three primary numeric types `int` / `uint` / `number` (existing
  bit-width types become FFI-only with warnings).
- `?T` type prefix sugar (one new operator character).
- `?` postfix propagation (same character, different position).
- `Option<T>` and `Result<T, E>` stdlib generics.
- `none` stdlib identifier (replaces `nil` keyword).
- `f"..."` string interpolation (one new literal prefix).
- `[1, 2, 3]` array literal syntax.

What's removed from prior proposals:
- `nil` keyword (D.013).
- `Bounded`, `Index`, `NonZero`, `Fin`, etc. refinement types
  (D.020).
- `static` keyword (no longer needed without refinement types).
- `newtype` keyword (Ada distinct types — deferred indefinitely).
- `?.`, `?[]`, `??` chaining operators.
- `if let` construct.
- `Default` / `From` traits.
- `unwrap()` / `expect()` methods.
- General trait system.

Compiler-internal complexity (increased to compensate):
- Range tracker on `int` / `uint` / `number` for specialisation
  and safety-obligation discharge.
- Smart-narrow analysis through `if x == none:`, `if i <
  s.length:`, etc.
- Bignum-promotion code-emission discipline (transparent to the
  user; appears in the emitted Zig as one branch per arithmetic
  op when the compiler can't prove the range).

---

## Cluster CA status: **ACCEPTED**

All 23 decisions approved. Source of truth for Phase D (the spec).

---

# Cluster CB — Cast and conversions

This cluster decides the shape of all conversions in A7:
numeric (`int ↔ uint ↔ number`), string (parse, format),
boolean, reference (already covered by CA), array/slice,
enum/discriminant, and FFI bit-width.

Sources: `edge-cases/01-cast.md`,
[`conversions.md`](./conversions.md) (the deep-research input
written for this cluster), and the existing comparative files in
`comparative/`.

Direction (from `conversions.md`):

- **Method-style** is the conversion shape — no new operator
  keyword.
- **Fallible conversions return `?T`** — consistent with CA.
- **No `cast(T, x)` operator** — the existing audit-flagged hole
  is closed.
- **No `bit_cast` operator** — stdlib helpers cover the few
  cases.
- **Narrowing eliminates runtime checks** — the central
  performance insight; conversion checks compile away when the
  prover discharges them.

---

### D.024 — `cast(T, x)` is the universal conversion operator       [ACCEPTED]

**Question.** `01-cast.md` Q01a — the shape of the cast surface.

**Decision.** All A7 conversions use the **`cast(T, x)`
operator**, which is A7's existing syntax. The operator is
restricted to safe conversions per D.025: it returns the direct
type `T` when the precondition is statically discharged;
returns `?T` when the failure is genuinely data-dependent;
compile error when the precondition is statically resolvable
but not discharged; hard compile error for forbidden casts
(int↔ptr).

```a7
x: int = 5
y: uint = cast(uint, x)          // compile error: x may be negative
z: number = cast(number, x)      // infallible (lossless)
s: string = cast(string, x)      // infallible (format)
n: ?int = cast(int, "42")        // ?int — parsing is data-dependent
```

There is **no `as T` operator** and no `int(x)` constructor
form. One uniform shape: `cast(T, x)`.

Method-style operations like `n.floor()`, `n.ceil()`,
`n.round()`, `n.trunc()` on `number` still exist — they're
**operations on `number`** that return `number` (rounded), not
conversions. The user combines them: `cast(int, n.floor())`.

**Rationale.** The user has directed that the existing A7
`cast()` syntax be preserved. The remedy for the audit's most
urgent finding (`07-language-review.md` §1.2) is to **restrict**
`cast()` to safe conversions rather than remove it.

**Implications.**
- The existing `cast(T, x)` syntax stays in the parser.
- The cast classifier (per D.037) decides per `(source, target)`
  pair whether the cast is allowed, fallible (returns `?T`),
  or forbidden.
- The audit's `INVALID_CAST` and `UNSAFE_CAST` error types are
  promoted from declared-but-unused to actually-emitted.

---

### D.025 — Statically-resolvable failures compile-error; only data-dependent failures return `?T`   [ACCEPTED]

**Question.** `01-cast.md` Q01b, revised after user direction.

**Decision.** Operations divide into two categories:

| Category | Examples | Return type | Failure handling |
| --- | --- | --- | --- |
| **Statically resolvable** | `a / b`, `s[i]`, `x.to_uint()`, `n.to_int_floor()`, `[N]T::from(s)`, `EnumT::from_discriminant(i)` | the direct type (`int`, `uint`, `[N]T`, `EnumT`, etc.) | Compile error if the prover can't discharge the obligation; user adds a guard |
| **Data-dependent** | `s.parse_int()`, `new T{...}`, `read_line()`, `extern fn` returns | `?T` or `Result<T, E>` | User matches, propagates with `?`, or uses `.unwrap_or(default)` |

The key principle: **a method returns `?T` only when the failure
cannot be statically discharged by the prover.** Conversions
between known types (where the prover knows the source's range)
do not return `?T` — they return the direct type and emit a
compile error when the user hasn't established the preconditions.

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

**Rationale.** The previous draft of this decision made every
conversion return `?T`, which forces Rust-style `?`-everywhere
boilerplate. The revised principle says: if the compiler *can*
know whether the operation will succeed (via narrowing), make it
return the direct type and force the user to establish the
precondition. The user writes plain code; the compiler enforces.
Matches the Python/Go/JS ergonomic target while keeping the
zero-runtime-error contract.

**Implications.**
- Most conversions return their direct type, not `?T`.
- `?T` survives for: parsing, allocation, I/O, FFI returns,
  and the few cases where the failure is genuinely data-dependent
  (e.g., `to_int_exact()` — "is this number an integer?" depends
  on the value at runtime).
- Compile errors carry fix-it suggestions naming the right guard
  pattern (per D.037).
- The narrowing system (`narrowing.md`) is no longer
  "optional optimisation" but **mandatory** for category-1
  operations — without it the program doesn't compile (see D.039).

---

### D.026 — The numeric conversion method catalog                  [ACCEPTED]

**Question.** Implicit from the user-facing numeric surface.

**Decision.** The complete cross-conversion menu for the three
primary numeric types. Every method returns the **direct type**
— never `?T`. When the prover cannot discharge the precondition,
the call is a compile error.

| Source | Target | Method | Returns | Precondition (must be discharged or compile error) |
| --- | --- | --- | --- | --- |
| `int` | `uint` | `.to_uint()` | `uint` | `x >= 0` |
| `int` | `number` | `.to_number()` | `number` | none (always succeeds) |
| `uint` | `int` | `.to_int()` | `int` | none |
| `uint` | `number` | `.to_number()` | `number` | none |
| `number` | `int` | (4 methods — see D.027) | `int` | varies |
| `number` | `uint` | (4 methods — see D.027) | `uint` | `n >= 0` (where applicable) |

Identity conversions (`int → int`, etc.) are not methods; they
are no-ops (the type system accepts the value directly).

**Rationale.** Per D.025: statically-resolvable failures return
the direct type and force a compile-error if the precondition
isn't discharged. The user writes plain code; the compiler
enforces the guard.

**Implications.**
- Stdlib defines six methods on each numeric type.
- No `?T` return on conversions — eliminates Rust-style
  `?` boilerplate.
- Compile errors carry fix-it suggestions (D.037).
- Narrowing (D.039) is what makes the methods usable — the
  prover discharges the preconditions for typical code patterns.

---

### D.027 — `number → int` / `uint` rounding methods               [ACCEPTED]

**Question.** Implicit from CA D.001 plus rounding-policy design.

**Decision.** Four methods on `number` for each integer target:

| Method | Semantics |
| --- | --- |
| `.to_int_trunc() -> int` | Round toward zero |
| `.to_int_floor() -> int` | Round toward `-∞` |
| `.to_int_round() -> int` | Round half to even (banker's) |
| `.to_int_exact() -> ?int` | None unless `n` is mathematically an integer (data-dependent) |

For `to_uint_*` variants — same shape with one extra
precondition: `n >= 0`. The compiler enforces it.

| Method | Return | Compile-time precondition |
| --- | --- | --- |
| `.to_uint_trunc()` | `uint` | `n >= 0` (data-dependent → compile error if not proved) |
| `.to_uint_floor()` | `uint` | `n >= 0` |
| `.to_uint_round()` | `uint` | `n >= 0` |
| `.to_uint_exact()` | `?uint` | none (returns none if not exact OR negative) |

Per D.025: the `_trunc`, `_floor`, `_round` variants return the
direct type and fail compilation if the prover can't discharge
the `n >= 0` precondition. The `_exact` variants return `?T`
because integrality is genuinely runtime-data-dependent.

**Rationale.** Explicit rounding modes are self-documenting. The
Python `int(x)` default-truncate is convenient but hides the
mode; A7 makes the user pick. Four modes cover every practical
need. The `?T` shape is reserved for the genuinely
data-dependent case (`_exact`).

**Implications.**
- Eight methods on `number` (four `to_int_*` + four `to_uint_*`).
- Six of the eight return direct types (`int` / `uint`); two
  return `?int` / `?uint` (the exact variants).
- A user calling `n.to_uint_floor()` with an opaque `n` gets a
  compile error suggesting `if n >= 0: ... else: ... end` or
  using `n.to_uint_exact()` to handle both failure modes
  uniformly.

---

### D.028 — String formatting via `.to_string()` and `.format(spec)`   [ACCEPTED]

**Question.** Implicit — needed for `f"..."` interpolation and
general formatting.

**Decision.** Every built-in type provides `.to_string()`. For
formatted output, `.format(spec)` takes a stdlib format-spec
string. Exact format-spec syntax is a stdlib detail (TBD;
Python-style `:0.4f` is the working assumption).

**Rationale.** Two-method surface. Default-format covers 90 % of
cases (used implicitly by `f"..."` per CA D.008); formatted
output for the rest.

**Implications.**
- Stdlib has `.to_string()` on each built-in type.
- Format-spec language designed during stdlib work, not in this
  decision.

---

### D.029 — String parsing methods                                  [ACCEPTED]

**Question.** Implicit from CA D.007 (string has `.parse_int()`).

**Decision.** `string` provides:

- `s.parse_int() -> ?int` — decimal parse, returns none for any
  invalid input
- `s.parse_uint() -> ?uint` — decimal, fails for invalid or
  negative
- `s.parse_number() -> ?number` — decimal point, scientific
  notation
- `s.parse_bool() -> ?bool` — exactly `"true"` or `"false"`,
  case-sensitive

For radix parsing: `s.parse_int_radix(r: uint) -> ?int` where
`r ∈ [2, 36]`.

**Rationale.** Five methods covers the typical surface. Richer
parsing is user code.

**Implications.**
- Five stdlib methods.
- Whitespace handling is **not** built in (user calls `.trim()`
  first); avoids hidden behaviour.

---

### D.030 — `bool ↔ numeric` conversions are forbidden              [ACCEPTED]

**Question.** Implicit from CA D.006 (no truthy/falsy).

**Decision.** No `.to_int()` on `bool`; no `.to_bool()` on
`int`/`uint`/`number`. Users wanting numeric-from-bool write
`if b: 1 else: 0 end` explicitly.

**Rationale.** Numeric / boolean conflation is a footgun. The
explicit `if`-expression is one extra character.

**Implications.**
- Stdlib does not define these methods.
- Diagnostic when a user attempts `b.to_int()` suggests the
  explicit form.

---

### D.031 — Array → slice implicit; slice → array compile-error if length not proved   [ACCEPTED]

**Question.** `01-cast.md` C-25, C-26.

**Decision.** `[N]T → []T` is an **implicit upcast** (no method
call needed). `[]T → [N]T` is **statically resolvable** per
D.025: the method `[N]T::from(s)` returns `[N]T` directly when
the compiler proves `s.length == N`; compile error otherwise.

```a7
arr: [3]int = [1, 2, 3]
s: []int = arr                          // implicit array-to-slice

s2: []int = read_slice()                // opaque length
a2: [3]int = cast([3]int, s2)           // compile error: s2.length not proved == 3

if s2.length == 3 {
    a2: [3]int = cast([3]int, s2)       // OK; narrowed
}
```

There is no `try_from` returning `?[N]T` in v1 — converting a
runtime-length slice to a fixed-size array is uncommon enough
that forcing the guard is fine; if practice shows it's painful,
a fallible variant can be added later.

**Rationale.** D.025 principle: no `?T` for statically
resolvable failures. The slice-to-array conversion's failure
mode is "length doesn't match" — exactly the kind of obligation
the prover should discharge.

**Implications.**
- Type checker accepts `[N]T` where `[]T` is expected; auto-emit
  the slicing.
- `[N]T::from(s)` is a static-prove-or-compile-error method,
  not a fallible one.
- Narrowing through `if s.length == N:` discharges the
  obligation inside the branch.

---

### D.032 — Enum discriminant conversion                             [ACCEPTED]

**Question.** `01-cast.md` Q01d (C-22, C-23, C-24).

**Decision.** Enums expose two methods:

- `e.discriminant() -> int` — always succeeds; extracts the
  discriminant value (default sequential from 0, or as declared).
- `EnumT::from_discriminant(i: int) -> EnumT` — returns the
  enum variant directly. **Compile error** if `i` isn't
  range-proved to match a valid discriminant.

For data-dependent discriminants (parsed input, FFI), the user
uses an explicit `match` or guard:

```a7
raw: int = parse_disc()?                   // opaque after parse
v: Color = cast(Color, raw)                // compile error: raw not proved valid

// with guard:
match raw {
    case 0..=2: { v: Color = cast(Color, raw) }   // OK; range-proved
    else: { ret nil }
}
```

Cross-enum casts (`EnumA → EnumB`) are forbidden; the user must
go through the discriminant.

**Rationale.** D.025 principle. The discriminant-to-enum
conversion's failure mode (invalid discriminant) is statically
resolvable when the source is range-proved; the prover discharges
in those cases. For genuinely-data-dependent cases (parsing),
the user writes a `match` on the int, which the narrowing
system uses to discharge the call in each arm.

**Implications.**
- Every enum type gains these two methods automatically.
- The user wraps `from_discriminant` in a guard for
  parsing-style data flow.
- Diagnostic for the unguarded call suggests the `match`
  pattern.

---

### D.033 — FFI bit-width conversions inside extern shims          [ACCEPTED]

**Question.** `01-cast.md` C-29.

**Decision.** Inside an `extern fn` declaration's caller shim
(the function wrapping the foreign call), bit-width types
(`i32`, `u64`, etc.) are first-class without warning (per CA
D.002's exemption). Conversions follow D.025: direct return type
with compile-error-when-unproved.

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

Inverse direction `int → i32` requires the prover to discharge
the range fit:

```a7
write_count :: fn(n: int) {
    if n > 2147483647 {
        ret                              // or handle overflow
    }
    raw: i32 = cast(i32, n)              // OK; n proved in i32 range
    c_set_count(raw)
}
```

**Rationale.** Same shape as primary-type conversions (D.026).
The narrowing system discharges typical FFI conversions where
the user has guarded; opaque conversions get compile errors
with fix-it suggestions.

**Implications.**
- Bit-width types are valid `cast()` source and target types in
  FFI-shim contexts: `cast(int, raw_i32)`, `cast(i32, n: int)`
  etc.
- Inverse direction (`int → i32`, etc.) requires range proof;
  compile error otherwise.
- FFI **return values** from `extern fn` are declared with
  `?T` or `Result<T, E>` based on what the foreign function
  promises; that's a data-dependent failure mode.

---

### D.034 — No `bit_cast` operator; stdlib helpers cover the cases   [ACCEPTED]

**Question.** `01-cast.md` Q01c.

**Decision.** A7 has no `bit_cast` keyword or operator. For the
small closed set of bit-pattern reinterpretation needs, stdlib
provides explicit helpers:

| Method | Use case |
| --- | --- |
| `f32.bits() -> u32` | Float-to-int bit extraction (hashing) |
| `f64.bits() -> u64` | Same for 64-bit |
| `u32.as_f32() -> f32` | Construct float from bits |
| `u64.as_f64() -> f64` | Same |

All four require bit-width source/target types, so they're only
available inside FFI-shim contexts or with explicit annotation
silencing.

**Rationale.** Audit Q01c's first option (yes-restricted) lets
users reinterpret arbitrary same-size non-pointer values, which
is mostly unused and a footgun. Closing it to four named
helpers covers the real cases without ambiguity.

**Implications.**
- No `bit_cast` keyword in the parser.
- Four stdlib methods, in FFI / bit-twiddling scope.

---

### D.035 — Compile-time literal conversion has no runtime cost     [ACCEPTED]

**Question.** `01-cast.md` Q01h.

**Decision.** Numeric literals carry **comptime-known values**.
Converting a literal to any compatible numeric target happens at
compile time with range-check at compile time; no runtime code
is emitted. Same for arithmetic among literals.

```a7
x: int = 42                // literal, comptime int
y: uint = 42               // literal fits uint; compile-time conversion
z: number = 42             // lossless embedding
n: uint = 10 * 5           // comptime 50; fits uint
bad: uint = -5             // compile error: -5 doesn't fit uint
```

**Rationale.** Matches Zig's `comptime_int` semantics. Hugely
ergonomic — the user writes plain integer literals everywhere.

**Implications.**
- Constant-folding pass (existing in A7) recognises literal
  conversions and emits the target-type value directly.
- The user never writes `.to_T()` for a literal.

---

### D.036 — Generic-context conversion: per-instantiation            [ACCEPTED]

**Question.** `01-cast.md` Q01g + C-28.

**Decision.** `cast()` invocations inside generic code are
checked **per instantiation**. If a generic function calls
`cast(int, x)` where `x: $T`, each concrete instantiation of `$T`
must support the conversion (or satisfy a type-set constraint
that promises one).

```a7
double_then_int :: fn($T: @type_set([CastableToInt]), x: $T) int {
    ret cast(int, x) * 2
}
```

Without the type-set constraint, the generic call is a compile
error at the declaration site (no instantiation can prove the
conversion is supported generically).

**Rationale.** Matches the existing A7 generics infrastructure
(`@type_set(...)`). Type-set constraints already serve this
purpose; the conversion methods just become additional
predicates in the vocabulary.

**Implications.**
- Stdlib type-sets: `CastableToInt`, `CastableToUint`,
  `CastableToString`, etc. for common conversions.
- Per-instantiation checking adds no new infrastructure (the
  existing pass already covers it).

---

### D.037 — Forbidden-conversion diagnostics with fix-it suggestions   [ACCEPTED]

**Question.** `01-cast.md` Q01g.

**Decision.** When a user attempts a forbidden conversion, the
diagnostic must:

1. Name the source and target types explicitly.
2. Suggest the right method-call alternative.
3. Where applicable, suggest a guard pattern that would discharge
   the obligation.

Concrete example:

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

No `?T` form is suggested in v1: D.025 says `to_uint()` returns
`uint` directly. The diagnostic guides the user toward the guard
pattern; the narrowing system then discharges the call.

The existing `INVALID_CAST` and `UNSAFE_CAST` error types
(currently declared-but-unused at `a7/errors.py:148-149`) are
promoted to actually-emitted.

**Rationale.** The diagnostic is the user-visible interface of
the safety contract. Excellent suggestions teach the discipline.

**Implications.**
- Error-emission table maps (source-type, target-type) tuples
  to fix-it strings.
- One-time investment; pays off across the entire example suite
  and user code.

---

### D.038 — The `cast(T, x)` operator is removed                     [ACCEPTED]

**Question.** `01-cast.md` Q01f.

**Decision.** The existing A7 `cast(T, x)` syntax is **removed
from the language**. No grace period, no deprecation flag —
clean break. Existing uses get a compile error with a fix-it
suggesting the appropriate `.to_T()` method.

**Rationale.** The audit (`07-language-review.md` §1.2) found
this is the most urgent safety hole — `cast(ref T, integer)`
compiles today. A clean removal closes the hole atomically.
The migration is small (a handful of uses in the existing
example suite per the audit).

**Implications.**
- Parser removes `cast` as a keyword/operator.
- Existing examples that use `cast(T, x)` get a one-time
  rewrite to the appropriate method call.
- `docs/SPEC.md` removes the cast section.

---

### D.039 — Narrowing is the only mechanism that makes statically-resolvable operations callable   [ACCEPTED]

**Question.** Implicit from D.025 and the narrowing system
documented in `narrowing.md`.

**Decision.** For every operation whose failure mode is
**statically resolvable** (per D.025) — division `a / b`,
indexing `s[i]`, conversions like `x.to_uint()`,
`n.to_int_floor()`, `[N]T::from(s)`, `EnumT::from_discriminant(i)`,
etc. — **the narrowing analysis is mandatory**:

- If the prover discharges the operation's precondition at the
  call site, the compiler emits a bare op. No runtime check.
- If the prover cannot discharge, the call **does not compile**.
  Compile error with fix-it suggesting the appropriate guard.

This is **not** "narrowing optimises away runtime checks." It is
"narrowing is the only way the operation reaches code generation
at all." Without narrowing, the user's program doesn't compile.

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

Compare what happens without the guard:

```a7
process_bad :: fn(s: []int, i: int) int {
    idx := cast(uint, i)              // compile error: `i` may be negative
                                       // help: guard with `if i < 0 { ret ... }`
    ret s[idx]                         // (this line never compiles)
}
```

The user never picks between "fast" and "safe" emission. They
write the obvious code; the compiler either accepts it (prover
discharged) or rejects it (with fix-it). The Zig output has no
`@panic`, no `unreachable`, no implicit safety check.

**Rationale.** This is **the** load-bearing principle of A7's
zero-runtime-error contract. Statically-resolvable operations
become a single unified mechanism: the type checker enforces
the precondition; the emitter assumes it. No two codegen paths
per method, no `?T`-everywhere boilerplate, no runtime traps.

**Implications.**
- D.025–D.027, D.031–D.033 all delegate their precondition
  discharge to the narrowing system.
- The narrowing system (Cluster CD locks in details) is a
  **required v1 feature**, not an optimisation that can be
  shipped later.
- The no-trap codegen test (per `05-for-a7.md` §4.8.13) is the
  operational verification: any code path that compiles must
  emit safe Zig under `-O ReleaseFast`.
- Implementation: each conversion / division / index method has
  **one** codegen path (bare op). The "fallible" shape exists
  only for data-dependent operations (parsing, I/O, allocation,
  FFI returns), which always emit the `if` form.

---

## Cluster CB — summary

**Decisions: 16.** (D.024 through D.039.)

Coverage:
- **Conversion shape**: D.024 — D.025 (2)
- **Numeric method catalog**: D.026 — D.027 (2)
- **String I/O**: D.028 — D.029 (2)
- **Bool isolation**: D.030 (1)
- **Compound conversions**: D.031 — D.032 (2)
- **FFI conversions**: D.033 (1)
- **No `bit_cast`**: D.034 (1)
- **Compile-time + generics**: D.035 — D.036 (2)
- **Diagnostics + migration**: D.037 — D.038 (2)
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

The `?T` surface is now small: only **data-dependent**
operations return option-shaped results. Statically-resolvable
operations return direct types and emit compile errors when
preconditions aren't discharged.

### What the user sees (compared to A7 today)

Additions:
- Conversion methods on numeric / string / bool / FFI types.
- `[N]T::from(s)` for slice-to-array.
- `.discriminant()` and `EnumT::from_discriminant(i)`.
- `f32.bits()` and friends (bit-twiddling helpers, FFI scope).

Removals:
- The `cast(T, x)` operator. Closes the audit's most urgent
  finding.

Compiler-internal complexity (no user-visible change):
- Mandatory narrowing-driven check discharge per D.039.
- Forbidden-conversion diagnostic table per D.037.

---

## Cluster CB status: **ACCEPTED**

All 16 decisions are marked accepted in the cluster index. This section is
accepted, but D.024 and D.038 still require the explicit Q2 resolution tracked
in `HANDOFF.md`: keep the hybrid `cast()` boundary or remove `cast()`
entirely. Until that Q2 edit lands, the accepted cluster still contains a known
internal contradiction.

---

# Cluster CC — Ownership and parameter modes

This cluster defines A7's parameter-passing modes, the move
analysis underlying ownership safety, and the channel/task
primitives that compose with ownership for concurrency.

Sources: `edge-cases/10-affine-ownership.md`,
[`parameter-modes.md`](./parameter-modes.md) (deep-research
input written for this cluster), `comparative/hylo.md`,
`comparative/swift.md`, `comparative/inko-koka-verona.md`.

Direction (from `parameter-modes.md`):

- **Function parameters are immutable by default** (Odin / Zig
  style).
- **Three parameter modes** exist (`borrow`, `inout`, `consume`)
  but are **inferred from the function body** — the user
  writes plain `fn(args)` declarations; the compiler decides
  per parameter. Keywords remain available for explicit
  contracts at API boundaries.
- **No caller-side sigils** (Mojo style); the function
  signature + IDE tooling tell the reader what each argument
  does.
- **References exist only as parameter modes**, never as
  storable values. No lifetime annotations.
- **Move analysis** at compile time: each binding is live /
  partially-moved / consumed. Re-use of a consumed binding is
  a compile error.
- **Concurrency**: channels + isolated owned data. No shared
  mutable state across tasks. Move semantics on channel send.

---

### D.040 — Function parameters are immutable by default               [PROPOSED]

**Question.** Implicit from user direction ("function params are
immutable like Zig and Odin").

**Decision.** All function parameters are **immutable** within
the function body unless declared `inout` or `consume`. The
default mode is **read-only** (equivalent to the explicit
`borrow` keyword). Mutating the parameter binding directly is
a compile error.

```a7
process :: fn(x: int, s: []u8) {
    x = 10                          // compile error: x is immutable
    s[0] = 0                        // compile error: s is borrow
}
```

To mutate at the call site, the function must declare the
parameter `inout`:

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

**Rationale.** Matches Odin's "all proc parameters are
immutable" model. Removes a common footgun (silently mutating a
parameter and the caller not seeing the effect). Forces the
function signature to declare its intent explicitly.

**Implications.**
- Parser change: parameter mutability is determined by mode
  keyword.
- Type checker rejects parameter reassignments unless
  `inout`/`consume`.
- Codegen: parameters lower to `const` Zig locals by default.

---

### D.041 — Parameter modes are explicit at public boundaries and inferred privately  [REVISED — PROPOSED]

**Question.** `10-affine-ownership.md` Q10a, Q10b. Revised after
user direction ("the user shouldn't need to write all these
stuff; the compiler should be doing the checking").

**Decision.** A7 has **three parameter modes** (`borrow`,
`inout`, `consume`). Public/API-boundary functions require
explicit parameter modes in their signatures. Private functions
may omit mode keywords; the compiler infers each omitted mode
from the function body.

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

The inference algorithm walks the function body and assigns
the maximum of the use-lattice:
**`borrow` < `inout` < `consume`**.

- If any `del` or `consume`-positioned use → `consume`.
- Else if any write or `inout`-positioned use → `inout`.
- Else (only reads) → `borrow`.

The keywords `borrow`, `inout`, `consume` are required for:
- **Public functions** where the signature is the durable API contract.
- **Cross-module signatures** where the body may be unavailable.
- **Public generic functions** where each instantiation may impose different
  pressure and the mode must be named.

Private functions may still write modes explicitly when the author wants a
local contract. The compiler checks that the body matches the declared mode.

If a declared mode doesn't match the inferred mode, the
compiler reports a discrepancy (warning or error — see D.041b).

**Rationale.** The user has directed that the language be as
simple to use as Python/Go/JS. For private functions, explicit
parameter modes are ceremony that the compiler can supply. For
public functions, body-inferred modes break separate compilation
and make API contracts unstable. The split keeps local ergonomics
while preserving a readable, durable interface at module
boundaries.

**Implications.**
- The parser accepts parameter declarations both with and without mode keywords,
  but rejects omitted modes on public functions and public generic functions.
- A new compiler pass (or extension of the move-analysis pass
  in D.043) infers each parameter's mode from the body.
- Tooling (`a7 --show-types`) displays inferred modes so users
  can verify the compiler's choice.
- Cross-module signatures encode explicit public modes and inferred private
  modes in the module's interface (binary or AST representation).
- Callers always see the (inferred or declared) mode for
  exclusivity checks per D.044.

---

### D.041b — Inferred mode vs declared mode discrepancies         [PROPOSED]

**Decision.** When the user writes a parameter mode
explicitly and the inferred mode is different:

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

**Rationale.** The declared mode is the API contract; the
inferred mode is what the body actually does. Discrepancies
fall into two categories:
- Body too strong for the declaration (writes a `borrow`) →
  error; the contract is violated.
- Body too weak for the declaration (`consume` declared but
  body only borrows) → warning; the API may be more
  restrictive than needed, but it's not unsafe.

**Implications.**
- The mode-inference pass produces a label per parameter; the
  type-check pass compares to the declaration if any.
- Diagnostics suggest correcting the declaration.

---

### D.042 — No caller-side sigils for `inout`                            [PROPOSED]

**Question.** `10-affine-ownership.md` Q10b (caller-side syntax).

**Decision.** Calls do **not** require a sigil at the call
site. `fill(buf)` looks the same whether `fill`'s parameter is
`borrow`, `inout`, or `consume`. The resolved function signature
is the source of truth for how each argument is treated: explicitly
declared for public/API-boundary functions, compiler-inferred for
private functions.

```a7
buf: [4]u8 = [0, 0, 0, 0]
fill(buf)                            // implicit inout-pass; reads as plain call
```

**Rationale.** Matches Mojo / Hylo. Cleaner syntax; less
ceremony at call sites. Users learn each function's behaviour
from its resolved signature, not from per-call decorations. Swift
requires `&buf` for `inout`; A7 follows Mojo's cleaner choice.

**Implications.**
- Parser change: no `&` or other sigil required.
- Public function signatures must be syntactically obvious enough that a reader
  can identify each argument's mode from a quick scan.
- Private inferred signatures must be visible through tooling and diagnostics.

---

### D.043 — Move analysis: live / partially-moved / consumed             [PROPOSED]

**Question.** `10-affine-ownership.md` Q10c, Q10g.

**Decision.** Each binding `x` is in one of three states at any
program point:

- **Live**: `x` is initialised and not consumed; all operations
  permitted.
- **Partially moved**: some fields of `x` have been consumed;
  reading non-consumed fields is allowed; full-`x` operations
  are compile errors.
- **Consumed**: `x` has been moved out; any use is a compile
  error.

State transitions follow the table in
[`parameter-modes.md`](./parameter-modes.md#move-analysis-lattice).
Key transitions:

- `f(consume x)` or `f(x)` for non-`Copy` `T` ⇒ `x` becomes
  consumed.
- `f(inout x)` or `f(borrow x)` ⇒ `x` stays live.
- `del x` ⇒ `x` becomes consumed.
- `y := x.field` for non-`Copy` field ⇒ `x.field` partially-moved.
- Re-assignment `x = new_value` ⇒ `x` returns to live (old
  value consumed implicitly).

**Rationale.** Three-state lattice covers the cases without
introducing per-field tracking for `Copy` types (which copy
freely). Matches Rust's affine model minus lifetimes; matches
Hylo's `let`/`sink`/`inout` semantics.

**Implications.**
- New pass in `a7/passes/` (or extension of the existing
  semantic validator) maintains per-binding state through CFG.
- Compile-time UAF, double-free, and use-of-moved-value
  rejection.
- Existing examples using manual `del` must work after the
  pass lands.

---

### D.044 — Call-site exclusivity for `inout` / `borrow`                 [PROPOSED]

**Question.** `10-affine-ownership.md` Q10f.

**Decision.** At any single call, the following are compile
errors:

1. Two `inout` arguments naming the same value.
2. One `inout` and one `borrow` argument naming the same value.
3. Two `inout` arguments naming overlapping field paths
   (`f(inout x.a, inout x)` — the second covers the first).

Two `borrow` arguments naming the same value are **allowed**
(read-only sharing is safe).

```a7
swap(x, y)                           // OK if x and y are distinct
swap(x, x)                           // compile error: aliasing
swap(arr[0], arr[1])                 // OK; distinct indices
swap(arr[i], arr[j])                 // compile error unless i != j proved
```

For array/slice indexing with opaque indices, the narrowing
prover applies the same machinery used for bounds checking. If
`i != j` is provable, the call compiles.

**Rationale.** Exclusivity prevents aliasing-driven data races
within a function. Matches Hylo's call-site rule. The
narrowing prover (CD) handles the dynamic-index case
uniformly.

**Implications.**
- New checker pass at every call site.
- Uses the narrowing prover (CD) for index-distinctness proofs.

---

### D.045 — `del p` consumes `p`; double-free is compile-time            [PROPOSED]

**Question.** `10-affine-ownership.md` AO-06, AO-08.

**Decision.** `del p` is the heap-deallocation operation. It
consumes the binding `p`; any subsequent use of `p` is a
compile error. Double-`del` is therefore a compile-time error
("use of consumed value").

```a7
p: ref Buf = new Buf{...}
del p
del p                                // compile error: use of consumed value
```

**Rationale.** Same move analysis as everywhere; `del`
participates in the lattice. Closes double-free statically;
matches Rust's `drop` semantics.

**Implications.**
- Existing examples with manual `del` work unchanged.
- The codegen for `del p` continues to call the allocator's
  destroy function.

---

### D.046 — Auto-drop at scope exit                                      [PROPOSED]

**Question.** `10-affine-ownership.md` Q10e.

**Decision.** When a non-`Copy` binding goes out of scope
without being consumed, the compiler **auto-emits `del`**
at the scope exit point.

```a7
process :: fn() {
    p: ref Buf = new Buf{...}
    use(p)
    // implicit `del p` at the closing brace
}
```

The user can still write explicit `del p` to control timing.

`defer del p` (existing A7 idiom) remains valid; if both an
explicit `defer del` and the implicit drop would apply, the
explicit form takes precedence (the compiler doesn't double-`del`).

**Rationale.** Ergonomic — users don't write `del` for every
local heap allocation. Matches Rust's `Drop` trait and Hylo's
scope-exit semantics. The contract is preserved (no leaks);
the auto-emit is purely a compile-time codegen feature.

**Implications.**
- New codegen pass: emit `del` at scope-exit points for
  non-`Copy` live bindings.
- Auto-drop **order** is reverse declaration order (last-
  declared dropped first); matches Rust convention.

---

### D.047 — `Copy` is compiler-inferred from structure                    [PROPOSED]

**Question.** Implicit from CA D.021 (Copy marker exists).

**Decision.** A type is `Copy` if and only if all its component
types are `Copy`:

- All primitives (`int`, `uint`, `number`, `bool`) are `Copy`.
- `string` is **not** `Copy` (it owns a heap allocation; A7
  strings are UTF-8 byte buffers).
- `[N]T` is `Copy` iff `T` is `Copy`.
- `[]T` (slice) is **not** `Copy` (it borrows a backing
  storage; treating it as `Copy` would create aliasing).
- `ref T` is **not** `Copy` (reference types track ownership).
- Tagged unions are `Copy` iff all variant payloads are `Copy`.
- Structs are `Copy` iff all fields are `Copy`.
- Enums (without payload) are always `Copy`.

The user does **not** write `Copy` annotations. The compiler
infers and reports the property in diagnostics when relevant.

**Rationale.** Structural inference matches Hylo, Mojo. Avoids
trait-system machinery (which A7 doesn't have). The inferred
property is stable: adding a non-`Copy` field to a `Copy`
struct silently breaks the inference, but the compiler will
catch downstream usage.

**Implications.**
- Type checker maintains a `Copy` flag per type.
- Generic constraints can reference `Copy` via the existing
  `@type_set` vocabulary: `@type_set([Copy])`.

---

### D.048 — Partial moves out of struct fields are allowed                [PROPOSED]

**Question.** `10-affine-ownership.md` AO-25 — AO-28, Q10i.

**Decision.** Moving out of a struct field is allowed; the
parent struct enters the **partially-moved** state. Accessing
the non-moved fields remains permitted; using the whole struct
(passing it to a function, returning it, etc.) is a compile
error until the moved field is replaced.

```a7
pair := (first: new Buf{...}, second: 42)
extracted := pair.first              // pair is now partially-moved on .first
print(pair.second)                   // OK; .second still live
take(pair)                           // compile error: pair partially moved
pair.first = new Buf{...}            // restores live state
take(pair)                           // OK now
```

**Rationale.** Matches Rust's partial-move semantics; useful
for builder patterns and field-by-field disassembly. The
restoration via re-assignment is symmetric.

**Implications.**
- Move analysis tracks per-field state for non-`Copy` struct
  fields.
- Diagnostic format: "pair partially moved on field .first;
  the move happened at line N".

---

### D.049 — No storable references; references are parameter-mode only   [PROPOSED]

**Question.** `10-affine-ownership.md` Q10a.

**Decision.** References in A7 exist **only** as parameter
modes. A struct field cannot have type `borrow T` or `inout T`
or `consume T`; a local variable cannot store a borrow. The
only "reference-like" storage is `ref T` (pointer to a heap
allocation), which is itself an owning reference managed by
allocation.

```a7
Wrapper :: struct {
    r: borrow int                    // compile error: borrow not storable
}

x: int = 5
b: borrow int = x                    // compile error: borrow not a value type
```

**Rationale.** Eliminates lifetime annotations entirely.
Matches Hylo and Mojo's "references at parameters only" rule.
Storable references would force the language to encode
lifetimes; deferred indefinitely.

**Implications.**
- Idioms that store references (callbacks, observers, linked
  structures) use heap-allocated `ref T` instead.
- Linked data structures use indices into an owning container
  rather than self-referential references.

---

## Concurrency

### D.050 — Concurrency model: channels + isolated owned data            [PROPOSED]

**Question.** User direction (earlier confirmation): channels +
isolated heaps; no reference capabilities.

**Decision.** A7's concurrency model is **task-as-actor with
channel communication**:

- Each task has its own stack and conceptually its own private
  heap region.
- Cross-task communication is via **channels** only.
- Values cross channels by **move** (ownership transfer); no
  shared mutable state across tasks.
- For `Copy` types, channel send is indistinguishable from
  copy. For non-`Copy` types, the sender loses ownership and
  the receiver gains it.

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

**Rationale.** Composes naturally with affine ownership. No
new type-system features (no reference capabilities like
Pony's six caps). Familiar to Go / Erlang / Inko users.
Sufficient for the typical concurrent workload.

**Implications.**
- Stdlib `Channel<T>` type with `.new(capacity)`, `.send(v)`,
  `.recv() -> ?T`, `.close()`, `for v in ch` iteration.
- Runtime support for task scheduling (delegated to Zig's
  async or a custom scheduler; implementation decision).
- No shared mutex / lock primitives in v1; not needed because
  no shared mutable state.

---

### D.051 — Task spawn syntax: `go` keyword                              [PROPOSED]

**Question.** `parameter-modes.md` Q11.

**Decision.** Task spawn syntax follows Go's convention:

```a7
go work(args)                         // spawn task running `work(args)`
go fn() {                             // inline anonymous task
    ...
}()
```

**Rationale.** Short, familiar, English-readable. Matches Go's
goroutines; users coming from Go feel at home. The keyword is
unambiguous in context (no conflict with existing A7
keywords).

**Implications.**
- Tokenizer adds `go` keyword.
- Codegen lowers to a task-spawn function in the runtime.

---

### D.052 — Cross-task data crosses by move only; no borrow              [PROPOSED]

**Question.** Implicit from D.050.

**Decision.** Channels accept values by `consume` semantics
only. A `borrow` or `inout` parameter cannot cross a channel
or task boundary. References to data owned by another task are
forbidden.

```a7
ch.send(consume p)                   // OK; p is moved into the channel
ch.send(p)                           // same; default mode for non-Copy is consume on cross-task
ch.send(borrow p)                    // compile error: borrow doesn't cross tasks
```

**Rationale.** Without storable references and without shared
mutable state, the only safe channel transfer is by move.
Closes the data-race surface entirely at the type level.

**Implications.**
- Type checker rejects borrow/inout in channel-send positions.
- Channel `recv()` returns owned values.

---

### D.053 — Stack budget applies per task                                 [PROPOSED]

**Question.** `parameter-modes.md` Q12.

**Decision.** The compile-time stack-budget analysis (planned
for CE D.062) applies **per task**. Each spawned task gets its
own statically-computed stack size; the runtime allocates
exactly the required stack per task at spawn.

```a7
work :: fn(items: []int) {
    // budget analyzed at compile time; runtime allocates this much
    ...
}

go work(my_items)
```

**Rationale.** Tasks have bounded stack needs because A7 has
no recursion. The per-task budget computation reuses the same
infrastructure as the main task. Eliminates the typical "what
stack size should I give my goroutine?" question — the
compiler answers it.

**Implications.**
- Spawning code retrieves the callee's computed budget and
  passes it to the runtime stack allocator.
- Tasks calling functions that exceed their budget refuse to
  compile (caught early).

---

## Cluster CC — summary

**Decisions: 14.** (D.040 through D.053.)

Coverage:
- **Default parameter immutability**: D.040 (1)
- **Parameter modes**: D.041 — D.042 (2)
- **Move analysis**: D.043 — D.048 (6)
- **No storable refs**: D.049 (1)
- **Concurrency**: D.050 — D.053 (4)

### What the user sees

User-facing additions:

- Parameter mode keywords: `borrow`, `inout`, `consume`.
- `go fn(args) { ... }` task spawn.
- `Channel<T>` stdlib type.
- Move-by-default for non-`Copy` types on function calls and
  channel sends.

User-facing rules (compile-time):

- Parameters are immutable by default; mutation requires
  `inout`.
- Calling `f(x)` for non-`Copy` `T` consumes `x`.
- Re-using a consumed binding is a compile error.
- `del p` consumes `p`; double-`del` is a compile error.
- Auto-`del` at scope exit for non-consumed bindings.
- Two `inout` arguments to the same call must name distinct
  values.
- References cannot be stored in struct fields or local
  variables.
- Cross-task transfer is by move only.

### What the compiler does

- Per-binding state lattice (live / partial / consumed)
  through the CFG.
- Call-site exclusivity check at every function call.
- Per-task stack-budget computation.
- Auto-`del` emission at scope-exit points.

---

## Cluster CC status: **PROPOSED**

Please review. Three response shapes:

1. **Approve as a whole** → I mark all 14 as ACCEPTED and
   proceed to Cluster CD (flow analysis details).
2. **Amend specific D.NN** → tell me which numbers need
   changes and how.
3. **Block on something** → point me at the decision; I
   research further or ask follow-up questions.

---

# Clusters CD through CG — pending

These clusters follow Cluster CC's approval. Now-simplified
topics:
- **CD — Flow analysis** (informed by `narrowing.md`; locks in
  lattice level, recognised pattern catalog, invalidation rules,
  diagnostic format).
- **CE — Numerics specifics** (mostly absorbed into CA;
  remaining: divisor non-zero method names, stack-budget policy).
- **CF — Modules and metaprogramming** (Ada inspirations:
  `private` sections, hierarchical modules, aspect specifications,
  profiles. Possibly: bit-width-warning silencing attribute
  syntax).
- **CG — FFI boundary** + **concurrency model commitment**
  (channels-and-isolated-heaps per your prior pick).
