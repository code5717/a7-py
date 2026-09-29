# A7 Website Audit — GLM-5.3 Advisory Review

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) supersede parts of it.

- Date: 2026-09-14
- Reviewer: external website reviewer (Z.AI GLM-5.3), invoked by the controlling Codex session
- Scope: `site/` source, generated `site/dist`, public markdown corpus, and their claims
  against `README.md`, `docs/RELEASE.md`, `docs/STATUS.md`, `docs/SPEC.md`, and actual CLI
  behavior
- Role: advisory only. No implementation files were edited. Nothing was committed or
  deployed. No global machine configuration changed. The working tree was clean before and
  after (verified with `git status --porcelain`; the site build regenerates `llms.txt`,
  `llms-full.txt` and `sitemap.xml` byte-identically).
- Design stance: the Field Manual direction (graphite shell, paper reading surface, oxide
  accent, monospace navigation) works and should stay. The findings cover factual accuracy,
  interaction quality and coverage, not a redesign.

Companion report: [website-codex-review.md](website-codex-review.md). This review was
produced independently. Overlaps are confirmed with independent evidence; new findings are
marked. Evidence labels:

- **Rendered**: verified in `site/dist` after `bun run build`, or by executing the compiler CLI
- **Source-only**: verified in source, not exercised in a browser (no browser was used; see
  Coverage Limits)

## Verification performed

Commands run (environment details in Coverage Limits):

- `bun install`, `bun run lint` (`site-lint: ok`), `bun run build` (9 docs built; the only
  output noise is a Node `DEP0205` deprecation warning from the Tailwind CLI, cosmetic)
- `a7 --help`, hello-world compile, `--mode pipeline` on the language tour, and three
  deliberate failures to confirm documented exit codes
- Scripted link/anchor check over all 10 built HTML pages: **277 local hrefs, 0 broken,
  0 dangling fragments**
- Scripted contrast-ratio computation for the token pairs actually used by
  `site/src/tailwind.css`
- Preview server (`bun run scripts/serve.ts`) with curl checks of every route class
- Diff-by-rebuild: rebuilding regenerated `llms.txt`, `llms-full.txt`, `sitemap.xml` with no
  git diff — the committed generated files are fresh

### What passed (keep as-is)

- CLI claims: mode names, `compile` default, `--format {human,json}`, `-o`, `--doc-out`,
  `--backend zig`, `-v` all match `a7 --help` exactly
- Exit codes verified empirically: no-args → 2, missing file → 3, syntax error → 5
  (site table `compiler.md` lists 0/2/3/4/5/6/7/8, consistent with README.md:65)
- Real compile behavior: `uv run a7 examples/001_hello.a7 --mode compile` → exit 0, writes
  `examples/001_hello.zig`, single line of output (see Finding 3 for the mismatch this
  creates)
- Language tour: `--mode pipeline` on `examples/037_language_tour.a7` exits 0
- Stdlib page matches implementation exactly: `std/io` = `print`/`println`/`eprintln`
  (`a7/stdlib/io.py`), `std/math` = the 11 listed functions (`a7/stdlib/math.py`), typed
  `sqrt_f32`/`sqrt_f64` builtins exist
- Example facts: 43 files in `examples/`; `001_hello.a7`, `004_func.a7`,
  `037_language_tour.a7` all exist
- Agent entry points: `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, `/a7-py/docs/*.md` all serve
  200 with `text/plain` under the preview server; `llms.txt` index and `llms-full.txt` corpus
  structure are sound; the stable-URL contract in `index.md` matches the dist layout
- SEO basics present: canonical per page, `sitemap.xml` covers all 9 pages, `robots.txt`
  points at it, `lang="en"`, per-page meta descriptions from frontmatter summaries
- Accessibility basics present: custom `:focus-visible` style, `prefers-reduced-motion`
  honored in both CSS and JS, favicon has `role="img"` + `aria-label`, decorative elements
  are `aria-hidden`, dialog/search markup has roles and labels
- The security caveat ("not a sandbox") is consistently present on Project, and in AGENTS.md
  and README.md

## Prioritized findings

Priorities: P1 = a documented workflow fails as written; P2 = accuracy, accessibility, or
usability defect; P3 = polish and hardening.

### P1 — Published command block breaks if pasted

`site/public/docs/release.md:16-22` — the "Local gates" block is:

```bash
uv run python scripts/verify_examples_e2e.py
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
cd site && bun install && bun run build
./run_all_tests.sh
```

Line 20 changes cwd into `site/`; line 21 then runs `./run_all_tests.sh`, which does not
exist there. Anyone pasting the block from the repository root (the obvious reading) fails at
the last step. **Source-confirmed** (also found independently by the Codex review).

- Repro: `cd "$(git revolve --show-toplevel)"` equivalent — from the repo root, paste the
  block; the final command fails with "no such file or directory"
- Fix: use the subshell form from docs/RELEASE.md:59 — `(cd site && bun install && bun run build)`
- Acceptance: pasting each fenced block on the page from the repo root completes without a
  cwd-dependent failure; a docs-lint rule (or review checklist item) rejects `cd X && …`
  lines inside multi-command blocks unless wrapped in a subshell

### P2 — Findings that must be fixed

| # | Finding | Evidence | Repro / fix | Acceptance criteria |
|---|---|---|---|---|
| 2 | Version branding misstates the A7 version. Topbar pill `v0.16` (build.ts:385), poster meta and footer ticker `v0.16.0` (build.ts:461, 641), `site/package.json` `0.16.0` — while `pyproject.toml` says `0.3.0`. The number is the Zig toolchain version presented where readers parse it as the project version. | **Rendered** (dist HTML) + source | Show both facts distinctly: `v0.3.0 · zig 0.16` or similar; ideally derive the A7 version at build time from `pyproject.toml` (single source of truth) | No element on any page can be read as "A7 v0.16"; A7 version shown matches `pyproject.toml`; changing the package version updates the site without manual edits |
| 3 | Homepage terminal shows invented output. The compile tab renders six `[compile] <stage> ok` lines and `-> examples/001_hello.zig`; the real CLI prints one line: `Compiled examples/001_hello.a7 -> examples/001_hello.zig (579 bytes, 1 ms)`. The release tab shows a static `release gate: green`. | **Rendered** (build.ts:576-592) vs CLI executed | Replace with a real transcript captured from an actual run, or caption the panel as illustrative ("example session, output abbreviated"). Same for the release tab | Every terminal-looking output on the homepage either matches real tool output or is explicitly labeled as illustrative; a newcomer pasting the first command gets output consistent with the panel |
| 4 | Search cannot find body text. `searchIndex()` (build.ts:706-728) indexes only page title, group, summary, and h2/h3 headings; `rankSearch()` (site.js:198-218) matches the same fields. Verified: `usize`, `println`, `recursion`, `--format`, `del`, `match` all return 0 results (51 index entries total). | **Rendered** (dist/assets/search.json queried directly) | Index section body text at build time — e.g. attach each heading's following content (or a keyword list plus fenced identifiers) to the search entry, capped in size; keep search.json lean | The six queries above return the correct page(s)/section anchors; `search.json` stays under ~100 KB; first keystroke still renders without delay (preload path in site.js:296-300 keeps working) |
| 5 | Ordered lists collapse into run-on paragraphs. The markdown renderer handles only `[-*]` bullets (build.ts:173); `compiler.md:16-24` uses `1.`–`9.` and renders as `<p>1. Tokenize source 2. Parse into AST …</p>` (verified in dist/compiler/index.html; 0 `<ol>` elements site-wide). | **Rendered** | Extend `renderMarkdown` with an ordered-list branch (`/^\d+\.\s+/`) emitting `<ol><li>`, or convert compiler.md to bullets | The pipeline renders as 9 list items in `<ol>`; a lint check fails if any public doc contains an ordered list that renders without `<ol>` |
| 6 | Status page drifts from the authoritative roadmap. Site `status.md:22-27` lists two priorities that do not exist in `docs/STATUS.md:16-26` ("Clearer status reporting for parsed-only language features", "stdlib additions starting with deterministic random helpers") and omits four canonical ones (script-derived facts, numeric design brief, safety-proofing stage split, `a7 check/build/run/doctor/--version` workflow commands). Deferred lists also diverge: site adds "Full language server" and "Runtime sandboxing" (status.md:40-46), omits "Tensor, AI, GPU, performance annotations" (docs/STATUS.md:41-44). Additionally `status.md:31` describes file-backed imports wholesale as future work while README.md:164 and docs/STATUS.md:30 say simple alias imports already lower into the combined Zig file. | Source comparison (new detail vs Codex finding) | Rewrite the site page as a faithful compression of `docs/STATUS.md`; where compression drops items, say "see docs/STATUS.md for the full list" instead of substituting different items | Every site status bullet maps 1:1 to a `docs/STATUS.md` statement; no site-only priorities or deferred items; import support described as partial-with-examples, matching README |
| 7 | Compiler page overstates compiler internals. `compiler.md:57-58`: "Compiler internals also avoid recursive AST traversal" contradicts README.md:140, which states the parser is recursive descent and some backend emission paths remain visitor-recursive. | Source comparison | Reword to match README: internals are "largely iterative" / "iterative where feasible", keeping the sharp distinction from the A7-source-recursion ban | No sentence on the site claims more internal iteration than README.md does |
| 8 | Mobile ≤640 px removes the only search and shortcuts affordances. `tailwind.css:1088` hides `.shortcut-trigger`, and no other search entry point exists in the topbar. Copy buttons are hover-revealed only (`tailwind.css:834` `pre:hover .copy`), so on touch devices they are effectively undiscoverable. | Source-only (CSS inspection; no device rendering) | Keep a visible search control at small widths (icon-only is fine); add `@media (hover: none) { .copy { opacity: 1; transform: none; } }` | At 375 px, search opens via a visible control; copy buttons render persistently on coarse pointers; both verifiable in a browser or with responsive screenshots |
| 9 | Modal and tab accessibility incomplete. Modals have no focus trap or background `inert`; Tab moves to content behind the overlay (`site.js:116-169`). Terminal tabs declare `role="tab"` (build.ts:569-573) but panels lack `role="tabpanel"`/`aria-controls`, and there is no arrow-key tab navigation (site.js:413-427). Search selection lacks `aria-activedescendant` on the input. | Source-only (needs browser qualification) | Implement focus containment (trap or `inert` on the shell), restore focus on close (partially present via `lastFocus`), complete the ARIA tabs pattern, set `aria-activedescendant` | Keyboard-only walkthrough: Tab/Shift+Tab stay inside an open modal; Escape returns focus to the trigger; arrow keys move terminal tabs; screen reader announces the active search option |
| 10 | WCAG AA contrast failures on real text. Computed ratios from the shipped palette: spec-spine `oxide-600` on `#0f0e0c` = **3.23:1** (tailwind.css:437); route-group h3 `muted-500` on `paper-200` = **2.81:1** (tailwind.css:489); doc-pager small labels `muted-500` on `paper-100` = **3.12:1** (tailwind.css:877-880, verified in compiled CSS); terminal `t-ok` `calibration-600` on `graphite-950` = **4.08:1** (tailwind.css:666). All are below 4.5:1 at 9–13 px sizes. (New finding.) | **Rendered** (compiled `dist/assets/site.css`) + computed | Darken/increase lightness of these token uses for small text only — e.g. use `muted-400`-class values or `ink-800` on paper surfaces, `oxide-300` for small oxide text on graphite — without touching the palette itself | Automated contrast check over compiled CSS text/background pairs passes 4.5:1 (or 3:1 only where text is ≥24 px / 18.66 px bold); Field Manual look unchanged |
| 11 | Release page understates the release gate. `release.md:24-26` calls `run_all_tests.sh` "the single local release gate" but docs/RELEASE.md:63-65 additionally requires pinned `pip-audit`, `bandit`, and `bun audit`. | Source comparison | Either list the three audit commands in the block or state explicitly that dependency/security audits are separate and link to the canonical checklist | No reader could tag a release believing `run_all_tests.sh` alone is sufficient |
| 12 | Language reference is thinner than the working language. README "What Works" (README.md:150-168) includes generics (`$T` type parameters, constraints, type sets), `match`, `defer`, casts, fixed-array `+`, if-expressions, inline-struct multiple returns — none of which appear in `language.md` beyond a one-line bullet (language.md:64-76). The page never shows the `$T` syntax a reader needs to read `examples/`. | Source comparison (new finding) | Add short, verified snippets for generics declaration + call, `match`, `defer`, and a note on casts/multiple returns, keeping the "operational reference, SPEC is canonical" framing | Every README "What Works" bullet has either a syntax example or an explicit pointer on the Language page; snippets compile (gate: examples e2e or a tour extension) |
| 13 | Compiler page omits supported CLI options. `-o/--output`, `--doc-out`, `--backend`, `-v/--verbose` exist (`a7 --help`) and are documented in README.md:44-54, but `compiler.md:29-40` lists only modes and `--format`. | **Rendered** (help output vs page) | Add an options table row group; consider showing `--doc-out auto` since it feeds the doc workflow | Every flag in `a7 --help` has a row on the Compiler page |
| 14 | No social/ sharing metadata and thin home title. `<head>` (build.ts:367-381) has title/description/canonical but no `og:*`/`twitter:*`; home `<title>` is just "A7". Raw `.md` twins are indexable duplicates of the HTML pages with no `noindex` signal. | **Rendered** (dist HTML grep: 0 og/twitter tags) | Add og:title/description/url (+ an og:image derived from the system map; PNG preferred); extend home title ("A7 — AOT compiler to Zig 0.16"); decide duplicate policy (e.g. `X-Robots-Tag` for `/docs/*.md` is not settable via static GH Pages — alternatively accept duplicates or link canonicals from the md) | Sharing any page renders a sensible card; home title is descriptive; a stated duplicate-content decision is recorded |

Note (2026-09-16), finding 6: the canonical `docs/STATUS.md` items it cites ("numeric design brief" and deferred "Tensor, AI, GPU, performance annotations") are superseded by ledger L3, L4 and L1, L7. The finding's drift judgment stands as recorded.

### P3 — Polish and hardening

| # | Finding | Evidence | Fix |
|---|---|---|---|
| 15 | Site lint does not require `project.md`. `REQUIRED` in site/scripts/lint.ts:6 lists 8 files; `project.md` can be deleted without lint failure. | Source | Add `project.md` to `REQUIRED`; better, derive REQUIRED from `DOC_ORDER` in build.ts so the two lists cannot drift |
| 16 | Preview server diverges from Pages behavior: unknown paths serve `404.html` with HTTP 200 (serve.ts:28), and `search.json` serves as `application/octet-stream` (serve.ts:15 default branch). | **Rendered** (curl checks) | Send 404 status for the fallback; add a `.json` → `application/json` branch |
| 17 | Homepage code caption says `EXAMPLES / 004_func.a7` but the listing is adapted (adds `factorial`, omits `greet`/`divide`). build.ts:532-554 vs examples/004_func.a7. | Source comparison (new) | Caption as "adapted from examples/004_func.a7" or use the true file content |
| 18 | Start page lists Bun as a flat requirement (start.md:16) though it is only needed to build the docs site; no install links for `uv`/Zig (README.md:16 has them). | Source | Split "to use the compiler" vs "to build this site"; link the uv and Zig install pages |
| 19 | No skip-to-content link; on ≤640 px the TOC is hidden with no in-page navigation substitute (tailwind.css:1092). | Source-only | Add a visually-hidden-until-focused skip link; consider a collapsible "On this page" details element on mobile |
| 20 | Dead CSS: `.route-kind` rules (tailwind.css:521-528) never apply — `routeBoardHtml` (build.ts:269-286) emits no `route-kind`/`data-kind` markup. | Source (new) | Either emit the kind chips (nice scannability win in the route board, using the existing Getting-started/Reference/Project/Agents groups) or delete the rules |
| 21 | Latent TOC mislabel: when a doc has no h2/h3, the "On this page" rail silently shows `related` links instead (build.ts:444-447). No current doc triggers it. | Source (new) | Render "Related" with its own label when falling back |
| 22 | For agents consuming raw markdown, in-corpus links point at HTML routes (e.g. `[Language](/a7-py/language/)` inside docs/*.md). They resolve over HTTP, but an agent following them gets HTML, not markdown. | Source (new) | Prefer sibling `.md` links inside the corpus (`/a7-py/docs/language.md`), or add both; keep HTML links on rendered pages only |
| 23 | Toolchain skew note: deploy-docs.yml pins Bun 1.3.11 while local dev commonly runs 1.4.x (lockfileVersion 1, currently compatible). | Source | Low risk; upgrade the pin deliberately when convenient |
| 24 | `run_all_tests.sh` does not build the site (grep: no `site`/`bun` steps) — deployment relies solely on the Pages workflow. That matches docs, but means site regressions surface only at deploy time. | Source | Consider folding `bun run lint && bun run build` (with Bun setup) into the local gate or a CI job so docs drift is caught pre-deploy |

## Information architecture and journey (summary judgment)

The nine-page, task-grouped IA (Getting started → Reference → Project → Agents) with a
linear pager and `g`-chord navigation is coherent and appropriate for the project size. The
getting-started journey is honest about prerequisites and correctly sequences install →
first compile → tour → modes → gates. The two weakest links are Finding 12 (language page
under-represents the working language, which is the page new users will lean on most) and
Finding 4 (search cannot answer even basic symbol queries, which undermines the otherwise
good keyboard-first navigation). The Field Manual presentation actively helps credibility
here; nothing in this report requires changing it.

## Claim-accuracy ledger

| Site claim | Status |
|---|---|
| Pipeline stages (index, compiler pages) | Matches README/docs/RELEASE (note ordered-list rendering bug, Finding 5) |
| CLI modes/default/`--format json` | Verified against `a7 --help` |
| Exit codes 0–8 | 2/3/5 verified empirically; rest consistent with README |
| Compile output transcript (homepage) | **Wrong** (Finding 3) |
| `v0.16` version branding | **Misleading** (Finding 2) |
| 43 examples, tour/004/001 files exist | Verified |
| Stdlib module contents | Verified against `a7/stdlib/` |
| Status priorities/deferred | **Drifted** (Finding 6) |
| "Compiler internals avoid recursion" | **Overstated** (Finding 7) |
| "run_all_tests.sh is the single gate" | **Understates** audit steps (Finding 11) |
| File-backed imports as future work | **Overgeneralized** (Finding 6) |
| Zig 0.16 target, single-file output, recursion ban, usize guidance, `new [N]T` rejection, no address-of/deref syntax | All consistent with README/AGENTS/SPEC |
| Stable URL contract (index.md) | Matches dist layout |
| "Multi-file input resolved, single Zig output" | Consistent with README.md:164 |

## Proposed completion roadmap (for agreement)

1. **Fix published facts (P1 + findings 2, 3, 6, 7, 11, 17).** All are content-only edits
   plus, ideally, deriving the version from `pyproject.toml` at build time. Accept when every
   row of the claim ledger reads Verified/consistent and terminal transcripts match real
   output.
2. **Repair interaction (findings 4, 5, 8, 9, 10, 16).** Ordered-list rendering, body-text
   search indexing, mobile search access, touch copy buttons, focus trap + tab pattern,
   contrast token fixes. Accept when the six search queries hit, an `<ol>` renders on the
   Compiler page, compiled-CSS contrast passes 4.5:1 for small text, and a keyboard-only
   walkthrough keeps focus inside modals (browser qualification required).
3. **Complete reference coverage and SEO (findings 12, 13, 14, 18, 22).** Language page
   gains generics/match/defer/casts snippets (each snippet compiled or added to the tour),
   CLI options table, install links, og/twitter metadata, descriptive home title, md-link
   policy for agents. Accept when `a7 --help` is fully covered and every README
   "What Works" bullet is represented or pointed to.
4. **Harden and prevent regressions (findings 15, 19, 20, 21, 23, 24).** Extend site lint:
   link/fragment check over dist, ordered-list rendering check, search-index smoke query,
   version-freshness check against `pyproject.toml`, REQUIRED derived from DOC_ORDER.
   Accept when `bun run check` fails on an intentionally introduced instance of each defect
   class, and desktop + mobile screenshots confirm the Field Manual typography, palette,
   layout, and compiler map are unchanged (screenshots must be captured and inspected —
   this review did not perform visual verification).

## Coverage limits and capability notes

- **No browser was used.** Playwright MCP/CLI was not invoked (not permitted without user
  approval) and no other browser capability was available in this session. All DOM/CSS/JS
  findings above are source-level or built-artifact-level and are labeled **Source-only**
  where behavior could not be exercised. No visual/screenshot verification is claimed.
- **Web search:** one web-search call was made (llms.txt convention) and the provider
  returned an empty result set; no other provider limits or authentication failures were
  encountered. No external claims in this report depend on that search.
- **Zig absent from PATH**, so generated Zig could not be built or executed locally; no
  e2e binary runs, no `zig run` confirmation, and `run_all_tests.sh` was not executed.
- **uv access:** the `uv` mise shim had no default version set; the compiler was exercised
  via the nested install binary
  (`~/.local/share/mise/installs/uv/0.12.6/uv-x86_64-unknown-linux-musl/uv`). No global
  configuration was changed.
- The local Bun is 1.4.2 while CI pins 1.3.11 (see Finding 23); the build and lint succeeded
  with the committed lockfile.
