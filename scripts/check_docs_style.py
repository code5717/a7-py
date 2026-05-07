#!/usr/bin/env python3
"""Lightweight docs style checker for repository markdown content."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass
class Finding:
    path: Path
    line_no: int
    rule: str
    snippet: str


BANNED_PHRASES = {
    "hype phrase": [
        re.compile(r"\bdive into\b", re.IGNORECASE),
        re.compile(r"\bunleash\b", re.IGNORECASE),
        re.compile(r"\bgame\s*changing\b", re.IGNORECASE),
    ],
    "journey phrase": [
        re.compile(r"\blet us take a look\b", re.IGNORECASE),
        re.compile(r"\bjoin me\b", re.IGNORECASE),
    ],
    "sentence-edge filler": [
        re.compile(r"^\s*(basically|clearly|interestingly)\b", re.IGNORECASE),
        re.compile(r"\b(basically|clearly|interestingly)[.!?]\s*$", re.IGNORECASE),
    ],
    "redundant structure": [
        re.compile(r"\band also\b", re.IGNORECASE),
    ],
}

EM_DASH_RE = re.compile(r"[—–]")
QUESTION_RE = re.compile(r"\?")
URL_RE = re.compile(r"https?://\S+")


def iter_doc_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()

    for fixed in [root / "README.md", root / "RELEASE.md", root / "site" / "README.md"]:
        if fixed.exists():
            paths.add(fixed)

    docs_dir = root / "docs"
    if docs_dir.exists():
        paths.update(docs_dir.glob("*.md"))

    site_content_docs = root / "site" / "src" / "content" / "docs"
    if site_content_docs.exists():
        paths.update(site_content_docs.rglob("*.mdx"))
        paths.update(site_content_docs.rglob("*.md"))

    site_pages = root / "site" / "src" / "pages"
    if site_pages.exists():
        paths.update(site_pages.rglob("*.md"))
        paths.update(site_pages.rglob("*.mdx"))

    return sorted(paths)


def check_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8")

    in_code_fence = False
    in_frontmatter = False

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if idx == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        if EM_DASH_RE.search(line):
            findings.append(Finding(path, idx, "dash punctuation", line.strip()))

        for rule, patterns in BANNED_PHRASES.items():
            for pat in patterns:
                if pat.search(line):
                    findings.append(Finding(path, idx, rule, line.strip()))
                    break

        question_line = URL_RE.sub("", line)
        if QUESTION_RE.search(question_line):
            findings.append(Finding(path, idx, "question mark in prose", line.strip()))

    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings: list[Finding] = []

    for path in iter_doc_paths(root):
        findings.extend(check_file(path))

    if not findings:
        print("docs-style: ok")
        return 0

    print("docs-style: violations found")
    for f in findings:
        rel = f.path.relative_to(root)
        print(f"{rel}:{f.line_no}: {f.rule}: {f.snippet}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
