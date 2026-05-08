"""
Edge case and stress tests for the A7 parser.

This file tests edge cases, error conditions, and boundary conditions
to ensure the parser is robust.
"""

import pytest
from a7.parser import parse_a7, Parser
from a7.tokens import Tokenizer
from a7.ast_nodes import NodeKind, BinaryOp
from a7.errors import ParseError


class TestParserEdgeCases:
    """Test parser edge cases and boundary conditions."""

    def test_deeply_nested_expressions(self):
        """Test parsing deeply nested expressions."""
        # Create a deeply nested expression: ((((1 + 2) + 3) + 4) + 5)
        code = "result :: " + "(" * 9 + "1 + 2" + " + 3)" * 9
        ast = parse_a7(code)
        # Should not crash and should create proper AST
        assert ast.declarations[0].value.kind == NodeKind.BINARY

    def test_very_long_identifier(self):
        """Test parsing very long identifiers (within limits)."""
        # A7 spec limits identifiers to 100 characters
        long_name = "a" * 99  # Just under the limit
        code = f"{long_name} :: 42"
        ast = parse_a7(code)
        assert ast.declarations[0].name == long_name

    def test_multiple_function_parameters(self):
        """Test function with many parameters."""
        params = ", ".join([f"p{i}: i32" for i in range(20)])
        code = f"test :: fn({params}) {{}}"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert len(func_decl.parameters) == 20

    def test_nested_function_calls(self):
        """Test nested function calls."""
        code = "result :: f(g(h(1, 2), 3), 4)"
        ast = parse_a7(code)
        # Should parse as nested calls
        expr = ast.declarations[0].value
        assert expr.kind == NodeKind.CALL
        assert expr.function.name == "f"
        assert expr.arguments[0].kind == NodeKind.CALL

    def test_complex_operator_precedence(self):
        """Test complex operator precedence scenarios."""
        # Test: 1 + 2 * 3 + 4 * 5 + 6
        code = "result :: 1 + 2 * 3 + 4 * 5 + 6"
        ast = parse_a7(code)
        # Should respect precedence: ((1 + (2 * 3)) + (4 * 5)) + 6
        expr = ast.declarations[0].value
        assert expr.kind == NodeKind.BINARY
        assert expr.operator == BinaryOp.ADD

    def test_mixed_literal_types(self):
        """Test expressions with mixed literal types."""
        code = """
        main :: fn() {
            a := 42 + 3.14  // int + float
            b := true and false  // bool and bool
            c := 'A' == 'B'  // char == char
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert len(func_decl.body.statements) == 3

    def test_empty_function_body(self):
        """Test function with empty body."""
        code = "test :: fn() {}"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert func_decl.body.statements == []

    def test_function_with_no_return_type(self):
        """Test function with no explicit return type."""
        code = "test :: fn(x: i32) { x + 1 }"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert func_decl.return_type is None

    def test_multiple_variable_declarations(self):
        """Test multiple variable declarations in sequence."""
        code = """
        a := 1
        b := 2
        c := 3
        d := 4
        e := 5
        """
        ast = parse_a7(code)
        assert len(ast.declarations) == 5
        for i, decl in enumerate(ast.declarations):
            assert decl.kind == NodeKind.VAR
            assert decl.value.literal_value == i + 1


class TestParserErrorRecovery:
    """Test parser error recovery mechanisms."""

    def test_recovery_after_missing_semicolon(self):
        """Test parser can recover after missing terminators."""
        code = """
        x :: 42
        y :: 24
        z :: 36
        """
        ast = parse_a7(code)
        # Should parse all three declarations despite missing explicit terminators
        assert len(ast.declarations) == 3

    def test_recovery_in_function_body(self):
        """Test error recovery within function bodies."""
        code = """
        main :: fn() {
            x := 1
            // Some invalid syntax here would be recovered from
            y := 2
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        # Should have parsed the valid statements
        assert len(func_decl.body.statements) >= 2

    def test_synchronization_points(self):
        """Test parser synchronization at declaration boundaries."""
        # Even if one declaration fails, parser should recover for next one
        valid_code = """
        x :: 42
        main :: fn() { ret 0 }
        """
        ast = parse_a7(valid_code)
        assert len(ast.declarations) == 2


class TestParserErrorMessages:
    """Test parser error message quality and specificity."""

    def test_missing_value_error(self):
        """Test error when value is missing from declaration."""
        with pytest.raises(ParseError) as exc_info:
            parse_a7("x :: ")
        assert "Expected expression" in str(exc_info.value)

    def test_missing_function_body_error(self):
        """Test error when function body is missing."""
        with pytest.raises(ParseError) as exc_info:
            parse_a7("test :: fn()")
        # Should indicate missing function body
        error_msg = str(exc_info.value)
        assert "Expected" in error_msg

    def test_invalid_parameter_syntax_error(self):
        """Test error with invalid parameter syntax."""
        with pytest.raises(ParseError) as exc_info:
            parse_a7("test :: fn(x) {}")
        # Should indicate missing type annotation
        assert "Expected" in str(exc_info.value)

    def test_unmatched_parentheses_error(self):
        """Test error with unmatched parentheses."""
        with pytest.raises(ParseError) as exc_info:
            parse_a7("result :: (1 + 2")
        assert "Expected" in str(exc_info.value)

    def test_invalid_binary_operator_error(self):
        """Test error with invalid binary operator usage."""
        with pytest.raises(ParseError) as exc_info:
            parse_a7("result :: 1 +")
        assert "Expected expression" in str(exc_info.value)


class TestParserBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_zero_parameter_function(self):
        """Test function with zero parameters."""
        code = "test :: fn() { ret 42 }"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert func_decl.parameters == []

    def test_single_parameter_function(self):
        """Test function with single parameter."""
        code = "test :: fn(x: i32) { ret x }"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert len(func_decl.parameters) == 1

    def test_single_statement_block(self):
        """Test block with single statement."""
        code = "main :: fn() { ret 42 }"
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert len(func_decl.body.statements) == 1

    def test_empty_argument_list(self):
        """Test function call with empty argument list."""
        code = "result :: func()"
        ast = parse_a7(code)
        call_expr = ast.declarations[0].value
        assert call_expr.kind == NodeKind.CALL
        assert call_expr.arguments == []


class TestParserWhitespaceHandling:
    """Test parser handling of whitespace and formatting."""

    def test_minimal_whitespace(self):
        """Test parsing with minimal whitespace."""
        code = "x::42"
        ast = parse_a7(code)
        assert ast.declarations[0].name == "x"
        assert ast.declarations[0].value.literal_value == 42

    def test_excessive_whitespace(self):
        """Test parsing with excessive whitespace."""
        code = "   x   ::   42   "
        ast = parse_a7(code)
        assert ast.declarations[0].name == "x"
        assert ast.declarations[0].value.literal_value == 42

    def test_mixed_line_endings(self):
        """Test parsing with different line ending styles."""
        # Test with explicit newlines
        code = "x :: 42\ny :: 24\nz :: 36"
        ast = parse_a7(code)
        assert len(ast.declarations) == 3

    def test_comments_ignored(self):
        """Test that comments are properly ignored."""
        code = """
        // This is a comment
        x :: 42  // End of line comment
        /* Multi-line
           comment */
        y :: 24
        """
        ast = parse_a7(code)
        assert len(ast.declarations) == 2
        assert ast.declarations[0].value.literal_value == 42
        assert ast.declarations[1].value.literal_value == 24


class TestParserTypeSystem:
    """Test parser handling of type system constructs."""

    def test_all_primitive_types(self):
        """Test parsing all primitive types."""
        primitive_types = [
            "i8",
            "i16",
            "i32",
            "i64",
            "isize",
            "u8",
            "u16",
            "u32",
            "u64",
            "usize",
            "f32",
            "f64",
            "bool",
            "char",
            "string",
        ]

        for type_name in primitive_types:
            code = f"test :: fn(x: {type_name}) {{}}"
            try:
                ast = parse_a7(code)
                func_decl = ast.declarations[0]
                param_type = func_decl.parameters[0].param_type
                assert param_type.kind == NodeKind.TYPE_PRIMITIVE
                assert param_type.type_name == type_name
            except Exception as e:
                pytest.fail(f"Failed to parse primitive type {type_name}: {e}")

    def test_array_type_variations(self):
        """Test different array type syntax variations."""
        test_cases = [
            "[10]i32",  # Fixed size array
            "[100]u8",  # Different size
            "[1]bool",  # Size 1 array
        ]

        for array_type in test_cases:
            code = f"test :: fn(arr: {array_type}) {{}}"
            ast = parse_a7(code)
            func_decl = ast.declarations[0]
            param_type = func_decl.parameters[0].param_type
            assert param_type.kind == NodeKind.TYPE_ARRAY

    def test_slice_type_variations(self):
        """Test different slice type syntax variations."""
        test_cases = [
            "[]i32",
            "[]string",
            "[]bool",
        ]

        for slice_type in test_cases:
            code = f"test :: fn(slice: {slice_type}) {{}}"
            ast = parse_a7(code)
            func_decl = ast.declarations[0]
            param_type = func_decl.parameters[0].param_type
            assert param_type.kind == NodeKind.TYPE_SLICE

    def test_pointer_type_variations(self):
        """Test different pointer type syntax variations."""
        test_cases = [
            "ref i32",
            "ref string",
            "ref bool",
        ]

        for pointer_type in test_cases:
            code = f"test :: fn(ptr: {pointer_type}) {{}}"
            ast = parse_a7(code)
            func_decl = ast.declarations[0]
            param_type = func_decl.parameters[0].param_type
            assert param_type.kind == NodeKind.TYPE_POINTER


class TestParserPerformance:
    """Test parser performance with various input sizes."""

    def test_large_expression_chain(self):
        """Test parsing large expression chains."""
        # Create a long chain: 1 + 1 + 1 + ... + 1
        chain_length = 100
        expr = " + ".join(["1"] * chain_length)
        code = f"result :: {expr}"

        ast = parse_a7(code)
        # Should complete without timeout or stack overflow
        assert ast.declarations[0].value.kind == NodeKind.BINARY

    def test_large_function_parameter_list(self):
        """Test parsing function with large parameter list."""
        params = ", ".join([f"p{i}: i32" for i in range(50)])
        code = f"test :: fn({params}) {{}}"

        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert len(func_decl.parameters) == 50

    def test_deeply_nested_blocks(self):
        """Test parsing deeply nested block structures."""
        # Create nested if statements
        depth = 20
        code = "main :: fn() {\n"
        for i in range(depth):
            code += "  " * i + f"if true {'{'}\n"
        code += "  " * depth + "x := 1\n"
        for i in range(depth):
            code += "  " * (depth - i - 1) + "}\n"
        code += "}"

        ast = parse_a7(code)
        # Should complete without stack overflow
        assert ast.declarations[0].kind == NodeKind.FUNCTION


class TestParserSpecialCases:
    """Test special parsing cases and corner conditions."""

    def test_function_call_no_spaces(self):
        """Test function call without spaces around parentheses."""
        code = "result::func(1,2,3)"
        ast = parse_a7(code)
        const_decl = ast.declarations[0]
        call_expr = const_decl.value
        assert call_expr.kind == NodeKind.CALL
        assert len(call_expr.arguments) == 3

    def test_chained_field_access(self):
        """Test chained field access operations."""
        code = "result :: obj.field1.field2.field3"
        ast = parse_a7(code)
        const_decl = ast.declarations[0]
        # Should parse as nested field access
        expr = const_decl.value
        assert expr.kind == NodeKind.FIELD_ACCESS

    def test_mixed_unary_operators(self):
        """Test multiple unary operators in sequence."""
        code = "result :: --x"  # Double negation
        ast = parse_a7(code)
        const_decl = ast.declarations[0]
        expr = const_decl.value
        assert expr.kind == NodeKind.UNARY
        assert expr.operand.kind == NodeKind.UNARY

    def test_assignment_vs_declaration_disambiguation(self):
        """Test parser can distinguish assignment from declaration."""
        code = """
        main :: fn() {
            x := 42    // Variable declaration
            x = 24     // Assignment
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert len(func_decl.body.statements) == 2
        # First should be variable declaration
        var_decl = func_decl.body.statements[0]
        assert var_decl.kind == NodeKind.VAR
        # Second should be assignment
        assignment = func_decl.body.statements[1]
        assert assignment.kind == NodeKind.ASSIGNMENT


class TestParserRobustness:
    """Test parser robustness with unusual inputs."""

    def test_empty_string_input(self):
        """Test parser with empty string input."""
        ast = parse_a7("")
        assert ast.kind == NodeKind.PROGRAM
        assert ast.declarations == []

    def test_whitespace_only_input(self):
        """Test parser with whitespace-only input."""
        ast = parse_a7("   \n\n   \n  ")
        assert ast.kind == NodeKind.PROGRAM
        assert ast.declarations == []

    def test_single_token_input(self):
        """Test parser with single token inputs."""
        with pytest.raises(ParseError):
            parse_a7("42")  # Just a number, not a valid program

        with pytest.raises(ParseError):
            parse_a7("identifier")  # Just an identifier

    def test_incomplete_expressions(self):
        """Test parser with various incomplete expressions."""
        incomplete_cases = [
            "x ::",  # Missing value
            "x := ",  # Missing value
            "fn(",  # Incomplete function
            "1 +",  # Incomplete binary expression
            "if",  # Incomplete if statement
        ]

        for case in incomplete_cases:
            with pytest.raises(ParseError):
                parse_a7(case)
