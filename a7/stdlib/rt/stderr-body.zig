    var __a7_stream_buf: [1024]u8 = undefined;
    var __a7_writer = std.Io.File.stderr().writerStreaming(__a7_io.?, &__a7_stream_buf);
    __a7_writer.interface.print(fmt, args) catch @panic("a7 stderr write failed");
    __a7_writer.interface.flush() catch @panic("a7 stderr flush failed");
}
