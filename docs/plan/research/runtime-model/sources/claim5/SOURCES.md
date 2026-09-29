<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim5/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 5 sources — zero-copy unified memory coherency

All read 2026-09-18. Quotes grep-verified against the saved `.txt` renderings.
Ruling depth only: under EVALUATION.md this claim depends on hardware A7 does
not target, so three primary sources were taken rather than a full sweep.

### D3D12 heap types
URL: https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ne-d3d12-d3d12_heap_type
Saved: d3d12_gpuupload.html / .txt
Kind: vendor spec
Quote: "This heap type experiences the most bandwidth for the GPU, but cannot provide CPU access."  (on `D3D12_HEAP_TYPE_DEFAULT`)
Quote: "This heap type has CPU access optimized for uploading to the GPU, but does not experience the maximum amount of bandwidth for the GPU."  (on `D3D12_HEAP_TYPE_UPLOAD`)
Quote: "The CPU address for such heaps is commonly not efficient for CPU reads."
Note: The staging buffer exists because the memory the GPU reads fastest is not CPU-accessible at all on a discrete part. `D3D12_HEAP_TYPE_GPU_UPLOAD` is present in the enum; the page does not describe it in the constants list captured here.

### Vulkan VkMemoryPropertyFlagBits
URL: https://registry.khronos.org/vulkan/specs/latest/man/html/VkMemoryPropertyFlagBits.html
Saved: vk_memprops.html / .txt
Kind: spec
Quote: "VK_MEMORY_PROPERTY_HOST_COHERENT_BIT bit specifies that the host cache management commands vkFlushMappedMemoryRanges and vkInvalidateMappedMemoryRanges are not needed to manage availability and visibility on the host."
Quote: "Host memory read accesses to uncached memory are slower than to cached memory, however uncached memory is always host coherent."
Note: Coherence is a per-memory-type property, not a guarantee. Where it is absent the program must issue explicit flush and invalidate calls; where it is present it is often bought by making the mapping uncached on the CPU. Either way there is a cost the claim does not name.

### NVIDIA developer blog, "Maximizing Unified Memory Performance in CUDA"
URL: https://developer.nvidia.com/blog/maximizing-unified-memory-performance-cuda/
Saved: nv_um.html / .txt
Dated on the page: Nov 19, 2017. Hardware: Pascal and Volta, PCIe and NVLink.
Kind: vendor blog with measured results
Quote: "Still it&#8217;s almost 2x slower (5.4GB/s) than prefetching (10.9GB/s) or explicit memory copy (11.4GB/s) for PCIe."
Quote: "This fault handling adds significant overhead to streaming performance of Unified Memory on current generation GPU architectures."
Quote: "any outstanding translations can proceed but any new translations will be stalled until all faults are resolved"
Note: A measured price for "direct, instant access" on a discrete GPU: roughly half the bandwidth of an explicit copy. The figures are from 2017 hardware; they establish the mechanism and its order of magnitude, not today's numbers. The page also carries an "AI-Generated Summary" block — quotes above are from the body text, not that block.

## Not obtained
- Apple Metal resource storage mode documentation: developer.apple.com pages are JavaScript-rendered. Delegated to a GLM lookup; see `tmp/glm/rm-claim5.md` and treat as UNVERIFIED.
- NPU memory-model documentation (Qualcomm QNN, Intel Level Zero NPU, Apple ANE): not obtained.
- OpenCL SVM specification text: not obtained.
