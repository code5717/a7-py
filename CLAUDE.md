# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the canonical agent guide. This file holds only Claude-only
deltas: architecture, CLI modes, docs accuracy, and out-of-scope notes below.
For the compiler entrypoints, verification commands, test quality, writing
style, anti-slop, language-change approval, A7 source rules, post-change
checklist, and security caveat, follow `AGENTS.md`.

## Architecture

See `docs/ARCHITECTURE.md` for the pipeline, module map, and no-recursion
pointer. The rule itself lives in `AGENTS.md` ("No recursion in compiler
internals"); do not restate it here.

## Running the Compiler

Same entrypoints as `AGENTS.md`: `uv run a7 <args>` after `uv sync`, or
`uv run python main.py <args>` from a fresh checkout.

CLI modes (`--mode`): `compile` (default, writes `.zig`), `tokens`, `ast`,
`semantic`, `pipeline` (full run, no file write), `doc`. `--format` is
`human` or `json`. Exit codes: 0 success, 2 usage, 3 io, 4 tokenize,
5 parse, 6 semantic, 7 codegen, 8 internal.

## Verification Commands

See `AGENTS.md`. It lists the pytest, artifact, E2E, error-stage, gate,
package, and site commands (`bun install --frozen-lockfile`).

## Agent rules

Test quality, writing style, anti-slop, language-change approval, and A7
source rules live in `AGENTS.md`. Follow them as written.

## Docs Accuracy

User-facing docs (`README.md`, `docs/SPEC.md`, `docs/STATUS.md`,
`site/public/llms*.txt`, `site/public/docs/`) must clearly distinguish
**currently supported** features from syntax that is only **parsed or
reserved** but not yet implemented. In particular, mark these as
parsed-only/reserved rather than working features:

- variadic parameters
- intrinsics other than `@type_set`
- multiple-declaration and destructuring binding syntax

Adding examples, snippets, or claims that imply the parsed-only forms work
end-to-end is treated the same as a doc/code drift bug.

## Out of Scope

- Package-registry publishing (a7 package index, registry client, lockfile
  resolution, etc.) is **out of scope** for this repository. Do not add
  features, examples, docs, or status entries that assume a registry;
  treat related requests as out-of-scope and flag them.

## Post-Change Checklist

See `AGENTS.md`, including the `sync:exports` step for website content edits.

## Security Caveat

See `AGENTS.md`. `a7-py` is not a sandbox for untrusted source.
