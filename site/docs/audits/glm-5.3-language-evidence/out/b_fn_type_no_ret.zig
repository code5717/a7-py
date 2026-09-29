const Handler = *const fn () i32;

const S = struct {
    cb: *const fn () void,
};

pub fn main() void {
    const h: Handler = undefined;
    _ = h;
}
