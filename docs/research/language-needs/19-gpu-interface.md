# 19 — GPU / accelerator interface (design only)

Status: interface design only, 2026-10-02. No qualification, no implementation.
Per L8, V1 is CPU first with an interface for a later GPU backend; L8 permits
interface design but qualifies no GPU, NPU, TPU, or FPGA. Per L36, GPU work is
a later track. Per L41, Zig handles native imports, runtime, builds, linking.
This file sketches the interface shape so V1 decisions do not block it.
Nothing here is approved syntax. Every spelling below is undecided and needs
a before/after packet plus user approval before any compiler change.

## 1. What A7 code must express (and what it must not)

Five pieces, no more:

1. Kernel spelling: which function runs on the device.
2. Dispatch: grid/block sizes, launch site.
3. Host-device movement: copy in, copy out, placement query.
4. Streams and sync: order, wait, overlap.
5. Errors: device failure as a value the caller checks.

What A7 must not express in V1: placement annotations on types, transfer-cost
promises, vendor pragmas, inline device assembly, manual fence insertion.
SPEC section 9.9 (`tensor_to_gpu`, `tensor_to_cpu`, `tensor_device`) is a
design target, not implemented syntax.

## 2. Kernel spelling (verdict: design later)

No new keyword in V1. Candidates only:

```a7
// Option A: attribute on an ordinary function (preferred: no new keyword,
// fits existing @vectorize/@parallel annotation style in SPEC 9.7)
@kernel
vadd :: fn(a: []f32, b: []f32, out: []f32) {
    i := thread_id()
    out[i] = a[i] + b[i]
}

// Option B: block form (rejected for now: new control construct, no need)
gpu {
    out[i] = a[i] + b[i]
}
```

Rules to decide later: kernels take slices only (no `ref` escape, no
recursion — A7 recursion is already banned), no `new`/`del` inside, no IO.
Restriction set must match what the Zig reuse path (section 5) can lower.

## 3. Dispatch (verdict: design later)

Launch stays an explicit call, never implicit. Sketch:

```a7
h := gpu_alloc(n * size_of(f32))   // device buffer handle, see section 6
gpu_copy_to(h, host_slice)
gpu_launch(vadd, grid: 128, block: 256, h_a, h_b, h_out)
gpu_sync()
gpu_copy_from(host_out, h_out)
```

Why explicit: L40 says unknown effects stay sequential. Implicit auto-offload
would break that rule and hide transfer cost. Grid/block are plain `usize`
args so the shape works on CPU fallback too (launch = loop).

## 4. Host-device memory movement (verdict: design now the handle contract)

Placement is explicit and visible. No silent migration. Three ops:

- `gpu_alloc(nbytes: usize)`: returns a device handle or an error.
- `gpu_copy_to(handle, host_slice)` / `gpu_copy_from(host_slice, handle)`.
- `gpu_free(handle)`.

`tensor_to_gpu` / `tensor_to_cpu` (SPEC 9.9) become library functions over
these three ops later, not compiler magic. V1 work now: keep target selection
separate from storage ownership and physical placement (file 09, section 5),
and record device identity in the IR effect set (roadmap step 3) so later
analysis sees "this slice lives on device 0". No placement syntax ships now.

## 5. What the Zig backend can reuse (verdict: design now the bridge shape)

V1 builds only the checked synchronous native bridge (L41). The GPU adapter
plugs into that bridge later. Reuse candidates found 2026-10-02:

| Path | State | Fit for A7 |
| --- | --- | --- |
| C ABI calls into CUDA runtime (`cudaMalloc`, `cudaMemcpy`, `cudaLaunchKernel`) via Zig `@cImport` / `extern` | Stable, documented, vendor-supported | Best first device path: Zig already calls C ABIs; A7 emits the same `extern` decls it emits for libc today |
| HIP/ROCm runtime (`hipMalloc`, `hipMemcpy`, `hipLaunchKernel`) via the same C ABI route | Stable on Linux for AMD datacenter parts; consumer-part support uneven | Same bridge as CUDA; one interface, two vendor backends |
| Zig SPIR-V backend (`spirv64-vulkan-none`, `spirv64-opencl-none`) for kernels | Maturing, experiments only; doc gaps | Later: lets kernels be written in a Zig subset instead of shipped PTX/GCN blobs |
| Zig-emitted PTX (`nvptx64-cuda-none`) / AMDGCN (`amdgcn-amdhsa-none`) via LLVM | Works for basic kernels; needs runtime loader glue | Later: avoids vendoring `nvcc`/`hipcc` output |
| `zgpu` / `mach/gpu` (WebGPU/Dawn bindings for Zig) | Maintained, graphics-first | Never for compute core: WebGPU limits (no unified memory control, shader-language detour) add cost without A7 benefit |
| `zcuda` (Zig CUDA bindings + kernel DSL) | Community, young | Watch only; do not depend on until stable |

Order: (1) C ABI bridge to CUDA/ROCm runtimes behind the L41 checked
interface; (2) Zig-compiled kernels when the SPIR-V/PTX path is documented;
(3) never WebGPU as the compute substrate.

## 6. Handle ownership under A7 memory direction (verdict: design now)

Device buffers are handles, not `ref` pointers. Application code never sees a
raw device address (L41: no raw native pointers in app code). Sketch:

```a7
h := gpu_alloc(1024)      // owner: caller scope
defer gpu_free(h)         // same cleanup shape as defer/del today
gpu_copy_to(h, data)
```

Rules: one owner per handle (mirrors the exclusivity shape in file 06,
section 3); copies are explicit (`gpu_copy_to`/`gpu_copy_from` only); a
handle must never sit in a bulk-reset arena extent (file 06, M45: resources
and native-retained buffers excluded); double-free and use-after-free follow
the same `del` validation direction as host memory. No borrow syntax for
handles; pass by value, invalidate on free. Cycle policy: handles hold no
references to each other, so no cycle handling needed.

## 7. Streams and sync (verdict: design later)

Default is fully synchronous: every launch completes before the next
statement. Async needs an explicit stream handle:

```a7
s := gpu_stream_create()
gpu_launch_on(s, vadd, grid: 128, block: 256, h_a, h_b, h_out)
gpu_stream_sync(s)     // wait; error surfaces here too
gpu_stream_destroy(s)
```

Cross-stream ordering and overlap are later work. V1 keeps the sync bridge;
no async/device execution until sync is sound (file 09, section 6).

## 8. Error model for device failures (verdict: design now)

Device failures are values, not traps. Failing ops return a status the caller
must check; unchecked launch results are a compile error (same direction as
`new` returning `nil` today, SPEC 8.2). Cases: no device, out of device
memory, launch failure, copy failure, timeout. Sketch:

```a7
h := gpu_alloc(n)
if h == nil {
    ret CpuFallback
}
ok := gpu_copy_to(h, data)
if !ok {
    gpu_free(h)
    ret CpuFallback
}
```

No exceptions, no panics for recoverable device errors. Shape matches a
future `Result` union; do not invent throw/catch syntax for this (never).

## 9. CPU-first rule (verdict: now)

Every GPU sketch above must also run on CPU: `gpu_launch` without a device
lowers to a loop; `gpu_copy_*` without a device are plain copies; placement
queries report "host". This keeps L8 (CPU first) and L38 (C-baseline perf
gate) meaningful and stops device syntax from splitting the language.

## 10. Verdict table

| Piece | Verdict | Reason |
| --- | --- | --- |
| Handle + copy + error contract (sections 4, 6, 8) | Design now | Shapes IR effects and the L41 bridge; blocks nothing |
| C ABI bridge shape for CUDA/ROCm runtimes (section 5) | Design now | L41 Zig-native path; vendor kernels stay outside A7 per L9 |
| Kernel spelling, dispatch, streams (sections 2, 3, 7) | Later | Needs typed IR effects + memory contract first (file 09, section 6) |
| WebGPU as compute substrate, device assembly, hidden auto-offload, throw/catch errors | Never | Cost, complexity, or conflict with L40/L41 |
