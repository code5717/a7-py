> **Source:** Claude research subagent. Primary-source study of Carp's memory management from the repository, `docs/Memory.md`, the issue tracker and the authors' own statements.  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim, including the subagent's own source-quality labels (`[primary]`, `[deepwiki]`, **INFERENCE**) and its caveat that fetched quotations may be lightly paraphrased. Two `[deepwiki]` findings were re-checked against source; see [carp-verify.md](carp-verify.md). User decisions are in the [ledger](../../../decisions.md).

# Carp: memory management — primary-source research

Research date / access date for all URLs: **2026-09-16**.
Version the evidence reflects: repository **master** (newest commit shown 2026-09-11);
newest tagged release **v0.6.0, 2024-03-28**. `docs/Memory.md` in its current form
lands via "Document the memory management system further" (#1442, closed 2022-10-31)
and ships in v0.6.0.

**Source-quality note.** Sources are labelled `[primary]` (the repository, its docs,
GitHub API, author's own words) or `[deepwiki]` (DeepWiki's AI answers over the repo —
secondary, useful for locating code but not authoritative). Where a `[deepwiki]` claim
was load-bearing I re-checked it against `[primary]` text and say so. Anything I could
not source is written **not found**. My own reasoning is marked **INFERENCE**.

A caveat on quotation fidelity: `[primary]` quotes were retrieved through a fetch tool
that summarizes pages, so wording may be lightly paraphrased in places (two fetches of
docs/Memory.md returned slightly different phrasings of the Recursive Types sentence).
The load-bearing quotes — the one-move rule, the lifetime `sig` syntax, and the
`endo-map`/`copy-map` passage — were seen consistently across more than one fetch.
Line counts, struct definitions and macro definitions were read from the files themselves.

One DeepWiki answer fabricated a commit hash and author for the introduction of
lifetime annotations; that specific provenance is recorded below as **not found**
rather than repeated.

---

## Summary (5 lines)

1. Carp reclaims memory by having one compiler pass, `manageMemory` in `src/Memory.hs`, attach *deleters* to AST nodes; the C emitter turns those into `T_delete(...)` → `CARP_FREE` calls at scope exit. Nothing runs at run time to decide this, with one exception: a per-closure deleter pointer (§5).
2. The discipline is single-ownership with moves ("one move per binding per lexical scope"), non-owning `&` references, and explicit `@` copies; unused bindings are silently deleted, so it is *affine in practice* despite the docs' "linear" wording.
3. There **are** user-written lifetime annotations — `(sig id (Fn [(Ref String a)] (Ref String a)))` — contradicting the widely cited 2018 claim that Carp omits lifetimes; that blog post is stale.
4. There is **no** reference counting, no drop flags, no shared-ownership type (no `Rc`/`Arc`), no cycles, and no compiler-inserted storage reuse; in-place reuse exists only as hand-written library functions (`endo-map`) that mutate an array you own.
5. Cost to users: the model is visible everywhere (`&`, `@`, `copy-` prefixes, `Box` for recursion), the checker still has open false-positive and unsoundness bugs from 2020, and the project self-describes as "a research project … Don't use it for anything important just yet!"

---

## 1. What exactly reclaims memory, where is a free inserted, by which pass, on what static information

**What reclaims.** Generated C calls type-specific `delete` functions, which call `CARP_FREE`. There is no collector and no runtime.

`[primary]` README feature bullets, https://github.com/carp-lang/Carp/blob/master/README.md:
> "Automatic and deterministic memory management (no garbage collector or VM)"
> "No hidden performance penalties – allocation and copying are explicit"

`[primary]` docs/Memory.md, "Safe Deallocations", https://github.com/carp-lang/Carp/blob/master/docs/Memory.md:
> "When the memory management system determines some linear value will no longer be used in the lexical scope of it's owner, it automatically calls the corresponding linear type's `delete` implementation to free the associated memory."

**Which pass, and where the free is recorded.** The pass is `manageMemory` in `src/Memory.hs`. It does not emit code; it *annotates* AST nodes with deleters, and the C backend emits from those annotations.

`[primary]` docs/Memory.md, "Under the Hood: The Implementation of Carp's Memory Management System" / "AST Info, Identifiers, and Deleters":
> "As the memory management system examines code, if it finds a form using a linear value that should be deleted, it adds an appropriate deleter to the info object for the form."

`[deepwiki]` (locating the code; consistent with the doc above): `manageMemory` lives in `src/Memory.hs`, runs over the AST in a `State MemState` monad, and writes results into the `infoDelete` field of each node's `Info`. Supporting functions named: `visit`, `manage` (add a deleter), `unmanage` (remove one on transfer), `transferOwnership` / `exclusiveTransferOwnership`, `createDeleter`, `getDropFunc`, `canBeReferenced`, `refTargetIsAlive`, `returnRefTargetIsAlive`, `collectLifetimeVars`, `addToLifetimesMappingsIfRef`. `Deleter` itself is defined in `src/Info.hs`.

**On what static information.** `[deepwiki]` quotes the state record:

```haskell
data MemState = MemState
  { memStateDeleters :: Set.Set Deleter,
    memStateDeps :: Set.Set Ty,
    memStateLifetimes :: Map.Map String LifetimeMode,
    memStateParamDeleters :: Set.Set Deleter,
    memStateNames :: Map.Map String String
  }
```

So the static inputs are: the set of live deleters, type dependencies, a lifetime-variable → `LifetimeMode` map (`LifetimeInsideFunction`, `LifetimeOutsideFunction`, `LifetimeMixed`), and name mappings. Deleter kinds reported: `ProperDeleter` (real `delete` call), `FakeDeleter` (external/linear but nothing to free), `PrimDeleter`, `RefDeleter`.

**Where the free lands in time.** At **end of lexical scope**, not at last use.

`[deepwiki]`, cross-checked against the "Under the hood" worked example in docs/Memory.md, which shows `String_delete(text)` emitted at function scope exit: "Carp inserts a `delete` call at the end of the lexical scope of a linear value's owner, not necessarily at its last use."

**INFERENCE:** this is the simplest possible placement rule and means Carp holds memory longer than a last-use/Perceus-style scheme would. For A7 this is the cheap-to-implement baseline; moving frees earlier is a separate optimization Carp never took.

**The allocator.** `[primary]` `core/carp_memory.h` (88 lines), https://github.com/carp-lang/Carp/blob/master/core/carp_memory.h — `CARP_MALLOC`/`CARP_REALLOC`/`CARP_FREE` are macros over plain `malloc`/`realloc`/`free`, with two opt-in debug variants — `LOG_MEMORY` (`logged_malloc`/`logged_free`, maintaining a `malloc_balance_counter` used by `Debug.memory-balance`) and `CHECK_ALLOCATIONS` (abort on allocation failure). Verified directly against the file: the default build is

```c
#define CARP_MALLOC(size) malloc(size)
#define CARP_REALLOC(ptr, size) realloc(ptr, size)
#define CARP_FREE(ptr) free(ptr)
```

and **no counter, flag, tag or bookkeeping variable is defined anywhere outside the `LOG_MEMORY` block.**

---

## 2. How the borrow checker works; what the user must write; lifetime annotations

**What is tracked.** Ownership of linear values (via the deleter set) and lifetimes of references (via `memStateLifetimes`). The checks are `refTargetIsAlive` (run as each form is visited) and `returnRefTargetIsAlive` (run once after the function body, against lifetime variables in the return type). `[deepwiki]`

`[primary]` docs/Memory.md, "Lifetimes":
> "The memory management system uses _lifetimes_ which determine whether or not a reference is valid in a given form."

`[primary]` docs/Memory.md, "Lifetimes in Detail":
> "Carp's lifetimes are made up of two pieces of information. Only references have lifetimes, and every reference has _exactly one_ lifetime assigned to it."

**What the user must write.** Ordinarily: `&` / `ref` to borrow, `@` / `copy` to duplicate, and `Box` to build recursive types. Types defined with `deftype` get `delete`, `copy` and `str` generated automatically `[deepwiki]`, so users do not hand-write destructors; types defined in C do need one:

`[primary]` docs/Memory.md, "Custom deletion functions":
> "Type that are defined in C do not have a `delete` function generated for them automatically, you can write your own deletion function, declare it to be implementing `delete`."

**Lifetime annotations: they exist.** docs/Memory.md has a section literally titled **"Explicit Lifetime Annotations"**, and the syntax is a type variable in the `Ref` position of a `sig`:

`[primary]` docs/Memory.md, "Explicit Lifetime Annotations":
```clojure
(sig id (Fn [(Ref String a)] (Ref String a)))
(defn id [x] x)
```
Here `a` is the lifetime variable tying the returned reference's lifetime to the argument's.

This **contradicts** the most-cited secondary description of Carp. `[primary, author-adjacent]` Veit Heller (Carp core maintainer), "Borrow Checking, The Carp Way", 2018-01-30, https://blog.veitheller.de/Borrow_Checking,_The_Carp_Way.html:
> "Rust solves this problem using lifetimes, which Carp decided to omit."
and
> "you cannot return references in Carp."

**INFERENCE:** the blog is accurate for 2018 and stale for master. v0.6.0's release notes list "More expressive lifetimes (#1512)" `[primary, releases page]`, so lifetimes were an ongoing work item through 2024. The exact PR/version that *first* introduced the `sig` lifetime-variable syntax: **not found** (DeepWiki supplied a hash I could not corroborate, so I discard it).

Returning a reference to a local is still rejected; the annotation only lets you thread a caller's lifetime through.

`[primary]` error text captured in issue #1065 (below): `"The reference '(ref (Sum.Two))' (depending on the variable '_9') isn't alive at line 9, column 15"`.

**Is it "Rust-style"?** The author's own framing, `[primary]` Erik Svedäng interviewed by Serokell, 2022-07-14, https://serokell.io/blog/carp-with-erik-svedang:
> "it's using borrow checking, very Rust-inspired but still has a kind of different feel from Rust, it's not trying to be as detailed as Rust, it's trying to be a bit slower but more ergonomic."

And `[primary]` eriksvedang on Hacker News, 2017-11-25, https://news.ycombinator.com/item?id=15778530: the type system is "less expressive but also less dependent on annotations" than Rust's; asked whether Carp distinguishes mutable from immutable references, he answered "not at the moment", adding "it's probably coming."

---

## 3. Ownership and moves: assignment, passing, returning; affine or linear; what is copied

`[primary]` docs/Memory.md, "Moving: Transferring Ownership":
> "The important, and only rule about moving linear values is: you can only move a linear value from an individual binding **once** in any given lexical scope."

and the stated cost:
> "This restriction ensures the type system knows exactly when to deallocate memory, but it can be a bit limiting."

- **Assignment** to a new binding moves; the old binding is invalidated.
- **Passing to a function** moves. `[primary]` docs/Memory.md: "Passing a linear value as an argument to a function is another example of a move across lexical scopes."
- **Returning** moves ownership to the caller's scope.
- **References are not linear.** `[primary]` docs/Memory.md, "Borrowing: Lending Ownership": "References are not linear types themselves; we're allowed to pass them around freely like other non-linear values." There is no borrow *count* and no exclusivity (see §"Claims checked").

**Linear or affine?** The docs say linear ("every linear value can only be used once"). `[deepwiki]` reports that a managed value bound in a `let` and never used produces **no** must-use error — a `delete` is silently inserted. **INFERENCE:** that is affine behaviour with linear vocabulary; the "exactly once" phrasing describes *at most one move*, not a use obligation.

**What is copied.** Nothing implicitly, for managed types. `@` / `copy` on a reference allocates a duplicate:

`[primary]` docs/Memory.md, "Copying: Increasing Supply":
> "Copying a reference creates a new linear value that **duplicates** the linear value the reference is pointing to"

and on literals:
> "This binds a **copy** of the string literal to the variable `string`. This reveals an important aspect of Carp's builtin string literals: they are references!"

**Blittable types are exempt entirely.** `[deepwiki]` (feature entry "feat: don't manage blittable types (#1407)" is `[primary]` from CHANGELOG, v0.5.5): `Int`, `Float`, `Bool`, `Long`, `Ptr` and anything implementing the `blit` interface are not linear, are ignored by the memory system, get no deleters, and are safe to bit-copy.

**INFERENCE, A7-relevant:** this two-tier split (blittable vs managed) is exactly the split A7 would need in Zig — a scalar/POD tier with zero bookkeeping, and a managed tier that owns heap storage.

---

## 4. Cycles and graph-shaped data

**Direct type recursion is rejected outright; recursion must go through an indirection.**

`[primary]` docs/Memory.md, "Recursive Types":
> "Recursive types are supported when the recursion goes through indirection (`Box` or `Ptr`). Direct recursion is rejected because the compiler must be able to determine a concrete size for every type."
> "`Box` is linear and managed by the memory system"; "`Ptr` is unmanaged and is intended for advanced use cases."

Canonical shape, `[primary]` docs/Memory.md:
```clojure
(deftype (List a)
  (Nil)
  (Cons [a (Box (List a))]))
```
v0.6.0 added "recursive types (#1496)" `[primary, releases page]`, and a 2026-06-29 commit "refactor: move Box from a compiler built-in to a core recursive type" `[primary, commit list]`. Users can mark their own heap-indirection type `recursive` (see `test/produces-output/recursive_types_user_box.carp`, a `Cell` type) `[deepwiki]`.

**Can a user build a *cycle*?** Not within the managed model.

`[deepwiki]`, asked directly: Carp's core contains **no** shared-ownership or reference-counted type (no `Rc`/`Arc`/`shared_ptr`), and **no weak references**; "only one binding ever owns the memory associated with a given linear value", so there is no way for two owners to point at the same allocation without `Unsafe`/`Ptr`. On what happens if you did force a cycle through `Box`: DeepWiki would not commit, saying the docs "do not explicitly describe how cycles are handled" and that a cycle "would likely result in a stack overflow during deletion or a memory leak".

`[primary]` docs/Memory.md contains **no** discussion of cycles, graphs, shared mutable state, or self-referential data — I checked the full section list for it. There is no doubly-linked list, cyclic graph, or parent-pointer tree in `core/` `[deepwiki]`; **not found** in examples either.

**INFERENCE (clearly labelled):** a back-edge is inexpressible in owned form, because owning it would mean two owners of one allocation, which the one-move rule forbids. A user who needs a general graph must either (a) store indices into an `Array` — the standard workaround, and the same one A7's CLAUDE.md already mandates for A7 source — or (b) drop to `Ptr`, leaving the managed model entirely and hand-managing the frees. Carp's docs never tell the user this; the absence is itself the finding.

---

## 5. Any runtime memory work left?

**No.** No reference counts, no drop flags, no ownership tags.

`[primary]` README: "Automatic and deterministic memory management (no garbage collector or VM)"; carp-website adds "Compiled without a garbage collector, runtime, or VM" (https://carp-lang.github.io/carp-website/).

`[deepwiki]`, asked to settle exactly this: "Carp's generated C code does not use runtime reference counts, drop flags, or ownership tags for memory bookkeeping … the compiler insert[s] explicit `_delete` and `_copy` function calls based on ownership analysis during compilation. Allocator metadata is handled by the underlying `malloc`/`free` or `CARP_MALLOC`/`CARP_FREE`."

Generated delete shapes quoted by `[deepwiki]` from the emitter:
```c
void String_delete(String s) { CARP_FREE(s); }
void Array_delete(Array a) { for(int i = 0; i < a.len; i++) { /* delete each element */ } CARP_FREE(a.data); }
```
The one exception is closures, which carry a deleter *function pointer* in the value itself. The struct is `[primary]`, `core/core.h`, https://github.com/carp-lang/Carp/blob/master/core/core.h:

```c
typedef struct {
    void* callback;
    void* env;
    void* delete;
    void* copy;
} Lambda;
```

and `[primary]` `src/Emit.hs` shows the compiler filling those slots when a lambda needs an environment — `.delete = <LambdaEnvType>_delete`, `.copy = <LambdaEnvType>_copy`, both `NULL` when no environment is captured. The generated deleter that consults the pointer at run time is `[deepwiki]`-reported (I did not locate its emission site in `src/Emit.hs`):
```c
void Function_delete (Lambda f) {
  if(f.delete) { ((void(*)(void*))f.delete)(f.env); CARP_FREE(f.env); }
}
```
**INFERENCE:** that per-lambda deleter pointer is the single piece of *runtime* dispatch in the scheme — it exists because a closure's captured environment is not statically known at the point where the closure is dropped. The `Lambda` struct carrying `delete`/`copy` slots is confirmed primary; the `if (f.delete)` branch that reads them is deepwiki-reported and unverified. It is not a drop flag (it does not record whether a value was moved), but it is the seam where Carp's otherwise fully static story needs a runtime word. A7 should expect the same seam if it ever has closures with heap-captured state.

The only other runtime bookkeeping is opt-in debugging: `LOG_MEMORY` compiles in a `malloc_balance_counter` for `Debug.memory-balance` / `Debug.reset-memory-balance!` `[primary, core/carp_memory.h]`. **This is the quote that settles the question:** read directly, `core/carp_memory.h` is 88 lines that define nothing but the three allocator macros and that opt-in debug counter — outside the `LOG_MEMORY` block it defines no counter, flag or tag at all. Corroborating primary text, README: "No hidden performance penalties – allocation and copying are explicit."

---

## 6. What Carp rejects that a GC'd language accepts

Concrete, evidenced cases. Source for the issue list: GitHub API, `https://api.github.com/search/issues?q=repo:carp-lang/Carp+borrow+OR+ownership+OR+memory+in:title` `[primary]`; the repo's label `memory` is described as "Borrow checker and lifetimes" (`https://api.github.com/repos/carp-lang/Carp/labels`).

**(a) A closure may not move out a captured value.** This is a real expressiveness loss, introduced deliberately to fix unsoundness.

`[primary]` issue #1040, "Taking ownership of value captured by a lambda env is unsafe", TimDeve, 2020-12-01, **still open**, https://github.com/carp-lang/Carp/issues/1040:
```clojure
(defn main []
  (let [s @"String"
        f (fn [] s)]
    (ignore (f))))
```
> "returning the value `s` means the consumer of the lambda will take ownership of it, so when it is done with the value it will call `delete` on it, but the value is still captured in the env of the lambda so when the env gets deleted it tries to free something already free-ed."

`[primary]` PR #1440, https://github.com/carp-lang/Carp/pull/1440 — the fix is a prohibition:
> "disallowing functions to leak variables captured from another scope. Doing so is now an error."
`(fn [] capture)` is now an error; `(fn [] @&capture)` — i.e. copy it — is the required rewrite.

**INFERENCE:** in any GC'd Lisp this is the single most ordinary thing a closure does. Carp's answer is "copy instead", which is a real allocation the GC'd version would not make.

**(b) A reference cannot be returned from a local.** §2 above. In a GC'd language, returning an interior pointer to a freshly built value is unremarkable.

**(c) The one-move rule blocks reuse after a call.** `[primary]` docs/Memory.md, "Beyond Moves" — the doc's own framing of the problem is that after moving a value into a function you cannot use it again; its answer is literally:
> "Luckily, there's a way out: references."
and in "Borrowing: Lending Ownership":
> "Luckily, there's a mechanism that allows us to reuse `string` more than once in our let block: _references_."

**(d) Map over an array changing element type must allocate, and the name says so.** `[primary]` docs/Memory.md, "Working with arrays":
> "The restriction of 'endo-map' is that it must return an array of the same type as the input. If that's not possible, use 'copy-map' instead. It works like the normal 'map' found in other functional languages. The 'copy-' prefix is there to remind you of the fact that the function is allocating memory."

**INFERENCE:** the user's ordinary `map` is split into two functions by a *memory* criterion, and the naming convention exists to keep the cost visible. That is the clearest single example of the memory model surfacing in an everyday API — directly against A7's goal of "a surface where ordinary users never think about memory".

**(e) Cycles and shared graphs.** §4.

**(f) Threads and shared state.** `[primary]` issue #1149, eriksvedang, 2021-01-26, https://github.com/carp-lang/Carp/issues/1149:
> "There is not a good and well though-out plan for threading and concurrency, I'm afraid."
Core has no concurrency support `[deepwiki]`.

**(g) Checker false positives — code the user *should* be able to write, rejected.** These are bugs, not design, but they are what users hit:
- `[primary]` #1065 "Borrow checker is confused by using a match-ref with a let block", 2020-12-12, **open**: two independent `match-ref` forms in one `let` produce "The reference '(ref (Sum.Two))' (depending on the variable '_9') isn't alive…", and the reporter notes "there is no shared values between the two match-ref".
- `[primary]` #1107 "Borrow checker gets confused by references inside `if`", 2020-12-29, **open**, labels bug/haskell/memory.

**(h) Soundness holes in the other direction** (Carp *accepts* what it should reject — relevant because it shows how hard the pass is to get right):
- `[primary]` #1075 "Possible to borrow twice what is passed to a match", 2020-12-16, open.
- `[primary]` #997 "Complex case leads to free before allocation", scolsen, 2020-11-22, open, milestone "0.7.0 – No major bugs": generated C calls `String_delete(p->x)` on a captured String, producing "pointer being freed was not allocated"; the same code shape with `Int` works.
- `[primary]` #1416 "Memory management in nested lambdas is not working properly", 2022-04-12, open; #1419 "memory management crash", 2022-04-22, open.
- Leaks: #1432 "`format` leaks memory" (2022-09-19, open), #1576 "we leak memory on `break` inside `if` or `match`" (2026-08-10, open), #1575 (2026-08-05, open).

**INFERENCE:** the open-bug profile is the most instructive thing here. The hard cases are uniformly *control flow that splits or defers ownership* — `if`, `match`, `break`, and closures. Straight-line scope-exit deletion is easy; everything else is where a decade of bugs accumulated.

---

## 7. Escape hatches

`[primary]` `core/Unsafe.carp`, https://github.com/carp-lang/Carp/blob/master/core/Unsafe.carp — the module defines exactly two functions:
- `coerce : (Fn [b] a)` — "coerces a value of type `b` to a value of type `a`."
- `leak : (Fn [a] ())` — "prevents a destructor from being run on a value a."

So **leaking on purpose is a first-class, documented operation**, and it is used inside the core library: `Box.unbox` calls `Unsafe.leak` after `Box.heap-free` so the memory system does not delete the value a second time `[deepwiki]`.

Other hatches:
- **`Ptr`** — `[primary]` docs/LanguageGuide.md / Memory.md: "`Ptr` is unmanaged and is for advanced use cases where you handle lifetime and deallocation yourself."
- **`register`** for C functions, including hand-written `delete` implementations for C-defined types `[primary]` docs/Memory.md "Custom deletion functions". Overriding `delete` is explicitly discouraged: "As the `delete` interface is responsible for freeing memory, it is **unsafe** to override it." (`[primary]`, carp-docs Memory page; CHANGELOG v0.5.1 records "docs: Updates memory docs to discourage overriding `delete` (#1245)").
- **Raw C emission** — `Unsafe.emit-c`, `Unsafe.preproc`, `Unsafe.C.asm` (the last recorded in CHANGELOG v0.5.1, "feat: Add Unsafe.C.asm (#1206)") `[deepwiki + primary CHANGELOG]`. Note these are not in `core/Unsafe.carp` itself.
- **`Box.heap-alloc` / `Box.heap-free`** wrap `CARP_MALLOC`/`CARP_FREE` directly `[deepwiki]`.
- **Proposed but unresolved:** `[primary]` issue #1095 "RFC: Implement `delete` for `Ptr` and add `Leak` type", scolsen, 2020-12-23, **open** — proposes splitting `Ptr`'s dual role (C interop vs unmanaged memory) by adding a `Leak` type with a no-op delete, so that "seeing a function with signature `[b] (Leak c)` would immediately indicate that I'm getting a long-lived … value that I'll have to delete/clean-up manually." Alternative names floated: `Memory`, `Unmanaged`, `Eternal`.

---

## 8. Maturity and scale

**Self-assessment.** `[primary]` README, https://github.com/carp-lang/Carp:
> "WARNING! This is a research project and a lot of information here might become outdated and misleading without any explanation. Don't use it for anything important just yet!"

**Activity: yes, active — but slowly, and by few people.** `[primary]` commit list, https://github.com/carp-lang/Carp/commits/master — newest commit 2026-09-11 ("Add docexample and print-docexample to compiler and stdlib"), with memory-related work continuing into 2026 ("Fix duplicate deleters in manage function", 2026-07-29; "refactor: move Box from a compiler built-in to a core recursive type", 2026-06-29). Repo metrics: ~6,000 stars, 127 open issues, 5,056 commits `[primary, repo page]`. Releases: v0.6.0 on **2024-03-28**, preceded by v0.5.5, v0.5.4, v0.5.3, v0.5.2, v0.5.1 `[primary, releases page]` — i.e. **no tagged release in ~2.5 years** despite ongoing commits.

**Scale of real programs.** Small. `[primary]` docs/Libraries.md (https://carp-lang.github.io/Carp/Libraries.html) lists six community libraries — Anima (drawing/animation), Stdint, Socket, Physics (a port of phys.js), NCurses bindings, Curl bindings — and points at https://github.com/carpentry-org for "a growing list of Carp packages". The `carp-lang` org itself has six repos, of which only the compiler is active: carp-emacs (last updated 2023-02-04), carp-docs (2022-11-01), carp-website (2021-04-22), carp-docker (2021-04-21), comparisons (2020-05-06) `[primary, https://github.com/orgs/carp-lang/repositories]`. The core library is ~46 `.carp` files loaded by `core/Core.carp` `[deepwiki]`. The README lists no production users or showcase projects `[primary]`.

**The creator has not shipped a program in it.** `[primary]` Svedäng, Serokell interview, 2022-07-14:
> "I have not yet made an actual finished game with Carp, so it's still just a distant goal but one that I'm still working towards."
> "If you download the compiler right now, it's a bit buggy but it works."

**Main friction reported.** Notably, the creator's stated blocker is **not** the memory model — it is compiler speed and stability:
> "to create a big game with it, it would have to be even more stable and even faster as a compiler. Like, I can't spend years working on something and then get stuck because my language is not good enough."
He describes wanting to rewrite on LLVM: "a new version of the compiler … using LLVM … gonna be much much faster." And on audience: "There is this very particular kind of person who likes both Lisp and game development … it's never going to be the mainstream."

Second-order friction from the issue tracker: borrow-checker false positives around `if`/`match`/lambdas, and leaks around `break` (§6g, §6h).

---

## 9. Published performance numbers

**Not found.** No benchmark table, timing, or measured comparison from a primary Carp source was located.

What exists is qualitative only: `[primary]` README/website — "Inferred static types for great speed and reliability", "No hidden performance penalties – allocation and copying are explicit", "Uses cache-friendly data structures and mutation under the hood". The org's `comparisons` repo (https://github.com/carp-lang/comparisons, "Small example projects in various languages to compare with Carp") holds example projects (`sim-carp`, `sim-clj`) but publishes **no numbers**; 3 stars, 1 commit, last updated 2020-05-06 `[primary]`.

Searches for "as fast as C", FPS figures, and benchmark results returned nothing from Carp sources.

---

## Claims checked

| Claim (as it appears in our documents) | Verdict | Basis |
|---|---|---|
| "Carp adopts Rust-style borrow checking" | **Verified, with a qualifier** | The author calls it "borrow checking, very Rust-inspired but still has a kind of different feel from Rust, it's not trying to be as detailed as Rust" (Serokell 2022). Qualifier: unlike Rust there is **no `&mut` vs `&` distinction** — eriksvedang, HN 2017: asked if Carp differentiates them, "not at the moment". So it is Rust-*style* ownership + lifetimes, but without exclusivity. |
| "uses ownership, borrowed references and deterministic frees without a garbage collector" | **Verified** | README: "Automatic and deterministic memory management (no garbage collector or VM)". docs/Memory.md: ownership/moves, `&` borrows, `delete` at scope exit. No refcount, no drop flags (§5). |
| "Carp is the closest of Koka, Lean 4, Roc, MLKit and Carp to a statically resolved model" | **Partially verified — do not state as fact** | The *Carp half* is solid: zero runtime memory bookkeeping, all decisions in `manageMemory` (§5). But I did not check Koka, Lean 4, Roc or MLKit from primary sources in this session. **INFERENCE / caution:** MLKit's region inference is also fully static with no runtime refcount, so "closest" is not established against MLKit; and Koka/Roc/Lean 4 are refcount-based (Perceus/RC), which would make the ranking plausible against *those three* but not against MLKit. Recommend restating as "Carp resolves all memory decisions statically, with no runtime reference counting" and dropping the superlative unless MLKit is checked. |
| "its borrow checker is roughly 600 lines" | **Refuted as a Carp figure** | The 600-line figure belongs to **Austral**: "The implementation of Austral's linearity checking algorithm is 600 lines of OCaml, much of which is error reporting, comments, and utility functions" — Borretti, "How Austral's Linear Type Checker Works", https://borretti.me/article/how-australs-linear-type-checker-works. No comparable figure is claimed anywhere for Carp. Carp's `src/Memory.hs` is **833 lines (796 loc), 39.8 KB** `[primary — GitHub's own header, https://github.com/carp-lang/Carp/blob/master/src/Memory.hs]`, and it is not the whole story: lifetime/borrow logic is entangled with `src/Concretize.hs`, `src/Info.hs` (the `Deleter` type) and the emitter. |
| "Carp's memory model permits in-place mutation of a value the program still holds elsewhere" | **Verified** | Two independent legs. (i) No exclusivity: references "are not linear types themselves; we're allowed to pass them around freely" (docs/Memory.md), and there is no `&mut`/`&` split (eriksvedang, HN 2017) — so two live `&`s to one value are permitted. (ii) Mutation happens *through* a shared reference: `Array.aset!` takes a `Ref` and "mutates the array element at the given index in place" `[deepwiki]`; `endo-map` and `filter` "use C-style mutation of the array and return the same data structure back afterwards, no allocation or deallocation needed" `[primary, docs/Memory.md]`. Svedäng, Serokell 2022: "you can mutate anywhere. It's not like Haskell where you have to mark things at all." **INFERENCE:** Carp's safety argument is liveness-only (does this reference still point at something alive?), not exclusivity (is anyone else looking at it?). That is a strictly weaker guarantee than Rust's, and it is *why* Carp has no answer for threads (§6f). |

**One further correction worth recording:** the frequently quoted line "Rust solves this problem using lifetimes, which Carp decided to omit" (Heller, 2018) is **stale**. Master has a documented "Explicit Lifetime Annotations" section and a lifetime-variable syntax in `sig` forms, and v0.6.0 shipped "More expressive lifetimes (#1512)". Any A7 document repeating "Carp has no lifetimes" should be fixed.

---

## What A7 can and cannot take from Carp

Against A7's five stated wants: no GC, no refcount, memory decided at compile time, in-place reuse of storage, and a surface where ordinary users never think about memory.

**Can take.**

1. **The architecture of the free-insertion pass.** Carp's shape is directly portable to A7's pipeline: one pass walks the AST with a state record, and *annotates nodes* with deleters rather than emitting anything; the backend emits from the annotations. A7 already runs `a7/passes/` semantic passes ahead of `a7/backends/zig.py`, so a `MemState`-equivalent carrying a deleter set, a lifetime map, and type deps would slot in after the type checker. Note A7's iterative-traversal invariant: Carp's `visit` is recursive Haskell; A7 would need the explicit-stack form, which is mechanical.
2. **The blittable/managed split.** Exempting scalars and POD structs from all bookkeeping (Carp's `blit` interface, #1407) is the single highest-leverage simplification, and it maps cleanly onto Zig's value types. Most code then generates zero memory machinery.
3. **Deterministic scope-exit frees as the v1 rule.** Carp proves that "delete at end of the owner's lexical scope" is sufficient for a working language with zero runtime cost. A7 should adopt this as the baseline and treat last-use narrowing as a later optimization, not a prerequisite.
4. **Evidence that the no-runtime-state goal is achievable.** §5 is the load-bearing result: no refcounts, no drop flags, no tags — just `malloc`/`free` and statically placed calls. Carp is an existence proof that A7's first three wants are jointly satisfiable.
5. **Negative lesson on where to spend test effort.** Carp's decade of open bugs clusters entirely on `if`, `match`, `break` and closures — control flow where ownership splits or escapes. A7 should build its conformance tests around branch-and-merge ownership *first*.

**Cannot take.**

6. **In-place reuse is not solved by this design.** Carp does **no** compiler-inserted storage reuse — every managed value is a `CARP_MALLOC` and every dead one a `CARP_FREE` `[deepwiki]`. Its only in-place reuse is *hand-written library functions* on values you own (`endo-map`, `filter`, `aset!`). **INFERENCE:** A7's want of "in-place reuse of storage" is therefore *not* obtainable by copying Carp; that want is the Perceus/Koka reuse-analysis feature, which requires knowing a value is uniquely referenced at the point of reuse — and Koka gets that from a refcount A7 has ruled out. A7 must either (a) accept library-level in-place APIs like Carp's, obtaining reuse only where the owner is statically known, or (b) invent static uniqueness analysis. Do not assume Carp's model delivers (b).
7. **The invisible-memory surface is exactly what Carp failed to deliver.** This is the sharpest finding for A7. Carp's users write `&`, `@`, `ref`, `Box`, and choose between `endo-map` and `copy-map` — and the `copy-` prefix exists specifically "to remind you of the fact that the function is allocating memory". The one-move rule is described in Carp's own docs as "a bit limiting", and the escape from it is always "use references" or "make a copy". **INFERENCE:** ownership-with-moves buys you no-GC/no-refcount at the cost of a visible memory surface. A7 wants both; Carp demonstrates the trade, not a way around it. If A7 holds the invisible-surface constraint, it must find its cost model elsewhere — e.g. arena/region discipline per scope (closer to MLKit) — rather than surfacing moves and borrows.
8. **Cycles and graphs have no answer here.** No `Rc`, no weak refs, no cyclic structure in managed form, and the docs are silent on it. A7's existing rule — index-based worklists and arrays, as already mandated in `examples/025_linked_list.a7` / `026_binary_tree.a7` — is in fact the same workaround Carp users must reach for, and A7 should keep it as an explicit, documented part of the memory model rather than a gap.
9. **Leaking must be a designed feature, not an accident.** Carp's `Unsafe.leak` is used *by the core library itself* (`Box.unbox`) to suppress a double-delete. **INFERENCE:** any statically-resolved model needs a sanctioned "the compiler is wrong about this one, don't free it" valve, or the standard library cannot be written. A7 should plan the valve up front — and note issue #1095 shows Carp regretting that it never gave unmanaged memory its own *type*, leaving `Ptr` overloaded.
10. **Do not cite Carp for performance.** There are no published numbers (§9). And do not cite it for maturity: "Don't use it for anything important just yet", no tagged release since 2024-03-28, and the creator has not finished a program in it.

---

## Sources

All accessed **2026-09-16**.

Primary — repository and docs:
- https://github.com/carp-lang/Carp — README, tagline, feature bullets, research-project warning, repo metrics
- https://github.com/carp-lang/Carp/blob/master/README.md
- https://github.com/carp-lang/Carp/blob/master/docs/Memory.md — sections: Linear Types and Memory Management; Recursive Types; Bindings, Ownership, and Lexical Scopes; Safe Deallocations; Moving, Borrowing, and Copying; Moving: Transferring Ownership; Moving to a New Scope; Beyond Moves; Borrowing: Lending Ownership; Copying: Increasing Supply; Rule of thumb; Working with arrays; Under the Hood: The Implementation of Carp's Memory Management System; AST Info, Identifiers, and Deleters; Lifetimes; Lifetimes in Detail; Explicit Lifetime Annotations; Mutation and Lifetime Invalidation; Type Dependencies; Memory State; Custom deletion functions; Related pages
- https://carp-lang.github.io/carp-docs/Memory.html — rendered Memory doc ("it is unsafe to override it")
- https://raw.githubusercontent.com/carp-lang/Carp/master/docs/Drop.md — the `drop` interface, `(Fn [&a] ())`
- http://carp-lang.github.io/Carp/LanguageGuide.html — ownership by static analysis; `ref`/`&`; `@`; `set!`; `Ptr` unmanaged; recursive types via Box/Ptr
- https://github.com/carp-lang/Carp/blob/master/core/Unsafe.carp — `coerce`, `leak`
- https://github.com/carp-lang/Carp/blob/master/core/carp_memory.h — 88 lines; `CARP_MALLOC`/`CARP_REALLOC`/`CARP_FREE`; no bookkeeping outside `LOG_MEMORY`
- https://github.com/carp-lang/Carp/blob/master/src/Memory.hs — 833 lines (796 loc); `manageMemory :: TypeEnv -> Env -> XObj -> Either TypeError (XObj, Set.Set Ty)`; `MemState`; `LifetimeMode`
- https://github.com/carp-lang/Carp/tree/master/core — header inventory (no Lambda struct among `core/*.h`)
- docs/Borrowing.md — **not present on master** (https://raw.githubusercontent.com/carp-lang/Carp/master/docs/Borrowing.md returns HTTP 404); borrowing is documented inside docs/Memory.md instead
- https://github.com/carp-lang/Carp/blob/master/CHANGELOG.md — v0.5.1–v0.5.5 memory entries (#1407 blittable, #1358 Box, #1223 Pointer.address, #1245 delete docs, #1206 Unsafe.C.asm)
- https://github.com/carp-lang/Carp/releases and https://github.com/carp-lang/Carp/releases/tag/v0.6.0 — v0.6.0 dated 2024-03-28; recursive types (#1496); more expressive lifetimes (#1512)
- https://github.com/carp-lang/Carp/commits/master — newest commit 2026-09-11; memory commits through 2026
- https://carp-lang.github.io/Carp/Libraries.html — community library list; carpentry-org
- https://github.com/orgs/carp-lang/repositories — org repo inventory and last-updated dates
- https://github.com/carp-lang/comparisons — example projects, no numbers, last updated 2020-05-06
- https://carp-lang.github.io/carp-website/ — feature claims, no benchmarks

Primary — issues and PRs:
- https://api.github.com/search/issues?q=repo:carp-lang/Carp+borrow+OR+ownership+OR+memory+in:title — issue inventory with labels and dates
- https://api.github.com/repos/carp-lang/Carp/labels — label `memory` = "Borrow checker and lifetimes"
- https://github.com/carp-lang/Carp/issues/1040 — lambda capture double free (open, 2020-12-01)
- https://github.com/carp-lang/Carp/pull/1440 — the resulting prohibition on leaking captured variables
- https://github.com/carp-lang/Carp/issues/997 — free before allocation (open, 2020-11-22)
- https://github.com/carp-lang/Carp/issues/1095 — RFC: `delete` for `Ptr`, add `Leak` (open, 2020-12-23)
- https://github.com/carp-lang/Carp/issues/1065 — match-ref in let, false positive (open, 2020-12-12)
- https://github.com/carp-lang/Carp/issues/1107 — references inside `if` (open, 2020-12-29)
- https://github.com/carp-lang/Carp/issues/1149 and https://api.github.com/repos/carp-lang/Carp/issues/1149/comments — "There is not a good and well though-out plan for threading and concurrency, I'm afraid." (eriksvedang, 2021-01-26)

Primary — authors' own words:
- https://serokell.io/blog/carp-with-erik-svedang — Functional Futures interview with Erik Svedäng, 2022-07-14
- https://news.ycombinator.com/item?id=15778530 — HN thread, 2017-11-25, with eriksvedang comments
- https://blog.veitheller.de/Borrow_Checking,_The_Carp_Way.html — Veit Heller (core maintainer), 2018-01-30 — **stale on lifetimes**
- https://blog.veitheller.de/Carp.html — Heller, 2017

Comparison claim:
- https://borretti.me/article/how-australs-linear-type-checker-works — the 600-line figure, belonging to Austral

Secondary (AI-generated over the repo; used for code location and cross-checked where load-bearing):
- https://deepwiki.com/carp-lang/Carp — Memory Management page and targeted queries (`manageMemory`, `MemState`, deleter kinds, `core/carp_memory.h`, blittable types, absence of Rc/Arc, delete timing, absence of reuse optimization, ~833 lines for `src/Memory.hs`)

Not found (searched, no primary source located):
- Published performance benchmarks or timing numbers for Carp
- Any "~600 lines" or comparable size figure claimed for Carp's borrow checker
- The specific PR/version that first introduced `sig` lifetime-variable syntax
- Any documented treatment of cyclic/graph-shaped data in Carp's docs
- Any list of production applications or large real-world Carp programs
