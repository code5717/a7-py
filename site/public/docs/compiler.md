# Compiler and Tests

## Pipeline

```text
Source (.a7) -> Tokenizer -> Parser -> Semantic Analysis -> AST Preprocessing -> Backend Codegen -> Zig/C output
```

## Backends

- Zig backend emits Zig source.
- C backend emits C11 source and is validated with `zig cc`.
- `scripts/build_examples.py` builds debug and release artifacts for both backends.

## Verification Layers

```bash
PYTHONPATH=. uv run pytest --tb=no -q
uv run python scripts/verify_examples_e2e.py
uv run python scripts/verify_examples_e2e_c.py
uv run python scripts/verify_backend_parity.py
uv run python scripts/verify_error_stages.py
uv run python scripts/build_examples.py --profile debug --backend both --clean
uv run python scripts/build_examples.py --profile release --backend both --clean
./run_all_tests.sh
```

## Backend Parity

`scripts/verify_backend_parity.py` compiles selected non-example programs through Zig and C, builds them, runs them, and compares runtime output.

Current selected coverage includes control flow, strings, labeled loops, function pointers, slice fields, indexed slice iteration, match statements and expressions, string slice iteration, defer unwind order, untagged unions, generic function specialization, enum match expressions, heap struct allocation, and 2D/3D nested fixed arrays.
