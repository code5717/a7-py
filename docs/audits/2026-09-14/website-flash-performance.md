# Website Performance Review — A7 Docs Site (GLM-5.3-Flash)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- Reviewer: GLM-5.3-Flash, website performance specialist (advisory, bounded area)
- Scope: performance only: asset sizes, request/caching structure, render-blocking work,
  font loading, DOM/event/observer costs, search startup/filtering, unnecessary work,
  mobile constraints, build output.
- Workspace: `/home/cx89/Projects/pl-dev/a7-py` (site under `site/`)
- Advisory findings, not an acceptance verdict. The review does not claim to find every issue.

---

## 1. Method and inspected material

### 1.1 Files inspected (read in full or relevant sections)

- `/home/cx89/Projects/pl-dev/a7-py/AGENTS.md`
- `/home/cx89/Projects/pl-dev/a7-py/site/README.md`
- `/home/cx89/Projects/pl-dev/a7-py/site/package.json`
- `/home/cx89/Projects/pl-dev/a7-py/site/scripts/build.ts` (full, 754 lines)
- `/home/cx89/Projects/pl-dev/a7-py/site/scripts/serve.ts` (full)
- `/home/cx89/Projects/pl-dev/a7-py/site/src/site.js` (full, 442 lines)
- `/home/cx89/Projects/pl-dev/a7-py/site/src/tailwind.css` (lines 100–169, 344–365, 668–682
  context, 898–905, 1000–1140; plus greps over the whole file)
- `/home/cx89/Projects/pl-dev/a7-py/site/dist/` (full recursive inventory; `404.html` read;
  head of `assets/site.css`; `index.html`, `language/index.html`, `compiler/index.html`,
  `start/index.html`, `stdlib/index.html` inspected via HTTP and tag counts)

### 1.2 Exact checks performed (local measurements)

1. Full `site/dist` file inventory with byte sizes (`find … ls -la`).
2. Raw vs gzip(1) payload sizes for every first-party artifact
   (`gzip -c file | wc -c` locally — no server compression involved).
3. Byte-compare `src/site.js` vs `dist/assets/site.js` (`cmp`) — identical, proving the
   build ships JS unminified and untransformed.
4. `diff -rq site/public site/dist` — source-vs-dist drift check.
5. HTTP response headers from the local preview `http://localhost:4173/a7-py/` via
   `curl -sI` for `/`, `/assets/site.css`, `/assets/site.js`, `/assets/search.json`.
6. DOM element counts per page (`grep -o '<[a-zA-Z]'`), per-tag prose-child counts for
   reveal-candidate estimation, and `search.json` entry count.
7. Static greps for CSS cost drivers: `backdrop-filter`, `will-change`, `@keyframes`,
   `animation`, `transition`, `font-variation-settings`, `prefers-reduced-motion`.

### 1.3 Execution limitations (recorded as required)

- **Provider rate-limit failure:** this review was interrupted mid-run by a GLM provider
  request-rate failure and was resumed by the coordinator. No findings were lost, but the
  run was split across sessions.
- **Tool-permission denial:** one combined measurement command was rejected because it
  used relative `cd`-based paths. Retried and completed with absolute paths; no evidence
  gap remains from this.
- **No browser:** in-app browser unavailable; local browser connection failed. Per
  instructions, Playwright/MCP/competing browsers were not invoked. Therefore:
  - No Lighthouse scores, no Core Web Vitals (LCP/CLS/INP), no render timings, no real
    waterfall, no font-file payload counts are reported. None are invented below.
  - Request *order* below is derived from HTML/CSS/JS source analysis, not observed.
- **Preview server ≠ production CDN:** the local preview (`serve.ts`) sends no
  `Content-Encoding` and no `Cache-Control`, and serves `.json` as
  `application/octet-stream` (`site/scripts/serve.ts:15`). GitHub Pages' production
  compression/caching behavior was **not** measured live; nothing below relies on
  unverified production headers.
- **Dist staleness at review time:** `diff -rq public dist` shows
  `public/docs/index.md` and `public/llms-full.txt` differ from their `dist/` copies
  (docs cleanup landed after the last build). Byte sizes of measured HTML/`llms-full.txt`
  therefore reflect a slightly stale corpus; conclusions are not size-sensitive at this
  scale, but see Finding F6.

---

## 2. Baseline: build output inventory

Measured from existing `site/dist` (stale-docs caveat above). Gzip = local `gzip` level
default, a proxy for server transfer size.

| File | Raw (B) | gzip (B) |
|---|---:|---:|
| `assets/site.css` (tailwindcss 4.3, `--minify`) | 65,975 | 10,971 |
| `index.html` (home) | 16,610 | 4,358 |
| `assets/site.js` (shipped verbatim) | 13,814 | 4,349 |
| `llms-full.txt` | 14,235 | 5,335 |
| largest doc page (`language/index.html`) | 9,735 | 3,168 |
| `assets/search.json` (51 entries) | 6,028 | 1,241 |
| `a7-system-map.svg`, `favicon.svg` | 3,171 / 310 | — |
| `404.html` (redirect stub) | 369 | — |

The site is small: a doc page costs roughly HTML 3.2 KB + CSS 11 KB + JS 4.3 KB gzip,
plus fonts. The main page costs are **not** first-party bytes. They are the third-party
font CSS on the critical path (F1) and compositing/scroll costs (F2, F3).

---

## 3. Findings

### F1 — Render-blocking third-party font stylesheet on every page — **Priority: High**

- **Evidence:** `site/scripts/build.ts:377–379` — every generated page includes
  `<link rel="preconnect" href="https://fonts.googleapis.com">`,
  `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>`, then
  `<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@…&family=JetBrains+Mono:wght@300..700&display=swap" rel="stylesheet">`.
  A head stylesheet without a non-blocking pattern is render-blocking by spec.
- **Consequence:** first paint of every page is gated by a cross-origin request to
  `fonts.googleapis.com`, and the actual `fonts.gstatic.com` woff2 files are only
  *discovered after* that CSS is parsed (they are not preloaded). On slow or high-RTT
  networks — and in regions where Google font hosts are unreliable or blocked — text
  render is delayed by the full CSS round trip, or stalls until connection failure.
  This is the single largest user-visible load risk on the site, and it is invisible in
  fast-desktop testing.
- **Also:** `display=swap` avoids invisible text (good), but with default fallback metrics
  the swap from serif/monospace fallbacks to Fraunces/JetBrains Mono reflows headlines —
  a visible shift on first visit that metric overrides would remove.
- **Suggested correction:** self-host the two woff2 subsets (the site already serves
  everything else first-party, matching the "intentionally small" design in
  `site/README.md`): download the latin subsets once, add `@font-face` with
  `font-display: swap` plus `size-adjust`/`ascent-override` metric-compatible fallbacks in
  `src/tailwind.css`, drop the two `preconnect`s and the Google CSS link. If self-hosting
  is rejected, at minimum load the Google CSS non-blockingly (e.g. `media="print"`
  swap-onload or `rel="preload" as="style"` with a noscript fallback) and
  `rel="preload" as="font" crossorigin` the two woff2 URLs.
- **Acceptance criteria (observable):**
  - Generated HTML in `site/dist` contains no `<link>` to `fonts.googleapis.com` /
    `fonts.gstatic.com` (grep-checkable), and all font files are served from the site's
    own origin.
  - Render-critical path per page (from head analysis, confirmable in a devtools waterfall
    once browser access is granted) is HTML → site.css only; fonts arrive asynchronously.
  - Font files reuse browser cache across pages (same stable URLs, `font-display` set).
  - No text is invisible while fonts load (`font-display: swap` retained).

### F2 — Full-width sticky topbar with heavy `backdrop-filter` — **Priority: Medium**

- **Evidence:** `site/src/tailwind.css:121–126` — `.topbar` is `sticky top-0` with
  `background: rgba(17,16,14,.82)` and
  `backdrop-filter: blur(14px) saturate(140%)` (+ `-webkit-` prefix). The mobile
  breakpoint (`tailwind.css:1083–1092`) keeps the element sticky; it only changes
  sizing/padding. A second, interaction-gated blur(8px) exists on the modal overlay
  (`tailwind.css:898–901`) — acceptable since it exists only while a modal is open.
- **Consequence:** a permanently visible, full-width backdrop-filtered element forces the
  compositor to re-sample the blurred backdrop on every scrolled frame for the whole page
  session. This is one of the most common real-world scroll-jank sources on low-end
  Android GPUs; the 14px radius + saturate make it worse. User-visible effect: reduced
  scroll smoothness on mobile; measurable battery cost on long reads.
- **Suggested correction:** keep the effect where it is cheap and drop the cost on
  constrained surfaces — e.g. reduce blur radius (8px), remove `saturate()`, or switch to
  a near-opaque background at `(max-width: 640px)` and under
  `prefers-reduced-transparency: reduce`. Alternatively scroll-swap: enable
  backdrop-filter only when `scrollY > 0` (class toggle in the existing topbar scroll
  handler, `site/src/site.js:430–441`).
- **Acceptance criteria (observable):**
  - At `≤640px` viewport widths the topbar style block contains no
    `backdrop-filter` declaration (grep-checkable in built CSS) *or* the blur is
    enabled only after scroll via a class.
  - On a low-end mobile device (verification once browser/device access exists):
    scrolling a long doc page shows no sustained frame drops attributable to the topbar.
  - `prefers-reduced-transparency` users get an opaque topbar.

### F3 — `will-change` on every revealed prose block; reveal hides content pre-JS flag — **Priority: Medium-Low**

- **Evidence:** `site/src/tailwind.css:1012–1018` — `[data-reveal]` sets
  `opacity: 0`, `translateY(14px)`, a 0.7s transition, and
  `will-change: transform, opacity`. The attribute is added by JS only
  (`site/src/site.js:75–82`) to `.prose > h2/h3/p/ul/ol/pre/table`, `.route-board`,
  `.terminal-strip`, `.doc-pager`. Tag counts on `language/index.html`: ~10 `p`, 6 `h2`,
  2 `h3`, 3 `ul`, 4 `pre` ⇒ roughly 25 promoted elements per doc page;
  `index.html` ≈ 27. The `will-change` declaration is never removed after `.is-revealed`.
- **Consequence:** each `[data-reveal]` element keeps a persistent compositor layer for
  the lifetime of the page (memory + raster cost), long after the one-shot reveal
  animation ends. On long reference pages over low-end mobile this is measurable memory
  and compositing overhead for zero visual benefit after the first 0.7s. Not a correctness
  bug: without JS the attribute never exists, so content stays fully visible (verified by
  reading the code path — no-JS safe), and `prefers-reduced-motion` forces
  `[data-reveal] { opacity: 1 }` (`tailwind.css:1053`).
- **Suggested correction:** delete `will-change` from `[data-reveal]` (browsers promote
  elements automatically while the transition runs), or strip it on reveal by setting
  `el.style.willChange = 'auto'` in the observer callback in `site.js:65–83`.
- **Acceptance criteria (observable):**
  - Built CSS contains no `will-change` on `[data-reveal]` *or* revealed elements lose it
    after the transition (inspectable in devtools layers once browser access exists).
  - Independent invariant preserved: with JavaScript disabled, all prose content is
    visible (no `data-reveal` attribute in served HTML — grep `site/dist/**/index.html`
    for `data-reveal`, which must return no static occurrences).

### F4 — `site.js` shipped unminified, no content hashing — **Priority: Low**

- **Evidence:** `site/scripts/build.ts:742` copies `src/site.js` to
  `dist/assets/site.js` verbatim; `cmp` confirmed byte-identity (13,814 B raw /
  4,349 B gzip). No minification step exists (contrast with CSS:
  `site/package.json` `"build:css": "tailwindcss … --minify"`). Filenames carry no
  content hash.
- **Consequence:** ~2–3 KB extra gzip per first visit versus a minified bundle, and no
  fingerprinted URLs. Impact is small: GitHub Pages' short cache lifetime (expected, but
  **not verified live** in this review) makes the missing hash mostly moot, and 4.3 KB
  gzip parses in negligible time. This is a build-hygiene item, not a user-visible bug
  today.
- **Suggested correction:** in `build.ts`, emit JS through the same toolchain as CSS
  (e.g. `Bun.build({ minify: true })` or `bun build --minify`) and, if desired, append a
  short content hash to the filename with the HTML reference rewritten at template time.
- **Acceptance criteria (observable):**
  - After rebuild, `dist/assets/site.js` is minified (no comments; single/few lines) and
    its gzip size is smaller than today's 4,349 B; behavior identical (copy buttons,
    search, shortcuts, tabs all function in smoke test).
  - If hashing is added: every page references the hashed filename; no page references a
    stale name after a rebuild.

### F5 — Search: eager idle fetch and synchronous ranking — **Priority: Low (verified acceptable)**

- **Evidence:** `site/src/site.js:187–196, 266–271, 296–300` — `search.json` (51 entries,
  6,028 B raw / 1,241 B gzip) is prefetched in `requestIdleCallback` (1.5s timeout, with
  200ms `setTimeout` fallback); `rankSearch` is a linear scan over 51 items per input
  event; results re-render via `innerHTML` rebuild on each keystroke
  (`site/src/site.js:220–247`).
- **Consequence:** one extra ~1.2 KB gzip request per page view during idle, in exchange
  for an instant first keystroke — a good trade at this corpus size. Ranking and re-render
  costs are trivial (O(51) string scans); no debounce is needed at this size, and adding
  one would be speculative micro-optimization. No user-visible issue found. Note for the
  future: if the corpus grows by an order of magnitude, re-evaluate ranking cost and
  consider serving the index with a long cache lifetime.
- **Minor observation (preview-only):** `serve.ts` returns `application/octet-stream` for
  `.json` (`serve.ts:15`) and no compression; `fetch().then(r => r.json())` ignores the
  content type, so search works locally regardless. Production CDN behavior was not
  measured.
- **Acceptance criteria (observable, if anything changes):** first keystroke after modal
  open renders results without a network wait on warm cache; search index response is
  cacheable across pages. No change recommended today.

### F6 — Stale `dist` relative to `public` docs — **Priority: Medium (process, affects measurements and release)**

- **Evidence:** `diff -rq site/public site/dist` at review time:
  `public/docs/index.md` and `public/llms-full.txt` differ from `dist/` copies;
  dist timestamps (08:27) predate `public/llms-full.txt` (08:28). The build regenerates
  HTML, `search.json`, and `llms*.txt` from `public/docs` (`build.ts:736–751`).
- **Consequence:** the currently deployed-looking `dist/` output does not correspond to
  the current documentation source; any release from this tree would ship stale content,
  and performance measurements taken from `dist` (including this report's table) do not
  exactly describe the next build. At this corpus size the byte delta is trivial, but the
  invariant "dist is a pure function of public/ + src/" is broken right now.
- **Suggested correction:** run `bun run build` before the next publish and before
  re-measuring; consider a CI check that `dist` is fresh (rebuild + `git diff --exit-code`
  on generated outputs).
- **Acceptance criteria (observable):** after rebuild, `diff -rq site/public/docs
  site/dist/docs` is empty and `site/dist/llms-full.txt` is byte-identical to
  `site/public/llms-full.txt`.

### F7 — Verified-good practices (no action) — **Priority: Informational**

Recorded so the coordinator knows these were checked, not missed:

- **Fonts (beyond F1):** `display=swap` present; both font hosts preconnected
  (`build.ts:377–378`). The three-axis Fraunces request (`opsz,wght,SOFT`) is *not*
  over-broad: `SOFT` is actively used at values 0–50 and `opsz` 14–144 across
  `tailwind.css` (lines 61, 129, 133, 256, 383, 408, 424, 482, 556, 608, 692, 731, 737,
  743, 751, 770, 945), so no axis can be trimmed from the request.
- **Reduced motion:** full `prefers-reduced-motion` block kills animations, transitions,
  reveal hiding, and smooth scroll (`tailwind.css:1047–1055`); JS also gates the
  IntersectionObserver reveal on it (`site.js:16, 64`).
- **Scroll handlers:** reading progress is rAF-throttled with `{ passive: true }`
  (`site.js:29–35`); topbar shadow handler is state-change-gated and only writes
  `boxShadow` when crossing an 8px threshold (`site.js:430–441`). Two scroll listeners
  total; both cheap.
- **DOM size:** home ≈ 398 elements, doc pages ≈ 256–280 — small; no virtualization or
  delegation needed. Copy-button listeners are per-`pre` (≤4 per page).
- **Infinite animations:** `a7-bob` (home scroll hint) and `a7-blink` (terminal cursor)
  animate only `transform`/`opacity` on tiny elements (`tailwind.css:348–351, 674–682,
  1040`); compositor-friendly, and disabled under reduced motion.
- **Mobile layout:** single-column collapse, horizontal-scroll nav rail, `toc` hidden,
  huge type via `clamp()`, search input enlarged for touch, shortcut triggers hidden on
  phones (`tailwind.css:1058–1140`). Reasonable; the main mobile cost remains F2.
- **404:** 369-byte redirect stub with a plain fallback link (`dist/404.html`) — no
  asset cost.
- **HTML:** not minified, but gzip ≈ 3.2–4.4 KB/page; minifying would save under ~1 KB
  gzip per page — not worth build complexity.

---

## 4. Coverage limits and what this review did not verify

- No browser execution: no Lighthouse, no Core Web Vitals, no paint/waterfall timings,
  no font payload counts, no compositor-layer inspection. All load-order and costing
  statements are static analysis plus byte measurements, as flagged inline.
- Production GitHub Pages responses (compression, cache headers, HTTP version) were not
  fetched; the local preview server's behavior differs (no compression/cache).
- Only the pages present in the current `dist/` were measured; content drift (F6) means
  absolute byte sizes will shift on rebuild.
- No claim is made that F1–F6 are the complete set of performance issues.

## 5. Recommended order of work

1. F1 (self-host fonts / unblock critical path) — largest user-visible win, esp. slow networks.
2. F6 (rebuild dist; freshness check) — required before any release or re-measurement.
3. F2 (topbar blur on mobile) — main mobile scroll cost.
4. F3 (drop persistent `will-change`) — small, safe, zero-visual-change.
5. F4 (minify JS) — build hygiene.
