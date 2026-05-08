"""End-to-end verification for all example programs."""

from __future__ import annotations

import subprocess
import sys
import json
import shutil
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_examples_e2e.py"


def has_zig() -> bool:
    try:
        result = subprocess.run(
            ["zig", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_examples_end_to_end_outputs_match_goldens(tmp_path: Path) -> None:
    report_path = tmp_path / "zig-e2e-report.json"
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--json-report", str(report_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, combined
    assert "Examples verified: 38/38" in result.stdout

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["passed"] == payload["total"] == 38
    assert len(payload["results"]) == 38
    for item in payload["results"]:
        assert item["compile_ok"] is True
        assert item["ast_ok"] is True
        assert item["build_ok"] is True
        assert item["run_ok"] is True
        assert item["output_match"] is True
        assert item["error"] == ""


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_examples_verifier_fails_when_golden_fixture_is_missing(tmp_path: Path) -> None:
    examples_dir = tmp_path / "examples"
    fixtures_dir = tmp_path / "fixtures"
    examples_dir.mkdir()
    fixtures_dir.mkdir()
    shutil.copy(PROJECT_ROOT / "examples" / "001_hello.a7", examples_dir / "001_hello.a7")

    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_SCRIPT),
            "--examples-dir",
            str(examples_dir),
            "--fixtures-dir",
            str(fixtures_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    combined = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 1, combined
    assert "missing golden fixture" in combined
    assert not (fixtures_dir / "001_hello.out").exists()
