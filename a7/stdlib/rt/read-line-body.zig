    var n: usize = 0;
    while (n < buf.len) {
        const b = __a7_stdin_reader.?.interface.takeByte() catch |e| switch (e) {
            error.EndOfStream => if (n == 0) return .{ .err = .EndOfStream } else break,
            error.ReadFailed => return .{ .err = .ReadFailed },
        };
        buf[n] = b;
        n += 1;
        if (b == '\n') break;
    }
    return .{ .ok = n };
}
