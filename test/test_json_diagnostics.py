"""Shape of `error.details` in `--format json` (schema 3.0).

Each detail carries the error `code` (the enum value from a7/errors.py, or
null), the `hint` when one exists, a stable `type`, and a `message` without
the `file:line:col:` prefix; `file` and `span` hold the location. The
top-level `error.message` has no `file` beside it and keeps the prefix.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HELLO = 'io :: import "std/io"\n\nmain :: fn() {\n    io.println("hi")\n}\n'


def run_cli(args, cwd=PROJECT_ROOT):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def failure(tmp_path, text, *args, expect):
    source = tmp_path / "main.a7"
    source.write_text(text, encoding="utf-8")
    result = run_cli([source, "--format", "json", *args])
    assert result.returncode == expect, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "3.0"
    return source, payload["error"]


def test_semantic_detail_carries_code_and_hint(tmp_path):
    source, error = failure(
        tmp_path, 'main :: fn() {\n    x: i32 = "hello"\n}\n', expect=ExitCode.SEMANTIC,
    )

    [detail] = error["details"]
    assert detail["type"] == "TypeCheckError"
    assert detail["code"] == "type_mismatch"
    assert detail["hint"] == "Ensure the types match or use an explicit cast"
    assert detail["message"] == "Type mismatch: expected 'i32', got 'string' (Variable 'x')"
    assert detail["file"] == str(source)
    assert (detail["span"]["start_line"], detail["span"]["start_column"]) == (2, 5)


def test_tokenizer_detail_carries_code_and_hint(tmp_path):
    _, error = failure(
        tmp_path, 'io :: import "std/io"\nmain :: fn() {\n    io.println("open)\n}\n',
        expect=ExitCode.TOKENIZE,
    )

    [detail] = error["details"]
    assert detail["type"] == "TokenizerError"
    assert detail["code"] == "not_closed_string"
    assert detail["hint"] == "Close the string literal with a double quote"
    assert detail["span"]["start_line"] == 3


def test_parse_detail_has_null_code_and_no_location_in_message(tmp_path):
    _, error = failure(tmp_path, "main :: fn() {\n    x := (\n}\n", expect=ExitCode.PARSE)

    [detail] = error["details"]
    assert detail["type"] == "ParseError"
    assert detail["code"] is None
    assert detail["hint"] is None
    assert detail["message"] == "Expected expression"
    # The top-level summary has no `file` field beside it and keeps the prefix.
    assert error["message"] == "main.a7:2:11: Expected expression"
    assert (detail["span"]["start_line"], detail["span"]["start_column"]) == (2, 11)


def test_safety_failure_has_its_own_type_and_a_hint(tmp_path):
    _, error = failure(
        tmp_path,
        'io :: import "std/io"\navg :: fn(sum: i32, n: i32) i32 {\n    ret sum / n\n}\n'
        'main :: fn() {\n    io.println("{}", avg(4, 2))\n}\n',
        "--mode", "pipeline", expect=ExitCode.SEMANTIC,
    )

    [detail] = error["details"]
    assert error["category"] == "semantic"
    assert detail["type"] == "SafetyError"
    assert detail["code"] is None
    assert "if n != 0 {" in detail["hint"]
    assert detail["message"].startswith("Divisor not proven non-zero")


def test_coded_safety_failure_keeps_its_code(tmp_path):
    _, error = failure(
        tmp_path,
        'io :: import "std/io"\nN :: struct { v: i32 }\nmain :: fn() {\n    n := new N\n'
        '    n.v = 3\n    io.println("{}", 1)\n    del n\n}\n',
        "--mode", "pipeline", expect=ExitCode.SEMANTIC,
    )

    detail = error["details"][0]
    assert detail["type"] == "SafetyError"
    assert detail["code"] == "cannot_dereference"
    assert "if n != nil {" in detail["hint"]


def test_unknown_backend_is_a_codegen_error_not_a_python_class(tmp_path):
    _, error = failure(tmp_path, HELLO, "--backend", "nope", expect=ExitCode.CODEGEN)

    [detail] = error["details"]
    assert error["category"] == "codegen"
    assert detail["type"] == "CodegenError"
    assert detail["message"] == "Unknown backend 'nope'. Available backends: zig"
    # The Python class stays available for bug reports.
    assert error["exception_type"] == "ValueError"


def test_codegen_detail_has_a_span(tmp_path):
    _, error = failure(
        tmp_path,
        "a :: fn(k: i32) i32 {\n    helper :: fn(v: i32) i32 { ret v + k }\n    ret k\n}\nmain :: fn() {\n    y := a(1)\n}\n",
        expect=ExitCode.CODEGEN,
    )

    [detail] = error["details"]
    assert detail["type"] == "CodegenError"
    assert detail["message"] == (
        "Zig backend: nested function 'helper' uses 'k' from the enclosing function; "
        "pass it as a parameter"
    )
    assert (detail["span"]["start_line"], detail["span"]["start_column"]) == (2, 5)
    assert error["span"] == detail["span"]


def test_internal_error_has_a_detail_entry(tmp_path, monkeypatch, capsys):
    # The parser is replaced at its boundary to force an unexpected exception;
    # this leaves real internal failures inside later stages unverified.
    from a7.cli import main
    from a7.parser import Parser

    source = tmp_path / "main.a7"
    source.write_text(HELLO, encoding="utf-8")

    def parser_failure(_parser):
        raise RuntimeError("injected parser boundary failure")

    monkeypatch.setattr(Parser, "parse", parser_failure)
    monkeypatch.setattr(sys, "argv", ["a7", str(source), "--mode", "ast", "--format", "json"])
    with pytest.raises(SystemExit) as exited:
        main()

    error = json.loads(capsys.readouterr().out)["error"]
    assert exited.value.code == ExitCode.INTERNAL
    assert error["category"] == "internal"
    assert error["details"] == [{
        "type": "InternalError",
        "code": None,
        "message": "injected parser boundary failure",
        "hint": None,
        "file": str(source),
    }]


def test_error_in_imported_module_names_that_file(tmp_path):
    (tmp_path / "helper.a7").write_text(
        "pub twice :: fn(x: i32) i32 {\n    ret x * factor\n}\n", encoding="utf-8",
    )
    _, error = failure(
        tmp_path,
        'io :: import "std/io"\nh :: import "helper"\nmain :: fn() {\n    io.println("{}", h.twice(2))\n}\n',
        "--mode", "pipeline", expect=ExitCode.SEMANTIC,
    )

    detail = error["details"][0]
    assert Path(detail["file"]).name == "helper.a7"
    assert "helper.a7" not in detail["message"]
    assert detail["span"]["start_line"] == 2
