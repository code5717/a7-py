"""Local guard proofs must hold for every input and preserve storage effects."""
import pytest
from conftest import compile_program, failure_text

HEADER = 'access::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'

@pytest.mark.parametrize('is_library', [False, True])
@pytest.mark.parametrize('body', [
    'if b{ret};access(nil,b)',
    'if !b{access(nil,b)}',
    'if b==false{access(nil,b)}',
    'saved:=b;if saved{ret};access(nil,saved)',
    'if false!=b{ret};access(nil,b)',
    'if !!b{ret};access(nil,b)',
    'v:=b;if v{ret};saved:=v;v=true;access(nil,saved)',
    'if b{ret};{b:=true};access(nil,b)',
])
def test_universal_local_guard_keeps_optional_index_and_call(tmp_path, body, is_library):
    source = HEADER+'wrap::fn(b:bool){'+body+'}\nmain::fn(){wrap(false);wrap(true)}'
    result = compile_program(source, tmp_path, is_library=is_library)
    assert int(result.exit_code) == 0, failure_text(result)
    zig = (tmp_path/'main-debug.zig').read_text()
    assert 'a.?[0]' in zig and 'access(' in zig

@pytest.mark.parametrize('body', [
    'v:=b;if v{ret};v=true;access(nil,v)',
    'v:=false;if b{v=true};access(nil,v)',
    'v:=false;if b{v=other};access(nil,v)',
    'v:=false;while b{v=true;break};access(nil,v)',
    'v:=false;i:usize=0;for i=0;i<2;i+=1{access(nil,v);v=true}',
    'v:=b;if v{ret};{defer {v=true}};access(nil,v)',
    'v:=b;if v{ret};set::fn(){v=true};set();access(nil,v)',
    'access(nil,b)',
])
def test_mutation_join_loop_defer_and_unknown_do_not_reuse_false(tmp_path, body):
    result = compile_program(HEADER+'wrap::fn(b:bool,other:bool){'+body+'}\nmain::fn(){wrap(false,false)}', tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert 'nil' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()

@pytest.mark.parametrize('source', [
    'flip::fn(b:ref bool){if b==nil{ret};b=true}\nwrap::fn(b:bool){v:=b;if v{ret};flip(v);access(nil,v)}\nmain::fn(){wrap(false)}',
    'Flags::struct{b:bool}\nflip::fn(f:ref Flags){if f==nil{ret};f.b=true}\nwrap::fn(f:ref Flags){if f==nil{ret};if f.b{ret};flip(f);access(nil,f.b)}\nmain::fn(){f:=Flags{b:false};wrap(f)}',
    'g:bool=false\nmain::fn(){if g{ret};access(nil,g)}',
])
def test_exposed_and_nonlocal_cells_remain_unknown(tmp_path, source):
    result = compile_program(HEADER+source,tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert 'nil' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()

@pytest.mark.parametrize('body,exit_code', [
    ('access(nil,false)',0), ('access(nil,true)',6),
    ('a:[4]i32=[1,2,3,4];access(a,true)',0),
])
def test_existing_literal_and_borrowed_controls(tmp_path,body,exit_code):
    result=compile_program(HEADER+'main::fn(){'+body+'}',tmp_path)
    assert int(result.exit_code)==exit_code,failure_text(result)

@pytest.mark.parametrize('body', [
    'if b{access(nil,!b)}',
    'v:=b;if b{v=false}else{v=false};access(nil,v)',
])
def test_negated_value_and_equal_join_are_value_facts(tmp_path, body):
    result=compile_program(HEADER+'wrap::fn(b:bool){'+body+'}\nmain::fn(){wrap(false);wrap(true)}',tmp_path)
    assert int(result.exit_code)==0,failure_text(result)

@pytest.mark.parametrize('call', ['ordered(nil,v,flip(v))', 'reversed(nil,flip(v),v)'])
def test_borrow_exposure_stays_unknown_in_both_argument_orders(tmp_path, call):
    source=('ordered::fn(a:ref[4]i32,b:bool,ignored:bool){if b{x:=a[0]}}\n'
            'reversed::fn(a:ref[4]i32,ignored:bool,b:bool){if b{x:=a[0]}}\n'
            'flip::fn(v:ref bool)bool{if v==nil{ret false};v=true;ret false}\n'
            'main::fn(){v:=false;'+call+'}')
    result=compile_program(source,tmp_path)
    assert int(result.exit_code)==6,failure_text(result)
    assert 'nil' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()

@pytest.mark.parametrize('body', [
    'v:=false;i:usize=0;for i=0;i<2;i+=1{access(nil,v);defer {v=true}}',
    'v:=false;while b{v=true;continue};access(nil,v)',
])
def test_loop_deferred_and_continue_writes_drop_prior_boolean(tmp_path, body):
    result=compile_program(HEADER+'wrap::fn(b:bool){'+body+'}\nmain::fn(){wrap(false)}',tmp_path)
    assert int(result.exit_code)==6,failure_text(result)
    assert 'nil' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()

@pytest.mark.parametrize('body', [
    'v:=false;r:ref bool=v',
    'v:=false;h:=Holder{value:v}',
])
def test_value_storage_does_not_implicitly_create_a_reference_alias(tmp_path,body):
    result=compile_program('Holder::struct{value:ref bool}\nmain::fn(){'+body+'}',tmp_path)
    assert int(result.exit_code)==6,failure_text(result)
    assert 'mismatch' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()

@pytest.mark.parametrize('body', [
    'v:=false;borrow::fn(x:ref bool)ref bool{ret x};r:=borrow(v);access(nil,v)',
    'v:=false;later::fn(){v=true};defer {later()};access(nil,v)',
])
def test_reference_alias_and_deferred_capture_exclude_the_cell(tmp_path,body):
    result=compile_program(HEADER+'main::fn(){'+body+'}',tmp_path)
    assert int(result.exit_code)==6,failure_text(result)
    assert 'nil' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()

def test_forward_nested_capture_does_not_leave_outer_cell_eligible(tmp_path):
    source=HEADER+'main::fn(){set::fn(){v=true};v:=false;set();access(nil,v)}'
    result=compile_program(source,tmp_path)
    assert int(result.exit_code)==6,failure_text(result)
    assert 'nil' in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()
