# AGENTS.md

Guidance for coding agents working in this repository. Keep changes consistent
with `README.md` and `RELEASE.md`; those are the authoritative user-facing docs.
For terminal/curl workflows, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/index.md` are the
agent-readable docs entry points derived from the authoritative docs.

## Running the Compiler

- Installed CLI entrypoint (after `uv sync`): `uv run a7 <args>`
- Repository compatibility wrapper: `uv run python main.py <args>`

Both invoke the same `a7.cli:main` (the Python package now lives at `a7/`,
not `src/`). Prefer `uv run a7` for examples that mirror end-user usage;
use the `main.py` wrapper when working from a fresh checkout without a
synced environment.

## Verification Commands

- Debug artifact verification:
  `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- Release artifact verification:
  `uv run python scripts/build_examples.py --profile release --backend both --clean`
- Full local release gate: `./run_all_tests.sh`
- Package build: `uv build`
- Wheel install smoke test (clean venv):
  `uv run python scripts/verify_wheel_install.py` (CI/release jobs run this
  with `--skip-build` after `uv build`)
- Docs site build: `cd site && npm ci && npm run build`
- Agent/curl.md docs preview: `cd site && npm run build && npm run preview`
  then check `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, and
  `/a7-py/docs/index.md`.

`run_all_tests.sh` is the single source of truth for the full gate (pytest,
parser/semantic/codegen tests, example e2e for Zig and C, backend parity,
debug + release artifacts, error-stage matrix, docs style, secrets check).
Run it before tagging or before reporting a task as done when changes are
non-trivial.

The public docs site also ships Markdown entry points for agent tooling under
`site/public/llms.txt`, `site/public/llms-full.txt`, and `site/public/docs/`.
Keep those files aligned with `README.md`, `RELEASE.md`, and user-visible site
navigation when docs structure changes.

## A7 Source Rules

- A7 source recursion is banned. Semantic validation rejects direct, mutual,
  and local function-pointer alias-cycle recursion as compile-time errors;
  do not author examples, tests, or docs that rely on recursive A7 functions.
- Port recursive algorithms to loops, explicit stacks, or index-based
  worklists (see `examples/025_linked_list.a7` and
  `examples/026_binary_tree.a7` for the expected style).
- Use `usize` for sizes, lengths, capacities, and array/slice/string
  indices. Index and slice-bound variables must be `usize`; non-negative
  integer literals are still accepted for simple indexing. Reserve `isize`
  for signed pointer-sized offsets and position differences only; it is
  not the default signed integer type.
- `new [N]T` (heap fixed arrays) is currently rejected by the compiler.
  Use stack arrays (`buf: [N]T`) or slices in examples, tests, and docs
  until the language model is defined.
- Native release archives are named with platform/toolchain context
  (`a7-example-artifacts-linux-x86_64-zig0.15.2-<profile>.tar.gz`); keep
  any docs or scripts that reference these filenames in sync.
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
6. **site/public/llms.txt**, **site/public/llms-full.txt**, and
   **site/public/docs/** — update agent/curl.md entry points if site
   navigation, release commands, CLI behavior, or public docs structure
   changed

Keep examples and docs aligned across `README.md`, `docs/SPEC.md`,
`CHANGELOG.md`, `MISSING_FEATURES.md`, `TODO.md`, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/` — drift between them is
treated as a bug.

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig or C
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
