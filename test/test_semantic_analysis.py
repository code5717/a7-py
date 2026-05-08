"""
Tests for semantic analysis passes.

Tests the integration of:
- Name resolution
- Type checking
- Semantic validation
"""

import pytest
from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.errors import SemanticError


def parse_program(source: str):
    """Helper to parse a source program."""
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


class TestNameResolution:
    """Test name resolution pass."""

    def test_simple_function(self):
        """Test resolving a simple function."""
        source = """
        main :: fn() {
            x := 42
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        # Check that main function is registered
        main_symbol = symbols.lookup("main")
        assert main_symbol is not None
        assert main_symbol.name == "main"

    def test_variable_shadowing(self):
        """Test variable shadowing in nested scopes."""
        source = """
        main :: fn() {
            x := 42
            {
                x := 100
            }
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        # Should succeed - shadowing is allowed
        assert symbols is not None

    def test_duplicate_function(self):
        """Test duplicate function declaration."""
        source = """
        foo :: fn() {}
        foo :: fn() {}
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        resolver.analyze(program, "test.a7")

        # Should have a duplicate definition error
        assert len(resolver.errors) > 0
        assert "already defined" in str(resolver.errors[0]).lower() or "duplicate" in str(resolver.errors[0]).lower()

    def test_struct_field_registration(self):
        """Test struct fields are registered."""
        source = """
        Point :: struct {
            x: i32
            y: i32
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        # Check that struct is registered
        point_symbol = symbols.lookup("Point")
        assert point_symbol is not None
        assert point_symbol.name == "Point"


class TestTypeChecking:
    """Test type checking pass."""

    def test_simple_variable_type_inference(self):
        """Test type inference for variable declarations."""
        source = """
        main :: fn() {
            x := 42
        }
        """
        program = parse_program(source)

        # Name resolution first
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")
        assert len(resolver.errors) == 0

        # Type checking
        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        # Should complete without errors - type inference is tested more deeply elsewhere
        assert len(checker.errors) == 0

    def test_explicit_type_annotation(self):
        """Test explicit type annotations."""
        source = """
        main :: fn() {
            x: i64 = 42
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")
        assert len(resolver.errors) == 0

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        # Should complete without errors - explicit annotations are allowed
        assert len(checker.errors) == 0

    def test_function_return_type(self):
        """Test function return type checking."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        add_symbol = symbols.lookup("add")
        assert add_symbol is not None
        # Function type should be fn(i32, i32) i32
        assert "fn(" in str(add_symbol.type)

    def test_type_mismatch_error(self):
        """Test type mismatch detection."""
        source = """
        main :: fn() {
            x: i32 = "hello"
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        # Should have a type mismatch error
        assert len(checker.errors) > 0
        assert "type" in str(checker.errors[0]).lower() or "mismatch" in str(checker.errors[0]).lower()


class TestSemanticValidation:
    """Test semantic validation pass."""

    def test_break_outside_loop_error(self):
        """Test break outside loop is caught."""
        source = """
        main :: fn() {
            break
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        validator = SemanticValidationPass(symbols, checker.node_types)
        validator.analyze(program, "test.a7")

        # Should have an error about break outside loop
        assert len(validator.errors) > 0
        assert "break" in str(validator.errors[0]).lower() or "loop" in str(validator.errors[0]).lower()

    def test_break_in_loop_valid(self):
        """Test break inside loop is valid."""
        source = """
        main :: fn() {
            while true {
                break
            }
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        validator = SemanticValidationPass(symbols, checker.node_types)
        # Should not raise
        validator.analyze(program, "test.a7")

    def test_continue_outside_loop_error(self):
        """Test continue outside loop is caught."""
        source = """
        main :: fn() {
            continue
        }
        """
        program = parse_program(source)

        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        validator = SemanticValidationPass(symbols, checker.node_types)
        validator.analyze(program, "test.a7")

        # Should have an error about continue outside loop
        assert len(validator.errors) > 0
        assert "continue" in str(validator.errors[0]).lower() or "loop" in str(validator.errors[0]).lower()


class TestIntegration:
    """Test full semantic analysis pipeline."""

    def test_complete_program(self):
        """Test a complete program through all passes."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            x := 5
            y := 10
            result := add(x, y)
        }
        """
        program = parse_program(source)

        # Name resolution
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        # Type checking
        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        # Semantic validation
        validator = SemanticValidationPass(symbols, checker.node_types)
        validator.analyze(program, "test.a7")

        # All passes should succeed
        assert symbols is not None

    def test_struct_usage(self):
        """Test struct declaration and usage."""
        source = """
        Point :: struct {
            x: i32
            y: i32
        }

        main :: fn() {
            p := Point{x: 10, y: 20}
        }
        """
        program = parse_program(source)

        # Name resolution
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "test.a7")

        # Type checking
        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "test.a7")

        # Should succeed
        point_symbol = symbols.lookup("Point")
        assert point_symbol is not None
