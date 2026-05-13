# A7 Documentation Site

React + TypeScript + Vite docs frontend for the A7 compiler repository.

## Local Development

```bash
cd site
bun install
bun run dev
```

The site uses `HashRouter`, so routes resolve as `#/path` locally and on GitHub Pages.

## Build

```bash
cd site
bun run build
bun run preview
```

## Quality Checks

```bash
cd site
bun run lint -- --max-warnings=0
bun run typecheck
bun run build
```

Repository-level docs style checks:

```bash
uv run python scripts/check_docs_style.py
```

Repository-level release gates:

```bash
./run_all_tests.sh
uv run python scripts/build_examples.py --profile debug --backend both --clean
uv run python scripts/build_examples.py --profile release --backend both --clean
```

## Styling System

Design tokens and shared interface styles live in:

- `site/src/styles/tokens.css`
- `site/src/index.css`

Primary shared UI primitives live in `site/src/components/`.

The current site direction is:

- minimal editorial docs UI with warm light/dark surfaces and restrained monochrome actions
- editorial serif display type with a restrained sans body
- 1px border discipline and flat panels
- top navigation plus drawer-based curl.md documentation groups
- code-led home page and social preview assets from `site/public/` plus source assets in `site/src/assets/`
- concise, product-like copy with no fake testimonials
- keyboard-accessible docs search overlay from the header search button and `/` shortcut
- built-in `light` / `dark` / `system` theme modes with persistence
- dark-extension detection to avoid double-dark styling when browser extensions inject their own theme layer
- static Markdown entry points under `site/public/docs/`, `site/public/llms.txt`, and `site/public/llms-full.txt`

## Adding a Docs Page

When adding or renaming a page, update these pieces together:

- route registration in `site/src/App.tsx`
- primary/sidebar navigation and `PAGE_META` in `site/src/content/navigation.ts`
- curl.md directory data in `site/src/content/curlDocs.ts` when the page belongs in the public docs map
- section search entries for important anchors
- footer links if the page is a major docs group
- public Markdown files under `site/public/docs/`
- `site/public/llms.txt`, `site/public/llms-full.txt`, and `site/public/sitemap.xml`
- route-specific content with `SectionPanel` titles for stable anchors
- `bun run lint -- --max-warnings=0`, `bun run typecheck`, and `bun run build`

## Deployment

GitHub Pages deploy runs from `.github/workflows/deploy-docs.yml` when docs-related files change on `main`/`master`.
