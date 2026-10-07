"""
Tests for the A7 standard library registry.

Validates StdlibRegistry initialization, module/function resolution,
backend mapping, and I/O call detection. The registry has no bare typed
builtin names (such as sqrt_f64); test/test_stdlib_call_resolution.py checks
that a user function with such a name runs as written.
"""

import pytest
from a7.stdlib import StdlibRegistry, StdlibFunction, StdlibModule


class TestStdlibRegistryInitialization:
    """Test that StdlibRegistry initializes with the expected default modules."""

    def test_io_module_registered(self):
        """The io module should be registered on initialization."""
        registry = StdlibRegistry()
        assert "io" in registry.modules

    def test_math_module_registered(self):
        """The math module should be registered on initialization."""
        registry = StdlibRegistry()
        assert "math" in registry.modules

    def test_io_module_has_expected_functions(self):
        """The io module should contain println, print, and eprintln."""
        registry = StdlibRegistry()
        io_mod = registry.modules["io"]
        assert "println" in io_mod.functions
        assert "print" in io_mod.functions
        assert "eprintln" in io_mod.functions

    def test_math_module_has_expected_functions(self):
        """The math module should contain all core math functions."""
        registry = StdlibRegistry()
        math_mod = registry.modules["math"]
        expected = ["sqrt", "abs", "floor", "ceil", "sin", "cos",
                    "tan", "log", "exp", "min", "max"]
        for name in expected:
            assert name in math_mod.functions, f"Missing math function: {name}"

    def test_only_two_default_modules(self):
        """Only io and math should be registered by default."""
        registry = StdlibRegistry()
        assert set(registry.modules.keys()) == {"io", "math"}

    def test_public_module_paths_include_short_and_std_paths(self):
        """Stdlib imports should accept both short and std-prefixed paths."""
        registry = StdlibRegistry()
        assert registry.public_module_paths() == {"io", "std/io", "math", "std/math"}


class TestResolveCall:
    """Test resolve_call for module.method lookups."""

    def test_io_println(self):
        """resolve_call('io', 'println') should return 'std.io.println'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("io", "println")
        assert result == "std.io.println"

    def test_std_io_println_alias(self):
        """resolve_call('std/io', 'println') should resolve through the io module."""
        registry = StdlibRegistry()
        result = registry.resolve_call("std/io", "println")
        assert result == "std.io.println"

    def test_io_print(self):
        """resolve_call('io', 'print') should return 'std.io.print'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("io", "print")
        assert result == "std.io.print"

    def test_io_eprintln(self):
        """resolve_call('io', 'eprintln') should return 'std.io.eprintln'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("io", "eprintln")
        assert result == "std.io.eprintln"

    def test_math_sqrt(self):
        """resolve_call('math', 'sqrt') should return 'std.math.sqrt'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("math", "sqrt")
        assert result == "std.math.sqrt"

    def test_std_math_sqrt_alias(self):
        """resolve_call('std/math', 'sqrt') should resolve through the math module."""
        registry = StdlibRegistry()
        result = registry.resolve_call("std/math", "sqrt")
        assert result == "std.math.sqrt"

    def test_math_abs(self):
        """resolve_call('math', 'abs') should return 'std.math.abs'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("math", "abs")
        assert result == "std.math.abs"

    def test_math_floor(self):
        """resolve_call('math', 'floor') should return 'std.math.floor'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("math", "floor")
        assert result == "std.math.floor"

    def test_math_ceil(self):
        """resolve_call('math', 'ceil') should return 'std.math.ceil'."""
        registry = StdlibRegistry()
        result = registry.resolve_call("math", "ceil")
        assert result == "std.math.ceil"

    def test_math_trig_functions(self):
        """resolve_call should work for sin, cos, tan."""
        registry = StdlibRegistry()
        assert registry.resolve_call("math", "sin") == "std.math.sin"
        assert registry.resolve_call("math", "cos") == "std.math.cos"
        assert registry.resolve_call("math", "tan") == "std.math.tan"

    def test_math_log_exp(self):
        """resolve_call should work for log and exp."""
        registry = StdlibRegistry()
        assert registry.resolve_call("math", "log") == "std.math.log"
        assert registry.resolve_call("math", "exp") == "std.math.exp"

    def test_math_min_max(self):
        """resolve_call should work for min and max."""
        registry = StdlibRegistry()
        assert registry.resolve_call("math", "min") == "std.math.min"
        assert registry.resolve_call("math", "max") == "std.math.max"

    def test_nonexistent_module(self):
        """resolve_call with an unknown module should return None."""
        registry = StdlibRegistry()
        result = registry.resolve_call("nonexistent", "foo")
        assert result is None

    def test_nonexistent_function_in_known_module(self):
        """resolve_call with an unknown function in a known module should return None."""
        registry = StdlibRegistry()
        result = registry.resolve_call("io", "nonexistent")
        assert result is None

    def test_nonexistent_module_and_function(self):
        """resolve_call with both unknown module and function should return None."""
        registry = StdlibRegistry()
        result = registry.resolve_call("fake_mod", "fake_func")
        assert result is None

    def test_empty_strings(self):
        """resolve_call with empty strings should return None."""
        registry = StdlibRegistry()
        assert registry.resolve_call("", "") is None
        assert registry.resolve_call("io", "") is None
        assert registry.resolve_call("", "println") is None


class TestCustomModuleRegistration:
    """Test registering custom modules after initialization."""

    def test_register_custom_module(self):
        """A manually registered module should be resolvable."""
        registry = StdlibRegistry()
        custom_mod = StdlibModule(name="custom")
        custom_mod.functions["do_thing"] = StdlibFunction(
            module="custom", name="do_thing",
            canonical="std.custom.do_thing",
        )
        registry.register_module(custom_mod)

        assert registry.resolve_call("custom", "do_thing") == "std.custom.do_thing"


class TestStdlibDataclasses:
    """Test the StdlibFunction and StdlibModule dataclass basics."""

    def test_stdlib_module_fields(self):
        """StdlibModule should store name and functions."""
        mod = StdlibModule(name="test")
        assert mod.name == "test"
        assert mod.functions == {}

    def test_stdlib_module_add_function(self):
        """Adding a function to a module should be retrievable."""
        mod = StdlibModule(name="test")
        func = StdlibFunction(module="test", name="f", canonical="std.test.f")
        mod.functions["f"] = func
        assert mod.functions["f"] is func
