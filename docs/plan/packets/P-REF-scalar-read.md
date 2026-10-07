# P-REF: ordinary scalar reads through references

Status: proposed, not approved. This packet asks for a bounded scalar-read
contract. It changes accepted programs and printed output, so implementation
requires an explicit disposition in the [decision ledger](../decisions.md).
It selects no automatic-memory mechanism and introduces no public address-of or
dereference operator.

## Current behavior and evidence

The strict `heap_scalar_write_through` row in
[test_stage_boundary.py](../../../test/test_stage_boundary.py) expects `5\n`:

```a7
io :: import "std/io"
main :: fn() {
    p := new i32
    if p == nil { ret }
    p = 5
    io.println("{}", p)
    del p
}
```

Its defect text records the prior observation that printing produces an address
representation such as `i32@...`, while the referent cannot be read as a scalar.
That is the test's recorded native observation, not a new native run for this
packet. This review performed compile-only probes on CPUs 12-15. The current
pipeline accepts the program and emits these Zig statements:

```zig
p.?.* = 5;
__a7_stdout_print("{any}\n", .{p});
```

The write dereferences p; the print passes the reference itself. Source evidence:
[type-checker assignment handling](../../../a7/passes/type_checker.py),
[Zig implicit dereference and print lowering](../../../a7/backends/zig.py),
and [safety proof handling](../../../a7/passes/safety.py).
`_io_call_text` emits the argument expression unchanged, and
`_format_spec_for_arg` falls back to `any` for ReferenceType. This mechanism
explains the recorded pointer output. No native build or execution was repeated.

Eight compile-only probes confirmed this boundary after `p := new i32`, a nil
exit guard, and `p = 5`:

| Expression | Current result |
| --- | --- |
| `io.println("{}", p)` | Exit 0; prints reference expression in generated Zig |
| `v: i32 = p` | Exit 6: `Type mismatch: expected 'i32', got 'ref i32' (Variable 'v')` |
| `v := p + 1` | Exit 6: `Requires numeric type: got 'ref i32'` |
| `v := p == 5` | Exit 6: `Operator requires compatible types (eq between ref i32 and i32: the operands have different types)` |
| `q := p; v := p == q` | Exit 0; reference identity comparison |
| `read(p)` where `read` takes i32 | Exit 6: `Argument type mismatch: expected 'i32', got 'ref i32' (Argument 1)` |
| `mutate(p)` where `mutate` takes ref i32 | Exit 0 |
| `q := p` | Exit 0; reference alias |

The local archive `tmp/v1-completion-2026-10-07/scalar-ref-packet/` contains source,
generated Zig and `results.json`, including source hashes and the imported
package path. It is an ignored local archive, not a publication link. The table
and snippets above preserve the decision evidence without depending on it.

## Existing authority and unresolved choice

[SPEC reference semantics](../../SPEC.md#35-reference-semantics) describes ordinary
lvalues passed to `ref` parameters and compiler-inserted internal reference
operations. It excludes public address-of and dereference operators.
[SPEC parameter rules](../../SPEC.md#63-function-parameter-immutability) keep
parameter bindings immutable while permitting writes to referenced storage.
Those rules remain constraints on every alternative below.

L74 approved rejection of nil field access and deleted aliases while preserving
guarded accesses, independent allocations and reassignment controls. It did not
choose automatic scalar reads, reference printing, or value-versus-identity
comparison. A strict test expectation identifies the intended output of one
case; it does not settle the rest of this language contract. L6's immutable
argument-binding rule also remains in force. No prior approval is treated as
permission to introduce a public dereference spelling.

## Recommended bounded contract for a decision

Permit one checked scalar load from `ref S` in scalar-consuming contexts, where
S is a fixed-width integer, `usize`, `isize`, f32, f64, bool or char. The load
requires a proven non-nil, live reference. Reference-preserving contexts keep the
reference value. This proposal covers the same load rule in both heap locals and
ref parameters; it does not make ref parameter bindings assignable.

```a7
io :: import "std/io"
read :: fn(x: i32) { io.println("{}", x) }
mutate :: fn(x: ref i32) { x = 6 }
main :: fn() {
    p := new i32
    if p == nil { ret }
    p = 5
    q := p
    saved: i32 = p
    io.println("{}", p)
    read(p)
    mutate(p)
    io.println("{} {}", saved, p)
    io.println("{} {}", p == 6, p == q)
    del p
}
```

Proposed successful-allocation output:

```text
5
5
5 6
true true
```

Allocation failure still takes the early return and produces no output. `saved`
is a copied i32 and remains 5 after mutation; q aliases p and must not be deleted
again. The example is proposed behavior, not executed evidence.

| Context | Proposed behavior | Compatibility effect |
| --- | --- | --- |
| Concrete scalar initialization or assignment (`v: i32 = p`, `v = p`), scalar return, concrete scalar parameter | Load once, then apply existing scalar fit/conversion rules | Previously rejected reference-to-value forms become accepted when proven safe |
| Arithmetic, scalar ordering, mixed reference/scalar equality in either operand order | Load the scalar reference operand; retain normal operand-type rules | `p + 1`, `p < 7`, `7 > p`, `p == 5`, `5 == p` gain scalar meaning |
| Scalar compound-assignment right operand (`v += p`) | Load the right operand; preserve existing target rules | Newly accepts a proven scalar load; `p += 1` remains existing write-through |
| Unary numeric negation, boolean `not`, bitwise-not | Load once, then apply existing operator/type rules | `-p`, `not p`, `~p` follow their scalar equivalents |
| Match scrutinee of scalar-reference type | Load once, then apply existing scalar pattern and exhaustiveness rules | Numeric, bool and char matching gain the same scalar value used by operators |
| Bool condition with `ref bool` in `if` or loops | Load bool after a non-nil proof | Heap locals need a guard; checked ref parameters already have the boundary proof |
| Ordinary print argument of `ref S` | Load S; select its existing scalar formatter | Address output changes to value output; no address-print replacement is included |
| `q := p`, inferred const/return-generic argument, explicit `ref S` destination | Preserve reference identity | Existing alias construction stays valid |
| `p == q`, `p != q` for compatible references | Compare identities; no scalar load | Equal-valued distinct allocations remain unequal |
| `p == nil`, `p != nil` | Compare nullness | Existing guards remain unchanged |
| Argument to `ref S`, `del p` | Preserve reference/lifetime operation | No copied scalar can replace the reference here |
| Local `p = 5` | Existing write-through | Continues to change referenced storage |
| Local `p = q` or `p = nil` where rebinding is allowed today | Preserve existing reference assignment rules | Does not become a scalar copy assignment |

Inference therefore remains deliberate: `q := p` is an alias; `q: i32 = p` is a
scalar copy. A generic `fn($T)` argument still infers `ref S` from p because there
is no concrete scalar expectation. A generic callback instantiated with a
concrete S must follow the concrete parameter rule after binding, without
mutating a shared AST across instantiations. A constrained generic still infers
`ref S` from the argument. No load is inserted to satisfy a constraint such as
`Numeric`, so a constraint excluding references rejects that instantiation.

Both-reference arithmetic such as `p + q` loads both scalar referents, but
both-reference equality preserves identity. To compare their scalar values,
use explicit scalar copies before comparison. Ref-versus-ref ordering remains
rejected; it must not silently become address ordering. These asymmetries are
part of the proposed compatibility contract and require approval.

## Safety, diagnostics and scope limits

A nil guard proves nullness only. It does not revive an allocation deleted
through p or an alias. Every inserted load participates in the existing safety
pass before Zig emission. Unguarded or deleted scalar loads must exit 6, using
the existing primary diagnostic families `Reference not proven non-nil` and
`Use after move or delete`. The implementation must not defer these failures to
Zig, print a pointer as fallback, or manufacture a default scalar value.

A scalar copy has no ownership of the allocation. Loading does not consume the
reference, allocate another object, free memory or extend its lifetime. Deleting
p invalidates reference aliases but cannot invalidate an already copied integer.
Preserve evaluation order: a scalar operand evaluated before a later deleting
call retains its copied value; a later scalar load from the deleted reference
fails. Existing scalar borrowing invalidation rules remain unchanged.

This proposal does not add recursive dereference. `ref ref i32`, reference-to-
record/slice/string/function/enum reads, reference selection through untracked
containers, and an address-printing interface are outside the proposed new
contract. Their existing behavior remains unchanged. Cast contexts and index
contexts load once when the reference has the required concrete scalar referent;
all existing cast/range/usize obligations still apply. A nil proof alone does
not establish a valid index or safe narrowing conversion.

For an assignment target that itself is a ref parameter, current parameter
immutability and write-through rules remain authoritative. Approval does not
permit pointer rebinding through an immutable argument binding. Implicit borrow
of an ordinary scalar lvalue into a ref parameter also remains unchanged.

## Alternatives

| Choice | Result for the original program | Scope and cost |
| --- | --- | --- |
| Approve the bounded scalar-consuming contract above | Prints `5\n` on successful allocation | Fixes scalar reads consistently; changes print and accepted expression semantics; preserves explicit reference contexts |
| Change only scalar-reference printing | Prints `5\n` on successful allocation | Smaller formatter special case; typed reads, arithmetic and scalar calls remain unavailable; cannot claim a general scalar-read repair |
| Keep reference expressions unchanged | Retains pointer representation | Requires explicitly rejecting the stage test's expected value contract; leaves ordinary heap-scalar reads unresolved |

The recommended choice is the bounded scalar-consuming contract, including its
explicit alias and identity-comparison exceptions. It remains a proposal.
No alternative authorizes public `.adr`, `.val`, prefix address-of, or prefix
dereference syntax.

## Conditions for implementation acceptance

An approval must identify the chosen alternative and any changes to the context
table. Record that disposition before compiler edits. The delivery roadmap and
STATUS retain work tracking; this packet creates no separate TODO ledger.

For the bounded choice, acceptance requires semantic exit 6 for nil/deleted loads,
the original stage row's value output, scalar-copy-versus-alias controls,
identity-versus-value comparison controls, immutable parameter/borrow controls,
and argument-order controls. Cover declaration and later assignment, compound
assignment, unary operators, both mixed operand orders, scalar match and bool
conditions. Test numeric, bool and char formatters and concrete versus generic
call contexts, including constraints that reject reference types. Valid native controls must run debug, release and
fast; no unsafe program needs native execution. Remove the strict xfail only
when the chosen behavior passes, and update SPEC and public documentation to
state the approved rules. None of these implementation checks ran for this packet.
