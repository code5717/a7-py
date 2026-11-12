"""A7 stdlib: math module — mathematical functions."""

from . import StdlibModule, StdlibFunction, ZigHook


def register_math_module(registry):
    """Register the math module with the stdlib registry."""
    module = StdlibModule(name="math", public_paths=("math", "std/math"))

    for name in ("sqrt", "abs", "floor", "ceil", "sin", "cos", "tan", "log", "exp", "min", "max"):
        binary = name in {"min", "max"}
        policy = "numeric_common" if binary else "numeric_unary" if name == "abs" else "floating_unary"
        module.functions[name] = StdlibFunction(
            module="math", name=name,
            canonical=f"std.math.{name}",
            signature="fn($T, $T) $T" if binary else "fn($T) $T",
            argument_policy=policy,
            backend_map={"zig": ZigHook("@" + name, call_kind="signed_abs" if name == "abs" else "builtin")},
        )

    registry.register_module(module)
