"""Stage-by-stage error handling matrix across modes and output formats."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.compile import ExitCode


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = PROJECT_ROOT / "main.py"

ALL_MODES = ["compile", "tokens", "ast", "semantic", "pipeline", "doc"]
PARSE_MODES = ["compile", "ast", "semantic", "pipeline", "doc"]
SEMANTIC_MODES = ["compile", "semantic", "pipeline", "doc"]
CODEGEN_MODES = ["compile", "pipeline", "doc"]
FORMATS = ["human", "json"]


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


def parse_json_output(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"stdout is not valid JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}")


@pytest.fixture
def stage_sources(tmp_path: Path) -> dict[str, Path]:
    tokenize_error = tmp_path / "tokenize_error.a7"
    tokenize_error.write_text(
        'io :: import "std/io"\nmain :: fn() {\n    io.println("Hello, World!)\n}\n',
        encoding="utf-8",
    )

    parse_error = tmp_path / "parse_error.a7"
    parse_error.write_text(
        "main :: fn() {\n    x := (\n}\n",
        encoding="utf-8",
    )

    semantic_error = tmp_path / "semantic_error.a7"
    semantic_error.write_text(
        'main :: fn() {\n    x: i32 = "hello"\n}\n',
        encoding="utf-8",
    )

    deferred_semantic_error = tmp_path / "deferred_semantic_error.a7"
    deferred_semantic_error.write_text(
        "main :: fn() {\n    x: i32 = 1\n    defer del x\n}\n",
        encoding="utf-8",
    )

    ok_program = tmp_path / "ok.a7"
    ok_program.write_text("main :: fn() {}\n", encoding="utf-8")

    return {
        "tokenize": tokenize_error,
        "parse": parse_error,
        "semantic": semantic_error,
        "deferred_semantic": deferred_semantic_error,
        "ok": ok_program,
    }


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_tokenize_errors_are_well_handled(
    stage_sources: dict[str, Path], mode: str, output_format: str
) -> None:
    args = ["--mode", mode]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["tokenize"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.TOKENIZE
    if output_format == "human":
        combined = (result.stdout + result.stderr).lower()
        assert "string is not closed" in combined
        assert "hint" in combined
        assert "line" in combined
    else:
        payload = parse_json_output(result)
        assert payload["schema_version"] == "2.0"
        assert payload["status"] == "error"
        assert payload["error"]["category"] == "tokenize"
        assert payload["error"]["details"][0]["type"] == "TokenizerError"
        assert payload["error"]["details"][0]["span"]["start_line"] == 3
        if mode == "compile":
            assert "output_path" not in payload["artifacts"]


@pytest.mark.parametrize("mode", PARSE_MODES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_parse_errors_are_well_handled(
    stage_sources: dict[str, Path], mode: str, output_format: str
) -> None:
    args = ["--mode", mode]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["parse"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.PARSE
    if output_format == "human":
        combined = (result.stdout + result.stderr).lower()
        assert "expected expression" in combined
    else:
        payload = parse_json_output(result)
        assert payload["status"] == "error"
        assert payload["error"]["category"] == "parse"
        assert payload["stages"]["tokenize"]["ok"] is True
        assert payload["stages"]["parse"]["ok"] is False
        if mode == "compile":
            assert "output_path" not in payload["artifacts"]


@pytest.mark.parametrize("output_format", FORMATS)
def test_tokens_mode_skips_parse_errors(
    stage_sources: dict[str, Path], output_format: str
) -> None:
    args = ["--mode", "tokens"]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["parse"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.SUCCESS
    if output_format == "json":
        payload = parse_json_output(result)
        assert payload["status"] == "ok"
        assert payload["mode"] == "tokens"
        assert "parse" not in payload["stages"]


@pytest.mark.parametrize("mode", SEMANTIC_MODES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_semantic_errors_are_well_handled(
    stage_sources: dict[str, Path], mode: str, output_format: str
) -> None:
    args = ["--mode", mode]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["semantic"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.SEMANTIC
    if output_format == "human":
        combined = (result.stdout + result.stderr).lower()
        assert "type mismatch" in combined
        assert "hint" in combined
    else:
        payload = parse_json_output(result)
        assert payload["status"] == "error"
        assert payload["error"]["category"] == "semantic"
        assert payload["stages"]["parse"]["ok"] is True
        assert payload["stages"]["semantic"]["ok"] is False
        if mode == "compile":
            assert "output_path" not in payload["artifacts"]


@pytest.mark.parametrize("mode", SEMANTIC_MODES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_deferred_statement_errors_are_well_handled(
    stage_sources: dict[str, Path], mode: str, output_format: str
) -> None:
    args = ["--mode", mode]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["deferred_semantic"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.SEMANTIC
    if output_format == "human":
        combined = (result.stdout + result.stderr).lower()
        assert "reference" in combined
        assert "defer" in combined or "del" in combined
    else:
        payload = parse_json_output(result)
        assert payload["status"] == "error"
        assert payload["error"]["category"] == "semantic"
        assert payload["stages"]["semantic"]["ok"] is False
        if mode == "compile":
            assert "output_path" not in payload["artifacts"]


@pytest.mark.parametrize("output_format", FORMATS)
def test_ast_mode_skips_semantic_errors(
    stage_sources: dict[str, Path], output_format: str
) -> None:
    args = ["--mode", "ast"]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["semantic"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.SUCCESS
    if output_format == "json":
        payload = parse_json_output(result)
        assert payload["status"] == "ok"
        assert payload["mode"] == "ast"
        assert "semantic" not in payload["stages"]


@pytest.mark.parametrize("mode", CODEGEN_MODES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_codegen_errors_are_well_handled(
    stage_sources: dict[str, Path], mode: str, output_format: str
) -> None:
    args = ["--mode", mode, "--backend", "nope"]
    if output_format == "json":
        args += ["--format", "json"]
    args += [str(stage_sources["ok"])]

    result = run_cli(args)

    assert result.returncode == ExitCode.CODEGEN
    if output_format == "human":
        combined = (result.stdout + result.stderr).lower()
        assert "unknown backend" in combined
        # Ensure we do not print duplicate codegen errors.
        assert combined.count("unknown backend") == 1
    else:
        payload = parse_json_output(result)
        assert payload["status"] == "error"
        assert payload["error"]["category"] == "codegen"
        assert payload["stages"]["parse"]["ok"] is True
        if mode == "compile":
            assert "output_path" not in payload["artifacts"]


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize("output_format", FORMATS)
def test_io_errors_are_well_handled(mode: str, output_format: str) -> None:
    args = ["--mode", mode]
    if output_format == "json":
        args += ["--format", "json"]
    args += ["/tmp/this_file_does_not_exist_1234567890.a7"]

    result = run_cli(args)

    assert result.returncode == ExitCode.IO
    if output_format == "human":
        combined = (result.stdout + result.stderr).lower()
        assert "input file not found" in combined
    else:
        payload = parse_json_output(result)
        assert payload["status"] == "error"
        assert payload["error"]["category"] == "io"


def test_usage_contract_for_output_with_non_compile_mode(stage_sources: dict[str, Path]) -> None:
    out = stage_sources["ok"].with_suffix(".zig")
    result = run_cli(["--mode", "tokens", "--output", str(out), str(stage_sources["ok"])])

    assert result.returncode == ExitCode.USAGE
    assert "--output is only valid" in result.stderr
