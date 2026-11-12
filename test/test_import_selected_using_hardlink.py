"""Track 2 module pins: selected imports, using-import reject, hardlink identity."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_selected_import_file_module_compiles(tmp_path):
    (tmp_path / "vector.a7").write_text(
        "Vec3 :: struct { x: f32, y: f32, z: f32 }\n"
        "dot :: fn(a: Vec3, b: Vec3) f32 {\n"
        "    ret a.x * b.x + a.y * b.y + a.z * b.z\n"
        "}\n",
        encoding="utf-8",
    )
    main = tmp_path / "main.a7"
    main.write_text(
        'io :: import "std/io"\n'
        'import "vector" { Vec3, dot }\n'
        "main :: fn() {\n"
        "    a := Vec3{x: 1.0, y: 2.0, z: 3.0}\n"
        "    b := Vec3{x: 1.0, y: 0.0, z: 0.0}\n"
        '    io.println("{}", dot(a, b))\n'
        "}\n",
        encoding="utf-8",
    )
    out = tmp_path / "main.zig"
    compiled = run_cli(["--mode", "compile", "--output", str(out), str(main)])
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    emitted = out.read_text()
    assert "module_vector__dot" in emitted or "dot" in emitted
    assert "module_vector__Vec3" in emitted or "Vec3" in emitted


def test_selected_import_stdlib_println(tmp_path):
    main = tmp_path / "main.a7"
    main.write_text(
        'import "std/io" { println }\n'
        "main :: fn() {\n"
        '    println("hi")\n'
        "}\n",
        encoding="utf-8",
    )
    out = tmp_path / "main.zig"
    result = run_cli(["--mode", "compile", "--output", str(out), str(main)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "hi" in out.read_text() or "__a7_stdout_print" in out.read_text()


def test_selected_import_missing_name_exits_6(tmp_path):
    (tmp_path / "helper.a7").write_text("value :: fn() i32 { ret 1 }\n", encoding="utf-8")
    main = tmp_path / "main.a7"
    main.write_text(
        'import "helper" { missing }\n'
        "main :: fn() {}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    assert "missing" in (result.stdout + result.stderr).lower()


def test_selected_import_private_name_exits_6(tmp_path):
    (tmp_path / "helper.a7").write_text("_secret :: fn() i32 { ret 1 }\n", encoding="utf-8")
    main = tmp_path / "main.a7"
    main.write_text(
        'import "helper" { _secret }\n'
        "main :: fn() {}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    assert "private" in (result.stdout + result.stderr).lower()


def test_using_import_exits_6_with_alias_guidance(tmp_path):
    main = tmp_path / "main.a7"
    main.write_text(
        'using import "std/io"\n'
        "main :: fn() {}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    text = result.stdout + result.stderr
    assert "using import is not supported" in text
    assert 'alias :: import' in text


def test_hardlink_duplicate_import_exits_6(tmp_path):
    helper = tmp_path / "helper.a7"
    helper.write_text("pub value :: fn() i32 { ret 7 }\n", encoding="utf-8")
    link = tmp_path / "link.a7"
    try:
        os.link(helper, link)
    except OSError:
        pytest.skip("cannot create hardlink")
    main = tmp_path / "main.a7"
    main.write_text(
        'h :: import "helper"\n'
        'l :: import "link"\n'
        "main :: fn() {}\n",
        encoding="utf-8",
    )
    result = run_cli(["--mode", "semantic", str(main)])
    assert result.returncode == 6, result.stdout + result.stderr
    assert "uplicate import" in result.stdout + result.stderr


def test_hardlink_diamond_shares_one_module(tmp_path):
    shared = tmp_path / "shared.a7"
    shared.write_text("pub value :: fn() i32 { ret 3 }\n", encoding="utf-8")
    (tmp_path / "left").mkdir()
    (tmp_path / "right").mkdir()
    (tmp_path / "left" / "part.a7").write_text(
        'shared :: import "../shared"\n'
        "pub left_value :: fn() i32 { ret shared.value() }\n",
        encoding="utf-8",
    )
    link = tmp_path / "right" / "alias.a7"
    try:
        os.link(shared, link)
    except OSError:
        pytest.skip("cannot create hardlink")
    (tmp_path / "right" / "part.a7").write_text(
        'shared :: import "alias"\n'
        "pub right_value :: fn() i32 { ret shared.value() * 2 }\n",
        encoding="utf-8",
    )
    main = tmp_path / "main.a7"
    main.write_text(
        'l :: import "left/part"\n'
        'r :: import "right/part"\n'
        "main :: fn() {\n"
        "    x := l.left_value()\n"
        "    y := r.right_value()\n"
        "}\n",
        encoding="utf-8",
    )
    out = tmp_path / "main.zig"
    result = run_cli(["--mode", "compile", "--output", str(out), str(main)])
    assert result.returncode == 0, result.stdout + result.stderr
