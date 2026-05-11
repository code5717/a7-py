# Conversions — Research Notes for Cluster CB

> Phase C research input. Companion to `narrowing.md`. Catalogs
> the post-CA conversion surface, compares language designs,
> and proposes A7's shape. Not itself a decision document — the
> decisions land in `08-decisions.md` Cluster CB.
>
> **Revision note (post-CA + Python/JS-feel pushback):**
> Earlier drafts had every fallible conversion return `?T`.
> The revised principle is two-category:
>
> - **Statically resolvable** (`x.to_uint()`, `s[i]`, `a / b`):
>   return the direct type. Compile error if the prover can't
>   discharge the precondition. The user adds a guard.
> - **Data-dependent** (`s.parse_int()`, `new T{...}`,
>   `read_line()`, `extern fn` returns): return `?T` or
>   `Result<T, E>` because failure depends on runtime input the
>   compiler can't see.
>
> This file's worked examples and recommendation tables have
> been updated to reflect that principle. The historical
> "everything returns `?T`" sections are preserved in places
> for context, marked with a callout.

## The post-CA conversion surface (much smaller than the audit assumed)

Cluster CA's numeric refactor (`int`/`uint`/`number` as primary
types; bit-width types as FFI-only) collapsed most of the 30
subcases in `edge-cases/01-cast.md`. The remaining conversion
surface, in five categories:

### 1. Numeric conversions

Across the three primary numeric types:

| From | To | Always safe? | Notes |
| --- | --- | --- | --- |
| `int` | `int` | yes — identity | no-op |
| `uint` | `uint` | yes — identity | no-op |
| `number` | `number` | yes — identity | no-op |
| `uint` | `int` | yes — widening | always; arbitrary precision |
| `int` | `uint` | **no** — sign | `?uint`; fails when `x < 0` |
| `int` | `number` | yes — embedding | precision-preserving |
| `uint` | `number` | yes — embedding | same |
| `number` | `int` | **no** — must round | three modes + fallible exact |
| `number` | `uint` | **no** — sign + round | three modes + fallible exact |

Five fallible conversions; the rest are infallible.

### 2. String parsing and formatting

| From | To | Always safe? |
| --- | --- | --- |
| `int`, `uint`, `number`, `bool` | `string` | yes (always succeeds) |
| `string` | `int` | no — `?int` |
| `string` | `uint` | no — `?uint` |
| `string` | `number` | no — `?number` |
| `string` | `bool` | no — `?bool` (`"true"` / `"false"` only) |

### 3. Bool conversions

Forbidden in both directions to numerics. Allowed: `bool ↔
string` via parse/format. No truthy/falsy.

### 4. Reference and compound conversions

| From | To | Mechanism |
| --- | --- | --- |
| `ref T` | `?ref T` | implicit upcast (CA D.011) |
| `?ref T` | `ref T` | `match` only (no cast keyword) |
| `[N]T` | `[]T` | implicit upcast (array-to-slice) |
| `[]T` | `[N]T` | fallible `[N]T::try_from(s) -> ?[N]T` |

### 5. FFI bit-width conversions

Bit-width types are warned in non-FFI code (CA D.002). Inside
an `extern fn`'s caller shim, bit-width types are first-class
without warning; conversions between them use the same
method-style as the primary types: `bw.to_int()`, `n.to_i32() ->
?i32`, etc.

### 6. Enum-discriminant conversions

| Direction | Mechanism |
| --- | --- |
| `EnumT` → discriminant `int` | `e.discriminant() -> int` |
| `int` → `EnumT` | `EnumT::from_discriminant(i) -> ?EnumT` |

The fallible direction returns `?EnumT` because not every `int`
is a valid discriminant.

### 7. The escape: `bit_cast`?

A small number of operations are bit-pattern reinterpretation
between same-size types — most commonly extracting float bits as
an integer (for hashing, FFI shim work). The audit's Q01c asks
whether `bit_cast` is a language operator.

**Recommendation**: no language operator. Provide stdlib helpers
(`f32.bits() -> u32`, `u32.as_f32() -> f32`) only for the
known-needed cases. The set is small and closed.

### Surface size after categorisation

| Category | Count |
| --- | --- |
| Numeric (1) | 9 conversions, 5 fallible |
| String parsing/formatting (2) | 8 |
| Bool (3) | 2 |
| Reference / compound (4) | 4 |
| FFI bit-width (5) | Inside extern shims; same as numeric |
| Enum discriminant (6) | 2 |

Total user-visible: ~25 method names across the relevant types.
All fallible cases use `?T`. No new keywords.

---

## Three design styles — comparative

How do production languages name and structure conversions?

### Style A — Method-style

`x.to_int()`, `x.to_string()`, `s.parse_int()`. Methods on the
source type's namespace.

**Languages:**
- **Kotlin** — `x.toInt()`, `x.toLong()`, `x.toString()`,
  `s.toIntOrNull()` (fallible variant). The most pervasive
  method-style design.
- **Rust** — `x.to_string()` (via `Display`), `s.parse::<T>()`
  (parses any `T: FromStr`). Mixed with the `as` operator.

**Pros:**
- Methods chain (`s.trim().parse_int()?`).
- The source type "knows" about its conversions; namespace is
  natural.
- IDE autocomplete: type a dot and see all the conversions.
- No new keywords.
- Discoverable: hover the method, see the docstring.

**Cons:**
- Verbose for one-off conversions (`x.to_int()` vs `int(x)`).
- If a conversion is *between* two types that don't "own"
  either side (e.g., `Bool` and a `Color` enum from different
  modules), the method has to live somewhere.

### Style B — Constructor-style

`int(x)`, `String(x)`, `Bool("true")`. Function-call syntax
where the type name acts as a constructor.

**Languages:**
- **Python** — `int(x)`, `float(x)`, `str(x)`, `bool(x)` — the
  canonical Pythonic style.
- **JavaScript** — `Number(x)`, `String(x)`, `parseInt(s)` —
  type-name-as-function for some; separate parsers for parsing.
- **Swift** — `Int(exactly: x)`, `Int(x)`, `String(x)` —
  initialisers (labeled, supports many overloads).
- **Mojo** — `Int(x)`, recently `int(x)` lowercase.

**Pros:**
- Reads as `int(x)` — concise, familiar to Python/JS users.
- Constructor and conversion are uniform.
- No "method dispatch" complexity.

**Cons:**
- Requires types to be callable as functions (a language
  feature most procedural languages don't naturally have).
- Constructors with multiple signatures are confusing (`Int(x)`
  truncates vs `Int(exactly: x)` returns optional in Swift).
- Doesn't chain as naturally.

### Style C — Operator-style

`x as int`, `@as(int, x)`, `cast(int, x)`. A dedicated operator
or built-in.

**Languages:**
- **Rust** — `x as i32` for primitive casts (always succeeds,
  may truncate). Also `T::from(x)` / `T::try_from(x)` traits.
- **Zig** — `@as(T, x)`, `@intCast(T, x)`, `@floatFromInt`,
  etc. Namespaced builtins per conversion family.
- **A7 today** — `cast(T, x)` — the unrestricted operator that
  the audit flagged as a critical safety hole.

**Pros:**
- Compact syntax for the common case.
- One operator vs many methods.

**Cons:**
- Doesn't distinguish lossless / lossy / forbidden conversions
  syntactically.
- Easy to add new "supported" conversions silently.
- Zig's `@intCast` etc. partially fixes this but at the cost of
  ten separate builtins.
- The audit found that A7's current `cast` is exactly the
  ambiguous-style problem.

### A7's choice: **Style A (method-style)** with fallible
return types

The other styles' downsides bite A7:

- Style B (constructor-style) requires "type as function," which
  A7 doesn't have today and which interacts awkwardly with
  generics.
- Style C (operator-style) is what A7 has today and is the
  source of the audit's most urgent finding (§1.2 of
  `07-language-review.md`).
- Style A — methods on the source type, fallible variants
  returning `?T` — composes with CA D.018 (existing method-call
  surface).

This is the recommendation. The rest of this file fills in
details.

---

## The `number → int` rounding policy

`number` (arbitrary precision real) needs to convert to `int`
or `uint` in four different ways:

| Method | Semantics | Failure |
| --- | --- | --- |
| `n.to_int_trunc() -> ?int` | Round toward zero | Fails if `n` not finite-int-representable; succeeds for `3.7 → 3`, `-3.7 → -3` |
| `n.to_int_floor() -> ?int` | Round toward `-∞` | `3.7 → 3`, `-3.7 → -4` |
| `n.to_int_round() -> ?int` | Round to nearest (banker's rounding) | `3.7 → 4`, `3.5 → 4`, `4.5 → 4` |
| `n.to_int_exact() -> ?int` | Only succeeds if `n` is mathematically equal to an integer | `3.0 → 3`; `3.5 → none` |

Same four for `to_uint_*`. With `number` being arbitrary
precision, every output that *would* fit in `int` does fit (no
range failure), so the only failure cases are:

- `n` is not finite-representable as an integer (matters for
  `_exact` only).
- For `to_uint_*`: `n < 0`.

**Why four methods**: each rounding mode is a different
mathematical operation. Forcing the user to pick makes the code
self-documenting. "Default to trunc with optional mode argument"
hides the choice; an explicit `to_int_round` is *less ambiguous*
than a Python-style `int(x)` which truncates by default but
silently.

---

## **Narrowing eliminates conversion runtime checks** (the central insight)

This is the load-bearing principle for A7's performance story.

A conversion method's signature is its **contract**:
`to_uint() -> ?uint` says "this *might* fail." But the
implementation is *not* required to check at runtime. If the
narrowing analysis (see `narrowing.md`) has discharged the
conversion's range obligation at this call site, the compiler
emits the success branch directly.

### Worked examples

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

`cast(uint, i)` returns `uint` directly per D.026; the compiler
emits **no range check** because narrowing has proved `i >= 0`.
The emitted Zig is:

```zig
fn process(s: []const i64, i: i64) ?i64 {
    if (i < 0 or i >= @intCast(i64, s.len)) return null;
    // `i` proved >= 0 here; the to_uint conversion emits bare cast:
    const idx: usize = @intCast(usize, i);
    // `idx` proved < s.len; bare ptr-indexing:
    return s.ptr[idx];
}
```

No `if (i < 0)` for the `.to_uint()` check; no bounds check on
`s[idx]`. Both range obligations have been discharged
statically.

### A second example, with `number → uint`

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

Both the cast and the bounds are discharged by narrowing. The
emission is a bare `@intFromFloat(usize, @floor(f))` — no NaN
check, no negative check, no range check.

### Why this matters

This is what makes A7's conversions **both safe and free**.
The fallible-method shape (`?T` return) gives the type-system
proof; the prover-driven emission ensures the runtime cost is
paid only when the prover cannot discharge. In typical code
(loop-bounded conversions, post-guard conversions, literal
conversions), the cost is zero.

This is exactly the discipline of CA's bare arithmetic
specialisation (D.003): the contract is "safe by default"; the
implementation specialises when it can prove safety.

### Without narrowing, what would the emission be?

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

Three extra branches; two of them dead. The narrowing analysis
removes them.

---

## What happens when narrowing CAN'T discharge

Under the revised principle (D.025): the operation **does not
compile**. The user adds a guard, and on the next compile the
narrowing system discharges the precondition.

```a7
process_opaque :: fn(s: []int, i: int) int {
    // no early-return guard; i could be anything
    idx := cast(uint, i)              // compile error: i may be negative
    ret s[idx]                         // compile error: idx not in bounds
}
```

The diagnostics tell the user exactly what guard to add:

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

The user is **never silently given a runtime trap**; the
compiler refuses the unsafe code and tells them how to fix it.

---

## Compile-time conversion: literals

Numeric literals get a special path. `42` is "an integer
literal with comptime value 42." It converts to any numeric
target whose range covers 42, **without any runtime work and
without using any conversion method**:

```a7
let x: int = 42
let y: uint = 42                       ; literal fits uint range; no method needed
let z: number = 42                     ; literal converts to number losslessly
```

For non-literal expressions involving only literals, the same
applies: `let n: uint = 10 * 5` compiles because `10 * 5 = 50`
fits `uint`.

This is **compile-time const folding** at the conversion site.
Matches Zig's `comptime_int` semantics. The user writes plain
integer literals everywhere; the compiler figures out the type
from context.

---

## String formatting

`x.to_string()` is the universal format method. Every built-in
type provides it. For more control, `x.format(spec)` takes a
format-spec string:

```a7
let s1 = 42.to_string()                ; "42"
let s2 = 3.14.to_string()              ; "3.14"
let s3 = 255.format("hex")             ; "ff"
let s4 = 0.123.format("0.4f")          ; "0.1230"
```

The format-spec syntax can be Python-style or Rust-style; the
specific syntax is a stdlib detail, not a Cluster CB decision.

`f"..."` interpolation (CA D.008) uses `.to_string()` on each
interpolated value implicitly.

---

## String parsing

Four parsing methods on `string`:

| Method | Return | Notes |
| --- | --- | --- |
| `s.parse_int() -> ?int` | none for invalid input | Decimal only by default |
| `s.parse_uint() -> ?uint` | none for invalid or negative | Decimal only |
| `s.parse_number() -> ?number` | none for invalid | Decimal-point or scientific notation |
| `s.parse_bool() -> ?bool` | `"true" → some(true)`, `"false" → some(false)`, otherwise none | |

For radix parsing (hex, octal, binary), additional methods:

| Method | Return | Notes |
| --- | --- | --- |
| `s.parse_int_radix(r: uint) -> ?int` | `r ∈ [2, 36]` | Hex via `parse_int_radix(16)` |

This is the minimal v1 surface. The user can write their own
parser for richer parsing.

---

## Comparison to Cluster CA's `?T` discipline

Cluster CA decided:
- `?T` is sugar for `Option<T>` (D.010).
- No `unwrap()` / `expect()` (D.018).
- `?` postfix propagation (D.017).
- Minimal combinators: `.map()`, `.unwrap_or()` (D.019).

Conversions fit cleanly:
- Every fallible conversion returns `?T`.
- The user matches, propagates with `?`, or uses `.unwrap_or(default)`.
- No new operators or keywords.

Example chaining:

```a7
fn read_age(s: string) -> uint
    return s.trim().parse_uint().unwrap_or(0)
end

fn read_name_age(s: string) -> ?(string, uint)
    let parts = s.split(",")
    if parts.length != 2
        return none
    end
    let name = parts[0].trim()
    let age = parts[1].trim().parse_uint()?
    return some((name, age))
end
```

Reads like TypeScript with stricter types.

---

## FFI bit-width conversions (special case)

Inside an `extern fn` shim, the warning on bit-width types (CA
D.002) is suppressed. Conversions between the FFI types and the
primary types use the same method-style:

```a7
extern fn c_get_count() -> i32

; The shim wraps the foreign call:
fn read_count() -> ?uint
    let raw: i32 = c_get_count()       ; FFI return type
    return raw.to_uint()               ; ?uint; fails if raw < 0
end
```

Inside the shim, `i32 → uint` is just another fallible numeric
conversion. The CA D.002 warning is silenced at this site
(scoping via the shim's attribute, exact syntax in CF).

---

## Enum-discriminant conversions

Enums have a built-in discriminant relationship:

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

The discriminant is a numeric value the user can choose
(default: sequential from 0). `from_discriminant` is fallible
because user input may not match a valid value.

---

## Compile-time vs. runtime semantics summary

| Conversion | When the check happens |
| --- | --- |
| Literal `42 → uint` | Compile time; no code emitted |
| `42 → uint` via `.to_uint()` | Compile time; literal recognised |
| `x.to_uint()` where `x` is range-proved `>= 0` | Compile time; emission is bare cast |
| `x.to_uint()` where `x` is opaque | Runtime branch; `?uint` return contract |
| `s.parse_int()` | Runtime parse; always returns `?int` |
| `s.to_string()` | Runtime format; always succeeds |
| `r.bits()` (float→int reinterpret) | Compile-time eligible (no failure mode) |

The compile-time / runtime split is **invisible to the user** —
they write the same method-call regardless. The optimisation is
purely an emission detail.

---

## How A7's conversions compare to other languages

| Language | Lossless | Lossy (truncating) | Reinterpret | Fallible |
| --- | --- | --- | --- | --- |
| **Python** | `int(x)` (raises) | `int(x)` (truncates) | none | (use `try/except`) |
| **JavaScript** | `Number(x)` (NaN on fail) | `parseInt(x)` | `Float32Array` hacks | (returns NaN) |
| **Swift** | `Int(x)` (traps on overflow) | `Int(truncating: x)` | `unsafeBitCast` | `Int(exactly: x)` returns `Int?` |
| **Kotlin** | `x.toLong()` | `x.toInt()` (truncates) | `Float.fromBits` | `s.toIntOrNull()` |
| **Rust** | `T::from(x)` | `x as T` (truncates) | `mem::transmute` | `T::try_from(x)` returns `Result` |
| **Ada** | `Integer(X)` (range-checked) | n/a | `Unchecked_Conversion` | range-check raises |
| **Zig** | `@as(T, x)` (lossless only) | `@intCast(T, x)` | `@bitCast(T, x)` | n/a (traps if out-of-range) |
| **A7 proposed** | `.to_T()` (when lossless) | `.to_T_trunc()`, `.to_T_floor()`, etc. | stdlib helpers only | `.to_T() -> ?T` for fallible |

A7's choice — method-style with `?T` for fallibility — is
closest to Kotlin. The difference: A7's compiler discharges most
fallible-conversion runtime checks via narrowing.

---

## Open questions for Cluster CB

Each becomes a numbered decision.

- **Q1** Should `int(x)` constructor-style **also** exist
  alongside `.to_int()`? My lean: no. One way to do it.
- **Q2** Exact list of rounding methods on `number`. My lean:
  the four documented above (`trunc`, `floor`, `round`,
  `exact`).
- **Q3** Format-spec syntax for `.format(spec)`. Defer; stdlib
  detail.
- **Q4** Should `string` provide `.bytes() -> []u8` for direct
  byte access? My lean: yes; cheap and useful at FFI boundary.
- **Q5** Should `bool` interpolate as `"true"` / `"false"` in
  `f"..."` strings? My lean: yes.
- **Q6** Generic-context conversion. `fn f<$T>(x: $T) -> ?$U`
  where the body calls `x.to_$U()` — does this work? Depends
  on whether the type-set constraint declares the method.
- **Q7** Should there be an explicit `.into<T>()` polymorphic
  conversion (Rust style)? My lean: no in v1; can be added
  if needed.
- **Q8** `bit_cast`-style helpers — exactly which ones in the
  stdlib? `f32.bits()`, `f64.bits()`, `u32.as_f32()`,
  `u64.as_f64()`. Maybe `u8 ↔ char` for ASCII work.

---

## What's removed from the audit's plan

The original `01-cast.md` proposed three operators: `cast` /
`truncating_cast` / `bit_cast`. All three are **out** under
Cluster CA + this proposal:

- `cast` keyword removed entirely (D.038 in CB).
- `truncating_cast` doesn't exist; truncation is explicit per
  rounding method (`to_int_trunc()`).
- `bit_cast` is replaced by stdlib helpers (D.034 in CB).

Net language size: **fewer operators**, **same expressiveness
via methods**, **stronger safety via the fallible-method
discipline**.

---

## Cluster CB decision shape

The Cluster CB section in `08-decisions.md` will codify:

- Method-style is the conversion shape (D.024).
- Fallible conversions return `?T` (D.025).
- The numeric method catalog (D.026–D.027).
- String formatting and parsing (D.028–D.029).
- Bool/numeric forbidden (D.030).
- Array/slice/enum/FFI conversions (D.031–D.033).
- No `bit_cast` operator (D.034).
- Compile-time literal conversion (D.035).
- Generic-context conversion (D.036).
- Forbidden-conversion diagnostics (D.037).
- `cast(T, x)` keyword removed (D.038).
- Narrowing-driven check elision (D.039).

12–15 decisions. All marked PROPOSED. Cross-references back
to CA where relevant.
