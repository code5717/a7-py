"""
Comprehensive semantic analysis test suite for A7.

Tests all semantic rules, type checking, and validation across the entire language.
Organized by feature category for easy maintenance and debugging.
"""

import pytest
from src.tokens import Tokenizer
from src.parser import Parser
from src.passes.name_resolution import NameResolutionPass
from src.passes.type_checker import TypeCheckingPass
from src.passes.semantic_validator import SemanticValidationPass
from src.errors import SemanticError, CompilerError


def parse_program(source: str):
    """Helper to parse a source program."""
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def run_semantic_analysis(source: str):
    """Helper to run full semantic analysis pipeline.

    Raises SemanticError if any pass detects errors.
    """
    program = parse_program(source)

    # Name resolution
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "test.a7")
    if resolver.errors:
        raise resolver.errors[0]

    # Type checking
    checker = TypeCheckingPass(symbols)
    checker.analyze(program, "test.a7")
    if checker.errors:
        raise checker.errors[0]

    # Semantic validation
    validator = SemanticValidationPass(symbols, checker.node_types)
    validator.analyze(program, "test.a7")
    if validator.errors:
        raise validator.errors[0]

    return symbols, checker


def run_analysis_expect_success(source: str):
    """Helper that just verifies analysis completes without errors."""
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def run_analysis_expect_error(source: str):
    """Helper that expects analysis to fail with SemanticError."""
    try:
        run_semantic_analysis(source)
        return False  # Should have raised
    except CompilerError:
        return True  # Expected


class TestPrimitiveTypes:
    """Test primitive type operations and conversions."""

    def test_integer_literals(self):
        """Test integer literal type inference."""
        source = """
        main :: fn() {
            a := 42
            b := 0xFF
            c := 0b1010
            d := 0o77
        }
        """
        # Just verify analysis completes without errors
        assert run_analysis_expect_success(source)

    def test_float_literals(self):
        """Test float literal type inference."""
        source = """
        main :: fn() {
            x := 3.14
            y := 2.5e-10
        }
        """
        assert run_analysis_expect_success(source)

    def test_boolean_literals(self):
        """Test boolean type."""
        source = """
        main :: fn() {
            t := true
            f := false
        }
        """
        assert run_analysis_expect_success(source)

    def test_string_literals(self):
        """Test string type."""
        source = """
        main :: fn() {
            msg := "hello"
        }
        """
        assert run_analysis_expect_success(source)

    def test_char_literals(self):
        """Test character type."""
        source = """
        main :: fn() {
            c := 'a'
        }
        """
        assert run_analysis_expect_success(source)

    def test_type_annotations(self):
        """Test explicit type annotations."""
        source = """
        main :: fn() {
            a: i8 = 1
            b: i16 = 2
            c: i32 = 3
            d: i64 = 4
            e: u8 = 5
            f: u16 = 6
            g: u32 = 7
            h: u64 = 8
            x: f32 = 1.0
            y: f64 = 2.0
        }
        """
        assert run_analysis_expect_success(source)


class TestArithmeticOperators:
    """Test arithmetic operations and type checking."""

    def test_basic_arithmetic(self):
        """Test basic arithmetic operators."""
        source = """
        main :: fn() {
            a := 10 + 5
            b := 10 - 5
            c := 10 * 5
            d := 10 / 5
            e := 10 % 3
        }
        """
        assert run_analysis_expect_success(source)

    def test_arithmetic_type_compatibility(self):
        """Test arithmetic with compatible types."""
        source = """
        main :: fn() {
            x: i32 = 10
            y: i32 = 20
            z := x + y
        }
        """
        assert run_analysis_expect_success(source)

    def test_unary_operators(self):
        """Test unary operators."""
        source = """
        main :: fn() {
            a := -5
            b := not true
            c := ~0xFF
        }
        """
        assert run_analysis_expect_success(source)


class TestComparisonOperators:
    """Test comparison operations."""

    def test_equality_operators(self):
        """Test == and != operators."""
        source = """
        main :: fn() {
            a := 5 == 5
            b := 5 != 3
        }
        """
        assert run_analysis_expect_success(source)

    def test_relational_operators(self):
        """Test <, <=, >, >= operators."""
        source = """
        main :: fn() {
            a := 5 < 10
            b := 5 <= 5
            c := 10 > 5
            d := 10 >= 10
        }
        """
        assert run_analysis_expect_success(source)


class TestLogicalOperators:
    """Test logical operations."""

    def test_and_or_operators(self):
        """Test 'and' and 'or' operators."""
        source = """
        main :: fn() {
            a := true and false
            b := true or false
        }
        """
        assert run_analysis_expect_success(source)

    def test_not_operator(self):
        """Test 'not' operator."""
        source = """
        main :: fn() {
            a := not true
        }
        """
        assert run_analysis_expect_success(source)


class TestBitwiseOperators:
    """Test bitwise operations."""

    def test_bitwise_and_or_xor(self):
        """Test bitwise &, |, ^ operators."""
        source = """
        main :: fn() {
            a := 0xFF & 0x0F
            b := 0xFF | 0x0F
            c := 0xFF ^ 0x0F
        }
        """
        assert run_analysis_expect_success(source)

    def test_bitwise_shifts(self):
        """Test << and >> operators."""
        source = """
        main :: fn() {
            a := 1 << 4
            b := 16 >> 2
        }
        """
        assert run_analysis_expect_success(source)


class TestArrayTypes:
    """Test fixed-size array operations."""

    def test_array_declaration(self):
        """Test array type declarations."""
        source = """
        main :: fn() {
            arr: [5]i32
        }
        """
        assert run_analysis_expect_success(source)

    def test_array_initialization(self):
        """Test array initialization."""
        source = """
        main :: fn() {
            arr := [1, 2, 3, 4, 5]
        }
        """
        assert run_analysis_expect_success(source)

    def test_array_indexing(self):
        """Test array element access."""
        source = """
        main :: fn() {
            arr := [1, 2, 3]
            x := arr[0]
        }
        """
        assert run_analysis_expect_success(source)

    def test_multidimensional_arrays(self):
        """Test multi-dimensional arrays."""
        source = """
        main :: fn() {
            matrix: [3][4]i32
        }
        """
        assert run_analysis_expect_success(source)


class TestSliceTypes:
    """Test dynamic slice operations."""

    def test_slice_declaration(self):
        """Test slice type declarations."""
        source = """
        main :: fn() {
            slice: []i32
        }
        """
        assert run_analysis_expect_success(source)

    def test_slice_indexing(self):
        """Test slice element access."""
        source = """
        main :: fn() {
            slice: []i32
            x := slice[0]
        }
        """
        assert run_analysis_expect_success(source)

    def test_slice_expression_from_array(self):
        """Test array sub-slicing produces a slice type."""
        source = """
        main :: fn() {
            arr: [4]i32 = [1, 2, 3, 4]
            slice := arr[1..3]
            x := slice[0]
        }
        """
        assert run_analysis_expect_success(source)

    def test_slice_expression_rejects_non_sliceable_values(self):
        """Only arrays and slices may be sliced."""
        source = """
        main :: fn() {
            x := 42
            y := x[0..1]
        }
        """
        assert run_analysis_expect_error(source)


class TestPointerTypes:
    """Test pointer operations."""

    def test_pointer_declaration(self):
        """Test pointer type declarations."""
        # A7 uses 'ref T' for reference types (not 'ptr T')
        source = """
        main :: fn() {
            x: i32 = 42
            p := x.adr
        }
        """
        assert run_analysis_expect_success(source)

    def test_address_of_operator(self):
        """Test .adr operator."""
        source = """
        main :: fn() {
            x := 42
            p := x.adr
        }
        """
        assert run_analysis_expect_success(source)

    def test_dereference_operator(self):
        """Test .val operator."""
        source = """
        main :: fn() {
            x := 42
            p := x.adr
            y := p.val
        }
        """
        assert run_analysis_expect_success(source)


class TestReferenceTypes:
    """Test reference type operations."""

    def test_reference_declaration(self):
        """Test ref type declarations."""
        source = """
        main :: fn() {
            r: ref i32
        }
        """
        assert run_analysis_expect_success(source)


class TestFunctionTypes:
    """Test function type checking."""

    def test_simple_function(self):
        """Test simple function declaration."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }
        """
        assert run_analysis_expect_success(source)

    def test_void_function(self):
        """Test void function (no return type)."""
        source = """
        print_hello :: fn() {
        }
        """
        assert run_analysis_expect_success(source)

    def test_function_call(self):
        """Test function call type checking."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            result := add(5, 10)
        }
        """
        assert run_analysis_expect_success(source)

    def test_nested_function_calls(self):
        """Test nested function calls."""
        source = """
        double :: fn(x: i32) i32 {
            ret x * 2
        }

        quad :: fn(x: i32) i32 {
            ret double(double(x))
        }
        """
        assert run_analysis_expect_success(source)


class TestStructTypes:
    """Test struct type operations."""

    def test_struct_declaration(self):
        """Test struct type declaration."""
        source = """
        Point :: struct {
            x: i32
            y: i32
        }
        """
        assert run_analysis_expect_success(source)

    def test_struct_initialization(self):
        """Test struct literal initialization."""
        source = """
        Point :: struct {
            x: i32
            y: i32
        }

        main :: fn() {
            p := Point{x: 10, y: 20}
        }
        """
        assert run_analysis_expect_success(source)

    def test_struct_field_access(self):
        """Test field access on structs."""
        source = """
        Point :: struct {
            x: i32
            y: i32
        }

        main :: fn() {
            p := Point{x: 10, y: 20}
            x_val := p.x
        }
        """
        assert run_analysis_expect_success(source)

    def test_nested_structs(self):
        """Test nested struct types."""
        source = """
        Point :: struct {
            x: i32
            y: i32
        }

        Line :: struct {
            start: Point
            end: Point
        }
        """
        assert run_analysis_expect_success(source)


class TestEnumTypes:
    """Test enum type operations."""

    def test_enum_declaration(self):
        """Test enum type declaration."""
        source = """
        Color :: enum {
            Red
            Green
            Blue
        }
        """
        assert run_analysis_expect_success(source)

    def test_enum_with_values(self):
        """Test enum with explicit values."""
        source = """
        ErrorCode :: enum {
            Success = 0
            NotFound = 404
            ServerError = 500
        }
        """
        assert run_analysis_expect_success(source)


class TestUnionTypes:
    """Test union type operations."""

    def test_union_declaration(self):
        """Test union type declaration."""
        source = """
        Value :: union {
            int_val: i32
            float_val: f64
            str_val: string
        }
        """
        assert run_analysis_expect_success(source)


class TestControlFlow:
    """Test control flow statements."""

    def test_if_statement(self):
        """Test if statement."""
        source = """
        main :: fn() {
            x := 5
            if x > 0 {
                y := 1
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_if_else_statement(self):
        """Test if-else statement."""
        source = """
        main :: fn() {
            x := 5
            if x > 0 {
                y := 1
            } else {
                y := -1
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_while_loop(self):
        """Test while loop."""
        source = """
        main :: fn() {
            i := 0
            while i < 10 {
                i = i + 1
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_for_loop(self):
        """Test C-style for loop."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i = i + 1 {
                x := i * 2
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_for_in_loop(self):
        """Test for-in loop."""
        source = """
        main :: fn() {
            arr := [1, 2, 3, 4, 5]
            for x in arr {
                y := x * 2
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_for_in_indexed_loop(self):
        """Test for-in loop with index."""
        source = """
        main :: fn() {
            arr := [1, 2, 3, 4, 5]
            for i, x in arr {
                y := x + i
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_match_statement(self):
        """Test match statement."""
        source = """
        main :: fn() {
            x := 5
            match x {
                case 1: y := 10
                case 2: y := 20
                else: y := 0
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_break_statement(self):
        """Test break in loop."""
        source = """
        main :: fn() {
            while true {
                break
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_continue_statement(self):
        """Test continue in loop."""
        source = """
        main :: fn() {
            while true {
                continue
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_break_outside_loop_error(self):
        """Test that break outside loop is an error."""
        source = """
        main :: fn() {
            break
        }
        """
        assert run_analysis_expect_error(source)

    def test_continue_outside_loop_error(self):
        """Test that continue outside loop is an error."""
        source = """
        main :: fn() {
            continue
        }
        """
        assert run_analysis_expect_error(source)


class TestVariableScoping:
    """Test variable scoping rules."""

    def test_block_scoping(self):
        """Test variables in nested blocks."""
        source = """
        main :: fn() {
            x := 1
            {
                y := 2
                z := x + y
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_variable_shadowing(self):
        """Test variable shadowing (allowed in A7)."""
        source = """
        main :: fn() {
            x := 1
            {
                x := 2
                y := x
            }
        }
        """
        assert run_analysis_expect_success(source)

    def test_function_scope(self):
        """Test function parameter scoping."""
        source = """
        foo :: fn(x: i32) {
            y := x + 1
        }
        """
        assert run_analysis_expect_success(source)


class TestNameCollisions:
    """Test name collision detection."""

    def test_duplicate_function_error(self):
        """Test that duplicate functions are detected."""
        source = """
        foo :: fn() {}
        foo :: fn() {}
        """
        assert run_analysis_expect_error(source)

    def test_duplicate_struct_error(self):
        """Test that duplicate structs are detected."""
        source = """
        Point :: struct { x: i32 }
        Point :: struct { y: i32 }
        """
        assert run_analysis_expect_error(source)

    def test_duplicate_variable_in_scope_error(self):
        """Test that duplicate variables in same scope are detected."""
        source = """
        main :: fn() {
            x := 1
            x := 2
        }
        """
        assert run_analysis_expect_error(source)


class TestMemoryManagement:
    """Test memory management operations."""

    def test_new_expression(self):
        """Test new allocation."""
        source = """
        main :: fn() {
            p := new i32
        }
        """
        assert run_analysis_expect_success(source)

    def test_del_statement(self):
        """Test del deallocation."""
        source = """
        main :: fn() {
            p := new i32
            del p
        }
        """
        assert run_analysis_expect_success(source)

    def test_defer_statement(self):
        """Test defer statement."""
        source = """
        cleanup :: fn() {}

        main :: fn() {
            defer cleanup()
        }
        """
        assert run_analysis_expect_success(source)


class TestTypeInference:
    """Test type inference for := operator."""

    def test_integer_inference(self):
        """Test integer literal inference."""
        source = """
        main :: fn() {
            x := 42
        }
        """
        assert run_analysis_expect_success(source)

    def test_expression_inference(self):
        """Test expression type inference."""
        source = """
        main :: fn() {
            x := 5 + 10
            y := x * 2
        }
        """
        assert run_analysis_expect_success(source)

    def test_function_return_inference(self):
        """Test function return type inference."""
        source = """
        get_value :: fn() i32 {
            ret 42
        }

        main :: fn() {
            x := get_value()
        }
        """
        assert run_analysis_expect_success(source)


class TestCastExpressions:
    """Test type casting."""

    def test_numeric_cast(self):
        """Test numeric type casting."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := cast(i64, x)
        }
        """
        assert run_analysis_expect_success(source)


class TestComplexPrograms:
    """Test complete, realistic programs."""

    def test_fibonacci_function(self):
        """Test iterative fibonacci function."""
        source = """
        fib :: fn(n: i32) i32 {
            if n <= 1 {
                ret n
            }
            prev := 0
            curr := 1
            i := 2
            while i <= n {
                next := prev + curr
                prev = curr
                curr = next
                i += 1
            }
            ret curr
        }

        main :: fn() {
            result := fib(10)
        }
        """
        assert run_analysis_expect_success(source)

    def test_linked_list_operations(self):
        """Test linked list data structure."""
        source = """
        Node :: struct {
            value: i32
            next: ref Node
        }

        create_node :: fn(val: i32) ref Node {
            node := new Node
            node.val.value = val
            node.val.next = nil
            ret node
        }

        main :: fn() {
            head := create_node(1)
        }
        """
        assert run_analysis_expect_success(source)

    def test_calculator(self):
        """Test simple calculator with operators."""
        source = """
        add :: fn(a: i32, b: i32) i32 { ret a + b }
        sub :: fn(a: i32, b: i32) i32 { ret a - b }
        mul :: fn(a: i32, b: i32) i32 { ret a * b }
        div :: fn(a: i32, b: i32) i32 { ret a / b }

        main :: fn() {
            x := 10
            y := 5
            sum := add(x, y)
            diff := sub(x, y)
            prod := mul(x, y)
            quot := div(x, y)
        }
        """
        assert run_analysis_expect_success(source)
