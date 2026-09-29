# Language facilities for a live, inspectable system: research

Started 2026-09-18, third batch of material from the user (verbatim in
`tmp/research/language-facilities/claims.md`). More is expected; new batches go
into the same file with a date, and each becomes rows in the audit below.

Where the earlier two programmes cover the runtime
([runtime-model](../runtime-model/README.md)) and what the programmer sees
([live-environment](../live-environment/README.md)), this one covers what the
*language* must offer: errors that pause instead of unwinding, compile-time
execution, layout control, code as structure rather than text, and objects that
carry their own views. Two working systems anchor it — Naughty Dog's GOAL, which
drove a PlayStation 2 from a live Lisp REPL, and the Handmade Hero loop-editing
model, which got most of the benefit from a contiguous state block and a
reloadable library.

| Report | Question |
| --- | --- |
| `00-claims-audit.md` | The 16 claims, ruled on with evidence: shipped, built and abandoned, demonstrated only, or not built |
| `01-condition-systems.md` | Common Lisp conditions and restarts, resumable errors, and whether a statically compiled language can pause in place and continue after a fix |
| `02-compile-time-execution.md` | Arbitrary code at compile time: Jai's `#run`, Zig's `comptime`, D's CTFE, C++ `constexpr`, Rust const evaluation and macros, Terra — and the hermeticity, reproducibility and security questions it raises |
| `03-data-layout-control.md` | AoS to SoA by keyword: Jai, Zig's MultiArrayList, ISPC, Julia's StructArrays, Rust derive crates — and measured effects on cache behaviour |
| `04-structural-programs.md` | Code as trees, graphs and constraints: Sketchpad, MPS, Unison, Hazel, Dion, and why text has kept winning |
| `05-moldable-inspection.md` | Objects that define their own views: Glamorous Toolkit, debugger visualizers, notebooks fused with a live runtime |
| `06-live-targets.md` | Driving a running target from a REPL: GOAL and the PS2, Erlang's remote shell, embedded REPLs, and what the link requires |

Every claim is judged on agent value and human value, weighted toward
agentic use, and each gets a report, a section or a one-paragraph ruling
according to that judgement. See [EVALUATION.md](../EVALUATION.md); do not
research an idea past its ruling.
