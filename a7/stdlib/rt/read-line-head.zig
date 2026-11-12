var __a7_stdin_buf: [4096]u8 = undefined;
var __a7_stdin_reader: ?std.Io.File.Reader = null;
fn __a7_stdin_read_line(buf: []u8) __a7_IoResult {
