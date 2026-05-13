# Why A7

A7 is a deliberately small systems language with one goal: be the cleanest
target for both humans and coding agents to write correct, low-level code
without the foot-guns that come with C-family compilers.

## What A7 trades off

| Trade | Direction |
|---|---|
| Expressiveness | Down. No source recursion, no closures-with-captures, no GC. |
| Predictability | Up. Iterative traversal everywhere, deterministic exit codes, no hidden allocations. |
| Toolchain weight | Down. Python compiler, Zig backend, zero runtime. |
| Agent-readability | Up. Stable URLs, raw markdown, llms.txt + llms-full.txt as first-class artifacts. |

A7 is not trying to be Rust, Go, or even Zig. It is trying to be the smallest
language that can express systems code and still be auditable line-by-line by
a coding agent.

## Design principles

1. **Simplicity over features.** Each feature must justify its complexity
   against the cost of teaching it to a new reader.
2. **Explicit over implicit.** No hidden allocations. No hidden conversions.
   `cast()` is a function call you can grep for.
3. **Iteration as the only control structure for recursion-shaped problems.**
   The compiler rejects A7-source recursion. This is a feature, not a bug —
   it forces algorithms into shapes that don't blow the stack and that an
   agent can analyse without symbolic interpretation.
4. **Zero-cost abstractions.** Generics monomorphize. Slices are
   `(ptr, len)`. Nothing is paid for at runtime that wasn't requested at
   compile time.
5. **Clean Zig interoperability.** A7 lowers to readable Zig. The output is
   meant to be inspectable.

## Why compile to Zig

Zig is a small, stable, fast-moving systems language with excellent
cross-compilation. By targeting Zig source rather than LLVM IR directly,
A7 inherits:

- A mature toolchain pinned at one version (currently 0.16.0).
- Cross-compilation to every Zig-supported target without per-target work.
- Output that's editable and debuggable by hand if needed.
- A clean `c_int`/`usize` ABI surface for FFI.

The cost is a one-step toolchain dependency. We think that's worth it.

## Why no source recursion

Three reasons:

1. **Stack-safety.** Coding agents that emit A7 should not also have to
   reason about stack depth. Banning recursion removes a whole class of
   bugs.
2. **Iterative traversal in the compiler matches iterative code in the
   language.** The compiler's own passes use explicit stacks. The output it
   emits should follow the same discipline.
3. **Loops, worklists, and explicit stacks are universal.** Every recursive
   algorithm can be rewritten. Examples 025 (linked list traversal) and 026
   (binary tree traversal) show the canonical rewrites.

The compiler rejects:

- Direct recursion (`fn f() { f() }`).
- Mutual recursion (`f` calls `g`, `g` calls `f`).
- Function-pointer alias cycles (`p: fn() = f; p()` where `f` reaches `p`).
- Higher-order callback trampolines.

## Who should use A7

Use A7 if you want:

- A small, stable surface that a coding agent can hold in context.
- Native binaries without an LLVM dependency.
- Compiler internals that are inspectable in Python.
- Strict iterative discipline enforced by the compiler.

Look elsewhere if you need:

- Runtime polymorphism or garbage collection.
- A mature ecosystem of libraries today (A7 ships `std/io`, `std/math`,
  `std/mem`, `std/string`, `std/debug`, `std/random` — and that's it).
- Recursion as a primary control structure.
- A package registry (out of scope — see [Status](/a7-py/compiler/status)).

## What's not in A7

Out of scope for this repository and the language:

- Package-registry publishing. No `a7 install foo`. Use git submodules or
  vendor-and-commit.
- A runtime. The Python compiler produces Zig source. Everything else is the
  Zig toolchain's job.
- A sandbox. A7 emits Zig that the host toolchain compiles and runs. Only
  compile source you trust.
- GPU / tensor primitives. These are deferred tracks that need separate
  design work before code lands.
