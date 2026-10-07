# P-GPU: local Vulkan feasibility experiment

Status: deferred by the user on 2026-10-07 under ledger L75. Deep research into
Zig's GPU support must precede reconsideration. No implementation or GPU
submission is authorized. The proposal below is retained for that later review.
It does not select A7 tensor syntax or a production GPU backend. Record the
disposition in the [decision ledger](../decisions.md) before implementation.

## Decision and observable result

Approve a Zig 0.16.0 host program that dispatches one small GLSL compute shader
through the installed Vulkan driver, then checks all 256 output values against
a CPU reference. Keep the prototype and its evidence under
`tmp/v1-completion-2026-10-07/gpu/`. It will not change the A7 compiler or public
language behavior.

| State | Evidence |
| --- | --- |
| Before | A read-only query enumerates the Radeon 890M and compute-capable queues. No logical device, compute pipeline, or GPU submission has been tested. |
| After, if successful | The prototype submits four workgroups, waits for completion, copies GPU output back, and reports `gpu-vector-add: 256/256 matched`. |
| If blocked or incorrect | The prototype reports the missing prerequisite, Vulkan failure, or first mismatched element and exits nonzero. A CPU result cannot substitute for GPU evidence. |

The [published inventory digest](../../research/evidence/2026-10-07-zig-gpu/README.md)
records AMD Radeon 890M Graphics, RADV STRIX1, PCI `1002:150e`, kernel
`7.2.5-3-omarchy`, and Mesa `26.2.2-arch1.1`. The loader reports Vulkan
1.4.357; the device reports 1.4.354. One queue family advertises four compute
queues without graphics capability. These observations establish a candidate
route, not working shader execution. Zig 0.16.0, `glslc`, `glslangValidator`,
and `spirv-as` are installed. Recheck their versions when building the prototype.

## Workload and independent checks

The operation is unsigned 32-bit addition modulo 2^32. For indices 0 through
255, generate asymmetric inputs:

```text
left[i]  = (4294967280 + i) modulo 4294967296
right[i] = 3*i + 7
output[i] = (left[i] + right[i]) modulo 4294967296
```

Compute the CPU reference with `u64` arithmetic and an explicit 32-bit mask.
The shader uses GLSL `uint` addition. Pin these independently calculated
examples in the host check:

| Index | Left | Right | Expected output |
| --- | --- | --- | --- |
| 0 | 4294967280 | 7 | 4294967287 |
| 2 | 4294967282 | 13 | 4294967295 |
| 3 | 4294967283 | 16 | 3 |
| 16 | 0 | 55 | 55 |
| 255 | 239 | 772 | 1011 |

Compare every readback element, not a checksum or the presence of a completed
submission. Initialize device output with a sentinel before dispatch so an
unwritten element cannot pass. Include a CPU-only comparator check that changes
one reference value and confirms that comparison reports its index and values.
That check qualifies the comparison only; it is not GPU execution evidence.

Use a local size of 64 and four workgroups. There are no loops inside the
shader, floating-point operations, atomics, or workload-size options in this
prototype. Compile GLSL to SPIR-V with the installed `glslc`, targeting Vulkan
1.2. The host uses the existing loader and pinned Khronos headers already in
the inventory directory. No package installation or driver change is included.

## Allocation, transfers, and completion

The host selects the enumerated hardware device by vendor/device identity and
records its full name. It must reject a missing match, a software device, or a
missing compute queue. Re-enumerate queue families rather than assume the
inventory's family index still applies. Create one logical device and one queue.

Allocate two input storage buffers and one output storage buffer, each 1,024
bytes, plus an upload staging buffer and a readback staging buffer. Choose
memory types from the actual buffer requirements. Request host-visible staging
memory and prefer host-coherent memory. Record allocation sizes and memory type
indices. Refuse the run if driver-required buffer allocations exceed 1 MiB in
total; this cap does not measure driver-internal memory.

Record copies from upload staging to both inputs, fill the output sentinel,
then make transfer writes available to compute reads and writes. Bind three
storage-buffer descriptors and dispatch once. Make compute writes available to
the readback copy, copy output to staging, and make the copy visible to host
reads. Use the same queue family for copies and compute. Wait on a submission
fence before reading staging memory. Noncoherent uploads require flushes;
noncoherent readback requires invalidation after completion, with ranges aligned
to `nonCoherentAtomSize`. These dependencies follow the
[Khronos synchronization examples](https://docs.vulkan.org/guide/latest/synchronization_examples.html)
and [memory rules](https://docs.vulkan.org/spec/latest/chapters/memory.html).

On normal completion or a pre-submission error, release every created object
and allocation in dependency-safe order. Check Vulkan return codes. If a fence
wait reports failure, record the failure and submit no more work. Do not destroy
objects while submitted commands still use them. A failed wait does not qualify
recovery or cleanup of in-flight work; inspect the evidence before another run.

## Shared-machine limits and failure contract

Use `taskset -c 0-15` for builds and the host process on this 24-logical-CPU
machine, leaving eight CPUs outside the task's affinity. Use at most eight CPU
workers across concurrent task work. Run GPU submissions serially, with one
dispatch per invocation. There is no soak run, benchmark loop, or automatic
retry. No process termination outside the prototype, restart, GPU reset,
overclock, remote compute, or system configuration change is authorized.

Proposed exits are 0 for an exact match, 2 for missing tools or unsupported
prerequisites, 3 for Vulkan/build execution failure, and 4 for an output
mismatch. Report the failed stage and Vulkan result where available. Missing
Zig, `glslc`, headers, loader, matching hardware, or suitable memory must fail
before submission. Never install dependencies or switch to CPU execution to
make the GPU check appear to pass.

## Evidence and acceptance boundary

Save the exact commands, exit codes, stdout and stderr, source revision, and
SHA-256 hashes of host source, shader source, SPIR-V, executable, and headers.
Log Zig/shader-tool versions, kernel, driver/API versions, device identity,
queue selection, memory types, allocation sizes, submission result, fence
result, and all input/reference/readback arrays. Record whether Vulkan validation
layers are available and enabled. Do not install them as part of this approval.

Acceptance requires an actual dispatch on the logged Radeon, successful fence
completion, all 256 exact matches including the wrapping cases, and normal
resource cleanup. A shader compilation, queue enumeration, mock test, or CPU
comparison alone cannot satisfy it.

This result would qualify only this small integer workload and local toolchain.
It would not qualify an A7 GPU lowering path, model training, floating-point
semantics, performance, multiple devices, sustained load, power-loss recovery,
or behavior after device loss. Broader API, ownership, scheduling, numeric, and
compiler architecture decisions remain separate.

## Alternatives for disposition

| Choice | Consequence |
| --- | --- |
| Approve this Vulkan experiment | Obtain actual local dispatch evidence before choosing an A7 GPU architecture. |
| Keep CPU-only work for now | Continue compiler work; GPU execution remains untested. |
| Investigate another GPU runtime first | Requires a separate scope. The OpenCL loader currently returns no platforms, and HIP/CUDA tools were not found on PATH. |

The user deferred this experiment pending research into Zig's GPU support.
No implementation or GPU submission has occurred under this packet.
