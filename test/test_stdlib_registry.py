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


class TestGetBackendMapping:
    """Test get_backend_mapping for retrieving backend-specific code strings."""

    def test_io_println_zig(self):
        """Zig mapping for std.io.println should target stdout."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.io.println", "zig")
        assert result == "__a7_stdout_print"

    def test_io_print_zig(self):
        """Zig mapping for std.io.print should target stdout."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.io.print", "zig")
        assert result == "__a7_stdout_print"

    def test_io_eprintln_zig(self):
        """Zig mapping for std.io.eprintln should target stderr."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.io.eprintln", "zig")
        assert result == "__a7_stderr_print"

    def test_math_sqrt_zig(self):
        """Zig mapping for std.math.sqrt should be '@sqrt'."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.math.sqrt", "zig")
        assert result == "@sqrt"

    def test_math_abs_zig(self):
        """Zig mapping for std.math.abs should be '@abs'."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.math.abs", "zig")
        assert result == "@abs"

    def test_all_math_zig_mappings(self):
        """All math functions should have correct Zig mappings."""
        registry = StdlibRegistry()
        expected = {
            "std.math.sqrt": "@sqrt",
            "std.math.abs": "@abs",
            "std.math.floor": "@floor",
            "std.math.ceil": "@ceil",
            "std.math.sin": "@sin",
            "std.math.cos": "@cos",
            "std.math.tan": "@tan",
            "std.math.log": "@log",
            "std.math.exp": "@exp",
            "std.math.min": "@min",
            "std.math.max": "@max",
        }
        for canonical, zig_code in expected.items():
            result = registry.get_backend_mapping(canonical, "zig")
            assert result == zig_code, (
                f"get_backend_mapping('{canonical}', 'zig') returned {result}, "
                f"expected '{zig_code}'"
            )

    def test_unknown_backend_returns_none(self):
        """An unregistered backend should return None."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.math.sqrt", "llvm")
        assert result is None

    def test_unknown_canonical_returns_none(self):
        """An unknown canonical name should return None."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("std.fake.func", "zig")
        assert result is None

    def test_empty_canonical_returns_none(self):
        """An empty canonical name should return None."""
        registry = StdlibRegistry()
        result = registry.get_backend_mapping("", "zig")
        assert result is None


class TestIsIoCall:
    """Test is_io_call for detecting I/O operations."""

    def test_io_println_is_io(self):
        """io.println should be detected as an I/O call."""
        registry = StdlibRegistry()
        assert registry.is_io_call("io", "println") is True

    def test_io_print_is_io(self):
        """io.print should be detected as an I/O call."""
        registry = StdlibRegistry()
        assert registry.is_io_call("io", "print") is True

    def test_io_eprintln_is_io(self):
        """io.eprintln should be detected as an I/O call."""
        registry = StdlibRegistry()
        assert registry.is_io_call("io", "eprintln") is True

    def test_math_sqrt_is_not_io(self):
        """math.sqrt should not be detected as an I/O call."""
        registry = StdlibRegistry()
        assert registry.is_io_call("math", "sqrt") is False

    def test_math_abs_is_not_io(self):
        """math.abs should not be detected as an I/O call."""
        registry = StdlibRegistry()
        assert registry.is_io_call("math", "abs") is False

    def test_nonexistent_module_is_not_io(self):
        """A nonexistent module should not be detected as I/O."""
        registry = StdlibRegistry()
        assert registry.is_io_call("nonexistent", "println") is False

    def test_nonexistent_function_is_not_io(self):
        """A nonexistent function in the io module should not be detected as I/O."""
        registry = StdlibRegistry()
        assert registry.is_io_call("io", "nonexistent") is False


class TestCustomModuleRegistration:
    """Test registering custom modules after initialization."""

    def test_register_custom_module(self):
        """A manually registered module should be resolvable."""
        registry = StdlibRegistry()
        custom_mod = StdlibModule(name="custom")
        custom_mod.functions["do_thing"] = StdlibFunction(
            module="custom", name="do_thing",
            canonical="std.custom.do_thing",
            backend_map={"zig": "custom.doThing"},
        )
        registry.register_module(custom_mod)

        assert registry.resolve_call("custom", "do_thing") == "std.custom.do_thing"
        assert registry.get_backend_mapping("std.custom.do_thing", "zig") == "custom.doThing"

    def test_custom_module_not_io(self):
        """A non-io custom module should not be detected as I/O."""
        registry = StdlibRegistry()
        custom_mod = StdlibModule(name="custom")
        custom_mod.functions["write"] = StdlibFunction(
            module="custom", name="write",
            canonical="std.custom.write",
            backend_map={},
        )
        registry.register_module(custom_mod)
        assert registry.is_io_call("custom", "write") is False


class TestStdlibDataclasses:
    """Test the StdlibFunction and StdlibModule dataclass basics."""

    def test_stdlib_function_fields(self):
        """StdlibFunction should store module, name, canonical, and backend_map."""
        func = StdlibFunction(
            module="io", name="println",
            canonical="std.io.println",
            backend_map={"zig": "std.debug.print"},
        )
        assert func.module == "io"
        assert func.name == "println"
        assert func.canonical == "std.io.println"
        assert func.backend_map == {"zig": "std.debug.print"}

    def test_stdlib_function_default_backend_map(self):
        """StdlibFunction should default to an empty backend_map."""
        func = StdlibFunction(module="test", name="f", canonical="std.test.f")
        assert func.backend_map == {}

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
