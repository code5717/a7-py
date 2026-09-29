# GLM tooling review

Advisory review through `opencode run -m zai-coding-plan/glm-5.3`, completed
2026-09-19. The prompt included the repository recursion guard. No provider
limit or authentication failure was reported. Scope excludes unrelated compiler
changes. Body below preserves the reviewer's output.

## Advisory review — verdict: all three root findings are fixed; flat-download manifests still work; no regression found in scope

Evidence verified by running `pytest test/test_release_tooling.py -k "manifest or flat"` (8 passed) and `bun test scripts/serve.test.ts` (1 pass, 17 expects).

### 1. Preview encoded traversal — fixed (serve.ts)

- Old code decoded and `path.join`ed with no traversal or containment check; new code rejects NUL/backslash/`..` segments after a single decode (site/scripts/serve.ts:24-30), enforces prefix-with-separator containment (serve.ts:17,32-33), re-resolves with `realpath` and re-checks containment before every read — this also blocks symlink escapes, including the directory-index symlink case (serve.ts:35-38). Binds 127.0.0.1 only (serve.ts:19).
- Double-encoding (`%252e`) is not exploitable: one decode yields a literal `%2e` filename that no segment check needs; it 404s.
- Tests assert 403 for `..%2f`, `%2e%2e%2f`, symlinked file, symlinked dir-index; 400 for malformed encoding (serve.test.ts:26-31). Wired into CI via the new `bun run test` step (ci.yml:116-118; script exists at site/package.json:13).
- Residual (informational): no `X-Content-Type-Options: nosniff`; same-origin `image/svg+xml` allows script execution if a hostile SVG lands in `dist` (serve.ts:9); small TOCTOU window between `realpath` check and `Bun.file` open (serve.ts:40). All low-impact for a localhost preview tool.

### 2. Release manifest absolute-path guard — fixed (verify_release_manifest.py)

- Old code returned `base_dir / candidate` and `base_dir / candidate.name` with no resolved containment check, so symlinks inside `base_dir` could satisfy entries from outside; the new `checked()` resolves symlinks and requires `is_relative_to(base_dir | ROOT)` for every returned path (scripts/verify_release_manifest.py:53-60). `..` in any position was and remains rejected (verify_release_manifest.py:50-51).
- Absolute external paths now read only the local basename, never the publisher's path (verify_release_manifest.py:62-71). Tests: external absolute file with correct hash and local symlink both rejected (test_release_tooling.py:461-477); flat download of a manifest naming the publisher's absolute path verifies against local bytes only (test_release_tooling.py:480-494).
- Flat-download compat preserved: relative candidates try `base_dir/candidate`, `base_dir/candidate.name` (flat), then `ROOT/candidate` (verify_release_manifest.py:73-77); pre-existing tests for flat and repo-relative manifests still pass.
- Residual (low/informational): allowed roots include the whole repo, so a manifest can "verify" any repo file whose hash matches — by design for repo-relative manifests, but worth documenting; TOCTOU between `resolve()`, `is_file()`, and `open()` — local-race only; the absolute-path-with-local-symlink-basename combination is guarded by the same `checked()` path but not directly tested; `--base-dir` flag has no test in these two new tests (pre-existing gap).

### 3. Isolated uvx dependency audit — fixed (ci.yml, release.yml)

- Old `uvx --from pip-audit==2.10.0 pip-audit --strict` audited pip-audit's own uvx environment, not the project. New steps export the locked dependency set and audit that: `uv export --locked --all-groups --no-emit-project` then `pip-audit --strict -r` (ci.yml:52-55, release.yml:66-69). Identical in both workflows; `--all-groups` includes dev dependencies.
- Residual limitations (low, detection-only): unpinned `python -m pip install uv` at ci.yml:34-35 / release.yml:39-40 and unpinned transitive deps of pip-audit via uvx — runner trusts PyPI at run time (pre-existing, outside this diff); audits run after `uv sync`/pytest/run_all_tests, so a malicious dependency executes before it is flagged; `bun audit --audit-level=moderate` (ci.yml:110, release.yml:77) does not fail on low advisories and runs after `bun install` (postinstall scripts already executed).

### Coverage limits

I reviewed only the scoped files plus their diffs; the large set of unrelated modified compiler/doc files was not examined. CI and release workflows were not executed; findings there rest on static reading. Bun version used locally (1.4.2) differs from the pinned CI version (1.3.11 at ci.yml:102), so local test results approximate CI behavior. pip-audit/bun-audit efficacy is bounded by their upstream vulnerability databases; neither covers the project's own code or the unpinned runner tooling chain.
