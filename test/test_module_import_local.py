"""L76: imported files expose declarations, not their import aliases."""
import pytest
from a7.compile import A7Compiler
from conftest import compile_program, expect_ok, failure_text


def files(tmp_path):
    (tmp_path/'a.a7').write_text('b::import "b"\n_hidden::import "c"\nio::import "std/io"\nvalue::fn()i32{ret b.value()}\nRecord::struct{b:i32}\nrecord:Record=Record{b:9}\n_private::3')
    (tmp_path/'b.a7').write_text('c::import "c"\nvalue::fn()i32{ret 42}\nVALUE::7\nBox::struct{value:i32}')
    (tmp_path/'c.a7').write_text('value::fn()i32{ret 6}')


@pytest.mark.parametrize('mode', ['compile', 'semantic'])
@pytest.mark.parametrize('body', [
    'x:=a.b.value()', 'x:=a.b', 'x:=a.b.VALUE', 'X::a.b.VALUE;x:=X',
    'x:=a.b.c.value()', 'x:a.b', 'x:a.b(i32)', 'x:=a.b{}',
    'x:=cast(a.b,1)', 'buf:[a.b.VALUE]i32',
    'match 1 {case a.b.VALUE:{} else:{}}', 'match 1 {case a.b:{} else:{}}',
    'a.io.println("{}",1)',
])
def test_forwarded_import_is_located_semantic_error(body, mode, tmp_path):
    files(tmp_path)
    source=tmp_path/'main.a7'
    source.write_text('a::import "a"\nmain::fn(){'+body+'}')
    result=A7Compiler(mode=mode).compile_file_detailed(str(source),str(tmp_path/'main-debug.zig'))
    assert int(result.exit_code)==6, failure_text(result)
    text=failure_text(result)
    assert 'is local to module' in text
    assert 'import its dependency directly in this file' in text
    assert 'dep :: import "<dependency path>"' in text
    assert 'Choose an unused alias' in text
    assert 'path resolved from this file' in text
    assert any(d.get('file')==str(tmp_path/'main.a7') for d in result.failure.details)
    assert not (tmp_path/'main-debug.zig').exists()


def test_file_scope_enum_constant_and_imported_error_owner(tmp_path):
    files(tmp_path)
    (tmp_path/'consumer.a7').write_text('a::import "a"\nE::enum{X=a.b.VALUE}')
    result=compile_program('c::import "consumer"\nmain::fn(){}',tmp_path)
    assert int(result.exit_code)==6
    assert 'is local to module' in failure_text(result)
    assert any(d.get('file')==str(tmp_path/'consumer.a7') for d in result.failure.details)


@pytest.mark.parametrize('body', ['x:=a._hidden.value()', 'x:=a._private'])
def test_private_members_keep_visibility_diagnostic(body, tmp_path):
    files(tmp_path)
    result=compile_program('a::import "a"\nmain::fn(){'+body+'}',tmp_path)
    assert int(result.exit_code)==6
    assert 'Private declaration' in failure_text(result)


def test_direct_imports_wrappers_fields_and_importer_local_names(tmp_path):
    files(tmp_path)
    # b is an import in a.a7, but an ordinary local in main.a7.
    expect_ok('a::import "a"\ndirect::import "b"\nmain::fn(){'
        'b:=a.Record{b:8};x:=b.b;y:=a.record.b;z:=a.value();'
        'q:=direct.value();v:direct.Box;n:=direct.VALUE;'
        '__local::fn(__arg:i32)i32{ret __arg};r:=__local(q)}',tmp_path)


@pytest.mark.parametrize('body', ['x:a.b.Box', 'x:=a.b.Box{value:1}'])
def test_unsupported_multidot_type_grammar_is_unchanged(body, tmp_path):
    files(tmp_path)
    result=compile_program('a::import "a"\nmain::fn(){'+body+'}',tmp_path)
    assert int(result.exit_code)==5


def test_direct_import_and_public_wrapper_native_controls(tmp_path, zig):
    from conftest import run_all_profiles
    files(tmp_path)
    assert run_all_profiles('io::import "std/io"\na::import "a"\n'
        'direct::import "b"\nmain::fn(){io.println("{}",direct.value());'
        'io.println("{}",a.value())}',tmp_path,zig)=='42\n42\n'
