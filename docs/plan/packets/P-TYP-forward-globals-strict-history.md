# Historical strict global-type proposal

Superseded as the active proposal on 2026-09-20. The user selected development
of exact-fit untyped constants. The text below preserves the earlier proposal
and its evidence; its approval request is inactive. See
[the revised P-TYP packet](P-TYP-forward-globals.md).

# P-TYP: type global declarations before function bodies

Status: pending approval, 2026-09-20. No production type-checker change has been
made. This packet covers global value types only. It does not approve new module
rules, local use-before-declaration behavior or implicit numeric conversions.

## Decision requested

Approve resolving global declaration types before checking function bodies,
independent of source order. Reject a forward reference when its resolved type
is incompatible with the operation, including the float-to-integer example
below. Keep generated declaration order and runtime evaluation order unchanged.

The existing execution plan routes TYP-01's working float-to-integer case to
P-TYP. The historical type audit also records that this case builds and runs.
See [execution](../execution.md) and [TYP-01](../../audits/2026-09-16/compiler/types.md).

## Current and proposed behavior

This current program compiles, builds with Zig Debug and prints the string's
bytes instead of the string:

```a7
io :: import "std/io"
show :: fn() { io.println("{}", GREETING) }
GREETING :: "hello"
main :: fn() { show() }
```

Current output:

```text
{ 104, 101, 108, 108, 111 }
```

Proposed output:

```text
hello
```

Moving `GREETING :: "hello"` above `show` already prints `hello`. The current
forward case generates Zig formatting `{any}`; the backward case uses `{s}`.
The proposal makes both declarations produce the same string behavior.

This second program also currently compiles and runs:

```a7
io :: import "std/io"
show :: fn() {
    n: i32 = RATE
    io.println("{}", n)
}
RATE :: 2.0
main :: fn() { show() }
```

Current output is `2`. Proposed behavior is semantic exit 6 with a type mismatch:
`expected 'i32', got 'f64'`. No Zig file is emitted. Moving `RATE :: 2.0` above
`show` already rejects this assignment. Approval therefore changes an accepted,
building program to a compiler error. It does not add an implicit conversion.

## Current evidence and corpus impact

Fresh native Debug checks reproduced both string outputs and the accepted
forward float assignment. The backward float assignment returned exit 6.
Exact sources, commands, complete compiler output, emitted Zig, build results
and process output are preserved in
[the native evidence](../../audits/2026-09-20-core-v1/forward-globals-native.json).
The original local evidence file is:

```text
/tmp/a7-global-types-lhaddwcg/results.json
```

Compiler invocation pattern:

```bash
.venv/bin/python main.py /tmp/a7-global-types-lhaddwcg/forward_float.a7 \
  --format json --output /tmp/a7-global-types-lhaddwcg/forward_float.zig
zig build-exe /tmp/a7-global-types-lhaddwcg/forward_float.zig -O Debug \
  -femit-bin=/tmp/a7-global-types-lhaddwcg/forward_float
/tmp/a7-global-types-lhaddwcg/forward_float
```

A read-only experiment changed visitor ordering in a separate Python process.
It checked global constants and variables before function bodies. It did not
edit production files, reorder emitted declarations or implement dependency
ordering. Its four targeted cases generated the intended string formatting and
rejected both float assignments. Those candidate results were compile-only.

The same experiment checked 255 repository `.a7` files selected by `rg --files`,
excluding `tmp/` and `site/node_modules/`. Both baseline and experiment accepted
135 files. No file changed exit status or emitted Zig text. The inventory,
source hashes, per-file results, experiment source and targeted results are at:

```text
/tmp/a7-global-order-scan-c2f1txll/results.json
/tmp/a7-global-order-scan-c2f1txll/experiment.py
/tmp/a7-global-order-scan-c2f1txll/targeted-experiment.json
```

This is a measured result for that limited experiment, not a zero-impact claim
for the final fix. It excludes generated test-source strings and temporary
historical probes. It does not cover new dependency or cycle diagnostics. The
full implementation needs a fresh comparison. The experiment and its results
are now preserved in the
[implementation evidence](../../audits/2026-09-20-core-v1/README.md).

## Implementation after approval

Resolve declared global types and initializer dependencies before function
bodies. Use an explicit dependency worklist. For example, infer `FIRST` through
`SECOND` in `FIRST :: SECOND` followed by `SECOND :: "hello"`, without moving
runtime evaluation or emission. Register function signatures as today. Do not
execute initializer functions during type discovery.

Keep local declaration checking separate. Do not change `UnknownType` throughout
the compiler as part of this bounded fix. A failed global inference must produce
a located diagnostic instead of allowing unknown types to authorize operations.

The following rules still need concrete cases before final implementation:

- Distinguish dependencies needed to infer a type from dependencies between
  initializer values. Explicitly typed declarations can have known types even
  when their initializer values form an invalid cycle.
- Reject unresolved inference cycles and name the declarations involved. Do not
  make cyclic or unsupported initializers newly executable.
- Preserve valid function calls with already-known return types in initializers.
  Generic return inference and calls that read other globals need separate
  checks for unresolved dependencies.
- Preserve the original source location when dependencies fail. Avoid cascading
  misleading type errors after the first unresolved dependency.

These are proposed implementation constraints. This packet does not select new
runtime initialization semantics or approve cyclic global values.

## Acceptance

Verify both declaration orders print `hello` in Debug and ReleaseFast. Verify
both float assignments reject with the same type rule and no output artifact.
Add direct and multi-step global dependencies, explicit globals, calls with
known return types, unknown names and inference cycles. Pair each rejection
with a valid control. Confirm emitted order stays unchanged for supported
initializers and run the corpus comparison plus the full release gate.
