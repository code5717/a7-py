"""Compound-assignment operand types through the real CLI and real Zig.

Rejected cases are programs Zig 0.16.0 rejects after A7 emits them (TYP-05).
Accepted cases are programs Zig builds today; they must stay accepted.
Zig checks are compile-only (`build-obj -fno-emit-bin`); nothing is executed.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from a7.compile import ExitCode
from conftest import shared_zig_cache


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compound_program(decls: str, statement: str) -> str:
    return (
        'io :: import "std/io"\n'
        "f :: fn() {\n"
        f"{decls}"
        f"    {statement}\n"
        '    io.println("{}", 1)\n'
        "}\n"
        "main :: fn() {\n"
        "    f()\n"
        "}\n"
    )


def statement_line(source: str, statement: str) -> int:
    lines = source.splitlines()
    return next(i for i, line in enumerate(lines, 1) if line.strip() == statement)


def run_cli(source_path: Path, output_path: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--format",
            "json",
            str(source_path),
            "--output",
            str(output_path),
        ],
        cwd=source_path.parent,
        capture_output=True,
        text=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    return result, json.loads(result.stdout)


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


@pytest.mark.parametrize(
    ("decls", "statement", "fragment"),
    [
        pytest.param(
            '    a: string = "x"\n    b: string = "y"\n',
            "a += b",
            "Requires numeric type",
            id="b34-string-add",
        ),
        pytest.param(
            "    a: f64 = 1.0\n    b: f64 = 3.0\n",
            "a <<= b",
            "Requires integer type",
            id="c35-f64-shl",
        ),
        pytest.param(
            "    a: bool = true\n    b: bool = false\n",
            "a += b",
            "Requires numeric type",
            id="c36-bool-add",
        ),
        pytest.param(
            '    a: string = "x"\n    b: string = "y"\n',
            "a %= b",
            "Requires numeric type",
            id="c37-string-mod",
        ),
        pytest.param(
            # Valid left operand, invalid right operand.
            '    a: i32 = 1\n    b: string = "y"\n',
            "a += b",
            "Requires numeric type",
            id="i32-add-string-rhs",
        ),
        # char has no arithmetic: `a + b` on two chars was already rejected,
        # and the compound forms follow the binary operators.
        pytest.param(
            "    a: char = 'a'\n    b: char = 'b'\n",
            "a += b",
            "Requires numeric type",
            id="char-add-char",
        ),
        pytest.param(
            "    a: char = 'a'\n    b: char = 'b'\n",
            "a |= b",
            "Requires integer type",
            id="char-or-char",
        ),
    ],
)
def test_compound_assignment_rejects_operand_types_zig_rejects(tmp_path, decls, statement, fragment):
    source = compound_program(decls, statement)
    source_path = tmp_path / "main.a7"
    output_path = tmp_path / "main.zig"
    source_path.write_text(source, encoding="utf-8")

    result, payload = run_cli(source_path, output_path)

    assert result.returncode == ExitCode.SEMANTIC, result.stdout
    assert not output_path.exists()
    details = payload["error"]["details"]
    matching = [d for d in details if fragment in d["message"]]
    assert matching, [d["message"] for d in details]
    assert matching[0]["span"]["start_line"] == statement_line(source, statement)
    # c37 used to reach the safety pass and blame the divisor; the operand
    # type is the actual problem.
    assert not any("divisor" in d["message"] for d in details), details


@pytest.mark.parametrize(
    ("decls", "statement"),
    [
        pytest.param("    a: i32 = 1\n    b: i32 = 0\n", "a += 2", id="i32-add-literal"),
        pytest.param("    a: f64 = 1.0\n    b: f64 = 0.0\n", "a *= 2.0", id="f64-mul-literal"),
        pytest.param("    a: u32 = 1\n    b: u8 = 3\n", "a <<= b", id="u32-shl-u8"),
        pytest.param("    a: f64 = 1.0\n    b: f64 = 0.0\n", "a += 2", id="f64-add-int-literal"),
        # bool supports &, |, ^ in Zig; these build today.
        pytest.param("    a: bool = true\n    b: bool = false\n", "a ^= b", id="bool-xor-bool"),
        pytest.param("    a: bool = true\n    b: bool = false\n", "a &= b", id="bool-and-bool"),
    ],
)
def test_compound_assignment_accepts_programs_zig_builds(tmp_path, zig, decls, statement):
    source = compound_program(decls, statement)
    source_path = tmp_path / "main.a7"
    output_path = tmp_path / "main.zig"
    source_path.write_text(source, encoding="utf-8")

    result, payload = run_cli(source_path, output_path)

    assert result.returncode == ExitCode.SUCCESS, payload.get("error")
    process = subprocess.run(
        [
            zig,
            "build-obj",
            "-fno-emit-bin",
            str(output_path),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--global-cache-dir",
            str(shared_zig_cache() / "global"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
