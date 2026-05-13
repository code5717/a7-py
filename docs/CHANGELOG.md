# Changelog

This file tracks only current release-facing changes. Historical review notes
belong in git history, not in long Markdown logs.

## Unreleased

- Consolidated project-status documentation around the current Zig-only
  compiler surface and removed stale review/audit handoff files.
- Added `scripts/project_status.py` as the source for example counts and small
  release facts.
- Release archive verification now derives example counts from the repository
  instead of duplicating fixed numbers.

## 0.3.0

- Installed `a7` CLI entrypoint.
- Zig is the only supported public backend.
- Added debug and release example artifact verification.
- Added wheel install smoke verification.
- Added checksum and archive-content verification for release artifacts.
- Added internal safety proof planning and operation-specific backend approvals
  for casts, division/modulo, bounds-sensitive indexing/slicing, ref
  dereferences, and direct use after `del`.
- Expanded the verified example suite to 43 runnable programs.
