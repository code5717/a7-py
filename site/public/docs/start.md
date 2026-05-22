---
title: Start
nav: Start
group: Getting started
summary: Install A7, compile a program, and run the language tour example.
order: 1
---

# Start

## Requirements

- Python 3.13 or newer
- `uv` for the Python environment
- Zig 0.16.0 to build generated Zig output
- Bun to build the docs site locally

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

## First compile

```bash
uv run a7 examples/001_hello.a7 --mode compile
zig run examples/001_hello.zig
```

The backend writes one Zig file per A7 input. Multi-file A7 input can be
resolved by the compiler, but the generated Zig output remains single-file.

## Language tour

Read the current language surface in one verified example file:

```bash
uv run a7 examples/037_language_tour.a7 --mode pipeline
```

See [Language](/a7-py/language/) for a short reference. Full semantics live in
`docs/SPEC.md`.

## Useful modes

| Mode | Purpose |
| --- | --- |
| `tokens` | Show lexer output |
| `ast` | Show parsed structure |
| `semantic` | Run semantic checks |
| `pipeline` | Run the full compiler pipeline without writing a file |
| `compile` | Emit Zig |
| `doc` | Emit compiler documentation output |

Use `--format json` for tools and agents. CLI modes and exit codes are listed on
the [Compiler](/a7-py/compiler/) page.

## Verify locally

Quick check after a compiler change:

```bash
uv run python scripts/verify_examples_e2e.py
```

Full release gate (heavier):

```bash
./run_all_tests.sh
```

Use the full gate before tagging or claiming a compiler change is complete. See
[Release](/a7-py/release/) for the complete checklist.
