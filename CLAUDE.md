# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project-level guidance for Claude Code. Mirrors `AGENTS.md`; treat that file
as the canonical agent guide and keep both in sync. `README.md` and
`docs/RELEASE.md` remain the authoritative user-facing docs.
For terminal/curl workflows, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/index.md` are the
agent-readable docs entry points derived from the authoritative docs.

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
local imports that currently fail closed before codegen),
`a7/stdlib/` (registry of `std/io`, `std/math`, `std/mem`, `std/string`),
`a7/formatters/` (console/JSON/markdown output for tokens/AST/semantic dumps
and the `--doc-out` report), `a7/errors.py` (typed errors and rich display).

Iterative-traversal invariant: semantic passes, AST preprocessing,
formatter/reporting walks, and backend binary-expression emission use
explicit stacks. The parser is recursive descent; some backend
statement/non-binary emission paths still use visitor recursion. The
project validates the supported pipeline at Python recursion limit 100;
do not reintroduce deep recursion in compiler internals (see
`test/test_iterative_traversal.py`). A7 source recursion is a separate,
banned construct (see "A7 Source Rules" below).

## Running the Compiler

- Installed CLI entrypoint (after `uv sync`): `uv run a7 <args>`
- Repository compatibility wrapper: `uv run python main.py <args>`

Both invoke `a7.cli:main` (the Python package is `a7/`, not `src/`). Prefer
`uv run a7` to match end-user usage; use the `main.py` wrapper when working
from a fresh checkout.

CLI modes (`--mode`): `compile` (default, writes `.zig`), `tokens`, `ast`,
`semantic`, `pipeline` (full run, no file write), `doc`. `--format` is
`human` or `json`. Exit codes: 0 success, 2 usage, 3 io, 4 tokenize,
5 parse, 6 semantic, 7 codegen, 8 internal.

## Verification Commands

- Pytest (all): `PYTHONPATH=. uv run pytest`
- Single test file: `PYTHONPATH=. uv run pytest test/test_tokenizer.py`
- Targeted by keyword: `PYTHONPATH=. uv run pytest -k "generic" -v`
- Debug artifact verification:
  `uv run python scripts/build_examples.py --profile debug --backend zig --clean`
- Release artifact verification:
  `uv run python scripts/build_examples.py --profile release --backend zig --clean`
- Example E2E:
  `uv run python scripts/verify_examples_e2e.py`
- Error-stage matrix:
  `uv run python scripts/verify_error_stages.py --mode-set all --format both`
- Full local release gate: `./run_all_tests.sh`
- Package build: `uv build`
- Wheel install smoke test (clean venv):
  `uv run python scripts/verify_wheel_install.py` (CI/release jobs run this
  with `--skip-build` after `uv build`)
- Docs site build: `cd site && npm ci && npm run build`
- Agent/curl.md docs preview: `cd site && npm run build && npm run preview`
  then check `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, and
  `/a7-py/docs/index.md`.

Examples are verified end-to-end against the Zig backend.
The Zig example E2E script must pass for any change to
`examples/`, codegen, or runtime behavior.

`run_all_tests.sh` is the single source of truth for the full gate (pytest,
parser/semantic/codegen tests, Zig example E2E, debug + release artifacts,
error-stage matrix, docs style, secrets check, package build, and clean-venv
wheel install smoke test). Run it before reporting a non-trivial task as done.

The public docs site also ships Markdown entry points for agent tooling under
`site/public/llms.txt`, `site/public/llms-full.txt`, and `site/public/docs/`.
Keep those files aligned with `README.md`, `docs/RELEASE.md`, and user-visible site
navigation when docs structure changes.

## A7 Source Rules

- A7 source recursion is banned. Semantic validation rejects direct, mutual,
  and local function-pointer alias-cycle recursion as compile-time errors;
  do not introduce examples, tests, or docs that rely on recursive A7
  functions.
- Prefer loops, explicit stacks, or index-based worklists when porting
  recursive algorithms (see `examples/025_linked_list.a7`,
  `examples/026_binary_tree.a7`).
- Use `usize` for sizes, lengths, capacities, and array/slice/string
  indices. Index and slice-bound variables must be `usize`; non-negative
  integer literals are still accepted for simple indexing. Reserve `isize`
  for signed pointer-sized offsets and position differences only; it is
  not the default signed integer type.
- `new [N]T` (heap fixed arrays) is currently rejected by the compiler. Use
  stack arrays (`buf: [N]T`) or slices in examples, tests, and docs until
  the language model is defined.
- Public A7 reference syntax does not expose address-of or dereference
  operators. Do not author examples or docs with `.adr`, `.val`, prefix `&`,
  or prefix `*` as reference operations; pass lvalues directly to `ref`
  parameters and use ordinary field access after nil checks.
- Native release archives are named with platform/toolchain context
  (`a7-example-artifacts-linux-x86_64-zig0.16.0-<profile>.tar.gz`); keep
  any docs or scripts that reference these filenames in sync.
- This rule applies to A7 source only. Compiler internals already use
  iterative AST traversals; keep them that way.

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

When language features, backends, or user-facing behavior change, update:

1. `docs/CHANGELOG.md` — add a short release-facing entry
2. `README.md` — usage, feature lists, examples
3. `docs/SPEC.md` — language semantics or syntax
4. `docs/STATUS.md` — close or open gaps and priorities
5. `site/public/llms.txt`, `site/public/llms-full.txt`, and
   `site/public/docs/` — update agent/curl.md entry points when site
   navigation, release commands, CLI behavior, or public docs structure changes

Keep examples and docs aligned across `README.md`, `docs/SPEC.md`,
`docs/CHANGELOG.md`, `docs/STATUS.md`, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/` — drift between them is
treated as a bug.

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
