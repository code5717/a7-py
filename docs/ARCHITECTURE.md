# A7 compiler architecture

A7 is an ahead-of-time compiler from `.a7` source to Zig source, then to a
native binary via the host Zig toolchain. The Python compiler is the entire
implementation; there is no separate runtime.

Pipeline (orchestrated by `a7/compile.py: A7Compiler`):

1. `a7/tokens.py` — Tokenizer. Handles single-token generics (`$T`), nested
   comments, multiple number formats.
2. `a7/parser.py` — Worklist-driven parser with precedence climbing.
   Produces nodes defined in `a7/ast_nodes.py`.
3. `a7/passes/` — Semantic passes run in order:
   `name_resolution.py` → `type_checker.py` → `semantic_validator.py` →
   `safety.py` (internal safety proof planning).
   Shared state lives in `a7/semantic_context.py` and `a7/symbol_table.py`;
   type machinery lives in `a7/types.py` (including generic constraint
   resolution). Shared integer width/range tables also live in `a7/types.py`;
   constant folding lives in `a7/exact_constants.py`, the only numeric
   folder.
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

## Traversal candidates and qualification

Compiler internals must use explicit stacks and worklists. The static scan in
`test/test_no_recursion.py` limits the remaining recursive groups.
The component snapshots below were combined in frozen manifest `04330ece`.
It passed 3,602 tests with one expected failure and all native example profiles.
The secrets check failed because the snapshot lacked Git metadata. After an
exact-manifest index was added, secrets and all skipped release checks passed
without source changes. V1 remains incomplete. The
[qualification record](audits/2026-10-07/qualification.md) identifies the
checkpoint's source and checks.

| Component | Component review snapshot SHA256 prefix | Review evidence |
| --- | --- | --- |
| Parser | `58c4448e` | 576 focused tests; 462 source comparisons; 111 independent review cases |
| Type checker | `7b5d91cc` | 1,246 focused tests; 648 source comparisons, including 612 that reached checking |
| Zig backend | `3aaf327e` | 184 focused tests; 171 source/profile comparisons; 42 isolated AST comparisons; 51 native examples in both debug and release |
| AST methods | `21c85515` | 129 focused tests; baseline comparisons of equality, display and cycle behavior |
| Safety statement traversal | `e339c46f` | 258 focused tests; 228 state comparisons; 195 source/profile comparisons; 40 independent compile runs |

Later array-fitting and compact-provenance repairs are included in the combined
manifest: parser `9da02ec6`, checker `a87ebdfd` and safety `338ecedb`.
The [follow-up record](audits/2026-10-07/iterative-followup-verification.json)
identifies the complete frozen manifest and recovery commands.

The combined scan reports no recursive groups, deepcopy calls or recursive
generated dataclass methods. The conservative unresolved-call scan agrees.
An empty scan does not establish that every dynamic compiler execution is
iterative. The scan also excludes fields annotated `Any` or
`object` from its generated-method analysis. Reproduce the source scan with
`python test/norec_scan.py`.

Parser statement, expression, type and pattern traversal use suspended frames.
The driver resumes one child at a time and returns its result to its parent.
It forwards child exceptions into the parent so generic-literal lookahead can
recover from a failed type parse. Token order, precedence, header state and the
existing logical nesting limit of 256 remain unchanged.

Type-checker statements use a worklist for blocks, branches, loops and match
arms. Continuations preserve diagnostic order; a separate region stack restores
the scopes and facts protected by the original cleanup paths. Type resolution
uses suspended frames for compound types and alias dependencies. Alias caches
use declaration identity, so an inner alias keeps its own type when it shares
an outer alias's name. Expression and pattern checking use a separate worklist
that preserves contextual initializer fitting, exact-value handling and
match-arm scope cleanup.

Zig statement, expression and type emission use separate worklists. They retain
lexical names, indentation, loop labels, captures, helper selection and emission
order. The expression driver forwards child errors into parent handlers,
including the match-pattern diagnostic wrapper. Candidate source comparisons
check emitted Zig byte-for-byte against the saved backend. Native example
checks cover all 51 examples in debug, release and fast on the combined snapshot.

Safety expression evaluation uses an explicit event stack. It preserves
left-to-right operand order and applies each argument's borrowing effects before
the next one. Exact callee replay and global body effects run after argument
evaluation. Expression facts retain the value observed at that evaluation point
even when a later operand invalidates a symbol fact. Safety statements use
suspended frames with child-error forwarding. Independent deep block, branch,
loop, match and defer sources preserve diagnostics and emitted Zig at Python
recursion limit 100. Compact allocation graphs replace enumerated fresh-origin
paths. The depth-64 branching factory retains 196 graph nodes and its guarded
native control passes in all profiles. This closes the observed expansion for
that source family; it does not prove a universal analysis complexity bound.

AST structural equality and repr consume declared fields with explicit
worklists. Dynamic compiler annotations stay outside dataclass comparison and
display. Repr keeps path-local cycle markers and field-read order; equality
preserves class checks and container comparison order. Custom external Python
payloads with recursively reentrant methods are outside this traversal guarantee.
Container contents are captured before rendering their elements. A custom
element that mutates its container during display can therefore produce a
different result from Python's live-container repr. Compiler-created payloads
do not use those callbacks. `ASTNode.literal_value` remains an `Any` field;
arbitrary third-party equality and repr methods placed there are not qualified.
