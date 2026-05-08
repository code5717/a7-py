# AGENT.md

Compatibility pointer for tools that look for a singular `AGENT.md`.

- **Canonical agent guide:** [`AGENTS.md`](AGENTS.md) — read this first for any
  generic coding agent.
- **Claude Code mirror:** [`CLAUDE.md`](CLAUDE.md) — kept in sync with
  `AGENTS.md`.
- **User-facing docs:** [`README.md`](README.md) and [`RELEASE.md`](RELEASE.md)
  remain authoritative for end users.
- **Agent/curl docs:** [`site/public/llms.txt`](site/public/llms.txt),
  [`site/public/llms-full.txt`](site/public/llms-full.txt), and
  [`site/public/docs/index.md`](site/public/docs/index.md) are the
  agent-readable public docs entry points derived from the authoritative docs.

## Key Commands (short form)

- Run the compiler: `uv run a7 <args>` (or `uv run python main.py <args>`).
  The Python package lives at `a7/`; the entrypoint is `a7.cli:main`.
- Full release gate: `./run_all_tests.sh` (covers example E2E for **both**
  Zig and C backends and the 24-case backend parity sweep).
- Debug artifacts:
  `uv run python scripts/build_examples.py --profile debug --backend both --clean`
- Release artifacts:
  `uv run python scripts/build_examples.py --profile release --backend both --clean`
- Backend parity (24 cases — generic constraints, generic structs/functions,
  explicit enum discriminants, stdlib math, operator edge cases):
  `uv run python scripts/verify_backend_parity.py`
- Package build: `uv build`
- Wheel install smoke test (clean venv):
  `uv run python scripts/verify_wheel_install.py` (CI/release uses
  `--skip-build` after `uv build`)
- Docs site build: `cd site && npm ci && npm run build`
- Agent/curl.md docs: `site/public/llms.txt`, `site/public/llms-full.txt`,
  and `site/public/docs/`

## Key Rules (short form)

- A7 source recursion is banned; the compiler reports direct, mutual, and
  local function-pointer alias-cycle recursion as semantic errors. Use
  loops, explicit stacks, or index-based worklists in examples and tests.
- Use `usize` for sizes, lengths, capacities, and array/slice/string
  indices (index and slice-bound variables must be `usize`); reserve
  `isize` for signed pointer-sized offsets, not as the default signed type.
- `new [N]T` (heap fixed arrays) is currently rejected; use stack arrays
  or slices in examples, tests, and docs.
- Native release archives are named with platform/toolchain context
  (`a7-example-artifacts-linux-x86_64-zig0.15.2-<profile>.tar.gz`).
- Keep `README.md`, `docs/SPEC.md`, `CHANGELOG.md`, `MISSING_FEATURES.md`,
  and `TODO.md` aligned with any user-visible change.
- Keep `site/public/llms.txt`, `site/public/llms-full.txt`, and
  `site/public/docs/` aligned when site navigation, release commands, CLI
  behavior, or public docs structure changes.
- Docs must distinguish currently supported features from parsed-only or
  reserved syntax — notably variadics, intrinsics other than `@type_set`,
  and multiple-declaration/destructuring binding syntax. Do not present
  parsed-only forms as working.
- Package-registry publishing (a7 package index, registry client, lockfile
  resolution) is **out of scope**; reject related additions to code, docs,
  TODO, or MISSING.

See `AGENTS.md` for the full workflow, post-change checklist, and security
caveats.
