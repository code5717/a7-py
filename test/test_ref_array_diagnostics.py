"""Ref-array proof failures distinguish caller requirements from numeric bounds."""
import pytest
from conftest import compile_program, failure_text


@pytest.mark.parametrize('index', ['0', 'i'])
def test_missing_summary_does_not_recommend_fixed_array_len(tmp_path, index):
    source = ('Counts::struct{value:i32}\n'
              'change::fn(a:ref[4]i32,c:ref Counts,i:usize){c.value=1;x:=a['+index+']}\n'
              'main::fn(){values:[4]i32=[11,22,33,44];c:=Counts{value:0};change(values,c,0)}')
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert result.failure.category == 'semantic'
    bounds = [e for e in result.failure.details if e['message'].startswith('Index not proven in bounds')]
    assert len(bounds) == 1
    error = bounds[0]
    assert error['type'] == 'SafetyError'
    assert error['span']['start_line'] == 2
    assert error['span']['start_column'] == source.splitlines()[1].index('a[')+1
    assert error['file'] == str(tmp_path/'main.a7')
    assert error['message'].endswith('reference-array access requires a complete caller proof: function access requirements are unresolved)')
    assert error['hint'] == "The current analysis cannot resolve this function's access requirements; an index guard alone cannot establish the required caller proof."
    assert '.len' not in error['hint'] and 'Copy' not in error['hint']
    assert any('reference-array caller requirement is unresolved' in e['message'] and e['span']['start_line'] == 3 for e in result.failure.details)
    assert not (tmp_path/'main-debug.zig').exists()


def test_untrackable_callable_origin_is_distinct(tmp_path):
    source = ('access::fn(a:ref[4]i32){x:=a[0]}\n'
              'main::fn(){invoke:=access;invoke=access;values:[4]i32=[1,2,3,4];invoke(values)}')
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 6
    assert result.failure.category == 'semantic'
    error = next(e for e in result.failure.details if e['message'].startswith('Index not proven in bounds'))
    assert error['span']['start_line'] == 1
    assert error['span']['start_column'] == source.splitlines()[0].index('a[')+1
    assert 'callable origin is not trackable' in error['message']
    assert error['hint'] == 'Use direct calls or unwritten, uncaptured local callable aliases; an index guard alone cannot establish the required caller proof.'
    assert not (tmp_path/'main-debug.zig').exists()


@pytest.mark.parametrize('typ,index,hint', [
    ('ref[4]i32','4','This array has 4 elements; valid indexes are 0 to 3'),
    ('ref[4]i32','i',"Guard the index: 'if i < 4 { ... }' around the access"),
    ('[]i32','i',"Guard the index: 'if i < a.len { ... }' around the access"),
])
def test_real_bounds_errors_retain_correct_advice(tmp_path, typ, index, hint):
    result = compile_program('read::fn(a:'+typ+',i:usize){x:=a['+index+']}\nmain::fn(){}',tmp_path)
    assert int(result.exit_code) == 6
    assert result.failure.category == 'semantic'
    errors = result.failure.details
    assert len(errors) == 1
    assert errors[0]['message'].endswith('index bounds are not proven)')
    assert errors[0]['hint'] == hint
    assert not (tmp_path/'main-debug.zig').exists()
