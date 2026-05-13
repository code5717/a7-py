# CLI Reference

The A7 compiler ships one entrypoint: `a7`. It's installed by `uv sync` as
a console script. Use it via `uv run a7 ...` or import the Python API
directly (see [API](/a7-py/ref/api)).

## Invocation

```bash
uv run a7 <file.a7> [options]
```

A repo-checkout-friendly wrapper exists at `main.py`:

```bash
uv run python main.py <file.a7> [options]
```

Both invoke `a7.cli:main`. Prefer the installed `a7` to match end-user
usage; use the wrapper from a fresh checkout.

## Modes (`--mode`)

| Mode | Description | Writes file? |
|---|---|---|
| `compile` | (default) Run the full pipeline and emit `.zig` next to the source | yes |
| `tokens` | Lex only; print token stream | no |
| `ast` | Lex + parse; print AST | no |
| `semantic` | Run semantic passes; print resolved AST | no |
| `pipeline` | Full pipeline including codegen, but no file write | no |
| `doc` | Extract doc comments only | optional |

## Format (`--format`)

| Format | Use |
|---|---|
| `human` | (default) Pretty-printed for humans |
| `json` | Machine-readable. Use for agents, editor integrations, or scripts. |

JSON output includes structured diagnostics, source spans, and AST shapes
that mirror the internal node names from `a7/ast_nodes.py`.

## Common flags

```text
file                     A7 source file (.a7), positional, required
--mode {compile,tokens,ast,semantic,pipeline,doc}
--format {human,json}
--verbose                Full pipeline timing + intermediate dumps
--doc-out {auto,<path>}  Emit a markdown doc summary alongside compile
--output <path>          Override the default .zig output path
--no-write               Equivalent to --mode pipeline
--help                   argparse help
```

## Exit codes

Stable and intended for automation.

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Usage error (bad flags, missing file) |
| `3` | IO error (can't read source, can't write output) |
| `4` | Tokenize error |
| `5` | Parse error |
| `6` | Semantic error (type, scope, safety, recursion rejection) |
| `7` | Codegen error |
| `8` | Internal compiler error (please report) |

Use these in shell pipelines to branch on the failure stage:

```bash
if ! uv run a7 file.a7; then
    case $? in
        4) echo "lex failure"   ;;
        5) echo "parse failure" ;;
        6) echo "semantic failure" ;;
        *) echo "other failure ($?)" ;;
    esac
fi
```

## Typical sessions

```bash
# Print tokens for a source file
uv run a7 --mode tokens examples/006_if.a7

# Inspect the parsed AST as JSON
uv run a7 --mode ast --format json examples/004_func.a7

# Run all passes without writing .zig
uv run a7 --mode pipeline examples/014_generics.a7

# Compile + emit a doc summary
uv run a7 examples/001_hello.a7 --mode compile --doc-out auto

# Doc-only run
uv run a7 --mode doc examples/001_hello.a7

# Verbose run with intermediate dumps
uv run a7 --verbose examples/009_struct.a7
```

## Building binaries

The compiler emits Zig source. To get a native binary:

```bash
uv run a7 examples/001_hello.a7
zig build-exe -O ReleaseFast examples/001_hello.zig
./001_hello
```

For the whole example suite under the same flags CI uses:

```bash
uv run python scripts/build_examples.py --profile debug   --backend zig --clean
uv run python scripts/build_examples.py --profile release --backend zig --clean
```

## Agent automation

JSON mode is the agent-facing surface:

```bash
uv run a7 --mode semantic --format json file.a7 > sem.json
```

The JSON shape is stable across releases. The `errors` array contains
structured diagnostics with source span, severity, code, and message.

For full agent context, fetch
`https://code5717.github.io/a7-py/llms-full.txt` rather than walking
individual pages.

## What's not in the CLI

- No language server (LSP) yet. Use `--mode semantic --format json` for
  editor integration in the meantime.
- No `a7 run` shortcut. Compile to Zig then invoke `zig build-exe`.
- No `a7 install` / package registry. Out of scope.
- No `a7 fmt`. Format is not pinned; use whitespace conventions in
  `examples/`.

Workflow commands (`a7 check`, `a7 build`, `a7 run`, `a7 doctor`,
`a7 --version`) are on the roadmap — see [Status](/a7-py/compiler/status).
