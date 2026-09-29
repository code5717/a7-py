"""P-TYP observable requirements through the CLI and native Zig in both profiles.

No mocks or coverage targets. IEEE expectations are fixed mathematical cases from
untyped-ieee-acceptance-2026-09-20.md. Only that test replaces the final print
argument to observe stored bits; it does not qualify A7 float formatting.
These tests do not qualify resource enforcement, security, or a complete release.
"""
import json
import re
import subprocess
import sys

import pytest

from test.test_constant_folding_exact import (
    ROOT, emit, expect_everywhere, run_all_profiles, zig,
)

HEADER = 'io :: import "std/io"\n'


def reject(tmp_path, source, words):
    """A semantic failure has one located cause and leaves no new Zig artifact."""
    path = tmp_path / 'main.a7'
    output = tmp_path / 'main.zig'
    path.write_text(source)
    result = subprocess.run(
        [sys.executable, str(ROOT / 'main.py'), str(path), '--format', 'json',
         '--output', str(output)], cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 6, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    # The CLI deliberately repeats details under stages. Count the public error
    # list once, not every serialized occurrence of the same diagnostic.
    errors = payload['error']['details']
    assert len(errors) == 1, errors
    error = errors[0]
    assert error['span']['start_line'] > 0, error
    assert any(word in error['message'].lower() for word in words), error
    assert not output.exists(), 'Rejected source emitted a new usable artifact'


@pytest.mark.parametrize('forward', [False, True], ids=['defined-first', 'forward'])
def test_alias_order_and_independent_destinations(tmp_path, zig, forward):
    declarations = 'VALUE :: ALIAS\nALIAS :: 200.0\n'
    function = '''show :: fn() {
        small: u8 = VALUE
        wide: i64 = VALUE
        io.println("{} {}", small, wide)
    }
'''
    source = HEADER + (function + declarations if forward else declarations + function)
    source += 'main :: fn() { show() }\n'
    assert run_all_profiles(zig, tmp_path, emit(tmp_path, source)) == expect_everywhere('200 200\n')


@pytest.mark.parametrize('body, expected', [
    ('HUGE :: 1e400\nCANCEL :: HUGE - HUGE\n'
     'main :: fn() { local :: 1e400; x: i32 = CANCEL + local - local; '
     'io.println("{} {}", x, HUGE == 1e400) }', '0 true\n'),
    ('main :: fn() { x: i32 = -5 / 2; y: f64 = 5 / 2; z: f64 = -5.5 % 2.0; '
     'io.println("{} {} {} {}", x, y, z, 0.1 + 0.2 == 0.3) }', '-2 2 -1.5 true\n'),
    ('main :: fn() { x: i64 = 9007199254740993.0; low: i8 = -128.0; '
     'high: u8 = 255.0; io.println("{} {} {}", x, low, high) }', '9007199254740993 -128 255\n'),
    ('main :: fn() { x: u8 = 255; x += 1; '
     'io.println("{}", x) }', '0\n'),
    ('LEFT :: 1 << 40\nRIGHT :: -3 >> 1\n'
     'main :: fn() { x: i64 = LEFT; y: i32 = RIGHT; z: i32 = (6 & 3) | 8; '
     'io.println("{} {} {}", x, y, z) }', '1099511627776 -2 10\n'),
], ids=['unmaterialized-binding-cancellation', 'exact-arithmetic-category',
        'integer-fit-boundaries', 'typed-wrapping', 'untyped-bitwise-shifts'])
def test_exact_values_and_concrete_operations(tmp_path, zig, body, expected):
    assert run_all_profiles(zig, tmp_path, emit(tmp_path, HEADER + body)) == expect_everywhere(expected)


@pytest.mark.parametrize('body, expected', [
    ('RATE :: 2.0\nBox :: struct { n: i32 }\n'
     'get :: fn() i32 { ret RATE }\nshow :: fn(x: i32) { io.println("{}", x) }\n'
     'main :: fn() { b := Box{n: RATE}; a: [1]i32 = [RATE]; '
     'show(RATE); io.println("{} {} {}", get(), b.n, a[0]) }', '2\n2 2 2\n'),
    ('SIZE :: 2.0\nINDEX :: 1.0\nmain :: fn() { a: [SIZE]i32 = [3, 4]; '
     'io.println("{}", a[INDEX]) }', '4\n'),
    ('RATE :: 2.0\nmain :: fn() { x: i32 = 2; match x { '
     'case RATE: { io.println("yes") } else: { io.println("no") } } }', 'yes\n'),
    ('choose($T) :: fn(a: $T, b: $T) $T { ret b }\nRATE :: 2.0\n'
     'main :: fn() { x: i32 = 1; y := choose(x, RATE); io.println("{}", y) }', '2\n'),
], ids=['declared-destinations', 'array-length-index', 'typed-pattern', 'known-generic-type'])
def test_destination_contexts(tmp_path, zig, body, expected):
    assert run_all_profiles(zig, tmp_path, emit(tmp_path, HEADER + body)) == expect_everywhere(expected)


@pytest.mark.parametrize('declaration, words', [
    ('x: i32 = 2.5', ('integral', 'fraction', 'fit')),
    ('x: u8 = 256', ('range', 'fit')),
    ('x: usize = -1', ('range', 'fit', 'negative')),
    ('x: i8 = -129', ('range', 'fit')),
    ('x: f32 = 340282356779733661637539395458142568448.0', ('overflow', 'fit')),
    ('x: f64 = 1.7976931348623159e308', ('overflow', 'fit')),
    ('x := 2.0 & 3', ('integer', 'bitwise')),
    ('x := 1 << -1', ('negative', 'shift')),
    ('runtime := 2.0; x: i32 = runtime', ('i32', 'f64')),
    ('typed: i8 = 1; x := typed + 200', ('range', 'fit')),
    ('x := 9007199254740993', ('i32', 'default')),
], ids=['fractional', 'unsigned-overflow', 'unsigned-negative', 'signed-underflow',
        'f32-overflow-tie', 'f64-overflow', 'float-bitwise', 'negative-shift',
        'runtime-stays-typed', 'typed-operand-fit', 'default-overflow'])
def test_rejection_has_one_located_cause(tmp_path, declaration, words):
    reject(tmp_path, 'main :: fn() { ' + declaration + ' }', words)


def test_generic_inference_materializes_float_default(tmp_path):
    reject(tmp_path, 'identity($T) :: fn(x: $T) $T { ret x }\n'
           'main :: fn() { value := identity(2.0); n: i32 = value }', ('i32', 'f64'))


def test_patterns_are_compared_after_fitting(tmp_path):
    reject(tmp_path, 'RATE :: 2.0\nmain :: fn() { x: i32 = 2; match x { '
           'case RATE: {} case 2: {} else: {} } }', ('duplicate', 'overlap'))


# Fixed IEEE bit patterns from independently stated midpoint and range rules.
IEEE_CASES = [
    ('f32', '1.000000059604644775390624', 0x3f800000),
    ('f32', '1.000000059604644775390625', 0x3f800000),
    ('f32', '1.0000000596046447753906250000000000000000000000000000000000000000000000001', 0x3f800001),
    ('f64', '1.00000000000000011102230246251565404236316680908203124', 0x3ff0000000000000),
    ('f64', '1.00000000000000011102230246251565404236316680908203125', 0x3ff0000000000000),
    ('f64', '1.00000000000000011102230246251565404236316680908203126', 0x3ff0000000000001),
    ('f32', '7.006492321624085e-46', 0),
    ('f32', '7.006492321624086e-46', 1),
    ('f32', '1.401298464324817e-45', 1),
    ('f64', '2.4703282292062327e-324', 0),
    ('f64', '2.4703282292062328e-324', 1),
    ('f64', '4.9406564584124654e-324', 1),
    ('f32', '340282346638528859811704183484516925440.0', 0x7f7fffff),
    ('f32', '340282356779733661637539395458142568447.0', 0x7f7fffff),
    ('f64', '1.7976931348623157e308', 0x7fefffffffffffff),
    ('f32', '-0.0', 0x80000000),
    ('f64', '-1e-400', 0x8000000000000000),
]


def test_direct_ieee_materialization_bits(tmp_path, zig):
    lines = [HEADER, 'main :: fn() {']
    for index, (kind, literal, _) in enumerate(IEEE_CASES):
        lines += [f'observed_{index}: {kind} = {literal}',
                  f'io.println("{{}}", observed_{index})']
    lines += ['}']
    output = emit(tmp_path, '\n'.join(lines))
    generated = output.read_text()
    for index, (kind, _, _) in enumerate(IEEE_CASES):
        integer = 'u32' if kind == 'f32' else 'u64'
        pattern = r'(__a7_stdout_print\("\{\}\\n", \.\{)' + f'observed_{index}' + r'(\}\);)'
        replacement = r'\g<1>@as(' + integer + f', @bitCast(observed_{index}))' + r'\g<2>'
        generated, count = re.subn(pattern, replacement, generated)
        assert count == 1, 'IEEE observer must replace exactly one final print argument'
    observer = tmp_path / 'observer.zig'
    observer.write_text(generated)
    expected = ''.join(str(bits) + '\n' for _, _, bits in IEEE_CASES)
    assert run_all_profiles(zig, tmp_path, observer) == expect_everywhere(expected)
