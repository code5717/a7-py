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

Continue CPU/compiler work. GPU execution is deferred under L75. Review
docs/research/2026-10-07-zig-gpu-support.md as research evidence only. Do not
submit GPU work, choose a production GPU backend or count enumeration and
compile-only probes as execution qualification. L73 still requires actual GPU
execution before eventual V1 publication, so this CPU continuation cannot
establish full V1 completion.

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

Existing language decisions remain approved, including L69 module scopes,
L76 file-local imports and L68 stdlib architecture. Before any new syntax or
behavior change outside an existing approval, present current behavior,
proposed behavior, a concrete A7
example and compatibility impact. Record the user's decision. Continue work
that does not depend on that decision. Do not invent automatic-memory,
concurrency or tensor contracts to bypass a missing approval.

Use independent agents with disjoint file ownership. Use OpenCode
zai-coding-plan/glm-5.3 for substantive reviews, at most five concurrent runs.
Use zai-coding-plan/glm-5.3-flash for very small tasks, at most 25 concurrent
runs. Give detailed prompts: immutable source identity, exact scope, allowed
and forbidden files/actions, concrete checks, expected results, evidence
requirements and output format. Maintain the exact external-reviewer role and
recursion guard required by AGENTS.md, one reviewer identity per batch, and
controller-managed worker counts. Keep normal tools, web search and built-in
subagents available. Do not impose a CLI turn count or elapsed-time limit.
Record failed invocations as failures, not completed reviews. Verify the CLI's
actual project path and source imports before trusting probe output.

Reserve CPUs 16-23 on this 24-CPU machine. Use no more than eight pytest workers
in total and one full native release gate at a time. Never use -n auto. Pin
build/test jobs within CPUs 0-15. Verify fixes with meaningful targeted tests,
then qualify a frozen copy of the combined source using run_release_checks.sh.
Record the source manifest, command, environment, exit status and full output.
Later source edits require their own qualification; never transfer a passing
gate claim from an older snapshot to newer code.

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
