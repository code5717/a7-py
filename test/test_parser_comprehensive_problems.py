"""
Comprehensive tests for parser problems and edge cases.

This test file focuses on specific parser implementation issues identified
through code analysis, including error handling, incomplete parsing, and
missing language constructs.
"""

import pytest
from a7.parser import parse_a7
from a7.errors import ParseError
from a7.ast_nodes import NodeKind, LiteralKind


class TestIncompleteExpressionHandling:
    """Test parser handling of incomplete expressions that should raise errors."""

    def test_incomplete_binary_expression_right_operand(self):
        """Test incomplete binary expressions missing right operand."""
        incomplete_expressions = [
            "x := a +",
            "result := value *",
            "check := flag &&",
            "y := x -",
            "z := a /",
            "w := b %",
            "compare := x ==",
            "test := val !=",
            "check := a <",
            "verify := b >",
            "result := x <=",
            "final := y >=",
            "bits := a |",
            "mask := b &",
            "shifted := x <<",
            "reduced := y >>",
        ]

        for expr in incomplete_expressions:
            with pytest.raises(ParseError, match="Expected.*expression"):
                parse_a7(expr)

    def test_incomplete_unary_expression(self):
        """Test incomplete unary expressions."""
        incomplete_cases = [
            "x := -",
            "y := !",
            "z := ~",
            "w := &",
        ]

        for expr in incomplete_cases:
            with pytest.raises(ParseError):
                parse_a7(expr)

    def test_incomplete_parenthesized_expression(self):
        """Test incomplete parenthesized expressions."""
        incomplete_cases = [
            "x := (",
            "y := (a +",
            "z := (a + b",
            "w := ((nested",
        ]

        for expr in incomplete_cases:
            with pytest.raises(ParseError):
                parse_a7(expr)


class TestFunctionTypeParsingProblems:
    """Test function type parsing - NOW IMPLEMENTED."""

    def test_function_type_in_parameter(self):
        """Test function types as parameters."""
        source = """
        higher_order :: fn(callback: fn(i32) i32, value: i32) i32 {
            ret callback(value)
        }
        """

        # Function types are now implemented and should parse successfully
        ast = parse_a7(source)
        assert ast is not None

    def test_function_type_in_struct(self):
        """Test function types in struct fields."""
        source = """
        Handler :: struct {
            process: fn(string) bool
        }
        """

        # Function types are now implemented and should parse successfully
        ast = parse_a7(source)
        assert ast is not None

    def test_function_type_return_type(self):
        """Test function type as return type."""
        source = """
        get_processor :: fn() fn(i32) string {
            ret nil
        }
        """

        # Function types are now implemented and should parse successfully
        ast = parse_a7(source)
        assert ast is not None


class TestBraceMatchingProblems:
    """Test detection of unmatched braces in complex structures."""

    def test_unmatched_function_brace(self):
        """Test unmatched brace in function definition."""
        source = """
        broken_func :: fn() {
            x := 42
            if x > 0 {
                return x
            }
        // Missing closing brace for function
        """

        with pytest.raises(ParseError):
            parse_a7(source)

    def test_unmatched_if_brace(self):
        """Test unmatched brace in if statement."""
        source = """
        test_func :: fn() {
            if true {
                x := 1
            // Missing closing brace for if
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)

    def test_extra_closing_brace(self):
        """Test extra closing braces are detected as errors."""
        source = """
        test_func :: fn() {
            x := 42
        }
        }  // Extra closing brace
        """

        # Parser should detect and report extra closing braces as errors
        with pytest.raises(ParseError):
            parse_a7(source)

    def test_mismatched_brace_types(self):
        """Test mismatched brace types (e.g., [} instead of ])."""
        source = """
        test_func :: fn() {
            arr := [1, 2, 3}  // Wrong closing brace
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)


class TestForLoopLimitationsAndRangeBasedLoops:
    """Test for loop parsing behavior and edge cases."""

    def test_range_based_for_loop_simple(self):
        """Test simple range-based for-in loop over iterables."""
        source = """
        test_func :: fn() {
            arr := [1, 2, 3, 4, 5]
            for value in arr {
                print(value)
            }
        }
        """

        # Range-based for loops are now supported!
        ast = parse_a7(source)
        assert ast is not None
        
        # Check that we have a function with a FOR_IN loop
        func = ast.declarations[0]
        assert func.kind == NodeKind.FUNCTION
        for_loop = func.body.statements[1]  # Second statement after variable declaration
        assert for_loop.kind == NodeKind.FOR_IN

    def test_indexed_for_loop(self):
        """Test indexed for loop (now supported)."""
        source = """
        test_func :: fn() {
            arr := [1, 2, 3, 4, 5]
            for i, value in arr {
                print(i, value)
            }
        }
        """

        # Indexed for loops are now supported!
        ast = parse_a7(source)
        assert ast is not None
        
        # Check that we have a function with a FOR_IN_INDEXED loop
        func = ast.declarations[0]
        assert func.kind == NodeKind.FUNCTION
        for_loop = func.body.statements[1]  # Second statement after variable declaration
        assert for_loop.kind == NodeKind.FOR_IN_INDEXED

    def test_range_for_loop(self):
        """Test range-based for loop with range syntax (not yet supported)."""
        source = """
        test_func :: fn() {
            for i in 0..10 {
                print(i)
            }
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)


class TestImportAndFieldAccessProblems:
    """Test import declarations and field access on modules."""

    def test_import_with_field_access(self):
        """Test import followed by field access (now supported)."""
        source = """
        io :: import "std/io"
        
        main :: fn() {
            io.println("Hello, world!")
        }
        """

        # Import parsing and field access on imported modules now works
        ast = parse_a7(source)
        assert ast is not None

    def test_chained_field_access_on_import(self):
        """Test chained field access on imported modules (now supported)."""
        source = """
        std :: import "std"
        
        main :: fn() {
            std.io.println("Hello")
            std.math.sqrt(16.0)
        }
        """

        # Chained field access on imported modules now works
        ast = parse_a7(source)
        assert ast is not None


class TestMatchStatementPatternProblems:
    """Test match statement pattern parsing behavior."""

    def test_range_patterns_in_match(self):
        """Range patterns should parse into PATTERN_RANGE nodes."""
        source = """
        test_match :: fn(x: i32) {
            match x {
                case 1..5: {
                    print("Low")
                }
                case 6..10: {
                    print("High")
                }
            }
        }
        """

        ast = parse_a7(source)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[0]
        assert match_stmt.kind == NodeKind.MATCH
        assert len(match_stmt.cases) == 2
        first_pattern = match_stmt.cases[0].patterns[0]
        second_pattern = match_stmt.cases[1].patterns[0]
        assert first_pattern.kind == NodeKind.PATTERN_RANGE
        assert second_pattern.kind == NodeKind.PATTERN_RANGE
        assert first_pattern.start.kind == NodeKind.PATTERN_LITERAL
        assert first_pattern.end.kind == NodeKind.PATTERN_LITERAL
        assert second_pattern.start.kind == NodeKind.PATTERN_LITERAL
        assert second_pattern.end.kind == NodeKind.PATTERN_LITERAL

    def test_multiple_values_in_case(self):
        """Multiple comma-separated patterns should parse per case."""
        source = """
        test_match :: fn(x: i32) {
            match x {
                case 1, 2, 3: {
                    print("Small")
                }
                case 4, 5, 6: {
                    print("Medium")
                }
            }
        }
        """

        ast = parse_a7(source)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[0]
        assert match_stmt.kind == NodeKind.MATCH
        assert len(match_stmt.cases) == 2
        assert len(match_stmt.cases[0].patterns) == 3
        assert len(match_stmt.cases[1].patterns) == 3
        assert all(p.kind == NodeKind.PATTERN_LITERAL for p in match_stmt.cases[0].patterns)
        assert all(p.kind == NodeKind.PATTERN_LITERAL for p in match_stmt.cases[1].patterns)

    def test_fall_statement(self):
        """`fall` tokens should parse as FALL statements inside match case blocks."""
        source = """
        test_match :: fn(x: i32) {
            match x {
                case 1: {
                    print("One")
                    fall
                }
                case 2: {
                    print("Two")
                }
            }
        }
        """

        ast = parse_a7(source)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[0]
        first_case_body = match_stmt.cases[0].statement
        assert first_case_body.kind == NodeKind.BLOCK
        assert len(first_case_body.statements) == 2
        assert first_case_body.statements[1].kind == NodeKind.FALL

    def test_boolean_literal_patterns(self):
        """Boolean literals in case patterns should parse as literal patterns."""
        source = """
        test_match :: fn(flag: bool) {
            match flag {
                case true: {
                    print("T")
                }
                case false: {
                    print("F")
                }
            }
        }
        """
        ast = parse_a7(source)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[0]
        first = match_stmt.cases[0].patterns[0]
        second = match_stmt.cases[1].patterns[0]
        assert first.kind == NodeKind.PATTERN_LITERAL
        assert second.kind == NodeKind.PATTERN_LITERAL
        assert first.literal.literal_kind == LiteralKind.BOOLEAN
        assert second.literal.literal_kind == LiteralKind.BOOLEAN

    def test_nil_literal_pattern(self):
        """Nil literals in case patterns should parse as literal patterns."""
        source = """
        test_match :: fn(ptr: ref i32) {
            match ptr {
                case nil: {
                    print("nil")
                }
                else: {
                    print("value")
                }
            }
        }
        """
        ast = parse_a7(source)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[0]
        nil_pattern = match_stmt.cases[0].patterns[0]
        assert nil_pattern.kind == NodeKind.PATTERN_LITERAL
        assert nil_pattern.literal.literal_kind == LiteralKind.NIL


class TestEnumAccessPatternProblems:
    """Test enum access parsing behavior."""

    def test_scoped_enum_access(self):
        """Scoped enum access should parse as field access expressions."""
        source = """
        Color :: enum {
            Red,
            Green,
            Blue
        }
        
        test_func :: fn() {
            c := Color.Red
        }
        """

        ast = parse_a7(source)
        func_decl = ast.declarations[1]
        var_decl = func_decl.body.statements[0]
        expr = var_decl.value
        assert expr.kind == NodeKind.FIELD_ACCESS
        assert expr.object.kind == NodeKind.IDENTIFIER
        assert expr.object.name == "Color"
        assert expr.field == "Red"

    def test_enum_with_explicit_values_access(self):
        """Enum access with explicit values and cast expressions should parse."""
        source = """
        Status :: enum {
            Ok = 200,
            NotFound = 404,
            Error = 500
        }
        
        test_func :: fn() {
            s := Status.Ok
            code := cast(i32, s)
        }
        """

        ast = parse_a7(source)
        func_decl = ast.declarations[1]
        first_var = func_decl.body.statements[0]
        second_var = func_decl.body.statements[1]
        assert first_var.value.kind == NodeKind.FIELD_ACCESS
        assert second_var.value.kind == NodeKind.CAST


class TestMemoryManagementSyntaxProblems:
    """Test memory management syntax parsing behavior."""

    def test_new_expression(self):
        """Test new expressions for allocation (now implemented)."""
        source = """
        test_func :: fn() {
            ptr := new i32
            ptr.val = 42
        }
        """

        # Should parse successfully now
        ast = parse_a7(source)
        assert ast is not None

    def test_new_with_value(self):
        """Reject initializer-like arguments after new expressions."""
        source = """
        test_func :: fn() {
            ptr := new i32(42)
        }
        """

        with pytest.raises(ParseError, match="new expressions do not take initializer"):
            parse_a7(source)

    def test_parenthesized_new_type(self):
        """Parenthesized type spelling remains valid for allocation."""
        source = """
        test_func :: fn() {
            ptr := new(i32)
        }
        """

        ast = parse_a7(source)
        assert ast is not None

    def test_del_statement(self):
        """Test del statements for deallocation (now implemented)."""
        source = """
        test_func :: fn() {
            ptr := new i32
            ptr.val = 42
            del ptr
        }
        """

        # Should parse successfully now (changed to use valid syntax)
        ast = parse_a7(source)
        assert ast is not None

    def test_pointer_dereference_syntax(self):
        """Test pointer dereference syntax ptr.val (now implemented)."""
        source = """
        test_func :: fn(ptr: ref i32) {
            value := ptr.val
        }
        """

        # This should now work with the new syntax
        ast = parse_a7(source)
        assert ast is not None


class TestStructLiteralComplexPatterns:
    """Test complex struct literal patterns."""

    def test_anonymous_struct_initialization(self):
        """Test anonymous struct initialization (now supported)."""
        source = """
        Token :: struct {
            type: i32,
            values: [3]i32
        }
        
        test_func :: fn() {
            t := Token{1, [10, 20, 30]}
        }
        """

        # Anonymous (positional) initialization is now supported by parser
        ast = parse_a7(source)
        assert ast is not None

    def test_nested_struct_initialization(self):
        """Test nested struct initialization (now supported)."""
        source = """
        Point :: struct {
            x: i32,
            y: i32
        }
        
        Line :: struct {
            start: Point,
            end: Point
        }
        
        test_func :: fn() {
            line := Line{
                start: Point{x: 0, y: 0},
                end: Point{x: 10, y: 10}
            }
        }
        """

        # Nested struct initialization is now supported by parser
        ast = parse_a7(source)
        assert ast is not None

    def test_array_field_in_struct_literal(self):
        """Test array fields in struct literals (now supported)."""
        source = """
        ArrayStruct :: struct {
            name: string,
            values: [3]i32
        }
        
        test_func :: fn() {
            arr_struct := ArrayStruct{
                name: "test",
                values: [1, 2, 3]
            }
        }
        """

        # Array initialization in struct literals is now supported by parser
        ast = parse_a7(source)
        assert ast is not None


class TestExplicitTypeAnnotationProblems:
    """Test explicit type annotation problems."""

    def test_explicit_type_variable_declaration(self):
        """Explicit type annotations use `=`, not `:=`."""
        source = """
        test_func :: fn() {
            x: i32 := 42
            y: string := "hello"
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)

    def test_array_literal_with_explicit_type(self):
        """Reject typed array-constructor syntax that is not current A7 syntax."""
        source = """
        test_func :: fn() {
            arr := [3]i32{10, 20, 30}
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)

    def test_cast_expression(self):
        """Test cast expressions are now implemented."""
        source = """
        test_func :: fn() {
            x := 42
            y := cast(f32, x)
        }
        """

        # Cast expressions are now implemented and should parse successfully
        result = parse_a7(source)
        assert result is not None
        assert result.kind == NodeKind.PROGRAM


class TestOperatorPrecedenceEdgeCases:
    """Test edge cases in operator precedence that might cause problems."""

    def test_complex_precedence_with_grouping(self):
        """Test complex operator precedence with grouping."""
        source = """
        test_func :: fn() {
            result := a + b * c - d / e % f
            grouped := (a + b) * (c - d) / (e % f)
            mixed := a and b or c and d
            bitwise := a | b & c ^ d << e >> f
        }
        """

        # This should parse successfully if precedence is implemented correctly
        ast = parse_a7(source)
        assert ast is not None

    def test_precedence_with_unary_operators(self):
        """Test precedence with unary operators."""
        source = """
        test_func :: fn() {
            result := -a + b
            negated := -(a + b)
            logical := !flag and other
            bitwise := ~mask | value
        }
        """

        # Unary operator precedence should work correctly
        ast = parse_a7(source)
        assert ast is not None


class TestErrorRecoveryProblems:
    """Test error recovery mechanisms in complex nested structures."""

    def test_error_in_deeply_nested_context(self):
        """Test error detection in deeply nested structures."""
        source = """
        complex_func :: fn() {
            for i := 0; i < 10; i += 1 {
                if i % 2 == 0 {
                    match i {
                        case 0: {
                            while true {
                                broken syntax here  // Invalid syntax
                            }
                        }
                    }
                }
            }
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)

    def test_multiple_errors_in_sequence(self):
        """Test multiple errors and recovery."""
        source = """
        func1 :: fn() {
            x := +  // Error 1: incomplete expression
        }
        
        func2 :: fn() {
            if true  // Error 2: missing brace
                y := 42
        }
        """

        with pytest.raises(ParseError):
            parse_a7(source)


class TestParserStateStressCases:
    """Test parser state stress cases."""

    def test_very_deep_nesting(self):
        """Test very deep nesting to check parser limits."""
        # Create deeply nested expressions
        nesting_levels = 100
        source = (
            "test_func :: fn() {\n    x := "
            + "(" * nesting_levels
            + "42"
            + ")" * nesting_levels
            + "\n}"
        )

        ast = parse_a7(source)
        assert ast is not None

    def test_very_long_expression(self):
        """Test very long expressions."""
        # Create a long chain of additions
        terms = ["x{}".format(i) for i in range(100)]
        expression = " + ".join(terms)
        source = f"test_func :: fn() {{\n    result := {expression}\n}}"

        ast = parse_a7(source)
        assert ast is not None
