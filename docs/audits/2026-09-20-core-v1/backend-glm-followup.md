# Backend follow-up to GLM review 1

D1 has an isolated repair with passing native tests. D2 remains open. These
results do not replace the external review's `CHANGES REQUIRED` verdict or
establish complete backend qualification.

## D1: nonvoid loop update

The independent reproduction accepts this A7 source, then Zig rejects
`step()` in the loop update because its `i32` result is ignored:

```a7
io :: import "std/io"
step :: fn() i32 { io.println("step"); ret 1 }
main :: fn() {
    i: i32 = 0
    for i = 0; i < 3; step() {
        io.println("body {}", i)
        i += 1
    }
    io.println("done")
}
```

The [patch](backend-glm-evidence/d1.patch) adds the existing void-type check to
`_emit_statement_as_expr`. Nonvoid expression statements discard their result
in generated Zig, matching ordinary expression statements and deferred calls.
The void control keeps its existing output.

[Before evidence](backend-glm-evidence/before.json) records compiler exit 0 and
Zig exit 1 for D1. [After evidence](backend-glm-evidence/after.json) records
compiler and Zig exit 0 for both return types, with identical stdout. Additional
native regressions check that `continue` executes the update once and `break`
skips it. Both Debug and ReleaseFast must produce exact expected output.

The isolated command was:

```bash
python -m pytest test/test_glm_for_update.py test/test_v1_backend_regressions.py -q
```

[Result](backend-glm-evidence/tests.log): 12 passed.
[Hashes](backend-glm-evidence/hashes.json) identify the isolated backend before
and after the repair, plus its new test. The patch was not applied to the active
checkout during these checks. Integration and external review remain separate.

## D2: constant usage and shadowing

Both independent probes compile through A7 with exit 0 and fail Zig. Sources
and exact diagnostics are retained in the
[before record](backend-glm-evidence/before.json).

The sibling-scope probe fails with `unused local constant` for the first `y`:

```a7
io :: import "std/io"
main :: fn() {
    if true { y :: 2 }
    if true { y :: 3; io.println("{}", y) }
}
```

The nested-scope probe fails with `local constant 'y' shadows local constant
from outer scope`:

```a7
io :: import "std/io"
main :: fn() {
    y :: 2
    { y :: 3; io.println("{}", y) }
    io.println("{}", y)
}
```

The first repair's function-wide name set cannot distinguish declarations
named `y`. Existing preprocessing does not provide a usable constant annotation:
`_mark_usage` only marks variables and parameters, using the same flat name set;
`_resolve_shadowing` only registers variables. The backend's existing name
registration can help rename constants but does not determine whether a
specific declaration is used.

A separate bounded repair must track which declaration each use refers to.
Its tests must cover sibling and nested blocks, initializers before the new
binding exists, loop and match captures, array-size/type references, and name
restoration after scope exit. Some existing unbraced and switch emission paths
also lack the scope handling used by ordinary blocks. Blanket discards or the
existing `is_used` flag are not a reliable fix.

No D2 patch is included. The batch must not claim that constant usage or
shadowing is fully handled. D2 remains in the controller's open-finding and
release-blocker reconciliation.
