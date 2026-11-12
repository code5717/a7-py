"""Secondary callee locations retain the file distinct from the primary caller."""
import pytest
from conftest import compile_program, failure_text

HELPER = 'Box :: struct { x: i32 }\n\nread :: fn(p: ref Box) {\n    i: usize = 0\n    for i = 0; i < 1; i += 1 { x := p.x }\n}\n'
ENTRY_HELPER = 'Box::struct{x:i32}\nb::fn(n:bool,p:ref Box){v:=true;if n{v=false};if v{x:=p.x};if n{ret}}\nf::fn(n:bool,p:ref Box){b(n,p)}\n'


@pytest.mark.parametrize('imported', [False, True])
def test_call_note_names_actual_callee_source(tmp_path, imported):
    if imported:
        (tmp_path/'helper.a7').write_text(HELPER)
        source = 'h :: import "helper"\nmain :: fn() {\n    h.read(nil)\n}\n'
        primary_line, callee = 3, tmp_path/'helper.a7'
    else:
        source = HELPER + '\nmain :: fn() {\n    read(nil)\n}\n'
        primary_line, callee = 9, tmp_path/'main.a7'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert len(result.failure.details) == 1
    error = result.failure.details[0]
    assert error['file'] == str(tmp_path/'main.a7')
    assert (error['span']['start_line'], error['span']['start_column']) == (primary_line, 5)
    note = f'callee use at line 5, column 37 in {callee}' if imported else 'callee use at line 5, column 37)'
    assert note in error['message']
    assert not (tmp_path/'main-debug.zig').exists()


def test_executable_entry_note_names_imported_read(tmp_path):
    (tmp_path/'helper.a7').write_text(ENTRY_HELPER)
    result = compile_program('h::import "helper"\nmain::fn(){flag:=false;h.f(flag,nil)}', tmp_path)
    assert int(result.exit_code) == 6, failure_text(result)
    assert len(result.failure.details) == 1
    error = result.failure.details[0]
    assert 'readonly executable entry field access' in error['message']
    assert error['file'] == str(tmp_path/'main.a7')
    assert error['span']['start_line'] == 2
    assert f'callee use at line 2, column 55 in {tmp_path/"helper.a7"}' in error['message']


@pytest.mark.parametrize('guarded', [False, True])
def test_source_note_does_not_change_valid_calls(tmp_path, guarded):
    helper = HELPER.replace('    i: usize', '    if p == nil { ret }\n    i: usize') if guarded else HELPER
    (tmp_path/'helper.a7').write_text(helper)
    body = 'h.read(nil)' if guarded else 'value:=h.Box{x:7};h.read(value)'
    result = compile_program('h::import "helper"\nmain::fn(){'+body+'}', tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)
    assert (tmp_path/'main-debug.zig').exists()
