# Memory research reconciliation and measurement proposal

Status: draft, 2026-09-20. This is preparation for a memory decision packet,
not a completed packet or an approved contract. No candidate has been measured
under this protocol. Numeric budgets below are proposals. They do not qualify
A7, approve language changes, or replace the user's memory requirements.

## Decisions still open

The [ledger](../../decisions.md) records the user's requirements. The
[memory plan](../../memory.md) is revision 3 and explicitly unapproved. Its
M48 entry reports a suggested ordinary/advanced split. This draft does not adopt
that split. Measure the whole corpus, including resources, tasks and tensors.

| Question | Existing evidence | Current disposition |
| --- | --- | --- |
| Reject escapes or insert copies | The [synthesis](synthesis.md) records advisors rejecting unproved escapes without hidden copies. Later plan revisions instead copy escaping values. | Compare both outcomes. Neither is consensus or approval. |
| Can Perceus establish a count-free design | The [reuse study](reuse-languages.md) separates static drop/reuse placement from runtime uniqueness checks. | It cannot establish that result. RC remains a comparison baseline. |
| Does FP² settle static reuse | The same study distinguishes function-definition checks from call-site sharing. It records uniqueness typing with specialization costs and Koka's runtime fallback. | A7 still needs a call-site mechanism and evidence for its restrictions. |
| Optional copies or temporary lookup views | [Review reconciliation](review/README.md) and memory-plan section 10 record Qwen and GLM performance/consistency preferring views. M33 still proposes copies. | Keep both candidates and measure read-heavy and nested-update programs. |
| Recoverability | Reviews disagree between extent boundaries and fallible signatures. | Specify observable recovery before choosing syntax or lifetime rules. |
| Tensor lifetime boundaries | Reviews disagree between tensor-specific structural rules and simpler call/iteration/task boundaries. | Trace actual training state and failure paths before choosing. |
| Stored function values | Reviews disagree over type-informed call edges and exclusion. | Resolve jointly with recursion and effect-summary rules. |
| Simplicity | The plan acknowledges that tables, ids and move-only resources introduce concepts. No decision says L19 overrides L17 or permits exempting advanced code. | Count concepts and rewrites without exempting any workload category. |
| C-like performance | [GLM performance](review/glm-performance.md) identifies copy fallback, retention and baseline bias. Its margins were proposals. | Freeze budgets and baseline procedures before measuring candidates. |

The [fact check](functional-memory-fact-check.md) labels several claims unchecked.
The [review index](review/README.md) records completed historical reviews of
revision 2, followed by revision 3 changes. The security review compiled and ran
nothing. Those reports establish questions and design risks, not current native
safety or performance.

## Primary-source check, 2026-09-20

Perceus inserts reference-count operations and uses runtime uniqueness information
for reuse. Its results do not establish a reference-count-free A7 design.
See the [Perceus paper, sections 1 and 2](https://www.microsoft.com/en-us/research/uploads/prod/2021/06/perceus-pldi21.pdf).

FP² checks function definitions, but safe destructive calls also require sharing
information at call sites. Section 1.4 compares static uniqueness typing with the
runtime reference-count checks used by its Koka implementation. These are distinct
mechanisms, not evidence that arbitrary A7 programs can update in place.
See the [FP² paper, section 1.4](https://www.microsoft.com/en-us/research/wp-content/uploads/2023/05/fbip.pdf).

## Candidate comparison requirements

Compare each mechanism in isolation where possible, then compare combinations.
Do not label the proposed layer stack the selected architecture before approval.

| Candidate | Evidence required |
| --- | --- |
| Static ownership and region inference | Accepted programs, required lifetime restrictions, release points, retained bytes, branch/loop/call behavior and rejection diagnostics. |
| Compiler-inserted copying | Copy locations and byte counts, alias semantics, failed-allocation behavior, peak memory and proof failures that caused a copy. |
| Static uniqueness and reuse | Definition and call-site proofs, invalidation by aliases, specialization count, generated-code size, missed reuse and runtime cost. |
| Automatic placement and packing | Placement determinism, alignment, live-range interference, dynamic-size handling, planner bounds and cleanup of non-memory resources. |
| Reference counting baseline | Count operations, header space, cyclic-data policy, atomic operations where required, pause/teardown distribution and adaptive reuse. Not an approved A7 mechanism. |
| Tracing baseline | Heap reserve, collection work, pauses, peak memory, roots and resource cleanup policy. Not an approved A7 mechanism. |

For every candidate, report unmodified accepted cases, rejected cases, required
programmer rewrites, new concepts, copies, allocations, peak memory, execution
cost and compiler cost. Do not replace a rejected case with a rewritten case in
the aggregate result. Report both. Separate runtime allocation and checks from
compile-time reasoning.

## Workload specifications

These requirements describe application behavior without prescribing A7 syntax,
ownership, reference counts, tables, region boundaries or hidden copies. Proposed
A7 examples belong in the later decision packet. Each workload needs a positive
case and the stated invalid or failure case.

| ID | Program and deterministic input | Independently stated outputs and invariants |
| --- | --- | --- |
| W1 | Grow a sequence by appending integers 0 through 9,999. Keep a logical reference to the item whose stable application key is 123. | Length 10,000, sum 49,995,000, key 123 still identifies value 123 after growth. An access to a missing key reports absence. The implementation must explain any required rewrite to preserve that application identity. |
| W2 | Nested invoice data starts with row values `[2, 3]`. Two application paths intentionally identify the same row. Increment the first element by 5 through one path. Separately create a historical snapshot before that update. | Both live paths read `[7, 3]`; the historical snapshot reads `[2, 3]`. Preserve the distinction between shared identity and a requested snapshot. Any candidate unable to express it must report rejection or a rewrite. |
| W3 | Build nodes 0 through 3 with edges `0→1`, `1→2`, `2→0`, `2→3`. Traverse from 0 with visited-node tracking; remove node 1 and its incident edges. | Initial traversal visits four distinct keys with sum 6. Afterwards, node 1 is absent, traversal from 0 visits only 0, and nodes 2 and 3 remain stored. Releasing the graph leaks no storage. The cycle is data, not recursive execution. |
| W4 | A producer creates records with keys 0 through 999 and values twice their keys. It returns the records whose keys are multiples of 3. Consume them after the producer has finished. | 334 records, first key 0, last key 999, value sum 333,666. No result depends on dead producer storage. A local scratch buffer that was not returned does not remain live indefinitely. |
| W5 | Capacity-three least-recently-used cache receives keys `A,B,C,A,D,B`; a miss loads the key's ASCII value. Repeat the pattern from an empty cache. | First pass has 5 misses and 1 hit, sum of all six returned values 397, final most-recent-first keys `B,D,A`. Occupancy never exceeds 3. A repeated fixed-size request stream reaches bounded steady-state memory. |
| W6 | Process three records using a resource that counts opens/closes. Inject a write failure on record 2, release that attempt's resources, then retry all records into a fresh output. Also inject failure before the second acquisition completes. | The successful output contains records 1, 2, 3 exactly once. Every successful acquisition has exactly one release. Failed acquisitions are not released as if successful. Active resources return to zero on every exit; failure remains observable and retry succeeds. |
| W7 | Worker pool handles jobs 0 through 99, each returning its square. Then test shutdown with one active job and queued jobs using deterministic scheduling barriers. | Successful run produces 100 unique results with sum 328,350. On shutdown every accepted job has exactly one terminal outcome, completed or cancelled. No job continues after shutdown returns, no queued payload leaks, and blocked waiters wake. |
| W8 | Read source bytes `alpha\nbeta\nalpha\n`. Retain the second field past completion of the parsing function and count all words. Test invalid UTF-8 separately under the eventual encoding contract. | Retained field is `beta`; counts are `alpha=2`, `beta=1`. The retained data remains valid. The encoding case must have a specified diagnostic or byte-preserving result before execution is graded; this draft does not settle source/text encoding. |
| W9 | Tensor-like numeric storage holds `[1,2,3,4]`. Read the middle two elements through a logical view, then update the underlying second element to 20 and read the view again. Separately compute `y=sum(x*x)` for `x=[2,3]`, retain the forward state, mutate the current application input, then request gradients of the recorded forward computation. | View reads `[2,3]`, then `[20,3]` when shared-view behavior is requested. Forward value is 13 and its recorded-input gradient is `[4,6]`. A candidate may reject unsupported mutation, but must not silently return a gradient for a different forward computation. Record the rejection and the required rewrite. |
| W10 | Save state containing parameters `[1,2]`, optimizer step 7 and RNG state 42. Load it, and inject truncation at each field boundary plus failure during the data phase. | Valid round trip preserves every field exactly. Failed load leaves the prior usable state unchanged or explicitly invalidates it so execution cannot consume partial state. Never report success after a partial load. The choice between rollback and explicit invalidation remains a decision. |

W9 is a small correctness workload, not classifier or decoder qualification.
Both full training recipes still need independently specified data provenance,
seeds, quality targets, tolerances, optimizer state and checkpoint behavior.
W10 specifies state integrity without approving a checkpoint format.

## Proposed measurement procedure

1. Freeze workload requirements, input generators, output oracles and candidate
   acceptance rules before implementation. An independent reviewer derives
   expected results from these specifications. Do not copy expectations from a
   candidate's diagnostics.
2. Name and record the Linux x86-64 machine, CPU, RAM, kernel, power policy,
   toolchains, flags, allocator and numeric-library versions. Pin versions and
   record source revision plus working-tree patch. The machine is not selected
   by this document.
3. Have independent authors implement C or Zig baselines from the specifications,
   without using candidate implementations as templates. Match observable
   behavior, including identity, bounds/failure handling and numeric strictness.
   Review baseline competitiveness. For cache, tasks and training, use two
   independently authored baselines and record both results.
4. Freeze the selected budgets before any performance baseline runs. Preserve
   exploratory runs, but do not select budgets after seeing their results.
5. Separate compilation, warmup and measurement. Propose 5 warmup runs and 30
   measured fresh-process runs per workload/profile, alternating baseline and
   candidate order. Record all samples, median and p95. Keep checksums outside
   timed loops. Explain workloads too short for stable timing and scale their
   input before the measurement series.
6. Measure wall time, peak RSS, peak live allocated bytes, allocation count,
   copied bytes, release time, compiler wall time, compiler peak RSS and emitted
   code size. Record proof failures and degraded analysis. Instrumented runs
   measure counts; separate uninstrumented runs measure time.
7. Run native Debug and ReleaseFast correctness checks. Run allocator/sanitizer
   checks separately and state coverage limits. Compile-only rejections and hand
   traces do not count as native execution. Verify inferred releases and generated
   cleanup at Python recursion limit 100 without introducing recursive analyses.
8. For bounded request/cache/resource workloads compare N=10,000 with
   10N=100,000 iterations using fixed per-iteration input size and bounded state.
   Report both RSS and live allocated bytes so allocator caching cannot conceal
   retained live values. Test cleanup after failures as well as successful exits.
9. Hand-trace a complete classifier and decoder training step before selecting
   copying or reuse. Include saved values, updates, views, shared parameters,
   optimizer state, failure cleanup and checkpoint peaks. Native workload
   qualification follows implementation and approved thresholds.

## Proposed budgets, not approved

These numbers make the proposed experiment falsifiable. They are starting
proposals, not measurements or claims that the requirements are achievable.
Ratios compare equivalent work against the independently reviewed baseline.

| Measure | Proposed budget |
| --- | --- |
| W1-W7 median execution time | At most 1.25 times baseline; p95 at most 1.50 times baseline. |
| W8 text processing | Median at most 1.50 times baseline; peak live allocated bytes at most 2.0 times baseline. The looser allowance needs explicit approval. |
| W1-W7 peak live allocated bytes | At most 1.25 times baseline, allowing an additive 1 MiB floor for small cases. |
| W1-W8 allocation count | At most 1.5 times baseline plus 16 allocations per process. Report counts even when the baseline performs zero allocations. |
| W5/W6 steady-state retention | Peak live bytes at 10N no greater than peak at N plus 1 MiB; active resources exactly zero after each completed attempt. Report RSS growth separately, with a proposed maximum increase of 8 MiB. |
| W9 reuse on a proven unique, fixed-size repeated update | Zero additional payload allocations after warmup. Always report copied bytes; no claim of eliminated copying without measured byte counts. |
| W10 same-shape load peak | At most 1.30 times the equivalent baseline's peak live bytes plus 1 MiB. Shape-changing load needs a separate budget. |
| Prototype analysis cost | On a frozen 10,000-statement corpus, at most 2.0 times compiler baseline time and peak RSS. On 100,000 statements, time and peak RSS each at most 15 times the 10,000-statement result. Report absolute values and recursion-limit-100 behavior. |
| Simplicity | Report every memory-caused rejection and rewrite. Proposed target is zero memory-specific annotations or rewrites for W1-W8 and zero silent semantic changes for any case. A miss is a requirement conflict, not permission to recategorize the program. |

Correctness, data integrity and cleanup have no tolerated failures. An unsafe
acceptance or incorrect native result rejects that candidate implementation.
Exceeding a proposed performance or simplicity budget, once approved, blocks that
candidate's qualification for the affected workload. Record the miss, investigate
it, and present a design change or explicit requirement decision. Do not loosen
the budget retrospectively, omit the workload, or add runtime mechanisms silently.

The small tensor budget does not set classifier/decoder quality or throughput
thresholds. Those remain unmeasured and unapproved. No current result demonstrates
the complete combination of Python-like simplicity, no tracing or counting,
and C-like performance and memory use across this corpus.

## Prerequisites and next packet

Stable declaration/storage identities, typed control flow, explicit evaluation
order, call-effect summaries and specialization evidence precede production
release placement or copy removal. Memory-plan M29 requires adversarial checks
for branch joins, loop back edges and call effects. A prototype must remain
isolated until those prerequisites and the relevant contract are approved.

The eventual decision packet must show current behavior, candidate behavior,
runnable examples, measured results, rejected alternatives, compatibility impact
and acceptance tests. Its unresolved decisions include alias/copy semantics,
permitted runtime machinery, recovery, simplicity, budgets and migration order.
Add replacement facilities before removing existing forms, subject to approval.
