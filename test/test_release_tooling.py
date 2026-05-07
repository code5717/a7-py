"""Release/debug build tooling smoke tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
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
