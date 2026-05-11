# Gap 10 — Affine ownership + `inout`/`borrow` parameter modes

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.7](../07-language-review.md#17-del--no-aliasing-no-move-check).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

The single largest gap. Today `del p` consumes a reference but the
language doesn't track aliases or moves — double-free and UAF are
both reachable. The contract requires compile-time UAF safety.
**A7 is not adopting Rust's full borrow checker** (per
`05-for-a7.md` §3.4 and `06-compile-time-safety.md` §8); the chosen
direction is **mutable value semantics** (Hylo's approach):
references exist only as parameter-passing modes, not as storable
values.

Ada doesn't have affine ownership; SPARK 2014+ added limited
ownership for access types but it's restricted. Rust and Hylo are
the primary references.

## Subcases

### Move analysis

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| AO-01 | `p := new T{...}` (binding owns) | Works | `p` owns the allocation |
| AO-02 | `q := p` (move) | Aliases today | `q` owns; `p` becomes unbindable |
| AO-03 | `consume(p)` (function call by value) | Aliases today | `p` moved into the function |
| AO-04 | `return p` | Works | `p` moved out of the function |
| AO-05 | `field = p` (move into struct) | Aliases today | `p` moved into the struct's field; `p` unbindable |
| AO-06 | `del p` | Works (no aliasing check) | Consumes `p`; subsequent use is error |
| AO-07 | Use after consume: `consume(p); p.val` | Compiles today | **Compile error**: "use of moved value `p`" |
| AO-08 | Use after `del`: `del p; p.val` | Compiles today | **Compile error**: same as AO-07 |
| AO-09 | `if c then consume(p) end; p.val` | Compiles | **Compile error**: partial move on the consume branch |
| AO-10 | `match p.kind { case A: consume(p); case B: keep(p) }` | Compiles | Each arm controls move; analysis joins at end |

### Parameter-mode dispatch

| # | Mode | Semantics | Lowers to Zig |
| --- | --- | --- | --- |
| AO-11 | `fn f(x: T)` (default — pass-by-value) | Copy if `Copy`, move otherwise | `T` (struct value) |
| AO-12 | `fn f(x: borrow T)` | Read-only borrow; cannot escape; no mutation | `*const T` |
| AO-13 | `fn f(x: inout T)` | Exclusive mutable borrow; cannot escape | `*T` |
| AO-14 | `fn f(x: consume T)` | Same as default for non-`Copy`; explicit consume marker | `T` |
| AO-15 | `fn f(x: set T)` | Write-only output; caller passes uninit | `*T` (Zig out-param) |
| AO-16 | Return modes mirror parameter modes for clarity | n/a | n/a |

### Call-site exclusivity

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| AO-17 | `swap(inout x, inout y)` — distinct values | Aliases possible | OK |
| AO-18 | `swap(inout x, inout x)` — same value | Aliases trivially | **Compile error**: two `inout`s alias |
| AO-19 | `f(inout big.field_a, inout big.field_b)` — distinct fields of same struct | Aliases possible | Distinct field paths ⇒ no alias |
| AO-20 | `f(inout arr[i], inout arr[j])` — same array, opaque indices | Aliases possible | **Compile error**: cannot prove distinct |
| AO-21 | `f(inout arr[i], inout arr[i+1])` — known-distinct indices | n/a | OK (range proof: `i ≠ i+1`) |
| AO-22 | `f(inout x, borrow x)` — mix of borrow + inout on same value | n/a | **Compile error**: borrow + inout exclusive |
| AO-23 | `f(borrow x, borrow x)` — two read borrows of same value | n/a | OK (read-only sharing) |
| AO-24 | `f(borrow x, borrow y)` where `x` and `y` might alias (refs through pointers) | n/a | Decision: forbid borrows of dereferenced pointers, or require explicit "may alias" |

### Aggregate / partial moves

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| AO-25 | `let (a, b) = pair` — destructure | n/a | Both `a` and `b` are owned; `pair` is moved |
| AO-26 | `let y = pair.first; pair.second` — partial field move | n/a | `pair.first` is moved; `pair.second` still accessible; `pair` itself is partially-moved |
| AO-27 | Reassigning a moved field: `pair.first = new_value` | n/a | Restores access |
| AO-28 | Whole-struct move after partial move | n/a | **Compile error**: cannot move the whole if a part has moved |
| AO-29 | Drop order at scope exit | n/a | Reverse declaration order; deterministic |
| AO-30 | `defer` interaction with move | n/a | `defer` runs after move; if the moved value is needed by `defer`, error |

### Refused features (don't add to A7)

| # | Rust feature | Why not in A7 |
| --- | --- | --- |
| AO-31 | Named lifetimes `'a` | Hylo demonstrates lifetimes aren't needed if refs aren't storable |
| AO-32 | Generic lifetimes on types | Same |
| AO-33 | `'static` and friends | Same |
| AO-34 | NLL / Polonius lifetime inference | Same; we don't have lifetimes to infer |
| AO-35 | Self-referential structs (`Pin`, etc.) | Forbidden; user works around via indices |
| AO-36 | `Rc`/`Arc` shared ownership | Out of scope; consider regions (Gap A reduction) |

## Interactions

- **Gap 01 cast.** Casting a value doesn't consume it if it's `Copy`;
  moves it otherwise. Cast classification (Gap 01) doesn't change
  ownership semantics.
- **Gap 02 nullable pointers.** A moved `ref T` slot becomes
  effectively `?ref T = none` (the same "uninitialised after move"
  state DA tracks). Move analysis and DA share the lattice.
- **Gap 03 definite assignment.** **Core interaction**: DA tracks
  "is the binding readable here?"; move analysis tracks "is the
  resource live here?". Same CFG, same lattice operations,
  separate flags. Reusing the validator infrastructure at
  `a7/passes/semantic_validator.py:140-236`.
- **Gap 04 NonZero division.** `NonZero<T>` is `Copy`; no ownership
  concern.
- **Gap 05 stack budget.** No interaction.
- **Gap 06 typed arithmetic.** Range tracker doesn't change with
  ownership; ranges are over `Copy` numeric values.
- **Gap 07 bounded indexing.** Indexing `s: borrow []T` returns a
  `borrow T`; indexing `s: inout []T` returns an `inout T`; indexing
  a value `s: []T` requires care (decision: returns `T` if `Copy`,
  otherwise requires `borrow` mode at the indexing site).
- **Gap 08 `Option<T>` / `Result<T, E>`.** Match arm `case some(v):
  ...` moves the inner `v` if `T` is non-`Copy`. Borrow-style match
  (`case some(borrow v): ...`) is open (Q10g).
- **Gap 09 refinement-lite.** Refinements over non-`Copy` base types
  inherit ownership semantics.
- **Gap 11 finite floats.** `Fin<F>` is `Copy`.
- **Gap 12 FFI.** Foreign code may keep aliases the language can't
  see. **Documented FFI hazard.** Mitigation: foreign returns of
  reference types come back as `?ref T`; foreign params take
  `borrow T` by default.
- **Closures (future).** When closures land: capture semantics must
  pick a mode per captured variable (`borrow`, `inout`, `consume`).
  Hylo and Swift both do this.
- **Match.** AO-10. Move analysis must join branches; each branch's
  consumption state is collected.

## Failure modes

### False positives

- Algorithms that legitimately need shared mutable state (caches,
  observers). Mitigation: region-style scopes (out-of-scope for
  this gap; future work) or stricter refactoring.
- Builder patterns that pass a buffer through stages. Mitigation:
  `inout` chains.
- Linked data structures where parent and child both reference each
  other. Mitigation: use indices into a parent-owned arena (Cyclone
  style).

### False negatives

- Foreign code (FFI). Documented.
- Address-of expressions (`&x`) — open question (Q10c).
- Generic code where `$T` ownership semantics differ per
  instantiation. Mitigation: re-check at instantiation.

### Ergonomic costs

- The biggest. This is the most invasive change. Existing examples
  (especially `examples/025_linked_list.a7`, `examples/026_binary_tree.a7`)
  will need significant refactors to model ownership cleanly.
- Users will need to learn the four parameter modes (`T`, `borrow`,
  `inout`, `consume`, plus possibly `set`).
- Move errors are subtle; diagnostic quality is crucial.

### Performance costs

- None at runtime — affine ownership is purely compile-time.
- Compile-time: move analysis is the same complexity as DA (linear
  in CFG size).

## Open questions

- **Q10a.** Do A7 references exist as **storable values** (struct
  fields, array elements) or **only as parameter modes**? Two
  options:
  - **Hylo-style (parameter modes only)**: cleanest; no lifetimes
    needed; most restrictive.
  - **Rust-lite (storable refs with limited usage)**: more
    expressive; requires lifetime-like reasoning.
  - **Compromise: storable but only in specific shapes** (e.g.,
    closures, generators).
- **Q10b.** Parameter-mode keyword vocabulary. Candidates:
  - Hylo: `let`, `inout`, `sink`, `set`.
  - Swift: `borrowing`, `consuming`, `inout`.
  - Custom A7: `borrow`, `inout`, `consume`, `set`.
- **Q10c.** Address-of (`x.adr`) — does it produce a temporary
  borrow (good citizen) or a long-lived alias (forbidden)?
- **Q10d.** Indexing `arr[i]` of an array of non-`Copy` values —
  return a borrow, a move, or error?
- **Q10e.** Drop / destructor semantics. Does A7 have a
  user-definable destructor (Rust `Drop`)? If yes, when does it run
  (scope exit, last-use)? **Recommendation**: no destructor; `del`
  is explicit and the type tracks it.
- **Q10f.** Aliasing through `inout` on array elements (AO-20) —
  pure forbid, or allow when range tracker proves indices distinct?
- **Q10g.** Borrowing-style match (Gap 08 Q08e) — `case some(borrow
  v): ...` syntax that lets the user *borrow* the matched value
  without consuming the enclosing `Option<T>`. Yes/no.
- **Q10h.** Loops over `inout` arrays — does `for inout x in arr`
  exist? Per iteration, `x` is an `inout T`.
- **Q10i.** Partial moves through fields (AO-26) — supported or
  forbidden?
- **Q10j.** Scope-exit drop order (AO-29) — declaration order
  reverse, or any other order?
- **Q10k.** Self-move (AO-18) detection — purely syntactic
  (both args are the same identifier), or richer (same address)?

## Source citations

- No ownership / move analysis exists today;
  `docs/SPEC.md:1067` explicitly notes "lifetime analysis: not yet
  implemented."
- CFG infrastructure to reuse:
  `a7/passes/semantic_validator.py:140-236`.
- `del` codegen: emits `defer if (p) |q| allocator.destroy(q)` —
  see `build/debug/zig/src/011_memory.zig:17`.
- Existing examples needing the biggest refactors:
  `examples/011_memory.a7`, `examples/025_linked_list.a7`,
  `examples/026_binary_tree.a7`, `examples/034_string_utils.a7`,
  `examples/037_language_tour.a7`.
- Design references:
  - Hylo Mutable Value Semantics: <https://hylo-lang.org/introduction/>
  - Hylo Spec: <https://hylo-lang.org/docs/reference/specification/>
  - Rust NLL: <https://rust-lang.github.io/rfcs/2094-nll.html>
  - Swift exclusivity:
    <https://github.com/apple/swift-evolution/blob/main/proposals/0176-enforce-exclusive-access-to-memory.md>
  - Cyclone regions:
    <https://www.cs.umd.edu/projects/cyclone/papers/cyclone-regions.pdf>

## Phase C decision-input summary

1. Q10a — storable refs vs parameter modes only. **Drives:** the
   entire architecture.
2. Q10b — keyword vocabulary.
3. Q10c — address-of semantics.
4. Q10d — indexing of non-`Copy` array.
5. Q10e — destructor (`Drop`) yes/no.
6. Q10f — aliased `inout` on arrays.
7. Q10g — borrowing-style match.
8. Q10i — partial moves.

All other AO-NN items follow.
