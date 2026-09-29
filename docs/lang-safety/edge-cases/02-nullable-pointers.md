# Gap 02 — Nullable pointers (`ref T` vs `?ref T`)

Status: Phase A research from before 2026-09-14, not a decision. Decisions are in the [ledger](../../plan/decisions.md); the [memory plan](../../plan/memory.md) (L15, L17–L22) proposes optionals in place of `nil` references.

Audit finding: [`../07-language-review.md` §1.1](../07-language-review.md#11-pointer-types--ref-t-is-nullable-by-default).
Phase C decisions were to land in [`../08-decisions.md`](../08-decisions.md).

## Summary

In Phase A, `ref T` was nullable by default and lowered to Zig `?*T`.
Every dereference emitted `.?.*`, which panics on null in `ReleaseSafe`
and is undefined behavior in `ReleaseFast`.

The contract asks the type system to track nullness, so that
dereferencing a non-null `ref T` lowers to a bare `p.*` with no `.?`.
This file lists every place a pointer can appear and decides, per site,
how nullness is tracked.

## Current behavior (2026-09-16)

Note (2026-09-16): two later changes affect this file. Evidence is a
source read on 2026-09-16; no program was compiled in this session.

**1. A safety pass now guards dereference.** `ref T` is still nullable,
but the compiler rejects a dereference it cannot prove non-nil.

- `ReferenceType` is still documented as "can be nil"
  (`a7/types.py:210-226`). The backend still emits `?*T`
  (`a7/backends/zig.py:2101-2104`) and `.?.*` (`zig.py:1735`, `1742`).
- Field access, dereference and assignment through a reference each need
  a non-nil fact (`a7/safety.py:319-325`, `427-433`, `441-443`,
  `610-629`).
- `new` and the `nil` literal produce "maybe nil" facts (`safety.py:452-453`,
  `493-494`). A `ref` parameter is assumed non-nil (`safety.py:482-483`).
- `if p != nil { ... }` proves `p` inside the branch. `if p == nil { ret }`
  proves `p` after the `if` (`safety.py:663-668`, `698-702`). `match` does
  not narrow (`safety.py:372-378`).
- `docs/SAFETY_CONTRACT.md` ("Reference Surface") plans the split this file
  describes: `ref T` proven non-null, optional `ref T` maybe null, `nil`
  only for optional refs, and `new T` returning an optional ref.

**2. The memory plan proposes a different direction.** It is proposed,
not approved; its gates are pending.

- Absence uses optionals instead of `nil` references.
- `ref` locals, returns and struct fields are removed (gate M4). `ref`
  parameters stay, as permission to change the caller's value.
- The keywords `new`, `del` and `nil` are removed or reserved.

Under that plan, N-01, N-02, N-05 to N-13, N-19 and N-22 describe a
surface that would go away. N-03, N-04 and N-18 (parameters and
receivers) stay relevant.

## Subcases

| # | Site | Phase A: today | Phase A: treatment |
| --- | --- | --- | --- |
| N-01 | Local `p: ref T = new T{...}` | `?*T`, deref `.?.*` | `*T`, deref `p.*` |
| N-02 | Local `p: ?ref T = nil` | `?*T`, deref `.?.*` | `?*T`, deref only inside `match` or `if let` |
| N-03 | Parameter `fn f(p: ref T)` | Nullable | Non-null |
| N-04 | Parameter `fn f(p: ?ref T)` | Same as N-03 | Nullable; must match |
| N-05 | Return type `-> ref T` | Nullable | Non-null; allocation failure surfaces as `-> ?ref T` |
| N-06 | Struct field `field: ref T` | Nullable | Non-null; struct init must provide a value |
| N-07 | Struct field `field: ?ref T` | Nullable | Nullable |
| N-08 | Array element `arr: [N]ref T` | Nullable; uninitialized elements? | Non-null; every element must be initialized |
| N-09 | Slice element `s: []ref T` | Nullable | Non-null; built only from fully initialized arrays |
| N-10 | Tagged-union variant carrying `ref T` | Nullable | Non-null inside the variant |
| N-11 | `nil` literal | Typed as the target pointer's nullable form | Typed `?ref Never`; unifies with any `?ref T` |
| N-12 | Cyclic data (linked list, tree) | End of chain built with `nil` | End-of-chain link is `?ref T` (literal `none`); inner links are `ref T` |
| N-13 | Lazy init: `p: ref T = compute_later()`, where the call may fail | Nullable plus a manual check | `compute_later -> ?ref T`; the user matches |
| N-14 | Function pointer `fn_ptr: ref fn(...) T` | Nullable | Non-null; the nullable form is `?ref fn(...) T` |
| N-15 | Generic `$T` instantiated with a reference type | Inherits nullability | The type set must declare `$T: nullable` or `$T: non-null`; otherwise generic code defaults to non-null |
| N-16 | `p == nil` on a non-null `ref T` | Trivially false, silently allowed | Compile error: meaningless for a non-null type |
| N-17 | `match` on `?ref T` with `case nil:` | Works | Required before deref; `case some(v):` binds a `ref T` |
| N-18 | Method receiver `fn (self: ref T) foo()` | A nullable receiver invites `.?.*` per call | Non-null receiver; nullable receivers are illegal, so the caller unwraps first |
| N-19 | `defer` on a maybe-null pointer | `defer if (p) \|q\| del q` style | Unchanged for `?ref T`; for `ref T` the defer always frees |
| N-20 | Multiple return values containing references | Each reference tracked separately | Same |
| N-21 | Function reference (`ref fn(...)`) cast to data | `cast` admits it (Gap 01) | Forbidden |
| N-22 | Builder with a partly built struct and later field writes | Stored as nullable and assigned later | A builder that returns `?T` until complete, or definite assignment proves the field is set before use (Gap 03) |

Note (2026-09-16): N-03 — the safety pass assumes `ref` parameters are
non-nil; whether a caller can pass `nil` was not checked. N-16 — the pass
uses `p == nil` as a narrowing guard. N-20 — multiple return values are
not a current backend feature (`docs/STATUS.md`). N-21 — reference and
function casts are now forbidden (Gap 01).

### Examples

Current A7 blocks use today's syntax. Compiled 2026-09-16; where a block is
rejected, the observed exit code and message are recorded in its comment.

```a7
// Current A7 (examples/011_memory.a7 pattern). N-01, N-19.
Box :: struct {
    value: i32
}

main :: fn() {
    b := new Box
    if b == nil {
        ret
    }
    defer del b
    b.value = 42
}
```

```a7
// Current A7. N-03: a ref parameter (examples/013_pointers.a7 pattern).
bump :: fn(p: ref i32) {
    p += 1
}
```

```a7
// Current A7 syntax. N-05, N-06, N-12. The memory plan (section 3) records
// that ref returns compile and that assigning to a self-referential ref
// field fails.
ListNode :: struct {
    value: i32
    next: ref ListNode
}

make :: fn() ref ListNode {
    ret new ListNode
}
```

```a7
// Current A7 syntax. N-08, N-09, N-10, N-11, N-14.
// Rejected (exit 6) when compiled with a `Box` declaration added: N-09 gives
// "expected '[]ref Box', got '[4]ref Box'" (a fixed array of references does
// not coerce to a slice), and N-14 gives "Undefined type (Type 'void')" even
// though docs/SPEC.md:192 writes `fn_ptr: ref fn() void = nil`. That is a
// SPEC/compiler disagreement, not a typo in this block.
Holder :: union {
    boxed: ref Box
    raw: i32
}

main :: fn() {
    items: [4]ref Box            // N-08
    view: []ref Box = items      // N-09
    empty: ref Box = nil         // N-11: nil needs an explicit ref type
    callback: ref fn() void = nil // N-14 (SPEC form)
}
```

```a7
// Current A7 syntax. N-15, N-16.
// Rejected (exit 6): N-15's `items[0]` gives "index bounds are not proven",
// because a slice parameter has no statically known length. N-16 compiles.
first($T) :: fn(items: []$T) $T {
    ret items[0]                 // N-15 with $T = ref Box
}

check :: fn(p: ref Box) bool {
    ret p == nil                 // N-16
}
```

```a7
// Proposed (Phase A). `?ref T`, `some` and `none` do not exist.
// N-02, N-04, N-07, N-12, N-13, N-17.
ListNode :: struct {
    value: i32
    next: ?ref ListNode          // N-07, N-12
}

find :: fn(id: i32) ?ref Box {   // N-13
    ret none
}

read :: fn(p: ?ref Box) i32 {    // N-04
    match p {
        case some(v): {          // N-17: v is ref Box
            ret v.value
        }
        case nil: {
            ret 0
        }
    }
}
```

```a7
// Proposed (Phase A). N-18, N-20, N-21, N-22.
total :: fn(self: ref Account) i64 { ... }     // N-18: non-null receiver
pair :: fn() (ref Box, ref Box) { ... }        // N-20
raw := cast(usize, callback)                   // N-21: forbidden
partial := AccountBuilder{}                    // N-22: returns ?Account until complete
```

## Interactions

- **Gap 01, cast.** C-13, C-14, C-17 and C-18 in `01-cast.md`. The
  classifier must reject any cast that creates a pointer or moves between
  non-null and nullable, except through `match`.
- **Gap 03, definite assignment.** N-08 and N-22. Definite assignment must
  prove every `ref T` field is set before it is read. N-08 (an array of
  non-null refs) is hardest: either forbid declaration without an
  explicit initializer, or require a slice-builder pattern.
- **Gap 04, NonZero division.** No direct interaction.
- **Gap 05, stack budget.** No direct interaction.
- **Gap 06, typed arithmetic.** No direct interaction.
- **Gap 07, bounded indexing.** Indexing a `[]ref T` returns a non-null
  `ref T` by the N-09 invariant, so no `.?` is needed.
- **Gap 08, `Option<T>` and `Result<T, E>`.** Is `?ref T` sugar for
  `Option<ref T>` or a separate type? See Q02a. Spelling is open under G5.
- **Gap 09, refinement-lite.** No direct interaction.
- **Gap 10, affine ownership.** Moving a `ref T` consumes it; the slot is
  effectively `?ref T` `none` until reassigned. Move analysis must track
  this state, with the same machinery as the nullability split. Note
  (2026-09-16): the memory plan makes ownership internal (ledger O2).
- **Gap 11, finite floats.** No direct interaction.
- **Gap 12, FFI.** A foreign `?*T` (Zig optional pointer) arrives in A7 as
  `?ref T`. A foreign `*T` arrives as `ref T`, but the language cannot
  enforce the foreign promise; the FFI boundary documents this.
- **Generics and type sets.** N-15. Either add `Nullable` and `NonNull`
  constraints to the type-set vocabulary, or default to non-null inside
  generics and make nullability opt-in.
- **Tagged unions.** N-10. A variant `case some(ref T)` carries a non-null
  reference; the tag itself marks nullability.
- **Match.** N-17 and N-18. Match is the only narrowing operator. Note
  (2026-09-16): today the safety pass narrows on `if`, not on `match`.

## Failure modes

### False positives

- Builders that need a half-built struct. A struct with non-null fields
  cannot be partly initialized without a `MaybeUninit<T>` or a staged
  construction rule. Phase C must pick one.
- Generic code that worked with nullable refs for every instantiation
  fails on the non-null path. Mitigation: a `?` annotation on generic
  parameters.
- Code that uses `ref T` to mean "maybe null" breaks everywhere. Migration
  is a one-time but large effort.

### False negatives

- A non-null `ref T` obtained inside `if (raw_ptr != null) { ... }`. This
  narrowing is simple to support but easy to forget in the type checker.
  Note (2026-09-16): `a7/safety.py:698-700` implements it as an internal
  fact.

```a7
// Current A7. The safety pass proves p inside the branch.
show :: fn(p: ref Box) i32 {
    if p != nil {
        ret p.value
    }
    ret 0
}
```

- FFI returns. The compiler trusts the foreign signature; if the signature
  lies, that is a documented FFI hazard.

### Ergonomic costs

- Cyclic data needs `?ref T` at exactly the link that closes the cycle.
  This is a standard pattern, shown by the linked-list and tree examples.
  Note (2026-09-16): `examples/025_linked_list.a7` and
  `examples/026_binary_tree.a7` now use indices instead of references.
- Every existing `ref T` declaration must be reclassified. A one-shot
  codemod would help.

### Performance costs

- None. A non-null deref is faster (no `.?`); a nullable deref costs the
  same as before.

## Open questions

- **Q02a.** Is `?ref T` a distinct type (the Zig approach) or sugar for
  `Option<ref T>` (the Rust approach)?
  - Distinct: a separate `?ref T` AST node. Simplest to build, and it
    matches the backend's `?*T` for references. It duplicates the `?T`
    machinery from Gap 08.
  - Sugar: `?ref T` is `Option<ref T>`. A cleaner type system, but the
    `nil` literal is harder: does it match as `Option.none` or stay its
    own keyword?
  - Note (2026-09-16): the memory plan removes `nil` and stored references,
    so neither option is the proposed direction. Optional spelling is
    open under G5.
- **Q02b.** How is the implicit non-null to nullable upcast written?
  Coercion at assignment only, an explicit `some(p)` constructor, or both?
- **Q02c.** Default for generic type parameters: nullable, non-null, or
  required to be declared? "Required" is safest but noisier; "non-null by
  default" matches the rest of the rules.
- **Q02d.** How is an array of non-null refs initialized?
  - Forbid declaration without an explicit initializer
    (`arr: [N]ref T = .{p1, p2, ..., pN}` only).
  - Allow `arr: [N]?ref T` as the only nullable-element array, plus
    `try_freeze(arr) -> ?[N]ref T` once every slot is filled.
  - Require an initializer function:
    `[N]ref T(init: fn(usize) -> ref T)`.
- **Q02e.** Builders: `MaybeUninit<T>` or staged types?
  - `MaybeUninit<T>` adds a wrapper type and an `assume_init()` rule.
  - Staged types (`Builder<T>` to `T` through a finishing call) need
    nominal types and one extra type per builder.
- **Q02f.** Is `nil == p` on a non-null `ref T` a compile error or simply
  `false`? An error is more honest; `false` is more lenient.
- **Q02g.** Method calls on `?ref T`: forbidden, or allowed through a
  chaining form (`p?.foo()` giving `?ReturnType`)?
- **Q02h.** Narrowing through `if p != null`: does `p` become `ref T`
  inside the branch, or is `if let some(q) = p` required? Note
  (2026-09-16): the current safety pass narrows `p` itself, as an internal
  fact, with no new syntax.
- **Q02i.** Does `p1 == p2` on two `?ref T` values compare addresses or
  unwrap and compare? Address comparison is standard but surprises users
  who think of `?ref T` as an `Option`.

## Source citations

Line numbers describe the Phase A tree; 2026-09-16 locations follow.

- Reference type model: `a7/types.py:210-226`, `ReferenceType`, with no
  `nullable: bool` flag. Unchanged.
- Parser: `a7/parser.py:743-751`, `TYPE_POINTER` token. Not rechecked.
- `nil` type check: `a7/passes/type_checker.py:727-733` and 674; only
  reference types accept `nil`. Now around `type_checker.py:662-736`.
- Backend emission: `a7/backends/zig.py:1682-1688`, emits `?*T` and
  `.?.*`. Now `zig.py:2101-2104` (`?*T`) and `1735`, `1742` (`.?.*`).
- Example: `build/debug/zig/src/013_pointers.zig:9`, `p.?.* += 1`, the
  running example of the unneeded `.?`. Not rechecked; the A7 source now
  passes a `ref i32` parameter.
- Examples to migrate: `examples/011_memory.a7`, `013_pointers.a7`,
  `017_methods.a7`, `019_literals.a7`, `025_linked_list.a7`,
  `026_binary_tree.a7`, `034_string_utils.a7`, `037_language_tour.a7`.
- Spec: `docs/SPEC.md` around line 188 (`nil` semantics). Not rechecked.
- Safety facts: `a7/safety.py` (see "Current behavior").

## Phase C decision inputs

Phase C must answer at least:

1. Q02a, distinct type or `Option` sugar. Drives the parser, the type
   model, error messages and how `nil` is used.
2. Q02c, the generic default.
3. Q02d, initializing arrays of non-null refs. Drives N-08.
4. Q02e, builder policy. Drives N-22.
5. Q02g, method-call chaining syntax.
6. Q02h, narrowing ergonomics.

The other questions follow from these.
