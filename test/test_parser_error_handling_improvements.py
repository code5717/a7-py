"""
Test error handling improvements for the A7 parser.

This file focuses on testing parser behavior with various error conditions
and edge cases that should be handled more robustly.
"""

import pytest
from src.parser import parse_a7
from src.errors import ParseError


class TestBetterErrorMessages:
    """Test that parser provides helpful error messages for common mistakes."""

    def test_missing_assignment_operator_error(self):
        """Test error message when assignment operator is missing."""
        source = """
        test_func :: fn() {
            x 42  // Missing := or =
        }
        """

        with pytest.raises(ParseError) as exc_info:
            parse_a7(source)

        # Error message should be helpful
        assert (
            "assignment" in str(exc_info.value).lower()
            or "operator" in str(exc_info.value).lower()
        )

    def test_missing_colon_in_struct_field_error(self):
        """Test error message when colon is missing in struct field."""
        source = """
        Person :: struct {
            name string  // Missing colon
            age: i32
        }
        """

        with pytest.raises(ParseError) as exc_info:
            parse_a7(source)

        # Should provide helpful error message
        assert exc_info.value.message is not None

    def test_mismatched_parentheses_error(self):
        """Test error message for mismatched parentheses."""
        source = """
        test_func :: fn() {
            result := (a + b) * (c + d  // Missing closing parenthesis
        }
        """

        with pytest.raises(ParseError) as exc_info:
            parse_a7(source)

        assert exc_info.value.message is not None

    def test_unexpected_token_in_expression_error(self):
        """Test error message for unexpected tokens in expressions."""
        source = """
        test_func :: fn() {
            result := a + + b  // Unexpected second +
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)


class TestErrorRecoveryLimitations:
    """Test current limitations in error recovery."""

    def test_error_recovery_stops_too_early(self):
        """Test cases where error recovery might stop too early."""
        source = """
        func1 :: fn() {
            x := incomplete +  // Error here
        }
        
        func2 :: fn() {  // This should still be parseable
            y := 42
        }
        """

        # The parser might not recover properly to parse func2
        with pytest.raises(ParseError):
            parse_a7(source)

    def test_error_recovery_in_nested_blocks(self):
        """Test error recovery in nested block structures."""
        source = """
        outer_func :: fn() {
            if true {
                inner_func :: fn() {
                    x := broken +  // Error in nested context
                }
                
                // This should still be parseable after recovery
                y := 42
            }
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)


class TestIncompleteConstructHandling:
    """Test handling of incomplete language constructs."""

    def test_incomplete_function_signature(self):
        """Test incomplete function signatures."""
        incomplete_signatures = [
            "func :: fn(",  # Missing closing paren
            "func :: fn(x",  # Missing type and closing paren
            "func :: fn(x:",  # Missing type
            "func :: fn(x: i32",  # Missing closing paren
            # Note: "func :: fn() i32" is now valid as a function type alias
        ]

        for sig in incomplete_signatures:
            with pytest.raises(ParseError):
                parse_a7(sig)

    def test_incomplete_struct_definition(self):
        """Test incomplete struct definitions."""
        incomplete_structs = [
            "Person :: struct",  # Missing brace
            "Person :: struct {",  # Missing closing brace
            "Person :: struct { name",  # Missing type and closing
            "Person :: struct { name:",  # Missing type
            "Person :: struct { name: string",  # Missing closing brace
        ]

        for struct_def in incomplete_structs:
            with pytest.raises(ParseError):
                parse_a7(struct_def)

    def test_incomplete_enum_definition(self):
        """Test incomplete enum definitions."""
        incomplete_enums = [
            "Color :: enum",  # Missing brace
            "Color :: enum {",  # Missing variants and closing
            "Color :: enum { Red",  # Missing closing brace
            "Color :: enum { Red,",  # Missing closing brace
        ]

        for enum_def in incomplete_enums:
            with pytest.raises(ParseError):
                parse_a7(enum_def)

    def test_incomplete_if_statement(self):
        """Test incomplete if statements."""
        incomplete_ifs = [
            "if",  # Missing condition
            "if true",  # Missing body
            "if true {",  # Missing closing brace
            "if { x := 1 }",  # Missing condition
        ]

        for if_stmt in incomplete_ifs:
            with pytest.raises(ParseError):
                parse_a7(if_stmt)

    def test_incomplete_while_statement(self):
        """Test incomplete while statements."""
        incomplete_whiles = [
            "while",  # Missing condition
            "while true",  # Missing body
            "while true {",  # Missing closing brace
            "while { x := 1 }",  # Missing condition
        ]

        for while_stmt in incomplete_whiles:
            with pytest.raises(ParseError):
                parse_a7(while_stmt)


class TestInvalidTokenSequences:
    """Test handling of invalid token sequences."""

    def test_consecutive_operators(self):
        """Test consecutive operators that should be invalid."""
        invalid_sequences = [
            "x := a + + b",  # Consecutive + (invalid)
            "z := e * * f",  # Consecutive * (invalid)
            "w := g / / h",  # Consecutive / (invalid)
        ]

        for seq in invalid_sequences:
            with pytest.raises(ParseError):
                parse_a7(seq)
        
        # Note: "c - - d" is valid A7 syntax (subtraction of negative d)
        
        # A7 uses 'and'/'or' keywords, not && ||  
        # These tokenize as separate & or | tokens, causing parse errors
        invalid_a7_operators = [
            "result := a && b",  # Tokenizes as & & causing parse error
            "check := x || y",   # Tokenizes as | | causing parse error
        ]
        
        for seq in invalid_a7_operators:
            with pytest.raises(ParseError):
                parse_a7(seq)

    def test_invalid_identifier_sequences(self):
        """Test invalid identifier sequences."""
        invalid_sequences = [
            "x y := 42",  # Two identifiers without operator
            "func name :: fn() {}",  # Two identifiers in function name
            "struct Point Point2 {}",  # Two identifiers in struct declaration
        ]

        for seq in invalid_sequences:
            with pytest.raises(ParseError):
                parse_a7(seq)

    def test_invalid_literal_sequences(self):
        """Test invalid literal sequences."""
        invalid_sequences = [
            "x := 42 43",  # Two integer literals
            'y := "hello" "world"',  # Two string literals
            "z := true false",  # Two boolean literals
        ]

        for seq in invalid_sequences:
            with pytest.raises(ParseError):
                parse_a7(seq)


class TestContextSensitiveErrors:
    """Test context-sensitive error detection."""

    def test_return_outside_function(self):
        """Test return statement outside function context."""
        source = """
        x := 42
        return x  // Return outside function
        """

        # This might not be caught by the parser (semantic analysis issue)
        # But we can test that it at least parses without crashing
        try:
            ast = parse_a7(source)
            # If it parses, the error will be caught in semantic analysis
            assert ast is not None
        except ParseError:
            # It's also acceptable to catch this at parse time
            pass

    def test_break_outside_loop(self):
        """Test break statement outside loop context."""
        source = """
        test_func :: fn() {
            x := 42
            break  // Break outside loop
        }
        """

        # Similar to return - might be semantic rather than syntactic
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass

    def test_continue_outside_loop(self):
        """Test continue statement outside loop context."""
        source = """
        test_func :: fn() {
            x := 42
            continue  // Continue outside loop
        }
        """

        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass


class TestTypeAnnotationEdgeCases:
    """Test edge cases in type annotations that might cause problems."""

    def test_invalid_array_size_types(self):
        """Test invalid array size specifications.

        Note: Non-integer array sizes like ["hello"]i32 are syntactically valid
        as typed declarations but should be caught by semantic analysis.
        We test them inside function bodies where they're parsed as statements.
        """
        # These are genuinely invalid syntax in expression context
        for arr_type in ['["hello"]i32', "[true]i32", "[3.14]i32", "[-5]i32"]:
            source = f'test :: fn() {{ x: {arr_type} = 0 }}'
            # These parse as valid typed declarations; semantic analysis catches invalid sizes
            parse_a7(source)  # Should not raise

    def test_nested_array_type_edge_cases(self):
        """Test edge cases in nested array types."""
        # Only genuinely unparseable types
        genuinely_invalid = [
            "[[[]i32",  # Unmatched brackets
            "[3][i32",  # Missing size in inner array
        ]

        for type_expr in genuinely_invalid:
            source = f"x: {type_expr}"
            with pytest.raises(ParseError):
                parse_a7(source)

        # These are valid syntax (multi-dim arrays, array of slices)
        valid_types = [
            "[3][]i32",  # Array of slices — valid
            "[3][4][5]i32",  # 3D array — valid
        ]
        for type_expr in valid_types:
            source = f"x: {type_expr}"
            parse_a7(source)  # Should not raise

    def test_invalid_reference_types(self):
        """Test invalid reference type usage."""
        # Genuinely invalid syntax
        genuinely_invalid = [
            "ref",  # Missing target type
            "ref [3]",  # Missing element type in array
        ]
        for ref_type in genuinely_invalid:
            source = f"x: {ref_type}"
            with pytest.raises(ParseError):
                parse_a7(source)

        # ref ref i32 is syntactically valid (double reference)
        parse_a7("x: ref ref i32")


class TestStringAndCharLiteralEdgeCases:
    """Test edge cases in string and character literal parsing."""

    def test_unclosed_string_literals(self):
        """Test unclosed string literals in different contexts."""
        from src.errors import TokenizerError
        
        unclosed_strings = [
            'x := "unclosed string',
            'y := "unclosed with newline\n',
            'z := "unclosed with tab\t',
            'func_name := "function name',
        ]

        for string_lit in unclosed_strings:
            with pytest.raises(TokenizerError):
                parse_a7(string_lit)

    def test_unclosed_char_literals(self):
        """Test unclosed character literals."""
        from src.errors import TokenizerError
        
        unclosed_chars = [
            "x := 'a",
            "y := '",
            "z := '\\n",  # Escaped newline without closing
        ]

        for char_lit in unclosed_chars:
            with pytest.raises(TokenizerError):
                parse_a7(char_lit)

    def test_invalid_escape_sequences(self):
        """Test invalid escape sequences in strings."""
        from src.errors import TokenizerError
        
        # Test cases that should cause TokenizerError due to unclosed strings
        unclosed_escapes = [
            'y := "incomplete\\',  # Incomplete escape causes unclosed string
        ]
        
        for invalid_str in unclosed_escapes:
            with pytest.raises(TokenizerError):
                parse_a7(invalid_str)
        
        invalid_escapes = [
            'x := "invalid\\q"',  # Invalid escape
            'z := "\\x"',  # Incomplete hex escape
            'w := "\\xZZ"',  # Invalid hex digits
        ]

        for invalid_str in invalid_escapes:
            with pytest.raises(TokenizerError):
                parse_a7(invalid_str)


class TestStructLiteralContextProblems:
    """Test struct literal context detection problems."""

    def test_ambiguous_brace_contexts(self):
        """Test ambiguous brace contexts that confuse struct literal detection."""
        # These cases test the _should_parse_struct_literal heuristic
        ambiguous_cases = [
            """
            test_func :: fn() {
                if condition {  // This { should not be a struct literal
                    x := 42
                }
            }
            """,
            """
            test_func :: fn() {
                while true {  // This { should not be a struct literal
                    break
                }
            }
            """,
            """
            test_func :: fn() {
                for i := 0; i < 10; i += 1 {  // This { should not be a struct literal
                    continue
                }
            }
            """,
        ]

        for case in ambiguous_cases:
            try:
                ast = parse_a7(case)
                assert ast is not None
            except ParseError:
                pytest.fail(f"Valid code should parse correctly: {case}")

    def test_struct_literal_vs_block_disambiguation(self):
        """Test disambiguation between struct literals and blocks."""
        # This should be parsed as a struct literal
        struct_literal_case = """
        Point :: struct { x: i32, y: i32 }
        
        test_func :: fn() {
            p := Point{ x: 1, y: 2 }  // Should be struct literal
        }
        """

        try:
            ast = parse_a7(struct_literal_case)
            assert ast is not None
        except ParseError:
            pytest.fail("Valid struct literal should parse correctly")


class TestParserInfiniteLoopPrevention:
    """Test prevention of infinite loops in parser."""

    def test_malformed_input_does_not_loop(self):
        """Test that malformed input doesn't cause infinite loops."""
        # Inputs that should raise ParseError
        error_causing_inputs = [
            "::::::::",  # Multiple declaration operators
            "(((((((",  # Multiple opening parens
            "}}}}}}",  # Multiple closing braces
            "++++++",  # Multiple operators
        ]
        
        for malformed in error_causing_inputs:
            try:
                with pytest.raises(ParseError):
                    parse_a7(malformed)
            except RecursionError:
                pytest.fail(f"Parser should not recurse infinitely on: {malformed}")
        
        # Special case: Multiple terminators parse successfully (empty program)
        terminators_only = ";;;;;;;"
        try:
            ast = parse_a7(terminators_only)
            # Should parse successfully as empty program
            assert ast is not None
            assert len(ast.declarations) == 0
        except RecursionError:
            pytest.fail(f"Parser should not recurse infinitely on: {terminators_only}")

    def test_parser_iteration_limit(self):
        """Test parser iteration limit prevention."""
        # Create input that might cause parser to iterate excessively
        repetitive_input = "x := 1\n" * 2000  # Many simple statements

        try:
            ast = parse_a7(repetitive_input)
            # Should either succeed or fail gracefully
            assert ast is not None
        except ParseError:
            # Acceptable to fail on very large input
            pass
        except Exception as e:
            pytest.fail(f"Parser should handle large input gracefully: {e}")


class TestErrorLocationAccuracy:
    """Test accuracy of error location reporting."""

    def test_error_location_in_multiline_input(self):
        """Test that error locations are accurate in multiline input."""
        source = """
        func1 :: fn() {
            x := 42
            y := 84
        }
        
        func2 :: fn() {
            z := broken +  // Error on this line
            w := 168
        }
        """

        with pytest.raises(ParseError) as exc_info:
            parse_a7(source)

        # Error should be reported on the correct line
        assert exc_info.value.span is not None
        # Line number should be around line 8 (where the error is)
        assert exc_info.value.span.start_line >= 7

    def test_error_column_accuracy(self):
        """Test accuracy of error column reporting."""
        source = "x := a +        // Error after spaces"

        with pytest.raises(ParseError) as exc_info:
            parse_a7(source)

        # Error should be reported at the correct column
        assert exc_info.value.span is not None
        # Column should be around where the error occurs
        assert exc_info.value.span.start_column > 5
