"""Generic constraints are resolved or rejected, never dropped (P2-3, P2-7).

A constraint that named no type set used to vanish, so `$T: Bogus` and
`$T: Signed` accepted every type. SPEC 7.3 lists the predefined sets
Numeric, Integer, Float, Signed and Unsigned; a `Name :: @type_set(...)`
alias in the file wins over a predefined set of the same name.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles


def test_predefined_sets_and_a_shadowing_alias_run(tmp_path, zig):
    source = """\
io :: import "std/io"

Numeric :: @type_set(i8, i16)

twice($T: Numeric) :: fn(x: $T) $T { ret x + x }
neg($T: Signed) :: fn(x: $T) $T { ret -x }
low($T: Unsigned) :: fn(x: $T) $T { ret x & 15 }
larger :: fn(a: $T, b: $T) $T where T: Integer {
    ret if a > b { a } else { b }
}

main :: fn() {
    small: i8 = 21
    f: f64 = 2.5
    u: u16 = 300
    a: i32 = 3
    b: i32 = 9
    io.println("{} {} {} {} {}", twice(small), neg(a), neg(f), low(u), larger(a, b))
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "42 -3 -2.5 12 9\n"


@pytest.mark.parametrize(
    ("declaration", "call", "fragment"),
    [
        pytest.param(
            "f($T: Bogus) :: fn(x: $T) $T { ret x }", 'f("s")',
            "Constraint of '$T': 'Bogus' is not a type set",
            id="unknown-constraint-name",
        ),
        pytest.param(
            "f($T: SignedInt) :: fn(x: $T) $T { ret x }", "f(1)",
            "'SignedInt' is not a type set",
            id="name-the-spec-does-not-list",
        ),
        pytest.param(
            "f($T: @type_set(i32, Missing)) :: fn(x: $T) $T { ret x }", "f(1)",
            "@type_set member 'Missing' is not a known type",
            id="unresolved-member",
        ),
        pytest.param(
            "f($T: Signed) :: fn(x: $T) $T { ret x }", "f(u)",
            "Generic parameter '$T' requires Signed, got u8",
            id="signed-excludes-unsigned",
        ),
        pytest.param(
            "f($T: Unsigned) :: fn(x: $T) $T { ret x }", "f(1.5)",
            "Generic parameter '$T' requires Unsigned, got f64",
            id="unsigned-excludes-float",
        ),
        pytest.param(
            "Numeric :: @type_set(i8)\nf($T: Numeric) :: fn(x: $T) $T { ret x }", "f(1.5)",
            "Generic parameter '$T' requires @type_set(i8), got f64",
            id="alias-shadows-predefined-set",
        ),
        pytest.param(
            "V :: struct { x: i32 }\nf($T: @type_set(i32, V)) :: fn(x: $T) { }", 'f("s")',
            "Generic parameter '$T' requires @type_set(V, i32), got string",
            id="struct-member-still-constrains",
        ),
    ],
)
def test_constraints_that_do_not_hold_are_rejected(tmp_path, declaration, call, fragment):
    source = f"{declaration}\n\nmain :: fn() {{\n    u: u8 = 1\n    r := {call}\n}}\n"
    if "fn(x: $T) { }" in declaration:
        source = source.replace(f"r := {call}", call)
    result = expect_exit(source, tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details


def test_cast_of_an_integer_constrained_parameter_runs(tmp_path, zig):
    source = """\
io :: import "std/io"

to_f64($T: Integer) :: fn(x: $T) f64 {
    ret cast(f64, x)
}

widen($T: @type_set(i8, i16, i32)) :: fn(x: $T) i64 {
    ret cast(i64, x)
}

same($T: Float) :: fn(x: $T) f64 {
    ret cast(f64, x)
}

main :: fn() {
    a: i32 = 4
    b: f32 = 1.5
    c: i16 = 7
    u: u8 = 200
    io.println("{} {} {} {}", to_f64(a), to_f64(u), widen(c), same(b))
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "4 200 7 1.5\n"


@pytest.mark.parametrize(
    ("function", "fragment"),
    [
        pytest.param(
            "conv :: fn(x: $T) i64 { ret cast(i64, x) }",
            "'$T' has no constraint, so it may be any type; declare it as '$T: Numeric'",
            id="unconstrained-source",
        ),
        pytest.param(
            "conv($T: Numeric) :: fn(x: $T) i64 { ret cast(i64, x) }",
            "the constraint admits",
            id="some-admitted-type-does-not-fit",
        ),
        pytest.param(
            "conv($T: Numeric) :: fn(x: $T) f64 { ret cast(f64, x) }",
            "admits float types, and one cast site converts either integers or floats",
            id="integers-and-floats-in-one-cast",
        ),
    ],
)
def test_cast_of_a_parameter_that_may_not_convert_is_rejected(tmp_path, function, fragment):
    result = expect_exit(f"{function}\n\nmain :: fn() {{\n}}\n", tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details
