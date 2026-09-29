# Coordinator verification

Status: audit record from 2026-09-14 (baseline `701c67936c70ad2b0608326e23e56cc5d38c9fdb`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

The audit findings support the proposed completion roadmap. Implementation and
release approval remain pending.

The changed-tree full gate is **11/12**, with **12 pytest failures and 2,515
passes**. A7 is not ready for v1 qualification. The baseline pass below is useful
historical evidence, not the current verdict.

## Verification boundaries

The baseline release script passed 12/12 checks, including the existing 2511
pytest tests, 43 native example runs, debug and release artifact runs, 61
error-stage checks, and the clean-wheel smoke test. This run preceded the newly
authorized regression tests. It does not qualify the changed test suite or
negate the concrete defects below. See `evidence/baseline-release-gate.log`.

The first attempt could not run because the Mise uv shim had no selected
version. The successful run selected the already-installed uv 0.12.6 for this
process. Zig 0.16.0 was downloaded to a temporary directory from the CI-pinned
official URL and verified against the CI SHA-256. No global tool configuration
changed. Pinned pip-audit and Bandit checks and Bun audit also exited zero.
However, inspection of the pip-audit JSON inventory shows it audited its own
isolated tool environment, including pip-audit and requests, with no a7-py or
pytest entry. That passing command does not establish a project-environment
dependency audit. GLM owns security remediation review of this coverage gap.

Website `bun run check` passed. The initial generated-link scan checked 259
internal links across 10 HTML files with no missing file or fragment. This is
link evidence, not visual or accessibility acceptance.

## R1. Integer constant folding silently changes exact results

Priority: P1. Source: `a7/ast_preprocessor.py:620-625`.

The preprocessor converts integer operands to Python floating point with
`int(lval / rval)`. Large exact integers lose precision before truncation.

The coordinator compiled this trusted source through the CLI, built the output
with Zig 0.16.0 Debug, and executed it.

Current A7 (built and executed):

```a7
io :: import "std/io"
main :: fn() {
    x: i64 = 9007199254740993 / 1
    io.println("{}", x)
}
```

Expected stdout is `9007199254740993`. Actual stdout is `9007199254740992`, with
successful compiler, Zig build and native exit codes. The emitted Zig already
contains the wrong literal. No overflow is involved; the value fits in i64.

Use exact integer arithmetic for truncating division and remainder. Verify
large positive and negative values against independently stated mathematical
results and equivalent non-folded expressions. The observed `% 2` comparison
case happened to return the correct result and is not evidence that remainder
folding is generally sound. A coordinator-added regression subsequently checked
division and remainder by one against a function-parameter version in Debug
and ReleaseFast. Both profiles show the incorrect folded result. The fixture
uses only safe, defined integer arithmetic.

The coordinator reran all new tests after that addition. The result is 12 failed
and 4 passed. These are explicit requirement failures, with no skip, xfail or
mock masking. The earlier external test report describes its original 15-case
set; the coordinator's precision test is the additional case.

## R2. An imported parse error becomes an internal compiler failure

Priority: P2. Sources: `a7/module_resolver.py:154-168`,
`a7/compile.py:246-250`, `a7/compile.py:491`.

A main program imports `broken.a7`, whose source is `pub work :: fn() {`.
The public JSON CLI exits 8 with category `internal`, exception type
`ParseError`, empty details and a null span. The human-readable message embeds
the imported basename but automation receives no structured source location.

The same missing brace in the main file exits 5 with category `parse` and a
source span. Imported source errors must remain source errors, retain their
origin and give users an editable location. The import boundary currently
catches `SemanticError`, while the parser raises `ParseError`.

Control checks for a main-file invalid escape, missing brace and type mismatch
returned valid JSON with exit codes 4, 5 and 6 and their expected categories and
locations. See `evidence/root-pipeline-probes.json` for source and results.

## R3. Preview root boundary and HTTP status

Priority and security remediation belong to the GLM cybersecurity review.
The coordinator initially verified the following harmless request before the
user routed cybersecurity work to GLM:

```text
GET /a7-py/..%2fpackage.json
```

The local preview returned the source `site/package.json` with HTTP 200 rather
than restricting access to `site/dist`. `site/scripts/serve.ts:23-24` decodes
the path and joins it without verifying containment. No secret file was read.
A nonexistent route also returns the fallback body with HTTP 200. These local
preview observations do not establish a vulnerability in GitHub Pages hosting.

## R4. Additional compiler-stage findings independently reproduced

See `evidence/root-stage-validation.json` for sources, results and emitted code.

| Finding | Coordinator verification | Classification |
| --- | --- | --- |
| Literal fit differs by context | `ret 0` in a u8-returning function and `f(5)` for a u8 parameter both fail as i32 mismatches. SPEC Appendix A permits integer literals that fit. | Current contract inconsistency. |
| Struct checks defer invalid source to Zig | An undefined `Point` initializer and a declared struct missing a required field both pass A7, then fail real `zig build-exe -fno-emit-bin`. | Missing A7 semantic diagnostics. |
| A malformed numeric token causes an internal error | Superscript two reaches Python `int()` and exits 8 with ValueError and no source span. | Lexer/parser error-handling defect. This does not decide whether all non-ASCII numeric forms should be forbidden. |
| A parser warning corrupts JSON output | 1001 independent empty functions produce a warning before the JSON object. Exit 5 is returned, but stdout is not valid JSON. | Automation contract defect, separate from choosing a supported declaration limit. |
| Semantic mode disagrees with compilation | A simple file-backed module call fails semantic mode as an unknown stdlib call, but pipeline and compile modes accept the same files. | Pipeline consistency defect. |

A targeted `python -m pytest` run also reproduces the ten-level expression test
failure under recursion limit 100. The same test passes through the repository's
configured `uv run pytest` gate. Record this invocation-sensitive stack limit
separately from the full gate result. The flat 1200-term expression defect in the
compiler report is a separate full-pipeline observation.

## R5. Parser recovery drops main and reports successful compilation

Priority: P1. Source: `a7/parser.py:171-264`.

The coordinator replayed GLM's `repros/a7glmr_silent_drop.a7` through the real
CLI. A valid `good` declaration precedes a malformed import inside `main`.
Compilation exits zero and writes 47 bytes containing only `good`; the entire
main declaration disappears. See `evidence/parser-recovery-coordinator.json`.
No native program was built or run for this check.

Recovery may collect diagnostics, but any source error that discards a declaration
must fail compilation. A success message plus a silently incomplete program is
a current correctness defect. The new regression files do not yet cover this
later finding; adding the public-CLI rejection case belongs to phase 1.

## Advisory findings that are not accepted as stated

- A7's safety proofs are not unsound only inside loops. Branch/block mutation,
  compound assignment and calls have independently supported counterexamples.
- A simple compile-only command is not automatically evidence that Zig analyzed
  all bodies. Lazy analysis requires reachable roots. GLM requalified the memory
  fixtures with `build-exe -fno-emit-bin` from reachable main functions and
  corrected its report. No runtime memory-safety conclusion follows from these
  compile-only checks.
- An integer constant expression such as `100 + 100` is not necessarily the same
  promised conversion as a single integer literal. That contextual typing proposal
  needs a language decision before a rejection becomes a failing requirement test.
  (Still open as gate G3 in the [v1 plan](../../plan/README.md).)
- Generic claims that failed compilations advertise no output are contradicted
  by the stale-output and directory-output regressions.
- Module cycle policy is not clearly public. The loader and its topological
  validator disagree, but tests must not invent the intended policy.
- A count of parser tests alone does not establish redundancy. Each proposed test
  removal needs comparison of the actual requirement and failure mode it checks.
- `xfail` recommendations, scans for absent panic strings, and a few compiled
  fixtures cannot qualify v1 memory safety. The new AGENTS.md rule remains the
  acceptance standard.
- The contract review conflates fixed-width overflow with the exact representable
  i64 precision defect in R1. Overflow policy remains a design question; R1 is a
  current arithmetic defect regardless of that policy.
  Note (2026-09-16): overflow for integer `+`, `-` and `*` is now decided by ledger
  L5 (wrapping); the rest stays open under gate G3. R1 is unaffected.
- Enforcing module privacy must not remove private declarations that public
  functions need internally. Check access at module boundaries while preserving
  implementation dependencies.
- Missing required Zig tooling cannot silently skip release qualification.
  Optional local test skips, if any are later adopted, must remain distinct from
  the mandatory release gate. The current added tests contain no skips.
- Two rejected safety fixtures demonstrate those cases only. They do not establish
  universal enforcement in the face of GLM's counterexamples.
- Documentation preservation verified 13 corrected SPEC TOC anchors. The contract
  review's smaller anchor count is inaccurate; the preserved diff is authoritative.

## Website reconciliation

The source audit confirms wrong A7 version stamps, missing search body content,
dead homepage search fragments, hidden mobile search controls, incomplete modal
focus handling, flattened numbered instructions, and inaccurate copy/transcripts.
See `website-reconciliation.md` for accepted, rejected and provisional findings.

The coordinator rebuilt the site after documentation cleanup. Its build/lint and
259 generated internal links pass. Earlier source-versus-dist drift was an
in-progress build state and is now resolved locally; it was not proof of a
published corpus mismatch. The homepage still omits the overview Markdown body,
and the search-index fragment mismatch is a separate generator defect.

Accessibility acceptance should use actual interactions and computed rendered
styles. Ordinary text needs 4.5:1 contrast, while qualifying large text has a 3:1
threshold. See the [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
Modal keyboard and focus behavior should follow the
[W3C dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
These references do not establish this site's conformance.

## Review limitations

The dedicated [GLM cybersecurity review](security-glm-review.md) is saved. Its
preview containment and dependency-target findings support the roadmap. The
coordinator requested corrections to broader positive claims and remediation
advice. GLM completed that correction pass and recorded it in the report.
The following boundaries apply:

- The project dependency set has not been qualified by a corrected audit. No
  claim that today's lockfile is free of known advisories is accepted from the
  isolated tool-environment result.
- Import traversal and symlink rejection fixtures do not prove module identity
  or cycle handling correct. Independent contract review found the loader's
  cache and cycle-validator behavior inconsistent.
- Site-content injection that requires repository write access is conditional
  hardening unless a lower-trust publishing boundary is established. No browser
  execution of injected content was verified.
- A default network bind is not proof of actual LAN reachability through host
  and network controls. The observed preview path escape remains a local finding,
  separate from GitHub Pages hosting.
- One deep-input fixture returning an internal error cannot establish bounded
  cost for all compiler input. Tool subprocess deadlines are a possible later
  policy decision; no deadline is imposed on external model reviews.
- Proposed containment code and name-only dependency-inventory assertions are
  not accepted fixes without verification against the real boundary and locked
  dependency versions.

The in-app browser is unavailable. The local browser connector also failed.
No current website screenshot has been accepted. Source and generated HTML
findings must not be described as a visual Product Design audit. A request to
use Playwright as the fallback is pending.

The first compiler sub-agent reported a provider safety-filter termination after
collecting compiler evidence. It was told not to retry the blocked action and
then saved its existing findings. The dedicated Codex memory CLI ended with the
same provider error, exit 1, before producing its requested report; that review is
incomplete. Memory and cybersecurity reviews use GLM. The corrected GLM memory
report is complete, and its claims remain bounded by compile-only evidence. No
blocked operation is being retried through Codex.

External reports are advisory. Their whole-worktree cleanliness statements refer
to their own observations and do not override the known concurrent documentation
and test edits. Generated HTML inspection is not screenshot inspection even if
an external report calls it rendered evidence.
