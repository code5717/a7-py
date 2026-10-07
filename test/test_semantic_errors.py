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



from pipeline_helpers import expect_error, expect_parse_error, pipeline_tmp  # noqa: F401


class TestNameResolutionErrors:
    """Test name resolution error detection."""

    def test_undefined_variable_error(self):
        """Test error on undefined variable usage."""
        source = """
        main :: fn() {
            x := y + 10
        }
        """
        assert expect_error(source, "Undefined identifier: 'y'")

    def test_undefined_function_error(self):
        """Test error on undefined function call."""
        source = """
        main :: fn() {
            result := undefined_func()
        }
        """
        assert expect_error(source, "Undefined identifier: 'undefined_func'")

    def test_duplicate_variable_error(self):
        """Test error on duplicate variable declaration."""
        source = """
        main :: fn() {
            x := 10
            x := 20
        }
        """
        assert expect_error(source, "Already defined: Variable 'x'")

    def test_duplicate_function_error(self):
        """Test error on duplicate function declaration."""
        source = """
        foo :: fn() { }
        foo :: fn() { }

        main :: fn() { }
        """
        assert expect_error(source, "Already defined: Function 'foo'")

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
        assert expect_error(source, "Struct 'Point' has no field 'z'")


class TestTypeCompatibilityErrors:
    """Test type compatibility error detection."""

    def test_type_mismatch_in_assignment(self):
        """Test type mismatch in assignment."""
        source = """
        main :: fn() {
            x: i32 = "hello"
        }
        """
        assert expect_error(source, "Type mismatch: expected 'i32', got 'string'")

    def test_type_mismatch_in_binary_operation(self):
        """Test type mismatch in binary operation."""
        source = """
        main :: fn() {
            result := 10 + "hello"
        }
        """
        assert expect_error(source, "Requires numeric type")

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
        assert expect_error(source, "lt between Point and Point")

    def test_return_type_mismatch(self):
        """Test return type mismatch."""
        source = """
        get_number :: fn() i32 {
            ret "hello"
        }

        main :: fn() { }
        """
        assert expect_error(source, "Return type mismatch: expected 'i32', got 'string'")

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
        assert expect_error(source, "Argument type mismatch: expected 'i32', got 'string'")


class TestInvalidOperationErrors:
    """Test invalid operation error detection."""

    def test_index_non_array(self):
        """Test indexing non-array type."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := x[0]
        }
        """
        assert expect_error(source, "Cannot index this type: got 'i32'")

    def test_call_non_function(self):
        """Test calling non-function."""
        source = """
        main :: fn() {
            x: i32 = 42
            result := x()
        }
        """
        assert expect_error(source, "Type is not callable: got 'i32'")

    def test_field_access_on_non_struct(self):
        """Test field access on non-struct type."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := x.field
        }
        """
        assert expect_error(source, "Cannot access field on non-struct type: got 'i32'")


class TestControlFlowErrors:
    """Test control flow error detection."""

    def test_break_outside_loop(self):
        """Test break outside loop."""
        source = """
        main :: fn() {
            break
        }
        """
        assert expect_error(source, "Break statement outside loop")

    def test_continue_outside_loop(self):
        """Test continue outside loop."""
        source = """
        main :: fn() {
            continue
        }
        """
        assert expect_error(source, "Continue statement outside loop")

    def test_return_outside_function_is_a_parse_error(self):
        """Only declarations may appear at file scope, so the parser rejects `ret`."""
        source = """
        x := 10
        ret x
        """
        assert expect_parse_error(source, "3:9: Expected declaration")


class TestMemoryManagementErrors:
    """Test memory management error detection."""

    def test_nil_for_non_reference_type(self):
        """Test nil assignment to non-reference type."""
        source = """
        main :: fn() {
            x: i32 = nil
        }
        """
        assert expect_error(source, "Nil only allowed for reference types: got 'i32'")

    def test_del_non_reference_type(self):
        """Test del on non-reference type."""
        source = """
        main :: fn() {
            x: i32 = 42
            del x
        }
        """
        assert expect_error(source, "Delete requires a reference type")

    def test_defer_outside_function_is_a_parse_error(self):
        """Only declarations may appear at file scope, so the parser rejects `defer`."""
        source = """
        x := 10
        defer cleanup()

        cleanup :: fn() { }
        """
        assert expect_parse_error(source, "3:9: Expected declaration")


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
        assert expect_error(source, "Undefined identifier: 'x'")

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
        assert expect_error(source, "Undefined identifier: 'i'")
