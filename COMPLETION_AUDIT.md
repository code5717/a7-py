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
4. Prepare debug builds, release builds, release packaging, publishing workflow,
   and documentation.
5. Do not claim completion if factual confidence is weaker than the objective.

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Vulnerability/problem review | `RELEASE_READINESS_REVIEW.md`, `SECURITY.md`, `MISSING_FEATURES.md`, `TODO.md` | Covered for current known risks |
| Security dependency audit | Hosted CI run `25528605790`; local `uvx pip-audit --strict`; local site runtime audit | Passing for known advisories |
| Secret scanning | Hosted CI run `25528605790`; `scripts/check_no_secrets.py` | Passing pattern-based scan |
| Python test suite | Hosted CI run `25528605790`; local full gate evidence in `RELEASE_READINESS_REVIEW.md` | Passing |
| Error-stage behavior | Hosted CI run `25528605790`; `scripts/verify_error_stages.py` | Passing |
| Zig example E2E | Hosted CI run `25528605790`; `scripts/verify_examples_e2e.py` | Passing |
| C example E2E | Hosted CI run `25528605790`; `scripts/verify_examples_e2e_c.py` | Passing |
| Zig/C backend parity | Hosted CI run `25528605790`; `scripts/verify_backend_parity.py` | Passing selected suite |
| Debug artifacts | Hosted CI run `25528605790`; `scripts/build_examples.py --profile debug --backend both --clean` | Passing |
| Release artifacts | Hosted CI run `25528605790`; `scripts/build_examples.py --profile release --backend both --clean` | Passing |
| Python package build | Hosted CI run `25527971161`; local clean `rm -rf dist && uv build` | Passing |
| Local package hygiene | `README.md`, `RELEASE.md`, `site/public/docs/release.md` now require `rm -rf dist` before `uv build` | Covered |
| Release checksums and archive contents | `scripts/generate_release_manifest.py`; `scripts/verify_release_manifest.py`; `scripts/verify_archive_contents.py`; `test/test_release_tooling.py`; release workflow validates required paths, required archive members, and re-checks hashes before upload | Covered |
| Docs style/build | Hosted CI run `25528605790`; local `scripts/check_docs_style.py`; local `site npm run check` | Passing |
| Docs deploy | Hosted Deploy Docs run `25528605791`; hosted fetches for `/llms.txt`, `/docs/index.md`, `/docs/status.md`, and `/llms-full.txt` | Passing |
| curl.md/agent documentation | `site/public/llms.txt`, `site/public/llms-full.txt`, `site/public/docs/*.md`, plugin/dev subtrees, sitemap and robots entries | Implemented |
| Release workflow | `.github/workflows/release.yml`, manual dispatch run `25527020391` on commit `67da15e`; downloaded artifacts verified with `scripts/verify_archive_contents.py` and `scripts/verify_release_manifest.py` | Passing for non-tag validation |
| PyPI publishing | `.github/workflows/release.yml`, GitHub `pypi` environment documented | Blocked until PyPI project/trusted publisher exists |
| No-recursion language rule | Semantic recursion rejection, docs in `README.md`, `docs/SPEC.md`, and site docs | Implemented for named call cycles |
| No-recursion compiler traversal confidence | Iterative traversal tests and full gate | Covered for tested traversal paths |
| Virtual stdlib module resolution | `src/module_resolver.py`, `src/stdlib/__init__.py`, `test/test_module_resolver.py`, focused alias codegen tests | Implemented for `std/io`, `io`, `std/math`, and `math` |
| Array literal assignment compatibility | `src/passes/type_checker.py`, `src/backends/c.py`, `test/test_semantic_types.py`, `test/test_codegen_c.py`, `scripts/verify_backend_parity.py`; local full gate | Covered for declared lengths, nested literals, and Zig/C runtime parity |
| Parser ambiguity hardening | `src/parser.py`, `test/test_parser_comprehensive_problems.py`, `docs/SPEC.md`; local full gate | Covered for rejecting initializer-like `new` calls while preserving `new(T)` allocation syntax |

## Incomplete Or Weakly Covered Areas

These prevent a factual "100% confident" claim:

1. The compiler is not a sandbox; native output can execute host-level behavior.
2. Backend parity is selected and expanding, not exhaustive over all valid A7
   programs.
3. `fall` parses and fails closed, but final fallthrough semantics and backend
   lowering are not designed.
4. Full ownership, borrowing, lifetime, use-after-free, and double-free
   guarantees are not implemented.
5. Full generic specialization is incomplete beyond simple top-level generic
   functions lowered for the C backend.
6. Tagged/discriminated union tag workflows remain incomplete. Untagged
   single-field union construction and field access now have focused semantic,
   C backend, Zig backend, CLI JSON, and example verifier coverage.
7. PyPI publishing is wired but cannot be proven until the public PyPI project
   and trusted publisher are created/configured outside this repository.
8. Secret scanning is pattern-based and should be backed by repository-host
   protections for public release.
9. Dependency audits cover known advisories, not unknown supply-chain
    compromise.

## Conclusion

The implementation is release-candidate ready for the documented current
language surface, with strong local and hosted verification. It is not
factually possible to claim 100% confidence or zero vulnerabilities from the
available evidence. The remaining work is tracked in `MISSING_FEATURES.md`,
`TODO.md`, and `RELEASE_READINESS_REVIEW.md`.
