"""CLI regression tests for failure handling and mode contracts."""

import json
import os
import subprocess
import sys
from pathlib import Path

from a7.compile import ExitCode


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = PROJECT_ROOT / "main.py"


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the compiler CLI and capture output."""
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{PROJECT_ROOT}:{existing_pythonpath}" if existing_pythonpath else str(PROJECT_ROOT)
    )
    return subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_parse_error_returns_nonzero(tmp_path):
    src = tmp_path / "parse_error.a7"
    src.write_text(
        """
main :: fn() {
    x := (
}
""".strip()
    )

    result = run_cli([str(src)])
    combined = result.stdout + result.stderr

    assert result.returncode == ExitCode.PARSE
    assert "expected expression" in combined.lower()


def test_cli_semantic_error_returns_nonzero_and_skips_codegen(tmp_path):
    src = tmp_path / "semantic_error.a7"
    out = tmp_path / "semantic_error.zig"
    src.write_text(
        """
main :: fn() {
    x: i32 = "hello"
}
""".strip()
    )

    result = run_cli([str(src), "-o", str(out)])
    combined = result.stdout + result.stderr

    assert result.returncode == ExitCode.SEMANTIC
    assert "type mismatch" in combined.lower()
    assert not out.exists()


def test_cli_missing_local_import_returns_semantic_error(tmp_path):
    src = tmp_path / "missing_import.a7"
    out = tmp_path / "missing_import.zig"
    src.write_text(
        """
missing :: import "missing/module"

main :: fn() {}
""".strip()
    )

    result = run_cli(["--format", "json", str(src), "-o", str(out)])

    assert result.returncode == ExitCode.SEMANTIC
    payload = json.loads(result.stdout)
    assert payload["error"]["category"] == "semantic"
    assert "module" in payload["error"]["details"][0]["message"].lower()
    assert not out.exists()


def test_cli_virtual_stdlib_import_does_not_require_a7_file(tmp_path):
    src = tmp_path / "stdlib_import.a7"
    out = tmp_path / "stdlib_import.zig"
    src.write_text(
        """
io :: import "std/io"

main :: fn() {
    io.println("ok")
}
""".strip()
    )

    result = run_cli([str(src), "-o", str(out)])

    assert result.returncode == ExitCode.SUCCESS
    assert out.exists()


def test_cli_unknown_virtual_stdlib_function_returns_semantic_error(tmp_path):
    src = tmp_path / "bad_stdlib_call.a7"
    out = tmp_path / "bad_stdlib_call.zig"
    src.write_text(
        """
console :: import "std/io"

main :: fn() {
    console.nope("ok")
}
""".strip()
    )

    result = run_cli(["--format", "json", str(src), "-o", str(out)])

    assert result.returncode == ExitCode.SEMANTIC
    payload = json.loads(result.stdout)
    assert payload["error"]["category"] == "semantic"
    assert "std/io" in payload["error"]["details"][0]["message"]
    assert "nope" in payload["error"]["details"][0]["message"]
    assert not out.exists()


def test_cli_json_union_initializer_error_does_not_crash(tmp_path):
    src = tmp_path / "bad_union.a7"
    out = tmp_path / "bad_union.zig"
    src.write_text(
        """
Value :: union {
    int_val: i32
    float_val: f64
}

main :: fn() {
    v := Value{int_val: 42, float_val: 1.5}
}
""".strip()
    )

    result = run_cli(["--format", "json", str(src), "-o", str(out)])

    assert result.returncode == ExitCode.SEMANTIC
    payload = json.loads(result.stdout)
    assert payload["error"]["category"] == "semantic"
    assert "one named field" in payload["error"]["details"][0]["message"]
    assert payload["stages"]["parse"]["ast"]["declarations"][1]["body"]["statements"][0]["value"]["struct_type"] == "Value"
    assert not out.exists()


def test_cli_fallthrough_returns_semantic_error_and_skips_codegen(tmp_path):
    src = tmp_path / "fallthrough.a7"
    out = tmp_path / "fallthrough.zig"
    src.write_text(
        """
main :: fn() {
    x := 1
    match x {
        case 1: {
            fall
        }
        case 2: {}
    }
}
""".strip()
    )

    result = run_cli(["--format", "json", str(src), "-o", str(out)])

    assert result.returncode == ExitCode.SEMANTIC
    payload = json.loads(result.stdout)
    assert payload["error"]["category"] == "semantic"
    assert "fallthrough" in payload["error"]["details"][0]["message"].lower()
    assert not out.exists()


def test_cli_parse_error_json_mode_returns_error_object(tmp_path):
    src = tmp_path / "parse_error_json.a7"
    src.write_text(
        """
main :: fn() {
    x := (
}
""".strip()
    )

    result = run_cli(["--format", "json", str(src)])

    assert result.returncode == ExitCode.PARSE
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "2.0"
    assert payload["status"] == "error"
    assert payload["mode"] == "compile"
    assert "error" in payload
    assert payload["error"]["category"] == "parse"
    assert payload["error"]["details"][0]["type"] in {"ParseError", "CompilerError"}


def test_cli_rejects_output_when_mode_is_not_compile(tmp_path):
    src = tmp_path / "ok.a7"
    src.write_text("main :: fn() {}")
    out = tmp_path / "out.zig"

    result = run_cli(["--mode", "tokens", "--output", str(out), str(src)])

    assert result.returncode == ExitCode.USAGE
    assert "--output is only valid" in result.stderr


def test_cli_io_error_exit_code_for_missing_file():
    missing = "does_not_exist.a7"
    result = run_cli([missing])

    assert result.returncode == ExitCode.IO


def test_cli_compile_mode_supports_doc_out(tmp_path):
    src = tmp_path / "hello.a7"
    out = tmp_path / "hello.zig"
    doc = tmp_path / "hello.md"
    src.write_text(
        """
io :: import "std/io"

main :: fn() {
    io.println("hello")
}
""".strip()
    )

    result = run_cli(
        [
            "--mode",
            "compile",
            "--doc-out",
            str(doc),
            "--output",
            str(out),
            str(src),
        ]
    )

    assert result.returncode == ExitCode.SUCCESS
    assert out.exists()
    assert doc.exists()
    doc_text = doc.read_text()
    assert "`io` | MODULE | `module`" in doc_text
    assert f"**Output:** `{out}`" in doc_text


def test_cli_doc_mode_writes_default_markdown_path(tmp_path):
    src = tmp_path / "doc_only.a7"
    default_doc = tmp_path / "doc_only.md"
    src.write_text(
        """
main :: fn() {}
""".strip()
    )

    result = run_cli(["--mode", "doc", str(src)])

    assert result.returncode == ExitCode.SUCCESS
    assert default_doc.exists()
    doc_text = default_doc.read_text()
    assert "**Output:** `(not written; in-memory)`" in doc_text
    assert "unknown type" not in doc_text


def test_cli_compile_mode_supports_doc_out_auto_keyword(tmp_path):
    src = tmp_path / "auto_doc.a7"
    out = tmp_path / "auto_doc.zig"
    expected_doc = tmp_path / "auto_doc.md"
    src.write_text("main :: fn() {}")

    result = run_cli(
        [
            "--mode",
            "compile",
            "--output",
            str(out),
            "--doc-out",
            "auto",
            str(src),
        ]
    )

    assert result.returncode == ExitCode.SUCCESS
    assert out.exists()
    assert expected_doc.exists()
