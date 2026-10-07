"""Generic initializer requirements are checked for each concrete call."""

import pytest

from conftest import expect_exit, run_both_profiles


@pytest.mark.parametrize("declaration_first", [True, False])
def test_call_order_does_not_hide_incompatible_literal(tmp_path, declaration_first):
    declaration = 'zero($T) :: fn(a: $T) $T { z: $T = 0; ret z }\n'
    caller = 'main :: fn() { value := zero("text") }\n'
    source = declaration + caller if declaration_first else caller + declaration
    expect_exit(source, tmp_path, 6, "$T instantiated as string")


@pytest.mark.parametrize("calls", [
    'a := zero(1); b := zero("text")',
    'b := zero("text"); a := zero(1)',
])
def test_each_instantiation_is_checked_independently(tmp_path, calls):
    expect_exit('zero($T) :: fn(a: $T) $T { z: $T = 0; ret z }\n'
                + 'main :: fn() { ' + calls + ' }', tmp_path, 6,
                "$T instantiated as string")


def test_forwarded_generic_mapping_reaches_later_function(tmp_path):
    expect_exit('''
main :: fn() { result := forward("text") }
forward($Outer) :: fn(a: $Outer) $Outer { ret middle(a) }
middle($Middle) :: fn(a: $Middle) $Middle { ret zero(a) }
zero($Inner) :: fn(a: $Inner) $Inner { z: $Inner = 0; ret z }
''', tmp_path, 6, "$Inner instantiated as string")


def test_nested_generic_call_checks_its_own_declaration(tmp_path):
    expect_exit('''
zero($T) :: fn(a: $T) $T { z: $T = a; ret z }
outer($U) :: fn(a: $U) $U {
    zero :: fn(b: $V) $V { z: $V = 0; ret z }
    ret zero(a)
}
main :: fn() { result := outer("text") }
''', tmp_path, 6, "$V instantiated as string")


@pytest.mark.parametrize("literal,argument", [
    ("300", "small"),
    ("1.5", "small"),
    ("true", "small"),
    ("'x'", "small"),
    ('"text"', "small"),
])
def test_instantiated_numeric_range_and_kind_are_checked(tmp_path, literal, argument):
    expect_exit('zero($T) :: fn(a: $T) $T { z: $T = ' + literal + '; ret z }\n'
                + 'main :: fn() { small: i8 = 1; result := zero(' + argument + ') }',
                tmp_path, 6, "$T instantiated as i8")


def test_multiple_numeric_and_aggregate_instantiations_run(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
Box :: struct { value: i32 }
zero($T) :: fn(a: $T) $T { z: $T = 0; ret z }
copy($T) :: fn(a: $T) $T { z: $T = a; ret z }
forward($U) :: fn(a: $U) $U { ret zero(a) }
main :: fn() {
    small: i8 = 3
    large: i64 = 4
    real: f64 = 5.5
    b := copy(Box{value: 7})
    xs := copy([8, 9])
    text := copy("ok")
    io.println("{} {} {} {} {} {}", forward(small), zero(large), zero(real), b.value, xs[1], text)
}
''', tmp_path, zig) == "0 0 0 7 9 ok\n"


def test_same_named_nested_functions_do_not_share_requirements(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
number :: fn() i32 {
    zero :: fn(a: $T) $T { z: $T = 0; ret z }
    ret zero(3)
}
text :: fn() string {
    zero :: fn(a: $T) $T { z: $T = ""; ret z }
    ret zero("input")
}
main :: fn() { io.println("{}{}end", number(), text()) }
''', tmp_path, zig) == "0end\n"


def test_initializer_forwarded_from_a_different_generic_parameter_is_checked(tmp_path):
    expect_exit('''
assign($T, $U) :: fn(destination: $T, value: $U) $T {
    result: $T = value
    ret result
}
main :: fn() { value := assign(1, "text") }
''', tmp_path, 6, "$T instantiated as i32")


def test_exact_float_initializer_must_fit_the_instantiated_width(tmp_path):
    expect_exit('''
large($T) :: fn(a: $T) $T { value: $T = 1e39; ret value }
main :: fn() { seed: f32 = 1.0; value := large(seed) }
''', tmp_path, 6, "$T instantiated as f32")


def test_typed_integer_initializer_does_not_convert_to_float(tmp_path):
    expect_exit('''
assign($T, $U) :: fn(destination: $T, value: $U) $T {
    result: $T = value
    ret result
}
main :: fn() {
    destination: f64 = 1.0
    source: i32 = 2
    result := assign(destination, source)
}
''', tmp_path, 6, "$T instantiated as f64")


@pytest.mark.parametrize('expression', [
    'if flag { 0 } else { 100 }',
    'match flag { case true: 0 else: 100 }',
])
def test_generic_branch_initializer_fits_narrow_concrete_type(tmp_path, expression):
    from conftest import expect_ok

    expect_ok('choose :: fn(seed: $T, flag: bool) $T { z: $T = '
              + expression + '; ret z }\n'
              + 'main :: fn() { small: i8 = 0; value := choose(small, true) }', tmp_path)


@pytest.mark.parametrize('expression', [
    'if flag { 0 } else { 300 }',
    'match flag { case true: 0 else: 300 }',
    'if flag { 0 } else { other }',
    'match flag { case true: 0 else: other }',
])
def test_branch_initializer_rejects_overflow_and_typed_narrowing(tmp_path, expression):
    expect_exit('choose :: fn(seed: $T, flag: bool) $T { other: i32 = 1; z: $T = '
                + expression + '; ret z }\n'
                + 'main :: fn() { small: i8 = 0; value := choose(small, true) }',
                tmp_path, 6, '$T instantiated as i8')


def test_branch_initializers_preserve_literal_and_mixed_variable_semantics(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
choose :: fn(seed: $T, flag: bool) $T { z: $T = if flag { 0 } else { 100 }; ret z }
matched :: fn(seed: $T, flag: bool) $T { z: $T = match flag { case true: 0 else: 100 }; ret z }
mixed :: fn(seed: $T, flag: bool, other: i32) $T { z: $T = if flag { 0 } else { other }; ret z }
main :: fn() {
    small: i8 = 1
    wide: i64 = 1
    real: f64 = 1
    io.println("{} {} {} {} {} {}", choose(small, false), choose(wide, true), choose(real, false),
        matched(small, false), mixed(wide, false, 33), mixed(wide, true, 33))
}
''', tmp_path, zig) == '100 0 100 100 33 0\n'
