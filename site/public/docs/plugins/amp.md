# Amp

Use this workflow when Amp needs A7 context.

## Fetch

```text
https://code5717.github.io/a7-py/llms.txt
https://code5717.github.io/a7-py/docs/index.md
```

Use `llms-full.txt` when a single context file is easier than following links.

## Work Locally

```bash
uv sync
uv run a7 examples/001_hello.a7
PYTHONPATH=. uv run pytest --tb=no -q
```

## Constraints

- A7 source recursion is banned.
- The compiler emits native Zig or C output.
- Do not run untrusted A7 source.
