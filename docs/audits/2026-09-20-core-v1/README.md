# Core V1 implementation evidence

Status: implementation in progress. Three combined release gates passed their
recorded source snapshots. The third includes the final formatter repair. Four
external reviews completed for those changes. Further correctness candidates
remain isolated while their tests and reviews run.
This batch does not qualify V1 for production.

## Scope and provenance

The source baseline is the complete dirty working tree, not HEAD alone.
`baseline.json`, `baseline-inputs.json` and `baseline-status.txt` identify it.
The preserved source archive is at
`tmp/v1-core-implementation-tycajqwt/baseline-source.tar.gz`.
`gate-start-source-hashes.json` identifies compiler and verifier code for the
first gate. `release-checks.log` holds its output. It passed 2,162 pytest cases,
43 examples, both 43-artifact profiles, 61 error-stage checks, docs, secrets,
package installation, site checks and dependency/static audits. Compiler and
verifier hashes remained unchanged during that run.

`final-gate-start-hashes.json` identifies the combined follow-up source and tests.
`final-release-checks.log` records 2,171 passing pytest tests and a complete gate
pass. The original unsafe SAF-4 case now rejects, and independent safe controls
retained identical generated Zig. Installed artifacts exercise all new CLI
workflows. GLM review 3 passed this scope.

The formatter follow-up then passed 106 integrated checks and GLM review 4.
`verified-source-hashes.json` identifies this final compiler/test/script source.
`verified-release-checks.log` records the third complete gate pass, with 2,174
pytest tests, 43 examples, both 43-artifact profiles, 61 error-stage checks,
installed wheel/source-distribution workflows, site checks and audits. All
recorded compiler, test and verifier hashes stayed unchanged during that run.

This batch implements iterative module loading, type display and console labels,
selected Zig lowering repairs, installed native distribution checks, CLI workflows
and one local/CI release command. Independent checks are recorded in [module loading and type display](module-types.md),
[console and backend repairs](console-backend.md), and
[release and CLI verification](release-cli.md).

## Remaining release blockers

- Current safety probes still accept SAF-2, SAF-3, SAF-6 and SAF-8. See
  [post-repair revalidation](critical-safety-after-saf4.json).
- An unused A7 loop label can cause a native build failure. See the
  [failure and control](unused-loop-label.json).
- Scope-aware constant usage and shadowing remain open as D2 in the
  [backend review follow-up](backend-glm-followup.md). No blanket-discard workaround
  was accepted.
- Browser acceptance is blocked. Neither browser-harness nor the independent CUA
  inventory provides a working browser. No screenshots or visual pass are claimed.
- Compiler recursion remains in parsing, checking, safety, emission and type
  operations. Deep helper tests do not prove a deep full pipeline. The same
  low-recursion test fails under `python -m pytest` and passes through the pytest
  entry point. See the [paired check](recursion-launcher-check.md).
- The forward-global typing packet is pending approval. It changes an accepted
  float-to-integer program into a type error.
- Alias/lifetime safety is incomplete. The preserved memory probes show accepted
  double deletion through aliases and a slice returned from a local array. These
  unsafe binaries were not executed.
- Automatic memory, complete module/generic behavior, errors, collections and
  native bindings need further implementation and acceptance evidence.
- The C performance and live-memory limits have not been qualified. AI, multicore,
  GPU execution and the A7-written V2 compiler remain later work.

Broad code cleanup and documentation expansion follow the approved plan. Comments
needed to explain new traversal and output-protection logic are included now.
