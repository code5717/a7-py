const std = @import("std");
const allocator = std.heap.page_allocator;

const Box = struct {
    value: i32,
};

pub fn main() void {
    var b = allocator.create(Box) catch null;
    if ((b == null)) {
        return;
    }
    var n: i32 = 0;
    while ((n < 3)) {
        defer if (b) |p| allocator.destroy(p);
        b.?.value += 1;
        n += 1;
    }
}
