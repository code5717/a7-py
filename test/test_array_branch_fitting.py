"""A declared array element type applies to every selected literal arm."""

import pytest

from conftest import expect_exit, expect_ok, failure_text, run_both_profiles


@pytest.mark.parametrize("expression", [
    "if flag { [1, 2] } else { [3, 4] }",
    "match flag { case true: [1, 2] else: [3, 4] }",
])
@pytest.mark.parametrize("context", ["ordinary", "generic", "callback"])
def test_literal_array_branches_fit_the_destination(tmp_path, expression, context):
    if context == "ordinary":
        source = ('choose :: fn(flag: bool) { value: [2]i8 = ' + expression
                  + ' }\nmain :: fn() { choose(true); choose(false) }')
    elif context == "generic":
        source = ('choose :: fn(seed: $T, flag: bool) $T { value: $T = '
                  + expression + '; ret value }\n'
                  + 'main :: fn() { seed: [2]i8 = [0, 0]; '
                  + 'a := choose(seed, true); b := choose(seed, false) }')
    else:
        source = ('invoke :: fn(f: fn([2]$T), flag: bool) { f(' + expression
                  + ') }\nsmall :: fn(value: [2]i8) {}\n'
                  + 'main :: fn() { invoke(small, true); invoke(small, false) }')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize("expression,diagnostic", [
    ("if flag { [1, 2] } else { [3, 300] }", "300 is out of range for i8"),
    ("match flag { case true: [1, 2] else: [3, 300] }", "300 is out of range for i8"),
    ("if flag { wide } else { wide }", "expected '[2]i8', got '[2]i32'"),
    ("match flag { case true: [1, 2, 3] else: [4, 5, 6] }", "mismatch"),
    ("if flag { [true, false] } else { [false, true] }", "mismatch"),
])
def test_declared_array_rejects_nonfitting_branch_elements(tmp_path, expression, diagnostic):
    expect_exit('choose :: fn(flag: bool) { wide: [2]i32 = [1, 2]; '
                + 'value: [2]i8 = ' + expression + ' }\n'
                + 'main :: fn() { choose(true) }', tmp_path, 6, diagnostic)


def test_generic_array_branch_does_not_narrow_typed_values(tmp_path):
    expect_exit('''
choose :: fn(seed: $T, flag: bool) $T {
    wide: [2]i32 = [1, 2]
    value: $T = if flag { wide } else { wide }
    ret value
}
main :: fn() { seed: [2]i8 = [0, 0]; value := choose(seed, true) }
''', tmp_path, 6, '$T instantiated as [2]i8')


@pytest.mark.parametrize("calls", [
    'a := choose(wide, true); b := choose(small, false)',
    'b := choose(small, false); a := choose(wide, true)',
])
def test_array_initializer_checks_each_generic_instantiation(tmp_path, calls):
    expect_exit('''
choose :: fn(seed: $T, flag: bool) $T {
    value: $T = match flag { case true: [1, 2] else: [3, 300] }
    ret value
}
main :: fn() {
    wide: [2]i16 = [0, 0]
    small: [2]i8 = [0, 0]
''' + calls + '\n}', tmp_path, 6, '$T instantiated as [2]i8')


def test_bound_callback_rejects_overflow_in_unselected_arm(tmp_path):
    expect_exit('''
invoke :: fn(f: fn([2]$T), flag: bool) {
    f(if flag { [1, 2] } else { [3, 300] })
}
small :: fn(value: [2]i8) {}
main :: fn() { invoke(small, true) }
''', tmp_path, 6, 'Callback argument 1')


def test_nested_array_branch_fitting_reaches_inner_elements(tmp_path):
    expect_ok('''
choose :: fn(flag: bool) {
    value: [2][2]i8 = if flag { [[1, 2], [3, 4]] } else { [[5, 6], [7, 8]] }
}
main :: fn() { choose(false) }
''', tmp_path)
    expect_exit('''
choose :: fn(flag: bool) {
    value: [2][2]i8 = if flag { [[1, 2], [3, 4]] } else { [[5, 6], [7, 300]] }
}
main :: fn() { choose(true) }
''', tmp_path, 6, '300 is out of range for i8')


def test_invalid_arm_keeps_its_original_name_diagnostic(tmp_path):
    result = expect_exit('''
main :: fn() {
    value: [2]i8 = if true { [1, 2] } else { missing }
}
''', tmp_path, 6, 'missing')
    assert 'Type mismatch' not in failure_text(result)


def test_selected_arrays_and_independent_instantiations_run(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
ordinary :: fn(flag: bool) [2]i8 {
    value: [2]i8 = if flag { [1, 2] } else { [3, 4] }
    ret value
}
choose :: fn(seed: $T, flag: bool) $T {
    value: $T = match flag { case true: [5, 6] else: [7, 8] }
    ret value
}
invoke :: fn(f: fn([2]$T), flag: bool) {
    f(if flag { [9, 10] } else { [11, 12] })
}
show :: fn(value: [2]i8) { io.println("{} {}", value[0], value[1]) }
nested :: fn(flag: bool) [2][2]i8 {
    value: [2][2]i8 = match flag {
        case true: [[13, 14], [15, 16]]
        else: [[17, 18], [19, 20]]
    }
    ret value
}
main :: fn() {
    small: [2]i8 = [0, 0]
    wide: [2]i16 = [0, 0]
    a := ordinary(true)
    b := ordinary(false)
    c := choose(small, true)
    d := choose(wide, false)
    io.println("{} {} {} {} {} {} {} {}", a[0], a[1], b[0], b[1], c[0], c[1], d[0], d[1])
    invoke(show, true)
    invoke(show, false)
    e := nested(true)
    f := nested(false)
    io.println("{} {} {} {} {} {} {} {}", e[0][0], e[0][1], e[1][0], e[1][1], f[0][0], f[0][1], f[1][0], f[1][1])
}
''', tmp_path, zig) == (
        '1 2 3 4 5 6 7 8\n9 10\n11 12\n'
        '13 14 15 16 17 18 19 20\n'
    )
