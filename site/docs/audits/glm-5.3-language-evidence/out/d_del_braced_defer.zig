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
    b.?.value = 1;
    if (b) |p| allocator.destroy(p);
    defer {
        b = allocator.create(Box) catch null;
    }
    b.?.value = 2;
}
