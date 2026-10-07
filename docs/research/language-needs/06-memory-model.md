# 06 — A7 memory-model gap

Status: research only, 2026-10-02. No mechanism selected. L37 permits
compiler-managed runtime help; it selects nothing. L42 fixes list-assignment
identity (share; explicit copy). L38 sets the 1.10x C baseline bar (median time
and peak live memory). L39 allows checked execution; checks stay in release.

## 1. Current lowering and safety facts

- `new T` emits `allocator.create(T) catch null`; `new [N]T` emits
  `allocator.alloc(elem, N) catch null` (`a7/backends/zig.py:2196-2206`).
  Failure value is `nil`, not a diagnostic.
- `del x` emits `if (x) |p| allocator.destroy(p)` (`zig.py:1514-1523`); codegen
  rejects `del` of a non-reference type (`zig.py:1520-1521`).
- Allocator is global: `std.heap.smp_allocator` (thread-safe build) or
  `std.heap.page_allocator` (`zig.py:177-186`). One allocator, no extents,
  no placement choice.
- Semantic validation of `new`/`del` is a stub: allocation tracked, leak
  detection unimplemented (`a7/passes/semantic_validator.py:506-510`); `del`
  validation at `:400`.
- Safety pass: `del` invalidates the operand's identifier fact, reducing
  through field/index/slice/deref bases to the base name
  (`a7/passes/safety.py:428-430`). Ref args, deref, and field access through
  refs need a proven non-nil fact (`safety.py:974-993`, `:788-795`).
- Fact map is keyed by plain identifier only. Facts are never derived from a
  field or element value, so `b.value = 0` cannot kill the fact for `b`
  (`semantic_validator.py`, `_deferred_assigned_symbols` comment). The same
  blindness applies to value aliases: two names for one struct are invisible
  to the fact engine.

## 2. Known aliasing holes (nested refs, del-through-ref, double-del)

- Nested refs: a struct holding a `ref` copies the reference on assignment
  (plan records current binding type as `ref T`; removal is unapproved gate
  M31). Copying a `ref` into a field then deleting the original writes freed
  memory (brainstorm notes H). Returning a struct holding a `ref` to a local
  dangles (same source).
- Del-through-ref: `del` of `s.field` kills the fact for `s`, which is
  over-invalidation in the safe direction, but a live alias `t := s` keeps a
  stale fact and a stale pointer. No alias tracking exists.
- Double-del: after `del x`, `x` still tests non-nil (nothing nils it), so
  `del x; del x` emits two `destroy` calls. The `if (x) |p|` guard only
  protects literal `nil`, not use-after-del. No move-after-del rule is
  enforced.
- Overlapping write through a live slice (`s := arr[0..2]; arr[0] = 7`) runs
  today and `s[0]` reads 7; revision-3 plan would reject it (unapproved).

## 3. External models (what to borrow, what to refuse)

- Zig: explicit allocator per call, no hidden allocation, caller chooses
  (`GeneralPurposeAllocator` for debug/leak checks, `ArenaAllocator` for
  extents, `smp_allocator`/`page_allocator` for global). A7 already lowers to
  this; missing layer is who picks the allocator per extent. Borrow the
  allocator taxonomy and the debug-allocator leak protocol for gates.
- Odin: implicit `context.allocator` threaded through every call; default is
  heap, replaceable per scope (arena per frame/loop iteration is idiomatic).
  Closest fit to "compiler picks extent, user sees nothing": B1 arena is an
  Odin-style scope allocator with the choice made by the compiler, not the
  user. Borrow per-scope swap discipline; refuse implicit global state without
  a reset point.
- Jai: allocators as explicit parameters, `temporary` storage per scope,
  no hidden control flow. Borrow the "reset at scope end" contract; refuse
  manual threading (L19/L21 forbid the mental load).
- Rust: ownership + moves + borrow checker, one owner, compile-time exclusivity,
  `RefCell/Rc` as opt-in runtime escape. Borrow the exclusivity rule shape
  (one writer xor readers) for the static side; refuse lifetime annotations in
  surface syntax and refuse `Rc` cycles policy as precedent (Rust pushes cycles
  to the user with `Weak` — A7 must handle W3-style cycles internally or
  reject with a rewrite).

## 4. Open design surface: extents, copies, placement, reuse, planner, layout

- Extents: candidate set is call, iteration, task, training step, session,
  process (M11 disputed: structural tensor rules vs this flat set). Block/branch
  extents undecided (M38): a large temporary in one branch is held to call end
  without them. Resources and native-retained buffers must never sit in a
  bulk-reset extent (M45).
- Copies: contract item 4 (copy-on-bind, remove only when proven unobservable)
  is superseded by L42 for lists (share by default, explicit copy). Struct and
  fixed-array value behavior stays. Copy spelling and failure behavior need the
  memory packet; M33 (optional copy vs view on lookup) has unanimous reviewer
  support for views and no defender of copies — B3 must measure read-heavy and
  nested-update shapes for both.
- Placement: whole-program assumption (monomorphize first; M50 undecided),
  per-target stack-size threshold for large values (M35), deterministic for
  identical source/target/version (M40). Native boundary needs descriptors
  (M12/M25, no syntax today).
- Reuse: Perceus-style runtime uniqueness checks do not transfer to a
  count-free design; FP² definition checks do not cover call-site sharing
  (reconciliation primary-source check). Any reuse claim needs call-site proof
  evidence plus missed-reuse counts, not citations.
- Planner: only dynamic shapes need a runtime planner (M20/M44: bucket by
  shape/dtype/device/alignment, cap count+bytes+work, checked-alloc fallback).
  Static shapes get static plans.
- Layout report: SoA per type across the program, excluding types reaching
  native code or `ref` element args; identical output with/without transform
  plus measured locality. User-facing report uses plain terms (M8/M9); no
  memory vocabulary in source.

## 5. B1 (arena) vs B2 (RC) comparison axes

Both behind one flag, default behavior byte-identical. Touch map:
preamble `zig.py:177-221`, `_emit_new_expr` `:2202-2213`, `_visit_del`
`:1514-1518`, `_visit_defer` `:1482-1510`, plumbing `a7/compile.py:100-109`.

| Axis | B1 arena (one per function extent + deinit) | B2 RC (header + retain/release, roots-only) |
| --- | --- | --- |
| Release timing | Bulk reset at extent end; peak = high-water per extent | Per-value at last release; peak tracks live set |
| `del` sites | Must become no-ops (never double-release) | Must become release-dec, never a second free |
| Cycles (mem_cyclic) | Harmless if same extent; edges are `usize` today so RC-unexpressible until assignable ref fields land | Leaks without cycle handling; needs stated policy |
| Returns (mem_returned) | Callee-local arena dies at return; needs caller-provided or global arena | Naturally escapes via retained count |
| Failure path | OOM at arena chunk growth (M2 scope TBD) | OOM at retain/copy point; partial builds need rollback |
| Overhead source | Reset cost + retained-until-end bytes | Header bytes + atomic/non-atomic count traffic |
| Determinism | Bump pointer is order-stable | Release order follows execution order |

## 6. Measurement plan: the 7 bench shapes

`bench/mem_*.a7` (from `tmp/b-benchspec/`, counted-up, exact `result:` lines in
`docs/plan/HANDOFF-2026-10-02.md`): shared (list alias write visibility),
copy (snapshot independence + cost), cyclic (usize-edge graph build/teardown),
returned (escape producer storage), cache (bounded eviction, flat memory),
text (retained parse output), cleanup (open/close pairing under failure).
These are the B3 corpus. Map: shared/copy stress L42; cyclic maps to W3;
returned maps to W4; cache maps to W5; cleanup maps to W6 (+W10 integrity);
text maps to W8. W7 (tasks), W9 (views/tensors) have no bench shape yet.

Per run record: wall time, peak RSS, peak live bytes, alloc count, copied
bytes, release time, compiler time/RSS, emitted size. Instrumented runs for
counts, separate clean runs for time. N vs 10N for cache/cleanup flatness
(RSS and live bytes separately). Debug + ReleaseFast. Proposed (unapproved)
budgets in the reconciliation doc: 1.25x time / 1.25x live bytes vs baseline;
L38's 1.10x governs qualification. Freeze budgets before baselining; baseline
authors work from specs, not from candidate output.

## 7. What B3 must contain to select a mechanism

1. Per-workload table for B1, B2, and C baseline: all measures above, both
   profiles, N and 10N where applicable. 2. Rejection/rewrite log per
   candidate (zero-silent-change rule: a rewrite is reported, never folded
   into the timing). 3. Copy accounting: locations, byte counts, which copies
   a proof removed and which it could not. 4. Failure behavior: OOM point,
   cleanup-exactness (cleanup shape), partial-state rule. 5. Cycle verdict for
   B2 (policy + leak evidence) and escape verdict for B1 (caller-arena cost).
   6. Compiler cost (time/RSS at 10k and 100k statements) and determinism
   check (two builds, different hash seeds, identical Zig). 7. Explicit
   non-selection statement for tracing (documented, not built) and for the
   loser: which workloads it fails and why. Selection needs the memory packet
   (current vs proposed behavior, runnable examples, compatibility impact,
   acceptance tests) and a user decision; B3 recommends, it does not approve.
