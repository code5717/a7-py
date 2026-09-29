# Dependency-security follow-up: `site/bun.lock` + `site/package.json`

**Result: no known vulnerabilities found against any of the 66 exact locked package versions, via a validated OSV API fallback. `bun audit` remains unqualified (3rd consecutive registry 503).**

## 1. `bun audit` attempt (normal path)

```
bun audit v1.4.2 (744846f84)
error: POST https://registry.npmjs.org/-/npm/v1/security/advisories/bulk - 503
```

Exit code 1, run once in `site/` as instructed. This matches root's two failures; the npm advisory endpoint is still down for this run. **`bun audit` is unqualified — no result from it.**

## 2. Fallback: OSV API (clearly labeled — not equivalent to `bun audit`)

- Source: `https://api.osv.dev/v1/querybatch` (Google OSV), exact `name@version` match per locked entry; detail lookups via `/v1/vulns/{id}`.
- Method: parsed `site/bun.lock` (JSONC) directly, extracted the resolved `name@version` from every package entry (66 entries, 66 unique — no duplicates). Includes the 6 packages bundled inside `@tailwindcss/oxide-wasm32-wasi` and all platform-specific optional binaries (win32/darwin/freebsd/android/musl), i.e. broader than what's installed on this host.
- The workspace root `a7-docs-site@0.16.0` is private/unpublished and was not queried.
- Script ran from `/tmp/opencode`; **no repository files were created, modified, or deleted by this review** (the repo's uncommitted changes, including `site/package.json`, predate this review and belong to the controlling session).

### Exact package coverage (66/66 queried, all answered, 0 errors)

`@emnapi/core@1.10.0`, `@emnapi/runtime@1.10.0`, `@emnapi/wasi-threads@1.2.1`, `@jridgewell/gen-mapping@0.3.13`, `@jridgewell/remapping@2.3.5`, `@jridgewell/resolve-uri@3.1.2`, `@jridgewell/sourcemap-codec@1.5.5`, `@jridgewell/trace-mapping@0.3.31`, `@napi-rs/wasm-runtime@1.1.4`, `@parcel/watcher@2.5.6` (+ 12 platform subpackages @2.5.6: android-arm64, darwin-arm64/x64, freebsd-x64, linux-arm-glibc/arm-musl/arm64-glibc/arm64-musl/x64-glibc/x64-musl, win32-arm64/ia32/x64), `@tailwindcss/cli@4.3.0`, `@tailwindcss/node@4.3.0`, `@tailwindcss/oxide@4.3.0` (+ 12 subpackages @4.3.0: android-arm64, darwin-arm64/x64, freebsd-x64, linux-arm-gnueabihf/arm64-gnu/arm64-musl/x64-gnu/x64-musl, wasm32-wasi, win32-arm64-msvc/x64-msvc), `@tybys/wasm-util@0.10.2`, `detect-libc@2.1.2`, `enhanced-resolve@5.21.3`, `graceful-fs@4.2.11`, `is-extglob@2.1.1`, `is-glob@4.0.3`, `jiti@2.7.0`, `lightningcss@1.32.0` (+ 11 subpackages @1.32.0), `magic-string@0.30.21`, `mri@1.2.0`, `node-addon-api@7.1.1`, `picocolors@1.1.1`, `picomatch@4.0.4`, `source-map-js@1.2.1`, `tailwindcss@4.3.0`, `tapable@2.3.3`, `tslib@2.8.1`

All 66 queries returned HTTP 200 with per-package results; no query errors, no timeouts.

### Findings

- **0 OSV advisories match any locked exact version** (all severity levels, not just moderate+).
- Positive control confirms the query path is not vacuously passing: `minimist@1.2.0` → 2 advisories, `lodash@4.17.20` → 5 advisories, while `tailwindcss@4.3.0` → 0, all as expected.

## 3. Coverage caveats (do not overstate)

- OSV aggregates GHSA and other upstream databases on its own sync schedule; it is **not** identical to the npm registry's bulk-advisory endpoint that `bun audit` uses, and I make no claim that it covers everything `npm audit` would. Advisory lag on either side is possible.
- The check is point-in-time (2026-09-19) and version-exact; it says nothing about versions outside the lock.
- Only `site/` was in scope. The Python dependency tree (`uv.lock`) was not part of this task.

**Disposition (advisory):** no action required on `site/` dependencies based on current OSV data. When the npm advisory endpoint recovers, a confirming `bun audit --audit-level=moderate` run in `site/` would close the remaining gap.
