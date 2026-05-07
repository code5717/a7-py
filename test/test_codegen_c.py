"""Regression tests for C backend code generation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.backends import get_backend, list_backends
from src.ast_nodes import ASTNode, NodeKind
from src.errors import CodegenError
from src.compile import ExitCode


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = PROJECT_ROOT / "main.py"


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
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


def has_zig() -> bool:
    try:
        result = subprocess.run(
            ["zig", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_and_run_c(source: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    src = tmp_path / "program.a7"
    out = tmp_path / "program.c"
    bin_path = tmp_path / "program"
    src.write_text(source.strip(), encoding="utf-8")

    result = run_cli(["--backend", "c", "--output", str(out), str(src)])
    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr

    build = subprocess.run(
        ["zig", "cc", "-std=c11", str(out), "-lm", "-o", str(bin_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    return subprocess.run(
        [str(bin_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def test_backend_registry_exposes_c_backend() -> None:
    backend = get_backend("c")
    assert backend.file_extension == ".c"
    assert backend.language_name == "C"
    assert "c" in list_backends()


def test_c_backend_fall_statement_raises_codegen_error() -> None:
    backend = get_backend("c")

    with pytest.raises(CodegenError, match="fallthrough is not implemented"):
        backend.visit(ASTNode(NodeKind.FALL))


def test_cli_backend_c_default_output_extension(tmp_path: Path) -> None:
    src = tmp_path / "hello.a7"
    src.write_text(
        """
io :: import "std/io"

main :: fn() {
    io.println("hello")
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(["--backend", "c", str(src)])
    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr
    assert src.with_suffix(".c").exists()


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_passes_zig_cc_syntax_check(tmp_path: Path) -> None:
    src = tmp_path / "math_io.a7"
    out = tmp_path / "math_io.c"
    src.write_text(
        """
io :: import "std/io"
math :: import "std/math"

main :: fn() {
    x := 9.0
    io.println("sqrt({}) = {}", x, math.sqrt(x))
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(["--backend", "c", "--output", str(out), str(src)])
    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr
    assert out.exists()

    syntax = subprocess.run(
        ["zig", "cc", "-std=c11", "-c", str(out), "-o", str(tmp_path / "math_io.o")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_slice_expr_index_and_for_in(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

main :: fn() {
    arr: [4]i32 = [1, 2, 3, 4]
    tail := arr[1..4]
    total := tail[0]
    for x in tail {
        total += x
    }
    indexed_total := 0
    for i, x in tail {
        indexed_total += i + x
    }
    io.println("{} {}", total, indexed_total)
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "11 12"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_honors_labeled_break_and_continue(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

main :: fn() {
    break_total := 0
    outer_break: for i := 0; i < 3; i += 1 {
        for j := 0; j < 3; j += 1 {
            if j == 1 {
                break outer_break
            }
            break_total += 1
        }
        break_total += 100
    }

    continue_total := 0
    outer_continue: for i := 0; i < 2; i += 1 {
        for j := 0; j < 3; j += 1 {
            if j == 1 {
                continue outer_continue
            }
            continue_total += 1
        }
        continue_total += 100
    }

    io.println("{} {}", break_total, continue_total)
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "1 2"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_match_cases_keep_local_scope_and_case_defers(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

main :: fn() {
    x := 1
    match x {
        case 1: {
            y := 10
            defer io.println("case {}", y)
            io.println("body {}", y)
        }
        case 2: {
            y := 20
            io.println("other {}", y)
        }
        else: {
            y := 30
            io.println("else {}", y)
        }
    }
    io.println("after")
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == ["body 10", "case 10", "after"]
