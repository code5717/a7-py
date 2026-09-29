# Website Organization Review — GLM-5.3-Flash

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- Scope: information organization of the docs site (`site/`): newcomer-to-advanced
  reader routes, task naming/grouping, navigation hierarchy, reference
  discoverability, placement of limitations and release requirements, authority
  of canonical vs summarized docs, raw-agent navigation.
- Advisory. No implementation changes were made.

## Inspected files and exact checks

Files inspected:

- `AGENTS.md`, `site/README.md`
- `site/scripts/build.ts` (nav groups, order, home/HTML generation, llms/sitemap/search generators)
- `site/scripts/lint.ts`
- `site/src/site.js` (shortcuts, `g`-chord nav keys, 404 `?from=` handling, search loader)
- `site/public/docs/*.md` — all nine pages in full
- `site/public/llms.txt`, `site/dist/llms.txt`, `site/dist/llms-full.txt`
- `site/dist/` — sidebar/nav/pager HTML, `assets/search.json`, `sitemap.xml`, `robots.txt`, `404.html`

Exact checks run:

- `diff` of every `site/public/docs/*.md` against `site/dist/docs/*.md` (only
  `index.md` differs — see Observation O1)
- `diff` of `public/llms.txt` vs `dist/llms.txt` (in sync) and
  `public/llms-full.txt` vs `dist/llms-full.txt` (differ — O1)
- `git status --porcelain -- site` (in-progress cleanup present; preserved)
- Parsed rendered sidebar/pager HTML from `dist/start/index.html` and via
  `curl http://localhost:4173/a7-py/…` for `status/`, `release/`, `project/`
- `rg` for `Public contract` and `authoritative` across `site/dist/**/*.html`
- Enumerated `assets/search.json` (51 entries: 9 pages + h2/h3 headings)

Coverage limits and capability constraints:

- Browser capture was blocked (in-app browser unavailable; local browser
  connection failed). No Playwright/browser was invoked. Served-HTML checks used
  `curl` against the existing preview at `http://localhost:4173/a7-py/` and the
  checked-in `site/dist/`.
- The shared `site/dist` was not rebuilt. The local preview therefore serves the
  08:27 build, which predates an in-progress edit (O1).
- Production GitHub Pages URLs were not fetched; findings about published state
  are inferences from the build script and checked-in `dist/`.
- Visual design, responsive layout, and accessibility beyond nav markup are out
  of scope. Repo docs (`docs/SPEC.md` etc.) were not content-reviewed — only
  their discoverability from the site.

Preserved in-progress work (not treated as defects): local modifications to
`site/public/docs/index.md` and `site/public/llms-full.txt` (an added
"repository documentation index" paragraph).

---

## Findings

### F1 — High: linear reading order breaks group contiguity; page 07 sits inside the Project block

Evidence:

- `site/public/docs/agent-usage.md:6` — `order: 7`; `site/public/docs/project.md:6` — `order: 8`.
- `site/scripts/build.ts:24-34` (`DOC_ORDER`) and `build.ts:36-41`
  (`NAV_GROUP_ORDER` ends with `Agents`).
- Rendered sidebar (dist + preview): Getting started `00,01` → Reference
  `02,03,04` → Project `05,06,08` → Agents `07`.
- Pager: `release/` next → **Agent Usage**; `project/` previous → **Agent Usage**
  (`build.ts:403-417` walks flat order).
- Home route board shows the same broken sequence: Project group ends with
  `08 Project`, then the Agents group shows `07` (`build.ts:269-286`).

Consequence: the site's own promise — "Read in order."
(`build.ts:508`) and the index read-order table
(`site/public/docs/index.md:21-32`) — is contradicted by the visible page
numbers and by the prev/next route: a linear reader goes Status(05, Project) →
Release(06, Project) → Agent Usage(07, Agents) → Project(08, Project), bouncing
between two groups, and the route board displays 05, 06, 08, then 07.

Suggested correction (minimal, preserves all groupings): renumber the last two
pages — `project.md` `order: 7`, `agent-usage.md` `order: 8` — and swap the two
rows in the index read-order table (`site/public/docs/index.md:31-32`) so Agent
Usage is listed last. Groups become contiguous blocks (Getting started 0-1,
Reference 2-4, Project 5-7, Agents 8), matching `NAV_GROUP_ORDER` and matching
Agents as the natural exit route for raw-fetching agents.

Acceptance criteria:

- Sidebar numbers ascend 00→08 and each nav group is a contiguous numeric block.
- The prev/next pager sequence never leaves a group and re-enters it later.
- Home route board numbers ascend within and across groups.

### F2 — High: the canonical-authority statement is absent from the rendered human surface

Evidence:

- `site/scripts/build.ts:451-655` — `homeHtml()` renders a hardcoded poster,
  route board, preview, and terminal strip; it never renders `doc.html` for the
  index doc. The index markdown body (`site/public/docs/index.md:9-67`: Pipeline,
  Read order, Repository docs, Public contract) is not present in any rendered
  HTML page.
- `rg -l "Public contract" site/dist/` matches only `docs/index.md` (the raw
  twin), `llms-full.txt`, and `search.json` — no HTML page.
- `rg -l "authoritative" site/dist/**/*.html` matches only
  `status/index.html` and `agent-usage/index.html`.

Consequence: the authority model ("site compresses the repository; `README.md`,
`docs/SPEC.md`, `docs/STATUS.md`, `docs/RELEASE.md` are authoritative",
`site/public/docs/index.md:34-42`) is visible to agents fetching raw markdown
but never to a human reader of the homepage — the primary landing surface. The
in-progress index.md edit strengthens the raw twin only; the rendered site stays
silent. Canonical vs summarized authority is asserted asymmetrically.

Suggested correction: keep the poster homepage minimal, but render the index
doc's prose somewhere humans reach: either (a) add a compact "Canonical sources"
section to `homeHtml()` (3–4 lines: site is a public summary; README/SPEC/
STATUS/RELEASE are authoritative; link each), or (b) render `index.md`'s body as
a real `/overview/`-style HTML page linked from the route board, so the markdown
body and HTML stop diverging. Option (a) is the smaller change and keeps the
current single-page home.

Acceptance criteria:

- Rendered HTML at `/a7-py/` (or a page linked from the home route board)
  contains a visible statement that repository docs are authoritative, with
  working links to README/SPEC/STATUS/RELEASE.
- The stable public-contract URL list appears in rendered HTML, not only in the
  raw markdown twin.

### F3 — Medium: canonical docs are named as plain code text, not links, from the site summaries

Evidence:

- `site/public/docs/language.md:11-13` — "Full semantics are in
  `docs/SPEC.md`" renders as `<code>` (`dist/language/index.html:54`); no link.
- `site/public/docs/status.md:13` — `docs/STATUS.md` plain text.
- `site/public/docs/release.md:11` — `docs/RELEASE.md` plain text.
- `site/public/docs/start.md:57-58` — `docs/SPEC.md` plain text.
- `site/public/docs/project.md:29` — `docs/CHANGELOG.md` plain text.
- Only `site/public/docs/index.md:44` links into the repo docs (the GitHub
  docs README). The index authority list (`index.md:37-42`) omits
  `docs/CHANGELOG.md`, although `AGENTS.md` (Post-Change Checklist) treats it
  as release-facing and required.

Consequence: a reader on a site summary page cannot jump to the canonical
source it summarizes; the summary→canonical chain the authority model depends on
is prose-only. Newcomers are told a file path they may not know how to resolve.

Suggested correction: hyperlink each first mention to the canonical file
(e.g. `https://github.com/code5717/a7-py/blob/master/docs/SPEC.md`) on the
Language, Status, Release, Start, and Project pages; add `docs/CHANGELOG.md` to
the index authority list or state explicitly that the changelog is
release-facing and not mirrored on the site.

Acceptance criteria:

- Every rendered page that names a canonical repo doc hyperlinks it; the link
  resolves to the file on the default branch.
- The index authority list either includes `docs/CHANGELOG.md` or the site
  states where release-facing notes live.

### F4 — Medium: limitations (Status) are not labeled or linked for newcomers

Evidence:

- `site/public/docs/status.md:4-5` — Status is in group `Project`, nav label
  "Status"; the group name carries no "state/limitations" semantics, and the
  group also contains Release and the contribution page.
- `site/scripts/build.ts:386-393` — the topbar quick rail lists only Start,
  Language, Stdlib, Compiler; Status is absent from every page's top
  navigation (`site.js` already maps `g t` → `status/`, `site.js:324`).
- Home poster states limitations as slogans ("Recursion banned",
  `build.ts:490`) with no link to Status; the route board intro
  (`build.ts:509`) mentions "project status" only in prose.

Consequence: a newcomer evaluating A7 scans for "Limitations/Gaps/Roadmap" and
finds only the "Project" group label; discovering the known-gaps list requires
reading group contents. Limitations are placed correctly in the reading order
(before Release), but their entry points are weak.

Suggested correction (preserving current grouping): add a Status link to the
topbar quick rail in `pageHtml()` (the `g t` shortcut already exists), and/or
rename the group to "Project state" in `NAV_GROUP_ORDER` and the three pages'
`group:` frontmatter. Either change is a few lines; the topbar link is the
lower-risk one.

Acceptance criteria:

- From any rendered page, Status is reachable in one click via the top rail
  (not only via the sidebar group).
- If the group is renamed, rendered nav groups and frontmatter agree and the
  route board reflects the new label.

### F5 — Medium: Start requirements mix compiler needs with docs-site contributor needs

Evidence: `site/public/docs/start.md:11-16` — Requirements list Python 3.13+,
`uv`, Zig 0.16.0, and "Bun to build the docs site locally". Bun is never needed
to compile or run A7; it belongs to the docs deployment flow documented on
Release (`site/public/docs/release.md:20,32-38`) and Project.

Consequence: the first page a newcomer reads implies Bun is part of the A7
toolchain, inflating the perceived install cost of the install route.

Suggested correction: keep Start requirements to exactly what compiling and
running A7 needs (Python 3.13+, `uv`, Zig 0.16.0); move or annotate the Bun
requirement ("only for building the docs site") into Release/Project where the
docs gate already lives.

Acceptance criteria:

- The Start requirements list contains only compiler-run prerequisites; a reader
  can install and compile `examples/001_hello.a7` without anything the list
  doesn't name.
- Docs-site build prerequisites appear on Release and/or Project pages.

### F6 — Low: `llms.txt` lacks the authority and fetch-order framing that agents only find on Agent Usage

Evidence: `site/public/llms.txt:1-25` — lists the nine pages with summaries and
a canonical-site line, but says nothing about which sources are authoritative
and does not point to `docs/agent-usage.md` for fetch order. `agent-usage.md`
(`site/public/docs/agent-usage.md:32-38`) carries the agent rules, but an agent
that fetches only the advertised first entry (`llms.txt`) never sees them.
`build.ts:657-671` generates it.

Consequence: the authority hierarchy is one fetch deeper than the advertised
agent entry point; a minimal agent can act on site markdown believing it is the
canonical contract.

Suggested correction: extend `llmsTxt()` with 2–3 framing lines: state that
site markdown is a public summary and `README.md`/`docs/SPEC.md`/
`docs/STATUS.md`/`docs/RELEASE.md` in the repository are authoritative, and
link `docs/agent-usage.md` for fetch order. Regeneration keeps `public/` and
`dist/` copies in sync.

Acceptance criteria:

- The generated `llms.txt` names the canonical sources and links the
  agent-usage page; both the `public/` and `dist/` copies contain the framing
  after a build.

### F7 — Medium: page lists are duplicated across generators, and site lint does not guard `project.md`

Evidence:

- `site/scripts/lint.ts:6` — `REQUIRED` lists 8 files and omits
  `project.md`, although `project.md` is part of the published public contract
  (`site/public/docs/index.md:66`) and ships in the archive requirement list
  context (`release.md:42-53`).
- The 8-slug list is hardcoded a second time for 404 recovery in
  `site/src/site.js:11`, and a third time as `DOC_ORDER` in
  `site/scripts/build.ts:24-34`.

Consequence: deleting or renaming a contracted page (e.g. `project.md`) would
not fail site lint, and every page addition requires edits in three lists —
the exact drift class `AGENTS.md` calls a bug.

Suggested correction: derive `REQUIRED` in lint and the redirect list in
`site.js` from the frontmatter corpus (e.g. lint reads `docs/*.md` and compares
against the URL contract parsed from `index.md`, or both import a shared
generated list); at minimum add `project.md` to `REQUIRED` now.

Acceptance criteria:

- Site lint fails if any page named in the public contract is missing from
  `site/public/docs/`.
- A new page can be added by editing one list (plus its own file), verified by
  a dry-run adding a page and observing a single-list change.

### Observation O1 (no action requested): in-progress cleanup is newer than the shared dist

Evidence: `site/dist` was built 2026-09-14 08:27; `site/public/docs/index.md`
and `site/public/llms-full.txt` contain an added paragraph ("repository
documentation index…") absent from `site/dist/docs/index.md` and
`site/dist/llms-full.txt` (verified by `diff`; `git status` shows both files
modified). The preview at `http://localhost:4173/a7-py/` therefore serves the
pre-cleanup homepage content. `public/llms.txt` is in sync with `dist`.

This is consistent with the stated in-progress documentation cleanup; it is
recorded so the next full build (`cd site && bun install && bun run build`,
which writes both `public/` and `dist/`) publishes it. Per instructions the
shared dist was not rebuilt.

## Preserved strengths (keep as-is)

- Raw markdown twins for every page, linked per-page from each doc footer
  ("Raw markdown", `build.ts:439`), plus `llms.txt` / `llms-full.txt` /
  `sitemap.xml` in the home footer Raw column — good raw-agent discoverability.
- Home hero links "Agent fetch paths" directly (`build.ts:484`); the
  agent fetch order (llms.txt → llms-full.txt → language.md) matches the
  generated llms ordering.
- Search covers all 9 pages plus h2/h3 headings with group labels
  (`search.json`, 51 entries); keyboard nav includes every page (`g`-chord).
- 404 fallback redirects unknown routes home and remaps known slugs
  (`404.html`, `site.js:8-14`).
- Reading-order placement of limitations before release requirements
  (Status 05 → Release 06) and the "not a sandbox" caveat on both Compiler
  (`compiler.md:68`) and Project (`project.md:47-48`) pages.
- Canonical URLs, sitemap order, and robots are consistent with doc order.

## Limitations of this review

- No browser rendering was possible (capture blocked); layout/visual behavior
  of nav was assessed from generated HTML/CSS markup, not a rendered viewport.
- Production-site state was not fetched; conclusions about the deployed site
  assume the GitHub Pages workflow publishes `site/dist` as documented.
- Content accuracy of repo docs and of page prose was out of scope; only
  organization, entry points, and authority linkage were evaluated.
- Findings are not exhaustive; acceptance criteria above are checkable
  invariants, not a full acceptance suite.
