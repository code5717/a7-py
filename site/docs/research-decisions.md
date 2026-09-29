# Website design decisions

Reviewed 2026-09-19. These decisions implement the user's approved option 2 plan. They do not change A7 syntax or compiler behavior.

## Reading and navigation

Use a persistent documentation rail, a readable article column, and an optional page outline. Collapse navigation into native disclosures on smaller screens so it works without JavaScript. Separate the guided tour from exhaustive language reference. This applies the distinction between learning and information retrieval in [Diátaxis](https://diataxis.fr/).

No option 2 concept image was located by the initial repository filename search. The written approved plan is the design authority. Existing screenshots under `docs/audits/2026-09-19/browser/` record the previous site, not acceptance of this rebuild. Do not claim a pixel comparison against an unavailable reference.

## Typography

Use Inter Variable for prose and navigation, with JetBrains Mono for literal source and terminal commands. Inter documents optical sizing and tabular figures. JetBrains documents its code-oriented character design. These properties suit this layout; they do not prove Inter is the fastest font for every reader. Research found substantial individual variation in reading speed across fonts.

- [Inter documentation and license links](https://rsms.me/inter/)
- [JetBrains Mono documentation](https://www.jetbrains.com/lp/mono/)
- [Individual reading differences, Adobe Research](https://research.adobe.com/publication/towards-individuated-reading-experiences-different-fonts-increase-reading-speed-for-different-individuals/)

Self-host pinned WOFF2 files and retain license notices. Use swap display, preload only the primary prose font, and test blocked fonts. A preload can improve discovery but also competes for bandwidth; excessive preloading is not a substitute for measuring the page. See [web.dev font delivery guidance](https://web.dev/articles/font-best-practices).

Set body text to 1.0625rem with a 1.65 line height and prose width near 65ch. Use 0.9375rem code with a 1.6 line height. Disable code ligatures to retain literal operators. These dimensions are project choices from the approved plan.

## Contrast and interaction

Use the plan's neutral light and dark backgrounds and restrained red links. Underline article links and provide a visible focus outline. Status text must state supported, limited, unavailable, planned, or unverified rather than relying on color. Validate actual rendered pairings, including secondary surfaces, against [WCAG contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) and [use of color guidance](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html).

Review reflow at a 320 CSS pixel width and enlarged text. Keep code and wide tables in local overflow containers. Test spacing overrides without hidden or overlapping content. These checks follow [reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) and [text spacing guidance](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html). Passing a viewport sweep alone is not complete accessibility acceptance.

## Diagrams

Simple compiler and memory explanations use semantic HTML with explicit labels and equivalent text. Labels remain visible without hovering. Complex diagrams need a caption and an explanation that preserves the relationships, following [W3C complex-image guidance](https://www.w3.org/WAI/tutorials/images/complex/). Do not invent performance charts or completion percentages.

## Agent retrieval

Keep `llms.txt` a concise grouped Markdown index. Recommend selective retrieval, with `llms-full.txt` available for consumers that need the complete corpus. Each document has a Markdown twin; structured metadata describes features, qualifications, evidence, and source revision. A revision identifies a source snapshot and is not proof of correctness.

The [llms.txt proposal](https://llmstxt.org/) describes a discovery convention. The fetched page labels its current text v2. Adoption by a particular agent is not guaranteed. Preserve the project's established URLs and ordinary Markdown links independently of proposal revisions.

## Evidence boundaries

Compiler tests establish only the behaviors they exercise. Parser acceptance cannot establish native execution support. Browser captures establish only the states and viewports inspected. Record unsupported features and unresolved specification conflicts explicitly. The final verification report must distinguish automated checks, manual inspection, and skipped checks.
