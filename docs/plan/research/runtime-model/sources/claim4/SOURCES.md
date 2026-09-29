<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim4/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 4 — "Bit-exact deterministic neural inference on NPUs" — primary sources

All quotes below were extracted from files saved in this directory with `curl -sL`
(PDF via `pdftotext`) and verified with
`tr -s '[:space:]' ' ' < <file> | grep -o -F '<quote>'`.
`./verify.sh` re-runs every check: 47 OK, 0 FAIL.
Date read for every source: 2026-09-18.

---

## A. Vendor reproducibility statements and their scope limits

### cuDNN developer guide — "Reproducibility (Determinism)" (current)
URL: https://docs.nvidia.com/deeplearning/cudnn/backend/latest/developer/misc.html
Saved: `cudnn-misc.html` / Read: 2026-09-18 / Kind: vendor claim (spec-like scope statement)

Quote (grep-verified): "generate the same bit-wise results across runs when executed on GPUs with the same architecture"

Quote (grep-verified): "the following routines do not guarantee reproducibility across runs, even on the same architecture, because they use atomic operations in a way that introduces truly random floating point rounding errors"

Quote (grep-verified): "Across different architectures, no cuDNN routines guarantee bitwise reproducibility."

Excluded routines listed on the page (read from the same saved file): `cudnnConvolutionBackwardFilter`
with `CUDNN_CONVOLUTION_BWD_FILTER_ALGO_0` or `_ALGO_3`; `cudnnConvolutionBackwardData` with
`CUDNN_CONVOLUTION_BWD_DATA_ALGO_0`; `cudnnPoolingBackward` with `CUDNN_POOLING_MAX`;
`cudnnSpatialTfSamplerBackward`; `cudnnCTCLoss`/`cudnnCTCLoss_v8` with
`CUDNN_CTC_LOSS_ALGO_NON_DETERMINSTIC`.

Note: establishes the exact scope — same cuDNN version, same GPU architecture, and only for the
routines that do not use atomics. Explicitly refuses any cross-architecture bit-exactness guarantee.
Directly contradicts the claim's "eliminates non-deterministic cross-silicon rounding drift".

### cuDNN 8.9.7 developer guide (archive) — same section, older wording
URL: https://docs.nvidia.com/deeplearning/cudnn/archives/cudnn-897/developer-guide/index.html
Saved: `cudnn-repro.html` / Read: 2026-09-18 / Kind: vendor claim

Quote (grep-verified): "Across different architectures, no cuDNN routines guarantee bit-wise reproducibility."

Note: establishes that this is long-standing NVIDIA policy, not a recent doc edit. The archive page
names Volta/Turing/Ampere as the example pairs.

### cuBLAS library documentation — "Results Reproducibility" and math modes
URL: https://docs.nvidia.com/cuda/cublas/index.html
Saved: `cublas.html` / Read: 2026-09-18 / Kind: vendor claim

Quote (grep-verified): "generate the same bit-wise results at every run when executed on GPUs with the same architecture and the same number of SMs"

Quote (grep-verified): "bit-wise reproducibility is not guaranteed across toolkit versions because the implementation might differ due to some implementation changes"

Quote (grep-verified): "This guarantee no longer holds when multiple CUDA streams are active"
(the sentence continues "…or fixed-point emulation is used", with `fixed-point` as a link in the HTML)

Quote (grep-verified, from the note headed "The non-deterministic behavior of fixed-point emulation is due to its workspace memory requirements"): "allocation failures result in fallbacks to non-emulated routines"

Quote (grep-verified, `CUBLAS_PEDANTIC_MATH`): "This mode uses the prescribed precision and standardized arithmetic for all phases of calculations and is primarily intended for numerical robustness studies, testing, and debugging."

Quote (grep-verified, batch-invariance section): "the library is free to select different kernels or different reduction schemes (for example, split-K) for different shapes"

Note: the strongest scope limit found anywhere. Bit-exactness is conditioned on (i) same toolkit
version, (ii) same GPU architecture, AND (iii) the same **number of SMs** — so it breaks between two
SKUs of one architecture, let alone between vendors. `CUBLAS_PEDANTIC_MATH` is described as a
precision/debugging mode, not a cross-device reproducibility guarantee.

### PyTorch — "Reproducibility" notes
URL: https://docs.pytorch.org/docs/2.14/notes/randomness.html
Saved: `pytorch-randomness.html` / Read: 2026-09-18 / Kind: project doc

Quote (grep-verified): "Completely reproducible results are not guaranteed across PyTorch releases, individual commits, or different platforms."

Quote (grep-verified): "results may not be reproducible between CPU and GPU executions, even when using identical seeds"

Quote (grep-verified): "Each backend performs floating-point accumulation in a different order, and because floating-point addition is not associative, the results will differ between backends."

Quote (grep-verified): "Due to benchmarking noise and different hardware, the benchmark may select different algorithms on subsequent runs, even on the same machine."

Note: establishes the standard framework-level disclaimer, and that `torch.use_deterministic_algorithms`
buys run-to-run determinism "for a specific platform, device, and PyTorch release" only — not across
devices. The last quote establishes that even *one machine* is not stable when autotuning is on.

### NVIDIA/framework-reproducibility
URL: https://raw.githubusercontent.com/NVIDIA/framework-reproducibility/master/README.md
Saved: `fw-repro-readme.md` / Read: 2026-09-18 / Kind: project doc

Quote (grep-verified): "(bit-accurate, run-to-run reproducibility)"
Full sentence as it appears in the saved Markdown (the link markup `[determinism][2]` sits inside
it): "provide documentation, status, patches, and tools related to [determinism][2] (bit-accurate,
run-to-run reproducibility) in deep learning frameworks, with a focus on determinism when running on
GPUs".

URL: https://raw.githubusercontent.com/NVIDIA/framework-reproducibility/master/doc/d9m/README.md
Saved: `fwr-d9m.md` / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified), under the heading "MYTH: GPUs are inherently nondeterministic": "Any system that utilizes asynchronous parallelism can, theoretically, be configured to convert asynchronous parallelism into truly random noise."

Note: NVIDIA's own determinism project scopes the whole problem as **run-to-run** reproducibility.
It makes no cross-silicon claim anywhere in either file.

---

## B. Why FP reduction / atomic ordering breaks bit-exactness

### CUDA C++ Programming Guide (12.4.0)
URL: https://docs.nvidia.com/cuda/archive/12.4.0/cuda-c-programming-guide/index.html
Saved: `cuda-pg-1240.html` / Read: 2026-09-18 / Kind: spec

Quote (grep-verified): "each read/modify/write to that location occurs and they are all serialized, but the order in which they occur is undefined"

Note: establishes that the ordering of concurrent atomic read-modify-writes to one address is
undefined by the CUDA programming model. Combined with FP non-associativity this makes any
atomic-based float reduction non-reproducible even run-to-run on one device — which is exactly the
mechanism cuDNN names for its excluded routines.

### NVIDIA "Floating Point and IEEE 754 Compliance for NVIDIA GPUs"
URL: https://docs.nvidia.com/cuda/floating-point/index.html
Saved: `nvidia-floating-point.html` / Read: 2026-09-18 / Kind: spec / vendor technical note

Quote (grep-verified): "an implementation of the serial algorithm on multiple systems will give exactly the same result"

Quote (grep-verified): "results computed by an implementation of the serial algorithm may differ from those computed by an implementation of the other two algorithms"

Note: this is the precise boundary. NVIDIA says a *fixed algorithm* gives identical results on
multiple IEEE-754 systems; it does **not** say a fixed *operation* (a dot product, a matmul) does.
Different silicon runs different algorithms — different tiling, different reduction trees — so the
results differ. The claim asserts the operation-level property NVIDIA declines to assert.
PyTorch's "floating-point addition is not associative" sentence (above) is the same point stated
directly.

---

## C. Tensor cores — direct evidence against cross-silicon FP bit-exactness

### CUDA C++ Programming Guide — WMMA / Alternate Floating Point (TF32)
URL: https://docs.nvidia.com/cuda/archive/12.4.0/cuda-c-programming-guide/index.html
Saved: `cuda-pg-1240.html` / Read: 2026-09-18 / Kind: spec

Quote (grep-verified): "The internal layout of this format is implementation defined."
(context in the saved file: "tf32 This data format is a special floating point format supported by
Tensor Cores, with the same range as f32 and reduced precision (>=10 bits). The internal layout of
this format is implementation defined.")

Quote (grep-verified): "is unspecified and subject to change in future architectures"
(context in the saved file: "The mapping of matrix elements into <code>fragment</code> internal
storage is unspecified and subject to change in future architectures". The word `fragment` is
wrapped in markup in the HTML, so only the tail of the sentence is contiguous in the raw file.)

Quote (grep-verified, `__nv_bfloat16`): "This data format is an alternate fp16 format that has the same range as f32 but reduced precision (7 bits)."

Note: decisive. NVIDIA declares the tensor-core TF32 bit layout **implementation defined** and the
fragment storage mapping **unspecified and subject to change in future architectures**. A hardware
vendor that refuses to fix the internal representation cannot be delivering bit-exactness across
silicon generations, let alone across vendors.

### PyTorch CUDA notes — TF32 numerics
URL: https://docs.pytorch.org/docs/2.14/notes/cuda.html
Saved: `pytorch-tf32.html` / Read: 2026-09-18 / Kind: project doc

Quote (grep-verified): "rounding input data to have 10 bits of mantissa, and accumulating results with FP32 precision, maintaining FP32 dynamic range"

Note: establishes that a TF32 tensor-core matmul rounds FP32 inputs down to 10 mantissa bits, so it
cannot match an FP32 matmul on the same inputs. Whether tensor cores are used is a per-library,
per-version policy decision (the same page documents the flags and that the cuDNN default differs
from the matmul default), so the *same source program* produces different bits depending on library
version and device capability.

---

## D. Compiler freedoms below the API

### Metal Shading Language Specification (2026-06-04, Apple)
URL: https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf
Saved: `msl-spec.pdf`, text `msl-spec.txt` / Read: 2026-09-18 / Kind: spec

Quote (grep-verified): "The options enable or disable the optimizations for floating-point arithmetic that may violate the IEEE 754 standard."

Quote (grep-verified): "This option sets how aggressive the compiler can be with floating-point optimizations. The default is fast."
(the option is `-fmetal-math-mode=<fast, relaxed, safe>`; the same page states `-fmetal-math-fp32-functions=<fast|precise>` — "The default is fast.")

Quote (grep-verified): "Allow Reassociation: Allow algebraically equivalent transformations, such as reassociating floating-point operations that may dramatically change the floating-point results."

Quote (grep-verified): "By default, the compiler allows floating-point contractions."

Note: on Apple GPUs the shader compiler defaults to fast math, which by Apple's own list permits
reassociation "that may dramatically change the floating-point results", plus FMA contraction.
Bit-exactness is opt-out, not default, and the opt-out costs performance.

### VK_KHR_shader_float_controls (Vulkan)
URL: https://docs.vulkan.org/spec/latest/appendices/extensions.html (extension appendix)
Saved: `vk-ext-float-controls.html`; struct page `vk-float-controls.html`
(https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceFloatControlsProperties.html)
Read: 2026-09-18 / Kind: spec

Quote (grep-verified): "extension enables efficient use of floating-point computations through the ability to query and override the implementation"
(full sentence in the saved file: "The VK_KHR_shader_float_controls extension enables efficient use
of floating-point computations through the ability to query and override the implementation's
default behavior for rounding modes, denormals, signed zero, and infinity." — the apostrophe is the
HTML entity `&#8217;`, so the quote is cut before it.)

Note: the existence of a *query-and-override* extension for rounding mode, denormal handling, signed
zero and infinity establishes that Vulkan implementations did not guarantee uniform IEEE behavior.
The struct `VkPhysicalDeviceFloatControlsProperties` (saved separately) exposes per-width booleans
(`shaderDenormPreserveFloat16/32/64`, `shaderDenormFlushToZeroFloat*`, `shaderRoundingModeRTEFloat*`,
`shaderRoundingModeRTZFloat*`, `shaderSignedZeroInfNanPreserveFloat*`) — i.e. these are capabilities
a device **may not have**, not guarantees.

### HLSL / DXIL — fast math is the default; `/Gis` is opt-in
URL: https://raw.githubusercontent.com/microsoft/DirectXShaderCompiler/main/docs/DXIL.rst
Saved: `dxil-rst.txt` / Read: 2026-09-18 / Kind: spec (DirectX Shader Compiler IR specification)

Quote (grep-verified): "By default, all floating-point HLSL operations are considered 'fast' or non-precise. HLSL and driver compilers are allowed to refactor such operations."

Quote (grep-verified): "The /Gis compiler switch implicitly declares all variables and values as precise."

Quote (grep-verified): "When fast math is enabled, implementation may use reciprocal form"

Note: same pattern as Metal. In HLSL, fast math is the default and IEEE-precise behavior must be
requested with `/Gis` or the `precise` qualifier. The spec states explicitly that **driver
compilers** — i.e. the vendor's JIT, not the offline compiler — are allowed to refactor these
operations, so the final instruction sequence, and therefore the result bits, is chosen per driver
and per GPU.

### Direct3D 11.3 Functional Specification — permitted deviations from IEEE-754
URL: https://microsoft.github.io/DirectX-Specs/d3d/archive/D3D11_3_FunctionalSpec.htm
Saved: `d3d-fl-spec.html` / Read: 2026-09-18 / Kind: spec

Quote (grep-verified): "are required to operate under a defined subset of the IEEE 754 32-bit single precision floating point behavior"

Quote (grep-verified): "Fused operations (such as mad, dp3) must produce results that are no less accurate than the worst possible serial ordering of evaluation of the unfused expansion of the operation."

Quote (grep-verified): "the exact bit pattern of the NaN is not required to stay the same"

Quote (grep-verified): "it is permissible for the result of comparing zeros to be dependent on the order of parameters, using a comparison that ignores the signs"

Note: the D3D specification defines fused operations — `mad`, `dp3`, i.e. exactly the primitives a
neural or motion-matching kernel is built from — by an **accuracy bound**, not an exact result. Two
conforming implementations may return different bits for the same `dp3`. NaN payloads and
signed-zero comparison order are likewise left to the implementation. This is a graphics-API spec,
not an NPU one, but it is the same silicon and the same governing model.

### `fxc` command-line reference (Microsoft Learn)
Attempted: https://learn.microsoft.com/en-us/windows/win32/direct3dtools/fxc (saved `hlsl-fxc.html`,
HTTP 200, 48 KB) — the saved file is a JavaScript shell; text extraction found no occurrence of
`Gis`, `IEEE` or `strict`.
Status: **not readable — no quote.** The `/Gis` semantics are instead quoted from `DXIL.rst` above.

### IEEE 754 reproducibility clause
Not attempted beyond discovery: the standard is paywalled by IEEE.
Status: **not readable — no quote.**

---

## E. The fixed-point escape — what the integer spec actually promises

### TensorFlow Lite / LiteRT 8-bit quantization specification
URL: https://ai.google.dev/edge/litert/models/quantization_spec
Saved: `tflite-quant-spec.html` / Read: 2026-09-18 / Kind: spec

Quote (grep-verified): "We also understand different hardware may have preferences and restrictions that may cause slight deviations when implementing the spec that result in implementations that are not bit-exact."

Quote (grep-verified): "the nature of machine learning (and deep learning in the most common case) makes it impossible to provide any hard guarantees"

Note: **this is the decisive source for the claim's strongest part.** The canonical integer inference
spec — the one the claim's "standardized fixed-point" language points at — states in its own
"Specification summary" that hardware implementations of it are expected to be *not bit-exact*, and
that hard guarantees are impossible. It offers per-operation *tolerances*, not bit-exactness.

### TFLite kernel source — two requantization rounding modes selected at build time
URL: https://raw.githubusercontent.com/tensorflow/tensorflow/master/tensorflow/lite/kernels/internal/common.h
Saved: `tflite-common-h.txt` / Read: 2026-09-18 / Kind: project source (primary)
URL: https://raw.githubusercontent.com/tensorflow/tensorflow/master/tensorflow/lite/kernels/internal/BUILD
Saved: `tflite-bazel-common.txt` / Read: 2026-09-18 / Kind: project source (primary)

Quote (grep-verified, `common.h`): "#if TFLITE_SINGLE_ROUNDING"
In the saved file this guard sits between the comments "// Single-rounding
MultiplyByQuantizedMultiplier" (line 349) and "// Double-rounding
MultiplyByQuantizedMultiplier" (line 395, on the `#else` branch), each providing its own
`MultiplyByQuantizedMultiplierSmallerThanOneExp` / `...GreaterThanOne`.

Quote (grep-verified, `BUILD`): "TFLITE_SINGLE_ROUNDING=1"
The BUILD file defines both a `quantization_util` target and a `quantization_util_single_rounding`
target, and both `quantization_util_test` (`TFLITE_SINGLE_ROUNDING=0`) and
`quantization_util_test_single_rounding` (`=1`).

Note: even the *reference integer path* ships two different rounding implementations of the
requantization step, selected by a compile-time define, with a test target for each. Integer
determinism therefore holds only against a **named build of a named reference**, not against
"standardized fixed-point" in the abstract.

### LiteRT delegate documentation — accelerators differ from CPU kernels
URL: https://ai.google.dev/edge/litert/performance/delegates (redirects to developers.google.com)
Saved: `tflite-delegates.html` / Read: 2026-09-18 / Kind: vendor/project doc

Quote (grep-verified): "Delegates usually perform computations at a different precision than their CPU counterparts."

Note: Google states plainly that hardware-accelerated execution differs numerically from the CPU
reference and must be measured per model. The page frames delegate validation as an accuracy
question ("Does the delegate perform the same as the CPU?"), not a settled guarantee.

### ONNX Runtime — execution providers
URL: https://onnxruntime.ai/docs/execution-providers/ (saved `onnxruntime-ep.html`)
URL: https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html (saved `ort-qnn-ep.html`)
Read: 2026-09-18 / Kind: project doc — **searched, nothing found**

Terms grepped on the text-extracted pages: `determinis`, `bit-exact`, `bit exact`, `reproducib`.
Hits: 0 on both pages. ("accuracy" appears twice on the QNN page, only about int8-vs-int16
quantization tradeoffs.)
Note: does not establish anything either way; records that ORT makes **no** cross-EP numerical
equivalence statement on these pages.

---

## F. NPU vendor statements

### Arm Ethos-U / Vela compiler — the one real bit-exactness statement found
URL: https://raw.githubusercontent.com/nxp-imx/ethos-u-vela/master/TESTING.md
(NXP mirror of the Arm `ml/ethos-u/ethos-u-vela` repository; `gitlab.arm.com` and
`review.mlplatform.org` both returned HTTP 202 with a zero-byte body, and
`developer.arm.com/documentation/109267/...` returned HTTP 403 — see "not readable" below)
Saved: `vela-testing.md`, plus `vela-readme.md` / Read: 2026-09-18 / Kind: project doc

Quote (grep-verified): "Vela is tested in-house by comparing the bit exact numerical behaviour of the optimised network against that of the corresponding behaviour of the reference code."

The same file states TFLite networks "are compared against the TensorFlow Lite/LiteRT reference
kernels", TOSA networks against "the TOSA Reference Model", and lists which single TensorFlow
version each Vela release was tested against (e.g. "Vela 4.5.0 to current supports TensorFlow
2.19.1").

Note: **establishes the narrow form of the claim and only that form.** It is (i) an integer/TOSA
path, (ii) bit-exact *against a named reference implementation at a pinned version*, and (iii) a
statement about in-house **testing**, not a contractual guarantee across chips. It is not a
statement that two different NPUs agree with each other. Caveat: read from a vendor mirror because
Arm's own hosts were unreachable.

### Apple — Core ML / Apple Neural Engine
URL: https://apple.github.io/coremltools/docs-guides/source/typed-execution.html
Saved: `coreml-typed-exec.html` / Read: 2026-09-18 / Kind: vendor claim

Quote (grep-verified): "The GPU and NE use float 16 precision, and the CPU uses float 32."

Quote (grep-verified): "The execution precision varies based on the hardware and software versions, since the partitioning of the graph varies with hardware and software."

Note: the opposite of the claim, stated by the vendor. On Apple silicon the same model produces
different numerics on ANE vs GPU vs CPU *of the same device*, and Apple says the precision itself
varies with hardware and OS version because the runtime repartitions the graph. Terms grepped on
https://developer.apple.com/documentation/coreml/mlcomputeunits (saved `coreml-ane.html`, a 1 KB
JS shell): `determinis`, `bit-exact`, `reproducib` — 0 hits, page not readable.

### Intel — OpenVINO NPU plugin
URL: https://docs.openvino.ai/2025/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html
Saved: `openvino-npu.html` / Read: 2026-09-18 / Kind: vendor claim

Quote (grep-verified): "Computation precision for the HW is FP16."

Terms grepped on the text-extracted page (136 KB of text): `determinis` 0, `bit-exact` 0,
`bit exact` 0, `reproducib` 0.
Note: Intel states the NPU computes in FP16 regardless of the model's declared precision — so an
FP32 model does not reproduce its CPU result — and makes **no** determinism or reproducibility
statement anywhere on the device page.

### AMD — Ryzen AI / XDNA
URL: https://ryzenai.docs.amd.com/en/latest/index.html
Saved: `ryzenai-docs.html` / Read: 2026-09-18 / Kind: vendor claim

Quote (grep-verified): "These models are internally converted to bfloat16 and compiled using the bfloat16 compilation flow."

Terms grepped: `determinis` 0, `bit-exact` 0, `bit exact` 0, `reproducib` 0.
Note: FP32 models are silently converted to bf16 by the compiler; no determinism or reproducibility
statement on the landing page.

### Google — Edge TPU / Coral
URL: https://coral.ai/docs/edgetpu/models-intro/ (served from gweb-coral-full.uc.r.appspot.com)
Saved: `edgetpu.html` / Read: 2026-09-18 / Kind: vendor doc

Quote (grep-verified): "Depending on input/output size, this operation might not be mapped to the Edge TPU to avoid loss in precision."

Terms grepped: `determinis` 0, `bit-exact` 0, `bit exact` 0, `reproducib` 0.
Note: even on a pure-integer accelerator, whether a given op runs on the TPU or falls back to CPU
depends on tensor shape — so the execution path, and with it the numerics, is not fixed by the model
alone.

### Qualcomm — Hexagon NPU / QNN (AI Engine Direct)
URL: https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-50/overview.html
Saved: `qnn-hexagon.html` (HTTP 200, 52 KB) — the saved file is a JavaScript shell; text extraction
yields only CSS variables. Terms grepped anyway: `determinis` 0, `bit-exact` 0, `reproducib` 0,
`precision` 0.
Status: **not readable — no quote.**
Also checked, readable, and empty on those terms:
https://ai.google.dev/edge/litert/next/qualcomm (saved `litert-qualcomm.html`) — `determinis` 0,
`bit-exact` 0, `reproducib` 0, `accuracy` 0; and the ONNX Runtime QNN EP page above.
Note: no Qualcomm determinism or bit-exactness statement located in any readable source.

### GLM-5.3-flash fallback lookup (SECONDARY — produced no usable content)
Prompt: `tmp/glm/claim4-npu-determinism-prompt.md`
Output: `tmp/glm/claim4-npu-determinism.md`
Read: 2026-09-18 / Kind: GLM lookup (secondary)

The run failed before producing an answer: every web search returned
`MCP error -429: {"error":{"code":"1310","message":"Weekly/Monthly Limit Exhausted. Your limit will
reset at 2026-09-22 23:05:34"}}`, then a timeout. No claims were returned, so there is nothing to
mark UNVERIFIED. All vendor findings in section F above are my own reads of files saved here.

---

## Files in this directory

| File | Source |
|---|---|
| `cudnn-misc.html` | cuDNN backend/latest developer "Odds and Ends" (Reproducibility) |
| `cudnn-repro.html` | cuDNN 8.9.7 archive developer guide |
| `cudnn-devguide.html` | cuDNN developer overview (used only to locate the section) |
| `cublas.html` | cuBLAS library documentation (2.4 MB) |
| `cuda-pg-1240.html` | CUDA C++ Programming Guide 12.4.0 (single page) |
| `cuda-prog-guide.html` | current CUDA guide page — JS shell, not usable |
| `nvidia-floating-point.html` | NVIDIA Floating Point and IEEE 754 Compliance |
| `pytorch-randomness.html`, `pytorch-tf32.html` | PyTorch Reproducibility, CUDA notes |
| `fw-repro-readme.md`, `fwr-d9m.md` | NVIDIA/framework-reproducibility |
| `msl-spec.pdf`, `msl-spec.txt` | Metal Shading Language Specification |
| `vk-ext-float-controls.html`, `vk-float-controls.html` | Vulkan extension appendix, float-controls struct |
| `hlsl-fxc.html` | fxc page — JS shell, unusable |
| `dxil-rst.txt` | DirectXShaderCompiler `docs/DXIL.rst` (fetched as `dxc-wiki.html`, renamed) |
| `d3d-fl-spec.html` | Direct3D 11.3 Functional Specification (2.2 MB) |
| `vela-pypi.json`, `vela-pypi-description.txt` | PyPI metadata for ethos-u-vela (no bit-exactness text) |
| `nvidia-fw-repro-pytorch.md` | framework-reproducibility doc/d9m/pytorch.md (not quoted) |
| `tflite-quant-spec.html` | LiteRT 8-bit quantization specification |
| `tflite-common-h.txt`, `tflite-bazel-common.txt` | TFLite kernel source + BUILD |
| `tflite-delegates.html` | LiteRT delegates guide |
| `onnxruntime-ep.html`, `ort-qnn-ep.html` | ONNX Runtime EP pages |
| `vela-testing.md`, `vela-readme.md` | Arm Ethos-U Vela (NXP mirror) |
| `coreml-typed-exec.html`, `coreml-ane.html` | coremltools typed execution; MLComputeUnits (JS shell) |
| `openvino-npu.html` | OpenVINO NPU device page |
| `ryzenai-docs.html` | AMD Ryzen AI Software docs landing page |
| `edgetpu.html` | Coral Edge TPU models overview |
| `qnn-hexagon.html`, `litert-qualcomm.html` | Qualcomm QNN overview (JS shell); LiteRT Qualcomm page |
| `nnapi-ndk.html` | Android NDK NeuralNetworks reference — index page only, no relax-computation text |
| `verify.sh` | re-runs all 47 quote checks |
