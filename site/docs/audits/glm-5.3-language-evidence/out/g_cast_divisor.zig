pub fn main() void {
    const c: i32 = 0;
    if ((c != 0)) {
        const z = @divTrunc(100, @as(i32, c));
        _ = z;
    }
}
