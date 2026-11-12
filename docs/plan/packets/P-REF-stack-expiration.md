# Proven expired stack-reference use

Status: proposed, awaiting user approval. No rejection implementation is authorized by this document.

## Current and proposed behavior

The exact observed program in [the frozen stack-escape input](../../../tmp/v1-completion-2026-10-18/stack-escape-reconciliation/inputs/stack_escape.a7) passes semantic checking and emits Zig. make passes its local Counter to keep; keep publishes that borrowed reference in global g. main dereferences g after make returns. A nil guard succeeds as a nilness check but cannot establish that make's storage is still alive.

Proposed bounded rule: a dereference whose known referent storage belongs to a completed function frame or exited lexical scope fails semantic checking with exit 6. Propagate that storage identity through known ref arguments, forwarded returns, global reference stores and checked inline fields. Do not extend the referent's lifetime. Preserve references whose referent scope is still active at the use. Apply expiration at the actual end of the owning frame or lexical scope, after its scheduled cleanup and defer statements have used still-live locals. Return, break and continue must follow their actual cleanup sequence. A stored escaped reference that is never used after expiration is not rejected merely for being stored.

The immediate witnessed change is:

```a7
Counter :: struct { value: i32 }
g: ref Counter = nil
keep :: fn(p: ref Counter) { g = p }
make :: fn() {
    c := Counter{value: 41}
    keep(c)
}
main :: fn() {
    make()
    if g != nil { value := g.value }
}
```

Today the original, longer version emits a pointer to make's local variable. Under the proposal, the read of g.value is rejected because make has returned. The compiler must not report an ordinary nil failure as evidence that it checked expiration.

The paired observed control remains accepted:

```a7
Counter :: struct { value: i32 }
g: ref Counter = nil
keep :: fn(p: ref Counter) { g = p }
main :: fn() {
    c := Counter{value: 41}
    keep(c)
    if g != nil { value := g.value }
}
```

Here c belongs to main's still-active frame. Publication alone is not the proposed rejection condition. Both original inputs are pinned in the [reconciliation evidence](../../../tmp/v1-completion-2026-10-18/stack-escape-reconciliation/REPORT.md). These shorter excerpts explain the rule; they were not separately compiled.

## Authority and compatibility

SPEC §8.1 and Appendix A.4 establish the intended storage duration and reference lifetime requirement. Appendix A.4 explicitly disclaims established enforcement. SAFETY_CONTRACT currently lists non-nil dereference proof and explicit-del lifetime proof. L74's approved rejection set addresses nil and explicit deletion, not stack expiration. L35 does not select a new ownership model. The proposed acceptance change therefore needs an explicit disposition before implementation.

The proposed rejection changes previously accepted dangling-reference uses. It preserves ordinary helper borrows, a borrow returned to a caller while its owner remains live, heap-owned return values, and references to other live allocations. It changes no public ref syntax and chooses no automatic-memory mechanism. The initial bounded implementation cannot claim general lifetime safety for unknown calls, arbitrary aliases or unrepresented aggregate paths. Those remain explicit gaps; do not silently convert them to a blanket rejection policy.

## Alternatives

1. Reject a proven expired dereference. This is the recommendation. It separates a harmless temporary publication from a later invalid use, while requiring owner-duration propagation and expiration effects.
2. Reject every publication or return of a callee-local borrow at the escape point. This can be simpler but is broader: a temporary global borrow consumed and cleared before the owner returns could be rejected. It needs its own compatibility controls and approval; it is not an implementation shortcut for option 1.
3. Extend storage lifetime through automatic promotion or another memory mechanism. This could make some escape programs valid, but requires allocation placement, failure, cleanup and identity rules. L37 permits runtime help without selecting a mechanism. This investigation supplies no measurements or approval for promotion, data stacks, reference counting or collection.

## Acceptance tests

All tests must run in semantic and Zig-emission modes. Rejections require exit 6 and no emitted artifact. Positive controls require exit 0. For negative tests, require an expiration-specific diagnostic at the stale use, with the originating local and completed scope identified; a generic non-nil failure is insufficient. This proposal does not prescribe a diagnostic code that already exists.

| Case | Example shape | Required result |
| --- | --- | --- |
| Observed global escape | make creates c; keep(c) assigns g; main reads g.value after make | 6 |
| Observed live caller | main creates c; keep(c) assigns g; main reads g.value before returning | 0 |
| Direct returned local | make returns its local c as ref Counter; caller guards and reads returned value | 6 |
| Forwarded returned local | forward returns make(); caller guards and reads | 6 |
| Inline aggregate escape | make creates Holder{inner:Counter{value:41}}; keep(holder.inner); caller reads g after make | 6 |
| Caller-owned borrow returned | echo(p:ref Counter) returns p; main passes its local c and reads the returned borrow in main | 0 |
| Heap-owned return | make returns new Counter after guarded initialization; caller guards and reads while allocation remains alive | 0 |
| Live nested helper | main's c passes through echo and keep while main remains active | 0 |
| Temporary publication | helper stores a borrow to its local in g, reads it, then clears g before returning; caller does not use an expired borrow | 0 |
| Distinct live referent | an expired local existed, but g was definitely overwritten with a different still-live referent before use | 0 |
| Fresh allocation replacement | g once referred to expired storage, then receives a checked fresh heap allocation before read | 0 |
| Exited nested scope | outer reference receives an inner-block local; read occurs after that block ends | 6 |
| Cleanup before expiration | a defer reads its own scope's local through a saved borrow before that storage expires | 0 |
| Stored but unused | a helper publishes its local reference and returns; no later operation reads or dereferences that expired reference | 0 |

Only the first two cases have been compiled in this task. The other cases are proposed acceptance requirements, not passing tests. Concrete runnable fixtures must be source-reviewed and frozen before candidate execution. Existing 206 inherited and 12 recurrent-owner outcomes remain mandatory; this new work must not replace them.

## Source review and implementation boundary

The emitted witness confirms a direct stack address: keep(&c), followed by frame return, then a read through g. A repair must distinguish the borrowing callee's frame from the referent owner's frame. Returning a parameter from echo does not expire a caller-owned local. Inline fields inherit the containing local's duration. Forwarding functions must carry original storage identity rather than relabeling it as their own local or a new allocation.

Use iterative transfer and finite scope/frame-origin identities consistent with the no-recursion compiler rule. Track expiration independently of explicit del, and preserve stale aliases when other slots are reassigned. Definite replacement clears a slot's old value, not the old referent's expiration for remaining aliases. No source was changed to implement these rules.
