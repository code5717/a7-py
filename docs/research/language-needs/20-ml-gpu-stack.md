# 20 — ML GPU stack: how frameworks lower tensor ops

Status: research only. No syntax or roadmap commitment. A7 today is CPU-only
via Zig (`18-gpu-landscape.md`, `19-gpu-interface.md`, SPEC §9).

## 1. PyTorch: library-first with codegen on top

Stack: Python `torch.*` -> ATen dispatcher (C++, `native_functions.yaml`
schema registry) -> per-device kernels. Heavy ops are not handwritten:
GEMM calls cuBLAS/cuBLASLt, convolution/RNN/attention call cuDNN, sparse
and solvers call cuSPARSE/cuSOLVER. Elementwise and reduction ops use
handwritten CUDA kernels over TensorIterator (shared loop driver for
broadcasting and type dispatch). Autograd lives above dispatch, so a new
CUDA kernel keeps backward for free if the schema matches.

Codegen layer: `torch.compile` (TorchInductor) fuses the graph and emits
Triton kernels for elementwise, reduction, GEMM-adjacent shapes; Triton
compiles tile programs to PTX without hand-tuning each shape. FlagGems
shows the same path: Triton implementations registered into the ATen
dispatcher override CUDA for portability to new vendors.

Verdict for A7: reuse the pattern, not the code. A7 cannot vendor
cuBLAS/cuDNN. What transfers: dispatcher shape (one op schema, many
device impls), TensorIterator-like loop driver on CPU first, and Triton
as the answer to "who writes the Nth fused kernel".

## 2. JAX/XLA: compiler-first, libraries as callees

Stack: `jnp` trace -> jaxpr -> StableHLO (~100 statically shaped ops) ->
XLA:GPU -> (LLVM NVPTX emitters + TritonIR emitters + calls into
cuBLAS/cuDNN/NCCL). Fusion is the main optimization: elementwise chains
collapse to one kernel. Matmul/softmax fusions lower through Triton.
PJRT runtime handles buffers and devices. User code never calls cuBLAS
directly; XLA chooses it.

Cost: whole-program compile (tracing + autotuning + codegen), static
shapes, opaque performance cliffs when fusion fails. Benefit: one
frontend covers CPU/GPU/TPU.

Verdict for A7: do not rebuild XLA. No MLIR, no StableHLO, no PJRT at
A7 scale. What transfers: static-shape fast path and fusion as an
optimization over an already-correct CPU op library, never as the first
implementation.

## 3. Mojo/MAX Engine: split kernels from serving

Stack: Mojo kernel code (`max.gpu`: threads, blocks, barriers, shared
memory) + layout types (`LayoutTensor`, tiling) + ready kernels
(`linalg`, `nn`: matmul, attention, conv, softmax, norm) all lowered
through MLIR to CPU/GPU/ASIC. A graph compiler schedules ops; `comm`
and `shmem` handle multi-GPU and multi-node. TensorCore struct wraps
NVIDIA/AMD mma with shapes per arch (e.g. f16 16x8x16 on NVIDIA).

Cost: compiler team plus hardware partners. Benefit: one language from
kernel to server, vendor-tuned kernels in-tree.
Verdict for A7: copy the split (kernels as text, host as Zig), reject
the stack. The `max.gpu` + `layout` + `nn` package split is a good
model for a future `std/gpu`, `std/layout`, `std/nn` shape. MLIR
itself is out of scope (see `21-small-lang-gpu.md`).

## 4. TinyGrad: smallest credible full stack

Stack: `Tensor` builds a lazy UOp graph (movement ops: reshape,
permute, expand, pad; elementwise; reduce; WMMA for tensor cores).
Scheduler breaks the graph into one kernel per CALL, fuses and folds
views, runs BEAM search over tilings, then Renderer emits source per
backend (CUDA, HIP, Metal, OpenCL, LLVM, WGSL) and Compiler builds it.
Backends in `tinygrad/runtime/` are thin; most logic is shared UOps.

Verdict for A7: closest to an achievable end state. UOp-style IR with
6 movement ops + lazy realization + per-backend renderers fits a small
team. But TinyGrad still required years of codegen and BEAM tuning.
A7 should treat it as the ceiling of custom codegen ambition, reached
only after Stage 1 FFI (file 21, Stages 1-2) saturates.

## 5. Burn/Candle: what Rust proves about small-team GPU

Burn: `Backend` trait; ops generic over device. Portable path is
`burn-wgpu` (CubeCL DSL -> WGSL default, SPIR-V flag for matmul with
tensor cores and f16). Fast path is `burn-cuda` / `burn-rocm` /
`burn-tch` (LibTorch). `burn-fusion` decorator fuses op streams;
`burn-autodiff` decorator adds backward to any backend. Lesson: trait
+ decorator keeps one op definition with many devices, and WGSL-first
works for portability but needs SPIR-V or CUDA to reach matmul speed.

Candle: minimal tensor lib over CPU plus CUDA via `cudarc` and
`candle-kernels` (handwritten CUDA), Metal/Accelerate on Mac. No
compiler, no autotuner. Lesson: FFI to vendor libs plus a few custom
kernels is enough for inference; training-speed parity is not.

Verdict for A7: imitate both. Burn's trait/decorator shape maps to A7
generics (`$T: Numeric`) plus a device handle (file 19, sections 4-6).
Candle's scope (inference-grade FFI, no autotuner) is the correct first
GPU ceiling for A7.

## 6. Kernel libraries vs codegen vs autotuning

Three layers, in cost order:

1. Call a library (cuBLAS, cuDNN, MKL, Accelerate). Cheapest, fastest
   per-op. Cost is dependency and vendor lock, not code.
2. Emit fixed kernels (handwritten CUDA/WGSL strings, one per op).
   Covers elementwise, reductions, transpose. Cost is linear in op
   count times backend count.
3. Generate and tune (Triton, Inductor, XLA fusion, TinyGrad BEAM,
   CUTLASS templates). Covers fused and odd-shaped cases. Cost is a
   compiler project of its own.

A7 order: 1 via C ABI where the license allows, then 2 for a small
blessed subset (map/reduce over slices, file 21 Stage 2), never 3 in
V1. Autotuning before a correct CPU library is wasted work.

## 7. A7 tensor track: reuse vs rebuild (SPEC §9)

Reuse (no new language): `tensor_*` op list in SPEC 9.1-9.6 as library
function signatures over slices and structs; Burn-style generic
constraint (`$T: Numeric`) already exists in SPEC §7; handle + copy +
error contract from file 19 (sections 4, 6, 8); CPU loop driver in
host Zig (TensorIterator role without the C++).

Rebuild later (small, A7-owned): contiguous/strided layout helpers
(SPEC 9.7), broadcast shape rules tested on CPU, one codegen subset
(elementwise map/reduce to WGSL text), CPU fallback for every GPU op
(file 19, section 9).

Never rebuild: dispatcher with 2000+ ops, autograd engine, graph
compiler, MLIR/XLA/PJRT, NCCL-equivalent. Call or defer all of these.

SPEC §9 gaps that block even CPU work: tensor types are design text,
not implemented; no `f16`/`bf16` types exist (see section 8); no
device type exists (`tensor_device` returns `Device`, undefined).

## 8. f16/bf16 story on GPU

Hardware: NVIDIA Tensor Cores accelerate f16/bf16/TF32/FP8 matmul at
8-16x vs f32 CUDA cores (Ampere and later; Blackwell adds NVFP4/MXFP
block-scaled types via CUTLASS). AMD matrix cores cover f16/bf16 on
MI100 and later, FP8 on MI300. Accumulation stays f32; storage is 16
bit. bf16 keeps f32 range with short mantissa (training-safe);
f16 has more precision but narrow range (needs loss scaling).

Software catch: WGSL-first paths (Burn default, WebGPU) do not reach
tensor cores; Burn needs the SPIR-V flag for f16 matmul. Full speed
needs CUDA/HIP WMMA or a library call (cuBLAS/cuDNN with f16/bf16).

Verdict for A7: no half types until CPU semantics exist. A7 has no
`f16`/`bf16` type, cast, printf, or const-fitting rule for them.
Adding GPU-only half types repeats the WebGPU trap: ops that test on
CPU cannot run. Prove f16/bf16 arithmetic, conversion, and printing
on CPU first; expose tensor-core speed only through library calls,
never as inline A7 assembly.

## 9. Multi-device and collective scope

NCCL scope: all-reduce, broadcast, reduce, all-gather, reduce-scatter
over explicit communicators and streams; every rank must call the same
collective with the same count and dtype or the job hangs. XLA and
PyTorch distribute call NCCL; they do not reimplement it. JAX adds GSPMD
sharding annotations so the compiler partitions the HLO.

Verdict for A7: out of scope until single-device is boring. No
communicator type, no rank/device mesh, no sharding annotations in V1.
If multi-GPU ever lands, it lands as bindings to NCCL/RCCL plus
explicit handles, following file 19's error-as-value rule. Implicit
distribution is never.

## 10. Ordering: what CPU-AI must prove first

1. CPU tensor ops correct: construction, broadcast, matmul, reduction,
   transpose, conv/pool forward on slices, with tests and no GPU.
2. Layout and dtype sound: contiguous/strided views, `usize` indices,
   f32/f64 exactness first; then f16/bf16 CPU semantics.
3. Handle contract in IR: device identity in effects, one-owner
   buffers, explicit copy, error-as-value, CPU fallback for each op.
4. One FFI backend: `std/gpu` thin binding (WebGPU portable, CUDA/HIP
   for speed) with vector-add then matmul verified, pinned by hash.
5. Only then: small codegen subset and library calls for matmul/conv.

Each gate blocks the next. Skipping to codegen or collectives with a
red CPU suite produces untestable speed.
