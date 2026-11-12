# A7 Status

This is the single working status document for current gaps, roadmap, and
implementation priorities. Keep `docs/CHANGELOG.md` short and release-facing.

The toolchain pin is Zig 0.17.1 (`a7/cli.py` `ZIG_VERSION`, CI/release
workflows, archive prefix `zig0.17.1`). Native builds require that exact
version on `PATH`. The 2026-11-12 push checkpoint still records an older
0.16.0 mismatch against a host 0.17.0 install; that conflict is closed by
this pin. [Push check record](audits/2026-11-12-push-checks.md).

The checked storage-identity adapter passes all sixteen original caller
outcomes, including repeated_site_live. Eleven importer invariants, 23 focused
tests and six readonly tests pass. New controls match 14/16 outcomes: the fresh
replacement-allocation positive still rejects in both modes. Parent verified
1,736 source pins and 1,024 standalone imported module bindings. No full sweep,
native run or integration followed these remaining failures.
[Identity adapter execution review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/scalar-contained-identity-focused/PARENT-REVIEW.md).

Callable successor10 passes 11/13 tests and 10/14 standalone outcomes. Noop,
nested live and copied-noop cases improve. Mixed targets, repeated owner contexts,
argument capture and the global writer still have failing live controls. Parent
verified 1,740 sources and 479 module bindings. Broader tests remain unrun.
[Callable successor10 review](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor10/PARENT-EXECUTION-REVIEW.md).

The checked scalar-metadata successor passes four invariants, 23 focused tests
and six readonly tests. Its caller controls remain 14/16: repeated_site_live
still rejects in both modes. All 16 complete diagnostics and exits match the
predecessor. Parent verified the 1,735-file snapshot and bound result artifacts.
The scalar filter removes the empty payload, but a later identity mismatch
still blocks the program: exact replay uses a storage identity where the loop
inventory expects an owner/field identity. Both observation packets preserve
full JSON parity. A typed identity repair is being designed. No full sweep or
integration.
[Scalar metadata execution review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/scalar-contained-focused/PARENT-REVIEW.md).

The entry-owner obligation candidate passes all 23 original focused tests and
six readonly ownership tests. Its new controls match 14/16 required outcomes,
up from 10/16 on the predecessor. The repeated-call-site live program still
rejects in both modes; all five negative fixtures retain their required sites.
Root verified the 1,734-file source and focused/standalone artifacts. The full
238-outcome sweep has not run on this candidate. No safety integration.
The direct `read(nil,false)` rejection-preservation case is awaiting the
user's disposition: complete proof of skipped use would change exit 6 to 0.
The reached true case must still reject. Keep the existing oracle until approval.
[Pending call-proof proposal](plan/packets/P-REF-proven-skipped-call.md).
[Entry-owner execution review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/entry-owner-obligation-focused/PARENT-REVIEW.md).

The readonly composition candidate passes all eight caller checks and all six
replay-ownership tests. Its focused reference suite reports 22/23 passed; only
the valid nested distinct-owner case still rejects. The previously unsafe
readonly nil call now rejects at the required caller site. Root verified the
1,734-file source manifest and focused input, import and artifact hashes.
The full run matches all 238 required outcomes. Root verified 476 streams,
238 import reports, 7,616 module bindings and 59 emissions. Only the two
readonly nil outcomes differ from the predecessor; all other complete error
objects and exits match. No safety candidate is integrated.
[Full composition review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/readonly-composition/full238/PARENT-REVIEW.md).
[Focused composition review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/readonly-composition/PARENT-FOCUSED-REVIEW.md).

The preceding reference-publication candidate matched 236/238 full regression
outcomes: 218 inherited, 14 caller and four imported-module checks. Full error
objects and exits changed only in the four intended replacement-reference rows.
[Prior full regression review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/repeated-new-successor/full-reference-publication/PARENT-REVIEW.md).

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
[Adapter execution review](../tmp/v1-completion-2026-10-18/readonly-revision11-review/performance-candidate/closed-root-adapter-successor2/PARENT-REVIEW.md).

The proposed readonly summary shortcut fails its strict admission check at all
nine observed calls: six have incomplete owner views and three receive nil.
Keep those ownership requirements. A summary must carry guarded owner-use
obligations before it can replace replay. The existing broad readonly run has
no terminal result.
[Admission evidence](../tmp/v1-completion-2026-10-18/readonly-revision11-review/summary-admission-observation/REPORT.md).

A fresh-guard trace confirms a safety/backend proof gap on scalar successor6.
Safety skips a body whose derived guard is zero, but owner blocking prevents
an omission certificate. Zig retains the body and rejects its unapproved field
access with exit 7; the required valid result is 0. Plain and observed full JSON
match apart from timing. Parent verified 1,738 source pins and 31 imports.
A local omission-proof design is under review; no eligibility rule changed.
[Fresh-guard diagnosis review](../tmp/v1-completion-2026-10-18/readonly-revision11-review/fresh-guard-diagnosis/PARENT-REVIEW.md).

Callable traces locate the earliest failure in formal-type classification:
both noop and nested-writer summaries have an empty callable-parameter map.
Concrete outer targets are captured, but their owners have no usable summary.
Plain/observed full JSON matches apart from timing. A source-only correction
will use checked function-signature parameter types consistently; later callable
evaluation and capture controls remain unqualified.
[Callable diagnosis review](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor9-diagnosis/PARENT-REVIEW.md).

Callable successor9 fixes the undefined variable but passes only 7/13 focused
tests and 8/14 standalone requirements. All standalone commands exit 6; valid
writer and noop controls still reject. Parent verified 1,740 source hashes,
30 streams and 479 imported module bindings. Negative generic rejections do not
qualify captured-target checking. No broader suite or native execution followed.
[Callable first-stage review](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor9/PARENT-REVIEW.md).

Callable successor8 failed before semantic checking: 13 tests failed and all
14 standalone commands exited 8 with an undefined program variable. Both source
reviews missed that the call is inside _visit_program(self, node). The failed
snapshot is preserved. A separate one-line correction will rerun the unchanged
controls before any broader suite.
[Callable review correction](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor8/PARENT-SOURCE-REVIEW.md).

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
[Successor6 execution review](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor6/execution/PARENT-REVIEW.md).
[Broader scalar report](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor6-regression/REPORT.md).

Revision13 successor3 reports 76 passed and three failed tests. All 10 CLI
checks match. The three indexed true variants now pass, including capture before
later argument mutation. Returned-nil guarded setter and mixed copied-guard
positives still reject, as does the unknown-callable live case. Keep their
acceptance requirements. Root verified 1,736 source pins, 79 program inputs,
41 emissions and 475 loaded module bindings. No safety candidate is integrated.
[Focused execution report](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor3/REPORT.md).

Three plain/observed diagnosis pairs preserve full diagnostics and emissions.
Direct literal nil passes a guarded setter; a returned nil reference fails an
unconditional argument-nonnil check in both ordinary analysis and replay.
The setter replay itself completes. Mixed-case lifetime errors remain, so
removing those argument checks alone is not a verified repair. Preserve actual
read, write and lifetime obligations when correcting their proof ownership.
[Nullable setter diagnosis](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor3-diagnosis/REPORT.md).

A separate mixed-case trace locates the first ordinary-analysis precision loss:
the branch join drops a primitive indexed scalar cell because it has no
allocation identity. Keeping the cell alone is insufficient; its conditional
Boolean values also need guarded transport. Both plain/observed pairs match.
This is a diagnosed defect, not an integrated repair.
[Scalar join diagnosis](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision13/successor3-mixed-diagnosis/REPORT.md).

Two new Claude CLI attempts ended with exit 1 after provider retry exhaustion.
Both reported EAI_AGAIN and zero model tokens. Neither completed a review or
repaired tests. Detailed prompts, logs and terminal records are preserved.
[Claude attempt evidence](../tmp/v1-completion-2026-10-18/claude-repair-wave/REPORT.md).

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
[Readonly nil controls](../tmp/v1-completion-2026-10-18/readonly-abort-controls/requirements.json).
[Revision11 focused evidence](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision11/REPORT.md).
[Revision12 first-stage review](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision12/execution-new/PARENT-REVIEW.md).

Revision10 `a216986b` matches all four scalar-argument snapshot outcomes,
all six original boundary outcomes and all 12 strict typed outcomes. Focused
pytest reports 93 passed and four failed. The borrowed-scalar distinct and
callee-rebinding positives still reject; two new admission tests fail because
their synthetic allocation labels are invalid. Keep their requirements while
correcting the fixtures. The inherited discovery matches 196/206; all exits and complete diagnostics
are identical to revision7. The same five loop cases still fail in both modes.
No native or
production integration is claimed for this safety candidate.
[Revision10 evidence](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision10/REPORT.md).
[Revision10 inherited evidence](../tmp/v1-completion-2026-10-17/typed-reference-revision10-inherited/REPORT.md).

Revision10 fixes revision9's optional-marker crash and readonly test setup.
Revision9 had already repaired the global-flag and computed-constant boundaries;
its scalar snapshot still rejected before CALL-actual admission was corrected.
[Revision9 evidence](../tmp/v1-completion-2026-10-17/typed-reference-candidate/revision9/REPORT.md).

Revision8 matched only 2/6 original boundary outcomes. Its observer showed a
global Boolean lost before ordinary call analysis and a checked exact constant
rejected by root initialization. Revision9 repairs those bounded cases; it does
not establish general scalar-reference or lifetime correctness.
[Revision8 diagnosis](../tmp/v1-completion-2026-10-17/typed-reference-revision8-diagnosis/REPORT.md).

The revision7 inherited inventory matches 196/206, the same as revision4.
Four unsafe loop sources remain accepted, and one valid loop source rejects,
each in both modes. Root session14254 terminated with recorder exit0; that exit
records completion, not passing requirements. Root rehashed 412 output streams
and 206 import reports. Independent review verified all 1,728 source pins. Every
exit and full diagnostic object is identical to revision4. Seven negative sources retain
duplicate diagnostics. Emitted-file hashes establish current bytes only; the
runner did not pin those files at execution time.
[Inherited terminal record](../tmp/v1-completion-2026-10-17/typed-reference-revision7-inherited/OWNER-TERMINAL.json).
[Inherited audit](../tmp/v1-completion-2026-10-17/typed-reference-revision7-inherited/REVIEW.md).

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
[Loop discovery](../tmp/v1-completion-2026-10-18/loop-composition-discovery/REPORT.md).
[Full inherited result](../tmp/v1-completion-2026-10-18/loop-composition-inherited/REPORT.md).
[Recurrent-owner controls](../tmp/v1-completion-2026-10-18/loop-recurrent-owner-controls/REPORT.md).

Independent returned-boolean controls on revision7 match all four outcomes,
without an empty-if seed. Each negative receiver has two distinct reasons per mode: ordinary use and
callee replay. These are repeated sites, not identical diagnostic objects.
No native or release qualification is claimed. The earlier revision4 native
witness does not qualify these successors.
[Returned-boolean controls](../tmp/v1-completion-2026-10-18/returned-guard-controls/REPORT.md).

The recurrent-owner observer confirms two false-rejection mechanisms: unknown
fallback adds the deleted owner to a reference saved from a distinct allocation;
backedge deaths also contaminate first-entry body analysis. A successor is being
implemented in isolation with ordered captured stores and separate first/recurrent
condition poststates. Preserve residual deaths for unsupported effects.
[Owner diagnosis](../tmp/v1-completion-2026-10-18/loop-recurrent-owner-diagnosis/REPORT.md).

The owner-loop successor's second frozen stage passes 25 direct domain/import
invariants. It preserves dead entry owners through opaque aliases and handles
missing aggregates without inventing initialized siblings. Automatic inventory
and ordered condition/body integration remain unfinished; these tests do not
establish the 218 required program outcomes.
[Stage2 parent review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/domain-stage2/PARENT-REVIEW.md).

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
[Corrected draft review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ORDERED-CORRECTION-PARENT-REVIEW.md).
[Correction 2 review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ORDERED-CORRECTION2-PARENT-REVIEW.md).
[Stage3 evidence review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ordered-stage3/PARENT-REVIEW.md).
[Stage4 evidence review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ordered-stage4/PARENT-REVIEW.md).
[Full218 parent review](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/ordered-stage4-full218/PARENT-REVIEW.md).

An independent imported-global pair matches all four semantic/emission outcomes.
Two modules with identical declaration names retain distinct owners; replacing
one module with the saved-owner deletion witness rejects at receiver line 21.
These controls do not qualify general module behavior or native execution.
[Module owner controls](../tmp/v1-completion-2026-10-18/module-owner-controls/REPORT.md).

[Caller validation results](../tmp/v1-completion-2026-10-17/loop-provenance-composition/caller-validation/execution/results.json).
[Domain stage evidence](../tmp/v1-completion-2026-10-17/loop-provenance-composition/revision2/domain-stage1/REPORT.md).

A separate scalar-argument pair matches 2/4 outcomes on revision8. The valid case
captures true before a later argument changes the global to false, then falsely
rejects the returned fresh reference. Revision9 preserves that scalar capture;
its ordinary replay admission rejects a reference CALL actual before using it.
Revision10 passes both sources in both modes after post-capture admission. Keep the case
required alongside the original boundaries; it does not cover callable-slot mutation.
[Scalar snapshot baseline](../tmp/v1-completion-2026-10-18/scalar-call-snapshot-controls/REPORT.md).

A new scalar-reference store pair matches only 2/4 outcomes on revision10.
Writing true through ref bool still falsely rejects the fresh-return path;
writing false rejects the deleted alias. Both currently produce the same errors.
Implement captured referent-location writes and preserve these paired controls.
[Scalar store evidence](../tmp/v1-completion-2026-10-18/scalar-ref-store-controls/REPORT.md).

A controlled exact-budget experiment sets retained_bytes=132. Arrays with 4, 16
and 64 elements emit 3, 15 and 63 resource errors for one initializer; all pass
with the unchanged default budget. Fix repeated reporting while preserving
separate initializer sites and unrelated errors. This does not reproduce the
reported 300,000-element default-budget case. SPEC Appendix C explicitly counts
retained AST cache entries; excluding those values would change the contract.
[Budget diagnosis](../tmp/v1-completion-2026-10-18/exact-budget-diagnosis/REPORT.md).

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
[Reporting candidate evidence](../tmp/v1-completion-2026-10-18/exact-budget-candidate/verification/successor/verification/REPORT.md).
[Integration evidence](../tmp/v1-completion-2026-10-18/exact-budget-candidate/integration/REPORT.md).

The frozen stack-escape probe passes semantic and emission modes despite
publishing a local reference that is read after its frame returns. A live-caller
control also passes. Emitted Zig confirms the stack address escape; no native
execution ran. The [stack-expiration proposal](plan/packets/P-REF-stack-expiration.md)
awaits approval for proven expired-use rejection while preserving active borrows,
heap returns and cleanup before expiration. No rejection has been implemented.
[Stack-escape evidence](../tmp/v1-completion-2026-10-18/stack-escape-reconciliation/REPORT.md).

The [borrowed-deletion proposal](plan/packets/P-REF-deletion-origin.md) awaits a user decision.
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
[Retry evidence](../tmp/v1-completion-2026-10-18/claude-arrays-retry/REPORT.md).

## V1 completion boundary

V1 is not complete. L73 requires core language and automatic memory, useful
libraries and tools, structured concurrency, CPU AI, actual GPU execution and
self-hosting parity before publication. The [delivery roadmap](plan/delivery-roadmap.md)
records the sequence and requirement-specific evidence. Unresolved designs need
approval before dependent changes; L69 already authorizes file-module scopes.

Before the scalar-store and numeric-write changes below, the combined compiler
checkpoint came from frozen source `04c5e959`.
Its full pytest run passed 5,117 tests with one known heap-scalar expected
failure. Native and package evidence appears below. The strict benchmark gate
failed for three missing host pins at that checkpoint. The current 17-workload
suite lacks seven pins. The later example-builder cleanup has
separate verification; these results do not qualify the whole live tree.

The scalar-declaration optimization is integrated from frozen source `3982d76c`.
Its full pytest run passed 5,132 tests with one known scalar-printing expected
failure and the four authorized scanner exclusions. It skips aggregate descendant
scans only for resolved locals with concrete scalar types and initializers.
Paired output and diagnostic checks passed. This removes measured local scans;
no whole-compiler speedup or release-wrapper pass is claimed. The
[qualification record](audits/2026-10-17-scalar-store.md) gives the source and
verification boundaries. Scalar-reference reads remain a pending decision.

Allocation field lookup now checks dotted prefixes from longest to shortest,
avoiding a sort of all registered allocation places. The exact integrated
candidate passed full pytest on frozen source `8bb066b3`: 5,153 passed and one
known strict scalar-printing expected failure, with four authorized scanner
exclusions. Independent review and transfer checks verified all 334 compiler/test
files. The [lookup audit](audits/2026-10-17-field-prefix.md) records the paired
controls and operation counts. No whole-compiler speedup or release-wrapper
pass is claimed.

Further compile-only scaling probes count 1,922 / 7,938 / 32,258 allocation
intersection calls at 32 / 64 / 128 guarded allocations and deletions, with
identical paired Zig output. These are operation counts, not timings. A separate
iterator mismatch in a dead-global summary is confirmed. Follow-up probes find
a separate precision gap: a function that leaves a global live on both branches
can be rejected after one branch deletes an earlier allocation. Materializing
the iterator alone does not repair this loss of branch correlation. No repair
is integrated. The
[roadmap](plan/delivery-roadmap.md) links the probes and follow-up review.

Further lifetime probes found three unsafe field-store/cleanup programs that
pass semantic checking and Zig emission. A callee stores a fresh allocation in
`h.child`, deletes it during deferred cleanup, and the caller reads
`h.child.value` after a nil guard. These require semantic exit 6. No native
program was run. The [ordering probes](../tmp/v1-completion-2026-10-17/global-effect-correlation-design/ordering-probes/REPORT.md)
preserve the inputs and two accepted distinct-allocation controls. The current
suite does not cover these failures; a passing suite cannot close them.
Two [loop-call alias failures](../tmp/v1-completion-2026-10-17/loop-call-alias-diagnosis/REPORT.md)
also accept after deletion. The loop summary discards fresh call allocations
and leaves saved aliases without identity or death state. Paired fresh and
distinct-allocation controls accept, while a direct-allocation stale alias
rejects. These failures remain open; neither repair is integrated.
An independent [nested-call witness](../tmp/v1-completion-2026-10-17/global-condition-verification/ordered-candidate-review.md)
also accepts when a global reference selects between two holders and a nested
callee stores then deletes a child. The caller's guarded child reads require
rejection. Both baseline and the initial ordered-replay candidate accept it.
Resolving only singleton destinations does not cover this case.
Later isolated revisions reject this represented-destination witness and retain
fresh-overwrite controls. They remain unqualified: the
[revision13 checks](../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/revision13/REPORT.md)
meet 72/82 exit requirements. Unknown-destination deletion still passes semantic
checking. Skipped lifetime branches also lack a lowering contract, so two valid
controls pass semantics but fail Zig emission with exit 7. Neither failure can
be closed by approving dereferences in an unvisited body.
A [selected-field cache witness](../tmp/v1-completion-2026-10-17/selected-field-cache-controls/REPORT.md)
also remains unsafe: reading `g.child` before a deleting call makes the later
guarded read pass in revision13. Removing only the earlier read restores the
required rejection. Both fresh-overwrite controls remain accepted. The live
compiler also accepts the cached negative. Current field reads and replay
stores must share allocation-based storage identities.
An [aggregate replacement probe](../tmp/v1-completion-2026-10-17/aggregate-field-controls/REPORT.md)
blocks isolated revision14: replacing an inline record leaves its old child
facts behind. It accepts a deleted replacement and rejects a live replacement.
Revision13 meets both controls. The repair must update guarded descendant
cells while preserving saved aliases; revision14 is not integrated.
The [expanded aggregate controls](../tmp/v1-completion-2026-10-17/aggregate-successor-controls/REPORT.md)
confirm failures in copies, self-copies and two-holder selection. Revision14
meets only six of 24 strict outcomes. Four additional matching exits carry
false diagnostics. A separate sixteen-input extension meets ten of 32 strict
outcomes and exposes unselected-holder and selected-self-copy failures. An
isolated successor has now been probed.
[Revision15](../tmp/v1-completion-2026-10-17/ordered-successor-controls/REPORT.md)
meets all 32 strict aggregate checks and 98/106 earlier ordered-call outcomes.
The tested cached and unknown-destination pairs now behave correctly. Two loop
negatives and a three-way formal/global alias negative still accept, while two
valid controls fail lowering. Fixed-array replacement also behaves correctly,
but the frozen negative test's line-only expectation needs correction to admit
the earlier stale-array read. Nothing from revision15 is integrated.
A [one-formal replay witness](../tmp/v1-completion-2026-10-17/replay-entry-coverage-controls/REPORT.md)
reduces the alias failure: leaving g nullable accepts the deleted child, while
binding g to h before the guarded call restores rejection. Both fresh controls
accept. A [parity-checked replay trace](../tmp/v1-completion-2026-10-17/global-effect-correlation-candidate/replay-entry-observer/execution/REPORT.md)
confirms the cause: the caller excludes g's nil entry alternative, but replay
starts with every region active and aborts for missing destination coverage.
All four observed outputs match their uninstrumented counterparts. An isolated
successor now carries the caller region explicitly. Isolated revision16 meets
182/194 required outcomes. Its four replay traces preserve baseline output and
confirm matching caller, replay and destination regions. Loop and lowering
failures remain. A separate [focused regression run](../tmp/v1-completion-2026-10-17/revision16-focused-pytest/REPORT.md)
passed 182 tests and failed six. It also found a valid deferred fresh-rebinding
case rejected by both revisions15 and16, plus an obsolete diagnostic-message
expectation whose program correctly rejects. Neither candidate is integrated.
The [deferred-write trace](../tmp/v1-completion-2026-10-17/replay-active-fact-observer/execution/ROOT-REPORT.md)
confirms that replay checks a nullable alternative excluded by the active branch.
The bounded repair must restrict evaluated facts while preserving stored
alternatives and reachable deaths. Isolated revision17 applies that correction.
Its [focused checks](../tmp/v1-completion-2026-10-17/revision17-focused-pytest/REPORT.md)
pass 190 tests and fail four known loop/lowering tests. This fixes the original
deferred-write test and preserves the new negative controls. The
[broader batch](../tmp/v1-completion-2026-10-17/active-fact-successor-controls/REPORT.md)
meets 194/206 required outcomes. Seven loop/lowering inputs still fail, and a
nil-rebinding negative carries an extra caller diagnostic. Neither revision17
nor its predecessors are integrated.
The separate [region-aware loop candidate](../tmp/v1-completion-2026-10-17/loop-composed2-controls/REPORT.md)
meets 38/44 targeted outcomes. Tested stale aliases now reject and older live
aliases remain accepted, but three valid zero-trip cases falsely reject.
One regresses from revision17 when a condition call makes the loop false.
That candidate is also isolated and unqualified.
Its [composed3 successor](../tmp/v1-completion-2026-10-17/loop-composed3-controls/REPORT.md)
meets51/60 targeted outcomes, including40/44 inherited outcomes. Zero-trip
semantic checks improve but still fail lowering. Scalar-call positives still
reject. A paired trace confirms missing parameter-node type metadata prevents
the new scalar helper from reaching the store; the resolved call signature
has the required type. The
[composed4 correction](../tmp/v1-completion-2026-10-17/loop-composed4-controls/REPORT.md)
meets54/60 outcomes: all30 semantic checks pass, while six valid sources still
fail code generation. Additional
[scalar boundary checks](../tmp/v1-completion-2026-10-17/scalar-call-boundary-execution/REPORT.md)
meet10/16 outcomes; repeated-condition and cleanup positives still reject.
The [recurrent trace](../tmp/v1-completion-2026-10-17/recurrent-scalar-observer/REPORT.md)
shows the first call publishing i=1, then the loop-head join dropping it. The
second call becomes unknown and complete exit projection publishes an
impossible deletion. Separate initial and recurrent analysis without a trip cap.
The [full composed4 inventory](../tmp/v1-completion-2026-10-17/loop-composed4-full-inventory/REPORT.md)
records 315/328 raw matches, or 317/328 after correcting one duplicated nil-case
oracle in both modes. Eleven compile failures span eight distinct sources;
two regress from valid compilation on revision17. The 164 records contain
124 distinct sources. Repeated-condition and cleanup boundary failures remain
outside this inventory. [Composed5 checks](../tmp/v1-completion-2026-10-17/loop-composed5-controls/REPORT.md)
match 67/80 outcomes. The repeated-condition positive now passes semantics
but fails code generation. Nine compile failures and both cleanup and
three-phase semantic failures remain. All 44 negative mode rows match exact
diagnostic contracts. Production integration remains incomplete.
The [scalar phase observations](../tmp/v1-completion-2026-10-17/scalar-domain-observer/REPORT.md)
confirm actual backedges i=1 and i=2 join to unknown. Cleanup is refused at
DEFER validation before scalar stores run. Preserve correlated scalar and
allocation alternatives, then implement existing lexical cleanup and return
capture order. These successor mechanisms remain unimplemented.
New [cleanup baseline controls](../tmp/v1-completion-2026-10-17/scalar-cleanup-baseline/REPORT.md)
match 4/8 outcomes. A true return captured before deferred mutation is accepted
in both modes despite a reachable stale read; emitted Zig retains that read.
Repair this unsafe acceptance before treating cleanup as a precision-only gap.
The LIFO-disables positive still rejects. No native execution occurred.
The [return-capture trace](../tmp/v1-completion-2026-10-17/return-capture-observer/REPORT.md)
shows fallback exit restoration clearing saved allocation3 and its death,
then retaining only the deleted global slot. An incomplete empty-origin saved
reference becomes non-nil and passes the read. Preserve guarded exit values
and allocation deaths through fallback; nil refinement alone cannot prove
liveness. This repair must cover zero-trip and deferred break exits too.
Independent [fallback controls](../tmp/v1-completion-2026-10-17/loop-fallback-baseline/REPORT.md)
match 6/14 outcomes: ordinary, nested-cleanup and labeled-cleanup stale aliases
are accepted; the zero-trip positive rejects. Fresh replacement and distinct
allocations pass. Retain all seven programs as strict repair requirements.
The guarded containing-cell successor fails two direct
[internal probes](../tmp/v1-completion-2026-10-17/contained-transport-probes/REPORT.md):
forgetting erases possible death, and reachability omits canonical-owner child
contents. Source review also found sparse replay and copy-coverage gaps.
Correct these before broader compiler checks. No pipeline or pytest run has
qualified the candidate; all 1725 source hashes/modes remain pinned.
Neither isolated candidate is qualified.
The separate [lowering revision3 checks](../tmp/v1-completion-2026-10-17/lowering3-focused-pytest/REPORT.md)
pass137 tests, including both original skipped-arm codegen failures. Two
inherited unsafe loop acceptances still fail. Its
[initialized native preflight](../tmp/v1-completion-2026-10-17/lowering3-native-preflight/REPORT.md)
passes six of12 compile checks; two sources fail across all three profiles.
The [inherited comparison](../tmp/v1-completion-2026-10-17/lowering3-inherited-controls/REPORT.md)
meets196/206 outcomes; five loop inputs still fail. Six separate
[native effect-order/use tests](../tmp/v1-completion-2026-10-17/lowering3-native-effects-usage/REPORT.md)
pass across three profiles. Initialized allocation examples remain unqualified.
[Minimized effect probes](../tmp/v1-completion-2026-10-17/lowering-native-effect-probes/REPORT.md)
also expose an unsafe semantic acceptance behind nested initialization guards.
The [legacy-effect traces](../tmp/v1-completion-2026-10-17/lowering-native-effect-observer-revision2/REPORT.md)
confirm that child deletion marks the holder dead while leaving a saved child
alias live. They also show a call preserving a stale complete nil child fact,
which skips a reachable branch. Repair allocation-specific deaths and field
invalidation before granting further branch-omission authority.
The candidate remains isolated.
The [caller-region shape controls](../tmp/v1-completion-2026-10-17/replay-region-controls/REPORT.md)
repeat the failure after early return and nested IF analysis; a guard inside
an exact callee rejects correctly. [State-boundary controls](../tmp/v1-completion-2026-10-17/replay-state-boundary-controls/REPORT.md)
also preserve failing deferred-call, nested-declaration and unrelated-nullable
cases, each with an accepted fresh twin. Carry explicit feasible region state
through these boundaries without deriving it from arbitrary reference facts.
The [composed loop audit](../tmp/v1-completion-2026-10-17/global-condition-verification/loop-composed-revision1-execution-review.md)
meets 175/188 command outcomes across 94 grouped inputs. Unknown-destination,
loop lifetime and lowering failures remain. These counts include duplicated
input groups and do not qualify the candidate.

Numeric reference writes now use existing contextual fitting. Guarded
`ref usize` assignments accept `3`, named exact constants and `3.0`.
Out-of-range constants and incompatible typed values remain semantic errors;
typed mismatches now report `assignment_type_mismatch`. The isolated repair
passed 21 focused and 180 related nonnative tests. Candidate and typed baseline
produced six exact native outputs across three Zig optimization modes from one
A7 lowering each. Those results predate the scalar-store integration; combined
qualification passed on frozen 1,721-file source `9d2384c4`: 5,153 passed and
one known scalar-printing expected failure, with the four authorized scanner
exclusions. Owner 80409 exited 0 after 818.22 seconds. This is full pytest,
not a complete release-wrapper result. Later Goose research is outside that
snapshot. The
[repair evidence](../tmp/v1-completion-2026-10-16/ref-scalar-literal-write-review/REVISION4-REPORT.md)
and [native review](../tmp/v1-completion-2026-10-16/ref-scalar-literal-write-review/revision4-native-controls/ACTUAL-INDEPENDENT-REVIEW.md)
record the scope. L47 and existing reference writes authorize this correction;
it does not implement the scalar-read proposal.


The earlier integrated compiler checkpoint was frozen source `de578138`.
It adds local Boolean guard facts and indexed-use diagnostics. Permitted full
pytest passed 4,442 tests with one expected failure; four scanner tests were
excluded under the user's instruction. The scoped native qualification covers
32 logical steps across an original run and three corrected diagnostic retries.
The original diagnostic expectation failure remains recorded.

Nine direct compiler/package checks are covered by four original successes and
five successful retries after write-quota failures. These are combined results,
not a single uninterrupted gate pass. The
[integration verification](../tmp/v1-completion-2026-10-07/ref-array-local-diagnostic-integration/independent-verification.json)
records the qualified source, native results, retries and live integration.
A source comparison verified all 388 compiler, test, script, example and selected
root-file paths before the later example update. Example 014 now includes
`where T: Integer` calls with signed and unsigned arguments. Its updated golden
output passed all three native profiles and the full 51-example E2E run.
The [example verification](audits/2026-10-08-generics-example.md) records that
overlay separately. Later example and documentation edits are outside the
earlier full pytest qualification scope.
Examples 016 and 018 also add scalar payload bindings and a local file import.
Both passed three native profiles, followed by a combined 51-example E2E pass.
The [payload/module record](audits/2026-10-08-payload-module-examples.md) keeps
their source and verification scope separate from compiler qualification.
The [L67 benchmark promotion](audits/2026-10-08-l67-promotion.md) adds three
unchanged workloads after nine native correctness runs. Their host timing pins
remain unset; the expanded performance gate rejects the incomplete pin.
This establishes output correctness, not memory-reclamation or L38 performance.

The [October 8 site check](../tmp/v1-completion-2026-10-08/site-checkpoint/REPORT.md)
passed all seven checks and all 12 tests, including preview socket binding.
All 554 inventoried site source entries remained unchanged. The earlier preview
`EPERM` failure remains in its historical record. Browser rendering, publication
and V1 release acceptance remain unverified.
The October 16 site check failed when preview socket binding returned `EPERM`.
Lint, type checking, coverage and 11 publication tests passed. Separate build,
export and link checks passed. The [integration report](../tmp/repo-simplification-2026-10-16/live-integration/REPORT.md)
records this current limit. Cyber, secrets and dependency-vulnerability scans
remain excluded.

The earlier reference-array indexing integration was qualified on frozen source
`b26d502a`: 4,194 tests passed with one expected failure, plus 12 valid native
controls. Nine direct compiler/package checks are covered by four original
successes and five successful recovery checks. The quota-failed run and its
streams remain part of the evidence; the recovery does not replace that run.

Two later overlays have separate evidence. The source docstring overlay changes
only Python `__doc__` metadata; the remaining AST is identical. Diagnostic source
`95dfa299` adds available callee filenames to secondary notes and preserves
primary caller locations. It passed 630 focused nonnative tests and independent
review with 24 compile observations. No new native or full-suite qualification
is claimed for that diagnostic source.

The earlier `158a8423` checkpoint passed 4,124 tests with one expected failure,
12 native else-if controls and nine direct compiler/package checks. The
[prerequisite record](audits/2026-10-07/stdlib-source-loader-prerequisites.json)
retains the source and integration history. Site build, exports and links pass.
That checkpoint's preview test failed with `EPERM`. Later site results are
recorded above.
Cyber, secrets and dependency-vulnerability scans were excluded by the user.
These checkpoints are not a full release-gate pass or V1 acceptance.

The registered-stdio checkpoint matched the compiler and tests in frozen
source manifest `e0c6235a`. Its full release gate passed 3,933 tests with one
expected failure and all 11 compiler/package checks. All 51 examples passed
E2E and artifact checks in each profile. Package installation and site checks
passed. All 1,625 frozen file hashes and modes stayed unchanged. The
[stdio verification record](audits/2026-10-07/stdio-integration-verification.json)
separates source qualification from the later documentation edits and native
controls. The [readonly verification record](audits/2026-10-07/readonly-v3-verification.json)
records the earlier 3,896-test checkpoint. The
[October 7 qualification history](audits/2026-10-07/qualification.md) preserves
earlier checkpoints, failed runs and their recoveries. V1 remains incomplete.

GPU execution is deferred under L75. The
[Zig GPU research](research/2026-10-07-zig-gpu-support.md) separates installed
0.16, stable 0.17 and development support, host APIs and compile-only results.
It does not qualify device execution. L73's GPU publication requirement stays open.

The [published documentation checkpoint](audits/2026-10-07/published-docs-verification.json)
passed 16 HTTP content comparisons against the frozen build. Browser interaction
and responsive rendering remain unverified because no browser connection was
available. This does not satisfy final publication acceptance.

## Current Surface

An earlier loop-analysis false rejection affected a reference declared outside a
loop, deleted and replaced by a nil-checked fresh allocation on every iteration.
The [reduced witness](../tmp/v1-completion-2026-10-07/l67-cache-loop-repro/REPORT.md)
received semantic exit 6 despite having no surviving aliases. Straight-line
replacement and iteration-local allocation controls pass. The repair must keep
rejecting reads through aliases to deleted old allocations.
The now-integrated combined source `04c5e959` accepts the unchanged cache workload
in semantic and compile modes, along with the copy, text and ID-cycle candidates.
The [October 16 prechecks](../tmp/v1-completion-2026-10-16/l67-combined-prechecks/REPORT.md)
record eight successful compiler checks and four emitted Zig files. The later
[independent native audit](../tmp/v1-completion-2026-10-16/l67-native-independent-review/REPORT.md)
verified all 24 full-count outputs across Debug, ReleaseSafe and ReleaseFast
with two input seeds. Owner session 47687 exited 0. Optimized work retention,
allocation-failure paths, memory costs and L38 performance remain unqualified.
The text and ID-cycle inputs remain proxies for the required lifetime cases.
A separate [conditional replacement witness](../tmp/v1-completion-2026-10-07/conditional-replacement-repro/REPORT.md)
shows the same false rejection without a loop: one branch replaces a deleted
reference, the other preserves it, and the guarded read after the branch fails.
Both missing-replacement and saved-old-alias controls must continue to reject.
The isolated conditional candidate `e59c78fa` passed its full permitted pytest
selection: 4,514 passed and one existing xfail. Its source and output hashes were
[rechecked by the parent](../tmp/v1-completion-2026-10-07/conditional-replacement-parent/full-pytest-verification.json).
This candidate is not integrated. Its five positive native controls passed in
Debug, ReleaseSafe and ReleaseFast: [15 exact-output runs](../tmp/v1-completion-2026-10-07/conditional-replacement-parent/native-verification.json),
with empty stderr. These controls do not qualify the array successor.

A separate [fixed-array alias review](../tmp/v1-completion-2026-10-07/conditional-replacement-independent-review/REPORT.md)
reproduces an incorrect acceptance across a conditional. In the
[exact input](../tmp/v1-completion-2026-10-07/conditional-replacement-independent-review/inputs/array_pair_dead.a7),
`if a { xs[1] = xs[0] }` can make two literal-index slots share an allocation.
After `del xs[0]`, reading through `xs[1]` must reject with semantic exit 6.
Both frozen loop baseline `e2a777d0` and conditional candidate `e59c78fa` instead
exit 0 in semantic and compile modes. The valid distinct-slot swap remains
accepted. No native execution occurred. This pre-existing gap prevents a full
alias-safety claim and remains a compiler correctness requirement.
The isolated joined-slot repair `88b9246b` passed 4,533 permitted pytest cases
with one existing xfail. The [recovery verification](../tmp/v1-completion-2026-10-08/conditional-array-parent/full-verification.json)
pins its 1,687 source files and test streams. The earlier interrupted run remains
in the evidence record. This candidate is not integrated.
Its five positive native controls passed in three profiles, with 15 exact outputs
and empty stderr. [Independent evidence verification](../tmp/v1-completion-2026-10-08/conditional-array-parent/native-verification.md)
checked 112 streams and 30 artifacts. Four negative controls reject in both
compiler modes with exit 6; none was executed natively.
The isolated joined-slot repair also leaves raw nested-array initializer
references untracked. Explicit leaf assignments in its controls do not repair
that initializer route. The [report correction](../tmp/v1-completion-2026-10-07/conditional-array-alias-candidate/REPORT-ERRATUM.md)
identifies the original accepting test output.
The nested-initializer candidate `ece1d6f3` is held after
[independent review](../tmp/v1-completion-2026-10-08/nested-array-initializer-independent-review/REPORT.md)
found a valid dynamic-index field overwrite changing from exit 0 to exit 6.
It retains an obsolete field identity after an unknown write. Its focused
passing tests do not override that regression; the candidate is not integrated.
Its successor `6f33478f` is also held: an unknown-index write to an unrelated
integer field discards the reference-field identity and lets a deleted-alias
read pass. The [V2 review](../tmp/v1-completion-2026-10-08/nested-array-v2-independent-review/REPORT.md)
requires invalidating only fields that the write can modify.
V3 `dd327bda` passed [bounded independent review](../tmp/v1-completion-2026-10-08/nested-array-v3-independent-review/REPORT.md).
It preserves sibling reference identities during uncertain-index scalar writes.
Its full permitted pytest run passed 4,582 tests with one existing xfail.
[Parent verification](../tmp/v1-completion-2026-10-08/nested-array-v3-parent/full-pytest-verification.json)
rechecked all 1,688 source files and output streams. Its five bounded native
programs passed in three profiles, with 15 exact outputs and empty stderr.
[Independent native verification](../tmp/v1-completion-2026-10-08/nested-array-v3-parent/native-independent-verification.md)
checked 136 streams, 35 artifacts and ten compiler-only negative checks.
Integration and required GLM review remain pending.
The [V3 GLM invocation](../tmp/v1-completion-2026-10-08/glm-nested-v3-review/run.json)
exited 1 before review because OpenCode could not open its normal log on the
read-only filesystem. HOME was unchanged; no completed review is claimed.
Known dynamic-index and loop-field incorrect acceptances remain.
A [singleton-index analysis](../tmp/v1-completion-2026-10-08/dynamic-field-alias-analysis/REPORT.md)
shows four incorrect acceptances even where current scalar facts prove one
array cell. The proposed correction uses those current facts for exact-cell
tracking; genuinely uncertain selection still needs a separate alias design.
The isolated [singleton candidate](../tmp/v1-completion-2026-10-08/singleton-index-alias-candidate/REPORT.md)
`e87b5861` passed 660 nonnative tests. Its [independent review](../tmp/v1-completion-2026-10-08/singleton-index-alias-independent-review/REPORT.md)
recommends bounded full/native qualification. The one changed
existing acceptance assertion reads deleted p when its branch is false; its
source is unchanged and the expected semantic exit is now 6 under L74.
A [saved-slot loop analysis](../tmp/v1-completion-2026-10-08/saved-slot-loop-analysis/REPORT.md)
also reproduces three deleted-allocation reads that pass when the alias came
from `xs[0]`, while equivalent `r := p` aliases reject. Loop invalidation erases
the copied scalar identity along with mutable array cells. Preserve that scalar
identity while keeping valid distinct-allocation and fresh-reassignment controls.
The isolated [saved-slot V2 candidate](../tmp/v1-completion-2026-10-08/saved-slot-loop-v2/REPORT.md)
passed 165 final-source tests and 118 semantic/compile outcomes. Both valid
regressions from its first draft now pass. [Independent review](../tmp/v1-completion-2026-10-08/saved-slot-loop-v2-independent-review/REPORT.md)
holds the repair for two more valid rejections: a shadowed false-condition loop
and a Boolean mutated before both correlated tests. Preserve their expected
acceptance in the next correction. Its parent also retains the rejected V2
field-invalidation behavior, so eventual combination and qualification remain
required before integration. The isolated [saved-slot V3 successor](../tmp/v1-completion-2026-10-08/saved-slot-loop-v3/REPORT.md)
`fadec97c` passed 704 nonnative tests and all 154 compiler replay outcomes.
It fixes both V2 rejections, but [V3 review](../tmp/v1-completion-2026-10-08/saved-slot-loop-v3-independent-review/REPORT.md)
found two further valid rejections and one semantic-only capture regression.
The [isolated combination](../tmp/v1-completion-2026-10-08/reference-alias-combined/REPORT.md)
`9b92385e` passed 737 nonnative tests and 12 compiler interaction outcomes.
It is held for further saved-slot regressions: copied flags before their first
test and false-entry loops. A read-only capture also regresses semantically;
its predecessor already failed compile mode. Neither successor nor the
combination has a full or native qualification result.
The [second combination](../tmp/v1-completion-2026-10-08/reference-alias-combined-v2/REPORT.md)
`ae73087c` restores those controls and passes 748 nonnative tests with 42
deselections. The parent [source verification](../tmp/v1-completion-2026-10-09/reference-alias-combined-v2-parent/source-verification.json)
checks all 1,690 source hashes and modes, the two-file delta and test streams.
Read-only capture remains semantic 0 and compile 7. The [independent review](../tmp/v1-completion-2026-10-09/reference-alias-combined-v2-independent-review/REPORT.md)
recommends full/native qualification after 260 commands and 520 verified streams.
The [permitted full pytest run](../tmp/v1-completion-2026-10-09/reference-alias-combined-v2-parent/full-pytest-verification.json)
passed 4,695 tests with one existing xfail. All 1,690 source hashes and modes
were rechecked. Twenty-two compiler prechecks for seven native positives and
four negatives pass on this exact source. Its [native verification](../tmp/v1-completion-2026-10-09/reference-alias-combined-v2-parent/native-verification.json)
confirms 21 exact outputs across three profiles, 176 streams and 49 artifacts.
These results apply to the seven initialized controls on `ae73087c`.
Integration remains incomplete. Valid stable-continue and uncalled
mutator-capture controls reject on parent `9b92385e` and candidate `ae73087c`.
A separate [cleanup diagnosis](../tmp/v1-completion-2026-10-08/conditional-cleanup-analysis/REPORT.md)
reproduces valid complementary deletion and saved-alias reads rejected on both
the earlier compiler and the combination. An unconditional moved-slot mark
overrides the remembered allocation path. Repair branch feasibility while
retaining rejection of same-path and changed-flag repeated deletion.
The first cleanup draft's broader run passed 693 tests and failed three existing
fresh-factory acceptance controls. Its [failure record](../tmp/v1-completion-2026-10-09/conditional-cleanup-parent/first-broad-failure.json)
remains preserved. The [frozen correction](../tmp/v1-completion-2026-10-09/conditional-cleanup-parent/frozen-source-verification.json)
`09c95046` passes 715 nonnative tests with 34 deselections. All 1,691 source
hashes and modes match the run's before/after snapshots. The [paired replay](../tmp/v1-completion-2026-10-09/conditional-cleanup-parent/replay-verification.json)
checks 42 inputs on both sources in both modes. All 84 candidate outcomes match
requirements, including the four original complementary-cleanup controls.
The [independent cleanup review](../tmp/v1-completion-2026-10-09/conditional-cleanup-independent-review/REPORT.md)
recommends qualification of an isolated combination after 44 matching candidate
outcomes. The [combined snapshot verification](../tmp/v1-completion-2026-10-09/reference-alias-cleanup-parent/review-broad-verification.json)
records 738 nonnative passes and an independent review with 16 matching candidate
outcomes. Source `008e8419` contains 1,692 files. Its permitted full pytest run
passed 4,749 tests with one existing xfail in 882.62 seconds. The four secret-scan
tests were excluded. Eleven positive native inputs, including the four original
cleanup forms, pass compiler prechecks alongside four negative controls.
[Native verification](../tmp/v1-completion-2026-10-09/reference-alias-cleanup-parent/native-verification.json)
confirms all 33 outputs across three profiles, 264 streams and 77 artifacts.
Live integration remains incomplete.
The [stable-continue diagnosis](../tmp/v1-completion-2026-10-09/stable-continue-analysis/REPORT.md)
traces a separate valid rejection to an infeasible backedge after an inevitable
first-iteration break. Existing numeric loop-header proofs do not cover this
Boolean-header loop. Preserve actual repeat and mutation rejections when repairing
statement-local reachability; conditional cleanup alone does not close it.
The [isolated reachability candidate](../tmp/v1-completion-2026-10-09/stable-continue-parent/source-broad-verification.json)
`91579223` passes 738 nonnative tests with 17 deselections. Parent verification
checks its 1,693 current files and the final run's two changed-file hashes.
Its final replay matches all 64 outcomes. The [independent review](../tmp/v1-completion-2026-10-09/stable-continue-independent-review/REPORT.md)
recommends bounded full/native qualification. A valid two-trip deferred-counter
case still rejects on both snapshots; its expected acceptance remains recorded.
The [acceptance-boundary review](../tmp/v1-completion-2026-10-09/loop-proof-acceptance-boundary/REPORT.md)
keeps that requirement open. The uncalled-mutator capture fixture separately
expects semantic exit 0 and compile exit 7; its earlier observed exits are 6/6.
These inherited limits do not close with first-backedge qualification.
Its [permitted full pytest verification](../tmp/v1-completion-2026-10-09/stable-continue-parent/full-pytest-verification.json)
records 4,781 passed and one existing xfail in 763.31 seconds, with the four
secret-scan tests excluded. All 1,693 source hashes and modes were rechecked.
[Native verification](../tmp/v1-completion-2026-10-09/stable-continue-parent/native-verification.json)
confirms 39 exact outputs for thirteen positives across three profiles and twelve
compiler-only negative checks. All 316 streams and 91 artifacts were rechecked.
[Remaining-gate verification](../tmp/v1-completion-2026-10-09/stable-continue-parent/remaining-gates-verification.json)
records nine permitted compiler/package checks passed, including wheel and
source-distribution installation. The separate performance gate failed because
`mem_shared`, `mem_returned` and `mem_cleanup` lack timing/hash baselines.
[Example verification](../tmp/v1-completion-2026-10-09/stable-continue-parent/examples-e2e-verification.json)
confirms all 51 example names and their compile, build, run and normalized
output-comparison outcomes. Debug, ReleaseSafe and
[ReleaseFast](../tmp/v1-completion-2026-10-09/stable-continue-parent/fast-artifact-verification.json)
artifact profiles each passed all 51 examples; parent verification records
102 generated files per profile. The report-only benchmark ran thirteen
workloads but compared only ten pins; it does not close the failed gate.
The separate [site run](../tmp/v1-completion-2026-10-09/stable-site-readiness/execution/results.json)
failed at preview socket creation with `EPERM`. Lint, type checking, coverage
and eleven publishing tests passed. The preview test failed, stopping that run.
A [separate static run](../tmp/v1-completion-2026-10-09/stable-site-downstream/execution/results.json)
built 23 pages, verified current exports and checked 1,506 local resources plus
183 search targets. It does not close the failed preview test. Existing installed
dependencies were copied without installation for both runs.
The candidate is not integrated.

Two further repairs remain isolated from that qualified source. The
[two-trip candidate](../tmp/v1-completion-2026-10-09/two-trip-proof-candidate/REPORT.md)
`342d150b` passes 757 nonnative tests and 38 compiler outcomes. Independent
review of its final source supports combined qualification.
The [captured-Boolean successor](../tmp/v1-completion-2026-10-09/uncalled-capture-proof-candidate/revision3/REPORT.md)
`e4497b17` matches 54 compiler outcomes and passes its 27-test file.
[Parent verification](../tmp/v1-completion-2026-10-09/uncalled-capture-proof-candidate/revision3/parent-replay-verification.json)
checks all 1,694 source files, 112 replay streams and exact input/mode coverage.
Its unchanged compiler passed 764 broader tests on the preceding snapshot;
one new test asserted the wrong diagnostic. The final snapshot corrects that
assertion. These separate runs do not establish a clean full-suite result.
Valid captures retain compile exit 7 because closure lowering remains absent.
Independent reviews of both repairs support combined qualification. They retain
two valid false rejections: an unknown Boolean prefix whose branches both exit
the second loop trip, and a saved noop callable whose source variable is later
rebound. Both remain open requirements. The [combined source](../tmp/v1-completion-2026-10-09/two-trip-capture-combined/REPORT.md)
`9ada6e28` passes 784 nonnative tests with 17 deselections and all twenty
supported interaction outcomes. [Independent combined review](../tmp/v1-completion-2026-10-09/two-trip-capture-independent-review/REPORT.md)
verified 72 commands and 144 streams without finding a new merge regression.
[Full pytest verification](../tmp/v1-completion-2026-10-09/two-trip-capture-full-pytest/parent-verification.json)
records 4,827 passed and one existing xfail in 696.08 seconds, with the four
secret-scan exclusions. All 1,695 source files and six streams were rechecked.
[Native verification](../tmp/v1-completion-2026-10-09/two-trip-capture-native/parent-verification.json)
confirms 42 exact outputs across three profiles and sixteen negative compiler
checks. All 1,695 source files, 346 streams and 98 artifacts were rechecked.
Integration remains incomplete.
Neither inherited valid rejection is counted as passing.

Two separate successors address those rejections. The
[terminal-prefix repair](../tmp/v1-completion-2026-10-09/terminal-prefix-branch-candidate/REPORT.md)
`89578873` passes 802 targeted tests and all 36 bounded compiler outcomes.
Independent review supports further qualification. Its initialized native inputs
pass compiler prechecks; they have not been executed.
The [saved-callable repair](../tmp/v1-completion-2026-10-09/saved-callable-copy-candidate/revision2/REPORT.md)
`7c6fa0af` passes 825 targeted tests and all 64 compiler outcomes. Final independent
review supports bounded combination. Neither successor is integrated.
Their combined snapshot `2a699e77` fails its
[interaction replay](../tmp/v1-completion-2026-10-09/terminal-callable-combined/interaction-verification.json):
two valid saved-noop call interactions and the inherited correlated-counter loop
still exit 6 in both modes. The replay records sixty commands and no prerequisite
failures. Broad qualification is held while these acceptance requirements remain
unmet. The isolated [counter repair](../tmp/v1-completion-2026-10-09/correlated-counter-candidate/REPORT.md)
`be024793` passes 857 targeted tests and 46 required compiler outcomes. Its
guarded-value proof accepts the correlated-counter examples. Parent verification
rehashed all 1,698 source files and 208 replay streams.
[Independent implementation review](../tmp/v1-completion-2026-10-10/counter-implementation-review/REPORT.md)
found no blocker and verified 22 matching compiler outcomes across 48 commands.
Both saved-noop call cases still reject in both modes.
The [call-retention review](../tmp/v1-completion-2026-10-09/call-scalar-design-review/REPORT.md)
supports retaining inaccessible local counters across ordinary calls. The isolated
call-retention successor is frozen at `0374758a`. Its nineteen focused tests and
38 recorded compiler outcomes pass, including the two original saved-noop cases.
The broader regression selection passes 876 tests with 17 deselections.
[Independent execution review](../tmp/v1-completion-2026-10-10/call-scalar-independent-review/REPORT.md)
supports bounded full qualification: 22 of 26 required outcomes match, with
the four outcomes below still unmet. Full pytest passed 4,919 tests with one
existing xfail on the frozen source. [Parent verification](../tmp/v1-completion-2026-10-10/call-scalar-full-pytest/parent-terminal-verification.json)
rehashed 1,699 source files, six streams and five tools after terminal exit 0.
[Independent full-run audit](../tmp/v1-completion-2026-10-10/call-scalar-full-pytest/independent-review/REPORT.md)
confirmed the counts and four authorized exclusions. The remaining expected
failure is `heap_scalar_write_through`; scalar reference output remains an
unmet requirement. The [October 16 research](plan/research/scalar-reference-reads-2026-10-16.md)
revises the scalar-read proposal after 12 compile-only probes. No scalar-read
behavior change or native acceptance is claimed.
[Native qualification](../tmp/v1-completion-2026-10-10/call-scalar-native/parent-terminal-verification.json)
passed all 54 exact runtime outputs across Debug, ReleaseSafe and ReleaseFast,
plus 36 semantic/compile rejection checks. Parent verification rehashed 474
streams and 126 artifacts after terminal exit 0. This source remains isolated.
On `0374758a`, two runtime-valid controls still reject: a borrowed but unmodified counter and
a counter followed by a standard-library print. Their acceptance requirements
remain open in [the candidate evidence](../tmp/v1-completion-2026-10-10/call-scalar-candidate/open-requirements.json);
the exit-6 compatibility assertions do not establish valid-program acceptance.
Later isolated repairs address borrowed-counter and reference-slot precision.
The [reference-slot candidate](../tmp/v1-completion-2026-10-10/reference-slot-candidate/REPORT.md)
`31135c8e` passed 927 bounded regression tests. Its independent replay matched
54 of 56 outcomes; readonly returned references and the author's separate
alias-overwrite requirement remained open. Three accepted initialized programs
passed [nine native output checks](../tmp/v1-completion-2026-10-10/borrowed-slot-native/REPORT.md)
across Debug, ReleaseSafe and ReleaseFast.
The [graph successor source review](../tmp/v1-completion-2026-10-10/borrowed-counter-implementation-review/graph-revision2-source-review.md)
cleared `addbf488` for bounded tests. All 61 focused tests and 122 paired-replay
outcomes pass, including those valid gaps and LIFO cleanup controls. The broader
selection passed 937 tests with seventeen deselections. Independent replay
matched all 74 candidate outcomes and eighty unsafe diagnostic-site checks.
The stdlib retention repair is merged in isolated `8adf421e`. Its 87 focused
tests, all 140 paired-replay outcomes and 944 broader tests pass. The broader
selection deselected seventeen tests. Independent combined replay matches all
94 candidate outcomes and one hundred negative-site checks across both sources.
Map traces confirm retained valid facts and no restoration after nested mutation.
Full pytest passed 4,987 tests with one strict scalar-read expected failure,
which remains unmet. Independent review verified that result. Native
qualification stopped before building: initialized `returned_readonly` still
rejects at its loop deletion despite requiring acceptance. All 52 unsafe-site
checks passed, but no native program ran. No candidate is integrated into the
live compiler; none of these bounded results establishes V1 completion.
Follow-up diagnosis reproduces four initialized valid failures: readonly return,
overwritten alias, LIFO cleanup and nested readonly return. Primitive field
initialization forces their owners into conservative fallback analysis.
The isolated [primitive-place repair](../tmp/v1-completion-2026-10-10/primitive-place-candidate/REPORT.md)
is frozen as `9df00ac7`. Its prerequisite run accepts all nine initialized
programs in both modes, including the four original failures. A distinct local
stack-array store still falsely rejects: its all-roots write effect erases an
unrelated counter proof. Three negative fixtures have bounds, nil or immutable
target errors, so they do not qualify the intended lifetime checks. The run
matches twenty of twenty-eight compiler requirements. Broader and native gates
have not run on this repair; storage-origin precision remains unresolved.
Independent refinement isolates three valid failures without other diagnostics:
local array storage, a local field with an RHS call, and a bounded effectful
index. A final-summary trace confirms the array store incorrectly lists the
separate counter among its writes. The proposed repair separates reference
values from addressed storage, including projected arguments passed by reference.
Baseline summary inspection also finds missing writes for a primitive element
passed by reference through a formal aggregate. The program passes checking,
but its caller publishes no mutation effect. Global, captured and slice
projection controls expose the same omission. CLI acceptance alone cannot
qualify this repair.
The location-tracking successor also needs owned provenance for untracked
primitive locals. A paired probe passes on `9df00ac7` but rejects on successor
`82cfb51d`: passing a separate local `i32` by reference wrongly invalidates the
loop's `usize` counter. This regression blocked that snapshot's qualification.
The analogous enum-local probe passes on `9df00ac7` and rejects on `c1120acd`.
Revision 5, `b37fc6f2`, retains owned enum provenance. Its
[bounded qualification](../tmp/v1-completion-2026-10-10/primitive-place-location-candidate/revision5/qualification/REPORT.md)
matches all 54 semantic/compile outcomes and passes 13 summary tests and 127
focused tests. The focused count includes the summary tests. The captured
fixture follows the documented semantic-0/compile-7 contract while retaining
its mutation-summary requirement. Broader capture support is separate.
Independent paired probes still expose three valid rejections introduced by
the location model: replacing a distinct string, slice or function-value slot
invalidates the unrelated loop counter. All three passed on `9df00ac7` and
reject on `c1120acd`; the tested tagged-union slot passes on both. Preserve
these controls while distinguishing slot replacement from writes through
reachable storage. Independent occurrence traces verify local return and escape
tokens, deferred return snapshots, and receiver selection before an effectful
index in the separately guarded probe. The original index probe still fails
bounds checking. Broader qualification and native verification remain incomplete.
No location candidate is integrated.
The [handle controls](../tmp/v1-completion-2026-10-10/primitive-location-handle-controls/REPORT.md)
reproduce those three failures on `b37fc6f2`. A complete same-backed slice and
element-reference caller passes both modes, with the required formal write in
its helper summary. A replaced callback that resets the counter rejects at
the intended deletion. The correction must preserve that invocation effect
while accepting the distinct slot replacements.
Further controls preserve lifetime rejections after reference forwarding,
global retention and an unresolved aggregate callback. A separate proposed
callee-before-arguments control rejects too, but that ordering is not yet an
approved public contract. Reconcile the analysis order with native behavior
before proposing a language guarantee.
The isolated slot-effect repair passed 74 compiler outcomes for 37 unique
inputs on `da0bf9a5`, including the three original valid handle replacements.
The runner found a duplicate CLI case name after collection, so summary and
focused stages did not run. Revision 8, `75ffeaec`, removes that duplicate.
Independent review verified the unchanged compiler and exact correspondence
of all 37 inputs to the earlier outcomes. After correcting the summary-result
prerequisite, revision 8 passed 18 summary tests and 142 focused tests. The
142 include those 18 summary tests and 37 CLI cases, so the counts overlap.
Parent verification checked all twelve stage streams and their source/review
bindings. No separate revision 8 prerequisite replay or native safety
acceptance is claimed.

A separate native probe found that an inferred mutable function declaration
emits `var state = old_target`, which Zig rejects as a mutable bare function
type. An explicitly typed counterpart builds and prints `argument`, `old`,
`new` in Debug, ReleaseSafe and ReleaseFast. The isolated declaration repair
`f8485bac` now builds and runs the original inferred input in all three
profiles. Its [bounded qualification](../tmp/v1-completion-2026-10-10/primitive-location-function-declaration-candidate/revision2/qualification/REPORT.md)
passed 15 native regression cases and 62 nonnative generic compatibility
tests. Parent verification and independent evidence review passed for that
bounded run. Combined qualification remains open. No live backend integration
occurred.
The reviewed
[callable-order proposal](plan/packets/P-CALL-evaluation-order.md) awaits the
user's choice before adding a public ordering guarantee.

The [combined candidate](../tmp/v1-completion-2026-10-11/combined-location-declaration-candidate/REPORT.md)
`e78ffbd7` freezes 1,706 files. Parent and independent source review verified
the exact safety and declaration changes, with current documentation copied
into the snapshot. No further compiler or test changes were introduced.
The original 53-input replay completed all 106 compiler outcomes: 27 valid
programs passed both modes and 26 unsafe programs rejected in both modes.
Its runner exited 1 because it incorrectly required whole-expression error
spans. Parent inspection verified every required site using the original
span-containment contract; all 52 negative diagnostic lists match the earlier
`8adf421e` run exactly. Raw failed-verifier evidence is preserved. These are
compiler checks, not native executions. The combined broad regression passed
999 tests with 32 native/slow deselections. Root verified the recorded test
outcomes and raw output; there were no skips or expected failures in this
selection. Full pytest finished with 5,056 passed, one failed and one expected
failure in 782.73 seconds. The sole failure is the packaged-source function
alias emission assertion: the emitted declaration includes the checked function
type, while the assertion expects the old unannotated form. The existing
heap-scalar write-through requirement remains an expected failure.
Test-only successor `3ba27b74` corrects that assertion
and adds imported-alias native output checks in three profiles. Its compiler
files are unchanged. Independent source review found no blocker. All 19
packaged-module tests passed on the successor, including the original
wrong-argument rejection and three native runs printing exactly `7\n` in Debug,
ReleaseSafe and ReleaseFast. Parent verification checked source hashes, raw
outputs and binaries. Full pytest then passed with 5,060 tests and the existing
heap-scalar expected failure in 783.12 seconds. Parent verification checked all
1,706 source files, nine observer records and the identical 5,061-node worker
collections. The four scanner exclusions remain explicit. The original native
qualification passed all 81 exact outputs on this successor, with 27 programs
in each profile. All 106 compiler prechecks ran before native builds; 52 negative
checks matched their required diagnostic sites. Parent and independent review
rehashed 704 streams, 189 artifacts and all 1,706 source files. The
[native review](../tmp/v1-completion-2026-10-11/combined-location-declaration-revision2-native-independent-review/REPORT.md)
records the finite-case limits. Separate handle and remaining package checks
are still required before integration.
Separate observable string, slice and function-slot controls passed semantic
checking and code generation on the combined source. Native qualification then
failed while building the Debug slice control. Its inferred `state` declaration
omits the checked slice type; Zig infers a pointer to the backing array and
rejects passing its address to the slice-reference parameter. The Debug string
control passed; the other eight outputs remain unverified. The
[failed handle review](../tmp/v1-completion-2026-10-11/combined-location-declaration-revision2-handle-native-independent-review/REPORT.md)
preserves the original input and compiler output. Isolated slice repair
`1ec7b7cf` passed 39 native tests, 177 compatibility tests and the original
slice witness in all three profiles. Three of those native tests insert Zig
type assertions into emitted code; the other 36 run ordinary compiler output.
A baseline probe fails the intended assertion before the repair. The immutable
binding fix reads the checked initializer type, preserving backing constness.
These bounded results do not replace full qualification. Combined source
`04c5e959` includes the repair, L53 benchmark changes and the newer strict JSON
and traversal tests. Its completed full run passed 5,117 tests with the existing
heap-scalar expected failure in 798.93 seconds. Recovery found the old tool
handle unavailable; terminal records, raw output and all worker exits establish
completion. Independent review verified the source and all 999 historical broad
test identities passing in this run. The [native qualification](../tmp/v1-completion-2026-10-11/combined-slice-harness-native-independent-review/REPORT.md)
passed all 90 exact outputs across Debug, ReleaseSafe and ReleaseFast, plus
52 required rejection sites. Owner session 17214 exited zero. The
[remaining gate audit](../tmp/v1-completion-2026-10-16/combined-remaining-gates-review/REPORT.md)
verified 11 passing component checks, including 51 examples in each artifact
profile, 61 error-stage checks and wheel/source-distribution installation.
The strict benchmark gate failed for missing `mem_shared`, `mem_returned` and
`mem_cleanup` host pins. Report-only timings were unpinned and do not qualify
performance. The 30 reviewed compiler, test and benchmark transfers and seven
matching documentation files are now integrated into the live tree. The known
heap-scalar expected failure remains unresolved.

Reference-to-fixed-array indexing supports primitive element reads and simple
or compound writes when bounds and non-nil requirements are proven. Guarded nil
calls and borrowed-array calls remain valid. Unresolved nil-call conditions,
effectful indices, selected reference-array fields, mutable or captured callable
origins, ref slicing and general reference-element ownership remain incomplete.

Resolved functions whose body contains one Boolean-literal return supply indexed
guard facts. This covers direct and forwarded calls and stable unwritten,
uncaptured local aliases. The checker preserves call and argument evaluation;
indexed uses retain optional-reference unwraps. Conditional, effectful and
deferred helpers remain unknown.

Eligible local Boolean cells and value parameters supply indexed guard facts
from bare or negated conditions and comparisons with Boolean literals. Early
returns retain the surviving branch fact; copies retain their evaluated value.
Captured or reference-exposed cells, fields and globals are excluded. Assignments
replace facts; joins require matching values. Loop write invalidation also
clears affected Boolean facts.
True or unknown guards with nil reject at semantic exit 6. An unguarded symbolic
`read(nil, b)` wrapper still rejects even if its only caller passes false.
These facts do not certify purity or complete effect modeling.

- Zig is the only supported public backend.
- Else-if checking preserves each declaration and its lexical scope, including
  parent bindings after an arm shadows the same name.
- Overlong module paths report a located `ImportError` at resolution exit 3,
  retaining the filesystem failure for entry and dependency imports.
- The benchmark `--gate` requires a complete host baseline before building.
  `--pin --gate` together exits 2; updating and checking are separate runs.
- Constant float remainder follows the runtime truncation rule, including the
  dividend sign and negative zero.
- The compiler pipeline covers tokenization, parsing, semantic analysis,
  internal safety proof planning, AST preprocessing, and Zig code generation.
- Output paths cannot overwrite input modules. Diagnostics retain module origins;
  artifact reports exclude stale files.
- Source recursion is banned. Use loops, explicit stacks, queues, and
  index-based worklists.
- `a7 check FILE --layout` reports struct memory layout (alignment-ordered
  offsets, size, 64B line use, field-access counts), matching the emitted
  Zig binary in the `debug` and `release` profiles. `fast` drops the hidden
  tag of an untagged union.
- The bench corpus measures layout effects: the AoS/SoA pair proves
  parallel arrays 1.59x faster than struct arrays for subset-field loops
  (`bench/`, `scripts/bench_perf.py`).
- The example suite is verified against golden output fixtures. Current counts:
  `uv run python scripts/project_status.py`.
- The perf gate times the seventeen-program `bench/` suite as median-of-N
  ReleaseFast (`--profile fast`) runs against per-host pins in `bench/pins/<host>.json`.
  `run_all_tests.sh` runs `scripts/bench_perf.py` report-only; `--gate` exits 1
  past 1.15 times the pinned median.

L53's benchmark hardening is integrated from combined source `04c5e959`.
The live harness defaults to seven samples, requires at least five for pin/gate
runs, rejects noisy pin/gate measurements and enforces inherited CPU affinity.
The original 36 deterministic tests used replaced timer/process boundaries;
the combined full pytest run also passed the harness tests. The
[harness review](../tmp/v1-completion-2026-10-11/benchmark-harness-l53-independent-review/REPORT.md)
records those test boundaries. The later report-only run completed all thirteen
workloads with seven samples, but its unpinned affinity and `alloc_churn` CV of
0.13 prevent performance qualification. The strict gate failed before measuring
because three promoted workloads lacked host pins at that checkpoint.
The [October 16 promotion](audits/2026-10-16-l67-promotion.md) adds four
public-input workloads with exact output checks. The suite now has 17 entries
and the unchanged host pin lacks seven. Four full-count native harness smoke
runs passed; these one-sample observations do not calibrate timings. No pin
was updated.
Host regression pins do not satisfy L38's C-relative runtime and memory limits.

The safety pass keys facts by declaration, not by name, and joins state
at branches, loops and scope exits (2026-10-04 repair):

- After a loop, the state is the loop-entry state with everything the loop
  can assign forgotten and everything it can delete marked moved. The
  negated loop condition holds only when no `break` can leave the loop.
- A deferred statement is proven at every exit of its block (end, `ret`,
  `break`, `continue`), in reverse registration order.
- A call to a non-stdlib function forgets every fact about a file-scope
  variable. A `ref` argument passed to a function value or other unknown
  callee counts as deleted.
- An arm reached by `fall` starts from the join of both entry states.
- A match capture, a loop variable and a shadowing local each start with
  no inherited fact.

This closes the audit's loop, defer, shadowing and callee-identity holes,
SAF-3 fallthrough division and SAF-6 global mutation across calls (ledger
L71). The approved L74 repair rejects SAF-2 user-field `ptr` nil access,
SAF-8 repeated field deletion, and direct reference alias use after deletion
(`c := b; del b; c.value`). The seven original valid controls ran in all three profiles against an
earlier safety.py revision, as recorded in the
[qualification boundary](audits/2026-10-07/qualification.md). Later nested-record,
wrapper and match repairs are included in the passing integration gate.
Exact array-element aliases at proven indices now track allocation identity for
fixed local arrays of references: stale element reads after deleting the source
allocation exit 6, while before-delete and distinct-slot controls remain
accepted. Independent slot copies and fresh replacements retain valid behavior.
Bounded dynamic-index stores on those arrays join or invalidate every tracked
element fact that the store may hit. Slice-element identity and arrays inside
records remain outside this slice; see
[P-REF-container-identities](plan/packets/P-REF-container-identities.md) (not
approved for broader policy). On the reviewed snapshot, deletion through a
borrowed aggregate left a caller alias alive in the proof state; callee field replacement
could retain the previous allocation's identity. The same snapshot rejected
valid parent/sibling use after child-only deletion and valid parent use when a
callee deleted an unrelated local allocation. The bounded exact-callee repair passes focused semantic and native controls,
including borrowed-field deletion, replacement and parent/sibling preservation.
It also repairs nested-function global summaries and delays global body effects
until after argument evaluation. These repairs are included in the passing
integration gate.
Exact replay permits at most one transitive conditional and source-sized expanded
work. A doubling call chain can exceed this budget at depth three; this is a
work bound, not a fixed depth guarantee. Over-budget callees fail closed to the
legacy summaries. Selected-child lifetime dependencies
now preserve the represented aliases without marking every possible child
deleted. Focused and independent compile-only checks, native controls in all
profiles and the integration gate pass. Stores through a selected holder join
old and new facts for each concrete candidate rather than overwriting all to the
new value; heap-field sync still reaches selected binding paths that share
storage, but independent by-value struct copies that merely hold the same
reference stay separate. Joined-holder nil-write invalidation clears overlapping
selected binding paths. Unapproved P-REF cases (correlated complementary
selections, unknown-callee container effects) remain ledger-deferred.
Other paths retain incomplete legacy analysis. A later candidate repairs
loop-head deletion through a reference-field argument and a loop-local alias.
It preserves unrelated allocations, fresh factory returns and valid one-trip
loops. It also separates returning cleanup from continuing paths. That candidate
passes 294 focused nonnative tests and replays 65 reviewer cases. GLM review matched 165 behavioral cases; the full integration gate above
predates it.
Independent review also found exponential fresh-origin expansion in a small
acyclic factory chain. Compact allocation graphs now retain 196 nodes for the
depth-64 reproducer. Independent comparison of 16 programs preserves exits,
diagnostics and generated Zig; 159 integrated focused tests pass. The depth-64
valid control runs in all three profiles. GLM review matched 68 paired programs
and reproduced the resource counts. The published `1857e03` integration run passed 3,602 tests
with one expected failure, 51 examples in each build profile, and native package
installation. Its secrets check failed because the snapshot lacked Git metadata.
After metadata recovery, that check and all skipped release checks passed on
unchanged sources. The later integration candidate propagates direct global
reference stores and deletion effects across known calls. It preserves captured
arguments, saved old globals and distinct live replacements. Its one-trip proof
also accepts separate positive increments on alternative paths when every
backedge crosses the bound without wrapping. Post-loop deletion checks remain.
Global nil-state summaries and parameter proof obligations remain incomplete;
the unsafe nullability/branch-precision trial `68f` is excluded. Nil-origin
trial `f521` is also excluded after a confirmed valid false-branch control
regressed. Conditional origin relations and callee preconditions remain open.
The integrated literal-return repair selects precise return facts for simple
direct callees and literal boolean arguments. Its frozen 1,601-file snapshot
passed the full release gate: 3,772 tests passed, one expected failure, and
all 11 compiler/package checks passed. Native controls passed in debug,
release and fast profiles, including later-argument mutation of a reference.
The external review completed 73 compile-only pairs: 17 new rejections,
four valid acceptances, 30 unchanged acceptances and 22 unchanged rejections.
Its first invocation failed a provider rate limit; the retry completed.
General effectful returns and nonliteral selectors remain open. That literal-return
checkpoint used safety source `0d8b3938`; the later readonly integration used
`c51f8378` with readonly requirements `aeefd7cf`. It adds rejection-only call
requirements for represented branches, defers and certified loops. The earlier
stale-counter and borrowed-scalar failures are preserved in isolated candidates;
their repairs passed independent review and the latest full release gate.
General callee and container proofs remain incomplete.
See the [container-identity proposal](plan/packets/P-REF-container-identities.md)
for the separate array/slice/selected-value decision boundary.
The October 4 runtime-contract
repair defines signed minimum-value arithmetic and checks runtime shift counts;
those former gaps no longer describe that checkpoint. See
`test/test_checked_arithmetic_edges.py` and `test/test_build_profiles.py`. A loop that deletes and then reassigns one
reference in its body is rejected. The checks do not establish complete
alias or lifetime safety. Pinned in `test/test_safety_loop_facts.py`,
`test/test_safety_defer_facts.py`, `test/test_safety_binding_identity.py`
and `test/test_safety_stale_facts.py`.

The qualified entry commit `0d510421` was deployed. All 61 fetched HTTP
resources matched the built bytes; CI was pending at that review. This is HTTP
parity, not rendered-browser or accessibility qualification. The
[publication record](audits/2026-10-07/readonly-entry-publication.json)
retains the exact revision and observation limits.

The first stdio gate on source `7f5fd941` exited 1: 3,932 tests passed,
one failed and one was an expected failure; 10/11 compiler/package checks
passed. The failure was the stale codegen-7 expectation for a call now rejected
at semantic stage 6. The one-line repair preserves the program and line-4
assertion; 52 focused tests passed, followed by independent and same-session
GLM review. The outer site, dependency and security checks were not reached.
The [first gate record](audits/2026-10-07/stdio-first-gate-verification.json)
preserves that failed run. The repaired gate passed on source `e0c6235a`
with 3,933 passing tests, one expected failure and all 11 compiler/package checks.

## Active implementation priorities

The user requested Goose-informed feature preparation under L77. The
[pinned research](plan/research/goose-2026-10-17.md) is complete as source review;
Goose execution and A7 prototype results are unverified. Keep Zig and defer C
export. The roadmap's GOOSE-1 through GOOSE-6 phases prepare lifetime/placement,
compact layout, construction, callbacks, isolated transfer and error contracts.
No new memory mechanism, syntax or compatibility change is approved by the
research request. Existing memory and language decisions remain in force.

1. Keep status and release facts script-derived, not hard-coded.
2. Qualify per-file module scopes and reporting in the combined release gate.
3. Resolve the numeric gates in [the v1 plan](plan/README.md) before changing
   arithmetic or casts. Decisions L3 and L4 retain explicit-width integers and
   reject `int`, `uint`, and `number`.
4. Split safety proofing into internal CFG, fact, obligation, proof-discharge,
   and backend-plan stages. Rewrite-facing milestones and the thin
   `a7/proof_discharge.py` boundary are in
   [P-PROOF](plan/packets/P-PROOF-discharge-milestones.md) (constant-fold
   congruence, recursion-ban graph, tagged-union exhaustiveness, obligation
   records). No CompCert claim. Coordinate invasive CFG/fact splits with
   Track 1 safety/alias work.
5. Finish generic specialization before broad cross-module generic workflows.
6. Maintain installed-distribution checks for `a7 check`, `a7 build`, `a7 run`,
   `a7 doctor` and `a7 --version`. Wheel and source-distribution workflows pass
   on the current Linux x86-64 target.
7. Keep both recursion scans empty and extend deep pipeline checks for new
   compiler paths. All currently scanned recursive groups, deepcopy calls and
   generated-method cycles are removed. Dynamic external Python callbacks remain
   outside the structural traversal guarantee. See the
   [delivery roadmap](plan/delivery-roadmap.md).
8. Keep compile-perf baselines documented for the rewrite (`--timings` / stage
   `ms` in JSON). Do not deep-parallelize this Python frontend; see Planned
   work.

## Known Gaps

- Exact-fit untyped constants are implemented with one evaluator
  (`a7/exact_constants.py`): exact arithmetic, then a fit to the
  destination (ledger L61). Growth preflights, initializer and compilation work,
  logical retention, exact binding depth and bounded diagnostics implement the
  C3–C10 accounting rules in SPEC Appendix C. The existing exponent limit remains
  semantic exit 6. Generic pattern conversions share the same accounts, including
  emitted unused widths and templates. C11 emission qualification remains open;
  math-call output is unchanged. Small injected limits test accounting boundaries;
  default-limit C3 and C5 witnesses test real compiler refusal. Those controls do
  not establish full-policy or native qualification. Direct literal patterns are
  fitted
  to the concrete numeric subject before duplicate checks. Generic numeric
  patterns defer fitting until the subject type is known. Each instantiation
  retains its own overlap checks and defining constant bindings. Runtime ranges
  require numeric or character subjects. General runtime generic dispatch remains
  unimplemented.
  Bitwise `~`
  is not folded. Declaration-order-independent global typing follows
  [P-TYP](plan/packets/P-TYP-forward-globals.md).
- Integer literal/range overlap checks preserve fitted integer values beyond
  2^53. Disjoint adjacent values remain accepted and equal singleton/literal
  pairs are rejected in either order.
- Generic argument constraints admit equivalent or narrower source sets for
  function calls, nominal construction and nominal type annotations. Source sets
  containing a nonmember, empty sets and unconstrained arguments remain rejected
  on those paths. Invalid annotations in variables, signatures, fields and type
  aliases report constraint errors even without construction. Record constraints
  resolve after named aliases in their defining file, including forward members
  and imported owners. Broader generic propagation limits below remain open.
- Both candidate recursion scanner modes report empty recursive-group,
  deepcopy and generated-method lists. Safety statements; parser statements,
  expressions and types; checker statements,
  expressions and type resolution; backend statements, expressions and types;
  and AST structural comparison/display now use explicit worklists. These
  paths are included in the qualified integration checkpoint. The earlier frozen
  expression snapshot passed 3,082 nonnative tests. Parser review matched 111
  independent cases; backend debug and release each passed all 51 examples.
  Expression GLM reviews passed within their assigned scopes. Safety traversal
  review passed. The combined snapshot passed 3,602 tests with one expected
  failure; secrets and skipped release checks passed after metadata recovery.
  The [follow-up record](audits/2026-10-07/iterative-followup-verification.json)
  identifies each source and its evidence. Passing selected deep inputs does
  not establish the full no-recursion requirement. Arbitrary external Python
  payload callbacks remain outside the AST structural traversal guarantee.
  A later positive regression combines an imported struct, 200 array dimensions,
  canonical `Option(Result(i32, i32))` and local generic inference. Compilation
  emits identical Zig at recursion limits 1,000 and 100. The
  [regression record](audits/2026-10-07/deep-canonical-module-verification.json)
  records 91 passing related tests and nine excluded native tests. This checks
  the Python compiler pipeline through Zig emission, without native execution.
  The [deep JSON regression](../tmp/v1-completion-2026-10-11/deep-json-strict-regression/REPORT.md)
  now requires semantic exit 6 for a 2,000-link undefined field chain in three
  modes; internal exit 8 no longer passes. All six tests in that file passed.
  Independent probes also observed semantic exit 6 on frozen source `3ba27b74`.
  The later combined full run on `04c5e959` includes this stricter regression
  and passed with 5,117 tests and the known heap-scalar expected failure.
  The earlier `3ba27b74` evidence retains its original narrower scope.
  Two later [deep cleanup regressions](../tmp/v1-completion-2026-10-16/deep-cleanup-regression/REPORT.md)
  cover 200 nested projected deferred writes and a saved alias used after
  deferred deletion. At recursion limits 100 and 1,000, the valid case emits
  identical Zig with all 200 cleanup calls; the invalid case reports semantic
  exit 6 at the exact saved-alias use. The related nonnative selection passed
  123 tests. These test additions do not claim native cleanup execution or
  a new full-suite qualification.

- A labeled loop whose label is never targeted no longer emits a label: the
  fix landed with commit `ed0baff`, and the never-targeted case is pinned in
  both profiles by the `unused-labels` case in
  `test/test_resume_backend_bindings.py`.

- Local constant usage is now tracked by declaration identity. A declaration
  initializer reads the outer binding, and match-expression arms use their own
  scopes, so sibling-scope collisions and nested shadowing resolve to the
  binding their position in the block selects. Both cases are pinned in both
  profiles by `test/test_resume_backend_bindings.py`. The [review
  follow-up](audits/2026-09-20-core-v1/backend-glm-followup.md) preserves the
  original reproducers.

- File-backed imports now have separate semantic scopes, private top-level names
  and distinct nominal type identities. Qualified types, struct literals,
  constant array lengths and generic bodies resolve in their defining files.
  Reports retain file and lexical owners. One combined Zig output preserves
  existing module and declaration order. L28 still rejects local bindings that
  reuse their own file's aliases; fields remain independent. Selected imports
  (`import "m" { A, B }`) bind public names from file modules and virtual
  stdlib modules. `using import` rejects at semantic exit 6 with alias-form
  guidance. Hardlinks share one module identity with symlinks and realpath
  spellings (duplicate import exit 6; diamond load shares one ModuleInfo).
  L76 keeps import aliases local to their declaring file. Parsed forwarding
  rejects with semantic exit 6 and direct-import guidance; ordinary public
  wrappers and struct fields remain valid. Unsupported multi-dot type
  annotations and literals retain parse exit 5. The
  [approved packet](plan/packets/P-MOD-import-forwarding.md) records this
  boundary. Pins:
  `test/test_import_selected_using_hardlink.py`.
  Stage10's full compiler gate exited 1: 3,689 tests passed, one obsolete `__`
  fixture failed and one expected failure remained. The other ten compiler
  checks and all 51 examples in every profile passed; outer release checks did
  not run. The corrected fixture received independent review. Stage12 passed
  3,305 nonnative tests. Stage13 combines modules, constant diagnostics, global
  aliases, equivalent loop increments, immutable generic aliases, the symbol-kind
  guard and L76 v2. Manifest `c37e0c08` passed 3,337 nonnative tests in 51.26
  seconds. Two targeted native tests passed: corrected local-name collisions in
  debug/fast and direct imports/public wrappers in all three profiles. The
  combined immutable-alias control built and produced its expected output in
  all three profiles. Full manifest `27c4c26e` then passed the complete release
  gate: 3,756 tests with one expected failure, all 11 compiler/package checks,
  51 examples in every profile, site checks and dependency/security checks.
  All 1,599 frozen file hashes and modes remained unchanged. L76 core and
  diagnostic-delta external reviews found no scoped blocker. Rendered browser
  checks could not run because no browser connection was available. These
  results do not qualify full V1.
- Immutable aliases whose copy chain is never reassigned, passed by reference
  or captured by another function preserve concrete body obligations for
  same-file, imported field, module-global and selected-import origins.
  Parameter, mutable, captured and aggregate origins remain incomplete when the
  chain is not analyzable; those calls do not claim body proofs. General
  runtime generic dispatch is not implemented. Pins:
  `test/test_immutable_generic_aliases.py`,
  `test/test_generics_obligation_origins.py`.
- An entry file must define `main :: fn()`; a file without one exits 6 at the
  Entry Point stage. Imported modules are exempt. `a7 check --lib` checks a
  library file without an entry point; `build` and `run` still require one.
- Integer `+`, `-`, and `*`, including compound forms, keep wrapping by
  default. Release builds lower proven-range results to non-wrapping
  operators; `--no-nonwrap` forces wrapping everywhere. Union discriminant
  access, full ref/del alias behavior and ownership/lifetime guarantees
  remain incomplete.
- Generic functions construct and return parameterized Box, Option and swapped
  Pair values in seven fresh controls, including cross-file wrappers and
  module-qualified constructors. All 21 executions across Debug, ReleaseSafe
  and ReleaseFast match exact output. The October 4 D6 codegen failure is stale
  for these forms; general runtime generic dispatch remains incomplete. The
  [stdlib prerequisite record](audits/2026-10-07/stdlib-source-loader-prerequisites.json)
  pins the sources, outputs and limits.
- Generic `union(tag)` types now specialize positionally like structs:
  `Result(i32, string){ok: 1}` checks and field access resolves.
  Conflicting `$T` bindings at one call site exit 6
  (`GENERIC_PARAM_MISMATCH`). Generic enums stay out of scope (no
  payload types to specialize). Pinned in
  `test/test_generics_fast_union.py`.
- `$N` value params (`usize`, `bool`, small ints) work on generic fns,
  structs, and unions for declarations, named-constant instantiation
  (`Buf(SIZE)` with `SIZE :: 4`), and literal args (`Buf(4)`, `Flag(true)`).
  Function calls infer `$N` when the binding is unique (for example from a
  fixed array length). Matching forwarding (`inner: Buf($N)`) is accepted
  under kind checks; mismatched kinds exit 6. A bare `$N` as a type, a value
  of the wrong kind or range, a type for a value param, or a value for a type
  param exits 6. Pinned in `test/test_generics_value_params.py`.
- Minimal `where` conjunctions (`where T: Numeric`,
  `where T: Numeric, U: Float`) work on generic fns, structs, and
  unions. Richer predicates, unknown names, and `where` on enums
  exit 6. Pinned in `test/test_where_clauses.py`.
- Two functions with the same name exit 6 (`ALREADY_DEFINED`),
  whatever their signatures. Overloading is parked (ledger L59).
  Pinned in `test/test_duplicate_function_names.py`.
- Generic local literal/array and scalar if/match initializers and bound callback arguments
  are checked against concrete instantiations. Callback assignment and branch
  selection preserve their bound signature. Focused semantic and debug/fast
  native controls and the integration gate pass.
  Callback provenance through record fields and array elements, and generic
  declarations stored as runtime function pointers, remain open.
  A later candidate fits ordinary and generic if/match array-literal arms,
  including nested arrays. It passed 206 focused tests and combined debug/fast
  native controls. GLM review found no introduced regression. The repair is
  included in the frozen integration and recovered release checks above.
  A further candidate fits literal arms to a concrete typed array arm. Its
  244 focused tests, 13 independent source cases and debug/fast execution of
  both branches pass. GLM review matched 79 independent compile-only programs
  without an introduced regression. Immutable alias obligation preservation now
  covers same-file, imported, module-global and selected-import copy chains that
  stay unwritten and uncaptured. Parameter, mutable, captured and aggregate
  origins remain incomplete. The earlier local-flow trial stays excluded because
  it loses branch correlations. No general runtime generic representation is
  implemented.
  Declared fixed-array element types such as `[2]$T`, including nested arrays,
  now use the existing initializer checks after concrete substitution. Fitting
  direct calls, qualifying immutable aliases and concrete wrappers are accepted;
  overflow, wrong lengths and typed narrowing remain rejected. A concrete
  wrapper may use ordinary function aliases and parameters after its initializer
  checks are discharged. Unrelated generic parameters do not reopen those checks.
  Newly deferred initializers with unresolved source or destination types still
  reject unsupported callable escapes. An unresolved generic element destination
  such as `[2]$T` still fails before instantiation. General call-chain
  propagation of generic inference and runtime generic representation stay open.
  The integrated repair on frozen source `4e432638` passes 4,075 tests with
  one expected failure, 12 native controls and nine direct compiler/package
  checks. The [prerequisite record](audits/2026-10-07/stdlib-source-loader-prerequisites.json)
  preserves the source identities, reviews and predecessor failures.
- Multiple return values, destructuring, and user variadic parameters
  are cut from the runnable surface. Variadic parameters (`values: ..T`)
  parse then fail at semantic exit 6 with a slice guidance message.
  Multi-declaration / destructuring (`a, b := …`) and multi-return
  spellings (`fn() (T, U)`, `ret a, b`) fail at parse exit 5 with an
  explicit cut message. Return a named struct for several results.
  Collections / `std/string` / `std/mem` stay deferred pending approval of
  [P-STD-collections-scope](plan/packets/P-STD-collections-scope.md).
  Tagged unions match through leading-dot arms (see below); other tag
  workflows stay open.
- Tagged-union payload matching works end to end. `case .none:` tests
  a tag, `case .ok(v):` binds a copy of the payload, and `else:` and
  `_` opt out of exhaustiveness. A bare `case tag:` exits 6, and a
  match with uncovered tags and no `else` reports one exit-6 error
  listing each missing tag. A payload that is or holds a `string`
  (directly, in a struct field, or in a fixed array) cannot bind by
  value and exits 6; match the tag without a binding. A `ref` to a
  tagged union matches the same way. Pinned in
  `test/test_match_payload.py` and `test/test_match_dot_e2e.py`.
- Package-owned `Option(T)` and `Result(T, E)` are available in every file.
  Redeclaring either name fails at semantic exit 6. Members may retain those names.
  `io.println_ok` and `io.read_line` return canonical `Result(usize, io.IoErr)`;
  saved values, wrapper returns and cross-file signatures use the same identity.
  `read_line` requires one mutable `[]u8` and counts a consumed newline.
  Module operations and `io.IoErr` require explicit imports in each file.
  Literal `std/` paths cannot fall back to project files; explicit relative
  paths keep existing containment rules. `get`/`pop`, collection modules and
  `or{}`/`use` remain deferred. Pinned in `test/test_stdlib_signature_typing.py`
  and `test/test_stdlib_result.py`.
- The package-owned implementation loader resolves reserved `std/` imports to
  registered hooks or package sources. Bundled dependencies retain their module
  identities and package containment root. The package still supplies only
  prelude and I/O declaration sources; `std/ascii` remains unavailable. Loader
  tests inject an ASCII fixture without publishing that module.
  Hook signatures and module-owned declaration resources come from the registry.
  Existing math and format policies remain explicit. Zig mappings select packaged
  runtime fragments when used, and mapped helper names share the backend's
  collision handling. These compiler prerequisites add no Phase A public modules.
  The earlier loader prototype and loader-only qualification are recorded in the
  [prerequisite record](audits/2026-10-07/stdlib-source-loader-prerequisites.json).
  Those earlier results do not qualify the combined compiler or promote Phase A.
  That integrated compiler matched frozen source `9164ac09`: 4,006 tests
  pass with one expected failure, plus nine direct compiler/package checks and
  12 valid native alias controls. All three artifact profiles and example E2E
  pass 51/51; error stages pass 61/61. Documentation and exports were updated
  afterward. Its site build/export/link checks passed, but preview binding failed
  with `EPERM`. The October 8 site check later passed that test; the
  October 16 check failed socket binding again.
  Rendered-site, external GLM and full release qualification remain incomplete.
- The registered stdio repair rejects inferred bindings,
  container elements, `if`/`match` results and format arguments supplied by
  registered `print`, `println` or `eprintln`. The stage changes from semantic
  acceptance followed by codegen exit 7 to semantic exit 6. Statement effects,
  `println_ok` results, ordinary user void bindings and prior type-error priority
  are preserved in the paired checks. The author passed 181 nonnative tests.
  Independent review checked 18 fresh sources in two modes, 36 paired
  observations: nine source shapes receive the intended stage correction and
  five jointly accepted programs retain identical Zig. Nine native executions
  across debug, release and fast match exact stdout/stderr; all nine emitted
  Zig files match the baseline. The full gate passed on frozen source
  `e0c6235a43632839d50be28d2128af666be78634e8a5c50c8fcf317ef6915470`: 3,933 tests passed,
  one expected failure and 11/11 checks.
  Gate log SHA256: `b795102848638d64f78ce2a8091903c32079a07655c6879832d8611b5320bc2c`. Type
  and exact-constant errors retain priority; later semantic-validator messages
  can be suppressed by the earlier consuming-call error. General user-function void consumption remains
  outside this repair. Evidence is retained in
  `tmp/v1-completion-2026-10-07/stdlib-inferred-void-candidate/` and
  `tmp/v1-completion-2026-10-07/stdlib-inferred-void-independent-review/`.
- Zig emission changed in two pinned ways with no runtime behavior
  change: single parens in conditions and left-assoc chains, and native
  `switch` for a match whose scrutinee is an integer, char, bool or
  enum and whose arms are constants. Every other match (floats,
  strings, runtime arm values, `fall` arms) keeps the if-chain.
  Strings compare by content in `==`, `!=` and `match`. `ref`
  parameters lower to `?*T` (ledger L60). `ret`, `break`, `continue`
  or `fall` leaving a `defer`, directly or from inside a
  `defer { ... }` block, exits 6. Inline generic functions
  (`fn(x: $T) $T`) and file-scope `@type_set` aliases compile and run.
  New examples
  `049_expense_ledger` and `050_tip_split` run end to end. Pinned in
  `test/test_codegen_emit.py` and `test/test_del_defer_codegen.py`.
- The recursion ban follows function values by type, not by flow: an
  indirect call may reach any function of the same type that is used as
  a value. A function that is itself used as a value and calls through a
  value of its own type exits 6 even when it never recurses. Pinned in
  `test/test_recursion_ban_function_values.py`.
- A function-pointer local without an initializer has no callable zero value.
  Proved-uninitialized calls and copies now exit 6 before Zig (partial local
  check; uncertain joins after partial assignment remain accepted). Aggregate
  field/array function slots stay outside this first slice
  ([P-FN-initialization](plan/packets/P-FN-initialization.md)).
- `main` cannot return an exit status: a program exits 0, or 134 on a
  panic.
- Collections and fuller string/memory helpers are planned
  stdlib work.
- Reference-to-fixed-array indexing retains incomplete callable and condition
  support described under Current Surface. Reference slicing remains rejected.
  The [prerequisite record](audits/2026-10-07/stdlib-source-loader-prerequisites.json)
  preserves the earlier bounds-failure diagnosis on `158a8423`.

The focused native probes record these repaired behaviors and remaining limits:

- Escaped IO braces compile and print literal braces. Signed-integer
  `math.abs` preserves the declared signed result type; its minimum negative
  input wraps to that same negative value.
- Scalar-filled fixed-array initializers and direct `string.len` access are rejected.

- Duplicate imports are rejected (fixed). The same path twice, alternate
  spellings (`helper` vs `./helper`), symlinked paths, and a reused alias
  each exit 6. Pinned by `test_duplicate_import_same_path_exits_6`,
  `test_duplicate_import_alternate_spelling_exits_6`,
  `test_duplicate_import_second_alias_exits_6`, and
  `test_duplicate_import_through_symlink_exits_6` in
  `test/test_import_error_stages.py`. Different files importing one module
  stays legal (`test_different_files_importing_same_module_stays_legal`).
- Unclosed block comments are tokenizer errors (fixed). A plain unclosed
  `/*` and a nested-unclosed `/*` each exit 4 at the comment start. Pinned
  by `test_unclosed_block_comment_exits_4` and
  `test_unclosed_nested_block_comment_exits_4` in
  `test/test_import_error_stages.py`.
- Imported-file errors keep their own stage and file (fixed). A tokenize
  failure in a dependency exits 4 with category `tokenize`; a parse
  failure exits 5 with category `parse`; each names the imported file.
  Missing, unreadable, and permission-denied imports exit 3 with category
  `io`. Pinned by `test_imported_tokenize_failure_exits_4`,
  `test_imported_parse_failure_exits_5`, `test_missing_import_exits_3`,
  `test_unreadable_import_exits_3`, and
  `test_permission_denied_import_exits_3` in
  `test/test_import_error_stages.py`.
- Reversed constant match ranges are rejected (fixed). `case 10..1` and the
  const-alias, char, and match-expression forms each exit 6 with
  `invalid_pattern`; swap the endpoints to fix. Bounds known only at run
  time keep the prior rule: an empty range matches nothing through the
  if-chain. Pinned by `TestReversedConstantRanges` and
  `TestDynamicEmptyRange` in `test/test_match_ranges_break.py`. The
  constant form failed the Zig build, so the fix needed no packet.
- An unlabeled `break` or `continue` in a match case inside a loop
  targets the enclosing loop, in both the `switch` and if-chain
  lowerings (ledger L58). Pinned by `TestBreakInMatchCase` in
  `test/test_match_ranges_break.py`, which runs the binaries.
- SPEC text now matches the implementation; behavior unchanged. Updated
  sections: 2.1 source encoding, 2.2 comments, 2.3 identifiers, 2.5
  operators and folds and release nonwrap, 2.6 literal rules,
  float-to-int literal-only proof, 10.2 through 10.2.2 module
  identity and cycles and entry, 10.4 visibility intent, 11.2 stdlib
  generations, 12.1 token list, the limits table, and Appendix D
  escapes (`docs/SPEC.md`; phases 2a/2b/2c).
- Call, index, slice, field-access, unary, assignment and parenthesised
  nodes carry spans from their first to their last token.
- An undefined bare identifier in a `case` pattern exits 6 as an undefined-name
  error. Use `_` for a wildcard; bind from the scrutinee in the arm. Explicit
  capture syntax beyond tagged-union `case .tag(name):` is not approved.
- Failed JSON `stages.parse` entries include `message` and `span` alongside the
  top-level `error` object. Remaining parse diagnostics that lack source
  excerpts are tracked under PAR-14.

See [documentation verification](../site/docs/content-verification.md) for source,
commands, diagnostics, and supported alternatives. Historical audit reports retain
the earlier failures. Current repairs have regressions in `test/test_audit_type_boundaries.py` and
`test/test_audit_backend_repairs.py`.

## Planned work

Automatic memory is required for V1. Runtime help is allowed, but no production
mechanism is selected. The approval packet
[P-MEM-mechanism-selection](plan/packets/P-MEM-mechanism-selection.md)
compares static reuse, RC with cycle policy, tracing and hybrid options and
states the L38 measurement protocol; it needs ledger approval before any
runtime implementation. The Python compiler remains the bootstrap implementation;
Zig handles generated code and runtime/native integration. L73 also requires
structured concurrency, CPU AI, actual GPU execution and self-hosting parity.
These requirements remain unqualified. A package registry stays outside scope.
The [bootstrap parity proposal](plan/packets/P-BOOTSTRAP-parity.md) defines the
Python-to-A7 generation chain and proposes exact Zig comparison across all
three compilers. It is not approved. Python-specific CLI compatibility needs
a separate disposition before replacement; four report probes do not establish
self-hosting.

Safety alias and formal discharge work remains open on separate tracks. This
docs/tests/examples sync does not rewrite `a7/safety.py`; alias/lifetime gaps
in Current Surface and the [safety contract](SAFETY_CONTRACT.md) stay as
recorded until those tracks land.

Compile performance for the rewrite is measured, not optimized here: on the
2026-11-12 example corpus the Python frontend is ~3–43 ms while
`zig build-exe` release/fast is ~11–14 s per program. Use `a7 check --timings`
or `a7 build --timings`. Stage share on larger examples is roughly semantic
40%, codegen 27%, safety 20%, lex/parse under 10%. Rewrite work should attack
the Zig hop and safety-graph scaling, not deep parallelization of this tree.
Project baseline write-up: store doc `docs/perf-baseline-for-rewrite.md`
(Track 6).

Small standalone arena/RC foundation fixtures passed 134 checks using Debug
LLVM/LLD and a shared C-O0 allocation shim. The instrumented revision records
explicit-root aliasing, returned values, metadata and allocation-failure cleanup.
Independent review found weaknesses in its trace checker. A separate strengthened
checker accepts all 24 archived traces and rejects 710 count/layout mutations.
The frozen sources and original execution evidence remain unchanged.
These results do not qualify the seven required workload shapes, automatic A7
lowering or L38. Runtime category budgets are not measured stack bounds.
The W4 returned-record prototypes and independent C baseline passed 138 native
checks, including 24 workload cases. Each successful case checks all 334 returned
records after producer cleanup. Independent and GLM reviews found no source
blocker in this bounded fixture. Timing, complete peak memory and L38 remain
unqualified. The first W1 native attempt stopped at a Zig type-instantiation error before
any workload executed. After an explicit alignment type repair, the frozen retry
passed 112 checks, including 42 growth cases and controlled corruption tests.
The repaired program stops before publishing corrupted storage and frees each
allocation once. Timing, complete runtime storage and L38 remain unqualified.
The W2 shared-row and explicit-snapshot prototypes passed 75 Debug native checks.
Both live paths observe the update; the historical snapshot preserves its values.
Allocation and copy failures clean up verified owners. Named corrupt-count/queue
cases exit 6 with recorded residual storage rather than claiming safe reclamation.
Normal requested backing peaks are 48 bytes for C/arena and 144 for RC. These
exclude unmeasured runtime storage and do not qualify timing or L38. See the
[W2 record](audits/2026-10-07/memory-w2-verification.json).
W3 passes 75 Debug native checks of actual node cycles, deletion,
allocation-failure cleanup, intact-cycle abort and output failures.
Independent trace review confirms those bounded observations. Requested
backing peaks are 96 bytes for C/arena and 192 for RC; stack and other
runtime storage remain unmeasured. The RC prototype clears this
container's owned edges before releasing roots. General cycle collection,
timing and L38 remain unqualified. See the
[W3 record](audits/2026-10-07/memory-w3-verification.json).
W5 inline and fixed-pool C baselines each passed 84 bounded O0 native
checks: 31 small full traces, 47 invalid inputs and six output failures.
Archived outputs match the independent timestamp model. Their declared
storage inventories are 651 and 475 bytes; these are not measured peaks.
The two C sources also passed 24 large correctness cases at 10,000 and
100,000 accesses: 20 full traces and four summary traces across 31 commands.
The audit replayed exact rows and stdout and retained 162,447,636 stream bytes,
about 155 MiB. The auditor authored the inline C baseline and reviewed the pool;
this is evidence reconciliation with a shared contract/layout oracle, not a new
independent implementation. See the
[large C record](audits/2026-10-07/memory-w5-large-verification.json).
The corrected arena/RC contract and source are frozen and independently
reviewed. The first Debug preflight failed while Zig compiled the object,
with SIGSEGV before linking or any workload execution. The core shows an
unmapped read in a memory-copy-shaped loop; the compiler subsystem and root
cause remain unresolved. That attempt proved no native behavior.
See the [managed preflight failure](audits/2026-10-07/memory-w5-managed-preflight-failure.json).
An exact fresh-cache repetition also exited with SIGSEGV. Changing only the
object compiler's backend flag from `-fllvm` to `-fno-llvm` produced an object.
This diagnostic does not identify the faulty compiler component or prove a fix.
The [backend diagnostic](audits/2026-10-07/memory-w5-zig-backend-diagnostic.json)
records both results. A fresh Debug build then linked and passed six native
controls: arena and RC, each with zero accesses, six accesses, and loader failure
at access one. All stdout and complete stderr matched the unchanged matrix.
The [managed smoke record](audits/2026-10-07/memory-w5-managed-smoke.json)
preserves eleven commands and the bounded C ABI and stream evidence. This uses
Zig's alternate object backend; it is not A7 self-hosting or a production choice.
Observer v2 closes the reviewed storage-touch source defect; native allocator
interception and ABI checks remain outstanding. Normal observer build preparation
was rejected by an automatic safety filter; no build or completed review resulted.
The [preparation record](audits/2026-10-07/memory-w5-observer-preparation-block.json)
preserves that blocker. Optimized execution,
full memory accounting, performance and L38 qualification remain pending.
The [small native record](audits/2026-10-07/memory-w5-verification.json)
preserves the earlier bounded checks.
Canonical Option/Result and typed existing stdlib hooks are integrated. The frozen
compiler/package gate passed 3,826 tests with one expected failure and all 11
checks. The release wrapper then failed a stale generated docs manifest. After
regeneration, site and remaining dependency/static checks passed separately;
all compiler, test and package source bytes were unchanged. The
[qualification record](audits/2026-10-07/stdlib-b2-verification.json) preserves
both results. Readonly V3 is now integrated after its full release gate.
It uses implicit-borrow annotations and distinct Boolean/integer environment
keys. These fix the isolated V2 candidate's valid-call rejection and unsafe-call
acceptance. Independent review checks 16 sources across three snapshots; GLM
review matches 37 matrix cases and preserves 126 prior results. Six valid native
controls pass across all three profiles. Caller-local selectors and summaries
outside the existing work certificate can still leave unsafe reads unresolved.
The compiler does not treat those unresolved predicates as safety proofs.

The compiler also checks the original executable entry declaration against
its complete readonly summary. It rejects a represented nil read reached through
a known local selector. `--lib` has no implicit executable root. General
caller-local Boolean and effect proofs remain incomplete.
The check retains existing entry-signature diagnostic priority. Its callee
origin text reports source filename, line and column.
Independent compile-only review found six new rejections in 26 paired sources;
15 jointly accepted sources emit identical Zig. This does not qualify native
behavior or close the unresolved cases above. The native controls establish
successful empty-output execution in three profiles, without measuring
retained optimized work. The first full gate failed a test hook that did not
forward the new keyword argument. Its two-line repair preserved all state-size
assertions. The fresh full release gate passed 3,918 tests with one expected
failure, all 11 compiler/package checks, the site, dependencies and static
checks. All 1,621 frozen source files remained unchanged. The
[entry verification record](audits/2026-10-07/readonly-entry-verification.json)
preserves both gate results and the independent/GLM reviews.
The [delivery roadmap](plan/delivery-roadmap.md) owns their work order and exits.

## Audit evidence

The [audit index](audits/README.md) separates dated findings from current checks.
A passing example suite does not establish that all accepted programs are safe
or that the compiler implements the full specification. The
[execution plan](plan/execution.md) tracks correctness repair and approval packets.
