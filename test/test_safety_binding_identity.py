"""Facts follow the declaration, not the spelling (audit P2-54, P2-55, P2-57).

Two variables with the same name are different variables. Each rejected
program compiled before the fix because a fact, or a callee's "does not
delete" verdict, was looked up by name and found the wrong declaration.
"""

import pytest

from conftest import expect_exit, run_both_profiles

DIVISOR = "Divisor not proven non-zero"
INDEX = "Index not proven in bounds"
MOVED = "Use after move or delete"

IO = 'io :: import "std/io"\n'
BOX = IO + """Box :: struct { value: i32 }
keep :: fn(b: ref Box) { b.value = 1 }
drop :: fn(b: ref Box) { del b }
"""
RESULT = """Outcome :: union(tag) {
    ok: i32
    err: i32
}
"""


def test_length_guard_on_an_inner_slice_does_not_bound_the_outer_one(tmp_path):
    source = IO + """g :: fn(i: usize) i32 {
    small: [2]i32 = [1, 2]
    big: [10]i32 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    s := small[0..2]
    {
        s := big[0..10]
        if i >= s.len { ret 0 }
    }
    ret s[i]
}
main :: fn() { io.println("{}", g(cast(usize, 7))) }
"""
    expect_exit(source, tmp_path, 6, INDEX)


def test_length_guard_on_the_outer_slice_survives_an_inner_shadow(tmp_path, zig):
    source = IO + """g :: fn(i: usize) i32 {
    small: [2]i32 = [1, 2]
    big: [10]i32 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    s := small[0..2]
    if i >= s.len { ret 0 }
    {
        s := big[0..10]
        io.println("{}", s.len)
    }
    ret s[i]
}
main :: fn() {
    io.println("{}", g(cast(usize, 1)))
    io.println("{}", g(cast(usize, 7)))
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "10\n2\n0\n"


@pytest.mark.parametrize("functions, call", [
    ("apply :: fn(keep: fn(ref Box), b: ref Box) { keep(b) }\n", "    apply(drop, b)\n"),
    ("", "    {\n        keep: fn(ref Box) = drop\n        keep(b)\n    }\n"),
], ids=["parameter", "local"])
def test_function_value_named_like_a_non_deleting_function_may_delete(tmp_path, functions, call):
    source = BOX + functions + "main :: fn() {\n    b := new Box\n    if b == nil { ret }\n" + call + (
        '    b.value = 3\n    io.println("{}", b.value)\n}\n'
    )
    expect_exit(source, tmp_path, 6, MOVED)


def test_call_to_the_file_scope_function_keeps_the_reference(tmp_path, zig):
    source = BOX + """apply :: fn(b: ref Box) { keep(b) }
main :: fn() {
    b := new Box
    if b == nil { ret }
    apply(b)
    {
        keep(b)
    }
    io.println("{}", b.value)
    b.value = 3
    io.println("{}", b.value)
    del b
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "1\n3\n"


@pytest.mark.parametrize("outer, local", [
    ("v :: 5\n", ""),
    ("", "    v := 5\n"),
], ids=["file-scope-constant", "local"])
def test_match_capture_does_not_inherit_an_outer_fact(tmp_path, outer, local):
    source = IO + outer + RESULT + "f :: fn(r: Outcome) i32 {\n" + local + """    match r {
        case .ok(v): { ret 10 / v }
        case .err(e): { ret e }
    }
}
main :: fn() { io.println("{}", f(Outcome{ok: 0})) }
"""
    expect_exit(source, tmp_path, 6, DIVISOR)


def test_guarded_match_capture_divides(tmp_path, zig):
    source = IO + "v :: 5\n" + RESULT + """f :: fn(r: Outcome) i32 {
    match r {
        case .ok(v): {
            if v != 0 { ret 10 / v }
            ret 0
        }
        case .err(e): { ret e }
    }
}
main :: fn() {
    io.println("{} {} {} {}", f(Outcome{ok: 0}), f(Outcome{ok: 2}), f(Outcome{err: 9}), 10 / v)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "0 5 9 2\n"
