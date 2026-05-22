---
title: Agent Usage
nav: Agent Usage
group: Agents
summary: curl and llms.txt entry points for fetching A7 documentation.
order: 7
---

# Agent Usage

Prefer raw text URLs over crawling the visual site. Every rendered page has a
markdown twin under `/a7-py/docs/<slug>.md`.

## Fetch order

```bash
curl -fsSL https://code5717.github.io/a7-py/llms.txt
curl -fsSL https://code5717.github.io/a7-py/llms-full.txt
curl -fsSL https://code5717.github.io/a7-py/docs/language.md
```

## Compact index

`llms.txt` lists every public markdown page with a short summary. Use it first
when choosing which page to fetch.

## Full corpus

`llms-full.txt` concatenates the whole public docs corpus. Use it when one
fetch with the entire public context is enough.

## Agent rules

- Treat `README.md`, `docs/SPEC.md`, `docs/STATUS.md`, and `docs/RELEASE.md`
  as authoritative when changing the compiler.
- Treat site markdown as public-facing compression of those sources.
- Keep generated Zig output single-file.
- Do not author A7 examples that rely on source recursion.

## Deploy verification

After a docs deploy:

```bash
curl -fsSI https://code5717.github.io/a7-py/
curl -fsSL https://code5717.github.io/a7-py/docs/index.md
curl -fsSL https://code5717.github.io/a7-py/llms.txt
```

See [Project](/a7-py/project/) for contribution and doc maintenance rules.
