"""A7 stdlib: string module — string operations (stub)."""

from . import StdlibModule


def register_string_module(registry):
    """Register the string module with the stdlib registry."""
    module = StdlibModule(name="string")
    registry.register_module(module)
