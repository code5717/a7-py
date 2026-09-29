# Comparative: Austral

Status: Phase B study written before 2026-09-14; dated notes mark superseded A7 points, and current decisions are in [decisions.md](../../plan/decisions.md) and the [memory plan](../../plan/memory.md).

## Summary

Austral is a systems language with linear types and capability-based security.
It commits fully to simplicity through linearity. A value of a linear type has
exactly one owner and must be used exactly once, and the type checker proves
both at compile time. The author reports that the linearity checker is about 600
lines of code, an order of magnitude smaller than Rust's borrow checker.

For A7, Austral is the benchmark for how small a safety story can be.

## Linear types

An Austral type is either free (unrestricted, like `Copy`) or linear (used
exactly once). A linear value:

- cannot be duplicated;
- cannot be discarded silently; it must be consumed by a function, returned or
  destroyed;
- cannot be shared.

```austral
let f: File := open("foo.txt");
write(f, "hello");
-- compile error: f used once already, must be consumed exactly once
```

Linearity covers three kinds of safety:

- Memory safety: use after free is impossible, because the owner of a freed
  allocation has been consumed.
- Resource safety: files, network connections and similar resources cannot leak
  or be released twice.
- Effect tracking: capabilities for IO, allocation and so on are linear values,
  so code cannot perform an effect without holding the capability.

The extension is small: track a use count per variable and require it to be 1 at
scope exit for linear types.

## Capabilities as values

Austral uses capabilities to control effects:

```austral
module Bootstrap is
    function rootCap(): RootCap
    -- The capability for the whole program, given at startup
end module
```

Opening a file needs a `FileSystemAccess` capability. Printing to stdout needs a
`Terminal` capability. Because capabilities are linear values, the type system
enforces that:

- functions declare the capabilities they need;
- callers supply, and give up, those capabilities;
- a library cannot perform IO unless its caller hands it a capability.

This is least privilege at the type level.

## Per-gap findings

| Gap | Austral |
| --- | --- |
| 01 Cast | Explicit numeric conversions; no `as`-style operator. Bit casts need unsafe code. |
| 02 Nullable pointers | `Option[T]`; references are never null in the safe subset. |
| 03 Definite assignment | Enforced by linearity: the use count starts at 0 (uninitialized) and must reach 1 (assigned) before any read. |
| 04 `NonZero` division | No refinement types. Division by zero is a precondition violation or runtime trap; the design was in flux. |
| 05 Stack budget | Not addressed. Recursion is allowed. |
| 06 Typed arithmetic | Fixed-width numeric types. Overflow is defined and wraps in release. |
| 07 Bounded indexing | Arrays are bounded. Indexing returns `Option[T]` for unverified indices; compile-time-known indices are checked statically. |
| 08 Option/Result | Standard sum types: `Option[T]` and `Either[E, T]` (a `Result`). |
| 09 Refinement-lite | Not present. |
| 11 Finite floats | Not addressed. |
| 12 FFI | Explicit FFI; foreign calls must hold a relevant capability. |

> Note (2026-09-16): A7 now matches Austral on Gap 06 (wrapping `+ - *`, L5) and
> treats floats as IEEE 754 values (L16).

### Gap 10 — Linear ownership

Austral uses strict linearity, not affinity:

- A linear value must be used exactly once.
- A linear value cannot be discarded by going out of scope.
- Forgetting to destroy a linear value is a compile error.

```austral
let buf: Buffer := allocate(1024);
-- if we don't call destroy(buf) before scope exit: compile error
destroy(buf);
```

Rust is affine (use at most once). A7's Phase B plan was affine with a drop at
scope exit. Austral requires every linear value to be handled explicitly, which
also catches leaks.

References are explicit (`&!T` for a mutable borrow, `&T` for a shared borrow)
and have lexical lifetimes. This is similar to Rust, but simpler, because there
are no inferred non-lexical regions.

## What A7 should adopt

1. The evidence that linear or affine types can be implemented simply. Austral's
   600-line checker is the existence proof. A7's Hylo-inspired approach differs
   (affine, parameter modes), but a checker far simpler than Rust's is
   achievable.
2. Explicit destruction that forbids silent leaks. A7's `del p`, which consumes
   `p`, is the analog of Austral's `destroy(p)`, and the no-silent-leak rule
   could inform A7's drop policy.
3. Capabilities as linear values for effect tracking, when A7 needs effect
   typing. Probably out of scope for v1.

> Note (2026-09-16): Item 2 is superseded. The memory plan removes `del` from
> ordinary code (gate M3) and releases storage automatically at static points
> (contract item 3). Only resources such as files and sockets are move-only; they
> are released at extent end, with an explicit fallible `close` and a warning
> when a writable resource is never closed (M7). The Phase B plan of affine
> ownership with parameter modes is replaced by internal ownership (ledger O2).
> See [memory.md](../../plan/memory.md).

## What to avoid

1. Strict linearity (use exactly once). Too verbose for A7's ergonomic target;
   Phase B judged affinity, with `del` and drop at scope exit, the better
   balance.
2. Lexical lifetimes and Austral's reference syntax (`&!T`). A7 follows Hylo and
   has no lifetimes.
3. Capability-based effects. Out of scope for A7 v1.

## Lessons for A7

Austral's contribution is scope discipline. One linearity engine gives resource
safety, memory safety and effect tracking together. A7's Phase B design echoed
this: definite assignment, move analysis and region scopes are all flow analyses
over a shared control-flow graph. A7 stayed narrower, covering memory safety
only and deferring effect tracking.

Austral also warns against over-design. A 600-line checker is enough for
industrial linear types, so A7 should not plan a 10,000-line borrow checker.

## Sources

- [Austral language home](https://austral-lang.org/)
- [Linear Types tutorial](https://austral-lang.org/tutorial/linear-types)
- [Introducing Austral (Borretti blog)](https://borretti.me/article/introducing-austral)
- [Austral repository](https://github.com/austral/austral)
- [Interview with Fernando Borretti (LambdaClass blog)](https://blog.lambdaclass.com/austral/)
- [What Austral Proves (Crash Lime)](https://animaomnium.github.io/what-austral-proves/)
