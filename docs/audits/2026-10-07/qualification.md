# Compiler repair qualification, 2026-10-07

The earlier pushed checkpoint `621f70c` passed the complete release gate with
3,374 tests and one expected failure. The current frozen manifest `04330ece`
passed 3,602 tests with one expected failure and the native checks. Its original
gate failed on missing Git metadata; all recovery checks passed on unchanged
sources. Both runs are preserved below. V1 is incomplete.

## Resumed baseline

The [verification record](baseline-verification.json) records these completed
commands against the frozen resumed baseline:

| Command | Observed result |
| --- | --- |
| `taskset -c 0-7 env PYTHONPATH=. uv run --locked pytest --tb=short -q -n 6` | Exit 0; 3,090 passed, 7 expected failures |
| `taskset -c 8-15 ./run_all_tests.sh --skip pytest` | Exit 0; 10 passed, 1 skipped |

The second run includes 51 examples in every profile, the error-stage matrix,
report-only benchmarks, docs/secrets checks, package build and native installed
wheel/source-distribution checks. It excludes the site and extra release checks.
The earlier October 4 full-release result is separate historical evidence.

## Intermediate repair gate

The [intermediate record](intermediate-verification.json) records
`taskset -c 0-15 env A7_PYTEST_WORKERS=6 ./run_release_checks.sh`, exit 1.
All 11 compiler/package checks passed: 3,205 pytest cases, 2 expected failures,
51 examples in every profile and native wheel/source-distribution checks.
The site check also passed. The gate then stopped at the Bun dependency audit:
`source-map-js@1.2.1` had high-severity advisory
[GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
Python dependency and static-security checks after that stage did not run.

The current lockfile updates only that transitive package to 1.2.2. The
[upstream release](https://github.com/7rulnik/source-map-js/releases/tag/v1.2.2)
identifies the indexed-source-map denial-of-service fix. The updated site passes
`bun run check` and `bun audit --audit-level=moderate`, which reports no known
vulnerabilities. This targeted repair does not turn the older failed gate into
a full-release pass. The separate combined checkpoint below contains the fix.

## Combined checkpoint

The [combined record](combined-verification.json) records exit 0 for
`taskset -c 0-15 env A7_PYTEST_WORKERS=6 ./run_release_checks.sh`.
All 11 compiler/package checks passed: 3,312 pytest cases, one expected failure,
51 example executions and 51 artifacts in each profile, plus native wheel and
source-distribution checks. Site checks, both dependency audits and Bandit passed.

This snapshot contains the dependency repair and earlier compiler changes. It
excludes the later checker statement worklist, joined-child dependency repair
and importer-local alias-clash validation. Their passing focused tests cannot
be combined with this older gate to claim a full pass for the current source.

## Reviewed checkpoint and fixture repair

The [reviewed record](reviewed-verification.json) records a failed pytest stage:
2 failed, 3,370 passed and one expected failure. Both failures came from stdlib
dispatch fixtures that reused their own file's import alias. L28 now rejects
those declarations. The run then passed all 51 example executions and was
stopped during debug artifact verification. Its process exit was -15; the
remaining release checks did not complete.

The repair keeps both original sources as explicit semantic-exit-6 tests.
Valid dispatch fixtures use a distinct import alias and retain their original
output checks. All 20 tests passed, including 16 native cases and four
compile-only cases. An independent Flash review found no issue in that patch.
Production compiler files did not change. The integration checkpoint below qualifies
the repaired test suite and current compiler together.

## Integration checkpoint

The [integration record](integration-verification.json) records exit 0 for
`taskset -c 0-15 env A7_PYTEST_WORKERS=6 ./run_release_checks.sh`.
All 11 compiler/package checks passed: 3,374 pytest cases, one expected failure,
51 example executions and 51 artifacts in each profile, 61 error-stage checks,
and native installed wheel/source-distribution checks. Site lint, type checks,
coverage, 12 tests, build, exports and local links passed. Bun and Python
dependency audits and Bandit passed. Benchmarks ran in report-only mode.

This snapshot includes the checker statement worklist, separate selected-child
lifetime dependencies, importer-local alias-clash validation and repaired
stdlib dispatch fixtures. The live compiler, tests, scripts, site and dependency
files match the frozen manifest. Later edits update qualification and review
records, STATUS and the roadmap; they do not change the tested compiler.

The qualified compiler checkpoint was committed and pushed as
`621f70cbebd9f4c842ea71a1b8c47894eb5f32ab`. Its compiler, tests, scripts, site and
dependencies match this snapshot. Later source changes need new qualification.
The generated research PDF remains outside that commit.

The remaining expected failure is scalar-reference printing, covered by the
unapproved [scalar-read proposal](../../plan/packets/P-REF-scalar-read.md).
The gate exercises specific valid and invalid programs. It does not establish
complete alias safety, per-module scopes, removal of all compiler recursion,
browser acceptance, GPU execution or V1 completion.

## Snapshot identity and local archives

The baseline and intermediate/review copies share HEAD `c8face6`, but contain
uncommitted changes. HEAD alone does not identify their contents. These manifest
hashes identify the saved per-file source records:

| Manifest | SHA-256 |
| --- | --- |
| `baseline-manifest.json` | `741e69dca433708e8c7a2432b4afb9fe706101f3c129a58ae7076847de64d4b7` |
| `batch-manifest.json` | `09119c9aa16945d354fb9e947e9bc0e6fa6439df4d87a443de9de593d032603e` |
| `review-manifest.json` | `febda822063c2d888a35a3bacaee5c111c83b4eae10dadbb5b6a2c453c4412d2` |
| `combined-manifest.json` | `a7b6b10259b391cb5c58999c8a20ed7f476cf0aef2552bfd4c4d36ca6197cba3` |
| `reviewed-manifest.json` | `c6b2321ea2ea6a04f6e5be821a56dbe5f311a2440af56444688aa0a68f2790c0` |
| `integration-manifest.json` | `b26fa15faf33cd3caf5248d5a5afa61e79e2dc5ee0fd9236b8ede20d1b41b287` |

Raw manifests and logs remain under the host-local ignored directory
`tmp/v1-completion-2026-10-07/`. The verification JSON's log/manifest fields are
archive filenames, not publication links. Log hashes remain in that record.
This publication digest preserves the observed results; a fresh clone does not
contain the complete raw archive or reproduce those runs automatically.

## Safety evidence boundary

The seven original L74 valid controls ran in debug, release and fast against
safety.py SHA-256 `1ba5b366804695f93d502c60c3692056a3502d096626b73619bb1caa56cc92ca` as recorded by the local
`safety-proposals/verification.json` archive. That source identifier
is historical; it is not a claim about the current source. The integration gate
qualifies later nested-record, wrapper, match and bounded callee-effect edits
against the cases it exercises.

The original four rejection cases and seven compatibility controls are recorded
in the [approved packet](../../plan/packets/P-REF-bounded-safety.md).
The live source still has unqualified alias paths. Earlier compile-only probes
found unsafe acceptance through borrowed child deletion and field replacement,
and valid-program rejection when a callee deleted only a child or an unrelated
local allocation. Bounded exact replay repairs the covered cases. Selected/base
store synchronization, joined-holder nil-write invalidation and effects outside
that replay remain open. Current dispositions remain in [STATUS](../../STATUS.md).

## Later checker statement worklist

The checker statement refactor is newer than the combined gate snapshot.
Its source hash is
`977cd1117051a770fa5b79c77412e458ef31f34bff01812e02b56810c08508ce`.
Focused tests passed: 269 cases, with 24 native cases deselected. Their reduced
recursion limit accounts for test-runner frames. A separate direct invocation
sets the limit to exactly 100: both AST shapes at depth 1,601 pass real name
resolution and checking, with valid and incompatible leaves. The previous
checker raises `RecursionError` on the deep shapes in the differential tests.

Independent review compared 16 checker probes and six full compiler-pipeline
probes against the previous checker. All 22 pairs matched the inspected
diagnostics and state. A separate selection passed 122 tests. These checks
exclude native execution. Fault injection also reproduced unchanged loop-state
cleanup leaks in WHILE and FOR_IN; no ordinary-source trigger was established.

The recursion scanner now reports seven explicit groups with 94 functions and
ten generated methods. Its 36 tests pass after removing the six checker
statement methods from the allowed list. The existing traversal suite also
passes through `python -m pytest`: 44 tests. These results qualify selected
stages and inputs, not the full no-recursion requirement.

Local raw evidence is in `iterative-checker-statements/`, including
`fixed-limit-100.json`,
`checker-statements-independent-review.md`, `checker-statement-review-probes/`
and `recursion-module-launcher-current.json` under the archive directory above.
The integration gate includes this checker revision and native controls. The
separate 27-case native selection also passed, including selected-child
replacement and complementary-child reads in debug, release and fast.

## Review evidence

The [review digest](review-summary.json) records seven completed GLM-5.3 reviews
and five GLM-5.3-Flash reviews. They cover distinct snapshots and bounded inputs;
their findings were checked against source and reproductions before action.
Failed invocations remain in the local archive and are not counted as reviews.
Model output is advisory evidence, not a replacement for compiler or native
checks. The digest records scope limits and corrected reviewer claims.

## Published documentation checkpoint

The [deployment record](published-docs-verification.json) records successful
GitHub Pages deployment for `4ace8caf3b764a37558534c77601db02a02088ac`.
Six HTML pages, both llms entry points, four Markdown/JSON documentation exports,
the sitemap and three site assets returned HTTP 200. All 16 responses matched
the frozen site's bytes, including its CSS, JavaScript and search index.

These are HTTP publication checks. Browser-harness could not establish a
connection; the computer-use inventory was empty and its in-app browser was
unavailable. Rendered desktop/mobile layout, navigation/search interactions
and browser console health remain unverified. The deployment is a development
documentation checkpoint, not V1 publication.

## Subsequent iterative candidates

The [follow-up record](iterative-followup-verification.json) identifies the later
AST and type-resolution candidates. AST comparison/display passed 129 focused
tests, 47 independent checks and GLM review within the compiler-payload boundary.
Custom Python payload mutation and wrapper reentry remain outside that boundary.
Type resolution passed 126 focused tests, 64 independent checks and a 12-case
differential. The independent 210-link alias source reaches Zig generation at
recursion limit 100; both earlier checker variants fail with internal exit 8.

The initial combined candidate passed 3,018 tests excluding native and slow
cases. A later parser/setter snapshot passed 3,040. The expression snapshot
passed 3,082. Each result applies to the source manifest in the follow-up
record; none is a full release gate.

Parser statement and backend statement GLM reviews found no introduced
regression. The later parser expression candidate passed 576 focused tests
and 462 baseline comparisons. Independent review matched 111 cases. It found
an ineffective test hook; the corrected hook observes actual driver requests,
and all 34 error-handling tests pass. Checker expressions passed 1,246 focused
tests and 648 fresh-AST comparisons. Backend expressions passed 184 focused
tests, 171 source/profile comparisons and 42 fresh-AST comparisons. Debug and
release native verification each passed all 51 examples. Expression GLM reviews found no introduced regression in their tested scopes.

The safety statement conversion also passed 40 independent compile runs and
six new deep tests. Both scanner modes now report empty recursive-group,
deepcopy and generated-method lists. The live integration check passed 42
tests. Its GLM review matched 300 paired analyses and 70 exception cases. These are
bounded checks, not complete
dynamic-call or V1 acceptance.

Safety review found conditional setters incorrectly counted as unconditional
stores and valid cleanup on a returning path counted as a continuing deletion.
The failed results remain archived. Candidate ebda repairs explicit cleanup;
the original control builds and prints the expected six lines in all three
profiles. Candidate 178c also repairs returned reference origins, valid one-trip
loop cases and loop-local alias deletion. Its 294 focused tests and 65 reviewer
replay cases pass within their stated expectations. GLM review matched 165 behavioral cases; independent review found exponential fresh-origin
expansion and a preexisting equivalent-increment false rejection. General selected/container identities remain open.

The component checks above describe intermediate snapshots. The combined
integration and its metadata recovery below qualify their final combination;
they do not establish V1 acceptance.

Compact provenance candidate `338ecedb` is now integrated. Independent consumer
review matched 16 programs; 159 integrated focused tests pass. The depth-64
factory retains 196 graph nodes, and its valid native control prints the expected
output in debug, release and fast profiles. These measurements close the
observed expansion for this source family, without proving a general complexity
bound. GLM review matched 68 paired programs and reproduced the resource
counts. Frozen manifest `04330ece` passed 3,602 tests with one expected failure,
51 example E2E checks, all 51 artifacts in each of three profiles, 61 error-stage
checks and native package installation. The compiler gate finished with 10 of
11 checks passing. The secrets check failed with `fatal: not a git repository`
because the isolated snapshot lacked Git metadata. The release wrapper stopped
before site and dependency/security audits. The original gate remains recorded
as exit 1. An independent review verified all 1,591 source hashes and modes.
An exact-manifest Git index was then created in the isolated copy, without a
commit or source changes. Secrets, locked site install, site checks, Bun audit,
locked requirements export, pip-audit and Bandit all passed. All source hashes
and modes still match. The [follow-up record](iterative-followup-verification.json)
retains both the failed run and the seven recovery results.
Global-store alias propagation and equivalent-increment rejection remain open.
