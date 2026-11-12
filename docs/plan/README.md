# A7 v1 plan

Start with [Status](../STATUS.md) for implemented behavior and gaps, then the
[delivery roadmap](delivery-roadmap.md) for work order and completion evidence.
Those two files own current todos. This index points to decisions, research and
history; it does not maintain another task list.

## Current delivery sequence

| Need | Start here |
| --- | --- |
| Continue the compiler work | [CPU/compiler continuation prompt](goal-prompt.md) |
| Read the latest evidence snapshot | [October 18 handoff](HANDOFF-2026-10-18.md) |
| Check an approval and its exact limits | [Decision ledger](decisions.md) |
| Check current enforcement | [Safety contract](../SAFETY_CONTRACT.md) |
| Prepare a proposal | [Decision packets](packets/) |
| Study automatic-memory design | [Memory plan](memory.md) |
| Run feature-specific Claude audits | [Claude review protocol](claude-feature-reviews.md) |
| Find advisory studies | [Research index](research/README.md) |
| Trace ideas from other languages | [Language inspirations](../inspirations.md) |
| Find compiler and release commands | [Release checklist](../RELEASE.md) |

The ledger records user decisions; research does not grant approval. A planned
feature or an isolated passing check is not a qualified release. L73 defines the
V1 publication scope. GPU execution is deferred in the current workstream; its
required publication evidence is not waived. Use the continuation prompt and
roadmap for the active CPU/compiler scope and review limits.

## Where things go

- Current todos and dispositions: [Status](../STATUS.md) and the
  [delivery roadmap](delivery-roadmap.md).
- User decisions: [ledger](decisions.md), preserving the user's wording and scope.
- Session evidence: dated `HANDOFF-<date>.md` files. Preserve prior snapshots;
  record new progress in Status and the roadmap.
- Advisory research: [research/](research/README.md). Keep proposals distinct
  from approved behavior and observed implementation.
- Scratch and raw evidence: repository `tmp/<topic>-YYYY-MM-DD/` directories.
  Preserve every path cited by docs; do not add loose top-level scratch files.

## Historical plan and audits

The [archived plan](archive/v1-plan-before-2026-10-16.md) preserves the previous
index's full planning text, dated probes and proposed work tracks. Its original
start date is 2026-09-15. Historical failures and proposals are not fresh
reproductions or current approvals. The [execution record](execution.md),
[language audit checklist](audit/language-audit-checklist.md) and
[historical open items](audit/open-items.md) retain their existing locations.
Older handoffs and research files have not moved.

The links below preserve the old section anchors for existing citations. Read
the archived observation with its date, then check its current disposition in
the ledger and roadmap.

- <a id="summary"></a>[Summary](archive/v1-plan-before-2026-10-16.md#summary)
- <a id="direction"></a>[Direction](archive/v1-plan-before-2026-10-16.md#direction)
- <a id="approval-gates"></a>[Approval gates](archive/v1-plan-before-2026-10-16.md#approval-gates)
- <a id="g1-floating-point-details"></a>[G1. Floating-point details](archive/v1-plan-before-2026-10-16.md#g1-floating-point-details)
- <a id="g2-ownership-and-reference-surface"></a>[G2. Ownership and reference surface](archive/v1-plan-before-2026-10-16.md#g2-ownership-and-reference-surface)
- <a id="g3-numeric-rules-beyond-wrapping"></a>[G3. Numeric rules beyond wrapping](archive/v1-plan-before-2026-10-16.md#g3-numeric-rules-beyond-wrapping)
- <a id="g4-function-values-and-the-recursion-ban"></a>[G4. Function values and the recursion ban](archive/v1-plan-before-2026-10-16.md#g4-function-values-and-the-recursion-ban)
- <a id="g5-errors-matching-and-composite-values"></a>[G5. Errors, matching and composite values](archive/v1-plan-before-2026-10-16.md#g5-errors-matching-and-composite-values)
- <a id="g6-source-text-modules-and-tooling"></a>[G6. Source text, modules and tooling](archive/v1-plan-before-2026-10-16.md#g6-source-text-modules-and-tooling)
- <a id="g7-concurrency"></a>[G7. Concurrency](archive/v1-plan-before-2026-10-16.md#g7-concurrency)
- <a id="g8-ai-contracts"></a>[G8. AI contracts](archive/v1-plan-before-2026-10-16.md#g8-ai-contracts)
- <a id="g9-release-posture"></a>[G9. Release posture](archive/v1-plan-before-2026-10-16.md#g9-release-posture)
- <a id="work-tracks"></a>[Work tracks](archive/v1-plan-before-2026-10-16.md#work-tracks)
- <a id="documentation-defects-for-track-0"></a>[Documentation defects for track 0](archive/v1-plan-before-2026-10-16.md#documentation-defects-for-track-0)
- <a id="defects-reproduced-in-wave-0"></a>[Defects reproduced in Wave 0](archive/v1-plan-before-2026-10-16.md#defects-reproduced-in-wave-0)
- <a id="ai-sequence"></a>[AI sequence](archive/v1-plan-before-2026-10-16.md#ai-sequence)
- <a id="test-plan"></a>[Test plan](archive/v1-plan-before-2026-10-16.md#test-plan)
- <a id="assumptions"></a>[Assumptions](archive/v1-plan-before-2026-10-16.md#assumptions)
