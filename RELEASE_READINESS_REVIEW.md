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
- release checklist, security policy, and updated status docs
- Node 24-compatible GitHub workflow actions for CI, Pages deploy, artifact
  upload/download, and draft GitHub releases
- checksum-verified Zig 0.15.2 install steps in CI and release workflows
- semantic recursion rejection for direct, mutual, and local function-pointer
  alias call cycles, with scope-aware handling for local function-pointer
  shadowing
- consolidated docs-site navigation with curl.md-friendly Markdown entry points
  under `site/public/llms.txt` and `site/public/docs/`
- C backend specialization for simple top-level generic function calls and used
  generic struct instances
- virtual `std/io`, `io`, `std/math`, and `math` imports registered through the
  module resolver, with alias-safe backend lowering
- public docs-site primary navigation and homepage messaging centered on A7
  itself, while curl.md/plugin resources remain available from docs surfaces

This is not a claim that the implementation is free of all bugs or
vulnerabilities. For a compiler and native-code build pipeline, that standard is
not factually provable from local tests alone.

## Evidence Checked

- `uv run a7 --help`
- `PYTHONPATH=. uv run pytest test/test_release_tooling.py -q`
- `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- `uv run python scripts/build_examples.py --profile release --backend both --clean`
- `uv run python scripts/verify_backend_parity.py`
- `uv run pytest test/test_codegen_c.py::test_c_backend_lowers_simple_generic_function test/test_codegen_c.py::test_generated_c_runs_multiple_generic_instantiations -q`
- `uv run pytest test/test_stdlib_registry.py test/test_module_resolver.py test/test_cli_failures.py::test_cli_unknown_virtual_stdlib_function_returns_semantic_error test/test_codegen_c.py::test_generated_c_resolves_stdlib_import_aliases test/test_codegen_zig.py::TestCodePatterns::test_stdlib_import_aliases_emit_zig_stdlib_calls -q`
- `./run_all_tests.sh`
- `uv build`
- local `dist/` cleanup before package builds
- `uvx --from pip-audit==2.10.0 pip-audit --strict`
- `uvx --from bandit==1.9.4 bandit -r a7 scripts main.py -q --skip B404,B603`
- `uv run python scripts/check_no_secrets.py`
- `cd site && npm audit --omit=dev --audit-level=moderate`
- `cd site && npm run check`
- direct Chromium CDP preview checks for canonical and compatibility hash links
  such as `#/language#standard-library`, `#/stdlib`, `#/pipeline#backend-notes`,
  and `#/cli#flags`
- preview HTTP checks for `/a7-py/llms.txt`, `/a7-py/docs/index.md`,
  `/a7-py/docs/status.md`, `/a7-py/sitemap.xml`, and `/a7-py/robots.txt`
- built wheel installed into a temporary virtualenv and invoked as `a7`
- built wheel now installs a project-specific top-level `a7` package instead of
  a generic `src` package
- `git diff --check`
- hosted CI and Deploy Docs must be checked after each release-candidate push;
  the current workflows cover docs, pytest, dependency audits, error-stage
  verification, Zig and C example verification, backend parity checks, debug
  artifacts, release artifacts, and package build.
- manual release workflow dispatch passed on `master`; run `25517785179` uploaded
  `python-package-distributions` artifact `6864726540` and `release-bundles`
  artifact `6864741365`, while the tag-only GitHub release job was skipped as
  intended.
- manual release workflow dispatch passed again on `master` after checksum
  manifest wiring; run `25524734727` completed release gate, package build,
  docs archive, release example artifact archive, checksum generation, and
  release-bundle upload. Downloaded `release-bundles` contained `SHA256SUMS`,
  `a7-docs-site.tar.gz`, and `a7-example-artifacts-linux-x86_64-zig0.15.2-release.tar.gz`.
- manual release workflow dispatch `25525956855` passed after manifest
  verification was added; downloaded release bundles and Python distributions
  were reconstructed under `dist/` and verified with
  `scripts/verify_release_manifest.py`.
- manual release workflow dispatch `25526402237` passed on commit `65f9624`
  after the curl.md docs-surface update; downloaded release bundles and Python
  distributions were reconstructed under `dist/` and verified with
  `scripts/verify_release_manifest.py`.
- manual release workflow dispatch `25527020391` passed on commit `67da15e`
  after archive-content verification was added. Downloaded release bundles and
  Python distributions were reconstructed under `dist/`; docs/native archives
  passed `scripts/verify_archive_contents.py`, and `SHA256SUMS` passed
  `scripts/verify_release_manifest.py`.
- hosted CI run `25527971161` passed on commit `48847f8` after the expanded
  curl.md navigation update, including docs style, secret scanning, docs
  dependency audit, docs lint/build, pytest, Python dependency audit,
  error-stage verification, Zig/C example verification, backend parity, debug
  artifacts, release artifacts, and package build.
- hosted Deploy Docs run `25527971188` passed on commit `48847f8`; hosted
  fetches for `/a7-py/llms.txt`, `/a7-py/docs/index.md`, and
  `/a7-py/docs/plugins/codex.md` confirmed the deployed curl.md navigation and
  plugin docs.
- hosted CI run `25528605790` passed on commit `8407a97` after simple C generic
  function lowering was added, including pytest, Python dependency audit,
  error-stage verification, Zig/C example verification, backend parity, debug
  artifacts, release artifacts, package build, docs style, secret scanning,
  docs dependency audit, docs lint, and docs build.
- hosted Deploy Docs run `25528605791` passed on commit `8407a97`; hosted
  fetches for `/a7-py/docs/status.md` and `/a7-py/llms-full.txt` confirmed the
  deployed generic-status wording.
- hosted CI run `25532352797` passed on commit `ca00e0e` after error-stage
  audit logic was deduplicated into `scripts/error_stage_common.py`, including
  docs, pytest, Python dependency audit, error-stage verification, Zig/C
  example verification, backend parity, debug artifacts, release artifacts, and
  package build.
- hosted Deploy Docs run `25532352789` passed on commit `ca00e0e`.
- hosted CI run `25532650949` passed on commit `05dff14` after the public site
  was re-centered around A7, including docs, pytest, Python dependency audit,
  error-stage verification, Zig/C example verification, backend parity, debug
  artifacts, release artifacts, and package build.
- hosted Deploy Docs run `25532650954` passed on commit `05dff14`; a live
  browser-harness check confirmed the deployed homepage title
  `Simple, fast systems code.`, eyebrow `A7 language`, and primary navigation
  `Start`, `Language`, `Examples`, `Compiler`, `Status`, `Docs`, `GitHub`.
- local `./run_all_tests.sh` passed after expanding backend parity to 16
  selected cases:
  parser/tokenizer 501 passed; semantic 305 passed; compiler/CLI/backend 322
  passed; Zig examples 38/38; C examples 38/38; backend parity 16/16; debug
  artifacts 76/76; release artifacts 76/76; error-stage checks 61/61; docs
  style ok; secrets check ok; the then-current pytest suite passed; summary
  12/12.
- local manual report inspection confirmed `037_language_tour` has
  `compile_ok`, backend validation (`ast_ok` for Zig, `syntax_ok` for C),
  `build_ok`, `run_ok`, and `output_match` set to true in both JSON reports.
- hosted CI run `25533359030` passed on commit `68f1429` after adding
  `037_language_tour.a7` and the full-context docs file, including docs,
  pytest, Python dependency audit, error-stage verification, Zig/C example
  verification, backend parity, debug artifacts, release artifacts, and
  package build.
- hosted Deploy Docs run `25533359054` passed on commit `68f1429`; a hosted
  fetch of `/a7-py/llms-full.txt` confirmed the deployed `# A7 Full Context`
  aggregate format.
- Claude CLI reviewed the language-tour and `llms-full.txt` direction as a
  second opinion before commit `68f1429`; the final patch applied its concrete
  recommendations to make `llms-full.txt` more self-contained and avoid
  overselling the compact tour as exhaustive.
- local `uv run python scripts/verify_backend_parity.py` passed after expanding
  the differential suite: backend parity 18/18. Manual report inspection
  confirmed matching Zig and C output for the new defer, union, generic,
  enum-match, heap-struct, fallthrough, nested fallthrough, and nested-array
  cases, including a 3D fixed-array case. The C parity build uses
  `-Werror=incompatible-pointer-types`.
- focused C backend audit found that return values were emitted after deferred
  cleanup in C; local focused regression now confirms return values are captured
  before deferred `del` runs.
- local Ruby stdlib YAML parse passed for every workflow after release/CI
  concurrency, package-output cleanup, post-download release checksum
  verification, and Claude workflow trigger hardening were added.
- local `./run_all_tests.sh` passed after the C return-temp type fix:
  parser/tokenizer 501 passed; semantic 305 passed; compiler/CLI/backend 324
  passed; Zig examples 38/38; C examples 38/38; backend parity 16/16; debug
  artifacts 76/76; release artifacts 76/76; error-stage checks 61/61; docs
  style ok; secrets check ok; total pytest 1204 passed; summary 12/12.
- Online check of GitHub's current action release pages confirmed
  `actions/upload-artifact@v7` and `actions/download-artifact@v8` exist, so the
  release workflow's artifact actions are not using nonexistent major tags.
- All workflow actions are pinned to immutable commits, and Dependabot is
  configured for GitHub Actions, Python, and docs npm dependency updates.
- Tag release runs now generate GitHub artifact attestations for `SHA256SUMS`,
  Python package files, docs archive, and native example archive.
- Manual release workflow dispatch `25536114185` passed on commit `582f47e`,
  including release gates, package/docs/native artifacts, checksum generation,
  GitHub artifact attestations, and release bundle upload. Downloaded release
  assets verified locally with `scripts/verify_release_manifest.py`, and
  `gh attestation verify` passed for the package, wheel, docs archive, and
  native example archive.
- Hosted CI run `25539118297` passed on commit `d678c80`, including pytest,
  Python dependency audit, Bandit static security scanning, error-stage
  verification, Zig/C example verification, backend parity, debug artifacts,
  release artifacts, package build, and clean wheel-install verification.
- Hosted Deploy Docs run `25539118290` passed on commit `d678c80`.
- Manual release workflow dispatch `25539300989` passed on commit `d678c80`,
  including release gate, Python dependency audit, Bandit static security
  scanning, docs runtime dependency audit, package build, wheel install, docs
  build, release example artifacts, archive verification, checksum generation,
  GitHub artifact attestations, and release-bundle upload. The
  `create-github-release` job was skipped because draft GitHub release creation
  is intentionally gated to `refs/tags/v*` runs.
- A follow-up hardening pass pinned the CI/release Python audit tools, removed
  unsafe paths in the downloaded release-manifest verifier, restricted
  file-backed module imports to configured search paths, added a compiler-step
  timeout to example artifact builds, and expanded wheel smoke verification to
  both Zig and C codegen.
- local `./run_all_tests.sh` passed after implementing fallthrough lowering:
  parser/tokenizer 501 passed; semantic 320 passed; compiler/CLI/backend 326
  passed; Zig examples 38/38; C examples 38/38; backend parity 18/18; debug
  artifacts 76/76; release artifacts 76/76; error-stage checks 61/61; docs
  style ok; secrets check ok; total pytest 1227 passed; summary 12/12.
- local `./run_all_tests.sh` passed after implementing branch-local match
  capture patterns: parser/tokenizer 501 passed; semantic 332 passed;
  compiler/CLI/backend 326 passed; Zig examples 38/38; C examples 38/38;
  backend parity 19/19; debug artifacts 76/76; release artifacts 76/76;
  error-stage checks 61/61; docs style ok; secrets check ok; total pytest
  1239 passed; summary 12/12.
- local focused generic struct verification passed after retaining concrete
  generic struct literal instance types and adding C monomorphization for used
  generic struct instances: backend parity 20/20, focused semantic/codegen
  tests 10 passed, and generic/codegen/parity pytest 183 passed after updating
  the parity assertion.
- local `./run_all_tests.sh` passed after generic struct instance lowering:
  parser/tokenizer 501 passed; semantic 336 passed; compiler/CLI/backend 328
  passed; Zig examples 38/38; C examples 38/38; backend parity 20/20; debug
  artifacts 76/76; release artifacts 76/76; error-stage checks 61/61; docs
  style ok; secrets check ok; total pytest 1245 passed; summary 12/12.
- local `./run_all_tests.sh` passed after example and parity coverage
  expansion: parser/tokenizer 501 passed; semantic 336 passed;
  compiler/CLI/backend 328 passed; Zig examples 38/38; C examples 38/38;
  backend parity 24/24; debug artifacts 76/76; release artifacts 76/76;
  error-stage checks 61/61; docs style ok; secrets check ok; total pytest
  1245 passed; summary 12/12.
- local manual report inspection confirmed matching Zig and C output for the
  four new parity cases: type-set generic constraints, explicit enum
  discriminants through match, stdlib math mappings, and edge operator
  assignments/comparisons.
- hosted CI run `25545566335` passed on commit `cdcf7e3` after example and
  parity coverage expansion, including docs, pytest, Python dependency audit,
  Bandit static security scanning, error-stage verification, Zig/C example
  verification, backend parity, debug artifacts, release artifacts, package
  build, and clean wheel-install verification.
- hosted Deploy Docs run `25545566352` passed on commit `cdcf7e3`.
- local focused import regression passed after file-backed imports were made to
  fail closed before backend codegen: `test/test_cli_failures.py` and
  `test/test_module_resolver.py` reported 18 passed. Manual CLI probes
  confirmed existing `helper :: import "helper"` fails with exit code 6 for
  codegen modes and does not write target code, while semantic mode still
  validates resolver loading.
- local `./run_all_tests.sh` passed after file-backed import fail-closed
  behavior and docs updates: parser/tokenizer 501 passed; semantic 336 passed;
  compiler/CLI/backend 330 passed; Zig examples 38/38; C examples 38/38;
  backend parity 24/24; debug artifacts 76/76; release artifacts 76/76;
  error-stage checks 61/61; docs style ok; secrets check ok; total pytest
  1247 passed; summary 12/12.
- hosted CI run `25547403153` passed on commit `1234a44` after file-backed
  imports were made to fail closed before codegen, including docs, pytest,
  Python dependency audit, Bandit static security scanning, error-stage
  verification, Zig/C example verification, backend parity, debug artifacts,
  release artifacts, package build, and clean wheel-install verification.
- hosted Deploy Docs run `25547403136` passed on commit `1234a44`.
- local `npm run check` in `site/` passed after updating the public status and
  language docs for the generic struct behavior.
- hosted CI run `25541793153` passed on commit `5baa7f7` after fallthrough
  lowering was added, including docs, pytest, Python dependency audit, Bandit
  static security scanning, error-stage verification, Zig/C example
  verification, backend parity, debug artifacts, release artifacts, package
  build, and clean wheel-install verification.
- hosted Deploy Docs run `25541793145` passed on commit `5baa7f7`.

## Fixed In This Pass

- Package metadata now has a real description and a console script.
- Runtime-only test dependency moved into the dev dependency group.
- `main.py` now delegates to `a7.cli:main`.
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
  creating a GitHub release.
- Release workflow permissions are split so the gate/artifact build job keeps
  read-only repository contents access; only the tag-only draft release job gets
  `contents: write`.
- CI and release workflows now use concurrency groups to prevent redundant or
  racing runs.
- Release builds clean `dist/` before `uv build`, and the tag-only draft release
  job re-verifies downloaded `SHA256SUMS` before attaching artifacts.
- Release builds generate GitHub artifact attestations for all release assets
  before the artifacts are uploaded or attached to draft releases.
- Secret-backed Claude workflows now require repository owner/member/collaborator
  author association for comment-triggered runs, and automated Claude PR review
  skips fork pull requests.
- Claude-triggered workflows now use per-issue/PR concurrency groups so newer
  runs cancel stale automation for the same target.
- All workflow actions are pinned to immutable commits, and Dependabot now
  covers GitHub Actions, Python, and docs npm dependencies.
- Automated Claude PR review now treats PR titles, bodies, comments, and diffs
  as untrusted content to review rather than instructions to follow.
- `docs/SPEC.md` no longer contains the duplicated type/control-flow/function/
  memory sections inside the modules section, and later section numbering now
  matches the table of contents.
- C backend `for-in` lowering now caches iterable expressions before loop
  length and element access.
- Untagged union literals now initialize exactly one named field, union field
  access type-checks declared fields, and the union example runs through both
  native backends.
- Array literal assignment now checks declared lengths and nested element types,
  and C nested fixed-array declarations emit true multidimensional arrays rather
  than arrays of pointers.
- Parser ambiguity around `new i32(42)` is locked down as a syntax error while
  `new(i32)` remains valid allocation syntax.
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
  Node 24-compatible immutable SHAs.
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
  string slices, labels, function pointers, defer unwinding, untagged unions,
  generic function specialization, enum match expressions, heap struct
  allocation, and nested fixed arrays.
- C backend `for-in` lowering now emits pointer-to-array cache declarations for
  nested fixed arrays instead of decaying them to invalid pointer-to-pointer
  types.
- C backend return lowering now captures non-void return values before emitting
  deferred cleanup, avoiding use-after-free when a return expression reads a
  value owned by a deferred `del`.
- Public docs-site top navigation is reduced and old CLI, stdlib, pipeline, and
  testing pages are consolidated into Start, Language, and Compiler sections
  with compatibility aliases and verified hash scrolling.
- `llms.txt`, `llms-full.txt`, and public Markdown docs under
  `site/public/docs/` provide stable curl.md/agent entry points for CLI,
  language, compiler, examples, release, and status information.
- The public docs map now follows Introduction, Guide, Plugins, LLM Resources,
  Contributing, and A7 Reference groups, with static Markdown pages for API/SDK,
  agent/editor plugins, skills, deploy, and kitchen-sink coverage.
- Site metadata, README, robots, and sitemap now consistently use
  `https://code5717.github.io/a7-py/`.
- Local release documentation now explicitly cleans `dist/` before package
  builds so stale versioned artifacts are not accidentally mixed into a manual
  release upload.
- `COMPLETION_AUDIT.md` maps the release-readiness objective to concrete
  verification evidence and records the requirements that remain incomplete.
- Release tooling now generates a deterministic `SHA256SUMS` manifest for
  draft GitHub release artifacts and verifies that expected package, docs, and
  native artifact archive paths are present before upload, then re-checks the
  recorded hashes and sizes on disk.
- Release workflow now emits GitHub artifact attestations for the checksum
  manifest and release assets, giving consumers a provenance check in addition
  to `SHA256SUMS`.
- Release manifest verification now accepts both the workflow `dist/...` layout
  and the flat downloaded-release-assets layout used before publishing a draft
  release.
- Release tooling now verifies required members inside the docs and native
  example archives before checksum generation, including `llms.txt`,
  `llms-full.txt`, public Markdown docs, and `001_hello` Zig/C outputs.
- Zig/C example verifier entrypoints now share compile/build/run/report logic
  through `scripts/verify_examples_common.py`, while preserving their JSON
  report contracts.
- The error-stage verifier and pytest matrix now share mode sets, source
  fixtures, CLI runner, JSON helpers, and 61-check audit construction through
  `scripts/error_stage_common.py`.
- The public docs site now uses A7-first primary navigation and homepage copy;
  curl.md, plugin, and LLM resources remain reachable from docs pages instead
  of framing the entire site.
- Added `examples/037_language_tour.a7`, a commented compact language tour
  that introduces the current stable language surface from one verified file;
  the Language page and `site/public/docs/language.md` remain the one-page
  reference.
- CI/release Python audit tools are pinned to exact versions instead of fetching
  arbitrary latest tool releases during release gates.
- The committed-secret guard now flags sensitive `.env`/private-key-style
  filenames even when content is binary or unreadable, and avoids duplicate
  generic/specific findings on the same line.
- The release-manifest verifier rejects parent-directory traversal and unsafe
  absolute paths while preserving the documented flat downloaded-assets flow.
- File-backed module imports are contained to configured search paths and reject
  absolute or parent-directory traversal module paths.
- Example artifact compilation has a timeout, and wheel-install verification now
  checks both installed Zig and C code generation paths.
- `fall` now lowers in both native backends for the documented narrow form:
  the final direct statement of a non-final match case. Invalid placements
  remain semantic errors.

## Residual Risks

- `a7-py` is not a sandbox. Do not compile or run untrusted A7 source.
- Full ownership/lifetime safety is not implemented.
- Built-in `std/io` and `std/math` imports are virtual modules; `std/string`,
  `std/mem`, and collections remain planned rather than current public modules.
- Backend parity is verified for examples and selected differential smoke
  programs, including core control flow, match, slices, string slices, labels,
  function pointers, contextual array literal assignment, defer unwinding,
  untagged unions, generic function specialization, enum match expressions,
  heap struct allocation, and nested fixed arrays. It is still not exhaustive
  for all possible source programs.
- Dependency audits are configured for known advisories, not unknown supply-chain
  compromise.
- All workflow actions are pinned to full commit SHAs resolved from current
  upstream release tags on 2026-05-08.
- Secret scanning is pattern- and filename-based and should be supplemented by
  repository host protections when publishing publicly.
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

1. Expand nested/composite generic specialization and method-style propagation
   parity beyond the currently covered generic struct instances.
2. Add stronger hosted secret scanning if the repository host supports it.
3. Expand backend parity for every new language feature, including additional
   fallthrough and capture-pattern edge cases.
