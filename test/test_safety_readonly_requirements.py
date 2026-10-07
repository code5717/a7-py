"""Readonly callee reads retain their execution guards at actual calls."""
import pytest
from conftest import expect_exit, expect_ok

HEADER = 'Box::struct{x:i32}\n'
LOOP = 'i:usize=0;for i=0;i<1;i+=1{BODY}'


def test_loop_read_error_is_located_at_call(tmp_path):
    source = HEADER + 'read::fn(r:ref Box){' + LOOP.replace('BODY', 'x:=r.x') + '}\nmain::fn(){\n read(nil)\n}\n'
    result = expect_exit(source, tmp_path, 6, 'reachable readonly callee read receives nil')
    errors = [d for d in result.failure.details if 'readonly callee' in d['message']]
    assert len(errors) == 1
    assert errors[0]['span']['start_line'] == 4
    assert 'callee use at' in errors[0]['message']


@pytest.mark.parametrize('body', [
    'if r!=nil{' + LOOP.replace('BODY', 'x:=r.x') + '}',
    'if r==nil{ret};' + LOOP.replace('BODY', 'x:=r.x'),
    'i:usize=0;for i=0;i<0;i+=1{x:=r.x}',
    'while false{x:=r.x}',
    'match r{case nil:{ret} else:{x:=r.x}}',
])
def test_nil_is_valid_when_callee_does_not_read_it(tmp_path, body):
    expect_ok(HEADER + 'read::fn(r:ref Box){' + body + '}\nmain::fn(){read(nil)}', tmp_path)


@pytest.mark.parametrize('flag,exit_code', [('false', 0), ('true', 6)])
def test_forwarded_formal_selector_is_substituted_at_outer_call(tmp_path, flag, exit_code):
    source = HEADER + 'read::fn(r:ref Box,f:bool){' + LOOP.replace('BODY', 'if f{x:=r.x}') + '}\nforward::fn(f:bool){read(nil,f)}\nmain::fn(){forward(' + flag + ')}'
    if exit_code:
        expect_exit(source, tmp_path, exit_code, 'readonly callee')
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize('guard,exit_code', [('', 6), ('if r!=nil', 0)])
def test_deferred_loop_requirement_uses_its_guard(tmp_path, guard, exit_code):
    body = LOOP.replace('BODY', 'x:=r.x')
    if guard:
        body = guard + '{' + body + '}'
    source = HEADER + 'read::fn(r:ref Box){defer{' + body + '}}\nmain::fn(){read(nil)}'
    if exit_code:
        expect_exit(source, tmp_path, exit_code, 'readonly callee')
    else:
        expect_ok(source, tmp_path)


def test_unselected_short_circuit_field_read_is_not_made_unconditional(tmp_path):
    # The general short-circuit expression is outside the new readonly certificate.
    source = HEADER + 'read::fn(r:ref Box){i:usize=0;for i=0;i<1;i+=1{x:=false and r.x==1}}\nmain::fn(){read(nil)}'
    expect_ok(source, tmp_path)


def test_existing_direct_callee_error_is_preserved(tmp_path):
    expect_exit(HEADER + 'read::fn(r:ref Box,f:bool){if f{x:=r.x}}\nmain::fn(){read(nil,false)}', tmp_path, 6, 'callee field access')


def test_live_and_borrowed_actuals_preserve_acceptance(tmp_path):
    source = HEADER + 'read::fn(r:ref Box){' + LOOP.replace('BODY', 'x:=r.x') + '}\nmain::fn(){b:Box;read(b);p:=new Box;if p==nil{ret};read(p);del p}'
    expect_ok(source, tmp_path)


def test_file_constant_call_precedes_function_summary_construction(tmp_path):
    expect_ok('value::fn()i32{ret 1}\nx::value()\nmain::fn(){y:=x}', tmp_path)


@pytest.mark.parametrize('start,bound,op,step,exit_value', [
    (0, 1, '<', 1, 1),
    (0, 0, '<', 1, 0),
    (1, 6, '<', 2, 7),
    (1, 5, '<=', 2, 7),
])
@pytest.mark.parametrize('deferred', [False, True])
def test_counter_exit_value_controls_later_nil_read(tmp_path, start, bound, op, step, exit_value, deferred):
    for tested, expected in {exit_value: 6, start: 6 if start == exit_value else 0, exit_value + 1: 0}.items():
        condition = f'if i=={tested}{{x:=r.x}}'
        before = 'defer{' + condition + '}' if deferred else ''
        after = '' if deferred else condition
        body = f'i:usize={start};' + before + f';for i={start};i{op}{bound};i+={step}{{}};' + after
        source = HEADER + 'read::fn(r:ref Box){' + body + '}\nmain::fn(){read(nil)}'
        case_dir = tmp_path / str(tested)
        case_dir.mkdir()
        if expected:
            expect_exit(source, case_dir, expected, 'readonly callee')
        else:
            expect_ok(source, case_dir)


def test_counter_guard_before_loop_keeps_initial_value(tmp_path):
    expect_exit(HEADER + 'read::fn(r:ref Box){i:usize=0;if i==0{x:=r.x};for i=0;i<1;i+=1{}}\nmain::fn(){read(nil)}', tmp_path, 6, 'readonly callee')
