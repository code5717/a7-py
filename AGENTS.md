# agents.md

Guidance for coding agents working in this repository. Keep changes consistent
with `README.md` and `RELEASE.md`; those are the authoritative user-facing docs.

## Running the Compiler

- Installed CLI entrypoint (after `uv sync`): `uv run a7 <args>`
- Repository compatibility wrapper: `uv run python main.py <args>`

Both invoke the same `src.cli:main`. Prefer `uv run a7` for examples that
mirror end-user usage; use the `main.py` wrapper when working from a fresh
checkout without a synced environment.

## Verification Commands

- Debug artifact verification:
  `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- Release artifact verification:
  `uv run python scripts/build_examples.py --profile release --backend both --clean`
- Full local release gate: `./run_all_tests.sh`
- Package build: `uv build`
- Docs site build: `cd site && npm install && npm run build`

`run_all_tests.sh` is the single source of truth for the full gate (pytest,
backend tests, example e2e, debug + release artifacts, error-stage matrix,
docs style). Run it before tagging or before reporting a task as done when
changes are non-trivial.

## A7 Source Rules

- A7 source recursion is banned. Semantic validation rejects both direct and
  mutual recursion as compile-time errors; do not author examples, tests, or
  docs that rely on recursive A7 functions.
- Port recursive algorithms to loops, explicit stacks, or index-based
  worklists (see `examples/025_linked_list.a7` and
  `examples/026_binary_tree.a7` for the expected style).
- This rule applies to A7 source only. Compiler internals already use
  iterative AST traversals; keep them that way.

## Post-Change Checklist

After making major changes (new language features, bug fixes, backend
additions, refactors), ensure the following docs are up to date before
committing:

1. **CHANGELOG.md** — add an entry for the change
2. **README.md** — update usage, feature lists, or examples if affected
3. **docs/SPEC.md** — update if language semantics or syntax changed
4. **MISSING_FEATURES.md** — mark completed gaps or document new ones
5. **TODO.md** — check off completed items or add newly discovered work

Keep examples and docs aligned across `README.md`, `docs/SPEC.md`,
`CHANGELOG.md`, `MISSING_FEATURES.md`, and `TODO.md` — drift between them is
treated as a bug.

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig or C
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
