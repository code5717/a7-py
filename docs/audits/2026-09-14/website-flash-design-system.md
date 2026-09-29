# Website Design-System Review — Field Manual Presentation & Consistency

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- **Reviewer:** GLM-5.3-Flash, website design-system specialist, external and advisory.
- **Date:** 2026-09-14
- **Scope:** overall presentation and consistency: Field Manual palette, hierarchy, component patterns, page-to-page consistency, homepage identity and compiler map, content priority, controls versus decoration, and evidence-based product messaging. The graphite/paper/oxide/monospace direction is treated as fixed.
- **Out of scope:** typography metrics and responsive behavior (separate reviews), contrast numbers and ARIA (accessibility review), SEO, interactions and information architecture.
- **Method:** static source inspection, inspection of the existing `site/dist`, and read-only `curl` of the running local preview (`http://localhost:4173/a7-py/`, HTTP 200).

## Execution limitations

- An earlier attempt was interrupted by a provider request-rate failure; this run resumed the same reviewer identity and completed. No other provider, auth or capability limits were hit.
- In-app browser unavailable and local browser connection failed (per coordinator). No browser capture or visual verification was attempted, and no rendered-pixel verification is claimed.
- The shared `site/dist` was not rebuilt. Drift between `dist` and `public` was measured with `diff` only. No implementation changes were made.
- Sibling website review reports in `docs/audits/2026-09-14/` were not read; findings are independent.

## Inspected files and checks

Read in full: `AGENTS.md` (repo instructions), `site/README.md`, `site/package.json`, `site/src/tailwind.css` (1140 lines), `site/src/site.js` (442 lines), `site/scripts/build.ts` (754 lines), `site/scripts/lint.ts`, `site/scripts/serve.ts`, `site/public/404.html`, `site/public/a7-system-map.svg`, `site/public/docs/index.md`, `site/public/docs/compiler.md` (lines 1–70).

Checked: frontmatter (title/nav/group/order/summary) of all nine `site/public/docs/*.md`; `grep` for usage of `--feat-display`, `--feat-num`, `.hero`, `.route-kind`/`data-kind`, `data-key`; raw hex literals in `tailwind.css` outside `@theme` (≈33 occurrences, lines 238–871); `examples/004_func.a7` vs the homepage sample; `examples/*.a7` count (43); `a7/cli.py` `--mode` flag (exists, lines 24–27); version sources (`pyproject.toml:3` = 0.3.0, `docs/CHANGELOG.md` latest release = 0.3.0, no git tags); preview HTML via `curl` (index and `/start/`); `diff` of `dist/llms.txt`, `dist/llms-full.txt`, `dist/docs/index.md` against `public/` counterparts; `git status` for `site/` (worktree has modified `site/public/docs/index.md` and `site/public/llms-full.txt` from other workers — preserved, not touched).

## Findings

### P1 — Compiler-pipeline vocabulary differs across the homepage's three identity surfaces

- Evidence:
  - Poster chips: `site/scripts/build.ts:466-476` — `.a7 → parse → check → zig → binary`.
  - System map SVG: `site/public/a7-system-map.svg:26-27` (`SOURCE -> SAFETY PASSES -> SINGLE ZIG FILE -> NATIVE BINARY`), `:61-63` (stage labels `parse`, `validate`, `emit`).
  - Terminal tab: `site/scripts/build.ts:576-584` — `tokenize / parse / name-resolve / type-check / safety / emit zig`.
  - Overview doc: `site/public/docs/index.md:18` — `.a7 → tokenize → parse → semantic checks → emit Zig → native binary`.
  - Canonical reference: `site/public/docs/compiler.md:14-24` (nine stages, including "Validate language invariants"; the word "validate" appears nowhere else in site UI).
- Consequence: the pipeline is the product identity (site/README.md rule: "The first viewport must make 'A7' unmistakable and show the compiler map"). Four different namings for the same pipeline, on one page, undercut the field-manual precision thesis and can mislead readers about what the compiler actually does.
- Suggested correction: adopt the `compiler.md` vocabulary as the single source. Poster chips and SVG labels should be abbreviations of it (e.g. `tokenize · parse · check · emit zig · binary`), with the terminal tab (which matches real CLI output) left as-is as the literal form. Regenerate the SVG text nodes from the same string set.
- Acceptance criteria: one documented stage-name set exists; poster chips, SVG labels, and overview pipeline line use only names from it; a manual diff of those surfaces shows no synonym pairs (no `check` + `validate`, no `zig file` vs `emit zig` mix).

### P1 — Version stamps conflate the A7 version with the Zig toolchain version

- Evidence: brand pill "v0.16" (`site/scripts/build.ts:385`), poster-meta "v0.16.0" (`build.ts:461`), footer ticker "v0.16.0" (`build.ts:641`), `site/package.json:4` = 0.16.0. The project version is 0.3.0 (`pyproject.toml:3`, `docs/CHANGELOG.md` latest release). Zig 0.16.0 is the toolchain requirement (`README.md:16`).
- Consequence: "A7 v0.16" overstates the product version by five minor versions. This is exactly the evidence-based-messaging failure the Field Manual direction is supposed to preclude, and it sits in the first viewport.
- Suggested correction: stamp the A7 version from one source (pyproject version or a generated release-facts file; the repo already keeps example counts in `scripts/project_status.py` per `docs/CHANGELOG.md`). Where the toolchain matters, label it explicitly, e.g. "zig 0.16.0" (the poster plate at `build.ts:465` already does this correctly).
- Acceptance criteria: rendered version strings match `uv run a7 --version` / pyproject; the bare string "v0.16*" no longer appears as an A7 version; Zig appears only with a toolchain label.

### P2 — Route-board copy says "Nine pages"; the board renders eight routes

- Evidence: `site/scripts/build.ts:509` ("Nine pages grouped by task") vs `routeBoardHtml` excluding `index` (`build.ts:272`); served homepage shows exactly 8 `route-row` elements (curl). Related: poster-meta "SHEET 01 / 09" (`build.ts:459`) counts the overview as a sheet the board never shows.
- Consequence: a countable claim that is falsified by the element directly beneath it.
- Suggested correction: change the copy to "Eight routes grouped by task…" (or include an Overview row and keep "nine").
- Acceptance criteria: the number stated in the route-board intro equals the number of rendered `route-row` links.

### P2 — Designed route-kind component exists in CSS but is never emitted

- Evidence: `site/src/tailwind.css:521-528` define `.route-kind` plus a four-way color taxonomy keyed on `data-kind="guide|reference|status|manual"`; `routeBoardHtml` (`site/scripts/build.ts:269-286`) emits no `data-kind` and no `.route-kind` element; doc frontmatter has no kind field.
- Consequence: an entire designed component pattern is dead. The homepage's primary navigation loses the intended task-type layer, and future editors may assume the coding is active.
- Suggested correction: either emit the chips — derivable from the existing groups (Getting started→guide, Reference→reference, Project→status, Agents→manual) — or delete the CSS block. Emitting is the higher-value option: it uses the already-designed oxide/ink/calibration/muted encoding and adds scannable type information to the board.
- Acceptance criteria: if kept, every `route-row` carries a kind chip whose color maps deterministically to its group; if dropped, no `.route-kind`/`data-kind` CSS remains in `tailwind.css`.

### P2 — System-map SVG palette drifts from the @theme tokens

- Evidence: SVG hexes `#d84a2b` (oxide accents, `a7-system-map.svg:39,57-59`), `#f4ead7`/`#cbbd9f` (paper, `:4-5,44`), `#11100e`/`#161410`/`#201d18`/`#191713` (shells, `:16-19,30`), `#91856e`/`#8a7d65`/`#574f42`/`#6f6553` (rules/mutes) versus tokens `--color-oxide-600: #b23a1f`, `--color-oxide-300: #e07b62`, `--color-paper-50: #f4eee0`, `--color-graphite-900: #11110e`, `--color-muted-500: #8b806b` (`site/src/tailwind.css:4-21`). The map renders inside the poster immediately adjacent to CSS-oxide registration marks (`build.ts:454-457`).
- Consequence: two visibly different "oxide" reds share the first viewport. The map is the one asset that must read as the same ink system as the page around it.
- Suggested correction: re-point all SVG fills/strokes to the @theme hex values (oxide-600 for the flow arrows/dots, paper-50/paper-300 for ink, graphite-850/900/950 for shells, muted-500/rule-500 for grid lines).
- Acceptance criteria: every hex literal in `a7-system-map.svg` equals the value of a `--color-*` token in `src/tailwind.css`.

### P2 — ~30 out-of-token hex values scattered through the stylesheet

- Evidence (representative, all in `site/src/tailwind.css`): paper rule `#cabd9e` used ~10× (lines 461, 469, 473, 489, 493, 522, 529, 549, 566, 747, 803, 851, 860, 867, 871); paper-body ink `#544b3e` ×4 (485, 529, 559, 734); code-shell `#15130f` ×3 (574, 594, 807); poster shell `#14120f` (244, 295) and `#0f0e0c` (373, 428, 437, 600); syntax amber `#e7c478` (594-595); ink-rule `#c9bfa3` (238), `#cdbc99` (803); terminal traffic lights `#c25340`/`#c8a14a`/`#4d9577` (623-625); plus one-offs at 829, 851, 860, 867, 871. site/README.md rule: the palette is the token set; raw palette utilities should not define the look.
- Consequence: the token system is bypassed on precisely the surfaces (paper rules, code shells) that repeat most; a palette adjustment means hunting raw hexes, and new one-off colors are likely.
- Suggested correction: promote the recurring values to @theme tokens that keep the field-manual naming, e.g. `--color-rule-paper: #cabd9e`, `--color-ink-600: #544b3e`, `--color-shell-880: #14120f`, `--color-shell-920: #0f0e0c`, `--color-code-shell: #15130f`, `--color-amber-400: #e7c478`; replace usages. Terminal traffic lights may stay as a documented pictorial exception.
- Acceptance criteria: `grep -n '#[0-9a-f]\{6\}' site/src/tailwind.css` returns matches only inside `@theme` plus an explicitly documented exception list.

### P3 — Dead legacy components and tokens keep drift alive

- Evidence: `.hero` block `tailwind.css:243-263` plus responsive overrides at `:1070` and `:1095-1097` — no `.hero` element is generated (only `.hero-actions` is reused, `build.ts:481`); legacy fallback selector `.poster-copy > p:not(...)` (`tailwind.css:420-425`, animation at `:1037`) matches no current markup; tokens `--feat-display` (`tailwind.css:37`) and `--feat-num` (`:39`) are defined but never referenced; `data-key="S|L|B|C"` attributes (`build.ts:387-390`) are consumed by nothing in `site.js` and hint single-key navigation that does not exist (real binding is the `g` chord, `site.js:360-376`).
- Consequence: maintenance noise and a misleading affordance hint; the dead `.hero`/legacy rules can be accidentally "restored".
- Suggested correction: delete the `.hero`, legacy-selector, and unused `--feat-*` blocks; remove `data-key` or implement the hint it implies.
- Acceptance criteria: `grep` finds no `.hero `, `--feat-display`, `--feat-num`, or `data-key` in `site/src` and `site/scripts`.

### P3 — Homepage code sample is captioned as a file it does not reproduce

- Evidence: figcaption "EXAMPLES / 004_func.a7" (`build.ts:532`) vs actual `examples/004_func.a7`: the file uses `result := add(5, 7)` then prints `5! = {}` with `factorial(5)`; the site shows an inlined `add(5, 7)` call and `factorial(6)` printing `6! = {}`, plus an added comment ("Iterative — A7 source recursion is banned") not in the file.
- Consequence: the section headline promises "Syntax from working examples"; a caption naming a specific file while showing edited code undermines the evidence-based stance and invites silent drift.
- Suggested correction: either caption it "adapted from examples/004_func.a7", or have the build inline the real file (escape + highlight) so caption and bytes agree.
- Acceptance criteria: caption provenance is accurate; if verbatim provenance is claimed, the rendered code text equals the example file's text modulo highlighting spans.

### P3 — "Examples: verified" stat is unverifiable; a concrete count is available

- Evidence: `build.ts:487-488` (stat "verified"); 43 example files exist (`ls examples/*.a7 | wc -l` = 43); `docs/CHANGELOG.md` notes `scripts/project_status.py` is the source for example counts.
- Consequence: "verified" names no verifier; the strongest fact available (a count maintained by the release tooling) is left off the poster.
- Suggested correction: render the number from build-time facts (e.g. "43 examples") or link the stat to the Release page where the gate is defined.
- Acceptance criteria: the stat is numeric and matches `scripts/project_status.py` output, or carries a link to its evidence.

### P3 — Mobile topbar loses the search and shortcuts controls entirely

- Evidence: `tailwind.css:1088` (`.shortcut-trigger { @apply hidden; }` in the ≤640px block); no alternative search entry exists on small screens (quick links are page links only).
- Consequence: the only real interactive controls in the topbar are removed on phones while decorative elements (registration marks, plates) survive — the inverse of the "controls versus decoration" priority. This is a component-pattern observation; behavioral detail belongs to the interactions review.
- Suggested correction: keep a single compact search trigger in the collapsed mobile topbar (shortcuts trigger may stay hidden).
- Acceptance criteria: at ≤640px a visible control opens the search modal.

### P3 — "Overview" nav item (00) leads to the poster; the overview body exists only as raw markdown

- Evidence: `index.md` frontmatter (nav "Overview", group "Getting started", order 0) places it in the sidebar of every doc page; `docHref('index')` returns the homepage (`build.ts:247-249`); `homeHtml` never renders `doc.html` (`build.ts:365,451`), so the overview sections — Pipeline, Read order, Repository docs, Public contract (`site/public/docs/index.md:15-67`) — appear on no HTML page.
- Consequence: the label promises an overview document; readers get a poster. The "Public contract" (stable URLs) is invisible to HTML readers, though it is exactly the content agents are told to rely on.
- Suggested correction: either rename the sidebar item to "Home", or surface the read-order/public-contract material on the homepage below the fold (the route board already covers read order partially).
- Acceptance criteria: the sidebar label matches the nature of the landing page, and public-contract content is reachable in rendered HTML.

### P3 — Inline style in the doc footer bypasses the class system

- Evidence: `build.ts:441` — `style="margin-left:auto;opacity:.7"`.
- Consequence: one-off inline styling contradicts the tokens-and-components rule and is invisible to the stylesheet's single source of truth.
- Suggested correction: add a small utility (e.g. `.doc-footer-note`) in the components layer.
- Acceptance criteria: generated HTML contains no `style=` attributes.

### P3 (coordinator action, not done here) — Served raw artifacts lag the edited overview

- Evidence: `diff` shows `site/dist/docs/index.md` ≠ `site/public/docs/index.md` and `site/dist/llms-full.txt` ≠ `site/public/llms-full.txt`; `dist/llms.txt` matches. `site/public/docs/index.md` is modified in the worktree (documentation cleanup by other workers — preserved). The overview itself states "Drift between the site and repository docs is a bug" (`index.md:50`).
- Consequence: agents curling `/docs/index.md` and `/llms-full.txt` receive pre-cleanup content while the HTML chrome presents the current state.
- Suggested correction: re-run `bun run build` (normal flow) before the next deploy. Deliberately not executed in this review to avoid rebuilding the shared dist.
- Acceptance criteria: after the next build, `dist/docs/index.md`, `dist/llms-full.txt` and `dist/llms.txt` are byte-identical to their `public/` counterparts.

## Observations (no change requested here)

- Smallest type on the site (10px mono captions, letter-spacing .18–.26em) consistently uses `muted-500` — the faintest ink at the smallest size. As a hierarchy pattern this concentrates the least-readable treatment on metadata; numeric contrast evaluation is left to the accessibility review.
- Terminal traffic-light colors (`tailwind.css:623-625`) are off-token but pictorial; acceptable if documented as an exception in the P2 token cleanup.
- Homepage max-width 1720px vs docs shell 1480px (`tailwind.css:174,291`) reads as an intentional poster-vs-editorial scale difference; worth one sentence in `site/README.md` if challenged.
- `404.html` is an unstyled redirect stub (title "A7 route redirect") with an unstyled no-JS fallback link. Acceptable pattern; a Field-Manual-styled fallback would be a low-value polish.
- `scripts/lint.ts:6` requires eight docs but not `project.md`, so removal of `project.md` would silently drop the "Project" nav group. A one-word addition to `REQUIRED` closes it.
- The build writes generated `llms.txt`/`llms-full.txt`/`sitemap.xml` into `public/` (source tree), which is the mechanism behind the drift class in the last finding; a build-output-only layout would remove it. Process-level; noted for the coordinator.

## Coverage limits

- No browser rendering: no visual, spacing, or computed-style verification; SVG color drift was judged from source values, not pixels.
- Preview inspected via read-only `curl` of served HTML only; no interaction paths exercised.
- `compile` terminal-tab output format was verified only at the level of the `--mode` flag existing (`a7/cli.py:24-27`); the exact stage lines were not reproduced by running the compiler.
- Contrast ratios not computed; keyboard/search behavior not exercised; SEO/typography/responsive/IA/interaction areas excluded (covered by sibling reviews, not read).
- This review does not claim to enumerate all design-system issues, and does not constitute acceptance of the site.
