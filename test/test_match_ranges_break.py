"""Pins for reversed match ranges and break/continue inside match cases.

Covers docs/research/language-needs/01-correctness-holes.md sections 4-5:
- Constant reversed ranges (`case 10..1`) are compile errors (exit 6).
- Dynamic (non-constant) empty ranges keep runtime empty-matches-nothing.
- Unlabeled break/continue in a match case body inside a loop targets that
  loop, in the switch lowering and in the if-chain lowering. The labeled form
  works too.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.errors import CompilerError
from conftest import expect_ok, run_both_profiles

ROOT = Path(__file__).resolve().parents[1]


def parse_program(source: str):
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def run_semantic_analysis(source: str):
    program = parse_program(source)

    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    if resolver.errors:
        raise resolver.errors[0]

    type_checker = TypeCheckingPass(symbols)
    node_types = type_checker.analyze(program, "<test>")
    if type_checker.errors:
        raise type_checker.errors[0]

    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<test>")
    if validator.errors:
        raise validator.errors[0]

    return symbols, node_types


def expect_success(source: str) -> bool:
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def expect_error(source: str, error_fragment: str | None = None) -> bool:
    try:
        run_semantic_analysis(source)
        return False
    except CompilerError as e:
        if error_fragment:
            return error_fragment.lower() in str(e).lower()
        return True


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def has_zig() -> bool:
    try:
        result = subprocess.run(
            ["zig", "version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def write_source(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


class TestReversedConstantRanges:
    def test_const_reversed_range_rejected(self):
        source = """
        main :: fn() {
            n: i32 = 5
            match n {
                case 10..1: x := 1
                else: x := 0
            }
        }
        """
        assert expect_error(source, "reversed")

    def test_const_reversed_range_exit_code_6(self, tmp_path: Path):
        src = write_source(tmp_path, "rev.a7", """
        main :: fn() {
            n: i32 = 5
            match n {
                case 10..1: x := 1
                else: x := 0
            }
        }
        """)
        proc = run_cli([str(src), "-o", str(tmp_path / "rev.zig")], ROOT)
        assert proc.returncode == 6, proc.stderr
        assert "reversed" in (proc.stdout + proc.stderr).lower()

    def test_constant_alias_reversed_range_rejected(self):
        source = """
        A :: 10
        B :: 1

        main :: fn() {
            n: i32 = 5
            match n {
                case A..B: x := 1
                else: x := 0
            }
        }
        """
        assert expect_error(source, "reversed")

    def test_char_reversed_range_rejected(self):
        source = """
        main :: fn() {
            c: char = 'm'
            match c {
                case 'z'..'a': x := 1
                else: x := 0
            }
        }
        """
        assert expect_error(source, "reversed")

    def test_reversed_range_in_match_expression_rejected(self):
        source = """
        main :: fn() i32 {
            n: i32 = 5
            ret match n {
                case 10..1: 1
                else: 0
            }
        }
        """
        assert expect_error(source, "reversed")

    def test_valid_range_still_compiles(self, tmp_path: Path):
        source = """
        main :: fn() {
            n: i32 = 5
            match n {
                case 1..10: x := 1
                else: x := 0
            }
        }
        """
        assert expect_success(source)
        src = write_source(tmp_path, "ok.a7", source)
        proc = run_cli([str(src), "-o", str(tmp_path / "ok.zig")], ROOT)
        assert proc.returncode == 0, proc.stderr

    def test_single_point_range_allowed(self):
        source = """
        main :: fn() {
            n: i32 = 5
            match n {
                case 5..5: x := 1
                else: x := 0
            }
        }
        """
        assert expect_success(source)


class TestDynamicEmptyRange:
    def test_dynamic_empty_range_matches_nothing(self, tmp_path: Path):
        source = """io :: import "std/io"

main :: fn() {
    lo: i32 = 10
    hi: i32 = 1
    n: i32 = 5
    hit := false
    match n {
        case lo..hi: hit = true
        case _: hit = false
    }
    if hit {
        io.println("matched")
    } else {
        io.println("empty")
    }
}
"""
        src = write_source(tmp_path, "dyn.a7", source)
        zig_out = tmp_path / "dyn.zig"
        proc = run_cli([str(src), "-o", str(zig_out)], ROOT)
        assert proc.returncode == 0, proc.stderr
        # Non-constant bounds lower through the if-chain, which keeps the
        # runtime rule: start > end matches nothing.
        assert ">= lo and " in zig_out.read_text(encoding="utf-8")

    @pytest.mark.skipif(not has_zig(), reason="zig not installed")
    @pytest.mark.zig
    def test_dynamic_empty_range_runtime(self, tmp_path: Path):
        source = """io :: import "std/io"

main :: fn() {
    lo: i32 = 10
    hi: i32 = 1
    n: i32 = 5
    hit := false
    match n {
        case lo..hi: hit = true
        case _: hit = false
    }
    if hit {
        io.println("matched")
    } else {
        io.println("empty")
    }
}
"""
        src = write_source(tmp_path, "dyn.a7", source)
        zig_out = tmp_path / "dyn.zig"
        proc = run_cli([str(src), "-o", str(zig_out)], ROOT)
        assert proc.returncode == 0, proc.stderr
        binary = tmp_path / "dyn_bin"
        build = subprocess.run(
            ["zig", "build-exe", str(zig_out), f"-femit-bin={binary}"],
            cwd=tmp_path, capture_output=True, text=True, timeout=120,
        )
        assert build.returncode == 0, build.stderr
        run = subprocess.run(
            [str(binary)], cwd=tmp_path, capture_output=True, text=True, timeout=30,
        )
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "empty"


def emitted_zig(tmp_path: Path, profile: str = "debug") -> str:
    return (tmp_path / f"main-{profile}.zig").read_text(encoding="utf-8")


# Which lowering a test exercises is asserted from the emitted Zig: a native
# `switch (` for constant integer arms, an if-chain when a case ends in `fall`.
SWITCH_BREAK = """io :: import "std/io"

main :: fn() {
    for i := 0; i < 5; i += 1 {
        match i {
            case 2: {
                break
            }
            else: {
                io.println("{}", i)
            }
        }
    }
    io.println("done")
}
"""

FALL_BREAK = """io :: import "std/io"

main :: fn() {
    for i := 0; i < 5; i += 1 {
        match i {
            case 1: {
                io.println("one")
                fall
            }
            case 2: {
                break
            }
            else: {
                io.println("{}", i)
            }
        }
    }
    io.println("done")
}
"""

SWITCH_CONTINUE = """io :: import "std/io"

main :: fn() {
    for i := 0; i < 5; i += 1 {
        match i {
            case 2: {
                continue
            }
            else: {
            }
        }
        io.println("{}", i)
    }
    io.println("done")
}
"""

FALL_CONTINUE = """io :: import "std/io"

main :: fn() {
    for i := 0; i < 5; i += 1 {
        match i {
            case 1: {
                io.println("one")
                fall
            }
            case 2: {
                continue
            }
            else: {
            }
        }
        io.println("{}", i)
    }
    io.println("done")
}
"""

WHILE_BREAK = """io :: import "std/io"

main :: fn() {
    i := 0
    while i < 10 {
        match i {
            case 3: break
            else: i += 1
        }
    }
    io.println("{}", i)
}
"""


class TestBreakInMatchCase:
    """An unlabeled break/continue in a match case targets the enclosing loop."""

    def test_break_in_switch_case_leaves_loop(self, tmp_path: Path, zig):
        assert run_both_profiles(SWITCH_BREAK, tmp_path, zig) == "0\n1\ndone\n"
        assert "switch (" in emitted_zig(tmp_path)

    def test_break_after_fall_leaves_loop(self, tmp_path: Path, zig):
        # i == 1 prints "one", falls into the break arm, and leaves the loop.
        assert run_both_profiles(FALL_BREAK, tmp_path, zig) == "0\none\ndone\n"
        assert "switch (" not in emitted_zig(tmp_path)

    def test_continue_in_switch_case_skips_iteration(self, tmp_path: Path, zig):
        assert run_both_profiles(SWITCH_CONTINUE, tmp_path, zig) == "0\n1\n3\n4\ndone\n"
        assert "switch (" in emitted_zig(tmp_path)

    def test_continue_after_fall_skips_iteration(self, tmp_path: Path, zig):
        # i == 1 prints "one", falls into the continue arm, and skips its print.
        assert run_both_profiles(FALL_CONTINUE, tmp_path, zig) == "0\none\n3\n4\ndone\n"
        assert "switch (" not in emitted_zig(tmp_path)

    def test_break_in_while_loop_match_leaves_loop(self, tmp_path: Path, zig):
        assert run_both_profiles(WHILE_BREAK, tmp_path, zig) == "3\n"

    def test_break_in_match_in_loop_passes_semantic_analysis(self, tmp_path: Path):
        expect_ok(SWITCH_BREAK, tmp_path)
        expect_ok(SWITCH_CONTINUE, tmp_path)

    def test_break_targeting_inner_loop_in_case_allowed(self):
        source = """
        main :: fn() {
            i := 0
            while i < 10 {
                match i {
                    case 0: {
                        j := 0
                        while j < 3 {
                            j += 1
                            break
                        }
                        i += 1
                    }
                    else: i += 1
                }
            }
        }
        """
        assert expect_success(source)

    def test_break_in_match_outside_loop_keeps_old_error(self):
        source = """
        main :: fn() {
            x := 1
            match x {
                case 1: break
                else: x := 2
            }
        }
        """
        assert expect_error(source, "outside loop")

    def test_labeled_break_compiles_and_targets_loop(self, tmp_path: Path):
        source = """
        main :: fn() {
            i := 0
            @outer while i < 10 {
                match i {
                    case 0, 1, 2: i += 1
                    else: break outer
                }
            }
        }
        """
        assert expect_success(source)
        src = write_source(tmp_path, "lbl.a7", source)
        zig_out = tmp_path / "lbl.zig"
        proc = run_cli([str(src), "-o", str(zig_out)], ROOT)
        assert proc.returncode == 0, proc.stderr
        assert "break :a7_loop_outer" in zig_out.read_text(encoding="utf-8")

    @pytest.mark.skipif(not has_zig(), reason="zig not installed")
    @pytest.mark.zig
    def test_labeled_break_exits_loop_at_runtime(self, tmp_path: Path):
        source = """io :: import "std/io"

main :: fn() {
    i := 0
    @outer while i < 10 {
        match i {
            case 0, 1, 2: i += 1
            else: break outer
        }
    }
    if i == 3 {
        io.println("broke-at-3")
    } else {
        io.println("wrong")
    }
}
"""
        src = write_source(tmp_path, "lbl.a7", source)
        zig_out = tmp_path / "lbl.zig"
        proc = run_cli([str(src), "-o", str(zig_out)], ROOT)
        assert proc.returncode == 0, proc.stderr
        binary = tmp_path / "lbl_bin"
        build = subprocess.run(
            ["zig", "build-exe", str(zig_out), f"-femit-bin={binary}"],
            cwd=tmp_path, capture_output=True, text=True, timeout=120,
        )
        assert build.returncode == 0, build.stderr
        run = subprocess.run(
            [str(binary)], cwd=tmp_path, capture_output=True, text=True, timeout=30,
        )
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "broke-at-3"
