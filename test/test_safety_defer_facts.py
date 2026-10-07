"""Deferred statements are proven where they run (audit P2-53).

A `defer` runs when its block ends: at the fall-through end and at every
`ret`, `break` or `continue` that leaves the block. The rejected programs
compiled before the fix because the deferred statement was proven with the
facts at the `defer` line; they then divided by zero, read freed memory or
freed twice.
"""

import pytest

from conftest import expect_exit, expect_ok, run_both_profiles

DIVISOR = "Divisor not proven non-zero"
MOVED = "Use after move or delete"
DELETED_TWICE = "a value can be deleted only once"

HEADER = 'io :: import "std/io"\nBox :: struct { value: i32 }\n'


def test_deferred_division_sees_the_later_assignment(tmp_path):
    source = HEADER + """f :: fn(n: i32) {
    d := 5
    defer io.println("{}", 10 / d)
    d = n
}
main :: fn() { f(0) }
"""
    expect_exit(source, tmp_path, 6, DIVISOR)


def test_deferred_division_is_proven_at_an_early_return(tmp_path):
    """The fall-through end has `d == 5`; the `ret` leaves with `d == 0`."""
    source = HEADER + """f :: fn(n: i32) {
    d := 5
    defer io.println("{}", 10 / d)
    if n > 0 {
        d = 0
        ret
    }
}
main :: fn() { f(1) }
"""
    expect_exit(source, tmp_path, 6, DIVISOR)


def test_deferred_division_with_a_divisor_proven_at_every_exit_runs(tmp_path, zig):
    source = HEADER + """f :: fn(n: i32) {
    d := 5
    defer io.println("{}", 10 / d)
    if n > 7 { ret }
    d = n
    if d == 0 { d = 1 }
}
main :: fn() {
    f(0)
    f(5)
    f(9)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "10\n2\n2\n"


def test_deferred_read_after_del_is_rejected(tmp_path):
    source = HEADER + """main :: fn() {
    b := new Box
    if b == nil { ret }
    b.value = 7
    defer io.println("{}", b.value)
    del b
}
"""
    expect_exit(source, tmp_path, 6, MOVED)


def test_deferred_field_write_after_del_is_rejected(tmp_path):
    source = HEADER + """main :: fn() {
    b := new Box
    if b == nil { ret }
    defer b.value = 0
    b.value = 7
    io.println("{}", b.value)
    del b
}
"""
    expect_exit(source, tmp_path, 6, MOVED)


def test_deferred_field_write_before_the_deferred_del_runs(tmp_path, zig):
    """Registered after `defer del b`, the field write runs first and `b` is still non-nil."""
    source = HEADER + """main :: fn() {
    b := new Box
    if b == nil { ret }
    defer del b
    defer io.println("{}", b.value)
    defer b.value = 0
    b.value = 7
    io.println("{}", b.value)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "7\n0\n"


@pytest.mark.parametrize("body", [
    "    defer del b\n    b.value = 1\n    del b\n",
    "    defer del b\n    defer del b\n    b.value = 1\n",
], ids=["defer-then-del", "two-defers"])
def test_double_delete_through_defer_is_rejected(tmp_path, body):
    source = HEADER + "main :: fn() {\n    b := new Box\n    if b == nil { ret }\n" + body + '    io.println("done")\n}\n'
    expect_exit(source, tmp_path, 6, DELETED_TWICE)


def test_defers_run_last_in_first_out_before_the_delete(tmp_path, zig):
    """The read is deferred after the `del`, so it runs first and the program is safe."""
    source = HEADER + """f :: fn(n: i32) i32 {
    b := new Box
    if b == nil { ret 0 }
    defer del b
    defer io.println("{}", b.value)
    b.value = n
    if n > 3 { ret b.value + 1 }
    match n {
        case 1: { ret 11 }
        else: { b.value = 2 }
    }
    ret b.value
}
main :: fn() {
    io.println("{}", f(5))
    io.println("{}", f(1))
    io.println("{}", f(0))
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "5\n6\n1\n11\n2\n2\n"


def test_defer_in_a_loop_body_is_proven_at_break_and_continue(tmp_path, zig):
    source = HEADER + """main :: fn() {
    total := 0
    for i := 0; i < 5; i += 1 {
        b := new Box
        if b == nil { break }
        defer del b
        b.value = i
        if i == 1 { continue }
        if i == 3 { break }
        total += b.value
    }
    io.println("{}", total)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "2\n"


def test_defer_reads_the_binding_visible_at_the_defer_line(tmp_path):
    """The deferred `x` is the parameter, not the `x` declared later in the block."""
    source = HEADER + """f :: fn(x: i32) {
    {
        defer io.println("{}", 10 / x)
        x := 5
        io.println("{}", x)
    }
}
main :: fn() { f(0) }
"""
    expect_exit(source, tmp_path, 6, DIVISOR)


def test_defer_as_the_only_statement_of_a_match_arm_runs_at_the_arm_end(tmp_path):
    """`d` is zero when the arm ends; the later `d = 5` does not help."""
    source = HEADER + """f :: fn(n: i32) {
    d := 0
    match n {
        case 1: defer io.println("{}", 10 / d)
        else: io.println("else")
    }
    d = 5
    io.println("{}", d)
}
main :: fn() { f(1) }
"""
    expect_exit(source, tmp_path, 6, DIVISOR)


DEFERRED_ADD = HEADER + """f :: fn(n: i32) {
    x := 1
    defer io.println("{}", x + 1)
    if n == 7 { ret }
    x = n
}
main :: fn() {
    f(7)
    f(2147483647)
}
"""


def test_deferred_add_wraps_unless_every_exit_proves_the_range(tmp_path, zig):
    """`x + 1` fits at the `ret` exit and may overflow at the block end."""
    release = expect_ok(DEFERRED_ADD, tmp_path, profile="release")
    with open(release.output_path, encoding="utf-8") as handle:
        assert "(x +% 1)" in handle.read()
    assert run_both_profiles(DEFERRED_ADD, tmp_path, zig) == "2\n-2147483648\n"
