#!/usr/bin/env python3
"""Verify that a release archive contains required member paths."""

from __future__ import annotations

import argparse
import fnmatch
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
    parser.add_argument(
        "--require-glob-count",
        action="append",
        default=[],
        metavar="PATTERN=COUNT",
        help="Required member glob with exact match count, e.g. 'release/zig/src/*.zig=38'.",
    )
    args = parser.parse_args()

    archive_path = Path(args.archive)
    if not archive_path.is_file():
        print(f"archive does not exist: {archive_path}", file=sys.stderr)
        return 2
    if not args.require and not args.require_glob_count:
        print("at least one --require or --require-glob-count check is needed", file=sys.stderr)
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

    glob_errors = []
    for spec in args.require_glob_count:
        if "=" not in spec:
            print(f"invalid --require-glob-count value: {spec}", file=sys.stderr)
            return 2
        pattern, count_text = spec.rsplit("=", 1)
        pattern = normalize_member(pattern)
        try:
            expected_count = int(count_text)
        except ValueError:
            print(f"invalid --require-glob-count count: {spec}", file=sys.stderr)
            return 2
        actual_count = sum(1 for member in members if fnmatch.fnmatchcase(member, pattern))
        if actual_count != expected_count:
            glob_errors.append((pattern, expected_count, actual_count))

    if glob_errors:
        print(f"archive content verification failed for {archive_path}:", file=sys.stderr)
        for pattern, expected_count, actual_count in glob_errors:
            print(
                f"- glob count mismatch: {pattern} expected {expected_count}, got {actual_count}",
                file=sys.stderr,
            )
        return 1

    total_checks = len(required) + len(args.require_glob_count)
    print(f"archive content verified: {archive_path} ({total_checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
