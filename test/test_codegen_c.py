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
def test_generated_c_for_in_caches_side_effectful_slice_iterable(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

calls := 0

make_tail :: fn(arr: [4]i32) []i32 {
    calls += 1
    ret arr[1..4]
}

main :: fn() {
    arr: [4]i32 = [1, 2, 3, 4]
    total := 0
    for x in make_tail(arr) {
        total += x
    }
    io.println("{} {}", total, calls)
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "9 1"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_string_escapes_have_runtime_effect(tmp_path: Path) -> None:
    result = build_and_run_c(
        r'''
io :: import "std/io"

main :: fn() {
    io.print("line\nquote: \"A\"\x21")
}
''',
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'line\nquote: "A"!'


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_string_slices(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

main :: fn() {
    text: string = "abcdef"
    for ch in text {
        if ch == 'a' {
            io.print("{}", ch)
        }
    }
    for ch in text[1..4] {
        io.print("{}", ch)
    }
    for ch in text[4..] {
        io.print("{}", ch)
    }
    for i, ch in text[1..3] {
        io.print("{}", ch)
    }
    io.println("")
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "abcdefbc"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_basic_match_expressions(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

Color :: enum {
    Red,
    Blue,
}

main :: fn() {
    value := 2
    exact := match value {
        case 1: 10
        case 2, 3: 20
        else: 30
    }
    ranged := match value {
        case 0..1: 100
        case 2..4: 200
        else: 300
    }
    color: Color = Color.Blue
    color_code := match color {
        case Color.Red: 1
        case Color.Blue: 2
    }
    flag: bool = false
    bool_code := match flag {
        case true: 7
        case false: 8
    }
    io.println("{} {} {} {}", exact, ranged, color_code, bool_code)
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "20 200 2 8"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_match_statement_range_patterns(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

main :: fn() {
    value := 7
    match value {
        case 0..3: {
            io.println("low")
        }
        case 4, 5: {
            io.println("mid")
        }
        case 6..9: {
            io.println("high")
        }
        else: {
            io.println("other")
        }
    }
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "high"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_match_identifier_patterns(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

main :: fn() {
    LOW :: 2
    HIGH :: 6
    value := 5
    statement_result := 0
    match value {
        case LOW: {
            statement_result = 10
        }
        case 3..HIGH: {
            statement_result = 20
        }
        else: {
            statement_result = 30
        }
    }
    expr_result := match value {
        case LOW: 100
        case 3..HIGH: 200
        else: 300
    }
    io.println("{} {}", statement_result, expr_result)
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "20 200"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_function_pointer_declarations(tmp_path: Path) -> None:
    result = build_and_run_c(
        """
io :: import "std/io"

BinaryOp :: fn(i32, i32) i32
UnaryOp :: fn(i32) i32

add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

double :: fn(value: i32) i32 {
    ret value * 2
}

apply_unary :: fn(f: UnaryOp, value: i32) i32 {
    ret f(value)
}

apply_binary :: fn(op: BinaryOp, a: i32, b: i32) i32 {
    ret op(a, b)
}

main :: fn() {
    raw: fn(i32, i32) i32 = add
    aliased: BinaryOp = add
    a := raw(2, 3)
    b := apply_binary(aliased, 5, 8)
    c := apply_unary(double, 11)
    io.println("{} {} {}", a, b, c)
}
""",
        tmp_path,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "5 13 22"


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_c_backend_match_expression_side_effectful_scrutinee_var_init(tmp_path: Path) -> None:
    src = tmp_path / "match_expr_call.a7"
    out = tmp_path / "match_expr_call.c"
    bin_path = tmp_path / "match_expr_call"
    src.write_text(
        """
io :: import "std/io"

value :: fn() i32 {
    ret 1
}

main :: fn() {
    x := match value() {
        case 1: 10
        else: 0
    }
    io.println("{}", x)
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(["--backend", "c", "--output", str(out), str(src)])
    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr

    generated = out.read_text(encoding="utf-8")
    assert "__a7_match_" in generated
    assert generated.count("value()") == 1

    build = subprocess.run(
        ["zig", "cc", "-std=c11", str(out), "-lm", "-o", str(bin_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    run = subprocess.run(
        [str(bin_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.strip() == "10"


def test_c_backend_match_expression_side_effectful_scrutinee_in_expression_fails_closed(tmp_path: Path) -> None:
    src = tmp_path / "match_expr_call_inline.a7"
    out = tmp_path / "match_expr_call_inline.c"
    src.write_text(
        """
io :: import "std/io"

value :: fn() i32 {
    ret 1
}

main :: fn() {
    io.println("{}", match value() {
        case 1: 10
        else: 0
    })
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(["--backend", "c", "--output", str(out), str(src)])
    assert result.returncode == ExitCode.CODEGEN
    output = result.stdout + result.stderr
    assert "side-effectful scrutinees" in output
    assert "variable initializers" in output


@pytest.mark.skipif(not has_zig(), reason="zig not installed")
def test_generated_c_supports_slice_ptr_and_len_fields(tmp_path: Path) -> None:
    src = tmp_path / "slice_fields.a7"
    out = tmp_path / "slice_fields.c"
    bin_path = tmp_path / "slice_fields"
    src.write_text(
        """
io :: import "std/io"

main :: fn() {
    arr: [4]i32 = [10, 20, 30, 40]
    tail := arr[1..4]
    ptr := tail.ptr
    io.println("{} {}", tail.len, ptr.val)
}
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(["--backend", "c", "--output", str(out), str(src)])
    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr

    generated = out.read_text(encoding="utf-8")
    assert "(tail).len" in generated
    assert "(tail).data" in generated

    build = subprocess.run(
        ["zig", "cc", "-std=c11", str(out), "-lm", "-o", str(bin_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr

    run = subprocess.run(
        [str(bin_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.strip() == "3 20"


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
