const Box = struct {
    value: i32,
};

fn g(b2: ?*Box) void {
    b2.?.value = 1;
}

pub fn main() void {
    const b: ?*Box = null;
    g(b);
}
