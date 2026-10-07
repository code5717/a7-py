# 21. Small languages and GPUs: how they reach accelerators

Scope: Nim, Odin, Jai, Hare, V, Roc, Futhark, Mojo, Bend, Gleam. Question: what is the cheapest credible GPU path for A7, a Python compiler that emits Zig source and builds with the host Zig toolchain (`docs/ARCHITECTURE.md`).

## The short answer

No small language in this set compiles its own general-purpose GPU kernels from scratch and wins. The ones with a real GPU story do one of three things: (1) call C-level runtime APIs through FFI, (2) emit an existing shading/compute language (WGSL, GLSL, CUDA C) as strings, or (3) restrict the language so far that mapping to GPU threads is trivial. A7 should do (1) then (2), in that order, and skip (3).

## What each language actually does

### Nim: library FFI plus generated kernels. Verdict: closest model for A7.
Arraymancer wraps CUDA and OpenCL through Nim's C FFI (`nimcuda`, `nimcl` bindings), and generates small CUDA kernels from templates at compile time with macros. CPU fallback uses OpenMP. Lesson: the stdlib carries the GPU weight, not the compiler. Dead end: Arraymancer's CUDA backend bit-rotted when it tracked old CUDA compute capabilities and old Nim versions; one maintainer, two vendor APIs, constant churn. Takeaway for A7: bind one API, generate kernels as text, keep CPU fallback mandatory.

### Odin: vendor bindings to C graphics libraries. Verdict: copy this first.
Odin ships `vendor:` bindings for OpenGL, Vulkan, DirectX, plus community Sokol and raylib wrappers. There is no Odin GPU compiler. Users write shaders in GLSL/HLSL and call them from Odin. Lesson: for a Zig-backed language this is nearly free, because Zig already links C the same way (`@cImport`, `zig-gamedev/zgpu`, mach Dawn bindings). Takeaway: A7 Stage 1 is just extern declarations plus a build-system story.

### V: same pattern, thinner. Verdict: cautionary.
V's `gg`/`sokol` modules wrap Sokol for 2D graphics; `vcl` wraps OpenCL for compute. Both are thin wrappers maintained outside the core compiler. Lesson: thin wrappers work for demos but V's churn (rewrites of `gg`, Sokol-version skew) shows the cost lives in pinning third-party native deps, not in language design.

### Jai, Hare: no GPU story. Verdict: explicit non-goal.
Jai (closed beta, game-focused) does GPU the C way: call DirectX/Vulkan from Jai code, write shaders separately. No kernel language. Hare has no GPU bindings and no plan; its minimal runtime and OS focus point away from accelerators. Lesson: two competent systems languages decided GPU codegen is out of scope. That is a valid choice and sets the floor: FFI-only is respectable.

### Roc: platforms, no GPU. Verdict: not applicable yet.
Roc's platform/effect model could host a GPU platform the way it hosts CLI or web platforms, but no such platform ships. The interesting bit is the design: GPU access would be an effect with a host implementation in another language. A7 could imitate the shape (a `std/gpu` module backed by host Zig/C code) without adopting Roc's effect system.

### Gleam: no GPU story. Verdict: not applicable.
Gleam targets Erlang VM and JavaScript. GPU access means calling out to NIFs or JS WebGPU bindings. Lesson for A7: none, except that VM-hosted languages pay a boundary-crossing cost A7 avoids by emitting Zig.

### Futhark: a whole compiler that IS the GPU backend. Verdict: do not imitate.
Futhark is a purely functional data-parallel array language; `map`/`reduce`/`scan` compile to OpenCL/CUDA with fusion, tiling, and flattening of nested parallelism (diku-dk/futhark, futhark-lang.org). It is fast and well published. But it works because the language is restricted: no aliasing, no arbitrary recursion, whole-program second-order array combinators. A7 is an imperative Zig-shaped language; bolting Futhark semantics on would fork the language. Read Futhark papers for optimizer ideas, not for architecture.

### Mojo: new MLIR stack with vendor money. Verdict: admire, do not chase.
Mojo (Modular) lowers Python-shaped syntax through MLIR to CPU/GPU/ASIC targets, with a MAX runtime for device management and tensor ops (mojolang.org). This is the "real" answer: own the compiler stack down to the accelerator. Cost: a compiler team plus hardware partners. A7 cannot pay it. Lesson that transfers: separate kernel code from serving code; Mojo writes kernels, MAX schedules them. A7 can copy the split at small scale (kernels as WGSL text, host as Zig).

### Bend: whole program runs on GPU via interaction nets. Verdict: exciting, fragile.
Bend compiles a Python/Haskell-shaped language to HVM2 interaction nets that run on CUDA (bendlang/bend). Any parallelisable work spreads across GPU threads with no annotations. Early demos matched hand-written CUDA on some benchmarks. Dead ends so far: HVM2 runtime churn, memory-unification limits, few real programs shaped like interaction nets, project pivots. Lesson: implicit-everywhere parallelism pushes the hard problems (memory, divergence, debugging) into the runtime instead of removing them. A7 should demand explicit offload.

## Cross-cutting lessons

1. FFI to a C runtime beats owning a backend. Every survivor (Nim, Odin, V, Zig itself) starts here.
2. One API target, not three. CUDA-only strands non-NVIDIA users; CUDA+OpenCL+Metal triples maintenance. Small teams that picked WebGPU/WGSL (one source, Dawn/wgpu-native backends for D3D12/Metal/Vulkan) kept one code path.
3. Emit shader text, do not build a shader IR. GLSL/WGSL-as-string plus a foreign-function call outlives every custom codegen experiment at this scale.
4. CPU fallback is not optional. GPU-absent machines, CI runners, and driver skew make GPU-only examples untestable. Arraymancer and Futhark both kept CPU backends for this reason.
5. Pin native deps by hash. Odin, V, and Zig GPU projects all broke at different times on Sokol/Dawn/wgpu version drift. Vendored or hashed pins are the fix.

## Recommendation for A7, in stages

Stage 0 (now, no language change): document that GPU work goes through Zig/C interop. A7 already emits Zig; any C header Zig can import is reachable. No syntax, no stdlib.

Stage 1 (cheap, credible): `std/gpu` as a thin host binding over WebGPU via existing Zig libraries (zig-gamedev `zgpu` or mach Dawn bindings). A7 side is extern declarations plus buffer-submit-read helpers written in Zig, merged the way `std/io` and `std/math` already merge. Kernels stay hand-written WGSL strings. Ship one compute example (vector add, then matmul) verified on one backend. CPU fallback keeps the example suite green without a GPU.

Stage 2 (only if Stage 1 gets users): a small blessed subset, e.g. element-wise map/reduce over slices, that lowers to generated WGSL with a CPU-Zig fallback from the same source. Futhark-shaped but deliberately tiny; reject the rest with a clear error. This is the only custom codegen A7 should ever own.

Stage 3 (defer indefinitely): full kernel language, autotuner, multi-vendor backends, debugger/profiler integration. That is a second project wearing A7's name. Say no until Stages 1-2 saturate.

## What to avoid

- A CUDA-only path. Splits the user base and ties A7 to NVIDIA's toolchain.
- A custom GPU IR or MLIR dependency. Build cost and toolchain weight exceed A7's whole compiler.
- Bend-style implicit parallelism. Conflicts with A7's explicit.n safety model and makes safety claims untestable.
- Promising GPU execution in the language spec before Stage 1 ships. Spec promises outlive the volunteers who must keep drivers working.

## Verdicts, one line each

Nim: imitate (library-led FFI plus template kernels). Odin: imitate (vendor bindings first). V: imitate with tighter pins. Jai/Hare: follow their restraint (FFI-only is fine). Roc/Gleam: no transfer. Futhark: learn optimizer tricks, reject the language fork. Mojo: learn host/kernel split, reject the stack cost. Bend: watch, do not bet on. Cheapest credible A7 path: WebGPU binding in host Zig, WGSL-as-string, CPU fallback, one pinned example.
