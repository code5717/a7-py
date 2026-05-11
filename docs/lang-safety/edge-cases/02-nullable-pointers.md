# Gap 02 — Nullable pointers (`ref T` vs `?ref T`)

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.1](../07-language-review.md#11-pointer-types--ref-t-is-nullable-by-default).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Today `ref T` is nullable by default and lowers to Zig `?*T`; every
deref emits `.?.*` (Zig safety-panic on null in `ReleaseSafe`, UB in
`ReleaseFast`). The contract demands the **type system** track
nullness, so deref of a non-null `ref T` lowers to a bare `p.*` with
no `.?` involved. This file enumerates everywhere a pointer can appear
and decides per-site how nullness is tracked.

## Subcases

| # | Site | Today | Treatment |
| --- | --- | --- | --- |
| N-01 | Local `p: ref T = new T{...}` | `?*T`, deref `.?.*` | `*T`, deref `p.*` |
| N-02 | Local `p: ?ref T = nil` | `?*T`, deref `.?.*` | `?*T`, deref only inside `match`/`if let` |
| N-03 | Parameter `fn f(p: ref T)` | nullable | non-null |
| N-04 | Parameter `fn f(p: ?ref T)` | (today same as N-03) | nullable; must match |
| N-05 | Return type `-> ref T` | nullable | non-null; allocation failure surfaces as `-> ?ref T` |
| N-06 | Struct field `field: ref T` | nullable | non-null; struct init must provide a value |
| N-07 | Struct field `field: ?ref T` | nullable | nullable |
| N-08 | Array element `arr: [N]ref T` | nullable; uninitialised elements? | non-null; every element must be initialised |
| N-09 | Slice element `s: []ref T` | nullable | non-null; constructible only via fully-initialised arrays |
| N-10 | Tagged-union variant carrying `ref T` | nullable | non-null inside the variant |
| N-11 | `nil` literal | typed as the target pointer's nullable form | typed as `?ref Never`, unifies with any `?ref T` |
| N-12 | Cyclic data structure (linked list, tree) | constructed with `nil` for end-of-chain | end-of-chain stored as `?ref T` (literal `none`); intermediate is `ref T` |
| N-13 | Lazy initialisation: `p: ref T = compute_later()` where `compute_later` may fail | nullable + manual check | `compute_later -> ?ref T`; user matches |
| N-14 | Function pointer `fn_ptr: ref fn(...) T` | nullable | non-null; nullable function pointer is `?ref fn(...) T` |
| N-15 | Generic type parameter `$T` instantiated with a reference type | inherits nullability | the constraint `$T: nullable` or `$T: non-null` must be declared on the type-set, otherwise generic code defaults to non-null |
| N-16 | Comparison `p == nil` on a `ref T` (non-null) | trivially false, today silently allowed | compile error: comparison is undecidable for non-null type |
| N-17 | Pattern match on `?ref T` with `case nil:` | works | required for `?ref T` deref; binding form `case some(v):` extracts a `ref T` |
| N-18 | Method receiver `fn (self: ref T) foo()` | nullable receiver invites `.?.*` per call | non-null receiver; nullable receivers are illegal — user must unwrap first |
| N-19 | `defer` on a maybe-null pointer | `defer if (p) |q| del q` style | unchanged for `?ref T`; for `ref T` the defer always frees |
| N-20 | Multiple-return-value tuple containing references | each ref tracked individually | same |
| N-21 | Reference to a function-pointer (`ref fn(...)`) cast to data | currently `cast` admits — see Gap 01 | forbidden |
| N-22 | Builder-pattern partially-constructed struct with deferred field writes | today: stored as nullable and assigned later | requires a builder pattern that returns `?T` until complete, or definite-assignment proves the field is initialised before use (Gap 03 interaction) |

## Interactions

- **Gap 01 cast.** C-13, C-14, C-17, C-18 from `01-cast.md`. The cast
  classifier must reject any cast that synthesises or moves between
  non-null and nullable except through `match`.
- **Gap 03 definite assignment.** N-08, N-22 above. Definite assignment
  must prove every `ref T` field is initialised before it's read. The
  N-08 case (array of non-null refs) is the hardest: either disallow
  declaration without explicit initialisation, or require the user to
  use a slice-builder pattern.
- **Gap 04 NonZero division.** No direct interaction.
- **Gap 05 stack budget.** No direct interaction.
- **Gap 06 typed arithmetic.** No direct interaction.
- **Gap 07 bounded indexing.** Indexing a `[]ref T` returns a `ref T`
  (non-null) by N-09 invariant — no `.?` needed.
- **Gap 08 `Option<T>` / `Result<T, E>`.** Is `?ref T` sugar for
  `Option<ref T>` or a separate type? Open question Q02a below.
- **Gap 09 refinement-lite.** No direct interaction.
- **Gap 10 affine ownership.** Moving a `ref T` consumes it; the
  consumed slot becomes effectively `?ref T none` until reassigned.
  The move analysis must track this state — it's the same machinery
  as the nullability split.
- **Gap 11 finite floats.** No direct interaction.
- **Gap 12 FFI.** Foreign returns of `?*T` (Zig optional pointer)
  cross to A7 as `?ref T`. Forein returns of `*T` (Zig non-optional)
  arrive as `ref T` — but the language can't enforce the foreign
  promise; documented in the FFI boundary.
- **Generics / type sets.** N-15 above. Either add a `Nullable` /
  `NonNull` constraint to the type-set vocabulary, or default to
  non-null inside generics and require the user to opt in to
  nullability.
- **Tagged unions.** N-10. A variant `case some(ref T)` carries a
  non-null reference. The tag itself is the nullability marker.
- **Match.** N-17, N-18. Match is the only narrowing operator.

## Failure modes

### False positives

- Builder patterns that legitimately need a half-built struct. A
  struct with non-null fields can't be partially initialised without
  some form of `MaybeUninit<T>` or staged-construction discipline.
  The Phase C decision must pick one.
- Generic code that previously worked with nullable refs across all
  instantiations will fail on the non-null path. Mitigation: a
  `?` annotation on generic parameters.
- Code that uses `ref T` as "maybe-null" idiomatically will break
  en masse. Migration is a one-time but large effort.

### False negatives

- A non-null `ref T` obtained from an `if (raw_ptr != null) { /* p:
  ref T from this branch */ }` narrowing — straightforward to
  support but easy to forget in the type checker.
- FFI returns. The compiler trusts the foreign signature; if it
  lies, that's a documented FFI hazard.

### Ergonomic costs

- Cyclic data structures need `?ref T` at exactly the cycle-closing
  link. This is a standard pattern; the linked-list and tree examples
  show how.
- The migration of existing examples — every `ref T` declaration must
  be re-classified. Tooling (a one-shot codemod) would help.

### Performance costs

- None. Non-null deref is strictly faster (no `.?`); nullable deref
  is the same.

## Open questions

- **Q02a.** Is `?ref T` a *distinct type* (the Zig approach) or
  *sugar for `Option<ref T>`* (the Rust approach)? Two options:
  - Distinct: separate `?ref T` node in the AST. Simplest to
    implement; matches how the backend already produces `?*T` for
    references. But duplicates the `?T` machinery from Gap 08.
  - Sugar: `?ref T` is `Option<ref T>`. Cleaner type system; but
    introduces issues with the `nil` literal (does it pattern-match
    as `Option.none` or its own keyword?).
- **Q02b.** What's the syntax for the implicit upcast non-null →
  nullable? Coercion at assignment sites only, or an explicit
  `some(p)` constructor, or both?
- **Q02c.** Default for *generic type parameters*: nullable, non-null,
  or required to be declared? "Required to declare" is safest but
  noisier; "non-null by default" matches the rest of the discipline.
- **Q02d.** Array-of-non-null-refs initialisation. Three options:
  - Disallow declaration without an explicit initialiser (`arr: [N]ref T =
    .{p1, p2, ..., pN}` only).
  - Allow `arr: [N]?ref T` as the only nullable-element array form,
    and provide a `try_freeze(arr) -> ?[N]ref T` to convert when all
    slots are filled.
  - Require an initialiser function: `[N]ref T(init: fn(usize) -> ref T)`.
- **Q02e.** Builder patterns — `MaybeUninit<T>`-style or staged-types?
  - `MaybeUninit<T>` adds a wrapper type and `assume_init()` discipline.
  - Staged types (`Builder<T>` → `T` via a finalising call) require
    nominal types and one extra type per builder.
- **Q02f.** Should `nil == p` on a non-null `ref T` be a compile error
  or trivially `false`? Compile error is more honest; `false` is
  more lenient.
- **Q02g.** Method calls on `?ref T`: forbidden entirely, or allowed
  via a chaining syntax (`p?.foo()` evaluating to `?ReturnType`)?
- **Q02h.** Implicit narrowing through `if p != null` ergonomics:
  do we shadow the binding (`p` inside the `if` becomes `ref T`),
  or require `if let some(q) = p`?
- **Q02i.** Comparison `p1 == p2` where both are `?ref T`: does it
  compare addresses or unwrap-and-compare? Address comparison is
  standard but surprising for users who think of `?ref T` as an
  `Option`.

## Source citations

- Reference type model: `a7/types.py:210-226` — `ReferenceType` (lacks
  `nullable: bool` flag today).
- Parser: `a7/parser.py:743-751` — `TYPE_POINTER` token.
- `nil` type-check: `a7/passes/type_checker.py:727-733` and 674 — only
  reference types accept `nil`.
- Backend emission: `a7/backends/zig.py:1682-1688` — emits `?*T`,
  deref `.?.*`.
- Example impact: `build/debug/zig/src/013_pointers.zig:9` —
  `p.?.* += 1` is the running example of the unnecessary `.?`.
- Existing examples to migrate: `examples/011_memory.a7`,
  `examples/013_pointers.a7`, `examples/017_methods.a7`,
  `examples/019_literals.a7`, `examples/025_linked_list.a7`,
  `examples/026_binary_tree.a7`, `examples/034_string_utils.a7`,
  `examples/037_language_tour.a7`.
- Spec section: `docs/SPEC.md` around line 188 (`nil` semantics).

## Phase C decision-input summary

Phase C must answer at least:

1. Q02a — distinct type vs `Option` sugar. **Drives:** parser, type
   model, error messages, idiom of `nil`.
2. Q02c — generic default.
3. Q02d — array-of-non-null-refs initialisation. **Drives:** N-08.
4. Q02e — builder pattern policy. **Drives:** N-22.
5. Q02g — method-call chaining syntax.
6. Q02h — narrowing ergonomics.

The remaining questions follow from these.
