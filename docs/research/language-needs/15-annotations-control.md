# 15 — Annotations and control surface

Status: research only. Nothing below is approved syntax.
Verified against `a7/` on 2026-10-02: no attribute/annotation syntax, no
conditional-compilation primitive, no doc-comment extraction, no match guards,
no atomics, no async syntax, no stack traces. `panic :: fn(msg: string)` exists
as a stdlib stub (`docs/SPEC.md:1730`); `@`-builtins cover `@size_of` /
`@align_of` / `@type_id` / `@type_name` / `@unreachable()` (`a7/parser.py:1645`).

## 1. Conditional compilation (target_os / target_arch)

Today: nothing. No `cfg`, `version`, `static if`, or builtin OS query.

How others do it: Rust `#[cfg(target_os = "linux")]`; D `version(linux)` /
`static if`; Zig `builtin.os.tag == .linux` (comptime, no special syntax);
Odin `when ODIN_OS == .Linux`; C++ `#ifdef __linux__`.

Proposal: comptime-evaluable builtin, not a new directive. Reuse the `@`
builtin namespace already in the parser:

```a7
main :: fn() {
    if @target_os() == "linux" { epoll_init(); } else { poll_init(); }
}
```

The condition must be a comptime constant; dead branch is discarded before
codegen. No `#ifdef` textual inclusion, no separate `cfg` mini-language.
Verdict: **later**. Needed before first platform-specific stdlib code, not
before core language work. Depends on const-eval rules (file 05).

## 2. Attributes / annotations syntax

Today: nothing. No `#[...]`, `@(...)`, or pragma. Layout words such as
`packed`/`align` appear only inside type syntax where the grammar fixes them.

How others do it: Rust `#[inline]`, `#[derive]`; C++ `[[nodiscard]]`,
`[[likely]]`; D `@safe`, `@nogc`, UDAs `@("x")`; Zig folds most of this into
calling conventions and builtins instead of a general attribute; Odin uses
`@(foreign)`, `#force_inline`, `#packed` directives.

Proposal: one prefix form in the existing `@` namespace, attached to
declarations, restricted to a closed allowlist:

```a7
@(inline_hint)
fast_add :: fn(a: i32, b: i32) -> i32 { ret a + b; }

@(packed)
Header :: struct { flags: u8; kind: u8; }
```

Unknown attributes are compile errors, not warnings. No user-definable
attributes, no derive macros. New attributes each need their own approval.
Verdict: **later**. Ship `inline_hint` and `packed` only when codegen needs
them; the general mechanism is not needed now.

## 3. Doc comments + extraction

Today: nothing. `//` comments exist; no `///` convention, no doc tool.
Rust `///` + rustdoc; D `///` + ddoc; Zig `///` + `zig std`; C++ Doxygen.

Proposal: `///` on the line(s) directly above an item is a doc comment;
`//` stays undocumented. A `a7 doc` subcommand renders Markdown. No markup
DSL beyond code fences and `[links]`:

```a7
/// Adds two counters. Wraps on overflow.
add :: fn(a: i32, b: i32) -> i32 { ret a +% b; }
```

Verdict: **later**. Zero language risk, pure tooling. Do it when stdlib is
large enough to need generated docs.

## 4. Match pattern guards

Today: patterns plus `else`; no `if` guard on a case. Overlapping ranges need
nested `if` inside the case body.

How others do it: Rust `Some(x) if x > 0 =>`; D has no guards (nested `if`
or `case` fallthrough); Zig `=> |cap| if (cond)` capture-guard on
`switch`; Odin `case x if cond:`; C++ n/a (no pattern matching pre-C++26
inspection proposal, which includes guards).

Proposal: optional `if` after the pattern, evaluated after a successful match
with bindings in scope; first matching pattern+guard wins:

```a7
match kind {
    RED if count > 10 => { bulk_red(); }
    RED => { small_red(); }
    else => { other(); }
}
```

Guard must be side-effect free (same rule set as comptime/pure contexts in
file 05). Verdict: **need now** (small, composes with the match work in
file 02). Guard evaluation order is top-down; overlapping-guard diagnostics
stay warnings, not errors.

## 5. Atomics + memory ordering

Today: nothing. No atomic types, no ordering enum, no fence. Shared-memory
code cannot be written correctly.

How others do it: Rust `AtomicU32` + `Ordering::{Relaxed, Acquire, Release,
AcqRel, SeqCst}`; C++ `std::atomic` + `memory_order_*`; D `core.atomic`
(`atomicLoad`, `cas`, `MemoryOrder`); Zig `@atomicLoad`/`@atomicStore`/
`@cmpxchgWeak` + `.acquire`/`.release`/`.seq_cst`; Odin `intrinsics`
`atomic_*` with default sequential consistency.

Proposal: library types over compiler intrinsics, Zig-style. Ordering is an
explicit argument, default `seq_cst` so the safe choice is the shortest:

```a7
c: AtomicU32 = atomic_make(0);
atomic_store(mut c, 1, order_release());
v: u32 = atomic_load(c, order_acquire());
```

No `volatile`-as-atomic pun. Verdict:
**later**, with the concurrency track (file 09).

## 6. Async model: syntax vs library vs out-of-scope

Today: no syntax, no runtime. `defer` exists; threads/tasks do not (file 09).

How others do it: Rust `async fn` + `.await` with a third-party executor
(colored functions, ecosystem split); C++20 coroutines (`co_await`,
customizable but notoriously hard); Zig removed `async`/`await` keywords in
0.15 and routes concurrency through the `std.Io` interface parameter with
`io.async()` futures (no function coloring); Odin has no async syntax,
uses threads + `core:sync`; D has fibers in stdlib, no syntax.

Proposal: **library, never syntax**. No `async`/`await` keywords, no colored
functions. When the concurrency track lands, blocking operations take an
explicit context parameter (Zig `Io`-style) and a task API returns joinable
handles. Sequential code keeps working unchanged. Verdict: **never** for
syntax; library design belongs to file 09 and is post-V1. Do not reserve the
words `async`/`await` in the grammar.

## 7. Error stack traces + panic-vs-error boundary

Today: `panic :: fn(msg: string)` stub; no backtrace, no `catch`/`try`
syntax in A7 source (only Zig-emit `catch @panic` inside generated glue).
Recoverable errors are return values; the boundary is unwritten.

How others do it: Rust `panic!` (unwind/abort, backtrace with symbols) vs
`Result` (typed, must-handle); Zig `panic` handler hook + `error` unions
with optional `error_return_trace`; Odin `panic` + optional `or_return`
sugar; D `Exception` (stack `TraceInfo`) vs `Error` (unrecoverable); C++
exceptions with `std::stacktrace` (C++23) as a separate opt-in library.

Proposal: keep two disjoint paths. Recoverable errors are values with
explicit handling (file 02 decides the exact form). `panic` is unrecoverable,
aborts the program, and prints a trace only in debug builds:

```a7
panic("unreachable branch");          // aborts, debug-only backtrace
res: i32 = must(parse_count(s));      // recoverable path, explicit
```

No `try`/`catch` exceptions, no trace objects attached to every error value
(trace capture cost belongs to debug tooling, not the error type). Verdict:
**later**. Define the boundary now (values vs abort), build backtraces with
the debug-info track, post-V1.

## Verdict table

| Item | Verdict |
| --- | --- |
| Conditional compilation | later (with first platform stdlib) |
| Attributes | later (closed allowlist, per-item approval) |
| Doc comments | later (tooling, no language risk) |
| Match guards | now (small, with file 02 match work) |
| Atomics | later (with file 09, copy Rust/C++ semantics) |
| Async syntax | never; async library post-V1 under file 09 |
| Panic/error boundary | boundary now, backtraces later |
