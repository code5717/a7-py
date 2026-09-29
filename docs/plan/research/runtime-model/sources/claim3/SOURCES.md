<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim3/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 3 — primary sources
Claim under audit: "Graphics shaders, compute kernels, and ray tracing pipelines recompile
directly into hardware bytecode on every keystroke without tearing the display context,
invalidating pipeline state objects (PSOs), or stalling the command queue. The developer can
modify lighting models, procedural compute passes, or particle simulations live on the GPU
while maintaining the current frame buffer and geometry state."

All quotes below were verified against the saved file with
`tr -s '[:space:]' ' ' < <file> | grep -o -F '<quote>'`.
`vkspec.flat.txt` is a derived copy of `vulkan-pipelines.html` with whitespace collapsed
(`tr -s '[:space:]' ' '`); HTML tags are still present in it. It is used for locating passages
only. Every quote is verified against the saved HTML, not against the derived file.

---

### Vulkan spec — object model immutability
URL: https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html / Saved: vulkan-pipelines.html (41.6 MB) / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "is considered to be immutable, though the content of certain object types is still free to change"
Note: Full sentence in the source reads "Once an object is created or allocated, its &#8220;structure&#8221; is considered to be immutable, though the content of certain object types is still free to change." (typographic quotes are HTML entities, so the clause above is the grep-verifiable span). The "content is still free to change" carve-out covers object types the API gives explicit mutation commands for — device memory (`vkMapMemory`), descriptor sets (`vkUpdateDescriptorSets`), command buffers (`vkBeginCommandBuffer`/`vkCmd*`), pipeline caches (`vkMergePipelineCaches`), query pools. `VkPipeline` is not among them; see the command-surface block below.

### Vulkan spec — what pipeline creation does (§10.14)
URL: https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html / Saved: vulkan-pipelines.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "When a pipeline is created, its state and shaders are compiled into zero or more device-specific executables, which are used when executing commands against that pipeline."
Note: The shader→hardware-executable compile happens at `vkCreateGraphicsPipelines`/`vkCreateComputePipelines`/`vkCreateRayTracingPipelinesKHR` time and is bound to that pipeline object. There is no `vkUpdatePipeline` or `vkSetPipelineShader` in the API — shaders enter only through `pStages` of the create-info.

### Vulkan — the complete `VkPipeline` command surface (no mutator exists)
URL: https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html / Saved: vulkan-pipelines.html / Read: 2026-09-18 / Kind: spec (enumeration, not a quote)
Evidence (reproducible): `grep -o -E 'vk[A-Za-z]*Pipeline[A-Za-z]*' vkspec.flat.txt | sort -u` returns, for non-cache non-layout pipeline commands: vkCreateGraphicsPipelines, vkCreateComputePipelines, vkCreateRayTracingPipelinesKHR, vkCreateRayTracingPipelinesNV, vkCreateExecutionGraphPipelinesAMDX, vkCreateDataGraphPipelinesARM, vkDestroyPipeline, vkCmdBindPipeline, vkCmdBindPipelineShaderGroupNV, vkCmdSetRayTracingPipelineStackSizeKHR, vkCmdUpdatePipelineIndirectBuffer(NV), vkGetPipelineExecutableProperties/Statistics/InternalRepresentationsKHR, vkGetPipelineIndirectDeviceAddress/MemoryRequirementsNV, vkGetPipelinePropertiesEXT, vkGetPipelineKeyKHR, vkUpdateIndirectExecutionSetPipelineEXT.
Note: There is no `vkUpdatePipeline`, no `vkSetPipelineShader`, no pipeline command that accepts SPIR-V. The two commands with "Update" in the name do not edit a pipeline: `vkCmdUpdatePipelineIndirectBuffer` writes a pipeline's indirect metadata into a buffer, and `vkUpdateIndirectExecutionSetPipelineEXT` swaps which whole pipeline handles sit in an indirect execution set. Shader code enters a pipeline only through `pStages` of a `vkCreate*Pipelines` call. Marked as inference from an exhaustive command enumeration, not as a quoted spec sentence.

### Vulkan spec — pipeline binding (§10, vkCmdBindPipeline)
URL: https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html / Saved: vulkan-pipelines.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "Once bound, a pipeline binding affects subsequent commands that interact with the given pipeline type in the command buffer until a different pipeline of the same type is bound to the bind point"
Note: Changing what a draw executes requires binding a *different* pipeline object, i.e. re-recording the command buffer. Does not establish anything about compile latency.

### Vulkan spec — pipeline cache (§10.8)
URL: https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html / Saved: vulkan-pipelines.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "Pipeline cache objects allow the result of pipeline construction to be reused between pipelines and between runs of an application."
Note: Caching mitigates repeat compiles. It does not remove the first compile, and a keystroke that changes shader source is by definition a cache miss.

### Vulkan spec — descriptors / resources are separate from pipelines (§15)
URL: https://registry.khronos.org/vulkan/specs/latest/html/vkspec.html / Saved: vulkan-pipelines.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "opaque data structure used to access shader resources such as buffers, images, or samplers"
Note: Buffers, images and samplers are distinct objects reached through descriptors; destroying and recreating a `VkPipeline` does not destroy them. Supports the "maintaining the current frame buffer and geometry state" part of the claim.

### Vulkan — VkPipelineCreationFeedback
URL: https://registry.khronos.org/vulkan/specs/latest/man/html/VkPipelineCreationFeedback.html / Saved: vk-pipeline-creation-feedback.html / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "is the duration spent creating a pipeline or pipeline stage in nanoseconds."
Note: The API ships a *mechanism* for measuring pipeline creation time. It is evidence that creation time is non-zero and worth measuring; it is not itself a measurement.

### D3D12 — ID3D12PipelineState (reference page)
URL: https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nn-d3d12-id3d12pipelinestate / Saved: d3d12-id3d12pipelinestate.html / Read: 2026-09-18 / Kind: vendor doc (API reference)
Quote (grep-verified): "The only way to change states contained within the pipeline object is to change the currently bound pipeline object."
Quote (grep-verified): "Represents the state of all currently set shaders as well as certain fixed function state objects."
Note: This is the definitional point. `ID3D12PipelineState` exposes exactly one method (`GetCachedBlob`) and no setters. A shader change means a new PSO; the old PSO is replaced, not edited.

### D3D12 — Managing Graphics Pipeline State in Direct3D 12
URL: https://learn.microsoft.com/en-us/windows/win32/direct3d12/managing-graphics-pipeline-state-in-direct3d-12 / Saved: d3d12-managing-pso.html / Read: 2026-09-18 / Kind: vendor doc
Quote (grep-verified): "The bytecode for all shaders including, vertex, pixel, domain, hull, and geometry shaders."
Quote (grep-verified): "were designed to allow the GPU to pre-process all of the dependent settings in each pipeline state, typically during initialization, to make switching between states at render time as efficient as possible."
Note: Shader bytecode is listed among the states set *by the PSO*. The design intent is explicitly front-loaded compilation at initialization. (Full second sentence begins "PSOs in Direct3D&nbsp;12" — that entity is why the quote starts mid-sentence.)

### D3D12 — D3D12_GRAPHICS_PIPELINE_STATE_DESC
URL: https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ns-d3d12-d3d12_graphics_pipeline_state_desc / Saved: d3d12-gfx-pso-desc.html / Read: 2026-09-18 / Kind: vendor doc (API reference)
Quote (grep-verified): "D3D12_SHADER_BYTECODE VS;"
Quote (grep-verified): "structure that describes the vertex shader"
Note: Shader bytecode is a *create-struct member*, not a settable property of the created object. Confirms the "new shader ⇒ new PSO" reading.

### D3D12 — ID3D12PipelineLibrary
URL: https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nn-d3d12-id3d12pipelinelibrary / Saved: d3d12-id3d12pipelinelibrary.html / Read: 2026-09-18 / Kind: vendor doc
Quote (grep-verified): "Adds the input PSO to an internal database with the corresponding name."
Note: D3D12's analogue of `VkPipelineCache`. Same limitation: reuse of already-compiled PSOs, no in-place mutation.
(The conceptual page https://learn.microsoft.com/en-us/windows/win32/direct3d12/pipeline-state-object-library returned HTTP 404 — not readable, no quote.)

### DXR spec — application controls shader compilation because it is expensive
URL: https://raw.githubusercontent.com/Microsoft/DirectX-Specs/master/d3d/Raytracing.md / Saved: d3d12-raytracing-spec.md / Read: 2026-09-18 / Kind: spec (vendor engineering spec)
Quote (grep-verified): "Applications must control when and where (on which threads) shader compilation occurs given the high CPU cost, particularly with large asset bases."
Note: Microsoft's own statement that driver-side RT shader compilation is high-CPU-cost and must be scheduled off the critical path.

### DXR spec — AddToStateObject still produces a NEW object
URL: https://raw.githubusercontent.com/Microsoft/DirectX-Specs/master/d3d/Raytracing.md / Saved: d3d12-raytracing-spec.md / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "Since `AddToStateObject` returns a new state object, this enables the application to free the original object when it is no longer needed"
Note: The closest thing D3D12 has to incremental pipeline editing. Even it creates a new `ID3D12StateObject`; it has no delete counterpart and cannot replace an existing shader in place. Strongest counter-evidence to "without invalidating pipeline state objects".

### D3D12 Work Graphs spec — "generic programs" (the nearest D3D12 analogue to shader objects)
URL: https://raw.githubusercontent.com/microsoft/DirectX-Specs/master/d3d/WorkGraphs.md / Saved: d3d12-workgraphs.md / Read: 2026-09-18 / Kind: spec
Quote (grep-verified): "Generic programs introduce the need to configure graphics pipline state." (typo "pipline" is in the source)
Quote (grep-verified): "Which generic program to set."
Note: The second quote is the `ProgramIdentifier` member of `D3D12_SET_GENERIC_PIPELINE_DESC` — what a command list sets is a program identifier obtained from an already-created `ID3D12StateObject`, so a generic program is still a created, immutable object, not individually bindable shader code. Inference: this is the closest D3D12 analogue to `VK_EXT_shader_object`, and it does not remove the create-an-object step. I found no D3D12 equivalent of shader objects; absence of evidence, established by reading the D3D12 PSO, state-object and work-graph specs fetched here.

### VK_EXT_shader_object — Khronos proposal
URL: https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/main/proposals/VK_EXT_shader_object.adoc / Saved: vk-ext-shader-object-proposal.adoc / Read: 2026-09-18 / Kind: spec (extension proposal)
Quote (grep-verified): "even state that could have been fully dynamic on all implementations was required to be baked into the static pipeline objects"
Quote (grep-verified): "This extension introduces a new object type `VkShaderEXT` which represents a single compiled shader stage."
Quote (grep-verified): "This function compiles the source code for one or more shader stages into `VkShaderEXT` objects."
Note: The escape hatch. Shader objects remove the pipeline object, so "without invalidating PSOs" becomes vacuously true — there are no PSOs. But `vkCreateShadersEXT` still *compiles*, and a source edit still means creating a new `VkShaderEXT`. The compile step and its latency are unchanged.

### VK_EXT_shader_object — Khronos blog
URL: https://www.khronos.org/blog/you-can-use-vulkan-without-pipelines-today / Saved: khronos-blog-shader-object.html / Read: 2026-09-18 / Kind: vendor doc (Khronos blog, 31 March 2023, Daniel Story, Nintendo)
Quote (grep-verified): "In environments where VK_EXT_shader_object is supported, applications can choose to use only pipelines, only shader objects, or an arbitrary mix of the two."
Note: Vulkan-only, and an optional extension — not core, not guaranteed present.

### VK_EXT_graphics_pipeline_library — Khronos proposal
URL: https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/main/proposals/VK_EXT_graphics_pipeline_library.adoc / Saved: vk-ext-gpl-proposal.adoc / Read: 2026-09-18 / Kind: spec (extension proposal)
Quote (grep-verified): "The main aim of this proposal is to reduce the cost of loading novel state and shader combinations within the rendering loop, thus avoiding hitching."
Note: Khronos treats compiling a novel shader/state combination inside the render loop as a known cause of hitching — a whole extension exists to reduce it.

### NVIDIA — RTX Best Practices (ray tracing pipeline cost) — MEASURED
URL: https://developer.nvidia.com/blog/rtx-best-practices/ / Saved: nvidia-rtx-best-practices.html / Read: 2026-09-18 / Kind: vendor doc with figures
Quote (grep-verified): "Avoid State Object creation on the critical path"
Quote (grep-verified): "Collections and pipelines can take tens to hundreds of milliseconds to compile."
Quote (grep-verified): "An application should therefore either create all PSOs upfront (e.g. at level load), or asynchronously create state objects on background threads and hot-swap them when ready."
Quote (grep-verified): "What’s the typical cost of RT PSO compilation in games today?"
Quote (grep-verified): "Anywhere from, 20ms → 300ms, per pipeline."
Quote (grep-verified): "What’s the relationship between number of unique shaders and compilation cost (time) for RT PSOs?"
Note: The best public latency figure found for ray tracing pipeline creation: 20–300 ms per pipeline, roughly linear in unique shader count. This is a vendor statement of typical observed cost, not a published benchmark with methodology. Also the primary source for (c): background-thread creation plus hot-swap-when-ready is the *documented* way to avoid a stall.
Caveat: the page carries an "AI-Generated Summary" block; all quotes above are from the article body, not that block.

### NVIDIA — Vulkan Do's and Don'ts
URL: https://developer.nvidia.com/blog/vulkan-dos-donts/ / Saved: nvidia-vulkan-dos-donts.html / Read: 2026-09-18 / Kind: vendor doc
Quote (grep-verified): "Parallelize command buffer recording, image and buffer creation, descriptor set updates, pipeline creation, and memory allocation / binding."
Note: Pipeline creation is guidance-level a background-thread activity on Vulkan too.

### Unreal Engine — PSO Precaching (hitch threshold)
URL: https://dev.epicgames.com/documentation/en-us/unreal-engine/pso-precaching-for-unreal-engine / Saved: ue-pso-precaching.html / Read: 2026-09-18 / Kind: project doc (engine documentation)
Quote (grep-verified): "A PSO compilation is marked as a hitch if the compilation took longer than a certain amount of milliseconds for the runtime PSO to be compiled."
Quote (grep-verified): "The default value of 20 milliseconds is high because the first hits on the driver cache can take a long time."
Note: A shipping engine defines runtime PSO compilation as a *hitch* and instruments it (`r.PSO.RuntimeCreationHitchThreshold`, default 20 ms). Direct evidence that compiling a pipeline during rendering stalls the frame.

### Unreal Engine — Shader Development (hot reload workflow)
URL: https://dev.epicgames.com/documentation/en-us/unreal-engine/shader-development-in-unreal-engine / Saved: ue-shader-development.html / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified): "If you change a file that is included in many shaders (such as, common.usf), this can take a while."
Note: UE's live shader iteration is a manual `recompileshaders changed` command (Ctrl+Shift+.), explicitly not per-keystroke, and explicitly slow for widely-included files.

### Unity — Shader loading
URL: https://docs.unity3d.com/Manual/shader-loading.html / Saved: unity-shader-loading.html / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified): "Fixing hitches or stalls"
Note: Unity files shader loading/compilation under a documentation section named for the hitches and stalls it causes. (https://docs.unity3d.com/Manual/prevent-shader-stutter.html returned HTTP 404 — not readable, no quote.)

### Bonzomatic — live shader coding tool (existence proof at small scale)
URL: https://raw.githubusercontent.com/Gargaj/Bonzomatic/master/README.md / Saved: bonzomatic-readme.md / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified): "This is a live-coding tool, where you can write a 2D fragment/pixel shader while it is running in the background."
Quote (grep-verified): "F5 or Ctrl-R: recompile shader"
Note: Live shader editing is real — for ONE 2D fragment shader. INFERENCE (not stated by the README): because recompile is bound to F5/Ctrl-R, the tool recompiles on an explicit keypress rather than on every keystroke; the README documents the binding but does not say anything about per-keystroke behaviour. The scale gap versus "ray tracing pipelines" with many hit groups is several orders of magnitude.

### Khronos Vulkan Samples — pipeline cache sample (MEASURED, on-device)
URL: https://docs.vulkan.org/samples/latest/samples/performance/pipeline_cache/README.html / Saved: vk-sample-pipeline-cache.html / Read: 2026-09-18 / Kind: measured result (vendor/Khronos sample write-up)
Quote (grep-verified): "Pipeline cache is enabled and Sponza is rendered at 60 FPS when the existing pipelines are destroyed."
Quote (grep-verified): "Pipeline re-creation takes 24.4 ms thanks to the pipeline cache."
Quote (grep-verified): "If we disable the pipeline cache, re-creating the pipelines takes 50.4 ms, more than double the previous time."
Quote (grep-verified): "The driver then needs to rebuild the pipeline which includes shader compilation, an expensive operation."
Quote (grep-verified): "Building pipelines dynamically without a pipeline cache can result in a sudden framerate drop."
Note: The only wall-clock measurement of driver-side pipeline (re)creation I could find from a first-party source: 50.4 ms cold, 24.4 ms warm, for the Sponza scene on a Mali G76 phone. At 60 FPS the frame budget is 16.7 ms, so a cold rebuild is roughly three frames. This is a whole-scene rebuild, not a single shader, and it is a mobile GPU — read it as an order-of-magnitude anchor, not as the cost of one keystroke.

### Godot — Reducing stutter from shader (pipeline) compilations
URL: https://docs.godotengine.org/en/stable/tutorials/performance/pipeline_compilations.html / Saved: godot-pipeline-compilations.html / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified): "Before Godot 4.4, there was no solution to pipeline compilation other than generating them when an object shows up inside the camera's view, leading to the infamous"
Quote (grep-verified): "or hitches that only occur during the first playthrough."
Quote (grep-verified): "The engine does not currently feature precompilation for 2D elements and stutters will show up when the 2D node is drawn for the first time."
Note: A third engine independently documents that compiling a pipeline during rendering produces a visible stutter, and that the fix is precompilation/ubershaders — not in-place shader editing.

### Unreal Engine — Optimizing Rendering With PSO Caches (100+ ms figure)
URL: https://dev.epicgames.com/documentation/en-us/unreal-engine/optimizing-rendering-with-pso-caches-in-unreal-engine / Saved: ue-pso-caches.html / Read: 2026-09-18 / Kind: project doc
Quote (grep-verified): "Although this greatly improves rendering efficiency, generating a new PSO on-demand can take 100 or more milliseconds, as the application has to configure every possible parameter."
Quote (grep-verified): "This makes it necessary to generate PSOs long before they are needed for them to be efficient."
Note: Epic's own figure for on-demand PSO creation: 100+ ms. A vendor statement, not a benchmark with methodology, but it is the largest first-party non-RT number found and it is six frames at 60 FPS.

### D3D12 — Advanced Shader Delivery, State Object Database
URL: https://raw.githubusercontent.com/microsoft/DirectX-Specs/master/d3d/StateObjectDatabase.md / Saved: d3d12-state-object-database.md / Read: 2026-09-18 / Kind: spec (vendor engineering spec)
Quote (grep-verified): "For example, this could enable modifying a shader without modifying the calling code that references it by key."
Quote (grep-verified): "This version number is used to match with precompiled binaries in a separate database."
Note: Microsoft's newest shader-delivery design still treats "modifying a shader" as producing a new *version* of an object, matched against separately precompiled binaries. Even the forward-looking design has no in-place shader edit; it moves the compile offline instead.

### GLM-5.3-flash lookup (SECONDARY — treat as unverified)
Path: tmp/glm/claim3-shader-compile-latency.md / Read: 2026-09-18 / Kind: LLM-assisted secondary lookup
Note: RETURNED NOTHING USABLE. The delegated question covered measured shader/pipeline compile latency, zero-stall hot-reload claims in shipping engines, and any in-place PSO mutation API. Every web search the model issued failed with "MCP error -429 ... Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-09-22", so the file contains only error traces and no sourced claims. As of the last check it was still retrying, with no "claims checked: N" line and no exit code written. Nothing from it is used in the ruling. Recorded here for completeness; not a primary source.
