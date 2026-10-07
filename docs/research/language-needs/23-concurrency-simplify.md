# 23 — Concurrency simplify: the smallest honest story

Status: research only. Nothing below is approved syntax.
Builds on file 09 (concurrency/tensors constraint) and file 15 sections 5-6
(atomics library, async never-syntax). Goal: cut, not add.

## 1. Answer up front

V1 ships zero concurrency syntax. No `go`, no `spawn`, no `async`/`await`,
no channel, group, join, close, or cancel keyword. Sequential semantics only.
This is honest if three things hold: the docs say so, the IR records effects,
and float/order rules stay strict.

File 09 already says this (L36/L40): unknown effects stay sequential,
parallelism is inferred only where safe, strict float order by default.
File 15 already says async syntax is never. This file extends that verdict
to everything else: no single concurrency primitive is V1-required.

## 2. Why zero syntax is not a lie

A language lies about concurrency when sequential-looking code runs in
parallel without a stated rule. V1 avoids that by stating the rule: nothing
runs in parallel. Every statement executes in program order. There is no
background execution, no reordering of observable effects.

What V1 must still do (all non-syntax work):

- Typed IR records read/write effects and storage identity (file 09 step 1).
- Unknown dependencies stay sequential (L40). No inference without proof.
- Strict float order; a changed reduction order needs an explicit contract.
- Explicit-copy list semantics (L42) so later task homes have a sound base.
- Checked synchronous Zig bindings only (L41). No async bridge yet.

This is the same trick pure-functional array systems use: JAX and TinyGrad
get parallelism for free later because user code is already value-oriented.
A7 gets there by keeping V1 sequential and effect-annotated.

## 3. What each reference language refused

| Language | Kept minimal | Refused to put in the language |
| --- | --- | --- |
| Go | `go` + channel + `select` only | Structured join, cancellation, effect system. Cancel is library (`context`). No async coloring. Close ownership left to convention, and it shows. |
| Zig | Nothing since 0.15: `async`/`await` keywords removed | Function coloring entirely. Concurrency goes through the `std.Io` interface parameter with `io.async()` futures. Blocking ops take `io` explicitly. |
| Odin | Nothing: threads + `core:sync` library | Green threads, coroutines, async syntax of any kind. No channel type in the language. |
| D | Nothing in syntax: fibers in stdlib (`core.thread.Fiber`) | `async`/`await` keywords, task syntax, channel syntax. `core.atomic` is library over intrinsics. |
| C (C11) | `_Atomic` + memory orders only (and that was late) | Threads are library (`thrd_create`, pthreads before that). No task, channel, join, or cancel construct. |

Pattern: every language that stayed maintainable pushed task lifetime,
cancellation, and channels outward — into library, interface parameters,
or explicit context values. None put join-with-error-reporting or
close-ownership in grammar. A7 should copy the refusal, not just the feature.

## 4. The G7 questions dissolve without syntax

File 09 lists three open G7 questions. With no V1 syntax, none needs an
answer now:

- Sibling cancellation on failure: no siblings exist yet. Decide with the library.
- Join outcome shape (value/error/cancelled): no join yet. Decide with the library.
- Explicit `close`: no channels yet. Decide with the library.

The only V1 decision is negative: do not reserve `async`/`await`/`go`/
`spawn`/`yield` as keywords (file 15 already says this for async/await).
Keep the namespace free so the library track is not boxed in.

## 5. Verdict lists

KEEP (V1, no syntax):

- Sequential execution semantics, stated in SPEC.
- IR effect recording (reads, writes, storage identity).
- Strict program order + strict float order.
- Explicit-copy value semantics for lists.
- Synchronous checked Zig native bridge.

CUT (never language syntax):

- `async`/`await`, colored functions, `co_await`.
- `go`/`spawn` statements, structured-task blocks.
- Channel/group/join/close/cancel keywords or operators.
- Atomic types as syntax, ordering as syntax, fences as statements.
- Device placement or target annotations for concurrency.

LIBRARY (post-V1, under file 09 track):

- Task groups with join handles and failure/cancel policy.
- Channels with documented close ownership (sender closes, double close errors).
- Cooperative cancellation contexts (Go-context or Kotlin-scope style).
- `AtomicU32`-style types over intrinsics, default `seq_cst` (file 15 section 5).
- Mutex, condition variable, thread pool, fiber scheduler, executor.
- Tensor-parallel and autodiff-parallel runtimes, built on the above.
