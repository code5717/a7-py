"""Literals in if and match arms take the destination type (P2-38).

`y: u8 = if c { 1 } else { 2 }` used to fail: each arm took the i32
default before the declared type was looked at. `char` compares with
`char`; it has no arithmetic without a cast (the SPEC defines none).
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles, run_semantic_analysis


def test_branch_literals_take_the_destination_type(tmp_path, zig):
    source = """\
io :: import "std/io"

pick :: fn(c: bool) u8 {
    ret if c { 200 } else { 2 }
}

main :: fn() {
    c := true
    y: u8 = if c { 250 } else { 2 }
    f: f32 = if c { 1.5 } else { 2.5 }
    base: f32 = 0.25
    g := if c { base } else { 2.5 }
    wide: i64 = if c { 5000000000 } else { 1 }
    m: u8 = match y {
        case 250: 7
        else: 9
    }
    io.println("{} {} {} {} {} {}", y, f, g, wide, pick(false), m)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "250 1.5 0.25 5000000000 2 7\n"


def test_untyped_array_elements_take_the_typed_element_or_the_declared_type(tmp_path, zig):
    source = """\
io :: import "std/io"

main :: fn() {
    a := [1, 2.5, 3]
    x: f32 = 0.5
    b := [x, 2, 3.5]
    m: [2][2]f64 = [[1, 2], [3.5, 4.0]]
    k: u8 = 9
    c := [1, k, 3]
    io.println("{} {} {} {}", a[1], b[2], m[1][0], c[1])
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "2.5 3.5 3.5 9\n"


def test_char_orders_against_char(tmp_path, zig):
    source = """\
io :: import "std/io"

is_lower :: fn(c: char) bool {
    ret c >= 'a' and c <= 'z'
}

main :: fn() {
    io.println("{} {} {}", is_lower('q'), is_lower('Q'), 'a' < 'b')
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "true false true\n"


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        pytest.param("c: char = 'a'\n    c += 1", "char is not a number; convert with cast(u8, c)", id="char-compound-add"),
        pytest.param("c: char = 'a'\n    d := c + 1", "char is not a number; convert with cast(u8, c)", id="char-add"),
        pytest.param("c: char = 'a'\n    if c < 1 { }", "the operands have different types", id="char-ordered-against-integer"),
        pytest.param("y: u8 = if true { 300 } else { 2 }", "300 is out of range for u8", id="branch-literal-out-of-range"),
        pytest.param(
            "x: i32 = 1\n    f: f64 = 1.5\n    y := if true { x } else { f }",
            "If expression branches have different types: expected 'i32', got 'f64'",
            id="branches-of-two-typed-kinds",
        ),
    ],
)
def test_context_typing_rejections(tmp_path, body, fragment):
    result = expect_exit(f"main :: fn() {{\n    {body}\n}}\n", tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details


def test_index_through_a_reference_to_an_array_type_checks():
    """Checker only: `a[0]` on `a: ref [4]i32` reads through the reference.

    This calls the type checker alone and leaves the rest unverified. The
    full pipeline still exits 6 here: the safety pass does not yet prove a
    bound for an index through a reference (a7/passes/safety.py).
    """
    analysis = run_semantic_analysis(
        "first :: fn(a: ref [4]i32) i32 {\n    ret a[0]\n}\n\nmain :: fn() {\n}\n"
    )
    assert [str(error) for error in analysis["checker_errors"]] == []
