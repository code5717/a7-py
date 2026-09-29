# Storage reuse in Carp, Koka, Lean 4 and Roc

Status: authored summary, 2026-09-16. It is not a decision. Decisions go to the
[ledger](../../decisions.md).

The user asked for a study of these four languages on 2026-09-16. Four research
subagents wrote reports, and a fifth pass re-checked two Carp findings. The
reports are preserved verbatim in [`languages/`](languages/).

| Language | Report |
| --- | --- |
| Carp | [carp.md](languages/carp.md), re-checked in [carp-verify.md](languages/carp-verify.md) |
| Koka | [koka.md](languages/koka.md) |
| Lean 4 | [lean4.md](languages/lean4.md) |
| Roc | [roc.md](languages/roc.md) |

The reports mix direct reads of papers and source files with DeepWiki answers (an
AI summary of a repository), search-result snippets, an HTML render of one paper
and a fetch tool that can paraphrase. Each report labels which is which. Paper
section numbers below are the reports' citations and were not re-checked;
lean4.md read Counting Immutable Beans through an HTML render of a later arXiv
revision. This summary went through two audit rounds against the reports.

## Why this study was run

Item 6 of the advisors' architecture in the [synthesis](synthesis.md) is "in-place
reuse where uniqueness is proven statically, as in Perceus but without counts."
The [fact check](functional-memory-fact-check.md) had already noted, without a
source, that Perceus checks uniqueness at run time. This study checks that claim
and what a count-free version would need.

## What Perceus decides statically

Perceus is a static ownership discipline with one dynamic ingredient (koka.md,
summary).

| Part | When decided | Source |
| --- | --- | --- |
| Ownership and borrowing | Compile time | Perceus §3.2, §3.4 |
| Where `dup` and `drop` go | Compile time | Perceus §3.4 |
| Pairing a destructed constructor with a same-size allocation | Compile time | Perceus §2.4 |
| Assigning only the fields that change | Compile time | Perceus §2.5 |
| Whether the paired cell may be taken | Run time: `is-unique(x)` | Perceus §2.4 |

The run-time test appears cheap. FP² §6 reports "That `std-reuse` is only about
1% slower shows that the dynamic reuse check has negligible impact on
performance" (koka.md §7.3). The report does not say which variant is the
baseline. If the authors' reading holds, deleting the test saves little by
itself. The other costs of counting are atomic updates, which were measured, and
cycle leaks and per-allocation header words, which were not.

So "as in Perceus but without counts" is accurate for the four static parts. It
is wrong only if read as saying Perceus already proves uniqueness statically.

## FP² and its limits

FP² (Lorenzen, Leijen and Swierstra, ICFP 2023) defines a calculus, FIP, that
proves a function can run in place, using linear "reuse credits". The paper
states (FP² §1.5, quoted in koka.md §6):

> "FIP is exactly that subset of λ^fip which requires no dynamic reference
> counting or memory management at runtime. As a result, in the Perceus setting
> FIP functions can interact safely with any other function, executing in-place
> when possible and copying when necessary."

The second sentence matters: FP² presents FIP running inside a counted runtime.
Its limits, from koka.md §9 unless noted:

1. **Call sites are not covered.** The check covers a function's definition.
   Whether a given call may update in place depends on sharing at the call site,
   as in `append(xs, reverse(xs))` (§1.4). FP² names two ways out: uniqueness
   typing as in Clean, which is static but leads to duplicated functions, or
   runtime checks. Koka uses runtime checks, including for `fip` functions
   (§1.4.2).
2. **FIP is not affine.** The calculus "is not affine: we cannot discard owned
   variables as that implies freeing a potentially heap allocated value" (§2.2).
   The weaker `fbip` variant allows deallocation. A7's plan uses affine owners,
   so the nearer match is `fbip`, not `fip`.
3. **No general lambdas.** Only top-level functions may be passed as arguments,
   "effectively making it second-order" (§1.3). This bears on open gate M6.
4. Borrowed parameters may only be inspected, not consumed or returned.
5. Zero allocation needs unboxed tuples and field-less constructors as tagged
   atoms.
6. Reuse credits are size-exact and cannot be split or merged (§1.1). Koka's
   authors pad constructors so sizes match (§4).
7. `fip` functions may call only `fip` functions. This comes from Koka's
   documentation and source as reported by DeepWiki, not from the paper.

koka.md concludes, labeled as inference, that A7's model is "FIP without the
dynamic fallback". The evidence supports a narrower statement: FP²'s `fbip`
rules are the nearest published check for function definitions. For call sites,
the published static option is uniqueness typing, with its cost in duplicated
functions. Neither FP² nor shipped Koka checks call sites statically. A7 would
have to choose and build that part.

## What the count buys

The count lets a compiler attempt reuse without proving uniqueness, because a
failed test falls back to allocation.

- **Lean 4.** The compiler inserts `reset`/`reuse` where static conditions hold:
  the value is dead, not borrowed, and layout-compatible. It never proves
  uniqueness; the runtime test `lean_is_exclusive` decides (lean4.md §3). The
  report found no static elision of that test. Open RFC #7374 asks to skip it
  where it is provably pointless; the report infers from this that no elision
  exists. lean4.md labels the "fallback" framing as inference.
- **Koka.** The dynamic check "is also what enables FBIP to use a single function
  that can be used for both unique or shared objects (since the uniqueness
  property is *not* part of the type)" (Perceus §5).
- **Roc.** A born-unique analysis proves some returns unique statically, and
  `refcount == 1` decides at run time otherwise (roc.md §2). The mechanism that
  lets a builtin skip the runtime test is reported only by DeepWiki.

Where A7 cannot prove uniqueness, it must copy or reject. An inserted copy runs
every time, including when the value was in fact unique at run time.

## What A7 gives up

The facts are sourced; the consequences for A7 are projections.

1. **One function for unique and shared callers.** Static uniqueness "usually
   also requires writing multiple versions of a function for each case"
   (Perceus §5).
2. **Call-site uniqueness without duplicated functions,** as in FP² limit 1.
3. **Adaptive copying.** With counts, a shared tree copies only its shared spine
   and still updates unshared parts in place (Perceus §2.5).
4. **Performance on shared data.** Koka's optimizations are "less effective" on
   sharing-heavy benchmarks (Perceus §4). Without counts, A7 decides at compile
   time and cannot adapt.
5. **Size-exactness** becomes a compile-time obligation, as in FP² limit 6.

One constraint holds with or without counts. Both published reuse algorithms
"are quite fragile with respect to small program transformations" such as
inlining (Frame-Limited Reuse §3). koka.md recommends the drop-guided
formulation, which runs after ownership analysis. For A7, a missed pairing
becomes an inserted copy or a rejection.

## What A7 avoids by having no counts

- **Atomic counts.** Making all counts atomic slowed Koka by 5% (`rbtree`) up to
  59% (`nqueens`) (Perceus §4). Lean's ablation has an all-atomic geomean of 1.89
  against a base column geomean of 1.24, read from an HTML render. lean4.md
  divides these to get about 1.52×; koka.md reads the same column against 1.00.
  The ratio is derived, not printed.
- **Cycles.** Koka has no cycle collector; a cycle built through a mutable `ref`
  leaks unless the programmer clears a cell (Perceus §2.7.4). Lean's verifiable
  fragment cannot build cycles; a cycle formed outside it leaks (lean4.md §5).
  Roc has "no way to express reference cycles" (roc.md §5).
- **A Lean trap.** `lean_is_exclusive` requires single-threaded and `rc == 1`.
  lean4.md infers that an object marked multi-threaded can never be reused in
  place, even when it is in fact unique.

## Roc's reuse today

Roc's earlier Rust compiler had a general reuse pass based on Frame-Limited Reuse,
plus Perceus drop specialization. In the current Zig compiler's pass list
(`src/lir/mod.zig`), the report found no general `reset`/`reuse` token pass. What
it found is narrow: `box_reuse.zig` for straight-line box updates, and
`arc_dismantle.zig` for taking fields out of an aggregate that is about to die
(roc.md §6). Treat Roc as a language that had general reuse and now has special
cases.

## Carp

- **No runtime counts.** Carp decides frees statically. The exception is closures:
  the `Lambda` struct carries a `delete` function pointer (carp.md §5). The code
  that calls it at run time is reported only by DeepWiki, and carp-verify.md did
  not find it in `src/Emit.hs`.
- **Frees at end of lexical scope, not last use.** Confirmed from `src/Memory.hs`:
  deleters attach to the `let` or `defn` form after its whole body is visited
  (carp-verify.md).
- **No compiler-inserted reuse was found** in `src/Memory.hs` or `src/Emit.hs`.
  carp-verify.md adds: "Absence outside those two files is not established by
  this task and should not be asserted." It describes `Memory.hs` as about 500
  lines, while carp.md reports GitHub's count as 833, so the fetch may have been
  incomplete.
- **Mutation in place is allowed.** Carp's author says "you can mutate anywhere"
  (carp.md, claims table). Its documented in-place array functions include
  `endo-map` and `filter`.
- **Reference kinds.** Asked in 2017 whether Carp separates mutable and immutable
  references, its author answered "not at the moment", adding "it's probably
  coming" (carp.md §2). carp.md infers that Carp's safety is about liveness
  rather than exclusivity, and that this is why Carp has no threading plan.
- **Visible memory surface.** Users write `&`, `@` and `Box`, and choose between
  `endo-map` and `copy-map`. The `copy-` prefix is there "to remind you of the
  fact that the function is allocating memory" (carp.md §6).

Carp is evidence that frees can be placed statically with no counts. It is not
evidence for compiler-inserted reuse.

## What users see

- **Koka.** Perceus §2.6 says "a programmer can rely on this optimization
  happening", by pairing match patterns with same-size constructors in each
  branch. Before FP², nothing checked this; FP² adds `fip` and `fbip` so the
  compiler verifies it (koka.md §4). DeepWiki reports that `fip` functions still
  emit a uniqueness test and copy when it fails.
- **Lean 4.** Library code must sometimes be rewritten or inlined so constructor
  applications are guarded by a `reuse` (Beans §6).
- **Roc.** The tutorial never mentions memory. The API docs expose
  `List.with_capacity`, `List.reserve` and `List.release_excess_capacity`, and
  say `List.keep_if` "will not allocate any new memory on the heap" on a unique
  list (roc.md §3). Roc's FAQ says linear or uniqueness types "would move things
  that are currently behind-the-scenes performance optimizations into the type
  system" (roc.md §9; the report's fetch tool did not reproduce the full FAQ
  section).
- **Carp.** Memory appears throughout ordinary code, as above.

koka.md infers that Koka's reuse is best-effort and silent by default, and
checked only under `fip` or `fbip`. A7 wants reuse that is both guaranteed and
invisible, and none of the four languages shows that combination. The options
are an annotation like `fbip`, a diagnostic mode, or accepting compiler-inserted
copies.

## Corrections to existing documents

| Where | Existing text | Correction |
| --- | --- | --- |
| Fact check, item 2 | Perceus authors "Reinking, Xie, Leijen, Swierstra" | Reinking, Xie, de Moura and Leijen (koka.md, lean4.md). Lean 4 does not use Perceus |
| Fact check, item 4 | "Up to 90% of count operations" | Not found in the Perceus, Frame-Limited Reuse, FP², Lorenzen thesis or Beans papers. Lean 4 and Roc infer borrowed parameters. Koka had no automatic borrow inference as of the 2022 paper |
| Fact check, item 5 | "Identical or smaller size" | Identical size only |
| Fact check, item 6 | A zero count frees the entire subgraph | Already rated wrong. Confirmed: children are dropped and survive if shared (koka.md, claim C5) |
| Fact check, item 13 | Timing of reclamation | Also, reuse analysis cannot preserve Perceus's garbage-free property (Frame-Limited Reuse §4) |
| Fact check, item 15 | "Broadly correct" | Correct, with a qualifier on reference kinds; see the Carp section |
| Gemini annotations | Uniqueness "decided by a reference count at run time, sometimes removed by static analysis" | Lean 4: no removal found. Koka: not removed in the shipped compiler. Roc: some values proved unique statically |
| Gemini annotations | Carp "closest of the five to a statically resolved model" | Unsupported: MLKit was not studied |
| Synthesis, item 6 | "as in Perceus but without counts" | Accurate for Perceus's static parts. Neither FP² nor shipped Koka checks call-site uniqueness statically |

## Not established

- **MLKit** was not studied. The fact check's unchecked item 8 says MLKit adds
  run-time region resets and later versions add a tracing collector. carp.md
  infers the opposite, that its region inference is fully static. Neither claim
  was checked.
- **Carp performance numbers:** none were found.
- **Carp reuse:** absence over two files, possibly from an incomplete fetch.
- **Lean ablation ratios** are derived, and the two reports disagree.
