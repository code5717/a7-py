# 09 — Concurrency and tensors/AI future

Status: design constraint, not V1 work. Per L36, V1 ships the core language,
automatic memory, libraries and tools first. AI and concurrency stay as
constraints on current decisions and as later delivery tracks. Per L40,
unknown effects stay sequential; parallelism is inferred only where safe.
Nothing in this file is approved syntax. Every spelling below is undecided.

## 1. Current absence

A7 has no task, channel, or tensor syntax today. No tensor code compiles.
`docs/plan/README.md` G7 states "A7 has no task syntax today" and G8 states
"SPEC section 9 is a design target; no tensor code compiles today."
The G7/G8 code sketches in that file are proposals, not accepted language.
Any new syntax needs a before/after packet and explicit approval first.

## 2. Concurrency: what G7 must decide

G7 covers structured task lifetime, cancellation, join outcomes, and channel
close. It depends on G5 (errors, matching, composite values) and memory gate
M10. Open questions, quoted from `docs/plan/README.md`:

- If one task in a group fails, what happens to the others.
- What each join reports (value, error, cancellation).
- Whether `close` on a channel is explicit.

### How others handle each item

| Item | Reference behavior |
| --- | --- |
| Structured tasks / join | Kotlin-style structured concurrency: a scope ends only after all child tasks end. Failure of one child cancels siblings by default; the scope reports the first failure. This matches the G7 sketch where `task_group` ends after both tasks end. |
| Cancellation | Go uses explicit context cancellation passed by the caller. Kotlin uses cooperative cancellation: suspend points check, blocking code must cooperate. A7 should pick cooperative cancellation tied to task scope, since preemptive kill breaks the memory story (see section 5). |
| Channels / close | Go channels: `close` is explicit, send-on-closed panics, receive yields zero value plus ok-flag. Kotlin channels: `close` is explicit, receive throws on closed-empty. A7 must decide close ownership: only the sender side closes, and double close is an error. |
| Task = memory home | `docs/plan/research/memory/advice-glm.md` proposes: a task is a memory home; values moved into a task live in a home that ends at join. Deterministic cleanup by construction. Channel-queued values need a home that outlives the join point. |

### Design constraint for V1

V1 code must be writable so that later task inference is sound. That means
the typed IR (roadmap step 3) records read/write effects and storage identity
now, even though no parallel execution exists. L40: unknown dependencies stay
sequential. Strict float order by default; a changed reduction order needs an
explicit contract.

## 3. Tensors: value semantics, broadcast, views

G8 and memory gates M11, M17–M24 cover this. Decisions needed:

- Literal default dtype (`f32` or `f64`). L11 names tensor formats; scalar
  floats stay `f32`/`f64`. Undecided for tensor literals.
- Value vs view: does slicing share storage or copy. Memory gate M18
  recommends rejecting a write to a buffer saved for backward at compile time.
- Broadcast rules: implicit shape expansion or explicit spelling.

### How others handle each item

| Item | Mojo / MAX | TinyGrad | Burn (Rust) | PyTorch | JAX |
| --- | --- | --- | --- | --- | --- |
| Value semantics | Mojo tensors are owned values; slices borrow with lifetimes | TinyGrad tensors are immutable lazy values; ops build a graph, realize on demand | Burn tensors are owned; backend trait abstracts storage | Eager mutable buffers; views share storage, in-place ops allowed with autograd version checks | Pure functional arrays; no in-place mutation at all |
| Broadcast | Explicit shapes, static checks where possible | NumPy-style implicit broadcast | NumPy-style implicit broadcast | NumPy-style implicit broadcast | NumPy-style implicit broadcast (XLA) |
| Views | Borrow checker governs aliasing | No views: every op is a new lazy value | Backend decides; API is value-oriented | Views share storage; `view` vs `reshape` vs `clone` is user-visible | No views; `arr.at[i].set(v)` returns a new array |

Recommendation for A7: TinyGrad/JAX direction. Tensors are values, not
mutable buffers. Updates are functional. Buffer reuse happens inside the
backend (last-owner reuse, as in Bend 2), not in user-visible syntax. This
fits L40 inference (pure ops parallelize freely) and avoids the PyTorch
view/in-place hazard class entirely.

## 4. Kernels, autodiff tape, mixed precision, training state

### Kernels (L9)

L9: A7 owns tensor semantics and autodiff over established native kernel
libraries. A7 does not write its own matmul. The Zig native bridge (L41)
calls existing kernels. V1 work: checked synchronous Zig bindings only.
No kernel work in V1.

### Autodiff tape

`docs/plan/research/ai-frameworks-codex.md` section 6 compares designs:
tape-based (PyTorch: record ops, replay backward) vs staged (JAX: trace to
graph, transform with `grad`). For A7, decide:

- What the tape (or staged graph) saves: values, shapes, or closures.
- Non-differentiable boundary spelling: which ops stop gradients.
- Mutation of saved values: reject at compile time (M18 direction) rather
  than PyTorch-style runtime version counters.

### Mixed precision

Same research doc, section 5: decide default dtype, promotion vs explicit
casts, and where loss scaling lives. Constraint for V1: keep scalar rules
exact and documented (G1, L33 constant work) so later precision policy has a
sound base. No autocast in V1.

### Training state

Checkpoints, skipped-step and retry rules, model recipes, accuracy
thresholds, named CPU target: all G8 items. None in V1. Record formats must
be versioned from day one when the track starts; do not invent an
unversioned format first.

## 5. GPU adapters (interface only)

L8: CPU first, with an accelerator interface for a later GPU backend.
L41: Zig handles native imports, runtime, builds, linking. What V1 may do:

- Keep target selection separate from storage ownership and physical
  placement (roadmap: a shared address model does not prove zero cost).
- Design the native bridge so a GPU backend can plug in later without
  changing A7 source semantics.

What V1 must not do: qualify any GPU/NPU target, ship device placement
syntax, or promise transfer costs. No CUDA/Metal paths until a Zig-based
integration path is demonstrated (roadmap condition).

## 6. Staged roadmap: what must exist first

1. Typed IR with read/write effects and storage identity (roadmap step 3).
   Both concurrency inference and tensor optimization read this. No IR
   effects, no safe parallelism, no tape analysis.
2. Memory decision (M-gates). Task homes, channel-queued value lifetimes,
   and tensor buffer reuse all depend on the selected memory contract.
   G7 depends on M10; G8 on M11, M17–M24.
3. Checked synchronous native bridge through Zig (L41). Kernels and later
   GPU adapters attach here. Async/device execution comes after sync is
   sound.
4. Then, in order: structured tasks with explicit close/join semantics;
   value-semantics tensors on CPU with a small kernel set; autodiff over
   the staged graph; mixed precision policy; GPU adapter behind the
   interface from step 3.

Bend 2 is ideas only, not an adopted runtime: CPU workers, Metal/CUDA
paths, reference counting, last-owner reuse. Take annotated parallelism and
reuse discipline; do not take its runtime.

## 7. Constraint vs V1 work (per L36)

Stays a design constraint (shapes V1, ships later): task/channel syntax and
semantics, tensor types and ops, autodiff, precision policy, checkpoints,
GPU targets and placement.

V1 work that keeps the future open: IR effects and storage identity, memory
contract selection with task/tensor lifetimes in mind, strict float order,
explicit-copy list semantics (L42), checked sync Zig bindings, G1 float
exactness. Review the IR against disjoint array updates, cancellation,
tensor buffers and training saved values without claiming those features
ship (roadmap, AI section).
