"""Registered no-result hooks cannot supply values; statement effects remain valid."""
import pytest
from conftest import expect_exit, expect_ok

HEADER = 'out::import "io"\n'

@pytest.mark.parametrize('body', [
    'x:=out.println("x")',
    'x::out.println("x")',
    'x:=[out.println("x")]',
    'x:=[[out.println("x")]]',
    'out.println("{}",out.println("x"))',
    'x:=if true{out.println("a")}else{out.println("b")}',
    'x:=match true{case true:out.println("a") else:out.println("b")}',
])
def test_registered_calls_cannot_supply_inferred_values(tmp_path, body):
    result = expect_exit(HEADER+'main::fn(){'+body+'}', tmp_path, 6, 'returns no value')
    assert all(item['span']['start_line'] == 2 for item in result.failure.details)

@pytest.mark.parametrize('hook', ['print', 'eprintln'])
def test_other_registered_no_result_hooks(tmp_path, hook):
    expect_exit(HEADER+f'main::fn(){{x:=out.{hook}("x")}}',tmp_path,6,f'std.io.{hook} returns no value')


def test_statement_effect_roots_include_headers_and_nested_bodies(tmp_path):
    source = HEADER+'''g::fn(x:$T){out.println("generic")}
main::fn(){
    defer {out.println("defer")}
    for out.println("init");false;out.println("update"){}
    if true{out.println("if")}else{out.println("else")}
    match true{case true:out.println("arm") else:out.println("default")}
    f::fn(){out.println("nested")};f();g(1)
}'''
    expect_ok(source,tmp_path)


def test_registered_result_and_ordinary_void_are_not_banned(tmp_path):
    (tmp_path/'local_io.a7').write_text('println::fn(){}')
    expect_ok(HEADER+'local::import "local_io";println::fn(){};main::fn(){a:=println();b:=local.println();c:=out.println_ok("x")}',tmp_path)


def test_existing_exact_overflow_diagnostic_keeps_priority(tmp_path):
    result=expect_exit(HEADER+'main::fn(){x:=out.println("x");y:=2147483648}',tmp_path,6,'2147483648')
    assert 'returns no value' not in str(result.failure.details)


def test_imported_error_uses_original_call_location(tmp_path):
    helper=tmp_path/'helper.a7'
    helper.write_text(HEADER+'f::fn(){\n x:=out.println("x")\n}')
    result=expect_exit('dep::import "helper";main::fn(){dep.f()}',tmp_path,6,'returns no value')
    detail=result.failure.details[0]
    assert detail['span']['start_line']==3
    assert str(helper) in str(detail)


def test_generic_origin_is_not_duplicated_for_two_instantiations(tmp_path):
    result=expect_exit(HEADER+'g::fn(x:$T){y:=out.println("x")};main::fn(){g(1);g(true)}',tmp_path,6,'returns no value')
    assert len(result.failure.details)==1


def test_library_body_is_checked_without_executable_root(tmp_path):
    expect_exit(HEADER+'f::fn(){x:=out.println("x")}',tmp_path,6,'returns no value',is_library=True)
