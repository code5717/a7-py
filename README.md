# A7 Programming Language Compiler

A Python-based compiler for A7, a statically-typed systems programming language. A7 combines the simplicity of C-style syntax with modern features like generics, type inference, and compiler-managed reference operations.

The compiler features a complete pipeline: tokenizer, parser, semantic analysis, internal safety proof planning, AST preprocessing, and Zig code generation.

## Inspired By

A7 draws inspiration from practical systems programming languages that prioritize clarity and programmer productivity:

- **[JAI](https://www.youtube.com/playlist?list=PLmV5I2fxaiCKfxMBrNsU1kgKJXD3PkyxO)** by Jonathan Blow - Design philosophy and compile-time features
- **[Odin](https://odin-lang.org/)** by Ginger Bill - Simplicity and explicit memory management

## Quick Start

**Requirements:** Python 3.13+ and [uv](https://docs.astral.sh/uv/) (recommended package manager). Install [Zig 0.16.0](https://ziglang.org/download/) to build and run generated Zig output; CI pins the same version for repeatable artifact checks.

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

Learn the current language from one commented file:
```bash
uv run python main.py examples/037_language_tour.a7
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
uv run python scripts/verify_error_stages.py       # Error-stage audit across modes and formats
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
./run_all_tests.sh                                 # Full release-oriented local gate
```

## Debug and Release Builds

The compiler emits Zig source. `scripts/build_examples.py` is the native artifact builder used for release smoke checks:

```bash
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

Artifacts are written under `build/debug/` and `build/release/`:

```text
build/<profile>/zig/src/*.zig
build/<profile>/zig/bin/*
```

Each built binary is executed and compared with `test/fixtures/golden_outputs/*.out`.

## Packaging

Build the Python package:

```bash
rm -rf dist
uv build
```

Cleaning `dist/` first prevents stale older package artifacts from being mixed
with the current release build.

Generate a checksum manifest for release artifacts:

```bash
uv run python scripts/generate_release_manifest.py dist --output dist/SHA256SUMS
uv run python scripts/verify_release_manifest.py dist/SHA256SUMS
uv run python scripts/verify_archive_contents.py dist/a7-docs-site.tar.gz --require dist/llms.txt --require dist/llms-full.txt
```

The installed CLI entrypoint is `a7`:

```bash
uv run a7 --help
```

Release tags build distributions and attach them to the draft GitHub release.
There is no package-registry publishing job in the current workflow.

## Compilation Pipeline

```
Source (.a7) → Tokenizer → Parser → Semantic Analysis → Safety Proof Planning → AST Preprocessing → Zig Codegen → Output (.zig)
```

1. **Tokenizer**. Lexes source into tokens. Handles single-token generics (`$T`), nested comments, and number formats.
2. **Parser**. Uses recursive descent with precedence climbing. Parses all A7 constructs.
3. **Semantic Analysis**. Runs name resolution, base type checking with inference, control flow validation, and recursion rejection.
4. **Safety Proof Planning**. Proves or rejects risky operations such as casts, division/modulo, indexing/slicing, reference dereferences, and direct use after `del` before backend lowering.
5. **AST Preprocessing**. Runs stdlib resolution, struct init normalization, mutation and usage analysis, type inference, shadowing resolution, function hoisting, and constant folding.
6. **Backend Code Generation**. Translates approved AST operations to valid Zig source code.

Semantic analysis, AST preprocessing, formatter/reporting AST walks, and backend binary-expression emission use explicit stacks. The parser is recursive descent, and backend statement/non-binary expression generation still uses visitor-style recursive emission in some paths. Current low-recursion coverage validates the supported pipeline at Python recursion limit 100 for representative programs. A7 source recursion, including local function-pointer aliases and higher-order callback trampolines, is rejected during semantic validation; use loops, explicit stacks, or index-based worklists instead.

## Integer Type Guidance

Use `usize` for sizes, lengths, capacities, allocation byte counts, and array/slice/string indices. Index and slice-bound variables are required to be `usize`; non-negative integer literals are accepted for simple indexing. `usize` maps directly to Zig `usize`.

Use `isize` only when the value is a signed pointer-sized offset or a difference between positions. It exists for pointer-adjacent signed math, not as the default signed integer type.

Use fixed-width integers such as `i32`, `i64`, `u32`, or `u64` when the data itself has that width or range. Small arithmetic examples can use `i32`; counters and indexes should usually use `usize`.

## What Works

- **Types**: Primitives, arrays, slices, pointers, generics, raw and aliased function types, inline struct return values
- **Declarations**: Functions, structs, enums, unions, variables, constants, type aliases
- **Control Flow**: if/else, while, for loops, for-in, labeled loops with break/continue, match statements, defer
- **Function Rules**: Direct, mutual, alias-mediated, and callback-trampoline recursion are semantic errors
- **Expressions**: All operators with proper precedence, fixed-array `+` for same-shape numeric arrays, casts, if-expressions, struct/array literals, untagged union field literals/access
- **Memory**: `ref` parameters use ordinary lvalue arguments, ref struct fields
  are accessed directly after nil-proofing, and scalar/struct `new` plus `del`
  support defer cleanup. Heap fixed arrays (`new [N]T`) are rejected until the
  language model is defined.
- **Safety proofing**: casts, division/modulo, bounds-sensitive indexing/slicing,
  reference dereferences, operation-specific backend approvals, and direct use
  after `del` are checked by internal facts before Zig emission.
- **Imports**: Virtual `std/io` and `std/math` modules with aliases; simple file-backed alias imports can lower into the same generated Zig file
- **Generics**: Type parameters (`$T`), constraints, type sets, generic structs, generic struct literals, and simple top-level generic function calls
- **Code Generation**: A7 → Zig, with generated `std/io` print helpers that preserve stdout/stderr on current Zig toolchains
- **Standard Library**: Registry with io and math modules, backend-specific mappings
- **Error Messages**: Rich formatting with source context and structured error types

## Project Status

- Test status depends on current branch state. Check with `PYTHONPATH=. uv run pytest --tb=no -q`.
- Example end-to-end verification is available through
  `uv run python scripts/verify_examples_e2e.py`.
- Debug/release artifact verification is available through `scripts/build_examples.py`.
- Tag releases attach package artifacts to a draft GitHub release.
- Parser covers the implemented language surface, but spec/implementation gaps remain tracked in `docs/STATUS.md`.
- Zig backend handles the current example suite and most AST node types; unsupported source constructs should continue moving to compiler-side diagnostics.
- This compiler is not a sandbox. Do not compile and execute untrusted A7 source.

## Learn More

- Documentation website: `https://code5717.github.io/a7-py/`
- Agent/curl.md docs entry point: `https://code5717.github.io/a7-py/llms.txt`
- Agent docs index: `https://code5717.github.io/a7-py/docs/index.md`
- Full agent context: `https://code5717.github.io/a7-py/llms-full.txt`
- `docs/SPEC.md` - Language specification
- `docs/SAFETY_CONTRACT.md` - Compiler safety contract and proof/backend-plan invariants
- `docs/STATUS.md` - Current gaps, priorities, and roadmap
- `docs/RELEASE.md` - Release/debug build checklist
- `docs/SECURITY.md` - Security policy and trust boundary
- `examples/` - 43 sample programs
- `docs/CHANGELOG.md` - Change history
- `docs/ERROR_ANALYSIS.md` - Historical error-analysis snapshot, not current status

## Docs Development

```bash
cd site
npm ci
npm run dev
```

---

Work in progress. Contributions welcome!
