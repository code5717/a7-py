# Compiler Safety Contract

A7 fails closed: if an operation can trap, miscompile, or rely on unchecked Zig
behavior, the compiler must prove it safe or reject the program before codegen.

The safety pipeline is:

```text
base type checking -> semantic validation -> safety facts -> obligations -> proofs -> BackendPlan -> Zig codegen
```

Type checking resolves base types and symbols. Safety proof analysis owns facts
such as integer intervals, non-zero values, known lengths, nil/non-nil refs,
moved/deleted bindings, and discriminants. Codegen consumes `BackendPlan` and
does not independently approve risky operations.

## Current Enforced Obligations

| Operation | Required proof | Backend approval |
| --- | --- | --- |
| Numeric cast | classified primitive cast plus required range proof | `cast` |
| Division/modulo | divisor is non-zero | `div`, `mod`, `div_assign`, `mod_assign` |
| Indexing | index is in bounds | `index` |
| Slicing | `0 <= start <= end <= len` | `slice` |
| Ref field access/deref | reference is proven non-nil | `deref` |
| Direct use after `del` | binding is reassigned before reuse | semantic rejection |

Backend approval is operation-specific. A node approved for `index` is not
approved for `cast`, `deref`, or any other lowering.

## Public Reference Surface

Users do not write `.adr`, `.val`, prefix `&`, prefix `*`, or public
borrow/mutate/consume keywords. Ref arguments are passed as ordinary lvalues,
and ref struct fields are accessed directly after nil-proofing.

`ref T` is still the accepted nullable reference surface in current examples.
The planned nullability split is `ref T` for proven non-null references and an
optional ref spelling for maybe-null references. Until then, `new` and `nil`
references are tracked internally as maybe nil and must be checked before field
access.

## Ownership Direction

Current enforcement rejects direct use after `del`, and assignment after `del`
reinitializes the binding. The next ownership phase will make heap refs affine,
reject conflicting mutable aliases, and add explicit stdlib `clone` behavior
for deep copies. A7 does not provide implicit deep copy for heap graphs.
