"""A7 stdlib: math module — mathematical functions."""

from . import StdlibModule, StdlibFunction


def register_math_module(registry):
    """Register the math module with the stdlib registry."""
    module = StdlibModule(name="math")

    # Core math functions available as math.sqrt, math.abs, etc.
    _MATH_FUNCS = {
        "sqrt": "@sqrt",
        "abs": "@abs",
        "floor": "@floor",
        "ceil": "@ceil",
        "sin": "@sin",
        "cos": "@cos",
        "tan": "@tan",
        "log": "@log",
        "exp": "@exp",
        "min": "@min",
        "max": "@max",
    }

    for name, zig_builtin in _MATH_FUNCS.items():
        func = StdlibFunction(
            module="math", name=name,
            canonical=f"std.math.{name}",
            backend_map={"zig": zig_builtin},
        )
        module.functions[name] = func

    registry.register_module(module)
