# Getting Started

Five-minute path from a fresh checkout to a running A7 binary.

## Requirements

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** as the Python package manager
- **[Zig 0.16.0](https://ziglang.org/download/)** to build the generated Zig
  output. CI pins this exact version for repeatable artifact checks.

```bash
# Install uv (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Clone and sync

```bash
git clone https://github.com/Airbus5717/a7-py.git
cd a7-py
uv sync
```

`uv sync` resolves and installs the compiler and its development dependencies
into a project-local virtualenv. It does not touch your global Python.

## First compile

```bash
uv run a7 examples/001_hello.a7
```

Output goes to `examples/001_hello.zig`. To turn that into a native binary:

```bash
zig build-exe -O ReleaseFast examples/001_hello.zig
./001_hello
```

The included `scripts/build_examples.py` does this for the entire example
suite in one shot — see [Examples](/a7-py/learn/examples).

## CLI modes you'll use

| Command | Output |
|---|---|
| `a7 file.a7` | Compile to `file.zig` (default) |
| `a7 --mode tokens file.a7` | Token stream |
| `a7 --mode ast file.a7` | Parsed AST |
| `a7 --mode semantic file.a7` | Semantic pass output |
| `a7 --mode pipeline file.a7` | Full pipeline, no write |
| `a7 --format json file.a7` | Machine-readable output |
| `a7 --mode doc file.a7` | Doc extraction only |

Full reference: [CLI](/a7-py/ref/cli).

## Verifying your environment

```bash
PYTHONPATH=. uv run pytest                           # all tests
uv run python scripts/verify_examples_e2e.py         # compile + run all examples
uv run python scripts/build_examples.py --profile release --backend zig --clean
./run_all_tests.sh                                   # full release gate
```

`run_all_tests.sh` is the source of truth for what must pass before a release.

<a id="agents"></a>

## Using A7 from a coding agent

A7 is designed to be navigable by coding agents without a special plugin.
Fetch order:

1. `https://code5717.github.io/a7-py/llms.txt` — page index with one-line
   summaries.
2. `https://code5717.github.io/a7-py/llms-full.txt` — every page concatenated.
   Single fetch for full project context (~30 KB).
3. `https://code5717.github.io/a7-py/docs/<slug>.md` — raw markdown for a
   specific page when you need depth.

Agents reading these surfaces should respect three invariants:

- A7 source recursion is banned. Don't emit recursive A7 functions; rewrite
  to loops or explicit stacks.
- `usize` for sizes/indices, `isize` only for signed pointer-sized offsets.
- `new [N]T` (heap fixed arrays) is rejected. Use stack arrays or slices.

Exit codes are stable and scriptable: `0` success, `2` usage, `3` io,
`4` tokenize, `5` parse, `6` semantic, `7` codegen, `8` internal.

## First rule

A7 source recursion is a compile-time error. The compiler rejects direct,
mutual, and function-pointer alias cycles. Port recursive algorithms to loops
or explicit stacks before you start writing — examples 025 and 026 show the
pattern for a linked list and a binary tree.

## Next

- [Why A7](/a7-py/learn/why) — what the language trades off.
- [Examples](/a7-py/learn/examples) — 46 commented programs.
- [Language Reference](/a7-py/ref/language) — the full surface.
