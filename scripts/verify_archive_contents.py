#!/usr/bin/env python3
"""Verify that a release archive contains required member paths."""

from __future__ import annotations

import argparse
import fnmatch
import posixpath
import sys
import tarfile
from pathlib import Path


def normalize_member(path: str) -> str:
    """Normalize a tar member path for comparison.

    Strips a single leading "./" and trailing slashes. Does NOT use
    ``str.lstrip("./")`` — that strips any combination of "." and "/" chars
    from the left and would launder "../etc/passwd" into "etc/passwd".
    """
    cleaned = path.strip()
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/")


def _is_unsafe_member(member: tarfile.TarInfo) -> str | None:
    """Return a reason string if the member is unsafe, else None."""
    raw = member.name
    if not raw:
        return "empty member name"
    # Reject absolute paths (POSIX or Windows-style).
    if raw.startswith("/") or raw.startswith("\\"):
        return f"absolute member path: {raw!r}"
    # Reject any ".." segment after POSIX normalization.
    normalized = posixpath.normpath(raw)
    if normalized.startswith("../") or normalized == ".." or "/../" in normalized or normalized.startswith("/"):
        return f"path traversal in member: {raw!r}"
    # Reject symlinks/hardlinks whose targets escape the archive root.
    if member.issym() or member.islnk():
        target = member.linkname or ""
        if not target:
            return f"link member with empty target: {raw!r}"
        if target.startswith("/") or target.startswith("\\"):
            return f"absolute link target: {raw!r} -> {target!r}"
        # Resolve the link target relative to the member's directory.
        member_dir = posixpath.dirname(normalized)
        resolved = posixpath.normpath(posixpath.join(member_dir, target))
        if resolved.startswith("../") or resolved == "..":
            return f"link target escapes archive: {raw!r} -> {target!r}"
    # Reject device, FIFO, and other non-regular members. We accept
    # regular files, directories, symlinks, and hardlinks (the latter two
    # are validated above).
    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
        return f"unsupported member type: {raw!r} (type={member.type!r})"
    return None


def archive_members(path: Path) -> set[str]:
    members: set[str] = set()
    with tarfile.open(path, "r:*") as archive:
        for member in archive.getmembers():
            reason = _is_unsafe_member(member)
            if reason is not None:
                raise ValueError(f"unsafe archive member: {reason}")
            members.add(normalize_member(member.name))
    return members


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
    except (tarfile.TarError, OSError, ValueError) as exc:
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
