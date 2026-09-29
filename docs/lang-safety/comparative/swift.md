# Comparative: Swift

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Swift is the largest production deployment of exclusivity without lifetimes.
Apple ships it on iOS, macOS and its other platforms, across billions of
devices. Swift 5.9 and 6.0 added noncopyable types and explicit ownership
conventions (`borrowing`, `consuming`, `inout`). These are the closest production
parallel to Hylo's design and to A7's Phase B plan.

Hylo is the academic clean slate. Swift is an established language migrating
incrementally to the same discipline, while keeping compatibility with
reference-counted class types. A7 faced a similar migration question for its
existing example corpus.

## Parameter conventions

Swift declares ownership per parameter:

| Convention | Meaning | Caller still owns? |
| --- | --- | --- |
| `borrowing` | Shared, immutable access for the call | yes |
| `consuming` | Caller transfers ownership and cannot use the value after | no |
| `inout` | Exclusive, mutable access for the call | yes, after the call |

Copyable types always had these conventions under the underscored names
`__shared` and `__owned`; SE-0377 made them explicit and stable. For noncopyable
types (SE-0390), the convention must be written, because no default is always
safe.

```swift
func process(_ buf: borrowing Buffer) { ... }  // can't mutate, can't consume
func handoff(_ buf: consuming Buffer) { ... }  // takes ownership
func update(_ buf: inout Buffer)      { ... }  // mutates in place
```

Inside the function, a consuming parameter can be:

- consumed (passed to another consuming function, returned, and so on);
- borrowed further (passed to a borrowing function);
- dropped at end of scope, which runs `deinit`.

It cannot be used after it is consumed. This is the same affine rule as Rust's
and A7's Phase B plan.

## The Law of Exclusivity

SE-0176 (Swift 4.2, 2018) established:

> Two mutable accesses to the same memory must not overlap.

Swift enforces it statically where possible and with a runtime check otherwise.
The runtime check is cheap, and Swift has run it across the iOS userland for
years.

Swift shows that call-site exclusivity with a runtime fallback works at scale.
A7 takes the stricter Hylo line: compile-time only, no runtime check.

> Note (2026-09-16): The memory plan still rejects exclusivity conflicts at
> compile time (contract item 8.1). A runtime distinct-index or overlap check is
> allowed only if a gate approves it with a defined result (section 6). See
> [memory.md](../../plan/memory.md).

## Per-gap findings

| Gap | Swift |
| --- | --- |
| 03 Definite assignment | Enforced. Stored properties must be initialized before use, in `init` or by a default value. |
| 04 `NonZero` division | No `NonZero` family. Division by zero is a runtime trap. |
| 05 Stack budget | Not addressed. Recursion is allowed. |
| 09 Refinement-lite | No refinement types; numeric subtypes are not expressible. |
| 11 Finite floats | `Float.isFinite` query only; no `Fin<F>` refinement. |
| 12 FFI | `@_cdecl`, C interop through module maps, direct C header import. |

> Note (2026-09-16): Gap 11 is settled: A7 floats follow IEEE 754 as in Zig and
> C, so NaN and infinity are ordinary values (L16). A `Fin<F>` refinement is no
> longer planned as the default.

### Gap 01 — Cast

Swift uses explicit conversion initializers:

- `Int(x)`: trapping or failable construction, depending on the source type.
- `Int(exactly:)`: returns `Int?`; `nil` if the value is not representable.
- `Int(truncatingIfNeeded:)`: truncates.
- `unsafeBitCast(_:to:)`: explicit and named.

A7 can adopt the named-initializer pattern. `Int(exactly:)` expresses a fallible
conversion cleanly; the Phase B draft `truncating_cast<T>(x) -> ?T` followed the
same pattern.

> Note (2026-09-16): The A7 cast design is open under gate G3; see
> [decisions.md](../../plan/decisions.md).

### Gap 02 — Nullable pointers

Swift separates `T` (non-optional) from `T?` (optional). `!` force-unwraps and
traps on `nil`. Safe unwrapping uses `if let`, `guard let` and `??`.

```swift
var name: String? = nil
if let unwrapped = name { use(unwrapped) }
let safe = name ?? "default"
```

A7 can adopt `if let` and the `??` nil-coalescing operator; both are
well-tested. A7 should not adopt `!`, which is Swift's equivalent of Rust's
`unwrap()` and traps at run time.

### Gap 06 — Typed arithmetic

Swift's `+` on `Int` traps on overflow by default. `&+`, `&-` and `&*` wrap.
`addingReportingOverflow(_:)` returns `(partialValue, overflow: Bool)`.

A7 could name a wrapping operator `&+` like Swift, or `+%` like Zig; both are
defensible.

> Note (2026-09-16): Superseded by L5. Ordinary `+`, `-` and `*` now wrap in A7,
> as in Odin, so no separate wrapping operator is needed. Division, shifts and
> narrowing casts remain open under gate G3.

### Gap 07 — Bounded indexing

Swift collections provide `subscript(_:)`, which traps when out of bounds, the
`indices` property (the range of valid indices) and several safer collection
methods.

A7 can adopt the `indices` idea: each collection exposes its valid index range.
This drives a `for i in s.indices` pattern, similar to Ada's
`for I in Arr'Range`.

Current A7 gives the loop index type `usize` ([SPEC](../../SPEC.md) section
5.3), but that alone does not prove an index bound: indexing by a separately
tracked `usize` is still rejected.

```a7
// Current A7 syntax (SPEC section 5.3). Compiled 2026-09-16: rejected,
// exit 6, "index bounds are not proven" at `values[best]`. The loop gives
// `i: usize`, but `best` carries no proven bound against `values`.
index_of_max :: fn(values: []i32) usize {
    best: usize = 0
    for i, value in values {
        if value > values[best] {
            best = i            // i: usize, always a valid index
        }
    }
    ret best
}
```

### Gap 08 — Option/Result

Swift's `Optional<T>` (sugar `T?`) is the canonical reference. Swift 5.0 added
`Result<Success, Failure: Error>`.

`try?` converts a throwing call to an optional:

```swift
let val: Int? = try? parse(s)
```

A7 can adopt the `Result<T, E>` shape with `E` constrained to an `Error`
protocol. Requiring errors to be `Error` types is structurally clean. The A7
choice is open question Q08h.

### Gap 10 — Affine ownership

Swift's recent direction matched A7's Phase B plan. `borrowing`, `consuming` and
`inout` map to Hylo's `let`, `sink` and `inout`, and to A7's proposed `borrow`,
`consume` and `inout`. The Law of Exclusivity is the call-site rule.

Differences from the Phase B plan:

- Swift keeps copyable types as the default. Noncopyable is opt-in through the
  `~Copyable` constraint. A7 might or might not have a similar split.
- Swift falls back to runtime exclusivity checks where static analysis cannot
  decide. A7's contract requires compile-time discharge.

A7 can adopt the convention names: `borrowing`, `consuming` and `inout` are clear
English words that match their meaning. A7 may prefer shorter forms (`borrow`,
`consume`). A7 should not adopt the runtime exclusivity fallback.

> Note (2026-09-16): L6 approves immutable argument bindings but no
> parameter-mode syntax; `ref` stays the working form, and proposed decisions
> D.040, D.041 and D.049 (mode keywords, inferred modes) were not accepted. The
> memory plan makes ownership internal. Assignment copies (contract item 4),
> which is closer to Swift's copyable default than to affine-by-default; only
> resources are move-only (M7).

## What A7 should adopt

1. `borrowing`, `consuming` and `inout` parameter conventions: clear English
   keywords that map directly to the Phase B plan.
2. Named conversion initializers (`Int(exactly:)`, `Int(truncatingIfNeeded:)`),
   to inform Gap 01's `cast`, `truncating_cast` and `bit_cast`.
3. `if let` for unwrapping.
4. The `??` nil-coalescing operator.
5. An `indices` property on collections, for clean bounded loops such as
   `for i in s.indices`.
6. An `Error` protocol for `Result<T, E>` (open question Q08h).
7. Swift's production experience with noncopyable types, as validation of the
   model.

> Note (2026-09-16): Item 1 is superseded by L6 and the memory plan (see the
> Gap 10 note). Item 2 is open under G3. Items 3 and 4 would be syntax changes
> and need approval with examples under the ledger's approval rule.

## What to avoid

1. `!` force-unwrap, which traps at run time.
2. Trap-on-overflow by default with no static proof. Phase B wanted either a
   proof or an explicit operator.
3. Copyable-by-default types. Phase B preferred affine-by-default with explicit
   `Copy` opt-in.
4. The runtime exclusivity fallback. A7's contract is compile-time only.

> Note (2026-09-16): Item 2 is superseded by L5 (ordinary `+ - *` wrap). Item 3
> is reversed by the memory plan: assignment copies, and only resources are
> move-only (contract item 4, M7).

## Lessons for A7

Swift shows that a production language can adopt borrowing, consuming and inout
conventions incrementally, on top of a reference-counted model. A7's situation
differs: its corpus is smaller and it has no ownership model to preserve. Still,
the design points Swift has settled (keyword names, parameter conventions,
exclusivity rules) are valuable.

Among production languages, Swift is the most relevant ownership reference:

- It is not a small academic language (Hylo) or a niche systems language (Rust),
  and it ships to billions of devices.
- Its design discussions happen in public Swift Evolution proposals, so the
  trade-offs are documented.
- Its keyword names are mature and read as plain English.

## Sources

- [Swift book](https://docs.swift.org/swift-book/)
- [SE-0176: Law of Exclusivity](https://github.com/apple/swift-evolution/blob/main/proposals/0176-enforce-exclusive-access-to-memory.md)
- [SE-0377: borrowing and consuming parameter ownership modifiers](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0377-parameter-ownership-modifiers.md)
- [SE-0390: Noncopyable structs and enums](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0390-noncopyable-structs-and-enums.md)
- [SE-0432: Borrowing and consuming pattern matching](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0432-noncopyable-switch.md)
- [WWDC 2024: "Consume noncopyable types in Swift"](https://developer.apple.com/videos/play/wwdc2024/10170/)
