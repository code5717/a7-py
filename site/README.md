# A7 documentation site

The static site publishes at <https://code5717.github.io/a7-py/>. Bun runs the
build and checks. Tailwind compiles the stylesheet. No client framework or
server is required for deployed documentation.

## Content and publication

`public/docs/**/*.md` holds the human and agent documentation. Each document has
frontmatter for its title, navigation group, summary, and order, followed by one
H1. Use Markdown topic links such as `/a7-py/docs/language/functions.md`; the
HTML renderer converts them to the corresponding page URLs.

`scripts/content.ts` discovers nested documents and creates the typed registry.
It combines headings, legacy anchors, source links, examples, and records from
`content/features.json`. The HTML build, search index, sitemap, manifest, and
agent exports all read that registry. Markdown-it renders CommonMark with table
support and raw HTML disabled. Code fences retain their literal source.

```bash
bun install --frozen-lockfile
bun run sync:exports
bun run check
bun run preview
```

Run `sync:exports` after changing the corpus or feature metadata. It updates the
tracked `llms.txt`, `llms-full.txt`, sitemap, and manifest. Ordinary builds write
only `dist/`. `check:exports` detects stale tracked exports and exits nonzero.
The documentation digest in the manifest identifies the published corpus, not
compiler correctness or a clean Git revision.

`check` runs lint, TypeScript checks, source-derived feature coverage checks,
renderer and publication tests, preview-server security tests,
the static build, export synchronization checks, and internal-link checks.
The Pages workflow checks generated exports before uploading the build.

The preview server binds to `127.0.0.1:4173`; set `PORT` to change it. Missing
resources return 404. JSON has the JSON content type. GitHub Pages controls
production HTTP headers. Deployment is a separate operation.

## Design

The approved minimal documentation layout uses a 240px navigation rail, a reading
column, and a 180px outline. Native disclosures replace the rail below 900px and
the outline below 1200px. Article prose uses Inter Variable at 17px and 1.65 line
height. Literal code uses JetBrains Mono at 15px and 1.6 line height without
ligatures. Both fonts are pinned dependencies, copied locally with their
licenses. Only the prose font is preloaded.

Light and dark tokens live in `src/tailwind.css`. The initial theme follows the
system; explicit preferences apply before paint and persist when storage is
available. Search, copy controls, and outline tracking enhance static HTML.
Without JavaScript, content, navigation, outlines, and Markdown links still work.

See [research decisions](docs/research-decisions.md),
[coverage](docs/coverage.md), and [verification](docs/verification.md).
