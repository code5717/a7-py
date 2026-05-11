# Comparative: Austral

> Phase B artifact in the `docs/lang-safety/` research process.

Austral is a **systems language with linear types and
capability-based security**. It is the most extreme commitment to
**simplicity through linearity**: every value of a linear type has
exactly one owner, must be used exactly once, and the type checker
proves both at compile time. The author reports the linear-type
borrow-checker fits in about **600 lines of code** — an order of
magnitude smaller than Rust's borrow checker.

For A7, Austral is the **"how minimal can a safety story be?"**
benchmark.

Primary sources:

- [Austral language home](https://austral-lang.org/)
- [Linear Types tutorial](https://austral-lang.org/tutorial/linear-types)
- [Introducing Austral (Borretti blog)](https://borretti.me/article/introducing-austral)
- [Austral repository](https://github.com/austral/austral)
- [Interview with Fernando Borretti (LambdaClass blog)](https://blog.lambdaclass.com/austral/)
- [What Austral Proves (Crash Lime)](https://animaomnium.github.io/what-austral-proves/)

---

## The core idea: linear types

A type in Austral is either **free** (Copy / unrestricted use) or
**linear** (must be used exactly once). For linear types:

- Cannot be duplicated.
- Cannot be discarded silently — must be consumed by a function,
  returned, or explicitly destroyed.
- Cannot be shared.

```austral
let f: File := open("foo.txt");
write(f, "hello");
-- compile error: f used once already, must be consumed exactly once
```

Linearity covers:

- **Memory safety** — UAF impossible (a freed allocation's owner
  has been consumed).
- **Resource safety** — files, network connections, etc. cannot
  be leaked or double-freed.
- **Effect tracking** — capabilities for IO, allocation, etc. are
  linear values; you can't perform an effect without holding the
  capability.

The type-system extension is small: track a "use count" per
variable; ensure it equals 1 at scope exit for linear types.

---

## Capabilities as values

Austral uses **capability-based effects**:

```austral
module Bootstrap is
    function rootCap(): RootCap
    -- The capability for the whole program, given at startup
end module
```

To open a file you need a `FileSystemAccess` capability; to print
to stdout you need a `Terminal` capability. Capabilities are
**linear values**, so the type system enforces:

- Functions declare which capabilities they need.
- Callers must supply (and lose) the capability.
- A library can't perform IO unless the caller hands it a
  capability.

This is fine-grained **principle-of-least-privilege** at the type
level.

---

## How Austral handles each gap

### Gap 01 — Cast

Explicit numeric conversions; no `as`-style operator. Bit-cast
requires unsafe.

---

### Gap 02 — Nullable pointers

Austral uses `Option[T]`; references are never null in the safe
subset.

---

### Gap 03 — Definite assignment

Enforced by the linear-type discipline: every linear value must
be assigned before use; the use count starts at 0 (uninit) and
increments to 1 (assigned) before any read.

---

### Gap 04 — `NonZero` division

No refinement types. Division by zero is a precondition
violation (or runtime trap; design in flux).

---

### Gap 05 — Stack budget

Not addressed. Austral allows recursion.

---

### Gap 06 — Typed arithmetic

Austral has fixed-width numeric types. Overflow is defined
behaviour (wraps in release).

---

### Gap 07 — Bounded indexing

Austral arrays are bounded; indexing returns `Option[T]` for
unverified indices. Compile-time-known indices are checked
statically.

---

### Gap 08 — Option/Result

Standard sum types: `Option[T]`, `Either[E, T]` (= Result).

---

### Gap 09 — Refinement-lite

Not present.

---

### Gap 10 — Affine/linear ownership — **the headline feature**

Austral uses **strict linearity** (not affinity):

- A linear value **must** be used exactly once.
- A linear value cannot be discarded by going out of scope.
- The compiler emits an error if you forget to destroy a linear
  value.

```austral
let buf: Buffer := allocate(1024);
-- if we don't call destroy(buf) before scope exit: compile error
destroy(buf);
```

Compared to Rust's affinity (use *at most* once) and A7's plan
(affine, scope-exit drop), Austral requires *every* linear value
to be explicitly handled. This catches leaks too.

References in Austral are explicit (`&!T` for mutable borrow,
`&T` for shared borrow) and have **lexical lifetimes** —
similar to Rust but simpler because there are no NLL-style
inferred regions.

**What A7 can steal:**

1. **The 600-line borrow checker** claim: Austral's
   demonstration that linearity *plus* explicit destruction is
   tractable to implement. A7's Hylo-inspired approach is
   different (affine, parameter modes) but the insight that
   "simpler than Rust's borrow checker" is achievable holds.
2. **Capabilities as linear values** for effect tracking —
   future-looking but interesting. Probably out of scope for A7
   v1.
3. **Explicit destruction**: A7's `del p` consuming `p` is
   the analog of Austral's `destroy(p)`. The Austral discipline
   of *forbidding silent leak* could inform A7's drop policy.

**What A7 should not steal:**

1. **Strict linearity (use exactly once)** — A7's
   `del`-then-drop-on-scope-exit is more permissive and
   ergonomic. Linear is more correct but more verbose.
2. **Austral's specific reference syntax** (`&!T`).
3. **Capability-as-effect machinery** — overkill for A7 v1.

---

### Gap 11 — Finite floats

Not addressed.

---

### Gap 12 — FFI

Austral has explicit FFI; foreign calls must claim a relevant
capability.

---

## Primary sources

- [Austral home](https://austral-lang.org/)
- [Linear Types tutorial](https://austral-lang.org/tutorial/linear-types)
- [Introducing Austral](https://borretti.me/article/introducing-austral)
- [What Austral Proves](https://animaomnium.github.io/what-austral-proves/)
- [Austral GitHub](https://github.com/austral/austral)

---

## What A7 can steal — consolidated

1. **The principle that linear/affine types can be implemented
   simply** — Austral's 600-line borrow checker is the existence
   proof.
2. **Explicit destruction** discipline — `del p` is the analog;
   forbid silent leak.
3. **Capability-as-linear-value** for effect tracking — future,
   when A7 needs effect typing.

## What A7 should not steal

1. **Strict linearity** — too verbose for A7's ergonomic
   target. Affinity is the sweet spot.
2. **Lexical lifetimes** — A7 follows Hylo (no lifetimes).
3. **Capability-based effects** — out of scope for A7 v1.

## The single big idea

Austral's contribution is **scope discipline**: the borrow
checker / linearity engine is *the* mechanism by which the
language gets resource safety, memory safety, and effect
tracking — all in one. A7's design echoes this idea
(definite-assignment + move-analysis + region scopes are all
flow analyses sharing a CFG), but A7 stays narrower (just memory
safety; effect tracking deferred).

The Austral experience says: **don't over-design**. A 600-line
checker is sufficient for industrial linear types. A7 shouldn't
plan a 10,000-line borrow checker.
