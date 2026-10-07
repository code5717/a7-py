"""Human diagnostics: stream, single printing, file naming, literal text.

Every case drives the real CLI. Human-mode diagnostics belong on stderr;
`--format json` keeps its payload on stdout.
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
PARSE_ERROR = "main :: fn() {\n    x := (\n}\n"
TYPE_ERROR = 'main :: fn() {\n    x: i32 = "hello"\n}\n'


def run_cli(args, cwd=PROJECT_ROOT):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "NO_COLOR": "1", "COLUMNS": "200"}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_unknown_backend_name_with_markup_is_printed_literally(tmp_path):
    source = write(tmp_path / "ok.a7", HELLO)

    result = run_cli([source, "--backend", "[/b]"])

    assert result.returncode == ExitCode.CODEGEN, result.stdout + result.stderr
    assert "Unknown backend '[/b]'" in result.stderr


def test_source_line_with_markup_is_printed_literally(tmp_path):
    source = write(
        tmp_path / "markup.a7",
        'io :: import "std/io"\nmain :: fn() {\n    io.println("{}", [bold]x)\n}\n',
    )

    result = run_cli([source, "--mode", "pipeline"])

    assert result.returncode == ExitCode.SEMANTIC, result.stdout + result.stderr
    assert 'io.println("{}", [bold]x)' in result.stderr


@pytest.mark.parametrize("mode", ["compile", "ast", "semantic", "pipeline", "doc"])
def test_legacy_human_parse_error_goes_to_stderr(tmp_path, mode):
    source = write(tmp_path / "broken.a7", PARSE_ERROR)

    result = run_cli([source, "--mode", mode])

    assert result.returncode == ExitCode.PARSE
    assert result.stdout == ""
    assert "Expected expression" in result.stderr


def test_legacy_human_semantic_error_goes_to_stderr(tmp_path):
    source = write(tmp_path / "typed.a7", TYPE_ERROR)

    result = run_cli([source, "--mode", "pipeline"])

    assert result.returncode == ExitCode.SEMANTIC
    assert result.stdout == ""
    assert "Type mismatch" in result.stderr


def test_json_error_stays_on_stdout(tmp_path):
    source = write(tmp_path / "typed.a7", TYPE_ERROR)

    result = run_cli([source, "--mode", "pipeline", "--format", "json"])

    assert result.returncode == ExitCode.SEMANTIC
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "error"


@pytest.mark.parametrize("command", ["check", "build", "run"])
def test_subcommand_prints_a_parse_error_once(tmp_path, command):
    # No Zig needed: build and run stop at the failed compile.
    source = write(tmp_path / "broken.a7", PARSE_ERROR)

    result = run_cli([command, source])

    assert result.returncode == ExitCode.PARSE
    assert result.stdout == ""
    assert result.stderr.count("Expected expression") == 1


@pytest.mark.parametrize("text", [PARSE_ERROR, TYPE_ERROR], ids=["parse", "semantic"])
def test_check_prints_what_the_legacy_pipeline_prints(tmp_path, text):
    source = write(tmp_path / "program.a7", text)

    check = run_cli(["check", source])
    legacy = run_cli([source, "--mode", "pipeline"])

    assert check.returncode == legacy.returncode != 0
    assert check.stderr == legacy.stderr
    # The snippet line under the caret, and for the semantic case the hint.
    assert "2 ┃" in check.stderr
    if text == TYPE_ERROR:
        assert "hint: Ensure the types match or use an explicit cast" in check.stderr


TWO_FILE_MAIN = (
    'io :: import "std/io"\nh :: import "helper"\n\n'
    'main :: fn() {\n    io.println("{}", h.twice(2) + oops)\n}\n'
)
TWO_FILE_HELPER = "pub twice :: fn(x: i32) i32 {\n    ret x * factor\n}\n"


def test_errors_in_two_modules_each_name_their_file(tmp_path):
    write(tmp_path / "main.a7", TWO_FILE_MAIN)
    write(tmp_path / "helper.a7", TWO_FILE_HELPER)

    result = run_cli(["main.a7", "--mode", "pipeline"], cwd=tmp_path)

    assert result.returncode == ExitCode.SEMANTIC, result.stdout + result.stderr
    assert "--> helper.a7:2:13" in result.stderr
    assert "--> main.a7:5:35" in result.stderr


def test_error_path_is_relative_to_the_working_directory(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    write(project / "main.a7", TWO_FILE_MAIN)
    write(project / "helper.a7", TWO_FILE_HELPER)

    result = run_cli([project / "main.a7", "--mode", "pipeline"], cwd=tmp_path)

    assert "--> proj/helper.a7:2:13" in result.stderr
    assert "--> proj/main.a7:5:35" in result.stderr


@pytest.mark.parametrize("command", [["check"], ["--mode", "pipeline"]], ids=["check", "legacy"])
def test_parse_error_in_imported_module_shows_that_modules_source(tmp_path, command):
    write(tmp_path / "main.a7", 'io :: import "std/io"\nh :: import "helper"\n\nmain :: fn() {\n    io.println("{}", h.twice(2))\n}\n')
    write(tmp_path / "helper.a7", "// helper\npub twice :: fn(x: i32) i32 {\n    ret x *\n}\n")

    result = run_cli([*command, "main.a7"], cwd=tmp_path)

    assert result.returncode == ExitCode.PARSE, result.stdout + result.stderr
    assert "--> helper.a7:3:" in result.stderr
    assert "3 ┃     ret x *" in result.stderr


def test_tokenizer_error_names_the_file_and_position(tmp_path):
    write(tmp_path / "main.a7", 'io :: import "std/io"\nmain :: fn() {\n    io.println("open)\n}\n')

    result = run_cli(["main.a7"], cwd=tmp_path)

    assert result.returncode == ExitCode.TOKENIZE
    assert "--> main.a7:3:" in result.stderr


def test_codegen_error_shows_location_and_snippet(tmp_path):
    # Passes semantic analysis, fails in the backend.
    write(tmp_path / "main.a7", "a :: fn(k: i32) i32 {\n    helper :: fn(v: i32) i32 { ret v + k }\n    ret k\n}\nmain :: fn() {\n    y := a(1)\n}\n")

    result = run_cli(["main.a7"], cwd=tmp_path)

    assert result.returncode == ExitCode.CODEGEN, result.stdout + result.stderr
    assert "nested function 'helper' uses 'k' from the enclosing function" in result.stderr
    assert "--> main.a7:2:5" in result.stderr
    assert "2 ┃     helper :: fn(v: i32) i32 { ret v + k }" in result.stderr
