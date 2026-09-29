# Fact check: non-GC memory in functional languages

The user supplied two explanatory texts on 2026-09-15 for checking. This file
records the corrections, their relevance to A7, and the original texts.

The corrections came from the controlling session's knowledge of the published
work. On 2026-09-16, items 2, 4, 5, 6, 13 and 15 were checked against sources;
see the [storage reuse study](reuse-languages.md). The other items are unchecked.

## Verdict

Both texts describe the four families accurately at a high level: precise
reference counting with reuse, region inference, substructural types, and escape
analysis. Several specific claims are overstated or wrong, and some matter for A7.

## Corrections

| # | Claim | Assessment |
| --- | --- | --- |
| 1 | Pure immutability guarantees an acyclic heap, so cycles cannot form | **Overstated.** Holds for strict, pure data without mutable cells. Lazy languages build cycles by knot-tying (`xs = 1 : xs`). Recursive closures can be cyclic. Koka has mutable references, and its Perceus paper acknowledges that cycles through them leak. A7 has mutable data, so this invariant does not apply to A7. |
| 2 | Koka and Lean 4 both use Perceus | **Wrong.** Perceus is Koka's algorithm (Reinking, Xie, de Moura and Leijen, PLDI 2021). Lean 4 uses the reference counting and reuse scheme of "Counting Immutable Beans" (Ullrich and de Moura, IFL 2019), which Perceus builds on. Checked 2026-09-16. |
| 3 | Pseudo-code for the shared branch: `alloc_cons(apply(f, cell->head), map(f, cell->tail)); dec_ref(cell)` | **Unsound as written.** When the cell is shared, its fields must be duplicated (count incremented) before the cell is released. Otherwise freeing the cell would release the head and tail still in use. The closure `f` is also used twice and needs a duplicate. |
| 4 | Borrow inference eliminates up to 90% of count operations | **Not found.** No such figure appears in the Perceus, Frame-Limited Reuse, FP², Lorenzen thesis or Counting Immutable Beans papers. Lean 4 and Roc infer borrowed parameters. Koka had no automatic borrow inference as of the 2022 Frame-Limited Reuse paper. Checked 2026-09-16. |
| 5 | Reuse pairs a freed node with an allocation of identical or smaller size | **Wrong.** Pairing is on identical size only (Perceus §2.4). FP²'s reuse credits cannot be split or merged, so Koka's authors pad constructors to make sizes match. Checked 2026-09-16. |
| 6 | When a count reaches zero, the entire subgraph rooted at the object is dead and freed | **Wrong.** Zero means that object is dead. Its children are decremented and freed only if their counts also reach zero; other references may keep them alive. Recursive release can also take time proportional to the structure. The child-release behavior was confirmed 2026-09-16 (Perceus §2.3); the time claim is unchecked. |
| 7 | Reference counting requires a background cycle collector | **Overstated.** CPython adds one. Swift and Objective-C instead rely on weak and unowned references and accept leaks from strong cycles. |
| 8 | Region deallocation is a single pointer bump, with precise lifetimes and zero per-allocation overhead | **Overstated.** Freeing a region is cheap, but allocation still bumps into region pages, and storage-mode analysis adds run-time region resets. Region inference is conservative: lifetimes can be much longer than necessary, and some programs need rewriting to avoid space leaks. Later MLKit versions combine regions with a tracing collector. |
| 9 | Multiplicity analysis distinguishes zero, one or infinitely many values | **Imprecise.** MLKit's multiplicity inference separates finite regions, whose size is known and which can live on the stack, from infinite regions that grow by pages. **Verify** the exact categories. |
| 10 | Uniqueness types in Clean and Austral | **Partly wrong.** Clean uses uniqueness typing. Austral uses linear types with borrowing. The two are related but not the same discipline. |
| 11 | Linear types place a free exactly where a value is consumed | **Simplified.** Linearity identifies the consuming operation. Freeing happens where a destructor or deconstruction consumes the value. Conditional moves can still need drop flags or rejection. |
| 12 | Tail-call stack recycling avoids heap garbage | **Conflated.** Tail calls reuse the stack frame. They do not stop the loop body from allocating heap data such as accumulated lists. |
| 13 | Perceus reclaims memory "immediately upon last dereference" | **Wrong wording.** Drops occur after the last use of a reference, not at the last dereference. Also, reuse analysis cannot preserve Perceus's garbage-free property, because it keeps cells alive until reuse (Frame-Limited Reuse §4). Checked 2026-09-16. |
| 14 | Uniqueness or affine approaches have zero runtime overhead | **Mostly true.** Frees still cost allocator work, and conditional moves may need runtime drop flags unless the compiler rejects them. |
| 15 | Carp adopts Rust-style borrow checking | **Correct, with a qualifier.** Carp uses ownership, borrowed references and deterministic frees without a garbage collector. Unlike Rust, it did not separate mutable and immutable references as of its author's 2017 answer ("not at the moment"). A research report infers that its checks concern liveness rather than exclusivity. Checked 2026-09-16. |

## Lazy evaluation caveat

The user supplied this addition on 2026-09-15:

> Languages with non-strict evaluation (like Haskell) complicate this model.
> Thunks (delayed computations) introduce implicit mutability when evaluated, and
> recursive bindings can construct cyclic graphs of suspensions. Non-GC functional
> memory management is therefore overwhelmingly applied to strict (call-by-value)
> languages.

Assessment: **correct**, and consistent with correction 1. Forcing a thunk
overwrites it with its value, which is a hidden mutation, and recursive lazy
bindings create cycles. Koka, Lean 4, MLKit, Clean's strict-by-default code
paths, and Carp are strict or largely strict. A7 is strict, so the caveat does not
restrict it, but it confirms that A7's mutable data needs cycle handling that
does not depend on immutability.

## Relevance to A7

- **The acyclicity argument does not transfer.** A7 has mutable data, so a
  counting scheme would leak cycles. The recursion ban removes recursive functions,
  not cyclic data (notes B). Releasing storage by extent avoids the problem.
- **In-place reuse under L15 needs a static uniqueness proof.** Perceus places
  reuse statically but tests uniqueness at run time. FP² checks a function
  definition statically but leaves uniqueness at call sites to uniqueness types
  or runtime checks. A7 would have to supply the call-site part. Values that are
  truly shared are not reused. See the [storage reuse study](reuse-languages.md).
- **Region inference corresponds to extent inference.** Its known weakness is
  retention when long-lived and short-lived values share a region. GLM's advice
  limits this with coarser extents, such as loop iteration, task and training
  step, and with rejection instead of silent promotion. The memory plan instead
  uses an iteration release floor and copies values out on escaping paths
  (contract items 5 and 8).
- **Affine ownership is the static base.** It supplies both the release points and
  the uniqueness facts for reuse. Conditional moves need either rejection or
  runtime drop flags. That was a design decision; the memory plan chooses no drop
  flags (contract item 3).
- **Escape analysis applies directly.** Stack promotion of non-escaping values fits
  A7. Tail-call recycling does not apply because A7 bans recursion; loops play
  that role.

## Supplied text 1

```text
Pure functional programming without a tracing garbage collector relies on four distinct compile-time and runtime mechanisms. These take advantage of a fundamental mathematical invariant: pure immutability guarantees directed acyclic graphs (DAGs). Because an immutable object can only point to values that already exist, reference cycles cannot form organically.1. Precise Reference Counting with Reuse Analysis (The Perceus Model)Instead of relying on a runtime collector or naive, costly reference counting, modern compilers (such as Koka and Lean 4) use static reference count placement combined with destructive reuse.Pure Source Code:
map f (Cons x xs) = Cons (f x) (map f xs)

Perceus Compilation Target (C-like pseudo-code):
Node* map(Closure* f, Node* cell) {
    if (cell->rc == 1) {
        // Reuse buffer directly in-place: zero malloc/free overhead
        cell->head = apply(f, cell->head);
        cell->tail = map(f, cell->tail);
        return cell;
    } else {
        // Shared node: decrement reference and allocate new
        Node* new_cell = alloc_cons(apply(f, cell->head), map(f, cell->tail));
        dec_ref(cell);
        return new_cell;
    }
}
Borrow Inference: The compiler statically determines whether a function consumes ownership of an argument or merely reads it. "Borrowed" references do not trigger reference count increments (dup) or decrements (drop), eliminating up to 90% of reference-counting instructions.Reuse Pairs: When a pattern-matched data constructor (e.g., Cons) drops to rc == 1 at runtime, the compiler pairs its deallocation directly with the allocation of a successor node of identical or smaller memory footprint. The memory is updated in-place (Functional But In-Place, or FBIP), eliminating allocator bottlenecks.2. Static Region Inference (Tofte-Talpin System)First implemented in the ML Kit for Standard ML, region inference replaces per-object heap allocation with a stack of bulk-memory regions (arenas).Region Polymorphism: Every expression and type variable is annotated during compilation with an abstract region parameter $\rho$. For example, a pair allocation has the type:$$\text{pair} : \tau_1 \times \tau_2 \to (\tau_1 \times \tau_2) \text{ at } \rho$$Lifetime Scoping (letregion): The compiler computes the precise lifetime of values via static analysis. It then wraps expressions inside region allocators:$$\text{letregion } \rho \text{ in } e$$When evaluation of \(e\) terminates, the entire region \(\rho\) is deallocated en masse with a single pointer bump, freeing all nested structures simultaneously with zero per-object scanning.
Multiplicity Analysis: The compiler statically determines whether a region will hold zero, one, or infinitely many values, allowing it to select between single-word stack slots or growable arena pages.3. Substructural and Uniqueness TypesRather than tracking references at runtime, substructural type systems prevent sharing entirely or track aliasing at compile time.Linear & Affine Types: By enforcing that a value is used at most once (affine) or exactly once (linear), the compiler identifies the exact AST node where an object dies. A deterministic free() call is placed at that precise instruction.Uniqueness Typing (Clean / Austral): A type $\text{Unique}[T]$ guarantees that only a single path to the memory block exists across the entire program graph. Because aliasing is banned by the type checker:Mutations can happen destructively without breaking equational reasoning.Deallocation is statically scheduled at the exact point of consumption, requiring no runtime metadata header.4. Escape Analysis and Stack PromotionClosures and algebraic data types typically require heap storage if they outlive their parent scope. Escape analysis computes the flow of pointers through the call tree:Local Allocation: If an environment record, lambda closure, or intermediate list cell does not escape the lexical scope of the caller, it is allocated directly on the call stack.Tail-Call Stack Recycling: Because tail calls reuse the active stack frame ($O(1)$ space), intermediate accumulators and arguments continuously overwrite existing stack registers without generating heap garbage.Comparison of ApproachesStrategyMemory Reclaim TimingRuntime OverheadCode Size ImpactPrimary Failure Mode / Trade-offPerceus (RC + Reuse)Immediate at last dropAtomic/Non-atomic counter checksMinimalCost of counter branches when memory is widely sharedRegion InferenceScope exit (letregion)Near zero ($O(1)$ stack bump)ModerateMemory leaks if long-lived & short-lived values share a regionUniqueness / AffineStatic compile-time insertionZero
```

## Supplied text 2

```text
Eliminating tracing garbage collection in functional languages without sacrificing memory safety relies on four primary strategies: acyclic reference counting, destructive reuse analysis (FBIP), region inference, and substructural typing.1. Structural Acyclicity: Why Immutability Enables Pure Reference CountingIn imperative languages, standard reference counting (RC) requires a background tracing cycle collector because mutable pointers can create reference cycles (such as $A \to B \to A$), leaking memory when external pointers disappear. Pure functional programming avoids this entirely: because data structures are immutable upon construction, a value can only reference values that were created before it. The heap forms a strict Directed Acyclic Graph (DAG). Consequently, an object's reference counter reaching zero guarantees that the entire subgraph rooted at that object is dead and can be freed immediately.2. Perceus and Functional But In-Place (FBIP)Modern functional compilers like Koka and Lean 4 advance beyond basic RC using the Perceus algorithm. The compiler statically determines precise drop locations, inserting decrements at the exact point a variable is consumed for the last time. It then applies reuse analysis: if a constructor node is matched and its runtime reference count is uniquely owned ($\text{rc} = 1$), the compiler reuses that node's existing memory buffer directly rather than freeing it and allocating fresh heap memory.SVGHow Perceus turns pure functional pattern matching into in-place updates at runtime.This allows functional algorithms—such as quicksort, tree rebalancing, or map transformations—to execute with the memory footprint and raw speed of imperative mutations while retaining referential transparency.3. Tofte-Talpin Region InferencePioneered in Standard ML via the ML Kit, region inference eliminates runtime accounting overhead entirely. The compiler reconstructs memory management into an arena-based model through static type inference:Region Variables: Every expression and data type is annotated with an inferred region variable $\rho$, denoting where the value lives.Lexical Scoping: Values are assigned to nested regions introduced by a lexical construct, letregion \(\rho\) in \(e\) end.Bulk Reclamation: When the lexical scope of region $\rho$ terminates, the entire memory block is reclaimed in $O(1)$ time by popping the region stack pointer, without inspecting individual objects.4. Substructural Type Systems (Linear and Affine Typing)Substructural typing governs how many times a reference can be used, giving the compiler mathematical guarantees about memory lifetimes:Linear TypesEnforce that a value must be consumed exactly once. The compiler inserts a free instruction precisely where the binding is consumed, avoiding runtime counters.Affine Types & BorrowingAllow a value to be consumed at most once. Languages like Carp adopt Rust-style borrow checking, letting functions borrow immutable references while ensuring the unique owner deterministically reclaims memory when it goes out of scope.Uniqueness TypesUsed in Clean and Austral, uniqueness types guarantee that no other aliases to a pointer exist. If a function takes a *Unique Array, the runtime can update the array destructively without violating purity.Comparison of Non-GC Memory Management in Functional LanguagesStrategyRuntime OverheadLatency ProfileMemory Reclaim MomentPerceus / FBIPLow (counter updates, branch on reuse)Deterministic (interleaved drops)Immediate upon last dereferenceRegion InferenceZero per-allocation overheadPredictable batch deallocationsEnd of lexical region scopeLinear / Affine TypesNone (statically resolved)Strictly deterministic
```
