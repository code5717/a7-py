> **Source:** Codex CLI external reviewer, AI framework and autodiff research.  
> **Session:** `codex rollout 2026-09-14T23-06-34 (01a0a187-4fde)`  
> **Date:** 2026-09-14. Recovered 2026-09-15 from temporary output after Plan Mode blocked the original write.  
> **Status:** Advisory. Body preserved verbatim except removal of pre-report narration where noted. User decisions are in the [ledger](../decisions.md).

# A7 v1 tensor and autodiff research review

## Executive recommendation

Proceed with the approved architecture: **A7 owns tensor semantics, automatic differentiation, optimizer state, RNG, and checkpoint behavior. Established libraries supply numerical kernels through a small native bridge.**

For CPU-first v1, I recommend:

- A synchronous tensor runtime with an eager reverse-mode tape.
- A portable reference path for every required operator and dtype.
- OpenBLAS or BLIS for qualified `f32` and `f64` matrix operations.
- Optional oneDNN acceleration for qualified neural-network operations.
- Explicit storage, computation, accumulation, and output precision.
- Functional tensor operations, with storage reuse permitted only when old values are no longer observable.
- Separate acceptance gates for training, checkpoint continuation, and packaged inference.

**My floating-point recommendation is IEEE values with strict scalar semantics, plus explicit numerical checks at training boundaries. This remains a proposal requiring user approval.** Finite-only behavior is possible, but it needs substantially more specification than banning NaN and infinity.

Do not make a framework binding the implementation of A7’s tensor or AD semantics. JAX, PyTorch, and TensorFlow are valuable design references and differential oracles. They are not interchangeable kernel libraries.

This review inspected repository sources and opened official documentation and source code. Three independent sub-agents covered JAX/TensorFlow, PyTorch/MLX/tinygrad, and numerical backends. No repository files were edited. No libraries were built, benchmarked, or runtime-qualified.

## 1. Repository findings and authority

The reviewed checkout identifies commit `701c67936c70ad2b0608326e23e56cc5d38c9fdb` and contains existing working-tree changes. Findings therefore describe the inspected files, not a clean release revision.

| Finding | Evidence | Planning consequence |
|---|---|---|
| AI facilities remain a design target | [SPEC section 9](/home/cx89/Projects/pl-dev/a7-py/docs/SPEC.md:1083) explicitly says tensors, AD-related operations, and GPU movement are unimplemented | Examples cannot serve as implementation evidence |
| Older roadmap excludes AI from v1 | [Completion roadmap](/home/cx89/Projects/pl-dev/a7-py/docs/audits/2026-09-14/completion-roadmap.md) | Superseded by the user’s approved training and inference scope |
| Numeric decisions retain rejected proposals | [Decisions document](/home/cx89/Projects/pl-dev/a7-py/docs/lang-safety/08-decisions.md:76) labels arbitrary-precision `int`, `uint`, and `number` accepted | Superseded by explicit-width integers and wrapping ordinary arithmetic |
| Parameter proposal allows exceptions to binding immutability | [D.040](/home/cx89/Projects/pl-dev/a7-py/docs/lang-safety/08-decisions.md:1494) says parameters are immutable unless declared with proposed modes | Rewrite around the approved distinction: bindings remain immutable; referenced-data mutation requires permission |
| Safety contract requires arithmetic range proofs | [Safety contract](/home/cx89/Projects/pl-dev/a7-py/docs/SAFETY_CONTRACT.md) | Ordinary wrapping `+`, `-`, and `*` need different obligations from allocation-size arithmetic and indexing |
| Existing constant folding uses host arithmetic | [Constant folding](/home/cx89/Projects/pl-dev/a7-py/a7/ast_preprocessor.py:590) | Target-format rounding and integer wrapping must be explicit |
| Prior audit records an exact integer folding failure | [Coordinator review R1](/home/cx89/Projects/pl-dev/a7-py/docs/audits/2026-09-14/root-review.md) | Existing compiler correctness work remains a prerequisite |

The decisions document also incorrectly describes Python `float` as arbitrary precision. Python documents ordinary floats as finite-precision binary floating point, typically binary64. [Python floating-point explanation](https://docs.python.org/3/tutorial/floatingpoint.html)

There is a concrete tensor-example error. Under the stated NumPy broadcasting rules, `[3,1,4] + [2,5,1]` is invalid because the leading dimensions conflict. To obtain `[3,2,5,4]`, compatible shapes include `[3,1,1,4]` and `[1,2,5,1]`. [NumPy broadcasting rules](https://numpy.org/doc/stable/user/basics.broadcasting.html)

The plan must also resolve:

- `flatten` cannot always promise a shared-memory view for arbitrary strides.
- `usize` strides cannot represent negative strides.
- `axis: -1` needs an axis convention distinct from element indices.
- Eigendecomposition, SVD, LU, and inverse are not dependencies of the two approved ML workloads.
- A tensor save/load API returning only a boolean cannot express the proposed recovery and compatibility behavior.

These are planning findings, not newly executed compiler tests.

## 2. What the compared systems actually provide

| System | Actual role | Useful to A7 | What it does not establish |
|---|---|---|---|
| JAX | Array programming, AD transformations, tracing, compilation | Functional semantics, JVP/VJP design, compiler comparisons | Strict arithmetic or universal backend equivalence |
| PyTorch | Tensor framework, eager AD, compilation, training ecosystem | Tape mechanics, mutation checks, AMP, workload references | A small independent kernel ABI |
| TensorFlow | Tensor runtime, tape AD, graph execution, training/export ecosystem | Tensor/variable separation, explicit errors, checkpoint state | A7 semantics or effortless native distribution |
| NumPy | Array library | Broadcasting, layouts, numerical comparisons | Training runtime or AD |
| SciPy | Scientific algorithms | Selected numerical oracles | Classifier/transformer runtime |
| MLX | Array/ML framework with transformations and lazy execution | Function-oriented gradients, evaluation boundaries | Merely an Apple-specific kernel library |
| tinygrad | Tensor framework, scheduler, compiler, runtime | Operator decomposition and implementation layering | Complete qualification for A7’s dtype/workload requirements |
| oneDNN | Optimized neural-network kernels and graph facilities | Convolution, matmul, related forward/backward operations | A7 AD or complete CPU `f64` support |
| OpenBLAS / BLIS | Dense numerical kernels | Matrix operations | Tensor semantics, optimizers, checkpoints |
| Eigen | C++ template numerical library | Selected routines and conversion references | A stable public C tensor ABI |
| ONNX Runtime | Model execution runtime | Independent exported-inference target | General replacement for A7 training semantics |
| StableHLO | Tensor compiler operation set | Future interchange/lowering | Runtime, numerical accuracy guarantee, or A7 error model |
| XLA | Optimizing tensor compiler | Future optimization backend | A small kernel dependency |

The implementation boundaries are documented in the official [JAX sources](https://raw.githubusercontent.com/jax-ml/jax/main/jax/_src/dtypes.py), [PyTorch AD documentation](https://docs.pytorch.org/docs/2.14/notes/autograd.html), [TensorFlow tensor guide](https://www.tensorflow.org/guide/tensor), [tinygrad architecture](https://docs.tinygrad.org/developer/developer/), [oneDNN repository](https://github.com/uxlfoundation/oneDNN), and [XLA overview](https://openxla.org/xla).

## 3. Framework findings

### JAX

**Findings.** JAX implements its own promotion rules, including weak scalar types. Its default configuration selects `f32`; explicit `f64` requests can be canonicalized to `f32` when 64-bit support is disabled. Its promotion lattice treats `f16` and `bf16` as distinct branches meeting at `f32`. [Dtype source](https://raw.githubusercontent.com/jax-ml/jax/main/jax/_src/dtypes.py), [promotion design](https://docs.jax.dev/en/latest/jep/9407-type-promotion.html)

Immutable arrays support functional updates. Compilation can reuse storage when the original value is dead. Explicit buffer donation additionally permits reuse across a call boundary while forbidding subsequent use of the donated input. [Array behavior](https://docs.jax.dev/en/latest/notebooks/Common_Gotchas_in_JAX.html), [buffer donation](https://docs.jax.dev/en/latest/buffer_donation.html)

JAX provides strong evidence that IEEE representation does not imply strict expression evaluation. Its FAQ demonstrates eager `exp(100)/exp(100)` producing NaN, while JIT compilation simplifies the expression to `1.0`. This is a documented example, not a result measured here. [JAX numerical FAQ](https://docs.jax.dev/en/latest/faq.html)

AD and compilation impose different control-flow restrictions. Structured `cond` and `scan` support differentiation. Dynamic `while_loop` supports forward-mode differentiation. `fori_loop` supports reverse mode when a static trip count permits lowering through `scan`. [Control flow](https://docs.jax.dev/en/latest/control-flow.html), [fori_loop](https://docs.jax.dev/en/latest/_autosummary/jax.lax.fori_loop.html)

A custom VJP does not automatically support JVP: JAX explicitly disallows forward-mode differentiation through `custom_vjp`. Activation checkpointing controls saved residuals and recomputation. [Custom VJP](https://docs.jax.dev/en/latest/_autosummary/jax.custom_vjp.html), [checkpointing](https://docs.jax.dev/en/latest/gradient-checkpointing.html)

JAX also separates dot-product precision controls from output dtype. Without an explicit algorithm, preferred element type is not an unconditional accumulation guarantee. Dispatch may be asynchronous, and optional `checkify` checks return error information. [Dot API](https://docs.jax.dev/en/latest/_autosummary/jax.lax.dot.html), [asynchronous dispatch](https://docs.jax.dev/en/latest/async_dispatch.html), [checkify](https://docs.jax.dev/en/latest/_autosummary/jax.experimental.checkify.checkify.html)

**Recommendation for A7.** Adopt explicit transformations and functional updates as design precedents. Reject silent disabling of requested `f64`. Do not import tracing restrictions into ordinary A7 control flow merely because JAX has them.

### PyTorch

**Findings.** Promotion depends on dtype category, scalar status, and tensor dimensionality. An integer scalar and an integer tensor can affect promotion differently. Integer-to-floating promotion does not guarantee preservation of every integer. [Tensor attributes](https://docs.pytorch.org/docs/2.14/tensor_attributes.html)

The eager AD graph is rebuilt as execution proceeds. Backward operations retain required forward values. Saved tensor version checks detect mutations that invalidate those values. Masking an invalid result after division does not necessarily prevent an invalid backward computation. [Autograd mechanics](https://docs.pytorch.org/docs/2.14/notes/autograd.html)

Basic indexing returns views; advanced indexing returns copies. `reshape` may do either, and `contiguous` copies only when necessary. Functionalization can remove intermediate mutations while preserving observable behavior. [Tensor views](https://docs.pytorch.org/docs/2.14/tensor_view.html), [functionalization](https://docs.pytorch.org/docs/2.14/generated/torch.func.functionalize.html)

AMP uses per-operator policies. CPU examples use bf16, and current documentation also describes CPU f16 policies. This does not establish native execution speed on any particular CPU. In-place and explicit-output forms do not participate identically in autocasting. [AMP documentation](https://docs.pytorch.org/docs/2.14/amp.html)

The GradScaler source checks gradients for nonfinite values, skips affected optimizer updates, and maintains scale-growth state. Adam initializes moments with `zeros_like(parameter)`. Therefore, ordinary AMP does not universally imply separate `f32` master weights or `f32` moments. [GradScaler source](https://raw.githubusercontent.com/pytorch/pytorch/main/torch/amp/grad_scaler.py), [Adam source](https://raw.githubusercontent.com/pytorch/pytorch/main/torch/optim/adam.py)

Forward-mode operator coverage has limitations. Custom AD functions and activation checkpointing have additional contracts, including saved values, mutation declarations, and RNG replay. [JVP](https://docs.pytorch.org/docs/2.14/generated/torch.func.jvp.html), [extension guidance](https://docs.pytorch.org/docs/2.14/notes/extending.html), [activation checkpointing](https://docs.pytorch.org/docs/2.14/checkpoint.html)

**Recommendation for A7.** Adopt explicit saved-value lifetimes and mutation detection. Specify master-weight and optimizer precision directly. Use PyTorch as a matched-case oracle, never as the definition of A7 behavior.

### TensorFlow

**Findings.** TensorFlow separates immutable tensor values from mutable variables. Ordinary `tf.math.add` requires matching tensor dtypes and supports broadcasting. Experimental NumPy compatibility behavior is a separate facility. [Tensor guide](https://www.tensorflow.org/guide/tensor), [add API](https://www.tensorflow.org/api_docs/python/tf/math/add)

The mixed-precision guide distinguishes layer computation dtype from variable dtype. Its mixed-f16 policy retains `f32` variables, recommends `f32` output softmax, and uses loss scaling. Bf16 generally needs less scaling because of its wider exponent range, but it can still overflow. CPU speed depends on hardware. [Mixed precision](https://www.tensorflow.org/guide/mixed_precision)

Current Keras source checks gradients for finiteness. Its nonfinite branch reduces the dynamic scale without applying the inner optimizer. The source and older TensorFlow guide do not expose identical API generations, so their details should not be mixed indiscriminately. [LossScaleOptimizer source](https://raw.githubusercontent.com/keras-team/keras/master/keras/src/optimizers/loss_scale_optimizer.py)

`GradientTape` records executed operations. A normal gradient call releases tape resources; persistent tapes retain them. Unconnected gradients can be absent rather than numerically zero. `ForwardAccumulator` provides JVPs. [Autodiff guide](https://www.tensorflow.org/guide/autodiff), [forward mode](https://www.tensorflow.org/api_docs/python/tf/autodiff/ForwardAccumulator)

`tf.function` tracing and AutoGraph conversion distinguish tracing-time effects from graph execution. Recomputation reruns forward work during differentiation. [Function guide](https://www.tensorflow.org/guide/function), [recompute_grad](https://www.tensorflow.org/api_docs/python/tf/recompute_grad)

Optional numeric checking reports NaN/Inf with operation context. Deterministic execution requires controlled software, hardware, RNG, and data pipelines. Training checkpoints can include model, optimizer, step, and iterator state. [Numeric checking](https://www.tensorflow.org/api_docs/python/tf/debugging/enable_check_numerics), [determinism](https://www.tensorflow.org/api_docs/python/tf/config/experimental/enable_op_determinism), [checkpoints](https://www.tensorflow.org/guide/checkpoint)

**Recommendation for A7.** Adopt explicit tensor/state separation and structured diagnostics. Keep absent gradients distinct from zero gradients. Treat a training checkpoint as a complete continuation state.

### MLX and tinygrad

MLX provides composable gradient transformations and lazy evaluation. Evaluation boundaries affect when work, errors, and memory use become visible. Current installation documentation includes Linux CPU and CUDA packages, despite retaining some older macOS-only wording. Calling it Apple-only would be inaccurate. [Transformations](https://ml-explore.github.io/mlx/build/html/usage/function_transforms.html), [lazy evaluation](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html), [installation](https://ml-explore.github.io/mlx/build/html/install.html)

MLX also documents reduced-precision hardware paths for some nominally `f32` matrix operations and a control requesting full `f32` paths. This reinforces the need to specify computation separately from storage. [Numerical precision](https://ml-explore.github.io/mlx/build/html/usage/precision.html)

Tinygrad is useful for studying tensor decomposition, scheduling, lowering, and execution as separate layers. This review did not establish complete CPU mixed-precision, `f64`, mutation, or checkpoint guarantees. [Architecture](https://docs.tinygrad.org/developer/developer/), [operator implementation documentation](https://docs.tinygrad.org/tensor/ops/)

**Recommendation.** Study both. Neither should become an undeclared replacement for the A7-owned runtime.

## 4. Proposed floating contract

### IEEE versus finite-only

| Choice | Benefits | Required consequences |
|---|---|---|
| IEEE values with explicit checks | Matches established numerical formats; supports conventional diagnostics and intermediate overflow detection | Specify NaN, infinity, signed zero, subnormals, conversions, and operation-specific behavior |
| Finite-only values | Numerical failure becomes an explicit result rather than a special value | Check imports, casts, arithmetic, kernels, and intermediate results; specify recovery and overhead |
| Mixed policy by operation | Can accommodate strict application boundaries and numerical kernels | Requires clear boundaries so callers know which operations are fallible |

**Recommendation requiring approval:** use IEEE values, preserve strict scalar expression behavior, and provide explicit finite checks for training and application boundaries.

Finite inputs do not guarantee finite intermediates. PyTorch documents a norm computation that overflows despite a representable final mathematical answer. It also disclaims universal behavior for nonfinite inputs to external linear-algebra routines. [Numerical accuracy](https://docs.pytorch.org/docs/2.14/notes/numerical_accuracy.html)

Finite-only semantics also affect attention. PyTorch’s reference attention uses negative infinity for excluded positions. A7 can instead define semantic masked softmax without exposing sentinel arithmetic. Replacing negative infinity with a very negative finite constant is not a complete specification. [Attention reference](https://docs.pytorch.org/docs/2.14/generated/torch.nn.functional.scaled_dot_product_attention.html)

### Defaults, promotion, and casts

I recommend a small initial policy:

| Situation | Proposed behavior |
|---|---|
| Unconstrained floating literal | `f32` |
| Literal with explicit destination context | Round directly to that format |
| Explicit `f64` | Always retained |
| Same-dtype elementwise arithmetic | Preserve dtype unless the operator specifies otherwise |
| Different typed numeric operands | Require explicit conversion initially |
| `f16` mixed with `bf16` | Require explicit conversion to a chosen common type |
| Integer-to-float conversion | Explicit; distinguish rounded conversion from exact conversion |
| Float-to-integer conversion | Explicit rounding rule plus finite/range validation |
| Float narrowing | Explicit; overflow behavior follows the approved IEEE or finite policy |
| Reduction result | Operator-specific, not inferred solely from element dtype |

NumPy’s own rules include `int64 + uint64 -> float64` and special treatment of Python scalars. Those rules are useful comparison evidence, not an appropriate policy to inherit accidentally. [NumPy promotion](https://numpy.org/doc/stable/reference/arrays.promotion.html)

An alternative float promotion lattice is defensible: `f16` and `bf16` meet at `f32`, then widen to `f64`. Choose explicitly between that convenience and mandatory casts.

### Observable special values

The following are **behavior pseudocode, not valid or approved A7 syntax**.

| Expression or case | Proposed strict IEEE result |
|---|---|
| `1.0 / +0.0` | `+Inf` |
| `1.0 / -0.0` | `-Inf` |
| `0.0 / 0.0` | NaN |
| `sqrt(-1.0)` | NaN |
| `NaN == NaN` | False |
| `+0.0 == -0.0` | True, with distinguishable sign bits |
| Smallest representable subnormal stored and loaded | Preserve its bits |
| Finite check on NaN or infinity | Explicit failure result |

These examples require reconciliation with the current nonzero-divisor proof rule. Integer division and floating division need separate specifications.

Also decide NaN behavior for minimum/maximum, reduction ties, signaling NaNs, and serialization. I recommend no portable promise about NaN payload preservation, and no implicit saturation.

### Constant folding and optimization

The current folder performs arithmetic using Python values without target-format rounding at each operation. That is insufficient for the proposed semantics.

Recommended requirements:

- Fold integer arithmetic exactly, then apply the approved width-specific wrapping semantics.
- Round floating operations at the same semantic boundaries as runtime execution.
- Preserve signed zero and required exceptional results.
- Avoid folding transcendental functions unless the folder meets the runtime accuracy contract.
- Do not reassociate, contract multiply-add, or eliminate exceptional intermediates under strict scalar semantics.
- Keep fast math separately selectable and separately qualified.

Zig 0.16.0 distinguishes default strict floating behavior from `.optimized`, which permits reassociation, contraction, reciprocal transformations, and disregard for signed zero or nonfinite values. Release optimization and floating policy must therefore be controlled separately. [Zig floating modes](https://ziglang.org/documentation/0.16.0/#setFloatMode)

Tensor reductions and contractions need their own ordering and accuracy rules. Strict scalar arithmetic does not imply that all parallel reductions must produce identical bits.

## 5. Mixed precision

Storage support is only one part of mixed precision.

| Component | Proposed mixed-training precision |
|---|---|
| Authoritative parameters | `f32` |
| Forward parameter/activation storage | `f16` or `bf16` where selected |
| Low-precision matrix/convolution accumulation | `f32` |
| Gradient accumulation across uses or microbatches | `f32` |
| Adam moments and optimizer arithmetic | `f32` |
| Softmax, normalization statistics, losses | `f32` |
| Explicit scientific/reference execution | `f64` |
| Low-precision output conversion | Explicit rounding and overflow policy |

F16 has greater precision near one than bf16, but a much smaller exponent range. For example, f16’s largest finite value is 65,504. Neither format makes `f32` accumulation exact or eliminates overflow.

**Proposed step protocol:**

1. Compute loss using the selected operator precision rules.
2. Scale the loss for f16 training.
3. Run backward.
4. Unscale gradients before clipping.
5. Check gradients for nonfinite values.
6. If invalid, skip the entire optimizer update and adjust the scaler.
7. Otherwise apply clipping and the optimizer update.
8. Check any additional approved post-update invariants.

A skipped update should leave parameters, moments, weight decay, and successful-update counters unchanged. Scheduler advancement should follow successful updates by default.

Data consumption and RNG advancement are separate decisions. I recommend reporting that the batch was consumed even when the optimizer update was skipped. Retrying the same batch requires explicit restoration of its RNG and data position.

Bf16 can usually omit loss scaling, but must retain numerical checks. Gradient checks alone do not detect every invalid forward value or optimizer overflow.

On CPUs without a conforming native path, A7 should widen low-precision inputs to `f32`, execute a defined fallback, and convert outputs according to A7 rules. This qualifies semantics, not acceleration. Emulation overhead and temporary storage must be visible in diagnostics and performance reports.

## 6. Tensor values, storage, and autodiff

### Tensor contract

A7 should own:

- Dtype, rank, dimensions, element order, and device.
- Storage identity, offset, strides, and lifetime.
- Rules for views, copies, broadcasting, and mutation.
- Operation-specific shape and dtype validation.

Recommended initial layout contract:

| Operation | Proposed behavior |
|---|---|
| Creation | Contiguous row-major logical storage |
| Transpose and simple slicing | Read-only views where representable |
| Reshape | View when legal; otherwise explicit or documented materialization |
| Broadcast | Logical expansion; no ambiguous writable overlapping view |
| Advanced gather | New result |
| Functional update | New observable value |
| Negative-stride slicing | Defer or materialize until explicitly specified |
| Kernel packing | Private storage, separate from public tensor layout |

NumPy documents why “new array object” and “new storage” are different: basic indexing creates views, advanced indexing copies, and reshape can require copying. [Copies and views](https://numpy.org/doc/stable/user/basics.copies.html)

The approved immutable argument binding means a function cannot rebind its argument. It does not automatically prohibit or permit changing referenced storage.

**Proposed rule:** storage mutation requires the approved explicit permission and must preserve AD correctness. Syntax remains undecided.

### Functional update and buffer reuse

Behavior pseudocode:

```text
x = tensor([1, 2, 3])
alias = view(x)
y = updated(x, index=1, value=9)

x     remains [1, 2, 3]
alias remains [1, 2, 3]
y     equals  [1, 9, 3]
```

The runtime may reuse `x`’s allocation only if no live alias, saved AD value, or caller can observe its former contents. Binding immutability alone is insufficient evidence.

For explicit mutation, shared-storage versions are a useful runtime backstop. A version counter attached only to one view handle would miss mutations through another alias.

### AD architecture

**Recommendation:** first-order reverse-mode AD using an execution tape, with iterative traversal.

Each differentiable operator needs a registry entry describing:

- Forward semantics.
- Shape and dtype constraints.
- VJP rule.
- Saved values and their lifetimes.
- Mutation restrictions.
- Nondifferentiable behavior.
- JVP and higher-order support status.

Ordinary loops and branches should record the executed path. Predicates and integer indices are not differentiable quantities. Dynamic loop support requires dynamic tape storage and defined allocation failure behavior; it cannot imply unlimited memory.

Distinguish:

| Case | Meaning |
|---|---|
| Zero gradient | Defined derivative equals zero |
| Disconnected input | No differentiable path |
| Nondifferentiable input | Integer IDs, masks, or another excluded domain |
| Missing AD implementation | Unsupported operator |
| Invalid numerical gradient | Computation produced an invalid result |

Do not silently turn missing implementations or disconnected trainable parameters into zeros.

For nondifferentiable boundaries, approve conventions individually. Examples include ReLU at zero, maximum ties, pooling ties, clipping boundaries, and empty reductions.

Forward-mode AD is useful for JVPs and independent consistency checks, but the two training workloads primarily require reverse mode. I recommend declaring forward-mode coverage separately and deferring unrestricted higher-order AD.

Custom gradients should declare their saved values and supported transformations. “Custom gradient supported” must not imply JVP or second-derivative support.

Activation recomputation can reduce memory, but requires replayable regions. Dropout must replay the same mask without incorrectly consuming the global RNG twice. Effects such as file reads or parameter mutation should not be silently repeated.

## 7. CPU backend and native bridge

### Backend selection

| Backend | Recommended use | Qualification issue |
|---|---|---|
| OpenBLAS | Baseline `f32`/`f64` GEMM | BLAS integer ABI, layouts, threading, distribution |
| BLIS | Alternative dense matrix provider | Its mixed-precision claims do not automatically establish f16/bf16 coverage |
| oneDNN | Optional neural-network acceleration | Per-operator dtype/ISA coverage and numerical behavior |
| Eigen | Selected portable routines | C++ types and expression lifetimes must stay behind the bridge |
| A7 reference path | Complete semantic fallback | Correctness first; performance measured separately |

OpenBLAS exposes `cblas_sgemm` and `cblas_dgemm`. Its default LP64 distribution uses 32-bit BLAS integers, so passing A7 `usize` dimensions requires checked conversion. Distribution choices include threading and CPU dispatch configurations. [CBLAS header](https://raw.githubusercontent.com/OpenMathLib/OpenBLAS/develop/cblas.h), [distribution guide](https://www.openmathlib.org/OpenBLAS/docs/distributing/)

BLIS distinguishes storage and computation precision, but this review did not verify a complete low-precision operator matrix. [BLIS repository](https://github.com/flame/blis)

OneDNN’s current documentation does not provide CPU `f64` coverage. Low-precision support varies by ISA. It documents default floating accumulation, destination conversions that are not universally correctly rounded, and AMX paths that flush subnormal outputs. **It cannot be the sole backend for A7’s approved CPU dtype scope.** [oneDNN datatype contract](https://uxlfoundation.github.io/oneDNN/dev_guide_data_types.html)

OneDNN’s blocked layouts and reorders should remain private implementation details. Its threadpool integration can require a private C++ adapter despite a C-facing execution API. [Memory formats](https://uxlfoundation.github.io/oneDNN/dev_guide_understanding_memory_formats.html), [threadpool integration](https://uxlfoundation.github.io/oneDNN/dev_guide_threadpool.html)

Eigen provides relevant conversion source and threading controls, but those do not prove fast low-precision contractions. [Bf16 source](https://gitlab.com/libeigen/eigen/-/raw/master/Eigen/src/Core/arch/Default/BFloat16.h), [threading](https://libeigen.gitlab.io/eigen/docs-nightly/TopicMultiThreading.html)

### Proposed bridge boundary

```text
A7 language and compiler
          |
A7 tensor semantics, AD, optimizer, RNG, checkpoints
          |
Versioned C ABI kernel bridge
          |
Reference kernels | BLAS provider | optional oneDNN
```

The bridge should use plain descriptors and opaque handles, with explicit:

- ABI version and capability queries.
- Storage ownership and temporary-memory ownership.
- Shape, stride, and dimension conversion.
- Storage, computation, accumulation, and output dtype.
- Numerical-policy compatibility.
- Status results and synchronous completion.
- Thread configuration and backend identity.

Do not expose C++ templates, exceptions, or framework tensor objects in the public A7 ABI.

Ordinary integer wrapping must not make allocation calculations wrap silently. Shape products, byte counts, and BLAS conversions require checked operations even though ordinary source `+`, `-`, and `*` wrap.

Use one coordinated threading policy. Nested A7 workers, OpenMP, BLAS, and oneDNN pools can oversubscribe a CPU. Start with a controlled configuration, record it, then qualify alternatives.

A future GPU interface should reserve device capabilities, transfer operations, completion events, and backend errors. That is architectural preparation, not GPU qualification.

### Distribution and licenses

| Dependency | License identified in official source |
|---|---|
| JAX, TensorFlow | [Apache-2.0](https://raw.githubusercontent.com/jax-ml/jax/main/LICENSE), [Apache-2.0](https://raw.githubusercontent.com/tensorflow/tensorflow/master/LICENSE) |
| PyTorch | [BSD-style license and notices](https://raw.githubusercontent.com/pytorch/pytorch/main/LICENSE) |
| MLX, tinygrad | [MIT](https://raw.githubusercontent.com/ml-explore/mlx/main/LICENSE), [MIT](https://raw.githubusercontent.com/tinygrad/tinygrad/master/LICENSE) |
| oneDNN | [Apache-2.0 with component notices](https://github.com/uxlfoundation/oneDNN#license) |
| OpenBLAS, BLIS | [BSD-3-Clause](https://raw.githubusercontent.com/OpenMathLib/OpenBLAS/develop/LICENSE), [BSD-3-Clause](https://raw.githubusercontent.com/flame/blis/master/LICENSE) |
| Eigen | [MPL-2.0](https://gitlab.com/libeigen/eigen/-/raw/master/COPYING.MPL2) |
| NumPy, SciPy | [BSD-3-Clause](https://numpy.org/doc/stable/license.html), [BSD-3-Clause](https://raw.githubusercontent.com/scipy/scipy/main/LICENSE.txt) |
| ONNX Runtime | [MIT](https://raw.githubusercontent.com/microsoft/onnxruntime/main/LICENSE) |
| StableHLO, XLA | [Apache-2.0](https://raw.githubusercontent.com/openxla/stablehlo/main/LICENSE), [Apache-2.0](https://raw.githubusercontent.com/openxla/xla/main/LICENSE) |

These are license identifications, not approval of a final distribution. The packaged dependency inventory must include bundled components, native runtimes, notices, and modifications.

## 8. Errors, numerical failure, and recovery

**Inference:** arbitrary input shapes, allocation availability, file contents, and backend failures cannot all be proved away at compile time. The v1 plan needs defined runtime error values or must restrict those operations accordingly.

| Condition | Proposed behavior |
|---|---|
| Statically invalid shape/dtype | Compile-time diagnostic |
| Dynamically invalid shape/dtype/index | Structured error before invalid kernel execution |
| Size calculation overflow | Structured error |
| Unsupported backend combination | Conforming fallback or explicit unsupported error |
| Recoverable allocation failure | OOM result; no valid partial tensor |
| Nonfinite gradient | Explicit skipped-step outcome under the approved policy |
| Invalid forward numerical result | IEEE result or checked failure, according to approved policy |
| Backend execution failure | Error with backend and operation context |
| Corrupt/incompatible checkpoint | Reject before replacing live state |
| Unsupported checkpoint version | Explicit compatibility error |

Diagnostics should identify the A7 source operation, execution phase, input shapes and dtypes, backend, and relevant requested size.

A recoverable allocator failure is different from the operating system killing a process. Do not promise in-process recovery after external termination. Checkpoint recovery is the relevant mechanism for that case.

CPU execution should initially complete synchronously. Future asynchronous execution must define where errors become observable, which outputs remain invalid, and when checkpoint publication may report success.

StableHLO cannot supply this contract automatically. Its specification gives no general numerical-accuracy guarantee, leaves many errors implementation-defined, and places responsibility for dynamic shape agreement on the producer. [StableHLO accuracy and errors](https://openxla.org/stablehlo/spec#accuracy)

## 9. Actual workload requirements

### Image classifier

Freeze a concrete architecture before closing operator coverage. A convolutional classifier exercises substantially more than a flattened-image MLP.

The official PyTorch MNIST example requires convolution, ReLU, max-pooling, dropout, flattening, linear layers, log-softmax, NLL loss, preprocessing, data loading, optimizer updates, and scheduling. [Official classifier source](https://raw.githubusercontent.com/pytorch/examples/main/mnist/main.py)

For an A7 CNN, qualify:

- Forward convolution, input gradient, weight gradient, and bias reduction.
- Pooling selection and backward routing.
- Broadcast bias gradients.
- Stable classification loss.
- Training/evaluation mode differences.
- Dataset decoding, normalization, batching, and final partial batches.

Batch normalization adds running statistics and additional checkpoint state. Include it only if the selected model uses it.

### Small decoder transformer

A concrete initial proposal is a decoder with learned token/position embeddings, causal self-attention, residuals, LayerNorm, a GELU feed-forward block, and a vocabulary projection.

| Component | Required operations and behavior |
|---|---|
| Embeddings | Gather and repeated-index gradient accumulation |
| Q/K/V projections | Matmul, bias, reshape, transpose |
| Attention | Batched matmul, scaling, causal/padding masks, stable softmax |
| Attention dropout | RNG and evaluation-mode handling |
| Residual paths | Addition and shared gradient accumulation |
| LayerNorm | Mean, variance, epsilon, affine parameters, backward |
| Feed-forward block | Linear operations and selected GELU definition |
| Output loss | Projection, stable cross-entropy, target indexing |
| Generation | Context handling, argmax or sampling |
| Optional KV cache | Append/update semantics and cached-versus-full equivalence |

The official attention reference supports this decomposition, including explicit dropout handling and mask conventions. [Scaled dot-product attention](https://docs.pytorch.org/docs/2.14/generated/torch.nn.functional.scaled_dot_product_attention.html)

Approve exact GELU, normalization, mask, and positional conventions. Weight tying requires gradients from multiple uses to accumulate into the same parameter.

Define all-masked attention rows explicitly. I recommend a semantic masked operation with a documented zero-output/zero-gradient convention for fully excluded rows, subject to approval.

### Training and inference state

A resumable checkpoint should contain:

- Model configuration and parameters.
- Optimizer moments and successful-update counters.
- Scheduler state.
- Loss-scaler state.
- RNG algorithm, version, and state.
- Dataset/sampler position and shuffle state.
- Preprocessing and tokenizer identity.
- Precision policy and relevant compatibility metadata.
- Any accumulated gradients if mid-accumulation checkpoints are supported.

Weights alone are insufficient for next-step continuation. Framework guidance also distinguishes optimizer-bearing training checkpoints from inference loading. [TensorFlow checkpoints](https://www.tensorflow.org/guide/checkpoint), [PyTorch saving/loading](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html)

Inference packaging should separately include architecture, parameters, preprocessing/tokenizer, input/output contracts, runtime ABI, and dependency requirements.

ONNX Runtime is a useful independent export target. Qualify a specific model, opset, dtype, runtime version, and execution provider. Its CPU low-precision coverage is operator-specific, so begin with `f32` exports. [ORT float16 guidance](https://onnxruntime.ai/docs/performance/model-optimizations/float16.html), [official kernel matrix](https://raw.githubusercontent.com/microsoft/onnxruntime/main/docs/OperatorKernels.md), [ONNX versioning](https://onnx.ai/onnx/repo-docs/Versioning.html)

## 10. Acceptance scenarios

All examples below are **behavior pseudocode**. None asserts currently valid A7 syntax or completed implementation.

| Area | Independent acceptance requirement |
|---|---|
| Integer folding | `9007199254740993 / 1` remains exact in folded and runtime forms |
| Wrapping arithmetic | Boundary `+`, `-`, `*` results agree across folding and build profiles |
| Floating formats | Storage/casts cover halfway values, overflow, signed zero, NaN/Inf, and subnormal boundaries |
| Strict expressions | Optimizations preserve the approved exceptional and rounding behavior |
| Matmul | `[[1,2],[3,4]] × [[5,6],[7,8]] = [[19,22],[43,50]]` |
| Broadcasting | Valid rank expansion works; `[3,1,4] + [2,5,1]` fails |
| Reverse AD | `sum(x*x)` at `[1,-2,3]` gives `[2,-4,6]` |
| Shared operands | Multiple uses contribute to one accumulated gradient |
| Broadcast backward | Bias gradient sums every expanded use |
| Gather backward | Repeated token IDs accumulate gradients rather than overwrite |
| Control flow | Both branch paths and multiple loop lengths have correct path derivatives |
| Mutation | An alias change cannot silently corrupt a saved backward value |
| Tape lifetime | Repeated ordinary backward passes release saved storage |
| Recomputation | Gradients agree with saved-activation execution, including dropout |
| Mixed-precision skip | One nonfinite gradient leaves all optimizer-controlled state unchanged |
| OOM | Controlled allocator failure returns an error without publishing partial results |
| Checkpoint continuation | Fresh-process step N+1 matches uninterrupted step N+1 |
| Classifier | Real training plus held-out evaluation under a frozen recipe |
| Decoder | Real next-token training plus separate generation/inference |
| Export | Fresh ORT process reproduces qualified `f32` outputs |
| Packaging | Clean target environment runs without the training development environment |

### Gradient validation

Use several independent methods:

1. Analytic derivatives for small expressions.
2. Finite differences in `f64`, away from nondifferentiable boundaries.
3. JVP/VJP consistency where both exist.
4. Framework comparison with matched semantics.
5. End-to-end training.

Finite differences are sensitive to step size, cancellation, kinks, and overlapping storage. PyTorch’s gradcheck documents double-precision assumptions and such limitations. [Gradcheck](https://docs.pytorch.org/docs/2.14/generated/torch.autograd.gradcheck.gradcheck.html)

Do not finite-difference f16 directly and treat unstable estimates as an oracle.

### Tolerances and determinism

Specify tolerances by operation, dtype, scale, and conditioning. A useful comparison combines absolute and relative error:

```text
abs(actual - reference) <= atol + rtol * abs(reference)
```

Check NaN, infinity, and signed zero separately. Use exact expectations for representable small cases.

Before differential comparison, match:

- Input and accumulator dtype.
- Reduction axes and normalization.
- Epsilon placement.
- Mask polarity.
- GELU variant.
- Loss reduction.
- Optimizer epsilon, bias correction, and weight-decay convention.

NumPy/SciPy agreement is weaker when both candidate and oracle call the same BLAS provider. Add independent scalar calculations. SciPy is useful for future scientific routines, but ordinary classifier and decoder training do not require its decomposition catalog. [SciPy linear algebra](https://docs.scipy.org/doc/scipy/reference/linalg.html)

Define reproducibility within a recorded configuration. Cross-version, cross-ISA, cross-thread-count, and cross-device bitwise equality should not be promised. PyTorch explicitly documents these limits. [Reproducibility](https://docs.pytorch.org/docs/2.14/notes/randomness.html)

Strict and fast-math outputs should satisfy their respective contracts. Fast math must not be “validated” by assuming exact agreement with strict mode.

For real training, freeze datasets, splits, model definitions, seeds, update counts, precision modes, and acceptance thresholds before qualification. A decreasing loss or tiny-batch overfit is useful evidence, but does not establish held-out model performance.

## 11. Adoption and approval decisions

| Disposition | Recommendation |
|---|---|
| Preserve approved | A7-owned tensor/AD runtime; established kernels; CPU first; classifier and decoder training plus inference; four float formats |
| Preserve approved | Explicit-width integers, `usize` indices, wrapping ordinary integer arithmetic |
| Preserve approved | Immutable argument bindings and explicit referenced-data mutation permission |
| Adopt in plan | Per-operator precision contracts, structured errors, complete training checkpoints |
| Adopt in plan | Synchronous execution, iterative reverse tape, explicit saved-value lifetimes |
| Reject | Framework binding presented as A7-owned semantics |
| Reject | Dtype names treated as computation guarantees |
| Reject | oneDNN-only CPU architecture |
| Reject | Silent `f64` downgrading or arbitrary-precision revival |
| Reject | Weights-only checkpoint presented as training recovery |
| Defer | GPU qualification, unrestricted higher-order AD, distributed training |
| Defer | Broad scientific decomposition catalog and general StableHLO/XLA integration |
| Decide explicitly | Forward-mode coverage and activation recomputation in v1 |
| User approval required | IEEE versus finite-only behavior |
| User approval required | Float defaults, promotion, casts, subnormals, strict/fast policy |
| User approval required | Mutation syntax and alias behavior |
| User approval required | Nondifferentiable conventions and all-masked attention behavior |
| User approval required | Exact model recipes, CPU targets, performance and accuracy thresholds |
| User approval required | Numerical skip/retry behavior and checkpoint compatibility scope |

The implementation plan should proceed from approved semantics to the reference runtime, then optimized kernels, integrated training, recovery, and packaged inference. Existing compiler correctness findings remain prerequisites; new tensor tests do not close them.

### Questions for the separate GLM review

This research identifies the following boundaries without auditing their security:

- How must the native bridge validate external descriptors, dimensions, and lifetimes?
- What guarantees apply after allocation or kernel failure?
- How should malformed or partially written checkpoints be rejected?
- Which checkpoint formats can invoke code or external resources?
- How are backend dependencies, bundled binaries, and loader paths qualified?
- What resource limits and diagnostics apply to input-controlled shapes and tape growth?
- How are permitted mutations enforced across aliases and native calls?

## 12. Source versions and limitations

Sources were accessed on **2026-09-14**.

| Source family | Version or snapshot observed |
|---|---|
| A7 | Commit `701c679…` plus inspected working-tree changes |
| Zig | Versioned 0.16.0 documentation |
| PyTorch | Stable URLs redirected to documentation labeled 2.14 |
| TensorFlow | Opened API pages labeled 2.16.1; guides span different API generations |
| JAX | Moving `/latest/` documentation and `main` source |
| Keras | Moving `master` source |
| NumPy | Documentation labeled 2.5 |
| SciPy | Documentation labeled 1.18.0 |
| MLX | Documentation labeled 0.32.2 |
| oneDNN | Documentation labeled 3.14.0 |
| Eigen | Development documentation labeled `5.0.1-dev+7c7d8473` |
| OpenBLAS, BLIS, tinygrad, ORT, OpenXLA | Moving official documentation/source branches |

These are observed source labels, not a verified latest-release inventory. Pin exact tags or commits before implementation.

No runtime accuracy, performance, memory-use, training, recovery, ABI, or binary-distribution claim was verified in this review. Some official guides contain stale or contradictory passages, particularly MLX platform/lazy-compilation descriptions and older TensorFlow mixed-precision examples. The report uses those sources within the stated limits and leaves unverified behavior as an explicit qualification task.