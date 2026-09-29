# V1 delivery roadmap

The delivery target is core V1: a stable Python compiler, consistent numerics,
automatic memory, errors and collections, useful libraries and installed tools.
Zig handles generated programs, runtime support, native integration, builds and
linking. Linux x86-64 is the first qualification target. V2 aims to implement the
compiler in A7 and establish bootstrap parity before replacing Python.

The user approved this roadmap on 2026-09-20. Decisions L36-L46 in the
[ledger](decisions.md) supersede the older full-V1 boundary. AI and concurrency
remain design constraints and later release tracks. GPU execution requires a
demonstrated Zig-based integration path. No additional platform is qualified.

Static analysis is preferred. Automatic runtime memory help and release-safe
runtime checks are permitted. Growable lists share identity on assignment;
independent copies are explicit. No memory mechanism has been selected. Every
required workload must meet a 1.10-times C baseline limit for median execution
time and peak live memory, including runtime bookkeeping. Record RSS, reserved
memory, allocation/copy counts, cleanup and compiler cost separately.

Exact syntax, failure behavior and compatibility changes still need the
before/after packets specified in AGENTS.md. Preserve explicit integer widths,
wrapping integer addition/subtraction/multiplication, immutable argument bindings
and the source-recursion ban. Keep historical evidence and rejected proposals.

## Delivery sequence and exits

1. Preserve the full source baseline and record current decisions. Reconcile all
   original and later audit findings against current evidence.
2. Repair compiler correctness and finish iterative traversal. Each critical/high
   finding needs original-probe evidence or a presented blocking decision packet
   before replacing compiler architecture. Open findings still block release.
3. Introduce a typed internal program representation with stable declarations,
   source locations, evaluation order, storage identity, proofs and read/write
   effects. Compare diagnostics and native behavior before replacing old passes.
4. Prototype memory candidates against shared lists, explicit copies, cyclic
   graphs, returned data, bounded caches, retained text and failure cleanup.
   Compare static reuse, reference counting with cycle handling, tracing and
   combinations. Select only after behavior and cost gates pass. Report measured
   tradeoffs to the user if none passes; do not relax the limits silently.
5. Complete modules, generics, tagged values, errors, strings, collections and
   practical input/file/path operations. Add check/build/run/doctor/version.
   Native integration goes through Zig with checked synchronous bindings.
6. Qualify installed wheel and source distributions through actual native debug
   and release programs. Unify compiler/site/security checks, verify release
   versions and hashes, and perform browser acceptance and GLM-5.3 review.

Required measurements use fixed inputs and pinned hardware/toolchains, five
warmups and thirty measured runs by default. Each workload passes separately.
C baselines must preserve the same algorithms, outputs, identity and failure
handling. Ordinary programs require no manual allocation/free or lifetime
annotations. Long-running bounded workloads must have bounded memory use and
exactly-once resource cleanup. Compile time includes A7 and Zig as separate costs.

## AI, parallel execution and self-hosting

Track reads, writes, shared storage and native effects before inferring parallel
work. Unknown dependencies stay sequential. Keep floating-point order strict by
default. A changed reduction order requires an explicit contract. Review the
internal representation against disjoint array updates, cancellation, tensor
buffers and training's saved values without claiming those features are shipped.

Bend 2 is a source of implementation ideas, not an adopted runtime. Its current
runtime has CPU workers, Metal/CUDA paths, reference counting and last-owner
reuse. Keep target selection separate from storage ownership and physical
placement. A shared address model does not establish zero transfer cost.

V1 acceptance includes text scanning, syntax trees, symbol tables and multi-file
compiler-oriented programs. V2 starts with a compiler written in A7 and built by
the qualified Python compiler. That first compiler builds its successor. Compare
both generations across conformance programs, diagnostics, generated output and
native results. Both A7 source and compiler algorithms retain iterative traversal.

## Source baseline and evidence

HEAD is `701c67936c70ad2b0608326e23e56cc5d38c9fdb`. The repaired compiler,
site and research include tracked modifications and untracked files. HEAD alone
is not the implementation baseline. Preserve the complete working tree when
creating an isolated checkout. Do not discard or commit unrelated work.

The earlier 2,087-test, 43-example, nine-check result belongs to the
[GLM remediation snapshot](../../site/docs/audits/glm-5.3-remediation.md).
The 2,629-test result in the September 19 cleanup report belongs to another
snapshot. Neither count is a release criterion or a substitute for a fresh run.
Current source manifests and gate results belong in the
[delivery evidence](../audits/2026-09-20-v1-foundations/README.md).

## Current disposition of historical claims

This is a reconciliation of the cited findings, not closure of every historical
audit ID. A repaired trigger does not establish correctness of every related
language construct. Findings without a fresh reproducer or closure evidence stay
open in the [audit inventory](audit/open-items.md).

| Historical claim or work item | Current disposition | Evidence or remaining requirement |
| --- | --- | --- |
| `a7/` has no uncommitted changes; worktrees can start from HEAD | Superseded | Baseline status and hashes in delivery evidence |
| Release gate has 11 or 12 known failures | Superseded | Later repair reports and fresh delivery gate |
| Declaration parse errors silently discard source | Verified fixed for covered regression triggers | `test/test_language_audit_parser_fixes.py` |
| Branch, loop, call and deferred effects retain stale safety facts | Verified fixed for covered regression triggers | `test/test_audit_safety_repairs.py`; alias/lifetime analysis remains open |
| Output aliases overwrite source; failures advertise stale artifacts | Verified fixed for covered regression triggers | `test/test_pipeline_artifacts.py` |
| Imported diagnostics lose origin | Verified fixed for covered regression triggers | `test/test_pipeline_diagnostics.py` |
| Keyword and loop-capture bindings generate invalid Zig | Verified fixed for covered regression triggers | `test/test_pipeline_native.py` |
| Constant float remainder differs from runtime | Verified fixed under L33 for covered regression triggers | `test/test_constant_folding_exact.py`; native repair gate |
| Deep programs pass at recursion limit 100 | Not established | Existing pipeline tests use shallow nesting; scanner retains recursive groups |
| NOREC-0b dispatch omissions and false positives | Verified fixed for the listed mechanisms | Scanner before/after tests in delivery evidence; dynamic Python limitations remain |
| File-module design can be implemented from L25-L31 alone | Awaiting a decision packet | Ledger requires compatibility approval; [P-MOD draft](packets/P-MOD-modules.md) now records measured examples and remaining scan work |
| Typed IR and new proof/emission pipeline can replace current passes | Blocked by correctness-first exit | L23 requires critical/high closure or presented decision packets |
| Memory revision 3 is the selected contract | Awaiting a decision | Revision 3 is explicitly proposed; copies, views and failures remain disputed |
| Ordinary and advanced code have different memory promises | Awaiting a decision | M48 proposal is not approval |
| CPU AI and structured concurrency are qualified | Not implemented or qualified | Contracts, compiler foundations and workload thresholds remain prerequisites |

## Compiler foundation sequence

1. Repair NOREC-0b scanner omissions and false positives before conversions.
   Keep its limitations explicit. Remove confirmed recursion from compiler
   helpers with output-preservation and deep-input tests. Never expand an
   exception list to accommodate new recursive compiler code.
2. Reproduce each remaining critical/high finding. Give every parser-supported
   form executable behavior or a deliberate diagnostic. Complete module,
   specialization, reference and diagnostic correctness within approved scope.
3. Finish iterative parser, passes, type operations, AST handling and emission.
   Exit requires empty recursive-group, deepcopy and generated-method lists,
   plus deep full-pipeline programs at recursion limit 100.
4. After L23's exit, introduce declaration identities, typed IR, explicit
   evaluation order, CFGs and effect summaries. Run new proof and emission
   beside the current pipeline. Compare diagnostics and native behavior across
   supported programs before replacement.
5. Add one optimization at a time. Verify observable behavior before accepting
   performance measurements.

## Grouped decision packets

Each packet needs current behavior, proposed behavior, runnable examples,
compatibility impact, rejected alternatives and independently stated acceptance
tests. Record the user's disposition in the ledger before dependent changes.
A rejected packet pauses only its dependent work and requires a revised proposal.

| Packet | Contract to settle |
| --- | --- |
| Numerics | Signed overflow edges, negation, shifts, mixed types, casts, sizes, IEEE details and constant/runtime agreement |
| Modules and generics | Approved file-module direction, qualified types, visibility, cycles, specialization and identities |
| Composite values and errors | Payload matching, optionals, results, propagation, initialization, equality and recovery |
| Source and tooling | Encoding, unfinished comments, unsupported syntax, commands, diagnostics and versioning |
| Memory | Copying, aliasing, lifetime inference, resource cleanup, failure behavior and runtime checks |
| Concurrency and native calls | Task lifetime, sharing, cancellation, channels, ABI ownership and cleanup |
| CPU AI | Shapes/dtypes, differentiation, mutation, kernels, checkpoints and workload thresholds |
| Release | Profiles, pinned toolchain, compatibility, supported environment and safety claims |

## Dependency milestones

| Milestone | Implementation | Acceptance |
| --- | --- | --- |
| Usable core | Approved numerics, modules, generics, errors, commands and minimal input/files/arguments | Multi-file calculator or VM and interactive CLI through installed tooling |
| Automatic memory and collections | Approved ownership/effects, cleanup, strings, lists/maps, placement and reuse | Independent memory corpus and approved rewrite/cost budgets |
| Standard library and native boundary | Recoverable text/file/path/time/random/process operations, native descriptors and generated bindings | Actual failure recovery, ABI checks and cleanup |
| Later structured concurrency | Approved tasks, joins, cancellation, channels and sharing rules | Worker pool shutdown, race, blocking and failure scenarios |
| Later CPU AI | Reference kernels, reverse-mode autodiff, native numeric libraries, mixed precision and complete training state | Classifier and decoder training, checkpoint recovery and inference under approved thresholds |
| V1 qualification | Integrated applications, docs, packaging, compatibility and security review | All criteria pass at one identified Linux x86-64 source state |

Introduce replacement memory facilities before removing existing forms. Migrate
examples only after compatibility approval and before/after behavior checks.
Version public commands, language/library APIs, native contracts and checkpoint
formats before release.

## Memory research and qualification controls

Use the [memory reconciliation](research/memory/delivery-reconciliation.md)
before commissioning more advice. Compare static ownership and regions,
compiler-inserted copies, uniqueness-based reuse and automatic placement.
Reference counting and tracing are now eligible candidates under L37, not selected designs.
Do not infer count-free reuse from Perceus or unrestricted in-place behavior
from FP². Prototype disputed mechanisms in isolation after freezing workload
specifications and proposed budgets.

Pair unsafe programs with valid guarded controls. Exercise actual diagnostics,
artifacts, execution and recovery. Compare constants and runtime boundary values
across supported build profiles. Include modules/generics, cleanup/errors,
collections/aliasing and tasks/tensors combinations.

Before later AI qualification, freeze recipes, data provenance, seeds, tolerances,
quality targets and resource budgets. Keep HTML, Markdown, manifests, search,
examples and agent exports synchronized, with stale-export checks. Complete
responsive, keyboard, accessibility, failure-state and agent-retrieval checks.

Each substantive batch receives independent verification and a GLM-5.3 review
through OpenCode. Preserve findings and provider failures. Verify advisory
findings locally. The final gate includes clean installation, artifact provenance
and security review. Publish only claims supported by that identified source state.
Use dependency milestones rather than calendar promises.

## Current implementation evidence

The [2026-09-20 batch report](../audits/2026-09-20-core-v1/README.md) records
implemented compiler and distribution changes, reviews and open blockers. The
[next correctness batch](../audits/2026-09-20-core-v1/next-correctness-batch.md)
separates the loop-label repair, declaration identity work and fallthrough
compatibility experiment. None of these records marks the V1 milestones done.
