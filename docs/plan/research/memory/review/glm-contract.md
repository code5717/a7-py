> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: contract soundness and residual runtime work. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

I'll start by reading the core planning documents.
Now the audit, plan README, and SAFETY_CONTRACT:
Now let me look at the supporting research directory structure and read key audit reports:
Now the audit reports, which are critical for cross-checking the closed rejection list:
Now audit 2 (pending for revision 3) and the review index:
I have the audits. Now let me verify the exact text of the research contract that M16 amends, and double-check a few points in memory.md:
Let me read the two completed external reviews for the same focus area:
All source material read. I ran no code; every claim below is from reading the repository documents (cited) or is labeled inference.

# Advisory review: contract soundness (memory.md §1 items 1–12, §6, gate M16)

**Verdict.** The 12-item contract is close to sound in shape and most items match the fixes the audits demanded, but it is not yet internally consistent: item 7's closed-world claim ("nothing else runs at run time for memory management") is falsified by the plan's own layer 7 and item 8; item 8's rejection list is not closed; §6 is missing rows for work the plan itself mandates; and gate M16 as scoped cannot cure the `SAFETY_CONTRACT.md` contradictions it is assigned to cure. This independently confirms and extends Qwen B-1/B-2 (docs/plan/research/memory/review/qwen.md:32-54).

## A. Item-by-item assessment (§1, memory.md:49-102)

| Item | Verdict | Evidence / issue |
|---|---|---|
| 1 No GC/counts/pauses | Sound | Pause defined (memory.md:53-55); consistent with iterative release. "Leak" from audit 5 F11 is still undefined — minor |
| 2 No UAF/dangling | Sound, qualified | Native caveat matches audit 3 G-11 fix (memory.md:56-57) |
| 3 Static release points | **Tension** | "No runtime drop flags" (memory.md:58-59) vs M7 explicit `close` on one branch only (memory.md:494): audit 3 EC3-59/G-14 (audit-3:1204-1217, 1386) needs per-edge fact-joined release, duplication, or a flag; the plan picks none |
| 4 Copy semantics | Sound | Audit 5 F4 / audit 1 gap 1 fixes applied (memory.md:60-64). Delivery risk vs item 12 (Kimi B-2), not an inconsistency |
| 5 Bounded loops | **Incomplete** | Iteration floor and reassignment release adopted (memory.md:65-69), but nothing releases storage of a *removed collection element* — an evicted process-extent cache entry is held to process end under item 5's last sentence, so corpus 1 "memory flat" (memory.md:555) is not guaranteed. Audit 2 G-15/EC2-21 (audit-2:1042, 109), pending for revision 3. No block/branch extent (audit 1 EC1-C12, audit-1:94; Qwen M-1) |
| 6 Structured tasks | Sound | Audit 3 G-1/G-2 fixes applied incl. deadlock qualification (memory.md:70-72) |
| 7 Residual runtime work | **Blocker** | See section C |
| 8 Closed rejection list | **Blocker** | See section B |
| 9 No memory vocabulary | Internally consistent | F6 fix applied (memory.md:91-94). Whether `Id(T)`/`Table(T)`/move-only satisfy L17's "new concepts" is a user decision (Kimi B-3); `detach`/`item()` in M23's rewrite are lifetime-adjacent source vocabulary (Qwen m-7) |
| 10 Iterative destruction | Sound | But the destruction work itself has no §6 row (see C) |
| 11 Determinism | Sound | Should explicitly extend to the runtime planner and cache eviction (Kimi minor; memory.md:97-98, 509) |
| 12 C-like, measured | Sound in form | Margin violation blocks release (memory.md:99-102); margin-setting order and violation action remain open (Qwen B-5b, Kimi B-2) |

## B. Item 8 closed-list cross-check (mandated check)

Item 8 claims these nine classes are "the only memory-related compile errors users see" (memory.md:75-76). Rejections the plan requires elsewhere with **no covering class**:

| Rejection required by the plan | Where | Nearest class and why it misses |
|---|---|---|
| Second `backward` on a consumed loss | M17 (memory.md:506) | Class 5 is scoped to "moved into a task" (also Qwen B-2) |
| Use after explicit `close`/move of a resource | M7 move-only (memory.md:494; audit-3 EC3-58/62) | Class 5 is task-specific |
| `ret`/`break`/recoverable failure inside `defer` | Architecture rules (memory.md:447-449) | None (also Qwen B-2) |
| Write to a loop binding (`for v in xs { v.x = 9 }`) | M30 (memory.md:475) | Not exclusivity — the binding is an immutable copy (also Qwen B-2) |
| Sending a typed `Id(T)` without its `Table` | Corpus 10 second half expects reject (memory.md:564; audit-3 EC3-12/13) | An id is not a "temporary view" (class 2) and the sender committed no use-after-move (class 5). **Not flagged by Qwen/Kimi** |
| Returning a view of `ref`-received data | M32 (memory.md:477) | The view does *not* outlive its owner; it's a form restriction, not class 2 |
| M12 descriptor violations other than retention (e.g. thread-affine handle moved into a task) | M12 (memory.md:496; audit-3 EC3-53) | Class 8 covers only retention-without-owner |
| Unproven index/key on a dynamic collection | Undecided (see section C3) | If fail-closed (as `SAFETY_CONTRACT.md:49` requires today), it is a tenth memory-related rejection class; if runtime-checked, it is unlisted §6 work |

Classes do cover: corpus 2/7 (class 2), corpus 8 (class 7), corpus 11 (class 4), corpus 12 (classes 1/8), corpus 14 (class 1), corpus 17 (class 6), M13 (class 2), M34 (class 9), M36 parent-write-during-children (class 1).

## C. Item 7 vs layer 7's runtime planner and item 8's copies (mandated check)

Item 7 (memory.md:73-74) + §6 (memory.md:521-530) form a closed-world claim ("Nothing else runs at run time for memory management"; memory-brainstorm.md:115 repeats it). §6 has six rows: allocator call (obtain/grow), bump/free-list op, id lookup, distinct-index/overlap check, checked size arithmetic, shape/dtype preflight. Missing runtime memory work the plan itself mandates:

1. **The dynamic-shape buffer planner** — layer 7 (memory.md:432) and M20 (memory.md:509) require "a deterministic runtime planner with a bounded cache" plus "shrink on out-of-memory". Planning, plan-cache insert/evict, and shrink are runtime memory-management work with defined-ish outcomes (M2) but no §6 rows. (Confirms Qwen B-1.)
2. **Compiler-inserted deep copies** — item 4 (memory.md:60-64) and item 8's escape hatch "it copies the value out on the escaping path" (memory.md:88-90) introduce O(size) allocations+copies the user never wrote; EC3-27 shows one can abort on OOM on a line with no visible allocation. Only the allocator call is arguably covered; the copy work and its M2 classification are not listed. (Confirms Qwen B-1.)
3. **Release/destruction work** — §6 row 1 covers calls "to obtain or grow" only. Item 5's "a growing collection releases its old buffer when it grows" (memory.md:67-68), item 10's iterative destruction (memory.md:95-96), M2's "returns its storage" (memory.md:486) and M20's shrink are all release-side runtime work with no row. **Not flagged by Qwen/Kimi.**
4. **Generation maintenance** — M5's generation bump on slot reuse and exhaustion/retirement (memory.md:470; Qwen m-12 flags retirement as undefined silent failure).
5. **C3. Index/key validity for collections disappeared.** Revision 1's contract listed "index validity tests where they cannot be proven away" (quoted at audit-5:27-29); audit 2 still reasons from "the contract-4 index test" (audit-2:313-314) and asks it to cover Map key presence (G-17, audit-2:1043). Revision 2's §6 has **no index- or key-validity row**, and M33's optional lookup (memory.md:478) covers only `get`. So either plain `xs[i]` with an unprovable dynamic index is a compile rejection (a tenth class, missing from item 8) or a runtime check (missing from §6 and from M16's blessing). The plan is silent. **Not flagged by Qwen/Kimi in this form.**
6. **Wording defect**: §6's distinct-index row has outcome "Rejected at compile time unless a gate approves a runtime check" (memory.md:528) — a compile-time rejection is not a runtime outcome, and under current gate recommendations (corpus 14, memory.md:568) the check never runs.

## D. Gate M16 (SAFETY_CONTRACT amendment) assessment

M16 as written: "Amend `SAFETY_CONTRACT.md` to allow the listed residual checks with defined outcomes and program stop on non-recoverable out-of-memory" (memory.md:488). Assessment: **not yet approvable, and under-scoped**.

1. **Scope mismatch inside the plan.** memory.md:104-105 says the whole 12-item contract amends `SAFETY_CONTRACT.md` and the lang-safety research contract; the M16 row blesses only residual checks + OOM stop. An amendment against the narrower scope would leave the rest of the current contract contradicting the plan.
2. **The target document contradicts more than checks.** Verified in `docs/SAFETY_CONTRACT.md`: the fail-closed preamble "cannot trap… rejects the program before Zig code is emitted" (lines 3-6) admits neither the OOM program stop nor any runtime check outcome; the risky-operations table's index row (line 49) presupposes proof-or-reject (ties into C3); the arithmetic row (line 54) already conflicts with L5 (plan README documentation defects); the Reference Surface plan for `ref`/`nil`/`new T` (lines 69-78) and Ownership Surface `del`/affine/`clone` text (lines 80-91) are superseded by M3/M4 and must be rewritten, not amended-around. The research contract "statically rejects **every** program that would exhibit a memory-safety violation… no unsafe escape hatch" (docs/lang-safety/README.md:44-50), co-named at memory.md:104-105, is falsified by the same runtime outcomes.
3. **M16 points at an incomplete list.** Until the section C gaps are fixed, "the listed residual checks" bakes the incompleteness into the safety contract.
4. **No review evidence.** All nine GLM runs produced no output; "Gate M16 and the security review required by L12 therefore have no GLM evidence yet" (review/README.md:30-33), while Phase A's exit requires a GLM review of the contract (memory.md:536). Under L12 ("any cyber seucirity stuff use glm", decisions.md:47) the rerun is a precondition, not a formality.
5. **One strength to preserve**: the architecture rule "Checks are A7 code… not a Zig safety check that ReleaseFast removes" (memory.md:456-457) is exactly what the lang-safety ReleaseFast claim needs; the M16 amendment should elevate it into `SAFETY_CONTRACT.md` alongside the residual-work table.

## E. Ranked findings

**Blockers**
- B-1. Item 7/§6 closed-world claim false: runtime planner + cache + shrink, compiler-inserted copies, release/destruction work, generation maintenance unlisted (memory.md:73-74, 432, 509, 521-530 vs items 4, 5, 8, 10).
- B-2. Item 8 rejection list not closed: at least the eight rows in section B above; four confirmed by Qwen B-2, the id-without-table, M32, M12-descriptor and index cases additional.
- B-3. M16 under-scoped and unevidenced: gate text vs memory.md:104-105 scope mismatch; preamble/surfaces/risky-ops/research-contract rewrites required; §6 incomplete; no GLM/L12 evidence (review/README.md:30-33).

**Major**
- M-a. Item 5 does not guarantee corpus 1 "memory flat": no release/recycle rule for removed collection elements (audit-2 G-15) and no block/branch extent (audit-1 EC1-C12).
- M-b. Item 3 "no drop flags" unresolved against M7 conditional close (audit-3 EC3-59/G-14): no mechanism chosen.
- M-c. Index/key validity policy for dynamic collections undecided (section C3); either path currently violates item 8 or §6.
- M-d. M6/G4 interlock (class 4 depends on stored function values; recursion-ban premise of layers 3-5 at stake) — Qwen B-3/Kimi M-4; confirmed by reading memory.md:187-190, 221 and plan README G4.

**Minor**
- m-1. "Leak" undefined (audit 5 F11 partially applied).
- m-2. edge-case-audit.md:38 cites "contract items 7 and 12" for residual checks; the content is item 7 + §6 (item 12 is performance) — citation drift.
- m-3. §6 distinct-index row outcome wording self-contradictory (memory.md:528).
- m-4. Item 8 class 9 (uninitialized read) is a correctness rule, not memory — label it as borrowed (Kimi minor).
- m-5. M23 rewrite vocabulary (`detach`, `item()`) sits uneasily with item 9 (Qwen m-7).

## F. Decisions the user must make (with recommendations)

1. **Reword item 7 and complete §6** — adopt "no tracing, counting, scanning or deferred copying at run time; all remaining runtime work is listed in §6", then add rows: dynamic-shape planner/plan-cache/shrink (outcome: planner failure is M2 allocation failure), compiler-inserted copies (outcome: M2 by owning extent, surfaced by M8), destruction/release work, generation maintenance, and (per decision 3) index/key validity. *Recommend: yes — this is the fix for B-1.*
2. **Re-close the rejection list** — reorganize into Qwen's four families (exclusivity / escape / move-and-initialization / form restrictions) and add the missing classes (second `backward`; use-after-close/move of move-only values; defer control flow; loop-binding writes; id separated from its table; returned views of `ref` data; descriptor violations). Freeze it as the entire content M16 blesses. *Recommend: yes.*
3. **Index/key validity for dynamic collections** — proof-or-reject (fail-closed; add the rejection class) vs runtime check with defined stop outcome. *Recommend: proof-or-reject for plain `xs[i]` in v1, optional-returning `get` for lookups — keeps the fail-closed contract and avoids a new stop class.*
4. **Item 3 vs conditional close** — pick per-edge fact-joined release with rejection when closed-ness is unprovable, or permit one-bit drop flags as listed residual work (audit 3's option). *Recommend: per-edge release, no drop flags.*
5. **Corpus 1 flatness rule** — add "storage of a removed/overwritten collection element is released or recycled at that point" to item 5 (audit 2 G-15). *Recommend: yes.*
6. **Extent granularity** — add block/branch extents or last-use release above the M35 threshold. *Recommend: yes, block extents.*
7. **G4+M6 jointly** — Qwen recommends G4(b) (type-informed call-graph edges) as prerequisite of M6 storage permission. *Recommend: G4(b), and add MS-7 to the Phase B defect list.*
8. **M16 timing** — do not present M16 until revision 3 (audit 2 + reviews applied), §6 final, and the GLM/L12 review rerun; then approve a full `SAFETY_CONTRACT.md` + research-contract rewrite (preamble, facts, risky-ops table, reference surface, ownership surface, and the L5 arithmetic-row conflict), not a checks-only patch. *Recommend: yes.*
