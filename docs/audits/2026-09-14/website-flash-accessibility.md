# Website Accessibility Review — GLM-5.3-Flash (independent pass)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- **Date:** 2026-09-14
- **Reviewer:** GLM-5.3-Flash, external and advisory. No implementation changes.
- **Scope:** accessibility only: semantic HTML, landmarks, headings and lists,
  names and labels, keyboard navigation and focus, modal containment and
  restoration, search combobox/listbox behavior, tabs, skip links, contrast,
  zoom, reduced motion, no-JS resilience and touch targets.
- **Method:** source-based static analysis only. Browser capture was blocked
  (in-app browser unavailable, local browser connection failed, Playwright not
  invoked per constraints). The local preview at `http://localhost:4173/a7-py/`
  served the current `site/dist` byte-for-byte (`dist/index.html` md5
  `292d1b4b…` identical to the served response; `dist/assets/site.js` md5
  identical to `src/site.js`). No rendering, DOM-query or screen-reader
  verification was performed. Contrast values are computed with the WCAG 2.x
  relative-luminance formula from design tokens in `site/src/tailwind.css`
  against their known solid backgrounds.
- **Standards:** WCAG 2.2 (A/AA criteria cited per finding) and the WAI-ARIA
  Authoring Practices (APG) patterns for dialog, combobox and tabs.
- **Independence:** no other review reports in `docs/audits/2026-09-14/` were read.

## Files inspected

| File | Notes |
| --- | --- |
| `AGENTS.md`, `site/README.md` | Required context |
| `site/scripts/build.ts` (754 lines) | Static site generator; emits all page HTML, modals, tabs, search index |
| `site/src/site.js` (442 lines) | All client JS: modals, search, shortcuts, tabs, copy, reveal, scrollspy |
| `site/src/tailwind.css` (1140 lines) | Design tokens, focus styles, contrast-relevant colors, media queries |
| `site/public/404.html` | JS redirect page with fallback link |
| `site/scripts/lint.ts` | Confirmed lint covers doc presence/legacy refs only — **no accessibility checks exist in tooling** |
| `site/dist/` (index.html, start/index.html, assets/site.css, assets/site.js) | Spot-verified built output matches source (greps for `aria-current`, `tabindex`, `role=`, `:focus-visible`, `prefers-reduced-motion`) |
| `site/public/docs/*.md` | Confirmed exactly one `#` H1 per doc (so the hidden-prose-H1 dedup is safe) |

Not inspected: `site/scripts/serve.ts` internals beyond build relevance,
`site/public/a7-system-map.svg` internals (loaded via `<img alt>`, so internal
text is not exposed either way), Google Fonts endpoints, the GitHub Pages
deployment itself.

## Findings summary

| ID | Priority | Area | One-line summary |
| --- | --- | --- | --- |
| F1 | High | Skip links | No bypass-blocks mechanism anywhere |
| F2 | High | Modal containment | Dialogs have no focus trap; Tab escapes while `aria-modal="true"` hides background from AT |
| F3 | High | Focus visible | Search input (the modal's primary element) has **no visible focus indicator** |
| F4 | High | Search combobox | Combobox/listbox pattern not implemented; no state, count, or selection announcements |
| F5 | High | Feature parity | Search entry point entirely hidden at ≤640px — search unusable on touch |
| F6 | High | No-JS resilience | "release" and "agents" terminal panels are permanently hidden without JS (content loss) |
| F7 | Medium | Non-text contrast | Global focus ring is 2.35:1 on light paper surfaces (< 3:1) |
| F8 | Medium | Text contrast | 9 computed text/background failures, all small label text (2.81–4.08:1, need 4.5:1) |
| F9 | Medium | Tabs | `tablist`/`tab` roles without tabpanels, `aria-controls`, or arrow-key support |
| F10 | Medium | Keyboard | Scrollable regions (code blocks, tables, search results) not keyboard-scrollable — zero `tabindex` in dist |
| F11 | Medium | Status messages | Copy button success/failure not announced; static `aria-label` masks the visible state text |
| F12 | Medium | Label in Name | Close buttons: visible text "esc" not contained in accessible name "Close search/shortcuts" |
| F13 | Medium | State exposure | Active nav page/TOC state is class-only; no `aria-current` (0 occurrences in dist) |
| F14 | Medium | Landmarks | No `contentinfo` landmark; `.quick` nav unnamed |
| F15 | Medium | Target size | Several controls likely < 24×24 CSS px with no spacing exception (verify) |
| F16–F24 | Low | Misc | `scope` on table headers, Esc-behavior vs hint mismatch, dead code, hidden TOC on mobile, etc. |

---

## High-priority findings

### F1 — No skip link or other bypass mechanism (WCAG 2.4.1 Bypass Blocks, A)

- **Evidence:** `site/scripts/build.ts:382-400` — page shell renders
  `<header class="topbar">` then `<main>`; no skip link exists in the template,
  in `modalsHtml()` (build.ts:288-347), or anywhere in `dist/` (`grep skip` in
  CSS/HTML: 0 hits).
- **Consequence:** Keyboard users must tab through 7 topbar stops (brand, 4
  quick links, 2 buttons) plus the 9-link sidebar nav (~16 tab stops) before
  reaching article content on every doc page. Repeated on every navigation.
- **Suggested correction:** Emit `<a class="skip-link" href="#main-content">Skip
  to content</a>` as the first element inside `<body>` in `pageHtml()`, give
  `<main>` a matching `id`, and add a visually-hidden-until-focused style in
  `src/tailwind.css` (high-contrast, ≥3:1, respects `prefers-reduced-motion`).
- **Acceptance criteria:**
  1. The skip link is the first tab stop on every page.
  2. Activating it moves *focus* (not merely scroll position) into `<main>`.
  3. It is visible when focused on both dark and light page regions.

### F2 — Modals have no focus containment (WCAG 2.4.3 Focus Order; ARIA APG dialog pattern)

- **Evidence:** `site/src/site.js:123-151` — `openModal` moves focus in and
  `closeModal` restores it (good), but there is no Tab-cycle trap and no
  `inert`/`aria-hidden` on background content. Modals declare
  `aria-modal="true"` (`build.ts:293, 311`).
- **Consequence:** With a dialog open, Shift/Tab walks straight through the
  backdrop into the obscured page (topbar, sidebar, article links), while
  `aria-modal="true"` tells screen readers the background is *not* there — a
  keyboard/AT mismatch of the class covered by Technique F85. Sighted keyboard
  users lose their place behind an opaque overlay.
- **What already works (do not regress):** focus restoration
  (`site.js:150`), initial focus with rAF retry (`site.js:130-142`), Esc close
  (`site.js:344-353`), backdrop-click close (`site.js:162-165`).
- **Suggested correction:** While a modal is open, set `inert` on background
  siblings (or implement a Tab trap that cycles within `.modal-card`), then
  remove on close. Keep the existing restoration logic.
- **Acceptance criteria:**
  1. With search or shortcuts open, Tab/Shift+Tab cycles only among that
     dialog's focusable elements.
  2. Background links are not reachable by keyboard or pointer while open.
  3. Closing restores focus to the trigger (already true — must remain).
  4. VoiceOver/NVDA does not expose background content while open (browser
     verification).

### F3 — Search input has no visible focus indicator (WCAG 2.4.7 Focus Visible, AA)

- **Evidence:** `site/src/tailwind.css:943-953` applies `outline-none` to
  `.search-input-row input`. In the built CSS the rule
  `.search-input-row input{…outline-style:none}` has specificity (0,1,1) and
  therefore **permanently overrides** the global focus ring
  `:focus-visible{outline:2px solid var(--color-oxide-300)…}` (specificity
  (0,1,0), tailwind.css:84-87), regardless of source order.
- **Consequence:** `openModal` focuses this input by design
  (`site.js:130-137`), so the very first thing a keyboard user does in the
  search modal happens on an element with no focus indicator — only the text
  caret. A caret is a text-insertion point, not a focus indicator.
- **Suggested correction:** Replace `outline-none` with an explicit
  `:focus-visible` style for the input (e.g., 2px bottom border in
  `--color-oxide-300` on the dark modal card at 6.5:1, or re-enable the
  outline for this element).
- **Acceptance criteria:**
  1. Focusing the search input shows a non-color-only indicator with ≥3:1
     contrast against `--color-graphite-850`.
  2. Tabbing from the input to a result and back shows a visible indicator
     both times.

### F4 — Search is a combobox/listbox in name only (WCAG 4.1.2 Name, Role, Value; ARIA APG combobox pattern)

- **Evidence:**
  - `build.ts:300` — the input has `aria-label="Search"` but no
    `role="combobox"`, `aria-expanded`, `aria-controls`, or
    `aria-activedescendant` (grep across dist HTML+JS: 0 occurrences of any of
    these attributes).
  - `build.ts:302` — `role="listbox"` on an always-empty `<div>`; the listbox
    has no accessible name.
  - `site.js:228-247` — results are `<a>` elements given `role="option"`,
    which *replaces* their link semantics while they remain natively
    focusable — focusable options outside an `aria-activedescendant` scheme,
    invisible to the pattern's contract.
  - `site.js:273-292` — arrow/Enter handling exists on the input (good bones).
  - `build.ts:303` — the "no matches" element is a plain `div`; no live region
    anywhere in the search UI.
- **Consequence:** Screen-reader users get no announcement that the popup
  opened, how many results matched, which option is selected, or that a search
  returned nothing. The `aria-selected` bookkeeping in `site.js:233, 249-260`
  is not perceivable without `aria-activedescendant`/focus management.
- **Suggested correction:** Adopt the APG combobox pattern: `role="combobox"`
  + `aria-expanded` + `aria-controls` + `aria-activedescendant` on the input;
  options as non-focusable elements with `role="option"` and stable `id`s
  (navigation stays via the input's arrow handling; navigate on Enter as
  today); label the listbox (`aria-labelledby` the dialog title); add a
  visually-hidden `role="status"` region announcing "N results" / "no
  matches". Alternatively drop the ARIA roles and ship a plain list of links —
  the current half-pattern is worse than either.
- **Acceptance criteria:**
  1. Opening search announces the dialog and the input's expanded state.
  2. Typing announces result availability (count or "no matches") without
     moving focus.
  3. Arrow keys announce the selected option's full text; Enter activates the
     announced destination.

### F5 — Search is unreachable on small screens (feature parity / 1.3.x robustness)

- **Evidence:** `tailwind.css:1088` (640px media query)
  `.shortcut-trigger { @apply hidden; }` removes the only search button; the
  alternate entry points are keyboard-only (`/`, Cmd/Ctrl+K,
  `site.js:336-341, 384-388`), which touch users cannot invoke.
- **Consequence:** At phone widths the search feature cannot be opened at all;
  touch/mobile users silently lose a primary navigation tool.
- **Suggested correction:** Keep the search trigger visible in the mobile
  topbar (it can move into a wrapped row, as `.quick` already does at
  tailwind.css:1087).
- **Acceptance criteria:** At 320–640px viewport width a reachable control
  (≥24×24 CSS px per F15) opens the search modal.

### F6 — No-JS: release/agents terminal panel content is unreachable (content loss, cf. WCAG 2.1.1 robustness)

- **Evidence:** `build.ts:586` and `build.ts:594` — the "release" and "agents"
  `[data-tab-panel]` elements carry the `hidden` attribute in the *static*
  HTML; the only code that removes it is the JS click handler
  (`site.js:413-427`).
- **Consequence:** Without JavaScript, the release-gate transcript and the
  agent `curl` examples (substantive documentation content, not decoration)
  are permanently `display:none`. This is content loss, not merely lost
  interactivity. The other JS-dependent features degrade acceptably (copy
  buttons simply don't exist; modals are never open).
- **Suggested correction:** Remove `hidden` from the static markup and let
  `site.js` add it during initialization (progressive enhancement), so
  no-JS/all-panels is the baseline. Or convert to `<details>`/`<summary>`.
- **Acceptance criteria:** With JavaScript disabled, the text of all three
  terminal panels is readable in document order.

---

## Medium-priority findings

### F7 — Focus ring fails non-text contrast on light surfaces (WCAG 1.4.11 Non-text Contrast, AA)

- **Evidence:** `tailwind.css:84-87` sets the sole focus indicator to
  `--color-oxide-300` (#e07b62). Computed contrast: **2.35:1** on
  `--color-paper-100` (#ede6d3) — below 3:1. (On `--color-graphite-900` it is
  6.47:1 — fine.) Every doc-page link, button, pager, and heading anchor sits
  on the paper surface.
- **Consequence:** Focus position is effectively invisible for
  low-vision users on the article, route board, preview, and footer of the
  home page — the majority of the site's interactive surface.
- **Suggested correction:** Use a darker ink on light contexts (e.g.,
  `--color-oxide-700` #8f2c18 = 6.6:1 on paper) via a context class on
  `.paper`/`.route-board`/`.preview`, or add a contrasting outline shadow
  behind the ring.
- **Acceptance criteria:** Every focus indicator ≥3:1 against its adjacent
  colors in both dark and light contexts (spot-check: nav link, prose link,
  pager, copy button, footer link).

### F8 — Text contrast failures (WCAG 1.4.3 Contrast (Minimum), AA) — computed values

All flagged instances are small text (< 18pt / 14pt bold), so 4.5:1 is required.

| Foreground / context | Where (source) | Computed |
| --- | --- | --- |
| `muted-500` on `paper-100` | `.paper::before` running header, `tailwind.css:238`; `.doc-pager small`, `tailwind.css:878` | **3.12:1** |
| `muted-500` on `paper-200` | `.route-group h3`, `tailwind.css:489` | **2.81:1** |
| `oxide-600` on `graphite-950` | `.site-footer-nav h4`, `tailwind.css:703` | **3.28:1** |
| `oxide-600` on `graphite-850` | `.shortcuts-group h3`, `tailwind.css:993`; `.search-result span` kind label, `tailwind.css:966` | **3.00:1** |
| `oxide-600` on `#14120f` | `.plate` hero eyebrow, `tailwind.css:266` | **3.13:1** |
| `oxide-600` on `#0f0e0c` | terminal-intro `.eyebrow` (§04), `tailwind.css:723` | **3.23:1** |
| `oxide-600` on topbar (hover state) | `.quick a:hover`, `tailwind.css:162` | **3.17:1** |
| `calibration-600` on `graphite-950` | `.t-ok` terminal "passed/ok", `tailwind.css:666` | **4.08:1** |
| `muted-500` on selected-row blend | `.search-result em` (tailwind.css:975) over the hover/selected background `rgba(178,58,31,.12)` (tailwind.css:962-963) | **4.27:1** when highlighted |

For reference, pairs that pass: `.eyebrow`/`.route-num` oxide-600 on paper
(4.79:1), `.nav-link`/`.toc` muted-500 on graphite-900 (4.86:1), prose body
(11.2:1), prose links oxide-700 (6.6:1), summary/route `#544b3e` (6.9:1).
Contrast on translucent backdrops (topbar `rgba(17,16,14,.82)`, modal
backdrop) was approximated; exact sampling requires a browser (see
verification section).

- **Consequence:** Group headings, footers' column headings, search-result
  metadata, terminal success text, and the article's running header are below
  AA for low-vision users. These are informational labels, not decoration.
- **Suggested correction:** Either darken the oxide/muted text tokens used on
  dark surfaces (e.g., use `oxide-300` for text on graphite: 6.5:1) or
  lighten the muted token used on paper (e.g., `#6f6450`-range computed ≥4.5:1
  on paper-100/200); verify each pair after retokening.
- **Acceptance criteria:** Every text/background pair used for rendered text
  ≥4.5:1 (3:1 only for ≥24px or ≥18.66px bold), including hover/selected
  states; re-check with the contrast computations in CI or a documented
  token table.

### F9 — Terminal tabs use tab roles without the tabs pattern (WCAG 4.1.2; ARIA APG tabs)

- **Evidence:** `build.ts:569-573` — `role="tablist"`, three `role="tab"`
  buttons with `aria-selected`; no `id`/`aria-controls` linking tabs to
  panels; panels (`build.ts:575-602`) have no `role="tabpanel"`, no
  `aria-labelledby`, no `tabindex="0"`. `site.js:413-427` handles click only;
  no arrow-key roving focus.
- **Consequence:** Assistive tech announces "tab, selected" and then finds no
  tabpanels; keyboard users expect (per APG) Left/Right arrow movement that
  doesn't exist. The ARIA contract is half-implemented, which is less
  accessible than no roles at all.
- **Suggested correction:** Either (a) complete the pattern — give each tab an
  `id` + `aria-controls`, panels `role="tabpanel"` + `aria-labelledby` +
  `tabindex="0"`, roving `tabindex` with Left/Right/Home/End — or (b) drop the
  tab roles and render three plain stacked sections or `<details>` blocks.
- **Acceptance criteria:** SR announces "compile tab, selected, 2 of 3";
  arrow keys switch tabs per APG (or roles removed and content is plain
  sections); each panel's name comes from its tab.

### F10 — Scrollable regions are keyboard-unreachable (WCAG 2.1.1 Keyboard, A)

- **Evidence:** `grep -c tabindex` across dist HTML + JS: **0**. Scrollable
  containers: `.prose pre` (`overflow-x-auto`, tailwind.css:807), `.prose
  table` (`display:block; overflow-x:auto`, tailwind.css:846-850),
  `.search-results` (`overflow-y`, tailwind.css:955-958), `.terminal-panel`
  (`overflow:auto`, tailwind.css:651-654), mobile `.sidebar`
  (`overflow-x:auto`, tailwind.css:1063, 1090).
- **Consequence:** Keyboard-only users cannot scroll wide code blocks or
  tables to read clipped content; they cannot scroll the search result list.
- **Suggested correction:** Add `tabindex="0"` plus an accessible name/role
  (e.g., `role="region"` + `aria-label`) to scrollable containers — either
  statically in `build.ts` for `pre`/`table` wrappers or via a small
  enhancement pass in `site.js`.
- **Acceptance criteria:** Each container that actually clips content is
  focusable, scrollable via keyboard, and named; containers that never clip
  are untouched (avoid noise).

### F11 — Copy-button status not announced; static aria-label hides state (WCAG 4.1.3 Status Messages, AA)

- **Evidence:** `site.js:42-58` — `button.textContent` cycles
  `copy → copied → failed`, while `aria-label="Copy code"` (site.js:46) is
  never updated. Per the ARIA name computation the `aria-label` overrides the
  visible text, so the state change is invisible to AT even on re-focus, and
  there is no live region.
- **Consequence:** Screen-reader users receive no confirmation of copy
  success or failure (failure path exists at site.js:52-54).
- **Suggested correction:** Drop the static `aria-label` (visible text "copy"
  is a sufficient accessible name; "Copy code" already contains it for
  2.5.3) and announce the outcome via `role="status"` or by updating the
  button's name text; ensure the failure path is equally announced.
- **Acceptance criteria:** Activating copy announces success ("copied") or
  failure ("failed") without moving focus; the accessible name always
  contains the visible label.

### F12 — Dialog close buttons: visible "esc" not in accessible name (WCAG 2.5.3 Label in Name, A)

- **Evidence:** `build.ts:297` and `build.ts:315` — visible text `esc`, but
  `aria-label="Close search"` / `"Close shortcuts"`.
- **Consequence:** Speech-control users saying "click esc" get no match;
  name/visible-label mismatch.
- **Suggested correction:** `aria-label="Close search (Esc)"` or visible
  "close · esc".
- **Acceptance criteria:** Each close button's accessible name contains its
  visible text.

### F13 — Current-page state is class-only (1.3.1 Info and Relationships; programmatic state)

- **Evidence:** `build.ts:259-262` — active sidebar link gets only a CSS
  `active` class; TOC active link likewise (site.js:99-101). `grep -c
  aria-current` in dist: **0**.
- **Consequence:** Screen-reader users cannot tell which page/section is
  current while navigating the nav or TOC; only the visual style differs.
- **Suggested correction:** `aria-current="page"` on the active sidebar link
  in `navHtml()`; `aria-current="location"` (or `"true"`) on the TOC active
  link in `setActive()`.
- **Acceptance criteria:** The active nav link is exposed as "current page"
  by AT on every doc page; the TOC's active entry is exposed as current.

### F14 — Landmark structure: no contentinfo; unnamed quick nav

- **Evidence:**
  - `build.ts:605` — the site footer `<footer aria-label="Site footer">` is
    rendered **inside** `<main class="home">`; per HTML+AAM it only maps to
    `contentinfo` when not nested in `main`/`article`/`aside`/`nav`/`section`.
    The doc pages' only footer (`build.ts:438-442`) sits inside `<article>`.
    Net: the site exposes **no contentinfo landmark on any page**.
  - `build.ts:386` — `<nav class="quick">` has no accessible name (the other
    three navs are named; verified by grep).
- **Consequence:** SR users landmark-jumping to "footer information" find
  nothing; two sibling navs, one unnamed, are ambiguous.
- **Suggested correction:** Move the home site footer outside `</main>` (it
  is already visually last), or add explicit `role="contentinfo"`; add
  `aria-label="Quick links"` to `.quick`; consider `<nav aria-label="Docs
  sections">` semantics for the sidebar `aside` (its content is pure
  navigation).
- **Acceptance criteria:** SR landmark list on the home page and any doc page
  contains banner, main, at least one named navigation, and contentinfo; no
  two landmarks share an unnamed identity.

### F15 — Touch/pointer targets likely below 24×24 CSS px (WCAG 2.5.8 Target Size (Minimum), AA) — static estimate, measure in browser

- **Evidence (CSS-derived sizes):**
  - `.modal-card header button` — `font-size: 14px`, no padding
    (tailwind.css:925-928) → ≈17px tall.
  - `.site-footer-nav a` — 12px mono text, `gap-2` (8px) between stacked
    links (tailwind.css:706-711) → ≈15px tall, 8px spacing (spacing exception
    needs 24px).
  - `.quick a` — 12px uppercase text (tailwind.css:147-151) → ≈16px tall,
    18px horizontal gaps (`gap-[18px]`).
  - `.terminal-tabs button` — 11px text, `py-1.5` (tailwind.css:634-637) →
    ≈25px, borderline.
  - Controls that pass: `.shortcut-trigger` (28×28, tailwind.css:166),
    `.nav-link` (`min-h-9` = 36px), `.doc-pager a`, `.route-row`,
    `.hero-actions a`, `.copy` (≈25×45).
- **Consequence:** Modal close, footer links, and quick links are
  hard-to-hit targets on touch; 2.5.8 fails where spacing doesn't rescue it.
- **Suggested correction:** Extend hit areas with padding (visual size can
  stay): e.g., min-height 24px + inline padding on footer/quick links and the
  modal close button.
- **Acceptance criteria:** Every interactive target ≥24×24 CSS px or
  separated from neighbors by ≥24px, measured at 320px and 390px widths in a
  real browser.

---

## Low-priority findings

- **F16 — Table header cells lack `scope`** (1.3.1): `build.ts:120` emits
  `<th>` in `thead` without `scope="col"`. Add it in `closeTable()`.
- **F17 — Esc behavior contradicts the visible hint** (consistency/expected
  behavior): `site.js:344-349` makes the first Esc clear a non-empty query;
  the search footer advertises "esc close" (`build.ts:307`). Either make Esc
  close immediately or update the hint to "esc clear · esc close".
- **F18 — `role="document"` on `.modal-card`** (`build.ts:294, 312`) is an
  unnecessary role change inside a dialog and can alter SR reading mode;
  remove it.
- **F19 — `aria-label` on a generic `<p>`**: `build.ts:466`
  (`<p class="poster-pipeline" aria-label="A7 pipeline">`) — ARIA labels are
  not exposed on generic elements; harmless (text is visible) but misleading.
  Remove or use a figure/labelled group if naming matters.
- **F20 — Dead code**: `site.js:407-409` duplicates the `g` chord branch
  already handled at `site.js:372-376`; unreachable. Hygiene only.
- **F21 — TOC hidden entirely ≤640px** (`tailwind.css:1092`): in-page section
  navigation is lost on small screens with no replacement; consider a
  `<details>`-based TOC above the article.
- **F22 — No `<noscript>` affordance**: the search button renders inert
  without JS (`build.ts:391`; all handlers in `site.js`). A `<noscript>`
  hint pointing to `/docs/*.md` (or hiding the button) avoids a dead control.
- **F23 — Heading anchors wrap the entire heading text** (`build.ts:169`):
  every heading appears in SR link lists as a link to itself. Common pattern,
  but if SR verification shows noise, switch to an `aria-hidden` "§" anchor
  or leave as-is by design.
- **F24 — `body { overflow-x: hidden }`** (`tailwind.css:63`) masks horizontal
  reflow overflow instead of allowing scroll; if any child overflows at
  320px/400% zoom it is clipped, not scrollable (1.4.10 risk). Verify in
  browser; if clean, no change needed.
- **F25 (info) — Search input visible label**: labeled only via placeholder +
  `aria-label` (3.3.2 passes programmatically; the wrapping `<label>` has no
  text content). A persistent visible cue exists (the ⌕ glyph is CSS content,
  not announced). Acceptable; note for visual-label best practice.

---

## Invariants that already hold (verified in source; do not regress)

- `lang="en"`, unique per-page `<title>`, meta description, canonical
  (`build.ts:368-376`).
- Exactly one visible `<h1>` per page; each markdown doc's own `#` H1 is
  hidden by `.prose h1 { hidden }` (`tailwind.css:745`) and the corpus check
  confirms one H1 per file, so no real sections are hidden; heading IDs are
  de-duplicated (`build.ts:164-167`).
- Real list/heading semantics from the markdown renderer (ul/li, h1–h3,
  figure/figcaption, dl/dt/dd in poster stats and shortcuts).
- Dialogs: `role="dialog"` + `aria-modal` + `aria-labelledby`; focus-in with
  rAF retry, focus restore, Esc, backdrop click (`site.js:123-169`,
  `build.ts:293-346`).
- `prefers-reduced-motion` is thoroughly respected: global animation/transition
  kill switch + `scroll-behavior:auto` (`tailwind.css:1047-1055`), reveal
  observer skipped and smooth-scroll downgraded in JS (`site.js:16, 64, 366,
  403`). The looping blink/bob animations are covered by the kill switch.
- Scroll-reveal never hides content without JS: `data-reveal` is only applied
  by JS (`site.js:78-81`), so the `[data-reveal]{opacity:0}` rule
  (`tailwind.css:1012`) never applies in no-JS.
- Decorative elements correctly `aria-hidden`: progress bar, registration
  marks, poster meta, scroll cue, ticker, terminal cursor, pipeline arrows
  (`build.ts:383, 454-462, 492, 584, 640`).
- The chord indicator is a proper `role="status" aria-live="polite"` region
  (`build.ts:290`; `site.js:305-316`).
- The single content image has meaningful alt text (`build.ts:495`).
- 404 page degrades to a plain accessible link without JS
  (`public/404.html:11`).
- `color-scheme: dark` declared; `scroll-padding-top` compensates the sticky
  topbar for anchor jumps (`tailwind.css:36, 47`).

## Required browser / screen-reader verification (could not be concluded from source)

1. **Focus order & traps** (F2): confirm Tab containment in both modals with
   real focus events; confirm VoiceOver/NVDA honors `aria-modal` containment.
2. **Search announcements** (F4, F11): VO/NVDA pass over open → type →
   arrow → Enter; confirm result-count and "no matches" announcements after
   fixes.
3. **Tabs semantics** (F9): SR announcement of tab/tabpanel relationship;
   arrow-key behavior.
4. **Zoom & reflow** (F24, F5, F21, F15): 320px viewport / 400% zoom (1.4.10)
   and 200% text resize (1.4.4); specifically the topbar row at 641–1040px
   (fixed `h-16`, non-wrapping) and `.route-row` right-edge arrow overlap;
   confirm nothing is clipped by `overflow-x: hidden`.
5. **Target sizes** (F15): measure actual hit boxes on device at 320/390px.
6. **Focus indicator visibility on paper surfaces** (F3, F7): confirm the
   computed 2.35:1 ring is perceivable in practice and that the search input
   shows *some* indicator today (it should show none — confirm).
7. **Single-key shortcuts vs SR modes** (`site.js:336-410`): keys `g`, `t`,
   `[`, `]`, `?`, `/` may interfere with VoiceOver quick-nav or browse-mode
   pass-through; not assessable statically.
8. **Forced-colors / Windows High Contrast**: no `forced-colors` media queries
   exist; prose link underlines are `background-image` gradients
   (`tailwind.css:790-797`) which vanish in forced colors — links then rely
   on system LinkText color only. Verify legibility; consider a
   `forced-colors` fallback that restores `text-decoration`.
9. **Hover-only affordances**: copy button is `opacity:0` until `pre:hover`
   or `:focus-visible` (`tailwind.css:828-837`) — keyboard reveal exists
   (good); verify discoverability and that the reveal is not flash-dependent.

## Limitations of this review

- **No browser or screen reader.** All findings come from source. The preview
  server was live and served the current build (md5 match), but no rendered-DOM
  checks were possible. Claims that depend only on CSS cascade and specificity
  (F3) or on generated markup (F1, F6, F9, F13, F14) are certain. Anything that
  involves layout, geometry or assistive-technology behavior is deferred to the
  verification list above.
- **Contrast on translucent or gradient backdrops is approximate.** Solid
  token-on-token pairs are exact; the topbar and modal-backdrop composites were
  estimated. Every flagged failure uses a solid background, so no listed finding
  depends on the approximation.
- **Coverage is not exhaustive.** This is an independent, bounded pass. Other
  reviewers may have found issues outside this area or overlapping ones. No
  claim of "all issues found" or of acceptance is made.
- **No tooling guards against accessibility regressions.** `site/scripts/lint.ts`
  checks only doc presence and package-manager references. If the findings are
  adopted, consider a small axe-core or HTML validator step in `bun run check`.
  This is a recommendation; nothing was implemented.
- **Provider and auth limits:** none beyond the blocked browser tooling. No
  nested agent CLIs were launched, no global configuration was modified, and
  nothing outside this report file was written.
