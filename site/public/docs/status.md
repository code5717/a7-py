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
| References and explicit allocation | limited | Nil guards, tracked field deletion and direct alias deletion checks exist; complete lifetime guarantees remain unavailable. |
| Generic functions and structs | limited | Simple top-level specialization works; call-chain propagation is incomplete. |
| File modules | limited | Separate file scopes, qualified declarations and underscore privacy emit one combined Zig file; import aliases stay local. |
| Fixed arrays and slices | limited | Bounds checking exists; heap fixed-array allocation is rejected. |
| `std/io` and `std/math` | limited | Registered calls only; see exact signatures and restrictions. |
| Source recursion | unavailable | Rejected by semantic validation; use iterative algorithms. |

Constant floating remainder follows the runtime truncation rule, including the
dividend sign and negative zero. Diagnostics retain imported module locations.
Output paths cannot overwrite input modules; artifact reports exclude stale files.

## Work and verification

The [repository status](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
and [delivery roadmap](https://github.com/code5717/a7-py/blob/master/docs/plan/delivery-roadmap.md)
hold the current work list. Compiler AST traversals use explicit worklists;
the recursion exception list is empty. Deep pipeline tests run at Python
recursion limit 100. A7 source recursion remains a separate rejected construct.

## Known gaps

- Safety remains incomplete for aliases through array elements and selected
  fields, loop field-argument deletion and unsupported callee effects. A bounded
  exact-callee repair covers represented field replacement/deletion paths.
  Direct global reference stores now propagate allocation identity. Global nil
  state and callee non-nil requirements remain incomplete; these checks do not
  establish full lifetime safety.

- A labeled loop whose label is never targeted no longer emits a label: the
  fix landed with commit `ed0baff`, and the never-targeted case is pinned in
  both profiles by the `unused-labels` case in
  `test/test_resume_backend_bindings.py`.

- Local constants use declaration identity. Sibling-scope collisions and nested
  shadowing are covered by native regression tests.

| Topic | Current restriction | Reference |
| --- | --- | --- |
| Modules | Selected imports and `using import` remain unavailable. File scopes and qualified struct literals work. Parsed import forwarding rejects with exit 6; unsupported multi-dot type/literal syntax keeps parser exit 5. | [Modules](/a7-py/docs/language/modules.md) |
| Numeric operations | Integer addition, subtraction and multiplication wrap. Runtime shifts are checked; signed minimum-value division, negation and absolute value wrap. | [Operators](/a7-py/docs/language/operators.md) |
| Unions | Tagged-union payload matching works. Complete discriminant proofs remain unfinished. | [Aggregate types](/a7-py/docs/language/aggregate-types.md) |
| Memory | Full `ref`/`del` alias behavior and ownership/lifetime guarantees remain incomplete. | [Memory](/a7-py/docs/language/memory.md) |
| Generics | Concrete initializers, nested array arms and qualifying immutable local aliases are checked. Imported, module-global, parameter, mutable, selected and captured generic origins remain incomplete. | [Generics](/a7-py/docs/language/generics.md) |
| Functions | Multiple returns, destructuring, and user-defined variadic runtime lowering are unavailable. | [Functions](/a7-py/docs/language/functions.md) |
| Standard library | Prelude `Option`/`Result` and typed I/O are available. Collections and a full memory/string library remain incomplete. | [Standard library](/a7-py/docs/stdlib.md) |

Focused native probes verify escaped IO braces and ordinary signed `math.abs`
results after repairs. `math.abs` of the minimum signed value wraps to that
value in every profile. Scalar-filled fixed arrays and direct `string.len` are
rejected.
See [stdlib](/a7-py/docs/stdlib.md), [arrays](/a7-py/docs/language/arrays-strings.md),
[generics](/a7-py/docs/language/generics.md), and
[recorded checks](https://github.com/code5717/a7-py/blob/master/site/docs/content-verification.md).

## Planned work

V1 publication requires core language and automatic memory, useful libraries
and installed tooling, structured concurrency, CPU AI, actual GPU execution,
and an A7 compiler that establishes self-hosting parity (decision L73).
The Python compiler remains the bootstrap until parity justifies replacement;
Zig handles generated code and runtime/native integration.

GPU implementation and the proposed local Vulkan experiment remain deferred
for Zig GPU research under L75. That deferral does not waive V1's GPU
qualification requirement. No GPU backend or automatic-memory mechanism is
selected by these decisions. See the
[delivery roadmap](https://github.com/code5717/a7-py/blob/master/docs/plan/delivery-roadmap.md)
and [decision ledger](https://github.com/code5717/a7-py/blob/master/docs/plan/decisions.md).
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
