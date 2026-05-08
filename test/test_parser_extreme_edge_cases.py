"""
Extreme edge case tests for the A7 parser.
Tests cover deep nesting, Unicode, boundary conditions, and complex corner cases.
"""

import pytest
from a7.parser import Parser
from a7.tokens import Tokenizer, Token, TokenType
from a7.errors import ParseError, TokenizerError
from a7.ast_nodes import NodeKind, create_identifier


class TestDeepNesting:
    """Test deeply nested structures that stress the parser."""

    def test_deeply_nested_parentheses(self):
        """Test extremely deep parenthesis nesting."""
        depth = 100
        code = "main :: fn() {\n    x := " + "(" * depth + "42" + ")" * depth + "\n}"
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None
        assert ast.kind == NodeKind.PROGRAM

    def test_deeply_nested_blocks(self):
        """Test deeply nested block statements."""
        depth = 50
        code = "main :: fn() {\n"
        for i in range(depth):
            code += "    " * (i + 1) + "{\n"
        code += "    " * (depth + 1) + "x := 1\n"
        for i in range(depth, 0, -1):
            code += "    " * i + "}\n"
        code += "}"

        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_deeply_nested_if_else(self):
        """Test deeply nested if-else chains."""
        depth = 30
        code = "main :: fn() {\n    x := 0\n"
        for i in range(depth):
            code += "    " * (i + 1) + f"if x == {i} {{\n"
            code += "    " * (i + 2) + f"x = {i + 1}\n"

        for i in range(depth, 0, -1):
            code += "    " * i + "}\n"
        code += "}"

        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_deeply_nested_function_calls(self):
        """Test deeply nested function calls."""
        depth = 50
        code = "main :: fn() {\n    x := " + "f(" * depth + "42" + ")" * depth + "\n}"
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_deeply_nested_array_access(self):
        """Test deeply nested array access."""
        code = """main :: fn() {
    arr: [][][][][]i32 = [[[[[1]]]]]
    x := arr[0][0][0][0][0]
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_deeply_nested_struct_fields(self):
        """Test deeply nested struct field access."""
        code = """A :: struct { b: B }
B :: struct { c: C }
C :: struct { d: D }
D :: struct { e: E }
E :: struct { value: i32 }

main :: fn() {
    a := A{b: B{c: C{d: D{e: E{value: 42}}}}}
    x := a.b.c.d.e.value
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestUnicodeAndSpecialChars:
    """Test Unicode handling and special character scenarios."""

    def test_unicode_in_strings(self):
        """Test Unicode characters in string literals."""
        code = '''main :: fn() {
    s1 := "Hello 世界 🌍"
    s2 := "Emoji: 😀😃😄😁"
    s3 := "Math: ∑ ∏ ∫ √"
    s4 := "Greek: α β γ δ ε"
}'''
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_escaped_characters_in_strings(self):
        """Test various escape sequences in strings."""
        code = r'''main :: fn() {
    s1 := "Line 1\nLine 2"
    s2 := "Tab\there"
    s3 := "Quote: \"Hello\""
    s4 := "Backslash: \\"
    s5 := "Hex: \x41\x42\x43"
}'''
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_special_whitespace(self):
        """Test various whitespace characters."""
        # A7 doesn't support tabs - they should raise an error
        code = "main	::	fn()		{x   :=   1}"
        lexer = Tokenizer(code)
        with pytest.raises(TokenizerError):
            tokens = lexer.tokenize()

    def test_empty_strings(self):
        """Test empty string literals."""
        code = '''main :: fn() {
    empty := ""
    also_empty :: ""
}'''
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_empty_file(self):
        """Test completely empty source file."""
        code = ""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 0

    def test_only_comments(self):
        """Test file with only comments."""
        code = """// This is a comment
// Another comment
/* Block comment */
// More comments"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None
        assert len(ast.declarations) == 0

    def test_maximum_identifier_length(self):
        """Test identifier at maximum allowed length."""
        # A7 allows 100 character identifiers
        long_name = "a" * 100
        code = f"{long_name} :: 42"
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_maximum_number_length(self):
        """Test number literal at maximum allowed length."""
        # A7 allows 100 character numbers
        long_number = "1" * 100
        code = f"x :: {long_number}"
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_zero_values(self):
        """Test various zero and empty values."""
        code = """main :: fn() {
    zero_int := 0
    zero_float := 0.0
    zero_hex := 0x0
    zero_binary := 0b0
    zero_octal := 0o0
    empty_array: [0]i32 = []
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_single_character_identifiers(self):
        """Test single character variable names."""
        code = """a :: 1
b :: 2
c :: fn() { d := 3; e := d + 1 }
f :: struct { g: i32 }"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestExpressionPrecedence:
    """Test complex expression precedence scenarios."""

    def test_complex_arithmetic_precedence(self):
        """Test complex arithmetic expression precedence."""
        code = """main :: fn() {
    // Should follow standard precedence rules
    a := 1 + 2 * 3 - 4 / 2 % 3
    b := (1 + 2) * 3 - 4 / (2 % 3)
    c := -1 + -2 * -3
    d := 1 << 2 + 3 >> 1
    e := 1 & 2 | 3 ^ 4
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_complex_logical_precedence(self):
        """Test complex logical expression precedence."""
        code = """main :: fn() {
    a := true and false or true and not false
    b := !true or false and true
    c := 1 < 2 and 3 > 2 or 4 == 4 and 5 != 6
    d := (1 < 2) and (3 > 2) or (4 == 4) and (5 != 6)
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_mixed_precedence(self):
        """Test mixed arithmetic and logical precedence."""
        code = """main :: fn() {
    a := 1 + 2 < 3 * 4 and 5 - 6 > 7 / 8
    b := true and 1 + 2 * 3 == 7
    c := !false or 10 % 3 != 0
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_chained_comparisons(self):
        """Test chained comparison operators."""
        code = """main :: fn() {
    // Each comparison should be separate
    a := 1 < 2 < 3  // Should parse as (1 < 2) < 3
    b := 5 > 4 > 3
    c := 1 == 1 == true
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestAmbiguousPatterns:
    """Test potentially ambiguous grammar patterns."""

    def test_struct_literal_vs_block(self):
        """Test disambiguation between struct literals and blocks."""
        code = """Point :: struct { x: i32, y: i32 }

main :: fn() {
    // Struct literal
    p := Point{x: 1, y: 2}

    // Block statement
    {
        x := 1
        y := 2
    }

    // Nested scenarios
    if true { p2 := Point{x: 3, y: 4} }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_generic_vs_comparison(self):
        """Test disambiguation between generics and comparisons."""
        code = """main :: fn() {
    // Comparison
    a := 1 < 2 > 0

    // Generic type (in type context)
    list: List($T) = nil

    // Function with generic
    swap :: fn(a: ref $T, b: ref $T) {}
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_array_type_vs_array_literal(self):
        """Test array type vs array literal disambiguation."""
        code = """main :: fn() {
    // Array type in declaration
    arr: [5]i32

    // Array literal
    values := [1, 2, 3, 4, 5]

    // Array of arrays
    matrix: [2][3]i32 = [[1, 2, 3], [4, 5, 6]]
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestErrorScenarios:
    """Test error handling and recovery scenarios."""

    def test_unterminated_string(self):
        """Test unterminated string literal."""
        code = 'main :: fn() { s := "unterminated }'
        lexer = Tokenizer(code)
        with pytest.raises(TokenizerError):
            lexer.tokenize()

    def test_invalid_number_format(self):
        """Test invalid number formats."""
        test_cases = [
            "x := 0x",  # Hex without digits
            "x := 0b",  # Binary without digits
            "x := 0o",  # Octal without digits
            # Note: "1.2.3" tokenizes as two floats (1.2 and .3) since leading dots are valid
            # This will fail at parsing, not tokenization
            "x := 1e",  # Incomplete scientific notation
        ]

        for code in test_cases:
            lexer = Tokenizer(code)
            with pytest.raises(TokenizerError):
                lexer.tokenize()

    def test_mismatched_brackets(self):
        """Test mismatched bracket scenarios."""
        test_cases = [
            "main :: fn() { x := [1, 2, 3) }",  # Mismatched array brackets
            "main :: fn() { f(1, 2] }",  # Mismatched function call
            "main :: fn() { { } ] }",  # Extra closing bracket
        ]

        for code in test_cases:
            lexer = Tokenizer(code)
            tokens = lexer.tokenize()
            parser = Parser(tokens, code)
            with pytest.raises(ParseError):
                parser.parse()

    def test_incomplete_statements(self):
        """Test incomplete statement scenarios that should raise errors."""
        test_cases = [
            "main :: fn() { x := }",  # Missing expression after :=
            "main :: fn() { if }",  # Missing condition after if
            "main :: fn() { for }",  # Missing loop specification
            # Note: "ret" without value is VALID for void functions, so not included
        ]

        for code in test_cases:
            lexer = Tokenizer(code)
            tokens = lexer.tokenize()
            parser = Parser(tokens, code)
            with pytest.raises(ParseError):
                parser.parse()


class TestComplexCombinations:
    """Test complex combinations of language features."""

    def test_generic_struct_with_methods(self):
        """Test generic structs with method-like functions."""
        code = """
List :: struct {
    items: []$T
    size: usize
}

push :: fn(list: ref List, item: $T) {
    // Implementation
}

main :: fn() {
    list := List{items: nil, size: 0}
    push(list.adr, 42)
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_nested_generics(self):
        """Test nested generic types."""
        code = """
Result :: struct {
    value: Option
    error: string
}

Option :: struct {
    has_value: bool
    value: $T
}

main :: fn() {
    result: Result = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_complex_control_flow(self):
        """Test complex control flow with multiple constructs."""
        code = """main :: fn() {
    for i := 0; i < 10; i += 1 {
        if i % 2 == 0 {
            continue
        }

        match i {
            case 1, 3: {
                print("small")
            }
            case 5..7: {
                print("medium")
                fall
            }
            case 9: {
                print("large")
            }
            else: {
                break
            }
        }

        while i > 0 {
            i -= 1
            if i == 0 {
                break
            }
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_complex_type_expressions_implemented(self):
        """Test complex type expressions that ARE currently implemented."""
        code = """main :: fn() {
    // Pointer to array
    arr_ptr: ref [5]i32 = nil

    // Array of pointers
    ptr_arr: [5]ref i32 = nil

    // Multi-dimensional arrays
    matrix: [3][3]f64 = nil

    // Slice of slices
    nested_slice: [][]i32 = nil

    // Pointer to pointer
    ptr_ptr: ref ref i32 = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_expressions(self):
        """Test function type expressions.

        Function types allow declaring function pointers and callbacks.
        Syntax: fn(param_types) return_type
        """
        code = """main :: fn() {
    // Function pointer type - takes two i32s, returns i32
    callback: fn(i32, i32) i32 = nil

    // Function with no parameters, returns void
    handler: fn() void = nil

    // Array of function pointers
    handlers: [10]fn() void = nil

    // Function taking another function as parameter
    mapper: fn(fn(i32) i32, i32) i32 = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_types(self):
        """Test inline struct type expressions.

        Inline struct types allow anonymous struct definitions in type position.
        Syntax: struct { field1: type1, field2: type2, ... }

        Note: Inline structs are value types, cannot be assigned nil.
        Only pointers (ref T) and function pointers can be nil.
        """
        code = """main :: fn() {
    // Inline struct type - uninitialized declaration
    data: struct {
        id: u64
        values: [100]f32
    }

    // Pointer to inline struct type - can be nil
    ptr_data: ref struct {
        id: u64
        values: [100]f32
    } = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestInlineStructTypeEdgeCases:
    """Comprehensive tests for inline struct type parsing edge cases."""

    def test_inline_struct_single_field(self):
        """Test inline struct with single field."""
        code = """main :: fn() {
    point: struct { x: i32 }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_multiple_fields(self):
        """Test inline struct with multiple fields."""
        code = """main :: fn() {
    person: struct {
        name: string
        age: i32
        height: f64
        active: bool
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_with_complex_field_types(self):
        """Test inline struct with complex field types."""
        code = """main :: fn() {
    data: struct {
        values: [100]i32
        names: []string
        ptr: ref i32
        callback: fn(i32) bool
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_nested(self):
        """Test nested inline struct types."""
        code = """main :: fn() {
    outer: struct {
        id: i32
        inner: struct {
            x: f64
            y: f64
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_in_array(self):
        """Test inline struct as array element type."""
        code = """main :: fn() {
    points: [10]struct {
        x: i32
        y: i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_in_slice(self):
        """Test inline struct as slice element type."""
        code = """main :: fn() {
    people: []struct {
        name: string
        age: i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_pointer(self):
        """Test pointer to inline struct type."""
        code = """main :: fn() {
    ptr: ref struct {
        id: u64
        data: [256]u8
    } = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_in_function_parameter(self):
        """Test inline struct in function parameter type."""
        code = """
process :: fn(data: struct { id: i32, value: f64 }) void {
    ret
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_as_return_type(self):
        """Test inline struct as function return type."""
        code = """
get_point :: fn() struct { x: i32, y: i32 } {
    ret cast(struct { x: i32, y: i32 }, nil)
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_with_function_field(self):
        """Test inline struct containing function type field."""
        code = """main :: fn() {
    handler: struct {
        name: string
        callback: fn(i32) bool
        cleanup: fn() void
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_multi_dimensional_array(self):
        """Test inline struct in multi-dimensional arrays."""
        code = """main :: fn() {
    grid: [10][10]struct {
        occupied: bool
        value: i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_complex_nesting(self):
        """Test deeply nested inline struct types."""
        code = """main :: fn() {
    complex: struct {
        id: i32
        data: struct {
            values: [5]i32
            meta: struct {
                created: i64
                modified: i64
            }
        }
        refs: []ref struct {
            key: string
            value: i32
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_with_generic_fields(self):
        """Test inline struct with generic type fields."""
        code = """main :: fn() {
    container: struct {
        data: $T
        size: i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestFunctionTypeEdgeCases:
    """Comprehensive tests for function type parsing edge cases."""

    def test_function_type_no_params(self):
        """Test function type with no parameters."""
        code = """main :: fn() {
    callback: fn() void = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_one_param(self):
        """Test function type with single parameter."""
        code = """main :: fn() {
    callback: fn(i32) void = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_multiple_params(self):
        """Test function type with multiple parameters."""
        code = """main :: fn() {
    callback: fn(i32, f64, string, bool) i32 = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_complex_param_types(self):
        """Test function type with complex parameter types."""
        code = """main :: fn() {
    // Array parameter
    f1: fn([10]i32) void = nil

    // Slice parameter
    f2: fn([]i32) void = nil

    // Pointer parameter
    f3: fn(ref i32) void = nil

    // Multiple complex parameters
    f4: fn([5]i32, ref string, []f64) bool = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_returning_function(self):
        """Test function type that returns another function type."""
        code = """main :: fn() {
    // Function returning function
    factory: fn() fn(i32) string = nil

    // Function taking i32, returning function that takes string and returns bool
    complex: fn(i32) fn(string) bool = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_nested_in_arrays(self):
        """Test function types nested within array types."""
        code = """main :: fn() {
    // Array of function pointers
    handlers: [10]fn() void = nil

    // 2D array of functions
    matrix: [5][5]fn(i32) i32 = nil

    // Slice of function pointers
    callbacks: []fn(string) bool = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_with_pointers(self):
        """Test function types combined with pointer types."""
        code = """main :: fn() {
    // Pointer to function
    fptr: ref fn(i32) i32 = nil

    // Function returning pointer
    get_ptr: fn() ref i32 = nil

    // Function taking pointer, returning pointer
    transform: fn(ref i32) ref i32 = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_taking_function(self):
        """Test function type with function type as parameter."""
        code = """main :: fn() {
    // Function taking function as parameter
    higher_order: fn(fn(i32) i32, i32) i32 = nil

    // Function taking multiple function parameters
    combinator: fn(fn(i32) i32, fn(i32) i32) fn(i32) i32 = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_in_variable_declaration(self):
        """Test function types in various declaration contexts."""
        code = """
// Global function pointer constant
global_callback :: cast(fn(i32) void, nil)

main :: fn() {
    // Local function pointer with explicit type
    local: fn() i32 = nil

    // Function pointer with complex type
    nullable: fn(string) bool = nil

    // Variable declaration with type inference (would need actual function value)
    // handler := some_function  // Would work with actual function value
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestEdgeCaseNumbers:
    """Test edge cases in number parsing."""

    def test_number_boundaries(self):
        """Test numbers at type boundaries."""
        code = """main :: fn() {
    // Maximum values
    max_i8 := 127
    max_u8 := 255
    max_i32 := 2147483647
    max_u32 := 4294967295

    // Minimum values
    min_i8 := -128
    min_i32 := -2147483648

    // Edge case floats
    tiny := 0.000000000000001
    huge := 999999999999999.9
    sci_small := 1.0e-10
    sci_large := 1.0e+10
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_number_formats(self):
        """Test various number format edge cases."""
        code = """main :: fn() {
    // With underscores
    big := 1_000_000_000
    binary := 0b1111_0000_1111_0000
    hex := 0xDEAD_BEEF

    // Leading zeros (octal)
    octal := 0o777

    // Floating point variations
    f1 := .5
    f2 := 5.
    f3 := 5.0
    f4 := 0.5e10
    f5 := 5E-10
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestCommentEdgeCases:
    """Test edge cases in comment handling."""

    def test_nested_block_comments(self):
        """Test nested block comments."""
        code = """/* Outer comment
/* Inner comment */
Still in outer comment */
main :: fn() { x := 1 }"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_comment_like_strings(self):
        """Test strings that look like comments."""
        code = '''main :: fn() {
    s1 := "// This is not a comment"
    s2 := "/* Neither is this */"
    s3 := "Mixed /* // */ styles"
}'''
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_comments_in_expressions(self):
        """Test comments embedded in expressions."""
        # Block comments work mid-expression, but line comments (//) consume to end of line
        # and create a TERMINATOR, which breaks multi-line expressions (this is by design in A7)
        code = """main :: fn() {
    x := 1 + /* comment */ 2 + /* another
         multiline
         comment */ 4
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestPointerEdgeCases:
    """Test edge cases specific to A7's pointer syntax."""

    def test_pointer_chains(self):
        """Test long chains of pointer operations."""
        code = """main :: fn() {
    x := 42
    p1 := x.adr
    p2 := p1.adr
    p3 := p2.adr

    // Deep dereference
    val := p3.val.val.val

    // Mixed operations
    y := p1.val.adr.val
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_pointer_arithmetic_like_expressions(self):
        """Test expressions that might look like pointer arithmetic."""
        code = """main :: fn() {
    ptr := x.adr

    // These should be regular arithmetic, not pointer arithmetic
    a := ptr.val + 1
    b := ptr.val - 1
    c := ptr.val * 2

    // Array element addresses
    arr: [5]i32 = [1, 2, 3, 4, 5]
    elem_ptr := arr[2].adr
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])