# Live programming environments: research

Started 2026-09-18. The user supplied a second feature list from another project
(verbatim in `tmp/research/live-environment/claims.md`) and asked for research
and analysis of it.

Where the runtime-model list describes an execution engine, this one describes
what the programmer sees: source and running program in permanent
synchronization, values visible instead of imagined, time unfolded across space,
and direct manipulation of the program while it runs. Most of it has a named
lineage — Smalltalk and Self, Bret Victor's demonstrations, Light Table, Eve,
Hazel, Sketch-n-Sketch — and several parts have been built and abandoned. What
is worth knowing is which parts survived contact with real programs, and why the
rest did not.

| Report | Question |
| --- | --- |
| `00-claims-audit.md` | Each of the eight claims: what has been built, by whom, what it required of the language, where it broke down, and what it would cost to build again |
| `01-live-systems.md` | Systems that kept a program and its source in sync: Smalltalk and Self images, Lisp, Erlang code change, Light Table, Eve, Observable, Jupyter, Hazel, Glamorous Toolkit, hot module reload in web toolchains, Unreal and Godot live editing |
| `02-bidirectional-mapping.md` | Source to output and back: program slicing, provenance tracking, Sketch-n-Sketch's direct manipulation of generated output, browser element inspection, RenderDoc pixel history |
| `03-value-visualization.md` | Making values visible: iteration tables, Python Tutor, omniscient debuggers, projectional and structured editors, notebook output, and what breaks at scale |
| `04-performance-capture.md` | Continuous and gestural input as program input: live-coding music systems, Max/MSP and TouchDesigner, animation curve capture, and recording a performance as editable data |
| `06-structural-editing.md` | Editing a program as a tree or a graph rather than as text: what it buys, what it costs, and why text persists |
| `05-what-the-language-must-provide.md` | The implementation bill: incremental compilation, resumable state, determinism, provenance metadata in the IR, structural editing, and which of these a static ahead-of-time language can have |

Evidence standard: quote sources verbatim with a URL and the date read; name the
system and the author for every claim; separate a demonstration from a shipped
tool; mark inference as INFERENCE; say where a project was abandoned and what
its own authors said about why.

Relation to A7: A7 compiles ahead of time to Zig and runs as a native binary,
with no runtime, no incremental compilation and no editor integration
(`docs/audits/2026-09-18/production-readiness.md`). Each report closes with what
its area would demand of A7, and what is incompatible with compiling to a native
binary at all.

Every claim is judged on agent value and human value, weighted toward
agentic use, and each gets a report, a section or a one-paragraph ruling
according to that judgement. See [EVALUATION.md](../EVALUATION.md); do not
research an idea past its ruling.
