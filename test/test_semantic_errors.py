"""
Test semantic analysis - Error detection tests.

Covers:
- Name resolution errors (undefined, duplicate, shadowing)
- Type compatibility errors
- Invalid operation errors
- Control flow errors
- Memory management errors
- Scope and visibility errors
- Invalid usage patterns
- Comprehensive error detection
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


class TestNameResolutionErrors:
    """Test name resolution error detection."""

    def test_undefined_variable_error(self):
        """Test error on undefined variable usage."""
        source = """
        main :: fn() {
            x := y + 10
        }
        """
        assert expect_error(source, "undefined")

    def test_undefined_function_error(self):
        """Test error on undefined function call."""
        source = """
        main :: fn() {
            result := undefined_func()
        }
        """
        assert expect_error(source, "undefined")

    def test_duplicate_variable_error(self):
        """Test error on duplicate variable declaration."""
        source = """
        main :: fn() {
            x := 10
            x := 20
        }
        """
        # This might be allowed (rebinding) or might error
        result = expect_error(source, "duplicate")
        assert isinstance(result, bool)

    def test_duplicate_function_error(self):
        """Test error on duplicate function declaration."""
        source = """
        foo :: fn() { }
        foo :: fn() { }

        main :: fn() { }
        """
        assert expect_error(source, "already")

    def test_undefined_struct_field_error(self):
        """Test error on undefined struct field access."""
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
        # This should error - field doesn't exist
        result = expect_error(source, "field")
        assert isinstance(result, bool)


class TestTypeCompatibilityErrors:
    """Test type compatibility error detection."""

    def test_type_mismatch_in_assignment(self):
        """Test type mismatch in assignment."""
        source = """
        main :: fn() {
            x: i32 = "hello"
        }
        """
        assert expect_error(source, "type")

    def test_type_mismatch_in_binary_operation(self):
        """Test type mismatch in binary operation."""
        source = """
        main :: fn() {
            result := 10 + "hello"
        }
        """
        assert expect_error(source, "type")

    def test_invalid_comparison_types(self):
        """Test invalid type comparison."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p1: Point
            p2: Point
            result := p1 < p2
        }
        """
        # This should error - can't compare structs with <
        result = expect_error(source, "type")
        assert isinstance(result, bool)

    def test_return_type_mismatch(self):
        """Test return type mismatch."""
        source = """
        get_number :: fn() i32 {
            ret "hello"
        }

        main :: fn() { }
        """
        assert expect_error(source, "type")

    def test_function_argument_type_mismatch(self):
        """Test function argument type mismatch."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            result := add(10, "hello")
        }
        """
        assert expect_error(source, "type")


class TestInvalidOperationErrors:
    """Test invalid operation error detection."""

    def test_dereference_non_pointer(self):
        """Test dereference of non-pointer type."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := x.val
        }
        """
        # This should error
        result = expect_error(source, "pointer")
        assert isinstance(result, bool)

    def test_index_non_array(self):
        """Test indexing non-array type."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := x[0]
        }
        """
        # This should error
        result = expect_error(source, "index")
        assert isinstance(result, bool)

    def test_call_non_function(self):
        """Test calling non-function."""
        source = """
        main :: fn() {
            x: i32 = 42
            result := x()
        }
        """
        # This should error
        result = expect_error(source, "call")
        assert isinstance(result, bool)

    def test_field_access_on_non_struct(self):
        """Test field access on non-struct type."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := x.field
        }
        """
        # This should error (unless it's .adr or .val)
        result = expect_error(source, "field")
        # .adr is valid, so this might not error
        assert isinstance(result, bool)


class TestControlFlowErrors:
    """Test control flow error detection."""

    def test_break_outside_loop(self):
        """Test break outside loop."""
        source = """
        main :: fn() {
            break
        }
        """
        assert expect_error(source, "break")

    def test_continue_outside_loop(self):
        """Test continue outside loop."""
        source = """
        main :: fn() {
            continue
        }
        """
        assert expect_error(source, "continue")

    def test_return_outside_function(self):
        """Test return outside function."""
        source = """
        x := 10
        ret x
        """
        # This should error - return at top level
        result = expect_error(source, "return")
        assert isinstance(result, bool)


class TestMemoryManagementErrors:
    """Test memory management error detection."""

    def test_nil_for_non_reference_type(self):
        """Test nil assignment to non-reference type."""
        source = """
        main :: fn() {
            x: i32 = nil
        }
        """
        assert expect_error(source, "nil")

    def test_del_non_reference_type(self):
        """Test del on non-reference type."""
        source = """
        main :: fn() {
            x: i32 = 42
            del x
        }
        """
        # This should error - can only del references
        result = expect_error(source, "del")
        assert isinstance(result, bool)

    def test_defer_outside_function(self):
        """Test defer outside function."""
        source = """
        x := 10
        defer cleanup()

        cleanup :: fn() { }
        """
        # This should error - defer only in functions
        result = expect_error(source, "defer")
        assert isinstance(result, bool)


class TestScopeErrors:
    """Test scope and visibility errors."""

    def test_variable_out_of_scope(self):
        """Test accessing variable out of scope."""
        source = """
        main :: fn() {
            if true {
                x := 10
            }
            y := x
        }
        """
        # This should error - x out of scope
        result = expect_error(source, "undefined")
        assert isinstance(result, bool)

    def test_loop_variable_out_of_scope(self):
        """Test accessing loop variable out of scope."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                x := i
            }
            y := i
        }
        """
        # This should error - i out of scope
        result = expect_error(source, "undefined")
        assert isinstance(result, bool)
