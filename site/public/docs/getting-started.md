# Getting Started

## Requirements

- Python 3.13+
- `uv`
- Zig 0.15.2 to build and run generated Zig/C outputs

## Install

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
```

## Compile

```bash
uv run python main.py examples/001_hello.a7
uv run a7 examples/001_hello.a7
```

The default backend emits Zig. Use `--backend c` for C output.

```bash
uv run python main.py --backend c examples/001_hello.a7
```

To learn the current language from one file, run the commented tour:

```bash
uv run python main.py examples/037_language_tour.a7
```

## Run Verification

```bash
PYTHONPATH=. uv run pytest
uv run python scripts/verify_examples_e2e.py
uv run python scripts/verify_examples_e2e_c.py
uv run python scripts/verify_backend_parity.py
./run_all_tests.sh
```

## First Rule

A7 source recursion is banned. Direct and mutual recursion are semantic errors. Use loops, explicit stacks, or index-based worklists.
