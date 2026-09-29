# Controller disposition of GLM review

The [first review](glm-review.md) and [closure review](glm-closure.md) are preserved
verbatim. Their compiler and scanner checks support this batch. They remain
advisory; the following corrections control interpretation of their provenance
claims.

- F1, F2 and F6 prompted current conversion-status text, explicit scanner limits
  and an unambiguous cache oracle. The scanner edit changed only its module
  docstring. Independent AST comparison and focused tests confirm that its
  executable code stayed unchanged.
- F3 concerns the temporary v1 report. Delivered evidence uses the frozen v2
  report, patch and hashes. F5's forward links resolve in the delivered tree.
- F4 was unsupported. The controller ran the baseline gate in this session and
  verified all recorded paths unchanged before editing. GLM retracted F4.
- The closure report's PDF provenance claim is also incorrect. All six deleted
  PDFs have `sha256: null` in the original manifest. The manifest did not read
  their Git object contents. A [direct recheck](review-provenance-check.json)
  finds 1,045 unchanged paths and ten expected changed files, not 1,039 and 16.
  Missing paths compare as null on both sides. They are absent from the local
  source archive.
- The closure report attributes the historical 2,629 count to whole-tree
  collection. The cited notes document an earlier collection problem but do
  not establish that count's cause. This batch makes no such causal claim.
  Its fresh baseline has 2,087 tests; the added tests raise collection to 2,106.
- GLM corrected its other arithmetic errors. There are 28 remaining function
  groups and 44 tests in `test_iterative_traversal.py`.

No review found a behavior regression in the three converted helpers. GLM's
randomized differential checks covered 300 unary chains, 400 mutation targets
and 120 scope trees. Scanner limitations remain qualification limits, including
confirmed missed cycles for the explicitly unmodelled Python forms. This report
does not qualify the full compiler or the entire V1 roadmap.

## Module-packet review follow-up

The resumed GLM review completed. The controller reran all six cited failing
fixtures and confirmed the diagnostics recorded in the packet. The packet now
includes non-entry importers, qualified annotations/literals and global alias
clashes. The review's broad claim that all chains of depth two or greater fail
is narrowed to the measured qualified-use cases. The imported annotation parse
error is reported through semantic exit 6; the entry-file literal fails at exit 5.

An external-directory guard rejected the reviewer's mistaken relative path.
The same session completed using absolute in-repository paths. No outside access
was granted. The controller's first rerun used incorrect CLI flags and returned
usage exit 2; corrected invocations produced the recorded results. Both attempts
remain in the source/results archive. These are compiler-only checks.
