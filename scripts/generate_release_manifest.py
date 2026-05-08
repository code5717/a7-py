#!/usr/bin/env python3
"""Generate a deterministic SHA-256 manifest for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    git = shutil.which("git")
    if git is None:
        return "unknown"
    result = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=5,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def is_hidden_artifact(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def iter_files(paths: list[Path], output_path: Path | None) -> list[Path]:
    files: list[Path] = []
    resolved_output = output_path.resolve() if output_path else None

    for path in paths:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"artifact path does not exist: {path}")
        if resolved.is_file():
            if resolved != resolved_output and not resolved.name.startswith("."):
                files.append(resolved)
            continue
        if resolved.is_dir():
            for child in resolved.rglob("*"):
                relative_child = child.relative_to(resolved)
                if child.is_file() and child.resolve() != resolved_output and not is_hidden_artifact(relative_child):
                    files.append(child.resolve())
            continue
        raise ValueError(f"artifact path is not a file or directory: {path}")

    return sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix() if item.is_relative_to(ROOT) else item.as_posix())


def make_entries(files: list[Path]) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    for path in files:
        display_path = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
        entries.append(
            ManifestEntry(
                path=display_path,
                size=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )
    return entries


def render_manifest(entries: list[ManifestEntry], commit: str) -> str:
    lines = [
        "# A7 Release Artifact Checksums",
        f"# commit: {commit}",
        "# format: sha256  size_bytes  path",
        "",
    ]
    lines.extend(f"{entry.sha256}  {entry.size}  {entry.path}" for entry in entries)
    return "\n".join(lines) + "\n"


def parse_manifest_paths(path: Path) -> set[str]:
    paths: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 2)
        if len(parts) != 3:
            raise ValueError(f"invalid manifest line: {line}")
        paths.add(parts[2])
    return paths


def verify_manifest(manifest_path: Path, required_paths: list[str]) -> tuple[bool, list[str]]:
    manifest_paths = parse_manifest_paths(manifest_path)
    missing = [path for path in required_paths if path not in manifest_paths]
    return not missing, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SHA-256 checksums for release artifacts")
    parser.add_argument(
        "paths",
        nargs="+",
        help="Artifact files or directories to include",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Writes to stdout when omitted.",
    )
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="Required manifest path. May be supplied multiple times.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve() if args.output else None

    try:
        files = iter_files([Path(item) for item in args.paths], output_path)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not files:
        print("no artifact files found", file=sys.stderr)
        return 2

    content = render_manifest(make_entries(files), git_commit())

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        if args.require:
            ok, missing = verify_manifest(output_path, args.require)
            if not ok:
                print("manifest missing required artifact paths:", file=sys.stderr)
                for path in missing:
                    print(f"- {path}", file=sys.stderr)
                return 1
    else:
        if args.require:
            print("--require needs --output so the manifest can be verified", file=sys.stderr)
            return 2
        print(content, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
