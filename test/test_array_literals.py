"""An array literal without a declared type is an array, not a tuple (audit P2-47).

`xs := [1, 2, 3]` was emitted as `const xs = .{ 1, 2, 3 };`. Zig makes that a
tuple: a runtime index and `for` over it do not build.
"""

from conftest import run_both_profiles


def test_inferred_array_takes_a_runtime_index_and_a_for_loop(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    xs := [1, 2, 3]
    i: usize = 1
    i += 1
    total := 0
    for v in xs { total += v }
    io.println("{} {}", xs[i], total)
}
""", tmp_path, zig) == "3 6\n"


def test_element_types_and_nesting(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    floats := [1.5, 2.5]
    grid := [[1, 2], [3, 4]]
    words := ["x", "y"]
    i: usize = 0
    i += 1
    io.println("{} {} {}", floats[i], grid[i][i], words[i])
}
""", tmp_path, zig) == "2.5 4 y\n"


def test_declared_type_still_decides_the_element_type(tmp_path, zig):
    # The literal alone is `[3]i32`; each destination here is wider or narrower.
    assert run_both_profiles("""
io :: import "std/io"
take :: fn(v: [3]i64) i64 { ret v[2] }
main :: fn() {
    wide: [3]i64 = [1, 2, 3000000000]
    small: [2]u8 = [200, 2]
    i: usize = 0
    i += 0
    wide = [4, 5, 6000000000]
    io.println("{} {} {}", wide[2], small[i], take([7, 8, 9000000000]))
}
""", tmp_path, zig) == "6000000000 200 9000000000\n"


def test_literal_used_where_no_destination_gives_a_type(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    i: usize = 0
    i += 1
    for v in [10, 20] { io.println("{}", v) }
    for k, v in [5, 6] { io.println("{} {}", k, v) }
    io.println("{}", [1, 2][i])
}
""", tmp_path, zig) == "10\n20\n0 5\n1 6\n2\n"
