# UI component refinement

The component pass improves code blocks, search, navigation, and section links
without changing A7 syntax or the approved documentation layout.

## Changes

- Code blocks now render their language and toolbar at build time. Copy failures
  appear after the code in normal flow, including at 320px with doubled text and
  spacing overrides. The copy action can be retried and success feedback resets.
- H2 and H3 headings have descriptive permalink controls. Keyboard focus exposes
  the icon and its focus ring. Anchor scrolling now uses one offset, so the
  highlighted outline item agrees with the section reached.
- Desktop navigation scrolls its own rail to reveal the current page. The article
  stays at its initial position. Both desktop and mobile outlines identify the
  current section.
- Search result context, section titles, excerpts, and matched terms are distinct.
  The input stays available while results scroll. Keyboard arrows apply only to
  search input/results; modified editing keys and the Close button keep native
  behavior. The last result does not wrap unexpectedly to the first.
- Search excerpts come from Markdown tokens, preserving source identifiers without
  displaying link destinations or treating code comments as section headings.
- Full-corpus link rewriting preserves inline and indented code, in addition to
  fenced code. A regression check covers literal code that looks like a link.

## Browser evidence

The isolated Chromium checks cover widths 320, 390, 768, 1024, and 1440 in both
themes. At 1440x800 the current Project link is visible while document scrollY
stays zero. Copy failures do not overlap code at 320px, including 200% text with
spacing overrides. Native section-link clicks reach the matching active outline
item. No-JavaScript content retains code labels, literal code, and section links.

The browser's computed theme colors were checked, and final representative
captures use the theme control's change handler with matching selection and
rendered state. The initial screenshot labels were corrected before delivery.

Evidence is in [ui-components-evidence](ui-components-evidence/). The source, interaction checks, and
site tests establish only the scoped component behavior they exercise.

## Checks

`bun run check` passed with 12 tests, 428 coverage records, 23 pages, 172 search targets, and current generated exports. The full repository release gate passed all 9 checks, including 2,651 pytest cases, 43 examples in each native artifact profile, and 61 error-stage cases. These results do not establish untested compiler safety properties.

## External review

[GLM-5.3-Flash's full website review](glm-5.3-flash-full-review.md) found no blocking website defects. It reported 41 fresh browser checks and five minor findings. The exact model was `zai-coding-plan/glm-5.3-flash`, invoked through OpenCode 1.18.30. The original prompt, JSON event stream, process result, and stderr are retained here.

The controlling session confirmed the duplicate 404 source, duplicated CSS, and ignored lint flags, then removed them. Search excerpts now use a query term that occurs in the section body. The initial browser report now points to this newer evidence while preserving its historical observations. The old report's counts were not rewritten to imply its checks ran again.

The post-review `bun run check` passed. Generated exports were already current and needed no synchronization. The [same-session Flash follow-up](glm-5.3-flash-closure.md) verified all closures. It records 17 passing component checks and one incorrect styled-404 expectation that the reviewer corrected through HTTP verification. The local preview returns plain-text 404 responses; GitHub Pages receives the styled 404 file. Compiler behavior was not changed.
