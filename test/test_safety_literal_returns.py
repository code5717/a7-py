"""Literal selectors preserve the chosen reference's nil and lifetime facts."""

import pytest

from conftest import build_and_run, expect_exit, expect_ok

HEADER = 'Box :: struct { x: i32 }\n'
CHOOSE = '''choose :: fn(p: ref Box, flag: bool) ref Box {
 if flag { ret nil }
 ret p
}
'''
ALLOCATE = 'p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};'
SELECT = '''select :: fn(p:ref Box, flag:bool, q:ref Box) ref Box {
 if false { ret nil }
 if flag { ret q } else { ret p }
}
'''


def test_selected_nil_diagnostic_points_to_use(tmp_path):
    source = HEADER + CHOOSE + '''main :: fn() {
 p:=new Box;if p==nil{ret}
 r:=choose(p,true)
 if p!=nil {
  value:=r.x
 }
 del p
}
'''
    result = expect_exit(source, tmp_path, 6, 'Reference not proven non-nil')
    line = source.splitlines().index('  value:=r.x') + 1
    errors = [d for d in result.failure.details if 'Reference not proven non-nil' in d['message']]
    assert len(errors) == 1
    assert errors[0]['span']['start_line'] == line
    assert errors[0]['file'] == str(tmp_path / 'main.a7')


@pytest.mark.parametrize('call', ['r:ref Box=nil', 'r:=choose(p,true)'])
def test_unreachable_nil_use_keeps_static_proof_rule(tmp_path, call):
    # Existing direct-nil rejection also applies to a known nil call result.
    expect_exit(HEADER + CHOOSE + 'main::fn(){' + ALLOCATE
                + 'if false{' + call + ';value:=r.x};del p;del q}',
                tmp_path, 6, 'Reference not proven non-nil')


@pytest.mark.parametrize('flag,selected', [('true', 'q'), ('false', 'p')])
def test_deleting_selected_allocation_rejects(tmp_path, flag, selected):
    expect_exit(HEADER + SELECT + 'main::fn(){' + ALLOCATE
                + 'r:=select(p,' + flag + ',q);del ' + selected + ';value:=r.x}',
                tmp_path, 6, 'deleted')


@pytest.mark.parametrize('deleted', ['p', 'q'])
def test_return_captures_field_before_later_argument_replacement(tmp_path, deleted):
    source = HEADER + '''Holder::struct{ptr:ref Box}
replace::fn(h:ref Holder,q:ref Box)ref Box{h.ptr=q;ret q}
choose::fn(p:ref Box,flag:bool,other:ref Box)ref Box{if flag{ret nil};ret p}
main::fn(){''' + ALLOCATE + '''
 h:=Holder{ptr:p};if h.ptr==nil{ret}
 r:=choose(h.ptr,false,replace(h,q))
 del ''' + deleted + '''
 value:=r.x
}
'''
    if deleted == 'p':
        expect_exit(source, tmp_path, 6, 'deleted')
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize('deleted', ['p', 'q'])
def test_return_selects_later_argument_after_field_replacement(tmp_path, deleted):
    source = HEADER + SELECT + '''Holder::struct{ptr:ref Box}
replace::fn(h:ref Holder,q:ref Box)ref Box{h.ptr=q;ret q}
main::fn(){''' + ALLOCATE + '''
 h:=Holder{ptr:p};if h.ptr==nil{ret}
 r:=select(h.ptr,true,replace(h,q))
 del ''' + deleted + '''
 value:=r.x
}
'''
    if deleted == 'q':
        expect_exit(source, tmp_path, 6, 'deleted')
    else:
        expect_ok(source, tmp_path)


def test_generic_reference_nil_selection(tmp_path):
    source = HEADER + '''choose::fn(p:ref $T,flag:bool)ref $T{if flag{ret nil};ret p}
main::fn(){''' + ALLOCATE + 'r:=choose(p,true);value:=r.x}'
    expect_exit(source, tmp_path, 6, 'Reference not proven non-nil')


def test_module_call_uses_own_declaration(tmp_path):
    (tmp_path / 'dep.a7').write_text(HEADER + CHOOSE, encoding='utf-8')
    source = '''dep::import "dep"
choose::fn(p:ref dep.Box,flag:bool)ref dep.Box{ret p}
main::fn(){p:=new dep.Box;if p==nil{ret};r:=dep.choose(p,true);value:=r.x}
'''
    expect_exit(source, tmp_path, 6, 'Reference not proven non-nil')


def test_nil_actual_passthrough_cannot_be_dereferenced(tmp_path):
    expect_exit(HEADER + CHOOSE + 'main::fn(){r:=choose(nil,false);value:=r.x}',
                tmp_path, 6, 'Reference not proven non-nil')


def test_uncertified_selector_and_effect_body_keep_guarded_control(tmp_path):
    # These bodies stay outside literal selection. Use guarded results, without
    # treating the legacy summary's lost nil alternatives as desirable behavior.
    source = HEADER + '''g:i32=0
choose::fn(p:ref Box,flag:bool)ref Box{if flag{g=1;ret nil};ret p}
main::fn(){''' + ALLOCATE + '''flag:=true;r:=choose(p,flag)
 if r!=nil{value:=r.x}
 del p;del q
}
'''
    expect_ok(source, tmp_path)


NATIVE_CONTROL = '''io::import "std/io"
''' + HEADER + SELECT + CHOOSE + '''Holder::struct{ptr:ref Box}
replace::fn(h:ref Holder,q:ref Box)ref Box{h.ptr=q;ret q}
main::fn(){
'''
for _flag, _unselected in [('true', 'p'), ('false', 'q'), ('false', 'q'), ('true', 'p')]:
    NATIVE_CONTROL += '{' + ALLOCATE + 'p.x=7;q.x=9;r:=select(p,' + _flag + ',q);del ' + _unselected + ';io.println("{}",r.x);del r;}\n'
NATIVE_CONTROL += '''p:=new Box;if p==nil{ret};p.x=11
 empty:=choose(p,true)
 if empty!=nil{io.println("unexpected {}",empty.x)}
 live:=choose(p,false)
 io.println("{}",live.x)
 del p
'''
NATIVE_CONTROL += '{' + ALLOCATE + '''
 p.x=13;q.x=19
 h:=Holder{ptr:p};if h.ptr==nil{ret}
 r:=select(h.ptr,true,replace(h,q))
 del p
 io.println("{}",r.x)
 del q
}
}
'''


@pytest.mark.zig
@pytest.mark.parametrize('profile', ['debug', 'release', 'fast'])
def test_literal_returns_native(tmp_path, zig, profile):
    process = build_and_run(NATIVE_CONTROL, tmp_path, zig, profile=profile)
    assert process.returncode == 0, process.stderr
    assert process.stderr == ''
    assert process.stdout == '9\n7\n7\n9\n11\n19\n'
