---
title: Start
nav: Start
group: Learn
summary: Install A7, compile a program, and understand the command shape used by CI and examples.
order: 1
---

# Start

## Requirements

- Python 3.13 or newer.
- `uv` for the Python environment.
- Zig 0.16.0 to build generated Zig output.
- Bun for the docs site.

## Install

```bash
git clone https://github.com/code5717/a7-py.git
cd a7-py
uv sync
zig version
```

The preferred compiler entry point is:

```bash
uv run a7 examples/001_hello.a7
```

The repository wrapper is equivalent:

```bash
uv run python main.py examples/001_hello.a7
```

## Compile

```bash
uv run a7 examples/001_hello.a7 --mode compile
zig run build/zig/001_hello.zig
```

The backend writes one Zig file per A7 input. Multi-file A7 input can be
resolved by the compiler, but the generated Zig output remains single-file.

## Useful modes

| Mode | Purpose |
| --- | --- |
| `tokens` | Show lexer output. |
| `ast` | Show parsed structure. |
| `semantic` | Run semantic checks. |
| `pipeline` | Run the full compiler pipeline without writing a file. |
| `compile` | Emit Zig. |
| `doc` | Emit compiler documentation output. |

Use `--format json` for tools and agents.

## Verify locally

```bash
uv run python scripts/verify_examples_e2e.py
uv run python scripts/build_examples.py --profile debug --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
./run_all_tests.sh
```

The full gate is intentionally heavier than the docs site gate. Use it before
tagging or claiming a compiler change is complete.
