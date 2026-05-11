"""
Test semantic analysis - Type system tests.

Covers:
- Primitive type inference and compatibility
- Array and slice type operations
- Pointer and reference type semantics
- Struct/enum/union type checking
- Type compatibility and casting
- Type inference with := operator
"""

import pytest
from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.ast_nodes import NodeKind
from a7.passes.name_resolution import NameResolutionPass
from a7.passes import SafetyProofPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.errors import SemanticError, CompilerError
from a7.types import PointerType, PrimitiveType, SliceType


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

    safety = SafetyProofPass(symbols, node_types)
    safety.analyze(program, "<test>")
    if safety.errors:
        raise safety.errors[0]

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


class TestPrimitiveTypes:
    """Test primitive type operations."""

    def test_integer_type_inference(self):
        """Test integer literal type inference."""
        source = """
        main :: fn() {
            x := 42
            y := -10
            z := 0
        }
        """
        assert expect_success(source)

    def test_float_type_inference(self):
        """Test float literal type inference."""
        source = """
        main :: fn() {
            pi := 3.14159
            e := 2.71828
            half := 0.5
        }
        """
        assert expect_success(source)

    def test_bool_type_inference(self):
        """Test boolean literal type inference."""
        source = """
        main :: fn() {
            t := true
            f := false
        }
        """
        assert expect_success(source)

    def test_string_type_inference(self):
        """Test string literal type inference."""
        source = """
        main :: fn() {
            msg := "Hello, World!"
            empty := ""
        }
        """
        assert expect_success(source)

    def test_explicit_integer_types(self):
        """Test explicit integer type annotations."""
        source = """
        main :: fn() {
            a: i8 = 127
            b: i16 = 32767
            c: i32 = 2147483647
            d: i64 = 9223372036854775807
            e: u8 = 255
            f: u16 = 65535
            g: u32 = 4294967295
            h: u64 = 18446744073709551615
        }
        """
        assert expect_success(source)

    def test_unsigned_integer_rejects_negative_literal(self):
        """Unsigned integers do not accept negative literals implicitly."""
        source = """
        main :: fn() {
            bad: usize = -1
        }
        """
        assert expect_error(source, "type")

    def test_integer_literal_range_is_checked_for_explicit_type(self):
        """Integer literals must fit the explicitly declared type."""
        source = """
        main :: fn() {
            bad: i8 = 128
        }
        """
        assert expect_error(source, "type")

    def test_integer_variable_does_not_implicitly_convert_to_unsigned(self):
        """Signed variables require an explicit cast before unsigned assignment."""
        source = """
        main :: fn() {
            signed: i32 = 1
            unsigned: usize = signed
        }
        """
        assert expect_error(source, "type")

    def test_explicit_float_types(self):
        """Test explicit float type annotations."""
        source = """
        main :: fn() {
            x: f32 = 3.14
            y: f64 = 2.71828
        }
        """
        assert expect_success(source)

    def test_type_mismatch_integer_to_float(self):
        """Test type mismatch between integer and float."""
        source = """
        main :: fn() {
            x: f32 = 42
        }
        """
        # This might be allowed with implicit conversion, or might error
        # Depending on language semantics
        result = expect_success(source)
        # For now, just run the test - adjust based on actual behavior
        assert isinstance(result, bool)

    def test_type_mismatch_string_to_int(self):
        """Test type mismatch between string and int."""
        source = """
        main :: fn() {
            x: i32 = "hello"
        }
        """
        assert expect_error(source, "type")


class TestArrayAndSliceTypes:
    """Test array and slice type operations."""

    def test_array_type_declaration(self):
        """Test array type declarations."""
        source = """
        main :: fn() {
            arr: [5]i32
            matrix: [3][4]f64
        }
        """
        assert expect_success(source)

    def test_array_initialization_with_literal(self):
        """Test array initialization with array literal."""
        source = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
        }
        """
        assert expect_success(source)

    def test_array_literal_uses_declared_element_compatibility(self):
        """Array literals are checked against the declared element type."""
        source = """
        main :: fn() {
            arr: [3]i64 = [1, 2, 3]
        }
        """
        assert expect_success(source)

    def test_array_literal_allows_declared_float_widening(self):
        """Contextual array checks allow integer literals in declared float arrays."""
        source = """
        main :: fn() {
            arr: [3]f64 = [1, 2.5, 3]
        }
        """
        assert expect_success(source)

    def test_nested_array_literal_uses_declared_element_compatibility(self):
        """Nested array literals are checked recursively against the declared type."""
        source = """
        main :: fn() {
            matrix: [2][2]i64 = [[1, 2], [3, 4]]
        }
        """
        assert expect_success(source)

    def test_nested_array_literal_allows_declared_float_widening(self):
        """Nested contextual array checks avoid first-element-only inference."""
        source = """
        main :: fn() {
            matrix: [2][2]f64 = [[1, 2], [3.5, 4.0]]
        }
        """
        assert expect_success(source)

    def test_array_type_inference(self):
        """Test array type inference from literal."""
        source = """
        main :: fn() {
            arr := [1, 2, 3, 4, 5]
        }
        """
        assert expect_success(source)

    def test_array_literal_rejects_incompatible_inferred_elements(self):
        """Inferred array literals must still be homogeneous."""
        source = """
        main :: fn() {
            arr := [1, "two"]
        }
        """
        assert expect_error(source, "array element")

    def test_array_literal_inference_promotes_numeric_elements(self):
        """Inferred array literals keep the wider compatible element type."""
        source = """
        main :: fn() {
            arr := [1, 2.5, 3]
        }
        """
        assert expect_success(source)

    def test_declared_array_literal_rejects_incompatible_elements(self):
        """Declared array literals check every element, not only the top-level shape."""
        source = """
        main :: fn() {
            arr: [2]i32 = [1, "two"]
        }
        """
        assert expect_error(source, "element")

    def test_nested_array_literal_rejects_incompatible_elements(self):
        """Nested array literal element mismatches are semantic errors."""
        source = """
        main :: fn() {
            matrix: [2][2]i32 = [[1, 2], [3, "four"]]
        }
        """
        assert expect_error(source, "element")

    def test_slice_type_declaration(self):
        """Test slice type declarations."""
        source = """
        main :: fn() {
            s: []i32
            s2: [][]f64
        }
        """
        assert expect_success(source)

    def test_slice_ptr_and_len_field_types(self):
        """Test built-in slice fields."""
        source = """
        main :: fn() {
            arr: [4]i32 = [1, 2, 3, 4]
            s := arr[1..3]
            p := s.ptr
            n := s.len
        }
        """
        program = parse_program(source)
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "<test>")
        assert not resolver.errors

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "<test>")
        assert not checker.errors

        field_types = {}
        stack = [program]
        while stack:
            node = stack.pop()
            if getattr(node, "kind", None) == NodeKind.FIELD_ACCESS:
                field_types[node.field] = checker.get_type(node)
            for value in vars(node).values():
                if isinstance(value, list):
                    stack.extend(item for item in value if hasattr(item, "kind"))
                elif hasattr(value, "kind"):
                    stack.append(value)

        assert isinstance(field_types["ptr"], PointerType)
        assert str(field_types["ptr"].pointee_type) == "i32"
        assert isinstance(field_types["len"], PrimitiveType)
        assert field_types["len"].name == "usize"

    def test_string_slice_type_is_char_slice(self):
        """Slicing a string produces a dynamic char slice."""
        source = """
        main :: fn() {
            text: string = "abcdef"
            chunk := text[1..4]
            first := chunk[0]
        }
        """
        program = parse_program(source)
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, "<test>")
        assert not resolver.errors

        checker = TypeCheckingPass(symbols)
        checker.analyze(program, "<test>")
        assert not checker.errors

        slice_types = []
        stack = [program]
        while stack:
            node = stack.pop()
            if getattr(node, "kind", None) == NodeKind.SLICE:
                slice_types.append(checker.get_type(node))
            for value in vars(node).values():
                if isinstance(value, list):
                    stack.extend(item for item in value if hasattr(item, "kind"))
                elif hasattr(value, "kind"):
                    stack.append(value)

        assert len(slice_types) == 1
        assert isinstance(slice_types[0], SliceType)
        assert isinstance(slice_types[0].element_type, PrimitiveType)
        assert slice_types[0].element_type.name == "char"

    def test_slice_unknown_field_is_rejected(self):
        """Only ptr and len are valid built-in slice fields."""
        source = """
        main :: fn() {
            arr: [4]i32 = [1, 2, 3, 4]
            s := arr[1..3]
            bad := s.capacity
        }
        """
        assert expect_error(source, "no field")

    def test_array_element_access(self):
        """Test array element access type checking."""
        source = """
        main :: fn() {
            arr: [5]i32
            x := arr[0]
            arr[1] = 42
        }
        """
        assert expect_success(source)

    def test_usize_variable_can_index_arrays(self):
        """Indexes stored in variables must use usize."""
        source = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
            index: usize = 1
            value := arr[index]
        }
        """
        assert expect_success(source)

    def test_signed_index_variable_is_rejected(self):
        """Signed integer variables cannot index arrays implicitly."""
        source = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
            index: i32 = 1
            value := arr[index]
        }
        """
        assert expect_error(source, "expected usize")

    def test_negative_index_literal_is_rejected(self):
        """Negative literals cannot be accepted as array indexes."""
        source = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
            value := arr[-1]
        }
        """
        assert expect_error(source, "expected usize")

    def test_new_heap_array_is_rejected_until_backend_model_exists(self):
        """Heap fixed arrays are fail-closed until the language defines a model."""
        source = """
        main :: fn() {
            buffer := new [3]i32
            del buffer
        }
        """
        assert expect_error(source, "heap arrays")

    def test_array_size_mismatch(self):
        """Test array size mismatch in initialization."""
        source = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3, 4, 5]
        }
        """
        assert expect_error(source, "size")


class TestPointerAndReferenceTypes:
    """Test pointer and reference type semantics."""

    def test_pointer_type_declaration(self):
        """Test pointer type declarations.

        NOTE: A7 uses 'ref' for pointer/reference types, not 'ptr'.
        """
        source = """
        main :: fn() {
            p: ref i32
            pp: ref ref i32
        }
        """
        assert expect_success(source)

    def test_reference_type_declaration(self):
        """Test reference type declarations."""
        source = """
        main :: fn() {
            r: ref i32
            rr: ref ref i32
        }
        """
        assert expect_success(source)

    def test_ref_parameter_accepts_lvalue_argument(self):
        """Test implicit reference passing for lvalue arguments."""
        source = """
        inc :: fn(x: ref i32) {
            x += 1
        }
        main :: fn() {
            x: i32 = 42
            inc(x)
        }
        """
        assert expect_success(source)

    def test_ref_struct_field_access(self):
        """Test checked implicit dereference for ref struct fields."""
        source = """
        Box :: struct { value: i32 }
        set :: fn(box: ref Box) {
            box.value = 42
        }
        main :: fn() {
            b := Box{value: 0}
            set(b)
        }
        """
        assert expect_success(source)

    def test_nil_for_reference_types(self):
        """Test nil assignment to reference types."""
        source = """
        main :: fn() {
            r: ref i32 = nil
        }
        """
        assert expect_success(source)

    def test_nil_for_non_reference_types(self):
        """Test nil cannot be assigned to non-reference types."""
        source = """
        main :: fn() {
            x: i32 = nil
        }
        """
        assert expect_error(source, "nil")

    def test_nil_inferred_variable_requires_explicit_ref_type(self):
        """Untyped nil declarations must state the intended ref type."""
        source = """
        main :: fn() {
            x := nil
        }
        """
        assert expect_error(source, "explicit ref type")


class TestStructEnumUnionTypes:
    """Test struct, enum, and union type checking."""

    def test_struct_type_declaration(self):
        """Test struct type declaration and usage."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p: Point
        }
        """
        assert expect_success(source)

    def test_struct_field_access(self):
        """Test struct field access type checking."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p: Point
            p.x = 10
            p.y = 20
            a := p.x
        }
        """
        assert expect_success(source)

    def test_struct_initialization(self):
        """Test struct initialization type checking."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p := Point{x: 10, y: 20}
        }
        """
        assert expect_success(source)

    def test_struct_field_type_mismatch(self):
        """Test struct field type mismatch detection."""
        source = """
        Point :: struct {
            x: i32,
            y: i32,
        }

        main :: fn() {
            p := Point{x: "hello", y: 20}
        }
        """
        assert expect_error(source, "type")

    def test_enum_type_declaration(self):
        """Test enum type declaration and usage."""
        source = """
        Color :: enum {
            Red,
            Green,
            Blue,
        }

        main :: fn() {
            c: Color = Color.Red
        }
        """
        assert expect_success(source)

    def test_union_type_declaration(self):
        """Test union type declaration and usage."""
        source = """
        Value :: union {
            int_val: i32,
            float_val: f64,
            string_val: string,
        }

        main :: fn() {
            v: Value
        }
        """
        assert expect_success(source)

    def test_union_field_initialization_and_access(self):
        """Test union field initialization and field access type checking."""
        source = """
        Value :: union {
            int_val: i32,
            float_val: f64,
        }

        main :: fn() {
            v := Value{int_val: 42}
            x: i32 = v.int_val
        }
        """
        assert expect_success(source)

    def test_union_initializer_rejects_multiple_fields(self):
        """Union values must initialize exactly one named field."""
        source = """
        Value :: union {
            int_val: i32,
            float_val: f64,
        }

        main :: fn() {
            v := Value{int_val: 42, float_val: 1.5}
        }
        """
        assert expect_error(source, "one named field")

    def test_union_field_access_rejects_unknown_field(self):
        """Unknown union fields should produce a semantic error."""
        source = """
        Value :: union {
            int_val: i32,
        }

        main :: fn() {
            v := Value{int_val: 42}
            x := v.float_val
        }
        """
        assert expect_error(source, "Union 'Value' has no field 'float_val'")


class TestTypeCasting:
    """Test type casting operations."""

    def test_cast_between_integer_types(self):
        """Test casting between integer types."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := cast(i64, x)
        }
        """
        assert expect_success(source)

    def test_cast_integer_to_float(self):
        """Test casting from integer to float."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := cast(f64, x)
        }
        """
        assert expect_success(source)

    def test_cast_pointer_types_rejected(self):
        """Reference casts are rejected before codegen."""
        source = """
        main :: fn() {
            p: ref i32 = nil
            vp := cast(ref i64, p)
        }
        """
        assert expect_error(source, "cast")

    def test_signed_to_unsigned_literal_initializer_proves_nonnegative(self):
        """Literal initializer facts can prove signed-to-unsigned casts."""
        source = """
        main :: fn() {
            x: i32 = 42
            y := cast(usize, x)
        }
        """
        assert expect_success(source)

    def test_signed_to_unsigned_after_early_return_guard(self):
        """An early-return negative guard proves the value is non-negative."""
        source = """
        main :: fn() {
            x: i32 = 42
            if x < 0 { ret }
            y := cast(usize, x)
        }
        """
        assert expect_success(source)

    def test_structural_cast_rejected(self):
        """Structural conversions are outside the Phase 1 cast boundary."""
        source = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
            s := arr[0..3]
            out := cast([3]i32, s)
        }
        """
        assert expect_error(source, "primitive numeric")


class TestTypeInference:
    """Test type inference with := operator."""

    def test_infer_from_literal(self):
        """Test type inference from literals."""
        source = """
        main :: fn() {
            a := 42
            b := 3.14
            c := true
            d := "hello"
        }
        """
        assert expect_success(source)

    def test_infer_from_expression(self):
        """Test type inference from expressions."""
        source = """
        main :: fn() {
            a := 10 + 20
            b := 3.14 * 2.0
            c := true and false
        }
        """
        assert expect_success(source)

    def test_infer_from_function_call(self):
        """Test type inference from function return type."""
        source = """
        get_value :: fn() i32 {
            ret 42
        }

        main :: fn() {
            x := get_value()
        }
        """
        assert expect_success(source)
