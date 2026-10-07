"""A7 stdlib: math module — mathematical functions."""

from . import StdlibModule, StdlibFunction


def register_math_module(registry):
    """Register the math module with the stdlib registry."""
    module = StdlibModule(name="math")

    for name in ("sqrt", "abs", "floor", "ceil", "sin", "cos", "tan", "log", "exp", "min", "max"):
        module.functions[name] = StdlibFunction(
            module="math", name=name,
            canonical=f"std.math.{name}",
        )

    registry.register_module(module)
