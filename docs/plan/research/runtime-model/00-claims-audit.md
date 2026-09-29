# Claims audit: reproducible execution, history, and a mutable program

Audit of the eight claims in `tmp/research/runtime-model/claims.md`, supplied by
the user on 2026-09-18 from another project. The features are not the subject.
Each claim appears below as an illustration of one of the concepts named in
[CONCEPTS.md](../CONCEPTS.md); the concept is the thing being researched.

Judged under [EVALUATION.md](../EVALUATION.md): agent value above human value.

## Method

Every source was fetched with `curl` into
`tmp/research/runtime-model/sources/claim<N>/` and every quote here was
grep-verified against the saved file before it was written. Discovery used web
search; nothing was quoted from a search snippet or from a summarizing fetch.
Date read is 2026-09-18 throughout. Quotes are reproduced as they appear in the
saved file except that HTML entities (`&mdash;`, `&quot;`) are rendered as the
characters they denote.

Where a page resisted fetching it is recorded as "not readable" and no quote is
taken. Nothing in this document rests on a secondary lookup. Delegated
GLM-5.3-flash research runs were attempted for the vendor documentation that
resists fetching — Qualcomm's QNN pages, Apple's developer site, Unreal's docs —
and every one returned only a quota error ("Weekly/Monthly Limit Exhausted",
reset 2026-09-22), producing no claims; a later Grok route was tried for the
same gaps. The gaps those runs were meant to close are listed as gaps below,
not filled from an unread source.

Several findings here are **absences**, established by grepping a saved file for
a term and finding none. Those are stated with what was searched, because an
absence is only evidence if the search is named.

Rulings use four terms:

| Term | Meaning |
| --- | --- |
| **established** | Shipped, documented practice, and the claim describes it accurately |
| **achievable at an unstated cost** | Real, but the claim omits what it costs |
| **overstated** | A real mechanism described beyond what it does |
| **false as written** | The claim's own words contradict how the thing works |

## Which claim illustrates which concept

| Claim | Concept | Why |
| --- | --- | --- |
| 1. Deterministic fiber concurrency | C13, C1 | The scheduling half of reproducibility |
| 2. Heterogeneous pipeline (CPU/GPU/NPU) | C1, C2 | Extending reproducibility across accelerators; "unwinds" is history re-entry |
| 3. Shader and kernel hot-swap | C6 | Replacing behavior while running |
| 4. Bit-exact NPU inference | C1 | The numeric half of reproducibility |
| 5. Zero-copy unified memory | C5 | The shape of state, at the accelerator boundary |
| 6. Differential memory arenas | C5, C2 | Flat state; delta snapshots as history |
| 7. Live schema evolution | C6 | Migrating representation while running |
| 8. Cross-architecture IR and remote reload | C6, C3 | Loop cost; and the IR is where source mapping would live |

## C1. Reproducible execution

**What it is.** A program's execution is a function of its inputs: run it again
with the same inputs and get the same result, bit for bit. Everything else in
this batch rests on it.

### Claim 4, bit-exact deterministic neural inference on NPUs

**Ruling: false as written for floating point; achievable at an unstated cost
for integer arithmetic against a pinned reference.** The claim says strict
numeric rules "eliminate non-deterministic cross-silicon rounding drift",
giving "guaranteed reproducibility". Every vendor that has published on this
declines to guarantee exactly that.

NVIDIA's cuDNN documentation gives the scope precisely. Within it:

> generate the same bit-wise results across runs when executed on GPUs with the
> same architecture

Outside it:

> Across different architectures, no cuDNN routines guarantee bitwise
> reproducibility.

And a carve-out even inside the architecture:

> the following routines do not guarantee reproducibility across runs, even on
> the same architecture, because they use atomic operations in a way that
> introduces truly random floating point rounding errors

cuBLAS is stricter still. Its guarantee holds only for GPUs with

> the same architecture and the same number of SMs

so it breaks between two SKUs of one architecture, and

> This guarantee no longer holds when multiple CUDA streams are active

The mechanism is not mysterious. CUDA's own programming model leaves atomic
ordering undefined —

> each read/modify/write to that location occurs and they are all serialized,
> but the order in which they occur is undefined

— and floating-point addition is not associative, as PyTorch states when
explaining why its own backends disagree:

> Each backend performs floating-point accumulation in a different order, and
> because floating-point addition is not associative, the results will differ
> between backends.

NVIDIA's IEEE-754 note marks the exact boundary the claim crosses. A fixed
*algorithm* is portable:

> an implementation of the serial algorithm on multiple systems will give
> exactly the same result

A fixed *operation* is not:

> results computed by an implementation of the serial algorithm may differ from
> those computed by an implementation of the other two algorithms

Different silicon runs different algorithms — different tiling, different
reduction trees. The claim asserts the operation-level property that NVIDIA
declines to assert.

The claim names tensor cores specifically, and that is where the evidence is
bluntest. Of the TF32 format tensor cores use, the CUDA programming guide says:

> The internal layout of this format is implementation defined.

and of how matrix elements map into fragment storage:

> is unspecified and subject to change in future architectures

A vendor that refuses to fix the internal representation is not delivering
bit-exactness across silicon generations, let alone across vendors. And TF32
does not even match FP32 on one device, because it

> round[s] input data to have 10 bits of mantissa

Below the API the compilers take further freedoms. Apple's Metal Shading
Language Specification, on its float optimization mode:

> This option sets how aggressive the compiler can be with floating-point
> optimizations. The default is fast.

which by Apple's own description permits

> Allow Reassociation: Allow algebraically equivalent transformations, such as
> reassociating floating-point operations that may dramatically change the
> floating-point results.

and

> By default, the compiler allows floating-point contractions.

Direct3D's shader language makes the same default explicit:

> By default, all floating-point HLSL operations are considered

"fast" or non-precise, and the compilers may refactor them. Its feature-level
specification defines `mad` and `dp3` by a tolerance rather than a value: they

> must produce results that are no less accurate than the worst possible serial
> ordering

of the unfused expansion. And on Vulkan, IEEE behavior is a queryable capability
rather than a guarantee — which is why `VK_KHR_shader_float_controls` exists at
all:

> extension enables efficient use of floating-point computations through the
> ability to query and override the implementation

**The integer half is the claim's strongest ground, and even it does not reach
"eliminates".** The canonical integer inference specification — TensorFlow
Lite's 8-bit quantization spec, exactly what "standardized fixed-point" points
at — says in its own summary:

> We also understand different hardware may have preferences and restrictions
> that may cause slight deviations when implementing the spec that result in
> implementations that are not bit-exact.

> the nature of machine learning (and deep learning in the most common case)
> makes it impossible to provide any hard guarantees

Its reference kernels ship *two* requantization rounding implementations chosen
by a compile-time define (`#if TFLITE_SINGLE_ROUNDING`), with a separate test
target for each. So integer determinism is a property of a named build of a
named reference, not of fixed-point arithmetic in the abstract.

One real bit-exactness statement was found, and its shape is instructive. Arm's
Ethos-U Vela compiler:

> Vela is tested in-house by comparing the bit exact numerical behaviour of the
> optimised network against that of the corresponding behaviour of the reference
> code.

That is an integer path, compared against a named reference at a pinned version,
and it is a statement about testing. It is not a statement that two different
NPUs agree with each other.

**What the NPU vendors actually say.** Searched for `determinis`, `bit-exact`
and `reproducib` on the readable device documentation of Intel's OpenVINO NPU,
AMD's Ryzen AI, Google's Edge TPU and ONNX Runtime's execution-provider pages:
zero hits on every one. Qualcomm's QNN overview and Apple's `MLComputeUnits`
page are JavaScript shells and could not be read. **No NPU vendor was found to
make a bit-exactness guarantee.** What they do say points the other way. Intel:

> Computation precision for the HW is FP16.

AMD, of FP32 models:

> These models are internally converted to bfloat16 and compiled using the
> bfloat16 compilation flow.

Apple, of its own device:

> The GPU and NE use float 16 precision, and the CPU uses float 32.

> The execution precision varies based on the hardware and software versions,
> since the partitioning of the graph varies with hardware and software.

Google, of the Edge TPU:

> Depending on input/output size, this operation might not be mapped to the Edge
> TPU to avoid loss in precision.

That last one is the sharpest: on a pure-integer accelerator, whether an
operation runs on the accelerator at all depends on tensor shape, so the
execution path is not fixed by the model.

**What survives.** Run-to-run determinism on one device, one driver, one library
version, one build, with atomics-based kernels excluded and autotuning off, is
obtainable — every vendor above describes how. That is a real and useful
property and it is enough for record-and-replay on a fixed machine. It is not
what the claim says. "Cross-silicon" is precisely the word the evidence refuses.

### Claim 2, coordinating accelerators on a shared timeline

**Ruling on the task-graph sentence: established for CPU and GPU, unsupported
for NPU.** The claim says CPU logic, GPU compute and "NPU tensor inferences
coordinate through explicit dependency fences and shared event timelines". The
first two-thirds is ordinary practice with a decade of API support. The NPU
third could not be substantiated, and one piece of shipping driver source
contradicts it.

The GPU machinery is exactly as described. Vulkan timeline semaphores

> Are a synchronization primitive whose state consists of a monotonically
> increasing 64-bit integer value Enable omnidirectional synchronization between
> device and host using a single primitive Allow wait-before-signal submission
> order

D3D12 gives the cross-queue dependency without a host round trip:

> Queues a GPU-side wait, and returns immediately. A GPU-side wait is where the
> GPU waits until the specified fence reaches or exceeds the specified value.

CUDA graphs are the declarative task graph, with CPU work as a node type:

> A graph is a series of operations such as kernel launches, data movement,
> etc., connected by dependencies. A graph is defined separately from its
> execution.

and the timelines interoperate across APIs:

> Synchronization objects can be imported into CUDA using
> cudaImportExternalSemaphore() .

Render graphs in shipping engines are the same idea at the frame level; Unreal's
RDG

> records render commands into a graph data structure to be compiled and
> executed

The NPU is where it stops. On Linux, Intel's NPU is programmed through Level
Zero, whose plain fence is host-facing only:

> A fence can only be signaled from a device's command queue (e.g. between
> execution of command lists) and can only be waited upon from the host.

The spec does define an external-semaphore extension that would bridge the gap.
Intel's shipping NPU user-mode driver leaves every one of its entry points
unimplemented — from `umd/level_zero_driver/api/ze_cmdlist.cpp`:

> .pfnAppendSignalExternalSemaphoreExt = nullptr,

> .pfnAppendWaitExternalSemaphoreExt = nullptr,

and the device-side import and release entry points are null in the same way.
On that platform an NPU cannot import a Vulkan or D3D12 semaphore, and cannot
wait or signal one from a command list. GPU and NPU are separate submission
domains joined through the host.

Windows is the closest to the claim. Microsoft's own DirectML NPU sample selects
the NPU as a D3D12 adapter, gives it a `D3D12_COMMAND_LIST_TYPE_COMPUTE` queue
and an `ID3D12Fence` — so NPU work is fence-synchronized in the same object
model as GPU work. But the same file shows the two qualifications: the adapter
is selected as explicitly non-graphics, a *different* adapter from the GPU, and
the sample synchronizes on the host with `SetEventOnCompletion`, not by one
queue waiting on the other's fence. Cross-adapter GPU-to-NPU queue waits would
need a shared cross-adapter fence, and no vendor document was found saying NPU
adapters support one.

ONNX Runtime defines precisely the interop the claim needs — import a D3D12
fence or a Vulkan timeline semaphore and wait or signal it on an execution
provider's stream — and marks it optional:

> This is an optional EP capability. If the EP does not support external
> resource import,

A code search over the repository found the importer implemented by one
non-test execution provider, `nv_tensorrt_rtx`, which is an NVIDIA GPU provider.
Not QNN, not OpenVINO's NPU, not DirectML.

Apple's is the cleanest refutation of the NPU case. `MPSGraph` can wait on and
signal a Metal shared event, but `MPSGraphDevice` is initialized from an
`MTLDevice` — it is GPU scheduling. The entire public control surface over the
Neural Engine is an enum:

> The set of processing-unit configurations the model can use to make
> predictions.

> to allow the OS to select the best processing unit to use (including the
> neural engine, if available).

There is no queue, no fence and no event. You do not schedule the ANE; you
permit the OS to choose it.

Qualcomm is a negative too, established by absence in its own API index. The
complete QNN API reference saved for this audit (342 KB) contains **zero**
occurrences of "fence" and zero of "semaphore", case-insensitive — verified by
grep on 2026-09-18. Its asynchronous execution entry point takes a notification
callback, not a timeline, and its signal object's only configuration options are
abort and timeout. QNN has no fence primitive to share.

**INFERENCE.** Taken together — Intel's null entry points, ONNX Runtime's
GPU-only importer, Apple's enum — the shared-timeline claim across CPU, GPU and
NPU does not describe any platform that was checkable on 2026-09-18. The
building blocks exist in specifications; the NPU implementations do not.

The second sentence of claim 2, about unwinding command streams, is ruled under
C2 below.

### What C1 requires of a language

- A fixed evaluation order for every expression, including reductions. A7 has
  not decided this: gate G1 lists "tensor reduction order" among the open
  floating-point questions (`docs/plan/README.md`).
- No result-changing float optimizations by default, and contraction (FMA)
  decided explicitly rather than left to the backend. G1 lists this too, and
  notes Zig's strict mode forbids contraction while C compilers may fuse.
- Iteration order of every compiler-internal and language-level map fixed, not
  hash-seed dependent.
- No address-dependent behavior: no pointer values observable as integers, no
  allocation-address-dependent ordering.
- A defined, program-visible boundary for every source of nondeterminism that
  remains (clock, RNG, IO), so a replay can supply recorded values.

### What C1 costs

For the single-threaded numeric part: the cost is forgone optimization —
reassociation, vectorized reductions, FMA contraction, autotuned kernel
selection. No source consulted quantifies that in general; the closest figure is
Apple's implicit one, that strict IEEE is the non-default mode chosen for
correctness over speed. For the parallel part, see C13.

### Agent-facing form

The highest-value concept in the batch. An agent's loop is change, run, compare.
Without reproducibility the comparison is unreliable and every regression
requires re-running to distinguish signal from noise. This is also the one
concept whose absence is silent: a nondeterministic program does not report that
it is nondeterministic.

### Reachable through Zig?

For the numeric part, yes, and A7 is already close. Zig's default float mode is
strict (`docs/plan/README.md`, gate G1), so A7 inherits strictness unless it
opts out. What A7 has not done is *decide* it — G1 is open, and four of its
sub-questions (contraction, literal defaults, NaN ordering in min and max,
tensor reduction order) are exactly the ones that decide reproducibility.

## C13. Deterministic concurrency

**What it is.** Parallel execution has a defined order, so results do not depend
on scheduling. A special case of C1, separated because the cost is specific:
determinism constrains a scheduler, and constraining a scheduler costs
throughput. The research has to say how much, from measurements.

### Claim 1, deterministic fiber concurrency and logical scheduling

**Ruling: false as written; achievable at four unstated costs under a
charitable reading.** The claim says its design "guarantees that multi-core
execution remains **100% bit-exact and repeatable across runs**, preserving
reverse stepping and timeline scrubbing **even under heavy parallel loads**".
Read literally, both emphasized phrases are contradicted by the measured
literature and by the one production tool that delivers reverse stepping. Read
charitably — as a language that forbids data races by construction and fixes its
reduction order — it becomes achievable, at four costs the claim names none of:
losing load balancing, restricting the guarantee to race-free programs, either
abandoning floating point or fixing every reduction tree, and, if reverse
stepping over shared mutable state is really wanted, running on one core.

**The term "deterministic work-stealing scheduler" has no measured precedent.**
Not one source located measures the cost of making work stealing itself
reproducible. Every system that achieves determinism removes stealing, replaces
scheduling with a turn order, quantizes and commits, or serializes onto one
core. Intel's TBB states the mechanism in its own specification:

> parallel_deterministic_reduce uses a simple_partitioner or a static_partitioner
> only because other partitioners react to random work stealing behavior.

and its user guide names the price:

> static_partitioner Deterministic chunk size, cache affinity and uniform
> distribution of iterations without load balancing.

That is the cost claim 1 does not state: determinism is bought by fixing the
partitioning in advance, which means giving up load balancing — exactly the
property a work-stealing scheduler exists to provide.

**Float reductions break bit-exactness independently of the scheduler.** Rayon,
a mainstream production work-stealing runtime, says so in its own API
documentation:

> Note that the order in items will be reduced is not specified, so if the +
> operator is not truly associative (as is the case for floating point numbers),
> then the results are not fully deterministic.

The underlying fact, from Goldberg:

> Due to roundoff errors, the associative laws of algebra do not necessarily
> hold for floating-point numbers.

**The overheads.** Where the claim asserts a guarantee at no stated cost, the
literature gives numbers, and they scale the wrong way. All but the last row are
published measurements; the Hermit row is the project's own planning range and is
marked as such:

| System | Guarantee | Cost |
| --- | --- | --- |
| Kendo (ASPLOS 2009) | weak — race-free executions only | "a geometric mean overhead of only 16% when running on 4 processors" |
| CoreDet (ASPLOS 2010) | strong — arbitrary racy code | "the overheads for 8 threads range from 1.1x–6x" |
| CoreDet, measured independently by DThreads | strong | "run up to 8.4× slower than" pthreads |
| dOS (OSDI 2010) | strong, OS-level | "latency increases by 1.7× for DPGs alone"; parallel workloads 1.2×–10.1× |
| Determinator (OSDI 2010) | deterministic-by-construction OS | "a fixed performance cost of about 35% for the chosen quantum of 10 million instructions" |
| Hermit | determinizes an unmodified Linux guest | "should generally be budgeted at roughly 3-6x native wall-clock time" — a maintainer's planning range, and the README explicitly says it is "not a benchmark promise". Not a measurement; listed here because it is the only figure the project offers |

Kendo is the closest published analogue to the claim's "logical cycle clocks" —
it calls them deterministic logical clocks and builds them from hardware
performance counters. Its 16% is cheap because its guarantee is weak:

> Weak determinism offers the same guarantee for exactly those inputs that lead
> to race-free executions under the deterministic scheduler

DThreads confirms the boundary independently:

> Kendo ensures determinism of synchronization operations with low overhead, but
> does not guarantee determinism in the presence of data races

And Kendo's authors say outright what claim 1 asserts is free:

> we conjecture that it cannot be provided efficiently without hardware support

The same paper undercuts the hardware the claim's "logical cycle clocks" would
be built on:

> many of the performance counter events we tested did not offer deterministic
> results

Hermit, which determinizes an unmodified Linux process, states the structural
trade in its own architecture document: its scheduler tentatively picks the next
runnable thread, and

> This is conservative and limits parallelism, but makes the global snapshot and
> commit order well defined.

Deterministic scheduling and parallelism are traded against each other, by
design, in every system that has built it.

dOS supplies the structural finding that most directly refutes "even under heavy
parallel loads":

> Broadly, overhead tends to increase with sharing, especially as the number of
> threads grows.

The cost of a deterministic schedule rises with exactly the conditions the claim
says it survives.

**Reverse stepping is the sharpest refutation.** rr is the production tool that
delivers reverse execution over arbitrary shared mutable state, and its own
homepage states the price:

> emulates a single-core machine. So, parallel programs incur the slowdown of
> running on a single core. This is an inherent feature of the design.

Its paper adds that the serialization alone — pinning threads to one core with
no recording at all — costs up to 3.36× on a parallel workload, and that

> There is a large slowdown for workloads with a consistently high degree of
> parallelism

So the two halves of claim 1's final sentence are in direct tension: reverse
stepping and heavy parallelism are the trade, not a package.

**The two named techniques do not deliver determinism, and nobody claims they
do.** Fibers: the canonical production fiber job system is Naughty Dog's, and in
1499 lines of extracted slide text the words "determin", "race" and "order" each
occur zero times. Structured concurrency: the founding essay contains zero
occurrences of "determin"; it argues for guaranteed *lifetime and cancellation*,
which constrains when tasks may still be running, not the order in which they
interleave.

**How the industry actually achieves cross-machine bit-exactness.** By giving up
floating point. Photon Quantum, a shipping deterministic multiplayer engine,

> completely replaces all usages of floats and doubles to ensure cross-platform
> determinism

That is the price claim 1 does not name. And even with that price paid,
determinism is not a property that falls out of a design. Factorio, whose
product requires deterministic lockstep and which has years of engineering
behind it:

> Unfortunately making a fully deterministic game is not easy, so you will notice
> desyncs, especially at the beginning of a new experimental release such as this
> one.

Unity is the closest to a vendor determinism claim in this set, and it is
narrower than it looks. Burst's deterministic float mode is architecture-scoped:

> Ensure that floating point calculation in Burst are deterministic, i.e.,
> consistent across all supported platforms. Only supported on 64-bit
> architectures.

and the default mode is `Strict`, not `Deterministic`. Unity Physics' overview
does assert determinism flatly —

> provides a deterministic rigid body dynamics system and spatial query system

— and no page stating a same-platform limitation on that claim was located.
UNVERIFIED: whether Unity qualifies it elsewhere. Note also that the Burst claim
covers float *codegen*, not job scheduling order.

**Two nondeterminism sources the claim never mentions, both live in ordinary
runtimes.** Hash iteration order: Rust's `HashMap`

> algorithm is randomly seeded, and a reasonable best-effort is made to generate
> this seed from a high quality, secure source of randomness

and Python salts string hashes with

> an unpredictable random value

Either makes two runs of the same binary on the same machine differ, with no
scheduler involved. Any claim of bit-exact repeatability has to pin these too.

**What survives.** Deterministic *results* for data-race-free parallel programs
with a fixed reduction order — what Cilk's vocabulary means by determinism:

> The property of a program when it behaves identically from run to run when
> executed on the same inputs.

That is obtainable and useful. It is not a deterministic *schedule*, and it is
the deterministic schedule that reverse stepping through shared mutable state
needs.

### What C13 requires of a language

- No shared mutable state across tasks, or a deterministic protocol for every
  access to it. A7's memory gate M28 already proposes the strong form: "Cross-task
  data moves or stays read-only until join; globals are immutable after program
  start; a conflicting write is an exclusivity rejection" (`docs/plan/memory.md`).
  That is the precondition, and it is stated for safety reasons rather than for
  determinism.
- A fixed reduction order for every parallel reduction, which is a language-level
  decision about what `sum` over a parallel iterator means.
- Structured task lifetime, so the set of tasks at any join point is defined —
  gate G7's `task_group` shape (`docs/plan/README.md`).
- A fixed partition of parallel work, or an accepted loss of determinism when the
  partition adapts.
- No observable timing, no address-dependent ordering, no hash-seed-dependent
  iteration.

### What C13 costs

The table above. In one line: 16% for the weak guarantee on four cores, roughly
1.1×–10× for the strong one, 3–6× to determinize an unmodified Linux process, and
a single core if you want reverse execution. No published measurement exists for
the specific thing claim 1 names — a deterministic work-stealing scheduler —
because the systems that are deterministic do not steal.

### Agent-facing form

High, entirely through C1. An agent that runs a test a thousand times to bisect a
failure needs the thousand runs to agree; a flaky parallel test is worse than no
test, because it consumes the loop without producing information. The agent-facing
version of this concept is not "my program is deterministic" but "a failing run
can be handed to another agent and will fail the same way".

### Reachable through Zig?

Yes, and cheaply, *if* A7 chooses the restrictive shape it is already heading
toward. A7 has no concurrency at all today — zero occurrences of `spawn`,
`Channel`, `thread`, `atomic`, `mutex` or `parallel` in `a7/`, verified by grep on
2026-09-18 — which means it can choose determinism as a property of the design
rather than retrofit it. Gate M28's "moves or stays read-only until join" plus
gate G7's structured task groups plus a fixed reduction order would give
deterministic *results* with no scheduler machinery and no measured overhead from
the table above, because none of those systems' costs are paid: there is no racy
shared state to arbitrate. What it would forgo is exactly what TBB forgoes —
adaptive work distribution — and A7 has no data on what that costs it, because it
has no parallel workload to measure.

## C2. Execution history as data

**What it is.** The record of a run is a value the system can keep, search and
re-enter, rather than an event that happened and is gone. Two families: keep the
whole history, or keep enough to reconstruct any point — an initial state, a log
of non-deterministic inputs, and periodic checkpoints. The second is what makes
"go back to any moment" affordable, and it depends entirely on C1.

### Claim 2, "unwinds and resynchronizes GPU command streams"

**Ruling: false as written.** The claim says that stepping backward
"automatically **unwinds** and resynchronizes GPU command streams and NPU
inference pipelines to the matching logical frame". A GPU has no undo. Every
mechanism that exists moves forward from a saved state; none reverses executed
work.

RenderDoc is the reference implementation of "scrub a frame", and it says what
it does:

> When the capture button is hit the driver will enter active capturing upon the
> beginning of the next frame. In this state every API call is serialised out in
> order and any initial contents and states are saved.

> When replaying, the initial section of the capture (up to the beginning of the
> frame) is read and executed verbatim.

> The basic building block is replaying a partial frame.

Going backwards is implemented by restoring the frame's initial state and
re-running forward to a different point — which is why the docs also record the
leak hazard that forces a saved initial state for every resource, and why
replay is slow:

> Care is taken to minimise this as much as possible as this tends to be the
> slowest operation given the overheads of serialisation and decoding the
> command stream.

PIX works the same way and is blunt about how fragile the recording is:

> A PIX GPU capture records all the Direct3D 12 API calls made by the game,
> including their parameter data. These calls can later be replayed

> We can only guarantee playback will succeed when the GPU and driver are
> exactly the same

The nearest thing to an actual GPU state snapshot is NVIDIA's `cuda-checkpoint`,
and its scope is narrow:

> checkpoints and restores the CUDA state of a single Linux process

It quiesces by draining, not cancelling:

> waits for already-submitted CUDA work to finish before completing a checkpoint

> device memory is copied to the host, into allocations managed by the CUDA
> driver

and excludes unified and IPC memory:

> does not support UVM memory or IPC memory created with

Asked whether it will cover graphics workloads, a maintainer answered on the
project's issue tracker:

> jesus-ramos: No plans for that at the moment.

So for a renderer — the exact case the claim describes, with a frame buffer and
geometry state — there is no vendor checkpoint mechanism at all.

The measured cost of doing this transparently for compute is published. CRUM
(arXiv:1808.00117):

> The runtime overhead of using CRUM is 6% on average, and the time for forked
> checkpointing is seen to be a factor of up to 40 times less than traditional,
> synchronous checkpointing.

CRAC (SC20) reports

> low runtime overhead (approximately 1% or less); fast checkpoint-restart;
> support for scalable CUDA streams

Both are CUDA compute only.

**What is achievable, restated honestly:** re-execution from a checkpoint, with
the command stream recorded and replayed. That is a real and valuable
capability — it is what every GPU debugger does. It is not unwinding, it costs a
full replay of the frame from its start, and its correctness depends on the GPU
results being reproducible, which C1 above shows they are not across silicon,
drivers or library versions.

### Claim 6, delta snapshots as history

Ruled in full under C5 below; the part that matters here is that the snapshot
mechanism is what makes a history affordable, and the claim's "near-zero-cost"
does not survive contact with the measurements. The cheap mechanisms are
page-granular, costing a fault per first write to each page; the fine-grained
mechanism is compiler-inserted write barriers at a measured 1–2% for reference
stores alone. GGPO, the shipped reference for this exact use case, does not
attempt a delta at all — it copies the whole state every frame.

The precondition GGPO states, and the claim omits, is the one that ties this
section back to C1:

> Rollback networking is designed to be integrated into a fully deterministic
> peer-to-peer engine.

### What C2 requires of a language

- C1, without exception. A replay that does not reproduce is not a history.
- A defined boundary around every non-deterministic input, so it can be recorded
  and supplied again: clock reads, RNG, IO, environment, thread scheduling.
- State that can be snapshotted cheaply, which is C5.
- No state outside the snapshot's reach: no hidden globals, no state held by a
  library the runtime does not control, no addresses that change meaning on
  restore.

### What C2 costs

Two published figures for transparent GPU checkpointing: about 6% steady-state
(CRUM) and about 1% or less (CRAC), both CUDA compute only. For CPU-side record
and replay, no figure was gathered here; it belongs to
`01-deterministic-concurrency.md`.

### Agent-facing form

The highest-value concept in the batch after C1, and the one where the agent and
human forms differ most. A person scrubs a timeline and looks. An agent does not
look: it queries. "At which tick did this field first become zero", "which
allocation sites appear in run A and not run B", "replay from tick 4000 with
this input changed" are searches over a data structure, and an agent can run ten
thousand of them. The visual timeline is the least valuable part of the concept;
the queryable record is the whole of it.

### Reachable through Zig?

Partly, and only the cheap half. Input journaling plus periodic state snapshots
needs no runtime support from Zig — it needs A7 to define where non-determinism
enters and to make state snapshot-able (C5). Reverse execution of native code
does not; that needs the ptrace-and-replay machinery of an rr-class tool, which
is a separate program, not a language feature. The accelerator half is out of
scope under ledger L8.

## C3. Provenance

**What it is.** Every value, allocation and effect can name where it came
from — which source construct produced it, when, and from what inputs.

**No claim in this batch asserts it.** That is itself a finding. Eight claims
describe a runtime built for replay, and not one of them says that a value can
name its origin. The nearest hooks are claim 8's internal representation, which
is where a source mapping would have to live, and claim 6's arenas, which give
allocations an address space to be stamped in. The batch that does assert
provenance — a monotonic execution tick stamped on every allocation and event —
is filed under the live-environment programme
([CLAIMS.md](../CLAIMS.md)), not here.

**A7 today has none of it, verified.** `grep -rn -i "source_map\|sourcemap\|#line\|line_directive"`
over `a7/ --include=*.py` returns zero hits, observed 2026-09-18 in this tree.
The Zig emitted for `examples/037_language_tour.a7` begins at
`const std = @import("std");` with no header, no comment and no line directive
naming the `.a7` file it came from. This confirms, from the code rather than
from assertion, the statement in [EVALUATION.md](../EVALUATION.md) that A7 has
"no mapping from the generated Zig back to `.a7` lines".

**What it requires of a language.** A stable identity for source constructs
that survives compilation, and an emission path that carries it. For A7 the
cheapest form is a line directive or comment in the emitted Zig, which costs
nothing at run time and makes a Zig compile error or a native backtrace
traceable to `.a7` source. Anything richer — a birth stamp on each allocation —
requires a runtime that A7 does not have and an allocation identity that the
memory plan has not decided.

**Agent-facing form.** This is where the gap costs the most. A person reading a
Zig error can sometimes guess the `.a7` line. An agent cannot, and every
compiler or runtime failure in a generated file currently arrives without the
one field that would localize it. Provenance converts "read the code and reason
about it" into a lookup, and a lookup is what an agent is good at.

**Reachable through Zig?** The line-directive form, yes, and cheaply. Zig has no
`#line` equivalent, so the practical form is a comment plus a side table the
compiler writes — which makes it a tooling decision rather than a language one.

## C5. State as plain, relocatable data

**What it is.** Program state lives in flat, contiguous, position-independent
structures rather than a graph of pointers into an opaque heap. It is the
enabler concept: snapshotting, serializing, migrating, diffing and rolling back
are trivial for flat data and hard for a pointer graph.

### Claim 6, first-class differential memory arenas

**Ruling: the arena half is established; "at hardware cache-line resolution" is
false as written; "near-zero-cost" is achievable at a measured cost the claim
does not state.** Three sentences, three verdicts.

*Arenas instead of an opaque global heap* — established, and old. Nothing needs
defending here.

*"tracks dirty page deltas and mutation regions **at hardware cache-line
resolution**"* — false as written, and internally inconsistent before any
evidence is consulted: "dirty *page* deltas ... at hardware *cache-line*
resolution" names two granularities for one mechanism, and no mechanism has
both. Beyond that, no commodity mechanism exposes cache-line dirty state to
software at all. Every mechanism that exists is page-granular, and the
one hardware feature that does track cache lines does not let you read the set.

| Mechanism | Granularity | Who can use it | Cost |
| --- | --- | --- | --- |
| Linux soft-dirty | one PTE = one page | any process, via `/proc/PID/pagemap` | write-protect + page fault per first write |
| `userfaultfd` write-protect | PTE; ranges "page aligned" | any process | one message per faulting page (sync mode) |
| `mprotect` virtual dirty bits (Boehm GC) | page | any process | one SIGSEGV handler call per page per epoch |
| Intel PML | 4 KiB, forced by hardware | hypervisor only (a VM-execution control) | VM exit every 512 entries |
| Arm DBM (Armv8.1-A) | "a block or page" | OS | permission fault on first write |
| Intel TSX/RTM write set | **cache line** | nobody — no enumeration instruction | force-aborted by microcode on affected parts |
| HotSpot card table | 512 B default (max 1024) | a managed runtime, via compiler-emitted barriers | measured below |
| CoreCLR card table | 256 B on 64-bit | same | same |

The page-granular sources say so in their own words. The kernel on soft-dirty:

> The soft-dirty is a bit on a PTE which helps to track which pages a task
> writes to.

On `userfaultfd` write protection:

> It supports range operations by default, so one can enable tracking on any
> range of memory as long as page aligned.

Intel's PML, the closest thing x86 has to a hardware-maintained dirty *set*, is
4 KiB by construction:

> Bits 11:0 of the value written are always 0 (the guest-physical address
> written is thus 4-KByte aligned).

and it is not available to an application at all:

> Software can enable page-modification logging by setting the "enable PML"
> VM-execution control

Arm's hardware dirty management is the translation granule:

> Armv8.1-A introduced the ability for the processor to manage the dirty state
> of a block or page.

The one commodity x86 feature that genuinely tracks writes at 64 bytes is
transactional memory:

> Intel TSX maintains the read- and write-sets at the granularity of a cache
> line.

But that set exists to abort a transaction on conflict. There is no instruction
to enumerate it, its capacity is bounded by cache geometry, and on affected
parts Intel turned it off:

> Intel® TSX will be disabled by default.

> The processor will force abort all Restricted Transactional Memory (RTM)
> transactions by default.

(`CLWB` and `CLFLUSHOPT` are sometimes cited here; the SDM classifies them under
"TLB and Cacheability control". They act on an address software already supplies
and report nothing back.)

**So cache-line resolution requires compiler-inserted write barriers, and that
has a measured price.** Blackburn and Hosking, ISMM 2004, measured it:

> the average overhead for a reasonable generational write barrier was less than
> 2% on average, and less that 6% in the worst case

> The average costs are 1.01%, 0.80%, and 4.59% for the AMD, P4 and PPC
> respectively.

Two qualifications the claim would have to absorb. First, those barriers
instrument *reference stores only*; a general state-delta tracker has to
instrument every store, so 1–2% is a lower bound, not the figure. (INFERENCE —
no source measures the every-store case.) Second, even the barrier literature's
own card sizes never reach a cache line:

> the card barrier assumes a heap divided into fixed-size 2k -byte logical cards

> where typically 7 ≤ k ≤ 10

That is 128 to 1024 bytes. No shipped runtime found uses a card as small as 64.
The finest is CoreCLR's 256 bytes, and its source says why it is that size:

> The value of card_size is determined empirically according to the average size
> of an object

— object size, not cache-line size.

*"near-zero-cost delta snapshots"* — achievable at a stated cost, which the
claim does not state: either a page fault per first write to each page, or
1–2%-and-up of every store instrumented. Neither is zero, and the shipped state
of the art is cruder than either. GGPO, the reference rollback-netcode SDK,
takes a full copy:

> save_game_state - The client should allocate a buffer, copy the entire
> contents of the current game state into it, and copy the length into the *len
> parameter.

Bulk copy per frame, not a delta — in the domain the claim names as its use case.

### Claim 5, zero-copy unified memory coherency

**Ruling: hardware-conditional — established on unified-memory parts, false as
written on a discrete GPU.** The claim promises memory "accessible across CPU,
GPU, and NPU **without staging buffers or explicit bus transfers**", giving
"direct, instant access". On an integrated or unified-memory part that is
ordinary: one physical pool, one set of addresses. On a discrete accelerator
across PCIe it contradicts the memory model the APIs define.

Direct3D 12 states why the staging buffer exists at all. Of the heap the GPU
reads fastest (`D3D12_HEAP_TYPE_DEFAULT`):

> This heap type experiences the most bandwidth for the GPU, but cannot provide
> CPU access.

And of the heap the CPU can write:

> This heap type has CPU access optimized for uploading to the GPU, but does not
> experience the maximum amount of bandwidth for the GPU.

The staging buffer is not an implementation detail a better runtime removes; it
is the consequence of the fast memory not being CPU-addressable.

Coherence is likewise a property some memory types have, not a guarantee. The
Vulkan specification defines `VK_MEMORY_PROPERTY_HOST_COHERENT_BIT` as meaning

> the host cache management commands vkFlushMappedMemoryRanges and
> vkInvalidateMappedMemoryRanges are not needed to manage availability and
> visibility on the host.

which says plainly that without the bit they are needed. And where coherence is
present, it is often bought by giving up the CPU cache:

> Host memory read accesses to uncached memory are slower than to cached memory,
> however uncached memory is always host coherent.

"Instant access" has a measured price on a discrete part. NVIDIA's own
measurements of CUDA Unified Memory over PCIe, published 2017 on Pascal and
Volta hardware:

> Still it's almost 2x slower (5.4GB/s) than prefetching (10.9GB/s) or explicit
> memory copy (11.4GB/s) for PCIe.

> This fault handling adds significant overhead to streaming performance of
> Unified Memory on current generation GPU architectures.

Those numbers are nine years old and the hardware has moved; they establish the
mechanism — demand paging with GPU-side faults — and its order of magnitude, not
today's figures. What survives unchanged is the shape: on a discrete part the
transfer does not disappear, it becomes implicit, and the honest restatement of
the claim is "without *explicit* bus transfers".

The NPU third of the claim could not be checked. No vendor documentation was
obtained stating whether Qualcomm's, Intel's, AMD's or Apple's NPU accepts an
arbitrary host heap pointer or participates in CPU cache coherence. That is
recorded as unknown, not as refuted.

### What C5 requires of a language

- No interior pointers into relocatable state, or a complete map of them.
- References that survive relocation: indices, ids or handles.
- A defined, stable in-memory layout, so a snapshot means the same thing when
  restored — which makes C8 (representation control) a prerequisite, not an
  independent nicety.
- No addresses embedded in the state itself, since a snapshot restored at a
  different base address must still be valid.

A7's memory plan already points this way for reasons unrelated to snapshots.
Gate M4 removes stored and returned `ref` in favour of "values, indices or ids";
gate M5 makes removal-capable storage a `Table(T)` with generation-tagged
`Id(T)`; gate M1 makes a `List` position explicitly shift-sensitive
(`docs/plan/memory.md`, section 5). A language that lands those gates has, as a
by-product, state that can be snapshotted.

### What C5 costs

For flat, handle-addressed state: an indirection on every dereference, and the
loss of the ability to hold a pointer into a collection. No published
measurement of that cost was gathered here; Unity's ECS documentation is the
nearest evidence of the design being accepted in production for performance
reasons rather than despite them.

For the unified-memory half on a discrete accelerator: roughly half the transfer
bandwidth of an explicit copy, by NVIDIA's own 2017 figures above.

### Agent-facing form

Medium directly, high indirectly. Flat state is what makes a history affordable,
and a history is what an agent queries. The direct agent win is smaller and
concrete: flat, layout-declared state can be dumped to a file and diffed between
two runs mechanically, which turns "the output changed" into "these 40 bytes
changed".

### Reachable through Zig?

The arena and flat-data half, yes — it is a memory-model decision, and Zig's
explicit allocator interface is a good substrate for it. The unified-memory half
is not reachable and not relevant: ledger L8 confines accelerators to interface
design and its scope limit states it "does not qualify any GPU, NPU, TPU or
FPGA" (`docs/plan/decisions.md`, quoted in
`docs/audits/2026-09-18/design-gaps.md` DSG-12).

## C6. Mutable program during execution

**What it is.** Code and data layouts can change while the program runs,
without discarding the state built so far. Two halves that these claims
conflate: replacing behavior, which is a linking problem, and migrating
representation, which is a data-migration problem with the shape of a database
schema change.

### Claim 7, live dynamic schema evolution

**Ruling: false as written.** The claim says existing instances "are migrated
into the new layout **in-place** using automatic default initialization or
inline migration rules". No system does this, and the systems that come closest
document the opposite mechanism.

Live++ is the commercial state of the art for live C++ editing, and its
documentation (`liveplusplus.tech/docs/documentation.html`) names exactly the
operations the claim describes as "structural changes":

> Changing the memory layout of a class declaration, which includes: adding or
> removing base classes adding or removing non-static data members changing the
> order of non-static data members

Its migration procedure is not in place and not automatic:

> The basic idea is always the same: Serialize the data members of existing
> objects into memory. Delete the objects. Re-create the objects using the new
> class layout. Serialize the data members from memory to the new objects.

The user writes those hooks. And the escape clause the claim never mentions:

> Keep in mind that objects created on the stack cannot be migrated to a new
> class layout.

The JVM, a managed runtime with a precise moving collector and complete
knowledge of every reference, refuses the operation outright. JVMTI's
`RedefineClasses` (`docs.oracle.com/en/java/javase/21/docs/specs/jvmti.html`):

> Instances of the redefined class are not affected -- fields retain their
> previous values.

> The redefinition must not add, remove or rename fields or methods, change the
> signatures of methods, change modifiers, or change inheritance.

The Linux kernel's livepatch cannot add a field to a live struct either. Its
answer is a side table keyed by the object's address
(`docs.kernel.org/livepatch/shadow-vars.html`):

> Shadow variables are a simple way for livepatch modules to associate
> additional "shadow" data with existing data structures. Shadow data is
> allocated separately from parent data structures, which are left unmodified.

Unity's ECS, designed from the start around flat chunked data, still relocates
the instance when its shape changes
(`docs.unity3d.com/Packages/com.unity.entities@1.3/manual/concepts-structural-changes.html`):

> When you add or remove components from an entity, you change the entity's
> archetype. Unity stores each entity in a chunk that matches the entity's
> archetype. This means that if you change an entity's archetype, Unity must
> move the entity to another chunk.

> Structural changes to the data in ECS are the primary cause of sync points.

Erlang is the one mature working model, and it works by not being in place at
all. Two versions of a module are live simultaneously
(`erlang.org/doc/system/code_loading.html`):

> Both old and current code are valid, and can be evaluated concurrently.

> To change from old code to current code, a process must make a fully
> qualified function call.

The process rewrites its own state, at a point it chooses, through
`code_change/3`. Erlang can afford this because it has no raw pointers and no
shared mutable heap: there is no second reference to invalidate.

The claim's second promise — "preventing crashes or corrupted data pointers
when types change on the fly" — inverts the causality. Pointer corruption is not
a hazard that careful migration avoids; it is the reason every system above
either forbids the change, relocates the object and hands out an id, or makes
the program serialize itself across the transition.

### Claim 3, live shader and compute kernel hot-swap

**Ruling: one clause false as written, one established, two unmeasured.** The
claim bundles four assertions and they do not share a verdict.

*"without ... invalidating pipeline state objects (PSOs)"* — **false as
written**, by the definition of the object. Microsoft's reference page for
`ID3D12PipelineState` states it plainly:

> The only way to change states contained within the pipeline object is to
> change the currently bound pipeline object.

and the states contained in it include the shaders:

> Represents the state of all currently set shaders as well as certain fixed
> function state objects.

Shader bytecode is a member of the create-info struct
(`D3D12_SHADER_BYTECODE VS;`), not a settable property. Vulkan is the same:

> When a pipeline is created, its state and shaders are compiled into zero or
> more device-specific executables, which are used when executing commands
> against that pipeline.

There is no update entry point in either API. Changing a shader *is* creating a
new pipeline object and discarding the old one. Even DXR's incremental
`AddToStateObject`, the nearest thing to editing a pipeline in place, does not
edit it:

> Since `AddToStateObject` returns a new state object, this enables the
> application to free the original object when it is no longer needed

One escape exists and it is narrower than the claim. `VK_EXT_shader_object`
removes pipeline objects altogether:

> This extension introduces a new object type `VkShaderEXT` which represents a
> single compiled shader stage.

Under it, "without invalidating PSOs" is vacuously true because there are no
PSOs — but the compile does not go away:

> This function compiles the source code for one or more shader stages into
> `VkShaderEXT` objects.

It is a Vulkan-only optional extension, and no D3D12 equivalent was found.

*"without ... stalling the command queue"* — **established**, and it is the
standard technique. NVIDIA documents it directly:

> An application should therefore either create all PSOs upfront (e.g. at level
> load), or asynchronously create state objects on background threads and
> hot-swap them when ready.

Compile off the render thread, swap at a frame boundary. Khronos built an
extension for the same purpose, and the wording says why:

> The main aim of this proposal is to reduce the cost of loading novel state and
> shader combinations within the rendering loop, thus avoiding hitching.

*"on every keystroke"* — **overstated**, and the measurements say by how much.
NVIDIA's guidance on ray tracing pipelines, which the claim names explicitly:

> Collections and pipelines can take tens to hundreds of milliseconds to
> compile.

and, asked the typical cost in shipping games:

> Anywhere from, 20ms → 300ms, per pipeline.

Unreal instruments runtime pipeline compilation as a defect:

> A PSO compilation is marked as a hitch if the compilation took longer than a
> certain amount of milliseconds for the runtime PSO to be compiled.

> The default value of 20 milliseconds is high because the first hits on the
> driver cache can take a long time.

Its own live shader workflow is a command, not a keystroke, and it warns about
scale:

> If you change a file that is included in many shaders (such as, common.usf),
> this can take a while.

One genuinely measured on-device figure exists, from the Khronos Vulkan
Samples, rebuilding the pipelines for the Sponza scene on a Mali G76 phone:

> Pipeline re-creation takes 24.4 ms thanks to the pipeline cache. If we disable
> the pipeline cache, re-creating the pipelines takes 50.4 ms, more than double
> the previous time.

A 60 fps frame budget is 16.7 ms. Every figure in this section exceeds one
frame. Godot states the consequence in its own documentation:

> there was no solution to pipeline compilation other than generating them when
> an object shows up inside the camera's view, leading to the infamous shader
> stutter

Live per-keystroke shader editing is real at one scale. Bonzomatic:

> This is a live-coding tool, where you can write a 2D fragment/pixel shader
> while it is running in the background.

and even it recompiles on `F5 or Ctrl-R`, not per keystroke. One 2D fragment
shader against a ray tracing pipeline with many hit groups is several orders of
magnitude apart, and no public measurement was found for per-keystroke
recompilation of the latter. The honest statement is: unmeasured, and the
nearest measured figures (20–300 ms per RT pipeline) are far outside a
keystroke budget.

*"maintaining the current frame buffer and geometry state"* — **established and
trivial**. Buffers, images and samplers are separate objects reached through
descriptors; destroying a pipeline does not touch them. The claim presents as an
achievement something the object model gives for free.

### Claim 8, cross-architecture IR and remote hot reload

**Ruling: achievable at an unstated cost**, for both halves.

The IR half is ordinary. What the claim does not state is the price of "ultra-fast
direct translation", and there is a measured number for it. Zig's 0.15.1 release
notes (`ziglang.org/download/0.15.1/release-notes.html`) report its self-hosted
x86_64 backend replacing LLVM in Debug:

> Compilation time is significantly improved — around a 5x decrease compared to
> LLVM in most cases.

That 5x is for Debug-quality code, on one architecture. The cost shows in the
other two places the claim names. Code quality: QBE, the reference small
multi-target backend, states its own ceiling (`c9x.me/compile/`):

> QBE is a compiler backend that aims to provide 70% of the performance of
> industrial optimizing compilers in 10% of the code.

Architecture count: the claim lists three ISAs as though they were a
configuration option. A funded, full-time effort with the x86_64 backend
finished reports of its second:

> This backend is passing 1656/1972 (84%) behavior tests relative to LLVM, so is
> not ready to be enabled by default, nor is it currently usable in any real use
> case.

Cranelift, the other standard answer, claims less than the marketing around it
suggests. Its own README says only:

> This has the potential to improve compilation times in debug mode.

No measured multiplier appears in that README. A specific Cranelift-vs-LLVM
figure was not obtained from a primary source here.

The remote half is real and commercially shipped, at a cost in build
configuration the claim does not mention. Live++ splits into a broker on the
developer machine, an agent inside the running target process, and a network
link between them:

> Bridge and Broker communicate with each other via TCP/IP using the host name
> or IP address configured in the global preferences on port 12216.

> The Agent ships as a small shared library (e.g. .dll on Windows and Xbox)
> which is loaded into the target application

So consoles are in the product line. The devkit-specific documentation is not
public; no source can be cited for it, and none is cited here. What can be cited
is the build-time cost of patching live native code, from the kernel's own
livepatch documentation (`docs.kernel.org/livepatch/livepatch.html`):

> Livepatch works reliably only when the dynamic ftrace is located at the very
> beginning of the function. The function need to be redirected before the stack
> or the function parameters are modified in any way. For example, livepatch
> requires using -fentry gcc compiler option on x86_64.

> Only functions that can be traced could be patched.

A patch point must be reserved in every function at compile time, and the switch
needs a per-task safety argument:

> the affected unit (thread, whole kernel) need to start using all new versions
> of the functions at the same time. Also the switch must happen only when it is
> safe to do so, e.g. when the affected locks are released or no data are stored
> in the modified structures at the moment.

### What C6 requires of a language

Replacing behavior requires, at minimum: a reserved patch point in every
function (a build-time decision), a defined quiescence point at which the swap
happens, and either no inlining across the boundary or a way to invalidate what
was inlined. Migrating representation requires strictly more:

- No interior pointers into migrated objects, or a precise map of every one.
- References that survive relocation — handles, ids or generational indices,
  not addresses. Unity hands out entity ids for exactly this reason.
- No addresses held across the reload by anything the language does not control:
  no raw pointers in FFI-held structures, no addresses stored in files or sent
  over a socket.
- No live instances on the stack, or a way to rewrite frames. Live++ simply
  excludes them.
- A defined default for every added field, and a defined disposal for every
  removed one.

A7 has decided almost none of this, and two of its existing rules point in
opposite directions. Memory gates M4 and M5 already move A7 toward the working
model: stored and returned `ref` are removed in favour of "values, indices or
ids", and `Table(T)` with generation-tagged `Id(T)` is the recommended
removal-capable storage (`docs/plan/memory.md`, gate table in section 5). That
is precisely the handle indirection migration needs. Against it, gate M25 (the
native declaration surface) will hand raw addresses to C libraries, and every
such address is a reference the compiler cannot rewrite.

### What C6 costs

The measured figures are the compile-throughput ones above. For the migration
half there is no published cost measurement, because no system performs the
operation automatically; the cost is paid in hand-written hooks, and none of the
sources quantifies that.

### Agent-facing form

Low value, and lower than for a person. A person hot-reloads to avoid losing a
session — a level loaded, a debugger attached, a state reached by twenty
minutes of play. An agent has no session to lose: it rebuilds and re-runs, and
does so a thousand times. The concept that survives the translation is not
liveness but **loop cost**: wall-clock time from edit to observed behavior.

Measured for A7 on this machine (Linux x86_64, Zig 0.16.0, 2026-09-18),
`examples/037_language_tour.a7` at 143 lines:

| Stage | Command | Wall clock |
| --- | --- | --- |
| A7 front end, no file written | `uv run a7 --mode pipeline` | 0.262 s |
| Zig build to native binary | `zig build-exe tour.zig` | 0.298 s |
| Total edit-to-binary | | ≈ 0.56 s |

That is already well inside a usable loop for a file this size, and it means the
argument for A7 adopting hot reload cannot be made on loop cost — there is no
latency to recover. The number that will matter is how this scales, and the
scaling risk is on the A7 side: the front end is Python, and the Zig half is
already backed by the self-hosted backend whose 5x improvement is spent.

### Reachable through Zig?

Behavior replacement: not today, and not by A7's own effort. It needs a patch
point in every emitted function plus a loader, and the layer that would have to
provide it — Zig's incremental compilation — states its own status:

> This feature is still experimental — it has known bugs and can lead to
> miscompilations or incorrect compile errors.

Representation migration: incompatible with a native binary produced through
Zig unless A7 first adopts handle-only references everywhere, which is a
language decision (gates M4, M5) taken for other reasons and not yet approved.

## Gaps

What was looked for and not found. Each is a gap in the evidence, not a finding
against the claim.

| Gap | Status |
| --- | --- |
| A published measurement of a *deterministic work-stealing* scheduler | None located. Every deterministic system measured removes stealing, replaces it with turn-taking, quantizes and commits, or serializes to one core. The claim's central phrase has no measured precedent |
| Whether Unity limits its Physics determinism claim to the same platform or architecture | Not found. Two unqualified Unity claims were located and no page stating a limitation. UNVERIFIED — unfound, not disproven |
| Qualcomm NPU determinism or reproducibility statement | `docs.qualcomm.com` serves a JavaScript shell. No statement located in any readable source. (The fence absence is separately established from the QNN API index, which *was* readable) |
| Apple Metal storage-mode documentation on Apple silicon vs discrete GPUs | `developer.apple.com` pages are JavaScript-rendered. Not obtained |
| NPU memory model: whether any NPU accepts an arbitrary host heap pointer or participates in CPU cache coherence | Not obtained for any vendor |
| NPU checkpoint or restore, from any vendor | Nothing sourced. There appears to be no documented mechanism to snapshot or rewind an NPU inference pipeline at all |
| A measured Cranelift-vs-LLVM compile-time multiplier from a primary source | Not obtained. The project README claims a potential, not a number |
| A measured shader compile latency for one large desktop shader through a driver backend | Not found. The figures that exist are whole-scene (24–50 ms, Mali G76) or vendor statements (20–300 ms per RT pipeline) |
| Whether Intel *removed* TSX/RTM from later microarchitectures, rather than only force-aborting it by microcode | Unverified. Only the microcode force-abort is sourced |
| A source stating that executed GPU work cannot be undone | None exists as a spec statement. INFERENCE from the API surfaces: fences only "reach or exceed", checkpoint drains rather than cancels, replay restores initial state and re-runs |
| The measured cost of instrumenting *every* store rather than reference stores only | Not measured anywhere located. The 1–2% barrier figure is a lower bound for the claim's use case |
| Console devkit deployment documentation | Not public. Live++'s architecture is the nearest public evidence |

## Verdict table

| # | Claim | Ruling | Strongest single piece of evidence |
| --- | --- | --- | --- |
| 1 | Deterministic fiber concurrency; "100% bit-exact ... even under heavy parallel loads" | **False as written.** Achievable at four unstated costs under a charitable reading (race-free by construction, fixed reduction order) | oneTBB's own spec: "parallel_deterministic_reduce uses a simple_partitioner or a static_partitioner only because other partitioners react to random work stealing behavior" — determinism is bought by removing stealing, and its user guide adds that the deterministic partitioner works "without load balancing" |
| 2a | CPU/GPU/NPU coordinate through "explicit dependency fences and shared event timelines" | **Established for CPU and GPU; false as written for NPU** | Intel's shipping Linux NPU driver leaves every Level Zero external-semaphore entry point null: ".pfnAppendWaitExternalSemaphoreExt = nullptr,". Qualcomm's complete QNN API index contains zero occurrences of "fence" or "semaphore" |
| 2b | Stepping back "unwinds and resynchronizes GPU command streams" | **False as written.** Charitably read as restore-and-re-execute: achievable at an unstated cost | RenderDoc: "When replaying, the initial section of the capture (up to the beginning of the frame) is read and executed verbatim." Going back is re-running forward from a saved state |
| 3 | Shader recompile "on every keystroke without ... invalidating PSOs or stalling the command queue" | **Mixed: one clause false as written, one established, one overstated, one trivially true** | Microsoft on `ID3D12PipelineState`: "The only way to change states contained within the pipeline object is to change the currently bound pipeline object." A shader change *is* a new PSO |
| 4 | NPU/tensor-core determinism "eliminates non-deterministic cross-silicon rounding drift" | **False as written.** Run-to-run determinism on one fixed configuration is achievable at an unstated cost | cuDNN: "Across different architectures, no cuDNN routines guarantee bitwise reproducibility." The CUDA guide calls TF32's "internal layout of this format ... implementation defined" |
| 5 | Unified memory "without staging buffers or explicit bus transfers" | **Hardware-conditional: established on unified-memory parts, false as written on a discrete GPU** | D3D12 on the heap the GPU reads fastest: "This heap type experiences the most bandwidth for the GPU, but cannot provide CPU access." NVIDIA measured demand-paged unified memory at 5.4 GB/s against 11.4 GB/s for an explicit copy (2017, Pascal/Volta, PCIe) |
| 6a | Arenas instead of an opaque global heap | **Established** | Ordinary practice; GGPO's shipped snapshot API is a bulk copy of a contiguous state region |
| 6b | Dirty tracking "at hardware cache-line resolution" | **False as written.** Achievable only through compiler-inserted write barriers, at a measured cost | Every readable mechanism is page-granular; Intel PML forces the low 12 address bits to zero ("thus 4-KByte aligned"). The one cache-line tracker, Intel TSX, has no enumeration instruction and is force-aborted by microcode |
| 6c | "near-zero-cost delta snapshots" | **Achievable at an unstated cost** | Blackburn & Hosking measured write barriers at "1.01%, 0.80%, and 4.59% for the AMD, P4 and PPC respectively" — and that is for reference stores only |
| 7 | Live schema evolution, instances "migrated into the new layout in-place ... automatic" | **False as written** | Live++, the commercial state of the art, migrates by hand-written hooks: "Serialize the data members of existing objects into memory. Delete the objects. Re-create the objects using the new class layout." And: "objects created on the stack cannot be migrated to a new class layout" |
| 8a | An IR for "ultra-fast direct translation" into x86-64, ARM64 and RISC-V | **Achievable at an unstated cost** | Zig measured its own self-hosted backend at "around a 5x decrease compared to LLVM in most cases" — Debug only, one architecture; its second architecture is "passing 1656/1972 (84%) behavior tests ... not ready to be enabled by default" |
| 8b | Run and hot-reload on tethered consoles and devkits over a link | **Established commercially, at an unstated build-time cost** | Live++ ships a broker/agent split over TCP with an agent ".dll on Windows and Xbox". The cost: the kernel's livepatch "requires using -fentry gcc compiler option on x86_64" — a patch point reserved in every function at compile time |

## What the design actually buys

Taken as one design, the eight claims are not eight features. Three of them are
load-bearing for time travel and replay, one is load-bearing only under a
condition the claims do not state, and four are independent capabilities that
could be dropped without losing any of it.

**Load-bearing.**

- **Claim 1 (deterministic concurrency)** and **claim 4 (numeric determinism)**
  are the two halves of C1. Replay is a function of them. If either fails, the
  history is a recording of one run rather than a re-enterable state, and the
  whole design degrades to "keep a video of what happened".
- **Claim 6 (arenas and delta snapshots)** is what makes the history affordable.
  Without cheap snapshots you either keep every state (unaffordable) or replay
  from the beginning every time (slow enough to stop being interactive).

**Load-bearing only under a condition the claims never state.**

- **Claim 2 (accelerators on a shared timeline)** and, through it, claim 4's NPU
  half. These matter *if and only if* accelerator results feed back into
  simulation state. If the GPU is output-only — it draws what the simulation
  decided and nothing flows back — then neither GPU determinism nor GPU
  unwinding is needed for time travel, and claim 2 reduces to "re-execute the
  rendering for the frame you scrubbed to", which is exactly what RenderDoc
  already does. The claims never say which reading applies. Their own examples
  ("AI-driven entity behaviors, motion matching, neural physics
  approximations") are all feedback cases, so the design appears to intend the
  hard reading — and the hard reading is the one C1 shows is not obtainable
  across silicon.

**Independent, droppable without losing time travel.**

- **Claim 3 (shader hot-swap)** is a developer convenience. Nothing in replay
  needs it.
- **Claim 5 (zero-copy unified memory)** is a performance property of the
  accelerator boundary. It makes claim 2 cheaper; it does not make it possible.
- **Claim 7 (live schema evolution)** is the most separable of all. Time travel
  needs state that can be *copied*; it does not need state whose *type* can
  change mid-run. Erlang has hot code loading without time travel; rr has time
  travel without hot code loading.
- **Claim 8 (multi-target IR and remote reload)** is about where code runs and
  how fast it builds. Orthogonal to replay in both halves.

**The honest summary of the design.** Strip the four droppable claims and what
remains is: make execution reproducible, record the inputs, snapshot cheaply,
and re-execute. That is rr's design and rollback netcode's design, and both
work. The eight-claim version adds accelerators — which is where every ruling
above turns negative — and liveness, which is the part an agent does not need.

## For A7

A7 today is an ahead-of-time compiler from `.a7` to Zig with no runtime of its
own, no concurrency, no accelerator support, no incremental compilation and no
reload story. Verified by grep over `a7/ --include=*.py` on 2026-09-18: zero
occurrences of `tensor`, `spawn`, `Channel`, `extern`, `atomic`, `thread`, `gpu`
and `parallel`, matching `docs/audits/2026-09-18/design-gaps.md`. Also zero
occurrences of `source_map`, `sourcemap`, `#line` or `line_directive`, and the
emitted Zig carries no reference of any kind to the `.a7` file that produced it.

### Worth adopting, in order

**1. C1 numeric determinism — decide gate G1 now, as a determinism decision.**
This is the only item on the list that is free. Zig's default float mode is
already strict, so A7 inherits reproducible arithmetic unless it opts out. What
is missing is the decision. Four of G1's open sub-questions are exactly the ones
that decide reproducibility: whether v1 offers an opt-in fast mode at all,
multiply-add contraction, NaN ordering in min and max, and tensor reduction
order (`docs/plan/README.md`, G1). Each has a reproducible answer and a fast
answer, and G1 currently records neither. The cost of deciding is one gate; the
cost of not deciding is that A7's numerics become reproducible or not by
accident of what Zig's backend happens to do.

Concretely, the reproducible answers are: no fast mode in v1, contraction
forbidden by default, a fixed reduction order specified in the language rather
than chosen by the backend. Each is a language change and therefore needs
approval under the CLAUDE.md rule; none is a new syntax.

**2. C1 applied to the compiler itself — gate M40, which is already planned.**
`docs/plan/memory.md` gate M40 proposes "Versioned approval keys, ordered
analysis iteration, and a test that compiles one program twice under different
hash seeds and compares the emitted Zig". That is the first reproducibility work
A7 should do, and it is about the compiler, not the compiled program. It is also
the cheapest instance of the highest-value concept in this whole batch: an agent
that cannot trust the compiler to emit the same Zig twice cannot trust any
comparison it makes. Note the specific hazard the claim-1 evidence names for
A7's own implementation: Python salts string hashes with "an unpredictable
random value" by default, so a compiler that iterates a `dict` or a `set` keyed
by string can emit different output on two runs of the same input. M40's
hash-seed test is exactly the right test.

**3. C13 deterministic concurrency — make it a property of G7's design, not a
retrofit.** A7 has no concurrency, which is an advantage: it can choose the
restrictive shape before anything depends on the permissive one. Memory gate M28
already proposes the necessary condition for safety reasons — "Cross-task data
moves or stays read-only until join; globals are immutable after program start;
a conflicting write is an exclusivity rejection". A language with that property
plus gate G7's structured `task_group` plus a language-fixed reduction order
gets deterministic *results* without paying any cost in the table above, because
none of those systems' costs apply: there is no racy shared state to arbitrate,
so there is no arbitration overhead. What it forgoes is adaptive work
distribution, the same thing TBB's deterministic reduce forgoes. G7 should state
determinism as a decision, alongside the four questions it already asks.

What A7 should *not* promise is a deterministic schedule or reverse stepping.
Those need single-core execution (rr) or 1.1×–11× overhead (CoreDet, dOS), and
nothing in A7's plan calls for them.

**4. C5 flat, handle-addressed state — already the direction, worth naming the
second benefit.** Memory gates M4 (remove stored and returned `ref`, use "values,
indices or ids") and M5 (generation-tagged `Id(T)` in a `Table(T)`) were proposed
for memory safety. They happen to be the precondition for cheap snapshots,
serialization and rollback. That is worth recording in the memory plan as a
second reason, because it changes the cost-benefit of those gates: they are not
only a safety tax, they buy a capability.

**5. C3 provenance — the cheapest high-value item not on anyone's list.** A7
emits Zig with no back-reference to the source. A comment or side table mapping
emitted Zig lines to `.a7` lines costs nothing at run time, needs no language
change, and converts every Zig compile error and every native backtrace from an
unlocalized failure into a lookup. For an agent this is the single largest
practical gain available here, and it is a tooling change, not a gate.

### Not worth adopting

**Claim 2, claim 4's NPU half, claim 5.** Out of scope by the ledger, and the
evidence says they would not deliver what they promise anyway. L8 permits
accelerator interface design and its scope limit states it "does not qualify any
GPU, NPU, TPU or FPGA" (`docs/plan/decisions.md`). Nothing in the audit above
argues for revisiting that: cross-silicon bit-exactness is refused by every
vendor who has published on it, no NPU exposes a fence that a GPU timeline can
wait on, and unified memory is a property of hardware A7 does not target.

**Claim 3.** A7 has no shaders, no GPU backend and no render loop. Nothing
transfers except one observation, which belongs in the compile-latency budget
rather than in the language: the state of the art in live shader editing
recompiles on an explicit command, and the best measured figures (24–50 ms for a
scene, 20–300 ms for a ray tracing pipeline) all exceed a frame.

### Incompatible with compiling to a native binary through Zig

**Claim 7, live schema evolution.** Not reachable, and the obstacle is a
language decision A7 has not made rather than a Zig limitation. In-place
migration requires that every reference to a migrated object be findable and
rewritable. A7's plan is heading toward the ids and handles that would make this
possible (gates M4, M5), but gate M25 — the native declaration surface — will
hand raw addresses to C libraries, and every address held outside the language
is a reference the compiler cannot rewrite. Gate M12's descriptors ("borrowing,
retention, returned storage, alignment, completion, callbacks and thread
affinity") are the place where that would have to be decided, and they do not
currently contemplate reload at all. Note also that the commercial state of the
art does not do this either: Live++ requires the user to write
serialize-delete-recreate hooks, and excludes stack objects outright.

**Claim 3 and claim 8's reload half, live code replacement.** Not reachable
today, and the blocker is not A7's. Replacing a running function needs a patch
point reserved in every emitted function at compile time — the kernel's livepatch
needs `-fentry` for exactly this — plus a loader and a quiescence protocol. A7
would have to ask Zig for all of it, and Zig's incremental compilation, the
nearest layer, states its own status: "This feature is still experimental — it
has known bugs and can lead to miscompilations or incorrect compile errors."

**Claim 8's IR half, partially reachable but not worth building.** A7 compiles
through Zig, and Zig already ships the thing claim 8 describes: a self-hosted
backend "around a 5x decrease compared to LLVM in most cases" in Debug, with
aarch64 in progress. A7 gets multi-target code generation for free by emitting
Zig. Building A7's own low-level IR and native backends would be a large project
to reacquire something it already has, and the measured cost of doing it well —
one architecture finished, the second at 84% of a behavior suite — is a fair
estimate of the effort.

### The loop-cost number, since it is the thing an agent actually feels

Measured on this machine (Linux x86_64, Zig 0.16.0, 2026-09-18) for
`examples/037_language_tour.a7`, 143 lines: 0.262 s for the A7 front end
(`--mode pipeline`), 0.298 s for `zig build-exe` on the generated Zig, about
0.56 s end to end. That is a usable loop, and it means no argument for hot
reload in A7 can be made on latency grounds today. The number to watch is how
the Python front end scales, since the Zig half is already on the fast backend.

