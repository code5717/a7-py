---
title: Agent Usage
nav: Agent Usage
group: Agents
summary: Stable curl and agent entry points for consuming the A7 documentation.
order: 7
---

# Agent Usage

The docs site is designed to be easy to fetch from terminals and coding
agents. Prefer raw text URLs over crawling the visual site.

## Fetch order

```bash
curl -fsSL https://code5717.github.io/a7-py/llms.txt
curl -fsSL https://code5717.github.io/a7-py/llms-full.txt
curl -fsSL https://code5717.github.io/a7-py/docs/language.md
```

## Compact index

`llms.txt` lists every public markdown page and a short summary. Use it first
when choosing which page to fetch.

## Full corpus

`llms-full.txt` concatenates the whole public docs corpus. Use it when a coding
agent needs one fetch with the entire public context.

## Individual pages

Every visual page has a raw markdown twin under `/a7-py/docs/<slug>.md`.

Current slugs:

- `index`
- `start`
- `language`
- `stdlib`
- `compiler`
- `status`
- `release`
- `agent-usage`
- `project`

## Agent rules

- Treat `README.md`, `docs/SPEC.md`, `docs/STATUS.md`, and `docs/RELEASE.md`
  as authoritative when changing the compiler.
- Treat site markdown as public-facing compression of those sources.
- Keep generated Zig output single-file.
- Do not author A7 examples that rely on source recursion.
