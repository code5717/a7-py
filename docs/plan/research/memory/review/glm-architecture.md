> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: compiler feasibility of the architecture layers. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

Now let me read the compiler source. Starting with the pipeline driver and semantic context.
Now let me examine the passes and check traversal patterns (recursive vs iterative) across the compiler.
Let me verify a few final coupling details: where backend approvals are consumed, and how the safety pass order interacts with the preprocessor.
One last verification pass on small claims:
# Reviewer report: compiler feasibility of memory plan §4, layers 0–8

Advisory. Read-only; no code was run; nothing was compiled. All statements about compiler behavior are from reading source or citing prior compile-only audits, labeled accordingly.

---

## 1. What exists today (verified facts)

**Pipeline shape.** One shared AST is the only IR: tokenize → parse → imports → name resolution → type check → semantic validation → safety proof → AST preprocessor → Zig codegen (`a7/compile.py:167-432`). There is no CFG, no separate typed IR, no declaration identities. Passes communicate by annotating nodes in place (`node_types` keyed by `id(node)`, `a7/passes/type_checker.py:134-140`).

**Approval plumbing (the good news).** `BackendPlan` already exists as a proof-gated channel from analysis to codegen: `safety.py:206-222` approves `(id(node), operation)` keys; `zig.py:1786-1795` hard-fails codegen for unapproved deref/index/slice/cast/div ops (used at `zig.py:1316,1323,1568,1672,1690,1753`). Memory-plan "new explicit operations for release, extent reset, reuse…" (`memory.md:450-452`) can ride this exact mechanism.

**Facts engine (layer 1's starting point).** `SafetyProofPass` is a per-function walk with name-keyed facts (`FactMap.by_symbol`, `safety.py:149-176`): no branch joins (`safety.py:336-344` restores then-branch facts, never merges), no loop invariants (`safety.py:345-363`), no call invalidation (`safety.py:444-447` visits args only), `moved_symbols` is a name-keyed set fed only by `del` (`safety.py:236,724-726`); the `ValueFact.moved` field is never set (verified: only the definition at `safety.py:145`).

**Memory lowering.** Global `page_allocator`; `new T` → `allocator.create(T) catch null` (`zig.py:1903-1914`); `del` → `if (x) |p| allocator.destroy(p)` (`zig.py:1300-1306,2386-2390`). No arena, pool, release, or reuse anywhere. Stdlib `mem.py`/`string.py` are 9-line stubs; no `List`/`Map`/`Table` (verified by listing `a7/stdlib/`).

**Whole program.** File modules load transitively (cycle-checked, `module_resolver.py:113-197`) and merge into one PROGRAM AST with `module_emit_prefix` (`compile.py:247-261, 597-627`); all semantic passes then run on the combined AST. The whole-program assumption is structurally satisfied for A7 file modules today. Virtual stdlib modules stay outside the merge (`compile.py:607`); native descriptors (M12) do not exist.

**Monomorphization.** There is none in Python. Generic functions lower as Zig `comptime` functions (`zig.py:432-487`); call sites carry a `generic_mapping` annotation (`type_checker.py:1354-1362`) emitted as explicit type args (`zig.py:1653-1660`). `GenericMonomorphizer` (`generics.py:121-251`) is dead code in the pipeline, and its substitutor is shallow — `_substitute_type` does not recurse into array/slice/function types (`generics.py:246-251`), and instantiation uses `copy.deepcopy` (`generics.py:176`).

**Iterative invariant.** Fully iterative: preprocessor (`ast_preprocessor.py:16,62-74,114-169`), compile.py walks (`compile.py:574-595,629-667`), recursion-ban call-graph analysis (`semantic_validator.py:501-589`). Still recursive per AST level: parser (`parser.py:5,1360-1414`), type-checker statement/expression visitors (`type_checker.py:770-777` recurses per block; `visit_expression` per nesting), Zig `visit` (`zig.py:323-390`), module loading (`module_resolver.py:189-193`). The invariant test sets `sys.setrecursionlimit(100)` with ≤10-level nesting (`test/test_iterative_traversal.py:219-258`). Prior finding (compile-only, not re-run): 5000 nested parens → `RecursionError`, exit 8 (`docs/audits/2026-09-14/pipeline-glm-review.md:102`). So the invariant means "shallow programs survive limit 100", not unbounded depth.

**Recursion ban.** Enforced by an iterative call-graph cycle search with alias/shadowing handling (`semantic_validator.py:501-544`), which also gives layer 3 its acyclic call graph — the plan's own feasibility argument (`memory.md:437-440`, `synthesis.md:45-46`).

---

## 2. Layer-by-layer: what must be built, difficulty, order

| Layer | Gap vs today | Build | Difficulty |
| --- | --- | --- | --- |
| 0. Typed IR | Nothing exists | Per-function CFG from AST (explicit fall/break/continue/defer edges), storage identities (binding + access path), stable declaration IDs, effect summaries. Desugar `for-in`, short-circuit ops | **High effort, low risk.** Known algorithms; largest new subsystem; also serves v1 tracks 4-5 |
| 1. Sound facts | Name-keyed, join-blind, call-blind | Rewrite of `safety.py`'s fact engine on the CFG: identity keys, merge-point joins, loop widening/reset, call invalidation from summaries | **Medium-high.** Worklist dataflow fits the iterative invariant; precision must be tuned so valid programs stay valid (CF-25 defect shows current imprecision) |
| 2. Internal ownership | Nothing | Owner-per-storage analysis, move/copy of bindings (M31), release insertion on CFG edges, exclusivity at `ref` call sites (place + index-interval disjointness), rejection classes 1/3/9 incl. definite-initialization | **High.** The no-`&`, no-recursion, immutable-binding rules bound alias enumeration, which is what makes it tractable |
| 3. Escape analysis | No summaries; **no monomorphization** | Python-side instantiation (or a redesign decision — see Blocker B1), then bottom-up summaries in topological call-graph order (no fixpoint needed) | **Medium-high**, gated on B1 |
| 4. Extent inference | Nothing | Innermost-extent choice from summaries + last-use; copy-out on escaping paths; iteration release floor | **High, highest design risk** (determinism contract item 11; interacts with layer 6) |
| 5. Storage formation | `page_allocator` only | Emit stack slots / arena extents / pool slabs per placement plan; growth-failure paths (M2); a lowering abstraction layer — `zig.py` is a 2,395-line monolith consuming the AST directly | **Medium.** Codegen plumbing; isolate Zig API churn (audit 5 gap 5) |
| 6. Copy removal / reuse | Nothing (copies are header copies) | Last-use elision, in-place update on reassignment (Perceus-style, count-free) | **High**, correctness-sensitive, needs layers 2+4 sound first |
| 7. Buffer planning | Nothing; tensors don't exist | Static plans; deterministic runtime planner | Deferred by design (Phase F; M21 defers recomputation) — not on the v1 critical path until Phase F |
| 8. SoA layout | Nothing; AoS emitted directly | Type-level re-layout + access rewriting, exclusions for `ref`-element args (which lower to `&arr[i]` today — audit 5 F10) | **Medium-high mechanical**, last (Phase G) |

**Order:** the dependency chain in `memory.md:423-433` is correct as written. Nothing in layers 2-8 can start before 0-1; layer 3 additionally cannot start before the monomorphization decision.

---

## 3. Cross-cutting topics

**Iterative / recursion-limit-100 invariant.** All new analyses (CFG build, dataflow, ownership, escape, extent, release insertion) must be worklist-based; this is natural for dataflow and consistent with the existing discipline (`memory.md:594` already tracks it). Two specific hazards: (a) `copy.deepcopy`-based instantiation (`generics.py:176`) is recursion-depth-sensitive — the new monomorphizer must clone iteratively; (b) the invariant's test only covers 10 levels, so extend `test_iterative_traversal.py` with fixtures exercising each new pass at limit 100. Deep-nesting `RecursionError` in parser/type-checker/codegen remains a separate known defect, not a memory-plan blocker.

**Monomorphization.** `memory.md:445-446` ("computed after monomorphization") and layer 3's row assume an instantiation step the compiler does not have — Zig `comptime` does it, invisibly to Python. Either build Python-side instantiation for analysis only (keep `comptime` lowering), or fully monomorphize in Python and emit concrete Zig. The existing `generic_mapping` annotation is a usable hook; `GenericMonomorphizer` needs a real type substitutor (nested types) and iterative cloning.

**Whole program / file imports.** Substantially in place for A7 modules (combined-AST approach). Remaining gaps: `load_module` recursion, virtual stdlib modules outside the merge, and separate compilation listed as an open gap (`memory.md:599`). No new architecture needed — placement analyses run on the combined program.

**Phase C interim lowering (C′).** Feasible without layers 0-4: a lexical scope-exit pass emitting Zig `defer`-based `deinit()` for owning bindings, plus releases at reassignment and per-iteration block ends, over a single allocator. The `defer` lowering already exists (`zig.py:1272-1296`), so the emission mechanism is proven. Real prerequisites are user-surface ones: `List`/`Map`/`Table`/owning-`string` types don't exist, optionals need G5 decided and `?` tokenized (`edge-case-audit.md:128-129`), and the C↔track-8 circular dependency is only nominally split by C′ (`docs/plan/README.md:348-350`). Migration scale: ~364 tests, 13+ examples, 10 public docs (audit 5 part 4).

---

## 4. Findings

**Blockers**

- **B1. Monomorphization is assumed but absent** (`memory.md:445-446` vs `zig.py:432-487`, `type_checker.py:1354-1362`). Layers 3-8's "after monomorphization" premise has no implementation path chosen. Decision required before layer 3 work starts.
- **B2. Phase C has unresolved frontend prerequisites.** Optionals (G5 undecided; `?` not tokenized), owning `string`, and collections don't exist; the C↔track-8 cycle is split only on paper (`README.md:348-350`). C′ cannot start until the G5 optionals decision lands and the tokenizer/parser accept `?T`.
- **B3. Layers 0-1 (v1 tracks 4-5) are unstarted and everything is gated on them.** Not a design flaw — the plan says so — but the critical path is: CFG+facts → ownership → escape → extents → placement, with no shortcut to the L19 "users don't care about memory" outcome before Phase D.

**Major**

- **M-A. Layer 1 is a rewrite, not an increment** (`safety.py:149-176,336-363,444-447`): name-keyed facts cannot carry identity-keyed ownership state.
- **M-B. `zig.py` needs a lowering split** before layer 5: plan-then-emit with release/reuse/rese ops registered through `BackendPlan`, instead of inline string emission. Also: approvals are keyed by `id(node)` while the preprocessor runs between safety and codegen and can replace nodes (`compile.py:389-404`, `ast_preprocessor.py:141-149`) — safe today only because folding never replaces approved node kinds (inference; latent).
- **M-C. Exclusivity (corpus 14, `both(x,x)`, `set2(arr[i],arr[j])`) needs a new fact domain** — place disjointness with index intervals. Nothing exists; both aliasing forms are accepted today (audit 5 p5, p10c, compile-only).
- **M-D. G4/M6 stored function values can hide call-graph cycles** (README G4), undermining layer 3's acyclicity premise and the stack-bytes qualification (`memory.md:437-440`). Decide G4 before relying on it.
- **M-E. Phase B defect list is the true entry point and is cheap**: double-`del`, `del` through `ref` param, block-`defer` misclassification, name-keyed join-blindness (`edge-case-audit.md:75-108`; audit 5 F12). Note these flip accepted programs to rejected — behavior changes that still deserve a ledger note under the approval rule, even though they enforce the existing fail-closed contract.

**Minor**

- `module_resolver.load_module` recurses per dependency (`module_resolver.py:189-193`) — iterative rewrite when touched.
- `for (arr) |val|` immutable Zig capture confirmed (`zig.py:920-940`) — M30's breaking change is real and touches examples.
- `GenericMonomorphizer`'s shallow substitution (`generics.py:246-251`) would silently mis-instantiate nested generic types if reused as-is.

---

## 5. Minimum viable first milestone

**Phase B slice 1** (recommendation): per-function typed CFG with storage identities, plus an identity-keyed dataflow fact engine (branch joins, loop reset, call invalidation via per-function effect summaries) replacing `safety.py`'s fact walk.

Exit evidence, all runnable today:
1. Uninitialized read after zero-iteration loop rejected (audit 1 EC1-C08) — currently accepted.
2. Branch-joined `del` tracking correct in both directions (audit 1 p08, p17) — currently one false accept, one false reject.
3. Valid second write through a scalar `ref` parameter accepted (audit 2 CF-25) — currently rejected.
4. Guarded control programs still compile; `./run_all_tests.sh` green.
5. New passes compile 10-level-nested programs under `sys.setrecursionlimit(100)` (extend `test/test_iterative_traversal.py`).

Everything in layers 2-8 consumes this milestone; it needs no language-change approvals; and it retires the largest cluster of current memory-safety defects. C′ (collections + `defer`-based releases) is the best *parallel* track for user-visible progress, but only after B2's prerequisites.

---

## 6. Decisions for the user

1. **Monomorphization strategy (B1):** (a) Python-side instantiation for analysis only, keep Zig `comptime` lowering; (b) full Python monomorphization with concrete Zig emission. **Recommend (a) first** — smaller blast radius, reversible; revisit (b) when layer 5 needs per-instance storage plans.
2. **First milestone:** Phase B slice 1 (above) versus C′-first for visible progress. **Recommend Phase B slice 1**, with C′ started in parallel once G5 optionals are decided and `?` is tokenized.
3. **G4/M6 function values:** forbid stored function values (option a) or add type-informed call-graph edges (option b). **Recommend (a) for v1** — it preserves the acyclic-call-graph premise cheaply; examples 022/037 migrate to callback arguments.
4. **Approve the Phase B defect rejections** (`del`-family and uninitialized-read fixes flip accepted programs to rejected). **Recommend approving** — they enforce the existing fail-closed contract, but record them in the ledger with before/after examples per the approval rule.
5. **Timing of the `zig.py` lowering split:** now (before layer 2) or at layer 5. **Recommend a minimal split now** — route release/rese operations through `BackendPlan` and stop adding inline emission — to avoid retrofitting layers 2-6 onto the monolith.
