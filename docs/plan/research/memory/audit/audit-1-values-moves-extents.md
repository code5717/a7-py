> **Source:** Claude Code audit subagent 1, values, moves, extents, escape, control flow, generics.  
> **Date:** 2026-09-15. Audit of docs/plan/memory.md revision 1.  
> **Status:** Advisory. Expected results are hand traces; probe results are compile-only unless stated. Body preserved verbatim. User decisions are in the [ledger](../../../decisions.md).

# Audit 1: values, moves, extents, escape, control flow, generics

Date: 2026-09-15. Plan under audit: `docs/plan/memory.md` (status: proposed).
Also read: `docs/plan/decisions.md` (L15-L19), `docs/plan/research/memory/synthesis.md`,
`docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md`, `docs/SPEC.md`
sections 3, 5, 7 and 8, `a7/safety.py`, `a7/backends/zig.py` and
`a7/passes/type_checker.py`.

Evidence labels:

- **Hand trace**: every "expected under memory.md" entry. Nothing here is measured
  or executed.
- **Code read**: facts read from source, with file and line.
- **Compile-only (a7)**: probe compiled with
  `MISE_UV_VERSION=0.12.6 uv run a7 <file> --format json`.
- **Zig-checked, not run**: the emitted Zig was built with Zig 0.16.0
  (`build-exe` or `-fno-emit-bin`). No probe binary was executed.

The probes are in `probes-1/`, next to this file (`p01`-`p24`, `q01`-`q15`).

In the table below, code sketches are **proposed syntax** unless marked current.
`;` stands for a line break, and `List`, `Map` and `.append` are the plan's proposed
collections. All indices are `usize`, and no sketch uses recursion, `&`, `*`,
`.adr` or `.val`. `for i in 0..n` abbreviates the current counted loop
(`for i := 0; i < n; i += 1` with `i: usize`); it proposes no new syntax.

Column key:

- **Layer**: memory.md §4, from 0 (typed IR) to 8 (layout).
- **L19**: whether an ordinary user would notice. "No" means invisible;
  "perf" means only memory or speed changes; "yes" means a diagnostic or an
  observable semantic surprise.
- **Plan**: covered, ambiguous, missing or contradictory.

## 1. Edge-case table

### 1.1 Values and copies

| ID | Proposed program | Expected under memory.md (hand trace) | Layer | L19 | Plan | Proposed rule where missing |
| --- | --- | --- | --- | --- | --- | --- |
| EC1-A01 | `a: [1000000]f64; b := a; b[0] = 1.0; print(a[0])` | Accept; prints the original value. The copy becomes a move if `a` is dead. | 5, 6 | yes: a native stack overflow if both stay on the stack | Missing: fixed arrays are "values", and §3 says `new [N]T` stays rejected, but no size limit for stack placement is given | Values over a target-defined size threshold go to the call-extent store, not the native stack. Stack depth is already computable from the acyclic call graph (§4). |
| EC1-A02 | `a := List(i32){}; a.append(1); b := a; b.append(2); print(a.len)` | Accept; prints 1. `b` is independent; sharing ends at `b.append`. | 6 | no | Covered in §2 ("shares storage until either side changes") | none |
| EC1-A03 | `b := a; if cond() { b.append(1) }; print(a.len)` | Accept; prints the original length. A copy is needed only on the path that writes. | 2, 6 | perf | Ambiguous: sharing without counts needs path-static knowledge | Copy lazily at the first write on each CFG path. Where the paths join, a path that did not copy still shares, so later writes need a rule (see EC1-A04). |
| EC1-A04 | `b := a; for i in 0..n { if odd(i) { a.append(i) } else { b.append(i) } }` | Accept. The side that writes first is data-dependent. Without counts, either copy eagerly at `b := a` or keep a one-bit "already copied" flag. | 6 | perf | **Contradiction**: §2 promises sharing until change, §4 forbids counts, and contract item 4 lists no per-binding uniqueness flag as allowed runtime work | Choose one: (a) data-dependent first writes copy eagerly at the binding, or (b) add "uniqueness flags" to contract item 4. Recommend (a), reported under M8. |
| EC1-A05 | `snap := world` inside `for step in 0..n { snap := world; update(world); diff(snap, world) }` | Accept. One copy per iteration, storage reused through the iteration extent. | 4, 6, 7 | perf: a silent O(size) copy each iteration | Ambiguous: M8 warns only about "costly unavoidable copies" and sets no threshold | M8 needs a rule: report per-iteration copies above a size threshold in the memory report, never as a warning by default. |
| EC1-A06 | `f :: fn(a: List(i32), b: ref List(i32)) { b.append(a.len) }; f(xs, xs)` | Value semantics say `a` is a snapshot, so accept and copy `xs` for `a`. Contract item 7 could instead reject this as "a value changed while something depends on it". | 2, 3 | yes if rejected | **Contradiction** between §2 (everything is a value) and contract item 7 | A by-value argument that aliases a `ref` argument is copied, not rejected. Only `ref`/`ref` overlap is an exclusivity conflict. |
| EC1-A07 | `t := s; s.items.append(x); print(t.name)` where `s: struct { name: string; items: List(i32) }` | Accept. Only `items` needs its own storage, and `name` can stay shared. | 6 | perf | Missing: the granularity of sharing (whole value or per field) | Uniqueness is tracked per storage identity: each field or element subtree that owns storage gets its own identity (layer 0). |
| EC1-A08 | `grid := List(List(i32)){}; ...; row := grid[0]; row.append(5); print(grid[0].len)` | Accept; `grid[0]` is unchanged. Python users expect aliasing here. | 2 | **yes**: Python's aliasing model is the opposite | Covered by "everything is a value", but not flagged as an L19 surprise | Document "bindings copy; place expressions mutate in place": `grid[0].append(5)` changes `grid`, and `row := grid[0]` does not alias. Diagnostics hint when a mutated copy of an element is never written back (lint, M8). |
| EC1-A09 | `xs = xs` and `s.items = s.items` | Accept as a no-op. The old value must not be released before the right-hand side is read. | 2 | no | Missing | Assignment evaluates the right-hand side into a temporary before releasing the old left-hand value, and self-assignment of the same storage identity is elided. |
| EC1-A10 | `grid.append(grid[0])` | Accept. The argument is materialized before growth, so it does not read a moved buffer. | 0, 2 | no | Partly: corpus 2 covers slices during growth, not element arguments | Arguments of a mutating call are evaluated to owned or copied values before the receiver is invalidated. |
| EC1-A11 | `make :: fn() Big { b := Big{...}; ret b }` | Accept; the result is placed in the caller's storage. | 3, 6 | no | Covered (return moves) | none |
| EC1-A12 | `f :: fn(a: ref List(i32)) usize { t := a; a.append(1); ret t.len }` | Under §2, `t` is an independent value (the old length). Currently, **`t` is typed `ref`** (q14). | 0, 2 | yes (breaking) | **Missing breaking-change row** | Reading a `ref` parameter in value position yields the referent value, and `ref` is never a local binding type. Add this row to §3. |
| EC1-A13 | `for v in pts { v.x = 9 }` | Under value semantics, the write would silently not affect `pts`. | 0, 2 | **yes** | Missing | For-in bindings are immutable, and the diagnostic suggests `for i, v in pts { pts[i].x = 9 }`. |
| EC1-A14 | `match shape { case s: total += s.items.len }` | Accept. The capture is an immutable copy, elided to a borrow. | 6 | no | Covered by SPEC §5.2 (capture is immutable) | none |
| EC1-A15 | `CONFIG := List(i32){}` at module level; `local := CONFIG; reload()` where `reload` mutates `CONFIG` | Accept; `local` keeps the old contents. Sharing must be broken by the call's effect summary. | 3, 6 | no | Ambiguous: effect summaries are listed in §4, but global effects are not named | Function summaries include "writes global G". A call that writes G ends sharing with any copy of G. |

### 1.2 Moves (all internal; no user move syntax)

| ID | Proposed program | Expected under memory.md (hand trace) | Layer | L19 | Plan | Proposed rule where missing |
| --- | --- | --- | --- | --- | --- | --- |
| EC1-B01 | `b := a; b.append(1)` with `a` dead afterward | Move, no copy. | 2, 6 | no | Covered | none |
| EC1-B02 | `if c { reg.append(a) } else { print(a.len) }`, then `a` dead | Move on the `then` edge; release at the end of `else`. No flag is needed if releases go on CFG edges. | 0, 2 | no | Ambiguous: contract item 3 requires static release points but does not say how joins are handled | Releases are inserted on CFG edges (critical-edge splitting), so no drop flags are needed. State this in layer 2. |
| EC1-B03 | `buf := List(u8){}; for i in 0..n { out.append(buf) }` | Copy on every iteration, because `buf` is live on the back edge. Moving only on the last iteration is unprovable in general. | 1, 2, 6 | perf | Covered implicitly | Report under M8 when the per-iteration copy is large. |
| EC1-B04 | `x := list[i]; list[i] = List(i32){}` | Semantically a copy. It can become a take if the element is overwritten with no use in between. | 6 | perf | Missing: moves out of collection elements appear only in the Phase A category list | A read followed by overwriting the same place with no intervening use is a move. Standard `remove(i)` and `swap_remove(i)` return owned values. |
| EC1-B05 | `name := person.name; print(person.age)` | Accept. `name` is a copy, or a partial move if `person.name` and whole-`person` uses are dead. | 2, 6 | no | Missing: partial moves | No user-visible partially-moved state. Partial moves are an optimization and are valid only when the whole aggregate is never copied or read as a whole again. |
| EC1-B06 | "Use after move" | Cannot occur as a user error, because copies turn into moves only when the source is dead. | 2 | no | **Contradiction**: Phase A lists "use after move" as an edge case, but §2 has no user-visible moves | Reword to "internal move invariant: no read of a moved storage identity"; it is a compiler self-check, not a diagnostic. |
| EC1-B07 | `match k { case 1: reg.append(a) case 2: other.append(a) else: {} }`, then `a` dead | Move in arms 1 and 2; release in `else`. | 0, 2 | no | Covered by "moves in match arms" (listed only) | Same edge rule as EC1-B02. |
| EC1-B08 | `match k { case 1: { reg.append(a); fall } case 2: { other.append(a) } else: {} }` | Arm 1 must copy, because `fall` makes arm 2 reachable. | 0, 2 | perf | Missing: the Phase A list says "`match` fall-through", but the IR description does not mention `fall` edges | Layer 0 models `fall` as an explicit CFG edge. Current codegen lowers `fall` to boolean flags (p24), which the IR must not copy. |
| EC1-B09 | `f :: fn(a: ref List(i32)) { reg.append(a) }` | Copy; the caller keeps its value. | 2, 3 | perf | Missing | A value behind `ref` is never moved out implicitly, because `ref` grants change permission, not ownership. |
| EC1-B10 | `pass :: fn(a: List(i32)) List(i32) { ret a }; y := pass(x)`, where `x` may be dead or live afterward | The callee summary says "returns param 0". If `x` is dead, move in and move out. If `x` is live, the callee borrowed it, so the return copies. | 3 | perf | Ambiguous: summaries are listed without their content | Per-parameter summary facts are {read, stored-into P, returned, stored-global}. The caller passes an owned value when "returned or stored" and the argument is dead; otherwise the callee copies at the escape. |
| EC1-B11 | `b := a; a = List(i32){}; a.append(1); print(b.len)` | Accept. Reassigning `a` creates a new storage identity. | 0, 2 | no | Covered by "stable storage identities" | none |
| EC1-B12 | `a := xs; { a := ys; sink(a) }; print(a.len)` | Accept. The shadowed `a` is a different identity. Currently: the name-keyed moved set gives a false positive (p17, C4). | 0, 2 | no | Covered by layer 0 | Key ownership by binding identity (already C4). |
| EC1-B13 | `parts := split(s); if parts.len == 0 { ret }; reg.append(parts)` | Release `parts` on the `ret` edge; move on the other path. | 2, 4 | no | Covered by edge releases (EC1-B02) | none |

### 1.3 Extents

| ID | Proposed program | Expected under memory.md (hand trace) | Layer | L19 | Plan | Proposed rule where missing |
| --- | --- | --- | --- | --- | --- | --- |
| EC1-C01 | `for line in lines { parts := split(line); if parts.len == 0 { ret false } }` | Accept. On `ret`, the iteration store is released, then the call store. | 4, 5 | no | Covered (early return) | State the release order: innermost extent first. |
| EC1-C02 | `for i in 0..n { tmp := build(i); if ok(tmp) { ret tmp } }` | `tmp` escapes on one path only. With one extent per allocation site, it lands in the caller's extent every iteration, so memory grows with n. The alternative is iteration-store placement plus a copy out at `ret`. | 3, 4, 5 | perf, possibly unbounded memory | **Contradiction**: "tightest extent" (layer 4) versus "no silent promotion" (synthesis 7) versus "memory flat" (corpus 1). Placement is per site, but escape here depends on the path. | Path-dependent escape keeps the allocation in the iteration extent and copies it out (deep) on the escape edge. The copy is reported under M8 and is not a "hidden copy", because the source's semantics is copy. |
| EC1-C03 | `found := List(i32){}; for x in xs { tmp := f(x); if good(tmp) { found = tmp; break } }` | Same as EC1-C02, with escape through assignment to an outer binding followed by `break`. | 3, 4 | perf | Same gap | Same rule. |
| EC1-C04 | `for x in xs { tmp := g(x); if skip(tmp) { continue }; out.append(tmp) }` | On `continue`, `tmp` is released by the iteration reset. On append, `tmp` "moves" into `out`, but `out`'s store is a different extent, so the move is physically a **deep copy** of `tmp`'s heap parts. | 4, 5, 6 | perf | **Missing**: the plan assumes moves are cheap, and a move across stores is a copy | State that a move between different stores copies the storage. Layer 6 may place `tmp` in `out`'s store speculatively, but only when every path escapes into `out`. |
| EC1-C05 | `@outer for i in 0..h { row := List(i32){}; for j in 0..w { c := cell(i, j); if stop(c) { break outer }; row.append(c) }; grid.append(row) }` | Accept. `break outer` releases the inner iteration store, then `row` and the outer iteration store. `grid` survives. | 0, 4, 5 | no | Covered (break, nested loops) | Labeled `break` and `continue` release every extent between the jump and its target, innermost first. Current Zig lowering already runs a per-iteration `defer` on `break :label` (p11 emission), but see finding F9. |
| EC1-C06 | `acc := List(i32){}; for i in 0..n { acc.append(i) }` | Accept. `acc` lives in the call extent. Growth must free the old buffer. | 5 | perf | **Ambiguous**: lowering names `ArenaAllocator`-style extents, and a bump arena never frees the old buffers of a growing list (about 2x waste, which never returns in long-running loops) | Growable collections use a free-list or general store inside their extent, never a pure bump arena. Arenas hold only values that never grow. |
| EC1-C07 | `state := init(); for step in 0..1000000000 { state = next(state) }` | Each iteration's new `state` is assigned to an outer binding, so its extent is the call. The old `state` is dead at reassignment, but contract item 5 allows holding it until the call ends: **unbounded growth** in a long-running loop. | 2, 4, 6 | **yes**: out of memory | **Contradiction**: contract item 5 ("may be held until that extent ends") permits this, and corpus 1 requires flat memory | Contract rule: the previous value of a binding reassigned inside a loop is released at the reassignment (or reused in place, layer 6), never at the end of the enclosing extent. More generally, nothing allocated per iteration may be retained past the iteration unless it is reachable from a live owner. |
| EC1-C08 | `last: Pt; for x in empty { last = x }; print(last.x)` | Uninitialized read. Currently accepted (q05, `var last: Pt = undefined`, Zig-checked). | 1 | yes | Missing: optionals, unions and initialization belong to another audit category, but zero-iteration loops belong to this one | Definite initialization over the CFG. A read that some path reaches without an assignment is rejected, with a hint to give an initial value or use an optional. |
| EC1-C09 | `for x in empty { tmp := big() }` | No store is created or reset. | 5 | no | Missing | The iteration store is created lazily on first allocation. Zero-iteration loops cost nothing. |
| EC1-C10 | `for { req := accept(); handle(req); log.append(req.id) }` (never ends) | Iteration temporaries reset each pass. `log` grows because of the user's data, not over-retention. | 4 | yes, by design | Ambiguous: the plan does not separate user-data growth from compiler over-retention | Guarantee: in a loop, compiler-chosen retention is bounded per iteration. Growth reachable from a live owner is the program's own behavior. The memory report lists owners that grow without removal inside non-terminating loops. |
| EC1-C11 | `while read_line(f).len > 0 { ... }` and `for i := 0; i < parts(s).len; i += 1 {}` | Temporaries in the condition and update belong to the iteration extent. | 0, 4 | no | Missing | Condition and update expressions are sequenced inside the iteration extent (layer 0). |
| EC1-C12 | `if big_case { tmp := build_huge() ; use(tmp) }; long_compute()` | Contract item 5 allows `tmp` to be held until the function returns, through `long_compute`. | 4 | perf, possibly yes | **Missing**: the extent list (call, iteration, task, step, process) has no block or branch extent | Add block and branch scopes as extents, or require last-use release for values above a size threshold. |
| EC1-C13 | `main :: fn() { world := load(); for { tick(world) } }` | The process extent never ends. At exit, memory is not released (the OS reclaims it), but resources are (M7). | 4, 5 | no | Ambiguous: "every extent ends: ... the process" | At process exit, memory release is skipped, and resources are closed in reverse order of acquisition. |
| EC1-C14 | `prev := List(f32){}; for s in 0..n { cur := step(prev); prev = cur }` | Two storage slots alternate between iterations. | 6, 7 | perf | Covered by layer 7 (buffer packing), but only tensors are named | Apply layer 7 to any loop-carried same-shape value, not only tensors. |

### 1.4 Escape

| ID | Proposed program | Expected under memory.md (hand trace) | Layer | L19 | Plan | Proposed rule where missing |
| --- | --- | --- | --- | --- | --- | --- |
| EC1-D01 | `build :: fn(n: usize) List(i32) { xs := List(i32){}; ...; ret xs }` | Accept; placed in the caller's extent. | 3, 4 | no | Covered (corpus 7) | none |
| EC1-D02 | `get :: fn() []i32 { buf: [4]i32 = [1, 2, 3, 4]; buf[0] = 5; ret buf[0..2] }` | Reject: a view outlives its owner (M13). Currently accepted by a7 and Zig-clean, **dangling** (q13). | 3 | yes | Covered (corpus 7, M13) | none |
| EC1-D03 | `head :: fn(xs: ref List(i32)) []i32 { ret xs[0..2] }` | M13 says slices "cannot be returned", even when the owner is the caller's. This rejects a common helper. | 3 | **yes** | Ambiguous: a view of caller-owned storage does outlive the call | Gate: either keep the rule (return an owned copy or an index range) or allow returning a view derived only from `ref` parameters, valid until the caller next changes that value. |
| EC1-D04 | `View :: struct { data: []i32 }; make :: fn() View { ... ret View{data: buf[0..4]} }` | M13: slices cannot be stored, so slice-typed struct fields are forbidden. Currently accepted (q02). | 0, 3 | yes (breaking) | Missing breaking-change row: struct fields of slice type | Add §3 row "slice-typed fields become owned values or index ranges". Examples use `string` fields (009, 038, 040, 042), which become owning strings. |
| EC1-D05 | `add :: fn(reg: ref Registry, it: Item) { reg.items.append(it) }` | Accept. The summary says "param 1 stored into param 0", so the caller moves `it` if it is dead and copies it otherwise. | 3 | no | Covered by "store into outer value" | none |
| EC1-D06 | `Holder :: struct { p: ref i32 }; keep :: fn(h: ref Holder, x: ref i32) { h.p = x }` | Reject (M4). Currently accepted and Zig-clean (p03). | 3 | yes (breaking) | Covered (§3 row, M4) | none |
| EC1-D07 | `REGISTRY := List(Item){}` at module level; `register :: fn(it: Item) { REGISTRY.append(it) }` | Accept; the value goes to the process-extent store. | 3, 4 | no | Covered (corpus 13) | none |
| EC1-D08 | `g: ref Pt = nil` at module level; `stash :: fn(p: ref Pt) { g = p }; local := Pt{x: 1}; stash(local)` | Reject (M4, plus `ref` cannot be stored). Currently accepted and Zig-clean, **dangling** (p04). | 3 | yes (breaking) | Covered | none |
| EC1-D09 | `id :: fn(p: ref Pt) ref Pt { ret p }` | Reject: `ref` cannot be returned (§2). Currently accepted and Zig-clean (p23). | 3 | yes (breaking) | **Missing §3 row**: `ref` return types | Add a §3 row: functions returning `ref T` migrate to returning an index or taking a `ref` parameter to update. |
| EC1-D10 | `Slot :: struct { h: Handler }; s := Slot{h: one}; s.h()`, and locals `op: BinaryOp = sub` (022:32, 037:130) | M6 excludes "stored function values", which would also reject these today-valid forms, even without captures. Currently accepted (q06). | 3 | yes (breaking) | **Ambiguous**: "stored" is undefined for plain function pointers without captures | Split M6: function values without captures are ordinary values (they may be stored and bound). Only closures that capture values are excluded from v1. |
| EC1-D11 | `each :: fn(xs: List(Item), f: Visit) { for i, x in xs { f(x) } }; each(items, show)` | Accept; the callback borrows each element for the call. | 3 | no | Covered (M6 non-escaping callbacks) | none |
| EC1-D12 | `each_mut :: fn(xs: ref List(Item), f: fn(ref List(Item))) { for i, x in xs { f(xs) } }` | The callback can grow `xs` during iteration. Reject as an exclusivity conflict (iteration versus `ref` passed on). | 2, 3 | yes | Ambiguous: listed under collections, "iteration while changing" | Iterating over a `ref` collection and passing that same `ref` on inside the body is a conflict unless the callee summary is read-only. Function-pointer callees have no static summary, so they are assumed to write. |
| EC1-D13 | `fill :: fn(out: ref []i32) { local: [4]i32 = [0, 0, 0, 0]; out = local[0..4] }` | Reject: a view stored through `ref` outlives its owner. | 3 | yes | Covered by M13 ("cannot be stored") | none |
| EC1-D14 | `keep := outer[0..2]; while i < 2 { buf: [2]i32 = [1, 2]; keep = buf[0..2]; i += 1 }; n := keep.len` | Reject: the view outlives the iteration's owner. Currently accepted and Zig-clean, **dangling** (q03). | 3, 4 | yes | Covered by M13 | Diagnostic must name the loop extent ("`buf` ends each iteration"). |
| EC1-D15 | `pick :: fn(a: List(i32), b: List(i32), c: bool) List(i32) { if c { ret a }; ret b }` | The summary says it returns param 0 or 1. The caller copies whichever argument stays live. | 3 | perf | Covered implicitly | none |
| EC1-D16 | `identity(buf[0..2])` with `identity($T) :: fn(v: $T) $T` | Reject at instantiation when `$T` is a view type: the view escapes through a return. | 3 | yes | Missing: generic escape | See EC1-F03. |

### 1.5 Control-flow interactions

| ID | Proposed program | Expected under memory.md (hand trace) | Layer | L19 | Plan | Proposed rule where missing |
| --- | --- | --- | --- | --- | --- | --- |
| EC1-E01 | `data := load(); defer print(data.len)` | The `defer` must run before `data` is released. | 0, 2 | no | **Missing**: M7 keeps `defer` but gives no ordering against automatic release | All user `defer`s of a scope run first (in LIFO order), and compiler releases of that scope run after them. |
| EC1-E02 | `defer log(xs.len); reg.append(xs)` | The `defer` reads `xs` at every scope exit, so `xs` is live, and `append` must copy. | 1, 2 | perf | Missing | A `defer` body counts as a use on every exit edge of its scope. |
| EC1-E03 | `defer print(n.len); n = other_list()` | The `defer` sees the value at exit (Zig semantics). The old `n` is released at reassignment. | 0, 2 | no | Missing | Follows EC1-E01, plus the reassignment rule from EC1-C07. |
| EC1-E04 | `ret_list :: fn() List(i32) { xs := build(); defer xs.append(0); ret xs }` | If `ret xs` moves the buffer to the caller, the `defer` then writes a moved-from list, a **use after move inside generated code**. | 0, 2, 6 | yes if miscompiled | **Missing** | A returned value that any pending `defer` reads or writes is copied at `ret`, or the program is rejected ("defer changes a returned value"). Recommend the copy, as Zig does. |
| EC1-E05 | `for i in 0..n { f := open(p); defer f.close(); if bad { continue } }` | The `defer` runs at every iteration exit, then the iteration store is released. | 0, 4 | no | Ambiguous with M7 (resources) | M7: an explicit `close` consumes the handle, and automatic release skips consumed handles. This is static when `close` is on every path; otherwise the handle carries its closed state (allowed runtime work, to be added to contract item 4). |
| EC1-E06 | `match k { case 1: { tmp := build(); defer print(tmp.len); fall } case 2: {...} }` | `tmp` and its `defer` end at the arm's block exit, before the next arm runs. | 0, 4 | no | Missing (the `fall` extent) | An arm body is a block extent, and `fall` exits it. Current lowering matches this: the Zig `defer` sits inside the arm block, and the `fall` is a labeled `break` (p24). |
| EC1-E07 | `p := Pt{x: 5}; q := Pt{x: 6}; r := match k { case 1: p else: q }; r.x = 9; print(p.x)` | Accept; prints 5. `r` is a copy of the chosen value. If `p` and `q` are dead afterward, the chosen one moves and the other is released at the join. | 0, 2, 6 | no | Missing (match expression yielding owners) | Use the edge-release rule from EC1-B02. Currently: human mode compiles, and **JSON mode crashes** (q08, finding F12). |
| EC1-E08 | `x := if c { a } else { build() }` | Same as EC1-E07. | 2, 6 | no | Missing | Same rule. |
| EC1-E09 | `f :: fn() { xs := build(); ret; print(xs.len) }` | The unreachable statement is rejected (current validator, p19). Compiler-inserted releases after `ret` must not trigger that check. | 0 | no | Missing | Inserted release, reset and move operations live in IR and the backend plan, never as AST statements, as §4 already implies ("code generation never infers them from spelling"). |
| EC1-E10 | `for { i += 1 }; i = 5` | Code after an infinite loop with no `break` is dead. Releases placed after it are never emitted. Currently **not** reported as unreachable (q15 compiles). | 0, 1 | no | Missing | CFG reachability treats `for {}` with no `break` as non-returning. Warning parity with `ret` is a validator decision. |
| EC1-E11 | `@outer for i in 0..n { row := build(i); for j in 0..m { if skip(i, j) { continue outer } } ; grid.append(row) }` | `continue outer` releases `row` and the inner iteration, then resets the outer iteration. | 0, 4 | no | Covered in general by "break and continue" | Same as EC1-C05. |
| EC1-E12 | A bounds-check trap or out-of-memory stop inside a loop that holds an open file | Memory is not released (the process stops). Whether resources are closed depends on M2 and M7. | 4 | no | Ambiguous (M2 "stops the program") | M2: a stop runs no user `defer`s and no releases, and the OS reclaims resources. |

### 1.6 Generics

| ID | Proposed program | Expected under memory.md (hand trace) | Layer | L19 | Plan | Proposed rule where missing |
| --- | --- | --- | --- | --- | --- | --- |
| EC1-F01 | `List(List(string))` released at scope end | Iterative release per specialization. `List(i32)` needs no element loop. | 5, 8 | no | Covered (contract item 8) | Release code is generated per instantiation, and element types that own no storage emit none. |
| EC1-F02 | `push($T) :: fn(xs: ref List($T), v: $T) { xs.append(v) }` with `$T = i32` and with `$T = List(u8)` | One escape summary ("v stored into xs"); the storage plan differs per instantiation (trivial for `i32`, a move for `List(u8)`). | 3, 5 | no | **Missing**: are summaries per generic definition or per instantiation? | Escape summaries are computed after monomorphization, as SPEC §7.4 already specializes per call site. They may be cached per shape class ("owns storage", "is view", "plain"). |
| EC1-F03 | `identity($T) :: fn(v: $T) $T { ret v }; s := identity(buf[0..2])` | Accepted for `$T = i32`. For `$T = []i32`, the view escapes: reject at the call site, noting both the generic body and the call. | 3 | yes | Missing | Instantiation-time diagnostics cite the call site first and then the generic return. |
| EC1-F04 | `Box :: struct { value: $T }; Box([]i32){value: buf[0..3]}` | Reject: views cannot be stored (M13). Currently a **codegen error** ("generic type requires an explicit generic environment", p12). | 3 | yes | Missing | Instantiating a generic struct with a view type is a semantic error, not a codegen error. |
| EC1-F05 | `swap($T) :: fn(a: ref $T, b: ref $T) { t := a; a = b; b = t }; swap(arr[i], arr[j])` | Corpus 14: prove `i != j` or insert a runtime check. Currently **the SPEC §7.1 example itself does not compile** (p13, q04). | 0, 2 | yes | Covered by corpus 14; the SPEC example is broken | Fix EC1-A12 first (`ref` in value position yields the value); `a = b` then means a value store. |
| EC1-F06 | `m := Map(string, List(Item)){}; ...; v := m.get(k)` | Either a copy (possibly large) or a view (invalidated by a later `insert`). Unspecified. | 2, 6 | perf or yes | **Missing** | Lookup returns an optional *view* valid until the map next changes (under the M13 growth rule). `x := m.get(k)` binds a copy only if `x` outlives a later change, found by layer 6 liveness. This needs a gate. |
| EC1-F07 | `min($T: Numeric) :: fn(a: $T, b: $T) $T` | Trivial; there is no storage. | none | no | Covered | none |
| EC1-F08 | 200 instantiations of `List($T)` over record types | One storage plan per instantiation, which costs compile time. Placement must be deterministic. | 5, 8 | no | Covered by "determinism, compile-time cost" (another audit's category) | Order plans by instantiation key, not by hash-set iteration. |
| EC1-F09 | `big($T) :: fn() { v: $T; ... }` with `$T = [4]u8` and `$T = [1000000]f64` | Stack for one, store for the other (EC1-A01 threshold). The same source is placed differently per instantiation. | 5 | no | Missing | The threshold is applied per instantiation and shown in the memory report. |
| EC1-F10 | `Store($T)` with generation ids, `$T = Store(Item)` (a nested store) | Generation checks per level. Releasing the outer store iterates inner stores. | 5 | no | Covered (M5, contract item 8) | none |

Total: 80 edge cases (EC1-A values: 15, EC1-B moves: 13, EC1-C extents: 14, EC1-D escape: 16, EC1-E control flow: 12, EC1-F generics: 10). The `EC1-` prefix identifies this audit; the letter identifies the category.

## 2. Plan gaps and contradictions, with proposed fixes

1. **Sharing without counts (§2 and §4; EC1-A03, EC1-A04).** "Shares storage until
   either side changes" needs to know, per path, which side writes first. When that
   is data-dependent (loops), the only count-free options are an eager copy or a
   one-bit uniqueness flag. Contract item 4 permits neither explicitly.
   **Fix:** "Copy is the semantics. Move and sharing are unobservable
   optimizations. When the first writer is data-dependent, the compiler copies
   eagerly at the binding." Say so in §4, and record that such copies are not
   the "hidden copies" synthesis item 7 forbids.
2. **Contract item 7 versus the corpus (EC1-D02, -04, -06, -08, -09, -13, -14).**
   Item 7 says user-visible rejections are exclusivity conflicts. Corpus 7, 10, 11
   and 12 and gates M4, M6 and M13 reject escapes, stored references and stored
   function values. **Fix:** enumerate the rejection classes: exclusivity
   conflict, view outliving its owner, stored or returned `ref`, capturing
   function value (M6), value used after it moved into a task (M10), and an
   uninitialized read (EC1-C08).
3. **Two failure policies (§4 versus synthesis item 7).** When uniqueness cannot
   be proven, §4 copies; synthesis item 7 says to reject. **Fix:** proven
   uniqueness failures copy. Escape and view-lifetime failures reject. Extent
   choices never reject; they fall back to copying out on the escape edge
   (EC1-C02).
4. **Unbounded retention in long-running loops (contract item 5; EC1-C07, EC1-C06,
   EC1-C12).** "May be held until that extent ends" allows a
   `state = next(state)` loop inside `main` to grow without bound, and bump-arena
   growth of a list leaks its old buffers. **Fix:** add to contract item 5:
   "Inside a loop, a value that is no longer reachable from a live owner is
   released or reused no later than the end of the iteration in which it became
   unreachable. A reassigned binding releases its previous value at the
   reassignment. Growable collections free their old buffers when they grow."
   Add block and branch extents, or a size-threshold last-use release (EC1-C12).
5. **Escape that depends on the path (EC1-C02, EC1-C03).** Per-site "tightest
   extent" cannot express "escapes on one path only". **Fix:** allocate in the
   innermost extent and deep-copy out on escape edges. Allow speculative placement
   in the outer store only when every path escapes (layer 6).
6. **A move between stores is a copy (EC1-C04).** The plan treats moves as cheap.
   Moving a value from an iteration arena into a longer-lived collection store
   copies its heap parts. **Fix:** state this in §4, and let the memory report
   count cross-store moves.
7. **Ordering of `defer` and release (M7; EC1-E01 to EC1-E05).** No rule exists.
   **Fix:** user `defer`s run in LIFO order before compiler releases for the same
   scope. A `defer` body is a use on every exit edge. A returned value that a
   pending `defer` touches is copied at `ret`.
8. **Joins and conditional moves (EC1-B02, EC1-B07, EC1-E07).** Contract item 3
   requires static release points, but the plan does not state how to reach
   them. **Fix:** "Releases are placed on CFG edges (critical-edge splitting).
   No drop flags." This also rules out the snapshot-and-restore fact joins used
   today (finding F1).
9. **"Use after move" in the Phase A list (EC1-B06)** contradicts §2, which has
   no user moves. **Fix:** reword it as an internal invariant tested by a compiler
   self-check.
10. **Partial moves and moves out of elements (EC1-B04, EC1-B05, EC1-B09).**
    Unaddressed. **Fix:** no observable partial moves. Read-then-overwrite becomes
    a take. Values behind `ref` are never moved out. `remove` returns an owned
    value.
11. **Missing §3 breaking-change rows:**
    - `ref` in value position (`t := a` is currently `ref i32`, q14). Fix it so
      the binding yields the value (EC1-A12).
    - `ref` return types (p23, EC1-D09).
    - Slice-typed struct fields (q02, EC1-D04).
    - For-in bindings made immutable. Today a7 accepts `v.x = 9` and Zig fails
      on it (p20, EC1-A13).
    - Definite initialization. Today a7 accepts `last: Pt` read after a
      zero-iteration loop (q05, EC1-C08).
12. **M6 wording (EC1-D10).** "Stored function values" would reject today's
    capture-free function pointers in locals and fields (`examples/022:32`,
    `037:130`, q06). **Fix:** exclude only capturing closures.
13. **M13 and helpers returning views of `ref` data (EC1-D03).** This is an L19
    cost. Put it to the user as a gate.
14. **Nested collections versus Python intuition (EC1-A08).** Value semantics make
    `row := grid[0]; row.append(5)` leave `grid` unchanged. This is correct under
    the plan but is an L19 surprise. **Fix:** document the rule "bindings copy,
    place expressions change in place", plus an optional lint.
15. **Generics (EC1-F02 to EC1-F04, EC1-F06, EC1-F09).** The plan does not say
    whether summaries and storage plans apply per definition or per
    instantiation. **Fix:** compute them after monomorphization, cache them by
    shape class, and report view-type instantiation errors semantically at the
    call site. Specify how map and list lookups return values (EC1-F06).
16. **Aliased by-value and `ref` arguments (EC1-A06).** Value semantics say copy,
    and contract item 7 suggests reject. **Fix:** copy. Reject only overlap
    between two `ref` arguments.
17. **Large values on the stack (EC1-A01, EC1-F09).** **Fix:** a size threshold
    moves large values into the call store. The threshold is deterministic per
    target and shown in the memory report.
18. **`fall` edges in the IR (EC1-B08, EC1-E06).** Layer 0 must model `fall`
    explicitly. The current flag-based Zig lowering is not a CFG.

## 3. New gate questions for the user

Each needs before-and-after examples under the approval rule.

- **Q-A (copy policy):** When the compiler cannot tell which of two copies changes
  first, is an eager copy acceptable (and shown only in the optional memory
  report), or must it be a warning?
- **Q-B (loop memory promise):** Should the contract guarantee flat memory for
  long-running loops, meaning a replaced value is released at replacement
  (EC1-C07)? Or is "held until extent end" acceptable?
- **Q-C (element copies):** With `row := grid[0]; row.append(5)`, should `grid`
  stay unchanged (value semantics, EC1-A08)? Should the compiler warn when a
  changed copy of an element is never written back?
- **Q-D (for-in bindings):** Make `for v in xs { v.x = 9 }` a compile error
  (EC1-A13), or reintroduce per-element change permission (for example, a
  separately approved form)?
- **Q-E (`ref` in value position):** Should `t := a`, where `a: ref T`, copy the
  value? This is a breaking change from the current `ref` binding (q14, EC1-A12).
- **Q-F (returning views):** May a function return a slice of data it received by
  `ref` (EC1-D03), or must it return an owned value or an index range?
- **Q-G (function values):** Do capture-free function pointers stay storable in
  locals and fields (022, 037), with M6 excluding only capturing closures
  (EC1-D10)?
- **Q-H (map lookup):** Should `m.get(k)` return a copy or a temporary view
  (EC1-F06)?
- **Q-I (definite initialization):** Should declarations without an initializer
  that some path reads before assigning be rejected (EC1-C08), or should values
  get zero or default initialization?
- **Q-J (defer and return):** When a `defer` changes the value being returned,
  copy at `ret` (Zig-like) or reject (EC1-E04)?
- **Q-K (large values):** Is it acceptable for the compiler to move large fixed
  arrays off the native stack silently (EC1-A01)?
- **Q-L (rejection classes):** Approve the enumerated user-visible rejection
  classes that replace contract item 7 (gap 2).

## 4. Current-compiler findings

### Verified by code read

- **F1.** The move and delete state is a single name-keyed set:
  `self.moved_symbols: set[str]` (`a7/safety.py:236`), reset only in `analyze`
  (`:247`), written by `_mark_deleted` (`:724-726`), and checked on every
  identifier read (`:397-399`). It is not restored after blocks, branches or
  match arms. Fact joins use `copy_symbols`/`restore_symbols` snapshots, with no
  CFG (`:301-306`, `:335-344`).
- **F2.** No loop fixpoint: `while`, `for` and `for-in` bodies are visited once
  (`a7/safety.py:345-371`), so errors that need a back edge are missed.
- **F3.** Match arms are visited in sequence with no save or restore of the
  moved set (`a7/safety.py:372-378`).
- **F4.** A deferred `del` visits its operand without marking it deleted
  (`a7/safety.py:379-386`).
- **F5.** Calls invalidate nothing; the pass only visits arguments
  (`a7/safety.py:444-447`). There are no effect summaries.
- **F6.** Assignment through a `ref` is implicit only when the right-hand side is
  *not* a `ReferenceType` (`a7/passes/type_checker.py:834-841`). Otherwise the
  immutability check fires (`:851-859`). This is the root cause of F11.
- **F7.** `del` lowers to `if (expr) |p| allocator.destroy(p);` with the fixed
  capture name `p` (`a7/backends/zig.py:1300-1306`). `defer` is a 1:1 Zig
  `defer` (`:1272-1298`). Labeled loops lower to `a7_loop_<name>:`
  (`:833-964`). Call arguments get `&` for `implicit_ref_args`
  (`:1661-1664`).

### Compile-only (a7), with Zig-checked results where stated; no binary executed

- **F8. Path-insensitive false positives:**
  - p08: `del p` in the `then` branch makes reads of `p` in the exclusive `else`
    fail ("Use after move or delete").
  - p09: the same happens across match arms.
  - p17 (C4): `{ p := new Pt; del p }; p := 5; q := p + 1` is rejected at the
    unrelated `p`.
- **F9. Missed errors in loops:**
  - p06: a double `del` inside `while` passes a7.
  - p07: read, then `del` at the end of the loop body passes a7 (use after free
    on the second iteration).
  - p05: `new` in a loop with no `del` passes a7 (a leak, as notes H found for
    `leak.a7`).

  With Zig, these fail only incidentally: `capture 'p' shadows local constant`
  (p06, p11, q09b) and `shadows function parameter` (q12, a `del` of a `ref`
  parameter, MS-5). Lesson for compiler-inserted releases: use fresh names and
  never rely on Zig shadowing errors as a backstop.
- **F10. Escape holes that a7 accepts and Zig also accepts (dangling):**

  | Probe | Hole |
  | --- | --- |
  | p03 | `ref` parameter stored into a struct field |
  | p04 | `ref` to a local stored in a module-level `var g: ?*Pt` |
  | p23 | `ref` parameter returned |
  | q03 | slice of a per-iteration array carried out of the loop |
  | q13 | slice of a mutable local array returned |
  | q11 | struct holding a `ref` copied (`h2 := h`), then the original deleted; leaves latent dangling `ref` fields, never read afterward (the read variant is notes H `reffield_other.a7`) |

  q01 and q02 (slice of a `const` local array, returned directly or inside a
  struct) and p15 (slice of a by-value array parameter) are also accepted by a7.
  Zig rejects them only because `*const [N]i32` does not coerce to `[]i32`, an
  accidental backstop that disappears once the array is mutated (q13).
- **F11. The SPEC §7.1 `swap` example does not compile:** p13 (generic) and q04
  (`ref i32`) both fail with "Cannot assign to immutable binding: 'a' is
  immutable". Also, `t := a` on `a: ref i32` has type `ref i32` (q14: "Return
  type mismatch: expected 'i32', got 'ref i32'"), so even a compiling swap would
  alias. This is doc/code drift, relevant to corpus 14 and EC1-A12.
- **F12. `--format json` crashes** on a match expression that yields a struct
  (q08): `json_formatter.py:215` raises `TypeError: 'ASTNode' object is not
  iterable`, and the process exits 1 (not the documented internal-error exit 8).
  Human mode compiles it (`var r = switch (k) {...}`). This is a compiler
  defect, not a memory one.
- **F13.** For-in element mutation `for v in arr { v.x = 9 }` passes a7 and fails
  Zig with "cannot assign to constant" (p20). There is no A7 rule for for-in
  binding mutability.
- **F14.** A read after a zero-iteration loop of a declaration without an
  initializer passes a7 and Zig (q05, emitted `var last: Pt = undefined`).
  There is no definite-initialization check.
- **F15.** Aliased `ref` arguments `both(p, p)` pass a7 and Zig (p14). There is
  no exclusivity check.
- **F16.** Generic structs over slice types fail in codegen, not semantics (p12:
  "Zig backend: generic type requires an explicit generic environment").
- **F17.** Code after `for {}` with no `break` is not reported as unreachable
  (q15). A statement after `ret` is (p19).
- **F18.** A capture-free function pointer stored in a struct field passes a7 and
  Zig (q06). Examples bind function values to locals (`examples/022:32`,
  `examples/037:130`). A literal M6 would break these.
- **F19.** `new`/`del` appear only in `examples/011_memory.a7` and
  `examples/037_language_tour.a7` (lines 118 and 123). The migration surface in
  examples is small. `string` struct fields appear in 009, 038, 040 and 042.
- **F20.** Minor friction: `ret 0` in a function returning `usize` is rejected
  ("expected 'usize', got 'i32'", q09). It needed `cast(usize, 0)`.
- **F21.** Accepted value-copy shapes (compile-only, emitted Zig is by-value,
  not run):
  - q07: generic `Box(Pt)` copy, then change.
  - q08 (human mode): match-expression struct copy.
  - q10: struct with an array field copied inside a loop.

  memory.md's own native observation covers only plain structs and fixed
  arrays.
