# Release Readiness Review

Date: 2026-05-08

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
- semantic recursion rejection for direct and mutual named call cycles, with
  scope-aware handling for local function-pointer shadowing
- consolidated docs-site navigation with curl.md-friendly Markdown entry points
  under `site/public/llms.txt` and `site/public/docs/`

This is not a claim that the implementation is free of all bugs or
vulnerabilities. For a compiler and native-code build pipeline, that standard is
not factually provable from local tests alone.

## Evidence Checked

- `uv run a7 --help`
- `PYTHONPATH=. uv run pytest test/test_release_tooling.py -q`
- `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- `uv run python scripts/build_examples.py --profile release --backend both --clean`
- `uv run python scripts/verify_backend_parity.py`
- `./run_all_tests.sh`
- `uv build`
- local `dist/` cleanup before package builds
- `uvx pip-audit --strict`
- `uvx bandit -r src scripts -q --severity-level medium`
- `uv run python scripts/check_no_secrets.py`
- `cd site && npm audit --omit=dev --audit-level=moderate`
- `cd site && npm run check`
- direct Chromium CDP preview checks for canonical and compatibility hash links
  such as `#/language#standard-library`, `#/stdlib`, `#/pipeline#backend-notes`,
  and `#/cli#flags`
- preview HTTP checks for `/a7-py/llms.txt`, `/a7-py/docs/index.md`,
  `/a7-py/docs/status.md`, `/a7-py/sitemap.xml`, and `/a7-py/robots.txt`
- built wheel installed into a temporary virtualenv and invoked as `a7`
- `git diff --check`
- hosted CI and Deploy Docs must be checked after each release-candidate push;
  the current workflows cover docs, pytest, dependency audits, error-stage
  verification, Zig and C example verification, backend parity checks, debug
  artifacts, release artifacts, and package build.
- manual release workflow dispatch passed on `master` after the PyPI publish
  dependency update; run `25517785179` uploaded
  `python-package-distributions` artifact `6864726540` and `release-bundles`
  artifact `6864741365`, while tag-only GitHub release and PyPI publish jobs
  were skipped as intended.
- manual release workflow dispatch passed again on `master` after checksum
  manifest wiring; run `25524734727` completed release gate, package build,
  docs archive, release example artifact archive, checksum generation, and
  release-bundle upload. Downloaded `release-bundles` contained `SHA256SUMS`,
  `a7-docs-site.tar.gz`, and `a7-example-artifacts-release.tar.gz`.
- PyPI currently returns 404 for `https://pypi.org/pypi/a7-py/json`

## Fixed In This Pass

- Package metadata now has a real description and a console script.
- Runtime-only test dependency moved into the dev dependency group.
- `main.py` now delegates to `src.cli:main`.
- `scripts/build_examples.py` builds and verifies debug/release artifacts for
  both backends.
- `run_all_tests.sh` now covers C backend tests, C E2E, error-stage audit,
  selected Zig/C backend parity checks, debug/release artifact builds, docs
  style, and full pytest.
- GitHub CI now runs Python tests, backend verifiers, artifact builds, package
  build, dependency audits, secret scanning, docs style, docs lint, and docs
  build.
- GitHub release workflow now creates a draft release for `v*` tags with Python
  package artifacts, docs site archive, and release example artifacts.
- Manual release workflow dispatch validates gates and artifacts without
  creating a GitHub release or publishing to PyPI.
- Release workflow permissions are split so the gate/artifact build job keeps
  read-only repository contents access; only the tag-only draft release job gets
  `contents: write`.
- Release tags now publish package distributions to PyPI through Trusted
  Publishing/OIDC only after the release gate and draft GitHub release job pass.
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
- Formatter symbol collection no longer hides broad exceptions during console
  or Markdown report generation.
- Semantic validation now rejects direct and mutual recursion and avoids false
  recursion reports when a local function-pointer variable shadows a top-level
  function name.
- Selected non-example programs now run through both Zig and C backends and
  compare runtime output, including match statements/expressions, slices,
  string slices, labels, and function pointers.
- Public docs-site top navigation is reduced and old CLI, stdlib, pipeline, and
  testing pages are consolidated into Start, Language, and Compiler sections
  with compatibility aliases and verified hash scrolling.
- `llms.txt` and public Markdown docs under `site/public/docs/` provide stable
  curl.md/agent entry points for CLI, language, compiler, examples, release,
  and status information.
- Site metadata, README, robots, and sitemap now consistently use
  `https://code5717.github.io/a7-py/`.
- Local release documentation now explicitly cleans `dist/` before package
  builds so stale versioned artifacts are not accidentally mixed into a manual
  release upload.
- `COMPLETION_AUDIT.md` maps the release-readiness objective to concrete
  verification evidence and records the requirements that remain incomplete.
- Release tooling now generates a deterministic `SHA256SUMS` manifest for
  draft GitHub release artifacts and verifies that expected package, docs, and
  native artifact archive paths are present before upload.

## Residual Risks

- `a7-py` is not a sandbox. Do not compile or run untrusted A7 source.
- `fall` is parsed and rejected during semantic validation; full fallthrough
  lowering is not implemented.
- Full ownership/lifetime safety is not implemented.
- Built-in stdlib imports are virtual and still need unification with file-based
  module semantics.
- Backend parity is verified for examples and selected differential smoke
  programs, including core control flow, match, slices, string slices, labels,
  and function pointers. It is still not exhaustive for all possible source
  programs.
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
- Bandit reports no medium/high-severity findings after the formatter fix. Its
  remaining low-severity findings are expected subprocess usage in trusted
  release/example verifier scripts, plus a false positive on the
  `bad_token_at_global` error-code string.
- Local package directories such as `dist/` and `build/` are generated
  workspace state. Rebuild them from the documented commands before uploading
  artifacts manually.

## Recommended Next Pass

1. Expand differential backend tests beyond examples.
2. Unify virtual stdlib imports with file-based module semantics.
3. Design and implement `fall` backend lowering.
4. Create or preconfigure the PyPI trusted publisher for project `a7-py`,
   repository `code5717/a7-py`, workflow `release.yml`, and environment `pypi`.
5. Add stronger hosted secret scanning if the repository host supports it.
