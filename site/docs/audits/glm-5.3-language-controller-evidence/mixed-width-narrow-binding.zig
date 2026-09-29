const std = @import("std");
var __a7_io: ?std.Io = null;
fn __a7_stdout_print(comptime fmt: []const u8, args: anytype) void {
    var __a7_stream_buf: [1024]u8 = undefined;
    var __a7_writer = std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stream_buf);
    __a7_writer.interface.print(fmt, args) catch @panic("a7 stdout write failed");
    __a7_writer.interface.flush() catch @panic("a7 stdout flush failed");
}
pub fn main(init: std.process.Init) void {
    __a7_io = init.io;
    __a7_user_main();
}

fn add(a: i8, b: i64) void {
    const c: i8 = (a + b);
    __a7_stdout_print("{}\n", .{c});
}

fn __a7_user_main() void {
    const a: i8 = 100;
    const b: i64 = 200;
    add(a, b);
}
