# AGENTS.md

Guidance for coding agents working in this repository. Keep changes consistent
with `README.md` and `docs/RELEASE.md`; those are the authoritative user-facing docs.
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

## No recursion in compiler internals

No-recursion rule for compiler internals: no function in `a7/` may call
itself directly or through a cycle of calls, including the parser and the
backend. Use explicit stacks and worklists. `test/test_no_recursion.py`
(being added as batch NOREC-0) enforces this with a static call-graph scan;
until the conversions in `docs/plan/execution.md` ("No recursion anywhere in
the compiler") land, it holds a shrinking list of the recursive groups that
still exist; do not add to it. A scan on 2026-09-17 found recursion in the
parser, type checker, type equality (`a7/types.py`), semantic validator,
safety pass, AST preprocessor, backend, module resolver, symbol table dump and
console formatter. The pipeline is validated at Python recursion
limit 100 (see `test/test_iterative_traversal.py`). A7 source recursion is a
separate, banned construct (see "A7 Source Rules" below).

## Verification Commands

- Debug artifact verification:
  `uv run python scripts/build_examples.py --profile debug --backend zig --clean`
- Release artifact verification:
  `uv run python scripts/build_examples.py --profile release --backend zig --clean`
- Compiler/package gate: `./run_all_tests.sh`
- Complete local and CI release checks: `./run_release_checks.sh`
- Package build: `uv build`
- Wheel install smoke test (clean venv):
  `uv run python scripts/verify_wheel_install.py` (CI/release jobs run this
  with `--skip-build` after `uv build`)
- Docs site build: `cd site && bun install && bun run build`
- Agent/curl.md docs preview: `cd site && bun run build && bun run preview`
  then check `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, and
  `/a7-py/docs/index.md`.

`run_all_tests.sh` is the compiler/package gate (pytest,
parser/semantic/codegen tests, Zig example e2e, debug + release artifacts,
error-stage matrix, docs style, secrets check, package build, and clean-venv
wheel and source-distribution native installation checks).
`run_release_checks.sh` also checks release identity, the site, locked dependencies
and static security findings. Release CI uses that command.
Run it before tagging or before reporting a task as done when changes are
non-trivial.

The public docs site also ships Markdown entry points for agent tooling under
`site/public/llms.txt`, `site/public/llms-full.txt`, and `site/public/docs/`.
Keep those files aligned with `README.md`, `docs/RELEASE.md`, and user-visible site
navigation when docs structure changes.

## Test quality

- Do not write coverage illusion tests. Each test must verify an observable requirement, a real failure mode or an independently stated invariant. Do not mirror implementation logic, assert only that mocks were called or inflate test counts with equivalent cases. Use mocks only at named boundaries and state what they leave unverified. Passing unit or controlled fixture tests cannot mark integration, security enforcement, recovery or product acceptance complete. Prefer a smaller set of meaningful tests over a coverage percentage or test-count target.

## Writing style

Applies to answers in the terminal and to every document written into this
repository.

- Lead with the answer. State the result, then the evidence for it. Do not
  narrate what you are about to do, recap what was just said, or close by
  summarizing what the reader has already read.
- Always use simple technical language in replies, questions, plans, and
  documentation. Use short sentences and familiar words. Explain unfamiliar
  technical terms with a small example.
- Cut filler. No "it is worth noting", "in order to", "leverage", "robust",
  "comprehensive", "seamless", "delve", "journey", "landscape". No praise of the
  work, the question, or the user. Do not pad an answer to look thorough.
- Structure only where structure exists. Use a table when there are real
  columns, a list when there are real items, a heading when there is a real
  section. Do not bold whole sentences or end with a call to action.
- Match length to content. A one-line question gets a one-line answer.
- Make every claim traceable. Attribute a fact to the file, line, command output
  or source that establishes it. Mark inference as inference and unchecked
  claims as unchecked. Never state an attribution you have not verified; a
  confident sentence about which file or reviewer said something is a factual
  claim like any other.
- Report failures plainly, with the output. Do not hedge a verified result and
  do not soften a real failure. Say when a step was skipped.

## Language change approval

- Before changing existing A7 syntax or behavior, show the user the current
  behavior, the proposed behavior, concrete A7 examples and the compatibility
  impact. Obtain explicit approval before implementing the change.
- Research recommendations and accepted historical decisions do not count as
  approval. Record each disposition in `docs/plan/decisions.md`.

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
- Public A7 reference syntax does not expose address-of or dereference
  operators. Do not author examples or docs with `.adr`, `.val`, prefix `&`,
  or prefix `*` as reference operations; pass lvalues directly to `ref`
  parameters and use ordinary field access after nil checks.
- Native release archives are named with platform/toolchain context
  (`a7-example-artifacts-linux-x86_64-zig0.16.0-<profile>.tar.gz`); keep
  any docs or scripts that reference these filenames in sync.
- This rule applies to A7 source only. Compiler internals follow the separate
  no-recursion rule (no recursion anywhere in `a7/`).

## Post-Change Checklist

After making major changes (new language features, bug fixes, backend
additions, refactors), ensure the following docs are up to date before
committing:

1. **docs/CHANGELOG.md** — add a short release-facing entry
2. **README.md** — update usage, feature lists, or examples if affected
3. **docs/SPEC.md** — update if language semantics or syntax changed
4. **docs/STATUS.md** — update current gaps, priorities, or roadmap
5. **site/public/llms.txt**, **site/public/llms-full.txt**, and
   **site/public/docs/** — update agent/curl.md entry points if site
   navigation, release commands, CLI behavior, or public docs structure
   changed

Keep examples and docs aligned across `README.md`, `docs/SPEC.md`,
`docs/CHANGELOG.md`, `docs/STATUS.md`, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/` — drift between them is
treated as a bug.

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
