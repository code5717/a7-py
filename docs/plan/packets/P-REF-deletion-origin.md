# P-REF: deletion of borrowed storage

Status: presented for a user decision on 2026-10-17, not approved. This packet changes which programs pass semantic
checking. It requires an explicit disposition under the repository's language
change rule. L74 covers use after deletion and repeated deletion, but does not
settle the first deletion of an implicit stack or inline borrow.

## Current behavior

Eight initialized controls all return exit 0 in both semantic and compile/emission
modes. The 16 commands include heap and heap-alias deletion, stack and inline
deletion, stack and inline mutation, nil deletion, and deletion of a separately
allocated child through a borrowed stack holder.

All 43 compiler/entry-point source files in the isolated snapshot matched the
live checkout before and after execution. The evidence packet pins the complete
1,722-file snapshot and all emitted files. Its source manifest SHA256 is
`e808e1ba04dd16c693049dc3c3e9c8da6166087adbafda2b53d49fe669d2171d`.
See [execution evidence](../../../tmp/v1-completion-2026-10-17/deletion-origin-current/verification.json).

The generated Zig passes `&local` or `&h.?.inner` to `drop`, which emits
`allocator.destroy` on that pointer. Neither operation recovers the separately
allocated whole object. These are observed generated statements, not native
execution results. No native program ran in this experiment.

## Proposed rule

Reject a reachable `del` when its reference denotes a stack object or an inline
subobject. Report semantic exit 6. Apply the rule through calls and aliases using
the actual argument's storage origin. A function accepting `ref Box` may still
delete a separately allocated Box passed by its caller.

```a7
Box::struct{value:i32}
drop::fn(p:ref Box){del p}
main::fn(){local:=Box{value:7};drop(local)}
```

The proposed result is exit 6 at the call/deletion path: local is stack storage.
Passing an inline Box field to drop has the same proposed rejection:

```a7
Box::struct{value:i32}
Holder::struct{tag:i32;inner:Box}
drop::fn(p:ref Box){del p}
main::fn(){
 h:=new Holder;if h==nil{ret}
 h.tag=3;h.inner=Box{value:7}
 drop(h.inner)
}
```

An inline subobject remains an invalid deletion target even when its address
coincides with the start of its owner. The permitted target is the whole object
created by `new`, with its allocated type.

## Preserved behavior

This program must remain accepted:

```a7
Box::struct{value:i32}
drop::fn(p:ref Box){del p}
main::fn(){p:=new Box;if p==nil{ret};p.value=7;drop(p)}
```

Preserve heap aliases, forwarding through reference parameters, and deletion
through a reference-valued field that contains a separate allocation. Preserve
ordinary reads and writes through stack and inline borrows. Keep current nil
behavior. Existing repeated-deletion and use-after-deletion rules still apply.

A mixed-origin value must reject if a reachable deleting path can select a
proven borrowed object. A branch that cannot execute the deletion must not
cause rejection. Unknown provenance alone is outside this bounded proposal:
it does not authorize rejecting every unresolved parameter, global or return
value. Remaining unknown-origin enforcement stays an explicit release gap.

## Alternatives and compatibility

Keeping current acceptance leaves the backend able to destroy borrowed storage.
A runtime ownership tag could distinguish valid allocation targets, but would
require a separate reference representation, ABI and runtime-failure decision.
Deleting an inline view must never silently delete its enclosing owner.

The static rejection changes existing program acceptance without changing
`new`, `del` or ordinary `ref` argument syntax. It does not choose automatic
memory management or alter valid heap cleanup.

## Acceptance evidence required after approval

- Stack and inline deletion reject with exit 6, directly and through aliases,
  forwarding calls, reachable branches and deferred cleanup.
- Whole heap deletion stays accepted through aliases, parameters and reference
  fields, including a reference field inside a borrowed stack holder.
- Borrowed mutation and guarded reads stay accepted.
- Nil behavior and unreachable deletion paths keep their current behavior.
- An inline field at offset zero is still rejected as a deletion target.
- Saved views become invalid when their actual owner is deleted. Type differences
  between views must not erase their shared owner lifetime.

Run semantic, compile/emission and appropriate native valid controls on a pinned
source. Do not use native execution of an invalid allocator operation as the
acceptance test for rejection.
