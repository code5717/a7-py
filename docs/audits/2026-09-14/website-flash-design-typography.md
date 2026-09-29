# Website Flash Review — Design / Typography & Reading (Field Manual)

Status: audit record from 2026-09-14 (baseline `701c679`). Later user decisions in the [v1 decision ledger](../../plan/decisions.md) may supersede parts of it.

- Reviewer: GLM-5.3-Flash, website design-typography specialist (external, advisory).
  Made no implementation changes.
- Repo: `/home/cx89/Projects/pl-dev/a7-py`
- Scope: Field Manual typography only: reading measure, hierarchy, code vs prose
  density, headings/tables/captions, font fallbacks, spacing rhythm, contrast.
  Existing tokens and assets only; no redesign proposed.

## Execution limitations

1. **Provider interruption:** an earlier run failed on a GLM provider request-rate
   limit. The same reviewer identity resumed in this session and redid the review
   from source. No findings were carried over.
2. **No browser verification:** the in-app browser was unavailable and the local
   browser connection failed (per coordinator). Playwright CLI/MCP and competing
   browsers were not used. **All visual claims below are source-level hypotheses
   and stay provisional until a rendered check is possible.** The local preview
   answered over HTTP (`curl http://localhost:4173/a7-py/` → `HTTP 200`, 16,610
   bytes, Google Fonts `<link>` present). This verifies serving, not rendering.
3. **No computed-style or screenshot evidence:** all measurements come from source,
   committed `site/dist` artifacts and arithmetic (WCAG luminance, grid width), not
   from a live layout engine.
4. **Shared dist not rebuilt:** `site/dist` was inspected as committed.
5. **Other workers' changes preserved:** the working tree held in-progress doc
   cleanup (`AGENTS.md`, `README.md`, `docs/SPEC.md`, `docs/lang-safety/README.md`,
   `site/public/docs/index.md`, `site/public/llms-full.txt`) and new untracked
   tests (`test/test_pipeline_*.py`). Nothing outside this audit file was touched.
6. **Independence:** sibling reports in `docs/audits/2026-09-14/` were not read.
7. **Capabilities:** web search was available but not needed. No authenticated
   services or nested agent CLIs were used.

## Inspected files and exact checks

Files inspected (read in full unless noted):

- `AGENTS.md` (provided in session context), `site/README.md`
- `site/src/tailwind.css` (1,140 lines — the design system and all cited selectors)
- `site/scripts/build.ts` (754 lines — markdown renderer, HTML shell, font `<link>`)
- `site/src/site.js` (442 lines — reveal/scrollspy/copy; no typography defects found)
- `site/dist/assets/site.css` (minified; rules extracted via targeted regex, not read whole)
- Built pages under `site/dist/*/index.html` + `site/dist/index.html` (pattern counts only)
- `site/public/docs/*.md` (pattern counts + spot reads; corpus is small, 48–98 lines/page)

Exact checks performed:

| # | Check | Result |
|---|-------|--------|
| 1 | Source→dist drift: extracted `.prose*`, preflight `*{margin:0;padding:0}`, `code,kbd,samp,pre{font-size:1em}` from compiled `site.css`; matches `tailwind.css` | parity confirmed |
| 2 | Adjacent-paragraph census in built pages (`rg -U '</p>\s*<p>'`) | compiler 6, project 4, stdlib 4, release 2, status 2; others 0 |
| 3 | `data-lang` census across all built pages | 7×`a7`, 11×`bash`, 0 bare/`text` fences |
| 4 | `^####` census in `site/public/docs/*.md` | 0 (renderer supports h1–h3 only, build.ts:158) |
| 5 | Longest inline-code token in corpus | 26 ch (`/a7-py/docs/agent-usage.md`, index.md:66) |
| 6 | WCAG relative-luminance contrast, computed in Python for 12 fg/bg pairs + 3 candidate token values | see F2 table |
| 7 | Center-column (paper) content width from grid math at vw = 1040/1280/1440/1600/1920 | 352/568/712/744/744 px → ~38–86 ch at 18 px |
| 8 | Dead-token grep: `--feat-display`, `--feat-num` usage | defined at tailwind.css:37,39; never applied |
| 9 | Preview reachability over HTTP | HTTP 200; fonts link served |

## Findings

Priority scale: High = hurts reading on current corpus; Medium = clear defect,
bounded fix; Low = polish or latent.

---

### F1 (High) — Prose paragraphs render with zero vertical spacing

- **Evidence**: Tailwind preflight in compiled `site/dist/assets/site.css` sets
  `*,:after,:before,::backdrop{box-sizing:border-box;border:0 solid;margin:0;padding:0}`.
  The only paragraph rules in `site/src/tailwind.css:774-775` are color and
  `hanging-punctuation: first` — no margin utility. Compiled CSS confirms:
  `.prose p,.prose li{color:var(--color-ink-800)}` / `.prose p{hanging-punctuation:first}`
  and no margin declaration on `.prose p`. Headings (`h2 mt-[54px] mb-4`,
  `h3 mt-8 mb-2.5`), lists (`ul my-4`), `pre` (`my-6`) and tables (`my-[22px]`)
  all carry spacing — only `p + p` collapses to 0.
- **Consequence**: multi-paragraph runs (18 junctions across compiler, project,
  stdlib, release, status pages — check #2) read as one continuous block,
  separated only by leading. This is the single largest reading-comfort defect
  on the docs surface.
- **Correction** (one selector, existing rhythm scale):
  ```css
  .prose p { @apply mb-4; }   /* bottom-only; collapses correctly */
  ```
  Bottom-only keeps heading offsets intact (h2's `mt-54px` still wins the
  collapse), and `ul my-4` / `pre my-6` / table `my-[22px]` continue to govern
  their own gaps. `mb-4` (16 px) matches the existing list gap; `mb-5` (20 px)
  is the alternative if slightly looser prose is wanted.
- **Acceptance criteria**:
  1. In built CSS, `.prose p` has a non-zero block margin.
  2. On `compiler` and `project` pages, computed gap between adjacent `<p>` boxes is the chosen value (16 or 20 px), while gap from `p` to following `h2` remains ~54 px and `p`→`pre` remains ~24 px.
  3. No change to first-paragraph-after-heading offset.
- **Status**: source + compiled-CSS verified; visual severity estimate provisional.

---

### F2 (High) — Small mono captions on paper surfaces fail WCAG AA contrast

Computed ratios (sRGB relative luminance, WCAG 2.x formula; check #6):

| Foreground / background | Ratio | Verdict for <18.66 px text |
|---|---|---|
| `muted-500 #8b806b` on `paper-100 #ede6d3` | 3.12:1 | **fail (needs 4.5)** |
| `muted-500` on `paper-200 #e3dbc2` | 2.81:1 | **fail** |
| `muted-500` on `paper-50 #f4eee0` | 3.36:1 | **fail** |
| `muted-500` on `graphite-900` (sidebar/toc) | 4.86:1 | pass |
| `muted-500` on `graphite-950` (`.t-dim`) | 5.03:1 | pass |
| `oxide-600` on `paper-100` (eyebrow 12 px) | 4.79:1 | pass (marginal) |
| `oxide-700` on `paper-100` (prose links) | 6.63:1 | pass |
| `calibration-600` on `paper-100` (status chip, 9 px) | 3.85:1 | **fail** |

Affected selectors (all `muted-500` ink on paper): running head `.paper::before`
(11 px, tailwind.css:236-240; `data-running` set in build.ts:432, every doc page),
`.doc-pager small` (10 px, 877-880), `.route-intro-meta` (12 px, 463-466),
`.route-group h3` (10 px on paper-200, 488-491), `.route-kind` manual variant
(9 px, 521-528), and the `calibration-600` status chip (9 px, 527).

- **Consequence**: page furniture text (running head, pager labels, route board
  metadata) is below AA on exactly the surfaces readers scan; the running head
  appears on 100% of doc pages.
- **Correction** (token-level, no palette redesign): add one darker muted step
  and use it on paper surfaces only; keep `muted-500` on dark surfaces (it passes there):
  ```css
  /* @theme */
  --color-muted-600: #665c48;
  ```
  Computed: 5.29:1 on paper-100, 4.76:1 on paper-200, 5.69:1 on paper-50 — passes
  on every paper step. Swap `text-muted-500` → `text-muted-600` in the six
  selectors listed above. For the 9 px `calibration-600` status chip, prefer the
  existing `oxide-700` treatment (5.97:1 on paper-200, matches the guide chip
  pattern) or darken the chip text only.
- **Acceptance criteria**:
  1. Every text node below 18.66 px on `paper-50/100/200` uses a token pair whose computed ratio ≥ 4.5 (recompute with the same luminance script).
  2. Dark-surface `muted-500` usages unchanged (sidebar, toc, terminal, footer ticker).
  3. Visual character of captions (size, tracking, uppercase) unchanged.

---

### F3 (Medium, high value) — Reading measure exceeds comfortable range at desktop

- **Evidence**: `.prose { max-width: 900px }` (tailwind.css:742) is inert at
  desktop: the shell grid (`.shell` max-w 1480, rails `minmax(180px,240px)` +
  `minmax(160px,220px)`, two 34 px gaps, `px-7`) caps the paper at 896 px, and
  `.paper` padding `clamp(28px, 5vw, 76px)` leaves 744 px of content at ≥1480 vw.
  At 18 px Fraunces that is ≈79–86 characters per line (grid math, check #7);
  1440 vw ≈ 76–82 ch; 1280 vw ≈ 61–66 ch.
- **Consequence**: at common desktop widths the eye travel on full paragraphs is
  past the 45–75 ch comfort band; line-return errors grow on multi-clause
  sentences typical of the docs corpus.
- **Correction** (cap text-level elements only; leave `pre`/`table` full width):
  ```css
  .prose p, .prose ul, .prose h2, .prose h3 { @apply max-w-[66ch]; }
  ```
  (66ch ≈ 640–690 px in Fraunces; expected ≤ ~75 ch worst case. Alternatively
  `max-w-[680px]` if a px token is preferred.) The inert `max-w-[900px]` on
  `.prose` can stay to govern wide blocks.
- **Acceptance criteria**:
  1. At 1920 vw, rendered paragraph lines measure ≤ ~75 ch (spot-check the longest paragraphs on `language`/`start`).
  2. `pre` and `table` boxes still span the full paper content width.
  3. `h1`/`.summary` geometry unchanged.
- **Status**: arithmetic hypothesis; confirm with a rendered line count.

---

### F4 (Medium) — Code scale inconsistent: prose code blocks set at body size

- **Evidence**: `.prose pre` (tailwind.css:806-810) sets line-height 1.65 but no
  font-size; preflight `code,kbd,samp,pre{font-size:1em}` makes it inherit the
  `.prose` 18 px (confirmed in compiled CSS). Elsewhere the site sets code at
  14 px (`.preview-code pre`, tailwind.css:581) and 13.5 px (`.terminal-panel pre`,
  657). Inline code is `.9em` = 16.2 px (802-805).
- **Consequence**: the doc pages — the code-densest surface — set block code ~29%
  larger than the home page's showcase code, wasting measure (worse with F3) and
  breaking the code-scale rhythm; three coexisting code sizes (18 / 16.2 / 14) on
  one page type.
- **Correction**:
  ```css
  .prose pre  { @apply text-[14.5px]; }   /* keep line-height 1.65 */
  .prose code { @apply text-[.85em]; }    /* ≈15.3 px inside 18 px prose */
  ```
  14.5 px sits between the two existing home values without introducing a new
  scale stop; alternatively reuse `text-sm` (14 px) to reuse an existing token.
- **Acceptance criteria**:
  1. Built CSS shows `.prose pre` font-size = 14.5 px (or 14 px).
  2. Longest fence lines on `language`/`start`/`compiler` no longer scroll horizontally at ≥1280 vw (they currently do not scroll at 1440+; size reduction must not regress this — it only improves it).
  3. `data-lang` badge (`top:8px; left:14px`) still clears the first code line given `code { padding-top:16px }` for labeled fences.

---

### F5 (Medium) — Display feature tokens are dead code

- **Evidence**: `--feat-display` (ss01/ss02/cv11/kern) and `--feat-num`
  (tnum/lnum/kern) are defined in `:root` (tailwind.css:37,39) and referenced by
  no selector (grep, check #8). Meanwhile tabular figures are re-hardcoded
  ad hoc at tailwind.css:197-198 (`.nav-link span`), 409 (`.poster-stats dd`),
  510 (`.route-num`). Display selectors (`.paper > h1` 726-732, `.brand span`
  131-135, `.poster-copy h1` 411-418, `.prose h2` 747-753) set
  `font-variation-settings` but never the intended `font-feature-settings`.
- **Consequence**: the display cut of Fraunces renders with default character
  variants — the designed ss01/ss02/cv11 alternates never appear; token drift
  between the declared system and applied styles.
- **Correction** (apply, don't delete — matches the declared design intent):
  ```css
  .paper > h1, .brand span, .hero h1, .poster-copy h1, .prose h2 {
    font-feature-settings: var(--feat-display);
  }
  ```
  and replace the three hardcoded `tnum/lnum` declarations with
  `font-feature-settings: var(--feat-num)`.
- **Acceptance criteria**: 1) grep shows each `--feat-*` token referenced at
  least once outside `:root`; 2) no selector sets `tnum` by literal string
  anymore; 3) glyphs visibly change only in intended display/headline spots
  (rendered check, provisional).

---

### F6 (Low-Medium) — Latent: bare code fences get an unlabeled-space "TEXT" badge

- **Evidence**: build.ts:133 defaults bare fences to `data-lang="text"`;
  tailwind.css:812-822 paints the badge for every `data-lang`, but the extra
  `code { padding-top:16px }` clearance applies only to non-text (823-826).
- **Consequence**: today none — corpus has 0 bare fences (check #3: 7 a7 + 11
  bash). If a plain-output fence is added (likely, e.g. expected binary output),
  the badge collides with the first code line.
- **Correction**: `.prose pre[data-lang="text"]::after { display:none; }`
  (plain output needs no language badge), or include `text` in the padding rule.
- **Acceptance criteria**: a scratch doc with a bare fence renders with either no
  badge or full clearance (rendered check).

---

### F7 (Low-Medium) — Latent: long inline code will clip instead of wrap

- **Evidence**: `.prose` has `overflow-x-clip` (tailwind.css:742); `.prose code`
  (802-805) has no `overflow-wrap`. Current corpus max inline token is 26 ch
  (check #5), but AGENTS.md-documented artifact names
  (`a7-example-artifacts-linux-x86_64-zig0.16.0-<profile>.tar.gz`, ~52 ch) are
  plausible future release-doc content; at 15–16 px mono ≈ 470–500 px, wider than
  the 352 px content width at 1040 vw.
- **Consequence**: today none; once such a token lands in docs, inline code will
  be visually cut off on tablet widths.
- **Correction**: `.prose code { overflow-wrap: anywhere; }`
- **Acceptance criteria**: a 52-char inline token wraps within the paper at
  1040 vw (rendered check).

---

### F8 (Low) — Vertical rhythm off-scale for tables

- **Evidence**: block margins around prose blocks: `pre my-6` (24 px, 807),
  `ul my-4` (16 px, 776), `table my-[22px]` (844) — the only off-stop value.
- **Consequence**: barely perceptible (2 px) inconsistency; free harmonization.
- **Correction**: `table { @apply my-6; }` (tailwind.css:844).
- **Acceptance criteria**: computed `margin-block` on `.prose table` = 24 px.

---

### F9 (Low) — Minor scale polish (optional, bundle with any pass)

- `.summary` line-height 1.24 at up to 26 px (733-738) is tight for a 2–3 line
  serif lead over 820 px; `1.3` reads better without changing the look.
- `.prose h3` fixed 22 px (769) vs 18 px body is a weak 1.22 step for scanning;
  24 px would restore hierarchy. Fluid h1/h2 already scale down on mobile while
  h3 is fixed — 24 px keeps the mobile gap safe.
- Progressive enhancements, no visual risk: `text-wrap: balance` on
  `.paper > h1, .prose h2`; `text-wrap: pretty` on `.prose p`.
- **Acceptance criteria**: rendered line counts of `.summary` ≤ 4 lines on all
  pages; h3/body ratio ≥ 1.3.

---

### F10 (Low) — Font delivery: third-party swap, no metric bridge

- **Evidence**: single Google Fonts stylesheet, `display=swap` (build.ts:379);
  fallbacks are sound (`Georgia` serif stack, `ui-monospace` stack — tailwind.css:23-25).
- **Consequence**: FOUT reflow is most visible at display sizes (h1 up to 112 px);
  fonts.googleapis.com is a render dependency for the "first viewport must make
  A7 unmistakable" rule (site/README.md:31).
- **Correction** (minimal, no redesign): add `<link rel="preload" as="font">`
  for the two woff2 files once URLs are known, or self-host woff2 under
  `site/public/fonts/` with the same `@font-face` axes (`opsz,wght,SOFT`;
  `wght 300..700` mono). Either is additive.
- **Acceptance criteria**: no layout shift of `.paper > h1` between first paint
  and font load (rendered check; provisional today).

## Coverage limits and non-claims

- Nothing above is browser-verified; all ratios and measures are computed from
  source constants and committed dist artifacts. Visual hypotheses are provisional.
- Not audited (outside bounded area): copy/markdown content quality, JS behavior
  under real input, home poster display composition beyond cited tokens, print
  styles (none exist — noting only), i18n, iconography, the SVG system map.
- Not exhaustively claimed: these are the defects found by the listed checks;
  other typography issues may exist that these checks would not surface
  (e.g., real font rendering metrics of Fraunces, hinting, subpixel behavior).
- Renderer caps at h1–h3 (build.ts:158) and the corpus uses no h4+ today, so no
  h4+ styling gap exists to fix; flagged only as a boundary condition.
- The 404 page (`site/dist/404.html`) is a redirect stub with one plain link —
  no typography surface.
