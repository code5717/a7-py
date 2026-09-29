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

fn __a7_user_main() void {
    const x: i32 = 7;
    switch (x) {
        1 => {
            __a7_stdout_print("one\n", .{});
        },
    }
}
