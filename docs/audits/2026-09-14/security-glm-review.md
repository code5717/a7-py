# Security review — repository and delivery boundaries (GLM)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it; none of its findings were superseded as of 2026-09-16.

| Field | Value |
| --- | --- |
| Reviewer | Z.AI GLM-5.3, dedicated cybersecurity reviewer (advisory, external to the coordinating session) |
| Date | 2026-09-14 |
| Baseline revision | `701c67936c70ad2b0608326e23e56cc5d38c9fdb` |

Scope: trust boundaries for compiler input and import paths, source artifacts,
output path handling, symlinks and canonicalization, subprocess construction and
tool discovery, the local website preview, frontend injection and external
links, package, release and CI permissions, artifact integrity,
dependency and security gate coverage, accidental secret publication, and
denial-of-service robustness of the compiler process. Memory-semantics
findings belong to `memory-safety-glm-review.md` and are excluded, except where
they cross a delivery or error boundary.

Standing framing, from `AGENTS.md` and `docs/SECURITY.md`: A7 is
**not a sandbox** for untrusted source. The compiler emits Zig that is built
and run with host toolchain privileges. Compiled-program escapes are the
documented, accepted model, not findings. This review adds no sandbox
requirement and executed no exploit payloads.

## Verification conditions and incidents

- An in-audit attempt to read `/etc/hostname` through the local preview
  traversal (`/a7-py/docs/%2e%2e...`) was **rejected by the automatic
  external-directory approval** before any file content was returned. That
  denied operation was not retried, and no external directory has been read
  since. Containment failure is instead established by (a) coordinator
  evidence below and (b) source analysis.
- A read of the pip-audit inventory at `/tmp/a7-audit-20260914/...` was also
  initially rejected; the coordinator relocated the same evidence into the
  repository at `evidence/pip-audit-target-inventory.json`, which was used.
- The local preview (`localhost:4173`) is **no longer running** (connection
  refused at review time). Runtime findings therefore rest on: coordinator
  HTTP evidence (below), my earlier successful read-only `GET /a7-py/` and
  `GET /a7-py/llms.txt` probes (HTTP 200, expected docs content), and source
  inspection. Local preview behavior must not be conflated with GitHub Pages
  hosting, which serves only the built `site/dist` output.
- Two sub-agent deep-dives (CI/release, DoS robustness) failed with provider
  "Rate limit reached" errors; their scope was re-covered by direct review
  below. The site sub-agent completed; its top findings were independently
  re-verified line-by-line before incorporation.
- `uv`/mise shims failed in this shell (`mise ERROR` on `uv run`). Harmless
  reproductions used the repository's `.venv/bin/python` directly. No global
  tool configuration was changed. The full gate was not run; the coordinator
  owns gates.

## Findings

Priorities: P1 = fix before next release; P2 = fix soon / defense-in-depth
with real reachability; P3 = hardening. "Verified" = reproduced or proven
from source in this review; "Attributed" = reported by the coordinator or a
sub-agent and independently confirmed from source here.

### SEC-1 (P1) — Preview server: path traversal after decoding, plus non-loopback default bind

Verified (source) + Attributed (runtime, coordinator).

- `site/scripts/serve.ts:21-24`: the request path is prefix-stripped, then
  `decodeURIComponent`'d, then joined: `path.join(root, rel)` with **no
  containment check**. The WHATWG `URL` parser normalizes literal `/../`
  segments, but a `%2f`-encoded separator survives parsing and becomes `/`
  only after decoding, so `..%2f` sequences escape `site/dist`.
- Coordinator evidence (recorded verbatim in `root-review.md` §R3):
  `GET /a7-py/..%2fpackage.json` returned the source `site/package.json`
  with HTTP 200 — a file outside `dist/`. No sensitive file was read by
  either session.
- `site/scripts/serve.ts:18-19`: `serve({ port, ... })` sets no `hostname`;
  Bun's documented default bind is `0.0.0.0`, so the socket is exposed on
  non-loopback interfaces (the log line at :33 prints `localhost`, so the
  exposure is not obvious to the developer). **Actual remote reachability
  was not demonstrated** — it depends on host networking, firewalls, and
  address scope; the verified fact is the non-loopback default bind plus
  the traversal, not "any LAN host can connect".
- Impact, realistically: this is a **developer-local** server documented in
  `AGENTS.md` (`site && bun run preview`), not the deployed site. The
  verified escape reads one repo file (`site/package.json`) outside
  `dist/`; combined with a non-loopback bind on a host where such traffic
  is routable (e.g. shared Wi-Fi), the mechanism would expose files
  readable by the developer's account — a conditional, environment-dependent
  file-read exposure, not a demonstrated remote exploit. It does not affect
  GitHub Pages output.
- Fix requirements (requirements only, not approved or tested code;
  maintainers must write and test the implementation):
  1. Decode each path segment safely, tolerating malformed escapes (see
     SEC-8), and perform dot-segment/normal-form handling **after** decoding
     so `%2e%2e`, `%2f`, double-encoded, and mixed forms cannot reintroduce
     separators or dot segments.
  2. Containment must be checked on the **final resolved path**, including
     symlink resolution, against a precomputed absolute root, for the
     default `/index.html` mapping, the 404 fallback, and directory
     `index.html` joins alike.
  3. The root path itself (`site/dist`) must remain correct when the
     request is `/`, empty, or exactly the base prefix.
  4. The preview should bind loopback by default (`127.0.0.1`), with any
     wider bind requiring an explicit opt-in.
  Verification: re-run the harmless `..%2fpackage.json` request and assert
  a `dist`-only resolution (404 or contained file), plus unit checks that
  `%2f`, `%2e%2e`, double-encoded, mixed, absolute-path, and
  symlink-escaping forms are all contained; assert the listening socket is
  loopback-only by default.

### SEC-2 (P1) — The pip-audit security gate audits the wrong environment

Verified (inventory evidence + workflow source).

- `uvx --from pip-audit==2.10.0 pip-audit --strict` runs pip-audit inside
  the **ephemeral uvx tool environment**, not the project environment
  created by `uv sync --locked --all-groups`. Invocations:
  `.github/workflows/ci.yml:53`, `.github/workflows/release.yml:67`, and
  documented as the local gate in `docs/SECURITY.md:23`.
- Evidence: the audited set is the `dependencies` array of
  `evidence/pip-audit-target-inventory.json`, which contains 28 entries —
  pip-audit's own tool dependency closure (`cyclonedx-python-lib`,
  `pip-api`, `pip-requirements-parser`, `boolean-py`, …, plus `pip-audit`
  and `pip` themselves). The audited set does **not** contain the project's
  locked dependencies (`pyproject.toml`: runtime `rich`; dev `pytest`,
  `build`; with their transitive locked pins from `uv.lock`). Name overlap
  is not a valid criterion either way: the `rich` 15.0.0 entry belongs to
  pip-audit's own closure, and a corrected requirements-export audit would
  legitimately not list the local `a7-py` package itself — the correct
  comparison is the full locked runtime/dev dependency set **with versions**
  from `uv.lock`. `evidence/pip-audit.log` records that the uvx tool
  environment installed 28 packages before the audit; that install log line
  is not the audit enumeration (the counts coinciding is not evidence of
  identity). The coordinator independently reached the same conclusion
  (`root-review.md` "Verification boundaries").
- Impact: the "Audit Python dependencies" step is green **regardless** of
  advisories in the project's resolved dependency set. The gate currently
  proves only that pip-audit's own toolchain is advisory-free.
  `docs/SECURITY.md:51` already frames dependency audits narrowly, but the
  CI step name promises more than it delivers — a gate-integrity problem,
  and the practical risk is a known-CVE rich/pytest release passing release
  checks unnoticed. **No corrected project-target audit has been run**, so
  this review makes no claim about the current advisory status of the
  project's locked dependencies.
- Fix (pick one, then verify the corrected run): run inside the project
  environment, e.g. `uv run --with pip-audit==2.10.0 pip-audit --strict`,
  or export the locked set (`uv export --frozen --format requirements-txt`
  → `pip-audit -r requirements.txt --strict`). Add a CI assertion that the
  audited inventory matches the locked runtime/dev dependency names and
  versions from `uv.lock` (not mere name presence, and not expecting
  `a7-py` itself to appear) so a future target regression is loud.

### SEC-3 (P2) — `oven-sh/setup-bun@v2` is a mutable tag, contradicting the documented pinning policy

Verified (source).

- `docs/SECURITY.md:49-50` states workflow actions are pinned to immutable
  commits. True for checkout/setup-python/upload-artifact/attest/
  configure-pages/deploy-pages/gh-release and both claude-action uses (all
  40-hex SHAs). **Not** true for `oven-sh/setup-bun@v2` at
  `release.yml:52`, `ci.yml:98`, `deploy-docs.yml:27`.
- Impact: a retagged or compromised `v2` would execute unreviewed code in
  three workflows; the release job holds `id-token: write` +
  `attestations: write` at that point (release.yml:25-29), the deploy job
  holds `pages: write` + `id-token: write`. Third-party action
  tag-repointing is a demonstrated supply-chain class. Reachability is
  low-frequency/high-impact and depends on an upstream compromise — hence
  P2, not P1 — but it also silently falsifies a security-policy statement.
- Fix: resolve the current upstream release to a commit SHA (same procedure
  used for the other actions, comment with the resolved date), and update
  `docs/SECURITY.md` if the pinning date changes. Dependabot
  (`github-actions` ecosystem, `.github/dependabot.yml:3-6`) will keep
  proposing SHA bumps afterwards.

### SEC-4 (P2) — Unpinned `pip install uv` in CI

Verified (source): `release.yml:40` and `ci.yml:35` run
`python -m pip install uv` (latest from PyPI, no hash). Every other tool is
pinned (Python 3.13, Bun 1.3.11, Zig URL+SHA256 at `ci.yml:18-20` /
`release.yml:18-20`). A malicious or broken latest-uv would run inside the
same job scopes as SEC-3 before any lockfile-verified install happens.
Fix: `python -m pip install uv==<pinned>` (or astral's SHA-pinned action)
and bump via dependabot-style review. Low likelihood, cheap to close.

### SEC-5 (P2) — Site build: two content-injection paths into published HTML (conditional defense-in-depth)

Verified as source-level sinks (line-by-line code reading; **no browser
execution was verified in this review**). Precondition for both: repository
write access (a merged PR or malicious docs edit); PR review is the only
content gate.

**Trust framing (material):** an actor with repository write access can
already modify `site/src/site.js` and every build script — the same trust
level. Until a lower-trust content boundary exists (e.g. accepting external
or generated docs contributions that do not go through full-repo review),
these sinks are **conditional defense-in-depth**, not an independent
privilege boundary: they lower the friction and review-surface of an
injection but do not grant capability beyond what repo write already gives.
They become security-critical the moment such a lower-trust content path is
introduced. The deployed origin is `github.io` (deploy-docs.yml).

1. Markdown link scheme is not validated — `site/scripts/build.ts:78-82`:
   `escapeHtml(href)` neutralizes quotes/tags but the `external` regex only
   decides `target`/`rel`; `[x](javascript:...)` in any
   `site/public/docs/*.md` would publish a clickable XSS vector. Note the
   build reads only inside `site/` (build.ts:5-7), so the injection surface
   is the site's own markdown corpus, not the repo-root docs.
2. Inline script interpolation — `build.ts:359`:
   `window.__A7_PAGE__=${JSON.stringify(data)}` without escaping `<`. A
   `title:`/`nav:` frontmatter value containing `</script><script>…`
   (frontmatter parsed at :60-72) breaks out of the script context on every
   generated page.
- Fix: allowlist link schemes (http, https, mailto, `#`, `/`, relative) and
  drop the link otherwise; emit
  `JSON.stringify(data).replace(/</g, '\\u003c')`. Verify by building the
  site with a canary docs file containing both payloads and asserting the
  output contains no live `javascript:` href and no `</script>` breakout.

### SEC-6 (P3) — Minor site escaping gaps

Verified (source): canonical href uses raw `${canonical}` (build.ts:364,
375) while sibling attributes are escaped (escaping is used at :368 and
:372-373); sitemap `<loc>` is unescaped XML (build.ts:693, 695). Both
derive from doc filenames (readdir at :213), so exploitation needs a
maliciously named committed file — unrealistic but inconsistent.
`escapeHtml` (build.ts:43-49) does not escape `'`; safe only because all
generated attributes are double-quoted — worth a defensive `&#39;`. Fix all
three mechanically.

### SEC-7 (P3) — Output path derivation rewrites every `.a7` occurrence in the input path

Verified by harmless reproduction in `/tmp/opencode/a7-audit`:

- Input `/tmp/opencode/a7-audit/prefix.a7dir/prog.a7` (compile mode,
  default `-o`) wrote `/tmp/opencode/a7-audit/prefix.zigdir/prog.zig`,
  silently creating the new `prefix.zigdir/` directory. Cause:
  `a7/compile.py:850` (`input_path.replace(".a7", extension)`) — Python
  `str.replace` replaces **all** occurrences, including inside directory
  names. The doc path fallback at `compile.py:457` has the same pattern;
  the CLI (`a7/cli.py:85-87`) correctly uses `with_suffix(".md")` — an
  internal inconsistency.
- Security impact is bounded: output goes somewhere unexpected, `makedirs`
  creates collateral directories, and a pre-existing file at the rewritten
  location is overwritten without warning. Because the output location is
  user-supplied and the compiler is a local tool, this is correctness-plus-
  surprise rather than privilege escalation — but "output written outside
  the expected tree" is exactly the class worth closing in a deliverer of
  build artifacts. Fix: derive output via `Path(input_path).with_suffix(ext)`
  or replace only the final component; add a test asserting a directory
  component containing `.a7` never redirects output.

### SEC-8 (P3) — Preview server soft-404s and unhandled `decodeURIComponent`

Verified (source): missing routes return the 404 body with **HTTP 200**
(serve.ts:28-29) — hides misconfiguration and breaks link checkers; a
malformed `%` sequence throws `URIError` inside fetch (serve.ts:23) → 500.
Fix: `try/catch` → 404 page, and respond 404 status for missing files.
(Coordinator observed the 200-on-missing behavior live, `root-review.md`
§R3.)

### SEC-9 (P3/Info) — Subprocess hygiene and tool discovery

Verified (source; no execution beyond the documented examples gate):

- Good: every subprocess in `scripts/` uses argv lists, never `shell=True`
  (`build_examples.py:62-68`, `verify_examples_common.py:57-64`,
  `verify_wheel_install.py:28-35`, `generate_release_manifest.py:37-43`);
  compiled-example execution is timeout-bounded
  (`build_examples.py:125-134`, `verify_examples_common.py:124-134`); the
  wheel smoke test installs from a **local wheel path** — the evidence is
  the argv (`pip install <wheel file>`, `verify_wheel_install.py:77`) in a
  throwaway venv; no offline flag (e.g. `--no-index`) is passed, so absence
  of any network access is not asserted here, only that the package under
  test is installed from the local file; the compiler package itself
  (`a7/`) contains **no** subprocess/`os.system`/`eval` calls at all
  (exhaustive grep) — code execution lives only in trusted scripts and CI.
- Gaps: `zig` is discovered via `PATH` (`build_examples.py:285-287`
  `shutil.which`, then bare `"zig"`), and `uv`/`uvx` similarly — standard
  developer-machine trust, but worth one line in SECURITY.md (today only the
  compiled-program caveat is stated). `zig ast-check`, `zig fmt --check`,
  and `zig build-exe` in `build_examples.py:96-113` and
  `verify_examples_common.py:99-121` have **no timeout** (only compile and
  run steps do), so a wedged toolchain hangs the gate — CI-level DoS, not
  attacker-reachable beyond "hostile checkout + wedged toolchain".
  **Proposal, not a v1 requirement:** passing a timeout to every `run_cmd`
  is a policy choice for the maintainers. (Distinct from this: the
  operating rule that external model CLIs in review sessions run without
  model/time/turn limits governs reviewer tooling, not these build scripts,
  and is unaffected by any subprocess-timeout policy.)
- Bandit runs with `--skip B404,B603` (`ci.yml:57`, `release.yml:71`) — the
  two skips are precisely "import subprocess"/"subprocess call" checks; the
  comment explains why (trusted verifier scripts). Acceptable, but the skip
  also silences future regressions in these scripts; consider narrowing to
  per-file skips.

### SEC-10 (Info) — Compiler-process DoS robustness (in scope: the compiler, not compiled programs)

(Cited as "SEC-10, lines 289-312" in docs/plan/research/memory/notes-h-audits-pdfs-current-memory.md.)

Verified: the tokenizer is a hand-rolled linear scanner; its only `import re`
(`a7/tokens.py:8`) is dead — no regex backtracking surface. Verified by
execution: an 80,000-deep parenthesized expression exits promptly with
code 8 and a single clean stderr line (`Unexpected error: maximum recursion
depth exceeded`, via the outer handler at `a7/compile.py:491-504`) — the
recursive-descent parser blows the Python stack but converts it to a clean
INTERNAL result, no traceback, no hang. Fuzz tests already treat
`RecursionError` as failure below depth 50 (`test/test_parser_fuzzing.py:281`).
Remaining hygiene items (no fix urgency): `MAX_STRING_LENGTH`
(`tokens.py:16`) is defined but never enforced, and GENERIC_TYPE/BUILTIN_ID
tokens have no length cap (`tokens.py:1003-1011`, `:811-817`). **Scope
caveat:** the single executed fixture proves only that one nesting class is
bounded and exits cleanly; the claim that all other crafted inputs are
similarly bounded rests on code reading (hypothesis), not execution, and
must not be read as a general resource-bound proof for arbitrary source.
Error-classification defects owned elsewhere
but crossing this boundary: imported-module parse errors surface as exit-8
INTERNAL instead of parse-class errors (`root-review.md` §R2,
`a7/module_resolver.py:154-168` catches only `SemanticError`), and a
malformed numeric token (superscript digit) reaches Python `int()` →
exit-8 ValueError (`root-review.md` §R4). Both are clean exits, not
crashes; fixing them belongs to the compiler-correctness reviews.

### SEC-11 (Info) — Import-path trust boundary: tested paths hold; cycle-handling claims withdrawn

Verified by harmless reproduction, **limited to exactly these tested
paths**: `import "../outside_target"` → semantic error, exit 6
(`a7/module_resolver.py:64-74` rejects absolute, `..`, backslash, NUL,
empty); a symlink **inside** the search path pointing to a file outside it
is refused (`_is_within_search_path` resolves candidates, `:76-78`,
`:108`) — the outside file's contents never reached the output. No claim is
made about import behavior beyond these cases.

One code-reading note: `add_search_path` (`:357-360`) appends to
`search_paths` without updating `resolved_search_paths`, so later-added
roots fail containment — fail-closed, a functional bug not a hole.

**Correction (this review's earlier draft asserted the opposite):** the
previous positive claim that "cache/dedup by module path string is correct;
the recursion guard and Kahn topological check bound import cycles" is
**withdrawn**. Independent language/contract reviews found that the loaded
module cache is consulted (`:124-126`) *before* the loading-stack cycle
guard (`:131-135`), so the guard does not bound all cycle shapes the way
this review assumed, and `topological_sort` (`:310-350`) is not invoked by
the compile pipeline, so it contributes no runtime bound. Cycle semantics
are owned by the language/contract reviews; nothing here should be cited as
evidence either way.

### SEC-12 (P3) — Secrets guardrails: decent, with known gaps

Verified: `scripts/check_no_secrets.py` covers private keys, gh/openai/
anthropic/aws/slack patterns, generic assignments, and sensitive filenames;
it currently passes. Gaps, consistent with its self-description in
`docs/SECURITY.md:52-53`: no git-history scanning (a removed secret stays in
history); `.lock`/`.gz`/`build`/`dist` contents are skipped wholesale; and
`.env` is **not in `.gitignore`** (only the scanner would catch it, at CI
time rather than commit time). Fix: add `.env*` to `.gitignore`; consider
`gitleaks`-style history scanning in CI if the repo gains external
contributors. No secrets were observed in `site/public/` (swept), in tracked
files, or in this audit's reads.

### Cleared checks (verified, no finding)

- **Workflow permissions/triggers**: least-privilege `permissions:` blocks
  everywhere; `pull_request` (never `pull_request_target`) so fork PRs get
  no secret access; `claude.yml` gates `@claude` invocations to
  OWNER/MEMBER/COLLABORATOR author association; `claude-code-review.yml`
  excludes forks (`head.repo.full_name == github.repository`) and
  dependabot, and its direct prompt explicitly treats PR content as
  untrusted (prompt-injection awareness).
- **Release integrity**: two-job structure — build job verifies SHA256SUMS
  and attests artifacts (`actions/attest`, release.yml:137-145) before the
  contents-write job re-verifies the manifest on **downloaded** artifacts
  (release.yml:185-186), closing the artifact-swap window; releases are
  drafts. `verify_release_manifest.py:48-67` rejects `..`, confines
  absolute paths to base/repo, and hash-checks every entry;
  `verify_archive_contents.py:27-56` rejects traversal/absolute/link-escape/
  device members and documents the `lstrip("./")` laundering trap.
- **Toolchain download**: Zig pinned to URL + SHA256 with `sha256sum -c`
  before use (ci.yml:38-44, release.yml:42-49).
- **Docs dependencies**: `bun install --frozen-lockfile` + `bun audit
  --audit-level=moderate` run in the site directory (ci.yml:104-108) — this
  one audits the right tree; dependabot covers github-actions, pip, and bun
  (`.github/dependabot.yml`).
- **Client-side site** (code reading only — no browser execution in this
  review): search rendering escapes before `innerHTML` and assigns `href`
  as a property; `?from=` redirect is allowlisted; 404 redirect encodes its
  target; external markdown links get `rel="noopener"`; no
  `eval`/`document.write`/`postMessage` sinks (`site/src/site.js` —
  sub-agent sweep, spot-checked).
- **Wheel contents**: `pyproject.toml` package discovery includes only
  `a7*` — no tests, scripts, or site files ship.

## Coverage

Fully read this review: `AGENTS.md`, `docs/SECURITY.md`, `pyproject.toml`,
`main.py`, `run_all_tests.sh`, `a7/cli.py`, `a7/compile.py`,
`a7/module_resolver.py`, `a7/tokens.py`, `a7/backends/base.py`, all five
`.github/workflows/*.yml`, `.github/dependabot.yml`, `.gitignore`,
`scripts/build_examples.py`, `scripts/verify_examples_common.py`,
`scripts/verify_examples_e2e.py`, `scripts/check_no_secrets.py`,
`scripts/generate_release_manifest.py`, `scripts/verify_release_manifest.py`,
`scripts/verify_archive_contents.py`, `scripts/verify_wheel_install.py`,
`site/scripts/serve.ts`, and the cited sections of
`site/scripts/build.ts` (escaping, frontmatter, link rendering, page/sitemap
emission).

Sub-agent coverage (site review completed; findings re-verified here):
`site/scripts/{serve,build,lint}.ts`, `site/src/site.js`,
`site/package.json`, `site/bun.lock`, `site/public/404.html`, `robots.txt`,
`sitemap.xml`, sweep of `site/public/docs/*.md` + `llms*.txt` for
secret-like content.

Skimmed/targeted (limits): `a7/backends/zig.py` (escaping paths at
:1470-1516, :2282-2296 only), `a7/parser.py` (expression/precedence paths,
:1360-1520), `a7/passes/*` and `a7/ast_preprocessor.py` (traversal-style
greps plus `test/test_iterative_traversal.py` design, not full reads),
`site/src/tailwind.css`, `site/public/a7-system-map.svg` (not opened),
`docs/RELEASE.md` (not read; SECURITY.md's release section used instead).

## Limits of this review

- The preview traversal was not re-probed at runtime (server down;
  `/etc` probe approval-denied and not retried). Containment failure rests
  on the coordinator's harmless `package.json` evidence plus source proof of
  the missing check — sufficient for the finding, but "arbitrary file read"
  beyond the one observed escape is inference, not enumeration.
- No dynamic testing of the deployed GitHub Pages site, no browser-based
  XSS execution, no `bun audit`/`pip-audit` re-runs (coordinator gates
  own those), and no git-history secret scan (tooling absent from repo).
- `a7/passes/*` (5,000 lines) and `a7/backends/zig.py` (2,400 lines) were
  reviewed only along security-relevant axes (injection into generated Zig,
  traversal recursion); a full line-by-line pass was out of scope and is
  partly covered by the memory-safety and compiler-correctness reviews.
- Sub-agent failures and provider rate limits are recorded above; no
  blocked operation was retried through another provider.

## Recommended fix order

1. SEC-2 pip-audit target (gate integrity; one-line change + inventory
   assertion).
2. SEC-1 preview traversal/bind (small patch; unblocks safe local previews).
3. SEC-3/SEC-4 action and uv pinning (mechanical, restores the documented
   policy).
4. SEC-5 site build escaping (allowlist + `\u003c` — content-injection
   hardening per its conditional framing), then SEC-6/SEC-7/SEC-8
   hardening.
5. SEC-9 timeout policy decision, SEC-12 `.gitignore` entry as follow-ups.

All fixes require verification per finding before the next tagged release;
none were applied by this advisory review.

## Correction note — 2026-09-14 (reconciliation pass)

Reconciled against coordinator evidence and the independent language and
contract reviews. No new probes were run. Corrections applied in place:

| Finding | Correction |
| --- | --- |
| SEC-11 | Positive cycle-handling claim withdrawn (cache before guard, unused `topological_sort`); evidence limited to the two tested import paths |
| SEC-2 | No claim about the current advisory status of project dependencies (corrected audit not run). Audited inventory counted on its own evidence. Comparison is now version-qualified against `uv.lock`, not name-only overlap; local `a7-py` would not appear in a requirements-export audit |
| SEC-5 | Relabeled conditional defense-in-depth: repo write can already change site JS; no browser execution verified |
| SEC-1 | Remote-reachability claim limited to the verified non-loopback bind (LAN reachability unproven). Fix replaced by stated requirements instead of untested pseudocode |
| SEC-9 | Wheel-install network claim limited to the observed local-path argv. Subprocess timeouts labeled a policy proposal. The no-limits rule for external model CLIs is a separate reviewer-tooling rule and is unaffected |
| SEC-10 | Bounded-cost scope caveat added: one executed fixture; the rest is code-reading hypothesis |
| Cleared checks | Client-side site checks qualified as code reading only |
