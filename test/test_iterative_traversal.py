"""
Tests verifying the compiler pipeline works without deep recursion.

The A7 compiler uses iterative (stack-based) traversal in its semantic
analysis passes and AST preprocessor. These tests confirm that deeply
nested and large programs compile without hitting Python's recursion
limit, validating that the iterative implementations are correct.

Two categories of tests:
1. Low recursion limit tests -- set sys.setrecursionlimit(100) and
   compile programs that would blow the stack if any pass were recursive.
2. Deep nesting stress tests -- with the default recursion limit, create
   programs with extreme nesting depths (20-30+ levels) and verify
   they compile through the full pipeline.
"""

import os
import json
import sys
import tempfile

import pytest

from a7.ast_nodes import ASTNode, BinaryOp, LiteralKind, NodeKind
from a7.backends.zig import ZigCodeGenerator
from a7.compile import A7Compiler, OutputFormat
from a7.formatters import JSONFormatter


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def compile_source(source: str) -> bool:
    """Compile an A7 source string through the full pipeline.

    Returns True if compilation succeeded (all passes + codegen).
    Cleans up temporary files afterwards.
    """
    fd, path = tempfile.mkstemp(suffix=".a7")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        compiler = A7Compiler()
        return compiler.compile_file(path, path.replace(".a7", ".zig"))
    finally:
        if os.path.exists(path):
            os.unlink(path)
        zig_path = path.replace(".a7", ".zig")
        if os.path.exists(zig_path):
            os.unlink(zig_path)


def parse_only_source(source: str) -> bool:
    """Parse an A7 source string (tokenize + parse only, no semantic passes).

    Returns True if parsing succeeded.
    """
    fd, path = tempfile.mkstemp(suffix=".a7")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        compiler = A7Compiler(mode="ast")
        return compiler.compile_file(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ---------------------------------------------------------------------------
# Generators for deeply nested A7 programs
# ---------------------------------------------------------------------------

def make_nested_ifs(depth: int) -> str:
    """Generate a program with `depth` levels of nested if/else statements."""
    lines = [
        'io :: import "std/io"',
        "",
        "main :: fn() {",
    ]
    for i in range(depth):
        indent = "    " * (i + 1)
        lines.append(f"{indent}if true {{")
    # innermost body
    inner_indent = "    " * (depth + 1)
    lines.append(f"{inner_indent}io.println(\"deep\")")
    for i in range(depth - 1, -1, -1):
        indent = "    " * (i + 1)
        lines.append(f"{indent}}} else {{")
        lines.append(f"{indent}    io.println(\"else\")")
        lines.append(f"{indent}}}")
    lines.append("}")
    return "\n".join(lines)


def make_nested_whiles(depth: int) -> str:
    """Generate a program with `depth` levels of nested while loops."""
    lines = [
        'io :: import "std/io"',
        "",
        "main :: fn() {",
    ]
    for i in range(depth):
        indent = "    " * (i + 1)
        lines.append(f"{indent}while false {{")
    inner_indent = "    " * (depth + 1)
    lines.append(f"{inner_indent}io.println(\"inner\")")
    for i in range(depth - 1, -1, -1):
        indent = "    " * (i + 1)
        lines.append(f"{indent}}}")
    lines.append("}")
    return "\n".join(lines)


def make_nested_blocks(depth: int) -> str:
    """Generate a program with `depth` levels of nested blocks."""
    lines = [
        'io :: import "std/io"',
        "",
        "main :: fn() {",
    ]
    for i in range(depth):
        indent = "    " * (i + 1)
        lines.append(f"{indent}{{")
    inner_indent = "    " * (depth + 1)
    lines.append(f"{inner_indent}io.println(\"deep block\")")
    for i in range(depth - 1, -1, -1):
        indent = "    " * (i + 1)
        lines.append(f"{indent}}}")
    lines.append("}")
    return "\n".join(lines)


def make_nested_expressions(depth: int) -> str:
    """Generate a program with a deeply nested binary expression.

    Produces: ((((1 + 2) + 3) + 4) + ... + depth)
    """
    expr = "1"
    for i in range(2, depth + 2):
        expr = f"({expr} + {i})"
    return (
        'io :: import "std/io"\n'
        "\n"
        "main :: fn() {\n"
        f"    x := {expr}\n"
        "    io.println(\"{}\", x)\n"
        "}\n"
    )


def make_deep_binary_ast(depth: int) -> ASTNode:
    """Build a synthetic binary-expression AST without going through parser."""
    node = ASTNode(NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=1)
    for i in range(2, depth + 2):
        node = ASTNode(
            NodeKind.BINARY,
            left=node,
            operator=BinaryOp.ADD,
            right=ASTNode(NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=i),
        )
    return node


def make_many_statements(count: int) -> str:
    """Generate a function with `count` sequential statements."""
    lines = [
        'io :: import "std/io"',
        "",
        "main :: fn() {",
    ]
    for i in range(count):
        lines.append(f'    io.println("stmt {i}")')
    lines.append("}")
    return "\n".join(lines)


def make_many_functions(count: int) -> str:
    """Generate a program with `count` function declarations."""
    lines = ['io :: import "std/io"', ""]
    for i in range(count):
        lines.append(f"func_{i} :: fn() {{")
        lines.append(f'    io.println("func {i}")')
        lines.append("}")
        lines.append("")
    # main calls the first few
    lines.append("main :: fn() {")
    for i in range(min(count, 5)):
        lines.append(f"    func_{i}()")
    lines.append("}")
    return "\n".join(lines)


def make_chained_calls(count: int) -> str:
    """Generate a program where functions call each other in a chain.

    func_0 calls func_1, func_1 calls func_2, ..., func_(count-1) is a leaf.
    """
    lines = ['io :: import "std/io"', ""]
    for i in range(count):
        lines.append(f"func_{i} :: fn() {{")
        if i < count - 1:
            lines.append(f"    func_{i + 1}()")
        else:
            lines.append(f'    io.println("end of chain")')
        lines.append("}")
        lines.append("")
    lines.append("main :: fn() {")
    lines.append("    func_0()")
    lines.append("}")
    return "\n".join(lines)


# ===========================================================================
# 1. Low Recursion Limit Tests
# ===========================================================================


class TestLowRecursionLimit:
    """Verify the compiler pipeline works with a very low Python recursion limit.

    A recursion limit of 100 is low enough to catch any pass that uses
    recursive traversal on even modestly nested inputs, yet high enough
    for Python's own import machinery and pytest internals to function.
    """

    def setup_method(self):
        self.old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(100)

    def teardown_method(self):
        sys.setrecursionlimit(self.old_limit)

    def test_hello_world_compiles(self):
        """A trivial hello-world program should compile at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "main :: fn() {\n"
            '    io.println("Hello, World!")\n'
            "}\n"
        )
        assert compile_source(source) is True

    def test_nested_ifs_10_levels(self):
        """10 levels of nested if/else should compile at limit=100."""
        source = make_nested_ifs(10)
        assert compile_source(source) is True

    def test_nested_blocks_10_levels(self):
        """10 levels of nested blocks should compile at limit=100."""
        source = make_nested_blocks(10)
        assert compile_source(source) is True

    def test_nested_expressions_10_levels(self):
        """10 levels of nested binary expressions should compile at limit=100."""
        source = make_nested_expressions(10)
        assert compile_source(source) is True

    def test_many_statements_50(self):
        """A function with 50 sequential statements should compile at limit=100."""
        source = make_many_statements(50)
        assert compile_source(source) is True

    def test_multiple_functions_calling_each_other(self):
        """Multiple functions that call each other should compile at limit=100."""
        source = make_chained_calls(10)
        assert compile_source(source) is True

    def test_variables_and_assignments(self):
        """Variable declarations and assignments should work at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "main :: fn() {\n"
            "    a := 1\n"
            "    b := 2\n"
            "    c := a + b\n"
            "    d := c * 2\n"
            "    e := d - a\n"
            "    io.println(\"{}\", e)\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_while_loop_with_break_continue(self):
        """While loop with break/continue should compile at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "main :: fn() {\n"
            "    i := 0\n"
            "    while i < 10 {\n"
            "        i += 1\n"
            "        if i == 3 {\n"
            "            continue\n"
            "        }\n"
            "        if i == 7 {\n"
            "            break\n"
            "        }\n"
            "        io.println(\"{}\", i)\n"
            "    }\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_function_with_return_value(self):
        """Function with return type and return statement at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "add :: fn(x: i32, y: i32) i32 {\n"
            "    ret x + y\n"
            "}\n"
            "\n"
            "main :: fn() {\n"
            "    result := add(3, 4)\n"
            "    io.println(\"{}\", result)\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_nested_whiles_5_levels(self):
        """5 levels of nested while loops should compile at limit=100."""
        source = make_nested_whiles(5)
        assert compile_source(source) is True

    def test_struct_declaration_and_init(self):
        """Struct declaration and initialization at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "Point :: struct {\n"
            "    x: i32,\n"
            "    y: i32,\n"
            "}\n"
            "\n"
            "main :: fn() {\n"
            "    p := Point { x: 10, y: 20 }\n"
            "    io.println(\"{}\", p.x)\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_enum_declaration(self):
        """Enum declaration at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "Color :: enum {\n"
            "    Red,\n"
            "    Green,\n"
            "    Blue,\n"
            "}\n"
            "\n"
            "main :: fn() {\n"
            "    c := Color.Red\n"
            "    io.println(\"color set\")\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_constant_declaration(self):
        """Constant declarations at limit=100."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "PI :: 3.14\n"
            "MAX :: 100\n"
            "\n"
            "main :: fn() {\n"
            "    io.println(\"{}\", PI)\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_json_ast_output_compiles_at_low_limit(self, tmp_path, capsys):
        """JSON AST output should not add recursive traversal pressure."""
        source = make_nested_blocks(10)
        path = tmp_path / "deep_json.a7"
        path.write_text(source, encoding="utf-8")

        compiler = A7Compiler(mode="ast", output_format=OutputFormat.JSON)
        result = compiler.compile_file_detailed(str(path))
        captured = capsys.readouterr()

        assert result.ok is True
        payload = json.loads(captured.out)
        assert payload["status"] == "ok"
        assert payload["stages"]["parse"]["ast"]["kind"] == "PROGRAM"

    def test_json_formatter_deep_ast_uses_iterative_stack(self):
        """Direct JSON AST formatting should handle deep AST chains."""
        root = ASTNode(NodeKind.PROGRAM, declarations=[])
        current = root

        for _ in range(160):
            child = ASTNode(NodeKind.BLOCK, statements=[])
            if current.kind == NodeKind.PROGRAM:
                current.declarations = [child]
            else:
                current.statements = [child]
            current = child

        payload = JSONFormatter().format_compilation([], root, "", "deep.a7")
        node = payload["ast"]["declarations"][0]
        depth = 1
        while node.get("statements"):
            node = node["statements"][0]
            depth += 1

        assert depth == 160

    def test_zig_backend_deep_binary_expression_uses_iterative_stack(self):
        """Zig expression emission should not recurse on deep binary chains."""
        expr = make_deep_binary_ast(160)
        rendered = ZigCodeGenerator()._emit_expr(expr)

        assert rendered.count("+") == 160

# ===========================================================================
# 2. Deep Nesting Stress Tests (normal recursion limit)
# ===========================================================================


class TestDeepNestingStress:
    """Stress tests with deeply nested structures at the normal recursion limit.

    These tests create programs with 20-30+ levels of nesting. If any pass
    used naive recursion, these would exceed the default limit of ~1000 only
    for extremely deep nesting; instead, these tests verify the iterative
    implementations handle realistic deep nesting gracefully.
    """

    def test_20_nested_ifs(self):
        """20 levels of nested if/else should compile successfully."""
        source = make_nested_ifs(20)
        assert compile_source(source) is True

    def test_25_nested_ifs(self):
        """25 levels of nested if/else should compile successfully."""
        source = make_nested_ifs(25)
        assert compile_source(source) is True

    def test_20_nested_whiles(self):
        """20 levels of nested while loops should compile successfully."""
        source = make_nested_whiles(20)
        assert compile_source(source) is True

    def test_25_nested_whiles(self):
        """25 levels of nested while loops should compile successfully."""
        source = make_nested_whiles(25)
        assert compile_source(source) is True

    def test_20_nested_blocks(self):
        """20 levels of nested blocks should compile successfully."""
        source = make_nested_blocks(20)
        assert compile_source(source) is True

    def test_30_nested_blocks(self):
        """30 levels of nested blocks should compile successfully."""
        source = make_nested_blocks(30)
        assert compile_source(source) is True

    def test_30_nested_expressions(self):
        """30 levels of nested binary expressions should compile."""
        source = make_nested_expressions(30)
        assert compile_source(source) is True

    def test_50_nested_expressions(self):
        """50 levels of nested binary expressions should compile."""
        source = make_nested_expressions(50)
        assert compile_source(source) is True

    def test_20_function_declarations(self):
        """Program with 20+ function declarations should compile."""
        source = make_many_functions(25)
        assert compile_source(source) is True

    def test_50_function_declarations(self):
        """Program with 50 function declarations should compile."""
        source = make_many_functions(50)
        assert compile_source(source) is True

    def test_100_statements(self):
        """A function with 100 sequential statements should compile."""
        source = make_many_statements(100)
        assert compile_source(source) is True

    def test_deep_if_else_chain(self):
        """A long if/else-if chain (flat, not nested) should compile."""
        lines = [
            'io :: import "std/io"',
            "",
            "main :: fn() {",
            "    x := 42",
        ]
        for i in range(25):
            keyword = "if" if i == 0 else "} else if"
            lines.append(f"    {keyword} x == {i} {{")
            lines.append(f'        io.println("x is {i}")')
        lines.append('    } else {')
        lines.append('        io.println("x is something else")')
        lines.append("    }")
        lines.append("}")
        source = "\n".join(lines)
        assert compile_source(source) is True

    def test_mixed_deep_nesting(self):
        """Mix of nested ifs, whiles, and blocks at 15+ levels total."""
        source = (
            'io :: import "std/io"\n'
            "\n"
            "main :: fn() {\n"
            "    if true {\n"
            "        while false {\n"
            "            {\n"
            "                if true {\n"
            "                    while false {\n"
            "                        {\n"
            "                            if true {\n"
            "                                while false {\n"
            "                                    {\n"
            "                                        if true {\n"
            "                                            while false {\n"
            "                                                {\n"
            "                                                    if true {\n"
            '                                                        io.println("deep")\n'
            "                                                    }\n"
            "                                                }\n"
            "                                            }\n"
            "                                        }\n"
            "                                    }\n"
            "                                }\n"
            "                            }\n"
            "                        }\n"
            "                    }\n"
            "                }\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_chained_function_calls_20(self):
        """20 functions forming a call chain should compile."""
        source = make_chained_calls(20)
        assert compile_source(source) is True

    def test_deeply_nested_arithmetic(self):
        """Deeply nested arithmetic with mixed operators should compile."""
        # Build: ((((1 + 2) * 3) - 4) + 5) ... alternating ops
        ops = ["+", "*", "-", "+"]
        expr = "1"
        for i in range(2, 32):
            op = ops[(i - 2) % len(ops)]
            expr = f"({expr} {op} {i})"
        source = (
            'io :: import "std/io"\n'
            "\n"
            "main :: fn() {\n"
            f"    x := {expr}\n"
            "    io.println(\"{}\", x)\n"
            "}\n"
        )
        assert compile_source(source) is True

    def test_many_variables_in_function(self):
        """Function with many variable declarations should compile."""
        lines = [
            'io :: import "std/io"',
            "",
            "main :: fn() {",
        ]
        for i in range(50):
            lines.append(f"    var_{i} := {i}")
        # Use the last variable to prevent unused-var issues
        lines.append("    io.println(\"{}\", var_49)")
        lines.append("}")
        source = "\n".join(lines)
        assert compile_source(source) is True

    def test_nested_ifs_with_expressions(self):
        """Nested ifs where each condition is a compound expression."""
        lines = [
            'io :: import "std/io"',
            "",
            "main :: fn() {",
            "    x := 10",
            "    y := 20",
        ]
        for i in range(20):
            indent = "    " * (i + 1)
            lines.append(f"{indent}if (x + {i}) > 0 and (y - {i}) > 0 {{")
        inner = "    " * 21
        lines.append(f'{inner}io.println("all conditions met")')
        for i in range(19, -1, -1):
            indent = "    " * (i + 1)
            lines.append(f"{indent}}}")
        lines.append("}")
        source = "\n".join(lines)
        assert compile_source(source) is True


# ===========================================================================
# 3. AST-Mode Deep Nesting Tests
# ===========================================================================


class TestParseOnlyDeepNesting:
    """Verify the parser itself handles deep nesting without stack overflow.

    These tests use AST mode to isolate parser behavior from
    semantic analysis.
    """

    def test_parse_40_nested_blocks(self):
        """Parser should handle 40 levels of nested blocks."""
        source = make_nested_blocks(40)
        assert parse_only_source(source) is True

    def test_parse_40_nested_ifs(self):
        """Parser should handle 40 levels of nested if statements."""
        source = make_nested_ifs(40)
        assert parse_only_source(source) is True

    def test_parse_100_nested_expressions(self):
        """Parser should handle 100 levels of nested expressions."""
        source = make_nested_expressions(100)
        assert parse_only_source(source) is True

    def test_parse_deeply_nested_parenthesized_expressions(self):
        """Parser should handle deeply nested parenthesized expressions."""
        # Build 50 levels of parenthesized additions: (((((1 + 1) + 1) ...)))
        expr = "1"
        for _ in range(50):
            expr = f"({expr} + 1)"
        source = (
            'io :: import "std/io"\n'
            "\n"
            "main :: fn() {\n"
            f"    x := {expr}\n"
            "}\n"
        )
        assert parse_only_source(source) is True


# ===========================================================================
# 4. Low Recursion Limit with Deep Nesting (combined)
# ===========================================================================


class TestLowLimitDeepNesting:
    """The most demanding tests: low recursion limit AND deep nesting.

    The A7 parser uses recursive descent, so it needs some stack depth
    per nesting level. The semantic analysis passes (name resolution,
    type checking, semantic validation) and the AST preprocessor are
    fully iterative, so they add zero stack depth regardless of nesting.

    We use a recursion limit of 150 which is low enough that any
    recursive semantic pass would blow up on 20+ levels of nesting,
    but gives the recursive-descent parser enough headroom. The pytest
    framework itself consumes ~30-40 stack frames before the test body
    runs, further tightening the budget.
    """

    LIMIT = 150

    def setup_method(self):
        self.old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(self.LIMIT)

    def teardown_method(self):
        sys.setrecursionlimit(self.old_limit)

    def test_nested_ifs_at_low_limit(self):
        """Nested ifs should work at a low recursion limit.

        At limit 150, the parser can handle this nesting depth. If the
        semantic passes were recursive, they would blow up since each
        pass would add another full traversal on top of the parser.
        """
        source = make_nested_ifs(10)
        assert compile_source(source) is True

    def test_nested_blocks_at_low_limit(self):
        """Nested blocks at a low recursion limit."""
        source = make_nested_blocks(15)
        assert compile_source(source) is True

    def test_nested_whiles_at_low_limit(self):
        """Nested while loops at a low recursion limit."""
        source = make_nested_whiles(10)
        assert compile_source(source) is True

    def test_nested_expressions_at_low_limit(self):
        """Nested expressions at a low recursion limit."""
        source = make_nested_expressions(15)
        assert compile_source(source) is True

    def test_many_functions_at_low_limit(self):
        """Many function declarations should compile at a low recursion limit."""
        source = make_many_functions(30)
        assert compile_source(source) is True

    def test_many_statements_at_low_limit(self):
        """Many sequential statements at a low recursion limit.

        Sequential statements do not increase nesting, so the iterative
        passes handle them at any count. The parser processes them in a
        loop as well.
        """
        source = make_many_statements(80)
        assert compile_source(source) is True

    def test_parse_only_nested_blocks_at_low_limit(self):
        """AST mode with nested blocks at a low recursion limit."""
        source = make_nested_blocks(20)
        assert parse_only_source(source) is True
