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
- allocation identities shared by direct aliases, tracked fields and tracked
  literal-index fixed-array elements on straight-line paths
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

Reference-to-fixed-array indexing requires separate `index` and `deref`
approvals for the same access. The declared array length supplies the bound;
a guarded or borrowed non-nil reference supplies the dereference proof. Primitive
element writes retain caller-visible mutation. Indexed call summaries describe
access requirements, not purity or complete effect replay. An unresolved indexed
call requirement is rejected even when a summary exists, including in library
mode. Existing incomplete ordinary-field summaries keep their prior scope.

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

Unresolved nil-call conditions, effectful indices, selected reference-array
fields, mutable or captured callable origins, ref slicing and general
reference-element ownership remain incomplete.

The current implementation enforces cast, division/modulo, index, slice, ref
deref, operation-specific backend approvals, and deletion checks for direct
reference aliases, tracked fields and exact literal-index fixed-array reference
elements. These slot facts retain allocation identity through reference and array
copies and represented conditional paths. Replacing a slot does not retarget a
saved reference. Represented replacement and cleanup paths preserve known
allocation identity; accesses to known deleted allocations still reject.
Bounded dynamic-index stores on those arrays join or invalidate possibly-affected
element facts. Stores through a selected multi-allocation holder join old and new
candidate field facts; heap-field sync updates selected binding paths that share
storage, not independent by-value struct copies that only hold the same
reference. Joined-allocation nil-writes invalidate overlapping selected paths.
Unrepresented joins and loop effects do not gain general lifetime proofs.
Unknown writes, views and mutable array borrows prevent stale exact slot identities from causing
new rejections. Broader container identity (slices, correlated selections)
remains gated on
[P-REF-container-identities](plan/packets/P-REF-container-identities.md).
Earlier reviewed callee summaries
missed deletion through borrowed aggregates and retained stale allocation
identity after field replacement. They rejected valid parent/sibling uses after
child-only deletion and parent use after an unrelated local allocation was
deleted. These are historical findings; the represented repairs below do not
resolve every aggregate or joined-field case. See [Status](STATUS.md) for the
remaining findings.

Eligible loop counters retain facts across proved readonly calls, represented
returned-reference forwarding and writes to distinct owned storage. Reassigning
a reference alias changes the effects of later uses without changing references
already captured for earlier arguments or returns. Deferred statements retain
their established last-in, first-out behavior. This describes represented safety
analysis; it does not select a new callable-versus-argument evaluation order.

Primitive field and index lvalues passed to reference parameters publish writes
to their storage. The analysis distinguishes replacing an owned local slot from
mutating storage reached through that slot. Only proved slot-only effects retain
local-slot precision across handle calls; reachable slice or reference backing
may still alias other storage. Unknown calls, escaped storage and unsupported
projections remain conservative. These bounded repairs preserve the valid and
unsafe controls approved in [L74](plan/decisions.md); they do not supply general
lifetime safety or select automatic memory management.

The bounded ordered-callee-effect repair addresses direct, local-alias and
forwarded reference field replacement/deletion, with at most one conditional
across the known call expansion, source-sized expanded work, block/return exits
and LIFO defers. It passed the earlier integration gate. That qualification
applies to those represented paths. The later loop and returned-reference
precision described above extends only its stated subset. General combinations
of multiple conditionals, loops, match, new allocations, returned references,
by-value aggregate parameters/copies, short-circuit expressions, unknown callees
and unrepresented standard-library effects remain incomplete. Selected reference arguments or descendant facts with multiple
allocation identities retain the older summaries, whose missed aliases and
conservative rejections remain unresolved. These checks do not establish
complete allocation lifetime safety.
A later bounded repair composes known direct global reference stores, captured
arguments, return origins and deletion origins. Deleting an allocation stored in
a global invalidates represented caller aliases; replacing that global does not
retarget saved old values. Unknown, indirect and container effects remain
incomplete. Global nil-state summaries and parameter proof obligations are still
open, so this repair does not establish non-nil safety across all calls.
The null-guard trial `68f` and nil-origin trial `f521` are excluded. The former
accepts unsafe programs; the latter rejects a confirmed valid false-branch
control. Conditional origin relations and callee preconditions remain open.

A rejection-only readonly-call analysis checks represented nil field reads across
known calls, local boolean branches, LIFO defers and certified loop bodies.
A known violating call fails with semantic exit 6. Previously accepted guarded
calls and literal-selected non-reading controls remain accepted. Existing call
checks still apply. Finite counted loops publish
their proved final counter value before checking later branches. This analysis
adds no writes, returned-reference facts or lifetime effects. Unsupported globals,
reference fields, containers, nonliteral caller captures, effectful callees and
resource-excluded summaries remain incomplete; an unknown predicate is not a
safety proof. Existing effectful-call analysis retains its separate limits.

The executable-entry check evaluates the original entry file's
parameterless `main` declaration after ordinary safety checks. A complete
readonly summary that proves a reachable nil read adds semantic exit 6. Existing
fatal diagnostics retain priority. An imported or nested declaration named
`main` does not replace the selected entry; `--lib` supplies no execution root.
Missing, incomplete and unresolved summaries add no proof or new acceptance.
The entry diagnostic includes the originating callee source filename, line and
column. Twelve native build/run controls and the repaired
full release gate passed on the identified source snapshot. Function-pointer
locals without an initializer are rejected on proved-uninitialized use
(semantic exit 6); uncertain joins after partial assignment are not yet
rejected.
Effectful entries, ordered mutation and general caller-local truth remain open.

A bounded direct-call repair selects return facts for bodies containing only
blocks, boolean-literal or boolean-parameter conditions, and reference-parameter
or nil returns. Parameters must have explicit `ref` or `bool` types, and every
boolean argument must be a literal. Reference facts come from ordered argument
capture. A selected nil result needs its own guard before field access; a live
selected allocation keeps its identity when a different allocation is deleted.
The ordinary static proof rule also checks uses inside `if false` bodies.
Nonliteral boolean arguments, parameter types written as aliases instead of
explicit `ref` or `bool`, indirect calls and effectful bodies remain outside
this repair. A reference pointee may still be a named or aliased type. The repair
does not change nil-argument policy or generalize parameter assumptions into
caller proofs.

The one-trip proof accepts separate positive increments on alternative paths when
every backedge crosses the loop bound without wrapping. It continues to reject
unproven multi-trip deletion and applies deletion effects after loop exit.
General loop invariants and termination are outside this proof. The combined
stage13 source passed the full release gate. See [Status](STATUS.md) for its
manifest, the earlier failed stage10 gate and remaining safety limits.

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
