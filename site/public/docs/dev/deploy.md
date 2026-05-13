# Deploy the Docs Site

The docs at <https://code5717.github.io/a7-py/> deploy from the `site/`
directory to GitHub Pages. This page covers the workflow, base path, and
how the static markdown surfaces (`llms.txt`, `llms-full.txt`, raw
`.md`) are produced.

## What deploys

The build output of `site/` deploys to the `gh-pages` branch (or the
GitHub Pages action target). The artifact tree:

```text
dist/
├── index.html               # SPA entry
├── 404.html                 # GitHub Pages SPA fallback
├── assets/                  # bundled JS / CSS / fonts
├── docs/                    # raw markdown (copied from public/docs)
├── docs-data/               # build-time-rendered JSON per page + search index
├── llms.txt                 # auto-generated index
├── llms-full.txt            # auto-generated full corpus
├── sitemap.xml              # static, regenerated from manifest
├── robots.txt
└── favicon.svg
```

## Build locally

```bash
cd site
npm ci
npm run build
```

The output is `site/dist/`. Inspect it with:

```bash
npm run preview
# open http://localhost:4173/a7-py/
```

The `/a7-py/` base path is required — GitHub Pages serves the site under
`code5717.github.io/a7-py/`, not the domain root.

## Base path

The base path is set in `site/vite.config.ts`:

```ts
export default defineConfig({
  base: '/a7-py/',
  ...
})
```

`BrowserRouter` uses the same `basename` in `src/main.tsx`. Don't change
one without changing the other.

## SPA fallback for GitHub Pages

`public/404.html` stashes the requested path in `sessionStorage` and
redirects to `/a7-py/`. `main.tsx` reads `sessionStorage` before React
mounts and replaces the URL via `history.replaceState`. This lets
`/a7-py/learn/start` be a real bookmarkable URL even though GitHub Pages
doesn't do server-side rewrites.

Legacy `/#/route` hash URLs (from the previous HashRouter site) are also
handled — `404.html` rewrites them to `/route` before reload.

## Build-time markdown pipeline

`scripts/vite-plugin-a7-docs.ts` runs at build start (and on file change
during dev). For each `.md` in `public/docs/`:

1. Front-matter parsed with `gray-matter`.
2. Markdown rendered to HTML with `marked`.
3. Code blocks highlighted with `shiki` (`github-dark-default` theme).
4. Headings extracted for TOC + search.
5. JSON emitted to `public/docs-data/<slug>.json`.

The plugin then auto-generates `public/llms.txt` and
`public/llms-full.txt` from the route manifest. Don't hand-edit those
files — your changes will be overwritten on the next build.

## Regenerating the sitemap

```bash
cd site
npx tsx scripts/generate-sitemap.ts
```

The sitemap reads the manifest in `src/content/manifest.ts` and writes
`public/sitemap.xml`. Commit the regenerated file when you change the IA.

## GitHub Pages deploy

The deploy workflow:

1. Push or PR merge to `master`.
2. CI runs `./run_all_tests.sh` — must pass.
3. CI runs `cd site && npm ci && npm run build`.
4. The action publishes `site/dist/` to the `gh-pages` branch (or the
   Pages target).

`robots.txt` and `sitemap.xml` reference the canonical origin
`https://code5717.github.io/a7-py/`. If the domain ever changes, update
both files, the canonical `<link>` in `site/index.html`, and the
`ORIGIN` constant in `scripts/vite-plugin-a7-docs.ts`.

## Verifying a deploy

```bash
# Resolve a few URLs end-to-end
curl -fsSI https://code5717.github.io/a7-py/                    # 200
curl -fsSI https://code5717.github.io/a7-py/learn/start         # 200 (SPA)
curl -fsS  https://code5717.github.io/a7-py/llms.txt | head     # text/plain
curl -fsS  https://code5717.github.io/a7-py/llms-full.txt | wc  # big text
curl -fsS  https://code5717.github.io/a7-py/docs/language.md    # raw markdown
```

If `llms-full.txt` lacks a page you expect, the manifest is missing the
entry — see `site/src/content/manifest.ts`.
