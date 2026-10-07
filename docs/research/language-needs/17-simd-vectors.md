# 17 — SIMD and vector types

Status: later, not V1. No new syntax is approved. Every spelling below is a proposal.

## 1. What exists today

Fixed arrays have one element-wise operator: `+`.

- Type checker accepts only `ADD` on same-size, same-element numeric fixed
  arrays (`a7/passes/type_checker.py:1504-1510`). `-`, `*`, `/`, `%` on
  arrays are type errors.
- Backend lowers that `+` through Zig `@Vector(N, T)`
  (`a7/backends/zig.py:1589-1591`). Other ops have no lowering.
- Operands must be named or indexed arrays, not arbitrary expressions
  (`zig.py:1625-1633`). Fixed size and primitive numeric element required.
- SPEC `§3.3` documents `c = a + b` for `[4]f64`. SPEC `§9` (tensors,
  broadcasting, `@vectorize`) is a design target; nothing there compiles.
  Report 09 covers the tensor/AI track; this file covers only fixed-width
  SIMD vectors.

So A7 already leans on Zig vectors for one case, with no user-visible
vector type, no lane access, and no target-feature query.

## 2. How others do it

Zig: `@Vector(N, T)` is a first-class type. Normal operators apply
lane-wise. `@splat` fills lanes, `@reduce` folds lanes to scalar,
comparisons give `@Vector(N, bool)` masks, `@select`/`@shuffle` blend and
reorder. `std.simd.suggestVectorLength(T)` picks a width for the target.
Scalar fallback is automatic where the target lacks SIMD. Plain loops also
auto-vectorize; explicit vectors are for guaranteed lane behavior.

Odin: `#simd[N]T` vectors plus array programming on plain fixed arrays
(`a + b` on `[3]f32`). SIMD lane counts must be powers of two. The `simd`
package adds shuffles, selects, reductions. Plain arrays cover small
geometry; `#simd` covers wide data.

Rust: `std::simd::Simd<T, N>` (nightly, `portable_simd`). Lane-wise ops,
masks (`Mask<T, N>`), `splat`/`from_array`/`from_slice`, reductions.
Integer ops wrap. Falls back to scalar code per target. Stable alternative
is `std::arch` intrinsics per CPU family.

Mojo: `SIMD[DType, width]` with width as a compile-time parameter, plus
`vectorize[simd_width](size, closure)` for width-generic loops with
scalar/tail handling, and `simd_width_of[DType]()` to query the target.
One kernel specializes per width at compile time.

Common shape: fixed-width lane type, lane-wise arithmetic, mask or
comparison story, splat/reduce, target width query, scalar fallback.

## 3. Target-feature detection

A7 has no target query today. Zig gets this free: `@Vector` compiles
everywhere, widths from `std.simd` adapt, no `cpuid` check needed in
user code. A7 should copy that posture: no user-visible
`has_avx2`-style branching in V1 of this feature. If A7 later adds a
width query, it is one builtin (e.g. `@simd_width(T)`), decided with the
module/target story, not ad-hoc per-feature flags.

## 4. Relation to tensor track and math library

Keep three layers separate:

1. Fixed-width vectors (this file): small, stack-shaped, compile-time
   lane count. Use: geometry, dot/cross/normalize, short kernels.
2. Tensors (report 09): dynamic shapes, broadcasting, views, autodiff,
   kernels from native libraries. Vectors must not grow broadcast or
   view semantics; that belongs to tensors.
3. Math library (`std/math` today: `sqrt`, `sin`, `min`, `max`, ...):
   scalar-first. Vector math overloads come after the vector type
   exists, not before.

Rule: a vector is a value with N lanes, never a slice or view. No
aliasing questions, no broadcast rules, no autograd interaction.

## 5. Auto-vectorization posture vs explicit vectors

Posture: rely on Zig's auto-vectorizer for plain loops; add explicit
vectors only where lane control matters (reductions with known order,
masks, shuffles, width guarantees).

Reasons: A7 emits Zig, so `for` loops over fixed arrays already get
whatever LLVM does. Explicit syntax pays off only for dot products,
horizontal sums, and masked selects where scalar-loop form hides intent
or float reassociation changes bits. Do not add `@vectorize`-style loop
annotations before the type exists; SPEC `§9.7` annotations are
unapproved for this reason.

## 6. Proposal (undecided, needs packet + approval)

Fixed-width vector as a type, not an annotation:

```a7
v: [4]f32 = [1.0, 2.0, 3.0, 4.0]   // plain array stays scalar semantics
w: simd[4]f32 = simd[4]f32[1.0, 2.0, 3.0, 4.0]
c := w + w                            // lane-wise add
d := w * w                            // lane-wise mul (new: backend lacks this)
s := reduce_add(c)                    // f32 horizontal sum
m := w > splat(4, 0.5)                // mask value
picked := select(m, w, splat(4, 0.0)) // lane-wise blend
```

Steps in order: (a) extend the existing `+` path to `-`, `*`, `/`
through the same `@Vector` lowering; (b) add a `simd[N]T` spelling with
lane count restricted to powers of two, convertible to/from same-shape
arrays; (c) add `splat`, `reduce_*`, `select`, and comparison-to-mask;
(d) one width-query builtin. Each step is its own packet. (a) alone
closes the checker/backend gap and needs no syntax.

Open items: float reduction order (strict left-to-right vs
reassociation; default strict per L40 direction), integer wrap vs
proven-range nonwrap inside lanes, mask spelling (bool vector vs
distinct mask type), max lane count, `usize` index rules for lanes.

## 7. Verdict: later

Need later, not now. Order: finish V1 correctness and memory work
first; then step (a) above as a small bug-close; then the tensor track
(report 09) decides whether vectors ride along or stay separate.
Never: implicit broadcast on vectors, target-feature branches in user
code, or a separate vector math library ahead of the type.
