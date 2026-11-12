# V1 delivery roadmap

The checked storage-identity adapter passes all sixteen original caller
outcomes, including repeated_site_live. Eleven importer invariants, 23 focused
tests and six readonly tests pass. New controls match 14/16 outcomes: the fresh
replacement-allocation positive still rejects in both modes. Parent verified
1,736 source pins and 1,024 standalone imported module bindings. No full sweep,
native run or integration followed these remaining failures.
[Identity adapter execution review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/scalar-contained-identity-focused/PARENT-REVIEW.md).

Callable successor10 passes 11/13 tests and 10/14 standalone outcomes. Noop,
nested live and copied-noop cases improve. Mixed targets, repeated owner contexts,
argument capture and the global writer still have failing live controls. Parent
verified 1,740 sources and 479 module bindings. Broader tests remain unrun.
[Callable successor10 review](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor10/PARENT-EXECUTION-REVIEW.md).

The checked scalar-metadata successor passes four invariants, 23 focused tests
and six readonly tests. Its caller controls remain 14/16: repeated_site_live
still rejects in both modes. All 16 complete diagnostics and exits match the
predecessor. Parent verified the 1,735-file snapshot and bound result artifacts.
The scalar filter removes the empty payload, but a later identity mismatch
still blocks the program: exact replay uses a storage identity where the loop
inventory expects an owner/field identity. Both observation packets preserve
full JSON parity. A typed identity repair is being designed. No full sweep or
integration.
[Scalar metadata execution review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/scalar-contained-focused/PARENT-REVIEW.md).

The entry-owner obligation candidate passes all 23 original focused tests and
six readonly ownership tests. Its new controls match 14/16 required outcomes,
up from 10/16 on the predecessor. The repeated-call-site live program still
rejects in both modes; all five negative fixtures retain their required sites.
Root verified the 1,734-file source and focused/standalone artifacts. The full
238-outcome sweep has not run on this candidate. No safety integration.
The direct `read(nil,false)` rejection-preservation case is awaiting the
user's disposition: complete proof of skipped use would change exit 6 to 0.
The reached true case must still reject. Keep the existing oracle until approval.
[Pending call-proof proposal](packets/P-REF-proven-skipped-call.md).
[Entry-owner execution review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/entry-owner-obligation-focused/PARENT-REVIEW.md).

The readonly composition candidate passes all eight caller checks and all six
replay-ownership tests. Its focused reference suite reports 22/23 passed; only
the valid nested distinct-owner case still rejects. The previously unsafe
readonly nil call now rejects at the required caller site. Root verified the
1,734-file source manifest and focused input, import and artifact hashes.
The full run matches all 238 required outcomes. Root verified 476 streams,
238 import reports, 7,616 module bindings and 59 emissions. Only the two
readonly nil outcomes differ from the predecessor; all other complete error
objects and exits match. No safety candidate is integrated.
[Full composition review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/readonly-composition/full238/PARENT-REVIEW.md).
[Focused composition review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/readonly-composition/PARENT-FOCUSED-REVIEW.md).

The preceding reference-publication candidate matched 236/238 full regression
outcomes: 218 inherited, 14 caller and four imported-module checks. Full error
objects and exits changed only in the four intended replacement-reference rows.
[Prior full regression review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/full-reference-publication/PARENT-REVIEW.md).

The simplified closed-root readonly adapter passes 21 focused tests. Candidate
runs at depths4/6 reject with the required single nil diagnostic and zero exact
helper replays. Plain/observed full JSON matches apart from timing. Root verified
all 1,734 source pins, import and artifact hashes. The unused discharge path is
removed; the original lifetime resolver remains. Broader readonly verification
finished with 166 passed and 27 failed, with six native tests deselected. All
27 failures have matching full outputs with the shortcut enabled and disabled.
They remain failed requirements. On the same 27 tests, scalar successor6
passes 19 and the entry-owner candidate passes six. Twenty distinct cases pass
in at least one candidate; seven fail in both. This is not a composed result.
The original baseline is still running. These results do not establish general
live/effectful scaling or a time speedup.
[Adapter execution review](../../tmp/v1-completion-2026-10-18/readonly-revision11-review/performance-candidate/closed-root-adapter-successor2/PARENT-REVIEW.md).

The proposed readonly summary shortcut fails its strict admission check at all
nine observed calls: six have incomplete owner views and three receive nil.
Keep those ownership requirements. A summary must carry guarded owner-use
obligations before it can replace replay. The existing broad readonly run has
no terminal result.
[Admission evidence](../../tmp/v1-completion-2026-10-18/readonly-revision11-review/summary-admission-observation/REPORT.md).

A fresh-guard trace confirms a safety/backend proof gap on scalar successor6.
Safety skips a body whose derived guard is zero, but owner blocking prevents
an omission certificate. Zig retains the body and rejects its unapproved field
access with exit 7; the required valid result is 0. Plain and observed full JSON
match apart from timing. Parent verified 1,738 source pins and 31 imports.
A local omission-proof design is under review; no eligibility rule changed.
[Fresh-guard diagnosis review](../../tmp/v1-completion-2026-10-18/readonly-revision11-review/fresh-guard-diagnosis/PARENT-REVIEW.md).

Callable traces locate the earliest failure in formal-type classification:
both noop and nested-writer summaries have an empty callable-parameter map.
Concrete outer targets are captured, but their owners have no usable summary.
Plain/observed full JSON matches apart from timing. A source-only correction
will use checked function-signature parameter types consistently; later callable
evaluation and capture controls remain unqualified.
[Callable diagnosis review](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor9-diagnosis/PARENT-REVIEW.md).

Callable successor9 fixes the undefined variable but passes only 7/13 focused
tests and 8/14 standalone requirements. All standalone commands exit 6; valid
writer and noop controls still reject. Parent verified 1,740 source hashes,
30 streams and 479 imported module bindings. Negative generic rejections do not
qualify captured-target checking. No broader suite or native execution followed.
[Callable first-stage review](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor9/PARENT-REVIEW.md).

Callable successor8 failed before semantic checking: 13 tests failed and all
14 standalone commands exited 8 with an undefined program variable. Both source
reviews missed that the call is inside _visit_program(self, node). The failed
snapshot is preserved. A separate one-line correction will rerun the unchanged
controls before any broader suite.
[Callable review correction](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor8/PARENT-SOURCE-REVIEW.md).

Revision13 successor6 reports 92/93 tests passed and all 10 CLI outcomes matched.
Both nullable positives now pass. Guarded/unguarded returned-nil read/write
controls and all six readonly ownership checks pass. The unknown-callable live
case remains rejected. Root verified 1,738 source files, 91 compiler input
records, 36 streams, 568 module bindings and 48 pytest emissions. The preserved
103-test inventory reports 101 passed and two failed; all 26 CLI outcomes and
complete error objects match revision11. Borrowed-scalar live acceptance is
repaired. The callee-rebinding discovery case still fails. A known noop callback
now falsely triggers an unresolved scalar-write error; correcting it requires
captured-target proof because a no-argument callback may write globals. No
safety candidate is integrated.
[Successor6 execution review](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor6/execution/PARENT-REVIEW.md).
[Broader scalar report](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor6-regression/REPORT.md).

Revision13 successor3 reports 76 passed and three failed tests. All 10 CLI
checks match. The three indexed true variants now pass, including capture before
later argument mutation. Returned-nil guarded setter and mixed copied-guard
positives still reject, as does the unknown-callable live case. Keep their
acceptance requirements. Root verified 1,736 source pins, 79 program inputs,
41 emissions and 475 loaded module bindings. No safety candidate is integrated.
[Focused execution report](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor3/REPORT.md).

Three plain/observed diagnosis pairs preserve full diagnostics and emissions.
Direct literal nil passes a guarded setter; a returned nil reference fails an
unconditional argument-nonnil check in both ordinary analysis and replay.
The setter replay itself completes. Mixed-case lifetime errors remain, so
removing those argument checks alone is not a verified repair. Preserve actual
read, write and lifetime obligations when correcting their proof ownership.
[Nullable setter diagnosis](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor3-diagnosis/REPORT.md).

A separate mixed-case trace locates the first ordinary-analysis precision loss:
the branch join drops a primitive indexed scalar cell because it has no
allocation identity. Keeping the cell alone is insufficient; its conditional
Boolean values also need guarded transport. Both plain/observed pairs match.
This is a diagnosed defect, not an integrated repair.
[Scalar join diagnosis](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor3-mixed-diagnosis/REPORT.md).

Two new Claude CLI attempts ended with exit 1 after provider retry exhaustion.
Both reported EAI_AGAIN and zero model tokens. Neither completed a review or
repaired tests. Detailed prompts, logs and terminal records are preserved.
[Claude attempt evidence](../../tmp/v1-completion-2026-10-18/claude-repair-wave/REPORT.md).

Revision10 has a confirmed unsafe acceptance: read(nil, identity(p)) passes
semantic checking and emission even though read dereferences its first argument.
The paired live-reference call also passes. Revision9 rejects the nil call,
confirming a revision10 regression. A trace shows readonly validation skipped
before replay aborts for incomplete destination coverage.

Revision11 `b1d4751f` defers readonly ownership until replay completes. The nil
call now rejects with exit 6 in both modes; the live control passes with exit 0.
The focused run reports 101 passed and two failed, with 12 native tests
deselected. All 26 standalone CLI outcomes match. The remaining failures are
borrowed-scalar destination transfer and a callee-rebinding discovery control
under proposed P-CALL. Independent review verified source and output pins.
Broader readonly verification is pending. Revision12's first scalar-write run
reports 12 passed and four failed. The original setter pair now matches, but
unguarded set(nil) is accepted on both revisions11 and12. Ordinary analysis
assumes the formal nonnil; replay abort discards its nil diagnostic, and fallback
has no scalar-write requirement. Repair call-sensitive write obligations.
The live unguarded control passes on both revisions; preserve that acceptance
and correct the draft test's unsupported rejection expectation.
Field-capture and indexed live controls still reject. Prior 103 tests and
26 CLI outcomes have not run on revision12.
No safety candidate is integrated, and no native execution was attempted.
[Readonly nil controls](../../tmp/v1-completion-2026-10-18/readonly-abort-controls/requirements.json).
[Revision11 focused evidence](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision11/REPORT.md).
[Revision12 first-stage review](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision12/execution-new/PARENT-REVIEW.md).

Revision10 `a216986b` matches all four scalar-argument snapshot outcomes,
all six original boundary outcomes and all 12 strict typed outcomes. Focused
pytest reports 93 passed and four failed. The borrowed-scalar distinct and
callee-rebinding positives still reject; two new admission tests fail because
their synthetic allocation labels are invalid. Keep their requirements while
correcting the fixtures. The inherited discovery matches 196/206; all exits and complete diagnostics
are identical to revision7. The same five loop cases still fail in both modes.
No native or
production integration is claimed for this safety candidate.
[Revision10 evidence](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision10/REPORT.md).
[Revision10 inherited evidence](../../tmp/v1-completion-2026-10-17/typed-reference-revision10-inherited/REPORT.md).

Revision10 fixes revision9's optional-marker crash and readonly test setup.
Revision9 had already repaired the global-flag and computed-constant boundaries;
its scalar snapshot still rejected before CALL-actual admission was corrected.
[Revision9 evidence](../../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision9/REPORT.md).

Revision8 matched only 2/6 original boundary outcomes. Its observer showed a
global Boolean lost before ordinary call analysis and a checked exact constant
rejected by root initialization. Revision9 repairs those bounded cases; it does
not establish general scalar-reference or lifetime correctness.
[Revision8 diagnosis](../../tmp/v1-completion-2026-10-17/typed-reference-revision8-diagnosis/REPORT.md).

The revision7 inherited inventory matches 196/206, the same as revision4.
Four unsafe loop sources remain accepted, and one valid loop source rejects,
each in both modes. Root session14254 terminated with recorder exit0; that exit
records completion, not passing requirements. Root rehashed 412 output streams
and 206 import reports. Independent review verified all 1,728 source pins. Every
exit and full diagnostic object is identical to revision4. Seven negative sources retain
duplicate diagnostics. Emitted-file hashes establish current bytes only; the
runner did not pin those files at execution time.
[Inherited terminal record](../../tmp/v1-completion-2026-10-17/typed-reference-revision7-inherited/OWNER-TERMINAL.json).
[Inherited audit](../../tmp/v1-completion-2026-10-17/typed-reference-revision7-inherited/REVIEW.md).

The separate loop candidate `7ffc1a50` passes 24 focused semantic/emission
checks and two internal invariants. All five inherited loop failures meet their
requirements in this focused run. The full inherited run matches 206/206;
full diagnostic/exit differences are limited to those five repaired cases.
Root rehashed 412 streams, 206 import reports and 49 emitted artifacts;
independent audit verified all source, input, import and artifact pins.
Six new recurrent-owner controls match only 4/12 outcomes on both baseline and
loop candidate. All four valid distinct-owner/replacement programs falsely
reject. Diagnose these failures before claiming later-condition owner coverage;
the dead controls alone do not establish it. Composition with revision7
still requires source review and tests. Both candidates remain isolated.
[Loop discovery](../../tmp/v1-completion-2026-10-18/loop-composition-discovery/REPORT.md).
[Full inherited result](../../tmp/v1-completion-2026-10-18/loop-composition-inherited/REPORT.md).
[Recurrent-owner controls](../../tmp/v1-completion-2026-10-18/loop-recurrent-owner-controls/REPORT.md).

Independent returned-boolean controls on revision7 match all four outcomes,
without an empty-if seed. Each negative receiver has two distinct reasons per mode: ordinary use and
callee replay. These are repeated sites, not identical diagnostic objects.
No native or release qualification is claimed. The earlier revision4 native
witness does not qualify these successors.
[Returned-boolean controls](../../tmp/v1-completion-2026-10-18/returned-guard-controls/REPORT.md).

The recurrent-owner observer confirms two false-rejection mechanisms: unknown
fallback adds the deleted owner to a reference saved from a distinct allocation;
backedge deaths also contaminate first-entry body analysis. A successor is being
implemented in isolation with ordered captured stores and separate first/recurrent
condition poststates. Preserve residual deaths for unsupported effects.
[Owner diagnosis](../../tmp/v1-completion-2026-10-18/loop-recurrent-owner-diagnosis/REPORT.md).

The owner-loop successor's second frozen stage passes 25 direct domain/import
invariants. It preserves dead entry owners through opaque aliases and handles
missing aggregates without inventing initialized siblings. Automatic inventory
and ordered condition/body integration remain unfinished; these tests do not
establish the 218 required program outcomes.
[Stage2 parent review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/domain-stage2/PARENT-REVIEW.md).

The global-inventory repair passes all six original owner controls in stage4.
The focused run reports 43 passed and two failed. Both remaining failures are
field-divisor positives whose acceptance was not established on the predecessor.
The new real-compiler invariant verifies checked global declaration identities.
Parent verified 1,731 source hashes/modes, seven runner/output pins, 31 imports,
15 compiler input records and seven emitted artifacts. The full semantic/emission
check now matches all 218 required outcomes and diagnostic sites. Parent checked
109 inputs, 436 streams, 218 import sidecars with 6,976 module bindings, and
53 emissions. All 206 inherited exits and complete diagnostics are unchanged.
The additional caller/capture check matches only 12/16 outcomes. A reached nil
read inside the loop passes both modes, and a valid repeated-NEW replacement
rejects both modes. Preserve both failures before composition. The captured
owner/distinct-owner pair and skipped-read controls match. Trace fallback and
compare the nil read against typed revision11 before selecting a repair.

Stage3's 38 passes and six failures remain preserved. Its empty per-program
record exposed a recorder defect; stage4 records compiler calls directly.
No native execution or production integration occurred.
[Corrected draft review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ORDERED-CORRECTION-PARENT-REVIEW.md).
[Correction 2 review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ORDERED-CORRECTION2-PARENT-REVIEW.md).
[Stage3 evidence review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ordered-stage3/PARENT-REVIEW.md).
[Stage4 evidence review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ordered-stage4/PARENT-REVIEW.md).
[Full218 parent review](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ordered-stage4-full218/PARENT-REVIEW.md).

An independent imported-global pair matches all four semantic/emission outcomes.
Two modules with identical declaration names retain distinct owners; replacing
one module with the saved-owner deletion witness rejects at receiver line 21.
These controls do not qualify general module behavior or native execution.
[Module owner controls](../../tmp/v1-completion-2026-10-18/module-owner-controls/REPORT.md).

[Caller validation results](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/caller-validation/execution/results.json).
[Domain stage evidence](../../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/domain-stage1/REPORT.md).

A separate scalar-argument pair matches 2/4 outcomes on revision8. The valid case
captures true before a later argument changes the global to false, then falsely
rejects the returned fresh reference. Revision9 preserves that scalar capture;
its ordinary replay admission rejects a reference CALL actual before using it.
Revision10 passes both sources in both modes after post-capture admission. Keep the case
required alongside the original boundaries; it does not cover callable-slot mutation.
[Scalar snapshot baseline](../../tmp/v1-completion-2026-10-18/scalar-call-snapshot-controls/REPORT.md).

A new scalar-reference store pair matches only 2/4 outcomes on revision10.
Writing true through ref bool still falsely rejects the fresh-return path;
writing false rejects the deleted alias. Both currently produce the same errors.
Implement captured referent-location writes and preserve these paired controls.
[Scalar store evidence](../../tmp/v1-completion-2026-10-18/scalar-ref-store-controls/REPORT.md).

A controlled exact-budget experiment sets retained_bytes=132. Arrays with 4, 16
and 64 elements emit 3, 15 and 63 resource errors for one initializer; all pass
with the unchanged default budget. Fix repeated reporting while preserving
separate initializer sites and unrelated errors. This does not reproduce the
reported 300,000-element default-budget case. SPEC Appendix C explicitly counts
retained AST cache entries; excluding those values would change the contract.
[Budget diagnosis](../../tmp/v1-completion-2026-10-18/exact-budget-diagnosis/REPORT.md).

The corrected reporting candidate passes 209 focused nonnative tests, with 30
native/slow tests deselected. Root verified all 1,723 source hashes/modes and
1,662 recorded import bindings. The first run's test setup failure is preserved;
the corrected assertion retains unrelated stdlib errors. The two compiler files
and regression test are now integrated after checking destination baseline hashes.
The same 209 tests also pass in the production worktree. A broader nonnative
run reports 4,653 passed and eight failures, all caused by uv cache writes denied
by the read-only filesystem before compiler execution. Site build, exports and
links pass; the full site check fails at preview listen with EPERM. Native and
release qualification remain open.
[Reporting candidate evidence](../../tmp/v1-completion-2026-10-18/exact-budget-candidate/verification/successor/verification/REPORT.md).
[Integration evidence](../../tmp/v1-completion-2026-10-18/exact-budget-candidate/integration/REPORT.md).

The frozen stack-escape probe passes semantic and emission modes despite
publishing a local reference that is read after its frame returns. A live-caller
control also passes. Emitted Zig confirms the stack address escape; no native
execution ran. The [stack-expiration proposal](packets/P-REF-stack-expiration.md)
awaits approval for proven expired-use rejection while preserving active borrows,
heap returns and cleanup before expiration. No rejection has been implemented.
[Stack-escape evidence](../../tmp/v1-completion-2026-10-18/stack-escape-reconciliation/REPORT.md).

The [borrowed-deletion proposal](packets/P-REF-deletion-origin.md) awaits a user decision.
Current source accepts stack and inline deletion in semantic and emission modes,
passing borrowed addresses to allocator.destroy. The proposed bounded rejection
preserves whole heap targets, borrowed mutation and nil behavior. Sixteen current
checks cover eight initialized controls; none ran natively. Unknown-origin
handling remains a release gap. No proposed rejection has been implemented.

The per-feature Claude audit campaign has 19 prepared scopes. The initial arrays,
references and generics runs failed with `EAI_AGAIN`. A separate arrays retry on
October18 also failed after ten provider retries, with zero token usage. No
feature audit completed; 16 packets remain unlaunched. Preserve these failures
and resume when provider access works.
[Retry evidence](../../tmp/v1-completion-2026-10-18/claude-arrays-retry/REPORT.md).

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

The user excluded cyber, secrets and dependency-vulnerability scans. Run the
permitted compiler, package and site checks directly, or skip `Secrets` in
`run_all_tests.sh`. Do not run the unchanged release wrapper, which invokes
excluded scans. Record skipped checks without claiming a full release-gate pass.

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

The first stdio gate on source `7f5fd941` exited 1: 3,932 tests passed,
one failed and one was an expected failure; 10/11 compiler/package checks
passed. The failure was the stale codegen-7 expectation for a call now rejected
at semantic stage 6. The one-line repair preserves the program and line-4
assertion; 52 focused tests passed, followed by independent and same-session
GLM review. The outer site, dependency and security checks were not reached.
The [first gate record](../audits/2026-10-07/stdio-first-gate-verification.json)
preserves that failed run. The repaired gate passed on source `e0c6235a`
with 3,933 passing tests, one expected failure and all 11 compiler/package checks.

## Goose-informed preparation

L77 records the user's October 17 research request and C-export deferral. The
[pinned study](research/goose-2026-10-17.md) covers all requested feature outcomes
and the [preparation packet](packets/P-GOOSE-direction.md) defines proposed
acceptance contracts. Forty unique upstream files were checked against the pinned
Git tree; no Goose build, test or benchmark was run. No production mechanism or
language change is approved by this preparation.

| Phase | Work to prepare | Exit before dependent implementation |
| --- | --- | --- |
| GOOSE-1 | Lifetime roots, region placement, independent ownership and failure policy | Concrete accepted/rejected A7 examples; compatibility with L42/L74; approved bounded prototype |
| GOOSE-2 | Zig data-stack candidate against existing memory candidates and equivalent C | Stable growth and cleanup evidence; full memory accounting; L38 per-workload results before selection |
| GOOSE-3 | Compact values, variable ADTs and relative-link images | Explicit indexing/mutation/format contracts; iterative validation; approved layout/API changes |
| GOOSE-4 | Fresh-result destination construction and known-callback specialization | Copy/relocation/evaluation-order rules; preserved runtime callables/constraints; measured code and compile cost |
| GOOSE-5 | Flat isolated transfer within the task/channel design | Approved ownership, queue capacity, failure and shutdown semantics; actual concurrent acceptance |
| GOOSE-6 | Cleanup-aware error propagation and any nonlocal return | Explicit Result/defer compatibility, target/callback/FFI rules and user disposition |

The phases are proposed preparation work, not completed implementation. Reuse
existing typed-IR, memory, P-CON and P-RESULT work instead of creating competing
contracts. Preserve the scalar-read and callable-evaluation-order decisions as
separate pending questions. C benchmark controls remain required even though C
export is deferred. GPU execution remains deferred under L75.

## Repository simplification

The user requested a simpler repository on 2026-10-16. Shorten the documentation
entry points and separate historical plan text from current guidance. Preserve
original evidence and resolve incoming links when moving documents. Audit
executable entry points and script dependencies before choosing code moves;
retain useful compatibility commands. Keep active qualification snapshots and
cited scratch paths stable. Follow each executable layout change through imports,
package data, CI and tests. This cleanup does not change A7 semantics or reduce
the V1 boundary.

The [documentation reorganization review](../../tmp/repo-simplification-2026-10-16/documentation-review.md)
verified the first cleanup. The plan index is now 70 lines instead of 593; its
full historical text is archived with the original anchors preserved. Both
documentation indexes retain old fragment links. All 87 relative links and
36 recorded incoming links passed. The executable audit retains `main.py` and
both distinct gate scripts. The undocumented `test.sh` shortcut is removed;
use `PYTHONPATH=. uv run pytest` directly. The example builder now imports its
four shared helpers instead of maintaining duplicate definitions. The [isolated helper review](../../tmp/repo-simplification-2026-10-16/example-helper-candidate/REVIEW.md)
verified 18 nonnative checks and nine supplementary CLI/origin commands with
`PYTHONPATH` removed. The cleanup replaces four duplicate helper definitions
with shared imports. The changed builder passed all 51 Debug examples and
three native profile tests. The first profile-test attempt failed before
collection because its runner omitted the cache directory; the corrected
profile-only continuation passed. The [helper evidence](../../tmp/repo-simplification-2026-10-16/helper-integration/REPORT.md)
preserves both runs. Compiler behavior and existing checks remain unchanged.

## Delivery sequence and exits

The executable-entry readonly check passed local qualification: 12 valid
native controls and the full release gate with 3,918 tests and one expected
failure. The first gate's test-hook failure and its two-line forwarding repair
remain in the [verification record](../audits/2026-10-07/readonly-entry-verification.json).
The selected entry uses only a complete existing summary; `--lib`, incomplete
effects and general local-selector inference stay outside this check. The later
diagnostic-only integration qualifies callee notes with their existing source
filename and preserves line/column fallback when no filename is attached.
V1 remains incomplete.

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
   and release programs. Run permitted compiler and site checks, verify release
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
The [bootstrap parity packet](packets/P-BOOTSTRAP-parity.md) proposes the exact
generation and corpus comparisons. Choose its acceptance contract before the
port; resolve Python-specific CLI compatibility before replacement. The packet
does not approve a memory mechanism or qualify any bootstrap generation.

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
  review completed 73 compile-only pairs with no scoped source blocker. The later
  readonly V3 integration passes its full release gate: 3,896 tests, one expected
  failure, all 11 compiler/package checks and the outer release checks. It repairs
  the isolated V2 borrowed-scalar false rejection and integer/Boolean environment
  collision. Six native controls and independent/GLM reviews pass within their
  recorded scopes. The [readonly record](../audits/2026-10-07/readonly-v3-verification.json)
  preserves the source identity and remaining limits. Open:
  reference aliases through array elements, selected/base store synchronization
  and joined-holder nil-write invalidation; global nil-state and parameter proof
  gaps; caller-local selectors and summaries outside the work certificate;
  callee effects outside bounded analysis; the type-based imprecision of the
  recursion rule, function-pointer
  locals without an initializer, a `main` exit status. Ordinary heap-scalar
  reads and printing need the proposed
  [scalar-read decision](packets/P-REF-scalar-read.md).
  The checked scalar-load contract was presented for explicit choice on
  October 10. On October 16 the user requested deeper research. The
  [research report](research/scalar-reference-reads-2026-10-16.md) revises the
  proposal to preserve reference comparisons and require sound parameter-load
  proofs. No behavior disposition is recorded; implementation remains pending.
  Independent compile-only probes on October 16 found a scalar-write typing
  defect: guarded `ref usize` assignment of `3`, a named exact constant or `3.0`
  rejects as immutable binding, although an equivalent typed `usize` value
  writes through. The scalar destination twins accept fitting values and reject
  overflow. The bounded contextual-fit repair was integrated on October 17 under
  L47 and the existing write-through contract. It passed 21 focused and 180 related
  nonnative tests, then six exact native outputs from candidate and typed baseline
  across three Zig modes. Each source used one default-debug A7 lowering. Combined
  qualification with the scalar-store optimization passed full pytest on frozen
  source `9d2384c4`: 5,153 passed and one known strict scalar-printing expected
  failure, with the four authorized scanner exclusions. Owner 80409 exited 0.
  This does not establish a complete release-wrapper pass. The repair selects
  no scalar-read behavior. See the
  [repair evidence](../../tmp/v1-completion-2026-10-16/ref-scalar-literal-write-review/REVISION4-REPORT.md).
  Fresh [exact slice probes](../../tmp/v1-completion-2026-10-07/exact-slice-alias-probe/REPORT.md)
  on `de578138` reject the fixed-array deleted-alias witness but still accept
  its constant-bound slice-view twin. Six before-deletion, distinct-allocation
  and fresh-replacement controls pass. These are compiler-only observations,
  with 17 commands and 1,664 unchanged source files. Repair must preserve shared
  backing-slot writes; uncertain-container policy remains unselected.
  Frozen candidate `a8d7cd60` tracks literal slice backing places and offsets.
  It passes 422 focused tests with 34 deselected, including the recursion check.
  Independent review then reproduced a false rejection: an inline struct carrying
  a view into a mutating helper leaves stale backing facts. The baseline accepts
  that valid program; `a8d7cd60` rejects it. The
  [review](../../tmp/v1-completion-2026-10-07/exact-slice-alias-review/candidate/REPORT.md)
  blocks integration and native qualification of that candidate. The frozen
  predecessor and its failures remain preserved.
  V2 `52c13fb1` moves view retirement to aggregate-expression completion and
  passes 427 focused tests with 34 deselected. Its independent review invocation
  failed with a tool report of possible cybersecurity risk, without a specific
  code finding. That review is incomplete. Native preparation remains unbound;
  no native execution or live integration has occurred.
  A separate [loop replacement witness](../../tmp/v1-completion-2026-10-07/l67-cache-loop-repro/REPORT.md)
  rejects a valid two-iteration delete/fresh-allocation loop with five
  `use_after_move` errors. Straight-line replacement and iteration-local
  allocation controls pass; the unsafe no-replacement control rejects.
  Independent review confirms the loop summary retains historical deletion
  facts as current place state. Repair definite replacement transfer while
  retaining old-allocation alias rejection, branch/exit distinctions and nil
  failure handling. No uncertain-container rule or memory mechanism is selected.
  Eight [independent controls](../../tmp/v1-completion-2026-10-07/loop-replacement-controls/REPORT.md)
  distinguish five required rejections from three valid replacement paths.
  The frozen baseline rejects all eight in semantic and compile modes.
  Three [shared-allocation controls](../../tmp/v1-completion-2026-10-07/loop-replacement-sharing-controls/REPORT.md)
  require the repair to preserve aliases between two replaced slots at loop
  exit. Reading before deletion must pass; reading after deletion and repeated
  deletion must fail. The repair remains isolated pending alias, defer and
  loop-exit review.
  Frozen loop candidate `d2f41e17` passed 351 focused tests, but
  [independent review](../../tmp/v1-completion-2026-10-07/loop-replacement-independent-review/REPORT.md)
  found five invalid stale-alias programs accepted in both semantic and compile
  modes. Dead aliases reassigned inside the loop retained unrelated entry
  identities at exit. Integration is blocked by these findings. The full pytest
  run was interrupted with exit 130 after the findings; it is not a completed
  gate. A successor must track dead current slots while preserving live aliases
  to their former allocations and the valid replacement twins.
  A [one-iteration witness without replacement](../../tmp/v1-completion-2026-10-07/loop-dead-slot-without-replacement/REPORT.md)
  also passes incorrectly on the baseline. Dead current-slot propagation must
  work when no replacement exists, without relying on an unrelated rejection.
  A [conditional replacement witness](../../tmp/v1-completion-2026-10-07/conditional-replacement-repro/REPORT.md)
  reproduces a separate false rejection without any loop. Preserve the original
  allocation on the unchanged branch and the fresh allocation on the replacement
  branch without reviving saved aliases. The valid witness and two required
  rejection controls currently all exit 6 in semantic and compile modes.
  An independent [conditional fixed-array review](../../tmp/v1-completion-2026-10-07/conditional-replacement-independent-review/REPORT.md)
  found a pre-existing incorrect acceptance on both frozen loop baseline
  `e2a777d0` and conditional candidate `e59c78fa`. The
  [exact input](../../tmp/v1-completion-2026-10-07/conditional-replacement-independent-review/inputs/array_pair_dead.a7)
  conditionally assigns `xs[1] = xs[0]`, deletes `xs[0]`, then reads the same
  allocation through `xs[1]`. Semantic and compile modes both exit 0; the required
  result is semantic exit 6. Repair this joined literal-index alias loss while
  preserving the accepted distinct-slot swap. No native execution occurred.
  These observations do not establish full alias safety.
  The isolated conditional candidate `e59c78fa` passed 4,514 permitted pytest
  cases with one existing xfail; [parent verification](../../tmp/v1-completion-2026-10-07/conditional-replacement-parent/full-pytest-verification.json)
  pins the source and streams. Its [15 native controls](../../tmp/v1-completion-2026-10-07/conditional-replacement-parent/native-verification.json)
  passed across three profiles. It remains unintegrated. The subsequent joined-slot
  candidate `88b9246b` passed 4,533 permitted pytest cases with one existing xfail;
  [recovery verification](../../tmp/v1-completion-2026-10-08/conditional-array-parent/full-verification.json)
  pins the source and streams. The original interrupted run remains recorded.
  Its [native evidence](../../tmp/v1-completion-2026-10-08/conditional-array-parent/native-verification.md)
  verifies five programs across three profiles, 15 exact outputs and eight
  compiler-only negative checks. These controls do not prove general array safety.
  This candidate is not integrated and leaves a raw nested-array initializer gap:
  constructor leaf references
  must be represented without requiring explicit leaf assignments. Preserve valid
  distinct-allocation controls when repairing this route. The
  [first-run correction](../../tmp/v1-completion-2026-10-07/conditional-array-alias-candidate/REPORT-ERRATUM.md)
  confirms that the original nested negative accepted too.
  The subsequent nested candidate `ece1d6f3` is rejected by
  [independent review](../../tmp/v1-completion-2026-10-08/nested-array-initializer-independent-review/REPORT.md):
  a dynamic-index field overwrite leaves obsolete exact-slot facts and falsely
  rejects a valid read. Repair that invalidation in a successor while preserving
  the raw-constructor rejection controls. No native qualification or integration
  is claimed for this rejected snapshot.
  Its successor `6f33478f` is held by [V2 review](../../tmp/v1-completion-2026-10-08/nested-array-v2-independent-review/REPORT.md):
  an unrelated scalar field write erases a reference-field identity and permits
  a deleted-alias read. Invalidate only fields that the unknown-index write can
  modify, including checking unrelated reference siblings.
  V3 `dd327bda` passed [bounded independent review](../../tmp/v1-completion-2026-10-08/nested-array-v3-independent-review/REPORT.md).
  Full permitted pytest passed 4,582 tests and one existing xfail;
  [parent verification](../../tmp/v1-completion-2026-10-08/nested-array-v3-parent/full-pytest-verification.json)
  pins the exact source and streams. [Native verification](../../tmp/v1-completion-2026-10-08/nested-array-v3-parent/native-independent-verification.md)
  confirms 15 exact outputs across three profiles and ten compiler-only negative
  checks. Integration and required GLM review remain pending.
  The [normal OpenCode invocation](../../tmp/v1-completion-2026-10-08/glm-nested-v3-review/run.json)
  failed before review with EROFS at its normal log path. Preserve that failure;
  the required external review is incomplete.
  Dynamic-index and loop-field incorrect acceptances remain open.
  The [singleton-index analysis](../../tmp/v1-completion-2026-10-08/dynamic-field-alias-analysis/REPORT.md)
  identifies four incorrect acceptances despite current singleton scalar facts.
  Repair exact-cell tracking for proven local indices; retain the separate
  compatibility decision for genuinely uncertain selections.
  The isolated [singleton candidate](../../tmp/v1-completion-2026-10-08/singleton-index-alias-candidate/REPORT.md)
  `e87b5861` passed 660 nonnative tests. [Independent review](../../tmp/v1-completion-2026-10-08/singleton-index-alias-independent-review/REPORT.md)
  recommends bounded full/native qualification; uncertain-index gaps remain.
  Separately, [saved-slot loop controls](../../tmp/v1-completion-2026-10-08/saved-slot-loop-analysis/REPORT.md)
  reproduce three exact alias reads that wrongly pass after deletion. Preserve
  a scalar reference copied from a known array cell across loop invalidation;
  changing that cell does not rebind the saved scalar. Retain the valid zero-trip,
  distinct-allocation, fresh-reassignment and read-before-deletion controls.
  The [saved-slot V2 candidate](../../tmp/v1-completion-2026-10-08/saved-slot-loop-v2/REPORT.md)
  passed 165 final-source tests and all 118 semantic/compile requirements.
  [Independent review](../../tmp/v1-completion-2026-10-08/saved-slot-loop-v2-independent-review/REPORT.md)
  holds it for two additional valid rejections: a shadowed false loop and mutation
  before both correlated tests. Repair both without changing their expected
  acceptance. Its inherited field-invalidation defect also requires the separate
  field repair in a combined qualified source.
  The [saved-slot V3 successor](../../tmp/v1-completion-2026-10-08/saved-slot-loop-v3/REPORT.md)
  `fadec97c` passed 704 nonnative tests and 154 compiler replay outcomes.
  Both V2 rejections are repaired, but [V3 review](../../tmp/v1-completion-2026-10-08/saved-slot-loop-v3-independent-review/REPORT.md)
  holds qualification for two further valid rejections and a semantic-only
  capture regression. Preserve the predecessor capture compile-7 distinction.
  Prepare an isolated combination, then qualify its exact source. Separate
  candidate results do not establish correctness of that combination.
  The [isolated combination](../../tmp/v1-completion-2026-10-08/reference-alias-combined/REPORT.md)
  `9b92385e` passed 737 nonnative tests and 12 interaction outcomes but remains
  held for copied-flag and false-entry-loop regressions. Read-only capture has
  a semantic regression too; its predecessor compile failure remains separate.
  Preserve this snapshot and repair a successor before full/native qualification.
  The [second combination](../../tmp/v1-completion-2026-10-08/reference-alias-combined-v2/REPORT.md)
  `ae73087c` passes 748 nonnative tests and restores the reported controls.
  Parent verification confirms all 1,690 files and the two-file delta.
  Its [independent review](../../tmp/v1-completion-2026-10-09/reference-alias-combined-v2-independent-review/REPORT.md)
  recommends bounded full/native qualification after 260 compiler commands.
  The permitted full pytest run passed 4,695 tests with one existing xfail;
  all 1,690 source files were rechecked. Native qualification passed 21 exact
  outputs across three profiles, with 176 streams and 49 artifacts verified. Preserve read-only capture's existing compile-7 boundary and keep cleanup
  work separate until both changes can be qualified together. Diagnose the
  inherited valid stable-continue rejection. The uncalled-mutator capture limit
  also remains open; passing this delta review does not close either requirement.
  The separate [cleanup diagnosis](../../tmp/v1-completion-2026-10-08/conditional-cleanup-analysis/REPORT.md)
  reproduces pre-existing complementary cleanup and guarded-alias false rejections.
  Make moved-slot and allocation checks respect the active branch, preserving
  rejection of real repeated deletion and mutation between condition tests.
  The first cleanup draft failed three existing fresh-factory controls after
  693 passes. The frozen correction `09c95046` passes 715 nonnative tests,
  including those unchanged controls. Its field-slot clearing preserves allocation
  death history. Independent review recommends a combined qualification after
  44 matching candidate outcomes. The isolated three-way combination `008e8419`
  passes 738 nonnative tests. Independent integration review recommends bounded
  next qualification after 16 matching candidate outcomes. Its permitted full
  pytest run passed 4,749 tests with one existing xfail and four secret-scan
  exclusions. Native qualification passed all 33 outputs for eleven positives
  across three profiles; four negatives remain compiler-only. Parent verification
  rechecked all 264 streams and 77 artifacts. The [stable-continue diagnosis](../../tmp/v1-completion-2026-10-09/stable-continue-analysis/REPORT.md)
  identifies an infeasible backedge after a proven first-iteration break.
  Repair reachability before projecting repeat deletions, preserving actual
  repeat, mutation, labeled transfer and defer controls.
  Isolated candidate `91579223` adds statement-local scalar transfer and passes
  738 nonnative tests with 17 deselections. Its final replay matches 64 outcomes;
  independent review recommends bounded full/native qualification. Preserve the
  unresolved two-trip requirement. Full pytest qualification passed 4,781 tests
  with one existing xfail and four secret-scan exclusions on this exact source.
  Parent verification rechecked all 1,693 source files. Native qualification
  passed 39 exact outputs across three profiles and twelve negative mode checks;
  all 316 streams and 91 artifacts were verified. Remaining compiler/package
  checks follow the [prepared plan](../../tmp/v1-completion-2026-10-09/stable-continue-remaining-gates/PLAN.md).
  The [acceptance-boundary review](../../tmp/v1-completion-2026-10-09/loop-proof-acceptance-boundary/REPORT.md)
  keeps both precision requirements open. Preserve the uncalled-mutator fixture's
  semantic-0 and compile-7 expectations separately from its observed 6/6 exits.
  The [two-trip trace](../../tmp/v1-completion-2026-10-09/two-trip-proof-analysis/REPORT.md)
  confirms the valid loop still rejects in both modes. Its real backedge carries
  a deleted allocation; merging the counter with first entry invents a repeated
  deletion. Investigate correlated re-entry checking while preserving exit
  history, actual repeated deletion and unsafe prefix operations.
  The [captured-call diagnosis](../../tmp/v1-completion-2026-10-09/uncalled-capture-proof-analysis/REPORT.md)
  traces another precision limit to declaration-wide capture exclusion. The
  isolated call-sensitive candidate `5078a1b5` matches 48 replay outcomes but
  fails one existing deferred-capture nil-argument check: expected exit 6,
  observed exit 7. [Parent verification](../../tmp/v1-completion-2026-10-09/uncalled-capture-proof-candidate/parent-failure-verification.json)
  preserves 761 passes and that failure. Separate literal argument eligibility
  from relational lifetime facts, preserving the existing rejection.
  The [successor](../../tmp/v1-completion-2026-10-09/uncalled-capture-proof-candidate/revision3/REPORT.md)
  `e4497b17` preserves that rejection and matches all 54 compiler outcomes.
  Its corrected test file passes 27 tests. The same compiler passed 764 broader
  tests on revision2, which failed one incorrect new diagnostic assertion.
  Keep those results separate; no clean full-suite result is claimed.
  The [two-trip candidate](../../tmp/v1-completion-2026-10-09/two-trip-proof-candidate/REPORT.md)
  `342d150b` passes 757 nonnative tests and 38 compiler outcomes. Both independent
  reviews support combined qualification. Preserve the valid unknown-prefix
  loop and saved-noop callable false rejections as open requirements. Qualify
  the exact combined source; neither repair is integrated.
  Combined `9ada6e28` passed 4,827 full pytest tests with one existing xfail and
  the four secret-scan exclusions. Its separate native qualification passed
  42 exact outputs across three profiles and sixteen negative compiler checks.
  These results preserve the known precision limits and do not establish V1
  or integration readiness.
  [Terminal-prefix diagnosis](../../tmp/v1-completion-2026-10-09/terminal-prefix-branch-analysis/REPORT.md)
  confirms that the unknown-branch witness retains its exact counter but stops
  before inspecting both safe branches. Isolated successor `89578873` passes
  802 targeted tests and independent review. A further valid case joins
  different counters correlated with a Boolean. The isolated
  [guarded-value repair](../../tmp/v1-completion-2026-10-09/correlated-counter-candidate/REPORT.md)
  `be024793` passes 857 targeted tests and 46 required compiler outcomes.
  Independent implementation review passed 22 required compiler outcomes.
  Complete combined qualification with the call repair before integration.
  [Saved-callable diagnosis](../../tmp/v1-completion-2026-10-09/saved-callable-copy-analysis/REPORT.md)
  confirms that later reassignment of a source slot loses an earlier saved noop
  identity. Isolated successor `7c6fa0af` passes 825 targeted tests and independent
  review. Combined snapshot `2a699e77` still rejects two valid saved-noop call
  interactions and the correlated-counter case in both compiler modes. The
  counter successor leaves both call interactions open. Implement the reviewed
  inaccessible-local retention rule before broad qualification; preserve their
  acceptance requirements, saved-mutator rejection and callee-before-argument ordering.
  Isolated call successor `0374758a` passes nineteen focused tests and 38 recorded
  compiler outcomes. Its broader regression selection passes 876 tests with
  17 deselections. Independent replay supports bounded qualification. Full
  pytest passed 4,919 tests with one existing xfail. Native qualification passed
  54 exact runtime outputs across three profiles and 36 rejection checks on
  that exact source. The xfail `heap_scalar_write_through` still
  requires a scalar reference read/output contract and qualification; it is
  not a passing acceptance case. Preserve acceptance requirements for the
  runtime-valid borrowed-but-unmodified and stdlib-print counter controls;
  their conservative rejection remains an open proof gap.
  The isolated stdlib successor `e663c137` retains inaccessible local counter
  facts after argument effects. Its 24 focused and 881 broader tests pass.
  Independent review verified 36 commands without mismatches and supports
  bounded successor qualification. Combined qualification remains required. The
  [borrowed-counter design review](../../tmp/v1-completion-2026-10-10/borrowed-counter-design-review/REPORT.md)
  supports a separate finite scalar write/escape analysis. Implement and review
  that proof without changing the existing Boolean/lifetime borrowing exclusions.
  Empty field-write summaries do not establish scalar readonly behavior.
  Initial borrowed candidate `d389a609` has thirteen focused passes and eleven
  failures. Tracing identifies fresh allocations incorrectly inheriting scalar
  origins and causing counter exclusion. Preserve that failed snapshot while
  correcting the transfer in a successor. Compound-write and nullable-loop
  fixtures also need documented prerequisite corrections; they are not lifetime
  rejection evidence.
  [Borrowed revision 2](../../tmp/v1-completion-2026-10-10/borrowed-counter-candidate/revision2/REPORT.md)
  `47ec7768` corrects fresh-allocation origins. Its focused run has 23 passes
  and one failure; paired replay matches 46 of 50 required outcomes. The
  entry-guarded readonly loop and alias-overwrite control still require 0/0
  but return 6/6. Repair the loop's lost reference nil fact and distinguish
  overwritten alias versions without weakening either acceptance requirement.
  [Nil-proof design review](../../tmp/v1-completion-2026-10-10/borrowed-counter-implementation-review/readonly-loop-design-review.md)
  requires transitive global-alias effects as well as parameter effects. A
  no-argument callee can delete a global allocation that aliases a parameter.
  Empty scalar parameter summaries alone cannot justify retaining non-nil facts.
  Revision 3 `938703fd` preserved that veto but failed six focused tests:
  thirty passed, including the seven new rejection controls. The declaration
  type lookup returned no type, so the new nil proof never became eligible.
  The [return-escape review](../../tmp/v1-completion-2026-10-10/borrowed-counter-implementation-review/return-escape-type-review.md)
  found the same missing-type assumption in return effects. Correct both in a
  preserved successor; keep the failed source and all acceptance requirements.
  Revision 4 `63da2f36` corrects those lookups and passes 38 focused tests,
  including the original entry-guarded readonly loop. Its 172-command paired
  replay matches 76 of 84 required candidate outcomes. Independent replay
  matches 40 of 46 candidate outcomes across 96 commands. Its local-alias,
  global-rebind and returned-readonly controls remain rejected. The separate
  author replay also retains the alias-overwrite failure. The 31-file nonnative regression selection passed 914
  tests with seventeen deselections. Conservative alias overwrite,
  local reference alias, global rebind and returned-reference precision gaps
  remain required acceptance cases.
  The readonly returned-reference case is a precision regression from revision
  3. Keep its 0/0 requirement. The
  [return-origin proposal](../../tmp/v1-completion-2026-10-10/borrowed-alias-version-design/return-origin-addendum.md)
  separates returned aliases from references retained elsewhere, preserving
  writes through the returned alias. Revision 4 remains unintegrated.
  A separate [alias-version design](../../tmp/v1-completion-2026-10-10/borrowed-alias-version-design/REPORT.md)
  proposes per-program-point alias values and argument snapshots to repair
  the overwritten-alias requirement. Its graph implementation is isolated in
  revision `addbf488`. Independent source review cleared bounded testing and
  all 61 focused tests passed, including both original gaps, valid LIFO cleanup
  and nested readonly return. Its 248-command paired replay matches all 122
  candidate outcomes. The broader selection passed 937 tests with seventeen
  deselections; independent replay matched all 74 candidate outcomes. Combined
  graph/stdlib candidate `8adf421e` passed source review, 87 focused tests and
  all 140 paired-replay outcomes and 944 broader tests with seventeen
  deselections. Independent replay matches all 94 candidate outcomes; map traces
  confirm exact-value and guarded-case retention without restoring invalidated
  facts. Combined full pytest passed 4,987 tests with the one existing strict
  scalar-read xfail still unmet. Independent result review passed. Native
  qualification then stopped before builds: initialized `returned_readonly`
  rejects at its loop deletion instead of passing. Preserve this valid input
  and repair the rejection before qualifying a successor. All 52 unsafe-site
  checks passed; no native output was obtained. Neither
  successor is integrated.
  Follow-up diagnosis reproduces four initialized valid failures caused by
  primitive stores selecting whole-function fallback. Isolated repair
  `9df00ac7` models RHS, receiver selection, index evaluation and write effects.
  Source review allowed prerequisites: all nine initialized programs now pass
  both modes, including the four original valid failures. A distinct local
  stack-array store still falsely rejects because its write invalidates an
  unrelated counter. Three negative fixtures have unrelated prerequisite errors.
  Repair storage-origin precision and preserve the valid requirements before
  broader or native qualification. Twenty of twenty-eight outcomes match.
  Independent refined controls reproduce three clean valid failures. Preserve
  their distinct storage and effectful expressions while separating value
  origins from addressed locations, including implicit reference arguments.
  Baseline projected-reference controls pass checking while omitting required
  formal write effects. Verify final summaries for formal, global, captured
  and slice projections as well as accepted/rejected compiler outcomes.
  Paired testing also reproduces a successor regression for a separate local
  `i32` passed by reference: `9df00ac7` accepts, `82cfb51d` rejects. Preserve
  owned provenance for untracked primitive locals before broader qualification.
  The paired enum-local probe reproduces the same precision regression on
  `c1120acd`. Preserve its required 0/0. Capture expectations follow the current
  documented 0/7 contract while retaining the required semantic write effects.
  Revision 5, `b37fc6f2`, passes all 54 bounded compiler outcomes, 13 summary
  tests and 127 focused tests, with the summary tests included in that focused
  count. [Qualification evidence](../../tmp/v1-completion-2026-10-10/primitive-place-location-candidate/revision5/qualification/REPORT.md).
  Three independent valid controls remain open: replacing a local string,
  slice or function-value slot loses an unrelated counter proof. Each passes
  on `9df00ac7` and rejects on `c1120acd`. Preserve slot identity without
  discarding reachable-storage effects or callback effects. For a reference
  to a handle slot, later arguments may replace its contents before the call;
  an earlier backing snapshot cannot stand in for the callee's observed value.
  Qualify these controls before broader or native gates. Independent occurrence
  traces now verify exact local return/escape tokens, deferred return snapshots
  and the guarded receiver/index ordering case. The original index probe still
  fails bounds checking. No location candidate is integrated.
  [Handle prerequisites](../../tmp/v1-completion-2026-10-10/primitive-location-handle-controls/REPORT.md)
  confirm the three failures on `b37fc6f2`, qualify a complete same-backed
  slice/element caller at 0/0, and retain its helper's required formal write.
  The callback-reset control rejects only at the intended deletion. Preserve
  its separately observed invocation write when making replacement precise.
  Additional forwarded, retained and aggregate-callback controls reject at
  their intended lifetime sites. Keep the saved-callee ordering proposal
  separate: the analysis captures callees before arguments, while the public
  specification orders only the arguments. Observe native behavior and obtain
  a disposition before implementing a new public ordering guarantee.
  Revision 7, `da0bf9a5`, passes 74 compiler outcomes for 37 unique inputs,
  including the three original handle replacements. The intended 38-case
  inventory contained a duplicated CLI name, so later stages stopped. Remove
  that duplicate, enforce unique names before constructing requirements, and
  qualify the corrected inventory. Revision 8, `75ffeaec`, removes only the
  duplicate. Independent review verified the 37-input correspondence with
  revision 7's recorded outcomes. With the summary-result prerequisite fixed,
  revision 8 passed 18 summary tests and 142 focused tests. The focused count
  includes the 18 summaries and 37 CLI cases. Combine the isolated repairs and
  complete broader and native qualification; these passes establish no native
  acceptance.
  The separate inferred mutable-function probe fails native build because its
  declaration lacks a function-pointer type. Its explicitly typed counterpart
  runs in all three profiles with `argument`, `old`, `new`. Declaration repair
  `f8485bac` now runs the original inferred input in all three profiles,
  passes 15 native regression cases and passes 62 nonnative generic checks.
  Parent verification and independent evidence review passed. Combine and
  qualify the repairs before integration. The reviewed
  [ordering contract](packets/P-CALL-evaluation-order.md) awaits approval;
  observed backend output alone does not adopt the proposed rule.
  Combined source `e78ffbd7` freezes 1,706 files and passed parent and
  independent source review. Qualify this exact composition through the broad
  regression selection, full pytest and native execution. The broad selection
  now passes 999 tests with 32 native/slow deselections and no skips or expected
  failures. The full eight-worker gate finished with 5,056 passed, one failed
  and the existing heap-scalar expected failure in 782.73 seconds.
  Its sole failure is the packaged-source alias emission assertion.
  Test-only successor `3ba27b74` retains the compiler, updates the expected
  typed canonical binding and adds three imported-alias native checks.
  Independent source review found no blocker. All 19 packaged-module tests
  passed in 26.91 seconds, including the wrong-argument rejection and three
  native outputs matching `7\n`. Full pytest passed on this successor with
  5,060 tests and the existing heap-scalar expected failure in 783.12 seconds.
  Parent review verified the actual source, raw output and worker records.
  The original native packet passed all 81 exact outputs and 52 rejection-site
  checks. All 106 compiler prechecks preceded native builds. Parent and
  independent review verified the raw streams, artifacts and source hashes.
  Preserve the failed predecessor and complete the separate handle packet
  before the remaining compiler/package checks.
  Three separate observable handle controls pass both compiler modes. Verify
  their nine native outputs after the full gate; keep them separate from the
  original 27 positive programs. The first native run passed the Debug string
  control and failed to build the Debug slice control. Zig infers an array
  pointer for its unannotated local, which cannot be passed by reference as a
  slice. Preserve the original witness and failure, qualify the isolated
  checked-slice declaration repair, then rerun the dependent gates on its exact
  source. At that checkpoint, eight handle outputs remained unverified.
  Slice repair `1ec7b7cf` passed 39 native cases, 177 compatibility cases and
  the original slice witness in all three profiles. The native cases include
  three instrumented Zig representation checks. The baseline fails the intended
  slice-type assertion; the successor passes it. Combined source `04c5e959`
  includes this repair, the L53 harness and the newer live test overlays.
  Full pytest completed with 5,117 passed and the existing heap-scalar expected
  failure. Recovered raw output, child and worker exits establish completion;
  the old tool handle was unavailable. All 999 historical broad test identities
  passed in this combined run. The [combined native audit](../../tmp/v1-completion-2026-10-11/combined-slice-harness-native-independent-review/REPORT.md)
  now verifies the original 81 outputs and all nine handle outputs, with 52
  required rejection sites. The [remaining gate audit](../../tmp/v1-completion-2026-10-16/combined-remaining-gates-review/REPORT.md)
  verified 11 passing checks and a strict benchmark failure for three missing
  host pins. Owner session 64982 exited 1. Preserve the known heap-scalar
  failure and missing benchmark pins.
  The reviewed [seven-file documentation patch](../../tmp/v1-completion-2026-10-16/combined-integration-docs-complete/REPORT.md)
  adds bounded safety tracking and inferred function bindings to the earlier
  slice/benchmark draft. All 30 source transfers and seven documentation files
  are integrated after matching every destination to its saved base.
  Exports are synchronized. Site lint, type checking, coverage and 11 publication
  tests passed. The preview test failed because the environment denied `listen`
  with `EPERM`. Separate build, export and link checks passed; the full site
  check remains failed. Recheck preview serving in an environment that permits
  local listening sockets before claiming site qualification.
  The original 53-input
  replay produced all 106 required exit codes and contained diagnostic sites.
  Its first verifier incorrectly required exact expression spans and exited 1;
  preserve that failure and the offline reconciliation. All 52 negative
  diagnostic lists match the earlier run. Keep the original 27 native positive
  outputs and 26 negative diagnostic contracts. Prior separate passes do not
  qualify the combination.
  [Repair source and limits](../../tmp/v1-completion-2026-10-10/primitive-place-candidate/REPORT.md).
  The reviewed [reference-slot design](../../tmp/v1-completion-2026-10-10/reference-slot-retention-design/REPORT.md)
  separates binding changes from referent effects to address local aliases
  and global rebinding first. Keep deletion, capture, unknown-call and selected
  allocation checks while qualifying that isolated successor. Candidate
  `31135c8e` freezes 1,702 files; parent verification confirms that only the
  reference-effect summary and a new thirteen-case test file differ from
  revision 4. Independent source review cleared bounded testing. All 51 focused
  tests passed, including the two formerly rejected valid cases. The paired
  replay records 216 commands and matches 102 of 106 candidate outcomes.
  Parent verification checked 432 streams and 39 emitted, unexecuted Zig
  artifacts. The 32-file nonnative regression selection passed 927 tests with
  seventeen deselections. Independent replay executed 116 commands and matched
  54 of 56 candidate outcomes; all sixty negative diagnostic-site checks passed.
  Its remaining failure is the readonly returned-reference case. The author's
  separate alias-overwrite requirement also remains open. Six ref-to-ref prerequisite
  probes failed type checking and supply no safety-pass evidence.
  Eight graph controls were checked on 3113 in both modes. All reached the
  intended safety diagnostic without an earlier prerequisite failure. Six
  unsafe controls reject as required. The valid LIFO rebind-before-reset and
  nested readonly-return controls remain required 0/0 but observed 6/6.
  These supplement the original alias-overwrite and returned-readonly cases.
  Separately, three accepted initialized inputs on 3113 passed nine native
  output checks across Debug, ReleaseSafe and ReleaseFast. The returned-readonly
  and alias-overwrite native inputs remain unexecuted because their 3113
  prechecks failed. These results do not qualify the graph successor.
  Keep existing immutable callable proofs for read-only captures and values
  passed to functions. Deferred calls resolve their callee when cleanup executes.
  Stable `91579223` passed all nine permitted remaining compiler/package checks.
  Its performance gate failed for three missing timing/hash baselines. The
  separate site check failed when preview socket creation returned `EPERM`.
  A subsequent static run passed build, export and link checks, with 23 pages,
  1,506 local resources and 183 search targets. The preview and performance
  failures remain open.
  The [main return-code proposal](packets/P-CLI-main-exit.md) defines a possible
  parameterless u8 entry alongside void main, with ordinary cleanup before
  process exit. Fresh probes confirm current typed-main rejection in executable
  and library modes. The reviewed proposal has been presented to the user;
  no entry contract is adopted or implemented before that decision.
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
  The historical P2-38 bounds failure on `158a8423` is preserved in the
  [prerequisite record](../audits/2026-10-07/stdlib-source-loader-prerequisites.json).
  Rejected candidate `84c6c20c` admitted a reachable nil index through a
  function-returned condition; its valid native controls did not cover that
  defect. Integrated successor `b26d502a` rejects unresolved indexed requirements
  at call sites in normal and library modes. Its frozen source passed 4,194 tests
  with one expected failure and 12 valid native controls. Four original direct
  checks and five recovery checks cover the nine-command compiler/package set.
  The original quota failure and recovery records remain separate.
  A later docstring-only overlay leaves the remaining Python AST unchanged.
  Diagnostic source `95dfa299` qualifies secondary callee notes without changing
  primary caller locations or proof decisions; 630 focused nonnative tests and
  24 independent compile observations cover that overlay, without a new native
  or full-suite claim. False-returning function guards with nil, symbolic nil
  wrappers, effectful indices and other documented ref-index limits remain
  incomplete. General P2-38 support and V1 completion remain open. Site build,
  exports and links pass; the preview test fails because socket listening is
  denied with `EPERM`.

  October 8 compile-only probes confirm integer match-range comparison errors
  above `2^53`. A singleton range at `9007199254740992` wrongly rejects the
  adjacent literal `9007199254740993`; a singleton range at `9007199254740993`
  wrongly accepts that same literal in another case. Both case orders fail.
  Nine other controls pass, including the selected `f32` fitting controls.
  L47 already approves fitting patterns before overlap checks. The isolated
  repair is integrated from snapshot `0772bfa0`. Permitted pytest passed
  4,216 tests with one existing expected failure; four scanner tests were
  excluded. All nine direct compiler/package checks passed, including 51 examples
  in each native profile and clean wheel/source-distribution installs. A separate
  18-call branch control passed in all three profiles. Independent review verified
  the source identities and output records. Site build, exports and links pass;
  preview testing fails on socket-listen `EPERM`. See the
  [candidate report](../../tmp/v1-completion-2026-10-07/match-pattern-candidate/REPORT.md). Sources and
  all 26 output streams are preserved in the
  [reproduction record](../../tmp/v1-completion-2026-10-07/match-pattern-reproduction/results.json)
  and its
  [supplement](../../tmp/v1-completion-2026-10-07/match-pattern-reproduction/supplement.json).

  A later ten-program compile-only probe confirms that valid generic numeric
  match patterns reject against unresolved `$T` before concrete instantiation.
  Distinct `f32`/`f64` literals and disjoint `i64` patterns are affected. Direct
  and named-constant controls behave correctly; two arithmetic-pattern attempts
  fail parsing and establish no semantic defect. The repair is integrated below.
  See the [probe report](../../tmp/v1-completion-2026-10-07/match-generic-pattern-probes/REPORT.md).

  The isolated repair `fcd32382` passes 501 selected checks, including 46 new
  cases. Independent compile controls exposed a constrained wrapper failure:
  a `$T: Float` wrapper calling another `$T: Float` function rejects with
  `constraint_violation`. Eleven paired probes establish that constraint
  forwarding already fails in the live compiler, including equivalent and
  narrower constraints on functions and struct construction. Repair both
  constraint checks under L66 while retaining rejection of broader and
  unconstrained arguments. Successor `e4e2b74b` is now integrated. Its permitted
  pytest run passed 4,281 tests with one expected failure and four scanner tests
  excluded. All nine compiler/package checks passed. Six independent programs
  and 18 integer branch/fallback calls per profile passed in Debug, ReleaseSafe
  and ReleaseFast. Site build, exports and links passed; preview testing failed
  because this environment denies the listen operation. See the [independent result](../../tmp/v1-completion-2026-10-07/generic-match-review-controls/review.json).

  The constraint repair also exposed a separate annotation-only gap:
  `Box($T: Float)` rejects `Box(i32){value: 0}` but accepts `b: Box(i32)`.
  Both the original and successor candidates reproduce this difference.
  Constructor forwarding checks do not close annotation enforcement. Track
  annotations, parameter and return types, aliases and forward declarations
  before claiming complete nominal constraint checking. See the
  [paired probe](../../tmp/v1-completion-2026-10-07/generic-match-constraint-candidate/concrete-annotation-probe/results.json).
  Twelve later compile-only controls confirm eight invalid annotation forms
  accept, including unused signatures, aliases, forward record fields and an
  imported owner. Three valid controls also accept; a forward type-set-member
  case remains an investigation. The proposed repair retains annotation
  obligations until owner constraints are registered. See the
  [annotation analysis](../../tmp/v1-completion-2026-10-07/generic-annotation-analysis/REPORT.md).
  Isolated candidate `3421237d` passes 554 selected checks and six independent
  compile controls. It also resolves record constraints after type aliases, so
  a valid forward type-set member works in construction as it does in function
  constraints. Its native control passed in Debug, ReleaseSafe and ReleaseFast.
  Permitted full pytest passed 4,315 tests with one expected failure and four
  scanner exclusions. All nine compiler/package checks passed, including
  51 examples in each artifact profile and clean package installs. The repair
  and six documentation updates are integrated; 382 core paths match the
  qualified source. Site exports, build and links pass. Preview testing still
  fails with `EPERM` on socket listening. See the
  [candidate report](../../tmp/v1-completion-2026-10-07/generic-annotation-candidate/REPORT.md).

  Accounting-only candidate `3fbb40dd` rebases approved C3–C10 enforcement
  onto the annotation repair. It preserves current math output and numeric
  spelling; C11 qualification remains separate. Permitted pytest passed 4,379
  tests with one expected failure and four scanner exclusions. Five native
  programs passed across three profiles, with 47 commands and 94 streams
  independently verified. The 17-row IEEE observers measure stored bits.
  All nine compiler/package checks passed. Six source/test changes and seven
  docs are integrated; 383 core paths match the qualified source. Site exports,
  build and links pass. The preview test still fails with `EPERM` on listening.
  See the [accounting report](../../tmp/v1-completion-2026-10-07/exact-accounting-rebase/REPORT.md).

  Boolean-guard candidate `4abb3b09` supplies reference-array guard facts for
  resolved functions whose body is one Boolean-literal return. Four direct or
  forwarded false-guard probes now accept nil; thirteen rejection controls
  retain exit 6 and five accepted controls emit identical Zig. Focused checks
  pass 122 tests; the broader nonnative selection passes 548 with 45 deselected.
  Independent review found no scoped blocker and added four compiler probes.
  Native controls pass in Debug, ReleaseSafe and ReleaseFast: false guards
  skip nil access, a true guard reads a borrowed array, and an argument counter
  proves one evaluation. Nine negative probes retain semantic exit 6 without
  artifacts. Permitted full pytest passed 4,395 tests with one expected failure
  and four scanner exclusions. Four direct checks passed in session 34047;
  its artifact and package quota failures remain preserved. Session 60311
  passed the five failed or unrun checks, completing nine logical checks.
  Four source/test files and seven docs are now integrated. Independent
  verification checked both 1,662-file trees, 26 command streams, 384 live core
  paths, eleven copies and ten backups. Site build, exports and links pass;
  the preview test still fails with `EPERM` on listening. See the
  [integration verification](../../tmp/v1-completion-2026-10-07/ref-array-boolean-guard-integration/independent-verification.json).
  Conditional and effectful helpers, deferred bodies and symbolic nil wrappers
  remain incomplete. See the
  [guard report](../../tmp/v1-completion-2026-10-07/ref-array-boolean-guard-candidate/REPORT.md).

  Follow-up probes distinguish two remaining guard gaps. A symbolic nil wrapper
  rejects before caller substitution; accepting it from known callers needs an
  explicit public/library contract. Four locally guarded forms also reject in
  both modes, including `if b { ret }; access(nil, b)`. Those forms need Boolean
  path facts within the function. Reassignment and mutation controls still reject.
  The combined local-proof and diagnostic candidate `de578138` passes 631
  selected tests with 45 deselected. Independent review verified all 1,664
  source files and the exact three-path change. The repair is now integrated.
  Native session 80219 passed the core in three profiles and eighteen negative
  cases, then failed an exact diagnostic assertion whose expected string omitted
  the existing index-requirement prefix. That failure remains preserved.
  Three corrected diagnostic retries complete 32 logical native steps; parent
  verification checked 66 streams, six artifacts and all 1,664 source files.
  Permitted full pytest passed 4,442 tests with one expected failure in session
  16066. Parent verification checked both 1,664-file trees and four streams;
  independent verification confirms those records and command scope.
  Session 95729 passed examples, debug artifacts, error stages and docs style.
  Release, fast, benchmark and package writes failed with quota errors;
  installation was skipped. The failed record and sixteen streams are preserved;
  both 1,664-file source trees remain unchanged.
  Closed Boolean-gate generated artifacts were archived and verified before
  removing 326 temporary files totaling 1,040,073,120 bytes. No source files
  were removed. Session 84011 passed all five retries. Nine logical direct
  checks are verified across the preserved original and retry records.
  Three source/test files and seven docs are integrated. Independent verification
  checked ten copies, eight backups and 388 live core paths using the parent's
  six-root-file scope. The earlier four-root-file scope counted 384 baseline
  and 386 candidate paths; both scopes include compiler, tests, scripts and
  examples. Site sync, build, exports and links pass. The preview test remains
  blocked by listen `EPERM`, with eleven tests passing and one failing. See the
  [integration verification](../../tmp/v1-completion-2026-10-07/ref-array-local-diagnostic-integration/independent-verification.json).
  Unresolved caller checks remain enforced. See the
  [wrapper diagnosis](../../tmp/v1-completion-2026-10-07/ref-array-symbolic-wrapper-analysis/REPORT.md).
  A read-only reconciliation of twenty historical U/A/D rows identifies twelve
  scoped repairs and eight decision or verification remainders. It establishes
  no new current defect. Its `de578138` source is now integrated;
  the [successor report](../../tmp/v1-completion-2026-10-07/phase2-successor-reconciliation/REPORT.md)
  preserves exact requirements and the limits of each assertion.
  A subsequent CLI Debug build reproduces the P2-75 generated-source lifetime
  defect: the saved binary refers to `a7-native-6cv2ys8i/program.zig`, deleted
  before the build command returns. Decoded line output has no A7 filename.
  The [CLI probe](../../tmp/v1-completion-2026-10-07/phase2-debug-source-lifetime/cli-probe/result.json)
  and parent verification retain six steps, twelve streams and 1,664 unchanged
  source files. The binary was not executed and debugger behavior is untested.
  No fix or design is adopted; one of the eight remainders now includes this
  reproduced defect. The historical reconciliation remains unchanged. The
  [source-retention proposal](packets/P-CLI-debug-source.md) defines build artifact
  ownership and failure cleanup; it awaits approval before implementation.
  P2-81 session 5006 failed on a reserved counter name in the depth-16 fixture.
  Six local/allocation inputs completed thirty samples each; the original
  depth-8 results remain preserved. Source analysis and profiles establish
  quadratic descendant scans within `_store_value`, not whole-compiler runtime.
  The [attribution review](../../tmp/v1-completion-2026-10-07/phase2-safety-scaling/local-attribution-review.md)
  records that boundary. All three renamed loop fixtures pass semantic checks;
  their measurement retry passed in session 72178. Nine input distributions are
  complete across the preserved attempts. The final
  [measurement report](../../tmp/v1-completion-2026-10-07/phase2-safety-scaling/MEASUREMENTS.md)
  reconciles 270 measured samples and verifies 726 streams and 20 profile
  artifacts. Allocation identity comparisons and nested loop summaries also
  contribute growing work; no whole-compiler complexity class is established.
  P2-81 remains open. The [October 16 reconciliation](../../tmp/v1-completion-2026-10-16/phase2-current-reconciliation/REVIEW.md)
  retains all eight Phase 2 remainders. A fresh
  [scalar-store probe and isolated candidate](../../tmp/v1-completion-2026-10-16/scalar-store-scaling-review/REPORT.md)
  confirms 1,056 / 4,160 / 16,512 descendant entry visits for 32 / 64 / 128
  scalar copies on the current source. The declaration-only candidate removes
  those scans while preserving paired generated output and diagnostics. Its
  conservative revision passed 135 nonnative tests. Reference, aggregate,
  assignment and unknown-type paths retain the old store behavior. The controller
  adopted and integrated this bounded internal optimization on October 17.
  It changes no language contract. Full pytest on frozen 1,719-file source
  `3982d76c` passed 5,132 tests with one known scalar-printing expected failure
  and the four authorized scanner exclusions. Owner 73162 terminated with exit 0.
  Independent review verified all source identities and worker outcomes. See the
  [qualification record](../audits/2026-10-17-scalar-store.md).
  P2-81 remains open; no whole-compiler speedup or release-wrapper pass is claimed.
  A current [allocation-pair observation](../../tmp/v1-completion-2026-10-17/allocation-scaling-observation/REPORT.md)
  records 1,922 / 7,938 / 32,258 graph intersection calls for 32 / 64 / 128
  guarded allocations and deletions. Six compile-only runs passed with paired
  identical Zig output. Counts include memo hits, not total compiler work.
  The [next scaling review](../../tmp/v1-completion-2026-10-17/scaling-next-review/REPORT.md)
  identified a longest-prefix lookup that can avoid sorting all known allocation
  places. The exact candidate is now integrated after full pytest on source
  `8bb066b3`: 5,153 passed, one known strict expected failure and four authorized
  scanner exclusions. Independent execution audit and transfer checks passed;
  see the [lookup qualification](../audits/2026-10-17-field-prefix.md).
  No whole-compiler speedup is measured. A concurrent
  [iterator review](../../tmp/v1-completion-2026-10-17/origin-iterator-review/REPORT.md)
  confirms an exhausted generator in the dead-global summary. Eight semantic
  probes still produce the expected six rejections and two accepted controls.
  User-visible impact remains unproven; production source is unchanged.
  The [follow-up summary observation](../../tmp/v1-completion-2026-10-17/origin-iterator-review/summary-observation/REPORT.md)
  distinguishes that iterator mismatch from a reproduced false rejection.
  `if flag { del p; g = new Box } else { g = p }` leaves `g` live on both
  exits, but the function-global summary merges stores and deletions without
  retaining their branch relationship. Eighteen baseline/materialized pairs
  have identical diagnostics; seven valid conditional controls still reject.
  Repair needs correlated effects and invocation-local condition identities;
  a whole-global live/dead shortcut is not a qualified fix.
  The [repair design](../../tmp/v1-completion-2026-10-17/global-effect-correlation-design/REPORT.md)
  and [independent review](../../tmp/v1-completion-2026-10-17/global-effect-correlation-design/independent-review.md)
  require finite predicate identities, guarded slot deaths and preservation of
  same-call deletion history. An isolated implementation is in progress;
  no repaired behavior or production integration is qualified.
  [Call-effect ordering probes](../../tmp/v1-completion-2026-10-17/global-effect-correlation-design/ordering-probes/REPORT.md)
  reproduce three unsafe field-store/deferred-delete programs accepted by both
  semantic checking and Zig emission. Two distinct-allocation controls accept;
  a returned-global negative rejects at the caller. Required field-alias
  rejections remain open. The probes establish unsafe acceptance, without
  proving history clearing is its sole cause. No native program was run.
  The isolated [correlation candidate](../../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/revision3/REPORT.md)
  meets 34 of 44 required semantic/compile outcomes. It still accepts the three
  field-cleanup negatives and two stale-loop-alias negatives in both modes.
  Traces show final field identities are omitted for deleting callees. Repair
  must prove destination identity and write order before publishing those
  stores. The candidate is unintegrated; its new proof tests and broader checks
  have not run.
  [Independent condition checks](../../tmp/v1-completion-2026-10-17/global-condition-verification/REPORT.md)
  pass 433 Boolean truth-table assertions and two concrete call-context
  witnesses. Re-evaluated final summaries and private-variable counts are
  stable. This qualifies those observations, not the failing lifetime cases.
  The [loop diagnosis](../../tmp/v1-completion-2026-10-17/loop-call-alias-diagnosis/REPORT.md)
  identifies fresh call origins discarded in loop-summary mode, followed by
  suppression of saved-alias death publication. Six paired controls and traced
  output parity support that diagnosis. An isolated repair must distinguish
  retained objects across iterations and preserve their deaths. A single prior
  generation cannot distinguish multiple retained older allocations.
  The [ordered-effect design](../../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/revision3/ORDERED-EFFECT-ALTERNATIVE.md)
  extends existing call replay for allocation, globals and returned references.
  It replaces the proposed separate field publisher as the implementation path.
  Both implementations remain isolated and unqualified.
  Ordered revision6 passes 46 of 50 required semantic/compile outcomes,
  including the three field-cleanup negatives, same-holder last-write controls
  and a nil prerequisite. Its two loop negatives still accept. The independent
  [nested-destination review](../../tmp/v1-completion-2026-10-17/global-condition-verification/ordered-candidate-review.md)
  adds a selected-global holder witness accepted by both baseline and candidate.
  A textual field key loses the actual destination alternatives. Falling back
  to the existing summary alone would retain that unsafe acceptance.
  Ordered revision8 represents guarded destination alternatives and restores
  field-location registries on incomplete replay. Its 62 semantic/compile
  commands meet 56 required outcomes: the selected-global negative now rejects,
  but a valid overwrite with a fresh allocation falsely rejects. Both loop
  negatives still accept. Root verified 1,722 source identities, 31 inputs and
  124 streams. Stable selection identity across writes needs further design;
  weakly combining all possible destinations does not meet the valid control.
  The [independent revision8 review](../../tmp/v1-completion-2026-10-17/global-condition-verification/revision8-execution-review.md)
  confirms raw diagnostic parity and intended caller-field spans. The next
  repair must replace each cell under a stable selection guard while preserving
  its previous contents outside that guard and all deleted-allocation aliases.
  Ordered revision11 now accepts the selected fresh overwrite, alias-copy and
  rebinding controls. It matches 68/74 required exit codes. Both loop negatives
  still accept, and the nil-selected valid control falsely rejects. The
  partial-known/unknown negative exits 6 with `cannot_dereference`, not its
  required lifetime diagnostic; that is not a passing lifetime requirement.
  Root verified 1,722 source identities, 37 inputs and 148 streams. Ordinary
  branch feasibility and unknown-effect propagation remain unresolved. No
  candidate pytest/native qualification or live integration has occurred.
  A [paired unknown-destination check](../../tmp/v1-completion-2026-10-17/unknown-destination-controls/REPORT.md)
  reads both the local and formal holder after the selected call. Live source
  accepts the deleted-child negative and fresh-overwrite positive. Revision11
  rejects both with cannot_dereference. Preserve the positive's required exit 0
  and require a real caller lifetime diagnostic for the negative; rejecting all
  unknown deleting calls would not satisfy this pair.
  [Revision13 branch checks](../../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/revision13/REPORT.md)
  meet 72/82 exit outcomes. Skipping impossible lifetime branches fixes the
  nil-selected semantic false rejection, but compile mode exits 7 because
  lowering still requires a dereference approval inside the skipped branch.
  The unknown-destination negative now passes semantic checking incorrectly;
  its fresh-overwrite positive also fails lowering. Preserve condition effects
  when transporting proven reachability, and repair missing call effects before
  treating absence of a field value as proof that a branch is impossible.
  The [symbolic-cell model](../../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/symbolic-cell-oracle/REPORT.md)
  compares concrete object IDs with guarded cells across all nil-inclusive alias
  partitions for one through three entry references. Ordered stores, deletion
  and saved-child observations match within its finite traces. This model uses
  successful child allocation and a fixed fresh holder; it does not qualify
  compiler transfer, allocation failure, arbitrary unknown cells or lowering.
  Independent review also requires complete cell-domain checks and an actual
  three-reference transfer witness. The
  [nullable successor model](../../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/symbolic-cell-oracle-nullable/REPORT.md)
  adds those checks, failed child allocations, copied-child stores and a named
  global slot. Its concrete and symbolic observations match. Arbitrary unknown
  cells, opaque calls, compiler integration and scalability remain unverified.
  An isolated semantic-transfer successor is being prepared for source review.
  A [selected-field cache pair](../../tmp/v1-completion-2026-10-17/selected-field-cache-controls/REPORT.md)
  exposes another failure in represented destinations. A prior read of `g.child`
  makes revision13 accept the deleted-child negative; removing only that read
  restores caller `use_after_move`. Fresh overwrites accept in both forms.
  Canonical replay stores and ordinary textual field caches must share current
  cell state without changing saved aliases. The successor must retain this
  distinguishing pair alongside unknown-destination controls.
  Revision14 now has a reproduced [aggregate replacement regression](../../tmp/v1-completion-2026-10-17/aggregate-field-controls/REPORT.md).
  Its canonical-field store bypasses descendant replacement: deleted q accepts
  while live q rejects after deleting old p. Repair guarded subtree replacement
  and preserve saved aliases before general execution. Both frozen sources and
  all 24 probe streams were verified; no repair is integrated.
  The [expanded aggregate controls](../../tmp/v1-completion-2026-10-17/aggregate-successor-controls/REPORT.md)
  reproduce copy, self-copy and selected-holder failures: six of 24 strict
  outcomes match. Preserve all twelve sources and diagnostic sites through the
  successor; a matching negative exit with a false current-child diagnostic
  does not pass. All 48 streams and before/after source manifests were checked.
  The sixteen-input extension preserves those twelve sources and adds live/dead
  pairs for unselected holders and selected self-copy. Revision14 meets ten of
  32 strict outcomes; all 64 streams and before/after source manifests match.
  [Revision15 execution](../../tmp/v1-completion-2026-10-17/ordered-successor-controls/REPORT.md)
  meets all 32 strict aggregate outcomes and 98/106 earlier ordered-call
  outcomes. Retain the five failing inputs: two stale-loop negatives, the
  three-way formal/global alias negative and two valid lowering failures.
  Correct the independently identified fixed-array diagnostic-site oracle in
  a successor while preserving its original frozen record. Direct indexed-field
  guards remain outside these successful probes. No integration or gate follows.
  A [one-formal witness](../../tmp/v1-completion-2026-10-17/replay-entry-coverage-controls/REPORT.md)
  reproduces unsafe nullable-global acceptance and restores rejection by binding
  g to h before the same call. Both fresh controls accept. The
  [observed replay trace](../../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/replay-entry-observer/execution/REPORT.md)
  confirms that replay starts with active=1 after the caller excludes the nil
  entry region. Its coverage check then rejects a region where the call cannot
  execute. Preserve that check and transport the caller region explicitly.
  All four instrumented outputs match baseline; source and imports were verified.
  Preserve the [shape controls](../../tmp/v1-completion-2026-10-17/replay-region-controls/REPORT.md)
  and [state-boundary controls](../../tmp/v1-completion-2026-10-17/replay-state-boundary-controls/REPORT.md).
  Early return, nested IF, deferred calls, nested declarations and unrelated
  nullable values still admit deleted children; all fresh twins accept. A
  guarded call inside exact callee replay rejects correctly. The independent
  [state obligations](../../tmp/v1-completion-2026-10-17/replay-region-controls/STATE-OBLIGATIONS.md)
  cover split/join, cleanup, loops, nested analysis and rollback. A value's
  missing coverage cannot justify narrowing the surrounding execution region.
  Revision16 carries that region and meets 182/194 required outcomes. Four
  parity-checked traces confirm replay coverage under the caller's region.
  The [focused regression run](../../tmp/v1-completion-2026-10-17/revision16-focused-pytest/REPORT.md)
  passed 182 tests and failed six. Repair the inherited deferred fresh-rebinding
  false rejection and preserve the remaining loop/lowering failures. Correct
  the nil-guard test's obsolete message expectation in a new candidate without
  weakening its semantic rejection requirement. Revision16 remains isolated.
  The [deferred-write observer](../../tmp/v1-completion-2026-10-17/replay-active-fact-observer/execution/ROOT-REPORT.md)
  confirms an excluded nullable case contaminates the evaluated identifier.
  Restrict evaluated facts to the active region while retaining storage and
  death history; verify active-qualified slot deaths separately. The paired
  unguarded, nil-rebound and deleted controls must continue to reject.
  Isolated revision17 passes those controls and the original deferred-write
  test in a [focused run](../../tmp/v1-completion-2026-10-17/revision17-focused-pytest/REPORT.md):
  190 passed, four known loop/lowering failures. The
  [broader batch](../../tmp/v1-completion-2026-10-17/active-fact-successor-controls/REPORT.md)
  meets 194/206 outcomes; seven inputs still fail. Review the extra caller
  diagnostic on the nil-rebinding negative and complete independent execution
  audit. Repair loop and lowering failures before qualification.
  The [region-aware partition probes](../../tmp/v1-completion-2026-10-17/loop-composed2-controls/REPORT.md)
  meet 38/44 targeted outcomes, preserving older-live aliases while rejecting
  tested stale aliases. Three valid zero-trip inputs falsely reject, including
  a condition-call regression from revision17. Repair first-condition effects
  before integration; the remaining preserved controls are still unexecuted.
  [Composed3 controls](../../tmp/v1-completion-2026-10-17/loop-composed3-controls/REPORT.md)
  meet51/60 outcomes. Repair the observed scalar-helper admission failure using
  resolved call-signature types, then recheck positive and negative controls.
  Zero-trip lowering remains unresolved;36 passing recursion checks do not
  establish full-pipeline qualification.
  The [composed4 correction](../../tmp/v1-completion-2026-10-17/loop-composed4-controls/REPORT.md)
  meets54/60 outcomes, with all30 semantic outcomes matching. Six valid inputs
  still fail lowering. Additional boundary checks meet10/16; retain strict
  repeated-condition and cleanup positives while repairing those gaps.
  [Recurrent traces](../../tmp/v1-completion-2026-10-17/recurrent-scalar-observer/REPORT.md)
  confirm exact scalar loss at the head join. Keep initial-entry effects
  separate from the recurrent fixpoint and verify convergence, unknown paths,
  nested loops and cleanup. Post-loop IF lowering needs a complete feasibility
  certificate; the loop itself can retain its existing emitted behavior.
  The [full composed4 inventory](../../tmp/v1-completion-2026-10-17/loop-composed4-full-inventory/REPORT.md)
  records 315/328 raw matches, or 317/328 after correcting one duplicated nil-case
  oracle in both modes. Eleven compile failures span eight distinct sources;
  two regress from valid compilation on revision17. The 164 records contain
  124 distinct sources. Repeated-condition and cleanup boundary failures remain
  outside this inventory. [Composed5 checks](../../tmp/v1-completion-2026-10-17/loop-composed5-controls/REPORT.md)
  match 67/80 outcomes. The repeated-condition positive now passes semantics
  but fails code generation. Preserve the nine compile failures and cleanup
  and three-phase semantic failures while extending the scalar domain.
  All 44 negative mode rows retain their exact diagnostic contracts.
  The [scalar phase observations](../../tmp/v1-completion-2026-10-17/scalar-domain-observer/REPORT.md)
  confirm actual backedges i=1 and i=2 join to unknown. Cleanup is refused at
  DEFER validation before scalar stores run. Preserve correlated scalar and
  allocation alternatives, then implement existing lexical cleanup and return
  capture order. These successor mechanisms remain unimplemented.
  New [cleanup baseline controls](../../tmp/v1-completion-2026-10-17/scalar-cleanup-baseline/REPORT.md)
  match 4/8 outcomes. A true return captured before deferred mutation is accepted
  in both modes despite a reachable stale read; emitted Zig retains that read.
  Repair this unsafe acceptance before treating cleanup as a precision-only gap.
  The LIFO-disables positive still rejects. No native execution occurred.
  The [return-capture trace](../../tmp/v1-completion-2026-10-17/return-capture-observer/REPORT.md)
  shows fallback exit restoration clearing saved allocation3 and its death,
  then retaining only the deleted global slot. An incomplete empty-origin saved
  reference becomes non-nil and passes the read. Preserve guarded exit values
  and allocation deaths through fallback; nil refinement alone cannot prove
  liveness. This repair must cover zero-trip and deferred break exits too.
  Independent [fallback controls](../../tmp/v1-completion-2026-10-17/loop-fallback-baseline/REPORT.md)
  match 6/14 outcomes: ordinary, nested-cleanup and labeled-cleanup stale aliases
  are accepted; the zero-trip positive rejects. Fresh replacement and distinct
  allocations pass. Retain all seven programs as strict repair requirements.
  The guarded containing-cell successor fails two direct
  [internal probes](../../tmp/v1-completion-2026-10-17/contained-transport-probes/REPORT.md):
  forgetting erases possible death, and reachability omits canonical-owner child
  contents. Source review also found sparse replay and copy-coverage gaps.
  Correct these before broader compiler checks. No pipeline or pytest run has
  qualified the candidate; all 1725 source hashes/modes remain pinned.
  Separate [lowering revision3 checks](../../tmp/v1-completion-2026-10-17/lowering3-focused-pytest/REPORT.md)
  pass137 tests and fail the two inherited unsafe loop cases. Both original
  skipped-arm codegen witnesses pass. The
  [initialized native preflight](../../tmp/v1-completion-2026-10-17/lowering3-native-preflight/REPORT.md)
  passes six of12 compile checks. Diagnose the two failing sources before native
  execution. The [inherited comparison](../../tmp/v1-completion-2026-10-17/lowering3-inherited-controls/REPORT.md)
  meets196/206 outcomes, retaining five failing loop inputs. Six separate native
  effect-order/use tests pass. Minimized nested-initialization probes include an
  unsafe semantic acceptance; repair these effect boundaries before combined
  qualification.
  [Paired fallback traces](../../tmp/v1-completion-2026-10-17/lowering-native-effect-observer-revision2/REPORT.md)
  now confirm wrong holder deaths, missed saved-child deaths and stale nil
  facts after excluded calls. Preserve both valid and invalid controls. Carry
  descendant identities through calls and invalidate unproved field contents;
  a larger branch allowance alone does not establish fallback correctness.
  The [composed loop execution audit](../../tmp/v1-completion-2026-10-17/global-condition-verification/loop-composed-revision1-execution-review.md)
  records 175/188 matching outcomes and 86/94 grouped pairs. It still admits
  stale references, rejects a valid zero-trip loop and fails lowering for valid
  controls. Retain these requirements through the aggregate repair.
  The separate loop candidate repairs the original two failures but introduces
  false rejections for a zero-trip loop and an older live saved allocation.
  A further post-loop alias deletion also remains undetected. These results
  prevent qualification; no expectations or accepted controls are weakened.
  The [loop-partition revision2 probes](../../tmp/v1-completion-2026-10-17/loop-partition-candidate/revision2/REPORT.md)
  match 86/98 outcomes across 49 entries. Simple stale and post-loop alias
  deletion reject, while the older-live/newer-deleted positive accepts.
  Older and nested stale aliases and effectful true entry remain unsafe accepts;
  a zero-trip positive falsely rejects. The selected-overwrite failure from its
  ordered revision8 baseline also remains. Root verified 1,722 source files,
  49 inputs and 196 streams. No native run or live integration occurred.
  Seven [instrumented semantic checks](../../tmp/v1-completion-2026-10-17/loop-partition-candidate/diagnosis-revision2/REPORT.md)
  retain the original raw semantic results. Every observed unsafe loop has
  incomplete exit projection because an unknown written reference survives.
  The zero-trip case combines a complete dead backedge projection with an
  incomplete exit, retaining a death from an unreachable body. Its counter is
  known at entry but excluded by whole-function escape classification. Repair
  requires current nil provenance and condition-local scalar validity; stale
  declaration values cannot prove either property.
  The [corrected observer](../../tmp/v1-completion-2026-10-17/loop-partition-candidate/observer-successor/REPORT.md)
  preserves event-time state rather than references to mutable dictionaries.
  It confirms the seven raw semantic results and final projection dispositions;
  11 earlier status snapshots were inaccurate. A separate source composition
  will use guarded reference cases for current nil provenance before any new
  scalar or backend transfer is added.
  The [zero-entry successor](../../tmp/v1-completion-2026-10-17/loop-call-alias-candidate/revision3/REPORT.md)
  meets 30 of 36 required outcomes. Direct false-entry controls now pass.
  An effectful condition that changes the counter to enter the loop rejects
  correctly. Its false-entry counterpart still rejects a valid program.
  Root's effectful-baseline/results.json records both controls accepted by live
  e4cc2a04 in semantic and compile modes. The false-entry rejection is therefore
  a candidate regression; the true-entry rejection repairs a baseline gap.
  Older-live/new-dead and post-loop alias deletion remain unmet requirements.
  The [partition projection design](../../tmp/v1-completion-2026-10-17/loop-call-alias-candidate/PROJECTION-ADDENDUM.md)
  remains unimplemented. It requires exclusive, exhaustive guarded alternatives,
  preserved entry identities and explicit treatment of unknown aliases.
  The [isolated escape model](../../tmp/v1-completion-2026-10-17/loop-escape-model/REPORT.md)
  covers 32,768 concrete short traces and seven targeted controls. Its three-slot,
  one-site abstraction reaches 756 states without a state cap. It preserves
  distinct retained objects and possible alias deletion after external recovery.
  The external pool loses exact object counts; all allocation succeeds in this
  model. Entry-root projection, nil allocation results, exact external fields
  and preservation of escaped relationships in compiler facts remain unresolved.
  The [P2-73 source review](../../tmp/v1-completion-2026-10-07/phase2-stack-evidence/REPORT.md)
  separates compiler initializer credits from native stack size. Fixed local
  arrays lower to zero-initialized Zig values; source inspection does not prove
  the historical 200 MB crash or a native frame size. No stack cap or allocation
  change is selected, and no exhaustion-sized program was run.
  Fresh [P2-68 probes](../../tmp/v1-completion-2026-10-07/phase2-selected-import-evidence/REPORT.md)
  confirm that unused selected names are unchecked and selected calls remain
  undefined. Ordinary alias access emits Zig. The
  [selected-import proposal](packets/P-MOD-selected-imports.md) awaits a decision;
  no selected-binding contract is adopted.

- R6 Docs, site and records. PARTIAL: README rewritten; tensor proposals moved
  out of SPEC; STATUS, CHANGELOG, module guidance and site pages updated.
  Site coverage, build, exports and links pass. Continue reconciliation as
  compiler changes land; error catalog, examples and final release review remain.
  The October 8 catalog correction verifies all 94 enum codes by family and
  uses four live compiler-only probes for imports, duplicate enum values and
  numeric-token length. It corrects catalog guidance without changing compiler
  behavior. The matching source hints now describe numeric-token characters
  and supported file imports; 63 focused tests pass. See the
  [catalog report](../../tmp/v1-completion-2026-10-07/error-catalog-reconciliation/REPORT.md).
  Fresh AST report probes cover the old missing loop/match/else-if declarations;
  the checker formerly corrupted parent shadow types in two valid else-if controls.
  The integrated scope-traversal repair passes focused and independent checks
  plus 12 native controls. Earlier combined source `158a8423`, including import-path
  diagnostics and the benchmark gate repair, passed full pytest with 4,124 tests
  and one expected failure. All nine direct compiler/package checks passed.
  Integration verified 319 compiler-related paths and seven documentation files.
  The separate SPEC reference-parameter correction follows L60. Site build,
  exports and links pass; the preview test fails on socket-listen `EPERM`.
- R7 CI, release, cleanup, file splits. PARTIAL. The explicit benchmark gate now
  requires a complete usable host pin before building. Controlled CLI evidence
  covers missing and invalid pins; the native benchmark run reports timings
  without establishing a performance limit. Release cleanup and file splits
  remain queued.

### A. Language chain

- A1 Generics: `$N` value parameters DONE with open repairs under R2
  (L66); minimal `where` DONE (L66); function overloading PARKED (L59
  restores the duplicate-name error).
- A2 Payload matching: dot arms parse, check, lower and run (L66);
  repairs under R2.
- A3 Option/Result: package-owned canonical generic unions and checker-typed
  existing stdlib returns are integrated under B1/B2 and L68. Collection
  operations and future stdlib modules remain queued.
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

- B1 `Option`/`Result` generic unions. Package-owned canonical declarations
  replace user declarations under L68/U3. Integrated and package-tested.
- B2 Existing stdlib calls use declared signatures. Saved `read_line` results,
  cross-file signatures and nested field-only types compile and run. Void I/O
  calls in typed initializers and returns fail with semantic exit 6. The frozen
  compiler/package gate passed 3,826 tests with one expected failure and all
  11 checks. A stale generated docs manifest stopped the release wrapper.
  Regenerating that one export preserved all compiler/package source bytes;
  site and remaining release checks then passed. Independent GLM and Flash
  reviews covered the repaired source. The [record](../audits/2026-10-07/stdlib-b2-verification.json)
  preserves the failed wrapper and separate recovery. Broader stdlib work remains.
  The separate B2 stage repair passed its combined gate on frozen source
  `e0c6235a43632839d50be28d2128af666be78634e8a5c50c8fcf317ef6915470`. Registered `print`,
  `println` and `eprintln` cannot supply inferred/container values, conditional
  results or format arguments. The reviewed checker reports semantic exit 6
  where those forms previously failed at codegen exit 7. It preserves discarded
  statement effects, `println_ok` values, ordinary user void bindings and
  existing type and exact-constant diagnostic priority. Later semantic-validator
  messages can be suppressed by this earlier type-check failure. Author checks
  passed 181 nonnative tests;
  independent review covered 36 paired observations over 18 fresh sources,
  including nine corrected source shapes and five identical accepted Zig
  outputs. Nine native controls passed across debug, release and fast with
  exact stdout/stderr and unchanged emitted Zig. The combined gate result is
  3,933 passed, one expected failure and
  11/11 compiler/package checks; log SHA256
  `b795102848638d64f78ce2a8091903c32079a07655c6879832d8611b5320bc2c`.
  Broader user-function void consumption remains unresolved.
- B3 Phase A, no heap: `io`, `option`, `result`, `slices`, `strings`,
  `ascii`, `bytes`, `math`, `conv`, `sort`, `hash`, `random`, `time`,
  `os`, `fs`, `path`, `testing`, `json`, `yaml` (L65, L68). QUEUED
  behind the proposal's Phase 0–2 gate and remaining infrastructure.
  Declared existing-hook signatures and per-module type scopes are implemented.
  R3 generic construction/return passes seven fresh forms in all three native
  profiles, including cross-file wrappers and qualified constructors. The old
  D6 codegen failure is stale for these controls; broader specialization is open.
  R13 and R21 compiler prerequisites are integrated. Hook signatures, explicit
  argument policies, module-owned declarations and mapped Zig fragments come
  from the registry. Reserved `std/` imports can load package-owned A7 sources.
  Public modules remain `io` and `math`; ASCII remains a loader-test fixture.
  The integrated source also checks known literal-index fixed-array aliases
  under L74. Unknown container identities retain their existing limits.
  The frozen combined compiler passes 4,006 tests with one expected failure,
  12 valid native alias controls and nine direct compiler/package checks.
  Examples and all three artifact profiles pass 51/51; error stages pass 61/61.
  Source hashes match after integration. The [prerequisite record](../audits/2026-10-07/stdlib-source-loader-prerequisites.json)
  retains predecessor failures, independent reviews and exact source identities.
  Documentation and agent exports are updated. Site build, exports and links
  pass; the preview test fails with `EPERM` on socket binding. Rendered-site,
  external GLM and full release qualification remain incomplete. Scans remain
  excluded. Phase A still requires reconciliation of remaining Phase 2 work;
  these prerequisites do not promote public modules or complete lifetime safety.
  The generic fixed-array initializer repair is integrated after 283 focused
  tests and 99 independent compiler-only controls. Frozen source `4e432638`
  passes 4,075 tests with one expected failure, 12 native controls with exact
  output and nine direct compiler/package checks. Site exports, build and links
  pass; the preview test still fails on socket binding with `EPERM`.
  Successor evidence covers the import-path and benchmark-gate repairs.
  The twenty-row Phase 2 reconciliation retains eight decision or verification
  remainders after twelve scoped repairs. It does not clear B3 or promote public
  modules. Its `de578138` source is now integrated; historical labels alone
  are not evidence that a repaired failure persists. A subsequent CLI Debug
  probe confirms P2-75's deleted generated-source reference in the saved binary.
  This bounded defect has no adopted fix or design. Binary execution, debugger
  behavior and full A7 source mapping remain unverified; B3 remains queued.
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

- D1 Examples 049 and 050. DONE. Example 014 now demonstrates approved
  `where T: Integer` with signed and unsigned arguments. Its three native
  profiles and the full 51-example E2E run pass; see the
  [verification record](../audits/2026-10-08-generics-example.md).
  Examples 016 and 018 now demonstrate scalar payload binding and a local file
  module. Both pass three native profiles. Existing labeled break/continue
  behavior in example 036 is covered by the combined 51-example E2E pass.
  The [payload/module record](../audits/2026-10-08-payload-module-examples.md)
  closes these D1 demonstrations without claiming general language coverage.
- D2 Docs sync per landing: SPEC, STATUS, CHANGELOG, `site/public`
  exports through `sync:exports`.
- D3 Run permitted compiler/package checks with
  `./run_all_tests.sh --skip Secrets`, or the equivalent direct commands.
  Run release-identity and site checks separately. The user excluded cyber
  scans; do not run `run_release_checks.sh` unchanged or claim that wrapper
  passed. The [2026-10-08 site checkpoint](../../tmp/v1-completion-2026-10-08/site-checkpoint/REPORT.md)
  passed all seven checks and 12 tests, including preview binding. Its 554 source
  entries were unchanged; browser rendering and publication remain unverified.
  Publication still requires the completion evidence below.
- D4 File splits (parser, type checker, Zig backend): QUEUED under R7.
- D5 B0 benchmark promotion (L56, L67): `mem_shared`, `mem_returned` and
  `mem_cleanup` are promoted after nine native correctness runs across three
  profiles. See the [L67 record](../audits/2026-10-08-l67-promotion.md).
  The [October 16 promotion](../audits/2026-10-16-l67-promotion.md) adds the
  four rewritten public-input workloads after native and retention checks.
  Re-pinning all 17 entries remains QUEUED for an idle host. Neither promotion
  nor the existing host pin qualifies L38.

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

The combined exact-resource accounting and typed hexadecimal emission snapshot
`44acf840` remains unintegrated. Its full pytest run recorded 4,262 passed, three failed
and one expected failure. The failures concern direct math-call output,
temporary-directory Git ancestry and an obsolete decimal-emission assertion.
The four-program native controls passed in Debug, ReleaseSafe and ReleaseFast.
These results do not qualify that snapshot for integration. Approved C3–C10
accounting was subsequently qualified and integrated separately as `3fbb40dd`,
preserving current math output and numeric spelling. C11 hexadecimal emission
still needs the math-output decision, rebasing onto the current compiler,
verification of the prepared test repairs and fresh qualification. The
[audit record](../audits/2026-10-07/stdlib-source-loader-prerequisites.json)
retains manifests, failed runs and native evidence.

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
| Publication | Blocked by incomplete requirements above | Frozen source, permitted release checks, installed artifacts, browser checks, documentation and GLM compiler review; cyber scans remain excluded |

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
   The deep JSON regression now rejects internal errors for its 2,000-link
   undefined chain. Six focused tests passed, with independent semantic-6
   observations in all three modes on `3ba27b74`. Preserve this separately
   tested live assertion change during later integration.
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

The [concurrency transition draft](research/concurrency-transitions.md) separates
task completion, cancellation requests and channel payload ownership. It records
proposed race outcomes and acceptance oracles before API selection. It is not an
approved packet or implementation evidence. Independent review identified stop
actions that invalidate borrowed descriptors, native callback dependencies and
child cleanup waiting on post-join queue disposal. The draft records these
constraints and compares cleanup orders without claiming deadlock freedom.
The [structured-task packet](packets/P-CON-structured-tasks.md) now supplies
three complete proposed programs and explicit operation outcomes. Their
[parser-only checks](../../tmp/v1-completion-2026-10-07/concurrency-packet-parser-canonical/REPORT.md)
pass on frozen `de578138`; type correctness and runtime behavior are unverified.
Complete owning-result extraction, handle lifetimes, early-return failure
delivery and native/runtime admission before requesting approval. Terminal child
runtime failure and a recoverable failure to wait are separate proposed outcomes.
The [consuming-result comparison](research/consuming-results.md) records the
payload prerequisite. Twelve fresh compiler-only probes confirm that today's
string-containing-payload rejection is not a general ownership classifier:
ref and slice captures pass. Settle consumption, alias visibility and cleanup
before using a general result API for task or channel ownership transfer.
The [consuming-result spelling packet](packets/P-RESULT-consuming-surface.md)
proposes an explicit `results.take` match subject and records the unresolved
public semantics. Independent review found no scoped wording blocker; both
complete programs passed [parser-only checks](../../tmp/v1-completion-2026-10-07/consuming-surface-parser/REPORT.md).
The design-direction question is pending. It does not authorize implementation.
Reconciliation with L68/U2/U3 corrected the task and channel proposal to use
canonical `Result` and `Option`, retaining operation-specific error distinctions
inside those types. L68/U6 already requires shared list identity and no manual
freeing. Neither that decision nor the historical file-close signature settles
general automatic cleanup. The [authority review](../../tmp/v1-completion-2026-10-07/concurrency-stdlib-authority/review.json)
records the adopted constraints and remaining gaps.

The [CPU AI contract boundaries](research/cpu-ai-contract-boundaries.md) reconcile
L7-L11, L16, L38 and L73 with the archived research. They preserve the four
formats and classifier/decoder scope, distinguish cost limits from open numerical
and model-quality thresholds, and define the evidence needed for fresh-process
checkpoint continuation. Freeze tensor/AD semantics, workload recipes and
thresholds in a concrete packet before CPU AI implementation. No tensor runtime
or checkpoint behavior is qualified by that source review.
The [tensor value packet](packets/P-AI-tensor-values.md) proposes immutable
automatically retained handles, copying constructors, checked shapes, read-only
views and explicit materialization. Its two complete programs passed
[parser-only checks](../../tmp/v1-completion-2026-10-07/tensor-values-parser/REPORT.md).
Current `std/tensor` imports still fail with exit 3. Numerical operations,
four-format computation, AD and model workloads remain separate requirements.
The [tensor cast packet](packets/P-AI-tensor-casts.md) proposes explicit direct
nearest-even conversion, gradual underflow and stated NaN/overflow behavior.
Its scoped approval question is pending. Thirty-three exact finite/signed-zero
vectors and two double-rounding witnesses have independent arithmetic checks;
the complete API example passes parsing. This is reference evidence, not native
A7 conversion qualification. All source/destination pairs and exceptional-value
cases remain required after implementation.
The [strict reduction packet](packets/P-AI-strict-reductions.md) proposes
default sum/dot/matmul order, accumulator/output widths and contraction rules.
Its approval question is pending. Independent exact witnesses distinguish
reassociation, low-format accumulation and FMA; one complete example parses.
Native kernels, cost qualification and any optimized opt-in policy remain open.
The [autodiff transition draft](research/autodiff-transitions.md) separates
recording commit, backward consumption, saved-value lifetime and gradient
lookup. It distinguishes connected zero gradients from disconnected inputs.
Alias invalidation, four-format adjoint rules and complete executable examples
must be settled before an approval packet. No AD behavior is approved or
implemented by this draft.
Its source reconciliation identifies a missing outcome-dependent consuming
effect contract: current allocation/deletion facts and tagged results do not
establish tape-state refinement. Select static effects, shared runtime state or
an explicit combination before implementing backward and retry behavior.

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
| V1 qualification | Core, memory, concurrency, CPU AI, GPU, self-hosting, docs, packaging and permitted independent reviews | All criteria pass at one identified Linux x86-64 source state; cyber scans remain excluded |

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
The later [L67 promotion](../audits/2026-10-08-l67-promotion.md) verified all three
on `de578138` in Debug, ReleaseSafe and ReleaseFast and copied them unchanged
into `bench/`. Nine executions matched exact stdout with empty stderr.
The following dated rewrite checks precede their October 16 promotion.
The [October 7 public rewrite checks](../../tmp/v1-completion-2026-10-07/l67-rewrite-current/REPORT.md)
supersede the old public-input rejection: copy, text and ID-cycle sources pass
semantic checking and Zig emission on `de578138`. Cache rejected with
36 moved-value diagnostics; the separate reduced loop witness above isolates
a valid replacement case. Native correctness and optimized work retention for
these exact public candidates were unverified at that checkpoint. Text and ID-cycle programs
remain proxies and cannot replace required retained-text or reference-cycle
qualification. The [October 16 combined-source prechecks](../../tmp/v1-completion-2026-10-16/l67-combined-prechecks/REPORT.md)
accept all four unchanged inputs on `04c5e959`, with no diagnostics and four
emitted Zig files. The cache's earlier 36 moved-value errors are absent.
The [native specification](../../tmp/v1-completion-2026-10-16/l67-native-spec/REPORT.md)
resolves exact outputs for both ASCII seeds at the original iteration counts.
The [corrected native runner review](../../tmp/v1-completion-2026-10-16/l67-native-preparation/PEER-V2-REVIEW.md)
checks the prerequisite schema against the actual saved results. The first
runner stopped before native execution because it expected the wrong status
label; that failure remains preserved. Revision 2 completed under owner
session 47687 with exit 0. The [independent native audit](../../tmp/v1-completion-2026-10-16/l67-native-independent-review/REPORT.md)
verified all 24 byte-exact outputs at the original counts across three profiles
and two seeds, plus 51 commands, 102 streams, 24 artifacts and all 1,708 source
identities. No workload was rerun for the offline audit.
The [retention review](../../tmp/v1-completion-2026-10-16/l67-retention-review/REPORT.md)
defines checks for the eight actual optimized binaries after terminal output
verification. Trace workload allocation pointers, replacement/free paths,
copy extents, scan extents and loop bounds. Historical kernel disassembly
does not qualify these public-input binaries; symbol presence and correct
checksums alone do not establish retained work. The completed
[optimized inspection](../../tmp/v1-completion-2026-10-16/l67-retention-review/INSPECTION-RESULT.md)
found workload heap requests, required payload operations, loop control and
successful release paths in all eight binaries. All 27 inspection commands
passed; no workload was rebuilt or rerun. Dynamic allocation counts, all
failure paths and memory costs remain unmeasured. Keep the retained-text and
reference-cycle proxy limits after promotion; this evidence does not
qualify an automatic-memory design.
The current harness's host-pin
ratio and timing-only measurements do not satisfy L38's per-workload C runtime
and peak-live-memory limits. Equivalent C baselines and actual release/retention
instrumentation remain required before the arena/RC comparison can qualify.

L53 already authorizes sample-count, variance and affinity hardening before
re-pinning. Isolated harness candidate `bd555bdc` implements seven default
samples, a five-sample pin/gate minimum, rejection above 0.10 raw-sample CV and
enforced inherited CPU selection. All 36 deterministic tests passed; their
mocked process and timer boundaries do not establish performance. Independent
source review found no blocker. The original manifest was recorded after
testing. The later frozen combined source `04c5e959` passed full pytest and is
now integrated. Its report-only benchmark ran thirteen workloads with seven
samples, but unpinned affinity and `alloc_churn` CV 0.13 prevent qualification.
The strict gate failed for three missing host pins at that checkpoint.
The [October 16 promotion](../audits/2026-10-16-l67-promotion.md) expands the
suite to 17 workloads and the missing-pin count to seven. The actual candidate
harness passed four full-count ReleaseFast smoke runs with exact A-seed output
and empty stderr. Calibrate all 17 workloads in an idle measurement window;
preserve existing pins until the
complete run passes. No host pin has changed.

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
W2 now passes 75 Debug native checks across independent C and arena/RC sources:
18 normal/injected cases, three copy corruptions, six named faults, 47 invalid
inputs and trace overflow. Actual typed pointers preserve the shared row and
independent historical snapshot. Normal requested peaks are 48 bytes C/arena
and 144 RC; corrupt metadata leaves explicitly checked 40/144-byte residuals.
Independent source, GLM and archived native evidence reviews passed within those
bounds. [Verification](../audits/2026-10-07/memory-w2-verification.json) retains
source/runner/artifact hashes. Optimized execution, full runtime accounting,
competitive representations, timing and L38 remain open.

W3 now passes 75 Debug native checks: 18 normal/allocation-failure cases,
three intact-cycle aborts, 47 invalid inputs, trace overflow and six output
failures. Actual node pointers form the cycle and preserve the expected
reachable and stored nodes after deletion. Requested backing peaks are
96 bytes for C/arena and 192 for RC. After deletion they are 72, 96 and
144 bytes; arena retains 24 dead payload bytes until teardown. These
figures exclude unmeasured runtime storage. RC explicitly clears the
container's owned edges before releasing roots; this is not a general
cycle collector. Independent trace review confirms the bounded cases.
The GLM report's incorrect output-error and arbitrary-corruption claims
were rejected during reconciliation. The corrected C source and unchanged
Zig source return 5 for stdout failure and 6 for trace failure. The
[W3 verification record](../audits/2026-10-07/memory-w3-verification.json)
retains source and evidence hashes. Optimized execution, full runtime
accounting, timing, competitive representations and L38 remain open.

W5 has two independently derived semantic models. For 10,000 individual
cache accesses they agree on 4,999 hits, 5,001 successful misses and
sum 661,665. At 100,000 accesses they agree on 49,999 hits, 50,001 misses
and sum 6,616,665. The independent model checks 66 failure/retry cases.
Primary inline and fixed-pool C baselines must use zero workload heap
allocations. Per-miss heap storage is a separate ownership stress case.
Both C sources passed 84 bounded O0 native checks each. Exact small
traces, parser rejection and output-failure exits were checked against
archived raw outputs. Native layout has 44 rows for inline storage and
47 for the pool. The pool category summary omitted a 15-byte snapshot;
source and native records include it. The corrected 475-byte inventory
is not peak memory. See the [native record](../audits/2026-10-07/memory-w5-verification.json);
the [preparation record](../audits/2026-10-07/memory-w5-preparation.json)
preserves the earlier source-only stage.
The later large C run passed 24 cases across 31 commands: 20 full traces and
four summaries at 10,000 and 100,000 accesses. All 162,447,636 stream bytes,
about 155 MiB, remain archived. An audit replayed every row and stdout against
the frozen protocol. Its author also authored inline C and reviewed pool C;
the shared contract/layout oracle and that provenance limit are recorded in the
[large C evidence](../audits/2026-10-07/memory-w5-large-verification.json).
These O0 correctness results do not qualify timing or full memory costs.

The corrected arena/RC contract distinguishes wrapper attempts, actual
allocator calls and physical allocation/free counts. Source-specific layouts,
fault traces and prototype source are frozen. Independent source review found
no blocker in the named source paths. The first Debug preflight then failed
with Zig SIGSEGV during object compilation, before linking or workload runs.
Core evidence identifies an unmapped copy read; its compiler subsystem and
root cause remain unresolved. The [preflight failure record](../audits/2026-10-07/memory-w5-managed-preflight-failure.json)
preserves the attempt. An exact fresh-cache repetition also crashed. The same
source compiled to an object after changing only `-fllvm` to `-fno-llvm`.
The [backend diagnostic](../audits/2026-10-07/memory-w5-zig-backend-diagnostic.json)
records this differential; no compiler root cause or production backend choice
is established. A fresh Debug build linked and passed the unchanged six-case
matrix: arena/RC with zero accesses, six accesses, and loader failure at one.
All stdout and complete stderr matched; eleven commands exited zero. The
[managed smoke record](../audits/2026-10-07/memory-w5-managed-smoke.json)
supports that C ABI path and those traces. Prepare and verify the normal allocator
observer next. No independent physical-free witness exists. Silent trace-failure cleanup still needs an allocator
observer. The source, models and earlier source reviews remain preserved.
Normal observer build preparation was rejected by an automatic safety filter;
no build ran. The [preparation record](../audits/2026-10-07/memory-w5-observer-preparation-block.json)
records the failed delegation and halted dependent preparation.
Managed large workloads, optimized execution, complete memory accounting and
performance remain unqualified. Keep stack eligibility separate from
the proposed whole-cache heap experiments.

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
and the permitted compiler/package checks. Cyber, secrets and dependency-vulnerability
scans remain excluded by the user's instruction. Publish only claims supported by
that identified source state.
Use dependency milestones rather than calendar promises.

## Current implementation evidence

The [2026-09-20 batch report](../audits/2026-09-20-core-v1/README.md) records
implemented compiler and distribution changes, reviews and open blockers. The
[next correctness batch](../audits/2026-09-20-core-v1/next-correctness-batch.md)
separates the loop-label repair, declaration identity work and fallthrough
compatibility experiment. None of these records marks the V1 milestones done.


### Readonly call requirements

The integrated rejection-only analysis preserves previously accepted valid
controls while rejecting represented nil reads through readonly callees.
Readonly V3 repairs finite-loop counters, forwarded scalar borrows and
Boolean/integer environment identities. Its full release gate and six native
controls pass on manifest `cf6a985d`. Independent and GLM reviews retain their
separate source scopes. Caller-local selectors, incomplete summaries,
unsupported effects, globals, reference fields and containers remain open.
