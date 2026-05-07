# A7 Programming Language Compiler

A Python-based compiler for A7, a statically-typed systems programming language. A7 combines the simplicity of C-style syntax with modern features like generics, type inference, and property-based pointer operations.

The compiler features a complete pipeline: tokenizer, parser, 3-pass semantic analysis, AST preprocessing, and pluggable code generation backends (Zig and C).

## Inspired By

A7 draws inspiration from practical systems programming languages that prioritize clarity and programmer productivity:

- **[JAI](https://www.youtube.com/playlist?list=PLmV5I2fxaiCKfxMBrNsU1kgKJXD3PkyxO)** by Jonathan Blow - Design philosophy and compile-time features
- **[Odin](https://odin-lang.org/)** by Ginger Bill - Simplicity and explicit memory management

## Quick Start

**Requirements:** Python 3.13+ and [uv](https://docs.astral.sh/uv/) (recommended package manager). Install [Zig](https://ziglang.org/) to build and run generated Zig/C outputs.

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/macOS
# or: pip install uv

# Clone and setup
git clone <repository-url>
cd a7-py
uv sync
```

## Usage

Run from the repository checkout:

Compile an A7 program to Zig (default backend):
```bash
uv run python main.py examples/001_hello.a7
# Output: examples/001_hello.zig
```

Compile an A7 program to C:
```bash
uv run python main.py --backend c examples/001_hello.a7
# Output: examples/001_hello.c
```

Modes and output formats:
```bash
uv run python main.py --mode tokens examples/006_if.a7                     # Tokens only
uv run python main.py --mode ast examples/004_func.a7                      # Tokens + AST
uv run python main.py --mode semantic examples/009_struct.a7               # Through semantic passes
uv run python main.py --mode pipeline examples/014_generics.a7             # Full pipeline, no file write
uv run python main.py --format json examples/014_generics.a7               # Machine-readable JSON
uv run python main.py examples/001_hello.a7 --mode compile --doc-out auto  # Compile + auto docs
uv run python main.py examples/001_hello.a7 --mode compile --doc-out out.md  # Compile + custom docs
uv run python main.py --mode doc examples/001_hello.a7                     # Doc-only run
uv run python main.py --verbose examples/009_struct.a7                     # Full pipeline details
```

Use the installed console script after `uv sync`:

```bash
uv run a7 examples/001_hello.a7
uv run a7 --backend c examples/001_hello.a7
```

Exit codes for automation:
```text
0 success, 2 usage, 3 io, 4 tokenize, 5 parse, 6 semantic, 7 codegen, 8 internal
```

Run tests:
```bash
PYTHONPATH=. uv run pytest                         # All tests
PYTHONPATH=. uv run pytest test/test_tokenizer.py  # Specific test file
PYTHONPATH=. uv run pytest -k "generic" -v         # Targeted tests
uv run python scripts/verify_examples_e2e.py       # Compile/build/run + output checks for all examples
uv run python scripts/verify_examples_e2e_c.py     # Same flow via C backend + zig cc
uv run python scripts/verify_error_stages.py       # Error-stage audit across modes and formats
uv run python scripts/build_examples.py --profile debug --backend both --clean
uv run python scripts/build_examples.py --profile release --backend both --clean
./run_all_tests.sh                                 # Full release-oriented local gate
```

## Debug and Release Builds

The compiler emits Zig or C source. `scripts/build_examples.py` is the native artifact builder used for release smoke checks:

```bash
uv run python scripts/build_examples.py --profile debug --backend both --clean
uv run python scripts/build_examples.py --profile release --backend both --clean
```

Artifacts are written under `build/debug/` and `build/release/`, split by backend:

```text
build/<profile>/zig/src/*.zig
build/<profile>/zig/bin/*
build/<profile>/c/src/*.c
build/<profile>/c/bin/*
```

Each built binary is executed and compared with `test/fixtures/golden_outputs/*.out`.

## Packaging

Build the Python package:

```bash
uv build
```

The installed CLI entrypoint is `a7`:

```bash
uv run a7 --help
```

## Compilation Pipeline

```
Source (.a7) → Tokenizer → Parser → Semantic Analysis (3-pass) → AST Preprocessing → Backend Codegen (Zig/C) → Output (.zig/.c)
```

1. **Tokenizer**. Lexes source into tokens. Handles single-token generics (`$T`), nested comments, and number formats.
2. **Parser**. Uses recursive descent with precedence climbing. Parses all A7 constructs.
3. **Semantic Analysis**. Runs name resolution, type checking with inference, and control flow validation.
4. **AST Preprocessing**. Runs 9 sub-passes: sugar lowering, stdlib resolution, mutation and usage analysis, type inference, shadowing resolution, function hoisting, and constant folding.
5. **Backend Code Generation**. Translates AST to valid Zig or C source code.

All AST traversals are iterative with no recursion. The pipeline works with Python's recursion limit set to 100.

## What Works

- **Types**: Primitives, arrays, slices, pointers, generics, function types, inline structs
- **Declarations**: Functions, structs, enums, unions, variables, constants, type aliases
- **Control Flow**: if/else, while, for loops, for-in, labeled loops with break/continue, match statements, defer
- **Expressions**: All operators with proper precedence, casts, if-expressions, struct/array literals
- **Memory**: Property-based pointer syntax (`.adr`, `.val`), new/delete, defer cleanup
- **Imports**: Module system with named imports, using imports, aliased imports
- **Generics**: Type parameters (`$T`), constraints, type sets, generic structs
- **Code Generation**: A7 → Zig and A7 → C backends
- **Standard Library**: Registry with io and math modules, backend-specific mappings
- **Error Messages**: Rich formatting with source context and structured error types

## Project Status

- Test status depends on current branch state. Check with `PYTHONPATH=. uv run pytest --tb=no -q`.
- Example end-to-end verification is available for both backends:
  - `uv run python scripts/verify_examples_e2e.py`
  - `uv run python scripts/verify_examples_e2e_c.py`
- Debug/release artifact verification is available through `scripts/build_examples.py`.
- Parser covers the implemented language surface, but spec/implementation gaps remain tracked in `MISSING_FEATURES.md`.
- Zig backend handles the current example suite and most AST node types; unsupported source constructs should continue moving to compiler-side diagnostics.
- C backend targets C11 and is validated with `zig cc`
- This compiler is not a sandbox. Do not compile and execute untrusted A7 source.

## Learn More

- Documentation website: `https://airbus5717.github.io/a7-py/`
- `docs/SPEC.md` - Language specification
- `RELEASE.md` - Release/debug build checklist
- `SECURITY.md` - Security policy and trust boundary
- `RELEASE_READINESS_REVIEW.md` - Current release-readiness audit
- `examples/` - 36 sample programs
- `MISSING_FEATURES.md` - Feature status and roadmap
- `CHANGELOG.md` - Change history

## Docs Development

```bash
cd site
npm install
npm run dev
```

---

Work in progress. Contributions welcome!
