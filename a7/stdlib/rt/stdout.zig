var __a7_stdout_buf: [4096]u8 = undefined;
var __a7_stdout_writer: ?std.Io.File.Writer = null;
var __a7_stdout_is_tty = false;
// A reader that closed the pipe ends the program quietly, as SIGPIPE does in C.
fn __a7_stdout_failed(comptime what: []const u8) noreturn {
    if (__a7_stdout_writer.?.err) |err| if (err == error.BrokenPipe) std.process.exit(0);
    @panic("a7 stdout " ++ what ++ " failed");
}
fn __a7_stdout_flush() void {
    __a7_stdout_writer.?.interface.flush() catch __a7_stdout_failed("flush");
}
fn __a7_stdout_print(comptime fmt: []const u8, args: anytype) void {
    const out = &__a7_stdout_writer.?.interface;
    out.print(fmt, args) catch __a7_stdout_failed("write");
    // A terminal is line-buffered: a finished line is shown at once.
    if (__a7_stdout_is_tty and std.mem.indexOfScalar(u8, out.buffered(), '\n') != null) __a7_stdout_flush();
}
// Text printed before a panic reaches stdout before the panic message.
fn __a7_panic(msg: []const u8, first_trace_addr: ?usize) noreturn {
    if (__a7_stdout_writer) |*writer| writer.interface.flush() catch {};
    std.debug.defaultPanic(msg, first_trace_addr orelse @returnAddress());
}
pub const panic = std.debug.FullPanic(__a7_panic);
