"""Expression traversal preserves facts at the point each operand is visited."""

from conftest import expect_exit, expect_ok


def test_borrowing_an_argument_invalidates_the_later_divisor(tmp_path):
    source = """take :: fn(d: ref i32, n: i32) { d = n }
main :: fn() {
    d := 5
    take(d, 10 / d)
}
"""
    expect_exit(source, tmp_path, 6, "Divisor not proven non-zero")


def test_division_before_the_borrow_keeps_its_proof(tmp_path):
    source = """take :: fn(n: i32, d: ref i32) { d = n }
main :: fn() {
    d := 5
    take(10 / d, d)
}
"""
    expect_ok(source, tmp_path)


def test_nested_deleting_call_invalidates_the_later_argument(tmp_path):
    source = """Box :: struct { value: i32 }
drop :: fn(b: ref Box) i32 { del b; ret 0 }
take :: fn(n: i32, b: ref Box) { b.value = n }
main :: fn() {
    b := new Box
    if b == nil { ret }
    take(drop(b), b)
}
"""
    expect_exit(source, tmp_path, 6, "Use after move or delete")


def test_left_operand_range_survives_a_later_borrow(tmp_path):
    source = """mutate :: fn(x: ref i32) i32 { x = 999; ret 0 }
main :: fn() {
    x := 1
    y := cast(u8, x + cast(i32, [mutate(x)][0..1].len))
}
"""
    # The left operand was 1. The right operand's one-element slice has length 1,
    # even though its call invalidates the current symbol fact for x.
    expect_ok(source, tmp_path)
