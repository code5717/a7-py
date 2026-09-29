> **Source:** OpenCode zai-coding-plan/glm-5.3 advisory answer to scratchpad advice prompt (reproduced in advice-prompt.md). Tool-progress lines on stderr are not included.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

All repository documents requested were read in full (brainstorm, ledger, plan, safety contract, SPEC §§3.3–3.5/6.2/6.3/8, all three plan-research reports, examples 011/025, comparative index). I ran no code and verified no compiler behavior; statements about the compiler are citations of the repo's own recorded observations. **Convention below: [V] = verified fact from the repository docs; [I] = my inference/recommendation.** External prior-art claims are from my knowledge unless the repo research independently records them (I note where it does).

---

# Advisory: A7 Memory Model

## 1. Is the combined goal achievable?

**Verdict [I]: yes, for a large and well-defined class of programs — not universally. The goal as phrased ("Python-simple + no GC + fully compile-time + inferred arenas/pools + reuse") contains a hidden contradiction that must be dissolved by *choosing the residual runtime work and the rejection boundary explicitly*. A7's fixed constraints (recursion ban, immutable bindings, no `&`/`*`, whole-program compilation, fail-closed culture) are unusually favorable — they remove most of the reasons this failed elsewhere.**

The undecidable core: "free exactly when dead" requires knowing runtime reachability. Every GC-free system picks one of: hold longer (regions/arenas), restrict programs (affine/linear), keep runtime work (RC — excluded), or reject (A7's fail-closed). A7 can have three of these four at once. The honest contract is not "zero runtime memory work" but: **no collector, no counts, no pauses; every deallocation *point* is static; residual per-operation costs are bounded and deterministic (bump-pointer increment, free-list push, one generation compare)** [I].

**Where it breaks, exactly [I]:**

1. **Data-dependent lifetimes inside a phase.** Evicting cache entry #k while #j lives; a merge that keeps a runtime-chosen subset of phase-1 objects. No static free point exists. Least-bad: pool free-lists (deterministic slot recycling, memory returned at phase end) or copy-into-outer-home at selection time. Immediate byte-level return is impossible statically — accept and document.
2. **Shared mutable graphs with mid-life removal.** Cycles are *not* the problem under arena reset (reclamation is by home end, not reachability — this is the big win over RC/GC designs [I]). Removal of individual nodes is the problem → handles + generations, exactly the repo's own "checked indices or generation-bearing handles" direction [V: memory-design-codex.md].
3. **Escaping closures/callbacks retaining borrows.** Restrict: non-escaping by default; escaping closures must own captures. G4's likely restriction of storable function values [V: plan README G4] shrinks this to near nothing.
4. **Unbounded accumulation over unbounded time** (caches without capacity, append-only servers). Any static model either rejects or leaks-by-design. Least-bad: capacity/reset knobs on stdlib home types — explicit, visible, deterministic.
5. **Dynamic sizes.** "Resolved compile-time" can mean placement and reclamation structure, never sizes (entity counts, batch sizes). The report can show the structure; the sizes are runtime data [I].

**The least-bad package [I]:** affine ownership floor + inferred homes (regions) + index-lowered links (handles) + pool free-lists where removal exists + in-place reuse under uniqueness + static buffer planning for tensors. Residual runtime: bump allocation, free-list push/pop, generation compare, growth reallocation. All deterministic, none scanning, none paused. This is materially *less* runtime work than Lobster (which keeps RC for shared) and Perceus (RC spine) — achievable only because A7 rejects what it cannot place.

---

## 2. Strongest candidate architecture

The 13 candidates in the brainstorm are not peers. **[I] They decompose into one mandatory floor, one inference spine, and optimization layers:**

**Layer 0 — IR (prerequisite).** Track 4's typed IR [V] must additionally carry: stable allocation-site identities, def-use chains, per-function CFG, a **DAG call graph** (DAG by construction — recursion banned [V: SPEC 6.2]), and interprocedural **effect/flow summaries**. Every later layer consumes this. Without it, no layer is sound — the repo's own MS-1/MS-2 findings (stale fact joins, no call effects [V: memory-security-glm.md §3.1]) are the current proof.

**Layer 1 — Affine ownership floor (not a "candidate"; it is the base).** Heap refs from `new` are affine; ref-typed copies rejected; auto-drop on defined exits; `del` = explicit early release; provenance rule for `del` legality. This is gate G2 option (a) [V: plan README] and the Codex review's Alternative A [V]. It closes MS-3/4/5-class holes *before* any inference exists and provides the uniqueness facts Layers 4–6 need. The brainstorm should remove this from the candidate list and treat it as settled input.

**Layer 2 — Interprocedural escape analysis via DAG summaries.** Each function computes, bottom-up in topological order (no fixpoint needed — the recursion ban's gift): which parameters' storage its results/stores can reach, which fresh allocations escape, which globals it writes. Compose summaries at call sites. Classification per allocation site: **no escape → stack; escapes to a known home → that home; escapes to unknown home (runtime-keyed global, channel, native) → move/copy required or reject.** This is Go-style bottom-up escape analysis [V-corroborated: research cites Go 1.27.1] with rejection instead of heap-escape.

**Layer 3 — Home inference (the region system).** Tofte–Talpin-shaped constraint solving, radically simplified [I]:
- Every allocation site gets a lifetime variable over the set of **homes**: function frame, loop iteration, task, or a named long-lived owner (world/session/model — the *containers* the program actually uses).
- Every use that outlives a home (store into a longer-lived object, return beyond caller, capture, channel send) emits a constraint.
- Solve each variable to the **least** satisfying home (least = tightest memory). Diagnostics fire when no home satisfies — "value created here outlives every home it can belong to."
- Crucial difference from MLKit [I]: homes are coarser than lexical scopes and include iteration/task granularity, which kills most of the loop-fixpoint pain — per-iteration allocations die at iteration end *unless* a constraint (an explicit store into an outer accumulator) hoists them. Hoisting is data-flow-visible, not inferred from nothing.

**Layer 4 — Pool formation and handle lowering.** Same-type allocations sharing a home → array-backed pool. Cross-object references the compiler cannot keep as raw pointers (growth, removal, layout freedom) lower to **handles: index + generation**. Generation checks default ON; elided only by static proof (no slot reuse before home end) — the same proof-driven-checks pattern as the existing index-bounds engine [V: SAFETY_CONTRACT]. This is Vale-style generational handles [V-corroborated: comparative/vale.md] without adopting Vale's whole model.

**Layer 5 — In-place reuse and liveness refinement.** Perceus-style reuse analysis [V-corroborated: research cites Perceus PLDI 2021] recast on affine uniqueness: at a point where a value is unique, `x = push(x, v)` and `x = f(x)` lower in place. Also ASAP-style last-use release [V-corroborated: brainstorm names it]: free at last use rather than scope end where liveness is provable. Soundness from Layer 1's uniqueness facts, not reference counts — this is the honest way to get Perceus's wins without Perceus's RC spine [I].

**Layer 6 — Static memory planning for tensors.** Weights/optimizer state = program-home pools with stable slots; per-step activations/tape = step home planned by liveness-interval coloring (XLA buffer assignment / ORT-style arena planning [V-corroborated: numerical-policy-glm.md records ORT's never-shrinking BFCArena — a cautionary knob, not a model]). Tape lifetime ends at step-home end or explicit release; backward-before-release discipline per the T1 session-ownership design, which I concur is the right v1 tensor arrangement [V: memory-design-codex.md T1; I: concur].

**Layer 7 — Layout transformation (SoA), deliberately last.** Once links are indices and there are no address-of/deref operators in the surface language [V], the compiler has *complete layout freedom* — a pool of structs can become parallel arrays with zero observable effect except through native boundaries. This is a genuine structural advantage over C++/Rust that almost no one exploits; but it is a codegen optimization on top of Layer 4, not a memory model [I].

**How the fixed constraints pay off [I, each grounded in verified constraints]:**
- **Recursion ban** → call graph is a DAG: summaries in topological order (no Kleene iteration over call cycles), computable maximum stack depth (the repo's own I-14 [V]), stack-pre-sized homes, and no recursive *construction* patterns to model. Note the ban does not forbid recursive *data* — index-based structures are the blessed form [V: AGENTS.md, examples 025/026].
- **Immutable argument bindings** [V: L6, SPEC 6.3] → no rebinding; writes through parameters are confined to `ref` positions → effect summaries are precise per-argument; non-`ref` arguments preserve caller facts (the repo's I-11 refinement [V]).
- **No `&`/`*`** [V: SAFETY_CONTRACT] → alias formation points are enumerable (`new`, `ref` params, projections, slices); no pointer arithmetic escape hatch; escape analysis can be *sound*, and Layer 7 becomes legal.
- **Whole-program compilation** → no conservative cross-module summaries; diagnostics can point at real allocation sites anywhere.
- **Fail-closed culture** → rejection is already the accepted answer to unprovable operations; memory joins that culture instead of fighting it.

---

## 3. Concepts and names

The draft five, critiqued [I]:

| Draft | Verdict | Replacement | Visibility |
|---|---|---|---|
| **lifetime group** | Two vague words; "group" implies programmer grouping. | **region** (internal; standard term, MLKit/Cyclone lineage) | never in source; appears only in `--memory-report` |
| **family** | Sentimental; describes a lowering, not a concept. | **pool** — call it what it lowers to | stdlib type names + diagnostics |
| **home** | **Keep.** The best of the five: human, memorable, and it names the *extent*, which is the real concept. Define rigorously: a home is a runtime extent with a static end point at which all its memory is reclaimed. | **home** | user-facing *in diagnostics and reports only* |
| **link** | Ambiguous (also "linker"). | **handle** — industry-standard (ECS handles, generational arenas); unifies with native-resource handles [V: memory-design I-22 uses the word] | diagnostics ("stale handle to removed entity") |
| **boundary** | Overloaded (FFI boundary, trust boundary). | **escape edge** (internal); diagnostics phrase it as "escapes its home" | message vocabulary only |

**Concepts the draft list is missing [I]:** **plan** (the emitted static allocation plan — stack slots, homes, pool capacities, elided/retained checks; surfaced in a memory report); **uniqueness** (the fact powering in-place reuse); **step template** (the per-training-step static buffer plan). 

**User-visible surface policy [I]: zero new keywords in v1 source.** The "new concepts" the user asked for should be *named compiler concepts with documented vocabulary and tooling*, not syntax. This is exactly how you keep "super simple like Python" while giving the Jai/Odin/Zig audience what it actually wants from those languages: *visibility and control over what the compiler decided* — via `a7 build --memory-report` (homes, pools, checks elided/retained, reuse decisions), not via annotations. Escape hatches come from stdlib home-owning types (a `Table` with capacity/eviction), never from language fallbacks.

---

## 4. Hard cases

- **Returning allocations** [I]: ownership moves with return; Layer 2 places the storage in the *caller's* home (the classic region-for-return / RVO analogue). Trivial case; should be corpus program #1.
- **Growing lists with references into them** [I]: the vector-invalidation classic. Owner containers are pool/arena-backed; *links are indices, so growth never invalidates them*. Raw borrows of elements (`ref` to an element) are valid only within a region where no growth occurs; growth during a live element borrow → compile-time rejection (conservative v1), mirroring the repo's own iteration-exclusivity direction [V: memory-design-codex]. The blessed user pattern — hold `usize` handles into a collection — is exactly what examples 025/026 already teach [V].
- **Cyclic graphs, parent pointers** [I]: pool of nodes + index links. Cycles are free (reclamation by home end, not reachability). Parent pointer = one more index field. This must be *the* documented representation; it is the single biggest ergonomic win over RC (no cycle collection) and Rust (no lifetime knots).
- **Caches and globals** [I]: a global is a home. Entries placed in the cache's home at allocation (when data-flow knows the destination — no copy needed). Eviction = runtime policy inside a stdlib pool with explicit capacity/reset; per-entry recycling via free list. No silent leak: capacity is part of the type's constructor, visible in source.
- **Closures** [I]: non-escaping default (borrow captures); escaping requires owned capture (move) → closure's home = destination home. With G4 restricting storable function values [V], this stays small and checkable.
- **Long-running loops/servers** [I]: iteration = home; per-iteration arena reset keeps RSS flat across unbounded iterations (the Jai frame-allocator / Odin temp-allocator pattern [V-corroborated: research notes both idioms], inferred instead of named). Escape from iteration N to N+1 must go through an outer-home accumulator — a constraint edge, diagnosed otherwise.
- **Entity removal** [I]: pool free-list + generation bump on slot reuse; stale handles caught by one compare. Checks elided only when Layer 4 proves no reuse before home end. Deterministic, O(1), no scanning.
- **Tensors, views, autodiff tape** [I]: T1 session ownership [V: recommended by Codex research; I concur]; views = temporary borrow descriptors (storage id + offset/shape/stride), non-storable across phases; tape = step-home allocation planned by interval coloring; backward then step-home end (or explicit release) frees the tape before the next step — bounded peak. Saved-storage mutation → reject or typed preflight failure (the repo's own policy menu [V]); in-place weight update legal only after release. Aliasing/overlap rules as in the repo's tensor rows [V].
- **Optimizer state and checkpoints** [I]: program-home pools, slots stable after first step; checkpointing is a serialization boundary (copies out), loading allocates fresh into current homes. No lifetime hazard beyond what T1 already answers.
- **Tasks/channels** [I]: structured tasks (G7 direction [V]) make this clean: task = home; move-on-send/spawn (already the committed direction [V: memory-security-glm I-18]); values moved into a task live in a home that ends at join — *deterministic task cleanup by construction*. Channel-queued values need a home ≥ join point; interprocedural constraint solved by Layer 3. The "allocator dies with sender" hazard [V: memory-design-codex] dissolves if task homes are children of the spawner's home.
- **Native kernel buffers** [I]: borrow-for-the-call by default (no retention past return unless the ABI descriptor declares transfer); kernel workspace = per-call scratch home, reset after return. Opaque affine handles per I-22 [V]. Native calls are full invalidation + escape sinks unless the Track-10 descriptor says otherwise.

---

## 5. When inference fails

**[I] Recommendation: reject, with a structured diagnostic; no silent fallback ever; library-level escape hatches instead of language-level ones.**

A placement diagnostic must contain four things: the value's creation site and inferred home; the escape edge (store/return/send/capture) and its target home; and 2–3 concrete fixes in source terms ("store it into `world.registry` from the start", "copy at the boundary with `clone`", "return it and let the caller own it"). Because placement is inferred *from* the stores, the fix is usually moving an allocation site — which is how Python programmers already reason ("this dict lives on self").

Rejected fallbacks: silent promotion to a bigger home (hidden leak, destroys predictability); automatic GC of last resort (contradicts L15); heavy annotation language (contradicts L17). The acceptable fallbacks are **stdlib-level**: an explicit `Cache`/`Table` home with capacity/eviction for genuinely data-dependent lifetimes; `clone` at boundaries. Fail-closed safety is preserved because *the compiler still placed every byte* — the policy just lives in a checked library type, visibly in the source. This matches the repo's existing philosophy exactly: proof-or-reject [V: SAFETY_CONTRACT], with typed library operations for runtime facts [V: memory-design-codex].

---

## 6. Prior art, precisely

| Source | Directly usable | Trap |
|---|---|---|
| **MLKit / Tofte–Talpin region inference** (Tofte–Talpin 1994/1997; Hallenberg–Elsgaard–Tofte implementation papers) | Constraint formulation; "allocations into regions with static end points"; evidence regions can coexist with other management [V-corroborated: research cites elsman/mlkit] | Lexical-only regions over-retain (their storage-mode analysis exists precisely for region leakage); polymorphic region schemes — A7 dodges both via coarse homes + whole-program + no recursion |
| **ASAP / static deallocation** (Guilloux–Schmitt "ASAP: a practical stack allocator"; Guyer–McKinley LIFO stack allocation) | Liveness-based free-point insertion; last-use refinement over scope-end | Needs precise liveness; use as refinement layer, not the floor |
| **Lobster** (van Oortmersen) | Proof that a small language gets GC-like ergonomics with mostly-static ownership | Falls back to runtime RC for shared refs — evidence for where static-only *ends*, which A7 replaces with handles + rejection |
| **Koka/Perceus** (Reinking et al., PLDI 2021) | Reuse analysis; functional-but-in-place; precise drop timing at last use [V-corroborated] | Soundness spine is RC; A7 must derive uniqueness from affine ownership instead |
| **Hylo / Val** (mutable value semantics; "Mutable Value Semantics" ~2021) | The *user model*: values + projections, call-site exclusivity | Needs generic lifetime-dependency types (cf. Swift SE-0446 non-escapable) — the type-system complexity A7 avoids via index lowering |
| **Vale** (generational references/generational arenas) | Handle concept: near-zero-cost dangling detection | Alpha status [V: research notes]; generation-exhaustion policy undefined — A7 must define it (repo already flags this [V]) |
| **Cyclone** (Grossman et al., POPL 2002) | Proof regions give safe manual memory in a C-like language; fat-pointer discipline | Annotation burden was real [V-corroborated: "8% migration" in comparative README]; A7's answer is inference + rejection, not annotations |
| **Swift OSSA / ownership** (SE-0377/0390/0427/0429/0446) | Ownership-aware IR instruction design (borrow/guarantee/consume) for Layer 0/1 | Dynamic exclusivity fallback traps [V: research verified fatalError in 6.3.3 runtime]; A7 has no runtime fallback slot → must be statically more conservative |
| **Go escape analysis** | Bottom-up per-function escape summaries at production scale | Escapes silently to GC heap; A7 rejects instead |
| **ML compiler memory planners** (XLA buffer assignment; TVM static memory planner; ONNX Runtime BFCArena) | Liveness-interval coloring for tensor buffers [V-corroborated: ORT arena behavior recorded] | Assume static graphs — eager A7 needs step templates; ORT's never-shrink arena is the cautionary default |
| **Jai / Odin / Zig** | The *tooling* and idiom layer: implicit context/frame allocators, temp allocator per frame, allocators-as-values + ArenaAllocator lowering [V-corroborated: research notes; Zig 0.16 docs] | Jai has no authoritative docs [V: research says so] — inspiration only; none of the three provides a proof model to copy |

---

## 7. Critique of `docs/plan/memory-brainstorm.md`

Sound: contract-first, corpus-first, mechanisms mapped to corpus, spikes after reading, decision session last. Specific defects [I]:

1. **Mis-ordered: the affine floor is listed as candidate #1 among 13 peers** (line 90). It is the prerequisite for uniqueness, liveness soundness, and the closure of today's accepted double-free programs [V: G2 observation; MS-3]. Pull it out as settled input (it is gate G2(a) [V]); the brainstorm should decide only what goes *on top*. Otherwise session 3 relitigates the safety floor.
2. **Two-tier taxonomy missing.** "Layout transformation," "allocation elision and fusion," and "in-place reuse" are optimizations enabled by a model, not memory-management models. Mixing them with regions/ownership invites scoring a SoA transform against a lifetime guarantee. Split: *models* (who owns, when freed) vs *optimizations* (where laid out, when reused).
3. **Missing: the Zig lowering/ABI session.** How homes map to Zig allocators (arena per home, stack frames, pool arrays as `ArrayList`-backed slots), how growth failure surfaces under inferred placement, how `ref` params lower when storage may move. These constrain the source model (index links surviving growth is a *semantic* choice). No session owns this.
4. **Missing: diagnostics contract in session 1.** For a fail-closed Python-simple language, the placement error message *is* the UX. Session 1 should specify the required parts of a placement diagnostic (creation site, home, escape edge, target, fixes).
5. **Missing: concurrency in the contract.** Tasks/channels appear in the corpus but not in session 1's guarantees. "Move-only across tasks; task home ends at join" is a contract statement.
6. **Missing: "no leaks" under retention.** Arena-holds-until-phase-end is not a leak but looks like one in RSS. Define the promise as "all memory returned at home end; every home ends" + documented retention.
7. **Missing: memory-report tooling** — the zero-syntax answer to open question 4 that satisfies the control-oriented audience.
8. **Open question 4 is the central UX decision and belongs in session 1**, not floating. My recommendation: never in source; always in diagnostics/reports.
9. **Falsification corpus, run first.** Session 2's coverage list is good but ordered by feature. Reorder by *killing power*: (a) server loop caching per-request results into a capacity-evicting global LRU; (b) tree with parent pointers + node removal + iteration; (c) builder holding element links across growth; (d) training loop: backward → in-place weight update → next step; (e) two-phase merge keeping a runtime-selected subset; (f) comparator closure capturing locals; (g) channel worker storing received data into a shared registry; (h) native kernel retaining a slice past return. Any candidate that survives (a)–(h) on paper is worth a spike; most will die on (a), (e), or (g) — better in session 2 than session 5.
10. **Determinism assumption unstated:** inference order and tie-breaking must be specified and deterministic, or rejection UX and build reproducibility break.

---

## 8. Concrete A7 examples (proposed syntax — not current A7; no recursion, `usize` indices, no `&`/`*`)

Current verified surface used: `::` declarations, `fn`, `:=`, `ret`, `match`, `for`, `ref` params, structs, fixed arrays [V: SPEC, examples]. Everything below is [I].

```a7
// PROPOSED 1 — ordinary code: no new, no del, no defer del.
// Compiler: result placed in caller's home; loop iteration is a home,
// reset each pass; the accumulator lives in main's home.
score :: fn(tokens: []Token) f64 {          // tokens: read-only binding (L6)
    total := 0.0
    for i := 0; i < tokens.len; i += 1 {    // i: usize
        total += weight(tokens[i])          // per-iteration home: scratch dies here
    }
    ret total
}
```

```a7
// PROPOSED 2 — graph with parent pointers and entity removal.
// Links are handles (usize + generation, compiler-lowered); cycles are free;
// removal is a free-list push; stale handle = one compare, caught.
Node :: struct { value: i32, parent: usize, next: usize }  // 0 = "none"

main :: fn() {
    world := Graph{}                    // world is a long-lived home
    a := world.add(Node{value: 1, ...}) // a: usize handle
    b := world.add(Node{value: 2, parent: a, ...})
    world.remove(a)                     // O(1); slot recycled later
    // world.remove(a) again, or use of a stale handle: caught,
    //   compile-time when provable, one checked compare otherwise
}
```

```a7
// PROPOSED 3 — growing list while holding links into it.
// Handles survive growth (they are indices); raw element borrows do not.
queue := WorkList{}
h0 := queue.push(Job{...})       // h0 stays valid across any growth
queue.push(Job{...})
queue.push(Job{...})
// ERROR case (rejected): j := queue.borrow(h0); queue.push(...); use j
```

```a7
// PROPOSED 4 — server loop: flat memory across unbounded requests.
main :: fn() {
    sessions := Cache{capacity: 4096}        // explicit capacity: no silent leak
    loop {
        req := net.accept()                  // req lives in the iteration home
        hit := sessions.find(req.key)
        if hit == 0 {
            sessions.put(req.key, build(req)) // escapes iteration -> placed
                                             // in sessions' home by the store
        }
        answer(hit, req)
    }                                        // iteration home resets: RSS flat
}
```

```a7
// PROPOSED 5 — training step: tape freed before update, bounded peak.
step :: fn(t: Trainer, batch: Batch) f64 {
    logits := forward(t.model, batch)   // activations: step home, statically
    loss := cross_entropy(logits)       //   planned by liveness intervals
    grads := backward(t.session, loss)  // tape traversal, iterative (no recursion)
    ret loss                            // step home ends: tape + activations freed
}                                      // weights updated by caller from grads
```

```a7
// PROPOSED 6 — in-place reuse under uniqueness.
xs := List{}; xs.push(1); xs.push(2)
xs = map_in_place(xs, double)   // compiler proves xs unique at this point:
                                // lowered in place, no copy, no reallocation
```

```a7
// PROPOSED 7 — task: deterministic cleanup at join; move-only handoff.
main :: fn() {
    data := load_table()                       // owned; home: main
    handle := spawn(parse_all, data)           // data moved; home: the task
    result := join(handle)                     // task home ends here:
}                                              //   all task memory reclaimed
```

---

## Decisions to put to the user (per the approval rule [V: decisions.md])

1. Accept the reframed contract: no collector/counts/pauses, static deallocation points, bounded deterministic residual costs (bump, free-list, generation compare) — instead of "zero runtime memory work."
2. Accept rejection-with-diagnostics as the inference-failure policy; no silent fallbacks; library home-types (`Cache`, `Table`) as the escape hatch.
3. Confirm zero new source keywords in v1; concepts surface in diagnostics + `--memory-report` only.
4. Confirm handle-based graphs/lists as the blessed representation (indices + generations), replacing raw `ref` links in examples/docs.
5. Confirm phased order: affine floor (G2a) → homes/escape → pools/handles → reuse → tensor planning → layout transforms.

The single fastest falsification step available this week: write corpus programs (a), (e), and (g) from §7.9 and hand-trace the home-constraint solution on paper before any mechanism is scored — it will kill or confirm the home model in a day.
