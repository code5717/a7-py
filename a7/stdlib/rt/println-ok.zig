fn __a7_stdout_print_ok(comptime fmt: []const u8, args: anytype) __a7_IoResult {
    __a7_stdout_writer.?.interface.print(fmt, args) catch return .{ .err = .WriteFailed };
    __a7_stdout_writer.?.interface.flush() catch return .{ .err = .FlushFailed };
    return .{ .ok = std.fmt.count(fmt, args) };
}
