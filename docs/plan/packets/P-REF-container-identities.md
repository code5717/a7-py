# P-REF: container and selected-reference identities

Status: proposed, not approved. This packet separates exact alias propagation
from decisions about uncertain indices and correlated branches. It does not
select automatic memory management, add syntax, or authorize blanket rejection
of reference containers. Record a disposition in the
[decision ledger](../decisions.md) before changing compatibility rules.

## Authority and current evidence

L74 approves rejecting use of an allocation deleted through an alias while
preserving guarded accesses, distinct allocations/fields and fresh reassignments.
Applying that rule to a demonstrated stale container alias is consistent with
its intent. Treating every uncertain index or selected reference as unusable is
a broader policy and has no automatic approval. The
[current status](../../STATUS.md) keeps container and selected-field identity as
open release blockers. Callee-effect repairs are a separate workstream.

Twelve compile-only probes used the immutable review checkout
`/var/tmp/a7-v1-review-2026-10-07-tm97sah2/checkout`, with safety.py SHA-256
`b8b508a22dd5c86f7bf30562031999e20295ebdf4c35b2f5472c85d1ba09b6e7`.
Python ran on CPUs 8-11 with that checkout prepended to sys.path and used as cwd.
The printed package path was that checkout's `a7/__init__.py`.
`A7Compiler.compile_file_detailed` stopped at generated Zig. No native build or
unsafe execution occurred. These are snapshot results, not a claim about later
callee repairs. The repository-root-relative local archive is
`tmp/v1-completion-2026-10-07/container-identity-packet/`; all decision evidence
needed below is reproduced here without a publication link to ignored scratch.

| Probe | Observed exit | Proposed bounded result |
| --- | --- | --- |
| Array element alias read after deleting source allocation | 0 | 6, deleted-value diagnostic |
| Same array alias read before deletion | 0 | 0 |
| Slice element alias read after deleting source allocation | 0 | 6, deleted-value diagnostic |
| Same slice alias read before deletion | 0 | 0 |
| Delete refs[0]'s allocation, read separately allocated refs[1] | 0 | 0 |
| Delete old refs[0], replace it with new allocation, guard and read | 0 | 0 |
| Nil element read under a non-nil guard | 0 | 0 |
| Nil element dereferenced without a guard | 6 | 6, `Reference not proven non-nil` |
| Copy selected reference, delete child through copy, read original child | 0 | 6, deleted-value diagnostic |
| Same selected child read before deletion | 0 | 0 |
| Replace deleted selected child with new allocation, guard and read | 0 | 0 |
| Delete selected child, read separately allocated selected sibling | 0 | 0 |

Exit 0 means compiler acceptance only. It does not qualify native execution,
cleanup, or all possible container operations.

## Concrete acceptance changes

### Exact array and slice elements

Current snapshot accepts this program. On successful allocation, q refers to the
allocation deleted through p. The nil guard does not restore its lifetime.

```a7
io :: import "std/io"
Box :: struct { value: i32 }
main :: fn() {
    p := new Box
    if p == nil { ret }
    refs: [1]ref Box = [p]
    del p
    q := refs[0]
    if q != nil { io.println("{}", q.value) }
}
```

The proposed result is semantic exit 6 with primary diagnostic
`Use after move or delete`, before native compilation. The slice variant inserts
`view := refs[0..1]` before deletion and reads `view[0]`; it currently exits 0
and should receive the same rejection. A slice must retain backing-storage and
offset identity; passing the fixed-array case alone does not qualify slices.

For the valid before-deletion control, move `del p` after the guarded read.
That must remain accepted. The following distinct-element/fresh-replacement
sequence must also remain accepted, assuming p and r are separately allocated
and guarded non-nil references:

```a7
refs: [2]ref Box = [p, r]
del p
q := refs[1]
if q != nil { io.println("{}", q.value) }
refs[0] = new Box
fresh := refs[0]
if fresh != nil { io.println("{}", fresh.value) }
del fresh
del r
```

The independent distinct-element and replacement probes each exited 0. This
combined snippet states their required composition; it was not an extra executed
probe. Fresh allocation may fail, so its guard remains necessary. Replacement
does not revive any earlier extracted alias to p.

### A copied selection must retain the same selected object

Assume guarded, independently allocated holders a and b, each with its own child:

```a7
p := if flag { a } else { b }
c := p
del c.child
if p.child != nil { io.println("{}", p.child.value) }
```

The complete probe declares `Holder :: struct { child: ref Box }`, allocates both
holders and children, and calls its enclosing function with true. It currently
exits 0. The proposed result is semantic exit 6: c and p are exact copies of the
same selected reference, regardless of which holder flag selected.

These controls must remain accepted:

```a7
p := if flag { a } else { b }
c := p
if p.child != nil { io.println("{}", p.child.value) }
del c.child
p.child = new Box
if p.child != nil { io.println("{}", p.child.value) }
```

Before-deletion and fresh-reassignment variants independently exited 0. A
separately allocated sibling must remain live after child deletion. Neither the
parent holder nor all fields beneath it may be marked deleted merely because
one child allocation died. Complete allocation-failure cleanup is required for
future native controls; the compile-only evidence does not qualify cleanup.

## Proposed exact analysis boundary

For a first bounded change, preserve element identities at exact indices in
fixed arrays, fixed-array copies, and slices with exact backing storage and
offset. "Exact" means the existing integer proof has one value at the use site,
not only a literal spelling: `refs[0]`, folded `refs[1-1]`, and `i: usize = 0;
refs[i]` qualify while that proof holds. Reassignment or call invalidation can
remove it. Existing bounds and usize rules still apply. This is a proposed scope
definition, not evidence that every such form was probed. An element copy copies a reference value; a slice copy shares the view.
A store at an exact element updates that slot, leaving previously copied
reference values and other slots unchanged. Overlapping slice views must observe
a store to their shared slot. Non-overlapping slots must remain independent.

Carry a selected-reference value identity through plain reference assignment.
A copied selection must resolve field storage consistently through either alias.
Deleting its child invalidates saved aliases of that child. Storing a fresh
reference into that selected child establishes the new value for that selection,
without pretending every possible holder's child was overwritten.

An allocation may-set alone cannot represent this. The following independent
selections can have identical sets while selecting different objects:

```a7
p := if first { a } else { b }
c := if second { a } else { b }
```

They must not be canonicalized to one storage location merely because their sets
match. Conversely `c := p` must not lose its exact-copy relation. Preserve that
relation only while the relevant values remain unchanged; reassignment to either
binding creates a new value relation.

The bounded container scope is one-dimensional local fixed arrays of references,
copies of those arrays, and slices into that storage with exact offsets.
Arrays inside record fields or record copies, arrays of arrays (`m[1][2]`), and
slices of slices are outside this first slice. Slice-of-slice views over the same
one-dimensional backing array qualify only when the composed offset is exact;
this is different from a slice whose elements are themselves slices. Existing
nested-record tests do not qualify any of these container extensions.

Selected fields also require checking effects through the original bases:
`del p.child` followed by `a.child.value`; `a.child = new Box` followed by a read
through p; and deleting a possible parent a before reading `p.child`, where
`p := if flag { a } else { b }`. Their post-change behavior is not established by
the twelve probes. The first slice must not leave stale selected-field facts
after a base-field store or deletion. Where correlation is required to preserve
a valid control, classify the case as unresolved rather than treating its old
fact as proof. Parent deletion remains a lifetime obligation independent of
field-key lookup: the reviewed source checks the identifier's allocation set
before traversing a field, so no current acceptance claim is made for that case.

No program should become accepted by accidentally discarding provenance. Any
unsupported case remains explicitly outside the qualified slice, with existing
gaps visible. Keeping a legacy path does not establish its soundness. In
particular, a call argument or nested store can change the identity domain during
evaluation; eligibility cannot be checked only before those effects occur.

## Unknown callees and affected storage

The new facts cannot survive an unknown callee merely because the slice binding
was passed by value: its backing storage can still be changed. A writable view
or borrowed array escaping to such a call requires a disposition for subsequent
slot identities, stored non-nil facts, and old extracted aliases. Forgetting a
slot's nil proof is insufficient if the callee can delete an allocation whose
alias was already copied elsewhere.

Two compatibility choices remain open. A conservative rule would forget affected
slot-value proofs and mark reachable allocation lifetimes uncertain; a later read
would fail with exit 6 unless a supported effect contract restores the needed
proof. That can reject a valid program whose callback happens to be read-only.
The alternative is to require a known checked effect contract for this new
qualified slice, leaving unknown-call cases explicitly unqualified with their
existing behavior. Neither choice is approved here. A nil guard alone cannot
restore a lost lifetime proof. Unrelated containers and a fixed array's structural
length should retain their independent facts; whether a caller-visible slice
binding can change length depends on whether that binding itself was borrowed.
No current unknown-callee acceptance result was newly measured for this packet.

## Dynamic indices and branch correlation need a separate choice

For an in-bounds but unknown index, a read can select any possible element.
Deleting that selected value may invalidate one of several allocations. A write
must retain unchanged alternatives for other elements. This does not justify
rejecting the index operation itself or treating every element as definitely
replaced/deleted.

Some programs are valid only with correlation information. For example, after
bounds checks and `i != j`, deleting `refs[i]` and reading `refs[j]` is safe only
if the elements are also known to contain distinct allocations. Different indices
alone do not prove that: `[p, p]` contains aliases. Likewise, these complementary
selections are distinct only while flag, a and b preserve their relevant values:

```a7
p := if flag { a } else { b }
c := if flag { b } else { a }
del p.child
if c.child != nil { io.println("{}", c.child.value) }
```

When a and b and their children are independently allocated, this is a valid
control. It is a proposed correlation requirement, not one of the twelve observed
probes. A may-alias union loses the relation and can falsely reject it. A nil guard
on c.child proves nullness, not independence from the deleted allocation.

| Alternative | Acceptance policy | Compatibility and qualification |
| --- | --- | --- |
| Approve exact elements/views and copied selections first | Reject the demonstrated stale uses; preserve the paired exact controls | Smallest proposed slice. Dynamic-index and independent-branch correlations remain unresolved release blockers |
| Require relational branch/index tracking before completing this track | Reject every feasible stale-use path while preserving proven distinct selections | Needs explicit rules for condition stability, mutation, joins, slice offsets and loops; this packet does not yet define a complete domain |
| Approve conservative rejection when live identity cannot be proved | Unknown reads may fail even when a programmer can prove they are safe | Requires explicit approval of lost valid cases such as the complementary-selection control; no blanket unknown-index rejection is implied |

The recommended initial disposition is the first alternative. It is not a
recommendation to publish with the remaining gaps or to declare all container
identity solved. The general correlation rule and any broader conservative
rejection policy remain undecided. No option selects reference counting, a
collector, ownership syntax or a runtime memory mechanism.

## Approval and verification boundary

An approval must name the selected alternative, preserved controls, and the
unknown-callee disposition for the qualified slice. Record
its compatibility boundary before implementation. STATUS and the delivery
roadmap remain the work trackers; this packet adds no separate TODO ledger.

Required checks pair stale-use and repeated-delete rejections with before-delete,
distinct-slot/distinct-allocation, shared-slot slice, fresh-replacement and
non-nil-guard controls. Explicit element-deletion pairs must include
`del refs[0]` followed by a read or second deletion through its previously copied
alias, and deletion through `view[0]` followed by a direct alias read. For
`v1 := refs[0..2]` and `v2 := refs[1..2]`, `del v1[1]` must invalidate a saved alias
of `v2[0]`; a fresh store through either view must be visible through the other.
The non-overlapping refs[0] allocation must remain independent. These are required
future checks, not additional observed results. Include arrays containing the
same allocation twice,
independent selections with the same may-set, and mutation between selection and
use. Confirm that existing direct aliases and parameter passing retain their
meaning. Run unsafe cases compile-only; native debug/release/fast controls must
verify the intended object and clean up exactly once. No native qualification
has been performed for this packet.

Primary implementation and regression references:

- [Reference identity tests](../../../test/test_safety_reference_identity.py)
- [Expression-order tests](../../../test/test_safety_expression_order.py)
- [Safety fact and storage implementation](../../../a7/passes/safety.py)
- [Array, slice and reference rules](../../SPEC.md)
- [Safety contract](../../SAFETY_CONTRACT.md)
