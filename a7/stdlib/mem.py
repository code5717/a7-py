"""A7 stdlib: mem module — memory management (stub)."""

from . import StdlibModule


def register_mem_module(registry):
    """Register the mem module with the stdlib registry."""
    module = StdlibModule(name="mem")
    registry.register_module(module)
