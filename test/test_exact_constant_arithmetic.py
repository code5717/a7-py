"""Untyped constant arithmetic is exact and the result must fit its destination.

Ledger L61 (`docs/plan/decisions.md`) and SPEC 4.2.1. The first half checks
`a7/exact_constants.py` directly; the second half runs whole programs through
the compiler and, where they are accepted, through Zig 0.16.0 in the debug and
fast profiles. Expected values are worked out by hand from the A7 source.

Not covered: the work-credit and cache-size caps of SPEC Appendix C, which the
evaluator does not enforce.
"""

from fractions import Fraction
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from a7.ast_nodes import BinaryOp
from a7.exact_constants import (
    ExactArithmeticError, compare, evaluate, ieee_bits, render,
)
from conftest import expect_exit, expect_ok, parse_program, run_both_profiles

ROOT = Path(__file__).resolve().parents[1]


def exact(expression):
    """Evaluate one constant expression with no named constants in scope."""
    declaration = parse_program("X :: " + expression + "\n").declarations[0]
    return evaluate(declaration.value, lambda name: None, {})


def f64_bits(value):
    return struct.unpack(">Q", struct.pack(">d", value))[0]


# ---------------------------------------------------------------------------
# The evaluator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expression, value", [
    ("2147483647 + 1", 2147483648),
    ("-2147483647 - 2", -2147483649),
    ("65536 * 65536", 4294967296),
    ("30 * 24 * 60 * 60 * 1000", 2592000000),
    ("-17 / 5", -3),
    ("-17 % 5", -2),
    ("17 % -5", 2),
    ("5 / 2", 2),
    ("(6 & 3) | 8", 10),
    ("6 ^ 3", 5),
    ("1 << 40", 1099511627776),
    ("-3 >> 1", -2),
    ("1 >> 99999999999999999999", 0),
    ("-1 >> 99999999999999999999", -1),
])
def test_integer_constants_are_mathematical_integers(expression, value):
    assert exact(expression) == (Fraction(value), False)


@pytest.mark.parametrize("expression, value", [
    ("5.0 / 2", Fraction(5, 2)),
    ("5 / 2.0", Fraction(5, 2)),
    ("-5.5 % 2.0", Fraction(-3, 2)),
    ("5.5 % -2.0", Fraction(3, 2)),
    ("0.1 + 0.2", Fraction(3, 10)),
    ("1e308 * 10.0", Fraction(10) ** 309),
    ("1e4096", Fraction(10) ** 4096),
])
def test_a_floating_operand_gives_an_exact_rational(expression, value):
    assert exact(expression) == (value, True)


def test_comparison_uses_exact_values():
    assert compare(BinaryOp.EQ, exact("0.1 + 0.2"), exact("0.3")) is True
    assert compare(BinaryOp.EQ, exact("2"), exact("2.0")) is True
    assert compare(BinaryOp.LT, exact("1e308 * 5.0"), exact("1e308 * 10.0")) is True
    assert compare(BinaryOp.NE, exact("0.0"), exact("-0.0")) is False
    # 2**53 + 1 and 2**53 are the same f64.
    assert compare(BinaryOp.GT, exact("9007199254740993.0"), exact("9007199254740992.0")) is True


@pytest.mark.parametrize("expression, negative", [
    ("0.0 * -1.0", True),
    ("1.0 * -0.0", True),
    ("0 * -1.0", True),
    ("-0.0 * -1.0", False),
    ("0.0 / -2.0", True),
    ("-4.0 % 2.0", True),
    ("4.0 % -2.0", False),
    ("-0.0 + -0.0", True),
    ("-0.0 + 0.0", False),
    ("1.0 - 1.0", False),
    ("-1.0 + 1.0", False),
    ("-0.0 - 0.0", True),
    ("0.0 - 0.0", False),
    ("-0.0", True),
    ("-(-0.0)", False),
])
def test_a_floating_zero_takes_the_ieee_sign(expression, negative):
    value = exact(expression)
    assert value[0] == 0
    assert ieee_bits(value, 64) == (1 << 63 if negative else 0)
    assert ieee_bits(value, 32) == (1 << 31 if negative else 0)


@pytest.mark.parametrize("expression, fragment", [
    ("1.0 / 0.0", "division by zero"),
    ("1 / 0.0", "division by zero"),
    ("0.0 / 0.0", "division by zero"),
    ("1.0 % 0.0", "remainder by zero"),
    ("1 << -1", "shift count is negative"),
    ("8 >> -1", "shift count is negative"),
    ("1e4097", "exponent exceeds the limit of 4096"),
    ("1e-4097", "exponent exceeds the limit of 4096"),
    ("1e999999999", "exponent exceeds the limit of 4096"),
    ("1 << 131073", "exceeds the limit of 131072 bits"),
    ("1 << 99999999999999999999", "exceeds the limit of 131072 bits"),
])
def test_rejected_constants_raise(expression, fragment):
    with pytest.raises(ExactArithmeticError, match=fragment):
        exact(expression)


def test_the_largest_allowed_component_is_131072_bits():
    assert exact("1 << 131071") == (Fraction(2 ** 131071), False)


@pytest.mark.parametrize("expression", ["1 / 0", "1 % 0", "2.0 & 3", "1 << 2.0", "~1"])
def test_expressions_owned_by_another_diagnostic_are_not_constants(expression):
    # The safety pass reports an integer zero divisor, the type checker
    # reports a floating operand of a bitwise operator, and `~` stays a
    # typed operator.
    assert exact(expression) is None


def test_float_fitting_rounds_once_to_the_destination_width():
    assert ieee_bits(exact("0.1 + 0.2"), 64) == f64_bits(0.3)
    assert f64_bits(0.1 + 0.2) != f64_bits(0.3)
    # Just above the midpoint of 1.0 and the next f32. Rounding through f64
    # first lands on the midpoint and then ties down to 1.0.
    above_tie = (Fraction(1) + Fraction(1, 2 ** 24) + Fraction(1, 2 ** 60), True)
    assert ieee_bits(above_tie, 32) == 0x3F800001
    assert ieee_bits((Fraction(1, 2 ** 1074), True), 64) == 1
    assert ieee_bits((Fraction(1, 2 ** 1080), True), 64) == 0


def test_a_finite_value_beyond_the_float_range_is_refused():
    assert ieee_bits(exact("1.7976931348623157e308"), 64) == 0x7FEFFFFFFFFFFFFF
    with pytest.raises(ExactArithmeticError, match="overflows f64"):
        ieee_bits(exact("1e308 * 10.0"), 64)
    with pytest.raises(ExactArithmeticError, match="overflows f32"):
        ieee_bits(exact("1e39"), 32)


def test_render_elides_the_middle_of_a_long_integer():
    assert render(Fraction(-2147483649)) == "-2147483649"
    assert render(Fraction(5, 2)) == "5/2"
    assert render(Fraction(7 * 10 ** 3000 + 123456789012)) == "700000000000...123456789012 (3001 digits)"
    # 40000 digits is past the length Python's str() accepts for an integer.
    assert render(Fraction(-(10 ** 39999 + 1))) == "-100000000000...000000000001 (40000 digits)"


# ---------------------------------------------------------------------------
# Whole programs
# ---------------------------------------------------------------------------

def program(body, declarations=""):
    return 'io :: import "std/io"\n' + declarations + 'main :: fn() {\n' + body + '}\n'


def test_integer_constants_do_not_wrap_at_i32(tmp_path, zig):
    assert run_both_profiles(program(
        '    ms: i64 = MONTH_MS\n'
        '    a: i64 = 2147483647 + 1\n'
        '    b: i64 = 65536 * 65536\n'
        '    io.println("{} {} {}", ms, a, b)\n',
        'MONTH_MS :: 30 * 24 * 60 * 60 * 1000\n',
    ), tmp_path, zig) == "2592000000 2147483648 4294967296\n"


def test_typed_arithmetic_still_wraps(tmp_path, zig):
    assert run_both_profiles(program(
        '    a: i32 = 2147483647\n'
        '    b := a + 1\n'
        '    io.println("{}", b)\n'
    ), tmp_path, zig) == "-2147483648\n"


@pytest.mark.parametrize("statement, fragment", [
    ("x: i32 = 2147483647 + 1", "Exact constant 2147483648 is out of range for i32"),
    ("x: u8 = 255 + 1", "Exact constant 256 is out of range for u8"),
    ("x: i32 = 5.0 / 2", "Exact constant 5/2 is fractional and cannot fit i32"),
])
def test_a_constant_that_does_not_fit_its_destination_is_rejected(tmp_path, statement, fragment):
    expect_exit(program('    ' + statement + '\n    io.println("{}", x)\n'), tmp_path, 6, fragment)


def test_an_array_length_is_the_exact_product(tmp_path):
    # 65536 * 65536 + 3 once wrapped to 3. The program is compiled, not
    # built: Zig refuses a 4 GiB stack array.
    result = expect_ok(program('    buf: [65536 * 65536 + 3]u8\n    buf[0] = 1\n'), tmp_path)
    assert "[4294967299]u8" in Path(result.output_path).read_text(encoding="utf-8")


def test_decimal_constants_compare_exactly_and_round_once(tmp_path, zig):
    # 0.1 + 0.2 is exactly 0.3 as a constant. Two f64 variables add to the
    # neighbouring f64, 0.30000000000000004.
    assert run_both_profiles(program(
        '    s: f64 = 0.1 + 0.2\n'
        '    t: f64 = 0.3\n'
        '    a: f64 = 0.1\n'
        '    b: f64 = 0.2\n'
        '    io.println("{} {} {}", 0.1 + 0.2 == 0.3, s == t, a + b == t)\n'
    ), tmp_path, zig) == "true true false\n"


@pytest.mark.parametrize("body, declarations", [
    ('    b: f64 = 1e308 * 10.0\n    io.println("{}", b)\n', ''),
    ('    b: f64 = BIG\n    io.println("{}", b)\n', 'BIG :: 1e308 * 10.0\n'),
], ids=["direct", "named-constant"])
def test_a_finite_constant_that_rounds_to_infinity_is_rejected(tmp_path, body, declarations):
    expect_exit(program(body, declarations), tmp_path, 6, "Finite exact constant overflows f64")


@pytest.mark.parametrize("expression, kind, fragment", [
    ("1.0 / 0.0", "f64", "Constant division by zero"),
    ("1.0 % 0.0", "f64", "Constant remainder by zero"),
    ("1 / 0", "i32", "Divisor not proven non-zero"),
    ("1 % 0", "i32", "Divisor not proven non-zero"),
])
def test_constant_division_by_zero_is_rejected(tmp_path, expression, kind, fragment):
    expect_exit(
        program('    x: ' + kind + ' = ' + expression + '\n    io.println("{}", x)\n'),
        tmp_path, 6, fragment,
    )


def test_a_zero_product_with_a_negative_factor_is_negative_zero(tmp_path, zig):
    assert run_both_profiles(program(
        '    a: f64 = 0.0 * -1.0\n'
        '    b: f64 = 1.0 * -0.0\n'
        '    c: f64 = 0.0 - 0.0\n'
        '    d: f64 = -0.0 * -1.0\n'
        '    io.println("{} {} {} {}", a, b, c, d)\n'
    ), tmp_path, zig) == "-0 -0 0 0\n"


def test_bitwise_not_of_a_literal_stays_a_typed_operation(tmp_path, zig):
    # As an exact constant `~1` would be -2, which no unsigned mask accepts.
    assert run_both_profiles(program(
        '    flags: u8 = 7\n'
        '    io.println("{} {}", flags & ~1, ~5)\n'
    ), tmp_path, zig) == "6 -6\n"


@pytest.mark.parametrize("initializer", [
    "if c { 5000000000 } else { 1 }",
    "match n { case 1: 5000000000 else: 2 }",
], ids=["if", "match"])
def test_constant_arms_fit_the_declared_type_of_the_expression(tmp_path, zig, initializer):
    assert run_both_profiles(program(
        '    c := true\n'
        '    n := 1\n'
        '    y: i64 = ' + initializer + '\n'
        '    io.println("{}", y)\n'
    ), tmp_path, zig) == "5000000000\n"


def test_a_constant_arm_that_does_not_fit_is_rejected(tmp_path):
    expect_exit(program(
        '    c := true\n'
        '    y: u8 = if c { 256 } else { 1 }\n'
        '    io.println("{}", y)\n'
    ), tmp_path, 6, "Exact constant 256 is out of range for u8")


def test_constant_shifts_and_bitwise_operators_are_exact(tmp_path, zig):
    assert run_both_profiles(program(
        '    d: i64 = 1 << 40\n'
        '    top: u64 = 1 << 63\n'
        '    back: i64 = 1 << 70 >> 60\n'
        '    low: u32 = 0xFFFFFFFF & 0xFF\n'
        '    io.println("{} {} {} {} {}", d, top, back, low, -3 >> 1)\n'
    ), tmp_path, zig) == "1099511627776 9223372036854775808 1024 255 -2\n"


@pytest.mark.parametrize("statement, value", [
    ("y := 5000000000", "5000000000"),
    ('io.println("{}", 5000000000)', "5000000000"),
    ('io.println("{}", id(5000000000))', "5000000000"),
    ("y := 1 << 40", "1099511627776"),
], ids=["inferred-variable", "format-argument", "generic-inference", "shift"])
def test_an_integer_with_no_destination_defaults_to_i32(tmp_path, statement, value):
    result = expect_exit(
        program('    ' + statement + '\n', 'id($T) :: fn(x: $T) $T { ret x }\n'),
        tmp_path, 6,
        "Exact constant " + value + " does not fit default i32; use an explicit destination type",
    )
    assert len(result.failure.details) == 1, result.failure.details


def test_an_explicit_i64_carries_a_large_constant_through_every_default_context(tmp_path, zig):
    assert run_both_profiles(program(
        '    y: i64 = 5000000000\n'
        '    io.println("{} {}", y, id(y))\n',
        'id($T) :: fn(x: $T) $T { ret x }\n',
    ), tmp_path, zig) == "5000000000 5000000000\n"


def test_an_exponent_past_the_cap_is_rejected_without_evaluating_it(tmp_path):
    # Runs in a subprocess with a timeout: before the cap, building the
    # exact value of this literal did not finish.
    source = tmp_path / "main.a7"
    source.write_text(program('    x := 1e999999999\n    io.println("{}", x)\n'), encoding="utf-8")
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), "--mode", "pipeline"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert process.returncode == 6, process.stdout + process.stderr
    assert "exponent exceeds the limit of 4096" in " ".join((process.stdout + process.stderr).split())


@pytest.mark.parametrize("initializer, fragment", [
    ("1e4300", "Float literal exponent exceeds the limit of 4096"),
    # 12345678901234567890 is about 10**19.0915, so the product of 240 of
    # them has 4582 digits, more than Python's str() will format.
    (" * ".join(["12345678901234567890"] * 240), "(4582 digits) is out of range for i32"),
    ("1e4000", "(4001 digits) is out of range for i32"),
], ids=["exponent-cap", "long-product", "long-literal"])
def test_a_huge_constant_is_a_located_error_not_an_internal_one(tmp_path, initializer, fragment):
    result = expect_exit(
        program('    x: i32 = ' + initializer + '\n    io.println("{}", x)\n'),
        tmp_path, 6, fragment,
    )
    assert len(result.failure.details) == 1, result.failure.details


@pytest.mark.parametrize("value, fragment", [
    ("1e99999", "Float literal exponent exceeds the limit of 4096"),
    ("2.5", "Exact constant 5/2 is fractional and cannot fit i32"),
    ("18446744073709551616", "Exact constant 18446744073709551616 is out of range for u64"),
])
def test_an_enum_value_must_be_an_integer_that_fits_the_tag(tmp_path, value, fragment):
    expect_exit(
        'E :: enum { A = ' + value + ' }\nmain :: fn() {\n    e := E.A\n}\n',
        tmp_path, 6, fragment,
    )


def test_an_enum_value_expression_is_emitted_as_its_exact_integer(tmp_path):
    result = expect_ok(
        'E :: enum { A = 1 << 4, B = 6.0 / 2 }\nmain :: fn() {\n    e := E.A\n}\n',
        tmp_path,
    )
    emitted = Path(result.output_path).read_text(encoding="utf-8")
    assert "A = 16," in emitted and "B = 3," in emitted
