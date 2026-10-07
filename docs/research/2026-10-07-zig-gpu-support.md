# Zig GPU support, 2026-10-07

GPU implementation is deferred. Zig can act as a CPU host for a GPU API and can
compile some device code, but those are separate capabilities. The evidence here
does not qualify an A7 GPU backend, tensor syntax, training, or GPU execution.
The repository pins Zig 0.16.0. Upstream has since released 0.17.0 with changes
that matter for SPIR-V. A toolchain upgrade requires its own compatibility review.

## Versions and evidence boundary

| Version | Evidence | Qualification |
| --- | --- | --- |
| Installed 0.16.0 | `zig version`; local binary hash and compile commands recorded below | Used for the compile-only probes; no device execution |
| Released 0.16.0 | Official source archive, index date 2026-04-13 | Compared with installed standard library and later source |
| Released 0.17.0 | Official index date 2026-10-01; release announcement dated October 2 | Latest stable at retrieval; source inspected, compiler not installed or run |
| 0.18.0-dev.35+5e754304d | Official index date 2026-10-05 | Development source snapshot only; no assumption of release stability |

Sources: [official download index](https://ziglang.org/download/index.json),
[0.17 announcement](https://ziglang.org/news/0.17.0-released/), and
[0.17 release notes](https://ziglang.org/download/0.17.0/release-notes.html).
Retrieval occurred on October 6 UTC, October 7 in Riyadh. The
[evidence manifest](evidence/2026-10-07-zig-gpu/sources.json)
records each URL, retrieval timestamp, SHA-256, and retrieval errors. All three
source archives matched their published index hashes. Extracted source preserves
archive version directories. Codeberg pages were attempted; the release archives
provide the primary source when web access fails.

The [June 26 development log](https://ziglang.org/devlog/2026/), not June 25,
reported 49% behavior-test progress for `spirv64-vulkan`. That historical number
is neither a current pass rate nor an executed-GPU acceptance result. In 0.17,
`test/tests.zig:1590-1593` still has the SPIR-V target disabled with an incomplete-backend
comment. Its SPIR-V branch at line 3047 requests an emitted binary without running
it. The inspected development snapshot retains these boundaries. No upstream
GPU test runner or driver setup was qualified by this research.
[Versioned test configuration](https://codeberg.org/ziglang/zig/src/tag/0.17.0/test/tests.zig).

## Device compilation support

Both release notes place AMDGCN, NVPTX, and SPIR-V targets among additional
platforms outside the ordinary support-tier table. A target name establishes a
compiler route, not a supported end-to-end GPU product.
[0.16 platform list](https://ziglang.org/download/0.16.0/release-notes.html#Additional-Platforms),
[0.17 platform list](https://ziglang.org/download/0.17.0/release-notes.html#Additional-Platforms).

| Route | Pinned 0.16 | Stable 0.17 and inspected development source | Remaining boundary |
| --- | --- | --- | --- |
| SPIR-V for Vulkan/OpenCL/OpenGL | Self-hosted backend; `std.gpu`; bare `.spirv_kernel` convention; `executionMode` helper | `std.spirv`; structured execution-mode options; `@SpirvType`; task/mesh conventions | Incomplete backend; no local emitted SPIR-V success or execution established |
| AMDGCN | LLVM route; `amdgcn_kernel`, device and compute-shader conventions; AMD address spaces and work-item intrinsics | These routes remain in source | Empty object emitted locally; loaded kernel ABI, target CPU compatibility and execution unqualified |
| NVPTX | LLVM route; kernel/device conventions; PTX assembly output required | Routes remain in source | Local minimal exported kernel hit LLVM alias errors; no usable PTX established |
| CPU host calling GPU API | C ABI declarations, imported/generated bindings, native linking | Host support remains distinct from shader support | Every API needs bindings, runtime, resource management and device qualification |

Evidence: [0.16 calling conventions](https://codeberg.org/ziglang/zig/src/tag/0.16.0/lib/std/builtin.zig),
[0.16 LLVM code generation](https://codeberg.org/ziglang/zig/src/tag/0.16.0/src/codegen/llvm.zig),
[0.17 language types](https://codeberg.org/ziglang/zig/src/tag/0.17.0/lib/std/lang.zig),
[0.17 SPIR-V library](https://codeberg.org/ziglang/zig/src/tag/0.17.0/lib/std/spirv.zig),
and [0.17 `@SpirvType` behavior tests, lines 4-24](https://codeberg.org/ziglang/zig/src/tag/0.17.0/test/behavior/spirv.zig#L4-L24).
These files are also in the captured source trees.

The 0.17 changes include opaque sampler/image/runtime-array types and descriptor
decorations. Execution modes move into calling conventions. Capabilities and
extensions come from target CPU features instead of inline `OpCapability` or
`OpExtension`. These changes require source migration from 0.16 examples.
The development snapshot's `std.spirv` is byte-identical to 0.17, but its backend
has later numeric-conversion and vector-bitcast changes. The inspected
`CodeGen.zig` diff updates cross integer/float conversion opcode selection and
per-lane vector bitcasts. Therefore a fix visible on master cannot be credited
to 0.17 without checking the release source.
[0.17 backend](https://codeberg.org/ziglang/zig/src/tag/0.17.0/src/codegen/spirv/CodeGen.zig),
[development backend at 5e754304d](https://codeberg.org/ziglang/zig/src/commit/5e754304d/src/codegen/spirv/CodeGen.zig).

## Kernel features and limits

| Requirement | Source evidence | Consequence for future tensor research |
| --- | --- | --- |
| Invocation and group IDs | `@workItemId`, `@workGroupId`, `@workGroupSize`; LLVM `FuncGen.zig:6096` maps AMDGCN/NVPTX intrinsics; SPIR-V backend maps input builtins | Indexing primitives exist. Backend-specific return types, dimensions and overflow still need qualification |
| Workgroup size | 0.17 structured kernel convention carries x/y/z; SPIR-V `airWorkGroupSize` retains a driver-crash TODO | Prefer known compile-time geometry in a future experiment; the TODO is evidence of unresolved handling, not a reproduced local driver fault |
| Address spaces | `std.lang.AddressSpace` includes global/shared/local/private/input/output/uniform/push_constant/storage_buffer | Device pointers are not ordinary host pointers. Specify ownership, binding, lifetime, stride and alignment before lowering |
| Workgroup barriers | 0.17 `std.spirv` has control and memory barriers; `workgroupBarrier` requests workgroup scope with acquire/release shared-memory semantics | Useful building block. Divergent barriers, cross-workgroup synchronization and host/device visibility need distinct rules |
| Atomics | Ordinary atomics tests skip stage2_spirv; 0.17 SPIR-V AIR dispatch has no atomic handlers and falls into TODO for unsupported tags | Treat language-level SPIR-V atomics as unsupported in this audit. Grammar opcode names and inline assembly do not establish usable Zig atomic lowering |
| f32/f16/f64 | SPIR-V codegen represents 16/32/64-bit floats and arithmetic; 80/128-bit constant paths remain TODO; capabilities are target-dependent | Arithmetic representation does not establish numeric accuracy, denormal behavior, rounding, contraction or device feature enablement |
| Buffers and layout | Runtime arrays/descriptors exist in 0.17; Vulkan has explicit layout rules | Validate host offsets and shader ArrayStride/Offset decorations. An `extern struct` alone does not prove a Vulkan layout match |
| Debugging | `airDbgStmt` emits OpString/OpLine when not stripped; variable names are emitted | Source annotations are present. Device stepping, traps, bounds reporting and recovery remain unverified |
| General Zig constructs | 0.17 backend has `airMemcpy` TODO, function-pointer representation TODO, incomplete composite-integer cases and unsupported AIR tags | Define a small supported kernel subset before attempting general A7 lowering |

Sources: [LLVM work-item implementation](https://codeberg.org/ziglang/zig/src/tag/0.16.0/src/codegen/llvm/FuncGen.zig),
[SPIR-V code generation](https://codeberg.org/ziglang/zig/src/tag/0.17.0/src/codegen/spirv/CodeGen.zig),
[atomics tests](https://codeberg.org/ziglang/zig/src/tag/0.17.0/test/behavior/atomics.zig),
[SPIR-V library](https://codeberg.org/ziglang/zig/src/tag/0.17.0/lib/std/spirv.zig),
and [Vulkan shader layout](https://docs.vulkan.org/guide/latest/shader_memory_layout.html).

For future f16 work, arithmetic support and 16-bit storage support must be checked
separately. The local inventory queried core float64/int64/int16 flags, not
`shaderFloat16` or 16-bit storage extension feature chains. Neither f16 execution
nor tensor/matrix instructions are qualified. GPU reduction order can differ from
the CPU order. A design must state exact integer behavior and explicit floating
point tolerances, including NaN, infinity and denormal handling. These are design
criteria, not changes to current A7 semantics.

## Host API options

Zig's C interoperability permits a host to call a GPU library. It does not supply
that library, allocate a device, or launch a shader automatically.
[Zig 0.16 C interoperability](https://ziglang.org/documentation/0.16.0/#C).

| API | Host/device boundary | Local evidence and limits |
| --- | --- | --- |
| Vulkan | Host creates device, buffers, descriptors, pipeline and command submissions; SPIR-V supplies shader code | RADV loader/device enumeration works. Installed GLSL tools offer a compiler-independent shader route for a future controlled comparison |
| OpenCL | C API loads source or accepted IL, creates kernels and enqueues work | Loader exists but enumeration returned -1001 and zero platforms; SPIR-V target presence does not supply an OpenCL implementation |
| HIP/ROCm | HIP module APIs load device code and retrieve functions; runtime controls launch and memory | No hipcc/rocminfo detected. AMD's current matrix lists 890M, but this Arch/Omarchy system is not established as a supported matrix configuration |
| CUDA | Driver module API loads PTX/cubin, JITs when needed and returns kernel handles | No NVIDIA device or nvcc in inventory. This is a future NVIDIA route, not a local AMD route |
| WebGPU | Native C headers bind Dawn or wgpu-native; shader/runtime support depends on chosen implementation | No WebGPU runtime was inventoried or qualified; header availability alone supplies no device runtime |

Primary API references: [OpenCL specification](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_API.html),
[HIP module management](https://rocm.docs.amd.com/projects/HIP/en/latest/reference/hip_runtime_api/modules/module_management.html),
[ROCm 7.14.1 matrix](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html),
[CUDA module management](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MODULE.html),
and [WebGPU native headers](https://github.com/webgpu-native/webgpu-headers).

The original retrieval manifest records HTTP 403 for the Vulkan shader-layout
page and OpenCL specification; neither page was fetched in that capture.
Follow-up web retrieval on 2026-10-07 succeeded for both primary sources.
The [Vulkan guide](https://docs.vulkan.org/guide/latest/shader_memory_layout.html)
explains alignment requirements and the `ArrayStride`/`Offset` examples.
The [OpenCL specification](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_API.html)
identifies itself as v3.1.2, dated 2026-09-17, commit
`219be24fc8947c68ee45b4d25b55a92b8f799f29`. Its program-object and kernel-execution
sections document `clCreateProgramWithSource`, `clCreateProgramWithIL`,
`clCreateKernel` and `clEnqueueNDRangeKernel`. This follow-up verifies the API
and layout descriptions above; it adds no local device-execution evidence.
The original manifest remains a record of the earlier failed requests.

No one API or device compiler has been selected. A Zig CPU host using an external
GLSL compiler would test a different claim from a Zig-authored SPIR-V kernel.
Both differ from A7 generating device code. Any future experiment must name
which boundary it measures.

## Local evidence and compile-only probes

The [inventory digest](evidence/2026-10-07-zig-gpu/README.md) found
AMD Radeon 890M Graphics, RADV STRIX1, PCI 1002:150e, Mesa 26.2.2-arch1.1 and
Vulkan device API 1.4.354. Queue family 1 advertises four compute queues;
64 KiB shared memory and 1,024 invocations per group are reported limits.
Enumeration did not submit commands. It proves available API/device discovery.

This research ran only CPU compilation, pinned to CPUs 12-15, with task-local
Zig caches. No GPU commands, package installs, toolchain changes, driver changes
or stress tests occurred. The tracked [compile probe digest](evidence/2026-10-07-zig-gpu/compile-probes.json)
contains the input texts, compiler arguments, return codes, diagnostics and hashes.
The [evidence notes](evidence/2026-10-07-zig-gpu/README.md) distinguish historical
commands from rerun recipes and record missing metadata. Raw archives remain
local under `tmp/v1-completion-2026-10-07/zig-gpu-research/`; published conclusions
do not depend on readers accessing that ignored directory.

| Probe with installed 0.16.0, ReleaseFast | Observed result | What it establishes |
| --- | --- | --- |
| Empty exported SPIR-V Vulkan kernel with old executionMode helper | Process signal 11, no stderr | This installed compiler build crashes for this exact input/command |
| SPIR-V variant containing a shared u32 atomic add | Process signal 11, no stderr | No atomic-lowering result can be inferred because compilation crashed |
| Empty exported AMDGCN kernel, amdgcn-amdhsa | Exit 0, relocatable AMD GPU ELF object | Target object emission only; no CPU model match, loadable kernel ABI or execution proof |
| Empty exported NVPTX kernel, binary output | Exit 1, diagnostic requires `-femit-asm` | Binary output is unsupported on that route |
| Same NVPTX source, assembly output, default CPU | Signal 6; LLVM alias error requires PTX >=6.3 and sm_30 | Default target configuration did not emit usable PTX |
| Same NVPTX source, assembly output, explicit sm_80 | Signal 6; LLVM aliasee must be a non-kernel function | A distinct export/alias failure remains after changing target features |

These failures do not establish that every 0.16 GPU program fails. No stack trace
or root-cause diagnosis was performed. The empty probes deliberately avoid
claiming arithmetic, resource binding, shader validation or driver compatibility.
The failed SPIR-V case was not retried. No newer compiler binary was installed
to test whether the observed failures are fixed.

## Reconciliation with earlier A7 research

[Report 20](language-needs/20-ml-gpu-stack.md) proposes a library-first tensor
stack, CPU numeric semantics, then GPU bindings and limited code generation.
Those are historical recommendations. Its references to SPEC section 9 now point
to the stable stub; the design text lives in
[array programming](../design/array-programming.md). Statements about what A7
should copy, never build, or implement first are not implementation approval.
This audit did not revalidate its framework comparisons or performance claims.

[Report 21](language-needs/21-small-lang-gpu.md) recommends WebGPU/WGSL with a
Zig host. Its description of Zig interop as nearly free omits binding maintenance,
resource lifetime, layout, synchronization and device qualification. Zig's native
SPIR-V and LLVM GPU routes also deserve an explicit comparison, even though the
current evidence does not qualify them. The local Vulkan inventory changes the
available experiment options; it does not ratify Vulkan or invalidate WebGPU.
Specific zgpu/Mach library versions and their compatibility with Zig 0.16/0.17
were not audited here, so historical library names are not current dependency
recommendations.

[Report 25](language-needs/25-stdlib-placement.md) proposes `cextern` plus header
imports and labels C interop as later library work. That is a proposed A7-facing
interface, not proof that A7 already exposes arbitrary GPU APIs. The host Zig
compiler's C ABI capability does not settle A7 declarations, ownership, error
conversion, packaging or dependency policy. Those decisions remain separate from
GPU target emission. The earlier reports are preserved as historical research;
this document qualifies their Zig-specific assumptions without adopting their
architecture recommendations.

## Decision criteria after deferral

The user deferred GPU work for this research. The
[local Vulkan proposal](../plan/packets/P-GPU-local-vulkan.md) remains a separate
proposal; this document does not approve or execute it. Scheduling and remaining
actions belong in the [delivery roadmap](../plan/delivery-roadmap.md).

A later decision should resolve the intended boundary first: GPU access from a
Zig CPU host, Zig device compilation, or A7 device lowering. The smallest useful
compiler qualification corpus would cover indexing, descriptor layout, wrapping
u32 arithmetic, f32 operations, conversions and workgroup shared memory. If the
intended workload needs f16, atomics or matrix instructions, those become explicit
requirements rather than presumed consequences of accepting a Vulkan target.

Before selecting a compiler route, the evidence should include emitted-module
validation for an exact target environment, inspection of entry points and buffer
layout, and version-pinned expected diagnostics for unsupported constructs.
Version comparison should isolate the repository's 0.16 host from any separately
approved 0.17 device compiler experiment. Replacing the repository's compiler pin
would require the existing compiler/package and release gates.

If execution is later approved, a bounded CPU-reference comparison on the actual
890M can qualify allocation, transfer, synchronization, dispatch and readback.
Separate tests would be needed for floating-point error, barriers, atomic scope,
missing-device failures and cleanup. Training, performance, portability and
power-loss recovery require further evidence. Source inspection and these
compile-only probes settle none of those acceptance questions.
