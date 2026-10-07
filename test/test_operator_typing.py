"""Operator operand rules the backend can honor (P2-34, P2-35, P2-4).

Zig rejects `i32 & i64`, arithmetic on a type parameter that may be any
type, `==` on structs, arrays, slices and unions, and a typed integer
stored in a float. The checker used to accept all of them.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles

DECLARATIONS = """\
P :: struct { x: i32 }
U :: union { a: i32, b: f64 }
halve :: fn(v: f64) f64 { ret v / 2.0 }
"""


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        pytest.param(
            "a: i32 = 1\n    b: i64 = 2\n    c := a & b",
            "bit_and between i32 and i64: both operands need the same integer type",
            id="and-of-two-widths",
        ),
        pytest.param(
            "a: u8 = 1\n    b: u16 = 2\n    c := a | b",
            "bit_or between u8 and u16",
            id="or-of-two-widths",
        ),
        pytest.param(
            "a: i32 = 1\n    b: u32 = 2\n    c := a ^ b",
            "bit_xor between i32 and u32",
            id="xor-of-two-signs",
        ),
        pytest.param("i: i32 = 1\n    i <<= 40", "Shift count must be non-negative and less than 32", id="compound-shl"),
        pytest.param("i: u8 = 1\n    i >>= 8", "Shift count must be non-negative and less than 8", id="compound-shr"),
        pytest.param("a := P{x: 1}\n    b := P{x: 1}\n    if a == b { }", "'P' values have no == or !=", id="struct-equality"),
        pytest.param(
            "a: [2]i32 = [1, 2]\n    b: [2]i32 = [1, 2]\n    if a == b { }",
            "'[2]i32' values have no == or !=",
            id="array-equality",
        ),
        pytest.param(
            "a: [2]i32 = [1, 2]\n    s := a[0..1]\n    t := a[0..1]\n    if s != t { }",
            "'[]i32' values have no == or !=",
            id="slice-equality",
        ),
        pytest.param("a := U{a: 1}\n    b := U{a: 1}\n    if a == b { }", "'U' values have no == or !=", id="union-equality"),
        pytest.param("a: i64 = 3\n    x: f64 = a", "write cast(f64, a)", id="integer-variable-into-float"),
        pytest.param("a: i32 = 3\n    x := halve(a)", "write cast(f64, a)", id="integer-variable-into-float-parameter"),
        pytest.param(
            "a: i32 = 3\n    b: f64 = 1.5\n    c := a + b",
            "add between i32 and f64; use an explicit cast",
            id="integer-plus-float-variables",
        ),
    ],
)
def test_operands_the_backend_cannot_combine_are_rejected(tmp_path, body, fragment):
    source = f"{DECLARATIONS}\nmain :: fn() {{\n    {body}\n}}\n"
    result = expect_exit(source, tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details


@pytest.mark.parametrize(
    ("function", "fragment"),
    [
        pytest.param("add :: fn(a: $T, b: $T) $T { ret a + b }", "declare it as '$T: Numeric'", id="arithmetic"),
        pytest.param("same :: fn(a: $T, b: $T) bool { ret a == b }", "declare it as '$T: Numeric'", id="equality"),
        pytest.param("less :: fn(a: $T, b: $T) bool { ret a < b }", "declare it as '$T: Numeric'", id="ordering"),
        pytest.param("mask :: fn(a: $T) $T { ret a & 1 }", "declare it as '$T: Integer'", id="bitwise"),
        pytest.param("neg :: fn(a: $T) $T { ret -a }", "declare it as '$T: Numeric'", id="negation"),
        pytest.param(
            "inc :: fn(a: $T) $T {\n    b: $T = a\n    b += a\n    ret b\n}",
            "declare it as '$T: Numeric'",
            id="compound-assignment",
        ),
    ],
)
def test_an_unconstrained_type_parameter_takes_no_operator(tmp_path, function, fragment):
    # `add(true, false)` used to pass: the parameter counted as a number.
    result = expect_exit(f"{function}\n\nmain :: fn() {{\n}}\n", tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details


def test_same_type_bitwise_operators_and_in_range_compound_shifts_run(tmp_path, zig):
    source = """\
io :: import "std/io"

main :: fn() {
    a: i32 = 12
    b: i32 = 10
    w: i64 = 255
    s: i32 = 1
    s <<= 4
    s >>= 1
    io.println("{} {} {} {} {}", a & b, a | 1, w ^ 15, cast(i64, a) & w, s)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "8 13 240 12 8\n"


def test_constrained_generic_arithmetic_and_comparison_run(tmp_path, zig):
    source = """\
io :: import "std/io"

abs($T: Signed) :: fn(x: $T) $T {
    ret if x < 0 { -x } else { x }
}

sum :: fn(xs: []$T) $T where T: Numeric {
    total: $T = 0
    for x in xs {
        total += x
    }
    ret total
}

low_bits($T: Unsigned) :: fn(x: $T) $T { ret x & 15 }

main :: fn() {
    v: i32 = -4
    values: [3]i64 = [1, 2, 3]
    u: u16 = 300
    io.println("{} {} {} {}", abs(v), abs(-2.5), sum(values[0..3]), low_bits(u))
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "4 2.5 6 12\n"


def test_comparable_types_and_untyped_integers_into_floats_run(tmp_path, zig):
    source = """\
io :: import "std/io"

Color :: enum { Red, Blue }

main :: fn() {
    s := "hi"
    c := Color.Blue
    flag := true
    x: f64 = 3
    x += 2
    hits := 0
    if s == "hi" { hits += 1 }
    if s != "no" { hits += 1 }
    if c == Color.Blue { hits += 1 }
    if flag != false { hits += 1 }
    if 'a' == 'a' { hits += 1 }
    io.println("{} {}", hits, x)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "5 5\n"
