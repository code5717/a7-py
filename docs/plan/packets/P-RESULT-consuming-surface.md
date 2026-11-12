# Consuming-result spelling

Status: proposed design-direction decision only. Selecting this spelling does
not authorize implementing general consumption before the lifetime, alias and
cleanup contracts are approved. No compiler behavior has changed.

## Current behavior

Tagged-union payload binding copies the selected payload. Binding a string or a
record containing a string is rejected with semantic exit 6. Bare tag tests pass.
Scalar, ref and slice captures pass the
[current probes](../../../tmp/v1-completion-2026-10-07/union-payload-current-probe/REPORT.md).
Those probes do not establish referent ownership or automatic cleanup.

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

The string binding above is rejected today. Replacing `.text(value)` with
`.text` makes it an accepted tag test.

## Recommended spelling for the final contract

Reserve a `take` operation in `std/results`. Permit `results.take(place)` only
as the direct subject of a match. Preserve ordinary `match r` copy behavior.
This follows existing call and match grammar without introducing a keyword.
`results` is a local import alias; programs may choose another alias.
The proposed module hook is a compiler operation, not an ordinary function that
copies its argument before the match sees it.
L68/U1, U4, U5 and U12 already select module free functions, explicit imports,
the `std/` prefix for new modules and typed internal hooks. They permit this
architecture but do not approve the consuming effect. Canonical `Result` and
`Option` are already selected by U3; this operation does not replace those types.

```a7
io :: import "std/io"
results :: import "std/results"
Outcome :: union(tag) {
    text: string,
    empty: i32,
}
main :: fn() {
    r := Outcome{text: "hello"}
    match results.take(r) {
        case .text(value): io.println(value)
        case .empty: {}
    }
}
```

After the complete contract is approved and implemented, the proposed program
prints `hello`. Consuming the result makes `r` unavailable on every arm until a
fresh assignment reinitializes it. A later `match r` would be a semantic exit-6
use-after-consumption error. Ordinary scalar matches retain today's ability to
read their source again. These are proposed outcomes, not current test results.

The operand's base and index expressions must each evaluate once. The final
contract must state the commitment point and what remains usable if evaluating
the operand fails. Functions cannot store or forward `results.take` as an
ordinary function pointer. Calls outside a direct match subject would fail
semantic checking. The complete contract must also cover returned temporary
results; a local-only implementation cannot satisfy the general result API.

## Alternatives and compatibility

| Direction | User-visible consequence |
| --- | --- |
| Explicit `results.take(r)` | Consumption is visible at the match; ordinary matching keeps its present behavior |
| Inferred consuming binding | Existing `.text(value)` spelling could consume according to the payload type; generic specialization can change source availability |
| Dedicated consuming-match syntax | Consumption is visible without a module import, but requires new grammar and a separate syntax choice |

The proposal adds a reserved standard module and leaves user-defined functions
named `take` unchanged. It does not remove `new`, `del`, refs or slices. It does
not introduce automatic parallel execution or approve P-CON's task interfaces.

## Required contract before implementation approval

Independent review identified five observable gaps. Selecting spelling does not
settle them:

1. Disposing a union slot versus freeing a ref's allocation or a slice's backing
   storage, including other live aliases. U6's shared list handles and automatic
   lifetime remain adopted; consuming a result cannot revoke another list handle.
2. Retaining every dependency of an extracted mixed record, including strings,
   refs, slices and resources. Users must not manually track cleanup obligations.
3. Partial consumption of record fields and indexed elements, whole-container
   operations, alias conflicts and reinitialization. Unknown-index rejection or
   runtime checking needs an explicit decision.
4. The commitment point, failure before consumption, failure afterward, bare
   arms, `else`, early return and repeated consumption.
5. Fallible cleanup: whether an arm executes after disposal failure and how that
   failure combines with a pending return or another failure.

The final packet must supply complete programs and observable outcomes for those
cases, plus native resource-release evidence after implementation. The
[consuming-result comparison](../research/consuming-results.md) keeps general
payloads in scope. The production allocator or collector may remain unselected
during public-contract design; lifetime and cleanup behavior cannot remain open
when execution semantics are approved.
