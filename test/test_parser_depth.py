"""Parser nesting cap: valid-deep input compiles, over-deep input exits 5.

The recursive-descent parser counts nesting in its directly recursive
entries (statement, binary, unary, type, if-expression) and aborts with
ParseError past MAX_NESTING_DEPTH. These tests pin both sides: deep but
valid programs still compile, and over-deep programs fail at the parse
stage (exit 5) instead of crashing with RecursionError or hanging.
"""

import sys

import pytest

from a7.compile import A7Compiler, ExitCode
from a7.errors import ParseError
from a7.parser import Parser
from a7.tokens import Tokenizer
from conftest import low_recursion_limit


def compile_ok(source: str) -> bool:
    """Full-pipeline compile of a source string; True when it succeeds."""
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".a7")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        return A7Compiler().compile_file(path, path.replace(".a7", ".zig"))
    finally:
        if os.path.exists(path):
            os.unlink(path)
        zig_path = path.replace(".a7", ".zig")
        if os.path.exists(zig_path):
            os.unlink(zig_path)


def compile_detailed(source: str, tmp_path):
    """Detailed compile; returns the CompilationResult (never raises)."""
    path = tmp_path / "deep.a7"
    path.write_text(source, encoding="utf-8")
    try:
        return A7Compiler().compile_file_detailed(str(path))
    except RecursionError:
        pytest.fail("over-deep input escaped as RecursionError instead of exit 5")


def make_nested_blocks(depth: int) -> str:
    lines = ['io :: import "std/io"', "", "main :: fn() {"]
    lines += ["    {" for _ in range(depth)]
    lines.append('        io.println("deep")')
    lines += ["    }" for _ in range(depth)]
    lines.append("}")
    return "\n".join(lines) + "\n"


def make_nested_parens(depth: int) -> str:
    expr = "1"
    for _ in range(depth):
        expr = f"({expr} + 1)"
    return (
        'io :: import "std/io"\n\nmain :: fn() {\n'
        f"    x := {expr}\n"
        '    io.println("{}", x)\n}\n'
    )


OVER_DEEP = 500


def over_parens() -> str:
    return "main :: fn() {\n    x := " + "(" * OVER_DEEP + "1" + ")" * OVER_DEEP + "\n}\n"


def over_blocks() -> str:
    return "main :: fn() {\n" + "{\n" * OVER_DEEP + "x := 1\n" + "}\n" * OVER_DEEP + "}\n"


def over_unary() -> str:
    return "main :: fn() {\n    x := " + "-" * OVER_DEEP + "1\n}\n"


def over_refs() -> str:
    return "main :: fn() {\n    x := new " + "ref " * OVER_DEEP + "i32\n}\n"


def over_else_if() -> str:
    src = "main :: fn() {\n    x := if true { 1 }"
    for _ in range(300):
        src += " else if false { 1 }"
    return src + " else { 2 }\n}\n"


class TestValidDeepPasses:
    def test_40_nested_blocks_compile(self):
        assert compile_ok(make_nested_blocks(40)) is True

    def test_100_nested_parens_compile(self):
        assert compile_ok(make_nested_parens(100)) is True


class TestOverDeepExitsParse:
    @pytest.mark.parametrize(
        "source",
        [over_parens(), over_blocks(), over_unary(), over_refs(), over_else_if()],
        ids=["parens", "blocks", "unary", "ref-types", "else-if-chain"],
    )
    def test_over_deep_fails_at_parse_stage(self, tmp_path, source):
        result = compile_detailed(source, tmp_path)
        assert result.ok is False
        assert result.exit_code == ExitCode.PARSE == 5
        assert "codegen" not in result.stages
        assert result.failure is not None
        assert "nesting depth" in result.failure.message

    def test_over_deep_raises_parse_error_directly(self):
        tokens = Tokenizer(over_parens()).tokenize()
        with pytest.raises(ParseError, match="nesting depth"):
            Parser(tokens).parse()


class TestLowLimitShallow:
    """IterLimit-style: the cap adds no stack pressure on valid programs."""

    def setup_method(self):
        self.old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(low_recursion_limit())

    def teardown_method(self):
        sys.setrecursionlimit(self.old_limit)

    def test_hello_world_compiles(self):
        assert compile_ok('main :: fn() {\n}\n') is True

    def test_10_nested_blocks_compile(self):
        assert compile_ok(make_nested_blocks(10)) is True

    def test_10_nested_parens_compile(self):
        assert compile_ok(make_nested_parens(10)) is True
