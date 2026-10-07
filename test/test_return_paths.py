"""Return-path analysis for `while true` (audit P2-61).

A `while true` loop with no `break` that leaves it never falls through, so a
non-void function may end with it.
"""

from conftest import expect_exit, run_both_profiles


MISSING = "does not return on all paths"


def test_function_ending_in_while_true_with_ret_runs(tmp_path, zig):
    out = run_both_profiles("""
io :: import "std/io"
first_multiple :: fn(step: i32, floor: i32) i32 {
    value := step
    while true {
        if value >= floor { ret value }
        value += step
    }
}
main :: fn() { io.println("{}", first_multiple(7, 30)) }
""", tmp_path, zig)
    assert out == "35\n"


def test_break_inside_an_inner_loop_does_not_leave_while_true(tmp_path, zig):
    out = run_both_profiles("""
io :: import "std/io"
f :: fn(limit: i32) i32 {
    round := 0
    while true {
        for i := 0; i < 10; i += 1 {
            if i == 2 { break }
        }
        round += 1
        if round >= limit { ret round }
    }
}
main :: fn() { io.println("{}", f(3)) }
""", tmp_path, zig)
    assert out == "3\n"


def test_while_true_with_a_break_still_needs_a_return(tmp_path):
    expect_exit("""
io :: import "std/io"
f :: fn(x: i32) i32 {
    while true {
        if x > 0 { ret 1 }
        break
    }
}
main :: fn() { io.println("{}", f(1)) }
""", tmp_path, 6, MISSING)


def test_labeled_break_from_an_inner_loop_still_needs_a_return(tmp_path):
    expect_exit("""
io :: import "std/io"
f :: fn(x: i32) i32 {
    @outer while true {
        for i := 0; i < 3; i += 1 {
            if i == x { break outer }
        }
        if x > 5 { ret 1 }
    }
}
main :: fn() { io.println("{}", f(1)) }
""", tmp_path, 6, MISSING)


def test_while_with_a_non_literal_condition_still_needs_a_return(tmp_path):
    expect_exit("""
io :: import "std/io"
f :: fn(x: i32) i32 {
    while x > 0 {
        ret 1
    }
}
main :: fn() { io.println("{}", f(1)) }
""", tmp_path, 6, MISSING)
