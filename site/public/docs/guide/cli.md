# CLI

## Entrypoints

```bash
uv run a7 [OPTIONS] <file.a7>
uv run python main.py [OPTIONS] <file.a7>
```

## Modes

- `compile`: full pipeline and code generation
- `tokens`: tokenize only
- `ast`: tokenize and parse
- `semantic`: tokenize, parse, and check
- `pipeline`: full pipeline with intermediate output
- `doc`: generate a Markdown report

## Flags

- `--verbose`: show intermediate results
- `--mode MODE`: select compiler stage
- `--format json`: emit structured JSON
- `--backend zig`: select target backend
- `--doc-out PATH`: write Markdown report

## Exit Codes

```text
0 success
2 bad arguments
3 file not found
4 tokenizer error
5 parse error
6 semantic error
7 codegen error
8 internal bug
```
