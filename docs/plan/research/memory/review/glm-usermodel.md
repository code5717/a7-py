> **Source:** OpenCode `zai-coding-plan/glm-5.3` review of memory plan revision 2; focus: user model, Python-simple surface and breaking changes. Prompt in [review-prompt.md](../review-prompt.md).  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

Now let me look at the examples and SPEC to gauge migration cost and current surface usage.
# Advisory review: user model (memory.md §2, §3) vs L17/L19

## Verified facts

**Ledger anchors**
- L17: "i want to make this super simple like python and how gc languages work"; "the compiler should group some stuff together as arenas and pools" (decisions.md:52). L19: "basically anyone using this programming language shouldnt care about memory in general" (decisions.md:54). L21: no Zig mental load (decisions.md:56). L22: keep current syntax for now (decisions.md:57).
- Approval rule: before/after examples required for any change (decisions.md:22-30).

**Plan surface (§2, memory.md:216-257)**
- Concepts: values; `List(T)`, `Map(K,V)`, owning `string`; optionals; `ref` params (non-storable); `usize` positions "valid while the element stays in place" (memory.md:228-230); generation-tagged `Id(T)` over `Table(T)` (memory.md:231-233); move-only resources (memory.md:234); "bindings copy, places change in place" (memory.md:234-235).
- §2's own example is internally consistent with M5 (uses `Table(Node)` + `?Id(Node)`, not `List`+`usize` — the revision-1 defect audit 2 called X/EC2-05 is fixed in rev 2) (memory.md:237-258).

**Breaking-change table (§3, memory.md:260-417)**
- Every "Before" block was compile-checked 2026-09-16, none executed (memory.md:284-287). I ran nothing; all compiler behavior below is cited, not reproduced.
- Each removal targets a documented current defect: `ref` returns dangle (audit-1 p23), returned slices of locals dangle (q13), double `del` accepted (p06), `del` through `ref` frees stack slots (audit-3 p13), aliased `ref` args accepted (p5), uninitialized reads accepted (EC1-C08) — edge-case-audit.md:76-98.
- Migration cost, documented: 12 modules (~330 lines), ~364 of 2,527 tests, 13+ examples, 10 doc files (edge-case-audit.md:137-141). Cross-check (my count, compile-free greps only): example use of `new`/`del`/`nil` is concentrated in 3 files (011, 019, 037); `ref` appears in 8 example files but only as *parameters*, which survive. ~76 test functions match by name; keyword matches span ~15+ test files. Consistent with audit 5.

**Audit 2 (postdates rev 2; rev 3 pending, memory.md:7-10)**
- L19 metric: diagnostics a Python programmer meets in ordinary code: EC2-02/03/18/33/40/43/44/46/54/56/57; behavior surprises vs Python: EC2-05/06/08 (positions), EC2-14 (element copies), EC2-19 (missing keys), EC2-20 (empty `len-1`); perf-only: EC2-27/71/72/73 (audit-2:1157-1169).
- Current compiler divergences that shape §3: views observe owner writes (CF-13), `?` not tokenized (CF-29), string `==` emits non-compiling Zig (CF-09), `arr = [arr[1], arr[0]]` miscompiles to `2 2` in D/RF (CF-20).

## Assessment (inference)

### Is the surface Python-simple?

**Declaration-level: yes. Zig-mental-load-free (L21): yes. Python-equivalent: no, and the plan mostly doesn't claim it — but §2 undersells the gaps.**

What genuinely meets L17: no allocate/free/arena/lifetime vocabulary (contract item 9, memory.md:91-94), copy semantics match Python's scalar/string intuition, nine-class closed rejection list phrased as behavior, and placement never fails visibly (copies out on escape, memory.md:88-90). The advisors' consensus backs achievability for the targeted workloads (synthesis.md:19-31).

Where L19 ("users should not care about memory") leaks, ranked by how ordinary the program is:

1. **Container choice is a lifetime decision.** Users must choose `List`+`usize` vs `Table(T)`+`Id(T)` vs `Map` (gate M1, memory.md:467). The choice hinges on "will records be removed? do links need to survive removal?" — a memory/data-lifetime question a Python user never asks (they use objects + dicts). Three overlapping container concepts is the single largest L19 violation in §2.
2. **Silent behavior divergence, no diagnostic.** `row := grid[0]; row.append(5)` changes the copy (memory.md:232-233). Python aliases. Ported mental model → wrong results, no error (EC2-14, "behav"). Same class at top level: `snapshot := tree` (memory.md:254-256) deep-copies. This is the most dangerous L19 hit because it is *silent*.
3. **Iteration + mutation.** Append during `for v in xs` must be rewritten (EC2-03, G-05); Python permits list-append-during-iteration. Note this is *undefined in rev 2* — snapshot vs view is undecided (Q-C3).
4. **Move-only resources.** `g := f` consumes `f` (memory.md:234, 399-404). No Python analog; narrow and teachable, but a named exception users must learn.
5. **Tape/dependency rules (rejection classes 6-7).** Training code must use `.item()`/`detach` and order `backward` before mutation (memory.md:179-194). PyTorch users already know this shape, so the surprise is bounded — but it is memory-awareness in AI code, and it is the AI acceptance path (L10).

Net: the surface is **value-simple, not Python-simple**. It satisfies L21 and L20 (much simpler than Zig/C++), and satisfies L19 for straight-line data plumbing. It fails L19-as-verbatim ("shouldn't care at all") at container selection, nested-aliasing intuition, iteration mutation, closures, and tape discipline. The plan has the right honesty instruments (closed rejection list, L19 metric in Phase A); §2's prose should state the divergences explicitly rather than only "collections and strings behave as values."

### Concept-by-concept

| Concept | Verdict | Notes |
| --- | --- | --- |
| `Id(T)` / `Table(T)` | Sound, keep | Fixes B3 (plain usize can't carry generation). Open: cross-store ids and outliving stores (G-03/Q-C2), generation exhaustion (G-02/Q-C11 rec: retire slot), both pending rev 3. |
| `List` + usize positions | Underspecified | "Valid while the element stays in place" (memory.md:228-230) hides EC2-05: `List.remove` shifts positions and generations cannot detect shifting. Audit 2's fix (List has no order-shifting removal; removal lives in `Table`) is not yet in the plan. |
| `Map` | Unspecified | Missing-key read/write/`ref` semantics undefined (Q-C9); iteration mutation undefined (EC2-18). |
| Owning `string` | Right call | Fable called it the largest ergonomic lever; depends on the materialization rule (G-09) — without it, `first_word` is a memory-aware rewrite; with it, ordinary text code is L19-clean. Encoding must be decided (G-19: SPEC says ASCII, compiler accepts UTF-8, CF-15). String `==` must land in Phase C (CF-09). |
| Optionals | Keep | Replaces `nil` coherently. `?` is not tokenized today (CF-29), so this is new surface, tied to G5. |
| Move-only resources | Keep, small | Named exception; M7's fallible `close` + unclosed-warning is good. |
| "Bindings copy, places change in place" | Load-bearing, but the key trade | This rule buys in-place performance without C++ machinery, at the cost of a two-rule mental model and the EC2-14 silent divergence. Fable's alternative (borrow bindings) would match nested-container Python better but adds a third binding kind; audit 2 recommends copy (Q-C4a). This is precisely a user decision. |

### Realistic programs needing a memory-aware rewrite

1. **Graphs with parent/back pointers and removal** → must become `Table`+`Id` with optional lookups (memory.md:246-257; corpus 4-5). Largest class; Python uses objects.
2. **Build-while-iterating** → second list or index loop (EC2-03; corpus 2's sibling). Decided only after Q-C3.
3. **Comparators / event handlers capturing state** → stored function values capturing locals rejected (class 4; EC2-56); rewrite to explicit fields.
4. **`swap(a[i], a[j])` with runtime indices** → library `arr.swap(i,j)` (corpus 14; Q-C8).
5. **Loss accumulation across training steps; mutation before `backward`** → `.item()`/`detach`/reordering (classes 6-7; corpus 8, 17).
6. **`for v in pts { v.x = 9 }`** → `for i, v` + `pts[i].x` (M30). Cheap: current form is already rejected by Zig (audit-1 p20), so this fixes a latent defect.
7. **Tokenizers returning views** → *no* rewrite **if** G-09 materialization is adopted (audit-2 EC2-26); reject only declared view-typed escapes. Strong argument for approving G-09.
8. **Long-lived caches** → explicit capacity/eviction API (synthesis point 8). This is "memory management in Python clothing" — acceptable, but call it what it is; and contract item 5 as written does not guarantee corpus 1's flat memory (G-15).

Not rewrites but silent divergences to document: nested-element copies (EC2-14), position ABA after `clear`/re-append (EC2-08), deep `snapshot := tree`.

### Breaking-change table and migration cost

**Judgment: necessary, evidence-based, honestly costed at repo scale — but incomplete per audit 2, and it understates user-code semantic cost of one row.**

Strengths:
- Every row deletes a documented unsafety (see verified facts); the migration buys correctness, not aesthetics.
- Phasing is right: C′ interim lowering, C″ diagnostics that *suggest rewrites* for `new`/`del`/`nil`/`ref` fields (memory.md:538-540).
- In-repo user-code cost is small: `new`/`del`/`nil` in 3 of 43 examples; no example stores `ref` fields (the `ref` uses are parameters, which survive). The "12 modules / ~364 tests / 13+ examples" figure is dominated by compiler machinery and test fixtures, not user programs.

Gaps:
1. **Missing rows** (audit 2, not yet applied): owner-writes-while-view-live (`s := arr[0..2]; arr[0] = 7` runs today, CF-13 → reject under G-07/Q-C6); and, if Q-C3(b) is chosen, the snapshot→view behavior change for `for` over fixed arrays (G-07b, q08/q24). B9's "table rebuilt from probes" is incomplete as of rev 2 — known, scheduled for rev 3.
2. **`ref` fields → `Id(T)`/usize row is the only semantically expensive one** — it forces a data-structure redesign (Table+Id), not a syntax swap. The table's impact column counts modules/tests but doesn't flag which rows are mechanical (`new`→value) vs redesign (stored refs). For migration planning, split those.
3. The row on `for v in` loop bindings is correctly scoped as fixing an A7-accepts/Zig-rejects inconsistency.
4. Minor: the table should cross-reference defect IDs (p23, q13, CF-13…) per row so approval discussions map to evidence; several do, some don't.

## Findings by severity

**Blocker** — none in §2/§3 as written that falsifies the plan; the two below are blockers *for seeking approval of §3 as-is*:
- (Approval-blocking) §3 table missing the G-07/G-07b rows; approving the table now would approve an incomplete compatibility story. Fix in rev 3 before the user signs off.

**Major**
1. Three-way container choice (List/Table/Map) is itself memory-awareness — the biggest L19 gap in §2 (see assessment #1).
2. EC2-14 silent wrong-result divergence from Python aliasing with no diagnostic; needs Q-C4 decided and the divergence documented (possibly an M8-family warning when a binding copied from a collection-of-owning-values is later mutated).
3. Contract item 5 vs corpus 1: evicted entries may be held to extent end (G-15) — user-visible unbounded growth on the flagship request-loop workload; adopt the release-at-removal rule in rev 3.
4. `List` mutation APIs and position semantics after removal undefined (EC2-05/G-01); "stays in place" phrasing is insufficient.
5. `Id` cross-store use, ids outliving stores, generation saturation undefined (G-02/G-03).
6. `Map` missing-key and iteration semantics undefined (Q-C9, EC2-18).
7. Iteration binding semantics (snapshot vs read view) undefined in rev 2 (G-05/Q-C3) — blocks the EC2-03 corpus decision.

**Minor**
1. Owning-`string` encoding undecided (G-19/Q-C13); SPEC/implementation already disagree (CF-15).
2. §2 example uses `none`, `Table(Node){}`, `?Id(Node)` — none exist today (`?` not tokenized, CF-29); correctly labeled proposed, but note the model cannot be compile-tested until G5 + Phase C.
3. §3 impact column conflates compiler-machinery cost with user-code cost; per-row user-cost labels would make approval easier.
4. Tape-rule rejections (classes 6-7) deserve an explicit "this is memory-awareness in AI code; accepted" statement rather than silence, since L10 makes AI the acceptance path.

## Decisions for the user (each needs before/after examples per the approval rule)

1. **Element binding semantics (Q-C4).** `row := grid[0]` copies (audit 2 rec) vs borrows (Fable rec). **Recommend: copy** — one binding rule, matches scalar intuition; document the nested-container divergence loudly.
2. **List vs Table split (Q-C1).** Remove order-shifting removal from `List`; removal lives in `Table(T)`. **Recommend: yes** — otherwise positions silently name the wrong element (EC2-05) and generations can't help.
3. **View materialization (G-09/Q-C7).** Views returned/assigned into owning types (`string`, `List`) materialize; only declared view-typed escapes reject. **Recommend: yes** — keeps text processing L19-clean with zero user awareness.
4. **Read-only views (G-07/Q-C5/Q-C6).** Views read-only; owner writes during a live view reject; add the missing §3 row. **Recommend: yes** — today's behavior (CF-13, prints 7) is observably non-value.
5. **Iteration binding (Q-C3).** Read view with structural changes rejected (audit 2 rec) vs snapshot. **Recommend: read view**, but note it adds the G-07b breaking row and changes behavior of currently accepted fixed-array programs (q08/q24).
6. **Id provenance (Q-C2).** Store identity in ids unless provenance proven (erased when proven). **Recommend: yes** (audit 2 rec) — cheaper than rejecting unproven cross-store use.
7. **Contract item 5 amendment (G-15/Q-C15).** Release or recycle element storage at removal. **Recommend: yes** — otherwise corpus 1 fails its own flatness expectation.
8. **Accept the nine-class rejection list as the explicit L19 bargain.** This is the decision that defines "Python-simple" honestly: no memory vocabulary, but ~10 diagnostic families and ~4 silent divergences vs Python remain. **Recommend: accept, and add the divergence list to §2 prose** so L17/L19 claims are testable against the Phase A L19 metric rather than aspirational.
