> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: contradictions across all plan documents. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

I'll review the planning corpus for consistency. Starting with the four core documents.
Now the edge-case audit and key supporting docs.
Core documents read. Now I'll verify cross-referenced claims against the repository (SPEC line citations, STATUS, SAFETY_CONTRACT, examples, audits).
Spot checks done. Now verifying the external citation in the fact-check and Gemini comparison ("Counting Immutable Beans" attribution).
Citation error confirmed. Checking the remaining cross-references in the research tree.
# External review: consistency of the A7 v1 planning corpus

Method: read the ledger, v1 plan, memory plan rev 2, edge-case audit, brainstorm record, synthesis, all three advice files, the fact-check, the Gemini comparison, Qwen/Kimi reviews, and the review index; spot-verified code and doc citations in the tree (read-only; no code run, no compiles). Web-verified one external citation. Statements below are verified unless labeled inference.

## What is consistent (verified)

- Ledger → plan fidelity: memory.md:33–44 and plan README "Direction" faithfully restate L15–L22; no recommendation in the corpus reintroduces GC/RC (L15), approves parameter-mode syntax (L6 scope limit), or ships a syntax change without the approval rule.
- Superseded-table citations resolve: `STATUS.md:20-21` and `:41-44`, `SAFETY_CONTRACT.md:54`, `completion-roadmap.md:15-18` with its inline "cited as" marker — all match the working tree.
- Code claims check out: `a7/backends/zig.py:1913` (`create(...) catch null`), `examples/025_linked_list.a7:7` (`next: isize`, `-1` sentinel), `examples/022` and `037:130` store function values, stdlib is io/math/mem/string only, `site/public/llms.txt` and `llms-full.txt` exist.
- The recorded SPEC defects are real: `SPEC.md:1155-1158` (broadcast `[3,1,4]`+`[2,5,1]`→`[3,2,5,4]` is wrong under NumPy rules), `:2021` (`.val` in grammar), `:410-411` vs `:447-448` (same typed-binding form declared immutable and mutable), `:698-702` (`swap` reassigns `ref` bindings, against L6).
- Gate accounting is consistent everywhere: M25/M28/M29 unused (memory.md:461, decisions.md:117-118, review README). Audit-4 gate crosswalk exists (edge-case-audit.md:25-32) with a pointer in audit-4's header. Review README's summaries of Qwen and Kimi are accurate (counts of minors/decisions match). GLM-review outage is consistently recorded. A7 source rules (no recursion, usize, no `&`/`*`) are respected in all plan examples; proposed fragments are labeled.

## Findings

### Blocker (must fix before any M-gate or M16 goes to the user)

1. **Contract item 7 is false as written.** memory.md:73-74 claims "Nothing else runs at run time" beyond §6, but §6 (memory.md:521-531) omits the dynamic-shape runtime planner and its bounded cache (layer 7, M20; memory.md:432,509), compiler-inserted escape copies (memory.md:88-90), and generation bumps. Confirms Qwen B-1 independently.
2. **Contract item 8's "closed list" of nine rejections is not closed.** The plan itself mandates additional memory-related rejections: second `backward` (M17, memory.md:506), `ret`/`break`/failure inside `defer` (memory.md:448-449), writes to loop bindings (M30, memory.md:475), use-after-move/close implied by move-only resources (M7, memory.md:494). Since item 8 is the proposed content of the M16 safety-contract amendment, it must be completed first. Confirms Qwen B-2.
3. **M6 presupposes undecided G4(b).** memory.md:437-440 conditions bounded call depth on stored function values staying non-recursive "(v1 gate G4)"; M6 (memory.md:471) recommends capture-free function values "anywhere". G4 (plan README:171-209) is open, and the 2026-09-14 GLM review's MS-7 (stored function values can emit recursive Zig) is absent from edge-case-audit's current-compiler defect list and from Phase B exit evidence. Confirms Qwen B-3/Kimi M-4.
4. **L19 and M14 are unfalsifiable as written** — the "L19 metric" Phase A exit condition (memory.md:536) is defined nowhere, and M14 sets margins after seeing the baselines with no violation action (memory.md:487, Qwen B-5, Kimi B-1/B-2). Also native declaration syntax has no gate although Phase F and G8 depend on it (Qwen B-4; `extern` probe failure recorded at edge-case-audit.md:134-135).

### Major

5. **Citation error in two controlling-session documents.** "Counting Immutable Beans" is by Sebastian Ullrich and **Leonardo de Moura** (CPP 2020, presented Sept 2019), not "Ullrich and Lorenzen, 2019" as written in `functional-memory-fact-check.md` (correction 2) and `gemini-comparison.md` (annotation). Verified via ACM DL (dl.acm.org/doi/10.1145/3412932.3412935) and the KIT PDF; Florian Lorenzen authored a different 2021 Perceus-borrowing thesis. The substantive claims (Lean 4 RC+reuse, borrowed parameters avoid count updates, preceded and influenced Perceus) are correct.
6. **`docs/lang-safety/05-for-a7.md:263` still asserts "No recursion, so no cyclic ownership graphs."** — flagged as wrong by synthesis.md:70-71, advice-grok (both drafts), and the fact-check, but the file carries no dated audit note, unlike the other superseded lang-safety claims (08-decisions.md:30-40 does have them).
7. **SAFETY_CONTRACT drift is broader than the ledger records.** Besides line 54 (already listed), line 48's division proof ("divisor is non-zero") conflicts with L16/G1 for float division (G1 documents the failing `0.0/0.0` probe), and lines 69-91's "planned split" (optional `ref T`, `nil`) and "next ownership phase will make heap refs affine" contradict memory plan M3/M4. Known in aggregate (track 0/M16), but the ledger's superseded table should cite the division row so it isn't missed.
8. **Track-8/Phase-C dependency cycle is mis-located.** Plan README:348-350 acknowledges the cycle but says "Revision 3 of the memory plan will split this" — the cycle lives in the v1 plan's own track table (track 8 depends on track 6 while memory Phase C needs track 8 collections); the v1 plan can split track 8 (8a collections / 8b rest, per Qwen M-10) without waiting.

### Minor

9. **Revision hygiene:** memory.md is labeled "revision 2, 2026-09-15" but contains 2026-09-16 probes (line 112) and post-review edits (the M25/M28/M29 note at line 461 answers Kimi M-9). Qwen/Kimi line citations no longer resolve (e.g. qwen.md cites the breaking table at memory.md:151-167; it is now at 264-281). Also Qwen m-11 (G4/G5 pointers to M6/M33) is fixed in the current text but not marked "(now fixed)" in the review README. Add a change note or bump the revision marker.
10. **Stale line pointer:** plan README's documentation-defects list cites `08-decisions.md:700-705` for the cluster-CA `nil` summary; after the 2026-09-16 reformat that content sits near lines 39-40/96. Use the ID-based pointer the ledger prescribes.
11. **Audit-2 provenance:** header says "Date: 2026-09-15", body says "Date: 2026-09-16".
12. **Kimi B-3 overstates its premise** (inference): it claims the plan "assumes L19 overrides L17's 'new concepts'", but L17's user words already say "we need new concepts" (decisions.md:52). The requested user decision (which concepts, and do they satisfy L19) is still valid; the "by fiat" framing is not.
13. **L12 scope stretched:** memory.md:546 makes *every* phase end with a GLM memory-safety review citing L12, whose user words cover "cyber security stuff" only. Conservative extension; worth one recorded sentence.

## Documents that must change

| Document | Change |
| --- | --- |
| `docs/plan/memory.md` | Rev 3: close contract items 7/8 (add planner/copies/generation rows to §6; complete the rejection list), adopt audit 2 + reviews, cross-ref G3 for checked sizes, M11 identification rules, split the track-8 coupling, version note for post-review edits |
| `docs/plan/README.md` | Fix 08-decisions line pointer; split track 8; carry MS-7 into Phase B evidence with the G4 decision |
| `docs/plan/research/memory/edge-case-audit.md` | Add MS-7 stored-function-value recursion bypass to current-compiler defects |
| `docs/plan/research/memory/functional-memory-fact-check.md`, `gemini-comparison.md` | Fix "Ullrich and Lorenzen" → "Ullrich and de Moura, CPP 2020" |
| `docs/lang-safety/05-for-a7.md` | Dated audit note on the false cyclic-graphs claim (line 263) |
| `docs/SAFETY_CONTRACT.md` | Track 0/M16: line 48 division row (L16), line 54 arithmetic row (L5, already listed), planned-ref-split and affine-next-phase paragraphs vs M3/M4, residual-check amendment |
| `docs/STATUS.md` | Track 0: lines 20-21 (numeric brief superseded by G3) and 41-44 (AI/concurrency superseded by L1/L7) |
| `docs/SPEC.md` | Track 0/1 defects already listed (broadcast, `.val`, typed-binding mutability, `swap`, `fn_ptr … void`); later: L3/L4/L5/L16 changes only as gates approve |
| `README.md`, `site/public/llms.txt`, `llms-full.txt`, `site/public/docs/` | No drift found today (verified: they mirror current behavior only); must update in lockstep with SPEC/STATUS when track 0 or approved gates land, per AGENTS.md |

## Decisions the user must make

1. **G4 + M6 together** (stored function values): recommend **G4(b)** type-informed call-graph edges + cycle rejection — keeps `examples/022`/`037` working and preserves the DAG premise layers 3-5 depend on; make it a stated prerequisite of M6 and Phase B evidence.
2. **L17 vs L19 reading**: confirm `Id(T)`, `Table(T)`, move-only resources are the approved "new concepts", ideally with Qwen's two-tier surface so L19 becomes measurable (Tier 1: zero memory rejections/vocabulary). Recommend: adopt, and define the L19 metric before any M-gate.
3. **M14 margin policy**: fix margins *before* baselines (e.g. ≤1.25× peak RSS, ≤1.10× wall, ≤1.5× allocs vs hand-written C/Zig) and define the violation action (recorded deviation vs rework). Recommend: fix before; no post-hoc targets.
4. **M2 out-of-memory**: extent-based recoverability (current) vs Qwen's fallible-signature rule. Recommend: fallible-signature — corpus 1's request loop otherwise dies on transient OOM; decide with before/after examples.
5. **M33 lookup semantics**: optional copy (current) vs temporary view with liveness-based copies. Recommend: view — copy-everywhere is a predictable M14 failure; needs M13 alignment.
6. **Phase C sequencing**: split additive (C1: optionals, owning `string`, `List`, `Map`, `Table`) from subtractive (C2: remove `new`/`del`/`nil`/stored `ref` after D+E margins). Recommend: yes — this is the faithful reading of L22 ("keep my a7 syntax for now").
7. **Confirm the L20 reading** ("C performance and simplicity without C++ complexity/hidden costs") — explicitly unconfirmed in the ledger scope limits; it anchors M14 and contract item 12.

Housekeeping items (findings 5-11) are factual corrections that need no approval-rule cycle; I'd apply them immediately.
