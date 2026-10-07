"""Loop backedges exclude function returns and matching break-only cleanup."""

import pytest

from conftest import expect_exit, expect_ok


def program(body, *, after='del b', iterations=2, extra='', loop=None):
    statement = loop if loop is not None else 'while i<' + str(iterations) + '{' + body + ';i+=1}'
    return '''Box::struct{value:i32}
''' + extra + '''
check::fn(flag:bool){
 b:=new Box;if b==nil{ret}
 i:usize=0
''' + statement + ';' + after + '\n}\nmain::fn(){check(false)}'


@pytest.mark.parametrize('cleanup', [
    'temp:=new Box;if temp==nil{del b;ret};del temp',
    'if flag{del b;ret}',
    'if flag{defer del b;ret}',
])
def test_return_only_cleanup_keeps_continuing_and_postloop_allocation_live(tmp_path, cleanup):
    expect_ok(program(cleanup + ';v:=b.value'), tmp_path)


def test_return_only_cleanup_does_not_reach_single_iteration_exit(tmp_path):
    expect_ok(program('if flag{del b;ret};v:=b.value', iterations=1), tmp_path)


@pytest.mark.parametrize('exit_statement', ['continue', 'break'])
def test_deletion_reaches_its_continue_or_break_destination(tmp_path, exit_statement):
    source = program('if flag{del b;' + exit_statement + '};v:=b.value', after='v:=b.value')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_break_only_deletion_does_not_poison_earlier_body_reads(tmp_path):
    expect_ok(program('v:=b.value;if flag{del b;break}', after=''), tmp_path)


def test_return_does_not_hide_an_earlier_invalid_read(tmp_path):
    expect_exit(program('if flag{del b;v:=b.value;ret}', after=''), tmp_path, 6, 'Use after move or delete')


def test_callee_return_keeps_deletion_in_the_callers_continuing_path(tmp_path):
    source = program('if b!=nil{drop(b)};v:=b.value', after='', extra='drop::fn(p:ref Box){del p;ret}')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('outer_target', [False, True])
def test_nested_break_targets_inner_exit_or_outer_exit(tmp_path, outer_target):
    target = ' outer' if outer_target else ''
    loop = '@outer while i<2 {v:=b.value;j:usize=0;while j<2 {if flag{del b;break' + target + '};j+=1};i+=1}'
    source = program('', loop=loop, after='')
    if outer_target:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_labeled_continue_runs_leaving_defers_before_outer_backedge(tmp_path):
    loop = '@outer while i<2 {v:=b.value;j:usize=0;while j<2 {if flag{defer del b;continue outer};j+=1};i+=1}'
    expect_exit(program('', loop=loop, after=''), tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('read_first', [False, True])
def test_return_cleanup_defers_retain_lifo_order(tmp_path, read_first):
    statements = 'defer v:=b.value;defer del b' if read_first else 'defer del b;defer v:=b.value'
    # Use an expression statement so defer does not introduce a declaration.
    statements = statements.replace('defer v:=b.value', 'defer consume(b.value)')
    source = program('if flag{' + statements + ';ret};v:=b.value', extra='consume::fn(v:i32){}')
    if read_first:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


def test_break_defer_still_reaches_postloop_use(tmp_path):
    expect_exit(program('if flag{defer del b;break}', after='v:=b.value'), tmp_path, 6, 'Use after move or delete')


def test_for_continue_update_observes_deferred_deletion(tmp_path):
    loop = 'for i=0;i<2;consume(b.value) {if flag{defer del b;continue};i+=1}'
    source = program('', loop=loop, after='', extra='consume::fn(v:i32){}')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_for_in_return_cleanup_keeps_normal_exit_live(tmp_path):
    source = program('', loop='for item in [1,2] {if flag{del b;ret};v:=b.value}')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('terminal', [False, True])
def test_match_join_keeps_only_paths_reaching_the_following_read(tmp_path, terminal):
    arm = 'del b;ret' if terminal else 'del b'
    source = program('match flag {case true:{' + arm + '} else:{}};v:=b.value')
    if terminal:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('terminal', ['ret', 'break', 'continue'])
def test_match_fall_reaches_the_next_arms_exit_destination(tmp_path, terminal):
    source = program('match i {case 0:{del b;fall} case 1:{' + terminal + '} else:{}};v:=b.value')
    if terminal == 'ret':
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_return_cleanup_in_match_does_not_hide_a_deleting_callee(tmp_path):
    source = program('match flag {case true:{drop(b)} else:{}};v:=b.value',
                     after='', extra='drop::fn(p:ref Box){del p;ret}')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_nested_terminal_branches_in_match_do_not_enter_fallthrough_join(tmp_path):
    source = program('match i {case 0:{if flag{del b;ret}else{ret}} else:{}};v:=b.value')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('bound,post_read', [(0, False), (0, True), (1, False)])
def test_inclusive_one_iteration_proof_keeps_exit_deletion(tmp_path, bound, post_read):
    source = program('v:=b.value;del b', after='v:=b.value' if post_read else '', iterations=1)
    source = source.replace('i<1', 'i<=' + str(bound))
    if bound or post_read:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


def test_inclusive_wrapping_bound_cannot_prove_one_iteration(tmp_path):
    source = program('v:=b.value;del b', after='', iterations=1)
    source = source.replace('i:usize=0', 'i:u8=255').replace('i<1', 'i<=255')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('factory', [
    'factory::fn() ref Box {t:=new Box;ret t}',
    'factory::fn() ref Box {ret fresh()}\nfresh::fn() ref Box {t:=new Box;ret t}',
    'factory::fn() ref Box {a:=fresh();b:=fresh();if b!=nil{del b};ret a}\nfresh::fn() ref Box {ret new Box}',
])
def test_known_fresh_factory_keeps_preexisting_allocations_live(tmp_path, factory):
    extra = 'Holder::struct{ptr:ref Box}\n' + factory + '\nset::fn(h:ref Holder,p:ref Box){h.ptr=p}\ndrop::fn(p:ref Box){del p}'
    body = 't:=factory();if t==nil{ret};h:=Holder{ptr:b};set(h,t);if h.ptr==nil{ret};v:=h.ptr.value;drop(h.ptr)'
    expect_ok(program(body, extra=extra), tmp_path)


@pytest.mark.parametrize('borrowed_branch', [False, True])
def test_returned_parameter_identity_is_not_mistaken_for_freshness(tmp_path, borrowed_branch):
    returned = 'if flag{ret new Box};ret p' if borrowed_branch else 'saved:=p;ret saved'
    extra = 'factory::fn(p:ref Box,flag:bool) ref Box {' + returned + '}\nHolder::struct{ptr:ref Box}\ndrop::fn(p:ref Box){del p}'
    body = 'if b==nil{ret};t:=factory(b,flag);if t==nil{ret};h:=Holder{ptr:t};drop(h.ptr)'
    expect_exit(program(body, extra=extra), tmp_path, 6, 'Use after move or delete')


def test_returned_global_identity_survives_a_local_same_named_binding(tmp_path):
    source = '''Box::struct{value:i32}
g:ref Box=nil
get::fn() ref Box {ret g}
main::fn(){g=new Box;if g==nil{ret};saved:=g;{
 g:=new Box;if g==nil{ret}
 t:=get();if t==nil{ret};del t
 v:=g.value;del g
};v:=saved.value}
'''
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('deferred', [False, True])
def test_returned_deleted_allocation_is_rejected(tmp_path, deferred):
    deletion = 'defer del t' if deferred else 'del t'
    extra = 'factory::fn() ref Box {t:=new Box;if t==nil{ret nil};' + deletion + ';ret t}'
    source = program('t:=factory();if t!=nil{v:=t.value}', after='', extra=extra)
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_factory_return_and_field_store_share_the_same_identity(tmp_path):
    extra = '''Holder::struct{ptr:ref Box}
factory::fn(h:ref Holder) ref Box {t:=new Box;h.ptr=t;ret t}
'''
    source = program('h:=Holder{ptr:b};t:=factory(h);if t==nil{ret};del t;if h.ptr!=nil{v:=h.ptr.value}', extra=extra)
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_fresh_return_stored_in_global_field_retains_saved_alias_identity(tmp_path):
    source = '''Box::struct{value:i32}
Holder::struct{ptr:ref Box}
h:Holder=Holder{ptr:nil}
factory::fn() ref Box {ret new Box}
main::fn(){h.ptr=factory();if h.ptr==nil{ret};saved:=h.ptr;del saved;if h.ptr!=nil{v:=h.ptr.value}}
'''
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_returned_argument_uses_its_capture_before_later_argument_deletion(tmp_path):
    extra = '''identity::fn(p:ref Box,n:i32) ref Box {ret p}
consume::fn(p:ref Box) i32 {del p;ret 0}
'''
    source = program('if b==nil{ret};t:=identity(b,consume(b));if t!=nil{v:=t.value}', after='', extra=extra)
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('loop', [
    'while i<1{i+=1;v:=b.value;del b}',
    'if flag{i=1};while i<1{v:=b.value;del b;i+=1}',
    'while i<1{v:=b.value;del b;j:usize=0;while j<1{j+=1;continue};i+=1}',
    'for item in [1]{v:=b.value;del b}',
])
def test_single_body_entry_uses_mandatory_increment_or_fixed_length(tmp_path, loop):
    expect_ok(program('', loop=loop, after=''), tmp_path)


@pytest.mark.parametrize('loop', [
    'while i<2{i+=1;v:=b.value;del b}',
    'if flag{i=1};while i<2{v:=b.value;del b;i+=1}',
    'while i<1{v:=b.value;del b;if flag{continue};i+=1}',
    '@outer while i<1{v:=b.value;del b;j:usize=0;while j<1{continue outer};i+=1}',
    'for item in [1,2]{v:=b.value;del b}',
])
def test_repeated_or_bypassed_increment_keeps_backedge_deletion(tmp_path, loop):
    expect_exit(program('', loop=loop, after=''), tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('loop', [
    'while i<1{i+=1;v:=b.value;del b}',
    'for item in [1]{v:=b.value;del b}',
])
def test_single_body_entry_still_deletes_at_exit(tmp_path, loop):
    expect_exit(program('', loop=loop, after='v:=b.value'), tmp_path, 6, 'Use after move or delete')


def test_loop_local_alias_deletion_reaches_next_field_read(tmp_path):
    source = program('h:=Holder{ptr:b};if h.ptr!=nil{v:=h.ptr.value;alias:=h.ptr;del alias}',
                     after='', extra='Holder::struct{ptr:ref Box}')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_local_alias_fresh_rebind_preserves_original_allocation(tmp_path):
    source = program('alias:=b;alias=new Box;if alias==nil{ret};v:=alias.value;del alias;w:=b.value')
    expect_ok(source, tmp_path)


def test_local_alias_transfer_deletes_only_its_current_allocation(tmp_path):
    source = '''Box::struct{value:i32}
main::fn(){b:=new Box;if b==nil{ret};c:=new Box;if c==nil{del b;ret};i:usize=0
while i<1{alias:=b;alias=c;del alias;i+=1};v:=b.value;del b}
'''
    expect_ok(source, tmp_path)
    expect_exit(source.replace('v:=b.value;del b', 'v:=c.value'), tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('missing_store', [False, True])
def test_falling_match_arm_reaches_the_following_store(tmp_path, missing_store):
    fallback = '' if missing_store else 'h.ptr=new Box'
    extra = '''Holder::struct{ptr:ref Box}
replace::fn(h:ref Holder,x:i32){match x{case 1:{fall} case 2:{h.ptr=new Box} else:{''' + fallback + '''}}}
'''
    source = program('h:=Holder{ptr:b};replace(h,1);if h.ptr==nil{ret};v:=h.ptr.value;del h.ptr', extra=extra)
    if missing_store:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


def test_increment_in_nested_loop_cannot_supply_outer_single_step_proof(tmp_path):
    source = '''Box::struct{value:i32}
main::fn(){b:=new Box;if b==nil{ret};i:u8=254
while i<255{v:=b.value;del b;j:usize=0;while j<2{i+=1;j+=1}}}
'''
    expect_exit(source, tmp_path, 6, 'Use after move or delete')
