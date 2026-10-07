# P-REF: bounded reference safety repair

Approved on 2026-10-07 under [L74](../decisions.md). The user replied:
"Approve these rejection rules and preserve the valid controls".
This record preserves the approved contract; it does not assert that all alias
paths or current-source verification are complete.

| Previously accepted pattern | Approved result |
| --- | --- |
| `h := Holder{ptr: nil}; h.ptr.value = 7` | Semantic exit 6 at the nil field access |
| `del h.child; del h.child` | Semantic exit 6 at the repeated deletion |
| `c := b; del b; io.println("{}", c.value)` | Semantic exit 6 at use of the deleted allocation |
| `c := b; del b; del c` | Semantic exit 6 at deletion of the same allocation through its alias |

The original probes accepted all four patterns before the repair. They were
compiler-only observations, not executed unsafe programs. Their source and
results remain in the host-local archive
`tmp/v1-completion-2026-10-07/safety-proposals/`.

Required valid controls are guarded user-field access, a single field deletion,
a field reassigned to a fresh allocation before another deletion, aliases used
before deletion, distinct allocations, independently allocated fields, and an
alias reassigned to a fresh allocation after deleting its old value.
[Test controls](../../../test/test_safety_reference_identity.py) exercise these
requirements. Guard and allocation facts must follow the current stored value;
reassignment must not revive aliases to a deleted allocation.

The change keeps existing `new` and `del` syntax. It selects no automatic-memory
mechanism or ownership annotation. A broader rejection of valid programs needs
a separate concrete compatibility decision. Branches, loops, deferred cleanup,
container aliases and callee effects need their own evidence before completion
claims. See the [qualification boundary](../../audits/2026-10-07/qualification.md).
