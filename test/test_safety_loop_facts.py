"""Facts after a loop (audit P2-52).

A loop may run zero times and a `break` leaves with the condition still true,
so nothing the condition or the body established may survive it. Each rejected
program here compiled before the fix and then trapped, or ran undefined
behaviour in release. Each accepted program is the same shape with the guard
the proof needs, built and run in both profiles.
"""

import pytest

from conftest import expect_exit, expect_ok, run_both_profiles

DIVISOR = "Divisor not proven non-zero"
NON_NIL = "Reference not proven non-nil"
INDEX = "Index not proven in bounds"
MOVED = "Use after move or delete"

BOX = "Box :: struct { value: i32 }\n"


def program(body: str, main: str) -> str:
    return 'io :: import "std/io"\n' + body + "main :: fn() {\n" + main + "}\n"


WHILE_GUARD_BREAK = """f :: fn(d: i32) i32 {
    while d != 0 { break }
    ret 10 / d
}
"""

FOR_GUARD_BREAK = """f :: fn(d: i32) i32 {
    for i := 0; d != 0; i += 1 { break }
    ret 10 / d
}
"""

BODY_GUARD = """f :: fn(d: i32, n: i32) i32 {
    i := 0
    while i < n {
        if d == 0 { ret 0 }
        i += 1
    }
    ret 10 / d
}
"""

LABELED_BREAK = """f :: fn(d: i32) i32 {
    @outer while d != 0 {
        for i := 0; i < 3; i += 1 { break outer }
    }
    ret 10 / d
}
"""

NIL_GUARD_BREAK = BOX + """f :: fn(n: i32) i32 {
    b: ref Box = nil
    if n > 5 { b = new Box }
    while b != nil { break }
    ret b.value
}
"""

BOUND_GUARD_BREAK = """f :: fn(i: usize) i32 {
    arr: [4]i32 = [1, 2, 3, 4]
    s := arr[0..4]
    while i < s.len { break }
    ret s[i]
}
"""

REASSIGN_IN_WHILE = BOX + """f :: fn(n: i32) i32 {
    b := new Box
    if b == nil { ret 0 }
    b.value = 7
    del b
    i := 0
    while i < n {
        b = new Box
        i += 1
    }
    if b != nil { ret b.value }
    ret 0
}
"""

REASSIGN_IN_FOR_IN = BOX + """f :: fn(n: i32) i32 {
    arr: [3]i32 = [1, 2, 3]
    b := new Box
    if b == nil { ret 0 }
    b.value = 7
    del b
    for v in arr[0..0] {
        b = new Box
    }
    if b != nil { ret b.value }
    ret 0
}
"""


@pytest.mark.parametrize("body, call, fragment", [
    (WHILE_GUARD_BREAK, "f(0)", DIVISOR),
    (FOR_GUARD_BREAK, "f(0)", DIVISOR),
    (BODY_GUARD, "f(0, 0)", DIVISOR),
    (LABELED_BREAK, "f(0)", DIVISOR),
    (NIL_GUARD_BREAK, "f(1)", NON_NIL),
    (BOUND_GUARD_BREAK, "f(cast(usize, 9))", INDEX),
    (REASSIGN_IN_WHILE, "f(0)", MOVED),
    (REASSIGN_IN_FOR_IN, "f(0)", MOVED),
], ids=["while-break", "for-break", "body-guard", "labeled-break", "nil", "bounds", "while-reassign", "for-in-reassign"])
def test_fact_from_a_loop_that_ran_zero_times_is_rejected(tmp_path, body, call, fragment):
    expect_exit(program(body, f'    io.println("{{}}", {call})\n'), tmp_path, 6, fragment)


def test_guard_after_the_loop_proves_the_divisor(tmp_path, zig):
    source = program("""f :: fn(d: i32) i32 {
    while d != 0 { break }
    if d != 0 { ret 10 / d }
    ret 0
}
g :: fn(d: i32, n: i32) i32 {
    for i := 0; i < n; i += 1 {
        if d == 0 { ret 0 }
    }
    if d == 0 { ret 0 }
    ret 10 / d
}
""", '    io.println("{} {} {} {}", f(0), f(5), g(0, 0), g(2, 3))\n')
    assert run_both_profiles(source, tmp_path, zig) == "0 2 0 5\n"


def test_false_condition_holds_after_a_loop_without_break(tmp_path, zig):
    """`while n == 0 { ... }` ends only with `n != 0`, so the division is proven."""
    source = program("""f :: fn(d: i32) i32 {
    n := d
    while n == 0 { n = 4 }
    ret 100 / n
}
""", '    io.println("{} {}", f(0), f(5))\n')
    assert run_both_profiles(source, tmp_path, zig) == "25 20\n"


def test_guard_after_the_loop_proves_nil_and_bounds(tmp_path, zig):
    source = program(BOX + """f :: fn(n: i32) i32 {
    b: ref Box = nil
    if n > 5 { b = new Box }
    while b != nil { break }
    if b != nil {
        b.value = n
        r := b.value
        del b
        ret r
    }
    ret -1
}
g :: fn(i: usize) i32 {
    arr: [4]i32 = [1, 2, 3, 4]
    s := arr[0..4]
    while i < s.len { break }
    if i < s.len { ret s[i] }
    ret -1
}
""", '    io.println("{} {} {} {}", f(1), f(9), g(cast(usize, 9)), g(cast(usize, 2)))\n')
    assert run_both_profiles(source, tmp_path, zig) == "-1 9 -1 3\n"


def test_reference_assigned_again_before_the_loop_is_usable_after_it(tmp_path, zig):
    source = program(BOX + """f :: fn(n: i32) i32 {
    b := new Box
    if b == nil { ret 0 }
    del b
    b = new Box
    i := 0
    while i < n {
        if b == nil { b = new Box }
        i += 1
    }
    arr: [2]i32 = [1, 2]
    for v in arr {
        if b == nil { b = new Box }
    }
    if b != nil {
        b.value = 7 + n
        r := b.value
        del b
        ret r
    }
    ret 0
}
""", '    io.println("{} {}", f(0), f(2))\n')
    assert run_both_profiles(source, tmp_path, zig) == "7 9\n"


NONWRAP_AFTER_LOOP = program("""h :: fn(x: i32) i32 {
    while x < 100 { break }
    ret x + 1
}
k :: fn(x: i32) i32 {
    if x < 100 { ret x + 1 }
    ret 0
}
""", '    io.println("{} {}", h(2147483647), k(41))\n')


def test_loop_condition_does_not_approve_a_non_wrapping_add(tmp_path, zig):
    """The loop guard proves nothing about `x`, so `x + 1` keeps the wrapping lowering.

    The `if` guard in `k` still earns the non-wrapping lowering in release.
    """
    release = expect_ok(NONWRAP_AFTER_LOOP, tmp_path, profile="release")
    with open(release.output_path, encoding="utf-8") as handle:
        zig_source = handle.read()
    assert "return (x +% 1);" in zig_source
    assert "return (x + 1);" in zig_source
    assert run_both_profiles(NONWRAP_AFTER_LOOP, tmp_path, zig) == "-2147483648 42\n"


def test_update_statement_is_proven_against_continue_states(tmp_path):
    """`continue` reaches the update with `x == 0`; the body end alone has `x == 5`."""
    source = program("""f :: fn(n: i32) i32 {
    x := 5
    total := 0
    for i := 1; i < n; i += 10 / x {
        if i == 1 {
            x = 0
            if true { continue }
        }
        x = 5
        total += 1
    }
    ret total
}
""", '    io.println("{}", f(3))\n')
    expect_exit(source, tmp_path, 6, DIVISOR)


def test_break_and_continue_branches_do_not_weaken_the_guard(tmp_path, zig):
    """After `if b == nil { continue }` only the non-nil path reaches the next statement."""
    source = program(BOX + """f :: fn(n: i32) i32 {
    total := 0
    for i := 0; i < n; i += 1 {
        b := new Box
        if b == nil { continue }
        b.value = i
        if i == 3 {
            del b
            break
        }
        total += b.value
        del b
    }
    ret total
}
""", '    io.println("{} {}", f(3), f(9))\n')
    assert run_both_profiles(source, tmp_path, zig) == "3 3\n"
