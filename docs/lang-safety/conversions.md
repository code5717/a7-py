# Conversions — Research Notes for Cluster CB

> **Status:** historical research. Phase C input for Cluster CB, written
> before 2026-09-14 and cleaned up on 2026-09-16. Not a decision document.
> The authoritative record is the ledger in
> [`../plan/decisions.md`](../plan/decisions.md).
> Companion to [`narrowing.md`](./narrowing.md). The proposed decisions were
> drafted in [`08-decisions.md`](./08-decisions.md) Cluster CB.

> **Note (2026-09-16): much of this file is superseded.**
>
> - It assumes `int`, `uint` and `number` are the primary numeric types, with
>   bit-width types kept for FFI. Ledger L3 removes `number`. L4 keeps only
>   explicit widths (`i8`–`i64`, `u8`–`u64`, `isize`, `usize`). The catalog must
>   be restated for explicit widths under gate G3.
> - It assumes `number` has no NaN or infinity. L16 adopts IEEE 754 floats as in
>   Zig and C, so NaN and infinity are ordinary values.
> - It cites D.003 (non-overflowing arithmetic). L5 makes `+`, `-` and `*` wrap.
> - It uses `cast(T, x)` in its worked examples but also says `cast` is removed
>   (D.038). D.024 and D.038 contradict each other; neither stands, and the
>   question is open under G3.
> - `?T`, `Option`, `Result`, `some` and `none` are not current features.
>   [`../STATUS.md`](../STATUS.md) lists `Option` and `Result` as planned stdlib work.
>
> The method-style principle and proof-driven check elision remain open
> research under G3.

## Guiding principle

Earlier drafts made every fallible conversion return `?T`. The revised
principle, written after Cluster CA and after feedback asking for a
Python/JS feel, has two categories.

| Category | Examples | Result type | When the precondition is unproven |
| --- | --- | --- | --- |
| Statically resolvable | `x.to_uint()`, `s[i]`, `a / b` | the direct type `T` | compile error; the user adds a guard |
| Data-dependent | `s.parse_int()`, `new T{...}`, `read_line()`, `extern fn` returns | `?T` or `Result<T, E>` | not applicable; failure depends on runtime input |

Some sections below still show the older "everything returns `?T`" view.
They are kept for context.

> **Note (2026-09-16):** the file is not fully consistent with this
> principle. The summary table under
> [Compile-time and runtime checks](#compile-time-and-runtime-checks) says an
> unproven `x.to_uint()` becomes a runtime branch. The section
> [When narrowing cannot discharge](#when-narrowing-cannot-discharge) says it
> does not compile. This conflict is unresolved.

## What the compiler does today

Verified on 2026-09-16 by reading `a7/cast_classifier.py`, `a7/safety.py`,
`a7/backends/zig.py` and `test/test_cast_safety_matrix.py`. The compiler was
not run for this cleanup.

Current A7 has one explicit cast form, `cast(T, x)`. It covers primitive
numeric types only. `classify_cast` sorts each cast into a class:

| Source → target | Class | Needs a proof? |
| --- | --- | --- |
| Identical types | lossless | no |
| Signed → wider or equal signed; unsigned → wider or equal unsigned; float → wider or equal float | lossless | no |
| Unsigned → strictly wider signed (for example `u32` → `i64`) | lossless | no |
| Signed → unsigned | provable narrowing | yes: value is non-negative and its known range fits the target |
| Unsigned → signed of equal or smaller width | forbidden unless proven | yes: value range fits the target |
| Signed → narrower signed; unsigned → narrower unsigned | forbidden unless proven | yes: value range fits the target |
| Float → integer | explicit numeric | yes: source must be a finite, integral float literal in range |
| Other numeric pairs (for example integer → float) | explicit numeric | no |
| Anything involving references, functions or non-numeric primitives | forbidden | not allowed |

The Zig backend emits `@as(T, @intCast(x))` for integer casts and
`@as(T, @intFromFloat(x))` for float-to-integer casts.

A guard can supply the non-negative proof, but the value also needs a known
range. A local initialized from a literal has one. A function parameter starts
with no range, and conditions add only lower bounds, so `if i < 0 { ret }` on a
parameter `i: i64` does not prove `cast(usize, i)` today. The test suite checks
the two forms below for every signed-to-unsigned pair.

Current A7:

```a7
early_return :: fn() {
    x: i64 = 7
    if x < 0 {
        ret
    }
    y := cast(usize, x)         // accepted: range [0, 7] fits usize
}

inside_branch :: fn() {
    x: i64 = 7
    if x >= 0 {
        y := cast(usize, x)     // accepted: branch condition keeps x >= 0
    }
}
```

A signed-to-unsigned cast without a known, fitting range is rejected.

## The conversion surface after Cluster CA

> **Note (2026-09-16):** this catalog assumes `int`, `uint` and `number`.
> Superseded by ledger L3/L4; restate under gate G3.

Cluster CA made `int`, `uint` and `number` the primary types and limited
bit-width types to FFI. That removed most of the 30 subcases in
[`edge-cases/01-cast.md`](./edge-cases/01-cast.md). Seven categories remain.

### 1. Numeric conversions

| From | To | Always safe? | Notes |
| --- | --- | --- | --- |
| `int` | `int` | yes, identity | no-op |
| `uint` | `uint` | yes, identity | no-op |
| `number` | `number` | yes, identity | no-op |
| `uint` | `int` | yes, widening | always; arbitrary precision |
| `int` | `uint` | no, sign | `?uint`; fails when `x < 0` |
| `int` | `number` | yes, embedding | precision-preserving |
| `uint` | `number` | yes, embedding | same |
| `number` | `int` | no, must round | three rounding modes plus a fallible exact mode |
| `number` | `uint` | no, sign and rounding | three rounding modes plus a fallible exact mode |

The original text said "five fallible conversions". The table has three
fallible pairs; the count of five may include rounding modes.

### 2. String parsing and formatting

| From | To | Always safe? |
| --- | --- | --- |
| `int`, `uint`, `number`, `bool` | `string` | yes |
| `string` | `int` | no, `?int` |
| `string` | `uint` | no, `?uint` |
| `string` | `number` | no, `?number` |
| `string` | `bool` | no, `?bool` (`"true"` and `"false"` only) |

### 3. Bool conversions

Bool never converts to or from a numeric type. There is no truthy or falsy
value. `bool` converts to and from `string` through formatting and parsing.

Proposed:

```a7
flag := true
n := flag.to_int()              // compile error: no bool-to-numeric conversion
m: i32 = if flag { 1 } else { 0 }   // write the mapping explicitly
text := flag.to_string()        // "true"
back := text.parse_bool()       // ?bool: some(true)
```

The `if` expression form in this example is illustrative, not a claim about
current syntax.

### 4. Reference and compound conversions

| From | To | Mechanism |
| --- | --- | --- |
| `ref T` | `?ref T` | implicit upcast (CA D.011) |
| `?ref T` | `ref T` | `match` only; no cast keyword |
| `[N]T` | `[]T` | implicit upcast (array to slice) |
| `[]T` | `[N]T` | fallible `[N]T::try_from(s) -> ?[N]T` |

Proposed:

```a7
buf: [4]u8 = [1, 2, 3, 4]
view: []u8 = buf                // implicit array-to-slice
fixed := [4]u8::try_from(view)  // ?[4]u8: none when view.len != 4
```

### 5. FFI bit-width conversions

> **Note (2026-09-16):** L4 makes explicit widths the only integer types, so
> the "bit-width types are warned outside FFI" premise (CA D.002) no longer
> holds.

Bit-width types were to be warned outside FFI code (CA D.002). Inside an
`extern fn` caller shim they are allowed without warning. Conversions between
them use the same method style as the primary types: `bw.to_int()`,
`n.to_i32() -> ?i32`. See [FFI shims](#ffi-shims) for an example.

### 6. Enum discriminant conversions

| Direction | Mechanism |
| --- | --- |
| `EnumT` → discriminant `int` | `e.discriminant() -> int` |
| `int` → `EnumT` | `EnumT::from_discriminant(i) -> ?EnumT` |

The second direction is fallible because not every `int` is a valid
discriminant. See [Enum discriminants](#enum-discriminants) for an example.

### 7. Bit reinterpretation (`bit_cast`)

A few operations reinterpret the bits of one type as another type of the same
size. The common case is reading float bits as an integer for hashing or FFI
shims. The audit's Q01c asks whether `bit_cast` should be a language operator.

Recommendation: no operator. The stdlib provides helpers for the known cases,
such as `f32.bits() -> u32` and `u32.as_f32() -> f32`. The set is small and
closed.

Proposed:

```a7
x: f32 = 1.5
raw := x.bits()                 // u32: 0x3FC00000
y := raw.as_f32()               // f32: 1.5
```

### Surface size

| Category | Count |
| --- | --- |
| Numeric (1) | 9 conversions, 3 fallible pairs |
| String parsing and formatting (2) | 8 |
| Bool (3) | 2 |
| Reference and compound (4) | 4 |
| FFI bit-width (5) | inside extern shims; same as numeric |
| Enum discriminant (6) | 2 |

That is about 25 method names across the relevant types, with no new keywords.
The original summary said "all fallible cases use `?T`"; the two-category
principle above narrows that to data-dependent cases.

---

## Three design styles

How do production languages name and structure conversions?

### Style A: method style

Conversions are methods on the source type: `x.to_int()`, `x.to_string()`,
`s.parse_int()`.

Languages:

- **Kotlin:** `x.toInt()`, `x.toLong()`, `x.toString()`, and the fallible
  `s.toIntOrNull()`. The most thorough method-style design.
- **Rust:** `x.to_string()` through `Display`, and `s.parse::<T>()` for any
  `T: FromStr`. Rust mixes this with the `as` operator.

Pros:

- Methods chain: `s.trim().parse_int()?`.
- The source type's namespace is a natural home for its conversions.
- Typing a dot shows every conversion in IDE autocomplete.
- No new keywords.
- Hovering a method shows its documentation.

Cons:

- Verbose for one-off conversions: `x.to_int()` against `int(x)`.
- A conversion between two types that own neither side, such as `Bool` and a
  `Color` enum from different modules, still needs a home.

### Style B: constructor style

The type name acts as a function: `int(x)`, `String(x)`, `Bool("true")`.

Languages:

- **Python:** `int(x)`, `float(x)`, `str(x)`, `bool(x)`.
- **JavaScript:** `Number(x)`, `String(x)`, with separate parsers such as
  `parseInt(s)`.
- **Swift:** initializers such as `Int(exactly: x)`, `Int(x)`, `String(x)`,
  with labels and many overloads.
- **Mojo:** `Int(x)`. The original notes say Mojo recently moved to lowercase
  `int(x)`; this was not re-verified on 2026-09-16.

Pros:

- `int(x)` is short and familiar to Python and JS users.
- Construction and conversion look the same.
- No method dispatch.

Cons:

- Types must be callable as functions, which most procedural languages do not
  support naturally.
- Overloaded constructors confuse: in Swift, `Int(x)` truncates a float while
  `Int(exactly: x)` returns an optional.
- Chains poorly.

### Style C: operator style

A dedicated operator or builtin: `x as int`, `@as(int, x)`, `cast(int, x)`.

Languages:

- **Rust:** `x as i32` for primitive casts. It always succeeds and may
  truncate. Rust also has the `T::from(x)` and `T::try_from(x)` traits.
- **Zig:** `@as`, `@intCast`, `@floatFromInt` and others, one builtin per
  conversion family.
- **A7 today:** `cast(T, x)`. The audit flagged the original unrestricted form
  as a critical safety hole. The current compiler restricts it (see
  [What the compiler does today](#what-the-compiler-does-today)).

Pros:

- Compact for the common case.
- One operator instead of many methods.

Cons:

- The syntax does not separate lossless, lossy and forbidden conversions.
- New "supported" conversions can be added silently.
- Zig's separate builtins partly fix this, at the cost of about ten builtins.
- The audit found this exact ambiguity in A7's original `cast`.

### Recommendation: method style with fallible return types

> **Note (2026-09-16):** this recommendation was drafted as D.024. D.024 and
> D.038 contradict each other on `cast(T, x)`; the choice is open under G3.

- Style B needs types callable as functions. A7 does not have that, and it
  interacts badly with generics.
- Style C is what A7 had, and it caused the audit's most urgent finding
  (§1.2 of [`07-language-review.md`](./07-language-review.md)).
- Style A puts methods on the source type, with fallible variants returning
  `?T`. It fits the existing method-call surface (CA D.018).

---

## Rounding from `number` to `int`

> **Note (2026-09-16):** `number` is removed by L3, and "arbitrary precision"
> no longer applies under L4. Under L16 a float can be NaN or infinite, and a
> finite float can still exceed an integer type's range. Restate for `f32`/`f64`
> and explicit-width targets under G3.

`number` converts to `int` or `uint` in four ways:

| Method | Semantics | Examples and failure |
| --- | --- | --- |
| `n.to_int_trunc() -> ?int` | round toward zero | `3.7 → 3`, `-3.7 → -3`; fails if `n` is not finite-integer-representable |
| `n.to_int_floor() -> ?int` | round toward `-∞` | `3.7 → 3`, `-3.7 → -4` |
| `n.to_int_round() -> ?int` | round to nearest, ties to even (banker's rounding) | `3.7 → 4`, `3.5 → 4`, `4.5 → 4` |
| `n.to_int_exact() -> ?int` | succeeds only if `n` equals an integer | `3.0 → 3`; `3.5 → none` |

`to_uint_*` has the same four. Because `number` was arbitrary precision, every
result that should fit in `int` did fit, so the only failures were:

- `n` is not representable as an integer (relevant to `_exact`);
- for `to_uint_*`, `n < 0`.

Why four methods: each rounding mode is a different operation. Making the user
pick documents the choice. A default mode with an optional argument hides it.
Python's `int(x)` truncates silently, which is more ambiguous than an explicit
`to_int_round`.

Proposed:

```a7
price: number = 19.5
a := price.to_int_trunc()       // some(19)
b := price.to_int_round()       // some(20): ties to even
c := price.to_int_exact()       // none
```

---

## Check elision through narrowing

This was the core performance argument for the design.

A conversion's signature is its contract. `to_uint() -> ?uint` says the
conversion might fail. The implementation does not have to check at run time.
If narrowing (see [`narrowing.md`](./narrowing.md)) has proved the range
obligation at the call site, the compiler emits only the success path.

> **Note (2026-09-16):** the examples below use `int`, `uint` and `number`
> (L3/L4) and `cast(T, x)` (open under G3). The emitted Zig uses the pre-0.11
> two-argument builtin form. The current backend emits
> `@as(usize, @intCast(i))`. The emitted Zig also returns `s.ptr[idx]` where
> the A7 source returns `some(s[idx])`.

### Example: guarded index

Proposed:

```a7
process :: fn(s: []int, i: int) ?int {
    if i < 0 or i >= s.length {
        ret nil
    }
    // here `i: int with range [0, s.length-1]`
    idx := cast(uint, i)            // returns uint directly;
                                     // narrowing discharged `i >= 0`;
                                     // emission: bare `@intCast(usize, i)`
                                     // — no runtime range check.
    ret some(s[idx])                 // idx range-proved in s.length;
                                     // bare s.ptr[idx] in emitted Zig.
}
```

`cast(uint, i)` returns `uint` directly (D.026). Narrowing has proved
`i >= 0`, so no range check is emitted. The intended Zig output:

```zig
fn process(s: []const i64, i: i64) ?i64 {
    if (i < 0 or i >= @intCast(i64, s.len)) return null;
    // `i` proved >= 0 here; the to_uint conversion emits bare cast:
    const idx: usize = @intCast(usize, i);
    // `idx` proved < s.len; bare ptr-indexing:
    return s.ptr[idx];
}
```

There is no `if (i < 0)` for the conversion and no bounds check on `s[idx]`.
Both obligations are discharged statically.

### Example: `number` to `uint`

Proposed:

```a7
float_to_index :: fn(f: number, n: uint) ?uint {
    if f < 0 or f >= cast(number, n) {
        ret nil
    }
    // here `f: number with range [0, n)`
    i := cast(uint, f.floor())       // cast(uint, number) on floored value;
                                      // f is range-proved [0, n);
                                      // emission: bare floor + cast.
    ret some(i)
}
```

The original claim: narrowing discharges both the cast and the bounds, so the
emission is a bare `@intFromFloat(usize, @floor(f))` with no NaN, negative or
range check.

> **Note (2026-09-16): unsound under L16.** For NaN, both `f < 0` and
> `f >= cast(number, n)` are false, so NaN passes the guard. `@intFromFloat`
> on NaN is illegal behavior in Zig and unchecked in ReleaseFast. A sound
> version needs an explicit NaN test, or a lattice that tracks NaN. See the
> float note in [`narrowing.md`](./narrowing.md).

### The argument

The fallible signature (`?T`) gives the type-level proof obligation. Emission
driven by the prover means the run-time cost is paid only when the prover
fails. In typical code (loop-bounded, post-guard or literal conversions), the
claim was that the cost is zero.

This mirrors CA's bare arithmetic specialization (D.003): the contract is safe
by default, and the implementation specializes when it can prove safety.

> **Note (2026-09-16):** D.003 is superseded by L4/L5. Wrapping `+ - *` needs
> no overflow proof; division, casts, shifts and sizes still do.

### Emission without narrowing

```zig
fn process_no_narrowing(s: []const i64, i: i64) ?i64 {
    if (i < 0 or i >= @intCast(i64, s.len)) return null;
    // Without narrowing, .to_uint() emits:
    if (i < 0) return null;          // dead check; i already > 0
    const idx: usize = @intCast(usize, i);
    // Without narrowing, s[idx] needs bounds check:
    if (idx >= s.len) return null;    // dead check; idx < s.len
    return s.ptr[idx];
}
```

Two extra branches, both dead. Narrowing removes them.

---

## When narrowing cannot discharge

Under the revised principle (D.025), the operation does not compile. The user
adds a guard, and the next compile discharges the precondition.

Proposed:

```a7
process_opaque :: fn(s: []int, i: int) int {
    // no early-return guard; i could be anything
    idx := cast(uint, i)              // compile error: i may be negative
    ret s[idx]                         // compile error: idx not in bounds
}
```

The diagnostic names the guard to add:

```
error: cast(uint, int) requires `i >= 0`
help: add a guard so the prover can discharge the precondition:
   |
 1 | process_opaque :: fn(s: []int, i: int) int {
 2 |     if i < 0 or i >= s.length { ret -1 }
 3 |     idx := cast(uint, i)
 4 |     ret s[idx]
 5 | }
```

The compiler never inserts a silent runtime trap. It rejects the code and
explains the fix.

Current A7 already fails closed for casts (see
[What the compiler does today](#what-the-compiler-does-today)). Its current
diagnostic text differs from this mockup.

---

## Literal conversions at compile time

An integer literal such as `42` has a compile-time value. It converts to any
numeric target whose range contains that value. No runtime work and no
conversion method are needed.

Proposed (original notation):

```a7
let x: int = 42
let y: uint = 42                       ; literal fits uint range; no method needed
let z: number = 42                     ; literal converts to number losslessly
```

The same holds for expressions of literals only: `let n: uint = 10 * 5`
compiles because `50` fits `uint`.

This is constant folding at the conversion site, matching Zig's
`comptime_int`. Users write plain integer literals, and context picks the type.

Current A7 (explicit widths):

```a7
main :: fn() {
    small: u8 = 42
}
```

A literal initializer of an explicit-width type is the form the ledger uses
for its own current-behavior example (`x: u8 = 255`). Whether a folded
expression such as `10 * 5` converts to `usize` without `cast` was not
verified; `examples/029_sorting.a7` writes `cast(usize, 0)` explicitly.

---

## String formatting

Every built-in type provides `x.to_string()`. For more control,
`x.format(spec)` takes a format-spec string.

Proposed (original notation):

```a7
let s1 = 42.to_string()                ; "42"
let s2 = 3.14.to_string()              ; "3.14"
let s3 = 255.format("hex")             ; "ff"
let s4 = 0.123.format("0.4f")          ; "0.1230"
```

The spec syntax, Python-style or Rust-style, is a stdlib detail and not a
Cluster CB decision. `f"..."` interpolation (CA D.008) calls `.to_string()` on
each interpolated value.

---

## String parsing

Four parsing methods on `string`:

| Method | Returns none when | Notes |
| --- | --- | --- |
| `s.parse_int() -> ?int` | input is invalid | decimal only by default |
| `s.parse_uint() -> ?uint` | input is invalid or negative | decimal only |
| `s.parse_number() -> ?number` | input is invalid | decimal point or scientific notation |
| `s.parse_bool() -> ?bool` | input is not `"true"` or `"false"` | |

For other radixes:

| Method | Range | Notes |
| --- | --- | --- |
| `s.parse_int_radix(r: uint) -> ?int` | `r ∈ [2, 36]` | hex via `parse_int_radix(16)` |

This is the minimal v1 surface. Users can write their own parsers for richer
formats.

Proposed:

```a7
port := "8080".parse_uint()               // some(8080)
bad := "80a0".parse_uint()                // none
mask := "ff".parse_int_radix(16)          // some(255)
```

---

## Fit with Cluster CA's `?T` rules

Cluster CA decided:

- `?T` is sugar for `Option<T>` (D.010).
- No `unwrap()` or `expect()` (D.018).
- Postfix `?` propagates none (D.017).
- Minimal combinators: `.map()` and `.unwrap_or()` (D.019).

Fallible conversions fit these rules. Each returns `?T`. The user matches,
propagates with `?`, or supplies a default with `.unwrap_or(default)`. No new
operators or keywords are needed.

> **Note (2026-09-16):** `?T` and `Option` are not current features (STATUS.md
> lists them as planned). D.010 is superseded for `int`/`number` optionals by
> L4. Under the `usize` rule, lengths and indices use `usize`, not `uint`.

Proposed (rewritten from the original `fn … end` notation into current block
syntax; types unchanged):

```a7
read_age :: fn(s: string) uint {
    ret s.trim().parse_uint().unwrap_or(0)
}

read_name_age :: fn(s: string) ?(string, uint) {
    parts := s.split(",")
    if parts.length != 2 {
        ret none
    }
    name := parts[0].trim()
    age := parts[1].trim().parse_uint()?
    ret some((name, age))
}
```

The tuple return type is illustrative. Multiple return values and
destructuring are not current backend features.

---

## FFI shims

Inside an `extern fn` shim, the bit-width warning (CA D.002) is suppressed.
Conversions between FFI types and primary types use the same method style.

Proposed (rewritten from the original `fn … end` notation; types unchanged):

```a7
c_get_count :: extern fn() i32

// The shim wraps the foreign call:
read_count :: fn() ?uint {
    raw: i32 = c_get_count()       // FFI return type
    ret raw.to_uint()              // ?uint; none if raw < 0
}
```

Inside the shim, `i32 → uint` is one more fallible numeric conversion. The
shim's attribute silences the D.002 warning; Cluster CF owns the exact syntax.
The `extern fn` declaration spelling above is illustrative.

> **Note (2026-09-16):** under L4 `i32` is an ordinary type and `uint` does not
> exist. The equivalent is a fallible `i32 → u32` or `i32 → usize` conversion,
> restated under G3.

---

## Enum discriminants

Enums have a built-in discriminant relationship.

Proposed (original notation):

```a7
enum Color { red, green, blue }

let c = Color::red
let d: int = c.discriminant()          ; e.g., 0

let from_disk: int = ...
let c2 = Color::from_discriminant(from_disk)
match c2
    case some(color): print(color)
    case none:        print("invalid color")
end
```

The user can choose discriminant values; the default is sequential from 0.
`from_discriminant` is fallible because input may not match any value.

---

## Compile-time and runtime checks

| Conversion | When the check happens |
| --- | --- |
| Literal `42 → uint` | compile time; no code emitted |
| `42 → uint` via `.to_uint()` | compile time; literal recognized |
| `x.to_uint()` where `x` is proved `>= 0` | compile time; emission is a bare cast |
| `x.to_uint()` where `x` is opaque | runtime branch; `?uint` return contract |
| `s.parse_int()` | runtime parse; always returns `?int` |
| `s.to_string()` | runtime format; always succeeds |
| `r.bits()` (float bits as integer) | compile-time eligible; no failure mode |

Users write the same method call in every case. The split is an emission
detail.

> **Note (2026-09-16):** the "opaque → runtime branch" row conflicts with
> [When narrowing cannot discharge](#when-narrowing-cannot-discharge), which
> makes the same call a compile error. Unresolved.

---

## Comparison with other languages

| Language | Lossless | Lossy (truncating) | Reinterpret | Fallible |
| --- | --- | --- | --- | --- |
| **Python** | `int(x)` (raises) | `int(x)` (truncates) | none | (use `try/except`) |
| **JavaScript** | `Number(x)` (NaN on fail) | `parseInt(x)` | `Float32Array` hacks | (returns NaN) |
| **Swift** | `Int(x)` (traps on overflow) | `Int(truncating: x)` | `unsafeBitCast` | `Int(exactly: x)` returns `Int?` |
| **Kotlin** | `x.toLong()` | `x.toInt()` (truncates) | `Float.fromBits` | `s.toIntOrNull()` |
| **Rust** | `T::from(x)` | `x as T` (truncates) | `mem::transmute` | `T::try_from(x)` returns `Result` |
| **Ada** | `Integer(X)` (range-checked) | n/a | `Unchecked_Conversion` | range check raises |
| **Zig** | `@as(T, x)` (lossless only) | `@intCast(T, x)` | `@bitCast(T, x)` | n/a (traps if out of range) |
| **A7 proposed** | `.to_T()` (when lossless) | `.to_T_trunc()`, `.to_T_floor()`, etc. | stdlib helpers only | `.to_T() -> ?T` |

> **Audit notes (2026-09-16, from language knowledge; not re-checked against
> each language's current docs):**
>
> - **Swift:** integer truncation is `Int(truncatingIfNeeded: x)`.
>   `Int(truncating:)` is an `NSNumber` initializer.
> - **Rust:** `as` from float to integer saturates (Rust 1.45 and later).
>   `f32::to_bits` and `f32::from_bits` reinterpret without `transmute`.
> - **Zig:** since 0.11, cast builtins take one argument and infer the result
>   type, as in `@as(u8, @intCast(x))`. `@intCast` is a checked conversion, not a
>   truncating one: it panics in Debug and ReleaseSafe and is illegal behavior
>   in ReleaseFast. Truncation is `@truncate`.

A7's proposal is closest to Kotlin: method style, with `?T` for fallibility.
The difference is that A7's compiler would discharge most fallible-conversion
checks through narrowing.

---

## Open questions for Cluster CB

Each was to become a numbered decision.

- **Q1:** Should constructor-style `int(x)` exist beside `.to_int()`? Lean: no;
  one way to do it.
- **Q2:** Which rounding methods on `number`? Lean: `trunc`, `floor`, `round`
  and `exact`, as above.
- **Q3:** Format-spec syntax for `.format(spec)`. Deferred; stdlib detail.
- **Q4:** Should `string` provide `.bytes() -> []u8` for direct byte access?
  Lean: yes; cheap and useful at the FFI boundary.
- **Q5:** Should `bool` interpolate as `"true"` or `"false"` in `f"..."`
  strings? Lean: yes.
- **Q6:** Conversion in generic code. In `fn f<$T>(x: $T) -> ?$U`, can the body
  call `x.to_$U()`? It depends on whether the type-set constraint declares the
  method.
- **Q7:** Should a polymorphic `.into<T>()` exist, as in Rust? Lean: not in v1;
  it can be added later.
- **Q8:** Which bit-reinterpretation helpers go in the stdlib? Candidates:
  `f32.bits()`, `f64.bits()`, `u32.as_f32()`, `u64.as_f64()`, and possibly
  `u8 ↔ char` for ASCII work.

> **Note (2026-09-16):** Q1 and Q2 name `int` and `number` (L3/L4). Under G3
> they become questions about explicit-width targets and `f32`/`f64` sources.

---

## Changes from the audit's plan

The original [`edge-cases/01-cast.md`](./edge-cases/01-cast.md) proposed three
operators: `cast`, `truncating_cast` and `bit_cast`. This proposal drops all
three:

- `cast` is removed (D.038 in CB).
- `truncating_cast` does not exist; truncation is an explicit rounding method
  (`to_int_trunc()`).
- `bit_cast` becomes stdlib helpers (D.034 in CB).

The result: fewer operators, the same expressiveness through methods, and
stronger safety through fallible methods.

> **Note (2026-09-16):** D.038 conflicts with D.024; `cast(T, x)` is open
> under G3. Current A7 still has `cast(T, x)` with proof requirements.

---

## Planned Cluster CB decisions

The Cluster CB section in [`08-decisions.md`](./08-decisions.md) was to codify:

| Decision | Topic |
| --- | --- |
| D.024 | Method style is the conversion shape |
| D.025 | Fallible conversions return `?T` |
| D.026–D.027 | Numeric method catalog |
| D.028–D.029 | String formatting and parsing |
| D.030 | Bool/numeric conversion forbidden |
| D.031–D.033 | Array, slice, enum and FFI conversions |
| D.034 | No `bit_cast` operator |
| D.035 | Compile-time literal conversion |
| D.036 | Generic-context conversion |
| D.037 | Forbidden-conversion diagnostics |
| D.038 | `cast(T, x)` keyword removed |
| D.039 | Narrowing-driven check elision |

That is 12–15 decisions, all marked PROPOSED, with cross-references to CA.

> **Note (2026-09-16):** the ledger lists D.005, D.022, D.025–D.027, D.029,
> D.033–D.037 and D.039 as written for `int`/`uint`/`number`; they must be
> restated for explicit widths under G3. D.024 and D.038 contradict each
> other; neither stands.
