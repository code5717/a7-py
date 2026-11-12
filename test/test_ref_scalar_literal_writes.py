"""Contextual constants write referenced numeric storage without rebinding it."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('type_name,setup,assignment,emitted', [
    ('usize', '', 'n=3', 'n.?.* = 3;'),
    ('u8', '', 'n=255', 'n.?.* = 255;'),
    ('i8', '', 'n=-128', 'n.?.* = -128;'),
    ('usize', 'THREE::3\n', 'n=THREE', 'n.?.* = 3;'),
    ('usize', '', 'n=3.0', 'n.?.* = 3;'),
    ('f32', '', 'n=3', 'n.?.* = 3.0;'),
    ('usize', '', 'three:usize=3;n=three', 'n.?.* = three;'),
    ('usize', '', 'three:usize=3;n+=three', 'n.?.* +%= three;'),
    ('usize', '', 'n+=3', 'n.?.* +%= 3;'),
    ('usize', '', 'n+=3.0', 'n.?.* +%= 3;'),
    ('usize', '', 'n<<=1', 'n.?.* <<= 1;'),
])
def test_numeric_constant_reference_write(tmp_path, type_name, setup, assignment, emitted):
    source = tmp_path / 'write.a7'
    source.write_text(setup + 'mutate::fn(n:ref ' + type_name + '){if n!=nil{' + assignment + '}}\n'
                      f'main::fn(){{x:{type_name}=0;mutate(x)}}\n')
    output = tmp_path / 'write.zig'
    result = subprocess.run([sys.executable, '-c', 'from a7.cli import main;main()', str(source),
                             '--mode', 'compile', '--format', 'json', '--output', str(output)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ''
    assert json.loads(result.stdout)['status'] == 'ok'
    code = output.read_text()
    assert emitted in code
    assert 'mutate(&x)' in code
    assert 'n = ' not in code


@pytest.mark.parametrize('type_name,assignment,message', [
    ('u8', 'n=256', 'Exact constant 256 is out of range for u8'),
    ('usize', 'n=-1', 'Exact constant -1 is out of range for usize'),
    ('usize', 'n=3.5', 'is fractional and cannot fit usize'),
    ('u8', 'n+=256', 'Exact constant 256 is out of range for u8'),
    ('usize', 'typed:i32=3;n=typed', "Assignment type mismatch: expected 'usize', got 'i32'"),
    ('usize', 'typed:f64=3.0;n=typed', "Assignment type mismatch: expected 'usize', got 'f64'"),
    ('usize', 'n=nil', 'Cannot assign to immutable binding'),
    ('usize', 'n=other', 'Cannot assign to immutable binding'),
])
def test_invalid_reference_write_stays_semantic(tmp_path, type_name, assignment, message):
    source = tmp_path / 'invalid.a7'
    source.write_text('mutate::fn(n:ref ' + type_name + ',other:ref ' + type_name + '){if n!=nil{' + assignment + '}}\n'
                      f'main::fn(){{x:{type_name}=0;y:{type_name}=0;mutate(x,y)}}\n')
    output = tmp_path / 'invalid.zig'
    result = subprocess.run([sys.executable, '-c', 'from a7.cli import main;main()', str(source),
                             '--mode', 'compile', '--format', 'json', '--output', str(output)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 6, result.stdout + result.stderr
    assert result.stderr == ''
    data = json.loads(result.stdout)
    assert data['error']['category'] == 'semantic'
    assert any(message in item['message'] for item in data['error']['details'])
    if assignment.startswith('typed:'):
        assert any(item.get('code') == 'assignment_type_mismatch'
                   for item in data['error']['details'])
    assert not output.exists()


@pytest.mark.parametrize('body,message', [
    ('p:=new usize;p=3', 'Reference not proven non-nil'),
    ('p:=new usize;if p==nil{ret};q:=p;del p;q=3', 'Use after move or delete'),
])
def test_contextual_write_still_requires_live_non_nil_storage(tmp_path, body, message):
    source = tmp_path / 'lifetime.a7'
    source.write_text('main::fn(){' + body + '}\n')
    output = tmp_path / 'lifetime.zig'
    result = subprocess.run([sys.executable, '-c', 'from a7.cli import main;main()', str(source),
                             '--mode', 'compile', '--format', 'json', '--output', str(output)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 6, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert any(item['type'] == 'SafetyError' and message in item['message']
               for item in data['error']['details'])
    assert not output.exists()
