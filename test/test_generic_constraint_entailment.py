"""Forwarded constrained types must satisfy every admitted source member."""

import pytest

from test_generic_numeric_match_patterns import compile_source


@pytest.mark.parametrize('required,provided,expected', [
    ('Float', 'Float', 0),
    ('Numeric', 'Float', 0),
    ('Float', '@type_set(f32)', 0),
    ('Float', 'Numeric', 6),
    ('Float', '@type_set(f32, i32)', 6),
    ('Float', None, 6),
])
@pytest.mark.parametrize('nominal', [False, True])
def test_forwarded_constraints(tmp_path, required, provided, expected, nominal):
    wrapper = f'wrap($U: {provided})' if provided else 'wrap'
    if nominal:
        source = f'Box($T: {required}) :: struct {{ value: $T }}\n{wrapper} :: fn(x: $U) Box($U) {{ ret Box($U){{value: x}} }}\n'
    else:
        source = f'identity($T: {required}) :: fn(x: $T) $T {{ ret x }}\n{wrapper} :: fn(x: $U) $U {{ ret identity(x) }}\n'
    source += 'main :: fn() { x: f32 = 1; y := wrap(x) }'
    zig = compile_source(tmp_path, source, expected, 'constraint_violation' if expected else None)
    if not expected:
        assert 'wrap(f32, x)' in zig


@pytest.mark.parametrize('nominal', [False, True])
def test_where_and_equivalent_local_set_alias(tmp_path, nominal):
    source = 'Floats :: @type_set(f32, f64)\n'
    if nominal:
        source += 'Box($T: Floats) :: struct { value: $T }\nwrap :: fn(x: $U) Box($U) where U: Float { ret Box($U){value: x} }\n'
    else:
        source += 'identity :: fn(x: $T) $T where T: Floats { ret x }\nwrap :: fn(x: $U) $U where U: Float { ret identity(x) }\n'
    compile_source(tmp_path, source + 'main :: fn() { x: f32 = 1; y := wrap(x) }')


def test_same_generic_name_and_original_match_wrapper(tmp_path):
    zig = compile_source(tmp_path, '''
io :: import "std/io"
pick($T: Float) :: fn(x: $T) i32 { ret match x { case 1.0: 1; case 1.00000011920928955078125: 2; else: 3 } }
wrap($T: Float) :: fn(x: $T) i32 { ret pick(x) }
main :: fn() { x: f32 = 1.00000011920928955078125; alias := wrap; copy := alias; io.println("{}", copy(x)) }
''')
    assert '@as(u32, 1065353217)' in zig
    assert 'pick(T, x)' in zig


def test_accepted_constraint_still_checks_bad_pattern_fit(tmp_path):
    compile_source(tmp_path, '''
pick($T: Float) :: fn(x: $T) i32 { ret match x { case 1.0: 1; case 1.00000001: 2; else: 0 } }
wrap($U: Float) :: fn(x: $U) i32 { ret pick(x) }
main :: fn() { x: f32 = 0; y := wrap(x) }
''', 6, 'redundant match pattern')


@pytest.mark.parametrize('nominal', [False, True])
def test_concrete_nonmember_stays_rejected(tmp_path, nominal):
    source = ('Box($T: Float) :: struct { value: $T }\nmain :: fn() { b := Box(i32){value: 0} }'
              if nominal else 'identity($T: Float) :: fn(x: $T) $T { ret x }\nmain :: fn() { x: i32 = 0; y := identity(x) }')
    compile_source(tmp_path, source, 6, 'constraint_violation')


def test_empty_admitted_set_does_not_gain_forwarding(tmp_path):
    compile_source(tmp_path, '''
Empty :: @type_set()
identity($T: Float) :: fn(x: $T) $T { ret x }
wrap($U: Empty) :: fn(x: $U) $U { ret identity(x) }
main :: fn() {}
''', 6, 'constraint_violation')
