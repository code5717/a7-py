# Python API

The compiler is a normal Python package — `a7/` — that you can import and
drive programmatically. The CLI (`a7.cli:main`) is the canonical entry
point, but every stage is also reachable as a module.

## Top-level pipeline

```python
from a7.compile import A7Compiler

compiler = A7Compiler(source_path="examples/001_hello.a7")
result = compiler.run()         # full pipeline → CompileResult
if result.zig_source:
    print(result.zig_source)
```

`A7Compiler` orchestrates the full pipeline. The result carries source,
tokens, AST, semantic context, generated Zig source, and any diagnostics.

## Individual stages

The pipeline runs the following modules in order. Each one is callable.

| Stage | Module | Notes |
|---|---|---|
| Tokenize | `a7.tokens` | Handles `$T` single-token generics, nested comments |
| Parse | `a7.parser` | Recursive descent with precedence climbing |
| Name resolution | `a7.passes.name_resolution` | Symbol table population |
| Type checking | `a7.passes.type_checker` | Type inference, monomorphization |
| Semantic validation | `a7.passes.semantic_validator` | Recursion rejection, etc. |
| Safety proof planning | `a7.safety` | Cast / div-mod / index obligations |
| AST preprocessing | `a7.ast_preprocessor` | Hoisting, folding, normalization |
| Code generation | `a7.backends.zig` | Zig source emission |

## Diagnostics

```python
from a7.errors import A7Error

for err in result.errors:
    assert isinstance(err, A7Error)
    print(err.kind, err.message, err.span)
```

`A7Error` is the structured diagnostic. The CLI formats these for human or
JSON output; the API hands them back directly.

## Symbol table & types

```python
from a7.semantic_context import SemanticContext

ctx: SemanticContext = result.semantic_context
for name, sym in ctx.symbol_table.iter_globals():
    print(name, sym.kind, sym.type)
```

`SemanticContext` is the shared state across passes. After a successful
run it carries every resolved symbol, type, and constraint.

## Module resolution

```python
from a7.module_resolver import ModuleResolver

resolver = ModuleResolver(...)
mod = resolver.resolve("std/io")
```

`std/*` modules are virtual — resolved directly from the stdlib registry
in `a7.stdlib`. File-backed local imports fail closed before codegen if
they can't be resolved.

## Backends

```python
from a7.backends import get_backend

backend = get_backend("zig")          # only public backend right now
zig_source = backend.emit(result.ast, result.semantic_context)
```

Backends register themselves via `a7.backends.__init__`. The Zig backend
is currently the only public one.

## Iterative-traversal invariant

The compiler enforces iterative traversal across semantic passes, AST
preprocessing, formatter/reporting walks, and the binary-expression
emission paths. CI runs the supported pipeline at Python recursion limit
100 to catch any deep-recursion regressions. Don't reintroduce recursion
in compiler internals — `test/test_iterative_traversal.py` will fail.

The parser is recursive descent and is allowed to recurse; its depth is
bounded by source syntactic nesting.

## Custom toolchains

If you want to wrap the compiler in your own tool:

```python
from a7.compile import A7Compiler
from a7.formatters import to_json

c = A7Compiler(source_text=read_source())
result = c.run(stop_at="semantic")     # any pipeline stage
print(to_json(result))
```

`stop_at` accepts `"tokens"`, `"ast"`, `"semantic"`, or `"codegen"` (the
default), matching the CLI `--mode` flag.

## Stable surfaces

Treat these as supported:

- `a7.compile.A7Compiler`
- `a7.cli.main`
- `a7.errors.A7Error` and subclasses
- `a7.backends.get_backend`
- The JSON output shape of every CLI `--mode`

Treat anything under `a7.passes.*` and `a7.ast_nodes` as internal — names
may change between minor releases.
