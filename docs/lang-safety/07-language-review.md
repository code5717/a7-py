# 07 — A7 Language Review against the Zero-Runtime-Error Contract

> Status: historical audit, added in commit 86819f5 (2026-05-11). Its "Today"
> text describes the code before the safety-proof overhaul in that same
> commit, so several findings are now stale; dated notes mark them. Newer user
> decisions live in [`docs/plan/decisions.md`](../plan/decisions.md) and
> override proposals here.

Part of the `docs/lang-safety/` series; see the [README](./README.md) for the
map. Siblings: [01 — InvisiCaps](./01-invisicaps.md) ·
[02 — Sanitizers](./02-sanitizers.md) ·
[03 — Hardware-assisted safety](./03-hardware.md) ·
[04 — Comparison](./04-comparison.md) ·
[05 — Take-aways for A7](./05-for-a7.md) ·
[06 — Compile-time techniques](./06-compile-time-safety.md).

This file audits A7 (the `a7/` codebase and `docs/SPEC.md`) against the
zero-runtime-error contract in [05](./05-for-a7.md). That contract requires the
emitted Zig to be memory-safe under `-O ReleaseFast`, where Zig disables every
runtime check. At the time of the audit, A7 output was not safe under
`-O ReleaseFast`.

Files 01–06 describe the target. This file describes the state at audit time
and the changes needed. Section 4 gives the change order.

How to read the code blocks: "Current A7" means the syntax compiles in today's
grammar; any stated behavior comes from reading the code, not from running the
compiler, unless the block says otherwise. "Proposed" means syntax from the
proposal that A7 does not accept.

## 0. Executive summary

| # | § | Gap | Behavior at audit time | Severity | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | 1.1 | `ref T` is nullable by default | Emits `?*T`; every deref is `.?.*` (Zig panics on null in safe modes) | Critical | S |
| 2 | 1.2 | `cast(T, x)` is unrestricted, including int↔ptr | UB under `-O ReleaseFast` | Critical | S |
| 3 | 1.3 | Indexing emits bare `s[i]` with no bound proof | Zig panic in safe modes, UB in fast | Critical | M |
| 4 | 1.4 | Integer `+`, `-`, `*` emit bare Zig operators | Trap or wrap depending on Zig mode; UB under `-O ReleaseFast` | Critical | M |
| 5 | 1.5 | Integer division emits `@divTrunc` / `@rem` with no non-zero proof | Zig panic in safe modes, UB in fast | Critical | S |
| 6 | 1.6 | No definite-assignment check | Uninitialized reads return zero silently | High | S |
| 7 | 1.7 | `del` has no aliasing or move check | Double free and use after free possible | High | L |
| 8 | 1.8 | No `Option<T>` / `Result<T, E>` | Failure can only be modeled through nullable `ref T` | High | M |
| 9 | 1.11 | Floats freely produce NaN / inf | Silent propagation through arithmetic | Medium | M |
| 10 | 1.10 | No stack-budget proof | Stack overflow possible even though recursion is banned | Medium | S |
| 11 | 1.12 | No FFI boundary | Out of scope; documented for the future | Low | n/a |
| — | 1.9 | No refinement types | Enabler for rows 3, 4, 5 and 9; no severity was assigned | — | M |

S = small (1–2 weeks), M = medium (3–6 weeks), L = large (months).

Rows 1–5 are Critical. They are prerequisites for any honest "zero runtime
errors" claim. Until they ship, the contract is aspirational.

Note (2026-09-16): the original text said "four Critical rows (1, 2, 3, 4, 5)"
and "12 gaps" while the table had 11 rows. Five rows are Critical. The § column
and the §1.9 row were added so the table matches sections 1.1–1.12.

### Re-check at 2026-09-16

A spot-check of the current source, by reading code only. The compiler was not
run for this re-check.

| § | Current state | Where | Ledger |
| --- | --- | --- | --- |
| 1.1 | Still lowers to `?*T` and `.?.*`, but each deref now needs a non-nil proof | `a7/safety.py:610-629`, `a7/backends/zig.py:1728-1742`, `2101-2104` | Memory plan removes stored `ref` and `nil` (M4) |
| 1.2 | Casts touching references or functions are forbidden; `UNSAFE_CAST` is emitted | `a7/cast_classifier.py:40-41`, `a7/safety.py:522-554`, `a7/backends/zig.py:1751-1756` | D.024 / D.038 conflict open under gate G3 |
| 1.3 | Each index needs a proof; the proof needs a statically known length | `a7/safety.py:567-574`, `602-608`; `a7/backends/zig.py:1670-1686` | — |
| 1.4 | Overflow obligation exists but returns early; no check | `a7/safety.py:631-646`; Zig op map `a7/backends/zig.py:2323-2328` still `+`, `-`, `*` | L5: `+ - *` wrap |
| 1.5 | Division and remainder need a non-zero divisor proof | `a7/safety.py:559-565`; emission `a7/backends/zig.py:1567-1585` | Remaining division rules in gate G3 |
| 1.6 | No definite-assignment analysis found | — | Memory plan gate M34: reject |
| 1.7 | Direct reads after `del` are rejected; aliasing and double free are not | `a7/safety.py:724-737`; `docs/SPEC.md:1070-1078` | Memory plan removes `del` (M3); L6 |
| 1.8 | Unchanged | — | Memory plan §2: optionals replace `nil` |
| 1.10 | No stack-budget analysis found | — | Memory plan §4 call-graph rule |
| 1.11 | Unchanged | — | L16: IEEE floats, NaN and inf are ordinary values |
| 1.12 | Unchanged | — | Memory plan gate M12 |

All `build/debug/zig/src/*.zig:N` citations below point at regenerated build
artifacts. Their lines no longer match (for example, `013_pointers.zig:9` is now
`pub fn main`).

## 1. Per-feature audit

Each item gives the behavior at audit time with file:line citations, the
contract requirement, and the proposed change.

### 1.1 Pointer types — `ref T` is nullable by default

**Today.** `ref T` parses as `TYPE_POINTER` (`a7/parser.py:743-751`), is modeled
by `ReferenceType` (`a7/types.py:210-226`), may hold `nil`
(`a7/passes/type_checker.py:727-733`), and lowers to Zig's optional pointer
`?*T` (`a7/backends/zig.py:1682-1688`). Every deref is emitted as `.?.*`
(`build/debug/zig/src/013_pointers.zig:9`). Under `-O ReleaseSafe`, `.?` traps
on null. Under `-O ReleaseFast`, dereferencing a null `?*T` is undefined
behavior.

Note (2026-09-16): parser and type citations still hold (`a7/parser.py:744-751`,
`ReferenceType` at `a7/types.py:211`). `?*T` lowering is now at
`a7/backends/zig.py:2101-2104`, and `.?.*` at `1735` and `1742`. Each deref now
goes through `_prove_ref_non_nil` (`a7/safety.py:610-629`), which reports
"reference may be nil" when no fact proves otherwise. The nullable type itself
is unchanged.

```a7
// Current A7 (syntax). Per the audit: accepted, lowered to .?.*
// Rejected at HEAD (compiled 2026-09-16), exit 6: "reference must be proven
// non-nil before field access through it: reference may be nil".
io :: import "std/io"

Box :: struct {
    value: i32
}

main :: fn() {
    b: ref Box = nil
    io.println("{}", b.value)
}
```

**Contract requirement.** [05 §1, §4.8.1–4.8.2](./05-for-a7.md). Non-null
pointer types lower to Zig `*T`, and deref is `p.*` with no `.?`. Nullable
pointers are a distinct type that cannot be dereferenced without an explicit
pattern match.

**Proposed change.**

1. Add `?ref T` (nullable) and keep `ref T` (non-null). Token change in
   `a7/tokens.py`; grammar change in `a7/parser.py` (an optional `QUESTION`
   before `REF`).
2. Give `ReferenceType` a `nullable: bool` flag, or add
   `OptionalReferenceType`. Update `equals`, `is_assignable_to` and `unify`.
3. Only `?ref T` can hold `nil`. The `nil` literal has type `?ref Never` and
   unifies with any `?ref T`.
4. Dereferencing `?ref T` is an error; the user must `match` it.
5. Codegen: emit `*T` for `ref T` and `?*T` for `?ref T`. A `match` on `?ref T`
   becomes Zig's `if (p) |val| ... else ...`. Deref of `ref T` becomes `p.*`.

```a7
// Proposed
b: ?ref Box = nil          // only ?ref T may hold nil
match b {
    case some(r): io.println("{}", r.value)
    else: io.println("no box")
}
```

**Migration.** Every `ref T` that can be `nil` becomes `?ref T`. This breaks the
surface language. Audit `a7/stdlib/*.py` and `examples/013_pointers.a7`.

Note (2026-09-16): the [memory plan](../plan/memory.md) proposes removing `nil`
and stored or returned `ref` in favor of optionals (gate M4). `ref` would stay
only as a parameter. None of this is approved.

### 1.2 Cast — unrestricted and admits int↔ptr

**Today.** `cast(T, x)` parses as a general cast. The type checker resolves the
target type and operand but does not check that the cast is safe:
integer-to-pointer and pointer-to-integer both compile
(`a7/passes/type_checker.py:1800-1805`). `INVALID_CAST` and `UNSAFE_CAST` are
defined in `a7/errors.py:148-149` but never emitted. The Zig backend emits
`@as(TargetType, value)`, which coerces or reinterprets depending on the types
(`a7/backends/zig.py:1690-1695`).

This was the most serious finding. Parts of `01-invisicaps.md` §17 and
`05-for-a7.md` §2 claim "A7 has no `inttoptr` operation." That claim was false:
`cast(ref T, some_usize)` compiled and produced an arbitrary pointer.

```a7
// Current A7 (syntax). Per the audit: compiled and forged a pointer
// Rejected at HEAD (compiled 2026-09-16), exit 6: "casts involving
// references or functions are forbidden".
main :: fn() {
    n: usize = 16
    p := cast(ref i32, n)
}
```

Note (2026-09-16): this gap is closed at HEAD by code reading. `visit_cast`
moved to `a7/passes/type_checker.py:1876` and records types only.
`a7/cast_classifier.py:40-41` forbids any cast that involves a reference or
function type. `a7/safety.py:522-554` turns a forbidden decision into an
`UNSAFE_CAST` error, and `a7/backends/zig.py:1751-1756` refuses to emit a cast
without an approved decision. Error codes are now at `a7/errors.py:149-150`.
The historical ranking below is kept as written.

**Contract requirement.** [05 §1, §4.8](./05-for-a7.md). The language must not
admit operations that forge pointers or confuse pointer and integer types.

**Proposed change.**

1. Classify casts in `a7/passes/type_checker.py`:

   | Class | Examples | Form |
   | --- | --- | --- |
   | Lossless widening | `i32 → i64`, `u8 → u16`, `i32 → f64` | `cast(T, x)` |
   | Lossy narrowing | `i64 → i32` | `truncating_cast(T, x)`: a runtime fit check that becomes a compile error when the prover can decide it statically, or a `?T` result |
   | Same-size non-pointer reinterpretation | `f32 ↔ u32` | `bit_cast(T, x)`; never for pointers |
   | Forbidden | any cast involving a pointer | except `ref T → ?ref T` (always) and `?ref T → ref T` (only after a `match` removes null) |

2. `cast(T, x)` covers only lossless widening. Everything else uses an explicit
   form. Emit `INVALID_CAST` / `UNSAFE_CAST`.
3. Backend: widening uses `@as`, truncating uses `@truncate`, `bit_cast` uses
   `@bitCast`. Integer↔pointer reinterpretation is never emitted because the
   front end rejects it.

```a7
// Proposed
wide := cast(i64, small)              // lossless only
low := truncating_cast(u8, count)     // explicit narrowing
bits := bit_cast(u32, ratio_f32)      // same size, non-pointer
```

**Migration.** Classify every `cast(...)` in the examples (`examples/015_types.a7`
and others). Most are widening. Remove any pointer↔integer casts.

**Do this first.** A language that allows a reinterpret cast from `usize` to
`ref T` has no memory-safety claim.

Note (2026-09-16): the ledger lists D.024 and D.038 (keep versus remove
`cast`) as contradictory and supersedes both; cast policy is open under gate
G3 ([decisions](../plan/decisions.md)). The memory plan also removes
`cast(ref T, value)` from the public surface.

### 1.3 Slice / array indexing — no bound proof

**Today.** `s[i]` for `s: []T` requires `i: usize` or a non-negative integer
literal (`a7/passes/type_checker.py:1680-1690`). The backend emits `s[i]`
directly (`a7/backends/zig.py:1638-1645`) with no bounds analysis. The same
holds for `[N]T`; `build/debug/zig/src/012_arrays.zig` uses `numbers[i]`. Under
`-O ReleaseSafe` Zig traps out of bounds; under `-O ReleaseFast` it is undefined
behavior.

Note (2026-09-16): `visit_index_expr` is now at
`a7/passes/type_checker.py:1677`, with `_validate_index_bound` at `1717`.
`_emit_index` is at `a7/backends/zig.py:1670-1686` and requires backend
approval. `_prove_index` (`a7/safety.py:567-574`) approves an index only when
the object's length is known statically (fixed arrays, or a tracked
`known_length`, `a7/safety.py:602-608`) and the index interval fits. So the
check exists but is partial: none of the four patterns below is implemented as
such. By this reading, the example below should be rejected because a slice
parameter has no known length; not run.

```a7
// Current A7 (syntax)
at :: fn(s: []i32, i: usize) i32 {
    ret s[i]
}
```

**Contract requirement.** [05 §3.5, §4.8.3–4.8.4](./05-for-a7.md). Every access
is either statically proved in bounds (so Zig can use `s.ptr[i]` with no check)
or goes through `try_get(i) -> ?T`, which emits an explicit `if`.

**Proposed change.**

1. Recognize four patterns in `a7/passes/type_checker.py`:
   - `for i in 0..s.length: s[i]` — the loop condition gives `i < s.length`.
   - `s[k]` with literal `k` and a slice with a refined upper bound.
   - `s[i]` after `if i < s.length` (flow-sensitive narrowing on the same
     `usize`).
   - `s[i]` where `i: Index(s.length)` (refinement type, §1.9).
2. Any other `s[i]` is a compile error. The user writes `s.try_get(i)`, which
   returns `?T`.
3. Backend: proved cases emit `s.ptr[i]`. `try_get` emits
   `if (i < s.len) some(s.ptr[i]) else null`.

```a7
// Proposed
at :: fn(s: []i32, i: usize) ?i32 {
    ret s.try_get(i)
}
```

**Migration.** Rewrite every `s[i]` in `examples/` and tests into a proved form
or `try_get`. Most loops already use `for i in 0..s.length`, so the work may be
mechanical.

### 1.4 Integer arithmetic — bare `+`, `-`, `*` emit Zig `+`

**Today.** `ADD`, `SUB` and `MUL` lower to Zig `+`, `-`, `*`
(`a7/backends/zig.py:1566`). Under `-O ReleaseSafe` these trap on overflow.
Under `-O ReleaseFast` overflow is undefined behavior; in practice it often
wraps silently.

Note (2026-09-16): the operator map is now `_binary_op_to_zig`
(`a7/backends/zig.py:2323-2328`), still plain `+`, `-`, `*`.
`_prove_integer_overflow` (`a7/safety.py:631-646`) returns immediately, with a
comment that range-safe arithmetic is left for follow-up. Ledger L5 later chose
wrapping `+`, `-`, `*` (Odin style), which replaces the checked-by-default
requirement below for those three operators. L5 is decided but not implemented:
wrapping would need Zig `+%`, `-%`, `*%`.

```a7
// Current A7 (syntax). 200 + 100 does not fit u8
add :: fn(a: u8, b: u8) u8 {
    ret a + b
}
```

**Contract requirement.** [05 §4.3, §4.8.6–4.8.8](./05-for-a7.md). Bare `+` is
allowed only when operand ranges prove no overflow. Otherwise the user chooses
`checked_add`, `wrap_add` or `sat_add`.

**Proposed change.**

1. Track integer ranges in the type checker: a small refinement lattice where
   `u32` starts as `[0, 2^32-1]` and narrows through loop induction, `if`
   conditions and arithmetic.
2. For each `+`, `-`, `*` and `<<`: if operand ranges prove the result fits,
   emit the Zig operator. Otherwise report a compile error that suggests
   `a.checked_add(b)`, `a.wrap_add(b)` or `a.sat_add(b)`.
3. Stdlib methods (`a7/stdlib/math.py` or a new module) provide the three forms.
   The backend lowers them to `@addWithOverflow`, `+%` and `+|`.

```a7
// Proposed (superseded for + - * by L5)
sum := a.checked_add(b)    // ?u8
wrapped := a.wrap_add(b)
clamped := a.sat_add(b)
```

**Migration.** Most example arithmetic runs in proved ranges (loop counters,
small constants). A real subset needs explicit `checked_*` calls.

### 1.5 Integer division — emits `@divTrunc(a, b)` with no `NonZero` proof

**Today.** Integer `a / b` emits `@divTrunc(a, b)` and `a % b` emits
`@rem(a, b)` (`a7/backends/zig.py:1550-1558`). Neither the type checker nor the
backend checks `b != 0`. Under `-O ReleaseSafe` Zig traps; under
`-O ReleaseFast` division by zero is undefined behavior.

Note (2026-09-16): emission is now at `a7/backends/zig.py:1567-1585`, behind
backend approval. `_prove_nonzero_divisor` (`a7/safety.py:559-565`) reports
"divisor may be zero" unless a fact proves the divisor non-zero. No `NonZero`
type exists, and signed `MIN / -1` is not handled. By this reading the example
below is rejected; not run.

```a7
// Current A7 (syntax)
ratio :: fn(a: i32, b: i32) i32 {
    ret a / b
}
```

**Contract requirement.** [05 §4.1, §4.8.5](./05-for-a7.md). The divisor must
have type `NonZero<T>`. A plain integer cannot be a divisor.

**Proposed change.**

1. Add `NonZero<T>` as a lite refinement type: no SMT, only a constructor that
   returns `?NonZero<T>`.
2. `/` and `%` accept only a `NonZero<T>` right operand. A plain integer is a
   compile error that suggests `NonZero::new(b)` and a `match`.
3. For signed division, also exclude `-1` to avoid `INT_MIN / -1`, through a
   `SafeDivisor<T>` or an extra constructor check.
4. Backend: emit `@divTrunc(a, d.value)` / `@rem(a, d.value)`. The type removes
   the need for a runtime zero check.

```a7
// Proposed
ratio :: fn(a: i32, b: i32) ?i32 {
    match NonZero::new(b) {
        case some(d): ret a / d
        else: ret none
    }
}
```

**Migration.** Audit every `/` and `%`. Most use literal denominators (free) or
loop-invariant denominators that can be wrapped in `NonZero` once.

Note (2026-09-16): L5 excludes division, remainder and `MIN / -1`; these are
open under gate G3.

### 1.6 Definite assignment — currently absent

**Today.** Variables may be declared without an initializer
(`buffer: [1024]u8`). The backend lets Zig handle default initialization.
`a7/passes/type_checker.py` has no pass that tracks whether a variable is
written before it is read. `build/debug/zig/src/002_var.zig:22-23` showed
`const value: i32 = 0;` for an uninitialized A7 variable: silent zero.

Note (2026-09-16): no definite-assignment analysis was found in `a7/passes/` or
`a7/safety.py`. The memory plan records that a read after a zero-iteration loop
is accepted today and proposes rejecting it (gate M34).

```a7
// Current A7 (syntax). No path check: x may be read unassigned
pick :: fn(flag: bool) i32 {
    x: i32
    if flag {
        x = 1
    }
    ret x
}
```

**Contract requirement.** [05 §3.1, 06 §1](./06-compile-time-safety.md#1-definite-assignment--flow-analysis).
Reading an unassigned local is a compile error.

**Proposed change.**

1. Add a definite-assignment pass in `a7/passes/semantic_validator.py`, reusing
   the control-flow plumbing of the recursion check.
2. Compute each variable's assignment state per basic block. A read where the
   variable is not definitely assigned is an error.
3. Drop silent zero initialization. Emit storage at the assignment site (Zig
   supports `var x: i32 = undefined; x = compute();`).

**Migration.** Code that declares `buf: [1024]u8` and writes before reading
still works. Code that reads an uninitialized local must add an initializer.

### 1.7 `del` — no aliasing, no move check

**Today.** `del p` frees a heap reference. The type checker confirms the operand
is a reference. Nothing checks that `p` is unique, that no other reference
aliases the allocation, or that `p` was not already deleted. `docs/SPEC.md:1067`
says lifetime analysis is "not yet implemented".
`build/debug/zig/src/011_memory.zig:17` showed a generated
`defer if (value_ptr) |p| allocator.destroy(p)`, but A7 had no use-after-free
prevention.

Note (2026-09-16): the original cited `a7/docs/SPEC.md`; the file is
`docs/SPEC.md`, and the text is now at lines 1070-1078. `a7/safety.py:724-737`
now marks a deleted identifier as moved and rejects later reads of that same
binding ("direct reads after `del` are rejected", `docs/SPEC.md:1071-1072`).
Aliases and double free remain unchecked (`docs/SPEC.md:1077-1078`).

```a7
// Current A7 (syntax)
main :: fn() {
    b := new Box
    if b != nil {
        q := b
        del b
        io.println("{}", q.value)    // alias read: the direct-read check tracks only `b` (code reading; not run)
    }
}
```

**Contract requirement.** [05 §3.3–§3.4](./05-for-a7.md). Affine ownership:
`del` consumes the value and later uses are compile errors. Aliasing is
prevented by making references non-storable except through the type system,
typically only as `inout` / `borrow` parameter modes.

**Proposed change.** Large; see
[05 §5 Phase 3](./05-for-a7.md#5-phased-plan-zero-runtime-error-ordering).

1. Move analysis pass in `a7/passes/`: each `ref T` binding has a consumed flag.
   Passing by value, returning, storing in a field or `del` consumes it. Using a
   consumed binding is an error.
2. Parameter modes `inout` and `borrow`, allowed only on parameters, never on
   variables or fields. A `borrow` is read-only and cannot escape. An `inout`
   is unique within the function.
3. Call-site exclusivity: no two `inout`/`borrow` arguments of one call may
   name the same allocation.
4. Backend: emit `*T` / `*const T` for `inout` / `borrow`. The static guarantee
   is the point; emission is otherwise unchanged.

```a7
// Proposed (not accepted; see note)
release :: fn(p: consume ref Box) {
    del p
}

main :: fn() {
    b := new Box
    release(b)
    io.println("{}", b.value)    // compile error: b was consumed
}
```

**Migration.** This is the largest design change. Code with manual `del` must
rely on scope-exit drop or move values through return chains. Patterns such as
building a transient buffer and handing it off need region-style scopes.

Note (2026-09-16): the original pointed to "§1.10" for region-style scopes, but
§1.10 covers the stack budget; no section in this file covers regions. The
parameter-mode keywords (D.040, D.041, D.049) were not accepted. Ledger L6
approves immutable argument bindings only, with no mode syntax. The
[memory plan](../plan/memory.md) makes ownership internal and proposes removing
`del` from ordinary code (gate M3). See also
[parameter-modes.md](./parameter-modes.md).

### 1.8 No `Option<T>` / `Result<T, E>` — fallibility is unmodelled

**Today.** A7 has no `Option<T>` or `Result<T, E>`. The only nullability is the
implicitly nullable `ref T` (§1.1). The only way to signal failure is to abuse
nullable references.

**Contract requirement.** [05 §1, §4.1–§4.7](./05-for-a7.md). Every fallible
operation returns `?T` or `Result<T, E>`, unwrapped with `match`.

**Proposed change.**

1. Add two generic types to `a7/stdlib/`:
   - `Option<$T>` with variants `some($T)` and `none`.
   - `Result<$T, $E>` with variants `ok($T)` and `err($E)`.
2. Add `?T` as sugar for `Option<T>`. Whether `?ref T` is sugar for
   `Option<ref T>` or a distinct shape is an open decision (§5).
3. `?T` and `Result<T, E>` must be matched before the inner value is used.
4. Backend: lower to tagged unions. `?T` lowers to Zig `?T` when `T` is a
   pointer, otherwise to `union(enum) { some: T, none: void }`.

```a7
// Proposed
parse_digit :: fn(c: u8) Result<u8, ParseError> {
    if c >= '0' and c <= '9' {
        ret ok(c - '0')
    }
    ret err(ParseError.not_a_digit)
}
```

**Migration.** Code that uses `ref T` to mean "might be absent" switches to `?T`
or `?ref T`. New fallible stdlib functions (parse, divide, allocate, index)
return `Option<T>` / `Result<T, E>`.

Note (2026-09-16): the memory plan §2 also uses optionals for absence instead of
`nil` references. The exact syntax is not approved.

### 1.9 Refinement types — currently absent

**Today.** A7 has primitives, slices, arrays, references, structs, enums, tagged
unions, function types and generics (`a7/types.py`). It has no refinement types
such as `{x: int | x > 0}`.

**Contract requirement.** [05 §3.5, 06 §10](./06-compile-time-safety.md#10-refinement-types).
A small refinement vocabulary is needed for proved indexing, non-zero divisors,
finite floats and proved-range arithmetic.

**Proposed change.** A lite version, not full SMT integration:

1. Add named refinements to `a7/types.py`:

   | Refinement | Meaning |
   | --- | --- |
   | `Index($n)` | `{i: usize \| i < $n}`, where `$n` is a compile-time-bound `usize` |
   | `NonZero<$T>` | `{x: $T \| x != 0}` |
   | `Fin<$F>` | `{x: $F \| !is_nan(x) && !is_inf(x)}` |
   | `Bounded<$T, $lo, $hi>` | arithmetic ranges |

2. Each refinement is a struct with a private `value` field and constructors
   that return `?Self`.
3. `+`, `/` and `[]` accept refined types where appropriate.
4. The type checker does pattern recognition, not theorem proving. The four `[]`
   patterns (§1.3) and the range tracker (§1.4) follow from this.

**Why not full refinement types?** Liquid-Haskell-style refinement needs a
bundled SMT solver, which conflicts with keeping the compiler simple. The lite
version covers most cases directly.

Note (2026-09-16): the original examples use `int`; ledger L4 removes `int` in
favor of explicit widths.

### 1.10 Stack budget — no proof, can still overflow

**Today.** A7 bans recursion (`a7/passes/semantic_validator.py:501-544`), so
the call graph is a DAG. The compiler does not compute maximum stack depth, and
the runtime does not set `RLIMIT_STACK` to a static bound. Deep non-recursive
call chains or large stack arrays can still overflow.

Note (2026-09-16): the recursion check is still at
`a7/passes/semantic_validator.py:501-532`. No stack-budget analysis was found.
The memory plan §4 notes that the bound also depends on stored function values
staying non-recursive (v1 gate G4), and proposes moving large values off the
native stack (gate M35).

**Contract requirement.** [05 §4.4](./05-for-a7.md). The compiler computes the
maximum stack depth, so the program cannot overflow its stack.

**Proposed change.**

1. Add a stack-budget pass after type checking. Compute each function's frame
   size (sum of local sizes plus a spill estimate). The program's maximum stack
   is the largest sum of frame sizes along any call-graph path.
2. Add `--stack-budget BYTES` (default 1 MiB). Reject programs that exceed it.
3. Emit a `comptime` assertion in the generated Zig and pass the computed budget
   as the thread stack size in `main`.

```a7
// Current A7 (syntax). Not recursive, but each frame holds 1 MiB
fill :: fn() u8 {
    buf: [1048576]u8
    buf[0] = 1
    ret buf[0]
}
```

**Migration.** Transparent for almost all examples. A deliberately deep program
may fail, which is intended.

### 1.11 Floating-point — NaN / inf flow silently

**Today.** `f32` and `f64` arithmetic uses Zig operators directly
(`a7/backends/zig.py:1556-1557`). NaN and infinity are valid values and
propagate without any signal. Comparisons with NaN return false. Converting NaN
to an integer is undefined behavior under `-O ReleaseFast`.

Note (2026-09-16): ledger L16 chose IEEE 754 floats: NaN and infinity are
ordinary values, following Zig and C. That replaces the requirement below as a
language default. Float-to-integer casts now need a proof, which only a finite
integral literal satisfies (`a7/safety.py:522-554`, `654-662`).

**Contract requirement.** [05 §4.6](./05-for-a7.md). Either `f64` is a sum type
whose `nan` / `inf` cases must be matched, or a refined `Fin<f64>` type serves
code that needs total arithmetic.

**Proposed change.**

1. Add `Fin<f64>` and `Fin<f32>` refinements (§1.9).
2. Operations on `Fin<T>` that can produce a non-finite result (division, sqrt
   of a negative, log of zero, `inf - inf`) return `?Fin<T>`.
3. Plain `f64` still works for arithmetic that stays in `f64`. Conversion to an
   integer is `int_from(f: f64) -> ?int`.

**Severity** is Medium because few examples do float arithmetic; the gap is
forward-looking.

### 1.12 FFI — explicitly absent

**Today.** A7 has no `extern` keyword and no foreign-function syntax.

**Contract requirement.** [05 §4.7](./05-for-a7.md). FFI is the single boundary
where the language stops enforcing. Each foreign function returns
`Result<T, ForeignError>`; the shim is a small Zig wrapper that the compiler
treats as opaque.

**Proposed change.** Defer. Document in `docs/STATUS.md` that future FFI must
follow the §4.7 boundary rules.

Note (2026-09-16): the memory plan's gate M12 proposes native-boundary
descriptors that declare borrowing, retention and returned storage.

## 2. What A7 already does right

Keep these properties:

- **Recursion is banned** (`a7/passes/semantic_validator.py:501-544`). The stack
  budget (§1.10) depends on the call graph being a DAG.
- **No `unsafe` block or escape hatch.** Adding one would break the contract.
- **No `inttoptr` syntax.** At audit time `cast` admitted the equivalent (§1.2).
- **No raw pointer arithmetic.** Public A7 has no address-of or dereference
  syntax; reference lowering is internal to the compiler.
- **Heap fixed arrays (`new [N]T`) are rejected** (`CLAUDE.md`,
  `docs/STATUS.md`). Keep that until the language model is defined.
- **`match` exhaustiveness is checked** for enums and bools
  (`a7/passes/type_checker.py:1854-1858`). Extend it to tagged unions and
  option/result types when they land.
- **Type sets** via `@type_set(...)` give a base for the refinement-lite system
  (§1.9).
- **`usize` is enforced for indices** (`a7/passes/type_checker.py:1680-1690`).
- **No FFI**, so there is no boundary leakage yet.

Note (2026-09-16): the original cited `a7/CLAUDE.md`; the file is the
repository-root `CLAUDE.md`. Exhaustiveness checking is now
`_check_match_exhaustiveness` at `a7/passes/type_checker.py:2685`. Index
validation is at `a7/passes/type_checker.py:1677-1717`.

## 3. Things parsed-only / reserved that interact with safety

From `docs/STATUS.md` and `CLAUDE.md`:

- **Variadic parameters** parse but codegen rejects them. When implemented, use
  a typed `va_list` shape, not C's untyped form. Fil-C's experience
  ([01 §7 examples 27–29](./01-invisicaps.md#7-worked-examples-from-invisicaps_by_examplehtml))
  shows the hazards.
- **Intrinsics other than `@type_set`** (`@size_of`, `@align_of`,
  `@unreachable`, `@likely`) are reserved. `@unreachable` needs the
  proof-obligation rules in
  [05 §4.8.12](./05-for-a7.md#4812-no-unreachable-reached-at-runtime).
- **Multiple declarations and destructuring** parse but are not implemented.
  When they land, definite assignment (§1.6) must handle partial destructuring
  writes.
- **Multi-file lowering** (`docs/STATUS.md`). Once imports link across files,
  the type-confusion and ODR-mismatch hazards that Fil-C catalogues
  ([01 §7 examples 22–26](./01-invisicaps.md#7-worked-examples-from-invisicaps_by_examplehtml))
  apply. The language already makes no ODR assumptions, but the linker must
  trap, or better, the compiler must check that re-declarations match.

## 4. Recommended change order

Each step moves A7 closer to the contract and depends on the steps above it.

| Order | § | Change | Size and reason |
| --- | --- | --- | --- |
| 1 | 1.2 | Restrict `cast` | Highest priority; claiming memory safety while allowing reinterpret casts to pointers defeats itself. About one week |
| 2 | 1.1 | Split `ref T` and `?ref T` | Largest single safety win |
| 3 | 1.6 | Definite assignment | Easy; removes the silent-zero hazard |
| 4 | 1.5 | `NonZero` for division | Small |
| 5 | 1.10 | Stack budget | Small; answers "the program can still overflow its stack" |
| 6 | 1.4 | Typed arithmetic with range tracking | Medium |
| 7 | 1.3 | Bound-proved indexing and `try_get` | Medium |
| 8 | 1.8 | `Option<T>` / `Result<T, E>` | Medium |
| 9 | 1.9 | Refinement-lite types (falls out of §1.3, §1.4, §1.5, §1.11) | Medium |
| 10 | 1.7 | Affine ownership | Large; most expressive and most invasive |
| 11 | 1.11 | Float NaN / inf through `Fin<f>` | Medium |
| 12 | 1.12 | FFI boundary | When FFI is needed |

After steps 1–7, the operational test from
[05 §4.8.13](./05-for-a7.md#4813-no-panic-no-trap-no-__builtin_trap) should pass
for the existing examples: build each with `zig build-exe -O ReleaseFast`, run
the test corpus, observe zero crashes. Steps 8–10 extend the contract to more
expressive programs; steps 11–12 close residual gaps.

Note (2026-09-16): step 1 appears done in code (§1.2 note); steps 4 and 7 are
partly covered by the safety pass. L5 changes step 6 for `+ - *`, L16 changes
step 11, and the memory plan replaces step 10 with internal ownership. The
current v1 order is the gate list in [the v1 plan](../plan/README.md).

## 5. Open design questions

None blocks the early steps. Settle them before §1.7 lands.

- **Is `?ref T` a separate type, sugar for `Option<ref T>`, or both?** Zig chose
  a separate type with special syntax. Rust chose `Option` with niche
  optimization. Zig's approach is simpler to implement, since the current
  `ref T → ?*T` lowering already does it. Rust's is more uniform.
- **How do refinement types compose with generics?** A function that takes
  `xs: []T` and indexes `xs[i]` needs `i: Index(xs.length)`. Does `T` propagate?
  Probably not, because `Index($n)` ranges over `usize`, not `T`. Document it.
- **What is the syntax for an affine consume?** Rust moves implicitly; Hylo uses
  `consume`. Choosing early avoids later churn.
- **Where do range and refinement annotations live: on the type or as separate
  constraints?** Liquid Haskell puts them in comments. F* and Dafny put them on
  types. A7's parser already handles `@type_set(...)` on type parameters; the
  same machinery could carry `@range(lo, hi)` or `@nonzero`.
- **Diagnostics** largely decide whether a compile-time-safe language is usable.
  From the start of §1.3 and §1.4, give messages anchored to source locations
  with suggestions, for example: "`s[i]` cannot be proved in bounds; use
  `s.try_get(i)` or loop with `for i in 0..s.length`".

Note (2026-09-16): the consume-syntax question is superseded for user code. The
memory plan keeps ownership internal and has no user-visible consume keyword.

## 6. Closing

The codebase suits the contract in [05](./05-for-a7.md). The type system,
semantic validation and Zig codegen exist; the gaps are about tightening them,
not building new infrastructure.

At audit time the most urgent change was restricting `cast` (§1.2). Until it
landed, A7 could not claim memory safety under any backend flag.

Re-test the Zig backend under `-O ReleaseFast` after each change. The no-trap
codegen test in
[05 §4.8.13](./05-for-a7.md#4813-no-panic-no-trap-no-__builtin_trap) is the
operational definition of "this change preserved the contract".
