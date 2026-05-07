# A7 Documentation Site

React + TypeScript + Vite docs frontend for the A7 compiler repository.

## Local Development

```bash
cd site
npm install
npm run dev
```

The site uses `HashRouter`, so routes resolve as `#/path` locally and on GitHub Pages.

## Build

```bash
cd site
npm run build
npm run preview
```

## Quality Checks

```bash
cd site
npm run lint -- --max-warnings=0
npm run typecheck
npm run build
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

- minimal terminal-brutalist dark mode with graphite surfaces, amber action color, and restrained cyan focus/info accents
- editorial serif display type with a restrained sans body
- 1px border discipline and flat panels
- top navigation plus drawer-based full route navigation
- image-led home page and social preview assets from `site/public/` plus source assets in `site/src/assets/`
- concise, product-like copy with no fake testimonials
- keyboard-accessible docs search overlay from the header search button and `/` shortcut
- built-in `light` / `dark` / `system` theme modes with persistence
- dark-extension detection to avoid double-dark styling when browser extensions inject their own theme layer

## Adding a Docs Page

When adding or renaming a page, update these pieces together:

- route registration in `site/src/App.tsx`
- primary/sidebar navigation and `PAGE_META` in `site/src/content/navigation.ts`
- section search entries for important anchors
- footer links if the page is a major docs group
- route-specific content with `SectionPanel` titles for stable anchors
- `npm run lint -- --max-warnings=0`, `npm run typecheck`, and `npm run build`

## Deployment

GitHub Pages deploy runs from `.github/workflows/deploy-docs.yml` when docs-related files change on `main`/`master`.
