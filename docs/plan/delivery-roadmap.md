# V1 delivery roadmap

V1 publication requires the core language, automatic memory, useful libraries
and tools, structured concurrency, CPU AI, actual GPU execution and a self-hosted
A7 compiler with bootstrap parity. L73 in the [ledger](decisions.md) records the
2026-10-07 boundary. These are completion requirements, not shipped capabilities.
Zig handles generated programs, runtime support, native integration, builds and
linking. The Python compiler remains the bootstrap implementation until parity
supports replacement. Linux x86-64 is the first qualification target.

The original core-first ordering from 2026-09-20 remains useful. Its core-only
publication boundary is superseded. New designs need concrete proposals and
approval before dependent implementation; accepted decisions remain accepted.
Use local hardware only, keep eight logical CPUs free and use at most eight
pytest workers. Unavailable GPU support blocks publication until resolved.

GPU execution is deferred under L75. The
[Zig GPU research](../research/2026-10-07-zig-gpu-support.md) records versioned
device compilation, host APIs, backend gaps and AMD compatibility. Review those
boundaries before any later execution proposal. Continue CPU and compiler work.

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
6. Propose and obtain approval for structured concurrency, then implement task
   lifetime, cancellation, channels and failure cleanup. Qualify real concurrent
   workloads before claiming multicore support.
7. Approve tensor, differentiation, training and checkpoint contracts. Qualify
   CPU classifier and decoder workloads, then implement and qualify actual GPU
   execution on local hardware. Record numerical and recovery results.
8. Implement the compiler in A7 after compiler-building workloads qualify. Build
   its successor and compare conformance, diagnostics, output and native results
   against the Python bootstrap compiler.
9. Qualify installed wheel and source distributions through actual native debug
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
compiler-oriented programs. Self-hosting starts with a compiler written in A7 and built by
the qualified Python compiler. That first compiler builds its successor. Compare
both generations across conformance programs, diagnostics, generated output and
native results. Both A7 source and compiler algorithms retain iterative traversal.

## Full todo (consolidated 2026-10-04, one file)

Status words: DONE, PARTIAL, IN FLIGHT, QUEUED (decided, waits on another row),
PROPOSED (no decision yet), PARKED (cut or deferred). A row cites its
ledger entry. A row with no entry is a research verdict, not a decision.
The 2026-10-03 and 2026-10-04 rows were added after the user approved
this roadmap on 2026-09-20; L58 to L70 cover them.

### R. Repair waves (from the 2026-10-04 audit)

The audit reproduced regressions in the uncommitted work, safety-proof
holes, and accept-then-fail-in-Zig defects while the gate was green.
Its findings live in [the audit record](../audits/2026-10-04/findings.md) (row IDs P0-1,
P2-52, T-1 and so on) until each is closed here or in STATUS.

- R0 Records and gate. DONE 2026-10-04: ledger L58 to L70; gate
  rejects unknown arguments, bad timeouts and zero-check runs; site
  coverage check passes.
- R1 Test infrastructure. DONE 2026-10-04: parallel run (`-n auto`,
  25m20s serial to under 5 minutes), shared Zig cache (20 GB to 1.5 GB
  of temp), fast loop (`-m "not zig and not slow"`, about 10 s),
  real-pipeline and build-and-run helpers in `test/conftest.py`, the
  semantic tests and `test_codegen_zig.py` moved onto them, no
  `zig ast-check` build checks, a stage-boundary test, a size ceiling
  on the recursion ratchet. Compiler defects the move exposed are
  strict expected failures that name their finding. Deleting tests
  that verify nothing and renaming session-named files stay under R7.
- R2 Regressions in the uncommitted work (L58, L59, L60). DONE
  2026-10-04: bare `break` in a match case, same-name functions, `ref`
  lowering, native `switch` conditions, tagged-union match lowering,
  `$N` checks and emission, `read_line` reader, one `del` emitter.
- R3 Preserve and push verified checkpoints. The inherited repair batch is
  committed and pushed as `621f70c`, with compiler/test/tooling dependencies
  kept together. It matches the passing integration source manifest; later
  documentation records were checked separately. Keep subsequent repairs in
  focused commits and leave the generated research PDF local.
- R4 Soundness (L32, L63, L64, L71, L74). PARTIAL. The 2026-10-04 repairs cover loop, defer,
  shadowing and callee-identity repairs in the safety pass; SAF-3 and
  SAF-6; defined `MIN / -1`, `-MIN`, `abs(MIN)` and checked run-time
  shifts; recursion ban over function values; control flow leaving a
  `defer`; zero-initialization; `release` as ReleaseSafe plus `fast`;
  stdout flushing. The October 7 L74 repair rejects SAF-2, SAF-8 and direct
  reference alias misuse while preserving the approved controls. Later candidates
  cover loop-head field deletion, returning cleanup, compact allocation origins,
  direct global reference stores and equivalent positive one-trip increments.
  Stage13 passed its full release gate. Trials `68f` and `f521` are excluded; the
  latter rejects a confirmed valid false-branch control. The integrated literal-return
  repair preserves selected allocation identity and rejects known nil results.
  Its 1,601-file snapshot passed the full release gate: 3,772 tests passed,
  one expected failure, all 11 compiler/package checks and the outer release
  checks passed. Three native profiles verify the valid controls. Its external
  review completed 73 compile-only pairs with no scoped source blocker. Open:
  reference aliases through array elements, selected/base store synchronization
  and joined-holder nil-write invalidation; global nil-state and parameter proof
  gaps; callee effects outside bounded analysis; the
  type-based imprecision of the recursion rule, function-pointer
  locals without an initializer, a `main` exit status. Ordinary heap-scalar
  reads and printing need the proposed
  [scalar-read decision](packets/P-REF-scalar-read.md).
- R5 Language core (L61, L62, L69). PARTIAL: the October 4 repair checkpoint
  includes statement/list parsing, type registration, `nil`, mutability,
  exact constants, inline-`$T` codegen and CLI/diagnostic repairs. Per-module
  scopes, visibility, qualified values/types and report ownership were integrated
  and pushed in `c0f8cf7` under L69. The stage9 module control passes in
  all profiles. Stage10's full compiler gate failed only the obsolete `__`
  fixture: 3,689 passed, one failed and one expected failure remained; outer
  checks did not run. The fixture correction was independently reviewed. Stage12
  passed 3,305 nonnative tests. Stage13 passed 3,337 nonnative tests and targeted
  native collision, direct-import/public-wrapper and immutable-alias controls.
  Full manifest `27c4c26e` then passed 3,756 tests with one expected failure,
  all 11 compiler/package checks, site checks and dependency/security checks.
  All 1,599 frozen file hashes and modes remained unchanged. L76 core and
  diagnostic-delta external reviews found no scoped blocker.
  L76 rejects parsed import forwarding at semantic
  exit 6 while unsupported multi-dot type/literal forms retain parse exit 5.
  Local aliases retain obligations when their same-file copy chain is never
  reassigned, passed by reference or captured by another function;
  imported/global/parameter/mutable/selected/captured origins remain incomplete.
  General runtime generic dispatch remains absent. Importer-local
  alias clashes continue to reject under L28. The remaining
  strict expected failure and
  audit findings prevent declaring the language core complete.
- R6 Docs, site and records. PARTIAL: README rewritten; tensor proposals moved
  out of SPEC; STATUS, CHANGELOG, module guidance and site pages updated.
  Site coverage, build, exports and links pass. Continue reconciliation as
  compiler changes land; error catalog, examples and final release review remain.
- R7 CI, release, cleanup, file splits. QUEUED.

### A. Language chain

- A1 Generics: `$N` value parameters DONE with open repairs under R2
  (L66); minimal `where` DONE (L66); function overloading PARKED (L59
  restores the duplicate-name error).
- A2 Payload matching: dot arms parse, check, lower and run (L66);
  repairs under R2.
- A3 Option/Result: user-declared generic unions work; `io` Result
  calls are registered and emitted; checker-typed stdlib returns
  QUEUED as part of B2.
- A4 Numerics: one `--profile` flag with values `debug`, `release`
  (checked) and `fast` (L64); exact constant arithmetic (L61). The
  remaining numerics rows from research (NaN, spelling) are PROPOSED.
- A5 Memory V1: B1 arena and B2 reference-count prototypes behind a
  flag, then a comparison memo (L51, L57). QUEUED behind R4.
- A6 Concurrency: REQUIRED by L73; contracts need approval before implementation.
- A7 Tensors and actual GPU execution: REQUIRED by L73; contracts and local
  execution evidence remain open.
- A8 Cuts that are decisions: package registry (CLAUDE.md), function
  overloading for now (L59). String interpolation, SIMD intrinsics,
  device placement and lifetimes are research verdicts, PROPOSED as
  cuts. Runtime tracking stays eligible under L37.

### B. Stdlib

Architecture (L68): typed hooks in the Python registry plus `.a7`
sources shipped inside the package, with `std/` reserved. The design,
signatures and open choices are in
[the stdlib proposal](../audits/2026-10-04/stdlib-proposal.md).

- B1 `Option`/`Result` generic unions. DONE as user-declared unions.
- B2 Checker types stdlib calls from declared signatures, so
  `match io.read_line(buf)` works. IN PROGRESS in an isolated candidate. R5
  module prerequisites passed. Prelude ownership, typed I/O, mutable-buffer
  facts and literal `std/` reservation still need combined qualification.
- B3 Phase A, no heap: `io`, `option`, `result`, `slices`, `strings`,
  `ascii`, `bytes`, `math`, `conv`, `sort`, `hash`, `random`, `time`,
  `os`, `fs`, `path`, `testing`, `json`, `yaml` (L65, L68). QUEUED
  behind B2, per-module type scopes (R5) and string payload binding.
- B4 Phase B, needs the memory decision: `text`, `list`, `map`, `set`,
  `data`, `ring`. QUEUED behind A5.
- B5 Phase C: `process`, `log`, `net`. PARKED.
- B6 `or {}` and `use` sugars: PARKED until B3 ships.
- B7 TOML, regex, crypto, C++ interop: research verdicts, PROPOSED as
  cuts.

### C. Tooling

- C1 Language server, REPL, profiler, coverage, incremental builds:
  PARKED until V1 qualifies.

### D. Examples, docs, gates

- D1 Examples 049 and 050. DONE. Examples for payload matching,
  `where`, file imports and labeled breaks QUEUED under R6.
- D2 Docs sync per landing: SPEC, STATUS, CHANGELOG, `site/public`
  exports through `sync:exports`.
- D3 Full gate `./run_all_tests.sh`, then `./run_release_checks.sh`
  before any tag.
- D4 File splits (parser, type checker, Zig backend): QUEUED under R7.
- D5 B0 benchmark promotion (L56, L67): promote `mem_shared`,
  `mem_returned`, `mem_cleanup`; rewrite the other four first. QUEUED.

### E. Codegen changes of 2026-10-03

- E1 Single parentheses in conditions and chains. DONE (L66).
- E2 No IO header for programs without IO. DONE; HEAD already did
  this (L66).
- E3 `ref` parameters as `*T`. REVERTED under R2 (L60): `*T` cannot
  express `if p != nil`.
- E4 Native `switch` for match. Kept for integer, enum, bool and char
  scrutinees with constant arms only (L60); repairs under R2.

## Completion evidence

A passing aggregate gate covers only the programs it exercises. Every row below
needs evidence at the final identified source state before publication.

| Requirement | Current disposition | Required evidence |
| --- | --- | --- |
| Compiler correctness and iterative traversal | Iterative paths landed; expected failure and critical correctness findings remain | Keep scanner lists empty; close critical/high findings and run deep inputs at recursion limit 100. Dynamic external Python callbacks remain outside the traversal guarantee |
| Modules and language contracts | L69 scopes and L76 local-import rule implemented; stage13 full gate passed, broader gaps remain | Qualified names, visibility, identity, cycles, diagnostics and approved compatibility probes |
| Automatic memory and collections | Arena/RC comparison approved; mechanism unselected | Shared identity, explicit copies, cycles, bounded retention and exactly-once cleanup; each workload meets L38 |
| Stdlib and checked native integration | L68 architecture/options approved; delivery incomplete | Installed-package examples and real I/O, parsing, allocation and native failure recovery |
| Structured concurrency | Required by L73; design unresolved | Task/channel state machines, races, cancellation, blocked-worker wakeup and shutdown cleanup |
| CPU AI | Required by L73; design and qualification incomplete | Approved classifier/decoder recipes, differentiation, training, inference and checkpoint recovery |
| Actual GPU execution | Required by L73; local execution not qualified | Named local device, real kernels, CPU agreement, transfers, synchronization and failure handling |
| Self-hosting | Required by L73; bootstrap parity not established | Python builds A7 compiler, which builds its successor; compare both generations |
| Publication | Blocked by incomplete requirements above | Frozen source, release gates, installed artifacts, browser checks, documentation and GLM security review |

Prepare decision packets for unresolved memory behavior and mechanism, module
changes beyond L69, concurrency, AI/GPU and acceptance details. Each packet
shows current/proposed behavior, runnable examples, compatibility and measurable
acceptance. Resume dependent work after approval. Do not reopen settled choices
such as shared-list identity, L38 limits or the L68 stdlib recommendations.

## Source baseline and evidence

The 2026-09-20 baseline was commit `701c67936c70ad2b0608326e23e56cc5d38c9fdb`
(HEAD on 2026-10-04 is `c8face6`). The repaired compiler,
site and research include tracked modifications and untracked files. HEAD alone
is not the implementation baseline. Preserve the complete working tree when
creating an isolated checkout. Do not discard or commit unrelated work.

The [October 7 qualification record](../audits/2026-10-07/qualification.md)
preserves the frozen baseline results and manifest hashes. Its 3,090 tests,
7 expected failures and ten other compiler/package checks apply to the resumed
baseline only. The newer integration checkpoint passed the full release gate
with 3,374 tests and one expected failure, all 51 examples in every profile,
installed packages, site checks and dependency/security checks. Its manifest
includes the latest checker, safety and alias-clash repairs. Benchmarks were
report-only, not L38 qualification.

The earlier 2,087-test, 43-example, nine-check result belongs to the
[GLM remediation snapshot](../../site/docs/audits/glm-5.3-remediation.md).
The 2,629-test result in the September 19 cleanup report belongs to another
snapshot. Neither count is a release criterion or a substitute for a fresh run.
Current source manifests and gate results are recorded in the
[October 7 qualification record](../audits/2026-10-07/qualification.md).
The [September 20 delivery evidence](../audits/2026-09-20-v1-foundations/README.md)
preserves the earlier foundation checkpoint.

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
| Deep programs pass at recursion limit 100 | Verified for identified inputs | Worklists pass the deep cases and both scanner modes are empty; frozen integration passed compiler/native checks, then secrets and skipped release checks passed after metadata recovery. Arbitrary dynamic payload callbacks remain outside the guarantee |
| NOREC-0b dispatch omissions and false positives | Verified fixed for the listed mechanisms | Scanner before/after tests in delivery evidence; dynamic Python limitations remain |
| File-module implementation requires another approval of L25-L31 | Superseded by L69 | Implement the approved scopes; [P-MOD](packets/P-MOD-modules.md) retains compatibility evidence and extra proposals that need separate disposition |
| Typed IR and new proof/emission pipeline can replace current passes | Blocked by correctness-first exit | L23 requires critical/high closure or presented decision packets |
| Memory revision 3 is the selected contract | Awaiting a decision | Revision 3 is explicitly proposed; copies, views and failures remain disputed |
| Ordinary and advanced code have different memory promises | Awaiting a decision | M48 proposal is not approval |
| CPU AI, GPU execution, concurrency and self-hosting qualify for publication | Not established | L73 requires each; contracts and workload evidence remain prerequisites |

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
| Structured concurrency | Approved tasks, joins, cancellation, channels and sharing rules | Worker pool shutdown, race, blocking and failure scenarios |
| CPU AI | Reference kernels, reverse-mode autodiff, native numeric libraries, mixed precision and complete training state | Classifier and decoder training, checkpoint recovery and inference under approved thresholds |
| Actual GPU execution | Approved device/runtime contract and local Zig integration | Native device execution, numerical agreement, transfer costs and failure recovery |
| Self-hosting | A7 compiler built by Python, then its successor built by A7 | Bootstrap parity across conformance, diagnostics, generated output and native results |
| V1 qualification | Core, memory, concurrency, CPU AI, GPU, self-hosting, docs, packaging and security review | All criteria pass at one identified Linux x86-64 source state |

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

The October 7 compile-only check accepts the three L67-ready proxy workloads
from `tmp/b-benchspec/`: shared references, returned allocations and cleanup.
Their success counter oracles are `49999995000000`, `50000005000000`, and
`9999900 100`. The compiler source matches checkpoint `621f70c`; no native
workload or mechanism benchmark ran in this check. Raw hashes and commands are
in `tmp/v1-completion-2026-10-07/memory-prototype-next/compile-ready-results.json`.
Promote those three under L67 after native correctness checks; rewrite cache,
copy, text and cyclic workloads before promotion. The current harness's host-pin
ratio and timing-only measurements do not satisfy L38's per-workload C runtime
and peak-live-memory limits. Equivalent C baselines and actual release/retention
instrumentation remain required before the arena/RC comparison can qualify.

The later copy/text/ID-cycle proxy runs passed reduced checks and retained work
in optimized disassembly. Allocation/failure controls passed 234 checks, but
integer-ID cycles and buffer scans do not establish actual reference-cycle or
retained-text behavior. The standalone foundation then passed 133 Debug checks
with LLVM/LLD and C-O0 through one allocation shim. It covers small explicit-root
shared and returned fixtures with failure cleanup. It is not full W1/W4 or
seven-workload qualification. Preserve those sources and failed linker evidence.
The later instrumented foundation passed 134 checks. Independent and GLM-5.3
reviews covered typed RC/domain lifetimes and phase accounting. Review exposed
trace-checker weaknesses; a separate strengthened checker accepts all 24
archived traces and rejects 710 count/layout mutations. The original execution
evidence and frozen sources remain unchanged. This is still a small fixture
qualification, with no measured stack maximum or performance result.

The W4 prototypes now materialize 1,000 records and return the 334 whose keys
are divisible by three. Two explicit strategies copy into an exact-sized result
or compact in place while retaining capacity for 1,000 records. An independently
authored C baseline preserves both strategies. The frozen candidate passed
138 native checks, including 24 workload cases with exact independent trace
validation. Each success checks all 334 records after producer cleanup. Requested
backing peaks are 22,368 bytes for C/arena exact copy and 17,024 for compaction;
RC adds 72 and 48 bytes respectively. These figures exclude unmeasured stack
and other runtime storage. Independent and GLM reviews found no source blocker.
Four advisory trace-checker weaknesses are rejected by the mandatory independent
checker. No timing, complete peak-memory or L38 result is qualified.

W1 now has an independent C baseline and a repaired arena/RC growth candidate.
The frozen runner checks 10,000 values, every growth-allocation failure and a
logical handle across reallocations. Controlled corruption must stop publication
and free fresh then old storage. The first native attempt stopped at a Zig
type-instantiation error before workload execution. After the reviewed alignment
type fix, a frozen retry passed 112 checks, including 42 growth cases and five
corruption comparisons. Normal requested backing peaks are 196,608 bytes for
C/arena and 196,672 for RC. This excludes unmeasured runtime storage and timing.
The initial candidate and its publish-after-detection behavior are preserved
as comparison artifacts. Competitive realloc and segmented alternatives remain open.
Maintain five warmups and thirty measured samples per workload when measurement
is authorized. Both runtime and peak-live-byte ratios, including bookkeeping,
must remain at most 1.10 against equivalent reviewed C under L38.

Pair unsafe programs with valid guarded controls. Exercise actual diagnostics,
artifacts, execution and recovery. Compare constants and runtime boundary values
across supported build profiles. Include modules/generics, cleanup/errors,
collections/aliasing and tasks/tensors combinations.

Before AI qualification, freeze recipes, data provenance, seeds, tolerances,
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
