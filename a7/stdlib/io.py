"""A7 stdlib: io module — I/O operations."""

from . import StdlibModule, StdlibFunction, ZigHook


def register_io_module(registry):
    """Register the io module with the stdlib registry."""
    module = StdlibModule(name="io", public_paths=("io", "std/io"), type_source="io.a7")

    module.functions["println"] = StdlibFunction(
        module="io", name="println",
        canonical="std.io.println",
        backend_map={"zig": ZigHook('__a7_stdout_print', call_kind='format_void', newline=True, io_runtime={'stdout': ('stdout.zig',)})},
        signature="fn(string)", argument_policy="format",
    )
    module.functions["print"] = StdlibFunction(
        module="io", name="print",
        canonical="std.io.print",
        backend_map={"zig": ZigHook('__a7_stdout_print', call_kind='format_void', newline=False, io_runtime={'stdout': ('stdout.zig',)})},
        signature="fn(string)", argument_policy="format",
    )
    module.functions["eprintln"] = StdlibFunction(
        module="io", name="eprintln",
        canonical="std.io.eprintln",
        backend_map={"zig": ZigHook('__a7_stderr_print', call_kind='format_void', newline=True, io_runtime={'stderr': ('stderr-head.zig', 'stderr-body.zig')})},
        signature="fn(string)", argument_policy="format",
    )
    module.functions["println_ok"] = StdlibFunction(
        module="io", name="println_ok",
        canonical="std.io.println_ok",
        backend_map={"zig": ZigHook('__a7_stdout_print_ok', call_kind='format_result', newline=True, io_runtime={'stdout': ('stdout.zig',), 'print_ok': ('println-ok.zig',)})},
        signature="fn(string) Result(usize, IoErr)", argument_policy="format",
    )
    module.functions["read_line"] = StdlibFunction(
        module="io", name="read_line",
        canonical="std.io.read_line",
        backend_map={"zig": ZigHook('__a7_stdin_read_line', call_kind='buffer_result', newline=False, io_runtime={'stdin': (), 'read_line': ('read-line-head.zig', 'read-line-body.zig')})},
        signature="fn([]u8) Result(usize, IoErr)", argument_policy="fixed",
    )

    registry.register_module(module)
