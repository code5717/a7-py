# Zig GPU evidence digest, 2026-10-07

This digest preserves the observations supporting the
[research report](../../2026-10-07-zig-gpu-support.md) and the deferred Vulkan
proposal. Under [L75](../../../plan/decisions.md), GPU execution remains deferred.
No shader dispatch, training, performance or A7 GPU backend is qualified.

## Source records

[sources.json](sources.json) preserves 14 historical retrieval records, including
URLs, UTC timestamps, SHA-256 values and HTTP failures. Retrieval ran on
2026-10-06 UTC, October 7 in Riyadh. The source archive hashes matched the
captured official download index:

| Archive revision | SHA-256 |
| --- | --- |
| Zig 0.16.0 | `43186959edc87d5c7a1be7b7d2a25efffd22ce5807c7af99067f86f99641bfdf` |
| Zig 0.17.0 | `b6c7f1728f043700d6529bac980800792f824256a9d2f1839b3d62beed0b8abd` |
| Zig 0.18.0-dev.35+5e754304d | `3b887a946adb8fbe57a1e77298794a45599c8ac979ee7a0e13d52a94dc84d94c` |

The installed compiler reported `0.16.0`. Its recorded binary SHA-256 was
`2317bbb91798556d9d0f38aabdac23db83f0979b25f767259ae474546724087c`.
No newer compiler binary was installed or run. The archive index supplied release
dates April 13 for 0.16.0, October 1 for 0.17.0, and October 5 for the development
snapshot. These are historical observations, not a current latest-version check.

## Compile-only probes

[compile-probes.json](compile-probes.json) contains all four exact Zig input
texts, their hashes, six compiler argument lists, return codes and diagnostics.
Only the absolute checkout prefix is sanitized to `${REPO}`. Every compiler
inherited CPU affinity 12-15 from its Python parent. Caches and outputs were
under the task's scratch directory. Negative subprocess return codes identify
signals, not shell exit codes.

| Probe | Return code | Recorded output |
| --- | --- | --- |
| SPIR-V empty kernel | -11 | Empty stdout/stderr |
| SPIR-V atomic variant | -11 | Empty stdout/stderr |
| AMDGCN empty kernel | 0 | Empty stdout/stderr; object emitted |
| NVPTX binary output | 1 | `error: cannot emit nvptx64 binary with the LLVM backend; only '-femit-asm' is supported` |
| NVPTX assembly, default CPU | -6 | `LLVM ERROR: .alias requires PTX version >= 6.3 and sm_30` |
| NVPTX assembly, sm_80 | -6 | `LLVM ERROR: NVPTX aliasee must be a non-kernel function definition` |

`file amdgcn_empty.o` reported an ELF 64-bit LSB relocatable AMD GPU object,
architecture version 1, with debug information, not stripped. The JSON retains
its hash. The two SPIR-V output files and the final PTX output were empty; their
hashes must not be interpreted as successful device artifacts. These probes did
not load or execute any output. No crash stack or root cause was established.

## Local inventory

The prior query reported Linux kernel `7.2.5-3-omarchy`, driver `amdgpu`, and
these Vulkan values:

```text
loader_api=1.4.357
physical_devices=1
device[0]=AMD Radeon 890M Graphics (RADV STRIX1)
vendor=1002 device=150e type=1
device_api=1.4.354
driver_version=26.2.2
driver_name=radv
driver_info=Mesa 26.2.2-arch1.1
conformance=1.4.5.3
compute_shared_memory=65536
compute_invocations=1024
compute_group_count=4294967295,65535,65535
compute_group_size=1024,1024,1024
shader_float64=1 shader_int64=1 shader_int16=1
queue[0] count=1 flags=0xf compute=yes graphics=yes transfer=yes timestamp_bits=64
queue[1] count=4 flags=0xe compute=yes graphics=no transfer=yes timestamp_bits=64
queue[2] count=1 flags=0x20 compute=no graphics=no transfer=no timestamp_bits=64
queue[3] count=1 flags=0x40 compute=no graphics=no transfer=no timestamp_bits=64
queue[4] count=1 flags=0x8 compute=no graphics=no transfer=no timestamp_bits=0
```

The C query created a Vulkan instance and enumerated physical-device properties.
It did not create a logical device, allocate GPU memory or submit commands.
The inventory README records this build/query recipe from the repository root:

```sh
taskset -c 12-15 cc -Wall -Wextra -Werror -I tmp/v1-completion-2026-10-07/gpu/headers tmp/v1-completion-2026-10-07/gpu/query.c -lvulkan -o tmp/v1-completion-2026-10-07/gpu/query
taskset -c 12-15 tmp/v1-completion-2026-10-07/gpu/query
```

The initial actual build was single-process without affinity; the query and
subsequent enumeration were pinned. Thus the pinned build line is the recorded
rerun recipe, not a claim about that initial invocation. The query source and
headers remain local archive material, so the recipe is not runnable from a
published checkout alone. Headers came from Khronos Vulkan-Headers `v1.4.357`;
no system development package was installed.

The tool inventory found `/usr/bin/cc`, `clang`, `glslc`, `glslangValidator`, and
`spirv-as`. It did not find `vulkaninfo`, `clinfo`, `rocminfo`, `hipcc`, or `nvcc`
on PATH. `clGetPlatformIDs` returned -1001 and zero platforms. The saved tool
record contains that result but not the original Python invocation; this digest
does not reconstruct an unrecorded command. Shaderc package version was
`2026.3-1`, glslang `1:1.4.357.0-1`, and spirv-tools `1:1.4.357.0-1`.
The advertised core features do not establish shaderFloat16 or storage16 support.

## Archive and qualification limits

Raw local material remains under `tmp/v1-completion-2026-10-07/gpu/` and
`tmp/v1-completion-2026-10-07/zig-gpu-research/`. Those ignored paths are local
archive references, not publication links. Large source archives, extracted
upstream trees, binaries and raw HTML are not included in this digest.

The original `probe-sha256.json` recorded a sources.json hash before later source
retrievals extended that manifest. That historical hash does not identify the
final manifest; this digest deliberately omits it. The tracked source manifest
is copied from the final archive record. CPU probe timestamps and an exact A7
checkout commit were not recorded with the probe results. Compiler binary and
input hashes identify the tested compiler/input boundary instead.

Publication checks do not rerun these observations. Queue enumeration establishes
API discovery only. Compiler acceptance establishes output emission only.
Neither is GPU execution evidence, and this digest grants no execution approval.
