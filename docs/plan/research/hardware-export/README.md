# Hardware export: research

Started 2026-09-18. The user asked what it means to compile software into
hardware, and specifically about the split: whether a program becomes hardware
*and* software, or only hardware — "i.e. verilog export". Verbatim request in
`tmp/research/hardware-export/claims.md`.

Three outputs are possible, and the field keeps them distinct:

1. **Hardware only.** The whole program becomes a circuit. Nothing runs on a
   processor. This is what Clash, Chisel, Bluespec and Amaranth produce, and
   what a C kernel compiled by Vitis HLS produces when the design has no host
   half. The artifact is RTL — Verilog or VHDL text — not a bitstream: every
   tool in this report stops at RTL and hands it to a separate synthesis and
   place-and-route flow.
2. **Hardware and software.** Part of the program becomes a circuit and the
   rest keeps running as instructions, on a hard CPU next to the fabric or on a
   softcore inside it. The two halves talk over a bus (AXI, Avalon), and that
   interface is the design. LegUp's profiler-driven flow is the canonical
   research form; Vitis plus XRT is the commercial one.
3. **Hardware and software in the same instruction stream.** The program stays
   software, and the *processor* gains instructions implemented in new logic —
   RISC-V custom opcodes, Xtensa TIE. The compiler, not the programmer, is
   where the hardware shows up.

| Report | Question |
| --- | --- |
| `01-software-to-hardware.md` | What each route produces and refuses; who decides the partition and what crossing it costs; which language features survive the translation; how the export is checked against the software it came from; the measured quality and turnaround numbers; what an agent-driven design search requires; and whether any of this is reachable for A7 |

Evidence standard as elsewhere in this directory: quote the source verbatim with
its URL and the date read, keep a vendor's claim separate from a measured
result, attribute nothing unread, mark inference as INFERENCE, and say where
sources disagree. Raw fetched material is under `tmp/research/hardware-export/`.

Judged under [EVALUATION.md](../EVALUATION.md). The report's A7 section is the
ruling: a language that compiles ahead of time to Zig, has no IR, and has no
accelerator or FFI story at all
(`docs/audits/2026-09-18/design-gaps.md`) is a long way from a hardware
back end, and the report says what "a long way" costs rather than leaving it
as a feeling.

## Source records

The [original brief](claims.md) and [source manifest](source-manifest.json) preserve
research provenance outside temporary files. The manifest records earlier source
metadata or local citation hashes, not a fresh verification of external claims.
Exact downloaded evidence remains under `tmp/research/hardware-export/`.
