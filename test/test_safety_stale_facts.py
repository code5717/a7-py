"""Facts that outlive the value they describe.

- Unary minus (audit P2-56): `-x` for `x == MIN` wraps to `MIN`, so the
  negated interval is not a fact about the result.
- Match `fall`: the next arm also starts from the falling arm's end state.
- File-scope variables: a called function can assign them.

Each rejected program compiled before the fix and then trapped.
"""

from conftest import expect_exit, run_both_profiles

IO = 'io :: import "std/io"\n'


def test_negated_minimum_does_not_prove_a_cast(tmp_path):
    source = IO + """f :: fn(x: i32) i32 {
    arr: [4]i32 = [1, 2, 3, 4]
    if x >= 0 { ret 0 }
    y := -x
    if y > 3 { ret 0 }
    ret arr[cast(usize, y)]
}
main :: fn() { io.println("{}", f(-2147483648)) }
"""
    expect_exit(source, tmp_path, 6, "signed-to-unsigned cast requires a non-negative proof")


def test_negation_of_a_bounded_value_proves_the_index(tmp_path, zig):
    source = IO + """f :: fn(x: i32) i32 {
    arr: [4]i32 = [1, 2, 3, 4]
    if x >= 0 { ret 0 }
    if x < -3 { ret 0 }
    y := -x
    ret arr[cast(usize, y)]
}
main :: fn() { io.println("{} {} {}", f(-2), f(-2147483648), f(4)) }
"""
    assert run_both_profiles(source, tmp_path, zig) == "3 0 0\n"


def test_arm_reached_by_fall_sees_the_falling_arm_state(tmp_path):
    source = IO + """f :: fn(n: i32) i32 {
    x := 5
    r := 1
    match n {
        case 1: {
            x = 0
            fall
        }
        case 2: { r = 10 / x }
        else: { r = 3 }
    }
    ret r
}
main :: fn() { io.println("{}", f(1)) }
"""
    expect_exit(source, tmp_path, 6, "Divisor not proven non-zero")


def test_guarded_arm_reached_by_fall_divides(tmp_path, zig):
    source = IO + """f :: fn(n: i32) i32 {
    x := 5
    r := 1
    match n {
        case 1: {
            x = 0
            fall
        }
        case 2: {
            if x != 0 { r = 10 / x }
        }
        else: { r = 3 }
    }
    ret r
}
main :: fn() { io.println("{} {} {}", f(1), f(2), f(7)) }
"""
    assert run_both_profiles(source, tmp_path, zig) == "1 2 3\n"


def test_file_scope_variable_fact_does_not_survive_a_call(tmp_path):
    source = IO + """g := 5
zero :: fn() { g = 0 }
main :: fn() {
    g = 5
    zero()
    io.println("{}", 10 / g)
}
"""
    expect_exit(source, tmp_path, 6, "Divisor not proven non-zero")


def test_file_scope_variable_guarded_after_the_call_divides(tmp_path, zig):
    source = IO + """g := 5
zero :: fn() { g = 0 }
main :: fn() {
    g = 5
    io.println("{}", 10 / g)
    zero()
    if g != 0 { io.println("{}", 10 / g) }
    g = 2
    io.println("{}", 10 / g)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "2\n5\n"
