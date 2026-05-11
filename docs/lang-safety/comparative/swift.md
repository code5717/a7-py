# Comparative: Swift

> Phase B artifact in the `docs/lang-safety/` research process.

Swift is the **largest production deployment of
exclusivity-without-lifetimes**. Apple ships Swift on iOS, macOS,
and the rest of their platforms — billions of devices. Recent Swift
versions (5.9+, 6.0) added **noncopyable types** and **explicit
ownership conventions** (`borrowing`, `consuming`, `inout`) that
form the closest production parallel to Hylo's design — and
directly to A7's plan.

Where Hylo is the academic clean-slate, **Swift is the
incremental migration of an established language to the same
discipline** while preserving backwards compatibility with
reference-counted reference types. Worth studying because A7
faces the same migration challenge (its existing example corpus).

Primary sources:

- [Swift documentation](https://docs.swift.org/swift-book/)
- [SE-0390: Noncopyable structs and enums](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0390-noncopyable-structs-and-enums.md)
- [SE-0377: borrowing and consuming parameter ownership modifiers](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0377-parameter-ownership-modifiers.md)
- [SE-0432: Borrowing and consuming pattern matching](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0432-noncopyable-switch.md)
- [Law of Exclusivity (SE-0176)](https://github.com/apple/swift-evolution/blob/main/proposals/0176-enforce-exclusive-access-to-memory.md)
- [WWDC 2024 — "Consume noncopyable types in Swift"](https://developer.apple.com/videos/play/wwdc2024/10170/)

---

## The three parameter conventions

Swift declares ownership at the parameter level:

| Convention | Meaning | Caller still owns? |
| --- | --- | --- |
| `borrowing` | Shared, immutable access for the call | ✅ |
| `consuming` | Caller transfers ownership; cannot use after | ❌ |
| `inout`     | Exclusive, mutable access for the call | ✅ (post-call) |

For *copyable* types these have always been available with
slightly different names (`__shared`, `__owned`); SE-0377 made
them explicit and stable. For *noncopyable* types (SE-0390),
the convention must be stated because there's no default that's
always safe.

```swift
func process(borrowing buf: Buffer) { ... }  // can't mutate, can't consume
func handoff(consuming buf: Buffer) { ... }  // takes ownership
func update(inout buf: Buffer)     { ... }  // mutates in place
```

A consuming parameter inside the function can be:

- *Consumed* (passed to another consuming function, returned, etc.).
- *Borrowed* further (passed to a borrowing function).
- Dropped at end of scope (triggers deinit).

But cannot be used after consumption — the same affine rule as
Rust/A7.

---

## The Law of Exclusivity (Swift's call-site rule)

SE-0176 (Swift 4.2, 2018) established:

> Two mutable accesses to the same memory must not overlap.

Enforced statically where possible, dynamically (with a runtime
check) otherwise. The dynamic check is cheap and Swift has been
running it across the iOS userland for years.

The relevance to A7: **Swift's experience shows that
call-site-exclusivity-with-fallback-to-runtime is workable** at
scale. A7 takes a stricter line (compile-time only, no
runtime), which is the Hylo direction.

---

## How Swift handles each gap

### Gap 01 — Cast

Swift has explicit conversion initialisers:

- `Int(x)` — failable / trapping construction depending on
  source.
- `Int(exactly:)` — returns `Int?`; fails for non-representable.
- `Int(truncatingIfNeeded:)` — truncating.
- `unsafeBitCast(_:to:)` — explicit, named.

**What A7 can steal:** the **named initialiser** pattern.
`Int(exactly:)` is a clean way to express fallible conversion;
A7's `truncating_cast<T>(x) -> ?T` is the same pattern.

---

### Gap 02 — Nullable pointers

Swift distinguishes `T` (non-optional) from `T?` (optional).
Force-unwrap with `!` (runtime trap if nil). Safe unwrap with
`if let`, `guard let`, `??`.

```swift
var name: String? = nil
if let unwrapped = name { use(unwrapped) }
let safe = name ?? "default"
```

**What A7 can steal:** the **`if let`** syntax and the **`??`
nil-coalescing operator** are clean. Both are well-tested
ergonomics.

**What A7 should not steal:** `!` force-unwrap — Swift's
analog to Rust's `unwrap()`, runtime-panicky.

---

### Gap 03 — Definite assignment

Swift enforces it. Stored properties of classes/structs must be
initialised before use, either in `init` or with a default value.

---

### Gap 04 — `NonZero` division

No `NonZero` family. Division by zero in Swift is a runtime trap.

---

### Gap 05 — Stack budget

Not addressed. Swift allows recursion.

---

### Gap 06 — Typed arithmetic

Swift's `Int.+` traps on overflow by default. Explicit overflow
operators: `&+`, `&-`, `&*` (wrapping). `Int.addingReportingOverflow(_:)`
returns `(partialValue, overflow: Bool)`.

**What A7 can steal:** the **operator naming** (`&+` for wrap)
is one option; A7 could use Zig's `+%`. Both are defensible.

---

### Gap 07 — Bounded indexing

Swift collections expose `subscript(_:)` (trap-on-OOB) and
`indices` (the range of valid indices) and various safer
collection methods.

**What A7 can steal:** the **`indices`** property idea — every
collection exposes its valid index range, which can drive
A7's `for i in s.indices` pattern (similar to Ada's
`for I in Arr'Range`).

---

### Gap 08 — Option/Result

Swift's `Optional<T>` (sugar `T?`) is the canonical reference.
Swift also has `Result<Success, Failure: Error>` since 5.0.

The Swift `try?` operator converts a throwing call to an
`Optional`:

```swift
let val: Int? = try? parse(s)
```

**What A7 can steal:** the **`Result<T, E>` shape** with `E`
constrained to an `Error` protocol — Swift's discipline of
"errors are Error types" is structurally clean. (A7's choice is
open in Q08h.)

---

### Gap 09 — Refinement-lite

Swift has no refinement types. Numeric subtypes are not
expressible.

---

### Gap 10 — Affine ownership

**Swift's recent direction is essentially what A7 plans.** The
three parameter conventions (`borrowing`, `consuming`, `inout`)
map to Hylo's `let`/`sink`/`inout` and A7's
`borrow`/`consume`/`inout`. The Law of Exclusivity is the
call-site rule.

Differences from A7's plan:

- **Swift retains copyable types as the default.** Noncopyable
  is opt-in (`~Copyable` constraint). A7 may or may not have a
  similar split.
- **Swift uses runtime exclusivity checks** as a fallback for
  cases the static analysis can't discharge. A7's contract
  requires compile-time discharge — no runtime check.

**What A7 can steal:** **the parameter-convention syntax** —
`borrowing`/`consuming`/`inout` are clear English keywords that
match the semantics. A7 may prefer shorter names (`borrow`,
`consume`).

**What A7 should not steal:** the **runtime fallback for
exclusivity**. A7's contract says no.

---

### Gap 11 — Finite floats

Swift's `Float.isFinite` query; no `Fin<F>` refinement.

---

### Gap 12 — FFI

Swift has `@_cdecl`, C interop via `Module.swift` mappings,
direct C-header import.

---

## Primary sources

- [Swift book](https://docs.swift.org/swift-book/)
- [SE-0176 (Law of Exclusivity)](https://github.com/apple/swift-evolution/blob/main/proposals/0176-enforce-exclusive-access-to-memory.md)
- [SE-0377 (parameter ownership modifiers)](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0377-parameter-ownership-modifiers.md)
- [SE-0390 (noncopyable structs and enums)](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0390-noncopyable-structs-and-enums.md)
- [SE-0432 (noncopyable pattern matching)](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0432-noncopyable-switch.md)

---

## What A7 can steal — consolidated

1. **`borrowing` / `consuming` / `inout` parameter conventions**
   — clear English keywords. Direct mapping to A7's plan.
2. **Named conversion initialisers** (`Int(exactly:)`,
   `Int(truncatingIfNeeded:)`) — informs Gap 01's `cast` /
   `truncating_cast` / `bit_cast`.
3. **`if let`** syntax for unwrapping.
4. **`??` nil-coalescing** operator.
5. **`indices`** property on collections — drives clean
   `for i in s.indices` bounded indexing.
6. **`Error` protocol** for `Result<T, E>` discipline (open
   question Q08h).
7. **Swift's empirical experience** with noncopyable types in
   production — validates the model.

## What A7 should not steal

1. **`!` force-unwrap** — runtime trap.
2. **Default-trap-on-overflow with no static proof** — A7 wants
   the proof or the explicit operator.
3. **Default-copyable types** — A7's affine-by-default is
   stricter and forces explicit `Copy` opt-in.
4. **Runtime exclusivity check fallback** — A7's contract is
   compile-time only.

## Swift's lessons for A7

The biggest insight: **Swift validates that a production
language can adopt borrowing/consuming/inout modes
incrementally, on top of an existing reference-counted model**.
A7's situation is different (smaller corpus, no existing
ownership story to preserve), but the *language design points*
Swift has settled (keyword names, parameter conventions,
exclusivity rules) are valuable.

If A7 looks at one production language for ownership
discipline, Swift is the most relevant because:

- It's not a small academic language (Hylo) or a beloved
  niche systems language (Rust). Swift ships to billions of
  devices.
- Its design conversations happened in public (Swift Evolution
  proposals). The trade-offs are documented.
- The keyword names are mature and English-friendly.
