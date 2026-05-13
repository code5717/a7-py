# FAQ

Short answers to questions that come up across issues, PRs, and agent
sessions.

## Is A7 ready to use?

For exploration and example-driven learning, yes. For production, no. The
language model is stable enough to write the included 46 example programs
and have them compile, link, and run reliably. Many surface features
documented in `docs/SPEC.md` are still parsed-only or reserved — see
[Features](/a7-py/ref/features) for the line between supported and reserved.

## What does A7 stand for?

It's a project codename, not an acronym. Treat it as a name.

## Why Python for the compiler?

The compiler is the contract; performance is the Zig backend's job. Python
makes the pipeline introspectable, easy to instrument, and easy for agents
to read. The compiler can be replaced with a faster one once the language
stabilises.

## Why iterative traversal in the compiler?

The same reason A7 source rejects recursion: stack-safety and predictable
behaviour. Semantic passes, AST preprocessing, formatter walks, and the
backend's binary-expression emission all use explicit stacks. CI enforces
Python recursion limit 100. The parser is the one exception (recursive
descent) and is structured so that its depth is bounded by source nesting.

## Can I use recursion?

In A7 source: no. The compiler rejects direct, mutual, and
function-pointer-alias-cycle recursion. Rewrite to loops or explicit stacks
— see examples 025 and 026.

In the Python compiler: avoid it for new code. Compiler internals are
iterative by invariant.

## Why no heap fixed arrays?

`new [N]T` is currently rejected by the compiler. The language model for
heap-allocated fixed arrays hasn't been defined yet, so the compiler fails
closed rather than emit something we'd have to change. Use stack arrays
(`buf: [N]T`) or slices.

## How do I report a bug?

Open an issue at <https://github.com/Airbus5717/a7-py/issues>. Include:

- A7 source that triggers the bug (minimal repro preferred).
- CLI command (mode + flags).
- Output, including exit code.
- Compiler version (`uv run a7 --version` when wired; for now,
  `git rev-parse HEAD`).

## How do I use A7 from a coding agent?

Fetch `https://code5717.github.io/a7-py/llms-full.txt`. It contains every
page of this site concatenated. From there, raw markdown is one fetch away
at `/a7-py/docs/<slug>.md`. See [Getting Started → agents](/a7-py/learn/start#agents).

## Is there a language server / LSP?

Not yet. The compiler's `--format json` mode is the closest stand-in — it
emits structured diagnostics and AST data that an editor or agent can parse.

## What's the relationship between A7 and Zig?

A7 lowers to Zig source. The Zig toolchain compiles that source to a native
binary. A7 is not a Zig dialect — the syntax, ownership rules, and
constraints differ. We pin Zig 0.16.0 in CI.

## Why no package registry?

Out of scope. The language is not stable enough yet, and registries are a
multi-year commitment we're not ready for. Vendor-and-commit or use git
submodules.

## Are the docs and code in sync?

They have to be. The docs site builds in CI; any drift between
`README.md`, `docs/SPEC.md`, `docs/STATUS.md`, and the public docs site is
treated as a bug. Run `./run_all_tests.sh` to verify the full gate locally.
