# Gap 05 — Stack-budget proof

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.10](../07-language-review.md#110-stack-budget--no-proof-can-still-overflow).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

A7 already bans recursion (`a7/passes/semantic_validator.py:501-544`)
so the call graph is a DAG and the maximum stack depth of any
program is computable at compile time. The work is in framing the
frame-size estimation, choosing the budget, and deciding what
happens when the program exceeds it.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| SB-01 | Simple call chain `main → a → b → c` | Compiles; runtime stack |  Frame-size sum along path; assert ≤ budget |
| SB-02 | Diamond `main → {a, b} → c` | Compiles | Max over diamond branches |
| SB-03 | Local `buf: [1024]u8` | Compiles | Frame size includes the 1024 bytes |
| SB-04 | Local `buf: [N]u8` with `N` a constant | Compiles | Frame size = `N` at instantiation |
| SB-05 | Local `buf: [N]u8` with `N` a runtime value | **Rejected today** (heap fixed arrays banned) | n/a — already rejected per `CLAUDE.md:114-116` |
| SB-06 | Many small locals via `defer` blocks | Compiles | Each defer block adds its own frame; budget tracks the sum |
| SB-07 | `match` arms with different local sets | Compiles | Frame size = max across arms |
| SB-08 | Spill estimation: lots of live values | Compiles | Conservative upper bound (LLVM register-pressure heuristic) or fixed margin per function |
| SB-09 | FFI shim frame | n/a (no FFI today) | Treat opaque foreign frames as a fixed budget per `extern fn` (e.g., 4 KiB default; configurable per shim) |
| SB-10 | Threading: `pthread_create` (when supported) | n/a | Each new thread gets its own RLIMIT_STACK budget |
| SB-11 | Signal handlers | n/a | Use alt-stack (`sigaltstack`); fixed size; documented |
| SB-12 | `inline` functions (when supported) | n/a | Inlined frames sum at the call site |
| SB-13 | Large struct return by value | Today: emit `*T` out-param? | Account for both caller's slot and callee's local |
| SB-14 | Closures (when added) | n/a | Capture environment counts toward frame size |
| SB-15 | Generic function instantiated with large `$T` | Compiles | Frame size per instantiation; reject if exceeds budget |
| SB-16 | Indirect call (function pointer) | Compiles; call target unknown statically | Budget = max over all callable functions whose type matches |
| SB-17 | Tail call (if added) | n/a | Tail call doesn't grow stack; subtract |
| SB-18 | User wants more stack | n/a | `--stack-budget` CLI flag; per-function attribute? |
| SB-19 | Main vs threads | n/a today | Per-thread budget; default 1 MiB |
| SB-20 | A function calls 100 different small functions in sequence (no recursion) | Compiles | Each call inflates only its own frame; depth = 1 + max(callees) |

## Interactions

- **Gap 01 cast.** No interaction.
- **Gap 02 nullable pointers.** No interaction.
- **Gap 03 definite assignment.** Frame-size estimation must match
  the storage actually used; if DA causes some locals to be elided,
  the estimate matches.
- **Gap 04 NonZero division.** No interaction.
- **Gap 06 typed arithmetic.** No interaction.
- **Gap 07 bounded indexing.** Bounded indices keep stack-allocated
  arrays statically sized — needed for frame-size estimation
  (`buf: [N]u8` only works if `N` is constant).
- **Gap 08 `Option<T>` / `Result<T, E>`.** Adds a tag byte (or
  niche-optimised); frame-size accounting must include.
- **Gap 09 refinement-lite.** Refinement types are wrappers; frame
  size = underlying type.
- **Gap 10 affine ownership.** No interaction at the frame-size
  level; affects DA but not the stack budget.
- **Gap 11 finite floats.** No interaction.
- **Gap 12 FFI.** SB-09 above.
- **Recursion ban.** **Required prerequisite.** Without it, the DAG
  property doesn't hold and the analysis is undecidable.
- **Generics.** SB-15. Frame size is per-instantiation; budget check
  runs per-instantiation.
- **Imports / multi-file.** When implemented, the call graph spans
  files; budget analysis needs whole-program info.

## Failure modes

### False positives

- Conservative spill estimation overstates. A program that
  *actually* uses 600 KiB might be rejected for "1.5 MiB" because
  the estimator is pessimistic. Mitigation: keep the margin small
  but documented; allow per-function attribute to disable spill
  estimate (`@stack(actual=500_000)`).
- Indirect calls (SB-16) — if the type matches many functions, the
  budget is forced to the worst case. Reasonable for safety but
  surprising.

### False negatives

- Optimization-induced inlining or outlining changes the actual
  frame size from the estimate. Mitigation: estimate before opt; or
  re-check after.
- FFI shim that uses lots of stack internally. The fixed budget per
  `extern fn` is an over-approximation; if foreign code uses more,
  it's a documented hazard.

### Ergonomic costs

- Programmers who use deep call chains (parser combinators, big
  iterator-chain pipelines) may hit the default. Mitigation:
  `--stack-budget` raises it; document the default and the override.
- Big-struct return by value (SB-13) may be re-emitted as out-param;
  user code shouldn't care, but generated Zig changes.

### Performance costs

- None at compile time (analysis is O(call-graph-edges)).
- Runtime: the stack size is set once at thread creation; same cost
  as today.

## Open questions

- **Q05a.** What's the default budget? 1 MiB matches most desktop
  defaults; 64 KiB is too small; 8 MiB matches Linux default but is
  wasteful. **Recommendation: 1 MiB.**
- **Q05b.** Spill estimation strategy. Three options:
  - Fixed margin per function (e.g., 256 bytes).
  - Use LLVM's register-pressure heuristic (requires post-codegen
    analysis).
  - Re-check after Zig compilation by reading the `.text` section's
    frame info (most accurate; most invasive).
- **Q05c.** Per-function override syntax. Candidates:
  - `@stack(max=2_000_000)` attribute on the function decl.
  - A pragma-style annotation.
  - No override; only the global `--stack-budget` flag.
- **Q05d.** Indirect calls (SB-16) — strictest analysis or weaker?
  - Strictest: max over all functions matching the signature.
  - Weaker: track "indirect-call targets" via address-taken set; max
    over that set only.
- **Q05e.** Thread stacks (SB-10, SB-19) — separate budget per thread,
  or shared with main? Separate is right; mechanism for declaring
  per-thread stacks is open.
- **Q05f.** Big-struct returns (SB-13). Today's behaviour is open;
  the rule should be: structs > N bytes (say, 256) are returned via
  `set` out-param (Gap 03 interaction).
- **Q05g.** Signal-handler stacks (SB-11) — fixed size? Configurable?
  Documented?
- **Q05h.** When a program exceeds the budget, what's the diagnostic?
  Just an error, or a per-function breakdown showing the cumulative
  budget along the worst path?

## Source citations

- Recursion-ban infra to reuse:
  `a7/passes/semantic_validator.py:501-544` — `_validate_no_recursion`,
  `_find_recursion_path`. The call-graph machinery at lines 546–589 is
  the input for the budget pass.
- No stack-size analysis exists today; this is greenfield.
- Backend emits no stack-size annotation today.
- `main` entry point in emitted Zig: `build/debug/zig/src/001_hello.zig`
  shows `pub fn main() void` — no explicit stack-size setting.

## Phase C decision-input summary

1. Q05a — default budget. **Drives:** user experience.
2. Q05b — spill estimation strategy. **Drives:** accuracy vs effort.
3. Q05c — per-function override. **Drives:** ergonomics.
4. Q05d — indirect-call analysis precision.
5. Q05f — big-struct return policy.
6. Q05h — diagnostic shape.

The rest follow.
