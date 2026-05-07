# Release Readiness Review

Date: 2026-05-07

## Result

The repository is substantially more release-ready than before this pass:

- installable `a7` CLI entrypoint
- compatibility `main.py` wrapper
- debug and release artifact builder for Zig and C
- committed docs lockfile for deterministic docs builds
- CI workflow for tests, backends, artifacts, package build, and docs build
- tag-based draft GitHub release workflow for packages, docs, and release
  example artifacts
- tag-based PyPI publishing workflow using Trusted Publishing/OIDC
- release checklist, security policy, and updated status docs
- Node 24-compatible GitHub workflow actions for CI, Pages deploy, artifact
  upload/download, and draft GitHub releases
- checksum-verified Zig 0.15.2 install steps in CI and release workflows
- protected GitHub `pypi` environment requiring `code5717` review

This is not a claim that the implementation is free of all bugs or
vulnerabilities. For a compiler and native-code build pipeline, that standard is
not factually provable from local tests alone.

## Evidence Checked

- `uv run a7 --help`
- `PYTHONPATH=. uv run pytest test/test_release_tooling.py -q`
- `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- `uv run python scripts/build_examples.py --profile release --backend both --clean`
- `./run_all_tests.sh`
- `uv build`
- `uvx pip-audit --strict`
- `uv run python scripts/check_no_secrets.py`
- `cd site && npm audit --omit=dev --audit-level=moderate`
- `cd site && npm run build`
- built wheel installed into a temporary virtualenv and invoked as `a7`
- `git diff --check`
- hosted CI and Deploy Docs runs passed after the workflow updates; before
  tagging, re-check the latest commit with
  `gh run list --branch master --limit 6`
- PyPI currently returns 404 for `https://pypi.org/pypi/a7-py/json`

## Fixed In This Pass

- Package metadata now has a real description and a console script.
- Runtime-only test dependency moved into the dev dependency group.
- `main.py` now delegates to `src.cli:main`.
- `scripts/build_examples.py` builds and verifies debug/release artifacts for
  both backends.
- `run_all_tests.sh` now covers C backend tests, C E2E, error-stage audit,
  debug/release artifact builds, docs style, and full pytest.
- GitHub CI now runs Python tests, backend verifiers, artifact builds, package
  build, dependency audits, secret scanning, docs style, docs lint, and docs
  build.
- GitHub release workflow now creates a draft release for `v*` tags with Python
  package artifacts, docs site archive, and release example artifacts.
- Release tags now publish package distributions to PyPI through Trusted
  Publishing/OIDC after the release gate passes.
- C backend `for-in` lowering now caches iterable expressions before loop
  length and element access.
- String literal tokenization now rejects unknown escapes and malformed `\xHH`
  escapes, and valid escapes are decoded/re-emitted so generated binaries print
  the intended characters.
- Semantic regression coverage now explicitly checks return type mismatches
  inside if branches, match branches, and nested blocks.
- Bool and enum match exhaustiveness diagnostics are covered for statements and
  expressions.
- `slice.ptr` and `slice.len` now type-check and lower in both Zig and C.
- Historical error-analysis docs are labeled as non-current and no longer
  conflict with release status.
- GitHub Pages deploy now uses `npm ci` with `site/package-lock.json`.
- README, SPEC, release docs, status docs, and agent docs describe the same
  release commands.
- CI and release workflows pin Zig 0.15.2 through a checksum-verified install
  instead of a third-party JavaScript setup action.
- First-party GitHub Actions, Pages, artifact, and draft-release actions are on
  Node 24-compatible majors.
- GitHub `pypi` environment now exists and requires `code5717` review before
  package publishing jobs can proceed.
- Release/security checklist shell snippets now use subshells so they can be
  copied and run literally.
- README now points to the current `code5717.github.io/a7-py` documentation URL.

## Residual Risks

- `a7-py` is not a sandbox. Do not compile or run untrusted A7 source.
- `fall` is parsed and rejected during semantic validation; full fallthrough
  lowering is not implemented.
- Full ownership/lifetime safety is not implemented.
- Built-in stdlib imports are virtual and still need unification with file-based
  module semantics.
- Backend parity is verified for examples, not all possible source programs.
- Tag-based PyPI publishing is wired, but `a7-py` is not yet a public PyPI
  project and still needs matching trusted-publisher configuration before the
  first real publish.
- Dependency audits are configured for known advisories, not unknown supply-chain
  compromise.
- Secret scanning is pattern-based and should be supplemented by repository host
  protections when publishing publicly.
- GitHub Pages deploy currently emits an upstream `punycode` deprecation warning
  from `actions/deploy-pages@v5`; the workflow succeeds and no repo-side
  replacement is currently available.

## Recommended Next Pass

1. Expand differential backend tests beyond examples.
2. Unify virtual stdlib imports with file-based module semantics.
3. Design and implement `fall` backend lowering.
4. Create or preconfigure the PyPI trusted publisher for project `a7-py`,
   repository `code5717/a7-py`, workflow `release.yml`, and environment `pypi`.
5. Add stronger hosted secret scanning if the repository host supports it.
