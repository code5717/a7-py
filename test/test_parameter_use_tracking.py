"""A parameter is written `_` in Zig exactly when no emitted code reads it (audit P2-47).

Use was tracked by name. An inner block that declares a local with the
parameter's name made the parameter look used, and Zig reported "unused
function parameter".
"""

from conftest import run_both_profiles


def test_inner_block_local_that_shadows_an_unused_parameter(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
f :: fn(x: i32) i32 {
    {
        x := 5
        ret x
    }
}
main :: fn() { io.println("{}", f(2)) }
""", tmp_path, zig) == "5\n"


def test_parameter_read_before_an_inner_shadow_stays_named(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
f :: fn(x: i32, unused: i32) i32 {
    y := x + 1
    {
        x := y * 10
        unused := x + 1
        ret unused
    }
}
main :: fn() { io.println("{}", f(2, 0)) }
""", tmp_path, zig) == "31\n"


def test_shadowing_chains_in_nested_blocks_and_loops(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    x := 1
    {
        x := x + 1
        io.println("{}", x)
        {
            x := x * 10
            io.println("{}", x)
        }
        io.println("{}", x)
    }
    for x := 0; x < 1; x += 1 { io.println("loop {}", x) }
    x_1 := 77
    {
        x := 3
        io.println("{} {}", x, x_1)
    }
    io.println("{}", x)
}
""", tmp_path, zig) == "2\n20\n2\nloop 0\n3 77\n1\n"
