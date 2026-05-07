# AGENT.md

Compatibility pointer for tools that look for a singular `AGENT.md`.

- **Canonical agent guide:** [`AGENTS.md`](AGENTS.md) — read this first for any
  generic coding agent.
- **Claude Code mirror:** [`CLAUDE.md`](CLAUDE.md) — kept in sync with
  `AGENTS.md`.
- **User-facing docs:** [`README.md`](README.md) and [`RELEASE.md`](RELEASE.md)
  remain authoritative for end users.

## Key Commands (short form)

- Run the compiler: `uv run a7 <args>` (or `uv run python main.py <args>`)
- Full release gate: `./run_all_tests.sh`
- Debug artifacts:
  `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- Release artifacts:
  `uv run python scripts/build_examples.py --profile release --backend both --clean`
- Package build: `uv build`
- Docs site build: `cd site && npm install && npm run build`

## Key Rules (short form)

- A7 source recursion is banned; the compiler reports direct and mutual
  recursion as semantic errors. Use loops, explicit stacks, or index-based
  worklists in examples and tests.
- Keep `README.md`, `docs/SPEC.md`, `CHANGELOG.md`, `MISSING_FEATURES.md`,
  and `TODO.md` aligned with any user-visible change.

See `AGENTS.md` for the full workflow, post-change checklist, and security
caveats.
