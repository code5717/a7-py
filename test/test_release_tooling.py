"""Release/debug build tooling smoke tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
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
