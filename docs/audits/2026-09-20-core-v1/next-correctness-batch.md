# Next correctness batch

These are follow-up designs, not implemented fixes or new language approvals.
The final release gate runs against an unchanged compiler while these findings
are recorded.

## Unused loop labels

Resolve labeled break and continue statements to the nearest matching enclosing
loop in an iterative traversal. Track targeted loop identities, not label text.
Emit unique Zig labels only for targeted loops. Skip nested function bodies.
Cover while, C-style for, for-in and indexed for-in. Native checks must include
unused labels, reused names, transfers to outer loops and update side effects.
This repairs a native build failure without changing working source behavior.

## Constant bindings

Resolve uses to declarations. Preserve outer-binding lookup during an initializer
and restore bindings after nested scopes. Include type names and array bounds.
The current function-wide name set cannot distinguish sibling declarations, and
type-name emission bypasses value renaming. Match and unbraced scopes also need
review. A blanket discard does not fix this defect.

A scoped pending-discard approach can count actual emitted uses after each
initializer and finalize at the owning scope exit, before a sibling reuses the
same generated name. Resolve marker lines once when assembling output. Do not
put discard statements after a return or repeatedly rewrite the whole output.
Type identifiers, struct construction and noncapture match patterns must use the
same binding lookup. Match captures and expression scopes also need explicit
binding registration. This design is not implemented or verified.

Tests must cover sibling unused constants, nested constant/variable shadowing,
outer bindings in initializers, loop/match captures, type-only references and
exactly-once side effects in unused initializers.

## Fallthrough safety

The current safety pass resets every match arm to facts from before the match.
A falling arm can therefore set a divisor to zero while the next arm still sees
an old nonzero fact. Carry facts and deleted-binding state along fallthrough
edges after scope cleanup. Join only reachable direct and fallthrough entries.
Preserve deferred effects. Only paths that finish normally contribute to the
match exit.

An isolated naive join rejected the original unsafe case and deferred mutation,
and retained two safe controls. It also rejected a valid control where the
falling case is unreachable. The current native Debug program prints `2`.
See [the five probes](saf3-design-results.json). The experiment is not applied.
A candidate must preserve proven reachability and pass compatibility checks.
Any remaining rejection of working programs needs a concrete approval packet.

A later integer-reachability prototype retained the original safe control but
rejected its enum equivalent, which currently builds and prints `2`. The
[candidate report](saf3-candidate-evidence/REPORT.md) preserves the source and
results. Its patch is explicitly not ready to apply. Enum selection needs a
sound known-value fact before that candidate can preserve working programs.

Typed enum facts later preserved that local control and handled direct, branch,
reference-call, deferred and loop mutations. Calls that change globals still
leave stale facts. Clearing global enum facts on every call rejects a valid
empty-function control that prints `2` in both profiles. The
[enum experiment](saf3-candidate-evidence/ENUM-REPORT.md) records this remaining
call-effect blocker. Neither candidate stage is applied.
