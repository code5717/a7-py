---
title: Status
nav: Status
group: Project
summary: Current implementation state, active priorities, and deferred work.
order: 5
---

# Status

A7 is pre-1.0. The compiler is usable for the checked example suite, but the
language and stdlib are still intentionally small.

## Completed baseline

- Python package layout under `a7/`.
- CLI wrapper through `uv run a7`.
- Zig 0.16 toolchain pin in CI.
- Recursive A7 source rejection.
- Iterative compiler traversal policy.
- Debug and release example artifact builders.
- Static docs site with raw markdown and agent corpus files.

## Active priorities

- Multi-file A7 source support with single-file Zig output.
- A practical stdlib plan starting with deterministic random helpers.
- Better cross-module generic specialization.
- Clearer status reporting for parsed-only language features.
- Smaller docs with less duplication.

## Deferred

- Package registry.
- File and network IO in the stdlib.
- Concurrency primitives.
- Full language server.
- Runtime sandboxing.

If a feature is listed here as deferred, do not write public examples that rely
on it as if it is complete.
