# Gap 10 — Affine ownership + `inout`/`borrow` parameter modes

Status: Phase A research from before 2026-09-14. Superseded as the user-facing
direction by the [memory plan](../../plan/memory.md); current decisions are in the
[v1 decision ledger](../../plan/decisions.md).

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.7](../07-language-review.md#17-del--no-aliasing-no-move-check).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

## Summary

This was the largest gap. In Phase A, `del p` consumed a reference, but the
language did not track aliases or moves, so double free and use after free were
both reachable. The contract requires compile-time use-after-free safety.

A7 was not to adopt Rust's full borrow checker (`05-for-a7.md` §3.4,
`06-compile-time-safety.md` §8). The chosen direction was mutable value semantics,
as in Hylo: references exist only as parameter-passing modes, never as stored
values.

Ada has no affine ownership. SPARK 2014 and later add limited ownership for access
types. Rust and Hylo are the primary references.

## Audit notes (2026-09-16)

- Note (2026-09-16): superseded as a user-facing direction. The memory plan
  (proposed, not approved) keeps ownership internal to the compiler. Ordinary
  source never writes allocate, free, lifetime or borrow (contract item 9). It
  removes `del` from ordinary code (gate M3), removes stored and returned `ref`
  (M4), and uses `Id(T)`, `Table(T)` (M1, M5) and native descriptors (M12).
- Note (2026-09-16): ledger L6 approves immutable argument bindings only. No
  parameter-mode syntax is approved; the `ref` parameter remains the working form.
  Proposed D.040–D.049 (mode keywords, inferred modes, no storable references) were
  not accepted. Open decision O2 was replaced by the memory plan. Ledger L15 and
  L17–L22 make memory automatic, compile-time and invisible.
- Note (2026-09-16): the subcase tables remain useful as inputs to the internal
  ownership layer (memory plan §4, layer 2). Read `borrow`, `inout`, `consume` and
  `set` as internal analysis states, not as syntax.
- Note (2026-09-16): AO-08 is stale. Direct reads after `del` are rejected until
  the binding is reassigned (`SPEC.md` §8.4,
  [`SAFETY_CONTRACT.md`](../../SAFETY_CONTRACT.md) "Ownership Surface"). The safety
  pass also rejects reads of names in `moved_symbols` (`a7/safety.py:398-399`);
  which operations mark a move was not verified.
- Note (2026-09-16): AO-18 remains accurate for today. The memory plan records that
  aliased `ref` arguments such as `both(x, x)` compile in A7 and Zig, and proposes
  rejecting them. Corpus program 14 covers `swap(a[i], a[j])` (AO-20).
- Note (2026-09-16): Q10c is answered for the public surface. There is no public
  address-of or dereference syntax (`SAFETY_CONTRACT.md` "Reference Surface").
  AO-07 and AO-08 were written with `p.val`; they now use field access.
- Note (2026-09-16): the memory plan answers several open questions in its
  proposal: no user destructor, with releases on control-flow edges (Q10e);
  resources released in reverse acquisition order (M7, Q10j); user `defer` runs
  before automatic releases in the same scope (§4, AO-30); loop bindings are
  immutable copies (M30, Q10h); no reference counting (AO-36).

## Subcases

### Move analysis

| # | Pattern | Phase A state | Decision target |
| --- | --- | --- | --- |
| AO-01 | `p := new T{...}` (binding owns) | Works | `p` owns the allocation |
| AO-02 | `q := p` (move) | Aliases | `q` owns; `p` becomes unusable |
| AO-03 | `consume(p)` (call by value) | Aliases | `p` moves into the function |
| AO-04 | `ret p` | Works | `p` moves out of the function |
| AO-05 | `field = p` (move into struct) | Aliases | `p` moves into the field; `p` unusable |
| AO-06 | `del p` | Works, no alias check | Consumes `p`; later use is an error |
| AO-07 | Use after consume: `consume(p); p.value` | Compiles | Compile error: "use of moved value `p`" |
| AO-08 | Use after `del`: `del p; p.value` | Compiles (stale, see audit note) | Compile error, as AO-07 |
| AO-09 | `if c { consume(p) }; p.value` | Compiles | Compile error: moved on one branch |
| AO-10 | `match p.kind { case A: consume(p); case B: keep(p) }` | Compiles | Each arm controls the move; analysis joins at the end |

### Parameter-mode dispatch

| # | Mode | Semantics | Lowers to Zig |
| --- | --- | --- | --- |
| AO-11 | `fn f(x: T)` (default, by value) | Copy if `Copy`, move otherwise | `T` |
| AO-12 | `fn f(x: borrow T)` | Read-only borrow; cannot escape; no mutation | `*const T` |
| AO-13 | `fn f(x: inout T)` | Exclusive mutable borrow; cannot escape | `*T` |
| AO-14 | `fn f(x: consume T)` | Default for non-`Copy`, marked explicitly | `T` |
| AO-15 | `fn f(x: set T)` | Write-only output; caller passes uninitialized storage | `*T` (out-param) |
| AO-16 | Return modes mirror parameter modes | n/a | n/a |

### Call-site exclusivity

| # | Pattern | Phase A state | Decision target |
| --- | --- | --- | --- |
| AO-17 | `swap(inout x, inout y)`, distinct values | Aliases possible | OK |
| AO-18 | `swap(inout x, inout x)`, same value | Aliases | Compile error: two `inout`s alias |
| AO-19 | `f(inout big.field_a, inout big.field_b)` | Aliases possible | Distinct field paths do not alias |
| AO-20 | `f(inout arr[i], inout arr[j])`, opaque indices | Aliases possible | Compile error: cannot prove distinct |
| AO-21 | `f(inout arr[i], inout arr[i+1])` | n/a | OK: range proof shows `i ≠ i+1` |
| AO-22 | `f(inout x, borrow x)` | n/a | Compile error: `borrow` and `inout` are exclusive |
| AO-23 | `f(borrow x, borrow x)` | n/a | OK: read-only sharing |
| AO-24 | `f(borrow x, borrow y)` where `x` and `y` may alias through pointers | n/a | Forbid borrows of dereferenced pointers, or require an explicit "may alias" |

### Aggregate / partial moves

| # | Pattern | Phase A state | Decision target |
| --- | --- | --- | --- |
| AO-25 | `let (a, b) = pair` (destructure) | n/a | `a` and `b` owned; `pair` moved |
| AO-26 | `let y = pair.first; pair.second` | n/a | `pair.first` moved; `pair.second` still usable; `pair` partially moved |
| AO-27 | `pair.first = new_value` after a move | n/a | Restores access |
| AO-28 | Whole-struct move after a partial move | n/a | Compile error |
| AO-29 | Drop order at scope exit | n/a | Reverse declaration order; deterministic |
| AO-30 | `defer` and moves | n/a | `defer` runs after the move; error if `defer` needs the moved value |

Note (2026-09-16): AO-25 uses destructuring, which CLAUDE.md lists as parsed-only
syntax.

### Refused features (don't add to A7)

| # | Rust feature | Why not in A7 |
| --- | --- | --- |
| AO-31 | Named lifetimes `'a` | Hylo shows lifetimes are unnecessary when references cannot be stored |
| AO-32 | Generic lifetimes on types | Same |
| AO-33 | `'static` and related | Same |
| AO-34 | NLL / Polonius inference | Same; no lifetimes to infer |
| AO-35 | Self-referential structs (`Pin`) | Forbidden; use indices |
| AO-36 | `Rc` / `Arc` shared ownership | Out of scope; consider regions (Gap A reduction) |

## Examples

AO-01, AO-06 and AO-13 in today's surface:

```a7
// Current A7 (excerpts from examples/011_memory.a7 and examples/037_language_tour.a7)
bump :: fn(value: ref i32) {
    value += 1                    // writes the caller's value
}

main :: fn() {
    value_box := new Box          // AO-01: binding owns the allocation
    if value_box == nil {
        ret
    }
    defer del value_box           // AO-06: explicit release
    value_box.value = 42

    counter: i32
    counter = 41
    bump(counter)                 // AO-13 analog: ref argument passed as an lvalue
}
```

AO-09 and AO-10, moves joined across branches:

```a7
// Proposed (move analysis as in Phase A; superseded as a user surface)
p := new Buffer
if ready {
    consume(p)
}
io.println("{}", p.length)       // AO-09: error, p may have moved

match p.kind {
    case Kind.A: { consume(p) }   // AO-10: moved in this arm
    case Kind.B: { keep(p) }      // still owned in this arm
}
```

AO-29 and AO-30, release order and `defer`:

```a7
// Proposed (automatic release per the memory plan; not implemented)
main :: fn() {
    log := open_log("run.txt")    // resource, released last
    data := load_rows()           // released first (reverse order)
    defer log.write("done")       // user defer runs before automatic releases
    send(data)                    // AO-30: data moves; a defer using data is an error
}
```

AO-35, parent links through typed ids instead of self-references:

```a7
// Proposed (from the memory plan, section 2; not implemented)
Node :: struct {
    value: i32
    parent: ?Id(Node)
}

Tree :: struct {
    nodes: Table(Node)
}
```

## Interactions

| Area | Interaction |
| --- | --- |
| Gap 01 cast | Casting a `Copy` value does not consume it; a non-`Copy` value moves. Cast classification does not change ownership. |
| Gap 02 nullable pointers | A moved `ref T` slot behaves like `?ref T = none`, the same "uninitialized after move" state definite assignment tracks. They share the lattice. |
| Gap 03 definite assignment | Core interaction. DA tracks "is the binding readable here?"; move analysis tracks "is the resource live here?". Same CFG, same lattice operations, separate flags. Reuses `a7/passes/semantic_validator.py:140-236`. |
| Gap 04 NonZero division | `NonZero<T>` is `Copy`; no ownership concern. |
| Gap 05 stack budget | No interaction. |
| Gap 06 typed arithmetic | Ranges are over `Copy` numeric values; ownership does not affect them. |
| Gap 07 bounded indexing | `s: borrow []T` indexes to `borrow T`; `s: inout []T` to `inout T`. A value `s: []T` returns `T` if `Copy`, otherwise needs `borrow` at the index site (probable decision). |
| Gap 08 `Option<T>` / `Result<T, E>` | `case some(v)` moves a non-`Copy` `v`. Borrow-style match (`case some(borrow v)`) is open (Q10g). |
| Gap 09 refinement-lite | Refinements over non-`Copy` types inherit ownership. |
| Gap 11 finite floats | `Fin<F>` is `Copy`. |
| Gap 12 FFI | Foreign code may keep aliases the language cannot see; documented hazard. Mitigation: foreign reference returns come back as `?ref T`; foreign parameters take `borrow T` by default. |
| Closures (future) | Captures pick a mode per variable (`borrow`, `inout`, `consume`), as in Hylo and Swift. |
| Match | AO-10: move analysis joins branches and collects each branch's consumption state. |

Note (2026-09-16): the Gap 03 row cites a CFG in `semantic_validator.py:140-236`.
Those lines hold an iterative statement visitor, not a CFG. `STATUS.md` lists an
internal CFG stage as a priority, and the memory plan lists a typed IR with a CFG
as layer 0.

Note (2026-09-16): the Gap 12 row is replaced in the memory plan by native
descriptors (M12) and the rejection "native code retaining storage without a
declared owner".

## Failure modes

### False positives

- Algorithms that need shared mutable state (caches, observers). Mitigation:
  region-style scopes (future work, outside this gap) or refactoring.
- Builders that pass a buffer through stages. Mitigation: `inout` chains.
- Linked structures where parent and child reference each other. Mitigation:
  indices into a parent-owned arena, as in Cyclone. The memory plan proposes
  `Table(T)` with `Id(T)`.

### False negatives

- Foreign code (FFI). Documented.
- Address-of expressions (`&x`): open (Q10c; see audit note).
- Generic code where `$T` ownership differs per instantiation. Mitigation: re-check
  at instantiation.

### Ergonomic costs

- The highest of all gaps; the most invasive change. `examples/025_linked_list.a7`
  and `examples/026_binary_tree.a7` need large refactors.
- Users must learn the parameter modes (`T`, `borrow`, `inout`, `consume`, possibly
  `set`).
- Move errors are subtle; diagnostic quality is crucial.

### Performance costs

- None at run time; affine ownership is compile-time only.
- Compile time: move analysis has the same complexity as definite assignment,
  linear in CFG size.

## Open questions

- **Q10a.** Are references storable values (struct fields, array elements) or only
  parameter modes?
  - Hylo style, parameter modes only: cleanest; no lifetimes; most restrictive.
  - Rust-lite, storable with limited use: more expressive; needs lifetime-like
    reasoning.
  - Compromise: storable only in specific shapes such as closures and generators.
- **Q10b.** Mode keywords:
  - Hylo: `let`, `inout`, `sink`, `set`.
  - Swift: `borrowing`, `consuming`, `inout`.
  - A7: `borrow`, `inout`, `consume`, `set`.
- **Q10c.** Does address-of (`x.adr`) produce a temporary borrow (acceptable) or a
  long-lived alias (forbidden)?
- **Q10d.** Does indexing `arr[i]` on an array of non-`Copy` values return a
  borrow, move the element, or fail?
- **Q10e.** Is there a user-defined destructor (Rust `Drop`)? If so, when does it
  run: scope exit or last use? Recommendation: no destructor; `del` is explicit
  and the type system tracks it.
- **Q10f.** `inout` aliasing on array elements (AO-20): always forbid, or allow
  when the range tracker proves the indices distinct?
- **Q10g.** Borrow-style match (Gap 08 Q08e): does `case some(borrow v)` let the
  user borrow the value without consuming the enclosing `Option<T>`?
- **Q10h.** Does `for inout x in arr` exist, with `x` an `inout T` per iteration?
- **Q10i.** Partial moves through fields (AO-26): supported or forbidden?
- **Q10j.** Scope-exit drop order (AO-29): reverse declaration order or another
  order?
- **Q10k.** Self-move detection (AO-18): syntactic (same identifier) or richer
  (same address)?

## Source citations

- No ownership or move analysis exists; `docs/SPEC.md:1067` notes "lifetime
  analysis: not yet implemented". Note (2026-09-16): the wording moved; SPEC §8.4
  now lists "Ownership, borrowing, or lifetime analysis that proves absence of
  dangling pointers" as not implemented (`docs/SPEC.md:1077`), and direct
  use-after-`del` is rejected.
- CFG infrastructure to reuse: `a7/passes/semantic_validator.py:140-236` (see the
  note under Interactions).
- `del` codegen emits `defer if (p) |q| allocator.destroy(q)`; see
  `build/debug/zig/src/011_memory.zig:17`. Note (2026-09-16): the current build
  output has `defer if (value_box) |p| allocator.destroy(p);` at line 26.
- Examples needing the largest refactors: `examples/011_memory.a7`,
  `examples/025_linked_list.a7`, `examples/026_binary_tree.a7`,
  `examples/034_string_utils.a7`, `examples/037_language_tour.a7`.
- Design references:
  - Hylo mutable value semantics: <https://hylo-lang.org/introduction/>
  - Hylo specification: <https://hylo-lang.org/docs/reference/specification/>
  - Rust NLL: <https://rust-lang.github.io/rfcs/2094-nll.html>
  - Swift exclusivity:
    <https://github.com/apple/swift-evolution/blob/main/proposals/0176-enforce-exclusive-access-to-memory.md>
  - Cyclone regions:
    <https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf>

## Phase C decision-input summary

1. Q10a — storable references vs parameter modes only. Drives the whole
   architecture.
2. Q10b — keyword vocabulary.
3. Q10c — address-of semantics.
4. Q10d — indexing a non-`Copy` array.
5. Q10e — destructor (`Drop`) yes or no.
6. Q10f — aliased `inout` on arrays.
7. Q10g — borrow-style match.
8. Q10i — partial moves.

All other AO items follow from these.
