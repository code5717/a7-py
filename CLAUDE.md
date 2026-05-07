# CLAUDE.md

Project-level guidance for Claude Code. Mirrors `AGENTS.md`; treat that file
as the canonical agent guide and keep both in sync. `README.md` and
`RELEASE.md` remain the authoritative user-facing docs.

## Running the Compiler

- Installed CLI entrypoint (after `uv sync`): `uv run a7 <args>`
- Repository compatibility wrapper: `uv run python main.py <args>`

Both invoke `src.cli:main`. Prefer `uv run a7` to match end-user usage; use
the `main.py` wrapper when working from a fresh checkout.

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
docs style). Run it before reporting a non-trivial task as done.

## Post-Change Checklist

When language features, backends, or user-facing behavior change, update:

1. `CHANGELOG.md` — add an entry
2. `README.md` — usage, feature lists, examples
3. `docs/SPEC.md` — language semantics or syntax
4. `MISSING_FEATURES.md` — close or open gaps
5. `TODO.md` — check off or add follow-ups

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig or C
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
