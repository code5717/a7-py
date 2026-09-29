# Memory advice synthesis

Status: comparison of advice, 2026-09-15. It is not a decision. It informed
memory plan revision 1. Decisions go to the [ledger](../../decisions.md).

Inputs: reading notes A–H; advice from GLM, Fable and Grok, all given the same
[prompt](advice-prompt.md); the user-supplied
[Gemini comparison](gemini-comparison.md); and the
[functional memory fact check](functional-memory-fact-check.md).

This document uses the plan's terms: extent, `Table(T)`, `Id(T)` and position.
The advisors' own names appear in the disagreement table: home, frame and region
for extent; pool, store and `Store<T>` for tables; handle and `Handle<T>` for ids.

## Agreement

All three advisors agree on the following points.

1. **A large subset is achievable, not every program.** No compiler can free
   arbitrary pointer graphs statically at the moment they die. The workloads v1
   already targets fit: training steps, game-style worlds, request loops, owned
   tensors and structured tasks. Python-style object webs do not.
2. **The honest promise.** No tracing collector, no reference counts, no pauses.
   Every release, reset, move and reuse happens at a program point the compiler
   chose. Some deterministic runtime work remains: allocator calls to grow
   tables, bump and free-list operations, and id validity tests. Sizes stay
   dynamic.
3. **The cost is over-retention.** Releasing by extent can hold memory until the
   extent ends. Releasing at last use is an optimization, not the safety
   mechanism.
4. **The architecture is one stack, not competing candidates:**
   1. typed CFG with ownership-aware operations and storage identities (plan
      track 4), as a hard prerequisite;
   2. affine owners, closing today's double-free and alias bugs (gate G2
      option a);
   3. interprocedural escape analysis with bottom-up summaries;
   4. inferred extents: function call, loop iteration, task, training step,
      long-lived owner, process;
   5. typed tables with `usize`-based ids instead of stored references;
   6. in-place reuse where uniqueness is proven statically, as in Perceus but
      without counts;
   7. liveness-based buffer packing, as in XLA and TVM, especially for tensors;
   8. structure-of-arrays layout last. It is legal because A7 has no address-of
      operator. Native boundaries are exempt.

   Note (2026-09-16): on item 6, Perceus places reuse statically but tests
   uniqueness at run time. FP² checks a function definition statically. At call
   sites, the published static option is uniqueness typing, which duplicates
   functions; Koka uses runtime checks instead. See the
   [storage reuse study](reuse-languages.md).
5. **A7's existing rules make this feasible.** The recursion ban gives an acyclic
   call graph, so summaries need no fixpoint and stack depth is computable.
   Immutable bindings make per-argument effects precise. With no public `&` or
   `*`, every way to form an alias can be enumerated. Whole-program compilation
   removes conservative cross-module summaries. Generated release code must be
   iterative.
6. **Cycles use ids, not references.** One table owns the nodes; parent and
   neighbor links are indices. Cycles cost nothing because the table is released
   as a whole. `examples/025_linked_list.a7` and `examples/026_binary_tree.a7`
   already follow this pattern.
7. **When inference fails, reject.** The diagnostic names the allocation, the
   escape and a concrete rewrite. No collector fallback, no inserted counts, no
   silent promotion to a longer lifetime, no hidden copy.
8. **Data-dependent lifetimes are library policy.** Caches and interning use
   explicit tables with capacity, eviction or clearing.
9. **Views never escape and never survive growth.** Positions may survive growth;
   slices and tensor views may not.
10. **Tensors use session ownership** (Codex design T1). A session or step owns
    storage and tape. Views are local projections. Changing a saved value is
    rejected or reported before execution. Checkpoints copy out.
11. **Tasks move values.** A task's storage ends at join. Ids into a table that
    the receiving task does not own must not cross tasks.
12. **The brainstorm plan needs restructuring.** Stop scoring layers as rival
    candidates. State the IR prerequisite. Write falsifying programs before the
    mechanism survey, and hand-trace them early. Reference-count elision is not a
    candidate under L15. The saved research claim that the recursion ban prevents
    cyclic data is wrong.

## Disagreement

| Topic | GLM | Fable | Grok |
| --- | --- | --- | --- |
| Name for the extent | home | region internally; home only in diagnostics | frame |
| Name for grouped storage | pool | pool; user type `Store<T>` | store: arena or pool |
| Stale handle | Generation compare; elided by proof | Exactly one runtime check class, returning a typed result | Generation stored in the id; lookup returns an optional; never traps |
| `del` | Kept as explicit early release | Not needed in ordinary code | Optional early release |
| Closures | Non-escaping by default; escaping closures own captures | None in v1 | Callbacks may borrow for the call; stored closures own captures; prefer no stored function values |
| User-visible surface | No new keywords; `--memory-report` | `List`, `Map`, `Store<T>`, `Handle<T>`, owning `string`; no hints | Values, lists and tables, ids; optional frame hint later |
| Plan sessions | Keep order; add lowering, diagnostics, concurrency and report sessions | Merge sessions 1 and 2; spikes at session 3 | Merge sessions 1 and 2; hand-trace in session 2 |
| Place of regions in G2 | On top of the affine floor | Ownership for precision, regions as lowering | Regions are the middle of the design, not optional |

## Facts reported from the tree

The advisors and reading notes reported these facts. Items marked compile-only
were compiled but never run.

- `ref T` lowers to a nullable Zig pointer. `ref` arguments conflate heap owners
  and borrowed stack slots. One global page allocator backs `new` and `del`.
- Codegen and the standard library have no arena, pool, list or map. `string` is
  a non-owning byte slice. No closure support was found.
- The safety pass joins facts by snapshot and restore without a CFG, and keys
  moves by name.
- A struct field whose type is its own struct is rejected (compile-only).
- Copying a `ref` into a field and deleting the original writes freed memory
  (compile-only).
- Returning a struct that holds a `ref` to a local leaves a dangling reference
  (compile-only).
- `examples/025_linked_list.a7` uses `isize` indices with `-1`, against the
  `usize` index rule.
- Plan gate G2 keeps affine `del`, while the brainstorm direction removes `del`.
  The two were unreconciled (Fable F11).

## Decisions to put to the user

Each needs before and after examples and compatibility impact under the approval
rule. The right column shows where each question now lives in the
[memory plan](../../memory.md).

| # | Decision | Now in |
| --- | --- | --- |
| 1 | **Promise:** accept the reframed guarantee above instead of zero runtime memory work | Contract items 1 and 7 |
| 2 | **Failure policy:** reject with rewrite diagnostics; no collector, counts, silent promotion or hidden copies | Contract item 8 |
| 3 | **Stale ids:** lookup returns an optional result; checks are elided when proven unnecessary | Gate M5 |
| 4 | **Stored references:** replace stored `ref` fields with ids into owning tables. This is a breaking change | Gate M4 |
| 5 | **`del`:** remove from ordinary code, or keep as optional early release | Gate M3 |
| 6 | **Closures and stored function values:** exclude from v1, or allow with owned captures | Gate M6; v1 gate G4 |
| 7 | **User-visible surface:** which collection and id types exist, and whether any hint or report is visible | Section 2; gate M8 |
| 8 | **Vocabulary:** home or frame; pool or store | Gate M9 |
| 9 | **Plan order:** IR and proof repair, then affine owners, inferred extents and ids, then reuse and packing, then layout | Phases A–G |
| 10 | **Brainstorm restructure:** merge contract and corpus sessions, and run falsifying programs first | [Brainstorm record](../../memory-brainstorm.md#changes-from-the-first-brainstorm-plan) |

## Where the memory plan departed from the advice

- **Escaping values are copied out, not rejected.** Point 7 said to reject and
  forbade hidden copies. Revision 2 copies a value out on the escaping path, so
  placement never fails visibly. Rejections form a closed list (contract item 8).
- **`del` is removed** from ordinary code (gate M3), as Fable proposed.
- **Function values** that capture nothing are allowed anywhere. Capturing values
  are allowed only as non-escaping arguments (gate M6).
- **Vocabulary:** diagnostics use plain terms; "extent" and "store" appear only in
  the memory report and compiler docs (gate M9). The user-visible types are
  `Table(T)` and `Id(T)` (section 2, gates M1 and M5).

## Falsifying programs to write first

Combined from the three advisors and ordered by how quickly each can break a
design. The right column gives the matching program in the plan's
[falsifying corpus](../../memory.md#falsifying-corpus).

| # | Program | Corpus |
| --- | --- | --- |
| 1 | Request loop with per-request temporaries, a connection table and a capacity-limited cache | 1 |
| 2 | List append while a slice of it is live (reject) and while only a position is live (accept) | 2, 3 |
| 3 | Tree with parent ids, node removal and iteration | 4 |
| 4 | Entity spawn and despawn, then use of an old id on the next tick | 5 |
| 5 | Merge keeping a subset of values chosen at run time | 6 |
| 6 | Returning a newly built list, and returning a slice of a local (reject) | 7 |
| 7 | Training step: `y = x * x`, change `x`, then backward (reject or report) | 8 |
| 8 | Training step with in-place weight update after tape release | 9 |
| 9 | Worker storing channel data into a shared registry; sending an id without its table (reject) | 10 |
| 10 | Closure stored in a struct capturing a local buffer | 11 |
| 11 | Native kernel retaining a slice past return; overlapping buffers passed to a matrix kernel | 12 |
| 12 | Global intern table | 13 |

Secondary: a checkpoint round trip, a failed append that leaves the original list
usable, and resetting a deep table without native recursion. Only the last has a
corpus counterpart (program 15, deep tree released iteratively).
