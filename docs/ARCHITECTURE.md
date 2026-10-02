# A7 compiler architecture

A7 is an ahead-of-time compiler from `.a7` source to Zig source, then to a
native binary via the host Zig toolchain. The Python compiler is the entire
implementation; there is no separate runtime.

Pipeline (orchestrated by `a7/compile.py: A7Compiler`):

1. `a7/tokens.py` — Tokenizer. Handles single-token generics (`$T`), nested
   comments, multiple number formats.
2. `a7/parser.py` — Recursive-descent parser with precedence climbing.
   Produces nodes defined in `a7/ast_nodes.py`.
3. `a7/passes/` — Semantic passes run in order:
   `name_resolution.py` → `type_checker.py` → `semantic_validator.py` →
   `safety.py` (internal safety proof planning).
   Shared state lives in `a7/semantic_context.py` and `a7/symbol_table.py`;
   type machinery lives in `a7/types.py` (including generic constraint
   resolution). Shared integer width/range tables also live in `a7/types.py`;
   constant folding lives in `a7/const_eval.py` (preprocessor) and
   `a7/exact_constants.py` (type checker).
4. `a7/ast_preprocessor.py` — sub-passes for stdlib resolution, struct init
   normalization, mutation/usage analysis, inference, shadowing, hoisting, and
   constant folding. AST traversal helpers are shared via
   `a7/formatters/scope_walk.py` for scope walks.
5. `a7/backends/` — Backend registry (`__init__.py`, `base.py`) plus the
   `zig.py` backend that emits Zig source.

Surrounding modules: `a7/cli.py` (argparse entrypoint → `compile.A7Compiler`,
including the Zig toolchain lookup), `a7/module_resolver.py` (import
resolution; virtual `std/*` plus file-backed local imports that are merged
into the single Zig output), `a7/stdlib/` (registry of `std/io` and
`std/math`), `a7/formatters/` (console/JSON/markdown output for
tokens/AST/semantic dumps and the `--doc-out` report), `a7/errors.py`
(typed errors and rich display).

No-recursion rule: see "No recursion in compiler internals" in `AGENTS.md`.
`test/test_no_recursion.py` holds the ratchet.
