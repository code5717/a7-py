"""`--mode semantic` accepts a program that calls into a file module."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cli(args, cwd):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "NO_COLOR": "1", "COLUMNS": "200"}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def project(tmp_path, call):
    (tmp_path / "helper.a7").write_text(
        "pub apply :: fn(x: i32) i32 {\n    ret x + 1\n}\n", encoding="utf-8",
    )
    (tmp_path / "main.a7").write_text(
        'io :: import "std/io"\nhelper :: import "helper"\n\n'
        f'main :: fn() {{\n    io.println("{{}}", {call})\n}}\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize("mode", ["semantic", "pipeline"])
def test_call_into_file_module_is_accepted(tmp_path, mode):
    project(tmp_path, "helper.apply(2)")

    result = run_cli(["--mode", mode, "--format", "json", "main.a7"], tmp_path)

    assert result.returncode == ExitCode.SUCCESS, result.stdout[-2000:] + result.stderr
    payload = json.loads(result.stdout)
    assert payload["stages"]["semantic"]["ok"] is True
    assert payload["stages"]["semantic"]["errors"] == []


@pytest.mark.parametrize("mode", ["semantic", "pipeline"])
def test_wrong_argument_type_to_file_module_is_rejected(tmp_path, mode):
    # Semantic mode must check the call against the module's signature, not
    # skip it.
    project(tmp_path, 'helper.apply("two")')

    result = run_cli(["--mode", mode, "--format", "json", "main.a7"], tmp_path)

    assert result.returncode == ExitCode.SEMANTIC, result.stdout[-2000:] + result.stderr
    codes = [detail["code"] for detail in json.loads(result.stdout)["error"]["details"]]
    assert "argument_type_mismatch" in codes
