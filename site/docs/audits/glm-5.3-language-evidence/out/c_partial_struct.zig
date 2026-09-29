const Counter = struct {
    value: i32,
    count: i32,
};

pub fn main() void {
    const c = Counter{ .value = 0 };
    _ = c;
}
