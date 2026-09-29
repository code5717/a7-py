> **Source:** Claude Code audit subagent 3, concurrency, failure, native boundaries, resources.  
> **Date:** 2026-09-15. Audit of docs/plan/memory.md revision 1.  
> **Status:** Advisory. Expected results are hand traces; probe results are compile-only unless stated. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

# Audit 3: concurrency, failure, native boundaries and resources

Date: 2026-09-15. Subject: `docs/plan/memory.md` (proposed memory plan).
Scope: edge cases in four categories: (1) concurrency, (2) failure,
(3) native boundaries, (4) resources. The security exploit audit belongs to GLM
(L12). Questions for GLM are in section 5.

Evidence classes:

- **Hand trace**: expected behavior derived by reading memory.md. No program
  was run.
- **Compile-only probe**: current A7 source compiled with
  `MISE_UV_VERSION=0.12.6 uv run a7 <file> --format json --output <file.zig>`
  at this tree. The emitted Zig was read. No binary was built or run. Probe
  sources are in `scratchpad/audit/probes-3/`.

Every A7 block labeled **proposed** uses syntax that A7 does not support and no
gate has approved. API names follow the unapproved illustrations in
`research/language-features-codex.md:1034-1056` (`tasks.open`, `group.start`,
`job.join`, `group.finish`, `channels.bounded`). `files.open`, `native` and
`kernels.*` are placeholders introduced for this audit.

## 0. Scales used in the table

**L19 impact** (would an ordinary user notice?):

| Code | Meaning |
| --- | --- |
| N | Not noticeable. Internal placement only |
| D | Diagnostic only. Compile-time rejection with a clear rewrite, rarely met |
| R | Memory-aware rewrite needed. Counts toward the plan's L19 metric |
| S | Silent surprise. Program compiles, but memory use, timing or effects differ from what a Python-style reader expects |
| A | Abort. Process stops at run time with a diagnostic |

**Coverage by memory.md**: **C** covered, **A** ambiguous, **X** memory.md
contradicts itself or a cited research requirement, **M** missing.

**Layers** refer to memory.md section 4 (0 typed IR through 8 layout). **Gates**
refer to M1-M13 and plan gates G5, G7 and G9.

## 1. Current-compiler facts relevant to these categories

All compile-only. None was executed.

| Probe | Source summary | Observed | Relevance |
| --- | --- | --- | --- |
| p01 | `b := new Box; if b == nil { ret }; defer del b` | Status ok. Emits `allocator.create(Box) catch null` and `defer if (b) \|p\| allocator.destroy(p)` | Allocation failure is **recoverable today** (nil). M2 makes ordinary failure abort. That is a breaking behavior change missing from the memory.md section 3 table |
| p02b | `x: i32 = 1; defer io.println("x = {}", x); x = 2`, plus a defer inside a C-style loop with `break` | Status ok. Lowers to Zig `defer { print(.., .{x}) }` after the assignment point; loop defer lowers inside the `while` body | Capture is at execution time: the Zig would print `x = 2` (inferred from emitted Zig, not run). Defers run per iteration, including on `break`. memory.md never states capture timing or the order of defers relative to automatic release |
| p03 | `Registry :: struct { h: Handler }`, `r.h()` | Status ok | Stored function values compile today. M6 would exclude them. That removal is missing from the section 3 breaking-change table |
| p04 | Mutable global `counter: i32 = 0` changed from a function | Status ok | Mutable globals exist. memory.md never mentions globals in exclusivity (contract 7) or tasks (M10) |
| p05 | `cos :: extern fn(x: f64) f64` | Exit 6, "Undefined type (Identifier 'extern')" | No native declaration surface exists. M12 has no current baseline to migrate from |
| p06 | Loop `for i in 0..3 { b := new Box ... defer del b ... }` | JSON status `ok`, but the `.zig` file ends after a top-level `var b = allocator.create(Box) catch null;` with no `main` | A silent declaration/output drop, already listed in `docs/plan/README.md:206` as track 1 "parser declaration drop" (not new). p02 used the same range loop and failed to parse, so the drop is not attributed to range syntax. Not a memory-plan issue, but any memory corpus run on this compiler must check that output is complete |
| p09 / p11 | `defer { io.println(..); del b }` followed by a use of `b`, versus the same block after the last use | p09 exit 6, "Use after move or delete ... 'b' was moved or deleted earlier" at the later use. p11 status ok | The safety pass treats a block-form deferred `del` as an immediate delete. The single-statement `defer del b` form (p01, p06b) does not. Record in notes H |
| p10 | `new [n]u8` | Exit 6, heap arrays not implemented | Matches the section 3 row |
| p12 | `defer del b; b.value = 7; ret b.value` | Status ok. Emits `defer ... destroy` then `return b.?.value` | Zig evaluates the return value before defers. This matches LF:549-552 step order |
| p13 | `drop_it :: fn(p: ref Box) { del p }`, then caller `b.value = 1` | Status ok. Emits `allocator.destroy(p)` in the callee; the caller's later write is accepted | Confirms MS-2/MS-5: deletion through a `ref` parameter, then use after free, is accepted |
| stdlib | `io.println` lowering | `print(..) catch @panic("a7 stdout write failed")` | Output failure aborts today. This matters for EC3-33 (failure inside `defer`) and EC3-57 (fallible release) |

Probes p07 and p08 failed on unrelated type-check errors ("Undefined type
(Identifier 'buf')", "Requires array or slice type: got 'ref [4]u8'"). They are
**not** evidence that the compiler rejects stored references or slice escape.

## 2. Edge-case table

### 2.1 Summary

| ID | Case | Layer / gate | L19 | Coverage |
| --- | --- | --- | --- | --- |
| EC3-01 | Task result built in task storage, used after join | 3, 4, 5 / M10 | N | A |
| EC3-02 | Task handle never joined (abandoned task) | 4 / M10, G7 | D | M |
| EC3-03 | Early `ret` out of a task group while children run | 4 / M10, G7 | S | M |
| EC3-04 | Task spawn fails (stack or bookkeeping allocation) | 5 / M2, M10 | A | X |
| EC3-05 | Task fails; values moved into it | 4, 5 / M10, G5 | S | M |
| EC3-06 | Cancellation in the middle of list growth | 2, 5 / M10, G7 | S | M |
| EC3-07 | Cancellation while a native kernel borrows task storage | 4 / M10, M12 | S | M |
| EC3-08 | Cancellation races a send commit | 2 / M10, G7 | N | M |
| EC3-09 | Channel dropped with queued owning payloads | 4, 5 / M10, G7 | S | M |
| EC3-10 | Channel dropped with queued resources | 4 / M7, M10 | S | M |
| EC3-11 | Send to a closed channel returns the payload | 2 / M10, G5 | R | M |
| EC3-12 | Sending a bare `usize` index without its collection | 2 / M1, M5, M10 | D | X |
| EC3-13 | Typed id sent on one channel, its collection on another | 2 / M5, M10 | R | M |
| EC3-14 | Read-only model weights shared by worker tasks | 4, 6 / M10 | S | X |
| EC3-15 | Parent changes data that child tasks read | 2 / M10, contract 7 | D | M |
| EC3-16 | Deadlock: join never returns, extent never ends | 4 / contract 5, G7 | S | X |
| EC3-17 | Long-running worker loop inside a task | 4 / M10 | S | A |
| EC3-18 | Payload built in the sender's task store outlives the sender | 3, 5 / M10 | N | M |
| EC3-19 | Spawning a task per loop iteration | 3, 4 / M10 | S | A |
| EC3-20 | Several senders; close when the last sender ends | 5 / contract 1, M10 | N | X |
| EC3-21 | Task stack sizing from the recursion ban | 4, 5 / M10, G9 | A | X |
| EC3-22 | Mutable global touched by two tasks | 2 / contract 7, M10 | D | M |
| EC3-23 | Full-duplex socket split across reader and writer tasks | 2 / M7, M10 | R | M |
| EC3-24 | Large fixed-array value exhausts the stack | 5 / M2 | A | M |
| EC3-25 | `List.append` fails; is the old list usable? | 5, 6 / M2 | A | X |
| EC3-26 | String concatenation in a loop runs out of memory | 5, 6 / M2 | A | C |
| EC3-27 | Out-of-memory in a copy the compiler inserted | 6 / M2, M8 | A | M |
| EC3-28 | Pool slab growth fails during entity spawn | 5 / M2, M5 | A | A |
| EC3-29 | Recoverable tensor call and aborting list in one step | 5 / M2, M11 | S | X |
| EC3-30 | Argument marshalling allocation for a recoverable call | 5, 6 / M2, M12 | S | M |
| EC3-31 | Recoverable failure after partial parameter update | 4 / M2, M11, G8 | S | M |
| EC3-32 | Out-of-memory inside a task | 5 / M2, M10 | A | X |
| EC3-33 | Failure inside `defer` | 4 / M2, M7 | A | M |
| EC3-34 | Destruction worklist needs memory during out-of-memory | 5 / contract 8 | N | M |
| EC3-35 | Error value for a recoverable failure needs storage | 5 / M2, G5 | N | M |
| EC3-36 | Capacity arithmetic overflows under wrapping | 5 / M2, G3 | A | M |
| EC3-37 | Out-of-memory caused only by extent over-retention | 4 / contract 5, M8 | S | X |
| EC3-38 | Share-until-changed copy fails at first mutation | 6 / M2 | A | M |
| EC3-39 | Placement differs by build profile | 4, 5 / M2, G9 | S | M |
| EC3-40 | Native library's own allocation fails or terminates | boundary / M2, M12 | A | M |
| EC3-41 | Arena chunk request for an iteration extent fails midway | 5 / M2 | A | A |
| EC3-42 | Native call retains a borrowed buffer, undeclared | boundary / M12, contract 2 | S | X |
| EC3-43 | Declared retained buffer released before native unregister | 4 / M7, M12 | S | M |
| EC3-44 | Native code returns storage it allocated | 5, 8 / M12 | R | M |
| EC3-45 | Native code returns a pointer to its own static storage | 2 / M12, M13 | N | M |
| EC3-46 | Alignment required by a kernel versus bump allocation | 5, 7 / M12 | N | M |
| EC3-47 | SoA layout for a type also passed to native code | 8 / M12 | S | A |
| EC3-48 | `ref` to one element of an SoA collection | 2, 8 / M4 | N | M |
| EC3-49 | Runtime-dependent buffer overlap passed to a kernel | 2 / M12, contract 4 | A | A |
| EC3-50 | Native callback re-enters A7 and grows a borrowed list | 2, 3 / M6, M12 | D | M |
| EC3-51 | Native code keeps a callback after the call returns | 3 / M6, M12, G4 | D | M |
| EC3-52 | Native worker threads still use a buffer after return | boundary / M12 | S | M |
| EC3-53 | Thread-affine native handle moved to another task | 2 / M10, M12 | D | M |
| EC3-54 | Owning `string` passed where C expects a NUL terminator | 5 / M12, M2 | N | M |
| EC3-55 | `usize` length passed as a 32-bit native integer | boundary / M12, G3 | A | M |
| EC3-56 | File flush fails during automatic release | 4 / M7 | S | X |
| EC3-57 | Release order of dependent resources | 4 / M7, contract 5 | S | A |
| EC3-58 | Explicit `close`, then automatic release | 2 / M7 | N | A |
| EC3-59 | Resource closed on one branch only | 1, 2 / M7, contract 4 | N | M |
| EC3-60 | Resources inside a `List` | 4, 5 / M7 | S | M |
| EC3-61 | Resource-bearing values in a bulk-reset arena | 5 / M7, contract 5 | N | M |
| EC3-62 | `b := a` on a file handle | 2 / section 2, M7 | R | X |
| EC3-63 | Adding a resource field changes a struct from copyable to move-only | 2 / section 2, M7 | R | M |
| EC3-64 | Resource in a global; process abort | 4 / M2, M7 | S | M |
| EC3-65 | `defer file.close()` plus automatic release | 2, 4 / M7 | N | A |
| EC3-66 | Blocking release: child process at extent end | 4 / M7, G7 | S | M |
| EC3-67 | Slice of a memory-mapped file outlives the mapping | 2 / M7, M13 | D | A |
| EC3-68 | Resource moved into a task that is cancelled | 4 / M7, M10 | S | M |

### 2.2 Concurrency

#### EC3-01. Task result built in task storage, used after join

```a7
// Proposed
build :: fn(n: usize) List(i32) {
    out := List(i32){}
    for i: usize = 0; i < n; i += 1 { out.append(1) }
    ret out
}
main :: fn() {
    group := tasks.open()
    job := group.start(build, 1000)
    result := job.join()
    group.finish()
    total := result.value.len   // used after the task ended
}
```

- Expected under memory.md: accept. M10 says "task storage ends at join", which
  literally releases `out` before `result` is read. Escape analysis (layer 3) must
  see that the task's return flows to the joining scope.
- Coverage: **A**. The rule does not say which storage ends at join.
- Proposed rule: *A task's return value is placed in the store of the scope that
  calls `join`. The task store holds only non-escaping task temporaries and is
  released when the task completes, not at join. Join transfers ownership of the
  result without copying.*

#### EC3-02. Task handle never joined

```a7
// Proposed
main :: fn() {
    group := tasks.open()
    items := List(i32){}
    job := group.start(process, items)
    // no job.join(), no group.finish()
}
```

- Expected: memory.md is silent. Contract 5 says every extent ends, but a detached
  task has no extent end. LF:992 requires "Task handles do not silently detach".
- Coverage: **M**.
- Proposed rule: *Tasks are structured. Every task belongs to a group, and every
  group belongs to a lexical scope. Leaving the scope implicitly finishes the
  group: it joins every child that is still running. An unobserved failed outcome
  is reported. There is no detach operation in v1.*

#### EC3-03. Early return while children run

```a7
// Proposed
serve :: fn(queue: ref Queue) {
    group := tasks.open()
    job := group.start(worker, queue.take())
    if queue.shutdown { ret }       // child still running
    job.join()
    group.finish()
}
```

- Expected: silent in memory.md. Any static release point for `group` at `ret` is
  unsound while the child runs.
- L19: **S**. `ret` becomes a blocking wait.
- Proposed rule: *An early exit from a group scope requests cooperative
  cancellation of running children, waits for them to finish, then runs `defer`
  bodies, then releases storage. Order: cancel request, join, defers, automatic
  release.*

#### EC3-04. Task spawn fails

```a7
// Proposed
main :: fn() {
    group := tasks.open()
    data := load_rows()
    job := group.start(train, data)   // task stack cannot be allocated
}
```

- Expected: M2 classifies ordinary allocation failure as abort. A task stack is
  neither an ordinary value nor a tensor call. CX:483 and CX:646 require "captures
  remain recoverable".
- Coverage: **X** (M2 against CX:646).
- Proposed rule: *Spawn failure is a recoverable outcome of `group.start` that
  returns the moved arguments to the caller unchanged. Moves into a task commit
  only after the task exists.* If M2 stays type-based, state explicitly that spawn
  failure aborts and drop CX:646.

#### EC3-05. Task fails; values moved into it

```a7
// Proposed
parse_all :: fn(rows: List(string)) List(Record) { /* may fail */ }
main :: fn() {
    group := tasks.open()
    rows := read_rows()
    job := group.start(parse_all, rows)
    outcome := job.join()
    if !outcome.ok { io.println("failed") }   // rows is gone
}
```

- Expected: silent. `rows` moved in, so the caller cannot retry. LF:996 needs
  application failure and resource failure to stay distinguishable.
- Proposed rule: *Values moved into a failed task are released with the task
  store when the task ends. The join outcome distinguishes completion,
  application failure, cancellation and resource failure (G5). A caller that
  wants a retry keeps a copy; the M8 report shows that copy.*

#### EC3-06. Cancellation in the middle of list growth

```a7
// Proposed
fill :: fn(out: ref List(i32)) {
    for i: usize = 0; i < 1000000; i += 1 { out.append(7) }
}
```

- Expected: silent. If cancellation can take effect between reallocating the
  buffer and updating the length, the list is torn.
- Proposed rule: *Cancellation is observed only at defined cancellation points:
  blocking channel operations, join, explicit `tasks.check_cancelled()` and loop
  back-edges the compiler marks. No cancellation point exists inside a
  compiler-generated storage operation (growth, copy, release). Library
  collection operations are atomic with respect to cancellation.*

#### EC3-07. Cancellation while a native kernel borrows task storage

```a7
// Proposed
step :: fn(weights: ref Tensor, batch: Tensor) {
    kernels.matmul(weights, batch)     // long native call
}
main :: fn() {
    group := tasks.open()
    job := group.start(step_worker, load())
    job.cancel()
    job.join()
}
```

- Expected: silent in M10 and M12. CX:492 requires storage to stay live until the
  kernel returns or acknowledges.
- Proposed rule: *A borrow held by a native call extends the enclosing task store
  until the call returns. Cancellation never releases storage while a native call
  is in progress. A kernel that never returns keeps the task alive; this is
  documented as not guaranteed termination (CX:618).*

#### EC3-08. Cancellation races a send commit

```a7
// Proposed
producer :: fn(tx: Sender(List(i32))) {
    batch := make_batch()
    sent := tx.send(batch)       // task cancelled concurrently
    if !sent.ok { keep(sent.unsent) }
}
```

- Expected: silent. LF:1007: "Cancellation races after commit: must not return a
  second owned copy".
- Proposed rule: *`send` has one commit point. Before it, a cancelled send returns
  the payload in `unsent`. After it, the send reports success even if cancellation
  was requested, and the payload belongs to the channel. Layer 2 treats the
  payload as moved exactly on the success path.*

#### EC3-09. Channel dropped with queued owning payloads

```a7
// Proposed
main :: fn() {
    pair := channels.bounded(List(i32), 16)
    for i: usize = 0; i < 16; i += 1 { pair.sender.send(make_list(i)) }
}   // receiver never reads; 16 lists queued
```

- Expected: contract 5 releases them at extent end, but nothing says which extent
  owns queued payloads or in what order they are released.
- Proposed rule: *A channel's queue store belongs to the scope that created the
  channel. Queued payloads are released when that scope ends, in FIFO order,
  using iterative destruction. Waiting senders wake with `unsent`.*

#### EC3-10. Channel dropped with queued resources

```a7
// Proposed
main :: fn() {
    pair := channels.bounded(File, 4)
    pair.sender.send(files.open("a.log"))
}   // queued File never received
```

- Expected: M7 releases files "automatically at extent end". A queued file's
  flush can fail with nobody left to observe it.
- Proposed rule: *Same order as EC3-09. Release errors from queued resources go to
  the discarded-release-error report defined in EC3-56. The compiler warns when a
  channel element type owns a resource and the receiving side can be abandoned.*

#### EC3-11. Send to a closed channel

```a7
// Proposed
job := make_job()
sent := tx.send(job)
if !sent.ok {
    job2 := sent.unsent        // CX:398-404
}
```

- Expected: M10 says only "values move into tasks". A conditional move with
  ownership returned in an outcome is not described.
- L19: **R**. Users must handle `unsent` or lose the value.
- Proposed rule: *`send` consumes its argument. Its outcome owns the payload on
  failure. Dropping an unhandled failure outcome releases the payload and reports
  an unhandled failure. The unsent payload keeps the original's storage.*

#### EC3-12. Sending a bare `usize` index without its collection

```a7
// Proposed
main :: fn() {
    table := List(Node){}
    idx := add_node(table, 3)
    group := tasks.open()
    job := group.start(use_index, idx)   // corpus 10: "reject"
}
```

- Expected: corpus row 10 expects rejection. A bare `usize` is a number; nothing
  ties it to `table`. Section 2 says "indices or ids" without choosing.
- Coverage: **X**. The corpus expectation cannot be met for `usize`.
- Proposed rule: *Bare `usize` values cross tasks freely and carry no collection
  identity. Only typed ids (M5 generation-tagged ids) carry a store brand. Corpus
  row 10 is restated as: sending a typed `Id(Node)` whose store does not move with
  it is rejected; sending a bare `usize` is accepted and any lookup in another
  collection is an ordinary bounds-checked lookup.*

#### EC3-13. Typed id on one channel, its collection on another

```a7
// Proposed
ids_tx.send(entity_id)          // Id(Entity)
world_tx.send(world)            // Store(Entity), sent separately
```

- Expected: silent. The compiler cannot statically pair two independent channel
  deliveries.
- L19: **R**.
- Proposed rule: *A typed id may cross a task boundary only inside the same moved
  value as its store, or into a task that already owns that store by static
  scope. Otherwise reject with the rewrite "send the world and the id together, or
  send a plain index".*

#### EC3-14. Read-only weights shared by workers

```a7
// Proposed
main :: fn() {
    weights := load_weights()          // 2 GB
    group := tasks.open()
    for w: usize = 0; w < 8; w += 1 {
        group.start(infer, weights, w) // M10: no sharing without a move
    }
    group.finish()
}
```

- Expected: M10 forbids sharing without a move. The only accepted forms are eight
  copies (16 GB, silent) or rejection. Section 2 "shares storage until changed"
  suggests sharing is free; across tasks it is not.
- Coverage: **X** between section 2 (share until changed) and M10.
- Proposed rule: *Structured scopes permit read-only access from child tasks to
  values owned by an enclosing scope, because the parent's extent outlives every
  child (Rust scoped-thread model, no counts). The parent cannot change those
  values until the group finishes (EC3-15). This needs its own approval
  (CX:496, CX:688).*

#### EC3-15. Parent changes data children read

```a7
// Proposed
group := tasks.open()
group.start(infer, weights, 0)
weights.scale(0.5)                 // child may be reading
group.finish()
```

- Expected: contract 7 names this conflict class, but only for one thread.
- Proposed rule: *Starting a child that reads a parent value begins an exclusive
  read access that lasts until the group finishes. A write during that interval is
  an exclusivity conflict diagnostic naming the child start.*

#### EC3-16. Deadlock

```a7
// Proposed
a :: fn(rx: Receiver(i32), tx: Sender(i32)) { v := rx.receive(); tx.send(v) }
main :: fn() {
    p := channels.bounded(i32, 1)
    q := channels.bounded(i32, 1)
    group := tasks.open()
    group.start(a, p.receiver, q.sender)
    group.start(a, q.receiver, p.sender)
    group.finish()                 // never returns
}
```

- Expected: contract 5 says "every extent ends". Here the group extent never ends,
  so its storage is never released. LF:1012 and I-21 forbid claiming deadlock
  freedom.
- Coverage: **X**. Contract 5 is false for non-terminating programs.
- Proposed rule: *Restate contract 5: "All storage is returned when its extent
  ends. An extent ends when control leaves it. A7 does not guarantee that control
  leaves any extent (loops, blocking waits, deadlocks, native calls)."*

#### EC3-17. Long-running worker loop inside a task

```a7
// Proposed
worker :: fn(rx: Receiver(Request), registry: ref Map(u64, string)) {
    for {
        req := rx.receive()
        if !req.ok { ret }
        reply := format_reply(req.value)   // per-message temporary
        registry.put(req.value.id, reply)  // survives
    }
}
```

- Expected: accept (corpus 1 and 10). Per-message temporaries must reset per
  iteration, but contract 5 makes iteration-level release only an optimization.
  A task whose extent is the process could then retain every temporary.
- Coverage: **A**.
- Proposed rule: see EC3-37. *Non-escaping temporaries created in a loop body are
  released by the end of that iteration. This is part of the contract, not an
  optimization.*

#### EC3-18. Payload outlives the sender's task store

```a7
// Proposed
producer :: fn(tx: Sender(List(i32))) {
    batch := List(i32){}
    batch.append(1)
    tx.send(batch)
}   // producer task ends; its store is released
```

- Expected: silent. CX:488: "A receiver must not retain an allocation whose
  allocator state dies with the sender."
- Proposed rule: *A value that escapes into a channel is allocated in the
  channel's store (escape analysis sees `send`). When the allocation site is shared
  with non-escaping paths, the move into the channel copies into the channel store
  and the M8 report lists the copy. Contract 3 "move" therefore means an ownership
  move, not always a storage move.*

#### EC3-19. Spawning a task per iteration

```a7
// Proposed
group := tasks.open()
for i: usize = 0; i < files_list.len; i += 1 {
    chunk := read_chunk(files_list, i)   // iteration extent
    group.start(process, chunk)          // escapes into the group
}
group.finish()
```

- Expected: `chunk` is created in the iteration but lives until its task ends. The
  plan's extent list (call, iteration, task, step, process) has no "group" extent.
- L19: **S**. Memory grows with the number of started tasks.
- Proposed rule: *Values moved into a child task are placed in that task's store,
  which is released when the child completes. Add "task group" to the extent list.
  The standard library offers a bounded group so memory is bounded by concurrency,
  not iteration count.*

#### EC3-20. Several senders; close on last sender

```a7
// Proposed
pair := channels.bounded(i32, 8)
tx2 := pair.sender.duplicate()
group.start(produce, pair.sender)
group.start(produce, tx2)
drain(pair.receiver)   // ends when both senders end (LF:1010)
```

- Expected: "close when the last sender ends" requires counting live senders at
  run time. Contract 1 forbids reference counts.
- Coverage: **X**.
- Proposed rule: *Channel end-of-stream happens at an explicit `close` or when the
  group scope that owns the sender endpoints finishes. No runtime sender count. If
  a runtime counter is accepted, contract 1 must say "no reference counts on
  program values; runtime infrastructure (channels, schedulers) may keep internal
  counters".*

#### EC3-21. Task stack sizing

```a7
// Proposed
worker :: fn(n: usize) {
    buf: [65536]u8 = [65536]u8{}
    kernels.sort_bytes(buf)      // native frames unknown
}
```

- Expected: section 4 says "stack depth is computable" from the recursion ban.
  LF:64 and LF:715 say exact stack sizing does not follow (backend spills, ABI
  frames, native calls, runtime helpers).
- Coverage: **X** between memory.md section 4 and LF:715.
- Proposed rule: *The recursion ban bounds A7 call depth. Task stack size is that
  bound times a target-qualified frame estimate, plus a declared native-frame
  budget from each binding descriptor, plus a margin. Large values above a size
  threshold are placed in the task store, not the stack. Stack overflow is a guarded
  abort (G9), not undefined behavior.*

#### EC3-22. Mutable global touched by two tasks

```a7
// Proposed
counter: u64 = 0
bump :: fn() { counter = counter + 1 }
main :: fn() {
    group := tasks.open()
    group.start(bump)
    group.start(bump)
    group.finish()
}
```

- Expected: p04 shows mutable globals compile today. memory.md never mentions
  globals. CX:450 says globals defeat syntactic exclusivity.
- Proposed rule: *Effect summaries (layer 0) record global reads and writes. A
  task function whose summary writes a global, or reads a global another started
  task writes, is rejected as an exclusivity conflict. Globals shared across tasks
  are immutable after program start.*

#### EC3-23. Full-duplex socket across two tasks

```a7
// Proposed
conn := net.connect("127.0.0.1:9000")
group.start(read_loop, conn)
group.start(write_loop, conn)   // conn already moved
```

- Expected: M10 single-owner moves make this unexpressible.
- L19: **R**.
- Proposed rule: *Resources that support concurrent directions provide a
  consuming `split` returning separate read and write endpoints, each move-only.
  The socket is released when both endpoints are released, at the owning group's
  end, with no runtime count (EC3-20).*

### 2.3 Failure

M2 as written: "Ordinary values stop the program with a clear diagnostic; tensor
and bulk-data library calls return a recoverable error so training can back off."

#### EC3-24. Large fixed-array value exhausts the stack

```a7
// Proposed
main :: fn() {
    grid: [4096][4096]f32 = [4096][4096]f32{}   // 64 MB value
}
```

- Expected: memory.md "values" plus storage formation (layer 5) could pick a stack
  slot. Stack exhaustion is not out-of-memory and is not covered by M2.
- Proposed rule: *Values above a target-defined size are placed in a heap store of
  the same extent. Their allocation failure follows M2. Stack overflow from any
  remaining frame is a guarded abort.*

#### EC3-25. `append` fails; is the old list usable?

```a7
// Proposed
names := List(string){}
names.append("a")
names.append(huge_string)   // growth fails
io.println("{}", names.len)
```

- Expected: M2 aborts, so "old list usable" never matters for ordinary lists. The
  plan's own audit list (section 6: "failure during growth leaving the old value
  usable") and synthesis line 139 ("failed append leaving the original list
  usable") assume recovery.
- Coverage: **X**.
- Proposed rule: *Either (a) delete the "old value usable" requirement for
  ordinary collections because M2 aborts, or (b) add a recoverable `try_append`
  returning an outcome whose failure leaves length, contents and capacity
  unchanged. Recommend both: plain `append` aborts; `try_append` exists for
  capacity-sensitive code, and growth always allocates the new buffer before
  releasing the old one.*

#### EC3-26. String concatenation in a loop runs out of memory

```a7
// Proposed
text := ""
for i: usize = 0; i < n; i += 1 { text = text + line(i) }
```

- Expected: abort with a diagnostic (M2). Layer 6 should turn this into in-place
  growth.
- Coverage: **C** for the failure class. The diagnostic must name the source
  expression, not a Zig allocator frame.

#### EC3-27. Out-of-memory in a compiler-inserted copy

```a7
// Proposed
a := load_list()           // 1 GB
b := a
b.append(1)                // uniqueness not proven: full copy of a
use(a)
```

- Expected: section 4 "the compiler copies rather than inserting counts". The copy
  can fail and abort on a line with no visible allocation. This is the worst L19
  case: memory surprise plus abort.
- Coverage: **M**.
- Proposed rule: *Every compiler-inserted copy above a size threshold is listed in
  the M8 report with its source line. An abort diagnostic for a failed inserted
  copy names the copy, the value copied and the reason uniqueness was not proven.*

#### EC3-28. Pool slab growth fails during entity spawn

```a7
// Proposed
world := Store(Entity){}
for tick: usize = 0; tick < 100000; tick += 1 {
    id := world.insert(spawn_enemy(tick))   // new slab needed
}
```

- Expected: abort (M2). Games expect to refuse a spawn and continue.
- Coverage: **A**. Is `Store` a "bulk-data library call"?
- Proposed rule: *Name the recoverable set explicitly. Proposal: every standard
  collection offers a capacity-limited constructor and `try_insert`/`try_append`.
  "Bulk-data library calls" in M2 is replaced by an enumerated list.*

#### EC3-29. Recoverable tensor call and aborting list in one step

```a7
// Proposed
step :: fn(model: ref Model, batch: Batch) {
    order := List(usize){}               // ordinary: abort on failure
    for i: usize = 0; i < batch.len; i += 1 { order.append(i) }
    logits := model.forward(batch)       // tensor: recoverable
    if !logits.ok { ret }                // back off
}
```

- Expected: the same memory pressure aborts or recovers depending on which
  allocation hits it first. GLM R-8 requires out-of-memory during training to leave
  a clean error and run cleanups.
- Coverage: **X** between M2 and numerical-policy-glm R-8.
- Proposed rule: *Failure class follows the store, not the value type.
  Allocations in a step, session or task store are recoverable at that store's
  boundary: the step returns a resource-failure outcome, its store is released,
  and the caller decides to back off. Allocations in call, iteration and process
  stores outside any recoverable boundary abort.*

#### EC3-30. Argument marshalling allocation for a recoverable call

```a7
// Proposed
rows := List(f32){}
logits := tensors.from_list(rows, shape)   // compiler copies rows into a 64-byte-aligned buffer
```

- Expected: the copy happens before the recoverable library call begins. M2 does
  not say whether that copy aborts.
- Proposed rule: *Allocations performed to prepare arguments for a recoverable call
  (alignment copies, layout conversion, NUL termination) belong to that call's
  failure class.*

#### EC3-31. Recoverable failure after partial parameter update

```a7
// Proposed
update :: fn(params: ref List(Tensor), grads: List(Tensor)) {
    for i: usize = 0; i < params.len; i += 1 {
        r := optim.adam_step(params[i], grads[i])   // fails at i = 7
        if !r.ok { ret }
    }
}
```

- Expected: M2 says training "can back off", but parameters 0 to 6 are already
  changed. CX:655 asks for atomic step commit.
- Coverage: **M**.
- Proposed rule: *memory.md does not promise atomicity. G8 decides whether the
  optimizer stages updates in the step store and commits after all succeed. Until
  then the recoverable outcome documents partial state.*

#### EC3-32. Out-of-memory inside a task

```a7
// Proposed
group := tasks.open()
job := group.start(build_index, docs)   // ordinary List growth fails inside
outcome := job.join()
```

- Expected: M2 stops the whole process, including other tasks, with their files
  unflushed. LF:996 requires join to report resource failure distinctly.
- Coverage: **X** (M2 against LF:996).
- Proposed rule: *With the store-based rule of EC3-29, a task store is a
  recoverable boundary: the task ends with a resource-failure outcome, its store is
  released, and siblings continue. Allocations in the parent's or process store
  still abort.*

#### EC3-33. Failure inside `defer`

```a7
// Proposed
save :: fn(path: string, rows: List(Row)) {
    f := files.open(path)
    defer io.println("saved " + path + " rows " + fmt(rows.len))   // allocates
    write_rows(f, rows)
}
```

- Expected: silent in memory.md. Today `io.println` panics on write failure
  (probe stdlib row). If the concatenation fails, the process aborts in the middle
  of cleanup and `f` is never flushed.
- Coverage: **M**.
- Proposed rule: *(1) Order at scope exit: evaluate the return value, run defers
  LIFO, release resources in reverse acquisition order, then release storage. (2)
  An abort in a `defer` stops the process; remaining defers and releases do not
  run; the diagnostic says cleanup was interrupted. (3) A `defer` body cannot
  return a recoverable failure; it may not use `ret`, `break` or `continue`
  (LF:554). (4) Capture is at execution time, matching current lowering (p02b).*

#### EC3-34. Destruction worklist needs memory during out-of-memory

```a7
// Proposed
tree := build_deep_tree(10000000)
// scope ends while the process is near its memory limit
```

- Expected: contract 8 requires iterative destruction. An explicit stack of
  pending nodes needs allocation (CX:210).
- Proposed rule: *Generated destruction never allocates. Stores holding values
  without per-object release hooks are released in bulk (arena reset, slab free).
  Collections of resource-bearing values keep a flat release list maintained at
  insertion (EC3-61), so traversal needs no extra memory.*

#### EC3-35. Error value for a recoverable failure needs storage

```a7
// Proposed
r := model.forward(batch)
if !r.ok { io.println("{}", r.error.message) }
```

- Expected: silent. A formatted message allocated on the failure path can fail
  again.
- Proposed rule: *Resource-failure outcomes carry only fixed-size data (kind,
  requested bytes, source location id). Messages are formatted into static or
  pre-reserved storage.*

#### EC3-36. Capacity arithmetic wraps

```a7
// Proposed
buf := List(u64){}
buf.reserve(count * 8)       // L5: `*` wraps
```

- Expected: L5 wraps ordinary `*`. GLM R-1 forbids wrapped sizes. memory.md
  contract 4 does not mention size checks, and doubling growth inside `List` is
  compiler/runtime arithmetic.
- Proposed rule: *All size and capacity arithmetic generated by the compiler or
  used by the standard library is checked. Overflow is an allocation failure of the
  same class as the allocation (M2), never a smaller allocation. A user expression
  passed to `reserve` wraps before the call, so `reserve` also validates against a
  maximum element count.*

#### EC3-37. Out-of-memory caused only by over-retention

```a7
// Proposed
process_all :: fn(paths: List(string)) u64 {
    total: u64 = 0
    for i: usize = 0; i < paths.len; i += 1 {
        text := read_file(paths[i])   // 100 MB each
        total += count_words(text)
    }
    ret total
}
```

- Expected: contract 5 permits holding every `text` until the function returns
  ("precise release at last use is an optimization"). With 1000 files the program
  needs 100 GB and aborts, while a Python programmer expects 100 MB.
- Coverage: **X**. Layer 4 promises "the tightest extent" for each allocation,
  while contract 5 disclaims precise release as an optimization; corpus 1 expects
  "memory flat" and L19 expects no memory thinking.
- Proposed rule: *Contract 5 gains a floor: a value that does not escape a loop
  iteration is released by the end of that iteration. Release at last use within an
  iteration stays an optimization.*

#### EC3-38. Share-until-changed copy fails at first mutation

```a7
// Proposed
snapshot := world
world.entities.append(e)     // copy-on-change of a large shared world
```

- Expected: an innocent append performs a full copy that can abort (M2).
- Proposed rule: *A mutation that must copy shared storage copies before any
  visible change. If it fails under a recoverable store (EC3-29), both `snapshot`
  and `world` remain as before the statement. The M8 report lists copy-on-change
  sites whose size is not statically bounded.*

#### EC3-39. Placement differs by build profile

```a7
// Proposed
main :: fn() {
    big := List(u8){}
    big.reserve(3000000000)
    ret                       // Debug keeps the allocation; ReleaseFast elides it
}
```

- Expected: LF:906 asks whether elided allocation or allocation failure is
  observable. If Debug and ReleaseFast place differently, one build aborts.
- Proposed rule: *Placement, copy and release decisions (layers 2-7) are
  independent of the build profile. Zig-level elision after lowering may remove
  allocations; A7 does not guarantee that an unused allocation runs or fails.*

#### EC3-40. Native library allocation failure

```a7
// Proposed
y := kernels.gemm(a, b)      // OpenBLAS buffer pool exhausted: process terminates (NP:50)
```

- Expected: M2 promises recoverable tensor errors. OpenBLAS terminates the process
  internally.
- Proposed rule: *Recoverable failure covers A7-owned allocations only. Native
  internal allocation behavior is a descriptor fact. Bindings whose library can
  terminate on exhaustion are qualified with configured limits (thread count,
  build options) and documented as a boundary assumption.*

#### EC3-41. Arena chunk request fails midway through an iteration

```a7
// Proposed
for r: usize = 0; r < requests.len; r += 1 {
    header := parse_header(requests[r])
    body := decode_body(requests[r])   // new arena chunk needed here
    reply(header, body)
}
```

- Expected: abort (M2), with `header` already built. Nothing observable is lost
  because the process ends.
- Coverage: **A**. It is unclear whether a server loop counts as recoverable.
- Proposed rule: *Follow EC3-29. The standard library offers a per-request
  recoverable boundary (for example, a request handled as a task). A plain loop body
  is not a recoverable boundary.*

### 2.4 Native boundaries

No native declaration syntax exists (probe p05). `native` blocks below are
placeholders for compiler-owned binding descriptors (LF:1133-1148).

#### EC3-42. Undeclared retention of a borrowed buffer

```a7
// Proposed
logger :: native "liblog" {
    set_buffer :: fn(buf: []u8)     // library keeps the pointer; descriptor says "borrow"
}
main :: fn() {
    scratch: [256]u8 = [256]u8{}
    logger.set_buffer(scratch)
}   // later native writes go to released stack memory
```

- Expected: M12 rejects retention unless declared. It cannot detect a descriptor
  that states the wrong retention.
- Coverage: **X**. Contract 2 says "no dangling reference in A7 code". Native
  retention can create one.
- Proposed rule: *Contract 2 is restated as holding under the assumption that
  every binding descriptor is correct. Descriptor correctness is qualified by
  integration tests (CX:617). The memory report lists every native borrow.*

#### EC3-43. Declared retained buffer released before native unregister

```a7
// Proposed
audio :: native "libaudio" {
    start :: fn(buf: Retained([]f32)) Stream
    stop :: fn(s: Stream)
}
main :: fn() {
    ring := audio.retained_buffer(4096)
    stream := audio.start(ring)
}   // release order: ring, then stream?
```

- Expected: M7 releases both at extent end. Reverse declaration order releases
  `stream` first, which is correct here. Nothing forbids the compiler's "precise
  release" optimization from releasing `ring` earlier.
- Proposed rule: *A descriptor can declare that a handle depends on a retained
  buffer. The dependency makes the buffer live as long as the handle. Release runs
  the handle's native release function first.*

#### EC3-44. Native code returns storage it allocated

```a7
// Proposed
img :: native "libimg" {
    decode :: fn(bytes: []u8) Owned([]u8, release: img_free)
}
main :: fn() {
    pixels := img.decode(read_file("a.png"))
    rows := List([]u8){}
    rows.append(pixels)          // moved into an A7 collection
}
```

- Expected: M12 mentions only borrowed and retained buffers. LF:1150 says native
  pointers are not automatically owned A7 values. DLPack deleters need the producer
  release function.
- Coverage: **M**.
- Proposed rule: *Native-returned storage is an owned foreign handle with its
  producer's release function. It is never placed in an A7 arena or pool, never
  moved by layout transformation (layer 8), and is released exactly once. Moving it
  into a collection moves the handle. Converting it to an ordinary A7 value is an
  explicit copy.*

#### EC3-45. Pointer to native static storage

```a7
// Proposed
libc :: native "c" {
    getenv :: fn(name: string) Borrowed(?string, until: next_call)
}
home := libc.getenv("HOME")
libc.setenv("HOME", "/tmp")
io.println("{}", home)
```

- Expected: silent. M13 slices cannot be stored, but a borrowed native result is
  invalidated by an unrelated later native call.
- Proposed rule: *A borrowed native result is copied into an owned value at the call
  site unless it is used only before any later call into the same library. The
  compiler performs the copy; the descriptor states the validity interval.*

#### EC3-46. Alignment

```a7
// Proposed
batch := Tensor(f32){shape: [64, 3, 224, 224]}
kernels.conv2d(batch, weights)     // requires 64-byte aligned input (GLM R-3)
```

- Expected: layer 5 groups allocations into arenas and pools; memory.md says nothing
  about alignment.
- Proposed rule: *Every allocation carries an alignment class. Storage formation
  groups only allocations with compatible alignment, or aligns each bump. Native
  descriptors state required alignment. A misaligned buffer is copied into an
  aligned one (EC3-30), and the copy is reported.*

#### EC3-47. SoA layout versus native layout

```a7
// Proposed
Vec3 :: struct { x: f32  y: f32  z: f32 }
points := List(Vec3){}
physics.integrate(points)          // native expects contiguous x, y, z records
```

- Expected: layer 8 is "exempt at native boundaries", but it does not say whether
  the exemption applies per type, per value or per call.
- Coverage: **A**.
- Proposed rule: *Layout is decided per type, whole program. Any type that reaches a
  native boundary (directly or as an element) keeps native layout everywhere.
  The M8 report lists types excluded from SoA and why. No hidden per-call layout
  conversion.*

#### EC3-48. `ref` to one element of an SoA collection

```a7
// Proposed
nudge :: fn(p: ref Vec3) { p.x = p.x + 1.0 }
nudge(points[i])
```

- Expected: with SoA there is no record address to pass.
- Proposed rule: *A `ref` to an SoA element lowers to copy-in/copy-out of the
  element. This is unobservable because exclusivity (contract 7) already forbids
  other access to `points` during the call, including from callbacks and tasks.*

#### EC3-49. Runtime-dependent overlap passed to a kernel

```a7
// Proposed
blas.axpy(alpha, data[k..k + n], data[j..j + n])   // k and j known only at run time
```

- Expected: corpus 12 rejects overlap. With runtime bounds a static proof is
  impossible. Contract 4 lists only index validity tests as residual runtime work.
- Coverage: **A**.
- Proposed rule: *Add "overlap checks for runtime-bounded views passed to
  non-aliasing parameters" to contract 4. A failed check aborts before the call
  (or returns a recoverable failure for recoverable calls).*

#### EC3-50. Native callback re-enters A7 and grows a borrowed list

```a7
// Proposed
on_row :: fn(rows: ref List(Row), r: Row) { rows.append(r) }
parser :: native "libcsv" {
    parse :: fn(bytes: []u8, cb: Callback(on_row))
}
parser.parse(rows.bytes_view(), on_row)    // rows' buffer borrowed and grown
```

- Expected: M6 allows non-escaping callbacks. Neither M6 nor M12 addresses
  callbacks that touch storage the same native call borrowed. LF:713 says native
  re-entry also bypasses the call graph used by the recursion ban.
- Proposed rule: *A callback passed to native code is analyzed as called
  zero or more times during the call. Its effect summary must not conflict with any
  borrow passed to the same call. The descriptor declares whether re-entry happens.
  A callback that transitively calls the native function that invokes it is
  rejected by the recursion ban.*

#### EC3-51. Native code keeps a callback

```a7
// Proposed
timer :: native "libtimer" {
    every :: fn(ms: u32, cb: fn())   // stored by the library
}
```

- Expected: M6 excludes stored function values from v1. A native library storing a
  function pointer is a stored function value outside A7.
- Proposed rule: *A descriptor that retains a callback accepts only non-capturing
  functions. Retention returns an owned registration handle; releasing it
  unregisters the callback. Its effects enter the call graph as possible calls from
  every later native call into that library.*

#### EC3-52. Native worker threads use a buffer after return

```a7
// Proposed
kernels.async_fill(buf)    // returns while library threads still write (CX:569)
buf.append(1)              // growth moves the buffer
```

- Expected: M12 says "native calls borrow storage for the call". "For the call"
  assumes completion at return.
- Proposed rule: *The borrow interval is the descriptor's completion event, which
  defaults to return. v1 accepts only bindings whose completion is return (GLM
  R-10). Asynchronous bindings wait for a later approval.*

#### EC3-53. Thread-affine native handle moved to another task

```a7
// Proposed
prim := dnn.create_conv(desc)        // oneDNN: execute on the creating thread (NP:49)
group.start(run_conv, prim)
```

- Expected: M10 moves values into tasks freely.
- Proposed rule: *Descriptors mark handles as thread-affine. Thread-affine handles
  cannot be moved into tasks; the compiler rejects the move and suggests creating
  the handle inside the task.*

#### EC3-54. NUL-terminated string at a native boundary

```a7
// Proposed
f := libc.fopen(path, "r")   // owning `string` has no terminator
```

- Expected: a hidden allocation adds a terminator.
- L19: **N**, unless it fails.
- Proposed rule: *Boundary conversions allocate in the call extent, are released
  when the call returns, and follow EC3-30 for failure class.*

#### EC3-55. `usize` length passed as a 32-bit native integer

```a7
// Proposed
blas.sgemm(n, m, a, b)       // LP64 OpenBLAS: 32-bit integers (AI:344)
```

- Expected: numeric gate G3, but it affects buffer lengths.
- Proposed rule: *Descriptor integer widths are checked at conversion. A length that
  does not fit aborts before the call or returns a recoverable failure for
  recoverable calls.*

### 2.5 Resources

M7 as written: "Owned values released automatically at extent end, with explicit
`close` optional; `defer` kept for non-memory actions."

#### EC3-56. File flush fails during automatic release

```a7
// Proposed
write_report :: fn(path: string, rows: List(Row)) {
    f := files.create(path)
    for i: usize = 0; i < rows.len; i += 1 { f.write_line(fmt_row(rows[i])) }
}   // implicit release flushes; disk full
```

- Expected: M7 releases automatically, so the flush error has no observer.
  CX:197: "file flush or transaction commit cannot be hidden in an infallible
  destructor".
- Coverage: **X** (M7 "close optional" against CX:197).
- L19: **S**. Data loss with no error.
- Proposed rule: *Automatic release is infallible: it releases the OS handle and
  never reports success. A flush or commit error during automatic release is written
  to a process-wide discarded-error report (stderr diagnostic). Durable writes
  require explicit `close`, which returns an outcome. The compiler warns when a
  writable resource reaches automatic release without `close` on some path.*

#### EC3-57. Release order of dependent resources

```a7
// Proposed
conn := db.connect(url)
txn := conn.begin()
txn.insert(row)
// last use of conn was before last use of txn
```

- Expected: contract 5 allows release at last use as an optimization. Releasing
  `conn` first breaks `txn`.
- Coverage: **A**.
- Proposed rule: *Resources are never released early by optimization. They are
  released at extent end in reverse acquisition order, after defers. Early release
  applies only to storage without observable release effects.*

#### EC3-58. Explicit `close`, then automatic release

```a7
// Proposed
f := files.open("a.txt")
r := f.close()
// scope end
```

- Expected: M7 implies no double close, without stating the mechanism.
- Proposed rule: *`close` consumes the resource (layer 2 move). Automatic release is
  skipped on that path. Use after `close` is a use-after-move diagnostic.*

#### EC3-59. Resource closed on one branch

```a7
// Proposed
f := files.open("a.txt")
if quick { f.close() }
// scope end: release only if not closed
```

- Expected: needs a runtime drop flag or per-path release code. Contract 4 lists
  neither.
- Proposed rule: *Layer 1 joins produce per-path release. Where paths cannot be
  duplicated, a one-bit drop flag is emitted. Add "drop flags" to contract 4's
  residual runtime work and state that they are not reference counts.*

#### EC3-60. Resources inside a `List`

```a7
// Proposed
open_files := List(File){}
for i: usize = 0; i < paths.len; i += 1 { open_files.append(files.open(paths[i])) }
open_files.remove(3)       // releases one file now?
```

- Expected: silent. Removal, clear, overwrite (`open_files[2] = other`) and scope
  end each release files.
- Proposed rule: *Removing or overwriting a resource element releases it
  immediately at that statement. Clearing or ending the collection releases elements
  in reverse index order, iteratively. A failing release does not stop the others;
  errors go to the EC3-56 report. `remove` returning the element moves it out
  instead.*

#### EC3-61. Resource-bearing values in a bulk-reset arena

```a7
// Proposed
for r: usize = 0; r < n; r += 1 {
    tmp := files.open_temp()     // iteration extent
    scratch := List(u8){}
}   // iteration arena reset
```

- Expected: layer 5 groups allocations sharing an extent into arenas. An arena
  reset runs no per-object code, so `tmp` would leak.
- Proposed rule: *A type is trivially releasable only if it transitively owns no
  resource. Storage formation may bulk-reset stores holding only trivially
  releasable values. Other values are registered on the extent's release list and
  released before the reset.*

#### EC3-62. `b := a` on a file handle

```a7
// Proposed
a := files.open("log.txt")
b := a
a.write_line("x")
```

- Expected: section 2 says "`b := a` means `b` is an independent value". An
  independent file handle means `dup()` or reopening, which changes position and
  locking behavior.
- Coverage: **X** (section 2 against CX:193, CX:200).
- L19: **R**.
- Proposed rule: *Resource types are move-only. `b := a` moves; using `a` afterward
  is rejected with the rewrite "use `b`, or open the file twice". Section 2 lists
  resources as the exception to "everything is a value".*

#### EC3-63. Adding a resource field changes copy behavior

```a7
// Proposed
Config :: struct { name: string  log: File }   // `log` added in a later version
backup := config                                // previously a copy, now a move
io.println("{}", config.name)                   // now rejected
```

- Expected: silent in memory.md. CX:202 calls this a compatibility change.
- Proposed rule: *Move-only status propagates to containing types. The diagnostic
  names the field that made the type move-only. The memory report lists move-only
  types.*

#### EC3-64. Resource in a global; process abort

```a7
// Proposed
log_file: File = files.create("run.log")
main :: fn() {
    log_file.write_line("start")
    big := List(u8){}
    big.reserve(1 << 40)       // M2 abort
}
```

- Expected: M2 abort ends the process. Process-extent resources are never flushed.
- Proposed rule: *Abort does not run releases or defers (contract, stated
  explicitly). The abort handler flushes the standard output and error streams only.
  Recommend documenting "explicit `close` or flush before risky work" for durable
  data.*

#### EC3-65. `defer file.close()` plus automatic release

```a7
// Proposed
f := files.open("a.txt")
defer f.close()
f.write_line("x")
```

- Expected: M7 keeps `defer` for non-memory actions. Probe p02b shows defers
  capture at execution time. Probe p09 shows that today's safety pass treats a
  deferred deletion as immediate in block form.
- Coverage: **A**.
- Proposed rule: *A deferred consuming call reserves the resource: uses before
  scope exit are allowed; moves after the `defer` are rejected; automatic release is
  skipped because the deferred call consumes it. The outcome of a deferred `close`
  is discarded into the EC3-56 report unless handled inside the defer body.*

#### EC3-66. Blocking release: child process at extent end

```a7
// Proposed
for r: usize = 0; r < jobs.len; r += 1 {
    child := process.spawn(jobs[r])
}   // release: kill, wait, or detach?
```

- Expected: LF:1093 leaves this open. A release that waits blocks each iteration;
  a release that kills changes behavior.
- Proposed rule: *Each resource type documents its release action. Release actions
  must not block without bound. The process handle release requests termination and
  waits with a bounded timeout, then reports. Types whose release could block
  indefinitely require explicit `close` or `wait` and are rejected at implicit
  release.*

#### EC3-67. Slice of a memory-mapped file outlives the mapping

```a7
// Proposed
m := files.map("data.bin")
header := m.bytes()[0..16]
m.close()
io.println("{}", header[0])
```

- Expected: M13 forbids slices outliving owners. Closing is a consuming use while a
  view is live.
- Proposed rule: *`close` on a resource with live views is an exclusivity conflict
  (contract 7), the same class as growth during a live slice.*

#### EC3-68. Resource moved into a task that is cancelled

```a7
// Proposed
out := files.create("part.csv")
job := group.start(export_rows, out, rows)
job.cancel()
job.join()
```

- Expected: EC3-05 and EC3-07 release it with the task store. A partly written file
  remains.
- Proposed rule: *Resources moved into a cancelled task are released at the task's
  end, reverse acquisition order, with errors reported (EC3-56). Durability after
  cancellation is not promised.*

## 3. Plan gaps and contradictions, with fixes

| # | Location | Problem | Fix |
| --- | --- | --- | --- |
| G-1 | Contract 5 against M10 | "Every extent ends: ... task" assumes structured tasks. M10 never requires them. Detached tasks (EC3-02) and early exits (EC3-03) break the contract | Add to M10: tasks are structured; scope exit cancels then joins children; no detach in v1 |
| G-2 | Contract 5 | False for deadlocks, infinite loops and blocked native calls (EC3-16, EC3-07) | Restate as conditional on control leaving the extent; cite I-21 |
| G-3 | Layer 4 ("tightest extent") against contract 5; corpus 1 and L19 | The architecture promises the tightest extent, but the contract makes iteration-level release only an optimization, so the plan permits unbounded retention in loops (EC3-37, EC3-17) | Guarantee release of non-escaping iteration temporaries by iteration end |
| G-4 | Corpus 10 against section 2 | "Reject sending an index without its collection" is impossible for bare `usize` (EC3-12) | Bare `usize` crosses freely; typed ids carry a store brand and are rejected without their store |
| G-5 | M2 | Type-based failure class creates contradictory outcomes under the same memory pressure (EC3-29, EC3-32), aborts on invisible compiler copies (EC3-27) and conflicts with GLM R-8 and LF:996 | Failure class follows the store: step, session and task stores are recoverable boundaries; call, iteration and process stores outside them abort. Enumerate the recoverable library set |
| G-6 | Section 6 audit list and synthesis line 139 against M2 | "Failure during growth leaving the old value usable" is moot if ordinary growth aborts (EC3-25) | Keep abort for `append`; add `try_append` with the unchanged-on-failure guarantee |
| G-7 | Section 3 breaking-change table | Missing rows: allocation failure changes from nil-recoverable to abort (probe p01); stored function values removed (probe p03, M6); resources become move-only (EC3-62) | Add the three rows with before/after examples |
| G-8 | Section 2 against resources | "Everything is a value; `b := a` independent" is false for files, sockets and native handles (EC3-62, EC3-63) | Declare move-only resource types as the explicit exception |
| G-9 | Contract 1 against M10 | Multi-producer close on last sender needs a runtime count (EC3-20) | Close explicitly or at group end, or state that runtime infrastructure counters are not value reference counts |
| G-10 | Section 4 principle "stack depth is computable" against LF:64, LF:715 | Native frames, backend spills and runtime helpers are not bounded by the recursion ban (EC3-21) | Replace with "A7 call depth is bounded; stack size is target-qualified with declared native budgets" |
| G-11 | Contract 2 against M12 | "No dangling reference in A7 code" cannot hold if a descriptor is wrong (EC3-42) | Scope as an assumption on descriptor correctness, qualified by integration tests |
| G-12 | M12 | Missing native-returned storage, static-storage results, alignment, callback re-entry, completion after return and thread affinity (EC3-44 to EC3-53) | Extend M12 to require binding descriptors with those fields (LF:1135-1148) |
| G-13 | Layer 8 | "Exempt at native boundaries" does not say per type, per value or per call (EC3-47) | Per type, whole program; reported |
| G-14 | Contract 4 | Residual runtime work omits overlap checks (EC3-49), drop flags (EC3-59) and checked size arithmetic (EC3-36) | Add them |
| G-15 | Contract 5 "precise release" against M7 | Early release by optimization reorders observable resource releases (EC3-57, EC3-43) | Resources released only at extent end, reverse acquisition order |
| G-16 | M7 | "Explicit close optional" hides flush and commit failures (EC3-56) | Infallible implicit release with a discarded-error report; explicit fallible `close`; warning for writable resources |
| G-17 | `defer` (section 3 row, M7) | No capture timing, no order against automatic release, no rule for failure, `ret` or `break` inside a defer (EC3-33, EC3-65). Current safety pass mishandles block-form deferred deletion (probe p09) | Adopt the EC3-33 order and rules; capture at execution time |
| G-18 | Layer 5 | Bulk-reset arenas cannot hold resource-bearing values (EC3-61); arenas ignore alignment (EC3-46) | Trivially-releasable classification and alignment class are inputs to storage formation |
| G-19 | Extent list (contract 5, layer 4) | No "task group" or "channel" extent; payloads outlive sender stores (EC3-18, EC3-19) | Add group and channel extents; channel payloads placed in the channel store |
| G-20 | M10 against section 2 share-until-changed | Read-only sharing across tasks is forbidden, so large weights are copied silently per worker (EC3-14) | Structured read-only sharing from parent to children, with parent writes rejected until finish (separate approval) |
| G-21 | Contract 7 | Exclusivity never mentions globals or tasks (probe p04, EC3-22) | Effect summaries include global reads/writes; cross-task global writes rejected |
| G-22 | Phase A exit | "L19 metric" is not defined operationally | Count cases with L19 code R or A, plus S cases a user would report as a bug; this audit gives R = 6, A = 15, S = 25, D = 8, N = 14 of 68 |
| G-23 | Phase F exit | Corpus 10 and 12 are the only concurrency and native programs; cancellation, channel close, spawn failure and native-returned storage have no corpus entry | Add EC3-03, EC3-04, EC3-09, EC3-32, EC3-44 and EC3-56 to the falsifying corpus |

Counts in G-22 come from the section 2.1 L19 column of this audit only. Coverage
column totals: C = 1, A = 11, X = 13, M = 43.

## 4. New gate questions

For the user under the approval rule. Each needs before/after examples.

1. **M2 split:** failure class by value type (as written) or by store (step,
   session and task boundaries recoverable)? (EC3-29, EC3-32)
2. **M2 recoverable set:** which library operations are recoverable: tensors only,
   or also `try_append`, capacity-limited stores, file reads and task spawn?
   (EC3-04, EC3-25, EC3-28)
3. **Contract 5 floor:** is release of non-escaping iteration temporaries by
   iteration end a guarantee? (EC3-37)
4. **M10 structure:** are all tasks structured with implicit cancel-then-join at
   scope exit and no detach? (EC3-02, EC3-03)
5. **M10 cancellation:** which cancellation points exist, and is cancellation part
   of v1 at all? (EC3-06)
6. **M10 sharing:** may child tasks read parent-owned values without copies?
   (EC3-14)
7. **Channel close:** explicit close, group end or last-sender drop? Is an internal
   runtime counter acceptable under contract 1? (EC3-20)
8. **Ids across tasks:** are typed ids store-branded, and does a bare `usize` cross
   freely? (EC3-12, EC3-13)
9. **M7 fallible release:** is implicit release infallible with a discarded-error
   report, and must writable resources be explicitly closed? (EC3-56)
10. **Resources and values:** are resources move-only, making them the named
    exception to "everything is a value"? (EC3-62, EC3-63)
11. **`defer`:** execution-time capture; order defers, then resource release, then
    storage release; no `ret`, `break` or recoverable failure inside `defer`?
    (EC3-33, EC3-65)
12. **Abort behavior:** abort runs no defers or releases except standard stream
    flush? (EC3-64)
13. **M12 descriptors:** do native-returned storage, alignment, completion events,
    callback re-entry and thread affinity become required descriptor fields in v1?
    (EC3-44 to EC3-53)
14. **Layer 8:** is SoA decided per type over the whole program, with native-reached
    types excluded? (EC3-47)
15. **Stack promise (G9):** guarded abort on stack overflow, with a target-qualified
    bound instead of a computed exact size? (EC3-21, EC3-24)
16. **Profile independence:** must placement and copy decisions be identical across
    Debug and ReleaseFast? (EC3-39)

## 5. Questions for GLM (security review, L12)

Not investigated here.

1. Can a wrong binding descriptor (retention, completion, alignment) turn M12
   borrows into use after free or cross-task data races, and what qualification
   evidence would be enough? (EC3-42, EC3-52)
2. Does copy-in/copy-out lowering of `ref` to an SoA element stay sound when a
   native callback or signal handler observes the collection mid-call? (EC3-48,
   EC3-50)
3. Is store-branding of typed ids enough to stop a forged or stale id from reading
   another task's store, including after generation exhaustion? (EC3-12, EC3-13)
4. Can a task cancelled during a native kernel have its store released while
   library worker threads still write to it? (EC3-07, EC3-52)
5. Are queued channel payloads and discarded-release errors a resource-exhaustion
   vector (unbounded queues, error report growth)? (EC3-09, EC3-56)
6. Does recoverable failure at a task store boundary leave any shared state
   (channel queues, parent-borrowed data, native plans) inconsistent enough to be
   exploited by a later task? (EC3-32)
7. Can boundary conversions (NUL termination, alignment copies, 32-bit length
   conversion) produce a truncated or smaller buffer than the native side assumes?
   (EC3-54, EC3-55)
8. Does abort-without-release (EC3-64) leave temporary files, sockets or mapped
   regions in a state an attacker can use (predictable temp names, unflushed
   partial checkpoints)?
9. With mutable globals accepted today (probe p04), does any memory-plan lowering
   rely on exclusivity that globals or native re-entry can violate?
10. Are the current-compiler defects in probes p06 (output truncated with status ok),
    p09 (block-form deferred delete treated as immediate) and p13 (`del` through a
    `ref` parameter then use) already tracked in the MS findings, or new?
