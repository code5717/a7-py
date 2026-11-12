# Concurrency transition contract draft

This draft proposes observable outcomes for structured tasks and bounded
channels. It is not an approved API, executable A7, or runtime qualification.
It does not select an allocator, reference counter, scheduler or new syntax.
L73 requires real concurrency for V1; L40 permits inferred independence and
keeps work with unknown effects sequential. Neither decision approves the
choices below. Implementation must wait for the complete decision packet.

The [prerequisite inventory](../../../tmp/v1-completion-2026-10-07/concurrency-design-prerequisites/REPORT.md)
records the current source boundary. The registry exposes `io` and `math`;
the inspected compiler paths have no task/channel lowering. Historical
[memory recommendations](../memory.md) and
[failure scenarios](memory/audit/audit-3-concurrency-failure-native.md)
are design inputs, not adopted semantics.

The [current import probes](../../../tmp/v1-completion-2026-10-07/concurrency-current-probe/REPORT.md)
confirm that `std/tasks` and `std/channels` each fail with exit 3 in semantic
and compile modes on frozen source `de578138`. A sequential scalar function
call passes both modes. These results establish module availability and
emission behavior only; no native program ran.

## Proposed task outcomes

A task group owns its children until each child has stopped and its cleanup
has completed. A returned value remains alive until its parent consumes or
discards it. Joining a child transfers its result once. No child or task handle
escapes its group in this proposed V1 contract.

| Initial state | Event | Proposed next state and observable outcome |
| --- | --- | --- |
| Arguments belong to caller | Start cannot reserve task resources | Start fails; caller retains arguments and no child exists |
| Arguments belong to caller | Start commits | Child owns transferred arguments; caller cannot mutate through old aliases |
| Child running | Parent requests cancellation | Request becomes visible; child still owns its values and remains live |
| Child running | Child observes cancellation | Child releases its resources, then publishes a cancelled outcome |
| Child running | Child completes before observing cancellation | Child publishes its result; a later request cannot replace that result |
| Child running | Child reports recoverable failure | Child cleans up, publishes the failure, and requests sibling cancellation |
| Child terminal | Parent joins | Parent receives the stored result, failure or cancellation outcome once |
| Group open | Parent exits normally or early | Group refuses starts, requests cancellation, wakes blocked operations and joins all children before releasing parent storage used by them |

Terminal publication follows cleanup. A parent cannot interpret a cancellation
request as permission to reclaim child storage. A native operation retaining a
buffer keeps that buffer alive until its declared completion event, even when
cancellation has been requested.

Before cleanup, a successful child transfers its result into group-owned outcome
storage. Cleanup releases its remaining child-owned values. Join transfers the
stored result to the parent once; group disposal releases unconsumed results.
Failed start preserves argument ownership but does not roll back side effects
from evaluating argument expressions.

Parent storage used by children must remain alive through their completion.
The relative order of parent defers, child cancellation, joins, channel disposal
and native callback servicing remains unresolved. A child may depend on a parent
defer closing an external producer, or on a callback serviced by the joining
thread. The decision packet must resolve these dependencies before prescribing
a universal cleanup order. The group-exit row states lifetime obligations only.

### Cleanup ordering alternatives

Current A7 defers run at scope exit in LIFO order, as specified in
[`docs/SPEC.md`, section 8.3](../../SPEC.md#83-defer-statement).
The concurrency proposal must preserve ordinary sequential defer ordering.
Implicitly moving all parent defers ahead of joins could release borrowed
storage; moving them all after joins could prevent a child from finishing.

These traces describe proposed operations, not executable A7:

| Trace | Event sequence | Consequence |
| --- | --- | --- |
| Join first | Child waits for producer end; parent waits for child; parent producer-close defer has not run | Neither wait can finish |
| All defers first | Parent releases buffer; child still reads buffer; parent joins | Child accesses released storage |
| Cancel only | Parent requests cancellation; child remains inside an uninterruptible native read; parent joins | Request alone cannot complete shutdown |
| Separate stop from release | Parent signals producer stop without releasing borrowed storage; child completes and cleans up; parent joins; storage releases | Lifetime and progress obligations can both hold, subject to the producer's stop contract |

The recommended direction is an explicit stop phase followed by mandatory join
and then release. Stop operations must describe what they wake and which values
they access. They cannot release or mutate storage that a child still borrows.
An external producer's stop operation may signal its endpoint without freeing
the endpoint or the child's input buffer. Its descriptor must distinguish those
effects; naming an operation `close` is insufficient.
The stop operation must preserve outstanding child accesses. It cannot invalidate
a borrowed descriptor unless that descriptor's concurrent-shutdown contract
permits the operation. Stop failures are recorded while remaining defined
shutdown steps continue; a recoverable stop failure cannot skip mandatory joins.

Joining during group shutdown cannot abandon a child when the parent receives
another cancellation request. The group retains the child's dependencies until
completion. A native callback that requires the joining thread needs a declared
progress protocol. Running arbitrary user callbacks while joining would add
reentrancy and ownership obligations and is not implied by this draft.
The protocol must name the callback's execution context and dependencies,
including locks and event loops. It cannot allow reentrant group starts or access
to partially cleaned parent state. A declaration alone does not prove progress.

Child cleanup must not depend on queued payloads or unconsumed results whose
disposal waits until after join. Resource contracts must expose these dependencies;
unresolved dependencies prevent admitting the operation under this proposed
contract. Transferring a result must also transfer or retain the dependencies
needed to use it. Group shutdown cannot release storage still needed by a result
transferred to the parent. Unsupported borrowed-result escape must be rejected.

An alternative is to prohibit children from borrowing parent values and require
independent task-owned inputs. That removes some parent-storage dependencies,
but it still cannot make an uninterruptible native call finish. Another option
is to require explicit joins before every return and reject live children at
scope exit. That exposes cleanup to each caller and still needs an early-failure
contract. The public packet should compare these costs against L19 rather than
choose an option solely because it is easier to implement.

No general deadlock-freedom claim follows from the recommended phase ordering.
A child can wait for an event its parent never sends. Admission rules for native
retention, callback thread affinity and stop effects need approval with the
native boundary. Existing sequential native behavior is outside that proposed
task-admission change.

The proposed group result includes all unconsumed child failures in start order.
A failed child must not disappear because the parent joined another child first.
The decision packet must reconcile that result with early return and the future
error representation. Process abort is separate: it cannot promise completed
cleanup or a recoverable group result.

## Proposed channel commit rules

The proposal uses positive, explicit bounded capacity. Zero-capacity rendezvous
and unbounded queues remain alternatives for the decision packet. One group
owns a channel. Its close authority is explicit; dropping the last sender does
not imply close in this draft. Sends preserve FIFO commit order. Concurrent
senders have no source-order guarantee.

| Initial state | Event ordered at the channel commit point | Proposed outcome |
| --- | --- | --- |
| Sender owns payload; space available | Enqueue commits | Queue owns payload; sender receives sent, even if cancellation arrives afterward |
| Sender owns payload; send has not committed | Close or sender cancellation wins | Sender receives closed or cancelled together with the unsent payload |
| Queue owns payload | Dequeue commits | Receiver owns payload; cancellation arriving afterward cannot discard it |
| Receive pending; queue empty and open | Receiver cancellation wins | Receiver receives cancelled; no payload changes owner |
| Channel open | Authorized close commits | New sends fail; queued values remain available to receivers |
| Channel closed and empty | Receive | Receiver receives end of stream |
| Group draining | Group stops channel operations | Uncommitted sends return their payloads to their tasks; remaining queued values are released once after child cleanup |

Close and cancellation wake affected blocked operations. When both could stop
an operation, the first event ordered before its commit determines the outcome.
The runtime must record one outcome, rather than return cancellation after
silently enqueueing or consuming a payload. Group draining cancels pending
operations; it does not promise delivery of queued values during shutdown.
An uncommitted send retains its payload in sender-owned storage until normal
handling or cancellation cleanup releases it. A committed receive transfers
the payload into receiver-owned storage before cancellation cleanup can begin.

## Sharing and responsiveness

The proposed sharing rule permits read-only parent data until the last child
using it has finished. Conflicting parent or sibling writes are rejected unless
independence is established. Disjoint regions need an explicit proof contract;
different variable names alone do not establish independence. Mutable globals
reachable from task calls require the same analysis. Existing sequential global
mutation stays valid. This differs from the historical proposal to make all
globals immutable after startup and requires an explicit compatibility decision.

Cancellation is cooperative in this draft. Channel waits and joins observe it;
CPU loops require observation points. A native call must declare whether it can
be interrupted and how completion is reported. Without such a declaration,
shutdown waits for the call to return. This draft promises no finite shutdown
bound for a child that never observes cancellation. Compiler-inserted loop
checks, explicit checks, and their measured costs need a decision before the
public packet can claim responsive CPU workers.

Cancellation of a user-facing join may stop that wait. It does not discharge
the group's obligation to retain and finish the child. Whether shutdown joins
are protected from cancellation, and how they make progress, remains a decision.

## Acceptance oracles for the decision packet

These are required observations under the proposed contract, not passing tests.
Each native case needs event synchronization so its assertion does not depend
on a sleep or a lucky schedule.

| Scenario | Observable requirement |
| --- | --- |
| Start fails before commit | Caller can still use and release each argument; child-start counter stays zero |
| Parent returns with a child borrowing data | Child cleanup completes before the parent's data-release event |
| Cancellation races with send | Exactly one sent or unsent outcome occurs; exactly one owner releases the payload |
| Cancellation races with receive | Payload is delivered once or remains queued; it is never lost between owners |
| Ordinary close with queued values, without group shutdown | Committed values drain in FIFO order, then end of stream; later sends return their payloads |
| Sibling fails while a child waits on a full channel | Waiting child wakes; group reports the failure and waits for all cleanup |
| Child returns a resource | Result remains usable after join and is released once by its eventual owner |
| Parent writes data still read by child | Compiler rejects the conflict; read-only and proven-disjoint controls remain accepted |
| Cancellation during a retaining native call | Buffer release follows native completion, never the cancellation request |
| Two independent CPU children | Instrumented native execution proves overlapping work on the permitted local CPU set |

These oracles do not prove deadlock freedom, fairness, bounded latency or L38's
per-workload cost limits. Those claims require separate contracts and measurements.
The full packet also needs concrete A7 examples, error/result syntax, task and
channel construction, close authority, cleanup-failure behavior, compatibility
cases and an independent review. No approval is requested for this draft alone.
