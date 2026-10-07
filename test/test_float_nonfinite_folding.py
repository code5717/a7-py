"""Infinity and NaN come from typed run-time arithmetic, never from a constant.

Ledger L61 (`docs/plan/decisions.md`) makes untyped constant arithmetic exact:
`1e308 * 10.0` is the finite number 1e309, so it compares as 1e309 and is
refused by an f64 destination instead of becoming infinity. Ledger L16 still
makes infinity and NaN ordinary values of typed f64 arithmetic.

Each constant program below has a typed twin that moves one operand into an
`f64` variable. The twin must give the IEEE answer and the constant program
the exact answer. Expected outputs are derived by hand from the A7 source.
Programs are built with Zig 0.16.0 in Debug and ReleaseFast.

NaN is never asserted through its printed text. IEEE 754 does not specify the
sign bit of a NaN and Zig prints `nan` or `-nan` depending on where the value
came from, so NaN is observed through predicates (`n != n`) instead.
"""

import pytest
from conftest import expect_exit, run_both_profiles


def program(body):
    return 'io :: import "std/io"\n\nmain :: fn() {\n' + body + '}\n'


# ---------------------------------------------------------------------------
# Comparisons over a product that exceeds f64.
#
# Exact: 1e309 > 5e308, the two differ, and 1e309 - 1e309 is 0.
# IEEE f64: both products are +inf, so inf > inf is false, inf == inf is
# true, and inf - inf is NaN, which equals nothing, itself included.
# ---------------------------------------------------------------------------

def test_constant_comparison_over_a_product_beyond_f64_is_exact(tmp_path, zig):
    assert run_both_profiles(program(
        '    a := 1e308 * 10.0 > 1e308 * 5.0\n'
        '    b := 1e308 * 10.0 == 1e308 * 5.0\n'
        '    c := (1e308 * 10.0 - 1e308 * 10.0) == 0.0\n'
        '    d := (1e308 * 10.0 - 1e308 * 10.0) == (1e308 * 10.0 - 1e308 * 10.0)\n'
        '    e := (1e308 * 10.0 - 1e308 * 10.0) != (1e308 * 10.0 - 1e308 * 10.0)\n'
        '    io.println("{} {} {} {} {}", a, b, c, d, e)\n'
    ), tmp_path, zig) == "true false true true false\n"


def test_typed_comparison_over_an_overflowing_product_is_ieee(tmp_path, zig):
    assert run_both_profiles(program(
        '    big: f64 = 1e308\n'
        '    a := big * 10.0 > big * 5.0\n'
        '    b := big * 10.0 == big * 5.0\n'
        '    c := (big * 10.0 - big * 10.0) == 0.0\n'
        '    d := (big * 10.0 - big * 10.0) == (big * 10.0 - big * 10.0)\n'
        '    e := (big * 10.0 - big * 10.0) != (big * 10.0 - big * 10.0)\n'
        '    io.println("{} {} {} {} {}", a, b, c, d, e)\n'
    ), tmp_path, zig) == "false true false false true\n"


@pytest.mark.parametrize("declaration, stdout", [
    ("", "greater\n"),
    ("    big: f64 = 1e308\n", "not greater\n"),
], ids=["constant", "typed"])
def test_if_over_a_product_beyond_f64(tmp_path, zig, declaration, stdout):
    left = "big" if declaration else "1e308"
    assert run_both_profiles(program(
        declaration +
        '    if ' + left + ' * 10.0 > ' + left + ' * 5.0 {\n'
        '        io.println("greater")\n'
        '    } else {\n'
        '        io.println("not greater")\n'
        '    }\n'
    ), tmp_path, zig) == stdout


# ---------------------------------------------------------------------------
# A finite constant that rounds to infinity is refused by its destination.
# test_exact_constant_arithmetic.py holds the positive and named-constant cases.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source", [
    program('    x: f64 = -1.0e308 * 10.0\n    io.println("{}", x)\n'),
    # A return type is a destination too.
    'big_value :: fn() f64 {\n    ret 1.0e308 * 10.0\n}\n'
    'main :: fn() {\n    x: f64 = big_value()\n    if x > 0.0 {\n        ret\n    }\n}\n',
    # 1e39 is finite in f64 and beyond f32.
    program('    x: f32 = 1e38 * 10.0\n    io.println("{}", x)\n'),
], ids=["negative", "return", "f32"])
def test_constant_overflowing_its_float_destination_is_rejected(tmp_path, source):
    expect_exit(source, tmp_path, 6, "Finite exact constant overflows f")


@pytest.mark.parametrize("statement, stdout", [
    ("x := big * 10.0", "inf\n"),
    ("x := -big * 10.0", "-inf\n"),
    ("x := big * 10.0 / 100.0", "inf\n"),
], ids=["inf", "negative-inf", "compound-overflow"])
def test_typed_overflow_prints_infinity(tmp_path, zig, statement, stdout):
    assert run_both_profiles(program(
        '    big: f64 = 1.0e308\n'
        '    ' + statement + '\n'
        '    io.println("{}", x)\n'
    ), tmp_path, zig) == stdout


def test_constant_with_an_intermediate_beyond_f64_fits_when_the_result_does(tmp_path, zig):
    # 1e308 * 10.0 / 100.0 is exactly 1e307. The intermediate 1e309 never
    # needs an f64, so nothing overflows.
    assert run_both_profiles(program(
        '    x: f64 = 1.0e308 * 10.0 / 100.0\n'
        '    y: f64 = 1e307\n'
        '    io.println("{}", x == y)\n'
    ), tmp_path, zig) == "true\n"


@pytest.mark.parametrize("statement", [
    "n := big * 10.0 - big * 10.0",
    "n := big * 10.0 * 0.0",
], ids=["inf-minus-inf", "inf-times-zero"])
def test_typed_nan_behaves_as_nan(tmp_path, zig, statement):
    assert run_both_profiles(program(
        '    big: f64 = 1.0e308\n'
        '    ' + statement + '\n'
        '    io.println("{} {} {}", n == n, n != n, n == 0.0)\n'
    ), tmp_path, zig) == "false true false\n"


@pytest.mark.parametrize("statement", [
    "n: f64 = 1.0e308 * 10.0 - 1.0e308 * 10.0",
    "n: f64 = 1.0e308 * 10.0 * 0.0",
], ids=["difference", "times-zero"])
def test_constant_that_is_exactly_zero_is_zero_not_nan(tmp_path, zig, statement):
    assert run_both_profiles(program(
        '    ' + statement + '\n'
        '    io.println("{} {} {}", n == n, n != n, n == 0.0)\n'
    ), tmp_path, zig) == "true false true\n"


def test_float_remainder_constants_match_native_values(tmp_path, zig):
    # Truncated quotients leave the dividend's sign: -5.5 - (-2)*2 = -1.5.
    # The runtime expressions use typed locals; expected values are independent
    # of either implementation. Positive, negative, and exact division differ.
    assert run_both_profiles(program(
        '    x: f64 = -5.5\n'
        '    p: f64 = 5.5\n'
        '    exact: f64 = -4.0\n'
        '    y: f64 = 2.0\n'
        '    io.println("{} {} {} {} {} {}", -5.5 % 2.0, x % y, 5.5 % 2.0, p % y, -4.0 % 2.0, exact % y)\n'
    ), tmp_path, zig) == "-1.5 -1.5 1.5 1.5 -0 -0\n"
