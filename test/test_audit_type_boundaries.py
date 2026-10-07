"""Audit counterexamples through the public compiler and native toolchain."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def compile_source(tmp_path, source):
    path = tmp_path / 'case.a7'
    path.write_text(source)
    out = tmp_path / 'case.zig'
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--format', 'json', str(path), '-o', str(out)], capture_output=True, text=True)
    return result, out


@pytest.mark.parametrize('body,fragment', [
    ('a: i8 = 1\nb: i64 = 300\nc: i8 = a + b', 'Type mismatch'),
    ('a: u8 = 1\nb := -a', 'Cannot negate unsigned'),
    ('a: i32 = 1\nb := a << -1', 'Shift count'),
    ('a: u8 = 1\nb := a >> 8', 'Shift count'),
    ('p := Pair{a: 1}', 'Missing struct fields'),
    ('p := Pair{a: 1, b: 2, c: 3}', 'no field'),
    ('p := Pair{a: 1, a: 2, b: 3}', 'Duplicate struct field'),
    ('p := Pair{1}', 'Missing struct fields'),
    ('p := Pair{1, 2, 3}', 'Too many struct field'),
    ('p := Pair{1, true}', 'Type mismatch'),
])
def test_reject_native_type_errors(tmp_path, body, fragment):
    result, out = compile_source(tmp_path, 'Pair :: struct { a: i32, b: i32 }\nmain :: fn() {\n' + body + '\n}\n')
    assert result.returncode == 6, result.stdout + result.stderr
    assert fragment.lower() in result.stdout.lower(), result.stdout
    assert not out.exists()


@pytest.mark.parametrize('literal', ['256', '-1'])
def test_out_of_range_argument_and_return(tmp_path, literal):
    for source in [f'f :: fn(x: u8) {{}}\nmain :: fn() {{ f({literal}) }}',
                   f'f :: fn() u8 {{ ret {literal} }}\nmain :: fn() {{}}']:
        result, _ = compile_source(tmp_path, source)
        assert result.returncode == 6, result.stdout + result.stderr
        # One diagnostic names the value and the type it does not fit.
        assert f'{literal} is out of range for u8' in result.stdout


def test_stdlib_function_value_rejected(tmp_path):
    result, _ = compile_source(tmp_path, 'math :: import "std/math"\nmain :: fn() { f := math.sqrt }')
    assert result.returncode == 6, result.stdout + result.stderr
    assert 'must be called directly' in result.stdout


@pytest.mark.zig
def test_contextual_literals_and_widening_native(tmp_path):
    source = '''io :: import "std/io"
f :: fn(x: u8) u8 { ret x }
g :: fn() u8 { ret 255 }
main :: fn() {
    N :: 3
    Alias :: N
    buffer: [Alias]i32
    io.println("{}", buffer[2])
    a: i8 = 1
    b: i64 = 300
    c := a + b
    x: i64 = 300
    yes := true
    choice := if yes { 1 } else { x }
    io.println("{} {} {} {}", c, f(200), g(), choice)
    io.println("{ } {{}}")
}
'''
    result, out = compile_source(tmp_path, source)
    assert result.returncode == 0, result.stdout + result.stderr
    zig = shutil.which('zig')
    assert zig, 'Zig required for native type agreement'
    binary = tmp_path / 'case'
    build = subprocess.run([zig, 'build-exe', str(out), f'-femit-bin={binary}'], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout == '0\n301 200 255 1\n{ } {}\n'


@pytest.mark.parametrize('declaration', ['main :: fn() i32 { ret 1 }', 'main :: fn(x: i32) {}'])
def test_root_main_signature_rejected(tmp_path, declaration):
    result, _ = compile_source(tmp_path, declaration)
    assert result.returncode == 6, result.stdout + result.stderr
    assert 'entry point main' in result.stdout


def test_library_without_main_remains_valid(tmp_path):
    # LNG-16 (Option B): a main-less file is rejected without --lib, and
    # accepted as a library with it. Both directions are pinned here.
    rejected, _ = compile_source(tmp_path, 'answer :: fn() i32 { ret 42 }')
    assert rejected.returncode == 6, rejected.stdout + rejected.stderr
    assert "--lib" in rejected.stdout + rejected.stderr
    path = tmp_path / 'case.a7'
    out = tmp_path / 'case.zig'
    accepted = subprocess.run(
        [sys.executable, str(ROOT / 'main.py'), '--format', 'json', '--lib', str(path), '-o', str(out)],
        capture_output=True, text=True,
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert out.exists()


def test_file_import_cycle_has_specific_diagnostic(tmp_path):
    (tmp_path / 'a.a7').write_text('b :: import "./b"\nfa :: fn() {}')
    (tmp_path / 'b.a7').write_text('a :: import "./a"\nfb :: fn() {}')
    result, _ = compile_source(tmp_path, 'a :: import "./a"\nmain :: fn() {}')
    assert result.returncode == 6, result.stdout + result.stderr
    assert 'Circular dependency detected' in result.stdout


def test_mixed_positional_and_named_fields_remain_rejected(tmp_path):
    result, _ = compile_source(tmp_path, 'Pair :: struct { a: i32, b: bool }\nmain :: fn() { p := Pair{1, b: true} }')
    assert result.returncode == 5, result.stdout + result.stderr
