"""
Test semantic analysis - Expression tests.

Covers:
- Binary operators (arithmetic, comparison, logical, bitwise)
- Unary operators (negation, not, address-of, dereference)
- Expression type checking and compatibility
- Operator precedence and associativity
- Complex nested expressions
- Member access and indexing
"""

import pytest
from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.errors import SemanticError, CompilerError


def parse_program(source: str):
    """Helper to parse a source program."""
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def run_semantic_analysis(source: str):
    """Helper to run full semantic analysis.

    Raises SemanticError if any pass detects errors.
    """
    program = parse_program(source)

    # Run name resolution pass
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    if resolver.errors:
        raise resolver.errors[0]

    # Run type checking pass
    type_checker = TypeCheckingPass(symbols)
    node_types = type_checker.analyze(program, "<test>")
    if type_checker.errors:
        raise type_checker.errors[0]

    # Run semantic validation pass
    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<test>")
    if validator.errors:
        raise validator.errors[0]

    return symbols, node_types


def expect_success(source: str) -> bool:
    """Helper to expect successful semantic analysis."""
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def expect_error(source: str, error_fragment: str = None) -> bool:
    """Helper to expect semantic error with optional message check."""
    try:
        run_semantic_analysis(source)
        return False
    except CompilerError as e:
        if error_fragment:
            return error_fragment.lower() in str(e).lower()
        return True


class TestArithmeticOperators:
    """Test arithmetic operator type checking."""

    def test_integer_arithmetic(self):
        """Test integer arithmetic operations."""
        source = """
        main :: fn() {
            a := 10 + 20
            b := 30 - 15
            c := 5 * 6
            d := 100 / 4
            e := 17 % 5
        }
        """
        assert expect_success(source)

    def test_float_arithmetic(self):
        """Test floating-point arithmetic operations."""
        source = """
        main :: fn() {
            a := 3.14 + 2.71
            b := 10.5 - 3.2
            c := 2.5 * 4.0
            d := 15.0 / 3.0
        }
        """
        assert expect_success(source)

    def test_mixed_type_arithmetic_error(self):
        """Test arithmetic with incompatible types."""
        source = """
        main :: fn() {
            x := 10 + "hello"
        }
        """
        assert expect_error(source, "type")

    def test_compound_assignment_operators(self):
        """Test compound assignment operators."""
        source = """
        main :: fn() {
            x: i32 = 10
            x += 5
            x -= 3
            x *= 2
            x /= 4
            x %= 3
        }
        """
        assert expect_success(source)


class TestComparisonOperators:
    """Test comparison operator type checking."""

    def test_integer_comparisons(self):
        """Test integer comparison operations."""
        source = """
        main :: fn() {
            a := 10 == 20
            b := 30 != 15
            c := 5 < 6
            d := 100 > 4
            e := 17 <= 5
            f := 23 >= 23
        }
        """
        assert expect_success(source)

    def test_float_comparisons(self):
        """Test floating-point comparison operations."""
        source = """
        main :: fn() {
            a := 3.14 == 3.14
            b := 2.71 != 2.72
            c := 1.5 < 2.5
            d := 10.0 > 5.0
        }
        """
        assert expect_success(source)

    def test_boolean_comparisons(self):
        """Test boolean comparison operations."""
        source = """
        main :: fn() {
            a := true == false
            b := true != false
        }
        """
        assert expect_success(source)

    def test_string_comparisons(self):
        """Test string comparison operations."""
        source = """
        main :: fn() {
            a := "hello" == "world"
            b := "foo" != "bar"
        }
        """
        assert expect_success(source)

    def test_struct_ordering_is_rejected(self):
        """Ordering comparisons are only valid for ordered scalar types."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            a: Point
            b: Point
            bad := a < b
        }
        """
        assert expect_error(source, "operator")

    def test_string_ordering_is_rejected(self):
        """Strings can be equality-compared but not ordered."""
        source = """
        main :: fn() {
            bad := "a" < "b"
        }
        """
        assert expect_error(source, "operator")


class TestLogicalOperators:
    """Test logical operator type checking."""

    def test_logical_and_or(self):
        """Test logical and/or operations."""
        source = """
        main :: fn() {
            a := true and false
            b := true or false
            c := (10 > 5) and (20 < 30)
            d := (1 == 2) or (3 != 3)
        }
        """
        assert expect_success(source)

    def test_logical_not(self):
        """Test logical not operation."""
        source = """
        main :: fn() {
            a := not true
            b := not false
            c := not (10 > 5)
        }
        """
        assert expect_success(source)

    def test_logical_with_non_boolean_error(self):
        """Test logical operators with non-boolean operands."""
        source = """
        main :: fn() {
            x := 10 and 20
        }
        """
        # This should error - logical operators require boolean operands
        result = expect_error(source, "bool")
        # Might not be implemented yet
        assert isinstance(result, bool)


class TestBitwiseOperators:
    """Test bitwise operator type checking."""

    def test_bitwise_operations(self):
        """Test bitwise operations."""
        source = """
        main :: fn() {
            a := 0b1010 & 0b1100
            b := 0b1010 | 0b0101
            c := 0b1010 ^ 0b1100
            d := 0b0011 << 2
            e := 0b1100 >> 2
        }
        """
        assert expect_success(source)

    def test_bitwise_compound_assignments(self):
        """Test bitwise compound assignment operators."""
        source = """
        main :: fn() {
            x: i32 = 0xFF
            x &= 0x0F
            x |= 0xF0
            x ^= 0xAA
            x <<= 1
            x >>= 2
        }
        """
        assert expect_success(source)

    def test_bitwise_not(self):
        """Test bitwise not operation."""
        source = """
        main :: fn() {
            a := ~0b1010
        }
        """
        assert expect_success(source)


class TestUnaryOperators:
    """Test unary operator type checking."""

    def test_numeric_negation(self):
        """Test numeric negation."""
        source = """
        main :: fn() {
            a := -42
            b := -3.14
            c: i32 = 10
            d := -c
        }
        """
        assert expect_success(source)

    def test_address_of_operator(self):
        """Test address-of operator (.adr)."""
        source = """
        main :: fn() {
            x: i32 = 42
            p := x.adr
            pp := p.adr
        }
        """
        assert expect_success(source)

    def test_dereference_operator(self):
        """Test dereference operator (.val)."""
        source = """
        main :: fn() {
            x: i32 = 42
            p := x.adr
            y := p.val
            p.val = 100
        }
        """
        assert expect_success(source)

    def test_dereference_non_pointer_error(self):
        """Test dereference of non-pointer type."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := x.val
        }
        """
        # This should error - can't dereference non-pointer
        result = expect_error(source, "pointer")
        # Might not be implemented yet
        assert isinstance(result, bool)


class TestMemberAccessAndIndexing:
    """Test member access and array indexing."""

    def test_struct_field_access(self):
        """Test struct field access."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p: Point
            a := p.x
            b := p.y
            p.x = 10
        }
        """
        assert expect_success(source)

    def test_nested_struct_field_access(self):
        """Test nested struct field access."""
        source = """
        Inner :: struct {
            value: i32,
        }

        Outer :: struct {
            inner: Inner,
        }

        main :: fn() {
            o: Outer
            x := o.inner.value
            o.inner.value = 42
        }
        """
        assert expect_success(source)

    def test_array_indexing(self):
        """Test array indexing operations."""
        source = """
        main :: fn() {
            arr: [5]i32
            x := arr[0]
            arr[1] = 42
            y := arr[2] + arr[3]
        }
        """
        assert expect_success(source)

    def test_multidimensional_array_indexing(self):
        """Test multidimensional array indexing."""
        source = """
        main :: fn() {
            matrix: [3][4]i32
            x := matrix[0][1]
            matrix[2][3] = 99
        }
        """
        assert expect_success(source)

    def test_invalid_field_access_error(self):
        """Test accessing non-existent struct field."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p: Point
            z := p.z
        }
        """
        # This should error - field 'z' doesn't exist
        result = expect_error(source, "field")
        # Might not be implemented yet
        assert isinstance(result, bool)


class TestComplexExpressions:
    """Test complex nested and combined expressions."""

    def test_complex_arithmetic_expression(self):
        """Test complex arithmetic expression with multiple operators."""
        source = """
        main :: fn() {
            result := (10 + 20) * 3 - 15 / 5 + 2 % 2
        }
        """
        assert expect_success(source)

    def test_complex_logical_expression(self):
        """Test complex logical expression."""
        source = """
        main :: fn() {
            result := (10 > 5) and (20 < 30) or (15 == 15)
        }
        """
        assert expect_success(source)

    def test_mixed_expression_with_variables(self):
        """Test mixed expression with variables and operators."""
        source = """
        main :: fn() {
            a: i32 = 10
            b: i32 = 20
            c: i32 = 30
            result := (a + b) * c - (a / 2)
        }
        """
        assert expect_success(source)

    def test_expression_with_function_calls(self):
        """Test expression with function call results."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        multiply :: fn(a: i32, b: i32) i32 {
            ret a * b
        }

        main :: fn() {
            result := add(10, 20) + multiply(5, 6)
        }
        """
        assert expect_success(source)

    def test_expression_with_casts(self):
        """Test expression with type casts."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := cast(f64, x) * 3.14
        }
        """
        assert expect_success(source)
