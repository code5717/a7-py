# Gap 07 — Bound-proved slice / array indexing

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.3](../07-language-review.md#13-slice--array-indexing--no-bound-proof).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

Today `s[i]` emits raw Zig indexing with no bound proof. Under
`-O ReleaseFast` this is UB. The contract requires every indexing
operation to be either statically bound-proved (emit `s.ptr[i]` —
no Zig bounds check) or routed through `try_get(i) -> ?T`. The work
is enumerating the recognised proof patterns and the migration of
existing examples.

## Subcases

| # | Pattern | Today | Decision target |
| --- | --- | --- | --- |
| BI-01 | `for i in 0..s.length: s[i]` | Compiles | Pattern-proved; emit `s.ptr[i]` |
| BI-02 | `for value in s: ...` (foreach, no index) | Compiles | Trivially safe (no index expression) |
| BI-03 | `for i, value in s: ...` (indexed foreach) | Compiles | Trivially safe (the index is bounded by the slice) |
| BI-04 | `s[0]` after `if s.length > 0` (flow-sensitive) | Compiles | Pattern-proved |
| BI-05 | `s[k]` where `k` is a literal `< s.length` | Often compiles | Pattern-proved if `s.length` is statically bound and `k < bound` |
| BI-06 | `s[k]` where `k` is a literal and `s.length` is dynamic | Compiles, may OOB | `if k < s.length { ... s.try_get(k) ... }` — Phase 7 pattern |
| BI-07 | `s[i]` with opaque `i` | Compiles, runtime check | **Compile error**; rewrite via `s.try_get(i)` |
| BI-08 | Nested: `m[i][j]` | Compiles | Each index proved separately |
| BI-09 | Indirect via getter: `s[idx_func()]` | Compiles | Treat return value as opaque; **compile error** unless return type carries a bound |
| BI-10 | Negative offset `s[i - 1]` | Compiles, possible underflow | Compile error unless range proves `i ≥ 1` |
| BI-11 | Reverse loop `for i in (0..n).rev(): s[i]` | n/a today | Same range info; pattern-proved |
| BI-12 | Slice-of-slice `t = s[2..5]` | Compiles | `t.length = 3`; bound proof carried |
| BI-13 | Empty slice `[]T = []` | Compiles | Length 0; any index fails |
| BI-14 | Stale length: capturing `let n = s.length` then growing/changing `s` | n/a (slices are immutable refs) | n/a |
| BI-15 | `s[s.length - 1]` (last element) | Compiles | Requires `s.length > 0`; pattern-proved with that guard |
| BI-16 | Linear scan with break: `for i in 0..n { if cond { break }; s[i] }` | Compiles | Bound `i < n` holds in body; assuming `n ≤ s.length` is statically known |
| BI-17 | Indexed access from a typed index: `i: Index<n>` | n/a | `Index<n>` carries proof `i < n` |
| BI-18 | Map-like access where keys aren't dense integers | n/a (slices only) | Out of scope for slice indexing; handled by separate `Map<K, V>` API |
| BI-19 | String indexing `s[i]` where `s: string` | Compiles? | Should be a slice over bytes; same rules |
| BI-20 | Comprehension / generator-style indexing | n/a | When added, range-tracker spans the generator |

## Interactions

- **Gap 01 cast.** Casting to `usize` is the normal path from arithmetic
  to index; the range tracker propagates.
- **Gap 02 nullable pointers.** Indexing a `[]ref T` returns `ref T`
  (non-null) by Gap 02 invariant — proof composes.
- **Gap 03 definite assignment.** The same flow analysis tracks
  "definitely assigned" and "proved bounded"; reuses the CFG.
- **Gap 04 NonZero division.** A range-proved index is often
  range-proved non-zero for use in division — cross-cutting refinement.
- **Gap 05 stack budget.** No interaction.
- **Gap 06 typed arithmetic.** **Shares the range tracker.** This is
  the single most important interaction: arithmetic on `i` produces
  a new `i + k` whose range the tracker computes; if the new range
  fits the slice length, the indexing is proved.
- **Gap 08 `Option<T>` / `Result<T, E>`.** `try_get` returns
  `Option<T>`.
- **Gap 09 refinement-lite.** `Index<n>` is the canonical refinement
  type. BI-17 is the closed-form version of the pattern catalog.
- **Gap 10 affine ownership.** Indexing through `[]ref T` doesn't
  consume the slice; indexing returns a `borrow T` or `T` depending
  on the element type (decision: probably `borrow T` for non-Copy,
  `T` for Copy).
- **Gap 11 finite floats.** No interaction.
- **Gap 12 FFI.** Slices crossing FFI boundary lose length info;
  documented hazard.
- **Generics.** Generic functions over `$T` accessing `s: []$T`
  follow the same rules per-instantiation.
- **Match.** Match arm patterns over slices (`case [a, b, ...rest]`)
  carry implicit bounds for the matched prefix.

## Failure modes

### False positives

- Linear scans with externally-validated invariants. Example: a
  function returns `usize` that the caller *knows* is in range, but
  the return type doesn't say so. Mitigation: declare return type
  `Index<n>` if the function can prove the property; otherwise
  `try_get`.
- Mid-loop modifications of induction variable. The four-pattern
  catalog requires "clean" loops; mutation breaks the pattern.
- Cross-function range info — if a function takes `s: []T` and
  `i: usize`, it must use `try_get`. The user can declare
  `i: Index<s.length>` but generics over slice lengths is a heavy
  feature.

### False negatives

- Imprecision in arithmetic ranges (Q06i — bit-op range propagation)
  can let an opaque index through. Mitigation: route the residual
  through `try_get`.
- A slice whose length is itself mutable (currently slices are
  immutable, so this doesn't arise) — protected by language
  invariant.

### Ergonomic costs

- Functions over slices need to either accept `Index<s.length>`
  (requires length-parameterised types — heavy) or use `try_get`
  internally. Most real code uses one of the recognised loop
  patterns and gets the proof for free.
- Stress test: porting `examples/029_sorting.a7`, `examples/035_matrix.a7`
  — these will exercise the four-pattern catalog. Anything not
  covered must use `try_get` plus user-written bounds checks.

### Performance costs

- Proved cases emit `s.ptr[i]` (skips Zig's bounds check) — *faster*
  than today.
- `try_get` lowers to one explicit `if`; same cost as Zig's bounds
  check today, but in user-visible source.

## Open questions

- **Q07a.** The four-pattern catalog — fixed at four, or growable?
  Recommendation: ship four; mark "extensible" as a future work
  item.
- **Q07b.** Index<n> generic parameterised on a length expression —
  shape:
  - `Index<$n: usize>` — requires `$n` to be a comptime usize.
  - `Index<s>` — refinement over the slice variable itself.
- **Q07c.** Slice-of-slice (BI-12) — carry the bound? `s[2..5]`
  produces a slice with length 3. The bound info is in the type if
  the slicer is precise.
- **Q07d.** `try_get` shape. Three options:
  - Method `s.try_get(i) -> ?T`.
  - Indexing returns `?T` always (overloads `[]`). Removes the
    distinction; less ergonomic for proved cases.
  - Two operators: `s[i]` (proved, panic otherwise) and `s.get(i) -> ?T`.
- **Q07e.** Empty slice as a special case (BI-13) — should `s[0]`
  on an empty slice be a compile error specifically, or fall under
  the generic "bound not proved" message?
- **Q07f.** Multi-dimensional indexing (BI-08) — first-class
  multi-d slice (`[[]T]` with a different layout), or row-major
  with manual indexing?
- **Q07g.** String indexing (BI-19) — `string[i]` returns a byte,
  a rune, or is rejected (string ≠ slice)?
- **Q07h.** Reverse iteration (BI-11) — language-level `for i in
  (a..b).rev()` or library-level `for i in reverse(a..b)`?

## Source citations

- Today's emission: `a7/backends/zig.py:1638-1645` — direct
  `@as`-coerced indexing.
- Type-checking: `a7/passes/type_checker.py:1640-1656` plus the
  index-type validator at 1680–1690.
- Slice / array type model: `a7/types.py:150-188`.
- 15 array/slice-indexing examples to audit. Spot-check:
  `examples/005_for_loop.a7`, `examples/012_arrays.a7`,
  `examples/026_binary_tree.a7`, `examples/029_sorting.a7`,
  `examples/031_number_guessing.a7`, `examples/034_string_utils.a7`,
  `examples/035_matrix.a7`, `examples/036_control_flow_edges.a7`,
  `examples/037_language_tour.a7`.
- Existing `try_get` doesn't exist; this is new stdlib.

## Phase C decision-input summary

1. Q07a — pattern catalog scope.
2. Q07b — `Index<n>` shape.
3. Q07c — slice-of-slice length tracking.
4. Q07d — `try_get` shape.
5. Q07f — multi-d indexing.
6. Q07g — string-vs-slice semantics.

The rest follow.
