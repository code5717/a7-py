# CPU AI contract boundaries

CPU AI is required for V1 under L73. The following separates adopted requirements
from proposed implementation and acceptance choices. It reconciles the archived
[AI review](ai-frameworks-codex.md) and
[tensor audit](memory/audit/audit-4-tensors-autodiff.md) against the current
[decision ledger](../decisions.md). It does not approve an API or kernel provider.

## Adopted requirements

| Requirement | Authority | Evidence needed for completion |
| --- | --- | --- |
| Tensor operations, training and inference | L7 and restored V1 boundary L73 | Implemented A7 programs and native results |
| CPU-first implementation | L8; GPU execution separately deferred by L75 | Qualified local CPU runtime; no GPU substitute claim |
| A7-owned tensor semantics and automatic differentiation using established kernels | L9 | A7 operation/gradient contracts, runtime implementation and native bridge evidence |
| Small image classifier and decoder transformer with checkpoint recovery | L10 | Frozen recipes, held-out evaluation, separate inference and fresh-process continuation |
| Tensor f16, bf16, f32 and f64 | L11 | Per-format storage, conversion, arithmetic and accumulation evidence |
| IEEE values and strict arithmetic by default | L16 | Exceptional-value and rounding behavior; explicit opt-in for result-changing optimization |
| Per-workload median runtime and peak live memory at most 1.10 times reviewed C | L38 | Equivalent measured workloads including bookkeeping; reserved memory, RSS, allocations, copies, cleanup and compiler costs also reported |

L38 does not set model accuracy, numerical error tolerance, dataset size or
training duration. Those values cannot be inferred from the 1.10 cost ratio.
The comparator must implement the same proposed operations, precision and
training-state transitions. A faster program with different numerical semantics
is not an equivalent baseline.

## Current source boundary

SPEC section 9 labels its tensor API and autodiff examples as proposals.
The inspected default registry registers `io` and `math`; it does not register
a tensor module. Independent scoped searches of `a7/` and `test/` found no
tensor/autodiff implementation or qualification suite. A fixed-array variable
named `tensor_3d` and a backend list containing Zig's reserved name `f16` do not
establish tensor support. These are source observations, not execution evidence.

The historical AI review's opening describes optimizer, RNG and checkpoint
ownership as part of an approved architecture. L9 explicitly selects tensor
semantics and AD ownership; the detailed state contract still needs a proposal.
The review also predates L16's IEEE decision and L73's restored full V1 scope.
Its recommendations cannot reopen those decisions or defer required CPU AI.

## Contract fields to settle together

| Area | Concrete decision needed | Failure of an incomplete substitute |
| --- | --- | --- |
| Tensor values | Rank/shape, views, strides, mutation and aliases | A descriptor alone does not preserve saved backward values |
| Precision | Input/output formats, casts, promotion and accumulator widths per operation | A dtype name does not establish mixed-precision computation |
| Reductions | Order guarantees, special values and permitted kernel variation | A single global tolerance can hide wrong axes or cancellation errors |
| AD | Tape/result lifetime, repeated backward, shared gradients and nondifferentiable points | Decreasing training loss does not prove correct gradients |
| Numerical failure | Nonfinite gradients, skipped updates, RNG advancement and loss scaling | Skipping parameter writes alone can still corrupt optimizer continuation |
| Workloads | Classifier/decoder definitions, data, preprocessing, seeds, steps and quality thresholds | Tiny-batch overfit does not prove held-out performance |
| Checkpoints | Exact saved state, publication boundary, validation and continuation compatibility | Weights-only reload cannot prove resumed training |
| Native bridge | Kernel semantics, completion, retention, thread counts and failures | Calling a framework cannot stand in for A7-owned AD |

A tensor reduction contract must reconcile optimized kernels with L16 rather
than silently inherit a provider's arithmetic choices. Strict scalar arithmetic
does not by itself specify the order of every new tensor reduction. Conversely,
calling an operation a tensor kernel does not authorize result-changing compiler
rewrites. The packet must state the intended operation and any explicit opt-in.

## Checkpoint continuation oracle

The proposed oracle compares one uninterrupted training branch with a fresh
process restored from the same committed boundary. Both must execute the same
next input batch and next update. Freeze the comparison before qualification.

| State or observation | What the comparison must detect |
| --- | --- |
| Model configuration, operator conventions, precision policy and runtime/kernel compatibility | Identical arrays interpreted with different architecture, epsilon, masking, update rules or computation settings |
| Parameters and persistent model buffers | Missing weights, stale running statistics or wrong dtype |
| Optimizer moments and update counters | Correct inference weights paired with an incorrect next update |
| Scheduler and loss scaler | Changed learning rate or mixed-precision skip decisions |
| RNG algorithm, version and state | Different dropout or sampling after restart |
| Dataset order, position and preprocessing/tokenizer identity | Repeated, skipped or differently interpreted input |
| Pending accumulated gradients, if that boundary is supported | Lost partial accumulation |
| Next loss, gradients, update decision and resulting state | A restored checkpoint that loads but does not continue equivalently |

The proposal must choose checkpoint boundaries explicitly. Supporting only a
completed update boundary can be a public contract choice; it cannot be an
undocumented workaround that drops pending gradients. Bitwise continuation can
only be claimed within a qualified configuration. Cross-provider or cross-thread
compatibility needs its own selected comparison rule.

The packet must select whether a rejected load leaves live state unchanged and
usable, or explicitly invalidates it so training cannot continue. Compare the
whole state against that selected outcome, not only the parameter array. The
recommended direction is unchanged usable state, but the historical memory
proposal's loading behavior is not approval of that choice.
After an interrupted save, a previous committed
checkpoint must remain usable under the selected publication contract. These
are acceptance requirements to propose, not claims about existing recovery code.

## Independent numerical evidence

Use exact small representable examples, analytic gradients, f64 finite
differences away from nondifferentiable points, and a separately implemented
reference. Compare shared-operand and repeated-index gradients to accumulation
oracles, not just output shapes. Framework agreement is weaker when both paths
call the same native kernel. Keep end-to-end training and packaged inference
as separate acceptance observations.

No model recipe, tolerance, runtime, checkpoint format or kernel library is
selected here. The next CPU AI packet must bind these fields to concrete
programs and measurable thresholds before dependent implementation. GPU work
remains deferred under L75; its V1 execution requirement remains intact.
