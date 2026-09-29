# Deterministic, replayable, heterogeneous runtime: research

Started 2026-09-18. The user supplied a feature list from another project
(verbatim in [the original brief](claims.md)) and asked for research and
an audit of it: what is real, what it costs, what prior art exists, and what A7
would need.

The list describes one coherent design: a runtime whose execution is
deterministic enough to record, step backward and scrub, across CPU, GPU and
NPU, with memory arranged so snapshots are cheap and code and data layouts can
change while the program runs.

| Report | Question |
| --- | --- |
| `00-claims-audit.md` | Each of the eight claims, checked: what is established practice, what is achievable with a stated cost, what is overstated, and what is false as written. Evidence before judgement |
| `01-deterministic-concurrency.md` | Fibers, deterministic work-stealing, logical clocks, structured dependency graphs: how bit-exact multi-core execution is actually obtained, and what it costs in parallel speedup |
| `02-heterogeneous-pipelines.md` | CPU/GPU/NPU task graphs, fences and event timelines; unified memory in practice; whether GPU and NPU results can be made reproducible |
| `03-state-snapshots-arenas.md` | Arena allocation, dirty-region tracking, delta snapshots, rollback, and zero-copy serialization — at what granularity the hardware and OS actually support |
| `04-live-reload-schema-evolution.md` | Hot reload of code and of data layout: Erlang, Smalltalk, Unreal, Unity, shader hot-swap, and the pointer-invalidation problem schema migration creates |
| `06-loop-editing.md` | The cheap version of time travel: a single contiguous state block, no globals, a reloadable code module, and recorded input replayed over it — what it demands of the language and where it stops working |
| `05-multi-target-ir.md` | An IR built for fast translation to several architectures, and remote deployment to devkits: LLVM, Cranelift, QBE, Roc's and Zig's own backends, and what "ultra-fast" means in measured numbers |

Evidence standard, as everywhere in this repository: quote sources verbatim with
a URL and the date read; separate a vendor's claim from a measured result;
attribute nothing unread; mark inference as INFERENCE; state plainly where
sources disagree.

Relation to A7: A7 today is an ahead-of-time compiler to Zig with no runtime of
its own, no concurrency, no accelerator support and no reload story
(`docs/audits/2026-09-18/design-gaps.md`). Each report closes with what adopting
its area would require here, and what it would rule out.

Every claim is judged on agent value and human value, weighted toward
agentic use, and each gets a report, a section or a one-paragraph ruling
according to that judgement. See [EVALUATION.md](../EVALUATION.md); do not
research an idea past its ruling.

## Source records

The [original brief](claims.md) and [source manifest](source-manifest.json) preserve
research provenance outside temporary files. The manifest records earlier source
metadata or local citation hashes, not a fresh verification of external claims.
Exact downloaded evidence remains under `tmp/research/runtime-model/`.
