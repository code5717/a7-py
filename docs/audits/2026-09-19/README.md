# Repository audit and cleanup, 2026-09-19

The audit found tooling defects and stale documentation. The cleanup repairs the
confirmed tooling issues, simplifies repeated work, and applies explicitly
approved float-remainder and backend-binding fixes. It does not qualify A7 as production-ready or
close the existing compiler audit backlog.

## Findings and disposition

| Finding | Evidence | Disposition |
| --- | --- | --- |
| Preview path traversal | `/a7-py/..%2fpackage.json` returned the package file outside `site/dist` | Fixed decoded-path and resolved-path containment, including symlinks. Preview binds to loopback; malformed URLs return 400 and missing files return 404 |
| Manifest containment bypass | Existing absolute paths returned before the old guard; symlinks also escaped | Validate every resolved candidate. External publisher paths can use downloaded local basenames without reading the external file |
| Dependency audit checked the isolated tool environment | CI invoked `uvx pip-audit` without project requirements | Export locked project requirements, including dev dependencies, and audit that file in CI and release workflows |
| Float remainder disagreed between constants and runtime | `-5.5 % 2.0` printed 0.5; typed local operands printed -1.5 | Fixed under explicit user approval L33. Constant folding uses truncated remainder and preserves signed zero |
| Source/output alias collision | `--output` and `--doc-out` could overwrite the source; imported aliases were also unchecked | Reject destinations that alias any loaded source or another output before writes, including symlinks and hard links |
| Stale artifact reports | Failed runs could advertise old files or directories | Assign output paths only after successful writes |
| Diagnostic provenance loss | Operators had incorrect columns; imported errors lost origin or became internal faults | Preserve token starts and module span provenance; keep source errors in the source-error path |
| Invalid Zig bindings | Keywords, unused loop captures, and shadowed captures failed native builds | Correct escaping and scope restoration under user approval L34; verify nested and indexed loops by runtime output |
| Repeated verification work | Three pytest subsets preceded full collection; release rebuilt verified artifacts | Run full pytest once; retain end-to-end and artifact checks; release reuses gate-verified distributions and binaries |
| Duplicated compiler traversal | Preprocessor repeated its existing child iterator | Reuse the iterator with the same ordering and parent slots; remove parser catch-and-rethrow |
| Stale current-state claims | Public imports and recursion claims, numeric priorities, safety and ownership wording | Reconcile current docs with implementation limits and decision records; regenerate public corpora |
| Broken research references | Five links to unwritten optimization report 03 | Mark it planned without linking to a nonexistent file |
| Secrets scan included ignored downloads | Filesystem traversal ignored Git exclusions and scanned fetched HTML | Enumerate tracked and non-ignored working files. A regression checks that force-added ignored secrets still remain in scope |
| Fragile research provenance | Runtime source records and hardware quotation evidence lived under temporary paths | Preserve eight runtime source records and briefs, plus hashes for 41 hardware citation files; retain original downloads |
| Redundant PDF exports | Seven historical pointer reports with overlapping contents | User authorized deletion. Keep the base PDF; remove six alternate exports and their active index links |

The PDF variants were not byte-identical. The base and direct-wkhtmltopdf exports
have equivalent normalized text, as do compact and dark. The Beamer export is a
shorter subset. Git history retains the deleted files. Their reference-syntax
recommendations are obsolete and are not approved language rules.

## Research basis

- [pytest discovery](https://pytest.org/en/stable/explanation/goodpractices.html)
  establishes that a full invocation discovers tests without maintaining subsets.
- [uv tool isolation](https://docs.astral.sh/uv/concepts/tools/) and
  [pip-audit usage](https://github.com/pypa/pip-audit) explain why auditing the tool
  environment does not audit the project.
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
  documents locked dependency operations.
- [Zig 0.16.0 reference](https://ziglang.org/documentation/0.16.0/) documents the
  backend's remainder operation and build modes. A7's constant/runtime mismatch
  was also reproduced with native binaries, not inferred only from documentation.

## Coverage and limits

The [compiler inventory](compiler-inventory.json) records 32 Python files and
19,347 lines, with the largest functions identified for later bounded refactors.
These size measurements are not correctness evidence.

Three independent reviewers covered compiler internals and relevant diffs,
documentation/research organization, and tests/build/CI/site tooling. The
[GLM security review](glm-tooling-review.md) independently checked the tooling
fixes and ran their regressions. It found no blocking regression in its scope.
Local file replacement races remain outside these path checks; the preview is a
local development tool, not a hardened public file server.

The initial docs scan covered 183 Markdown files and 76,200 lines mechanically.
A deeper research scan covered 108 research/safety files and 50,412 lines.
Semantic reads focused on authoritative docs, decisions, implementation claims,
provenance, and contradictions. This is not a claim that every historical research
sentence or external citation was revalidated. The source records preserve earlier
verification statements as historical evidence.

All seven PDFs passed `qpdf --check`; all extracted texts were read. The base
PDF's first page was rendered and inspected. Other pages were not visually
qualified. Deletion followed user approval, not a claim of exact duplication.

The working tree was already substantially modified at audit start. Existing work
was retained. No commit, publication, release tag, or deployment was made.

## Verification

The [final gate](gate-results.txt) passed all nine checks with exit code 0:

- 2,629 pytest tests.
- 43/43 example execution checks.
- 43/43 debug and 43/43 release artifact builds with runtime verification.
- 61/61 error-stage checks.
- Docs style, secrets scan, package build, and clean-venv wheel installation.

The separate final site check passed lint, one HTTP test with 17 assertions,
and the nine-page build.
Focused checks already passed: 18 release-tooling tests, two new float-remainder checks, and the
site lint/request-test/build command. Native remainder checks use f64 and run Debug and
ReleaseFast. Negative-divisor and nonfinite remainder boundaries have evaluator
checks; they were not separately run through native remainder programs. The independent compiler reviewer reported 71 focused tests passed. After the
pipeline repairs, 874 parser/tokenizer/CLI/semantic tests passed; the backend
reviewer reported eight binding cases and 207 backend/traversal cases passed.
The locked Python dependency audit found no known vulnerabilities.

The first complete gate reported 11 failures and 2,605 passes in pytest; all
other eight gate checks passed. Those failures were the existing artifact,
diagnostic, and native-binding regressions described above. Their focused repairs
pass, and the expanded final gate passed after those fixes.

The earlier startup gate run stopped after the gate script was edited while Bash was
still reading it. Its error was `unexpected EOF while looking for matching` a
quote. It is not a passing baseline. A fresh gate run validates the final script.

The Bun advisory endpoint returned HTTP 503 on three attempts, including GLM's
retry. The [GLM dependency follow-up](glm-dependencies-review.md) queried OSV for
all 66 exact locked site packages and found no advisory matches. Known-vulnerable
positive controls returned advisories. This fallback does not qualify the failed
Bun audit or guarantee identical advisory coverage.

The initial browser
connection failed, then an isolated headless Chromium session succeeded. All nine
routes were checked at widths 1440 and 390 with no page-level horizontal overflow.
Stable reduced-motion captures of home and compiler pages were inspected; the
mobile navigation and code blocks have intentional internal scroll areas.
Search returned the new Float remainder section. The rendered check also found
and fixed numbered Markdown lists being flattened into paragraphs. The compiler
pipeline now renders as nine ordered items.

[Browser measurements](browser/checks.json), [search evidence](browser/search-check.json),
and desktop/mobile captures in `browser/` retain this bounded review. This does
not establish complete accessibility, live-site deployment, or every interaction.
Local Bun is 1.4.2; CI pins 1.3.11, which was not executed here.

Detailed local command logs and the starting diff are in
`tmp/audit/2026-09-19/`. This Verification section retains the results
without requiring those temporary logs. GitHub Actions itself was not executed
locally. Workflow YAML parsed successfully; the [separate GLM review](glm-release-review.md) found no blocker in
release artifact reuse. The docs archive passed its six required-content checks. An archive of the
gate-built release examples passed four checks, including exact counts of 43
Zig sources and 43 binaries. The [gate input hashes](gate-inputs.json) identify the
uncommitted files checked by the gate. Only `site/scripts/build.ts` changed
within that snapshot after the gate started; the separate final site check
passed after that renderer fix. Later workflow and report edits are outside
that snapshot.

The [generated-site link check](site-link-check.json) found no missing target or
fragment among 264 links. Six public HTML/Markdown endpoints returned HTTP 200.
The [repository link scan](docs-link-check.json) checked 840 relative Markdown
targets. Its five remaining matches are quoted syntax or placeholders, not links
to missing documents. [PDF checks](pdf-checks.json) retain the pre-deletion
structural results and metadata.

## Remaining work

- Continue the correctness batches and approval packets in the existing execution
  plan. No-recursion conversion, ownership/lifetime proofs, module semantics,
  generics, and planned v1 facilities remain outside this cleanup's completed work.
- Revalidate historical research claims before using them to make new design
  decisions. Hardware source URLs are still absent from the recovered hash index.
- Complete a dedicated accessibility and full-interaction review before claiming
  website acceptance beyond the bounded checks above.
- Retry the Bun dependency advisory check after the service recovers.
