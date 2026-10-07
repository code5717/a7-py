---
title: Memory and references
nav: Memory
group: Reference
summary: Allocation, references, nil guards, cleanup, and safety enforcement.
order: 19
---

# Memory and references

Values copy by value. Heap allocations use `new T` and need explicit cleanup with `del` or `defer del`. A7 is not a sandbox, and its current safety checks do not amount to a complete ownership system.

## Allocation and nil guards

The repository memory example uses this allocation pattern:

```a7
value_box := new Box
if value_box == nil {
    io.println("allocation failed")
    ret
}
defer del value_box
value_box.value = 42
```

This excerpt assumes the example's `Box` struct and `io` import. `new` is treated as maybe nil. The early return proves that subsequent field access uses a non-nil reference. Unproved access is rejected.

## Reference access

1. `new Box` produces a reference that may be nil.
2. The nil branch exits before any field access.
3. The surviving branch accesses `value_box.value` and schedules `defer del value_box`.

The guard supplies the non-nil fact used by the safety pass. Cleanup ends the allocation lifetime; complete alias analysis remains unfinished.

## Reference parameters

Pass an ordinary lvalue to a `ref T` parameter. The compiler inserts internal reference operations. Access a reference's fields with ordinary `.` after nil proof. There is no public address-of or dereference syntax, and no public borrow, mutate, or consume mode.

| Step | Binding or storage | Effect |
| --- | --- | --- |
| Caller declares `counter` | Value struct in caller storage | Owns the current field value |
| Caller uses `increment(counter)` | Function accepts `ref Counter` | Compiler passes checked access to that storage |
| Callee updates `counter.value` | Same field in caller storage | Caller observes the update |

This complete program prints `42`. The caller and function access the same
struct storage.

```a7
io :: import "std/io"

Counter :: struct {
    value: i32
}

increment :: fn(counter: ref Counter) {
    counter.value += 1
}

main :: fn() {
    counter := Counter{value: 0}
    counter.value = 41
    increment(counter)
    io.println("{}", counter.value)
}
```

This demonstrates reference passing, not a general alias-safety guarantee.

## Deletion, defer, and lifetimes

Branch joins, loop mutations, reference calls, and deferred effects invalidate
stale facts. A guard before a mutation or call may no longer prove a later
operation. These checks do not provide complete alias or lifetime analysis.

`del` releases supported heap allocations. Direct reference aliases share
deletion state; repeated deletion and reads after deletion fail until fresh
reassignment. Guarded reference fields receive the same nil checks, including
user fields named `ptr`. `defer` schedules a statement for scope exit;
`defer del value_box` keeps cleanup next to allocation.

Known direct stores into global references propagate allocation identity
through calls. Deleting the stored allocation invalidates tracked caller
aliases. Simple direct calls with literal boolean selectors preserve a selected
reference or nil return. A nil result needs its own guard before field access.
Broader return paths, global nil-state summaries and callee non-nil requirements remain
incomplete. Alias tracking also has gaps for array elements, selected or joined
field paths, nested aggregates, borrowed aggregates and direct deletion of call
results. Accepted programs can still violate allocation lifetimes.

Represented readonly calls reject known nil field reads across branches,
read-only defers and certified loops. The executable-entry check evaluates the
original entry file's parameterless `main` against its complete readonly summary.
A proved reachable nil read adds semantic exit 6 after ordinary safety checks.
Imported or nested functions named `main` do not replace it; `--lib` has no
implicit execution root. Unknown or incomplete summaries do not supply a proof.
Effectful entries, ordered mutation and general caller-local truth remain open.
The entry diagnostic includes the originating callee line and column, but not
its filename. The [entry qualification record](https://github.com/code5717/a7-py/blob/master/docs/audits/2026-10-07/readonly-entry-verification.json)
identifies the checked snapshot and remaining limits.

Slices must not outlive their backing arrays, and references must not outlive referents. These are required programming constraints. Full ownership, alias tracking, and lifetime enforcement remain incomplete. There is no implicit deep-copy guarantee.

## Safety checks and remaining gaps

| Operation | Current required evidence |
| --- | --- |
| Cast | Classified primitive conversion and safe range |
| Division or remainder | Nonzero divisor |
| Index | Valid `usize` or non-negative literal and in-bounds position |
| Slice | Ordered bounds within the length |
| Reference field access | Non-nil reference |
| Backend lowering | Approval for that particular operation |
| Tracked reference use after deletion | Referenced allocation has not been deleted |

Status: limited. Runtime shift checks and wrapping signed minimum-value arithmetic
are implemented. Union discriminant proofs and complete ownership analysis
remain unfinished. The safety contract states required behavior and lists
implementation gaps; it does not guarantee that every accepted program is safe.

## Planned memory model

Automatic memory management and a non-null versus optional reference split are planned. They do not describe today's `ref T` semantics. Heap fixed arrays using `new [N]T` are unavailable. Use the current examples until a language change is approved.

## Evidence

- [examples/011_memory.a7](https://github.com/code5717/a7-py/blob/master/examples/011_memory.a7)
- [examples/013_pointers.a7](https://github.com/code5717/a7-py/blob/master/examples/013_pointers.a7)
- [examples/024_defer.a7](https://github.com/code5717/a7-py/blob/master/examples/024_defer.a7)
- [docs/SAFETY_CONTRACT.md](https://github.com/code5717/a7-py/blob/master/docs/SAFETY_CONTRACT.md)
- [docs/plan/memory.md](https://github.com/code5717/a7-py/blob/master/docs/plan/memory.md)

## Related topics

[Language overview](../language.md) · [Current status](../status.md) · [Examples](../examples.md)
