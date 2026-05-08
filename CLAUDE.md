# CLAUDE.md

Project-level guidance for Claude Code. Mirrors `AGENTS.md`; treat that file
as the canonical agent guide and keep both in sync. `README.md` and
`RELEASE.md` remain the authoritative user-facing docs.
For terminal/curl workflows, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/index.md` are the
agent-readable docs entry points derived from the authoritative docs.

## Running the Compiler

- Installed CLI entrypoint (after `uv sync`): `uv run a7 <args>`
- Repository compatibility wrapper: `uv run python main.py <args>`

Both invoke `a7.cli:main` (the Python package is `a7/`, not `src/`). Prefer
`uv run a7` to match end-user usage; use the `main.py` wrapper when working
from a fresh checkout.

## Verification Commands

- Debug artifact verification:
  `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- Release artifact verification:
  `uv run python scripts/build_examples.py --profile release --backend both --clean`
- Backend parity (24 cases — generic constraints, generic structs/functions,
  explicit enum discriminants, stdlib math, operator edge cases):
  `uv run python scripts/verify_backend_parity.py`
- Full local release gate: `./run_all_tests.sh`
- Package build: `uv build`
- Wheel install smoke test (clean venv):
  `uv run python scripts/verify_wheel_install.py` (CI/release jobs run this
  with `--skip-build` after `uv build`)
- Docs site build: `cd site && npm ci && npm run build`
- Agent/curl.md docs preview: `cd site && npm run build && npm run preview`
  then check `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, and
  `/a7-py/docs/index.md`.

Examples are verified end-to-end against **both** the Zig and C backends —
the Zig and C example E2E scripts must both pass for any change to
`examples/`, codegen, or runtime behavior.

`run_all_tests.sh` is the single source of truth for the full gate (pytest,
parser/semantic/codegen tests, example E2E for Zig and C, 24-case backend
parity, debug + release artifacts, error-stage matrix, docs style, secrets
check). Run it before reporting a non-trivial task as done.

The public docs site also ships Markdown entry points for agent tooling under
`site/public/llms.txt`, `site/public/llms-full.txt`, and `site/public/docs/`.
Keep those files aligned with `README.md`, `RELEASE.md`, and user-visible site
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
- Native release archives are named with platform/toolchain context
  (`a7-example-artifacts-linux-x86_64-zig0.15.2-<profile>.tar.gz`); keep
  any docs or scripts that reference these filenames in sync.
- This rule applies to A7 source only. Compiler internals already use
  iterative AST traversals; keep them that way.

## Docs Accuracy

User-facing docs (`README.md`, `docs/SPEC.md`, `MISSING_FEATURES.md`,
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
  features, examples, docs, or TODO/MISSING entries that assume a registry;
  treat related requests as out-of-scope and flag them.

## Post-Change Checklist

When language features, backends, or user-facing behavior change, update:

1. `CHANGELOG.md` — add an entry
2. `README.md` — usage, feature lists, examples
3. `docs/SPEC.md` — language semantics or syntax
4. `MISSING_FEATURES.md` — close or open gaps
5. `TODO.md` — check off or add follow-ups
6. `site/public/llms.txt`, `site/public/llms-full.txt`, and
   `site/public/docs/` — update agent/curl.md entry points when site
   navigation, release commands, CLI behavior, or public docs structure changes

Keep examples and docs aligned across `README.md`, `docs/SPEC.md`,
`CHANGELOG.md`, `MISSING_FEATURES.md`, `TODO.md`, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/` — drift between them is
treated as a bug.

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig or C
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
