# Changelog

This page mirrors the canonical `docs/CHANGELOG.md` in the repository
root. Release-facing entries only — longer narratives live in
[Status](/a7-py/compiler/status).

## Unreleased

- Full docs site rebuild: industrial-chrome / editorial-paper hybrid
  design, flat 5-section IA → 4-section IA, build-time markdown
  pipeline (no runtime parser / sanitiser ship), auto-generated
  `llms.txt` and `llms-full.txt` from the route manifest.
- Agents section removed. Agent contracts now live in the existing
  `llms.txt` / `llms-full.txt` surfaces and in [Getting Started →
  agents](/a7-py/learn/start#agents).
- Per-editor plugin pages dropped (no `claude` / `codex` / `cursor` /
  `amp` / `opencode` / `pi`). Editor configuration is up to the editor.
- `std/debug` and `std/random` added to the stdlib registry.

## 0.16.0 — Zig 0.16 toolchain bump

- Pinned Zig toolchain to 0.16.0.
- Updated `scripts/build_examples.py` to emit
  `a7-example-artifacts-...-zig0.16.0-<profile>.tar.gz`.
- Backend updates for Zig 0.16 API changes (slice ABI, allocator API).
- Example suite re-verified against pinned toolchain.

## 0.15 series

- Hardened safety backend plan: split into internal CFG, fact,
  obligation, proof-discharge stages.
- Iterative-traversal invariant enforced via
  `test/test_iterative_traversal.py` with Python recursion limit 100.
- Generic specialization improvements for single-module call sites.
- New examples 025 (linked list) and 026 (binary tree) demonstrating
  iterative replacements for recursive algorithms.

## 0.14 series

- File-backed local imports lower into a single combined Zig file.
- `match` exhaustiveness for `bool` and `enum`.
- Untagged unions with field-literal construction.

## Earlier

- Initial tokenizer, parser, semantic analysis, Zig backend.
- 46-example suite with golden-output verification.
- `std/io`, `std/math`, `std/mem`, `std/string` registry modules.

## Where to look

- `docs/CHANGELOG.md` in the repo — canonical, machine-readable history.
- GitHub releases — tagged distributions with checksums.
- `git log --oneline` — full commit history.
