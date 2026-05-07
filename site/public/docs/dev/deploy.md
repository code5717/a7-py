# Deploy

Use this page for docs and release deployment notes.

## Docs Site

The docs site is built from `site/` and deployed by GitHub Pages.

```bash
cd site
npm ci
npm run build
```

Preview locally:

```bash
npm run preview
```

Check public markdown files after deploy:

```bash
curl -fsS https://code5717.github.io/a7-py/llms.txt
curl -fsS https://code5717.github.io/a7-py/docs/index.md
```

## Release Artifacts

Release workflows build Python distributions, docs archives, native example artifacts, and checksums.

```bash
uv run python scripts/generate_release_manifest.py dist/SHA256SUMS --base-dir .
uv run python scripts/verify_release_manifest.py dist/SHA256SUMS --base-dir .
```

Archive content verification checks required files before upload.
