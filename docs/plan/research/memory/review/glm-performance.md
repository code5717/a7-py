> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: C-like performance and memory, benchmarks and margins. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

# External review — focus: C-like performance and memory use (L20, gate M14)

Advisory only. I ran no code and built nothing; every "current compiler" fact below is a source read or a repo-recorded probe (labeled as such). This is the "GLM performance" review listed as not delivered at docs/plan/research/memory/review/README.md:24.

## Verified facts

Current compiler (source reads):

- One global `std.heap.page_allocator` backs all `new`/`del` (a7/backends/zig.py:159). No arena, pool, `List`, `Map`, or `Table` exists; `a7/stdlib/mem.py:1-9` is a stub. Layers 5–8 of the plan have no code.
- Assignment lowers to a bare Zig `=` (zig.py:1308-1325). There is no copy-removal or reuse analysis anywhere (audit 2 CF-35 records the same).
- Every `println` emits a 1 KB buffer and an explicit flush per call (zig.py:165-171); C stdio buffers until newline/larger chunks.
- `for v in arr` over a fixed array lowers to `for (arr) |v|`, copying each element (audit 2 CF-03, probe q08/q24 run Debug/ReleaseFast).
- Overlapping aggregate self-assignment miscompiles today: `arr = [arr[1], arr[0]]` prints `2 2` (edge-case-audit.md:71-73, executed).

Plan machinery (docs/plan/memory.md):

- Contract 12 makes C-like perf a measured target with release-blocking margins (memory.md:99-102); M14 sets those margins "after Phase A baselines" (memory.md:487).
- Layers: extent inference (4), storage formation (5), copy removal/reuse (6), buffer planning (7), SoA layout (8) (memory.md:429-433).
- "Checks are A7 code … not a Zig safety check that ReleaseFast removes" (memory.md:456-457): residual checks (id lookup, overlap/distinct-index, checked size arithmetic, shape preflight; memory.md:521-530) survive in ReleaseFast.
- Phase E exit is "allocation counts and peak memory within M14 margins" (memory.md:542) but tensors are Phase F (memory.md:543); audit 5 already flagged that buffer planning is scheduled before tensors exist (docs/plan/research/memory/audit/audit-5-consistency-impact.md:84).
- Evidence rules: flatness = peak at N vs 10N; baselines hand-written C or Zig with pinned toolchains (memory.md:585-587).
- The user has not yet confirmed the reading of L20 itself (decisions.md:74-75).

## Where A7 will be slower or heavier than hand-written C, and why

### Blocker

**P1. M14 cannot enforce L20 as specified.** Margins are set after the baselines exist, no action is defined on violation, and baseline authorship is undefined and bias-prone (qwen.md:74-88 B-5; kimi.md:41-47 B-2; audit-5:489 "No acceptance ratio; baseline author bias"). A target chosen after seeing your own numbers is not a target. Everything below is unmeasurable until the margin policy, workload list, and authorship procedure are fixed — before Phase A baselines run.

**P2. Copy-when-unproven is the structural L20 gap, and it is unmeasured exactly on the acceptance workloads.** Contract 4 copies at the binding and removes copies only when unobservability is proven (memory.md:56-60). C aliases by pointer at zero cost. Recorded worst cases: one copy per loop iteration (`prev := cur; cur.step()`, audit 2 EC2-73); `snapshot := model` then one update copies every parameter, peak doubles (audit 4 EC4-08); one element write to a shared 1 GB tensor copies the whole tensor (EC4-09); a bound view materializes on first write (EC4-01) and broadcast results copy on write (EC4-04). Inference: uniqueness proofs fail precisely at branch joins, cross-call effects, and loop backs — the same places the current fact system is weakest (CF-25, a second write through a `ref` rejected because a fact was overwritten; edge-case-audit.md:97-99). No full classifier or decoder training step has been hand-traced; those traces are Phase F work (kimi.md:43-47). Until they are Phase A evidence plus benchmarks, L20 is asserted, not enforceable.

### Major

**P3. Correctness rules force layer-6 reuse to be conservative, and every conservative miss is a copy C would not have.** Reuse must materialize the RHS before the first write when source and target overlap (audit 2 G-11, from the CF-20 miscompile); no reuse while any view of the old value is live (EC2-76); the compiler must never hand a native kernel its own input as output — `a = matmul(a, w)` under naive reuse creates an aliased GEMM the source never wrote (audit 4 P7); data-dependent first-writer paths need per-path copies (EC2-72, G-10). Inference: real programs hit these constantly; the realistic outcome is "C-like where uniqueness is provable, copy-heavy where it is not."

**P4. Permanent residual checks.** Generation-tagged `Id(T)` lookup, distinct-index/overlap checks when not proven, checked capacity arithmetic, shape preflight (memory.md:521-530) are emitted as explicit code in every profile (memory.md:456-457). C has none. Individually a compare; per-element in hot loops (table access by id inside a tick loop) they are measurable. The plan's answer is proof-based elision (M5 recommendation), but no elision-coverage target or benchmark exists.

**P5. Over-retention by extent.** Releasing at extent end holds memory C releases at the closing brace (synthesis.md:28-30 names this the cost). There is no block or branch extent, so `if big_case { tmp := build_huge(); use(tmp) }` holds `tmp` for the whole call (qwen.md:94 M-1, audit 1 EC1-C12). The iteration release floor bounds by end-of-iteration, not last use; a reassigned binding releases at reassignment, but if the replacement is built first, peak transiently doubles unless reuse proves uniqueness (contract 5, memory.md:63-69).

**P6. Map/list lookup as optional copy (M33) is a predictable M14 failure** on read-heavy workloads (`Map(string, Record)` copies the record per lookup; qwen.md:100 M-4). Needs the temporary-view resolution before baselines are set.

**P7. Text processing has no cheap path.** Owning `string` means materializing substrings on return/assignment into owning bindings (audit 2 EC2-26, EC2-29), prepend needs memmove overlap handling (EC2-28), and no builder type is named (qwen.md m-5: `acc = acc + s` is O(n²) risk). C tokenizers run on pointers into one buffer at zero copy. This is the workload class where A7 will lose to C by the largest factor, and it should be priced in openly, not discovered by M14 later.

**P8. The flagship L18 claim has no scheduled measurement.** XLA-style buffer packing is motivated by training steps, but its Phase E exit evidence can only cover non-tensor programs (audit 5:84; memory.md:542-543). Tensor-packing measurement must move to (or repeat at) Phase F, and Phase E needs a non-tensor packing benchmark so layer 7 has any M14 evidence.

### Minor

**P9. I/O overhead today**: flush per `println` with a 1 KB buffer (zig.py:165-171). Any benchmark printing per iteration measures this, not memory management. Fix or design benchmarks to print checksums only.
**P10. SoA granularity**: layout is chosen per type across the whole program (memory.md:433), while C picks per data structure; exclusions (native-reached, slice element types per qwen m-1, `ref` element args with copy-in/copy-out per EC2-25) further shrink wins. Tensor payloads are never split (EC4-67), so SoA barely touches the AI workloads.
**P11. Large values above the M35 threshold move off the native stack** (memory.md:480) — indirection where C uses stack arrays.
**P12. Mixed precision**: f16/bf16 widening is software where CPUs lack support (v1 plan AI sequence step 2, docs/plan/README.md:385-388); strict floats forbid fast-math by default (L16), so C baselines must be pinned to `-O2` without `-ffast-math` or the comparison is rigged either way.
**P13. Loop bindings copy** (today CF-03; by policy M30). Read-only iteration over big structs must get borrow elision under contract 4, or every scan pays a per-element memcpy C doesn't.
**P14. Compile-time degradation silently becomes runtime cost**: kimi M-5 (kimi.md:73-74) — if analysis exceeds budget and the degradation order drops copy removal or packing, run time regresses with no diagnostic. Degradation must appear in the M8 report.

## Proposed benchmark suite (with C baselines and margins)

All programs print an output checksum only (P9). All are new except where they extend corpus programs (memory.md:553-577); A7 sides are proposed syntax. Expected outputs derived independently per the evidence rules (memory.md:579-583). Margin violation = release block per contract 12; the only escape is a deviation the user records in the ledger.

| # | Program (A7 shape, proposed) | C baseline (hand-written) | Metrics | Proposed margin |
| --- | --- | --- | --- | --- |
| B1 | Request/server loop, per-request temporaries, connection table, capacity-limited cache (corpus 1) + an in-branch large temporary (P5 probe) | malloc/free per request, fixed tables, frees at brace | wall; peak RSS at N and 10N; allocs/iteration | wall ≤1.10×; RSS ≤1.25×; allocs ≤ C + O(1); peak(10N) ≤ peak(N) + chunk constant |
| B2 | Entity tick: spawn/remove, id lookup incl. stale id next tick (corpus 5) | hand-written slotmap with generations (the honest C twin) | wall; RSS; checks per element not elided | wall ≤1.15×; RSS ≤1.10×; elided-check ratio reported |
| B2b | Same record type read in two loops: field-scan vs whole-record copy | C author picks SoA for one, AoS for the other | wall vs better C layout | ≤1.15× (prices P10) |
| B3 | Build 10M-node tree in `Table`, iterate, release at scope end (corpus 4/15) | arena-allocated nodes, one arena free | wall; RSS; release time | wall ≤1.10×; RSS ≤1.15× |
| B4 | Merge keeping runtime-chosen subset (corpus 6) | memcpy of selected rows | wall; peak | ≤1.25× wall |
| B5 | Split/filter/join over ~100 MB text | pointer-chunked zero-copy C | wall; RSS; allocs | wall ≤1.50×; RSS ≤2.0× — or a pre-recorded deviation (P7) |
| B6 | Pure numeric loops: axpy/dot/small fixed matmul, f32/f64, integer mix | C `-O2`, no fast-math | wall | ≤1.05× (prices backend quality; requires track 3 wrapping lowering first, else Debug traps/ReleaseFast UB per docs/plan/README.md:149-150) |
| B7 | Copy-removal stress: `prev := cur` per iteration (EC2-73); `b := a; b.items[0] = 5` (EC2-71); `x = f(x)` reuse (EC2-27/28) | in-place / pointer swap C | allocs per iteration; wall | allocs = 0 when unique (design target); wall ≤1.10×; every non-removable copy appears in the M8 report |
| B8 | Classifier and decoder training step with static-shape buffer planning (Phase F) | C with OpenBLAS and a hand-preallocated workspace | wall/step; peak; allocs/step after warmup | wall ≤1.25×; peak ≤1.25×; allocs ≤ C + O(1) |
| B9 | KV-cache generation (corpus 19) with capacity (M22) | append + realloc C | bytes copied; peak | O(T·d) not O(T²) (audit 4 P6); peak ≤1.25× |
| B10 | Checkpoint load, same shapes and changed shapes (corpus 21, M24) | `fread` in place / mmap | peak during load | ≤1.30× same-shape; changed-shape 2× allowed only as a recorded deviation |

Rationale for the numbers (inference): Zig ReleaseFast via LLVM sits within a few percent of `-O2` C on tight loops (hence 1.05×); residual checks and placement justify 1.10–1.15× on data-structure work; autodiff and strictness justify 1.25× on training; text is priced honestly at 1.5×/2× rather than pretended at 1.1×. These adapt qwen's proposal (≤1.25× RSS, ≤1.10× wall, ≤1.5× allocs; qwen.md:88) into per-workload classes. Note margins are upper bounds only — arena bump allocation and batch release should let A7 *beat* per-object malloc/free C on allocation count; the suite should record wins too.

## Who should author the baselines

Phase A already includes "C and Zig baselines" (memory.md:536); the procedure is the missing part (P1). Recommended, consistent with repo practice (audit subagents, external reviewers):

1. The controlling session freezes a benchmark spec per program: problem statement, input generator, expected-checksum derivation method, metrics, pinned toolchains (gcc/clang version and flags, Zig 0.16.0 ReleaseFast, measurement tools). No A7 source in the spec.
2. A **fresh subagent that is not implementing any memory layer** writes the C baseline from the spec alone, so it cannot mirror A7's structure. It must derive the expected checksum independently (same rule as the corpus, memory.md:581-582).
3. Flagship workloads (B1, B6, B8) get **two independent C baselines**; the faster one is the margin denominator, and the spread is recorded — this is the only defense against a weak baseline masquerading as a pass (audit-5:489).
4. GLM reviews the baselines for competitiveness before margins are applied (fits the L12 review routing).
5. The user approves the spec and the margin table **before** the baselines run (approval rule, decisions.md:22-30; kimi.md:117 decision 10).

Zig baselines are secondary: B6 gets both (measures backend parity); everything else anchors on C because L20 says "like C in performance and memory usage" (decisions.md:55).

## Decisions the user must make

1. **Confirm the L20 reading** (decisions.md:74-75 says it is unconfirmed): "C-like" means measured against hand-written C per the M14 margin table, violation blocks release, escape only by a recorded deviation. *Recommend: confirm.*
2. **Fix the margin policy before baselines run** (P1): adopt the per-workload-class margins above (or edit them), plus the violation action. *Recommend: adopt, with B5's looser text margins as recorded deviations rather than pretend-tight ones.*
3. **Baseline authorship procedure** (P1): independent-author-from-spec, dual baselines for B1/B6/B8, GLM competitiveness review, your sign-off pre-run. *Recommend: adopt as Phase A procedure.*
4. **Promote training-step hand-traces and B7/B8 to Phase A exit evidence** (P2; kimi B-2). *Recommend: yes — cheapest falsification of the riskiest choice.*
5. **M33 lookup: temporary view or copy** (P6; qwen M-4). *Recommend: temporary view, copy only where liveness demands.*
6. **Add block/branch extents or a last-use release rule for large values** (P5; qwen M-1). *Recommend: add to layer 4 before Phase D.*
7. **Move tensor buffer-planning measurement to Phase F with its own M14 checkpoint; add a non-tensor packing benchmark to Phase E** (P8). *Recommend: yes.*
8. **Name a builder owner for text and set B5's deviation budget** (P7; qwen m-5). *Recommend: track 8a.*
9. **Set an elision target for residual checks** (P4): e.g. zero per-element checks in proven-hot loops, reported via B2. *Recommend: fold into M14 via B2 rather than a new gate.*
