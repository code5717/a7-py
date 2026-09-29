# Master claim register

Every idea supplied by the user on 2026-09-18, deduplicated across four batches,
with a ruling on how far to research it. Judged by
[EVALUATION.md](EVALUATION.md): agent value weighted above human value.

Verbatim sources: `tmp/research/runtime-model/claims.md`,
`tmp/research/live-environment/claims.md`,
`tmp/research/language-facilities/claims.md`, `tmp/research/claims-batch4.md`.

Depth: **Report** = full research. **Section** = a few paragraphs inside a
related report. **Ruling** = one paragraph saying why it stops here.

"Agent twin" is the machine-facing version of an idea whose original form is
visual. Where one exists, it is usually the version worth building.

## Research in depth

| Claim | Agent | Human | Depth | Why |
| --- | --- | --- | --- | --- |
| Deterministic input journaling plus copy-on-write arena checkpoints | high | high | Report | The practical core of everything else in these lists. Restore the nearest snapshot, replay the journal, arrive at any tick. rr and rollback netcode already do it |
| Self-contained `.session` replay package (snapshot, input journal, code diffs) | high | high | Report | An agent handed a failing session reproduces the exact failure with no local setup. The single most transferable artifact in the four batches |
| Reverse data watchpoints (step backward to the write that corrupted a value) | high | high | Report | Turns "who wrote this" from a search into a query. rr's reverse-continue is the existing proof |
| Monotonic execution tick stamped on every allocation and event | high | med | Report | Gives every object a provenance key an agent can query and jump to. Cheap to emit, and it makes a trace searchable rather than steppable |
| Condition system: fault suspends in place, fix, resume from the frame | high | high | Report | An agent gets the live faulted state instead of a stack trace. The hard part is whether a statically compiled language can resume at all |
| Contiguous arenas, POD-only state, no globals | high | med | Report | Makes snapshots, serialization and rollback trivial rather than clever. It is a language decision A7 has not made, and it interacts with the memory plan |
| Deterministic fiber concurrency with logical clocks | high | med | Report | Determinism is the precondition for replay; without it the rest collapses. Also the open question in gate G7 |
| Arbitrary compile-time execution (`#run`) | high | high | Report | Agents generate tables, validate invariants and run checks at build time. Raises hermeticity and security questions A7 must answer, since it is not a sandbox |
| Moldable inspectors, in their agent form: a type declares how it is projected | high | high | Report | For a person, a canvas; for an agent, a structured projection instead of a memory dump. Same mechanism, two renderers |

| Context as a compiler input (game, OS, safety-critical, space profiles) | high | high | Report | A machine-checkable definition of what a context forbids is exactly what an agent needs to stay inside it. Prior art exists: Ravenscar, MISRA, DO-178C, `no_std` |
| AI-proposed optimization behind a verifier | high | med | Report | An agent can run a propose-and-check loop indefinitely; the value is entirely in the checker, without which it is a miscompile generator |

## Cover as a section

| Claim | Agent | Human | Where | Note |
| --- | --- | --- | --- | --- |
| Continuous state-space reversibility (append-only timeline) | high | high | inside the journaling report | The idealized statement of journaling plus checkpoints; the engineering is there, not here |
| Live code swap by trampoline or module reload | med | high | runtime-model `06-loop-editing.md` | Agents rebuild cheaply; the win is a fast loop, not liveness |
| Sub-perceptual keystroke codegen | med | high | same | Agent twin: compile latency as a loop-rate budget. A7 compiles in Python; measure before designing |
| Unfolded iteration matrices | med | high | tooling `09-visualization.md` | Agent twin: per-iteration variable state as queryable structured data — a trace query, not a grid |
| Bidirectional source-to-output mapping | med | high | live-environment `02` | Agent twin: provenance and slicing — which statements produced this output |
| Time-anchored profiling that warps to the tick of a spike | med | high | tooling `04` | Useful once a timeline exists; worthless before |
| Live schema evolution | low | high | runtime-model `04` | A development-loop convenience; pointer invalidation is the real content |
| AoS/SoA layout by keyword | low | med | language-facilities `03` | A performance feature, independent of everything else here |
| Code as trees and graphs, structural editing | med | med | live-environment `06` | Agent twin: structured edit operations on the AST instead of text patches |
| Cross-architecture IR and remote deployment | low | med | runtime-model `05` | A7 reaches other targets through Zig already; the question is what an own IR would add |
| Executable notebooks fused with a live runtime | low | med | live-environment `01` | Documentation and runtime in one artifact; narrow for a systems language |

## Ruled out here, with the transferable idea named

| Claim | Ruling |
| --- | --- |
| Unified CPU/GPU/NPU coherency; live shader hot-swap; deterministic NPU inference; GPU timeline unwinding | A7 has no accelerator story at all — a grep for `tensor`, `spawn` and `extern` across the compiler returns nothing (`docs/audits/2026-09-18/design-gaps.md`). Revisit with tracks 10 and 11. Transferable: the claim that accelerator work must sit on the same dependency timeline as CPU work, which is a design constraint worth recording before that work starts |
| Spatial projection of trajectories; parameter scrubbing; pixel-to-code | A graphics or simulation environment, which A7 is not. Transferable, and genuinely useful: the agent twin of scrubbing is an automated parameter sweep, and the twin of a trajectory is speculative forward evaluation — both are property testing by another name |
| Gestural and analog performance capture | Belongs to an authoring tool. No agent value |
| Data-reified schematics and ghost waveforms | Domain-specific to circuits and signals. The general idea — compare a previous run against the current one — is already covered by differential testing |
| Hardware-aligned object system for a specific console; live socket REPL into a devkit | Historical case studies (Naughty Dog's GOAL). One paragraph in `06-live-targets.md` for what the link required, not a programme |

## What this adds up to for A7

Six items are worth real work, in this order, and all six are independent of
graphics, accelerators and editors:

1. Determinism, because nothing else replays without it.
2. Input journaling with arena checkpoints.
3. A portable session artifact an agent can be handed.
4. A monotonic tick stamped on allocations, so history is queryable.
5. Reverse watchpoints over that history.
6. Compile-time execution, which is independent of the rest and useful now.

Arenas and POD-only state sit underneath 2 and 3 and are a memory-plan decision,
not a tooling one. The condition system is the one high-value item that may be
incompatible with compiling ahead of time to a native binary; the research
should settle that before anyone plans it.
