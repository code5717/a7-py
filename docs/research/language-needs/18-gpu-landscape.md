# 18 — GPU compute landscape for A7

Status: research only, not approved syntax or roadmap commitment.
Per L8, interface sketches below are allowed as design input; none
are qualified or accepted language. A7 today emits Zig for CPU on
Linux x86_64 (`README.md:5,22`); no GPU code compiles.

## 1. CUDA (NVIDIA)

Programming model: host/device split. Kernels in CUDA C++
(`__global__`, thread/block/grid, shared memory, streams, explicit
or unified memory). Two host APIs: runtime (implicit context) and
driver (`cu*`, explicit context/module).

Bindings: kernel language is C++ (nvcc/clang). Host side has a
full C ABI: the driver API is plain C (`cuda.h`); NVRTC (runtime
kernel compilation) is a C API. A small language can emit PTX
strings, compile at runtime with NVRTC, and drive everything
through the C driver API. No C++ toolchain needed on user machines
if PTX ships ahead of time.

What A7 needs: a kernel-code path (emit CUDA C++ source or PTX),
host bindings to ~20 driver-API functions (context, module load,
`cuLaunchKernel`, memcpy, streams/events), and an annotation story
for device vs host pointers. Rust's `nvptx64-nvidia-cuda` target
shows the LLVM-to-PTX path works for small languages.

Maturity: highest (libraries, docs, installed base).
Lock risk: highest. Single vendor, proprietary driver/toolchain;
PTX is forward-compatible, SASS is not; CUDA code runs on NVIDIA only.

Verdict: FIRST, behind a vendor-neutral A7 interface (section 7).

## 2. ROCm / HIP (AMD)

Programming model: HIP is CUDA-shaped C++ by design; HIPIFY
converts CUDA source semi-automatically. Compiled with amdclang++ /
hipcc to AMDGCN code objects.

Bindings: C++ for kernels. Host runtime (`hip_runtime_api.h`) is
usable from C for host-only code; device launches need the HIP
compiler. hipRTC (runtime compilation) mirrors NVRTC. Same recipe
as CUDA: emit kernel source, compile with hipRTC or offline, drive
with the C-usable host API.

What A7 needs: same as CUDA plus a second kernel-compilation path
(AMDGPU target instead of PTX). If the A7 GPU interface is shaped
as "parallel loops + explicit buffers" rather than raw CUDA
spelling, one frontend feeds both NVRTC and hipRTC.

Maturity: medium, rising. ROCm 7.x aligned HIP to CUDA; 10.0
added memory-pool and cooperative-groups parity. Linux-first;
consumer-GPU support trails datacenter; majors break the API.
Lock risk: medium. Open stack, AMD-only hardware in practice; AMD
follows NVIDIA's lead instead of setting direction.

Verdict: FIRST (paired with CUDA). HIP's CUDA likeness means one
A7 GPU interface covers both at small extra cost. Do not adopt
`roc*`-only libraries in the core interface.

## 3. oneAPI / SYCL (Intel, cross-vendor in theory)

Programming model: single-source C++17 with queues, buffers or USM
(unified shared memory) pointers, and command groups; compiler
builds a fat binary with SPIR-V plus per-target images. SYCL 2020
is the current standard; DPC++ adds a `kernel_compiler` extension
for runtime compilation of kernel strings.

Bindings: C++ only. There is no stable pure-C SYCL API; community
Rust bindings (`sycl-rs`) are pre-0.1 experimental and still require
the Intel DPC++ toolchain installed. A small language must either
generate SYCL C++ source and shell out to `icpx`, or target Level
Zero / OpenCL directly and skip SYCL.

What A7 needs: a source-emit step producing SYCL C++ with
fat-binary flags (`-fsycl -fsycl-targets=...`); or skip SYCL and
reach Intel GPUs through Vulkan/WebGPU instead. Either way the
host side drags in a heavy C++ toolchain.

Maturity: medium-low outside Intel shops. Open Khronos spec, and
DPC++ can emit PTX/AMDGPU images, but mindshare and library depth
trail CUDA; toolchain releases break the ABI.
Lock risk: low on paper, medium in practice (the usable
implementation is Intel's; Intel compute share is small).

Verdict: LATER. Keep the A7 interface abstract enough for a later
SYCL source-emit backend; no V1-era DPC++ dependency.

## 4. Metal (Apple)

Programming model: MSL (Metal Shading Language, C++14-based, C++17
in Metal 4) for kernels/compute; Objective-C/Swift/C++ host API
(devices, command queues, buffers, compute encoders, pipelines).
Runtime shader compilation is built in (`MTLDevice`
`newLibraryWithSource`); Metal 4 adds an explicit compiler object
with QoS control and on-disk pipeline archives.

Bindings: no official C API. Apple ships Objective-C/Swift headers
and `metal-cpp` (header-only C++17). A C language binds through the
ObjC runtime or a small shim; community C wrappers exist but are
unofficial and pre-1.0. MSL source generates as text like any
kernel language.

What A7 needs: a text-emit path for MSL kernels, a thin host shim
over the ObjC runtime (device, queue, buffers, dispatch, readback),
built only on Apple hosts. Argument binding is index-based, which
suits generated code.

Maturity: high on Apple hardware, nonexistent elsewhere.
Lock risk: total in its lane — Apple-only, proprietary.

Verdict: LATER. Needed when A7 cares about Mac laptops. Isolate
behind the portable interface; keep MSL idioms out of A7 syntax.

## 5. WebGPU / Dawn compute (portable, browser-shaped)

Programming model: WGSL compute shaders, explicit
device/queue/bind-group setup, async buffer mapping. Same shader
runs in browsers and natively via Dawn or wgpu-native.

Bindings: best C story here. Dawn exposes `webgpu.h`; wgpu-native
exposes a C ABI too. Link one shared library, generate WGSL text,
call plain C. No vendor SDK, no kernel compiler install.

What A7 needs: WGSL text emission plus host bindings to the
`webgpu.h` surface (device, shader module, pipeline, bind group,
command encoder, readback). The shader model is lower-ceiling than
CUDA (no tensor-core intrinsics, limited 64-bit atomics), so map
only the portable subset.

Maturity: medium, rising fast. Stabilized 2024–2025; Dawn and
wgpu ship real apps; validation layers good. The spec constrains
advanced compute for web portability.
Lock risk: lowest. Multi-vendor, open spec, no hardware gatekeeper.

Verdict: FIRST, as the default portable backend. One C-linkable
runtime across NVIDIA, AMD, Intel, Apple, no vendor SDK. Users who
outgrow the ceiling move to CUDA/HIP.

## 6. Vulkan compute shaders (portable, high ceiling)

Programming model: GLSL/HLSL compute shaders compiled to SPIR-V,
dispatched through Vulkan queues with explicit descriptor sets,
memory barriers, and command buffers. No hidden state; the app
controls everything, including synchronization.

Bindings: pure C. The loader API is C (`vulkan.h`); glslang/DXC
are callable tools or libraries; SPIR-V is an open IR a small
language can emit directly. Friendliest native API for a
hand-rolled compiler backend.

What A7 needs: SPIR-V or GLSL emission, host bindings to the
Vulkan compute subset (instance, device, queue, descriptor sets,
pipeline, fences), and a runtime module honest about explicit
barriers. Wraps once into a reusable module.

Maturity: high. Ships everywhere except Apple-proper (needs
MoltenVK on macOS). Validation layers and profilers are strong.
Lock risk: low. Open Khronos standard, all major vendors.

Verdict: FIRST. The portable high-ceiling backend: where WebGPU's
limits pinch, Vulkan exposes the rest. Share shader-generation
work between the two.

## 7. Recommendation for A7

One portable GPU interface, three first backends:

1. WebGPU/Dawn — default portable backend, C ABI, no vendor SDK.
2. Vulkan compute — portable high ceiling, pure C, shares
   shader-generation work with WebGPU.
3. CUDA/HIP — performance backend through one CUDA-shaped path
   (NVRTC + hipRTC).

Later: Metal (when Mac matters), SYCL (only on demand). Never a
vendor spelling in A7 syntax. Kernels stay lowerable text plus a
small C host runtime per backend; A7 names parallel loops and
buffers, not `__global__` or `@workgroup_size`. V1 CPU-only work
stays sound: effect and memory-home notes (file 09, sections 2–5)
transfer unchanged when backends land.
