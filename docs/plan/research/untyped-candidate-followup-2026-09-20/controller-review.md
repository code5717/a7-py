# Controller review of the numeric follow-up

Date: 2026-09-20. Status: isolated prototype evidence. The proposed language
change is not implemented in the production compiler and is not release-qualified.

The follow-up corrects reproduced overflow, double-rounding and exact-division
failures in the first candidate. [The CLI report](REPORT.md) describes the
bounded change and preserves its failures, fixes, source snapshot and commands.
It does not establish every rule in the
[language packet](../../packets/P-TYP-forward-globals.md).

## Independent checks

The controller froze the final compiler in `review-candidate-2` before running
these checks. The source snapshot and hash inventory are archived alongside
this report.

- [IEEE stored-bit verification](../untyped-ieee-verification-2026-09-20/README.md)
  passes 17 accepted cases in both Debug and ReleaseFast. Two finite-overflow
  cases reject at A7 stage with no new artifact. The expected bits were stated
  independently. A documented edit to the generated Zig observes stored bits;
  it does not qualify A7 formatting.
- [The context matrix](context-results.json) records 27 ordinary CLI cases and
  runs accepted outputs in both native profiles. It confirms exact decimal
  comparison, direct rounding, finite intermediate cancellation, typed wrapping
  and supported fitting destinations. Rejected index, array-length and pattern
  cases remain implementation gaps under the proposal.
- [The corpus comparison](corpus-comparison.json) uses the original 255 sources
  and verifies their hashes. Acceptance changes from 135 to 136. One previously
  rejected literal-fitting reproducer becomes accepted. Thirteen files have
  generated-code or diagnostic changes. This scan compiles sources only; it
  does not execute archived security reproducers or establish native behavior.
- [Formatting probes](formatting-results.json), compared with the
  [baseline](../untyped-formatting-baseline-2026-09-20.json), expose a rejection
  absent from that file inventory. Printing the bare integer quotient
  `9007199254740993 / 1` currently works. The candidate rejects the proposed
  `i32` default. An explicit `i64` variable preserves the output in both compilers
  and both profiles. The inventory excludes source strings in Python tests.

The first corpus rerun accidentally included 20 newly archived research
fixtures. Its [result](inventory-drift-results.json) is preserved but excluded
from the comparison. The corrected runner uses the original
[inventory](frozen-corpus-inventory.json). Those research sources are preserved
in the first candidate's archive instead of adding runnable `.a7` files to the
corpus during measurement.

## Regression disposition

The CLI reports 52 selected passes and one stale recursion-allowlist failure
that also reproduces on the baseline. Two other original test sources do not
pass unchanged. Candidate copies now use explicit wide intermediates because
of the proposed formatting default. Their old failures and the test diff remain
in the archive. This is a compatibility change, not a baseline defect.

Separately, the controller removed the two obsolete semantic-validator entries
from the production recursion test's exception list. Those functions had already
been converted to iterative traversal. The focused command
`.venv/bin/python -m pytest -q test/test_no_recursion.py test/test_iterative_return_analysis.py`
passed 41 cases. This bookkeeping change does not promote the constant prototype.

## Work still required

GLM found repeated diagnostics for a failing global initializer. The controller
[reproduced it](duplicate-diagnostic.json) with `BAD :: 1.0 / 0.0`. The candidate
exits 6 with no artifact, but prints the same located error three times. Failed
evaluation must be recorded once and propagated without repeating the error.

Untyped declarations still receive provisional default-f64 materialization.
The candidate therefore does not qualify a binding with a huge exact value
that becomes representable only after later arithmetic. Exact bitwise and shift
operations, several fitting contexts, target-width handling and complete
dependency diagnostics remain open.

The GLM resource policy is a proposal. No candidate enforcement or resource
qualification exists. The full compiler/package and release gates have not run
for this prototype. Native evidence is limited to this host and Zig 0.16.0.

[GLM's completed candidate review](../untyped-candidate-glm-2026-09-20/README.md)
records the diagnostic finding, a clarification about exact comparisons without
float fitting, and an unconfirmed typing concern. Follow-up source inspection
did not substantiate that concern. It does not replace full integration checks.

The source archives, scripts, results and their SHA256 manifest preserve the
experiment. Several scripts retain their original temporary-directory paths;
read those paths before reproducing a run.
