"""A7 stdlib: io module — I/O operations."""

from . import StdlibModule, StdlibFunction


def register_io_module(registry):
    """Register the io module with the stdlib registry."""
    module = StdlibModule(name="io")

    module.functions["println"] = StdlibFunction(
        module="io", name="println",
        canonical="std.io.println",
    )
    module.functions["print"] = StdlibFunction(
        module="io", name="print",
        canonical="std.io.print",
    )
    module.functions["eprintln"] = StdlibFunction(
        module="io", name="eprintln",
        canonical="std.io.eprintln",
    )
    module.functions["println_ok"] = StdlibFunction(
        module="io", name="println_ok",
        canonical="std.io.println_ok",
    )
    module.functions["read_line"] = StdlibFunction(
        module="io", name="read_line",
        canonical="std.io.read_line",
    )

    registry.register_module(module)
