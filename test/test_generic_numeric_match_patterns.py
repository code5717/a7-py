"""Generic match constants fit each actual subject type without shared rounding."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def compile_source(tmp_path, source, expected=0, diagnostic=None):
    path = tmp_path / 'main.a7'
    path.write_text(source)
    output = tmp_path / 'main.zig'
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), str(path),
                             '--format', 'json', '-o', str(output)],
                            cwd=tmp_path, capture_output=True, text=True)
    (tmp_path / 'compile.stdout').write_text(result.stdout)
    (tmp_path / 'compile.stderr').write_text(result.stderr)
    (tmp_path / 'compile.json').write_text(json.dumps({
        'argv': result.args, 'exit': result.returncode,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
        'stderr_sha256': hashlib.sha256(result.stderr.encode()).hexdigest(),
    }, indent=2))
    assert result.returncode == expected, result.stdout + result.stderr
    assert not result.stderr
    if diagnostic:
        assert diagnostic in result.stdout
    if expected:
        assert not output.exists()
        return result.stdout
    return output.read_text()


def picker(patterns, constraint='', statement=False):
    cases = '; '.join(f'case {p}: ' + (f'{{ ret {i} }}' if statement else str(i))
                      for i, p in enumerate(patterns, 1))
    body = f'match x {{ {cases}; else: {{ ret 0 }} }}' if statement else f'ret match x {{ {cases}; else: 0 }}'
    return f'pick{constraint} :: fn(x: $T) i32 {{ {body} }}\n'


@pytest.mark.parametrize('type_name,patterns,expected,diagnostic', [
    ('f32', ['1.0', '1.00000011920928955078125'], 0, None),
    ('f32', ['1.0', '1.00000001'], 6, 'redundant match pattern'),
    ('f64', ['1.0', '1.00000001'], 0, None),
    ('i64', ['9007199254740992..9007199254740992', '9007199254740993'], 0, None),
    ('i64', ['-9007199254740993', '-9007199254740993..-9007199254740993'], 6, 'overlaps'),
    ('u64', ['18446744073709551614..18446744073709551614', '18446744073709551615'], 0, None),
    ('i8', ['128'], 6, 'Match pattern type mismatch'),
    ('i32', ['1.25'], 6, 'Match pattern type mismatch'),
    ('bool', ['1'], 6, 'Match pattern type mismatch'),
    ('string', ['1'], 6, 'Match pattern type mismatch'),
    ('f32', ['2.0..1.0'], 6, 'reversed'),
])
def test_concrete_pattern_obligations(tmp_path, type_name, patterns, expected, diagnostic):
    value = 'false' if type_name == 'bool' else '"x"' if type_name == 'string' else '0'
    compile_source(tmp_path, picker(patterns) + f'main :: fn() {{ x: {type_name} = {value}; result := pick(x) }}', expected, diagnostic)


@pytest.mark.parametrize('reverse', [False, True])
def test_each_call_order_rejects_f32_overlap(tmp_path, reverse):
    calls = ['a: f64 = 0; p := pick(a)', 'b: f32 = 0; q := pick(b)']
    if reverse:
        calls.reverse()
    compile_source(tmp_path, picker(['1.0', '1.00000001']) + 'main :: fn() {' + '; '.join(calls) + '}', 6, 'redundant match pattern')


def test_direct_rounding_and_single_generic_body(tmp_path):
    # 1 + 2^-24 + 2^-60 rounds upward to f32; an f64 intermediate loses 2^-60.
    exact = '1.000000059604644776257986737988403547205962240695953369140625'
    zig = compile_source(tmp_path, picker(['1.0', exact]) + 'main :: fn() { a: f32 = 0; b: f64 = 0; p := pick(a); q := pick(b) }')
    assert zig.count('fn pick(') == 1
    assert '@as(u32, 1065353217)' in zig
    assert '@as(u64, 4607182419068452864)' in zig
    assert 'pick(f32, a)' in zig and 'pick(f64, b)' in zig


def test_statement_match_and_immutable_wrapper_chain(tmp_path):
    zig = compile_source(tmp_path, picker(['1.0', '1.00000011920928955078125'], statement=True) + '''
wrap :: fn(x: $A) i32 { ret pick(x) }
main :: fn() { x: f32 = 0; invoke := wrap; again := invoke; result := again(x) }
''')
    assert '@as(u32, 1065353217)' in zig


def test_concrete_wrapper_discharges_obligation(tmp_path):
    compile_source(tmp_path, picker(['127']) + '''
fixed :: fn(x: i8) i32 { ret pick(x) }
main :: fn() { f := fixed; x: i8 = 0; result := f(x) }
''')


@pytest.mark.parametrize('use', [
    'f := pick; f = pick; x: i8 = 0; result := f(x)',
    'f := wrap; f = wrap; x: i8 = 0; result := f(x)',
    'f := pick; f = pick',
])
def test_unsupported_callable_origins_remain_rejected(tmp_path, use):
    compile_source(tmp_path, picker(['128']) + 'wrap :: fn(x: $A) i32 { ret pick(x) }\nmain :: fn() {' + use + '}', 6, 'known generic callable origin')


def test_unused_generic_and_unused_stable_alias(tmp_path):
    compile_source(tmp_path, picker(['128']) + 'main :: fn() { f := pick }')


def test_lexical_named_constant_does_not_use_callers_shadow(tmp_path):
    zig = compile_source(tmp_path, 'B :: 1.00000011920928955078125\n' + picker(['1.0', 'B']) + 'main :: fn() { B :: 1.0; x: f32 = 0; result := pick(x) }')
    assert '@as(u32, 1065353217)' in zig


def test_runtime_range_binding_is_not_resolved_in_entry_scope(tmp_path):
    compile_source(tmp_path, '''
y :: 0
pick($T: Float) :: fn(x: $T, y: $T) i32 { ret match x { case 1.0..y: 1; else: 0 } }
main :: fn() { x: f32 = 0; y: f32 = 2; result := pick(x, y) }
''')


def test_imported_generic_pattern_obligation(tmp_path):
    (tmp_path / 'helper.a7').write_text('pub ' + picker(['1.0', '1.00000011920928955078125']))
    zig = compile_source(tmp_path, 'h :: import "helper"\nmain :: fn() { x: f32 = 0; result := h.pick(x) }')
    assert '@as(u32, 1065353217)' in zig


@pytest.mark.parametrize('main', [
    'f := pick; nested :: fn() { x: i8 = 0; y := f(x) }; nested()',
    'items := [pick, pick]',
    'flag := true; f := if flag { pick } else { pick }',
])
def test_other_untracked_origins_retain_rejection(tmp_path, main):
    compile_source(tmp_path, picker(['128']) + 'apply :: fn(f: fn($A) i32, x: $A) i32 { ret f(x) }\nmain :: fn() {' + main + '}', 6, 'known generic callable origin')


def test_global_callable_escape_rejected(tmp_path):
    compile_source(tmp_path, picker(['128']) + 'f :: pick\nmain :: fn() {}', 6, 'known generic callable origin')


@pytest.mark.parametrize('reverse', [False, True])
def test_named_exact_constant_overlap_in_both_orders(tmp_path, reverse):
    patterns = ['A', '1.0']
    if reverse:
        patterns.reverse()
    compile_source(tmp_path, 'A :: 1.00000001\n' + picker(patterns) + 'main :: fn() { x: f32 = 0; y := pick(x) }', 6, 'redundant match pattern')


@pytest.mark.parametrize('generic', [False, True])
def test_variable_pattern_keeps_runtime_comparison(tmp_path, generic):
    subject = '$T' if generic else 'f32'
    compile_source(tmp_path, f'pick :: fn(x: {subject}) i32 {{ A: {subject} = 1; ret match x {{ case A: 1; case 1.0: 2; else: 0 }} }}\nmain :: fn() {{ x: f32 = 0; y := pick(x) }}')


def test_concrete_subject_checked_despite_unrelated_generic(tmp_path):
    compile_source(tmp_path, 'pick :: fn(x: $T, unused: $U) i32 { ret match x { case 128: 1; else: 0 } }\nouter :: fn(y: $V) i32 { x: i8 = 0; ret pick(x, y) }\nmain :: fn() {}', 6, 'Match pattern type mismatch')


def test_large_unused_constant_has_no_unbounded_integer_emission(tmp_path):
    zig = compile_source(tmp_path, 'HUGE :: 1 << 16000\n' + picker(['HUGE']) + 'main :: fn() {}')
    assert 'match pattern does not fit an integer target' in zig
    assert len(zig) < 5000


def test_wildcard_redundancy_is_not_deferred(tmp_path):
    compile_source(tmp_path, picker(['_', '1.0']) + 'main :: fn() {}', 6, 'previous wildcard')


def test_callback_inference_diagnostic_priority(tmp_path):
    compile_source(tmp_path, picker(['128']) + 'apply :: fn(f: fn($A) i32, x: $A) i32 { ret f(x) }\nmain :: fn() { x: i8 = 0; y := apply(pick, x) }', 6, 'generic_binding_conflict')


def test_exact_duplicate_in_unused_template_is_rejected(tmp_path):
    compile_source(tmp_path, picker(['1', '1.0']) + 'main :: fn() {}', 6, 'redundant match pattern')


def test_imported_generic_value_escape_rejected(tmp_path):
    (tmp_path / 'helper.a7').write_text('pub ' + picker(['128']))
    compile_source(tmp_path, 'h :: import "helper"\nmain :: fn() { f := h.pick }', 6, 'known generic callable origin')


@pytest.mark.parametrize('type_name,value,expected', [
    ('i32', '0', 0), ('f32', '0.0', 0), ('char', "'a'", 0),
    ('bool', 'false', 6), ('string', '"x"', 6), ('Box', 'Box{value: 0}', 6),
])
def test_runtime_range_subject_checked_at_instantiation(tmp_path, type_name, value, expected):
    compile_source(tmp_path, 'Box :: struct { value: i32 }\npick :: fn(x: $T, lo: $T, hi: $T) i32 { ret match x { case lo..hi: 1; else: 0 } }\n' + f'main :: fn() {{ x: {type_name} = {value}; y := pick(x, x, x) }}', expected, 'Range patterns require a numeric or char' if expected else None)


def test_runtime_range_callable_escape_rejected(tmp_path):
    compile_source(tmp_path, 'pick :: fn(x: $T, lo: $T, hi: $T) i32 { ret match x { case lo..hi: 1; else: 0 } }\nmain :: fn() { f := pick; f = pick }', 6, 'Range pattern requires a known generic callable origin')


@pytest.mark.parametrize('invalid', [False, True])
def test_repeated_wrapper_dag_preserves_pattern_checks(tmp_path, invalid):
    source = picker(['128' if invalid else '127'])
    previous = 'pick'
    for level in range(12):
        name = f'wrap{level}'
        source += f'{name} :: fn(x: $T) i32 {{ a := {previous}(x); b := {previous}(x); ret a + b }}\n'
        previous = name
    source += f'main :: fn() {{ x: i8 = 0; y := {previous}(x) }}'
    compile_source(tmp_path, source, 6 if invalid else 0, 'Match pattern type mismatch' if invalid else None)
