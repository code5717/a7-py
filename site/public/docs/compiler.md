# Compiler and Tests

## Pipeline

```text
Source (.a7) -> Tokenizer -> Parser -> Semantic Analysis -> Safety Proof Plan -> AST Preprocessing -> Backend Codegen -> Zig output
```

## Backends

- Zig backend emits Zig source.
- `scripts/build_examples.py` builds debug and release artifacts for Zig.

## Verification Layers

```bash
PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
uv run python scripts/verify_error_stages.py
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
./run_all_tests.sh
```

## Backend Parity

`scripts/verify_examples_e2e.py` compiles examples through Zig, builds them, runs them, and compares runtime output.

Current selected coverage includes control flow, strings, labeled loops, function pointers, slice fields, indexed slice iteration, match statements and expressions, string slice iteration, defer unwind order, untagged unions, generic function specialization, enum match expressions, heap struct allocation, and 2D/3D nested fixed arrays.
