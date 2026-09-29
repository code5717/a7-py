> **Source:** Claude Code reading subagent, group G, full read of saved repository research.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# G. Language features, AI frameworks, hardware providers: notes for the L15/L16 brainstorm

Sources read completely (every line):

- `docs/plan/research/language-features-codex.md` (1532 lines), cited as **LF:n**
- `docs/plan/research/ai-frameworks-codex.md` (615 lines), cited as **AI:n**
- `docs/plan/research/hardware-providers-codex.md` (323 lines), cited as **HW:n**
- Context: `docs/plan/decisions.md` (**DEC:n**), `docs/plan/README.md` (**PLAN:n**)

All three files are Codex research dated 2026-09-14. They were written **before** L15
(memory direction) and L16 (float behavior), both dated 2026-09-15 (DEC:47-48). None of
them discusses garbage collection, compile-time memory resolution, or data-oriented design
by name. Where I connect a passage to L15, that connection is my own **inference**.

---

## 1. Per-file summaries

### 1.1 language-features-codex.md (LF)

- **Status:** advisory research. It "approves no language change and verifies no
  implementation" (LF:6). It used selective source inspection and in-memory probes. The
  full release gate, native runs, fuzzing and security review were not performed (LF:30-31).
- **Main recommendation:** build a typed IR with a CFG, stable identities (`SourceId`,
  `DeclId`, `BindingId`, `OperationId`, ...), effect summaries, exact constant evaluation
  and checked transformation boundaries before adding features (LF:15, 719-784). The IR
  should emit Zig, and direct LLVM or MLIR should be deferred (LF:723-730).
- **Defects that constrain the plan:** safety facts are keyed by name, scope and branch
  restore loses writes, calls do not invalidate facts, and integer division folding goes
  through Python float (LF:146-159, 161-169).
- **Proposed packages:**
  - A: source text
  - B: numerics, with wrapping implemented modulo 2^N (LF:294)
  - Floats: an approval gate (LF:375-409)
  - C: composites, matching and errors
  - D: functions and generics
  - E: modules
  - F: structured concurrency (LF:982-1060)
  - Stdlib contracts (LF:1064-1127), native descriptors (LF:1131-1156), CLI and tooling
    (LF:1160-1231)
- **Recursion ban:** needs a whole admitted-call graph with iterative SCC analysis over
  resolved identities, including closures, callbacks and foreign re-entry (LF:692-715).
- **Ownership:** explicitly delegated to "the memory report" (LF:790, 1154, 1314). This
  file only says how ownership results must feed the compiler: dataflow events such as
  deletion, move, task transfer and suspension (LF:792-808).
- **Limits:** no Jai claims ("No unverified Jai feature claim is used", LF:209). Tagged Zig
  `Air.zig`, `Zir.zig` and `Io.zig` could not be opened (LF:1531). LSP fields were not
  verified (LF:1231). Milestones run M0-M12 (LF:1334-1348).

### 1.2 ai-frameworks-codex.md (AI)

- **Status:** advisory. Nothing was built, benchmarked or runtime-qualified (AI:29, 615).
  Sources are moving documentation labels, not pinned releases (AI:597-614).
- **Architecture:** A7 owns tensor semantics, AD, optimizer state, RNG and checkpoints.
  Native kernels come through a small versioned C-ABI bridge (AI:13, 354-376).
- **CPU v1 recommendations** (AI:17-23):
  - a synchronous runtime with an eager reverse-mode tape
  - a portable reference path for every operator and dtype
  - OpenBLAS or BLIS for f32/f64
  - optional oneDNN, which must never be the only path (AI:348)
  - functional tensor operations with storage reuse "only when old values are no longer
    observable"
- **Floats:** "IEEE values with strict scalar semantics, plus explicit numerical checks at
  training boundaries" (AI:25, 149). This matches L16.
- **Tensor contract:** covers storage identity, offset, strides, lifetime, views, copies and
  broadcast (AI:250-272). It also defines the functional-update and buffer-reuse rule
  (AI:278-294).
- **AD:** first-order reverse mode with an iterative execution tape. A per-operator
  registry declares saved values and their lifetimes (AI:296-330). Recomputation needs
  replayable regions (AI:330).
- **Mixed precision:** an f32 master, accumulator and optimizer, with a full-step skip on
  non-finite gradients (AI:212-246).
- **Workloads:** a CNN classifier and a small decoder, including an optional KV cache
  (AI:425-485). Acceptance scenarios cover tape lifetime, mutation, OOM and checkpoint
  continuation (AI:487-513).
- **Limits:** no memory-use claims were verified (AI:615). The file says the plan needs
  runtime error values because shapes, allocation and files "cannot all be proved away at
  compile time" (AI:402, labeled inference in the source).

### 1.3 hardware-providers-codex.md (HW)

- **Status:** read-only. No hardware was run and no accounts were opened (HW:11). The
  sibling AI report was absent when checked (HW:13).
- **Recommendation:** stay CPU-first. The first accelerator should be a narrow CUDA
  backend, then selected ROCm configurations (HW:9). The ordered roadmap has ten rungs
  (HW:234-249).
- **Taxonomy:** classify devices by execution contract (CPU, GPU, graph accelerator,
  DSP/spatial, FPGA, hosted API), not by vendor label (HW:20-33). The file includes vendor
  matrices for CPU, GPU, NPU, TPU/custom silicon and cloud providers (HW:35-179).
- **Numerics:** "does not support a blanket promise that an IEEE storage type implies
  identical IEEE execution across all tensor backends" (HW:106). BF16 flushes subnormals on
  Intel, Arm and TPU. CUDA FTZ and contraction depend on compiler flags. Gaudi's "float64"
  is not binary64 (HW:108-122).
- **Backend architecture:** adapters own device enumeration, capability description,
  buffer allocate/import/export "with explicit ownership and lifetime", artifact caching,
  and submission with completion and errors (HW:193-218).
- **Async and DLPack:** A7 must prevent conflicting mutation and premature destruction
  until an asynchronous operation completes (HW:220). DLPack does not solve this by itself
  (HW:222).
- **Open decisions** include "Asynchronous borrowing of mutable tensor referents" and
  "Canonical versus device-packed serialization" (HW:292-293).
- **Limits:** the GLM security handoff is out of scope (HW:300). Prices are unranked
  (HW:181). Local host identity only: Ryzen AI 9 HX 370 / Radeon 890M, unqualified (HW:49).

---

## 2. Material that constrains or informs the L15 memory design

L15 wording (DEC:47): "Automatic memory management without a runtime collector, designed for
data-oriented programs, resolved at compile time, in the style of Jai, Odin and Zig".

### 2.1 Tensor storage, views, aliasing and buffer reuse

- **What A7 owns.** AI:252-257: "Storage identity, offset, strides, and lifetime. Rules for
  views, copies, broadcasting, and mutation." Storage identity is a separate concept from
  the tensor value, so the memory model needs a storage entity distinct from its view
  handles.
- **Layout contract** (AI:261-270):
  - Creation is "Contiguous row-major".
  - Transpose and simple slicing produce "Read-only views where representable".
  - Reshape is a "View when legal; otherwise explicit or documented materialization".
  - Broadcast has "no ambiguous writable overlapping view".
  - Gather produces a "New result".
  - "Kernel packing | Private storage, separate from public tensor layout".
  - **Inference:** whether an op returns a view or new storage is partly data-dependent
    (reshape legality depends on strides). A compile-time lifetime analysis must treat a
    reshape result as "may alias its input" unless the strides are known.
- **Stride and flatten limits.** AI:51-52: "`flatten` cannot always promise a shared-memory
  view for arbitrary strides" and "`usize` strides cannot represent negative strides".
- **New object versus new storage.** AI:272: "new array object" and "new storage" are
  different. AI:103 (PyTorch): basic indexing returns views, advanced indexing returns
  copies, and `reshape` may do either.
- **Buffer-reuse rule.** AI:292: "The runtime may reuse `x`'s allocation only if no live
  alias, saved AD value, or caller can observe its former contents. Binding immutability
  alone is insufficient evidence." This is the central reuse obligation. Under L15 it
  would need to be discharged statically (**inference**), for example by uniqueness or
  last-use analysis.
- **Runtime version counters.** AI:294: "shared-storage versions are a useful runtime
  backstop. A version counter attached only to one view handle would miss mutations through
  another alias." This is a runtime mechanism; see the tension noted in section 4.
- **JAX buffer donation.** AI:85: "Compilation can reuse storage when the original value is
  dead. Explicit buffer donation additionally permits reuse across a call boundary while
  forbidding subsequent use of the donated input." This is a precedent for a compile-time
  "consume" of a buffer, which L6 syntax does not yet cover (DEC:53-54).
- **PyTorch functionalization.** AI:103: "Functionalization can remove intermediate
  mutations while preserving observable behavior." This is a precedent for converting
  mutation into functional updates that a static reuse analysis then turns back into
  in-place writes.
- **Mutation permission.** AI:274-276: immutable binding "does not automatically prohibit
  or permit changing referenced storage". The proposed rule is "storage mutation requires
  the approved explicit permission and must preserve AD correctness."
- **Compiler place model.** LF:776-784: every operation keeps "Place identity for memory
  access". "A mutable variable is a storage place. Each write changes its value version."
- **Copy propagation.** LF:905: "A copied reference is not an independent object." This
  lines up with the double-`del` defect in PLAN:104-116.
- **Scalar replacement.** LF:914: needs "No required address identity/escape; preserve
  layout and destruction". It is a data-oriented (DOD) optimization that interacts with
  destruction.
- **Tensor fusion.** LF:918: needs the "AI-owned operation contract, shapes, aliases,
  numerical and allocation behavior". Fusion changes allocation.
- **Futhark precedent.** LF:205: "size-dependent array typing, and fixed-point alias
  reasoning around loops". A7 "should similarly state restrictions where its analysis
  depends on them".

### 2.2 Autodiff tape and saved-tensor lifetime

- **Registry entry.** AI:300-308: each differentiable operator declares "Saved values and
  their lifetimes" and "Mutation restrictions".
- **Tape shape and size.** AI:298: "first-order reverse-mode AD using an execution tape,
  with iterative traversal". AI:310: "Dynamic loop support requires dynamic tape storage
  and defined allocation failure behavior; it cannot imply unlimited memory."
  - **Inference:** tape length depends on executed control flow, so tape size cannot be
    resolved at compile time. Only its allocation and release policy can be.
- **PyTorch saved-tensor checks.** AI:101: "Backward operations retain required forward
  values. Saved tensor version checks detect mutations that invalidate those values."
- **TensorFlow tape release.** AI:121: "A normal gradient call releases tape resources;
  persistent tapes retain them." This is a precedent for two tape lifetimes, one-shot and
  persistent.
- **Acceptance scenarios** (AI:504-505):
  - "Mutation | An alias change cannot silently corrupt a saved backward value"
  - "Tape lifetime | Repeated ordinary backward passes release saved storage"
- **Gradient accumulation.** AI:463: "Weight tying requires gradients from multiple uses to
  accumulate into the same parameter". AI:501-502 covers shared operands and repeated
  gather IDs. Gradient buffers are therefore long-lived and shared across uses.
- **Gradient absence.** AI:316-322: a disconnected input differs from a zero gradient.
  **Inference:** absent gradients may need no storage, which is an optional-buffer
  representation question.
- **Plan dependency.** PLAN:125-126: "Tensor saved-value lifetime depends on this gate"
  (G2).

### 2.3 Checkpoint recomputation

- **Replay requirements.** AI:330: "Activation recomputation can reduce memory, but requires
  replayable regions. Dropout must replay the same mask without incorrectly consuming the
  global RNG twice. Effects such as file reads or parameter mutation should not be silently
  repeated."
- **JAX checkpointing.** AI:91: activation checkpointing "controls saved residuals and
  recomputation".
- **PyTorch checkpointing.** AI:109: activation checkpointing has contracts for "saved
  values, mutation declarations, and RNG replay". AI:123 (TensorFlow): "Recomputation
  reruns forward work during differentiation."
- **Acceptance.** AI:506: "Recomputation | Gradients agree with saved-activation execution,
  including dropout".
- **v1 status.** AI:573: "Decide explicitly | Forward-mode coverage and activation
  recomputation in v1".
- **Inference:** recomputation is a memory-for-compute trade. A compile-time memory
  planner would need an effect system that marks a region as replayable: pure except RNG
  with a captured state. LF:206 (Koka) and LF:584 (separate effect properties) supply the
  IR hook.

### 2.4 Mixed-precision state

- **Precision per component** (AI:216-224):
  - "Authoritative parameters | `f32`"
  - "Forward parameter/activation storage | `f16` or `bf16`"
  - "Gradient accumulation ... | `f32`"
  - "Adam moments ... | `f32`"
  - **Inference:** each parameter can exist in two dtypes at once, an f32 master and an
    f16/bf16 working copy. The memory planner has to own both copies and the conversion
    temporaries.
- **Skipped updates.** AI:240: "A skipped update should leave parameters, moments, weight
  decay, and successful-update counters unchanged." **Inference:** checking before mutating
  implies either a separate check pass or staging buffers. This is a transactional-update
  requirement.
- **Fallback widening.** AI:246: CPUs without native support widen to f32. "Emulation
  overhead and temporary storage must be visible in diagnostics and performance reports."
  HW:47 agrees: "A baseline can store f16/bf16 and compute through explicit f32 conversion,
  but that must be reported as a conversion path."
- **Framework comparisons.** AI:107: PyTorch Adam uses `zeros_like(parameter)`, so AMP does
  not imply separate f32 master weights. AI:117: TensorFlow's mixed-f16 policy retains f32
  variables.
- **MLX.** AI:133: reduced-precision hardware paths exist for nominally f32 ops.
  "specify computation separately from storage".

### 2.5 Optimizer state

- **State ownership.** AI:13: A7 owns "optimizer state, RNG, and checkpoint behavior".
- **Checkpoint contents.** AI:469-479: model parameters, "Optimizer moments and
  successful-update counters", scheduler, loss scaler, RNG, dataset position, precision
  policy, and "Any accumulated gradients if mid-accumulation checkpoints are supported".
  AI:481: "Weights alone are insufficient".
- **Checkpoint load failure.** AI:414: "Corrupt/incompatible checkpoint | Reject before
  replacing live state". **Inference:** loading must allocate new state and swap it in
  atomically, which is a two-copy peak.
- **TensorFlow separation.** AI:115: TensorFlow "separates immutable tensor values from
  mutable variables". AI:564 adopts "explicit tensor/state separation".
  **Inference:** this maps naturally onto DOD: long-lived parameter and optimizer arenas
  versus per-step activation and tape arenas.

### 2.6 Native kernel buffers and DLPack

- **Bridge descriptors** (AI:366-374): "Storage ownership and temporary-memory ownership.
  Shape, stride, and dimension conversion." Also "Status results and synchronous
  completion".
- **ABI limits.** AI:376: "Do not expose C++ templates, exceptions, or framework tensor
  objects in the public A7 ABI." AI:350: oneDNN "blocked layouts and reorders should remain
  private implementation details".
- **Integer widths at the boundary.** AI:344: OpenBLAS LP64 uses 32-bit BLAS integers, so
  `usize` dimensions need checked conversion. AI:378: "Shape products, byte counts, and BLAS
  conversions require checked operations even though ordinary source `+`, `-`, and `*`
  wrap." LF:316 agrees: "Allocation arithmetic | Checked size/capacity operations |
  Ordinary wrapping cannot justify allocation sizes". LF:1117-1127 proposes
  `sizes.checked_multiply`.
- **Native descriptor fields.** LF:1135-1148: "Buffer lengths, alignment, and alias
  permissions. Retention after return. Ownership and destruction of returned storage.
  Blocking and thread affinity. Callback invocation and re-entry."
- **Native pointers.** LF:1150: "A native function that returns a pointer is not
  automatically a non-null, valid, uniquely owned A7 reference."
- **Ownership split.** LF:1154: "The memory report owns allocation and aliasing design. The
  AI report owns tensor/kernel numerical and buffer contracts."
- **DLPack.** HW:222: "DLPack is useful for interchange, but it does not independently
  solve these obligations. Its protocol includes lifetime and stream coordination
  requirements. A7 must also validate shape/stride integer conversions and whether a copy
  occurred."
- **Adapter duties.** HW:214: "Allocate/import/export buffers with explicit ownership and
  lifetime."
- **Threading.** AI:380: "Nested A7 workers, OpenMP, BLAS, and oneDNN pools can
  oversubscribe a CPU". LF:1060 lists "buffer-retention contracts" for native pools.

### 2.7 Device buffers

- **Future GPU interface.** AI:382: should reserve "device capabilities, transfer
  operations, completion events, and backend errors".
- **CUDA.** HW:55: "Discrete allocations, transfers, streams and events require explicit
  ownership."
- **Shared-memory iGPU and Apple unified memory.** HW:58: "Shared physical memory still has
  allocation limits, synchronization and CPU/GPU contention." HW:61: "Unified memory
  requires resource-mode and synchronization discipline."
- **NPUs.**
  - HW:73 (AMD IRON): "Explicit tile placement, local memory, streams and DMA."
  - HW:84: "Shared memory does not prove zero-copy import, coherence, unrestricted CPU
    access during execution, or stable alignment requirements."
- **Memory tiers on accelerators.** These are distinct address spaces and tiers, not one
  heap:
  - HW:90: TPU7x chip "exposes two chiplet devices with distinct memory spaces. Host RAM,
    HBM and VMEM are separate tiers."
  - HW:91: NeuronCore-v4 "software-managed SRAM"
  - HW:93: Cerebras "Distributed on-wafer SRAM ... placement-aware programs"
  - HW:94: SambaNova SRAM + HBM + DDR5
  - HW:95: Graphcore in-processor + streaming memory
  - HW:97: Tenstorrent "local storage, external-memory transfers and tiled layouts"
  - HW:99: FPGA HBM + DDR4
- **Serialization.** HW:293: open decision "Canonical versus device-packed serialization".
- **Cache keys.** HW:224: artifact cache keys include "layout" and "shape specialization".
- **Inference:** a compile-time memory model that assumes one address space will not
  generalize. Placement or device must be part of the storage identity (AI:252 already
  lists "device").

### 2.8 Async execution

- **Hardware reports.**
  - HW:220: "Immutable argument bindings do not eliminate mutation hazards. An asynchronous
    operation may still read an explicitly mutable referent. A7 must prevent conflicting
    mutation and premature destruction until completion. Views and exported tensors require
    the same treatment."
  - HW:216: adapters "Submit operations with dependencies and report completion/errors."
- **AI report.**
  - AI:421: "CPU execution should initially complete synchronously. Future asynchronous
    execution must define where errors become observable, which outputs remain invalid,
    and when checkpoint publication may report success."
  - AI:93 (JAX): "Dispatch may be asynchronous". AI:131 (MLX): "Evaluation boundaries
    affect when work, errors, and memory use become visible."
- **Language report.**
  - LF:807: "Suspension | Account for state another permitted actor can change".
  - LF:1019-1021: runtime options include stackful cooperative tasks ("Stack management")
    and stackless async ("Larger language/IR change").
- **Inference:** static lifetime ends ("free at scope end") are unsound across async
  submission unless the free point is moved to a completion event. Either the language
  keeps v1 synchronous, which the AI report recommends, or lifetimes extend to a join or
  synchronization point.

### 2.9 Concurrency: task and channel ownership

- **Structured lifetime** (LF:986-996): "Every task belongs to a parent scope. Scope
  completion waits for children to finish." Also "Task handles do not silently detach on
  destruction" and "Transferability is checked through the entire reachable value." Channels
  are bounded by default.
  - **Inference:** structured scopes give stack-like, statically nestable lifetimes, which
    are compatible with compile-time resolution. The unstructured spawn at LF:1022 is not.
- **Send commit table** (LF:1000-1008):
  - "Before enqueue/rendezvous commits | Sender owns payload"
  - "Successful send | Receiver/channel owns payload"
  - "Closed/cancelled/failed send before commit | Sender receives unsent payload with
    failure"
  - "Cancellation races after commit | Must not return a second owned copy"
  - "Receiver abandonment | ... queued payload destruction is defined"
- **Drain on close.** LF:1010: "dropping the last sender allows queued messages to drain
  before end-of-stream".
- **Pony isolation.** LF:207: "Moving an outer struct does not by itself establish safe
  cross-task transfer."
- **Stack sizing.** LF:64: "D.053 claims exact task-stack sizing from the recursion ban.
  That claim is not established." LF:715: "Exact stack sizing also does not follow. Backend
  spills, ABI frames, foreign functions, runtime helpers, optimization, and task machinery
  remain relevant."
- **Deadlock.** LF:1012: "Do not claim deadlock freedom from ownership."
- **Dataflow events.** LF:806: "Task transfer | Remove sender ownership only at the defined
  transfer point".
- **Tests.** LF:1316: cancel a blocked receive, abandon a receiver, race cancellation with
  send commit, and "Check message ownership and final outcomes".

### 2.10 Closures and function values

- **Current state.** LF:124: "Closures | No complete capture contract established | Captures,
  escape, layout, invocation multiplicity, and recursion analysis missing".
- **Progression table** (LF:588-601):
  - "Noncapturing function values | Preserve concrete signatures and possible-target sets"
  - "Capturing closures | Add only with capture ownership, lifetime, escape, and invocation
    contracts"
  - "Homogeneous variadics | Consider lowering to slices after lifetime approval"
- **Capture example.** LF:646-652: "whether `offset` is copied, moved, or borrowed; whether
  the closure escapes; and how its calls enter recursion analysis. No capture policy is
  approved here."
- **Futhark.** LF:205: restrictions on higher-order values "to support defunctionalization".
  **Inference:** defunctionalization plus a no-escape rule would let captured environments
  live on the stack or in the caller's arena at no runtime cost.
- **Stored function values.** PLAN:152-158 (G4): stored function values and callback tables
  versus the recursion ban.

### 2.11 Collections and iterator invalidation

- **Stdlib contract.** LF:1071: "Collections | Vector, map, set, queue; capacity/growth
  failures; iterator invalidation".
- **Open questions** (LF:1088-1089): "Whether collection mutation invalidates
  iterators/views" and "Whether allocation failure leaves the original collection
  unchanged".
- **Dataflow.** LF:799: "Slice/container resize | Invalidate dependent length, storage, view,
  and bounds facts". LF:830: "A later call that can resize or replace the underlying view may
  invalidate it."
- **Tests.** LF:1318: "collection growth near size limits, iterator invalidation ...
  allocation failure preserving original state".
- **Current state.** LF:102: "Slices | ... Mutation, lifetime, equality, and ownership depend
  on memory decisions".
- **KV cache.** AI:459: "Optional KV cache | Append/update semantics and cached-versus-full
  equivalence". A growing buffer whose views are in use is the iterator-invalidation problem
  in a tensor setting.

### 2.12 Stdlib owned handles

- **Files.** LF:1069: "Owned handles, explicit open options, close/flush/durability
  distinction".
- **Random.** LF:1075: "Owned seeded generator". LF:1076 (Process): "Handles, cancellation".
- **Fallible cleanup.** LF:1091: "Whether cleanup can fail or suspend."
- **Interpolation.** LF:286 for `f"..."`: "allocation failure, result ownership". "If
  allocation can fail, the illustrated direct `string` result cannot be assumed without an
  allocation policy." LF:87 says the same for interpolation: "formatting and allocation
  behavior unresolved".
- **Zero initialization.** LF:424: "Non-null references, resources, and tagged unions cannot
  become valid merely because their storage was zeroed."
- **Current references.** LF:103: "Nullable `ref T`, `nil`, implicit typed reference passing
  | Non-null/optional split and affine ownership planned".

### 2.13 Defer and cleanup

- **Capture timing.** LF:119: "`defer` | Scope-exit cleanup and LIFO intent | Capture timing,
  mutation, failure, auto-drop, and suspension interactions unresolved".
- **Cleanup order** (LF:547-554), "pending ownership reconciliation":
  1. Evaluate the return expression.
  2. Run defers in reverse order.
  3. "Perform required destruction in the approved relation to explicit defers".
  4. Transfer the return value.
  - "A future automatic destruction pass must not double-delete an explicitly deferred
    resource."
- **Timing example.** LF:540-545: execution-time capture prints `2`, registration-time
  capture prints `1`. "The language must choose."
- **Exactly-once destruction.** LF:563: "cleanup executes once before the caller observes
  completion". LF:1314: "Verify exactly-once destruction and approved ordering. Memory
  specialists own the underlying lifetime model."
- **Matching and moves.** LF:464: "Delay affine payload moves until the selected guard
  succeeds". LF:636: destructuring "needs partial-move behavior".
- **Dataflow events.** LF:805: "Deletion/move | Update ownership and all dependent aliases".
  LF:533: "Cleanup on every exit".
- **Dead-code elimination.** LF:906: "Unused allocation, I/O, task, or native call can
  matter." **Inference:** a compile-time memory system that elides allocations must define
  whether allocation, or allocation failure, is observable.

### 2.14 IR, CFG and effects needed for analysis

- **Pipeline order.** LF:747-753 puts "Effects, initialization, ownership, target sets, and
  value facts" before "Obligation discharge" and "Cleanup and representation lowering". It
  follows with "Revalidation of changed control/data flow".
- **Rust MIR.** LF:721: "basic blocks, explicit places, non-nested operations, and copy/move
  distinctions ... without adopting ... its complete borrow checker."
- **Effect separation.** LF:584: "Reading, writing, retaining, consuming, returning aliases,
  and invoking callbacks are different properties. Internal effect summaries should record
  them separately." This is the direct precursor to compile-time ownership inference.
- **Minimum analysis state.** LF:790: "initialization state, ownership state, numeric facts,
  lengths/shapes, nil state, active variants, alias relations, and call-target/effect
  summaries".
- **Dataflow event table.** LF:792-808 covers mutable call arguments, unknown calls, joins,
  loops needing a fixed point, deletion/move, task transfer, suspension and foreign calls.
- **LLVM MemorySSA.** LF:832: "memory versions and clobber queries ... does not remove the
  need for alias information or correct call effects."
- **Transformation contract.** LF:840-853: lists preserved and invalidated analyses, and
  says proofs must be tied to operands and value versions.
- **Call graph.** LF:694-707: whole admitted-call graph with iterative SCC. **Inference:**
  with source recursion banned, the call graph is a DAG apart from foreign re-entry
  (LF:713). Bottom-up interprocedural ownership summaries therefore terminate without
  fixed points across SCCs, which is a real enabler for L15.
- **Separate compilation.** LF:976: "An interface must include types, ABI-visible layouts,
  generic requirements/body availability, effects, callback targets, ownership/transfer
  properties". Compile-time memory resolution across modules needs ownership summaries in
  interfaces.
- **Analysis budgets.** LF:686: "Use deterministic work budgets for constant evaluation,
  generic expansion, and analysis. Report exhaustion as a compiler capability limit."
  **Inference:** static lifetime inference may time out, and a fallback policy is needed.
- **Plan tracks.** PLAN:201-205: track 4 (typed IR, CFG, effects) comes before track 6
  (memory model).

### 2.15 Gap: the "data-oriented" half of L15 is almost absent

None of the three files recommends layout control as a language feature. There is no
discussion of SoA/AoS, field reordering, alignment or padding control, hot/cold splitting, or
handle/index-based entity storage. The only touchpoints are:

- LF:453: "Normal A7 layout should remain distinct from native ABI layout".
- LF:441: "Do not compare padding bytes".
- LF:681-684: `@size_of(i32)`, whose "result depends on a target layout contract".
- LF:914: scalar replacement "preserve layout and destruction".
- HW:213: adapters describe operations "by storage dtype, compute dtype, accumulator, shape,
  layout, alignment and numerical mode".
- AI:261-270: contiguous row-major tensors and private kernel packing.

**Finding for the brainstorm:** the user said "data oriented design", but the research corpus
gives nothing on DOD layout to react to. That part needs new research or a direct user
statement.

---

## 3. Float recommendations compared with L16

L16 (DEC:48): "Follow Zig and C: IEEE 754 values, so NaN and infinity are ordinary float
values; strict arithmetic by default; optimizations that change results only by explicit
opt-in."

| Research claim | Location | Relation to L16 |
|---|---|---|
| "My floating-point recommendation is IEEE values with strict scalar semantics, plus explicit numerical checks at training boundaries." | AI:25, AI:149 | **Agrees.** The checks are library predicates, compatible with L16 (PLAN:83-85 `is_finite`/`is_nan`/`is_inf`). |
| Special-value table: `1.0/+0.0 = +Inf`, `0.0/0.0 = NaN`, `sqrt(-1.0) = NaN`, `NaN == NaN` false, `+0.0 == -0.0` true, subnormal bits preserved | AI:180-189 | **Agrees** with IEEE. It conflicts with the current nonzero-divisor proof on float division (AI:191; PLAN:74-76 observed exit 6). L16 implies removing that proof for floats, which is still an open sub-decision (PLAN:61). |
| "I recommend no portable promise about NaN payload preservation, and no implicit saturation." | AI:193 | Compatible. Zig and C also do not promise payloads (external knowledge, **inference**). |
| "Do not reassociate, contract multiply-add, or eliminate exceptional intermediates under strict scalar semantics." "Keep fast math separately selectable and separately qualified." | AI:204-206 | **Agrees with Zig strict.** C diverges here, because compilers may contract FMA by default (PLAN:61). L16 names both Zig and C, so FMA remains ambiguous. |
| Zig 0.16 `.optimized` permits reassociation, contraction, and ignoring signed zero and non-finite values. "Release optimization and floating policy must therefore be controlled separately." | AI:208 | **Agrees.** It matches "explicit opt-in" and means ReleaseFast must not imply `.optimized`. |
| "Unconstrained floating literal \| `f32`" | AI:161 | **Divergence (inference).** Zig uses `comptime_float` with contextual typing, and C's unsuffixed literal is `double`. An f32 default matches neither. Undecided sub-item (PLAN:86). |
| "Different typed numeric operands \| Require explicit conversion initially"; alternative lattice f16/bf16 → f32 → f64 | AI:165, 174 | Zig-like (Zig requires explicit casts between float types). C uses the usual arithmetic conversions. |
| Float-to-integer conversion: "Explicit rounding rule plus finite/range validation" | AI:168 | Zig safety-checks `@intFromFloat` out of range, and C makes it UB (**inference**, not in the files). Needs a decision. |
| IEEE versus finite-only table ("Finite-only package") | LF:379-387; AI:141-147 | **Superseded by L16.** |
| "Float behavior \| IEEE versus finite-only remains unapproved \| Do not infer behavior from current SPEC wording or Zig defaults" | LF:47 | **Superseded.** L16 now does infer from Zig and C. |
| "Also decide literal rounding, intermediate precision, subnormal handling, signed zero, NaN payload observability, fused multiply-add, and reproducibility expectations. Scalar policy and tensor policy may differ only through an explicit boundary." | LF:407 | Still-open L16 sub-decisions. "Intermediate precision" concerns the C/x87 `FLT_EVAL_METHOD` question, where C and Zig can differ (**inference**). |
| "Do not enable fast-math merely because a program passed tests or all observed inputs were finite." | LF:409 | Agrees. |
| "Reduction vectorization \| Approved reassociation or order-preserving lowering \| Floating addition is not associative"; "Fast-math/contraction \| Explicit permission or sound per-operation proof" | LF:916, 919 | Agrees. Note that "sound per-operation proof" would also let the compiler contract without opt-in when results are provably unchanged. |
| "Float folding must not silently use Python binary64 as the semantics of an `f32` operation." | LF:893; AI:197-203 | Required for L16's strict default (the folder must round per operation at the target format). |
| "Metamorphic ... Do not apply that identity to floats." | LF:1302 | Consistent. |
| "Tensor reductions and contractions need their own ordering and accuracy rules. Strict scalar arithmetic does not imply that all parallel reductions must produce identical bits." | AI:210 | **Qualifies L16.** Strict applies to scalars. Tensor reductions need their own contract. |
| "does not support a blanket promise that an IEEE storage type implies identical IEEE execution across all tensor backends" | HW:106 | **Qualifies L16 for tensors.** BF16 subnormal flushing (HW:110-111, 115), CUDA FTZ and contraction by compiler flag (HW:112), cuBLAS reduced-precision compute modes (HW:113), Gaudi subnormals as zero (HW:117). |
| "Make TF32, FP8, reduced-precision multiplication, stochastic rounding and flush-to-zero explicit choices"; "Specify whether FMA contraction and reassociation are permitted"; "Never silently narrow f64, substitute TF32/BF16" | HW:128-129, 229 | Agrees with the "explicit opt-in" spirit, extended to kernels. |
| Mixed precision, f16 loss scaling, full-step skip on non-finite gradients | AI:229-244 | Relies on NaN/Inf being ordinary values, so L16 enables it (PLAN:80). |
| Attention: "PyTorch's reference attention uses negative infinity for excluded positions. A7 can instead define semantic masked softmax" | AI:153; AI:465 | Under L16, `-inf` masking is legal. The semantic masked op is still recommended for fully masked rows (0/0 → NaN). |
| "Define reproducibility within a recorded configuration. Cross-version, cross-ISA, cross-thread-count, and cross-device bitwise equality should not be promised." | AI:551 | Compatible. L16 strict does not promise cross-library bit equality for kernels. |

**Memory-relevant float point (inference).** Mixed precision and fallback widening
(AI:246) create conversion temporaries. If fast-math and fusion are opt-in, the default
memory plan cannot assume fused kernels that avoid intermediates, except where a fusion
is provably result-preserving (LF:918).

---

## 4. Claims that conflict with L15, L16 or other locked decisions

Most conflicts come from the reports predating L15 and L16. Items marked "tension" are my
**inference**, not literal contradictions.

1. **Float undecided (conflicts with L16).** LF:47: "IEEE versus finite-only remains
   unapproved | Do not infer behavior from current SPEC wording or Zig defaults". LF:377:
   "The current specification's IEEE labels do not override the explicit instruction that
   IEEE versus finite-only behavior is undecided." Both are superseded by L16.
2. **Finite-only presented as a live option (conflicts with L16).** LF:379-387 has a
   "Finite-only package" column. AI:146 has "Finite-only values | Numerical failure becomes
   an explicit result". AI:574 has "User approval required | IEEE versus finite-only
   behavior". AI:25: "Finite-only behavior is possible". All are superseded.
3. **f32 literal default (tension with L16's "Zig, C").** AI:161: "Unconstrained floating
   literal | `f32`". Zig uses `comptime_float` and C uses `double` (**inference**, external).
4. **Runtime version counters (tension with L15's "resolved compile-time").** AI:294:
   "shared-storage versions are a useful runtime backstop". AI:101 adopts PyTorch "Saved
   tensor version checks". AI:111: "Adopt explicit saved-value lifetimes and mutation
   detection." Runtime mutation detection is not a collector, but it is runtime lifetime
   bookkeeping. L15 would prefer static proof, with a runtime check at most as a debug
   backstop.
5. **Dynamic tape, dynamic shapes, recoverable OOM (tension with "everything is resolved
   compile-time").**
   - AI:310: "Dynamic loop support requires dynamic tape storage".
   - AI:402: "arbitrary input shapes, allocation availability, file contents, and backend
     failures cannot all be proved away at compile time. The v1 plan needs defined runtime
     error values".
   - AI:410: "Recoverable allocation failure | OOM result".
   - **Inference:** this does not contradict L15 if L15 means *lifetimes and free points*
     are compile-time while *sizes* stay runtime. It does contradict a literal reading of
     "everything".
6. **Runtime shape guards (tension, pointing the other way).** HW:232: "Preserve the current
   compile-time proof rule. Runtime guards for dynamic shapes require an approved contract
   extension; this report does not authorize that change." This is consistent with L15 but
   conflicts with AI:407 "Dynamically invalid shape/dtype/index | Structured error before
   invalid kernel execution", which assumes runtime checks. The two reports disagree with
   each other.
7. **Unstructured spawn listed as a runtime option (tension with L15).** LF:1022:
   "Unstructured spawn | Concise use | Shutdown, error observation, and lifetime burden".
   Unscoped task lifetimes cannot be resolved statically without extra machinery.
8. **Async submission (tension with L15 static free points).** HW:220: "A7 must prevent
   conflicting mutation and premature destruction until completion". AI:421: "Future
   asynchronous execution must define ...". Static scope-end frees need a join or
   synchronization point.
9. **Memory report ownership (process conflict).** LF:790: "The memory report owns the
   ownership model". LF:1154: "The memory report owns allocation and aliasing design".
   Those memory reports predate L15, so any ownership recommendation there needs
   re-checking against L15. Not in these files.
10. **Parameter-mode vocabulary (L6 scope, DEC:53-54).** LF:49: "Do not introduce `borrow`,
    `inout`, or `consume` as accepted syntax". LF:584: "Do not model all parameter behavior
    as a simple `borrow < inout < consume` scale". These are consistent, not conflicts. JAX
    donation (AI:85) implies a consume-like concept that would need approved syntax or
    inference.
11. **Stack sizing from the recursion ban.** LF:64: "D.053 claims exact task-stack sizing
    from the recursion ban. That claim is not established." This is not a conflict with a
    locked decision. It is a warning against using "no recursion" as a basis for a claim
    that memory is fully resolved at compile time.
12. **Current SPEC broadcasting example (doc defect, not a locked-decision conflict).**
    AI:47: `[3,1,4] + [2,5,1]` is invalid.
13. **No address-of or deref.** None of the three files proposes a public `&` or `*`. LF:51:
    "Internal IR operations do not justify public syntax". Consistent.
14. **Wrapping versus safety contract.** HW:18, AI:41 and LF:65 note that SAFETY_CONTRACT
    range proofs conflict with L5. They are consistent with the locked decisions and flag
    the doc.
15. **Mixed numeric operands.** LF:304 recommends the same concrete type with contextual
    literals. It is consistent with explicit widths (L4) and still undecided under G3.
16. **Recursion.** Nothing proposes recursion. AI:298 requires "iterative traversal" for the
    tape, which is consistent.

---

## 5. Hard cases and workload requirements a memory design must handle

Each item names its source. "Inference" marks my extrapolation.

1. **Functional update with a live view** (AI:283-292). `y = updated(x, 1, 9)` while
   `alias = view(x)` is alive. Reuse is forbidden. When no alias exists, reuse is expected
   for performance.
2. **Saved activation later mutated through another alias** (AI:504, AI:294). The mutation
   goes through a different view handle of the same storage.
3. **Repeated backward passes** (AI:505). The tape and saved storage must be released each
   step without a collector. There is one-shot versus persistent tape (AI:121).
4. **Data-dependent loops in the forward pass** (AI:310). Tape length is known only at
   runtime, and both branch paths must be supported (AI:503).
5. **Weight tying and shared operands** (AI:463, 501-502). One parameter gradient buffer
   receives writes from several uses. Gather backward accumulates duplicate indices.
6. **Activation recomputation with dropout** (AI:330, 506). Captured RNG state replaces
   saved activations, and effects must not repeat.
7. **Mixed-precision step** (AI:216-244). f32 masters, f16 or bf16 working copies and
   moments. A skipped step leaves all state unchanged, which needs transactional staging
   (inference).
8. **Checkpoint load and continuation** (AI:414, 509). Incompatible checkpoints are rejected
   "before replacing live state". A fresh process at step N+1 must match an uninterrupted
   run. Loading produces unknown-at-compile-time sizes.
9. **KV cache** (AI:459). An appended buffer grows during generation while views into
   earlier positions are read, which is the container-resize invalidation of LF:799.
10. **Controlled OOM** (AI:508): "returns an error without publishing partial results".
    Also "allocation failure leaves the original collection unchanged" (LF:1089).
11. **Reshape that may or may not be a view** (AI:265, AI:51). Result aliasing depends on
    strides.
12. **Kernel packing and private oneDNN layouts** (AI:270, 350). Temporary storage is owned
    by the bridge, not by A7 values.
13. **Native returned storage** (LF:1142-1143, 1150). Retention after return and destruction
    of returned buffers. It is not automatically uniquely owned.
14. **Foreign callback re-entry** (LF:713). It creates call cycles and aliasing that A7
    analysis cannot see.
15. **Async kernel or device submission** (HW:220). A tensor must not be destroyed or
    mutated before completion. Views and exported (DLPack) tensors share the obligation
    (HW:222).
16. **Multiple address spaces and tiers** (HW:55, 58, 61, 90-99). Host versus device, shared
    DRAM with opaque NPU buffers (HW:84), and chiplet-local memory.
17. **Channel payload ownership under cancellation races** (LF:1004-1008). This includes
    queued payload destruction on receiver abandonment.
18. **Structured task scope exit with failing children** (LF:986-996, 1316).
19. **Capturing closures that may escape** (LF:646-652). Stored callbacks create recursion
    risks (PLAN:152-158).
20. **`defer` combined with automatic destruction** (LF:554). No double-free is allowed.
    Execution-time versus registration-time capture (LF:540-545).
21. **The current double-`del` program** (PLAN:104-116). `q := p; del p; del q` compiles
    today.
22. **Guarded match with affine payload** (LF:464). The move happens only after the guard
    succeeds. Destructuring partial moves (LF:636).
23. **Interpolated strings and formatting** (LF:286). Result ownership and allocation
    failure.
24. **Allocation sizing** (LF:316, AI:378, LF:1117-1127). Shape products and byte counts
    must use checked arithmetic even though ordinary `*` wraps.
25. **Threading oversubscription and native pool buffer retention** (AI:380, LF:1060).
26. **Scalar replacement and DCE of allocations** (LF:906, 914). Is an elided allocation
    observable?
27. **Benchmark expectations** (HW:279). Report "distributions and memory peaks, not a
    single throughput number". The memory design will be measured on peak memory.
28. **Untagged unions** (LF:106): "Active-member safety incomplete". LF:455: "An unchecked
    union is not a sufficient implementation of a safe error type". This is related to memory
    safety, and G2 lists "untagged-union access" as a sub-decision (PLAN:124-125).
29. **Analysis budget exhaustion** (LF:686). Needs a defined outcome when lifetime inference
    hits its budget.

---

## 6. Open questions for the user brainstorm

1. **Scope of "compile time" in L15.** Does "everything is resolved compile-time" mean free
   points and ownership are static while sizes stay runtime (tape, shapes, KV cache,
   checkpoints)? Or does it mean sizes must be static too? AI:310 and AI:402 imply that
   sizes cannot always be static.
2. **Mechanism family.** Which is closest to intent?
   - (a) Rust-like affine ownership with inferred moves and drops (PLAN:120 option a)
   - (b) Explicit allocators, arenas and scratch storage (PLAN:122 option c; the Odin/Jai
     temp-allocator style is **inference**)
   - (c) Compile-time reference counting with elision (Lobster/Perceus style, not in these
     files)
   - (d) Region inference
   - a hybrid
3. **Arena tiers per training step.** Should the DOD story be persistent parameter and
   optimizer arenas plus per-step activation and tape arenas freed wholesale? AI:115 and
   AI:564 support tensor/state separation. How do arenas interact with async completion
   (HW:220)?
4. **Runtime safety nets.** Are runtime mutation or version checks acceptable as a Debug
   backstop (AI:294), or must all alias safety be static?
5. **Donation or consume.** L6 forbids unapproved mode syntax (DEC:53). Should buffer reuse
   rely only on inferred last-use? Or does the user want visible consume or donate syntax
   (AI:85)?
6. **Views without address-of.** How are views, slices and storable references expressed
   and tracked, given no public `&` or `*`? Are storable `ref` fields allowed (PLAN:124)?
7. **Tape lifetime policy.** Should the default be one-shot tape release, with persistent
   tapes opt-in (AI:121)? Is recomputation in v1 (AI:573)?
8. **Recoverable OOM or abort.** Should allocation failure be a recoverable result (AI:410,
   LF:1089)? Does L15 imply allocations can be pre-planned so that failure happens only at
   defined points?
9. **Closures.** Should v1 ban escaping captures, so environments stay on the stack or in
   an arena (LF:592-595, Futhark LF:205)? Should function values be storable (G4)?
10. **`defer` and auto-destruction.** Which runs first? Is capture execution-time or
    registration-time (LF:540-554)? Should `del` stay a public operation once destruction
    is automatic?
11. **Concurrency.** Confirm structured scopes only, with no detached spawn (LF:986-996
    versus LF:1022). Does transferring across tasks require a statically proven unique
    reachable graph (LF:993, LF:207)?
12. **Device memory.** Should storage identity carry device or placement from day one
    (AI:252, HW:90)? Or is the memory model CPU-only until an accelerator gate?
13. **Native bridge ownership.** Who frees kernel temporaries and native-returned buffers,
    and how is that expressed in compiler-trusted descriptors (LF:1135-1150, AI:366-374)?
14. **Collections.** Should mutation invalidate iterators and views as a compile error (a
    static borrow-like rule) or as documented unspecified behavior (LF:1088)?
15. **Separate compilation.** Should ownership summaries be part of module interfaces now
    (LF:976)?
16. **Analysis limits.** If lifetime inference exceeds its budget, should compilation reject
    the program or fall back to an explicit annotation (LF:686)?
17. **Float follow-ups for L16.**
    - FMA contraction default (Zig strict forbids it, C may fuse; PLAN:61)
    - literal default (f32 per AI:161, or Zig `comptime_float`/C `double`)
    - float division-by-zero proof removal
    - whether an opt-in fast mode exists in v1
    - tensor reduction ordering and BF16 subnormal flushing (HW:106-115) as an explicit
      tensor-level relaxation of strict IEEE

---

## 7. External references worth following up

From the files:

- Zig 0.16.0 reference: wrapping operations and `@setFloatMode` (LF:201, LF:296, AI:208).
  https://ziglang.org/documentation/0.16.0/
- Odin overview: parametric polymorphism, packages, foreign system (LF:201, 688, 972, 1152).
  https://odin-lang.org/docs/overview/
- Rust MIR guide and source: places, move/copy, indexed identities (LF:721).
  https://rustc-dev-guide.rust-lang.org/mir/index.html
- LLVM MemorySSA: memory versions and clobbers (LF:832). https://llvm.org/docs/MemorySSA.html
- Futhark language reference: higher-order restrictions, size types, alias analysis
  (LF:205). https://futhark.readthedocs.io/en/stable/language-reference.html
- Koka row-polymorphic effect types (LF:206).
  https://www.microsoft.com/en-us/research/publication/koka-programming-with-row-polymorphic-effect-types/
- Pony reference capabilities: transitive isolation for task transfer (LF:207).
  https://tutorial.ponylang.io/reference-capabilities/reference-capabilities.html
- Rust scoped threads and Swift structured concurrency (LF:998).
- JAX buffer donation (AI:85). https://docs.jax.dev/en/latest/buffer_donation.html
- JAX gradient checkpointing (AI:91).
  https://docs.jax.dev/en/latest/gradient-checkpointing.html
- PyTorch autograd mechanics: saved tensors, version counters (AI:101).
  https://docs.pytorch.org/docs/2.14/notes/autograd.html
- PyTorch tensor views and functionalization (AI:103).
  https://docs.pytorch.org/docs/2.14/tensor_view.html and
  https://docs.pytorch.org/docs/2.14/generated/torch.func.functionalize.html
- PyTorch activation checkpointing (AI:109).
  https://docs.pytorch.org/docs/2.14/checkpoint.html
- TensorFlow GradientTape persistence (AI:121). https://www.tensorflow.org/guide/autodiff
- MLX lazy evaluation: when memory use becomes visible (AI:131).
  https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html
- NumPy copies versus views (AI:272). https://numpy.org/doc/stable/user/basics.copies.html
- tinygrad architecture: scheduling and lowering layers (AI:135).
  https://docs.tinygrad.org/developer/developer/
- oneDNN memory formats (AI:350).
  https://uxlfoundation.github.io/oneDNN/dev_guide_understanding_memory_formats.html
- DLPack Python spec: lifetime and stream coordination (HW:222).
  https://dmlc.github.io/dlpack/latest/python_spec.html
- TPU7x architecture: chiplet memory spaces (HW:90).
  https://docs.cloud.google.com/tpu/docs/tpu7x
- Neuron runtime C interface (HW:91).
  https://awsdocs-neuron.readthedocs-hosted.com/en/latest/neuron-runtime/guides/nrt-developer-guide.html
- CUDA floating-point rules (HW:112).
  https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/mathematical-functions.html
- Intel SDM BF16 semantics (HW:110), TPU BF16 (HW:115).

Not in the files (**inference**, suggested for the L15 brainstorm and still to be verified):

- Lobster's compile-time reference-count elision and ownership inference
- Koka's Perceus: reuse analysis and "functional but in-place". This bears directly on the
  AI:292 buffer-reuse rule.
- Mojo's ASAP destruction and origins
- Vale's generational references and regions
- MLKit and Tofte-Talpin region inference, and Cyclone regions
- Futhark uniqueness types for in-place updates
- Rust non-lexical lifetimes and Polonius
- Zig's `std.mem.Allocator` and arena allocators
- Odin's `context.allocator` and `context.temp_allocator`
- Jai's temporary storage
- Static memory planning in ML compilers: XLA and TVM memory planners, and PyTorch
  `torch.compile` activation memory planning
