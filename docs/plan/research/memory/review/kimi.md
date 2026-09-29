> **Source:** Kimi CLI (kimi -p) review of everything learned; prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16. Reviewed docs/plan/memory.md revision 2.  
> **Status:** Advisory. Body preserved verbatim, including progress lines and the CLI's two-space indent. User decisions are in the [ledger](../../../decisions.md).

• I'll review the core documents first, then the supporting research and audits as needed.

• Let me verify a few key facts directly and check the remaining advice briefly.

• # External review: the v1 plan, ledger, memory plan rev 2, research, advice and audits as a whole

  ## What I verified directly (reads/greps at this tree, no compilation run by me)

  - `a7/safety.py:236` — the move/delete fact set is a name-keyed `set[str]` (audit 1 F1 confirmed).
  - `a7/backends/zig.py:159` — one global `std.heap.page_allocator` backs all allocation (advice-fable F3 confirmed).
  - `docs/plan/memory.md` gates are numbered M1–M36 but **M25, M28 and M29 are defined nowhere** in `docs/plan/` (grep for all three returns nothing).
  - `docs/SPEC.md:1096,1109` — tensor `data: ref T` (stored reference, contradicts M4); `docs/SPEC.md:192` — `fn_ptr: ref fn() void = nil`.
  - `docs/plan/README.md:211` — track 6 still reads "Approved ownership surface, **deletion**, defer, provenance…", contradicting M3's removal of `del`.
  - `docs/plan/README.md:185` — G7 now points at the memory plan and G5 (audit 5's F9 complaint on this line was fixed); track 6 was not.
  - `docs/plan/research/memory/edge-case-audit.md:12,15` — audit 2 (collections, strings, exclusivity, optionals, reuse) and the GLM memory-safety review are still "Running/Pending".

  Everything the audits report about current-compiler behavior (dangling `ref` returns, double `del`, `both(x,x)` accepted, etc.) is their compile-only probe evidence, which I did not rerun; I treat it as credible because the code-read facts underpinning it check out.

  ## Overall judgment

  The memory plan revision 2 is the coherent core the three advisors independently converged on: value semantics + internal affine ownership + inferred extents + generation-tagged ids + static-uniqueness reuse + buffer planning, with rejection instead of runtime fallback. Given L15 ("compile-time, no GC, no RC"), L19 ("users shouldn't care about memory") and L20 ("C-like performance and memory"), this is not merely a good choice — it is close to the only consistent package, and the Gemini comparison (`gemini-comparison.md:32-36`) correctly identifies why: reuse-by-uniqueness systems (Koka/Lean/Roc) need runtime counts; static-placement systems (MLKit, Carp) don't reuse; A7 is trying to get both, which no production system has shipped.

  The plan mostly *knows* this. Revision 2 honestly resolved all nine rev-1 blockers (B1–B9). What follows are the remaining contradictions, infeasible parts and weak recommendations, ranked.

  ---

  ## Blockers

  ### B-1. L19 is asserted, never measured — and the plan's own corpus suggests it will fail often

  Contract item 8 (`memory.md:71-85`) lists **nine** user-visible rejection classes. Every one is a memory concept reaching a user who, per L19 (`decisions.md:50`), "shouldn't care about memory in general": views outliving owners, growth while a view is live, moves into tasks, autodiff history leaving a step. Of the 23 falsifying-corpus programs, about 9 are expected rejections (`memory.md:303-327`). Worse, audit 5 (part 6, line 496) notes the corpus expected results "come from the design itself" — self-consistent, not independent evidence.

  The "L19 metric" appears as Phase A exit evidence (`memory.md:286`) but is defined nowhere, and audit 3 (G-22) flags exactly this. There is no hand-traced rejection-rate estimate over *realistic* Python-style code. If idiomatic code hits rejection classes 1–2 (exclusivity, view lifetime) with any frequency, L19 fails and with it the plan's reason to exist.

  *Fix:* Phase A must hand-trace a large realistic corpus (all 42 current examples rewritten in the proposed style, plus ~50 new Python-idiomatic programs written by someone other than the plan's authors) *before* any M-gate is presented for approval. Define the metric operationally: rejections and memory-related rewrites per program, with the acceptability threshold fixed by the user in advance.

  ### B-2. "Values everywhere + copy when unproven" versus L20's C-like memory use — unproven on the acceptance workloads

  Contract 4 (`memory.md:56-60`) makes copy the meaning and removes copies only when proven unobservable; contract 8's escape hatch (`memory.md:84-86`) is "copy out on the escaping path". Audits 1 and 4 document what this costs in the worst cases: a move between stores is a deep copy (audit 1 EC1-C04), `snapshot := model` then one update copies every parameter with peak doubling (audit 4 EC4-08), a single-element write to a shared 1 GB tensor copies the whole tensor (EC4-09), and compiler-inserted copies can abort on OOM on a line with no visible allocation (audit 3 EC3-27 — audit 3 itself calls this "the worst L19 case").

  The danger is concentrated exactly where v1's acceptance criteria live (L7/L10: CPU training of a classifier and a transformer). Tensors-as-values is the single riskiest modeling choice in the plan: the joint rule (unique and unsaved → in place; saved → reject per M18; otherwise → copy) has never been hand-traced over a complete training loop. M14's performance margins are explicitly "set after Phase A baselines" (`memory.md:238`), and audit 5 notes the baseline-authorship procedure is undefined and bias-prone.

  *Fix:* promote full hand-traces of the classifier step, the decoder step (P2, P5, P6 from audit 4) and checkpoint load to **Phase A exit evidence**, not Phase F. If the traces show systematic copying the reuse layer can't eliminate, the tensor model needs revision before 364 tests and 13+ examples are migrated onto it (audit 5's scale numbers). Fix the baseline procedure: independently authored C/Zig baselines, pinned toolchains, reviewer sign-off, before margins are set.

  ### B-3. The L17-versus-L19 contradiction is resolved by fiat, not by user decision

  L17 (`decisions.md:48`): "we need new concepts". Contract 9 (`memory.md:87-90`): no memory vocabulary ever; users meet only values, collections, optionals, **typed ids** and **move-only resources**. GLM's advice (`advice-glm.md:79`) recommended zero new keywords; the user's words say the opposite. The plan silently assumes L19 overrides L17 — audit 5 F15 flags that this assumption "is not recorded" anywhere.

  And the assumption is contestable: `Id(T)` and move-only resources **are** new concepts a Python user must learn. "Why does `b := a` copy a list but move a file?" and "why can't I store this id?" are exactly the kind of thinking L19 promises to eliminate. This may still be the right design — I believe it is — but it is a user decision the ledger does not yet contain.

  *Fix:* put the question to the user explicitly with examples: are `Id(T)`, `Table(T)` and move-only resources the approved reading of L17's "new concepts", with memory words confined to diagnostics and the report? Record the disposition.

  ---

  ## Major

  ### M-1. Revision 2 is explicitly incomplete — do not present M-gates yet
  Audit 2 (collections, strings, exclusivity, optionals, reuse — the heart of the Python-simple surface) and the GLM security review are both pending (`edge-case-audit.md:12,15`). Audits 3 and 4 each end with 10 questions for GLM that remain unanswered, including wrong-descriptor use-after-free (EC3-42), forged/stale ids across tasks, and dataset-controlled shapes as a plan-cache exhaustion vector (audit 4 GLM Q3). Contract 2's "no use after free" holds only "to the extent its binding descriptor is correct" (`memory.md:52-53`) — the security qualification of that escape hatch does not exist yet. Recommend revision 3 + completed GLM review as a precondition for any gate approval.

  ### M-2. M2's abort policy is a behavioral cliff that needs a worked example
  M2 (`memory.md:236`): allocations outside task/step/session extents stop the program; audit 3's EC3-33/EC3-64 add that abort runs no defers and no releases. A Python user gets a recoverable `MemoryError` almost anywhere; an A7 server loop (corpus 1) dies on transient OOM unless each request is a task. This is defensible — but it is the single most surprising runtime behavior in the plan, and the corpus has no program demonstrating the *recommended* recoverable pattern (a request handled as a task). Add one to the corpus and show M2 with before/after examples at approval time.

  ### M-3. Training-extent *identification* is unspecified heuristic inference
  M11 (`memory.md:255`) lists "process, session, optimizer step, microbatch and call extents; never written in source" — but the compiler must *recognize* these boundaries in unannotated code. Audit 4 G-4 proposed identification rules (session = extent of the value holding parameters; step = loop containing the parameter write) which were not adopted; nothing in rev 2 says how inference works or what happens when it guesses wrong (answer: silently different memory behavior — invisible to the user, violating the spirit of L19's predictability). Audit 4's own EC4-21 suggests plain loop-iteration + call extents with loop-carried accumulators suffice for gradient accumulation. *Fix:* simplify M11 to structurally identifiable extents (call, iteration, task, process, plus value-owned stores), or specify the identification rules and make them a gate sub-question.

  ### M-4. M6 presupposes G4 option (b), which is undecided
  Rev-2 M6 (`memory.md:221`) allows capture-free function values "anywhere", including struct fields. That reopens exactly the hole G4 (`README.md:156-164`) describes: recursion through stored function values that the name-based ban misses. `memory.md:187-189` hedges ("if stored function values stay non-recursive (v1 gate G4)"). Make G4(b) — type-informed call-graph edges — a declared prerequisite of M6's storage permission, or downgrade M6 to non-stored function values.

  ### M-5. Whole-program analysis cost has no budget and no failure mode
  Layers 0–8 (`memory.md:173-184`) stack monomorphization, bottom-up escape summaries, extent inference, storage formation, copy removal, buffer planning and SoA over the whole program. The known-gaps list (`memory.md:344`) names compile-time cost limits, but no gate states what happens when analysis exceeds the budget — rejection is not in the closed list of contract 8. For the transformer acceptance workload this is a real feasibility question. *Fix:* add a gate or Phase A task: per-analysis cost model, a deterministic degradation order (e.g., skip SoA, then buffer packing, then copy removal — never skip soundness layers 0–3), and a hard compile-time bound with a diagnostic.

  ### M-6. M32's flat "no returned views" will hit zero-copy parsing hard, and a costed alternative exists but isn't presented
  M32 (`memory.md:228`): no returning views of `ref` data in v1. Fable's advice (§1, break point 3) proposed the middle option — a callee may return a view into a *by-value* argument with the dependency tracked internally — which covers the tokenizer pattern that idiomatic code in this performance class uses constantly. The plan chose the simple reject without presenting the alternative or its cost. Add it to M32 as an explicit option; default to reject in v1 only after a tokenizer-style corpus program quantifies how often the rejection fires.

  ### M-7. The silent-copy fallback chain is never stated as one rule
  Contract 4 (copy at binding), contract 8 (copy out on escape path) and M8 (report) together define a fallback total order — prove uniqueness → reuse/move → reported copy → reject (9 classes only) — but no single passage says so, and `synthesis.md:42-44` still records "no hidden copy" as the policy. Audits 1 (gap 1, 3) and 5 (part 2, synthesis row) both flag the unreconciled text. *Fix:* one contract paragraph stating the total order, plus amending the synthesis line with a superseded marker (the pattern the ledger already uses).

  ### M-8. Nested-value semantics is the biggest silent Python divergence and gets only a lint
  `row := grid[0]; row.append(5)` leaves `grid` unchanged (audit 1 EC1-A08) — the exact opposite of Python. M30 makes for-in bindings immutable copies for the same reason. Both are *correct* under value semantics, both are S-class silent surprises (audit 3's scale), and the plan's mitigation is "document the rule plus an optional lint" (M8). The rule "bindings copy, place expressions change in place" (`memory.md:119-120`) deserves gate-level prominence with before/after examples aimed at Python users — it is arguably the most important single semantic in the whole design for L19.

  ### M-9. Missing gate numbers M25, M28, M29
  Verified: no definition exists anywhere. Either renumber the gate tables or add the missing rows; as written, "gates M1–M36" (`decisions.md:100`) overcounts by three.

  ---

  ## Minor

  - **Track 6 wording** (`README.md:211`) still says "deletion" — update to "internal ownership, automatic release".
  - **Contract 11 determinism** (`memory.md:93-94`) vs the compiler's own nondeterminism sources noted by audit 5 (`id(node)` keys, Python set iteration in `safety.py`): add an implementation rule — all analysis iteration ordered by stable keys — to Phase B.
  - **Runtime planner determinism** (M20): state that the runtime shape planner and its cache eviction are deterministic per (shape signature, build), so contract 11's determinism claim extends to residual runtime work.
  - **M10's hidden blocking**: scope-exit cancel-then-join makes early `ret` block on children (audit 3 EC3-03, S-class). Correct under structured concurrency, but call it out in the gate presentation — Python users will not expect `ret` to wait.
  - **G1's observed float-division defect** (`README.md:74-76`) is correctly routed to track 1; just note the memory plan's checked-size-arithmetic row (residual work table, `memory.md:279`) depends on G3's resolution — the dependency is present via M16/M2 but worth one explicit line.
  - **Corpus 14** (`swap(a[i], a[j])`) currently has *no compiling current-A7 form at all* (audit 1 F11: the SPEC `swap` fails two different ways). The corpus entry should say so; today it reads as if only the memory rule is at stake.
  - **Contract 8 class 9** ("reading a variable no path initialized") is not memory-related; fine to keep, but label it as borrowed from the correctness track.

  ## What the plan gets right (so the fixes land in context)

  Revision 2's resolutions of B1–B9 are technically sound: M2-by-extent instead of by-type, the closed nine-class rejection list, `Id(T)` generations with optional lookup, consume-on-`backward` (M17), static rejection of saved-value mutation (M18), validate-then-write-in-place checkpoints (M24), channel close without sender counting (M27), and the interim lowering phase C′ as de-risking before placement exists. The falsifying corpus is the right instrument, and the evidence rules (`memory.md:329-338`) match the AGENTS.md test-quality rule. The honest framing — over-retention as the cost, rejection as the failure mode, residual runtime work enumerated — is exactly what L15 requires and what the research supports.

  ---

  ## Decisions the user must make

  1. **L17 vs L19 (blocker B-3).** Are `Id(T)`, `Table(T)` and move-only resources the "new concepts", with memory vocabulary confined to diagnostics and the memory report? *Recommend: approve this reading and record that L19 overrides L17's "new concepts" being memory concepts — it is the only reading consistent with the rest of the plan.*
  2. **Gate timing (M-1).** Require audit 2 and the GLM security review to complete (revision 3) before any M-gate is presented. *Recommend: yes — approving gates on an explicitly incomplete audit base invites re-litigation.*
  3. **The L19 metric (B-1).** Define it now: independently written realistic corpus, rejection/rewrite rate per program, threshold fixed in advance. *Recommend: block M-gate approval on Phase A producing this measurement; set the threshold only after seeing the trace results.*
  4. **Copy-fallback visibility (B-2, M-7).** Approve the total order (prove → reuse → reported copy → reject) and whether costly-copy warnings are on by default in loops and above a size threshold. *Recommend: warnings on by default for both; the report always available.*
  5. **Tensor-model proof before migration (B-2).** Make hand-traced classifier/decoder training loops Phase A exit evidence. *Recommend: yes — cheapest possible falsification of the riskiest modeling choice.*
  6. **M2 abort semantics (M-2).** Abort outside task/step/session extents, no defers on abort. *Recommend: approve only alongside a corpus program showing the recoverable per-request-via-task pattern.*
  7. **M11 extent identification (M-3).** Structural identification rules vs simplified extents. *Recommend: simplify to call/iteration/task/process plus value-owned stores (audit 4 EC4-21); revisit session/step inference only if the training traces demand it.*
  8. **G4 before M6 storage (M-4).** *Recommend: G4 option (b), type-informed call-graph edges, as a stated prerequisite.*
  9. **M32 alternatives (M-6).** *Recommend: present reject vs internal-dependency carve-out with a tokenizer corpus measurement; default reject in v1.*
  10. **M14 baseline authorship (B-2).** *Recommend: independently authored, toolchain-pinned C/Zig baselines with reviewer sign-off, fixed before margins — otherwise contract 12's "measured against C" is unfalsifiable.*

