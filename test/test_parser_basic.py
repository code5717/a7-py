"""
Basic parser tests for fundamental A7 language constructs.

This file tests the core parsing functionality that should work.
"""

import pytest
from src.parser import parse_a7, Parser
from src.tokens import Tokenizer
from src.ast_nodes import NodeKind, LiteralKind, BinaryOp, UnaryOp
from src.errors import ParseError


class TestBasicParsing:
    """Test basic parsing functionality."""

    def test_empty_program(self):
        """Test parsing an empty program."""
        ast = parse_a7("")
        assert ast.kind == NodeKind.PROGRAM
        assert ast.declarations == []

    def test_simple_constant_declaration(self):
        """Test parsing simple constant declarations."""
        ast = parse_a7("x :: 42")
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 1

        const_decl = ast.declarations[0]
        assert const_decl.kind == NodeKind.CONST
        assert const_decl.name == "x"
        assert const_decl.value.kind == NodeKind.LITERAL
        assert const_decl.value.literal_kind == LiteralKind.INTEGER
        assert const_decl.value.literal_value == 42

    def test_simple_variable_declaration(self):
        """Test parsing simple variable declarations."""
        ast = parse_a7("x := 42")
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 1

        var_decl = ast.declarations[0]
        assert var_decl.kind == NodeKind.VAR
        assert var_decl.name == "x"
        assert var_decl.value.kind == NodeKind.LITERAL
        assert var_decl.value.literal_kind == LiteralKind.INTEGER
        assert var_decl.value.literal_value == 42

    def test_function_declaration_no_params(self):
        """Test parsing function declaration without parameters."""
        code = """
        main :: fn() {
            ret 42
        }
        """
        ast = parse_a7(code)
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 1

        func_decl = ast.declarations[0]
        assert func_decl.kind == NodeKind.FUNCTION
        assert func_decl.name == "main"
        assert func_decl.parameters == []
        assert func_decl.return_type is None
        assert func_decl.body.kind == NodeKind.BLOCK


class TestLiterals:
    """Test parsing of literal values."""

    def test_integer_literals(self):
        """Test parsing various integer literal formats."""
        test_cases = [
            ("42", 42),
            ("0", 0),
            ("123456", 123456),
            ("0x2A", 42),  # Hexadecimal
            ("0b101010", 42),  # Binary
            ("0o52", 42),  # Octal
        ]

        for code, expected_value in test_cases:
            ast = parse_a7(f"x :: {code}")
            const_decl = ast.declarations[0]
            assert const_decl.value.literal_kind == LiteralKind.INTEGER
            assert const_decl.value.literal_value == expected_value

    def test_float_literals(self):
        """Test parsing float literals."""
        test_cases = [
            ("3.14", 3.14),
            ("0.5", 0.5),
            ("123.456", 123.456),
        ]

        for code, expected_value in test_cases:
            ast = parse_a7(f"x :: {code}")
            const_decl = ast.declarations[0]
            assert const_decl.value.literal_kind == LiteralKind.FLOAT
            assert const_decl.value.literal_value == expected_value

    def test_string_literals(self):
        """Test parsing string literals."""
        ast = parse_a7('x :: "hello world"')
        const_decl = ast.declarations[0]
        assert const_decl.value.literal_kind == LiteralKind.STRING
        assert const_decl.value.literal_value == "hello world"

    def test_string_literal_escapes_are_decoded(self):
        """Test parsing string literal escape sequences."""
        ast = parse_a7(r'x :: "line\nquote: \"A\"\x21"')
        const_decl = ast.declarations[0]
        assert const_decl.value.literal_kind == LiteralKind.STRING
        assert const_decl.value.literal_value == 'line\nquote: "A"!'

    def test_char_literals(self):
        """Test parsing character literals."""
        test_cases = [
            ("'a'", "a"),
            ("'Z'", "Z"),
            ("'\\n'", "\n"),
            ("'\\t'", "\t"),
            ("'\\x41'", "A"),
        ]

        for code, expected_value in test_cases:
            ast = parse_a7(f"x :: {code}")
            const_decl = ast.declarations[0]
            assert const_decl.value.literal_kind == LiteralKind.CHAR
            assert const_decl.value.literal_value == expected_value

    def test_boolean_literals(self):
        """Test parsing boolean literals."""
        ast = parse_a7("x :: true")
        const_decl = ast.declarations[0]
        assert const_decl.value.literal_kind == LiteralKind.BOOLEAN
        assert const_decl.value.literal_value is True

        ast = parse_a7("y :: false")
        const_decl = ast.declarations[0]
        assert const_decl.value.literal_kind == LiteralKind.BOOLEAN
        assert const_decl.value.literal_value is False

    def test_nil_literal(self):
        """Test parsing nil literal."""
        ast = parse_a7("x :: nil")
        const_decl = ast.declarations[0]
        assert const_decl.value.literal_kind == LiteralKind.NIL
        assert const_decl.value.literal_value is None


class TestExpressions:
    """Test parsing of expressions."""

    def test_binary_expressions(self):
        """Test parsing binary expressions with correct precedence."""
        # Test simple addition
        ast = parse_a7("result :: 1 + 2")
        const_decl = ast.declarations[0]
        expr = const_decl.value
        assert expr.kind == NodeKind.BINARY
        assert expr.operator == BinaryOp.ADD
        assert expr.left.literal_value == 1
        assert expr.right.literal_value == 2

        # Test precedence: multiplication before addition
        ast = parse_a7("result :: 1 + 2 * 3")
        const_decl = ast.declarations[0]
        expr = const_decl.value
        assert expr.kind == NodeKind.BINARY
        assert expr.operator == BinaryOp.ADD
        assert expr.left.literal_value == 1
        assert expr.right.kind == NodeKind.BINARY
        assert expr.right.operator == BinaryOp.MUL

    def test_unary_expressions(self):
        """Test parsing unary expressions."""
        ast = parse_a7("result :: -42")
        const_decl = ast.declarations[0]
        expr = const_decl.value
        assert expr.kind == NodeKind.UNARY
        assert expr.operator == UnaryOp.NEG
        assert expr.operand.literal_value == 42

    def test_parenthesized_expressions(self):
        """Test parsing parenthesized expressions."""
        ast = parse_a7("result :: (1 + 2) * 3")
        const_decl = ast.declarations[0]
        expr = const_decl.value
        assert expr.kind == NodeKind.BINARY
        assert expr.operator == BinaryOp.MUL
        assert expr.left.kind == NodeKind.BINARY
        assert expr.left.operator == BinaryOp.ADD
        assert expr.right.literal_value == 3

    def test_function_calls(self):
        """Test parsing function call expressions."""
        ast = parse_a7("result :: add(1, 2)")
        const_decl = ast.declarations[0]
        expr = const_decl.value
        assert expr.kind == NodeKind.CALL
        assert expr.function.kind == NodeKind.IDENTIFIER
        assert expr.function.name == "add"
        assert len(expr.arguments) == 2
        assert expr.arguments[0].literal_value == 1
        assert expr.arguments[1].literal_value == 2


class TestStatements:
    """Test parsing of statements."""

    def test_expression_statement(self):
        """Test parsing expression statements."""
        code = """
        main :: fn() {
            1 + 2
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        block = func_decl.body
        assert len(block.statements) == 1

        expr_stmt = block.statements[0]
        assert expr_stmt.kind == NodeKind.EXPRESSION_STMT
        assert expr_stmt.expression.kind == NodeKind.BINARY

    def test_return_statement(self):
        """Test parsing return statements."""
        code = """
        main :: fn() {
            ret 42
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        block = func_decl.body
        assert len(block.statements) == 1

        ret_stmt = block.statements[0]
        assert ret_stmt.kind == NodeKind.RETURN
        assert ret_stmt.value.literal_value == 42

    def test_if_statement(self):
        """Test parsing if statements."""
        code = """
        main :: fn() {
            if true {
                ret 1
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        block = func_decl.body
        assert len(block.statements) == 1

        if_stmt = block.statements[0]
        assert if_stmt.kind == NodeKind.IF_STMT
        assert if_stmt.condition.literal_value is True
        assert if_stmt.then_stmt.kind == NodeKind.BLOCK

    def test_while_statement(self):
        """Test parsing while statements."""
        code = """
        main :: fn() {
            while true {
                break
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        block = func_decl.body
        assert len(block.statements) == 1

        while_stmt = block.statements[0]
        assert while_stmt.kind == NodeKind.WHILE
        assert while_stmt.condition.literal_value is True
        assert while_stmt.body.kind == NodeKind.BLOCK


class TestTypes:
    """Test parsing of type expressions."""

    def test_primitive_types(self):
        """Test parsing primitive types."""
        code = "add :: fn(x: i32, y: i32) i32 { ret x + y }"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]

        # Check parameter types
        param1 = func_decl.parameters[0]
        assert param1.param_type.kind == NodeKind.TYPE_PRIMITIVE
        assert param1.param_type.type_name == "i32"

        # Check return type
        assert func_decl.return_type.kind == NodeKind.TYPE_PRIMITIVE
        assert func_decl.return_type.type_name == "i32"

    def test_array_types(self):
        """Test parsing array types."""
        code = "data :: fn(arr: [10]i32) {}"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        param = func_decl.parameters[0]

        assert param.param_type.kind == NodeKind.TYPE_ARRAY
        assert param.param_type.element_type.type_name == "i32"
        assert param.param_type.size.literal_value == 10

    def test_slice_types(self):
        """Test parsing slice types."""
        code = "data :: fn(arr: []i32) {}"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        param = func_decl.parameters[0]

        assert param.param_type.kind == NodeKind.TYPE_SLICE
        assert param.param_type.element_type.type_name == "i32"

    def test_pointer_types(self):
        """Test parsing pointer types."""
        code = "data :: fn(ptr: ref i32) {}"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        param = func_decl.parameters[0]

        assert param.param_type.kind == NodeKind.TYPE_POINTER
        assert param.param_type.target_type.type_name == "i32"


class TestImports:
    """Test parsing of import statements."""

    def test_simple_import(self):
        """Test parsing simple import statements."""
        ast = parse_a7('import "std/io"')
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 1

        import_decl = ast.declarations[0]
        assert import_decl.kind == NodeKind.IMPORT
        assert import_decl.module_path == "std/io"


class TestErrorHandling:
    """Test parser error handling."""

    def test_missing_semicolon_recovery(self):
        """Test parser recovery from missing terminators."""
        # Parser should be able to recover and continue parsing
        code = """
        x :: 42
        y :: 24
        main :: fn() { ret 0 }
        """
        ast = parse_a7(code)
        assert len(ast.declarations) == 3

    def test_invalid_token_error(self):
        """Test parser error on invalid syntax."""
        with pytest.raises(ParseError):
            parse_a7("x :: ")  # Missing value

    def test_unexpected_token_error(self):
        """Test parser error on unexpected tokens."""
        with pytest.raises(ParseError):
            parse_a7(":: 42")  # Missing identifier
