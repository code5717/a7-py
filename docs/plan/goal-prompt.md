# CPU/compiler continuation prompt

Run this prompt from the repository root. It resumes the approved plan and
preserves the GPU deferral. Current status and remaining work stay in
[STATUS](../STATUS.md) and the [delivery roadmap](delivery-roadmap.md).

```text
Implement the approved A7 completion plan in this repository. Read AGENTS.md,
README.md, docs/RELEASE.md, docs/STATUS.md, docs/plan/delivery-roadmap.md and
latest decisions in docs/plan/decisions.md before editing. Inspect current git
status, active task-owned processes and the latest verification records.
Preserve existing changes and unrelated sessions. Do not assume a handoff's
claims describe the current source.

Maintain affected docs in the same task. Use docs/inspirations.md to trace
ideas from other languages, add new research links and keep adoption status
consistent with the ledger. Preserve historical evidence and distinguish
unexecuted proposals from verified behavior.

Cyber scans are excluded by the user's instruction. Do not run auxiliary
security, secrets or dependency-vulnerability scans. Continue compiler
correctness tests, native controls, packaging and documentation checks.
Respect the current filesystem and network permissions. If a required write
or external review is unavailable, preserve the failure and report the limit;
do not change HOME or tool state directories to bypass it.

Continue CPU/compiler work. GPU execution is deferred under L75. Review
docs/research/2026-10-07-zig-gpu-support.md as research evidence only. Do not
submit GPU work, choose a production GPU backend or count enumeration and
compile-only probes as execution qualification. L73 still requires actual GPU
execution before eventual V1 publication, so this CPU continuation cannot
establish full V1 completion. L73 includes core language, automatic memory,
useful libraries and tools, structured concurrency, CPU AI, actual GPU execution
and self-hosting parity. Keep that publication boundary intact.

Follow the delivery roadmap's ordering. Repair confirmed critical/high compiler
findings, preserve iterative compiler traversal and retain source-recursion
rejection. Use explicit stacks and worklists; do not expand the recursion
allowlist. Reconcile original audit witnesses and paired valid controls before
closing a finding. Passing existing tests does not override a counterexample.

L74 already approves rejecting nil user-field ptr access, repeated reference-
field deletion and use of a deleted allocation through direct aliases with
semantic exit 6. Preserve guarded accesses, aliases used before deletion,
independent fields and allocations, and reassignment to fresh allocations.
Known gaps in array/selected aliases, callee effects and escaping allocation
lifetimes remain release blockers until reproduced and repaired. A precise
callee effect model must preserve evaluation order, actual-argument aliasing,
ordered live/non-nil uses and stores/deletes, and mark unsupported functions
explicitly. Never silently classify unknown effects as read-only.

Read docs/plan/research/goose-2026-10-17.md and
docs/plan/packets/P-GOOSE-direction.md for the user's Goose-informed feature
preparation request. Keep Zig; C export and TinyCC integration are deferred.
Prepare the roadmap's GOOSE-1 through GOOSE-6 contracts and bounded experiments.
Do not treat Goose slogans, inspected fixtures or aggregate benchmarks as A7
proof. Preserve L37, L38, L42, L68 and L74 until an explicit new decision changes
them. Implement only approved packets; preserve existing runtime function
values, Result/defer behavior and the recursion ban. Keep C performance controls.

Existing language decisions remain approved, including L69 module scopes,
L76 file-local imports and L68 stdlib architecture. Before any new syntax or
behavior change outside an existing approval, present current behavior,
proposed behavior, a concrete A7
example and compatibility impact. Record the user's decision. Continue work
that does not depend on that decision. Do not invent automatic-memory,
concurrency or tensor contracts to bypass a missing approval.

Use independent agents with disjoint file ownership. Use OpenCode
zai-coding-plan/glm-5.3 for substantive reviews, at most five concurrent model
sessions. Use zai-coding-plan/glm-5.3-flash for very small tasks, at most 25
concurrent model sessions. Count each run and its active built-in subagents
toward the corresponding model limit. Give detailed prompts: immutable source
identity, exact scope, allowed and forbidden files/actions, concrete checks,
expected results, evidence
requirements and output format. Maintain the exact external-reviewer role and
recursion guard required by AGENTS.md, one reviewer identity per batch, and
controller-managed worker counts. Keep normal tools, web search and built-in
subagents available. Do not impose a CLI turn count or elapsed-time limit.
Record failed invocations as failures, not completed reviews. Verify the CLI's
actual project path and source imports before trusting probe output. Set the
explicit project directory and matching PWD for isolated reviews, then verify
the running process and recorded session directory. Preserve permission
denials and distinguish unperformed checks from completed checks.
Copy review packets by their exact manifested paths, including nested fixture
directories. Rehash every entry before launch. Preserve the original envelope
when adding a later supplement, and distinguish file availability or hashing
from observed semantic inspection.

Use separate Claude CLI reviewers for major features and unimplemented tracks.
Read docs/plan/claude-feature-reviews.md and its execution ledger before launching
or resuming a review. Preserve one identity per feature. After reconciling feature
findings, request a full-project review of interactions and remaining V1 gaps.
Repeat relevant reviews after substantial integration and before qualification.
Apply the external-reviewer guard. Reconcile advice against primary evidence;
it supplements GLM reviews and local checks. Preserve provider failures and unread
areas. A retrying or failed request does not count as a completed review.

Keep memory experiments faithful to their frozen workloads. Review competitive
C representations independently, including zero-heap choices where appropriate.
Separate semantic models, source checks, native correctness, optimized execution
and full runtime accounting. L38 remains a per-workload 1.10 limit; unapproved
additive allowances and weaker baselines cannot replace it.

Reserve CPUs 16-23 on this 24-CPU machine. Use no more than eight pytest workers
in total and one full native release gate at a time. Never use -n auto. Pin
build/test jobs within CPUs 0-15. Verify fixes with meaningful targeted tests,
then qualify a frozen copy of the combined source. The current
run_release_checks.sh invokes excluded scans, so do not run it unchanged.
Use run_all_tests.sh --skip Secrets for compiler/package qualification, or
run its permitted checks directly when the environment requires it. Run the
permitted release-identity and site checks separately. Record excluded and
unperformed checks; do not claim the complete release wrapper passed.
Pytest also contains four test_release_tooling.py::test_secret_scan_* tests
that invoke the scanner. Deselect their exact node names as recorded in
tmp/v1-completion-2026-10-07/match-pattern-qualification/run.json. Preserve
ordinary compiler safety and artifact-integrity tests. Report the scanner
exclusions instead of claiming an unfiltered full-suite pass.
Record the source manifest, command, environment, exit status and full output.
Later source edits require their own qualification; never transfer a passing
gate claim from an older snapshot to newer code.

Simplify the repository as requested on 2026-10-16. Reduce duplicate entry
points and stale navigation, give current guidance a clear home, and separate
historical plans from current work. Inspect inbound references before moving
files; update imports, package data, CI, tests and documentation together when
a move needs them. Preserve useful compatibility commands and historical
evidence. Do not move cited scratch paths or files used by active gates.
Prefer a small coherent cleanup over mass renames or new wrapper layers.
Verify behavior and package contents after executable layout changes.

Keep README, SPEC, STATUS, CHANGELOG, release guidance and site exports aligned
with implemented behavior. Run site export/check commands after site changes.
Published evidence links must resolve from tracked files. Keep raw scratch in
dated tmp directories without moving paths already cited by documentation.
Keep package/release identity at its qualified value; do not label this work
1.0.0 or publish V1 while any L73 requirement remains unqualified.

At completion, report what changed, exact verification boundaries and remaining
blockers. Include reviewed commit/push status and a runnable continuation goal
prompt. Do not call a passing compiler gate full V1 acceptance.
```
