"""Nested function bodies get the control-flow and return checks (audit P2-61).

Before, the validator skipped a function declared inside a function body, so
`break` outside a loop and a missing return compiled.
"""

from conftest import expect_exit, expect_ok


def test_break_outside_a_loop_in_a_nested_function_is_rejected(tmp_path):
    expect_exit("""
io :: import "std/io"
main :: fn() {
    inner :: fn(m: i32) i32 {
        break
        ret m
    }
    io.println("ok")
}
""", tmp_path, 6, "Break statement outside loop")


def test_enclosing_loop_does_not_make_a_nested_break_valid(tmp_path):
    expect_exit("""
io :: import "std/io"
main :: fn() {
    for i := 0; i < 2; i += 1 {
        inner :: fn() {
            break
        }
        io.println("ok")
    }
}
""", tmp_path, 6, "Break statement outside loop")


def test_missing_return_in_a_nested_function_is_rejected(tmp_path):
    expect_exit("""
io :: import "std/io"
main :: fn() {
    inner :: fn(m: i32) i32 {
        if m > 0 { ret 1 }
    }
    io.println("ok")
}
""", tmp_path, 6, "Function 'inner' does not return on all paths")


def test_nested_function_with_valid_control_flow_compiles(tmp_path):
    expect_ok("""
io :: import "std/io"
main :: fn() {
    inner :: fn(m: i32) i32 {
        total := 0
        for i := 0; i < m; i += 1 {
            if i == 3 { break }
            total += i
        }
        ret total
    }
    io.println("ok")
}
""", tmp_path)


def test_nested_function_body_is_type_checked(tmp_path):
    expect_exit("""
main :: fn() {
    inner :: fn(m: i32) i32 { ret "wrong" }
}
""", tmp_path, 6, "Type mismatch")
