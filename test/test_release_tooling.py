"""Release/debug build tooling smoke tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_installed_cli_entrypoint_works() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "a7",
            "--format",
            "json",
            "--mode",
            "tokens",
            "examples/001_hello.a7",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert '"schema_version": "2.0"' in result.stdout
    assert '"status": "ok"' in result.stdout


def test_debug_build_script_verifies_single_zig_example(tmp_path: Path) -> None:
    if shutil.which("zig") is None:
        return

    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    shutil.copy(ROOT / "examples" / "001_hello.a7", examples_dir / "001_hello.a7")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_examples.py",
            "--profile",
            "debug",
            "--backend",
            "zig",
            "--examples-dir",
            str(examples_dir),
            "--out-dir",
            str(tmp_path / "build"),
            "--clean",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Build artifacts verified: 1/1" in result.stdout


def test_release_manifest_has_stable_checksums(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    alpha = dist / "alpha.txt"
    beta = dist / "beta.txt"
    hidden = dist / ".ignored"
    output = dist / "SHA256SUMS"
    beta.write_text("beta\n", encoding="utf-8")
    alpha.write_text("alpha\n", encoding="utf-8")
    hidden.write_text("ignored\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_release_manifest.py",
            str(dist),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    content = output.read_text(encoding="utf-8")
    assert "# A7 Release Artifact Checksums" in content
    assert f"{sha256(b'alpha\n').hexdigest()}  6  " in content
    assert f"{sha256(b'beta\n').hexdigest()}  5  " in content
    assert ".ignored" not in content
    assert "SHA256SUMS" not in "\n".join(content.splitlines()[3:])


def test_release_manifest_fails_for_missing_path(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_release_manifest.py",
            str(tmp_path / "missing"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "artifact path does not exist" in result.stderr


def test_release_manifest_requires_expected_paths(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "artifact.tar.gz"
    output = dist / "SHA256SUMS"
    artifact.write_text("artifact\n", encoding="utf-8")

    ok_result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_release_manifest.py",
            str(dist),
            "--output",
            str(output),
            "--require",
            artifact.as_posix(),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert ok_result.returncode == 0, ok_result.stderr or ok_result.stdout

    bad_result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_release_manifest.py",
            str(dist),
            "--output",
            str(output),
            "--require",
            "dist/missing.tar.gz",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert bad_result.returncode == 1
    assert "manifest missing required artifact paths" in bad_result.stderr


def test_verify_release_manifest_detects_tampering(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "artifact.tar.gz"
    manifest = dist / "SHA256SUMS"
    artifact.write_text("artifact\n", encoding="utf-8")

    generate = subprocess.run(
        [
            sys.executable,
            "scripts/generate_release_manifest.py",
            str(dist),
            "--output",
            str(manifest),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert generate.returncode == 0, generate.stderr or generate.stdout

    verify = subprocess.run(
        [
            sys.executable,
            "scripts/verify_release_manifest.py",
            str(manifest),
            "--base-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert verify.returncode == 0, verify.stderr or verify.stdout
    assert "release manifest verified: 1 artifacts" in verify.stdout

    artifact.write_text("tampered\n", encoding="utf-8")
    tampered = subprocess.run(
        [
            sys.executable,
            "scripts/verify_release_manifest.py",
            str(manifest),
            "--base-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert tampered.returncode == 1
    assert "release manifest verification failed" in tampered.stderr


def test_verify_archive_contents_requires_expected_members(tmp_path: Path) -> None:
    archive_path = tmp_path / "docs.tar.gz"
    docs_dir = tmp_path / "dist"
    docs_dir.mkdir()
    (docs_dir / "llms.txt").write_text("index\n", encoding="utf-8")
    nested = docs_dir / "docs"
    nested.mkdir()
    (nested / "index.md").write_text("# Docs\n", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(docs_dir / "llms.txt", arcname="dist/llms.txt")
        archive.add(nested / "index.md", arcname="dist/docs/index.md")

    ok_result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_archive_contents.py",
            str(archive_path),
            "--require",
            "dist/llms.txt",
            "--require",
            "./dist/docs/index.md",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert ok_result.returncode == 0, ok_result.stderr or ok_result.stdout
    assert "archive content verified" in ok_result.stdout

    missing_result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_archive_contents.py",
            str(archive_path),
            "--require",
            "dist/llms-full.txt",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert missing_result.returncode == 1
    assert "archive content verification failed" in missing_result.stderr
    assert "dist/llms-full.txt" in missing_result.stderr
