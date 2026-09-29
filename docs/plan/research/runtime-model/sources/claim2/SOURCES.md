<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim2/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 2 — primary sources

Claim under audit: "Unified heterogeneous compute pipeline (CPU, GPU, NPU) ... declarative task
graphs where CPU logic, GPU compute shaders, and NPU tensor inferences coordinate through explicit
dependency fences and shared event timelines. Stepping backward or scrubbing the simulation
timeline automatically unwinds and resynchronizes GPU command streams and NPU inference pipelines
to the matching logical frame."

All files below were fetched with `curl -sL` or `curl -skL` into this directory; the three
exceptions (GitHub API/code search, and one file renamed from .html to .h) are marked on their
entries. Every quote was checked against the saved file with `verify.py` in this directory.
verify.py stands in for the literal `tr -s '[:space:]' ' ' | grep -o -F` check because on HTML that
command fails on any sentence spanning an inline tag (`<code>`, `<a>`) or containing an entity;
verify.py strips script/style, tags and entities, collapses whitespace, then does the same exact
substring match. For the .h, .cpp, .txt and .json files the two checks are equivalent. Quotes that
failed the check are not used. Date read: 2026-09-18.

---

## PART A — task graphs, fences, shared timelines

### Khronos blog: Vulkan Timeline Semaphores
https://www.khronos.org/blog/vulkan-timeline-semaphores / Saved: khronos-timeline-blog.html / Read: 2026-09-18 / Kind: vendor claim (Khronos/NVIDIA, Vulkan WG)
Quote (grep-verified): "VkSemaphore allowed applications to synchronize operations across device queues."
Quotes (list items from one bulleted list, each verified individually): "Are a synchronization primitive whose state consists of a monotonically increasing 64-bit integer value" / "Enable omnidirectional synchronization between device and host using a single primitive" / "Allow wait-before-signal submission order"
Quote (grep-verified): "Most Vulkan queue operations can now accept either binary or timeline semaphores, though the window system integration APIs are currently a notable exception."
Note: Establishes a real monotonic-counter timeline shared between device queues and host. Scope
is one Vulkan device/instance (plus external-handle export). Says nothing about NPUs.

### D3D12 ID3D12Fence
https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nn-d3d12-id3d12fence / Saved: d3d12-fence.html / Read: 2026-09-18 / Kind: spec (vendor API reference)
Quote (grep-verified): "Represents a fence, an object used for synchronization of the CPU and one or more GPUs."
Note: Fence is CPU<->GPU and cross-GPU. Interface itself is only monotonic value + completion
event; it carries no notion of "rewind".

### D3D12 ID3D12CommandQueue::Wait
https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12commandqueue-wait / Saved: d3d12-queue-wait.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "Queues a GPU-side wait, and returns immediately. A GPU-side wait is where the GPU waits until the specified fence reaches or exceeds the specified value."
Note: This is the cross-queue dependency primitive: one queue waits on another queue's fence
without a host round trip. Only "reaches or exceeds" — monotonic forward, no decrement.

### D3D12_FENCE_FLAGS
https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ne-d3d12-d3d12_fence_flags / Saved: d3d12-fence-flags.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "D3D12_FENCE_FLAG_SHARED_CROSS_ADAPTER Value: 0x2 The fence is shared with another GPU adapter."
Quote (grep-verified): "Non-monitored fences should only be used when the adapter doesn't support monitored fences, or when a fence is shared with an adapter that doesn't support monitored fences."
Note: Cross-adapter fence sharing exists and is opt-in. Doc says "another GPU adapter"; it does
not say anything about NPU adapters, and I found no Microsoft doc stating an NPU adapter supports
cross-adapter fence sharing. The second quote shows a degraded fence type exists for adapters that
cannot do monitored fences; I did not check what that degradation costs (unchecked).

### CUDA Programming Guide — CUDA Graphs
https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html / Saved: cuda-graphs.html / Read: 2026-09-18 / Kind: spec (vendor programming guide)
Quote (grep-verified): "A graph is a series of operations such as kernel launches, data movement, etc., connected by dependencies. A graph is defined separately from its execution."
Quote (grep-verified): "A graph node can be one of:" followed by a bulleted list whose items were verified individually, including "CPU function call", "signalling an external semaphore" and "waiting on an external semaphore"
Note: A declarative dependency DAG, defined once and launched repeatedly, with CPU-function nodes
and external-semaphore signal/wait nodes as first-class node types. This is the strongest single
source for "declarative task graph spanning CPU and GPU work". Nothing here is NPU.

### CUDA Programming Guide — external resource interoperability
https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/graphics-interop.html / Saved: cuda-graphics-interop.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "Synchronization objects can be imported into CUDA using cudaImportExternalSemaphore() . An imported synchronization object can then be signaled using cudaSignalExternalSemaphoresAsync() and waited on using cudaWaitExternalSemaphoresAsync() ."
Note: A Vulkan timeline semaphore or a D3D12 fence can be imported into CUDA and waited/signalled
on CUDA streams (the page shows `cudaExternalSemaphoreHandleTypeD3D12Fence` and Vulkan FD/Win32
import code). This is a genuine shared timeline across two GPU APIs on the same GPU.

### Unreal Engine — Render Dependency Graph
https://dev.epicgames.com/documentation/en-us/unreal-engine/render-dependency-graph-in-unreal-engine / Saved: unreal-rdg.html / Read: 2026-09-18 / Kind: project doc (shipped engine)
Quote (grep-verified): "The Render Dependency Graph , also called Render Graph or RDG , is an immediate-mode application programming interface (API) which records render commands into a graph data structure to be compiled and executed."
Quote (grep-verified): "traverses the graph to optimize memory usage and parallelize render passes on the CPU and GPU"
Note: Shipped-engine evidence that "declarative task graph" for rendering is ordinary practice. It
is a per-frame record/compile/execute graph, not a persistent scrubbable timeline.

### Frostbite — FrameGraph (GDC 2017 talk page)
https://web.archive.org/web/20190329224900/https://www.ea.com/frostbite/news/framegraph-extensible-rendering-architecture-in-frostbite/ / Saved: frostbite-post.html / Read: 2026-09-18 / Kind: vendor claim (talk abstract)
Quote (grep-verified): "Yuriy describes our new rendering abstraction design, which is based on a graph of all render passes and resources."
Note: Only the abstract is quotable; the slides are on GDC Vault/SlideShare, which I did not fetch.
Establishes provenance of the frame-graph pattern, not its details.

### Level Zero Specification — Core Programming Guide (fences)
https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/PROG.html / Saved: l0-prog.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "A fence can only be signaled from a device’s command queue (e.g. between execution of command lists) and can only be waited upon from the host."
Note: In Level Zero — the API Intel NPUs are programmed through — the fence is a device-to-host
primitive only. Cross-device waiting requires events or the external-semaphore extension.

### Level Zero Specification — External Semaphore extension
https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/api/extensions/external_semaphore.html / Saved: l0-external-semaphore.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "ze_external_semaphore_win32_ext_desc_t"
Note: The extension exists in the Level Zero spec (import of Win32/FD semaphore handles), so the
spec-level path for a shared GPU/NPU timeline is defined. Whether any NPU driver implements it is
the next source.

### Intel Linux NPU driver — Level Zero entry points
https://github.com/intel/linux-npu-driver/raw/main/umd/level_zero_driver/api/ze_device.cpp and .../ze_cmdlist.cpp / Saved: npu-ze_device.cpp, npu-ze_cmdlist.cpp / Read: 2026-09-18 / Kind: project doc (shipping driver source)
Quote (grep-verified, ze_device.cpp): ".pfnImportExternalSemaphoreExt = nullptr,"
Quote (grep-verified, ze_device.cpp): ".pfnReleaseExternalSemaphoreExt = nullptr,"
Quote (grep-verified, ze_cmdlist.cpp): ".pfnAppendSignalExternalSemaphoreExt = nullptr,"
Quote (grep-verified, ze_cmdlist.cpp): ".pfnAppendWaitExternalSemaphoreExt = nullptr,"
Note: Load-bearing negative. Intel's shipping NPU user-mode driver leaves every Level Zero
external-semaphore entry point unimplemented (null in the dispatch table). On Linux/Level Zero an
Intel NPU therefore cannot import a Vulkan/D3D12 semaphore, and cannot signal or wait one from a
command list. GPU and NPU remain separate submission domains synchronized through the host.
(Supporting: npu-driver-readme.html — "Intel® NPU device is an AI inference accelerator integrated with Intel client CPUs".)

Second file, same driver: umd/level_zero_driver/source/driver_handle.cpp (saved as
npu-driver_handle.cpp). Its `getSupportedExtensions()` (quote grep-verified:
"std::vector<ze_driver_extension_properties_t> DriverHandle::getSupportedExtensions() {") appends
only graph, profiling, mutable-command-list, NPU command-queue/context/driver, DDI-handles and
"appendExtension(ZE_EXTERNAL_MEMORY_MAPPING_EXT_NAME," — no external-semaphore extension is
reported. And IPC is memory-only: "pIPCProperties->flags = ZE_IPC_PROPERTY_FLAG_MEMORY;"
(grep-verified). Sharing between an Intel GPU and an Intel NPU is therefore limited to memory; no
event or semaphore crosses the two drivers. Inference, marked as such: that the GPU and the NPU are
separate Level Zero driver instances follows from their being separate user-mode drivers in
separate repositories (intel/linux-npu-driver vs intel/compute-runtime); I did not fetch a spec
sentence stating that Level Zero events cannot cross driver instances.

### DXCore adapter attribute GUIDs (how Windows exposes an NPU)
https://learn.microsoft.com/en-us/windows/win32/dxcore/dxcore-adapter-attribute-guids / Saved: dxcore-attribute-guids.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "DXCORE_ADAPTER_ATTRIBUTE_D3D12_GENERIC_ML . A driver reports this attribute as a GUID in their INF if the device supports DirectX meta-commands required for ML workloads."
Quote (grep-verified): "DXCORE_ADAPTER_ATTRIBUTE_D3D12_CORE_COMPUTE . Specifies an adapter that supports being used with the Direct3D 12 Core compute APIs."
Note: Microsoft's own doc for the attributes the DirectML NPU sample selects on. An NPU on Windows
is enumerated as a D3D12 adapter, which is why it gets D3D12 queues and fences at all. The doc
describes adapter capability, not any GPU<->NPU synchronization guarantee.

### Microsoft DirectML — NPU inference sample
https://github.com/microsoft/DirectML/raw/master/Samples/DirectMLNpuInference/main.cpp / Saved: directml-npu-sample.cpp / Read: 2026-09-18 / Kind: project doc (vendor sample code)
Quote (grep-verified): "// Create the DXCore Adapter, for the purposes of selecting NPU we look for (!GRAPHICS && (GENERIC_ML || CORE_COMPUTE))"
Quote (grep-verified): "queueDesc.Type = D3D12_COMMAND_LIST_TYPE_COMPUTE;"
Quote (grep-verified): "THROW_IF_FAILED(fence->SetEventOnCompletion(1, fenceEvent.get()));"
Note: The closest thing to the claim that exists. On Windows an NPU is a D3D12 adapter with a
D3D12 compute queue and an ID3D12Fence — so NPU work *is* fence-synchronized in the same object
model as GPU work. Two qualifications, both visible in the same file: the adapter is selected
explicitly as non-graphics (a separate adapter from the GPU), and the sample synchronizes on the
host (`SetEventOnCompletion`), not by a GPU queue waiting on the NPU's fence. Cross-adapter
GPU<->NPU queue waits would require a shared cross-adapter fence; I found no Microsoft document
saying NPU adapters support that.

### ONNX Runtime C API — interop (external memory and semaphores)
https://github.com/microsoft/onnxruntime/raw/main/include/onnxruntime/core/session/onnxruntime_c_api.h / Saved: onnxruntime_c_api.h / Read: 2026-09-18 / Kind: spec (public header)
Quote (grep-verified): "External memory handle type for importing GPU/NPU resources."
Quote (grep-verified): "External semaphore type for GPU synchronization."
Quote (grep-verified): "ORT_EXTERNAL_SEMAPHORE_D3D12_FENCE = 0,"
Quote (grep-verified): "ORT_EXTERNAL_SEMAPHORE_VK_TIMELINE_SEMAPHORE_OPAQUE_FD = 2,"
Quote (grep-verified): "This API enables importing external GPU resources (memory and semaphores) for zero-copy sharing"
Quote (grep-verified): "Inserts a wait operation into the EP's stream that blocks until the semaphore"
Quote (grep-verified): "Inserts a signal operation into the EP's stream that sets the semaphore"
Quote (grep-verified): "This is an optional EP capability. If the EP does not support external resource import,"
Quote (grep-verified): "Callback function for RunAsync"
Note: ONNX Runtime does define exactly the interop the claim needs — import a D3D12 fence or a
Vulkan timeline semaphore and wait/signal it on the execution provider's stream. But it is
explicitly optional per execution provider, and the generic async path is a host callback
(`RunAsync`). Note the asymmetry the header's own authors wrote: memory import is documented for
"GPU/NPU resources"; semaphore import is documented "for GPU synchronization". See next source for
who implements it.

### ONNX Runtime — which execution providers implement the importer
`gh search code --repo microsoft/onnxruntime "ExternalResourceImporter"` (GitHub code search, not curl) / Saved: ort-interop-ep-search.txt / Read: 2026-09-18 / Kind: project doc (code search result)
Result (verbatim paths): onnxruntime/core/session/interop_api.{h,cc}; include/.../onnxruntime_ep_c_api.h;
core/session/plugin_ep/*; onnxruntime/core/providers/nv_tensorrt_rtx/nv_provider_factory.cc;
onnxruntime/test/autoep/library/example_plugin_ep/*; onnxruntime/test/providers/nv_tensorrt_rtx/*
Note: The only non-test execution provider implementing external-resource/semaphore import is
`nv_tensorrt_rtx` — an NVIDIA GPU provider. No QNN (Qualcomm NPU), OpenVINO/Intel-NPU, or
DirectML provider implements it. So in practice the fence-import path is GPU-only today.
Method caveat: this is GitHub code search over the default branch, not a curl of a doc page, and
it cannot see out-of-tree EP plugins (Qualcomm ships an ORT QNN EP plugin of its own). Inference,
marked as such: since the complete QNN API index contains no fence or semaphore type at all (see
the Qualcomm entries), a QNN-based EP would have no primitive to implement `WaitSemaphore`/
`SignalSemaphore` against.

### Qualcomm AI Engine Direct (QNN) — QnnGraph_executeAsync
https://docs.qualcomm.com/doc/80-63442-50/topic/function_QnnGraph_8h_1a690b74571029dd9f36e38cd902c86784.html / Saved: qnn-executeAsync.html / Read: 2026-09-18 / Kind: spec (vendor API reference)
Quote (grep-verified): "Asynchronously execute a finalized graph. Graphs will be enqueued for execution in FIFO order."
Quote (grep-verified): "**signalHandle** – **[in]** Signal object which may be used to control the execution of this call."
Quote (grep-verified): "**notifyFn** – **[in]** Pointer to notification function, called when execution is finished."
Quote (grep-verified): "*notifyFn* will be called in context of backend owned thread, with priority equal or lower than client’s calling thread."
Note: The docs.qualcomm.com `/bundle/publicresource/` URLs are JavaScript shells (see below), but
the `/doc/80-63442-50/topic/` path serves readable text. This is the async NPU execution entry
point on Qualcomm hardware: work is enqueued on a QNN-internal FIFO, and completion is reported by
a host callback on a backend thread. There is no fence out-parameter and no way for a GPU queue to
wait on it.

### Qualcomm AI Engine Direct — what Qnn_Signal actually is
https://docs.qualcomm.com/doc/80-63442-50/topic/enum_QnnSignal_8h_1a3202811a83bc067cb56e9b15c78a3e7c.html / Saved: qnn-signal-configoption.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "QNN\_SIGNAL\_CONFIG\_OPTION\_ABORT = 1 - Sets abort on API calls invoked with a signal object."
Quote (grep-verified): "QNN\_SIGNAL\_CONFIG\_OPTION\_TIMEOUT = 2 - Sets timeout interval on API calls invoked with a signal object."
Note: Forecloses the obvious misreading. `Qnn_SignalHandle_t` is a cancellation/timeout control
object, not a synchronization primitive — the only config options are abort and timeout.

### Qualcomm AI Engine Direct — full API index (negative search)
https://docs.qualcomm.com/doc/80-63442-50/topic/unabridged_api.html / Saved: qnn-unabridged_api.html / Read: 2026-09-18 / Kind: spec (complete symbol index)
Result: the complete QNN API index (342 KB, every header, struct, enum, function and typedef)
contains 0 occurrences of "Fence", 0 of "fence", and 0 case-insensitive matches for "semaphore".
Note: A negative from a complete symbol index, not from a failed search. Qualcomm's NPU API surface
has no fence or semaphore type at all, so there is nothing for a GPU timeline to interoperate with.

### Qualcomm docs — `/bundle/publicresource/` URL form
https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-50/function_QnnGraph_8h_1a3ea05f42a9295f9a74a2e3a0cdd64228.html and .../gpu_qnnmem_api_tutorial.html / Saved: qnn-graph-execute.html, qnn-gpu-mem.html / Read: 2026-09-18 / Kind: —
Not readable — no quote. Both return an identical 51,988-byte JavaScript shell. Recorded so the
failure is not mistaken for a finding; the `/doc/.../topic/` URLs above carry the same content in
readable form. I did not obtain readable text for the QNN GPU-backend QnnMem tutorial, so I cannot
say from primary sources what the GPU backend shares beyond memory.

### Apple — MPSGraph executable execution descriptor (MTLSharedEvent wait/signal)
https://developer.apple.com/tutorials/data/documentation/metalperformanceshadersgraph/mpsgraphexecutableexecutiondescriptor/wait(for:value:).json and .../signal(_:atexecutionevent:value:).json / Saved: apple-mpsgraph-wait.json, apple-mpsgraph-signal.json / Read: 2026-09-18 / Kind: spec (Apple documentation data endpoint)
Quote (grep-verified, wait): "Waits on these shared events before scheduling execution on the HW."
Quote (grep-verified, signal): "Signals these shared events at execution stage and immediately proceeds."
Note: The declaration in the same files takes `MTLSharedEvent` plus a `UInt64` value — a Metal
shared-event timeline that an inference graph can wait on and signal. But MPSGraph is a Metal
framework: `MPSGraphDevice` is documented as "A class that describes the compute device." and its
initializers are `MPSGraphDevice/init(MTLDevice:)` (verified in apple-mpsgraphdevice.json), so this
is GPU-side scheduling, not an Apple Neural Engine submission. I found no Apple API that gives ANE
inference the same treatment.

### Apple CoreML MLComputeUnits
https://developer.apple.com/tutorials/data/documentation/coreml/mlcomputeunits.json / Saved: apple-mlcomputeunits.json (the .html URL returns a JavaScript shell) / Read: 2026-09-18 / Kind: spec (Apple documentation data endpoint)
Quote (grep-verified): "The set of processing-unit configurations the model can use to make predictions."
Quote (grep-verified): "to allow the OS to select the best processing unit to use (including the neural engine, if available)."
Note: The entire public control surface over ANE use is an enum choosing which processing units the
OS *may* pick. There is no queue, no fence, no event. Supporting but weaker: the CoreML framework
landing page's topic listing (apple-coreml-index.json, fetched by me) contains zero occurrences of
`MTLSharedEvent`, `MTLCommandBuffer` or `MTLFence`. That is a landing page, not the full symbol
graph, so treat "Apple exposes no ANE/GPU event interop" as strongly indicated but not proven.

### GLM-5.3-flash secondary lookup (NPU fence interop)
tmp/glm/claim2-npu-fences.md and tmp/glm/claim2-qnn-ane.md (relaunch) / Read: 2026-09-18 / Kind: secondary (LLM lookup)
Note: Delegated per coordinator instruction because the docs.qualcomm.com `/bundle/` and
developer.apple.com HTML pages are JavaScript shells. BOTH RUNS FAILED. Run 1 ended
"attempt=1 rc=1 FAILED provider-limit" (its search tool returned "Weekly/Monthly Limit Exhausted");
run 2 ended "Error: Rate limit reached for requests". Neither produced the required
"claims checked: N" line, and neither produced an answer. NOTHING from GLM is used as evidence
anywhere in this file. What the run logs did contribute was discovery only: they surfaced the
readable docs.qualcomm.com `/doc/80-63442-50/topic/` URL form and the Apple documentation-data
endpoints, both of which I then fetched and quoted myself with curl (see the Qualcomm and Apple
entries above).

---

## PART B — "unwinds and resynchronizes GPU command streams"

### D3D12 — Managing Graphics Pipeline State
https://learn.microsoft.com/en-us/windows/win32/direct3d12/managing-graphics-pipeline-state-in-direct3d-12 / Saved: d3d12-pipeline-state.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "there are a wide range of hardware settings that determine how the input data is interpreted and rendered. Collectively, these settings are called the graphics pipeline state"
Note: Establishes that a GPU context carries substantial bound state (rasterizer/blend/depth-
stencil and the rest of the PSO), on top of resource contents and queue state. Any "rewind" has to
reconstruct all of it; the API offers no operation that does so.

### RenderDoc — How RenderDoc works
https://renderdoc.org/docs/behind_scenes/how_works.html / Saved: renderdoc-how-works.html / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified): "When the capture button is hit the driver will enter active capturing upon the beginning of the next frame. In this state every API call is serialised out in order and any initial contents and states are saved."
Quote (grep-verified): "When replaying, the initial section of the capture (up to the beginning of the frame) is read and executed verbatim."
Quote (grep-verified): "The basic building block is replaying a partial frame."
Quote (grep-verified): "When replaying from the beginning of a frame (and not a partial subset of the frame) the initial states of all resources are applied, and the initial pipeline state is restored."
Note: This is the actual mechanism behind every "scrub the frame" GPU tool: serialize the API call
stream plus initial resource contents, then re-execute from the start of the frame up to the
chosen event on a replay device. The same page states that resources without a serialized initial
state have one saved before the first replay: "Resources which did not have a serialised initial
state (e.g. gbuffer textures) have an initial state saved before the first replay of the frame, and
this is restored. That way you don’t get effects ‘leaking’ from later in a frame into an earlier
point." (verified in the same file) Going backwards is implemented by restoring a snapshot and
re-running forward, never by undoing executed commands. It also notes replay is slow: "Care is
taken to minimise this as much as possible as this tends to be the slowest operation given the
overheads of serialisation and decoding the command stream." (verified in the same file)

### PIX on Windows — GPU Captures
https://devblogs.microsoft.com/pix/gpu-captures/ / Saved: pix-docs.html / Read: 2026-09-18 / Kind: vendor claim / project doc
Quote (grep-verified): "A PIX GPU capture records all the Direct3D 12 API calls made by the game, including their parameter data. These calls can later be replayed, which enables a range of debugging and analysis features."
Quote (grep-verified): "We can only guarantee playback will succeed when the GPU and driver are exactly the same"
Note: Same model as RenderDoc — record the D3D12 call stream, replay it later. Not a rewind of a
live context. The second quote records how fragile replay fidelity is: a driver upgrade can break
a capture.

### NVIDIA cuda-checkpoint — README
https://raw.githubusercontent.com/NVIDIA/cuda-checkpoint/main/README.md / Saved: cuda-checkpoint-readme.html (raw Markdown) / Read: 2026-09-18 / Kind: project doc (vendor)
Quote (grep-verified): "checkpoints and restores the CUDA state of a single Linux process"
Quote (grep-verified): "already-submitted CUDA work, including stream callbacks, are completed"
Quote (grep-verified): "device memory is copied to the host, into allocations managed by the CUDA driver"
Quote (grep-verified): "waits for already-submitted CUDA work to finish before completing a checkpoint"
Quote (grep-verified): "does not support UVM memory or IPC memory created with"
Note: The closest real mechanism to the claim, and it is a process-level snapshot, not a rewind.
Granularity: whole Linux process, CUDA state only. It quiesces by *draining* in-flight work to
completion (not cancelling it), copies all device memory to host, releases GPU resources, and on
resume copies memory back and restores streams/contexts — always moving forward from a saved
state. The README's own limitations list excludes UVM and exported IPC memory, and says the
utility "does not attempt to keep the process in a good state if an error ... is encountered
during checkpoint or restore" (verified in the same file).

### NVIDIA cuda-checkpoint issue #20 — graphics workloads
https://github.com/NVIDIA/cuda-checkpoint/issues/20 (fetched with `gh api`, not curl) / Saved: cuda-checkpoint-issue20.txt / Read: 2026-09-18 / Kind: project doc (maintainer statement)
Quote (grep-verified, from the saved file): "jesus-ramos: No plans for that at the moment."
Context in the same file, question asked: "IIUC `cuda-checkpoint` tool is only meant for CUDA binaries. Are there plans to extend this checkpiont/restore capability to graphics workloads, like Vulkan binaries?" and a later maintainer reply "sgurfinkel: No change so far, unfortunately!"
Note: Decisive for the graphics half of Part B — NVIDIA's own checkpoint/restore does not cover
graphics (Vulkan/D3D) workloads at all, and there are no plans to. "Unwinding GPU command streams"
for a renderer has no vendor mechanism behind it.

### CRUM (Garg, Mohan, Sullivan, Cooperman; Cluster 2018 / arXiv:1808.00117)
https://arxiv.org/pdf/1808.00117 / Saved: crum.pdf, crum-flow.txt (pdftotext) / Read: 2026-09-18 / Kind: measured result
Quote (grep-verified against crum-flow.txt): "The runtime overhead of using CRUM is 6% on average, and the time for forked checkpointing is seen to be a factor of up to 40 times less than traditional, synchronous checkpointing."
Note: Measured cost of transparent CUDA checkpoint/restart with UVM: ~6% steady-state runtime
overhead, plus the checkpoint itself. Compute only; no graphics, no NPU.

### CRAC (Jain, Cooperman; SC20)
https://www.ccs.neu.edu/home/gene/papers/sc20.pdf / Saved: crac.pdf, crac-flow.txt (pdftotext) / Read: 2026-09-18 / Kind: measured result
Quote (grep-verified against crac-flow.txt): "low runtime overhead (approximately 1% or less); fast checkpoint-restart; support for scalable CUDA streams"
Note: Best published overhead figure for CUDA checkpoint/restart, ~1%. Again compute-only, process
granularity, and a snapshot-and-resume model rather than a rewind.

### NVIDIA Technical Blog — Checkpointing CUDA Applications with CRIU
https://developer.nvidia.com/blog/checkpointing-cuda-applications-with-criu/ / Saved: nvidia-criu-blog.html / Read: 2026-09-18 / Kind: vendor claim
Quote (grep-verified, article body): "In contrast, NVIDIA GPUs provide functionality beyond that of a standard Linux kernel, so CRIU is not able to manage them."
Note: Generic process checkpoint/restore cannot touch GPU state at all without vendor driver
support; that support is what cuda-checkpoint adds, for CUDA only. Caution: this page opens with a
banner-labelled "AI-Generated Summary"; the quote above is from the article body, not the summary.

### CRIU CUDA wiki page
https://criu.org/CUDA / Saved: criu-cuda.html / Read: 2026-09-18 / Kind: —
Not readable — no quote. The page exists but is empty: "There is currently no text in this page."
(verified in the saved file). The CRIU side is covered by the two NVIDIA sources above, which
include a worked `criu dump` / `criu restore` example.


---

## Fetched but not cited

These were saved in this directory and read, but no quote from them is used. Listed so an auditor
can confirm nothing contradicting was skipped: vk-synchronization.html (the whole 3.9 MB
vkspec.html; the fragment URL was ignored), vk-timeline-ext.html, vk-semaphore-spec.html,
d3d12-fence-based.html (ring-buffer sample), d3d12-multiadapter.html, d3d12-shared-heaps.html,
d3d12-generic-ml.html (D3D12_COMMAND_LIST_TYPE reference), renderdoc-capturing.html,
renderdoc-index.html, cuda-prog-guide.html (TOC only), ort-ep.html, onnxruntime-qnn.html,
qnn-api.html (1.4 KB stub), qnn-api-rst_file_include_QNN_QnnGraph_h.html, kayru-pubs.html,
frostbite-framegraph.html (404), apple-mlcomputeunits-json.html, apple-coreml-index.json (cited
only as a negative count), npu-ze_device.cpp/npu-ze_cmdlist.cpp beyond the quoted lines,
crum.txt / crac.txt (the -layout pdftotext variants; quotes came from the reflowed *-flow.txt).
Helper scripts: ctx.py, verify.py, verify2-9.py, quotes*.json.
