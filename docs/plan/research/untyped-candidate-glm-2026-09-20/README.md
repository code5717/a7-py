# GLM review of the final numeric prototype

Date: 2026-09-20. OpenCode model `zai-coding-plan/glm-5.3`, process exit 0.
Advisory review of frozen `review-candidate-2`. No language approval, production
implementation, resource qualification or release qualification follows from it.
No provider limit or authentication failure was reported.

[The final report](REPORT.md) and [transcript](transcript.txt) preserve the
review. [The prompt](prompt.txt) includes the external-reviewer recursion guard.
[The probe archive](reviewer-probes.tar.gz) preserves the available scripts,
sources, emitted Zig and logs. Probe corrections and invalid early reference
results remain visible in the transcript. The reviewer performed no native
builds; the controller's independent IEEE report provides native evidence.

The controller reconciled these findings:

- F1 is confirmed. One global zero-division error appears three times. The
  [controller reproduction](../untyped-candidate-followup-2026-09-20/duplicate-diagnostic.json)
  records exit 6 and no artifact. It remains an implementation blocker.
- F2 is a documentation clarification. Exact comparisons need no float
  materialization, so `1e400 == 1e400` may evaluate to true. Rejecting `1e400`
  means rejecting its implicit fitting to an overflowing float destination.
  The proposal now states the distinction.
- F3 is not substantiated by the follow-up source review. Both operands are
  visited before the early return. Fitting records fractional and range errors;
  the outer visitor records the result type. The skipped arithmetic block has
  compatibility and widening checks, not proof annotations. Compiler orchestration
  rejects accumulated type errors before later passes. The concrete integral
  guard excludes array and generic peers. These facts address the suggested
  bypass; they do not qualify every numeric context.

F3 source evidence is in frozen `type_checker.py` lines 1251-1252, 1327-1338 and
3115-3125, and `compile.py` lines 342-355. The type-checker SHA256 is
`a41e67b21b5a82b87395e305ab1e3c40de7ac6a9d621d093d468326c225e2345`.
An independent Codex subagent compared the branch and the controller inspected
those paths. No additional tests were run for this source-only disposition.

The report's helper experiments support the tested numerical behavior only.
Its final claim that the largest probe values were about 460 bits is not used
as a measured resource bound. The transcript describes larger exponent-scaled
rationals. These experiments do not qualify compiler resource enforcement.
