#!/usr/bin/env python3
"""Fail if likely secrets are committed to the repository."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "a7_py.egg-info",
    "build",
    "dist",
    "node_modules",
    "site/dist",
    "site/node_modules",
}

SKIP_SUFFIXES = {
    ".lock",
    ".png",
    ".webp",
    ".pdf",
    ".whl",
    ".gz",
}

SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)?PRIVATE KEY-----"),
    "github token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
    "openai api key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "anthropic api key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "generic secret assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"\s]{16,}['\"]"
    ),
}


@dataclass
class Finding:
    path: Path
    line_no: int
    kind: str


def should_skip(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    joined = "/".join(rel_parts)
    if any(joined == skip or joined.startswith(f"{skip}/") for skip in SKIP_DIRS):
        return True
    return path.suffix in SKIP_SUFFIXES


def iter_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not should_skip(path)
    )


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding(path, line_no, kind))
    return findings


def main() -> int:
    findings: list[Finding] = []
    for path in iter_files():
        findings.extend(scan_file(path))

    if not findings:
        print("secrets-check: ok")
        return 0

    print("secrets-check: possible committed secrets found")
    for item in findings:
        print(f"{item.path.relative_to(ROOT)}:{item.line_no}: {item.kind}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
