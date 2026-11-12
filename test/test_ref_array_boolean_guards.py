"""Boolean result facts preserve access requirements and callable identity."""
import pytest
from conftest import compile_program, failure_text

HEADER = ('access::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'
          'false_flag::fn()bool{ret false}\n')


@pytest.mark.parametrize('body', [
    'access(nil,false_flag())',
    'invoke:=false_flag;copy:=invoke;access(nil,copy())',
])
def test_known_false_keeps_call_and_optional_access_in_output(tmp_path, body):
    result = compile_program(HEADER+'main::fn(){'+body+'}', tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)
    zig = (tmp_path/'main-debug.zig').read_text()
    assert 'a.?[0]' in zig
    assert 'return false;' in zig
    assert 'false_flag()' in zig or 'copy()' in zig


@pytest.mark.parametrize('is_library', [False, True])
def test_opposite_same_named_module_functions_keep_their_identity(tmp_path, is_library):
    (tmp_path/'yes.a7').write_text('pub flag::fn()bool{ret true}')
    (tmp_path/'no.a7').write_text('pub flag::fn()bool{ret false}')
    source = ('yes::import "yes"\nno::import "no"\n'+HEADER+
              'main::fn(){access(nil,no.flag())}')
    good = compile_program(source, tmp_path, is_library=is_library, name='good')
    assert int(good.exit_code) == 0, failure_text(good)
    bad = compile_program(source.replace('no.flag()', 'yes.flag()'), tmp_path,
                          is_library=is_library, name='bad')
    assert int(bad.exit_code) == 6
    assert 'reachable readonly callee read receives nil' in failure_text(bad)
    assert not (tmp_path/'bad-debug.zig').exists()


@pytest.mark.parametrize('helper,body,fragment', [
    ('', 'invoke:=false_flag;invoke=false_flag;access(nil,invoke())', 'non-nil'),
    ('', 'invoke:=false_flag;inner::fn(){access(nil,invoke())};inner()', 'non-nil'),
    ('conditional::fn(b:bool)bool{if b{ret false};ret true}\n',
     'access(nil,conditional(true))', 'non-nil'),
    ('missing::fn(b:bool)bool{if b{ret false}}\n',
     'access(nil,missing(true))', 'return'),
    ('safe_false::fn(x:i32)bool{ret false}\n',
     'p:ref[4]i32=nil;access(nil,safe_false(p[0]))', 'Reference not proven non-nil'),
    ('bad_false::fn()bool{p:ref[4]i32=nil;x:=p[0];ret false}\n',
     'access(nil,bad_false())', 'Reference not proven non-nil'),
])
def test_result_does_not_hide_unknown_origins_or_evaluation_errors(tmp_path, helper, body, fragment):
    result = compile_program(HEADER+helper+'main::fn(){'+body+'}', tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert fragment.lower() in failure_text(result).lower()
    assert not (tmp_path/'main-debug.zig').exists()


def test_false_result_does_not_hide_out_of_bounds_body(tmp_path):
    result = compile_program(HEADER.replace('a[0]', 'a[4]')+'main::fn(){access(nil,false_flag())}',tmp_path)
    assert int(result.exit_code) == 6
    assert 'Index not proven in bounds' in failure_text(result)


@pytest.mark.parametrize('deferred,fresh_guard', [(False,False),(False,True),(True,False),(True,True)])
def test_field_mutation_helpers_remain_outside_literal_return_shape(tmp_path, deferred, fresh_guard):
    helper = ('defer {h.ptr=nil};' if deferred else 'h.ptr=nil;')
    read = 'io.println("{}",h.ptr.value)'
    if fresh_guard:
        read = 'if h.ptr!=nil{'+read+'}'
    source = ('io::import "std/io"\nBox::struct{value:i32}\nHolder::struct{ptr:ref Box}\n'+HEADER+
              'clear_false::fn(h:ref Holder)bool{'+helper+'ret false}\n'
              'main::fn(){b:=new Box;if b==nil{ret};h:=Holder{ptr:b};'
              'if h.ptr!=nil{access(nil,clear_false(h));'+read+'};del b}')
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert 'reference-array caller requirement is unresolved' in failure_text(result)


def test_standalone_field_mutation_and_fresh_guard_stay_valid(tmp_path):
    source = ('io::import "std/io"\nBox::struct{value:i32}\nHolder::struct{ptr:ref Box}\n'+HEADER+
              'clear_false::fn(h:ref Holder)bool{h.ptr=nil;ret false}\n'
              'main::fn(){b:=new Box;if b==nil{ret};h:=Holder{ptr:b};'
              'clear_false(h);access(nil,false);if h.ptr!=nil{io.println("{}",h.ptr.value)};del b}')
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)
