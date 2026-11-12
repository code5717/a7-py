"""CLI contracts for agent discovery: help, doctor capabilities, JSON shape."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "main.py"


def cli(tmp_path: Path, *args: str, env: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, str(MAIN), *map(str, args)],
        cwd=tmp_path,
        env=env or {**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_help_documents_modes_exits_and_long_flag_preference(tmp_path: Path):
    result = cli(tmp_path, "--help")
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "modes (--mode):" in text
    assert "exit codes" in text
    assert "short aliases" in text
    assert "prefer long flags" in text
    assert "--output" in text and "-o" in text
    assert "doctor --format json" in text
    for mode in ("compile", "tokens", "ast", "semantic", "pipeline", "doc"):
        assert mode in text


def test_doctor_json_lists_capabilities_even_without_zig(tmp_path: Path):
    env = {**os.environ, "PATH": str(tmp_path), "PYTHONPATH": str(ROOT)}
    result = cli(tmp_path, "doctor", "--format", "json", env=env)
    assert result.returncode == 2, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "1.0"
    assert payload["command"] == "doctor"
    assert payload["status"] == "error"
    assert payload["exit_code"] == 2
    assert payload["zig"]["ok"] is False
    caps = payload["capabilities"]
    assert caps["modes"] == [
        "compile",
        "tokens",
        "ast",
        "semantic",
        "pipeline",
        "doc",
    ]
    assert caps["backends"] == ["zig"]
    assert caps["exit_codes"]["6"] == "semantic"
    assert caps["flags"]["short_aliases"]["-o"] == "--output"
    assert "--timings" in caps["flags"]["file_first"]
    assert caps["json_schema_version"] == "3.0"


def test_json_success_and_failure_carry_exit_code_and_diagnostics(tmp_path: Path):
    source = tmp_path / "ok.a7"
    source.write_text(
        'io :: import "std/io"\nmain :: fn() {\n    io.println("hi")\n}\n',
        encoding="utf-8",
    )
    ok = cli(tmp_path, str(source), "--mode", "pipeline", "--format", "json")
    assert ok.returncode == 0, ok.stderr
    payload = json.loads(ok.stdout)
    assert payload["schema_version"] == "3.0"
    assert payload["status"] == "ok"
    assert payload["exit_code"] == 0
    assert payload["diagnostics"] == []
    assert "stages" in payload and "tokenize" in payload["stages"]

    source.write_text('main :: fn() {\n    x: i32 = "hello"\n}\n', encoding="utf-8")
    bad = cli(tmp_path, str(source), "--format", "json")
    assert bad.returncode == 6, bad.stderr + bad.stdout
    failed = json.loads(bad.stdout)
    assert failed["exit_code"] == 6
    assert failed["status"] == "error"
    assert failed["diagnostics"]
    assert failed["diagnostics"] == failed["error"]["details"]
    span = failed["diagnostics"][0]["span"]
    assert span["start_line"] == 2
    assert span["start_column"] >= 1


def test_check_json_failure_keeps_stage_exit_and_diagnostics(tmp_path: Path):
    source = tmp_path / "broken.a7"
    source.write_text("main :: fn() {\n    x := (\n}\n", encoding="utf-8")
    result = cli(tmp_path, "check", source, "--format", "json")
    assert result.returncode == 5, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["exit_code"] == 5
    assert payload["error"]["category"] == "parse"
    assert payload["diagnostics"][0]["message"]
    assert "span" in payload["diagnostics"][0]
