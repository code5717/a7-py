# Pipeline

Per-stage detail for the A7 compile pipeline. Each stage takes the previous
stage's output, runs an iterative traversal, and hands off to the next.

## 1. Tokenize — `a7/tokens.py`

Turns ASCII source into a token stream. Handles:

- All keywords, operators, punctuation.
- Integer literals in decimal, hex (`0x`), octal (`0o`), binary (`0b`),
  with `_` separators.
- Float literals (`3.14`, `2.7e10`, `.5`, `1.`).
- Char literals with escapes (`\n \t \\ \' \x41`).
- String literals with escapes.
- Single-token generic parameters: `$T` is one token, not two.
- Nested block comments `/* /* */ */`.
- Hard rejection of tabs and non-ASCII bytes.

Output: a list of tokens with source spans. Exit code on failure: **4**.

## 2. Parse — `a7/parser.py`

Recursive descent with operator precedence climbing. Produces the AST
defined in `a7/ast_nodes.py`. Parses every public language form, including
some that are reserved (multiple-declaration binds, variadic params) but
not lowered by the backend.

Output: an AST root node. Exit code on failure: **5**.

## 3. Name resolution — `a7/passes/name_resolution.py`

Builds the symbol table (`a7/symbol_table.py`). Resolves every identifier
to its declaration. Detects redeclaration, undeclared name, and shadowing
errors. Uses an explicit-stack traversal over the AST.

## 4. Type checking — `a7/passes/type_checker.py`

Type inference and unification. Handles:

- Numeric literal type inference (default `i32`, refined by context).
- Type annotations and explicit casts via `cast(T, v)`.
- Generic specialization at call sites (per-site monomorphization).
- Struct field types, enum variant tags, union field types.

Uses `a7/types.py` for the type lattice and `a7/generics.py` for
specialization machinery.

## 5. Semantic validation — `a7/passes/semantic_validator.py`

Cross-cutting checks that the type checker doesn't do:

- **Recursion rejection.** Direct, mutual, and function-pointer
  alias-cycle recursion is reported as a compile-time error. Reachability
  is computed iteratively with a worklist.
- **Match exhaustiveness** on `bool` and `enum`.
- **Pattern type checks** inside `match` arms.
- **Backend-plan approval** for risky operations — handed to the safety
  proof planner.

Any failure in passes 3–5 surfaces as exit code **6**.

## 6. Safety proof planning — `a7/safety.py`

Plans safety obligations for risky operations *before* the backend emits
them. Currently covers:

- **Casts** — proves or rejects narrowing / signed-unsigned conversions.
- **Division / modulo** — denominator non-zero.
- **Indexing / slicing** — bounds against the operand's length.
- **Reference dereferences** — non-nil at use.
- **Direct use after `del`** — rejected at the AST level.

The safety planner can request the backend to insert runtime checks for
some operations; it can also refuse the program outright. Exit code on
refusal: **6**.

## 7. AST preprocessing — `a7/ast_preprocessor.py`

A sequence of small sub-passes that normalize the AST before codegen:

- Stdlib resolution — bind `std/io`-style imports to the registry.
- Struct init normalization — order fields, fill defaults.
- Mutation and usage analysis — `var` vs `const` and unused warnings.
- Inference refinement.
- Shadowing resolution.
- Function hoisting.
- Constant folding.

All sub-passes use explicit-stack AST traversal.

## 8. Zig code generation — `a7/backends/zig.py`

Walks the prepared AST and emits Zig source. The Zig output is meant to
be **readable** — it preserves source structure, function names, and
struct layouts where it can. Binary-expression emission uses an explicit
stack. Statement and some non-binary expression emission still use
visitor-style recursion in places.

The output is written to `<source>.zig` next to the original `.a7` source.
Exit code on failure: **7**.

## 9. Build — Zig toolchain

The compiler does not run Zig itself. Use:

```bash
zig build-exe -O ReleaseFast file.zig
```

For the full example suite:

```bash
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

## Where state lives

| Module | What it owns |
|---|---|
| `a7/semantic_context.py` | The threaded `SemanticContext` |
| `a7/symbol_table.py` | Symbols, scopes, lookup |
| `a7/types.py` | Type lattice + unification |
| `a7/generics.py` | Specialization registry |
| `a7/safety.py` | Obligations, proofs, plans |
| `a7/module_resolver.py` | Import resolution (std/* + file-backed) |

Each module is reachable from `a7.compile.A7Compiler` for programmatic
use — see [API](/a7-py/ref/api).
