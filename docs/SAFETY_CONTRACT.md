# A7 Compiler Safety Contract

This document states the compiler's safety requirements. It is not a guarantee
that every accepted program is safe. The compiler must reject a risky operation
when it cannot prove the required condition before emitting Zig. Current gaps
include alias and lifetime analysis.

Two audits reproduced accepted programs that trapped. The safety pass now
joins facts at branches, after loops (a loop may run zero times) and at
every exit of a block that holds a `defer`; it keys facts by declaration;
and a call to a non-stdlib function forgets facts about file-scope
variables. Passing the regression cases does not prove the contract for
every program.

This contract covers compiler safety, not sandboxing. A compiled A7 program can
still access whatever the host process and Zig toolchain allow.

## Pipeline Ownership

The frontend stages have separate responsibilities:

1. **Type checking** resolves base types, symbols, signatures, and literal
   values. It does not decide whether a risky operation is safe.
2. **Semantic validation** rejects illegal source constructs such as recursion,
   invalid `del`, unsupported imports, and non-runnable syntax.
3. **Safety proof analysis** tracks internal facts and collects obligations for
   risky operations.
4. **Proof discharge** either proves an obligation or emits a compile-time
   diagnostic.
5. **Backend planning** records the exact approved lowering for codegen.
6. **Zig codegen** consumes the `BackendPlan`; it must not independently accept
   an unsafe lowering.

## Internal Facts

Facts are internal compiler data, not public language types. The safety pass may
track:

- integer intervals and non-zero values
- known array, slice, and string lengths
- nil/non-nil reference state
- initialized, moved, and deleted bindings
- allocation identities shared by direct reference aliases and tracked fields
- enum or union discriminants
- operation-specific backend approvals

Facts can be learned from literals, type information, guards, early returns,
loop shapes, and previous statements. If a fact is invalidated or unknown, the
compiler must reject the dependent operation. The implementation uses
conservative invalidation across mutations and calls; this can require an
additional guard inside a loop or after a call.

## Risky Operations

| Operation | Required proof | Backend approval |
| --- | --- | --- |
| Numeric cast | primitive cast is classified and range-safe | `cast` |
| Division or modulo | divisor is non-zero | `div`, `mod`, `div_assign`, `mod_assign` |
| Indexing | index is `usize` or a non-negative literal, and `0 <= index < len` | `index` |
| Slicing | `0 <= start <= end <= len` | `slice` |
| Ref field access or dereference | reference is proven non-nil | `deref` |
| Assignment through ref | target reference is proven non-nil | `deref` |
| Use after `del` | the referenced allocation has not been deleted | semantic rejection |
| Integer `+`, `-`, `*` and compound forms | defined wrapping lowering | no overflow proof required |
| Union payload access | active discriminant is proven | union approval |

The current implementation enforces cast, division/modulo, index, slice, ref
deref, operation-specific backend approvals, and deletion checks for direct
reference aliases and tracked fields. Array-element aliases and fields reached
through joined allocation sets remain gaps. The reviewed callee summaries also
missed deletion through borrowed aggregates and retained stale allocation
identity after field replacement. They rejected valid parent/sibling uses after
child-only deletion and parent use after an unrelated local allocation was
deleted. See [Status](STATUS.md) for the recorded findings.

A bounded ordered-callee-effect candidate addresses direct, local-alias and
forwarded reference field replacement/deletion, with at most one conditional
across the known call expansion, source-sized expanded work, block/return exits
and LIFO defers. It passes focused checks but awaits combined-source qualification; these findings are not closed by earlier passing controls.
Multiple conditional occurrences, loops, match, new allocations, returned
references, by-value aggregate parameters/copies, global storage, short-circuit
expressions, unknown callees and unrepresented standard-library effects remain
incomplete. Selected reference arguments or descendant facts with multiple
allocation identities retain the older summaries, whose missed aliases and
conservative rejections remain unresolved. These checks do not establish
complete allocation lifetime safety.
A run-time shift count is checked when the program runs, in every profile.
Signed `MIN / -1`, `-MIN` and `abs(MIN)` have defined wrapping results. Union
discriminant proofs and complete ownership analysis remain active work.

## Reference Surface

Public address and dereference syntax is intentionally absent. Users do not
write `.adr`, `.val`, prefix `&`, prefix `*`, or public borrow/mutate/consume
modes. Ref arguments are passed as ordinary lvalues, and ref struct fields are
accessed directly after nil-proofing.

Today `ref T` remains the nullable heap-reference surface accepted by examples.
The planned split is:

- `ref T`: proven non-null reference
- optional `ref T`: maybe-null reference
- `nil`: assignable only to optional refs
- `new T`: returns an optional ref

Until that split lands, the safety pass treats `new` and `nil` references as
maybe nil and requires proof before field access or dereference.

## Ownership Surface

The current public model stays simple:

- value types copy by value
- heap refs created by `new` must be cleaned up with `del` or `defer del`
- direct use after `del` is a compile-time error
- assignment after `del` reinitializes the binding
- implicit deep copy is not provided

An earlier proposal made public heap refs affine and added explicit `clone`.
The current [memory plan](plan/memory.md) instead proposes automatic memory
management under ledger decisions L15-L21. Its details still require approval;
neither proposal describes implemented ownership guarantees.

## Backend Rule

Codegen must call `BackendPlan.require(node, operation)` before lowering any
approved risky operation. Approval is operation-specific: a node approved for
`index` is not approved for `cast`, `deref`, or any other lowering. Missing or
wrong approvals are compiler bugs and must fail codegen.
