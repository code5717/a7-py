#!/usr/bin/env python3
"""Verify that a release archive contains required member paths."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path


def normalize_member(path: str) -> str:
    return path.strip().lstrip("./").rstrip("/")


def archive_members(path: Path) -> set[str]:
    with tarfile.open(path, "r:*") as archive:
        return {normalize_member(member.name) for member in archive.getmembers()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify required files inside a tar archive")
    parser.add_argument("archive", help="Archive to inspect")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="Required archive member path. May be supplied multiple times.",
    )
    args = parser.parse_args()

    archive_path = Path(args.archive)
    if not archive_path.is_file():
        print(f"archive does not exist: {archive_path}", file=sys.stderr)
        return 2
    if not args.require:
        print("at least one --require path is needed", file=sys.stderr)
        return 2

    try:
        members = archive_members(archive_path)
    except (tarfile.TarError, OSError) as exc:
        print(f"could not read archive {archive_path}: {exc}", file=sys.stderr)
        return 2

    required = [normalize_member(item) for item in args.require]
    missing = [item for item in required if item not in members]
    if missing:
        print(f"archive content verification failed for {archive_path}:", file=sys.stderr)
        for item in missing:
            print(f"- missing: {item}", file=sys.stderr)
        return 1

    print(f"archive content verified: {archive_path} ({len(required)} required paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
