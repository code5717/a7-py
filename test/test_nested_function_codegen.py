"""Nested functions are emitted at file scope under their own Zig names (audit P2-50).

Zig has no function declarations inside a function body. The backend emits a
nested function before the function that declares it. Two functions may each
declare `helper`, so the emitted name is unique. A nested function that
reads a local or parameter of its enclosing function is rejected: at file
scope that name does not exist.
"""

from conftest import expect_exit, run_both_profiles


def test_nested_functions_that_capture_nothing_build(tmp_path, zig):
    # Both `outer` and `other` declare `helper`; one sits inside an `if`
    # block and one nests a second level.
    assert run_both_profiles("""
io :: import "std/io"
outer :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + 1 }
    if k > 0 {
        deep :: fn(v: i32) i32 {
            inner :: fn(w: i32) i32 { ret w * 2 }
            ret v
        }
    }
    ret k
}
other :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + 2 }
    ret k
}
main :: fn() {
    io.println("{} {}", outer(1), other(2))
}
""", tmp_path, zig) == "1 2\n"


def test_call_to_a_nested_function_runs(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
outer :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + 1 }
    ret helper(k)
}
other :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + 2 }
    ret helper(k)
}
main :: fn() {
    io.println("{} {}", outer(1), other(1))
}
""", tmp_path, zig) == "2 3\n"


def test_reading_an_enclosing_parameter_is_rejected(tmp_path):
    expect_exit("""
io :: import "std/io"
outer :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 { ret v + k }
    ret k
}
main :: fn() { io.println("{}", outer(1)) }
""", tmp_path, 7, "nested function 'helper' uses 'k' from the enclosing function; pass it as a parameter")


def test_reading_an_enclosing_local_is_rejected(tmp_path):
    expect_exit("""
io :: import "std/io"
outer :: fn() i32 {
    base := 10
    helper :: fn(v: i32) i32 { ret v + base }
    ret base
}
main :: fn() { io.println("{}", outer()) }
""", tmp_path, 7, "nested function 'helper' uses 'base' from the enclosing function")


def test_own_parameter_named_like_an_enclosing_local_is_not_a_capture(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
outer :: fn(k: i32) i32 {
    helper :: fn(k: i32) i32 {
        total := k + 1
        ret total
    }
    total := k * 2
    ret helper(total)
}
main :: fn() { io.println("{}", outer(4)) }
""", tmp_path, zig) == "9\n"


def test_nested_calls_use_the_lexical_scope_at_each_depth(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
outer :: fn(k: i32) i32 {
    helper :: fn(v: i32) i32 {
        answer := inner(v)
        inner :: fn(w: i32) i32 { ret w * 2 }
        ret answer
    }
    ret helper(k)
}
main :: fn() { io.println("{}", outer(4)) }
""", tmp_path, zig) == "8\n"


def test_returned_nested_function_runs(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
get_adder :: fn() fn(i32, i32) i32 {
    add :: fn(a: i32, b: i32) i32 { ret a + b }
    ret add
}
main :: fn() {
    adder := get_adder()
    io.println("{}", adder(10, 20))
}
""", tmp_path, zig) == "30\n"
