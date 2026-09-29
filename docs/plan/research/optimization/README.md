# Context-aware and AI-assisted optimization: research

Started 2026-09-18. The user asked for a compiler that understands the target
hardware and the kind of program being built — a game, an operating system, a
safety-critical program, a space application — and emits the best code for that
context, using AI, without giving up safety. Verbatim request in
`tmp/research/optimization/claims.md`.

Two separable questions, and the second is where the risk lives:

1. **Context as a compiler input.** A game wants a frame budget and cache
   behaviour; a kernel wants freestanding code, no floating point in interrupt
   paths and bounded stacks; a safety-critical program wants no dynamic
   allocation and provable worst-case timing; a space application adds
   radiation and certification constraints. Existing systems already encode
   some of this — Ada's Ravenscar profile, MISRA and DO-178C, Rust's `no_std`,
   kernel build constraints — so the question is what a *language-level*
   profile would mean and enforce.
2. **AI inside the compiler.** What is actually established: profile-guided
   optimization, BOLT and AutoFDO, MLGO's learned inlining in LLVM,
   autotuning in Halide and TVM, equality saturation, superoptimization, and
   the recent work on language models for compiler optimization. The honest
   framing is search plus verification: a model proposes, a checker disposes.
   A compiler that emits code no checker validated is a compiler that
   miscompiles convincingly.

| Report | Question |
| --- | --- |
| `01-learned-optimization.md` | What works today: PGO, BOLT, AutoFDO, MLGO, autotuning, equality saturation, superoptimization, learned cost models — with measured gains and their cost |
| `02-context-profiles.md` | What "game", "OS", "safety-critical" and "space" mean as compiler inputs: existing standards and profiles, what each forbids, and what a language could enforce rather than document |
| Report 03, not yet written | Language models proposing optimizations, and the verification that must sit behind them: translation validation, Alive2, differential testing, and the reproducibility and supply-chain questions |

Evidence standard as elsewhere: measured results over claims, sources quoted
with URLs and dates, inference marked. A vendor benchmark is not a measurement.

Judged under [EVALUATION.md](../EVALUATION.md). Agent value is high on both
halves: an agent can run a search loop a person would not tolerate, and it
benefits directly from a machine-checkable definition of what "safe for this
context" means.
