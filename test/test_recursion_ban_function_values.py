"""Recursion ban over function values (audit P2-58).

Each rejected program recursed at run time and printed `depth 5` before the
validator followed function values. The accepted programs use callbacks
without a cycle and must keep building and running.
"""

import pytest

from conftest import expect_exit, run_both_profiles


RECURSION = "Recursion is not allowed: Cycle: "

REJECTED = {
    "alias_of_alias": ("""
io :: import "std/io"
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    a: fn(i32) i32 = g
    b: fn(i32) i32 = a
    ret 1 + b(n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "g -> g"),
    "two_level_forwarding": ("""
io :: import "std/io"
lvl2 :: fn(f: fn(i32) i32, n: i32) i32 { ret f(n) }
lvl1 :: fn(f: fn(i32) i32, n: i32) i32 { ret lvl2(f, n) }
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    ret 1 + lvl1(g, n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "lvl2 -> g -> lvl1 -> lvl2"),
    "global_function_constant": ("""
io :: import "std/io"
CB :: g
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    ret 1 + CB(n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "g -> g"),
    "struct_field": ("""
io :: import "std/io"
Ops :: struct { cb: fn(i32) i32 }
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    o := Ops{cb: g}
    ret 1 + o.cb(n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "g -> g"),
    "returned_function": ("""
io :: import "std/io"
pick :: fn() fn(i32) i32 { ret g }
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    h := pick()
    ret 1 + h(n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "g -> g"),
    "array_element": ("""
io :: import "std/io"
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    fs: [1]fn(i32) i32 = [g]
    ret 1 + fs[0](n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "g -> g"),
    "if_expression": ("""
io :: import "std/io"
z :: fn(n: i32) i32 { ret 0 }
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    h: fn(i32) i32 = z
    if n > 0 { h = if n > 0 { g } else { z } }
    ret 1 + h(n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", "g -> g"),
    "mutual_through_stored_values": ("""
io :: import "std/io"
Ops :: struct { next: fn(i32) i32 }
left :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    o := Ops{next: right}
    ret 1 + o.next(n - 1)
}
right :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    o := Ops{next: left}
    ret 1 + o.next(n - 1)
}
main :: fn() { io.println("depth {}", left(5)) }
""", "left -> left"),
}


@pytest.mark.parametrize("shape", sorted(REJECTED))
def test_recursion_through_a_function_value_is_rejected(tmp_path, shape):
    source, cycle = REJECTED[shape]
    expect_exit(source, tmp_path, 6, RECURSION + cycle)


def test_recursion_through_an_imported_higher_order_function_is_rejected(tmp_path):
    (tmp_path / "helper.a7").write_text(
        "pub apply :: fn(f: fn(i32) i32, n: i32) i32 { ret f(n) }\n", encoding="utf-8"
    )
    expect_exit("""
io :: import "std/io"
h :: import "helper"
g :: fn(n: i32) i32 {
    if n <= 0 { ret 0 }
    ret 1 + h.apply(g, n - 1)
}
main :: fn() { io.println("depth {}", g(5)) }
""", tmp_path, 6, RECURSION + "g -> g")


def test_comparator_passed_to_a_selection_helper_runs(tmp_path, zig):
    out = run_both_profiles("""
io :: import "std/io"
ascending :: fn(a: i32, b: i32) bool { ret a < b }
descending :: fn(a: i32, b: i32) bool { ret a > b }
first_by :: fn(values: [4]i32, before: fn(i32, i32) bool) i32 {
    best := values[0]
    for value in values {
        if before(value, best) { best = value }
    }
    ret best
}
main :: fn() {
    values: [4]i32 = [3, 1, 4, 2]
    io.println("{} {}", first_by(values, ascending), first_by(values, descending))
}
""", tmp_path, zig)
    assert out == "1 4\n"


def test_visitor_called_in_a_loop_runs(tmp_path, zig):
    out = run_both_profiles("""
io :: import "std/io"
show :: fn(index: usize, value: i32) { io.println("{}: {}", index, value) }
each :: fn(values: [3]i32, visit: fn(usize, i32)) {
    for i := cast(usize, 0); i < 3; i += 1 {
        visit(i, values[i])
    }
}
main :: fn() {
    values: [3]i32 = [7, 8, 9]
    each(values, show)
}
""", tmp_path, zig)
    assert out == "0: 7\n1: 8\n2: 9\n"


def test_table_of_handlers_called_in_a_loop_runs(tmp_path, zig):
    out = run_both_profiles("""
io :: import "std/io"
Handler :: struct { apply: fn(i32) i32 }
double :: fn(x: i32) i32 { ret x * 2 }
negate :: fn(x: i32) i32 { ret 0 - x }
add_ten :: fn(x: i32) i32 { ret x + 10 }
main :: fn() {
    table: [3]fn(i32) i32 = [double, negate, add_ten]
    value: i32 = 4
    for i := cast(usize, 0); i < 3; i += 1 {
        value = table[i](value)
    }
    io.println("{}", value)
    last := Handler{apply: double}
    io.println("{}", last.apply(value))
}
""", tmp_path, zig)
    assert out == "2\n4\n"


def test_callback_that_calls_a_callback_of_another_type_runs(tmp_path, zig):
    # `apply` is passed as a value and calls through a value itself. Its own
    # type is fn(fn(i32, i32) i32) i32, so its call cannot reach `apply`.
    out = run_both_profiles("""
io :: import "std/io"
add :: fn(a: i32, b: i32) i32 { ret a + b }
apply :: fn(op: fn(i32, i32) i32) i32 { ret op(10, 20) }
run :: fn(user: fn(fn(i32, i32) i32) i32, op: fn(i32, i32) i32) i32 { ret user(op) }
main :: fn() { io.println("{}", run(apply, add)) }
""", tmp_path, zig)
    assert out == "30\n"
