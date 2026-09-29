> **Source:** Claude research subagent. Primary-source study of Koka's Perceus, reuse analysis and FIP, from Perceus (PLDI 2021), Frame-Limited Reuse (ICFP 2022), FP² (ICFP 2023), Lorenzen's 2021 thesis, and the Koka book and repository.  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim, including the subagent's `[deepwiki]` and `[Inference]` labels. Paper section numbers are the subagent's citations and were not re-checked. User decisions are in the [ledger](../../../decisions.md).

# Koka: Perceus, Reuse Analysis, and FBIP/FIP — research notes for A7

Research date: 2026-09-16. All section numbers refer to the published papers cited in
**Sources**. Statements are sourced unless explicitly marked `[Inference]`.
Passages in quotation marks are verbatim from the cited source.

Note on one source class: `deepwiki` answers (an AI index over the GitHub repositories) are
**secondary** and are labelled `[deepwiki]` wherever used. They are used only for
implementation details (file/function names, exact-size matching, Lean pass names), never
as the sole basis for a claim verdict where a paper speaks.

---

## Summary (5 lines)

1. Perceus is a *static* ownership discipline (a linear resource calculus, λ¹) that inserts
   `dup`/`drop` precisely; the only genuinely dynamic ingredient is a one-word `is-unique`
   test on the reference count header.
2. Reuse analysis is almost entirely static: it pairs a matched constructor with a
   **same-size** allocation in the same branch; the count is consulted once, to decide
   whether the paired cell may actually be taken.
3. FP² (ICFP'23) is the part A7 wants: the FIP calculus proves in-placeness *statically*
   with linear "reuse credits", and the paper states FIP is exactly the subset that needs
   **no dynamic reference counting at runtime** — but Koka still compiles it dynamically.
4. Perceus's costs come from what counts buy: cycles leak (Koka has no collector and hands
   the problem to the programmer), thread sharing forces atomics, and one function can serve
   both unique and shared callers only *because* uniqueness is not in the type.
5. Of our six claims, three are false as written (Lean 4/Perceus, "identical or smaller
   size", "entire subgraph freed"), one is unsourced ("90%"), and two need qualification.

---

## 1. What exactly is Perceus? The algorithm

**Name and claim.** "Perceus, pronounced *per-see-us*, is a loose acronym of 'PRecise
Reference Counting with rEUse and Specialization'" (Perceus, §2 footnote 1). The abstract
states Perceus "emits precise reference counting instructions such that programs are
*garbage free*, where only live references are retained" — and the Introduction scopes this
to "(cycle-free) programs".

The user-facing docs make the same claim in plainer terms (`doc/spec/why.kk.md`, §2.4 "Perceus
Optimized Reference Counting"): "Perceus uses extensive static analysis to aggressively optimize
the reference counts", which lets Koka "compile directly to plain C code without needing a
garbage collector or runtime system", and is "garbage-free" in that "objects are always
immediately deallocated as soon as they become unreachable". The stated performance target there
is "within 2x of the performance of C/C++". (Caveat, cross-referenced below: the garbage-free
property is a property of Perceus *before* reuse analysis and borrowing — see §2 and claim C4.)

**The core discipline is ownership, not scope.** §2.2: "Perceus takes a more aggressive
approach where *ownership* of references is passed down into each function: now `map` is in
charge of freeing `xs`, and `ys` is freed by `print`: no `drop` operations are emitted inside
`foo` as all local variables are *consumed* by other functions". This contrasts with
"scoped lifetime" reference counts as in C++ `shared_ptr`, Rust `Rc<T>`, Nim, and Swift
(§2.2).

**Where dup and drop go, and on what analysis.** The algorithm is presented not as a
dataflow pass but as a *syntax-directed derivation* of a linear resource calculus:

- §3.1–§3.2 define λ¹ with judgement `Δ | Γ ⊢ e ⇝ e'`, where Δ is a **borrowed** environment
  and Γ a **linear (owned)** environment. "The key idea of λ¹ is that each resource (i.e.
  owned variable) is consumed *exactly* once. That is, a resource needs to be explicitly
  duplicated (in rule DUP) if it is needed more than once; or be explicitly dropped
  (in rule DROP) if it is not needed" (§3.2). Declarative rules: Fig. 5 (VAR, DUP, DROP,
  APP, LAM, BIND, MATCH, CON).
- §3.4 defines the **Perceus algorithm itself** as the syntax-directed system `⊢s` of Fig. 8,
  maintaining the invariants "(1) Δ ∩ Γ = ∅; (2) Γ ⊆ fv(e); (3) fv(e) ⊆ Δ, Γ; and (4)
  multiplicity of each member in Δ, Γ is 1."
- The placement rule, verbatim (§3.4): "The Perceus rules are set up to do precise reference
  counting: we delay a `dup` operation to come as late as possible, pushing them out to the
  leaves of a derivation; and we generate a `drop` operation as soon as possible, right after
  a binding or at the start of a branch."
- Guarantees: Theorem 3 (syntax-directed translation is sound) and **Theorem 4** ("Perceus is
  precise and garbage free"), §3.4. Theorem 2 (§3.3) is "Reference counting leaves no
  garbage".

So the analysis is a liveness/linearity analysis expressed as a type-system-style derivation.
The follow-up paper confirms the liveness reading: "Perceus already performs precise liveness
analysis and it has been shown it inserts optimal dup/drop insertion" (Frame-Limited Reuse,
§3.2).

**Hard prerequisite: explicit control flow.** §2.7.1: "An essential requirement of our
approach is that programs have explicit control flow so that it is possible to statically
determine where to insert `dup` and `drop` operations." Koka achieves this by compiling
exceptions and all algebraic effect handlers into explicit control flow via effect typing and
evidence translation (§2.7.1, and footnote 3: a multi-prompt delimited control monad).

**Four post-passes turn the naive insertion into fast code** (§2.3–§2.5, Fig. 1a–1g):
1. `dup`/`drop` insertion (§2.2, Fig. 1b).
2. **Drop specialization** (§2.3): inline `drop(x) = if (is-unique(x)) then drop children of
   x; free(x) else decref(x)` at a known constructor (Fig. 1c).
3. **Push down `dup` into branches and fuse** matching `dup`/`drop` pairs (§2.3, Fig. 1d).
   "After this transformation, almost all reference count operations in the fast path are
   gone."
4. **Reuse analysis** (§2.4) and **reuse specialization** (§2.5), below.

Implementation, for orientation: `src/Backend/C/Parc.hs` (`parcCore`, reverse traversal for
live variables, `optimizeGuard`, `specializeDrop`), `src/Backend/C/ParcReuse.hs`,
`src/Backend/C/FromCore.hs` (`genDupDrop`), and `kklib/src/refcount.c` (`kk_block_check_drop`,
`kk_block_drop_reuse`) `[deepwiki]`.

---

## 2. Reuse analysis: the decision, the runtime test, its cost, and size vs constructor

**The static pairing.** §2.4, verbatim: "*Reuse analysis* is performed before emitting the
initial reference counting operations. It analyses each `match` branch, and tries to pair each
matched pattern to allocated constructors **of the same size** in the branch. In our `map`
example, `xs` is paired with the `Cons` constructor. When such pairs are found, and the
matched object is not live, we generate a `drop-reuse` operation that returns a *reuse token*
that we attach to any constructor paired with it."

**The runtime test.** §2.4 gives the pseudocode:

```
fun drop-reuse( x ) {
  if (is-unique(x)) then drop children of x; &x
                    else decref(x); NULL
}
```

and the paired allocation `Cons@ru` "means that (at runtime) if `ru==NULL` then the `Cons`
node is allocated fresh, and otherwise the memory at `ru` is of the right size and can be used
directly."

**What the test costs.** It is a single header read and branch. The paper's description of
kklib (§2.7.2) encodes the count so that one comparison covers both the free case and the
thread-shared case:

```
static inline void drop( block_t* b ) {
  if (b->header.rc <= 1) drop_check(b);   // slow path
                    else b->header.rc--;
}
```

with footnote 4: "Since the thread-shared sign-bit is *stable*, we can do the test
`b->header.rc <= 1` without needing expensive atomic operations and can use a
`memory_order_relaxed` atomic read." After drop specialization and dup/drop fusion, §2.4
reports for `map`: "In the fast path, where `xs` is uniquely owned, there are no more
reference counting operations at all!" — i.e. on the hot path the residual cost is the
`is-unique` branch itself. FP² §6 measures the aggregate cost of this dynamism: "That
`std-reuse` is only about 1% slower shows that the dynamic reuse check has negligible impact
on performance."

**Same size, or same constructor, or neither? → Same *size*, exactly.**
- Perceus §2.4: "constructors **of the same size**" (above).
- Frame-Limited Reuse §2.2: "Reuse analysis ... takes advantage of precise reference counts to
  try to reuse objects in-place. We can pair objects of known size with **same sized**
  allocated constructors and try to reuse these in-place at runtime."
- FP² makes the size explicit as a resource: "This 'diamond' resource type ◊k represents a
  specific heap cell of size k ... Similar to their space credits, we also apply the linearity
  restriction to reuse credits, but, unlike space credits, a reuse credit can **not be split
  or merged** with other credits" (§1.1).
- Implementation: `ruIsReusable` computes `conReprAllocSize` and returns `ReusableWithSize
  size`; `ruTryReuseCon` looks up an available block of the **exact** size; a `pick` preference
  for the *same constructor* exists but is disabled; `kk_block_alloc_at` takes a size and
  carries a TODO about checking the usable size of the reused block `[deepwiki]`.

So reuse is **size-keyed, constructor-agnostic** — a `Cons` cell can become a different
two-field constructor of the same size. Different sizes do not pair. FP² works around this by
*padding*: a finger-tree buffer is "a padded list of size 3, which makes it available for reuse
with the rest of the finger tree" (§4), and the thesis has a section on "B-trees and
constructor padding" (Lorenzen 2021, ToC §4.6).

**Reuse specialization** (§2.5) goes one step further and avoids re-writing unchanged fields:
`Cons@ru(x,xx)` compiles to `if (ru!=NULL) then { ru->head := x; ru->tail := xx; ru } else
Cons(x,xx)`. "Thus, we only specialize constructors if at least one of the fields stays the
same."

**Drop-guided reuse (the 2022 revision).** Frame-Limited Reuse §3 shows both published reuse
algorithms (Koka's "algorithm K" and Lean's "algorithm D") "are quite fragile with respect to
small program transformations" — inlining `is-red` breaks reuse in red-black insertion (§3.1.1).
The fix (§3.2) is to run reuse **after** Perceus: "we keep track of the currently known sizes
of each variable ... and if we encounter a `drop` we can statically determine if it can pair
with a later allocation of the same size", rewriting that `drop` into a `dropru`.

**Important cost, for A7's ledger:** reuse *sacrifices* garbage-freedom. §4: "since reuse
analysis keeps heap cells alive until they can be reused, it means that **no reuse analysis can
preserve the garbage-free property**!" Drop-guided reuse is instead proven *frame-limited*
(§4.1, §5.4): peak memory is bounded by a constant factor times the number of stack frames.

---

## 3. Borrowed parameters: declared or inferred, what they remove, and measurements

**In Koka they are declared, not inferred.** The annotation is a hat: FP² §1.3 — "the function
parameter is marked as *borrowed* using the hat notation (`^f`) [Ullrich and de Moura 2019]".

**What they eliminate.** Frame-Limited Reuse §4.2, verbatim: "When we annotate a parameter
like `xs` to be borrowed (as `^xs`), the caller keeps ownership of the parameter. As a result,
**no reference count operations need to be performed at all** for the `xs` parameter in our
example. Note that borrow annotations are strictly a performance hint, and do not change
semantics or whether a program is well-typed (in contrast to the notion of borrowing in a
language like Rust)."

In the calculus, borrowing is what lets `dup` be delayed: §3.2 of Perceus — "Borrowing is
important as it allows us to conduct a `dup` as late as possible, or otherwise we will need to
duplicate enough resources before we use the owned environment."

**Is it inferred anywhere?** Not in Koka. Frame-Limited Reuse §4.2, verbatim: "Ullrich and de
Moura (2019) describe a borrow inference algorithm that marks `xs` automatically as borrowed.
However, given that this is not safe for space, we argue that automatic borrow inference should
be further restricted to guarantee it is at least frame-limited. Therefore, **Koka currently has
no automatic borrow inference** and generally only uses borrowing for built-in primitives (like
(big) integer operations)." (The compiler flag `parcBorrowInference` defaults to `False`
`[deepwiki]`.) At PLDI'21 borrowing was still future work: "We would like to integrate selective
'borrowing' into Perceus – this would make certain programs no longer be *garbage free*"
(Perceus §6).

Lean *does* infer borrow signatures: "Borrow annotations can be provided manually by users
(which is always safe), but we have two motivations for inferring them: avoiding the burden of
annotations, and making our IR a convenient target for other systems (e.g., Coq, Idris and
Agda) that do not have borrow annotations" (Counting Immutable Beans §5.2; heuristic in Fig. 4).

**Published measurement of how many count operations borrowing removes: not found.**
I searched the Perceus paper, Frame-Limited Reuse, FP², Lorenzen's thesis, and Counting
Immutable Beans. None reports a count-operation reduction percentage. The closest published
numbers are *runtime* effects:

- Counting Immutable Beans, Fig. 6 (Lean variants, normalized to base): the `-borrow` column
  (borrow inference **disabled**) has geometric mean **1.27** vs base 1.00; per-benchmark:
  binarytrees 1.14, deriv 1.16, const_fold **0.90**, parser 1.00, qsort 1.00, rbmap 1.07,
  rbmap_10 1.52, rbmap_1 4.47, unionfind 1.00. Note `const_fold` is *faster without* borrowing.
- Lorenzen's thesis §6.5 on Lean's inference: "this inference made some programs slower, both
  in their benchmarks as well as our experience. We believe that a significant part of this
  slowdown can be found in the fact that Lean's borrow inference can hold on to memory for much
  longer than necessary."
- Thesis §6.4 on Koka's nqueens (Fig. 6.8): borrowing `xs` in `safe` helps, "but the effect is
  much bigger for the 32-bit variant: The arbitrary-precision variant still has to handle dup
  and drop operations on `queen` and `diag` while the 32-bit variant has to handle no other
  reference count instructions".

See **Claims checked**, item 2.

---

## 4. FBIP: what it is and what it asks of the programmer

**Definition.** Perceus §2.6, "A New Paradigm: Functional but In-Place (FBIP)": "This style of
programming that we call FBIP: 'functional but in place'. Just like tail-call optimization lets
us describe loops in terms of regular function calls, reuse analysis lets us describe in-place
mutating imperative algorithms in a purely functional way (and get persistence as well)."

**It is a discipline the programmer follows, and the guarantee is contractual — not an invisible
optimization.** The decisive sentence, Perceus §2.6: "Importantly, a programmer can **rely on
this optimization happening**, e.g. they can see the `match` patterns and match them to
constructors in each branch."

The Koka book says the same to users (`doc/spec/tour.kk.md`, §"FBIP: Functional but In-Place"):
"With Perceus reuse analysis we can write algorithms that dynamically adapt to use in-place
mutation when possible (and use copying when used persistently). **Importantly, you can rely on
this optimization happening**, &eg; see the `match` patterns and pair them to **same-sized
constructors** in each branch."

The docs state the same contract twice. `doc/spec/why.kk.md` (§2.5 "Reuse Analysis") says reuse
"pairs pattern matches with constructors of the same size and reuses them in-place if possible",
and that "the reuse optimization is guaranteed and a programmer can see when the optimization
applies" — plus a note that tail-recursion-modulo-cons (TRMC) turns the recursive call into "an
in-place updating loop for the fast path".

So the split is: the *mechanism* (tokens, `is-unique`, field assignment) is invisible; the
*obligation* is visible and on the programmer — write each branch so every destructed
constructor has a same-size allocation to pair with. Worked examples: red-black tree insertion
(§2.5: "every `Node` is reused in the fast path without doing any allocations!") and a
stack-less Morris-style in-order traversal derived from a `visitor` zipper (§2.6, Fig. 3:
"each `Bin` matches up with a `BinR`, each `BinR` with a `BinL` ... Since they all have the same
size, if the tree is unique, each branch updates the tree nodes *in-place* at runtime without
any allocation").

Pre-FP², nothing checked that you got it right. FP² adds the `fip`/`fbip` keywords so the
compiler verifies and reports it (see §9 below).

---

## 5. Cycles

Perceus §2.7.4 "Cycles", verbatim and in full substance:

> "A known limitation of reference counting is that it cannot release cyclic data structures.
> Just like with mutability, we try to mitigate its performance impact by reducing the potential
> for this to occur in the first place. In Koka, almost all data types are immutable and either
> *inductive* or *coinductive*. It can be shown that such data types are never cyclic (and
> functions that recurse over such data types always terminate).
>
> In practice, mutable references are the main way to construct cyclic data. Since mutable
> references are uncommon in our setting, **we leave the responsibility to the programmer to
> break cycles by explicitly clearing a reference cell** that may be part of a cycle. Since this
> strategy is also used by Swift, a widely used language where most object fields are mutable,
> we believe this is a reasonable approach to take for now. However, we have plans for future
> improvements: since we know statically that only mutable references are able to form a cycle,
> we could generate code that tracks those data types at run time and may perform a more
> efficient form of incremental cycle collection."

Corroborating statements:

- §1: "although we currently do not supply a cycle collector, our design has two mitigations to
  reduce the occurrences of cycles in the first place. First, *(co)inductive* data types and
  eager evaluation prevent cycles outside of explicit mutable references, and it is statically
  known where cycles can possibly be introduced in the code (Section 2.7.4)."
- §2.7.5: "This paper does not yet present a general solution to all problems with reference
  counting and future work is required to explore how cycles can be handled more efficiently".
- §6 (Conclusion): "It also remains to be seen if we can handle cycle collection efficiently."
- Frame-Limited Reuse §9: "in a functional style language like Koka it is uncommon to create
  cycles (which can only be created through mutable references). We would like to see if we can
  combine some of the static analysis with cycle collection."

**Net:** Koka has no cycle collector; a cycle built through a `ref` leaks unless the programmer
clears a cell. Note also a separate non-collection case in the runtime: reference counts that
overflow enter a "sticky" range and the object "will never be freed" (Perceus §2.7.2: "a
*sticky* range where very large reference counts (2^30 in our implementation) stay without being
further adjusted, and keeping them alive for the rest of the program").

---

## 6. How much of the uniqueness decision is static, and is there a static-only mode?

**Static:** everything about *placement*. Which variable is owned vs borrowed, where a `dup` is
needed, where a `drop` is emitted, which match arm pairs with which allocation, and which
constructor fields can be assigned in place (§2.3–§2.5, §3.4). None of that consults a count.

**Dynamic:** exactly one thing — *whether this particular cell is unique right now*, via
`is-unique(x)` (`kk_datatype_ptr_is_unique`, a header read). Both the free/decref decision and
the reuse/allocate decision hang off it (§2.3, §2.4).

**Is there a mode where Koka proves uniqueness statically and drops the check?** The papers say
no for the shipped implementation, and explain why the dynamic check is *wanted*:

- Perceus §5, verbatim: "Generally, a system with linear types, like linear Haskell, or the
  uniqueness typing of Clean, can offer *static* guarantees that the corresponding objects are
  unique at runtime, so that destructive updates can always be performed safely. However, this
  usually also requires writing multiple versions of a function for each case (unique- versus
  shared argument). By contrast, reuse analysis relies on dynamic runtime information, and thus
  reuse can be performed generally. This is also what enables FBIP to use a single function that
  can be used for both unique or shared objects (**since the uniqueness property is *not* part of
  the type**). These two mechanisms could be combined: **if our system is extended with unique
  types, then reuse analysis could statically eliminate corresponding uniqueness checks.**"
  — i.e. the static-only mode is named as future work, not shipped.
- FP² §1.4.2, on Koka's `fip` implementation: "Checking call sites of `fip` functions need not
  happen statically. Instead, we could also use a *dynamic* approach where we check at runtime if
  a FIP function can be executed in-place. **This is the approach taken in our implementation in
  the Koka language**, which uses Perceus precise reference counting." And, after showing the
  generated code for `fip fun reverse-acc` with an explicit `is-unique(xs)` test: "Compared to
  the static analysis, **we have lost the static guarantee that the owned parameters are unique at
  runtime**, but also we gained expressiveness".
- Confirmed in the implementation: `fip`-annotated functions still emit
  `kk_datatype_ptr_is_unique` and fall back to copying when the test fails `[deepwiki]`.
- The theoretical statement of what *would* remove counts is FP² §1.5: "FIP is exactly that
  subset of λ^fip which **requires no dynamic reference counting or memory management at
  runtime**. As a result, in the Perceus setting FIP functions can interact safely with any other
  function, executing in-place when possible and copying when necessary."

---

## 7. Published performance numbers

### 7.1 Perceus, §4 (Fig. 9)

Setup: Koka 2.0.3 → C via gcc 9.3.0 with a customised mimalloc; **OCaml 4.08.1**, **Haskell GHC
8.6.5** (with strictness annotations), **Swift 5.3**, **Java SE 15.0.1** (HotSpot G1), **C++
gcc 9.3.0** (libc allocator). 6-core AMD 3600XT, 64 GiB, Ubuntu 20.04. Median of 10 runs,
normalized to Koka. A "Koka no-opt" variant disables drop/reuse specialization and reuse
analysis.

Benchmarks: **rbtree** (42M red-black insertions then a fold), **rbtree-ck** (rbtree keeping
every 5th tree, so subtrees are shared), **deriv** (symbolic derivative, up to 10M nodes),
**nqueens** (all solutions for n=13; solution lists share sub-solutions), **cfold** (constant
folding over a 2M-node expression).

Headline result, §1 and §4: "on the tree insertion benchmark, the purely functional Koka
implementation is **within 10% of the performance of the in-place mutating algorithm in C++**
(using `std::map`)". Fig. 9 shows C++ at 0.92 relative to Koka on rbtree.

Author caveats, verbatim (§4): "we compare across languages we need to interpret the results
with care – the results depend not only on memory reclamation but also on the different
optimizations performed by each compiler and how well we can translate each benchmark to that
particular language. We view these results therefore mostly as **evidence that the Perceus
reference counting technique is viable and can be competitive and *not* as a direct comparison
of absolute performance between systems**." Also: "we selected only benchmarks that stress
memory allocation"; the C++ baselines are not equivalent programs — "we either use in-place
updates without supporting persistence (as in `rbtree` which uses `std::map`) or we do not
reclaim memory at all (as in `deriv`, `nqueens`, and `cfold`)"; no C++ version exists for
rbtree-ck ("this would essentially require a persistent implementation of `std::map`").

Other reported figures in §4: Java "uses almost 10× the memory of Koka (1.7GiB vs. 170MiB)";
on cfold "the 'no-opt' version is more than 2× slower", while "in benchmarks with lots of
sharing, like `deriv` and `nqueens`, the optimizations are less effective"; and §4's closing
concurrency measurement — running all reference counts as atomics gives "a slowdown from 5%
(`rbtree`) up to 59% (`nqueens`)".

### 7.2 Frame-Limited Reuse (drop-guided reuse + TRMC + FBIP)

- §1/§6: the purely functional red-black insertion "is about **19% faster** than the manually
  optimized in-place mutating red-black tree implementation in the C++ STL library
  (`std::map`)".
- §7.1 (binarytrees, FBIP visitor): "with this implementation of `check` Koka becomes **17%
  faster** and within 25% of the performance of the C++ implementation (0.8× versus Koka fbip)".
- §7.2 (red-black trees, FBIP zipper): "about **10% faster** than the regular version and now
  around **30% faster** than the C++ STL version".
- Fig. 8 (AMD5950X) and Fig. 9 (arm64 M1) compare Koka, "Koka no trmc", "Koka old", OCaml,
  Haskell, Swift, Java, clang 13.0.0 and "Koka fbip" over rbtree, rbtree-ck, binarytrees, deriv,
  nqueens, cfold. Caveat noted in App. B: on the M1 "Koka now has similar performance as C++.
  This may be partly due to the use of the clang (vs gcc) which uses a slightly different
  implementation of red-black tree rebalancing in `std::map`."

### 7.3 FP² (§6, Fig. 10)

Ubuntu 22.04.2, AMD7950X, Koka v2.4.1-dev-fbip; average of 5 runs; N=100000, 100 iterations.
Variants: `fip`, `std` (no reuse optimization), `std-reuse` (standard Koka, dynamic reuse),
`c/c++`, and `c/c++` linked with mimalloc. Benchmarks: **rbtree**, **ftree** (finger tree
uncons/snoc), **msort**, **qsort**, **tmap** (map over a *shared* tree).

Stated conclusions (§6): "The performance of `fip` versus `std` is generally much better showing
that in-place updating is indeed generally faster than allocation"; "in the `rbtree` benchmark
the `fip` variant rivals the performance of the in-place updating `std::map` implementation in
C++"; "`tmap` ... the `fip` variant is generally slower here" because the mapped tree is shared
and the zipper-based traversal reverses pointers Schorr-Waite style; and "That `std-reuse` is
only about 1% slower shows that the dynamic reuse check has negligible impact on performance."
Author caveat: "It is hard to draw firm conclusions as the results are dependent on our
particular implementation".

### 7.4 Lean (Counting Immutable Beans, §8) — for the Lean/Perceus comparison

Fig. 7 compares **Lean 4** against **GHC 8.8.3**, **ocamlopt 4.10**, **MLton 20180207**, **MLKit
4.4.2**, **Swift 5.1.1** on binarytrees, deriv, const_fold, qsort, rbmap (+rbmap_10, rbmap_1),
reporting wall clock (normalized to Lean), GC time %, and last-level cache misses. Noted result:
"Using `const_fold` as an example again, Lean spends only 17% of the runtime deallocating memory,
while OCaml spends 90% in the GC." Fig. 6 gives the ablation (`-reuse` 1.74 geo-mean, `-borrow`
1.27, `-ST` 1.89 vs base 1.00).

---

## 8. What Koka's model makes hard or impossible

**Cyclic data.** No collector; the programmer must break cycles by clearing a `ref`
(§2.7.4). Any data structure that is genuinely a cyclic graph — doubly-linked lists with owning
back-pointers, graphs with back edges, observer registries — leaks unless manually torn down.
`[Inference]` This is the main *expressiveness* tax of RC-without-a-collector, and it is the one
tax A7 does not inherit if it forbids sharing statically.

**Mutable references are a second-class citizen by design.** §2.7.3 shows the read/write race on
a thread-shared `ref`: "To make this work correctly, we need to perform both operations
atomically, either through a double-CAS, using hazard pointers, or using some other locking
mechanism. Either way, this can be quite expensive. Fortunately, in our setting, since FBIP
allows for the efficiency of in-place updates with a purely functional specification (Section
2.6), **we expect mutable references to be a last resort rather than the default**."

**Concurrency.** Objects must be marked thread-shared recursively when handed to a thread
(`tshare : forall a. a -> io ()`), and shared objects can never be un-shared: "Even though
marking is linear, it happens at most once for any object since shared objects cannot be
unshared" (§2.7.2). Thread-shared objects take the atomic path; the measured worst case is a 59%
slowdown when all counts are atomic (§4).

**Sharing defeats reuse, silently and at runtime.** When the `is-unique` test fails, the
algorithm copies: §2.5 — "if we use the tree *persistently* ... the algorithm adapts to copying
exactly the shared *spine* of the tree (and no more), while still rebalancing in place for any
unshared parts". Good for correctness, but performance becomes data-dependent and invisible in
the type: benchmarks with heavy sharing (`deriv`, `nqueens`, `rbtree-ck`) show the optimizations
"are less effective" (§4).

**Reuse is fragile under ordinary compiler transformations** (pre-2022): Frame-Limited Reuse
§3.1–§3.1.1 shows inlining `is-red` makes both Koka's algorithm K and Lean's algorithm D fail to
reuse; "both published algorithms are quite fragile with respect to small program
transformations." Drop-guided reuse fixes this.

**Borrowing costs peak memory and can inhibit other optimizations.** Frame-Limited Reuse §4.2:
"if `xs` happens to be unique, we allocate the tree while the full `xs` list is still live ...
In general, borrowing can increase the memory usage of a program by an arbitrary amount and it
is generally *not* frame-limited." App. C.1 gives a program where a borrow annotation keeps `n`
big lists alive instead of one. Thesis §6.4 adds that borrowing "should not inhibit reuse
optimization or tail call optimization, since these are more powerful optimizations".

**Only same-size cells pair.** Data structures whose nodes differ in arity get no reuse across
those shapes without padding (see §2 above; FP² §4 pads finger-tree buffers; thesis §4.6 on
B-tree/constructor padding).

**Non-linear control flow must be compiled away** (§2.7.1); a language that keeps `longjmp`-style
or un-resumed asynchronous continuations cannot do precise ownership-based insertion.

---

## 9. FP²: what "fully in-place" adds, and its restrictions

**What it adds.** FP² (ICFP'23) contributes a *static* proof of in-placeness. Abstract: "We
describe a linear *fully in place* (FIP) calculus where we prove that we can always execute such
functions in a way that requires no (de)allocation and uses constant stack space." §1: "the `fip`
keyword indicates that a static check guarantees the function is fully in-place." The weaker
`fbip` keyword signifies "FIP functions that still reuse in-place but are allowed to use
arbitrary stack space and deallocate memory" (§1.3). Both admit a budget form: "we also support
`fip(n)` and `fbip(n)` for a constant `n`, which allows the function to allocate at most `n`
constructors" (§1.3).

Koka's own user docs (`samples/learn/fip.kk`) `[deepwiki]`: "The `rev` function is fip: due to
Perceus reference counting, if the argument list `xs` is unique at runtime, each `Cons` cell is
reused and updated *in-place* for the reversed accumulator: no memory is (de)allocated and
constant stack space is used" and "There are severe restrictions on `fip` functions to make this
guarantee. See the paper for details. In essence, all owned parameters must be used linearly, and
the function can only call `fip` functions itself."

**The restrictions (FP² §1–§2, Fig. 2/Fig. 4):**
1. **Linearity of owned parameters.** "The FIP rules ensure that variables in the owned
   environment Γ are used linearly (with some borrowing allowed in LET). However, this is a
   syntactic property and we do not use a linear *type* system" (§2.2). VAR consumes the only
   element of Γ.
2. **Not affine — you may not discard.** §2.2: "The owned environment must be empty here since
   our calculus is not affine: we cannot discard owned variables as that implies freeing a
   potentially heap allocated value (but in the next section we consider an extension of FIP
   that allows deallocation as well)" — that extension is `fbip`.
3. **Reuse credits ◊k, exact size, non-splittable.** Destructive match `match!` on an owned
   variable yields a credit ◊k per branch; only REUSE (a constructor with k ≥ 1 arguments) or
   EMPTY (zero-size credit) may consume one (§2.2). Borrowed matches (`bmatch`) "can only be
   used to inspect values without creating fresh reuse credits".
4. **Borrowed parameters may only be inspected.** They cannot be destructively matched, "passed
   as an owned parameter, or returned as a result" (§1.3). And "we consider an application `f(e)`
   as a borrowed use of `f`, and, as a consequence, `f` cannot modify any captured free variables
   in-place."
5. **No general lambdas; effectively second-order.** §1.3: "We enforce this in our calculus by
   only allowing top-level functions (rather than arbitrary closures) as arguments in our fully
   in-place calculus, effectively making it second-order." §2: "There are no general lambda
   expressions. In general, closures need to be heap allocated if they contain free variables."
6. **Unboxed tuples and atoms are required to hit zero allocation.** Tuples are "unboxed values
   hence no allocation is needed for these"; constructors without fields are "atoms" represented
   by pointer tagging (§1.1, §1.2). Footnote 3: "The `fip` keyword additionally checks that no
   automatic (heap allocated) boxing is applied for such value types inside a FIP function."
7. **`fip` functions may only call `fip` functions** (Koka docs, above; enforced in
   `src/Core/CheckFBIP.hs` `[deepwiki]`).
8. **Call sites are not covered by the static check.** §1.4: "The FIP calculus presented here
   statically checks a function's *definition* — yet deciding which *calls* to `fip` functions
   can be safely executed using destructive updates requires further information about how
   arguments are shared at call sites." Their example: in `fun palindrome(xs) = append(xs,
   reverse(xs))`, `reverse` is `fip` but "it would not be safe for it to destructively update its
   input list since the argument `xs` is used twice". Two ways out are named: uniqueness typing
   (Clean) with the drawback of "code duplication, where a single function can have multiple
   different implementations" (§1.4.1), or dynamic Perceus checks — "the approach taken in our
   implementation in the Koka language" (§1.4.2).

**The sentence that matters most for A7** (§1.5): "FIP is exactly that subset of λ^fip which
requires no dynamic reference counting or memory management at runtime."

---

## Claims checked

### C1. "Koka and Lean 4 both use Perceus." — **FALSE as stated.**

Lean's RC scheme (IFL'19) predates Perceus (PLDI'21), and Lean 4 uses that earlier, different —
though closely related — scheme.

- Lean's scheme is Ullrich & de Moura, *Counting Immutable Beans* (IFL'19, submitted Aug 2019;
  arXiv v3 Mar 2020). It defines λ_pure → λ_RC with `inc`/`dec`, `reset`/`reuse` (§4, §5), and
  **borrow inference** (§5.2). Perceus is PLDI'21.
- Perceus explicitly builds *on* it, and distinguishes itself: §1 — "we build on the pioneering
  reference counting work in the Lean theorem prover [46], but we view it through the lens of
  language design, rather than purely as an implementation technique." §5 — "Our work is closely
  based on the reference counting algorithm in the Lean theorem prover as described by Ullrich
  and de Moura. ... As such, **the Perceus algorithm may differ from the Lean one** as that is
  specified over a lower-level calculus that uses explicit partial application nodes (pap) and
  has no first-class lambda expressions."
- Frame-Limited Reuse §3 treats them as two distinct published algorithms: "the Koka algorithm,
  which we call algorithm K (Reinking, Xie et al., 2021)" vs "The Lean algorithm, called
  algorithm D (Ullrich and de Moura, 2019 Fig 3)", and shows they behave differently (D is "more
  robust but can lead to an arbitrary increase in peak memory usage").
- Lean 4 source: the RC work is in `src/Lean/Compiler/LCNF/ExplicitRC.lean`,
  `ResetReuse.lean`, and `InferBorrow.lean`; `src/Lean/Compiler/IR/Basic.lean` states the IR
  implements an extended λPure/λRc from *Counting Immutable Beans*; "Perceus" does not appear
  `[deepwiki]`.

**Correct phrasing for our docs:** "Lean 4 and Koka use closely related ownership-based
reference counting with reset/reuse; Koka's variant is Perceus (PLDI'21), which builds on Lean's
earlier scheme (IFL'19). Borrow *inference* is Lean's; Koka does not ship it."

Differences worth keeping: Lean infers borrow signatures, Koka does not; Koka's reuse is
drop-guided since 2022 and frame-limited, Lean's algorithm D is not (Frame-Limited Reuse §4.1,
App. C.3).

### C2. "Borrow inference eliminates up to 90% of count operations." — **UNSOURCED; and false for Koka.**

- No such figure appears in the Perceus paper, Frame-Limited Reuse, FP², Lorenzen's thesis, or
  Counting Immutable Beans. **Not found.**
- Worse, the premise fails for Koka: "Koka currently has no automatic borrow inference and
  generally only uses borrowing for built-in primitives" (Frame-Limited Reuse §4.2). Borrow
  inference is Lean's (Counting Immutable Beans §5.2).
- The only published numbers are runtime ablations, not operation counts: Lean's `-borrow`
  ablation is geo-mean **1.27×** base runtime, i.e. borrow inference buys ~21% of runtime on that
  suite, with one benchmark (`const_fold` 0.90) *faster without it* (CIB Fig. 6).
- A "reducing reference count increments by 75–100%" figure does exist in the literature, but
  for a **different system**: "Fully-Automatic Type Inference for Borrows with Lifetimes"
  (OOPSLA 2026), which implements borrows-with-lifetimes inference in the *Morphic* language
  stack and compares against Perceus. `[Unverified — seen only in a search-result summary; I did
  not read the paper. Do not cite this number for Koka.]`

**Recommended action:** delete the claim, or replace with the sourced sentence: borrow
annotations remove *all* count operations for the borrowed parameter (Frame-Limited Reuse §4.2),
at a cost in peak memory that is not frame-limited.

### C3. "Reuse pairs a freed node with an allocation of identical or smaller size." — **FALSE as stated ("or smaller").**

The pairing is on **identical** size. Perceus §2.4 "constructors of the same size"; Frame-Limited
Reuse §2.2 "same sized allocated constructors"; FP²'s ◊k credits are size-specific and
non-splittable (§1.1). The implementation looks up the exact size and asserts the block's field
count on reuse; `kk_block_alloc_at` carries only a TODO about checking usable size `[deepwiki]`.
A *smaller* constructor reusing a larger cell is not what the algorithm does — instead FP² pads
constructors so sizes coincide (§4). Also note the pairing is **constructor-agnostic**: any
constructor of the same size can take the cell.

### C4. "Perceus reclaims memory immediately upon last dereference." — **TRUE of plain Perceus, with three caveats; and the wording is wrong.**

- Sourced core: "An important attribute that sets Perceus apart is that it is *precise*: an
  object is freed as soon as no more references remain" (§2.2), formalized as Theorem 4 "Perceus
  is precise and garbage free" (§3.4).
- Caveat 1 — **cycle-free only**. Abstract: "such that (cycle-free) programs are garbage free".
- Caveat 2 — **reuse analysis deliberately breaks this**: "no reuse analysis can preserve the
  garbage-free property!" (Frame-Limited Reuse §4). Drop-guided reuse is only *frame-limited*
  (§4.1). Since every shipping Koka build runs reuse analysis, the garbage-free property
  describes Perceus-the-algorithm, not Koka-the-implementation.
- Caveat 3 — **borrowing breaks it too**: "The resulting programs are not garbage-free, but
  *frame-limited*" (Lorenzen 2021, Abstract).
- Wording: it is the last *reference*, not "dereference", and the freeing point is decided
  statically by ownership, then executed when the count hits zero.

### C5. "When a count reaches zero, the entire subgraph rooted at the object is dead and freed." — **FALSE.**

The specification is a *recursive drop*, not a subgraph free. Perceus §2.3:

```
fun drop( x ) {
  if (is-unique(x)) then drop children of x; free(x)
                    else decref(x)
}
```

Children are **dropped** (their own counts decremented), and each child is freed only if *its*
count reaches zero; children still referenced elsewhere survive. §2.2 describes the same for the
scoped case: `drop(xs)` "decrements the reference count of an object and, if it drops to zero,
recursively drops all children of the object and frees its memory". The runtime mirrors this
(`kk_block_drop_free` recursively decrements children `[deepwiki]`). Two further corrections:
under drop-*reuse* the block is not freed at all but handed back as a reuse token (§2.4), and
under a cycle the count never reaches zero (§2.7.4).

**Correct phrasing:** "When an object's count reaches zero it is freed and its children are
dropped in turn; shared children survive."

### C6. "Pure immutability guarantees an acyclic heap in Koka." — **PARTLY TRUE; false as an unconditional statement about Koka.**

What the paper actually supports (§2.7.4): "In Koka, **almost all** data types are immutable and
either *inductive* or *coinductive*. It can be shown that such data types are never cyclic".
So: immutable (co)inductive data + eager evaluation ⇒ acyclic *for that data*. But Koka the
language does not have an acyclic heap, because:

- It has first-class mutable references, and "mutable references are the main way to construct
  cyclic data" (§2.7.4); "cycles ... can only be created through mutable references"
  (Frame-Limited Reuse §9).
- Koka also has `div type` (arbitrary recursive types) alongside `type`/`co type`, and the
  `hdiv` predicate exists precisely to catch "cases where code can diverge by storing self
  referential functions in the heap" `[deepwiki, on doc/spec]`.
- What *is* guaranteed is a static localization: "it is statically known where cycles can
  possibly be introduced in the code" (§1).

`[Inference]` For A7 the useful reading is the converse: acyclicity is a consequence of
(immutability + inductive types + no mutable cells), not of immutability alone. A language that
adds any owning mutable cell re-opens cycles regardless of how pure the rest is.

---

## What A7 can take without reference counts

The reuse transformation decomposes into five pieces. Four are static; exactly one reads a
count.

**Takeable as-is (no count involved):**

1. **Ownership/borrow discipline.** The λ¹ judgement `Δ | Γ ⊢ e ⇝ e'` — owned variables consumed
   exactly once, borrowed variables inspected but not consumed — is a static derivation
   (Perceus §3.2, Fig. 5/Fig. 8). A7 can adopt it as a checking pass over its AST with no runtime
   representation at all. `[Inference]` This is where "the user never thinks about memory" is
   won or lost: in Koka the discipline is inferred, and the user only sees it when they opt into
   `fip`.
2. **Drop placement.** "Delay `dup` as late as possible, generate `drop` as soon as possible,
   right after a binding or at the start of a branch" (§3.4). Without counts, `dup` disappears
   entirely (nothing may be duplicated) and each `drop` becomes an unconditional free. `[Inference]`
   A7 needs no analog of drop *specialization* (§2.3) — that pass exists only to inline the count
   test.
3. **The reuse pairing itself.** Matching a destructed constructor in a branch with a same-size
   allocation in that branch (§2.4; drop-guided variant, Frame-Limited Reuse §3.2) is a purely
   syntactic, per-branch pairing on a size key. This is the whole idea we want, and it survives
   intact. Prefer the **drop-guided** formulation: run it *after* the ownership pass so it keys
   off the point where a value provably dies, which is what makes it robust to inlining (§3.1
   shows the earlier algorithms breaking under inlining).
4. **Reuse specialization / in-place field update.** `Cons@ru(x,xx)` → assign only the changed
   fields (§2.5), and "we only specialize constructors if at least one of the fields stays the
   same". Static, keyed on which pattern variables are re-used unchanged. Fully takeable.
5. **Borrowing as a count-elimination device** is moot for A7 (`[Inference]`: with no counts
   there is nothing to elide), but borrowing is still needed as a *linearity escape hatch* —
   FP²'s BMATCH/BAPP let a value be inspected without being consumed (§2.2). Inherit Koka's two
   warnings: borrowing keeps values alive longer (peak memory not frame-limited,
   Frame-Limited Reuse §4.2 and App. C.1) and it inhibits reuse and tail calls (thesis §6.4).

**The one piece that needs the count:**

6. **The validity of the reuse token** — `if (is-unique(x)) then &x else NULL` (§2.4), and
   symmetrically `if (is-unique(x)) then free(x) else decref(x)` (§2.3). This is the *only* place
   where Koka reads the header. Everything above compiles to straight-line code; this compiles to
   a branch plus a copying fallback path.

**The replacement already exists and is named.** FP²'s FIP calculus replaces the runtime test
with a static linear resource: destructive match `match!` on an *owned* variable mints a reuse
credit ◊k; a constructor of size k consumes one; credits are size-exact and cannot be split or
merged (§1.1, §2.2, Fig. 4). The paper's own statement of the correspondence: "FIP is exactly
that subset of λ^fip which requires no dynamic reference counting or memory management at
runtime" (§1.5). **`[Inference]` A7's memory model is, essentially, "FIP without the dynamic
fallback": take FP²'s FIP rules as the checking discipline and Perceus's reuse-token codegen as
the lowering, and delete `is-unique` entirely.**

**What A7 must give up by deleting the count — be honest about each:**

- **One function serving both unique and shared callers.** Perceus §5 is explicit that static
  uniqueness "usually also requires writing multiple versions of a function for each case
  (unique- versus shared argument)", and that the dynamic check "is also what enables FBIP to use
  a single function that can be used for both unique or shared objects (since the uniqueness
  property is *not* part of the type)". A7 will either duplicate functions or forbid the shared
  case.
- **Graceful degradation.** Koka's failure mode for a shared argument is a copy at runtime
  (§2.5: copying "exactly the shared *spine*"). A7's failure mode must be a compile error. That
  is a better error but a smaller language.
- **Call-site uniqueness.** FP² §1.4 is the load-bearing warning: the FIP check covers a
  function's *definition*; whether a given *call* may update in place depends on sharing at the
  call site (`append(xs, reverse(xs))`). A7 needs a whole-program or type-level answer here
  (uniqueness/affine types), which Koka deliberately declined to build.
- **Persistence and structure sharing.** Persistent data structures are exactly the case where
  the count pays for itself (`rbtree-ck`, §4). Statically-unique A7 gives them up, or pays for
  explicit copies.
- **Size-exactness must now be a compile-time obligation.** Since there is no runtime NULL
  fallback, a pairing that fails to find a same-size partner is not a slow path but a missing
  optimization (or, under a `fip`-like annotation, an error). Budget for the padding tricks
  Koka's authors needed: padded constructors and atoms (FP² §1.2, §4; thesis §4.6).
- **Not affine, by default.** FP² §2.2: FIP "is not affine: we cannot discard owned variables as
  that implies freeing a potentially heap allocated value". If A7 wants to allow discarding (a
  plain free), it is choosing the weaker `fbip` guarantee, not `fip`.

**What A7 gets for free by having no counts:**

- `[Inference]` The cycle problem disappears rather than being deferred to the programmer as in
  Koka (§2.7.4). Static single ownership makes the heap a forest by construction.
- `[Inference]` The thread-sharing machinery — recursive `tshare` marking, atomic counts,
  sticky counts, the read/write race on `ref` (§2.7.2, §2.7.3) — is all count infrastructure and
  is simply absent. Koka measured up to 59% slowdown when counts must be atomic (§4).
- `[Inference]` The "explicit control flow" prerequisite (§2.7.1) still applies to A7 — any
  non-local exit must be visible to the ownership pass — and A7's existing ban on source
  recursion plus its explicit-stack style is aligned with the FIP restriction to constant stack
  space.

**One design warning to carry forward.** The FBIP contract is a *user-visible discipline*, not a
silent optimization: "Importantly, a programmer can rely on this optimization happening, e.g.
they can see the `match` patterns and match them to constructors in each branch" (§2.6; same
sentence in the Koka book). `[Inference]` A7's goal of "a surface where users never think about
memory" is in direct tension with this. Koka resolves it by making reuse best-effort-and-silent
by default and exact-and-checked only under `fip`/`fbip`. If A7 has no dynamic fallback, it
cannot be silent when the pairing fails — so it needs either a diagnostic mode or an explicit
annotation, i.e. Koka's `fip` keyword by another name.

---

## Sources

All accessed **2026-09-16**.

**Papers (primary; read as PDF)**

- Alex Reinking, Ningning Xie, Leonardo de Moura, Daan Leijen. *Perceus: Garbage Free Reference
  Counting with Reuse*. PLDI '21, pp. 96–111. DOI 10.1145/3453483.3454032.
  PDF: https://xnning.github.io/papers/perceus.pdf
  (MSR extended TR: https://www.microsoft.com/en-us/research/publication/perceus-garbage-free-reference-counting-with-reuse/ ;
  TR v1 PDF: https://www.microsoft.com/en-us/research/uploads/prod/2020/11/perceus-tr-v1.pdf)
  Sections used: §1, §2.2–§2.7.5, §3.1–§3.4, §4, §5, §6.
- Anton Lorenzen, Daan Leijen. *Reference Counting with Frame Limited Reuse*. ICFP '22
  (Proc. ACM Program. Lang. 6, ICFP, Article 103). Microsoft Technical Report MSR-TR-2021-30,
  Mar 15 2022 (v2). DOI 10.1145/3547634.
  PDF: https://www.microsoft.com/en-us/research/wp-content/uploads/2021/11/flreuse-tr.pdf
  Sections used: Abstract, §1, §2.1–§2.2, §3.1–§3.2.1, §4–§4.2, §5–§5.2, §6, §7.1–§7.2, §9,
  App. B, App. C.1–C.3.
- Anton Lorenzen, Daan Leijen, Wouter Swierstra. *FP²: Fully in-Place Functional Programming*.
  ICFP '23 (Proc. ACM Program. Lang. 7, ICFP, Article 198). DOI 10.1145/3607840. Preprint,
  July 2023. PDF: https://www.microsoft.com/en-us/research/wp-content/uploads/2023/07/fip.pdf
  (also https://webspace.science.uu.nl/~swier004/publications/2023-icfp.pdf)
  Sections used: Abstract, §1–§1.5, §2–§2.3, §5–§5.2, §6, §7, §8, App. A.
- Sebastian Ullrich, Leonardo de Moura. *Counting Immutable Beans: Reference Counting Optimized
  for Purely Functional Programming*. IFL '19 (Singapore, Sept 2019); arXiv:1908.05647v3,
  5 Mar 2020. PDF: https://arxiv.org/pdf/1908.05647
  Sections used: Abstract, §1, §2, §4, §5.1–§5.3, §6, §7.2, §8 (Fig. 6, Fig. 7), §9, §10.
- Anton Felix Lorenzen. *Optimizing Reference Counting with Borrowing*. Master's thesis,
  Universität Bonn, 29 Nov 2021 (supervisor: Daan Leijen).
  PDF: https://antonlorenzen.de/master_thesis_perceus_borrowing.pdf
  (also https://antonlorenzen.de/papers/master_thesis_perceus_borrowing.pdf)
  Sections used: Abstract, §1–§1.2, §6.1–§6.5 (Fig. 6.8, Fig. 6.9), §7–§7.3.

**Koka documentation and repository**

- The Koka Programming Language (book): https://koka-lang.github.io/koka/doc/book.html
  — §2.4 "Perceus Optimized Reference Counting", §2.5 "Reuse Analysis", §3.5 "FBIP: Functional
  but In-Place". Source files: `doc/spec/why.kk.md`
  (https://raw.githubusercontent.com/koka-lang/koka/master/doc/spec/why.kk.md — §2.4, §2.5) and
  `doc/spec/tour.kk.md`
  (https://raw.githubusercontent.com/koka-lang/koka/master/doc/spec/tour.kk.md), from which the
  "you can rely on this optimization happening ... pair them to same-sized constructors in each
  branch" sentence is quoted.
- Koka repository: https://github.com/koka-lang/koka — `src/Backend/C/Parc.hs`,
  `src/Backend/C/ParcReuse.hs`, `src/Backend/C/FromCore.hs`, `src/Core/CheckFBIP.hs`,
  `kklib/src/refcount.c`, `kklib/include/kklib.h`, `samples/learn/fip.kk`,
  `test/parc/*.kk.out`. Accessed via `mcp__deepwiki__ask_question` (repoName
  `koka-lang/koka`) — **secondary AI index over the repo**, marked `[deepwiki]` in the text.
- Lean 4 repository: https://github.com/leanprover/lean4 —
  `src/Lean/Compiler/LCNF/ExplicitRC.lean`, `ResetReuse.lean`, `InferBorrow.lean`,
  `src/Lean/Compiler/IR/Basic.lean`, `src/include/lean/lean.h`. Accessed via
  `mcp__deepwiki__ask_question` (repoName `leanprover/lean4`) — **secondary**, `[deepwiki]`.

**Mentioned but not read (do not cite as verified)**

- *Fully-Automatic Type Inference for Borrows with Lifetimes*, OOPSLA 2026,
  https://dl.acm.org/doi/10.1145/3798221 — source of a "75–100% reduction in reference count
  increments" figure for the **Morphic** language, seen only in a search-result summary.
