---
title: Project
nav: Project
group: Project
summary: Contribute to A7 and maintain the shared human and agent documentation.
order: 41
---

# Project

A7's compiler is Python. The website uses Bun, Tailwind, and static HTML.
GitHub Pages serves it under `/a7-py/`.

## Contributing

Read the repository instructions and these source documents before compiler work:

- [README](https://github.com/code5717/a7-py/blob/master/README.md) for usage.
- [Specification](https://github.com/code5717/a7-py/blob/master/docs/SPEC.md) for language semantics.
- [Status](https://github.com/code5717/a7-py/blob/master/docs/STATUS.md) for current limitations.
- [Safety contract](https://github.com/code5717/a7-py/blob/master/docs/SAFETY_CONTRACT.md) for safety obligations and gaps.
- [Release checklist](https://github.com/code5717/a7-py/blob/master/docs/RELEASE.md) for required gates.

Changing existing syntax or behavior requires explicit approval of the current
behavior, proposed behavior, examples, and compatibility impact. Record the
disposition in `docs/plan/decisions.md`. Documentation corrections do not grant
permission to change the language.

## Website development

Install Bun 1.3 or newer for website work. From the repository root:

```bash
cd site
bun install --frozen-lockfile
bun run build
bun run preview
```

Use the local URL printed by the preview server, including the `/a7-py/` base
path. The build output is `site/dist`. Compiler users do not need Bun.

## Documentation maintenance

The shared Markdown corpus lives in `site/public/docs/`. A typed content registry
connects pages, sections, examples, feature records, source links, and navigation.
The build derives HTML, search entries, sitemap, and agent metadata from that
content. Keep nested reference topics aligned with their public Markdown twins.

After editing documentation, run from `site/`:

```bash
bun run sync:exports
bun run check
```

Synchronization is explicit. `bun run check:exports` fails on stale tracked
exports; `bun run build` does not silently change them. Preserve established
routes and heading anchors when moving content.

For language or user-visible behavior changes, update `docs/CHANGELOG.md`,
`README.md`, `docs/SPEC.md`, and `docs/STATUS.md` as affected. Keep
`site/public/llms.txt`, `site/public/llms-full.txt`, and `site/public/docs/` aligned.
Current gaps belong in status; historical investigations belong in the audit
index. Every executable-support claim needs evidence beyond parser acceptance.

## Verification

Use tests that check observable requirements or actual failure modes. A passing
fixture suite does not prove complete language, integration, or safety support.
For non-trivial compiler changes and before tagging, run `./run_release_checks.sh`
from the repository root. See [Release](/a7-py/docs/release.md) for the included
checks and dependency audits.

## Deploy

The `Deploy Docs` GitHub Actions workflow publishes `site/dist` to GitHub Pages.
The public base path is `/a7-py/`. Build and verify locally before deployment;
then check page, Markdown, manifest, and 404 responses on the deployed site.

## Security

`a7-py` is not a sandbox. The compiler emits Zig, and the host toolchain builds
native code that runs with the host account's permissions. Only compile and
execute source you trust. Follow the repository's
[security policy](https://github.com/code5717/a7-py/blob/master/docs/SECURITY.md)
when reporting a vulnerability.
