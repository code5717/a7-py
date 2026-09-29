# 01 — Compiling software into hardware

Report 01 of the [hardware export programme](./README.md). Question, from the
user: what does it mean to compile software into hardware, and what is the split
— does the program become hardware *and* software, or only hardware, "i.e.
verilog export"?

Evidence standard: every quotation carries its URL and the date it was read.
Vendor claims are marked VENDOR and measured results MEASURED. Inference is
marked INFERENCE. Where sources disagree, both are given. Raw fetched material
is under `tmp/research/hardware-export/`; every quote below is greppable in a
file there.

## Findings in one place

1. **Nothing here produces a bitstream.** Every route in this report stops at
   RTL — Verilog or VHDL text — and hands it to a separate synthesis and
   place-and-route flow. Xilinx says so in its own user guide: the primary
   output is "RTL implementation files in hardware description language (HDL)
   formats", and "Using logic synthesis, you can synthesize the packaged IP into
   an FPGA bitstream" (UG902 v2019.1 p.13). "Verilog export" is exactly the
   right phrase for what a compiler can deliver; the bitstream belongs to the
   vendor tool after it.
2. **Three outputs, not two.** Hardware only (the whole program is a circuit);
   hardware plus software (a kernel is a circuit, the rest runs on a processor
   and calls it over a bus); and hardware inside the software (the program stays
   instructions, and the processor gains new ones). The third is the one people
   forget, and it is the cheapest to reach from a compiler.
3. **The forbidden list is the same list every time.** Dynamic allocation,
   recursion, function pointers, virtual dispatch, system calls, unbounded
   anything. Xilinx's synthesis precondition is four lines long and is the whole
   story: the function must contain the entire design, no functionality may come
   from the OS, "The C constructs must be of a fixed or bounded size", and "The
   implementation of those constructs must be unambiguous" (UG902 v2019.1
   p.282). A7 today bans exactly one item on that list — recursion — and proves
   a second (bounds) at compile time. It has all the rest: `new`/`del`/`nil`,
   `ref`, function values (`examples/022_function_pointers.a7`,
   `examples/027_callbacks.a7`), slices, `string` and `io`.
4. **The timing model, not the feature list, is what changes about the
   language.** A statement stops being a step in time and becomes a placement in
   a schedule. Whether the programmer must state the schedule is the axis that
   separates the families: HLS hides it behind pragmas and heuristics, Bluespec
   and Calyx make the compiler derive it from an explicit structure, Clash makes
   it a type, and Dahlia makes violating it a type error.
5. **The checking is weak where it matters.** The standard check is C/RTL
   co-simulation, which replays the C test bench's input vectors against the
   generated RTL — it proves the design agrees with the software on the vectors
   the test bench happens to exercise, and nothing else. Fuzzing four HLS tools
   with Csmith found 918 (13.7%), 167 (2.5%), 83 (1.2%) and 26 (0.4%) failing
   test cases in Bambu, LegUp, Vivado HLS and Intel i++ respectively, out of
   6700 — MEASURED, Herklotz et al., FCCM 2021.
6. **The loop is minutes to hours per candidate, and that is the fact that
   matters most for this research programme.** "HLS tools usually take 5-30
   minutes to generate RTL and estimate the performance" (AutoDSE,
   arXiv:2009.14381v2), and place-and-route on top of that runs 30-90 minutes
   for AWS's own example designs with a further step AWS says "can take hours".
   Dahlia's authors swept 32,000 configurations of one matrix-multiply kernel
   for "2,666 compute hours" — about five minutes each — in Vivado HLS's
   *estimation* mode alone (MEASURED, PLDI 2020). Software autotuning assumes
   "the cost of compiling and running a tensor program is a few seconds"
   (AutoTVM): two to three orders of magnitude apart. And the fast estimate is
   not the truth — Nane et al. found "no strict correlation" between HLS timing
   estimates and post-place-and-route frequency. Every fast-feedback assumption
   elsewhere in this research programme fails here.
7. **For A7 the honest answer is no, and far beyond v1.** The decision ledger
   already says so — L8 "does not qualify any GPU, NPU, TPU or FPGA" — and
   nothing found here argues with it. A7 has no IR, no CFG, no FFI, no
   accelerator interface and no concurrency; `docs/audits/2026-09-18/design-gaps.md`
   found zero lines of `a7/` mentioning any of them. The one favourable
   coincidence is that A7's single structural ban, source recursion, is the
   hardest restriction every one of these systems imposes, and Wave 5's Phase C2
   would incidentally remove `new`, `del`, `nil` and stored `ref` as well. That
   is a coincidence worth recording, not a reason to build a back end.
   Section 8 prices it.

---

## 1. The routes, and what each actually produces

### 1.1 The one thing they have in common

Every tool in this section emits **RTL as text** and stops. The Xilinx user
guide states its own output list plainly:

> "The following are Vivado HLS outputs:
> • RTL implementation files in hardware description language (HDL) formats
>   This is the primary output from Vivado HLS. Using Vivado synthesis, you can
>   synthesize the RTL into a gate-level implementation and an FPGA bitstream
>   file. The RTL is available in the following industry standard formats:
>   ○ VHDL (IEEE 1076-2000)
>   ○ Verilog (IEEE 1364-2001)
>   Vivado HLS packages the implementation files as an IP block for use with
>   other tools in the Xilinx® design flow. Using logic synthesis, you can
>   synthesize the packaged IP into an FPGA bitstream."
> — *Vivado Design Suite User Guide: High-Level Synthesis*, UG902 (v2019.1),
> July 12, 2019, p.13; `raw/ug902_2019_1.txt:555-570`, read 2026-09-19

So "Verilog export" is the accurate description of what a compiler back end can
deliver. Turning RTL into a configured device is a second, separate, much slower
pipeline — logic synthesis, technology mapping, placement, routing, bitstream
generation — owned by the FPGA vendor's tool (Vivado, Quartus) or, for an ASIC,
by a foundry flow. No compiler discussed here crosses that line, and a language
that wanted to would be taking on the hardest and least portable part of the
problem for no benefit.

### 1.2 Route table

| Route | Input may contain | Produces | Refuses |
| --- | --- | --- | --- |
| **Vitis / Vivado HLS** (C, C++, OpenCL) | a bounded C/C++ subset: loops, arrays, structs, classes, templates, float and double, arbitrary-precision types | VHDL or Verilog packaged as an IP block, plus reports | dynamic allocation, recursion (including tail recursion), function pointers, system calls, most of the STL, anything unbounded |
| **Intel/Altera HLS Compiler** (C++) | a bounded C++ subset (UNVERIFIED — no primary doc read) | Verilog for the Intel FPGA flow (UNVERIFIED) | same family of constructs (UNVERIFIED); measured separately: it had by far the worst compile time of four tools fuzzed (§4.4) |
| **LegUp** (C, LLVM-based) | C, with the *whole program* compiled; hot functions selected for hardware | synthesizable Verilog for the selected functions plus a modified software binary for a MIPS softcore | the same list; the 2011 version synthesized at function granularity only |
| **Catapult** (C++, SystemC) | UNVERIFIED — no primary doc read | RTL, plus a vendor equivalence-checking flow (VENDOR, §4.2) | UNVERIFIED |
| **Chisel** (Scala) | *any* Scala — the Scala runs at elaboration time, not on the chip | Verilog, or a C++ cycle-accurate simulator | nothing at the Scala level; everything at the *hardware* level, because only the datatypes that reach the hardware graph become circuit |
| **FIRRTL / CIRCT** | a hardware IR, not a source language | Verilog/SystemVerilog | — (it is the layer the above compile *through*) |
| **SpinalHDL** (Scala), **Amaranth** (Python) | any host-language code at elaboration time | VHDL/Verilog | same as Chisel: the host language is a generator, not a target. UNVERIFIED — characterised by analogy with Chisel; no primary doc for either was read |
| **Bluespec** | guarded atomic rules over state | Verilog, with a compiler-derived schedule | anything the scheduler cannot make atomic. UNVERIFIED — the Nikhil MEMOCODE 2004 paper was not read; only its citation in Nane et al.'s bibliography (`raw/nane_tcad2016.txt:919-920`, right-hand column) |
| **Clash** (Haskell) | a Haskell subset with statically known bit widths | VHDL, Verilog or SystemVerilog | data-dependent recursion, recursive datatypes (so: no lists), un-sized types |
| **Halide-to-FPGA** | a Halide pipeline with `hw_accelerate`-style schedule directives | synthesizable C fed to an HLS tool → Verilog, **plus** the CPU program and Linux drivers | anything outside the Halide model |
| **Dahlia** | an imperative language with time-sensitive affine types | HLS C++ with `#pragma` directives (so: RTL, via Vivado HLS) | programs whose parallelism exceeds their memory ports; arbitrary index expressions like `A[2*i]` |
| **Calyx** | an IR: a structural component language plus `seq`/`par`/`if`/`while` control | SystemVerilog | — (an IR; frontends decide what to refuse) |
| **Spatial** | a parallel-patterns DSL over explicit on-chip memories | Chisel → Verilog | MEASURED by its authors: "a geometric mean speedup of 2.9× compared to an industrial HLS tool", and design spaces "spanning 10^6 to 10^10 points and taking hours or days to exhaustively search" (`raw/spatial_pldi18.txt:875`, `:726`, PLDI 2018, read 2026-09-19) |
| **Vericert** | a subset of C, via CompCert's three-address IR | Verilog, with a Coq proof of behavioural preservation | switch statements, function pointers, recursion, non-32-bit integers, floats, global variables |

### 1.3 High-level synthesis: what it forbids, in the vendor's own words

The synthesis precondition is four bullets:

> "To be synthesized:
> • The C function must contain the entire functionality of the design.
> • None of the functionality can be performed by system calls to the operating
>   system.
> • The C constructs must be of a fixed or bounded size.
> • The implementation of those constructs must be unambiguous."
> — UG902 (v2019.1) p.282; `raw/ug902_2019_1.txt:15022-15028`, read 2026-09-19

Everything else follows from those four. Dynamic allocation:

> "Any system calls that manage memory allocation within the system, for
> example, malloc(), alloc(), and free(), are using resources that exist in the
> memory of the operating system and are created and released during run time:
> to be able to synthesize a hardware implementation the design must be fully
> self-contained, specifying all required resources."
> — UG902 (v2019.1) p.284; `raw/ug902_2019_1.txt:15115-15120`

Function pointers, in two sentences and no elaboration:

> "Function Pointers
>
> Function pointers are not supported."
> — UG902 (v2019.1) p.286; `raw/ug902_2019_1.txt:15235-15237`

Recursion, including the case people assume is fine:

> "Recursive functions cannot be synthesized. This applies to functions that can
> form endless recursion, where endless: [...] Vivado® HLS does not support tail
> recursion in which there is a finite number of function calls."
> — UG902 (v2019.1) p.286; `raw/ug902_2019_1.txt:15240-15252`

And the consequence for the standard library:

> "Many of the C++ Standard Template Libraries (STLs) contain function recursion
> and use dynamic memory allocation. For this reason, the STLs cannot be
> synthesized."
> — UG902 (v2019.1) p.286; `raw/ug902_2019_1.txt:15263-15266`

An independent academic statement of the same subset, from the open textbook
*Parallel Programming for FPGAs*, which states it as the assumption its whole
book rests on:

> "• No dynamic memory allocation (no operators like malloc(), free(), new, and
>   delete())
> • Limited use of pointers-to-pointers (e.g., may not appear at the interface)
> • System calls are not supported (e.g., abort(), exit(), printf(), etc. [...])
> • Limited use of other standard libraries [...]
> • Limited use of function pointers and virtual functions in C++ classes
>   (function calls must be compile-time determined by the compiler).
> • No recursive function calls.
> • The interface must be precisely defined."
> — Kastner, Matai, Neuendorffer, *Parallel Programming for FPGAs*,
> arXiv:1805.03648v1 (2018-05-11), p.11-12;
> `mine/pp4fpgas-flow.txt:385-397`, read 2026-09-19

and the same book's statement of the output:

> "The primary output of an HLS tool is a RTL hardware design that is capable of
> being synthesized through the rest of the hardware design flow."
> — ibid.; `mine/pp4fpgas-flow.txt:399-400`

### 1.4 Hardware construction languages: the program is the compiler

Chisel, SpinalHDL and Amaranth are a different thing wearing similar clothes.
The host program does not become hardware. The host program *runs*, and what it
builds while running becomes hardware:

> "Chisel comprises a set of Scala libraries that define new hardware datatypes
> and a set of routines to convert a hardware data structure into either a fast
> C++ simulator or low-level Verilog for emulation or synthesis."
> — Bachrach, Vo, Richards, Lee, Waterman, Avižienis, Wawrzynek, Asanović,
> "Chisel: Constructing Hardware in a Scala Embedded Language", DAC 2012, §2;
> `raw/chisel_dac2012.txt:89-93`, left-hand column, read 2026-09-19

This is **C7 (staged evaluation)** in the concept vocabulary, taken to its
limit: the entire host language is the compile-time stage, and the runtime stage
is a circuit. Arbitrary Scala — recursion, collections, file I/O, a solver — is
legal at elaboration time, because none of it survives into the output. The
restriction is not on what the program may do; it is on what may end up in the
graph. This is the cleanest answer to "which language features survive": in a
hardware construction language, *no* source feature survives, because the source
is not translated at all.

FIRRTL is the IR Chisel lowers to, and CIRCT is the current attempt to put that
IR family on MLIR. CIRCT is candid about its state:

> "The CIRCT project is an (experimental!) effort looking to apply MLIR and the
> LLVM development methodology to the domain of hardware design tools."
> — <https://circt.llvm.org/>, read 2026-09-19; `mine/circt.html`

> "Note: we do mean 'active development' (!) — most of these flows are the
> combined efforts of various student, phd and research projects, and should not
> be considered production-ready. You will encounter bugs"
> — <https://circt.llvm.org/docs/HLS/>, read 2026-09-19; `mine/circt-hls.html`

CIRCT's dialect list is the field's taxonomy in one place: `firrtl`, `calyx`,
`handshake`, `pipeline`, `loopschedule`, `hw`, `comb`, `seq`, `sv`, `systemc`,
`verif`, `smt`, `ltl`, `moore`, `esi`, `synth`. A language wanting a hardware
back end today would target one of those rather than emit Verilog directly —
INFERENCE, but the same inference that made LLVM the target of choice for
software back ends.

### 1.5 Clash: the restriction is a type, and recursion is the example

Clash compiles Haskell to VHDL, Verilog or SystemVerilog. Its documented
limitations are the most precise statement in this report of what a functional
language must give up, and they are worth reading in full because A7's own
no-recursion rule lands in exactly the same place.

Clash separates three kinds of recursion:

> "At first hand, it seems rather bad that a compiler for a functional language
> cannot synthesize recursively defined functions to circuits. However, when
> viewing your functions as a structural specification of a circuit, this
> feature of the Clash compiler makes sense."
> — *The Clash Book*, "Limitations of the compiler",
> <https://docs.clash-lang.org/>, read 2026-09-19;
> `mine/clash-print.txt:2651-2653`

*Dynamic, data-dependent recursion* (`fibR n = fibR (n-1) + fibR (n-2)`) is
refused, and the reason is the one that matters:

> "The `fibR` function is not synthesizable by the Clash compiler, because, when
> we take a structural view, `fibR` describes an infinitely deep structure. In
> principle, descriptions like the above could be synthesized to a circuit, but
> it would have to be a sequential circuit. Where the most general synthesis
> would then require a stack. Such a synthesis approach is also known as
> behavioral synthesis, something which the Clash compiler simply does not do."
> — ibid.; `mine/clash-print.txt:2672-2675`

*Value recursion* is accepted and becomes a feedback loop through registers.
*Static, structure-dependent recursion* — a `map` over a length-4 vector, which
could be unrolled at compile time — is refused today for a reason that is about
the compiler and not the model:

> "Sadly, the compile-time evaluation mechanisms in the Clash compiler are very
> poor, and a user-defined function such as the `mapV` function defined above,
> is currently not synthesizable."
> — ibid.; `mine/clash-print.txt:2724`

And the type-level restriction, which is the deeper one:

> "The Clash compiler needs to be able to determine a bit-size for any value
> that will be represented in the eventual circuit. More specifically, we need
> to know the maximum number of bits needed to represent a value. While this is
> trivial for values of the elementary types, sum types, and product types,
> putting a fixed upper bound on recursive types is not (always) feasible. This
> means that the ubiquitous list type is unsupported!"
> — ibid.; `mine/clash-print.txt:2729-2732`

Only `Vec` and `RTree`, whose lengths are type-level naturals, survive.

### 1.6 Accelerator DSLs

**Halide to FPGA** is the clearest published example of a compiler producing
*both* halves of the split, which is the question the user asked:

> "We address this problem by extending the image processing language Halide so
> users can specify which portions of their applications should become hardware
> accelerators, and then we provide a compiler that uses this code to
> automatically create the accelerator along with the 'glue' code needed for the
> user's application to access this hardware. Starting with Halide not only
> provides a very high-level functional description of the hardware, but also
> allows our compiler to generate the complete software program including the
> sequential part of the workload, which accesses the hardware for
> acceleration."
> — Pu, Bell, Yang, Setter, Richardson, Ragan-Kelley, Horowitz, "Programming
> Heterogeneous Systems from an Image Processing DSL", arXiv:1610.09405v1
> (2016-10-28), abstract; `mine/halide-flow.txt:8-22`, read 2026-09-19

It generates more than glue: "the CPU portion of the algorithm, the Linux kernel
drivers for the accelerator" and the calls that reach the hardware
(`mine/halide-hls.txt:88-94`). MEASURED, on a Xilinx Zynq against an NVIDIA
Tegra K1:

> "our design achieves up to 6× higher performance and 38× lower energy compared
> to the quad-core ARM CPU on an NVIDIA Tegra K1, and 3.5× higher performance
> with 12× lower energy compared to the K1's 192-core GPU."
> — ibid., abstract; `mine/halide-flow.txt:26-29`

**Dahlia** attacks the part of HLS that makes it unusable as a compilation
target: the heuristics.

> "We find that the black-box heuristics in HLS can be unpredictable: changing
> parameters in the program that should improve performance can
> counterintuitively yield slower and larger designs. This paper proposes a type
> system that restricts HLS to programs that can predictably compile to hardware
> accelerators. The key idea is to model consumable hardware resources with a
> time-sensitive affine type system that prevents simultaneous uses of the same
> hardware structure."
> — Nigam, Atapattu, Thomas, Li, Bauer, Ye, Koti, Sampson, Zhang, "Predictable
> Accelerator Design with Time-Sensitive Affine Types", PLDI 2020,
> arXiv:2004.04852v2, abstract; `mine/dahlia-flow.txt:18-28`, read 2026-09-19

Its refusals are unusually concrete, and one of them is directly relevant to
A7's index rule:

> "To enforce this hardware generation, Dahlia only allows simple indexing
> expressions like A[i] and A[4] and rejects arbitrary index calculations like
> A[2*i]. General indexing expressions can require complex indirection hardware
> to allow any PE to access any memory bank."
> — ibid. §3; `mine/dahlia-flow.txt:993-999`

Dahlia does not emit RTL. It emits HLS C++ with `#pragma` directives and lets
Vivado HLS finish the job (`mine/dahlia-flow.txt:1576-1582`).

**Calyx** is the IR that layer wants. Its split is the interesting part: a
structural language of components and guarded assignments, and separately a
control language of exactly `enable`, `par`, `seq`, `if` and `while`
(`mine/calyx-flow.txt:429-471`).

> "The Calyx compiler lowers control flow constructs using finite-state machines
> and generates synthesizable hardware descriptions."
> — Nigam, Thomas, Li, Sampson, "A Compiler Infrastructure for Accelerator
> Generators", ASPLOS 2021, abstract; `mine/calyx-flow.txt:31-32`, read
> 2026-09-19

> "Being an intermediate language, Calyx trades-off the convenient programming
> abstraction for predictable compilation."
> — ibid. §3.2; `mine/calyx-flow.txt:418-420`

That control language is the single most important fact in this report for A7,
and §8 returns to it: A7's planned Wave 3 IR is structured control flow with no
SSA, which is the same shape.

### 1.7 Vericert: the verified route, and the price of verification

Vericert is the answer to "can the translation itself be trusted".

> "To address this problem, we present the first HLS tool that is mechanically
> verified to preserve the behaviour of its input software. Our tool, called
> Vericert, extends the CompCert verified C compiler with a new
> hardware-oriented intermediate language and a Verilog back end, and has been
> proven correct in Coq."
> — Herklotz, Pollard, Ramanathan, Wickerson, "Formal Verification of High-Level
> Synthesis", *Proc. ACM Program. Lang.* 5, OOPSLA, Article 117 (October 2021),
> abstract; `raw/vericert_oopsla21.txt:15-18`, read 2026-09-19

What it accepts, and what it refuses:

> "It supports most C constructs, including integer operations, function calls
> (which are all inlined), local arrays, structs, unions, and general
> control-flow statements, but currently excludes support for case statements,
> function pointers, recursive function calls, non-32-bit integers, floats, and
> global variables."
> — ibid. §1; `raw/vericert_oopsla21.txt:90-93`

"function calls (which are all inlined)" is the important clause: inlining is
how a verified HLS tool avoids needing a call mechanism at all, and it "precludes
support for recursive function calls, but this feature is not supported in most
HLS tools anyway" (ibid. §2.3.1, `raw/vericert_oopsla21.txt:336-340`).

The price, MEASURED against LegUp on PolyBench/C:

> "We show that Vericert generates hardware that is 27× slower (2× slower in the
> absence of division) and 1.1× larger than that generated by LegUp."
> — ibid. §1; `raw/vericert_oopsla21.txt:122-124`

A verified translation costs roughly an order of magnitude of performance and
almost nothing in area, and the order of magnitude is mostly one operation. The
authors locate it precisely: "Vericert achieved an average clock frequency of
just 13MHz, while LegUp managed about 111MHz. After replacing the
division/modulo operations with our own C-based implementations, Vericert's
average clock frequency becomes about 220MHz."
(ibid. §5.2, `raw/vericert_oopsla21.txt:1236-1238`) — with division handled,
the verified tool clocks twice as fast as the unverified one.

### 1.8 What this report did not verify

The route table marks its own gaps. Bluespec, SpinalHDL, Amaranth, Intel's HLS
compiler and Siemens Catapult were not read from primary sources; their rows say
so. Spatial's numbers come from a subagent's extraction of the PLDI 2018 paper
and were not re-verified. Catapult claims in §4.2 are VENDOR throughout. §7
lists everything this research failed to obtain.

## 2. The split the user is asking about

### 2.1 Who decides the partition

Four answers exist, and they are ordered by how much the programmer has to know.

**The programmer decides, by writing two programs.** This is the default
commercial flow. You write a kernel, you compile it with an HLS tool, and you
write host code that drives it. Nothing decides anything; there are simply two
source trees. Vitis and XRT work this way.

**The programmer decides, by annotating one program.** Halide-to-FPGA is the
clean example: the user marks which stages of a pipeline become hardware, and
the compiler produces both halves — "we provide a compiler that uses this code
to automatically create the accelerator along with the 'glue' code needed for the
user's application to access this hardware", including "the CPU portion of the
algorithm, the Linux kernel drivers for the accelerator" (arXiv:1610.09405v1,
abstract and §1; `mine/halide-flow.txt:8-22`, `mine/halide-hls.txt:88-94`, read
2026-09-19). One source, one compiler invocation, two artifacts.

**A profiler proposes and the programmer disposes.** LegUp's flow, and the most
honest published account of automatic partitioning:

> "The MIPS processor has been augmented with extra circuitry to profile its own
> execution. Using its profiling ability, the processor is able to identify
> sections of program code that would benefit from hardware implementation.
> Specifically, the profiling results drive the selection of program code
> segments to be re-targeted to custom hardware from the C source. Profiling a
> program's execution in the processor itself provides the highest possible
> accuracy. Presently, we profile program run-time at the function level."
> — Canis, Choi, Aldham, Zhang, Kammoona, Anderson, Brown, Czajkowski, "LegUp:
> High-Level Synthesis for FPGA-Based Processor/Accelerator Systems", FPGA 2011
> §2; `raw/legup_fpga2011.txt:108-116`, read 2026-09-19

And the automation stops one step short of automatic:

> "Our long-term vision is to fully automate the flow in Fig. 1, thereby creating
> a self-accelerating adaptive processor in which profiling, hardware synthesis
> and acceleration happen transparently without user awareness. In the first
> release of our tool, however, the user must manually examine the profiling
> results and place the names of the functions to be accelerated in a file that
> is read by LegUp."
> — ibid.; `raw/legup_fpga2011.txt:132-138`

That sentence, from 2011, is the state of automatic hardware/software
partitioning as this report found it: the measurement is automatic, the decision
is a list of function names in a file. Nothing read here supersedes it.

LegUp names its own lineage — the Warp Processor, which "profiles software
running on a processor" and disassembles the selected binary segments back up to
a synthesizable representation, and Altera's commercial C2H, which "allows a
user to partition a C program's functions into a hardware set and a software
set" running on a Nios II softcore (`raw/legup_fpga2011.txt:39-53`, right-hand
column). The idea is old; the decision is still a list of names.

**The compiler decides, within one instruction stream.** §2.4.

### 2.2 What the interface looks like, and what crossing it costs

LegUp's is the simplest published case and worth stating concretely because it
shows what "the interface is the design" means:

> "The processor connects to one or more custom hardware accelerators through a
> standard on-chip interface. As our initial hardware platform is the Altera DE2
> Development and Education board (containing a 90 nm Cyclone II FPGA), we use
> the Altera Avalon interface for processor/accelerator communication. A shared
> memory architecture is used, with the processor and accelerators sharing an
> on-FPGA data cache and off-chip main memory. The on-chip cache memory is
> implemented using block RAMs within the FPGA fabric (M4K blocks on Cyclone
> II)."
> — ibid. §2; `raw/legup_fpga2011.txt:139-149`

The call mechanism is worth quoting because it is the whole protocol:

> "Functions selected for hardware implementation are automatically replaced
> with a wrapper by the LegUp framework. The wrapper function passes the
> function arguments to the corresponding hardware accelerator, and receives the
> returned data over the Avalon interconnect. While waiting for the accelerator
> to complete its work, the MIPS processor can do one of two things: 1) continue
> to perform computations and periodically poll a memory-mapped register whose
> value is set when the accelerator is done, or, 2) stall until done signal is
> asserted by the accelerator."
> — ibid. §4.2; `raw/legup_fpga2011.txt:158-167`, left-hand column

A function call became a wrapper that writes arguments to a bus, polls a
register, and reads a result. That is what "crossing the boundary" means at
source level, and it is why an accelerated function has to be coarse enough to
pay for it.

The vocabulary generalizes across vendors. AMD/Xilinx's own reference guide
names the three roles:

> "There are three types of AXI4 interfaces:
> • AXI4: For high-performance memory-mapped requirements.
> • AXI4-Lite: For simple, low-throughput memory-mapped communication (for
>   example, to and from control and status registers).
> • AXI4-Stream: For high-speed streaming data."
> — Xilinx, *Vivado AXI Reference Guide* UG1037 v4.0 (July 2017) p.5;
> `raw/xilinx_ug1037_axi_reference_guide.txt:184-190`, read 2026-09-19 (fetched
> from a Wayback snapshot; the live AMD docs site serves JavaScript only)

with the constraint that makes the control path slow: "AXI4-Lite allows only one
data transfer per transaction" (ibid. p.9,
`raw/xilinx_ug1037_axi_reference_guide.txt:273`). So: control registers over a
one-transfer-at-a-time bus, bulk data by DMA over a bursting bus or by streaming
FIFOs, and on coherent platforms shared cache lines instead of an explicit copy.

**The crossing cost is not quantified in this report.** The obvious source is
Choi, Cong, Fang, Hao, Reinman, Wei, "A quantitative analysis on
microarchitectures of modern CPU-FPGA platforms" (DAC 2016,
doi:10.1145/2897937.2897972), which compares "QPI-based Intel-Altera HARP with
coherent shared memory, and PCIe-based Alpha Data board with private device
memory" (abstract, `raw/choi_cong_dac2016_acm_abstract.txt`, read 2026-09-19) —
but only the abstract was reachable; the full text is behind the ACM paywall and
no open copy was found. So: the platforms differ, the paper measured how, and
this report does not have the numbers. Marked UNVERIFIED rather than filled in.

What can be said from what was read: LegUp's design avoids the crossing cost
entirely by sharing a cache, and it still loses clock frequency to do so — the
hybrid circuits "run at 6% lower frequency than the processor, on average"
(`raw/legup_fpga2011.txt:177-178` (right-hand column)). The cost of the interface shows up as a
constraint on the whole system's clock, not only as latency on each call.

### 2.3 The softcore case, and what it costs

LegUp's software half runs on a MIPS softcore inside the FPGA — the Tiger MIPS
from the University of Cambridge, chosen "based on its full support of the MIPS
instruction set, established tool flow, and well-documented modular Verilog"
(`raw/legup_fpga2011.txt:103-107`). MEASURED: "the processor runs at 74 MHz on
the Cyclone II" (`raw/legup_fpga2011.txt:172-173` (right-hand column)).

That number is the softcore's whole story. A CPU built out of FPGA fabric runs
at a fraction of a hard CPU's clock. A modern RISC-V softcore does better but not
by an order of magnitude — the VexRiscv project reports, for its smallest RV32I
configuration at 0.52 DMIPS/MHz, "Artix 7 -> 243 MHz 504 LUT 505 FF", and for
Cyclone IV 179 MHz (project-reported numbers, not independently measured;
<https://github.com/SpinalHDL/VexRiscv>, `raw/vexriscv_readme.md:103-107`, read
2026-09-19; the project states these were obtained "without any specific
synthesis options to save area or to get better maximal frequency" with "The
clock constraint... set to an unattainable value", `:93-95`).

So the softcore route buys a self-contained system and pays for it with a
processor running at roughly an order of magnitude lower clock rate than a
contemporary hard CPU — and that is before accounting for instructions per
cycle, which this report has no measurement for. The measured consequence in LegUp is the sequence of flows: pure
software on the softcore is the baseline, and moving work into hardware is how
you claw back the loss.

MEASURED, LegUp, geometric mean over CHStone-derived benchmarks
(`raw/legup_fpga2011.txt:172-194`, right-hand column):

| Flow | vs. software on the softcore |
| --- | --- |
| Hybrid2 (second-hottest function in hardware) | 50% fewer cycles, 6% lower clock, **1.9× faster** |
| Hybrid1 (hottest function and its descendants) | 75% fewer cycles, 9% lower clock, **3.7× faster** |
| LegUp-HW (everything in hardware) | 12% of the cycles at about the same MHz, **8× faster** |
| eXCite-HW (a commercial tool, everything in hardware) | 8% of the cycles at 45% lower MHz, **6.7× faster** |

Two things to take from that table. First, the speedup is against a 74 MHz
softcore, not against a real CPU, so it is a measure of the partitioning
technique and not of FPGA acceleration. Second, the trend is monotonic:
"execution time decreases substantially as more computations are mapped to
hardware" (`raw/legup_fpga2011.txt:185-187`, right-hand column). The hybrid split is a way station,
not an optimum.

Energy and area, MEASURED by the same paper (energy from Altera's PowerPlay
analyzer with ModelSim switching activity):

> "The LegUp-Hybrid2 and LegUp-Hybrid1 flows use 47% and 76% less energy than
> the MIPS-SW flow, respectively. With LegUp-HW, the benchmarks use 94% less
> energy than if they are implemented with the MIPS-SW flow (an 18× reduction).
> [...] The eXCite energy results are similar to LegUp."
> — ibid.; `raw/legup_fpga2011.txt:265-273`, right-hand column

Area (Cyclone II logic elements, geometric mean, ratio to MIPS-SW in brackets),
from Table 2, `raw/legup_fpga2011.txt:267-275`: MIPS-SW 12243 (1×),
LegUp-Hybrid2 27248 (2.23×), LegUp-Hybrid1 33629 (2.75×), LegUp-HW 15646
(1.28×), eXCite-HW 13101 (1.07×).

Read those three together and the hybrid split looks worse than either end: the
hybrid flows are the *largest* designs, because they pay for the processor and
the accelerator at once, while all-hardware is smaller than either hybrid and
18× more energy-efficient than all-software. The partition is a migration path,
not a destination.

### 2.4 The custom-instruction case: hardware inside the software

The third output is the one the question implies but does not name. The program
stays software. The *processor* changes.

RISC-V reserves encoding space for this in the base ISA. From the opcode map:

> "`<<opcodemap>>` shows a map of the major opcodes for RVG. Opcodes marked as
> _reserved_ should be avoided for custom instruction-set extensions as they
> might be used by future standard extensions. Major opcodes marked as
> _custom-0_ through _custom-3_ will be avoided by future standard extensions
> and are recommended for use by custom instruction-set extensions within the
> base 32-bit instruction format."
> — RISC-V unprivileged ISA specification source,
> `raw/riscv_rv-32-64g_opcode_map.adoc:24-31`, read 2026-09-19

Four major opcodes, permanently donated to whoever wants them. That is the whole
mechanism at the ISA level, and it is why this route is cheap: no new
architecture is needed, only a decoder that recognizes four more patterns and
logic behind it.

Attaching the logic without forking the CPU is what CV-X-IF standardizes:

> "The ``Core-V eXtension interface``, also called ``CV-X-IF``, is an interface
> aimed at extending a |processor| with (custom or standardized) instructions
> implemented in a |coprocessor|. [...] The goal of ``CV-X-IF`` is to enable the
> design and verification of instruction extensions in a |coprocessor| in a
> standardized manner without the need to modify the |processor| itself."
> — OpenHW Group, CV-X-IF specification, `raw/core-v-xif_intro.rst:4-9`, read
> 2026-09-19

**How a compiler is taught to emit them.** Three mechanisms, in increasing order
of integration, all of which were read:

1. **An assembler directive.** GNU `as` accepts `.insn` with an explicit opcode
   space and field values — `.insn r opcode7, funct3, funct7, rd, rs1, rs2` —
   and its documented opcode names include "CUSTOM_0 CUSTOM_1 CUSTOM_2 CUSTOM_3
   Opcode space for customize instructions"
   (`raw/riscv_insn_directive_binutils.txt:1`, read 2026-09-19). No compiler
   change at all: the instruction is spelled out in inline assembly.
2. **A compiler built-in.** Nios II's approach, and the clearest documented
   example of a compiler being taught an instruction. The macro is defined in a
   generated header, and it expands to a GCC built-in indexed by the
   instruction's slot number:
   > "#define ALT_CI_BITSWAP_N 0x00
   > #define ALT_CI_BITSWAP(A) __builtin_custom_ini(ALT_CI_BITSWAP_N,(A))"
   > — Altera, *Nios II Custom Instruction User Guide*, January 2011, Example
   > 2-1; `raw/nios2_custom_instruction_ug.txt:738-739`, read 2026-09-19

   > "The Nios II processor uses gcc built-in functions to map to custom
   > instructions. By default, the integer type custom instruction is defined in
   > a system.h file. However, by using built-in functions, software can use
   > non-integer types with custom instructions. Fifty-two built-in functions are
   > available to accommodate the different combinations of supported types.
   > Built-in function names have the following format:
   > `__builtin_custom_<return type>n<parameter types>`"
   > — ibid. §2; `raw/nios2_custom_instruction_ug.txt:786-792`

   Fifty-two built-ins, named by their type signature, generated alongside the
   hardware. This is a code generator writing a compiler extension, which is
   exactly the shape an agent-driven flow would want.
3. **A real back-end instruction.** LLVM's RISC-V target defines instruction
   formats in TableGen (`raw/llvm_RISCVInstrFormats.td`) and vendor extension
   built-ins in files such as `raw/llvm_BuiltinsRISCVXCV.td`; adding an
   instruction here makes it available to the instruction selector and the
   scheduler rather than only to inline assembly. This was confirmed to exist as
   a mechanism by reading the files; no measurement of what it buys was found.

INFERENCE: routes 1 and 2 are what a small language can reach, because both are
a naming convention over an existing assembler or compiler. Route 3 requires
owning a back end. A7 emits Zig, so its cheapest possible custom-instruction
story would be route 1 through Zig's inline assembly — which requires a native
declaration surface A7 does not have (§8).

## 3. What changes about the language

This is the section that matters for A7, so it is organized by what a language
designer has to decide rather than by tool.

### 3.1 The feature-by-feature verdict

| Feature | Survives? | Why, and who says so |
| --- | --- | --- |
| **Dynamic allocation** | No, everywhere | "An FPGA has a fixed set of resources, and the dynamic creation and freeing of memory resources is not supported" (UG902 p.15, `raw/ug902_2019_1.txt:665-668`). The design "must be fully self-contained, specifying all required resources" (p.284) |
| **Recursion** | No, everywhere, including tail recursion | "Recursive functions cannot be synthesized... Vivado HLS does not support tail recursion" (UG902 p.286). Clash: "describes an infinitely deep structure... would then require a stack". Vericert excludes it. Vericert's reason is the honest one: it inlines all calls, and inlining cannot terminate on a cycle |
| **Pointers and aliasing** | Heavily restricted | "Limited use of pointers-to-pointers (e.g., may not appear at the interface)" (pp4fpgas p.12). An HLS array becomes a block RAM with a fixed number of ports; two pointers that might alias into it force serialization |
| **Function pointers / indirect calls** | No | "Function pointers are not supported." (UG902 p.286). Vericert excludes them. pp4fpgas: "function calls must be compile-time determined by the compiler" |
| **Dynamic polymorphism / virtual dispatch** | No | Same clause in pp4fpgas; it is the same problem as a function pointer, because it *is* one |
| **Exceptions** | No, by omission | No source read here supports them. They require unwinding, which requires a stack, which is the same reason recursion fails — INFERENCE, but consistent with Vericert's "all calls inlined" |
| **Unbounded loops** | Tolerated, but expensive and unanalysable | A loop with an unknown trip count synthesizes to an FSM that loops, so it *works* — but latency and initiation interval become unknown, which is what the reports exist to tell you. The bounded case is the one the tools optimize |
| **Floating point** | Yes in HLS, no in Vericert | UG902 supports `float` and `double` and ships hardware operators for them (`raw/ug902_2019_1.txt:8735-8749` lists `dadd`, `ddiv`, `fmul`, `frsqrt` and the rest). Vericert "currently excludes... floats". Clash requires a statically known bit size, which IEEE floats have, but a float in Clash is a library type, not a primitive of the model |
| **Unsized integers** | No | Clash: "we need to know the maximum number of bits needed to represent a value"; this is why `[a]` is unsupported. Vericert goes further and excludes non-32-bit integers entirely |
| **The standard library** | No | "the STLs cannot be synthesized" (UG902 p.286) |
| **System calls, I/O, files, time** | No | "All data to and from the FPGA must be read from the input ports or written to output ports" (UG902 p.15) |

The pattern under all of it: **hardware has no stack and no heap, and the set of
resources is fixed before the program runs.** Every refusal above is a
consequence of one of those two facts. A language feature survives the
translation exactly when it can be resolved to a fixed set of wires and
registers at compile time.

### 3.2 The timing model is the real change

A statement in C is a step in a sequence. A statement in synthesized hardware is
an operation placed in a schedule:

> "High-level synthesis includes the following phases:
> • Scheduling — Determines which operations occur during each clock cycle based
>   on: Length of the clock cycle or clock frequency; Time it takes for the
>   operation to complete, as defined by the target device; User-specified
>   optimization directives.
> • Binding — Determines which hardware resource implements each scheduled
>   operation.
> • Control logic extraction — Extracts the control logic to create a finite
>   state machine (FSM) that sequences the operations in the RTL design."
> — UG902 (v2019.1) p.6; `raw/ug902_2019_1.txt:171-190`, read 2026-09-19

Three consequences that a language has to answer for.

**The same source produces different timing on different targets.** "If the
clock period is longer or a faster FPGA is targeted, more operations are
completed within a single clock cycle... Conversely, if the clock period is
shorter or a slower FPGA is targeted, high-level synthesis automatically
schedules the operations over more clock cycles" (UG902 p.6,
`raw/ug902_2019_1.txt:179-185`). There is no fixed answer to "how long does this
line take"; the clock constraint is an input to compilation.

**Latency and throughput become separate observable quantities.** The report the
tool emits is the semantics:

> "• Area: Amount of hardware resources required to implement the design...
> • Latency: Number of clock cycles required for the function to compute all
>   output values.
> • Initiation interval (II): Number of clock cycles before the function can
>   accept new input data.
> • Loop iteration latency... • Loop initiation interval... • Loop latency"
> — UG902 (v2019.1) p.7; `raw/ug902_2019_1.txt:230-240`

**Sequential source does not mean sequential hardware, and parallel source does
not mean parallel hardware.** "Loops in the C functions are kept rolled by
default" (UG902 p.6, `raw/ug902_2019_1.txt:200`). Unrolling, pipelining and dataflow are directives, not
meanings. Nothing in the C text says which will happen.

### 3.3 Must the programmer state it? Four different answers

This is the axis that actually separates the families.

**HLS: the programmer states it as pragmas, and the tool may ignore them.** This
is the design Dahlia was written to criticize, and the criticism is measured,
not rhetorical: "changing parameters in the program that should improve
performance can counterintuitively yield slower and larger designs"
(`mine/dahlia-flow.txt:19-22`). The concrete failure is that `#pragma HLS UNROLL`
duplicates the compute units but the memory keeps its original number of ports,
so the tool must serialize what the programmer asked to parallelize.

**Dahlia: the programmer states it, and stating it wrongly is a type error.**
The affine type system "prevents simultaneous uses of the same hardware
structure" — an array read is a capability that is consumed, so two parallel
reads of one bank do not type-check. The restriction is priced in the
evaluation: Dahlia accepts 354 of 32,000 configurations, "about 1.1% of the
unrestricted design space", and those points "lie primarily on the Pareto
frontier" (`mine/dahlia-flow.txt:1639-1647`). A type system that removes 98.9%
of a design space and keeps the good points is a favourable result, and it is
measured rather than claimed.

**Bluespec and Calyx: the programmer states the structure, and the compiler
derives the schedule.** Calyx's control language is `seq`, `par`, `if`, `while`
and group activation, and the compiler "lowers control flow constructs using
finite-state machines" (`mine/calyx-flow.txt:31-32`, `429-471`). The programmer
says what may run in parallel; the compiler says when.

**Clash: the timing is in the type.** A Clash function over plain values is
combinational; only a function over `Signal` is sequential. The book states the
paradigm outright: "only functions working on values of type `Signal` result in
sequential circuits, and all other (non higher-order) functions result in
combinational circuits. This paradigm gives the designer the most
straightforward mapping from the original Haskell description to generated
circuit" (`mine/clash-print.txt:2676-2677`). Registers are explicit function
calls. There is no scheduler to argue with, and correspondingly no scheduler to
do the work for you.

INFERENCE: the four answers trade the same quantity. The more the compiler
schedules, the less the source says about timing, and the less predictable the
output is from reading the source. Dahlia's contribution is the observation that
you can keep the compiler's scheduling and still make the source predictable, by
rejecting the programs where the scheduler would have to guess.

## 4. Verification and determinism

### 4.1 Co-simulation: what it is, and what it is not

The standard check is C/RTL co-simulation, and its mechanism is the limit of its
claim:

> "Post-synthesis verification is automated through the C/RTL co-simulation
> feature which reuses the pre-synthesis C test bench to perform verification on
> the output RTL."
> — UG902 (v2019.1) p.181; `raw/ug902_2019_1.txt:9322-9324`, read 2026-09-19

> "• The C simulation is executed and the inputs to the top-level function, or
> the Device-Under-Test (DUT), are saved as 'input vectors'.
> • The 'input vectors' are used in an RTL simulation using the RTL created by
> Vivado HLS. The outputs from the RTL are save as 'output vectors'.
> • The 'output vectors' from the RTL simulation are applied to C test bench,
> after the function for synthesis, to verify the results are correct."
> — UG902 (v2019.1) p.181; `raw/ug902_2019_1.txt:9327-9337`

So co-simulation proves: *for the inputs this test bench happened to produce,
the RTL agreed with the C.* It is differential testing with one sample set. It
is not equivalence. Vericert's authors put the limitation precisely:

> "Aware of the reliability shortcomings of HLS tools, hardware designers
> routinely check the generated hardware for functional correctness. This is
> commonly done by simulating the generated design against a large test-bench.
> But unless the test-bench covers all inputs exhaustively – which is often
> infeasible – there is a risk that bugs remain."
> — Herklotz et al., OOPSLA 2021 §1; `raw/vericert_oopsla21.txt:69-74`

### 4.2 The stronger checks, and what each proves

| Check | Proves | Cost / caveat |
| --- | --- | --- |
| C/RTL co-simulation | agreement on the test bench's vectors | cheap, shallow; "co-simulation only passes if the C test bench returns a value of zero" (UG902 p.58, `raw/ug902_2019_1.txt:2415`) |
| Sequential logic equivalence checking (SLEC) | the RTL is equivalent to the C++ source, by construction of the tool | Catapult is described by a third party as "designed only to produce an output netlist if it can mechanically prove it equivalent to the input program; it should therefore never produce wrong RTL" (Herklotz et al., FCCM 2021 §II, `raw/herklotz_fccm21_reliability.txt:97-100`). Those authors add "In future work, we intend to test Catapult C alongside Vivado HLS, LegUp, Intel i++, and Bambu" — i.e. the claim is untested by them. Treat as VENDOR |
| Formal property verification (SVA, SymbiYosys) | the *properties you wrote* hold, usually up to a bound | proves nothing about the properties you did not write; bounded model checking proves nothing past the bound |
| Mechanized compiler proof (Vericert) | the translation preserves behaviour, for every input program in the subset | costs 27× performance (2× without division) and 1.1× area against LegUp, and excludes floats, globals, `switch` and non-32-bit integers |

Vericert is the only one of these whose guarantee does not depend on the
engineer's choice of stimulus, and it is the one whose language subset is
smallest. That trade is the whole of §4.

### 4.3 Is it bit-identical? For floating point, no — and the fix runs the wrong way

Xilinx documents the divergence directly:

> "If the standard C math library is used in the C source code, the C simulation
> results and the C/RTL co-simulation results may be different: if any of the
> math functions in the source code have an ULP difference from the standard C
> math library it may result in differences when the RTL is simulated."
> — UG902 (v2019.1) p.231; `raw/ug902_2019_1.txt:12053-12057`

> "Bit-approximate HLS math library functions do not provide the same accuracy
> as the standard C function. To achieve the desired result, the bit-approximate
> implementation might use a different underlying algorithm than the standard C
> math library version. [...] The ULP difference is typically in the range of
> 1-4 ULP."
> — UG902 (v2019.1) p.225; `raw/ug902_2019_1.txt:11707-11715`

The remedy is the interesting part. You do not make the hardware match the
software. You make the software match the hardware:

> "If the hls_math.h library is used in the C source code, the C simulation and
> C/RTL co-simulation results are identical. However, the results of C
> simulation using hls_math.h are not the same as those using the standard C
> libraries. The hls_math.h library simply ensures the C simulation matches the
> C/RTL co-simulation results."
> — UG902 (v2019.1) p.231; `raw/ug902_2019_1.txt:12058-12063`

This is **C1 (reproducible execution)** in a hard form. A program that runs on
the CPU and a program that runs in the fabric are two different programs whose
float results differ by a few ULP, and the only way to get one answer is to
adopt the hardware's answer everywhere. Vericert sidesteps it by excluding
floats from the language entirely, which is the other consistent position.

INFERENCE, on the basis of the above: bit-identity for *integer* work is
achievable and is what Vericert proves; bit-identity for floating point is
achievable only by making the software use the hardware's operators. Reduction
order compounds this — pipelining and unrolling a sum reassociates it, and
floating-point addition is not associative — but no source read here quantifies
that effect for HLS, so it is marked unquantified rather than asserted.

### 4.4 How often is the translation simply wrong? MEASURED

The one systematic study fuzzes four tools with Csmith:

> "We have subjected four widely used HLS tools – LegUp, Xilinx Vivado HLS, the
> Intel HLS Compiler and Bambu – to a rigorous fuzzing campaign [...] out of
> 6700 test-cases, we found 1191 programs that caused at least one tool to fail,
> out of which we were able to discern at least 8 unique bugs."
> — Herklotz, Du, Ramanathan, Wickerson, "An Empirical Study of the Reliability
> of High-Level Synthesis Tools", FCCM 2021, abstract;
> `raw/herklotz_fccm21_reliability.txt:14-31`, read 2026-09-19

Per tool:

> "We see that 918 (13.7%), 167 (2.5%), 83 (1.2%) and 26 (0.4%) test-cases fail
> in Bambu, LegUp, Vivado HLS and Intel i++ respectively. The bugs we reported
> to the Bambu developers were fixed during our testing campaign, so we also
> tested the development branch of Bambu (0.9.7-dev) with the bug fixes, and
> found only 17 (0.25%) failing test-cases remained. Although i++ has a low
> failure rate, it has the highest time-out rate (540 test-cases) due to its
> remarkably long compilation time."
> — ibid. §IV.A; `raw/herklotz_fccm21_reliability.txt:160-166`

The authors' own caveat, which should travel with the numbers:

> "Note that the absolute numbers here do not necessarily correspond to the
> number of bugs in the tools, because a single bug in a language feature that
> appears frequently in our test suite could cause many failures. Moreover, we
> are reluctant to draw conclusions about the relative reliability of each tool
> by comparing the number of failures, because these numbers are so sensitive to
> the parameters of the randomly generated test suite we used. In other words,
> we can confirm the presence of bugs, but cannot deduce the number of them (nor
> their importance)."
> — ibid.; `raw/herklotz_fccm21_reliability.txt:169-179`, right-hand column

And one result that a compiler author should find alarming on its own: across
Vivado HLS v2018.3, v2019.1 and v2019.2, "there are test-cases that fail in
v2018.3, pass in v2019.1, and then fail again in v2019.2"
(`raw/herklotz_fccm21_reliability.txt:228-230`).

Vericert's own framing of why this matters is the C12 framing:

> "current HLS tools cannot always guarantee that the hardware designs they
> produce are equivalent to the software they were given, thus undermining any
> reasoning conducted at the software level."
> — Herklotz et al., OOPSLA 2021, abstract; `raw/vericert_oopsla21.txt:10-12`

### 4.5 The concept links

**C12 (search with a verifier).** HLS is propose-and-check with a weak checker.
The proposer is a scheduling heuristic plus a pragma set; the checker is a test
bench. The measured failure rates in §4.4 are what a weak checker buys. Vericert
is the same pipeline with the checker replaced by a Coq proof, and it costs an
order of magnitude of performance and most of the language. Every design-space
search in §6 inherits this: an agent sweeping pragmas is a proposer, and its
oracle is whatever the flow can check, which today is a test bench.

**C1 (reproducible execution).** Two answers. Integer hardware is deterministic
and, where proved, bit-identical to the source semantics. Floating-point
hardware is not bit-identical to the host libm, by 1-4 ULP, and the documented
fix is to change the software. A language that wanted one answer on both sides
would have to define its float semantics as the hardware's, or exclude floats
from the exported subset.

## 5. The measured reality

### 5.1 HLS against hand-written RTL

The one published meta-study is Lahti, Sjövall, Vanne and Hämäläinen, "Are We
There Yet? A Study on the State of High-Level Synthesis", IEEE TCAD 2019
(doi:10.1109/TCAD.2018.2834439). Its full text is paywalled with no open copy
(Unpaywall reports `is_oa: false`), so only its abstract is quotable — retrieved
through the Semantic Scholar API and saved verbatim to
`raw/s2_lahti.json`, read 2026-09-19:

> "we survey the scientific literature published since 2010 about the QoR and
> productivity differences between the HLS and RTL design flows. Altogether, our
> survey spans 46 papers and 118 associated applications. Our results show that
> on average, the QoR of RTL flow is still better than that of the
> state-of-the-art HLS tools. However, the average development time with HLS
> tools is only a third of that of the RTL flow, and a designer obtains over
> four times as high productivity with HLS. [...] The outcome of our case study
> is also in line with the survey results, as using an HLS tool is seen to
> increase the productivity by a factor of six. [...] Our results let us conclude
> that HLS is currently a viable option for fast prototyping and for designs
> with short time to market."

That is the honest summary of twenty years of HLS: worse hardware, produced
three to six times faster. It is the same trade as a compiler against hand-
written assembly, at an earlier point on the curve.

**Caveat on the evidence.** This is a survey of 46 papers, each of which chose
its own benchmark, its own baseline and its own effort budget for the hand-
written RTL. A comparison against hand-written RTL is only as good as the person
who wrote the RTL, and no published study read here controls for that. Nane et
al.'s TCAD 2016 evaluation, which is the other headline survey, does **not**
compare against hand-written RTL at all — it compares HLS tools with each other
(`raw/nane_tcad2016.txt:931-950`, left-hand column):

> "We experimentally evaluated three academic HLS tools, BAMBU, DWARV and LEGUP,
> against a commercial tool. [...] Overall, the performance results showed that
> academic and commercial HLS tools are not drastically far apart in terms of
> quality, and that no single tool producted [sic] the best results for all
> benchmarks."

### 5.2 Numbers that were actually measured

| Comparison | Result | Source |
| --- | --- | --- |
| HLS vs RTL, survey of 46 papers | RTL QoR still better on average; HLS development time ≈ ⅓; productivity > 4× (6× in the authors' case study) | Lahti et al., TCAD 2019 (abstract only) |
| Tuning pragmas and constraints vs default HLS | "one can expect ∼1.6-2× performance improvement, on average, from tuning code and constraints provided to HLS" | Nane et al., TCAD 2016 §IV; `raw/nane_tcad2016.txt:675-680`, right-hand column |
| Verified HLS vs optimizing HLS | Vericert 27× slower (2× without division), 1.1× larger than LegUp | Vericert, OOPSLA 2021; `raw/vericert_oopsla21.txt:122-124` |
| … the same, on clock frequency | "Vericert achieved an average clock frequency of just 13MHz, while LegUp managed about 111MHz. After replacing the division/modulo operations with our own C-based implementations, Vericert's average clock frequency becomes about 220MHz." | ibid.; `raw/vericert_oopsla21.txt:1236-1238` |
| A generator on a hardware IR vs HLS | Calyx systolic arrays "4.6× faster and 1.11× larger on average than HLS implementations"; 10.78× faster at the largest input size | Calyx, ASPLOS 2021; `mine/calyx-flow.txt:38`, `1336` |
| DSL-generated FPGA vs CPU and GPU | "up to 6× higher performance and 38× lower energy compared to the quad-core ARM CPU on an NVIDIA Tegra K1, and 3.5× higher performance with 12× lower energy compared to the K1's 192-core GPU" | Halide-to-FPGA, TACO 2017; `mine/halide-flow.txt:26-29` |
| Whole program in hardware vs the same program on a softcore | 8× (LegUp-HW), 3.7× (hottest function only), 1.9× (second-hottest only) | LegUp, FPGA 2011; §2.3 above |
| Restricting the design space by types | Dahlia accepts 1.1% of a 32,000-point space, and the accepted points "lie primarily on the Pareto frontier" | Dahlia, PLDI 2020; `mine/dahlia-flow.txt:1639-1647` |

### 5.3 Energy: the evidence is thin, and this report will not pretend otherwise

Two energy figures were found. Halide-to-FPGA's 38×/12× against a Tegra K1 is a
real measurement on a real board, but it is one application domain (image
processing), one platform pair, and one paper. LegUp reports energy only as a
plotted geometric mean with no number in the text
(`raw/legup_fpga2011.txt:339`). The Rosetta benchmark suite asserts FPGAs are
"competitive on energy efficiency compared to CPUs and GPUs"
(`raw/rosetta_fpga2018.txt:98`, right-hand column, read 2026-09-19) but its
tables report LUT/FF/BRAM/DSP counts, runtime and a dollars-per-hour cost ratio
for an AWS `f1.2xlarge` — not watts.

No measured performance-per-watt table for HLS-generated accelerators was found
in this research. "FPGAs are more energy-efficient" is, on the evidence read
here, an assertion supported by one strong data point in one domain, not a
general measured result.

### 5.4 Turnaround: the number that breaks the loop

This is the most important measurement in the report for A7's purposes, because
every other research programme in this directory assumes a fast edit-run-compare
cycle.

**The cheap oracle costs about five minutes.** Dahlia's authors swept an entire
design space in Vivado HLS's estimation mode — no place and route, no bitstream:

> "We explore a design space with banking factors of 1–4 and unrolling factors
> of 1, 2, 4, 6, and 8. This design space consists of 32,000 distinct
> configurations. We exhaustively evaluated the entire design space using Vivado
> HLS's estimation mode, which required a total of 2,666 compute hours."
> — Dahlia, PLDI 2020 §5.2; `mine/dahlia-flow.txt:1610-1623`, read 2026-09-19

2,666 hours over 32,000 configurations is **about five minutes per
configuration**, for the *cheapest* evaluation the tool offers (arithmetic on
the paper's own figures, marked as such).

**The expensive oracle costs hours.** AWS documents its own FPGA build flow, for
its own example designs:

> "DCP build times will vary based on the design size and complexity. The
> examples in the development kit take between 30 to 90 minutes to build."
> — AWS FPGA HDK README, `raw/aws_fpga_hdk_readme.md:120`, read 2026-09-19

and the step after that, turning the checkpoint into a loadable image:

> "The `create-fpga-image` command submits a customer's DCP to AWS to create an
> AFI in the background. This process can take hours depending on the size of
> the design."
> — AWS, *Amazon FPGA Images (AFIs) Guide*, `raw/aws_afi_guide.md:131`, read
> 2026-09-19

Those are two separate AWS documents describing two consecutive steps. No single
source found states the "HLS in minutes, place-and-route in hours" contrast in
one sentence for one design; the contrast here is assembled from the two, and is
marked as such.

**And the cheap oracle disagrees with the expensive one.** This is the fact that
makes the five-minute loop less useful than it sounds:

> "It should be noted that there is no strict correlation between these and the
> actual post place and route frequencies obtained after implementing the
> designs (shown in tables IV and V) due to the actual vendor-provided back-end
> tools that perform the actual mapping, placing and routing steps. This is
> explained by the inherently approximate timing models for computing in HLS."
> — Nane et al., TCAD 2016 §IV; `raw/nane_tcad2016.txt:684-692`, left-hand
> column, read 2026-09-19

So the loop is: five minutes for an estimate that the hours-long truth
routinely contradicts. An agent that sweeps against the estimate is optimizing a
proxy. §6 is about what that costs.

One more data point on compile time, from the fuzzing study: Intel's i++ "has
the highest time-out rate (540 test-cases) due to its remarkably long
compilation time. No other tool had more than 20 time-outs"
(`raw/herklotz_fccm21_reliability.txt:165-168`). Compile time is not a
uniform property of HLS; it varies by more than an order of magnitude between
tools on the same inputs.

### 5.5 Published critiques

No dedicated polemic against HLS quality of results was found as a primary
source. The critique that exists is inside the surveys — Lahti's "the QoR of RTL
flow is still better" *is* the critique, stated by people who went looking — and
inside the reliability literature:

> "Indeed, there are reasons to doubt that HLS tools actually do always preserve
> equivalence. For instance, Vivado HLS has been shown to apply pipelining
> optimisations incorrectly or to silently generate wrong code should the
> programmer stray outside the fragment of C that it supports. Meanwhile,
> Lidbury et al. [2015] had to abandon their attempt to fuzz-test Altera's (now
> Intel's) OpenCL compiler since it 'either crashed or emitted an internal
> compiler error' on so many of their test inputs."
> — Vericert, OOPSLA 2021 §1; `raw/vericert_oopsla21.txt:62-68`

The counterargument, from the same authors, is not "HLS is fine" but "the tool
should be verified": "Our position is that none of the above workarounds are
necessary if the HLS tool can simply be trusted to work correctly"
(`raw/vericert_oopsla21.txt:76-77`).

## 6. The agent angle

An agent can sweep a design space a person will not. The question is what the
sweep needs, and whether hardware flows provide it.

### 6.1 The four requirements, and whether they exist

| Requirement | State of the art |
| --- | --- |
| **A scriptable toolchain** | Yes, everywhere. Vitis HLS runs from Tcl (`csynth_design`, `cosim_design`, `export_design`); Bambu, Yosys, nextpnr, Calyx's `fud`, OpenROAD are all command-line tools |
| **A machine-readable report** | Yes for the ones that matter. Vitis writes `<top>_csynth.xml`; Yosys and nextpnr emit JSON |
| **A fast enough loop** | **No.** 5-30 minutes per HLS evaluation, hours for place and route. This is the binding constraint |
| **A correctness oracle** | **Weak.** A test bench (§4.1), which is why every result in §6.4 reports a simulation pass rate and not an equivalence proof |

### 6.2 The loop is the problem, and three independent sources agree on its size

> "Challenge 5: Long synthesis time of HLS tools: HLS tools usually take 5-30
> minutes to generate RTL and estimate the performance—and even longer if the
> design has a high performance. This emphasizes the need for a DSE that can
> find the Pareto-optimal design points in fewer iterations."
> — Sohrabizadeh, Yu, Gao, Cong, "AutoDSE: Enabling Software Programmers to
> Design Efficient FPGA Accelerators", arXiv:2009.14381v2 §1;
> `raw/autodse_2009.14381.txt:164-166`, read 2026-09-19

> "the evaluation of each candidate design using the HLS tool consumes
> significant time, ranging from minutes to hours, leading to a time-consuming
> optimization process. To accelerate this process, machine learning models have
> been used to predict design quality in milliseconds."
> — Bai, Sohrabizadeh, Qin, Hu, Sun, Cong, "Towards a Comprehensive Benchmark
> for High-Level Synthesis Targeted to FPGAs", NeurIPS 2023 Datasets and
> Benchmarks, abstract; `raw/hlsyn_neurips_abstract.txt:1`, read 2026-09-19

That agrees with the arithmetic on Dahlia's sweep in §5.4 (≈5 minutes per
estimation-mode run) and with DB4HLS, which built a database of "more than
100000 design points" representing "design points collected over 4 years of
synthesis time" run on sixty parallel Vivado HLS instances
(`raw/db4hls_2101.00587.txt:39`, arXiv:2101.00587, read 2026-09-19).

The contrast with software autotuning is explicit in the AutoTVM paper, and it
is the sentence that explains why hardware DSE looks different from every
software search loop:

> "Traditionally, hyper-parameter optimization problems incur a high cost to
> query f, viz., running experiments could take hours or days. However, the cost
> of compiling and running a tensor program is a few seconds."
> — Chen, Zheng, Yan, Yang, Guestrin, Krishnamurthy, "Learning to Optimize
> Tensor Programs", arXiv:1805.08166v4 §4;
> `raw/autotvm_1805.08166.txt:127-128`, read 2026-09-19

Seconds against 5-30 minutes is two to three orders of magnitude. Software
autotuners can brute-force; hardware DSE cannot, and everything in §6.3 is a
consequence.

### 6.3 What people build because the loop is slow

**Search that spends its budget carefully.** AutoDSE treats the HLS tool as a
black box and uses bottleneck-guided coordinate descent instead of random or
exhaustive search. MEASURED:

> "We evaluate AutoDSE on 11 computational kernels from Machsuite and Rodinia
> benchmarks and one convolution layer of Alexnet, showing that we are able to
> achieve, on the geometric mean, 19.9× speedup over a single-thread CPU—only a
> 7% performance gap compared to manual designs."
> — AutoDSE, arXiv:2009.14381v2 §1; `raw/autodse_2009.14381.txt:186-189`

and against a general-purpose autotuner, "S2FA requires on average 16.8 hours to
find the best solution" (`raw/autodse_2009.14381.txt:444`).

**A learned surrogate, so the loop stops calling the tool at all.** GNN-DSE
trains a graph neural network on the program's IR graph plus its pragmas to
predict latency and resource use, "to estimate the quality of design in
milliseconds with high accuracy" (`raw/gnn_dse_2111.08848.txt:27`,
arXiv:2111.08848v2, read 2026-09-19). The measured motivation is the coverage
number: "AutoDSE only explored 3.6% of the space after running for 21 hours as
it is dependent on invoking the time-consuming HLS tool"
(`raw/gnn_dse_2111.08848.txt:669`).

This is exactly the C12 shape, with a warning attached: the surrogate is a
proposer trained on the *tool's own estimates*, and §5.4 established that those
estimates do not strictly correlate with post-place-and-route reality. A
surrogate of an estimate of the truth is two removes from the answer. That is
tolerable when the final candidates are checked properly and dangerous when they
are not — INFERENCE, but it follows directly from Nane's sentence.

### 6.4 Agents generating hardware: measured pass rates, and what they check

Every benchmark below checks **testbench simulation**, not equivalence.

| System | Measured | Source |
| --- | --- | --- |
| VerilogEval (156 HDLBits problems) | GPT-4 pass@1 60.0% (machine set) / 43.5% (human set); GPT-3.5 46.7% / 26.7% | Liu et al., arXiv:2309.07544v2, ICCAD 2023; `raw/verilogeval_v1_2309.07544.txt` |
| RTLLM | three-tier goals — syntax, functionality (testbench), then "quality goal" measured as PPA "after the synthesis and layout of generated V" | arXiv:2308.05345v3; `raw/rtllm_2308.05345.txt` |
| RTLCoder | RTLLM V1.1: GPT-4 100% syntax / 65.5% functional; RTLCoder-DeepSeek 93.1% / 48.3% | arXiv:2312.08617v5; `raw/rtlcoder_2312.08617.txt` |
| MAGE (multi-agent, 2024) | 95.7% syntactic+functional on VerilogEval-Human v2, against "a single Claude-3.5-sonnet agent has a functionality pass rate of only 75.0% even for simple design tasks" | arXiv:2412.07822v1; `raw/mage_rtl_2412.07822.txt` |
| HDLFORGE (2026) | 91.2% / 91.8% Pass@1 on VerilogEval Human and V2; 97.2% Pass@5 on RTLLM; uses "a counterexample-guided formal agent that converts bounded-model-checking traces into reusable micro-tests" | arXiv:2603.04646v1; `raw/hdlforge_2603.04646.txt` |
| LLM-DSE (2025, pragma search not RTL) | "speedups of 2.55×, 1.60×, and 1.16× compared to AutoDSE-8, AutoDSE-24, and HARP-24" | arXiv:2505.12188v3; `raw/llm_dse_2505.12188.txt` |
| LIFT (2025, pragma insertion) | "improve performance by 3.52× and 2.16× than prior state-of the art [sic] AutoDSE and HARP respectively, and 66× than GPT-4o" | arXiv:2504.21187v1; `raw/lift_pragma_2504.21187.txt` |

These numbers were extracted by a subagent from PDFs saved under `raw/`; the
AutoDSE, GNN-DSE, HLSyn, AutoTVM and DB4HLS quotes in §6.2 and §6.3 were
re-verified against the saved files by this report's author, the table rows in
§6.4 were not. Treat the table as a sourced pointer rather than a verified
quotation.

One structural observation, marked INFERENCE: HDLFORGE is the only entry that
strengthens the oracle rather than the proposer. Everything else in the table
improves generation and keeps a test bench as the judge. Under C12 the value
lives in the checker, so the pass rates above measure the proposers against a
judge that §4 showed to be weak.

### 6.5 What a language would have to expose for an agent to drive it

From the requirements table, and stated as design consequences rather than as
findings:

1. **A stable, addressable set of knobs.** Vitis has pragmas; Dahlia has
   unroll/bank factors that the type system validates; Calyx has `par`. An agent
   needs a *named, enumerable* space, not free-form source edits — otherwise the
   sweep is program synthesis, not parameter search.
2. **A machine-readable report with the quantities that matter.** The concrete
   shape is known: hls4ml, a widely used production tool, parses
   `<top>_csynth.xml` for `SummaryOfOverallLatency/Best-caseLatency`,
   `Interval-min`, `Interval-max` and the `AreaEstimates/Resources` children
   `BRAM_18K`, `DSP48E`, `FF`, `LUT`
   (`raw/hls4ml_vivado_report.py:165-186`, from
   <https://github.com/fastmachinelearning/hls4ml>, read 2026-09-19). Latency,
   initiation interval, and four resource counts. That is the whole interface.
3. **An oracle that is cheaper than the artifact.** The reason the field builds
   surrogates is that the true oracle costs hours. A language that wanted an
   agent-driven hardware back end would need a *fast* semantics-preserving check
   — a simulator of the generated design that runs at software speed against the
   software version. Clash gets this for free because its simulation is the same
   function; C-based HLS does not.
4. **Determinism across the sweep.** If two runs of the same configuration give
   different reports, the search is measuring noise. What was read shows
   instability *across tool versions* — Vivado HLS test cases that "fail in
   v2018.3, pass in v2019.1, and then fail again in v2019.2" (§4.4). Whether two
   runs of one version of one tool on one input produce identical reports is
   unchecked: no source read here states it either way.

## 7. Methods, and what this research could not obtain

**How the sources were read.** Every quotation above was checked by grep against
a file saved under `tmp/research/hardware-export/` — `mine/` for the files this
report's author fetched, `raw/` for files fetched by research subagents.
Citations give a file and a line range in that saved file, so any claim here can
be re-checked without a network. Several papers are two-column PDFs whose text
extraction interleaves the columns; where a quote comes from one column of such
a file the citation says which, and the quote was reassembled by reading that
column only.

**AMD documentation.** `docs.amd.com` is a JavaScript application that returns
no text to a plain HTTP client, so the current Vitis HLS guide UG1399 could not
be read. The Vivado HLS guide UG902 v2019.1 was obtained as a PDF instead and is
the primary source for every Xilinx quote here. Vivado HLS is Vitis HLS's direct
predecessor and the constructs quoted (recursion, dynamic allocation, function
pointers, co-simulation, math-library accuracy) are stable across the rename —
but the citations are to the 2019.1 document, not to today's, and should be read
that way. A Grok web lookup was launched as the documented fallback
(`tmp/ai/hwexp-vitis-prompt.md`); UG902 arrived first and made it unnecessary.
At the time this report was finished it had still not produced output
(`tmp/ai/hwexp-vitis.status` empty, `tmp/ai/hwexp-vitis.rc` empty,
`tmp/ai/hwexp-vitis.json` zero bytes). Nothing in this report depends on it, and
no claim here is attributed to it.

**What could not be obtained, plainly:**

| Wanted | Outcome |
| --- | --- |
| Choi, Cong et al., DAC 2016, measured PCIe vs coherent-interconnect latency and bandwidth | Abstract only; ACM full text behind a JS challenge. **The cost of crossing the hardware/software boundary is therefore unquantified in this report** |
| Lahti et al., TCAD 2019, full text | Paywalled, no open copy (Unpaywall `is_oa: false`). Abstract quoted verbatim from the Semantic Scholar record |
| ARM AMBA AXI specification (IHI0022) | developer.arm.com serves JavaScript only; Xilinx's UG1037 paraphrase used instead |
| Atasu, Pozzi, Ienne, DAC 2003 (automatic instruction-set extension) | Bibliographic metadata only; EPFL's repository is a JavaScript application and no archived PDF was found |
| Tensilica Xtensa TIE and XPRES | Not researched |
| Measured performance-per-watt for HLS-generated accelerators | Not found anywhere. See §5.3 |
| Bluespec (Nikhil, MEMOCODE 2004), SpinalHDL, Amaranth, Intel HLS Compiler, Siemens Catapult | Not read from primary sources; their route-table rows are marked UNVERIFIED |
| HARP (ICCAD 2023) | IEEE-only, no preprint; its numbers here are second-hand through papers that cite it |
| A single source stating "HLS in minutes, place-and-route in hours" for one design | Not found; §5.4 assembles it from two AWS documents and says so |

**What was verified by the author versus by a subagent.** All §1, §3 and §4
quotations, and the LegUp, Dahlia, Calyx, Clash, Halide, Vericert, Herklotz,
Nane, AWS, AutoDSE, GNN-DSE, HLSyn, AutoTVM, DB4HLS, Spatial and hls4ml
quotations elsewhere, were re-verified by grep against the saved files. The
§6.4 table of LLM pass rates was not; it is marked as such in place.

## 8. A7: the ruling

Under [EVALUATION.md](../EVALUATION.md) this section is a **ruling**, not a
recommendation. The criterion it meets is the third one: an idea that "depends
on hardware A7 does not target". The user asked for the research, so the research
is above; what follows is the disposition.

### 8.1 The ledger already answers this

> "L8 permits accelerator interface design. It does not qualify any GPU, NPU,
> TPU or FPGA."
> — `docs/plan/decisions.md:79`

Nothing in this report argues with that. Everything in it supports it.

### 8.2 What A7 would need first, in order

**A typed IR with explicit sequencing.** A7 has none today. The plan has one —
Wave 3's "structured typed IR plus a derived CFG, no SSA"
(`docs/plan/execution.md:381`) — and it is gated: "the typed IR (Wave 3) and new
examples wait until Wave 2R exits" (`:26`), where Wave 2R is the correctness
repair program for six compiler audits. So the prerequisite is not merely unbuilt;
it is behind the entire correctness-first program.

The IR's shape, when it exists, matches one target closely. Wave 3's
statement nodes are `If`, `Loop`, `Match`, `Break`, `Continue`, `Fall`, `Return`,
`Defer`, `Del`, `Let`, `Assign`, `Eval` (`docs/plan/execution.md:383`). Calyx's
control language is `enable`, `seq`, `par`, `if`, `while`. `If` and `Loop` map
directly; `Match` lowers to an if-chain; `Break`, `Continue` and `Fall` have no
Calyx counterpart and would need a flag-lowered `while`; `Defer`, `Del` and the
`New`/`DerefPlace` family are outside any synthesizable subset. **The control
skeleton maps, minus early exits and minus memory** — INFERENCE, from reading
both designs, not from anyone having tried it.

**A subset declaration, and the machinery to enforce it.** This is C11
(context-directed compilation) exactly: "what it may allocate, what it may block
on, what timing it must meet, what it must prove", made machine-checkable. A
hardware profile for A7 would admit: functions over `[N]T` and the integer types
and `bool`, structs, enums, `while` with a provable trip count. It would exclude
`new`, `del`, `nil`, `ref`, slices, `string`, `io`, unspecialized generics, and
floats unless the language adopted hardware float semantics (§4.3). A7 has no
profile mechanism, so this would be a new language surface requiring approval
under the "Language change approval" rule.

**Trip-count analysis.** Every route in §1 needs loop bounds. A7 does not
compute them. The nearest existing hooks are the safety pass's facts learned
from "loop shapes" (`docs/SAFETY_CONTRACT.md`) and Wave 3's planned
`dataflow.py` with "widening after 3 header visits"
(`docs/plan/execution.md:385`) — widening is designed to *lose* precision on
loop counters, which is the opposite of what a bound needs. INFERENCE: this is
new analysis, not a reuse.

**An emitter, and a toolchain the repository cannot currently run.** A hardware
back end would be a new module under `a7/backends/` targeting Calyx or a CIRCT
dialect rather than raw Verilog (§1.4). Its output cannot be checked by anything
`run_all_tests.sh` does today: that script drives `zig` and nothing else
(`run_all_tests.sh:61-71`). Checking a hardware export needs a Calyx or CIRCT
compiler, a Verilog simulator, and for any real claim, a vendor place-and-route
flow — none of which are installable dependencies of this repository, and the
last of which is neither free nor fast.

**A co-simulation oracle.** The differential-harness pattern already exists in
`scripts/verify_examples_e2e.py` and in Wave 3's own
`test/test_ir_backend_differential.py` design, which compiles every example two
ways and compares stdout, stderr and exit code. A hardware version would compare
the Zig binary's output against a simulated design's output on the same inputs.
That is C/RTL co-simulation, with the limits §4.1 gives it.

**A timing vocabulary.** A7 has no clock, no initiation interval, no pipeline
depth and no notion that a statement occupies cycles. Every system in §3.3 has
one, in some form, because the timing model is the thing that changes. Adding it
is a language change, not an implementation detail.

### 8.3 What is genuinely favourable, and what is not

**Favourable.** Source recursion is already banned, and it is the restriction
every system in §1 imposes and the one that is hardest to add to a language after
the fact — Vitis refuses even tail recursion, Clash calls it "an infinitely deep
structure", Vericert excludes it because it inlines all calls. A7 paid that cost
for unrelated reasons and would not pay it again. Its index rule (`usize` for
indices, bounds proved at compile time) and its interval facts are the same
*kind* of information a hardware back end needs, and Wave 5's Phase C2 intends to
remove `new`, `del`, `nil` and stored `ref` from the language anyway
(`docs/plan/execution.md`, Wave 5), which would shrink the gap further without
anyone aiming at hardware.

**Not favourable, and worth being precise about.** A7's index rule is *not*
Dahlia's. Dahlia rejects `A[2*i]` outright, to keep the bank mapping static
(§1.6); A7 accepts any `usize` expression it can prove in bounds. Those are
different restrictions solving different problems, and A7's is the weaker one for
hardware. And `usize` is 64 bits (`a7/types.py:129`), so every index in A7 would
become a 64-bit datapath in generated hardware. The interval facts could in
principle narrow it — INFERENCE, and it would be a new inference pass, not a
consequence of the existing one.

### 8.4 The price, and the verdict

Set against what A7 buys: Lahti et al. measured that HLS produces *worse*
hardware than hand-written RTL, three to six times faster to write (§5.1);
Vericert measured that making the translation trustworthy costs an order of
magnitude of performance (§1.7); Herklotz et al. measured that untrustworthy
translation is not hypothetical (§4.4); and the loop costs 5-30 minutes per
evaluation against an estimate that place-and-route routinely contradicts
(§5.4, §6.2).

A7 would be adding, in order: a typed IR it does not have, a profile mechanism
it does not have, a trip-count analysis it does not have, a second backend
target, an external toolchain the test gate cannot run, a co-simulation harness,
and a timing vocabulary that is a language change requiring user approval — in
order to reach a technology whose own literature says it produces worse results
than the alternative and whose feedback loop is three orders of magnitude slower
than the one A7 has today.

**Verdict: out of scope for v1, and for the foreseeable roadmap.** The one thing
worth carrying forward is not a hardware back end at all:

- **The subset discipline transfers.** "The C constructs must be of a fixed or
  bounded size. The implementation of those constructs must be unambiguous"
  (UG902) is a good specification of a restricted profile *for any target*, and
  C11 says such profiles should be machine-checkable rather than documented. If
  A7 ever wants a freestanding, no-allocation, provably-bounded mode — for
  embedded work, for a kernel, for certification — that profile is most of the
  work, and it is useful whether or not hardware is ever the target.
- **The verification result transfers.** Vericert is the clearest demonstration
  in this report that a mechanically verified back end is achievable and that
  its price is performance, not correctness — which is the same C12 trade A7's
  safety pass already makes when it fails closed.
- **The turnaround number is a warning, not a lesson.** Every other research
  programme in this directory assumes a loop measured in seconds. This one is
  measured in hours. Any future proposal that puts A7 output behind a
  multi-hour toolchain inherits that problem whole.
