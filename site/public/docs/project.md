---
title: Project
nav: Project
group: Project
summary: Contributing, documentation maintenance, and security boundaries.
order: 8
---

# Project

## Contributing

Before changing language behavior, read:

- `docs/SPEC.md`
- `docs/STATUS.md`
- `docs/SAFETY_CONTRACT.md`
- `docs/RELEASE.md`

Small changes should still update public docs when they affect user-visible
behavior.

## Documentation maintenance

Keep the docs minimal:

- Long history belongs in `git log`, not the website.
- Current gaps belong in [Status](/a7-py/status/).
- Release-facing notes belong in `docs/CHANGELOG.md`.
- Public site pages should summarize, not duplicate every internal document.

When language features or user-visible behavior change, update `docs/CHANGELOG.md`,
`README.md`, `docs/SPEC.md`, and `docs/STATUS.md` as needed. Keep the site
corpus in `site/public/docs/` aligned with those sources.

Agent fetch paths and curl workflows live on [Agent Usage](/a7-py/agent-usage/).

## Deploy

The `Deploy Docs` GitHub Actions workflow publishes `site/dist` to GitHub
Pages. The published base path is `/a7-py/`.

Release gates and required archive paths are on [Release](/a7-py/release/).

## Security

`a7-py` is not a sandbox. The compiler emits Zig and the host toolchain builds
native code. Only compile and execute source you trust.
