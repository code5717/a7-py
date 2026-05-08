# API and SDK

Use this page for automation entry points around A7.

## Current Surface

A7 currently ships as a local compiler and repository toolchain. There is no hosted API service and no published SDK package yet.

Supported automation surfaces:

- CLI: `uv run a7 [OPTIONS] <file.a7>`
- Compatibility wrapper: `uv run python main.py [OPTIONS] <file.a7>`
- JSON output: `--format json`
- Markdown reports: `--mode doc --doc-out PATH`
- Static agent docs: `/a7-py/llms.txt`, `/a7-py/llms-full.txt`, and `/a7-py/docs/index.md`

## CLI Recipes

```bash
uv run a7 examples/001_hello.a7
uv run a7 --backend c examples/001_hello.a7
uv run a7 --mode semantic --format json examples/001_hello.a7
uv run a7 --mode doc --doc-out out.md examples/001_hello.a7
```

## Stable Contracts

- Exit codes are documented in [CLI](/a7-py/docs/guide/cli.md).
- Language semantics are documented in [Language and Library](/a7-py/docs/language.md).
- Remaining gaps are documented in [Status](/a7-py/docs/status.md).

## Not Yet Provided

- Hosted compile API.
- Typed TypeScript SDK.
- Remote sandbox execution.
- Registry-hosted package release.

Treat local CLI execution as the source of truth.
