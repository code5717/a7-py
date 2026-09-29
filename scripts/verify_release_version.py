#!/usr/bin/env python3
"""Reject a release tag that disagrees with package metadata or the changelog."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tomllib


ROOT = Path(__file__).resolve().parent.parent


def verify_version(root: Path, tag: str | None) -> str:
    with (root / "pyproject.toml").open("rb") as source:
        version = tomllib.load(source)["project"]["version"]
    if tag is None:
        return version
    if tag != f"v{version}":
        raise ValueError(f"release tag {tag!r} does not match package version v{version}")
    changelog = (root / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    if re.search(rf"^## {re.escape(version)}\s*$", changelog, re.MULTILINE) is None:
        raise ValueError(f"changelog has no release heading for {version}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Release tag; defaults to a GitHub tag ref when present")
    args = parser.parse_args()
    tag = args.tag
    ref = os.environ.get("GITHUB_REF", "")
    if tag is None and ref.startswith("refs/tags/"):
        tag = ref.removeprefix("refs/tags/")
    try:
        version = verify_version(ROOT, tag)
    except (OSError, ValueError, KeyError) as error:
        print(f"release-version: {error}", file=sys.stderr)
        return 1
    suffix = f", tag {tag} matches changelog" if tag is not None else ", untagged qualification"
    print(f"release-version: {version}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
