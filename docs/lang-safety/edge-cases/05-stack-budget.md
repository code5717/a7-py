# Gap 05 — Stack-budget proof

Status: Phase A research from before 2026-09-14, not a decision. Decisions are in the [ledger](../../plan/decisions.md); the recursion-ban prerequisite is affected by gate [G4](../../plan/README.md#g4-function-values-and-the-recursion-ban).

Audit finding: [`../07-language-review.md` §1.10](../07-language-review.md#110-stack-budget--no-proof-can-still-overflow).
Phase C decisions were to land in [`../08-decisions.md`](../08-decisions.md).

## Summary

A7 bans recursion (`a7/passes/semantic_validator.py:501-544`). The call
graph is therefore a DAG, and the maximum stack depth of any program can
be computed at compile time.

The work is in estimating frame sizes, choosing the budget and deciding
what happens when a program exceeds it.

## Current behavior (2026-09-16)

Note (2026-09-16): evidence is a source and docs read on 2026-09-16; no
program was compiled in this session.

- The recursion ban is still at `semantic_validator.py:501-544`
  (`_validate_no_recursion`, `_find_recursion_path`). The call graph comes
  from `_collect_function_calls` at `semantic_validator.py:546-589`. The
  ban also covers local function-pointer alias cycles (`CLAUDE.md`, "A7
  Source Rules").
- The DAG property is not guaranteed. Gate G4 records that a callback
  stored in a struct field can create recursion the ban does not detect
  (MS-7 in the 2026-09-14 GLM memory-safety review). This affects the
  prerequisite and SB-16.
- Neither `docs/STATUS.md` nor `docs/SAFETY_CONTRACT.md` lists a
  stack-budget pass. The compiler source was not searched again.
- Under the [memory plan](../../plan/memory.md) (L17), the compiler
  decides where storage lives, grouping allocations into arenas and pools.
  Frame sizes then depend on those compiler decisions, not only on
  declared locals.
- Later plan items touch several subcases: threads (SB-10, SB-19) fall
  under concurrency gate G7; FFI shims (SB-09) under v1 plan track 10;
  closures (SB-14) under memory plan gate M6, which proposes rejecting
  capturing function values. The `set` out-parameter (Q05f) is not
  accepted syntax (ledger L6 scope limit).

## Subcases

| # | Pattern | Phase A: today | Phase A: target |
| --- | --- | --- | --- |
| SB-01 | Simple call chain `main → a → b → c` | Compiles; run-time stack | Sum frame sizes along the path; assert ≤ budget |
| SB-02 | Diamond `main → {a, b} → c` | Compiles | Maximum over the diamond's branches |
| SB-03 | Local `buf: [1024]u8` | Compiles | The frame includes the 1024 bytes |
| SB-04 | Local `buf: [N]u8` with a constant `N` | Compiles | Frame size = `N` at instantiation |
| SB-05 | Local `buf: [N]u8` with a run-time `N` | Rejected (heap fixed arrays banned) | n/a; already rejected per `CLAUDE.md:114-116` |
| SB-06 | Many small locals in `defer` blocks | Compiles | Each defer block adds its own frame; the budget tracks the sum |
| SB-07 | `match` arms with different locals | Compiles | Frame size = maximum across arms |
| SB-08 | Spill: many live values | Compiles | A conservative upper bound (LLVM register-pressure heuristic) or a fixed margin per function |
| SB-09 | FFI shim frame | n/a (no FFI) | A fixed budget per `extern fn` for opaque foreign frames (for example 4 KiB default, configurable per shim) |
| SB-10 | Threads: `pthread_create`, once supported | n/a | Each new thread gets its own `RLIMIT_STACK` budget |
| SB-11 | Signal handlers | n/a | Use an alternate stack (`sigaltstack`) of fixed, documented size |
| SB-12 | `inline` functions, once supported | n/a | Inlined frames add up at the call site |
| SB-13 | Large struct returned by value | Emit a `*T` out-parameter? | Count both the caller's slot and the callee's local |
| SB-14 | Closures, once added | n/a | The captured environment counts toward frame size |
| SB-15 | Generic function instantiated with a large `$T` | Compiles | Frame size per instantiation; reject if over budget |
| SB-16 | Indirect call through a function pointer | Compiles; target unknown statically | Budget = maximum over every function of matching type |
| SB-17 | Tail call, if added | n/a | A tail call does not grow the stack; subtract |
| SB-18 | User wants more stack | n/a | A `--stack-budget` CLI flag; a per-function attribute? |
| SB-19 | Main thread and other threads | n/a | Per-thread budget; default 1 MiB |
| SB-20 | One function calls 100 small functions in sequence (no recursion) | Compiles | Each call affects only its own frame; depth = 1 + max(callees) |

Note (2026-09-16): SB-05 — the `CLAUDE.md:114-116` pointer is stale; the
`new [N]T` rule is now at `CLAUDE.md:128-130`. That rule rejects heap
fixed arrays (`new [N]T`). It does not say whether a stack array with a
run-time length is rejected, and that case was not checked. SB-06 —
whether a Zig `defer` adds a frame was not checked; Zig runs deferred code
inline at scope exit (inference).

### Examples

Current A7 blocks use today's syntax. Compiled 2026-09-16: every block below
is accepted (exit 0).

```a7
// Current A7. SB-01, SB-02, SB-20: chain, diamond and sequential calls.
leaf :: fn() i32 {
    ret 1
}
left :: fn() i32 {
    ret leaf()
}
right :: fn() i32 {
    ret leaf() + 1
}

main :: fn() {
    total := left() + right()    // depth = main + max(left, right) + leaf
    again := leaf()              // SB-20: sequential calls do not stack
}
```

```a7
// Current A7 for SB-03, SB-04 and SB-05. Compiled 2026-09-16: the whole
// block is accepted (exit 0), including the named-constant length `[SIZE]u8`
// and the run-time length `[n]u8`. `[n]u8` is not rejected by type checking,
// even though `ArrayType.size` is an int (a7/types.py:150-153); but the
// emitted Zig is `const dynamic: [n]u8 = [_]u8{0} ** n;` while the
// parameter is emitted as `_: usize`, so `n` is unbound and the Zig build
// would fail. The acceptance is a front-end gap, not working support.
SIZE :: 256

buffers :: fn(n: usize) {
    small: [1024]u8              // SB-03
    sized: [SIZE]u8              // SB-04: named constant length (unverified)
    dynamic: [n]u8               // SB-05: run-time length (unverified)
}
```

```a7
// Current A7. SB-06, SB-07, SB-08.
io :: import "std/io"

report :: fn(code: i32) {
    defer io.println("done")     // SB-06
    match code {
        case 1: {
            wide: [512]u8        // SB-07: the larger arm sets the frame
        }
        else: {
            narrow: [16]u8
        }
    }
    a := code + 1                // SB-08: many live values
    b := a + code
    c := a + b
    io.println("{} {} {}", a, b, c)
}
```

```a7
// Current A7. SB-13, SB-15, SB-16.
Frame :: struct {
    pixels: [4096]u8
}
BinaryOp :: fn(i32, i32) i32

make :: fn() Frame {
    f: Frame
    ret f                        // SB-13: large return by value
}

hold($T) :: fn(value: $T) $T {
    copy := value                // SB-15: frame grows with $T
    ret copy
}

apply :: fn(op: BinaryOp, a: i32, b: i32) i32 {
    ret op(a, b)                 // SB-16: any fn(i32, i32) i32 may run
}
```

```a7
// Proposed. None of these forms exist in current A7.
// SB-09, SB-10, SB-11, SB-12, SB-14, SB-17, SB-19.
extern open_file :: fn(path: string) i32     // SB-09: fixed shim budget
task := spawn(worker)                        // SB-10, SB-19: per-thread budget
on_signal(SIGINT, handler)                   // SB-11: alternate stack
inline square :: fn(x: i32) i32 { ... }      // SB-12
counter := fn() { total += 1 }               // SB-14: capture counts
ret tail next_state(state)                   // SB-17
```

SB-18 is a CLI flag, not source: `a7 --stack-budget 2000000 main.a7`
(proposed; no such flag exists).

## Interactions

- **Gap 01, cast.** No interaction.
- **Gap 02, nullable pointers.** No interaction.
- **Gap 03, definite assignment.** The frame estimate must match the
  storage actually used. If DA lets some locals be elided, the estimate
  follows.
- **Gap 04, NonZero division.** No interaction.
- **Gap 06, typed arithmetic.** No interaction.
- **Gap 07, bounded indexing.** Bounded indices keep stack arrays
  statically sized, which frame estimation needs: `buf: [N]u8` works only
  with a constant `N`.
- **Gap 08, `Option<T>` and `Result<T, E>`.** Adds a tag byte (or uses a
  niche); frame accounting must include it.
- **Gap 09, refinement-lite.** Refinement types are wrappers; frame size
  equals the underlying type.
- **Gap 10, affine ownership.** No interaction at the frame-size level; it
  affects DA, not the budget.
- **Gap 11, finite floats.** No interaction.
- **Gap 12, FFI.** SB-09.
- **Recursion ban.** A required prerequisite. Without it the call graph is
  not a DAG and the analysis is undecidable. Note (2026-09-16): see G4 in
  "Current behavior".
- **Generics.** SB-15. Frame size and the budget check are per
  instantiation.
- **Imports and multiple files.** Once implemented, the call graph spans
  files, and the budget analysis needs whole-program information.

## Failure modes

### False positives

- Conservative spill estimates overstate use. A program that uses 600 KiB
  might be rejected as "1.5 MiB" by a pessimistic estimator. Mitigation:
  keep the margin small and documented; allow a per-function attribute
  that replaces the estimate (`@stack(actual=500_000)`).
- Indirect calls (SB-16): if many functions match the type, the budget is
  forced to the worst case. Reasonable for safety, but surprising.

### False negatives

- Inlining or outlining by the optimizer changes real frame sizes.
  Mitigation: estimate before optimization, or re-check after.
- An FFI shim that uses much stack internally. The fixed per-`extern fn`
  budget is an approximation; if foreign code uses more, that is a
  documented hazard.

### Ergonomic costs

- Deep call chains (parser combinators, long iterator pipelines) may hit
  the default. Mitigation: `--stack-budget` raises it; document the
  default and the override.
- A large struct returned by value (SB-13) may be re-emitted as an
  out-parameter. User code should not notice, but the generated Zig
  changes.

### Performance costs

- Compile time: the analysis is O(call-graph edges).
- Run time: the stack size is set once at thread creation, the same cost
  as today.

## Open questions

- **Q05a.** What is the default budget? 1 MiB matches most desktop
  defaults; 64 KiB is too small; 8 MiB matches the Linux default but
  wastes memory. Phase A recommendation: 1 MiB.
- **Q05b.** How is spill estimated?
  - A fixed margin per function (for example 256 bytes).
  - LLVM's register-pressure heuristic (needs post-codegen analysis).
  - Re-check after Zig compilation by reading frame info for the `.text`
    section (most accurate, most invasive).
- **Q05c.** How is a per-function override written?
  - An `@stack(max=2_000_000)` attribute on the function declaration.
  - A pragma-style annotation.
  - No override; only the global `--stack-budget` flag.
  - Note (2026-09-16): performance annotations are a deferred track
    (`docs/STATUS.md`).
- **Q05d.** How precise is the indirect-call analysis (SB-16)?
  - Strictest: maximum over all functions matching the signature.
  - Weaker: track indirect-call targets through the set of functions used
    as values; maximum over that set only.
  - Note (2026-09-16): G4 decides whether stored function values remain.
- **Q05e.** Thread stacks (SB-10, SB-19): a separate budget per thread, or
  shared with main? Separate is right; how threads declare their stacks is
  open. Note (2026-09-16): concurrency is in v1 (L1) under gate G7.
- **Q05f.** Large struct returns (SB-13). Phase A behavior was unknown.
  Proposed rule: structs above N bytes (say 256) return through a `set`
  out-parameter (Gap 03). Note (2026-09-16): `set` is not accepted syntax.
- **Q05g.** Signal-handler stacks (SB-11): fixed size, configurable,
  documented?
- **Q05h.** What does the diagnostic show when a program exceeds the
  budget? Just an error, or a per-function breakdown of the cumulative
  budget along the worst path?

## Source citations

- Recursion-ban code to reuse: `a7/passes/semantic_validator.py:501-544`,
  `_validate_no_recursion` and `_find_recursion_path`. The call-graph code
  at lines 546–589 (`_collect_function_calls`) is the input for a budget
  pass. Both still hold on 2026-09-16.
- No stack-size analysis exists; greenfield.
- The backend emits no stack-size annotation.
- `main` entry in emitted Zig: `build/debug/zig/src/001_hello.zig` shows
  the Zig 0.16 `std.process.Init` entry wrapper with no explicit stack
  size. The same wrapper appears in `build/debug/zig/src/002_var.zig:9-12`
  (read 2026-09-16).

## Phase C decision inputs

1. Q05a, default budget. Drives user experience.
2. Q05b, spill estimation. Drives accuracy against effort.
3. Q05c, per-function override. Drives ergonomics.
4. Q05d, indirect-call precision.
5. Q05f, large struct return policy.
6. Q05h, diagnostic shape.

The other questions follow.
