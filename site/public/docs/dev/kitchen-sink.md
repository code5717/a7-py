# Kitchen Sink

Use this page to verify markdown shapes supported by the public docs.

## Links

- [Getting Started](/a7-py/docs/getting-started.md)
- [CLI](/a7-py/docs/cli.md)
- [Status](/a7-py/docs/status.md)

## Lists

- Bullet item
- Bullet item with `inline code`
- Bullet item with a link to [llms.txt](/a7-py/llms.txt)

## Code

```bash
uv run a7 examples/001_hello.a7
```

```a7
io :: import "std/io"

main :: fn() {
    io.println("Hello, World!")
}
```

## Table

| Item | Value |
| --- | --- |
| Backend | Zig and C |
| Recursion | Rejected in A7 source |
| Agent entry | `/a7-py/llms.txt` |
