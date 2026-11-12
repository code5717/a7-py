# Consuming result payloads

General task results and channel failure results need an ownership contract
beyond current tagged-union matching. This is design evidence for
[P-CON](../packets/P-CON-structured-tasks.md), not an approved language change.
It does not select a memory mechanism or propose that string-containing types
are the complete set of owning types.

## Current behavior

The [compiler-only probes](../../../tmp/v1-completion-2026-10-07/union-payload-current-probe/REPORT.md)
record twelve checks/emissions on frozen `de578138`. Scalar payload matching
can be repeated. String and string-record binding fail with exit 6. A bare
string tag test, ref capture and slice capture pass checking and emission.
No native program ran.

```a7
Outcome :: union(tag) {
    text: string,
    empty: i32,
}
main :: fn() {
    r := Outcome{text: "hello"}
    match r {
        case .text(value): {}
        case .empty: {}
    }
}
```

The binding above is currently rejected. Changing `.text(value)` to `.text`
permits a tag test. The classifier in `a7/passes/type_checker.py:5418` follows
by-value fields and fixed arrays but stops at refs, pointers and slices.
It does not prove that a captured handle uniquely owns its referent.
L66 approves the existing dot-arm matching; consuming a union needs approval.

## Existing decisions constrain consumption

L68 adopts the recommended options in the
[stdlib proposal](../../audits/2026-10-04/stdlib-proposal.md).
U2 selects `Result` or `Option` for externally fallible operations, and U3
selects canonical types provided to every file. Those choices do not provide
consuming payload extraction or define automatic cleanup.

U6 already selects shared list identity on assignment, independent copying via
`list.copy`, and returned list handles without manual freeing. A result containing
a list cannot acquire exclusive ownership of that list merely because the result
is consumed. An existing alias must retain the list's adopted identity and
lifetime behavior. Concurrent access still needs the separate sharing contract.

The proposed file `close` signature is marked as a checked signature in section
3.14. It is not an adopted policy for automatic disposal or cleanup failure.
The memory mechanism and owning payload binding remain separate prerequisites
in the proposal's R8 and R5 rows. A task/result design must not infer a cleanup
policy from the existence of a function named `close`.

## Public choices independent of allocator selection

| Choice | Proposed observable behavior | Compatibility consequence |
| --- | --- | --- |
| Explicit consuming operation | Caller explicitly consumes a result; all arms invalidate that result until reassignment; selected payload leaves it once | Ordinary scalar matching keeps copying; a new operation or syntax needs approval |
| Inferred consumption during binding | Binding an owning payload consumes the result without another spelling | Meaning depends on payload type and generic specialization; ordinary matches may acquire new post-match restrictions |
| Borrowed payload access | Bound value remains tied to the result's storage and lifetime | Useful for inspection; does not itself transfer an owning value out of a task or return an unsent payload |
| Copy payload | Binding makes an independent copy or retains shared storage | Copy costs, mutation visibility and resource duplication need contracts; copying a file or task handle cannot be assumed |

The recommended direction for comparison is explicit consumption while preserving
ordinary copy matching. This recommendation is not approval. A consuming form
must define what it consumes: the result container, its active value and that
value's ownership obligations. It cannot turn every reference reachable from a
payload into an exclusive owner merely by invalidating one local name.

## Required before/after cases

These outcomes describe the recommended direction. There is no selected spelling
for the consuming operation, so the following are transition traces rather than
claims about runnable syntax.

| Case | Before extraction | Required outcome for an explicit consuming contract |
| --- | --- | --- |
| String result | Current binding rejects | Extract once; source result becomes unavailable; an unused extracted value follows the approved cleanup rule |
| Record containing string and scalar | Current binding rejects structurally | Transfer the entire active record; early return cannot lose or duplicate its cleanup obligations |
| Ref payload with a separate alias | Current handle capture passes | Describe which ownership right moves; do not silently revoke the other alias or infer referent uniqueness |
| Slice payload with another view | Current handle capture passes | Preserve the backing lifetime and permitted views; moving the descriptor cannot prove exclusive ownership of backing storage |
| List payload with a copied handle | Shared-list identity is adopted, but no list implementation is qualified here | Consuming the result must preserve the other handle's shared identity and automatic lifetime; it cannot silently make the list unique |
| Bare active-tag arm | Current test does not consume | In an explicitly consuming match, dispose of the unbound active payload exactly once under its cleanup contract |
| Source assigned a fresh result afterward | Ordinary assignment exists | Reassignment restores the source's availability without reviving the previously extracted value |
| Match with different branch exits | Current match joins branch facts | Every exit records the same source-consumed state; selected payload cleanup follows its actual exit path |
| Source is a field or indexed element | Container may have other aliases | Define partial consumption and replacement, or reject that operand shape explicitly; local-only support cannot stand in for the eventual general contract |

For each permitted result transfer, storage needed by the extracted value must
remain alive after the original container disappears. This may require retained
storage, moved storage or another approved mechanism. Allocation strategy alone
does not determine which aliases may still read or write the payload.

## Acceptance boundary

A final packet needs complete programs for each selected operation, both accepted
controls and rejected double-consumption cases. It must cover nested aggregates,
generics, temporary results, branches, loops, deferred cleanup, reassignment and
aliases. Native observations must count resource release on success, early return
and failed transfer. String literals alone cannot prove owning-resource cleanup.

P-CON's general channels and task results remain dependent on this decision.
Replacing them permanently with scalar adapters would leave the V1 requirement
incomplete. The allocator can remain unselected during public-contract design,
but ownership, alias visibility and cleanup outcomes cannot remain unspecified
when the consuming API is approved for implementation.

## Error-set composition research, October 9

The user supplied Dillon McMahon's October 6 article,
[The Missing Piece in Rust Error Handling](https://mcmah309.github.io/posts/the-missing-piece-in-rust-error-handling/).
It describes combining possible error types, widening a set during propagation,
and removing a handled type from the remaining set. Diagnostic context travels
with the error separately from its recovery type. These are research inputs,
not adopted A7 behavior.

A7 already has canonical `Result(T, E)` and explicit match propagation. A future
proposal could examine composition within `E` without replacing `Result`.
Handling one variant of an error must preserve the remaining failures. Handling
file-not-found must not imply that permission failures have also been handled.
Domain-specific errors may still distinguish recovery policies that share an
underlying I/O type.

The author's [Eros README](https://github.com/mcmah309/eros#optimizations)
documents a boxed error representation. A7 must evaluate representation and
allocation costs separately; this article does not establish that boxing is
required. No Rust library build or performance validation was performed here.

Error-set reduction also leaves this document's ownership questions open.
Extracting or handling an error payload still requires rules for consumption,
aliases, retained storage and fallible cleanup. No new syntax, propagation
operator, type erasure policy or consuming operation is approved by this research.
