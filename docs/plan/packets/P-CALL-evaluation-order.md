# Callable selection before arguments

Disposition: proposed; no language change approved or implemented by this packet.

## Current specification and observations

`docs/SPEC.md` guarantees left-to-right argument evaluation. It does not
explicitly say when a mutable callable is selected relative to its arguments.
The safety analysis captures the callable before visiting arguments. The Zig
backend currently emits a direct call without an explicit saved-callee variable.
Source rendering order alone cannot establish runtime evaluation order.

This complete program passed semantic checking, emission, native builds and
execution on frozen `b37fc6f2`, using Zig 0.16.0 on the local host:

```a7
io::import "std/io"
old_target::fn(unused:usize){io.println("old")}
new_target::fn(unused:usize){io.println("new")}
change::fn(slot:ref fn(usize)) usize{
 io.println("argument")
 if slot!=nil{slot=new_target}
 ret 0
}
main::fn(){state:fn(usize)=old_target;state(change(state));state(0)}
```

Debug, ReleaseSafe and ReleaseFast each printed exactly:

```text
argument
old
new
```

The first call selected `old_target` before `change` replaced the variable.
The later call selected `new_target`. All three executions exited 0 with
empty stderr. This establishes an observation for this compiler and toolchain,
not a public language guarantee.

The otherwise identical inferred declaration, `state:=old_target`, passed
semantic checking and emission but failed its first native build. Zig rejected
`var state = old_target` because a mutable runtime variable needs a function
pointer type. No inferred-version binary ran. That declaration repair is
independent of the ordering choice and must preserve this failed source.

## Proposed contract

For each call, evaluate and save the callable value first. Then evaluate
arguments from left to right. Invoke the saved callable with those evaluated
arguments. A mutation of the callable's source variable during argument
evaluation affects subsequent calls, not the callable already selected.

An argument passed by reference still designates its storage. Saving that
argument's address does not freeze the storage contents: later argument
effects may change the value the callee reads. This distinction applies to
function slots and slice slots as well as ordinary reference arguments.

The program above would have the same required output after adoption. This
proposal preserves its observed Zig behavior and the analysis's existing
selection order. It adds an explicit obligation for every supported backend
and optimization profile. It does not introduce a propagation operator,
closure support, new reference syntax or a payload ownership rule.

## Alternatives and compatibility

| Choice | Meaning for `state(change(state))` | Compatibility |
| --- | --- | --- |
| Save callable before arguments, recommended | Invoke the old callable; a later call uses the replacement | Matches the observed native outputs; compiler analysis and lowering must preserve the guarantee |
| Leave callable selection unspecified | Callers cannot rely on selecting the old or replacement callable | Keeps the current specification gap; analysis must remain sound for every permitted order |
| Select callable after arguments | Invoke the replacement callable on the first call | Changes the tested current behavior to `argument`, `new`, `new`; requires a separate explicit choice |

No output from an existing native run alone approves any row. Inferred and
explicitly typed callable declarations must share whichever contract is adopted.

## Acceptance evidence after a decision

The adopted order needs observable tests for local callable replacement,
saved aliases, nested calls and multiple effectful arguments. A later call
must observe the replacement. Reference arguments must observe permitted
earlier argument writes through shared storage. Generic callable lowering
must preserve its selected specialization without introducing a mutable
runtime generic-function value.

Safety tests must distinguish the selected callable's effects from mutations
performed while evaluating arguments. A callback that resets a loop counter
must still invalidate its proof. The proposed saved-callee lifetime control
currently rejects conservatively; its required acceptance depends on the
ordering decision and a sound analysis of the complete loop.

Native assertions must cover Debug, ReleaseSafe and ReleaseFast on an identified
source revision. Emission tests and analysis traces alone cannot establish
runtime ordering. No such acceptance is claimed for a future repair here.

## Evidence

- [Specification and prior-record review](../../../tmp/v1-completion-2026-10-10/primitive-location-callable-order-contract/REPORT.md).
- [Inferred declaration build failure](../../../tmp/v1-completion-2026-10-10/primitive-location-callable-order-probe/REPORT.md).
- [Explicit-type native observations](../../../tmp/v1-completion-2026-10-10/primitive-location-callable-order-probe/explicit-type/REPORT.md).
- [Separate declaration diagnosis](../../../tmp/v1-completion-2026-10-10/primitive-location-callable-order-probe/explicit-type/DECLARATION-DIAGNOSIS.md).
- [Proposed lifetime control and its evidence boundary](../../../tmp/v1-completion-2026-10-10/primitive-location-handle-certificate-controls/REPORT-execution-addendum.md).
