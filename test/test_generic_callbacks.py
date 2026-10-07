"""Callback signatures use the type bindings of their enclosing function."""

import pytest

from conftest import expect_exit, run_both_profiles


def test_callbacks_forward_alias_and_infer_return_types(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
apply :: fn(f: fn($T) $U, x: $T) $U { alias := f; ret alias(x) }
forward :: fn(f: fn($A) $B, x: $A) $B { ret apply(f, x) }
get :: fn(f: fn() $R) $R { ret f() }
double :: fn(x: i32) i32 { ret x * 2 }
positive :: fn(x: i32) bool { ret x > 0 }
word :: fn() string { ret "ok" }
main :: fn() {
    io.println("{} {} {}", forward(double, 21), apply(positive, 1), get(word))
}
''', tmp_path, zig) == "42 true ok\n"


@pytest.mark.parametrize("bad_first", [False, True])
def test_callback_literal_checked_for_each_instantiation(tmp_path, bad_first):
    calls = ['a := invoke(number)', 'b := invoke(text)']
    if bad_first:
        calls.reverse()
    expect_exit('''
invoke :: fn(f: fn($T) $T) $T { ret f(0) }
number :: fn(x: i32) i32 { ret x }
text :: fn(x: string) string { ret x }
main :: fn() { ''' + '; '.join(calls) + ' }', tmp_path, 6, "Callback argument 1")


def test_callback_literal_numeric_instantiations_run(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
invoke :: fn(f: fn($T) $T) $T { ret f(0) }
small :: fn(x: i8) i8 { ret x }
real :: fn(x: f64) f64 { ret x }
main :: fn() { io.println("{} {}", invoke(small), invoke(real)) }
''', tmp_path, zig) == "0 0\n"


@pytest.mark.parametrize("body,diagnostic", [
    ('ret f()', 'Expected 1 arguments, got 0'),
    ('ret f(true)', 'Callback argument 1'),
    ('ret f(300)', 'Callback argument 1'),
])
def test_callback_bad_arguments_rejected(tmp_path, body, diagnostic):
    expect_exit('invoke :: fn(f: fn($T) $T) $T { ' + body + ''' }
small :: fn(x: i8) i8 { ret x }
main :: fn() { x := invoke(small) }
''', tmp_path, 6, diagnostic)


def test_generic_declaration_alias_keeps_unbound_return_error(tmp_path):
    expect_exit('''
make :: fn(x: $T) $U { ret x }
outer :: fn(x: $T) $T { alias := make; ret alias(x) }
main :: fn() { x := outer(1) }
''', tmp_path, 6, "Could not infer generic parameter '$U'")


def test_callback_aggregate_and_implicit_reference_arguments_run(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
Box :: struct { value: i32 }
apply :: fn(f: fn($T) $U, x: $T) $U { ret f(x) }
mutate :: fn(f: fn(ref $T), x: $T) $T { local := x; f(local); ret local }
field :: fn(b: Box) i32 { ret b.value }
increment :: fn(x: ref i32) { x += 1 }
main :: fn() {
    io.println("{} {}", apply(field, Box{value: 7}), mutate(increment, 8))
}
''', tmp_path, zig) == "7 9\n"


def test_forwarded_callback_argument_requirement_reaches_outer_call(tmp_path):
    expect_exit('''
forward :: fn(f: fn($A) $A) $A { ret invoke(f) }
invoke :: fn(f: fn($T) $T) $T { ret f(0) }
text :: fn(x: string) string { ret x }
main :: fn() { x := forward(text) }
''', tmp_path, 6, "Callback argument 1")


def test_callback_reference_argument_cannot_widen(tmp_path):
    expect_exit('''
invoke :: fn(f: fn(ref $T)) { value: i32 = 0; f(value) }
small :: fn(x: ref i8) { x += 1 }
main :: fn() { invoke(small) }
''', tmp_path, 6, "Callback argument 1")


def test_callback_argument_uses_declared_type_instead_of_rebinding(tmp_path):
    expect_exit('''
invoke :: fn(f: fn($T) $T, x: $U) $T { ret f(x) }
small :: fn(x: i8) i8 { ret x }
main :: fn() { value: i32 = 0; result := invoke(small, value) }
''', tmp_path, 6, "Callback argument 1")


def test_callback_array_literals_fit_each_concrete_element_type(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
invoke :: fn(f: fn([2]$T) $T) $T { ret f([1, 2]) }
small :: fn(x: [2]i8) i8 { ret x[0] + x[1] }
wide :: fn(x: [2]i64) i64 { ret x[0] + x[1] }
main :: fn() { io.println("{} {}", invoke(small), invoke(wide)) }
''', tmp_path, zig) == "3 3\n"


@pytest.mark.parametrize("argument", ['[1, 300]', 'values'])
def test_callback_array_fit_rejects_overflow_and_typed_narrowing(tmp_path, argument):
    expect_exit('''
invoke :: fn(f: fn([2]$T)) { values: [2]i32 = [1, 2]; f(''' + argument + ''') }
small :: fn(x: [2]i8) {}
main :: fn() { invoke(small) }
''', tmp_path, 6, "Callback argument 1")


def test_generic_array_initializer_fits_without_sharing_instantiation_types(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
make :: fn(example: $T) $T { result: $T = [1, 2]; ret result }
main :: fn() {
    small: [2]i8 = [0, 0]
    wide: [2]i64 = [0, 0]
    a := make(small)
    b := make(wide)
    io.println("{} {}", a[1], b[1])
}
''', tmp_path, zig) == "2 2\n"


@pytest.mark.parametrize("value", ['[1, 300]', 'values'])
def test_generic_array_initializer_rejects_overflow_and_typed_narrowing(tmp_path, value):
    expect_exit('''
make :: fn(example: $T) $T {
    values: [2]i32 = [1, 2]
    result: $T = ''' + value + '''
    ret result
}
main :: fn() { small: [2]i8 = [0, 0]; result := make(small) }
''', tmp_path, 6, 'Type mismatch')


@pytest.mark.parametrize("expression", [
    "if flag { 1 } else { 2 }",
    "match flag { case true: 1 else: 2 }",
])
def test_callback_constant_branches_fit_the_bound_type(tmp_path, zig, expression):
    assert run_both_profiles('''
io :: import "std/io"
invoke :: fn(f: fn($T) $T, flag: bool) $T { ret f(EXPR) }
small :: fn(x: i8) i8 { ret x }
wide :: fn(x: i64) i64 { ret x }
main :: fn() { io.println("{} {}", invoke(small, true), invoke(wide, false)) }
'''.replace('EXPR', expression), tmp_path, zig) == "1 2\n"


def test_callback_constant_branch_overflow_is_rejected(tmp_path):
    expect_exit('''
invoke :: fn(f: fn($T) $T, flag: bool) $T { ret f(if flag { 1 } else { 300 }) }
small :: fn(x: i8) i8 { ret x }
main :: fn() { value := invoke(small, true) }
''', tmp_path, 6, "Callback argument 1")


@pytest.mark.parametrize('setup', [
    'local: fn($T); local = f',
    'local := if flag { f } else { g }',
    'local := match flag { case true: f else: g }',
    'local := f; local = g',
    'local: fn($T); if flag { local = f } else { local = g }',
])
@pytest.mark.parametrize('bad_first', [False, True])
def test_assigned_and_selected_callbacks_keep_instantiated_argument_type(tmp_path, setup, bad_first):
    calls = ['invoke(wide, wide, true)', 'invoke(small, small, false)']
    if bad_first:
        calls.reverse()
    expect_exit('invoke :: fn(f: fn($T), g: fn($T), flag: bool) { '
                + setup + '; local(300) }\n' + '''
wide :: fn(x: i32) {}
small :: fn(x: i8) {}
main :: fn() { ''' + '; '.join(calls) + ' }', tmp_path, 6, 'Callback argument 1')


def test_zero_argument_callback_assignment_compiles(tmp_path):
    from conftest import expect_ok

    expect_ok('''
invoke :: fn(f: fn() $T) $T { local: fn() $T; local = f; ret local() }
number :: fn() i32 { ret 7 }
main :: fn() { x := invoke(number) }
''', tmp_path)


def test_assignment_selection_reassignment_and_zero_argument_callbacks_run(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
invoke :: fn(f: fn($T) $T, g: fn($T) $T, x: $T, flag: bool) $T {
    local: fn($T) $T
    local = if flag { f } else { g }
    first := local(x)
    local = g
    ret local(first)
}
choose :: fn(f: fn() $T, g: fn() $T, flag: bool) $T {
    local: fn() $T
    local = match flag { case true: f else: g }
    ret local()
}
inc :: fn(x: i8) i8 { ret x + 1 }
double :: fn(x: i8) i8 { ret x * 2 }
left :: fn(x: string) string { ret "L" }
right :: fn(x: string) string { ret "R" }
seven :: fn() i32 { ret 7 }
nine :: fn() i32 { ret 9 }
main :: fn() {
    x: i8 = 3
    io.println("{} {} {} {} {}", invoke(inc, double, x, true), invoke(inc, double, x, false),
        invoke(left, right, "start", true),
        choose(seven, nine, true), choose(seven, nine, false))
}
''', tmp_path, zig) == '8 12 R 7 9\n'


def test_callback_assignment_does_not_mark_shadowed_generic_declaration_alias(tmp_path):
    expect_exit('''
make :: fn(x: $T) $U { ret x }
invoke :: fn(f: fn($T) $T, x: $T) $T {
    local: fn($T) $T
    local = f
    { local := make; ignored := local(x) }
    ret local(x)
}
number :: fn(x: i32) i32 { ret x }
main :: fn() { value := invoke(number, 1) }
''', tmp_path, 6, "Could not infer generic parameter '$U'")


def test_selection_of_generic_declarations_keeps_unbound_diagnostic(tmp_path):
    expect_exit('''
make :: fn(x: $T) $U { ret x }
other :: fn(x: $T) $U { ret x }
choose :: fn(flag: bool) { local := if flag { make } else { other }; x := local(1) }
main :: fn() { choose(true) }
''', tmp_path, 6, "Could not infer generic parameter '$U'")


@pytest.mark.parametrize('expression', [
    'if flag { f } else { generic }',
    'if flag { generic } else { f }',
    'match flag { case true: f else: generic }',
    'match flag { case true: generic else: f }',
])
def test_selection_cannot_reinfer_a_runtime_callback_branch(tmp_path, expression):
    expect_exit('''
generic :: fn(x: $T) {}
small :: fn(x: i8) {}
invoke :: fn(f: fn($T), flag: bool) { local := ''' + expression + '; local(300) }\n'
                + 'main :: fn() { invoke(small, true) }', tmp_path, 6, 'Callback argument 1')
