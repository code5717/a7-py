"""Borrowed scalar addresses keep their nil domain through readonly forwarding."""
import pytest
from conftest import expect_exit, expect_ok

CASES=[]
for typ,value in [('i32','0'),('i32','1'),('i32','2'),('i32','-2147483648'),('i32','2147483647'),('bool','false'),('bool','true')]:
    for nil_branch,expected in [('!=',6),('==',0)]:
        CASES.append((f'{typ}_{value}_{nil_branch}',
            'Box::struct{x:i32}\n'
            f'g::fn(n:ref {typ},p:ref Box){{if n{nil_branch}nil{{y:=p.x}};if n==nil{{ret}}}}\n'
            f'f::fn(p:ref Box){{v:{typ}={value};g(v,p)}}\nmain::fn(){{f(nil)}}',expected))
for route in ['direct','copied_local','forwarded','deferred','inner_deferred','reverse_guard']:
    for op,expected in [('!=',6),('==',0)]:
        guard=f'n{op}nil' if route!='reverse_guard' else f'nil{op}n'
        definitions=f'Box::struct{{x:i32}}\ng::fn(n:ref i32,p:ref Box){{if {guard}{{y:=p.x}};if n==nil{{ret}}}}\n'
        if route=='direct':tail='main::fn(){v:i32=1;g(v,nil)}'
        elif route=='copied_local':tail='f::fn(p:ref Box){v:i32=1;w:=v;g(w,p)}\nmain::fn(){f(nil)}'
        elif route=='forwarded':tail='h::fn(n:ref i32,p:ref Box){g(n,p)}\nf::fn(p:ref Box){v:i32=1;h(v,p)}\nmain::fn(){f(nil)}'
        elif route=='deferred':tail='f::fn(p:ref Box){v:i32=1;defer{g(v,p)}}\nmain::fn(){f(nil)}'
        elif route=='inner_deferred':tail='f::fn(p:ref Box){v:i32=1;{defer{g(v,p)}}}\nmain::fn(){f(nil)}'
        else:tail='f::fn(p:ref Box){v:i32=1;g(v,p)}\nmain::fn(){f(nil)}'
        CASES.append((f'{route}_{op}',definitions+tail,expected))
for op,expected in [('==',6),('!=',0)]:
    CASES.append((f'true_nil_reference_{op}',
        f'Box::struct{{x:i32}}\ng::fn(n:ref i32,p:ref Box){{if n{op}nil{{y:=p.x}};if n==nil{{ret}}}}\n'
        'f::fn(p:ref Box){g(nil,p)}\nmain::fn(){f(nil)}',expected))
for flag,expected in [('true',6),('false',0)]:
    CASES.append((f'bool_value_selector_{flag}',
        'Box::struct{x:i32}\ng::fn(n:bool,p:ref Box){if n{y:=p.x};if n{ret}}\n'
        f'f::fn(p:ref Box){{g({flag},p)}}\nmain::fn(){{f(nil)}}',expected))
CASES.append(('guarded_reference_actual',
    'Box::struct{x:i32}\ng::fn(n:ref i32,p:ref Box){if n!=nil{y:=p.x};if n==nil{ret}}\n'
    'f::fn(p:ref Box){v:i32=1;g(v,p)}\nmain::fn(){p:=new Box;if p==nil{ret};f(p);del p}',0))

@pytest.mark.parametrize('name,source,expected',CASES,ids=[x[0] for x in CASES])
def test_forwarded_borrow_uses_address_nilness(tmp_path,name,source,expected):
    if expected:
        expect_exit(source,tmp_path,6,'readonly callee')
    else:
        expect_ok(source,tmp_path)


def test_literal_cannot_be_passed_as_writable_borrow(tmp_path):
    expect_exit('g::fn(n:ref i32){}\nmain::fn(){g(1)}',tmp_path,6,'Argument type mismatch')


@pytest.mark.parametrize('boolean_first',[False,True])
@pytest.mark.parametrize('flag,expected',[('true',6),('false',0)])
def test_integer_and_boolean_environments_do_not_share_identity(tmp_path,boolean_first,flag,expected):
    calls=[f'a(1,p)',f'b({flag},p)']
    if boolean_first:
        calls.reverse()
    source='''Box::struct{x:i32}
a::fn(n:i32,p:ref Box){if n==9{y:=p.x};if n==8{ret}}
b::fn(n:bool,p:ref Box){v:=false;if n{v=true};if v{y:=p.x};if n==false{ret}}
f::fn(p:ref Box){CALLS}
main::fn(){f(nil)}'''.replace('CALLS',';'.join(calls))
    if expected:
        expect_exit(source,tmp_path,6,'readonly callee')
    else:
        expect_ok(source,tmp_path)


@pytest.mark.parametrize('depth',[2,4,6,8])
def test_permuted_forwarding_stays_within_expanded_work_certificate(tmp_path,depth):
    # Count real evaluator states at its Python profiling boundary. The source
    # certificate must include every callee expansion, not only stored DAG nodes.
    import sys
    records=[]
    def observe(frame,event,result):
        if event=='return' and frame.f_code.co_name=='evaluate' and frame.f_code.co_filename.endswith('/readonly_requirements.py') and 'environments' in frame.f_locals:
            values=frame.f_locals;engine=values['self']
            records.append((len(values['cache']),engine.expanded_work[values['name']],engine.work_bound))
    names=[f'a{i}' for i in range(10)]
    params='p:ref Box,'+','.join(n+':i32' for n in names)
    lines=['Box::struct{x:i32}',f'f{depth}::fn({params})'+'{if a0==0{y:=p.x};if a0==1{ret}}']
    for level in reversed(range(depth)):
        rotate=names[1:]+names[:1];swap=[names[1],names[0],*names[2:]]
        lines.append(f'f{level}::fn({params})'+'{'+f'f{level+1}(p,'+','.join(rotate)+');'+f'f{level+1}(p,'+','.join(swap)+')}')
    lines.append('main::fn(){f0(nil,'+','.join(map(str,range(10)))+')}')
    old_profile=sys.getprofile()
    sys.setprofile(observe)
    try:
        expect_exit('\n'.join(lines),tmp_path,6,'readonly callee')
    finally:
        sys.setprofile(old_profile)
    assert records
    assert all(cache<=expanded<=bound for cache,expanded,bound in records)


BORROW_NATIVE_SOURCE='''
io::import "std/io"
Box::struct{x:i32}
g::fn(n:ref i32,p:ref Box)i32{
    if n==nil{ret p.x}
    if n==nil{ret 0}
    ret 17
}
f::fn(value:i32)i32{v:=value;ret g(v,nil)}
main::fn(){
    io.println("{}",f(0))
    io.println("{}",f(1))
    io.println("{}",f(2))
}
'''

@pytest.mark.zig
@pytest.mark.parametrize('profile',['debug','release','fast'])
def test_borrow_nil_guard_preserves_native_value(tmp_path,zig,profile):
    from native_profiles import run_profile
    result=run_profile(BORROW_NATIVE_SOURCE,tmp_path,zig,profile)
    assert (result.returncode,result.stdout,result.stderr)==(0,'17\n17\n17\n','')


def test_borrow_summary_does_not_restore_a_deleted_reference(tmp_path):
    source='''Box::struct{x:i32}
g::fn(n:ref i32,p:ref Box){if n!=nil{y:=p.x};if n==nil{ret}}
f::fn(p:ref Box){v:i32=1;g(v,p)}
main::fn(){p:=new Box;if p==nil{ret};del p;f(p)}'''
    expect_exit(source,tmp_path,6,'deleted')
