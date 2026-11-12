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

Exact evaluation enforces growth, work, logical retention, exact binding-depth
and diagnostic limits. Generic pattern conversions share those accounts. C11
emission qualification remains open, and math-call output is unchanged. Injected
limits and default C3/C5 witnesses cover different accounting boundaries; neither
alone qualifies the full policy. See the [specification limits](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md#appendix-c-implementation-limits).

## Current surface

Integer literal/range overlap checks preserve fitted integer precision beyond
2^53 in either pattern order. Generic numeric patterns fit concrete subject
types before overlap checks and preserve named exact constants. Runtime ranges
require numeric or character subjects. General runtime generic dispatch remains
unimplemented. Struct and union constraints also apply to type annotations,
including unused signatures, fields and aliases. Forward type-set members resolve
after named aliases in the owner's file. Broader generic propagation remains
incomplete.

| Area | Status | Qualification |
| --- | --- | --- |
| Zig source emission | supported | Only public backend; targets Zig 0.16.0. |
| Primitive values, functions, loops, structs | supported | See the reference and runnable examples for restrictions. |
| References and explicit allocation | limited | Nil guards, tracked fields, direct aliases and exact literal-index fixed-array aliases have bounded checks; complete lifetime guarantees remain unavailable. |
| Generic functions and structs | limited | Simple top-level specialization works; call-chain propagation is incomplete. |
| File modules | limited | Separate file scopes, qualified declarations and underscore privacy emit one combined Zig file; import aliases stay local. |
| Fixed arrays and slices | limited | Bounds checking exists; heap fixed-array allocation is rejected. |
| `std/io` and `std/math` | limited | Registered calls only; see exact signatures and restrictions. |
| Source recursion | unavailable | Rejected by semantic validation; use iterative algorithms. |

Constant floating remainder follows the runtime truncation rule, including the
dividend sign and negative zero. Diagnostics retain imported module locations.
Output paths cannot overwrite input modules; artifact reports exclude stale files.

Else-if arms preserve separate declaration scopes and parent bindings after
shadowing. Overlong module paths report the import location and filesystem
failure at resolution exit 3.

The benchmark `--gate` requires a positive finite timing and a nonempty output
hash for every workload in the host pin. Missing or unusable baselines exit 1.
Combining `--pin` and `--gate` exits 2 before building or updating pins. Default
report-only runs describe timing threshold violations without failing for timing
alone; output hash mismatches still fail.

Reference-to-fixed-array indexing supports primitive element reads and simple
or compound writes when bounds and non-nil requirements are proven. Guarded nil
calls and borrowed-array calls remain valid. Unresolved nil-call conditions,
effectful indices, selected reference-array fields, mutable or captured callable
origins, ref slicing and general reference-element ownership remain incomplete.

Resolved functions whose body contains one Boolean-literal return supply indexed
guard facts. This covers direct and forwarded calls and stable unwritten,
uncaptured local aliases. The checker preserves call and argument evaluation;
indexed uses retain optional-reference unwraps. Conditional, effectful and
deferred helpers remain unknown.

Eligible local Boolean cells and value parameters supply indexed guard facts
from bare or negated conditions and comparisons with Boolean literals. Early
returns retain the surviving branch fact; copies retain their evaluated value.
Captured or reference-exposed cells, fields and globals are excluded. Assignments
replace facts; joins require matching values. Loop write invalidation also
clears affected Boolean facts.
True or unknown guards with nil reject at semantic exit 6. An unguarded symbolic
`read(nil, b)` wrapper still rejects even if its only caller passes false.
These facts do not certify purity or complete effect modeling.

## Work and verification

The [repository status](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md)
and [delivery roadmap](https://github.com/code5717/a7-py/blob/master/docs/plan/delivery-roadmap.md)
hold the current work list. Compiler AST traversals use explicit worklists;
the recursion exception list is empty. Deep pipeline tests run at Python
recursion limit 100. A7 source recursion remains a separate rejected construct.

## Known gaps

The readonly executable-entry check passed the repaired full release gate and
12 valid native build/run controls on the recorded source snapshot. It evaluates
only a complete summary of the original parameterless entry declaration and
adds semantic exit 6 for a proved reachable nil read. Library mode has no
implicit execution root. Effectful entries and general caller-local truth remain
incomplete. See the [qualification record](https://github.com/code5717/a7-py/blob/master/docs/audits/2026-10-07/readonly-entry-verification.json)
for the first failed test-hook integration, its repair and the bounded native
controls. This does not qualify full safety or V1.

- Literal-index fixed-array aliases retain known allocation identity on tracked
  straight-line paths. Independent array copies and fresh slot replacements
  preserve valid uses. General array/slice and selected-field identities,
  loop field-argument deletion and unsupported callee effects remain incomplete.
  A bounded exact-callee repair covers represented field replacement/deletion paths.
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
| Generics | Concrete initializers, substituted fixed-array elements, concrete wrappers and qualifying immutable local aliases are checked. Imported, module-global, parameter, mutable, selected and captured generic origins remain incomplete. | [Generics](/a7-py/docs/language/generics.md) |
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
