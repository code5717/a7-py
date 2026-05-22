---
title: Status
nav: Status
group: Project
summary: Current implementation state, active priorities, and deferred work.
order: 5
---

# Status

A7 is pre-1.0. The compiler is usable for the checked example suite, but the
language and stdlib are still intentionally small. The authoritative status
document is `docs/STATUS.md`.

## Current surface

- Zig is the only supported public backend
- Source recursion is rejected at compile time
- The example suite is verified against golden output fixtures
- Static docs site with raw markdown and agent corpus files

## Active priorities

- Multi-file A7 source support with single-file Zig output
- Generic specialization before broad cross-module generic workflows
- Clearer status reporting for parsed-only language features
- Practical stdlib additions starting with deterministic random helpers

## Known gaps

- File-backed imports, `using import`, and broad cross-module type checking
  remain follow-up work
- Fixed-width overflow, union discriminant access, and full ref/del alias
  behavior are incomplete
- Multiple return value destructuring, tagged union tag workflows, and
  variadic runtime lowering are not current backend features
- `Option`, `Result`, collections, and fuller string/memory helpers are
  planned stdlib work

## Deferred

- Package registry
- File and network IO in the stdlib
- Concurrency primitives
- Full language server
- Runtime sandboxing

If a feature is listed here as deferred, do not write public examples that rely
on it as if it is complete.

For release gates and deploy checks, see [Release](/a7-py/release/).
