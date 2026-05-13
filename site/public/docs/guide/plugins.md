# Plugins

Use these pages when connecting A7 documentation to an agent or editor.

## Plugin Pages

- [Amp](/a7-py/docs/plugins/amp.md)
- [Claude Code](/a7-py/docs/plugins/claude.md)
- [Codex](/a7-py/docs/plugins/codex.md)
- [Cursor](/a7-py/docs/plugins/cursor.md)
- [OpenCode](/a7-py/docs/plugins/opencode.md)
- [Pi](/a7-py/docs/plugins/pi.md)

## Shared Fetch Order

```text
https://code5717.github.io/a7-py/llms.txt
https://code5717.github.io/a7-py/docs/index.md
https://code5717.github.io/a7-py/llms-full.txt
```

## Shared Rules

- Do not generate recursive A7 examples.
- Prefer `usize` for lengths and indices.
- Prefer `isize` for signed pointer-sized differences.
- Verify code changes with local commands before trusting prose.
- Keep public markdown docs aligned with README, SPEC, and `docs/STATUS.md`.
