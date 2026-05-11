# Comparative: Hylo (formerly Val)

> Phase B artifact in the `docs/lang-safety/` research process.

Hylo is the **closest reference for A7's design goal**: compile-time
memory safety equivalent to Rust's borrow checker, but with **no
lifetime annotations**, achieved through **mutable value semantics**
— references exist only as parameter-passing modes, never as
storable values. The Hylo team describes its design as "memory
safety without lifetime parameters."

For A7's purpose, **Hylo is the most important comparative**: if
Hylo's model works, A7 doesn't need to reinvent it.

Primary sources:

- [Hylo home](https://hylo-lang.org/)
- [Hylo introduction](https://hylo-lang.org/introduction/)
- [Hylo language specification](https://hylo-lang.org/docs/reference/specification/)
- [Implementation Strategies for Mutable Value Semantics (Racordon et al., JOT 2022)](https://www.jot.fm/issues/issue_2022_02/article2.pdf)
- [Memory Safety without Lifetime Parameters (Sutter, safe-cpp)](https://safecpp.org/draft-lifetimes.html)

---

## How Hylo handles each gap

### Gap 01 — Cast

Hylo has explicit conversion methods, similar to Swift's
`init(exactly:)` initialisers — fallible conversions return
`Optional`. No equivalent of Rust's `as` operator. Bit-cast
requires `unsafe` (Hylo has a small `unsafe` surface for FFI and
similar; A7 takes a stricter line — no unsafe at all).

**What A7 can steal:** the **constructor-based** conversion
pattern. Each fallible conversion is a named initialiser on the
target type, returning `Optional`.

---

### Gap 02 — Nullable pointers

Hylo uses **`Optional<T>`** with no special nullable-pointer
shape — the type system treats references uniformly. Since
references in Hylo are not storable values (only parameter modes),
the "nullable reference" question is largely absent.

**What A7 can steal:** the philosophical point — *non-storable
references eliminate most nullable-pointer pain*. A7's `?ref T`
exists only because A7 has stored references in struct fields and
locals; Hylo doesn't.

---

### Gap 03 — Definite assignment

Hylo enforces "must initialise before use" via a flow analysis
integrated with the move/exclusivity machinery. The same CFG
pass tracks both "is this binding initialised?" and "is it
consumed?".

**What A7 can steal:** the integration with move analysis. Same
recommendation as Rust.

---

### Gap 04 — `NonZero` division

Hylo follows Swift's approach: stdlib provides `NonZero*`-style
wrappers but the operator `/` doesn't require them. Division by
zero is a precondition violation (runtime trap in Swift; Hylo's
semantics in flux).

**What A7 can steal:** nothing here that Ada and Rust haven't
already provided. A7 takes a stricter line: `NonZero<T>` required.

---

### Gap 05 — Stack budget

Hylo does not have explicit stack-budget analysis. Like Rust, it
allows recursion and accepts the runtime overflow risk.

---

### Gap 06 — Typed arithmetic

Hylo follows Swift: arithmetic operators have `&+`/`&-`/`&*`
wrapping variants; the default operators panic on overflow in
debug, wrap in release. Same vocabulary as Rust.

**What A7 can steal:** the operator vocabulary (`&+` for wrap is
Swift's; A7 may prefer `+%` matching Zig).

---

### Gap 07 — Bounded indexing

Hylo collections provide both `at(index)` (precondition: in range,
trap if out) and safer accessor methods returning Optional.

**What A7 can steal:** none beyond what Rust offers; A7's
`try_get` is the same.

---

### Gap 08 — `Option<T>` / `Result<T, E>`

Standard sum types. Hylo's syntax is value-semantics-friendly;
`match` is exhaustive.

---

### Gap 09 — Refinement-lite

Hylo does not have refinement types built in. Its sister project
Val/Hylo focuses on the value-semantics property; refinement is
left to library.

---

### Gap 10 — Affine ownership — **the headline feature**

**This is what makes Hylo the model for A7.**

The four parameter-passing modes:

| Mode | Semantics | Lifecycle |
| --- | --- | --- |
| `let`   | Immutable borrow for the call's duration | Caller still owns at return |
| `inout` | Exclusive mutable borrow | Caller still owns at return |
| `sink`  | Consume (ownership transfer) | Caller loses ownership |
| `set`   | Output (uninitialised in, initialised out) | Caller gains ownership |

The crucial property: **references exist only at function
boundaries.** You cannot store a reference in a variable or field.
This eliminates the entire "lifetime" question — every reference's
lifetime is the call duration.

```hylo
fun swap(_ x: inout T, _ y: inout T) {
    let tmp = x       // borrow
    x = y
    y = tmp
}

swap(&a, &a)  // compile error: exclusivity violation — two inouts to the same value
```

Exclusivity is checked at the call site, intra-procedurally. No
borrow checker needed.

**Method calls** follow the same model. A method declares its
receiver's mode:

```hylo
extension Array {
    fun count() -> Int { ... }                  // let-receiver by default
    inout fun append(_ x: sink Element) { ... } // inout-receiver
    sink fun take_first() -> Element { ... }    // sink-receiver, consumes self
}
```

**What A7 can steal:** essentially **the whole model**. The four
modes, the no-storable-references rule, the call-site
exclusivity check. A7's Gap 10 plan directly mirrors this.

**What A7 should not steal:** Hylo's specific keyword names if
A7 has stylistic preferences (e.g., `borrow` vs `let`,
`consume` vs `sink`). The semantics matter, not the spelling.

---

### Gap 11 — Finite floats

Standard `Float` type without a `Fin<F>` analog. Same as Swift.

---

### Gap 12 — FFI

Hylo has C interop via opaque types and `unsafe` blocks (small
surface).

---

## Primary sources

- [Hylo home](https://hylo-lang.org/)
- [Hylo introduction](https://hylo-lang.org/introduction/)
- [Hylo language specification](https://hylo-lang.org/docs/reference/specification/)
- [Implementation Strategies for Mutable Value Semantics (Racordon et al., JOT 2022)](https://www.jot.fm/issues/issue_2022_02/article2.pdf)
- [Memory Safety without Lifetime Parameters](https://safecpp.org/draft-lifetimes.html)
- [Borrow Checking Hylo (Dimi Racordon, SPLASH 2023)](https://2023.splashcon.org/details?action-call-with-get-request-type=1&aeaf6a94a42c4ad59b2aa49bf08e9956action_174265066106514c553537a12bb6aa18971ade0b614=1&context=splash-2023&decoTitle=Borrow-checking-Hylo&track=iwaco-2023-papers&urlKey=5)

---

## What A7 can steal — consolidated

1. **The four parameter-passing modes** (`let`/`inout`/`sink`/`set`)
   — **the core of A7's Gap 10 plan**.
2. **The no-storable-references rule** — references exist only
   at function boundaries, never in struct fields or locals.
3. **Call-site exclusivity checking** instead of borrow checking.
4. **Constructor-based fallible conversion** (Gap 01).
5. **Method receiver modes** — methods declare their receiver's
   mode just like any other parameter.

## What A7 should not steal

1. Hylo's small `unsafe` escape (A7 has none).
2. Swift-inherited `&+` wrap operator (A7 may prefer Zig-style `+%`).
3. Hylo's lack of refinement types (A7 has refinement-lite).
4. Hylo's lack of stack-budget analysis.

## The single argument for adopting Hylo's model

If A7 adopts Hylo's parameter-mode discipline:

- **Compile-time UAF/aliasing safety** is achieved.
- **Lifetime annotations are unnecessary** (zero `'a`'s in the
  syntax).
- **The model is intra-procedural** — every check is local to a
  function or call site, no cross-function lifetime inference.
- **Diagnostics are clear** — "you passed `&a` and `&a` to the
  same call; one must be different."

The cost: references cannot be stored. Most idioms that need
stored references (callbacks, observers, linked structures)
need to be rewritten using indices or owning containers. The
Hylo team's published experience suggests this is tractable;
A7's smaller code base makes it easier.

This is the recommendation `06-compile-time-safety.md` already
makes; the Hylo deep-dive confirms it's been done in practice.
