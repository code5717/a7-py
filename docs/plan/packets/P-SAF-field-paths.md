# P-SAF: field-path non-null proofs

Status: draft, not approval-ready, 2026-09-20. No implementation is approved by
this packet. The isolated one-line SAF-2 candidate must not be applied because
it rejects a valid direct field guard. This document records remaining design
work; it is not an approval request.

A small path-fact layer can preserve the direct guard without waiting for typed
IR. It must be part of existing control-flow state, not a cache of AST results.
This can be sound with conservative invalidation. It cannot promise that every
formerly accepted program stays accepted: previously unchecked `ptr` accesses
include valid cases whose safety needs stronger alias or call-effect analysis.
Those remaining compatibility changes need measured examples and disposition.

## Current evidence and rejected candidate

[The durable safety revalidation](../../audits/2026-09-20-core-v1/critical-safety-revalidation.md)
and [exact sources/results](../../audits/2026-09-20-core-v1/critical-safety-revalidation.json)
record 13 original critical probes. Eight now reject; five still compile,
including SAF-2. None of those unsafe generated programs was built or executed.

The candidate changes the non-null rule from every field named `ptr` to only
an actual slice's `.ptr`. It rejects the original nil dereference and preserves
a guarded local alias and slice-pointer control in Debug and ReleaseFast. Four
initial tests pass. A 255-file repository corpus showed no exit-status or output
changes, but it omitted this valid direct-guard case:

```a7
io :: import "std/io"
Inner :: struct { value: i32 }
Outer :: struct { ptr: ref Inner }
main :: fn() {
    allocated := new Inner
    if allocated != nil {
        allocated.value = 7
        o := Outer{ptr: allocated}
        if o.ptr != nil { io.println("{}", o.ptr.value) }
        del allocated
    }
}
```

Before the candidate, this compiles with exit 0, builds with Zig Debug and runs
with exit 0, stdout `7\n` and empty stderr. After the candidate, it rejects with
semantic exit 6 and `Reference not proven non-nil`. No candidate native program
ran for this case. The fifth regression test requires acceptance and fails on
the candidate. Current guard facts recognize identifier bindings but do not
retain the proof for `o.ptr`.

The isolated patch and complete direct-guard command/output record remain at
`tmp/saf2-candidate-qnlak3ib/saf2-not-ready.patch` and
`tmp/saf2-candidate-qnlak3ib/direct-guard-results.json`. Main compiler and test
files were not modified for that experiment.

The execution plan labels P0b revision 3 approved, but L24 separately requires a
packet for changes to programs that compile and work. No explicit approval to
reject this valid control was located. Preserve its behavior before treating
the candidate as a bounded correction. Broader compatibility changes need their
own concrete evidence and disposition.

## Facts and guards

Use a key containing the root binding's identity and a tuple of field names.
For example, one declaration's `o.ptr` is distinct from another block's `o.ptr`.
Do not key solely by text, or let a node's old cached fact establish a new use.
Track lexical bindings while visiting parameters, globals and declarations;
resolve the initializer before introducing its new shadowing binding.

Initially support a field chain rooted in a local, parameter or global binding.
Indexing, calls and arbitrary computed roots produce no reusable path fact.
Check every dereferenced prefix before learning the final reference is non-null.
Learn from `path != nil` on the true branch and `path == nil` on the false branch.
Accept the fact only for the same binding and path in the dominated branch.

Snapshot path facts with scalar facts. At a join, retain only facts true on every
reachable predecessor. At an early return, retain the actual surviving branch
state. Do not replay an old negated condition after that branch's mutations.
This last rule must cooperate with the open SAF-4 defect.

## Invalidation rules

| Event | Required action |
| --- | --- |
| Reassign a root binding | Remove facts for that root and all its field paths. |
| Replace a reference-valued field or a composite containing references | Remove all path facts unless a separate alias proof establishes a narrower effect. Same-name roots are not a sufficient alias test. |
| Write a primitive scalar field | Keep non-null path facts only when its resolved type proves the write cannot replace a reference or containing object. Check the target path before the write. |
| Compound assignment | Visit operands and prove the target normally; apply the same storage-write rule, with no special exemption for spelling. |
| Copy an object or reference into another binding | Do not infer ownership or uniqueness. Do not automatically transfer guarded path facts to the alias. Later writes/deletes through either alias must invalidate affected proofs, conservatively all paths if uncertain. |
| Function or native call | Evaluate callee and arguments in actual evaluation order, then drop all path facts unless a verified effect summary permits retention. Argument-side calls invalidate before later argument expressions are checked. |
| `del`, including fields or aliases | Drop all potentially affected path facts. With no complete alias tracking, drop all path facts. A prior non-null check does not prove the object is still alive. |
| `defer` registration | Analyze the deferred body using its own snapshot; do not treat its future effects as already executed. Record its writes/calls/deletes for invalidation at every applicable scope exit. |
| Scope exit, return, break or continue | Apply executed deferred effects before propagating path facts. Remove local-binding identities. Do not restore stale outer facts after an intervening alias write. |
| Loop entry/back edge | Invalidate paths affected anywhere in the repeated body before analysis. Relearn from the current guard. Without an adequate loop effect summary, clear all path facts at entry and exit. |
| Match and `fall` | Separate case states, join exits and carry the actual fallthrough state into the next case. Until that is reliable, clear path facts at these boundaries. |

Do not add runtime checks in this batch. Their failure behavior and release
contract remain a separate approved design task. Dropping a fact must not become
an unchecked dereference.

## Minimum controls

Positive cases: direct guarded field read and write; nested reference field with
each prefix checked; guarded local alias; scalar `ptr` field; slice `.ptr`;
repeated reads without effects; distinct lexical bindings with the same name.
Run accepted controls in Debug and ReleaseFast with independently stated output.

Negative compile-only cases: original nil `ptr`; same field named `link`; root
reassignment after guard; replacement of an intermediate field; mutation through
an alias; direct and nested calls that clear a reference; call in an earlier
argument followed by a guarded-path read; direct/deferred deletion; deferred
reference replacement; loop second-iteration mutation; branch join and match
fallthrough carrying a null reference. Pair each invalidation case with a guard
re-established after the effect.

First prototype the direct branch case and invalidation checks in isolation.
Re-run the original 13 probes and compatibility corpus, including generated
sources. Do not declare SAF-2 closed if preserving its valid controls requires
ignoring calls, aliases, deferred effects or loop paths.

## Work required before an approval-ready packet

Define and test the binding identities, path extraction and effect invalidation
rules above. Resolve their interaction with the still-open SAF-3 fallthrough,
SAF-4 early-return mutation and SAF-6 global-call cases. Build an isolated
prototype that preserves the direct field guard and rejects its invalidated
variants. Measure compatibility against repository files and generated test
sources, then show every newly rejected working case. Preserve native guarded
controls in both profiles. Only then prepare a complete behavior proposal.
