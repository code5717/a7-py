# Source claims, verbatim (supplied by the user 2026-09-18, fourth batch)

Headings are the user's. This batch restates and extends batches 1-3; the master
register at docs/plan/research/CLAIMS.md records which items are new.

## Temporal and deterministic architecture

**Continuous state-space reversibility.** "Execution is modeled as an append-only timeline of discrete, deterministic transformations rather than destructive memory mutations. The runtime treats program history as an indexed dimension that can be scrubbed bidirectionally with zero state loss. Forward execution and backward unwinding possess identical operational guarantees."

**Deterministic input journaling and low-cost checkpointing.** "Non-deterministic boundary events—such as hardware interrupts, peripheral inputs, network packets, operating system calls, and monotonic clock ticks—are intercepted at the platform boundary and appended to a continuous input journal. The runtime coordinates this log with periodic, sparse copy-on-write memory snapshots of contiguous arenas. Reconstructing any arbitrary tick in program history requires only restoring the closest prior snapshot and fast-forwarding the recorded input log."

**Monotonically reified execution intrinsics.** "The runtime exposes a native, 64-bit monotonically increasing execution tick as a zero-cost intrinsic. Dynamic memory allocations, spawned entities, compute passes, and external side effects are permanently stamped with this temporal index at creation. Developers can directly query the birth tick of any in-game object to warp the entire debugger, memory state, and display output back to the exact CPU cycle and source instruction that instantiated it."

**Spatial projection of temporal trajectories.** "Temporal lifespans and procedural futures are projected visually as spatial structures inside the live canvas. Instead of stepping forward frame by frame to observe velocity or collision results, the runtime evaluates forward simulation ticks speculatively and draws the complete trajectory curve directly in the active scene. Changing constants or logic in the code reshapes the rendered trajectory curve instantly."

**Bidirectional code-state historical synchronization.** "The code editor and runtime timeline share a synchronized temporal coordinate system. Modifying a function during a live session creates a timestamped version delta within the editor. Scrubbing the execution timeline to an earlier frame causes the source editor to rewind its display, presenting the exact code implementation that was active when that frame was originally simulated."

## Compilation and reactive runtime pipeline

**Sub-perceptual keystroke codegen.** "The compiler is designed without traditional intermediate optimization bottlenecks or external linker stages. Operating as an in-memory, single-pass machine code generator, it translates modified syntax directly into executable memory pages in sub-millisecond intervals. Native code is emitted and hot-patched on every individual keystroke, eliminating the traditional write-compile-link-run loop."

**Zero-link function trampolining and page hot-swapping.** "Hot-reloading operates through dynamic function indirection tables and atomic prologue trampolines. When a function body is edited: The compiler parses and emits machine code only for the altered symbol into a fresh executable memory segment. The previous function prologue is atomically overwritten with an unconditional relative jump (`jmp rel32`) pointing to the new address. Active stack frames, register states, and persistent heap allocations remain undisturbed during the transition."

**Arbitrary compile-time code execution (`#run`).** "The language makes no semantic distinction between code executed during compilation and code executed at runtime. Any arbitrary function, algorithm, asset parser, or procedural generator can be evaluated during the compilation phase. The compiler acts as a full execution environment capable of computing lookup tables, validating invariants, and structurally reshaping the AST prior to native machine-code emission."

**Condition systems and stack-preserving error suspensions.** "Runtime panics, assertion failures, and memory violations do not unwind or discard the active call stack. When an invalid operation occurs, the runtime suspends the faulted fiber in place, leaving local registers, parameters, and heap references completely intact. The developer can edit the offending logic in the source editor, recompile the function live, and instruct the runtime to resume execution directly from the restored frame."

**Dynamic live schema evolution.** "Altering structural definitions—such as appending fields, reordering struct members, or changing type widths—does not require restarting the environment or dumping memory. The runtime diffs the structural changes against active memory layouts and automatically executes in-place layout migrations or updates pointer offsets across active arenas without zeroing live state."

## Memory architecture and heterogeneous synchronization

**Contiguous arena partitioning.** "The language bans arbitrary, scattered heap allocations in favor of contiguous, pre-sized memory arenas (Linear Arenas, Scratch Rings, and Persistent World Arenas). Program state is stored strictly as flat, relocatable Plain Old Data (POD) structures. This layout guarantees instant serialization, trivial delta snapshotting for reverse debugging, and cache-coherent batch access."

**Deterministic multi-fiber concurrency.** "Concurrency is decoupled from preemptive, non-deterministic OS threads. Parallel workloads execute across a user-space fiber pool governed by a deterministic work-stealing scheduler. Work units coordinate using explicit dependency DAGs and logical cycle clocks instead of blocking OS mutexes. This guarantees that multi-core execution remains bit-exact and repeatable across recordings, rollbacks, and multi-machine re-evaluations."

**Unified heterogeneous coherency (CPU, GPU, NPU).** "Accelerators operate inside a unified virtual address space governed by common dependency timelines rather than isolated driver bridges. Command buffers, compute shaders, and neural tensor operations are scheduled against the master simulation tick: **Live shader mutation:** Modifying compute kernels or rendering shaders recompiles machine bytecode on every keystroke, swapping shader pipelines without invalidating pipeline state objects or clearing GPU buffers. **Deterministic tensor inference on NPUs:** Neural network models executing on dedicated neural processors adhere to strict bit-exact floating-point or fixed-point accumulation standards, preventing numerical drift across different hardware accelerators during replay. **Accelerated time scrubbing:** Unwinding the timeline automatically unrolls GPU command queues and NPU inference states back to the target logical tick."

## Ambient visual introspection and interactive feedback

**Bidirectional source-to-visual co-projection.** "**Code-to-pixel:** Hovering or selecting any line of code immediately outlines and highlights the specific primitives, sprites, or geometry generated by that instruction on the screen. **Pixel-to-code:** Selecting any on-screen visual element or pixel inspects the live graphics pipeline and jumps the editor to the exact line of code and local variable responsible for rendering it."

**Direct parameter scrubbing and live in-place modulation.** "Numeric constants, vectors, color literals, and procedural constraints embedded in the source text act as continuous interactive controllers. Holding a modifier key and dragging over a numeric value sweeps the parameter across a continuous range, updating physics equations, procedural generators, or UI layouts in real time. This immediate feedback exposes dynamic thresholds and creative opportunities hidden by blind value guessing."

**Unfolded algorithmic iteration matrices.** "Loops, traversals, and recursive functions are unfolded horizontally into concrete visual matrices rather than evaluated as hidden sequential abstractions. Each loop iteration occupies an explicit, side-by-side data column showing the exact concrete state of local variables, comparison flags, and array indices. Edge cases, logic inversions, and off-by-one boundary failures are visible directly in the matrix without requiring breakpoints or print statements."

**Moldable contextual object inspectors.** "Debugging does not rely on raw hexadecimal memory dumps or generic tree views. Data structures define their own contextual, visual projection methods inside the language. Inspecting a spatial tree renders an interactive 2D bounding hierarchy; inspecting a network buffer renders an annotated packet frame; inspecting an AI entity renders its active behavior graph and utility curve."

**Continuous analog and gestural stream capture.** "Dynamic envelopes, procedural timing, and animation paths can be recorded into the runtime via continuous analog performance inputs (stylus, multi-touch, or analog controllers). Developers can physically perform a motion curve like a musical instrument. The recorded stream is materialized directly into the runtime timeline and mapped back into code parameters for mathematical tuning."

## Diagnostic systems and collaborative artifacts

**Reverse hardware data watchpoints.** "Hardware memory watchpoints operate bidirectionally. Placing a watchpoint on a corrupted variable, invalid pointer, or overwritten memory block allows the developer to command the debugger to step backward in time. The debugger scans the recorded history in reverse and stops at the precise write instruction, loop pass, and thread context responsible for the illegal memory write."

**Time-anchored diagnostic profiling.** "Call-graph instrumentation can be compiled in and out of the running binary without interrupting the active simulation. Latency spikes and memory allocation spikes recorded on the profiler timeline can be clicked directly, instantly warping the entire debugger and memory state to the exact execution tick where the performance regression occurred."

**Self-contained replay sessions (`.session`).** "When a crash, memory stomp, or visual artifact occurs, the entire state is serialized into an ultra-compact, portable session package containing: The base memory arena snapshot. The append-only input journal and external event records. The code diff log capturing every dynamic edit made during the run. Any developer on any machine can load the session file to reproduce the exact bit-for-bit execution trace, step backward from the crash point, and inspect the failure without altering their local working tree."
