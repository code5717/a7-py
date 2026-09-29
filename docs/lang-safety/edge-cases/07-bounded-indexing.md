# Gap 07 — Bound-proved slice / array indexing

Status: Phase A research from before 2026-09-14. Not approved. Current decisions
are in the [v1 decision ledger](../../plan/decisions.md).

> Edge-case enumeration for the audit finding in
> [`../07-language-review.md` §1.3](../07-language-review.md#13-slice--array-indexing--no-bound-proof).
> Phase A artifact; decisions land in [`../08-decisions.md`](../08-decisions.md).

## Summary

The Phase A text said that `s[i]` emits raw Zig indexing with no bound proof,
which is undefined behavior under `-O ReleaseFast`. The contract requires every
indexing operation to be one of:

- statically bound-proved, emitted without a Zig bounds check (`s.ptr[i]`); or
- routed through `try_get(i) -> ?T`.

The work is to enumerate the recognized proof patterns and to migrate the
existing examples.

## Audit notes (2026-09-16)

- Note (2026-09-16): the "no bound proof" claim is stale. The safety pass now
  collects an `index` obligation for every index expression. It proves the
  obligation only when the index interval lies inside a statically known length
  (an array size or a known slice length), and otherwise reports "index bounds
  are not proven" (`a7/safety.py:415-418`, `a7/safety.py:567-574`). The type
  checker requires `usize` or a non-negative integer literal as the index
  (`a7/passes/type_checker.py:1717-1727`). See the "Indexing" row in
  [`SAFETY_CONTRACT.md`](../../SAFETY_CONTRACT.md).
- Note (2026-09-16): proved indices lower to ordinary Zig `obj[idx]`, not
  `s.ptr[i]`, after `_require_backend_approval(node, "index")`
  (`a7/backends/zig.py:1670-1686`).
- Note (2026-09-16): the "Today" column below predates the safety pass. It was not
  re-checked row by row.
- Note (2026-09-16): `08-decisions.md` D.023 (line 653) records a later choice: the
  method is `s.get(i)` returning `?T`, not `try_get`. D.020 (line 577) keeps range
  facts internal, so `Index<n>` (BI-17, Q07b) is not a user-visible type. The
  ledger supersedes the `int`/`uint` parts of D.020 (L4). Under the ledger's
  approval rule, these D entries still need user approval with examples.
- Note (2026-09-16): L5 makes `+ - *` wrap. `s[i - 1]` with `i == 0` (BI-10) now
  wraps to a large `usize` instead of trapping, so the bound proof must still
  reject it.
- Note (2026-09-16): BI-14 assumed slices never change length. The
  [memory plan](../../plan/memory.md) (proposed) makes slices temporary views and
  rejects growth of the owner while a view is live (gate M13).

## Subcases

| # | Pattern | Today (Phase A) | Decision target |
| --- | --- | --- | --- |
| BI-01 | `for i in 0..s.length: s[i]` | Compiles | Pattern-proved; emit `s.ptr[i]` |
| BI-02 | `for value in s: ...` (foreach, no index) | Compiles | Safe: no index expression |
| BI-03 | `for i, value in s: ...` (indexed foreach) | Compiles | Safe: the slice bounds the index |
| BI-04 | `s[0]` after `if s.length > 0` (flow-sensitive) | Compiles | Pattern-proved |
| BI-05 | `s[k]`, `k` a literal `< s.length` | Often compiles | Pattern-proved if `s.length` has a static bound and `k < bound` |
| BI-06 | `s[k]`, `k` a literal, `s.length` dynamic | Compiles, may go out of bounds | `if k < s.length { ... s.try_get(k) ... }` (Phase 7 pattern) |
| BI-07 | `s[i]` with opaque `i` | Compiles, runtime check | Compile error; rewrite with `s.try_get(i)` |
| BI-08 | Nested `m[i][j]` | Compiles | Prove each index separately |
| BI-09 | Index from a call: `s[idx_func()]` | Compiles | Return value is opaque; compile error unless the return type carries a bound |
| BI-10 | Offset `s[i - 1]` | Compiles, may underflow | Compile error unless the range proves `i ≥ 1` |
| BI-11 | Reverse loop `for i in (0..n).rev(): s[i]` | n/a | Same range info; pattern-proved |
| BI-12 | Slice of slice `t = s[2..5]` | Compiles | `t.length = 3`; bound proof carried |
| BI-13 | Empty slice `[]T = []` | Compiles | Length 0; every index fails |
| BI-14 | Stale length: `let n = s.length`, then `s` changes | n/a (slices are immutable refs) | n/a (see audit note) |
| BI-15 | Last element `s[s.length - 1]` | Compiles | Needs `s.length > 0`; pattern-proved with that guard |
| BI-16 | Scan with break: `for i in 0..n { if cond { break }; s[i] }` | Compiles | `i < n` holds in the body; needs `n ≤ s.length` statically |
| BI-17 | Typed index `i: Index<n>` | n/a | `Index<n>` carries the proof `i < n` |
| BI-18 | Map-like access with non-dense keys | n/a (slices only) | Out of scope; a separate `Map<K, V>` API handles it |
| BI-19 | String indexing `s[i]`, `s: string` | Compiles? | A slice over bytes; same rules |
| BI-20 | Comprehension or generator indexing | n/a | When added, the range tracker spans the generator |

Note (2026-09-16) on BI-19: the type checker gives `string` indexing the type
`char` (`a7/passes/type_checker.py:1689-1690`). D.007 records `string.length` as a
byte count.

## Examples

The enumeration writes range loops as `for i in 0..n`. The verified examples use
the C-style `for` form and `for value in xs` / `for i, value in xs`.

BI-03 and C-style indexing over a fixed array:

```a7
// Current A7 (excerpt from examples/029_sorting.a7, verified by the example E2E)
arr: [5]i32 = [5, 1, 4, 2, 3]
for i := cast(usize, 0); i < 5; i += 1 {
    limit: usize = cast(usize, 4) - i
    for j := cast(usize, 0); j < limit; j += 1 {
        if compare(arr[j], arr[j + 1]) {
            temp := arr[j]
            arr[j] = arr[j + 1]
            arr[j + 1] = temp
        }
    }
}
for i, value in arr {
    io.println("arr[{}] = {}", i, value)
}
```

BI-06, BI-07 and BI-15 with a guard or the method form:

```a7
// Proposed (method name per D.023; not implemented)
pick :: fn(s: []i32, i: usize) i32 {
    if i < s.length {
        ret s[i]            // BI-04 style guard proves the bound
    }
    ret s.get(i).unwrap_or(0)   // BI-07: opaque index through ?T
}

last :: fn(s: []i32) i32 {
    if s.length > 0 {
        ret s[s.length - 1] // BI-15
    }
    ret 0
}
```

BI-18, map-like access outside slice indexing:

```a7
// Proposed (Map spelling not decided; the memory plan writes Map(K, V))
ages := Map(string, u32){}
ages.insert("ada", 36)
age := ages.get("ada")      // ?u32; no bound proof involved
```

BI-20, a generator whose range the tracker would span:

```a7
// Proposed (comprehensions do not exist in A7)
squares := [s[i] * s[i] for i in 0..s.length]
```

## Interactions

| Gap | Interaction |
| --- | --- |
| 01 cast | Casting to `usize` is the normal path from arithmetic to an index; the range tracker propagates through it. |
| 02 nullable pointers | Indexing `[]ref T` returns a non-null `ref T` under the Gap 02 invariant, so the proofs compose. |
| 03 definite assignment | The same flow analysis tracks "definitely assigned" and "proved bounded" and reuses the CFG. |
| 04 NonZero division | A range-proved index is often also proved non-zero for division. |
| 05 stack budget | No interaction. |
| 06 typed arithmetic | Shares the range tracker. This is the most important interaction: the tracker computes the range of `i + k`, and if it fits the slice length the index is proved. |
| 08 `Option<T>` / `Result<T, E>` | `try_get` returns `Option<T>`. |
| 09 refinement-lite | `Index<n>` is the canonical refinement type. BI-17 is the closed form of the pattern catalog. |
| 10 affine ownership | Indexing `[]ref T` does not consume the slice. It returns `borrow T` for non-`Copy` elements and `T` for `Copy` elements (probable decision). |
| 11 finite floats | No interaction. |
| 12 FFI | Slices crossing the FFI boundary lose length info; documented hazard. |
| Generics | Functions over `s: []$T` follow the same rules per instantiation. |
| Match | Slice patterns (`case [a, b, ...rest]`) carry implicit bounds for the matched prefix. |

Note (2026-09-16): the Gap 10 row is superseded as a user-facing direction. The
memory plan (proposed) has no `borrow` vocabulary; lookup returns an optional copy
and in-place changes go through place expressions (gate M33).

## Failure modes

### False positives

- Linear scans with invariants validated elsewhere. A function returns a `usize`
  the caller knows is in range, but the return type does not say so. Mitigation:
  return `Index<n>` if the function can prove it; otherwise use `try_get`.
- Loops that modify the induction variable. The four-pattern catalog requires
  clean loops; mutation breaks the pattern.
- Cross-function range info. A function taking `s: []T` and `i: usize` must use
  `try_get`. Declaring `i: Index<s.length>` needs generics over slice lengths, which
  is a heavy feature.

### False negatives

- Imprecise arithmetic ranges (Q06i, bit-op range propagation) can let an opaque
  index through. Mitigation: route the residue through `try_get`.
- A slice whose length can change. Slices are immutable today, so the language
  invariant prevents this (see the BI-14 audit note).

### Ergonomic costs

- Functions over slices must accept `Index<s.length>` (needs length-parameterized
  types) or use `try_get` inside. Most real code uses a recognized loop pattern and
  gets the proof for free.
- Stress test: port `examples/029_sorting.a7` and `examples/035_matrix.a7`. They
  exercise the four-pattern catalog. Anything uncovered needs `try_get` plus
  user-written bounds checks.

### Performance costs

- Proved cases emit `s.ptr[i]` and skip Zig's bounds check, which is faster than
  Phase A codegen.
- `try_get` lowers to one explicit `if`. That matches the cost of Zig's bounds
  check but is visible in source.

## Open questions

- **Q07a.** Is the pattern catalog fixed at four patterns or growable?
  Recommendation: ship four; mark extension as future work.
- **Q07b.** Shape of `Index<n>` parameterized on a length:
  - `Index<$n: usize>`: `$n` must be a comptime `usize`.
  - `Index<s>`: a refinement over the slice variable itself.
- **Q07c.** Does slice of slice (BI-12) carry the bound? `s[2..5]` has length 3,
  and the type holds that if the slicer is precise.
- **Q07d.** Shape of `try_get`:
  - Method `s.try_get(i) -> ?T`.
  - Indexing always returns `?T` (overloads `[]`). Removes the distinction; less
    ergonomic for proved cases.
  - Two operators: `s[i]` (proved, panic otherwise) and `s.get(i) -> ?T`.
    Note (2026-09-16): "panic otherwise" conflicts with the fail-closed rule in
    `SAFETY_CONTRACT.md`.
- **Q07e.** Empty slice (BI-13): should `s[0]` on an empty slice get its own
  compile error, or the generic "bound not proved" message?
- **Q07f.** Multi-dimensional indexing (BI-08): a first-class multi-d slice
  (`[[]T]` with a different layout), or row-major with manual indexing?
- **Q07g.** String indexing (BI-19): does `string[i]` return a byte, a rune, or
  get rejected (string is not a slice)?
- **Q07h.** Reverse iteration (BI-11): language-level `for i in (a..b).rev()` or
  library-level `for i in reverse(a..b)`?

## Source citations

- Phase A emission: `a7/backends/zig.py:1638-1645`, direct `@as`-coerced indexing.
  Note (2026-09-16): stale; emission is now `_emit_index` at
  `a7/backends/zig.py:1670-1686`.
- Phase A type checking: `a7/passes/type_checker.py:1640-1656` and the index-type
  validator at 1680–1690. Note (2026-09-16): stale; `visit_index_expr` is at
  1677–1693 and `_validate_index_bound` at 1717–1727. Bound proof is in
  `a7/safety.py:567-574`.
- Slice and array type model: `a7/types.py:150-188`.
- 15 array/slice-indexing examples to audit (count not re-verified). Spot-check:
  `examples/005_for_loop.a7`, `examples/012_arrays.a7`,
  `examples/026_binary_tree.a7`, `examples/029_sorting.a7`,
  `examples/031_number_guessing.a7`, `examples/034_string_utils.a7`,
  `examples/035_matrix.a7`, `examples/036_control_flow_edges.a7`,
  `examples/037_language_tour.a7`.
- `try_get` does not exist; it is new stdlib. Note (2026-09-16): still true;
  `a7/stdlib/` holds only `io`, `math`, `mem` and `string`.

## Phase C decision-input summary

1. Q07a — pattern catalog scope.
2. Q07b — `Index<n>` shape.
3. Q07c — slice-of-slice length tracking.
4. Q07d — `try_get` shape.
5. Q07f — multi-d indexing.
6. Q07g — string-vs-slice semantics.

The rest follow from these.
