# Website Review — Design / Responsive Composition (GLM-5.3-Flash)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- **Date:** 2026-09-14
- **Reviewer:** GLM-5.3-Flash, design specialist, external and advisory. No implementation changes, commits or rebuilds of the shared `site/dist`.
- **Scope:** responsive composition: CSS breakpoints, page rails (sidebar, TOC), homepage poster, map and code blocks, tables, touch navigation, overflow, zoom, narrow screens and orientation.
- **Repo:** `/home/cx89/Projects/pl-dev/a7-py`

## Method and files inspected

Static source review plus inspection of compiled output. **No screenshots were captured** (browser capture blocked). Every visual claim below is an estimate computed from the CSS and HTML, not a verified rendering. Each finding's acceptance criteria require screenshot confirmation.

Inspected:

| File | Purpose |
|---|---|
| `AGENTS.md`, `site/README.md` | Repo rules, Field Manual design direction |
| `site/src/tailwind.css` (all 1140 lines) | All breakpoints, layout, component and motion rules |
| `site/src/site.js` (all 442 lines) | Scrollspy, reveal, modals, copy buttons, tabs |
| `site/scripts/build.ts` (all 754 lines) | Generated HTML structure: topbar, shell/sidebar/TOC, home poster/route-board/preview/terminal/footer, pager, search modal |
| `site/public/a7-system-map.svg` | Poster image aspect ratio (1200×760) |
| `site/public/docs/*.md` (frontmatter + token scan) | Sidebar grouping, table column counts, longest unbreakable inline tokens |
| `site/dist/assets/site.css` (65,975 B) and `site/dist/*.html` | Compiled breakpoint set, hover-media wrapping, freshness check |
| `http://localhost:4173/a7-py/` via `curl` | Confirmed the preview serves the current dist (`site.css` byte length matches `dist/assets/site.css`; index HTML served with HTTP 200) |

Exact checks performed:

1. Enumerated every `@media` block in source and in compiled `dist/assets/site.css`. Compiled set: `(max-width:1040px)`, `(max-width:640px)`, `(prefers-reduced-motion:reduce)`, and exactly one `(hover:hover)` rule (`.modal-card header button:hover`). **No `orientation`, `pointer`, or `hover: none` queries exist** (`grep` over `src/tailwind.css` returned none).
2. Tracked column arithmetic for `.shell` (3-col ≥1041px → 1-col ≤1040px), `.poster` (3-col → 1-col), `.hero` (unused in output), `.route-board`, `.preview`, `.terminal-strip`, `.site-footer-row`, `.doc-pager`.
3. Byte/timestamp comparison: `dist` (08:27) is newer than `src` (08:23) — compiled output matches source.
4. Character-width estimates for mono (JetBrains Mono ≈ 0.6 em advance) and Fraunces (≈ 0.5 em average) with the tracking values set in CSS, applied to the narrowest and widest in-breakpoint viewports.
5. Scanned all doc bodies for the longest unbreakable inline tokens (longest inline `` `code` `` token: 26 chars, `/a7-py/docs/agent-usage.md`; longest raw URL 60 chars but only as an `href`, not visible text) and for table shapes (all tables are 2 columns; largest table 18 rows).
6. Verified the viewport meta (`width=device-width, initial-scale=1`, no `maximum-scale`) — pinch zoom is preserved; `text-size-adjust: 100%` deliberately disables iOS landscape font inflation.
7. Verified `prefers-reduced-motion` is fully handled (`site/src/tailwind.css:1047-1055`) and that `[data-reveal]` is only applied via JS when IntersectionObserver exists, so no-JS content stays visible.

## Execution limitations

- **Provider/auth:** the first attempt failed with a model-provider request-rate error; this run resumed it. Recorded per coordinator instruction.
- **Browser capture unavailable:** in-app browser unavailable and local browser connection failed. No Playwright, MCP or other browser was invoked. All visual statements are analytic estimates, not visual verification.
- The preview server was reachable (HTTP 200) and served the current dist, but screenshots were still impossible. Acceptance criteria are written for a later reviewer who can capture.
- Findings are incomplete by construction: static analysis cannot catch font-metric surprises, subpixel overlaps or OS-level zoom behavior.

## Findings

### F1 — HIGH: `.poster-stats` four-column stat row overflows/overlaps across the common desktop range (~1041–1550px)

- **Evidence:** `site/src/tailwind.css:393-398` — `grid-template-columns: repeat(4, minmax(0, auto))` with `gap-x-8` (32px). The only responsive fallback is 2 columns at ≤640px (`:1111`). The poster's first column is `minmax(0, .82fr)` (`:296`), and `.poster-copy` padding is `clamp(28px, 5vw, 84px)` (`:362`).
- **Consequence (computed estimate):** the four stat labels/values are single unbreakable words ("verified", "Zig 0.16", "1 file", "banned"; dt "RECURSION" at 10px mono + 0.24em tracking ≈ 76px). Minimum row width ≈ 400px + 96px gaps ≈ **~436–499px**. The copy column's content box is ≈ **284px at 1041px**, ≈ **352px at 1280px**, ≈ **397px at ≥1480px** (`.home` caps at 1720px, `:291`). With `minmax(0, …)` tracks, the tracks shrink below content and the stat text paints past its track — overlapping the neighboring stat or sliding under the `.system-plate` panel (later sibling, also `z-[1]`, `:427`). Expected severity: worst at 1041–1200px (small laptop windows / split view), moderate at 1280×800, marginal by ~1440px, clean only ≥ ~1550–1600px.
- **Suggested correction:** keep Field Manual look, change the track model: `grid-template-columns: repeat(auto-fit, minmax(112px, 1fr))` (wraps 4→2 naturally), or add an intermediate override `@media (max-width: 1280px) { .poster-stats { grid-template-columns: repeat(2, minmax(0,1fr)); } }`; optionally reduce `gap-x-8` to `gap-x-4`.
- **Acceptance criteria:** at viewports 1041×800, 1100×800, 1280×800, 1440×900: screenshot shows all four stat dd values fully readable, no glyph overlap between adjacent stats, no text extending past the dashed top border of `.poster-stats` into the `.system-plate` column; at 375px width the 2×2 fallback still holds (existing rule).

### F2 — HIGH: search becomes unreachable on touch — `.shortcut-trigger` is `hidden` at ≤640px with no substitute entry point

- **Evidence:** `site/src/tailwind.css:1088` — `.shortcut-trigger { @apply hidden; }` inside the ≤640px block. The only openers are the two topbar buttons (`build.ts:391-392`) and keyboard shortcuts (`/`, ⌘K — `site/src/site.js:338-341, 384-388`), none of which exist on a phone.
- **Consequence:** on phones the search modal, search index, and the shortcuts modal are dead features; docs search is a core navigation path for the site's agent/developer audience.
- **Suggested correction:** keep the search trigger visible in the stacked mobile topbar (e.g., exclude the search button from the `hidden` rule — hide only the shortcuts `?` button — or add a compact search row under the brand). The stacked topbar already has room: `.topbar` goes `flex-col` at ≤640px (`:1086`).
- **Acceptance criteria:** at 375×667 and 320×568: a visible, tappable search control exists in the topbar; tapping it opens the search modal; the modal input is focusable without triggering iOS input zoom (input is 24px/20px type — already ≥16px).

### F3 — MEDIUM: touch target sizes below platform guidance in the mobile chrome

- **Evidence:** `site/src/tailwind.css:1069` — `.nav-link { @apply min-h-8; }` (32px) at ≤1040px; `:217-219` — `.toc a` is `py-[6px]` around 12px text (≈ 27px tall); `:707-710` — footer links are bare 12px text (≈ 15px tall); `.quick a` in the stacked mobile topbar likewise unpadded (~15px). No touch-target compensation exists anywhere (no `pointer`/`hover` media, no padding bumps at ≤640px).
- **Consequence:** on phones the primary doc-nav strip, TOC chips (where visible), quick nav, and footer links are 15–32px targets against the 44px (iOS HIG) / 48dp (Android) guidance — mis-taps on the horizontally scrolling sidebar strip are likely.
- **Suggested correction:** at ≤640px raise `.nav-link` to `min-h-[44px]`, give `.quick a` and `.site-footer-nav a` `inline-block` padding of ~10px vertical (preserving the mono/uppercase look), and increase `.toc a` padding if the TOC returns to mobile (see F5).
- **Acceptance criteria:** at 375×667: every tappable element in topbar, sidebar strip, doc footer, and site footer has a ≥44×44px hit area (verify via dev-tools overlay screenshot or computed-style check, not eyeballing).

### F4 — MEDIUM: copy buttons on code blocks are invisible on touch (hover-gated) and hover styles generally misbehave on coarse pointers

- **Evidence:** `site/src/tailwind.css:834-837` — `pre:hover .copy, .copy:focus-visible { opacity: 1 }` with base `opacity: 0` (`:830`). There is no `@media (hover: none)` or `pointer: coarse` fallback anywhere in source. Meanwhile the compiled CSS wraps exactly one hover rule in `@media (hover:hover)` (`.modal-card header button:hover`) — i.e., hover handling is inconsistent: raw `:hover` rules for `.quick a` (`:162`), `.nav-link` (`:187`), `.toc a` (`:220`), `.route-row` (`:506-541`), `.system-plate img` (`:434`) all remain active on touch and will stick after a tap.
- **Consequence:** phones cannot see or reach the copy affordance on any code block (they can long-press-select instead, but the designed affordance is absent); route rows / sidebar links keep a "stuck" active-looking hover state after tap, contradicting the deliberate `hover:hover` gating used for the modal button.
- **Suggested correction:** add `@media (hover: none) { .copy { opacity: 1; transform: none; } }`, and wrap the decorative hover transforms (route-row arrow/background, nav-link translate, toc, system-plate zoom) in `@media (hover: hover)` to match the modal-button precedent.
- **Acceptance criteria:** on a 390×844 emulated touch viewport: copy buttons are visible without hover; tapping a route row navigates without leaving a persistent hover background; the modal-close hover rule and decorative hovers behave identically to source intent.

### F5 — MEDIUM/LOW: TOC is fully removed on phones; sidebar strip is a horizontally scrolling band with vertical mini-columns and no scroll affordance

- **Evidence:** `site/src/tailwind.css:1092` — `.toc { @apply hidden; }` at ≤640px. At ≤1040px the sidebar becomes `flex-row flex-nowrap overflow-x-auto` (`:1063-1067`) but its `.nav-section` children remain `flex flex-col` (`:199-201`), so the band renders up to four *vertical* column groups (Reference group = 3 links → ≈ 130–140px tall band). Estimated total strip width ≈ 584px vs ≈ 343px available at 375px → horizontal scrolling with no fade/edge cue.
- **Consequence:** on phones, per-page section navigation disappears entirely (relevant for long pages such as `language.md`); the sidebar strip's grouping is hard to parse and users get no signal that it scrolls.
- **Suggested correction:** either (a) render the TOC as horizontally wrapping chips above/below the article at ≤640px (reusing the ≤1040 `.toc` static flex-row treatment instead of `hidden`), and/or (b) flatten `.nav-section` to a single row at ≤640px (`flex-row flex-wrap`) with edge-fade gradients on the strip to signal scrollability.
- **Acceptance criteria:** at 375×667 on `language/`: a user can jump to any §2 heading without scrolling the whole page (TOC chips visible), and the sidebar strip shows a visible cut-off link or gradient at its right edge indicating scrollability; no layout shift when the strip scrolls.

### F6 — MEDIUM/LOW: anchor scroll offset too small for the stacked mobile topbar

- **Evidence:** `site/src/tailwind.css:1084` — `scroll-padding-top: 80px` at ≤640px (base 96px, `:47`). At ≤640px `.topbar` becomes `h-auto flex-col items-start p-4` (`:1086`): brand row (~64px with padding) plus a wrapping `.quick` row (4 links ≈ 356px wide > 343px available at 375px → wraps to 2 rows, ~40px) → **estimated stacked height ≈ 105–125px**, exceeding the 80px scroll offset. `.prose h2/h3 { scroll-margin-top: 80px }` (`:1099`) matches the too-small value.
- **Consequence:** following a search result to `page/#section` on a phone lands the target heading partially or fully under the sticky topbar; repeated for every anchor jump.
- **Suggested correction:** measure the real stacked topbar height, then set `scroll-padding-top` / `scroll-margin-top` to that + 16px (estimate: 120–136px), or unstick the topbar at ≤640px.
- **Acceptance criteria:** at 375×667: tap a search result pointing to a `#heading`; screenshot shows the heading and its rule fully visible below the topbar with ≥8px clearance.

### F7 — LOW: topbar has near-zero horizontal tolerance just above the 640px breakpoint

- **Evidence:** `site/src/tailwind.css:121-126` — `.topbar` is a non-wrapping flex row with `gap-6`; `.quick` is `gap-[18px]` with 4 uppercase links + 2 buttons (`build.ts:386-393`); the wrap/stack fallback only starts at ≤640px (`:1086-1088`).
- **Consequence (computed estimate):** minimum single-row content ≈ brand 240px + quick 356px + gap 24px + padding 40px ≈ **~660px**, while the breakpoint grants single-row up to 640px inclusive — a ~20px-wide failure window (641–~660px, e.g., half-open foldables, narrow desktop windows) where the right-side buttons can clip under `body { overflow-x: hidden }` (`:63`).
- **Suggested correction:** move the stack/wrap breakpoint to ~720px for `.topbar`/`.quick` only (leaving the rest of the 640px block), or let `.quick` wrap at ≤820px while keeping the row height fixed.
- **Acceptance criteria:** screenshots at 641px, 660px, 700px: both shortcut buttons and the "Compiler" link are fully inside the viewport with no horizontal scrollbar (`document.scrollingElement.scrollWidth <= innerWidth` in console).

### F8 — LOW: `100svh` used without a `vh` fallback

- **Evidence:** `site/src/tailwind.css:179` (`max-height: calc(100svh - 110px)` on `.sidebar, .toc`), `:245` (`.hero`), `:295` (`.poster min-h`). `grep svh dist/assets/site.css` → 3 occurrences, no preceding `vh` declaration.
- **Consequence:** on browsers without `svh` support (pre-2023 iOS/Chrome), the declaration is dropped entirely: rails lose their scroll constraint (page-level scrolling with a very long sidebar) and `.poster` loses its viewport-height floor — degraded but not broken. `.hero` is additionally dead CSS (see F9), so only two real usages remain.
- **Suggested correction:** emit a `vh` declaration immediately before each `svh` one (standard progressive-enhancement pair).
- **Acceptance criteria:** in a browser build without `svh` (or via CSS override test), `.sidebar` still scrolls internally and `.poster` retains a ≥600px height floor at 1280×800.

### F9 — LOW: `.hero` component block is dead CSS

- **Evidence:** `site/src/tailwind.css:243-263, 270-288` define `.hero`, `.hero h1/p/img` (and only `.hero-actions` is actually used, inside the poster, `build.ts:481`). `grep '"hero' dist/**/*.html` matches only `hero-actions`. The ≤1040/≤640 blocks still carry `.hero` overrides (`:1070, :1095-1097`).
- **Consequence:** no visual failure, but ~60 lines of unused responsive rules mislead future responsive work (e.g., someone tuning "the hero" that no page renders). Also `html { scroll-padding-top: 96px }` interplay and the `min(620px, calc(100svh - 128px))` math are maintained for nothing.
- **Suggested correction:** delete `.hero`-only rules (keep `.hero-actions`) in a cleanup pass, or re-home the comment marking it as reserved.
- **Acceptance criteria:** `grep -c '\.hero ' site/src/tailwind.css` drops to only `.hero-actions` entries; `bun run check` passes; diff of `dist/assets/site.css` shrinks accordingly.

### F10 — LOW (hardening): `.prose` clips overflow with `overflow-x-clip` and no `overflow-wrap` strategy

- **Evidence:** `site/src/tailwind.css:742` — `.prose { @apply … overflow-x-clip … }`. Only the terminal `pre` sets `word-break: break-word` (`:659`); prose `p`/`li`/`td` have no `overflow-wrap`. Current corpus is safe (longest unbreakable inline-code token = 26 chars ≈ 226px < 284px content at 320px viewport; all tables are 2-col and scrollable via `:845-850`).
- **Consequence:** today: none provable. Future risk: any longer slug/URL/identifier added to docs paints past the paper edge and is **clipped with no scrollbar** (clip, not scroll) — an invisible-content failure mode rather than an ugly-but-visible one.
- **Suggested correction:** add `overflow-wrap: anywhere;` (or `min-width: 0` + `word-break: break-word`) to `.prose p, .prose li, td, th`.
- **Acceptance criteria:** a fixture doc containing a 60-char unbroken token in a paragraph at 320×568 shows the token wrapping (not clipped) with no horizontal scrollbar.

### F11 — LOW: decorative hover states only half-protected; no orientation-specific rules (by design, acceptable) — recorded as coverage statements

- **Evidence/notes:**
  - Landscape phones (844×390) fall in the ≤1040 band: poster/terminal/route-board single-column; computed content fits (`.poster` `min-height: calc(100svh - 92px)` = 298px floor grows with content). No rule found that would clip; **screenshot confirmation still required**.
  - 320px floor: poster-copy h1 clamps to 72px (`:1110`), poster-meta drops its third span (`:1119`), doc pager goes 1-col (`:1139`) — consistent; smallest text is 9–10px uppercase with 0.16–0.26em tracking (`:1116`, `:401`) which is a legibility floor, not a failure.
  - No `orientation`, `pointer: coarse`, or `prefers-contrast` rules exist; forced-colors/high-contrast is out of my scope but noted as untested.
- **Acceptance criteria (orientation/zoom matrix):** screenshots at 844×390 (landscape phone) and 200% page zoom at 1280 (effective 640 — breakpoint boundary probe) and 400% zoom at 1280 (reflow probe): no horizontal page scrollbar, no clipped interactive elements, text remains readable.

## Proposed acceptance viewport matrix (measured, Field Manual direction preserved)

All checks are screenshot-based; nothing is accepted on analysis alone.

| Viewport | Purpose | Must-hold requirements |
|---|---|---|
| 320×568 | narrow floor | no page h-scroll; poster stats 2×2; pager 1-col; all nav tappable |
| 375×667 | reference phone | F2 search entry visible; F5 TOC/strip behavior; F6 anchor clearance; F3 targets ≥44px |
| 390×844 | modern phone portrait | same as 375 + terminal tabs wrap cleanly |
| 844×390 | landscape phone | poster/terminal stack; no clipped actions; no hover-stick artifacts |
| 768×1024 | tablet portrait | sidebar strip columns legible; no strip overflow without affordance |
| 1024×768 | tablet landscape (inside ≤1040 band) | single-column shell; spec-spine horizontal row readable |
| **1041×800** | just above main breakpoint (regression probe) | F1 poster-stats fully readable; 3-col poster intact |
| 1280×800 | common laptop (F1 worst common case) | F1 zero overlap; topbar single row comfortable |
| 1440×900 | desktop | poster columns balanced; no marginal stat clipping |
| 1720×1080+ | max-width cap | `.home` capped at 1720px, poster centered, rails proportional |
| 200%/400% zoom @1280 | zoom reflow | effective-viewport fallbacks engage; no clipped controls |

## Coverage limits

- Static analysis of one built snapshot (dist 2026-09-14 08:27, matching current source). Future doc/token additions can invalidate the F10 "currently safe" claim.
- Font-metric estimates (JetBrains Mono 0.6em, Fraunces ~0.5em average) carry ±10–15% error; F1's overflow *boundaries* are estimates, the overflow *mechanism* (`minmax(0,auto)` shrink + `overflow:hidden`) is certain from source.
- Not covered: OS-level browser font settings, forced-colors/high-contrast, screen-reader walkthroughs, JS-disabled rendering of `[data-reveal]` (argued safe by construction, not tested), Firefox/Safari-specific flex/grid quirks, real device touch latency.
- I did not read the other review reports in `docs/audits/2026-09-14/` per instructions; overlaps are possible and intentional isolation may duplicate points.
- This is not an exhaustive list of responsive defects and not an acceptance verdict.
