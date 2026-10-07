# 24 — Tensors: the smallest story that keeps §9 honest

Status: simplification audit, second round. Parent: `09-concurrency-tensors.md`.
SPEC §9 (lines 1190–1530+) is a design target; no tensor code compiles today.
Goal: cut §9 to the smallest core that stays honest, push the rest to LATER/library.

Thesis: keep owned values + right-align broadcast + explicit casts +
copy-not-view + one multi-index form. Cut autodiff direction, precision
policy, device story, and pragmas. Everything else is library calls.

## 1. What §9 promises today (too much)

§9.1: static `Tensor($T,$N)` plus `DynTensor` plus 4 sugar aliases.
§9.2: NumPy broadcast + scalar broadcast + 6 elementwise ops + math fns.
§9.3: reshape/transpose/expand/squeeze/concat/split/stack + view ops that share memory.
§9.4–9.5: reductions, stats, argmax, matmul/dot, eig/SVD/QR/LU, det/inv/norm.
§9.6: conv2d, pooling, 4 activations, batch/layer norm, grad_enable/backward/no_grad/clip.
§9.7: C/F/strided layout picks, contiguous/copy/clone, `@vectorize @parallel @prefetch`.
§9.8: 4 index forms (multi-index, ranges, boolean mask, int-array + fancy pairs).
§9.9: creation/cast/IO plus `tensor_to_gpu/to_cpu/device`.

That is a framework, not a core. It repeats the PyTorch mistake (09 §3):
user-visible views, in-place ops, and version counters.

## 2. What each reference refused to put in the core

- PyTorch: core is eager mutable buffers + autograd tape. Refused: static
  shapes, functional purity, device abstraction (`.to(device)` is stringly
  API). Views share storage; `view` vs `reshape` vs `clone` leaks (09 §3
  table). Lesson: mutable-view core buys speed, pays with a hazard class.
- JAX: core is pure functional arrays (`arr.at[i].set(v)` returns new array),
  XLA-staged transforms (`grad/jit/vmap`). Refused: in-place mutation, views,
  eager tape, device syntax (devices are mesh args to `jit`, not types).
  Lesson: purity + staging covers autodiff without any tape syntax.
- TinyGrad: core is immutable lazy values + realized-on-demand graph.
  Refused: views (every op is a new value), explicit devices in the type,
  precision policy (dtype is a tensor property, autocast is library).
  Lesson: smallest viable tensor core is ~value + lazy op + realize.
- Burn (Rust): core is owned tensors over a backend trait. Refused: kernel
  code in the language, layout control in user syntax, autodiff direction
  in types (backward is a backend pass). Lesson: trait boundary beats syntax.
- Mojo / MAX: core is owned values with borrow-checked slices. Refused:
  implicit broadcast in static code (explicit shapes), GC-managed buffers,
  device placement in the type. Lesson: explicit shapes + lifetimes scale;
  implicit magic does not.

Pattern: nobody put autodiff direction, precision policy, device placement,
or perf pragmas in core syntax. All four live in library/transformer/backend
layers. A7 should do the same.

## 3. Proposed core (5 rules)

1. Tensors are owned values. One type: `Tensor($T: Numeric, $N: u8)` with
   `data/shape/strides`. `DynTensor` is the same struct with runtime shape;
   no separate spelling needed beyond elided `$N`.
2. Right-align broadcast only: shapes align trailing axes, size-1 stretches,
   else compile error. Scalar stretches always. No other implicit expansion.
3. All casts explicit: `tensor_cast` only. No promotion table, no autocast,
   no literal-default-dtype decision (literals keep scalar rules from G1).
4. Copy-not-view: slicing, reshape, transpose return new owned values.
   Backend may reuse buffers (last-owner reuse, Bend-2 style) but user syntax
   never observes aliasing. Deletes `tensor_view/flatten-view/contiguous`
   distinction from §9.3/§9.7.
5. One index form: `t[i, j, k]` with integer indices and `a..b` ranges per
   axis. Boolean-mask, int-array, and fancy-pair indexing become library
   functions (`tensor_where`, `tensor_gather`), not syntax.

Everything in §9.4–9.5 (reductions, linalg) is then plain library functions
over this core. No syntax needed.

## 4. KEEP / CUT / LIBRARY

KEEP (core language): owned `Tensor($T,$N)`; nested-literal construction;
elementwise `+ - * / %` with right-align broadcast; `tensor_reshape`,
`tensor_transpose`, `tensor_concat/split/stack` as value ops; single
multi-index + range form; `tensor_shape/ndim/size/dtype` queries;
`tensor_matmul` as the one named op (justifies 2D story).

CUT to LATER (not V1, not library): autodiff direction choice
(tape vs staged — decide at transformer time, JAX-style); mixed-precision
policy + loss scaling + autocast; device story (`to_gpu/to_cpu/device`,
placement syntax, transfer-cost promises — 09 §5 already forbids);
pragmas `@vectorize @parallel @prefetch` (backend hints, not semantics);
C/F/strided layout picks (backend concern); grad ops
(`grad_enable/backward/no_grad/clip_grad`); checkpoints/recipes/thresholds.

LIBRARY (functions, no new syntax): creation (`zeros/ones/eye/arange/
linspace/random/from_data`); `tensor_cast`; reductions/stats
(`sum/mean/max/min/std/var/argmax`); linalg (`dot/cross/eig/svd/qr/lu/
det/inv/norm`); NN prims (conv2d, pool, relu/sigmoid/softmax/gelu,
batch/layer norm); `tensor_where/gather` (covers cut index forms);
`tensor_save/load/print`.

Open question kept open deliberately: static-vs-dynamic shape checking
strength. Core works either way; do not block V1 on the checker.
