# Claude feature review protocol

The user requested separate Claude CLI audits for major language features and
unimplemented V1 tracks on 2026-10-17. Each review is advisory. STATUS and the
delivery roadmap retain ownership of work items and dispositions.

## Review coverage

The first campaign uses these separate reviewers:

| Reviewer | Scope |
| --- | --- |
| arrays | Fixed arrays and indexing |
| references | References, aliases and deletion |
| generics | Generics and specialization |
| lexical_declarations | Source syntax, declarations and name resolution |
| numerics | Numeric and scalar semantics |
| records_adts | Records, unions, enums and matching |
| slices_strings | Slices and strings |
| control_flow | Control flow and deferred cleanup |
| functions | Functions, calls and callbacks |
| modules | Modules and imports |
| stdlib_errors | Standard library, IO and errors |
| backend_ir | Compiler architecture, typed IR and backend |
| tooling_release | CLI, packaging, docs and release qualification |
| automatic_memory | Unimplemented production automatic memory |
| collections | Unimplemented collections and allocation APIs |
| concurrency | Unimplemented concurrency and native boundaries |
| cpu_ai | Unimplemented CPU AI, tensors and autodiff |
| gpu | Deferred GPU support research |
| self_hosting | Unimplemented A7 self-hosting compiler |

A full-project review follows reconciliation of feature findings. It checks
interactions, conflicting assumptions and unowned requirements. Feature reports
alone do not establish whole-project acceptance.

## Preparation and reconciliation

1. Copy the intended source and record file hashes. Distinguish the live tree
   from isolated candidates and previously qualified snapshots.
2. Give each reviewer the exact external-review guard from AGENTS.md, a stable
   identity, its feature contracts, source entry points and related tests.
   Preserve normal tools, web research and built-in subagents. Respect the
   current scope exclusions and deferred GPU execution.
3. Request file-and-line evidence, minimal failing examples, paired valid controls,
   test gaps and explicit unread areas. For unfinished features, request current
   approval status, design questions, dependencies and executable acceptance cases.
4. Capture invocation arguments, session identity, stdout, stderr, provider errors
   and terminal exit. Use small concurrent batches. Do not impose a time or turn
   limit. Let active reviewers finish naturally.
5. Verify snapshot hashes after the campaign. Reconcile every finding against
   primary source and appropriate local checks. Record confirmed defects and
   unfinished requirements in STATUS and the delivery roadmap. Obtain explicit
   language-change approval when a recommendation changes syntax or behavior.

A returned report awaits reconciliation. A provider failure is an incomplete
review. Source review does not establish runtime behavior or release acceptance.

## First campaign evidence

Evidence directory:
`tmp/v1-completion-2026-10-17/claude-feature-reviews/`.
The 1,722-file source manifest is pinned by SHA256
`6e936c81ffc99f80e489b99865029f7fe7dc37d5d192604ea92cfc24f97d0224`.
It captures the dirty live source before this protocol was added.

`reviews.json` records 19 detailed prompts, reviewer identities, session IDs and
execution states. `run.py` runs at most three Claude processes. Arrays,
references and generics form the first batch. Each feature directory retains
its prompt and any process output. A failed invocation stops further queued
launches; active siblings finish normally. Remaining packets stay available for
a later attempt. The controller checks all copied source hashes before and after
execution. Review reports remain unqualified until reconciled.

The first three invocations ended with CLI exit 1 and API DNS error `EAI_AGAIN`.
No review completed. Sixteen packets remain unlaunched. All source hashes and
modes passed the controller's terminal audit. The campaign REPORT.md records
the failures; controller exit 0 means recording finished.
