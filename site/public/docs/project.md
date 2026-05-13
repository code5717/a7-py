---
title: Project
nav: Project
group: Project
summary: Contribution, deployment, and documentation maintenance rules.
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
- Current gaps belong in `docs/STATUS.md`.
- Release-facing notes belong in `docs/CHANGELOG.md`.
- Public site pages should summarize, not duplicate every internal document.

## Deploy

The `Deploy Docs` GitHub Actions workflow publishes `site/dist` to GitHub
Pages. The published base path is `/a7-py/`.

Use these checks after deployment:

```bash
curl -fsSI https://code5717.github.io/a7-py/
curl -fsSL https://code5717.github.io/a7-py/docs/index.md
curl -fsSL https://code5717.github.io/a7-py/llms.txt
```

## Security

`a7-py` is not a sandbox. The compiler emits Zig and the host toolchain builds
native code. Only compile and execute source you trust.
