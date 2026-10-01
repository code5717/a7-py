"""Phase 1 frontend pins: unclosed comments, duplicate imports, and
imported-file error-stage attribution.

CLI exit codes are the compiler's own vocabulary (a7/compile.py ExitCode):
unclosed comment is 4, duplicate import is 6, missing/unreadable dependency
is 3, dependency tokenize failure is 4, dependency parse failure is 5.
"""

import json
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
        cwd=ROOT, capture_output=True, text=True, env=env,
    )


def compile_main(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    main = tmp_path / "main.a7"
    main.write_text(source, encoding="utf-8")
    out = tmp_path / "main.zig"
    return run_cli(["--mode", "compile", "--format", "json",
                    "--output", str(out), str(main)])


def payload_of(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"stdout is not valid JSON:\n{result.stdout}\n{result.stderr}")


def test_unclosed_block_comment_exits_4(tmp_path: Path) -> None:
    main = tmp_path / "main.a7"
    main.write_text("main :: fn() {}\n/* note\nhelper :: fn() {}\n", encoding="utf-8")
    result = run_cli([str(main)])
    assert result.returncode == 4, result.stdout + result.stderr
    assert "not closed" in (result.stdout + result.stderr).lower()


def write_helper(tmp_path: Path, source: str = "pub value :: fn() i32 {\n    ret 7\n}\n") -> None:
    (tmp_path / "helper.a7").write_text(source, encoding="utf-8")


def test_duplicate_import_same_path_exits_6(tmp_path: Path) -> None:
    write_helper(tmp_path)
    result = compile_main(
        tmp_path,
        'h :: import "helper"\nh2 :: import "helper"\n'
        "main :: fn() {}\n",
    )
    assert result.returncode == 6, result.stdout + result.stderr
    assert "uplicate import" in result.stdout + result.stderr


def test_duplicate_import_alternate_spelling_exits_6(tmp_path: Path) -> None:
    write_helper(tmp_path)
    result = compile_main(
        tmp_path,
        'h :: import "helper"\nj :: import "./helper"\n'
        "main :: fn() {}\n",
    )
    assert result.returncode == 6, result.stdout + result.stderr
    assert "uplicate import" in result.stdout + result.stderr


def test_duplicate_import_second_alias_exits_6(tmp_path: Path) -> None:
    write_helper(tmp_path)
    result = compile_main(
        tmp_path,
        'h :: import "helper"\nh :: import "helper"\n'
        "main :: fn() {}\n",
    )
    assert result.returncode == 6, result.stdout + result.stderr
    assert "uplicate import" in (result.stdout + result.stderr).lower() \
        or "lready defined" in (result.stdout + result.stderr).lower()


def test_duplicate_import_through_symlink_exits_6(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("no symlink support")
    write_helper(tmp_path)
    try:
        os.symlink(str(tmp_path / "helper.a7"), str(tmp_path / "link.a7"))
    except OSError:
        pytest.skip("cannot create symlink")
    result = compile_main(
        tmp_path,
        'h :: import "helper"\nl :: import "link"\n'
        "main :: fn() {}\n",
    )
    assert result.returncode == 6, result.stdout + result.stderr
    assert "uplicate import" in result.stdout + result.stderr


def test_different_files_importing_same_module_stays_legal(tmp_path: Path) -> None:
    (tmp_path / "shared.a7").write_text(
        "pub value :: fn() i32 {\n    ret 3\n}\n", encoding="utf-8")
    (tmp_path / "left.a7").write_text(
        's :: import "shared"\n'
        "pub left_value :: fn() i32 {\n    ret s.value()\n}\n",
        encoding="utf-8")
    (tmp_path / "right.a7").write_text(
        's :: import "shared"\n'
        "pub right_value :: fn() i32 {\n    ret s.value() * 2\n}\n",
        encoding="utf-8")
    result = compile_main(
        tmp_path,
        'l :: import "left"\nr :: import "right"\n'
        "main :: fn() {\n    x := l.left_value()\n    y := r.right_value()\n}\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_imported_tokenize_failure_exits_4(tmp_path: Path) -> None:
    (tmp_path / "helper.a7").write_text(
        'pub value :: fn() i32 {\n    ret 7\n}\n"unterminated\n',
        encoding="utf-8")
    result = compile_main(
        tmp_path, 'h :: import "helper"\nmain :: fn() {}\n')
    assert result.returncode == 4, result.stdout + result.stderr
    payload = payload_of(result)
    assert payload["error"]["category"] == "tokenize"
    assert "helper.a7" in json.dumps(payload["error"])


def test_imported_parse_failure_exits_5(tmp_path: Path) -> None:
    (tmp_path / "helper.a7").write_text(
        "main :: fn() {\n    x := (\n}\n", encoding="utf-8")
    result = compile_main(
        tmp_path, 'h :: import "helper"\nmain :: fn() {}\n')
    assert result.returncode == 5, result.stdout + result.stderr
    payload = payload_of(result)
    assert payload["error"]["category"] == "parse"
    assert "helper.a7" in json.dumps(payload["error"])


def test_missing_import_exits_3(tmp_path: Path) -> None:
    result = compile_main(
        tmp_path, 'h :: import "absent"\nmain :: fn() {}\n')
    assert result.returncode == 3, result.stdout + result.stderr
    payload = payload_of(result)
    assert payload["error"]["category"] == "io"
    assert "absent" in json.dumps(payload["error"])


def test_unreadable_import_exits_3(tmp_path: Path) -> None:
    (tmp_path / "helper.a7").write_bytes(b"\xff\xfe invalid utf-8 \x80\x81\n")
    result = compile_main(
        tmp_path, 'h :: import "helper"\nmain :: fn() {}\n')
    assert result.returncode == 3, result.stdout + result.stderr
    payload = payload_of(result)
    assert payload["error"]["category"] == "io"
