# A7 audit and completion proposal

Status: audit record from 2026-09-14 (baseline `701c67936c70ad2b0608326e23e56cc5d38c9fdb`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

A7 is not ready for v1 qualification. The audit found compiler correctness,
diagnostic, artifact-handling, memory-proof and product gaps that the existing
passing gate did not expose. Start with the [proposed completion roadmap](completion-roadmap.md)
and the [coordinator verification](root-review.md). The [detailed audit matrix](audit-matrix.md)
records the wider investigation and acceptance scope. It is not a checklist of
completed verification.

Note (2026-09-16): the roadmap's v1 boundary is replaced by ledger L1 and L7, and
its memory direction by the [memory plan](../../plan/memory.md). The current plan
is the [v1 plan](../../plan/README.md); it keeps the roadmap's correctness phases
and exit evidence.

## Current outcome

| Evidence | Result | Limit |
| --- | --- | --- |
| Original full release gate | 12/12; 2,511 pytest passes | Before new regressions |
| Current full release gate | 11/12; 12 pytest failures, 2,515 passes | Known failures remain visible; no v1 acceptance |
| Sixteen new meaningful cases | 12 fail, four pass | Public CLI, real files and native behavior; no mocks or failure masking |
| Docs cleanup | Information preserved; navigation and anchors improved | Historical broken source citations remain documented |
| Site build and lint | Pass | Does not establish usability or visual quality |
| Generated site links | 259 checked across 10 HTML files, pass | Search-index fragments have separate defects |
| Browser acceptance | Unverified | Browser connection unavailable; fallback permission pending |
| Project dependency qualification | Incomplete | Existing pip-audit command audited its own tool environment |

The configured gate and the alternate pytest invocation are separate evidence.
The alternate invocation adds a low-recursion test failure. Do not combine their
counts; see the coordinator report.

## Findings that drive the roadmap

| Finding | Evidence status | Next action |
| --- | --- | --- |
| Source overwrite and false artifact reporting | Confirmed by real filesystem regressions | Reject collisions before writes; report current invocation artifacts only |
| Parser drops main after recovery and exits successfully | GLM finding independently replayed by coordinator | Fail compilation after source errors; preserve diagnostic collection if desired |
| Stale proof facts across mutation, scope and calls | Dedicated GLM source review and corrected reachable native compile checks | Repair conservative fact propagation; GLM owns cybersecurity validation |
| Exact integer folding changes representable i64 values | Native output mismatch in Debug and ReleaseFast | Use exact integer semantics; keep separate from overflow policy |
| Valid local and loop names generate invalid Zig | Real native build regressions | Preserve declaration/use identity and backend naming constraints |
| Imported diagnostics lose stage or source origin | Public CLI and JSON regressions | Carry original file and span across module boundaries |
| A7 accepts invalid aggregate construction for Zig to reject | Coordinator A7 and native compile checks | Complete semantic validation before emission |
| Ownership, aliasing, deferred deletion, escaping storage and unions | Mix of GLM-confirmed acceptance defects and documented unfinished semantics | Agree the supported memory model and close its requirements. Note (2026-09-16): model direction set by ledger L15, L17–L19; see the memory plan |
| Dependency command audits the wrong environment | Inventory inspected by coordinator and GLM | Qualify actual locked project inputs before trusting audit success |
| Website version, transcripts, search and procedure structure | Source/generated-output findings reconciled across reviewers | Correct content and behavior; then run browser acceptance |

This table prioritizes work. It does not replace the detailed reports or claim
that every item in the audit matrix has been executed.

## Review records

External reports are advisory. Coordinator reconciliation takes precedence over
unsupported completion claims or proposed fixes in those reports.

| Area | Review and reconciliation |
| --- | --- |
| Compiler internals | [Codex compiler review](compiler-review.md), [GLM pipeline review](pipeline-glm-review.md), [coordinator checks](root-review.md) |
| Language and release contract | [Codex language review](language-contract-review.md), [GLM contract review](contract-release-glm-review.md) |
| Memory safety | [Dedicated GLM review and corrected evidence](memory-safety-glm-review.md). Dedicated Codex CLI stopped at a provider safety filter without its requested report. Cybersecurity follow-up belongs to GLM. |
| Cybersecurity | [Dedicated GLM report](security-glm-review.md), with coordinator reconciliation in [root-review.md](root-review.md). Preview evidence is local; deployed behavior and corrected dependency qualification remain unverified. |
| Tests | [Codex test review](tests-codex-review.md), coordinator's additional exact-integer regression, GLM contract review |
| Documentation preservation | [Cleanup report](docs-cleanup-report.md), [coordinator byte comparison](evidence/docs-preservation-coordinator.json), GLM contract review |
| Website | [Codex review](website-codex-review.md), [GLM review](website-glm-review.md), [reconciliation](website-reconciliation.md) |

Nine independent GLM-5.3-Flash website reports cover
[accessibility](website-flash-accessibility.md),
[performance](website-flash-performance.md),
[organization](website-flash-organization.md),
[interactions](website-flash-interactions.md),
[content](website-flash-content.md),
[SEO](website-flash-seo.md),
[typography](website-flash-design-typography.md),
[responsive design](website-flash-design-responsive.md), and
[design consistency](website-flash-design-system.md).
These are source and generated-output reviews. None substitutes for current
browser captures, assistive-technology checks or measured performance.

## Changes authorized during the audit

- Added the user's exact test-quality policy to `AGENTS.md`.
- Added a documentation index and authority qualifications, corrected SPEC TOC
  links, and kept public agent docs aligned. No historical document was removed.
- Added real regression tests for artifacts, diagnostics and native compiler
  behavior. Compiler and website implementation remain unchanged.
- Saved reviewer reports, reproductions and verification evidence in this directory.

## Evidence and boundaries

The [evidence directory](evidence/) contains both full-gate logs, regression output,
site verification, source-preservation inventory, provider limitations and PDF
extractions. The [reproduction directory](repros/) contains audit fixtures.
Some fixtures intentionally violate safety requirements. They are evidence for
compiler rejection checks, not examples to execute as native programs.

Seven historical pointer-syntax PDFs remain byte-preserved. Text extraction and
PDF structural checks are recorded in [the inventory](evidence/pdf-inventory.json).
Their old `.adr` and `.val` syntax proposals do not override current reference
rules. Extracted content review is distinct from visual layout review.

This audit does not establish remote CI success, published artifact correctness,
cross-platform qualification, browser acceptance, or universal memory safety.
The next decision is agreement on the roadmap, followed by implementation and
fresh integrated release evidence.

Note (2026-09-16): scope agreement now happens through the
[v1 decision ledger](../../plan/decisions.md) and the gates in the
[v1 plan](../../plan/README.md).
