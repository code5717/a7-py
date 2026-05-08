#!/usr/bin/env python3
"""Verify SHA-256 manifest entries against release artifacts on disk."""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ManifestEntry:
    sha256: str
    size: int
    path: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_manifest(path: Path) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 2)
        if len(parts) != 3:
            raise ValueError(f"{path}:{line_number}: invalid manifest line")
        sha256, size_text, artifact_path = parts
        try:
            size = int(size_text)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid size: {size_text}") from exc
        entries.append(ManifestEntry(sha256=sha256, size=size, path=artifact_path))
    return entries


def resolve_artifact(base_dir: Path, artifact_path: str) -> Path:
    candidate = Path(artifact_path)
    if ".." in candidate.parts:
        raise ValueError(f"unsafe artifact path in manifest: {artifact_path}")

    if (base_dir / candidate).exists():
        return base_dir / candidate
    if (base_dir / candidate.name).exists():
        return base_dir / candidate.name
    if candidate.is_absolute():
        resolved_candidate = candidate.resolve()
        if resolved_candidate.is_relative_to(base_dir) or resolved_candidate.is_relative_to(ROOT):
            return resolved_candidate
        raise ValueError(f"unsafe artifact path in manifest: {artifact_path}")
    return ROOT / candidate


def verify_entries(entries: list[ManifestEntry], base_dir: Path) -> list[str]:
    errors: list[str] = []
    for entry in entries:
        try:
            path = resolve_artifact(base_dir, entry.path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"missing artifact: {entry.path}")
            continue

        actual_size = path.stat().st_size
        if actual_size != entry.size:
            errors.append(f"size mismatch for {entry.path}: expected {entry.size}, got {actual_size}")

        actual_sha256 = sha256_file(path)
        if actual_sha256 != entry.sha256:
            errors.append(f"sha256 mismatch for {entry.path}: expected {entry.sha256}, got {actual_sha256}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a release SHA-256 manifest")
    parser.add_argument("manifest", help="Path to SHA256SUMS")
    parser.add_argument(
        "--base-dir",
        default="",
        help="Directory to resolve manifest paths from before falling back to the repository root",
    )
    args = parser.parse_args()

    manifest = Path(args.manifest).resolve()
    base_dir = Path(args.base_dir).resolve() if args.base_dir else manifest.parent.resolve()

    try:
        entries = parse_manifest(manifest)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not entries:
        print("manifest contains no artifact entries", file=sys.stderr)
        return 2

    errors = verify_entries(entries, base_dir)
    if errors:
        print("release manifest verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"release manifest verified: {len(entries)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
