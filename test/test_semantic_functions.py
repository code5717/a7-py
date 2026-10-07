"""
Test semantic analysis - Function tests.

Covers:
- Function declarations and signatures
- Parameter type checking
- Return type validation
- Function call argument matching
- Return statement validation
- Variadic functions
- Recursion rejection
- Function pointers and higher-order functions
"""

import pytest


from pipeline_helpers import expect_error, expect_success, pipeline_tmp  # noqa: F401


class TestBasicFunctions:
    """Test basic function declarations and calls."""

    def test_simple_function_declaration(self):
        """Test simple function declaration."""
        source = """
        greet :: fn() {
            x := 42
        }

        main :: fn() {
            greet()
        }
        """
        assert expect_success(source)

    def test_function_with_parameters(self):
        """Test function with parameters."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            result := add(10, 20)
        }
        """
        assert expect_success(source)

    def test_function_with_return_type(self):
        """Test function with return type."""
        source = """
        get_value :: fn() i32 {
            ret 42
        }

        main :: fn() {
            x := get_value()
        }
        """
        assert expect_success(source)

    def test_void_function(self):
        """Test void function (no return type)."""
        source = """
        do_something :: fn() {
            x := 10
        }

        main :: fn() {
            do_something()
        }
        """
        assert expect_success(source)


class TestFunctionParameters:
    """Test function parameter validation."""

    def test_multiple_parameters(self):
        """Test function with multiple parameters."""
        source = """
        calculate :: fn(a: i32, b: i32, c: i32) i32 {
            ret a + b * c
        }

        main :: fn() {
            result := calculate(10, 20, 30)
        }
        """
        assert expect_success(source)

    def test_parameter_type_mismatch(self):
        """Test function call with wrong parameter type."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            result := add(10, "hello")
        }
        """
        assert expect_error(source, "Argument type mismatch: expected 'i32', got 'string'")

    def test_wrong_argument_count_too_few(self):
        """Test function call with too few arguments."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            result := add(10)
        }
        """
        assert expect_error(source, "Expected 2 arguments, got 1")

    def test_wrong_argument_count_too_many(self):
        """Test function call with too many arguments."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            result := add(10, 20, 30)
        }
        """
        assert expect_error(source, "Expected 2 arguments, got 3")

    def test_reference_parameters(self):
        """Test function with reference parameters."""
        source = """
        increment :: fn(x: ref i32) {
            x += 1
        }

        main :: fn() {
            value: i32 = 10
            increment(value)
        }
        """
        assert expect_success(source)


class TestReturnStatements:
    """Test return statement validation."""

    def test_return_with_value(self):
        """Test return statement with value."""
        source = """
        get_number :: fn() i32 {
            ret 42
        }

        main :: fn() {
            x := get_number()
        }
        """
        assert expect_success(source)

    def test_return_without_value_in_void_function(self):
        """Test return without value in void function."""
        source = """
        do_work :: fn() {
            x := 10
            ret
        }

        main :: fn() {
            do_work()
        }
        """
        assert expect_success(source)

    def test_return_type_mismatch(self):
        """Test return statement with wrong type."""
        source = """
        get_number :: fn() i32 {
            ret "hello"
        }

        main :: fn() {
            x := get_number()
        }
        """
        assert expect_error(source, "Return type mismatch: expected 'i32', got 'string'")

    def test_return_in_void_function_with_value(self):
        """Test return with value in void function."""
        source = """
        do_work :: fn() {
            ret 42
        }

        main :: fn() {
            do_work()
        }
        """
        assert expect_error(source, "Cannot return value from void function")

    def test_multiple_return_paths(self):
        """Test function with multiple return paths."""
        source = """
        abs :: fn(x: i32) i32 {
            if x < 0 {
                ret -x
            }
            ret x
        }

        main :: fn() {
            y := abs(-10)
        }
        """
        assert expect_success(source)


class TestVariadicFunctions:
    """Test variadic function support."""

    def test_variadic_function_typed(self):
        """Typed variadic functions are parsed but fail closed before codegen."""
        source = """
        sum :: fn(values: ..i32) i32 {
            total: i32 = 0
            ret total
        }

        main :: fn() {
            result := sum(1, 2, 3, 4, 5)
        }
        """
        assert expect_error(source, "Variadic parameters")

    def test_variadic_function_untyped(self):
        """Untyped variadic functions are parsed but fail closed before codegen."""
        source = """
        print_args :: fn(args: ..) {
            x := 42
        }

        main :: fn() {
            print_args(1, "hello", 3.14, true)
        }
        """
        assert expect_error(source, "Variadic parameters")

    def test_variadic_with_regular_params(self):
        """Variadic functions with regular params are parsed but unsupported."""
        source = """
        printf :: fn(format: string, args: ..) {
            x := 42
        }

        main :: fn() {
            printf("Value: %d", 42)
        }
        """
        assert expect_error(source, "Variadic parameters")


class TestRecursionBan:
    """Test that recursive function cycles are rejected."""

    def test_direct_recursion_is_rejected(self):
        """Test direct self-recursive functions."""
        source = """
        factorial :: fn(n: i32) i32 {
            if n <= 1 {
                ret 1
            }
            ret n * factorial(n - 1)
        }

        main :: fn() {
            result := factorial(5)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: factorial -> factorial")

    def test_mutual_recursion_is_rejected(self):
        """Test mutually recursive function cycles."""
        source = """
        is_even :: fn(n: i32) bool {
            if n == 0 {
                ret true
            }
            ret is_odd(n - 1)
        }

        is_odd :: fn(n: i32) bool {
            if n == 0 {
                ret false
            }
            ret is_even(n - 1)
        }

        main :: fn() {
            x := is_even(10)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: is_even -> is_odd -> is_even")

    def test_iterative_rewrite_is_allowed(self):
        """Test the allowed iterative equivalent."""
        source = """
        factorial :: fn(n: i32) i32 {
            result := 1
            for i := 2; i <= n; i += 1 {
                result *= i
            }
            ret result
        }

        main :: fn() {
            result := factorial(5)
        }
        """
        assert expect_success(source)

    def test_local_function_pointer_shadow_does_not_look_recursive(self):
        """A local function pointer can shadow a top-level function name."""
        source = """
        bar :: fn(x: i32) i32 {
            ret x * 2
        }

        foo :: fn(x: i32) i32 {
            foo: fn(i32) i32 = bar
            ret foo(x)
        }

        main :: fn() {
            result := foo(5)
        }
        """
        assert expect_success(source)

    def test_function_pointer_alias_recursion_is_rejected(self):
        """A function cannot recurse through a local function pointer alias."""
        source = """
        countdown :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            again := countdown
            ret again(n - 1)
        }

        main :: fn() {
            result := countdown(3)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: countdown -> countdown")

    def test_mutual_function_pointer_alias_recursion_is_rejected(self):
        """Mutual recursion through aliases is still a recursion cycle."""
        source = """
        left :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            next := right
            ret next(n - 1)
        }

        right :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            next := left
            ret next(n - 1)
        }

        main :: fn() {
            result := left(3)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: left -> right -> left")

    def test_higher_order_self_recursion_is_rejected(self):
        """A callback trampoline cannot hide direct recursion."""
        source = """
        call_it :: fn(f: fn(i32) i32, n: i32) i32 {
            ret f(n)
        }

        countdown :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            ret call_it(countdown, n - 1)
        }

        main :: fn() {
            result := countdown(3)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: countdown -> countdown")

    def test_higher_order_mutual_recursion_is_rejected(self):
        """Mutual recursion through callback parameters is rejected."""
        source = """
        call_it :: fn(f: fn(i32) i32, n: i32) i32 {
            ret f(n)
        }

        left :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            ret call_it(right, n - 1)
        }

        right :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            ret call_it(left, n - 1)
        }

        main :: fn() {
            result := left(3)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: left -> right -> left")

    def test_higher_order_parameter_alias_recursion_is_rejected(self):
        """A trampoline that aliases a callback parameter is still visible."""
        source = """
        call_it :: fn(f: fn(i32) i32, n: i32) i32 {
            next := f
            ret next(n)
        }

        countdown :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            ret call_it(countdown, n - 1)
        }

        main :: fn() {
            result := countdown(3)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: countdown -> countdown")

    def test_forwarded_higher_order_recursion_is_rejected(self):
        """A callback passed through another callback cannot hide recursion."""
        source = """
        Runner :: fn(fn(i32) i32, i32) i32

        run :: fn(user: Runner, op: fn(i32) i32, n: i32) i32 {
            ret user(op, n)
        }

        apply :: fn(op: fn(i32) i32, n: i32) i32 {
            ret op(n)
        }

        countdown :: fn(n: i32) i32 {
            if n <= 0 {
                ret 0
            }
            ret run(apply, countdown, n - 1)
        }

        main :: fn() {
            result := countdown(3)
        }
        """
        assert expect_error(source, "Recursion is not allowed: Cycle: countdown -> countdown")


class TestFunctionPointers:
    """Test function pointer and higher-order function support."""

    def test_function_pointer_type(self):
        """Test function pointer type declaration."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            op: fn(i32, i32) i32 = add
            result := op(10, 20)
        }
        """
        assert expect_success(source)

    def test_function_as_parameter(self):
        """Test passing function as parameter."""
        source = """
        apply :: fn(f: fn(i32) i32, x: i32) i32 {
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

    def test_function_type_alias(self):
        """Test top-level function type aliases."""
        source = """
        BinaryOp :: fn(i32, i32) i32

        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        apply :: fn(op: BinaryOp, a: i32, b: i32) i32 {
            ret op(a, b)
        }

        main :: fn() {
            op: BinaryOp = add
            result := apply(op, 10, 20)
        }
        """
        assert expect_success(source)

    def test_function_type_alias_forward_reference(self):
        """Test function type aliases that reference later aliases."""
        source = """
        OperationUser :: fn(BinaryOp) i32
        BinaryOp :: fn(i32, i32) i32

        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        run :: fn(user: OperationUser, op: BinaryOp) i32 {
            ret user(op)
        }

        apply :: fn(op: BinaryOp) i32 {
            ret op(10, 20)
        }

        main :: fn() {
            op: BinaryOp = add
            result := run(apply, op)
        }
        """
        assert expect_success(source)

    def test_type_alias_cycle_is_rejected(self):
        """Test circular type aliases fail closed."""
        source = """
        A :: fn(A) void

        main :: fn() {
            value: A = nil
        }
        """
        assert expect_error(source, "circular type alias")

    def test_constants_are_not_usable_as_type_aliases(self):
        """Test constants do not masquerade as type names."""
        source = """
        Size :: 1

        main :: fn() {
            value: Size = 1
        }
        """
        assert expect_error(source, "Undefined type (Type 'Size')")

    def test_local_function_type_alias(self):
        """Test function type aliases declared inside blocks."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        main :: fn() {
            BinaryOp :: fn(i32, i32) i32
            op: BinaryOp = add
            result := op(10, 20)
        }
        """
        assert expect_success(source)

    def test_function_returning_function(self):
        """Test function returning function pointer."""
        source = """
        add :: fn(a: i32, b: i32) i32 {
            ret a + b
        }

        get_adder :: fn() fn(i32, i32) i32 {
            ret add
        }

        main :: fn() {
            adder := get_adder()
            result := adder(10, 20)
        }
        """
        assert expect_success(source)

    def test_function_returning_nested_function(self):
        """A function declared inside another can be returned by name."""
        source = """
        get_adder :: fn() fn(i32, i32) i32 {
            add :: fn(a: i32, b: i32) i32 {
                ret a + b
            }
            ret add
        }

        main :: fn() {
            adder := get_adder()
            result := adder(10, 20)
        }
        """
        assert expect_success(source)
