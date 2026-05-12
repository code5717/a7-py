# Changelog

The canonical changelog is [`CHANGELOG.md`](https://github.com/code5717/a7-py/blob/master/CHANGELOG.md).

## Current Unreleased Focus

- Source recursion is rejected during semantic validation.
- Runnable examples were expanded and rewritten to avoid recursive A7 source.
- Same-shape numeric fixed arrays now support element-wise `+` assignment, and
  `examples/035_matrix.a7` uses `c = a + b`.
- Public curl.md-friendly docs and `llms.txt` are available for agents.
- Zig end-to-end checks were added and expanded to cover defer unwinding,
  unions, generics, enum match expressions, heap structs, and 2D/3D nested arrays.
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
- Added five application-style examples: inventory reporting, text analysis,
  task-board risk scoring, route simulation, and gradebook averages.
- Untagged union literals and field access now run in the Zig example verifier;
  tagged union tag workflows remain a known gap.
- The generics example now runs real generic functions and generic struct
  instances, and coverage includes type-set constraints, explicit
  enum discriminants, stdlib math calls, and edge operators.

## Current Release

`0.3.0` documents release/debug artifact checks, the installed `a7` CLI entrypoint, example verification, and the current language-core gap list.

## Release Status

Tag-created draft GitHub releases are configured. Package-registry publishing is
not part of the current release workflow.
