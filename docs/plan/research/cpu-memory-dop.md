# CPU memory and data-oriented programming for model inference

Status: advisory research, 2026-09-30. No report approves a language change,
verifies an implementation, or qualifies a release. User decisions live in
`docs/plan/decisions.md`. The v1 plan turns recommendations into approval gates.

Scope: user asked for model optimization on CPU across 8 items plus deep
research on data-oriented programming (DOP), then a brainstorm on how a7 can
compile to data-oriented exported code. This file records all three. Code
claims cite `a7-py` files and lines checked 2026-09-30. External numbers come
from web search 2024-2026 and are marked as such.

## 1. Virtual memory vs physical memory

Each process sees its own flat range, `0..2^48-1` on x86-64. RAM lives in a
separate physical range. The OS maps virtual pages to physical frames.

Unit is 4KB (`PAGE_SHIFT=12`). Benefits: isolation, swapping, `mmap` of files
larger than RAM, copy-on-write.

For models: 7B FP16 ~14GB = ~3.5M 4KB pages. 70B FP16 ~140GB. 671B GGUF
~400GB = ~100M pages. The weight file looks contiguous in virtual space but is
split in RAM. If the working set exceeds RAM, the OS swaps and tok/s drops
10-100x.

Fix: keep hot weights and KV-cache resident. Quantize or stream the rest.

## 2. Page table

A radix tree. 48-bit address splits as `9+9+9+9+12`:

```text
CR3 -> PML4 -> PDP -> PD -> PT -> offset[11:0]
```

Each level is one 4KB page with 512 8-byte entries. `PS=1` at PDP gives a 1GB
page. `PS=1` at PD gives a 2MB page. No PT level is needed then.

Table cost for 4KB pages is ~8MB per GB mapped, plus upper levels. 2MB pages
cut page count 512x. 1GB pages cut it 262144x.

For models: a 400GB model needs ~100M 4KB entries but only ~200K 2MB entries
or ~400 1GB entries. Fewer entries means less table memory and fewer misses.

Sources: kernel.org `page_tables.html`, kernel-internals.org x86 page tables,
ASPLOS'20 Elastic Cuckoo, llama.cpp issue 12444 (2025 hugetlb test, ~10x load
speedup on 1.5TB box with 2MB-aligned mmap).

## 3. MMU

Hardware that translates every load, store, and fetch through the page table.
Fast path is a TLB hit and costs ~0 extra cycles. Slow path is a hardware
page walk that reads tables from cache or DRAM.

Walk cost with paging-structure caches: ~20-60 cycles typical. Worst case with
4 DRAM reads: ~320-400ns, 1000+ cycles at 3GHz. Studies: HPCA'17 avg 58
cycles, MICRO'20 avg 50.9 cycles, Ivy Bridge study 20-150 cycles by workload.

For models: decode streams all weights once per token. Extra walks subtract
directly from tok/s. Random KV gather across long context defeats walk-cache
locality.

## 4. TLB

Cache of `VPN -> PFN` entries. Split L1 per size plus unified L2.

| CPU | L1 DTLB | L2 TLB |
| --- | --- | --- |
| Skylake | 64x4KB + 32x2MB + 4x1GB | 1536 shared + 16x1GB |
| Zen 4 | 72 entries | 3072 |
| Zen 5 | 96 entries, 48KB D-L1 | 4096 DTLB, 2048 ITLB |
| Golden Cove / Sapphire Rapids | ~64 + 256 ITLB | 2048 |

Coverage math is the key number:

* 64 x 4KB = 256KB. 1536 x 4KB = 6MB.
* 72 x 4KB = 288KB. 3072 x 4KB = 12MB.
* 96 x 4KB = 384KB. 4096 x 4KB = 16MB.
* 32 x 2MB = 64MB L1. 1536 x 2MB = 3GB L2.
* 1GB of working set at 4KB = 262144 pages, far above any TLB. At 2MB it is
  512 pages and fits.

Linux THP auto-merges anon memory `512x4KB -> 1x2MB`. Controls:
`/sys/kernel/mm/transparent_hugepage/enabled`, `MADV_HUGEPAGE`,
`MADV_COLLAPSE`. Dense weights and KV arenas are ideal: contiguous and
long-lived. Sparse heaps are not.

Check with `perf stat -e dTLB-load-misses,dTLB-loads,page-faults` and
`grep AnonHugePages /proc/meminfo`. Small resident models often show no gain
from THP (llama.cpp issue 2251). Large, cold, or swapping models do.

## 5. L1/L2/L3 caches

Line size is 64B on all x86-64 below. Rough order:
regs (~1c) < L1 (~4-5c) < L2 (~14-16c) < L3 (~40-100c) < DRAM (~200-400c).

| CPU | L1 | L2 | L3 |
| --- | --- | --- | --- |
| Zen 4 | 32KB I + 32KB D, 4c | 1MB/core, 14c | 32MB/CCD, ~46-50c |
| Zen 5 | 32KB I + 48KB D, 4c | 1MB/core 16-way, ~64B/clk | -3.5c vs Zen 4 |
| Sapphire Rapids | 32KB I + 48KB D | 2MB/core, 16c | up to 112.5MB mesh, ~33ns |
| Raptor Lake P | 32KB I + 48KB D | 2MB, 16c | up to 36MB shared |

Decode at batch=1 is GEMV: each weight is read once per token and never
reused. It is bound by DRAM bandwidth:

```text
tok/s ~= DRAM_BW / model_bytes
7B FP16 14GB at 40GB/s ~= 2.8 tok/s, at 300GB/s ~= 21 tok/s
7B INT4 3.5GB ~= 4x faster
```

Prefill is GEMM and compute-bound. Tiling matters there: keep `Mc x Kc` in
L1, `Kc x Nc` in L2, panel in L3, pack to linear buffers, run `Mr x Nr`
register micro-kernel (for example 8x6 AVX2). Reported speedups of 17-42x over
naive triple loops come from this plus SIMD plus threads.

Quantization wins decode because decode is traffic-bound. Weight-only INT4
loads a tile, dequantizes on the fly, then runs FMA. Fused dequant plus GEMV
hides the cost. llama.cpp GGUF `Q4_0/Q8_0` picks AVX2/AVX-512/VNNI kernels.

## 6. Cache coherence (MESI)

Each 64B line in each private cache is in one state:

| State | Meaning | Silent write? |
| --- | --- | --- |
| M Modified | Only copy, dirty | yes |
| E Exclusive | Only copy, clean | yes, becomes M |
| S Shared | May exist elsewhere, clean | no, must invalidate others |
| I Invalid | Garbage | no, must fetch |

Local rules: read miss with no other copy fetches from DRAM and lands in E.
Read miss with another copy lands in S on both sides. Write hit on S sends an
invalidate and moves to M. Write miss sends read-with-intent-to-modify.
Real chips use MESIF/MOESI plus directories. The model is the same.

For models: weights are read-only during decode, so lines stay S and copy
freely. No invalidations. Activations and partial sums must stay private E/M.
Tensor-parallel allreduce is the one true-sharing point. Accumulate locally,
then merge once or use a tree.

## 7. False sharing

Coherence tracks lines, not bytes. If core 0 writes `a` and core 1 writes `b`
and both sit on the same 64B line, the line bounces even though the threads
share nothing:

```c
struct { float v; char pad[60]; } sums[8]; /* one line per thread */
```

Bad sign: scales worse with more threads, vanishes at 1 thread, `HITM > 5%`
on one line in `perf c2c`. Fix: `alignas(64)`, per-thread scratch on 64B
bounds, per-CPU counters plus periodic global sync.

Detect:

```bash
perf c2c record -ag -- ./decode -t 16
perf c2c report
```

For tensor-parallel GEMV: shard weight rows, stream each shard, write disjoint
64B-aligned output chunks, one barrier, one reduction. Do not pack per-thread
progress counters or KV header fields into one struct.

## 8. mmap(2)/munmap(2) and a7

### 8.1 How runtimes use it

`mmap(NULL, len, PROT_READ, MAP_SHARED|PRIVATE, fd, off)` maps file pages
into virtual space. No `read` plus `memcpy`. Pages fault in on first touch.
Clean pages drop under pressure without swap I/O. The fd can close right
after `mmap`.

llama.cpp (`src/llama-mmap.cpp`) uses `MAP_SHARED` plus `PROT_READ`, then:

* `posix_fadvise(SEQUENTIAL)` on open
* `MAP_POPULATE` only when no lazy GPU ranges exist
* `madvise(WILLNEED)` on dense ranges, `RANDOM` on lazy/NUMA ranges
* `munmap` of fragments moved to GPU
* `mlock` path for low jitter, with `RLIMIT_MEMLOCK` check

GGUF (`ggml/docs/gguf.md`): magic plus version plus tensor infos plus padding
to `ALIGNMENT` (default 32), then raw `tensor_data`. Loader parses a small
header, then serves `tensor_ptr = base + data_off + info.offset`. No bulk
parse.

safetensors: 8B header length plus JSON `{dtype, shape, data_offsets}` plus
raw buffer. `safe_open` plus `get_tensor` faults in only touched tensors.
`torch.UntypedStorage.from_file(shared, nbytes)` selects `MAP_SHARED` vs
`MAP_PRIVATE`. Default backend is `mmap`, optional `pread` for network FS or
tiny subsets.

`madvise` cheat sheet: `WILLNEED` async prefetch, `RANDOM` no readahead,
`SEQUENTIAL` aggressive readahead, `DONTNEED` destructive drop, `HUGEPAGE`
THP hint. `mlock` wires pages and stops swap but costs startup time, full
RSS, and possible OOM. NUMA default is first-touch: one prefetcher puts all
weights on one node, so interleave or per-worker faulting matters.

Pitfalls: decode-time major faults, `kswapd` burn near full RSS, `SIGBUS` on
truncated files past EOF, page-aligned offsets, `fork` plus `MAP_PRIVATE`
copy-on-write blowup, `DONTNEED` as data loss on anon maps.

Zig API (`lib/std/os/linux.zig`): raw `mmap/munmap/mprotect/msync/mlock/
munlock/mlock2/mlockall/madvise` returning raw `usize` errno, plus portable
`std.posix.mmap` returning a slice, plus `std.fs.File.createMemoryMap`.

### 8.2 a7 audit

| Fact | Evidence |
| --- | --- |
| No mmap/munmap/madvise/mlock in compiler or emit | `grep mmap\|munmap\|madvise\|mlock\|mprotect` over `a7/*.py` returns zero hits |
| Allocator is profile-gated, two lines only | `a7/backends/zig.py:183` release `smp_allocator`, `:185` debug `page_allocator` |
| `new` lowers to create/alloc, `del` to destroy | `a7/backends/zig.py:2174-2185`, `:1509-1515` |
| `new [N]T` rejected | `a7/passes/type_checker.py:3366-3373`, `AGENTS.md` source rules |
| Slice/array layout: `[N]T` owns, `[]T` views | `a7/types.py:149-196`, `a7/backends/zig.py:2282-2307` |
| `ref` is nullable `?*T`, no public `&`/`*` | `a7/parser.py:676-684`, `a7/backends/zig.py:1979-2005` |
| stdlib `mem` and `string` are empty stubs | `a7/stdlib/mem.py:1-9`, `a7/stdlib/string.py:1-9` |
| Safety proofs cover index/slice/ref/use-after-del | `docs/SAFETY_CONTRACT.md:50-67`, `a7/safety.py:215-224,814-815,982-1001` |
| Benches stress churn and walks, not mapping | `bench/alloc_churn.a7`, `bench/array_walk.a7`, `bench/vector_ops.a7` |

Missing for weight loading: file and mapping surface, large read-only buffer
type, allocator choice and alignment control, header and shape validation,
`mlock/madvise` policy, and lifetime rules for mapped storage. Plan notes
already say v1 should read rather than map (`docs/plan/research/memory/
review/glm-security.md`, `docs/plan/memory.md:630,646`).

## 9. Data-oriented programming

a7 cites JAI (design philosophy) and Odin (procedures, data-oriented
programming) in `README.md:9-12`.

Core ideas, from Acton CppCon14, Blow JAI demos, Odin docs:

* SoA vs AoS vs AoSoA. SoA wins when a loop touches a subset. AoS wins when
  the whole record moves together. AoSoA (tile = SIMD width or line) keeps
  both. Intel SDLT example: AoS loop 69 AVX2 insns, SoA 19.
* Hot/cold split. Hot fields stay dense. Cold fields move behind an index.
  Split only when cold is large and rarely used.
* Sequential access. Dense `0..n` arrays prefetch. Pointer chase does not.
  Use full 64B lines. Align to 64B for AVX-512.
* Branch cuts. Hoist `if` out of loops. Sort or bucket by type. Swap-remove
  dead items and keep `n_active`. Use masks and `select` in SIMD lanes.
* SIMD needs: contiguous, aligned, independent, no alias, known trip count.

```c
/* AoS, loads unused fields */
struct P { float x, y, vx, vy; int hp; } *a;
/* SoA, one stream per field */
void step(float *x, float *vx, int *hp, int n, float dt);
```

ECS is the same idea for games: entities are ids, components are SoA
columns, systems are tight loops. Archetype tables iterate fast. Sparse sets
add and remove fast.

Transformer as DOP:

* Weights: blocked plus repacked plus quantized. `block_q4_0x4` interleaves
  scales then quants so one SIMD load feeds 4 rows.
* KV-cache per token: `2 * layers * n_kv * head_dim * bytes`. Llama2-70B fp16
  at 4k context is ~1.3GB. CPU layout `[n_page, n_kv, P, Dh]` with `P=16/32/
  128` keeps one head read sequential. GQA/MQA/MLA and sliding windows cut
  bytes. PagedAttention `(blocks, 16, n_kv, dh)` cuts padding and allows
  prefix sharing.
* Activations: fuse attention, skip padding with ragged reads, chunk prefill
  to reuse weights.

## 10. Brainstorm: a7 compiling to data-oriented code

Goal: A7 states intent, exported Zig shows plain loops over dense arrays. No
hidden alloc, no virtual call, no chase in the hot path. All items below are
proposals. Each needs explicit approval with current vs proposed A7, Zig
output, and compat impact before build, per `AGENTS.md`.

Phase 0, no syntax:

* Add `soa_walk`, `false_share`, and `kv_append` benches next to
  `array_walk` and `alloc_churn`. Prove layout wins before changing syntax.
* Add `a7 check --layout` view: struct size, line use percent, hot bytes per
  step. Catches 96B structs walked per frame early.

Phase 1, additive attributes:

* `align(64)` and `pad` lower to Zig `align(64)`. Fixes AVX-512 and false
  sharing. Old code unchanged.
* `hot` and `cold` field groups. Compiler reorders so hot fields pack first.
  Cold moves to a side table.
* `noalias` on `ref` slices. Safety pass already proves bounds. Add overlap
  proof so Zig can emit restrict-style code.

Phase 2, layout types:

* `soa struct` flips AoS to SoA in codegen. Same access `p.x[i]` lowers to
  column `p_x[i]`. One keyword change, no loop rewrite, same idea as JAI and
  Odin `#soa`.
* `Tensor[D0,D1]` with `block(32,8)` hint. Rejects strided access at check
  time. Reuses the `@Vector` path already used for `[N]+[N]` at
  `a7/backends/zig.py:1595-1614`.
* Owned `Bytes` plus `read` loader with header checks (`size` cap,
  `off+len<=file`, no overlap) before any map fast path. Answers truncation
  and `SIGBUS` class.

Phase 3, mapping and arenas:

* Arena and pool choice per `new`, not profile default. KV arena is one anon
  map plus `MADV_HUGEPAGE`, bumped per token, freed once.
* `mmap/madvise/mlock` binding plus `unmap_fragment` for GPU-offloaded
  layers, mirroring llama.cpp. Needs file-size validation, OOM and IO error
  returns, and `del`-compatible ownership first.

## Sources

* kernel.org page tables, transhuge; Intel VTune page-fault cookbook;
  7-cpu.com Skylake; Chips and Cheese Zen 4; AMD Hot Chips 2024 Zen 5;
  Wikipedia Zen 4/5, Sapphire Rapids, Raptor Lake; Phoronix AVX-512 2023.
* llama.cpp `src/llama-mmap.cpp`, issues 91, 2251, 12444; ggml `docs/gguf.md`;
  Hugging Face safetensors docs; PyTorch `from_file` docs; `man7.org`
  `mmap(2)`, `madvise(2)`, `mlock(2)`.
* Acton CppCon14 and GDC Three Big Lies; JaiPrimer philosophy and SOA docs;
  Odin site, `#soa` docs, `examples/simd/motion`; Intel SDLT SoA example;
  Chilimbi cache-conscious structures; LLVM hot/cold split slides.
* a7 files cited inline: `a7/backends/zig.py`, `a7/types.py`,
  `a7/passes/type_checker.py`, `a7/parser.py`, `a7/safety.py`,
  `a7/stdlib/mem.py`, `bench/`, `examples/`, `docs/SAFETY_CONTRACT.md`.
