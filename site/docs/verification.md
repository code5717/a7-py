# Website implementation and verification

The rebuilt static site publishes 23 pages, including the tour, all-example index,
and twelve language reference topics. Local site checks and the repository's full
release gate pass. The work changes presentation and documentation, not A7 syntax
or compiler behavior. Deployment was outside this task and did not run.

## Delivered files

- [Site guide](../README.md) explains authoring, the typed registry, and explicit
  export synchronization.
- [Research decisions](research-decisions.md) record the approved design choices
  and primary sources.
- [Coverage matrix](coverage.md) and [feature records](../content/features.json)
  map 117 specification headings, 48 keywords, 42 operator and punctuation
  spellings, all registered stdlib operations, all 43 examples, and proposed APIs.
  The 428 records have explicit support dispositions and evidence links.
- [Public manifest](../public/docs/manifest.json) exposes page metadata, stable
  sections, examples, sources, and feature qualifications. Its documentation
  SHA-256 identifies content, not compiler correctness or a clean Git revision.
- [Browser verification](browser-verification.md), [content verification](content-verification.md),
  and [agent retrieval](agent-retrieval.md) retain the observations and limitations.

## Publishing architecture

`scripts/content.ts` discovers nested Markdown and creates the registry used by
HTML, navigation, search, sitemap, and agent exports. Markdown-it handles nested
lists, tables, blockquotes, and fences with raw HTML disabled. HTML uses one H1
per page. Heading collisions receive unique stable IDs. Known old anchors remain
available; the old compiler exit-code anchor targets the new diagnostics section.

Each page links its Markdown twin and `llms.txt`. Raw topic links stay Markdown
links. HTML converts those links to page routes. The full corpus resolves relative
links from each source document and preserves fenced source, including nested
fence examples. The preview returns real 404s and a JSON manifest content type.
Compatibility redirects accept only the known historical page names.

`bun run sync:exports` updates tracked exports explicitly. Ordinary builds only
write `dist/`. An [isolated negative control](evidence/export-checks.json) changed
an export and observed exit 1 with the stale-file message. A before/after digest
of every public file confirmed that an ordinary build changed none of them.
The Pages workflow now checks types, source-derived coverage, publication tests,
export freshness, and generated links before upload.

## Verification results

| Check | Observed result | Evidence |
| --- | --- | --- |
| `bun run check` | Pass, including TypeScript, coverage, ten publication/server tests, build, exports, and links | [Site check](evidence/site-check.log) |
| Source-derived coverage | 428 records match the inventory and coverage matrix | [Checker](../scripts/check-coverage.py) |
| Published resources | 1,318 local links/resources and 172 search targets resolve | [Site check](evidence/site-check.log) |
| Complete website A7 snippets | Ten standalone code fences compile and run natively | [Observed source and output](evidence/standalone-snippets.json) |
| Repository examples | 43/43 compile, build, run, and match golden output | [Example results](examples-verification.json) |
| Focused reference and stdlib probes | Valid cases pass; rejection/native-failure cases retained and documented | [Content verification](content-verification.md) |
| Full release gate | 9/9 checks pass, exit 0 | [Full log](evidence/full-release-gate.log) |
| Browser layout | 30 route/width/theme cases and 46 all-page/width cases pass H1 and overflow checks | [Browser report](browser-verification.md) |
| Agent retrieval | Five selective retrieval tasks pass; manifest JSON and missing-page 404 confirmed | [Retrieval report](agent-retrieval.md) |

The release gate includes 2,651 pytest cases, 43 debug artifacts, 43 release
artifacts, 61 error-stage cases, docs style, secrets, package build, and clean
wheel installation. It ran alongside unrelated compiler activity in the shared
working tree. No failure was observed, but this is not an immutable release
snapshot. Existing unrelated modifications were preserved.

Reproduce standalone snippet checks from `site/` with:

```bash
uv run python docs/verify-snippets.py
```

The evidence records stdout and stderr. Ten complete snippets passed, including
the final mutable-struct reference example with stdout `42`. Context-dependent
fragments are identified as excerpts and are covered by repository examples or
the linked integration probes; this does not certify every possible composition.

## Design and interaction review

The written option 2 plan was the design authority. No approved concept image
was available, so no pixel-match claim is made. The final desktop and mobile
captures were opened in the image viewer. The review checked these concrete
requirements:

| Requirement | Implementation and observed result |
| --- | --- |
| Reading layout | 240px rail, centered article, 180px outline; disclosures below the specified breakpoints |
| Typography | Local Inter Variable prose and navigation; JetBrains Mono code; 40px/32px titles and literal operators |
| Palette | Plan's light/dark backgrounds, secondary surfaces, restrained red links, and visible focus colors |
| Article links | Underlines explicitly restored after Tailwind's reset; verified computed underline |
| Code and tables | Local overflow containers; literal source and accessible copy feedback; 44px mobile copy controls |
| Diagrams | Authored ordered steps rendered as semantic flows for compilation, arrays, and reference access |
| Navigation | Desktop rail visible after native-disclosure fix; short labels; no-JavaScript mobile disclosure works |
| Wrapping | No global overflow at 320px, including enlarged text with required spacing overrides |

Above-the-fold factual copy comes directly from the shared Markdown source.
Invented successful terminal transcripts, decorative parchment, oversized display
lettering, and text-reveal animation were removed. Search covers body text and
identifiers. Keyboard selection, empty/loading/failure states, retry recovery,
clipboard success/failure, theme persistence, blocked fonts, and unavailable
storage were exercised. Actual clipboard text matched the code.

Contrast calculations pass for text, links, focus rings, and control boundaries
against both background types. One delayed uncached font load recorded CLS 0.
That observation is not a field performance claim.

## Remaining limitations

The checks in this historical report passed at its source snapshot. Later
native repairs verified escaped IO braces and ordinary signed `math.abs` result
typing. The minimum signed input still needs qualification. The remaining
restrictions from this report are:
- Scalar-filled fixed-array initializers are rejected.
- Direct `string.len` access is rejected.
- Top-level local `@type_set` aliases can fail code generation.

The coverage matrix records additional specification conflicts and unverified
claims, including generic identifier rules and exhaustive evaluation-order
behavior. None was treated as approval to change language behavior.

Visual checks used local Chromium. A 320 CSS pixel viewport exercised the layout
width equivalent to 400% zoom on a 1280px window; actual browser chrome zoom was
not automated. Screen readers, Firefox, Safari, and live GitHub Pages headers
were not tested. Native dialog tabbing can move into browser chrome; it did not
focus underlying page controls. The original concept-image comparison remains
unavailable. These limits do not imply deployed acceptance.
