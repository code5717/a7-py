"""The selected executable entry applies certified readonly call requirements."""
import pytest
from conftest import expect_exit, expect_ok

HEADER = '''Box::struct{x:i32}
b::fn(n:bool,p:ref Box){v:=true;if n{v=false};if v{x:=p.x};if n{ret}}
f::fn(n:bool,p:ref Box){b(n,p)}
'''


@pytest.mark.parametrize('body', [
    'flag:=false;f(flag,nil)',
    'flag:=true;flag=false;f(flag,nil)',
    'flag:=false;old:=flag;flag=true;f(old,nil)',
    'flag:=true;{flag:=false;f(flag,nil)}',
    'flag:=true;{defer flag=false};f(flag,nil)',
])
def test_known_entry_path_to_nil_read_is_rejected(tmp_path, body):
    result = expect_exit(HEADER+'main::fn(){'+body+'}', tmp_path, 6,
                         'readonly executable entry field access')
    assert len(result.failure.details) == 1
    assert 'callee use at line 2' in result.failure.details[0]['message']
    assert result.failure.details[0]['span']['start_line'] == 4


@pytest.mark.parametrize('body', [
    'flag:=true;f(flag,nil)',
    'flag:=false;flag=true;f(flag,nil)',
    'flag:=true;old:=flag;flag=false;f(old,nil)',
    'flag:=false;{flag:=true;f(flag,nil)}',
    'flag:=true;defer flag=false;f(flag,nil)',
])
def test_known_nonreading_entry_path_stays_valid(tmp_path, body):
    expect_ok(HEADER+'main::fn(){'+body+'}', tmp_path)


def test_library_main_is_not_an_implicit_executable_root(tmp_path):
    expect_ok(HEADER+'main::fn(){flag:=false;f(flag,nil)}', tmp_path, is_library=True)


def test_guarded_nil_entry_stays_valid(tmp_path):
    source=HEADER.replace('if v{x:=p.x}', 'if v{if p!=nil{x:=p.x}}')
    expect_ok(source+'main::fn(){flag:=false;f(flag,nil)}', tmp_path)


@pytest.mark.parametrize('main', ['main::fn(n:bool){}', 'main::fn()i32{ret 0}'])
def test_invalid_entry_signature_keeps_existing_error(tmp_path, main):
    expect_exit(main, tmp_path, 6, 'Executable entry point main must have no parameters and no return value')


def test_existing_call_error_is_not_duplicated_at_entry(tmp_path):
    result=expect_exit(HEADER+'main::fn(){f(false,nil)}', tmp_path, 6, 'readonly callee field access')
    assert len(result.failure.details) == 1
    assert 'readonly executable entry' not in result.failure.details[0]['message']


def test_unused_imported_main_is_not_the_entry(tmp_path):
    (tmp_path/'other.a7').write_text(HEADER+'main::fn(){flag:=false;f(flag,nil)}')
    expect_ok('other::import "other";main::fn(){}',tmp_path)


def test_imported_main_does_not_hide_selected_entry(tmp_path):
    (tmp_path/'other.a7').write_text('main::fn(){}')
    expect_exit('other::import "other";'+HEADER+'main::fn(){flag:=false;f(flag,nil)}',
                tmp_path,6,'readonly executable entry')


def test_imported_main_called_by_entry_has_ordinary_call_semantics(tmp_path):
    (tmp_path/'other.a7').write_text(HEADER+'main::fn(){flag:=false;f(flag,nil)}')
    expect_exit('other::import "other";main::fn(){other.main()}',tmp_path,6,'readonly callee')


def test_unused_nested_main_is_not_an_entry(tmp_path):
    expect_ok(HEADER+'main::fn(){main::fn(){flag:=false;f(flag,nil)}}',tmp_path)


@pytest.mark.parametrize('body', [
    'flag:=true;i:usize=0;while i<1{flag=false;i+=1};f(flag,nil)',
    'flag:=true;mut(flag);f(flag,nil)',
    'flag:=false;p:=new Box;if p==nil{ret};f(flag,p);del p',
])
def test_incomplete_entry_keeps_existing_behavior(tmp_path,body):
    helper='mut::fn(n:ref bool){if n!=nil{n=false}}\n'
    expect_ok(HEADER+helper+'main::fn(){'+body+'}',tmp_path)
