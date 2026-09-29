> **Source:** Claude research subagent. Primary-source study of Lean 4's reference counting, from Counting Immutable Beans (IFL 2019), the Lean 4 repository, manual, release notes and issue tracker.  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim, including the subagent's `[STATED]` / `[INFERENCE]` / `not found` labels and its note that the paper was read through an ar5iv render rather than the published PDF. User decisions are in the [ledger](../../../decisions.md).

# Lean 4 runtime memory management — deep research for A7

Access date for all sources: **2026-09-16**.

Conventions used throughout:

- **[STATED]** = the cited source says this, quoted or closely paraphrased.
- **[INFERENCE]** = my conclusion from the stated facts; the source does not say it.
- **not found** = I looked and did not find it. I have not filled any gap from memory.
- Line numbers were **not retrieved** for any repository file. The Bash tool's output
  capture is broken in this environment and `WebFetch` strips line numbering, so files are
  cited by path only. Where a path from the task prompt 404s at `master`, I say so.

---

## Summary (5 lines)

1. Lean 4 has **no garbage collector**; it uses **non-atomic-by-default reference counting** with
   compile-time-inserted `inc`/`dec`, borrowed-vs-owned parameter modes, and a `reset`/`reuse`
   transformation that recycles constructor cells — the scheme of *Counting Immutable Beans*
   (Ullrich & de Moura, IFL 2019), confirmed.
2. The **uniqueness decision itself is 0% static**: every `reset` and every in-place primitive
   tests the runtime RC field (`lean_is_exclusive`, i.e. single-threaded *and* `rc == 1`);
   static analysis decides only *where* to try, and *who owns what*.
3. What the counts buy is a **graceful fallback**: when the check fails the program allocates
   instead, so the compiler may speculate about reuse without ever proving uniqueness.
4. Measured (paper Fig. 6, normalized run times; ×-ratios below derived from Fig. 6 geomeans, not
   printed in the paper): without reuse ≈ 1.40× geomean slower and up to
   3.23× on `rbmap`; without the single-threaded RC optimization ≈ 1.52× geomean slower and 2.31×
   on `unionfind`; borrow inference is small and **mixed in sign**.
5. Lean since 2019 has moved **toward more static ownership information, not away from RC and not
   toward a collector**: `@&` borrow annotations (v4.30.0), "ownership annotations" (FRO Y3) and
   "uniqueness annotations" (FRO Y4) are on the roadmap.

---

## 1. What is Lean 4's actual memory scheme? Authors and year. The algorithm.

**Authors and year — confirmed.** [STATED] The arXiv record for 1908.05647 gives the title
*"Counting Immutable Beans: Reference Counting Optimized for Purely Functional Programming"*,
authors **Sebastian Ullrich, Leonardo de Moura**, year **2019**, venue **IFL 2019**
(https://arxiv.org/abs/1908.05647). The full bibliographic record: *Proceedings of the 31st
Symposium on Implementation and Application of Functional Languages*, ACM, 2019, pages 1–12,
**DOI 10.1145/3412932.3412935** (https://ouci.dntb.gov.ua/en/works/ldkjA5Y4/). The Lean repository's
own benchmark README states the "Cross" suite "was created for the paper 'Counting Immutable Beans -
Reference Counting Optimized for Purely Functional Programming' (IFL19)"
(https://github.com/leanprover/lean4/blob/master/tests/bench/README.md).

**The scheme.** [STATED] Abstract: *"We propose a new mechanism for efficiently reclaiming memory
used by nonshared values, reducing stress on the global memory allocator. We describe an approach
for minimizing the number of reference counts updates using borrowed references and a heuristic for
automatically inferring borrow annotations."* The motivating observation is named in §1:
*"We call it the resurrection hypothesis: many objects die just before the creation of an object of
the same kind."*

The algorithm, as the paper structures it (§5, "A compiler from λ_pure to λ_RC"), is three passes
over a pure IR, in this order:

1. **§5.1 Inserting destructive update operations** — the `reset`/`reuse` pair (question 3).
2. **§5.2 Inferring borrowing signatures** — owned vs borrowed parameter modes (question 2).
3. **§5.3 Inserting reference counting operations** — `inc`/`dec` placement.

[STATED] The paper's own framing of why RC and not tracing GC (§1): *"having an exact reference
count of each value can enable optimizations such as destructive updates"*, and (§3) *"We remark
that in Lean and λpure, it is not possible to create cyclic data structures. Thus, one of the main
criticisms against reference counting does not apply."*

**In the shipped compiler today.** [STATED] Reference counting is implemented in the C++/C runtime
in `src/include/lean/lean.h` and `src/runtime/object.cpp`; the compiler passes live in the LCNF
pipeline: `src/Lean/Compiler/LCNF/ResetReuse.lean`, `src/Lean/Compiler/LCNF/ExpandResetReuse.lean`,
`src/Lean/Compiler/LCNF/InferBorrow.lean`, plus the explicit-RC pass (deepwiki search over
`leanprover/lean4`). Note: the task prompt's paths `src/Lean/Compiler/IR/ResetReuse.lean` and
`src/Lean/Compiler/IR/Borrow.lean` both **404 at `master`** on 2026-09-16; the live files are the
LCNF ones. `ResetReuse.lean`'s header reads *"Copyright (c) 2026 Lean FRO, LLC … Authors: Henrik
Böving"* and the file cites the paper by URL (https://arxiv.org/pdf/1908.05647).

[STATED] Object header, from `src/include/lean/lean.h`:

```c
typedef struct {
    int      m_rc;
    unsigned m_cs_sz:16;
    unsigned m_other:8;
    unsigned m_tag:8;
} lean_object;
```

with the comment: *"The reference counter `m_rc` field also encodes whether the object is single
threaded (> 0), multi threaded (< 0), or reference counting is not needed (== 0). We don't use
reference counting for objects stored in compact regions, or marked as persistent."*

[STATED] The manual confirms there is no cycle collection and no tracing GC: *"Because the
verifiable fragment of Lean cannot create cyclic data, the Lean runtime does not have a technique
to detect it."* (https://lean-lang.org/doc/reference/latest/Run-Time-Code/Reference-Counting/)

---

## 2. Borrowed vs owned parameters: inference, and what it saves

**What the modes mean.** [STATED] Paper §2: *"a borrowed reference does not actually keep the
referenced value alive, but instead asserts that the value is kept alive by another, owned
reference."* The runtime comment in the Lean sources states the calling convention precisely:

> *"1- "standard" calling convention if it consumes/decrements the RC. … When this calling
> convention is used for an argument `x`, then it is safe to perform destructive updates to `x` if
> its RC is 1. 2- "borrowed" calling convention if it doesn't consume/decrement the RC, and it is
> the responsibility of the caller to decrement the RC."* (quoted via deepwiki from the Lean
> sources; file path not confirmed by the tool, line numbers not retrieved)

[STATED] User-facing, the manual's FFI chapter: *"Parameters may be marked as borrowed by prefixing
their types with `@&`"*; borrowing *"only affects the ABI and runtime behavior of the function when
compiled or interpreted. From the perspective of Lean's type system, this annotation has no
effect."* For borrowed objects *"the function does not consume the value. This means that the
function will not decrement the value's reference count or deallocate it, and the caller is
responsible for doing so."*
(https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/)

**How inference works.** [STATED] Paper §5.2 gives a fixpoint over a map
`β : Const ⇀ {𝕆, 𝔹}*`, one entry per parameter:

> *"Given δ(c)=λy¯.b, we infer the value of β(c) by starting with the approximation β(c)=𝔹ⁿ, then we
> compute S=collect_𝕆(b), update β(c)ᵢ:=𝕆 if yᵢ∈S, and repeat the process until we reach a fix
> point and no further updates are performed on β(c)."*

with the seeding rule *"We say a parameter x should be owned if x or one of its projections is used
in a reset, or is passed to a function that takes an owned reference."* and the default *"we default
all missing entries to 𝕆."*

[STATED] The shipped pass agrees. `src/Lean/Compiler/LCNF/InferBorrow.lean` — *"This pass is
responsible for inferring borrow annotations to the parameters of functions and join points"* — and
it *"initially assumes all arguments are passed as borrowed and subsequently refines this by marking
parameters as owned as required and propagating the information throughout the program."* The
implementation splits reasons into **forced (correctness)** and **non-forced (performance)**:
forced reasons include *"We preserve tail calls to recursive functions and join points by ensuring
we never have to insert a `dec` after a tail call"* and ensuring *"values which are subject to
reset-reuse are owned so their reference count accurately reflects the real amount of references"*;
non-forced reasons are heuristics (propagating from callees, making constructor arguments owned to
avoid an `inc`). *"performance related heuristics will be ignored if there is a user-defined borrow
annotation."*

**What it saves — the measurement.** [STATED] Figure 6's `-borrow` column (normalized run time,
so >1 means *slower without* borrow inference). Per-benchmark, relative to base:
binarytrees **1.144**, deriv **1.166**, rbmap **1.077**, parser **1.000**, qsort **1.00**,
rbmap_10 1.52 vs base 1.49, const_fold **0.90**, rbmap_1 **4.47** vs base 4.722. The paper's running
text says *"Borrowed inference heuristic provides significant speedups in benchmarks binarytrees
and deriv."*

[INFERENCE] Two rows are **below 1**, i.e. those benchmarks ran *faster with borrow inference
disabled* (const_fold 0.90; rbmap_1 4.47 < 4.722 base). Borrow inference is therefore a modest and
not uniformly positive optimization in the paper's own data, unlike reuse and the single-threaded
RC optimization. Derived geomean ratio ≈ 1.277 / 1.24 ≈ **1.03** — about 3%. (The division is my
arithmetic, not the paper's.)

**Important negative result.** [STATED, verified by a targeted query] The paper reports **no count
or percentage of `inc`/`dec` operations removed** by borrow inference or by any static analysis —
only wall-clock effects. This matters for claim 4 below.

---

## 3. Reuse: how Lean decides to reuse a constructor cell; compile time vs run time

**The instruction pair.** [STATED] Paper §2:

> *"The two instructions are used together; if x is a shared value, then y is set to a special
> reference ⊥, and the reuse instruction just allocates a new constructor value ctor_i w̄. If x is
> not shared, then reset decrements the reference counters of the components of x, and y is set
> to x."*

§4 gives the operational rule `reset-uniq` firing only in the state where the cell's count is 1:
*"⟨reset x,σ⟩⇓⟨l,dec(l′¯,σ[l↦(ctor_i |l′¯|,1)])⟩ when ρ(x)=l and σ(l)=(ctor_i l′¯,1)"*.

**Compile-time part (where to put them).** [STATED] `src/Lean/Compiler/LCNF/ResetReuse.lean`
implements the paper's three functions:

- **R** (`Decl.insertResetReuse`) *"looks for candidates that might be eligible for reuse. For these
  variables it invokes `D`."*
- **D** *"looks for code regions in which the target variable is dead (i.e. no longer read from), it
  then invokes `S`. If `S` succeeds it inserts a `reset` instruction to match the `reuse` inserted
  by `S`."*
- **S** *"looks for allocations where reusing the target variable could be useful and replaces the
  allocation instructions with `reuse` instructions, otherwise fails and returns the code
  unmodified."*

Static side conditions, all checked by the compiler:

- the candidate is a variable scrutinised by a `cases` on a constructor alternative (`.ctorAlt`);
- it is **not already inside a `reset`** (prevents double-reset) and is **not borrowed** — ownership
  comes from `Decl.analyzePropagatedBorrows`, and `InferBorrow` *forces* reset/reuse candidates to
  be owned (see §2 above);
- **layout compatibility** via `mayReuse` (constructor size, usize, ssize);
- the pass runs **twice**: first `relaxedReuse := false` — *"If `relaxedReuse = false`, then we don't
  want to reuse cells from different constructors even when they are compatible because it produces
  counterintuitive behavior"* — then `relaxedReuse := true`, permitting reuse across different
  constructors of the same layout (e.g. `PSigma.mk` / `Prod.mk`); addresses issue #4089.

**Run-time part (whether to reuse).** [STATED] `ExpandResetReuse.lean` lowers the pair into an
explicit hot/cold branch on an `isShared` test; at emission, `reset` tests **`lean_is_exclusive`**:
if exclusive, the fields are released (`lean_ctor_release`) and the cell is handed on for reuse; if
not, the object is `lean_dec_ref`'d and a boxed zero (the ⊥ token) is returned, so the paired
`reuse` allocates fresh. `reuse` tests `lean_is_scalar` on the token to pick reuse vs allocation,
and updates the constructor tag with `lean_ctor_set_tag` when needed.

[STATED] `lean_is_exclusive(o)` is *"true when the object is single-threaded with rc==1"*;
`lean_is_shared(o)` is *"true when the object is single-threaded with rc > 1"* (`lean.h`).

[STATED] The same run-time-test shape applies to in-place primitives, not just reset/reuse. Paper
§7.1: *"We perform destructive updates when the array is not shared. For example, given the array
write primitive Array.write : Array α → Nat → α → Array α the function application Array.write a i v
will destructively update and return the array a if it is not shared."* `Array.uset`'s docstring
says *"The modification is performed in-place when the reference to the array is unique."*

**So, exactly:** compile time decides *placement, ownership and layout compatibility*; run time
decides *uniqueness*. [STATED] A 2025 RFC on the Lean tracker states this plainly:
issue #7374, *"RFC: 'Functional but in place' compiler should recognize when the return object is
equal to the destructed object"* (filed by JovanGerb, 2025-03-07, labelled P-high, assigned to
@zwarich) — the compiler *"performs an `isShared` check. If the input isn't shared, memory is
reused; if shared, a new object is created"*, and the request is that for a structurally identical
return *"the reference count check should not be performed, and the input object should be returned
no matter what."* A hand-written `unsafeCast` version of that optimization measured *stdlib C code
reduced by 3.2%, build instructions decreased by 0.22%*.

[INFERENCE] The existence and priority of #7374 is direct evidence that, as of 2025–2026, **no**
static uniqueness proof exists in Lean that would let even this trivial case skip the RC test.

**What the programmer must do (§6).** [STATED] Reuse is not automatic in the sense of being
layout-oblivious: §6 shows red-black tree `balance_1` creating three constructors while matching two
patterns, so some allocations are unguarded by a `reuse`. The fixes are *inlining* — *"After
inlining, the input value (T B a y b) is reused in the balance_1 code. The final generated code now
contains a single constructor application that is not guarded by a reuse"* — or rewriting the
function's parameters. The paper also offers tooling: *"a simple static analyzer that when invoked
by a developer, checks whether reuse instructions are guarding constructor applications"*, and
optional runtime instrumentation: *"For each let y=reset x instruction, we can optionally emit two
counters that track how often x is shared or not."*

---

## 4. Atomic or non-atomic? Multiple threads? Measured cost?

**Non-atomic by default, atomic on demand, per object.** [STATED] Paper §7.2:

> *"The reference counters are incremented using an atomic fetch and add operation with relaxed
> memory order … When decrementing a reference counter, enforce that decrements from other threads
> are visible before checking if the object should be deleted using a release operation after
> dropping a reference, and an acquire operation before deletion check."*

and the problem that motivates the design: *"memory fences have a significant performance impact
even when only one thread is being executed."* Their answer is a three-way tagging of values:
*"If a value is tagged as single-threaded, we do not use any memory fence for incrementing or
decrementing its reference counter. Persistent values are never deallocated and do not even need a
reference counter."*

[STATED] The invariant that makes the tag sound: *"from persistent values, we can only reach other
persistent values, and from multi-threaded values, we can only reach persistent or multi-threaded
values. There are no constraints on the kind of value that can be reached from a single-threaded
value."* And the transition: *"By default, values are single-threaded, and our runtime provides a
markMT(o) procedure that tags all single-threaded values reachable from o as multi-threaded. This
procedure is used to implement Task.mk f and Task.bind x f."* With the cost noted:
*"task creation is not a constant time operation in our approach because it is proportional to the
number of single-threaded values reachable from x and f."*

[STATED] In the shipped runtime this is the sign of `m_rc` (`> 0` ST, `< 0` MT, `== 0` persistent,
per the `lean.h` header comment quoted in §1); `lean_inc_ref_n` / `dec` branch on it, using
`std::atomic_fetch_sub_explicit` only in the MT case. Lean-level controls, quoted from
`src/Init/System/IO.lean`:

- `Runtime.markMultiThreaded`: *"Marks given value and its object graph closure as multi-threaded if
  currently marked single-threaded. This will make reference counter updates atomic and thus more
  costly."*
- `Runtime.markPersistent`: *"Marks given value and its object graph closure as persistent. This
  will remove reference counter updates but prevent the closure from being deallocated until the end
  of the process!"*
- `Runtime.forget`: *"Discards the passed owned reference. This leads to `a` and any object
  reachable from it never being freed. This can be a useful optimization for eliding deallocation
  time of big object graphs …"*

**Measured cost.** [STATED] Figure 6's `-ST` column disables the single-threaded optimization
(i.e. makes all counts atomic). Normalized run times: binarytrees **1.222**, deriv **1.42**,
const_fold **1.23**, parser **1.68**, qsort **1.13**, rbmap **1.71**, rbmap_10 2.43 (base 1.49),
rbmap_1 8.02 (base 4.722), unionfind **2.31**, geometric mean **1.89** (against base geomean 1.24).
[INFERENCE] Ratio of geomeans ≈ 1.89 / 1.24 ≈ **1.52×**, i.e. roughly a 50%
average slowdown if every count were atomic; worst case in the suite is `unionfind` at 2.31×.

[STATED] The manual states the same design rationale in user-facing terms:
*"Single-threaded reference counts can be updated much faster than multi-threaded reference counts,
and many values are accessed only on a single thread."*

[STATED] The tag is still being tuned in production. PR #15047 (*"perf: mark thunk results as
multi-threaded only when the thunk is"*): *"`lean_thunk_get_core` unconditionally called `mark_mt`
on the forced value, degrading the entire freshly computed result graph to atomic reference counting
even for a thunk that only its owner thread can reach."* Reported effect on one module:
*"-492.6M (-2.76%)"* instructions.

---

## 5. Cycles: possible at all? What happens?

**In the pure fragment: no.** [STATED] Paper §3: *"We remark that in Lean and λpure, it is not
possible to create cyclic data structures. Thus, one of the main criticisms against reference
counting does not apply."* Manual: *"Because the verifiable fragment of Lean cannot create cyclic
data, the Lean runtime does not have a technique to detect it."*

**Outside it: yes, and they leak.** [STATED] A comment in Lean's environment/realization code
warns of exactly this: *"We must ensure that `realizeEnv.localRealizationCtxMap` is not reachable
via `res` (such as by storing `realizeEnv` or `realizeEnv'` in a field or the closure) as `res` will
be stored in a promise in there, creating a cycle."* (quoted via deepwiki from `realizeConst`; file
path and line numbers **not confirmed** by the tool). [STATED] Relatedly, `importModules` with
`leakEnv` uses `unsafe Runtime.markPersistent` on the environment precisely to avoid RC traffic on a
long-lived object graph that survives to process end.

[STATED] There is **no cycle collector and no tracing GC** in Lean 4 (deepwiki search over the
repository; the manual's statement above). If a cycle forms, the counts never reach zero and the
memory is never reclaimed — a leak, bounded by process lifetime.

[INFERENCE] A user can construct a cycle deliberately: `IO.Ref` / `ST.Ref` is a mutable cell
(`lean_ref_object` in the C API), so storing into a ref a closure that captures that same ref closes
a loop that RC cannot break. I did **not** find documentation stating this in user-facing terms —
the manual's framing is about the *verifiable fragment*, which excludes `IO`. Treat the user-level
`IO.Ref` cycle as inference, not as a documented claim.

**Caveat on one piece of evidence I am deliberately not using.** The frequently-cited Zulip thread
"memory leak in server?" (Ullrich: *"There seems to be a shared_ptr cycle, assuming valgrind isn't
lying"*; Ebner: *"I think the module_mgr refactoring accidentally created a cyclic reference"*) is
dated **March 2018** and concerns a C++ `shared_ptr` cycle in the **Lean 3** implementation. It is
evidence that RC cycles bite in practice in this codebase's lineage, but it is **not** evidence
about the Lean 4 runtime object model.

**Overflow, a related failure mode.** [STATED] PR #14838, *"fix: freeze objects when their reference
count overflows"*: the 32-bit count could wrap and corrupt state; now *"the object is now frozen
(treated as persistent) and simply never freed, following the 'sticky' approach used by Koka."*
Measured: *"+0.8/0.6% instructions build overhead on core/Mathlib from the change but no
statistically significant effect on wall-clock."* [INFERENCE] Lean's answer to count overflow is
therefore a deliberate, permanent leak.

---

## 6. Performance evidence, against what baselines

**Setup.** [STATED] §8: *"executed on a PC with an i7-3770 Intel CPU and 16 GB RAM running Ubuntu
18.04, using Clang 9.0.0"*; *"All timings are arithmetic means of 50 runs."*

**Benchmarks.** [STATED] *"deriv and const_fold implement differentiation and constant folding …
rbmap stress tests the red-black tree [implementation from the Lean standard library] … parser is
the new parser … qsort it is the basic quicksort … binarytrees is taken from the Computer Languages
Benchmarks Game … unionfind implements the union-find algorithm."* `rbmap_10` and `rbmap_1` are
*"two variants where we perform updates on shared trees"* — saving the tree after every tenth
insertion, or after every insertion, to *"simulate the behavior of a backtracking search where we
store a copy of the state before each case-split."*

**Figure 6 — ablation of Lean's own features.** [STATED] Caption: *"Lean variant benchmarks,
normalized by the base run time (rbmap for rbmap_*)."* A value > 1 means slower than base.

| benchmark | base | -reuse | -borrow | -ST |
|---|---|---|---|---|
| binarytrees | 1.000 | 0.988 | 1.144 | 1.222 |
| deriv | 1.000 | 1.00 | 1.166 | 1.42 |
| const_fold | 1.00 | 1.64 | 0.90 | 1.23 |
| parser | 1.00 | 1.00 | 1.000 | 1.68 |
| qsort | 1.00 | 1.00 | 1.00 | 1.13 |
| rbmap | 1.000 | 3.23 | 1.077 | 1.71 |
| rbmap_10 | 1.49 | 3.62 | 1.52 | 2.43 |
| rbmap_1 | 4.722 | 5.42 | 4.47 | 8.02 |
| unionfind | 1.000 | 1.411 | 1.000 | 2.31 |
| **geom. mean** | **1.24** | **1.74** | **1.277** | **1.89** |

Transcription note: these cells were read out of the **ar5iv HTML render** of the paper
(two independent queries returned the same values); digits that the render split with `~` have been
normalized to three decimals. They are not read off the published PDF.

[STATED] Running text: *"The results show that the new reset and reuse instructions significantly
improve performance in benchmarks const_fold, rbmap, and unionfind."* and *"Borrowed inference
heuristic provides significant speedups in benchmarks binarytrees and deriv."*

[INFERENCE] Derived geomean ratios against the base column: reuse ≈ 1.74/1.24 ≈ **1.40×**,
single-threaded RC ≈ 1.89/1.24 ≈ **1.52×**, borrow ≈ 1.277/1.24 ≈ **1.03×**. Reuse and the ST
optimization carry the design; borrow inference is marginal on average and negative on two rows.

**Figure 7 — cross-language.** [STATED] Caption: *"Cross-language benchmarks. The measurements
include wall clock time (normalized by the Lean base run time), GC time (in percent, as reported by
the respective compiler), and last-level cache misses (CM, in million per second, as reported by
perf stat)."* Baselines: **GHC 8.8.3, ocamlopt 4.10, MLton 20180207, MLKit 4.4.2, Swift 5.1.1**
(§8 names Haskell, OCaml, Standard ML / MLton / MLKit, and Swift). Reported observations:
*"Lean is 5x as fast as OCaml on const_fold"*; Lean spends *"only 17% of the runtime deallocating
memory, while OCaml spends 90% in the GC"*; on `rbmap_1` Lean *"still outperforms all systems but
MLton."* The abstract's own summary is deliberately modest: *"Our preliminary experimental results
demonstrate our approach is competitive and often outperforms state-of-the-art compilers."*

**Afterwards.** [STATED] Production-side evidence rather than papers: v4.30.0's port of expand
reset/reuse to LCNF *"results in a ~15% decrease in binary size and slight speedups across the
board"*; PR #15047's -2.76% instructions on one module; PR #14838's +0.8/0.6% instruction overhead
for overflow safety. I found **no** post-2019 paper re-measuring *Lean's* scheme against baselines;
the follow-up measurement literature (Perceus PLDI'21, Frame-Limited Reuse ICFP'22, FP² ICFP'23) is
Koka-based. **not found**: a Lean-side successor paper with benchmarks.

---

## 7. Where the model costs most

Ranked by the evidence I could actually cite:

1. **Shared data defeats reuse, and this is the largest effect in the paper's own suite.**
   [STATED] `rbmap_1` costs **4.72×** plain `rbmap` at base, and the paper explains why:
   *"Lean's performance decreases on these two variants since the tree is now a shared value, and
   the time spent deallocating objects increases substantially."* [INFERENCE] Any program whose
   working set is genuinely shared — backtracking search keeping snapshots, memo tables, persistent
   structures held by more than one owner — pays twice: the RC traffic *and* the allocation that the
   failed uniqueness check forces.
2. **Multi-threaded objects.** [STATED] ≈1.52× geomean and 2.31× worst-case if all counts are
   atomic (Fig. 6 `-ST`); and `markMT` is *"not a constant time operation"*, proportional to the
   reachable single-threaded graph at task creation. [INFERENCE — from the definition, not stated]
   Because `lean_is_exclusive` requires **single-threaded AND rc==1**, an object that has been
   marked multi-threaded is *never* exclusive, so it can **never** be reused in place even when it
   is in fact uniquely referenced. Sharing a value with one task therefore permanently disables
   in-place update for it and everything reachable from it. PR #15047 is a concrete instance of this
   hazard biting accidentally, via thunks.
3. **The unremovable runtime check itself.** [STATED] Issue #7374 shows a case where the check is
   provably pointless (the returned object is the destructed object) and is still emitted; removing
   it by hand shrank stdlib C output by 3.2%.
4. **Long-lived graphs.** [STATED] The existence and documented purpose of `Runtime.markPersistent`
   and `Runtime.forget` — *"eliding deallocation time of big object graphs"* — plus `leakEnv` for
   imported environments. [INFERENCE] These are escape hatches admitting that RC's deallocation
   cost and count traffic are unacceptable for the elaborator's largest structures; Lean's answer is
   to stop counting and leak on purpose.
5. **Author-side obligations.** [STATED] §6: library code must sometimes be *rewritten or inlined*
   so that constructor applications are guarded by `reuse`. [INFERENCE] The "users never think about
   memory" property is thus not fully achieved even in Lean: performance-critical data structure
   authors do think about it, with tooling support the paper proposes.

**not found:** a systematic third-party measurement of Lean 4's total RC overhead as a fraction of
runtime (e.g. "X% of instructions are inc/dec"). The paper reports no such fraction either.

---

## 8. Has Lean moved toward or away from this design since 2019?

**Toward it, and toward more static ownership — not away from RC, and not toward a collector.**

[STATED] Evidence, in date order:

- The scheme was re-implemented, not replaced, as the compiler moved from the old IR to **LCNF**.
  v4.30.0 (2026-05-26) *"Ports the C emission pass from IR to LCNF, marking the final step of the
  IR/LCNF conversion and enabling end-to-end code generation through the new compilation
  infrastructure"*, and *"Ports the expand reset/reuse pass from IR to LCNF. In addition it prevents
  exponential code generation unlike the old one. This results in a ~15% decrease in binary size and
  slight speedups across the board."*
- **More user-visible ownership control**, v4.30.0: *"Users can now mark function arguments with
  `(x : @&Ty)` and have the borrow inference preserve these annotations, reducing reference counting
  pressure."*
- **FRO Year 3 roadmap** (August 2025 – July 2026): *"The new code generator will include support
  for stack-allocated objects, ownership annotations, and improved placement of reference-counting
  instructions."*
- **FRO Year 4 Part 1 roadmap** (September 2026 – February 2027): *"Lean features a capable
  optimizing code generator, but essential improvements are still outstanding. Improvements include:
  better performance, stack-allocated objects, recursive join points, uniqueness annotations, and
  better support for array manipulating programs."*
- **Sticky overflow instead of wider counts**, PR #14838, adopting *"the 'sticky' approach used by
  Koka."*
- **Open RFC to elide RC checks statically** in a special case: #7374, P-high.

[STATED] **not found**: any Lean proposal, issue, roadmap item or release note about adding a
tracing garbage collector, a cycle collector, or removing reference counting. deepwiki's search over
the repository found no cycle collector and no GC plans.

[INFERENCE] The trajectory is: keep the counts as the runtime substrate, but push *more* of the
decision statically — ownership annotations (shipped), stack allocation and uniqueness annotations
(still at design stage per the Y4 roadmap text quoted above; a web-search summary added that
implementation is to begin at the start of 2027, **search-snippet, unverified** — I did not find
that date on the roadmap page I fetched). That is the same direction A7
wants to travel, with Lean stopping short of removing the counts.

---

## Claims checked

### Claim: "Lean 4 uses Perceus."

**Verdict: FALSE as stated; your correction is right.**

- [STATED] Perceus is **Koka's** algorithm: *"Perceus: Garbage Free Reference Counting with Reuse"*,
  **Alex Reinking, Ningning Xie, Leonardo de Moura, Daan Leijen**, **PLDI 2021** (Distinguished
  Paper), MSR-TR-2020-42 (Nov 2020). Abstract: *"We show evidence that Perceus, as implemented in
  **Koka**, has good performance and is competitive with other state-of-the-art memory collectors."*
- [STATED] Lean's own compiler cites **Counting Immutable Beans** — `ResetReuse.lean` links
  https://arxiv.org/pdf/1908.05647 and the explicit-RC pass states it is based on that paper. A
  deepwiki search over `leanprover/lean4` found **no mention of "Perceus"** anywhere in source,
  comments or docs. Caveat: a search miss is weaker than a verified exhaustive grep; I could not run
  grep (Bash unusable here). Treat as "no evidence of, and positive evidence against."
- **Chronology** [STATED]: Beans is IFL **2019**; Perceus is TR Nov **2020** / PLDI **2021**.
  De Moura is an author of both.
- **The "influenced" half of your belief**: a web-search snippet of the MSR publication page states
  the Perceus authors *"built on pioneering reference counting work in the Lean theorem prover"* and
  viewed it *"through the lens of language design."* **Caveat:** I could not verify that sentence
  verbatim on any page I fetched — the MSR pages, the PLDI page and the author's page returned only
  the abstract, and every PDF fetch failed to decode. Label it **search-snippet, unverified**.
  The abstract alone does not mention Lean.

Recommended wording for your docs: *"Lean 4 uses the scheme of Counting Immutable Beans (Ullrich &
de Moura, IFL 2019). Perceus (Reinking, Xie, de Moura & Leijen, PLDI 2021) is Koka's later,
formalized descendant of that line of work; Lean does not use or reference it."*

### Claim: "Counting Immutable Beans (Ullrich and Lorenzen, 2019)"

**Verdict: the original was WRONG; your correction to "Ullrich and de Moura" is CONFIRMED.**

[STATED] arXiv 1908.05647 and the ACM record (DOI 10.1145/3412932.3412935, IFL '19, ACM, 2019,
pp. 1–12) both give **Sebastian Ullrich and Leonardo de Moura**. **Anton Lorenzen is not an author.**

[INFERENCE — likely source of the error] Lorenzen authors the *later, Koka-side* papers in this
line: *Reference Counting with Frame Limited Reuse* (**Lorenzen & Leijen**, ICFP 2022,
DOI 10.1145/3547634) and *FP²: Fully in-Place Functional Programming* (**Lorenzen, Leijen &
Swierstra**, ICFP 2023, DOI 10.1145/3607840), plus a master's thesis *Optimizing Reference Counting
with Borrowing*. Confusing those with Beans is an easy slip; keep the two lineages separate in the
docs.

### Claim: "Lean 4: optimized reference counting, in-place mutation allowed if unshared."

**Verdict: TRUE.**

[STATED] Manual: *"Primitive types, such as strings and arrays, may provide operations that copy
shared data but modify unshared data in-place."* Paper §7.1: *"We perform destructive updates when
the array is not shared."* Runtime comment: *"it is safe to perform destructive updates to `x` if
its RC is 1."* Two precisifications worth carrying into your docs: (i) "unshared" operationally
means **`lean_is_exclusive` = single-threaded AND rc == 1**, so a multi-threaded-marked object never
qualifies; (ii) "optimized" specifically means *borrow inference* (fewer inc/dec) + *reset/reuse*
(fewer alloc/free) + *the ST/MT/persistent tag* (no fences in the common case).

### Claim: "Uniqueness is decided by a reference count at run time, sometimes removed by static analysis."

**Verdict: first half TRUE; second half MISLEADING — correct it.**

[STATED] The uniqueness *decision* is made at run time, always: `reset` emits a `lean_is_exclusive`
test (lowered as an `isShared` hot/cold split), and in-place primitives test uniqueness too.
Issue #7374 (P-high, 2025) exists precisely because even a provably-redundant check is not removed.
I found **no** mechanism in Lean that proves uniqueness statically and skips the test.

What static analysis actually removes is **different work**:

- **`inc`/`dec` traffic** — via borrow inference (§5.2 / `InferBorrow.lean`). [STATED] The paper
  reports **no count or percentage** of RC operations elided; only wall-clock ablations, geomean
  ≈3% derived, and negative on two benchmarks.
- **Placement** of reset/reuse — R/D/S decide *where* a reuse is even attempted, and `mayReuse`
  rules out layout-incompatible pairs at compile time.
- **Ownership** — reset/reuse candidates are *forced* owned; borrowed values are excluded
  statically.

Recommended wording: *"Uniqueness is decided by a reference-count test at run time — in Lean this is
never eliminated by static analysis. Static analysis instead decides where to attempt reuse, which
parameters are owned vs borrowed (eliding many inc/dec), and whether counts need to be atomic. When
the run-time test fails, the program allocates instead; the count is what makes that fallback
possible."*

---

## What A7 can take without reference counts

Framing [INFERENCE, but the load-bearing one]: Lean's counts buy exactly one thing that a count-free
design does not get — a **fallback**. `reset`/`reuse` is a *speculation*: the compiler may insert it
wherever placement is legal, without ever proving uniqueness, because the failed case degrades to a
plain allocation and stays correct. A7, with no counts, has no fallback and therefore no right to
speculate: **uniqueness must be a static guarantee, which means the obligation moves into the type
system or an equivalent static discipline.** Note that Lean itself is now walking this road —
"ownership annotations" (FRO Y3) and "uniqueness annotations" (FRO Y4).

Directly transferable (the static half of Lean's design, all citable above):

1. **The reset/reuse *placement* algorithm (R/D/S), unchanged.** Find a `case`-scrutinised value
   whose last read precedes a constructor allocation of compatible layout; pair them. In A7 the pair
   becomes an unconditional in-place rewrite rather than a guarded one — *if* the static discipline
   proves the scrutinee unique at that point.
2. **Layout-compatibility as a first-class predicate** (`mayReuse`: size, pointer count, scalar
   bytes), and Lean's two-tier strictness — same-constructor reuse first, cross-constructor
   same-layout reuse second, the latter being the one Lean found *"counterintuitive"* enough to gate
   behind a second pass. A7 should expose the same conservatism, since cross-constructor reuse is
   where surprising aliasing-of-meaning shows up.
3. **Owned vs borrowed parameter modes, with Lean's exact defaults.** Start every parameter
   **borrowed**, promote to **owned** only when forced. Lean's forced set is a good starting
   specification: a parameter is owned if it (or a projection) feeds a reuse/destructive update, if
   it is passed to an owned position, or if ownership is needed to keep a tail call from needing a
   `dec` after it. In A7 these modes are not an RC optimization but the **ownership transfer
   relation itself**, which A7 needs regardless.
4. **The resurrection hypothesis as the design's justification** — *"many objects die just before
   the creation of an object of the same kind"* — which is exactly why compile-time reuse pays at
   all. It is also A7's argument for prioritizing constructor-cell reuse over general arena work.
5. **The "no counting" tier already exists in Lean** as `m_rc == 0` (persistent/compact-region
   objects): *"We don't use reference counting for objects stored in compact regions, or marked as
   persistent."* [INFERENCE] A7's whole heap is morally that tier — it is worth noting that Lean's
   own fastest path is the one with no counts.
6. **§6's honesty about author obligations**, which A7 should adopt as a feature rather than
   discover as a bug: ship the diagnostic the paper proposes — a checker reporting *which
   constructor applications are not guarded by a reuse* — so that "users never think about memory"
   degrades gracefully into "users who care can see why an allocation happened."

What A7 must supply that Lean does not have:

7. **A static uniqueness/affinity discipline** to replace the run-time test. The nearest published
   target is **FP²** (Lorenzen, Leijen & Swierstra, ICFP 2023): a `fip` keyword that *"statically
   checks that programs like the accumulating reverse function can execute in-place, that is, using
   constant stack space without needing any heap allocation **as long as the arguments are
   unique**"* — note the italicized proviso: even FP² leans on Perceus's runtime counts to
   establish that uniqueness, [STATED via the MSR blog, 2023-09-12] *"by using a compiler-guided
   reference counting algorithm called Perceus, we can reuse objects in place whenever the objects
   are uniquely referenced at runtime."* [INFERENCE] So **no** production system currently delivers
   A7's full combination; A7 must make uniqueness a *checked precondition at the type level*
   (linear/affine parameters, or a `unique`/`iso` mode), and then either reject or explicitly copy
   at the points where Lean would silently fall back. The FP² restrictions worth copying are the
   ones that make the guarantee possible: unboxed tuples, borrowed parameters, and **no general
   lambda expressions**.
8. **A decision about what replaces the fallback.** Lean's failed check costs an allocation; A7's
   options are (a) a compile error, (b) an inserted explicit copy, or (c) a mode annotation the user
   must write. [INFERENCE] Given A7's "users never think about memory" goal, (b) with an opt-in
   diagnostic is the only one consistent with the stated goals — and note that A7's existing
   no-recursion rule already removes one of the hardest cases for static reuse analysis (unbounded
   recursive structures whose sharing is not locally apparent).

What A7 avoids by having no counts, per the evidence above: the ≈1.52× atomic-RC cliff and the
`markMT` graph walk (§4/§7); the never-exclusive-once-shared trap (§7.2 inference); count overflow
and its sticky-leak workaround (PR #14838); cycle leaks through mutable cells (§5); and the
permanent inability to reuse genuinely-unique-but-marked-shared objects.

---

## Sources

All accessed **2026-09-16**.

**Primary — the paper**

- Ullrich, S. & de Moura, L. *Counting Immutable Beans: Reference Counting Optimized for Purely
  Functional Programming*. IFL 2019. arXiv abstract: https://arxiv.org/abs/1908.05647 ;
  full text read via the ar5iv HTML render: https://ar5iv.labs.arxiv.org/html/1908.05647 ;
  PDF (fetched but not machine-readable in this environment): https://arxiv.org/pdf/1908.05647
  **Revision caveat:** the rendered text cites GHC 8.8.3, ocamlopt 4.10 and Clang 9.0.0, which
  postdate an August 2019 v1, so ar5iv is showing a **later arXiv revision** (presumably the one
  revised for the ACM proceedings), not necessarily the IFL 2019 submission text.
  Sections cited: §1 (resurrection hypothesis, motivation), §2 (reset/reuse informal semantics,
  borrowed refs), §3 (no cyclic data in Lean/λpure), §4 (reset-uniq rule), §5.1–5.3 (the three
  passes), §5.2 (borrow fixpoint), §6 (data structures for reuse), §7.1 (values, destructive array
  update), §7.2 (thread safety, markMT, invariants), §8 (evaluation, Figs. 6 & 7), §9–10 (related
  work, conclusion).
- Bibliographic record (ACM, DOI 10.1145/3412932.3412935, 2019, pp. 1–12):
  https://ouci.dntb.gov.ua/en/works/ldkjA5Y4/
  (dblp was unreachable — the record page returned an Anubis anti-bot interstitial.)
- Appendix, listed but not fetched (PDF): https://lean-lang.org/papers/beans_appendix.pdf

**Primary — Lean 4 repository and manual**

- `src/include/lean/lean.h` (object header, `m_rc` encoding, `lean_is_st/mt/persistent/exclusive/
  shared`, `lean_inc_ref_n`, `lean_dec_ref`):
  https://raw.githubusercontent.com/leanprover/lean4/master/src/include/lean/lean.h — and
  https://github.com/leanprover/lean4/blob/master/src/include/lean/lean.h
- `src/Lean/Compiler/LCNF/ResetReuse.lean` (R/D/S, `mayReuse`, `relaxedReuse`, cites the paper):
  https://raw.githubusercontent.com/leanprover/lean4/master/src/Lean/Compiler/LCNF/ResetReuse.lean
- `src/Lean/Compiler/LCNF/InferBorrow.lean` (initially-borrowed default, forced vs non-forced owning
  reasons): https://raw.githubusercontent.com/leanprover/lean4/master/src/Lean/Compiler/LCNF/InferBorrow.lean
- `src/Lean/Compiler/LCNF/ExpandResetReuse.lean`, `src/Lean/Compiler/IR/EmitLLVM.lean`,
  `src/runtime/object.cpp`, `src/runtime/io.cpp`,
  `src/Init/System/IO.lean` — located and quoted **via deepwiki** (`mcp__deepwiki__ask_question`,
  repo `leanprover/lean4`), not fetched directly; line numbers not retrieved.
  **Note:** the paths `src/Lean/Compiler/IR/ResetReuse.lean` and `src/Lean/Compiler/IR/Borrow.lean`
  **404 at `master`** as of this date; the live implementations are the LCNF files above.
  The `inc`/`dec` insertion pass is referred to by deepwiki only as `explicitRc` — **its file path
  was not confirmed**, and `src/Lean/Compiler/IR/RC.lean` also **404s at `master`**.
- Manual, *Reference Counting*:
  https://lean-lang.org/doc/reference/latest/Run-Time-Code/Reference-Counting/
- Manual, *Foreign Function Interface* (`@&`, owned vs borrowed, `b_lean_obj_arg`):
  https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/
- Release notes v4.30.0 (LCNF C emission, expand reset/reuse port, user borrow annotations):
  https://lean-lang.org/doc/reference/latest/releases/v4.30.0/
- Benchmarks README ("Cross" suite, created for IFL19):
  https://github.com/leanprover/lean4/blob/master/tests/bench/README.md
- PR #15047, thunk results marked MT only when needed:
  https://github.com/leanprover/lean4/pull/15047
- PR #14838, freeze objects on RC overflow (Koka's "sticky" approach):
  https://github.com/leanprover/lean4/pull/14838
- Issue #7374, RFC on eliding the reuse RC check for identical returns:
  https://github.com/leanprover/lean4/issues/7374
- Lean FRO roadmaps — Year 3 (Aug 2025–Jul 2026): https://lean-lang.org/fro/roadmap/y3/ ;
  Year 4 Part 1 (Sep 2026–Feb 2027): https://lean-lang.org/fro/roadmap/y4-1/

**Adjacent / follow-up work (Koka lineage)**

- Reinking, A., Xie, N., de Moura, L. & Leijen, D. *Perceus: Garbage Free Reference Counting with
  Reuse*. PLDI 2021, Distinguished Paper. https://pldi21.sigplan.org/details/pldi-2021-papers/7/Perceus-Garbage-Free-Reference-Counting-with-Reuse
  ; MSR: https://www.microsoft.com/en-us/research/publication/perceus-garbage-free-reference-counting-with-reuse/
  ; author page: https://alexreinking.com/papers/perceus-garbage-free-reference-counting-with-reuse.html
  (PDF at https://xnning.github.io/papers/perceus-tr.pdf could not be decoded by the fetch tool.)
- Lorenzen, A. & Leijen, D. *Reference Counting with Frame Limited Reuse*. ICFP 2022,
  DOI 10.1145/3547634. https://dl.acm.org/doi/10.1145/3547634
- Lorenzen, A., Leijen, D. & Swierstra, W. *FP²: Fully in-Place Functional Programming*. ICFP 2023,
  DOI 10.1145/3607840. https://dl.acm.org/doi/10.1145/3607840 ; MSR blog (2023-09-12, quoted):
  https://www.microsoft.com/en-us/research/blog/fp2-fully-in-place-functional-programming-provides-memory-reuse-for-pure-functional-programs/
- Koka documentation (Perceus, FBIP, reuse analysis; no mention of Lean found):
  https://koka-lang.github.io/koka/doc/book.html

**Used only with an explicit caveat**

- Zulip archive, "memory leak in server?" (March **2018**, **Lean 3** C++ `shared_ptr` cycle):
  https://leanprover-community.github.io/archive/stream/113488-general/topic/memory.20leak.20in.20server.3F.html

**Tooling caveats affecting this report**

- The Bash tool was unusable (output capture broken; `mkdir` returned exit 2), so no `grep` over a
  local checkout was possible and **no line numbers** were obtained.
- Every PDF fetched (arXiv, Perceus TR, lean4.pdf system description) returned undecodable
  compressed streams; the paper was therefore read through the ar5iv HTML render, and Figure 6's
  cells are a transcription of that render (cross-checked by two independent queries).
- Repository file contents quoted via deepwiki are AI-summarized retrievals of the repo, not direct
  file reads; where that is the only provenance I have said so.
