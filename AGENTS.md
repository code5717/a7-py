# AGENTS.md

Guidance for coding agents working in this repository. Keep changes consistent
with `README.md` and `docs/RELEASE.md`; those are the authoritative user-facing docs.
For terminal/curl workflows, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/index.md` are the
agent-readable docs entry points derived from the authoritative docs.

## Map: how agents use docs/

- Language, gaps, safety, releases: `docs/SPEC.md`, `docs/STATUS.md`,
  `docs/SAFETY_CONTRACT.md`, `docs/RELEASE.md`, `docs/CHANGELOG.md`.
- Architecture: `docs/ARCHITECTURE.md`. Docs index: `docs/README.md`.
- Plan, decisions, gates: `docs/plan/README.md`, `docs/plan/decisions.md`,
  `docs/plan/delivery-roadmap.md`. Session handoffs: `docs/plan/HANDOFF-<date>.md`.
- Todos live in the delivery roadmap and `docs/STATUS.md`, nowhere else.
  Notes and scratch live under `tmp/<topic>-YYYY-MM-DD/`; never add loose
  top-level `tmp/` files, and never move a `tmp/` path cited by docs.
- This file plus `CLAUDE.md` hold only behavior rules. Detail lives in `docs/`.

## Running the Compiler

- Installed CLI entrypoint (after `uv sync`): `uv run a7 <args>`
- Repository compatibility wrapper: `uv run python main.py <args>`

Both invoke the same `a7.cli:main` (the Python package now lives at `a7/`,
not `src/`). Prefer `uv run a7` for examples that mirror end-user usage;
use the `main.py` wrapper when working from a fresh checkout without a
synced environment.

## No recursion in compiler internals

No-recursion rule for compiler internals: no new recursion in `a7/`. No
function may call itself directly or through a cycle of calls. Use explicit
stacks and worklists. `test/test_no_recursion.py` holds the ratchet: a
static call-graph scan with a shrinking allowlist of the recursive groups
that still exist; do not add to it. The historical census from 2026-09-17
listed the parser, type checker, type equality (`a7/types.py`), semantic
validator, safety pass, AST preprocessor, backend, module resolver, symbol
table dump and console formatter. Read `README.md` and `docs/STATUS.md` for
current traversal implementation and verification boundaries. Keep the scanner
and deep full-pipeline checks aligned; a passing subset at Python recursion
limit 100 does not prove all compiler internals are iterative. A7 source
recursion is a separate, banned construct (see "A7 Source Rules" below).

## Verification Commands

- Pytest (all, parallel): `PYTHONPATH=. uv run pytest -n 8`
- Pytest fast loop, no native builds:
  `PYTHONPATH=. uv run pytest -n 8 -m "not zig and not slow"`
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
- Compiler/package gate: `./run_all_tests.sh`
- Gate pytest workers: `A7_PYTEST_WORKERS=4 ./run_all_tests.sh` uses four
  workers. The default is eight; accepted values are integers 1 through 8.
  Keep eight logical CPUs available for other sessions by restricting gate
  CPU affinity with `taskset` on shared machines. Worker count alone does
  not limit the CPUs used by native compiler subprocesses.
- Complete local and CI release checks: `./run_release_checks.sh`
- Gate kill switch: `A7_CHECK_TIMEOUT` (default 3600s per check, 0 disables),
  `./run_all_tests.sh --timeout 300` for a shorter bound,
  `./run_all_tests.sh --only pytest` or `--skip bench` to run a subset.
  A hung check fails with `TIMEOUT` (exit 124) instead of hanging the gate.
  To kill a running gate started in background, kill its process tree
  (`ps aux | grep run_all_tests`, then `kill` the gate PID).
- Tmpfs hygiene: native tests share one Zig cache per run
  (`shared_zig_cache` in `test/conftest.py`); a full run leaves about 1.5G
  under `/tmp/pytest-of-*`. When `/tmp` is pressured, inspect file ages and
  active process references. Remove only verified stale directories owned
  by this task; preserve other sessions' files.
- Package build: `uv build`
- Wheel install smoke test (clean venv):
  `uv run python scripts/verify_wheel_install.py` (CI/release jobs run this
  with `--skip-build` after `uv build`)
- Docs site build: `cd site && bun install --frozen-lockfile && bun run build`
- Agent/curl.md docs preview: `cd site && bun run build && bun run preview`
  then check `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, and
  `/a7-py/docs/index.md`.

Examples are verified end-to-end against the Zig backend.
The Zig example E2E script must pass for any change to
`examples/`, codegen, or runtime behavior.

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

Applies to terminal answers and every document written into this
repository. Rules carry stable numbers; cite them in review.

- S1 Lead with the answer, then the evidence. No narration of what you
  are about to do, no recap of what was said, no closing summary of
  what the reader already read.
- S2 One idea per sentence. Short sentences, familiar words. Explain an
  unfamiliar term with a small example, or cut the term.
- S3 Name the mechanism, actor, or number. "The loader parses the file",
  "exits with code 2", "2387 passed". A sentence that could appear
  unchanged in another project's docs says nothing about this one; cut
  it or make it specific.
- S4 Structure only where structure exists. Tables for real columns,
  lists for real items, headings for real sections. No bold whole
  sentences, no call to action, no chatbot closings ("I hope this
  helps", "Let me know").
- S5 Match length to content. A one-line question gets a one-line
  answer. Do not pad to look thorough.
- S6 Every claim traceable. Attribute facts to file, line, command
  output, or source. Mark inference as inference and unchecked claims
  as unchecked. A confident sentence about which file or reviewer said
  something is a factual claim like any other.
- S7 Report failures plainly, with the output. No hedging a verified
  result, no softening a real failure. Say when a step was skipped.
- S8 No bare question to the user. Every question pairs simple words
  with a concrete example: what happens today, what changes, and a
  short before/after snippet or sample run. The user answers from the
  question alone, without reading the packet first.

## Anti-slop

A separate review pass, not a drafting instruction. Draft first, then
read once for these patterns only. Fix what matches. Preserve facts,
examples, structure, and deliberate rhythm. Weak tells count only with
other tells in the same passage. Never invent a detail to fix vagueness;
cut the sentence or mark the claim unchecked per S6.

- A1 Words. Never use: additionally, comprehensive, crucial, delve,
  facilitate, garner, intricate, interplay, journey, landscape (abstract
  sense), leverage, pivotal, robust, seamless, showcase, tapestry,
  testament, utilize, vibrant. Prefer the plain word: "use" for
  utilize/leverage/facilitate, "many" for numerous, "help" for
  facilitate, "is" or "has" for "serves as", "if" for "in the event
  that", "to" for "in order to", "because" for "due to the fact that".
  `scripts/check_docs_style.py` enforces this list on docs outside code
  fences.
- A2 Sentences. No binary contrasts ("It's not X. It's Y.", "Not just
  X, but Y"); state the point directly. No throat-clearing ("Here's the
  thing", "Let me be clear"), faux-insight setups ("What nobody tells
  you"), colon reveals ("The best part:"), dramatic fragments ("That's
  it. That's the whole thing"), or fake-profound endings. No importance
  puffery ("marks a pivotal moment", "a testament to") and no weasel
  attribution ("experts agree", "studies show"); name the source or
  delete the sentence. No synonym cycling: pick one name for a thing and
  repeat it. No forced groups of three: use the natural number of items.
  Active voice with a named actor; passive only when the actor is
  unknown or does not matter. Cut adverbs that prop up weak verbs
  ("significantly improves" becomes the measured delta) and stacked
  hedges ("could potentially possibly" becomes "may").
- A3 Structure. No emojis in code, docs, or terminal output unless asked
  or a fixture requires them. No boilerplate docstrings that restate a
  name. State the invariant or delete the comment. No narrator comments
  ("Obviously", "Clearly", "Simply", "Just", "Note that"); give the
  reason instead. No praise or hype adjectives for the work, the
  question, or the user. No generic conclusions ("The future looks
  bright"); state specific plans or facts.
- A4 Code. No new abstraction with one caller, no wrapper nobody asked
  for, no fallback behavior outside the task. No defensive checks or
  try/catch on trusted paths, no cast that only silences a type error.
  No error hidden behind false, nil, or an empty result. A cleanup pass
  keeps behavior unchanged; small focused edits.
- A5 Use least-privilege tool calls. Do not ask for broad allows such as
  `Bash python3 -c *` or `Read //tmp/**` wildcards; request the narrow path
  or command the step needs.

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

When language features, backends, or user-facing behavior change, update:

1. **docs/CHANGELOG.md** — add a short release-facing entry
2. **README.md** — usage, feature lists, examples
3. **docs/SPEC.md** — language semantics or syntax
4. **docs/STATUS.md** — close or open gaps and priorities
5. **site/public/llms.txt**, **site/public/llms-full.txt**, and
   **site/public/docs/** — update agent/curl.md entry points when site
   navigation, release commands, CLI behavior, or public docs structure
   changes; run `(cd site && bun run sync:exports)` after website content
   edits so tracked exports stay current

Keep examples and docs aligned across `README.md`, `docs/SPEC.md`,
`docs/CHANGELOG.md`, `docs/STATUS.md`, `site/public/llms.txt`,
`site/public/llms-full.txt`, and `site/public/docs/` — drift between them is
treated as a bug.

## Subagents

Use GLM-5.3 for substantive external reviews, with at most five runs in parallel.
Use GLM-5.3-Flash for very small tasks, with at most 25 runs in parallel. Give
each run a detailed prompt with its source snapshot, file scope, required
checks, evidence boundary and expected output. Count active runs by model before
starting another; failed or interrupted runs are not completed reviews.

Start every external CLI prompt with this exact role and boundary:

> You are an external reviewer invoked by a controlling Codex session. You are not the primary coordinator. Your output is advisory. You and your sub-agents may use this run's built-in sub-agent feature. Do not directly or indirectly launch any model or agent CLI, including another instance of this CLI, unless the user explicitly requests nested CLI orchestration.

Keep one reviewer identity throughout the review. The controller may start
independent sibling CLI reviews within the model limits above. Keep normal tools,
web search and built-in subagent capabilities enabled. Do not impose a turn count,
execution deadline or model time limit unless the user requests one. Let reviewers
finish naturally; preserve provider failures and tool limitations as evidence.

Use subagents for independent workstreams. Dispatch code, tests, docs,
scripts, examples/site, and hygiene work in parallel through subagents when
the streams touch different files. Give each worker one file set; file sets
must not overlap. Tell workers to read before editing and to check
`git status --porcelain` on their files before the first edit. Each worker
runs its own gate before reporting done: `pytest` for code and tests,
`build_examples.py` for examples and codegen, `bun run check` for site work.
The parent session consolidates worker results and runs the full gate for
non-trivial changes.

## Security Caveat

`a7-py` is **not** a sandbox for untrusted source. The compiler emits Zig
that is then built and run with the host toolchain; compiled A7 programs can do
anything the host environment permits. Only compile and execute A7 source you
trust.
