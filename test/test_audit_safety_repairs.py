"""Real CLI regressions for the six accepted-crashing audit programs.

Unsafe programs must fail before native output. The independent safe control
runs in Debug and ReleaseFast and pins output, not internal proof counters.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'test/fixtures/safety_regressions'


def compile_source(tmp_path, source):
    src, out = tmp_path / 'case.a7', tmp_path / 'case.zig'
    src.write_text(source)
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), str(src), '--format', 'json', '-o', str(out)], cwd=ROOT, capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout), out


@pytest.mark.parametrize('name,message', [
    ('d_loop_no_fixedpoint', 'Index not proven in bounds'),
    ('d_call_invalidates', 'Divisor not proven non-zero'),
    ('d_join_gap', 'Divisor not proven non-zero'),
    ('d_del_braced_defer', 'Use after move or delete'),
    ('d_loop_defer_del', 'Use after move or delete'),
    ('d_ref_nil_call', 'Reference not proven non-nil'),
    ('deferred_delete_guard', 'Use after move or delete'),
    ('loop_delete_guard', 'Use after move or delete'),
    ('call_delete_guard', 'Use after move or delete'),
    ('loop_call_delete_guard', 'Use after move or delete'),
])
def test_accepted_crashing_program_is_rejected(tmp_path, name, message):
    code, payload, output = compile_source(tmp_path, (CASES / (name + '.a7')).read_text())
    assert code == 6, payload
    assert payload['error']['category'] == 'semantic'
    assert message in str(payload['error']['details'])
    assert not output.exists()


@pytest.mark.parametrize('body', [
    'x := 4\n{ x = 0 }\ny := 100 / x',
    'x := 4\n{ defer { x = 0 } }\ny := 100 / x',
    'x := 4\nif true { x = 0 }\ny := 100 / x',
])
def test_scope_exit_never_restores_stale_divisor(tmp_path, body):
    code, payload, output = compile_source(tmp_path, 'main :: fn() {\n' + body + '\n}')
    assert code == 6, payload
    assert 'Divisor not proven non-zero' in str(payload['error'])
    assert not output.exists()


@pytest.mark.parametrize('profile', ['Debug', 'ReleaseFast'])
def test_guarded_mutation_and_bounded_loop_run(tmp_path, profile):
    source = '''io :: import "std/io"
zero :: fn(x: ref i32) { x = 0 }
slice_get :: fn(s: []i32, i: usize) i32 {
    if i < s.len { ret s[i] }
    ret 0
}
get :: fn(a: [3]i32, i: usize) i32 {
    if i < 3 { ret a[i] }
    ret 0
}
main :: fn() {
    x := 4
    zero(x)
    if x == 0 { x = 5 }
    if x != 0 { io.println("{}", 100 / x) }
    a: [3]i32 = [2, 3, 4]
    i: usize = 0
    while i < 3 { io.println("{}", get(a, i)); i += 1 }
    io.println("{}", slice_get(a[0..3], 2))
}
'''
    code, payload, output = compile_source(tmp_path, source)
    assert code == 0, payload
    binary = tmp_path / 'case'
    built = subprocess.run(['zig', 'build-exe', str(output), '-O', profile, '-femit-bin=' + str(binary)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(binary)], capture_output=True, text=True)
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, '20\n2\n3\n4\n4\n', '')


def test_slice_guard_does_not_survive_reassignment(tmp_path):
    code, payload, output = compile_source(tmp_path, '''get :: fn(s: []i32, i: usize) i32 {
    copy := s
    if i < copy.len {
        a: [1]i32 = [7]
        copy = a[0..1]
        ret copy[i]
    }
    ret 0
}
''')
    assert code == 6, payload
    assert 'Index not proven in bounds' in str(payload['error'])
    assert not output.exists()
