# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the canonical agent guide. This file holds only Claude-only
deltas: architecture, CLI modes, docs accuracy, and out-of-scope notes below.
For the compiler entrypoints, verification commands, test quality, writing
style, anti-slop, language-change approval, A7 source rules, post-change
checklist, and security caveat, follow `AGENTS.md`.

## Architecture

A7 is an ahead-of-time compiler from `.a7` source to Zig source, then to a
native binary via the host Zig toolchain. The Python compiler is the entire
implementation; there is no separate runtime.

Pipeline (orchestrated by `a7/compile.py: A7Compiler`):

1. `a7/tokens.py` — Tokenizer. Handles single-token generics (`$T`), nested
   comments, multiple number formats.
2. `a7/parser.py` — Recursive-descent parser with precedence climbing.
   Produces nodes defined in `a7/ast_nodes.py`.
3. `a7/passes/` plus `a7/safety.py` — Semantic passes run in order:
   `name_resolution.py` → `type_checker.py` → `semantic_validator.py` →
   internal safety proof planning.
   Shared state lives in `a7/semantic_context.py` and `a7/symbol_table.py`;
   type machinery in `a7/types.py` and `a7/generics.py`.
4. `a7/ast_preprocessor.py` — sub-passes for stdlib resolution, struct init
   normalization, mutation/usage analysis, inference, shadowing, hoisting, and
   constant folding.
5. `a7/backends/` — Backend registry (`__init__.py`, `base.py`) plus the
   `zig.py` backend that emits Zig source.

Surrounding modules: `a7/cli.py` (argparse entrypoint → `compile.A7Compiler`),
`a7/module_resolver.py` (import resolution; virtual `std/*` plus file-backed
local imports that are merged into the single Zig output),
`a7/stdlib/` (registry of `std/io`, `std/math`, `std/mem`, `std/string`),
`a7/formatters/` (console/JSON/markdown output for tokens/AST/semantic dumps
and the `--doc-out` report), `a7/errors.py` (typed errors and rich display).

No-recursion rule for compiler internals: no new recursion in `a7/`. No
function may call itself directly or through a cycle of calls. Use explicit
stacks and worklists. `test/test_no_recursion.py` holds the ratchet: a
static call-graph scan with a shrinking allowlist of the recursive groups
that still exist; do not add to it. The historical census from 2026-09-17
listed the parser, type checker, type equality (`a7/types.py`), semantic
validator, safety pass, AST preprocessor, backend, module resolver, symbol
table dump and console formatter. Current state per `README.md`: semantic
analysis, AST preprocessing, formatter/reporting AST walks, and backend
binary-expression emission use explicit stacks; the parser is recursive
descent and backend statement/non-binary expression paths still use
visitor-style recursive emission in places. The pipeline is validated at
Python recursion limit 100 (see `test/test_iterative_traversal.py`). A7
source recursion is a separate, banned construct; see "A7 Source Rules" in
`AGENTS.md`.

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
