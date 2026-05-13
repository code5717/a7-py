# A7 Docs Site

Fresh static site for <https://code5717.github.io/a7-py/>.

The site is intentionally small:

- `public/docs/*.md` is the public raw markdown corpus.
- `scripts/build.ts` renders every doc to static HTML under `dist/`.
- `src/tailwind.css` is the Tailwind 4 design system source.
- `llms.txt` and `llms-full.txt` are generated from the same corpus.
- No client framework runtime, no router bundle, no generated JSON content layer.

## Design System

**Name:** Field Manual.

**Thesis:** A7 should feel like an industrial compiler field manual: graphite
machine shell, warm paper reading surface, rare oxide inspection ink, and dense
monospace navigation.

**Rules:**

- Tailwind is the styling system. Tokens live in `@theme` inside
  `src/tailwind.css`.
- Use two type families only: serif for reading and display type, monospace for
  structure, code, nav, captions, and running headers.
- The palette is graphite shell, parchment paper, oxide red accent, and
  calibration green. Raw Tailwind palette utilities should not define the look.
- The docs surface is editorial, not SaaS. Use pages, rails, rules, and
  tables before cards.
- The first viewport must make "A7" unmistakable and show the compiler map.
- Body copy is readable on the paper surface; navigation stays compact and
  operational.
- No floating dashboard cards, decorative blobs, generic gradient panels, or
  rounded SaaS surfaces.

Commands:

```bash
bun install
bun run build
bun run preview
```

The GitHub Pages workflow publishes `site/dist`.
