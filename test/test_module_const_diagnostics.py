import pytest
from conftest import compile_program, failure_text, expect_ok

@pytest.mark.parametrize('module,statement', [
    ('VALUE::5', 'a.VALUE=6'),
    ('VALUE::5', 'a.VALUE+=1'),
    ('VALUE::cast(i32,5)', 'a.VALUE=6'),
    ('Box::struct{x:i32}\nVALUE::Box{x:5}', 'a.VALUE.x=6'),
    ('VALUE::([1,2])', 'a.VALUE[0]=6'),
])
def test_imported_constant_assignment_names_its_qualified_binding(module, statement, tmp_path):
    (tmp_path/'a.a7').write_text(module)
    result=compile_program('a::import "a"\nmain::fn(){'+statement+'}',tmp_path)
    assert int(result.exit_code)==6, failure_text(result)
    assert "'a.VALUE' is immutable: it is a constant" in failure_text(result)
    assert "'a' is not a variable" not in failure_text(result)
    assert any(detail.get('file')==str(tmp_path/'main.a7') for detail in result.failure.details)


def test_module_variables_and_ordinary_fields_remain_writable(tmp_path):
    (tmp_path/'a.a7').write_text('Box::struct{VALUE:i32}\nvalue:i32=5')
    expect_ok('a::import "a"\nmain::fn(){a.value=6;a.value+=1;'
              'b:=a.Box{VALUE:5};b.VALUE=6}',tmp_path)


def test_imported_constant_still_folds_for_size_and_value(tmp_path):
    (tmp_path/'a.a7').write_text('VALUE::5')
    expect_ok('a::import "a"\nmain::fn(){buf:[a.VALUE+1]i32;x:=a.VALUE*2}',tmp_path)
    emitted=(tmp_path/'main-debug.zig').read_text()
    assert '[6]i32' in emitted
    assert ' = 10;' in emitted


@pytest.mark.parametrize('field,message', [('_VALUE',"Private declaration '_VALUE'"),('MISSING',"has no declaration 'MISSING'")])
def test_inaccessible_module_members_keep_lookup_diagnostics(field,message,tmp_path):
    (tmp_path/'a.a7').write_text('_VALUE::5')
    result=compile_program('a::import "a"\nmain::fn(){a.'+field+'=6}',tmp_path)
    assert int(result.exit_code)==6
    assert message in failure_text(result)
