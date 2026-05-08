"""A7 stdlib: io module — I/O operations."""

from . import StdlibModule, StdlibFunction


def register_io_module(registry):
    """Register the io module with the stdlib registry."""
    module = StdlibModule(name="io")

    module.functions["println"] = StdlibFunction(
        module="io", name="println",
        canonical="std.io.println",
        backend_map={"zig": "std.debug.print", "c": "printf"},
    )
    module.functions["print"] = StdlibFunction(
        module="io", name="print",
        canonical="std.io.print",
        backend_map={"zig": "std.debug.print", "c": "printf"},
    )
    module.functions["eprintln"] = StdlibFunction(
        module="io", name="eprintln",
        canonical="std.io.eprintln",
        backend_map={"zig": "std.debug.print", "c": "fprintf"},
    )

    registry.register_module(module)
