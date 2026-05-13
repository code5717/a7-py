# Installation

## Requirements

- Python 3.13+
- `uv`
- Zig 0.16.0 for building and running generated Zig outputs

## Repository Install

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
```

## Verify Toolchain

```bash
uv run a7 --help
zig version
```

The CI and release workflows pin Zig 0.16.0. Use that version when comparing local output with hosted runs.

## Local Docs

```bash
cd site
npm ci
npm run build
npm run preview
```

The Markdown docs are static files under `site/public/docs/`. Start with `/a7-py/llms.txt` for a compact agent index or `/a7-py/llms-full.txt` for a single fetch.
