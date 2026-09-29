> **Source:** Claude research subagent. Primary-source study of Roc's memory management at repository HEAD `a49a16f`, from the language reference, `design.md`, the LIR passes, the builtins and the platform and glue documentation.  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim, including the subagent's `[SOURCE]` / `[DEEPWIKI]` / `[INFERENCE]` labels. Roc is pre-0.1 and its compiler was rewritten from Rust to Zig, so paths and behavior move quickly. User decisions are in the [ledger](../../../decisions.md).

# Roc's memory management — primary-source research

Access date: 2026-09-16. Repository HEAD at time of research:
`a49a16f41e0f5be4436da853995a58381af7a2e9` (Richard Feldman, 2026-09-16,
"Merge pull request #11423 …"), via
<https://api.github.com/repos/roc-lang/roc/commits?per_page=1>.
Published tags at that time: `nightly`, `langsrv`, `alpha4-rolling`,
`alpha3-rolling`, `0.0.0-alpha2-rolling`
(<https://api.github.com/repos/roc-lang/roc/tags>). The builtin docs site is
labelled `alpha4`. Roc's compiler was rewritten from Rust to Zig, so file
paths differ sharply between the historical (`crates/compiler/...`) and
current (`src/...`) trees; both are cited below and labelled.

Sourcing convention used here: **[SOURCE]** = quoted or paraphrased from a file
or page I fetched directly. **[DEEPWIKI]** = stated by the DeepWiki AI index of
`roc-lang/roc`, not verified against the raw file. **[INFERENCE]** = my
reasoning, not a source claim. "Not found" means I looked and did not find it.

---

## Summary (5 lines)

1. Roc has no GC and no ownership types: heap values (`Str`, `List`, `Box`,
   recursive tag unions) are **atomically reference-counted**, with all
   `incref`/`decref`/`free` statements inserted in exactly one compiler stage,
   "LIR ARC insertion".
2. Mutation is *opportunistic*: the Perceus "functional-but-in-place" rule —
   update in place when the refcount is 1, otherwise shallow-clone and update
   the clone — so the test is **dynamic by default, statically elided where a
   whole-program borrow/born-unique analysis proves uniqueness**.
3. Roc infers borrowed vs owned parameters interprocedurally
   (`src/lir/arc_solve.zig`) — the borrow-inference family its own historical
   passes cite (Perceus, frame-limited reuse); cycles are impossible *by
   language design*, which is why plain RC suffices.
4. The platform (host) boundary is an explicit ownership contract: the host
   supplies `roc_alloc`/`roc_dealloc`/`roc_realloc` and must `decref` every
   refcounted value Roc hands it, `incref` anything it stores; generated glue
   carries the layout/ownership rules so hosts never hand-roll them.
5. Roc is pre-0.1 ("not ready for a 0.1 release yet"); no plan to drop RC was
   found, only to make more data refcount-inert (static constant aggregates).

---

## 1. What is Roc's memory scheme today, and where are inc/dec inserted?

**Reference counting, no tracing GC.** [SOURCE]
`docs/langref/expressions.md`:

> "Heap-allocated Roc values are automatically reference-counted (atomically,
> for thread-safety)."

Only strings, lists, boxes and recursive tag unions are refcounted; numbers,
records, tuples and non-recursive tag unions are stack-allocated and not
refcounted (same file).
<https://github.com/roc-lang/roc/blob/main/docs/langref/expressions.md>

**Where the counts are inserted.** [SOURCE] `design.md` (repo root):

> "Static ownership reasoning lives in exactly one place: LIR ARC insertion.
> ARC insertion computes a whole-program borrows-with-lifetimes solution and
> emits explicit RC statements from it."

and

> "Backends do not reason about reference counting. They lower and execute the
> explicit LIR `incref`, `decref`, and `free` statements emitted before backend
> code generation."

The pipeline for both lowering strategies (`.lss` lambda-set-specializing and
`.boxy` boxing) ends `… -> LIR -> ARC insertion -> backend, interpreter, or
LirImage`. <https://github.com/roc-lang/roc/blob/main/design.md>

**The passes.** [SOURCE] `src/lir/mod.zig` pass list (one-line comments
verbatim): `Arc` — "ARC borrow inference and RC statement insertion over
explicit LIR"; `ArcSig` — "ARC-stage per-proc ownership signatures";
`ArcSolve` — "ARC borrow-inference solver over ownership-neutral LIR";
`ArcCertify` — "Debug borrow certifier for ARC-complete LIR";
`ArcDismantle` — "Field takes from dying aggregates, solved between ARC borrow
inference and RC statement emission"; `BoxReuse` — "Direct boxed update wrapper
rewrite before ARC"; `Trmc` — "Tail recursion modulo constructor + plain
tail-call elimination".
<https://github.com/roc-lang/roc/blob/main/src/lir/mod.zig>

**Runtime primitives.** [SOURCE] `src/builtins/utils.zig` defines
`increfRcPtr(ptr_to_refcount: *isize, amount, atomicity, roc_ops)` and
`decrefRcPtr(...)`, with

```zig
const RC_TYPE: Refcount = .atomic;
pub const RcAtomicity = enum(u1) { atomic, single_thread };
```

documented as: "How a refcount update is performed. `atomic` is always sound;
callers pass `single_thread` only for allocations the compiler proved no other
thread can ever touch." Atomic updates use `@atomicRmw(isize, …, .Add, …,
.monotonic)`; single-thread updates are a plain load/store.
<https://github.com/roc-lang/roc/blob/main/src/builtins/utils.zig>

---

## 2. Opportunistic in-place mutation: static, dynamic, or both?

**Both.** [SOURCE]

*Dynamic half* — `design.md`: "Runtime mutation still uses `refcount == 1` to
decide whether in-place mutation is allowed." `src/builtins/utils.zig`:

```zig
pub inline fn rcUnique(refcount: isize) bool { … return refcount == 1; … }
```

and `isUnique(bytes_or_null, *RocOps) bool` — "Determines if a data pointer has
a unique reference (refcount = 1). Returns true for null pointers (they're
conceptually uniquely owned)."

*Static half* — `src/lir/arc_solve.zig` header comment:

> "After signatures settle, unique returns solve to a fixpoint with the
> born-unique analysis: a proc's return is unique when every `ret` returns a
> born-unique value surviving to the return with no other holder, and a
> direct-call result of a unique-returning callee is itself a unique birth in
> its caller."

[DEEPWIKI] The static result is handed to builtins as a `unique_args` bitmask on
`LIR.AssignLowLevel` (with `LowLevel.RcEffect.may_runtime_uniqueness_check_args`),
letting the builtin take the in-place path *without* the runtime refcount load;
I did not verify those field names against the raw file.

**Runtime representation.** [SOURCE] `src/builtins/utils.zig`: the refcount is
an `isize` word stored immediately *before* the data — `isUnique` masks the
pointer's low tag bits and reads `(isizes - 1)[0]`. A sentinel marks immortal
data:

```zig
pub const REFCOUNT_STATIC_DATA: isize = 0;
```

> "Special refcount value that marks data with whole-program lifetime. When a
> refcount equals this value, it indicates static/constant data that should
> never be decremented or freed."

`rcConstant(refcount)` tests for it, and `increfRcPtr`/`decrefRcPtr` skip
constants entirely — i.e. string/array literals cost nothing at runtime. Debug
builds additionally poison freed refcount slots (`POISON_VALUE`) to catch
use-after-free. [DEEPWIKI] small `RocStr` values are stored inline and are
always "unique" because they have no heap allocation; `RocList`/`RocStr` carry
a `capacity_or_alloc_ptr` word whose low bit tags a seamless slice (not verified
against the raw file, though the seamless-slice concept is confirmed by
`src/glue/README.md` and the builtin docs — see §7 and §3).

---

## 3. "Functional but in-place", and what users are told

[SOURCE] `docs/langref/expressions.md`, section *Opportunistic Mutation*:

> "Roc's compiler does _opportunistic mutation_ using the [Perceus](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/11/perceus-tr-v4.pdf)
> \"functional-but-in-place\" reference counting system."

> "Builtin operations on reference-counted values will update them in place when
> their reference counts are 1. When their reference counts are greater than 1,
> they will be shallowly cloned first, and then the clone will be updated and
> returned."

The same file frames the surface guarantee (section *Value Identity*):

> "Roc treats memory addresses as behind-the-scenes implementation details that
> should not affect program behavior, and by design exposes no language-level
> way to access or compare addresses."

**How much the user has to know.** The user-facing *tutorial*
(`docs/mini-tutorial-new-compiler.md`, which `roc-lang.org/tutorial` now
redirects to, HTTP 302) does **not** mention memory, allocation, reference
counting, garbage collection, performance, or in-place mutation at all
[SOURCE]. It only teaches `var`/`$` reassignment: "Unlike a _constant_, a `var`
like `$num` can be reassigned."

But the *builtin API docs* do tell users about in-place behaviour [SOURCE],
<https://www.roc-lang.org/builtins/alpha4/List/> (version label "alpha4"),
`List.keep_if`:

> "always returns a list that takes up exactly the same amount of memory as the
> original, even if its length decreases… If given a unique list,
> [`List.keep_if`] will mutate it in place to assemble the appropriate list. If
> that happens, this function will not allocate any new memory on the heap."

and the capacity family is user-visible: `List.with_capacity` ("Create a list
with space for at least capacity elements"), `List.reserve`,
`List.release_excess_capacity` ("Shrink the memory footprint of a list such that
it's capacity and length are equal. Note: This will also convert seamless slices
to regular lists."). `Str.reserve`/`Str.with_capacity` docs are explicitly
performance advice: "This is a performance optimization tool…", "giving
with_capacity a higher value than ends up being necessary can help prevent
reallocation and copying—at the cost of using more memory than is necessary."
(<https://www.roc-lang.org/builtins/alpha4/llms.txt>)

[SOURCE, secondary] Richard Feldman, Changelog Interviews #645
(<https://changelog.com/podcast/645>): "if you're just using Roc and you're doing
application development, it just feels like a garbage collected language, except
that there's no concept of a GC pause"; on the runtime test, "at runtime, we look
at the reference count, and we're like okay, if the reference count is one, guess
what? Nobody else is observing this thing"; and on tuning, when performance
suffers you rewrite "in this slightly different way instead of this way, and
it'll be totally fine."

Not found: any dedicated user-facing "performance guide" or "memory model" page
on roc-lang.org beyond the langref section quoted above; `docs/langref/README.md`
itself says "This is heavily WIP!".

---

## 4. Borrowing / non-owning access, and borrow inference

Roc has **no user-visible borrow syntax**; borrowing is entirely an internal
inference. [SOURCE] `src/lir/arc_solve.zig` top-of-file doc comment:

> "ARC borrow inference over ownership-neutral LIR.
>
> Solving runs before RC statement emission and decides, for every refcounted
> local, whether its binding is owned (it carries exactly one ownership unit
> that emission must move or release) or borrowed (it is an alias into another
> value and emits no RC statements at all), and for every proc, its ownership
> signature: which refcounted parameter positions are borrowed and whether the
> return borrows from parameters."

> "Signatures solve interprocedurally in two phases. Phase A uses exact reverse
> dependencies to take parameter modes to a fixpoint with returns
> pessimistically owned: parameters start borrowed and flip to owned when any
> occurrence demands a unit, so every parameter bit is queued at most once.
> Phase B then marks returns borrowed when every returned value is a borrow
> anchored on a borrowed parameter, and re-solves binding modes so callers may
> borrow such results."

A binding is borrowed when "its single defining statement is borrow-capable: a
payload read (`assign_ref` with `.field`/`.tag_payload`/`.tag_payload_struct`),
a local alias … a low-level op whose `RcEffect.result_borrows_args` names
exactly one refcounted argument, or a call whose return borrows exactly one
refcounted argument".

**Historical note (old Rust compiler).** [SOURCE]
`crates/compiler/mono/src/borrow.rs` at tag `0.0.0-alpha2-rolling` ran the dual
fixpoint — "all functions initially own all their parameters" and "through a
series of checks and heuristics, some arguments are set to borrowed when that
doesn't lead to conflicts". The direction was inverted in the Zig rewrite
(parameters now start *borrowed* and flip to owned).
<https://github.com/roc-lang/roc/blob/0.0.0-alpha2-rolling/crates/compiler/mono/src/borrow.rs>

**Relative to Lean/Koka:** the Roc side is documented above; I did **not**
research Lean 4 or Koka in this task, so I make no claim about them beyond the
citation trail in §6 (Roc's own passes cite the Koka/Lean papers).

---

## 5. Cycles

[SOURCE] `docs/langref/expressions.md`, section *Reference Cycles*:

> "By design, Roc has no way to express reference cycles, so none of these
> solutions are necessary."

The "solutions" referred to are tracing GC and weak references. The mechanism is
the absence of mutable references/pointers plus semantic immutability, per the
*Value Identity* quote in §3. [DEEPWIKI] mutually recursive *functions* are
allowed at module top level, which is distinct from a data cycle.

[INFERENCE] This is the load-bearing design decision that makes plain
(non-tracing, non-cycle-collecting) RC total for Roc: the cycle problem is
removed at the language level rather than solved at the runtime level.

---

## 6. Reset and reuse

**Historically yes — a full Koka/Lean-style reuse pipeline; today, narrower.**

*Old Rust compiler* [SOURCE], tag `0.0.0-alpha2-rolling`:
- `crates/compiler/mono/src/reset_reuse.rs` — "Implementation based of Reference
  Counting with Frame Limited Reuse",
  <https://www.microsoft.com/en-us/research/uploads/prod/2021/11/flreuse-tr.pdf>;
  header credit: "This program was written by Jelle Teeuwissen within a final
  thesis project of the Computing Science master program at Utrecht University
  under supervision of Wouter Swierstra".
- `crates/compiler/mono/src/drop_specialization.rs` — "Implementation based of
  Drop Specialization from Perceus: Garbage Free Reference Counting with Reuse",
  <https://www.microsoft.com/en-us/research/uploads/prod/2021/06/perceus-pldi21.pdf>;
  same authorship header.

*Current Zig compiler* [SOURCE]: both ideas survive, under different names and in
narrower forms.

- **Reuse** = `src/lir/box_reuse.zig`, "Rewrites direct allocation-replacement
  wrappers to reuse an existing allocation when the LIR shape carries enough
  explicit information." It runs "after SolvedLirLower/TRMC and before ARC
  insertion" and "only accepts a straight-line shape" — `box_unbox` → `produce`
  → `box_box` → `ret`, rewritten to `box_prepare_update` + pointer load/store.
  A second matcher exists for erased callables: "Fuse a discarded
  erased-callable pack into the same-shape pack that replaces it, so the second
  pack reuses the first pack's allocation instead of allocating fresh."
- **Drop specialization** = `src/lir/arc_dismantle.zig`, "Field takes from dying
  aggregates":

  > "A payload read pays a retain whenever its result must be owned, because the
  > container keeps its stored unit. When the container itself is about to die,
  > that retain is the difference between mutating in place and copying: the
  > read result carries count 2 into the mutation's runtime uniqueness check.
  > This analysis finds containers whose whole life is being read field-by-field
  > and then dying, and marks their consuming reads as takes: the read consumes
  > the container's stored unit for that field, and the container is dismantled
  > instead of released whole."

  It runs "in the ARC stage against the solved binding modes rather than inside
  the mode fixpoint" and is "deliberately demand-driven". The rules live in
  `design.md`'s "Field Takes From Dying Aggregates".

I found **no** general Koka/Lean-style `reset`/`reuse` token pass (freeing a
constructor and handing its allocation to an unrelated later constructor) in the
`src/lir/mod.zig` pass list; the two passes above are pattern-matched special
cases. Not found: a design note saying whether the frame-limited-reuse pass is
intended to return. [INFERENCE] The rewrite traded a general reuse transformation
for narrow structural rewrites plus a stronger static borrow/uniqueness solver —
the "Roc = Koka's reuse" equation is historically true and currently only partial,
though the *motivation* is explicit in `arc_dismantle.zig`: avoid the retain that
would push a dying container's field to count 2 and force a copy.

---

## 7. The platform boundary (closest analogue to A7's native descriptor problem)

**Shape of the boundary.** [SOURCE] `docs/langref/platforms.md`:

> "Every Roc application is built on exactly one _platform_, and that platform
> (not Roc's standard library) provides all of the application's I/O primitives."

> "Host authors implement not only the platform's I/O primitives, but also
> functions for memory allocation and deallocation. In C terms, the host
> provides [`malloc` and `free`] implementations which the compiled Roc
> application will automatically call whenever it needs to allocate or
> deallocate memory."

> "The Roc application compiles down to a C library which the platform can
> choose to call (or not)." … "the host, not the Roc application, … starts
> running first. In C terms, the host implements `main()`".

**The ABI vtable.** [SOURCE] `src/builtins/host_abi.zig`:

```zig
pub const RocOps = extern struct {
    env: *anyopaque,
    roc_alloc:  *const fn (*RocOps, usize, usize) callconv(.c) ?*anyopaque,
    roc_dealloc:*const fn (*RocOps, *anyopaque, usize) callconv(.c) void,
    roc_realloc:*const fn (*RocOps, *anyopaque, usize, usize) callconv(.c) ?*anyopaque,
    roc_dbg:    *const fn (*RocOps, [*]const u8, usize) callconv(.c) void,
    roc_expect_failed: *const fn (*RocOps, [*]const u8, usize) callconv(.c) void,
    roc_crashed:*const fn (*RocOps, [*]const u8, usize) callconv(.c) void,
    hosted_fns: HostedFunctions,
};
```

Documented host obligations in the same file: `roc_alloc` — "A host that cannot
provide a non-null pointer (e.g. due to OOM) must not return a real pointer";
`roc_dealloc` — "The length is not provided, because seamless slices make it
unknown at runtime"; `roc_crashed` — "The host must stop execution of the Roc
program and not return to it"; and the refcount rule: "Roc transfers ownership
of refcounted arguments to hosted functions. A host function must decref each
owned refcounted argument when done with it."

**Ownership transfer rules.** [SOURCE] `src/compile/README.md`:

> "Refcounted values that Roc returns to the host (a `RocStr`, `RocList`, or
> `RocBox` written through `ret_ptr`; or any of those passed as arguments to
> your hosted functions) are **heap-owned by the host**. The interpreter does
> not auto-tear-down on `eval` return—that's intentional, since embedders
> frequently want to inspect the return value before freeing it."

> "The host must explicitly `decref` returned refcounted values when done.
> Without this, host allocator leak-checking will report leaks…"

The idiomatic Zig pattern shown is `defer result_str.decref(&my_roc_ops);`. For
arguments, "the host owns each `*RocStr` … for the call's duration" and must
`incref` before storing a value beyond the call.

**Why hand-rolled bindings are rejected.** [SOURCE] `src/glue/README.md`:

> "The Roc platform ABI is not just a collection of structs that can be copied
> by hand into C, Zig, or Rust. Host-visible values carry target-specific
> layout, ownership, and refcounting contracts."

Its enumerated hazards include: compiler-committed field order/padding/
discriminants and pointer-width differences; "`Str`, `List`, `Box`, and erased
callables have runtime allocation headers and ownership rules that are not
visible from the Roc source type alone"; "lists of refcounted elements need
different allocation metadata and teardown than lists of plain bytes";
"**seamless slices do not necessarily point at the allocation base that must be
retained or released**"; "hosted functions receive owned refcounted arguments,
and Roc-provided functions return owned refcounted values"; "recursive
refcounted data requires compiler-derived retain/release plans"; erased
callables need "a specific call ABI, capture teardown callback, and host/runtime
context". Conclusion: "platform code should consume generated glue instead of
hand-rolling Roc ABI bindings." Generated helpers must cover "retain, release,
and recursive teardown for refcounted public types" and "explicit ownership
transfer for hosted arguments, provided returns, stored values, and values
returned back to Roc".

On threads, the same README's runtime matrix line reads: "Thread-aware contracts
where supported, plus explicit documentation of host-visible value sharing
requirements" and notes that "current glue hosts are single-threaded".

[DEEPWIKI] The glue generators additionally emit `offsetof`/`static_assert`-style
size/alignment/offset assertions for 32- and 64-bit targets, and
`zig build run-check-glue-abi` compiles generated glue against the canonical
builtins to enforce the committed ABI; getting refcounts wrong on the host side
yields leaks or double-frees (e.g. releasing a container's elements while the
Roc caller still holds the container). Not verified against raw files.

[SOURCE, arena] `docs/langref/platforms.md` states a platform may use arena
allocation, where memory from completed requests "is freed as a batch operation
rather than individually", making allocations "about as cheap as stack
allocations, and deallocations are essentially free". [INFERENCE] Because
`roc_dealloc` is host-supplied, an arena host can make `free` a no-op. The
`decref` obligation is unchanged by that choice — it is about refcount balance,
not about returning memory — but its *failure mode* softens: a missed decref
under an arena leaves a stale count and leak-checker noise rather than unreclaimed
memory, since the arena reset reclaims everything anyway. A missed decref on a
conventional allocator host is a real leak, and an excess decref is a
use-after-free either way.

---

## 8. Performance evidence

Strongest published measurement: **Jelle Teeuwissen, "Reference Counting with
Reuse in Roc", MSc thesis, Utrecht University** (supervisor Wouter Swierstra).
Authorship is confirmed *primary-source* by the file headers of
`reset_reuse.rs`/`drop_specialization.rs` quoted in §6. The thesis landing page
(<https://studenttheses.uu.nl/handle/20.500.12932/44634>) and its PDF returned
HTTP 403 to my fetches; the abstract text below is from a search-result snippet,
**not** a fetched document:

> "…compare the previous Counting Immutable Beans implementation to an extended
> version of Perceus with drop guided reuse. The new implementation decreases
> reference counting overhead, increases memory reuse, and is competitive with
> functional programming languages that use tracing garbage collection."

Caveats: (a) snippet-level sourcing, not verified against the PDF; (b) it
measures the *old Rust compiler's* passes, which the Zig rewrite has not
reproduced in full (§6); (c) the "1.6×" and ">2×" figures circulating in search
results belong to the **Koka** frame-limited-reuse paper
(<https://www.microsoft.com/en-us/research/wp-content/uploads/2021/11/flreuse-tr.pdf>),
not to Roc.

Secondary, qualitative, and dated (2022, pre-rewrite): Eric Newbury, Test Double,
2022-02-15 — "Benchmark testing of Roc at this point has shown that it can be
almost as fast as C++, and it's been shown that it's faster than Go on some
benchmarks" (<https://testdouble.com/insights/super-performant-new-roc-language>);
no numbers, no linked benchmark. A 2022-02-19 write-up of a Feldman talk
(<https://systemhalted.in/2022/02/19/roc-lang-talk-richard-feldman/>) records the
design claim "Static In-place Detection, so this can be done at Compile time
rather than runtime" but no measurements.

[DEEPWIKI] The repo carries regression-style performance guards rather than a
public benchmark suite — e.g. `ci/check_str_eq_same_allocation.sh` uses
`valgrind --tool=callgrind` to assert that same-allocation string equality does
not scale with length (budget: 4,000,000 instructions of growth between a 4 KB
and 68 KB string), a `-Dtrace-refcount=true` interpreter flag, and
`src/eval/test/host_effects_tests.zig` asserting zero live allocations after
expressions. Not verified against raw files.

Not found: any first-party, published, numeric benchmark of Roc runtime
performance versus other languages on roc-lang.org. Caution: the widely cited
"35ms incremental rebuilds" from 2026 rewrite coverage is **compile** time, not
program runtime.

---

## 9. What the model makes hard; candid statements about RC's costs

[SOURCE] `src/builtins/utils.zig` carries an unresolved cost note:

```zig
// TODO: Deal with the fact we allocate an extra u64 for refcount.
// This may lead to allocating page size + 8 bytes.
// That could mean allocating an entire page for 8 bytes of data which isn't great.
```

[SOURCE] Atomicity is the *default*: `const RC_TYPE: Refcount = .atomic;`, with
`single_thread` available only "for allocations the compiler proved no other
thread can ever touch" — i.e. every un-proved refcount touch is an atomic RMW.

[SOURCE] The clone fallback is stated plainly in the langref (§3): shared values
are "shallowly cloned first, and then the clone will be updated and returned" —
so a single extra live reference silently turns an O(1) update into an O(n) copy.

[SOURCE, secondary] Feldman, Changelog #645:

> "Rust programs can run faster than Roc programs, because in Rust you don't
> have to reference count everything… But in Roc, that's just sort of done for
> you automatically, behind the scenes, which makes Roc code a lot more concise
> and a lot simpler than Rust code"

> "It is potentially doing the 'clone your thing', but kind of our hypothesis…
> was that in practice… the amount of cloning that your program needs to do
> actually should be extremely, extremely minimal."

[SOURCE] The FAQ (<https://www.roc-lang.org/faq>) defends keeping this implicit:

> "If Roc were to have linear types or uniqueness types, they would move things
> that are currently behind-the-scenes performance optimizations into the type
> system."

(The fetcher declined to reproduce the whole section; the surrounding argument is
that such types would burden the whole ecosystem for a minority of use cases, and
it does not itself discuss refcounting.)

[INFERENCE] What the model makes hard, in A7-relevant terms: (i) performance is
not locally predictable from the source text — whether `List.set` is O(1) or O(n)
depends on a count the user cannot see; (ii) atomic RC is a pervasive tax paid
for a thread-sharing possibility most programs never exercise; (iii) tiny
allocations pay a whole header word; (iv) a whole class of data structures
(anything cyclic — graphs with back-edges, doubly-linked lists, observers) is
simply not expressible.

---

## 10. Maturity and planned changes

[SOURCE] Repo `README.md`: "Roc is not ready for a 0.1 release yet"; the page is
headed "Work in progress!". `docs/langref/README.md`: "This is heavily WIP!".
Published tags are alphas (`alpha4-rolling` newest); the builtin docs site is
versioned `alpha4`.

[SOURCE, secondary] The compiler was rewritten Rust → Zig (GOTO 2026 session
"Roc & Zig: A Compiler Rewrite Story", Anjana Vakil & Richard Feldman); coverage
of it states "Roc v1, due before the end of 2026"
(<https://gotopia.tech/articles/442/roc-zig-a-compiler-rewrite-story>). Treat the
date as a stated intention, not a shipped fact.

**Planned memory-model work** [SOURCE] `projects/small/compact-constant-aggregates.md`:
the problem is that "LIR has no compact way to materialize a large or repeated
aggregate value: list construction is lowered one element per frame local"; the
fix emits fully-constant lists as static data with "refcount-frozen headers so
ARC never touches them", with ARC insertion and the certifier treating static
references as "refcount-inert", mirroring static strings.

Not found: any design document proposing to remove reference counting, to adopt
ownership/linear types, or to switch to a tracing GC. [INFERENCE] The trajectory
is *less* RC traffic (more refcount-inert static data, more statically proved
uniqueness, single-thread updates where provable), not a different scheme.

---

## Claims checked

**Claim 1 — "Roc: pure functional, app-focused; optimized RC plus borrowing;
mutable updates allowed."**
**Verdict: substantially correct, with one qualifier.**
- *App-focused*: confirmed — "Every Roc application is built on exactly one
  _platform_, and that platform … provides all of the application's I/O
  primitives" (`docs/langref/platforms.md`).
- *Optimized RC plus borrowing*: confirmed — atomic RC
  (`docs/langref/expressions.md`) with interprocedural owned/borrowed inference
  and born-unique analysis (`src/lir/arc_solve.zig`), plus single-thread
  (non-atomic) refcount mode for provably thread-confined allocations
  (`src/builtins/utils.zig`). [DEEPWIKI] an "RC elision" optimization removing
  adjacent retain/release pairs is also reported (test name "RC elision removes
  adjacent retain release pairs"); not verified against raw sources.
- *Mutable updates allowed*: confirmed in two distinct senses — invisible
  in-place update of unique heap values (langref *Opportunistic Mutation*), and
  **user-visible** reassignment of `var` locals, whose names must start with `$`
  (`docs/mini-tutorial-new-compiler.md`, `docs/langref/statements.md`).
- *Qualifier*: "pure functional" now needs care. Roc has reassignable `var`
  locals and effectful functions, so it is not ML-pure at the statement level;
  what holds is that **values are semantically immutable** and no address or
  identity is observable ("Roc treats memory addresses as behind-the-scenes
  implementation details…", langref *Value Identity*). [INFERENCE] Phrase it as
  "immutable-value semantics with local mutable bindings", not "pure functional".

**Claim 2 — "In Koka, Lean 4 and Roc, uniqueness is decided by a reference count
at run time, sometimes removed by static analysis."**
**Verdict: verified for Roc; Koka and Lean 4 not investigated in this task.**
Roc side, [SOURCE]: the runtime decision is `refcount == 1` (`design.md`:
"Runtime mutation still uses `refcount == 1` to decide whether in-place mutation
is allowed"; `utils.zig`: `rcUnique` returns `refcount == 1`), and the static
removal is real — `src/lir/arc_solve.zig`'s born-unique fixpoint, plus
[DEEPWIKI] the `unique_args` bitmask that lets a builtin take the in-place path
without the runtime check. I make no claim here about Koka or Lean 4; do not
carry their half of the sentence forward on this document's authority.

**Claim 3 — "Roc's users never see memory concepts in ordinary code."**
**Verdict: partially refuted.**
- Supporting: the tutorial contains zero mentions of memory, allocation,
  refcounting, GC, performance, or in-place mutation [SOURCE]; the language
  exposes no address, pointer, reference-equality or free operation (langref
  *Value Identity*); Feldman: it "just feels like a garbage collected language".
- Refuting: the language reference explains reference counting, refcount==1
  in-place update, and cloning to users directly; and the **API docs** users read
  daily surface memory: `List.with_capacity`, `List.reserve`,
  `List.release_excess_capacity` ("Shrink the memory footprint… will also convert
  seamless slices to regular lists"), `Str.with_capacity`/`Str.reserve`
  ("a performance optimization tool… can help prevent reallocation and copying—at
  the cost of using more memory than is necessary"), the same capacity family on
  `Dict`/`Set`, and `List.keep_if`'s "If given a unique list … will not allocate any new memory on
  the heap."
- [INFERENCE] Accurate wording for our docs: users never *manage* memory and
  never see addresses or frees, but *uniqueness, capacity, allocation and
  boxing* are all visible in the standard library, and performance tuning
  requires reasoning about how many references are live.

---

## What A7 can take without reference counts

All of this section is **[INFERENCE]** built on the sourced material above.

1. **Take the static half; you cannot take the dynamic half.** Roc's design
   splits cleanly: a whole-program borrow/ownership solve
   (`src/lir/arc_solve.zig`) that proves what it can, and a `refcount == 1`
   test that catches the rest. A7 has no runtime count, so the fallback edge
   must be resolved differently: when uniqueness is *not* proved, A7 must copy
   (or reject the program), where Roc merely gets slower. Making that the
   explicit rule — **prove unique, else copy, else diagnose** — is the single
   most important adaptation.
2. **Adopt the one-stage rule.** "Static ownership reasoning lives in exactly
   one place" and "backends do not reason about reference counting" is a
   compiler-architecture invariant worth copying verbatim in spirit: A7's
   safety/ownership planning should emit explicit, already-decided
   allocate/free/reuse statements into the IR, and the Zig backend should only
   lower them. Roc even ships a debug certifier (`ArcCertify`) that re-checks the
   emitted result — a cheap analogue for A7 would be a debug pass asserting every
   allocation has exactly one statically paired release.
3. **Copy the ownership-signature vocabulary.** Per-procedure signatures
   recording which parameters are borrowed, whether the return borrows from a
   parameter and which, plus a "born-unique" bit, is exactly the summary A7
   needs for interprocedural in-place reuse without any counts — and Roc's
   Phase A/Phase B fixpoint (start borrowed, flip to owned on demand) is a
   proven, cheap formulation.
3b. **"Dismantle instead of release" is a count-free idea.** `arc_dismantle.zig`
   exists because reading a field out of a container that is about to die would
   otherwise create a second holder and force a copy. A7 has the same hazard
   without counts: destructuring a dying aggregate should *move* each field out
   and free the shell, not copy fields and then free. Encode "this aggregate's
   last use is a field-by-field teardown" as an IR fact, exactly as Roc does.

4. **Make literals refcount-inert by construction.** Roc's
   `REFCOUNT_STATIC_DATA = 0` sentinel and the in-progress "refcount-frozen"
   static constant aggregates say that the best answer for constant data is *no
   lifetime management at all*. A7, having no counts, gets this for free — but
   should mirror the categorical distinction (static/immortal storage vs managed
   storage) in its IR so constants never enter the reuse machinery.
5. **Ban cycles at the language level, and say so.** Roc's ability to use the
   simplest possible scheme rests on "By design, Roc has no way to express
   reference cycles". A7's no-recursion, no-address-of surface already points
   the same way; documenting cycle-freedom as a *language guarantee that buys a
   simpler memory model* is the same trade, made earlier.
6. **Platform boundary — the directly transferable model.** Roc's native
   boundary is worth imitating almost point for point:
   - The host supplies the allocator (`RocOps` with `roc_alloc`/`roc_dealloc`/
     `roc_realloc`), so the language never bakes in a malloc; a host may be an
     arena where free is a no-op. A7's descriptor should likewise carry the
     allocator, not assume one.
   - Ownership transfers **explicitly at every crossing**, in a documented
     direction: values Roc returns are host-owned and the host must release
     them; arguments to host functions are owned by the host for the call;
     storing one beyond the call requires an explicit retain. A7's equivalent of
     "retain" is not a count but a copy or a move, so the A7 rule becomes:
     *every crossing is a move or an explicit copy, and the descriptor states
     which*.
   - **Never let the host hand-roll layouts.** The glue README's hazard list is
     the best available specification of what a native descriptor must encode:
     committed field order, padding, alignment, discriminants, payload offsets,
     pointer-width variants, allocation headers not visible from the source
     type, teardown plans for containers of managed elements, and the fact that
     a slice may not point at the allocation base that must be released. A7's
     descriptor format should enumerate these same facts and, like Roc, be
     **generated** with compile-time size/alignment/offset assertions checked in
     CI against the canonical definitions.
   - Boundary teardown is *recursive and conditional*: releasing a container
     releases its elements only when the container itself dies. Even without
     counts, A7 needs a per-type, compiler-derived teardown plan in the
     descriptor rather than a generic "free the pointer".
   - Crash/panic handling crosses too (`roc_crashed` — "must stop execution … and
     not return"), and the current glue runtime is documented as
     single-threaded: it is legitimate to ship a boundary that declares
     single-threaded ownership first and widen later.
7. **What not to take.** The `refcount == 1` runtime test, the per-allocation
   header word (Roc's own TODO flags the page-rounding waste it causes), atomic
   RMW on every un-proved touch, and the silent O(1)→O(n) clone. Those are the
   price Roc pays for deciding uniqueness late; A7's premise is to decide it
   early, which means A7 must instead accept either more copies or more
   compile-time rejections, and should be explicit in its docs about which.

---

## Sources

Accessed 2026-09-16. Repository content at HEAD `a49a16f` unless a tag is named.

Primary — Roc repository (`github.com/roc-lang/roc`):
- <https://github.com/roc-lang/roc/blob/main/docs/langref/expressions.md> — reference counting, reference cycles, opportunistic mutation, value identity
- <https://github.com/roc-lang/roc/blob/main/docs/langref/platforms.md> — platform/host split, host-provided malloc/free, arena allocation
- <https://github.com/roc-lang/roc/blob/main/docs/langref/README.md> — "This is heavily WIP!"
- <https://github.com/roc-lang/roc/blob/main/docs/langref/statements.md>, `loops.md` — `var`/`$` reassignment (via DeepWiki quotes)
- <https://github.com/roc-lang/roc/blob/main/docs/mini-tutorial-new-compiler.md> — tutorial (target of the roc-lang.org/tutorial 302 redirect)
- <https://github.com/roc-lang/roc/blob/main/design.md> — ARC insertion as the single ownership stage; `refcount == 1` runtime rule; LIR pipelines
- <https://github.com/roc-lang/roc/blob/main/src/lir/mod.zig> — LIR pass list (Arc, ArcSig, ArcSolve, ArcCertify, ArcDismantle, BoxReuse, Trmc)
- <https://github.com/roc-lang/roc/blob/main/src/lir/arc_solve.zig> — borrow inference doc comment, Phase A/B, born-unique analysis
- <https://github.com/roc-lang/roc/blob/main/src/lir/arc_dismantle.zig> — "Field takes from dying aggregates" (drop-specialization analogue)
- <https://github.com/roc-lang/roc/blob/main/src/lir/box_reuse.zig> — allocation-replacement reuse rewrite; erased-callable pack fusion
- <https://github.com/roc-lang/roc/blob/main/src/builtins/utils.zig> — `REFCOUNT_STATIC_DATA`, `RC_TYPE`, `RcAtomicity`, `rcUnique`, `isUnique`, `increfRcPtr`, `decrefRcPtr`, refcount-header TODO
- <https://github.com/roc-lang/roc/blob/main/src/builtins/host_abi.zig> — `RocOps` vtable and host obligations
- <https://github.com/roc-lang/roc/blob/main/src/compile/README.md> — host ownership of returned refcounted values, explicit `decref`
- <https://github.com/roc-lang/roc/blob/main/src/glue/README.md> — why glue is generated; ownership/refcount transfer rules; single-threaded hosts
- <https://github.com/roc-lang/roc/blob/main/projects/small/compact-constant-aggregates.md> — refcount-frozen static constant lists
- <https://github.com/roc-lang/roc/blob/main/README.md> — "Roc is not ready for a 0.1 release yet"
- <https://github.com/roc-lang/roc/blob/0.0.0-alpha2-rolling/crates/compiler/mono/src/reset_reuse.rs> — frame-limited reuse, Teeuwissen/Swierstra credit
- <https://github.com/roc-lang/roc/blob/0.0.0-alpha2-rolling/crates/compiler/mono/src/drop_specialization.rs> — Perceus drop specialization
- <https://github.com/roc-lang/roc/blob/0.0.0-alpha2-rolling/crates/compiler/mono/src/borrow.rs> — historical borrow fixpoint
- <https://api.github.com/repos/roc-lang/roc/commits?per_page=1>, <https://api.github.com/repos/roc-lang/roc/tags?per_page=5>

Primary — roc-lang.org:
- <https://www.roc-lang.org/faq> — uniqueness/linear types answer
- <https://www.roc-lang.org/> — "Roc code is designed to build fast and run fast. It compiles to machine code or WebAssembly."
- <https://www.roc-lang.org/builtins/alpha4/List/> — `with_capacity`, `reserve`, `release_excess_capacity`, `keep_if` in-place note
- <https://www.roc-lang.org/builtins/alpha4/llms.txt> — `Str.reserve`/`with_capacity` performance guidance

Papers referenced by the Roc source:
- Perceus: Garbage Free Reference Counting with Reuse — <https://www.microsoft.com/en-us/research/wp-content/uploads/2020/11/perceus-tr-v4.pdf> (linked from `docs/langref/expressions.md`); PLDI'21 version <https://www.microsoft.com/en-us/research/uploads/prod/2021/06/perceus-pldi21.pdf>
- Reference Counting with Frame Limited Reuse — <https://www.microsoft.com/en-us/research/wp-content/uploads/2021/11/flreuse-tr.pdf>
- Jelle Teeuwissen, "Reference Counting with Reuse in Roc", MSc thesis, Utrecht University — <https://studenttheses.uu.nl/handle/20.500.12932/44634> (landing page and PDF both returned HTTP 403 to automated fetch; abstract quoted from a search snippet only)

Talks, interviews and secondary coverage (labelled as such in the text):
- Richard Feldman, Changelog Interviews #645 — <https://changelog.com/podcast/645>
- "Roc & Zig: A Compiler Rewrite Story", Anjana Vakil & Richard Feldman, GOTO 2026 — <https://gotopia.tech/articles/442/roc-zig-a-compiler-rewrite-story>
- Eric Newbury, Test Double, 2022-02-15 — <https://testdouble.com/insights/super-performant-new-roc-language>
- SystemHalted write-up of a Feldman talk, 2022-02-19 — <https://systemhalted.in/2022/02/19/roc-lang-talk-richard-feldman/>

Tooling note: DeepWiki (`mcp__deepwiki__ask_question`, repo `roc-lang/roc`) was used for navigation and for the items explicitly marked [DEEPWIKI]; its index date is unknown and it is an AI summary, not a primary source.
