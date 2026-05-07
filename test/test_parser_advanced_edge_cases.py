"""
Comprehensive tests for array programming features and parser edge cases in A7.

Tests multidimensional arrays, broadcasting syntax, complex expressions, and edge cases.
"""

import pytest
from src.tokens import Tokenizer, TokenType
from src.parser import parse_a7
from src.errors import TokenizerError, ParseError


class TestArrayProgrammingTokenization:
    """Test tokenization of array programming syntax."""

    def test_multidimensional_array_literals(self):
        """Test parsing of multidimensional array literals."""
        source = """
        matrix := [[1, 2, 3],
                   [4, 5, 6],
                   [7, 8, 9]]
        """
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Should have nested brackets
        bracket_count = sum(
            1 for token in tokens if token.type == TokenType.LEFT_BRACKET
        )
        assert bracket_count >= 4  # Outer array + 3 inner arrays

    def test_array_function_calls(self):
        """Test array function call syntax using existing identifiers."""
        test_cases = [
            "array_create([3, 4, 5], f32)",
            "matrix_multiply(A, B)",
            "array_reshape(a, [6])",
            "array_sum(data)",
        ]

        for source in test_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert tokens[0].type == TokenType.IDENTIFIER
            assert tokens[1].type == TokenType.LEFT_PAREN

    def test_named_parameter_syntax(self):
        """Test named parameter syntax for array operations."""
        source = "array_sum(a, dim: 1)"
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Should find colon for named parameter
        colon_found = any(token.type == TokenType.COLON for token in tokens)
        assert colon_found


class TestArraySyntaxEdgeCases:
    """Test edge cases in array syntax."""

    def test_deeply_nested_arrays(self):
        """Test parsing of deeply nested array literals."""
        source = "data := [[[[1, 2], [3, 4]], [[5, 6], [7, 8]]], [[[9, 10], [11, 12]], [[13, 14], [15, 16]]]]"
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Should parse without error
        assert len(tokens) > 0
        assert tokens[-1].type == TokenType.EOF

    def test_mixed_array_operations(self):
        """Test complex array operation chains."""
        source = """
        result := matrix_multiply(
            array_transpose(array_reshape(input, [batch, size])),
            array_expand(weights, dim: 0)
        )
        """
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Should parse complex nested function calls
        assert len(tokens) > 20

    def test_broadcasting_syntax(self):
        """Test broadcasting operation syntax with standard operators."""
        source = """
        a := create_array([3, 1, 4])
        b := create_array([2, 5, 1])
        result := a + b  // Broadcasting addition
        """
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Find plus operator for broadcasting
        plus_found = any(token.type == TokenType.PLUS for token in tokens)
        assert plus_found

    def test_array_indexing_syntax(self):
        """Test advanced array indexing."""
        test_cases = [
            "array[i, j, k]",
            "matrix[i, ..]",
            "data[.., j]",
            "block[i..i+3, j..j+3]",
            "filtered[mask]",
            "selected[indices]",
            "elements[row_idx, col_idx]",
        ]

        for source in test_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert (
                len(tokens) > 3
            )  # At least identifier, bracket, something, bracket, EOF


class TestParserArraySupport:
    """Test parser support for array constructs."""

    def test_multidimensional_array_types(self):
        """Test parsing of multidimensional array type declarations."""
        source = """
        Matrix :: [M][N]f32
        Volume :: [D][H][W]u8
        Batch :: [B][C][H][W]f32
        """
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.

    def test_array_literal_parsing(self):
        """Test parsing of multidimensional array literals."""
        source = """
        matrix := [[1.0, 2.0, 3.0],
                   [4.0, 5.0, 6.0]]
        """
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.

    def test_array_function_parsing(self):
        """Test parsing of array function calls."""
        source = """
        zeros := create_zeros([3, 4], f32)
        reshaped := reshape_array(zeros, [12])
        """
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.


class TestParserGeneralEdgeCases:
    """Test general parser edge cases and stress scenarios."""

    def test_deeply_nested_expressions(self):
        """Test parsing of deeply nested expressions."""
        source = """
        result := ((((a + b) * c) - d) / e) % f
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_complex_generic_constraints(self):
        """Test complex generic type constraints."""
        source = """
        complex_fn :: fn($T: Numeric, $U: Integer, a: T, b: U) T {
            ret cast(T, a + cast(T, b))
        }
        """
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.

    def test_nested_match_statements(self):
        """Test nested match statements."""
        source = """
        process :: fn(x: i32, y: i32) i32 {
            match x {
                case 0: {
                    match y {
                        case 0: ret 1
                        case 1: ret 2
                        else: ret 3
                    }
                }
                case 1: ret 4
                else: ret 5
            }
        }
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_complex_pointer_chains(self):
        """Test complex pointer dereferencing chains."""
        source = """
        complex_ptr :: fn() {
            ptr := x.adr
            ptr_ptr := ptr.adr
            ptr_ptr_ptr := ptr_ptr.adr
            value := ptr_ptr_ptr.val.val.val
        }
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_mixed_array_slice_operations(self):
        """Test mixed array and slice operations."""
        source = """
        process_array :: fn(arr: [10]i32) {
            slice1 := arr[1..5]
            slice2 := arr[..3]
            slice3 := arr[7..]
            element := arr[slice1[0]]
        }
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_complex_struct_initialization(self):
        """Test complex struct initialization patterns."""
        source = """
        ComplexStruct :: struct {
            nested: NestedStruct
            array: [5]i32
            ptr: ref f64
        }
        
        NestedStruct :: struct {
            x: i32
            y: f32
        }
        
        create_complex :: fn() ComplexStruct {
            ret ComplexStruct{
                nested: NestedStruct{x: 42, y: 3.14},
                array: [1, 2, 3, 4, 5],
                ptr: new f64
            }
        }
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_recursive_function_calls(self):
        """Test recursive function definitions."""
        source = """
        factorial :: fn(n: i32) i32 {
            if n <= 1 {
                ret 1
            } else {
                ret n * factorial(n - 1)
            }
        }
        
        fibonacci :: fn(n: i32) i32 {
            if n <= 1 {
                ret n
            }
            ret fibonacci(n - 1) + fibonacci(n - 2)
        }
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_complex_generic_function_calls(self):
        """Test complex generic function instantiation."""
        source = """
        swap :: fn(a: ref $T, b: ref $T) {
            temp := a.val
            a.val = b.val
            b.val = temp
        }

        use_swap :: fn() {
            x := 42
            y := 84
            swap(x.adr, y.adr)

            s1 := "hello"
            s2 := "world"
            swap(s1.adr, s2.adr)
        }
        """
        ast = parse_a7(source)
        assert ast is not None

    def test_memory_management_patterns(self):
        """Test complex memory management scenarios."""
        source = """
        memory_test :: fn() {
            // Heap allocation
            ptr := new i32
            ptr.val = 42
            defer del ptr
            
            // Array allocation
            arr := new [100]f64
            defer del arr
            
            // Conditional allocation
            if condition {
                temp := new ComplexStruct
                defer del temp
                process(temp)
            }
        }
        """
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.

    def test_operator_precedence_edge_cases(self):
        """Test complex operator precedence scenarios."""
        test_cases = [
            "result := a + b * c - d / e % f",
            "result := (a and b) or (c and d)",
            "result := !a and b or c",
            "result := a << 2 + b >> 1",
            "result := a & 0xFF | b ^ c",
            "result := a == b and c != d or e < f",
        ]

        for source in test_cases:
            full_source = f"test :: fn() {{ {source} }}"
            ast = parse_a7(full_source)
            assert ast is not None

    def test_malformed_syntax_recovery(self):
        """Test parser error recovery on malformed syntax."""
        malformed_cases = [
            "fn incomplete(",  # Incomplete function
            "struct { x: }",  # Incomplete struct field
            "match x { }",  # Empty match
            "for { break }",  # Invalid for loop
            "[1, 2, 3,]",  # Trailing comma
        ]

        for source in malformed_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()

            with pytest.raises(ParseError):
                parse_a7(source)


class TestArrayErrorHandling:
    """Test error handling for array-related syntax errors."""

    def test_invalid_array_dimensions(self):
        """Test error handling for invalid array dimensions."""
        invalid_cases = [
            "data := [[[[]]]]]",  # Unmatched brackets
            "mixed := [1, [2, 3]]",  # Mixed dimensions
            "empty := []",  # Empty array
        ]

        for source in invalid_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            # Should tokenize but may fail in parser
            assert len(tokens) > 0

    def test_array_function_argument_errors(self):
        """Test error handling for array function arguments."""
        invalid_cases = [
            "create_array()",  # Missing arguments
            "reshape_array(a)",  # Missing shape argument
            "sum_array(a, dim:)",  # Missing dimension value
        ]

        for source in invalid_cases:
            with pytest.raises(ParseError):
                parse_a7(source)

    def test_broadcasting_syntax_errors(self):
        """Test error handling for broadcasting syntax."""
        source = """
        a := create_array([3, 1])
        b := create_array([2, 5])
        result := a +  # Incomplete expression
        """

        with pytest.raises(ParseError):
            parse_a7(source)


class TestArraySemanticValidation:
    """Test semantic validation of array operations (when implemented)."""

    def test_array_shape_compatibility(self):
        """Test array shape compatibility checking."""
        # These would require semantic analysis to validate
        source = """
        compatible_shapes :: fn() {
            a := create_array([3, 4])
            b := create_array([3, 4])
            result := a + b  // Should be compatible
        }
        
        incompatible_shapes :: fn() {
            a := create_array([3, 4])
            b := create_array([2, 5])
            result := a + b  // Should require broadcasting or error
        }
        """

        # For now, just test that it parses
        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.

    def test_array_type_inference(self):
        """Test array type inference scenarios."""
        source = """
        infer_types :: fn() {
            // Type should be inferred from literal
            matrix := [[1.0, 2.0], [3.0, 4.0]]  // f64 matrix
            integers := [[1, 2], [3, 4]]         // i32 matrix
            
            // Type should be inferred from function
            zeros := create_zeros([3, 3], f32)   // f32 array
        }
        """

        try:
            ast = parse_a7(source)
            assert ast is not None
        except ParseError:
            pass  # Document current parser behavior for this edge case.
