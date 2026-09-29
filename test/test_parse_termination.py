"""Parser termination on malformed `match` statements, through the real CLI.

Before the PAR-01 fix, `parse_match_statement` looped forever on any token
other than `case`, `else` or `}` inside the braces, so every input below hung
the compiler. Each case runs the installed CLI in a subprocess with a timeout
and checks that compilation stops at the parse stage (exit 5) with a location
on the offending token.

Expected lines and columns are the ones the tokenizer reports for the
offending token, checked against the fixture text and against
`--mode tokens --format json`.
These are compile-only checks; no Zig is built or run.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 20
MATCH_STATEMENT_MESSAGE = "Expected 'case' or 'else' in match statement"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


# `match x { foo }`: a bare identifier where an arm should start.
UNKNOWN_TOKEN_SOURCE = """\
// probe: compile-only
io :: import "std/io"

main :: fn() {
    x := 1
    match x {
        foo
    }
}
"""

# Two statements on one arm line: the second `io` (line 7, column 33)
# is where the next arm should start.
TWO_STATEMENTS_SOURCE = """\
// probe: compile-only
io :: import "std/io"

main :: fn() {
    x := 1
    match x {
        case 1: io.println("a") io.println("b")
    }
}
"""

# `default:` is not an A7 arm keyword.
DEFAULT_TYPO_SOURCE = """\
// probe: compile-only
io :: import "std/io"

main :: fn() {
    x := 1
    match x {
        case 1: io.println("a")
        default: io.println("b")
    }
}
"""

CASES = [
    pytest.param(UNKNOWN_TOKEN_SOURCE, 7, 9, id="p01-unknown-token"),
    pytest.param(TWO_STATEMENTS_SOURCE, 7, 33, id="p02-two-statements-one-line"),
    pytest.param(DEFAULT_TYPO_SOURCE, 8, 9, id="p02b-default-typo"),
]


def run_cli(source: Path, output_format: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "main.py"),
                "--format",
                output_format,
                str(source),
            ],
            cwd=source.parent,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"compiler did not finish within {TIMEOUT_SECONDS}s "
            f"({output_format} format): parser hang"
        )


@pytest.mark.parametrize(("text", "line", "column"), CASES)
def test_malformed_match_statement_fails_at_offending_token_json(
    tmp_path, text, line, column
):
    source = tmp_path / "main.a7"
    source.write_text(text, encoding="utf-8")

    result = run_cli(source, "json")

    assert result.returncode == ExitCode.PARSE, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["error"]["category"] == "parse"
    assert "codegen" not in payload["stages"]
    assert not source.with_suffix(".zig").exists()
    detail = next(
        item
        for item in payload["error"]["details"]
        if MATCH_STATEMENT_MESSAGE in item["message"]
    )
    assert detail["span"]["start_line"] == line
    assert detail["span"]["start_column"] == column


@pytest.mark.parametrize(("text", "line", "column"), CASES)
def test_malformed_match_statement_fails_at_offending_token_human(
    tmp_path, text, line, column
):
    source = tmp_path / "main.a7"
    source.write_text(text, encoding="utf-8")

    result = run_cli(source, "human")

    assert result.returncode == ExitCode.PARSE, result.stdout + result.stderr
    output = ANSI_ESCAPE.sub("", result.stdout + result.stderr)
    assert "Traceback" not in output
    assert MATCH_STATEMENT_MESSAGE in output
    assert f"[line {line}: col {column}]" in output
    assert not source.with_suffix(".zig").exists()
