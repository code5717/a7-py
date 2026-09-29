pub fn main() void {
    const x: i32 = 1;
    const y = (x << @intCast(-1));
    _ = y;
}
