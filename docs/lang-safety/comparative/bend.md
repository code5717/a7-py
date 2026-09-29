# Bend 2

Source: <https://bend-lang.com>, the repository `HigherOrderCo/bend` (Apache-2.0,
TypeScript, 21,349 stars, last push 2026-09-18), its `README.md` and
`guide/GUIDE.md`, read 2026-09-18. Quotations below are verbatim from those two
files. Claims about the papers `BendTT.pdf` and `BendRT.pdf` and about the Lean
formalization are unread and marked UNVERIFIED. Benchmark numbers are the
project's own and were not reproduced.

## What it is

A dependently typed, affine, parallel language whose stated purpose is to make
AI-written code verifiable: "a fast language that blocks AI mistakes via proof"
(repository description). The pitch is that an agent writes the code, a
`LAWS.bend` file states the properties that must hold, and the compiler refuses
the program until a proof in `PROOF.bend` discharges them. "In short,
`LAWS.bend` is `AGENTS.md` backed by proof."

Bend 1 was a parallel language over the HVM interaction-net runtime. Bend 2
drops it: "Bend 2 is a new language. Bend 1 programs and HVM do not carry over."

## Execution model

- One C file per program, and that file is both the CPU program and the GPU
  kernel: "clang compiles it for the CPU. Metal (on Apple) or CUDA (on NVIDIA)
  compiles the same file for the GPU."
- Parallelism is a call annotation, not a thread API: `pow2!(20n)` runs on the
  GPU, `pow2(20n)` in parallel on the CPU. The scheduler is "a contention-free,
  binary fork-join machine: every task is handed to a core exactly once and
  never moved afterwards", which requires the programmer to keep the two halves
  of a split balanced.
- No C stack: "each def compiles to a segment of a flat state machine, a call is
  a jump".
- Targets are C, Metal, CUDA and JavaScript; Lua, Luau and Python are planned.

## Memory model

- Affine by default: "variables must be used, at most, once". A type declared
  `is Data` may be copied; `is Type` may not. A `+` before a variable allows
  reuse of a `Data` value.
- No garbage collector: "Since values are affine, a `match` frees the node it
  opens on the spot, and only `+` values carry a reference count."
- A term is one 64-bit word; everything larger is a pointer into a single heap
  shared by every core and by the GPU.
- Arrays get in-place mutation without losing purity because an `Array<T>` "has
  exactly one owner at all times", so `a[5] <- 42` rewrites the slot and hands
  the same array back. A read returns the array alongside the element.
- Closures are affine: "it can be called at most once, even when everything it
  captures is `Data`".

## Type system and proofs

- Dependent types with almost no inference: "Bend does almost no inference,
  meaning it requires more annotations than similar languages. This is what
  allows Bend's checker to be significantly faster than other provers."
- `Type : Type` holds and there is no positivity check. Consistency is kept by
  splitting the checker: "Code that runs is checked *live*; types, erased
  arguments and equations are checked *dead*. Dead code may loop forever or
  inhabit `Empty`, but nothing dead ever counts as live evidence, and live
  recursion must terminate."
- Live recursion must terminate, with `@unsafe` as the escape hatch.
- Proofs are ordinary definitions; there are no tactics and no proof search.
- Numbers are `Nat`, `U32` and `F32` only. "F32 is axiomatic: nothing about
  floating point can be proven."

## Stated limitations

The README carries a 30-line limitations block. The ones that matter for judging
the project:

- "The compiler (not kernel) is 99% AI-written and has not been fully audited
  yet."
- "The Lean formalization and bend.ts mismatch. Early consistency bugs may
  occur."
- "Strings are linked lists of characters, so text processing is slow."
- "Error messages are terse; no debugger, profiler, formatter, REPL or LSP."
- "No editor support, no test framework and no documentation beyond the guide."
- "One C file per program: no separate compilation, no incremental builds."
- "Parallelism requires balanced calls."
- "The hub has no names, versions, accounts or search yet. Packages are hashes."

## Relevance to A7

Shared ground: both languages restrict the source to make a static argument
possible, both compile ahead of time through a systems-language backend (Bend to
C, A7 to Zig), and both refuse a program the compiler cannot justify rather than
inserting a run-time check.

Differences that matter:

| | Bend 2 | A7 |
| --- | --- | --- |
| Restriction on recursion | Live recursion allowed, must be proved terminating; `@unsafe` opts out | Source recursion banned outright (SPEC 6.2) |
| Aliasing | Affine by default, `Data`-kinded values copyable, `+` for reuse | References with compile-time proofs; the memory model is still in design (`docs/plan/memory.md`) |
| Proof obligations | Written by the user or the agent as explicit proofs, checked by the type checker | Discharged internally by the safety pass; the user never writes a proof |
| Properties provable | Anything expressible in the theory, stated in `LAWS.bend` | A fixed obligation set: divisor non-zero, index in bounds, slice bounds, reference non-nil |
| Numerics | `Nat`, `U32`, `F32`; floats axiomatic | Full fixed-width integer set and `f32`/`f64`; float semantics under gate G1 |
| Annotation burden | Near-total, by design | Inference where the checker can |

Three things worth taking:

1. **A user-visible way to state a property the compiler must enforce.** A7's
   obligations are fixed and internal; a user cannot say "this index is always
   in range because of an invariant I maintain" except by restructuring code.
   `LAWS.bend` is the opposite extreme, but the gap between "the compiler proves
   its own fixed list" and "the user can state a property" is a real design
   question for A7's gate G5 and the memory plan.
2. **Splitting the checker into live and dead modes** is how Bend keeps a
   permissive theory sound. A7's analogue is the separation between what the
   safety pass proves and what the backend may assume; that boundary is
   currently implicit and is exactly where SAF-1 through SAF-34 live.
3. **The limitations block itself.** It is a single honest list of everything
   missing, in the README, where a user reads it first. A7's equivalent is
   spread across `docs/STATUS.md`, SPEC Appendix E and the plan; the language
   audit checklist (`docs/plan/audit/language-audit-checklist.md`) is the first
   time it exists in one place.

Two things not to copy:

1. **Verbosity as a performance strategy.** Bend removes inference to make the
   checker fast. A7's checker is not the bottleneck; its problem is soundness,
   not speed.
2. **An AI-written, unaudited compiler shipped as the product.** Bend says so
   plainly, which is to its credit, but A7's whole current program is auditing
   the compiler it already has.

UNVERIFIED: the performance claims ("as fast as C on the CPU, as fast as CUDA on
the GPU", "checks, in under a second, files that other projects would take
minutes"), the contents of both papers, and whether the Lean formalization
covers the implemented checker.
