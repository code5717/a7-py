# An intermediate representation for A7: research

Started 2026-09-19 at the user's request (verbatim in `tmp/research/ir/claims.md`):
research a compact IR for A7, designed well enough that optimization works
across any platform or hardware.

The tension to settle first, because it decides everything else: **A7 emits Zig
source, and Zig plus LLVM already optimize.** An IR that exists to produce
better machine code would be duplicating work that is already done, and done
better. So the question is not "which IR makes the fastest code" but "what does
A7 need an IR for" — and the honest candidates are analysis (the safety pass has
no CFG today), stable identity (several miscompiles trace to analyses keyed by
name and by Python object identity), provenance back to source, optimization
that Zig *cannot* do because it has lost A7's invariants, and keeping a second
backend possible.

"Any platform or any hardware" needs the same scrutiny. Portable IRs exist —
WebAssembly, SPIR-V, MLIR — and each buys portability by fixing a semantic model
and giving something up. A report that claims universality without naming what
was given up is not finished.

| Report | Question |
| --- | --- |
| `01-ir-design-space.md` | What IRs exist and what each is for: SSA and its alternatives, sea-of-nodes, RVSDG and region forms, CPS and ANF, typed IRs, e-graphs; and what "compact" means in practice — flat index-based arenas, bit-packed encodings, interning, and the data-oriented designs shipping today |
| `02-a7-ir-proposal.md` | A concrete proposal for A7: what the IR must carry, how it is encoded, what invariants it guarantees, how passes run under A7's no-recursion rule, how safety obligations survive optimization, and how it lowers to Zig without fighting it |

Judged under [EVALUATION.md](../EVALUATION.md); the concepts it serves are C3
(provenance), C12 (search with a verifier) and C1 (reproducible execution) in
[CONCEPTS.md](../CONCEPTS.md). The existing plan for this work is Wave 3 of
`docs/plan/execution.md`.
