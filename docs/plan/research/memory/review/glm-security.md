> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: memory safety and cybersecurity (L12). Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

I have the core four documents. Now let me read the audit reports most relevant to my focus areas.
The GLM security review slot is the one I'm filling — it has produced no output yet. Let me read the security-relevant research and remaining audits.
I have the full picture. Let me verify a few load-bearing compiler facts cited by the audits against the current tree, since the audits were recorded at commit `701c679`.
I have everything needed. Let me verify one external fact my verification plan depends on (Zig DebugAllocator detection capabilities), then write the review.
# External GLM security review: memory plan revision 2 (L12 focus)

Advisory only. Read-only; I compiled and executed nothing. Verified-by-me facts cite `file:line` at HEAD `701c679` (confirmed still HEAD today); facts from repository research/audits are cited to their documents and labeled attributed. All A7 snippets obey the source rules (no recursion, `usize` indices, no `&`/`*`); snippets using `List`, `Table`, `Id`, tensors, tasks or native blocks are **proposed syntax** — none of it compiles today (`extern fn` fails, `edge-case-audit.md:134-135`).

The L12 slot this review fills has produced no prior output (`review/README.md:28-35`), so gates M12/M16 and Phase F currently have zero security evidence. Nothing here approves anything; every change to syntax or behavior goes through the approval rule (`decisions.md:22-30`).

---

## 1. Threat model for the memory plan (assets, adversaries, surfaces)

**Assets:** (1) the validity of contract items 1–12 (`memory.md:49-102`) — the compiler only certifies what its analyses prove; (2) host process integrity during compilation and of compiled binaries (A7 is explicitly not a sandbox, `docs/SECURITY.md:8-14`); (3) training-result integrity (a half-loaded checkpoint or stale alias silently corrupting weights is worse than a crash); (4) confidentiality of process memory (information remanence through storage reuse); (5) artifact/provenance integrity and reproducibility.

**Untrusted inputs (from the repo's own tensor threat model, `numerical-policy-glm.md:130-136`):** checkpoint bytes, dataset files/paths, dataset-derived shapes/indices/labels, threading environment variables, native-library version/ABI mismatch at load time, plus (new, this review) adversarially *pathological but legal* A7 source that stresses the placement analyses, and the native binding descriptors themselves.

**Not attacks:** compiled-program escape (documented accepted model), and every environmental impossibility class already listed in `memory-security-glm.md:171-194`.

---

## 2. Findings

### Blockers

**SEC-B1. Every insertion decision inherits the unsound fact engine; rev 2 does not gate layers 2–8 on its repair.**
Verified by me at HEAD: branch/loop/block facts are joined by snapshot-restore, so any outer variable assigned in a body reverts to stale pre-body facts (`a7/safety.py:302-306`, `:338-342`, `:348-352`, `:353-363`); calls invalidate nothing (`a7/safety.py:444-447`). These are MS-1/MS-2 (`memory-security-glm.md:46-47`, verified there at the same commit). Consequence for rev 2 specifically: contract item 4's "compiler removes a copy only when it proves the removal unobservable" (`memory.md:60-64`), layer 2's "releases on CFG edges" (`memory.md:427`), and layer 6 reuse are *proofs*. On the current lattice they are unsound proofs: a liveness/uniqueness fact surviving a join can license a move where a copy is required, then a release of storage that is still aliased — a compiler-manufactured use-after-free, in ReleaseFast (where Zig removes every backstop, `memory-security-glm.md:204`). Rev 2 puts "sound facts" at layer 1 and Phase B, but no falsifiable entry/exit criterion (join widening, call effects, loop back-edge second-visit) blocks later layers from being built and tested on the broken engine.

Counterexample (current syntax for the engine, proposed semantics for the release):
```a7
// Proposed semantics of compiler-inserted release; the defect is the fact engine.
xs := List(i32){}
if flag { xs = other() }        // stale post-join fact: "xs still the old storage"
b := xs                         // engine "proves" b unique; removes the copy
b.append(1)                     // writes storage xs may share or own -> corruption
```
Required verification: the adversarial proof-engine suite T1/T2/T11 (`memory-security-glm.md:226-231`) must pass, red first, before any layer-2+ analysis may place a release or remove a copy; plus a stated fact-lattice semantics document the tests derive from (`memory-security-glm.md:218`).

**SEC-B2. Size arithmetic: the §6 "checked size arithmetic" row does not cover wrap-before-call or wrapped slice bounds, and G3 explicitly leaves allocation-size arithmetic open (`decisions.md:61-65`).**
Rev 2 has the residual row (capacities, byte counts, tensor shapes, native dimension conversions — `memory.md:529`), which answers audit-4 EC4-46/47. Uncovered:

1. User expression wraps *before* reaching a checked API (audit-3 EC3-36, `audit-3-concurrency-failure-native.md:809-824`):
```a7
// Proposed syntax. count: usize = 0x2000_0000_0000_0000
buf := List(u64){}
buf.reserve(count * 8)     // `*` wraps under L5; reserve sees a small number;
                           // if capacity bookkeeping trusts it, later growth is undersized
```
2. Slice/index bounds computed with wrapping operators: `end := i + n` wraps, and `i <= end <= len` can be "proved" against the wrapped value, licensing an OOB view (the current engine folds literals exactly and would carry the wrapped interval; attributed: `memory-security-glm.md` I-1/I-9 discussion, `:138`). Note the present compiler already compiles `x << @intCast(count)` and `@divTrunc(x, -1)` shapes that trap or are UB (`plan/README.md:149-155`, compile-only).
3. Internal growth doubling inside `List`/`Table`/arena chunking: nothing in rev 2 obliges the standard library's own arithmetic to be checked (EC3-36's second half was not applied).

Required rule: every size that reaches an allocator, slice bound, capacity, tensor descriptor, or native length argument is computed on a checked path (R-1, `numerical-policy-glm.md:95`); user-supplied counts are validated against a maximum element count; verification tests V-1/V-2 style (`numerical-policy-glm.md:142-143`) plus a wrapped-slice-bound rejection test, Debug and ReleaseFast identical.

**SEC-B3. Native library supply chain and descriptor trust have no gate, no pinning, and no qualification harness.**
Verified facts: no native declaration syntax exists (`a7/stdlib/` has no native surface; `glm-concurrency.md:16-17`); "Hostile or incorrect native descriptors" is a known gap with no plan (`memory.md:599`); contract item 2 already concedes native safety is only as good as the descriptor (`memory.md:56-57`); the current dependency-audit gate audits the wrong environment (SEC-2), and `uv` remains unpinned (SEC-3/4) (`memory-security-glm.md:79`). Supply-chain requirements exist in research but nowhere in the plan: pin OpenBLAS/oneDNN versions + hashes like the Zig toolchain, record `openblas_get_config()`/oneDNN version in artifacts, extend the dependency audit (R-12, `numerical-policy-glm.md:117`), set thread/env configuration explicitly because env vars are process-global untrusted inputs, and treat OpenBLAS's build-time buffer-pool termination and oneDNN create/execute thread-affinity segfault as documented boundary assumptions (R-4, `numerical-policy-glm.md:46-47,101`; audit-3 EC3-40, `:881-893`).
Security consequence of skipping it: a wrong "borrow" descriptor is a persistent use-after-free inside a training loop; a wrong "completion" descriptor is a data race with library worker threads (EC3-52, `audit-3:1097-1109`); an unpinned OpenBLAS is arbitrary native code in the release archive.
Required verification: per-binding integration harness (corpus 12 variants under ASan + leak detection, Debug and ReleaseSafe); load-time version/ABI assertion; pinned hashes in the release manifest; a binding-authorship rule (decision D4 below).

**SEC-B4. Checkpoint loading (M24) is specified for the happy path only; checkpoints are untrusted bytes.**
M24: "Validate, then write in place for same shapes; build then swap otherwise; save through a temporary file and rename" (`memory.md:513`). Missing, all security-relevant:
1. **Format constraints.** Header cap, no-overlap/no-hole offset ranges, offsets+size ≤ file size, no code/object graph, bounded non-recursive parse, total-bytes budget. Evidence class: two successive escapes of PyTorch's `weights_only` allowlist unpickler (CVE-2025-32434, CVE-2026-24747) and the safetensors design rationale (`numerical-policy-glm.md:62-63`); a pickle-shaped or graph-shaped A7 checkpoint format is disqualified by evidence, not preference.
2. **Partial data-phase failure.** A read error after some parameters were overwritten in place leaves a half-old/half-new model that later code can use without noticing (audit-4 EC4-51 `:251`; glm-ai major 7). That is a silent training-integrity failure — the worst outcome in this threat model. Answer to audit-4 Q4: marking invalid is acceptable **only if invalidation is poisoned before the first byte is written and any subsequent use is a hard typed error** (not an ignorable flag), and the checkpoint carries a content checksum re-verified after the data phase; otherwise build-then-swap (2× peak) is the only honest option.
3. **TOCTOU/truncation.** The file can change or shrink between validation and read. mmap'd weights make truncation a SIGBUS crash (audit-4 EC4-54/Q5, `:254`, `:401-402`). v1 should read (not mmap) the data phase, or document SIGBUS as an environmental crash class; re-validate ranges while reading.
Required verification: V-9/V-10 fuzz corpus (truncated, overlapped, holed, giant-header, giant-dims, mutated-after-validate files) under ASan + timeout; corpus 21 extended with a mid-load failure asserting the model is either bit-identical to before or hard-invalid.

**SEC-B5. No data-race-freedom contract item; mutable globals compile today; M36 cannot reach globals.**
Verified: mutable globals compile with no race story (audit-3 p04, `:54`; `edge-case-audit.md:117-118`), layer 0 mentions "effect summaries including globals" (`memory.md:425`) but no gate adopts audit-3 EC3-22/G-21 (task-shared globals immutable after start; conflicting read/write in concurrent tasks rejected), and M36's "parent values" wording has no lexical owner for globals (`glm-concurrency.md:50-51`). Per-task stores plus a shared process store also need a thread-safe allocation path — allocator choice and thread safety are a listed gap with no rule (audit-5 part 5 item 8, `audit-5-consistency-impact.md:465`).
Required: a contract item "A7 code has no data races: cross-task data crosses by move or is read-only until join, and task-visible globals are immutable after program start"; TSan build of the task corpus (V-8 precedent, `numerical-policy-glm.md:149`).

### Major

**SEC-M1. Release ordering rules are incomplete where a wrong order is memory corruption.**
Rev 2 fixes defer-before-release and capture timing (`memory.md:446-449`) but omits two audit-1 rules: (a) assignment must evaluate the right-hand side into a temporary **before releasing the old left-hand value** (EC1-A09, `audit-1:53`); the present compiler already exhibits the class benignly — `arr = [arr[1], arr[0]]` prints `2 2` because element 0 is written before it is read (audit-2 CF-20, executed, `edge-case-audit.md:71-74`) — with compiler-inserted release at reassignment (`memory.md:67-68`) the same evaluation order becomes use-after-free of the old buffer. (b) A pending `defer` that touches a returned value must force a copy at `ret` or be rejected, else generated code writes a moved-from list (EC1-E04, `audit-1:126`).
Required: both rules into the contract; corpus tests `m[k] = f(m[k])`-shaped and defer-returns-list (the latter currently unspecified → could ship as silent corruption in generated code).

**SEC-M2. "No runtime drop flags" vs branch-closed resources — the unresolved join case yields double release.**
Contract item 3 forbids drop flags (`memory.md:58-59`) while EC3-59's close-on-one-branch needs a per-path release or a one-bit flag (`audit-3:1204-1217`; glm-concurrency major 9). If per-path release duplication gets a join wrong, the resource's native release function (file close, native handle free) runs twice — a double free of an OS/native resource, exactly the class the plan bans for memory. Decide: either permit one-bit closed-state flags in §6 residual work (they are not reference counts), or specify critical-edge release duplication with a join invariant test.

**SEC-M3. Arena membership: resources and native-retained buffers must never live in bulk-reset extents, and destruction must not allocate.**
Rev 2 says resources are "handled explicitly" at layer 5 (`memory.md:530`) and M7 releases in reverse acquisition order (`memory.md:494`), but the operative rules from audit 3 were not applied: (a) a resource-bearing value inside an iteration/extent arena must be on a flat release list maintained at insertion, else arena reset leaks its OS handle (unbounded fd growth = resource exhaustion; EC3-61, `audit-3:133`); (b) generated destruction must never allocate — a worklist allocation during near-OOM release either aborts mid-destruction or leaks (EC3-34, `audit-3:780-793`); (c) a declared-retained native buffer must create an extent dependency on its handle, else "precise release" can free storage a live native stream still writes (EC3-43, `audit-3:939-958`); (d) "Failure during automatic release" is a known gap (`memory.md:598`) — define the abort/discard semantics (audit-3 EC3-56's infallible-release + discarded-error report is the sound shape).
Counterexample (proposed):
```a7
// Proposed syntax. If logs lives in the per-request arena and holds files:
for r: usize = 0; r < requests.len; r += 1 {
    logs.append(files.open(path(requests[r])))   // file in bulk-reset extent
}   // arena reset skips the close -> fd exhaustion, then "too many open files"
```

**SEC-M4. Id lookup: generation exhaustion and wrong-table use are undefined; corpus 10's rejection has no rule.**
M5: "generation exhaustion retires the slot" (`memory.md:470`) — retire is undefined (permanent leak? silent invalidation?) and is flagged as an undefined silent failure (Qwen M-12, `review/README.md:70`). If a generation field is narrow and wraps, a stale `Id(T)` aliases a new record (classic ABA) — an integrity violation: the program reads and mutates the wrong record with no diagnostic. Also: ids are linked to the collection's *type*, not instance (`memory.md:228-229`), so two same-typed tables accept each other's ids (audit-2 pending item, `edge-case-audit.md:59`); and none of the nine rejection classes forbids an `Id(T)` crossing a task boundary without its store, while corpus 10 expects exactly that rejection (`memory.md:564`; glm-concurrency major 7).
Counterexample (proposed):
```a7
// Proposed syntax. allies and enemies are both Table(Player)
a := allies.insert(p)
e := enemies.insert(q)
hit := enemies.find(a)   // type-correct, generation may match: reads q's record
```
Required: 64-bit id layout (index + generation) so exhaustion is unreachable in practice and, when forced (debug-injected narrow generation), is a program stop with diagnostic — never aliasing; a documented wrong-table rule (instance check or an explicit SPEC'd limitation); the id-without-store rejection class added before M16 closes the list.

**SEC-M5. Reuse and stale-data exposure: no definite-initialization or capacity-hygiene rule covers reused storage.**
Contract rejection class 9 bans uninitialized reads of *named variables* (`memory.md:86`). Nothing governs: bytes of reused pool/arena storage (including struct padding), `Table` slots after removal/retire, planner-reused tensor buffers where "plans for a smaller signature may reuse the larger arena" (EC4-40, `audit-4:240`), and native kernels receiving capacity-sized buffers whose tail beyond length is stale bytes from a previous value. If any of those become observable (a kernel whose output depends on the stale tail, a checkpoint written from a capacity-sized region), previously-freed secrets flow into outputs or files — information remanence with no user-visible memory vocabulary to even describe it. Inference: the risk is low while class 9 holds and kernels get length-exact buffers, but neither is stated.
Required: (a) rule — native calls receive length-exact or explicitly zeroed capacity tails; planner reuse must not expose bytes beyond the current value's extent; (b) a decision on zeroization (recommend: none in v1, documented, since L19 forbids asking users; remanence accepted as out of scope); (c) corpus test printing/checksumming a reused buffer's untouched region under ASan.

**SEC-M6. Copy removal and layer-6 reuse have no self-check or corpus entry for the compiler-made aliasing hazard.**
Layer 6 promises "never creating aliased native kernel inputs and outputs" (`memory.md:431`) and corpus 12 covers user-level overlap (`memory.md:566`), but the compiler-made case — reuse choosing an input buffer as a GEMM/oneDNN output (EC4-44/P7, `audit-4:163-171`) — has no gate, no backend-plan invariant test, and no corpus row. This is a memory-corruption hazard created by the optimizer, invisible in source. Required: a compiler self-check (backend-plan assertion: no native output allocation aliases a live input unless the descriptor declares in-place safety) plus a corpus row; answered as audit-4 Q2: enforce at the backend plan, keyed on descriptor fields `in_place_safe`, after any fusion pass re-validates (R-9, `numerical-policy-glm.md:111`).

**SEC-M7. SoA layout: slice-of-SoA semantics unstated; whole-program per-type decision vs separate compilation; exit evidence needs both profiles.**
Layer 8 excludes types reaching native code or `ref` element arguments (`memory.md:433`) — that closes EC3-47/48 (at a performance cost worth reporting via M8). Remaining: (a) M13 slices over a `List(T)` whose records are SoA-split cannot be contiguous views; the plan assumes contiguous records (audit-5 F10, `audit-5:138`) — a slice of an SoA collection must materialize or be rejected; unstated. (b) The per-type whole-program decision is undermined by the separate-compilation gap (`memory.md:600`): a type used natively in one module and normally in another breaks the exemption's premise. (c) Phase G exit "identical output with and without layout transformation" (`memory.md:544`) must run in both Debug and ReleaseFast per the plan's own evidence rules (`memory.md:583-585`) — say so explicitly.

**SEC-M8. Runtime planner: planning-time bound, bucketing, and cache-key contents unspecified (resource-exhaustion input).**
M20: "deterministic runtime planner with a bounded cache for dynamic shapes... cache bounded by count and bytes; shrink on out-of-memory" (`memory.md:509`). Dataset-controlled sequence lengths select plan signatures (audit-4 Q3, `audit-4:395-397`): without bucketing (power-of-two, audit-4 EC4-41) an adversarial or merely pathological stream of distinct shapes buys O(distinct-shapes) planning work and arena churn — a resource-exhaustion input through a *data* channel. The cache key must include dtype, device, and alignment class, or bf16/f32 collisions reuse a wrong-sized arena (undersized buffer → OOB). Planning per new signature must be bounded work with a defined fallback (bucketed plan or unplanned but checked allocation), never unbounded. Corpus 22 should be authored as an adversarial shape stream with asserted planning-time and cache-size ceilings. Steady-state retention (arenas that only shrink on OOM, ORT BFCArena precedent, `numerical-policy-glm.md:48`) should be reported via M8 for long-running servers.

**SEC-M9. Determinism (contract item 11) is unenforceable on the current implementation and untested.**
Contract 11 promises identical placement and copy decisions (`memory.md:96-98`). Attributed and structural: approvals are keyed by raw `id(node)` with no liveness/version guard (LH-1 — a recycled `id()` can grant a fabricated approval), and the engine iterates Python sets/dicts whose order over strings varies with `PYTHONHASHSEED` (`memory-security-glm.md:143`; audit-5 part 5 item 1, `audit-5:458`). Any placement layer built on these is nondeterministic across runs, which breaks reproducible-build/provenance claims (release archives already carry platform/toolchain context per AGENTS.md). Required: versioned approval keys; insertion-ordered/sorted worklists; a CI test compiling one program twice with different `PYTHONHASHSEED` and asserting byte-identical emitted Zig.

**SEC-M10. Unbounded resource use remains reachable through tasks, channels, and stacks.**
Contract 5's iteration release floor (`memory.md:65-69`) closes loop retention. Still open: a task spawned per iteration retains every task store until each child ends, with no bounded group in M10 (EC3-19, `audit-3:500-518`); channel queues have no capacity rule in M27 (`memory.md:498`; EC3-09); task stack sizing and guarded stack-overflow abort are absent (EC3-21, `audit-3:540-558`; I-14 `memory-security-glm.md:145`) — a stack overflow in ReleaseFast is UB, the single worst failure mode the contract could leave unspecified. Spawn-failure semantics (does `group.start` return moved arguments?) are undecided (EC3-04, glm-concurrency blocker 4).

**SEC-M11. M16 cannot be approved as drafted (endorse and extend the concurrency review's finding).**
§6 residual work omits the runtime planner, plan-cache eviction, arena shrink, and compiler-inserted copies whose allocation can fail (Qwen B-1, glm-concurrency blocker 2, glm-ai blocker 2); the nine-class rejection list omits second-`backward`, use-after-close/move, id-without-store, and defer control-flow rejections; and the overlap-check row's runtime outcome is undefined ("unless a gate approves a runtime check with a defined result", `memory.md:528`). From the security side I add: generation exhaustion and destruction-during-OOM outcomes also need rows. Until the lists are closed and each residual item has a *defined failure outcome*, the SAFETY_CONTRACT amendment (M16) would promise something the plan contradicts — and the fail-closed contract text it amends is absolute (`SAFETY_CONTRACT.md:3-6`).

### Minor

- **SEC-m1. Memory report hygiene (M8/M35).** The report is compile-time and optional (`memory.md:472`, `:480`) — good; ensure it is never embedded in release artifacts and that shipped forms avoid absolute source paths (same artifact-injection class as NEW-2, `memory-security-glm.md:71-73`). Thresholds are per-target deterministic (M35) — keep them out of the binary.
- **SEC-m2. Failure-path allocation discipline.** Error values and diagnostics on OOM paths should be fixed-size, pre-reserved data (EC3-35, `audit-3:795-807`); not in §6.
- **SEC-m3. Native borrow details** proposed by audit 3 but absent from M12 text: borrowed-static-storage validity intervals (EC3-45), NUL-termination conversion ownership (EC3-54), checked `usize`→32-bit dimension conversion (EC3-55; covered generically by the §6 row, needs the M12 link).
- **SEC-m4. Multi-loss `backward`** (EC4-17) missing from M17 — rejection-class closure affects it.
- **SEC-m5. Extent-list disagreement** (contract 5 vs M2 vs M11, glm-concurrency minor 10) changes which boundary "return storage before delivering the error" attaches to — fix before corpus 20 is authored.
- **SEC-m6. Debug/ReleaseFast parity of every residual check** is already the rule (`memory.md:455-457`); add an explicit test that no residual check compiles to a Zig safety check ReleaseFast removes.

---

## 3. Answers to audit 4 §5 (questions directed at the GLM security review)

1. **May-save analysis soundness (M18):** no — not until MS-1/MS-2-class joins/call effects are repaired; the counterexample is any branch that conditionally saves `x` then mutates it (EC4-14) with a stale post-join "not saved" fact, silently wrong gradients. Require the layer-1 repair gate first (SEC-B1) and may-save facts joined to ⊤ when unreachable-code or summary gaps exist.
2. **Layer-6 reuse vs native outputs:** descriptor field `in_place_safe` (default false), backend-plan assertion that no output buffer aliases a live input unless set, re-validated after every fusion/transform pass (R-9). Test: corpus 12 variant where the alias can only arise from reuse.
3. **Planner bounds (M20):** bound distinct signatures (bucket to powers of two), cache by (shape-signature, dtype, device, alignment), cap count and bytes, bound per-shape planning work with a checked-allocation fallback, shrink arenas only on the OOM error path. Corpus 22 as adversarial stream. (SEC-M8.)
4. **Checkpoint partial failure (M24):** a failure after the data phase starts must leave the model hard-invalid (poisoned before first write, use = typed error) plus post-load checksum — otherwise build-then-swap. "Marked invalid" as a soft flag is not enough. (SEC-B4.)
5. **Mmap under live mapping:** truncation is SIGBUS (environmental crash). v1: read, don't mmap, the data phase; mmap only as a later gate with SIGBUS documented. Read-only mapping is acceptable under contract 2 only while nothing writes it.
6. **Shrink-on-OOM with live native scratchpad:** safe *only* under the v1 completion-at-return descriptor restriction and if workspaces are tape-owned handles (descriptor-declared), never raw pointers into step arenas. Enforce both in M12; test corpus 20 under ASan. (SEC-B3/M3.)
7. **A7-only recoverability (EC4-64):** no conflict with R-8 if the contract says native-internal allocation behavior is a descriptor fact and recoverability covers A7-allocated storage; libraries must be configured not to allocate (user scratchpads) or documented as aborting (OpenBLAS pool).
8. **Retained workspaces (EC4-43):** a workspace may outlive the primitive only as an owned handle whose descriptor declares it; the tape owns it and `backward` consumes it (M17); violation is a compile-time or backward-time typed error, never a dangling arena pointer.
9. **Detached values aliasing tape storage:** rejecting history-carrying sends is necessary but not sufficient — layer-6 sharing decisions must also prove a detached result does not alias tape-owned storage; if unprovable, copy (contract item 4 already forces this; add the test).
10. **Checked size path in Debug too:** yes — checked size arithmetic must be the only path in every profile, so Debug and ReleaseFast agree (and Debug traps don't mask a missing check). Matches SEC-B2.

---

## 4. Required verification (minimum security test matrix)

| # | Requirement falsified | Test |
|---|---|---|
| V-S1 | Sound joins / call effects before any insertion (SEC-B1) | T1/T2/T11 adversarial suite, red first; then corpus under Zig DebugAllocator (leak + double-free detection, `ziglang/zig` `debug_allocator.zig`) with safety checks on, plus ASan corpus builds for UAF; ReleaseFast parity runs |
| V-S2 | Release ordering (SEC-M1) | `m[k] = f(m[k])`, `xs = next(xs)`, defer-touches-returned-value; expected: old value read before release; Debug + ReleaseFast output equality |
| V-S3 | Size arithmetic (SEC-B2) | wrapped `reserve`, wrapped slice end, dataset dims product > i64::MAX: all typed errors, no allocation, both profiles identical |
| V-S4 | Checkpoint robustness (SEC-B4) | V-9/V-10 fuzz under ASan + timeout; mid-load kill → model bit-identical or hard-invalid; file mutated after validate → detected |
| V-S5 | Native boundary (SEC-B3/M6) | Corpus 12 variants (overlap via reuse, retention, workspace ownership) under ASan; TSan task corpus; load-time version assertion; pinned-hash release manifest check |
| V-S6 | Race freedom (SEC-B5) | Globals + tasks rejection tests; M36 parent-write-during-children rejection; TSan clean on accepted programs |
| V-S7 | Determinism (SEC-M9) | Same source twice, different `PYTHONHASHSEED` → byte-identical Zig; placement log identical |
| V-S8 | Planner bounds (SEC-M8) | Adversarial shape stream: bounded planning time, cache within count/bytes caps, correct buffer sizes per dtype key |
| V-S9 | Generation exhaustion (SEC-M4) | Debug-forced narrow generation: stop with diagnostic, never aliasing; wrong-table id documented behavior test |
| V-S10 | Destruction discipline (SEC-M3) | Near-OOM scope exit of deep structure: no allocation during release, no fd leak from arena-held resources |

All follow the test-quality rule (no coverage illusions; rejected-program fixtures stay compile-only and labeled).

---

## 5. Decisions the user must make (with recommendations)

1. **Gate layers 2–8 on a falsifiable layer-1 soundness gate** (join/call-effect repair, red tests first). *Recommend: yes — this is the single highest-leverage security decision; everything else inherits it.*
2. **Checked-size rule scope** (SEC-B2): internal-only (current) or also user-facing (`reserve` validated against max element count; slice bounds computed checked). *Recommend: both — fold into G3's allocation-size arithmetic decision.*
3. **Zeroization/remanence posture** (SEC-M5): none in v1 (documented) vs zero-on-release for security-sensitive types (new vocabulary, conflicts with L19). *Recommend: none in v1, documented limitation; length-exact native buffers mandatory.*
4. **Native descriptor authorship and supply chain** (SEC-B3): who may write `native` descriptors — stdlib/vetted bindings only in v1, or any user? Plus pinning gate for OpenBLAS/oneDNN (hashes, version records, thread config, no-alloc configuration). *Recommend: vetted bindings only; pinning gate is a Phase F entry requirement.*
5. **Checkpoint partial-failure semantics** (SEC-B4): poison-before-write + checksum, or build-then-swap; data-only format constraints adopted into M24; read-vs-mmap. *Recommend: poison + checksum + read(); mmap deferred.*
6. **Generation and id rules** (SEC-M4): 64-bit ids, exhaustion = program stop, wrong-table instance check or documented limitation, id-without-store rejection class. *Recommend: adopt all; instance check if cheap, else document.*
7. **Data-race contract item + globals rule** (SEC-B5) before Phase F. *Recommend: adopt audit-3 G-21 plus the no-data-races contract item.*
8. **Arena membership + destruction rules** (SEC-M3): resources and native-retained buffers excluded from bulk-reset extents; destruction never allocates; defined failure-during-release semantics. *Recommend: adopt all three into contract/§6.*
9. **Determinism enforcement** (SEC-M9): versioned approval keys + reproducible-Zig CI test. *Recommend: adopt; cheap and blocks later audit pain.*
10. **Bounds for tasks/channels/stacks** (SEC-M10): bounded task groups and channels in the v1 stdlib; guarded stack-overflow abort; spawn-failure semantics. *Recommend: adopt; decide stack policy with G9.*
11. **M16 sequencing** (SEC-M11): complete both closed lists (including planner/copies rows and defined outcomes for overlap check, generation exhaustion, destruction-during-OOM), then rerun the failed GLM reviews, then approve. *Recommend: approve nothing under M16 before that.*

The plan's architecture is sound in shape; the security risk is concentrated where *the compiler* becomes the allocator's author — insertion, reuse, planning — and each of those currently rests on either an unsound fact engine, an undefined failure outcome, or an unqualified trust assumption.
