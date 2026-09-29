# Browser verification

The rebuilt site passed the recorded layout and interaction checks after fixes to desktop navigation, narrow-screen wrapping, and control borders. This report covers local static output served at `http://127.0.0.1:4174/a7-py/` on 2026-09-19. It does not verify a deployed GitHub Pages version.

This is the initial rebuild record. The later [component verification](audits/ui-components.md) supersedes its search and clipboard observations. The current `usize` search returns 19 results, and copy failure reads `Copy failed. Select the code and copy it manually, or try again.` Historical JSON and observations below remain unchanged.

## Browser and method

Used an isolated headless Chromium instance through the browser-harness CDP interface. The default browser connection failed with `chrome-not-running`; a task-owned Chromium instance on port 9237 provided the local connection. No user browser tabs were altered.

The viewport sweep used widths of 320, 390, 768, 1024, and 1440 CSS pixels, each at 1000 pixels high, for the home, memory, and compiler pages in light and dark themes. The [30 measurements](evidence/viewport-results.json) show one H1 and no page-wide horizontal overflow. A separate [46 measurements](evidence/all-pages.json) checked all 23 pages at 320 and 1440 pixels. Every page retained one H1 and stayed within the viewport.

The 320 CSS pixel viewport tests the available layout width of a 1280-pixel browser at 400% zoom. Browser chrome zoom itself was not automated. This is a reflow-equivalent viewport check, not a claim about every browser's zoom behavior.

Inspected screenshots using the image viewer, including [desktop light](evidence/home-1440-light.png), [mobile dark](evidence/home-320-dark.png), [compiler mobile](evidence/compiler-390-light.png), [blocked fonts](evidence/blocked-fonts-390.png), and [enlarged text with spacing overrides](evidence/text-200-percent-320.png). Additional viewport captures are in [evidence](evidence/).

## Findings and fixes

- Desktop navigation was initially blank because its native disclosure was closed while its summary was hidden. The final desktop capture shows the full rail. Mobile navigation starts collapsed with JavaScript and works as a native disclosure without it.
- A CSS class named `outline` inherited Tailwind's outline utility and produced unwanted black borders. Renaming the class removed them.
- At 320 pixels, 200% root text size combined with text-spacing overrides initially exceeded the viewport. Wrapping fixes reduced the final document width to 305 pixels inside the 320-pixel viewport, including the scrollbar. Content remains in normal flow.
- Initial button and select borders had insufficient contrast. Their final borders use the secondary text color, which exceeds 6:1 against both light surfaces and 8:1 against dark surfaces. Decorative separators retain lower contrast.

## Interaction and fallback checks

The [interaction results](evidence/interaction-results.json) record these exercised behaviors:

- The first Tab stop was the visible `Skip to content` link targeting `#main`, with the dark theme focus color.
- Searching for `usize` returned 18 results. Arrow Down focused a result link. Escape closed the dialog and returned focus to the opener.
- Blocking the search-index request produced an explicit failure message with a retry control. Unblocking it and activating Retry restored 20 search results.
- Actual clipboard copy succeeded in the isolated browser after a CDP permission grant. Reading the browser clipboard returned the exact code text.
- Rejecting the Clipboard API call produced `Copy failed. Select code to copy.` The literal code remained selectable.
- A 27-Tab dialog sequence never focused an underlying page control. Native Chromium transferred focus to browser chrome once, then returned to the dialog. This is not a strict in-document Tab trap.
- A query with no matches produced the distinct empty state. Selecting Light persisted after a reload.
- Throwing on access to local storage did not prevent the article, search control, or theme control from appearing.
- With JavaScript execution disabled, navigation initially exposed all 23 links. Pointer clicks closed and reopened it. Search stayed hidden.
- Blocking WOFF2 requests preserved readable fallback text without page-wide overflow.
- Required line, letter, word, and paragraph spacing overrides at 320 pixels did not overflow the document. The same overrides with 200% root text also passed after the wrapping fix.

The [contrast calculations](evidence/contrast.json) cover primary text, secondary text, links, focus rings, and control borders against main and secondary surfaces in both themes. Text pairs exceed 4.5:1; focus and control boundaries exceed 3:1. Article links have explicit underlines after the final CSS fix. The final computed decoration is `underline`, mobile copy controls are 44 pixels high, and the reference navigation uses short topic labels. See [final polish evidence](evidence/final-polish.json).

An uncached load with 350ms network latency and 80KB/s throughput recorded no layout-shift entries. Both local fonts loaded. See [font loading evidence](evidence/font-loading.json). This single measured load does not establish a field performance percentile.

## Boundaries

No approved option 2 image was available in the repository search. Captures were compared with the written plan's layout, typography, color, and navigation requirements. Pixel matching to the unavailable concept is unverified.

The checks do not substitute for screen-reader testing, testing in Firefox or Safari, or a complete accessibility audit. The 23-page sweep measures layout; detailed visual inspection sampled the named pages and screenshots rather than every article at every scroll position. Source examples and compiler release qualification are covered by separate checks.
