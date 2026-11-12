"""Pins for generic body obligations through more analyzable alias origins."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def test_imported_immutable_alias_preserves_bad_body(tmp_path):
    (tmp_path / "lib.a7").write_text(
        "safe :: fn(x: $T) $T { z: $T = 1; ret z }\n"
        "bad :: fn(x: $T) $T { z: $T = 300; ret z }\n",
        encoding="utf-8",
    )
    main = tmp_path / "main.a7"
    main.write_text(
        'lib :: import "lib"\n'
        "main :: fn() {\n"
        "    a: i8 = 0\n"
        "    f := lib.bad\n"
        "    x := f(a)\n"
        "}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    assert "Initializer" in result.stdout + result.stderr


def test_imported_immutable_alias_preserves_safe_body(tmp_path):
    (tmp_path / "lib.a7").write_text(
        "safe :: fn(x: $T) $T { z: $T = 1; ret z }\n"
        "bad :: fn(x: $T) $T { z: $T = 300; ret z }\n",
        encoding="utf-8",
    )
    main = tmp_path / "main.a7"
    main.write_text(
        'lib :: import "lib"\n'
        "main :: fn() {\n"
        "    a: i8 = 0\n"
        "    f := lib.safe\n"
        "    x := f(a)\n"
        "}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 0, result.stdout + result.stderr


def test_module_global_immutable_alias_preserves_bad_body(tmp_path):
    main = tmp_path / "main.a7"
    main.write_text(
        "safe :: fn(x: $T) $T { z: $T = 1; ret z }\n"
        "bad :: fn(x: $T) $T { z: $T = 300; ret z }\n"
        "alias := bad\n"
        "main :: fn() {\n"
        "    a: i8 = 0\n"
        "    x := alias(a)\n"
        "}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    assert "Initializer" in result.stdout + result.stderr


def test_selected_import_direct_call_preserves_bad_body(tmp_path):
    (tmp_path / "lib.a7").write_text(
        "bad :: fn(x: $T) $T { z: $T = 300; ret z }\n",
        encoding="utf-8",
    )
    main = tmp_path / "main.a7"
    main.write_text(
        'import "lib" { bad }\n'
        "main :: fn() {\n"
        "    a: i8 = 0\n"
        "    x := bad(a)\n"
        "}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    assert "Initializer" in result.stdout + result.stderr
