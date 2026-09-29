## Closure verdict

**All six closures verified. No remaining defects found. `bun run check` exit 0 on the final tree (1,467 links, 172 search targets, exports current without re-sync).**

1. **Evidence labeling — confirmed.** `site/docs/browser-verification.md:5` now states the record is superseded by `audits/ui-components.md`, gives the current 19-result count and current copy-failure string, and preserves the original observations below unchanged (old line 32 retained as history). `ui-components.md` present with 14 evidence files including a release-gate log.
2. **404 single source — confirmed.** No 404 generation remains in `scripts/build.ts`; `public/404.html` == `dist/404.html` == served `/a7-py/404.html` byte-for-byte (`cmp` clean). Unknown route returns 404 `text/plain` from the preview (by design; the styled page ships for GitHub Pages). My initial browser "FAIL" on this point was my own wrong expectation — the local preview never serves styled 404 markup, matching the documented preview contract.
3. **Search excerpt — confirmed live.** `src/site.js` now anchors at `excerptTerm = terms.find(t => lower.includes(t))`. Drove the real dialog with `"stdlib println"` (first term exists only in metadata/features): 5 results; all 5 rendered excerpts byte-match a reimplementation of the new algorithm; 4/5 show leading `…` (proof of in-text offset; the 5th legitimately starts at 0), matched term `<mark>`ed, no feature-ID leakage. This query under the old code would have anchored at offset 0.
4. **CSS consolidation — computed styles preserved.** Combined `aria-current` selectors at `tailwind.css:461-464`; border folded into the `button, select` rule (line ~90); `.prose a` underline at 238; mobile `.copy` 2.75rem and `.code-toolbar` 3.75rem inside the 899px block. Live computed checks: control border `rgb(87,91,99)` == `--muted` both themes; prose links underlined (light fresh; dark verified in the prior run's screenshots); desktop toolbar 52px, mobile 60px; desktop copy 32px, mobile copy exactly 44px; outline highlights the section reached by permalink click on desktop and via mobile-outline link click at 390px; no horizontal overflow at 390. Tailwind file 894 → 882 lines with no orphaned duplicates left except the intentional wrapping tail.
5. **Workflow flag — confirmed.** No `max-warnings` in `ci.yml` or `deploy-docs.yml`.
6. **No unnecessary sync — confirmed.** `check:exports` reports current after the changes; content sources untouched.

Fresh browser checks: 17/17 meaningful checks pass (`/tmp/opencode/audit/closure-browser-results.json`); the single recorded FAIL is the mis-specified 404 expectation explained above, re-verified clean via curl.

Scope note: language-level review proceeds in the sibling GLM-5.3 session; not addressed here.
