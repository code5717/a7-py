"""Per-stage wall timers record ms without changing emitted Zig."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(MAIN), *args],
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stage_ms_present_and_zig_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "hello.a7"
    source.write_text(
        'io :: import "std/io"\n\nmain :: fn() {\n    io.println("hi")\n}\n',
        encoding="utf-8",
    )
    out_a = tmp_path / "a.zig"
    out_b = tmp_path / "b.zig"

    timed = _run(
        [
            str(source),
            "--mode",
            "pipeline",
            "--format",
            "json",
            "--timings",
        ],
        cwd=tmp_path,
    )
    assert timed.returncode == 0, timed.stderr
    payload = json.loads(timed.stdout)
    for stage in ("tokenize", "parse", "semantic", "safety", "codegen"):
        assert stage in payload["stages"], stage
        assert isinstance(payload["stages"][stage]["ms"], (int, float))
        assert payload["stages"][stage]["ms"] >= 0

    compile_a = _run([str(source), "-o", str(out_a), "--timings"], cwd=tmp_path)
    compile_b = _run([str(source), "-o", str(out_b)], cwd=tmp_path)
    assert compile_a.returncode == 0, compile_a.stderr
    assert compile_b.returncode == 0, compile_b.stderr
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
    assert "timings:" in compile_a.stdout
    assert "tokenize=" in compile_a.stdout
