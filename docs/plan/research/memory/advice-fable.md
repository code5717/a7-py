> **Source:** Claude Fable subagent advisory answer to advice-prompt.md.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim. User decisions are in the [ledger](../../decisions.md).

# A7 memory model: external advisory analysis

Advisor: Fable 5.1 (Claude Code subagent). Date: 2026-09-15. Read-only; no
repository file was modified. No code was run. Every claim about external
languages, papers and compilers below is from training recall and is labeled
as such; nothing external was fetched for this note.

Inputs read in full or in the requested sections: `docs/plan/memory-brainstorm.md`,
`docs/plan/decisions.md`, `docs/plan/README.md`, `docs/SAFETY_CONTRACT.md`,
`docs/SPEC.md` sections 3.3-3.5, 6.2-6.3, 8; `docs/plan/research/memory-design-codex.md`
(full), `docs/plan/research/ownership-zig-odin-glm.md` (full),
`docs/plan/research/memory-security-glm.md` sections 5-7 and 10-11,
`docs/lang-safety/08-decisions.md` D.040-D.053, `docs/lang-safety/comparative/README.md`,
header scans of the comparative studies and `05-for-a7.md`, plus spot reads of
`a7/safety.py`, `a7/backends/zig.py`, `a7/stdlib/`, `a7/parser.py` and
`examples/011_memory.a7`, `025_linked_list.a7`, `040_task_board.a7`.

---

## 0. Facts verified at this tree versus inferences

### Verified (read directly in the working tree)

| # | Fact | Where |
| --- | --- | --- |
| F1 | `ref T` lowers to Zig `?*T` (nullable pointer). | `a7/backends/zig.py` ~2100-2104 |
| F2 | `ref` arguments accept arbitrary lvalues; the backend inserts `&` (`implicit_ref_args`). So one `ref` type covers both a heap owner from `new` and a borrowed stack slot. | `a7/backends/zig.py` ~1661-1666 |
| F3 | One global allocator: `const allocator = std.heap.page_allocator;`. `new` emits `allocator.create(T) catch null` (or `allocator.alloc` for arrays); `del` emits `if (x) |p| allocator.destroy(p)`. No arena, pool, or allocator parameter exists in codegen. | `a7/backends/zig.py` 159, 1301-1306, 1904-1914 |
| F4 | `string` lowers to `[]const u8`; strings are not owning heap values today. | `a7/backends/zig.py` 2087 |
| F5 | The stdlib registry has `io`, `math`, `mem`, `string` only. `mem.py` is 9 lines. No list, map, arena or pool type. | `a7/stdlib/` |
| F6 | The parser has `parse_function_decl_anonymous`, but its own comment says anonymous functions "should have names in declarations", i.e. it is an error path. No closure or capture machinery was found by grep in the passes. Treat closures as absent. | `a7/parser.py` 613-617 |
| F7 | The safety pass is an AST walk with a `FactMap` using `copy_symbols`/`restore_symbols` at joins (snapshot/restore). No CFG or IR exists. Facts: integer intervals, lengths, nil-ness, deleted bindings. | `a7/safety.py` 150-175, 225-300 |
| F8 | Whole-program compilation is the current reality: one Zig file, virtual `std/*`, local file imports fail closed before codegen. | `CLAUDE.md`, `a7/module_resolver.py` description |
| F9 | Recursion (direct, mutual, local function-pointer alias cycles, callback trampolines) is a semantic error. | `docs/SPEC.md` 6.2, `CLAUDE.md` |
| F10 | `examples/025_linked_list.a7` uses `next: isize` with `-1` as the null sentinel. That conflicts with the `usize`-for-indices rule in `CLAUDE.md` and is a small existing drift item. | `examples/025_linked_list.a7` 7, 15 |
| F11 | The ledger locks L15/L17/L18 (no collector, Python-simple, compiler-grouped arenas/pools, storage reuse) and L6 (immutable argument bindings, explicit permission for referent mutation). Gate G2's recommended option (a) keeps `del` and makes heap refs affine. The brainstorm expects `del` (and possibly `new`) to leave ordinary code. These two documents do not yet reconcile. | `docs/plan/decisions.md`, `docs/plan/README.md` G2, `memory-brainstorm.md` session 7 |
| F12 | Codex research recommends "Alternative A: affine owners with scoped access"; GLM recommends "Q1 (a) syntax-free affine refs, reject ref copies"; D.049 (proposed) bans storable borrows and points linked structures at indices. All three converge on the same spine. | research reports, `08-decisions.md` |

### Inferences (my analysis; not verified by running anything)

Everything in sections 1-8 that is not in the table above is inference,
design judgment, or recall. Recall about external work is marked "(recall)".

---

## 1. Is the combined goal achievable? Where exactly does it break?

### Short answer

Yes, for a well-defined and large subset of programs, if A7 accepts three
things: (1) values and containers own; stored cross-references are handles,
never pointers; (2) death that depends on runtime data is expressed by the
user as a container or store operation (which Python users already do:
`list.remove`, `dict.pop`, `del cache[k]`); (3) exactly one class of residual
runtime check is allowed, a handle validity test that yields a typed failure.

The phrase "everything resolved at compile time" must be split into four
different claims, because they have different feasibility:

| Claim | Feasible statically? | Note |
| --- | --- | --- |
| Where each allocation lives (which region/pool) | Yes | Escape and region inference over a DAG call graph (section 2). |
| When each allocation is released | Yes | Scope exit or last use, decided at compile time; no counts, no tracing. |
| How big each allocation is | Sometimes | Static for fixed arrays, struct pools, static-shape tensors; runtime for growable lists, strings, dynamic shapes. Sizes being dynamic does not make release points dynamic. |
| Whether a stored handle still names a live entity | Only when the store never removes | If a store has `remove`, a stale handle is a data-dependent fact. Either forbid `remove` on stores whose handles are stored, or check a generation at use and return a typed failure. |

"No runtime garbage collector and no reference counting as the core" is
compatible with all four rows. What A7 cannot promise is "zero runtime memory
work": free-list push/pop, arena reset, list growth, and generation compares
remain. None of them is a collector, none is proportional to live heap, and
all are deterministic.

### The exact break points

Pure region inference (Tofte-Talpin/MLKit style) as the safety mechanism
breaks in three well-known places; A7's combination of constraints lets each
be handled, but not by regions alone:

1. **Data-dependent death inside a long-lived scope.** A server loop with a
   cache, a game world with entities spawned and killed, a training loop with
   early stopping. Lexical regions can only free at region exit; anything that
   might survive an iteration gets promoted to the enclosing region and is
   retained until that region dies. In MLKit this is the classic "region
   leak" (recall). The fix is not a smarter region inferencer; it is that
   per-entity death is an ownership event (drop of the owner, or store
   removal), and regions only batch the physical frees. Ownership gives
   precision; regions give locality and cheap bulk release.

2. **Shared and cyclic graphs.** Parent pointers, doubly linked lists, DAGs
   of nodes with multiple parents, tape nodes referenced by several tensors.
   Affine ownership cannot express two owners; regions can hold cycles but
   cannot free one node early. The fix is the *store*: one owner (the store)
   for many entities, arbitrary handle-links inside it, bulk release when the
   store dies, slot reuse when entities are removed. This is the Verona/ECS
   idea of "one external owner, arbitrary internal topology" (recall). With
   handles instead of pointers, cycles cost nothing and need no collector.

3. **Escaping borrows.** Returning a slice of a local, storing a `ref` into a
   struct that outlives the referent, a tokenizer returning views into its
   input, closures capturing locals and escaping. Without lifetime
   annotations these cannot be expressed. A7 must either (a) reject them and
   push users to copy or to store handles, or (b) adopt lifetime dependency
   tracking (Codex "Alternative B"). Recommend (a) for v1 with one carve-out
   handled internally: a callee may return a view into a *by-value argument*
   only if the compiler can attach the result to the argument's storage in the
   caller (an internal, non-annotated dependency; see section 4, "tokenizer").
   If that is too much for v1, reject and copy.

Secondary break points:

4. **Dynamic sizes with relocation.** A growing list reallocates. Any pointer
   into it dangles. Since A7 has no public pointers and D.049-style storable
   borrows are absent, the only references into lists are `usize` indices or
   iteration borrows. Iteration borrows plus mutation must be rejected
   (exclusivity). This is cheap to check and easy to explain.

5. **Tasks.** A value sent through a channel must carry its whole reachable
   owned subgraph and must not be allocated from a region that dies with the
   sender. Codex already flagged that "task-private heap" is incoherent
   unless allocator lifetime is handled. Recommendation in section 4.

6. **Native buffers.** A kernel may hold a pointer for the duration of the
   call and, for some libraries, worker threads may still be running after
   return. A7 must model native borrows as call-scoped and treat any library
   that retains pointers as returning an opaque owner with a deleter.

### Least-bad set of restrictions and residual runtime work

Restrictions (compile-time rejections, with fix messages):

- No storable borrows. Struct fields hold values, owned boxes, or handles.
- No escaping closures in v1. Callbacks are direct function arguments.
- Iteration borrows exclude structural mutation of the same container.
- Returning a view into a local is rejected; returning a view into an
  argument is either internally tracked or rejected (v1 decision).
- Global mutable state is owned by the program region; tasks may not touch
  it unless it is immutable after initialization (concurrency gate G7).

Residual runtime work (allowed; none is a collector):

- Allocation and growth can fail: typed result, as `new` returns maybe-nil
  today.
- Free-list push/pop in stores; arena reset at region exit; realloc on growth.
- Generation compare on handles into stores that support `remove`, yielding a
  typed failure. This is the only "check" and it has the same shape as the
  existing nil check, so it does not weaken fail-closed: unproven use is
  rejected unless the user writes the check.
- For dynamic-shape tensors, the step memory plan is computed at runtime by
  a deterministic planner; for static shapes it is computed at compile time.

---

## 2. Strongest candidate architecture

### One-paragraph shape

Value semantics with affine owners give *correctness* (no use-after-free, no
double free, no leak on defined exits). Compiler-inferred regions, pools and
static memory plans give *performance* and are pure lowering choices that
never change behavior. Stores with handles give *sharing and cycles*. The
recursion ban makes the whole thing context-sensitive and fixpoint-free
across functions. Users see values, `List`, `Store`, `Handle`, and nothing
about memory.

### Layers

**Layer 0: value semantics and `Copy` classification.** Structs, arrays,
enums, tagged unions are values. `Copy` is inferred structurally (D.047) but
must be a *semantic* property that resource wrappers can opt out of (Codex
point about a `u64` file handle). Non-`Copy` values move on assignment
between owners. Strings become owning values (breaking change to F4; it is
the single largest ergonomic lever for the "Python feel").

Two rules that must be stated explicitly because the examples depend on them:

- **Default passing.** A by-value non-`Copy` argument is a read-only,
  call-scoped borrow by default. Because bindings are immutable (L6), the
  callee cannot observe whether it received a copy or a reference, so the
  compiler may pass by reference (GLM's R2 point). The compiler infers a
  *consuming* position only when the callee's summary stores the argument
  into an owner (container, store, global, channel, returned value). At such
  a call the caller's binding is moved and later use is rejected. No keyword;
  the summary is the contract, and public signatures must expose it in
  tooling so a body edit that starts consuming is a visible API change.
- **Binding from an element.** `x := container[i]` or `x := store[h]` where
  the element type is non-`Copy` creates a scope-bounded *borrow binding*,
  not a move and not a copy. It cannot escape its scope and it excludes
  structural mutation of the container while live. Owned extraction is
  explicit: `.clone()` for an independent copy, `list.take(i)` or
  `store.take(h)` to move the element out and leave the slot vacant.

**Layer 1: owners and automatic release.** Every non-`Copy` value has exactly
one owner: a local binding, a struct field, a container element, a store slot,
a global. Release happens at the owner's scope exit in reverse declaration
order (D.046), or earlier at the last use when the compiler proves it safe and
profitable and the value holds no native resource (memory-only early release
is unobservable; resource release stays at scope exit or explicit close).
`new` and `del` leave ordinary code: heap boxes appear where the compiler
needs indirection (recursive data via `Store`, large values, escaping
returns), and users never free.

**Layer 2: temporary access.** `ref` parameters (existing surface) and
iteration bindings are call- or loop-scoped borrows. No borrow is storable
(D.049). Exclusivity: while a place is mutably borrowed, no other access to an
overlapping place is allowed (D.044, GLM I-16). Places are `base + field path
+ index/slice projection`, resolved on storage identity, not names.

**Layer 3: region inference (internal).** Each allocation site, in each
calling context, is assigned to the innermost *region* that dominates all its
uses: function frame, loop iteration, task, store, or program. With a DAG
call graph and whole-program visibility, the analysis runs bottom-up in
topological order: each function gets a summary, and each call site
instantiates it. Allocations that escape via return are placed in the
caller's region (the callee receives an implicit region parameter; this is
Tofte-Talpin region polymorphism without the fixpoint, because there is no
recursion). Allocations that do not escape the iteration of a loop go into a
per-iteration region that is reset each pass; this is the "reuse allocated
space" ask, and it is exactly Jai's temporary storage and Odin's
`temp_allocator` made automatic (recall for Jai/Odin).

**Layer 4: pools and stores (internal lowering; `Store` is user-visible).**
Same-type allocations in one region with a dynamic count lower to a typed pool
(slab with free list). A `Store<T>` is a user-visible owner of many `T` that
hands out `Handle<T>`. Handles lower to `u32`/`usize` slot indices, plus a
generation only when the whole program contains a `remove` on that store type
and some handle to it is stored beyond a call (whole-program decision). A
store with no `remove` needs no generations and no checks at all.

**Layer 5: static memory planning and in-place reuse.** For groups whose sizes
are static (fixed arrays, struct pools with known maximum, static-shape tensor
graphs), compute liveness intervals and pack them into one arena with fixed
offsets, as ML compilers do (XLA buffer assignment, TVM USMP, TFLite arena
planner; recall). Because the recursion ban bounds every call chain, this can
be applied beyond tensors: a whole training step, a whole request handler, or
a whole frame update can be planned as one allocation with computed offsets
when its sizes are static. In-place reuse: when an owned value's last use is
as an operand of an operation producing a same-size value, the output reuses
the input's storage. Under affine ownership, uniqueness is static, so this is
Perceus-style reuse without the runtime reference-count test (recall for
Perceus).

**Layer 6: layout selection (SoA).** Only for `Store<T>` and pools, where the
compiler owns the layout and no raw pointer to an element can exist. Fields
become columns; `store[h].x` becomes `x_column[slot]`. Legal because the only
element accesses are handle-indexed and call-scoped borrows. Zig's
`std.MultiArrayList` is a plausible lowering target (recall; verify against
Zig 0.16 API).

### The analyses, precisely

| # | Analysis | Input | Output | Depends on |
| --- | --- | --- | --- | --- |
| A1 | `Copy` classification | types | per-type `Copy` flag with opt-out for resources | none |
| A2 | Definite initialization | CFG | initialized fields/prefixes per point | CFG |
| A3 | Move/affine state | CFG, A1 | live / partially moved / consumed per place | A2 |
| A4 | Place and alias model | CFG, types | storage identity for bases, fields, index and slice projections; overlap decision | A2 |
| A5 | Exclusivity and borrow scope | A4 | each borrow's begin/end; conflicts rejected | A3, A4 |
| A6 | Effect summaries (per function, bottom-up on the DAG) | bodies | reads, writes by place, allocations that escape to return / into `ref` params / into globals, calls, native calls, allocation and failure points | A3-A5 |
| A7 | Escape and region assignment | A6, call graph | region per allocation site per context; region parameters per function | A6 |
| A8 | Liveness (last use) | CFG, A3 | last-use points for early release and reuse | A3 |
| A9 | Size classification | types, shapes | static / symbolic (shape-derived) / dynamic per allocation | A7 |
| A10 | Memory planning | A8, A9 | arena offsets for static groups; runtime planner for symbolic | A7-A9 |
| A11 | Reuse selection | A8, A3 | operand-to-result storage reuse decisions | A8 |
| A12 | Layout selection | store usage | AoS or SoA per store type | A7 |
| A13 | Runtime-check planning | A7, store ops | which handles need generations; where failure results appear | A7 |
| A14 | Cleanup planning | A3, A7 | one ordered release plan per defined exit; no drop cascades (store release is slab release) | A3, A7 |

All of these are iterative-traversal friendly; none needs recursion in the
compiler.

### IR they need

A typed control-flow graph (plan track 4) with:

- stable declaration and storage identities (not names; shadowing and
  generic specialization must keep identities);
- explicit places (base, field path, projection) as the unit of ownership and
  borrow facts;
- explicit sequencing and evaluation order;
- value categories in the style of Swift OSSA: *owned* and *guaranteed*
  (borrowed) operands, with lifetime-ending uses marked (recall);
- per-function summaries attached to declarations and consumed at call sites;
- a region variable per allocation site per context, resolved to a concrete
  region before lowering;
- `BackendPlan` extended so lowering consumes region, pool, layout and reuse
  decisions rather than reconstructing them from AST spelling (this is the
  existing safety-contract rule, generalized).

The existing snapshot/restore joins (F7) are unsound for this and must be
replaced by union/widening at joins (GLM I-10) before any of the above is
trusted.

### How the fixed constraints help

- **Recursion ban** gives a DAG call graph: summaries compute bottom-up with
  no interprocedural fixpoint; region polymorphism is resolved by
  per-call-site instantiation; every allocation's lifetime is a lexical scope
  in a finite unrolling of the program; stack budgets are static; and
  destruction of deep structures never needs a recursive drop because stores
  release as slabs. Function values must resolve to a finite target set for
  summaries to be sound (G4: choose direct-argument callbacks or type-informed
  edges; either works; storing function values in fields makes A6 coarser).
- **Immutable argument bindings, explicit referent permission** shrink the
  mutation surface: a by-value argument cannot leak or be mutated; the only
  channels out of a callee are returns, `ref` parameters, globals and native
  calls. Effect summaries are small and precise.
- **Whole-program compilation** removes unknown callees, so no conservative
  "may escape anywhere" fallback is needed, and store/generation decisions can
  be made from actual program usage.
- **No public address-of/deref** means every reference is compiler-created
  and its scope is known, which is what makes SoA and relocation safe.
- **Explicit-width wrapping integers** are irrelevant to placement but matter
  for sizes: allocation byte counts, strides and offsets must use checked
  arithmetic (already noted by GLM I-9). Keep that rule.

---

## 3. New concepts

### Compiler-internal (never written by users, used in diagnostics)

| Concept | Definition | Lowering | Diagnostic use |
| --- | --- | --- | --- |
| **Region** | A lifetime scope that owns allocations: frame, iteration, task, store, program | arena (bump) or nothing when all members are stack-promoted | "this value's lifetime is the loop iteration" |
| **Allocation site (in context)** | Source expression that creates storage, specialized per call context | pool member, arena member, or stack slot | "allocated here, escapes there" |
| **Place** | Storage identity: base + field path + projection | address computation | "already mutably borrowed at line N" |
| **Escape point** | Return, global store, channel send, native call, closure capture | move, copy, or region parameter | "cannot return a view of a local; return the value" |
| **Pool** | Same-type members of one region with dynamic count | slab + free list; SoA optional | shown only in `--doc-out` reports |
| **Generation** | Slot reuse counter, present only when needed | `u32` alongside slot | "handle may be stale; check with `store.get(h)`" |

### User-visible (proposed; needs approval with examples)

| Concept | Why users must see it | Python analogue |
| --- | --- | --- |
| `List<T>` | Growable owned sequence; the workhorse | `list` |
| `Map<K, V>` | Owned dictionary | `dict` |
| `Store<T>` | Owner of many entities with stable identity, removal, and cross-links | a `dict[int, T]` plus ids, or an ECS registry |
| `Handle<T>` | Stable identity into a store; storable in fields; `usize`-backed | an id key |

That is the entire user-visible surface. Arenas, pools, regions, layouts and
generations are not user concepts in v1. A single optional hint may be
justified later (see section 5), not now.

### Critique of the draft names

- **Lifetime group** → use the established word *region* internally. "Group"
  invites confusion with type groups and with `@type_set`. Users never see it.
- **Family** → this is a typed pool. "Family" implies inheritance to most
  readers. Internally: *pool*. The user-visible thing is `Store<T>`.
- **Home** → keep only as diagnostic vocabulary ("the home of this value is
  the loop iteration"). It reads well in messages. Do not make it a type or
  keyword.
- **Link** → rename to *handle*. "Link" collides with linked lists, hyperlinks,
  and linker terminology.
- **Boundary** → *escape point* internally; "boundary" is fine in prose but
  too vague as an analysis term because native boundary and task boundary are
  different things.

Net: two user-visible nouns (`Store`, `Handle`) beyond ordinary containers, and
four internal nouns (region, pool, place, escape point).

---

## 4. Hard cases

Each entry: mechanism, what the user writes, what remains at runtime.

**Returning allocations.** The callee's escaping allocation is placed in the
caller's region via an implicit region parameter; ownership moves to the
caller's binding. User writes `ret values`. Runtime: none beyond the allocation.
If the caller's binding is itself in a per-iteration region, the returned
value is freed at iteration end without any call to free.

**Growing lists with references into them.** No references into lists exist;
positions are `usize`. Iteration is a borrow of the list; `list.push` during
`for item in list` is rejected: "cannot grow `list` while iterating it; push
into a separate list, or iterate by index". Growth relocation is invisible.
Runtime: realloc on growth with typed failure.

**Cyclic graphs and parent pointers.** `Store<Node>`; `Node.parent:
?Handle<Node>`, `Node.children: List<Handle<Node>>`. Cycles are handles.
Freeing a subtree = removing its nodes (an explicit iterative walk with a
worklist, no recursion). Dropping the store releases columns in one call.
Runtime: generation compare only if the program removes nodes and stores
handles; otherwise pure indexing.

**Caches and globals.** A global `Map` or `Store` lives in the program region.
Eviction is a `map.remove(k)`; the removed value is dropped then. Nothing is
inferred about data-dependent death; the user expresses it as they would in
Python. Globals participate in effect summaries (any call that may write a
global invalidates facts about it). Under G7, tasks may read globals only if
they are immutable after initialization or protected by a task-owned handoff.

**Closures.** v1: none. Callbacks are direct function-value arguments; their
captures are the arguments the user passes explicitly. Later: closures own
their captures by move, and a closure that consumes a capture is callable
once; escaping closures then become ordinary owned values with an inferred
region. Do not add closures until stores and lists are qualified.

**Long-running loops and servers.** The loop body is an iteration region;
anything not escaping the iteration is bulk-released at the end of each pass.
Anything that must survive is moved into a loop-level or program-level owner
(a list, a map, a store), which the user writes naturally ("append to the
results", "put in the cache"). No promotion of loose values to outer regions
is ever performed silently, so no region leak is possible: the choice is
either the value is owned by something longer-lived, or it dies. Peak memory
per iteration is the region high-water mark, which is stable after warm-up.

**Entity removal.** `store.remove(h)` pushes the slot to the free list and
bumps the generation. Removal during iteration: reject `store.remove` inside
`for h in store`, and offer `store.retain(pred)` or a two-phase pattern (collect
handles to remove in a `List<Handle<T>>`, remove after the loop). Stale-handle
use after removal is either statically impossible (no stored handles) or a
typed `store.get(h)` returning maybe-nil that the user must check, exactly
like `new` today.

**Tensors with views and the autodiff tape.** Adopt Codex T1 (session owns
storage) and read it as a region structure: a *model region* (parameters,
optimizer state, RNG) outlives a *step region* (activations, saved values,
tape nodes, gradients). Tensors are owned values whose storage lives in one
of those regions; views are call-scoped borrows of storage plus a descriptor,
never storable across statements unless materialized. Tape nodes reference
tensors by handle into the step region's store. Mutation of a saved value:
when the step body is a static graph (no data-dependent control flow over
tensor ops), the compiler knows every saved value and rejects conflicting
mutation statically; otherwise a version counter check before mutation
returns a typed conflict. Static shapes: the step's memory plan (offsets in
one arena) is computed at compile time; peak memory is minimal by interval
packing; this is where the "next generation" claim is strongest and also most
directly measurable. Dynamic shapes: the same planner runs once per distinct
shape signature at runtime, deterministically.

**Optimizer state and checkpoints.** Live in the model region, owned by a
model value. Checkpoint save serializes; load builds new values in the model
region and moves them into place, dropping the old ones. Skipped steps leave
the model region untouched because nothing crosses from the step region
except through explicit `apply_update` moves.

**Tasks and channels.** Two-tier allocation: task-local scratch regions (bump,
reset per task or per iteration) and one global heap for transferable values.
Rule: a value may be sent only if its whole owned subgraph lives in the global
heap or is moved there at send (the compiler decides placement by looking at
whether the allocation site's value can reach a send; whole-program makes
this decidable). Handles into a task-local store may not cross; the store
itself may be sent as a whole. Failed send returns the value to the sender
(Codex table). Allocator state is never task-private for sendable data, which
resolves the D.050 incoherence.

**Native kernel buffers.** A7-owned storage is borrowed for the call; the
call is an escape point with a summary "reads a, writes c, no retention". Any
library that retains pointers or spawns workers past return is wrapped as an
opaque owned handle with a deleter and a documented completion point; its
buffers are excluded from relocation, SoA and per-iteration reset. Workspace
buffers are ordinary allocations in the step or iteration region. Foreign
imports (DLPack-style) are owners with a foreign deleter and cannot enter
pools.

---

## 5. When inference fails

### What can actually fail

Under this architecture, "the compiler could not place this value" is rare,
because every value has an owner and placement follows the owner. The real
rejection classes are:

1. A borrow escapes: returning a slice of a local, storing a `ref`.
2. An exclusivity conflict: mutation during iteration; two overlapping
   mutable `ref` arguments.
3. A handle use that may be stale and is not checked.
4. A value that must cross a task boundary but whose subgraph cannot be
   moved (holds a task-local handle or a native borrow).
5. Size arithmetic that cannot be proven in range.

### The fallback that keeps the Python feel

Reject with a precise diagnostic that names the fix, and provide the fix as a
library operation. Never fall back to a runtime collector, never silently
promote to program lifetime (that is a leak by another name), never silently
copy (Codex is right that silent copies break predictability). Python users
never see rejections, so A7 will feel stricter than Python on these five
classes; the corpus (section 7) measures how often they occur in idiomatic
code. If the answer is "rarely, and the message is good", the feel survives.

Example diagnostic (proposed wording):

```
error[E-memory-escape]: `head` is a view into the argument `line`; A7 cannot
express that a returned value depends on the caller's storage
  --> parse.a7:12:9
   |  ret head
   |      ^^^^ view whose storage belongs to the caller
help: return an owned copy: `ret head.to_owned()`
help: or return positions: `ret Span{start: 0, end: n}` and slice in the caller
```

(When the view is into a *local* rather than an argument, the message is the
simpler "view of a value that dies when `parse` returns".)

### Optional hints

None in v1. If the corpus shows a recurring case where the compiler picks a
worse-but-safe placement (for example, keeping a large scratch value in the
frame region when the user knows it is per-iteration), a single attribute
such as `@scratch` on a binding could be considered, with the rule that hints
can only restrict lifetimes, never extend them, so a wrong hint produces a
compile error rather than a dangling reference. Do not design this before the
corpus exists.

---

## 6. Prior art (all from recall; verify before citing in docs)

| Work | Directly usable | Trap |
| --- | --- | --- |
| Tofte and Talpin, "Region-based memory management" (1994/1997); MLKit; Birkedal, Tofte, Vejlstrup "From region inference to von Neumann machines via region representation inference" (POPL 1996) | The region calculus, region parameters on functions, storage-mode analysis (whether a region can be reset in place), region representation inference (finite vs infinite regions, which is A7's stack-slot vs arena decision) | Region leaks in long-running loops and with data-dependent death; the interprocedural fixpoint and region polymorphism that A7 avoids only because of the recursion ban; ML's immutable data made it easier |
| Aiken, Fähndrich, Levien, "Better static memory management: improving region-based analysis of higher-order languages" (PLDI 1995) | Decoupling region *deallocation* from lexical scope using liveness; this is the basis for early release inside a region | Complexity; A7 can get most of it from last-use liveness under ownership |
| Cyclone (Grossman, Morrisett, Jim, Hicks, Wang, Cheney, PLDI 2002; later "unique pointers" and dynamic regions) | The taxonomy: stack regions, lexical regions, heap, dynamic regions; region-typed pointers with inference inside functions | Annotation burden at function boundaries; A7 must keep regions internal |
| ASAP, Raphael Proust, PhD thesis, University of Cambridge (2017), "ASAP: As Static As Possible memory management" | The framing "static deallocation by default; whole-program access/shape analysis inserts frees"; the honest conclusion that a residual runtime scan is needed for some shapes | That residual scan is a collector in disguise; general shape analysis is expensive. A7 avoids it by making shared shapes live in stores |
| Lobster (van Oortmerssen), "memory management via ownership inference" | Evidence that inferring owner vs borrow from usage in a Python-like language works without annotations; its lifetime analysis removes most RC ops | Core is reference counting; violates the fixed constraint |
| Koka / Perceus (Reinking, Xie, de Moura, Leijen, PLDI 2021); "Reference counting with frame-limited reuse" (Lorenzen, Leijen, ICFP 2022); FBIP | Reuse analysis (a dead value's cell is reused for a new value of the same size), drop specialization, the "functional but in place" programming idiom | RC core; uniqueness is dynamic there, static in A7 |
| Hylo (formerly Val); Racordon, Abrahams et al., "Implementation strategies for mutable value semantics" (2022) | Mutable value semantics, no storable references, projections/subscripts as call-scoped access, `inout` exclusivity | Immature implementation; keyword surface A7 does not want; still needs lifetime reasoning for local views |
| Vale (Evan Ovadia), generational references, "region borrowing" | Generation check as the one permitted runtime test, applied only to handles into stores with removal; the observation that an immutable region needs no checks | Vale checks every dereference; alpha status; region borrowing was not shipped when last recalled |
| Swift OSSA (ownership SSA in SIL), SE-0377/0390/0446 | The IR design: owned vs guaranteed values, lifetime-ending uses, borrow scopes as explicit instructions; nonescapable types (SE-0446) as a model for call-scoped views | ARC and copy-on-write are the runtime substrate |
| Rust NLL and Polonius; MIR places and drop elaboration | Liveness-based end of borrows, the place model (move paths, projections), drop elaboration on every exit | Lifetime annotations and variance; do not import the type-level machinery |
| Go escape analysis (cmd/compile, data-flow over locations); HotSpot/Graal partial escape analysis (Stadler, Würthinger, Mössenböck, CGO 2014) | Stack promotion decisions; partial escape (materialize only on the escaping path) | Both assume a GC backstop for the escaping case |
| Verona (Microsoft Research) regions; ownership types (Clarke, Potter, Noble, OOPSLA 1998), owners-as-dominators | The store concept: one external owner, arbitrary internal references, bulk release; region-as-unit-of-transfer between concurrent owners | Verona is research; ownership types need annotations |
| Entity component systems (EnTT, Bevy ECS), slotmap and generational-arena crates | Practical `Store<T>` / `Handle<T>` designs, generation width, free-list details, SoA storage | Generation exhaustion must be defined (Codex note); do not wrap |
| ML compiler memory planners: XLA buffer assignment and heap simulator; TVM graph plan memory and USMP; TensorFlow Lite arena planner; MLIR one-shot bufferization and buffer deallocation; Checkmate (Jain et al., MLSys 2020) for rematerialization | Interval packing given static shapes; liveness over a DAG; the shape-signature cache for dynamic shapes | All assume a closed DAG of kernels; general A7 code needs the recursion ban and static sizes to be in the same regime |
| Jai temporary storage (`temp`, per-frame reset); Odin `context.temp_allocator` and `free_all`, dynamic arrays carrying allocators; Zig `ArenaAllocator`, `std.heap.MemoryPool`, `std.MultiArrayList`, `std.ArrayList` | The per-iteration region idiom as the default; Zig types as direct lowering targets for region, pool, SoA store, list | Jai has no public spec; Zig 0.16 allocator API changed and must be verified in the shipped toolchain; none of these provides the safety analysis |
| Austral; Carp; Neut | Evidence that a tiny linear/affine checker without annotations is implementable; Carp infers ownership and borrows in a Lisp; Neut inserts copies statically | Small communities; copy insertion in Neut can hide allocations |
| Ada/SPARK ownership pointers (SPARK 2014+) | Formal, annotation-light ownership in production tooling; the discipline of "proof or typed result" | Ada's access-type surface is far larger than A7 wants |

Two traps to state in the plan explicitly: any design whose core is reference
counting (Lobster, Perceus, Swift) is excluded by the fixed constraint even if
its reuse ideas are borrowed; and any region system that promotes escaping
values to an outer region (MLKit) must be paired with ownership so promotion
is never silent.

---

## 7. Critique of `docs/plan/memory-brainstorm.md`

### Missing

1. **Reconciliation with G2 and the D.04x cluster.** The brainstorm treats
   memory as a fresh exploration while G2 recommends affine `ref` plus
   `del`. The brainstorm should be the design input to G2, not a parallel
   track; state that G2 option (a) is the correctness spine and this plan
   adds the inference layers on top. Otherwise the user is asked to approve
   `del` semantics that the memory model will remove.
2. **Values as the base.** The plan never says that structs, arrays and
   strings are owning values. This decision (strings especially, F4) does more
   for the Python feel than any arena inference. Add it to session 1.
3. **What users still must do.** The contract session lists "no free in user
   code" but not the honest counterpart: users still remove entries from
   containers and stores, and still close native resources. Write that
   sentence; it is what makes the goal achievable.
4. **Storable references decision.** D.049 (no storable borrows) versus the
   accepted `ref` struct fields (SPEC 3.3). The brainstorm must pick;
   everything in sections 2-4 above assumes D.049 plus handles.
5. **The IR prerequisite.** Track 4 (typed CFG) and GLM I-10 (sound joins)
   are not mentioned. Every analysis in section 3 of the brainstorm needs
   them. Add a dependency line.
6. **Corpus gaps.** Add: string building in a loop; a map/dictionary
   workload; a tokenizer returning views into its input; a function that
   conditionally stores its argument in a global registry; swap of two
   elements by index (exclusivity); allocation failure with early return and
   cleanup; a sort with a comparator callback (function values, G4).
7. **A manual baseline.** "Peak memory versus an ideal manual version"
   requires writing that manual version. Write it in Zig for five programs
   only.

### Mis-ordered

- Session 1 (contract) cannot be settled before session 2 (corpus): the
  contract's acceptable-rejection rate is an empirical question. Run them
  together; write the corpus first, then the contract with corpus references.
- Session 6 (feasibility spikes) is too late. Hand-trace the two riskiest
  analyses (escape/region over the DAG; iteration exclusivity) on five corpus
  programs by session 3. If either fails on paper, the mechanism survey
  changes.

### Unnecessary or mislabeled

- "Compile-time RC elision" is not a candidate under the fixed constraint;
  keep only its reuse idea under "In-place reuse".
- "Hidden handles with generation checks" and "Layout transformation" are
  mechanisms that follow from choosing stores; they are not competing
  candidates. Fold them under "Inferred pools".
- "Allocation elision and fusion" is an optimization that falls out of
  region inference plus static planning; do not score it separately.
- The evaluation metric list should put "programs rejected, and the quality
  of the fix message" first; it is the metric that decides whether the
  Python-feel promise holds.

### Corpus programs that falsify a design fastest (write these first)

1. Request loop with a cross-request LRU cache: tests data-dependent death,
   long-running regions, eviction as user action.
2. World update with entity spawn and removal during iteration: tests
   exclusivity, stale handles, two-phase removal, store bulk release.
3. Training loop with checkpoint every N steps and early stop: tests step
   region versus model region, tensor escape from the step, saved-value
   mutation policy.
4. Callee returning a variable-length list built from its input: tests
   caller-region placement and moves.
5. Tree with parent handles and subtree deletion: tests cycles, worklist
   deletion without recursion, generation need.
6. Tokenizer returning spans or views into its input: tests the one
   escaping-view carve-out; decides Alternative A vs B for v1.
7. String builder in a loop: tests owning strings, temporaries, per-iteration
   reuse and growth.
8. Producer/consumer over a channel with a struct owning a list: tests
   subgraph transfer and allocator tiers.
9. Matmul through a BLAS call with a workspace: tests native borrow
   summaries and workspace placement.
10. Conditional store of an argument into a global registry: tests escape
    through globals and effect summaries.

---

## 8. Concrete A7 examples (all PROPOSED syntax; not supported today)

Conventions: no recursion, `usize` indices, no `&` or `*`, no `new`/`del` in
ordinary code, `ret` for return. Container and store APIs are placeholders.

### 8.1 Values die with their scope; returning moves

```a7
// PROPOSED
Point :: struct {
    x: f64
    y: f64
}

make_points :: fn(count: usize) List<Point> {
    points := List<Point>.new()          // owned by `points`
    for i: usize = 0; i < count; i += 1 {
        p := Point{x: 1.0, y: 2.0}       // value; no allocation
        points.push(p)                   // p moves into the list
    }
    ret points                           // list moves to the caller;
                                         // storage was placed in the caller's region
}

main :: fn() {
    pts := make_points(1000)
    io.println("{}", pts.len)
}                                        // pts released here; nothing written by the user
```

### 8.2 Per-iteration reuse in a long-running loop

```a7
// PROPOSED
serve :: fn(conn: Connection, cache: ref Map<string, Response>) {
    while true {
        request := conn.read_request()   // owned; lives in this iteration's region
        if request == nil { ret }
        key := request.path.to_owned()   // owned string
        hit := cache.get(key)            // call-scoped borrow of the map entry
        if hit != nil {
            conn.write(hit)
            continue                     // request, key released; region reset, no free calls
        }
        response := build_response(request)
        conn.write(response)             // read-only borrow for the call
        cache.insert(key, response)      // consuming position: key and response move
                                         // into the map; the compiler places them in
                                         // the map's region, not the iteration's.
                                         // `key` and `response` are unusable after this line.
    }
}
```

The compiler's report for this function (from `--doc-out`) would say:
region `iteration` holds `request`, temporaries of `build_response`; region
`cache` (owned by the caller) holds `key`, `response`.

### 8.3 Store and handles: a tree with parent links, no recursion

```a7
// PROPOSED
Node :: struct {
    name: string
    parent: ?Handle<Node>
    children: List<Handle<Node>>
}

build :: fn() Store<Node> {
    nodes := Store<Node>.new()
    root := nodes.add(Node{name: "root", parent: nil, children: List<Handle<Node>>.new()})
    child := nodes.add(Node{name: "leaf", parent: root, children: List<Handle<Node>>.new()})
    nodes[root].children.push(child)     // cycle root <-> child through handles; fine
    ret nodes
}

depth_sum :: fn(nodes: ref Store<Node>, start: Handle<Node>) usize {
    total: usize = 0
    work := List<Handle<Node>>.new()
    work.push(start)
    while work.len > 0 {
        h := work.pop()
        total += 1
        for c in nodes[h].children {     // borrow of one entity, call-scoped
            work.push(c)
        }
    }
    ret total
}
```

Because no `remove` is called on `Store<Node>` anywhere in this program, the
compiler lowers `Handle<Node>` to a plain slot index and inserts no checks.
Dropping `nodes` releases every node at once.

### 8.4 Entity removal with a stale-handle check

```a7
// PROPOSED
World :: struct {
    entities: Store<Entity>
}

update :: fn(world: ref World) {
    dead := List<Handle<Entity>>.new()
    for h in world.entities {            // iteration borrows the store
        e := world.entities[h]           // borrow binding; no `.get` needed: handles
                                         // yielded by the store's own iteration are
                                         // valid because the borrow excludes `remove`
        if e.hp <= 0 {
            dead.push(h)                 // allowed: pushing to another list; Handle is Copy
        }
    }
    for h in dead {
        world.entities.remove(h)         // allowed: iteration ended
    }
}

target_name :: fn(world: ref World, target: Handle<Entity>) string {
    e := world.entities.get(target)      // maybe-nil because the program calls `remove`
    if e == nil {                        // on Store<Entity> and `target` came from outside
        ret "gone".to_owned()            // an iteration borrow
    }
    ret e.name.clone()                   // explicit copy out of a borrow binding
}
```

If `target_name` wrote `world.entities[target].name` directly, the compiler
would reject it: "handle may be stale because `Store<Entity>` supports
`remove`; use `entities.get(h)` and check for nil".

### 8.5 A rejected program and its fix

```a7
// PROPOSED (rejected)
grow :: fn(items: ref List<i32>) {
    for x in items {
        items.push(x * 2)                // error: cannot grow `items` while iterating it
    }
}

// PROPOSED (accepted)
grow :: fn(items: ref List<i32>) {
    n := items.len
    for i: usize = 0; i < n; i += 1 {
        items.push(items[i] * 2)         // index access, no live iteration borrow
    }
}
```

### 8.6 Returning an owned copy instead of an escaping view

```a7
// PROPOSED (rejected)
first_word :: fn(line: string) string {
    ret line[0..find_space(line)]        // error: view into the argument `line`; the
                                         // result would depend on the caller's storage,
                                         // which A7 cannot express without lifetimes
}

// PROPOSED (accepted, copy)
first_word :: fn(line: string) string {
    end := find_space(line)
    ret line[0..end].to_owned()
}

// PROPOSED (accepted, positions)
Span :: struct { start: usize, end: usize }
first_word_span :: fn(line: string) Span {
    ret Span{start: 0, end: find_space(line)}
}
```

### 8.7 Training step with a step region and a model region

```a7
// PROPOSED
Model :: struct {
    w1: Tensor<f32>
    w2: Tensor<f32>
    opt: AdamState
}

train_step :: fn(model: ref Model, batch: Batch) f32 {
    h := relu(matmul(batch.x, model.w1))     // activations: step region
    logits := matmul(h, model.w2)
    loss := cross_entropy(logits, batch.y)
    grads := backward(loss)                  // tape and saved values: step region
    apply_update(model, grads)               // moves new parameter values into the model region
    ret loss.item()
}                                            // step region released as one block

train :: fn(model: ref Model, data: Dataset, steps: usize) {
    for s: usize = 0; s < steps; s += 1 {
        batch := data.next()
        loss := train_step(model, batch)
        if s % 100 == 0 {
            save_checkpoint(model, s)        // reads the model region only
        }
        if loss < 0.01 { ret }
    }
}
```

With static shapes the compiler emits one arena for the step with computed
offsets for `h`, `logits`, `loss`, saved values and `grads`, packed by
liveness. `relu(matmul(...))` reuses the matmul output in place because it is
the last use of a uniquely owned value.

### 8.8 Sending an owned subgraph through a channel

```a7
// PROPOSED
Job :: struct {
    id: u64
    payload: List<u8>
}

producer :: fn(out: Sender<Job>) {
    for i: u64 = 0; i < 10; i += 1 {
        job := Job{id: i, payload: read_payload(i)}   // placed in the transferable heap
        sent := out.send(job)                          // job moves; `job` unusable after
        if !sent.ok {
            ret                                        // failed send returned the job in sent.unsent; dropped here
        }
    }
}
```

The compiler places `job` and its `payload` in the transferable tier because
the allocation site reaches a `send`; a `Handle` into a task-local store in
`Job` would be rejected: "cannot send a handle into `Store<Entity>` owned by
this task; send the store or copy the entity".

---

## 9. Summary of recommendations

1. Make the spine explicit: value semantics plus affine owners for
   correctness; regions, pools, planning and layout as behavior-preserving
   lowering. Fold this into G2 rather than running the brainstorm beside it.
2. Add two user-visible nouns, `Store<T>` and `Handle<T>`, alongside ordinary
   `List`/`Map`; make `string` an owning value. Everything else stays internal.
3. Permit exactly one runtime check class (stale handle to a store with
   removal, typed result) and no collector, no counts, no silent promotion,
   no silent copies.
4. Build the typed CFG with places and effect summaries first (track 4, GLM
   I-10); no memory analysis is trustworthy on the current snapshot/restore
   walker.
5. Exploit the recursion ban deliberately: bottom-up summaries, per-call-site
   region instantiation, static planning of whole steps and frames, slab
   release instead of drop cascades.
6. Write the ten falsifying corpus programs before the contract, and
   hand-trace escape inference and exclusivity on five of them before any
   mechanism scoring.
7. Fix `examples/025_linked_list.a7` (`isize` index with `-1`) when the
   handle model lands; it is the shape the `Store` concept replaces.
