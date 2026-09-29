# Website Flash Review — Navigation, Search & Interaction

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- Reviewer: GLM-5.3-Flash website interactions specialist (external, advisory)
- Repo: /home/cx89/Projects/pl-dev/a7-py
- Scope (bounded): all internal hrefs/fragments, legacy URLs and not-found recovery,
  copy buttons, keyboard shortcuts, search ranking/body coverage/error states, TOC,
  paging, homepage terminal tabs, state restoration, JS failure behavior.
- No implementation changes. Shared `site/dist` was not rebuilt. No browser or
  nested agent CLI was launched.

## Method and evidence base

Static analysis of source and generated output, plus direct local HTTP against
`http://localhost:4173/a7-py/` (preview server already running; not started by me).

Inspected files:

- `site/README.md`, `site/package.json`, `AGENTS.md` (provided)
- `site/src/site.js` (full, 442 lines)
- `site/src/tailwind.css` (targeted sections: reveal, copy, modal, search, terminal, breakpoints)
- `site/scripts/build.ts` (full), `site/scripts/serve.ts` (full)
- `site/public/404.html`; `site/public/docs/*.md` frontmatter + headings
- Generated: `site/dist` — all 9 `index.html` pages crawled, `assets/search.json`,
  `assets/site.js` (diffed vs src), `404.html` (diffed vs public), `docs/*.md`, `llms*.txt` presence

Exact checks executed:

1. Crawled every `href`/`src` in all 9 generated pages: 85 unique internal targets,
   each HEAD-checked over local HTTP → 0 broken.
2. Fragment integrity: every in-page `#fragment` link matched against ids in the same
   page → 0 issues on doc pages. Every `search.json` fragment href matched against the
   target page's ids → 4 broken (Finding 1).
3. `rankSearch` logic reimplemented in Python against the real `search.json` and probed
   with representative terms (see Finding 2).
4. `diff site/src/site.js site/dist/assets/site.js` → identical (dist not stale).
5. `diff site/public/404.html site/dist/404.html` → identical.
6. Frontmatter `order` values across all 9 docs → 0–8, unique, sequential (pager is
   deterministic).
7. HTTP status checks: `/a7-py/` 200; `/a7-py/nonexistent-page/` → 200 with 404.html
   body (see Finding 9); `/a7-py/assets/search.json` 200.
8. `window.__A7_PAGE__` verified in generated HTML for `/language/` (prev=Start,
   next=Stdlib) and `/` (null/null).

**Untested browser behavior (not verified):** all click/keyboard/scroll dynamics,
the `404.html` redirect script, clipboard writes, in-browser search ranking, TOC
scrollspy motion, terminal tab switching, modal focus management, bfcache/back-state
restoration, fragment-scroll and reveal interplay, reduced-motion behavior. Browser
capture was blocked (in-app browser unavailable; local browser connection failed).
Playwright and competing browsers were not used, per instructions. Findings that
depend on these are labeled *static analysis*.

**Execution limitations:** a provider request-rate failure interrupted the review
mid-run; the same reviewer identity resumed it. No model/time/turn limits were
self-imposed. Web search and sub-agents were available but not needed; no nested CLI
orchestration was launched. Other reports in `docs/audits/2026-09-14/` were not read.

---

## Findings

### F1 — HIGH: Search index contains 4 dead homepage-fragment entries, and they are the first default results

- Evidence: `site/scripts/build.ts:706-728` — `searchIndex()` iterates **all** docs,
  including `index`, and emits one entry per level≥2 heading of
  `public/docs/index.md`, with hrefs like `/a7-py/#pipeline`. But the homepage body is
  produced by `homeHtml()` (`build.ts:451-655`), which never renders `doc.html`, so
  those anchors do not exist in `site/dist/index.html`. Verified mechanically:
  `search.json` entries `Pipeline→/a7-py/#pipeline`, `Read order→#read-order`,
  `Repository docs→#repository-docs`, `Public contract→#public-contract` — all 4 ids
  absent from the homepage HTML. Aggravating factor: with an empty query,
  `rankSearch` returns `items.slice(0, 12)` (`site/src/site.js:199`), and the index
  order puts the index page + these 4 headings **first** — so opening search shows
  the dead links as the top default results.
- Consequence: clicking any of these lands at homepage top with no scroll and no
  feedback; the most visible search results are broken.
- Suggested correction: skip `doc.slug === 'index'` heading entries in
  `searchIndex()` (or emit them only if the homepage actually renders those anchors).
- Acceptance criteria: no `search.json` entry whose `#fragment` is missing from its
  target page's HTML (mechanically checkable); empty-query default result list contains
  no dead anchors.

### F2 — HIGH: Search never matches body text; common terms return nothing

- Evidence: `site/src/site.js:198-218` — the haystack is
  `` `${item.title} ${item.section ?? ''} ${item.summary ?? ''}` `` only. The search
  index (`build.ts:706-728`) contains page-level entries and headings; no body prose.
  Reimplemented ranking against real `search.json`: `run_all_tests` → NO MATCHES,
  `recursion` → NO MATCHES, `usize` → NO MATCHES, `frontmatter` → NO MATCHES,
  `zig run` → NO MATCHES — all appear prominently in page bodies (e.g. homepage
  terminal panel, Status/Project pages). Yet the input placeholder promises
  "search docs and headings…" — headings are covered; "docs" (body) effectively is not.
- Consequence: docs lookup fails for any term not present in a heading; users must
  already know the section name to find content.
- Suggested correction: include stripped body text in page entries (e.g. a `body`
  field searched at lower weight), or add per-paragraph/per-block entries linking to
  the nearest heading; alternatively narrow the placeholder copy to what is actually
  indexed.
- Acceptance criteria: representative body-only terms (e.g. `run_all_tests`,
  `usize`, `recursion`) return the containing page/section in the top results.

### F3 — MEDIUM-HIGH: On mobile (≤640px) there is no touch entry point to search or shortcuts

- Evidence: `site/src/tailwind.css` inside `@media (max-width: 640px)` —
  `.shortcut-trigger { @apply hidden; }` (search `⌕` and shortcuts `?` buttons,
  generated at `build.ts:391-392`). The search modal opens only via those buttons or
  keyboard (`⌘K`/`/`, `site/src/site.js:336-388`). TOC is also hidden at this width
  (`.toc { @apply hidden; }`).
- Consequence: phone/tablet users (no hardware keyboard) cannot open search or the
  shortcuts dialog at all — search is effectively desktop-only.
- Suggested correction: keep the search trigger visible in the mobile topbar (or add
  a "Search" row to the mobile nav strip).
- Acceptance criteria: at a 375px-wide viewport a visible control opens the search
  modal (requires browser verification).

### F4 — MEDIUM: Legacy not-found recovery breaks when the dead URL carried a query string or fragment, and unknown paths fall back silently

- Evidence: `site/public/404.html:9` builds
  `from = path + location.search + location.hash`. `site/src/site.js:8-14` then does
  `clean.split('/')[0]` and compares against the hardcoded `known` list: for
  `from=/language/?x=1` the first segment is `language/?x=1`, which is not in
  `known`, so **no redirect happens** — the user stays on the homepage with
  `?from=...` still in the address bar. (Verified by code path analysis; the redirect
  script itself is browser-executed and untested.) Additionally, unknown paths that
  pass the `known` filter get a silent homepage fallback — no "page not found"
  message, no 404 affordance.
- Consequence: legacy deep links with query/hash (common for old router URLs) do not
  recover to the intended page; users get no signal that their target page was not
  found.
- Suggested correction: parse only the path portion, e.g.
  `new URL(from, location.origin).pathname` before the `known` check; render a
  visible "page not found — showing overview" notice when `from` is present or
  unknown.
- Acceptance criteria: a dead `/a7-py/language/?x=1#frag` URL (via 404) lands on
  `/a7-py/language/`; an unknown path shows an explicit not-found notice on the
  homepage (browser verification required).

### F5 — MEDIUM: Same-page search results keep the modal open with body scroll locked *(static analysis)*

- Evidence: search results are plain anchors (`site/src/site.js:228-247`) and Enter
  uses `location.assign(sel.getAttribute('href'))` (`site.js:286-291`). Nothing
  closes the modal on navigation. For a result on the **current** page (e.g. being on
  `/language/` and picking `Exit codes` → `/a7-py/language/#exit-codes`, present in
  the real `search.json`), the browser performs a same-document fragment navigation —
  no reload — so `[data-modal]` keeps `data-open` and
  `document.body.style.overflow = 'hidden'` (`site.js:128-129`) persists.
- Consequence: user sees the page jump behind a still-open, scroll-locked modal; they
  must press Esc manually. Cross-page results are unaffected (full reload).
- Suggested correction: close modals when a result is clicked/entered, or add a
  `hashchange` listener that calls `closeAllModals()`.
- Acceptance criteria: selecting a same-page heading result closes the search modal
  and restores page scrolling (browser verification required).

### F6 — MEDIUM-LOW: A failed search-index fetch is cached permanently and misreported as "no matches"

- Evidence: `site/src/site.js:187-196` — `loadSearchIndex()` caches
  `searchIndexPromise`, whose `.catch(() => [])` resolves to `[]`; the resolved
  (empty) value is then cached in `searchIndex` for the life of the page.
  `renderSearch([])` shows the "no matches" message (`site.js:223-226`) for every
  query.
- Consequence: one transient network failure (or a bad deploy missing
  `assets/search.json`) permanently disables search for the session, and the error
  state is indistinguishable from a genuine empty result — a misleading error state.
- Suggested correction: only cache successful loads (reset `searchIndexPromise` on
  failure) and add a distinct error/retry message instead of "no matches" when the
  index failed to load.
- Acceptance criteria: with `/a7-py/assets/search.json` forced to fail, the UI shows
  an error/retry affordance rather than "no matches", and a subsequent attempt can
  succeed without reloading the page.

### F7 — LOW-MEDIUM: Copy buttons are invisible until hover; no touch affordance

- Evidence: `site/src/tailwind.css:828-835` — `.copy { opacity: 0; ... }` revealed
  only by `pre:hover .copy, .copy:focus-visible`. The button is created for every
  `pre code` by `site/src/site.js:39-61`. `navigator.clipboard` requires a secure
  context (HTTPS / localhost) — fine on GitHub Pages and local preview; the
  `catch` → "failed" path handles insecure contexts. Opacity does not remove the hit
  target, so touch users can tap an invisible button in a code block's top-right
  corner with zero visual affordance; keyboard users can tab to it (focus-visible
  reveals it), adding every code block to the tab order.
- Consequence: undiscoverable copy on touch devices; accidental copies from blind
  taps.
- Suggested correction: make `.copy` always visible under `@media (hover: none)`.
- Acceptance criteria: on a `hover: none` device the copy control is visible on
  every code block (browser verification required).

### F8 — LOW: Keyboard shortcut and tab-pattern details

- Evidence and notes (all static analysis unless stated):
  - `site/src/site.js:407-409` — duplicate `if (k === 'g')` block is unreachable
    (the same condition returns at `site.js:372-376`). Dead code.
  - `site/src/site.js:337` — comment says Cmd/Ctrl+K applies "but not inside the
    search input itself", but the handler fires there too (benign: re-opens/refocuses
    the same modal). Comment/code mismatch.
  - Modals have no focus trap (`site.js:116-176`); Tab can move focus into the
    background page while `aria-modal="true"` is set.
  - Homepage terminal tabs (`build.ts:569-573`): `role="tab"` buttons without
    `aria-controls`/`id` linkage and without arrow-key tablist behavior; panels
    switch via click only (`site.js:413-427`). Tab state is not persisted (URL or
    storage); back-navigation after switching restores the default `compile` tab on
    a fresh load (bfcache restores DOM, untested).
  - JS-failure degradation: without JS the site is fully readable — TOC links,
    pager, nav, and the first terminal panel work; terminal panels 2–3 carry the
    `hidden` attribute in generated HTML (`build.ts:586,594`) so they are
    unreachable without JS; the topbar `⌕`/`?` buttons do nothing (no non-JS
    fallback). Acceptable for a no-framework static site; recorded as behavior, not
    necessarily a defect.
  - `known` legacy slugs are hardcoded in `site/src/site.js:11` and must be kept in
    sync with `DOC_ORDER` in `site/scripts/build.ts:24-34`; adding a doc page
    without updating `known` silently breaks legacy deep-link recovery for it.
    Consider deriving `known` from a shared generated constant.
- Suggested correction: remove the dead block; add a focus trap; complete the ARIA
  tabs pattern or drop the tab roles; generate the legacy-slug list from
  `DOC_ORDER`.
- Acceptance criteria: no unreachable shortcut branch; focus stays within an open
  modal while tabbing; arrow keys move between terminal tabs; new doc pages recover
  legacy deep links without a second hand-edited list.

### F9 — LOW: Local preview serves the 404 page with HTTP 200

- Evidence: `site/scripts/serve.ts:28-29` — when a file is missing it serves
  `404.html` via `new Response(Bun.file(file), ...)` with the default status 200
  (verified: `curl /a7-py/nonexistent-page/` → 200). GitHub Pages will serve the
  same file with a real 404 status. A missing asset (e.g. `assets/site.js`) is also
  served as HTML with 200 locally, which can mask broken asset references during
  local verification.
- Consequence: local preview cannot distinguish OK from not-found; local-only
  verification overstates health.
- Suggested correction: return status 404 when serving the `404.html` fallback in
  `serve.ts`.
- Acceptance criteria: `curl -i http://localhost:4173/a7-py/missing` returns HTTP
  404 locally.

---

## Verified-good (independent invariants observed)

- All 85 unique internal `href`/`src` targets across the 9 generated pages resolve
  over local HTTP (0 broken), including the 8 raw markdown twins `/a7-py/docs/*.md`,
  `llms.txt`, `llms-full.txt`, `sitemap.xml`, and the system-map SVG.
- All in-page TOC fragment links on doc pages match existing heading ids (0 issues);
  TOC exists on all 8 doc pages (every doc has level≥2 headings).
- Pager (`[`, `]`, footer links) is consistent: frontmatter orders are unique 0–8;
  `window.__A7_PAGE__` prev/next matches the generated `.doc-pager` for the checked
  page; homepage correctly has null prev/next.
- `dist/assets/site.js` is identical to `src/site.js`; `dist/404.html` identical to
  `public/404.html` (dist not stale).
- Search escape behavior is layered sensibly in code: first Esc clears the query,
  second closes the modal (`site.js:344-353`); result HTML is escaped via
  `escapeHtml` (`site.js:262-264`), limiting injection from doc titles.
- Scroll-reveal is JS-safe: `[data-reveal]` (opacity:0) is only ever set by JS, so
  no-JS users never see hidden content; `prefers-reduced-motion` forces
  `[data-reveal] { opacity: 1 }` (`tailwind.css:1053`).
- `.terminal-panel[hidden] { display: none; }` is explicitly enforced in CSS
  (`tailwind.css:655`), so the `hidden` attribute cannot be overridden by the
  panel's display rules.

## Coverage limits and non-claims

- No browser execution was possible (capture blocked per coordinator): every
  interactive dynamic (redirects, clipboard, scrollspy, tabs, focus, bfcache,
  reduced motion) is code-path analysis only and must be confirmed in a real browser
  before acceptance.
- Ranking was probed via a faithful reimplementation of `rankSearch` over the real
  `search.json`, not in-browser; edge cases in event ordering under real input
  cadence are untested.
- Checks were run against the existing `site/dist` (verified in sync for `site.js`,
  `404.html`); CSS/HTML drift beyond those diffs was not re-derived from a fresh
  build (shared dist was not rebuilt, per instructions).
- This review does not claim to enumerate all interaction issues and does not
  constitute acceptance.
