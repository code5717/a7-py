# Autodiff tape and gradient transitions

Status: unapproved design draft. L9 selects A7-owned automatic differentiation.
It does not approve this API, a tape mechanism or failure behavior. The
[CPU AI contract boundaries](cpu-ai-contract-boundaries.md) preserve the full
four-format training and inference requirements. This document develops the
[archived AD recommendations](ai-frameworks-codex.md#ad-architecture) into
reviewable transitions. No compiler or runtime implementation is claimed.

The tensor [value](../packets/P-AI-tensor-values.md),
[cast](../packets/P-AI-tensor-casts.md) and
[reduction](../packets/P-AI-strict-reductions.md) contracts are also pending.
The proposed operations below depend on those decisions. Names are illustrative
API notation, not complete A7 programs or parser evidence.

## Recording and identity

The proposed `std/ad` module exposes opaque `Tape`, `Var` and `Gradients`
handles through free functions. `ad.open()` creates an open tape.
`ad.watch(tape, tensor)` records a differentiable leaf and returns a variable.
`ad.mul(tape, x, y)` and `ad.sum_all(tape, x)` record explicit operations.
Each fallible operation returns a canonical `Result`.

A variable identifies a node and its tape. Copying a variable handle preserves
that identity. Watching the same tensor twice creates two independent leaves.
Tied parameters must reuse one watched variable or use a separately defined
parameter table. Storage aliasing alone must not merge gradient identities.

The proposal records only the executed path through ordinary loops and branches.
Recording and reverse traversal use explicit worklists. Integer predicates and
indices select operations but are not differentiable variables. A missing
derivative rule returns `unsupported_operation`; it never records an operation
whose derivative silently becomes zero.

Each successful operation publishes its output and tape node together. A failed
operation leaves existing nodes and variables usable, releases its temporary
storage, and publishes neither a partial output nor a partial node. This requires
an implementation strategy for reserving node and output storage before commit.
Dynamic recording remains bounded by available memory.

## Backward boundary

`ad.backward(tape, loss)` proposes a scalar loss and an implicit seed of one.
A loss containing one element but having shape `[1]` is not a scalar; callers
must explicitly reduce or reshape it. Nonscalar seeds need a separate API.

| State and event | Proposed result | Tape after the call |
| --- | --- | --- |
| Open tape, wrong-tape loss or nonscalar loss | Preflight error | Open and unchanged |
| Open tape, valid loss, backward succeeds | Complete `Gradients` result | Consumed |
| Validated backward starts, then allocation or execution fails | Error, no partial gradient result | Consumed |
| Validated backward finds a nonfinite reachable value or gradient | Numerical error, no partial gradient result | Consumed |
| Consumed tape, another record or backward attempt | Rejected use | Consumed |

Preflight checks run before the irreversible transition. The transition consumes
the whole tape, including nodes disconnected from this loss. Two losses recorded
on one tape therefore need one combined scalar loss or a future multiple-root
API. Retaining a graph for repeated backward is a separate alternative.
Backward scratch allocation occurs after the transition in this proposal, so
its failure consumes the tape. Reverse evaluation visits only nodes reachable
from the selected loss. A NaN in a disconnected node does not fail backward.

The proposed finite-only backward check is separate from L16's permission for
ordinary tensor computations to produce infinities and NaNs. It needs explicit
approval. It does not authorize clipping, replacing bad gradients with zeros or
choosing an optimizer skip policy. The implementation must define a deterministic
first reported numerical error when several reachable nodes fail.

Consumption affects every alias of the tape. Checking one local handle is
insufficient. The compiler needs a rule for aliases, branch joins and failed
calls that leave the tape open. Whether rejection is static exit 6, a typed
runtime error, or a specified combination remains unresolved. This draft must
not be presented as an implementation-ready approval packet until that rule and
concrete complete programs are supplied.

### Outcome-dependent consumption

An error tag alone cannot restore a tape after an unrelated alias consumed it.
Any static refinement must connect the exact backward call, its outcome and its
tape identity. A Boolean such as `failed` is insufficient. Consider these
illustrative sequences:

| Sequence | Required distinction under this draft |
| --- | --- |
| Copy `tape` to `other`; backward succeeds through `tape`; record through `other` | Reject the second operation on the consumed identity |
| Backward rejects a nonscalar loss; record another scalar loss on the same tape | Allow recording because preflight preserved the tape |
| Backward reports scratch allocation failure; retry through another alias | Reject retry because allocation occurred after consumption |
| One branch runs backward and the other does nothing; record after the join | Identity may be consumed; an unconditional static acceptance is unsound |
| Reassign one alias to a fresh tape after backward | New identity is open; other aliases still refer to the consumed identity |

Two candidate enforcement contracts remain distinct:

| Contract | Alias and branch behavior | Cost and compatibility consequence |
| --- | --- | --- |
| Static consuming effects | Represent tape identity and refine state from specific backward outcomes; reject unresolved use at semantic exit 6 | Needs outcome-sensitive effect metadata and rules for containers, calls and loops; conservative rejection can exclude valid programs |
| Shared runtime state | Every tape alias refers to the same open/consumed state; operations return `tape_consumed` before reading released history | Supports uncertain control flow with typed errors; state checks, retention and synchronization costs enter L38 accounting |

A combination needs a stable rule for when a program fails checking versus
returns an error. Compiler analysis becoming more precise must not silently
change the public contract. Runtime state would be a mechanism choice requiring
approval, not an implied consequence of opaque handles. Static effects also
require approval; existing `del` behavior does not authorize them.

The static alternative needs separate preflight and consuming error variants
with exhaustive handling. Combining both as an undifferentiated allocation error
would prevent a caller from knowing whether retry is permitted. A helper that
returns an error must preserve the corresponding tape effect in its contract.
The runtime alternative still needs this distinction so callers can decide
whether to retry or create a new tape. No error variant may claim that a consumed
tape is open again.

This draft does not authorize sharing a mutable recording tape between tasks.
Thread confinement or synchronized recording needs a separate concurrency rule.
That rule must also define whether recording order is deterministic. Immutable
primal and gradient tensors have separate sharing requirements.

### Current compiler prerequisites

Source inspection on 2026-10-08 found mechanisms that are relevant but do not
establish this contract:

| Current source | Observation | Missing AD rule |
| --- | --- | --- |
| `a7/passes/safety.py`, `ValueFact` and `_move_allocations` | Values can carry allocation origins; deletion tracks origin sets | Opaque tape identity and open/consumed state |
| `_join_facts` and the `IF_STMT` visitor | Joins combine possible origins and moved states | Outcome-linked retained versus consumed tape states |
| The `MATCH` visitor | Visits arms from saved facts and joins reachable states | Refinement from a named backward result to the corresponding tape identity |
| The bounded exact-effect analysis near line 1007 of `safety.py` | Marks stdlib calls other than print/println as unrepresented effects | Generic opaque-handle transitions through typed calls |
| `a7/stdlib/__init__.py`, `StdlibFunction` | Holds signature, argument policy and backend mapping | Declared conditional consuming effects and retained results |
| `a7/stdlib/sources/prelude.a7` | Defines generic `Result` and `Option` tagged unions | Resource-state effects attached to their variants |

The inspected source hashes are `975394027f0e09bf23e0cea0851f81dd0411c56f8f3ae149c79ce70dae39cdc9`
for `safety.py`, `89f0e184ffcb10e8711ff654e5d57cb3898fd4f3dabd01df712d8bf72d2a6544`
for the registry, and `e4e26f6fa4faa37f67a1f0397d42c609b0d702d1a478758e821da948e86750e9`
for the prelude. These are source observations, not compiler execution evidence.
L68's typed-hook architecture permits an eventual implementation location; it
does not approve the proposed effect semantics.
An independent built-in reviewer confirmed these source boundaries. This was a
read-only source review, not a GLM review or execution test.

## Saved values and result lifetime

Under the pending immutable tensor contract, recorded operations retain the
values their derivative rules need. Reassigning a caller's tensor variable does
not change a saved value. A native kernel may not mutate retained backing
storage through an undeclared alias. Kernel completion and retention must be
part of the native bridge contract.

Backward completion releases saved history that no surviving value needs.
`Gradients` owns or retains its output tensors independently of that history.
Variable identifiers used for lookup must remain comparable after consumption
without retaining the entire graph. A returned tensor value may outlive backward
under the tensor value contract; that does not make its consumed history usable.
Observing a variable's immutable primal after consumption is proposed to remain
valid if that variable retains the primal tensor. This retention does not extend
to other nodes or saved history. The historical M23 rejection of escaping history
is still a recommendation; this draft does not silently adopt that restriction.
Automatic cleanup of an abandoned open tape is required. No manual `del` API
or production allocator mechanism is selected here.

## Gradient lookup and numerical rules

The proposed `ad.gradient(grads, variable)` returns
`Result(Option(Tensor), ADError)`:

| Result | Meaning |
| --- | --- |
| `ok(some(tensor))` | Connected variable with a defined gradient, including an all-zero tensor |
| `ok(none)` | Valid variable from the same tape with no differentiable path to this loss |
| `err(...)` | Wrong identity, unsupported query or other specified lookup failure |

An optimizer must separately decide how to handle a disconnected trainable
parameter. Returning `none` does not permit silent substitution of zero.
Failed backward produces no `Gradients` handle to query.

An AD operation needs a mathematical derivative rule as well as its rounded
forward contract. Differentiating the literal finite-bit mapping would give a
different result from the usual real-valued operation rule. The packet must
state which rule applies to arithmetic and explicit casts. Cast derivatives
must not be inferred from the pending conversion packet.

Four-format coverage requires a table for leaf gradients, intermediate adjoints,
products, sums and returned gradient tensors. F32 adjoints for F16/BF16 leaves
are a candidate, not an adopted rule. Narrowing at every edge and narrowing only
at the final update can produce different training results. F64 gradients must
not silently pass through F32.

Shared operands create multiple contributions. A deterministic candidate visits
reachable nodes in reverse recording order, then input slots in declaration
order. Repeated-index and broadcast contributions also need an explicit logical
coordinate order. Each accumulation must name its dtype and rounding rule.
Choosing strict forward reductions alone does not settle backward accumulation.
The eventual precision table must also state the initial accumulator value and
whether independent output elements can run concurrently without changing bits.

## Analytic acceptance cases

These are exact real-arithmetic expectations, not native execution results.
The eventual packet must bind them to approved operation and dtype contracts.

| Computation | Expected distinction |
| --- | --- |
| `x = [2, -3]`, loss is the sum of `x * x` | Gradient `[4, -6]`; both occurrences contribute |
| `x = [0]`, loss is the sum of `x * x` | Connected gradient `[0]`, returned as `some` |
| Watch `x` and `y`, then reduce only `x` | `y` lookup is `none`, even if its stored value equals `x` |
| Reuse one watched scalar three times in a broadcast sum | One leaf receives gradient `3` |
| Watch the same tensor twice, then reduce only the first leaf | The second leaf is disconnected |
| Sum a watched empty tensor | Connected empty gradient with the original shape |
| Two aliases of one tape, backward through the first | The second cannot record or run backward |
| Recording fails before commit | Earlier variables and tape nodes still work |
| Backward fails after preflight | All tape aliases are consumed; no partial gradients escape |

Qualification also needs operation-specific derivative tests, view scatter
rules, repeated-index accumulation, nonfinite cases, allocation failures and
saved-value lifetime tests. Finite differences apply away from nondifferentiable
points and need stated step sizes and tolerances. ReLU at zero, maximum ties,
clipping boundaries and other nondifferentiable conventions require explicit
choices. A decreasing training loss cannot replace these checks.

## Alternatives and compatibility

An implicit tape would reduce explicit parameters but needs rules for ambient
scope and nested recording. A persistent tape would allow repeated backward but
needs explicit release and retention behavior. Treating disconnected leaves as
zeros would simplify callers while hiding missing connections. These alternatives
need concrete costs and examples before selection.

The explicit proposal adds library behavior without changing ordinary scalar,
array or function semantics. First-order reverse differentiation is a proposed
initial contract. Forward-mode, higher-order and custom-gradient support need
separate coverage declarations. This draft does not remove required classifier,
decoder, checkpoint, inference, kernel or cost qualification from V1.
