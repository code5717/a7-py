> **Source:** Codex CLI external reviewer, hardware and provider research.  
> **Session:** `codex rollout 2026-09-14T23-10-35 (01a0a18a-fd95)`  
> **Date:** 2026-09-14. Recovered 2026-09-15 from temporary output after Plan Mode blocked the original write.  
> **Status:** Advisory. Body preserved verbatim except removal of pre-report narration where noted. User decisions are in the [ledger](../decisions.md).

This review supports keeping A7 v1 CPU-first, with A7 owning tensor semantics and automatic differentiation. The strongest future general-purpose accelerator path is a narrowly qualified CUDA backend, followed by selected ROCm configurations. NPUs, TPUs, Neuron, spatial accelerators and FPGAs need distinct integration and acceptance plans.

**Broad research does not qualify any hardware or expand approved v1 scope.** This was a read-only review dated **2026-09-14**, using three parallel hardware reviewers and central source reconciliation. No dependencies were installed, hardware workloads executed, accounts opened, resources provisioned, or repository files changed. Cybersecurity investigations remain assigned to GLM.

The sibling framework report was absent when checked. The compatibility discussion below is independently researched and should be reconciled with that report when available.

The local documents establish two boundaries:

- [SPEC.md](/home/cx89/Projects/pl-dev/a7-py/docs/SPEC.md:1083) explicitly describes tensors, differentiation and GPU movement as unimplemented design targets.
- [SAFETY_CONTRACT.md](/home/cx89/Projects/pl-dev/a7-py/docs/SAFETY_CONTRACT.md:1) requires approved lowerings and compile-time rejection when required proofs are missing. Its range-proof description of integer arithmetic differs from the supplied approved wrapping `+`, `-`, `*` decision. This report follows the supplied decision and flags the documentation discrepancy.

**Hardware taxonomy and access**

A7 should classify devices by execution contract, rather than by the vendor's processor label.

| Class | What users can execute | Consequence for A7 |
|---|---|---|
| General-purpose CPU | Native programs, libraries, dynamic control flow | Direct home for A7's runtime, reference kernels and AD |
| Programmable GPU | Host program plus custom device kernels and native libraries | Suitable for A7-owned forward/backward execution |
| Graph accelerator | Compiled supported operators or graph partitions | Requires graph lowering, capability checks and shape planning |
| Programmable DSP or spatial processor | Custom kernels with explicit local memory, DMA or placement | Possible backend, with a substantially different compiler/runtime contract |
| FPGA/adaptive compute | Synthesized circuits, bitstreams and host applications | Qualification attaches to the design and toolchain, not just the board |
| Hosted model API | Requests against selected models | Application integration, not an A7 tensor backend |

These categories overlap. AMD NPUs have both production graph deployment and custom IRON programming. Qualcomm has QNN graph execution and Hexagon custom compute. Cerebras has a hosted inference API and a separate programmable wafer-scale system. Those distinctions materially change feasibility.

**CPU vendor matrix**

| Family | Available execution and software | Numerical, memory and deployment implications |
|---|---|---|
| Intel x86 client/server | Native programs; established BLAS, oneDNN and compiler-vectorized kernels. Xeon 6 P-core products expose AVX-512 and AMX capabilities that must not be inferred for every Xeon 6 SKU. | Baseline f32/f64 execution is practical. F16 conversion, native FP16 arithmetic, BF16 dot products and AMX require separate dispatch checks. AMX also needs OS support. NUMA placement, memory channels, thread count and packing affect performance. [Intel architecture distinctions](https://www.intel.com/content/www/us/en/support/articles/000098612/processors/intel-xeon-processors.html) |
| AMD Ryzen/EPYC | Native programs and established CPU libraries. EPYC 9005 launched October 10, 2024, with up to 192 cores, twelve DDR5 channels and full-width AVX-512 execution. | Server memory bandwidth cannot be extrapolated to Ryzen laptops. CPU, GPU and NPU support are independent. Qualify scalar, vector and BF16 paths separately. [AMD EPYC launch](https://www.amd.com/en/newsroom/press-releases/2024-10-10-amd-launches-5th-gen-amd-epyc-cpus-maintaining-le.html) |
| AWS Graviton | Arbitrary AArch64 programs on EC2. Graviton5 R9g/R9gd became generally available August 31, 2026, in specified regions. Earlier Graviton generations remain useful qualification targets. | Requires AArch64 native dependencies. Graviton5 documentation identifies DDR5-8800, but actual instance capacity and exposed features depend on size. “Arm64” does not establish one BF16/vector behavior. [Dated AWS availability](https://aws.amazon.com/blogs/aws/amazon-ec2-r9g-and-r9gd-instances-powered-by-aws-graviton5-processors-are-now-generally-available/) |
| Arm server, including Ampere | Altra and AmpereOne remain in the vendor catalog with partner systems. Native Linux execution is practical. | Do not assume all Arm servers implement SVE, SME or the same matrix instructions. AmpereOne reference systems include different memory-channel configurations. Establish a baseline AArch64 build before optimized dispatch. [Ampere processors](https://amperecomputing.com/en/products/processors), [partner systems](https://www.amperecomputing.com/products/ecosystem/supermicro) |
| Apple CPU | Native macOS programs; Accelerate and BNNS. BNNS explicitly supports CPU training and inference. | Useful CPU backend without delegating A7 AD to Core ML. Apple framework linkage and ABI are separate from Linux AArch64. CPU qualification says nothing about Metal or Neural Engine. [Apple BNNS](https://developer.apple.com/documentation/accelerate/bnns-library/) |
| Qualcomm and mobile Arm CPUs | Native applications on supported Windows, Android and Linux environments. | Windows Arm64, Android and embedded Linux require different binaries and packaging. CPU fallback is feasible only when the relevant application/runtime permits it. QAIRT acceleration is a separate path. [Qualcomm SDK overview](https://www.qualcomm.com/developer/software/neural-processing-sdk-for-ai) |
| RISC-V | Real development boards exist. Milk-V Jupiter lists RVV 1.0, RV64GCVB and 4/8/16 GB configurations. | Appropriate for exploratory native-CPU portability. Optional FP/BF16 extensions require device confirmation. RVV 1.0 and older vector implementations are not interchangeable. Board GPU claims do not establish AI-library support. [Jupiter](https://milkv.io/jupiter), [RISC-V vector specification](https://docs.riscv.org/reference/isa/unpriv/v-st-ext) |

CPU qualification should distinguish storage support from native arithmetic. A baseline can store f16/bf16 and compute through explicit f32 conversion, but that must be reported as a conversion path. It must not claim native half-precision throughput or identical intermediate rounding.

The development host was directly identified as **AMD Ryzen AI 9 HX 370 with Radeon 890M**, PCI identifier `1002:150e`, running **Linux 7.1.9-arch1-2**. This establishes identity only. No numerical or performance qualification occurred.

**GPU vendor matrix**

| Family | Programming and workloads | Memory, precision and availability |
|---|---|---|
| NVIDIA datacenter and RTX | CUDA/PTX custom kernels; cuBLAS, cuDNN and other native libraries. Training, inference and general compute. | Discrete allocations, transfers, streams and events require explicit ownership. HBM server GPUs and GDDR workstation GPUs are separate targets. FP64 capability and throughput differ substantially by product; tensor formats and compute modes are generation-specific. Current cloud catalogs expose H100/H200/B200 and selected newer configurations. [CUDA documentation](https://docs.nvidia.com/cuda/), [HGX configurations](https://docs.nvidia.com/enterprise-reference-architectures/hgx-ai-factory-h100-h200-b200/latest/components.html) |
| AMD Instinct | HIP/ROCm custom kernels, rocBLAS/hipBLASLt, MIOpen, RCCL. Training, inference and HPC. | MI355X advertises 288 GB HBM3E and 8 TB/s device-memory bandwidth. This is not host-transfer or application throughput. Exact GPU, library, OS and runtime compatibility matters. [MI355X specifications](https://www.amd.com/en/products/accelerators/instinct/mi350/mi355x.html) |
| AMD Radeon | Selected products support ROCm; Vulkan and OpenCL are separate programming routes. | Driver recognition does not establish rocBLAS/MIOpen support. GDDR capacity, PCIe transfers and matrix instructions vary. Qualify separately from Instinct. [ROCm compatibility](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html) |
| AMD Strix integrated GPU | Current ROCm matrix includes Radeon 890M/880M and `gfx1150`. Custom HIP execution is a credible research route. | Shared physical memory still has allocation limits, synchronization and CPU/GPU contention. The matrix lists Ubuntu and Windows combinations, not the current Arch host. [Versioned matrix](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html) |
| Intel Arc/Core Ultra GPU | SYCL/DPC++, Level Zero, OpenCL, oneDNN, OpenVINO and upstream PyTorch XPU. Custom compute, training and inference. | Integrated GPUs share system memory; discrete Arc uses GDDR. Query FP64 independently from XMX/matrix capabilities. B580 is a launched 12 GB product with advertised 456 GB/s bandwidth. [Intel GPU stack](https://dgpu-docs.intel.com/overview/introduction.html), [B580 specifications](https://www.intel.com/content/www/us/en/products/sku/241598/intel-arc-b580-graphics/specifications.html) |
| Intel Max | Xe-HPC, SYCL/Level Zero, training and HPC. | Max 1550 lists 128 GB HBM2e and 3276.8 GB/s, but its product page also lists expected discontinuance in January 2026. Existing-system research is plausible; new procurement requires confirmation. This is not proof that all support has ended. [Max 1550](https://www.intel.com/content/www/us/en/products/sku/232873/intel-data-center-gpu-max-1550/specifications.html) |
| Apple GPU | Metal custom kernels, MPS/MPSGraph, MLX and PyTorch MPS. | Unified memory requires resource-mode and synchronization discipline. M5 was announced October 15, 2025, with 153 GB/s bandwidth for the base chip. Its GPU Neural Accelerators are distinct from the separate Neural Engine. MLX documents f64 as CPU-only. [M5 announcement](https://www.apple.com/newsroom/2025/10/apple-unleashes-m5-the-next-big-leap-in-ai-performance-for-apple-silicon/), [MLX dtype restrictions](https://ml-explore.github.io/mlx/build/html/python/data_types.html) |

For Strix, the dated anchor is **ROCm 7.14.1, released September 2, 2026**. Its listed Ryzen combinations include Ubuntu 26.04 with GA kernel 7.0, Ubuntu 24.04.4 with HWE kernel 6.17, and Windows 11 25H2. This is stronger evidence than an undated “latest” page, but does not qualify Arch or every dtype/library combination. The archived 7.2 Ryzen matrix validated only FP16; that historical restriction should not be silently presented as the current restriction. [Release notes](https://rocm.docs.amd.com/en/docs-7.14.1/about/release-notes.html), [archived Ryzen matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html)

NVIDIA's January 2026 Rubin announcement projected partner products for the second half of 2026. That announcement alone does not establish rentable capacity on this review date. Keep announced systems outside qualification plans until an actual product, SDK and access configuration are verified. [Rubin announcement](https://nvidianews.nvidia.com/news/rubin-platform-ai-supercomputer)

**NPU, DSP and edge matrix**

| Family | Actual execution contract | Constraints and A7 relevance |
|---|---|---|
| Intel Core Ultra NPU | OpenVINO inference graphs compiled into a device format. | The 2026 NPU documentation accepts F32/F16 graph types but identifies FP16 hardware computation. A custom OpenVINO operator does not automatically supply a custom NPU kernel. Query execution placement and compiler/driver versions. Exceptional-value and accumulator details remain incomplete. [OpenVINO NPU](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html) |
| AMD Ryzen AI production stack | ONNX Runtime/Vitis AI deployment, including pretrained-model and LLM flows. | Version 1.8 documentation, updated August 3, 2026, includes Linux deployment. Supported processor, model, quantization and OS combinations differ. GPU and NPU paths remain separate. [Ryzen AI documentation](https://ryzenai.docs.amd.com/en/main/) |
| AMD IRON/MLIR-AIE | Vendor-owned custom NPU programming using Python descriptions, C++ kernels, LLVM/MLIR and Peano. | Explicit tile placement, local memory, streams and DMA. Produces device artifacts used with XRT/XDNA. This is genuine custom computation, but not a universal stable NPU ABI or turnkey A7 training backend. Non-Ubuntu configurations are experimental. [IRON/MLIR-AIE](https://github.com/Xilinx/mlir-aie) |
| Apple Neural Engine | Core ML model execution with permitted compute-unit selection. | `.all` permits ANE use without guaranteeing it. Public custom layers expose CPU evaluation and optional Metal encoding, not a corresponding ANE kernel entry point. No public general-purpose ANE ABI was established. [Core ML custom layers](https://developer.apple.com/documentation/coreml/mlcustomlayer), [typed execution](https://apple.github.io/coremltools/docs-guides/source/typed-execution.html) |
| Qualcomm QNN/QAIRT | Native SDK and official ORT execution provider. | The documented ORT HTP route requires quantized models, fixed shapes and a supported operator subset; `If` and `Loop` are unsupported there. These restrictions must not be generalized to every Qualcomm API. [ORT QNN provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html) |
| Qualcomm Hexagon DSP/NPU | Custom heterogeneous compute through the Hexagon SDK. | SDK access requires login/agreement and a supported device environment. Qualcomm's March 23, 2026 XNNPACK/HVX announcement is a distinct kernel route, not proof that every framework distribution enables it. [Hexagon SDK](https://www.qualcomm.com/developer/software/hexagon-npu-sdk), [XNNPACK integration](https://www.qualcomm.com/developer/blog/2026/03/bringing-xnnpack-hexagon-npu) |
| NVIDIA Jetson | Native Arm host programs plus CUDA/TensorRT on an integrated GPU. | AGX Thor developer kit/T5000 were announced generally available in August 2025, with 128 GB memory. JetPack and device generation control compatibility. Xavier developer-kit EOL does not mean every Xavier module is unavailable. [Thor launch](https://developer.nvidia.com/blog/?p=104879), [Jetson lifecycle distinctions](https://developer.nvidia.com/embedded/faq) |
| Arm Ethos-U | Vela AOT compilation into supported SoC deployments; TFLite Micro and ExecuTorch routes. | U85 supports INT8 weights and INT8/INT16 activations. This is licensed IP integrated into products, not one generic rentable device. Published FPGA demonstrations do not qualify shipping boards. [Vela](https://arm-software.github.io/CMSIS-Ethos-U/main/vela/index.html), [Ethos-U85](https://newsroom.arm.com/blog/ethos-u85) |
| NXP Neutron | Device-specific compilation of quantized TFLite through eIQ. | i.MX95 is an active product. Host application, RTOS/Linux environment and accelerator artifact depend on SoC. Appropriate for later inference export. [NXP conversion](https://eiq.nxp.com/learning-hub/convQuant/neutron.html), [i.MX95](https://www.nxp.com/products/i.MX95) |
| Hailo | Compiled custom models through Dataflow Compiler and Hailo runtime. | Raspberry Pi AI HAT+ 2 launched January 15, 2026, with Hailo-10H and 8 GB dedicated RAM. Its advertised INT4 TOPS cannot be compared directly with INT8 TOPS. The original AI Kit is no longer in production; replacements exist. [Raspberry Pi launch](https://www.raspberrypi.com/news/introducing-the-raspberry-pi-ai-hat-plus-2-generative-ai-on-raspberry-pi-5/), [product distinctions](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html) |
| Rockchip RKNN | Host-side model conversion and C/C++ or Python target runtime. | Follow the current vendor repository, not the unmaintained predecessor. Qualify exact SoC/compiler/runtime combinations. Arbitrary NPU kernels are not established by model conversion support. [Current RKNN SDK](https://github.com/airockchip/rknn-toolkit2) |
| Coral Edge TPU | Compiled, fully quantized 8-bit TFLite models. | Distinct from Cloud TPU. Unsupported operations can cause CPU execution of the remaining graph. No current stock or long-term availability was established. Suitable only for an explicitly constrained inference-export proposal. [Coral model contract](https://www.coral.withgoogle.com/docs/edgetpu/models-intro/) |

For opaque NPU paths, storage may reside in shared DRAM while execution uses undocumented local buffers and compiler-selected layouts. Shared memory does not prove zero-copy import, coherence, unrestricted CPU access during execution, or stable alignment requirements. Exact accumulator widths, NaN/Inf propagation, subnormal behavior and rounding remain unknown where the cited SDK does not specify them.

**TPUs, custom accelerators and adaptive compute**

| Family | Availability and user programmability | Architecture and workload implications |
|---|---|---|
| Google TPU | Ironwood TPU7x is generally available; TPU8i/8t remain listed as coming soon. Compute Engine/GKE provide programmable access. | Training and inference through XLA; custom Pallas/Mosaic kernels. TPU7x supports JAX/PyTorch and explicitly excludes TensorFlow. Its table lists 192 GiB HBM/chip and 7,380 GB/s. Each chip exposes two chiplet devices with distinct memory spaces. Host RAM, HBM and VMEM are separate tiers. [Product status](https://cloud.google.com/tpu?hl=en), [TPU7x architecture](https://docs.cloud.google.com/tpu/docs/tpu7x) |
| AWS Trainium/Inferentia | Trn3 UltraServers GA announcement is dated December 2, 2025. Trn1/Trn2/Inf2 remain documented. | Trainium supports training/inference; Inferentia is inference-oriented. Neuron compiler/runtime, NKI custom kernels and native `libnrt` C API provide real custom-framework routes. Trainium3 lists 144 GB HBM3e/chip and 4.9 TB/s; NeuronCore-v4 has software-managed SRAM. [Trn3 announcement](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-ec2-trn3-ultraservers/), [runtime C interface](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/neuron-runtime/guides/nrt-developer-guide.html) |
| Groq LPU | Public GroqCloud offers hosted models. GroqWare and ALCF documentation establish separate programmable hardware access. | “Language Processing Unit” is Groq's vendor term. Compiler-scheduled dataflow and graph compilation differ from general CPU execution. Public API access does not grant arbitrary kernel upload or user-controlled device memory. [Groq models](https://console.groq.com/docs/models), [ALCF programming environment](https://docs.alcf.anl.gov/ai-testbed/groq/) |
| Cerebras | CS-3/WSE-3 programming is documented. CS-4 was introduced August 18, 2026; CS-5/CS-6 are roadmap previews. | Training integration and CSL custom dataflow/HPC programming are separate from the inference API. Distributed on-wafer SRAM and explicit fabric communication require placement-aware programs. A local simulator does not establish access to physical hardware or CS-4 SDK compatibility. [CS-4 introduction](https://www.cerebras.ai/blog/introducing-cerebras-cs-4), [CSL SDK](https://www.cerebras.ai/blog/supercharge-your-hpc-research-with-the-cerebras-sdk) |
| SambaNova | Current SN50 offering exists; public positioning emphasizes inference. | SN50 lists 432 MB SRAM, 64 GB HBM2E and up to 512 GB DDR5. SambaFlow creates PEF executables. Older customer documentation supports custom models and training, but does not establish unrestricted current SN50 kernel access or public rental. [RDU specifications](https://sambanova.ai/products/rdu-ai-chips), [SambaFlow guide](https://docs-legacy.sambanova.ai/developer/latest/developer-book.html) |
| Graphcore IPU | Sales/contact and SDK paths remain. Immediate self-service hardware capacity was not verified. | Poplar C++ graphs/codelets support custom computation. Bow Pod16 documents 14.4 GB distributed in-processor memory plus 512 GB streaming memory across sixteen IPUs. Older framework integrations need exact-version review. There is insufficient evidence here to declare the whole product line discontinued. [Access page](https://www.graphcore.ai/getstarted), [Bow memory architecture](https://docs.graphcore.ai/projects/bow-pod16-datasheet/en/latest/product-description.html) |
| Intel Gaudi | IBM documents Gaudi3 under Select Availability, with Linux and quota requirements. | Separate from Intel GPU SYCL. PyTorch, graph compilation and custom TPC kernels support training/inference. IBM's profile contains eight 128 GB accelerators, a substantial allocation rather than a small developer instance. [IBM technical profiles](https://cloud.ibm.com/docs/vpc?topic=vpc-accelerated-profile-family) |
| Tenstorrent | Blackhole developer products were available to order April 3, 2025; Galaxy Blackhole has dated 2026 production/shipping evidence. | TT-Metalium custom kernels, TT-NN and TT-Forge. Explicit core grids, local storage, external-memory transfers and tiled layouts. Embedded RISC-V cores do not make this the ordinary RISC-V CPU backend. Grayskull is a legacy software target. [Developer launch](https://tenstorrent.com/en/newsroom/tenstorrent-launches-blackhole-developer-products-at-tenstorrent-dev-day), [production update](https://tenstorrent.com/newsroom/tt-deploy) |
| Huawei Ascend | Current international cloud documentation confirms particular Ascend inference instances. | CANN, Ascend C and `aclnn` offer graph/custom-operator routes. Retrieved 310-based instances have fixed older software combinations. This does not establish modern 910C training rental or availability in the user's region. [Ascend cloud instances](https://support.huaweicloud.com/intl/en-us/productdesc-ecs/ecs_01_0047.html) |
| AMD/Xilinx FPGA | AWS F2 is a documented programmable rental path. | Up to eight VU47P FPGAs; each has 16 GiB HBM plus 64 GiB DDR4. Custom RTL and supported C/C++/OpenCL flows produce hardware artifacts. Vitis/Vivado, bank allocation, DMA, pipelining and timing closure are part of qualification. [AWS F2](https://aws.amazon.com/ec2/instance-types/f2/) |
| Altera FPGA | RTL/Quartus and a specifically pinned dedicated oneAPI route remain documented. | Old FPGA OpenCL/HLS tools have discontinuance notices. Generic Intel compiler FPGA integration was removed in 2025.1. Altera's dedicated route uses oneAPI 2025.0.1 plus FPGA package 2025.0. Board/BSP and tool licensing are prerequisites. [Dedicated toolchain](https://www.altera.com/products/development-tools/oneAPI-base-toolkit), [OpenCL discontinuance](https://docs.altera.com/r/docs/683177/22.4/fpga-sdk-for-opencl-pro-edition-version-22.4-release-notes/product-discontinuance-notification?contentId=lmo4zlcq5cMnN82VhVLNfQ) |

AWS's generic accelerator table did not include Trn3 when inspected, although the dated GA announcement does. Treat this as catalog inconsistency, not evidence of universal regional availability. The exact instance/access documentation must control a future reservation.

**Numerical policy implications**

The hardware evidence does not support a blanket promise that an IEEE storage type implies identical IEEE execution across all tensor backends.

| Path | Documented distinction | Required A7 treatment |
|---|---|---|
| Intel BF16 instructions | Nearest-even rounding, denormal zeroing/flushing, no normal MXCSR consultation/update | Separate BF16 matrix semantics from scalar f32 semantics. [Intel SDM](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf) |
| Arm BF16 | Earlier BF16 dot/matrix behavior includes round-to-odd and denormal flushing; enhanced behavior depends on architecture features/settings | Record BF16 instruction generation and control state. [Arm BF16 explanation](https://developer.arm.com/community/arm-community-blogs/b/ai-blog/posts/bfloat16-processing-for-neural-networks-on-armv8_2d00_a) |
| CUDA scalar and atomic operations | Compiler flags affect FTZ, division and contraction. Global-memory f32 atomic addition flushes subnormals, unlike shared-memory f32 atomic addition | “Strict kernel” cannot be inferred from one compiler flag. Audit the actual operation selection. [CUDA floating-point rules](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/mathematical-functions.html) |
| CUDA library GEMM | Input/output dtype and compute mode are separate; FP32 storage can use reduced-precision computation | Explicitly select multiplication/accumulation mode. Reproducibility also depends on version, architecture, streams and workspace. [cuBLAS](https://docs.nvidia.com/cuda/cublas/index.html) |
| AMD MI200 matrix operations | Particular FP16/BF16 MFMA paths flush subnormals; documented alternate implementations change precision/range tradeoffs | Scope behavior to generation and library algorithm. [rocBLAS numerical notes](https://rocm.docs.amd.com/projects/rocBLAS/en/docs-6.1.5/API_Reference_Guide.html) |
| TPU BF16 | Conversion uses nearest-even, preserves NaN/Inf, overflows to infinity and flushes BF16 subnormals | Cannot silently implement a gradual-underflow contract through this path. [TPU BF16](https://docs.cloud.google.com/tpu/docs/bfloat16) |
| Neuron | Generation-dependent types; some integer paths narrow or compute through floating point unless specific modes are selected | Preserve exact A7 integer behavior independently of vendor defaults. [Neuron dtype rules](https://awsdocs-neuron.readthedocs-hosted.com/en/v2.32.0/about-neuron/arch/neuron-features/data-types.html) |
| Gaudi TPC | Subnormals treated as zero; fixed output NaN pattern. `float64` names a vector of 64 f32 elements | Do not mistake the identifier for binary64 support. [TPC type specification](https://docs.habana.ai/en/latest/TPC/TPC_C_Language_Spec/Supported_Data_Types.html) |
| Graphcore | Stochastic rounding and configurable half-overflow behavior, including saturation/NaN modes | Pin options and test them. [Poplar floating-point controls](https://docs.graphcore.ai/projects/poplar-api/en/3.2.0/poplar/utility/CSRFunctions.html) |
| Cerebras | f16/bf16 and custom cbfloat16 formats; configurable reduced-precision reductions | A framework proxy dtype must not replace physical-format metadata. [Cerebras precision guide](https://training-api.cerebras.ai/en/2.1.0/wsc/how_to_guides/cs-1-data-formats.html) |
| Tenstorrent | Vendor documentation identifies incomplete special-value behavior for some operations | Requires corrective implementation or an explicitly relaxed profile. [Special-value report](https://github.com/tenstorrent/tt-metal/blob/main/tech_reports/Handling_Special_Value/special_values.md) |
| Vulkan/OpenCL | Width-specific optional FP capabilities, rounding and denormal controls | Query capabilities, request execution modes and reject unsupported contracts. [Vulkan float controls](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceFloatControlsProperties.html), [OpenCL C specification](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_C.html) |
| FPGA floating-point IP | HLS f32/f64 synthesis is documented as partially IEEE-compliant | Qualify the synthesized arithmetic configuration. [Vitis HLS rules](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Floats-and-Doubles) |

Recommended decisions, **not approved policy**:

1. Define storage, multiplication, accumulation and output types separately.
2. Define scalar arithmetic separately from reductions, matrix multiplication and transcendental functions.
3. Make TF32, FP8, reduced-precision multiplication, stochastic rounding and flush-to-zero explicit choices.
4. Specify whether FMA contraction and reassociation are permitted.
5. Define signed-zero, NaN/Inf, overflow, underflow and conversion behavior without promising portable NaN payload identity.
6. Treat integer quantization as a separate contract containing scale, zero point, grouping, rounding and saturation. Ordinary A7 wrapping integers must not inherit quantizer behavior.
7. Separate reproducibility on one pinned implementation from bitwise reproducibility across devices.
8. Require an error or explicitly permitted alternative when a backend cannot meet the requested contract.

A practical initial proposal is f16/bf16 storage with explicitly specified f32 accumulation for selected tensor operations, alongside f32/f64 reference execution. Whether intermediate products, reductions and output conversion follow that proposal remains a language decision.

StableHLO does not settle these questions for A7. Its specification explicitly leaves numerical accuracy guarantees incomplete and describes undefined behavior for some runtime shape mismatches. A7 must discharge its own obligations before emitting such operations. [StableHLO specification, updated August 5, 2026](https://openxla.org/stablehlo/spec)

**Compiler, runtime and ecosystem compatibility**

“Official” below identifies a documented project/vendor integration. It is not an A7 qualification claim.

| Ecosystem | Established connections | Important limits |
|---|---|---|
| JAX | CPU, CUDA, TPU; AMD-maintained ROCm plugin; Intel/Apple plugin efforts | Platform maturity differs. Apple acceleration is experimental rather than a portable baseline. Pin `jaxlib`, plugin and runtime versions. [JAX installation](https://docs.jax.dev/en/latest/installation.html), [project platform table](https://github.com/jax-ml/jax/blob/main/README.md) |
| PyTorch | CPU, CUDA/ROCm; upstream Intel XPU and Apple MPS; vendor integrations for TPU, Neuron, Gaudi and Cerebras | An eager operator working does not establish compiler, backward or custom-op coverage. [PyTorch installation](https://pytorch.org/get-started/locally/), [Intel XPU support](https://pytorch.org/blog/intel-gpu-support-pytorch-2-5/?linkId=100000309607022) |
| TensorFlow | CPU and supported CUDA configurations; vendor-specific alternative integrations | Native Windows/macOS GPU assumptions are unsafe. TPU7x explicitly excludes TensorFlow despite older TPU support. [TensorFlow installation](https://www.tensorflow.org/install/pip), [TPU7x restrictions](https://docs.cloud.google.com/tpu/docs/tpu7x) |
| ONNX Runtime | CPU and execution providers including CUDA, TensorRT, DirectML, OpenVINO, QNN, Core ML and MIGraphX | Provider/operator/version status varies. ROCm EP is deprecated. DirectML is in sustained engineering, with new Windows development directed toward WinML. ONNX import alone is not an ORT EP. [Provider catalog](https://onnxruntime.ai/docs/execution-providers/), [DirectML status](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html) |
| TVM | Target-specific compilation and exportable runtime modules | Requires an exact target/runtime path. Generic TVM support does not prove vendor-maintained qualification of every NPU. [TVM architecture](https://tvm.apache.org/docs/arch/) |
| IREE | Documented CPU, CUDA, ROCm, Vulkan and Metal deployment configurations | Useful optional compiler/runtime integration. MLIR inside another SDK does not automatically make that device an IREE backend. [IREE deployment matrix](https://iree.dev/guides/deployment-configurations/) |
| MLX | Apple CPU/Metal execution, custom kernels and tensor interoperability | f64 is CPU-only in current documentation. Dtype support and operation placement remain separate. [MLX dtypes](https://ml-explore.github.io/mlx/build/html/python/data_types.html) |
| tinygrad | Project-maintained CPU, CUDA/NV, AMD, Metal, Qualcomm/OpenCL and WebGPU runtimes | These are tinygrad implementation paths, not blanket vendor support. Exact hardware requirements differ by runtime. [tinygrad runtime matrix](https://docs.tinygrad.org/runtime/) |
| XLA/PJRT/StableHLO | Graph interchange, compilation and uniform device/plugin interfaces | PJRT is an execution integration boundary; StableHLO is an operation representation. Neither supplies A7's complete ownership, AD or numerical contract. [PJRT](https://openxla.org/xla/pjrt) |

For native distribution, keep vendor C++ and framework ABIs inside adapters. CUDA has documented x86-64, Arm SBSA and cross-compilation routes, but runtime/compiler redistribution is component-specific. Metal requires Apple platform frameworks; metal-cpp is a header interface, not a portable Metal runtime. SYCL likewise needs the relevant compiler runtime and device driver. [CUDA installation/distribution](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/), [metal-cpp](https://developer.apple.com/metal/cpp/)

A Zig cross-compiled executable does not automatically include compatible CUDA, ROCm, Neuron, Apple or NPU binaries. Package host architecture, OS ABI, device code and runtime requirements separately.

**Provider matrix**

All access descriptions concern public documentation. They do not establish account eligibility, immediate stock, quota or a guaranteed regional reservation.

| Provider | Custom A7 execution versus model service | Qualification and cost considerations |
|---|---|---|
| AWS | EC2 CPU/GPU/Neuron/F2 instances can run host programs and supported device artifacts. Managed model APIs are separate. | Pin instance family, host architecture and accelerator count. G5g/Grace-based systems introduce Arm hosts. Use on-demand, Spot or Capacity Block prices for the exact region/configuration. [Accelerator specifications](https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html), [Capacity Block pricing](https://aws.amazon.com/ec2/capacityblocks/pricing/) |
| GCP | Compute Engine GPU VMs and TPU configurations permit custom computation. | GPU price can be additional to VM price; accelerator-optimized configurations have their own totals. Include disks/network. Availability is zone-specific. [GPU types](https://docs.cloud.google.com/compute/docs/gpus), [GPU pricing](https://cloud.google.com/products/compute/gpus-pricing?hl=en) |
| Azure | GPU VM families provide custom execution; hosted model endpoints are separate. | Compute NC/ND families differ from graphics/fractional NV offerings. Verify exact size, driver and usable device partition. [VM family catalog](https://learn.microsoft.com/en-sg/azure/virtual-machines/sizes/overview) |
| CoreWeave | Kubernetes/bare-metal GPU execution and separate managed/serverless inference offerings. | Public pricing distinguishes whole instances from inference-platform per-GPU rates. Do not substitute one for the other. [Getting started](https://docs.coreweave.com/get-started), [pricing](https://coreweave.com/pricing) |
| Lambda | Linux GPU VMs with SSH and selectable images. | Suitable for native binaries/custom kernels. GH200 uses an Arm host. Billing runs while the instance exists/runs, not only while kernels execute; storage can survive termination. [VM documentation](https://docs.lambda.ai/public-cloud/on-demand/), [billing](https://docs.lambda.ai/public-cloud/billing/) |
| Runpod | Pods accept custom containers and SSH. Serverless workers also execute custom code. Public model endpoints are a separate product. | Pods are not unrestricted nested-Docker hosts; documented Windows/UDP limitations apply. Serverless billing includes startup and idle worker time. [Pods](https://docs.runpod.io/pods/overview), [serverless pricing](https://docs.runpod.io/serverless/pricing) |
| Oracle OCI | GPU VMs/bare metal, including documented AMD MI300X/MI355X shapes. | Useful AMD cloud qualification candidate. Verify shape availability and full-node allocation requirements. [Price/shape list](https://www.oracle.com/cloud/price-list/), [MI355X setup](https://docs.oracle.com/en-us/iaas/Content/Compute/gpu-quick-start/amd/MI355X/README-MI355X.htm) |
| Nebius | GPU compute VMs and separate managed offerings. | Public documentation describes per-second billing and bundled GPU/vCPU/RAM charges for certain configurations. Storage remains separately relevant. [Compute pricing](https://docs.nebius.com/compute/resources/pricing) |
| OVHcloud / Scaleway | Regional GPU instances and separate inference products. | European access alternatives. Exact availability zone matters; Scaleway's table explicitly distinguishes unavailable zones. OVH's page includes future October 1, 2026 pricing changes, which must not be treated as already effective. [OVH prices](https://www.ovhcloud.com/en/public-cloud/prices/), [Scaleway GPU prices](https://www.scaleway.com/en/pricing/gpu/) |
| Modal | Custom container/function execution, including GPU training and inference. | Serverless compute is not necessarily a fixed-model API. Include CPU/memory requests, startup and actual execution model in costs. [Execution model](https://modal.com/docs/guide), [pricing](https://modal.com/pricing) |
| AMD Accelerator Cloud | Documented MI355X bare-metal environments. | Credible custom-code research access, subject to admission, terms and capacity. [AMD cloud configurations](https://aac.amd.com/help/bare-metal/whats-new/) |
| IBM Cloud | Documented Gaudi3 instances under Select Availability. | Confirm quota/access before planning qualification. Do not promote marketing availability into an immediate reservation promise. [Gaudi3 profiles](https://cloud.ibm.com/docs/vpc?topic=vpc-accelerated-profile-family) |
| Groq / Cerebras / SambaNova hosted services | Public inference interfaces primarily expose model execution. | Token/request/model customization access does not establish arbitrary A7 runtime or kernel execution. Use separate enterprise/testbed access for backend qualification. |
| Saudi/regional services | Groq reports Dammam traffic since February 2025. HUMAIN publicly exposes hosted model services. | Physical regional deployment is not evidence of customer-controlled hardware rental or selectable request residency. These sources establish service offerings, not A7 backend access. [Groq dated deployment](https://groq.com/newsroom/groq-solidifies-status-as-emerging-hyperscaler-with-new-global-deployment), [HUMAIN Node](https://www.humain.com/en/node.html) |
| On-premises/edge cloud | Azure Local supports documented GPU assignment/partitioning configurations. AWS Outposts has generation-specific offerings. | Requires owned/contracted hardware and supported drivers. Do not assume every regional-cloud GPU SKU exists at the edge. [Azure Local GPU support](https://learn.microsoft.com/en-us/azure/azure-local/manage/gpu-preparation?view=azloc-2604), [Outposts offerings](https://aws.amazon.com/documentation-overview/outposts//) |

No dollar ranking is justified by this review. A valid comparison must record:

- Region, currency, tax treatment and observation date.
- Exact GPU/accelerator variant, memory and count.
- Whole-instance versus per-device pricing.
- Host CPU/RAM, storage, interconnect and egress.
- On-demand, interruptible, reserved or committed terms.
- Compilation, warmup, idle time and failed-run costs.
- For APIs, model identity, input/output token charging and batching.

The useful planning metric is cost per accepted workload result under the same numerical and latency requirements, not advertised cost per GPU-hour or TOPS.

**Recommended A7 backend architecture**

Keep the runtime boundary small and explicit:

```text
A7 semantic analysis and approved lowering plan
                    |
          A7 tensor operations and AD
                    |
       capability-aware execution planning
          /             |              \
   CPU libraries   GPU libraries     graph/device
   and kernels     and kernels       compiler adapters
          \             |              /
       buffers, dependencies, completion, errors
```

Recommended adapter responsibilities:

- Enumerate exact devices and distinguish physical devices from partitions or chiplets.
- Describe supported operations by storage dtype, compute dtype, accumulator, shape, layout, alignment and numerical mode.
- Allocate/import/export buffers with explicit ownership and lifetime.
- Compile/load device artifacts and expose cache compatibility requirements.
- Submit operations with dependencies and report completion/errors.
- Report the actual kernel, algorithm and device selected.
- Distinguish supported forward operations from supported backward operations.

Immutable argument bindings do not eliminate mutation hazards. An asynchronous operation may still read an explicitly mutable referent. A7 must prevent conflicting mutation and premature destruction until completion. Views and exported tensors require the same treatment.

DLPack is useful for interchange, but it does not independently solve these obligations. Its protocol includes lifetime and stream coordination requirements. A7 must also validate shape/stride integer conversions and whether a copy occurred. [DLPack protocol](https://dmlc.github.io/dlpack/latest/python_spec.html)

A backend artifact/cache key should include device architecture, compiler/runtime/library versions, numerical policy, shape specialization, layout, kernel options and relevant topology. A model hash alone is insufficient.

Unsupported behavior should be explicit:

- Reject known unsupported operations during planning.
- Never silently narrow f64, substitute TF32/BF16, change quantization, or downcast exact integers.
- For an explicitly selected device, reject unsupported work unless fallback was explicitly permitted.
- When fallback is permitted, expose CPU partitions and transfer costs.
- Preserve the current compile-time proof rule. Runtime guards for dynamic shapes require an approved contract extension; this report does not authorize that change.

**Ordered backend roadmap**

| Order | Recommended scope | Rationale |
|---|---|---|
| 1 | Approved CPU v1, one primary platform first | Establish tensor semantics, AD, numerics, errors and native packaging |
| 2 | Additional CPU qualification on one Intel x86 and one Arm platform | Detect ISA, ABI and numerical assumptions without accelerator integration complexity |
| 3 | Experimental Strix study and one CUDA prototype | Strix uses available local hardware; CUDA provides accessible programmable cloud hardware and established kernels |
| 4 | Narrow CUDA release candidate | Qualify one GPU/OS/toolchain and the approved classifier/decoder workloads before broader claims |
| 5 | ROCm Instinct plus a separate Radeon/Strix lane | Reuse architectural lessons while respecting different hardware/library matrices |
| 6 | Metal and Intel XPU according to actual users/hardware | Valuable desktop coverage, with distinct dtype and runtime limitations |
| 7 | One TPU or Neuron experiment | TPU offers the XLA ecosystem; Neuron offers a particularly concrete native C runtime boundary |
| 8 | Selected NPU inference export and custom DSP/NPU experiments | Separate model deployment from A7-owned training execution |
| 9 | Tenstorrent, Cerebras, SambaNova, Graphcore, Gaudi or Ascend proposals | Require confirmed physical access, numerical policy and SDK compatibility first |
| 10 | FPGA for a measured fixed workload | Justified by streaming latency, custom precision or I/O requirements, not generic coverage |

Vulkan/IREE can be a parallel portability experiment. They should become supported dependencies only after proving operator coverage, numerical behavior, deployment simplicity and performance for A7's workloads.

**Precise qualification scenarios**

Every qualification record should contain hardware identifiers, memory configuration, firmware, OS/kernel, driver, compiler/runtime/library versions, power mode, model and dataset hashes, tensor shapes, numerical policy and actual device placement.

| Scenario | Prerequisites | Required evidence |
|---|---|---|
| CPU baseline | Named host, pinned native libraries and baseline instruction target | All approved dtypes; forward/backward/optimizer behavior; independent scalar reference; debug/release and clean installation |
| Optimized x86 | Separate Intel and AMD configurations | Actual selected kernels; ISA/OS dispatch; odd dimensions, packing and thread-count sensitivity |
| Arm CPU | One Graviton and/or Apple CPU system | Native artifacts, ABI compatibility, conversion behavior and BF16-feature distinctions |
| Strix GPU | Choose vendor-matrix Ubuntu or explicitly experimental Arch lane | Device enumeration, allocation, library/custom-kernel execution, four dtype dispositions, CPU/GPU synchronization and sustained workload behavior |
| CUDA / ROCm discrete | Exact GPU, compatible driver/toolchain, custom-code access | Classifier and decoder training/inference, operation placement, transfer traces, numerical modes and unsupported-operation behavior |
| Intel NPU / Core ML / QNN | Supported device and pinned graph/compiler/runtime | Fixed-shape classifier; calibrated quantization where required; graph partition report; cold/warm latency; unsupported-op disposition |
| AMD IRON / Hexagon | Supported custom-program SDK and physical device | One matmul/reduction plus its derivative; explicit DMA/lifetime behavior; actual hardware execution |
| TPU / Neuron | Confirmed allocation and compatible graph/native runtime | A7-owned partition invocation; backward/optimizer execution; shape specialization; custom operation; integer and special-value behavior |
| Spatial accelerator | Physical access and compiler entitlement | Custom operation and derivative on hardware; placement, memory and communication evidence. Simulator success is insufficient |
| FPGA | Named board/F2, exact shell/BSP and synthesis tools | Simulation plus hardware execution, timing closure, bitstream identity, DMA behavior and complete latency |
| Edge quantized export | Named Hailo/NXP/RKNN/Coral configuration | Calibration provenance, compiled operator assignment, model accuracy and host/device overhead |
| Hosted API | Public API documentation only for this review | Qualify an application adapter separately. No tensor-backend or AD qualification claim |

For a common proposed test corpus:

- GEMM shapes should include aligned and tail cases, such as `32×32×32` and `17×33×65`.
- Reductions should include lengths `0`, `1`, `31`, `32`, `33`, `255`, `256`, `257`.
- Include contiguous, transposed, sliced and broadcast views.
- Include signed zeros, NaN/Inf, subnormal boundaries, cancellation, overflow and FMA-sensitive inputs.
- Compare gradients with an independent f64 finite-difference/reference implementation at smooth points.
- Exercise a classifier and a small decoder through inference, backward propagation and optimizer updates, including parameter sharing and varying batch/sequence shapes.
- Measure cold compilation, warm execution, host-to-device transfer and end-to-end completion separately.
- Report distributions and memory peaks, not a single throughput number.

These are proposed scenarios. Numerical tolerances and model acceptance thresholds must be agreed before running them. A test that invokes the same vendor kernel through two frameworks is not an independent numerical oracle.

**Open decisions**

The controlling session still needs decisions on:

1. Scalar versus tensor floating-point guarantees.
2. Reduction ordering and FMA/reassociation permissions.
3. Default accumulation and mixed-precision rules.
4. Explicit-device fallback behavior.
5. Dynamic-shape proof and runtime-error policy.
6. Asynchronous borrowing of mutable tensor referents.
7. Canonical versus device-packed serialization.
8. Supported host/OS distribution matrix and optional runtime packaging.
9. Which single GPU configuration earns the first qualification effort.
10. Whether Strix research uses the current experimental Arch environment or a separately approved vendor-supported environment.

Unknown numerical behavior must remain recorded as unknown. This particularly affects opaque NPU accumulators, transcendental accuracy, signed-zero handling, NaN payloads, graph-compiler rewrites and import/coherence guarantees.

Hand off to GLM the security review of driver/runtime loading, device-buffer imports, custom-op boundaries, compiled-artifact loading and remote-service trust boundaries. This report makes no security disposition.

**Dated source ledger**

All linked sources above were checked during this review on **2026-09-14**. This ledger distinguishes dated evidence from mutable documentation.

| Source | Date/version anchor | What it establishes |
|---|---|---|
| AMD EPYC 9005 launch | 2024-10-10 | Shipped CPU family and architectural specifications |
| AWS Trn3 announcement | 2025-12-02 | GA announcement, not universal regional inventory |
| Apple M5 announcement | 2025-10-15 | Product introduction and base-chip specifications |
| Raspberry Pi AI HAT+ 2 | 2026-01-15 | Hailo-10H product launch |
| Qualcomm XNNPACK/Hexagon | 2026-03-23 | Announced kernel integration, not all downstream packages |
| Azure Local GPU documentation | 2026-04-22 update | Supported assignment and partitioning configurations |
| Tenstorrent production update | 2026-05-04 | Production/shipping statement |
| Runpod Pod documentation | 2026-07-20 modification | Custom-container access and runtime limitations |
| Ryzen AI documentation | 1.8.0, 2026-08-03 update | Current documented NPU deployment paths |
| StableHLO specification | 2026-08-05 update | Numerical and shape-contract limitations |
| Cerebras CS-4 introduction | 2026-08-18 | Introduced product, distinct from rental/SDK qualification |
| AWS Graviton5 R9g/R9gd | 2026-08-31 | Region-scoped GA |
| ROCm release notes | 7.14.1, 2026-09-02 | Released SDK anchor for Strix research |
| GCP GPU machine types | 2026-09-03 update | Documented configurations |
| Vendor catalogs, framework docs and price pages | Mutable; accessed 2026-09-14 | Current published offerings and interfaces, not guaranteed stock or future pricing |

The proposed roadmap preserves CPU v1. Its next concrete planning step is to approve the numerical contract and choose a single accelerator qualification configuration, while keeping the remaining hardware families as researched, explicitly unqualified candidates.