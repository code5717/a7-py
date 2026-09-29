---
title: Implementation status
nav: Status
group: Project
summary: Current support, known compiler gaps, and planned work.
order: 40
---

# Implementation status

A7 is experimental and pre-1.0. The example suite checks selected programs
against golden outputs. Passing that suite does not establish full specification
support or complete safety. The repository's
[status document](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
is the current implementation authority.

## Current surface

| Area | Status | Qualification |
| --- | --- | --- |
| Zig source emission | supported | Only public backend; targets Zig 0.16.0. |
| Primitive values, functions, loops, structs | supported | See the reference and runnable examples for restrictions. |
| References and explicit allocation | limited | Nil checks and direct use-after-delete checks exist; alias and lifetime guarantees remain incomplete. |
| Generic functions and structs | limited | Simple top-level specialization works; call-chain propagation is incomplete. |
| File modules | limited | Simple aliased imports emit one combined Zig file. |
| Fixed arrays and slices | limited | Bounds checking exists; heap fixed-array allocation is rejected. |
| `std/io` and `std/math` | limited | Registered calls only; see exact signatures and restrictions. |
| Source recursion | unavailable | Rejected by semantic validation; use iterative algorithms. |

Constant floating remainder follows the runtime truncation rule, including the
dividend sign and negative zero. Diagnostics retain imported module locations.
Output paths cannot overwrite input modules; artifact reports exclude stale files.

## Active priorities

- Keep current counts script-derived with `uv run python scripts/project_status.py`.
- Complete practical multi-file support while retaining one combined Zig output.
- Resolve numeric decisions before changing arithmetic or casts.
- Split safety internals into control-flow, facts, obligations, proof discharge, and backend planning.
- Complete generic specialization and call-chain propagation.
- Maintain installed `a7 check`, `a7 build`, `a7 run`, `a7 doctor`, and `a7 --version` checks. Wheel and source-distribution workflows pass on Linux x86-64.
- Convert remaining recursive compiler internals to explicit stacks and worklists.

The source recursion ban and the compiler-internals conversion are separate
requirements. Neither makes the other complete.

## Known gaps

- Safety remains incomplete. Current probes still accept field-name confusion,
  fallthrough division, stale global facts after calls and repeated field deletion.
- A low-recursion test passes through the pytest entry point but fails through
  `python -m pytest`. Full compiler traversal still needs conversion.
- Forward-global typing awaits compatibility approval because the fix rejects
  a float-to-integer assignment that currently builds.

- A labeled loop whose label is never targeted can emit an unused Zig label and
  fail the native build.

- Local constant usage is not tracked by declaration identity. Sibling-scope name
  collisions and nested constant shadowing can still emit invalid Zig.

| Topic | Current restriction | Reference |
| --- | --- | --- |
| Modules | Selected imports, `using import`, broad cross-module typing, and generic module workflows remain incomplete. | [Modules](/a7-py/docs/language/modules.md) |
| Numeric operations | Integer addition, subtraction, and multiplication wrap. Shifts and other numeric edge cases need further qualification. | [Operators](/a7-py/docs/language/operators.md) |
| Unions | Tag and discriminant workflows are not implemented. | [Aggregate types](/a7-py/docs/language/aggregate-types.md) |
| Memory | Full `ref`/`del` alias behavior and ownership/lifetime guarantees remain incomplete. | [Memory](/a7-py/docs/language/memory.md) |
| Generics | Arbitrary specialization propagation is incomplete. | [Generics](/a7-py/docs/language/generics.md) |
| Functions | Multiple returns, destructuring, and user-defined variadic runtime lowering are unavailable. | [Functions](/a7-py/docs/language/functions.md) |
| Standard library | No `Option`, `Result`, collections, or full memory/string library. | [Standard library](/a7-py/docs/stdlib.md) |

Focused native probes verify escaped IO braces and ordinary signed `math.abs`
results after repairs. The minimum signed `abs` input remains an unsafe edge case.
Scalar-filled fixed arrays and direct `string.len` are rejected. A top-level
local `@type_set` alias can pass semantic checking but fail code generation.
See [stdlib](/a7-py/docs/stdlib.md), [arrays](/a7-py/docs/language/arrays-strings.md),
[generics](/a7-py/docs/language/generics.md), and
[recorded checks](https://github.com/code5717/a7-py/blob/master/site/docs/content-verification.md).

## Planned work

Core V1 includes automatic memory, useful libraries and installed tooling. The
Python compiler remains the V1 implementation; Zig handles generated code and
future runtime/native integration. V2 aims to implement the compiler in A7.

AI, concurrency, multicore and GPU execution remain design constraints and later
qualification tracks. Runtime memory help is allowed, but no memory mechanism is
selected or implemented. See the
[delivery roadmap](https://github.com/code5717/a7-py/blob/master/docs/plan/delivery-roadmap.md).
A package registry remains outside the current scope.

## Not currently available

There is no package registry, full language server, runtime sandbox, file I/O
stdlib, or network I/O stdlib. Compiler acceptance alone is not evidence that a
program can build or run through Zig.

## Interpreting evidence

Reference labels distinguish supported, limited, unavailable, planned, and
unverified behavior. Evidence links point to implementation, tests, fixtures,
or explicit status records. A source revision identifies a checkout; it is not
a correctness certificate. See the
[audit index](https://github.com/code5717/a7-py/blob/master/docs/audits/README.md)
for dated investigations, and [Release](/a7-py/docs/release.md) for required gates.
