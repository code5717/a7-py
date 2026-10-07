# 22 — Memory: what V1 can cut

Status: simplification audit, 2026-10-02. Parent: `06-memory-model.md`.
Current lowering: `new T` → `allocator.create(T) catch null`;
`del x` → `if (x) |p| allocator.destroy(p)`; one global allocator
(`smp_allocator` release, `page_allocator` debug; `a7/backends/zig.py:177-186`).
`new [N]T` heap fixed arrays are rejected at compile time. Leak detection is a
stub (`semantic_validator.py:506-510`). Safety facts are identifier-keyed only.

Thesis: V1 needs arena-per-function + explicit `del`. Everything else is cut.

## 1. What each language shipped WITHOUT at V1

- Zig (0.x → still): no GC, no borrow checker, no implicit allocator. Every
  allocation names its allocator. Leak check is debug-only (`GPA` +
  `deinit` assert), not a language rule. Lesson: ship explicit choice +
  debug tooling, not a managed default.
- Odin: shipped `context.allocator` (implicit per-scope default) but WITHOUT
  borrow checking, cycle collection, or a layout report. Arena-per-frame
  is idiom, not syntax. Lesson: one implicit scope rule covers 90% of
  placement; the rest is library convention.
- Jai (beta): explicit allocator params + `temporary` scope storage, WITHOUT
  automatic reuse, planner, or cross-function escape analysis. Lesson: reset
  at scope end is enough; reuse is a later optimization.
- Rust 1.0: shipped ownership + moves + borrow checker, WITHOUT `async`,
  WITHOUT placement (`placement-in` RFC never landed), WITHOUT a layout
  report, WITHOUT a runtime planner. `Rc`/`RefCell` existed but cycles were
  pushed to the user (`Weak`). Lesson: even Rust cut placement, planner, and
  layout reporting at V1 — and it had a borrow checker. A7 has none.

Pattern: nobody shipped placement syntax, reuse proofs, a runtime planner, or
a layout report at V1. All four are second-system features.

## 2. Cut entirely: placement / reuse / planner / layout report

| Feature (06 §4) | Verdict | Reason |
| --- | --- | --- |
| Placement syntax (per-target stack threshold M35, whole-program monomorphize M50, native descriptors M12/M25) | CUT from V1 syntax | No evidence any bench shape needs it. Stack-vs-heap for large values is a backend threshold constant, not syntax. Native descriptors belong in the FFI packet, not the memory packet. |
| Reuse (Perceus-style uniqueness, FP² call-site proofs) | CUT | Requires call-site proof evidence nobody has produced. B3 has no missed-reuse metric. Reuse is an optimization; correctness comes first. Revisit only with measured waste >25% on a real shape. |
| Runtime planner (bucket by shape/dtype/device, M20/M44) | CUT | Only dynamic tensor shapes need it; V1 has no tensor type. Static shapes get static plans for free. A planner without dynamic shapes is dead code. |
| Layout report (SoA transform, M8/M9) | CUT | SoA changes observable layout and needs identical-output proof. No bench shape measures locality. `--print-layout` CLI flag already shows struct offsets; that is enough for V1. |
| Block/branch extents (M38) | CUT | Holding one branch temporary to call end wastes bytes, not correctness. One arena per function is predictable; finer extents are scope creep. |
| Extent zoo (call, iteration, task, step, session, process) | CUT to two | Keep function extent + process (global) extent. Iteration/task/step extents are loops the user can already wrap in a helper function. |

## 3. Reject outright instead of specifying

These are compile-time errors in V1, not specified behaviors:

- Nested `ref` in a struct field that escapes: returning a struct holding a
  `ref` to a local dangles. Verdict: REJECT (borrowed-from-local escape is an
  error; 06 §2 case). No lifetime syntax to save it — return by value or
  allocate with `new` and return the pointer.
- `del` through a field/index of a shared value (`del s.field` while `t := s`
  is live): no alias tracking exists to make this safe. Verdict: REJECT `del`
  of anything but a plain identifier bound by `new` in the same function.
  Kills over-invalidation (§2) and the stale-alias hole in one rule.
- Double `del`: `x` still tests non-nil after `del x`, so `del x; del x` emits
  two `destroy` calls. Verdict: REJECT second `del` as use-after-move (error
  type already exists: `USE_AFTER_MOVE`, `DOUBLE_FREE`). Safety pass already
  invalidates the fact; add the diagnostic.
- Use-after-`del` reads: same rule as moves. Verdict: REJECT (already the
  `USE_AFTER_MOVE` error shape; enforce it instead of documenting UB).
- `del` of non-`new` value (stack struct, global, parameter): Verdict: REJECT
  (codegen already rejects non-reference `del`; extend to non-owned refs).
- Cycles (`mem_cyclic`): `usize` edges today, unexpressible in RC terms.
  Verdict: REJECT cycle collection from V1 scope; arena frees cycles for free
  when the extent ends. No `Weak`, no policy doc.

Each rejection is one sentence in SPEC, not a section.

## 4. The minimal V1 that covers the bench shapes

Arena-per-function + explicit `del`-of-local-`new`:

- Function entry creates an arena; all `new` in the body allocates from it;
  function exit resets it. Peak = high-water per function. Predictable.
- `new` failure = `nil` (current behavior, keep). Caller nil-checks.
- `del x` = early release hint + move-out of `x` (second `del`/use is an
  error). Inside an arena it is a no-op at runtime but still moves at
  compile time — same rule, both profiles.
- Escapes (returned refs, cached/text shapes): allocate from the caller's
  arena (pass one hidden arena param) or the process allocator. Two choices,
  picked by escape analysis; user writes nothing.
- Debug profile: leak check = arena `deinit` asserts empty after `del`s +
  extent end; no separate protocol to design.

This covers all 7 bench shapes: shared/copy (L42 share semantics, unaffected),
cyclic (same-extent cycles die at reset), returned (caller arena), cache/text
(process extent or explicit cap), cleanup (defer + arena reset is idempotent).

## 5. Lists

KEEP (V1 syntax + rules):
1. `new T` / `del x` with current lowering; `del` moves (reuse = error).
2. Arena per function + process allocator; hidden caller-arena param for
   escapes. No user-facing extent names.
3. Nil-on-OOM; mandatory nil-check before deref through ref (exists today).
4. Debug-only leak assert on arena deinit.
5. `--print-layout` offsets as the only layout surface.

CUT (refused with reason):
1. Placement syntax — backend constant, not syntax; no bench needs it.
2. Reuse proofs — no evidence, optimization not correctness.
3. Runtime planner — no dynamic shapes in V1 to plan for.
4. SoA layout report — observable-layout risk, no locality bench.
5. Block/branch extents — bytes, not correctness.
6. Cycle collector / `Weak` — arena reset already frees cycles.
7. Borrow checker / lifetime annotations — Rust-level cost, refused; the
   `del`-moves + no-escape rules above cover the holes cheaper.

LIBRARY (not syntax):
1. Bounded cache with eviction (bench `cache` shape) — stdlib type with cap.
2. Text/parse-output buffers (`text` shape) — process-extent buffer helper.
3. Fixed-capacity stack arrays — already in the language, no heap involved.
4. Future tensor planner/pool — ships with the tensor type, not before.

Line budget: this file replaces 06 §4–§5 (~60 lines of open surface) with
§2–§4 above (~50 lines of verdicts). Net spec shrink, not growth.
