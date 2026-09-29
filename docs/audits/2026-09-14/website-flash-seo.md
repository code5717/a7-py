# Website review — SEO and web delivery (GLM-5.3-Flash)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- Scope: bounded area only: titles/descriptions, canonical/base path,
  robots/sitemap, metadata, crawlable links, status/not-found behavior, raw
  Markdown discovery, page identities, link previews, deployment configuration.
- Advisory only. No implementation files edited; nothing committed or deployed.
  Findings are not exhaustive and imply no full acceptance.

## Method and inspected artifacts

Source inspected:

- `site/scripts/build.ts` (generator: head/meta, canonical, sitemap, llms files,
  404.html consumption, page templates)
- `site/scripts/serve.ts` (local preview server)
- `site/scripts/lint.ts`, `site/package.json`, `site/README.md`
- `site/public/404.html`, `site/public/robots.txt`, `site/public/sitemap.xml`
- `site/public/docs/*.md` (frontmatter: title/nav/group/summary/order)
- `site/src/site.js` (client redirect handling for `?from=`, search index fetch)
- `site/dist/` (existing build, not rebuilt): all 9 `index.html` heads grepped,
  `assets/search.json`, corpus copies diffed against `public/`
- `.github/workflows/deploy-docs.yml`
- `AGENTS.md` (read first)

Local checks run (exact):

- `curl -s -D -` status/type matrix on `http://localhost:4173/a7-py/…` for `/`,
  `/start/`, `/start` (no slash), `/nonexistent-page/`, `/docs/language.md`,
  `/llms.txt`, `/llms-full.txt`, `/robots.txt`, `/sitemap.xml`,
  `/assets/search.json`
- H1 counts: `grep -o "<h1…"` on `dist/start/index.html`,
  `dist/language/index.html`
- Per-page head audit: grep `<title>`, canonical, description across all 9
  built pages
- Consistency diffs: `public/llms.txt` vs `dist/llms.txt` (identical),
  `public/sitemap.xml` vs `dist/sitemap.xml` (identical),
  `public/llms-full.txt` vs `dist/llms-full.txt` (differ — see context note),
  `dist/docs/*.md` vs `public/docs/*.md` (differ only for the uncommitted
  `index.md` cleanup paragraph)

Published-site checks (live, `https://code5717.github.io/a7-py/`, via curl and
webfetch):

- `/` → 200 `text/html`; head inspected: canonical
  `https://code5717.github.io/a7-py/`, title `A7`, description present, no
  `og:*`/`twitter:*`
- `/start` → **301** → `/start/` (trailing-slash canonical form enforced)
- `/not-a-real-page/` → real **404** status, 404.html body served
- `/docs/language.md` → **200 `text/markdown`** (raw markdown survives Pages;
  front matter included)
- `/robots.txt`, `/sitemap.xml`, `/llms.txt` → 200 with correct types,
  `cache-control: max-age=600`
- Live `llms-full.txt` fetched and compared with working tree
- Deploy history: `gh run list --workflow deploy-docs.yml` — last successful
  deploy 2026-06-14 (matches live footer "built 2026-06-14"); only Dependabot
  bumps since.

## Verified good (do not regress)

These are observable invariants that hold today, checked locally and/or live:

1. **Per-page identities**: all 9 pages have unique `<title>` (`X - A7`
   pattern), unique meta description sourced from frontmatter `summary`
   (build.ts:363, 373; verified in every `dist/*/index.html`).
2. **Canonicals**: every page emits one canonical matching its URL exactly;
   sitemap `<loc>` values match canonicals 1:1 for all 9 URLs
   (build.ts:364, 690-696; diffed public vs dist identical).
3. **Base path consistency**: `/a7-py` hard-coded consistently in build.ts:9,
   public/404.html:5, src/site.js:2, serve.ts:22; all generated hrefs,
   canonicals, sitemap, robots, and llms.txt URLs use it. Live 301 from
   `/start` → `/start/` prevents non-slash duplicates; local preview serves
   both but canonical tags disambiguate.
4. **robots/sitemap**: robots.txt allows all and references the sitemap; both
   verified live 200. Sitemap has valid namespace, 9 URLs, no stray or missing
   pages.
5. **Crawlable links**: nav, quick links, route board, pager, doc footer
   ("Raw markdown"), and home footer are server-rendered `<a href>` elements.
   Search results are JS-only but are not the sole path to any page.
6. **Raw Markdown discovery (published)**: `/docs/<slug>.md` twins verified
   live 200 `text/markdown` including front matter; discoverable from every
   doc page footer, `llms.txt` (lists all 9 with summaries), and `llms-full.txt`
   (full corpus with source URLs). All llms.txt URLs point at the live origin.
7. **Not-found behavior (published)**: unknown routes return a real 404 status
   plus a no-JS fallback link; 404.html's script redirects to home with
   `?from=…` and site.js:8-14 restores known first-segment routes client-side.
   Home canonical (query-less root) prevents the `?from=` variant from
   indexing as a duplicate.
8. **Deployment config**: `deploy-docs.yml` builds `site/dist` on push to
   master/main (bun frozen lockfile, lint, build) and publishes via
   `upload-pages-artifact` + `deploy-pages`; live behavior confirms the
   artifact is served as-is (raw .md intact).

## Findings

### F1 — Duplicate `<h1>` on every doc page (P1)

- Evidence: build.ts:434 renders `<h1>${doc.title}</h1>` in the article header;
  renderMarkdown (build.ts:158-171) also renders the body's `# Start` /
  `# Language` line as a second `<h1 id=…>`. Verified in dist:
  `<h1>Start` + `<h1 id="start">` in `dist/start/index.html`; same in
  `dist/language/index.html`.
- Consequence: two level-1 headings per page blur the page-heading signal for
  SERP/heading extraction and produce a doubled outline; the un-anchored
  template H1 and the anchored body H1 carry identical text.
- Correction: strip the single leading body H1 in `renderMarkdown` output when
  it duplicates `doc.title` (or demote body `#` to be skipped), keeping the
  template H1 — or the reverse; pick one owner.
- Acceptance: exactly one `<h1>` per built page; TOC/anchors still resolve;
  `bun run lint && bun run build` passes.

### F2 — Local preview soft-404s: unknown paths return HTTP 200 (P2)

- Evidence: serve.ts:28-29 falls back to `404.html` without setting a status
  (default 200). Verified locally: `GET /a7-py/nonexistent-page/` → 200
  `text/html`. Published behavior is correct (live 404 verified).
- Consequence: local QA, link checkers, and any scripted route audit against
  the preview cannot detect broken routes; local and prod behavior diverge.
- Correction: in serve.ts, respond with status 404 while still serving the
  404.html body.
- Acceptance: `curl -s -o /dev/null -w '%{http_code}'` on an unknown preview
  path returns 404; known routes still 200; 404 body unchanged.

### F3 — Home page `<title>` is just "A7" (P2)

- Evidence: build.ts:363 special-cases index to `'A7'`; confirmed live.
- Consequence: the most competitive page has the thinnest SERP title; branding
  alone wastes the title budget that every other page uses well.
- Correction: e.g. `A7 — AOT compiler: Python-like source to Zig 0.16`
  (keep uniqueness and current description).
- Acceptance: home title names the product and its differentiator; all 9
  titles remain unique.

### F4 — No `.nojekyll` in the published artifact (P2, defensive)

- Evidence: no `.nojekyll` anywhere in the repo (searched); `dist/` listing has
  none; `site/public/docs/*.md` all carry YAML front matter, which Jekyll
  would transform.
- Consequence: raw-markdown availability currently rests on the artifact-based
  Pages path not running Jekyll (verified working today, live
  `text/markdown`). A future switch to branch-based Pages deployment would
  silently break every documented raw fetch URL (llms.txt entries,
  agent-usage.md:17-20, doc footers).
- Correction: add an empty `site/public/.nojekyll` (copyPublic copies it into
  dist).
- Acceptance: `.nojekyll` present in dist; live `/docs/language.md` still 200
  `text/markdown` after next deploy.

### F5 — No Open Graph / Twitter card metadata (P3 — optional polish)

- Evidence: build.ts:367-381 head has title/description/canonical/theme-color/
  icon/fonts only; live head confirmed zero `og:*`/`twitter:*`.
- Consequence: link shares (chat apps, social) render no card. Per review
  constraints this is deliberately ranked below the items above.
- Correction: og:title/og:description/og:url/og:type + `twitter:card=summary`
  per page from existing title/summary; optional og:image derived from the
  system map.
- Acceptance: sharing any page shows title/description card; URLs stay
  canonical-consistent.

### F6 — Raw `.md` twins are indexable near-duplicates with no stated policy (P3)

- Evidence: `/a7-py/docs/<slug>.md` serves the same content as the HTML page;
  text/plain cannot carry `<link rel=canonical>` and GitHub Pages cannot set
  `X-Robots-Tag` (static host). MD bodies link to HTML routes (e.g.
  language.md `[Status](/a7-py/status/)`), so agents following in-corpus links
  land on HTML.
- Consequence: crawlers may index both variants; the HTML page's canonical
  protects it but the .md can surface separately. Agent journeys get HTML when
  following md-internal links.
- Correction: record a decision; options: keep as-is (accept duplicates), or
  append an HTML-canonical pointer line to each md, or switch in-corpus links
  to sibling `.md` targets.
- Acceptance: a documented decision exists in the corpus (agent-usage or
  project page) and any chosen mechanism is verifiable in dist.

### F7 — `assets/search.json` served as `application/octet-stream` in preview (P3)

- Evidence: serve.ts:8-16 lacks a `.json` mapping; verified locally. Live GH
  Pages serves its own types (not checked for this file; unverified live).
- Consequence: cosmetic; `fetch().json()` ignores MIME, but strict tooling may
  flag it.
- Correction: add `if (file.endsWith('.json')) return 'application/json;
  charset=utf-8'`.
- Acceptance: preview returns `application/json` for `search.json`.

### F8 — llms.txt entry format deviates from the common convention (P3)

- Evidence: build.ts:657-671 emits `- Title: URL` + indented summary; the
  widely-followed draft convention is `- [Title](URL): summary`.
- Consequence: strictly-convention-parsing agent tooling may miss entries; the
  file is otherwise complete and correct (9 pages, live-fetched URLs).
- Correction: align the line format (or document the format explicitly in
  agent-usage.md).
- Acceptance: format either matches the convention or is explicitly specified
  in the corpus.

### F9 — Informational: working tree is ahead of the published site (no action now)

- Evidence: uncommitted modifications `site/public/docs/index.md` and
  `site/public/llms-full.txt` (git status; mtimes 08:28 vs dist build 08:27)
  add one paragraph; live llms-full.txt lacks it and live footer says "built
  2026-06-14"; last successful deploy 2026-06-14 (gh run list). Local `dist/`
  is correspondingly stale for these two files.
- Consequence: none today — the live corpus is self-consistent and matches
  pushed master. Next push to master publishes the cleanup.
- Acceptance: after next deploy, live llms-full.txt contains the new paragraph
  and home footer date updates; verify with the curls already specified in
  agent-usage.md "Deploy verification".

### F10 — Informational: hard-coded version/base strings (no action now)

- Evidence: `v0.16` (build.ts:385), `v0.16.0` (poster/footer, build.ts:461,
  641), BASE/ORIGIN duplicated across build.ts:9-10, 404.html:5, site.js:2,
  serve.ts:22. All currently in sync with package.json 0.16.0.
- Consequence: drift risk at the next release or repo rename; not a defect
  today.

## Provider / capability limitations

- Browser capture blocked (in-app browser unavailable; local browser
  connection failed). The 404.html and `?from=` JS redirects were reviewed by
  source reading only; no rendered-DOM or screenshot verification.
- Live HTTP statuses/headers were obtained via `curl` from this environment;
  `webfetch` cannot expose status codes for 2xx responses. Live caching was
  observed only via `cache-control` headers; CDN/edge behavior beyond that is
  unverified.
- Search-engine indexing, Search Console data, Lighthouse scores, and mobile
  rendering are out of reach and out of scope.
- GitHub Pages build logs for the 2026-06-14 run were not inspected (would
  require further authenticated API calls; behavior was verified from the
  live responses instead).
- The shared `site/dist` was not rebuilt (per constraints); dist greps reflect
  pre-cleanup content for the index corpus files. Generator behavior was
  verified from source plus the existing dist for the other 8 slugs.

## Coverage limits

- This review does not claim to enumerate all SEO issues; it covers the listed
  area with the checks above. No accessibility, content-accuracy, or
  performance review is included (other reviewers' areas).
- Link checking was representative (nav/footer/raw-md links inspected
  in dist and live), not an exhaustive crawl of every href/anchor.
- No test-count or coverage targets are asserted; acceptance criteria above
  are observable requirements only.
