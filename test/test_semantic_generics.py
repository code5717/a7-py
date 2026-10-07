"""
Test semantic analysis - Generic type tests.

Covers:
- Generic function declarations
- Generic type parameters
- Generic constraints with type sets
- Generic struct/enum/union types
- Generic type instantiation
- Type inference with generics
- Multiple generic parameters
- Nested generic types

NOTE: A7 uses inline generic syntax where $T is embedded directly in type expressions,
not declared as separate parameters. E.g., `fn(x: $T) $T` not `fn($T, x: T) T`.
"""

import pytest
from a7.generics import resolve_generic_constraint
from a7.types import F64, I32, I64, NUMERIC


from conftest import parse_program
from pipeline_helpers import (  # noqa: F401
    expect_error, expect_parse_error, expect_success, pipeline_tmp,
)

class TestGenericConstraintHelpers:
    """Direct coverage for generic constraint helper internals."""

    def test_resolve_predefined_constraint_identifier(self):
        ast = parse_program("Box($T: Numeric) :: struct { value: $T }")
        constraint = ast.declarations[0].generic_params[0].constraint

        resolved = resolve_generic_constraint(constraint)

        assert resolved == NUMERIC

    def test_resolve_inline_type_set_constraint(self):
        ast = parse_program("Box($T: @type_set(i32, i64, f64)) :: struct { value: $T }")
        constraint = ast.declarations[0].generic_params[0].constraint

        resolved = resolve_generic_constraint(constraint)

        assert resolved is not None
        assert resolved.types == frozenset({I32, I64, F64})

    def test_invalid_inline_type_set_member_returns_none(self):
        ast = parse_program("Box($T: @type_set(i32, MissingType)) :: struct { value: $T }")
        constraint = ast.declarations[0].generic_params[0].constraint

        assert resolve_generic_constraint(constraint) is None


class TestGenericFunctions:
    """Test generic function declarations and usage."""

    def test_simple_generic_function(self):
        """Test simple generic function with inline $T syntax."""
        source = """
        identity :: fn(x: $T) $T {
            ret x
        }

        main :: fn() {
            a := identity(42)
            b := identity(3.14)
            c := identity("hello")
        }
        """
        assert expect_success(source)

    def test_return_only_generic_parameter_cannot_be_inferred(self):
        """`$T` that appears only in the return type has no argument to bind it."""
        source = """
        create_default($T) :: fn() $T {
            x: $T
            ret x
        }

        main :: fn() {
            a: i32 = create_default()
        }
        """
        assert expect_error(source, "Could not infer generic parameter '$T'")

    def test_return_only_inline_generic_parameter_cannot_be_inferred(self):
        """The inline form must name the same cause as the declared form."""
        source = """
        create_default :: fn() $T {
            x: $T
            ret x
        }

        main :: fn() {
            a: i32 = create_default()
        }
        """
        assert expect_error(source, "Could not infer generic parameter '$T'")

    def test_generic_swap_function(self):
        """Test generic function with references."""
        source = """
        Box :: struct {
            value: $T
        }

        put($T) :: fn(box: ref Box($T), value: $T) {
            box.value = value
        }

        main :: fn() {
            box := Box(i32){value: 10}
            put(box, 20)
        }
        """
        assert expect_success(source)

    def test_multiple_generic_parameters(self):
        """Test function with multiple generic parameters."""
        source = """
        pair :: fn(first: $T, second: $U) {
            x := first
            y := second
        }

        main :: fn() {
            pair(42, "hello")
            pair(3.14, true)
        }
        """
        assert expect_success(source)


class TestGenericConstraints:
    """Test generic constraints with type sets.

    NOTE: Generic constraints in A7 are a semantic analysis feature.
    The parser accepts $T in type expressions, but constraint checking
    happens during type checking phase.
    """

    def test_predefined_numeric_constraint(self):
        """Test generic with Numeric constraint."""
        source = """
        abs($T: Numeric) :: fn(x: $T) $T {
            ret if x < 0 { -x } else { x }
        }

        main :: fn() {
            a := abs(-42)
            b := abs(-3.14)
        }
        """
        assert expect_success(source)

    def test_inline_type_set_constraint(self):
        """Test generic with inline type set constraint."""
        source = """
        process($T: @type_set(i32, i64)) :: fn(value: $T) $T {
            ret value * 2
        }

        main :: fn() {
            a := process(42)
        }
        """
        assert expect_success(source)

    def test_constraint_violation(self):
        """A float argument violates the predefined Integer constraint."""
        source = """
        process($T: Integer) :: fn(value: $T) $T {
            ret value * 2
        }

        main :: fn() {
            x := process(3.14)
        }
        """
        assert expect_error(
            source,
            "Generic constraint violation: Generic parameter '$T' requires Integer, got f64",
        )

    def test_declared_generic_constraint_allows_matching_type(self):
        """Explicit generic declaration constraints should allow matching arguments."""
        source = """
        IntOnly :: @type_set(i32, i64)

        process($T: IntOnly) :: fn(value: $T) $T {
            ret value
        }

        main :: fn() {
            x := process(42)
        }
        """
        assert expect_success(source)

    def test_declared_generic_constraint_rejects_mismatched_type(self):
        """Explicit generic declaration constraints should reject non-member arguments."""
        source = """
        IntOnly :: @type_set(i32, i64)

        process($T: IntOnly) :: fn(value: $T) $T {
            ret value
        }

        main :: fn() {
            x := process(3.14)
        }
        """
        assert expect_error(
            source,
            "Generic constraint violation: Generic parameter '$T' requires "
            "@type_set(i32, i64), got f64",
        )

    def test_inline_declared_generic_constraint_rejects_mismatched_type(self):
        """Inline type-set constraints should reject non-member arguments."""
        source = """
        process($T: @type_set(i32, i64)) :: fn(value: $T) $T {
            ret value
        }

        main :: fn() {
            x := process(3.14)
        }
        """
        assert expect_error(
            source,
            "Generic constraint violation: Generic parameter '$T' requires "
            "@type_set(i32, i64), got f64",
        )

    def test_multiple_constraints(self):
        """Test multiple generic parameters with different constraints."""
        source = """
        combine($T: Numeric, $U: Integer) :: fn(a: $T, b: $U) $T {
            ret a + a
        }

        main :: fn() {
            result := combine(3.14, %s)
        }
        """
        assert expect_success(source % "42")
        assert expect_error(
            source % "4.5",
            "Generic constraint violation: Generic parameter '$U' requires Integer, got f64",
        )


class TestGenericStructs:
    """Test generic struct declarations.

    NOTE: A7 uses inline generic syntax in structs: `struct { value: $T }`
    not `struct($T) { value: T }`.
    """

    def test_simple_generic_struct(self):
        """Test simple generic struct with inline $T syntax."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            b1: Box(i32)
            b2: Box(string)
        }
        """
        assert expect_success(source)

    def test_generic_struct_initialization(self):
        """Test generic struct initialization."""
        source = """
        Pair :: struct {
            first: $T,
            second: $U,
        }

        main :: fn() {
            p := Pair(i32, string){first: 42, second: "hello"}
        }
        """
        assert expect_success(source)

    def test_generic_struct_initialization_with_explicit_target_type(self):
        """Generic struct literals should retain their concrete instance type."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            b: Box(i32) = Box(i32){value: 42}
        }
        """
        assert expect_success(source)

    def test_generic_struct_initialization_rejects_target_type_arg_mismatch(self):
        """Different generic struct instances should not assign to each other."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            b: Box(string) = Box(i32){value: 42}
        }
        """
        assert expect_error(source, "Type mismatch")

    def test_generic_struct_initialization_rejects_field_type_mismatch(self):
        """Generic struct literal fields are checked after type substitution."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            b: Box(i32) = Box(i32){value: "x"}
        }
        """
        assert expect_error(source, "Field 'value'")

    def test_nested_generic_struct_initialization_with_explicit_target_type(self):
        """Nested generic struct literals should preserve their full instance type."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            b: Box(Box(i32)) = Box(Box(i32)){value: Box(i32){value: 42}}
        }
        """
        assert expect_success(source)

    def test_generic_struct_field_access(self):
        """Test generic struct field access."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            b: Box(i32)
            b.value = 42
            x := b.value
        }
        """
        assert expect_success(source)

    def test_nested_generic_struct(self):
        """Test nested generic struct types."""
        source = """
        Box :: struct {
            value: $T,
        }

        main :: fn() {
            nested: Box(Box(i32))
        }
        """
        assert expect_success(source)


class TestGenericArrays:
    """Test generic functions with arrays."""

    def test_generic_array_parameter(self):
        """Test generic function with array parameter."""
        source = """
        first :: fn(arr: []$T, i: usize, fallback: $T) $T {
            if i < arr.len {
                ret arr[i]
            }
            ret fallback
        }

        main :: fn() {
            numbers: [3]i32 = [1, 2, 3]
            x := first(numbers[0..3], 0, -1)
        }
        """
        assert expect_success(source)

    def test_generic_array_length(self):
        """Test generic function with fixed-size array."""
        source = """
        sum_array :: fn(arr: [5]$T) $T where T: Numeric {
            total: $T = 0
            for x in arr {
                total += x
            }
            ret total
        }

        main :: fn() {
            numbers: [5]i32 = [1, 2, 3, 4, 5]
            result := sum_array(numbers)
        }
        """
        assert expect_success(source)


class TestGenericTypeInference:
    """Test type inference with generics."""

    def test_infer_from_argument(self):
        """Test inferring generic type from argument."""
        source = """
        identity :: fn(x: $T) $T {
            ret x
        }

        main :: fn() {
            a := identity(42)
        }
        """
        assert expect_success(source)

    def test_infer_multiple_parameters(self):
        """Test inferring multiple generic types."""
        source = """
        pair :: fn(first: $T, second: $U) {
            x := first
            y := second
        }

        main :: fn() {
            pair(42, "hello")
        }
        """
        assert expect_success(source)

    def test_type_mismatch_in_generic_call(self):
        """Test type mismatch in generic function call."""
        source = """
        same_type :: fn(a: $T, b: $T) $T {
            ret a
        }

        main :: fn() {
            x := same_type(42, "hello")
        }
        """
        assert expect_error(source, "Conflicting types for $T: string vs i32")


class TestGenericEnumsUnions:
    """Test generic enums and unions."""

    def test_generic_enum_payload_is_a_parse_error(self):
        """Generic enums are out of scope (SPEC 7.2): a variant takes no payload type."""
        source = """
        Option :: enum {
            Some: $T,
            None,
        }

        main :: fn() {
            opt: Option(i32) = Option(i32).None
        }
        """
        assert expect_parse_error(
            source,
            "3:17: Expected ',' or a newline between items in enum variants, found ':'",
        )

    def test_generic_union(self):
        """Test generic union declaration with inline $T syntax."""
        source = """
        Result :: union {
            ok: $T,
            err: $E,
        }

        main :: fn() {
            res: Result(i32, string)
        }
        """
        assert expect_success(source)


class TestComplexGenerics:
    """Test complex generic scenarios."""

    def test_generic_function_returning_generic_struct(self):
        """Test generic function returning generic struct."""
        source = """
        Pair :: struct {
            first: $T,
            second: $U,
        }

        make_pair :: fn(a: $T, b: $U) Pair($T, $U) {
            ret Pair($T, $U){first: a, second: b}
        }

        main :: fn() {
            p := make_pair(42, "hello")
        }
        """
        assert expect_success(source)

    def test_recursive_generic_type(self):
        """Test recursive generic type."""
        source = """
        Node :: struct {
            value: $T,
            next: ref Node($T),
        }

        main :: fn() {
            n: Node(i32)
            n.value = 42
        }
        """
        assert expect_success(source)

    def test_generic_with_function_type(self):
        """Test generic with function type parameter."""
        source = """
        apply($T, $U) :: fn(f: fn($T) $U, x: $T) $U {
            ret f(x)
        }

        double :: fn(x: i32) i32 {
            ret x * 2
        }

        main :: fn() {
            result := apply(double, 21)
        }
        """
        assert expect_success(source)
