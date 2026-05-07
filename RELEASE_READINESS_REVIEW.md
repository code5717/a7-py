# Release Readiness Review

Date: 2026-05-07

## Result

The repository is substantially more release-ready than before this pass:

- installable `a7` CLI entrypoint
- compatibility `main.py` wrapper
- debug and release artifact builder for Zig and C
- committed docs lockfile for deterministic docs builds
- CI workflow for tests, backends, artifacts, package build, and docs build
- release checklist, security policy, and updated status docs

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
- `cd site && npm audit --omit=dev --audit-level=moderate`
- `cd site && npm run build`
- built wheel installed into a temporary virtualenv and invoked as `a7`
- `git diff --check`

## Fixed In This Pass

- Package metadata now has a real description and a console script.
- Runtime-only test dependency moved into the dev dependency group.
- `main.py` now delegates to `src.cli:main`.
- `scripts/build_examples.py` builds and verifies debug/release artifacts for
  both backends.
- `run_all_tests.sh` now covers C backend tests, C E2E, error-stage audit,
  debug/release artifact builds, docs style, and full pytest.
- GitHub CI now runs Python tests, backend verifiers, artifact builds, package
  build, docs style, docs lint, and docs build.
- GitHub Pages deploy now uses `npm ci` with `site/package-lock.json`.
- README, SPEC, release docs, status docs, and agent docs describe the same
  release commands.

## Residual Risks

- `a7-py` is not a sandbox. Do not compile or run untrusted A7 source.
- `fall` is parsed but not semantically validated or lowered.
- Full ownership/lifetime safety is not implemented.
- Built-in stdlib imports are virtual and still need unification with file-based
  module semantics.
- Backend parity is verified for examples, not all possible source programs.
- Tag-based publishing is not wired.
- Dependency audits are configured for known advisories, not unknown supply-chain
  compromise.

## Recommended Next Pass

1. Replace Zig backend `@compileError("unsupported")` fallbacks with compiler
   codegen errors.
2. Add tag-based release workflow after choosing the package publishing target.
3. Add secret scanning to CI.
4. Expand differential backend tests beyond examples.
5. Unify virtual stdlib imports with file-based module semantics.
