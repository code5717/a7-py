# A7 Compiler Safety Contract

A7 is safe only when the compiler can prove that generated code cannot trap,
miscompile, or rely on unchecked target-language behavior. The compiler must
fail closed: if a risky operation has no proof, semantic analysis rejects the
program before Zig code is emitted.

This contract covers compiler safety, not sandboxing. A compiled A7 program can
still access whatever the host process and Zig toolchain allow.

## Pipeline Ownership

The frontend stages have separate responsibilities:

1. **Type checking** resolves base types, symbols, signatures, and literal
   values. It does not decide whether a risky operation is safe.
2. **Semantic validation** rejects illegal source constructs such as recursion,
   invalid `del`, unsupported imports, and non-runnable syntax.
3. **Safety proof analysis** tracks internal facts and collects obligations for
   risky operations.
4. **Proof discharge** either proves an obligation or emits a compile-time
   diagnostic.
5. **Backend planning** records the exact approved lowering for codegen.
6. **Zig codegen** consumes the `BackendPlan`; it must not independently accept
   an unsafe lowering.

## Internal Facts

Facts are internal compiler data, not public language types. The safety pass may
track:

- integer intervals and non-zero values
- known array, slice, and string lengths
- nil/non-nil reference state
- initialized, moved, and deleted bindings
- enum or union discriminants
- operation-specific backend approvals

Facts can be learned from literals, type information, guards, early returns,
loop shapes, and previous statements. If a fact is invalidated or unknown, the
compiler rejects the dependent operation.

## Risky Operations

| Operation | Required proof | Backend approval |
| --- | --- | --- |
| Numeric cast | primitive cast is classified and range-safe | `cast` |
| Division or modulo | divisor is non-zero | `div`, `mod`, `div_assign`, `mod_assign` |
| Indexing | index is `usize` or a non-negative literal, and `0 <= index < len` | `index` |
| Slicing | `0 <= start <= end <= len` | `slice` |
| Ref field access or dereference | reference is proven non-nil | `deref` |
| Assignment through ref | target reference is proven non-nil | `deref` |
| Use after `del` | deleted binding is not read again before reassignment | semantic rejection |
| Fixed-width integer arithmetic | result range is proven in-bounds | `arithmetic` |
| Union payload access | active discriminant is proven | union approval |

The current implementation enforces cast, division/modulo, index, slice, ref
deref, operation-specific backend approvals, and direct use-after-`del` checks.
Full fixed-width arithmetic, union discriminant proofs, and complete ownership
analysis remain active compiler-safety work.

## Reference Surface

Public address and dereference syntax is intentionally absent. Users do not
write `.adr`, `.val`, prefix `&`, prefix `*`, or public borrow/mutate/consume
modes. Ref arguments are passed as ordinary lvalues, and ref struct fields are
accessed directly after nil-proofing.

Today `ref T` remains the nullable heap-reference surface accepted by examples.
The planned split is:

- `ref T`: proven non-null reference
- optional `ref T`: maybe-null reference
- `nil`: assignable only to optional refs
- `new T`: returns an optional ref

Until that split lands, the safety pass treats `new` and `nil` references as
maybe nil and requires proof before field access or dereference.

## Ownership Surface

The current public model stays simple:

- value types copy by value
- heap refs created by `new` must be cleaned up with `del` or `defer del`
- direct use after `del` is a compile-time error
- assignment after `del` reinitializes the binding
- implicit deep copy is not provided

The next ownership phase will make heap refs affine, reject conflicting mutable
aliases, and add explicit stdlib `clone` behavior for deep copies.

## Backend Rule

Codegen must call `BackendPlan.require(node, operation)` before lowering any
approved risky operation. Approval is operation-specific: a node approved for
`index` is not approved for `cast`, `deref`, or any other lowering. Missing or
wrong approvals are compiler bugs and must fail codegen.
