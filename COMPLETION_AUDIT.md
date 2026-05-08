# A7 Completion Audit

Date: 2026-05-08

This audit maps the active release-readiness objective to concrete evidence.
It is intentionally strict: a green test run is not treated as proof that every
language feature, release path, or security boundary is complete.

## Objective Restated

Deliverables implied by the active objective:

1. Identify vulnerabilities and implementation problems.
2. Fix every issue that can be fixed safely in the current pass.
3. Repeat verification until the current implementation has defensible release
   confidence.
4. Prepare debug builds, release builds, release packaging, and documentation.
5. Do not claim completion if factual confidence is weaker than the objective.

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Vulnerability/problem review | `RELEASE_READINESS_REVIEW.md`, `SECURITY.md`, `MISSING_FEATURES.md`, `TODO.md` | Covered for current known risks |
| Security dependency audit | Hosted CI run `25533359030`; local `uvx pip-audit --strict`; local site runtime audit | Passing for known advisories |
| Secret scanning | Hosted CI run `25533359030`; `scripts/check_no_secrets.py` | Passing pattern-based scan |
| Python test suite | Hosted CI run `25533359030`; local `./run_all_tests.sh` after expanding backend parity | Passing: 1202 tests |
| Error-stage behavior | Hosted CI run `25533359030`; `scripts/verify_error_stages.py`; refactored shared logic in `scripts/error_stage_common.py` | Passing |
| Zig example E2E | Hosted CI run `25533359030`; local `scripts/verify_examples_e2e.py`; shared verifier logic in `scripts/verify_examples_common.py`; manual JSON inspection for `037_language_tour` | Passing: 38/38 |
| C example E2E | Hosted CI run `25533359030`; local `scripts/verify_examples_e2e_c.py`; shared verifier logic in `scripts/verify_examples_common.py`; manual JSON inspection for `037_language_tour` | Passing: 38/38 |
| Zig/C backend parity | Hosted CI run `25533359030`; local expanded `scripts/verify_backend_parity.py`; manual report inspection; local full gate | Passing selected suite: 16/16 locally |
| Debug artifacts | Hosted CI run `25533359030`; local `./run_all_tests.sh` after expanding backend parity | Passing: 76/76 |
| Release artifacts | Hosted CI run `25533359030`; local `./run_all_tests.sh` after expanding backend parity | Passing: 76/76 |
| Python package build | Hosted CI run `25527971161`; local clean `rm -rf dist && uv build` | Passing |
| Local package hygiene | `README.md`, `RELEASE.md`, `site/public/docs/release.md` now require `rm -rf dist` before `uv build` | Covered |
| Release checksums, provenance, and archive contents | `scripts/generate_release_manifest.py`; `scripts/verify_release_manifest.py`; `scripts/verify_archive_contents.py`; `test/test_release_tooling.py`; release workflow validates required paths, required archive members, re-checks hashes before upload, and emits GitHub artifact attestations for release assets | Covered for workflow definition; tag-only attestation path still needs a real tag run before release |
| Docs style/build | Hosted CI run `25533359030`; local `scripts/check_docs_style.py`; local `site npm run check` | Passing |
| Docs deploy | Hosted Deploy Docs run `25533359054`; hosted browser-harness check for `/a7-py/` confirmed the A7-first homepage title and primary navigation; hosted fetch confirmed the new `llms-full.txt` format | Passing |
| curl.md/agent documentation | `site/public/llms.txt`, `site/public/llms-full.txt`, `site/public/docs/*.md`, plugin/dev subtrees, sitemap and robots entries | Implemented |
| Release workflow | `.github/workflows/release.yml`, hosted CI run `25535705154`, hosted Deploy Docs run `25535705155`; manual dispatch run `25527020391` on commit `67da15e`; downloaded artifacts verified with `scripts/verify_archive_contents.py` and `scripts/verify_release_manifest.py`; local workflow YAML parse after concurrency/checksum hardening | Passing for non-tag validation; tag-only draft release path still requires a real tag run before release |
| Workflow supply-chain hardening | Non-`actions/*` actions pinned to immutable commits; `.github/dependabot.yml` covers GitHub Actions, Python, and docs npm; automated Claude review prompt treats PR text as untrusted | Improved; first-party actions still pinned by major version tags |
| No-recursion language rule | Semantic recursion rejection, docs in `README.md`, `docs/SPEC.md`, and site docs | Implemented for named call cycles |
| No-recursion compiler traversal confidence | Iterative traversal tests and full gate | Covered for tested traversal paths |
| Virtual stdlib module resolution | `src/module_resolver.py`, `src/stdlib/__init__.py`, `test/test_module_resolver.py`, focused alias codegen tests | Implemented for `std/io`, `io`, `std/math`, and `math` |
| Array literal assignment compatibility | `src/passes/type_checker.py`, `src/backends/c.py`, `test/test_semantic_types.py`, `test/test_codegen_c.py`, `scripts/verify_backend_parity.py`; local full gate | Covered for declared lengths, nested literals, and Zig/C runtime parity |
| Parser ambiguity hardening | `src/parser.py`, `test/test_parser_comprehensive_problems.py`, `docs/SPEC.md`; local full gate | Covered for rejecting initializer-like `new` calls while preserving `new(T)` allocation syntax |
| Public site positioning | Commit `05dff14`; `site/src/pages/Home.tsx`; `site/src/content/navigation.ts`; hosted Deploy Docs run `25533359054`; live browser-harness check | Covered for keeping the public homepage and primary nav centered on A7 rather than agent/plugin docs |
| Learn-by-reading language artifact | `examples/037_language_tour.a7`; `test/fixtures/golden_outputs/037_language_tour.out`; local Zig/C verifiers; README and public docs links | Covered for current documented language surface |

## Incomplete Or Weakly Covered Areas

These prevent a factual "100% confident" claim:

1. The compiler is not a sandbox; native output can execute host-level behavior.
2. Backend parity is selected and expanding, not exhaustive over all valid A7
   programs. The current local selected suite covers 16 non-example programs.
3. `fall` parses and fails closed, but final fallthrough semantics and backend
   lowering are not designed.
4. Full ownership, borrowing, lifetime, use-after-free, and double-free
   guarantees are not implemented.
5. Full generic specialization is incomplete beyond simple top-level generic
   functions lowered for the C backend.
6. Tagged/discriminated union tag workflows remain incomplete. Untagged
   single-field union construction and field access now have focused semantic,
   C backend, Zig backend, CLI JSON, and example verifier coverage.
7. Secret scanning is pattern-based and should be backed by repository-host
   protections for public release.
8. Dependency audits cover known advisories, not unknown supply-chain
    compromise.
9. Most first-party GitHub Actions remain pinned by major version tag instead of
   full commit SHA.

## Conclusion

The implementation is release-candidate ready for the documented current
language surface, with strong local and hosted verification. It is not
factually possible to claim 100% confidence or zero vulnerabilities from the
available evidence. The remaining work is tracked in `MISSING_FEATURES.md`,
`TODO.md`, and `RELEASE_READINESS_REVIEW.md`.
