> **Source:** Grok CLI single-turn advisory answer (grok -p) to advice-prompt.md.  
> **Date:** 2026-09-15.  
> **Status:** Advisory. Body preserved verbatim, including the opening progress narration. The output contains multiple drafts with repeated sections, preserved as reviewer evidence. Read the [synthesis](synthesis.md) for the consolidated recommendations. User decisions are in the [ledger](../../decisions.md).

I'll start by reading the required plan, decision, and spec documents so the advice is grounded in A7's actual constraints.Next I’ll pull the spec memory sections and the research notes that the plan depends on.I’ll pull the remaining ownership research, comparative notes, and current memory examples so the architecture advice is specific.I have enough of the plan and research. Next I’ll check the compiler IR shape and a few remaining safety notes so the architecture advice is concrete.The combined goal is achievable for a large, useful fragment of A7, and not achievable as a general replacement for a garbage collector. The defensible slogan is not “GC at compile time.” It is: **the compiler is the allocator**. Users write values, tables, and loops. The compiler assigns every allocation a home, a layout, and a reuse schedule. If it cannot, the program does not compile.

That is next-generation compiler technology if you ship it. It is not Python’s object model.

---

## Facts I verified vs inferences

**Verified by reading the cited documents** (I did not run the compiler, did not execute programs, and did not re-check GLM’s code-level findings at this HEAD):

- L15 / L17 / L18 lock automatic, compile-time, data-oriented memory with a Python-simple surface, compiler-grouped arenas/pools, and reuse. No GC and no RC as the core.
- Current public surface is `new` / `del` / `defer del` / `ref` / `nil`. SPEC §8.4 and the safety contract both say ownership, escape, and complete double-free analysis are not implemented.
- Argument bindings are immutable; `ref` parameters mutate caller storage. No public `&` / `*`. Source recursion is a compile-time error.
- G2 currently recommends syntax-free affine refs first, then parameter modes, then regions. Track 6 (memory) depends on G2 and proof repair.
- Existing examples already encode graphs as tables plus indices: `examples/025_linked_list.a7` uses `next: isize`; `examples/026_binary_tree.a7` uses `left`/`right: usize` and an explicit stack.
- `05-for-a7.md` §3.3 claims “No recursion → no cyclic ownership graphs.” That claim is false as stated (see §2).
- Cluster CC in `08-decisions.md` (parameter-mode keywords, “no storable refs”) is **PROPOSED**, not locked. L6 explicitly does not approve mode syntax.

**Inferences** below are expert judgment from that reading plus the standard literature. Treat them as advice, not as verified A7 behavior.

---

## 1. Is the combined goal achievable? Where it breaks

**Yes, if “like GC” means: no `del`, no named allocators, no lifetime annotations, deterministic bulk free, and Python-shaped code for trees, tables, scratch, and tensor steps.**

**No, if it means: arbitrary object identity, interior pointers, cycles, caches, and “this lives until nobody uses it” — with the compiler still proving exact free points and never holding memory too long.**

That second reading is undecidable for general programs. Every known system that looks automatic does at least one of:

| Escape hatch | What it really does | A7-legal? |
| --- | --- | --- |
| Restrict the language | Ban stored aliases, cycles, or escaping views | Yes, and required |
| Hold memory longer | Region/arena dies later than last use | Yes; this is the main residual cost |
| Keep runtime work | GC, RC, generation checks, or exclusivity traps | GC/RC forbidden as core. Typed lookup failure and allocation failure are allowed |
| Ask the user | Annotations, arenas, `clone`, `del` | Allowed only as rare hints, not the ordinary surface |

### Where it breaks, exactly

These are the hard boundaries. They are not implementation bugs.

1. **Independent lifetimes inside one growing structure.** A list that reallocates, plus a stored index/view into an element, is the C++ `vector` invalidation problem. Compile-time exact free of the *element* while the *list* lives is not possible without uniqueness proofs that growing lists do not have.

2. **Cyclic identity graphs.** Parent pointers, undirected graphs, object caches keyed by identity. Affine ownership cannot express “two live names for one object.” Region inference can keep the whole graph until the region dies, which is coarse. Tracing GC solves this by doing runtime work you have forbidden.

3. **“Until nobody uses it.”** Last-use deallocation for an arbitrary heap graph is the same problem as GC, just asked of the compiler. Whole-program analysis can do it for first-order, non-escaping, non-cyclic data (ASAP, MLKit). It cannot do it for open-ended servers, plugins, or data whose last use depends on runtime input in a way that is not region-shaped.

4. **Long-running loops with sparse deletion.** A game world or a connection table needs slot reuse. That is not a region. It is a pool with free-lists. Stale handles are a dynamic fact unless you ban reuse or check generations.

5. **Escaping views.** Returning `buf[0..n]` of a local, storing a slice in a heap object, capturing a local in a closure that outlives the frame. Hylo/Val reject stored references for this reason. A7 already has storable `ref` fields and slices (SPEC §3.3). That surface and L17 are in conflict until you split “owner” from “temporary view.”

6. **Mutation of storage that another value depends on.** Autodiff saved tensors, string/slice views, and tensor views of the same buffer. This is not a free-time problem; it is an aliasing + version problem.

### Least-bad restriction set (the actual contract)

Promise this, and only this:

- Ordinary code never writes `new`, `del`, or an allocator name.
- No tracing collector and no reference counts on the fast path.
- Every allocation is assigned a **home** at compile time (call, loop iteration, task, module, training session).
- Allocations that die with their home are grouped into one arena or one typed table.
- Values and owned containers move; temporary views last for the current statement or call only.
- Relationships that are not ownership are `usize` slots into a table.
- When the compiler cannot assign a home, it **rejects** the program. It may also **promote** to a strictly longer, still-static home (hold memory longer). It never leaks silently and never inserts a collector.
- Residual runtime work that stays fail-closed:
  - allocation failure as a typed result (`?T` / `Result`)
  - table lookup of a slot as `?T` (missing or generation mismatch)
  - native/FFI as an explicit trust boundary
- Not promised: exact last-use free of every object; cycle collection; unbounded caches that shrink themselves; “no memory held longer than necessary.”

That last bullet is the honesty tax. MLKit, Cyclone, and every arena system pay it. Jai/Odin/Zig pay it by making the programmer name the arena. A7 pays it inside the compiler.

“Resolved at compile time” should mean **placement, layout, and bulk release are decided before codegen**, not **zero runtime memory work**. Allocation, growth, and slot lookup remain runtime. Peak memory is predictable per home, not globally minimal.

---

## 2. Strongest candidate architecture

Do not pick one mechanism from the brainstorm catalog. Stack them. The order is the design.

```
User program (values, tables, loops, tensors)
        │
        ▼
[1] Typed CFG + storage identity IR
        │
        ▼
[2] Classification: Copy / Own / View / Slot
        │
        ▼
[3] Escape + home inference          ← Tofte–Talpin, adapted to a DAG
        │
        ▼
[4] Cohort grouping → arena or typed table
        │
        ▼
[5] Uniqueness / liveness            ← Perceus reuse without RC
        │
        ▼
[6] Static buffer packing            ← ML-compiler memory planner
        │
        ▼
[7] Optional SoA / fusion            ← behavior-preserving
        │
        ▼
BackendPlan → Zig (arenas, tables, stack, checked sizes)
```

### Layer-by-layer

**[1] IR.** Track 4 already calls for typed IR, CFG, identities, and effect summaries. Memory work cannot live on the current AST walk. `SafetyProofPass` is name-keyed, restores facts by snapshot, and has no points-to or escape information (documented in the GLM advisory and SPEC §8.4). You need:

- Stable **storage IDs** (allocation instance, not variable name).
- SSA or explicit sequencing for locals.
- Projections: field, index, slice, tensor view (offset/stride/dtype).
- Effect summaries on functions: reads, writes, resize/invalidate, consume, allocate, capture, send, native.
- Home annotations on allocations and on types of owned containers.
- A cleanup plan per CFG exit, consumed by codegen. Codegen must not rediscover ownership.

**[2] Classification.** Every type is one of:

| Kind | Meaning | User spelling |
| --- | --- | --- |
| Copy value | `i32`, `f64`, small structs of Copy | ordinary |
| Owner | string, list, tensor buffer, file, task, table | ordinary; compiler drops |
| View | slice, tensor view, `ref` parameter | temporary; cannot be stored in an owner that outlives the source |
| Slot | `usize` (optionally with generation) into a table | `id` or just `usize` |

This is Hylo’s “references are not values,” plus Jai/Odin’s “entities are indices,” plus Zig’s “allocators are real” — with the allocator hidden.

**[3] Escape analysis and home inference.** For each allocation, compute the earliest home that covers every use:

- Does not escape the statement → stack / SSA temporary.
- Does not escape the call → callee frame or caller-provided out-storage.
- Escapes the call but not the caller’s home → allocate in the caller’s arena (return-owned, or region-polymorphic).
- Used across loop iterations but not after the loop → loop-home arena, reset each iteration or reused in place.
- Used for the process lifetime → module home (static / long arena).
- Used for a training step / request / task → that home.

This is Tofte–Talpin region inference, with two A7-specific simplifications:

- The call graph is a DAG once G4 is closed. Region nesting is well-founded. You do not need recursive region types for recursive functions.
- There are no user pointers, so the only aliases are: copies of owners (must become moves), views, and slots.

**[4] Cohorts and tables.** Allocations that share a home *and* die together become one arena. Allocations that share a home *and* a type, and are addressed by slots, become one typed table (pool). This is the L17 “compiler groups stuff into arenas and pools” mechanism. Users do not name them.

**[5] Uniqueness and in-place reuse.** When an owner is dead after a consuming update (`xs = xs.append(v)` or `x = f(x)`), reuse its storage. This is Perceus/FBIP **without** keeping RC as the model. Uniqueness is a proof: no live view, no other owner, no saved autodiff dependency. If uniqueness fails, copy (typed allocation failure) or reject.

**[6] Static memory planning.** For tensor graphs, autodiff tapes, and per-step scratch, do not allocate per op. Build the interference graph of buffer live ranges and pack into a fixed workspace. This is XLA/TVM/MLIR buffer assignment. It is the only L18 claim that is actually “next generation” for an AOT language that owns autodiff.

**[7] SoA.** Only when it does not change identity, taking addresses (you have none), or view semantics. Safe for closed tables whose elements are never viewed as whole-struct pointers. Unsafe for FFI and for any API that exposes element identity as a view. Default off for v1 except compiler-owned entity tables.

### How A7’s constraints help

| Constraint | What it buys | What it does not buy |
| --- | --- | --- |
| Recursion ban | Call graph DAG; bounded region depth; stack budget is at least well-defined for A7 frames | Does **not** forbid cyclic *data*. `05-for-a7.md:190` is wrong. Trees still need explicit stacks (you already write them that way). Generated drop of a deep owned tree can still recurse in Zig unless you plan iterative destruction |
| Immutable argument bindings | Large values may be passed by const pointer; signatures stay simple | **Not** exclusivity, **not** `noalias`, **not** deep immutability. Odin/Zig/Jai all allow pointee writes. GLM’s corrected advisory is right: L6 is a calling-convention fact |
| No public `&`/`*` | Users cannot manufacture aliases | The compiler still inserts refs for `ref` params and slices. Escape analysis is mandatory |
| Whole-program compilation | Interprocedural region inference is feasible (MLKit needed this). Effect summaries can be computed, not trusted | Separate compilation / plugins become a later problem. Generics still need monomorphization before memory planning |
| Fail-closed | You can refuse the unanalyzable 5% instead of inserting a GC | Diagnostics must be good or the language will feel like a borrow checker |

G2 option (a) — affine `new`/`del` first — is the right *internal* model and the wrong *user* surface. If you ship affine `new`/`del` as the public memory story, you have contradicted L17. Affine ownership should be the IR invariant. The public story is: values, tables, and inferred homes.

---

## 3. New concepts: keep, rename, hide

The draft names are reasonable as compiler-internal vocabulary and bad as a user language. Do not make people write `lifetime group` or `family`.

### Compiler-internal (keep a small set)

| Draft | Verdict | Replacement |
| --- | --- | --- |
| **Lifetime group** | Academic; users do not think this way | **Cohort**: allocations proved to die together; lowered to one arena reset |
| **Family** | Sounds like OOP | **Table**: homogeneous dense storage of one type in one home; addressed by slots |
| **Home** | Good internally | Keep. Instantiated as: frame, loop, task, module, session, request |
| **Link** | Sounds like a pointer | **Slot**: `usize` index into a table, optionally paired with a generation |
| **Boundary** | Vague | **Escape**: a use that would take storage out of its home (return, store, send, capture, native) |

### User-visible (as few as possible)

Users should see **data**, not memory policy.

1. **Values** — numbers, structs of values, fixed arrays. Copy.
2. **Owned containers** — `string`, lists, maps, tensors, files. No `del`. Dropped with their home, or moved.
3. **Tables** — the one new public type worth adding. “A growable array of `T` whose elements are named by `usize`.” This is the data-oriented replacement for `ref T` fields.
4. **Slots** — just `usize`, or a distinct `id T` if you want wrong-table mixing to be a type error (recommended). Lookup returns `?T`.
5. Optional, later, and rare: a **`keep`** or home hint when inference fails. Not in v1 ordinary code.

Do **not** add user-visible: region names, arena types, `borrow`/`inout`/`consume` (not approved; not needed if views cannot be stored), generational-reference syntax, `Rc`.

`ref` today is three concepts glued together: owning heap pointer, borrowed stack slot, and maybe-null. That overload is why MS-5 exists in the security advisory (`del` on a `ref` param). Split it internally:

- owner (hidden, from `new` or container growth)
- view (parameter / local slice only)
- slot (stored relationships)

Public `ref T` as a storable heap pointer should leave ordinary A7. Keep `ref` as the mutation permission on parameters if you want zero new keywords (current SPEC §6.3). That matches L6 without Cluster CC’s mode keywords.

---

## 4. Hard cases

### Returning allocations

Return **owners**, not views.

```a7
// Proposed. Function result is an owned list. Home is the caller.
three :: fn() List(i32) {
    xs := list_of(i32)
    xs = xs.append(1)
    xs = xs.append(2)
    xs = xs.append(3)
    ret xs
}
```

Returning `local[0..n]` is rejected (today this compiles, per G2’s MS-8 observation in the plan; I did not re-run it). Returning a Copy array by value is fine.

If several allocations must outlive the callee together, infer a **caller home** and allocate there (region polymorphism). That is how “return a tree of nodes” works without `del`.

### Growing lists with references into them

Ban interior views of resizable storage. Relationships are slots.

```a7
// Proposed. Indices, not refs, into a growable table.
people: Table(Person)
parent_of: Table(id Person)    // slot, not ref Person
```

A local view `p := people[i]` lasts until the next operation that may grow `people`, or until end of statement. A `for p in people` that `people.append(...)` is a compile error (iteration exclusivity). This is the C++ iterator rule, discharged statically.

### Cyclic graphs and parent pointers

One owning table, many slots. Cycles are data, not ownership.

```a7
// Proposed. Matches the spirit of examples/025 and 026.
Node :: struct {
    value: i32
    parent: id Node
    left: id Node
    right: id Node
}

nodes: Table(Node)
root := nodes.add(Node{value: 1, parent: none, left: none, right: none})
```

No `ref Node` fields. Removal is a table operation (see entity removal). Traversal uses an explicit stack or a `usize` cursor — which you already require because recursion is banned.

### Caches and globals

A global is a **module home**. It lives until process exit. That is honest and coarse.

A cache that must forget entries is a table with an eviction API, not a GC. If eviction is input-dependent, lookup is `?T`. Do not infer a shrinking cache from reachability; that is a collector.

```a7
// Proposed. Explicit, not inferred.
cache: Table(Entry)
got := cache.get(key)
if got == none {
    e := load_entry(key)
    cache.put(key, e)
}
```

### Closures

Immediate callback: may view captures for the call. Escaping closure: must **own** captures (move or copy into the closure value). A closure that consumes a capture is one-shot; if you cannot say that in the type, reject storage of that closure (G4 option (a) is the simple sound choice).

Do not allow a closure to capture a view of a local and be stored in a struct. That is a lifetime parameter in disguise.

### Long-running loops / servers

Two homes:

- **Server / world home**: tables of long-lived entities.
- **Request / frame home**: scratch arena, reset at the back edge.

```a7
// Proposed.
for req in incoming {
    // inferred: cohort reset at end of iteration
    body := read_all(req)
    reply := handle(body)
    write(req, reply)
}   // scratch dies here; server tables do not
```

If `handle` stores a slice of `body` into a global, that is an escape: compile error. Copy or intern into the server table.

### Entity removal

Tables reuse slots. A raw `usize` after reuse is a time bomb.

Least-bad A7 answer: **`id T` is a slot plus generation**. `table.get(id)` returns `?T`. That is a typed result, not a panic and not a GC. Proved-live ids (just created, or held while the table is frozen) skip the check in codegen.

Generation wrap must be defined: saturate and reject reuse, or use a width where wrap is a documented process-lifetime assumption. Do not silently wrap.

This is Vale’s idea, restricted to table slots, not to every pointer.

### Tensors, views, autodiff tape

Follow the Codex memory-design T1 as v1: a **session home** owns buffers, tape, and optimizer state. Tensor values are ids into the session, not owning pointers and not RC.

```a7
// Proposed.
sess := train_session()
x := sess.tensor(data, shape)
y := sess.square(x)
loss := sess.sum(y)
grads := sess.backward(loss)
```

Rules:

- Views (`x[0.., 1]`) are views: they cannot outlive the session op that created them unless stored as a session id.
- While a buffer is saved for backward, mutation is rejected or returns a typed conflict. Snapshotting is explicit because it allocates.
- Per-step activations are a **step home**; pack them with the static planner; reset after `step()`.
- Optimizer state and checkpoints live in the session home. Checkpoint I/O copies bytes; it does not freeze views.

Do not use tensor objects with shared backing (T2) in v1. That is RC, even if you hide the counts.

### Optimizer state and checkpoints

Owners: session. Checkpoints are explicit serialize/deserialize of owned buffers. After load, all old tensor ids are invalid (generation bump of the session). That falsifies a large class of use-after-reload bugs at the type/id layer.

### Tasks and channels

Inko/Verona, not Go. Move owners on send. No shared mutable views across tasks.

```a7
// Proposed.
sent := ch.send(job)
if !sent.ok {
    job := sent.unsent   // still owned here
    ret
}
// job is not usable here
```

A task’s captures must be owned. A task home dies at join. Unjoined tasks that captured owners are a compile error (structured concurrency). Channel close is affine. Deadlock is **not** prevented (already in the GLM advisory I-21).

Allocator lifetime: do not send a view into a sender-owned arena. Send bytes, or transfer a whole cohort. “Task-private heap” is insufficient if the receiver keeps a pointer into the sender’s arena.

### Native kernel buffers

A7 owns the buffer. The kernel **borrows** it for the call. The wrapper’s effect summary says: reads, writes, no retain after return, overlap rules, alignment, workspace allocation. If the library may retain (DLPack producer deleter, oneDNN persistent plans), the A7 type is an owner with that deleter, not a view.

Cancellation: a running BLAS call finishes before the buffer’s home dies. You cannot prove prompt cancellation.

---

## 5. When inference fails

Fail closed. The only Python-feeling fallback that does not break the contract is **promote to a longer static home**.

| Failure | Diagnostic (what to say) | Legal next step |
| --- | --- | --- |
| View escapes a home | “`body` is scratch for this request; storing it in `conn` would keep it after the request ends. Copy with `clone`, or store an `id` into a server table.” | clone / intern / restructure |
| Two homes disagree | “this list is used in `train_step` and also stored in `model`; those are different homes.” | move to the longer home (session) |
| Cycle of owners | “`Node.next` is an owning field and forms a cycle. Use `id Node` in a table.” | tables + slots |
| Uniqueness fails for in-place | do not fail the program; copy or reject the in-place claim | copy is a typed allocation |
| Runtime-only last use | “cannot prove when this dies; it would need a collector. Give it a home: session, module, or table.” | user picks a home by construction, not by annotation |
| Slot may be stale | do not fail compile if lookup is `?T` | residual typed check |

**Forbidden fallbacks:** insert RC; insert a tracing GC; leak; free early; Vale-style trap on the fast path as the default safety net; Swift-style dynamic exclusivity traps.

**Optional hints**, if inference keeps failing on real corpus programs: a way to name a home at a scope (`scratch { ... }` or a `table` declaration). That is a hint because the compiler still checks escapes. It is not an allocator API. Ship it only after the corpus shows you need it.

Holding memory too long is the correct residual. It is what “like GC” actually felt like for peak memory anyway, except you get deterministic release at home end and no pauses.

---

## 6. Prior art — what is usable, what is a trap

| Source | Directly usable | Trap |
| --- | --- | --- |
| **Tofte–Talpin / MLKit** (*Region Inference*, I&C 1997; MLKit docs; Elsman tag-free GC papers) | Home inference, region polymorphism for returns, “hold longer than last use,” whole-program region assignment | Naive TT puts too much in the outermost region (the classic space-leak). You **must** have storage-mode analysis / resetting at loops. Do not expose region types to users the way early MLKit did |
| **Cyclone** (Grossman et al., PLDI 2002; Swamy et al., SCP 2006) | Arena-tied provenance; fat pointers ≈ slices; default region + a few annotations (their 8% port figure) | Region subtyping and `'r` annotations become a second type system. A7 should infer homes and reject, not teach region variables |
| **ASAP** (Aigner et al. / related static automatic pool allocation — Lattner automatic pool allocation, LLVM; “Automatic Pool Allocation”, PLDI 2005, Lattner & Adve) | Type-homogeneous pools from points-to; DOD layout | Relies on C pointer analysis. A7 should not reconstruct this from `ref` soup; it should make tables the source-level graph form |
| **Go/Java escape analysis** | Stack promotion of non-escaping news; cheap win | They have a GC for the rest. Copying their EA without a GC leaves the escaping remainder unsolved |
| **Hylo / Val** (Racordon et al., JOT 2022; hylo-lang spec) | No stored references; call-site exclusivity; mutation as value update | Implementation is in flux (hylo-new). Restricting stored refs **does not** eliminate owned heap containers or graph data. Do not promise “no lifetime reasoning” for slices you already have |
| **Swift OSSA / ownership SIL** (SE-0377, 0390, 0427, 0446; Law of Exclusivity) | SSA ownership IR is the right compiler shape; noncopyable + nonescapable split | Production Swift still has dynamic exclusivity traps and RC classes. A7 cannot copy that fallback |
| **Koka / Perceus** (Reinking et al., PLDI 2021) | In-place reuse when unique; drop insertion; functional-but-in-place | The **model** is RC. You may steal the reuse analysis, not the counts. Their proofs assume a functional core; A7 is mutable and concurrent |
| **Lobster** (Wouter van Oortmerssen) | Compile-time RC elision, some static lifetime | Still RC-centered; not a DOD story; not a fail-closed proof engine |
| **Vale** (Verdagon; generational references; *Grimoire*) | Generation-bearing **table slots**; excellent taxonomy | Using generation checks as the default pointer safety net is a runtime trap language. Alpha; do not cite as a completed region system |
| **Austral** | Proof that a small linear checker is implementable | Too linear for Python-feel; error paths and discard become painful |
| **Inko** | Isolated heaps + move over channels | Runtime is still a language runtime; steal the concurrency rule, not the heap impl |
| **VerThe combined goal is achievable for A7’s actual v1 programs, and not achievable as “Python object graphs, no annotations, no residual allocator.” The design that works is not a compile-time garbage collector. It is **frame-scoped storage planning**: the compiler infers *where* data lives and *when the whole group dies*, then lowers that to arenas, typed pools, indices, and in-place reuse. Python-simple is the surface. Jai/Odin/Zig is the code that comes out.

I did not run the compiler or any program. Claims about current A7 behavior below are from the documents I read, not from a fresh compile.

---

## Facts I verified (documents only)

From `docs/plan/decisions.md`, `docs/plan/README.md`, `docs/SAFETY_CONTRACT.md`, `docs/SPEC.md` §§3.3–3.5, 6.2–6.3, 8, A.4, and the cited research:

- **L15–L18** lock automatic, compile-time, data-oriented memory management; Python-simple surface; compiler-grouped arenas/pools; reuse/optimization ambition. No GC and no RC as the core (brainstorm + your constraints).
- **Current surface:** `new` / `del` / `defer del` / `ref` / `nil`. Heap lives until explicit `del`. Public `&` / `*` / `.adr` / `.val` are banned. Argument *bindings* are immutable; `ref` parameters mutate caller storage. Recursion is a compile-time error.
- **Fail-closed:** unproven risky operations are rejected before Zig is emitted. Codegen consumes `BackendPlan`; it must not invent safety.
- **G2** currently stages (a) syntax-free affine refs, then (b) parameter modes, then (c) regions “if gaps remain.” Tensor saved-value lifetime depends on G2.
- **Track 4** is typed IR + CFG; **track 5** is proof repair; **track 6** is the memory model. The current safety pass is an AST walk with name-keyed facts (`a7/safety.py`: `BackendPlan`, `moved_symbols: set[str]`). There is no escape analysis, no CFG, no points-to.
- **Existing examples already use indices, not pointers:** `examples/025_linked_list.a7` (`next: isize`), `examples/026_binary_tree.a7` (`left`/`right: usize`). `examples/011_memory.a7` is the `new` + `defer del` idiom.
- **Cluster CC** in `08-decisions.md` is still **PROPOSED**. D.049 “no storable references” is **not** a locked user decision. L6 does not approve mode keywords.
- Plan-documented observation (not rechecked by me): `p := new Pt; q := p; del p; del q` compiles and would emit two `allocator.destroy` calls.

One documented claim is wrong and must not survive into the design: `docs/lang-safety/05-for-a7.md` §3.3 says “No recursion → no cyclic ownership graphs.” The recursion ban is about the **call graph**. Data graphs can still be cyclic. Trees, parent pointers, and ECS worlds are the point of L15.

---

## 1. Is the combined goal achievable?

**For the programs v1 already locked — training steps, game-style worlds, request loops, owned tensors, isolated tasks — yes, with restrictions that match data-oriented design rather than fight it.**

**For “any graph a Python GC would collect, inferred perfectly, zero runtime allocator, peak memory equal to a perfect `free`,” no.** That is not an engineering gap. It is the shape of the problem.

### Where it breaks, exactly

Compile-time memory management can decide a lifetime only from **structure**: scopes, loops, calls, uniqueness, and explicit frames (tick, request, training step, task). A tracing GC decides lifetimes from **runtime reachability**. Those are different predicates.

The break is any object whose last use is “whenever nothing can reach it anymore,” when that reachability is not a function of the CFG:

| Pattern | Why inference cannot place it | What happens if you force it |
| --- | --- | --- |
| Arbitrary heap graph with stored addresses | Last use depends on aliasing you cannot close | Reject, or hold the whole heap until process exit (a leak named an arena) |
| Interior view into a buffer that later reallocates | Grow invalidates addresses; even indices are wrong if you compact | Reject the view across grow, or forbid compact while handles exist |
| Cache / intern table with data-dependent eviction | Lifetime is a policy, not a scope | Must be an explicit table with `put`/`get`/`clear` |
| Escaping closure over a local buffer | Capture outlives the frame | Move/copy the capture, or reject |
| Cross-task alias of a store the receiver does not own | Two frames, one storage | Move the value or the whole store; never send a raw handle |
| Native kernel that keeps a pointer after return | A7 no longer controls the referent | Opaque owned handle + documented borrow interval; otherwise reject |

Rice-style limit, stated operationally: **liveness for arbitrary pointer graphs is not decidable in a way that is both sound and precise.** Every real system picks one of:

1. Restrict the language (Hylo, Austral, affine Rust without `Rc`).
2. Approximate and **over-retain** (MLKit regions, game-frame arenas).
3. Leave **residual runtime work** (RC, GC, Vale generation traps, Swift exclusivity checks).

A7’s constraints already choose (1) and allow a controlled amount of (2). They forbid (3) as the *safety* mechanism. That is a coherent point in the design space. It is not Python.

### Least-bad restrictions (accept these; they *are* the design)

1. **No stored addresses.** Already true. Keep it. The heap the user thinks in is **tables of records plus `usize` ids**, not objects with pointers in fields.
2. **A stored “reference” is an index into a store the compiler can name**, not a `ref T` field that aliases an independent allocation.
3. **Views (slices, tensor views) are local and non-escaping** unless the callee returns *ownership* of the backing store, or the view is into a parameter that the compiler can tie to the caller.
4. **Growth while a view is live is a compile error.** Growth while only *ids* are live is fine if you never compact, or if ids are generational and lookup returns `?T`.
5. **Cycles are numbers, not owners.** One table owns the nodes. `parent: usize` is not an ownership edge.
6. **Long-running programs have compiler-visible frames.** The body of `for request in server`, `for tick in world`, and `for step in train` is a frame. Temporaries die at iteration end. What survives must be stored in a named long-lived table (`world`, `session`, `conn_table`).
7. **When placement is unproven, reject.** Do not leak, do not insert RC, do not insert a collector, do not emit a trap “just in case.”

### Least-bad residual runtime work (this is not a GC)

Fail-closed still allows **typed, defined results**. It does not allow “the CPU might segfault, or we panic to be safe.”

Keep:

- **Allocator calls** to grow a store (`mmap`/`malloc` of arena chunks, pool slabs). Inferred arenas still sit on an allocator. Jai/Odin/Zig do this too.
- **Bump / free-list inside a store.** O(1) allocate; bulk reset at frame end. No mark, no sweep, no counts on the fast path.
- **Allocation failure** as `?T` / `Result` (already the `new` surface).
- **Checked size arithmetic** for capacities, shapes, strides. Ordinary `+ - *` wrap (L5); allocation sizes must not.
- **Handle lookup** as a value: `world.get(id) -> ?Entity`. A miss is a domain result, not a UAF trap.
- **Tensor shape/overlap preflights** when dimensions are runtime values.
- **Channel closed / send failure** as typed results.

Do not keep, even as “fallback”:

- Tracing GC
- Reference counts as the ownership mechanism (Perceus-style *reuse analysis* is fine *after* uniqueness is proved; the counts themselves are not)
- Vale-style generation compare that panics
- Swift-style dynamic exclusivity traps
- Hidden copies (COW) that can allocate on mutation without a visible failure path

“Resolved at compile time” should mean: **every drop, reset, move, and reuse is inserted by the compiler at a known program point; there is no collector and no count.** It should not mean “the process never calls malloc.”

Over-retention is the remaining honest cost. A request-scoped arena that dies at the end of the handler may hold a 4 KB parse tree until the handler returns even if the tree died at line 20. That is the MLKit/game-arena trade: **predictable, slightly high watermark, no pauses.** For v1 that is the right trade. Precise last-use free is an optimizer (L18), not the safety story.

---

## 2. Strongest candidate architecture

Name it internally **storage planning**, not “compile-time GC.” Three layers, one user story.

### User story

You write values, lists, tables, and ids. You do not free, name allocators, or write lifetimes. The compiler decides stack vs pool vs arena, groups objects that die together, reuses buffers when the old value is dead, and rejects the program when it cannot.

### Layer A — Affine owners for resources (necessary, not sufficient)

This is G2(a), and it must land, but it is **not** L15–L18. It makes today’s `new`/`del` sound.

- A heap owner is moved, not copied.
- Scope exit drops it (reverse declaration order).
- `del` becomes optional early-release, conflicting with `defer del` and with a later use.
- `ref` parameters are **temporary access**, not a second owner.
- Files, sockets, channel ends, native kernel handles live here.

Without this, inferred arenas are unsound because `q := p; del p; del q` still exists.

### Layer B — Inferred stores (this *is* L15/L17)

Every allocation is assigned to a **store** attached to a **frame**.

| Store kind | When the compiler chooses it | Lowering |
| --- | --- | --- |
| Stack / registers | Does not escape the frame; size known | Zig locals |
| Typed pool | Many values of one type, same frame, need stable indices, insert/remove | SoA or AoS slab + free-list of slots |
| Bump arena | Mixed types, bulk death, no individual free | `ArenaAllocator`-style reset |
| Reused scratch | Loop/step with the same shape each iteration | One store, `reset` at the back edge |
| Session store | Training graph, optimizer, world | Long-lived store; explicit export copies out |

Placement algorithm, in order:

1. **Escape analysis.** Does this allocation leave the current frame (return, field of escaping object, global, closure, channel, native)? If no: stack or frame scratch.
2. **Region/lifetime inference.** If it escapes, to which *least* frame that covers all uses? Tofte–Talpin region assignment on a **DAG call graph** (the recursion ban makes the lattice well-founded). Over-approximation is allowed; under-approximation (free too early) is not.
3. **Homogeneity.** Same type + index-heavy access → pool. Mixed → arena.
4. **Uniqueness / affinity.** At most one mutable path to a location at a time (call-site exclusivity). Unique dead value → storage reusable (Perceus *without* RC).
5. **Liveness-based packing.** Inside a frame, buffer lifetimes are intervals; pack them (XLA/TVM memory planning). This is L18.
6. **Layout.** If all access is `field` of `table[id]`, SoA is a behavior-preserving transform. If FFI needs a C layout, do not transform.

### Layer C — Handles, not pointers

User-level “I have a reference to an entity” is `EntityId` (`usize`, optionally `{index, generation}` as a value). The compiler never lowers that to a raw pointer the user can store.

This matches `025`/`026` and matches DOD. It also dissolves the parent-pointer / cycle problem.

### Analyses and the IR they need

Do not hang this on the current AST + `FactMap`. Track 4 is the real prerequisite; the brainstorm never says so.

Required IR, after monomorphization (A7 already specializes generics):

1. **Typed CFG** with explicit sequencing. Joins and loops are first-class. (Today’s snapshot-restore in `safety.py` is documented as unsound for facts; the same shape cannot carry ownership.)
2. **Ownership SSA** (Swift SIL/OSSA is the right prior art): every value has a unique owner at each point; borrow/move/drop are SSA uses. This is how you do last-use reuse without a collector.
3. **Storage identities**, not variable names. `p` and `q` after `q := p` are the same allocation. Fields, slice projections, and tensor views are projected regions of a storage id.
4. **Effect summaries** on every function, serialized for public APIs:
   - reads / writes / resizes / drops of each argument
   - allocation into which frame
   - returned storage dependencies (“returns owner” vs “returns view of arg 2”)
   - globals, callbacks, suspension
   A single lattice `borrow < inout < consume` (D.041) is too poor. A function can read A, mutate B, return a view of C, and allocate into the caller frame.
5. **Points-to / projection aliasing** for fields, `arr[i]` vs `arr[j]`, overlapping tensor views. Exclusivity is about storage, not names.
6. **Region/store annotation** on each allocation and each view: `(store_id, frame_id)`.
7. **Liveness intervals** of buffers inside a frame, for packing and in-place reuse.
8. **Backend plan extension:** not only `index`/`deref`/`cast`, but `drop`, `reset_store`, `reuse_buffer`, `handle_lookup`. Codegen must not reconstruct this from spelling.

Whole-program compilation is not optional for L17. Separate compilation would freeze effect summaries without seeing allocation grouping. A7 already compiles a program, not a shared library zoo; use that.

### How the locked constraints help

- **Recursion ban.** Call graph is a DAG. Region nesting is finite. Stack-budget analysis becomes a real number (A7 frames only; native kernels remain a separate bound). Generated drop of a deep owned tree must still be **iterative** — a compiler-emitted recursive destructor would reintroduce unbounded native recursion. Use an explicit stack or a pool reset.
- **Immutable argument bindings.** Callee cannot rebind. Large values may be passed by const pointer. This does *not* give `noalias` by itself (Odin/Zig lesson in the GLM ownership report). Exclusivity analysis does.
- **No public `&`/`*`.** Users cannot manufacture aliases the IR does not see. That is the single biggest reason inferred stores are feasible. Guard this at FFI: `cast(ref T, usize)` must stay illegal.
- **Whole-program + monomorphization.** Store placement and buffer packing see the real call graph, not generic soup.
- **Fail-closed.** Forces diagnostics instead of a silent GC fallback, which is what keeps the “as Zig” performance story honest.
- **`usize` as the index type.** The language is already biased toward handles. Do not add a parallel pointer vocabulary.

G4 (stored function values) is a memory-model dependency, not a side issue. A struct field holding a function can hide recursion and can capture stores. Either forbid stored function values, or give the call graph type-informed edges and treat escaping closures as owning their captures. Option (a) in G4 is the one that keeps storage planning tractable.

---

## 3. New concepts: keep few user-visible, rename the internals

The brainstorm’s five names mix compiler IR with a language. That will leak into the user model and destroy the Python-simple promise.

### Compiler-internal (users never write these)

| Draft name | Verdict | Replace with |
| --- | --- | --- |
| **Lifetime group** | Sounds like Rust lifetimes; users will try to write it | **Store** — the allocation bucket. Kind: arena or pool |
| **Family** | Collides with type families | **Pool** — a typed store with dense slots |
| **Home** | Vague | **Frame** — function activation, loop iteration, task, training step, process |
| **Link** | Too pointer-like | **Handle** / **id** — `usize` (optional generation as data, not as a pointer header) |
| **Boundary** | Fine as IR jargon | Keep internally as **escape edge** (return / global / channel / native / capture) |

A **frame** owns zero or more **stores**. A **handle** is valid only for a named store. An **escape edge** requires moving a store, copying, or rejection.

### User-visible (aim for three ideas, not five)

1. **Values.** Copy if they are plain data; move if they own resources. No keyword.
2. **Tables and lists.** Owned collections. `append`, `get`, `remove` are ordinary calls. The compiler places the backing store.
3. **Ids.** `id := world.spawn(e)` returns a `usize` (or a distinct `EntityId` alias). `world.get(id)` returns optional. No `*` anywhere.

Ordinary code does not say arena, pool, region, lifetime, borrow, or consume.

### User-visible only when inference fails (optional v1, better as v1.1)

A **named frame** for long-lived or multi-allocation scratch, if the compiler cannot see the loop/request/step:

```a7
// Proposed — only as a hint when the diagnostic asks for it.
// Not required for the common path.
session := Frame.create()
// ... allocations inferred into session ...
// session ends at scope exit; bulk reset
```

I would **not** ship this in the first cut if diagnostics are good. Game/server/train loops already *are* frames if the compiler treats iteration bodies as frames by default.

Do not add `region r;` as Cyclone did. Cyclone needed annotations on ~8% of ported lines. That is the opposite of L17.

`ref` stays as today’s **mutation permission at a call**, not as a storable heap pointer. That matches L6 without mode keywords. Stored `ref T` fields should go away in favor of ids or owned nested values. That is a breaking change; L2 allows it through the approval rule.

---

## 4. Hard cases

All examples below are **proposed** behavior, not current A7.

### Returning allocations

Return **owners**, never views of callee storage.

```a7
// Proposed. The list is an owner. The compiler places its pool
// in the caller, or moves a heap owner out of the callee.
make_ids :: fn() List(i32) {
    xs := List(i32).empty()
    xs.append(10)
    xs.append(20)
    ret xs
}
```

Returning `xs[0..2]` of a local is a compile error (this is today’s MS-8 hole). If you need a slice of a *parameter*, v1 should still reject it unless you later approve a dependency contract (“returns a view of arg 1”). Silent copy-on-return is not acceptable: it allocates and can fail.

### Growing lists with “references” into them

This is the design fulcrum. Addresses into a reallocating buffer are poison. **Indices are not**, unless you compact.

```a7
// Proposed.
xs := List(i32).empty()
xs.append(1)
i: usize = 0
xs.append(2)
v := xs.get(i)          // OK: id/index, not an address
// slice := xs.items()  // a view
// xs.append(3)         // ERROR if slice is live: grow while viewed
```

Rule:

- **Index/id** may survive append.
- **View/slice** may not survive grow, remove-compact, or move of the backing store.
- **Remove** either leaves holes (ids stay valid; pool + free-list) or uses generational ids.

That is how every engine that is not a GC actually works.

### Cyclic graphs and parent pointers

Do not infer a pointer web. One owning table.

```a7
// Proposed. Same idea as examples/026_binary_tree.a7, grown up.
Node :: struct {
    value: i32
    parent: usize
    left: usize
    right: usize
}

Tree :: struct {
    nodes: List(Node)
    empty: usize
}

set_left :: fn(tree: ref Tree, parent: usize, child: usize) {
    p := tree.nodes.get(parent)
    if p == none { ret }
    c := tree.nodes.get(child)
    if c == none { ret }
    // p and c are copies of records, or mutating getters —
    // mutation goes through tree, not through stored refs.
    tree.nodes.set_parent(child, parent)
    tree.nodes.set_left(parent, child)
}
```

Cycles are `usize` equalities. Drop of `Tree` resets one pool. No recursive destructor.

### Caches and globals

A global is the process frame. That is the coarsest store. An unbounded “dict of objects until forgotten” **is** a GC. Do not infer it.

```a7
// Proposed. Explicit table, explicit eviction.
Intern :: struct {
    strings: List(string)
}

intern :: fn(tab: ref Intern, s: string) usize {
    // search, or append and return new id
    tab.strings.append(s)
    ret tab.strings.len - 1
}
```

If you want LRU eviction, that is a library policy on a table, not a language lifetime.

### Closures

- Immediate callback argument: may borrow for the call.
- Stored / returned closure: **owns** captures (moved or copied). Capturing a slice of a local is rejected.
- Prefer G4(a): no function values in fields. Callback tables for AI/kernels should be compiler-known stdlib, not user function pointers in structs.

### Long-running loops and servers

The iteration body is a frame. Scratch resets. Survivors go into a table owned by the loop header.

```a7
// Proposed.
World :: struct {
    entities: List(Entity)
}

run :: fn(world: ref World, n: usize) {
    tick: usize = 0
    while tick < n {
        // Frame = this iteration.
        // Scratch (pathfinding temps, event lists) inferred here and reset.
        dt: f32 = 0.016
        step(world, dt)     // mutates world; may spawn into world.entities
        tick += 1
    }
}
```

If `step` allocates a temp `List` that does not escape, that list’s store is reused next tick (L18). If it stores into `world`, placement is the world store.

This is Odin’s `temp_allocator` / game scratch arena, inferred.

### Entity removal

```a7
// Proposed. Generation is data on the id, not a pointer header check that traps.
EntityId :: struct {
    index: usize
    gen: usize
}

spawn :: fn(world: ref World, e: Entity) EntityId { /* occupy a free slot, bump gen */ }
despawn :: fn(world: ref World, id: EntityId) { /* free slot, bump gen */ }
get :: fn(world: ref World, id: EntityId) ?Entity {
    // miss if index empty or gen mismatch — typed none, not a trap
}
```

Slot reuse is allowed because a stale id does not resolve to a new occupant. Fail-closed: the *unsafe* operation (load through a dangling pointer) never exists. The *safe* operation (optional lookup) does.

### Tensors, views, autodiff tape

Follow the Codex memory-design **T1 (session ownership)**, not T2 (RC-backed tensor objects). v1 already requires A7-owned reverse-mode AD (L9) and checkpoint recovery (L10). A session is a frame.

```a7
// Proposed.
train_step :: fn(session: ref Session, x: TensorId, target: TensorId) ?f32 {
    y := tensor_mul(session, x, x)
    loss := tensor_sum(session, y)
    grads := tensor_backward(session, loss)
    if grads == none { ret none }
    // ERROR if we mutated x while saved:
    // tensor_fill(session, x, 0.0)
    tensor_release_graph(session, loss)
    ret tensor_to_f32(session, loss)
}
```

Rules:

- A `TensorId` names session storage; it is not a borrow and not an owner of bytes.
- A **view** (slice, transpose, broadcast) is a local projection: shape, strides, offset. It cannot outlive the session entry. Writable overlapping views are exclusivity errors (same as `swap(arr[i], arr[i])`).
- Tape saved values are owned by the session until `backward` + release, or until step end.
- Mutation of saved storage: **reject or return a preflight failure**; do not snapshot implicitly (that allocates).
- Intermediates: liveness packing reuses buffers across the step DAG. Reverse-mode needs saved values; those intervals are longer. This is exactly XLA buffer assignment on a DAG — and A7 source is already non-recursive, so the step graph is a DAG if you ban callback-shaped ops or treat them as opaque nodes.
- Export / checkpoint: copy or move into an independent owner (file, owned buffer). A checkpoint must not be a view into live session memory.

Optimizer state (`m`, `v`, master weights) lives in the session store for the run; it is not scratch.

### Tasks and channels

Move the **value**, not a handle into a store the receiver does not own.

```a7
// Proposed.
send_job :: fn(ch: ref Chan(Job), job: Job) SendResult {
    // on failure, job is still owned by the caller
}

// ERROR: sending EntityId into another task that does not own world
// ch.send(id)

// OK: send the record, or send an owned snapshot
ch.send(copy_entity(world, id))
```

Task-private stores. Join is mandatory for owned child tasks. Do not claim deadlock freedom (already the GLM security position). Cancellation: a native kernel must finish or acknowledge before buffers reset.

### Native kernel buffers

Opaque owned handle. The kernel **borrows** A7 storage for the call. If a library keeps the pointer (cuBLAS-style async, or a persistent plan), that is a different resource with an explicit lifetime, not a slice.

DLPack is the right foreign protocol: producer deleter, not “trust this pointer.” Overlap of GEMM `A` and `C` is a preflight, not UB.

---

## 5. When inference fails

**Reject. Explain. Offer a rewrite. Do not fall back to a collector.**

That is the only policy that keeps both L15 (“as Zig”) and the safety contract. A GC fallback would make two languages, and ReleaseFast would be a different program.

### Diagnostics (the Python-simple part)

The message must name the allocation, the escape edge, and one legal repair. Three templates cover almost all failures:

1. **Escaping view:** “`xs[0..n]` is a view of local `xs` and is returned. Return `xs` itself, or copy into a new list.”
2. **Grow while viewed:** “`xs.append` reallocates while `view` is live. Index with `usize`, or finish using `view` first.”
3. **Handle leaves its store:** “`id` refers to `world.entities` and is sent to another task. Send the entity value, or share `world` as a single owner (not allowed across tasks — copy or move the world).”

Optional **hints** (`Frame.create()`, “put this in `world`”) are fine as suggested edits. They must not be required on the happy path.

### What “fallback” is allowed

| Tempting fallback | Keep? |
| --- | --- |
| Over-retain until frame end | Yes — this is region inference working |
| Typed `?T` lookup / alloc failure / shape mismatch | Yes — values, not traps |
| Insert RC when a cycle of owners is detected | No |
| Insert GC for “too hard” functions | No |
| Vale generation panic | No |
| Implicit deep copy to make a return safe | No (hidden alloc + failure) |
| “Unsafe, we proved nothing” | No |

If a program is a true cache/graph in Python style, the rewrite is **make a table**. That is the DOD tax. It is also how you get the performance the user asked for. Charging that tax at compile time is the product.

---

## 6. Prior art — what to steal, what is a trap

I did not re-fetch these papers for this note. Names and lessons are from the repo’s research plus standard knowledge of the area. Treat paper-level details as things to re-read, not as freshly verified.

### Directly usable (steal the mechanism)

| Source | What to take | Trap |
| --- | --- | --- |
| **Tofte–Talpin region inference** (POPL 1994); **MLKit** | Assign allocations to nested regions from types/effects; free en bloc | They added **tag-free GC on top of regions** (Elsman) because regions **over-retain** and SML has unrestricted data. Do not advertise MLKit as “GC replaced.” A7’s recursion ban and handle discipline are why you might not need their GC. |
| **Cyclone** (Grossman et al., PLDI 2002; Swamy et al., SCP 2006) | Lexical regions, region subtyping, fat pointers as slices, non-null vs nullable | ~8% of C lines changed; region **annotations leak**. Also still a C dialect with addresses. Use as the *internal* region story, not the surface. |
| **Hylo / Val** (Racordon et al., JOT 2022; hylo-lang.org) | References as **call-duration modes**; call-site exclusivity; no lifetime parameters | Implementation is not a finished production compiler. “No storable refs” fights today’s `ref` fields — resolve by **ids**, not by pretending fields do not exist. Mode keywords are not approved (L6). |
| **Swift OSSA** (SIL ownership SSA; SE-0176 exclusivity; SE-0390/0446 noncopyable / nonescapable) | The **IR shape**: ownership in SSA, drop points, non-escaping values | Production Swift **falls back to dynamic exclusivity traps**. A7 cannot. Also ARC remains for class objects — do not copy that split. |
| **Perceus** (Reinking et al., PLDI 2021); **Koka** | Uniqueness ⇒ in-place reuse; drop at last use | The paper is **RC elision**. If you keep the counts, you have RC (cycles, thread costs, destructor storms). Steal *reuse*, drop the counts. Koka is functional; A7 mutation needs exclusivity on top. |
| **Clean uniqueness typing**; **linear update** | In-place update of unique arrays | Easy to over-reject once aliases exist. Pair with handles so graphs are not unique-pointer webs. |
| **XLA / TVM / Halide / MLIR buffer assignment** | Liveness intervals → pack tensors into a fixed workspace | Works on a **known DAG**. Perfect for a training step. Not a general language heap. |
| **Go/Java escape analysis** | Stack-allocate non-escaping; scalar replacement | Only answers stack vs heap, **not when to free**. Necessary but nowhere near sufficient. |
| **MLton**; **Stalin** (Siskind) | Whole-program flattening, unboxing, aggressive lifetime | Compile-time cost; Stalin is a warning that “next-gen” whole-program can become a research compiler that only likes closed programs. A7 is already whole-program — use MLton’s *engineering*, not Stalin’s maximalism. |
| **Odin** context allocators, `temp_allocator`; **Zig** `ArenaAllocator`, `MemoryPool`; **Jai** (qualified: no public spec) implicit allocator + SOA | The *lowering targets* and the frame-scratch idiom | These are **manual**. Inferring them is the A7 bet. Do not copy “pass an allocator everywhere” into user code. Do not claim Jai semantics you cannot cite. |
| **Inko** isolated heaps + channels | Concurrency pairing: no shared mutable heap | Fine for G7. Not a sequential memory story. |
| **Verona** regions as the unit you *send* | Send a whole store to a task | Research/paused. Use the idea, not the language. |
| **Austral** | Proof that a small linear checker is implementable | Too linear for Python-simple (must consume exactly once). Affine + frame reset is enough. |
| **DLPack**; **PyTorch autograd saved-tensors + version counters** (docs, not a dependency) | Foreign buffer ownership; saved-value vs mutation | Version-after-mutation detects bugs too late. Prefer reject/preflight. |

### Study, then mostly avoid as the core

| Source | Why it looks attractive | Why it is a trap for A7 |
| --- | --- | --- |
| **Rust** borrow checker + `'a` | Gold-standard safety | Lifetime parameters are the opposite of L17. Steal affine moves and exclusivity *invariants*, not the surface. Tree Borrows is an unsafe-alias model for LLVM, not an A7 user model. |
| **Vale** generational references | “Most checks elide, a few remain” | Residual **panic** on mismatch violates fail-closed. Typed `?T` lookup is the A7-shaped cousin; do not emit a check that traps. Alpha status. |
| **Pony** `iso`/`val`/`ref`/`box`/`tag`/`trn` | Race freedom | Six user-facing capabilities. Also **ORCA GC** for cycles. Wrong surface, wrong residual. |
| **Swift ARC / Apple RC** | Ergonomic sharing | RC is banned as core; class vs struct split is the opposite of one heap model. |
| **Go/Java GC** | The “simple like Python” feeling | This *is* the thing L15 forbids. Escape analysis inside them is still not a lifetime system. |
| **C++ RAII + `unique_ptr`** | Deterministic drop | Does not stop dangling views or iterator invalidation. A7 already needs the extra analyses. |
| **Cluster CC / D.040–D.049 as written** | Already in-repo | Contradicts itself (storable vs non-storable refs), mis-cites Odin/Zig for deep immutability, and is not user-approved. Do not implement the cluster as a block. |

**Lobster** (Wessing): compile-time RC elision + uniqueness. Useful as a *small-language existence proof* that a games-oriented compiler can drop most counts. Trap: residual RC and a different language shape. Same lesson as Perceus: copy the elision, not the counts.

**ASAP** as used in the brainstorm (“static deallocation”): treat as the family of **compile-time free insertion** (region inference, liveness, first-shot GC in ML compilers), not as one drop-in algorithm. The win is whole-program liveness → `free`/`reset` at known points. The failure mode is the same as MLKit: either over-retain or reject.

---

## 7. Critique of `docs/plan/memory-brainstorm.md`

The draft is honest about the central tension and right to demand a corpus. It is mis-ordered as an attack on L15–L18, and it treats **layers as alternatives**.

### What is good

- Fail-closed, no silent leak/early free.
- Corpus-before-mechanism instinct.
- Evaluation includes peak memory and reuse versus a manual ideal, not just “does it compile.”
- Explicit open questions on rejection vs hints vs runtime checks.

### What is mis-ordered

1. **Session 1 (contract) before any programs is too abstract.** “Like GC” only becomes a sentence once you have a parent pointer and a growing list. Merge sessions 1–2. Write the contract *on* ten programs.
2. **Session 3 is a bake-off of 13 candidates.** Escape analysis, regions, pools, handles, SoA, Perceus reuse, and XLA packing are **one stack**. Scoring them as rivals will produce a false winner (probably “affine + Hylo modes”) that does not deliver L17 arenas.
3. **G2(a) affine refs is a soundness patch for today’s `new`/`del`.** The brainstorm lets it eat the whole design. Sequence should be: proof-engine joins (track 5) → affine owners for resources → inferred stores+handles (L17) → reuse/packing (L18). Regions are not “later if gaps remain” (plan G2 option c). For L17 they are the *middle*.
4. **Feasibility spikes are session 6.** Hand-trace five programs in session 2. The design will die on program 3 (grow+view) or 7 (entity despawn), not after a literature survey.

### What is missing

- **Typed CFG / ownership SSA as a hard prerequisite.** Current `SafetyProofPass` cannot host this.
- **Handles/indices as the default heap**, despite `025`/`026` already doing it. This is the DOD answer and it is underweighted versus Tofte–Talpin.
- **Frames for the workloads v1 already locked** (training step, task, tick). Open question 1 (“games, servers, CLI, or AI first?”) is **already answered by L7–L10 and G7**. Stop asking it.
- **Allocation-size arithmetic** vs wrapping `+ - *` (L5 scope limit).
- **Iterative destruction** so generated drop does not recurse.
- **Kill the “no recursion ⇒ no cyclic data” error** from `05-for-a7.md`.
- **SoA identity:** layout transform is legal *because* there is no address-of. Say that, and say FFI layouts are exempt.
- **T1 vs T2 tensor ownership** is decided enough: T2 is RC. T1 is the only option compatible with the constraints.

### What is unnecessary / contradictory

- **Compile-time RC elision as a candidate** contradicts “no RC as core.” Demote to an optimizer footnote.
- **Hidden handles “with or without generation checks”** as a maybe. Decide now: generation is part of the id value; lookup returns `?T`; no trap.
- **User-visible lifetime group / family / home** as starting names. Decide user-visible vs internal *first*, or those words will ship.

### Corpus that falsifies fastest

Write these as proposed-syntax fixtures before any more mechanism debate. If a candidate cannot say yes/no/rewrite on all twelve, it is not a design.

1. **Return a newly built list** (must move owner, not a slice).
2. **Append while a slice of the list is live** (must reject).
3. **Append while only a `usize` index is live** (must accept).
4. **Tree with `parent: usize`** (must accept; one table).
5. **Two nodes pointing at each other** (must accept as ids; must reject as stored `ref` owners).
6. **Intern/cache table in a global** (must be an explicit table, not inferred GC).
7. **Closure stored in a struct capturing a local buffer** (reject or own a copy; G4).
8. **Tick loop: spawn, despawn, use old id next tick** (`get` returns none; no UAF path).
9. **Request loop: per-request temps + a connection table** (temps reset; conns survive).
10. **`y = x * x`; mutate `x`; `backward(y)`** (reject or preflight; saved-value).
11. **Channel send of `EntityId` without sending `World`** (reject).
12. **GEMM with aliased native buffers** (reject or typed failure before the kernel).

Secondary: checkpoint round-trip (L10), failed `append` leaves the original list usable, deep pool reset does not blow the native stack.

Independent review should score those twelve before any syntax is approved. GLM still owns the security pass (L12).

---

## 8. Proposed A7 examples (not current language)

Constraints honored: no recursion, `usize` indices, no `&`/`*`, immutable argument bindings, `ref` only as today’s mutation permission.

### Ordinary code: no `new`/`del`

```a7
// Proposed. List backing store inferred: caller frame, or moved out.
sum_extra :: fn(base: i32) i32 {
    xs := List(i32).empty()
    xs.append(base)
    xs.append(1)
    total: i32 = 0
    i: usize = 0
    while i < xs.len {
        item := xs.get(i)
        if item != none {
            total += item.value
        }
        i += 1
    }
    ret total
}
```

The compiler: stack-promote `total`; place `xs` in a small pool in this frame; drop/reset at return. User never frees.

### Mutation permission without new keywords

```a7
// Proposed. Binding `xs` cannot be rebound. Referent grows.
append_one :: fn(xs: ref List(i32), v: i32) {
    xs.append(v)
}

main :: fn() {
    xs := List(i32).empty()
    append_one(xs, 7)
}
```

This is L6 on the current `ref` surface. Functional style also works and enables reuse:

```a7
// Proposed. Unique `xs` consumed and produced; lowering may reuse the buffer.
grow :: fn(xs: List(i32), v: i32) List(i32) {
    xs.append(v)
    ret xs
}

main :: fn() {
    xs := List(i32).empty()
    xs = grow(xs, 7)
}
```

### World as a pool; scratch as an arena

```a7
// Proposed.
Entity :: struct {
    hp: i32
    target: usize
}

World :: struct {
    ents: List(Entity)
}

step :: fn(world: ref World) {
    damage: List(i32) = List(i32).empty()
    i: usize = 0
    while i < world.ents.len {
        e := world.ents.get(i)
        if e != none {
            damage.append(1)
        }
        i += 1
    }
    // `damage` does not escape: inferred scratch, reset on return.
    // `world.ents` lives in the caller's store.
    i = 0
    while i < world.ents.len {
        d := damage.get(i)
        if d != none {
            world.ents.add_hp(i, 0 - d.value)
        }
        i += 1
    }
}
```

Call `step` in a tick loop and the scratch store is reused (L18). That is the “compiler groups stuff as arenas and pools” sentence, in code.

### What we reject, and the rewrite

```a7
// Proposed rejection.
bad_return :: fn() []i32 {
    xs := List(i32).empty()
    xs.append(1)
    ret xs.items()     // ERROR: view of local store
}

// Rewrite: return the owner.
good_return :: fn() List(i32) {
    xs := List(i32).empty()
    xs.append(1)
    ret xs
}
```

```a7
// Proposed rejection.
bad_alias :: fn() {
    p := Node{value: 1, parent: 0, left: 0, right: 0}
    q := p              // if Node later owns a resource, this moves;
                        // if Node is plain data, this copies bytes.
}
```

Plain `Copy` records copy. Resource-owning records move. There is no third implicit “alias the heap object” (that is today’s bug).

---

## What to tell the controlling session

1. **Do not implement Cluster CC.** Do not treat G2(c) regions as optional flavoring. L15–L18 *are* inferred stores on a handle-shaped heap, with affine owners for resources and XLA-style reuse as the optimizer.
2. **Do not wait for mode keywords.** L6 is already enough permission surface (`ref` at calls). Stored `ref` fields should be replaced by ids under the approval rule.
3. **Build IR first** (track 4), repair joins/effects (track 5), then storage planning (track 6). Spikes on the AST will lie.
4. **Write the twelve falsifiers now**, labeled proposed. The design is whatever survives them without GC, RC, or traps.
5. **Promise this, not Python:** programs look like Python; data layout and lifetimes look like a game engine that a compiler wrote; when the compiler cannot prove a placement, it says so and names the table/frame you must introduce.

That is next-generation only in the assembly of known parts: MLKit regions on a DAG, Hylo-style exclusivity without lifetime parameters, Perceus reuse without counts, XLA packing for tensors, Odin/Zig arenas as lowering, indices as the public pointer. Each piece is old. The forbidden residual (GC/RC/traps) is what makes the combination sharp — and what makes unrestricted Python graphs out of scope.

I did not run code, launch other agents, or change the repository.The combined goal is achievable for A7’s actual v1 programs, and not achievable as “Python object graphs, no annotations, no residual allocator.” The design that works is not a compile-time garbage collector. It is **frame-scoped storage planning**: the compiler infers *where* data lives and *when the whole group dies*, then lowers that to arenas, typed pools, indices, and in-place reuse. Python-simple is the surface. Jai/Odin/Zig is the code that comes out.

I did not run the compiler or any program. Claims about current A7 behavior below are from the documents I read, not from a fresh compile.

---

## Facts I verified (documents only)

From `docs/plan/decisions.md`, `docs/plan/README.md`, `docs/SAFETY_CONTRACT.md`, `docs/SPEC.md` §§3.3–3.5, 6.2–6.3, 8, A.4, and the cited research:

- **L15–L18** lock automatic, compile-time, data-oriented memory management; Python-simple surface; compiler-grouped arenas/pools; reuse/optimization ambition. No GC and no RC as the core (brainstorm + your constraints).
- **Current surface:** `new` / `del` / `defer del` / `ref` / `nil`. Heap lives until explicit `del`. Public `&` / `*` / `.adr` / `.val` are banned. Argument *bindings* are immutable; `ref` parameters mutate caller storage. Recursion is a compile-time error.
- **Fail-closed:** unproven risky operations are rejected before Zig is emitted. Codegen consumes `BackendPlan`; it must not invent safety.
- **G2** currently stages (a) syntax-free affine refs, then (b) parameter modes, then (c) regions “if gaps remain.” Tensor saved-value lifetime depends on G2.
- **Track 4** is typed IR + CFG; **track 5** is proof repair; **track 6** is the memory model. The current safety pass is an AST walk with name-keyed facts (`a7/safety.py`: `BackendPlan`, `moved_symbols: set[str]`). There is no escape analysis, no CFG, no points-to.
- **Existing examples already use indices, not pointers:** `examples/025_linked_list.a7` (`next: isize`), `examples/026_binary_tree.a7` (`left`/`right: usize`). `examples/011_memory.a7` is the `new` + `defer del` idiom.
- **Cluster CC** in `08-decisions.md` is still **PROPOSED**. D.049 “no storable references” is **not** a locked user decision. L6 does not approve mode keywords.
- Plan-documented observation (not rechecked by me): `p := new Pt; q := p; del p; del q` compiles and would emit two `allocator.destroy` calls.

One documented claim is wrong and must not survive into the design: `docs/lang-safety/05-for-a7.md` §3.3 says “No recursion → no cyclic ownership graphs.” The recursion ban is about the **call graph**. Data graphs can still be cyclic. Trees, parent pointers, and ECS worlds are the point of L15.

---

## 1. Is the combined goal achievable?

**For the programs v1 already locked — training steps, game-style worlds, request loops, owned tensors, isolated tasks — yes, with restrictions that match data-oriented design rather than fight it.**

**For “any graph a Python GC would collect, inferred perfectly, zero runtime allocator, peak memory equal to a perfect `free`,” no.** That is not an engineering gap. It is the shape of the problem.

### Where it breaks, exactly

Compile-time memory management can decide a lifetime only from **structure**: scopes, loops, calls, uniqueness, and explicit frames (tick, request, training step, task). A tracing GC decides lifetimes from **runtime reachability**. Those are different predicates.

The break is any object whose last use is “whenever nothing can reach it anymore,” when that reachability is not a function of the CFG:

| Pattern | Why inference cannot place it | What happens if you force it |
| --- | --- | --- |
| Arbitrary heap graph with stored addresses | Last use depends on aliasing you cannot close | Reject, or hold the whole heap until process exit (a leak named an arena) |
| Interior view into a buffer that later reallocates | Grow invalidates addresses; even indices are wrong if you compact | Reject the view across grow, or forbid compact while handles exist |
| Cache / intern table with data-dependent eviction | Lifetime is a policy, not a scope | Must be an explicit table with `put`/`get`/`clear` |
| Escaping closure over a local buffer | Capture outlives the frame | Move/copy the capture, or reject |
| Cross-task alias of a store the receiver does not own | Two frames, one storage | Move the value or the whole store; never send a raw handle |
| Native kernel that keeps a pointer after return | A7 no longer controls the referent | Opaque owned handle + documented borrow interval; otherwise reject |

Rice-style limit, stated operationally: **liveness for arbitrary pointer graphs is not decidable in a way that is both sound and precise.** Every real system picks one of:

1. Restrict the language (Hylo, Austral, affine Rust without `Rc`).
2. Approximate and **over-retain** (MLKit regions, game-frame arenas).
3. Leave **residual runtime work** (RC, GC, Vale generation traps, Swift exclusivity checks).

A7’s constraints already choose (1) and allow a controlled amount of (2). They forbid (3) as the *safety* mechanism. That is a coherent point in the design space. It is not Python.

### Least-bad restrictions (accept these; they *are* the design)

1. **No stored addresses.** Already true. Keep it. The heap the user thinks in is **tables of records plus `usize` ids**, not objects with pointers in fields.
2. **A stored “reference” is an index into a store the compiler can name**, not a `ref T` field that aliases an independent allocation.
3. **Views (slices, tensor views) are local and non-escaping** unless the callee returns *ownership* of the backing store, or the view is into a parameter that the compiler can tie to the caller.
4. **Growth while a view is live is a compile error.** Growth while only *ids* are live is fine if you never compact, or if ids are generational and lookup returns `?T`.
5. **Cycles are numbers, not owners.** One table owns the nodes. `parent: usize` is not an ownership edge.
6. **Long-running programs have compiler-visible frames.** The body of `for request in server`, `for tick in world`, and `for step in train` is a frame. Temporaries die at iteration end. What survives must be stored in a named long-lived table (`world`, `session`, `conn_table`).
7. **When placement is unproven, reject.** Do not leak, do not insert RC, do not insert a collector, do not emit a trap “just in case.”

### Least-bad residual runtime work (this is not a GC)

Fail-closed still allows **typed, defined results**. It does not allow “the CPU might segfault, or we panic to be safe.”

Keep:

- **Allocator calls** to grow a store (`mmap`/`malloc` of arena chunks, pool slabs). Inferred arenas still sit on an allocator. Jai/Odin/Zig do this too.
- **Bump / free-list inside a store.** O(1) allocate; bulk reset at frame end. No mark, no sweep, no counts on the fast path.
- **Allocation failure** as `?T` / `Result` (already the `new` surface).
- **Checked size arithmetic** for capacities, shapes, strides. Ordinary `+ - *` wrap (L5); allocation sizes must not.
- **Handle lookup** as a value: `world.get(id) -> ?Entity`. A miss is a domain result, not a UAF trap.
- **Tensor shape/overlap preflights** when dimensions are runtime values.
- **Channel closed / send failure** as typed results.

Do not keep, even as “fallback”:

- Tracing GC
- Reference counts as the ownership mechanism (Perceus-style *reuse analysis* is fine *after* uniqueness is proved; the counts themselves are not)
- Vale-style generation compare that panics
- Swift-style dynamic exclusivity traps
- Hidden copies (COW) that can allocate on mutation without a visible failure path

“Resolved at compile time” should mean: **every drop, reset, move, and reuse is inserted by the compiler at a known program point; there is no collector and no count.** It should not mean “the process never calls malloc.”

Over-retention is the remaining honest cost. A request-scoped arena that dies at the end of the handler may hold a 4 KB parse tree until the handler returns even if the tree died at line 20. That is the MLKit/game-arena trade: **predictable, slightly high watermark, no pauses.** For v1 that is the right trade. Precise last-use free is an optimizer (L18), not the safety story.

---

## 2. Strongest candidate architecture

Name it internally **storage planning**, not “compile-time GC.” Three layers, one user story.

### User story

You write values, lists, tables, and ids. You do not free, name allocators, or write lifetimes. The compiler decides stack vs pool vs arena, groups objects that die together, reuses buffers when the old value is dead, and rejects the program when it cannot.

### Layer A — Affine owners for resources (necessary, not sufficient)

This is G2(a), and it must land, but it is **not** L15–L18. It makes today’s `new`/`del` sound.

- A heap owner is moved, not copied.
- Scope exit drops it (reverse declaration order).
- `del` becomes optional early-release, conflicting with `defer del` and with a later use.
- `ref` parameters are **temporary access**, not a second owner.
- Files, sockets, channel ends, native kernel handles live here.

Without this, inferred arenas are unsound because `q := p; del p; del q` still exists.

### Layer B — Inferred stores (this *is* L15/L17)

Every allocation is assigned to a **store** attached to a **frame**.

| Store kind | When the compiler chooses it | Lowering |
| --- | --- | --- |
| Stack / registers | Does not escape the frame; size known | Zig locals |
| Typed pool | Many values of one type, same frame, need stable indices, insert/remove | SoA or AoS slab + free-list of slots |
| Bump arena | Mixed types, bulk death, no individual free | `ArenaAllocator`-style reset |
| Reused scratch | Loop/step with the same shape each iteration | One store, `reset` at the back edge |
| Session store | Training graph, optimizer, world | Long-lived store; explicit export copies out |

Placement algorithm, in order:

1. **Escape analysis.** Does this allocation leave the current frame (return, field of escaping object, global, closure, channel, native)? If no: stack or frame scratch.
2. **Region/lifetime inference.** If it escapes, to which *least* frame that covers all uses? Tofte–Talpin region assignment on a **DAG call graph** (the recursion ban makes the lattice well-founded). Over-approximation is allowed; under-approximation (free too early) is not.
3. **Homogeneity.** Same type + index-heavy access → pool. Mixed → arena.
4. **Uniqueness / affinity.** At most one mutable path to a location at a time (call-site exclusivity). Unique dead value → storage reusable (Perceus *without* RC).
5. **Liveness-based packing.** Inside a frame, buffer lifetimes are intervals; pack them (XLA/TVM memory planning). This is L18.
6. **Layout.** If all access is `field` of `table[id]`, SoA is a behavior-preserving transform. If FFI needs a C layout, do not transform.

### Layer C — Handles, not pointers

User-level “I have a reference to an entity” is `EntityId` (`usize`, optionally `{index, generation}` as a value). The compiler never lowers that to a raw pointer the user can store.

This matches `025`/`026` and matches DOD. It also dissolves the parent-pointer / cycle problem.

### Analyses and the IR they need

Do not hang this on the current AST + `FactMap`. Track 4 is the real prerequisite; the brainstorm never says so.

Required IR, after monomorphization (A7 already specializes generics):

1. **Typed CFG** with explicit sequencing. Joins and loops are first-class. (Today’s snapshot-restore in `safety.py` is documented as unsound for facts; the same shape cannot carry ownership.)
2. **Ownership SSA** (Swift SIL/OSSA is the right prior art): every value has a unique owner at each point; borrow/move/drop are SSA uses. This is how you do last-use reuse without a collector.
3. **Storage identities**, not variable names. `p` and `q` after `q := p` are the same allocation. Fields, slice projections, and tensor views are projected regions of a storage id.
4. **Effect summaries** on every function, serialized for public APIs:
   - reads / writes / resizes / drops of each argument
   - allocation into which frame
   - returned storage dependencies (“returns owner” vs “returns view of arg 2”)
   - globals, callbacks, suspension
   A single lattice `borrow < inout < consume` (D.041) is too poor. A function can read A, mutate B, return a view of C, and allocate into the caller frame.
5. **Points-to / projection aliasing** for fields, `arr[i]` vs `arr[j]`, overlapping tensor views. Exclusivity is about storage, not names.
6. **Region/store annotation** on each allocation and each view: `(store_id, frame_id)`.
7. **Liveness intervals** of buffers inside a frame, for packing and in-place reuse.
8. **Backend plan extension:** not only `index`/`deref`/`cast`, but `drop`, `reset_store`, `reuse_buffer`, `handle_lookup`. Codegen must not reconstruct this from spelling.

Whole-program compilation is not optional for L17. Separate compilation would freeze effect summaries without seeing allocation grouping. A7 already compiles a program, not a shared library zoo; use that.

### How the locked constraints help

- **Recursion ban.** Call graph is a DAG. Region nesting is finite. Stack-budget analysis becomes a real number (A7 frames only; native kernels remain a separate bound). Generated drop of a deep owned tree must still be **iterative** — a compiler-emitted recursive destructor would reintroduce unbounded native recursion. Use an explicit stack or a pool reset.
- **Immutable argument bindings.** Callee cannot rebind. Large values may be passed by const pointer. This does *not* give `noalias` by itself (Odin/Zig lesson in the GLM ownership report). Exclusivity analysis does.
- **No public `&`/`*`.** Users cannot manufacture aliases the IR does not see. That is the single biggest reason inferred stores are feasible. Guard this at FFI: `cast(ref T, usize)` must stay illegal.
- **Whole-program + monomorphization.** Store placement and buffer packing see the real call graph, not generic soup.
- **Fail-closed.** Forces diagnostics instead of a silent GC fallback, which is what keeps the “as Zig” performance story honest.
- **`usize` as the index type.** The language is already biased toward handles. Do not add a parallel pointer vocabulary.

G4 (stored function values) is a memory-model dependency, not a side issue. A struct field holding a function can hide recursion and can capture stores. Either forbid stored function values, or give the call graph type-informed edges and treat escaping closures as owning their captures. Option (a) in G4 is the one that keeps storage planning tractable.

---

## 3. New concepts: keep few user-visible, rename the internals

The brainstorm’s five names mix compiler IR with a language. That will leak into the user model and destroy the Python-simple promise.

### Compiler-internal (users never write these)

| Draft name | Verdict | Replace with |
| --- | --- | --- |
| **Lifetime group** | Sounds like Rust lifetimes; users will try to write it | **Store** — the allocation bucket. Kind: arena or pool |
| **Family** | Collides with type families | **Pool** — a typed store with dense slots |
| **Home** | Vague | **Frame** — function activation, loop iteration, task, training step, process |
| **Link** | Too pointer-like | **Handle** / **id** — `usize` (optional generation as data, not as a pointer header) |
| **Boundary** | Fine as IR jargon | Keep internally as **escape edge** (return / global / channel / native / capture) |

A **frame** owns zero or more **stores**. A **handle** is valid only for a named store. An **escape edge** requires moving a store, copying, or rejection.

### User-visible (aim for three ideas, not five)

1. **Values.** Copy if they are plain data; move if they own resources. No keyword.
2. **Tables and lists.** Owned collections. `append`, `get`, `remove` are ordinary calls. The compiler places the backing store.
3. **Ids.** `id := world.spawn(e)` returns a `usize` (or a distinct `EntityId` alias). `world.get(id)` returns optional. No `*` anywhere.

Ordinary code does not say arena, pool, region, lifetime, borrow, or consume.

### User-visible only when inference fails (optional v1, better as v1.1)

A **named frame** for long-lived or multi-allocation scratch, if the compiler cannot see the loop/request/step:

```a7
// Proposed — only as a hint when the diagnostic asks for it.
// Not required for the common path.
session := Frame.create()
// ... allocations inferred into session ...
// session ends at scope exit; bulk reset
```

I would **not** ship this in the first cut if diagnostics are good. Game/server/train loops already *are* frames if the compiler treats iteration bodies as frames by default.

Do not add `region r;` as Cyclone did. Cyclone needed annotations on ~8% of ported lines. That is the opposite of L17.

`ref` stays as today’s **mutation permission at a call**, not as a storable heap pointer. That matches L6 without mode keywords. Stored `ref T` fields should go away in favor of ids or owned nested values. That is a breaking change; L2 allows it through the approval rule.

---

## 4. Hard cases

All examples below are **proposed** behavior, not current A7.

### Returning allocations

Return **owners**, never views of callee storage.

```a7
// Proposed. The list is an owner. The compiler places its pool
// in the caller, or moves a heap owner out of the callee.
make_ids :: fn() List(i32) {
    xs := List(i32).empty()
    xs.append(10)
    xs.append(20)
    ret xs
}
```

Returning `xs[0..2]` of a local is a compile error (this is today’s MS-8 hole). If you need a slice of a *parameter*, v1 should still reject it unless you later approve a dependency contract (“returns a view of arg 1”). Silent copy-on-return is not acceptable: it allocates and can fail.

### Growing lists with “references” into them

This is the design fulcrum. Addresses into a reallocating buffer are poison. **Indices are not**, unless you compact.

```a7
// Proposed.
xs := List(i32).empty()
xs.append(1)
i: usize = 0
xs.append(2)
v := xs.get(i)          // OK: id/index, not an address
// slice := xs.items()  // a view
// xs.append(3)         // ERROR if slice is live: grow while viewed
```

Rule:

- **Index/id** may survive append.
- **View/slice** may not survive grow, remove-compact, or move of the backing store.
- **Remove** either leaves holes (ids stay valid; pool + free-list) or uses generational ids.

That is how every engine that is not a GC actually works.

### Cyclic graphs and parent pointers

Do not infer a pointer web. One owning table.

```a7
// Proposed. Same idea as examples/026_binary_tree.a7, grown up.
Node :: struct {
    value: i32
    parent: usize
    left: usize
    right: usize
}

Tree :: struct {
    nodes: List(Node)
    empty: usize
}

set_left :: fn(tree: ref Tree, parent: usize, child: usize) {
    p := tree.nodes.get(parent)
    if p == none { ret }
    c := tree.nodes.get(child)
    if c == none { ret }
    // mutation goes through tree, not through stored refs
    tree.nodes.set_parent(child, parent)
    tree.nodes.set_left(parent, child)
}
```

Cycles are `usize` equalities. Drop of `Tree` resets one pool. No recursive destructor.

### Caches and globals

A global is the process frame. That is the coarsest store. An unbounded “dict of objects until forgotten” **is** a GC. Do not infer it.

```a7
// Proposed. Explicit table, explicit eviction.
Intern :: struct {
    strings: List(string)
}

intern :: fn(tab: ref Intern, s: string) usize {
    tab.strings.append(s)
    ret tab.strings.len - 1
}
```

If you want LRU eviction, that is a library policy on a table, not a language lifetime.

### Closures

- Immediate callback argument: may borrow for the call.
- Stored / returned closure: **owns** captures (moved or copied). Capturing a slice of a local is rejected.
- Prefer G4(a): no function values in fields. Callback tables for AI/kernels should be compiler-known stdlib, not user function pointers in structs.

### Long-running loops and servers

The iteration body is a frame. Scratch resets. Survivors go into a table owned by the loop header.

```a7
// Proposed.
World :: struct {
    entities: List(Entity)
}

run :: fn(world: ref World, n: usize) {
    tick: usize = 0
    while tick < n {
        // Frame = this iteration.
        // Scratch inferred here and reset.
        dt: f32 = 0.016
        step(world, dt)
        tick += 1
    }
}
```

If `step` allocates a temp `List` that does not escape, that list’s store is reused next tick (L18). If it stores into `world`, placement is the world store.

This is Odin’s `temp_allocator` / game scratch arena, inferred.

### Entity removal

```a7
// Proposed. Generation is data on the id, not a pointer header check that traps.
EntityId :: struct {
    index: usize
    gen: usize
}

spawn :: fn(world: ref World, e: Entity) EntityId { /* occupy a free slot, bump gen */ }
despawn :: fn(world: ref World, id: EntityId) { /* free slot, bump gen */ }
get :: fn(world: ref World, id: EntityId) ?Entity {
    // miss if index empty or gen mismatch — typed none, not a trap
}
```

Slot reuse is allowed because a stale id does not resolve to a new occupant. Fail-closed: the *unsafe* operation (load through a dangling pointer) never exists. The *safe* operation (optional lookup) does.

### Tensors, views, autodiff tape

Follow the Codex memory-design **T1 (session ownership)**, not T2 (RC-backed tensor objects). v1 already requires A7-owned reverse-mode AD (L9) and checkpoint recovery (L10). A session is a frame.

```a7
// Proposed.
train_step :: fn(session: ref Session, x: TensorId, target: TensorId) ?f32 {
    y := tensor_mul(session, x, x)
    loss := tensor_sum(session, y)
    grads := tensor_backward(session, loss)
    if grads == none { ret none }
    // ERROR if we mutated x while saved:
    // tensor_fill(session, x, 0.0)
    tensor_release_graph(session, loss)
    ret tensor_to_f32(session, loss)
}
```

Rules:

- A `TensorId` names session storage; it is not a borrow and not an owner of bytes.
- A **view** (slice, transpose, broadcast) is a local projection: shape, strides, offset. It cannot outlive the session entry. Writable overlapping views are exclusivity errors (same as `swap(arr[i], arr[i])`).
- Tape saved values are owned by the session until `backward` + release, or until step end.
- Mutation of saved storage: **reject or return a preflight failure**; do not snapshot implicitly (that allocates).
- Intermediates: liveness packing reuses buffers across the step DAG. Reverse-mode needs saved values; those intervals are longer. This is exactly XLA buffer assignment on a DAG — and A7 source is already non-recursive, so the step graph is a DAG if you ban callback-shaped ops or treat them as opaque nodes.
- Export / checkpoint: copy or move into an independent owner (file, owned buffer). A checkpoint must not be a view into live session memory.

Optimizer state (`m`, `v`, master weights) lives in the session store for the run; it is not scratch.

### Tasks and channels

Move the **value**, not a handle into a store the receiver does not own.

```a7
// Proposed.
send_job :: fn(ch: ref Chan(Job), job: Job) SendResult {
    // on failure, job is still owned by the caller
}

// ERROR: sending EntityId into another task that does not own world
// ch.send(id)

// OK: send the record, or send an owned snapshot
ch.send(copy_entity(world, id))
```

Task-private stores. Join is mandatory for owned child tasks. Do not claim deadlock freedom (already the GLM security position). Cancellation: a native kernel must finish or acknowledge before buffers reset.

### Native kernel buffers

Opaque owned handle. The kernel **borrows** A7 storage for the call. If a library keeps the pointer (cuBLAS-style async, or a persistent plan), that is a different resource with an explicit lifetime, not a slice.

DLPack is the right foreign protocol: producer deleter, not “trust this pointer.” Overlap of GEMM `A` and `C` is a preflight, not UB.

---

## 5. When inference fails

**Reject. Explain. Offer a rewrite. Do not fall back to a collector.**

That is the only policy that keeps both L15 (“as Zig”) and the safety contract. A GC fallback would make two languages, and ReleaseFast would be a different program.

### Diagnostics (the Python-simple part)

The message must name the allocation, the escape edge, and one legal repair. Three templates cover almost all failures:

1. **Escaping view:** “`xs[0..n]` is a view of local `xs` and is returned. Return `xs` itself, or copy into a new list.”
2. **Grow while viewed:** “`xs.append` reallocates while `view` is live. Index with `usize`, or finish using `view` first.”
3. **Handle leaves its store:** “`id` refers to `world.entities` and is sent to another task. Send the entity value, or share `world` as a single owner (not allowed across tasks — copy or move the world).”

Optional **hints** (`Frame.create()`, “put this in `world`”) are fine as suggested edits. They must not be required on the happy path.

### What “fallback” is allowed

| Tempting fallback | Keep? |
| --- | --- |
| Over-retain until frame end | Yes — this is region inference working |
| Typed `?T` lookup / alloc failure / shape mismatch | Yes — values, not traps |
| Insert RC when a cycle of owners is detected | No |
| Insert GC for “too hard” functions | No |
| Vale generation panic | No |
| Implicit deep copy to make a return safe | No (hidden alloc + failure) |
| “Unsafe, we proved nothing” | No |

If a program is a true cache/graph in Python style, the rewrite is **make a table**. That is the DOD tax. It is also how you get the performance the user asked for. Charging that tax at compile time is the product.

---

## 6. Prior art — what to steal, what is a trap

I did not re-fetch these papers for this note. Names and lessons are from the repo’s research plus standard knowledge of the area. Treat paper-level details as things to re-read, not as freshly verified.

### Directly usable (steal the mechanism)

| Source | What to take | Trap |
| --- | --- | --- |
| **Tofte–Talpin region inference** (POPL 1994); **MLKit** | Assign allocations to nested regions from types/effects; free en bloc | They added **tag-free GC on top of regions** (Elsman) because regions **over-retain** and SML has unrestricted data. Do not advertise MLKit as “GC replaced.” A7’s recursion ban and handle discipline are why you might not need their GC. |
| **Cyclone** (Grossman et al., PLDI 2002; Swamy et al., SCP 2006) | Lexical regions, region subtyping, fat pointers as slices, non-null vs nullable | ~8% of C lines changed; region **annotations leak**. Also still a C dialect with addresses. Use as the *internal* region story, not the surface. |
| **Hylo / Val** (Racordon et al., JOT 2022; hylo-lang.org) | References as **call-duration modes**; call-site exclusivity; no lifetime parameters | Implementation is not a finished production compiler. “No storable refs” fights today’s `ref` fields — resolve by **ids**, not by pretending fields do not exist. Mode keywords are not approved (L6). |
| **Swift OSSA** (SIL ownership SSA; SE-0176 exclusivity; SE-0390/0446 noncopyable / nonescapable) | The **IR shape**: ownership in SSA, drop points, non-escaping values | Production Swift **falls back to dynamic exclusivity traps**. A7 cannot. Also ARC remains for class objects — do not copy that split. |
| **Perceus** (Reinking et al., PLDI 2021); **Koka** | Uniqueness ⇒ in-place reuse; drop at last use | The paper is **RC elision**. If you keep the counts, you have RC (cycles, thread costs, destructor storms). Steal *reuse*, drop the counts. Koka is functional; A7 mutation needs exclusivity on top. |
| **Clean uniqueness typing**; **linear update** | In-place update of unique arrays | Easy to over-reject once aliases exist. Pair with handles so graphs are not unique-pointer webs. |
| **XLA / TVM / Halide / MLIR buffer assignment** | Liveness intervals → pack tensors into a fixed workspace | Works on a **known DAG**. Perfect for a training step. Not a general language heap. |
| **Go/Java escape analysis** | Stack-allocate non-escaping; scalar replacement | Only answers stack vs heap, **not when to free**. Necessary but nowhere near sufficient. |
| **MLton**; **Stalin** (Siskind) | Whole-program flattening, unboxing, aggressive lifetime | Compile-time cost; Stalin is a warning that “next-gen” whole-program can become a research compiler that only likes closed programs. A7 is already whole-program — use MLton’s *engineering*, not Stalin’s maximalism. |
| **Odin** context allocators, `temp_allocator`; **Zig** `ArenaAllocator`, `MemoryPool`; **Jai** (qualified: no public spec) implicit allocator + SOA | The *lowering targets* and the frame-scratch idiom | These are **manual**. Inferring them is the A7 bet. Do not copy “pass an allocator everywhere” into user code. Do not claim Jai semantics you cannot cite. |
| **Inko** isolated heaps + channels | Concurrency pairing: no shared mutable heap | Fine for G7. Not a sequential memory story. |
| **Verona** regions as the unit you *send* | Send a whole store to a task | Research/paused. Use the idea, not the language. |
| **Austral** | Proof that a small linear checker is implementable | Too linear for Python-simple (must consume exactly once). Affine + frame reset is enough. |
| **DLPack**; **PyTorch autograd saved-tensors + version counters** (docs, not a dependency) | Foreign buffer ownership; saved-value vs mutation | Version-after-mutation detects bugs too late. Prefer reject/preflight. |

### Study, then mostly avoid as the core

| Source | Why it looks attractive | Why it is a trap for A7 |
| --- | --- | --- |
| **Rust** borrow checker + `'a` | Gold-standard safety | Lifetime parameters are the opposite of L17. Steal affine moves and exclusivity *invariants*, not the surface. Tree Borrows is an unsafe-alias model for LLVM, not an A7 user model. |
| **Vale** generational references | “Most checks elide, a few remain” | Residual **panic** on mismatch violates fail-closed. Typed `?T` lookup is the A7-shaped cousin; do not emit a check that traps. Alpha status. |
| **Pony** `iso`/`val`/`ref`/`box`/`tag`/`trn` | Race freedom | Six user-facing capabilities. Also **ORCA GC** for cycles. Wrong surface, wrong residual. |
| **Swift ARC / Apple RC** | Ergonomic sharing | RC is banned as core; class vs struct split is the opposite of one heap model. |
| **Go/Java GC** | The “simple like Python” feeling | This *is* the thing L15 forbids. Escape analysis inside them is still not a lifetime system. |
| **C++ RAII + `unique_ptr`** | Deterministic drop | Does not stop dangling views or iterator invalidation. A7 already needs the extra analyses. |
| **Cluster CC / D.040–D.049 as written** | Already in-repo | Contradicts itself (storable vs non-storable refs), mis-cites Odin/Zig for deep immutability, and is not user-approved. Do not implement the cluster as a block. |

**Lobster** (Wessing): compile-time RC elision + uniqueness. Useful as a *small-language existence proof* that a games-oriented compiler can drop most counts. Trap: residual RC and a different language shape. Same lesson as Perceus: copy the elision, not the counts.

**ASAP** as used in the brainstorm (“static deallocation”): treat as the family of **compile-time free insertion** (region inference, liveness, first-shot GC in ML compilers), not as one drop-in algorithm. The win is whole-program liveness → `free`/`reset` at known points. The failure mode is the same as MLKit: either over-retain or reject.

---

## 7. Critique of `docs/plan/memory-brainstorm.md`

The draft is honest about the central tension and right to demand a corpus. It is mis-ordered as an attack on L15–L18, and it treats **layers as alternatives**.

### What is good

- Fail-closed, no silent leak/early free.
- Corpus-before-mechanism instinct.
- Evaluation includes peak memory and reuse versus a manual ideal, not just “does it compile.”
- Explicit open questions on rejection vs hints vs runtime checks.

### What is mis-ordered

1. **Session 1 (contract) before any programs is too abstract.** “Like GC” only becomes a sentence once you have a parent pointer and a growing list. Merge sessions 1–2. Write the contract *on* ten programs.
2. **Session 3 is a bake-off of 13 candidates.** Escape analysis, regions, pools, handles, SoA, Perceus reuse, and XLA packing are **one stack**. Scoring them as rivals will produce a false winner (probably “affine + Hylo modes”) that does not deliver L17 arenas.
3. **G2(a) affine refs is a soundness patch for today’s `new`/`del`.** The brainstorm lets it eat the whole design. Sequence should be: proof-engine joins (track 5) → affine owners for resources → inferred stores+handles (L17) → reuse/packing (L18). Regions are not “later if gaps remain” (plan G2 option c). For L17 they are the *middle*.
4. **Feasibility spikes are session 6.** Hand-trace five programs in session 2. The design will die on program 3 (grow+view) or 7 (entity despawn), not after a literature survey.

### What is missing

- **Typed CFG / ownership SSA as a hard prerequisite.** Current `SafetyProofPass` cannot host this.
- **Handles/indices as the default heap**, despite `025`/`026` already doing it. This is the DOD answer and it is underweighted versus Tofte–Talpin.
- **Frames for the workloads v1 already locked** (training step, task, tick). Open question 1 (“games, servers, CLI, or AI first?”) is **already answered by L7–L10 and G7**. Stop asking it.
- **Allocation-size arithmetic** vs wrapping `+ - *` (L5 scope limit).
- **Iterative destruction** so generated drop does not recurse.
- **Kill the “no recursion ⇒ no cyclic data” error** from `05-for-a7.md`.
- **SoA identity:** layout transform is legal *because* there is no address-of. Say that, and say FFI layouts are exempt.
- **T1 vs T2 tensor ownership** is decided enough: T2 is RC. T1 is the only option compatible with the constraints.

### What is unnecessary / contradictory

- **Compile-time RC elision as a candidate** contradicts “no RC as core.” Demote to an optimizer footnote.
- **Hidden handles “with or without generation checks”** as a maybe. Decide now: generation is part of the id value; lookup returns `?T`; no trap.
- **User-visible lifetime group / family / home** as starting names. Decide user-visible vs internal *first*, or those words will ship.

### Corpus that falsifies fastest

Write these as proposed-syntax fixtures before any more mechanism debate. If a candidate cannot say yes/no/rewrite on all twelve, it is not a design.

1. **Return a newly built list** (must move owner, not a slice).
2. **Append while a slice of the list is live** (must reject).
3. **Append while only a `usize` index is live** (must accept).
4. **Tree with `parent: usize`** (must accept; one table).
5. **Two nodes pointing at each other** (must accept as ids; must reject as stored `ref` owners).
6. **Intern/cache table in a global** (must be an explicit table, not inferred GC).
7. **Closure stored in a struct capturing a local buffer** (reject or own a copy; G4).
8. **Tick loop: spawn, despawn, use old id next tick** (`get` returns none; no UAF path).
9. **Request loop: per-request temps + a connection table** (temps reset; conns survive).
10. **`y = x * x`; mutate `x`; `backward(y)`** (reject or preflight; saved-value).
11. **Channel send of `EntityId` without sending `World`** (reject).
12. **GEMM with aliased native buffers** (reject or typed failure before the kernel).

Secondary: checkpoint round-trip (L10), failed `append` leaves the original list usable, deep pool reset does not blow the native stack.

Independent review should score those twelve before any syntax is approved. GLM still owns the security pass (L12).

---

## 8. Proposed A7 examples (not current language)

Constraints honored: no recursion, `usize` indices, no `&`/`*`, immutable argument bindings, `ref` only as today’s mutation permission.

### Ordinary code: no `new`/`del`

```a7
// Proposed. List backing store inferred: caller frame, or moved out.
sum_extra :: fn(base: i32) i32 {
    xs := List(i32).empty()
    xs.append(base)
    xs.append(1)
    total: i32 = 0
    i: usize = 0
    while i < xs.len {
        item := xs.get(i)
        if item != none {
            total += item.value
        }
        i += 1
    }
    ret total
}
```

The compiler: stack-promote `total`; place `xs` in a small pool in this frame; drop/reset at return. User never frees.

### Mutation permission without new keywords

```a7
// Proposed. Binding `xs` cannot be rebound. Referent grows.
append_one :: fn(xs: ref List(i32), v: i32) {
    xs.append(v)
}

main :: fn() {
    xs := List(i32).empty()
    append_one(xs, 7)
}
```

This is L6 on the current `ref` surface. Functional style also works and enables reuse:

```a7
// Proposed. Unique `xs` consumed and produced; lowering may reuse the buffer.
grow :: fn(xs: List(i32), v: i32) List(i32) {
    xs.append(v)
    ret xs
}

main :: fn() {
    xs := List(i32).empty()
    xs = grow(xs, 7)
}
```

### World as a pool; scratch as an arena

```a7
// Proposed.
Entity :: struct {
    hp: i32
    target: usize
}

World :: struct {
    ents: List(Entity)
}

step :: fn(world: ref World) {
    damage: List(i32) = List(i32).empty()
    i: usize = 0
    while i < world.ents.len {
        e := world.ents.get(i)
        if e != none {
            damage.append(1)
        }
        i += 1
    }
    // `damage` does not escape: inferred scratch, reset on return.
    // `world.ents` lives in the caller's store.
    i = 0
    while i < world.ents.len {
        d := damage.get(i)
        if d != none {
            world.ents.add_hp(i, 0 - d.value)
        }
        i += 1
    }
}
```

Call `step` in a tick loop and the scratch store is reused (L18). That is the “compiler groups stuff as arenas and pools” sentence, in code.

### What we reject, and the rewrite

```a7
// Proposed rejection.
bad_return :: fn() []i32 {
    xs := List(i32).empty()
    xs.append(1)
    ret xs.items()     // ERROR: view of local store
}

// Rewrite: return the owner.
good_return :: fn() List(i32) {
    xs := List(i32).empty()
    xs.append(1)
    ret xs
}
```

```a7
// Proposed.
bad_alias :: fn() {
    p := Node{value: 1, parent: 0, left: 0, right: 0}
    q := p              // if Node later owns a resource, this moves;
                        // if Node is plain data, this copies bytes.
}
```

Plain `Copy` records copy. Resource-owning records move. There is no third implicit “alias the heap object” (that is today’s bug).

---

## What to tell the controlling session

1. **Do not implement Cluster CC.** Do not treat G2(c) regions as optional flavoring. L15–L18 *are* inferred stores on a handle-shaped heap, with affine owners for resources and XLA-style reuse as the optimizer.
2. **Do not wait for mode keywords.** L6 is already enough permission surface (`ref` at calls). Stored `ref` fields should be replaced by ids under the approval rule.
3. **Build IR first** (track 4), repair joins/effects (track 5), then storage planning (track 6). Spikes on the AST will lie.
4. **Write the twelve falsifiers now**, labeled proposed. The design is whatever survives them without GC, RC, or traps.
5. **Promise this, not Python:** programs look like Python; data layout and lifetimes look like a game engine that a compiler wrote; when the compiler cannot prove a placement, it says so and names the table/frame you must introduce.

That is next-generation only in the assembly of known parts: MLKit regions on a DAG, Hylo-style exclusivity without lifetime parameters, Perceus reuse without counts, XLA packing for tensors, Odin/Zig arenas as lowering, indices as the public pointer. Each piece is old. The forbidden residual (GC/RC/traps) is what makes the combination sharp — and what makes unrestricted Python graphs out of scope.
