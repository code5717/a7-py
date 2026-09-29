# A7 memory plan

Status: historical proposal, revision 3, 2026-09-16. Its detailed mechanisms
remain unapproved. Decisions L37-L42, recorded 2026-09-20, supersede the absolute
ban on collectors/counting, mandatory rejection when a runtime check suffices,
and independent-value semantics for growable-list assignment. Shared-list
identity and explicit copies must survive optimization. Read the current
[delivery roadmap](delivery-roadmap.md) before using this proposal.

The remaining text preserves the earlier proposal and review disagreements. Every breaking
change and gate recommendation needs user approval with examples under the
approval rule in the [ledger](decisions.md).

Revision 2 applied audits 1, 3, 4 and 5 from the
[edge-case audit](research/memory/edge-case-audit.md). Revision 3 applies audit 2
and eleven external [reviews](research/memory/review/README.md): Qwen, Kimi and
nine GLM runs, including the memory-safety and security review required by L12.

What revision 3 changes:

- Contract item 7 no longer claims that nothing else runs at run time. Section 6
  lists the planner, inserted copies, release work and generation maintenance.
- Contract item 8 adds the rejection classes the plan requires elsewhere.
- Contract item 5 releases the storage of a removed element, and names the session
  extent.
- A new contract item 13 states that A7 code has no data races.
- New gates M25, M28, M29 and M37 to M51 cover the native declaration surface,
  fact-engine soundness, data races, conditional close, block extents, index
  validity, determinism, size arithmetic, id width, the native supply chain,
  planner bounds, arena membership, checkpoint robustness, stale bytes, the L19
  metric, storage-owning unions, monomorphization and iteration semantics.
- Phase C is split into an additive phase and a later subtractive one.
- The corpus gains eight programs drawn from the reviews.

Three questions are recorded as disagreements between reviewers and are not
settled here: G4 with M6, M2 recoverability, and M11 extents. Gate M33 is a
separate case: every reviewer who examined it recommends the opposite of what the
gate says, and section 10 records that.

How the design was explored is in the [brainstorm record](memory-brainstorm.md).
Evidence is in [research/memory](research/memory/).

## Summary

Programmers write values in current A7 syntax. They never allocate, free, name
allocators or annotate lifetimes. The compiler decides where every value lives,
when storage is released and when storage is reused. It lowers that decision to
stack slots, arenas, pools and in-place updates in Zig. There is no garbage
collector and no reference counting. Performance and memory use are measured
against hand-written C or Zig.

Current behavior is a partial starting point. Observed 2026-09-15 with a real
Zig 0.16.0 Debug build: after `b := a; b.x = 2` on a plain struct, `a.x` stays 1,
and after `arr2 := arr; arr2[0] = 9` on a fixed array, `arr[0]` stays 1. Plain
structs and fixed arrays without slice, string or `ref` members already behave
as values. Compile-only probes show the exceptions: copying a slice, or a struct
holding a slice, shares storage; A7 accepts a write to a by-value array parameter
that Zig then rejects.

## Directions

From the ledger:

- **L15:** compile-time, data-oriented memory management with no garbage
  collector.
- **L17:** a Python-simple surface where the compiler groups allocations into
  arenas and pools.
- **L18:** storage reuse and optimization.
- **L19:** users should not care about memory.
- **L20:** powerful and simple, with C-like performance and memory use, not like
  C++.
- **L21:** no Zig-style memory mental load.
- **L22:** keep current A7 syntax and build from the Zig backend.

"Like Jai, Odin and Zig" means the predictability and performance of the generated
code, not their manual memory model.

## 1. Contract

For every accepted program:

1. **No garbage collector, no reference counts, no pauses.** A pause means work
   that scans or traces live data at a time the program did not choose. Releasing
   a large structure costs time proportional to its size, at a known program point.
2. **No use after free, double free or dangling reference in A7 code.** Native code
   is covered only to the extent its binding descriptor is correct (gate M12).
3. **Static release points.** Releases are placed on control-flow edges. No
   runtime drop flags. A resource closed on one branch and not the other needs
   either a per-edge release or a one-bit closed flag; gate M37 decides which.
4. **Copy is the meaning of assignment.** `b := a` produces an independent value.
   The compiler removes a copy only when it proves the removal unobservable, for
   example when `a` is never used again. There is no deferred copy-on-write and no
   runtime sharing state. When removal cannot be proven, the compiler copies at the
   binding and reports costly copies (gate M8).
5. **Bounded memory in loops.** A value that is unreachable after a loop iteration
   is released or reused by the end of that iteration. A reassigned binding
   releases its previous value at the reassignment. A growing collection releases
   its old buffer when it grows. Removing or overwriting an element of a
   collection releases or recycles that element's storage at that point, so an
   evicting cache stays flat. Every other value is released when control leaves
   the extent that owns it: call, iteration, task, training step, session or
   process. Whether a block or branch also ends an extent is gate M38; without it,
   a large temporary inside an `if` is held until the call returns.

   Assignment reads the right-hand side into a temporary before releasing the old
   left-hand value, so `m[k] = f(m[k])` is defined. The current compiler gets this
   wrong for `arr = [arr[1], arr[0]]`, which is a defect to fix in Phase B.
6. **Structured tasks.** A task ends before the scope that started it ends.
   Contract items 5 and 6 hold whenever control leaves the extent. A deadlock or
   endless loop never leaves it.
7. **No tracing, counting, scanning or deferred copying at run time.** Every other
   runtime memory operation the compiler inserts is listed in section 6 with its
   failure outcome.
8. **Rejections form a closed list.** The only memory-related compile errors
   users see are:
   1. Two changes to the same place at once, or a change while something depends
      on the value (exclusivity).
   2. A temporary view outliving its owner, or any structural change or
      overlapping write to the owner while a view is live.
   3. Returning or storing a `ref`.
   4. A stored function value that captures local data.
   5. Using a value after it moved into a task.
   6. A value carrying autodiff history leaving its training step.
   7. Changing a value a live autodiff tape saved.
   8. Native code retaining storage without a declared owner.
   9. Reading a variable no path initialized. This one is a correctness rule
      borrowed from v1 track 5, not a memory rule.
   10. A second `backward` on a loss whose recorded computation was consumed.
   11. Using a move-only resource after it moved or was closed.
   12. `ret`, `break` or recoverable failure inside a `defer` body.
   13. Writing through a loop binding, which is an immutable copy.
   14. Sending a typed id to a task without the table that owns its records.
   15. Returning a view of data received through `ref`.
   16. Violating a native descriptor other than by retention, such as moving a
       thread-affine handle into another task.
   17. Asking for a gradient with respect to an input that was rebound after the
       recorded computation used it.

   The classes group into four families: exclusivity (1, 7, 17), escape (2, 3, 4,
   6, 8, 15, 16), move and initialization (5, 9, 10, 11, 14), and form
   restrictions (12, 13). Classes 7 and 17 are both mutation of a value a live
   tape recorded. Gate M39 decides whether an unprovable index or key on a dynamic
   collection becomes a further rejection class or a runtime check in section 6;
   the list closes either way. This list is the complete set of memory-related
   rejections that gate M16 blesses; the rest of that gate's scope is in its row
   in section 5.

   Each diagnostic describes behavior and names a rewrite. Placement never fails
   visibly: when the compiler cannot place a value in a short extent, it copies
   the value out on the escaping path.
9. **No memory vocabulary in ordinary source.** Programs never write allocate,
   free, arena, pool, lifetime, borrow or allocator. The concepts users do meet
   are values, collections, optionals, typed ids and move-only resources (section
   2). Diagnostics and the optional memory report use plain terms.
10. **Iterative destruction.** Releasing deep structures never uses native
    recursion.
11. **Deterministic placement.** Identical source, target and compiler version
    produce identical placement and copy decisions, in Debug and ReleaseFast. The
    runtime planner and its cache eviction are deterministic for a given shape
    signature and build. Gate M40 covers what the compiler must change to make
    this true.
12. **C-like performance and memory use** is a measured target. Each corpus
    program and benchmark is compared with a hand-written C or Zig baseline under
    the margins set by gate M14. A margin violation blocks release for that
    workload.

13. **No data races in A7 code.** Data reaches another task by move, or stays
    read-only until the task is joined. Values visible to a task do not change
    while it runs, and that includes globals, which are immutable after program
    start. Gate M28 settles the rule and its diagnostics.

These guarantees amend `docs/SAFETY_CONTRACT.md` and the research contract in
`docs/lang-safety/README.md`. That amendment is gate M16. It rewrites the
fail-closed preamble, the risky-operations table, the reference surface and the
ownership surface, rather than patching individual checks.

### Contract examples

These examples illustrate the contract; they add no rules. Blocks labeled
"Current A7 syntax" are fragments of full probe programs that A7 accepted in
compile-only checks on 2026-09-16; their comments describe the proposed behavior.
Where a comment states what a program printed, that result comes from an audit
that built and ran it, and the comment says so. Library calls such as
`initial_state`, `accept` and `process` are placeholders.

Item 4, assignment copies:

```a7
// Proposed syntax.
a := List(i32){}
a.append(1)
b := a              // b is an independent value
b.append(2)         // a.len is still 1
// If a is not used again, the compiler moves instead of copying.
```

Item 5, bounded memory in a loop:

```a7
// Proposed syntax.
state := initial_state()
for {
    request := accept()                  // released at the end of each iteration
    state = next_state(state, request)   // the previous state is released here
}
```

Item 8, rejection classes 1 to 9. Each block shows rejected code and the
suggested rewrite. Classes 10 to 17, added in revision 3, are stated in item 8 and
have no example here yet.

```a7
// 1. Exclusivity. Current A7 syntax; accepted today.
// both :: fn(a: ref i32, b: ref i32) writes a, then b
both(x, x)          // rejected: two changes to x at once
// Rewrite: pass two distinct places, such as both(x, y).
```

```a7
// 2. View outliving its owner, or a structural change to the owner while the
// view is live. Proposed syntax.
head := xs[0..1]
xs.append(3)        // rejected: xs changes structurally while head is live
io.println("{}", head[0])
// Rewrite: keep a position (i: usize = 0) and read xs[i] after the append.
```

Class 2 also covers an overlapping write, which the current compiler accepts:

```a7
// Current A7. Accepted today, compile-checked on 2026-09-16 as a full program;
// the emitted Zig writes arr[0] after taking the view. Audit 2 built and ran the
// same shape and recorded that s[0] then reads 7 (CF-13).
// Proposed: rejected, because arr is written while s is live.
arr: [4]i32 = [1, 2, 3, 4]
s := arr[0..2]
arr[0] = 7
x := s[0]
// Rewrite: read arr[0] directly, or take the view after the write.
```

```a7
// 3. Returning or storing a ref. Current A7 syntax; accepted today.
id :: fn(a: ref i32) ref i32 {
    ret a           // rejected: returns a ref
}
// Rewrite: return the value, as in fn(a: ref i32) i32.
```

```a7
// 4. Stored function value capturing local data. Proposed syntax; the
// capturing function literal is a placeholder, since A7 has none.
limit: i32 = 10
filter := Filter{keep: fn(v: i32) bool { ret v < limit }}   // rejected
// Rewrite: store limit as a field and pass it: keep: fn(v: i32, limit: i32) bool.
```

```a7
// 5. Use after a move into a task. Proposed syntax; tasks.open and
// group.start are placeholders from audit 3.
group := tasks.open()
job := group.start(process, items)   // items moves into the task
n := items.len                       // rejected: items moved into the task
// Rewrite: read items.len before start, or return the data from the task.
```

```a7
// 6. Autodiff history leaving its training step. Proposed syntax; tensor
// operations are placeholders from audit 4.
loss := cross_entropy(forward(model, batch.x), batch.y)
total = total + loss     // rejected: loss carries history out of the step
// Rewrite: add loss.item() to a plain float, or use detach(loss).
```

```a7
// 7. Changing a saved value. Proposed syntax, from audit 4 P1.
x := tensor_from([1.0, -2.0, 3.0], f32)
y := x * x               // the tape saves x
x = x + 1.0              // rejected: the live tape depends on x
g := backward(sum(y), x)
// Rewrite: call backward before changing x.
```

```a7
// 8. Native retention without a declared owner. Proposed syntax; the native
// block is a placeholder from audit 3.
logger :: native "liblog" {
    set_buffer :: fn(buf: []u8)   // the library keeps buf after the call
}
logger.set_buffer(scratch)        // rejected: retention is not declared
// Rewrite: declare the retention in the descriptor and pass storage that outlives it.
```

```a7
// 9. Uninitialized read. Current A7 syntax; accepted today.
last: Pt
for v in pts[0..0] {
    last = v
}
io.println("{}", last.x)   // rejected: no path initialized last
// Rewrite: give last an initial value, such as last := Pt{x: 0}.
```

## 2. User-visible model

Examples are **proposed syntax** in current A7 style unless stated.

- **Values.** Numbers, structs, arrays, collections and strings behave as values.
- **Collections.** `List(T)`, `Map(K, V)` and an owning `string`.
- **Absence** uses optionals instead of `nil` references.
- **`ref` parameters** remain permission to change the caller's value. A `ref`
  cannot be stored, returned or copied into a local reference.
- **Positions** in a list are `usize` indices, valid while the element stays in
  place. Removing an element that shifts later elements invalidates held
  positions, so data that supports removal lives in a `Table(T)` (gate M1).
- **Typed ids** (`Id(T)`) name records in a collection that supports removal. An id
  carries a generation, and lookup returns an optional, so a stale id never reads
  another record. Ids are linked to their collection's type.
- **Resources** such as files, sockets, native handles and tasks are move-only
  values. They are the named exception to copying.
- **Bindings copy, places change in place.** `row := grid[0]; row.append(5)`
  changes the copy only; `grid[0].append(5)` changes `grid`.

```a7
// Proposed syntax
Node :: struct {
    value: i32
    parent: ?Id(Node)
}

Tree :: struct {
    nodes: Table(Node)
}

add_child :: fn(tree: ref Tree, parent: ?Id(Node), value: i32) Id(Node) {
    ret tree.nodes.insert(Node{value: value, parent: parent})
}

main :: fn() {
    tree := Tree{nodes: Table(Node){}}
    root := add_child(tree, none, 1)
    child := add_child(tree, root, 2)
    snapshot := tree
    tree.nodes.remove(child)
    // snapshot still contains child; tree does not
}   // both trees released here, iteratively
```

## 3. Breaking changes

Each row needs before and after examples and user approval.

| Current | Proposed | Evidence or impact |
| --- | --- | --- |
| `new T` returns a nullable reference; failure returns `nil` | Values only; allocation failure follows gate M2 | `zig.py` lowers `create(T) catch null`; SPEC documents nil checks |
| `del`, `defer del` | Removed from ordinary code (M3) | 12 compiler modules, about 364 tests, 13+ examples |
| `ref T` locals, returns and struct fields | Removed; values, indices or ids instead (M4) | `ref` returns and stored locals compile today. Self-referential `ref` fields compile; assigning to them fails |
| `t := a` where `a: ref T` copies the reference | Copies the value (M31) | Current binding type is `ref T` |
| Aliased `ref` arguments such as `both(x, x)` accepted | Rejected as exclusivity conflict | Compiles today in A7 and Zig |
| `nil` for references and function values | Optionals | SPEC `fn_ptr: ref fn() void = nil`; parser tests |
| Stored function values | Capture-free function values stay; capturing values rejected (M6) | `examples/022` and `037` store function values |
| `string` is a non-owning byte slice | Owning value; slices are temporary views | Struct copies holding strings become deep copies |
| Slices returned or stored in fields | Temporary views only (M13) | Returning a slice of a mutable local dangles today |
| `for v in xs { v.x = 9 }` accepted by A7, rejected by Zig | Loop bindings are immutable copies unless a separately approved form is added (M30) | Compile-only probe |
| Reading a variable no path assigned | Rejected (M34) | Accepted today after a zero-iteration loop |
| Writing to the owner while a slice of it is live | Views are read-only. A structural change or an overlapping write while a view is live is rejected (M13, rejection class 2) | Today `s := arr[0..2]; arr[0] = 7` runs and `s[0]` then prints 7 (audit 2 G-07, CF-13) |
| `for v in arr` over a fixed array, where the body writes to `arr` | If gate M51 makes the loop binding a read view, those programs are rejected (M30) | Today the body works on a snapshot and is accepted (audit 2 G-07b, probes q08 and q24) |
| Slice `.ptr`, `string` as pointer plus length, planned `mem_*`, `T` to `ref T` conversion, `cast(ref T, value)` | Removed from the public surface | SPEC sections 3.2, 11, appendix A |
| Keywords `new`, `del`, `nil` | Removed or reserved | Tokenizer and SPEC keyword lists |
| Resources copied like values | Move-only | New rule |
| Heap fixed arrays `new [N]T` rejected | Unchanged; growable data uses `List` | Heap-array diagnostic text and its test change |

### Before and after

"Before" blocks are current A7. Each was compile-checked on 2026-09-16 with
`uv run a7 <file> --format json`; none was executed. "Accepted" means A7 exited 0,
not that Zig builds the output. "After" blocks are proposed.
Aliased `ref` arguments and uninitialized reads are shown under
[contract examples](#contract-examples), classes 1 and 9.

**`new`, `nil` and `del`.**

```a7
// Before (current A7). Accepted.
b := new Box
if b == nil {
    ret
}
defer del b
b.value = 1
```

```a7
// After (proposed). A value; allocation failure follows gate M2.
b := Box{value: 1}   // released when its extent ends
```

**Stored and returned `ref`, and binding a `ref` to a local.**

```a7
// Before (current A7). Accepted.
id :: fn(a: ref i32) ref i32 {
    ret a
}
Holder :: struct {
    p: ref i32
}
```

```a7
// Before (current A7). Rejected: "Return type mismatch: expected 'i32', got 'ref i32'".
f :: fn(a: ref i32) i32 {
    t := a        // t has type ref i32
    ret t
}
```

```a7
// After (proposed). M4 and M31.
f :: fn(a: ref i32) i32 {
    t := a        // t is an i32 copy
    ret t
}
Holder :: struct {
    item: Id(Item)   // or a usize position
}
```

**`nil` and stored function values.**

```a7
// Before (current A7). Accepted.
Handler :: fn()
Slot :: struct {
    h: Handler
}
fn_ptr: ref fn() = nil
```

```a7
// After (proposed). M6 keeps capture-free function values.
Slot :: struct {
    h: Handler
}
handler: ?Handler = none   // absence uses an optional
```

**Slices, `.ptr` and `string`.**

```a7
// Before (current A7). Accepted; the returned slice dangles (audit 1 q13).
get :: fn() []i32 {
    buf: [4]i32 = [1, 2, 3, 4]
    buf[0] = 5
    ret buf[0..2]
}
p := arr[0..4].ptr
```

```a7
// After (proposed). M13: return an owned value; .ptr is not public.
get :: fn() [2]i32 {
    buf: [4]i32 = [1, 2, 3, 4]
    buf[0] = 5
    ret [buf[0], buf[1]]
}
```

An owning `string` changes struct copies: copying a struct that holds a `string`
also copies its bytes.

**Loop bindings.**

```a7
// Before (current A7). A7 accepts; Zig rejects "cannot assign to constant" (audit 1 p20).
for v in pts {
    v.x = 9
}
```

```a7
// After (proposed). M30: change the element through the collection place.
for i, v in pts {
    pts[i].x = 9
}
```

**Resources.** There is no current resource type.

```a7
// After (proposed). files.open is a placeholder from audit 3.
f := files.open("data.txt")
g := f          // f moves into g; resources are not copied
g.close()       // explicit, fallible close; otherwise released at extent end
```

**Heap fixed arrays.**

```a7
// Before (current A7); unchanged after. Rejected: "new [N]T heap arrays are
// not implemented; use a stack array or slice an existing array".
buf := new [4]u8
```

```a7
// After (proposed). Growable data uses List.
buf := List(u8){}
```

## 4. Architecture

The layers form one stack.

| Layer | Purpose | Depends on |
| --- | --- | --- |
| 0. Typed IR | CFG with explicit `fall` edges, sequencing, storage identities, ownership-aware operations, effect summaries including globals | v1 track 4 |
| 1. Sound facts | Branch joins, loop invariants, call invalidation, identity-keyed facts | v1 track 5 |
| 2. Internal ownership | One owner per storage; moves, releases on CFG edges, exclusivity checks | 0, 1 |
| 3. Escape analysis | Bottom-up summaries over the call graph after monomorphization | 2 |
| 4. Extent inference | Innermost extent per allocation; copy out on escaping paths; iteration release floor | 3 |
| 5. Storage formation | Stack slots, arenas and typed pools; resources, alignment classes and large values handled explicitly | 4 |
| 6. Copy removal and reuse | Proven-unobservable copy removal, in-place update, never creating aliased native kernel inputs and outputs | 2, 4 |
| 7. Buffer planning | Static plans for static shapes; a deterministic runtime planner with a bounded cache for dynamic shapes | 4, 5 |
| 8. Layout | Structure-of-arrays chosen per type across the whole program; types reaching native code or `ref` element arguments excluded | 5 |

Rules and qualifications:

- **Call graph.** The recursion ban makes A7 call depth bounded if stored function
  values stay non-recursive (v1 gate G4). Stack bytes are qualified per target,
  with declared native budgets. Values above a per-target size threshold move off
  the native stack.
- **Whole program.** Placement assumes the full A7 program. Separately compiled
  native libraries enter only through descriptors. File-module imports must be
  complete before placement relies on them.
- **Generics.** Summaries and plans are computed after monomorphization and cached
  by shape class. No monomorphization step exists today; Zig's `comptime` performs
  it invisibly. Building one is a prerequisite of layers 3 to 8.
- **Soundness first.** Layers 2 to 8 place releases and remove copies on the
  strength of compiler facts. Today those facts are unsound: branch joins restore
  pre-branch state and calls invalidate nothing, so a proof can license a move
  where a copy is needed. Gate M29 makes a falsifiable soundness test a
  precondition for building any later layer.
- **Layout and slices.** A slice over a collection whose records are split into
  arrays cannot be a contiguous view. Such a slice materializes a copy or is
  rejected. Whole-program layout choice also assumes whole-program compilation,
  which separate compilation of A7 modules would break.
- **Determinism.** Analyses iterate in a stable order and key approvals by a
  versioned identity, not by object address.
- **`defer`.** User defers run in reverse order before automatic releases of the
  same scope. A defer body counts as a use on every exit edge. Defers capture at
  execution time. `ret`, `break` and recoverable failure inside a defer are
  rejected.
- **Backend plan.** New explicit operations for release, extent reset, reuse, id
  lookup, overlap check and checked size arithmetic. Code generation never infers
  them.
- **Lowering.** Stack locals, `ArenaAllocator`-style extents, pool slabs and
  explicit growth failure paths, isolated behind a lowering layer so Zig API
  changes stay local.
- **Checks are A7 code.** Every residual check is emitted as explicit code, not a
  Zig safety check that ReleaseFast removes.

## 5. Gates

Gates M25, M28, M29 and M37 to M48 come from the reviews. M49 and M51 come from
audit 2, findings G-13 and G-14 for M49 and G-05 with Q-C3 for M51. M50 comes from
the architecture review. All were added in revision 3.

### Model

| Gate | Question | Recommendation |
| --- | --- | --- |
| M1 | Shared structure | Lists with `usize` positions for stable data; `Table(T)` with typed ids where removal is needed. A `List` position is shift-sensitive: removal that moves later elements invalidates held positions, and generations cannot detect shifting, so removal-capable storage is `Table(T)` |
| M3 | `del` | Remove from ordinary code |
| M4 | Stored and returned `ref` | Remove; values, indices or ids |
| M5 | Stale ids | Generation-tagged `Id(T)`; lookup returns an optional; generation exhaustion retires the slot |
| M6 | Function values | Capture-free function values allowed anywhere; capturing values allowed only as non-escaping arguments |
| M8 | Visibility of compiler decisions | Optional memory report; warnings for costly copies in loops |
| M9 | Vocabulary | Plain terms in diagnostics; "extent" and "store" only in the report and compiler docs |
| M13 | Slices | Temporary views, read-only, not stored or returned. While a view is live, any structural change to the owner (growth, removal, clearing, insertion) and any overlapping write are rejected |
| M30 | Loop bindings | Immutable copies; changes go through the collection place. Whether the binding is a snapshot or a read view is gate M51 |
| M31 | Binding a `ref` parameter to a local | Copies the value |
| M32 | Returning views of data received by `ref` | Not in v1; return owned values or index ranges |
| M33 | Map and list lookup | Return an optional copy; in-place changes through place expressions |
| M34 | Uninitialized reads | Reject; no implicit zero initialization |
| M35 | Large values | Moved off the native stack by a deterministic per-target threshold, shown in the report |

### Failure and runtime checks

| Gate | Question | Recommendation |
| --- | --- | --- |
| M2 | Out-of-memory | Decided by the owning extent. Task, training-step and session extents are recoverable: failure ends that extent, returns its storage, then reports an error. Other allocations stop the program with a diagnostic. `try_append` offers explicit recovery with the original value unchanged |
| M14 | Performance margins against C and Zig | Fix per-workload margins for run time, peak memory and allocation count, and the action taken on a violation, before any baseline runs. Baselines are authored independently from the specification, with pinned toolchains |
| M16 | Safety contract amendment | Rewrite `SAFETY_CONTRACT.md` and the research contract in `docs/lang-safety/README.md` against the whole contract in section 1: the fail-closed preamble, the risky-operations table, the reference surface and the ownership surface, plus the residual checks in section 6 and the program stop on non-recoverable out-of-memory. Present it only after section 6 and the rejection list are final |

### Concurrency and resources

| Gate | Question | Recommendation |
| --- | --- | --- |
| M7 | Resources | Move-only; implicit release at extent end in reverse acquisition order; explicit fallible `close`; warning when a writable resource is never closed |
| M10 | Tasks | Structured; scope exit cancels then joins children; no detach in v1; values move in. What failure to spawn does with the values already moved in is undecided (audit 3 EC3-04) |
| M12 | Native boundaries | Descriptors declare borrowing, retention, returned storage, alignment, completion, callbacks and thread affinity |
| M26 | Cancellation points | Channel operations, joins and explicit checks only |
| M27 | Channel close | Explicit close or task-group end; no last-sender counting |
| M36 | Read-only sharing with child tasks | Allowed for parent values the parent does not change until children finish |

### AI

| Gate | Question | Recommendation |
| --- | --- | --- |
| M11 | Tensor extents | Inferred process, session, optimizer step, microbatch and call extents; never written in source |
| M17 | Tape lifetime | `backward(loss)` consumes the recorded computation; a second `backward` on the same loss is rejected |
| M18 | Changing a saved value | Reject statically; no runtime version counter in v1 |
| M19 | Tied parameters | A parameter table with ids where tying is needed |
| M20 | Dynamic shapes | Deterministic runtime planner; cache bounded by count and bytes; shrink on out-of-memory |
| M21 | Activation recomputation | Deferred unless the decoder does not fit the qualification host |
| M22 | Tensor capacity | Leading-axis capacity for caches; views cover rows present at creation |
| M23 | Autodiff history leaving its step | Reject with a rewrite to `item()` or `detach` |
| M24 | Checkpoint loading | Validate, then write in place for same shapes; build then swap otherwise; save through a temporary file and rename |

### Later

| Gate | Question | Recommendation |
| --- | --- | --- |
| M15 | Syntax simplification | After the memory model settles; each change with before and after examples |

### Added in revision 3

| Gate | Question | Recommendation |
| --- | --- | --- |
| M25 | Native declaration surface | Open it in Phase A with before and after examples. It has no syntax today, and gate M12, phase F and the AI acceptance workloads all depend on it |
| M28 | Data races and globals | Cross-task data moves or stays read-only until join; globals are immutable after program start; a conflicting write is an exclusivity rejection |
| M29 | Fact-engine soundness gate | No layer may place a release or remove a copy until branch joins, loop back edges and call effects pass an adversarial test suite, written to fail first |
| M37 | Resource closed on one branch | Per-edge release, with rejection when closed-ness cannot be proven. The alternative is a one-bit flag listed as residual work |
| M38 | Block and branch extents | Add them, so a large temporary inside an `if` is released at the closing brace as it would be in C |
| M39 | Index and key validity | Proof-or-reject for a plain index, and an optional-returning `get` for lookups. The alternative is a runtime check with a defined stop |
| M40 | Determinism enforcement | Versioned approval keys, ordered analysis iteration, and a test that compiles one program twice under different hash seeds and compares the emitted Zig |
| M41 | Size arithmetic scope | Every size that reaches an allocator, slice bound, capacity, tensor descriptor or native length is computed on a checked path, including sizes the user computes and the standard library's own growth arithmetic. Decide with v1 gate G3 |
| M42 | Id width and exhaustion | A 64-bit id of index and generation; exhaustion stops the program with a diagnostic and never reuses a live id; using an id with the wrong table of the same type is rejected or documented |
| M43 | Native supply chain | Pin kernel library versions and hashes as the Zig toolchain is pinned, record versions in artifacts, set thread configuration explicitly, and allow only vetted bindings in v1 |
| M44 | Planner bounds | Bucket shapes, key the cache by shape, dtype, device and alignment, cap planning work, cache count and bytes, and fall back to a checked allocation |
| M45 | Arena membership and destruction | Resources and native-retained buffers never sit in a bulk-reset extent; generated destruction never allocates; failure during release is defined |
| M46 | Checkpoint robustness | Data-only format with bounded parsing; a failure after the first write leaves the model hard-invalid; verify a checksum after loading; read rather than map the data phase |
| M47 | Stale bytes in reused storage | Native calls receive length-exact or explicitly zeroed buffers; reuse never exposes bytes beyond the current value. No zeroization on release in v1, recorded as a limitation |
| M48 | L19 metric | Define what "users do not care about memory" means, measured on an independently written corpus, before any memory gate is presented. Qwen proposes two tiers: a first tier of `string`, `List`, `Map`, optionals, structs, arrays and loops that must produce no memory-caused rejection and no memory vocabulary, and a second tier of `Table`, `Id`, tensors, tasks and native code where rejections are counted per gate |
| M49 | Storage-owning unions and defaults | A union that owns storage releases the storage of the variant it holds, and changing the variant releases the old one. Every storage-owning type has a defined empty default, so a declaration without an initializer is not an uninitialized read |
| M50 | Monomorphization strategy | Layers 3 to 8 need a monomorphization step that does not exist. Decide whether the Python compiler instantiates generics for analysis only, or emits instantiated Zig, and where the result is cached |
| M51 | Iteration semantics | Audit 2 asks for both readings to go to the user. Either `for v in xs` binds a snapshot, so a structural change to `xs` during the loop is defined, or it binds a read view, so structural change is rejected and the breaking-change row for fixed arrays applies. Under the read view, writing an element by position in `for i, v in xs` stays accepted; it does not change `v` for the current iteration |

## 6. Residual runtime work

| Work | When | Outcome on failure |
| --- | --- | --- |
| Allocator call to obtain or grow storage | Allocation, collection growth, extent chunk | Gate M2 |
| Bump or free-list operation | Allocation inside an extent or pool | None |
| Release work | Extent exit, reassignment, element removal, iterative destruction of deep values | Release never fails and never allocates (gate M45) |
| Compiler-inserted copy | A binding whose copy cannot be proven unobservable, and a value copied out on an escaping path | Gate M2, reported by gate M8 |
| Id lookup and generation maintenance | `Table` access by `Id(T)`; bumping a generation when a slot is reused | Optional result; exhaustion follows gate M42 |
| Buffer planning for dynamic shapes | A tensor operation whose shape signature is not already planned | Planner failure is an allocation failure under gate M2; bounds are gate M44 |
| Plan cache insert, evict and arena shrink | After planning, and on out-of-memory | None; bounded by count and bytes (gate M44) |
| Distinct-index or overlap check | `ref` arguments or native buffers not proven distinct | No check runs under the current recommendation, which rejects these at compile time. If a gate approves a check instead, it reports an error before the operation runs and never continues silently |
| Checked size arithmetic | Capacities, byte counts, tensor shapes, native dimension conversions, and user-computed sizes reaching any of them (gate M41) | Treated as allocation failure |
| Index or key validity | A dynamic index or key that cannot be proven valid, if gate M39 chooses a check rather than a rejection | Defined by gate M39 |
| Shape and dtype preflight | Tensor operations with runtime shapes | Error value before the operation runs |

## 7. Phases

| Phase | Work | Depends on | Exit evidence |
| --- | --- | --- | --- |
| A. Audit and corpus | Edge-case audit, falsifying corpus, C and Zig baselines, gate decisions | Ledger | Every corpus program has an independently derived expected result. The L19 metric (M48) is defined and measured on an independently written corpus. M14 margins and the action on a violation are fixed before any baseline runs, and baselines are authored independently. Both training steps are hand-traced. The native declaration gate (M25) is open |
| B. Foundations | Typed IR, sound facts, and repair of current memory defects listed in the audit | v1 tracks 4, 5 | The adversarial soundness suite passes, having failed first (M29). Known unsafe programs reject, including MS-7 stored-callback recursion and the `arr = [arr[1], arr[0]]` evaluation order. Guarded controls pass in native Debug and ReleaseFast |
| C1. New surface, additive | Owning `string`, `List`, `Map`, `Table`, `Id`, optionals and internal ownership, with nothing removed | B; v1 gate G5 and tracks 7a, 8a | Corpus 2, 3, 7, 14, 15 and 28 behave as expected; the L19 metric is measured again on the new surface |
| C1′. Interim lowering | During C1, collections use one allocator with compiler-inserted releases at extent exit, before extent inference exists | B | Leak and double-free detection clean on migrated examples |
| C2. Removal, subtractive | Remove `new`, `del`, `nil` and stored or returned `ref`, with migration diagnostics and ordered approval of each breaking change | C1, D, E | Margins met before removal; all examples, tests and docs migrated |
| D. Placement | Escape analysis, extent inference, storage formation, iteration release floor | C1 | Corpus 1, 4, 5, 6, 13, 25, 26 and 27 run with measured flat memory, and no file descriptor leaks |
| E. Reuse and planning | Copy removal, in-place update, static and runtime buffer planning | D | Allocation counts and peak memory within M14 margins |
| F. Tasks, tensors, native | Structured tasks, channels, tensor extents, tape rules, native descriptors | D; v1 gates G7, G8, and gates M25, M43; tracks 9, 10, 11 | Corpus 8–12, 16–23 and 29–31; skipped optimizer steps leave model values bit-identical; the task corpus is clean under a thread sanitizer; AI acceptance scenarios |
| G. Layout and report | Structure-of-arrays, memory report | E | Identical output with and without layout transformation; measured locality |

In the v1 plan, phases B, C1, C1′, D, E and C2 form track 6a, and phases F and G
form track 6b, which comes after tracks 9, 10 and 11. The split removes the cycle
in which F depended on tracks that depended on the memory model.

Each phase ends with a GLM memory-safety review and the full release gate. L12
routes cybersecurity reviews to GLM; applying it to every phase of this plan is a
proposal in this document, not something the ledger says.

### Falsifying corpus

Expected results below come from the plan and must be re-derived independently in
Phase A.

| # | Program | Expected | Phase |
| --- | --- | --- | --- |
| 1 | Request loop with per-request temporaries, a connection table and a capacity-limited cache | Accept; memory flat | D |
| 2 | Append while a slice of the list is live | Reject | C1 |
| 3 | Append while only a `usize` position is held | Accept | C1 |
| 4 | Tree with parent ids, node removal and iteration | Accept | D |
| 5 | Entity insert and removal, then lookup of an old id on the next tick | Accept; lookup returns none | D |
| 6 | Merge keeping a subset chosen at run time | Accept; survivors copied out | D |
| 7 | Return a new list; return a slice of a local list | Accept; reject | C1 |
| 8 | `y = x * x`, change `x`, then `backward(y)` | Reject | F |
| 9 | Weight update after `backward` | Accept; step memory reused | F |
| 10 | Worker storing received values in a registry; sending a typed id without its table | Accept; reject | F |
| 11 | Stored function value capturing local data | Reject | F |
| 12 | Native kernel output overlapping an input; kernel retaining a slice; read-only input overlap | Reject; reject without descriptor; accept | F |
| 13 | Global intern table | Accept as an explicit collection | D |
| 14 | `swap(a[i], a[j])` with unknown indices | Reject unless indices are proven distinct | C1 |
| 15 | Deep tree released at scope end | Accept; iterative release | C1 |
| 16 | Tied embeddings through a parameter table | Accept | F |
| 17 | Loss summed across steps with history | Reject with rewrite | F |
| 18 | Gradient accumulation across microbatches | Accept | F |
| 19 | KV cache growth during generation | Accept with capacity | F |
| 20 | Out-of-memory in a step, then retry with a smaller batch | Accept; retry succeeds | F |
| 21 | Checkpoint load peak memory | Within M24 bound | F |
| 22 | Variable sequence lengths | Accept; plan cache bounded | F |
| 23 | Task scope exit with a running child; channel close with queued values | Child cancelled and joined; queued values released | F |
| 24 | `m[k] = f(m[k])`, and a `defer` that touches the returned value | Accept; the old value is read before it is released | B |
| 25 | Evicting cache at capacity over many iterations | Accept; memory flat, because removal releases element storage | D |
| 26 | Large temporary built inside one branch, followed by a long call | Accept; released at the branch end once M38 is decided | D |
| 27 | Files opened into a per-iteration extent | Accept; every handle closed, no descriptor growth | D |
| 28 | `reserve` with a count whose multiplication wraps, and a slice bound computed with wrapping arithmetic | Reject or fail as an allocation error; never a short buffer | C1 |
| 29 | Two tasks writing one mutable global; a parent writing a value shared read-only with a running child | Reject both | F |
| 30 | Adversarial stream of distinct tensor shapes | Accept; planning time and cache size stay within their caps | F |
| 31 | Checkpoint load interrupted during the data phase | Model is bit-identical to before, or hard-invalid and rejected on use | F |

## 8. Evidence rules

- Follow the test-quality rule in `AGENTS.md`.
- Expected results are derived independently of the implementation.
- Memory claims need native Debug and ReleaseFast execution. Leak and double-free
  checks use Zig's debug allocator on benign programs. Programs expected to be
  rejected are compile-only and labeled so.
- Loop flatness is measured by peak memory at N and 10N iterations.
- Baselines are hand-written C or Zig; toolchains and measurement tools are pinned.
- Hand traces and compile-only results are labeled as such.
- Security tests accompany the corpus: the soundness suite for M29, leak and
  double-free detection with Zig's debug allocator, address sanitizer builds for
  use-after-free, a thread sanitizer build of the task corpus, a fuzz corpus of
  malformed checkpoints, and a determinism test that compiles one program twice
  under different hash seeds and compares the emitted Zig.
- Every residual check is tested in Debug and ReleaseFast, and no residual check
  may compile to a Zig safety check that ReleaseFast removes.

## 9. Known gaps

Tracked for Phase A:

- Compile-time cost limits and the recursion-limit-100 invariant for new analyses,
  including what the compiler does when an analysis exceeds its budget.
- Debugger and profiler views of placed values and structure-of-arrays records.
- Zig version dependence of allocator and I/O APIs.
- Deep equality and hashing of owning values, which `Map` needs before phase C1.
- A growable text type, since an owning `string` makes repeated concatenation
  quadratic.
- Thread safety of the allocator behind per-task and shared stores.
- Bounds for task groups, channel queues and task stacks, and what a stack
  overflow does.
- Separate compilation of A7 modules, which whole-program layout assumes away.
- Information left in reused storage, covered as a limitation by gate M47.

Gates now cover what were previously gaps: failure during automatic release
(M45), hostile or incorrect native descriptors (M25, M43).

## 10. Review status

Revision 3 applies audit 2 and eleven reviews. The reviews are indexed in
[research/memory/review](research/memory/review/README.md).

Open disagreements, recorded rather than settled:

| Question | Positions |
| --- | --- |
| G4 with M6 | Type-informed call-graph edges (Qwen, contract, consistency) against forbidding stored function values (architecture) |
| M2 recoverability | Recoverable by extent kind with a task-per-request idiom (concurrency) against recoverability by fallible function signature (Qwen, consistency) |
| M11 extents | Structural identification rules from audit 4 (AI) against simpler call, iteration, task and process extents (Kimi) |

Unanimous recommendations that this revision has not adopted:

- **M33 lookups.** Qwen, the performance review and the consistency review all
  recommend returning a temporary view, with a copy only where liveness demands
  one. No reviewer defends the optional copy the gate still recommends. The gate
  text is unchanged so the user decides rather than inherits it.

Also unsettled, and not yet a gate: Kimi's finding that the plan assumes L19
overrides L17's "we need new concepts". `Id(T)`, `Table(T)` and move-only
resources are new concepts a Python-style user must learn. The ledger records no
decision on that reading.

The reviews that examined the contract — Qwen, contract, AI, concurrency,
consistency and security — agree that gate M16 cannot be presented until section 6
and the rejection list are complete, which this revision does. Kimi asks for a
different precondition: that audit 2 and the security review be applied first,
which this revision also does. Qwen, Kimi, the performance review and the
consistency review add that the M14 margins and the L19 metric must be fixed
before any baseline runs.
