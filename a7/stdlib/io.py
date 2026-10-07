"""A7 stdlib: io module — I/O operations."""

from . import StdlibModule, StdlibFunction


def register_io_module(registry):
    """Register the io module with the stdlib registry."""
    module = StdlibModule(name="io")

    module.functions["println"] = StdlibFunction(
        module="io", name="println",
        canonical="std.io.println",
        signature="fn(string)", argument_policy="format",
    )
    module.functions["print"] = StdlibFunction(
        module="io", name="print",
        canonical="std.io.print",
        signature="fn(string)", argument_policy="format",
    )
    module.functions["eprintln"] = StdlibFunction(
        module="io", name="eprintln",
        canonical="std.io.eprintln",
        signature="fn(string)", argument_policy="format",
    )
    module.functions["println_ok"] = StdlibFunction(
        module="io", name="println_ok",
        canonical="std.io.println_ok",
        signature="fn(string) Result(usize, IoErr)", argument_policy="format",
    )
    module.functions["read_line"] = StdlibFunction(
        module="io", name="read_line",
        canonical="std.io.read_line",
        signature="fn([]u8) Result(usize, IoErr)", argument_policy="fixed",
    )

    registry.register_module(module)
