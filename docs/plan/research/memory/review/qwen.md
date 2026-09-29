> **Source:** Qwen Code CLI (qwen --approval-mode plan) whole-plan review of everything learned, prompt in ../review-prompt.md.  
> **Date:** 2026-09-16. Reviewed docs/plan/memory.md revision 2.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

I read the four required documents in full plus audits 1, 3, 4, 5, the synthesis, all three advisor reports, the Gemini comparison, the fact-check, the brainstorm, the v1 plan, the ledger, `SAFETY_CONTRACT.md`, `STATUS.md`, and the 2026-09-14 GLM memory-safety review. I verified a handful of code claims directly. **I ran no code**; every compile/execute result below is quoted from the repository's own recorded probes, which are labeled compile-only there.

---

# Verdict

The memory plan revision 2 is the strongest artifact in this record. It genuinely closed B1–B9 in *form*: contract items 1–12 are a real contract, the nine-class rejection list is the right shape, and a falsifying corpus with per-program expected results and phase assignment is better practice than most production language plans.

It satisfies **six of the eight** user directions outright. It does **not** satisfy L17's "Python-simple" half or L19 at all, and it does not yet admit that in a form you can approve or reject. It also contains five blockers that are internal contradictions or unscheduled prerequisites — three of them in the exact defect classes (B1, B2) that revision 2 claims to have fixed.

## Direction-by-direction

| Direction | Verdict | Evidence |
| --- | --- | --- |
| L15 compile-time, no GC, no RC | **Satisfied**, honestly qualified | `memory.md:49-51, 69-70`; §6 residue list |
| L17 compiler-grouped arenas and pools | **Satisfied** | layer 5, `memory.md:180`; layer 7, `:182` |
| L17 Python-simple surface | **Not satisfied** | §2 requires the user to choose `usize` positions vs `Id(T)`, understand `Table` vs `List`, never store or return a slice, handle optionals from every lookup, treat resources as move-only, and know "bindings copy, places change in place" (`memory.md:107-120`) |
| L18 reuse and optimization | **Satisfied** | layers 6–7, `memory.md:181-182` |
| L19 users do not care about memory | **Not satisfied, and not measurable** | "L19 metric" appears once, undefined, as a Phase A exit condition (`memory.md:286`) |
| L20 C-like performance and memory | **Asserted, not enforceable** | contract 12 (`:95-98`) blocks release on violation, but M14 (`:238`) sets the margins *after* the baselines, and no action is defined for a workload that cannot meet them |
| L21 no Zig-style mental load | **Satisfied** | no allocator, arena, pool or lifetime appears in source |
| L22 keep current syntax, Zig backend | **Backend yes; syntax no** | 16 breaking rows (`memory.md:151-167`). L22's own text permits later changes, but Phase C front-loads the *removals* before placement (D) or reuse (E) exist |

---

# Blockers

## B-1. Contract 7 is false as written: the runtime buffer planner and compiler-inserted deep copies are missing from §6

**Verified.** `memory.md:69-70`: residual runtime work "is listed… See section 6. Nothing else runs at run time for memory management." But:

- Layer 7 (`memory.md:182`) and M20 (`:259`) require "a deterministic runtime planner with a bounded cache for dynamic shapes" plus "shrink on out-of-memory". §6 (`:271-281`) lists six items; none is buffer planning, plan-cache maintenance, or arena shrink.
- Contract 8 (`memory.md:85-86`) promises that when placement fails the compiler "copies the value out on the escaping path". A deep copy of a large value is O(size) runtime work the user never wrote. §6 does not list copies either.

This is the same defect class as the audit's B1 (`edge-case-audit.md`), which revision 2 records as fixed.

**Fix.** Add three rows to §6: (a) *buffer planning for dynamic shapes* → outcome: planner error is an allocation failure under M2; (b) *plan-cache insert/evict, arena shrink* → outcome: none, bounded by M20's count and byte limits; (c) *compiler-inserted deep copy on escape edges and at bindings where removal is unproven* → outcome: allocation failure under M2, surfaced by M8. Then restate contract 7 as "no tracing, counting or scanning at run time" instead of "nothing else runs".

## B-2. Contract 8's rejection list is not closed

**Verified.** `memory.md:71-86` claims those nine classes are "the only memory-related compile errors users see". At least four rejections the plan itself mandates are outside them:

| Rejection | Where mandated | Why the list misses it |
| --- | --- | --- |
| Second `backward` on a consumed loss | M17 (`memory.md:256`) | Use-after-move; class 5 is scoped to "moved into a task" only |
| Use of a resource after it was moved or `close`d | M7 (`memory.md:248`) | Move-only resources imply use-after-move; not listed |
| `ret`, `break` or recoverable failure inside `defer` | `memory.md:198-199` | Not listed |
| `for v in xs { v.x = 9 }` | M30 (`memory.md:225`) | New behavior introduced *by* the memory model |

**Fix.** Reorganize into four families and enumerate exhaustively: (1) exclusivity; (2) escape — view, `ref`, capture, autodiff history, native retention; (3) move and initialization — use after move of a move-only value or a consumed tape, uninitialized read; (4) form restrictions the memory model requires — defer control flow, immutable loop binding. Then state that this list *is* the whole content of the M16 safety-contract amendment, so M16 cannot be approved against a moving target.

## B-3. M6 re-opens the recursion-ban bypass that layers 3–5 depend on

**Verified.** `memory.md:187-190` conditions bounded call depth on stored function values staying non-recursive "(v1 gate G4)"; layer 3 (`:178`) computes "bottom-up summaries over the call graph", which is only fixpoint-free if that graph is a DAG. M6 (`memory.md:221`) recommends "capture-free function values allowed **anywhere**" — i.e. storable in fields and globals.

`docs/audits/2026-09-14/memory-safety-glm-review.md:343-368` (MS-7a/7b) is compile-verified evidence that this already produces recursive Zig today, because callee extraction requires a bare `IDENTIFIER` (`semantic_validator.py:501-544`, `:803-818`, `:1091-1104`). The same review's decision 6 recommends the *opposite* of M6: "function values may only be passed directly as arguments, never stored". v1 README G4 likewise calls option (a) "simpler to verify". Three documents point three ways.

Worse: MS-7 is **absent** from the "Current-compiler defects found" list in `edge-case-audit.md`, so it is not carried into Phase B's exit evidence — even though it invalidates the stack-depth and summary premises.

**Fix.** Make M6 conditional and decide it *with* G4, not after: either G4(a) (no stored function values; drop rejection class 4; migrate `examples/022_function_pointers.a7:31` and `037:130`), or G4(b) (type-informed call-graph edges for field/index/module-qualified callees plus cycle rejection), which then becomes a hard prerequisite of layer 3 and a Phase B exit item. **I recommend G4(b)** — it keeps 022/037 working and preserves the DAG. Either way, add MS-7a/7b/7c to the defect list and to Phase B's exit evidence.

## B-4. Phase F's AI acceptance depends on a native declaration surface that does not exist and has no gate

**Verified.** L9/L10 require A7-owned tensor semantics over established native kernel libraries. M12 requires descriptors declaring "borrowing, retention, returned storage, alignment, completion, callbacks and thread affinity". But audit-3 probe p05 shows `cos :: extern fn(x: f64) f64` exits 6 with "Undefined type (Identifier 'extern')" — no native declaration syntax exists at all (`audit-3 §1`; repeated in `edge-case-audit.md`). I confirmed `a7/stdlib/mem.py` is a 9-line empty stub and `a7/stdlib/` contains only `io`, `math`, `mem`, `string` — there is no `List`, `Map`, `Table`, arena or pool anywhere in the compiler.

So M12 has no baseline, no syntax proposal, and no approval gate in either plan, while corpus programs 8–12 and 16–23 and all of G8 sit behind it. `memory.md`'s Known gaps mention "hostile or incorrect native descriptors" but not the absence of the surface.

**Fix.** Open a gate for the native declaration surface (new syntax, so it needs your approval with before/after examples under the approval rule). Add it to Phase A's "gate decisions" exit and name v1 track 10 as a prerequisite of Phase F in §7.

## B-5. The L19 promise has no definition, and the C-like margin has no failure path

**Verified.** `memory.md:286` makes "L19 metric… recorded" a Phase A exit condition. The metric is never defined. audit-3 G-22 supplied an operational one (count L19 codes R and A, plus S cases a user would report as a bug; that audit measured **R=6, A=15, S=25, D=8, N=14 of 68**) and revision 2 did not adopt it. Meanwhile contract 12 (`:95-98`) makes a margin violation block release, but M14 (`:238`) sets margins *after* the baselines — a target chosen after seeing your own numbers is not a target — and no action is defined for a workload that misses.

Over-retention is not a bug you can fix; it is inherent to the design you chose. `synthesis.md` item 3: "The cost is over-retention." advice-grok: "That last bullet is the honesty tax. MLKit, Cyclone, and every arena system pay it."

**Fix (two parts).**

*(a) Make L19 falsifiable by splitting the surface into two tiers.*
- **Tier 1 (Python tier):** `string`, `List(T)`, `Map(K,V)`, optionals, structs, arrays, loops, functions.
- **Tier 2 (data tier):** `Table(T)`/`Id(T)`, tensors and autodiff, tasks, native.

Metric: **Tier-1 corpus programs produce zero memory-caused rejections and contain zero memory vocabulary.** Tier-2 rejection counts are recorded per gate. This is the only way "users should not care about memory" becomes testable, and it is honest about where the data-oriented concepts have to live. It also matches what L17 actually said — "we need new concepts" — by confining the new concepts to Tier 2.

*(b) Fix the margin policy before baselines,* e.g. ≤1.25× peak RSS, ≤1.10× wall time, ≤1.5× allocation count versus hand-written Zig on corpus 1, 4, 5, 6, 13; and add the missing decision: on violation, either a recorded deviation you approve, or a Tier-2 opt-in hint. Without (b), contract 12 is unenforceable.

---

# Major

**M-1. Contract 5's extent list contradicts layer 4's "innermost extent".** `memory.md:61-65` enumerates call, iteration, task, training step, process. `memory.md:179` says "Innermost extent per allocation". There is no block or branch extent, so audit-1 EC1-C12 stands unfixed: `if big_case { tmp := build_huge(); use(tmp) }` followed by `long_compute()` holds `tmp` for the whole call. In C that memory is gone at the brace. Direct L20 risk. **Fix:** add block/branch extents to contract 5 and layer 4, or a last-use release rule for values above the M35 threshold.

**M-2. `defer` + return is still unsound.** `memory.md:196-199` orders defers before releases and makes a defer body "a use on every exit edge", but never says what happens when the returned value *is* the storage the defer touches (audit-1 EC1-E04; gap 7's third sentence proposed "copied at `ret`"). As written, move-on-return plus defer-use is a use-after-move inside generated code — which contract 2 forbids. **Fix:** adopt copy-at-`ret`, or reject "defer changes a returned value" and add it to the closed list.

**M-3. `usize` positions into a `List` are silently invalidated by removal — no check, no rejection, wrong result.** `memory.md:112-113` says positions are "valid while the element stays in place"; M1 (`:217`) sends removal to `Table(T)`; M5's generations cover only `Id(T)`. Nothing forbids removal from a `List`, and audit-1 EC1-B04 assumes `remove(i)`/`swap_remove(i)` exist. If they do, a held position reads the *wrong live element*. Contract 2 promises no dangling — it does not promise no silent logic error, and this is the one place the plan can be wrong without being unsafe. **Fix:** state in M1 that `List` has no positional removal (that is `Table`'s job), or document invalidation of positions ≥ i and add a corpus program for it.

**M-4. M33 makes every map/list lookup O(size) and will fail M14.** `memory.md:228`: "Return an optional copy." `Map(string, Record)` in a hot loop copies the record per lookup. Python returns a reference; C returns a pointer. audit-1 EC1-F06 recommended the opposite — a temporary view valid until the map next changes, with a copy only where liveness demands — and said "This needs a gate". Revision 2 chose the slow option and dropped the alternative. **Fix:** M33 becomes "temporary view by default; layer 6 copies only where liveness requires it", which is already legal under M13.

**M-5. M2 keys recoverability on extent kind, so one large request kills the server.** `memory.md:236` makes task/training-step/session extents recoverable and everything else a program stop. Corpus 1 is a request loop; a per-request allocation lands in an iteration or call extent → whole-process abort. That is worse than Python (MemoryError propagates) and worse than C. **Better alternative:** recoverability follows the *function's fallible return type*, not the extent kind. Any allocation inside a function whose signature can return an error is recoverable and propagates; allocations in non-fallible functions stop the program. One rule, no new syntax, visible in a signature the user already wrote, and it subsumes `try_append`.

**M-6. audit-3 G-21 (globals + tasks) was not applied.** `memory.md:175` mentions "effect summaries including globals", but no gate or contract item rejects a cross-task write to a mutable global, and mutable globals compile today (audit-3 probe p04). M36 supplies the read half; the write half is missing. There is also no data-race-freedom statement anywhere. **Fix:** add to M36 "a write to a value shared with a running task is an exclusivity conflict (class 1)", and add a contract item: "A7 code has no data races: cross-task sharing is either a move or read-only until join."

**M-7. M11's tensor extents have no identification rule, so "training step" is not implementable as written.** M11 says "Inferred process, session, optimizer step, microbatch and call extents; never written in source". audit-4 G-4 supplied the identification rules — session is the extent of the value holding parameters; optimizer step is the extent of the loop containing the parameter write; microbatch is the extent containing `backward` — and revision 2 dropped them. Without them audit-4 P5 (gradient accumulation across microbatches *inside* a step loop) is undecidable, yet corpus 18 expects "Accept". **Fix:** paste audit-4 G-4's rules into M11 and add a corpus program where the step loop is not the innermost loop.

**M-8. M24 does not answer the question that L10's "checkpoint recovery" acceptance hangs on.** `memory.md:263`: "Validate, then write in place for same shapes." audit-4 EC4-51 and audit-4 §5 Q4 asked what happens if the *data-phase read* fails after some parameters were already overwritten: the model is half-old, half-new. Revision 2 answers only for save (temp file + rename). **Fix:** M24 must pick one — (a) always build-then-swap, all-or-nothing at 2× peak; or (b) in-place write with the model marked invalid on any data-phase error and every later use rejected. I recommend (b) for memory, with the invalid state compile-visible, recorded as a ledger disposition because it changes the L10 acceptance test.

**M-9. Gate-number collision makes the evidence trail unreadable.** audit-4's header admits its M14–M22 "predate plan gates M14-M15 and must be renumbered when merged", but the body is preserved verbatim. So `M14` means "tape lifetime" in audit-4 (EC4-15/16) and "performance margins" in `memory.md:238`; `M15` means "saved-value mutation" in audit-4 and "syntax simplification" in memory.md; `M16` means "parameter identity" in audit-4 and "safety contract amendment" in memory.md. Anyone cross-checking a corpus expectation against a gate gets the wrong gate. **Fix:** add a crosswalk to `edge-case-audit.md` (audit-4 M14→M17, M15→M18, M16→M19, M17→M20, M18→M21, M19→M22, M20→M23, M21→M2, M22→M24) and a pointer line at the top of audit-4.

**M-10. v1 README tracks 6 and 8 were not reconciled; Phase C has a circular dependency.** Track 6 still reads "Approved ownership surface, **deletion**, defer, provenance…" (audit-5 F9 asked for "internal ownership, no deletion"). Track 8 (collections, text) depends on tracks 6 and 7, while memory.md Phase C depends on track 8 — a cycle. **Fix:** retitle track 6; split track 8 into 8a "collections + owning `string`" co-developed with Phase C (depends only on track 4 and G5) and 8b "text, files, paths, time, random, process" (depends on 6, 7).

**M-11. Phase C removes the old surface before the new one is fast — the worst point to be a user.** Phase C deletes `new`/`del`/stored `ref` and migrates ~364 tests, 13+ examples and 10 public docs while placement (D) and reuse (E) do not exist; C′ is an interim single-allocator lowering. Under L22 ("keep my a7 syntax for now") the removals are the *last* thing to land. **Fix:** split C into **C1 additive** (optionals, owning `string`, `List`, `Map`, `Table`, `Id`) with no removals, and **C2 subtractive** (`new`, `del`, `nil`, stored/returned `ref`) gated on D+E margins being met. This also gives the L19 metric something to measure before anything is taken away.

**M-12. M5's "generation exhaustion retires the slot" is an undefined silent failure.** `memory.md:220`. What does a live `Id(T)` do after retirement — return `none` for a record that still exists? That is a silent wrong answer, the same class as M-3. **Fix:** define `Id(T)` as 64-bit {index: u32, generation: u32}, document that retirement needs 2³² reuses of one slot, and make exhaustion a program stop with a diagnostic listed in §6 — not a silent retirement.

---

# Minor

- **m-1.** Layer 8's SoA exclusions (`memory.md:183`) cover native-reached types and `ref` element arguments but not "types that appear as the element type of a slice". M13 slices are views over contiguous storage, so an SoA-transformed `List(Record)` cannot yield `[]Record`. Add the exclusion (audit-5 F10's third case, only partly applied).
- **m-2.** §6 omits the generation bump on slot reuse and the arena-shrink path (see B-1).
- **m-3.** No `Map` iteration-order rule. Contract 11 promises deterministic *placement* but says nothing about deterministic *iteration*, which changes program output and matters for L10 reproducibility and the README's metamorphic test class. Recommend insertion-ordered, documented under M33.
- **m-4.** "Deep equality and hashing of owning values" is in Known gaps, but `Map(K,V)` with `K = string` or a struct cannot exist without it. Move it to a Phase C prerequisite.
- **m-5.** No growable-text type. `string` becomes owning and immutable, `acc = acc + s` in a loop is O(n²) with an allocation per step, and M13 forbids returning views — so text processing has no cheap path. Name an owner for a builder type in track 8a and add a corpus program (split/filter/join over a large text).
- **m-6.** memory.md never cites G3, though §6's "checked size arithmetic" row *is* G3's "checked allocation-size arithmetic". Cross-reference them so L5 wrapping and checked sizes cannot drift: user-written `n * 4` wraps silently; compiler-computed byte counts must not.
- **m-7.** `detach` / `item()` in M23's rewrite are lifetime-adjacent vocabulary in user source; contract 9 (`memory.md:87-90`) bans "lifetime" but not these. State that AI-domain verbs are not memory vocabulary, or the contract reads as violated.
- **m-8.** **Audit 2 (collections, strings, exclusivity, optionals, reuse) and the GLM memory-safety review are both still Pending/Running** per `edge-case-audit.md`, yet `memory.md:5` says "Revision 2 applies the edge-case audit". The largest L19 surface is the one part with no audit. Mark M1, M13 and M33 **provisional** until audit 2 lands; do not put them to you as final.
- **m-9.** Phase B's exit evidence does not cite the existing regression specs and roadmap in `docs/audits/2026-09-14/memory-safety-glm-review.md` §8–§9 (MS-1…MS-12, Phases 0–7). Without the citation the two roadmaps get executed twice, or divergently.
- **m-10.** Contract 1's "no pause" definition is good, but contract 10's iterative destruction means releasing a 10M-node `Table` is O(n) at a known point. Consistent — but M8's report should surface *release* cost, not just copies, or the first user to hit a 200 ms scope exit files it as a GC pause.
- **m-11.** v1 README G2 is marked superseded, but G4 and G5 were not updated to point at M6 and M33, which now own their subject matter.

---

# Decisions for the user

Each needs before/after A7 examples and a compatibility statement under the approval rule (`decisions.md`, 18:32 UTC).

1. **L19 scope — adopt the two-tier surface and the operational metric?** Tier 1 (`string`, `List`, `Map`, optionals, values) guarantees zero memory-caused rejections and zero memory vocabulary; Tier 2 (`Table`/`Id`, tensors, tasks, native) is where the data-oriented concepts live. **Recommend: adopt.** It is the only version of L19 that is both testable and honest.
2. **M14 margin policy — fix it before or after baselines, and what happens on violation?** **Recommend: fix before** (≤1.25× peak RSS, ≤1.10× wall time, ≤1.5× allocation count vs hand-written Zig on corpus 1, 4, 5, 6, 13); violation = a deviation you explicitly approve, recorded in the ledger. No silent hints.
3. **G4 + M6 together — storable function values.** **Recommend G4(b):** type-informed call-graph edges plus cycle rejection. Keeps `examples/022` and `037` working and preserves the DAG premise that layers 3–5 need. G4(a) is simpler but breaks two examples and removes callback tables.
4. **M2 out-of-memory — extent kind or fallible signature?** **Recommend: fallible signature.** A server whose request handler can return an error survives OOM; the current wording aborts the process.
5. **M33 map/list lookup — copy or temporary view?** **Recommend: temporary view**, copy only where liveness demands. The copy-everywhere option is a predictable M14 failure.
6. **M30 loop bindings — immutable copies (breaking) or an approved mutating form?** **Recommend: immutable copies**, plus a `for i, v in xs` idiom and a diagnostic that names it — but bring this to you *separately*, because `for v in xs { v.x = 9 }` is the highest-frequency line in everyday code and the largest single L19 friction point in the plan. Note today's behavior is already broken (A7 accepts it, Zig rejects it), so M30 is an improvement either way.
7. **Phase C sequencing — split additive/subtractive?** **Recommend: yes.** C1 adds the new surface with nothing removed; C2 removes `new`/`del`/`nil`/stored `ref` only after D+E margins are met. This is what L22 actually asked for.
8. **New gate: native declaration surface.** No native syntax exists; M12 and all of Phase F depend on it. **Recommend: open the gate in Phase A**, before any AI work is scheduled.
9. **M24 checkpoint load failure — all-or-nothing (2× peak) or in-place + mark-invalid?** **Recommend: in-place + mark-invalid**, with the invalid state compile-visible. It changes the L10 acceptance test, so it needs your disposition.
10. **M5 id width and exhaustion.** **Recommend: 64-bit {u32 index, u32 generation}; exhaustion stops the program with a diagnostic.** "Retires the slot" is a silent wrong answer as written.
11. **Extent granularity — add block/branch extents?** **Recommend: yes.** Without them A7 holds memory that C releases at the closing brace, and contract 12 becomes harder to meet for reasons no one can fix.
12. **Hold M1, M13 and M33 as provisional until audit 2 and the GLM review land?** **Recommend: yes.** Presenting them as final now would put unaudited recommendations in front of you under the approval rule.
