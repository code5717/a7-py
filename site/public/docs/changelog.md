# Changelog

The canonical changelog is [`CHANGELOG.md`](https://github.com/code5717/a7-py/blob/master/CHANGELOG.md).

## Current Unreleased Focus

- Source recursion is rejected during semantic validation.
- Runnable examples were expanded and rewritten to avoid recursive A7 source.
- Public curl.md-friendly docs and `llms.txt` are available for agents.
- Zig/C backend parity checks were added and expanded.
- C backend generic function calls now specialize simple top-level generic functions before emission.
- Release artifact checksum generation and verification were added.
- The docs site was simplified, dark mode was revised, and fake testimonial content was removed.
- The docs app now exposes a first-class `/docs` curl.md directory with direct
  `curl -fsS` commands and canonical `/docs/install.md` plus `/docs/guide/*`
  Markdown paths.
- The public site navigation and homepage were rebalanced around A7 itself:
  Start, Language, Examples, Compiler, and Status are primary again, while
  curl.md and plugin resources remain available from the docs surfaces.
- Added `examples/037_language_tour.a7`, a commented compact tour for learning
  the current stable language surface by reading and running one verified file.
- Untagged union literals and field access now run in both Zig and C example
  verifiers; tagged union tag workflows remain a known gap.

## Current Release

`0.3.0` documents release/debug artifact checks, the installed `a7` CLI entrypoint, C backend improvements, example verification, and the current language-core gap list.

## Release Status

Tag-created draft GitHub releases are configured. PyPI Trusted Publishing wiring exists, but final PyPI project trust setup is still required before first publish.
