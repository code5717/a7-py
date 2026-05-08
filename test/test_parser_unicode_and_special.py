"""
Tests for Unicode, special characters, and internationalization.

Creative tests covering non-ASCII content, edge cases in string handling,
and unusual but valid identifier patterns.
"""

import pytest
from a7.parser import parse_a7
from a7.ast_nodes import NodeKind


class TestUnicodeStrings:
    """Tests for Unicode content in strings."""

    def test_emoji_in_strings(self):
        """Test emoji and Unicode symbols in string literals."""
        code = """
        main :: fn() {
            // Emojis
            message1 := "Hello 👋 World 🌍"
            status := "✅ Success"
            error := "❌ Failed"
            warning := "⚠️ Warning"

            // Math symbols
            formula := "E = mc² and √x + ∫f(x)dx"
            pi := "π ≈ 3.14159"

            // Various Unicode
            greek := "α β γ δ ε"
            arrows := "← → ↑ ↓ ↔"
            symbols := "© ® ™ § ¶"
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_multilingual_strings(self):
        """Test strings with various writing systems."""
        code = """
        main :: fn() {
            // Different languages
            english := "Hello World"
            chinese := "你好世界"
            japanese := "こんにちは世界"
            korean := "안녕하세요 세계"
            arabic := "مرحبا بالعالم"
            russian := "Привет мир"
            hebrew := "שלום עולם"

            // Mixed
            mixed := "Hello 世界 مرحبا Привет שלום"
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_special_whitespace_in_strings(self):
        """Test various whitespace characters."""
        code = """
        main :: fn() {
            // Regular spaces
            s1 := "word1 word2  word3"

            // Tab characters
            s2 := "col1\tcol2\tcol3"

            // Newlines
            s3 := "line1\nline2\nline3"

            // Mixed whitespace
            s4 := "start\t\n  middle  \n\tend"
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestCommentEdgeCases:
    """Creative test cases for comments."""

    def test_comments_in_unusual_positions(self):
        """Test comments in various positions."""
        code = """
        // Top level comment
        main /* inline */ :: fn() { // end of line
            // Inside function
            x := /* mid-expression */ 42

            if /* before condition */ true { // after brace
                // Inside block
                y := 10 // trailing
            } // after block

            /* Multi-line
               comment across
               several lines */
            z := 99
        }
        // End comment
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_nested_block_comments(self):
        """Test deeply nested block comments."""
        code = """
        main :: fn() {
            /* Level 1
               /* Level 2
                  /* Level 3
                     /* Level 4 */
                  */
               */
            */
            x := 42

            /* Another /* nested */ comment */
            y := 10
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_comments_with_special_content(self):
        """Test comments containing code-like content."""
        code = """
        main :: fn() {
            // TODO: implement this function
            // FIXME: broken logic here
            // NOTE: optimization opportunity

            /* This is commented out code:
               x := 10
               if x > 5 {
                   do_something()
               }
            */

            // String-like content in comment: "not a string"
            // Symbol soup: {}[]()::.:=+-*/<>!&|^%~

            actual := 42
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestLongAndComplexCode:
    """Tests for very long or complex code structures."""

    def test_very_long_identifier(self):
        """Test identifiers approaching maximum length."""
        code = """
        main :: fn() {
            // 50 character identifier
            this_is_a_very_long_variable_name_for_testing := 42

            // Long function name
            calculate_the_hypotenuse_of_right_triangle :: fn(a: f64, b: f64) f64 {
                ret 0.0
            }

            // Long type name
            VeryLongStructureNameForTestingPurposesOnly :: struct {
                field: i32
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_very_long_string_literal(self):
        """Test very long string literal."""
        code = """
        main :: fn() {
            // Long string
            lorem := "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."

            // Very long URL
            url := "https://www.example.com/api/v1/resources/items/12345/subitems/67890/details?param1=value1&param2=value2&param3=value3&format=json"
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_many_function_parameters(self):
        """Test functions with many parameters."""
        code = """
        // Function with 10 parameters
        complex_function :: fn(
            p1: i32,
            p2: i32,
            p3: i32,
            p4: i32,
            p5: i32,
            p6: i32,
            p7: i32,
            p8: i32,
            p9: i32,
            p10: i32
        ) i32 {
            ret p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9 + p10
        }

        // Generic with multiple type parameters
        multi_generic :: fn(a: $T1, b: $T2, c: $T3, d: $T4) $T1 {
            ret a
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_very_wide_expression(self):
        """Test extremely wide expression."""
        code = """
        main :: fn() {
            // Long chain of operations
            result := a + b + c + d + e + f + g + h + i + j + k + l + m + n + o + p + q + r + s + t + u + v + w + x + y + z

            // Long boolean expression
            condition := a and b and c and d and e or f and g and h and i and j or k and l and m and n and o

            // Long function call chain
            value := obj.method1().method2().method3().method4().method5().field.nested.data
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestAmbiguousSyntax:
    """Tests for syntax that could be ambiguous but should parse correctly."""

    def test_generic_vs_comparison(self):
        """Test generic syntax vs less-than/greater-than."""
        code = """
        main :: fn() {
            // Generic type
            list := List(i32){}

            // Comparison
            if x < 10 {
                y := 5
            }

            // Complex generic
            data := Map(string, Vec(i32)){}

            // Multiple comparisons
            if a < b and c > d {
                work()
            }

            // Generic instantiation in expression
            result := process(Option(i32), value)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_struct_literal_vs_block(self):
        """Test struct literal vs standalone block disambiguation."""
        code = """
        Point :: struct {
            x: i32
            y: i32
        }

        main :: fn() {
            // Clearly struct literal (type annotation)
            p1: Point = Point{x: 1, y: 2}

            // Struct literal with inference
            p2 := Point{x: 3, y: 4}

            // Standalone block
            {
                temp := 10
                work(temp)
            }

            // Block with declarations
            {
                x := 1
                y := 2
                z := x + y
            }

            // Struct literal in expression
            distance := calc(Point{x: 0, y: 0}, Point{x: 10, y: 10})
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_minus_vs_negative(self):
        """Test minus operator vs negative literal."""
        code = """
        main :: fn() {
            // Negative literals
            a := -42
            b := -3.14

            // Subtraction
            c := 10 - 5
            d := x - y

            // Negative in expression
            e := -x + y
            f := x + -y

            // Complex
            g := -a - -b + -c

            // In array
            values: [3]i32 = [-1, -2, -3]
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestBoundaryValues:
    """Tests with boundary and extreme values."""

    def test_number_extremes(self):
        """Test extreme numeric values."""
        code = """
        main :: fn() {
            // Small values
            zero := 0
            one := 1
            tiny := 0.000001

            // Large values
            million := 1_000_000
            billion := 1_000_000_000
            large_float := 999999.999999

            // Hex extremes
            min_byte := 0x00
            max_byte := 0xFF
            large_hex := 0xDEADBEEF

            // In expressions
            scaled := 1_000_000 * 1_000_000
            precise := 0.123456789 + 0.000000001
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_array_size_extremes(self):
        """Test various array sizes."""
        code = """
        main :: fn() {
            // Small arrays
            single: [1]i32
            pair: [2]i32
            triple: [3]i32

            // Common sizes
            small: [10]i32
            medium: [100]i32
            large: [1000]i32

            // Power of 2 sizes
            p2_8: [8]i32
            p2_16: [16]i32
            p2_32: [32]i32
            p2_64: [64]i32
            p2_128: [128]i32
            p2_256: [256]i32
            p2_512: [512]i32
            p2_1024: [1024]i32

            // Multidimensional
            matrix_2x2: [2][2]i32
            matrix_10x10: [10][10]i32
            tensor_3d: [10][10][10]i32
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestUnusualButValidPatterns:
    """Unusual but completely valid code patterns."""

    def test_empty_statements_and_blocks(self):
        """Test empty but valid constructs."""
        code = """
        EmptyStruct :: struct {
        }

        EmptyEnum :: enum {
        }

        empty_function :: fn() {
        }

        main :: fn() {
            // Empty block
            {
            }

            // Empty if
            if true {
            }

            // Empty while
            while false {
            }

            // Empty for
            for i := 0; i < 0; i += 1 {
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_single_item_constructs(self):
        """Test constructs with minimal content."""
        code = """
        // Single field struct
        Single :: struct {
            value: i32
        }

        // Single variant enum
        Status :: enum {
            OK
        }

        // Single parameter function
        identity :: fn(x: i32) i32 {
            ret x
        }

        main :: fn() {
            // Single element array
            one: [1]i32 = [42]

            // Single iteration loop
            for i := 0; i < 1; i += 1 {
                work()
            }

            // Single case match
            result := match x {
                case 1: 100
                else: 0
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_redundant_but_valid_syntax(self):
        """Test redundant but syntactically valid patterns."""
        code = """
        main :: fn() {
            // Double negation
            a := !!true
            b := !!x

            // Identity operations
            c := x + 0
            d := x * 1
            e := x - 0
            f := x / 1

            // Redundant parentheses
            g := ((x))
            h := (((a + b)))

            // Redundant casts (casting to same type conceptually)
            i := cast(i32, int_value)

            // No-op expressions
            x
            42
            "string"
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_creative_identifier_patterns(self):
        """Test valid but unusual identifier patterns."""
        code = """
        main :: fn() {
            // Single letter
            a := 1
            x := 2
            z := 3

            // With numbers
            var1 := 10
            var2 := 20
            x1y2z3 := 30

            // With underscores
            _private := 1
            __very_private := 2
            _x_ := 3
            x_y_z := 4

            // Mixed patterns
            camelCase := 1
            snake_case := 2
            PascalCase := 3
            SCREAMING_SNAKE := 4

            // Long but readable
            total_sum_of_all_elements_in_array := 0
            maximum_retry_attempts_before_failure := 3
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
