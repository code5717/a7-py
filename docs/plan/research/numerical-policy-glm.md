> **Source:** OpenCode zai-coding-plan/glm-5.3, numerical policy and memory-safety/security review.  
> **Session:** `opencode session ses_f5e785e0affeur2XQ9Cxc2wgdE`  
> **Date:** 2026-09-14. Recovered 2026-09-15 with opencode export after Plan Mode blocked the original write.  
> **Status:** Advisory. Final report text preserved verbatim; earlier progress messages omitted. User decisions are in the [ledger](../decisions.md).

# A7 v1 Numerical-Policy & Memory-Safety/Security Review — Final Advisory Report

- **Role:** external reviewer (numerical policy + sole owner of cybersecurity/memory-safety review), advisory to the controlling Codex session. Read-only research; no repository edits, no model CLIs launched, no tests executed by me. All A7 repo facts are from first-hand reads at the current working tree (audits baseline `701c679`).
- **Method:** first-hand reads of `README.md`, `docs/SPEC.md` (§9 AI section), `docs/SAFETY_CONTRACT.md`, `docs/SECURITY.md`, `docs/STATUS.md`, `docs/audits/2026-09-14/memory-safety-glm-review.md`, `docs/audits/2026-09-14/security-glm-review.md`, `docs/audits/2026-09-14/audit-matrix.md`, `docs/lang-safety/{parameter-modes,edge-cases/06,11,12}`. External claims below are marked **[V]** (verified from fetched official source/version cited), **[I]** (inference from verified facts, not itself verified), or **[P]** (proposed A7 contract). **I did not run any tests; nothing here claims test execution.**

---

## 1. User approval decisions registered (as given)

| Topic | Status |
|---|---|
| A7-owned tensor + autodiff runtime, native numerical kernels, CPU first | Approved |
| Classifier + small decoder-transformer training & inference | Approved |
| f16/bf16/f32/f64 | Approved |
| Immutable argument bindings, explicit mutation permission for referenced data | Approved |
| IEEE NaN/Inf vs finite-only | **Not approved** — treat as open; default below preserves IEEE until decided |
| Ordinary wrapping arithmetic must never silently authorize wrapped allocation byte counts | Constraint (restated as hard requirement R-1) |

## 2. Verified primary-source findings

### 2.1 Mixed precision, accumulation, master weights, loss scaling, nonfinite recovery

- **[V] PyTorch autocast op policy (docs 2.14, `amp.html`):** CUDA fp16 autocast for matmul/conv/linear; **fp32 forced for reductions, losses, norms, softmax, exp/log/pow** (`sum`, `softmax`, `layer_norm`, `log_softmax`, losses…); widest-input promotion for others. CPU bf16 autocast for `mm/bmm/conv/linear/matmul/scaled_dot_product_attention`; fp32 for losses/FFT/linalg. **In-place and `out=` variants are not autocast-eligible.** bf16 CPU training uses autocast only, no GradScaler.
- **[V] PyTorch GradScaler (source `torch/amp/grad_scaler.py` @ v2.14.0):** defaults `init_scale=2^16`, `growth_factor=2.0`, `backoff_factor=0.5`, `growth_interval=2000`. Flow: `scale(loss)→backward`; `unscale_` computes `inv_scale = scale.double().reciprocal().float()` (reciprocal in FP64 for precision), then one fused kernel `torch._amp_foreach_non_finite_check_and_unscale_` both **detects inf/NaN and unscales** producing `found_inf`; `step` runs `optimizer.step()` **only if `sum(found_inf)==0`, else skips entirely**; `update` calls `torch._amp_update_scale_` (backoff on skip, growth after 2000 consecutive clean steps). Unscaling fp16 grads raises `ValueError("Attempting to unscale FP16 gradients.")` — **master gradients must be f32**. Sparse fp16 grads are coalesced because coalescing can overflow. The docs warn the scale is **not guaranteed ≥1** (bf16-pretrained models can be fp16-incompatible; fp16 max 65504).
- **[V] TensorFlow/Keras (mixed_precision guide, accessed 2026-09-14):** `mixed_float16` policy = fp16 compute + **fp32 variable dtype (master weights)**; final softmax/outputs must be fp32; `LossScaleOptimizer.apply_gradients` **skips the step if grads contain Inf/NaN and halves the scale**, growing it otherwise; first steps skipped during calibration is expected; `mixed_bfloat16` needs **no loss scaling** (same exponent range as f32). fp16 overflow >65504, underflow < ~6e-8.
- **[V] oneDNN bf16 training (v3.14 dev guide):** bf16 supported for src/weights; **destination may be bf16 or f32**; documented workflow is "maintain a master copy of all the weights, computing weights gradients in f32 and converting to bf16 afterwards." Attributes exist for floating-point math mode, accumulation mode, rounding, determinism (TOC-verified; details unverified).
- **[V] PyTorch autograd NaN semantics (autograd mechanics, 2.14):** NaN input is outside the domain; "an autograd formula may return any gradient at such an input and does not need to propagate the NaN… for performance reasons, some functions will use other values (`log(-1)`)." Division-by-zero: forward is IEEE `inf`, but backward through `x/0` yields **NaN grads even when the output was masked before the loss**; fix is masking *before* division. Multithreaded backward with shared inputs is documented non-deterministic (`.grad` races, Hogwild).
- **[V] safetensors format (README @ main):** "Tensor values are not checked against, in particular NaN and +/-Inf could be in the file." Checkpoints are an **untrusted-value** boundary, not just an untrusted-code boundary.

### 2.2 Alias/view lifetimes and in-place autodiff

- **[V] PyTorch:** every tensor has a **version counter** incremented on any in-place mark-dirty; saved tensors store the version and **error on mismatch** at backward ("one of the variables needed… modified by an inplace operation"). In-place ops additionally error if the modified storage is referenced by other tensors; autograd must rewrite the graph for in-place ops (documented cost). Saved tensors may be packed/unpacked to different tensor objects **sharing storage** — aliasing is storage-level. [V] MLX 0.32.2: lazy graph, `eval()`/`async_eval`, streams; arrays are graph handles.

### 2.3 Immutable arguments vs effect/exclusivity semantics

- **[V] Swift SE-0176 (implemented Swift 4.0):** Law of Exclusivity — two accesses to the same variable may not overlap unless both are reads. **Static enforcement** for locals/`inout`/struct properties; **dynamic runtime access-tracking** for class properties/globals/escaping closures; **no enforcement** for unsafe pointers or immutable memory. Array element mutation is whole-array exclusive access (hence `swapAt`); escaping into closures forces dynamic checks. Motivation is exactly optimizer validity (noalias, COW uniqueness hoisting) — the same property a tensor runtime needs to hand native kernels non-aliasing buffers.
- **[V] A7 planned model (docs/lang-safety/parameter-modes.md, research):** borrow/inout/consume, call-site exclusivity (`f(a,a)` with two inout rejected), no storable refs in v1, channels + owned data across tasks. Consistent with SE-0176's static variant; runtime (dynamic) enforcement is not planned — acceptable only if no storable mutable aliases exist.

### 2.4 Native ABI/library boundary: sizes, alignment, ownership, threading

- **[V] oneDNN v3.14:** memory objects wrap a user `void*` (or library-allocated) plus dims/dtype/format. **Scratchpad:** two modes. Default `library` mode with `ONEDNN_ENABLE_CONCURRENT_EXEC=OFF`: one **global shared scratchpad**; primitives may be created/executed in parallel **but executing a primitive in a different thread than creation results in segmentation fault**; `=ON`: per-primitive private scratchpad, cross-thread exec OK, different primitives concurrently OK, **same primitive concurrently returns incorrect results**. "Primitives are not thread-safe by default"; only `scratchpad_mode::user` (caller-provided, per-execution, distinct for concurrent executions) is fully safe. Scratchpad ≠ workspace (workspace persists between forward/backward, training only). Sizes: im2col scratch ∝ source image × weights spatial size; reduction scratch ∝ reduced tensor size × thread count. Query sizes via `scratchpad_desc().get_size()` — never compute them yourself. User scratchpad must be on the same engine. [V] Alignment: official getting-started text states memory passed into oneDNN "should have good alignment for better performance" (no hard ABI minimum published — treat 64B as A7's contract, not oneDNN's).
- **[V] OpenBLAS (FAQ, openmathlib docs):** for multi-threaded host apps, set `OPENBLAS_NUM_THREADS=1` / `openblas_set_num_threads(1)`; **single-threaded builds (`USE_THREAD=0`) still race under concurrent calls unless `USE_LOCKING=1`** (added 0.3.7); calling pthreads-built OpenBLAS inside OpenMP regions can **deadlock** unless built `USE_OPENMP=1`; internal buffer pool is `NUM_BUFFERS = MAX_CPU_NUMBER*2`, sized **at build time** — exceeding it terminates the program ("Program is Terminated. Because you tried to allocate too many memory regions"); thread count support is compiled-in and does not grow on bigger machines; `USE64BITINT` is a build setting discoverable via `openblas_get_config()`; F2C complex return convention is an ABI trap; affinity pinning needs `OPENBLAS_MAIN_FREE=1` to avoid interfering with the host.
- **[V] ONNX Runtime (C get-started docs):** each session owns threadpools by default (opt-in global shared pools via `CreateEnvWithGlobalThreadPools` + `DisablePerSessionThreads`); CPU allocator is a **BFCArena that never returns memory to the system** (opt-in shrinkage per Run; configurable `max_mem`, extend strategy, chunk sizing); shared-allocator and shared-initializer APIs exist for multi-session processes. Lesson: arena growth policy is a security-relevant resource-exhaustion knob A7 must expose deliberately.

### 2.5 Shape/byte-count integer overflow under wrapping arithmetic

- **[V] PyTorch v2.14.0 `aten/src/ATen/EmptyTensor.cpp`:** `computeStorageNbytesContiguous` performs **checked** u64 multiply of all dims → add storage_offset → multiply itemsize → compare against `storage_max() = min(INT64_MAX, SIZE_MAX)`; any overflow ⇒ `TORCH_CHECK` failure ("Storage size calculation overflowed with sizes=…"). Strided variant computes last-element offset with per-dim `mul_overflows/add_overflows`. **Mobile builds compile the checks out** (`#ifndef C10_MOBILE`) and fall back to wrapping math — a live demonstration of exactly the hazard A7 must never have. Sizes are also checked non-negative first. The runtime error is well-known from real workloads (GitHub issues #107552, #139181).
- **[V]** PyTorch sizes/strides live in int64 (`torch.Size`, SymInt) with the min(int64,size_t) ceiling above; **[I]** A7 `usize` (64-bit) arithmetic matches this on 64-bit targets, but A7's *proof-disabled* ordinary ops (MS-10) currently wrap silently under `-OReleaseFast` (verified by the memory-safety audit), so an A7-computed `numel*itemsize` can wrap today with no diagnostic.

### 2.6 Allocation failures and cleanup

- **[V] A7 today:** `new T` lowers to `allocator.create(T) catch null` (page_allocator) and callers must nil-guard; no general bounds-check insertion; `del` does not null; alias/defer double-del accepted (MS-3/MS-4/MS-5). **[V]** PyTorch CPU allocation raises `std::bad_alloc`/TORCH_CHECK errors rather than returning wrapped sizes; ONNX arena errors when `max_mem` exhausted. **[P]** A7 tensor allocation must surface failure as a typed error (Result/optional), never abort, never return a wrapped byte count.

### 2.7 Checkpoint deserialization / loaders / path trust boundaries

- **[V] CVE-2019-6446 (NumPy <1.16.3):** `np.load` pickle RCE; fixed by `allow_pickle=False` default.
- **[V] CVE-2025-32434 (PyTorch ≤2.5.1):** RCE via `torch.load(..., weights_only=True)` — the *safe* mode itself; patched 2.6.0. **[V] CVE-2026-24747 / GHSA-63cw-57p8-fm3p (PyTorch <2.10.0):** heap-corruption bypass of the `weights_only` restricted unpickler from a crafted `.pth`. **Two successive escapes of an allowlist unpickler** ⇒ any pickle-shaped A7 checkpoint format is disqualified by evidence, not preference.
- **[V] safetensors (README):** 8-byte little-endian header length; JSON header (dtype/shape/data_offsets); **header capped at 100MB**; buffer must be **fully indexed, no holes, no overlapping ranges** ("prevents the creation of polyglot files"); zero-copy mmap; no arbitrary code; explicit DoS-resistance rationale ("you should never exceed the size of the file in memory"). Also [V]: protobuf/ONNX flagged "hard 2GB max", npz zip-bomb DoS.
- **[V] A7 today:** module import paths already enforce containment (reject absolute, `..`, backslash, NUL; symlink escape refused; `verify_release_manifest.py`/`verify_archive_contents.py` encode the same discipline for release archives) — this machinery is the right pattern to extend to data loaders.

### 2.8 Compiler transformations invalidating safety facts

- **[V] A7 today:** constant folding after safety planning replaces nodes; `BackendPlan` approvals keyed by `id(node)` with **no liveness/versioning guard** (audit LH-1, currently latent); dead `GenericMonomorphizer` would bypass proofs if wired in post-safety (LH-2). **[V] PyTorch:** `torch.compile` changes autograd semantics (2.14 amp warning: `backward_pass_autocast` default assumes backward runs under forward's autocast — users must set it `off` for the recommended pattern), i.e., *even PyTorch's compiler changes float/autodiff semantics unless configured* — A7's tensor IR must be required to preserve declared float semantics across every transform. **[V] OpenBLAS FAQ:** FMA/vectorization/reassociation changes LAPACK-test numerics (documented small error drift) — reassociation is not semantics-free.

### 2.9 Async lifetime / resource handling

- **[V] JAX (async dispatch note):** dispatch returns futures; host reads/`block_until_ready()` force completion; benchmarks that skip blocking are wrong. **[V] MLX:** lazy graph, explicit `eval`. **[V] oneDNN/OpenBLAS/ORT:** on CPU the real async hazards are threadpool interactions (creation-thread affinity segfaults, concurrent-exec wrong results, deadlocks with OpenMP, build-time thread ceilings, arenas that never shrink). **[I]** For CPU-first A7 v1, "async" reduces to (a) internal library threading and (b) avoiding hidden futures; an explicit future type can be added later without breaking a synchronous core.

---

## 3. Numerical policy recommendation (primary + alternatives)

**Recommendation N-1 (dtype split):** storage/activation dtypes f16/bf16/f32/f64; **all reductions, softmax, norms, losses accumulate in f32 minimum** (f64 accumulation only for f64 models); matmul/conv take f16/bf16 inputs with f32 accumulation where the kernel provides it (oneDNN fpmath mode). Softmax/final outputs f32 (TF/PyTorch-verified practice).

**Recommendation N-2 (master weights):** trainable parameters are **f32 master copies**; reduced-precision compute weights are derived casts; gradients land in f32 (PyTorch rejects unscaled fp16 grads; TF variable_dtype=f32; oneDNN documents the same workflow). This is the unanimous cross-framework position — no alternative should ship for the approved transformer/classifier scope.

**Recommendation N-3 (loss scaling only for f16):**
- bf16: **no loss scaling** (f32 exponent range; TF and PyTorch agree).
- f16: dynamic scaling with exact GradScaler/LSO semantics: check nonfinite on **unscaled-in-place f32 grads via one fused scan** producing a `found_inf` flag; **skip the whole optimizer step** when set; multiply scale by backoff (0.5) on skip, growth (2.0) after 2000 clean steps; init 65536; reciprocal computed in f64 then f32. Persist scale + growth-tracker in checkpoints (GradScaler `state_dict` precedent).
- Nonfinite gradient "recovery" = step-skip + scale decay, **never** silent NaN-parameter writes. Policy for persistent nonfinites (N consecutive skips): configurable — abort with typed error by default, continue-with-warning opt-in.

**Recommendation N-4 (IEEE semantics, finite-only not adopted):** floats are IEEE-754 with NaN/±Inf representable and propagated by elementwise ops and reductions (`sum` propagates NaN; `nansum` is a distinct named op). **Autodiff must propagate NaN in gradients** (poison semantics): document that PyTorch does *not* guarantee this for NaN inputs (autograd mechanics, 2.14) and that A7 deliberately chooses the stricter, predictable contract; float→int casts of non-finite/out-of-range values are **checked errors** (lang-safety FF-05 direction), never Zig `@intFromFloat` UB. No fast-math/reassociation defaults: any reassociation (a la OpenBLAS FMA drift) must be opt-in and documented as changing results.

**Alternatives (recorded):** (a) finite-only `Fin<F>` discipline — remains research (user not approved); incompatible with NaN-as-signal loss-scaling unless split into "compute float" vs "validated float" layers; revisit only for a safety-critical dialect. (b) static loss scale — rejected: known-worse underflow/overflow trade-off, all majors moved to dynamic. (c) f16 master weights — rejected: contradicts N-2 evidence.

---

## 4. Memory-safety & security requirements (advisory, numbered, testable)

**R-1 Allocation byte counts (hard, from the user's constraint).** Ordinary `+`,`-`,`*` results are **ineligible** as allocation sizes, tensor byte counts, strides×dims products, or native-library length arguments. A new safety-pass obligation (`alloc_size`) requires discharge only by: literals, or dedicated `checked_mul/checked_add` intrinsics returning optional/Result, computed in a width ≥ max(usize) with an explicit overflow flag and an upper bound `min(isize::MAX, i64::MAX)` (PyTorch `storage_max()` pattern). Wrapping ops (`wrap_*`, per lang-safety Gap 06) may never feed sizes. **Prerequisite:** MS-10 (overflow proofs disabled) and MS-1/MS-2 (unsound joins/call-effects) must be fixed first, otherwise "checked" results themselves rest on stale facts — the current engine would certify wrapped sizes.

**R-2 Shapes/dims validation.** Rank ≤ 8, dims ≥ 0 checked, numel and nbytes computed once via R-1 path and cached in the tensor header; every native call re-derives lengths from the header, never from user arithmetic. Runtime (dataset-driven) shapes get the same runtime checked path (dynamic check, clean error).

**R-3 Buffer ownership & ABI.** A7 owns all buffers (one allocator; foreign allocations cross only as opaque handles — lang-safety FFI Q12h direction). Every native boundary call carries `(ptr, byte_len, dtype, alignment_class)` validated against the memory descriptor; **alignment contract: ≥64B** for any externally passed buffer (oneDNN alignment guidance is advisory; A7 makes it binding). Scratchpad/workspace buffers are sized **exclusively from descriptor queries** (`scratchpad_desc().get_size()`), never computed in A7 arithmetic; workspace objects outlive fwd→bwd pairs.

**R-4 Threading contract.** v1: single A7 execution thread. Native libs configured: oneDNN default library-scratchpad mode is acceptable **only** with create/execute on the same thread (verified segfault otherwise), or `scratchpad_mode::user` with per-execution scratchpads; OpenBLAS pinned to 1 thread (`OPENBLAS_NUM_THREADS=1` / `openblas_set_num_threads(1)`) or `USE_THREAD=0 + USE_LOCKING=1`; never pthreads-OpenBLAS inside OpenMP regions (deadlock). Thread-count ceilings are **build-time in OpenBLAS** (`NUM_THREADS`) and its buffer pool aborts when exceeded — A7 must query (`openblas_get_config()`/`openblas_get_parallel()`) and pin a build with adequate `NUM_THREADS`, and document the termination failure mode. `USE64BITINT` build required for >2³¹-element BLAS operands (verified setting name; A7 should also bound matmul operand byte sizes below the int32-indexing limit unless the 64-bit-int build is confirmed). Env-var threading overrides are process-global untrusted inputs — A7 sets them explicitly at runtime init.

**R-5 Views/aliasing/in-place.** v1 mirrors the approved immutable-args model: tensor arguments are borrow-mode (read-only); mutation (in-place ops, optimizer updates) requires explicit `inout` permission with **static call-site exclusivity** (SE-0176/Hylo/A7 parameter-modes convergence); **no storable mutable views** — view/borrow objects live only in expression/call scope, so no dangling-storage state is expressible. If/when saved-for-backward tensors alias parameters, add a version-counter check at backward (PyTorch-verified mechanism) and treat violation as a typed error. Optimizer update runs in a no-grad/inference-mode analog (out-of-autograd mutation permission).

**R-6 Checkpoint format.** safetensors-derived: fixed-size little-endian header length; JSON header with dtype/shape/offsets; **header cap (≤100MB), no overlap, no holes, offsets+size ≤ file size**, total ≤ configured budget; mmap zero-copy; **no code, no object graph, no allowlist unpickler at all** (two PyTorch CVEs prove allowlists keep failing). Shapes pass R-1/R-2 validation at load. Loading errors are typed, bounded-work, and never hang (bounded header parse, no recursion — matches A7's recursion ban). NaN/Inf values are expected and unvalidated by the format; sanitize at use-sites if a consumer requires finite values.

**R-7 Loader/path trust boundary.** Data paths obey the existing module-resolver containment rules (reject absolute, `..`, backslash, NUL, symlink escape from configured roots); archive/manifest discipline from `verify_archive_contents.py` (traversal/absolute/link/device rejection) extends to dataset archives. Dataset-controlled integers (labels, indices, sequence lengths) are untrusted and bounds/dtype-checked before touching tensor sizes.

**R-8 Allocation failure.** All tensor allocations return `Result`/optional; `nil`-checks are enforced pre-deref (existing contract); OOM mid-training must leave a clean error, run `defer` cleanups, and not corrupt state; recovery (retry smaller batch) is a caller decision. The audit's MS-3/4/5 (double-del, del-of-ref-param) must be closed before tensor buffers become `del`-able objects, or tensors use runtime-managed arenas (ORT-style) with explicit shrink control and a documented never-shrinks-by-default posture.

**R-9 Compiler-transform invariance.** Any tensor pass (fusion, layout, folding, autodiff graph build) must (a) re-validate index/size obligations on the post-transform node (fixes LH-1 class hazards: approval keys must be versioned, not raw `id()`), (b) preserve declared float semantics (no reassociation, no NaN-elision, no finite-assumption), (c) keep the backward pass **iterative** (worklist/topological — consistent with A7's recursion ban; PyTorch's engine is itself a heap-driven graph walk).

**R-10 Async discipline.** v1 semantics synchronous: every op returns only when its native call returned; no hidden futures (JAX's `block_until_ready` shows silent async corrupts benchmark/measurement reasoning). If async arrives later: explicit future type, ownership move across the await point, borrows may not cross it, and `block_until_ready`-equivalent required before host reads.

**R-11 Release profile.** Until MS-1..MS-9 closure, tensor-runtime binaries should build `-OReleaseSafe` (audit decision 9); ReleaseFast removes every Zig backstop the R-1/R-2 runtime checks would otherwise lean on during bring-up.

**R-12 Provenance/supply chain.** Native kernel libraries (oneDNN/OpenBLAS) are new dependencies: pin versions + hashes (Zig-toolchain precedent), record `openblas_get_config()`/oneDNN version in runtime `doctor` output, and add them to the (currently broken, SEC-2) dependency-audit gate once it audits the right environment.

## 5. Existing A7 conflict points (must be resolved, not papered over)

1. **SPEC §9 is a feature list, not a contract**: `tensor_view`/`tensor_flatten` "share memory" with no aliasing policy; `tensor_load` with no trust model; `@parallel`/`@vectorize`/`@prefetch` with no threading contract; GPU movement; `eig/svd/inv` with no failure semantics. Rewrite §9 as dtype/aliasing/overflow/trust contracts before implementation (drift is a documented bug class, AGENTS.md).
2. **Safety-fact engine unsound (MS-1/MS-2)** — directly undermines R-1's "checked" discharge; prerequisite, not parallel work.
3. **Overflow proofs disabled (MS-10)** — today's ordinary ops wrap under ReleaseFast; R-1 cannot exist as a *proof* until the arithmetic contract lands (typed-arithmetic Gap 06 decision).
4. **Immutable-args approved vs current unchecked `ref` mutation**: no call-effect invalidation, `del` through `ref` param frees caller storage (MS-2/MS-5) — the tensor runtime's borrow/inout surface is fiction until parameter-modes work is real.
5. **No heap buffer allocation story**: `new [N]T` rejected pending design; tensors need a runtime-owned buffer path — decide language surface vs runtime-internal allocator explicitly.
6. **FFI gap 12 is trust-based**: the numerical-kernel boundary will be A7's *first real FFI*; it must carry machine-checked size/dtype/alignment/threading contracts (R-3/R-4), not just `Result` returns.
7. **`del`/lifetime defects (MS-3/4/8/9)** apply to any tensor handle implemented as a del-able ref; arena ownership (R-8) avoids the class.
8. **SEC-1..SEC-4 delivery-boundary findings** (preview traversal, pip-audit wrong target, mutable action tag, unpinned uv) remain open and now guard releases that would ship native libraries.

## 6. Recommended A7 threat model (tensor runtime)

- **Assets:** host process memory/integrity; training results (weights); developer credentials reachable from files; release artifact integrity.
- **Trusted:** A7 source author; compiled program (documented non-sandbox, per `docs/SECURITY.md` — retained standing framing; no new sandbox claim invented).
- **Untrusted inputs:** checkpoint files (crafted bytes), dataset files/archives/paths, dataset-derived shapes/indices/labels, threading-related environment variables, mismatched native-library versions/ABIs at load time.
- **Boundaries:** (B1) deserializer bytes→tensors; (B2) path resolver → filesystem; (B3) A7→native-kernel call shim; (B4) shape/size planner → allocator; (B5) compiler tensor transforms → safety facts.
- **Top risks mapped to requirements:** crafted checkpoint RCE/heap corruption (B1→R-6, evidence: CVE-2025-32434, CVE-2026-24747); wrapped-size heap overflow (B4→R-1/R-2, evidence: PyTorch mobile-checked-out pattern); scratchpad/thread misuse → wrong results or segfault (B3→R-3/R-4, evidence: oneDNN/OpenBLAS docs); loader path escape (B2→R-7); stale-fact certification (B5→R-9, evidence: MS-1/MS-2, LH-1); resource exhaustion via huge shapes/zip bombs/arena growth (B1/B4→R-2/R-6/R-8).

## 7. Validation matrix (meaningful tests; no mocks-only qualification)

| ID | Requirement | Test (real pipeline, debug + release profiles) | Pass criterion |
|---|---|---|---|
| V-1 | R-1 static | A7 program computing size via ordinary `*` from literals ≥ overflow bound → compile | Rejected with alloc-size diagnostic; never a wrapped-size alloc |
| V-2 | R-1/R-2 dynamic | Dataset-driven dims product > i64::MAX through runtime loader | Typed error; no allocation, no abort; process continues |
| V-3 | R-2 | Strided subview bytes vs PyTorch-computed reference across 50 shapes incl. 0-dim/degenerate | Exact byte-length equality |
| V-4 | N-1/N-2 | Classifier + decoder-transformer trained f32, f16+scaling, bf16 | Loss curves within tolerance vs f64 reference run; **independent gradient reference**: finite-difference checks on 20+ ops (f64 central differences) AND cross-check vs NumPy f64 hand-built backward for the whole model |
| V-5 | N-3 | Inject Inf into one grad tensor each N steps | Step skipped, scale halved, weights bit-identical to pre-step; after injection stops, training converges (recovery ≤ growth-interval steps); consecutive-skip cap fires typed error |
| V-6 | N-4 | NaN input propagation suite: `log(-1)`, `0/0`, masked division | NaN reaches loss and grads (poison rule); masked-before-division yields clean grads (PyTorch's documented pitfall does not recur); float→int cast of NaN/Inf rejected |
| V-7 | R-5 | `f(t, t)` with two inout tensor args; mutate borrowed tensor | Compile-time rejection; borrow-read succeeds |
| V-8 | R-3/R-4 | Same primitive executed from two threads (TSan build); misaligned buffer; undersized user scratchpad | Rejected/queued, never wrong results; misalignment rejected at shim; scratchpad size from descriptor only |
| V-9 | R-6 | Fuzz corpus over checkpoint bytes (truncated, overlapped offsets, holes, 1GB header claim, giant dims, NaN payloads) under ASan + timeout | Clean typed errors, bounded memory/time, no crash/hang; valid file with NaN/Inf values loads and is usable |
| V-10 | R-7 | Loader with `..`, absolute, symlink-escape, NUL paths; archive traversal/zip bomb | All rejected; bomb bounded by declared budget |
| V-11 | R-8 | Allocation failure injection at each call site mid-training | Clean error path, `defer` cleanup runs, heap stays consistent (ASan clean), process exits typed |
| V-12 | R-9 | Metamorphic compiler suite: fused vs unfused, folded vs unfolded float graphs | Bit-identical or documented-tolerance results; approvals re-validated post-transform (red test if `id()` reuse reintroduced) |
| V-13 | R-10 | Timing of ops vs manual `block_until_ready` analog | No hidden latency; documented sync points |
| V-14 | Full-process recovery | End-to-end: corrupt checkpoint mid-training → reload good checkpoint → training continues; OOM → smaller batch retry continues | No restart required; no leaked memory (RSS before/after within bound) |
| V-15 | Differential profiles | Whole V-4..V-14 suite in debug and ReleaseSafe (ReleaseFast only after MS closure) | Zero behavior difference |

Suite hygiene per repo AGENTS.md: visible red regressions (no xfail), every case tied to a requirement above, mocks only at the native-shim boundary with the unverified remainder stated.

## 8. Limitations

- Read-only research; **no tests were run and none are claimed**. All external facts come from the cited fetched documents/sources at the versions cited (accessed 2026-09-14): PyTorch 2.14 docs + v2.14.0 sources (`amp.html`, autograd mechanics, `torch/amp/grad_scaler.py`, `aten/src/ATen/EmptyTensor.cpp`), TensorFlow mixed-precision guide (current site), oneDNN v3.14 docs (uxlfoundation), ONNX Runtime docs (current site), OpenBLAS FAQ (openmathlib, rev. 2024-12/2026-07), safetensors README @ main, Swift SE-0176, MLX 0.32.2 docs, JAX async-dispatch note, NVD/GHSA/CVE records for CVE-2019-6446, CVE-2025-32434, CVE-2026-24747.
- Not verified (marked [I] where used): oneDNN fpmath/accumulation-mode attribute details (only their existence), OpenBLAS int32 GEMM operand ceilings (only that `USE64BITINT` exists), tinygrad/StableHLO specifics (dropped), NumPy view/base internals (replaced by PyTorch storage-level aliasing evidence), torch.compile guard internals.
- Numerical tolerances in V-4 need pinning to concrete dtypes/models by the design session; threat model excludes the documented non-sandbox stance for compiled programs.
- A7-side facts reflect the audited revision `701c679` plus current docs; any post-audit compiler changes may have closed individual MS items — re-verify prerequisites (MS-1/MS-2/MS-10) before implementing R-1.

**Bottom line:** adopt IEEE-with-poisoning semantics + f32 master weights/accumulation + bf16-unscaled/f16-dynamic-scaled training with skip-on-nonfinite recovery; make checked, proof-discharged allocation arithmetic the single path from shapes to bytes; own every buffer behind size/dtype/alignment/threading-validated shims; ship a safetensors-style, no-code checkpoint format with bounded parsing; and treat the fact-engine soundness fixes as hard prerequisites — the two PyTorch weights_only CVEs and PyTorch's own mobile-checked-out overflow path are the cautionary evidence that each of these boundaries fails exactly where someone earlier declared it "handled."